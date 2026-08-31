> [보관됨 2026-08-31] 최신 버전: `ally_move.md`. 사유: 이 초안(Layered Blend Per Bone 제안 등)
> 이후 `ally_move.md`에서 Posture/Alert/Movement FSM 모델로 재설계됨(레이어링 방식은
> 로코모션+파지자세 조합에서는 폐기), 실제 애니메이션 목록은 `ally_animation_request.md`가
> 최신.

# 아군 액터 애니메이션 시스템 설계 (2026-08-04, 초안 — 논의 중)

> 목표: `BP_Ally_kadex`(ABP: `ABP_PlayerCharacter`)가 속도에 따라 대기/걷기/뛰기를 자연스럽게
> 전환하고, 총을 들고 조준한 자세 ↔ 내린 자세를 시나리오 상태에 맞춰 토글하며, 앉기/무릎/엎드림
> 등 기존 포즈들과 자연스럽게 어우러지도록 만드는 것. 30명이 동시에 존재해도 성능/제작비용이
> 감당 가능한 수준을 유지. **아직 구현 안 됨 — 논의용 설계 문서.**

이미 적용된 것: `BS_Movement`(아군 이동 블렌드 스페이스)의 `AxisToScaleAnimation`을
`BSA_None` → `BSA_X`로 변경(2026-08-04) — 실제 이동 속도에 맞춰 애니메이션 재생 속도가
늘어나고 줄어들게 함(예전엔 항상 원래 속도로만 재생돼서, 특히 저속 구간에서 발이 거의 안
움직이면서 캡슐만 미끄러지는 것처럼 보이던 문제의 근본 원인이었음).

---

## 0. 현재 상태 조사 결과 (실제 확인한 것들)

### 에셋 인벤토리
- **이동 블렌드 스페이스**: `/Game/Tutorial/Animation/BlendSpaces/BS_Movement` — Speed 축
  0(`AS_Idle`)/300(`AS_Walking`)/600(`AS_Run_Forward`), 스켈레톤
  `/Game/Characters/Soldier/Rifle_Aiming_Idle_Skeleton`.
- **상체 자세 후보**(전부 같은 스켈레톤, `/Game/Tutorial/Animation/AnimationSequences/`):
  `AS_RifleAim`(사용자 확인: 실제로는 **총 내린 자세** — 이름이 잘못 붙어있음),
  `AS_RifleIdle`(이름상 총 든 기본 자세로 추정, 라이브 확인 필요), 그 외 대부분(`AS_Idle`,
  `AS_Run_Forward` 등)도 총 든 자세로 추정. **`AS_Walking`/`AS_Walking1`은 상체 그립이
  이상해서 상체 레퍼런스로 쓰면 안 됨**(사용자 확인) — 하체(다리)만 쓸 것.
- **포즈 상태**: `AS_Crouching`(웅크리기 — **현재 ABP에 전혀 안 물려있음**, 이동 사이클
  없이 단일 포즈만 있는 것으로 보임), `AS_Knee`/`AS_StandtoKnee`(무릎쏴 — 이미 물려있음),
  `AS_ProneIdle`/`AS_ProneToKneel`(엎드리기 — 이미 물려있음).
- **재장전/살펴보기**: `AS_Reloading`/`AM_Reloading`, `AS_Inspecting`(이미 물려있음).
- **정지수신호**: `AS_Stopsign`(이미 물려있음, 분대장 전용).
- **둘러보기(look around)**: `AS_Enemy_Looking_Around` — **스켈레톤이
  `/Game/Tutorial/Blueprints/Enemy/Enemy_Skeleton`으로 아군 스켈레톤과 다름.** 그런데
  `ABP_PlayerCharacter`의 애셋 종속성 목록에 이미 포함돼 있고, `IsLookingAround` 변수도
  `BP_Ally_kadex`에 이미 존재함(`ABPEnemyBase`라는 공유 부모 클래스에서 상속된 것으로
  보임 — 이름은 "Enemy"지만 아군도 같은 부모를 씀). **스켈레톤이 다른데 실제로 재생되는지
  라이브로 확인 필요** — 리타겟이 이미 돼있을 수도, 조용히 무시되고 있을 수도 있음.
