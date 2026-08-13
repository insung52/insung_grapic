"""공통 봉투(Envelope) 포맷: protocol_icd.md §1

{ "cmd": str, "seq": uint32, "ts": uint64(세션 시작 후 경과 ms), "payload": {} }
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SessionClock:
    """ts 필드용: 이 프로세스(세션) 시작 후 경과 ms."""

    _start: float = field(default_factory=time.monotonic)

    def elapsed_ms(self) -> int:
        return int((time.monotonic() - self._start) * 1000)


class SeqCounter:
    """seq 필드용: 송신측 단조증가 카운터 (수신측 유실/재정렬 감지용, §1)."""

    def __init__(self) -> None:
        self._next = 0

    def next(self) -> int:
        value = self._next
        self._next += 1
        return value


def build_envelope(cmd: str, seq: int, ts_ms: int, payload: dict[str, Any]) -> dict[str, Any]:
    return {"cmd": cmd, "seq": seq, "ts": ts_ms, "payload": payload}
