# 시나리오 저작 가이드 — DataTable 구조 · 레벨 세팅 (2026-08-23)

새 레벨에서 3단계 전투 시나리오(또는 그 변형)를 **코드 수정 없이** 굴리기 위해
"무엇을 어디에 채워야 하는가"만 모은 실무용 문서.

- 요구사항 원본: `C:\working\insung_grapic\titan\newlevel\scenario.md`
- 구현 현황/설계 배경: `scenario_three_stage_combat.md` (이 문서와 짝)
- 관련 코드: `Source/titan_example/UI/ScenarioStepTypes.h`, `UI/ScenarioStateSubsystem.*`,
  `UI/ScenarioConfig.h`, `Soldiers/EnemyCombatComponent.*`, `Soldiers/AllyFormationComponent.*`

---

## 1. 전체 구조 — 값이 사는 세 곳

| 축 | 담당 | 어디서 편집 |
|---|---|---|
| **언제 무엇이 발동하는가** | 스텝 DataTable (한 행 = 스텝) | 콘텐츠 브라우저의 DataTable 에셋 |
| **어디로 / 무엇을** (레벨 액터 참조) | `ScenarioConfig` 액터 + 각 개체의 마커 | 레벨 뷰포트 + 디테일 패널 |
| **어떻게 보이는가** (속도·간격·자세) | 컴포넌트 EditAnywhere 프로퍼티 | 개체 디테일 패널 (또는 BP 기본값) |