- **사망**: `AS_Dead` — 확인만 해둠, 아직 용도 파악 안 함.

### ABP 변수 파이프 구조 (이미 확립된 패턴 — 그대로 따라가면 됨)
`ABP_PlayerCharacter::EventGraph`(`EventBlueprintUpdateAnimation`)를 직접 읽어봄 — 매 틱
캐릭터 BP(`PlayerCharacterRef`)의 변수를 그대로 복사해오는 구조:
```
Speed = VectorLengthXY(CharacterMovement.Velocity)
IsHoldingWeapon? = 캐릭터의 IsHoldingWeapon?
IsProne = 캐릭터의 IsProne
IsKneeling = 캐릭터의 IsKneeling
AimPitch = 캐릭터의 AimPitch
IsReloading = 캐릭터의 IsReloading (+ReloadBlendAlpha는 ABP에서 자체 보간)
IsLookingAround = 캐릭터의 IsLookingAround (UpdateLookAroundRunTrigger 통해서 간접)
```
→ **핵심**: ABP는 상태를 스스로 판단하지 않고, 캐릭터 BP의 bool/float 변수를 그대로
받아서 블렌드만 함. "언제 총을 들지/내릴지", "언제 웅크릴지" 같은 판단은 **캐릭터 쪽
(즉 우리 C++ `AllyFormationComponent`)의 몫**. 이미 `TickAmbush`에서
`SetBoolPropertyByName(Owner, FName("IsProne"), true)`로 이 패턴을 쓰고 있음(리플렉션
기반, BP 변수를 C++에서 직접 세팅) — 아래 설계도 전부 이 기존 패턴을 그대로 확장하는
방향.

---

## 1. 왜 "뛰는 것처럼 안 보이는지" — 속도 튜닝 문제였음 (2026-08-04, 조치 완료)

`BS_Movement`는 300에서 완전히 Walking, 600에서 완전히 Run_Forward. 확인해보니
`FollowMoveSpeed`/`CatchUpMoveSpeed`는 이미 600(Run 샘플)으로 맞춰져 있었지만
**`FormUpMoveSpeed`만 300(Walking 샘플)에 머물러 있었음** — "대형 갖추는 느낌으로 걷는 게
자연스럽다"는 예전 설계 판단이었는데, 이번 요청("총 내리고 뛰어서 이동")으로 뒤집힘 →
**600으로 상향 완료**(`AllyFormationComponent.h`).

**UGV 에스코트 속도와의 정합성 확인 + 버그 수정**: 사용자 확인 — "UGV 20km/h(real2world
보정)면 현실에서 뛰어야 도달하는 속도"가 설계 기준. 실제로 `AUGVAIController`의
`EscortMaxSpeedKmh` 거버너가 `GeoCoordinateUtils::GetDistanceScaleFactor()`(씬
1cm≈실제 1.2135cm, 이 프로젝트 다른 모든 km/h 환산이 쓰는 보정값) 적용을 빠뜨리고
있던 걸 발견 — "20km/h"로 설정해도 실제로는 씬 기준 20(≈ 실제 24.3km/h)까지 허용되고
있었음. **다른 코드와 동일하게 보정 적용해서 수정 완료.** 수정 후 계산: 실제 20km/h →
씬 기준 ≈457.7cm/s → 아군 `FollowCatchUpMarginCmPerSec`(150) 더하면 607.7 →
`FollowMoveSpeed`(600) 캡에 걸려 정확히 Run_Forward 샘플에 도달 — Following 구간은
이미 완전한 Run 블렌드가 나오는 게 맞음(수정 전에도 우연히 그랬음, 이제 계산 근거가
정확해짐).

---

## 2. 저속 슬라이딩 — 근본 원인 후보 정리

1. **(해결됨, 2026-08-04)** `AxisToScaleAnimation=BSA_None` → `BSA_X`로 수정 — 이제 저속에서도
   애니메이션 재생 속도가 실제 이동 속도에 맞춰 느려지므로, 예전처럼 "발이 하나도 안
   움직이는데 미끄러지는" 극단적인 증상은 크게 줄어들 것으로 예상.
