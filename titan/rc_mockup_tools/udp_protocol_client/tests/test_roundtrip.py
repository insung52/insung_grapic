"""
클라이언트 <-> 로컬 목업 UGV 서버 왕복 테스트.

정상 케이스(응답/ACK 옴)와 비정상 케이스(유실 시뮬레이션 후 재시도가 실제로
일어나는지, 최대 재시도 후 어떻게 되는지) 둘 다 검증한다.

실행: `python -m unittest discover -s tests -v` (udp_protocol_client 디렉토리에서)
또는 `python tests/test_roundtrip.py`
"""

from __future__ import annotations

import itertools
import logging
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from client import ProtocolTimeoutError, RetryConfig, UDPProtocolClient
from mock_server import MockUGVServer
from protocol import DeviceCode

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

# 테스트 간 포트 충돌을 피하기 위해 매 테스트마다 새 포트 쌍을 할당.
# (실제 UGV 포트 스킴 8000/8001 재현은 mock_server.py 기본값 및 run_demo.py에서 확인)
_port_gen = itertools.count(19000, 10)


def _alloc_ports() -> tuple[int, int, int, int]:
    base = next(_port_gen)
    return base, base + 1, base + 2, base + 3  # ugv_periodic, ugv_event, rc_periodic, rc_event


class RoundtripTestCase(unittest.TestCase):
    def setUp(self) -> None:
        ugv_p, ugv_e, rc_p, rc_e = _alloc_ports()
        self.server = MockUGVServer(
            device=DeviceCode.UGV,
            bind_ip="127.0.0.1",
            periodic_port=ugv_p,
            event_port=ugv_e,
        ).start()
        self.client = UDPProtocolClient(
            my_device=DeviceCode.RC,
            local_periodic_addr=("127.0.0.1", rc_p),
            local_event_addr=("127.0.0.1", rc_e),
            remote_periodic_addr=("127.0.0.1", ugv_p),
            remote_event_addr=("127.0.0.1", ugv_e),
            retry_config=RetryConfig(
                periodic_timeout_sec=0.15,
                periodic_max_retries=2,
                event_timeout_sec=0.1,
                event_max_retries=3,
            ),
        )

    def tearDown(self) -> None:
        self.client.close()
        self.server.stop()

    # ------------------------------------------------------------------
    # 주기성 메시지 (Request/Response)
    # ------------------------------------------------------------------
    def test_periodic_normal_roundtrip(self):
        """정상 케이스: 응답이 바로 옴 -> 재시도 0회."""
        data = self.client.request("PeriodBasicInfo", int(DeviceCode.UGV), {"probe": 1})
        self.assertEqual(data["echo"], {"probe": 1})
        self.assertEqual(self.server.requests_received, 1)
        self.assertEqual(self.server.responses_sent, 1)
        self.assertEqual(self.server.requests_dropped, 0)

    def test_periodic_retry_recovers(self):
        """비정상->정상 케이스: 첫 2번 유실, 3번째 시도에서 응답 -> 재시도 로직이
        실제로 동작해서 결국 성공하는지 확인."""
        self.server.drop_next_requests(2)
        data = self.client.request("PeriodBasicInfo", int(DeviceCode.UGV), {"probe": 2})
        self.assertEqual(data["echo"], {"probe": 2})
        self.assertEqual(self.server.requests_received, 3)  # 최초 1 + 재시도 2
        self.assertEqual(self.server.requests_dropped, 2)
        self.assertEqual(self.server.responses_sent, 1)

    def test_periodic_retry_exhausted(self):
        """완전 유실 케이스: 최대 재시도(2) 소진 후 ProtocolTimeoutError."""
        self.server.drop_all_requests(True)
        with self.assertRaises(ProtocolTimeoutError) as ctx:
            self.client.request("PeriodBasicInfo", int(DeviceCode.UGV), {"probe": 3})
        self.assertEqual(ctx.exception.attempts, 3)  # 최초 1 + 재시도 2
        self.assertEqual(self.server.requests_received, 3)
        self.assertEqual(self.server.responses_sent, 0)

    # ------------------------------------------------------------------
    # 이벤트 메시지 (Message/ACK)
    # ------------------------------------------------------------------
    def test_event_normal_roundtrip(self):
        self.client.send_event("ManualFire", int(DeviceCode.UGV_RCWS), {"trigger": True})
        self.assertEqual(self.server.events_received, 1)
        self.assertEqual(self.server.acks_sent, 1)
        self.assertEqual(self.server.events_dropped, 0)

    def test_event_retry_recovers(self):
        self.server.drop_next_events(2)
        self.client.send_event("ManualFire", int(DeviceCode.UGV_RCWS), {"trigger": True})
        self.assertEqual(self.server.events_received, 3)  # 최초 1 + 재시도 2
        self.assertEqual(self.server.events_dropped, 2)
        self.assertEqual(self.server.acks_sent, 1)

    def test_event_retry_exhausted(self):
        """완전 유실: 스펙 명시대로 3회까지 재시도(총 4회 전송) 후 ProtocolTimeoutError."""
        self.server.drop_all_events(True)
        with self.assertRaises(ProtocolTimeoutError) as ctx:
            self.client.send_event("ManualFire", int(DeviceCode.UGV_RCWS), {"trigger": True})
        self.assertEqual(ctx.exception.attempts, 4)  # 최초 1 + 재시도 3
        self.assertEqual(self.server.events_received, 4)
        self.assertEqual(self.server.acks_sent, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
