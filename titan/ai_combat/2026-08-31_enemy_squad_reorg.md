# 적군 3분대 재편 — 분대별 도주 경로 + 분대 전멸 캐스케이드

2026-08-31 / 코드+레벨 저작 완료·경로 가중치 근본원인 수정·PIE 재검증 대기 / 적 15명을 5명씩 3분대로 나눌 수 있게 `SquadId`/
`LastStandZoneIndex`/분대별 NavMesh 필터를 추가하고, "N분대 전멸" 시나리오 트리거를 신설.

선행 문서: `enemy_scenario_combat_expansion.md`(Part A~G — 단계적 도주/타겟 전환 캐스케이드,
선호도 시스템), `../level_new_kadex_0811/scenario_three_stage_combat.md`(DataTable 스텝 구조),
`../vehicle/ugv/2026-08-27_new_kadex_0811_navmesh_autonomous_driving.md` 3절(`enemypath` =
`NavArea_EnemyPath` + `UNavQueryFilter_Enemy` 구조).

짝이 되는 UGV 쪽 작업: `../vehicle/ugv/2026-08-31_ugv_enemy_distance_speed_limit.md`.

---

## 1. 요구사항 (memo.md "시나리오 관련 변경")

> 적들 15명을 5명씩 3분대로 변경, 각 분대들은 서로 다른 enemypath 를 따라감.
> 1분대는 1차 전투지에서 다 전멸 (적군 2차 전투지로 도망 시작 시 1분대는 제외)
> 2분대는 2차 전투지에서 다 전멸 (적군 3차 전투지로 도망 시작 시 2분대는 제외)

## 2. 기존 시스템이 어떻게 돼 있었나 (먼저 확인한 것)

요구사항의 "제외 처리"가 실제로 무엇을 고쳐야 하는 문제인지부터 확인했다.

| 항목 | 기존 구현 | 분대 관점에서의 문제 |
|---|---|---|
| 도주 명령 | `EScenarioEffectType::BeginEnemyFleeZone2/3` → `ForEachEnemyCombat`으로 **살아있는 적 전원**에게 `BeginFlee(1)`/`BeginFlee(2)` 브로드캐스트 | 사망 시 `UDetectableTargetSubsystem` 등록이 해제되므로 **전멸한 분대는 이미 자동으로 제외됨**. 진짜 문제는 "죽었어야 하는데 살아남은 낙오자"가 다음 전투지로 따라붙는 것 |
| 도주 트리거 | `EnemyCasualtyCountAtLeast` — **전체 사망자 수**(기준 적 수 − 현재 생존 수) | **문제 없음. 이게 정석이고 그대로 쓴다** — 아래 3.3절의 시행착오 참고 |
| 도주 경로 | 개체별 `CombatZones[i].CoverPose.Marker`로 이동, 경로 요청은 전원이 `UNavQueryFilter_Enemy` 하나(= `NavArea_EnemyPath` 할인) | 마커는 개체마다 다르지만 **경로 가중치는 15명이 전부 같은 스플라인 하나**를 공유 |

즉 손댈 곳은 두 군데였다 — **분대 소속 데이터(도주 제외 게이트)**, **분대별 경로 필터**.
트리거는 안 건드린다.

## 3. 구현

### 3.1 `UEnemyCombatComponent` — 분대 소속 (신규 프로퍼티 3개, 카테고리 `Enemy|Squad`)

| 프로퍼티 | 기본 | 의미 |
|---|---|---|
| `SquadId` | 0 | 분대 번호. **0 = 분대 미지정**(예전 동작 그대로). 새 시나리오는 1/2/3 |
| `LastStandZoneIndex` | -1 | **이 개체가 마지막까지 버틸 전투지 인덱스.** -1 = 제한 없음(예전 동작) |
| `PathQueryFilterClass` | 비어있음 | 이 개체의 NavMesh 경로 요청에 쓸 쿼리 필터. 비우면 `UNavQueryFilter_Enemy`로 폴백 |

**`LastStandZoneIndex`가 "제외 처리"의 본체다.** `BeginFlee(N)`은 `N > LastStandZoneIndex`면
조용히 거절한다. 1분대는 0, 2분대는 1, 3분대는 2를 넣으면 된다.

