# GASP 5.8 애님 블루프린트 구조 분석 — `SandboxCharacter_CMC_ABP`

2026-09-02 / 완료(스테이트머신 내부 미접근) / GASP의 CMC 캐릭터 애님 파이프라인 전수 분석 — AnimGraph 22노드 위상·평가순서, 캐릭터↔ABP 계약 구조체, 함수 그래프 지도, 궤적 생성 경로, MM 스키마·Chooser 계층, 인과 맵, 우리 층의 삽입 지점, 확장 vs 재구축 판정.

> **폴더 규칙·진행 상황·미해결 항목**: `../CLAUDE.md` · `../CURRENT_STATE.md` · `../OPEN_ITEMS.md`
>
> 목적: 이 문서는 **"무엇을 건드리면 무엇이 바뀌는가"의 지도**다. 확장을 택하든 재구축을 택하든
> 100% 재사용된다 — 재구축하면 "무엇을 재현할지"의 명세가 되고, 확장하면 "어디를 건드릴지"의
> 지도가 된다.
>
> 선행 문서: `../design/2026-09-01_architecture.md`(전체 설계),
> `../assets/2026-09-02_asset_supply_and_collaboration.md`(자산/협업).
> 후속 문서: `2026-09-02_pose_pipeline_spec.md`(이 분석을 근거로 한 애니메이션 층 명세).

---

## 0. 조사 방법과 한계

- **방법**: Unreal MCP(`editor_toolset`)로 에디터에 직접 질의. `read_graph_dsl`로 함수 그래프,
  `find_nodes`/`get_node_infos`로 AnimGraph 위상, `ObjectTools.get_properties`로 에셋 설정값.
  대량 조회는 `ProgrammaticToolset`으로 배치 실행.
- **대상**: `/Game/Blueprints/SandboxCharacter_CMC_ABP` (NPCLevel의 AI 병사 3기가 실제로 쓰는 ABP.
  `SandboxCharacter_CMC_C_1.CharacterMesh0.AnimClass`로 확인)
- **한계 — 접근 못 한 것**:
  - **스테이트머신 내부 그래프**(`AnimGraphNode_StateMachine_2`의 상태/전환). MCP가 경로를
    해석하지 못한다(`... is not valid EdGraph`). 에디터에서 수동 확인 필요.
  - **프로퍼티 바인딩의 정확한 연결선**. 핀이 와이어로 연결돼 있지 않고 바인딩으로 채워지는
    경우, 바인딩 대상을 직접 못 읽었다. 함수 이름(`Get_*`)과 핀 이름의 대응으로 **추론**했다.
    추론한 항목은 아래에서 (추정)으로 표시한다.
  - 트래버설·래그돌 경로는 이번 범위에서 제외(별개 관심사).

---

## 1. 한 장 요약

```
캐릭터(SandboxCharacter_CMC)
    │  Get_PropertiesForAnimation() → S_CharacterPropertiesForAnimation  ← 유일한 계약
    ▼
ABP EventGraph (BlueprintUpdateAnimation / ThreadSafe)
    Update_Trajectory → Update_EssentialValues → Update_States
    ▼  변수 76개
AnimGraph  (아래 2절 위상)
    MM 선택 → Lean 애디티브 → 조준 오프셋 애디티브 → 몽타주 슬롯
    → OffsetRootBone → RemapCurves → [컴포넌트공간] FootPlacement → LegIK → [로컬]
    → PoseHistory(기록) → Root
```

**핵심 성질 3가지**

1. **캐릭터와 ABP는 구조체 하나로만 통신한다.** 액터 변수를 매 틱 직접 읽지 않는다 —
   `titan_example`이 `AimPitch`/`IsKneeling`/`IsProne`을 직접 읽어서 겪은 문제가 여기엔 없다.
2. **궤적은 플레이어 입력이 아니라 캐릭터 이동 상태에서 생성된다**(4절). AI 구동이 원리적으로
   가능한 이유.
3. **MM 스키마가 놀랍도록 얇다**(6절). 품질은 스키마 복잡도가 아니라 **데이터 양**에서 나온다.

---

## 2. AnimGraph 전체 위상 (평가 순서)

노드 22개. 화살표는 포즈 흐름(= 평가 순서).

```
① 로코모션 소스 선택
   MotionMatching_0 ─────────────────────────┐
                                             ├→ BlendListByInt_0
   StateMachine_2 → Inertialization_1 ─┐     │   (ActiveChildIndex=0 → MM이 기본)
   BlendStack_3 ──────────────────────┴→ TwoWayBlend_2(Alpha=1 → B=BlendStack) ─┘
                                                   ↑ 실험적 스테이트머신 경로

② 애디티브 적층 (로컬/메시 공간)
   BlendListByInt_0
     → ApplyMeshSpaceAdditive_2   Base=①, Additive=BlendSpacePlayer_0 [BS1D_Additive_Lean_Run]
     → ApplyMeshSpaceAdditive_0   Base=위, Additive=DeadBlending_0, Alpha=1
            DeadBlending_0 ← BlendListByBool_0 (bActiveValue=False → Pose_0)
                 Pose_0 = BlendSpacePlayer_1 [BS_Neutral_AO_Stand]   ← 조준 오프셋
                 Pose_1 = IdentityPose_1                              ← 조준 끔
            BlendTime_0=0.75 / BlendTime_1=1.5

③ 몽타주·루트
   → Slot_0 ('DefaultSlot')
   → OffsetRootBone_0   TranslationMode=Interpolate, RotationMode=Accumulate,
                        TranslationHalflife=0.2, MaxTranslationError=30, bClampToTranslationVelocity=False
   → RemapCurves_0      (CurveExpression)

④ IK (컴포넌트 공간)
   → LocalToComponentSpace_0
   → FootPlacement_0    Alpha=1  (설정 상세 3절)
   → LegIK_1            Alpha=1
   → ComponentToLocalSpace_2

⑤ 기록
   → PoseSearchHistoryCollector_0  (PoseHistory)
   → Root
```

### 2.1 이 위상에서 읽어야 할 4가지

| # | 사실 | 왜 중요한가 |
|---|---|---|
| A | **조준 오프셋이 애디티브로, IK보다 앞에 있다** | 우리가 설계한 "애디티브는 앞, 결합 IK는 뒤" 순서가 GASP에 이미 그대로 있다. 5.5.3절 4층 구조와 정합 |
| B | **PoseHistory가 IK 뒤에 있다** | MM이 참조하는 포즈 이력이 **발 IK가 적용된 최종 포즈**다. 매칭이 실제 표시되는 몸과 일치한다 |
| C | **로코모션 소스가 2개**(MM / 실험 SM) | `BlendListByInt.ActiveChildIndex`로 갈린다(바인딩은 **`LocomotionSetup`** — 14.1절). ~~실험 SM 경로에만 Orientation Warping이 있다~~ → **정정: 기본 MM 경로에도 있다. 15.1절 참고** |
| D | **IK 구간이 명확히 분리돼 있다** | `LocalToComponentSpace` ~ `ComponentToLocalSpace` 사이가 IK 전용 구간. 우리 IK를 넣을 자리가 여기다 |

---

## 3. 주요 노드 설정값

### 3.1 `FootPlacement_0` — 발이 안 미끄러지는 이유

```
ikFootRootBone : ik_foot_root        pelvisBone : pelvis
legDefinitions : foot_r/ik_foot_r/ball_r, foot_l/ik_foot_l/ball_l, numBonesInLimb=2
                 speedCurveName = contact_r / contact_l      ← 애니메이션의 접지 커브를 읽음
plantSettings  : speedThreshold=60, distanceToGround=10, lockType=PivotAroundBall,
                 unplantRadius=20, replantRadiusRatio=0.2, unplantAngle=60,
                 replantAngleRatio=0.2, maxExtensionRatio=0.5, minExtensionRatio=0.2,
                 unalignmentSpeedThreshold=200, ankleTwistReduction=0.75
pelvisSettings : maxOffset=250, linearStiffness=100, linearDamping=1,
                 horizontalRebalancingWeight=0.3, maxOffsetHorizontal=10, heelLiftRatio=0.5,
                 pelvisHeightMode=AllLegs, actorMovementCompensationMode=SuddenMotionOnly,
                 bDisablePelvisOffsetInAir=true
traceSettings  : startOffset=-75, endOffset=100, sweepRadius=5, maxGroundPenetration=20, bEnabled=true
interpolation  : unplantLinear(200,1), unplantAngular(179,1), separation(1000,1),
                 floorLinear(1000,1), floorAngular(450,1)
```

