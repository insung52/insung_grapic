# 3차 전투지 도주 미발동 수정 + 동적 분대 재배정 + 사상자 로그

2026-09-03 / 코드·DataTable 모두 반영 완료, 2차 빌드 후 PIE 재검증만 남음(1차 검증에서 3차 도주 3명 확인) / `BeginFlee`가 도주 중 개체의 다음 도주 명령을 버려서 3차 전투지가 통째로 안 열리던 버그를 고치고, 전투지별 인원을 정원제(2차 10명 / 3차 5명)로 채우는 동적 분대 재배정과 사상자 진단 로그를 추가.

선행 문서: `2026-08-31_enemy_squad_reorg.md`(분대 재편·`LastStandZoneIndex`·분대별 경로),
`../level_new_kadex_0811/scenario_three_stage_combat.md`(스텝 테이블 구조),
`../level_new_kadex_0811/2026-09-01_scenario_run_modes_demo_fullsystem.md`(데모 모드).

---

## 1. 증상

사용자 리포트: **"적군이 생각보다 너무 빨리 죽어서 3차 전투지로 이동하는 3분대 인원이 전혀 없다."**
데모 모드로 완주해도 3차 전투(이동형지휘소 RCWS 교전)가 한 번도 안 열림.

## 2. 원인 — `BeginFlee`가 "이미 도주 중"이면 명령을 통째로 버렸다

`UEnemyCombatComponent::BeginFlee` 첫 줄이 이랬다:

```cpp
if (CurrentState == EEnemyState::Flee)
{
    return; // 이미 도망 중 — 중복 호출 무시.
}
```

의도는 "같은 도주 명령의 중복 호출 무시"였는데, 실제로는 **더 앞선 전투지로 가라는 새 명령까지
같이 버려진다.** 그리고 스텝은 `FiredScenarioSteps`에 들어가므로 재발동도 없다 — 한 번 놓치면 끝.

### 왜 반드시 걸리는가 — 레벨 실측

`New_kadex_0811`의 적 15기 전수 조사(MCP, 2026-09-03):

| 분대 | 개체 | `SquadId` | `LastStandZoneIndex` | 스폰→1차 | 1차→2차 | 2차→3차 |
|---|---|---|---|---|---|---|
| 1분대 | 1~5 | 1 | 0 | 260~266m | — | — |
| 2분대 | 6~10 | 2 | 1 | 287~326m | 184~203m | — |
| 3분대 | 11~15 | 3 | 2 | 336~360m | 212~222m | 360~367m |

`FleeMoveSpeed = 400cm/s`(15기 전부 동일) → **1차→2차 도주만 55~60초**(내비 우회 포함 ~65초).
`MinFleeCommitDelaySeconds`~`Max` 0.5~3초가 앞에 더 붙는다.

반면 스텝 테이블(`DT_ScenarioSteps_ThreeStage`) 값은:

| RowName | Trigger | 값 | Prereq |
|---|---|---|---|
| `EnemyFleeToZone2` | `EnemyCasualtyCountAtLeast` | **3** | (없음) |
| `EnemyFleeToZone3` | `EnemyCasualtyCountAtLeast` | **7** | `EnemyFleeToZone2` |

3명→7명은 **4명만 더 죽으면** 된다. 데모 모드 UGV RCWS는 `bDemoForceUGVAutoFire`로 ARM+AutoFire
상태고 1초 간격 3점사라, 이 4명은 도주 55~60초보다 훨씬 빨리 채워진다.

**결과**: 3분대는 2차로 뛰는 도중에 3차 도주 명령을 받고 → `CurrentState == Flee`라 조용히 버려지고
→ 2차에 도착해 거기서 전멸. 3차 전투지에 아무도 안 간다. **적이 빨리 죽을수록 더 확실하게 재현된다.**

### ★ 기존 로그로 확정됨 (빌드/재실행 불필요)

`ExcludeFleeingEnemies` 이펙트는 `GetCurrentZoneIndex() >= 2`인 적을 세서 이미 로그를 찍고 있었다.
`Saved/Logs`의 지난 실행 두 건이 그대로 증거다:

| 실행(로그 UTC) | `EnemyFleeToZone2` | `EnemyFleeToZone3` | 간격 | `도주 분대 N명` |
|---|---|---|---|---|
| 09-02 07:58 | 07:58:06 | 07:58:18 | **12.0초** | **1명** |
| 09-03 01:36 | 01:36:23 | 01:36:46 | **23.1초** | **0명** |
| 09-03 02:09 | 02:09:34 | 02:09:45 | **10.6초** | **0명** |
| 09-03 02:16 | 02:16:25 | 02:16:35 | **10.2초** | **0명** |

