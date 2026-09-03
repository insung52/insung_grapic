# 적군 AI 이동/전투 시스템 구현 현황 (2026-08-12)

> 아군 AI 사격/엄폐 시스템(`ally_ai_combat_system_status.md`)이 끝난 뒤, `BP_Enemy_kadex`(부모
> `BP_Enemy_Base`)에 같은 수준의 전투 행동(사격/엄폐/이동/도주)을 붙인 라운드. 새 컴포넌트
> `UEnemyCombatComponent`를 아군의 `UAllyFormationComponent`와 나란히 만드는 방식으로 진행 —
> 검증된 아군 로직을 그대로 복제/이식하되, 대형·UGV 동행 같은 아군 전용 개념은 제외하고 적군
> 전용 최상위 상태(Move/Combat/Flee)를 새로 설계함. 두 컴포넌트를 공통 베이스로 묶는 리팩터링은
> 의도적으로 미룸(아군 쪽이 이번 세션 내내 수많은 라운드를 거쳐 막 안정화된 코드라, 지금 시점에
> 공유 베이스로 합치는 건 회귀 위험이 큼).
>
> 관련 코드: `Source/titan_example/Soldiers/EnemyCombatComponent.h/.cpp`,
> `Source/titan_example/Soldiers/CombatPoseTypes.h`,
> `Source/titan_example/Soldiers/BlueprintReflectionHelpers.h`, `BP_Enemy_Base`, `BP_EnemyRifle`,
> `ABP_Enemy_kadex2`, `UScenarioStateSubsystem::BeginEnemyFlee`,
> `Atitan_examplePlayerController::BeginEnemyFlee`(콘솔 명령).

---

## 1. `UEnemyCombatComponent` — 최상위 상태머신 (Move / Combat / Flee)

아군의 Standby~Ambush 같은 대형 상태 대신, 적군은 개별 개체라 훨씬 단순한 3상태:

- **Move**: `EngagePoint`까지 NavMesh로 이동. 이동방향과 무관하게(이전 세션에 확립한 "조준방향
  분리" 패턴) 감지 범위 안의 아군을 매 틱 조준하고, 쿨다운마다(`Min/MaxSingleShotIntervalSeconds`,
  기본 1.5~3초) **단발 1회**만 사격(`FireSingleShotAtNearestAlly`) — 버스트 아님.
  `EngagePoint` 도착 시 `Combat`으로 전환.
- **Combat**: 도착 후 아군과 동일한 4단계 자세 사이클(`Cover → TransitioningToFiring → Firing →
  TransitioningToCover`, `TickCombatPoseCycle`)을 재생 — 버스트 사격(3~4발, `FireAtAlly`/
  `FireBurstShot`)도 아군 패턴 그대로.
- **Flee**: `ExfilPoint`가 설정된 개체만 진입 가능. "도망시작" 명령(아래 5절) 발동 시 그 지점으로
  NavMesh 이동 — 처음엔 이동만 하고 조준/사격이 아예 없었으나(사용자 리포트), `TickMove`와 동일한
  패턴(이동방향과 무관하게 아군 조준 + 쿨다운마다 단발 견제사격)을 이식해서 도망가면서도 보이는
  아군에게 사격하도록 수정함(2026-08-11).

`EngagePoint`/`FiringPose`/`CoverPose`/`ExfilPoint`는 전부 인스턴스별 마커 프로퍼티 — 마커를 안
채운 개체는 Combat 상태에서 제자리 버스트만 반복(크래시 없이 안전 폴백), Flee는 `ExfilPoint`가
없으면 도망 명령 자체를 무시.

---

## 2. 애니메이션 파이프라인 — `ABP_Ally_kadex2` 복제 방식과 그 후유증

`ABP_Enemy_Base`(튜토리얼 원본, Idle/Walk/Parachute 3상태짜리 단순 스테이트머신)를 확장하는 대신,
완성도 높은 `ABP_Ally_kadex2`를 복제해서 `ABP_Enemy_kadex2`를 만들고 낙하산 착지 등 원본에만
있던 기능을 이식하는 방식으로 진행(사용자 결정). 스켈레톤은 본 이름이 100% 일치해서
`USkeleton::CompatibleSkeletons`로 리타겟 없이 그대로 재생 가능(`Enemy_Skeleton`에
`Rifle_Aiming_Idle_Skeleton`을 호환 목록으로 추가).

