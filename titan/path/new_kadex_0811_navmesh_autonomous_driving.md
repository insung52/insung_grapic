# New_kadex_0811 자율주행 내비메시 구축 (2026-08-21~22)

> **후속 문서: `ugv_obstacle_avoidance_2026-08-26.md`** — 이 문서대로 내비메시를 깐 뒤 UGV가
> 주행 중 나무에 계속 부딪히던 문제를 해결한 기록. 나무 콜리전 프록시를 MCP 스크립트 대신
> 에디터 버튼으로 재생성하는 툴(`ATreeCollisionProxyBuilder`)이 거기 있으니, **프록시를 다시 깔
> 일이 생기면 이 문서 2절 대신 그쪽을 볼 것.**

새 레벨 `New_kadex_0811`에서 UGV(`BP_UGV_Vehicle`) 자율주행과 적군 이동을 위한 내비메시 작업 기록.

**예전 레벨(`kadex_demo_0716`) 문서와의 관계**: `ugv_navmesh_autonomous_driving_dev_guide.md`와
`ugv_driving_dev_guide.md` 10절이 그쪽 레벨의 기록이다. 두 레벨은 **지형 구성 자체가 달라서
접근법이 통째로 다르다** — 예전 것을 그대로 따라 하면 안 된다. 다만 축적된 함정(콜리전 프로파일,
`set_actor_transform` 부분 수정 버그 등)은 여전히 유효하니 그쪽도 같이 볼 것.

| | kadex_demo_0716 | New_kadex_0811 |
|---|---|---|
| 도로 | Datasmith 도로 메시 + Landscape 스플라인 253세그먼트 | **도로 없음.** PCG 숲 사이의 빈 흙길 |
| 주행 가능 구역 정의 | 도로 메시 자체 | **PCG 나무가 안 심긴 영역** |
| 가중치 배치 | 스크립트로 `NavModifierVolume` 253개 | **스플라인 + 엔진 `SplineNavModifier`(자동 추종)** |

---

## 0. 최종 구성 (결론부터)

세 겹으로 나눠서 각각 다른 문제를 담당한다.

| 층 | 무엇 | 담당 | 자동 추종 |
|---|---|---|---|
| 1 | `TreeCollisionProxy` 액터 (원기둥 ISM 1,719개) | UGV·보병이 나무에 **물리적으로** 막힘 + 내비메시 침식 | ✗ (스크립트 재실행) |
| 2 | `RoadCenterline` + `SplineNavModifier`(`NavArea_Road`) | UGV 자율주행 **경로 가중치** | ✓ |
| 3 | `RoadCenterline2` + `SplineNavModifier`(`NavArea_EnemyPath`) | 적군 이동 **경로 가중치** | ✓ |

2·3층은 스플라인 점을 옮기면 내비메시가 알아서 다시 구워진다. 1층만 스크립트를 다시 돌려야 한다.

---

## 1. 레벨 실측값 (2026-08-22 기준)

### 1.1 흙길 경계를 정의하는 스플라인

| 액터 | 스플라인 포인트 | 크기 | 역할 |
|---|---|---|---|
| `BP_SplineForest_tree_C_1` | 64 | 1,640m × 901m | 메인 경계 (닫힌 루프가 접혀서 안쪽에 흙길 공간을 만듦) |
| `BP_SplineForest_tree2_C_1` | 6 | 163m × 92m | 작은 섬 |
| `BP_SplineForest_tree_C_2` | 5 | 160m × 77m | 작은 섬 |
| `BP_SplineForest_plant_C_1/_C_3` | 50 / 29 | — | 하층식생(고사리 등), 경계와 무관 |

**중요**: 스플라인들은 사실상 평면이다(`tree_C_1`의 로컬 Z 폭이 3m 이내). 지형은 오르내리는데
스플라인은 평평하므로, 선을 따라 무언가를 세울 땐 높이를 크게 잡거나 Z를 무시해야 한다.

`NavMeshBoundsVolume_1`: 월드 AABB `X -51539~78461`, `Y -13371~36629`, `Z -8466~11534`
(1,300m × 500m × 200m). 레벨에 `RecastNavMesh-Tank` / `RecastNavMesh-Default` 둘 다 존재.

### 1.2 PCG 구성 (`PCG_SplineForest_tree2`, 노드 10개)