4개 실행 전부 동일. 우연이 아니라 구조적 재현이다.

**1차→2차 도주에 55~60초가 걸리는데 3차 도주 명령이 12~23초 만에 온다.** 명령이 도착하는 시점에
3분대는 전원 `Flee` 상태 한복판이고, 그래서 5명 중 0~1명만 3차로 갔다. 예측과 정확히 일치한다.

### 전체 타임라인 (2026-09-03 01:33 실행, 데모 모드 완주)

| 시각 | +초 | 스텝 |
|---|---|---|
| 01:33:32 | +0 | `EnemyApproach` — 경계 이동 시작 |
| 01:34:41 | +69 | `UAVSpotted` — UGV 출발 |
| 01:36:08 | +156 | `EnemyEngage` — UGV RCWS 최초 근거리 사격 |
| 01:36:23 | +171 | `EnemyFleeToZone2` — **교전 15초 만에 3명 사망** |
| 01:36:46 | +194 | `EnemyFleeToZone3` — 다시 23초 만에 7명 |
| 01:38:19 | +287 | `ScenarioComplete` — 15명 전멸 |

완주 **4분 47초** 중 **156초(54%)가 전투 전 경계 이동**이고, 15명이 죽는 데는 131초밖에 안 걸린다.
"적이 너무 빨리 죽는다"는 리포트가 수치로 확인된다 — 교전 시작 15초 만에 3명이 죽는 템포다.

### ★ "왜 이렇게 빨리 죽는가"의 산수 — 한 점사 = 정확히 1킬

이건 튜닝이 어긋난 게 아니라 **숫자가 딱 맞아떨어져서** 생긴 일이다:

| 값 | 위치 | 크기 |
|---|---|---|
| 적 체력 | `BP_Enemy_kadex` 인스턴스 `Health` | **100** |
| RCWS 탄 1발 피해 | `Vehicles/RCWSProjectile.h` `DamagePerHit` | **34** |
| 점사 발수 | `RCWSFireControl.BurstRoundCount` | **3** |
| 점사 주기 | `AutoFireCycleIntervalSeconds` | **1초** |
| 연사 속도 | `FireRateRPM` 1200 → 발간 간격 | 0.05초 |

**34 × 3 = 102 ≥ 100.** 3점사가 다 맞으면 정확히 한 명이 죽고, 그게 1초에 한 번씩 돈다.
이론상 **초당 1킬**이고, 실측(10초에 4킬)은 락온 0.6초 + 포탑 슬루 + 명중률까지 포함한 값이다.

즉 3단계 시나리오 전체(적 15명)를 **UGV 혼자 15~20초면 이론상 정리**할 수 있는 화력이다.
도주에 55~60초가 걸리는 지오메트리와는 애초에 자릿수가 안 맞는다.

### 곁가지 — 같은 뿌리의 두 번째 구멍

`PendingFleeDelayRemaining` 카운트다운이 **`TickCombat`에만** 있었다. 그래서 아직 1차 전투지로
걸어가는 중(`Move` 상태)에 도주 명령을 받은 개체는 예약만 되고 영영 커밋되지 않는다. 예전엔
도주 대상이 이미 도착해 `Combat`을 돌고 있는 게 보통이라 잘 안 드러났지만, 아래 동적 재배정으로
1분대(=아직 걷고 있을 수 있는 개체)까지 도주 대상이 되면서 실제로 걸리는 경로가 됐다.

## 3. 수정 ①  `BeginFlee` — 단조증가 판정으로 교체

zone 인덱스는 항상 증가한다는 점을 이용해, "지금 가고 있는 곳보다 뒤면 무시, 앞이면 받아들여
목적지를 다시 잡는다"로 바꿨다. 중복 호출 무시라는 원래 목적은 그대로 지켜진다.

```cpp
const int32 CommittedZone = (PendingFleeZoneIndex != INDEX_NONE) ? PendingFleeZoneIndex : CurrentZoneIndex;
if (NextZoneIndex <= CommittedZone) return;   // 중복/역행 명령만 무시
```

카운트다운은 `TickMove` / `TickCombat` / `TickFlee` **세 곳 전부**에 넣었다.

> 연출 참고: 이제 3분대는 2차로 뛰던 도중에 방향을 틀어 3차로 간다(2차에서 멈췄다 가는 게 아님).
> 2차에서 한 번 교전하는 그림을 원하면 그건 **임계값 7을 늦추는 것**으로 조정할 문제다 —
> 4절의 사상자 로그가 그 튜닝에 필요한 실제 타임라인을 준다.

## 4. 수정 ②  동적 분대 재배정 — 전투지별 정원제

