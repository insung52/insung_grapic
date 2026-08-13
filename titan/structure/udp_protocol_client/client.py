"""
UGV축 UDP+JSON 프로토콜 클라이언트 라이브러리.

LIG가 확정한 것(protocol_icd.md §3.1, architecture_decisions.md §2):
  - UDP + JSON 문자열, {cmd, src, recv, data} 봉투
  - 주기성 메시지(Request/Response): 응답 없으면 N회까지 Request 재전송
  - 이벤트 메시지(Message/ACK): 일정 msec 내 ACK 없으면 3회까지 Message 재전송

LIG가 빈칸으로 남긴 것 (우리가 정한 기본값 — RetryConfig 참고, README에도 근거 정리):
  - 주기성 재시도 횟수 → 3회 (스펙 예시값 "예: 3회" 그대로 채택)
  - 주기성 응답 대기 타임아웃 → 500ms (스펙에 값 자체가 없어 우리가 신규로 정함)
  - 이벤트 ACK 대기 타임아웃 → 300ms (스펙 제시 범위 200~500ms 중 중간값)
  - 이벤트 재시도 횟수 → 3회 (이건 스펙 원문에 이미 명시됨, 우리가 정한 게 아님)

이 클라이언트는 **한 번에 하나의 in-flight 요청만 지원하는 동기(blocking) 모델**이다.
LIG 봉투에 seq/request-id 같은 상관관계 필드가 없어서(§1(a) 참고), 응답을 "같은 cmd
문자열이 src/recv만 뒤집혀 돌아온 것"으로 매칭한다(protocol.py의 Envelope.is_response_for /
is_ack_for). 동시에 같은 cmd로 여러 요청을 동시에 보내는 유스케이스는 이 매칭 규칙으로는
구분 불가능 — 실사용 전 LIG 원본 시퀀스도로 반드시 재확인 필요(README "다음에 할 일" 참고).
"""

from __future__ import annotations

import logging
import socket
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional

from protocol import DeviceCode, Envelope

logger = logging.getLogger("udp_protocol_client")


@dataclass
class RetryConfig:
    # 주기성 메시지 (Request/Response)
    periodic_timeout_sec: float = 0.5      # 우리가 정함 (스펙 자체엔 빈칸도 아니고 미기재)
    periodic_max_retries: int = 3          # 우리가 정함 (스펙 빈칸, "예: 3회" 채택)

    # 이벤트 메시지 (Message/ACK)
    event_timeout_sec: float = 0.3         # 우리가 정함 (스펙 빈칸, 200~500ms 권장 범위 중간)
    event_max_retries: int = 3             # 스펙에 명시된 값 (우리가 정한 게 아님)


class ProtocolTimeoutError(TimeoutError):
    def __init__(self, cmd: str, attempts: int, kind: str):
        super().__init__(f"{kind} '{cmd}' timed out after {attempts} attempt(s)")
        self.cmd = cmd
        self.attempts = attempts
        self.kind = kind