**시나리오 시작**: PIE에서 `` ` `` → `BeginScenarioEnemyContact`
→ `EnemyCube` 태그 액터 위치를 "수신한 적 예상 좌표"로 저장 + **스텝 평가 시작**.
(이 명령을 치기 전에는 테이블의 어떤 행도 평가되지 않는다.)

평가 주기는 `UScenarioStateSubsystem::ScenarioStepTickInterval`(기본 0.2초).
한 번 발동한 스텝은 다시 발동하지 않는다(레벨 재시작 전까지).

---

## 2. DataTable 완전 설명

### 2.1 에셋 만들기와 연결

1. 콘텐츠 브라우저 → 우클릭 → **Miscellaneous ▸ Data Table**
2. Row Structure에 **`ScenarioStepRow`** 선택
3. 만든 에셋을 레벨의 **`ScenarioConfig` 액터 ▸ `Scenario|Steps` ▸ `ScenarioStepTable`** 에 연결
   - 비워두면 서브시스템 생성자 기본값 `/Game/Scenario/DT_ScenarioSteps`가 쓰인다.
   - 레벨마다 다른 테이블을 쓰려면 반드시 이 필드로 지정할 것(서브시스템은 GameInstance 단위라
     에디터에서 레벨별로 직접 지정할 방법이 이것뿐).
4. 행 추가: 테이블 에디터 상단 **Add** → 행 이름(RowName)이 곧 스텝 ID. 다른 행이
   `PrerequisiteStepId`로 이 이름을 참조한다. **이름을 바꾸면 참조도 같이 고칠 것.**

현재 3단계 시나리오용 테이블: `/Game/Scenario/DT_ScenarioSteps_ThreeStage` (17행, 4절 참고)

### 2.2 행 필드 레퍼런스

| 필드 | 타입 | 설명 |
|---|---|---|
| **RowName** | (행 이름) | 스텝 ID. `PrerequisiteStepId`가 가리키는 대상 |
| `DebugLabel` | Text | 사람이 읽는 설명. 로그에 같이 찍힘 — "무슨 스텝인지" 적어두면 디버깅이 쉬움 |
| `PrerequisiteStepId` | Name | **이 스텝이 발동된 뒤부터** 평가 시작. 비우면(None) 시나리오 시작 즉시부터 평가. 타이머의 기준 시각도 이 스텝의 발동 시각 |
| `TriggerType` | Enum | 발동 조건 종류 (2.3 참고) |
| `TriggerDelaySeconds` | float | `TimerOnly` 전용 — 기준 시각으로부터 경과 시간(초) |
| `TriggerDistanceThreshold` | float | 거리 조건(cm). 트리거마다 "이하/이상" 의미가 다름 (2.3) |
| `TriggerCountThreshold` | int32 | `EnemyCasualtyCountAtLeast` 전용 — **몇 명 사망 시**. 0이면 "0명 이상"이라 즉시 발동하니 반드시 1 이상 |
| `EffectType` | Enum | 발동 시 실행할 동작 (2.4 참고) |
| `NotificationKind` | Name | `ShowUIMessage` 전용 — `DT_NotificationWidgets`의 RowName |
| `bEnabled` | bool | 스텝 on/off. **끄면 이 스텝은 영원히 안 켜지고, 이 스텝을 Prereq로 삼은 뒤 스텝들도 전부 대기 상태로 멈춘다**(의도된 동작 — 흐름을 여기서 끊고 싶을 때 사용) |

### 2.3 트리거 레퍼런스

| TriggerType | 언제 참이 되나 | 읽는 필드 | 레벨에 필요한 것 |
|---|---|---|---|
| `Manual` | 자동으로는 절대 안 켜짐. `UScenarioStateSubsystem::FireScenarioStep(StepId)` 호출로만 (BlueprintCallable — 콘솔 직접 호출은 불가, BP에서 호출) | — | — |
| `TimerOnly` | 기준 시각 + `TriggerDelaySeconds` 경과 | Delay | — |
| `DistanceThreshold` | UGV ↔ **현재 목적지** 거리가 임계값 **이하** | Distance | UGV, 목적지가 설정돼 있어야 함 |
| `LeaderDistanceFromEnemyAtLeast` | UGV ↔ **가장 가까운 살아있는 적** 거리가 임계값 **이상** (적이 0명이면 발동 안 함) | Distance | UGV, 적군 |
| `ActorStopped` | UGV의 `AUGVAIController::IsMoving()`이 false | — | UGV + AI 컨트롤러 |
| `UAVArrived` | UAV `MissionState == Arrived` | — | 레벨에 `AUAVPawn` 1대 |
| `UAVEnemyDetected` | UAV 짐벌이 Faction==Enemy를 감지 | — | UAV + 적군에 `DetectableTargetComponent(Faction=Enemy)` |
| `EnemyDetected` | **UGV RCWS**가 적을 감지(모드 무관) | — | UGV에 `RCWSFireControlComponent` |
| `UGVFiredNearEnemy` | UGV RCWS가 **최근접 적과 `TriggerDistanceThreshold` 이내인 상태에서 발사** (자동/수동 구분 없음) | Distance | UGV RCWS, 적군 |
| `CommandPostFiredNearEnemy` | 위와 동일하되 대상이 **이동형지휘소** RCWS | Distance | `ScenarioConfig.CommandPost` 지정 필수 |
| `AllyFireStarted` | 등록된 아군 중 **누구라도 사격 버스트를 시작** | — | 아군(`AllyFormationComponent`)이 교전 상태여야 함 |
| `EnemyCasualtyCountAtLeast` | **누적 사망 적 수 ≥ `TriggerCountThreshold`** | Count | 적군에 `DetectableTargetComponent` (사망 시 등록 해제되는 걸로 카운트) |
| `AllEnemiesEliminated` | Enemy 진영 등록 타겟이 0 | — | ⚠️ 적 스폰 **전에도** 참이 되므로 반드시 적 등장 이후 스텝을 Prereq로 걸 것 |

### 2.4 이펙트 레퍼런스

| EffectType | 동작 | 레벨에 필요한 것 |
|---|---|---|
| `None` | 아무것도 안 함(순수 타이밍 마커용) | — |
| `BeginUAVMission` | UAV를 **`EnemyCube` 태그 액터 좌표**로 발진 | UAV, EnemyCube 태그 액터 |
| `RevealEnemies` | Enemy 전원 `SetRevealed(true)` (그 전까진 화면에 안 보임) | — |
| `DisableUAVTargetDetection` | UAV 감지 컴포넌트 틱 정지 | UAV |
| `MoveUGVToZone1Destination` | UGV를 **1차 목적지**로 자율주행 (+ 이후 거리/감지 트리거의 기준 액터로 UGV 등록) | `ScenarioConfig.UGVFormUpDestination` |
| `MoveUGVToZone2Destination` | UGV를 2차 목적지로 | `UGVZone2Destination` |
| `MoveUGVToZone3Destination` | UGV를 3차 목적지로 | `UGVZone3Destination` |
| `SetUGVAutoSurveillance` | UGV RCWS 자동 경계(탐색 스윕) | UGV RCWS |
| `SetUGVAutoFire` | UGV RCWS 자동 조준+발사 | UGV RCWS |
| `SetCommandPostAutoFire` | 지휘소 RCWS 자동 조준+발사 | `ScenarioConfig.CommandPost` |
| `BeginEnemyEngagementApproach` | 적 전원 **1차 전투지로 경계 이동 시작**(총 내림/저속/숙임/둘러보기, **사격 안 함**) | 적 `CombatZones[0]` 마커 |
| `BeginEnemyEngage` | 적 전원 **교전 돌입**(총 들고 뛰어서 엄폐 + 사격 시작) | 적 `CombatZones[0]` |
| `BeginEnemyFleeZone2` / `BeginEnemyFleeZone3` | 적 전원 2차/3차 전투지로 **단계적 도주**(개체별 랜덤 지연 후 순차 이탈) | 적 `CombatZones[1]` / `[2]` 마커. 비어 있는 개체는 그 자리 유지 |
| `RetargetEnemiesToAllies` / `RetargetEnemiesToCommandPost` | 적 전원 타겟 초기화 → 다음 틱에 **범위 내 최근접 유효 타겟** 재획득. **두 값의 동작은 동일**(이름은 의도 표시용) | — |
| `BroadcastApproach` / `BroadcastAmbush` | 아군 전원 접근/매복(엄폐·사격) 전환. 분대장이 있으면 수신호 재생 후 | 아군 `AmbushMarker`, 자세 마커 |
| `BeginAllyFormUpAndAdvance` | (구 시나리오) 아군 집결 + UGV 출발 | `UGVFormUpDestination` |
| `RaiseSquadSignal` / `LowerSquadSignal` | 분대장 정지 수신호 올림/내림 | `bIsSquadLeader` 아군 |
| `UAVEngagementZoomOut` | UAV 짐벌이 아군+적 전체를 프레이밍 | UAV |
| `ShowUIMessage` | 알림 위젯 표시 | `DT_NotificationWidgets`에 해당 RowName |

### 2.5 흐름 설계 규칙

- **순서를 강제하는 건 오직 `PrerequisiteStepId` 체인.** 여러 행이 같은 Prereq를 가리키면 병렬 진행.
- 트리거는 Prereq가 충족된 **뒤부터만** 평가된다 — 조건이 그 전에 이미 참이었어도 무시.
- 한 스텝은 한 번만 발동. 반복이 필요하면 별도 행으로 만들 것.
- 흐름을 중간에 끊고 싶으면 그 지점 스텝의 `bEnabled`를 끄면 된다(뒤 스텝 전부 대기).
- 타이밍만 벌리고 싶으면 `EffectType=None` + `TimerOnly` 행을 중간에 끼워 넣는 게 가장 안전.
- ⚠️ **적군 행동 스텝은 UAV/UGV 진행 스텝에 묶지 말 것** (2026-08-23 실사용에서 걸린 함정).
  적군의 교전 돌입/도주는 "UGV가 근거리에서 쐈다", "N명 죽었다" 같은 **조건만 맞으면** 발동해야
  하는데, 이 행들의 `PrerequisiteStepId`를 UAV/UGV 체인(`UAVSpotted` → `UGVSurveillance` →
  `UGVAutoFire`)에 걸어두면 **그 체인 중 하나만 `bEnabled`를 꺼도 적군이 영영 반응하지 않는다**
  (UGV가 바로 옆에서 쏴서 3명을 죽여도 아무 일도 안 일어남). 적군 행동 행은 Prereq를 비우거나
  (조건만으로 판정) **다른 적군 행동 행**에만 걸어서 순서를 잡을 것.
- 반대로 "여러 번 발동하면 안 되는 순서"(2차 도주 → 3차 도주)는 적군 행동끼리 Prereq로 묶어서
  보장한다. `EnemyCasualtyCountAtLeast`는 **누적** 카운트라, 임계값이 작은 행을 Prereq 없이 두면
  큰 행보다 먼저/동시에 켜질 수 있다.

---

## 3. 레벨 셋업 체크리스트 (새 레벨에서 처음부터)

### 3.1 필수 액터

| # | 액터 | 필수 설정 | 없으면 |
|---|---|---|---|
| 1 | 아무 액터(보통 TargetPoint) | **Tag에 `EnemyCube`** | `BeginScenarioEnemyContact`가 실패하고 시나리오가 아예 시작 안 됨 (`no actor tagged 'EnemyCube'` 경고) |
| 2 | `ScenarioConfig` (Place Actors에서 검색) | 레벨에 **정확히 1개**. 필드는 3.4 | UGV 이동/지휘소 관련 이펙트가 전부 경고만 남기고 스킵 |
| 3 | UAV (`BP_UAV`) | 1대 | `BeginUAVMission` 경고 (`레벨에서 AUAVPawn을 못 찾음`) |
| 4 | UGV (`BP_UGV_Vehicle`) | RCWS + AI 컨트롤러 | UGV 이동/사격 스텝 전부 스킵 |
| 5 | 이동형지휘소 | RCWS를 가진 액터 | 3차 전투지 스텝만 안 돌고 나머지는 정상 |
| 6 | NavMeshBoundsVolume | 모든 이동 경로/마커를 덮을 것 | 적/아군이 목적지로 못 감 |

### 3.2 적군 개체마다 (`BP_Enemy_kadex` — `EnemyCombatComponent`)

**개체당 마커 6개**가 필요하다. `CombatZones` 배열을 3개로 만들고 각 원소에:

| 배열 | 의미 | FiringPose.Marker | CoverPose.Marker |
|---|---|---|---|
| `CombatZones[0]` | 1차 전투지 | 노출해서 사격할 위치 | 엄폐 위치 **= 접근 이동의 목적지** |
| `CombatZones[1]` | 2차 전투지 | 〃 | 〃 **= `BeginEnemyFleeZone2`의 도주 목적지** |
| `CombatZones[2]` | 3차 전투지 | 〃 | 〃 **= `BeginEnemyFleeZone3`의 도주 목적지** |

- 마커는 아무 액터나 가능하지만 **TargetPoint 권장**.
- **마커의 회전(Yaw)도 의미가 있다** — 엄폐(Cover) 자세일 때 그 방향을 바라본다.
  사격(Firing) 자세일 때는 타겟을 향하므로 회전 무시.
- 포즈마다 `BodyPose`(Standing / Crouched / Prone), `Lean`(None / Left / Right) 지정.
- 엄폐↔사격은 **두 마커 사이를 실제로 걸어서** 오간다. 두 지점이 너무 멀면 사이클이 느려지니
  1~3m 정도 권장(현재 레벨은 약 2m).
- `AllyDetectRange` 스피어의 `SphereRadius` = 적이 아군/차량을 인지하는 거리(현재 20000 = 200m).
- `bAutoBeginMoveForTesting`은 **꺼둘 것**(켜면 시나리오와 무관하게 BeginPlay에서 출발).

> 팁: 개체별로 zone을 다 채우기 번거로우면, 한 개체를 완성한 뒤 복제하고 마커만 교체하는 게 빠르다.
> zone 마커가 비어 있는 개체는 해당 도주 명령을 **조용히 무시**하고 그 자리에 남는다.

### 3.3 아군 개체마다 (`BP_Ally_kadex` — `AllyFormationComponent`)

| 값 | 의미 |
|---|---|
| `AmbushMarker` | 매복 지점(이 위치로 이동해서 교전) |
| `FiringPose` / `CoverPose` / `NoTargetPose` | 각 Marker+BodyPose+Lean. 적군과 달리 **zone 개념 없이 1세트** |
| `bIsSquadLeader` | 분대장 1명. 수신호 몽타주(`DeploySignalMontage`, `TakeCoverSignalMontage`) 지정 |
| `SquadId`, `DefaultWatchYawDeg` | 분대 구분 / 대기 시 바라보는 방향 |
| `EnemyDetectRange` 반경 | 아군이 적을 인지하는 거리(현재 20000) |
| `bAutoBeginAmbushForTesting` | **꺼둘 것** (켜면 시작하자마자 교전) |

> 2차 전투지는 "아군 시야에 들어오는 지역"이어야 하므로, **아군 매복 지점과 적군
> `CombatZones[1]`의 위치 관계**가 이 단계 연출의 핵심이다.

### 3.4 `ScenarioConfig` 필드

| 필드 | 넣는 것 | 쓰는 이펙트/트리거 |
|---|---|---|
| `UGVFormUpDestination` | UGV **1차 목적지** TargetPoint | `MoveUGVToZone1Destination` |
| `UGVZone2Destination` | UGV 2차 목적지 | `MoveUGVToZone2Destination` |
| `UGVZone3Destination` | UGV 3차 목적지 | `MoveUGVToZone3Destination` |
| `UGVStandbyDestination` | (구 흐름 전용, 비워도 됨) | `BroadcastApproach` |
| `CommandPost` | 이동형지휘소 액터 | `SetCommandPostAutoFire`, `CommandPostFiredNearEnemy` |
| `ScenarioStepTable` | 이 레벨의 스텝 DataTable | 전체 |

**UGV 1차 목적지 잡는 법**: scenario.md 요구사항이 "적군이 1차 전투지에 도달하기보다 **UGV가
1차 목적지에 먼저 도착**"이므로, UGV 주행 거리/속도와 적군 `PatrolMoveSpeed`(150)를 비교해
UGV가 먼저 도착하도록 잡는다. 또 `UGVFiredNearEnemy`의 거리 임계값 안에 들어와야 1차 교전이
시작되므로, **목적지 ↔ 적군 1차 전투지 거리 < 그 임계값**이 되어야 한다.

### 3.5 최종 점검

- [ ] `EnemyCube` 태그 액터 1개
- [ ] `ScenarioConfig` 1개 + 필드 6종
- [ ] UAV / UGV / (지휘소) 배치
- [ ] 적 개체마다 zone 3개 × 마커 2개
- [ ] 아군 개체마다 매복 마커 + 자세 3종, 분대장 1명
- [ ] 테스트 자동시작 플래그 2종 모두 OFF
- [ ] NavMesh가 모든 마커/경로를 덮는지 (`P` 키로 확인)
- [ ] 스텝 테이블이 `ScenarioConfig`에 연결됐는지

---

## 4. 현재 3단계 시나리오 테이블 (`DT_ScenarioSteps_ThreeStage`, 17행)

| RowName | Prereq | Trigger | 값 | Effect | 이 행이 요구하는 레벨 값 |
|---|---|---|---|---|---|
| `UAVMission` | — | TimerOnly | 3s | BeginUAVMission | EnemyCube 태그, UAV |
| `EnemyApproach` | — | TimerOnly | 1s | BeginEnemyEngagementApproach | 적 `CombatZones[0]` |
| `UAVSpotted` | UAVMission | UAVEnemyDetected | — | MoveUGVToZone1Destination | `UGVFormUpDestination` |
| `RevealEnemies` | UAVSpotted | TimerOnly | 0s | RevealEnemies | — |
| `UAVDetectionOff` | UAVSpotted | TimerOnly | 2s | DisableUAVTargetDetection | UAV |
| `UGVSurveillance` | UAVSpotted | TimerOnly | 0s | SetUGVAutoSurveillance | UGV RCWS |
| `UGVAutoFire` | UGVSurveillance | EnemyDetected | — | SetUGVAutoFire | UGV RCWS |
| `EnemyEngage` | **—** | **UGVFiredNearEnemy** | 6000 | BeginEnemyEngage | UGV가 적 60m 이내에서 사격 |
| `EnemyFleeToZone2` | **—** | **EnemyCasualtyCountAtLeast** | **3** | BeginEnemyFleeZone2 | 적 `CombatZones[1]` |
| `UGVMoveZone2` | EnemyFleeToZone2 | LeaderDistanceFromEnemyAtLeast | 5500 | MoveUGVToZone2Destination | `UGVZone2Destination` |
| `AllyAmbush` | EnemyFleeToZone2 | TimerOnly | 5s | BroadcastAmbush | 아군 매복 마커 |
| `RetargetToAllies` | EnemyFleeToZone2 | **AllyFireStarted** | — | RetargetEnemiesToAllies | 아군이 적을 보고 쏠 수 있는 배치 |
| `EnemyFleeToZone3` | EnemyFleeToZone2 | **EnemyCasualtyCountAtLeast** | **7** | BeginEnemyFleeZone3 | 적 `CombatZones[2]`. ⚠️ 누적 카운트라 2차 도주 임계값보다 **커야** 함 |
| `UGVMoveZone3` | EnemyFleeToZone3 | LeaderDistanceFromEnemyAtLeast | 7200 | MoveUGVToZone3Destination | `UGVZone3Destination` |
| `CommandPostFire` | EnemyFleeToZone3 | TimerOnly | 3s | SetCommandPostAutoFire | `CommandPost` |
| `RetargetToCommandPost` | EnemyFleeToZone3 | **CommandPostFiredNearEnemy** | 8000 | RetargetEnemiesToCommandPost | 지휘소가 적 80m 이내에서 사격 |
| `ScenarioComplete` | EnemyEngage | AllEnemiesEliminated | — | ShowUIMessage(`ScenarioComplete`) | `DT_NotificationWidgets` |

**체인 구조(2026-08-23 재배선)**: 적군 행동 3행(`EnemyEngage` → `EnemyFleeToZone2` →
`EnemyFleeToZone3`)만 서로 묶여 있고 UAV/UGV/아군 스텝에는 의존하지 않는다. UAV·UGV 행을
테스트로 꺼도 적군은 조건만 맞으면 정상 반응한다. 반대로 UGV 후속 이동/아군 매복/지휘소
사격 행은 적군 행동 행을 Prereq로 삼는다(적이 도주해야 의미가 있으므로).

거리 값은 kadex_test 지오메트리 기준 — **새 레벨에서는 반드시 재계산**할 것
(요령: 각 단계에서 "UGV ↔ 최근접 적" 실제 거리를 재고, 단계 사이 값의 중간쯤을 임계값으로).

---

## 5. 자주 하는 커스텀

**① 다음 전투지로 도망가는 사망자 수 바꾸기**
`EnemyFleeToZone2` / `EnemyFleeToZone3` 행의 `TriggerCountThreshold` (현재 3 / 7, **누적** 기준).

**② UGV 자동사격 전환을 끄고 수동 사격으로 진행**
`UGVSurveillance` / `UGVAutoFire` 행의 `bEnabled` 해제 → `EnemyEngage`의 `PrerequisiteStepId`를
`UAVSpotted`로 변경(안 그러면 뒤가 전부 멈춤). 발사 카운터는 자동/수동을 구분하지 않으므로
**조작자가 직접 쏴도 `UGVFiredNearEnemy`는 정상 발동**한다.

**③ 1차 교전 트리거를 "거리 무관 최초 사격"으로**
`EnemyEngage`의 `TriggerDistanceThreshold`를 아주 크게(예: 100000).

**④ 특정 단계에서 흐름 멈추고 관찰**
멈추고 싶은 지점 스텝의 `bEnabled` 해제 → 그 뒤 스텝은 전부 대기.

**⑤ 전투지를 2단계로 줄이기**
`EnemyFleeToZone3` 이후 행들의 `bEnabled` 해제, `ScenarioComplete`의 Prereq를
`RetargetToAllies`로 변경.

**⑥ 적 인원 늘리기**
적 개체를 복제하고 **zone 3개 × 마커 2개**를 새로 배치·연결. 사망자 수 임계값도 인원에 맞춰 조정.

**⑦ 단계 사이 여유 시간 주기**
`EffectType=None` + `TimerOnly` 행을 끼우고, 뒤 스텝의 Prereq를 그 행으로 변경.

**⑧ 도주가 너무 우르르 몰릴 때**
적 `Min/MaxFleeCommitDelaySeconds`(기본 0.5~3) 범위를 넓히면 더 흩어져서 빠진다.

---

## 6. 트러블슈팅

로그 카테고리 `Logtitan_example`, 전부 `[ScenarioStateSubsystem]` 접두어.

| 증상 | 확인 | 원인/해결 |
|---|---|---|
| 아무 스텝도 안 켜짐 | `시나리오 스텝 발동:` 로그가 하나도 없음 | `BeginScenarioEnemyContact`를 안 쳤거나, `no actor tagged 'EnemyCube'` 경고 → 태그 액터 배치 |
| 〃 | `ScenarioStepTable이 없어서...` 경고 | `ScenarioConfig.ScenarioStepTable` 연결 |
| 특정 스텝부터 안 넘어감 | 마지막으로 찍힌 발동 로그 확인 | 그 다음 행의 Prereq/트리거 조건 점검. `bEnabled` 꺼져 있는지도 확인 |
| **테스트로 몇 행을 껐더니 적군이 아무 반응 없음** | 껐던 행이 적군 행동 행의 Prereq 체인에 있는지 | 꺼진 스텝은 발동하지 않으므로 **그걸 Prereq로 삼은 뒤 스텝은 전부 영구 대기**. 적군 행동 행의 Prereq를 비우거나 다른 적군 행동 행으로 옮길 것(2.5 규칙) |
| 적군이 화면에 안 보임 | `RevealEnemies` 행의 Prereq(`UAVSpotted`)가 꺼져 있는지 | UAV 단계를 꺼둔 상태면 reveal이 안 됨. 콘솔 `titan.DebugRevealAllEnemies 1`로 강제로 보이게 할 수 있음 |
| PIE 켜자마자 교전 | — | 적 `bAutoBeginMoveForTesting` / 아군 `bAutoBeginAmbushForTesting` 확인 |
| UGV가 안 움직임 | `MoveUGVToZoneN...: AScenarioConfig(또는 그 목적지 필드)가 비어있음` | 목적지 필드 연결 |
| 〃 | `UGV 또는 AUGVAIController를 못 찾음` | UGV 배치/컨트롤러 확인 |
| 적이 도주 안 함 | 로그엔 스텝이 찍힘 | 해당 `CombatZones[N]` 마커가 비었음(비면 조용히 무시됨) |
| 지휘소 단계가 안 돎 | `SetCommandPostAutoFire: AScenarioConfig::CommandPost가 비어있음` | `CommandPost` 지정 |
| 적이 안 쏨 | — | 정상일 수 있음 — `BeginEnemyEngage` 전에는 **의도적으로** 감지/사격이 꺼져 있다 |
| 적이 목적지로 못 감 | 적 컴포넌트 경고 `이동 중 N초간 …밖에 이동 못함(정체 의심)` | NavMesh 미커버/막힘 |

---

## 7. 부록 — 콘솔 명령 / BP 호출

**콘솔(Exec)로 바로 되는 것**
- `BeginScenarioEnemyContact` — 시나리오 시작(스텝 평가 개시)
- `BeginEnemyFlee` — 적 전원 zone 1(2차 전투지)로 도주
- `BeginAllyApproach` / `BeginAllyAmbush` / `BeginAllyFollowing`
- `BeginAllyFormUpAndAdvance (X=..,Y=..,Z=..)` / `SetUGVStandbyDestination (X=..,Y=..,Z=..)`

**BlueprintCallable만 가능(콘솔 불가)** — 필요하면 레벨 BP/디버그 위젯에서 호출
- `UScenarioStateSubsystem::FireScenarioStep(StepId)` — `Manual` 트리거 스텝 강제 발동
- `BeginEnemyEngage()` / `BeginEnemyFleeToZone(int32)` / `RetargetAllEnemies()`
- `UEnemyCombatComponent::BeginMove(zone)` / `BeginEngageAtCurrentZone()` / `BeginFlee(zone)` / `ForceRetarget()`