```
GetSplineData → SplineSampler(OnInterior, 간격 450cm) → Projection(랜드스케이프)
  → TransformPoints → SpatialNoise → AttributeMaths(OneMinus) → DensityFilter(0.38~1.0)
  → StaticMeshSpawner(PCGMeshSelectorWeighted: 소나무/자작나무/묘목)
```

- 샘플러가 `OnInterior` — **닫힌 스플라인 내부를 4.5m 격자로 채운다.** even-odd 규칙이라
  루프가 접힌 안쪽 공간(=흙길)은 자동으로 구멍으로 남는다. 이게 "나무 없는 길"의 정체다.
- `interiorDensityFalloffCurve`의 X축이 엔진 정의상 **"경계까지의 정규화 거리(0~1)"** —
  즉 이 그래프는 이미 경계로부터의 거리를 density로 들고 있다. "경계 근처만" 같은 분기를
  나중에 그래프 안에서 하고 싶으면 여기서 출발하면 된다.
- **`GenerationTrigger = GenerateOnLoad`, `Seed = 42` 고정, `bRegenerateInEditor = true`.**
  - 레벨을 열 때마다 처음부터 다시 생성한다 → **에디터에서 나무 인스턴스를 개별 삭제해도 의미 없다.**
  - 대신 Seed가 고정이라 **몇 번을 재생성해도 나무 위치는 동일하다.** 프록시가 어긋날 걱정은 없다.
  - 튀어나온 나무 한두 그루를 없애려면: (a) 스플라인 컨트롤 포인트를 안쪽으로 살짝 밀기(제일 쉬움,
    실제로 이 방법을 씀), (b) 그래프에 제외 볼륨 + `Difference` 노드 추가(정석),
    (c) `GenerateOnDemand`로 전환은 **비추천** — PCG는 생성물을 직렬화하지 않아서 로드 시 나무가
    아예 없는 상태가 될 수 있음.

### 1.3 나무 메시 콜리전 현황 (원본 에셋)

| 메시 | 단순 콜리전 | ISM 프로파일 |
|---|---|---|
| `SM_Scots_Pine_Forest_02` | **sphyl(캡슐) 1개** (반경 16cm, 길이 688cm) | NoCollision |
| `SM_BHF_BirchTreeA` | convex hull 16개 | NoCollision |
| `SM_BHF_BirchTreeTinnyA` | **0개 (없음)** | NoCollision |

묘목은 콜리전 지오메트리가 아예 없어서 `CollisionEnabled`만 켜도 아무 일도 안 일어난다
(예전 Datasmith 도로에서 겪은 것과 같은 함정). 자작나무는 convex 16개라 수천 그루에 켜면 무겁다.
**→ 원본 메시 콜리전을 켜는 대신 별도 프록시를 쓰기로 한 이유.**

---

## 2. 1층 — 나무 콜리전 프록시 (`TreeCollisionProxy`)

### 2.1 방식

PCG가 뿌린 나무 인스턴스의 트랜스폼을 읽어서, **경계 스플라인에서 15m 이내 + `NavMeshBoundsVolume`
안**에 드는 것들의 위치에만 "보이지 않는 원기둥"을 별도 ISM으로 복제한다. PCG 그래프도, 나무 메시
에셋도 건드리지 않는다 — 다른 레벨에 영향 0이고, 프록시 액터 하나만 지우면 원상복구된다.

- 액터: `TreeCollisionProxy` (플레인 `AActor`)
- 메시: `/Engine/BasicShapes/Cylinder` (바운드 ±50, convex 1개)
- **크기 — 나무별 실측 줄기 치수 (2026-08-26 개편)**. 처음엔 내비메시 여유폭 기준으로 전 개체
  반경 50cm / 높이 6m 고정이었는데, 피격 이펙트가 붙고 `Visibility = Block`이 되면서(6절)
  **보이지 않는 굵은 기둥이 총알과 시야를 과하게 가리는** 문제가 생겨 실제 줄기에 맞춰 줄였다.

  | | 로컬 줄기 반경 | 로컬 줄기 높이 | 근거 |
  |---|---|---|---|
  | 소나무 | 16cm | 700cm | 메시 자체 sphyl (반경 16, 길이 688) |
  | 자작나무 | 22cm | 860cm | convex hull #4 (z 200~862 구간, xySpan 39×44) |

  여기에 **각 나무 인스턴스의 원래 스케일(0.51~0.89)을 곱한다.** PCG가 나무마다 다른 스케일을
  주기 때문에 고정값으로 통일하면 개체별로 ±30% 어긋난다. 프록시 위치를 나무 위치에서 그대로
  복사해뒀기 때문에, 월드 XY를 정수로 반올림한 값을 키로 삼아 원본 인스턴스의 스케일을 정확히
  되찾을 수 있다(매칭률 99.9%).

  결과 실측: **지름 16.5~39.0cm(중앙값 25.9cm), 높이 3.6~7.6m(중앙값 5.4m)**, 총 1,931개.
  중심 Z는 각 인스턴스의 기존 높이에서 밑동을 역산해 지면에 고정하고, 회전은 기존 행렬을
  정규화해서 보존한다.