- **`lockType=PivotAroundBall`**: 발을 월드에 심고 발볼 중심으로만 회전. `unplantRadius`(20cm)나
  `unplantAngle`(60°)를 넘어야 뗀다. 사용자가 관찰한 "막혀도 발이 절대 안 미끄러진다"의 직접 원인.
- **골반 보정이 스프링**(stiffness 100 / damping 1)이고 `pelvisHeightMode=AllLegs`. 설계 문서
  5.2절의 "발만 붙이면 다리가 늘어나므로 골반까지 내린다"가 그대로 구현돼 있다.
- **플랜트 설정은 런타임에 교체된다** — 5.2절 `Get_FootPlacementPlantSettings` 참고.

### 3.2 `PoseSearchHistoryCollector_0` (PoseHistory)

```
poseCount=2, samplingInterval=0
collectedBones : foot_r, foot_l, thigh_r, thigh_l, spine_05, pelvis
collectedCurves: ["Phase"]                      ← 보행 위상
bResetOnBecomingRelevant=true, rootBoneRecoveryTime=0.3
bGenerateTrajectory=false                       ← 궤적을 여기서 만들지 않는다
trajectoryHistoryCount=10, trajectoryPredictionCount=8, predictionSamplingInterval=0.4
trajectoryData : rotateTowardsMovementSpeed=10, maxControllerYawRate=70,
                 bendVelocityTowardsAcceleration=0, 속도/가속 리매핑 커브 미사용
```

> `bGenerateTrajectory=false`이고 `TransformTrajectory` 핀이 와이어로 연결돼 있지 않다 →
> **ABP의 `Trajectory` 변수가 프로퍼티 바인딩으로 주입된다**(추정). 궤적 자체는 4절에서 만든다.

`Phase` 커브를 수집한다는 것은 **보행 위상 정합 블렌딩의 재료가 있다**는 뜻이다. 서로 다른
데이터베이스의 포즈를 섞을 때 발 딛는 타이밍을 맞출 수 있다.

### 3.3 `OffsetRootBone_0`

```
TranslationMode=Interpolate, RotationMode=Accumulate
TranslationHalflife=0.2, MaxTranslationError=30, bClampToTranslationVelocity=False
```

메시 루트를 캡슐과 분리해 관성감을 만든다. `Update_EssentialValues`가 이 노드의 트랜스폼을
읽어 `RootTransform`으로 삼고(yaw+90 보정), **조준 오프셋과 Orientation Warping의 기준 공간이
된다**(5.3·7절). 공식 문서상 실험적이며 충돌 검사가 없다.

### 3.3b `RemapCurves_0` — 발 접지의 실제 구동원 ★

```
expressionSource : ExpressionList
assignmentExpressions:
    contact_l = (1 - contact_l) * 100
    contact_r = (1 - contact_r) * 100
```

이 노드가 애니메이션의 `contact_l`/`contact_r` 커브를 뒤집어 0~100으로 스케일한다. 그리고
`FootPlacement.legDefinitions.speedCurveName`이 바로 이 `contact_r`/`contact_l`을 읽는다
(`plantSettings.speedThreshold = 60`).

**즉 발을 언제 심을지를 애니메이션 데이터가 결정한다:**

```
애니메이션의 contact_l/r 커브 (접지 = 1)
   → RemapCurves : (1−c)×100        → 접지 = 0, 뜬 상태 = 100
   → FootPlacement가 "발 속도"로 해석, speedThreshold=60 미만이면 심음
   → PivotAroundBall 로 고정, unplantRadius 20cm / unplantAngle 60° 넘으면 해제
```

> ### ⚠️ 자산 파이프라인 필수 요구사항
>
> **우리가 새로 들여오는 모든 로코모션 클립은 `contact_l`/`contact_r` 커브를 가져야 한다.**
> 없으면 발 심기가 오작동한다(커브가 0으로 읽혀 항상 심으려 하거나, 반대로 전혀 안 심음).
>
> Mixamo·ASP 등 외부 클립에는 이 커브가 없다. 해결책은 엔진 내장 도구다:
> **`UMotionExtractorModifier`** — 본의 모션을 커브로 굽는 애니메이션 모디파이어.
> `BoneName=foot_l/foot_r`, `MotionType=TranslationSpeed`, `bNormalize=true`,
> `bUseCustomCurveName=true` + 커브 이름 지정으로 접지 커브를 생성할 수 있다.
> (`../assets/2026-09-02_asset_supply_and_collaboration.md` 4절의 루트모션 인코딩 파이프라인에
> **이 단계를 추가해야 한다** — 아래 [P] 참고)
>
> 부수적으로 `UFootstepAnimEventsModifier`는 커브가 아니라 **싱크 마커/노티파이**를 생성한다
> (검출 방식: 기준본 통과 / 지면 도달 / 본 속도). 발소리 노티파이 자동 생성에 쓸 수 있다.

**[P] 자산 반입 파이프라인 (갱신판)**

```
1. 무료 인플레이스 클립 확보
2. IK Retargeter → UE5 Manny
3. UEncodeRootBoneModifier      → 루트모션 합성
4. UMotionExtractorModifier     → contact_l / contact_r 커브 생성      ← 신규 (이번 분석에서 발견)
5. UFootstepAnimEventsModifier  → 발소리 노티파이 (선택)
6. Root Motion 활성화 → Pose Search Database 편입
```

### 3.4 애디티브 2종

| 노드 | 에셋 | 용도 |
|---|---|---|
| `BlendSpacePlayer_0` | `BS1D_Additive_Lean_Run` | 가속에 따른 좌우 기울임(뱅킹) |
| `BlendSpacePlayer_1` | `BS_Neutral_AO_Stand` | **조준 오프셋**(비무장 중립 포즈 그리드) |

`BS_Neutral_AO_Stand`의 소스는 `Animations/AimOffset/`의 `M_Neutral_AO_Stand_X{0,±45,±90,±135}_Y{0,±90}`
= **7 yaw × 3 pitch = 21 포즈**. Crouch용도 동일하게 21포즈 존재(`M_Neutral_AO_Crouch_*`).
**로코모션 1,450 클립 대비 조준 공간은 42포즈로 정의된다.**

---

## 4. 궤적 생성 — P0-1의 핵심

`Update_Trajectory` 전문(디코딩):

```
Trajectory = PoseSearchGenerateTrajectory(forCharacter)(
      <Character>,                                        (PropertyAccess)
      Speed2D > 0 ? TrajectoryGenerationData_Moving
                  : TrajectoryGenerationData_Idle,
      <DeltaTime>,                                        (PropertyAccess)
      Trajectory,                     ← 이전 프레임 값(연속성)
      PreviousDesiredControllerYaw,   ← 컨트롤러가 향하려는 방향
      -1.0, 30, 0.1, 15 )

(Trajectory, TrajectoryCollision) = HandleTrajectoryWorldCollisions(
      self, Trajectory, true, 0.01, "TraceTypeQuery1", false, 0, "None", true, 150.0)

Trj_PastVelocity   = GetTrajectoryVelocity(Trajectory, -0.3, -0.2)
Trj_CurrentVelocity= GetTrajectoryVelocity(Trajectory,  0.0,  0.2)
Trj_FutureVelocity = GetTrajectoryVelocity(Trajectory,  0.4,  0.5)
```

### 4.1 결론

**`PoseSearchGenerateTrajectory(forCharacter)`는 캐릭터를 통째로 받아 이동 상태(속도·가속·
이동 파라미터)에서 궤적을 만드는 엔진 라이브러리 함수다. 플레이어 입력을 직접 읽지 않는다.**

→ AI가 `MoveTo`로 CMC를 구동하면 속도/가속이 채워지고, 궤적이 **동일한 경로로** 생성된다.
설계 문서 5.3절이 "최대 리스크"로 잡았던 `USoldierTrajectorySource` 자체 구현은 **불필요**하다.

### 4.2 AI 전환 시 손대야 하는 것 — 정확히 2개

| 항목 | 지금 | AI에서 |
|---|---|---|
| `PreviousDesiredControllerYaw` | 카메라 요 | **위협/조준 방향**을 AI가 공급해야 함 |
| `TrajectoryGenerationData_Moving` / `_Idle` | 카메라 조작 기준 튜닝 (`rotateTowardsMovementSpeed=10`, `maxControllerYawRate=70`) | AI 회전 특성에 맞게 재튜닝 |

`TrajectoryGenerationData`는 `FPoseSearchTrajectoryData` 구조체이고 `bendVelocityTowardsAcceleration`,
속도/가속 리매핑 커브를 갖는다 — **급선회 품질을 이 커브로 조정할 수 있다.**

### 4.3 부산물