2. **(검증 필요)** 그래도 완전히 안 없어질 수 있는 이유: `ApproachSlowdownDistanceCm`(현재
   300cm) 구간 전체에서 속도가 선형으로 0까지 줄어드는데, 그 사이 애니메이션은 여전히 Idle
   쪽으로 블렌드 웨이트가 쏠림(Idle=0, Walking=300 선형 블렌드라서 낮은 속도일수록 Idle
   비중이 큼) — 재생 속도는 이제 맞아도, "거의 멈춘 듯한 포즈 + 아주 느린 재생"이 자연스러운
   느낌인지는 라이브로 봐야 함. 필요하면 `ApproachSlowdownDistanceCm`을 줄이거나(감속 구간
   자체를 짧게), Idle-Walking 사이에 중간 샘플(예: Speed=100 지점에 살금살금 걷기)을
   추가하는 것도 고려 가능.
3. **발바닥-지면 정합**: 근본적으로 발 IK 없이는 완벽히 안 맞음(경사/계단 등) — Foot IK는
   3절 범위 밖(성능 문제로 별도 논의, 이전 대화 참고: 타르코프식 풀 스텝플래닝은 30명한테
   과함, 가벼운 2-Bone Foot IK 정도가 현실적 타협안).

---

## 3. 제안 아키텍처

### 3-1. 원칙: "판단은 C++, 표현은 ABP"
`AllyFormationComponent`(C++)가 시나리오 상태(`EAllyFormationState`: FormingUp / Following /
Approaching / Ambush)에 따라 캐릭터 BP의 bool 변수들을 세팅 — ABP는 그 변수를 그대로 받아
블렌드만 함(기존 `IsProne` 세팅 패턴 그대로 확장). 새로 필요한 변수:

| 변수 (BP_Ally_kadex, 이미 있으면 재사용) | 의미 | 세팅 시점 |
|---|---|---|
| `IsHoldingWeapon?` (기존 변수, 지금 실제로 쓰이는지 확인 필요) | true=조준자세, false=내린자세 | FormingUp/Following 진입 시 false, Approaching 진입 시 true |
| `IsCrouching` (신규) | 웅크리기 | 필요시(엄폐 등, 범위 확정 안 됨) |
| `AnimPhaseOffsetSeconds` (신규) | 개체별 애니메이션 위상차 | BeginPlay에서 1회 랜덤 |

### 3-2. 하체 로코모션 (거의 완성 — 튜닝만 남음)
`BS_Movement`(Idle/Walk/Run, Speed 축) 그대로 유지. 1절의 속도 튜닝 + 2절의 슬라이딩
재검증만 남음.

### 3-3. 상체 무기 자세 토글 — Layered Blend Per Bone 신규 필요
현재 구조는 하체 로코모션과 상체 포즈가 분리돼 있지 않은 것으로 보임(스테이트 머신 자체가
전신 애니메이션을 통째로 재생하는 방식). 목표(속도로 다리 자유 전환 + 별개로 무기 자세
토글)를 달성하려면 **상체/하체를 스파인 본 기준으로 분리하는 Layered Blend Per Bone 노드가
필요**:
- 하체: `BS_Movement`(Idle/Walk/Run) 그대로.
- 상체: `IsHoldingWeapon?`으로 두 소스 사이 크로스페이드 —
  - true(조준): **`AS_RifleIdle`**(사용자 확인 완료 — 정상적인 "총 든" 포즈).
  - false(내림): `AS_RifleAim`(사용자 확인 — 실제로는 내린 자세, 이름이 잘못 붙어있음).
  - **주의**: `AS_Walking`/`AS_Walking1`은 그립이 이상해서 상체 소스로 쓰면 안 됨(사용자
    확인) — 위 두 후보처럼 "제자리 포즈" 애셋에서 상체만 떼어 씀. 하체는 어차피
    `BS_Movement`가 담당하므로 상관없음.