- 콜리전: `CollisionProfileName = "Custom"`, `QueryAndPhysics`
  - **Block**: `WorldStatic`, `WorldDynamic`, `Pawn`, `PhysicsBody`, `Vehicle`, `Destructible`
  - **Ignore**: `Visibility`, `Camera`, `GameTraceChannel1`
  - Visibility를 Ignore로 둔 건 RCWS 조준/탐지 트레이스가 보이지 않는 기둥에 막히는 사고를 피하려는 것.
    나무를 시야 차폐물로도 쓰려면 Block으로 바꾸면 된다.
- 컴포넌트 태그 `TreeTrunkCollision`
- **렌더링 꺼짐** — 배치 확인이 끝난 뒤 전 컴포넌트(20개)에 `bVisible = false` + `bHiddenInGame = true`
  적용(2026-08-22). 콜리전은 `QueryAndPhysics` 그대로라 물리 차단과 내비메시 침식은 유지된다
  (내비게이션 관련성은 가시성이 아니라 콜리전에서 나온다). 다시 눈으로 확인하고 싶으면
  `bVisible`만 켜면 된다.

### 2.2 최종 배치 결과 (2026-08-22)

| 컴포넌트 | 대상 | 개수 |
|---|---|---|
| `Pine_0` ~ `Pine_7_1` (11개) | 메인 경계 소나무 | 905 |
| `Birch_0` ~ `Birch_7_1` (9개) | 메인 경계 자작나무 | 881 |
| `Island_0_0` / `Island_1_0` | 섬(`tree_C_2`) 소나무 / 자작나무 | 70 / 75 |
| **합계** | 컴포넌트 22개 | **1,931** |

> 스플라인을 수정할 때마다 다시 깔았기 때문에 이 숫자는 계속 변한다(1,719 → 1,954 → 1,931).
> 레벨 구성도 바뀌었다 — `tree2_C_1`은 삭제됐고 `tree_C_1`은 위치가 이동했으며 하층식생
> (`plant_C_*`) 액터가 여럿 추가됐다. **작업 전에 항상 현재 액터/컴포넌트 목록을 다시 조회할 것.**

묘목(`TinnyA`)은 제외했다 — 작은 묘목에 차가 막히면 어색해서. 넣으면 약 710개가 추가되고
내비메시 차단은 더 확실해진다.

### 2.3 차단 효과 계산

Tank 에이전트 반경이 200cm라, Recast는 반경 50cm 장애물 하나당 **지름 5m**짜리 내비메시 구멍을
낸다. 나무 평균 간격이 4.5~4.8m(4.5m 격자 × 밀도필터)라 대체로 막히지만, 밀도 필터로 격자 두 칸이
연속으로 비는 자리에는 틈이 생긴다. 완벽한 차단은 아니고 그래도 된다는 게 사용자 판단이었다
("수동으로는 어차피 처음 나무에 부딪힌 순간 사용자는 '나무는 막혀있구나' 생각들거임").

**작은 섬 두 개는 벽이 못 된다.** 섬의 나무 밀도가 훨씬 낮아서(섬당 소스 인스턴스 150~180그루,
평균 간격 8~9m) Tank 에이전트가 나무 사이로 그냥 지나간다. 물리적 장애물 역할만 한다.

### 2.4 ⚠ 에디터를 얼려먹은 함정 — `perInstanceSMData` 대용량 단일 쓰기

**인스턴스 2,218개를 `set_properties`로 한 번에 쓰다가 에디터가 완전히 멈췄다** (329초 무응답 후
MCP 타임아웃, 이후 가벼운 조회도 전부 타임아웃, 결국 강제 종료). 인스턴스 3개일 땐 즉시 됐으니
배열 크기에 대해 비선형적으로 느려지는 것으로 보인다.