`Trj_PastVelocity / CurrentVelocity / FutureVelocity` 3개를 궤적에서 뽑아둔다. `IsStarting`,
`IsPivoting` 같은 판정과 Chooser 입력에 쓰인다(추정). **AI가 "이 병사가 지금 출발/피벗 중인가"를
알고 싶을 때 이 값들을 그대로 읽으면 된다.**

---

## 5. 함수 그래프 지도

`EventGraph`는 껍데기(528자)이고 실질은 함수 그래프에 있다.

### 5.1 갱신 체인

```
EventBlueprintUpdateAnimation
  └ HasOwningActor 확인
     ├ Update_CVarDrivenVariables      (1558자, 콘솔변수 → 디버그/토글)
     ├ Update_PropertiesFromCharacter  (191자, 캐릭터 인터페이스 호출 → CharacterProperties)
     └ (ThreadSafe가 아니면) Update_Logic
BlueprintThreadSafeUpdateAnimation
  └ (ThreadSafe면) Update_Logic

Update_Logic
  ├ Update_Trajectory        ← 4절
  ├ Update_EssentialValues   ← 5.2
  ├ Update_States            ← 5.3
  └ if UseExperimentalStateMachine:
       Update_MovementDirection (2244자)
       Update_TargetRotation    (760자)
```

> **읽는 법**: 기본 경로에서는 `Update_MovementDirection`/`Update_TargetRotation`이 **실행되지
> 않는다.** 이 둘은 실험적 스테이트머신 전용이다.

### 5.2 `Update_EssentialValues` 요지

```
CharacterTransform_LastFrame ← CharacterTransform
CharacterTransform           ← (캐릭터 액터 트랜스폼)
RootTransform                ← GetOffsetRootTransform(OffsetRoot 노드).location
                                + rotation(roll,pitch, yaw + 90°)      ← 메시 전방축 보정
Acceleration_LastFrame / Acceleration / AccelerationAmount(= |accel| / maxAccel)
HasAcceleration              ← AccelerationAmount > 0
Velocity_LastFrame / Velocity / Speed2D(= |velocity.xy|)
HasVelocity                  ← Speed2D > 5.0
VelocityAcceleration         ← (Velocity - Velocity_LastFrame) / max(dt, 0.001)
RelativeAcceleration         ← UnrotateVector(VelocityAcceleration, ...)
LastNonZeroVelocity          ← HasVelocity일 때만 갱신
```

- **`RootTransform`이 조준 오프셋의 기준**이다(5.4). 즉 조준각은 **캡슐이 아니라 OffsetRootBone이
  만든 "시각적 루트"** 기준으로 계산된다.
- `HasVelocity` 임계 5.0, `Speed2D`는 XY 평면 속도.

### 5.3 `Update_States` 요지

```
MovementMode  ← 캐릭터 (PropertyAccess)
RotationMode  ← 캐릭터
MovementState ← IsMoving() ? NewEnumerator0(Moving) : NewEnumerator4(Idle)
Gait          ← 캐릭터
Stance        ← 캐릭터
(각각 _LastFrame 보관)
```

**전부 `_LastFrame`을 함께 유지한다** — 상태 전이 순간을 감지하려는 목적(예: `ShouldTurnInPlace`가
"직전 프레임에 Moving이었고 지금 Idle"을 조건으로 쓴다).

### 5.4 조준 오프셋 계산

```
Get_AO_Yaw()   = RotationMode에 따라 (Get_AOValue) 또는 0        ← 모드로 on/off
Get_AOValue()  = Lerp( Delta( CharacterProperties.aimingRotation , RootTransform.rotation ),
                       같은 값,
                       curve "Disable_AO" )                      ← 커브로 억제 가능
```

두 가지가 중요하다:

1. **조준각 = (조준 방향) − (시각적 루트 방향)**. 몸이 돌면 조준 오프셋이 자동으로 줄어든다.
2. **`Disable_AO`라는 애니메이션 커브로 조준 오프셋을 끌 수 있다.** 트래버설·특수 동작 클립에
   이 커브를 넣으면 그 구간만 조준이 꺼진다. **데이터가 시스템을 제어하는 깔끔한 패턴이고,
   우리도 그대로 채택할 가치가 있다.**

### 5.5 런타임 파라미터 교체 — 인과의 대표 사례

```
Get_FootPlacementPlantSettings() =
    (기본 경로)  CurrentDatabaseTags 에 "Stops" 포함 ? PlantSettings_Stops : PlantSettings_Default
    (실험 경로)  BlendStackInputs 에 "Stop" 포함 ? ...
```

**MM이 어떤 데이터베이스를 골랐는지가 발 IK 파라미터를 바꾼다.** 정지 동작 중에는 다른 플랜트
설정을 쓴다. 데이터(태그) → 시스템 동작의 연결 고리이고, 8절 인과 맵의 핵심 항목이다.

### 5.6 기타 판정 함수

```
Get_TrajectoryTurnAngle() = Delta( RotationFromXVector(Acceleration), RotationFromXVector(Velocity) )
                            ← 가속 방향과 속도 방향의 차 = 피벗 감지
ShouldTurnInPlace()       = |ΔRotation| >= 50° AND ( ... OR (지금 Idle AND 직전 Moving) )
Get_LeanAmount()          = CalculateRelativeAccelerationAmount()
                            × MapRangeClamped(Speed2D, 165→375, 0.5→1.0)
Get_OrientationWarpingWarpingSpace() = OffsetRootBoneEnabled ? "RootBoneTransform" : "ComponentTransform"
```

---

## 6. Motion Matching 스키마 — `PSS_Default`

```
sampleRate = 30,  dataPreprocessor = NormalizeWithCommonSchema,  permutations = 1
```

### 6.1 채널 1 — Trajectory (weight 1.0)

| 샘플 오프셋(초) | flags | weight |
|---|---|---|
| **−0.05** (과거) | 32 | 0.3 |
| **0.00** (현재) | 144 | 1.0 |
| **+0.35** | 160 | 1.0 |
| **+0.70** | 176 | 1.0 |
| **+1.00** | 4 | **1.5** |

- 과거 1개 + 현재 1개 + 미래 3개. **미래 1초 지점의 가중치가 가장 높다**(1.5) — 어디로 갈
  것인가가 매칭을 지배한다.
- `flags` 비트의 정확한 의미(위치/속도/방향 중 무엇을 샘플링하는지)는 **미확인**.

### 6.2 채널 2 — Group (포즈 특징)

| 서브채널 | 본 | 기준 | weight | 비고 |
|---|---|---|---|---|
| Position | `foot_l` | **originBone = `foot_r`** | 1.0 | **두 발의 상대 위치** = 스탠스 폭/스텝 위상 |
| Velocity | `foot_l` | — | 0.3 | 캐릭터 공간, normGroup `FeetVelZ` |
| Velocity | `foot_r` | — | 0.3 | 동일 |
| Heading | `pelvis` | — | 0.1 | headingAxis=Y, componentStripping=StripZ |

### 6.3 이 스키마에서 읽어야 할 것

**포즈 특징이 4개뿐이고, 전부 하체다. 상체 특징이 하나도 없다.**

- MM은 팔이 뭘 하는지 전혀 신경 쓰지 않는다 → **조준을 애디티브 레이어로 얹는 설계와 완전히
  정합**한다. 상체를 바꿔도 매칭이 흔들리지 않는다.
- 매칭의 실질은 "**두 발이 서로 어디 있고, 얼마나 빠르게 움직이며, 골반이 어디를 향하는가**"
  — 보행 위상 시그니처다.
- **스키마가 얇다는 것은 채널 추가 여지가 크다는 뜻이다.** 우리가 무기 자세·조준각·엄폐물
  근접도 같은 채널을 넣을 공간이 있다(9절).

---

## 7. Chooser 계층 — 데이터베이스 선택

```
Update_MotionMatching(Context, Node):
    ValidDatabases = EvaluateChooser(CHT_PoseSearchDatabases, self)
    SetDatabasesToSearch(Node, ValidDatabases, Get_MMInterruptMode())

Update_MotionMatching_PostSelection(Context, Node):
    CurrentSelectedAnim     = GetMotionMatchingSearchResult(Node)
    CurrentSelectedDatabase = GetMotionMatchingSearchResult(Node)
    CurrentDatabaseTags     = GetDatabaseTags(CurrentSelectedDatabase)   ← 5.5절이 이걸 쓴다
```

### 7.1 최상위 Chooser — LOD만 본다

`CHT_PoseSearchDatabases`: **컬럼 1개**
```
FloatRangeColumn ← MMDatabaseLOD    rows: [0..0], [1..1], [2..2]
```

→ **LOD 0 / 1 / 2** 세 행. 각 행이 하위 Chooser(`_Dense` / `_Sparse` / `_Extreme_Sparse`)를
반환한다(추정 — 폴더 구성과 정확히 일치).

