# LineGraphWidget 곡선 후처리 (두께 불균일/삐죽거림 개선)

2026-09-04 / 구현 완료(빌드·육안 확인 대기) / 픽셀 버킷 리샘플 + monotone cubic 보간 + 히스토리 EMA/중앙값 필터로 고도·속도 그래프를 부드럽게.

## 증상

`WBP_SelfDefenseMonitor1`의 고도(ALT)/속도(SPD) 그래프가 (1) 구간마다 선 두께가 달라 보이고
(2) 잘게 삐죽거렸다. 원인이 서로 다른 두 문제였다.

### ① 두께 불균일 = 렌더 아티팩트 (데이터 문제 아님)

`HistoryLength=300`(30Hz × 10초)인데 이 그래프는 화면상 90px 남짓 → **픽셀당 정점 3~4개**.
`FSlateDrawElement::MakeLines`는 세그먼트마다 두께 2px짜리 AA 쿼드를 만들어 그리므로, 정점
간격이 픽셀보다 좁으면 쿼드들이 서로 겹쳐 알파가 누적된다. 값이 세로로 흔들리는 구간만 유독
굵고 진해 보이던 게 이것 — **값을 아무리 부드럽게 만들어도 안 없어지는 종류의 문제**다.

### ② 삐죽거림 = 데이터 노이즈

`ADronePawn::UpdateStatusHUDFlightData()`가 `Flight->GetVelocityMS()`(Chaos 강체 속도)를 그대로
넘기고, `UStatusHUDComponent`가 필터 없이 30Hz로 히스토리에 쌓았다. 로터 진동이 그대로 실린다.
DronePawn.cpp의 "강체 속도라 필터 없이도 매끄럽다"는 주석은 UAV의 위치 미분 대비 상대적으로
매끄럽다는 뜻이지, 90px 폭 그래프에서 매끄럽다는 뜻은 아니었다.

## 변경 내용

### `LineGraphWidget.h/.cpp` — ① 리샘플 + ③ 보간

`SLineGraph::OnPaint`에서 히스토리 점을 화면좌표로 바꾼 직후, **선과 그라데이션이 갈라지기 전에**
한 번만 후처리한다(따로 만들면 채우기 윗변과 선이 어긋나 테두리가 지저분해짐).

- `ResampleByPixelBuckets()` — 가로 `ResampleBucketPixels`(기본 2px)마다 정점 1개로 버킷 평균.
  겹침 아티팩트가 원천적으로 사라지고, 평균이 픽셀 이하 크기 노이즈도 같이 걷어낸다.
  양 끝 정점의 X만 원본 위치로 되돌린다 — 안 그러면 "지금"에 해당하는 오른쪽 끝이 버킷 폭만큼
  안쪽으로 들어가서 곡선이 오른쪽 가장자리에 닿지 않는다.
- `BuildMonotoneCubic()` — Fritsch–Carlson monotone cubic Hermite로 `CurveStepPixels`(기본 1.5px)
  간격 평가. **Catmull-Rom을 안 쓴 이유는 오버슛**이다: 데이터에 없던 봉우리가 생기면 곡선이
  위젯 밖으로 삐져나가거나 값이 0일 때 바닥 아래로 내려가는데, 그라데이션 채우기가 곡선을
  따라가는 구조라 그대로 티가 난다. 단조 보정(원 논문의 a²+b²≤9 원형 제약)이 이걸 막는다.
- 버킷/스텝 폭은 **화면 픽셀 기준**이라 `AllottedGeometry.Scale`로 나눠 로컬 좌표로 환산한다
  (`MakeLines` 두께 처리와 같은 이유 — DPI/디자이너 줌이 달라져도 기준이 유지됨).
- Details 패널 노출: `bSmoothCurve` / `ResampleBucketPixels` / `CurveStepPixels`.
  `bSmoothCurve=false`면 예전 동작 그대로.
- 정점 수가 모자라 후처리가 실패하면(전부 한 버킷에 몰리는 등) 원본 점으로 폴백한다.

### `StatusHUDComponent.h/.cpp` — ② 필터

`FGraphSampleFilter`(플레인 구조체, 채널당 하나) 추가. 히스토리 push 직전에 적용:

1. **최근 3샘플 중앙값**(`bGraphSpikeRejection`, 기본 켬) — 한 프레임짜리 튄 값을 버린다.
   평균과 달리 정상 구간엔 영향이 없고 지연도 1샘플(1/30초)뿐이다.
2. **프레임률 독립 1극 저역통과** — `Alpha = 1 - exp(-dt/Tau)`.
   `AltitudeGraphSmoothingTauSeconds=0.3` / `SpeedGraphSmoothingTauSeconds=0.5`(0이면 끔).
   Alpha를 상수로 두면 샘플 간격이 흔들릴 때 차단 주파수가 같이 흔들려서 이 형태를 썼다.
   시정수를 1초 이상으로 키우면 실제 급상승/급가속까지 뭉개져 계기가 늦게 반응하는 것처럼 보인다.

**필터는 히스토리에 들어가는 값에만 건다.** `CurrentData.AltitudeMeters`/`SpeedKmh`(계기 숫자와
다른 소비자들이 읽는 값)는 원본 그대로 — 곡선만 부드럽게 하는 게 목적이라서.

또 `TimeSinceLastSample`을 리셋하기 전에 받아둬서 필터의 dt로 넘긴다.

### 순서가 중요

**EMA(저장 시) → 버킷 평균(그릴 때) → 스플라인(정점 사이)**. 뒤집으면 안 된다.
버킷 평균 자체가 이미 저역통과라서 EMA 시정수를 과하게 잡을 필요가 없다.

## 세로축 상한 조사 (동적 상한은 미구현)

`WBP_SelfDefenseMonitor1` CDO 실측: `UAVAltitudeGraphMaxMeters=150`, `UAVSpeedGraphMaxKmh=75`.

`New_kadex_0811`의 비행 경로/드론 실측(2026-09-04):

| | 값 | 그래프상 위치 |
|---|---|---|
| 드론 스폰 Z | -3835cm (`BP_Drone_C_2`) | — |
| `uavpath` (DroneFlightPath_1) 고도 | 25.8 ~ 90.0m | 상한 150m의 17~60% |
| `uavpath2` (DroneFlightPath_0) 고도 | 49.7 ~ 139.1m | 상한 150m의 33~93% |
| 순항 속도 (`Autopilot.CruiseSpeedKmh`, 레벨 인스턴스) | 70km/h | 상한 75의 **93%** |

→ **고도 150m는 정당하다**(uavpath2가 139m까지 감). 사진에서 곡선이 바닥에 눌려 보인 건 그
시점 고도가 33m라 그런 것이고, 상한을 낮추면 uavpath2에서 천장에 붙어버린다. 손대지 않음.

→ **속도 75km/h는 빡빡하다.** 순항이 70이라 그래프 상단에 눌려붙고, 강하/돌풍으로 조금만
넘겨도 평평하게 잘린다. 90 정도가 적당(순항이 78% 높이). 사용자 확인 대기 중.

이 표가 곧 **동적 상한(오토 레인지)의 근거 데이터**다. 다음 작업 때 쓸 설계 결론:
하한 0 고정 + 상한만 동적, `max(창 최대값 × 1.25, 최소상한)`을 예쁜 숫자 사다리
(10/20/30/50/75/100/150/200/300/500)로 스냅, 확장은 즉시·축소는 피크가 창을 벗어난 뒤
1~2초 지연 후 `FInterpTo`. 최소상한이 없으면 이륙 직전 지면 진동이 산맥처럼 보이고,
사다리가 없으면 상한이 미세하게 계속 움직여 곡선 전체가 꿈틀댄다(breathing).

## 영향 범위

`SLineGraph`를 쓰는 모든 위젯 — `WBP_SelfDefenseMonitor1` 외에 `Monitor1Widget`,
`StatusHUDWidget`의 고도/속도 그래프도 같이 좋아진다. 필터는 `UStatusHUDComponent` 공용이라
같은 컴포넌트를 쓰는 차량 전부에 적용된다.

## 건드린 파일

- `Source/titan_example/UI/LineGraphWidget.h` / `.cpp`
- `Source/titan_example/UI/StatusHUDComponent.h` / `.cpp`
