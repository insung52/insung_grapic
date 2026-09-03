# 3단계 전투 시나리오 — 구현 현황 / 설계 (2026-08-23)

저작/세팅 실무 가이드: `scenario_authoring_guide.md`
요구사항 원본: `C:\working\insung_grapic\titan\newlevel\scenario.md`
(1차 전투지 = UGV 단독 교전 → 도주 → 2차 = UGV+아군 → 도주 → 3차 = 이동형지휘소 RCWS)

이 문서는 "문서의 각 흐름이 지금 코드/데이터의 무엇으로 구현돼 있는가"와 "무엇이 아직 없는가"를
한 곳에 모아둔 것. 관련 코드는 전부 `Source/titan_example/UI/ScenarioStepTypes.h`,
`UI/ScenarioStateSubsystem.*`, `Soldiers/EnemyCombatComponent.*`, `UI/ScenarioConfig.h`.

> ⚠️ **[2026-09-01] UAV 관련 부분은 아래 본문이 옛날 얘기다.** 구 `AUAVPawn`/`BP_UAV`가 새
> 물리 드론 `ADronePawn`으로 대체되면서 트리거/이펙트/DT 행이 바뀌었다. 최신 내용은
> `vehicle/drone/drone_flight_dev_guide.md` 13절(에버그린) 참고. 요약:
>
> - **목적지가 `EnemyCube` 태그 액터 → `ADroneFlightPath` 스플라인**(행의 `UAVPathId`,
>   현재 `uavpath`)으로 바뀜. 아래 §"시나리오 시작 좌표 = UAV 목적지" 항목은 폐기.
> - **`UAVSpotted` 트리거가 `UAVEnemyDetected` → `UAVParachuteObserved`**. 행 설명("UAV가
>   낙하산 발견")과 실제 판정이 달랐던 걸 바로잡은 것 — 이 불일치 때문에 드론이 낙하산을
>   찾아도 UGV가 출발하지 않는 버그가 있었다.
> - `UAVDetectionOff` 행은 **`bEnabled=false`로 내려감** — 드론의 단계별 탐지
>   (아군만 → +낙하산 → +적군)가 그 역할을 대신한다.
> - 행 **2개 신설**: `DroneSeeEnemies`(선행 `UGVSurveillance`, 트리거 `EnemyDetected`,
>   이펙트 `EnableDroneEnemyDetection`), `DroneWideView`(선행 `DroneSeeEnemies`, 2초,
>   이펙트 `UAVEngagementZoomOut`).
> - `UAVPawn.ParachuteActor` → **`BP_Drone` 인스턴스의 `ParachuteActor`**(레벨에 직접 배치된
>   낙하산 액터를 꽂아야 함. 비어 있으면 정찰이 시작되지 않는다).
> - 이펙트 `MoveDroneToPath` 신설 — 2·3차 전투지로 도주하는 적을 드론이 따라가는 용도.
>   코드는 준비됐고 스플라인 추가만 남음.

---

## 1. 시스템 구조 요약

| 축 | 담당 |
|---|---|
| **언제 무엇이 발동하는가** | `DT_ScenarioSteps` 계열 DataTable (한 행 = 스텝: Prerequisite + Trigger + Effect) |
| **어디로/무엇을** (레벨 액터 참조) | `AScenarioConfig` 액터 (레벨에 1개 배치) |
| **어떻게 보이는가** (속도/자세/간격 등 튜닝값) | 각 컴포넌트의 EditAnywhere 프로퍼티 / ABP |
| **스텝 평가 시작** | 콘솔 `BeginScenarioEnemyContact` → `UScenarioStateSubsystem::BeginScenarioSteps()` |

`ScenarioStepTable`은 GameInstanceSubsystem 프로퍼티라 레벨마다 바꿀 수단이 없었는데,
2026-08 Part G에서 `AScenarioConfig::ScenarioStepTable`을 추가해서 **레벨이 자기 테이블을 지정**
할 수 있게 함(비워두면 생성자 기본값 `/Game/Scenario/DT_ScenarioSteps` 사용).

---

## 2. 문서 흐름 ↔ 구현 매핑

| # | scenario.md | 트리거 | 이펙트 | 상태 |
|---|---|---|---|---|
| 1 | 시나리오 시작(명령어) | — | — | 콘솔 `BeginScenarioEnemyContact` (EnemyCube 태그 액터 위치를 "수신 좌표"로 저장 + 스텝 평가 시작) |
| 2 | UAV 목표지점 이동 | `TimerOnly` | `BeginUAVMission` | ✅ |
| 3 | UAV가 낙하산 발견 → UGV 자율주행 시작 | `UAVEnemyDetected` | `MoveUGVToZone1Destination` | ✅ (Part G에서 이펙트 신설 — 아군 집결 없이 UGV만 출발) |
| 4 | 이후 UAV 적 감지 비활성 | `TimerOnly` | `DisableUAVTargetDetection` | ✅ (Part G, TargetDetection 틱만 끔) |
| 5 | 적군 1차 전투지로 경계 이동(저속·총내림·숙임·둘러보기) | `TimerOnly` | `BeginEnemyEngagementApproach` | ✅ Part C + Part G(교전 전엔 감지/사격 OFF) |
| 6 | UGV 객체탐지 → 통제기 전달 | — | — | ✅ 기구현(프로토콜) |
| 7 | 통제기가 원격 조준/사격 | `EnemyDetected` | `SetUGVAutoSurveillance` / `SetUGVAutoFire` | ✅ (통제기 SW 수령 전까지 UGV 자체 자동사격으로 대체) |
| 8 | **UGV RCWS가 근거리에서 최초 사격 → 적군이 뛰어서 엄폐 + 대응사격** | `UGVFiredNearEnemy` | `BeginEnemyEngage` | ✅ Part G 신설 |
| 9 | 적 3명 사망 → 2차 전투지 도주 | `EnemyCasualtyCountAtLeast(3)` | `BeginEnemyFleeZone2` | ✅ Part D+F |
| 10 | UGV-적 거리 벌어지면 UGV 2차 목적지로 이동(사격 유지) | `LeaderDistanceFromEnemyAtLeast` | `MoveUGVToZone2Destination` | ✅ Part F(트리거)+G(이펙트) |
| 11 | 2차 전투지에서 아군이 적 발견 시 사격 | `TimerOnly` 등 | `BroadcastAmbush` | ✅ 기구현(아군 매복/사격) |
| 12 | **아군 사격 시작 → 적군 타겟을 아군으로 전환** | `AllyFireStarted` | `RetargetEnemiesToAllies` | ✅ Part G(트리거)+F(이펙트) |
| 13 | 적 7명 사망(누적) → 3차 전투지 도주 | `EnemyCasualtyCountAtLeast(7)` | `BeginEnemyFleeZone3` | ✅ Part D+F |
| 14 | 지휘소 RCWS 사격 → 적군이 지휘소 타겟 | `CommandPostFiredNearEnemy` | `SetCommandPostAutoFire` / `RetargetEnemiesToCommandPost` | ✅ 코드 완료, **레벨에 이동형지휘소 액터 필요** |

부수 요구사항:
- 도주 중 고개 돌려 사격 → ✅ `TickFlee`(이동방향과 무관하게 조준/단발 사격)
- 타겟과 멀어지면 굳이 안 쏨 → ✅ 감지 스피어 밖이면 타겟 해제
- 이동 중 사망 시 관성 반영 → ✅ Part A(PhysicalAnimation 액티브 랙돌)
- 이동 중 피격 비틀거림 → ❌ 미구현(애니메이션 작업 필요)
- 도주 중 엄폐물에 기대고 정찰 → 보류(문서에서도 보류)

---

## 3. 이번에 추가된 것 (Part F / Part G)

### 트리거 (`EScenarioTriggerType`)
- `EnemyCasualtyCountAtLeast` — 누적 사망자 수 ≥ `TriggerCountThreshold`(새 int32 필드).
  기준 적 수는 스텝 시작 시점 값이되 **관측된 최대값으로 자동 상향**(낙하산 강하처럼 늦게
  스폰되는 연출 대비). 임계값 0은 "0명 이상"이라 즉시 발동하니 주의.
- `LeaderDistanceFromEnemyAtLeast` — UGV와 **최근접 살아있는 적** 거리가 임계값 이상.
  적이 0명이면 발동 안 함.
- `UGVFiredNearEnemy` / `CommandPostFiredNearEnemy` — RCWS 누적 발사 카운트
  (`URCWSFireControlComponent::GetShotsFiredCount()`)가 증가한 그 틱의 최근접 적 거리를 기록해두고,
  행의 `TriggerDistanceThreshold`와 비교. "멀리서 쏜 뒤 나중에 가까워진 것"으로는 발동 안 함.
- `AllyFireStarted` — 등록된 아군 전원의 `GetFireTriggerCount()` 합이 시나리오 시작 시점보다 증가.

### 이펙트 (`EScenarioEffectType`)
- `BeginEnemyEngage` — 적 전원 `BeginEngageAtCurrentZone()`
- `BeginEnemyFleeZone2` / `BeginEnemyFleeZone3` — 적 전원 `BeginFlee(1)` / `BeginFlee(2)`
- `RetargetEnemiesToAllies` / `RetargetEnemiesToCommandPost` — 적 전원 `ForceRetarget()`
  (**두 값의 동작은 동일** — 이름은 DataTable 가독성용)
- `MoveUGVToZone1/2/3Destination` — `AScenarioConfig`의 목적지로 `AUGVAIController::MoveToDestination`
  (1차는 기존 `UGVFormUpDestination` 재사용). 호출 시 `FormUpLeader`도 채워서 이후 거리/감지
  트리거가 UGV 기준으로 동작하게 함.
- `SetCommandPostAutoFire`, `DisableUAVTargetDetection`

### 컴포넌트 API
- `UEnemyCombatComponent::BeginEngageAtCurrentZone()` / `IsEngaged()` / `EngageRushSpeed`(기본 400)
  - **핵심 변경**: `BeginMove(0)`(1차 전투지 접근)은 이제 `bEngaged=false`로 시작 →
    감지 스피어 OFF → `TryAcquireTargetFromOverlaps()`가 아예 후보를 안 잡음 → **적군이 안 쏨**.
    `BeginEngageAtCurrentZone()`이 호출돼야 총을 들고(IsHoldingWeapon?), 둘러보기를 멈추고,
    남은 거리를 `EngageRushSpeed`로 뛰어서 붙으며 사격을 시작함.
    (예전엔 `BeginMove`가 무조건 감지를 켜서 접근 단계부터 교전이 벌어졌음.)
- `UAllyFormationComponent::GetFireTriggerCount()` — 사격 버스트 트리거 누적 횟수
- `URCWSFireControlComponent::GetShotsFiredCount()` — 발사 누적 카운트
- `AScenarioConfig`: `UGVZone2Destination` / `UGVZone3Destination` / `CommandPost` / `ScenarioStepTable`

---

## 4. 새 스텝 테이블 구성안 (`DT_ScenarioSteps_ThreeStage`)

거리/시간 값은 kadex_test 기준 예시 — 새 레벨에서는 재튜닝 필요.

| RowName | Prereq | Trigger | 값 | Effect |
|---|---|---|---|---|
| `UAVMission` | (없음) | TimerOnly | 3s | BeginUAVMission |
| `EnemyApproach` | (없음) | TimerOnly | 1s | BeginEnemyEngagementApproach |
| `UAVSpotted` | UAVMission | UAVEnemyDetected | — | MoveUGVToZone1Destination |
| `UAVDetectionOff` | UAVSpotted | TimerOnly | 2s | DisableUAVTargetDetection |
| `UGVSurveillance` | UAVSpotted | TimerOnly | 0s | SetUGVAutoSurveillance |
| `UGVAutoFire` | UGVSurveillance | EnemyDetected | — | SetUGVAutoFire |
| `EnemyEngage` | (없음) | **UGVFiredNearEnemy** | 6000 | BeginEnemyEngage |
| `EnemyFleeToZone2` | (없음) | EnemyCasualtyCountAtLeast | 3 | BeginEnemyFleeZone2 |
| `UGVMoveZone2` | EnemyFleeToZone2 | LeaderDistanceFromEnemyAtLeast | 5500 | MoveUGVToZone2Destination |
| `AllyAmbush` | EnemyFleeToZone2 | TimerOnly | 5s | BroadcastAmbush |
| `RetargetToAllies` | EnemyFleeToZone2 | **AllyFireStarted** | — | RetargetEnemiesToAllies |
| `EnemyFleeToZone3` | EnemyFleeToZone2 | EnemyCasualtyCountAtLeast | 7 | BeginEnemyFleeZone3 |
| `UGVMoveZone3` | EnemyFleeToZone3 | LeaderDistanceFromEnemyAtLeast | 7200 | MoveUGVToZone3Destination |
| `CommandPostFire` | EnemyFleeToZone3 | TimerOnly | 3s | SetCommandPostAutoFire |
| `RetargetToCommandPost` | EnemyFleeToZone3 | **CommandPostFiredNearEnemy** | 8000 | RetargetEnemiesToCommandPost |
| `ScenarioComplete` | EnemyEngage | AllEnemiesEliminated | — | ShowUIMessage |

> 기존 `DT_ScenarioSteps`는 이전 레벨 흐름(아군 집결 → UGV 호위 → 산개 → 매복) 전제라
> 새 시나리오와 스텝 구성이 다름 — 위 테이블은 **별도 에셋**으로 만들고
> `AScenarioConfig::ScenarioStepTable`로 지정하는 걸 전제로 함.

---

## 5. kadex_test 테스트 세팅 현황

- 적 4개체(`BP_Enemy_kadex_C_6/8/9/10`): `CombatZones` 3개 zone 연결 완료
  - zone0 x≈6340 / zone1(2차) x=7940 / zone2(3차) x=9540, Y 레인은 개체별 유지, 마커 z=128
  - ⚠️ zone0은 **라벨과 필드가 엇갈려 있음**(`_Zone1_Cover` 라벨이 FiringPose에 연결).
    동작엔 문제 없음(실제 이동 목적지는 CoverPose). 새로 만든 zone2/3은 라벨=필드로 맞춤.
- `bAutoBeginMoveForTesting`(적 4) / `bAutoBeginAmbushForTesting`(아군 9) **전부 OFF** —
  이제 PIE를 켜도 양측이 스스로 교전하지 않고 스텝 테이블이 흐름을 쥠.
- `TP_UGV_Zone1/2/3_Destination` (x=3800 / 5400 / 7000, y=2400) 배치
- `ScenarioConfig` 액터 1개 배치 + 전 필드 연결:
  UGVFormUpDestination/UGVZone2Destination/UGVZone3Destination = 위 3개,
  CommandPost = `BP_TitanTruck1`(RCWS 달린 차량, 이동형지휘소 대역),
  ScenarioStepTable = `/Game/Scenario/DT_ScenarioSteps_ThreeStage`
- `DT_ScenarioSteps_ThreeStage` 생성 완료(4절 표 + RevealEnemies 행 = 17행)
- **PIE 확인(2026-08-23)**: 22초 방치 시 적/아군 전원 `HasTarget=false`, 이동/사격 없음 —
  "PIE 켜자마자 교전" 문제 해소됨. 스텝 평가는 콘솔 `BeginScenarioEnemyContact`로 시작해야 함
  (MCP엔 콘솔 명령 툴이 없어 자동 검증 불가).
- 한계: 아군/지휘소가 적 전투지에서 매우 멀어서 **전술적 그림은 안 맞음**
  (감지 스피어가 양측 20000이라 스텝은 순서대로 다 발동하지만, 2·3차의 타겟 전환은 의미가 없음).
  실제 지오메트리 검증은 새 레벨에서.

---

## 6. 남은 작업

1. **PIE에서 전체 흐름 1회 통과 확인** — 콘솔 `BeginScenarioEnemyContact` 입력 후
   로그의 `[ScenarioStateSubsystem] 시나리오 스텝 발동:` 줄로 17행이 순서대로 켜지는지.
   적 사망 3명/7명은 UGV RCWS 자동사격이 만들어줘야 하므로, 안 죽으면 UGV 1차 목적지를
   더 가까이 당기거나 `EnemyEngage` 행의 임계값(6000)을 조정.
2. 새 레벨: 지오메트리에 맞춰 전투지 마커 3쌍/UGV 목적지 3개/이동형지휘소 배치 후
   `ScenarioConfig` 연결 + 거리 임계값 재튜닝(5500/7200/6000/8000은 kadex_test 기준).
3. `Content/Scenario/DT_ScenarioSteps.uasset`이 read-only(P4 미체크아웃)라 기존 테이블에 넣어둔
   Part F 4행이 저장되지 않은 상태 — 새 테이블로 가므로 그대로 버려도 됨.
4. 피격 비틀거림 애니메이션(문서 요구, 미구현).
5. 낙하산 하강 잔재로 사격 순간 총구가 반대로 보이는 문제 — 실제 페이싱에서 재확인 필요.
   여전하면 착지 후 최소 유예시간 게이트를 `EnemyCombatComponent`에 추가하는 방향.
6. 스텝 평가 시작을 콘솔 대신 자동으로 하고 싶으면 `AScenarioConfig`에
   "레벨 시작 N초 후 자동 시작" 옵션을 하나 추가하는 게 가장 간단(현재는 콘솔 전용).


---

## 7. 레벨에 배치/연결하는 것 (마커 인벤토리)

"어디로/무엇을"에 해당하는 값은 전부 **레벨 액터 참조**로 잡는다(에셋에 하드코딩 없음).

| 무엇 | 어디서 지정 | 개수 | 설명 |
|---|---|---|---|
| **시나리오 시작 좌표 = UAV 목적지** | 레벨의 아무 액터에 **Tag `EnemyCube`** | 1 | `BeginScenarioEnemyContact`가 이 액터 위치를 "수신한 적 예상 좌표"로 저장하고, `BeginUAVMission`이 UAV를 **이 좌표로** 보냄. UAV 도착 지점을 옮기려면 이 액터를 옮기면 됨(kadex_test: `enemys` TargetPoint) |
| **UGV 1차 목적지** | `ScenarioConfig.UGVFormUpDestination` | 1 | `MoveUGVToZone1Destination`이 사용 |
| **UGV 2차 / 3차 목적지** | `ScenarioConfig.UGVZone2Destination` / `UGVZone3Destination` | 각 1 | `MoveUGVToZone2/3Destination` |
| UGV 대기 위치(구 흐름) | `ScenarioConfig.UGVStandbyDestination` | 0~1 | 예전 아군 산개 흐름 전용. 새 시나리오에선 비워둬도 됨 |
| **이동형지휘소** | `ScenarioConfig.CommandPost` | 1 | 그 액터의 `RCWSFireControlComponent`를 지휘소 트리거/이펙트가 사용 |
| **스텝 테이블** | `ScenarioConfig.ScenarioStepTable` | 1 | 비우면 기본 `/Game/Scenario/DT_ScenarioSteps` |
| **적군 전투지 마커** | 적 개체마다 `EnemyCombatComponent.CombatZones[0..2]` | **개체당 6개** | zone당 `FiringPose.Marker`(노출·사격 위치) + `CoverPose.Marker`(엄폐 위치 = **그 zone으로의 이동/도주 목적지**). `[0]`=1차, `[1]`=2차, `[2]`=3차 |
| 적군 자세 | 각 포즈의 `BodyPose`(Standing/Crouched/Prone), `Lean`(None/Left/Right) | 포즈마다 | 마커 위치에서 취할 자세 |
| **아군 매복 지점** | 아군 개체마다 `AllyFormationComponent.AmbushMarker` | 개체당 1 | 매복 명령 시 이동할 지점 |
| **아군 사격/엄폐 자세** | `FiringPose` / `CoverPose` / `NoTargetPose` (각 Marker+BodyPose+Lean) | 개체당 3 | 아군은 zone 개념이 없고 1세트 |
| 아군 분대 구성 | `bIsSquadLeader`, `SquadId`, `DefaultWatchYawDeg` | 개체마다 | 분대장은 수신호 몽타주(`DeploySignalMontage`/`TakeCoverSignalMontage`)도 지정 |
| **감지 반경** | 적: `AllyDetectRange` / 아군: `EnemyDetectRange` 스피어 컴포넌트의 `SphereRadius` | 개체마다 | kadex_test 기준 **20000(200m)** — "언제 서로를 인지하는가"가 이 값에 좌우됨 |
| UAV 자동정찰 관측 대상 | `UAVPawn.ParachuteActor` | 1 | 낙하산 관측 연출용 |
| 알림 문구 | `DT_NotificationWidgets`의 RowName ↔ 스텝 행의 `NotificationKind` | — | `ShowUIMessage` 이펙트 전용 |

## 8. 스텝 테이블 행 필드 (DataTable에서 직접 편집)

한 행 = 스텝 하나. **어떤 트리거가 어떤 값을 읽는지**가 중요:

| 필드 | 읽는 트리거/이펙트 | 비고 |
|---|---|---|
| `PrerequisiteStepId` | 전부 | 이 스텝이 발동된 뒤부터 평가 시작. 비우면 시나리오 시작 즉시. 같은 Prereq를 여러 행이 참조하면 병렬 진행 |
| `TriggerDelaySeconds` | `TimerOnly` | Prereq 발동 시각 기준 경과 시간 |
| `TriggerDistanceThreshold` | `DistanceThreshold`(이하), `LeaderDistanceFromEnemyAtLeast`(이상), `UGVFiredNearEnemy` / `CommandPostFiredNearEnemy`(이 거리 이내에서 쐈는가) | cm 단위 |
| `TriggerCountThreshold` | `EnemyCasualtyCountAtLeast` | **적군 몇 명 사망 시 다음 전투지로 도주하는가** (현재 3 / 7). 0은 즉시 발동이니 1 이상 |
| `EffectType` | — | 발동 시 실행할 동작 |
| `NotificationKind` | `ShowUIMessage` | 다른 이펙트에선 무시 |
| `bEnabled` | 전부 | **스텝 on/off 스위치**. 끄면 그 스텝은 영원히 안 켜지고, **이 스텝을 Prereq로 삼은 뒤 스텝들도 영원히 대기**(의도된 동작 — 흐름을 여기서 끊고 싶을 때) |

트리거 종류: `Manual`(코드/콘솔 전용), `TimerOnly`, `DistanceThreshold`, `ActorStopped`, `UAVArrived`,
`EnemyDetected`(UGV RCWS가 적 포착), `UAVEnemyDetected`, `AllEnemiesEliminated`,
`EnemyCasualtyCountAtLeast`, `LeaderDistanceFromEnemyAtLeast`, `UGVFiredNearEnemy`,
`CommandPostFiredNearEnemy`, `AllyFireStarted`.

## 9. 컴포넌트 튜닝값 (행동이 "어떻게 보이는가")

### 적군 `EnemyCombatComponent`
| 값 | 기본 | 의미 |
|---|---|---|
| `PatrolMoveSpeed` | 150 | 1차 전투지 **경계 이동** 속도(총 내림/숙임) |
| `EngageRushSpeed` | 400 | 교전 돌입 후 엄폐지점까지 **뛰는** 속도 |
| `MoveSpeed` | 300 | 그 외 전투지 이동 속도 |
| `FleeMoveSpeed` | 400 | 도주 속도 |
| `Min/MaxFleeCommitDelaySeconds` | 0.5 / 3 | 도주 명령 후 개체별 랜덤 지연(한두 명씩 순차 도주) |
| `Min/MaxLookAroundIntervalSeconds`, `LookAroundDurationSeconds` | 4~8 / 2 | 경계 이동 중 둘러보기 주기·길이 |
| `Min/MaxFiringPoseSeconds`, `Min/MaxCoverPoseSeconds` | 2~4 | 사격/엄폐 자세 유지 시간 |
| `Min/MaxSingleShotIntervalSeconds` | 1.5~3 | 이동·도주 중 단발 견제사격 간격 |
| `Min/MaxFireIntervalSeconds` | 2.5~5 | 엄폐 사이클 버스트 간격 |
| `FiringAimToleranceDeg` | 5 | 이 각도 안으로 정렬돼야 발사 |
| `PoseMoveSpeed` / `PoseArrivalToleranceCm` | 300 / 10 | 엄폐↔사격 자세 전환 이동 |
| `bAutoBeginMoveForTesting` | false | 켜면 시나리오와 무관하게 BeginPlay에서 1차 전투지로 출발(테스트용) |

### 아군 `AllyFormationComponent`
`ApproachMoveSpeed`(300) / `FollowMoveSpeed`(600) / `FormUpMoveSpeed`(600),
`Min/MaxFireIntervalSeconds`(2.5~5), `Min/MaxTargetReactionSeconds`(0.2~0.6, 타겟 인지 후 반응 지연),
`FireLaneAllyMarginCm`(60, 아군이 사선에 있으면 발사 보류), 자세 사이클 값들(적군과 동일 구성),
`bAutoBeginAmbushForTesting`(false).

### UGV RCWS `RCWSFireControlComponent`
`MaxAutoAimSlewRateDegPerSec`(45), `AutoAimLockToleranceDegrees`(1),
`AutoFireTurretAlignmentToleranceDeg`(2), `LockOnGaugeChargeSeconds`(1),
`BarrelSpinUpSeconds`(2, 자동사격 시작까지의 예열), `FireRateRPM`(1200), `BurstRoundCount`(3),
`MaxEffectiveRangeMeters`(2000), `SearchSweep*`(대상 없을 때 탐색 스윕).

### UAV `UAVPawn`
`AscendDurationSeconds`(5) / `AscendHeightMeters`(20) / `CruiseSpeedKmh`(60),
`GimbalGuaranteedFindDelaySeconds`(5, 도착 후 적 발견까지 보장 시간 — 3번 스텝 타이밍에 직결),
`GimbalScan*`(정찰 스윕), `ParachuteObserveDurationSeconds`(5).

### 시나리오 서브시스템 `UScenarioStateSubsystem`
`ScenarioStepTickInterval`(0.2, 스텝 평가 주기), `SquadSignalFallbackSeconds`,
`FormUpAdvanceDelaySeconds`, `FormUpStaggerSeconds`, `NavObstacleSettleSeconds`.

## 10. "UGV RCWS 자동사격 전환"을 끄고 싶을 때

`BeginScenarioEnemyContact` 이후 RCWS 모드가 바뀌는 건 **스텝 테이블 두 행** 때문이다
(코드가 강제하는 게 아님):

- `UGVSurveillance` → `SetUGVAutoSurveillance` (자동 경계/탐색 스윕)
- `UGVAutoFire` → `SetUGVAutoFire` (자동 조준 + 자동 발사)

**끄는 법**: `DT_ScenarioSteps_ThreeStage`에서 두 행의 `bEnabled`를 해제.
단, `EnemyEngage` 행이 `UGVAutoFire`를 Prerequisite로 삼고 있으므로 그대로 두면 1차 교전이
영원히 시작되지 않는다 → `EnemyEngage`의 `PrerequisiteStepId`를 `UAVSpotted`(또는 비움)로 바꿀 것.

**중요**: `UGVFiredNearEnemy` 트리거가 보는 `ShotsFiredCount`는 자동/수동을 구분하지 않는다
(`bWantsToFire = bWantsAutoFire || bWantsManualFire`). 즉 자동사격을 꺼두고 **조작자가 직접
쏴도 적군 교전 돌입 트리거는 정상 발동**한다 — scenario.md의 "통제기 SW가 원격으로 조준·사격"
흐름에 오히려 더 가깝다.
