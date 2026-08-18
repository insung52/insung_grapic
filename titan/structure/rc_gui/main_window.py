# 메인 윈도우 — 레이아웃: 왼쪽 CCTV 4개(세로) / 가운데 RCWS 메인뷰(크게) / 오른쪽 UGV 상태정보
# (프로토콜로 수신 가능한 모든 cmd) / 하단 로그 패널. 사용자 지정 레이아웃 그대로.

from __future__ import annotations

import logging

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QPlainTextEdit,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)
from PyQt6.QtCore import Qt

from joystick_control import JoystickController
from keyboard_driving import KeyboardDrivingController
from net_client import DeviceCode, GuiRCClient
from qt_log_handler import QtLogHandler
from video_panel import VideoPanel

logger = logging.getLogger("rc_gui")

STATUS_POLL_MS = 200

# (cmd, 한글 라벨) — UGVRemoteControlSubsystem.cpp의 Send*/Handle_RC_Request_BIT* 가 실제로
# 보내는 cmd 전부. 순서 = 화면에 뜨는 순서.
STATUS_GROUPS = [
    ("UGV_Response_Connection", "연결 (UGV)"),
    ("UGV_Response_Connection_ADU", "연결 (ADU)"),
    ("UGV_Response_BIT", "BIT (UGV)"),
    ("UGV_Response_BIT_ADU", "BIT (ADU)"),
    ("UGV_Period_Basicinfo", "기본상태"),
    ("UGV_RCWS_Status", "RCWS"),
    ("UGV_Period_NavigationInformation", "항법(UTM)"),
    ("UGV_Period_BasicInformation", "주행거리"),
    ("UGV_Period_ObjectDetectionResult", "탐지 객체"),
    ("RPT_ObjectiveReached", "미션 도착 보고 (확장)"),
]