**해결**: ISM 컴포넌트를 여러 개로 쪼개고 **컴포넌트당 150개 이하**로 나눠 쓴다. 그래서
`Pine_0`~`Pine_7`, `Birch_0`~`Birch_7`, `Island_*`로 나뉘어 있다. 호출도 X축 슬라이스 단위로
쪼개서 각 호출이 120초 안에 끝나게 했다.

**근본 원인 (2026-08-26 확인)**: `set_properties`의 배열 갱신은 **차분(diff) 방식**이다. 에러
메시지가 결정적이었다:

> `ArrayRemove: elements changed alongside the size change; removed elements are ambiguous`

여기서 따라오는 규칙 세 가지:

1. **비용은 배열 크기가 아니라 "실제로 바뀐 원소 수"에 비례한다.** 빈 배열에 2,218개를 넣는 건
   원소를 하나씩 2,218번 추가하는 것과 같아서 사실상 끝나지 않는다.
2. **크기 변경과 원소 변경을 동시에 못 한다.** 유령 인스턴스 제거(크기 −1)와 값 수정은 반드시
   별도 호출로 나눠야 한다.
3. **전체 배열을 보내되 일부 원소만 바꾸면 차분이 그 일부만 처리한다.** 즉 150개짜리 컴포넌트를
   "1~50번만 수정 → 51~100번만 수정" 식으로 쪼갤 수 있다. 배열 부분 갱신이 불가능해 보여도
   사실상 가능하다는 뜻.

실측 처리량(원소 수정 기준): 130개 → 몇 초 / 330개 → 120초 이내 / 500개 → 120초 초과(백그라운드
완료). **한 호출당 300개 안팎**이 실용적인 상한이다.

부수 함정 둘:
- **인스턴스를 쓴 뒤에 `staticMesh`를 지정**해야 컴포넌트가 인스턴스 데이터를 제대로 리빌드한다.
  순서를 반대로 하면 액터 바운드가 갱신 안 되는 등 어긋난 상태가 된다.
- 이 방식으로 만든 ISM에는 **월드 원점(0,0,0)에 스케일 1짜리 유령 인스턴스가 컴포넌트마다 하나씩**
  딸려 들어간다(2026-08-26에 23개 발견·제거). 배열의 **마지막 원소**로 들어가므로, 값 작업이 다
  끝난 뒤 "마지막 하나만 잘라내기"(크기 변경만, 값 변경 없음)로 지우면 된다.

---

## 3. 2·3층 — 스플라인 가중치 (`SplineNavModifierComponent`)

### 3.1 예전에 이 방법을 못 썼던 이유

`ugv_driving_dev_guide.md` 10.3절:
> "Landscape Splines는 일반 `SplineComponent`가 아니라 전용 시스템이라 엔진 내장
> `USplineNavModifierComponent`를 못 붙임."

즉 **엔진 기능을 못 써서 스크립트로 우회했던 것**이다. 이번엔 디자이너가 직접 그린 평범한
`USplineComponent`라 엔진 기능을 그대로 쓸 수 있다.

### 3.2 컴포넌트 동작

`Engine/Source/Runtime/NavigationSystem/Public/SplineNavModifierComponent.h` — 스플라인을 곡률
적응형으로 테셀레이션해서 구간마다 `StrokeWidth × StrokeHeight` 단면의 컨벡스 헐 nav modifier를
만든다(예전에 스크립트로 손수 하던 일을 엔진이 대신 함). `bUpdateNavDataOnSplineChange = true`(기본)면
**스플라인 점을 옮기는 즉시 내비메시가 다시 구워진다.**

### 3.3 실제 배치

| 액터 | 컴포넌트 | AreaClass | StrokeWidth | StrokeHeight | 스플라인 |
|---|---|---|---|---|---|
| `RoadCenterline` (`Actor_7`) | `RoadNavWeight` | `NavArea_Road` | **100cm** | 20000cm | 780m × 224m |
| `RoadCenterline2` (`Actor_8`) | `EnemyPathNavWeight` | `NavArea_EnemyPath` | **200cm** | 20000cm | 26점, 724m × 149m |

- 두 액터 모두 플레인 `AActor` + 인스턴스 `SplineComponent`("Spline"). BP 에셋 아님.
- `RoadCenterline`에는 액터 태그 **`UGVRoadCenterline`** 이 붙어 있다(C++가 이걸로 찾는다, 4절).
- **`StrokeHeight`가 20000cm인 이유**: 디자이너가 편집 편의를 위해 스플라인을 지형보다 한참 위에
  그렸다(Z ≈ 11,000). 튜브가 지형까지 닿으려면 높이를 크게 잡아야 한다. 이렇게 하면 라인트레이스로
  Z를 맞출 필요가 없다.
