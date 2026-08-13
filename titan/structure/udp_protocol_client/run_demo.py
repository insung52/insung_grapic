"""
수동 데모 스크립트 — 실제 UGV 포트 스킴(주기=8000/비주기=8001)을 127.0.0.1에 그대로
띄운 목업 서버에, RC 포트 스킴(주기=8010/비주기=8011)으로 클라이언트가 접속해서
정상/비정상(유실->재시도) 케이스를 눈으로 확인할 수 있게 한다.

Wireshark/tshark가 이 환경에 없어서(설치 안 됨 + 관리자 권한도 없음, pktmon도
loopback 캡처엔 관리자 권한 필요) 실제 와이어 캡처는 생략했다. 대신 sendto() 직전에
실제로 소켓에 나가는 JSON 바이트열을 그대로 출력해서 봉투 포맷이 의도대로 나가는지
육안 확인은 가능하게 했다 — UDP는 페이로드가 그대로 프레임에 실리는 구조라(추가 래핑
없음) 이 바이트열이 곧 와이어 페이로드와 동일하다.

실행: python run_demo.py
"""

from __future__ import annotations

import logging
import time

from client import ProtocolTimeoutError, RetryConfig, UDPProtocolClient
from mock_server import MockUGVServer
from protocol import DeviceCode, Envelope, RC_EVENT_PORT, RC_PERIODIC_PORT, UGV_EVENT_PORT, UGV_PERIODIC_PORT

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("demo")


def show_wire_bytes(label: str, env: Envelope) -> None:
    raw = env.to_json_bytes()
    log.info("[WIRE %s] %d bytes -> %r", label, len(raw), raw.decode("utf-8"))


def main() -> None:
    server = MockUGVServer(
        device=DeviceCode.UGV,
        bind_ip="127.0.0.1",
        periodic_port=UGV_PERIODIC_PORT,
        event_port=UGV_EVENT_PORT,
    ).start()
    client = UDPProtocolClient(
        my_device=DeviceCode.RC,
        local_periodic_addr=("127.0.0.1", RC_PERIODIC_PORT),
        local_event_addr=("127.0.0.1", RC_EVENT_PORT),
        remote_periodic_addr=("127.0.0.1", UGV_PERIODIC_PORT),
        remote_event_addr=("127.0.0.1", UGV_EVENT_PORT),
        retry_config=RetryConfig(
            periodic_timeout_sec=0.3,
            periodic_max_retries=3,
            event_timeout_sec=0.3,
            event_max_retries=3,
        ),
    )

    try:
        log.info("=== 데모 1: 주기성 메시지 정상 왕복 (PeriodBasicInfo) ===")
        show_wire_bytes("Request", Envelope("PeriodBasicInfo", int(DeviceCode.RC), int(DeviceCode.UGV), {"query": "status"}))
        data = client.request("PeriodBasicInfo", int(DeviceCode.UGV), {"query": "status"})
        log.info("Response.data = %s", data)

        log.info("=== 데모 2: 주기성 메시지 유실 2회 후 재시도로 성공 ===")
        server.drop_next_requests(2)
        data = client.request("PeriodBasicInfo", int(DeviceCode.UGV), {"query": "status"})
        log.info("성공(재시도 뒤 회복). Response.data = %s, server.requests_received=%d", data, server.requests_received)

        log.info("=== 데모 3: 주기성 메시지 완전 유실 -> 최대 재시도 소진 ===")
        server.drop_all_requests(True)
        try:
            client.request("PeriodBasicInfo", int(DeviceCode.UGV), {"query": "status"})
        except ProtocolTimeoutError as exc:
            log.info("예상대로 ProtocolTimeoutError 발생: %s (총 시도 %d회)", exc, exc.attempts)
        server.drop_all_requests(False)

        log.info("=== 데모 4: 이벤트 메시지 정상 왕복 (ManualFire) ===")
        show_wire_bytes("Message", Envelope("ManualFire", int(DeviceCode.RC), int(DeviceCode.UGV_RCWS), {}))
        client.send_event("ManualFire", int(DeviceCode.UGV_RCWS), {})
        log.info("ACK 수신 완료")

        log.info("=== 데모 5: 이벤트 메시지 유실 2회 후 재시도로 성공 ===")
        server.drop_next_events(2)
        client.send_event("ManualFire", int(DeviceCode.UGV_RCWS), {})
        log.info("성공(재시도 뒤 회복). server.events_received=%d", server.events_received)

        log.info("=== 데모 6: 이벤트 메시지 완전 유실 -> 3회 재시도(총 4회) 소진 ===")
        server.drop_all_events(True)
        try:
            client.send_event("ManualFire", int(DeviceCode.UGV_RCWS), {})
        except ProtocolTimeoutError as exc:
            log.info("예상대로 ProtocolTimeoutError 발생: %s (총 시도 %d회)", exc, exc.attempts)

    finally:
        client.close()
        server.stop()


if __name__ == "__main__":
    main()