- 웅크림/무릎/엎드림 상태에서는 이 레이어가 어떻게 겹쳐야 하는지(예: 무릎쏴는 원래 총 든
  포즈라 그대로 두되, 엎드림도 마찬가지) — 상태별 우선순위 정리가 필요, 다음 라운드에서
  스테이트 머신 전체 구조를 보면서 논의.
- **이 작업 자체(Layered Blend Per Bone 노드 구성)는 사용자가 에디터에서 직접 담당**
  (2026-08-04 확정 — AnimGraph 내부 노드 작업은 MCP 툴로 신뢰성 있게 못 함, 이전에도
  결과가 안 좋았음). 나는 어떤 소스를 어떻게 연결할지 설계/검토만 지원.

### 3-3-1. `AS_Run_Forward` 상체 그립 이슈 (확인됨, 해결책 없음 — 사용자 작업 필요)
`CaptureAssetImage`로 `AS_Run_Forward`/`AS_Run_Forward1` 썸네일을 직접 확인함 — 둘 다
총구가 정면을 향한 채(low-ready 아님) 달리는 포즈로 동일. **이 애셋 세트 안에는 대체할
low-ready 런 애니메이션이 없음.** 원본 키프레임(본 트랜스폼) 편집 도구는 내 MCP 툴셋에
없음(프로퍼티 읽기/쓰기만 가능, 커브/키프레임 에디터 없음) — 옵션:
(a) Persona에서 팔/총 본 직접 리포즈, (b) 외부 DCC에서 수정 후 재임포트, (c) 마켓플레이스
등에서 low-ready 런 애니메이션 별도 조달, (d) 위 3-3처럼 런타임에 상체만 다른 포즈로
레이어링(단, 뛰는 동안 팔이 하체 사이클과 안 맞게 흔들릴 수 있어 완벽하진 않음). 우선순위
낮음 — 이번 라운드 필수는 아님.

### 3-4. 시나리오 상태 → 자세 매핑 (사용자 요청 반영)
| 시나리오 단계 | 이동 | 무기 자세 | 비고 |
|---|---|---|---|
| FormingUp(집결 이동) | 뛰기(속도 범위 재조정 필요, 1절) | 내림 | "총 내리고 대기 및 뛰어서 이동" |
| FormingUp 도착 직후 | 정지 | 내림 | **신규**: UGV 정면 방향을 보도록 회전(`SetActorRotation`) — 지금 안 되고 있음 |
| Following(UGV 동반) | 걷기/뛰기(UGV 속도 따라감) | 내림 | |
| Approaching(집결지 도착 후 매복지 이동) | 걷기 | **들고 조준으로 전환** | "TP_UGVFormUpDestination 도착하면 경계자세 하면서 자기 엄폐 위치로 이동" — `BeginAllyApproach` 진입 시 토글 |
| Ambush(매복) | 정지 | 조준 유지 | `IsProne` 이미 세팅됨 |
| (미래) 엄폐 도착 | 정지 | 조준 | `AS_Crouching`을 "장애물 뒤 엄폐" 포즈로 사용(사용자 확정, 3-6-1 참고) — 이동 사이클은 필요 없음(엄폐 지점까지는 3-4의 다른 이동 포즈로 걸어가고, 도착 순간에만 전환) |

### 3-6-1. 엄폐 포즈 — `AS_Crouching` + 향후 레벨별 커스텀 가능하게 (사용자 요청, 2026-08-04)
`AS_Crouching`은 이동 사이클 없는 단일 포즈라 "웅크리고 걸어다니는" 용도가 아니라
**"장애물 뒤에 웅크려 엄폐"** 용도로 확정(사용자 확인 — 걸어다니는 크라우치는 없을 것으로
판단). 추가 요청: **나중에 엄폐용 애니메이션이 더 늘어나면(기대기, 다른 방향 엄폐 등),
레벨 디자이너가 각 아군 인스턴스별로 어떤 엄폐 포즈를 쓸지 에디터에서 직접 고를 수 있어야
함.**

