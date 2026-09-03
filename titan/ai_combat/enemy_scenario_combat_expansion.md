# 3단계 전투 시나리오 — 적군 행동 고도화 구현 현황 (2026-08-24)

> `level_new_kadex_0811/scenario.md`에 정리된 새 레벨용 시나리오(UGV 단독 교전(1차) → 아군 합류(2차, UGV는
> 계속 사격하며 후퇴) → 이동형지휘소 RCWS(3차), 전환은 사망자 수/거리 트리거로 결정)를 반영해
> `enemy_ai_combat_system_status.md`(2026-08-12)의 1세트짜리 적군 엄폐/사격 시스템을 3세트로
> 확장하고, 그 사이를 잇는 분대 접근·단계적 도주·타겟 전환·사망 연출·시나리오 트리거 배선까지
> 전부 완료한 라운드. 원래 계획(`cheerful-moseying-dewdrop` 플랜 문서)은 Part F(시나리오 트리거/
> 이펙트 배선)를 별도 세션으로 미루자는 권고였으나, 실제로는 **Part A~G 전부 이 스코프 안에서
> 완료됨** — 코드에 이미 Part F/G 태그로 반영돼 있음.
>
> 관련 코드: `Source/titan_example/Soldiers/EnemyCombatComponent.h/.cpp`, `BP_Enemy_Base`
> EventGraph(사망 분기), `Source/titan_example/UI/ScenarioStepTypes.h`,
> `Source/titan_example/UI/ScenarioStateSubsystem.cpp`. 히트리액션(비살상 피격 스프링)은 별도 문서
> `enemy_hit_reaction_physics_system.md`, 로코모션 gait/AnimGraph 구조는
> `enemy_locomotion_animation_pipeline.md` 참고.

---

## Part A — 사망: 몽타주 폐기 + 액티브 랙돌

`BP_Enemy_Base::Event AnyDamage`의 사망(then) 분기를 스크립트 몽타주(`AM_Enemy_Death2`) 재생에서
`UPhysicalAnimationComponent` 기반 액티브 랙돌로 완전히 교체. 실행 순서:

1. `DeathIndex` 랜덤 세팅 → `IsDead=true` → `AimPitch`/`IsKneeling`/`IsProne` 전부 중립값으로 리셋
   (죽는 순간 값에 고정된 채 사망 포즈와 계속 충돌하던 기존 버그 재발 방지).
2. `StopMovementImmediately` + `DisableMovement`.
3. 캡슐 콜리전 비활성화, 메시는 `SetCollisionEnabled(QueryAndPhysics)`.
4. `PhysicalAnimationComponent->ApplyPhysicalAnimationSettingsBelow("Hips", ...)` — 현재 강도값은
   전부 0(사실상 순수 랙돌, 애니메이션 쪽으로 끌어당기는 힘 없음)으로 세팅돼 있음.
5. `SetAllBodiesSimulatePhysics(true)`.
6. `SetAllPhysicsLinearVelocity(LastVelocity)` — 죽기 직전 이동 속도로 관성 주입.
7. **(2026-08-24 추가)** `DelayUntilNextTick` 한 틱 대기 — 아래 참고.
8. `AddImpulseAtLocation(Mesh, LastHitDirection * DeathImpulseMagnitude, LastHitLocation,
   LastHitBoneName)` — 총알 방향 임펄스.
9. `CurrentRifle`(스폰된 소총 액터) detach + 물리 켜기, 장식용 `Gun` 메시도 동일 처리.
10. 5초 딜레이 후 `CurrentRifle`/자기 자신 `DestroyActor`.

