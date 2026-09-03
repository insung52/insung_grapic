# 적군 피격 리액션 — 절차적 스프링 시스템 구현 현황 (2026-08-24)

> `enemy_ai_combat_system_status.md`(2026-08-12) 이후 별도 라운드로 진행된 작업. 처음엔
> `UPhysicalAnimationComponent` 기반 진짜 리지드바디로 피격 시 몸을 흔드는 걸 시도했으나, 스프링
> 값/자기충돌/솔버 반복 횟수를 다 바꿔봐도 원인불명의 떨림이 계속돼서 폐기(Hips를 킨네마틱으로
> 고정하고 그 아래만 시뮬레이션하는 구성 자체가 문제였던 것으로 추정 — 한 고정점에 여러 갈래가
> 동시에 매달린 조인트 체인은 솔버가 잘 못 품). 대신 **물리 엔진을 전혀 안 건드리는 순수 계산
> 감쇠조화진동자**로 완전히 교체 — 애니메이션 위에 회전/이동 오프셋을 얹기만 해서 발산·충돌·조인트
> 문제가 구조적으로 없고, 캡슐 이동/기존 포즈와 절대 안 어긋남.
>
> 관련 코드: `Source/titan_example/Soldiers/EnemyCombatComponent.h/.cpp`(`TriggerHitReactionPhysics`/
> `TickHitReactionSpring`), `ABP_Enemy_kadex2`(AnimGraph의 `Transform (Modify) Bone` 노드들),
> `BP_Enemy_Base`(`Event AnyDamage`/`Event Point Damage`), `Source/titan_example/Vehicles/
> RCWSProjectile.cpp`(피격 파이프라인).

---

## 1. 히트 파이프라인 — Point Damage가 Any Damage보다 먼저 온다

`RCWSFireControlComponent`가 스폰한 `ARCWSProjectile`(실사용은 `BP_RCWSProjectile`,
`/Game/Vehicles/UGV/Effects/BP_RCWSProjectile` — `UGV_OLD` 쪽 구버전 아님)이 `OnComponentHit`에서
`UGameplayStatics::ApplyPointDamage(OtherActor, DamagePerHit, ImpactDirection, Hit, ...)`를 호출.
엔진 소스(`AActor::TakeDamage`) 기준으로 **`Event Point Damage`가 `Event Any Damage`보다 먼저
실행됨**이 확인됨 — 그래서 `BP_Enemy_Base`는 `Event Point Damage`에서 `LastHitLocation`/
`LastHitDirection`(=`ShotFromDirection`)/`LastHitBoneName`/`LastHitVelocity`(=현재 캐릭터 속도,
사망 시 관성용)만 캐싱해두고, `Event Any Damage`가 실행될 때는 이 값들이 이미 이번 히트 기준으로
채워져 있음을 보장받아 그대로 사용.

### 겪은 버그: `HitBoneName`이 항상 `None`
원인은 총알이 항상 **캡슐 콜리전**에 맞고 있었던 것(캡슐엔 본 단위 정보가 없음). 수정:
- 메시 컴포넌트는 `QueryOnly` + `WorldDynamic=Block`으로 바꿔서 실제 피직스 애셋 바디 형상으로
  충돌하게 함, 캡슐은 `WorldDynamic=Ignore`.
- **함정 1**: `collisionProfileName`이 여전히 실제 등록된 프로파일 이름(`"Pawn"`)인 채로 리플렉션
  으로 개별 채널 응답만 수정하면, 엔진이 프로파일 기준으로 조용히 재동기화해서 수정이 씹힘 —
  채널을 개별 수정할 땐 반드시 `collisionProfileName="Custom"`도 같이 세팅해야 함.
- **함정 2**: 실제 레벨에 스폰되는 클래스는 `BP_Enemy_kadex`(자식)이고, 이 자식이 `CapsuleComponent`/
  `Mesh`의 콜리전을 **부모(`BP_Enemy_Base`)와 독립적으로 오버라이드**하고 있어서, 부모에만 고친
  건 런타임에 전혀 반영 안 됐음 — 자식 CDO에도 동일하게 적용해야 함. (아래 4절 사망 임펄스 버그도
  같은 함정.)

