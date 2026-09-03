"""HQ 스텁 실행 진입점. 사용법: hq_stub/README.md 참고.

    python -m hq_stub --mode manual
    python -m hq_stub --mode auto --nats-url nats://127.0.0.1:4222
"""
from __future__ import annotations

import argparse
import asyncio
import sys

from . import logger
from .nats_client import HqStubClient
from .scenario import ReportBus, run_scenario

# Windows 콘솔 기본 코드페이지(cp949)는 이모지/일부 기호(—)를 못 담아 UnicodeEncodeError가 남.
if sys.stdout.encoding is not None and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="상위체계(HQ) 테스트 스텁 — hq.cmd.*/hq.rpt.* NATS 발행/구독"
    )
    parser.add_argument(
        "--nats-url", default="nats://127.0.0.1:4222",
        help="NATS 서버 URL (기본: nats://127.0.0.1:4222)",
    )
    parser.add_argument(
        "--mode", choices=("auto", "manual"), default="manual",
        help="auto=자동 재생, manual=단계별 수동 트리거 (기본: manual)",
    )
    parser.add_argument(
        "--jetstream", action="store_true",
        help="JetStream 사용 (기본: core NATS pub/sub). protocol_icd.md §0은 JetStream 권장이지만"
             " 개발 초기엔 서버에 JetStream이 안 켜져 있을 수 있어 기본은 꺼둠.",
    )
    parser.add_argument(
        "--no-auto-approve", action="store_true",
        help="auto 모드에서 교전승인(#4-6)을 자동 거부로 설정 (기본은 자동 승인)",
    )
    return parser.parse_args()


async def _main() -> None:
    args = parse_args()
    client = HqStubClient(nats_url=args.nats_url, use_jetstream=args.jetstream)
    bus = ReportBus()

    logger.log_info(f"NATS 연결 중: {args.nats_url} (jetstream={args.jetstream})")
    await client.connect()
    await client.subscribe_reports(bus.on_report)
    logger.log_info(f"연결됨. 모드={args.mode}. hq.rpt.ugv / hq.rpt.selfdefense 구독 중...")

    try:
        await run_scenario(
            client, bus,
            manual=(args.mode == "manual"),
            auto_approve=not args.no_auto_approve,
        )
    except KeyboardInterrupt:
        logger.log_info("사용자 중단.")
    finally:
        await client.close()


def main() -> None:
    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
