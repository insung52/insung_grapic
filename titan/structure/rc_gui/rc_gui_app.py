"""
rc_gui_app.py — UGV 원격통제기(RC) 목업 GUI.

Network/UGVRemoteControlSubsystem.*(UE, titan_example)을 상대로 실제 조이스틱 입력 + RTSP 영상
확인까지 되는 임시 통제기 프로그램. 프로토콜 레이어는 udp_protocol_client/rc_mock_client.py를
그대로 재사용한다(net_client.GuiRCClient 참고).

IP/포트는 전부 실행 인자로만 받는다(UI에 입력 필드 없음) — rc_mock_client.py의 기존 argparse
세트와 동일한 이름을 그대로 씀.

사용 예:
    python rc_gui_app.py --ugv-ip 192.168.10.10
    python rc_gui_app.py --ugv-ip 100.x.x.x --rtsp-host 100.x.x.x   # Tailscale 등 UGV/RTSP 호스트가 다를 때
    python rc_gui_app.py --ugv-ip 127.0.0.1 --rtsp-host 127.0.0.1 --joystick-index 0 --log-level DEBUG

의존성: requirements.txt (PyQt6, opencv-python-headless, pygame-ce)
"""

from __future__ import annotations

import argparse
import logging
import sys

from PyQt6.QtWidgets import QApplication

from main_window import MainWindow
from net_client import GuiRCClient


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    # rc_mock_client.py와 동일한 이름/기본값 (udp_protocol_client/rc_mock_client.py 참고)
    parser.add_argument("--ugv-ip", default="192.168.10.10", help="UGV 시뮬레이션 SW(UE) IP")
    parser.add_argument("--ugv-periodic-port", type=int, default=8000)
    parser.add_argument("--ugv-event-port", type=int, default=8001)
    parser.add_argument("--bind-ip", default="0.0.0.0", help="RC 자신의 수신 바인드 IP")
    parser.add_argument("--rc-periodic-port", type=int, default=8010)
    parser.add_argument("--rc-event-port", type=int, default=8011)

    parser.add_argument("--rtsp-host", default=None, help="RTSP 서버 호스트 (기본: --ugv-ip와 동일)")
    parser.add_argument("--rtsp-port", type=int, default=8554)

    parser.add_argument("--joystick-index", type=int, default=0)
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = parser.parse_args()

    log_level = getattr(logging, args.log_level)
    logging.basicConfig(level=log_level, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s", stream=sys.stdout)

    rtsp_host = args.rtsp_host or args.ugv_ip
    rtsp_base = f"rtsp://{rtsp_host}:{args.rtsp_port}"

    client = GuiRCClient(
        ugv_ip=args.ugv_ip,
        ugv_periodic_port=args.ugv_periodic_port,
        ugv_event_port=args.ugv_event_port,
        bind_ip=args.bind_ip,
        rc_periodic_port=args.rc_periodic_port,
        rc_event_port=args.rc_event_port,
    ).start()

    app = QApplication(sys.argv)
    window = MainWindow(client, rtsp_base, joystick_index=args.joystick_index, log_level=log_level)
    window.show()

    exit_code = app.exec()
    client.stop()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
