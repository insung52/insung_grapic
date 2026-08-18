# logging 레코드를 QTextEdit으로 그대로 흘려보내는 핸들러. emit()이 recv 스레드(rc_mock_client의
# _recv_loop)에서도 호출되므로, 실제 텍스트 append는 시그널로 메인(Qt) 스레드에 넘긴다 — Qt
# 시그널은 발신 스레드와 무관하게 안전하게 큐잉되므로(AutoConnection) 이 부분만은 폴링 대신
# 시그널을 쓴다.

from __future__ import annotations

import logging

from PyQt6.QtCore import QObject, pyqtSignal


class QtLogHandler(logging.Handler, QObject):
    log_line = pyqtSignal(str)

    def __init__(self):
        logging.Handler.__init__(self)
        QObject.__init__(self)
        self.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S"))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
        except Exception:
            msg = record.getMessage()
        self.log_line.emit(msg)