> **이것이 설계 문서 12.3절의 3티어 LOD와 같은 구조다.** Epic이 이미 "데이터베이스 밀도로
> LOD를 만드는" 방식을 구현해 두었고, 우리 T0/T1/T2에 그대로 대응시킬 수 있다.

### 7.2 하위 Chooser — 상태 조합표

`CHT_PoseSearchDatabases_Dense`: **컬럼 4개 × 행 7개**

```
MovementMode × Stance × MovementState × Gait   →   데이터베이스 집합
```

각 컬럼은 `EnumColumn`이고 `MatchEqual` 또는 `MatchAny`를 쓴다. 예: Gait 컬럼의 행별 값이
`MatchAny / Walk / Run / Sprint / MatchAny ...` 형태.

**확인된 enum 대응**

| enum | 값 |
|---|---|
| `E_MovementMode` | OnGround / InAir / Sliding / Traversing / Ragdoll / Flying |
| `E_Stance` | `NewEnumerator0`=Stand, `NewEnumerator1`=Crouch |
| `E_MovementState` | `NewEnumerator0`=Moving, `NewEnumerator4`=Idle |
| `E_Gait` | 0=Walk, 1=Run, 2=Sprint |
| `E_RotationMode` | 0=OrientToMovement, 1=Strafe, (2=Aim) |
| `E_MovementDirection` | F / B / LL / LR / RL / RR |

### 7.3 우리에게 중요한 결론

**데이터베이스 선택은 "이산 상태 조합표"다. 축을 하나 추가하려면 컬럼을 하나 추가하면 된다.**

무기 자세(정조준/허리/맹목/내림)를 추가하려면 `WeaponPosture` 컬럼 하나 + 행 확장. **코드 수정
없이 데이터만으로 확장된다.** 이건 우리 설계에 매우 유리한 구조다.

---

## 8. 캐릭터 ↔ ABP 계약 — `S_CharacterPropertiesForAnimation`

**GASP 전체에서 캐릭터가 ABP에 넘기는 유일한 통로다.**

```
inputState : S_PlayerInputState { wantsToSprint, wantsToWalk, wantsToStrafe,
                                  wantsToAim, wantsToCrouch }        ← 의도(결정)
movementMode          : E_MovementMode
stance                : E_Stance                                      ← 이산(Stand/Crouch)
rotationMode          : E_RotationMode
gait                  : E_Gait
movementDirection     : E_MovementDirection
actorTransform        : Transform
velocity              : Vector
inputAcceleration     : Vector
currentMaxAcceleration / currentMaxDeceleration : float
orientationIntent     : Rotator        ← 몸이 향하려는 방향
aimingRotation        : Rotator        ← 조준 방향        ★ 몸방향과 분리돼 있다
justLanded / landVelocity
steeringTime
groundNormal / groundLocation
basedMovementDelta
```

### 8.1 캐릭터가 이 구조체를 채우는 방법 (`Get_PropertiesForAnimation`)

```
inputState        ← CharacterInputState 변수
movementMode      ← CharacterMovement (select)
stance            ← IsCrouching(CMC) ? Crouch : Stand
rotationMode      ← bOrientRotationToMovement ? OrientToMovement : Strafe
gait              ← Movement.Gait 변수
actorTransform    ← GetActorTransform
velocity          ← CMC.GetVelocity
inputAcceleration ← CMC.GetCurrentAcceleration
currentMaxAccel   ← CMC.GetMaxAcceleration
currentMaxDecel   ← CMC.GetBrakingDecelerationWalking
orientationIntent ← GetActorRotation
aimingRotation    ← IsLocallyControlled ? GetControlRotation : GetBaseAimRotation
justLanded / landVelocity ← Movement 변수
groundNormal/Location ← CMC.GetCurrentFloor 의 HitResult
```

### 8.2 **AI 통합 지점 — 이 문서에서 가장 실용적인 결론**

| 우리가 줘야 할 것 | 어떻게 |
|---|---|
| **조준 방향** | **AIController의 컨트롤 로테이션**을 설정하면 `aimingRotation`이 자동으로 따라온다. `SetFocus`/`SetControlRotation`이 조준 체인 전체를 구동한다 |
| **몸 방향 의도** | `GetActorRotation` → CMC의 `bOrientRotationToMovement` / `bUseControllerDesiredRotation` 플래그로 제어 |
| **회전 모드**(이동방향 정렬 ↔ 스트레이프) | 같은 CMC 플래그 하나 |
| **자세·gait·의도** | `inputState`를 AI 결정으로 채운다. **플레이어 입력 구조체를 AI 출력 구조체로 바꾸는 것이 전부** |
| **궤적 회전** | `PreviousDesiredControllerYaw` (4.2절) |

즉 **`inputState`를 AI가 채우고 컨트롤 로테이션을 AI가 돌리면, 나머지 파이프라인은 그대로
동작한다.** 이것이 설계 문서 11절 명령 인터페이스가 최종적으로 내려앉는 지점이다.

---

## 9. 인과 맵 — "X를 건드리면 Y가 바뀐다"

| 건드리는 것 | 직접 영향 | 최종 결과 |
|---|---|---|
| `MMDatabaseLOD` (0/1/2) | 최상위 Chooser 행 → Dense/Sparse/Extreme_Sparse | 매칭 품질 ↔ 성능. **12절 LOD 티어의 손잡이** |
| `MovementMode`/`Stance`/`MovementState`/`Gait` | 하위 Chooser 행 → 검색 대상 DB 집합 | 어떤 동작군에서 포즈를 고를지 |
| `TrajectoryGenerationData_Moving`/`_Idle` | `PoseSearchGenerateTrajectory` | 궤적 모양 → **선택되는 포즈 전체**. 급선회·정지 품질 |
| `PreviousDesiredControllerYaw` | 궤적의 회전 성분 | **turn-in-place / 피벗 발동 여부** |
| `aimingRotation` (컨트롤 로테이션) | `Get_AOValue` | 상체 조준 오프셋 |
| `RotationMode` | `Get_AO_Yaw` 게이팅 | 조준 오프셋 on/off |
| 애니메이션의 **`Disable_AO` 커브** | `Get_AOValue`의 Lerp | 그 클립 구간만 조준 억제 |
| 애니메이션의 **`contact_l`/`contact_r` 커브** | `RemapCurves`가 `(1−c)×100`로 변환 → `FootPlacement.speedCurveName` | **발 심기 타이밍.** 커브가 없는 클립은 발 IK가 오작동한다(3.3b절) |
| **DB 태그에 `"Stops"`** | `Get_FootPlacementPlantSettings` | 정지 중 발 고정 파라미터 교체 |
| `OffsetRootBoneEnabled` | `RootTransform` 계산 + `Get_OrientationWarpingWarpingSpace` | 조준 기준 공간, 워핑 공간 |
| `OffsetRootBone`의 Halflife / MaxTranslationError | 메시-캡슐 분리량 | 관성감. 크면 미끄러지는 느낌 |
| `BlendListByInt.ActiveChildIndex` | 로코모션 소스 | MM ↔ 실험 스테이트머신 |
| `BlendListByBool.bActiveValue` | 조준 오프셋 ↔ IdentityPose | 조준 레이어 자체 on/off |
| `PoseHistory.collectedBones/Curves` | 매칭 입력 | 무엇을 "같은 포즈"로 볼지 |
| 스키마 채널 weight | 매칭 비용 | 궤적 추종 ↔ 포즈 연속성의 균형 |

---

## 10. 우리 층의 삽입 지점

설계 문서와 `2026-09-02` 논의에서 정한 합성 순서를 이 그래프에 대응시키면:

| 우리 층 | 삽입 위치 | 방식 | 위험 |
|---|---|---|---|
| **무기 자세 앵커** (정조준/허리/맹목/내림) | ② 애디티브 구간, 조준 오프셋 **앞** | 애디티브 추가 | 낮음. 기존 체인 확장 |
| **조준 오프셋 (라이플)** | ② `BlendSpacePlayer_1` **교체/확장** | 에셋 교체 + Chooser로 무기별 선택 | 낮음. **GASP가 자리를 이미 만들어놨다** |
| **자세 높이 축 (Stand↔Crouch 연속)** | ④ IK 구간, `FootPlacement` **앞** | Control Rig (골반 하강 + 다리 적응) | **중간**. MM이 고른 보폭과 어긋날 수 있음(P1 실측) |
| **안정화 IK (목표, gain<1)** | ④ IK 구간 진입 직후 | Control Rig | 중간 |
| **교란 (호흡·떨림·반동 잔여)** | 안정화 IK **뒤**, 결합 IK **앞** | Control Rig 내부에서 처리 권장(아래) | 낮음 |
| **결합 IK (왼손↔총, 발↔지면)** | ④ `FootPlacement`/`LegIK`와 같은 구간, 뒤쪽 | Control Rig + 기존 노드 | 낮음 |
| **피격 물리** | ⑤ 이후 또는 별도 경로 | PhysicsControl | 2차 |