---

## 2. 방향 계산 — 반드시 Mesh 컴포넌트 기준

`ABP_Enemy_kadex2`의 `Transform (Modify) Bone` 노드가 쓰는 "Component Space"는 **액터가 아니라
스켈레탈메시 컴포넌트 자신의 트랜스폼**(UE5.8 엔진소스 `AnimNode_ModifyBone.cpp:54`
`AnimInstanceProxy->GetComponentTransform()` 확인됨). 이 프로젝트의 Enemy 마네킹은:
- Mesh가 액터 기준 `Yaw -90°`로 붙어있음(표준 UE 마네킹 컨벤션, Epic 기본 Manny/Quinn과 동일).
- Hips 본 자체도 로컬로 `X축 90°` 회전돼 있음.

**둘 다 자산을 원래대로(0,0,0) 되돌려서 "해결"하면 안 됨** — 무브먼트/조준/기존 애니메이션 전부
같이 깨짐(확인 후 사용자가 직접 승인한 방향). 대신 `TriggerHitReactionPhysics`의 방향 변환을
`Owner->GetActorTransform()`이 아니라 **`Character->GetMesh()->GetComponentTransform()`** 기준으로
계산하도록 고쳐서 해결 — 이 회전들이 전부 반영된 로컬 좌표계 그대로 Pitch/Yaw/Roll에 태워짐.

### 최종 검증된 부호값 (2026-08-22 PIE 실측, 재추측 불필요)
| 프로퍼티 | 값 |
|---|---|
| `HitReactionPitchSign` | **-1.0** |
| `HitReactionYawSign` | **0.3** |
| `HitReactionRollSign` | **1.0** |

(과정에서 Roll/Yaw를 먼저 뒤집어봤다가 틀렸고, 최종적으로 Pitch만 뒤집는 게 정답이었음 — Mesh
트랜스폼 기준 로컬 변환 코드가 이미 적용된 상태에서 나온 값이므로, 코드 자체를 안 건드리는 한
다시 추측할 필요 없음.)

---

## 3. 부위별 스프링 — Spine / 다리(좌우) / 팔(좌우) / Hips

`TickHitReactionSpring`이 매 틱 상태(Move/Combat/Flee) 무관하게 아래 스프링들을 전부 적분해서
`ABP_Enemy_kadex2`의 대응 프로퍼티로 밀어주고, ABP가 각 본에 `Transform (Modify) Bone`으로 덧붙임.
공통 감쇠조화진동자 공식: `Accel = -Stiffness*Offset - Damping*Velocity`,
`Damping = 2*sqrt(Stiffness)*DampingRatio` — 감쇠비>0이 항상 보장돼 발산 없이 0으로 수렴.

| 대상 | 본 | 타입 | 비고 |
|---|---|---|---|
| 몸통 | `Spine` | 회전(Pitch/Yaw/Roll) | 기본 킥 |
| 왼/오 다리 | `LeftUpLeg`/`RightUpLeg` | 회전(Pitch/Roll만) | Spine과 반대로 뻗은 방향이라 부호 반전 필요(아래) |
| 왼팔 | `LeftHand` (IK 출력 본) | 회전(Pitch/Yaw/Roll) | IK와 안 겹치게 특수 처리(5절) |
| 오른팔 | `RightArm` (직결) | 회전(Pitch/Yaw/Roll) | IK 없음, 직접 킥 |
| Hips | `Hips` | **이동(cm, FVector)** | 회전 아님(4절) |

