# 적군 로코모션 애니메이션 파이프라인 — gait 구조 이식 + 2배속 버그 (2026-08-25)

> 시나리오 작업 중 "적군 발걸음이 배속 걸린 것처럼 빠르다"는 리포트에서 출발해, 원인 두 가지를
> 각각 규명하고 아군과 동일한 구조로 정리한 라운드. 원인이 **완전히 다른 두 개**가 겹쳐 있었고
> 둘 다 오진하기 쉬운 종류라, 재발/재조사 방지를 위해 경위까지 남김.
>
> 관련: `Source/titan_example/Soldiers/EnemyCombatComponent.h/.cpp`, `ABP_Enemy_kadex2`,
> `BP_Enemy_Base`, `BS_ally_kadex*`, `BP_ThirdPersonCharacter`/`BP_Ally_kadex`(아군 기준값).

---

## 1. 아군의 이동속도↔발걸음 매핑 구조 (커스텀 값이 어디 있는지)

한참 찾아 헤맨 부분이라 위치부터 기록. **블렌드스페이스가 아니라 캐릭터 BP + ABP의 2단 구조**임.

1. **`BP_ThirdPersonCharacter::EventTick`** — 자세/스프린트로 gait 속도 하나를 골라
   `MaxWalkSpeed`와 `GaitTopSpeed`에 **같은 값**을 넣음:
   - Prone → 0
   - Kneeling → `IsSprinting ? CrouchRunSpeed : CrouchWalkSpeed`
   - Standing → `IsSprinting ? RunSpeed : BaseWalkSpeed`
2. **속도 변수 4개의 실사용 값은 `BP_ThirdPersonCharacter` 기본값(300/600/150/300)이 아니라
   `BP_Ally_kadex`에서 오버라이드한 값**:
   `BaseWalkSpeed=200, RunSpeed=600, CrouchWalkSpeed=200, CrouchRunSpeed=400`
3. **`ABP_Ally_kadex2::EventBlueprintUpdateAnimation`**:
   ```
   Speed = Clamp(VelocityXY / GaitTopSpeed, 0..1) * (IsSprinting ? 600 : 300)
   ```
4. **`BS_ally_kadex`** Speed 축 `0~600`, 샘플은 3줄뿐:
   축 0 = `AS_RifleIdle`, 축 300 = `AS_Aim_Walk_*`(걷기), 축 600 = `AS_Jog_*`/`Run_*`(조깅).

**핵심**: 축은 실제 cm/s가 아니라 **"gait 안에서의 상대속도(0~1)를 고정 앵커(걷기 300 / 뛰기 600)에
실은 값"**. 그래서 gait top보다 느리게 이동하면 비율이 떨어져 애니메이션도 자동으로 같이 느려짐 —
상황별 이동속도를 gait 값에 억지로 맞출 필요가 없다.

적군 전용 블렌드스페이스는 없고 `BS_ally_kadex*`를 그대로 공유한다.

---

## 2. 원인 A — 적군에 gait 2단 구조가 없었음

적군은 `UEnemyCombatComponent::MoveToward`가 `GaitTopSpeed`에 **상황별 임의 속도**(150/220/300/400)를
그대로 넣었고, `ABP_Enemy_kadex2`도 마지막 곱셈이 앵커 상수가 아니라 **`GaitTopSpeed` 자기 자신**
이었음. 수식상 `Clamp(V/G)*G = min(V, G)`이라 축이 실제 cm/s가 돼버려서, 아군 기준으로 튜닝된
블렌드스페이스와 어긋났음.

**수정** — 아군과 동일 구조로 통일:
- `Enemy|Gait` 카테고리에 gait 속도 4종 추가, 값은 아군 오버라이드와 **동일하게 200/600/200/400**
  (블렌드스페이스를 공유하므로 여기가 달라지면 발 속도가 다시 어긋남).
