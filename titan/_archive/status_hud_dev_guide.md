> [보관됨 2026-08-31] 여기서 다루는 `Monitor1Widget`/구 대시보드 체계는 더 이상 안 쓰임 —
> 현재 실사용 UI는 `SelfDefenseMonitor1Widget`/`SelfDefenseMonitor2Widget`/`AxisSelectionWidget`
> 등(사용자 확인). 전용 후속 문서는 아직 없음, 필요시 새로 조사.

# UAV 상태 정보 위젯 (StatusHUD) 개발 문서 (2026-06-25)

`titan_example` 프로젝트에 추가한 "UAV 상태 정보" 오버레이 — 배터리/고도/속도/방향/GPS/링크/
임무/신호 세기를 보여주는 4분할 카메라 위젯의 동반 기능. M키로 4분할 뷰와 같이 켜고 끔.

QuadCamModule과 달리 **플러그인으로 만들지 않고 `titan_example` 모듈 안에 직접 위치**시킴
(요구사항이 titan 프로젝트에 한정되어 있고, 디자인팀 협업 때문에 레이아웃을 WBP로 분리한
시점에서 플러그인화의 이득이 크지 않다고 판단).

## 1. 설계 방향

- **레이아웃은 WBP, 로직/그리기는 C++** — UMG Designer에서 카드 배치·색상·폰트를
  자유롭게 바꿀 수 있기 위해, QuadCam의 `WBP_QuadCam`과 똑같은 패턴을 씀:
  C++ 베이스 클래스(`UStatusHUDWidget`)가 `BindWidgetOptional`로 필요한 위젯 "이름"만 선언하고,
  실제 트리 구성은 디자이너가 WBP에서 만든다.
- **꺾은선 그래프/원형 게이지/컴포스는 Slate 커스텀 페인트** — UMG 기본 위젯으로는 그릴 수 없는
  부분만 C++ `SLeafWidget` 파생 클래스로 직접 그림(`FSlateDrawElement::MakeLines`/`MakeBox`).
  나머지(카드 배치, 텍스트, 보더 색상)는 전부 일반 UMG 위젯.
- **QuadCamComponent와 동일한 M키/possession 게이팅 패턴** — 두 컴포넌트는 서로 모르고 독립
  적으로 동작하지만, 같은 키 입력을 각자 읽기 때문에 결과적으로 항상 같이 켜지고 꺼짐.

## 2. 파일 구조

```
titan_example/Source/titan_example/UI/
  StatusHUDTypes.h        FUAVStatusData (배터리/고도/속도/방향/GPS/링크/임무/신호 + 그래프 히스토리)
  StatusHUDComponent.h/.cpp   UActorComponent — M키 토글, possession 게이팅, 더미 데이터 생성기
  StatusHUDWidget.h/.cpp      UUserWidget 베이스 — BindWidgetOptional 이름 선언 + UpdateStatus()
  LineGraphWidget.h/.cpp      SLineGraph(Slate) + ULineGraphWidget(UWidget 래퍼) — 꺾은선 그래프
  RadialGaugeWidget.h/.cpp    SRadialGauge(Slate) + URadialGaugeWidget — 배터리 원형 게이지
  CompassWidget.h/.cpp        SCompass(Slate) + UCompassWidget — 방향 컴포스
```

`titan_example.Build.cs`의 `PublicIncludePaths`에 `"titan_example/UI"` 추가됨.
`Vehicles/TitanTruck.h/.cpp`에 `StatusHUD` 네이티브 컴포넌트 추가됨 (QuadCam과 나란히).

## 3. 핵심 동작

### StatusHUDComponent
- `ToggleKey`(기본 M) — `WasInputKeyJustPressed`로 매 프레임 직접 읽음. QuadCamComponent와
  동일한 패턴이라 두 컴포넌트가 서로 의존하지 않고도 동시에 토글됨.
- 소유 Pawn이 **로컬 플레이어에게 Possess된 상태일 때만** 반응. Possess를 잃으면 자동으로 숨김
  (`OwnerPawn->GetController() == LocalPC` 체크).