### 10.1 공간 문제 — 설계에서 놓쳤던 것

우리 파이프라인은 "**목표 IK → 교란 → 결합 IK**" 순서를 요구한다. 그런데 GASP 그래프에서
**애디티브는 로컬/메시 공간(②)이고 IK는 컴포넌트 공간(④)**이다. 교란(호흡 등)을 애디티브로
만들면 ②에 들어가는데, 그러면 목표 IK(④)보다 **앞**에 오게 되어 순서가 뒤집힌다.

**해결: 목표 IK와 교란을 하나의 Control Rig 안에서 순서대로 처리한다.**

```
④ IK 구간
   LocalToComponentSpace
     → [CR: 조준 정렬(gain<1) → 호흡/떨림 교란 → 총구 최종 오프셋 계산]
     → 자세 높이 CR
     → FootPlacement → LegIK
     → [CR: 왼손 그립 결합]
   ComponentToLocalSpace
```

Control Rig은 내부 실행 순서를 우리가 정하므로 공간 변환 비용 없이 규칙을 지킬 수 있다.
**교란을 애디티브 블렌드스페이스로 만들지 말고 Control Rig 연산으로 만들 것** — 이것이 이
분석에서 나온 구체적 설계 제약이다.

---

## 11. 확장 vs 재구축 판정

### 11.1 판정 기준과 결과

| 기준 | 결과 |
|---|---|
| 우리 층을 끼워넣을 **깨끗한 지점이 있는가** | ✅ 있다. 애디티브 구간(②)과 IK 구간(④)이 명확히 분리돼 있고, 조준 오프셋 자리는 이미 존재한다 |
| 기존 노드 **순서를 재배치해야 하는가** | ❌ 아니다. 10.1의 공간 문제도 IK 구간 **내부**에서 해결되며 기존 노드 순서를 안 건드린다 |
| 확장 축이 **데이터로 추가되는가** | ✅ Chooser는 컬럼 추가, 스키마는 채널 추가, DB는 항목 추가. 전부 데이터 |
| 이해하지 못한 채 남는 부분이 **크리티컬한가** | ⚠️ 스테이트머신 내부(실험 경로)는 미확인이나 **기본 경로가 아니다**. 우리는 MM 경로만 쓴다 |

### 11.2 결론 — **확장(복제 후 확장)을 권한다**

근거:

1. **삽입 지점이 이미 설계돼 있다.** 특히 조준 오프셋 자리(`BlendListByBool → DeadBlending →
   ApplyMeshSpaceAdditive_0`)는 우리가 필요한 것과 정확히 같은 형태다.
2. **확장이 전부 데이터 축 추가로 표현된다**(Chooser 컬럼 / 스키마 채널 / DB 항목).
   구조 변경이 아니다.
3. **재구축의 이득이 작다.** 우리가 바꾸고 싶은 순서(목표IK→교란→결합IK)가 IK 구간 내부에서
   해결되므로, 그래프를 새로 짜서 얻을 자유도가 별로 없다.
4. **품질 재현 비용이 크다.** 3절의 `FootPlacement` 설정값 30여 개, 스키마 가중치, OffsetRootBone
   파라미터는 전부 튜닝의 산물이다. 새로 짜면 이걸 다시 맞춰야 한다.

**단, 사용자가 제기한 우려("결국 다 이해해야 한다")는 유효하며 이 문서가 그 답이다.** 확장을
택하되 **블랙박스로 두지 않는다** — 이 문서의 3·6·7·9절이 곧 "우리가 이해한 범위"이고,
남은 미확인 항목은 13절에 명시했다.

### 11.3 실행 규칙

```
1. GASP의 SandboxCharacter_CMC_ABP / SandboxCharacter_CMC 를 복제해서 SoldierLab_* 로 시작
2. 원본은 지우지 않는다 — 같은 레벨에서 A/B 비교용으로 남긴다
3. 확장은 다음 순서로만 한다:
     ① 데이터(Chooser 컬럼 / 스키마 채널 / DB 항목)
     ② 애디티브 레이어 추가
     ③ IK 구간 내부 Control Rig 추가
   그래프 노드의 **기존 순서를 바꿔야 할 일이 생기면 그때 재구축을 재검토**한다
4. 원본에서 값 하나를 바꿀 때마다 9절 인과 맵에 항목을 추가한다
```

---

## 12. 성능 관련 관찰

- `PoseHistory`가 IK **뒤**에 있으므로, IK를 LOD로 끄면 매칭 입력도 함께 변한다.
  **LOD 티어 간 매칭 일관성**에 영향이 있을 수 있다 — 12.3절 팝핑 대책(D5)과 연결.
- `MMDatabaseLOD`가 이미 존재하므로 우리 T0/T1/T2를 여기에 직접 매핑할 수 있다.
- `Update_Logic`이 `BlueprintThreadSafeUpdateAnimation` 경로로 돌 수 있다
  (`UseThreadSafeUpdateAnimation` 변수). **45명 규모에서는 반드시 스레드세이프 경로를 쓸 것.**

---

## 13. 미확인 항목 (다음에 확인할 것)

| # | 항목 | 확인 방법 |
|---|---|---|
| U1 | **스테이트머신 내부 상태/전환**, Orientation Warping 노드 2개의 정확한 위치 | 에디터에서 수동 확인. MCP 경로 미지원 |
| U2 | 프로퍼티 바인딩의 정확한 대응 (`Get_*` → 노드 핀) | 에디터에서 각 노드 핀의 바인딩 표시 확인 |
| U3 | Trajectory 채널 `flags` 비트 의미 (32/144/160/176/4) | 엔진 소스 `PoseSearchFeatureChannel_Trajectory` 확인 |
| U4 | 하위 Chooser 7행의 정확한 조합과 반환 DB | `CHT_PoseSearchDatabases_Dense`의 results 배열 조회 |
| U5 | `Dense`/`Sparse`/`Extreme_Sparse`가 클립 수 차이인지 샘플링 차이인지 | 각 DB의 항목 수 비교 |
| U6 | `Relaxed` 티어의 성격 (LOD인가 스타일인가) | 5.7 업데이트의 "locomotion style"과 대조 |
| ~~U7~~ | ~~`RemapCurves`가 무엇을 리맵하는지~~ | **✅ 해결 — 3.3b절.** `contact_l/r = (1−c)×100`, 발 접지 구동원 |
| ~~U2~~ | ~~프로퍼티 바인딩 대응~~ | **✅ 해결 — 14절**(사용자 에디터 확인, 2026-09-03) |
| U1 | 스테이트머신 내부 / Orientation Warping 위치 | **⚠️ 부분 해결 — 14.3절.** `AnimationBlendStackGraph` 안에 있음이 확인됨. 어느 노드 소속인지는 미확정 |

U1·U4는 다음 작업 착수 전에 채우는 것이 좋다. 나머지는 필요할 때 확인해도 무방하다.

### 13.1 이번 분석에서 새로 생긴 작업

| # | 작업 | 근거 |
|---|---|---|
| **W1** | 자산 반입 파이프라인에 **접지 커브 생성 단계 추가**(`UMotionExtractorModifier`) | 3.3b절 [P]. `../assets/2026-09-02_asset_supply_and_collaboration.md` 4절 갱신 필요 |
| **W2** | 교란(호흡·떨림)을 **애디티브가 아니라 Control Rig 연산으로** 구현 | 10.1절 공간 문제 |
| **W3** | `AIController`가 **컨트롤 로테이션으로 조준을 구동**하는 배선 | 8.2절 |
| **W4** | `TrajectoryGenerationData_Moving/_Idle` **AI용 재튜닝** | 4.2절 |
| **W5** | `Disable_AO` 커브 패턴을 우리 무기 시스템에도 채택 | 5.4절 |

---

## 14. 에디터 실측 결과 (2026-09-03, 사용자 확인)

MCP로 못 읽었던 항목을 에디터에서 직접 확인한 결과. **분석 본문의 일부 추정이 정정된다.**

### 14.1 프로퍼티 바인딩 (U2 해결) [A]