> 왜 시나리오 이펙트 쪽에서 "분대 X 제외하고 브로드캐스트"로 안 했는가: 정상 흐름에서는 그
> 분대가 이미 전멸해 브로드캐스트 대상에 없으므로 제외가 자동이고, 명시적으로 막아야 하는 건
> 낙오자 케이스뿐이다. 그건 스텝 테이블이 아니라 **개체 자신이 아는 정보**라 컴포넌트에 두는
> 게 맞다(스텝 행마다 제외 분대 목록을 들고 다니는 것보다 저작도 단순하다).

`GetSquadId()`(BlueprintPure) 추가 — 시나리오 서브시스템의 분대 인구조사가 쓴다.

### 3.2 분대별 `enemypath` — NavArea 3개 + 쿼리 필터 3개 (신규 파일 4개, **`p4 add` 완료**)

```
Source/titan_example/Soldiers/NavArea_EnemySquadPath.h / .cpp
    UNavArea_EnemySquad1Path / 2Path / 3Path   (DefaultCost=1.0 중립, DrawColor 각각 Magenta/Cyan/Yellow)
Source/titan_example/Soldiers/NavQueryFilter_EnemySquad.h / .cpp
    UNavQueryFilter_EnemySquad1 / 2 / 3        (UNavQueryFilter_Enemy 상속 + 자기 area만 0.2로 할인)
```

기존 `NavArea_EnemyPath`/`NavQueryFilter_Enemy`의 설계 원칙을 그대로 답습했다 — **area는 중립,
할인은 필터에서만.** area 자체를 싸게 만들면 UGV·아군까지 그 경로에 끌려간다(2026-07-29에
`NavArea_Road`로 정확히 그 사고가 났고 그래서 `UNavQueryFilter_Infantry`가 생겼다).

세 필터는 전부 `UNavQueryFilter_Enemy`를 상속하므로 **공용 경로(`NavArea_EnemyPath`) 할인을
그대로 물려받고**, 그 위에 자기 분대 경로만 추가로 할인한다. 할인율은 공용 경로와 같은 0.2 —
겹치는 구간에서는 비용이 같아 경로가 튀지 않고, 갈라지는 구간에서만 자기 경로가 이긴다.

다른 분대 경로에 **페널티는 안 건다.** 중립이라 매력이 없을 뿐이고, 굳이 비싸게 만들면 세 경로가
겹치는 출발지 근처에서 경로가 아예 안 나오는 사고가 나기 쉽다.

`EnemyCombatComponent`의 경로 요청 2곳(최초 경로 + 정체 시 재경로)이
`ResolvePathQueryFilterClass()`를 거치도록 교체 — `PathQueryFilterClass`가 비어있으면
`UNavQueryFilter_Enemy`이므로 **분대를 안 쓰는 기존 레벨(kadex_test 등)은 동작이 완전히 동일**하다.

> **스플라인을 아직 안 그렸어도 안전하다.** 할인 대상 area가 내비메시에 하나도 없으면 분대
> 필터는 베이스와 똑같이 동작한다 — 분대 경로 저작은 나중에 해도 나머지가 전부 돌아간다.

### 3.3 ❌ 폐기 — "N분대 전멸" 트리거를 만들려던 시도

한때 `EScenarioTriggerType::EnemySquadEliminated`(+ `FScenarioStepRow::TriggerSquadId`,
분대별 인구조사 `UpdateSquadCensus`)를 신설해서 "1분대가 전멸하면 2차 전투지로 도주"를
트리거로 삼으려 했다. **요구사항을 잘못 읽은 것이라 코드째 제거했다.**

무엇을 잘못 읽었나 — memo.md의 "1분대는 1차 전투지에서 다 전멸"은 **트리거 조건이 아니라
결과**다. 흐름은 이렇다:

```
누적 사망자 N명   ──(트리거, 예전 그대로)──▶  BeginEnemyFleeZone2 를 살아있는 적 전원에게 브로드캐스트
                                             │
                                             ├─ 1분대: LastStandZoneIndex=0 이라 거절 → 1차 전투지에 남음 → 거기서 전멸
                                             └─ 2·3분대: 2차 전투지로 도주
```

즉 1분대의 전멸은 **도주를 안 해서 생기는 결과**이지, 도주를 시작시키는 조건이 아니다.
분대 전멸을 조건으로 걸면 오히려 "1분대 5기가 다 죽을 때까지 아무도 안 도망간다"가 되어
연출이 뻣뻣해지고, 1분대 한 명이 어딘가에 끼어 안 죽으면 시나리오가 통째로 멈춘다.

