# RTSP 영상 패널 — rtsp_viewer_test/rtsp_test_client.py에서 이미 검증된 접근(OpenCV
# cv2.VideoCapture + CAP_FFMPEG 백엔드, CONNECT_TIMEOUT_SEC 넘게 프레임이 안 오면 재접속)을
# 그대로 따른다. python-vlc 등 새 의존성 대신 이미 이 프로젝트에서 실제 RTSP 서버 상대로
# 동작 확인된 스택을 재사용 — 검증 안 된 새 라이브러리를 넣을 이유가 없어서.

from __future__ import annotations

import time

import cv2
import numpy as np
from PyQt6.QtCore import QThread, Qt, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

# rtsp_test_client.py와 동일한 기준 — 이 시간(초) 안에 프레임이 안 오면 접속을 버리고 새로 연다.
CONNECT_TIMEOUT_SEC = 8.0
RECONNECT_BACKOFF_SEC = 1.0


class VideoCaptureThread(QThread):
    frame_ready = pyqtSignal(QImage)
    status_changed = pyqtSignal(str)  # "connecting" | "live" | "lost"

    def __init__(self, name: str, url: str, parent=None):
        super().__init__(parent)
        self.name = name
        self.url = url
        self._stop = False

    def stop(self) -> None:
        self._stop = True
        self.wait(2000)

    def run(self) -> None:
        cap = None
        last_frame_time = None
        attempt_start = time.monotonic()
        self.status_changed.emit("connecting")

        while not self._stop:
            if cap is None:
                cap = cv2.VideoCapture(self.url, cv2.CAP_FFMPEG)
                try:
                    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                except Exception:
                    pass
                attempt_start = time.monotonic()
                self.status_changed.emit("connecting")

            since = last_frame_time if last_frame_time is not None else attempt_start
            if (time.monotonic() - since) > CONNECT_TIMEOUT_SEC:
                cap.release()
                cap = None
                last_frame_time = None
                self.status_changed.emit("lost")
                time.sleep(RECONNECT_BACKOFF_SEC)
                continue

            ret, frame = cap.read()
            if not ret or frame is None:
                continue

            last_frame_time = time.monotonic()
            self.status_changed.emit("live")

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            rgb = np.ascontiguousarray(rgb)
            h, w, ch = rgb.shape
            qimg = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888).copy()
            self.frame_ready.emit(qimg)

        if cap is not None:
            cap.release()


class VideoPanel(QWidget):
    def __init__(self, name: str, url: str, title: str = "", parent=None):
        super().__init__(parent)
        self.name = name
        self.url = url

        self.title_label = QLabel(title or name)
        self.title_label.setStyleSheet("color: #ccc; font-weight: bold;")

        self.video_label = QLabel("연결 중...")
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setStyleSheet("background-color: #111; color: #888;")
        self.video_label.setMinimumSize(160, 90)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.addWidget(self.title_label)
        layout.addWidget(self.video_label, stretch=1)

        self._thread = VideoCaptureThread(name, url)
        self._thread.frame_ready.connect(self._on_frame)
        self._thread.status_changed.connect(self._on_status)
        self._thread.start()

    def _on_frame(self, qimg: QImage) -> None:
        pixmap = QPixmap.fromImage(qimg).scaled(
            self.video_label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        )
        self.video_label.setPixmap(pixmap)

    def _on_status(self, status: str) -> None:
        colors = {"connecting": "#886600", "live": "#004400", "lost": "#660000"}
        self.title_label.setStyleSheet(f"color: #fff; font-weight: bold; background-color: {colors.get(status, '#333')};")
        if status != "live" and self.video_label.pixmap() is None:
            self.video_label.setText({"connecting": "연결 중...", "lost": "연결 끊김 - 재접속 중..."}.get(status, ""))

    def closeEvent(self, event) -> None:
        self._thread.stop()
        super().closeEvent(event)

    def shutdown(self) -> None:
        self._thread.stop()