| 노드 | 핀 | 실제 바인딩 | 본문 추정과 비교 |
|---|---|---|---|
| `BlendSpacePlayer_1` (`BS_Neutral_AO_Stand`) | **`yaw`** | `Get_AOValue.X` | ⚠️ 핀 이름이 `X`/`Y`가 아니라 **`yaw`/`pitch`**. `Get_AOValue`가 **벡터**를 반환하고 X=yaw, Y=pitch |
| 동일 | **`pitch`** | `Get_AOValue.Y` | |
| `Blend Poses by int` | `ActiveChildIndex` | **`LocomotionSetup`** | ❌ **본문 추정(`UseExperimentalStateMachine`)이 틀림.** 14.2절 참고 |
| `Blend Poses by bool` | `bActiveValue` | **`Enable_AO`** | 조준 오프셋 on/off 변수 |
| `OffsetRootBone` | `bClampToTranslationVelocity` | **`IsMoving`** | 나머지 핀은 `Get_OffsetRoot*` (추정대로) |
| `Foot Placement` / `Motion Matching` | — | `Get_*` 함수들 (추정대로) | ✅ |

### 14.2 ★ `DDCVar.ExperimentalStateMachine.Enable`은 효과가 없다 [A]

`Update_CVarDrivenVariables`의 마지막 두 줄이 앞선 설정을 **덮어쓴다**:

```
SetUseExperimentalStateMachine( cvar_ExperimentalStateMachine OR tag... )   ← 설정
...
SetLocomotionSetup( DDCVar.LocomotionSetupCMC )
SetUseExperimentalStateMachine( ToBoolean(LocomotionSetup) )                ← 덮어씀
```

그리고 14.1에서 확인된 대로 **`Blend Poses by int`의 로코모션 경로 선택도 `LocomotionSetup`이
결정한다.**

> **결론: 로코모션 경로(MM ↔ 실험 스테이트머신)를 바꾸는 실제 스위치는
> `DDCVar.LocomotionSetupCMC` (int)다.** `DDCVar.ExperimentalStateMachine.Enable`은 무시된다.
>
> 사용자 A2 실험에서 "차이를 못 느꼈다"의 원인이 이것이다 — **경로가 실제로 안 바뀌었다.**

### 14.3 Orientation Warping 위치 (U1 부분 해결) [B]

에디터 Ctrl+F 검색 결과 Orientation Warping 노드는 **`AnimationBlendStackGraph_0`** 안에 있다.
`My Blueprint` 탭 계층에서 같은 이름의 그래프가 **2개** 보인다:

```
Animation graphs
  ├ AnimGraph        └ AnimationBlendStackGraph_0     ← ①
  └ State Controller └ AnimationBlendStackGraph_0     ← ②
```

`AnimationBlendStackGraph`는 **BlendStack 노드의 내부 그래프**다(BlendStack이 재생하는 각
애니메이션에 대해 실행되는 그래프). 즉 **워핑은 "선택된 클립 하나하나에 적용되는 후처리"로
배치돼 있다.**

**미확정 [C-20]**: ①이 `MotionMatching_0`의 내부 블렌드스택인지, `BlendStack_3`(실험 경로)의
것인지. **이것이 확정되어야 "기본 MM 경로에 워핑이 있는가"가 결정된다.**

> ⚠️ **본문 2.1절의 "실험 SM 경로에만 Orientation Warping이 있다"는 서술은 [C-20]이 확정될
> 때까지 보류한다.** MotionMatching 노드도 내부에 블렌드스택을 갖기 때문에, ①이 MM 소속이면
> **기본 경로에도 워핑이 있는 것**이 된다.
>
> **확인 방법**: AnimGraph에서 `Motion Matching` 노드를 더블클릭 → 내부 그래프가 열리면
> 그것이 ①이다.

### 14.4 ★ `OffsetRootBone`은 연출 노드가 아니라 조준 체계의 기준이다 [A]

**증상**(A4 실험): `a.animnode.offsetrootbone.enable 0`으로 끄면 **캐릭터가 +X를 향하는 정도에
따라 발이 망가진다.** −X를 향하면 정상.

**원인**: `Update_EssentialValues`(5.2절)가 `RootTransform`을 만들 때 **yaw에 +90°를 더한다**
(메시 전방축 보정). OffsetRootBone이 꺼지면 이 경로를 못 타고 `CharacterTransform`으로 폴백하는데,
그쪽엔 +90° 보정이 없다.

```
AOValue = Delta( aimingRotation , RootTransform.rotation )
                                   ↑ 90° 어긋남
→ 조준 오프셋 값이 블렌드스페이스 유효 범위(yaw ±135°)를 벗어남
→ BS_Neutral_AO_Stand는 메시공간 애디티브라 상체만이 아니라 전신에 적용됨
→ 다리까지 뒤틀림. 오차가 고정 +90°라 바라보는 방향에 따라 범위 안/밖이 갈림
```

**설계 함의 [A]**

- `OffsetRootBone`이 공식 문서상 **실험적**이라 "빼는 것"을 검토했으나(설계 문서 3.2절 주의사항),
  **뺄 수 없다.** 빼려면 조준 오프셋의 기준 공간을 새로 정의하고 +90° 규약을 직접 처리해야 한다
- 우리 리그로 옮길 때 **이 +90° 규약을 반드시 승계**해야 한다. 메시 전방축이 다르면 값도 달라진다
- 포즈 명세 6.3절의 "조준각 = 조준 방향 − 시각적 루트 방향"에서 **"시각적 루트"가 바로 이것**이다

### 14.5 발 재정렬 각도 = 60° (실측) [A]

`DDCvar.DrawCharacterDebugShapes 1` 관찰 결과, **조준 방향을 돌리면 발이 60° 간격으로 재배치**된다.

이는 `FootPlacement.plantSettings.unplantAngle = 60`(3.1절)과 정확히 일치한다.

**포즈 명세 6.3절 "조준 한계각과 재정렬"의 실측 근거이자 [C-6]의 첫 번째 답이다.**
GASP 기본값 기준 **재정렬은 60°에서 일어난다.** 우리 병사는 견착 자세라 상체 비틀기 여유가
더 작으므로 이보다 작게 잡아야 할 가능성이 높다(P1 튜닝 대상).

### 14.6 LOD 티어 체감 차이가 작다 [B]

`DDCvar.MMDatabaseLOD 0/1/2` 전환 시 사용자가 눈에 띄는 차이를 못 느꼈다.

**해석**: Dense ↔ Sparse ↔ Extreme_Sparse의 품질 차이가 일반적인 보행에서는 미미하다.
**우리 12.3절 LOD 계획에 유리한 신호다** — T1/T2로 내려도 시각적 손실이 작다는 뜻.

> ⚠️ 다만 **급선회·정지 같은 전환 상황에서의 차이는 아직 안 봤다.** 데이터 밀도의 차이는
> 정상상태 루프가 아니라 전환에서 드러날 가능성이 높다. [C-21]로 등록.

---

## 15. 정정 — 2026-09-03 에디터 확인 2차

### 15.1 ★★ Orientation Warping은 **기본 MM 경로 안에 있다** [A]

**확인 방법**: AnimGraph의 `Motion Matching` 노드를 더블클릭 → `AnimationBlendStackGraph_0`가
열리고, **그 안에 Orientation Warping 노드가 있다.**

즉 14.3절의 [C-20]이 해결되었고, **본문 2.1절-C와 7절의 "실험 SM 경로에만 워핑이 있다"는
서술은 틀렸다. 정정한다.**

```
MotionMatching 노드
   └ AnimationBlendStackGraph_0        ← 선택된 클립 하나하나에 적용되는 내부 그래프
        └ Orientation Warping          ← 여기 있다
```

**구조적 의미**: `AnimationBlendStackGraph`는 BlendStack이 재생하는 **각 애니메이션에 대해
실행되는 그래프**다. 즉 워핑은 "MM이 고른 클립에 대한 후처리"로 배치돼 있다. 최상위 AnimGraph를
아무리 훑어도 안 보였던 이유가 이것이다.

#### 설계에 미치는 영향 (큼)

| 항목 | 이전 판단 | 정정 후 |
|---|---|---|
| GASP의 스트레이프 품질 출처 | "순전히 데이터(1,450 클립)" | **데이터 + Orientation Warping의 합작** |
| 견착 클립 필요량 | 데이터로만 커버해야 하므로 8방향 필요 가능성 높음 | **워핑이 이미 파이프라인에 있으므로 방향 수를 줄일 여지가 실재한다** |
| P0-2의 성격 | 워핑 노드를 우리가 새로 삽입해서 시험 | **이미 있는 워핑의 파라미터를 조정하며 시험** — 훨씬 쉬움 |
| `Get_StrafeYawRotationOffset` / `StrafeOffsetCurveContainer` | 실험 경로 전용으로 추정 | **MM 경로에서도 쓰일 가능성** — 재확인 필요 [C-22] |

