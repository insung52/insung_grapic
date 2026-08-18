# UDP+JSON 프로토콜 송수신 — udp_protocol_client/rc_mock_client.py의 RCMockClient를 그대로
# 재사용한다(Envelope 인코딩/포트 라우팅/연결 시맨틱을 여기서 새로 안 짬, 단일 소스 유지).
#
# GuiRCClient는 RCMockClient 대비 딱 하나만 확장한다: 원본은 4개 cmd(Basicinfo/Navigation/
# RCWSStatus/ObjectDetectionResult)의 최신값만 저장했는데, GUI 우측 상태 패널은 BIT
# 응답(UGV_Response_BIT*)이나 RPT_ObjectiveReached 등 프로토콜로 오는 모든 cmd를 보여줘야 해서
# last_by_cmd(cmd -> 최신 data dict)로 일반화한다. _recv_loop 본문을 그대로 오버라이드하는
# 이유는 원본 메서드에 훅 포인트가 없어서(부모를 고치지 않고 GUI 전용 파일 안에서만 확장하기
# 위해 어쩔 수 없이 복붙+한 줄 추가).

from __future__ import annotations

import logging
import os
import socket
import sys
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "udp_protocol_client"))
from rc_mock_client import (  # noqa: E402
    DeviceCode,
    Envelope,
    RC_TO_UGV_ROUTING,
    RCMockClient,
)

logger = logging.getLogger("rc_gui.net")


class GuiRCClient(RCMockClient):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # cmd -> 최신 data dict. 메인 윈도우가 QTimer로 폴링(stats_lock 하에 읽음) —
        # 프로젝트 전반에서 이벤팅보다 폴링을 일관되게 선호하는 것과 동일한 이유로, 여기서도
        # Qt 시그널 없이 단순 폴링으로 처리한다.
        self.last_by_cmd: dict[str, dict] = {}

    def _recv_loop(self, sock: socket.socket, label: str) -> None:
        while not self._stop.is_set():
            try:
                raw, addr = sock.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError:
                break
            try:
                env = Envelope.from_json_bytes(raw)
            except (ValueError, KeyError) as exc:
                logger.warning("[RECV %s] JSON 파싱 실패 from %s: %s (raw=%r)", label, addr, exc, raw[:200])
                continue

            with self.stats_lock:
                self.received_counts[env.cmd] = self.received_counts.get(env.cmd, 0) + 1
                self.last_by_cmd[env.cmd] = env.data
                if env.cmd == "UGV_Period_Basicinfo":
                    self.last_basicinfo = env.data
                elif env.cmd == "UGV_Period_NavigationInformation":
                    self.last_navigation = env.data
                elif env.cmd == "UGV_RCWS_Status":
                    self.last_rcws_status = env.data
                elif env.cmd == "UGV_Period_ObjectDetectionResult":
                    self.last_detection = env.data

            logger.info("[RECV %-8s <- %s] cmd=%s data=%s", label, addr, env.cmd, env.data)

    def snapshot(self) -> dict[str, dict]:
        """last_by_cmd의 스레드 안전 얕은 복사본 — 메인 스레드 QTimer가 매 tick 호출."""
        with self.stats_lock:
            return dict(self.last_by_cmd)


__all__ = ["GuiRCClient", "DeviceCode", "Envelope", "RC_TO_UGV_ROUTING"]
