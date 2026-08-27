# UGV 자율주행 — 장애물 충돌 해결 + 나무 콜리전 자동화 (2026-08-26)

`New_kadex_0811`에서 UGV가 자율주행 중 나무에 계속 부딪히던 문제를 끝까지 파고들어 해결한 기록.
그 과정에서 나무 콜리전 프록시 생성을 에디터 버튼 하나로 자동화하는 툴도 만들었다.

선행 문서: `new_kadex_0811_navmesh_autonomous_driving.md` (내비메시 구축 전반, 3층 구조 설계)

---

## 0. 결론 요약

문제는 하나가 아니라 **네 겹**이었고, 각각 원인이 달랐다.

| 증상 | 진짜 원인 | 조치 |
|---|---|---|
| 나무에 계속 부딪힘 | 조향 PI 게인이 낮아 요레이트가 목표의 57~83%밖에 안 나옴 | `YawRateKp` 0.04→0.08, `YawRateKi` 0.02→0.05, `LookaheadDistance` 800→500 |
| 커브 감속이 부족 | 각도→속도 매핑이 물리적이지 않음(반경 9.5m 이하만 최저속) | 곡률 반경 역산 `v = sqrt(a_lat·R)` 으로 교체 |
| 엉뚱한 데서 과감속 | 차량 **뒤쪽** 커브까지 세면서 제동거리를 0으로 잡음 | 거리 ≥ 0인 정점만 계산에 포함 |
| 경로가 나무를 겨냥 | 도로 중앙 당김이 A*의 안전 여유를 깨뜨림 | `bEnableRoadCentering` 기본값 false |

부수적으로 잡은 것: 목적지 Z 오입력으로 인한 경로탐색 실패, 부분 경로 무증상 문제,
`AgentRadius`가 에디터 재시작마다 되돌아가는 문제, A* 노드 예산 부족.

---

## 1. 나무 콜리전 프록시 자동 생성 툴

### 1.1 왜 만들었나

나무 스플라인, UGV 경로 스플라인, 적군 경로 스플라인이 앞으로도 계속 바뀔 예정인데, 그때마다
프록시를 MCP 스크립트로 다시 깔아야 했다. 그런데 **그 방식이 에디터를 두 번이나 얼려먹었다** —
`ObjectTools.set_properties`의 배열 쓰기가 차분(diff) 방식이라 빈 배열에 2,000여 개를 넣으면
원소를 하나씩 추가하는 셈이 된다(자세한 건 선행 문서 2.4절).

그래서 언리얼 안에서 네이티브로 도는 에디터 툴로 옮겼다. `UInstancedStaticMeshComponent::AddInstances()`
로 배열을 한 번에 넣으므로 수천 개도 밀리초 단위다.

### 1.2 `ATreeCollisionProxyBuilder`

```
Source/titan_example/Tools/TreeCollisionProxyBuilder.h / .cpp
```

레벨에 액터를 하나 배치하고 Details 패널의 버튼으로 돌린다.

**Routes** — 경로마다 스플라인 액터 + 반경. 경로는 몇 개든 추가 가능하고 `bEnabled`로 개별 토글.
현재 설정(2026-08-26):

| RouteActor | 라벨 | Radius |
|---|---|---|
| Actor_7 | `RoadCenterline_UGV` | 1500 |
| Actor_8 | `RoadCenterline_Enemy1` | 1500 |
| Actor_3 | `RoadCenterline_Enemy2` | 1500 |
| Actor_4 | `RoadCenterline_Enemy3` | 1500 |

**Species** — 나무 종별 줄기 치수. 여기 없는 메시를 쓰는 ISM은 통째로 무시된다(고사리·바위·묘목).

| TreeMesh | TrunkRadius | TrunkHeight | 근거 |
|---|---|---|---|
| `SM_Scots_Pine_Forest_02` | 16 | 700 | 메시 자체 sphyl(반경 16, 길이 688) |
| `SM_BHF_BirchTreeA` | 22 | 860 | convex hull #4 (z 200~862, xySpan 39×44) |

**버튼 3개**
- `Preview Counts` — 아무것도 안 만들고 개수만 로그로. 반경 정할 때 먼저 돌린다.
- `Rebuild Proxies` — 기존 프록시 전부 제거 후 현재 상태로 재생성
- `Clear Proxies` — 제거만

### 1.3 툴이 자동으로 하는 것

- **나무별 스케일 반영** — 각 인스턴스의 실제 스케일(0.51~0.89)을 줄기 반경/높이에 곱한다.
  고정값으로 통일하면 개체별로 ±30% 어긋난다.