**따라서 도주 트리거는 `EnemyCasualtyCountAtLeast` 그대로다.** 이번 작업이 §1에서 실제로
추가한 것은 `LastStandZoneIndex` 게이트와 분대별 경로 필터뿐이고, 스텝 시스템에는 §2의
UGV 속도 제한 이펙트 2개 말고는 아무것도 안 늘었다.

## 4. 레벨/데이터 저작 — **완료** (New_kadex_0811)

> 세션 중반까지 이 레벨엔 적군 액터가 하나도 없었고(아군 25기뿐), 그 사이 사용자가 15기를
> 배치했다. 아래는 그 위에 분대 데이터를 얹은 결과다.

### 4.1 적 개체 15기 — 분대 필드 배정 (MCP로 설정·검증·저장 완료)

라벨 `BP_Enemy_kadex_1`~`15` 기준(사용자 지정 규칙):

| 분대 | 개체 | `SquadId` | `LastStandZoneIndex` | `PathQueryFilterClass` | 저작된 `CombatZones` |
|---|---|---|---|---|---|
| 1분대 | 1~5 | 1 | **0** | `NavQueryFilter_EnemySquad1` | **1개**(zone0만) |
| 2분대 | 6~10 | 2 | **1** | `NavQueryFilter_EnemySquad2` | **2개**(zone0,1) |
| 3분대 | 11~15 | 3 | **2** | `NavQueryFilter_EnemySquad3` | **3개**(zone0,1,2) |

**저작 데이터 자체가 이미 "제외"를 표현하고 있었다.** 사용자가 1분대에는 2·3차 전투지 마커를
아예 안 붙였고(zone 배열 길이 1), 2분대에는 3차를 안 붙였다. `BeginFlee(N)`은 원래도
`CombatZones.IsValidIndex(N)` 검사에서 걸러지므로 **`LastStandZoneIndex` 없이도 제외는 됐을
것**이다. 그럼에도 이 필드를 남긴 이유:

- 의도가 명시적으로 드러난다(빈 배열이 "실수로 안 채운 것"인지 "일부러 뺀 것"인지 구분됨).
- 나중에 zone 마커를 다 채워넣어도(예: 연출상 1분대에도 2차 마커를 주고 싶어질 때) 제외가
  유지된다. 즉 **두 겹으로 보장**된다.

### 4.2 분대 경로 스플라인 — 완료

레벨에 적군 경로 스플라인이 이미 3개 있었는데(문서상 `RoadCenterline2` 1개에서 늘어남) 셋 다
공용 `NavArea_EnemyPath`로 칠해져 있어 세 경로가 모든 적에게 똑같이 매력적인 상태였다 —
분대를 갈라놓을 수가 없었다. 사용자 확인대로 **라벨 번호 = 분대 번호**로 배정:

| 액터 | 라벨 | `EnemyPathNavWeight.AreaClass` | 디버그 색 |
|---|---|---|---|
| `Actor_8` | `RoadCenterline_Enemy1` | `NavArea_EnemySquad1Path` | 마젠타 |
| `Actor_3` | `RoadCenterline_Enemy2` | `NavArea_EnemySquad2Path` | 시안 |
| `Actor_4` | `RoadCenterline_Enemy3` | `NavArea_EnemySquad3Path` | 노랑 |

`StrokeWidth 200` / `StrokeHeight 38000` / `bUpdateNavDataOnSplineChange true`는 그대로.

> ⚠️ **내비메시를 다시 구워야 한다.** `bUpdateNavDataOnSplineChange`는 *스플라인 점*이 바뀔 때만
> 도는 것이라, AreaClass만 바꾼 지금은 자동 재빌드가 안 걸렸을 수 있다. Build → Build Paths를
> 한 번 돌리고 P키 뷰에서 세 색이 보이는지 확인할 것.

### 4.3 `DT_ScenarioSteps_ThreeStage` — 도주 트리거는 **그대로**, 임계값만 15명 기준으로 복원

3.3절대로 트리거 타입은 `EnemyCasualtyCountAtLeast` 유지. 다만 임계값 1/3은 적 4기짜리
kadex_test용으로 낮춰뒀던 값이라(사용자 확인), 적 15기인 메인 레벨 기준 원안 값으로 되돌렸다:

| RowName | Trigger | `TriggerCountThreshold` | Effect |
|---|---|---|---|
| `EnemyFleeToZone2` | `EnemyCasualtyCountAtLeast` | **3** (이전 1) | BeginEnemyFleeZone2 |
| `EnemyFleeToZone3` | `EnemyCasualtyCountAtLeast` | **7** (이전 3) | BeginEnemyFleeZone3 |

3/7이 분대 구성과 맞물리는 방식:
- **3명 사망** → 2·3분대(10기)가 2차로 도주. 1분대 잔여 2기는 남아서 마저 죽는다.
- **누적 7명 사망**(1분대 5 + 2분대 2) → 3분대가 3차로 도주. 2분대 잔여 3기는 2차에 남는다.

숫자는 실제 교전 템포를 보고 조정할 값이다(1분대가 다 죽기 전에 도주가 시작되는 게 정상 —
동시에 벌어져야 그림이 산다).

## 5. ★ 근본 원인 — 적군 경로 가중치는 **도입 이래 한 번도 동작한 적이 없었다**

사용자 리포트: "보병들이 처음 걸어갈 때 enemypath 가중치를 안 받고 일직선으로 간다. 이상한 길로
돌아가는 애들도 있고 직선으로 가서 장애물에 끼는 애들도 있다."

### 5.1 원인 — 엔진이 필터의 비용 오버라이드를 하한 1.0으로 클램프한다

```cpp
// Engine/Source/Runtime/NavigationSystem/Private/NavFilters/NavigationQueryFilter.cpp
void UNavigationQueryFilter::InitializeFilter(const ANavigationData& NavData, const UObject* Querier,
                                              FNavigationQueryFilter& Filter) const
{
    ...
    if (AreaData.bOverrideTravelCost)
    {
        Filter.SetAreaCost(IntCastChecked<uint8>(AreaId), FMath::Max(1.0f, AreaData.TravelCostOverride));
    }                                                     // ↑ 0.2 를 넣어도 1.0 이 된다
```

Recast의 A* 휴리스틱이 admissible하려면 area 비용이 1.0 이상이어야 해서 엔진이 의도적으로 막아둔
것이다. **`UNavigationQueryFilter`로는 비용을 올릴 수만 있고, 내릴 수 없다.**

따라서 `UNavQueryFilter_Enemy::AddTravelCostOverride(NavArea_EnemyPath, 0.2f)`(2026-08-22 도입)는
조용히 1.0(중립)이 되어 **아무 효과가 없었다.** 이번에 내가 추가한 분대별 필터의 0.2도 똑같이
죽어 있었다.

**왜 여태 안 드러났나**: `UNavQueryFilter_Infantry`의 두 오버라이드(`NavArea_Road`=1.0,
`NavArea_UGVBody`=1000000)는 전부 1.0 이상이라 정상 동작한다. "필터 오버라이드는 잘 먹는다"는
인상만 남았고, 유일하게 1.0 미만인 값 하나만 죽어 있었다. 게다가 UGV의 도로 선호는 멀쩡해서
(그건 `NavArea_Road::DefaultCost=0.2`에 박혀 있고 **UGV는 필터를 아예 안 써서** 클램프를 안 거친다)
"가중치 시스템 자체는 되는데 적군만 이상하다"로 보였다.

증상이 두 갈래로 갈린 것도 이걸로 설명된다 — 가중치가 전부 중립이면 그냥 최단경로라,
숲 사이 지형에 따라 **어떤 개체는 이상하게 우회**하고 **어떤 개체는 직선으로 가다 장애물에 낀다.**

### 5.2 수정 — "경로를 싸게" → **"경로 밖을 비싸게"**

올리는 건 되므로 방향을 뒤집었다. area는 전부 중립(`DefaultCost=1.0`) 그대로 두고:

| 필터 | 오버라이드 | 결과 |
|---|---|---|
| `UNavQueryFilter_Enemy` | `NavArea_Default` → **5.0**, `NavArea_Road` → **5.0** | 적군 경로(1.0)가 **상대적으로 5배 싸짐** |
| `UNavQueryFilter_EnemySquadN` | **다른 두 분대**의 경로 area → **2.0** | 자기 경로(1.0)가 갈림길에서 이기되, 겹치는 구간에선 남의 area여도 계속 싸다 |