- 적군 경로 폭을 더 넓게(200cm) 잡은 이유: 보병 에이전트 반경이 30cm라 Recast가 area를 덜 부풀린다.
  같은 100cm면 UGV 경로보다 오히려 얇게 남는다.
- **폭 1m로 실제 자율주행 성공 확인됨** (2026-08-22). 예전 레벨에서 300~400cm 스트립이 리전 병합에
  흡수되던 문제(`ugv_driving_dev_guide.md` 10.4절)가 재현될까 우려했으나, Tank 반경이 이미 200으로
  낮춰져 있어서인지 문제없었다.

### 3.4 적군 경로에 `NavArea_Road`를 쓰면 안 되는 이유

**적군도 `UNavQueryFilter_Infantry`를 쓴다** (`EnemyCombatComponent.cpp:786`, `:841`). 이 필터의
유일한 역할이 `NavArea_Road` 비용을 1.0으로 되돌리는 것이라, 적군 경로에 `NavArea_Road`를 칠하면
**적군이 완전히 무시한다.**

그래서 area class를 분리하되, 방향을 반대로 잡았다:
- `UNavArea_EnemyPath`: `DefaultCost = 1.0` (**중립**) — 아무에게도 매력적이지 않음
- `UNavQueryFilter_Enemy`: `UNavQueryFilter_Infantry`를 상속(보병 공통 규칙 그대로 물려받음) +
  `NavArea_EnemyPath` 비용만 0.2로 할인

area 자체를 싸게 만들면 UGV와 아군까지 그 경로에 끌려간다. 2026-07-29에 `NavArea_Road`로 정확히
그 사고가 났었고(보병이 UGV처럼 도로를 따라다님) 그래서 `UNavQueryFilter_Infantry`가 생겼다.
같은 실수를 반복하지 않으려고 **"area는 중립 + 필터에서만 할인"** 구조를 택했다.

---

## 4. C++ 변경 (2026-08-22)

### 4.1 `AUGVAIController` — 도로 소스를 스플라인에서 직접 읽기

**문제**: `BeginPlay`가 `TActorIterator<ANavModifierVolume>`로 `AreaClass == NavArea_Road`인
**액터**를 스캔해서 `CachedRoadVolumes` / `CachedRoadSegments`를 만든다. `SplineNavModifier`는
액터가 아니라 **컴포넌트**라 이 스캔에 안 잡힌다 → 도로 기반 기능 3종이 통째로 죽는다.

**해결**: 볼륨 스캔 후, `RoadCenterlineActorTag` 태그가 붙은 액터의 `USplineComponent`가 있으면
`CachedRoadSegments`를 그걸로 통째로 다시 만든다(`CacheRoadSegmentsFromSplines`). 스플라인 소스가
이기고, 없으면 예전 방식 그대로라 `kadex_demo_0716`은 영향 없다.

| 기능 | 스플라인 소스일 때 |
|---|---|
| `ComputeRoadCenterPull` (경로 중앙 당김) | **코드 수정 없이 그대로 작동** — 원래부터 `CachedRoadSegments`만 보고 X/Y로만 계산 |
| `UpdateOffRoadSpeedDecay` | 콜리전 오버랩 → **중심선까지 2D 거리 ≤ `RoadSplineHalfWidth`** |
| `UpdateRoadBoundary` | 브로드페이즈 오버랩 + `GetClosestPointOnCollision` → 세그먼트 2D 최단거리 |

**Z는 전 구간 무시한다**(모든 도로 쿼리가 2D). 스플라인을 지형보다 높이 그려도 무방한 이유.

신규 헬퍼: `CacheRoadSegmentsFromSplines()`, `FindClosestRoadSegmentPoint()`, 플래그
`bRoadSourceIsSpline`. 스플라인은 **인덱스가 아니라 호 길이(arc length)로 샘플링**한다 —
컨트롤 포인트가 직선에선 성기고 커브에선 촘촘해서, 인덱스로 자르면 세그먼트 길이가 자릿수 단위로
들쭉날쭉해지고 `ComputeRoadCenterPull`의 "가장 가까운 두 세그먼트 블렌드"가 어긋난다.

신규 프로퍼티 (`UGV AI|Road`):