> **[C-5](견착 워핑 한계각) 전망이 밝아졌다.** "워핑을 새로 붙여야 하는가"가 아니라
> "이미 있는 워핑이 견착 자세에서 어디까지 버티는가"로 질문이 바뀐다.

#### 다음에 확인할 것 [C-22]

`AnimationBlendStackGraph_0` 내부의 전체 노드 구성. 특히:
- Orientation Warping의 파라미터 바인딩(무엇이 각도를 주는가)
- **Stride Warping / Slope Warping도 같이 있는가**
- 워핑 앞뒤에 다른 노드가 있는가

MCP로는 이 그래프에 접근이 안 된다(경로 해석 실패). 에디터에서 열어서 노드 구성을 확인해야 한다.

### 15.2 Chooser 구조 정정 — 각 행은 **중첩 Chooser**를 반환한다 [A]

본문 7.2절이 "각 행이 데이터베이스 집합을 반환한다"고 서술했으나, **실제로는 한 단계 더 있다.**

`CHT_PoseSearchDatabases_Dense`의 실제 구성 (에디터 확인):

| Result (중첩 Chooser 이름) | Movement Mode | Stance | Movement State | Gait |
|---|---|---|---|---|
| **Stand Idles** | = OnGround | = Stand | = Idle | **Any** |
| **Stand Walks** | = OnGround | = Stand | = Moving | = Walk |
| **Stand Runs** | = OnGround | = Stand | = Moving | = Run |
| **Stand Sprint** | = OnGround | = Stand | = Moving | = Sprint |
| **InAir** | = InAir | **Any** | **Any** | **Any** |
| **Crouch Idle** | = OnGround | = Crouch | = Idle | **Any** |
| **Crouch Moving** | = OnGround | = Crouch | = Moving | **Any** |

- **`Result` 컬럼의 타입이 `Nested Chooser`다.** 각 행은 PSD를 직접 반환하지 않고 **같은 에셋
  안에 정의된 중첩 Chooser**를 반환하며, 실제 데이터베이스 선택은 거기서 한 단계 더 갈린다
  (행 옆 `Edit` 버튼으로 진입).
- 에디터 우하단 `Nested Choosers` 패널에 7개가 모두 나열된다.

#### 읽어야 할 것 2가지

1. **계층이 3단이다**
   ```
   CHT_PoseSearchDatabases            ← LOD (0/1/2)
     └ CHT_..._Dense                  ← MovementMode × Stance × MovementState × Gait (7행)
         └ Nested Chooser              ← 여기서 실제 PSD 선택 (조건 미확인 [C-23])
   ```
   우리가 무기 자세 축을 추가할 때 **어느 단(段)에 넣을지가 선택지가 된다** — 2단에 컬럼을
   추가하거나, 3단(중첩 Chooser)에서 갈라내거나.

2. **Stand와 Crouch의 비대칭**
   - Stand는 gait로 4분할(Idle/Walk/Run/Sprint)
   - **Crouch는 gait 구분이 없다**(Idle/Moving 2분할, Gait=Any)

   즉 **웅크린 이동은 보행/구보를 구분하지 않는다.** 포즈 명세 6.2절에서 "자세 높이가 최대
   이동속도를 제한한다"고 적은 것과 정합하지만, 우리가 견착 자세를 추가할 때 **Crouch 쪽 gait
   분할이 필요한지**는 별도 판단이 필요하다.

#### [C-23] 중첩 Chooser의 내부 조건

각 중첩 Chooser(`Stand Walks` 등)가 어떤 조건으로 실제 PSD(`PSD_Dense_Stand_Walk_Loops` /
`_Starts` / `_Stops` / `_Pivots`)를 고르는지 미확인. **`MovementDirection`이나 `IsStarting`/
`IsPivoting` 류가 쓰일 것으로 추정**되나 확인 필요.

이건 우리가 견착 DB를 추가할 때 **그대로 복제해야 하는 구조**라 중요도가 높다.

### 15.3 중첩 Chooser 내부 ([C-23] 해결) [A]

`CHT_PoseSearchDatabases_Dense > Stand Idles`를 열어 확인한 실제 구성:

| Result (실제 PSD) | Speed 2D | JustLanded_Light | JustLanded_Heavy | ShouldTurnInPlace |
|---|---|---|---|---|
| `PSD_Dense_Stand_Idles` | **(0.0, 20.0)** | False | False | False |
| `PSD_Dense_Stand_Walk_Stops` | **(20.0, ∞)** | False | False | Any |
| `PSD_Dense_Stand_Run_Stops` | **(100.0, ∞)** | False | False | Any |
| `PSD_Dense_Stand_Sprint_Stops` | **(550.0, ∞)** | False | False | Any |
| `PSD_Dense_Stand_Idle_Lands_Light` | (−∞, ∞) | **True** | False | Any |
| `PSD_Dense_Stand_Idle_Lands_Heavy` | (−∞, ∞) | False | **True** | Any |
| `PSD_Dense_Stand_TurnInPlace` | (−∞, ∞) | False | False | **True** |

#### 발견 ① — Chooser는 **복수**를 반환하고, 범위가 일부러 겹친다 ★★

`(20,∞)` · `(100,∞)` · `(550,∞)`이 서로 겹친다. 첫 매치만 반환한다면 2행이 3·4행을 가려서
`Run_Stops`/`Sprint_Stops`가 영영 안 쓰인다. 그런데 실제로는 그렇지 않다 —

```
Update_MotionMatching:
    ValidDatabases = EvaluateChooser(CHT_PoseSearchDatabases, self)   ← 복수형
    SetDatabasesToSearch(Node, ValidDatabases, ...)                   ← 복수형
```

ABP 바이너리에도 **`EvaluateObjectChooserBaseMulti`** 함수 참조가 있다.

> **Chooser는 조건을 만족하는 모든 행을 반환하고, MM은 그 합집합에서 최적 포즈를 고른다.**

즉 속도 300일 때 `Walk_Stops`와 `Run_Stops`가 **둘 다 후보에 들어가고**, MM이 궤적·포즈 비용으로
더 맞는 쪽을 고른다. **속도가 높을수록 쓸 수 있는 정지 데이터가 누적적으로 늘어나는 구조다.**

#### 발견 ② — "Stand Idles"는 이름과 달리 "서서 안 움직이는 **맥락** 전체"다

`MovementState = Idle`이라도 실제 속도는 아직 높을 수 있다(감속 중). 그래서 이 중첩 Chooser는
정지 계열 전부를 담는다: **진짜 idle + 속도별 정지 동작 + 착지(경/중) + 제자리 회전.**

2단(`_Dense`)이 "큰 맥락"을, 3단(중첩)이 "그 맥락 안의 세부 + 이벤트"를 나눈다.

| 단 | 축의 성격 | 실제 컬럼 |
|---|---|---|
| 1단 `CHT_PoseSearchDatabases` | **성능 LOD** | `MMDatabaseLOD` |
| 2단 `_Dense` 등 | **큰 맥락(이산 상태)** | MovementMode × Stance × MovementState × Gait |
| 3단 중첩 Chooser | **세부 + 이벤트(연속값·bool)** | Speed2D 범위, JustLanded_*, ShouldTurnInPlace |

**속도 임계값**: 20 / 100 / 550 (Walk / Run / Sprint 정지 경계)

#### 우리 설계에 미치는 영향 [A]

**(가) 무기 자세 축은 2단에 컬럼으로 추가한다**

무기 자세(Lowered / LowReady / ADS)는 속도나 이벤트가 아니라 **큰 맥락**이다. 따라서
`_Dense`의 컬럼으로 추가하는 것이 구조에 맞다.

```
MovementMode × Stance × MovementState × Gait × [WeaponPosture]   ← 컬럼 1개 추가
```

행 수는 늘지만 **코드 변경이 없다.** 포즈 명세 6.4절의 판단이 확인되었다.

**(나) ★ 복수 반환을 "점진적 폴백"으로 쓴다 — 조달 부족의 완충 장치**

Chooser가 복수를 반환한다는 성질을 이용하면, **견착 데이터가 부족한 상황에서 총내림 데이터를
후보에 함께 넣을 수 있다.**

```
행 1: WeaponPosture=ADS, 이동방향 전방       → PSD_Rifle_ADS_Walk_F        (견착 데이터)
행 2: WeaponPosture=ADS, 이동방향 측/후방    → PSD_Rifle_ADS_Walk_F        (있는 것)
                                             + PSD_Lowered_Walk_LR/B      (총내림 보충)
```