**설계 제안**: `ECoverPoseType`(또는 유사한) enum 신설 — 처음엔 `Crouching` 하나뿐이라도,
`AllyFormationComponent`(또는 `AmbushMarker`)에 `EditInstanceOnly` 프로퍼티로
`ECoverPoseType CoverPoseType` 추가해서 레벨에서 아군 인스턴스마다 개별 지정 가능하게.
새 엄폐 애니메이션이 추가될 때마다 enum 값 + ABP 쪽 매핑(enum → AnimSequence)만 늘리면
되는 구조로 — 지금 `AmbushMarker`(액터 하드레퍼런스) 패턴과 같은 "레벨에서 인스턴스별
커스터마이즈" 철학 재사용. 실제 스위치 로직(엄폐 도착 시 이 enum 값 읽어서 어떤 애니메이션/
IsCrouching류 bool을 세팅할지)은 애니메이션이 1종류뿐인 지금은 자명하지만, 2종류 이상
늘어나면 ABP에도 대응하는 상태/블렌드 분기가 필요 — 그때 다시 설계.

### 3-5. 둘러보기(look-around) 유휴 변주
`IsLookingAround`/`AS_Enemy_Looking_Around` 이미 파이프는 있음 — **스켈레톤 호환 여부만
라이브로 확인**하면 됨. 안 맞으면: (a) 리타겟해서 아군 스켈레톤용으로 새로 굽거나, (b)
호환되는 다른 둘러보기 애셋을 찾거나 새로 제작.

### 3-6. 개체별 애니메이션 위상차(동기화 문제)
30명이 전부 같은 프레임에 Idle 루프를 시작해서 완전히 싱크됨. 표준 해법: `BeginPlay`에서
`AnimPhaseOffsetSeconds = FMath::FRandRange(0, IdleAnimLength)`를 한 번 랜덤 설정 →
ABP의 관련 Sequence Player 노드들의 "Start Position" 핀에 연결(상태 **진입 시 1회만**
평가, 매 틱 아님 — 안 그러면 위상이 계속 흔들림). Idle 상태 진입 시점에만 적용하면 충분 —
Walk/Run은 어차피 서로 다른 시점에 진입해서 자연스럽게 안 겹침.

---

## 4. 열린 질문

1. ~~`AS_RifleIdle`이 실제로 "총 든 정자세"가 맞는지~~ — **해결(사용자 확인): 맞음.**
2. `IsHoldingWeapon?`이 지금 AnimGraph 어딘가에서 실제로 소비되고 있는지 — **아직 모름**
   (사용자도 확실치 않음). MCP 툴로 AnimGraph 내부(스테이트머신 안쪽)를 못 읽어서
   (`read_graph_dsl`이 빈 문자열 반환, 이번에 확인됨) 에디터에서 직접 열어봐야 함 —
   3-3 작업(Layered Blend Per Bone)을 사용자가 직접 시작할 때 자연히 확인될 것.
3. ~~`AS_Crouching` 범위~~ — **해결(사용자 확정): 이동 없는 "장애물 뒤 엄폐" 전용으로.**
   3-6-1의 레벨별 커스텀 엄폐 포즈 시스템은 별도 설계/구현 필요(다음 라운드).
4. ~~속도 튜닝~~ — **해결**: `FormUpMoveSpeed` 600으로 상향 + `EscortMaxSpeedKmh`
   DistanceScale 버그 수정 완료(1절).
5. ~~Layered Blend Per Bone 스파인 본 확인~~ — **사용자가 직접 에디터에서 진행**(2026-08-04
   확정, 3-3 참고) — 내 쪽에서 더 조사할 필요 없음.

---

## 5. 범위 밖 (이번 설계에서 제외, 이전 대화 확정 사항)
- 타르코프식 풀 스텝-플래닝 로코모션 — 30명 동시 실행 비용 문제로 기각, 대신 Speed 블렌드
  스페이스 + (필요시) 가벼운 Foot IK로 타협.
- 장애물 기대 엄폐 포즈 — 애셋/IK 둘 다 미착수, 별도 라운드.