| 프로퍼티 | 기본값 | 의미 |
|---|---|---|
| `RoadCenterlineActorTag` | `UGVRoadCenterline` | 중심선 스플라인 액터를 찾을 태그 |
| `RoadSplineSampleInterval` | 500cm | 스플라인 → 세그먼트 샘플 간격 |
| `RoadSplineHalfWidth` | 300cm | "도로 위에 있다"고 볼 중심선 반폭 |

> ⚠ `RoadSplineHalfWidth`(300)와 `StrokeWidth`(100)는 **다른 값**이다. 전자는 온로드 판정 범위,
> 후자는 내비메시에 가중치를 칠하는 폭.

### 4.2 `AUGVAIController::MoveToDestination` — 목적지 내비메시 투영

**증상**: `MoveUGVFromTankTo (X=14596,Y=1922,Z=2069)` → `failed to find a path`. 큐브 콜리전을 다 끄고
내비메시 영향도 없앴는데 계속 실패.

**원인**: 목표 큐브(`StaticMeshActor_12`, UGV_04)는 **Z 1137~2137짜리 10m 큐브**였고, 입력한
Z=2069는 큐브 꼭대기 근처였다. 실제 내비메시는 Z≈1137. `FindPathToLocationSynchronously`는 두
끝점을 에이전트의 `DefaultQueryExtent`로 투영하는데, `Tank`는 **(50, 50, 250)** — 수직 2.5m뿐이라
투영이 실패하고 경로탐색이 시작조차 못 했다. **Z를 1150으로 주니 즉시 성공.**

**해결**: `MoveToDestination`이 경로탐색 전에 `ProjectPointToNavigation`으로 목적지를 직접 투영한다.
- 신규 프로퍼티 `DestinationProjectionExtent` = **(500, 500, 20000)** — X/Y는 좁게, Z만 200m로 크게.
  마커 높이/오타로 Z가 어긋나는 건 흡수하되, X/Y가 진짜 엉뚱하면 여전히 실패하게 둔다.
- 로그가 세 갈래로 갈라져서 다음 실패 때 원인이 바로 구분된다:
  - `Destination snapped to navmesh: ... (dZ ...)` — 정상
  - `Destination ... has no navmesh within extent ...` — 그 XY에 내비메시 없음(레벨 문제)
  - `... is not standing on navmesh` — UGV 자기 자리에 내비메시 없음(목적지와 무관하게 무조건 실패)

### 4.3 부분 경로(partial path) — A* 노드 예산 소진 (2026-08-24)

**증상**: 목적지 X=-4109를 줬는데 UGV가 X≈3800에서 멈춤. 로그상으로는 완전히 정상
(`MoveToDestination started` + 경로점 253개). 에러도 경고도 없음.

**분석**:
```
Destination snapped to navmesh: (-4109,17348,4318) -> (-4109,17348,4253)   ← 목적지에 내비메시 있음
RefinePath: bEnableRoadCentering=1 CachedRoadSegments=223 rawPoints=36
RefinePath: resampled to 253 points, first=(72648,17061,-4863) last=(4940,21736,3864)
                                                              ↑ 목적지에서 2D 100m 떨어진 곳
```
- 목적지 투영은 성공(dZ -65cm) → 목적지에 내비메시가 분명히 존재
- 중앙 당김 후처리는 범인이 아님 — 리샘플링은 각 구간 끝점을 항상 포함하고(`Alpha=1`),
  `ComputeRoadCenterPull`은 점을 최대 `RoadCenteringMaxLateralDistance`(300cm)만 움직인다.
  100m를 날릴 수 없음
- 즉 **Recast가 돌려준 원본 경로(36점)가 이미 거기서 끝나 있었다** = 부분 경로

**원인**: `ARecastNavMesh::DefaultMaxSearchNodes` 기본값이 **2048**(`RECAST_MAX_SEARCH_NODES`).
680m 경로에서 이 예산이 바닥났다. 이 레벨 내비메시가 유난히 잘게 쪼개져 있는 게 이유 —
10m 타일(`TileSizeUU=1000`) × 볼륨 1300m×500m = 타일 6,500개에, 나무 프록시 1,719개가 폴리곤을
더 잘게 나눈다.

**판별 방법 (빌드 불필요)**: UGV가 멈춘 뒤 **같은 명령을 한 번 더 친다.**
- 계속 주행 → 노드 예산 문제 (출발점이 가까워져 탐색 범위가 줄어든 것). 실제로 이쪽이었음
- 같은 자리에서 또 멈춤 → 내비메시가 실제로 끊긴 것 (통로가 `AgentRadius=200`에 못 미치게 좁거나
  나무 프록시가 봉했거나)

