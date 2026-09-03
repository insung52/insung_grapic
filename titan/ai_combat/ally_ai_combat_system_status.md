# 아군 AI 사격/엄폐 시스템 구현 현황 (2026-08-09)

> 무기/애니메이션 파이프라인(발사, 반동, 재장전, 왼손 IK)과 이동/조준방향 분리(`ally_move.md` Phase 0)가
> 끝난 뒤, AI 컨트롤러(`UAllyFormationComponent`)에 실제 전투 행동(사격/엄폐/재타겟팅)을 붙인 라운드.
> 계획 원본: 승인된 플랜 "AI 컨트롤러 사격/엄폐 행동 — FireAtEnemy 구현 + 커스텀 자세 시스템 + 조준
> 보정". 관련 코드: `Source/titan_example/Soldiers/AllyFormationComponent.h/.cpp`,
> `BP_ThirdPersonCharacter`, `BP_AR4Rifle`, `ABP_Ally_kadex2`.

---

## 1. 발사 로직 — `FireAtEnemy` 버스트 사격

`BP_ThirdPersonCharacter`의 `FireAtEnemy` 커스텀 이벤트가 완전히 빈 스텁이었던 것을 구현.

- `FireAtEnemy`: `BurstShotsRemaining`(int, 새 멤버 변수)을 3~4 사이 랜덤값으로 세팅하고 `FireBurstShot` 호출.
- `FireBurstShot`: `BurstShotsRemaining > 0`이고 `CurrentRifle`/`CurrentEnemy`가 유효하면 `Shoot()` 호출 →
  카운트 1 감소 → `Delay(FireRate + 0.05초)` → 재귀 호출. 0이 되거나 무기/적이 무효화되면 자연 종료.
- `BP_AR4Rifle.Shoot()`가 이미 `CanShoot?`/탄약 게이트와 `FireRate` 쿨다운을 자체적으로 갖고 있어서,
  이 위에서는 그 주기에 맞춰 반복 호출만 하면 됨 — 탄약이 떨어지면 `Shoot()` 내부에서 자동으로
  `StartReload()`가 트리거됨.
- `AllyFormationComponent::TickAmbush`가 매복 완료 + 타겟 존재 시 이 `FireAtEnemy`를 리플렉션으로
  호출하는 상위 게이트 역할(자세 시스템과 연동, 2절 참고).

### 발견/수정한 버그: "쿨다운 무시하고 계속 쏨"
`BP_ThirdPersonCharacter.EventTick`에 예전부터 있던 잔재 코드가 원인이었음 — `HasTarget`이 true인 동안
**매 틱 무조건** `FireAtEnemy`를 직접 호출하고, 총구 보정 없는 raw look-at으로 `SetActorRotation`도
매 틱 강제로 걸고 있었음. 이게 우리가 새로 만든 쿨다운/자세 게이팅을 완전히 무시하고 있었던 것 —
`BurstShotsRemaining`이 매 틱 새 랜덤값으로 리셋되면서 여러 재귀 체인이 겹쳐 돌았음. 두 줄 다 제거
(`AimPitch`/`TargetLocation` 갱신, 걷기속도 계산은 유지).

---

## 2. 커스텀 사격/엄폐 자세 시스템

`FiringPose`/`CoverPose`/`NoTargetPose` 3개의 `FAllyCombatPose`(마커 액터 참조 + 몸상태 +
기울임)를 아군 인스턴스마다 지정 가능. 하나라도 마커가 채워져 있으면(`IsCustomPoseSystemActive`)
이 시스템이 활성화되고, 기존 `ACoverPoint` 프리셋 사이클(`TickCoverPosture`)은 건너뜀 — 완전
병행 설계라 마커를 안 채운 기존 아군은 하위호환으로 그대로 동작.

```cpp
UPROPERTY(EditAnywhere, Category = "Ally|Combat|Pose")
FAllyCombatPose FiringPose;   // 타겟 있고 사격 차례
FAllyCombatPose CoverPose;    // 타겟 있고 사격 사이 대기(전술적 엄폐)
FAllyCombatPose NoTargetPose; // 타겟이 아예 없을 때(평소 대기) — 비워두면 CoverPose로 폴백
```

`FAllyCombatPose = { AActor* Marker; EAllyBodyPose(Standing/Crouched/Prone); EAllyLean(None/Left/Right); }`