### 겪은 문제들과 원인
- **EventGraph가 반복적으로 깨짐**: `write_graph_dsl`로 기존 이벤트를 재작성할 때, 복제 시점의
  낡은 노드(이미 지운 함수 그래프를 호출하는 고아 노드 등)와 새로 쓰는 내용이 "교체"가 아니라
  "병합"되면서 컴파일이 빈 에러 목록(`Compile Errors: []`)으로 조용히 실패. 그래프를 완전히
  비우고(고아 노드 전부 삭제) 처음부터 다시 쓰는 방식으로 해결.
- **죽는 모션이 안 나옴**: 원본 `ABP_Enemy_Base`는 `StateMachine → LayeredBoneBlend → Slot
  ('DefaultSlot') → 최종출력` 순서로 연결돼 있어 `DefaultSlot`에서 재생되는 몽타주(사망
  애니메이션이 정확히 이 슬롯을 씀)가 최종 포즈에 반영됨. `ABP_Ally_kadex2`엔 같은 `Slot
  ('DefaultSlot')` 노드가 있지만 출력이 어디에도 연결 안 된 죽은 노드였음(아군은 이 슬롯을 애초에
  안 써서 아무도 몰랐던 기존 결함) — `StateMachine → Slot(DefaultSlot) → LayeredBoneBlend`로
  재연결해서 해결.
- **이동방향과 다른 스트레이프 애니메이션 재생**(예: 왼쪽으로 걷는데 오른쪽으로 걷는 모션): `Direction`
  변수가 아예 안 채워지고 있었음(`Animation|CalculateDirection` 조합이 `write_graph_dsl`로 못
  쓰이는 알려진 버그라 처음엔 통째로 뺐었음). `self` 핀이 액터가 아니라 **애님 인스턴스 자신**을
  원한다는 걸 확인하고, DSL 대신 노드를 직접 만들어 연결(`create_node`/`connect_pins`)하는 방식으로
  우회 이식.
- **낙하산 낙하 포즈**: 원래 계획은 `MovementState` 스테이트머신 안에 진짜 Parachute 상태를
  추가하는 거였으나, `unreal-mcp` 툴이 스테이트머신 내부 그래프(상태/트랜지션)엔 노드 생성 자체를
  지원 안 함(`create_node`/`find_node_types` 둘 다 실패) — 대신 AnimGraph 최상단에서
  `StateMachine` 출력 바로 뒤에 `Blend Poses by Bool`을 끼워넣어 `IsParachuting`으로 게이팅하는
  임시 우회로 구현. 이후 사용자가 직접 에디터에서 진짜 Parachute 상태를 스테이트머신에 추가했고,
  이제 두 메커니즘이 중복되면서 낙하 관련 애니메이션이 가끔 꼬이는 원인이 됐던 것으로 보여 임시
  우회(top-level Blend) 쪽을 제거하고 사용자가 만든 진짜 상태 하나만 남김.

---

## 3. 무기 — `BP_EnemyRifle`

`BP_AR4Rifle`을 직접 재사용하지 않고 복제(사용자 결정 — 나중에 적군 전용 무기 메시(AK 계열 등)로
바뀔 수 있어서 처음부터 독립 에셋으로 분리). `Shoot()`/`StartReload()`/탄퍼짐/재장전 사운드 로직은
전부 그대로 복제됨. `BP_Enemy_Base`에 `BP_ThirdPersonCharacter`의 무기 배선 패턴을 그대로 미러링:

- `EquipRifle`(BeginPlay에서 호출): `BP_EnemyRifle` 스폰 → `Enemy_Rifle_Socket` 부착, 장식용
  `Gun` 스태틱메시는 숨김 처리(완전 삭제는 안 함, 병행), `OnWeaponFired`/`OnReloadStarted`/
  `OnReloadFinished` 델리게이트 바인딩.
  - 이 바인딩 노드들은 `BP_AR4Rifle.OnWeaponFired`와 `BP_EnemyRifle.OnWeaponFired`가 이름이
    같아서 `write_graph_dsl`이 클래스를 잘못 고정시키는 진짜(cosmetic 아닌) 오류가 났음 —
    `create_node`의 `declaring_class` 파라미터로 명시적으로 disambiguate해서 해결.
