# 조이스틱 입력 -> RC_* 프로토콜 명령 매핑.
#
# 2026-08-18 확인: 실제 연결된 장치가 Extreme 3D Pro(단일 스틱 플라이트 조이스틱, 축 4개/버튼
# 12개)라 듀얼스틱 게임패드 전제(왼쪽=주행/오른쪽=조준)를 쓸 수 없음 — 사용자 결정으로 주행은
# 키보드(WASD, keyboard_driving.py)로 분리하고 이 조이스틱은 RCWS 조준(Pan/Tilt) + 사격 관련
# 버튼 전용으로 씀. 버튼 번호는 여전히 placeholder — 로그 패널에 매 tick 원본 축/버튼 값을
# DEBUG 레벨로 찍어주므로(--log-level DEBUG), 조이스틱을 움직여보면서 어떤 인덱스가 뭔지
# 눈으로 확인해서 여기 상수만 고치면 된다.
#
# 필드명/값은 전부 UGVRemoteControlSubsystem.cpp의 Handle_RC_* 구현을 직접 읽고 맞춘 것 —
# ICD 원문 오타(BRUST/CONTINUS 등)도 그대로 보존.

from __future__ import annotations

import logging

import pygame
from PyQt6.QtCore import QObject, QTimer

from net_client import DeviceCode, GuiRCClient

logger = logging.getLogger("rc_gui.joystick")

TICK_HZ = 20  # RC_RemoteDriving 20Hz 스펙에 맞춤 (rc_mock_client.py run_scenario와 동일)
TICK_MS = int(1000 / TICK_HZ)
AXIS_DEADZONE = 0.08

# --- 축 매핑 (Extreme 3D Pro 기준: 축0=X 기울임, 축1=Y 기울임, 축2=트위스트, 축3=슬로틀 슬라이더) ---
AXIS_RCWS_PAN = 0       # 스틱 X 기울임 -> RC_Movement.XAxis
AXIS_RCWS_TILT = 1       # 스틱 Y 기울임 -> RC_Movement.YAxis
INVERT_TILT = True

# --- 버튼 매핑 (placeholder, 눌림 엣지에서 1회만 전송) -------------------------
BUTTON_FIRE = 0                 # 홀드 — RC_FireWeapon(FireButton PRESSED/RELEASE)
BUTTON_CHARGE_TOGGLE = 1        # RC_ChargeWeapon(ChargeSwitch ON/OFF) 토글
BUTTON_ARM_TOGGLE = 2           # RC_ActivateFire(안전/암 스위치) 토글
BUTTON_IGNITION_TOGGLE = 3      # RC_ActivateMovement(시동) 토글
BUTTON_FIRE_MODE_CYCLE = 4      # SINGLE -> BRUST -> CONTINUS 순환
BUTTON_CAMERA_TOGGLE = 5        # RC_SelectCamera(EO/IR) 토글
BUTTON_EMERGENCY_STOP = 6
BUTTON_EMERGENCY_RELEASE = 7

FIRE_MODE_CYCLE = ["SINGLE", "BRUST", "CONTINUS"]