비용 서열: **자기·공용 경로 1.0 < 다른 분대 경로 2.0 < 그 외 지형 5.0.**
두 배율은 `EnemyNavCost::OffPath` / `OtherSquadPath`(`NavQueryFilter_Enemy.h`) 두 상수로만 관리한다.
`OffPath`는 올릴수록 경로를 악착같이 따라가지만 A*가 펼치는 노드가 급증하므로(긴 경로에서
`DefaultMaxSearchNodes`=131072에 걸릴 위험) 3~8 사이에서 조정할 것.

> **가운데 단계(2.0)가 왜 필요한가 — 2026-09-01, 실측으로 확정**
>
> 처음엔 "다른 분대 경로도 5.0"으로 짰다가 **2·3분대가 가중치를 통째로 잃는 사고**가 났다.
> 원인은 세 경로 스플라인이 거의 같은 줄기라는 것:
>
> | 비교 | 최소거리 | 중간거리 | 200cm 이내 겹침 |
> |---|---|---|---|
> | 2분대 → 1분대 | 0cm | 0cm | **88%** |
> | 3분대 → 1분대 | 0cm | 3cm | **96%** |
> | 3분대 → 2분대 | 0cm | 4cm | **87%** |
>
> Recast는 **폴리곤 하나당 area 하나**라 modifier가 겹쳐도 쌓이지 않고 한쪽이 이긴다 → 공유 줄기
> 전체가 1분대 area로만 칠해졌고, 2·3분대는 그걸 "남의 경로=5.0"으로 봐서 경로 밖과 동일 취급했다.
> PIE 로그의 평균 area비용이 그대로 드러냈다 — **1분대 4.50~4.67(경로의 ~12%를 corridor 주행),
> 2·3분대 5.22~5.32(0%)**. 1분대만 corridor를 타려고 2.5~2.9km를 더 돌아갔다.
>
> 사용자 요구는 "겹치더라도 자기 분대 경로를 정상 가중치로 따라갈 것, 공유 구간을 따로 저작하지는
> 말 것"이었고, 가운데 단계가 정확히 그걸 만든다.

`NavArea_Road`까지 올린 이유: Infantry가 이미 1.0으로 중립화해둬서, 안 올리면 도로가 적군 경로와
같은 비용이라 "도로로 질러가는" 선택지가 생긴다.

**아군과 UGV는 무영향** — 아군은 `UNavQueryFilter_Infantry`(안 건드림), UGV는 필터 자체를 안 쓴다.
area의 `DefaultCost`는 여전히 중립이라 이들이 적군 경로에 끌릴 일도 없다(원래 설계 의도 유지).

### 5.3 진단 로그 추가 — 같은 실수를 다시 못 하게

`BeginNavPathMovement`는 경로 요청이 실패해도 **아무 로그 없이** `NavPathPoints`를 비운 채
리턴했고, `TickNavPathMovement`는 그럴 때 목적지로 **직선 조향**하는 폴백을 탄다. 즉
"경로 실패"와 "가중치 무시"가 밖에서 구분이 안 됐다.

`UEnemyCombatComponent::LogPathResult()` 신설(경로 요청 2곳 = 최초/정체 재탐색이 공유,
`bLogPathDiagnostics` 기본 켜짐):

```
[EnemyPath] BP_Enemy_kadex_C_1 squad=1 filter=NavQueryFilter_EnemySquad1 | BeginNavPath:
    pts=14 partial=0 끝지점거리=42cm | 직선 24954cm 경로 29431cm (detour x1.18) | cost=31200 (평균 area비용 1.06)
```

읽는 법:
- **detour 배율** — `x1.00`이면 직선(폴백이거나 가중치 무효), `x1.1~1.5`면 가중 area를 타고 우회 중(정상).
- **평균 area비용**(`cost/len`) — 필터가 실제로 걸렸는지의 직접 증거.
  `1.0` 근처면 **필터가 아예 안 걸린 것**, `EnemyNavCost::OffPath`(5.0) 근처면 필터는 걸렸는데
  **가중 area가 내비메시에 안 칠해진 것**(Build Paths 안 했거나 스플라인 AreaClass 문제).
  둘 사이면 정상적으로 경로를 타고 있다는 뜻.
- 경로가 아예 없으면 `Warning`으로 "**목적지로 직선 이동 폴백**"을 명시.
- 부분 경로면 `Warning`으로 목적지까지 남은 거리를 찍는다(그 지점에서 멈춰 정체되는 원인).

### 5.4 두 번째 원인 — 목적지 마커가 내비메시 밖(2026-09-01)

