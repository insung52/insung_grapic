"""
LIG UGV축 UDP+JSON 프로토콜 — 봉투 포맷 / 디바이스 코드 / 포트 스킴.

출처: C:\\working\\insung_grapic\\titan\\structure\\protocol_icd.md §3,
      architecture_decisions.md §2 (2026-08-06 LIG 답변, 2026-08-07 갱신).

**확정 사실 (LIG 답변, 바꾸면 안 됨)**:
  - 전송: UDP, 페이로드: JSON 문자열
  - 봉투: {"cmd": str, "src": device, "recv": device, "data": {...}}
  - device 코드: RC=20, UGV=14, UGV_RCWS=13, UGV_ADU=12
  - IP/포트:
        UGV        192.168.10.10   주기=8000   비주기=8001
        원격통제기  192.168.10.20   주기=8010   비주기=8011

**우리 추정치 (LIG 실제 cmd 코드 목록 도착 시 교체 대상)**:
  - CMD_REGISTRY 아래 cmd 이름 / data 필드 스키마
  - Response/ACK가 정확히 어떤 cmd 값·필드로 오는지 (LIG 원본 시퀀스도 미보유)
    → 이 라이브러리는 "Response의 cmd는 Request와 동일한 문자열을 src/recv만
      뒤집어서 돌려준다", "ACK는 cmd='ACK' + data.ackCmd=<원본 cmd>"로 가정하고
      구현했다. 실제 LIG 참조 모듈이 도착하면 client.py의 매칭 로직
      (_match_response / _match_ack)만 교체하면 된다 — 나머지 재시도/소켓 로직은
      그대로 재사용 가능하도록 분리해뒀다.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Optional


class DeviceCode(IntEnum):
    """LIG 확정 device 코드 (protocol_icd.md §1(a))."""

    RC = 20         # 원격통제기 (LIG 제작)
    UGV = 14        # UGV 시뮬레이션 SW (우리 제작)
    UGV_RCWS = 13   # UGV 원격사격통제체계
    UGV_ADU = 12    # UGV 탐지/식별 유닛(가정)


# IP/포트 — LIG 확정 (protocol_icd.md §3.1). 목업 서버 테스트 시엔 127.0.0.1로
# 재바인딩하되 "주기=8000/8001, 비주기=8010/8011" 포트 스킴은 그대로 유지한다.
UGV_IP = "192.168.10.10"
UGV_PERIODIC_PORT = 8000
UGV_EVENT_PORT = 8001

RC_IP = "192.168.10.20"
RC_PERIODIC_PORT = 8010
RC_EVENT_PORT = 8011


# --- 우리 추정 cmd 레지스트리 (protocol_icd.md §3.2) ---------------------------
# 실제 LIG cmd 코드 목록이 오면 이 dict만 갈아끼우면 된다. 값 자체는 client.py
# 로직에서 강제하지 않음(문자열은 호출자가 자유롭게 넘길 수 있음) — 참고/문서화용.
CMD_REGISTRY = {
    # 이벤트성 (Message/ACK) — RC -> UGV/RCWS
    "SetUGVMode": {"src": DeviceCode.RC, "recv": DeviceCode.UGV, "kind": "event"},
    "ManualDrive": {"src": DeviceCode.RC, "recv": DeviceCode.UGV, "kind": "event"},
    "MissionWaypoint": {"src": DeviceCode.RC, "recv": DeviceCode.UGV, "kind": "event"},
    "SetRCWSMode": {"src": DeviceCode.RC, "recv": DeviceCode.UGV_RCWS, "kind": "event"},
    "Movement": {"src": DeviceCode.RC, "recv": DeviceCode.UGV_RCWS, "kind": "event"},
    "ManualFire": {"src": DeviceCode.RC, "recv": DeviceCode.UGV_RCWS, "kind": "event"},
    # 주기성 (Request/Response) — UGV/RCWS -> RC
    "PeriodBasicInfo": {"src": DeviceCode.UGV, "recv": DeviceCode.RC, "kind": "periodic"},
    "PeriodObjectDetectionResult": {"src": DeviceCode.UGV_ADU, "recv": DeviceCode.RC, "kind": "periodic"},
    "PeriodNavigationInfo": {"src": DeviceCode.UGV_ADU, "recv": DeviceCode.RC, "kind": "periodic"},
    "PeriodRCWSStatus": {"src": DeviceCode.UGV_RCWS, "recv": DeviceCode.RC, "kind": "periodic"},
}

ACK_CMD = "ACK"  # 우리 추정 — 이벤트 메시지에 대한 ACK cmd 값. LIG 값 도착 시 교체.


@dataclass
class Envelope:
    """§1(a) 공통 봉투: { cmd, src, recv, data }."""

    cmd: str
    src: int
    recv: int
    data: dict[str, Any] = field(default_factory=dict)

    def to_json_bytes(self) -> bytes:
        return json.dumps(
            {"cmd": self.cmd, "src": int(self.src), "recv": int(self.recv), "data": self.data},
            ensure_ascii=False,
        ).encode("utf-8")

    @staticmethod
    def from_json_bytes(raw: bytes) -> "Envelope":
        obj = json.loads(raw.decode("utf-8"))
        return Envelope(
            cmd=obj["cmd"],
            src=int(obj["src"]),
            recv=int(obj["recv"]),
            data=obj.get("data", {}) or {},
        )

    def is_ack_for(self, cmd: str) -> bool:
        """우리 추정 ACK 매칭 규칙: cmd == 'ACK' and data.ackCmd == 원본 cmd."""
        return self.cmd == ACK_CMD and self.data.get("ackCmd") == cmd

    @staticmethod
    def build_ack(original: "Envelope", *, from_device: int) -> "Envelope":
        return Envelope(
            cmd=ACK_CMD,
            src=from_device,
            recv=original.src,
            data={"ackCmd": original.cmd},
        )

    def is_response_for(self, cmd: str) -> bool:
        """우리 추정 Response 매칭 규칙: 같은 cmd 문자열을 src/recv만 뒤집어 되돌려줌."""
        return self.cmd == cmd

    @staticmethod
    def build_response(original: "Envelope", *, from_device: int, data: dict) -> "Envelope":
        return Envelope(cmd=original.cmd, src=from_device, recv=original.src, data=data)
