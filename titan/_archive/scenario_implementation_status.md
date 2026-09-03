> [보관됨 2026-08-31] 최신 버전: `level_new_kadex_0811/scenario_three_stage_combat.md`. 사유: 이 문서는
> 옛 레벨(`kadex_demo_0716`) 기준 구현 현황이고, 새 레벨(New_kadex_0811)의 3단계 전투
> 시나리오로 작업이 넘어감(2026-08-22~23). 아군 이동/회피/포메이션 관련 근본원인 수정
> 기록(§1, §7 MCP 함정)은 여전히 참고 가치 있음 — 완전히 무효는 아니고 옛 레벨 기준임에 유의.

# 시나리오 구현 현황 + 남은 작업 계획 (2026-08-04 갱신)

> `ally_and_scenario_system_plan.md`(최초 설계 논의) → `scenario_datatable_system_plan.md`
> (DataTable 스텝 시스템 설계) → 2026-07-31 스냅샷 → **이 문서(2026-08-04)**. `시나리오.md`
> (#4-1~#4-8) 기준 번호 유지. 이번 라운드는 "아군+UGV 동반 이동이 실제로 매끄럽게
> 작동하게 만들기"(경로탐색/회피/속도 버그를 근본 원인까지 추적)와 "UAV 카메라가 아군+적군을
> 실제로 다 프레임 안에 담기"에 집중했음 — 세부 사항은 아래. **적 5명 도주(#4-7) + 자체방호
> RCWS 전환(#4-8)은 여전히 스킵 확정** — "교전 지역(UGV 목적지 근처)에서 적을 전부 사살"로
> 단순화.

---

## 1. 아군 + UGV 동반 이동/전투 (#4-4~#4-6 핵심)

### 대형(포메이션) — 2026-08-04 전면 재설계
30명을 6개 분대(각 5명)로 나눠 분대별 1열 종대(전후 200cm 간격)로 배치. 1·2분대가 UGV
바로 양옆(우측/좌측, 최근 좌우 간격 250cm로 축소 + 200cm 전진해서 UGV보다 살짝 앞서
나옴 — UGV RCWS/UAV 시야에 몇 명 정도 걸리도록), 3·4분대가 한 열 뒤, 5·6분대가 맨 뒤.
UGV 정중앙 뒤쪽(뒤 방향)은 비워둠. 분대장(`bIsSquadLeader`, 수신호 재생 주체) = 1분대
맨 앞. 각 아군의 `AllyFormationComponent::FormationOffsetFromLeader`(UGV 로컬 좌표,
X=전후/Y=좌우)로 저장 — MCP로 조정 가능(단, Vector 필드는 x/y/z 각각 별도 호출 필요,
7절 참고).

### FormingUp(집결)
아군 각자 NavMesh 경로로 목표 위치까지 순차 스태거 출발. `FormUpStaggerSeconds`
1.2초 → **0.7초로 하향**(2026-08-04) — 원래 이 값을 올렸던 건 텐트 병목 정체의 진짜
원인(아래 참고)을 못 찾아서 쓴 임시방편이었고, 근본 원인을 고친 뒤로는 더 짧아도 안전함이
확인됨. 정체 감지 시 자동 재탐색.

### Following(동반 질주)
UGV의 실제 주행 경로(polyline) 위 arc-length 기준으로 대형 유지하며 따라감
(`ComputeFormationPointOnPath`) — UGV 실제 속도에 맞춰 아군도 가속/감속
(`FollowCatchUpMarginCmPerSec`). **주의**: 이 상태는 매 틱 새로 NavMesh 경로를 쿼리하지
않는 순수 기하학적 계산이라, UGV에 대한 물리적 회피는 전적으로 RVO(아래 3단 방어 참고)에
의존함 — RVO를 끄고 테스트할 때 가장 먼저 확인해야 할 구간.

### 이동 로직 버그 — 근본 원인까지 추적해서 고친 것들 (2026-08-03~04)
- **"찔끔찔끔" 정지-재출발 반복**: 예전 이진 데드존(`MovementDeadZoneCm`)을 선형 감속
  램프(`ApproachSlowdownDistanceCm`) + 하드 정지(`StopDistanceCm`) 2단 구조로 교체.
- **"도리도리"(제자리 회전)**: `StopDistanceCm` 미만이면 조향 자체(`AddMovementInput`
  호출)를 스킵 — 회전도 안 건드림.
- **텐트 병목 정체**: `ArrivalToleranceCm`(150cm, 최종 도착용)을 중간 웨이포인트 통과
  판정에도 재사용해서, 좁은 구간의 촘촘한 웨이포인트 여러 개를 한 틱에 통째로 건너뛰던
  버그 → `WaypointPassToleranceCm`(30cm)으로 분리.
- **웨이포인트마다 감속되던 버그(2026-08-04, 이번 라운드 최대 발견)**: 도착 감속 램프가
  최종 목적지뿐 아니라 경로의 모든 중간 웨이포인트에도 걸려서, 웨이포인트에 가까워질
  때마다 속도가 0 근처로 떨어졌다가 다음 웨이포인트로 넘어가며 재가속 — "걷다 서다"를
  반복하는 것처럼 보였음. `MoveToward`에 `bApplyArrivalSlowdown` 플래그 추가,
  `TickNavPathMovement`가 **마지막 웨이포인트일 때만** true로 넘기도록 수정.
- **"한 점으로 뭉침" 버그(근본 원인 찾아서 완전 제거)**: `ResolveAllyOverlapPush`에
  붙여뒀던 "NavMesh 밖으로 밀려나면 되돌리는" 재투영 안전장치가 범인이었음 — 진단 로그
  실측 결과 전체 로그의 68%가 이 보정 발동이었고, 1회 보정량(25~55cm)이 실제 겹침
  푸시(2.6cm/틱)보다 10~20배 커서, 좁은 통로에서 여러 아군을 매 틱 거의 같은 좁은 지점으로
  끌어당기고 있었음 — 완전히 제거.
- **Z축 제외**: 도착/웨이포인트 판정을 `FVector::DistSquared2D`로 바꿔서 지형 높이차와
  무관하게 수평 거리만 비교.
- **죽은 적에게 계속 사격**: `DetectableTargetComponent`가 0.3초 간격으로 BP의 `IsDead`
  변수를 리플렉션 폴링 → 감지되면 `SetIncapacitated(true)`(부수 효과로
  `AllEnemiesEliminated` 트리거도 같이 정상화됨).

### UGV 회피 — 3단 방어 체계
1. **NavMesh 경로 계산 시점**: `UNavModifierComponent`(`UNavArea_UGVBody` 부여,
   `UNavQueryFilter_Infantry`가 이 영역을 100만배 비용으로 취급 — UGV 자신의 경로탐색은
   기본 필터라 영향 없음)로 UGV 발밑을 "웬만하면 피할 땅"으로 등록.
   **결정적 발견(2026-08-04)**: `RecastNavMesh-Default`의 `RuntimeGeneration`이
   `Static`으로 설정돼 있어서, 이 동적 모디파이어가 애초에 실제 경로탐색에 전혀
   반영되지 않고 있었을 가능성이 높음(Static = 런타임 변경 무시) — **`DynamicModifiersOnly`로
   변경**. 장애물 바운즈 소스도 개선: 처음엔 `FailsafeExtent`(엔진 기본 2m 입방체, 실제
   차체보다 훨씬 작음)를 손으로 키워봤지만 액터 원점 기준 대칭 상자라 비대칭 오프셋을
   못 담았음 → `BP_UGV_Vehicle`에 `NavObstacleBox`(큐브, 실측 차체 크기(SK_UGV_v15:
   X242/Y144/Z107) + 여유로 배치, 평소엔 콜리전 꺼짐) 컴포넌트를 새로 추가해서
   `UNavModifierComponent::CalculateBounds()`가 정확한 월드 바운즈를 자동으로 읽어가게
   함. `ScenarioStateSubsystem::AddUGVNavObstacle`/`RemoveUGVNavObstacle`이 이 박스의
   콜리전+`CanEverAffectNavigation`을 토글.
2. **이동 중 실시간(RVO)**: `UGVAvoidanceProxyComponent`가 UGV를 `UAvoidanceManager`에
   손님으로 등록(`AUGVAIController::OnPossess`에서 동적 부착, 항상 켜짐).
   `AvoidanceConsiderationRadius`/`RadiusPaddingCm`로 튜닝. **버그 수정(2026-08-04)**:
   위 `NavObstacleBox`가 콜리전 켜질 때 `GetActorBounds(bOnlyCollidingComponents=true)`
   계산에도 새어 들어가서 RVO 반경이 의도치 않게 커지던 것을 제외 처리(이름으로 걸러냄).
   **테스트용 토글 추가**: `AUGVAIController::bEnableAvoidanceProxy`
   (`BP_UGVAIController` Class Defaults에서 켜고 끌 수 있음, 재빌드 불필요) — NavMesh
   회피만으로 충분한지 검증 중, 아직 결론 안 남.
3. **물리적 안전망(2026-08-04 신규)**: `NavObstacleBox`에 **아군(Pawn)만 물리적으로
   막는 콜리전**을 추가(UGV 자신의 Chaos 차량 물리나 다른 시스템엔 전혀 영향 없음 — Pawn
   채널만 Block, 나머지 Ignore, `SetUGVNavObstacleBoxEnabled`가 매번 코드로 확정 지음) —
   RVO/경로탐색이 어떤 이유로든 실패해도 실제로 뚫고 지나가는 것 자체를 막음.

### 아군끼리 회피
RVO(`bUseRVOAvoidance`, 상태별 on/off) + `ResolveAllyOverlapPush`(물리적 밀어내기, 최종
안전망 — 캡슐 콜리전은 Overlap으로 낮춰둠). 도착 후 밀려나면 `DriftGraceSeconds` 유예 뒤
원위치 복귀.

### UGV 에스코트 속도 제한(2026-08-04 신규 — 예전부터 미해결이던 항목)
"아군과 같이 기동"하는 구간(`StartUGVAdvance` 호출 시점부터 `BeginAllyApproach`가 UGV를
대기 위치로 재출발시키는 시점까지 — 그 이후는 UGV·아군이 각자 다른 곳으로 흩어지므로 제외)
에서만 `AUGVAIController::EscortMaxSpeedKmh`(기본 20km/h)로 제한. 액셀 감소(목표 속도
접근)와 브레이크 증가(초과)를 `EscortSpeedRampBandKmh`(기본 5km/h) 폭 안에서 **하나의
연속된 선형 함수**로 통합 — 처음엔 스로틀/브레이크가 완전히 분리된 두 분기라 급브레이크
느낌이 났는데(사용자 리포트), 목표 속도 지점에서 두 입력이 정확히 0으로 만나도록 고쳐서
부드럽게 수렴함.

---

## 2. 시나리오 스텝 테이블 시스템 (`/Game/Scenario/DT_ScenarioSteps`)

`UI/ScenarioStepTypes.h`(`FScenarioStepRow`, `EScenarioTriggerType`, `EScenarioEffectType`)
+ `UScenarioStateSubsystem`의 매 틱 평가 루프. 트리거 조건/대기시간/효과를 재컴파일 없이
DataTable 값만 수정해서 조정 가능. `PrerequisiteStepId`로 체이닝.

**현재 전체 체인**(2026-08-04 갱신 — 아래 "UAVRecon" 행 트리거 변경 반영):
```
UAVMission(3초 타이머) ──┬─→ UAVArrived(UAV 도착 마커, prereq=UAVMission)
                          │      → RevealEnemies(숨어있던 적 드러남)
                          │
                          └─→ UAVRecon(3초 타이머, UAVMission과 동시 — prereq 없음)
                                 → BeginAllyFormUpAndAdvance(아군 집결 + UGV 출발)
                                   → HaltSignal(UGV-목적지 거리 2000cm 임계)
                                     → RaiseSquadSignal(분대장 정지 수신호)
                                       ├→ EngagementZoomOut(ActorStopped)
                                       │    → UAVEngagementZoomOut(UAV 카메라 줄아웃)
                                       ├→ EnemyEngagementApproach(20초 타이머)
                                       │    → BeginEnemyEngagementApproach(적군 등장)
                                       └→ Approach(7초 타이머)
                                            → BroadcastApproach(아군 산개 + UGV 대기위치 재출발)
                                              ├→ UGVAutoSurveillance(즉시) → UGV RCWS 자동 경계
                                              └→ AmbushTrigger(UGV RCWS 적 감지)
                                                   → BroadcastAmbush(엄폐+사격 참여)
                                                     └→ UGVAutoFire(즉시) → UGV RCWS 자동 사격
                                                          → ScenarioComplete(AllEnemiesEliminated)
                                                            → 완료 토스트
```
**2026-08-04 변경**: "UAVRecon" 행(DataTable 행 이름은 그대로 유지, `HaltSignal`의
`PrerequisiteStepId`가 이 이름을 참조하고 있어서)의 트리거를 `prerequisiteStepId=UAVArrived,
triggerType=UAVEnemyDetected`(UAV가 실제로 적을 발견해야 발동)에서
`prerequisiteStepId=None, triggerType=TimerOnly, triggerDelaySeconds=3`(UAVMission과 동일한
타이머, 즉 **UAV 이륙과 동시**)로 변경 — 사용자 요청: 아군 집결을 "UAV가 적을 발견한 뒤"가
아니라 "UAV 이륙 시점"으로 앞당김. `UAVEnemyDetected` 트리거 타입 자체는 코드에 그대로
남아있고 다른 용도로 재사용 가능(현재 이 체인에서는 안 쓰임 — UAV 자체의 짐벌 자동정찰
상태머신은 이 DataTable과 무관하게 항상 독립적으로 돌아감, 3절 참고).

이번 세션에 추가된 트리거: `UAVArrived`, `UAVEnemyDetected`, `DistanceThreshold`,
`ActorStopped`. 추가된 이펙트: `BeginAllyFormUpAndAdvance`, `SetUGVAutoSurveillance`,
`SetUGVAutoFire`, `BeginEnemyEngagementApproach`.

`AScenarioConfig`(레벨 배치 네이티브 액터, `UGVFormUpDestination`/`UGVStandbyDestination`
`ATargetPoint*` 참조 2개) — `UDataAsset`은 레벨 액터에 대한 하드레퍼런스를 가질 수 없어서
액터로 설계(기존 `AmbushMarker` 패턴과 동일).

---

## 3. UAV

### 짐벌 자동 정찰 상태머신
`Idle → ObservingParachute(낙하산 있으면) → ScanningForEnemies → TrackingEnemies →
WideEngagementView`(외부 트리거로 진입). 각 단계 타임아웃/속도/줌 레벨 전부
`EditAnywhere` 튜닝 가능(`UAVPawn.h` "Camera|Auto Recon" 카테고리).

### WideEngagementView 프레이밍 전면 재작성(2026-08-04)
예전엔 "적/아군 무게중심의 평균 지점 + 고정 줌 레벨"이었음 — 원근 카메라 특성상 가까운
쪽이 화면에 훨씬 크게 보여서, UAV 기준 멀리 있는 아군과 가까이 있는 적군을 동시에
담으려 하면 먼 쪽이 프레임 밖으로 밀려나는 문제가 있었음(사용자 리포트로 발견).
`AUAVPawn::ComputeFramingForPoints` 신규 — 카메라 위치 기준 각 대상(아군+적군 개별
위치)까지의 실제 각도(요/피치)를 구해서, 그 범위를 전부 포함하는 조준 방향과 필요
FOV를 매 틱 계산(세로 화각 요구량을 렌더타겟 종횡비로 가로 화각 기준으로 환산해서 통일).
`GimbalEngagementFramingMarginDegrees`/`MinFOVDegrees`/`MaxFOVDegrees`로 튜닝.
아군 위치는 트리거 시점에 `UScenarioStateSubsystem`이 넘겨줌(UAVPawn은 아군 레지스트리를
모름), 적군 위치는 UAVPawn이 이미 알고 있는 `TargetDetection`/
`DetectableTargetSubsystem` 경로로 매 틱 새로 모음.

### 낙하산 관찰
- GeometryCache가 DCC 절대좌표로 베이크돼서 액터 피벗과 시각적 위치가 다를 수 있음 —
  `GetActorBounds`(피벗 아님) 기준으로 조준.
- **`EnemyEvidence` 팩션 신규**(2026-08-03, `EMilitaryFaction` 3번째 값): 낙하산은
  "적의 흔적"이지 교전 대상이 아니므로 `Friendly`/`Enemy` 어디에도 안 걸림 — RCWS 자동
  조준, UAV 적 중심 계산 등 `Faction == Enemy` 엄격 비교하는 모든 소비처에서 **추가
  필터링 코드 없이** 자동 제외됨(코드베이스 전체가 엄격 동등 비교만 씀, 역방향
  `!= Friendly` 로직이 없어서 가능했던 설계).
- 순항고도 램프(`TickCruising`, `CruiseAltitudeStartZ` → `MissionTargetAltitudeZ`로
  스무스스텝 보간 — 예전엔 목표 고도보다 3m 짧게 정착하던 버그 수정).
- 짐벌 자동정찰 최대 피치(`GimbalReconMaxPitchDegrees`, 기본 -5도) — 자동 정찰 중엔
  절대 수평 위로 안 올라가게 강제.

---

## 4. 적군 AI

### 등장/이동
`EngagePoint`(`ATargetPoint*`, 인스턴스 편집 가능) → `BeginEngagementApproach` 커스텀
이벤트 → `SetMoveTarget` + `StartGroundMove`(BP_Enemy_kadex 자체 로직, C++ 백업 컴포넌트
없음).

### 이동 실패 버그 — 원인 특정, 부분 적용(2026-08-04)
- 증상 로그: `LogCharacterMovement: BP_Enemy_kadex_C_12 is stuck and failed to move! ...
  PenetrationDepth:0.420 Actor:BP_Enemy_kadex_C_15 Component:Gun`.
- **원인**: `Gun`(무기 메쉬) 컴포넌트의 콜리전 프로파일이 `BlockAll`이라 다른 적군
  Pawn까지 물리적으로 막고 있었음. 적군은 아군과 달리 밀어내기 안전망
  (`ResolveAllyOverlapPush` 같은 것)이 전혀 없어서, 두 적군의 총 메쉬가 살짝이라도
  겹치면 영구히 낄 수 있는 구조였음(한두 명만 걸리는 이유 — 특정 스폰/이동 경로에서만
  우연히 겹침).
- **조치**: `BP_Enemy_Base`(부모 블루프린트, `BP_Enemy_kadex`의 상위) 템플릿의 `Gun`
  콜리전을 `Custom` 프로파일로 바꿔 Pawn 채널만 `Ignore`(나머지 채널은 그대로
  `Block`) — **향후 새로 배치되는 적군에는 확실히 적용됨**.
- **미완료**: 이미 배치된 15명 인스턴스는 MCP 편집 툴이 이 배열형 프로퍼티
  (`bodyInstance.collisionResponses.responseArray`)를 인스턴스 단위로 안정적으로 못 써서
  (재현되는 "ArrayRemove: elements changed alongside the size change; removed elements
  are ambiguous" 에러, 7절 참고) 일부만 적용되고 인스턴스마다 상태가 다를 수 있음 —
  에디터에서 각 `BP_Enemy_kadex` 인스턴스의 `Gun` 콜리전 프리셋을 직접 확인해서 Pawn만
  Ignore인지 재확인 필요(또는 Details 패널의 "Reset to Default"로 새 템플릿 값을 제대로
  물어오는지 확인).

---

## 5. UI 알림 시스템 (2026-07-31 완료, 이번 라운드 변경 없음)

`UNotificationSubsystem`(GameInstanceSubsystem) + `WBP_NotificationToast`/
`WBP_ConfirmDialog`. 실제 호출부 3곳: #4-1 진입 메시지, UGV 지정구역 이탈 경고, #4-8(현재는
`ScenarioComplete` 스텝) 전멸 완료 안내. 왼쪽 모니터 전용 위치 고정. 자세한 구조는 이전
버전 스냅샷(git/Perforce 이력 또는 코드 `Source/titan_example/UI/NotificationSubsystem.h`)
참고 — 변경 없어서 여기서는 생략.

---

## 6. 그 외 자잘한 수정들 (2026-08-03~04)

- `Monitor1Widget` 미니맵 트럭 마커 회전이 실제 RCWS 방향과 90도 어긋나던 버그 —
  `TruckMeshForwardOffsetDeg` 보정 추가.
- Unity Build 심볼 충돌(`CallVoidEventByName`이 두 `.cpp` 파일 익명 네임스페이스에
  같은 이름으로 있어서 한 번역 단위로 합쳐질 때 충돌) — `ScenarioStateSubsystem.cpp`
  쪽을 `InvokeEnemyBlueprintEventByName`으로 개명.
- 비-네이티브 UGV(`BP_UGV_Vehicle`, 순수 BP 기반이라 `AUGVPawn` 아님) 호환 —
  `ResolveUGVPawn` 헬퍼(`AUGVPawn` 우선 시도, 없으면
  `Atitan_examplePlayerController::FindUGVFromTankInstance` 폴백) 여러 곳에 적용.

---

## 7. MCP 편집 툴 사용 시 알려진 함정 (다음 세션 필독)

이번 라운드에 레벨/블루프린트를 MCP(`unreal-mcp`)로 대량 편집하면서 반복적으로 겪은
문제들 — 다음에 비슷한 작업을 자동화할 때 미리 대비할 것.

- **Vector/구조체 프로퍼티는 필드 하나씩 분리해서 호출**: `set_properties`에
  `{"x":.., "y":.., "z":..}`처럼 다중 필드를 한 번에 보내면 첫 필드만(또는 일부만)
  적용되고 나머지가 조용히 드롭될 수 있음(호출 자체는 `true` 반환). 반드시 필드별로
  나눠서 호출하고 `get_properties`로 재검증할 것.
- **배열 프로퍼티(`collisionResponses.responseArray` 등)는 "덮어쓰기"가 아니라
  현재 값과의 "디프"처럼 동작하는 것으로 보임**: 큰 배열을 한 번에 통째로 갈아끼우려
  하면 애매한 경우 `"ArrayRemove: elements changed alongside the size change; removed
  elements are ambiguous"` 에러를 던지거나, 일부 항목만 반영되거나, 완전히 무시될 수
  있음. **클래스 템플릿(Blueprint CDO) 대상 호출은 대체로 안정적으로 반영됨** —
  문제는 거의 항상 **레벨에 이미 배치된 인스턴스**를 대상으로 할 때 발생.
- **Blueprint 클래스에 새 컴포넌트를 추가해도(`ActorTools.add_component` +
  `set_properties` + `compile_blueprint`) 이미 레벨에 배치된 기존 인스턴스는 새
  컴포넌트의 기본값을 자동으로 안 물려받음** — 크기/위치/콜리전 등을 인스턴스에도
  별도로 다시 써줘야 실제로 반영됨.
- **결론/권장**: 물리적으로 중요한 콜리전 설정(특히 배열형 응답 채널)은 에디터
  프로퍼티 값에만 의존하지 말고, 가능하면 **C++ 코드가 런타임(BeginPlay/상태 토글
  시점)에 명시적으로 강제**하는 편이 훨씬 안전함 — 예: `SetUGVNavObstacleBoxEnabled`가
  토글 시마다 `SetCollisionResponseToAllChannels`/`SetCollisionResponseToChannel`을
  직접 호출해서 에디터 저장 상태와 무관하게 항상 올바른 상태를 보장하도록 만든 것이
  이 패턴의 실제 적용 사례.
- 여러 액터에 같은 편집을 반복 적용할 땐 `ProgrammaticToolset.execute_tool_script`로
  파이썬 스크립트를 짜서 한 번에 처리하는 게 왕복 횟수를 크게 줄여줌 — 단, 위 필드
  분리/배열 함정은 스크립트 안에서도 그대로 적용됨.

---

## 8. 남은 이슈 / 다음 확인 순서

1. **적군 15명 중 이미 배치된 인스턴스의 `Gun` 콜리전 수동 재확인**(4절) — 템플릿은
   고쳐졌지만 인스턴스 전체가 확실히 반영됐는지 에디터에서 직접 확인 필요.
2. **`UGVAvoidanceProxyComponent`(RVO) 끄고 NavMesh만으로 충분한지 최종 판정** —
   `BP_UGVAIController`의 `bEnableAvoidanceProxy`로 테스트 중, 특히 **Following
   구간**(매 틱 NavMesh 쿼리를 안 해서 RVO에 전적으로 의존하던 구간)을 우선 확인할 것.
3. #4-7 UGV 위협사격 이펙트 + 적 피격 반응 애니메이션 — BP_Enemy 쪽 라이브 확인 필요
   (이전 스냅샷에서 이월, 아직 미착수). 5명 도주는 스킵 확정.
4. #4-8 자체방호 RCWS 전환 — 스킵 확정(실제 시나리오 미정).
5. 시나리오 자동 재시작(#4-8 종료 후 10초) — 우선순위 낮음, 미착수(이전 스냅샷에서 이월).