- 밑동을 지면에 고정, 렌더링 off(`bVisible=false` + `bHiddenInGame`), 그림자 off
- 콜리전: `Custom` 프로파일 + `QueryAndPhysics` + `ObjectType=WorldStatic`,
  전 채널 Block에 **`Camera`/`GameTraceChannel1`만 Ignore**
  - `ObjectType`이 `WorldStatic`이어야 하는 이유: 프로젝타일이 `WorldDynamic`을 Ignore한다
    (총알끼리 안 부딪히게 하는 설정이라 프로젝타일 쪽은 건드리면 안 된다)
  - `Visibility`는 일부러 Block — 나무는 시야를 가려야 하고, RCWS 탄도 조준도 나무까지의 거리로
    잡혀야 하며, 피격 재질 조회용 보조 트레이스도 이 채널을 쓴다
  - `Camera`는 Ignore — 보이지 않는 기둥이 카메라를 밀어내면 안 된다
- `PhysMaterialOverride = PM_Wood` (지정 안 하면 총알이 맞아도 이펙트가 안 나온다)
- **안전장치**: `Routes`가 비어 있으면 "전부 지우고 아무것도 안 만드는" 사고를 막기 위해
  아무것도 안 하고 중단한다.
- `bAlsoClearTaggedComponentsOnOtherActors` — 켜면 다른 액터에 붙은 같은 태그의 구 프록시도 같이
  정리한다. MCP로 만들어둔 예전 `TreeCollisionProxy` 액터를 한 번에 치울 때 썼다(그 뒤 빈 액터는
  수동 삭제).

### 1.4 결과

경로 4개 × 반경 15m 기준 **5,643개**(컴포넌트 2개, `MaxInstancesPerComponent=4000`).
예전 MCP 방식(1,931개, 경로 1개)에서 3배로 늘었지만 생성은 즉시 끝난다.

### 1.5 빌드 함정

`AActor::Owner` 멤버를 가리는 로컬 변수 이름 때문에 C4458이 났다(언리얼은 경고를 에러로 처리).
로컬은 `OwnerActor`처럼 이름을 피할 것.

---

## 2. 커브 선행 감속 재작성

### 2.1 문제 A — 각도→속도 매핑이 물리적이지 않았다

예전 방식: `Alpha = (10m 창 안의 |꺾임각| 합) / CornerFullSlowAngleDeg(60도)`, 그걸로
`Lerp(Straight, Min)`.

이걸 반경으로 환산하면 **60도/10m = 반경 9.5m**다. 즉 반경 9.5m보다 급한 커브에서만 최저속이고,
숲길에 흔한 반경 20~30m 커브는 목표가 28~33km/h로 나왔다. 실제로는 그 속도로 못 도는데도 "감속은
했다"고 판단하니, 눈에는 "돌아야 할 것 같은데 조금밖에 안 줄인다"로 보였다.

**해결**: 창에서 곡률 반경을 역산해 물리적으로 푼다.
```
R = 호길이 / 총꺾임각(rad)
v_corner = sqrt(CornerMaxLateralAccelMps2 * R)   → [CornerMinSpeedKmh, CornerStraightSpeedKmh] 클램프
```
호 길이는 창 안 정점들이 실제로 걸친 길이를 쓰되 **최소 `CornerWindowDistance`**로 본다. 경로점이
성긴 경우(도로 중심 리샘플이 꺼져 있으면 Recast 원본 경로라 커브가 정점 하나에 90도씩 몰린다)
걸친 길이가 0이 되어 반경이 0으로 튀는 걸 막는 장치다.

튜닝 값이 3개(`FullSlowAngle`/`Straight`/`Min`)에서 **`CornerMaxLateralAccelMps2` 하나**로 줄었고,
Straight/Min은 상하한 클램프로만 남았다. `CornerFullSlowAngleDeg`는 제거했다.

### 2.2 문제 B — 뒤쪽 커브를 "지금 당장" 요구했다

스캔 범위가 뒤로 `CornerLookbehindDistance`까지였는데, 뒤쪽 정점에서 시작하는 창은
`DistanceMeters = max(0, 음수) = 0`이 되어 **"지금 당장 그 속도여야 한다"**로 계산됐다.

결과가 둘:
- 커브를 **빠져나온 뒤에도** 뒤 10m 안에 그 정점이 남아 있는 동안 계속 눌림 → "직선인데 안 나간다"
- 그 창이 앞쪽 10m까지 포함하므로 **아직 10m 남은 커브를 지금 속도로 요구** → 진입 훨씬 전부터 과감속