class JoystickController(QObject):
    def __init__(self, client: GuiRCClient, joystick_index: int = 0, parent=None):
        super().__init__(parent)
        self.client = client
        self.enabled = False  # 제어권 획득 전에는 주행/조준 명령을 보내지 않음

        pygame.init()
        pygame.joystick.init()
        self.joystick = None
        if pygame.joystick.get_count() > joystick_index:
            self.joystick = pygame.joystick.Joystick(joystick_index)
            self.joystick.init()
            logger.info(
                "조이스틱 연결됨: %s (축 %d개, 버튼 %d개)",
                self.joystick.get_name(), self.joystick.get_numaxes(), self.joystick.get_numbuttons(),
            )
        else:
            logger.warning("조이스틱을 찾지 못함 — 연결 후 프로그램을 재시작하세요")

        self._prev_buttons: list[bool] = []
        self._charge_on = False
        self._armed = False
        self._ignition_on = True
        self._fire_mode_idx = 0
        self._brake_held = False  # BrakeButton=PRESSED 상태(비상 정지용 별도 버튼과는 무관)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(TICK_MS)

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled
        logger.info("조이스틱 -> 프로토콜 송신 %s", "활성화" if enabled else "비활성화")

    # ------------------------------------------------------------------
    def _tick(self) -> None:
        if not self.joystick:
            return
        pygame.event.pump()

        axes = [self.joystick.get_axis(i) for i in range(self.joystick.get_numaxes())]
        buttons = [bool(self.joystick.get_button(i)) for i in range(self.joystick.get_numbuttons())]
        logger.debug("axes=%s buttons=%s", ["%.2f" % a for a in axes], buttons)

        if not self._prev_buttons:
            self._prev_buttons = [False] * len(buttons)

        if not self.enabled:
            self._prev_buttons = buttons
            return

        self._send_rcws_aim(axes)
        self._handle_buttons(buttons)
        self._prev_buttons = buttons

    def _axis(self, axes: list[float], index: int, invert: bool = False) -> float:
        if index >= len(axes):
            return 0.0
        v = axes[index]
        if abs(v) < AXIS_DEADZONE:
            v = 0.0
        return -v if invert else v

    def _send_rcws_aim(self, axes: list[float]) -> None:
        pan = self._axis(axes, AXIS_RCWS_PAN)
        tilt = self._axis(axes, AXIS_RCWS_TILT, INVERT_TILT)
        self.client.send("RC_Movement", DeviceCode.UGV_RCWS, {
            "XAxis": round(pan * 100),
            "YAxis": round(tilt * 100),
            "BrakeButton": "PRESSED" if self._brake_held else "RELEASE",
        })

    def _pressed(self, buttons: list[bool], index: int) -> bool:
        if index >= len(buttons) or index >= len(self._prev_buttons):
            return False
        return buttons[index] and not self._prev_buttons[index]

    def _released(self, buttons: list[bool], index: int) -> bool:
        if index >= len(buttons) or index >= len(self._prev_buttons):
            return False
        return not buttons[index] and self._prev_buttons[index]

    def _handle_buttons(self, buttons: list[bool]) -> None:
        # 방아쇠 — 홀드형: 누른 순간 PRESSED, 뗀 순간 RELEASE
        if BUTTON_FIRE < len(buttons):
            if self._pressed(buttons, BUTTON_FIRE):
                self.client.send("RC_FireWeapon", DeviceCode.UGV_RCWS, {"FireButton": "PRESSED"})
            elif self._released(buttons, BUTTON_FIRE):
                self.client.send("RC_FireWeapon", DeviceCode.UGV_RCWS, {"FireButton": "RELEASE"})

        if self._pressed(buttons, BUTTON_CHARGE_TOGGLE):
            self._charge_on = not self._charge_on
            self.client.send("RC_ChargeWeapon", DeviceCode.UGV_RCWS, {"ChargeSwitch": "ON" if self._charge_on else "OFF"})

        if self._pressed(buttons, BUTTON_ARM_TOGGLE):
            self._armed = not self._armed
            # ICD 원문: RELEASE=활성(안전 해제), PRESSED=비활성(안전) — 토글 상태를 그 값으로 환산
            self.client.send("RC_ActivateFire", DeviceCode.UGV_RCWS, {"ActivateFireToggle": "RELEASE" if self._armed else "PRESSED"})

        if self._pressed(buttons, BUTTON_IGNITION_TOGGLE):
            self._ignition_on = not self._ignition_on
            self.client.send("RC_ActivateMovement", DeviceCode.UGV, {"ActivateMovementToggle": "RELEASE" if self._ignition_on else "PRESSED"})

        if self._pressed(buttons, BUTTON_FIRE_MODE_CYCLE):
            self._fire_mode_idx = (self._fire_mode_idx + 1) % len(FIRE_MODE_CYCLE)
            self.client.send("RC_FireMode", DeviceCode.UGV_RCWS, {"FireMode": FIRE_MODE_CYCLE[self._fire_mode_idx]})

        if self._pressed(buttons, BUTTON_CAMERA_TOGGLE):
            # PRESSED=IR, RELEASE=EO(Handle_RC_SelectCamera) — 매 누름마다 반대로 토글
            self._camera_ir = not getattr(self, "_camera_ir", False)
            self.client.send("RC_SelectCamera", DeviceCode.UGV_RCWS, {"SelectCameraButton": "PRESSED" if self._camera_ir else "RELEASE"})

        if self._pressed(buttons, BUTTON_EMERGENCY_STOP):
            self.client.send("RC_EmergencyStop", DeviceCode.UGV, {"CommandDevice": 1})

        if self._pressed(buttons, BUTTON_EMERGENCY_RELEASE):
            self.client.send("RC_EmergencyStopRelease", DeviceCode.UGV, {"CommandDevice": 1})
            # §2 결정(코드 주석 참고): 해제 후 STAY로 떨어지므로, 실제 오퍼레이터가 항상 다음에
            # 할 동작(REMOTE 재요청)을 여기서 바로 이어서 보냄.
            self.client.send("RC_OperationMode", DeviceCode.UGV, {"OperationMode": "REMOTE"})