사용자 요청: *"2차로 이동할 때 2/3분대가 몇 명 죽었다면 1분대가 대신 그 역할을 해서 무조건 10명이
2차로 이동하고, 3차도 무조건 5명이 이동 시작. 너무 많이 죽여서 10/5보다 남은 인원이 없으면 어쩔 수 없고."*

### 왜 그냥 브로드캐스트로는 안 되는가

기존 `BeginEnemyFleeToZone`은 살아있는 적 전원에게 `BeginFlee(N)`을 뿌리고, 각자 자기 zone 마커가
있으면 갔다. 그런데 **1분대는 `CombatZones`가 1개(1차만), 2분대는 2개**다(2026-08-31 저작). 즉
이동 인원 = 그 분대의 생존자 수로 고정이고, 대체가 원리적으로 불가능했다.

### 구현 — 죽은 개체의 "역할"을 산 개체가 물려받는다

`UEnemyCombatComponent`:

```cpp
bool HasCombatZoneRole(int32 ZoneIndex) const;     // 마커 있음 + LastStand 게이트 통과
bool HasAuthoredCombatZone(int32 ZoneIndex) const; // 마커만 봄(죽은 개체의 빈 역할 회수용)
const FEnemyCombatZone& GetAuthoredCombatZone(int32 ZoneIndex) const;
void AdoptCombatZoneRole(int32 ZoneIndex, const FEnemyCombatZone& Role);
```

`AdoptCombatZoneRole`은 배열이 짧으면 늘리고, **`LastStandZoneIndex`도 같이 올린다** — 안 올리면
`BeginFlee`가 바로 그 게이트에서 거절해서 물려받은 의미가 없어진다.

`UScenarioStateSubsystem::BeginEnemyFleeToZone(N)` 절차:

1. **정원과 빈 역할의 기준은 시나리오 시작 시점 스냅샷**(`ScenarioZoneRoles`)이다.
   실행 중에 세면 안 된다 — 죽은 적은 액터째 파괴돼서 마커까지 같이 사라지기 때문(5.5절에서
   실제로 이 함정에 빠졌다: 정원 10→9, 5→3). 생존 판정만 현재 상태에서 본다.
2. **정원** = 스냅샷에 그 zone 마커가 있던 개체 수(New_kadex_0811이면 자동으로 2차 10 / 3차 5).
   `AScenarioConfig::FleeQuotaZone2/3`가 0이 아니면 그 값이 이긴다.
3. 이미 그 역할을 가진 생존자를 먼저 넣는다(원소속).
4. 부족분은 **죽은 개체의 역할**을 생존자에게 넘긴다. 우선순위는
   ① 지금 더 앞선 전투지에 있는 개체(뒤에 처진 낙오자가 먼 길을 되돌아 뛰는 그림 방지)
   ② 그 역할 마커에 더 가까운 개체.
5. 뽑힌 인원에게만 `BeginFlee(N)`.

**저작해둔 포즈 배치가 그대로 유지되고 인원만 채워지므로 레벨 저작은 손댈 필요가 없다.**

> 왜 정원을 "저작된 마커 수"에서 자동으로 뽑는가: 레벨 저자가 마커를 놓은 순간 이미 "2차에 10자리,
> 3차에 5자리"를 표현한 것이다. 숫자를 두 군데(마커/설정값)에 적어두면 반드시 어긋난다.

### 로그

```
[ScenarioStateSubsystem] 2차 전투지 도주 배정 — 정원 10명(저작 역할 10) | 이동 10명(원소속 7 + 승계 3),
    잔류 2명 | 생존 12명 [1분대 4/5, 2분대 3/5, 3분대 5/5]
    승계: BP_Enemy_kadex_C_2(1분대) <- BP_Enemy_kadex_C_7(2분대)의 자리
```

정원을 못 채우면 `Warning`으로 따로 찍는다.

## 5. 추가 — 사상자 로그 (진단)

이 시나리오는 완주에 5분 가까이 걸려서(대부분이 전투가 아니라 `PatrolMoveSpeed=150cm/s`로
260~360m를 걷는 **경계 이동 173~240초**다) 눈으로 보며 디버깅하는 비용이 너무 크다.
**실행 한 번의 로그만으로 전투 템포를 재구성**할 수 있게 했다.

```
[적 사상] +142.3초 | 누적 7명 사망 (생존 8) | BP_Enemy_kadex_C_12 3분대 |
    상태=도주중 전투지=2차 | 위치=(12043, -3388, 7131) |
    최근피격 0.4초 전 by BP_UGV_0901 | 누적피해 187 (12발) | 1분대 0/5, 2분대 4/5, 3분대 4/5
```

