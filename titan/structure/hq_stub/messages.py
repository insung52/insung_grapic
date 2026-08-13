"""Layer A 메시지 정의: protocol_icd.md §2(공통 타입), §5(Layer A 메시지 전체)

상위체계 → SW(하달, HQ_*) 4종의 payload 빌더와, SW → 상위체계(보고, RPT_*) 6종의
cmd 이름 상수를 담는다. 이 스텁은 상위체계 역할이므로 HQ_*는 발행, RPT_*는 수신만 한다.
"""
from __future__ import annotations

from typing import Any, Optional, TypedDict


class Coord(TypedDict):
    lat: float
    lon: float
    alt: float


class BBox(TypedDict):
    x: float
    y: float
    w: float
    h: float


class Detection(TypedDict):
    id: str
    type: str  # "Person" | "Vehicle"
    bbox: BBox
    coord: Optional[Coord]
    confidence: float


def coord(lat: float, lon: float, alt: float = 0.0) -> Coord:
    """§2: lat/lon = WGS84 십진수 도, alt = 미터 AGL."""
    return {"lat": lat, "lon": lon, "alt": alt}


# --- 하달 (HQ_*, 상위체계 → SW) ---

HQ_ENEMY_CONTACT_REPORT = "HQ_EnemyContactReport"
HQ_MISSION_MOVE_TO_ENGAGE = "HQ_MissionMoveToEngage"
HQ_ENGAGEMENT_AUTHORIZATION = "HQ_EngagementAuthorization"
HQ_MISSION_ENGAGE_FLEEING = "HQ_MissionEngageFleeing"


def hq_enemy_contact_report(contact_id: str, contact_coord: Coord) -> dict[str, Any]:
    """#4-1, 상위체계→자체방호SW."""
    return {"contactId": contact_id, "coord": contact_coord}


def hq_mission_move_to_engage(target: Coord, radius: float) -> dict[str, Any]:
    """#4-4, 상위체계→UGV SW."""
    return {"target": target, "radius": radius}


def hq_engagement_authorization(approved: bool, contact_id: str) -> dict[str, Any]:
    """#4-6, 상위체계→UGV SW."""
    return {"approved": approved, "contactId": contact_id}


def hq_mission_engage_fleeing(fleeing_coord: Coord) -> dict[str, Any]:
    """#4-8, 상위체계→자체방호SW."""
    return {"coord": fleeing_coord}


# --- 보고 (RPT_*, SW → 상위체계) — 이 스텁은 수신만 하므로 cmd 이름 상수만 필요 ---

RPT_TARGETS_IDENTIFIED = "RPT_TargetsIdentified"  # #4-3, 자체방호SW→상위체계, FYI
RPT_OBJECTIVE_REACHED = "RPT_ObjectiveReached"  # #4-5, UGV SW→상위체계, FYI
RPT_CONTACT_DETECTED = "RPT_ContactDetected"  # #4-6, UGV SW→상위체계
RPT_ENGAGEMENT_INITIATED = "RPT_EngagementInitiated"  # #4-7, UGV SW→상위체계, FYI
RPT_ENGAGEMENT_RESULT = "RPT_EngagementResult"  # #4-7, UGV SW→상위체계
RPT_SCENARIO_COMPLETE = "RPT_ScenarioComplete"  # #4-8, 자체방호SW→상위체계