가중치를 고친 뒤에도 **15기 중 10기가 경로를 아예 못 받았다.** 새 진단 로그가 바로 갈랐다:

```
└ 내비메시 투영: start OK(79cm 이동) / end **실패**(내비메시 없음/너무 멂)
└ 원인 (a): 양 끝점 중 하나가 내비메시 위에 없음 — 필터/가중치 문제가 아님.
```

실패한 10기 **전부 end(엄폐 마커) 투영 실패**, start는 전부 정상.

원인: `FindPathToLocationSynchronously`는 양 끝점을 내비 데이터의 `DefaultQueryExtent`
(**수평 50cm** / 수직 250cm)로만 투영한다. 엄폐 마커는 본래 엄폐물 바로 옆에 놓는 것이고 이
레벨은 나무 콜리전 프록시가 내비메시에 구멍을 내므로, 마커가 내비메시 가장자리에서 50cm만
벗어나도 **질의가 통째로 실패**한다. 실측 스냅 거리 65~196cm — 전부 50cm를 넘겼다.

**`AUGVAIController::MoveToDestination`은 이 문제를 이미 `DestinationProjectionExtent`
(500,500,20000)로 해결해두고 있었다.** 적군 컴포넌트만 원본 마커 좌표를 그대로 넘기고 있었던 것.
같은 처리를 `UEnemyCombatComponent::TryBuildNavPath`에 넣었다
(`NavDestinationProjectionExtent`, 기본 (300,300,400) — 수직을 UGV만큼 크게 안 잡은 이유는
보병이 겹친 층에서 엉뚱한 높이로 끌려갈 수 있어서).

곁들여 고친 것: 스냅된 끝점은 마커와 최대 300cm 떨어질 수 있으므로 **마지막 웨이포인트 구간은
경로 끝점이 아니라 실제 마커를 향하게** 했다. 안 그러면 스냅 지점에서 멈춰 도착 판정
(`ArrivalToleranceCm`)에 영영 안 걸리고 "정체"로 오인된다.

→ 14/15 정상화. 남은 하나는 `enemy_cover_1_8`(`TargetPoint_68`, `-2664,10280,3097`)로
**300cm 안에 내비메시가 아예 없다** — 레벨에서 마커를 옮기거나 그 지점 지오메트리를 확인해야 함.

### 5.5 경로 재시도 — "정체"에만 있었고 "실패"에는 없었다(2026-09-01)

`TickNavPathMovement`에 1초마다 "20cm 미만 이동 = 정체" 재탐색은 있었지만, **경로 질의 실패에
대한 재시도는 없었다.** 실패하면 `NavPathPoints`가 빈 채로 목적지 직선 이동을 하는데, 마침 앞이
뚫려 있으면 정체 판정이 안 나서 **끝까지 재시도 없이 가중치 없는 직선으로 도착**해버린다.

경로 요청 3곳(최초 이동 / 실패 재시도 / 정체 재탐색)을 `TryBuildNavPath()` 하나로 통일하고,
경로가 없으면 `PathRetryIntervalSeconds`(1초)마다 재요청하도록 했다. 실패 질의는 노드 예산을
다 태우고 끝나 비싸므로 실패가 반복되면 간격을 2배씩 늘린다(`MaxPathRetryIntervalSeconds` 8초까지).

**항상 가중치 필터를 끼운다** — 실패했다고 필터를 빼고 다시 구하지 않는다(사용자 지시). 그러면
그 개체만 조용히 가중치 없는 경로로 걸어가서 시나리오는 어긋나는데 로그로는 정상처럼 보인다.
`DiagnoseFailedPath` 안에서 필터 없이 한 번 구해보는 건 **원인 판별 전용**이고 이동에는 안 쓴다.

### 5.6 조사 과정에서 배제한 것들 (같은 길 다시 안 파도록)