### 4단계 명시적 상태머신 (`EAllyCombatPoseState`)
처음엔 Cover/Firing 2단계 + 암묵적 "도착했는지" 플래그로 짰다가, 타이밍 문제(아래 3절)를 겪으면서
"전환 중" 구간을 이름 있는 상태로 명시적으로 분리:

```
Cover → TransitioningToFiring → Firing → TransitioningToCover → (반복)
```

- **Cover**: 대기 위치 도착 완료, 랜덤 대기 타이머(`Min/MaxCoverPoseSeconds`, 기본 2~4초)가 흐름.
  타이머 만료 시 `TransitioningToFiring`으로.
- **TransitioningToFiring**: 조준 위치로 이동/회전 중. **위치**(`PoseArrivalToleranceCm`, 기본
  10cm, Z축 무시)와 **회전**(`FiringAimToleranceDeg`, 기본 5°) 둘 다 완료돼야 `Firing`으로 승격 —
  승격되는 그 틱부터 발사 허용(=정확히 조준 상태가 됐을 때만 쏨). 도착 자체를 못 하면 거리 기반
  안전 타임아웃 후 포기하고 `TransitioningToCover`로.
- **Firing**: 도착 즉시 `FireAtEnemy` 트리거(3~4발 버스트). 버스트가 실제로 끝나면
  (`BurstShotsRemaining==0`) 대기 없이 바로 `TransitioningToCover`로.
- **TransitioningToCover**: 엄폐 위치로 복귀 중. 도착+정렬되면 `Cover`로 승격(그때부터 대기
  타이머 새로 시작).

재장전 시작 시(타겟은 있지만 못 쏘는 상태)엔 `Firing`/`TransitioningToFiring` 어느 상태에 있든
즉시 `TransitioningToCover`로 강제 전환 — 조준 대기시간이 남아있어도 무시.

### 안전 타임아웃은 거리 비례 (`EstimateTransitionSeconds`)
전환 상태의 "포기" 타임아웃을 고정 랜덤값 대신 `거리 / PoseMoveSpeed + TransitionTimeBufferSeconds`
(기본 1.5초 버퍼)로 계산 — 두 마커가 멀리 떨어져 있으면 자연스럽게 더 기다려주고, 가까우면 금방
포기 판정이 걸리지 않음.

### 총구 기준 조준 보정
- **좌우(Yaw)**: 액터 정면이 아니라 총구가 실제로 적을 향하도록, 총구가 몸통 정면 대비 얼마나
  틀어져 있는지(블렌드스페이스 포즈에 따라 매 틱 달라짐) 보정해서 목표 Yaw 계산.
- **상하(Pitch)**: 액터엔 피치 축이 없어서 총(`CurrentRifle`) 자체의 상대회전을 매 틱 보정
  (`TickWeaponAimPitchCorrection`) — 왼손이 총의 그립 소켓을 IK로 따라가므로 총이 돌면 자동으로
  같이 보정됨, 애니메이션/IK 쪽은 손 안 댐. 숙인 채 걷는 자세처럼 원래 총구가 위로 들리는
  포즈에서도 이 보정으로 실제 조준선이 적을 향함.
- `TransitioningToFiring` 상태에서도(도착 전부터) 적 방향으로 돌기 시작하도록 처리 — 도착하자마자
  바로 쏠 준비가 되게.

---

## 3. 이동 속도/애니메이션 버그 — 근본 원인까지 추적한 것들

포즈 마커 사이 이동(몇 걸음, ~400cm)에서 연쇄적으로 발견된 문제들. 전부 원인을 끝까지 추적해서 고침.

- **"목표 지점 도달을 못 함"**: 실제로는 물리 문제가 아니라 상태머신 문제였음 — Cover 대기 타이머가
  실제 도착 여부와 무관하게 만료되면서, 걸어가는 도중 목표가 반대쪽 마커로 바뀌어 버림(2절의
  4단계 분리로 해결 — Cover 대기 타이머는 도착+정렬 후에만 흐름).
- **"가까워질수록 애니메이션이 되레 빨라짐"**: `ABP_Ally_kadex2`의 `Speed` 계산식이
  `실제속도 / MaxWalkSpeed`를 정규화 비율로 쓰는데, 도착 감속 램프가 `MaxWalkSpeed` 자체를 계속
  줄이는 상황에서 실제속도가 그 목표를 못 따라가면 비율이 1을 넘어 애니메이션이 300/600 범위를
  초과해버림. `Math|Float|Clamp(Float)`로 비율을 [0,1] 클램프해서 1차 수정.
