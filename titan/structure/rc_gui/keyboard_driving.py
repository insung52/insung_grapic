# 키보드(WASD) -> RC_RemoteDriving. 조이스틱(Extreme 3D Pro, 단일 스틱)은 RCWS 조준 전용으로
# 쓰기로 결정(사용자 결정, 2026-08-18)해서 주행은 별도로 키보드에 배정.
#
# RC_RemoteDriving은 20Hz 주기 명령이라(ICD, rc_mock_client.py의 RC_TO_UGV_ROUTING 참고)
# 키를 안 누르고 있어도 매 tick 계속 보내야 함 — UE측 Handle_RC_RemoteDriving엔 "일정 시간
# 명령이 안 오면 정지" 같은 데드맨 스위치가 없어서, 여기서 안 보내면 마지막으로 받은 값이
# 그대로 유지되기 때문(예: W를 뗐는데도 계속 전진). 그래서 아무 키도 안 눌려있으면
# Acceleration=0/Brake=0(코스트)을 명시적으로 계속 보낸다.

from __future__ import annotations

import logging

from PyQt6.QtCore import QObject, Qt, QTimer

from net_client import DeviceCode, GuiRCClient

logger = logging.getLogger("rc_gui.keyboard")

TICK_HZ = 20
TICK_MS = int(1000 / TICK_HZ)

DRIVE_ACCELERATION = 80  # W/S 홀드 시 고정 스로틀(0..100) — 아날로그 아님, 키보드라 On/Off
STEER_MAGNITUDE = 100    # A/D 홀드 시 고정 조향각(-100..100)

DRIVE_KEYS = {Qt.Key.Key_W, Qt.Key.Key_A, Qt.Key.Key_S, Qt.Key.Key_D}


class KeyboardDrivingController(QObject):
    def __init__(self, client: GuiRCClient, parent=None):
        super().__init__(parent)
        self.client = client
        self.enabled = False
        self._held: set[Qt.Key] = set()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(TICK_MS)

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled
        self._held.clear()
        logger.info("키보드 주행(WASD) -> 프로토콜 송신 %s", "활성화" if enabled else "비활성화")

    def key_pressed(self, key: Qt.Key) -> None:
        if key in DRIVE_KEYS:
            self._held.add(key)

    def key_released(self, key: Qt.Key) -> None:
        self._held.discard(key)

    # ------------------------------------------------------------------
    def _tick(self) -> None:
        if not self.enabled:
            return

        forward = Qt.Key.Key_W in self._held
        backward = Qt.Key.Key_S in self._held and not forward
        left = Qt.Key.Key_A in self._held
        right = Qt.Key.Key_D in self._held and not left

        if forward:
            acceleration, gear = DRIVE_ACCELERATION, "FRONT"
        elif backward:
            acceleration, gear = DRIVE_ACCELERATION, "BACK"
        else:
            acceleration, gear = 0, "FRONT"

        # A=+100/D=-100 가정(왼쪽=양수) — Handle_RC_RemoteDriving은 TurnInput 부호를 그대로
        # 차량 스티어링에 넘길 뿐이라 실제 좌/우 방향은 테스트하며 반대면 부호만 뒤집으면 됨.
        steering = STEER_MAGNITUDE if left else (-STEER_MAGNITUDE if right else 0)

        self.client.send("RC_RemoteDriving", DeviceCode.UGV, {
            "Acceleration": acceleration,
            "Brake": 0,
            "Steering": steering,
            "Gear": gear,
        })