### 다리 방향이 거울처럼 반대인 이유
`AnimNode_ModifyBone.cpp`의 `BMM_Additive` 회전 합성(`NewBoneTM.SetRotation(BoneQuat *
NewBoneTM.GetRotation())`)은 축 자체는 본과 무관하게 항상 액터의 앞/오/위 축과 정렬되지만,
Spine은 골반에서 "위"로 뻗어있고 LeftUpLeg/RightUpLeg는 "아래"로 뻗어있어서 **똑같은 Pitch/Roll
값을 줘도 실제로 흔들리는 방향이 반대**로 보임(정면 피격 시 상체는 뒤로 젖혀지는데 다리는 앞으로
튀어나오는 버그의 원인). `HitReactionLegPitchSign`/`HitReactionLegRollSign`(기본 -1)을 다리 킥에만
곱해서 상쇄.

### 부위 판정
`USkinnedMeshComponent::BoneIsChildOf(BoneName, ParentBoneName)`로 `HitBoneName`의 조상을
`LeftUpLeg`/`RightUpLeg`/`LeftArm`/`RightArm`과 비교해서 분류, 어느 쪽도 아니면 몸통(Torso)으로
폴백.

---

## 4. 지렛대(레버) + 채찍(인셜) 효과 — 현실적인 충격 전파

사용자 요구사항: "몸통 중심에 맞으면 팔다리는 관성으로 반대로 튀어나오고, 팔다리 끝단에 맞을수록
그 팔다리 전체가 총알 방향으로 크게 넘어가야 함." 진짜 리지드바디 전파가 아니라 두 가지 절차적
장치로 구현:

- **레버 효과**: 그 팔다리 자신의 관절(엉덩관절 `LeftUpLeg`/`RightUpLeg`, 어깨 `LeftArm`/`RightArm`)
  에서 실제 피격 지점까지의 거리로 배율을 계산 — `LeverFactor = Lerp(MinFactor, 1.0,
  Clamp01(Distance/ReferenceCm))`. 관절 근처를 맞으면 약하게, 끝(발/손)에 가까울수록 최대(1.0).
  다리는 `HitReactionLegLeverReferenceCm=80`, 팔은 `HitReactionArmLeverReferenceCm=55`(팔이 더
  짧아서 기준거리도 작음), 둘 다 `MinFactor=0.15`(관절 바로 옆이어도 완전히 0은 아니게).
- **채찍(인셜) 효과**: 몸통(중심) 피격으로 분류되면, 맞은 부위(Spine)엔 정방향 킥을 주면서 **팔다리
  4곳 전부에 반대 부호(`-HitReactionWhipFactor`)로 킥**을 추가 — 진짜 지연 전파는 아니고, FK로
  자연히 전파되는 "같은 방향" 성분 위에 반대 부호를 얹어서 순간적으로 반대로 튀는 것처럼 보이게
  하는 절차적 트릭. 세기는 `HipsFalloff`(피격 지점이 Hips에서 얼마나 가까운지, 0~1)에 비례 —
  골반 근처를 맞을수록 채찍이 세게 걸림.
- 인접 부위(다리↔몸통) 전파는 별도로 `HitReactionPropagationFactor=0.35`만큼 Spine에도 항상
  더해짐(딱 맞은 본에만 반응하지 않고 몸 전체가 살짝 같이 반응하는 느낌).

---

## 5. 팔 IK와 안 겹치게 — `LeftHand`를 킥하는 이유

`TwoBoneIK`는 **상태 없는 매 프레임 기하학적 solve**임(엔진소스 `AnimNode_TwoBoneIK.cpp` 확인 —
스프링/힘/시간 기반 복원 로직이 전혀 없음). 그래서:
- IK의 입력 쪽 상위 본(예: `LeftForeArm`/`LeftArm`)을 먼저 킥하면, 그 다음 IK 스텝이 매 프레임
  다시 손 위치를 강제로 재계산해버려서 킥이 **보이지도 않고 그대로 흡수**됨.
- 대신 IK의 **출력 본**(`LeftHand`, 왼손 총 파지 IK의 최종 목표)을 킥하면 킥이 그대로 보이고, 스프링이
  자연 감쇠하면서 IK가 매 프레임 계속 손잡이 위치로 재수렴하기 때문에 "튕겼다가 알아서 원위치로
  복귀"하는 자연스러운 회복이 됨 — 왼손은 이 방식, **오른팔(`RightArm`)은 IK가 안 걸려 있어서 그냥
  직결로 킥**.