- **"실제속도는 관성 따라 느려지는데 애니메이션은 고정 속도로 재생"**: 클램프 이후에도 남은
  문제 — 분모(`MaxWalkSpeed`)가 AI 감속 램프로 계속 같이 줄어드니 비율이 항상 1 근처에 붙어서,
  절대 속도 정보가 사라짐(정상 걷기 속도로만 보임). **근본 수정**: `BP_ThirdPersonCharacter`에
  `GaitTopSpeed`(그 자세의 "원래" 최고속도, AI 램프가 안 건드리는 값) 변수를 신설, `EventTick`이
  매 틱 gait 공식 계산값을 `MaxWalkSpeed`와 `GaitTopSpeed` 양쪽에 저장. `ABP_Ally_kadex2`의 비율
  분모를 `GetMaxWalkSpeed()` 대신 `GetGaitTopSpeed()`로 교체 — 이제 분모가 고정이라 실제속도가
  느려지면 비율도 같이 줄어 애니메이션이 비례해서 느려짐. WASD 플레이어 쪽은 원래 `MaxWalkSpeed`가
  안 바뀌니 회귀 없음.
- **"너무 느리게 이동함"**: 범용 `ApproachSlowdownDistanceCm`(300cm, Following/Approach 같은
  장거리 이동용으로 튜닝됨)를 그대로 쓰면, 짧은 포즈 전환(~400cm)에서 감속 램프 구간이 이동거리
  대부분을 잡아먹음. 포즈 전용 `PoseApproachSlowdownDistanceCm`(60cm)로 분리, `MoveToward`에
  override 파라미터 추가.
- **"속도가 비연속적으로 바뀜"**: `MoveToward`가 램프 계산 결과를 `MaxWalkSpeed`에 매 틱 바로
  대입하던 걸, 기존 `SmoothedMovementDirection`(방향 관성, `RInterpConstantTo`)과 같은 패턴으로
  `SmoothedMaxWalkSpeed` + `MaxWalkSpeedAccelerationCmPerSec2`(기본 800cm/s²)를 도입해서
  속도 변화 자체도 매끄럽게(가/감속에 상한).

---

## 4. 타겟 재획득 버그

**증상**: 적 여러 명을 배치한 뒤 하나를 죽이면, 나머지가 사거리 안에 있어도 새 타겟을 안 잡고
계속 엄폐만 함.

**원인**: `OnComponentBeginOverlap`은 "새로" 겹치는 전이에만 반응함. 여러 적이 처음부터 다 감지
범위 안에 있었다면, 죽은 적 말고 다른 적들은 그 시점에 이미 겹쳐 있던 상태라 델리게이트가 다시
안 불림 — 감지 활성화 시점의 "이미 겹쳐있던 적 직접 확정" 로직(이전 라운드에 추가)과 똑같은 종류의
문제가 "타겟을 잃는" 모든 순간에 재발함.

**수정**: 그 로직을 `TryAcquireTargetFromOverlaps()`로 추출해서 공용화. `SetDetectionEnabled(true)`
시점뿐 아니라, `TickAmbush`에서 `HasTarget`이 false로 확인될 때마다(방금 잃었든 이미 없었든) 매 틱
재시도 — 스피어에 이미 겹쳐있는 다른 후보가 있으면 즉시 새 타겟으로 확정.

---

## 5. 탄 퍼짐 (Bullet Spread)

`BP_AR4Rifle`에 `BulletSpreadDegrees`(float, 인스턴스 편집 가능, 기본 1.5°) 신설. 발사 시 총구
정면 방향 기준 이 각도의 원뿔 안에서 `RandomUnitVectorInConeInDegrees`로 랜덤 방향을 뽑아서,
투사체 스폰 회전과 실제 물리 속도 벡터 양쪽에 동일하게 적용(트레이서 방향과 탄도가 항상 일치).
0으로 두면 기존처럼 완벽한 명중. 아군마다 다른 값을 줘서 정확도 차등 연출 가능
(예: 일반 아군 3~5°, 정예 0.5° 이하).

---

## 6. 재장전 사운드 + 어태뉴에이션

기존엔 재장전 사운드가 **아예 없었음**(`BP_AR4Rifle.StartReload`에 오디오 노드 자체가 없었고,
재장전 애니메이션 `AS_Reloading`의 노티파이 트랙에도 사운드가 없었음 — 에셋 종속성 조회로 확인).

