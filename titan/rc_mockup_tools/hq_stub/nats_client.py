"""hq.cmd.<axis> / hq.rpt.<axis> 발행/구독 래퍼: protocol_icd.md §0, §5

이 스텁은 상위체계 역할이므로:
  - hq.cmd.<axis> 에 발행 (하달, HQ_*)
  - hq.rpt.<axis> 를 구독 (보고 수신, RPT_*)
"""
from __future__ import annotations

import json
from typing import Any, Awaitable, Callable, Optional

import nats
from nats.aio.client import Client as NATS
from nats.aio.msg import Msg

from .envelope import SeqCounter, SessionClock, build_envelope

AXES = ("ugv", "selfdefense")

ReportHandler = Callable[[str, dict[str, Any]], Awaitable[None]]


def cmd_subject(axis: str) -> str:
    return f"hq.cmd.{axis}"


def rpt_subject(axis: str) -> str:
    return f"hq.rpt.{axis}"


class HqStubClient:
    """상위체계 역할 NATS 클라이언트: hq.cmd.*로 발행, hq.rpt.*를 구독."""

    def __init__(self, nats_url: str = "nats://127.0.0.1:4222", use_jetstream: bool = False) -> None:
        self._nats_url = nats_url
        self._use_jetstream = use_jetstream
        self._nc: Optional[NATS] = None
        self._js = None
        self._clock = SessionClock()
        self._seq = {axis: SeqCounter() for axis in AXES}

    async def connect(self) -> None:
        self._nc = await nats.connect(self._nats_url)
        if self._use_jetstream:
            # 스트림 생성/관리는 인프라(NATS 서버 설정) 소관 — 이 클라이언트는 만들지 않고
            # hq.cmd.<axis>/hq.rpt.<axis>를 이미 물고 있는 기존 스트림에 얹혀만 감.
            # 스트림이 아직 없으면 publish/subscribe 시 nats.js 에러로 바로 드러남.
            self._js = self._nc.jetstream()

    async def close(self) -> None:
        if self._nc is not None:
            await self._nc.drain()

    async def publish_command(self, axis: str, cmd: str, payload: dict[str, Any]) -> dict[str, Any]:
        if axis not in AXES:
            raise ValueError(f"unknown axis: {axis!r} (expected one of {AXES})")
        assert self._nc is not None, "connect() 먼저 호출해야 함"

        envelope = build_envelope(cmd, self._seq[axis].next(), self._clock.elapsed_ms(), payload)
        data = json.dumps(envelope).encode("utf-8")
        subject = cmd_subject(axis)

        if self._use_jetstream and self._js is not None:
            await self._js.publish(subject, data)
        else:
            await self._nc.publish(subject, data)
        return envelope

    async def subscribe_reports(self, on_report: ReportHandler) -> None:
        """hq.rpt.ugv / hq.rpt.selfdefense 둘 다 구독하고, 수신할 때마다 on_report(axis, envelope) 호출."""
        assert self._nc is not None, "connect() 먼저 호출해야 함"

        async def _handler(msg: Msg) -> None:
            axis = msg.subject.split(".")[-1]
            try:
                envelope = json.loads(msg.data.decode("utf-8"))
            except json.JSONDecodeError:
                return
            await on_report(axis, envelope)
            if self._use_jetstream:
                await msg.ack()

        for axis in AXES:
            subject = rpt_subject(axis)
            if self._use_jetstream and self._js is not None:
                await self._js.subscribe(subject, cb=_handler, durable=f"hq-stub-{axis}")
            else:
                await self._nc.subscribe(subject, cb=_handler)