---

## 6. Hips — 회전이 아니라 이동만

Hips는 스켈레톤의 최상위 루트 본이라 회전을 주면 다리 전체가 허공에서 호를 그리며 휩쓸리는 문제가
생김(발이 땅에서 떨어짐). 그래서 **이동(Translation)만** 줌 — 몸 전체가 지금 자세 그대로 슬라이드
되는 거라 이 문제가 구조적으로 없음. 방향은 회전과 마찬가지로 Mesh 컴포넌트 자신의 트랜스폼 기준
(Hips 본 자체가 로컬로 X축 90도 돌아가 있어서 로컬 기준으로 이동시키면 엉뚱한 방향으로 밀림).
피격 지점이 Hips에서 `HitReactionHipsFalloffDistanceCm=100cm` 이상 떨어지면 Hips 킥이 거의 0에
가까워짐(몸통/골반 근처면 세게, 먼 팔다리면 약하게).

---

## 7. 사망 임펄스 — 2026-08-24, 두 겹 버그

**요구사항**: 죽을 때도(사망 시퀀스는 `UPhysicalAnimationComponent` 기반 액티브 랙돌 — 별도 문서
`enemy_scenario_combat_expansion.md` 1절 참고) 지금까지의 관성(`SetAllPhysicsLinearVelocity(
LastVelocity)`)뿐 아니라 실제 총알 방향 임펄스도 받고 싶다는 요청. 조사 결과 `AddImpulseAtLocation
(Mesh, LastHitDirection*DeathImpulseMagnitude, LastHitLocation, LastHitBoneName)` 노드 자체는
Part A 작업 때(`SetAllPhysicsLinearVelocity` 바로 다음 줄) 이미 배선돼 있었음 — 그런데 매그니튜드를
400→1억5천만까지 올려도 육안으로 전혀 안 보임. 두 가지 독립된 버그가 동시에 있었음:

1. **자식 클래스 오버라이드**(3절/1절과 동일 계열 버그): `BP_Enemy_kadex`(실제 스폰 클래스)의 CDO가
   `DeathImpulseMagnitude`를 **0으로 독립 오버라이드**하고 있어서, 부모 `BP_Enemy_Base`에서 아무리
   값을 올려도 실제 스폰되는 자식은 계속 0을 썼음. 양쪽 CDO 다 `1500`으로 맞춤.
2. **Chaos 타이밍 버그**(진짜 물리 버그): `SetAllBodiesSimulatePhysics(true)`로 킨네마틱→시뮬레이트
   전환한 바로 그 프레임에 곧바로 `AddImpulseAtLocation`을 부르면, Chaos가 이 전환을 아직 처리하기
   전이라 임펄스가 조용히 씹힘(속도 설정(`SetAllPhysicsLinearVelocity`)은 되는데 임펄스만 안 먹는
   비대칭 증상과 정확히 일치). `SetAllPhysicsLinearVelocity`와 `AddImpulseAtLocation` 사이에
   `Utilities|FlowControl|DelayUntilNextTick` 노드를 끼워서 한 틱 쉬고 임펄스를 적용하도록 수정.

수정 후 `DeathImpulseMagnitude=1500`(부모/자식 CDO 동일)으로 맞춰뒀고, 사용자가 PIE에서 직접
확인하여 정상 작동 확인함("성공했음").

---

## 8. 전체 튜너블 값 (`EnemyCombatComponent.h`, `Enemy|Combat|HitReaction` 카테고리)