class MainWindow(QMainWindow):
    def __init__(self, client: GuiRCClient, rtsp_base: str, joystick_index: int = 0, log_level: int = logging.INFO):
        super().__init__()
        self.client = client
        self._log_level = log_level
        self.setWindowTitle("UGV 원격통제기 목업 (RC Mock)")
        self.resize(1600, 950)

        self._video_panels: list[VideoPanel] = []
        self._status_value_labels: dict[str, QLabel] = {}

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(4, 4, 4, 4)

        root.addWidget(self._build_toolbar())

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(self._build_main_area(rtsp_base))
        splitter.addWidget(self._build_log_panel())
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)
        root.addWidget(splitter, stretch=1)

        self.joystick = JoystickController(client, joystick_index=joystick_index)
        self.keyboard = KeyboardDrivingController(client)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self._refresh_status)
        self.status_timer.start(STATUS_POLL_MS)

    # ------------------------------------------------------------------
    def _build_toolbar(self) -> QWidget:
        bar = QWidget()
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(0, 0, 0, 0)

        btn_connect = QPushButton("연결 (RC_Connection)")
        btn_connect.clicked.connect(self._on_connect)
        btn_control = QPushButton("제어권 획득 + REMOTE")
        btn_control.clicked.connect(self._on_acquire_control)
        btn_estop = QPushButton("비상정지")
        btn_estop.setStyleSheet("background-color: #661111; color: white; font-weight: bold;")
        btn_estop.clicked.connect(self._on_emergency_stop)
        btn_release = QPushButton("비상정지 해제")
        btn_release.clicked.connect(self._on_emergency_release)

        for b in (btn_connect, btn_control, btn_estop, btn_release):
            layout.addWidget(b)
        layout.addStretch(1)

        # close()를 직접 호출 -> closeEvent가 소켓/영상스레드/로그핸들러 정리까지 다 해줌(창 X
        # 버튼으로 닫는 것과 동일 경로).
        btn_quit = QPushButton("종료")
        btn_quit.clicked.connect(self.close)
        layout.addWidget(btn_quit)

        return bar

    def _build_main_area(self, rtsp_base: str) -> QWidget:
        area = QWidget()
        layout = QHBoxLayout(area)
        layout.setContentsMargins(0, 0, 0, 0)

        # 왼쪽 — CCTV 4개 세로
        cctv_col = QWidget()
        cctv_layout = QVBoxLayout(cctv_col)
        cctv_layout.setContentsMargins(0, 0, 0, 0)
        for name, label in (
            ("front_cctv", "전면 CCTV"),
            ("rear_cctv", "후면 CCTV"),
            ("left_cctv", "좌측 CCTV"),
            ("right_cctv", "우측 CCTV"),
        ):
            panel = VideoPanel(name, f"{rtsp_base}/ugv/{name}", title=label)
            self._video_panels.append(panel)
            cctv_layout.addWidget(panel, stretch=1)
        cctv_col.setMaximumWidth(360)

        # 가운데 — RCWS 메인뷰(크게)
        rcws_panel = VideoPanel("rcws", f"{rtsp_base}/ugv/rcws", title="RCWS 메인뷰")
        self._video_panels.append(rcws_panel)

        # 오른쪽 — 상태정보
        status_scroll = self._build_status_panel()
        status_scroll.setMaximumWidth(380)

        layout.addWidget(cctv_col)
        layout.addWidget(rcws_panel, stretch=1)
        layout.addWidget(status_scroll)
        return area

    def _build_status_panel(self) -> QScrollArea:
        container = QWidget()
        vbox = QVBoxLayout(container)

        for cmd, label in STATUS_GROUPS:
            box = QGroupBox(label)
            box_layout = QVBoxLayout(box)
            value_label = QLabel("(수신 대기중)")
            value_label.setWordWrap(True)
            value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            box_layout.addWidget(value_label)
            vbox.addWidget(box)
            self._status_value_labels[cmd] = value_label

        vbox.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(container)
        return scroll

    def _build_log_panel(self) -> QWidget:
        box = QGroupBox("로그")
        layout = QVBoxLayout(box)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(2000)
        self.log_view.setStyleSheet("background-color: #0b0b0b; color: #ccc; font-family: Consolas, monospace; font-size: 11px;")
        layout.addWidget(self.log_view)

        self._log_handler = QtLogHandler()
        self._log_handler.log_line.connect(self._append_log)
        self._log_handler.setLevel(self._log_level)
        logging.getLogger().addHandler(self._log_handler)

        return box

    def _append_log(self, line: str) -> None:
        self.log_view.appendPlainText(line)

    # ------------------------------------------------------------------
    def _on_connect(self) -> None:
        self.client.send("RC_Connection", DeviceCode.UGV, {"RequestDevice": 1})
        self.client.send("RC_Request_BIT", DeviceCode.UGV, {"RequestBit": 1})

    def _on_acquire_control(self) -> None:
        self.client.send("RC_Control_Right", DeviceCode.UGV, {"ControlRight": 1})
        self.client.send("RC_OperationMode", DeviceCode.UGV, {"OperationMode": "REMOTE"})
        self.joystick.set_enabled(True)
        self.keyboard.set_enabled(True)
        self.setFocus()  # WASD를 받으려면 메인윈도우가 포커스를 갖고 있어야 함

    def _on_emergency_stop(self) -> None:
        self.joystick.set_enabled(False)
        self.keyboard.set_enabled(False)
        self.client.send("RC_EmergencyStop", DeviceCode.UGV, {"CommandDevice": 1})

    def _on_emergency_release(self) -> None:
        self.client.send("RC_EmergencyStopRelease", DeviceCode.UGV, {"CommandDevice": 1})
        self.client.send("RC_OperationMode", DeviceCode.UGV, {"OperationMode": "REMOTE"})
        self.joystick.set_enabled(True)
        self.keyboard.set_enabled(True)
        self.setFocus()

    # ------------------------------------------------------------------
    def keyPressEvent(self, event) -> None:
        if not event.isAutoRepeat():
            self.keyboard.key_pressed(Qt.Key(event.key()))
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event) -> None:
        if not event.isAutoRepeat():
            self.keyboard.key_released(Qt.Key(event.key()))
        super().keyReleaseEvent(event)

    # ------------------------------------------------------------------
    def _refresh_status(self) -> None:
        snapshot = self.client.snapshot()
        for cmd, label_widget in self._status_value_labels.items():
            data = snapshot.get(cmd)
            if data is None:
                continue
            if cmd == "UGV_Period_ObjectDetectionResult":
                label_widget.setText(self._format_detection(data))
            else:
                label_widget.setText("\n".join(f"{k}: {v}" for k, v in data.items()))

    @staticmethod
    def _format_detection(data: dict) -> str:
        total = data.get("TotalObject", 0)
        objects = data.get("Objects", []) or []
        lines = [f"TotalObject: {total}"]
        for obj in objects:
            lines.append(
                f"  #{obj.get('ObjectID')} {obj.get('ObjectClass')} "
                f"vel={obj.get('Velocity')} UTM=({obj.get('East')},{obj.get('North')})"
            )
        return "\n".join(lines)

    # ------------------------------------------------------------------
    def closeEvent(self, event) -> None:
        # logging 모듈은 모든 Handler를 생성 시점에 전역 weakref 레지스트리(_handlerList)에도
        # 등록해뒀다가 인터프리터 종료 시 atexit로 logging.shutdown()이 그 전부를 순회하며
        # close()를 부름 — removeHandler()만으로는 로거의 handlers 목록에서만 빠지고 이
        # 전역 레지스트리엔 남아있어서, Qt가 이미 C++ 객체를 지운 뒤에 shutdown()이 접근하면
        # RuntimeError가 난다. close()를 직접 불러 전역 레지스트리에서도 제거해야 함.
        logging.getLogger().removeHandler(self._log_handler)
        self._log_handler.close()
        for panel in self._video_panels:
            panel.shutdown()
        self.client.stop()
        super().closeEvent(event)