- `FireBurstShot`/`FireAtAlly`(Combat 상태 3~4발 버스트), `FireSingleShotAtNearestAlly`(Move/Flee
  상태 단발) — 아군의 `FireAtEnemy`/`FireBurstShot` 패턴 그대로.
- `OnRifleFired`/`OnRifleReloadStarted`/`OnRifleReloadFinished` — 반동/재장전 애니메이션 재생.

---

## 4. 사망 처리 버그 3종

`BP_Enemy_Base::EventAnyDamage`(원본 그대로, 이번 라운드에서 무기 배선 때문에 같이 손봄)에서
발견/수정:

- **총이 공중에 뜬 채 안 사라짐**: 사망 시퀀스가 여전히 예전 장식용 `Gun` 컴포넌트만
  detach+물리켜기를 하고, 새로 추가한 `CurrentRifle`(스폰된 별도 액터)은 전혀 안 건드리고 있었음.
  `CurrentRifle`도 detach + `SetCollisionEnabled(QueryAndPhysics)`(물리 시뮬레이션이 콜리전 없이는
  시각적으로 안 먹힘) + `SetSimulatePhysics(true)` + 딜레이 후 `DestroyActor` 추가.
- **가끔 죽는 모션 없이 그 자세 그대로 멈춤**(조준/엄폐 중일 때 특히 자주): `IsDead` 세팅 이후에도
  `ABP_Enemy_kadex2`가 액터의 `AimPitch`/`IsKneeling`/`IsProne`을 매 틱 계속 읽어가는데, 그 값들이
  죽는 순간 값에 고정된 채(컴포넌트가 죽으면 갱신을 멈추니까) 사망 몽타주와 계속 충돌 — `IsDead`
  세팅 시점에 이 값들을 전부 중립값(0/false)으로 같이 리셋해서 해결.
- **도망 중 죽으면 시체가 빙글빙글 돎**: `UEnemyCombatComponent::TickComponent`가 사망 여부를 전혀
  체크 안 해서, 죽은 뒤에도 계속 `TickFlee`+`TickFacingInterp`가 돌아 실제 이동은 막혀 있어도
  회전 보간은 계속 적용되고 있었음. `TickComponent` 맨 앞에 `IsDead` 체크를 추가해 사망 시 AI/이동/
  조준 로직 전체를 정지.

---

## 5. 이동/충돌 버그 — 캡슐 콜리전 + 상호 밀어내기 누락

**증상**: 적군끼리 서로 못 비켜가서 길막당하거나 이동을 포기, 플레이어가 적군 근처에서 이동이
부자연스럽게 막힘.

**원인**: 아군은 `BeginPlay`에서 자기 캡슐의 Pawn 채널 콜리전 응답을 Block→Overlap으로 낮추고
(`bEnablePhysicsInteraction=false` + `bUseRVOAvoidance=true`로 RVO가 부드러운 회피를 담당,
Overlap은 RVO가 기하학적으로 못 푸는 상황의 최종 안전망), 겹쳤을 때만 개입하는 밀어내기
(`ResolveAllyOverlapPush`, 매 틱 호출)로 서로 자연스럽게 비켜감. **적군 쪽엔 이 두 가지가 아예
없었음** — 캡슐이 기본 Block 응답 그대로라 다른 적군/플레이어한테 완전히 못 지나가는 벽처럼
작동했음.

**수정**: `EnemyCombatComponent::BeginPlay`에 동일한 캡슐 콜리전 완화 추가, `ResolveEnemyOverlapPush`
신규 구현(매 틱, 상태 무관 호출). 아군처럼 별도 등록 리스트를 새로 안 만들고, 이미 있는
`UDetectableTargetSubsystem`(Faction==Enemy 필터, `BeginEnemyFlee`와 동일 순회 패턴)을 재사용.