- **사망 판정은 새로 만들지 않았다** — 기존 경로(BP `IsDead` → 폴링 →
  `UDetectableTargetComponent::SetIncapacitated(true)`)의 false→true 전이만 스텝 틱(0.2초)에서 잡는다.
- **"누가 죽였는가"**: `UEnemyCombatComponent::BeginPlay`가 Owner의 `OnTakeAnyDamage`에 붙어
  마지막 피격의 출처를 들고 있는다. `DamageCauser`가 투사체면 그 `Owner`(없으면 `InstigatedBy`의
  폰)까지 거슬러 올라가서 `BP_UGV_0901` / `BP_TitanTruck` / `BP_Ally_kadex_*` 같은 실제 사수 이름이 남는다.
  데미지가 표준 `ApplyPointDamage` 경로라 **BP 수정이 전혀 필요 없다.**
- **성능**: `TObjectIterator`는 전체 UObject 배열을 훑으므로 매 틱 돌리면 안 된다. 감시 명단을
  캐시하고 5초에 한 번만 갱신한다(늦게 스폰되는 적 대비).

## 5.5 1차 검증 결과 (2026-09-03 02:36 실행) — 동작함, 그리고 새 버그 하나

빌드 후 첫 실행. `AutoFireCycleIntervalSeconds`는 사용자가 1 → **3초**로 낮춘 상태.

```
2차 전투지 도주 배정 — 정원 9명(저작 역할 9) | 이동 9명(원소속 8 + 승계 1), 잔류 3명 | 생존 12명 [1분대 4/4, 2분대 5/5, 3분대 3/4]
3차 전투지 도주 배정 — 정원 3명(저작 역할 3) | 이동 3명(원소속 3 + 승계 0), 잔류 5명 | 생존 8명 [1분대 0/1, 2분대 5/5, 3분대 3/3]
도주 분대 3명을 아군/UGV 타겟에서 제외 — 이동형지휘소만 교전.      ← 예전엔 0명
```

**3차 전투지에 3명이 도착했다** — 원래 목적은 달성. 승계도 실제로 한 번 발동했다.

### ★ 새 버그 — 죽은 적 액터가 파괴되면서 정원이 깎인다

정원이 의도한 10/5가 아니라 **9/3**이고, 분대 총원이 13명 → 9명으로 **줄어든다**(15명이어야 함).

원인: 5.1절 구현이 "이 월드의 적군 컴포넌트를 죽은 것까지 포함해 `TObjectIterator`로 센다"였는데,
**죽은 적은 잠시 뒤 액터째 파괴된다.** 시체가 랙돌로 남아 있을 거라는 전제가 틀렸다. 액터가 사라지면
그 개체가 들고 있던 `CombatZones` 배열(=전투지 마커)도 같이 사라지므로:

- **정원**(그 zone에 저작된 역할 수)이 시체 치워지는 속도만큼 깎인다 → 10→9, 5→3.
- **빈 역할**(승계의 재료)도 같이 사라져서 채울 수단이 없어진다 → 3차 승계 0명.

즉 "너무 많이 죽여서 남은 인원이 부족"한 게 아니라 **살아있는 후보가 5명 넘게 있는데도 정원이 3으로
줄어서 3명만 보낸 것**이다(생존 8명, 잔류 5명).

### 수정 — 시작 시점 스냅샷

`BeginScenarioSteps`(전원 생존)에서 전투지 역할 명단을 한 번 뜬다:

```cpp
USTRUCT() struct FScenarioEnemyZoneRole
{
    UPROPERTY() TWeakObjectPtr<UEnemyCombatComponent> OriginalOwner;  // 죽어 사라지면 그게 곧 "빈 역할"
    UPROPERTY() int32 ZoneIndex;
    UPROPERTY() FEnemyCombatZone Role;                                 // 마커 포함 — 액터가 사라져도 남는다
};
UPROPERTY() TArray<FScenarioEnemyZoneRole> ScenarioZoneRoles;
TMap<int32, int32> ScenarioSquadTotals;   // 생존 현황의 분모도 같은 이유로 스냅샷
```

`UPROPERTY`로 둔 이유는 GC — `FEnemyCombatZone` 안의 마커가 `AActor*` 생포인터라 일반 멤버 배열에
담으면 GC가 참조를 못 본다(마커는 레벨 배치 액터라 실제 수거될 일은 없지만 원칙대로).

스냅샷 직후 로그도 추가했다 — 정원이 의도와 다르면 저작 문제이므로 여기서 바로 드러난다:

```
[ScenarioStateSubsystem] 적군 전투지 역할 스냅샷 — 적 15명 | 1차 15자리, 2차 10자리, 3차 5자리 | [1분대 5/5, 2분대 5/5, 3분대 5/5]
```