| 프로퍼티 | 기본값 | 설명 |
|---|---|---|
| `HitReactionKickMagnitude` | 400 | 비살상 피격 기본 킥 세기 |
| `HitReactionSpringStiffness` | 500 | 스프링 강도(클수록 빠르게 반응/복귀) |
| `HitReactionSpringDampingRatio` | 0.6 | 0=무한진동, 1=임계감쇠 |
| `HitReactionPitchSign` | **-1.0** | 실측 검증 완료 |
| `HitReactionYawSign` | **0.3** | 실측 검증 완료 |
| `HitReactionRollSign` | **1.0** | 실측 검증 완료 |
| `HitReactionLegPitchSign` | -1.0 | 다리 거울 반전 보정 |
| `HitReactionLegRollSign` | -1.0 | 다리 거울 반전 보정 |
| `HitReactionPropagationFactor` | 0.35 | 인접 부위(다리↔몸통) 전파 비율 |
| `HitReactionLegLeverReferenceCm` | 80 | 다리 레버 기준거리 |
| `HitReactionLegLeverMinFactor` | 0.15 | 다리 레버 최소 배율 |
| `HitReactionWhipFactor` | 1.0 | 몸통 피격 시 팔다리 채찍 반응 전체 세기 |
| `HitReactionArmPitchSign` | 1.0 | ⚠ 미실측(라이브 PIE 검증 안 됨, 아래 9절) |
| `HitReactionArmYawSign` | 1.0 | ⚠ 미실측 |
| `HitReactionArmRollSign` | 1.0 | ⚠ 미실측 |
| `HitReactionArmLeverReferenceCm` | 55 | 팔 레버 기준거리 |
| `HitReactionArmLeverMinFactor` | 0.15 | 팔 레버 최소 배율 |
| `HitReactionHipsKickMagnitude` | 15 | Hips 이동 킥 세기(cm 단위, 회전과 스케일 다름) |
| `HitReactionHipsSpringStiffness` | 400 | Hips 스프링 강도 |
| `HitReactionHipsSpringDampingRatio` | 0.7 | Hips 감쇠비 |
| `HitReactionHipsFalloffDistanceCm` | 100 | 이 거리 이상이면 Hips 킥 거의 0 |
| `DeathImpulseMagnitude`(`BP_Enemy_Base` 블루프린트 변수) | 1500 | 사망 시 총알 방향 임펄스 세기 — **부모/자식 CDO 둘 다 맞춰야 함** |

---

## 9. 남은 작업 / 알려진 이슈

- **팔 부호값 미검증**: `HitReactionArmPitchSign`/`YawSign`/`RollSign`이 전부 기본값(1.0) 플레이스
  홀더 상태 — 사용자가 "성공했음"이라고 확인한 건 왼손 IK/오른팔 지렛대·채찍 로직이 정상 작동한다는
  것이지, 축 부호가 100% 정확하다고 실측 확정된 건 아님(다리 때처럼 각도별로 미묘하게 틀릴 가능성
  있음). 필요시 PIE에서 팔만 다양한 각도로 맞춰보고 부호 미세조정.
- **이동 중 피격 비틀거림 애니메이션**: 미구현(작업 목록 #38, 별도 트래킹).
- 새 레벨(`newlevel`) 전체 3단계 시나리오 흐름 검증은 `enemy_scenario_combat_expansion.md` 참고.
- **`Hit_Reaction` 몽타주는 이제 아예 재생되지 않음**(2026-09-01 실측 확정): `EventAnyDamage`의
  비치명 분기가 `TriggerHitReactionPhysics`만 호출하므로 `AS_Hit_Reaction`/`AM_Hit_Reaction`은
  미사용 애셋이 됐음(이 문서의 스프링 시스템이 완전히 대체). 따라서 예전에 여기 적어둔
  "`DefaultSlot` 필터 문제로 피격 리액션이 안 보일 것"이라는 우려는 **대상이 틀렸음** — 그 경로의
  실제 피해자는 낙하산 착지 몽타주(`AM_Falling_To_Landing`/`AM_Hard_Landing`, 둘 다 `DefaultSlot`)임.
  자세한 내용은 `enemy_locomotion_animation_pipeline.md` 5절 참고.