- `ApplyGaitForDesiredSpeed()` 신규 — 아군 `EventTick`과 같은 규칙(현재 `IsKneeling` + "이 속도가
  걷기 최고속도를 넘는가")으로 gait을 골라 `GaitTopSpeed`/`IsSprinting`(`BP_Enemy_Base`에 신규 bool)을
  세팅하고 그 gait의 top speed를 반환. `MaxWalkSpeed`는 기존대로 도착 감속 램프를 적용하되
  gait top으로 클램프.
- `ABP_Enemy_kadex2`의 Speed 수식을 아군과 동일하게 교체:
  `Clamp(V/GaitTopSpeed) * (IsSprinting ? 600 : 300)`.

덕분에 상황별 속도를 자유롭게 낮춰도 애니메이션이 비례해서 느려짐(경계 이동을 더 느리게 해달라는
요구가 구조적으로 해결됨).

### 남은 오차 (미해결, 체감 시 조정 필요)
축 앵커가 `300↔실이동 200` / `600↔실이동 600`으로 **비선형**이라, 그 사이 중간 속도에서는 발 속도가
정확히 맞지 않는다. 아군은 걷기(200)나 뛰기(600) 둘 중 하나에 정확히 머물러서 티가 안 났지만,
적군은 임의 중간 속도(220/300/400)로 계속 이동하므로 항상 중간 구간에 있음. 예: 앉아뛰기 gait
(top 400)로 400에 이동하면 축이 600이 되는데, 그 샘플은 원래 더 빠른 이동에 맞춰진 것.
- 정확도 우선이면 적군 이동속도를 gait top(200/600 또는 200/400)에 정확히 맞추는 방법,
- 속도감 우선이면 현 상태 유지 후 체감으로 미세조정.

참고로 `BS_ally_kadex_Crouch`의 `AS_Crouch_Aim_Run_Forward` 샘플에만 `rateScale = 1.3`이 걸려
있음(의도된 보정으로 보이므로 건드리지 말 것). `Knee` 상태는 `BS_ally_kadex_Crouch`를,
`AimLocomotion`/`LoweredLocomotion`은 `BS_ally_kadex`를 쓴다.

---

## 3. 원인 B — AnimGraph 포즈 갈래로 인한 진짜 2배속 ★

원인 A를 고쳤는데도 "블렌드스페이스 600 미리보기보다 2배 빠르다"는 리포트가 남았음. 축 매핑
문제로는 **같은 축값에서의 재생 배율 차이**를 설명할 수 없어서 재조사했고, 실측 로그로 이동속도
증폭이 아님을 먼저 배제함(`실제속도 == MaxWalkSpeed`, `CustomTimeDilation`/`GlobalAnimRateScale`
모두 1, 블렌드스페이스 노드 `playRate`도 1, `RootMotionMode`도 아군과 동일).

**진짜 원인**: `ABP_Enemy_kadex2` AnimGraph에서 `MovementState` 스테이트머신 출력이 캐시를 거치지
않고 **두 갈래**로 갈라져 있었음:

```
StateMachine(MovementState) ─┬─→ Slot'DefaultSlot'.Source ─→ LayeredBoneBlend_0.BlendPoses_0
                             └─→ LayeredBoneBlend_0.BasePose
```

AnimGraph에서 포즈 출력이 N개 입력에 연결되면 **그 상류 체인이 프레임당 Update를 N번 받아 시간이
N배로 흐른다**. 2갈래 = 정확히 2배속. 이전 세션의 "사망 몽타주가 안 보임" 수정에서 Slot 갈래를
추가하면서 기존 직결을 안 끊은 것이 원인이었음.

**수정**: `LocomotionRawCache`(Save Cached Pose)를 스테이트머신 뒤에 삽입하고, `Slot'DefaultSlot'`과
`LayeredBoneBlend_0.BasePose`가 각각 `Use Cached Pose`에서 받도록 재배선 → 스테이트머신 소비자가
하나가 되어 Update 1회로 정상화. `LayeredBoneBlend_0` 설정은 그대로라 포즈 결과값은 동일.

> **오진 방지 메모**: 아군 그래프에도 `LayeredBoneBlend_5`에 3갈래 포크가 있지만 **캐시 하류**라
> 스테이트머신엔 영향이 없어 증상이 없다. 문제가 되는 건 **시간이 흐르는 노드(스테이트머신/
> 블렌드스페이스/시퀀스 플레이어)가 포크 상류에 있을 때**뿐. 애니메이션이 이상하게 빠르면
> 재생 배율(playRate/rateScale/TimeDilation/GlobalAnimRateScale)보다 **포즈 fan-out을 먼저 확인**할 것.
> `get_connected_subgraph`로 받아 출력 핀의 연결이 2개 이상인 곳을 찾으면 바로 나옴(단 Output 기준
> subgraph에는 SaveCachedPose 체인이 안 잡히므로 그쪽도 따로 조회해야 함).

---

## 4. 부수적으로 확인된 AnimGraph 사실들

- **`AimPitch`는 `Spine2` 본의 `Transform (Modify) Bone` 회전으로 물려 있음**(그 위 `Neck`/`Head`가
  FK로 따라옴). 적군은 이 값을 갱신하는 주체가 없어 항상 0이었고, 그래서 경계 이동 시 고개를 든
  연출이 불가능했음 — `PatrolAimPitchDeg`로 해결(시나리오 문서 Part C 참고).
- **`UpperBodySlot` 슬롯 노드 + BlendMask 레이어 신설**: 상체 몽타주를 본별 가중치로 얹는 경로.
  `Enemy_Skeleton`의 `BM_UpperBodyLookAround`(Blend Mask 모드) 사용, 노드 가중치는 1.0으로 두고
  세기 조절은 마스크에서 함(`TargetBlendWeight = 노드가중치 × 마스크값`). 둘러보기 연출에는
  결국 안 쓰게 됐지만 배선은 남아있어 피격 리액션 등에 재활용 가능.
  - **BlendMask는 자식 본으로 전파되지 않음** — 목록에 없는 본은 가중치 0. 상체 본을 빠짐없이
    채워야 함.
  - Blend Profile UI는 **Skeleton Tree의 숨겨진 컬럼**임(`HiddenColumnsList`에 기본 포함). 컬럼
    헤더 우클릭 → `Blend Profile` 체크 → 헤더의 `NoBlend` 클릭 → `New` 섹션에서 Blend Mask 생성.
- **`LayeredBoneBlend_0`의 BranchFilter가 `Spine / blendDepth -1`** — 엔진 소스
  (`FAnimationRuntime::CreateMaskWeights`) 기준 `BlendDepth < 0`이면 증가분이 음수라 클램프되어
  **모든 본 가중치가 0**이 됨. 즉 현재 `DefaultSlot` 몽타주(`Hit_Reaction` 등)는 사실상 화면에
  반영되지 않고 있을 가능성이 큼. **미수정 — 확인 후 별도 처리 필요.**

---

## 5. 남은 작업

### 2026-09-01 실측으로 확정된 것 (디자이너 공유 문서 작성 중 발견)

- **`DefaultSlot` 경로가 죽어 있는 실제 피해자는 `Hit_Reaction`이 아니라 낙하산 착지 몽타주다.**
  비살상 피격은 몽타주를 아예 안 쓰고(`EventAnyDamage`의 비치명 분기가 `TriggerHitReactionPhysics`만
  호출) 스프링으로 대체됐으므로 `AS_Hit_Reaction`/`AM_Hit_Reaction`은 미사용 애셋이다. 반면
  `AM_Falling_To_Landing`/`AM_Hard_Landing`은 **둘 다 슬롯이 `DefaultSlot`** 이라, 4절의
  `blendDepth -1`(가중치 전부 0) 문제로 화면에 반영되지 않고 있을 가능성이 크다.
  → `LayeredBoneBlend_0`의 `blendDepth`를 1~3으로 정상화한 뒤 **착지 모션이 실제로 보이는지**로
  검증할 것(피격 리액션으로 검증하려 하면 애초에 재생되는 게 없어서 판단 불가).
- **`BS_ally_kadex_Lowered`는 아무도 안 쓴다.** 아군·적군 `LoweredLocomotion` 상태를 노드 단위로
  확인한 결과 둘 다 `BS_ally_kadex`(서서 조준용)를 물고 있고, 그 상태엔 블렌드스페이스 노드가
  하나뿐이라 다른 경로도 없다. 즉 **총 내린 이동에도 조준 시퀀스가 재생 중**이다.
  단, `BS_ally_kadex_Lowered`는 **방향 축이 없는 1D(전진 전용, 샘플 3개)** 라 지금의 사주경계
  옆걸음/뒷걸음을 표현할 수 없다 — 그대로 갈아끼우면 오히려 퇴보. 총 내린 8방향 세트가 확보되기
  전까지는 현 상태 유지가 맞다.
- **`BS_ally_kadex` 600축 -90°에만 `Run_Left`가 꽂혀 있다**(나머지 7방향은 `AS_Jog_*`). 같은 계열
  `AS_Jog_Left_2`가 미사용으로 남아 있어 실수일 가능성이 높음 — 좌우 사이드스텝 느낌이 다르면
  이 지점.

### 기존 항목

- 위 `LayeredBoneBlend_0`의 `blendDepth -1` 정상화(→ 1~3).
- 2절의 gait 중간속도 오차 — 체감상 거슬리면 이동속도를 gait top에 맞추는 방향으로 조정.
- 아군 `LayeredBoneBlend_5`의 3갈래 포크 정리(현재 무해하나 구조상 불필요한 중복 업데이트).