## 5.6 도주 중 사격 보류 (2026-09-03, 사용자 요청)

> "3차 전투지로 도망가는 적군이 계속 자기 도망가는 거 광고하듯 아군한테 쏨. 3차로 도망 시작하고
> 10초 정도 뒤부터는 계속 이동만 하고 총은 안 쏘게. 물론 truck RCWS가 사격 시작하면 그때는 truck에 쏴야 함."

기존 `bTargetableByAlliesAndUGV`("아군/UGV가 이 적을 안 쏨")와 **방향이 반대인 짝**을 만들었다.

### 구현 — 새 사격 게이트를 만들지 않고 감지 게이트를 재사용

```cpp
void UEnemyCombatComponent::SetFireHold(bool bNewHold)   // Enemy|Combat
{
    bFireHold = bNewHold;
    if (bNewHold) { SetDetectionEnabled(false); ForceRetarget(); }
    else          { SetDetectionEnabled(bEngaged); }
}
```

감지가 꺼지면 `PickTargetFromOverlaps`가 후보를 안 잡아 `HasTarget`이 false로 남고, 그러면
`TickFlee`의 사격 블록이 통째로 스킵되는 **동시에** 몸이 조준방향이 아니라 이동방향을 본다
(`bFaceMovementDirection=true` 폴백). "그냥 달려서 도망가는" 그림이 공짜로 나온다 — 교전 전
경계 이동에서 이미 검증된 경로라 새 분기를 안 늘리는 쪽을 택했다.

`SetDetectionEnabled`에 초크 포인트를 하나 뒀다 — `bDetectionEnabled = bEnabled && !bFireHold`.
보류를 감지 게이트로 구현했으므로, 다른 경로가 무심코 감지를 되살리면 보류가 풀려버리기 때문.

### 켜기/끄기 — 새 행은 하나만

| | 무엇이 | 언제 |
|---|---|---|
| **켜기** | `EScenarioEffectType::HoldFleeingEnemyFire`(신설) — `CurrentZoneIndex >= 2`인 생존자에게 `SetFireHold(true)` | **신규 DT 행** `HoldFleeingFire`: prereq `EnemyFleeToZone3`, TimerOnly **10초** |
| **끄기** | 기존 `RetargetEnemiesToCommandPost` 이펙트 끝에 `ReleaseEnemyFireHold()` 추가 | 기존 `RetargetToCommandPost` 행 그대로(트리거 `CommandPostFiredNearEnemy` 8000) |

해제 행을 새로 안 만든 이유: "트럭이 실제로 쐈다"가 곧 재교전 시점이고, 그때 타겟을 지휘소로
바꾸는 이펙트가 이미 있다. **순서 주의** — 선호도를 먼저 지휘소로 바꾼 뒤 보류를 풀어야
감지가 켜지는 순간 잡히는 타겟이 트럭이 된다(그래서 `RetargetAllEnemies` 다음 줄에 넣었다).

> ⚠️ **신규 DT 행은 리빌드 후에 넣어야 한다.** `HoldFleeingEnemyFire`가 새 UENUM 값이라
> 빌드 전에는 에디터가 그 이름을 몰라서 `set_rows`가 실패한다.
>
> **2026-09-03 12:26 — 리빌드 후 MCP로 추가·저장 완료.** 행 `HoldFleeingFire`:
> prereq `EnemyFleeToZone3` / `TimerOnly` 10초 / effect `HoldFleeingEnemyFire` / `bEnabled=true`.
> `.uasset`을 `p4 edit`으로 체크아웃해야 저장이 됐다(안 하면 `save_assets`가 조용히 false를
> 반환하고 dirty 상태로 남는다 — 반드시 `is_dirty`로 되확인할 것).

## 5.7 사상자 로그 첫 수확 — 02:36 실행 전수 분석

사격 주기 3초 상태. 시나리오 시작 02:32:57, 마지막 사망 02:39:03 → **완주 6분 6초**.

| # | +초 | 개체 | 분대 | 상태 / 전투지 | 사살자 |
|---|---|---|---|---|---|
| 1 | 170.8 | C_1 | 1 | **이동** / 1차 | UGV |
| 2 | 180.0 | C_11 | **3** | **이동** / 1차 | UGV |
| 3 | 187.2 | C_14 | **3** | **이동** / 1차 | UGV |
| 4 | 193.2 | C_2 | 1 | 도주중 / **2차** | UGV |
| 5 | 201.0 | C_4 | 1 | 교전 / 1차 | UGV |
| 6 | 203.2 | C_3 | 1 | 교전 / 1차 | UGV |
| 7 | 214.8 | C_5 | 1 | 교전 / 1차 | UGV |
| 8 | 250.2 | C_12 | 3 | 도주중 / **3차** | **아군 소총** |
| 9~13 | 275~319 | C_6,7,10,9,8 | 2 | 교전 / 2차 | **전부 UGV** |
| 14 | 349.2 | C_13 | 3 | 도주중 / 3차 | **트럭** |
| 15 | 364.6 | C_15 | 3 | 도주중 / 3차 | **트럭** |