**해결**: `Config/DefaultEngine.ini`
```ini
[/Script/NavigationSystem.RecastNavMesh]
DefaultMaxSearchNodes=65536.000000
```
> 처음엔 16384(엔진 기본의 8배)로 잡았다가 **2026-08-26에 65536(32배)으로 올렸다.** 경로가 더
> 길어졌고, 나무 프록시를 UGV 경로 하나가 아니라 **적군 경로 3개를 포함한 총 4개 경로** 주변에
> 깔면서 내비메시가 훨씬 더 잘게 쪼개졌기 때문.
- `UPROPERTY(config)` 전용이라 **에디터 디테일 패널에 안 보이고 MCP로도 못 읽는다.** ini에서만 설정.
- **에디터 재시작 필요**(config는 시작 시 로드).
- 레벨에 이미 배치된 `RecastNavMesh-*` 액터도 새 값을 따라온다 — 예전에 `AgentRadius`로 겪었던
  "이미 생성된 액터는 프로젝트 세팅 변경을 안 따라감" 함정과 다르다. 그건 액터가 자기 값을 따로
  저장하고 있던 경우고, 이 값은 지금까지 CDO 기본값과 같아서 레벨에 직렬화되지 않았다.
- 무작정 키우면 안 된다 — 경로탐색 1회당 `dtNodePool` 할당이 이 값에 비례하고, 아군 30명 + 적군이
  주기적으로 재경로를 돈다. 16384 ≈ 쿼리당 600KB.

**감지 로직 추가**: `MoveToDestination`이 경로를 받은 직후 `IsPartial()`과 목적지까지 잔여 거리를
검사해 경고를 남긴다. 이 상황은 원래 로그상 완전 무증상이라 매번 좌표를 손으로 대조해야 했다.
```
[UGVAIController] PARTIAL PATH: ends 10057cm (2D) short of the destination — IsPartial=1, ...
```

### 4.4 신규 파일 4개 (**퍼포스 `p4 add` 필요**)

```
Source/titan_example/Soldiers/NavArea_EnemyPath.h / .cpp
Source/titan_example/Soldiers/NavQueryFilter_Enemy.h / .cpp
```

`EnemyCombatComponent.cpp`의 경로 요청 2곳(786행 최초 경로, 841행 재경로)을
`UNavQueryFilter_Enemy::StaticClass()`로 교체. 아군(`AllyFormationComponent`)은 계속
`UNavQueryFilter_Infantry`를 쓴다.

---

## 5. 검토했지만 채택하지 않은 방법들

| 방법 | 왜 안 썼나 |
|---|---|
| **숲 영역 전체를 `NavArea_Null`로 채우기** (그림판 채우기식 flood fill) | 보수적 래스터 + 런렝스 병합으로 2.5~5m 셀에 수백 개 볼륨이면 충분히 가능하고 설계까지 마쳤으나, `Null`은 **모든 에이전트**를 막아서 보병이 나무 사이로 엄폐/이동을 못 하게 된다. 경계에 한 셀 폭의 안 채워진 띠가 남아 우회 경로가 생기는 문제도 있었다 |
| **경계선을 따라 `Null` 튜브 두르기** | 위와 같은 이유(보병 차단). 또 스플라인이 평면이라 지형 기복이 큰 구간에서 새기 쉽다 |
| **나무 원본 메시 콜리전 전체 활성화** | 자작나무 convex 16개 × 수천 그루면 물리 씬이 무겁고, 묘목은 콜리전 지오메트리가 아예 없어서 켜도 무의미 |
| **PCG 그래프에 콜리전 분기 추가** (경계 근처만 콜리전 켠 별도 스포너) | 정석이고 재생성에도 유지되지만, **MCP에 PCG 툴셋이 없어서 노드 추가/배선을 할 수 없다**(프로퍼티 읽기/쓰기만 가능). 사용자가 직접 그래프를 편집해야 한다. 프록시 방식으로 세팅이 확정되면 이쪽으로 정식화하는 것이 다음 단계 |
| **PCG를 `GenerateOnDemand`로 바꿔 수동 삭제 유지** | PCG가 생성물을 직렬화하지 않아서 로드 시 나무가 통째로 사라질 위험 |

---

## 6. 재현 / 재실행 방법

### 스플라인을 수정했을 때