| 의심 | 확인 결과 |
|---|---|
| 스플라인 모디파이어 설정 문제 | ❌ 검증된 UGV 도로(`RoadCenterline_UGV`)와 **동일 구성** — `AttachedSpline`=Spline, `bCanEverAffectNavigation`=true, StrokeWidth 200/Height 38000, 액터 Z 7130 vs 도로 7922 |
| 분대 area가 내비메시에 등록 안 됨 | ❌ `RecastNavMesh-Default.SupportedAreas`에 areaID **5/6/7**로 정상 등록 |
| NavMeshBoundsVolume이 적 스폰 지점을 안 덮음 | ❌ min=(-40828,-10592,-6706) max=(62156,29017,9137) — 전부 포함 |
| 우회가 애초에 이득이 아님(detour가 너무 김) | ❌ 직선 24,954cm vs 스플라인 경유 ~29,400cm — 5배 할인이면 **4배 유리**, 걸렸다면 눈에 띄게 휘어야 정상 |
| 적군이 공중에 떠 있어 경로탐색 실패 | ❌ 배치 당시 실제로 6.7~16.8m 떠 있었으나(uniform Z=980), **사용자가 지면에 붙인 뒤에도 증상 동일** — 이건 원인이 아니었다 |

## 6. 검증 방법 / 아직 안 된 것

- [x] **빌드** — 사용자가 직접 완료(2026-08-31). 신규 NavArea/필터 클래스가 에디터에 로드되는
      것을 MCP로 확인함(스플라인 AreaClass·개체 필터 지정 성공).
- [x] **레벨 저작** — 적 15기 분대 필드 + 스플라인 3개 area + 스텝 2행 교체, 전부 설정 후
      되읽기 검증하고 저장 완료.
- [ ] **Build → Build Paths** (4.2절 경고) 후 P키 뷰에서 마젠타/시안/노랑 세 경로 확인.
- [ ] PIE에서 콘솔 `BeginScenarioEnemyContact` → 로그의
      `[ScenarioStateSubsystem] 시나리오 스텝 발동:` 줄로 `EnemyFleeToZone2`가 **1분대 5기가
      전부 죽은 뒤에** 켜지는지 확인. (MCP엔 콘솔 명령 툴이 없어 이 단계는 자동화 불가 —
      PIE 시작/정지와 로그 읽기까지만 가능.)
- [ ] 1분대 낙오자를 일부러 남겨두고(예: 한 명을 사거리 밖에 배치) `EnemyFleeToZone2`를
      수동 발동시켜 그 낙오자가 2차 전투지로 안 따라가는지 확인 —
      `LastStandZoneIndex` 게이트의 직접 검증.
- [ ] 세 분대가 눈에 띄게 다른 경로로 도주하는지.
      `2026-08-27_..._navmesh_autonomous_driving.md` 7절의 미해결 항목
      ("적군이 `NavArea_EnemyPath`를 실제로 타는지 검증")이 여기서 같이 확인된다.
- [ ] **3차 전투지 이후 UGV가 안 따라간다** — `ScenarioConfig.UGVZone3Destination`이 비어 있고
      `UGVMoveZone3` 행도 `bEnabled=false`다(이전부터 그런 상태, 이번에 안 건드림).
      3분대까지 UGV가 쫓아가는 그림이 필요하면 목적지 배치 + 행 활성화가 필요.
- 15명 규모의 성능/충돌 특성 미실측(`enemy_scenario_combat_expansion.md` 남은 작업과 동일 —
  기존 검증은 4마리 기준).

## 7. 코드 변경 목록

```
신규
  Soldiers/NavArea_EnemySquadPath.h / .cpp        (p4 add)
  Soldiers/NavQueryFilter_EnemySquad.h / .cpp     (p4 add) — 5.2절대로 "남의 경로를 비싸게"

수정 (2026-08-31 2차 — 경로 가중치 근본 수정)
  Soldiers/NavQueryFilter_Enemy.h/.cpp   EnemyNavCost::OffPath 신설,
                                         죽은 0.2 할인 제거 → Default/Road를 5.0으로 상향
  Soldiers/NavArea_EnemyPath.h           설계 주석 정정(클램프 경위)
  Soldiers/EnemyCombatComponent.h/.cpp   LogPathResult() + bLogPathDiagnostics

수정 (p4 edit 완료)
  Soldiers/EnemyCombatComponent.h    SquadId / LastStandZoneIndex / PathQueryFilterClass /
                                     GetSquadId() / ResolvePathQueryFilterClass()
  Soldiers/EnemyCombatComponent.cpp  BeginFlee의 LastStandZoneIndex 게이트,
                                     경로 요청 2곳을 ResolvePathQueryFilterClass()로 교체
  (UI/ScenarioStepTypes.h / ScenarioStateSubsystem — §1 관련 변경 없음.
   EnemySquadEliminated 트리거를 넣었다가 3.3절 사유로 전부 되돌림)
```