- `SA_Weapon`(`/Game/Soldiers/Weapons/SA_Weapon`) — 무기 소리 전용 `SoundAttenuation` 신규 생성
  (`SA_Footstep`을 베이스로 복제, 무기 사거리에 맞게 확대: 풀볼륨 반경 1500cm,
  8000cm 지점에서 -60dB 감쇠, `NaturalSound` 알고리즘).
- 총소리(`assault_rifle_gunshot_01`)와 재장전 SFX 3종(전부 `FreeWeaponSounds/AssaultRifle/`
  기존 팩에서 발견) 모두 `SA_Weapon`을 어태뉴에이션으로 지정.
- `StartReload`에 3단계 순차 재생 추가: 탄창 빼기 → 0.6초 → 탄창 넣기 → 0.7초 → 노리쇠 → 0.7초 →
  재장전 완료(기존 고정 2초 재장전 시간에 맞춰 분배).

**미해결**: 새로 건드린 사운드 웨이브 4개(`/Game/NiagaraExamples/...` 경로, 이번에 처음 수정)가
Perforce 체크아웃이 안 돼서 디스크 저장이 실패함 — 현재 에디터 세션에는 속성이 반영돼 있지만,
에디터를 재시작하면 날아갈 수 있음. **체크아웃 필요**:
- `.../AssaultRifle/Gunshots/assault_rifle_gunshot_01`
- `.../AssaultRifle/Foley/01_assault_rifle_reload_1_drop_the_mag`
- `.../AssaultRifle/Foley/02_assault_rifle_reload_1_insert_the_mag`
- `.../AssaultRifle/Foley/03_assault_rifle_reload_1_bolt`

---

## 7. 남은 작업 / 알려진 이슈

- 22종 애니메이션 시퀀스(디자인팀 요청 `ally_animation_request.md`) 도착 후 블렌드스페이스/State
  Machine 정식 재구성 — 별도 트랙, 미착수.
- 위 6절의 사운드 웨이브 4개 P4 체크아웃 후 저장 재시도 필요.
- 레벨에 여러 아군 배치 + `FiringPose`/`CoverPose`/`NoTargetPose` 마커 실제 설치는 사용자가 직접
  진행(코드/시스템은 완성).
- 사격선 안전장치(`FireLaneAllyMarginCm`, 다른 아군이 사격선에 걸리면 보류)는 이번 자세 시스템과
  독립적으로 계속 동작 — 추가 작업 불필요.

---

## 8. 추가 수정 (2026-08-12, 적군 라운드 중 발견)

**버스트 도중 조기 엄폐 버그**: 2절의 `Firing` 상태는 `BurstShotsRemaining==0`이 될 때까지 기다렸다가
`TransitioningToCover`로 넘어가도록 짜여 있었지만, 그 직전에 있는 "타겟 없거나 재장전 중이면 즉시
강제 전환" 분기(`bForceCover`)가 이 조건을 안 보고 있었음 — 그래서 3~4발 버스트를 쏘는 도중에 상대가
죽어서 `HasTarget`이 풀리면, 남은 탄을 다 쏘기도 전에 바로 몸을 돌려 `TransitioningToCover`로
넘어가버리고(마지막 발이 이미 돌아가는 중이라 땅에 맞음). 이미 트리거된 버스트
(`bFiringBurstTriggered && BurstShotsRemaining>0`)는 다 쏠 때까지 이 강제 전환을 건너뛰도록 예외
추가. 적군 쪽(`EnemyCombatComponent.cpp`)에도 동일한 구조라 같이 수정함 —
`enemy_ai_combat_system_status.md` 6절 참고.

---

## 9. 관련 코드 위치

| 기능 | 파일 |
|---|---|
| 자세 상태머신, 조준 보정, 타겟 재획득, 이동 관성 | `Source/titan_example/Soldiers/AllyFormationComponent.h/.cpp` |
| 버스트 사격(`FireAtEnemy`/`FireBurstShot`), gait 최고속도(`GaitTopSpeed`) | `BP_ThirdPersonCharacter` EventGraph |
| 발사(`Shoot`, 탄퍼짐), 재장전(`StartReload`, 사운드) | `BP_AR4Rifle` EventGraph |
| 발걸음 애니메이션 속도(`Speed`) 계산 | `ABP_Ally_kadex2` EventGraph |
| 무기 사운드 어태뉴에이션 | `SA_Weapon` (`/Game/Soldiers/Weapons/`) |