### 2026-08-24 버그 수정 — 사망 임펄스가 안 보임
`DeathImpulseMagnitude`를 400→1억5천만까지 올려도 육안으로 전혀 안 보인다는 리포트로 조사, 두 겹
버그 발견:
- `BP_Enemy_kadex`(실제 스폰 클래스) CDO가 `DeathImpulseMagnitude`를 **0으로 독립 오버라이드**하고
  있어서 부모값이 전혀 안 먹힘(1절/`enemy_hit_reaction_physics_system.md` 1절과 동일한 "자식이
  부모 CDO를 그림자화" 패턴). 양쪽 CDO를 `1500`으로 통일.
- `SetAllBodiesSimulatePhysics(true)` 직후 같은 프레임에 바로 `AddImpulseAtLocation`을 부르면
  Chaos가 킨네마틱→시뮬레이트 전환을 아직 처리하기 전이라 임펄스가 조용히 씹힘(속도 설정은 되는데
  임펄스만 안 먹는 비대칭 증상). `SetAllPhysicsLinearVelocity`와 `AddImpulseAtLocation` 사이에
  `DelayUntilNextTick` 노드를 끼워서 해결. 사용자가 PIE에서 확인 완료("성공했음").

`Enemy_PhysicsAsset`의 관절 제약(Swing1/Swing2/Twist Limit)도 랙돌이 이상하게 꺾이지 않도록
Physics Asset Editor에서 튜닝 완료(코드 변경 없는 순수 에셋 작업).

---

## Part B — 전투지 zone 배열 구조

`EnemyCombatComponent.h`의 `FEnemyCombatZone`(`FiringPose`+`CoverPose`) 배열 `CombatZones`로
전환 — 기존엔 적 액터당 `EngagePoint`/`FiringPose`/`CoverPose` 단일 세트였던 걸 3개 zone(1차/2차/
3차 전투지, 인덱스 0/1/2)으로 확장. 별도 `EngagePoint`/`ExfilPoint` 필드는 폐지 — "N차 전투지"가
곧 그 zone의 `CoverPose.Marker`라는 문서상 정의를 그대로 반영해서, Move/Flee의 이동 목적지가 항상
`CombatZones[CurrentZoneIndex].CoverPose.Marker`로 통일됨. `TickCombatPoseCycle`/`ApplyCombatPose`
등 기존 로직은 하드코딩된 `FiringPose`/`CoverPose` 참조만 `CombatZones[CurrentZoneIndex].X`로
바뀌었을 뿐 동작 자체는 안 바뀜.

`kadex_test` 레벨에 적군 4마리의 `CombatZones[0]` 마커 세팅 완료(기존 레벨 검증용 — `EngagePoint`
필드가 없어졌으므로 이전 레벨의 저작 데이터와는 호환 안 됨, 재저작 필요).

---

## Part C — 분대단위 이동 (1차 전투지 접근) + 사주경계

scenario.md 요구사항 "느린 속도 + 총 내림 + 숙임 + 주위 경계"를 `CurrentZoneIndex==0`(1차 전투지
접근) 상태 전용으로 구현:

- `PatrolMoveSpeed`(기본 150, `MoveSpeed` 300보다 느림)로 이동.
- `IsHoldingWeapon?=false`, 숙인 자세 — `ABP_Enemy_kadex2`에 이미 있던 `LoweredLocomotion`
  상태(아군 것 복제 시 같이 이식됨) 재사용, 새 애니메이션 불필요.
- 기존 낙하산 착지용 `IsLookingAround` 인프라를 재사용해 주기적으로 둘러보기 트리거
  (`MinLookAroundIntervalSeconds`~`MaxLookAroundIntervalSeconds`, 지속 `LookAroundDurationSeconds`).
- **사주경계 재설계**: 몸이 보는 방향이 이동 방향을 따르지 않고(`bFaceMovementDirection=false`)
  `PrimaryWatchYawDeg`(절대 월드 Yaw, 개체마다 다르게 배정 — 예: 0/90/180/270)를 중심으로
  `WatchSweepRangeDeg` 범위를 Perlin 노이즈로 천천히/불규칙하게 훑음(사인파처럼 딱 떨어지면
  기계적으로 보여서 노이즈 사용, `WatchSweepNoiseSeed`로 개체마다 위상 다르게). 이동 경로는 각자
  `CombatZones[0]` 마커로 알아서 가면서도 몸은 배정된 방향을 경계.

2차/3차 전투지로의 이동(도주)은 이 스타일이 아니라 기존처럼 `FleeMoveSpeed`(빠른 숙인 뜀박질).

### 2026-08-25 — 둘러보기 연출: 몽타주 시도 폐기 → 스윕 각도 확대로 해결

"둘러보는 느낌이 약하다"는 리포트로 **전용 둘러보기 몽타주를 얹는 방향을 먼저 시도했다가 폐기**함.
경위와 결론(같은 시행착오 반복 방지용):

1. `AM_Enemy_Looking_Around_Montage_Base`를 재생하도록 배선했으나 **화면에 전혀 안 나옴** — 원인은
   그 몽타주의 슬롯이 `UpperBodySlot`인데 `ABP_Enemy_kadex2` AnimGraph엔 `DefaultSlot`/`ReloadSlot`/
   `FireRecoil` 슬롯 노드만 있어서, 재생은 되지만 받아줄 노드가 없었던 것.
2. `UpperBodySlot` 슬롯 노드 + `Layered blend per bone`(BlendMask 모드, 스켈레톤에 만든
   `BM_UpperBodyLookAround` 마스크) 레이어를 추가해 상체/하체 가중치를 나눠 얹도록 구성.
   → **이 배선 자체는 지금도 그대로 남아있고 정상 동작함**(피격 리액션 등 상체 몽타주에 재활용 가능).
3. 그런데 **애니메이션 원본들이 전부 전신 모션**이라(발부터 척추·머리까지 같이 돌아서 주위를 봄)
   웅크린 이동 자세와 근본적으로 안 맞았음. 하체 가중치를 낮추면 고개만 까딱하는 수준이 되고,
   높이면 웅크렸다가 일어서서 두리번거림. 대안으로 찾은 `Crouch_Torch_Idle_02_Anim`(웅크린 상태
   둘러보기)도 마찬가지로 전신 모션이라 개선이 없었음.
4. **결론**: 몽타주를 쓰지 않고, 원래 있던 스윕 메커니즘의 각도만 키우는 게 정답이었음 —
   `WatchSweepRangeDeg` **±20° → ±60°**. 몸이 크게 돌아가면 이동은 그대로 목적지로 가므로
   블렌드스페이스의 `Direction` 축이 알아서 게걸음/뒷걸음 모션을 뽑아준다("몸을 왼쪽으로 돌리면
   키보드 D를 눌러 걷는 것과 같은 상태"). 새 애셋도, 몽타주도 필요 없음.

몽타주 재생 경로 자체는 코드에 남겨둠(`LookAroundAnim`이 비어 있으면 아무것도 재생 안 하는
하위호환 구조). 몽타주가 아니라 **AnimSequence를 직접 받아 `PlaySlotAnimationAsDynamicMontage`로
슬롯에 얹는 방식**이라 시퀀스마다 몽타주 애셋을 만들 필요가 없고, 재생 배속
(`Min/MaxLookAroundPlayRate`)과 시작 지점(`Min/MaxLookAroundStartRatio`, 시퀀스 길이 대비 비율)을
매 재생마다 무작위로 뽑는 기능도 들어가 있음 — 나중에 적합한(상체만 움직이는) 시퀀스가 생기면
프로퍼티에 꽂기만 하면 됨.

### 2026-08-25 — 경계 이동 중 고개 각도(`PatrolAimPitchDeg`)

"웅크리고 걸을 때 고개를 너무 숙인다"는 리포트로 조사한 결과, **적군의 `AimPitch`는 사실상 항상
0이었음**:
- `AimPitch`는 `ABP_Enemy_kadex2` AnimGraph에서 **`Spine2` 본의 `Transform (Modify) Bone` 회전으로
  이미 물려 있음**(그 위 `Neck`/`Head`가 FK로 따라옴) — 즉 값만 채우면 상체+고개가 들림.
- 그런데 적군엔 이 값을 갱신하는 주체가 없었음. `UEnemyCombatComponent::TickWeaponAimPitchCorrection`은
  이름과 달리 **소총 액터의 상대 회전만** 바꾸고 캐릭터 `AimPitch`는 안 건드리며, `BP_Enemy_Base`엔
  `EventTick` 자체가 없음(아군은 `BP_ThirdPersonCharacter::EventTick`이 매 틱 `FindLookAtRotation`으로
  채우는데 그 대응물이 없었던 것). 유일한 사용처가 사망 시 `SetAimPitch(0)`뿐이었음.

→ 경계 이동 중 `AimPitch = PatrolAimPitchDeg`(기본 12°)를 쓰고, **교전 시작(`BeginEngageAtCurrentZone`)
및 전투지 도착 시 0으로 되돌림**(안 되돌리면 교전 중 아무도 갱신하지 않아 위를 본 채로 굳음).
스켈레톤 축이 돌아가 있어 부호가 반대일 수 있으므로 값은 에디터에 노출해둠.

---

## Part D — 단계적 도주 + 타겟 전환 캐스케이드

**단계적 도주**: `BeginFlee(NextZoneIndex)` 호출 시 즉시 전환하지 않고, 인스턴스별 랜덤
`MinFleeCommitDelaySeconds`~`MaxFleeCommitDelaySeconds`(0.5~3초) 동안 `Combat` 상태에서 계속
Cover/Firing 사이클(엄호 사격)을 유지하다가 `CommitPendingFlee()`로 실제 전환 — 전원이 한번에
안 튐.

**타겟 전환 캐스케이드**: `TryAcquireTargetFromOverlaps`의 타겟 후보 필터를 확장 — 기존엔
`UAllyFormationComponent`가 있는 액터만 인정해서 **UGV/이동형지휘소(차량, 이 컴포넌트 없음)는
절대 타겟이 될 수 없었음**. 이제 `UAllyFormationComponent` **또는** `Faction==Friendly`인
`UDetectableTargetComponent` 보유 여부로 판정 — 1차/3차 전투지의 "UGV/지휘소를 조준·사격" 요구를
충족. `ForceRetarget()`(`HasTarget=false`+`CurrentAlly` 클리어)로 다음 틱에 범위 내 유효 타겟을
자연 재획득 — 2차 전투지 진입(UGV→아군), 3차 전투지 진입(아군→지휘소) 타겟 전환에 재사용.

### 2026-08-25 — 타겟 분산(랜덤 풀) + 선호도(`EEnemyTargetPreference`)

**분산**: "여러 적이 같은 아군 한 명만 집중사격한다"를 없애려고 최근접 1명 고정에서
**거리순 상위 `TargetCandidatePoolSize`(기본 5)명 중 무작위**로 바꿈. 재추첨 시점은 두 곳 —
`Combat`은 사격/엄폐 전환마다(`SetCombatPoseState`), `Move`/`Flee`는 이동 중 위치가 계속 바뀌므로
`Min/MaxMoveRetargetIntervalSeconds`(2~4초) 주기(`TickMoveRetarget`).

이 과정에서 나온 회귀 두 건과 그 대응:
- **먼 아군을 쏨**: 감지 스피어가 넓어 코앞의 UGV와 한참 뒤의 아군이 같은 풀에 들어가고 추첨이
  먼 쪽을 고르는 일이 생김(예전엔 항상 최근접이라 없던 문제). → `TargetCandidateMaxExtraDistanceCm`
  (기본 1500) 추가: **최근접 후보보다 그 이상 먼 대상은 풀에서 제외**.
- **1차 전투지에서 아군을 쏨**: 선호도 기본값이 `Any`라, 아직 사격도 안 하고 서 있는 아군이
  감지 범위 안에 있기만 하면 후보에 포함됨. → 아래 선호도로 해결.

**선호도** `EEnemyTargetPreference { Any, Infantry, Vehicle, SpecificActor }` 신규. 후보 풀을 1차로
좁히되, **선호 대상이 사거리에 하나도 없으면 조용히 전체 후보로 폴백**(아무도 안 쏘는 공백 방지).
시나리오 이펙트가 각 국면에서 명시적으로 지정:

| 시점 / 이펙트 | 선호도 |
|---|---|
| `BeginEnemyEngage` (1차 전투지 교전 시작) | `Vehicle` — UGV/지휘소 등 비보병 |
| `RetargetEnemiesToAllies` (2차, `AllyFireStarted` 트리거) | `Infantry` — 보병 아군 |
| `RetargetEnemiesToCommandPost` (3차) | `SpecificActor` — `AScenarioConfig::CommandPost` 지정 |

이전엔 `RetargetEnemiesToAllies`/`RetargetEnemiesToCommandPost` **두 이펙트의 실제 동작이 완전히
동일**했고(둘 다 "지금 가장 가까운 유효 타겟" 재획득), 그래서 아군으로 갈아타라는 지시를 받아도
근처 UGV를 그대로 다시 잡는 일이 잦았음 — 이제 각각 실제 의미를 가짐.

---

## Part E — 검증

이동 중 Hit_Reaction(비살상)과 사망 관성이 PIE에서 자연스러운지 육안 확인 완료.

---

## Part F — 시나리오 트리거/이펙트 배선

`ScenarioStepTypes.h`/`ScenarioStateSubsystem.cpp`(기존 스위치문 기반 트리거/이펙트 패턴)에 신규
항목 추가 완료:

**신규 `EScenarioTriggerType`**:
- `EnemyCasualtyCountAtLeast` — 시나리오 시작 시점 기준 적 사망 수가 `TriggerCountThreshold`
  이상이면 발동(전용 int32 필드, 기존 float `TriggerDistanceThreshold`와 분리해서 단위 혼동 방지).
- `LeaderDistanceFromEnemyAtLeast` — UGV와 가장 가까운 살아있는 적 사이 거리가
  `TriggerDistanceThreshold` 이상 벌어지면 발동("이 전투지 교전 종료 후 다음 전투지로 이동" 판정,
  기존 `DistanceThreshold`와 부등호 방향 반대).
- `UGVFiredNearEnemy` / `CommandPostFiredNearEnemy` — UGV(또는 이동형지휘소) RCWS가 최근접 살아있는
  적과 `TriggerDistanceThreshold` 이내인 상태에서 실제로 한 발이라도 쐈으면 발동(그 틱의 최근접
  거리를 기억해뒀다가 판정 — 먼 거리에서 쏜 뒤 나중에 가까워지는 것만으론 발동 안 함).
- `AllyFireStarted` — 아군 전원의 `GetFireTriggerCount()` 합이 스텝 시작 시점보다 커지면 발동
  ("적을 봤다"가 아니라 "실제로 방아쇠를 당겼다"의 한 박자 늦은 시점).

**신규 `EScenarioEffectType`**:
- `BeginEnemyFleeZone2`/`BeginEnemyFleeZone3` — 등록된 적 전원에게 `BeginFlee(1)`/`BeginFlee(2)`
  브로드캐스트.
- `RetargetEnemiesToAllies`/`RetargetEnemiesToCommandPost` — 적 전원에게 선호도 지정 +
  `ForceRetarget()` 브로드캐스트. (2026-08-25 이전엔 두 값의 동작이 완전히 동일했으나, 지금은
  각각 `Infantry`/`SpecificActor` 선호도를 실제로 넘김 — Part D의 선호도 절 참고.)
- `MoveUGVToZone1Destination`/`Zone2`/`Zone3` — `AScenarioConfig`의 목적지를 읽어
  `AUGVAIController::MoveToDestination` 호출(RCWS 모드는 안 건드려서 이동 중에도 자동 조준/사격
  계속).

적 카운트 판정은 새 트래킹 인프라 없이 기존 `AllEnemiesEliminated`/`UDetectableTargetSubsystem`
인프라를 그대로 재사용(`ScenarioEnemyCountBaseline` 기준값 - 현재 생존 수).

---

## Part G — 경계 이동 ↔ 교전 전환 (원 계획에 없던 추가 설계)

scenario.md 세부 요구사항("UGV RCWS가 최초 사격하기 전까지 적군은 아직 교전 상태가 아님, 사격
받으면 그때 숙인 채 바로 뛰어서 엄폐 시작")을 반영해 원 계획에는 없던 `bEngaged` 게이트를 추가:

- `BeginMove(0)`(1차 전투지 접근)은 `bEngaged=false`로 시작 — 감지 스피어가 꺼져 있어서 아군/UGV가
  사거리에 들어와도 타겟을 안 잡고 쏘지도 않음(`TryAcquireTargetFromOverlaps`의 최종 게이트).
  그 외 zone으로의 직접 이동은 이미 교전 중이라는 뜻이라 `bEngaged=true`로 시작.
- `BeginEngageAtCurrentZone()`(신규 함수, `EScenarioEffectType::BeginEnemyEngage`가 호출) — 총을
  들고(`IsHoldingWeapon?=true`) 둘러보기를 멈추고 감지를 켬. 경계 이동 중이었으면 목적지는 그대로
  두되 속도만 `EngageRushSpeed`(400, 숙인 뜀박질)로 올림, 이미 전투지 도착 상태였으면 자세 사이클
  안 바꾸고 사격만 열림.
- UGV 쪽도 짝을 맞춰 `MoveUGVToZone1/2/3Destination` 이펙트로 자율주행 단계를 트리거.

### 2026-08-25 — 돌진 구간의 "경계사격 ↔ 전력이동" 번갈이

교전 시작 후 전투지로 뛰어가는 구간(zone0 + `bEngaged`)에서, 계속 타겟만 보며 쏘면서 가는 게
아니라 두 구간을 **개체별 랜덤 시간으로 번갈아** 돌림(사용자 요청 — "몇 명은 쏘고 몇 명은 도망"
식으로 역할을 나누는 게 아니라, 각자가 몇 초 쏘고 몇 초 뛰는 방식):

| 구간 | 길이 | 동작 | 속도 |
|---|---|---|---|
| 경계사격 | `Min/MaxSuppressFireWindowSeconds` (1.5~3초) | 몸이 타겟을 향한 채 단발 견제사격 | `SuppressFireMoveSpeed`(220) |
| 전력이동 | `Min/MaxRushOnlyWindowSeconds` (2~4초) | 조준/사격 판정을 통째로 건너뛰고 이동방향만 봄 | `EngageRushSpeed`(400) |

`BeginEngageAtCurrentZone` 직후엔 **전력이동 구간부터 시작**해서 피격 직후 반사적으로 튀어나가는
그림이 먼저 나오게 함. 개체마다 위상이 달라 자연히 엇갈리므로 별도 역할 배정이 필요 없음.

**여기서 드러난 기존 회귀 하나**: 경계사격 구간인데도 대부분이 몸을 안 돌리고 목표 지점만 보며
걷는 문제가 있었는데, 원인은 `BP_Enemy_Base::EventOnLanded`가 낙하산 착지 시 켜는
`bOrientRotationToMovement=true`였음 — CharacterMovement가 매 프레임 액터를 속도 방향으로 되돌려
`TickFacingInterp`의 조준 회전과 정면으로 싸웠고, 어느 쪽이 이기는지가 이동방향/타겟방향 각도에
달려 있어서 "PIE마다 한두 명만 제대로 조준"하는 것처럼 보였음(전투지 도착 후엔 속도가 0이라
자동 회전이 개입할 방향이 없어 멀쩡했던 것도 같은 이유). 아군은 이 두 플래그가 처음부터 꺼져 있어
문제가 없었음. → `TickComponent`에서 `Standby`가 아닐 때 매 틱
`bOrientRotationToMovement`/`bUseControllerRotationYaw`를 꺼둠(착지 이벤트가 언제 켜든 되돌리므로
순서에 안 휘둘림). 낙하 중에는 그 설정이 여전히 필요하므로 블루프린트는 안 건드림.

---

## 남은 작업 / 알려진 이슈

- 30명 규모 등 다수 배치 시 성능/충돌 특성 미실측(아군 쪽은 이미 그 규모로 검증됨).
- 새 레벨(`newlevel`)에 실제 DataTable 스텝(언제/어떤 조건으로 각 트리거를 발동시킬지) 저작은
  코드 범위 밖 — 콘텐츠 작업으로 별도 진행 필요. 시나리오 전체를 처음부터 끝까지 자동 진행시켜보는
  종단 검증도 아직.
- 적군 소총이 낙하산 하강 중 일시적으로 뒤집히는 현상 — 원인 규명됐으나 미해결(작업 목록 #36).
- 이동 중 피격 시 비틀거림 애니메이션 — 미구현(작업 목록 #38, Hit_Reaction 몽타주 자체는 이동
  상태와 무관하게 항상 재생되므로 최소 기능은 있음).