- `bUseDummyData = true`(기본값)면 매 틱마다 `GenerateDummyData()`가 사인파 2개 + 랜덤 지터를
  합성해서 배터리/고도/속도/방향/링크/신호 값을 만들어냄. 실제 차량 데이터 연동 시 이 플래그를
  끄고 `SetStatusData(FUAVStatusData)`를 외부에서 호출하면 됨 (BlueprintCallable로 노출되어
  있어 BP에서도 호출 가능).
- 숫자 표시는 매 틱 갱신되지만, **그래프 히스토리 샘플링은 `HistorySampleIntervalSeconds`
  (기본 1초)마다 한 번만** 기록함 (`TimeSinceLastSample` 누적). 매 틱(60fps) 기록하면 60개
  버퍼가 1초 만에 가득 차서 그래프 시간축이 에디터 프레임레이트에 따라 늘었다 줄었다 하는
  문제가 있었음 — 고정 간격 샘플링으로 해결.
- 그래프가 나타내는 시간 폭은 `HistoryLength * HistorySampleIntervalSeconds`(기본 60 * 1s = 1분)
  이고, 이 값을 `FUAVStatusData.GraphWindowSeconds`/`GraphSampleIntervalSeconds`에 실어서
  위젯에 전달함.

### 그래프가 "가짜 과거 데이터" 없이 1분 폭을 유지하는 법
처음엔 버퍼를 60개로 미리 채워서 시간축을 고정하는 방식을 썼었는데, 실제로 존재하지 않았던
과거 데이터를 만들어내는 게 부적절하다고 판단해서 더 정직한 방식으로 교체함:

- `AltitudeHistory`/`SpeedHistory`는 빈 배열로 시작.
- `SLineGraph::OnPaint`에서 각 점의 X좌표를 "점 개수 기준 등분"이 아니라 **"실제 나이(초) 기준
  고정 폭 매핑"**으로 계산함: `AgeSeconds = (마지막 인덱스 - 현재 인덱스) * SampleIntervalSeconds`,
  `X = Size.X * (1 - clamp(AgeSeconds / WindowSeconds, 0, 1))`.
- 그 결과: 데이터가 30초만 쌓였으면 그래프 오른쪽 절반에만 선이 그려지고 왼쪽 절반은 빈 채로
  남음. 1분이 지나야 좌측 끝까지 자연스럽게 채워짐 — 가짜 데이터 없이 "오른쪽에서 자라나는"
  모양이 됨.

### 커스텀 Slate 위젯 3종
- `SLineGraph`(`LineGraphWidget.h/.cpp`): 배경 박스 + 값 배열을 `MakeLines`로 연결. 색상은
  `ULineGraphWidget::LineColor`(EditAnywhere)로 WBP Details에서 지정 가능.
- `SRadialGauge`(`RadialGaugeWidget.h/.cpp`): 배경 링(연한 회색) + percent만큼의 호(`GaugeColor`)
  를 `MakeArcPoints()`로 계산한 원호 점들을 `MakeLines`로 그림. 중앙 "%" 텍스트는 그리지 않고
  WBP에서 `Overlay`로 `TextBlock`을 겹쳐서 표시 (Slate에서 텍스트 중앙 정렬하려면 폰트 측정이
  필요해서 더 복잡함 — UMG Overlay로 우회).
- `SCompass`(`CompassWidget.h/.cpp`): 원 외곽선 + N/E/S/W 4개 틱마크(고정) + 방향(heading)에
  따라 회전하는 바늘 선 1개. N/E/S/W 글자, 각도 숫자는 마찬가지로 WBP에서 별도 TextBlock으로
  배치.
- 세 클래스 모두 `ReleaseSlateResources()`를 오버라이드해서 내부 `TSharedPtr<SWidget>`을
  `Reset()`함 — 안 하면 위젯 제거 시 "유출 감지(Slate 리소스가 살아있음)" 경고가 뜸. UWidget을
  상속해서 자체적으로 `TSharedPtr<SWidget>` 멤버를 들고 있는 커스텀 위젯을 만들 때는 항상 필요.