MM이 궤적·포즈 비용으로 더 맞는 쪽을 고르므로, **견착 클립이 없는 각도에서는 자연히 총내림
클립이 선택되고 상체는 조준 오프셋이 덮는다.** 완벽하진 않지만 "아예 데이터가 없어서 미끄러지는"
것보다 훨씬 낫다.

> 이는 `../assets/2026-09-02_asset_supply_and_collaboration.md` 5절 **A안(요구 수준을 낮추고 연출로
> 흡수)의 구체적 구현 수단**이다. 데이터만으로 표현되고 코드가 필요 없다.
> 품질은 실측 대상 — **[C-24]**로 등록.

**(다) 3단의 이벤트 bool 패턴을 그대로 답습한다**

`ShouldTurnInPlace`, `JustLanded_*`처럼 **"순간적 상황"을 bool로 만들어 3단에서 분기**하는 패턴은
우리에게도 그대로 필요하다:

```
ShouldRealignBody   (포즈 명세 6.3절 재정렬, 60° 초과)
JustSuppressed      (근접 탄착)
JustHit_Light / _Heavy   (피격 강도 — 포즈 명세 6.7절)
IsBlindFiring
```

**포즈 명세 6.7절의 "피격 강도별 DB 스왑"이 바로 이 자리에 들어간다.**

---

## 16. `AnimationBlendStackGraph_0` 내부 ([C-22] 해결) — MM 후처리 체인 [A]

`MotionMatching` 노드 더블클릭으로 열리는 내부 그래프. **MM이 고른 클립 하나하나에 적용되는
후처리**다.

```
[BlendStack Input]
  → Local To Component
  → Orientation Warping
  → Reset Root Transform (Alpha 1.0)
  → Steering            (일반 이동용)
  → Steering            (제자리 회전 전용)
  → Component To Local
  → Output Pose
```

### 16.1 Orientation Warping — 입력 배선

| 핀 | 소스 |
|---|---|
| `Alpha` | **`Get Curve Value from Animation`(커브명 `Enable_Warping`)** ← 현재 블렌드스택 클립 + 재생시간 |
| `Locomotion Direction` | **`Last Non Zero Velocity`** |
| `Warping Space` | `Get_OrientationWarpingWarpingSpace()` → OffsetRootBone 켜짐이면 `RootBoneTransform`, 아니면 `ComponentTransform` |
| `Current Anim Asset` / `Time` | 현재 블렌드스택 클립/시간 |
| `Target Time` | 0.0 |

### 16.2 ★★ Epic의 주석 — C-5의 직접적인 답 [A]

그래프에 Epic이 남긴 주석 원문(요지):

> Orientation Warping(**"Strafe Warping"이 더 정확한 표현**)을 모션 매칭 출력에 적용한다.
> 이동 방향에 따라 발이 다른 방향으로 움직이게 만들어서, **전진 보행 하나로 여러 각도의
> "스트레이프"를 만들 수 있고 발 미끄러짐을 줄인다.**
>
> **현재 애니메이션이 직선으로 움직이지 않을 때 오리엔테이션 워핑에 문제가 있다. 그래서
> 애님 커브를 써서 동작이 직선인 구간에서만 워핑을 켠다.** 향후 릴리스에서 고쳐질 예정.

#### 이것이 확정하는 것

| | 결론 |
|---|---|
| **워핑은 실제로 "전진 클립 → 임의 각도 스트레이프"를 한다** | 우리 계획의 전제가 맞다 |
| **단 직선 구간에서만 동작한다** | `Enable_Warping` 커브로 게이팅된다 |
| **곡선·전환 구간에서는 워핑이 꺼진다** | **start / stop / pivot / turn-in-place는 워핑으로 못 메운다** |
| Epic도 알려진 결함으로 표기 | 향후 개선 예정이나 현재는 제약 |

> ### 조달 계획의 정밀화 [A]
>
> "적은 방향 클립 + 워핑" 전략이 **어디까지 유효한지가 확정됐다.**
>
> | 카테고리 | 워핑이 커버하는가 | 결론 |
> |---|---|---|
> | **정상상태 루프**(직선 이동) | ✅ **커버함** | **견착 루프는 전방 위주 소수 클립으로 충분** |
> | **start / stop / pivot / turn** | ❌ **커버 못 함**(직선이 아님) | **데이터가 반드시 필요.** 여기가 진짜 비용 |
>
> 이는 `../assets/2026-09-02_asset_supply_and_collaboration.md` 5절이 "남은 진짜 구멍"으로 지목한 것과
> 정확히 일치하며, **이제 그 이유가 기계적으로 설명된다** — 없어서가 아니라 **워핑이 구조적으로
> 못 메우기 때문**이다.

### 16.3 ⚠️ 자산 파이프라인 요구사항 추가 — `Enable_Warping` 커브 [A]

3.3b절의 `contact_l`/`contact_r`에 이어 **세 번째 필수 커브**다.

```
우리가 들여오는 모든 로코모션 클립이 가져야 하는 커브

  1. contact_l / contact_r   → 발 심기 타이밍      (FootPlacement)     [3.3b절]
  2. Enable_Warping          → 워핑 허용 구간      (Orientation Warping) [이 절]
  3. Disable_AO  (선택)      → 조준 오프셋 억제    (Get_AOValue)        [5.4절]
```

**`Enable_Warping`이 없으면 워핑이 영원히 안 켜진다**(커브 값 0 = Alpha 0). 즉 방향 커버가
전혀 안 되고, 우리 조달 계획의 핵심 전제가 무너진다.

**생성 방법 [B] — [C-25]**: 이 커브는 "동작이 직선인 구간 = 1"을 표시한다. `UMotionExtractorModifier`로
**루트 본의 회전 속도**(`MotionType=RotationSpeed`)를 뽑아 임계값 이하 구간을 1로 만드는 식으로
자동 생성할 수 있을 것으로 보인다. **P0-4(루트모션 인코딩 검증)에 이 단계를 함께 넣어 검증한다.**

### 16.4 Steering 노드 2개 [B]

Epic 주석:

> **Steering (실험적!)**: 애니메이션의 루트모션에 **추가 회전을 적용해 목표 쪽으로 조향**한다.
> 그 루트모션은 Offset Root Bone 노드가 소비해서 실제 루트 회전을 처리한다.
> **이 노드는 작업 중이며 원치 않는 거동이 일부 있다.**
>
> **두 번째 Steering**: 제자리 회전(turn in place)용으로 별도 노드가 필요하다. 이 노드의 일부
> 프로퍼티가 아직 핀으로 노출되지 않기 때문. 향후 제거될 예정.

| | 일반 Steering | 제자리 회전용 Steering |
|---|---|---|
| `Enabled` | `Enable Steering` | **`Current Database Tags` CONTAINS `"TurnInPlace"`** |
| `Target Orientation` | `Get_DesiredFacing()` | `Get_DesiredFacing()` |
| `Procedural Target Time` | **0.4** | **1000000.0** (절차적 조향 사실상 무효화) |
| `Animated Target Time` | 2.0 | 2.0 |

#### 읽어야 할 것

1. **`Get_DesiredFacing()`이 조향 목표다.** 5.4절에서 읽은 대로 기본 경로에서는 **궤적의 0.5초
   지점 방향**이다. 즉 **AI가 궤적을 통해 몸 방향을 제어하는 실제 경로가 여기다.**
2. **DB 태그로 노드를 켜는 패턴**(`Current Database Tags CONTAINS "TurnInPlace"`). 5.5절의
   `PlantSettings` 교체에 이은 두 번째 사례 — **DB 태그 규약이 시스템 동작을 제어한다.**
   우리가 견착 DB를 추가할 때 **태그를 반드시 규약에 맞게 달아야 한다.**
3. **Steering도 `OffsetRootBone`에 의존한다** — "루트모션은 Offset Root Bone이 소비한다".
   14.4절의 "OffsetRootBone은 뺄 수 없다"를 한 번 더 뒷받침한다.
4. Epic이 실험적/작업 중이라고 명시 → 우리가 AI로 구동할 때 **원치 않는 거동을 만날 수 있다.**
   P0-1에서 급선회 품질을 볼 때 이 노드를 의심 대상으로 둘 것.

### 16.5 인과 맵 추가

| 건드리는 것 | 영향 |
|---|---|
| 애니메이션의 **`Enable_Warping` 커브** | Orientation Warping의 Alpha → **방향 커버 가능 여부** |
| `Last Non Zero Velocity` | 워핑의 목표 이동 방향 |
| **DB 태그 `"TurnInPlace"`** | 제자리 회전용 Steering 활성화 |
| `Get_DesiredFacing()` (= 궤적 0.5초 지점) | **두 Steering 노드의 조향 목표** → 몸 회전 |
| `Enable Steering` | 일반 조향 on/off |