- **2·3층(가중치)**: 아무것도 안 해도 된다. 자동으로 따라간다.
- **1층(나무 콜리전 프록시)**: 스플라인이 바뀌면 PCG가 나무를 다시 뿌리므로 **프록시를 다시 깔아야
  한다.** 기존 `TreeCollisionProxy` 액터를 지우고 새로 만든 뒤, 나무 종류 × X축 슬라이스 단위로
  나눠서 호출한다(2.4절의 150개 제한 참고). 실제로 이 작업을 세 번 반복했다.

### 필터/파라미터 튜닝 지점

| 증상 | 만질 것 |
|---|---|
| 자율주행 경로가 중심선을 안 탄다 | `RoadCenteringMaxLateralDistance`(기본 300cm) → 500~800. Recast가 area를 에이전트 반경(200cm)만큼 부풀려 굽기 때문에 원경로가 3m 넘게 벌어져 있으면 당김 대상에서 제외된다 |
| UGV가 계속 느려진다 | `OffRoadSpeedDecayPerTick`. **도로 소스가 하나도 없으면 UGV는 영구 오프로드 취급이라 매 틱 1%씩 감속된다.** 4.1절 적용 전에는 0으로 꺼둬야 했다 |
| 가중치가 안 걸린 것 같다 | P키 내비메시 뷰. `NavArea_Road`는 **주황**, `NavArea_EnemyPath`는 **빨강**(`DrawColor`). 안 보이면 `StrokeWidth`를 키워서 리전 병합에 흡수되는지 확인 |
| 통로가 막혀 경로가 안 나온다 | 나무 프록시가 통로를 봉했을 수 있다. 프록시 반경 50→30cm, 또는 `Tank` 에이전트 반경 200→150 |
| **목적지 한참 앞에서 그냥 멈춘다** | 부분 경로(4.3절). 같은 명령을 다시 쳐서 판별 → 계속 가면 `DefaultMaxSearchNodes`(ini, **현재 65536**)를 더 올릴 것. 다만 이 값이 크면 *도달 불가능한* 목적지를 줬을 때 실패가 느려져 히칭이 생긴다 |
| 목적지를 줬는데 `failed to find a path` | 목적지 Z가 내비메시에서 너무 떨어져 있을 수 있다(4.2절). 마커 큐브 중심이 아니라 **바닥** Z를 쓸 것 |

### PIE 시작 시 확인할 로그

```
[UGVAIController] Road source: centerline spline (N segments, M RoadNavMod volumes)
```
`centerline spline`이 아니라 `RoadNavMod volumes`로 나오면 태그를 못 찾은 것이다.
스플라인 길이 780m / 샘플 간격 500cm 기준으로 N은 150~200 근처가 정상.

---

## 6.5 주행 중 장애물 회피 — 별도 문서

흙길 위에 나무 장애물을 의도적으로 배치하면서 UGV가 회피 조향을 원속도로 들어가 부딪히는 문제가
생겼고, 커브 선행 감속(제동 곡선)으로 해결했다 → **`ugv_corner_braking_dev_guide.md`**.

그 문서 2절에 적힌 함정 하나만 여기에도 옮겨둔다: **경로 위에 장애물을 두면
`RoadCenteringPullStrength`(기본 0.6)가 Recast의 회피를 다시 장애물 쪽으로 되돌린다.**
장애물이 있는 구간에서는 `bEnableRoadCentering`을 끄거나 당김 강도를 낮출 것.

## 7. 남은 작업

- [ ] 작은 섬 두 개는 나무 간격이 넓어 UGV 경로를 못 막는다 — 섬 안쪽으로 자율주행이 들어가면 안 되면
      별도 처리 필요(섬 전용 프록시 반경 확대 또는 섬에 nav modifier)
- [ ] 나무 프록시를 PCG 그래프 분기로 정식화(5절 표 참고) — 그러면 1층도 자동 추종이 된다
- [ ] 적군이 `NavArea_EnemyPath`를 실제로 타는지 시나리오 흐름(`BeginScenarioEnemyContact` 6단계
      이후)에서 검증
- [ ] `UpdateRoadBoundary`의 `RoadVolumeIgnoreParams`에 `ControlledPawn` 미포함 문제
      (`ugv_navmesh_autonomous_driving_dev_guide.md` 3절에서 넘어온 미해결 항목) — 스플라인 경로에서는
      지면 재트레이스만 남아 있어 영향이 줄었지만 여전히 미수정