정체 감지 + 자동 재탐색 로직(`TickNavPathMovement` 내부, 1초간 20cm 미만 이동 시 재탐색)은 처음부터
아군과 동일하게 구현돼 있었고, `EngagePoint`(Move)/`ExfilPoint`(Flee)/조준·엄폐 전환 이동
(`ApplyCombatPose`) 전부가 이 함수 하나를 공유해서 쓰기 때문에 별도 작업 없이 세 상황 모두 이미
커버되고 있었음.

---

## 6. 아군 쪽에도 같이 발견/수정된 버그

이번 라운드 중 적군 테스트로 발견했지만 아군 코드(`AllyFormationComponent.cpp`)에도 동일하게
있던 버그 — 양쪽 다 수정함:

- **버스트 도중 조기 엄폐**: 3~4발 버스트를 쏘는 중에 타겟이 죽어서 `HasTarget`이 풀리면
  `bForceCover`가 즉시 true가 되어, 남은 탄과 무관하게 바로 `TransitioningToCover`로 강제 전환되고
  있었음(마지막 발이 이미 돌아가는 몸 때문에 땅에 맞음). 이미 트리거된 버스트
  (`bFiringBurstTriggered && BurstShotsRemaining>0`)는 다 쏠 때까지 이 강제 전환을 건너뛰도록 예외
  추가(`AllyFormationComponent.cpp`/`EnemyCombatComponent.cpp` 둘 다).

---

## 7. 콘솔 명령 — "도망시작"

`Atitan_examplePlayerController::BeginEnemyFlee()`(콘솔에서 인자 없이 `BeginEnemyFlee` 입력) →
`UScenarioStateSubsystem::BeginEnemyFlee()`로 위임 — `UDetectableTargetSubsystem`에서
Faction==Enemy인 대상 전원을 순회하며 각자의 `UEnemyCombatComponent::BeginFlee()` 호출.
`ExfilPoint`가 없는 개체는 컴포넌트 내부에서 조용히 무시(Combat 상태를 계속 돎). 시나리오
DataTable 스텝으로 노출하는 건 이번 라운드 범위 밖(콘솔 명령까지만).

---

## 8. 남은 작업 / 알려진 이슈

- `FiringPose`의 `Lean`(왼쪽/오른쪽 기울임) 값이 `unreal-mcp` 프로퍼티 설정 툴로 가끔 안 먹히는
  현상 발견 — 단일 필드씩 쪼개서 재시도하면 됨(다른 필드와 묶어서 한 번에 설정하면 일부가 조용히
  누락되는 기존에 알려진 `unreal-mcp` 툴 한계와 동일 계열, 기능엔 지장 없고 에디터에서 수동으로도
  바로 잡을 수 있음).
- 여러 적을 동시에 대규모로 배치했을 때(30명 규모 등)의 성능/충돌 특성은 아직 실측 안 함 — 아군
  쪽은 이미 그 규모로 검증됨.
- 시나리오 DataTable 스텝으로 "도망시작"을 노출하는 건 미착수(콘솔 명령까지만 완료).

---

## 9. 관련 코드 위치

| 기능 | 파일 |
|---|---|
| 최상위 상태머신(Move/Combat/Flee), 자세 사이클, 조준 보정, 이동/충돌 | `Source/titan_example/Soldiers/EnemyCombatComponent.h/.cpp` |
| 아군과 공유하는 자세 구조체/리플렉션 헬퍼 | `Source/titan_example/Soldiers/CombatPoseTypes.h`, `BlueprintReflectionHelpers.h` |
| 무기 배선(`EquipRifle`/`FireBurstShot`/`FireAtAlly`), 사망 처리(`EventAnyDamage`), 낙하산 착지 | `BP_Enemy_Base` EventGraph |
| 발사(`Shoot`, 탄퍼짐), 재장전 | `BP_EnemyRifle` EventGraph |
| 이동 애니메이션(`Speed`/`Direction`), 낙하산 포즈, 죽는 몽타주 슬롯 배선 | `ABP_Enemy_kadex2` EventGraph/AnimGraph |
| "도망시작" 콘솔 명령 | `Atitan_examplePlayerController::BeginEnemyFlee`, `UScenarioStateSubsystem::BeginEnemyFlee` |