### StatusHUDWidget — BindWidgetOptional 이름 목록
`WBP_StatusHUD`(부모 클래스 = `StatusHUDWidget`)에서 아래 이름의 위젯을 배치해야 값이 갱신됨.
이름이 틀리거나 타입이 다르면 조용히 무시되고 그 항목만 안 보임 (에러 안 남):

| 이름 | 타입 | 용도 |
|---|---|---|
| `BatteryGauge` | RadialGaugeWidget | 배터리 원형 게이지 |
| `BatteryPercentText` | TextBlock | "78%" |
| `FlightTimeText` | TextBlock | "비행 시간 25:45" |
| `AltitudeText` | TextBlock | "152 m" |
| `AltitudeGraph` | LineGraphWidget | 고도 꺾은선 그래프 |
| `SpeedText` | TextBlock | "32.6 km/h" |
| `SpeedGraph` | LineGraphWidget | 속도 꺾은선 그래프 |
| `Compass` | CompassWidget | 방향 컴포스 |
| `HeadingText` | TextBlock | "312°" |
| `GpsFixText` | TextBlock | "3D 고정" |
| `GpsSatText` | TextBlock | "위성: 12" |
| `LinkStatusText` | TextBlock | "강함" |
| `LinkQualityText` | TextBlock | "품질: 72%" |
| `MissionStatusText` | TextBlock | "임무 수행중" |
| `MissionWaypointText` | TextBlock | "WP 2/4" |
| `SignalDbmText` | TextBlock | "-62 dBm" |
| `SignalBar1`~`SignalBar5` | Border | 신호 막대 5칸 (높이를 점점 키워서 배치) |

## 4. 새 WBP_StatusHUD 만드는 법 (디자이너용)

1. Content Browser → Widget Blueprint 생성, 이름 `WBP_StatusHUD`
2. Class Settings → Parent Class를 `StatusHUDWidget`으로 변경
3. 팔레트에서 "RadialGauge"/"LineGraph"/"Compass" 검색하면 커스텀 위젯 3종이 일반 위젯처럼
   나타남 — 드래그해서 배치
4. 각 위젯을 위 표의 이름으로 정확히 변경 (Details 패널 맨 위 이름 필드)
5. `BatteryGauge` + `BatteryPercentText`처럼 겹쳐야 하는 항목은 `Overlay`로 감싸고 양쪽 정렬을
   Center로
6. `BP_TitanTruck`의 `StatusHUD` 컴포넌트 Details → `Status HUD Widget Class`에 `WBP_StatusHUD` 지정

## 5. 다른 액터에 적용하기

QuadCam과 마찬가지로 `UStatusHUDComponent`를 아무 Actor/Pawn에 추가하고
`StatusHUDWidgetClass`에 `WBP_StatusHUD`(또는 그 파생 WBP)를 지정하면 끝. 컴포넌트 자체는
어떤 액터에 붙어 있는지 모르고, possession 여부만 보고 동작하므로 트럭이 아닌 다른 Pawn에도
바로 적용 가능.

## 6. 알려진 한계 / 다음 단계

- 지금은 `bUseDummyData = true`로 사인파+랜덤 더미 데이터만 표시. 실제 차량 텔레메트리 연동은
  `bUseDummyData = false`로 바꾸고 `SetStatusData()`를 실제 값으로 주기적으로 호출하면 됨
  (구조는 이미 준비되어 있고 위젯 쪽은 변경 불필요).
- `WBP_StatusHUD`는 아직 레퍼런스 이미지 수준으로 디자이너가 다듬지 않은 임시 레이아웃 상태일
  수 있음 — 디자인팀에게 위 3번 표를 전달하면 이름만 맞춰서 자유롭게 재배치 가능.
- 플러그인화는 보류 상태. 추후 다른 프로젝트(예: TankSim)에 재사용할 필요가 생기면
  QuadCamModule을 플러그인으로 승격했던 것과 같은 절차(코드+Content를 plugin 폴더로 이동,
  `CoreRedirects`로 클래스 경로 정리)를 다시 거쳐야 함.
