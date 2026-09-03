"""시나리오 단계별 메시지 체인 드라이버: architecture_decisions.md §3, protocol_icd.md §5

#4-1(침투보고) → #4-2~3(정찰/식별, FYI보고) → #4-4(이동명령) → #4-5(도착, FYI보고) →
#4-6(포착→교전승인 요청) → #4-7(교전개시 FYI+결과보고) → #4-8(잔적 교전승인→최종섬멸→
RPT_ScenarioComplete)

두 가지 모드:
  - auto:   순서대로 자동 발행, 각 단계 사이 짧게 대기
  - manual: 사용자가 엔터/커맨드로 한 단계씩 트리거 (실제 테스트 시나리오 트리거용)

수신된 RPT_*는 모드와 무관하게 도착 즉시 항상 콘솔에 로그된다(ReportBus.on_report).
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Optional

from . import logger, messages
from .nats_client import HqStubClient

# 테스트용 더미 좌표/값 — 위경도(WGS84), §2. 필요하면 여기서 수정.
CONTACT_ID = "CT-001"
ENEMY_COORD = messages.coord(lat=36.1000, lon=127.3000, alt=0.0)
ENGAGE_TARGET = messages.coord(lat=36.1005, lon=127.3006, alt=0.0)
ENGAGE_RADIUS = 20.0
FLEEING_COORD = messages.coord(lat=36.0988, lon=127.2991, alt=0.0)

RPT_WAIT_TIMEOUT_SEC = 30.0
AUTO_STEP_DELAY_SEC = 1.5


class ReportBus:
    """수신된 RPT_*을 항상 로그 + cmd별 큐에 적재 (드라이버의 대기 지점에서 소비)."""

    def __init__(self) -> None:
        self._queues: dict[str, asyncio.Queue[dict[str, Any]]] = {}

    def _queue_for(self, cmd: str) -> "asyncio.Queue[dict[str, Any]]":
        return self._queues.setdefault(cmd, asyncio.Queue())

    async def on_report(self, axis: str, envelope: dict[str, Any]) -> None:
        logger.log_incoming(axis, envelope)
        cmd = envelope.get("cmd", "")
        await self._queue_for(cmd).put(envelope)

    async def wait_for(self, cmd: str, timeout: float = RPT_WAIT_TIMEOUT_SEC) -> Optional[dict[str, Any]]:
        try:
            return await asyncio.wait_for(self._queue_for(cmd).get(), timeout=timeout)
        except asyncio.TimeoutError:
            logger.log_info(f"[타임아웃] {cmd} 수신 대기 {timeout:.0f}s 초과 — 계속 진행")
            return None


@dataclass
class ScenarioState:
    contact_id: str = CONTACT_ID


async def _publish(client: HqStubClient, axis: str, cmd: str, payload: dict[str, Any]) -> None:
    envelope = await client.publish_command(axis, cmd, payload)
    logger.log_outgoing(axis, envelope)


async def _prompt(step_label: str, description: str) -> str:
    loop = asyncio.get_event_loop()
    prompt_text = f"\n[{step_label}] {description}\n  엔터=진행, q=중단 > "
    return await loop.run_in_executor(None, input, prompt_text)


async def _prompt_yes_no(question: str, default: bool = True) -> bool:
    loop = asyncio.get_event_loop()
    suffix = "[Y/n]" if default else "[y/N]"
    answer = await loop.run_in_executor(None, input, f"  {question} {suffix} > ")
    answer = answer.strip().lower()
    if not answer:
        return default
    return answer.startswith("y")


async def run_scenario(client: HqStubClient, bus: ReportBus, manual: bool, auto_approve: bool) -> None:
    state = ScenarioState()

    async def step(label: str, description: str) -> bool:
        """manual 모드면 엔터 대기(q=중단), auto 모드면 로그 후 짧게 대기."""
        if manual:
            answer = await _prompt(label, description)
            if answer.strip().lower() == "q":
                return False
        else:
            logger.log_info(f"[{label}] {description}")
            await asyncio.sleep(AUTO_STEP_DELAY_SEC)
        return True

    # #4-1 침투보고
    if not await step("4-1", "적 침투 감지됨 — HQ_EnemyContactReport 하달"):
        return
    await _publish(
        client, "selfdefense", messages.HQ_ENEMY_CONTACT_REPORT,
        messages.hq_enemy_contact_report(state.contact_id, ENEMY_COORD),
    )

    # #4-2~3 정찰/식별(에뮬레이터/SW 내부 처리) → FYI 보고 대기
    logger.log_info("[4-2~3] 자체방호축 정찰/식별 처리 대기 중 (RPT_TargetsIdentified) ...")
    await bus.wait_for(messages.RPT_TARGETS_IDENTIFIED)

    # #4-4 이동명령
    if not await step("4-4", "UGV 교전 위치로 이동 명령 — HQ_MissionMoveToEngage 하달"):
        return
    await _publish(
        client, "ugv", messages.HQ_MISSION_MOVE_TO_ENGAGE,
        messages.hq_mission_move_to_engage(ENGAGE_TARGET, ENGAGE_RADIUS),
    )

    # #4-5 도착 FYI
    logger.log_info("[4-5] 목적지 도착 대기 중 (RPT_ObjectiveReached, FYI) ...")
    await bus.wait_for(messages.RPT_OBJECTIVE_REACHED)

    # #4-6 포착 → 교전승인 게이트 (판단/보고 게이트 원칙: 발사만 게이트)
    logger.log_info("[4-6] 접촉 포착 대기 중 (RPT_ContactDetected) ...")
    await bus.wait_for(messages.RPT_CONTACT_DETECTED)

    if manual:
        approved = await _prompt_yes_no("교전을 승인합니까? (HQ_EngagementAuthorization)", default=True)
    else:
        logger.log_info(f"[4-6] auto 모드: 교전승인 자동 {'승인' if auto_approve else '거부'}")
        await asyncio.sleep(AUTO_STEP_DELAY_SEC)
        approved = auto_approve

    await _publish(
        client, "ugv", messages.HQ_ENGAGEMENT_AUTHORIZATION,
        messages.hq_engagement_authorization(approved, state.contact_id),
    )

    # #4-7 교전개시 FYI + 결과보고 (승인 안 됐으면 스킵)
    if approved:
        logger.log_info("[4-7] 교전개시/결과 대기 중 (RPT_EngagementInitiated, RPT_EngagementResult) ...")
        await bus.wait_for(messages.RPT_ENGAGEMENT_INITIATED)
        await bus.wait_for(messages.RPT_ENGAGEMENT_RESULT)
    else:
        logger.log_info("[4-7] 교전 미승인 — 교전개시/결과 보고 대기를 건너뜁니다.")

    # #4-8 잔적 교전승인 → 최종섬멸
    if not await step("4-8", "도주 잔적 소탕 명령 — HQ_MissionEngageFleeing 하달"):
        return
    await _publish(
        client, "selfdefense", messages.HQ_MISSION_ENGAGE_FLEEING,
        messages.hq_mission_engage_fleeing(FLEEING_COORD),
    )

    logger.log_info("[4-8] 시나리오 완료 보고 대기 중 (RPT_ScenarioComplete) ...")
    await bus.wait_for(messages.RPT_SCENARIO_COMPLETE)

    logger.log_info("시나리오 종료.")