읽히는 것 5가지:

1. **3차로 갈 3분대가 1차 전투 시작 전에 갈린다.** 최초 3명 중 **2명이 3분대**(C_11, C_14)이고,
   둘 다 상태가 `이동` — 아직 1차 전투지로 **걸어가는 중**에 UGV가 잡았다. UGV는 분대를 구분하지
   않고 가까운 순으로 쏘므로 구조적이다. 동적 재배정이 정확히 이 손실을 메우는 장치다.
2. **승계가 실제로 발동했다** — #4 `C_2(1분대)`가 `도주중 / 2차`. 1분대는 원래 2차 마커가
   없으니, 죽은 개체의 자리를 물려받아 간 것이다.
3. **3차 전투는 실제로 성립했다** — #14·#15를 **트럭이** 잡았다. 원래 목표 달성.
4. **2차 전투지의 적 5명을 전부 UGV가 잡았다.** 아군 매복이 화력에 거의 기여하지 않는다
   (아군 명중률은 2026-09-01에 3.0°로 너프됨). 연출상 아군이 잡아야 한다면 별도 조정 필요 — 이번 범위 밖.
5. **#8이 버그를 드러냈다** — 아래.

### ★ 버그 — 아군이 "교전 제외된" 적을 계속 쏜다

`ExcludeFleeingEnemies`는 02:36:37.6에 발동해 3명을 제외 처리했는데, **그 31초 뒤인 02:37:08.8**에
3차로 도주 중이던 C_12가 **아군 소총탄**에 죽었다.

원인: 제외 게이트(`IsTargetableByAlliesAndUGV`)가 `UAllyFormationComponent::TryAcquireTargetFromOverlaps`
안에만 있다. 그건 **타겟이 없을 때만 도는 획득 경로**라, 제외가 걸리기 전에 이미 그 적을 조준 중이던
아군은 영향을 안 받고 계속 쏜다.

수정: 아군의 매 틱 타겟 유효성 재검증 블록(`!IsValid(Enemy)`이면 놓아주던 곳)에 제외 검사를 같이 넣었다.
놓아주면 바로 아래 재획득 블록이 제외되지 않은 다른 적을 잡는다.

> UGV RCWS 쪽은 같은 문제가 없다 — `URCWSFireControlComponent`는 매 틱 탐지 목록을 다시 훑으므로
> 게이트가 매번 적용된다. 로그에서도 제외 이후 UGV가 3차 도주 분대를 한 명도 안 잡았다.

### 곁가지 — 아군 소총탄은 사수 이름이 안 남았다

`최근피격 by BP_RifleProjectile_C_547`. RCWS 투사체는 `Owner`가 채워져 있어 `BP_UGV_0901`이
제대로 찍히는데, 아군 소총탄은 비어 있었다. `Owner`가 없으면 `InstigatedBy`의 폰으로 폴백하도록 고쳤다.

### 주의 — 나중에 적을 추가할 때 (02:48 이후 실행에서 관찰)

02:48~49 실행 로그에 `BP_Enemy_kadex_C_16 0분대`가 있다(현재 레벨엔 없음 — 그 사이 지운 듯).
트럭 바로 옆(50278, 12618)에 있었고 **시나리오 시작 0.3초 만에 트럭 RCWS에 사살**됐다.

이유 두 가지 — 새로 배치하는 적마다 걸린다:

- `DetectableTarget.bIsRevealed`가 기본 **true**다. 기존 15명은 전부 false로 내려둬서 `RevealEnemies`
  스텝(+69초) 전까지 탐지 자체가 안 되는데, 새로 놓은 액터는 처음부터 탐지·피격 대상이 된다.
- 데모 모드는 트럭 RCWS도 레벨 시작 직후 ARM+AutoFire다(`bDemoForceCommandPostAutoFire`).

부수 피해: 이렇게 죽은 개체도 `ScenarioEnemyCountBaseline` 대비 사망자에 포함되므로
**도주 트리거 3명/7명이 실질 2명/6명으로 당겨진다.** 3차 전투지 근처에 적을 놓을 거면
`bIsRevealed=false` + `SquadId`/`CombatZones` 저작을 같이 해줘야 한다.