class UDPProtocolClient:
    """LIG UGV축 봉투 포맷으로 통신하는 재사용 가능한 UDP 클라이언트.

    실제 하드웨어(192.168.10.10/.20)든 로컬 목업(127.0.0.1)이든, 생성자에
    주소만 바꿔 넣으면 동일하게 동작한다.
    """

    def __init__(
        self,
        my_device: DeviceCode,
        local_periodic_addr: tuple[str, int],
        local_event_addr: tuple[str, int],
        remote_periodic_addr: tuple[str, int],
        remote_event_addr: tuple[str, int],
        retry_config: Optional[RetryConfig] = None,
    ):
        self.my_device = my_device
        self.remote_periodic_addr = remote_periodic_addr
        self.remote_event_addr = remote_event_addr
        self.retry = retry_config or RetryConfig()

        self._sock_periodic = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock_periodic.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock_periodic.bind(local_periodic_addr)

        self._sock_event = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock_event.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock_event.bind(local_event_addr)

    def close(self) -> None:
        self._sock_periodic.close()
        self._sock_event.close()

    def __enter__(self) -> "UDPProtocolClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # ------------------------------------------------------------------
    # 주기성 메시지: Request -> Response (타임아웃 시 Request 재전송)
    # ------------------------------------------------------------------
    def request(
        self,
        cmd: str,
        recv_device: int,
        data: dict[str, Any],
        *,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
    ) -> dict[str, Any]:
        """Request를 보내고 Response의 data를 반환. 소진 시 ProtocolTimeoutError."""
        timeout = self.retry.periodic_timeout_sec if timeout is None else timeout
        max_retries = self.retry.periodic_max_retries if max_retries is None else max_retries

        envelope = Envelope(cmd=cmd, src=int(self.my_device), recv=int(recv_device), data=data)
        raw = envelope.to_json_bytes()

        total_attempts = max_retries + 1  # 최초 전송 1회 + 재시도 max_retries회
        for attempt in range(1, total_attempts + 1):
            logger.info("[REQUEST] cmd=%s attempt=%d/%d -> %s", cmd, attempt, total_attempts, self.remote_periodic_addr)
            self._sock_periodic.sendto(raw, self.remote_periodic_addr)

            resp = self._recv_until(
                self._sock_periodic,
                deadline=time.monotonic() + timeout,
                predicate=lambda env: env.is_response_for(cmd) and env.recv == int(self.my_device),
            )
            if resp is not None:
                logger.info("[RESPONSE] cmd=%s received on attempt %d/%d", cmd, attempt, total_attempts)
                return resp.data

            logger.warning("[REQUEST] cmd=%s no response within %.3fs (attempt %d/%d)", cmd, timeout, attempt, total_attempts)

        raise ProtocolTimeoutError(cmd, total_attempts, "Request")

    def serve_request_once(
        self,
        handler: Callable[[Envelope], dict[str, Any]],
        *,
        timeout: Optional[float] = None,
    ) -> Optional[Envelope]:
        """Responder 역할: Request 하나를 받아 handler(envelope)->data 로 처리 후 Response 전송.
        목업 서버 및 (장차) UGV 시뮬레이션 SW 쪽 구현에서 재사용."""
        deadline = None if timeout is None else time.monotonic() + timeout
        result = self._recv_raw(self._sock_periodic, deadline)
        if result is None:
            return None
        env, addr = result
        data = handler(env)
        response = Envelope.build_response(env, from_device=int(self.my_device), data=data)
        self._sock_periodic.sendto(response.to_json_bytes(), addr)
        logger.info("[RESPONSE] cmd=%s sent -> %s", env.cmd, addr)
        return env

    # ------------------------------------------------------------------
    # 이벤트 메시지: Message -> ACK (타임아웃 시 Message 최대 3회 재전송)
    # ------------------------------------------------------------------
    def send_event(
        self,
        cmd: str,
        recv_device: int,
        data: dict[str, Any],
        *,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
    ) -> None:
        """Message를 보내고 ACK를 기다림. 소진 시 ProtocolTimeoutError."""
        timeout = self.retry.event_timeout_sec if timeout is None else timeout
        max_retries = self.retry.event_max_retries if max_retries is None else max_retries

        envelope = Envelope(cmd=cmd, src=int(self.my_device), recv=int(recv_device), data=data)
        raw = envelope.to_json_bytes()

        total_attempts = max_retries + 1
        for attempt in range(1, total_attempts + 1):
            logger.info("[MESSAGE] cmd=%s attempt=%d/%d -> %s", cmd, attempt, total_attempts, self.remote_event_addr)
            self._sock_event.sendto(raw, self.remote_event_addr)

            ack = self._recv_until(
                self._sock_event,
                deadline=time.monotonic() + timeout,
                predicate=lambda env: env.is_ack_for(cmd) and env.recv == int(self.my_device),
            )
            if ack is not None:
                logger.info("[ACK] cmd=%s received on attempt %d/%d", cmd, attempt, total_attempts)
                return

            logger.warning("[MESSAGE] cmd=%s no ACK within %.3fs (attempt %d/%d)", cmd, timeout, attempt, total_attempts)

        raise ProtocolTimeoutError(cmd, total_attempts, "Message")

    def serve_event_once(
        self,
        handler: Callable[[Envelope], None],
        *,
        timeout: Optional[float] = None,
    ) -> Optional[Envelope]:
        """Responder 역할: Message 하나를 받아 handler(envelope) 처리 후 ACK 전송."""
        deadline = None if timeout is None else time.monotonic() + timeout
        result = self._recv_raw(self._sock_event, deadline)
        if result is None:
            return None
        env, addr = result
        handler(env)
        ack = Envelope.build_ack(env, from_device=int(self.my_device))
        self._sock_event.sendto(ack.to_json_bytes(), addr)
        logger.info("[ACK] cmd=%s sent -> %s", env.cmd, addr)
        return env

    # ------------------------------------------------------------------
    # 내부 유틸
    # ------------------------------------------------------------------
    @staticmethod
    def _recv_raw(sock: socket.socket, deadline: Optional[float]) -> Optional[tuple[Envelope, tuple[str, int]]]:
        remaining = None if deadline is None else max(0.0, deadline - time.monotonic())
        sock.settimeout(remaining)
        try:
            raw, addr = sock.recvfrom(65535)
        except socket.timeout:
            return None
        try:
            return Envelope.from_json_bytes(raw), addr
        except (ValueError, KeyError) as exc:
            logger.warning("malformed packet from %s ignored: %s", addr, exc)
            return None

    @classmethod
    def _recv_until(
        cls,
        sock: socket.socket,
        deadline: float,
        predicate: Callable[[Envelope], bool],
    ) -> Optional[Envelope]:
        """deadline까지, predicate에 맞는 패킷이 올 때까지 수신. 상관없는 패킷은 버림."""
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None
            sock.settimeout(remaining)
            try:
                raw, _addr = sock.recvfrom(65535)
            except socket.timeout:
                return None
            try:
                env = Envelope.from_json_bytes(raw)
            except (ValueError, KeyError) as exc:
                logger.warning("malformed packet ignored: %s", exc)
                continue
            if predicate(env):
                return env
            logger.debug("unrelated packet ignored: cmd=%s src=%s", env.cmd, env.src)
