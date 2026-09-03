"""
로컬 목업 UGV 서버.

실제 UGV 하드웨어(192.168.10.10)에 접근할 수 없는 환경에서 udp_protocol_client의
재시도/ACK 로직을 검증하기 위한 스탠드인. 같은 프로토콜(§1(a) 봉투, UGV의 포트 스킴
8000=주기/8001=비주기)을 127.0.0.1에 그대로 재현한다.

패킷 유실 시뮬레이션 훅(drop_next_*)을 제공해서, 클라이언트의 재시도 로직이 실제로
발동하는지/최대 재시도 후 어떻게 되는지를 결정론적으로 테스트할 수 있게 했다.
"""

from __future__ import annotations

import logging
import socket
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from protocol import DeviceCode, Envelope, UGV_EVENT_PORT, UGV_PERIODIC_PORT

logger = logging.getLogger("mock_ugv_server")


def _default_response_data(request: Envelope) -> dict:
    """기본 응답 데이터 생성기 — 받은 cmd/data를 그대로 echo. 목업이므로 실제
    business data 스키마(§3.2, 우리 추정치)를 흉내낼 필요는 없고, "무언가 응답이
    왔다"만 검증하면 충분하다는 전제."""
    return {"echo": request.data, "servedCmd": request.cmd}


@dataclass
class _DropCounters:
    lock: threading.Lock = field(default_factory=threading.Lock)
    drop_next_requests: int = 0
    drop_next_events: int = 0
    drop_all_requests: bool = False
    drop_all_events: bool = False


class MockUGVServer:
    def __init__(
        self,
        device: DeviceCode = DeviceCode.UGV,
        bind_ip: str = "127.0.0.1",
        periodic_port: int = UGV_PERIODIC_PORT,
        event_port: int = UGV_EVENT_PORT,
        response_data_fn: Callable[[Envelope], dict] = _default_response_data,
    ):
        self.device = device
        self.response_data_fn = response_data_fn

        self._sock_periodic = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock_periodic.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock_periodic.bind((bind_ip, periodic_port))
        self._sock_periodic.settimeout(0.2)  # stop 이벤트 폴링 주기

        self._sock_event = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock_event.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock_event.bind((bind_ip, event_port))
        self._sock_event.settimeout(0.2)

        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []
        self._drops = _DropCounters()

        # 통계 — 테스트에서 재시도가 실제 일어났는지 검증하는 데 사용
        self.stats_lock = threading.Lock()
        self.requests_received = 0
        self.requests_dropped = 0
        self.responses_sent = 0
        self.events_received = 0
        self.events_dropped = 0
        self.acks_sent = 0

    # ------------------------------------------------------------------
    def start(self) -> "MockUGVServer":
        t1 = threading.Thread(target=self._run_periodic_loop, daemon=True, name="mock-ugv-periodic")
        t2 = threading.Thread(target=self._run_event_loop, daemon=True, name="mock-ugv-event")
        self._threads = [t1, t2]
        t1.start()
        t2.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        for t in self._threads:
            t.join(timeout=2)
        self._sock_periodic.close()
        self._sock_event.close()

    def __enter__(self) -> "MockUGVServer":
        return self.start()

    def __exit__(self, *exc) -> None:
        self.stop()

    # --- 패킷 유실 시뮬레이션 제어 -------------------------------------
    def drop_next_requests(self, n: int) -> None:
        """다음 n개의 Request를 조용히 무시(Response 안 보냄) — 재시도 유발용."""
        with self._drops.lock:
            self._drops.drop_next_requests = n

    def drop_next_events(self, n: int) -> None:
        """다음 n개의 Message를 조용히 무시(ACK 안 보냄) — 재시도 유발용."""
        with self._drops.lock:
            self._drops.drop_next_events = n

    def drop_all_requests(self, enabled: bool = True) -> None:
        """최대 재시도 소진 케이스 테스트용 — 영구 무응답."""
        with self._drops.lock:
            self._drops.drop_all_requests = enabled

    def drop_all_events(self, enabled: bool = True) -> None:
        with self._drops.lock:
            self._drops.drop_all_events = enabled

    # ------------------------------------------------------------------
    def _run_periodic_loop(self) -> None:
        while not self._stop.is_set():
            try:
                raw, addr = self._sock_periodic.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError:
                break
            try:
                env = Envelope.from_json_bytes(raw)
            except (ValueError, KeyError) as exc:
                logger.warning("malformed request ignored: %s", exc)
                continue

            with self.stats_lock:
                self.requests_received += 1

            if self._should_drop_request():
                with self.stats_lock:
                    self.requests_dropped += 1
                logger.info("[MOCK] DROP Request cmd=%s from %s (simulated loss)", env.cmd, addr)
                continue

            data = self.response_data_fn(env)
            response = Envelope.build_response(env, from_device=int(self.device), data=data)
            self._sock_periodic.sendto(response.to_json_bytes(), addr)
            with self.stats_lock:
                self.responses_sent += 1
            logger.info("[MOCK] Response cmd=%s -> %s", env.cmd, addr)

    def _run_event_loop(self) -> None:
        while not self._stop.is_set():
            try:
                raw, addr = self._sock_event.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError:
                break
            try:
                env = Envelope.from_json_bytes(raw)
            except (ValueError, KeyError) as exc:
                logger.warning("malformed message ignored: %s", exc)
                continue

            with self.stats_lock:
                self.events_received += 1

            if self._should_drop_event():
                with self.stats_lock:
                    self.events_dropped += 1
                logger.info("[MOCK] DROP Message cmd=%s from %s (simulated loss)", env.cmd, addr)
                continue

            ack = Envelope.build_ack(env, from_device=int(self.device))
            self._sock_event.sendto(ack.to_json_bytes(), addr)
            with self.stats_lock:
                self.acks_sent += 1
            logger.info("[MOCK] ACK cmd=%s -> %s", env.cmd, addr)

    def _should_drop_request(self) -> bool:
        with self._drops.lock:
            if self._drops.drop_all_requests:
                return True
            if self._drops.drop_next_requests > 0:
                self._drops.drop_next_requests -= 1
                return True
            return False

    def _should_drop_event(self) -> bool:
        with self._drops.lock:
            if self._drops.drop_all_events:
                return True
            if self._drops.drop_next_events > 0:
                self._drops.drop_next_events -= 1
                return True
            return False


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    server = MockUGVServer()
    server.start()
    print("Mock UGV server running on 127.0.0.1: periodic=%d event=%d (Ctrl+C to stop)" % (UGV_PERIODIC_PORT, UGV_EVENT_PORT))
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()