## 6. 바뀐 파일

```
Soldiers/EnemyCombatComponent.h    GetCurrentState / HasCombatZoneRole / HasAuthoredCombatZone /
                                   GetAuthoredCombatZone / AdoptCombatZoneRole /
                                   피격 기록 4개(GetLastDamageSourceName 외) + HandleAnyDamage /
                                   bFireHold + SetFireHold / IsFireHeld
Soldiers/EnemyCombatComponent.cpp  BeginFlee 단조증가 판정, TickMove/TickFlee에 도주 커밋 카운트다운,
                                   AdoptCombatZoneRole, HandleAnyDamage, BeginPlay의 OnTakeAnyDamage 바인딩,
                                   SetFireHold, SetDetectionEnabled에 bFireHold 초크 포인트
UI/ScenarioStepTypes.h             EScenarioEffectType::HoldFleeingEnemyFire (신규, 열거 끝에 추가)
UI/ScenarioStateSubsystem.h/.cpp   BeginEnemyFleeToZone 정원제 재작성(스냅샷 기준),
                                   FScenarioEnemyZoneRole USTRUCT + ScenarioZoneRoles/ScenarioSquadTotals,
                                   CaptureEnemyZoneRoles, CollectEnemyCombatComponents,
                                   UpdateEnemyCasualtyWatch / LogEnemyCasualty / BuildSquadCensusString,
                                   HoldFleeingEnemyFire 이펙트 + ReleaseEnemyFireHold,
                                   TrackedEnemies 캐시, 리셋 2곳에 초기화 추가
UI/ScenarioConfig.h                FleeQuotaZone2 / FleeQuotaZone3 (0 = 자동)
Soldiers/AllyFormationComponent.cpp  타겟 유효성 재검증에 교전 제외(IsTargetableByAlliesAndUGV) 검사 추가
```

전부 `p4 edit` 완료. BP/레벨 값 변경은 없다.
DataTable(`DT_ScenarioSteps_ThreeStage`)은 `HoldFleeingFire` 행 1개 추가 — **완료·저장됨**(5.6절).

### 사용자가 별도로 바꾼 값 (2026-09-03)

- `RCWSFireControl.AutoFireCycleIntervalSeconds` **1 → 3초** — §2의 "한 점사 = 1킬" 완화.
  02:36 실행이 이 값으로 돌았다.

## 7. 남은 작업 / 검증

- [x] 1차 빌드 + PIE 완주 — 3차 도주 3명 확인(5.5절). `BeginFlee` 버그는 해결됨.
- [x] **2차 빌드**(정원 스냅샷 + 사격 보류) 완료 + `HoldFleeingFire` 행 추가·저장 완료(5.6절).
- [ ] 2차 빌드 상태로 PIE 재검증.
- [ ] 로그 확인 5종:
      `적군 전투지 역할 스냅샷 — 적 15명 | 1차 15자리, 2차 10자리, 3차 5자리`,
      `2차 전투지 도주 배정 — 정원 10명 ... 이동 10명`,
      `3차 전투지 도주 배정 — 정원 5명 ... 이동 5명`,
      `도주 분대 5명 사격 보류`,
      `도주 분대 N명 사격 보류 해제 — 이동형지휘소를 향해 교전 재개`.
- [ ] 사상자 로그로 **1차/2차/3차에서 각각 몇 명이 언제 죽는지** 실측 → 임계값 3/7 재튜닝.
      (02:36 실행에는 `[적 사상]` 줄이 남아 있으니 그것부터 읽으면 된다.)
      지금 값은 적 4기짜리 `kadex_test` 시절 값을 15기 기준으로 되돌린 것이지 실측으로 정한 게 아니다.
- [ ] `UGVZone3Destination`이 여전히 비어 있고 `UGVMoveZone3` 행도 `bEnabled=false` —
      3차까지 UGV를 따라 보낼지 결정 필요(2026-08-31부터 미결).
- [ ] 3차 도주 시 3분대가 2차로 뛰던 중 방향을 트는 그림이 어색하지 않은지 확인. 아래 참고.

### 권장 후속 — "2차에 도착한 뒤에 3차로" (DataTable만 고치면 됨, 코드 변경 없음)

위 수정으로 명령이 버려지지는 않지만, 실측상 3차 명령이 2차 도주 **23초째**에 오므로 3분대는
2차 전투지를 밟지도 못하고 도중에 방향을 튼다. "2차에서 한 번 교전한 뒤 3차로 도주"하는 그림을
원하면 **임계값을 올리는 것보다 시간 게이트를 거는 게 확실하다**(사망 속도는 교전 상황마다 다름).