**해결**: 거리 ≥ 0인 정점의 꺾임만 센다. 속도를 제약해야 하는 건 **남아 있는** 곡률이지 이미
지나온 곡률이 아니다. 뒤쪽 샘플 자체는 계속 모은다 — 차량 바로 앞 첫 정점의 "들어오는 방향"을
구하려면 그 앞 샘플이 하나는 필요하기 때문. 그래서 `CornerLookbehindDistance`는 역할이 축소되어
기본값을 1000 → **500**으로 낮췄다.

> 원래 이 값이 막던 문제("커브 절반쯤에서 남은 각도가 줄어 목표 속도가 올라가 → 커브 한복판에서
> 가속")는 `CornerTargetReleaseRateKmhPerSec`(목표 상승 속도 제한, 20km/h/s)가 담당한다.
> 커브 안에서 재가속이 다시 보이면 이 값이 아니라 그쪽을 낮출 것.

### 2.3 오해였던 것 — 브레이크는 잘 걸리고 있었다

처음엔 "목표를 넘기 전까지 브레이크가 안 걸려서 감속이 약하다"고 판단했는데 **틀렸다.**
`TargetSpeedKmh`는 코너 속도가 아니라 **제동 곡선상의 허용 속도**라, 코너에 접근하며 이 값이
내려가고 현재 속도가 그걸 넘는 순간부터 제동이 시작된다. 브레이크 토크도 16휠 × 3000Nm =
388kN이라 접지력 한계가 먼저 온다. 감속이 약해 보인 건 **목표 자체가 높았기 때문**(2.1절)이다.

---

## 3. 도로 중앙 당김 폐기

`RefinePathTowardRoadCenterline`은 `kadex_demo_0716`처럼 **폭 넓은 실제 도로가 깔려 있던 레벨**
전용 후처리였다. New_kadex_0811은 나무 사이를 헤쳐 나가는 숲길이라 "중심선으로 당긴다"는 전제
자체가 성립하지 않고, 오히려 해롭다:

- A*가 낸 경로는 **AgentRadius만큼 침식된 내비메시 위**에 있으므로 장애물과 최소 그만큼 떨어져
  있는 게 보장된다. 중심선 스플라인은 손으로 그린 선이라 그런 보장이 없다. 그쪽으로 당기면
  나무를 겨냥하게 된다.
- 점마다 당김 양이 다르면 경로에 톱니가 생기고, 커브 감속이 |꺾임각|을 합산하는 방식이라
  그 톱니를 "급커브"로 오인해 엉뚱한 데서 감속한다.

**`bEnableRoadCentering` 기본값을 false로 내렸다.**

켤 일이 생기면 같이 넣어둔 `bValidateRoadCenteringAgainstNavmesh`(기본 켜짐)도 함께 쓸 것 —
당긴 점을 내비메시에 재투영해보고 실패하면 원래 점으로 되돌린다. 거부된 개수가 로그로 나오는데,
그 숫자가 크면 **스플라인이 나무에 너무 가깝다**는 신호라 스플라인 자체를 손봐야 할 구간을
알려주는 지표도 된다.

---

## 4. 조향 게인 튜닝

### 4.1 진단 — 요레이트가 목표에 항상 못 미쳤다

`bLogPursuitDiagnostics`(BP Class Defaults → `UGV AI | Yaw Rate Steering`)를 켜면 0.2초마다:
```
[UGVPursuit] v=24.8km/h cornerTarget=28.5 | angErr=-11deg yaw des=-20.0 meas=-14.4 I=-0.06 | steer=-0.45 throttle=0.16
```

커브 구간에서 `meas`가 `des`의 **57~83%**밖에 안 됐다. 경로가 반경 14m를 요구하는데 차는 19m로
돌아나가니 그 차이만큼 밀렸다.

**속도 탓이 아니라는 근거 두 가지:**
1. 달성률이 19km/h든 30km/h든 똑같이 70~80%였다. 속도가 원인이면 저속에서 뚜렷하게 나빠져야 한다.
2. `steer`가 최대 **0.45**에서 멈췄다. 1.0까지 쓸 수 있는데 절반도 안 썼다 — 차가 못 도는 게
   아니라 제어기가 덜 명령하고 있었다.

```
steer = YawRateKp × 오차 + 적분항 = 0.04 × 4.2 + 0.18 ≈ 0.35~0.45   ← 관측값과 일치
```
P 제어 특성상 정상상태 오차가 남을 수밖에 없고, 그걸 없앨 적분(`Ki=0.02`)은 너무 느렸다 —
오차 4deg/s에서 조향 0.1을 쌓는 데 1.25초가 걸리는데 커브가 그 안에 끝난다.

### 4.2 적용값

**대상 BP는 `BP_UGVAIController`가 아니라 `/Game/Vehicles/UGV/Blueprint/BP_UGVAIController_new`다.**
`BP_UGV_Vehicle`의 `AIControllerClass`를 직접 읽어 확인했다. 옆에 있는 `_new` 없는 것을 고치면
아무 효과가 없다.

| 프로퍼티 | 이전 | 지금 |
|---|---|---|
| `YawRateKp` | 0.04 | **0.08** |
| `YawRateKi` | 0.02 | **0.05** |
| `LookaheadDistance` | 800 | **500** |

`LookaheadDistance`를 줄인 건 순수추종 곡률 `2·sin(α)/L_d`에서 L_d가 작아져 더 많이 꺾게 하고,
코너 파고들기(대략 `L²/(8R)`, L=800·R=8m면 1m)를 줄이기 위해서다.

### 4.3 그 이상은 효과가 없었다

`YawRateKp`를 0.08 → 0.12로 한 번 더 올려봤지만 **측정상 차이가 없었다.**

| 지표 | Kp=0.08 | Kp=0.12 |
|---|---|---|
| 요레이트 오차 평균 | 3.50 deg/s | 3.81 deg/s |
| 경로 방향오차 평균 | 5.1° | 5.2° |
| 달성률 중앙값 | 69% | 68% |
| max\|steer\| / 포화 | 0.87 / 0회 | 0.88 / 0회 |

남은 미달성분은 **커브 진입 순간의 물리적 지연**이다 — 목표 요레이트가 계단처럼 뛰는데 3톤 차체가
따라오는 데 시간이 걸린다. 조향이 포화되지 않는 것도 같은 얘기다(제어기는 여유가 있는데 차가 못
따라옴). 게인으로는 더 줄일 수 없으므로 **0.08이 적정선**이다.

> 더 개선하려면 게인이 아니라 다른 축이다: 목표 요레이트가 계단처럼 뛰지 않게 하거나
> (`LookaheadDistance` 추가 감소, 목표 요레이트 슬루 제한), 애초에 그런 급한 목표가 안 나오게
> 속도를 더 낮추는 것(`CornerMaxLateralAccelMps2` 하향).

### 4.4 조향이 포화되면 방향을 바꿀 것

`steer`가 0.9를 넘는 샘플이 생기기 시작하면 그때부터는 **조향 출력 한계**다. 게인을 더 올려도
소용없고, 속도를 낮추는 쪽으로 가야 한다.

---

## 5. 같이 잡은 것들

### 5.1 목적지 Z를 잘못 주면 조용히 실패한다

`FindPathToLocationSynchronously`는 두 끝점을 에이전트의 `DefaultQueryExtent`로 투영하는데
`Tank`는 (50, 50, **250**) — 수직 2.5m뿐이다. 마커 큐브 중심 Z를 그대로 찍으면(10m 큐브면 중심이
5m 위) 투영이 실패하고 경로탐색이 시작조차 못 한다.

`MoveToDestination`이 경로탐색 전에 `ProjectPointToNavigation`으로 직접 투영하도록 고쳤다.
신규 프로퍼티 `DestinationProjectionExtent` = **(500, 500, 20000)** — X/Y는 좁게, Z만 200m로 크게.
마커 높이나 오타로 Z가 어긋나는 건 흡수하되, X/Y가 진짜 엉뚱하면 여전히 실패하게 둔다.

로그가 세 갈래로 갈라져 원인이 바로 구분된다:
- `Destination snapped to navmesh: ... (dZ -665cm)` — 정상, 얼마나 보정됐는지 보임
- `Destination ... has no navmesh within extent ...` — 그 XY에 내비메시가 없음(레벨 문제)
- `... is not standing on navmesh` — UGV 자기 자리에 내비메시가 없음(목적지와 무관하게 무조건 실패)

### 5.2 부분 경로가 무증상이었다

Recast는 목적지에 못 닿아도 갈 수 있는 데까지의 경로를 돌려주고 `IsValid()`도 true다. 그래서
UGV가 그걸 정상 경로로 알고 달리다 중간에 그냥 멈추는데, 로그에는 정상 시작 메시지만 찍혔다.

`MoveToDestination`이 경로를 받은 직후 `IsPartial()`과 잔여 거리를 검사해 경고를 남기게 했다:
```
[UGVAIController] PARTIAL PATH: ends 1091cm (2D) short of the destination — IsPartial=1, rawPoints=83, end=..., wanted=...
```

**판별법**: 멈춘 자리에서 같은 명령을 다시 친다. **이어서 가면** A* 노드 예산 문제, **같은 자리에서
또 멈추면** 내비메시가 실제로 끊긴 것이다.

### 5.3 `AgentRadius`는 프로젝트 세팅에서 바꿔야 한다

레벨의 `RecastNavMesh-Tank` 액터 Details에서 고쳐봐야 **에디터를 껐다 켜면 되돌아간다.** 월드가
로드될 때 내비게이션 시스템이 `SupportedAgents` 설정으로 액터 값을 덮어쓰기 때문.

`Config/DefaultEngine.ini`의 `[/Script/Engine.NavigationSystemV1]` → `+SupportedAgents=(Name="Tank",...)`
에서 바꾸고 **에디터 재시작 + Build Paths**. 2026-08-26에 200 → **300**으로 올렸다.

> 반경만큼 내비메시가 양쪽에서 침식되므로, 통로가 좁아지는 구간에서 경로가 끊길 수 있다.
> 실제로 손으로 배치한 바위(`SM_BHF_RockA1/A2`, `BlockAll`) 옆을 지나는 구간이 이것 때문에 막힌
> 적이 있다. 올린 뒤엔 P키로 경로가 이어지는지 확인할 것.

### 5.4 A* 노드 예산

`DefaultMaxSearchNodes` 기본값 2048 → 16384 → 65536 → **131072**로 단계적으로 올렸다.
경로가 길어지고 나무 프록시가 5,643개로 늘면서 내비메시가 훨씬 잘게 쪼개졌기 때문.

**대가**: 경로탐색 1회당 `dtNodePool`을 통째로 할당한다(노드당 약 44바이트, 131072이면 약 5.8MB).
프레임 시간에는 영향이 없고 성공 경로도 필요한 만큼만 탐색하지만, **도달 불가능한 목적지를 줬을
때 실패가 그만큼 느려진다**(A*가 예산을 다 써야 포기하므로 히칭이 길어진다).

---

## 6. 현재 튜닝값 (2026-08-26 기준)

`BP_UGVAIController_new` Class Defaults:

| 카테고리 | 프로퍼티 | 값 |
|---|---|---|
| Yaw Rate Steering | `YawRateKp` | 0.08 |
| | `YawRateKi` | 0.05 |
| | `YawRateIntegralMax` | 0.4 |
| | `MaxDesiredYawRateDegPerSec` | 45 |
| | `bLogPursuitDiagnostics` | true (튜닝 끝나면 끌 것) |
| Chaos Pursuit | `LookaheadDistance` | 500 |
| | `CornerMaxLateralAccelMps2` | 2.5 |
| | `CornerStraightSpeedKmh` | 60 |
| | `CornerMinSpeedKmh` | 13 |
| | `CornerDecelMetersPerSecSq` | 2.0 |
| | `CornerWindowDistance` | 1000 |
| | `CornerLookbehindDistance` | 500 |
| | `ThrottleCutoffAngleDeg` | 90 |
| Road | `bEnableRoadCentering` | **false** |
| | `OffRoadSpeedDecayPerTick` | 0.01 |

성공 주행 실측(659샘플): 최고 34.6km/h, 평균 19.0km/h, 조향 포화 0회,
`cornerTarget` 최저 13.0(= `CornerMinSpeedKmh`에 도달, 커브 감속이 하한까지 작동).

---

## 7. 남은 것

- [ ] `bLogPursuitDiagnostics` 끄기(로그 파일이 커진다)
- [ ] 오르막 경사 보상 없음 — 커브 목표 속도에 미달인 채로 오르막을 만나면 그대로 느려진다.
      지금은 "안전하지만 답답한" 쪽이고, 필요하면 "목표 미달인데 스로틀이 이미 낮으면 최소 스로틀
      보장" 형태로 넣을 수 있다. **조향을 고치기 전에 속도부터 올리면 충돌이 심해지므로 순서 주의.**
- [ ] 적군 경로(`NavArea_EnemyPath` + `UNavQueryFilter_Enemy`)가 실제 시나리오에서 동작하는지 검증
- [ ] 나무 프록시를 PCG 그래프 분기로 정식화(선행 문서 5절) — 그러면 스플라인 수정 시 버튼도
      안 눌러도 된다