스텝 테이블 구조상 `PrerequisiteStepId`는 "이 스텝이 발동한 뒤부터 평가 시작"이므로, 중간에
타이머 행 하나만 끼우면 된다:

| RowName | Prereq | Trigger | 값 | Effect |
|---|---|---|---|---|
| `Zone2Settled`(신규) | `EnemyFleeToZone2` | `TimerOnly` | **70s** | (없음 / 알림용) |
| `EnemyFleeToZone3`(수정) | `EnemyFleeToZone2` → **`Zone2Settled`** | `EnemyCasualtyCountAtLeast` | 7 그대로 | `BeginEnemyFleeZone3` |

70초 = 도주 55~60초 + 커밋 지연 최대 3초 + 여유. 이러면 "2차 도착 → 아군과 교전 → 누적 7명이면
3차로"가 된다. `EnemyFleeToZone3`을 prereq로 삼는 행 4개(`UGVMoveZone3`/`CommandPostFire`/
`RetargetToCommandPost`/`DroneFrameZone3`/`ExcludeFleeingEnemies`)는 그대로 따라 밀린다.

> 이 변경은 **연출 페이싱 결정**이라 사용자 확인 없이 넣지 않았다. 사상자 로그를 한 번 뽑아보고
> 실제 2차 체류 시간을 본 뒤 70초 값을 정하는 게 순서상 맞다.

### 더 근본적인 후속 — 킬 레이트를 낮춰야 한다 (별건, 미결)

위 시간 게이트만으로는 부족하다. 실측상 `EnemyFleeToZone2` 이후 전멸까지가 **29초(09-03 02:09) /
96초(02:16)** 밖에 안 되므로, 70초 게이트를 걸면 게이트가 열리기 전에 전원 사망하는 실행이 나온다.
"한 점사 = 1킬"(위 §2 산수)을 완화하지 않으면 어떤 스텝 튜닝으로도 3단계 페이싱이 안 나온다.

레버 3개 — **어느 쪽을 쓸지는 연출 결정이라 손대지 않았다**:

| 레버 | 위치 | 효과 | 부작용 |
|---|---|---|---|
| `AutoFireCycleIntervalSeconds` 1 → **3** | `RCWSFireControl`(UGV/트럭 인스턴스) | 킬레이트 1/3 | 사격 리듬이 느긋해짐(데모 화면상 심심할 수 있음) |
| `DamagePerHit` 34 → **20** | `RCWSProjectile.h`(C++, 리빌드) | 점사 2회=5발 필요 → 킬레이트 1/2 | RCWS 전체(트럭 포함) 공용 |
| 적 `Health` 100 → **300** | `BP_Enemy_kadex` 인스턴스 15개 | 3점사 필요 → 킬레이트 1/3 | **아군 소총에도 동일 적용** → 2차 전투도 3배 길어짐 |

가장 손이 적고 되돌리기 쉬운 건 첫 번째(`AutoFireCycleIntervalSeconds`, 레벨 인스턴스 값 2개).
"2차 전투도 같이 길어져야 한다"면 세 번째가 맞다 — 다만 인스턴스 15개를 다 고쳐야 하고,
CDO에 넣으면 레벨 인스턴스에 전파되지 않는 함정이 있다(과거 기록).

## 8. 디버깅 비용을 줄이는 방법 (5분 완주 문제)

한 번 보는 데 5분이 드는 게 이 작업의 진짜 병목이었다. 정리해둔다.

1. **화면을 보지 말고 로그를 읽는다.** 위 사상자 로그 + 기존 `시나리오 스텝 발동:` +
   `[EnemyPath]` 세 줄이면 실행 한 번으로 전체 타임라인이 재구성된다.
2. **`slomo 3`** — 5분이 100초가 된다. AI 타이머·이동·애니메이션·투사체가 전부 같은 배율로
   스케일되므로 상대적 페이싱(무엇이 무엇보다 먼저 오는가)은 보존된다. 순서·타이밍 검증에 적합.
3. **5분의 대부분은 전투가 아니다** — `PatrolMoveSpeed=150`으로 260~360m를 걷는 경계 이동이
   173~240초다. 흐름만 볼 때는 이 값을 임시로 올리면 앞구간이 통째로 줄어든다(연출 검증 때는 원복).
4. **뒷구간만 보고 싶으면** 적 액터의 `CombatZones[0].CoverPose.Marker`를 UGV 쪽으로 당기지 말고,
   `EnemyFleeToZone2`/`Zone3`의 임계값을 낮춰서 도주 구간부터 빨리 열리게 하는 편이 안전하다
   (마커를 옮기면 내비메시 투영 실패 같은 다른 변수가 끼어든다 — 2026-08-31 §5.4 참고).
