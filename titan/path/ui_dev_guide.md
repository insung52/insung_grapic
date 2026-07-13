# 모니터 1/2 UI 연동 개발 가이드 (작성 2026-07-10, 2026-07-10 갱신)

## 사용자 확인 답변 정리 (7절 질문에 대한 답, 갱신본)

- **memo.md는 구버전**, Figma PNG가 최신 기준. memo.md에만 있고 새 디자인엔 없는 기존 구현
  (UGV 4분할캠/UGV상태정보/미니맵의 ugv.png 버전 등)은 **제거하지 않고 그대로 코드에 남겨둠**
  — 나중에 다시 쓸 가능성 있음.
- **모니터2(RCWS 뷰어)는 트럭/UGV 공용 화면 확정** (0.1절의 해석 (b)) — 다만 최종 확정 전까지는
  **기본값을 UGV RCWS로** 설정. `Atitan_examplePlayerController::SetCameraControlTarget`으로
  전환하는 기존 기능은 그대로 유지.
- **RCWS 줌은 사용자가 직접 조이스틱(`IA_CameraZoom` 신규 추가 예정)에 연동** — C++ 쪽은
  `URCWSComponent::AddZoomInput(float Delta)`/`SetZoomLevel(float)`만 준비해두면 됨(완료, 아래
  구현 현황 참고). 입력 바인딩은 이 문서의 스코프 밖.
- **UGV/UAV/트럭 미니맵 마커는 디자인 에셋 없음** — 간단한 삼각형(색상으로 구분)으로 구현
  (완료, `VehicleMarkerWidget` 참고). WP1/WP2용 `T_blue_marker`/`T_green_marker`는 기존 계획대로
  사용.
- **`T_Vector`** = 비행시간 텍스트 옆에 놓는 아이콘. **`T_Rectangle`/`_1`/`_2`/`_3`** = 신호 세기
  표시용 사각형 4개(디자인됨). 둘 다 사용자가 WBP에서 직접 배치할 아이콘이라 C++ 쪽에서 건드릴
  일 없음(마커류 제외) — 2절 표 갱신.
- **방위각은 확정: 차체 기준이 아니라 절대 방위(진북 기준)** — 구현 완료(아래 참고).
- **위경도 원점: 임시로 강원도 인제** — 실제 좌표는 나중에 전달, 그 전까지 `GeoCoordinateUtils.h`의
  `OriginLatitude`/`OriginLongitude` 값만 교체하면 전체가 갱신됨(완료).
- **적 예상 위치**: 시나리오 시작 명령어(`BeginScenarioEnemyContact` Exec 커맨드, 완료)를 치면
  씬의 `enemycube` 스태틱메시 액터(태그 `EnemyCube`를 MCP로 이미 추가함 — **레벨 저장 필요**,
  아래 참고) 위치를 예상 위치로 사용. 전체 시나리오(#4-1~#4-8) 자동화는 별도 작업으로 미룸.

## 구현 현황 (2026-07-10)

완료:
- `URCWSComponent`: `ZoomLevel`/`MinZoomLevel`/`MaxZoomLevel` + `AddZoomInput`/`SetZoomLevel`
  (FOV = `CameraFOV / ZoomLevel`), `RNG` 거리(`GetRangeMeters`, 매 틱 라인트레이스,
  `FRCWSStatusData::RangeMeters`), 방위각을 `SightCamera->GetComponentRotation().Yaw` 기반 절대
  방위(0~360 정규화)로 변경 — `TitanTruck`/`AUGVPawn` 둘 다 자동 적용됨(같은 컴포넌트).
- `AUAVPawn`: `ZoomLevel`(1.0x/2.5x 등 버튼용) + `SetZoomLevel`, `GetLatitudeText`/
  `GetLongitudeText`(가짜 GPS, `GeoCoordinateUtils.h`).
- `AUGVAIController::GetLastPathPoints()` — 미니맵 경로선용 실시간 경로 포인트 배열(신규, 기존
  `GetLastPathPointsAsJson`은 그대로 유지).
- `UScenarioStateSubsystem` + `Atitan_examplePlayerController::BeginScenarioEnemyContact` Exec
  커맨드 — "enemycube" 액터(태그 `EnemyCube` 추가함) 위치를 적 예상 위치로 저장.
- `UScrollingRulerWidget`/`SScrollingRuler` — 2절에서 설계한 4곳 전부 커버하는 범용 눈금 리본
  (방위각처럼 스크롤하는 wrap 모드 / EL·ZOOM처럼 고정범위+이동 포인터인 non-wrap 모드 둘 다 지원).
- `ULineGraphWidget` 그라데이션 채우기 옵션 추가(`bShowGradientFill`/`FillOpacityAtLine`) — 3절
  질문 해결.
- `UVehicleMarkerWidget`/`SVehicleMarker` — 미니맵용 단순 삼각형 마커(색상만 지정, 회전은 WBP의
  RenderTransform Angle을 헤딩값에 바인딩).
- `URadialAreaWidget`/`SRadialArea` — 부채꼴/원을 한 클래스로 커버(전부 코드로 그림, 디자인 에셋
  불필요). `SpanDegrees`가 360이면 꽉 찬 원(적 예상 위치 반투명 빨간 원), 360보다 작으면 그
  각도만큼의 부채꼴(RCWS/UAV 시야각 콘) — `FacingDegrees`만 갱신하면 됨.
- `UPolylineWidget`/`SPolyline` — 점 배열(정규화 UV, `DetectionOverlayWidget`/
  `WorldToMinimapUV`와 동일한 좌표계)을 이어 그리는 선. `bDashed`로 실선(UGV 경로)/점선(UAV
  WP1→WP2) 둘 다 커버.

- `UMonitor1Widget`/`UMonitor2Widget` — 조립 완료. Monitor1은 헤더/메인뷰/트럭4분할캠+미니리본/
  미니맵(마커·FOV콘·경로선·적예상위치)/UAV상태정보/UAV영상피드를 전부 바인딩. Monitor2는
  `Atitan_examplePlayerController::GetCameraControlTarget()`(신규 getter)로 트럭/UGV RCWS 중
  뭘 보여줄지 매 갱신마다 결정(기본값 UGV, 0.1절 참고), RCWS 상태정보 더미 필드
  (`ERCWSControlMode`, `PowerVoltage` 등 `RCWSTypes.h`에 신규 추가) 포함 전부 바인딩.
- `AUAVPawn`의 임무 WP 값(1/4→도착 후 2/4)이 기존엔 더미로 고정 2였던 걸
  `UStatusHUDComponent::SetRealMissionWaypoint`로 실제 `MissionState` 연동하도록 수정.

빌드 전 발견/수정한 버그: 새 위젯 4개(`ScrollingRulerWidget`/`LineGraphWidget`/
`VehicleMarkerWidget`/`RadialAreaWidget`)에 잘못된 경로로 넣었던 `#include "Layout/
SlateLayoutTransform.h"`를 실제 엔진 경로인 `Rendering/SlateLayoutTransform.h`로 수정함
(사용자가 빌드해서 발견, 감사).

남은 작업: 없음(WBP 쪽 실제 배치/이름 맞추기는 사용자 작업 — 5절 각 항목의 WBP 이름/설정값
참고).
- 나침반(원형) PNG 오버레이 자체는 WBP 작업(2.2절 공식 참고)이라 C++ 쪽 할 일 없음.

**레벨 저장 필요**: `kadex_demo`에 MCP로 `enemycube` 액터에 `EnemyCube` 태그를 추가했는데, 이
액터가 "external actor asset"이 아니라 레벨에 직접 저장하는 방식이라 MCP의 개별 저장이 안 먹힘
— 에디터에서 레벨을 한 번 저장(Ctrl+S)해줘야 태그가 디스크에 남음.

**갱신(2026-07-10) — 그래프 품질/속도 개선**:
- `LineGraphWidget`의 그라데이션을 밴딩(얇은 사각형 여러 겹) 방식에서 `FSlateDrawElement::
  MakeCustomVerts` 기반 진짜 정점 그라데이션으로 교체 — 곡선을 따라가는 도형(위쪽 정점=선 색상,
  아래쪽 정점=투명)을 직접 만들어서 GPU가 알아서 부드럽게 보간해줌. 결과적으로 "사각형 전체에
  그라데이션 주고 곡선 아래만 보이게"와 수학적으로 동일한 결과(밴딩 없음).
- `StatusHUDComponent`의 히스토리 샘플링을 초당 1회(1분 창)에서 **초당 30회, 10초 창**으로 변경
  (`HistoryLength=300`, `HistorySampleIntervalSeconds=1/30`, `UIUpdateIntervalSeconds=1/30`도
  같이 맞춤 — 안 맞추면 샘플링 체크 자체가 그 주기로만 실행돼서 30fps가 실제로 안 나옴).
- `Monitor1Widget`의 `UAVAltitudeGraph`/`UAVSpeedGraph` `SetValues` 호출도 리본과 같은 이유로
  매 프레임(스로틀 없이) 실행하도록 이동 — 안 그러면 히스토리 자체는 30fps로 쌓여도 위젯에
  넘겨주는 시점이 0.2초마다라 화면상으론 여전히 뚝뚝 끊겨 보임.
- 그라데이션 알파 기준을 "곡선~바닥 상대값"에서 "위젯 바닥(0)~천장(FillOpacityAtLine) 절대값"으로
  수정 — 이전엔 값이 낮을 때(곡선이 바닥 근처)도 정점 알파가 항상 최댓값이라 얇은 띠에 색이
  진하게 뭉쳐 보였음. 이제 곡선 높이에 비례해서 알파도 낮아짐(예: 값이 0.1 높이에 있으면
  그 지점 알파도 `FillOpacityAtLine`의 0.1배). 그래프 반투명 회색 배경 박스도 제거함.

**갱신(2026-07-10) — 리본 4종 세분화**: 디자인 시안 보니 리본 스타일이 4가지로 갈림. 클래스는
2개로 정리(완전히 4개로 쪼개진 않음 — EL/ZOOM은 로직이 90% 겹쳐서 플래그로 처리):
- `ScrollingRulerWidget`(기존 클래스 확장): `bShowMidTicks`로 3단계 눈금(대/중/소, 대→majors만
  라벨), `bShowSpine`으로 눈금들을 잇는 축선, `bMirrored`로 좌우반전 — UAV영상피드/RCWS azimuth
  는 `bShowMidTicks=true`로, EL/ZOOM은 `bShowSpine=true`+`bMirrored`(EL=false/ZOOM=true)로 설정.
- `CompactHeadingRibbonWidget`(신규 클래스) — 4분할캠 미니 리본 전용. 텍스트/눈금이 같은
  베이스라인에 있고(ScrollingRulerWidget은 눈금 아래 라벨이 따로 있는 구조라 안 맞음), 8방위
  전부 표시하되 현재값과 가장 가까운 것만 흰색/나머지는 회색 반투명 — 색상 로직 자체가 완전히
  다른 방식(다른 위젯들은 다 "선 색 하나"인데 이건 하이라이트/딤 이진 색상)이라 별도 클래스로
  분리하는 게 맞다고 판단함. 삼각형 포인터는 요청으로 제거함(WBP에서 별도 배치 가능).

**갱신(2026-07-10) — 눈금 길이 커스텀 + WBP 줌 시 두께 미리보기 문제**:
- `ScrollingRulerWidget`에 `MajorTickLengthFraction`(대눈금 길이, cross-axis 크기 대비 비율)
  추가 — 기존엔 0.4 고정값이었음. Mid/Minor는 그대로 "Major 길이 대비 비율".
- `CompactHeadingRibbonWidget`에 `TickHeightFraction`(눈금 길이, 위젯 높이 대비 비율) 추가 —
  기존엔 고정값(0.6)이었음.
- **WBP 디자이너에서 확대/축소해도 선(눈금) 두께가 화면상 그대로였던 이유**: 엔진 소스
  확인 결과 `FSlateDrawElement::MakeLines`의 두께 파라미터는 의도적으로 "스크린 픽셀" 단위로
  해석되고, 렌더러가 내부적으로 `/ DrawElement.GetScale()`을 해서 로컬 좌표로 되돌림
  (`SlateCore/Private/Rendering/ElementBatcher.cpp`) — Box/Text 요소들은 위치/크기가 이미
  로컬 공간 기준이라 자연스럽게 줌에 맞춰 커지는데, Line 두께만 "항상 화면상 N픽셀"이 되도록
  일부러 줌 무관하게 설계된 것. 고침: 두께 값에 `AllottedGeometry.Scale`을 미리 곱해서 넘기면
  내부 나눗셈이 상쇄되어 다른 요소들처럼 줌에 비례해서 커짐 — 이 프로젝트의 선을 그리는 커스텀
  페인트 위젯 전부(`ScrollingRulerWidget`/`CompactHeadingRibbonWidget`/`CompassWidget`/
  `RadialGaugeWidget`/`VehicleMarkerWidget`/`RadialAreaWidget`/`PolylineWidget`/
  `DetectionOverlayWidget`/`LineGraphWidget`)에 동일하게 적용함 — 이제 WBP 디자이너에서 확대해서
  실제 두께를 눈으로 바로 확인 가능, Play 안 해봐도 됨.

**갱신(2026-07-10) — WBP 디자이너에서 프로퍼티 수정 시 컴파일 없이 바로 미리보기**: 지금까지
만든 커스텀 페인트 위젯 전부가 `RebuildWidget()`에서만 프로퍼티 값을 반영하고 있었음 —
`RebuildWidget()`은 위젯이 처음 만들어질 때(=컴파일 시점)만 호출되니까, Details 패널에서 값
바꿔도 컴파일 전까진 반영이 안 됐던 것. 기본 위젯(Image, TextBlock 등)은 `SynchronizeProperties()`
라는 별도 함수를 통해 Details 패널 값이 바뀔 때마다(`UWidget::PostEditChangeProperty`가 자동 호출)
실시간으로 갱신됨 — 이 함수를 9개 위젯(`ScrollingRulerWidget`/`CompactHeadingRibbonWidget`/
`CompassWidget`/`LineGraphWidget`/`RadialGaugeWidget`/`DetectionOverlayWidget`/
`VehicleMarkerWidget`/`RadialAreaWidget`/`PolylineWidget`) 전부에 추가해서 동일하게 동작하도록
맞춤. 이제 Details 패널에서 값 바꾸면 컴파일 안 해도 WBP 디자이너 캔버스에 바로 반영됨.

**갱신(2026-07-10) — 좌/우 모니터가 둘 다 화면 왼쪽에 겹쳐 그려지던 문제**:
`Atitan_examplePlayerController::BeginPlay()`가 `AddToViewport()`만 호출하고 있었는데, 이건
기본적으로 위젯을 뷰포트 전체(앵커 (0,0)~(1,1))에 꽉 채우는 동작이라 — 왼쪽/오른쪽 위젯 둘 다
전체 화면에 늘어나서 서로 겹쳤고, `WBP_kadex1`이 `WBP_kadex`를 복제해서 만든 거라 내부 위젯들이
아직 왼쪽 절반 좌표 그대로라 둘 다 화면 왼쪽에 내용이 몰려 보였던 것. `SetAnchorsInViewport`로
왼쪽은 `(0,0)~(0.5,1)`, 오른쪽은 `(0.5,0)~(1,1)`로 각자 화면 절반만 차지하도록 고침 — 이제
`WBP_kadex1` 내부 위젯 좌표를 따로 오른쪽으로 옮길 필요 없이, 위젯 자신의 로컬 좌표계 기준
왼쪽 절반에 있던 내용이 자동으로 실제 화면 오른쪽 절반 안에 들어감.

**갱신(2026-07-10) — DetectionOverlayWidget 누락 발견/수정**: `Monitor1Widget`/`Monitor2Widget`을
새로 만들면서 예전 `MissionDashboardWidget`에 있던 탐지 바운딩 박스 배선(`DetectionOverlayWidget`)을
그대로 안 옮겨서, WBP에 위젯을 배치해도 아무것도 그려지지 않는 상태였음(위젯 자체는 멀쩡함,
그냥 아무도 `SetDetections()`를 호출 안 하고 있었음). `MainViewDetectionOverlay`/
`UAVCameraDetectionOverlay`(Monitor1), `RCWSDetectionOverlay`(Monitor2) 3개를 추가하고 각각
매칭되는 `TargetDetectionComponent`에 연결함 — 8절 표에도 반영함.

**갱신(2026-07-10) — DetectionOverlayWidget 실제 원인은 이름 불일치였음**: 위 수정을 해도 여전히
안 그려지길래 PIE로 직접 `DetectedTargets`를 읽어봤더니 탐지 자체는 정상(UGV를 신뢰도 1.0으로
잡고 있었음, UV 좌표도 유효) — 즉 데이터는 멀쩡한데 화면에 안 그려지는 상황이었음. 원인은
`WBP_kadex`가 예전에 `MissionDashboardWidget`을 부모로 만들어졌을 때 위젯 이름을
`TruckRCWSDetectionOverlay`(`MissionDashboardWidget`의 필드명)로 지어놨었는데, 부모를
`Monitor1Widget`으로 바꾼 뒤에도 위젯 이름은 그대로 남아있었던 것 — 타입은 맞아도(`Detection
Overlay Widget`) 이름이 `Monitor1Widget`이 기대하는 `MainViewDetectionOverlay`랑 달라서
`BindWidgetOptional`이 조용히(에러 없이) 실패하고 있었음. WBP에서 위젯 이름만 바꿔주면 해결.

**부모 클래스가 바뀐 적 있는 WBP에서 흔히 겪을 수 있는 이름 불일치표** (예전
`MissionDashboardWidget`/`WBP_test` 기준 이름 → 현재 `Monitor1Widget`/`WBP_kadex` 기준 이름):

| 예전 이름 (MissionDashboardWidget) | 현재 이름 (Monitor1Widget) |
|---|---|
| `TruckRCWSDetectionOverlay` | `MainViewDetectionOverlay` |
| `UGVRCWSDetectionOverlay` | `RCWSDetectionOverlay` |
| `UAVDetectionOverlay` | `UAVCameraDetectionOverlay` |
| `TruckRCWSImage` | `MainViewImage` |
| `UGVRCWSImage` | `RCWSViewImage` |

증상이 "코드는 맞는 것 같은데 특정 위젯만 계속 안 됨"이면, 그 위젯이 예전 클래스 이름을 그대로
쓰고 있는 건 아닌지부터 확인하는 게 빠름 — Details 패널에서 이름 확인, 아니면 위 표 참고.

**갱신(2026-07-10) — 신호세기 4바를 WBP 그래프 대신 C++로 자동 연동**: 원래 "Visibility만
토글하면 됨"이라고 WBP 쪽 작업으로 미뤘었는데, 이미 이 프로젝트 안에 똑같은 패턴의 선례
(`UStatusHUDWidget::UpdateSignalBars` — `UBorder` 배열 + `SetBrushColor`로 색조 전환, Visibility
토글 아님)가 있었어서 그거랑 똑같이 C++에서 처리하도록 바꿈. `UAVSignalBar1`~`4`(Image)를
이름만 맞춰 배치하면 `LinkQualityPercent` 기준으로 자동으로 하늘색/회색 전환됨 — 그래프 작업
전혀 불필요.

**갱신(2026-07-10) — 단계별 눈금 투명도**: `ScrollingRulerWidget`에 `MajorTickOpacity`/
`MidTickOpacity`/`MinorTickOpacity`(각각 0~1, `LineColor`의 알파에 곱해짐) 추가 — 예를 들어
UAV/azimuth 리본에서 소눈금을 흐리게 하고 대눈금만 진하게 하는 식의 시각적 위계 표현 가능.
대눈금 라벨(숫자/N·E·S·W 텍스트)도 `MajorTickOpacity`를 그대로 따라감.


`ui.md` + Figma 스크린샷 2장(모니터1: "군용 자체방호 통제기 모의기", 모니터2: "RCWS 뷰어")과
현재 코드 상태(`memo.md`, 기존 WBP_test/MissionDashboardWidget)를 대조해서 정리한 작업 계획.
아이콘은 `/Game/UI/Icons`에 이미 33개 추가된 상태(MCP로 직접 확인, 전부 32x32 아이콘 텍스처 +
compass 관련 2장 + 로고 1장) — 아래 2절에서 용도 매핑.

## 0. 가장 먼저: `ui.md`와 실제 Figma 시안 사이에서 발견한 불일치/모호점

### 0.1 모니터 2가 memo.md의 ugv.png와 완전히 다른 화면으로 재설계됨 — 확인 필요

`memo.md`의 기존 오른쪽 모니터(ugv.png) 기획은 "UGV 4분할 캠 + UGV 상태정보 + UGV 원격제어 +
RCWS 정보 + RCWS 영상/제어 + 미니맵"을 한 화면에 다 담는 구성이었음. 그런데 이번에 전달받은
Figma 스크린샷의 "모니터 2"는 **RCWS 뷰어 단독 화면**(조준 화면 + 3D 렌더링 뷰어 + RCWS
상태정보뿐, UGV 4분할캠/UGV상태정보/미니맵 없음)이고 `ui.md`도 정확히 이 구성만 정리되어 있음.

즉 UGV의 4분할캠/상태정보/미니맵이 새 디자인에서 어디로 갔는지가 불명확함. 두 가지 가능성:
- (a) 이번 라운드 스코프에서 아예 제외 — UGV 쪽 화면은 나중 별도 시안으로.
- (b) "RCWS 뷰어"가 고정된 화면이 아니라 **현재 `ECameraControlTarget`(TruckRCWS/UGVRCWS)에
  따라 내용이 바뀌는 공용 뷰어** — 즉 트럭 RCWS를 조작 중이면 트럭 RCWS를, UGV RCWS로 전환하면
  UGV RCWS 데이터를 그대로 보여주는 화면. `Atitan_examplePlayerController::SetCameraControlTarget`이
  이미 있어서 이 해석이면 데이터 배선이 자연스러움.

**확인 필요** — 이 문서는 일단 (b)로 가정하고 작성함(재사용성이 높고 기존 입력 시스템과 바로
맞아떨어짐). UGV 4분할캠/상태정보/미니맵을 아예 다른 화면에 넣을 계획이 있으면 알려주세요.

### 0.2 "UGV 주행영상" 오타 확인됨

`ui.md` 17번째 줄에 이미 명시된 대로, 모니터1 우측 상단 4분할 영상 라벨이 "UGV 주행영상"으로
되어 있지만 실제로는 TitanTruck(이동형 지휘소)의 QuadCam임 — 기존 `QuadCamComponent`를 그대로
쓰면 되고, WBP 텍스트 라벨만 그대로 오타 반영해서 배치하면 됨(코드 변경 없음).

### 0.3 RNG(거리) 값 — 신규 기능 필요

RCWS 조준 화면의 `RNG 1,253 m`은 현재 아무 데이터도 없음. RCWS 조준 카메라(`RCWSSightCamera`)
정면으로 라인트레이스를 쏴서 히트 거리를 반환하는 함수가 `URCWSComponent`에 새로 필요함
(`GetRangeToTargetMeters()` 같은 식 — Detection 모듈의 라인트레이스 패턴 재사용 가능하지만
별개 기능: Detection은 "등록된 대상"만 보고, RNG는 조준선 상의 아무 지형/오브젝트나 히트해도
거리만 알려주면 됨).

### 0.4 줌(Zoom) 값 — RCWS/UAV 둘 다 신규 기능 필요

현재 `URCWSComponent`/`AUAVPawn` 둘 다 `CameraFOV`가 고정값이고 "배율(x)" 개념이 없음. RCWS
조준화면의 0.5x~10.0x 세로 눈금, UAV 영상피드의 1.0x/2.5x 버튼 둘 다 새로 추가해야 함:
- `ZoomLevel`(float, 1.0 = 기본) 프로퍼티 추가
- 배율 → 실제 `FOVAngle`로 환산(예: `EffectiveFOV = BaseFOV / ZoomLevel`, 배율이 커질수록
  FOV가 좁아져 확대되어 보이는 식)
- 조이스틱/버튼 입력으로 배율 조절하는 함수 추가 (RCWS는 세로 눈금 위 어디쯤인지, UAV는 버튼
  두 개 중 어떤 게 선택됐는지를 텍스트 색으로 표시해야 하므로 "현재 배율값"을 WBP가 읽을 수
  있어야 함)

### 0.5 방위각(Azimuth)이 현재 "정규화 안 된 상대각"임 — 눈금 표시 전에 손봐야 함

`URCWSComponent::AddPanTiltInput`을 보면 `CurrentData.AzimuthDegrees`가 마운트의
`RelativeRotation.Yaw`를 그대로 누적한 값이라 **0~360으로 정규화되지 않고, 차체 기준 상대각**임
(예: 계속 한 방향으로 돌리면 Yaw가 730도, -400도처럼 무한히 누적될 수 있음). Figma 시안의
방위각 리본(240 W 330 N 30 60...)은 실제 나침반 방위처럼 보이므로:
- 표시 직전에 `FMath::Fmod` 등으로 0~360 정규화 필요
- **차체 기준 상대각인지 월드(진북 기준) 절대 방위인지 결정 필요** — 트럭/UGV 차체 자체도
  회전하므로, 진짜 나침반처럼 보이려면 `OwnerActor->GetActorRotation().Yaw + MountRelativeYaw`로
  월드 기준 절대 방위를 써야 함. 지금 코드는 상대각만 반환하므로 이 부분 수정이 필요함.

### 0.6 배터리 색상 규칙은 이미 있는 데이터로 충분

`ui.md` 81번째 줄의 "50% 이하 노랑/20% 이하 빨강"은 `FUAVStatusData::BatteryPercent`가 이미
있으므로 새 C++ 로직 불필요 — WBP에서 텍스트 컬러를 바인딩 함수로 계산하거나, C++
`UMissionDashboardWidget`/새 Monitor1 위젯 쪽에서 `SetColorAndOpacity`를 매 갱신마다 세팅하면 됨.

### 0.7 계획 없음으로 확인된 항목 (이번 라운드 스킵)

- ~~RCWS 3D 단독 렌더링 뷰어~~ (`ui.md` 111번째 줄에 명시: "아직은 구현 계획 없음") — **2026-07-11
  구현함**, 아래 "RCWSPreviewActor" 항목 참고. 당시엔 계획이 없었을 뿐 기획서 자체엔 "2. 3D 모델
  시각화 - RCWS 3D 모델 시각화 (고정)" 항목이 있었음이 나중에 확인됨
- 설정(톱니바퀴) 버튼의 실제 설정 UI (`ui.md` 11번째 줄: "설정 ui는 아직 계획 없음") — 버튼
  자체는 배치하되 클릭해도 아무 일도 안 일어나게 두거나, 나중을 위해 빈 `OnClicked` 델리게이트만
  걸어둠
- 미니맵 확대/축소(마우스 휠) — `ui.md`에도 "나중에 구현"으로 명시됨
- 종료 버튼은 실제 게임 종료로 확정(`ui.md` 13번째 줄) — `UKismetSystemLibrary::QuitGame` 호출만
  걸면 되는 단순 기능, 별도 설계 불필요

## 1. 아이콘 자산 매핑 (`/Game/UI/Icons`, MCP로 확인)

전부 32x32 (컴퍼스 관련 2개, 로고 제외). 이름과 스크린샷 대조로 추정한 용도 — **추정이 틀렸거나
다른 용도로 이미 정해둔 게 있으면 알려주세요**, 특히 `T_Rectangle*`/`T_Vector`/`T_triangle`은
이름만으로는 확신이 안 서는 범용 도형이라 실제 배치할 때 다시 확인이 필요할 수 있음.

| 아이콘 | 크기 | 추정 용도 |
|---|---|---|
| `T_logo` | 184x200 | 헤더 좌측 방패 로고 |
| `T_date` | 32x32 | 헤더 날짜 앞 캘린더 아이콘 |
| `T_clock` | 32x32 | 헤더 시간 앞 시계 아이콘 |
| `T_settings` | 32x32 | 헤더 톱니바퀴 버튼 |
| `T_exit` | 32x32 | 헤더 종료(X) 버튼 |
| `T_front`/`T_back`/`T_left`/`T_right` | 32x32 | 4분할 영상 라벨 앞 방향 아이콘(전방/후방/좌측/우측) |
| `T_compass` | 102x102 | 회전하는 나침반 바늘/눈금 레이어 (UAV 상태정보 "방향" 카드) |
| `T_compass_outer` | 32x32 | 고정된 나침반 외곽 테두리 레이어 |
| `T_battery` | 32x32 | 배터리 라벨 아이콘 |
| `T_az` | 32x32 | RCWS 상태정보 "방위각" 라벨 아이콘 |
| `T_el` | 32x32 | RCWS 상태정보 "고각" 라벨 아이콘, EL 세로눈금 라벨 |
| `T_target` | 32x32 | "표적 추적" 라벨 아이콘 / 조준 화면 상 타겟 브라켓(모서리 꺾쇠) |
| `T_crossline` | 32x32 | 조준 화면 중앙 십자선/눈금 |
| `T_mode` | 32x32 | "모드" 라벨 아이콘 |
| `T_system` | 32x32 | "시스템 연결" 라벨 아이콘 |
| `T_power` | 32x32 | "전원 상태" 라벨 아이콘 |
| `T_noti` | 32x32 | "경고/알람" 라벨 아이콘 |
| `T_stabil` | 32x32 | "안정화" 라벨 아이콘 |
| `T_temp` | 32x32 | "시스템 온도" 라벨 아이콘 |
| `T_ammo` | 32x32 | "탄약 현황" 라벨 아이콘 |
| `T_EO` | 32x32 | 영상 좌측 하단 EO 모드 배지 |
| `T_rec` | 32x32 | 영상 좌측 상단 REC 배지 |
| `T_green_marker`/`T_blue_marker` | 32x32 | 미니맵 UAV WP2(초록)/WP1(파랑) 마커 |
| `T_triangle` | 32x32 | 눈금 리본의 현재값 포인터(▲) — 3절 참고 |
| `T_Vector` | 32x32 | 용도 불명확 — 미니맵 방향 화살표 후보로 추정, 확인 필요 |
| `T_Rectangle`/`_1`/`_2`/`_3` | 32x32 | 용도 불명확 — 눈금 리본의 선택값 강조 박스(2.5x 배경 등) 후보로 추정, 확인 필요 |
| `T_monitorA` | 5760x3240 | 아이콘 아님 — 참고용 목업 스크린샷으로 추정(고해상도), 실제 UI 부품으로 안 씀 |

## 2. 방향/줌 눈금(ruler) — 코드로 구현, PNG 불필요 (질문에 대한 답)

`ui.md`에서 물어본 핵심 질문: **눈금 부분은 PNG를 준비해야 하는지 코드로 구현되는지** → 전부
**코드로 구현**합니다. 이유: 숫자가 실시간으로 바뀌고(방위각 240→330→30...), 스크롤되는 위치도
계속 변하기 때문에 고정 PNG로는 애초에 불가능함 — 기존 `SLineGraph`/`SCompass`/`SRadialGauge`
(Slate `SLeafWidget` 커스텀 페인트) 패턴을 그대로 재사용.

### 2.1 신규 위젯: `SScrollingRuler` / `UScrollingRulerWidget`

`Source/titan_example/UI/ScrollingRulerWidget.h/.cpp` 신규 — 아래 4곳에서 전부 재사용 가능한
범용 눈금 리본:

```
Construct 옵션:
  - Orientation (Horizontal / Vertical)
  - CurrentValue (float)
  - bWrap360 (true면 방위각처럼 0/360이 같은 값으로 순환, false면 EL/ZOOM처럼 범위 고정)
  - MinValue/MaxValue (bWrap360=false일 때만 사용, 예: EL -20~20, ZOOM 0.5~10.0)
  - MajorTickIntervalDeg (예: 방위각 30, EL 10)
  - bShowLabels (라벨 숫자 표시 여부 — 4분할캠 리본은 false, UAV영상피드/RCWS는 true)
  - LabelFormatter (숫자를 그대로 보여줄지 "N"/"E"/"S"/"W" 같은 방위 문자로 바꿀지)
  - VisibleRangeDeg (중심 기준 좌우/상하로 보여줄 범위, 화면 폭에 맞춰 조절)

OnPaint:
  - 중심선 고정, 눈금 자체가 CurrentValue에 따라 스크롤되어 지나가는 방식
    (배틀그라운드류 나침반 리본과 동일한 개념)
  - Major tick은 긴 선+숫자, Minor tick은 짧은 선만
  - 중심 포인터는 별도 고정 UI 요소(WBP에서 T_triangle 이미지를 중앙 고정 배치)로 처리 —
    OnPaint 안에 얹어도 되지만, 아이콘 텍스처를 그대로 쓰려면 WBP 오버레이가 더 간단함
```

**적용처 4곳:**
1. 트럭/UGV 4분할캠 리본 (숫자 없음, EWSN + 눈금만) — `bShowLabels=false`
2. UAV 영상피드 상단 리본 (30도 간격 숫자 + 눈금) — `bShowLabels=true`, `MajorTickIntervalDeg=30`
3. RCWS 조준화면 상단 azimuth 리본 (가로, 방위각) — `bWrap360=true`
4. RCWS 조준화면 좌/우 EL·ZOOM 세로 리본 (세로, 고정 범위) — `bWrap360=false`,
   `Orientation=Vertical`

같은 클래스를 4번 다른 파라미터로 배치하면 되므로 신규 C++ 클래스는 이거 하나로 충분함.

**갱신(2026-07-10)**: 현재값을 보여주던 반투명 하이라이트 박스+텍스트는 제거함(사용자가 별도
TextBlock으로 직접 배치하길 원함) — `SetCurrentValue()`만 남고 `SetCurrentValueLabel()`은
삭제됨. 대신 눈금 숫자/EWSN 폰트(`TickLabelFont`, `FSlateFontInfo` — 폰트 애셋/크기/굵기 등
Details 패널에서 그대로 지정 가능)와 큰눈금/작은눈금 두께(`MajorTickThickness`/
`MinorTickThickness`)를 각각 커스텀 가능하도록 프로퍼티 추가함. 이 프로젝트의 다른 커스텀 페인트
위젯(`LineGraphWidget`/`CompassWidget`/`VehicleMarkerWidget`/`RadialAreaWidget` 등)은 전부 자체
텍스트를 안 그리고 별도 `TextBlock`에 의존하므로, 그쪽 폰트/크기는 원래부터 Details 패널에서
자유롭게 커스텀 가능함(C++ 손댈 필요 없음) — `ScrollingRulerWidget`만 유일하게 직접 텍스트를
그려서 이 프로퍼티가 필요했음.

**갱신(2026-07-10) — 리본이 끊겨 보이는 문제**: `ScrollingRulerWidget` 자체엔 FPS 제한이 없음
(Slate 커스텀 페인트는 항상 매 프레임 다시 그려짐, 그건 원래 공짜). 끊겨 보인 진짜 원인은
`Monitor1Widget`/`Monitor2Widget`이 텍스트/미니맵 갱신 비용을 아끼려고 값 자체를
`RefreshIntervalSeconds`(0.2초/0.1초)마다만 업데이트하고 있었던 것 — 리본처럼 매끄럽게
스크롤돼야 하는 값이 초당 5~10번만 갱신되니 계단처럼 끊겨 보임. `MajorTickInterval`은 눈금
간격(도 단위)일 뿐 타이밍이랑 무관.

고침: 리본의 `SetCurrentValue()` 호출만 `RefreshRibbonValues()`로 분리해서 **매 프레임**(스로틀
없이) 실행하도록 변경 — float 대입 + 컴포넌트 회전값 읽기 정도라 비용이 사실상 0에 가까움.
텍스트/미니맵 마커처럼 `FString::Printf`/`FText::FromString`/Canvas 위치 갱신이 들어가는 무거운
부분은 그대로 기존 주기로 스로틀 유지 — 그래서 전체 리프레시 주기를 없애는 것보다 훨씬 저렴하고,
성능 영향은 사실상 없음.

부수적으로 발견한 버그도 같이 고침: 트럭 4분할캠 미니 리본들이 실제 세계 방위각이 아니라
미니맵 화면 기준 각도(`WorldYawToMinimapScreenAngle`, 미니맵 마커 회전용 변환)를 쓰고 있었음 —
카메라 리본은 진짜 나침반처럼 보여야 하므로 순수 월드 방위각(`NormalizeAzimuth360`)으로 수정.

### 2.2 나침반(원형, UAV 상태정보 "방향" 카드)은 리본과 다름 — PNG 텍스처 사용

이건 리본이 아니라 기존 `CompassWidget.h`의 손그림 원형 나침반과 같은 자리인데, 디자인팀이
`T_compass`(회전 레이어)/`T_compass_outer`(고정 테두리) 텍스처를 이미 줬으므로 이 자리는
**손그림 대신 실제 텍스처 2장 오버레이**로 교체 추천:
- `T_compass_outer` UImage 고정
- `T_compass` UImage를 `RenderTransform`의 Angle에 헤딩값 바인딩해서 회전
- `ui.md` 56번째 줄에 명시된 대로 **텍스처 기본 방향이 NE(45도)** 이므로 `WidgetAngle =
  HeadingDegrees - 45.f` 로 오프셋 보정 필요 (부호는 실제로 돌려보면서 확인 — 시계/반시계
  방향이 반대일 수 있음)
- 기존 `SCompass`/`UCompassWidget`는 그대로 두되(다른 자리에서 재사용될 수도 있으니 삭제하지
  않음), 이 자리에는 안 씀

## 3. 그래프 아래 그라데이션 음영 (`ui.md` 57번째 줄, 토론 필요 항목)

`ULineGraphWidget`(`SLineGraph::OnPaint`)이 지금은 `MakeLines`로 선만 그림. 그라데이션 채우기는
텍스처 없이 코드로 가능 — `FSlateDrawElement::MakeCustomVerts`로 선 아래 영역을 삼각형 스트립으로
채우면서 위쪽 정점은 알파 높게, 아래쪽(그래프 바닥) 정점은 알파 0으로 주면 세로 그라데이션이
됨(버텍스 컬러 보간은 Slate가 자동으로 해줌). PNG/머티리얼 불필요, `SLineGraph::OnPaint`에 채우기
패스 하나만 추가하면 됨.

## 4. 미니맵 — 이번 작업에서 가장 큰 신규 구현 영역

`AMinimapCaptureActor`(씬 캡처 + `WorldToMinimapUV`)는 이미 있지만 그 위에 그리는 마커/부채꼴/
경로선은 전혀 없음. `minimap.md` 기준으로 필요한 신규 요소:

| 요소 | 구현 방식 |
|---|---|
| UGV/UAV/지휘소 위치+방향 아이콘 | `UImage` + `WorldToMinimapUV`로 Canvas 슬롯 위치 갱신, `RenderTransform` Angle로 차량 방향 회전 (`T_Vector`나 별도 벡터/탱크 아이콘 필요 — 2절 표에서 확인 필요 항목) |
| UGV/트럭 RCWS 시야 부채꼴 | 신규 `SFieldOfViewCone`(Slate 커스텀 페인트, `MakeLines`나 `MakeCustomVerts`로 반투명 부채꼴 폴리곤) — RCWS `AzimuthDegrees`(0.5절 보정 후) + 카메라 FOV를 받아서 그림 |
| UGV 이동 예정 경로선 | 신규 `SPolyline`(포인트 배열 받아 `MakeLines`) — UGV의 NavMesh 경로 포인트(`UGVAIController`가 이미 갖고 있을 경로)를 UV로 변환해서 연결 |
| UAV WP1→WP2 점선 | 위 `SPolyline`에 점선 옵션 추가, 시작/끝에 `T_blue_marker`/`T_green_marker` 고정 배치 |
| 적군 예상 위치 반투명 빨간 원 | 새 원 오버레이(간단히 `UImage`에 원형 브러시 틴트, 또는 `SRadialGauge`처럼 커스텀 페인트) — 다만 **이 원이 언제/어디에 나타나는지가 아직 미구현**(memo.md 시나리오 #4-1: "시작 신호(적 위치 좌표) 수신" 트리거가 아직 없음) → 이 부분은 UI보다 시나리오 스크립트 문제라 별도 작업으로 분리 필요 |
| 정확한 빨간 마커(탐지 후) | 이미 있는 `TargetDetectionComponent::DetectedTargets` 중 `Faction==Enemy`인 대상의 월드 좌표를 `WorldToMinimapUV`로 변환해서 표시 — 데이터는 이미 있음, 미니맵 마커 위젯만 새로 필요 |
| 축척 표시 | `MinimapCaptureActor::CaptureWidth`와 Image 위젯의 실제 픽셀 크기로 "100m" 같은 스케일바 길이 계산 — 새 함수 하나면 충분 |
| 확대/축소 | 0.7절에서 스킵 확정 |

이 전체를 묶는 신규 `UMinimapOverlayWidget`(마커/부채꼴/경로선을 매 틱 갱신) 하나를 만들고,
그 안에 개별 마커는 재사용 가능한 작은 위젯들로 쪼개는 걸 추천.

## 5. Monitor1/Monitor2 위젯 클래스 구조

`WBP_kadex`(`/Game/widget/WBP_kadex`)가 이미 `MissionDashboardWidget`을 부모로 새로 만들어져
있는 걸 확인함(현재 위젯 트리는 비어있음 — 작업 시작 전 상태로 보임). 그런데 0.1절에서 정리한
대로 모니터2가 완전히 다른 스코프(RCWS 뷰어 단독)로 재설계됐기 때문에, 기존
`MissionDashboardWidget`(모든 필드를 한 클래스에 몰아넣은 테스트용 대시보드) 하나를 계속 우려
쓰기보다 **역할별로 분리**하는 걸 추천:

- `UMonitor1Widget`(신규) — 헤더 + 메인뷰(트럭 RCWS로 임시 대체) + 트럭 4분할캠 + 미니맵 +
  UAV 상태정보 + UAV 영상피드. `MissionDashboardWidget`의 관련 필드 대부분을 그대로 옮겨오면 됨.
- `UMonitor2Widget`(신규) — RCWS 조준화면 + (3D 뷰어는 스킵) + RCWS 상태정보. **어떤 RCWS를
  보여줄지는 `Atitan_examplePlayerController::CameraControlTarget`을 읽어서 결정**(0.1절의 (b)
  해석) — Truck/UGV 어느 쪽이 활성인지에 따라 바인딩 대상만 바꿔치기.
- 기존 `MissionDashboardWidget`/`WBP_test`는 회귀 테스트용으로 남겨둠(삭제 불필요).
- `Atitan_examplePlayerController::LeftDashboardWidgetClass`/`RightDashboardWidgetClass`에
  `WBP_kadex`(또는 새로 만들 `WBP_Monitor1`/`WBP_Monitor2`)를 배정.

## 6. 신규/수정 파일 목록 (구현 시)

- `Source/titan_example/UI/ScrollingRulerWidget.h/.cpp` (신규, 2절)
- `Source/titan_example/UI/MinimapOverlayWidget.h/.cpp` + 부채꼴/폴리라인용 보조 Slate 위젯 (신규, 4절)
- `Source/titan_example/UI/Monitor1Widget.h/.cpp`, `Monitor2Widget.h/.cpp` (신규, 5절)
- `Source/titan_example/UI/LineGraphWidget.cpp` — 그라데이션 채우기 추가 (3절)
- `Source/titan_example/UI/CompassWidget.*` — 변경 없음(다른 용도로 남겨둠), UAV 상태정보의
  원형 나침반은 텍스처 오버레이로 별도 구현 (2.2절)
- `Source/titan_example/Vehicles/RCWSComponent.h/.cpp` — Zoom, RNG 거리, 방위각 정규화/절대화
  (0.3~0.5절)
- `Source/titan_example/Vehicles/UAVPawn.h/.cpp` — Zoom, 위경도 변환(더미 GPS)
- `Source/titan_example/UGVAIController.*` (또는 UGVPawn) — 미니맵 경로선용 현재 경로 포인트
  목록을 외부에서 읽을 수 있는 getter 필요할 수 있음(4절)

## 8. WBP 위젯 이름/설정 레퍼런스 (구현 완료 기준, 실제로 이 이름들로 배치하면 됨)

4~6절은 설계 당시 메모라 세부 클래스명이 최종본과 다른 곳이 있음 — **여기 8절이 최신/정확한
기준**. `BindWidgetOptional`이라 이름만 정확히 맞추면 그래프 작업 없이 값이 채워짐. 이름을 안
맞추면 그냥 조용히 스킵되니(에러 안 남) 값이 안 뜨면 이름부터 다시 확인.

**갱신(2026-07-10) — WBP 2개 → 1개로 되돌림**: 처음엔 모니터1/모니터2를 `WBP_kadex`/
`WBP_kadex1` 두 개의 WBP로 나누고 `SetAnchorsInViewport`로 화면을 좌/우 절반씩 분할하는
방식으로 갔었는데, 창 크기에 따라 분할이 이상하게 어긋나는 문제가 있었음 — 그래서 원래
계획(3840 폭 단일 캔버스)으로 되돌려서 **`WBP_kadex` 하나만 사용**, `UMonitor2Widget` 클래스는
`UMonitor1Widget`에 전부 합치고 삭제함. `Atitan_examplePlayerController`도
`LeftDashboardWidgetClass`(=WBP_kadex) 하나만 `AddToViewport()`로 풀스크린 추가하고,
`RightDashboardWidgetClass`는 다시 필요해질 경우를 대비해 남겨뒀지만 지금은 비워둠
(`WBP_kadex1`은 부모를 평범한 `UserWidget`으로 되돌려서 깨지지 않게만 해둠 — 필요 없으면 직접
삭제해도 됨). 아래 필드 목록/설정값 자체는 안 바뀜, `UMonitor2Widget`이었던 부분도 전부
`UMonitor1Widget`에 그대로 있으니 같은 WBP_kadex 캔버스 안에 오른쪽 절반쯤에 배치하면 됨.

### `UMonitor1Widget` (WBP_kadex, 모니터1+모니터2 전부 포함)

**헤더**

| 위젯 이름 | 타입 | 설정/비고 |
|---|---|---|
| `HeaderDateText` | TextBlock | 자동 (YYYY-MM-DD) |
| `HeaderTimeText` | TextBlock | 자동 (HH:MM:SS) |
| `ExitButton` | Button | 클릭 시 `QuitGame` 자동 연결됨 |

설정(톱니바퀴) 버튼은 바인딩 대상 아님 — 아이콘만 배치.

**메인 뷰 / 트럭 4분할캠**

| 위젯 이름 | 타입 | 설정/비고 |
|---|---|---|
| `MainViewImage` | Image | 트럭 RCWS 화면(임시 대체) |
| `MainViewDetectionOverlay` | DetectionOverlayWidget | `MainViewImage`와 정확히 같은 위치/크기로 겹쳐서 배치(트럭 탐지 바운딩 박스). **`CornerRadius`**(2026-07-11 추가)를 `MainViewImage`의 라운드 반경과 동일하게 맞출 것 |
| `TruckFrontImage`/`TruckRearImage`/`TruckLeftImage`/`TruckRightImage` | Image | |
| `TruckFrontRibbon`/`TruckRearRibbon`/`TruckLeftRibbon`/`TruckRightRibbon` | **CompactHeadingRibbonWidget**(신규, `ScrollingRulerWidget` 아님) | 텍스트/눈금이 한 줄에 같이 있고, 가장 가까운 8방위 문자만 `HighlightColor`(기본 흰색), 나머지는 `DimColor`(기본 회색 반투명) — 기본값 그대로 써도 됨 |

**미니맵** — 아래 6개는 **전부 Canvas Panel의 직계 자식**이어야 함(위치를 `CanvasPanelSlot::SetPosition`으로 매 틱 옮김).

| 위젯 이름 | 타입 | 설정/비고 |
|---|---|---|
| `MinimapImage` | Image | |
| `MinimapTruckMarker` | VehicleMarkerWidget | `MarkerColor` 자유 지정(예: 주황) |
| `MinimapUGVMarker` | VehicleMarkerWidget | `MarkerColor` 자유 지정(예: 파랑). **버그 수정(2026-07-11)**: UGV 메시가 -X를 정면으로 두고 제작되어 있어서(`UGVMovementComponent.cpp`가 같은 이유로 `GetForwardVector()`를 4곳에서 negate함) `GetActorRotation().Yaw`를 그대로 쓰면 마커가 반대 방향을 향했음 — `(-GetActorForwardVector()).Rotation().Yaw`로 수정 |
| `MinimapUAVMarker` | VehicleMarkerWidget | `MarkerColor` 자유 지정(예: 초록) |
| `MinimapTruckFOVCone` | RadialAreaWidget | `FillColor`=반투명. **`SpanDegrees` 실시간 연동(2026-07-11)**: 이전엔 WBP에 넣어둔 고정값(트럭 RCWS `CameraFOV` 기본 40)만 썼는데, 줌을 넣으면 실제 FOV가 `CameraFOV/ZoomLevel`로 좁아지므로 매 갱신마다 `URCWSComponent::GetCurrentFOVDegrees()`(신규, `SightCamera->FOVAngle`을 그대로 읽음)로 갱신하도록 변경 — WBP에서 더 이상 `SpanDegrees`를 수동 설정할 필요 없음(코드가 매번 덮어씀) |
| `MinimapUGVFOVCone` | RadialAreaWidget | `FillColor`=반투명. `SpanDegrees`도 `MinimapTruckFOVCone`과 동일하게 `GetCurrentFOVDegrees()`로 실시간 연동(2026-07-11) |
| `MinimapUAVFOVCone` | RadialAreaWidget | **추가(2026-07-11)**: `FillColor`=반투명 — 방향은 트럭/UGV처럼 RCWS 방위각이 아니라 짐벌 카메라가 실제로 보는 방향(`AUAVPawn::GetGimbalWorldHeadingDegrees`, `UAVCameraHeadingText`/`UAVCameraRibbon`과 같은 소스). `SpanDegrees`도 신규 `AUAVPawn::GetCurrentFOVDegrees()`(`GimbalCamera->FOVAngle`)로 실시간 연동, 트럭/UGV처럼 WBP 수동 설정 불필요 |
| `MinimapEnemyPredictedArea` | RadialAreaWidget | `SpanDegrees=360`, `FillColor`=반투명 빨강 — 태그 없으면(적 예상 위치 없음) 자동으로 `Collapsed` |
| `MinimapUGVPath` | PolylineWidget | `bDashed=false` |
| `MinimapUAVRoute` | PolylineWidget | `bDashed=true` |

WP1/WP2 마커(`T_blue_marker`/`T_green_marker`)는 자동 배치 안 됨 — `GetUAVHomeUV()`/
`GetUAVTargetUV()`(둘 다 `Vector2D` 반환) 결과에 `MinimapImage` 크기를 곱해서 Canvas 위치를
직접 세팅해야 함(Tick 이벤트에서).

**UAV 상태정보**

| 위젯 이름 | 타입 | 설정/비고 |
|---|---|---|
| `UAVAltitudeText` | TextBlock | |
| `UAVAltitudeGraph` | LineGraphWidget | |
| `UAVSpeedText` | TextBlock | |
| `UAVSpeedGraph` | LineGraphWidget | |
| `UAVHeadingText` | TextBlock | |
| `UAVCompassImage` | Image (`T_compass`, 회전 바늘 레이어) | **갱신(2026-07-10)**: 이름만 맞추면 자동 연동됨(Property Binding 불필요) — 매 프레임 C++에서 `SetRenderTransformAngle()`을 직접 호출해서 회전시킴, `T_compass_outer`(고정 테두리)는 바인딩 대상 아니라 WBP에 그냥 고정 배치 |
| `UAVGpsMainText`/`UAVGpsSubText` | TextBlock | |
| `UAVLinkMainText`/`UAVLinkSubText` | TextBlock | |
| `UAVMissionMainText`/`UAVMissionWaypointText` | TextBlock | |
| `UAVSignalText` | TextBlock | |
| `UAVSignalBar1`/`UAVSignalBar2`/`UAVSignalBar3`/`UAVSignalBar4` | Image (`T_Rectangle`/`_1`/`_2`/`_3`) | 이름만 맞추면 자동 연동됨. **정정 3단계(2026-07-10)**: ① `SetColorAndOpacity` 곱셈 틴트 → `T_Rectangle*` PNG 자체에 파란 그라데이션이 박혀있어서(RGB 곱셈으로) 순수 회색에 도달 못함. ② 알파-마스크+단색 채우기 머티리얼 → 이번엔 그라데이션 자체가 통째로 사라짐. ③ Desaturation으로 명도 보존 + `TintColor` 곱셈 → 꺼짐 상태에서 이미 어두운 그라데이션에 어두운 틴트(`#313131`)를 또 곱해서 대비가 다 눌려버려 "불투명 회색 -> 불투명 검은색"처럼 보임. **최종 원인 확인**: `T_Rectangle` 텍스처를 실제로 픽셀 단위로 샘플링해봄(CaptureAssetImage로 렌더 후 PIL로 세로 컬럼 RGBA 추출) — **알파는 전체가 255로 고정**이고, "페이드"처럼 보이는 건 100% RGB 색상 그라데이션(위쪽 `#17B9FF` 밝은 파랑 → 아래쪽 `#081429`에 가까운 거의 검정)이었음. 즉 원본 하늘색 막대는 애초에 완전 불투명이고, 어두운 UI 배경에 묻혀서 "투명"처럼 보이는 것뿐. **최종 구현**: 켜진 바는 브러시를 아예 건드리지 않음(WBP에 배치된 원본 그대로, 회귀 위험 0). 꺼진 바만 `M_IconFlatTint` 머티리얼로 교체 — Emissive는 명도 섞지 않은 완전 플랫 `TintColor`(`#313131`, 대비 눌림 문제 해결), Opacity는 `TextureAlpha × Desaturation(원본, Fraction=1)`으로 원본이 어두워지던 자리를 실제 투명도로 대체(`불투명 회색 -> 투명 회색`, 하늘색 막대가 읽히는 방식과 동일하게 재현). 바마다 다이나믹 머티리얼 인스턴스(MID) 하나씩 자동 생성, WBP에서 추가로 할 일 없음. 또한 `UAVSignalText`(dBm 숫자)와 막대 켜진 개수가 서로 다른 독립 사인파로 따로 움직이던 버그도 수정 — 이제 `LinkQualityPercent`는 `SignalDbm`에서 매 틱 파생됨(`UStatusHUDWidget::UpdateSignalBars`와 같은 -100~-50dBm → 0~100% 매핑, `SignalDbm` ±15 → -75~-45dBm → 50~100%), 숫자와 막대가 항상 일치하며 천천히(0.15 rad/s) 오간다 |
| `UAVBatteryText` | TextBlock | |
| `UAVFlightTimeText` | TextBlock | |

**정정(2026-07-10)**: 원형 나침반(`T_compass`/`T_compass_outer`)은 원래 Property Binding
(`Render Transform > Angle`을 `GetUAVCompassImageAngle()`에 연결)으로 안내했었으나, 이 방법
자체가 UMG에서 작동하지 않음이 확인됨 — `Render Transform`은 `FWidgetTransform` 구조체
프로퍼티라서, 그 **서브필드**(`Angle` 등)는 Property Binding을 지원하지 않고 키프레임
(Sequencer/Widget Animation)만 지원함(엔진 소스 `WidgetTransform.h` 확인 완료). `Angle` 필드
옆에 동그라미가 아니라 마름모(키프레임 추가) 아이콘만 보이는 게 정상이고, Details 패널에
바인딩 동그라미 아이콘 자체가 아예 없는 것도 정상 — 코드 버그가 아니라 UMG 구조적 제약.

**최종 해결**: Property Binding을 아예 쓰지 않는 쪽으로 변경 — 다른 위젯들과 동일하게
**이름만 맞추면 자동 연동**되도록 함. `UWidget`이 기본 제공하는 `SetRenderTransformAngle(float)`
함수를 C++에서 직접 호출(`RefreshSmoothValues()`에서 매 프레임)해서 `UAVCompassImage`를
회전시킴 — WBP에서 할 일은 이미지 이름을 `UAVCompassImage`로 맞추는 것뿐, Details 패널
작업(바인딩이든 뭐든) 전혀 불필요.

**UAV 영상피드**

| 위젯 이름 | 타입 | 설정/비고 |
|---|---|---|
| `UAVCameraImage` | Image | |
| `UAVCameraDetectionOverlay` | DetectionOverlayWidget | `UAVCameraImage`와 정확히 같은 위치/크기로 겹쳐서 배치(UAV 탐지 바운딩 박스). `CornerRadius`를 `UAVCameraImage`의 라운드 반경과 동일하게 맞출 것 |
| `UAVCameraRibbon` | ScrollingRulerWidget | `Orientation=Horizontal`, `bWrapMode=true`, `bShowNumericLabels=true`, `bShowCardinalLabels=true`, `MajorTickInterval=30`, `bShowMidTicks=true`, `MinorTicksPerMajor=5`(3단계 눈금: 3-1-1-2-1-1 패턴) |
| `UAVCameraHeadingText` | TextBlock | 카메라(짐벌)가 실제로 보는 방향 — `UAVHeadingText`(드론 진행방향)와 다른 값, `AUAVPawn::GetGimbalWorldHeadingDegrees()` 기반 |
| `UAVLatitudeText`/`UAVLongitudeText` | TextBlock | |
| `UAVCameraAltitudeText`/`UAVCameraSpeedText` | TextBlock | **추가(2026-07-10)**: UAV 상태정보 패널의 `UAVAltitudeText`/`UAVSpeedText`와 이름이 겹치면 안 돼서 별도 이름. 고도는 상태정보 패널과 표기 형식이 다름 — `"153 m"`처럼 단위 포함(`%.0f m`), 속도는 상태정보 패널과 동일한 형식 그대로(`%.1f`) |
| `UAVCameraSignalBar1`/`UAVCameraSignalBar2`/`UAVCameraSignalBar3`/`UAVCameraSignalBar4` | Border | **추가(2026-07-10)**: UAV 상태정보 패널의 `UAVSignalBar1~4`(Image, 그라데이션 아이콘)와 이름이 겹치면 안 돼서 별도 이름 — 이쪽은 단색 Border라서 `M_IconFlatTint` 머티리얼 없이 `SetBrushColor`로 하늘색(`#17B9FF`)/회색(`#313131`) 토글만 함(`UStatusHUDWidget::UpdateSignalBars`와 동일 패턴), 같은 `LinkQualityPercent` 기준으로 `UAVSignalBar1~4`와 항상 같이 켜지고 꺼짐 |

**갱신(2026-07-12)**: 줌 버튼(1.0x/2.5x) 클릭 처리 자체(`UAVRef->SetZoomLevel(1.0)`/
`SetZoomLevel(2.5)` 호출)는 여전히 각 Button의 WBP `OnClicked` 그래프에서 함(`UAVRef`가
`BlueprintReadOnly`라 그래프에서 바로 접근 가능) — 다만 어느 쪽이 선택됐는지 텍스트 색을
바꾸는 부분은 더 이상 WBP에서 안 해도 됨. `UAVZoom1xText`/`UAVZoom2_5xText`(TextBlock)
이름만 맞춰서 각 배율 Border 안의 텍스트에 배치하면 `RefreshUAVZoomButtons()`가
`UAVRef->GetZoomLevel()`과 비교해서 선택된 쪽은 하늘색(`#17B9FF`), 나머지는 흰색으로 자동
반영(다른 신호세기 바들과 동일한 "recolor, not hide" 패턴).

**스케일바**: "100 m" 라벨 텍스트는 그냥 고정 텍스트로 적어두고, 그 옆 막대 그래픽(Border/
SizeBox)의 `Width`/`Width Override`를 Property Binding으로 `GetScaleBar100mPixelWidth()`에
연결하면 축척에 맞는 픽셀 길이가 나옴.

**RCWS 뷰어 (모니터2 — 같은 `WBP_kadex` 캔버스 안, 오른쪽 절반쯤에 배치)**

트럭/UGV 중 어느 쪽을 보여줄지는 `Atitan_examplePlayerController::GetCameraControlTarget()`을
기준으로 자동 결정(기본값 UGV) — WBP에서 신경 쓸 필요 없음.

| 위젯 이름 | 타입 | 설정/비고 |
|---|---|---|
| `RCWSViewImage` | Image | |
| `RCWSDetectionOverlay` | DetectionOverlayWidget | `RCWSViewImage`와 정확히 같은 위치/크기로 겹쳐서 배치(현재 활성 RCWS의 탐지 바운딩 박스). `CornerRadius`를 `RCWSViewImage`의 라운드 반경과 동일하게 맞출 것 |
| `AzimuthRibbon` | ScrollingRulerWidget | `Orientation=Horizontal`, `bWrapMode=true`, `MajorTickInterval=30`, `bShowNumericLabels=true`, `bShowCardinalLabels=true`, `bShowMidTicks=true`, `MinorTicksPerMajor=5` |
| `AzimuthRibbonText` | TextBlock | **추가(2026-07-11)**: `AzimuthRibbon`은 자체 라벨을 안 그리므로(다른 리본들과 동일 이유) 이 텍스트가 그 역할 — 형식 `330`(정수, 소수점/단위 없음, 아래 RCWS 상태정보의 `AzimuthText`(`330.0°` 형식)와는 다름, 위치만 다른 게 아니라 형식도 다름) |
| `ElevationRibbon` | ScrollingRulerWidget | `Orientation=Vertical`, `bWrapMode=false`, `MinValue=-20`, `MaxValue=20`, **`VisibleRange=40`**(2026-07-11 갱신 — 0일 때 -20~20이 보이도록), `bInvertAxis=false`(−20 위/+20 아래), `MajorTickInterval=10`, `MinorTicksPerMajor=2`, `bShowSpine=true`, `bMirrored=false` |
| `ElevationText` | TextBlock | 형식 `+04.6°` 자동 |
| `ElevationRibbonText` | TextBlock | **추가(2026-07-11)**: `ElevationText`와 완전히 동일한 형식(`+04.6°`) — 위치만 다른 두 번째 표시용 |
| `ZoomRibbon` | ScrollingRulerWidget | `Orientation=Vertical`, `bWrapMode=false`, **`ValueBreakpoints=[0.5, 1.0, 2.5, 5.0, 10.0]`**(2026-07-11 갱신 — MinValue/MaxValue/MajorTickInterval은 이 모드에서 무시됨), **`VisibleRange=4`**(인덱스 단위 — 기본 줌 2.5(=인덱스 2) 기준 전체 5개 브레이크포인트가 다 보임), `bInvertAxis=true`(10.0x 위/0.5x 아래), `MinorTicksPerMajor=1`(1.0~2.5 사이에 눈금 하나 추가), `bShowSpine=true`, `bMirrored=true`(EL과 좌우반전), **`LabelDecimalPlaces=1`, `LabelSuffix="x"`**(2026-07-11 추가 — 리본 자체가 그리는 눈금 라벨이 "2.5x"처럼 나오도록, 다른 리본들은 기본값 0/빈 문자열 그대로 정수 라벨) |
| `ZoomText` | TextBlock | 형식 `2.5x` 자동 |
| `RangeText` | TextBlock | 형식 `RNG 1,253 m` 자동 |
| `ModeText` | TextBlock | "원격 제어"/"자동 제어" (현재는 항상 원격) |
| `TargetTrackingText` | TextBlock | Detection 시스템 연동 — 탐지된 대상 있으면 "추적 중" |
| `AzimuthText` | TextBlock | 형식 `330.2°` |
| `SystemConnectionText` | TextBlock | 더미 "정상" |
| `PowerStatusText` | TextBlock | 형식 `정상 27.6V`, 전압만 느리게 변동 |
| `AmmoText` | TextBlock | **갱신(2026-07-11)**: 형식 `475`(최댓값 표시 없이 현재 탄약만) — 트럭/UGV 둘 다 `AmmoMax=600`(UGV가 실수로 1200이었던 것 수정, `UGVPawn.cpp`) |
| `WarningText` | TextBlock | 더미 "없음" |
| `StabilizationText` | TextBlock | 더미 "정상" |
| `SystemTemperatureText` | TextBlock | 형식 `48°C`, 더미 고정값 |
| `RCWSPreviewImage` | Image | **추가(2026-07-11)**: ui.md "2. 3D 모델 시각화 - RCWS 3D 모델 시각화 (고정)" 구현 — `RCWSPreviewActor`(신규 액터, 아래 항목 참고)가 자체적으로 갱신하는 `PreviewRenderTarget`을 `BindCameraImages()`에서 한 번만 바인딩(`RCWSViewImage`처럼 매 갱신마다 다시 바인딩할 필요 없음 — 항상 같은 RenderTarget 오브젝트). 크로마키 머티리얼(`M_ChromaKey`) 기반 MID로 적용됨 |
| `RCWSPreviewReflectionImage` | Image | **추가(2026-07-12)**: 디자인 시안의 "모델 아래 연하게 반사" 효과용 — `RCWSPreviewImage`와 완전히 같은 MID(크로마키 적용된 동일 이미지)를 공유해서 보여줌, 이름만 다른 별도 위젯(같은 이름은 WBP에 하나만 배치 가능해서 분리). **WBP 작업**: `RCWSPreviewImage` 바로 아래에 겹쳐 배치, `Render Transform > Scale`의 Y를 `-1`로(상하 반전), `Render Opacity`를 낮게(0.15~0.3 권장) — 둘 다 정적 값이라 C++ 코드 없이 WBP에서 직접 설정 |

### AzimuthRibbon이 UGV 조향만으로는 안 움직이던 버그(2026-07-11)

**RCWS 마운트/카메라 회전 구조 확인**: `AddPanTiltInput`(0.3절 기존 구현)은 이미 마운트 전체를
회전시키고 카메라는 그 자식으로 따라 도는 구조임(포탑 placeholder 큐브 하나뿐이라 팬/틸트 둘 다
마운트에 적용, `RCWSComponent.cpp` 주석 참고) — 나중에 실제 포탑 메시(베이스+틸트되는 배럴)로
교체해도 "마운트가 돌면 자식인 카메라도 같이 돈다"는 지금 구조 그대로 맞음, 추가 변경 불필요.

**진짜 원인은 이름/바인딩 문제가 아니라 갱신 타이밍 버그**: `CurrentData.AzimuthDegrees`
(`SightCamera->GetComponentRotation().Yaw` 기반 절대 방위)가 `AddPanTiltInput` 안에서만
계산되고 있었음 — 즉 RCWS 조이스틱으로 팬/틸트를 직접 넣을 때만 갱신됨. 마운트는 UGV/트럭
차체에 상대 회전으로 붙어있어서, 차체가 조향으로 회전하면 카메라의 **월드** 방위는 실제로
계속 바뀌는데(부착 체인 때문에 자동으로), `AddPanTiltInput` 호출이 없으니
`CurrentData.AzimuthDegrees`는 마지막 조이스틱 입력 시점 값에 멈춰있었음 — `AzimuthRibbon`이
그 멈춘 값을 그대로 보여주니 "가만히 있는 것처럼" 보인 것. 이름 바인딩은 처음부터 문제
없었음.

**수정**: 방위각 계산을 `RefreshAzimuth()`로 분리해서 `TickComponent`에서 매 틱 호출하도록
변경(`AddPanTiltInput`도 계속 즉시 반영되도록 같은 헬퍼 호출) — 이제 조이스틱 입력 여부와
무관하게 차체 회전만으로도 `AzimuthDegrees`가 항상 최신 월드 방위를 반영함.

**나머지 RCWS 위젯 전수 확인 결과(같은 날)**: `ElevationRibbon`/`ZoomRibbon`/`RangeText`/
`AzimuthText`/`TargetTrackingText`/`PowerStatusText`는 전부 정상(매 틱 또는 매 갱신마다
실시간 반영). `ModeText`/`SystemConnectionText`/`AmmoText`/`WarningText`/`StabilizationText`/
`SystemTemperatureText`는 버그가 아니라 애초에 5절에 문서화된 고정 더미값(실시간 로직 계획
없음).

**Elevation도 월드 기준으로 변경(같은 날, 사용자 확정)**: `ElevationDegrees`가 기존엔 마운트의
**차체 기준 상대 피치**였음 — Azimuth를 월드 절대 방위로 고친 것과 기준이 달랐고,
`StabilizationStatus`가 항상 "정상"(자이로 안정화 조준경을 암시)인 것과도 안 맞았음. 사용자가
월드 기준으로 통일하기로 확정 — `RefreshAzimuth()`를 `RefreshAzimuthElevation()`으로 확장해서
`SightCamera->GetComponentRotation().Pitch`(부착 체인 전체 반영, 차체가 경사로에서 기울어지면
같이 반영됨)를 매 틱 계산하도록 변경. `MinElevationDegrees`/`MaxElevationDegrees` 클램프는
그대로 마운트의 **차체 기준 상대** 기계적 틸트 한계로 유지(실제 포탑의 물리적 가동 범위는 차체
기준이 맞으므로) — 표시값(월드)과 클램프(상대)가 서로 다른 개념이라는 점만 유의.

### DetectionOverlayWidget: 모서리 둥글기(2026-07-11)

**질문**: 카메라 이미지가 기본적으로 둥근 모서리로 표시되는데, 그 위에 겹쳐 그리는 탐지
바운딩 박스(초록/빨강 사각형)의 뾰족한 모서리가 그 둥근 프레임 밖으로 튀어나오지 않게 할 수
있는지, 그리고 언리얼 기본 위젯만으로(예: Border를 라운드 처리하고 그 안에 overlay를 넣는
방식) 가능한지.

**답**: Border/Widget 감싸기만으로는 안 됨 — 엔진 소스로 확인함(`SlateCore/Public/Layout/
Clipping.h`의 `FSlateClippingZone`). Slate의 실제 클리핑 프리미티브는 4개 모서리 점으로 이뤄진
사각형(axis-aligned 또는 임의의 quad)만 지원하고, **둥근 모서리 클리핑 자체가 개념적으로
존재하지 않음**. 카메라 이미지가 둥글게 보이는 건 `Image`/`Border`의 `Brush.DrawAs=RoundedBox`
설정이 그 위젯 자신의 텍스처를 둥글게 "그리는" 기법일 뿐, 자식/형제 위젯의 렌더링을 그 둥근
모양으로 "잘라내는" 기능이 아님 — 그래서 `DetectionOverlayWidget`을 라운드 처리된 Border 안에
넣어도 사각형 박스 외곽선은 그대로 뾰족하게 그려짐(클리핑은 여전히 사각형 기준).

**구현**: `DetectionOverlayWidget`에 `CornerRadius`(float, 기본 0) 프로퍼티 신규 추가 — 카메라
Image의 둥근 모서리 반경과 같은 값으로 맞추면 됨. Slate 레벨 클리핑이 안 되므로, 대신
**지오메트리 레벨에서 직접 처리**: 박스 외곽선을 각 변마다 12구간으로 잘게 나눈 뒤
(`BuildRoundedBoxOutline`), 위젯 자신의 4개 모서리에 대해 정의된 둥근 경계 밖으로 벗어나는
점이 있으면 그 경계(원호) 위로 끌어당김(`ClampToRoundedRect`) — 모서리에서 멀리 떨어진 구간은
그대로 직선(no-op)이라 기존 각진 박스와 성능/외관 차이 없음. `CornerRadius=0`(기본값)이면
완전히 예전과 동일한 동작.

**설정**: `MainViewDetectionOverlay`/`UAVCameraDetectionOverlay`/`RCWSDetectionOverlay` 셋 다
겹쳐 배치되는 카메라 Image(`MainViewImage`/`UAVCameraImage`/`RCWSViewImage`)의 Brush
`RoundedBox` 코너 반경과 `CornerRadius` 값을 동일하게 맞춰주면 됨.

### ScrollingRulerWidget: non-wrap 모드에서 spine도 눈금 범위 밖으로 안 그려지게 수정(2026-07-11)

**증상**: non-wrap 모드 재설계(바로 위 항목) 이후 눈금은 `MinValue`/`MaxValue` 밖에서 정상적으로
안 그려지는데, `bShowSpine`의 연결선은 여전히 위젯 전체 길이(0~AxisLength)를 항상 그려서 눈금이
없는 빈 구간에도 선만 남아있었음.

**수정**: spine 그리는 범위를 하드코딩된 0~AxisLength 대신, 이미 계산되어 있는 `Ticks` 배열의
실제 화면 위치(`AxisPos`) 최소~최댓값으로 바꿈 — 눈금이 어차피 `MinValue`/`MaxValue` 밖에서
생성 자체가 안 되므로(바로 위 항목), spine도 자동으로 딱 그만큼만 그려짐. wrap 모드(Azimuth)는
눈금이 항상 보이는 구간을 꽉 채우므로 사실상 동작 변화 없음. 눈금이 하나도 없는 극단적인 경우
(예: `VisibleRange`가 너무 작음)엔 spine도 아예 안 그림.

### ScrollingRulerWidget: 눈금 라벨 소수점/단위 커스텀(2026-07-11)

`LabelDecimalPlaces`(int32, 기본 0)/`LabelSuffix`(FString, 기본 빈 문자열) 신규 추가 — 리본이
직접 그리는 숫자 라벨(카디널 N/E/S/W 라벨 제외) 형식을 결정. ZOOM 리본만 `LabelDecimalPlaces=1`,
`LabelSuffix="x"`로 설정하면 라벨이 "2.5x"처럼 나옴 — 다른 리본(Azimuth/Elevation)은 기본값
그대로 두면 기존과 동일한 정수 라벨("330", "-20")이 유지됨. `FString::Printf(TEXT("%.*f%s"),
LabelDecimalPlaces, Value, *LabelSuffix)`로 구현.

### ScrollingRulerWidget: 눈금-문자 간격 커스텀(2026-07-11)

`TickLabelGap`(float, 기본 4.0) 신규 추가 — Major 눈금 끝과 그 라벨 사이 간격. 가로/세로 모드
둘 다 동일하게 적용됨(가로: 라벨을 눈금과 수직으로 띄움, 세로: 수평으로 띄움), `bMirrored`일
때도 정상 반영. 두께(Thickness)와 달리 이건 로컬 좌표계 오프셋이라 WBP 줌 배율에 이미 자연스럽게
맞춰 스케일됨(별도 `AllottedGeometry.Scale` 보정 불필요 — 그 보정은 `MakeLines`의 두께 인자가
스크린스페이스 픽셀로 해석되는 특수한 경우에만 필요함).

### ScrollingRulerWidget: non-wrap 모드도 스크롤하도록 재설계(2026-07-11)

**사용자 지적**: `bWrapMode=false`가 그동안 "MinValue~MaxValue를 고정 배치, 스크롤 없음"이었는데,
이건 그냥 값만 보여줄 뿐 움직임이 없어서 사실상 불필요한 기능 아니냐는 지적 — 맞는 말이었음.
EL(고각)은 Azimuth처럼 360도로 반복(wrap)되진 않지만("-90~0~90"), 그래도 현재값에 따라 눈금
자체가 스크롤되어야 함.

**재설계**: `bWrapMode`의 의미를 "값이 반복(순환)되는가"로 좁힘 — 두 모드 다 이제 동일하게
스크롤함(현재값이 항상 화면 중앙 고정 포인터 위치에 오고, 눈금이 그 아래로 흘러감,
`VisibleRange`가 양쪽으로 보이는 폭 결정). 차이는: wrap 모드는 값이 360에서 0으로 순환,
non-wrap 모드는 `MinValue`/`MaxValue`를 벗어나는 눈금을 아예 안 그림(래핑도, 확장도 안 함) —
그래서 현재값이 `MaxValue`에 닿으면(예: 줌 10.0x) 그 눈금이 정확히 중앙 포인터 위치에 오고,
그 너머는 그냥 비어있게 됨(사용자가 원한 정확한 동작). `VisibleRange` 프로퍼티도 이제 두 모드
다 항상 활성화됨(기존엔 wrap 모드에서만 편집 가능했음).

**ZOOM 전용 비선형 눈금(`ValueBreakpoints`)**: 줌 눈금 값(0.5/1.0/2.5/5.0/10.0)은 숫자 간격이
균일하지 않은데(0.5→1.0은 0.5 차이, 2.5→5.0은 2.5 차이) 화면상 눈금 간격은 균일하게 보여야
하고, 저 5개 숫자만 major 눈금 라벨로 나와야 함(1.0과 2.5 사이엔 라벨 없는 minor 눈금 하나만
추가). 이를 위해 `ScrollingRulerWidget`에 `TArray<float> ValueBreakpoints` 신규 추가 — 2개
이상 채우면 그 순간부터 "인덱스 공간"에서 눈금을 균일 간격으로 생성하고(각 breakpoint가
정확히 인덱스 1씩 차이), major 눈금 라벨을 표시할 때만 그 인덱스를 다시 실제 값으로 역변환함
(`IndexToValue`). 이 모드에서는 `MinValue`/`MaxValue`/`MajorTickInterval`은 완전히 무시되고
유효 범위가 `[0, ValueBreakpoints.Num()-1]`로 자동 대체됨. `CurrentValue`(실제 줌 배율, 예:
2.5)는 `ValueToIndexPosition()`으로 인덱스 공간에 매핑해서 스크롤 위치 계산에 사용(2.5는
정확히 인덱스 2). `MinValue`/`VisibleRange` 등 나머지 프로퍼티는 EL처럼 비어있는(`ValueBreak
points.Num()<2`) 경우 기존 선형 동작 그대로 유지.

### RCWSPreviewActor: "RCWS 3D 모델 시각화 (고정)" 구현(2026-07-11)

`ui.md`에는 "아직 계획 없음"으로만 적혀있었는데, 기획서 원문에 "2. 3D 모델 시각화 - RCWS 3D
모델 시각화 (고정)" 항목이 있었음이 확인되어 이번에 구현. 방식은 사용자와 논의 후 확정:

- **"고정"의 의미**: 뷰가 안 바뀌는 정적 이미지가 아니라 **뷰잉 카메라 각도만 고정**된 실시간
  인디케이터로 해석 — 완전 정적 이미지면 "3D 모델 시각화"라고 부를 이유가 없고, 실제 포탑이
  차체 기준 어디를 보는지 계속 알려주는 게 더 유용함.
- **"디오라마" 방식**: 실제 차량이 있는 씬과 완전히 분리된 위치(레벨의 Z ~ -6000 등, 사용자가
  직접 배치)에 포탑 메시 복제본 하나 + 고정 앵글 카메라 하나만 있는 미니어처 씬을 따로 둠 —
  씬 캡처가 실제 차량/UGV의 특정 컴포넌트만 골라서 찍는(`ShowOnlyComponents` 류) 기능이
  마땅치 않아서, 아예 별도 공간에 최소 구성으로 다시 만드는 쪽이 훨씬 깔끔함(다른 물체가 전혀
  안 섞임). 미니맵(`AMinimapCaptureActor`)과 동일한 "레벨에 하나 배치, `BeginPlay`에서
  RenderTarget 자동 생성" 패턴.
- **차체 기준(hull-relative) vs 월드 기준(world-absolute)**: `AzimuthRibbon`/`ElevationRibbon`은
  월드 절대 방위를 쓰도록 이미 고쳤지만(바로 위 "Elevation도 월드 기준으로" 항목), 이 디오라마는
  **차체 기준 상대각**을 써야 함 — 디오라마엔 움직이는 "차체"가 없으므로, 월드 기준값을 먹이면
  실제 차량이 주행하면서 방향을 틀 때마다 포탑이 차체 대비 전혀 안 움직였는데도 미니어처
  포탑만 빙빙 도는 그림이 됨(위젯의 목적과 정반대). 다행히 구현도 더 간단함 — 새로 추가한
  `URCWSComponent::GetMount()`가 반환하는 마운트의 `GetRelativeRotation()`을 그대로 쓰면 됨
  (`AddPanTiltInput`이 원래 조작하는 값 그 자체라 별도 계산 불필요).

**신규 파일**: `Source/titan_example/UI/RCWSPreviewActor.h/.cpp` — `TurretMesh`(포탑 메시
복제본, 스태틱메시는 활성 RCWS의 실제 마운트에서 매 틱 자동 복사해오므로 나중에 진짜 포탑
메시로 교체돼도 이 액터는 안 건드려도 됨)와 `Capture`(고정 앵글 씬 캡처, 에디터에서 위치/각도
자유롭게 재배치 가능 — 시작값은 그냥 대략적인 3/4 앵글)를 가짐. `Tick`마다
`Atitan_examplePlayerController::GetCameraControlTarget()` 기준으로 트럭/UGV 중 활성 RCWS를
찾아(`Monitor1Widget::ResolveActiveRCWS()`와 동일한 로직) 그 마운트의 상대 회전값을
`TurretMesh`에 그대로 반영. `CaptureFPS` 기본 15(미니맵의 0.5보다 훨씬 반응성 있게, 실제
조준경만큼 무제한은 아님).

**RCWSComponent.h 변경**: `USceneComponent* GetMount() const` 신규 getter 추가 —
`SightCamera->GetAttachParent()`를 반환(기존 `AddPanTiltInput`이 내부적으로 쓰던 것과 동일한
값을 외부에 노출).

**사용자 작업**: 레벨에 `RCWSPreviewActor`(또는 그 BP 서브클래스) 하나 배치, Z ~ -6000처럼 씬
밖 위치로. `TurretMesh`는 처음엔 빈 상태(활성 RCWS의 마운트에서 자동 복사되므로 수동 할당
불필요), `Capture`의 상대 위치/회전을 원하는 "고정" 앵글로 에디터에서 조정. WBP에서
`RCWSPreviewImage`(Image) 이름만 맞춰 배치.

**디오라마 배경(같은 날, 사용자 결정)**: 투명 배경(프로젝트 전역 `r.PostProcessing.PropagateAlpha`
필요) 대신, 하늘색→검정 그라데이션 구체로 디오라마를 감싸는 방식으로 결정 — 기본 `Sphere`
메시(노멀이 바깥쪽)를 안에서 봐야 하므로 머티리얼에 **Two Sided** 필요(속이 빈 메시가 따로
있는 게 아니라 모든 메시는 원래 셸이라 노멀 방향과 컬링만 문제였음).

MCP로 `/Game/UI/Materials/M_RCWSPreviewSky` 생성함 — `MaterialDomain=MD_Surface`,
`ShadingModel=MSM_Unlit`(씬 라이팅 영향 안 받게), `BlendMode=BLEND_Opaque`, `TwoSided=true`.
그래프: `AbsoluteWorldPosition - ObjectPositionWS`로 액터 로컬 위치를 구하고 Z만
`ComponentMask`로 뽑은 뒤, 0~1로 정규화 → `Saturate`로 클램프 → `Lerp(BottomColor, TopColor,
그값)` → Emissive. `TopColor`(기본 하늘색)/`BottomColor`(기본 검정) 둘 다 벡터 파라미터라
머티리얼 인스턴스에서 자유롭게 색 조정 가능.

**정정 — "그라데이션이 아니라 위/아래 딱 잘린 두 색"(같은 날)**: 처음엔 정규화 기준을
`GradientHeight`(수동 cm 값, 기본 500) 스칼라 파라미터로 나눴는데, 구체의 실제 스케일이 그거랑
안 맞으면(예: 스케일 30배로 반지름 1500cm인데 기준값은 500) 그라데이션 구간이 구 전체에 비해
얇은 띠에 불과해서 나머지 대부분이 완전히 클램프된 단색으로 보임 — 값을 올려도 그 얇은
전환대가 이동만 할 뿐 안 넓어지는 것처럼 보인 이유. **해결**: 수동 값 대신 `ObjectRadius`
노드(메시의 실제 바운딩 구 반지름을 자동으로 읽음)를 기준으로 사용하도록 변경 — 이제 구를
얼마나 크게 스케일하든 항상 정확히 최상단~최하단까지 걸쳐서 자동으로 그라데이션됨. 기존
파라미터는 `GradientHeightScale`(기본 1.0 = 반지름 그대로, 배율 조절용)로 이름 변경해서 남겨둠.

**"메시만 나오고 나머지는 검은색"(같은 날)**: 머티리얼 자체(에셋 프리뷰 썸네일로 확인, 구
바깥쪽에서 정상적으로 그라데이션 보임)와 씬 배치(구체 스케일 30, `RCWSPreviewActor`와 같은
위치, 머티리얼 정상 할당, `TwoSided=true` 전부 정상)는 문제 없었음. 원인은 **씬 캡처의 오토
노출(Auto Exposure/Eye Adaptation)** — 이 디오라마는 아주 작고 고립된 씬이라, 조명을 받는
`TurretMesh`(밝음)에 맞춰 노출이 자동 보정되면서 상대적으로 은은한 Unlit 이미시브 하늘
배경이 통째로 검게 찌부러짐(메인 레벨처럼 다양한 밝기의 물체가 섞여서 노출이 완만하게
잡히는 것과 달리, 이 작은 씬은 비교 대상이 거의 없어서 극단적으로 보정됨). `RCWSPreviewActor`
생성자에서 `Capture->ShowFlags.SetEyeAdaptation(false)` +
`PostProcessSettings.AutoExposureMethod=AEM_Manual`로 오토 노출을 완전히 끄도록 수정.

**(폐기됨 — 아래 크로마키 항목 참고)** ~~사용자 작업: 구체 액터를 만들어 기본 `Sphere` 메시
배치, `RCWSPreviewActor`의 디오라마 전체를 감쌀 만큼 크게 스케일, `M_RCWSPreviewSky` 적용.~~
오토 노출 수정 후 실제로 이미시브가 살아났지만, 하늘색 배경을 대시보드 디자인과 맞추기가
어려워서 최종적으로 투명 배경(크로마키 방식)으로 전환하기로 결정함(사용자 확정).

### RCWSPreviewImage 투명 배경 — 크로마키 방식으로 최종 결정(2026-07-11)

**왜 진짜 알파(`r.PostProcessing.PropagateAlpha`)가 아니라 크로마키인지**: 그 설정은 씬 캡처
단위가 아니라 렌더링 파이프라인 전체(씬컬러 버퍼 포맷, TAA/TSR 히스토리 등)에 알파를
흘려보내는 **프로젝트 전역 토글**이라 이 캡처 하나만 골라서 켤 방법이 없음 — RCWS
메인뷰/미니맵 등 다른 모든 씬 캡처, 에디터 뷰포트, 패키징 빌드까지 전부 영향받음. 사용자가
나중에 RCWS 메인 뷰를 Lumen으로 고품질화할 계획이 있는데, 알파 전파는 Lumen
리플렉션/GI·TSR과 함께 쓸 때 엣지 케이스가 보고된 적 있는 조합이라(Epic 문서도 같이 쓸 때
테스트 권장) 그 계획과 충돌할 리스크가 있음 — 그래서 전역 설정을 아예 안 건드리는 크로마키로
결정.

**구현**: MCP로 신규 머티리얼 2개 생성.
- `/Game/UI/Materials/M_ChromaKeyBackdrop` — `MaterialDomain=MD_Surface`,
  `ShadingModel=MSM_Unlit`, `BlendMode=BLEND_Opaque`, `TwoSided=true`(구 안쪽에서 봐야 하므로,
  둥근 모서리 DetectionOverlayWidget 항목과 같은 이유). `KeyColor` 벡터 파라미터(기본
  마젠타 `(1,0,1)`) 하나만 그대로 Emissive로 출력하는 단색 배경 — 구체(`StaticMeshActor_0`)의
  머티리얼을 기존 `M_RCWSPreviewSky`에서 이걸로 교체함.
- `/Game/UI/Materials/M_ChromaKey` — `MaterialDomain=MD_UI`, `BlendMode=BLEND_Translucent`,
  `ShadingModel=MSM_Unlit`(M_IconFlatTint와 동일한 UI 머티리얼 패턴). `SourceTexture`(텍스처
  파라미터, 런타임에 `PreviewRenderTarget` 바인딩) 픽셀 색과 `KeyColor`(배경 머티리얼과 동일한
  기본 마젠타) 사이 `Distance` 계산 → `Tolerance`(기본 0.4)~`Tolerance+EdgeSoftness`(기본
  0.1) 구간에서 `SmoothStep`으로 부드럽게 Opacity 0→1 전환(하드 컷 대신 경계 안티에일리어싱) →
  Emissive는 `SourceTexture.RGB` 그대로.

`Monitor1Widget::BindCameraImages()`에서 `RCWSPreviewImage`를 더 이상 `SetImageRenderTarget`
(단순 텍스처 브러시)로 바인딩하지 않고, `M_ChromaKey` 기반 다이나믹 머티리얼 인스턴스(MID)를
만들어서 `SourceTexture` 파라미터에 `RCWSPreviewRef->PreviewRenderTarget`을 연결한 뒤
`SetBrushFromMaterial`로 적용 — 여전히 한 번만 바인딩(항상 같은 RenderTarget 오브젝트).

**주의**: `M_ChromaKeyBackdrop`과 `M_ChromaKey`의 `KeyColor` 기본값이 서로 같은 마젠타로
맞춰져 있음 — 둘 중 하나라도 색을 바꾸면(예: 배경 구체 색 변경) 다른 쪽도 반드시 같이
맞춰줘야 크로마키가 정상 작동함. `Tolerance`/`EdgeSoftness`는 `M_ChromaKey` 머티리얼
인스턴스에서 자유롭게 조정 가능(경계에 색 번짐이 남으면 `Tolerance`를 높이거나
`EdgeSoftness`를 낮춰서 조절).

### 미니맵 FOV콘 SpanDegrees 실시간 연동 + UGV 마커 방향 버그(2026-07-11)

**질문**: FOV콘의 `SpanDegrees`가 카메라 FOV 값이랑 자동 연동되어 있는지, RCWS Zoom 리본은 FOV를
어떻게 구하는지.

**답**: `ZoomRibbon`은 FOV가 아니라 **줌 배율**(`RCWS->GetZoomLevel()`, 0.5x~10.0x)을 표시하는
것이라 원래부터 FOV 관련 로직이 전혀 필요 없음 — 처음부터 정상 연동되어 있었음. 반면 FOV콘의
`SpanDegrees`는 실제로 그동안 연동이 안 되어 있었음(WBP에 넣어둔 고정값만 사용, 줌을 넣어도
콘이 안 좁아짐).

**구현**: `URCWSComponent`/`AUAVPawn`에 `GetCurrentFOVDegrees()` 신규 getter 추가 — 각각
`SightCamera->FOVAngle`/`GimbalCamera->FOVAngle`을 그대로 반환(줌 적용 시
`SetZoomLevel()`/`AddZoomInput()`이 이미 `CameraFOV/ZoomLevel`을 그 필드에 매 순간 써넣고
있으므로, 별도 계산 없이 그 값을 그대로 읽으면 항상 정확함 — "따로 계산해서 어긋날 걱정" 없음).
트럭/UGV/UAV FOV콘 3개 다 `RefreshMinimap()`에서 매 갱신마다 `SetSpanDegrees()`로 덮어쓰도록
변경 — WBP에서 더 이상 `SpanDegrees`를 수동 설정할 필요 없음(코드가 항상 최신값으로 갱신).

**추가로 발견된 버그**: 같은 작업 중 사용자가 `MinimapUGVMarker`가 반대 방향을 향하고 있다고
지적 — UGV 메시가 -X를 정면으로 두고 제작되어 있어서(`UGVMovementComponent.cpp`가 이미 같은
이유로 `GetForwardVector()`를 4곳에서 negate하고 있었음, 기존 코드에 전례가 있었음)
`GetActorRotation().Yaw`를 그대로 쓰면 마커가 반대로 그려짐. `(-GetActorForwardVector())
.Rotation().Yaw`로 수정(단순 +180 대신 기존 컨벤션과 일관되게 forward vector 반전 방식 사용).
FOV콘은 애초에 `RCWS->GetCurrentData().AzimuthDegrees`(카메라 자체 월드 방위)를 쓰고 있어서
이 버그의 영향을 안 받았음 — 사용자가 직접 확인해줌.

### 씬 캡처 FOV 조정 + UAV 줌 버튼 색상 자동화(2026-07-12)

**FOV 변경**: RCWS/UAV 1.0배율 시야각이 좁아 보인다는 피드백으로 기본값 조정 —
`URCWSComponent::CameraFOV` 40 → **90**, `AUAVPawn::CameraFOV` 60 → **120**. Truck
CCTV(`UQuadCamComponent::CameraFOV`, 90)는 줌 개념 자체가 없어서(고정 FOV) 논의 끝에 그대로
유지하기로 확정 — 애초에 ×2.5 공식을 그대로 적용하면 225°가 되는데 이건 원근 투영이 성립 안
되는 값이라(180° 근처부터 렌즈가 극단적으로 왜곡) 다른 방식으로 처리 필요했음. 두 값 다
`EditAnywhere` 프로퍼티라 에디터 Details 패널에서 그대로 커스텀 가능(별도 작업 불필요).

**UAV 줌 버튼 색상 자동화**: `UAVZoom1xText`/`UAVZoom2_5xText` 신규 TextBlock 필드 추가 —
`RefreshUAVZoomButtons()`가 `UAVRef->GetZoomLevel()`과 비교해서 현재 선택된 배율의 텍스트만
하늘색(`#17B9FF`), 나머지는 흰색으로 자동 반영(신호세기 바들과 동일한 "recolor, not hide"
패턴). 버튼 클릭 시 실제 줌을 바꾸는 처리(`UAVRef->SetZoomLevel(...)` 호출)는 여전히 각
Button의 WBP `OnClicked` 그래프에서 함 — 이름 겹침 문제가 없는 단순 함수 호출이라 C++로 옮길
필요 없음, 색상 로직만 C++로 자동화.

### 미니맵 축척 표시는 이미 구현되어 있음 — 표에 안 보여서 놓쳤을 뿐(2026-07-12)

`GetScaleBar100mPixelWidth()`(`Monitor1Widget.h/cpp`)로 이미 구현되어 있음 — 5절
"UAVCameraSignalBar1~4" 근처 프로즈 문단(**스케일바** 항목)에만 적혀있고 위젯 표 행으로는
안 빠져있어서 스캔하다 놓치기 쉬웠던 것으로 보임. `MinimapCaptureActor::CaptureWidth`와 Image
위젯의 실제 픽셀 크기로 "100m"에 해당하는 픽셀 길이를 계산 — WBP에서 막대 그래픽의
`Width`/`Width Override`를 이 함수에 Property Binding하면 됨(라벨 텍스트 "100 m"는 고정
텍스트로 직접 적어두면 됨).

### ⚠️ 알려진 이슈 — 씬-현실 축척 불일치가 거리 관련 값들에 반영 안 됨(2026-07-12, 미수정)

**배경**: UAV 위경도 표시를 구현하면서(`GeoCoordinateUtils.h`) Cube/Cube3 두 지점의 실측
위경도와 실제 거리(160,381cm)를 씬 상의 두 지점 거리와 비교해본 결과, **씬이 실제 축척과
1:1이 아님**이 확인됨 — `GeoCoordinateUtils::GetSceneToRealTransform()`이 계산하는
`Scale`(실제 cm / 씬 cm)이 **약 1.227** — 즉 씬이 실제보다 약 18.5% 작게 지어져 있음(1 -
1/1.227 ≈ 0.185). 이 `Scale` 값은 현재 **위경도 변환에만** 적용되고 있음.

**문제**: 씬의 raw 거리(cm)를 그대로 `/100`해서 "미터"로 보여주는 다른 모든 곳은 이 보정을
전혀 안 받고 있음 — 즉 위경도는 실제 축척 기준으로 정확한데, 나머지 거리/속도 표시는 전부
씬 축척(실제보다 작은) 기준이라 서로 안 맞음. 사용자가 직접 확인 요청한 목록 + 코드 전수
조사 결과, 현재 raw 변환(`/100` 또는 `* 3600/100000`)만 쓰고 있는 곳은 다음 5곳으로 확인됨:

1. `AUAVPawn::UpdateStatusHUDFlightData`의 `AltitudeMeters` (`(CurrentLocation.Z -
   HomeLocation.Z) / 100.f`)
2. 같은 함수의 `SpeedKmh` (cm/s → km/h, `* 3600.f / 100000.f`)
3. `AUGVPawn`/`UUGVStatusComponent`의 `SpeedKmh` (동일 공식)
4. `URCWSComponent::UpdateRangeTrace()`의 `RangeMeters`(RNG 거리 표시, 트럭/UGV RCWS 공용)
5. `Monitor1Widget::GetScaleBar100mPixelWidth()` — 미니맵 100m 스케일바(바로 위 항목)

**아직 수정 안 함** — 사용자 요청대로 우선 기록만 해둠. 나중에 고칠 때는:
`GeoCoordinateUtils.h`에 회전 없이 `Scale` 값만 반환하는 작은 헬퍼(예:
`GetDistanceScaleFactor()`, 내부적으로 기존 `GetSceneToRealTransform()`의 `OutScale`만
꺼내 씀)를 하나 추가하고, 위 5곳의 최종 값에 그 배율을 곱해주면 됨 — 계산 공식 자체(거리 →
미터, cm/s → km/h)는 안 바뀌고 마지막에 배율 곱하는 한 줄만 추가하면 되는 정도라 수정
자체는 간단함. 다만 5곳 다 "raw cm" 기준으로 이미 튜닝된 더미값(예: `ComputeDummyAltitude`
같은 함수들)이 섞여있을 수 있어서, 실제 적용 전에 각 소스별로 실제값/더미값 구분해서 어디에
곱해야 하는지 한 번 더 확인 필요.

## 7. 사용자 확인/준비 필요 사항 정리

1. **0.1절** — 모니터2 재설계로 빠진 UGV 4분할캠/상태정보/미니맵을 어디에 배치할지, 아니면
   "RCWS 뷰어"가 트럭/UGV 공용 화면이라는 해석이 맞는지
2. **2절 표의 `T_Vector`/`T_Rectangle*`** — 정확한 용도(추정과 다르면 알려주세요)
3. **0.5절** — RCWS 방위각을 차체 기준 상대각으로 보여줄지, 진북 기준 절대 방위로 보여줄지
4. **4절 위경도 변환** — 레벨의 어느 지점을 위경도 origin으로 잡을지(실제 GPS 좌표 아니고
   `memo.md` 의문사항처럼 더미 계산이라 임의로 정해도 되지만, 화면에 표시되는 값이 시나리오
   내내 일관돼야 하므로 기준점 하나 필요)
5. **4절 적 예상 위치 원** — memo.md 시나리오 #4-1의 "시작 신호(적 위치 좌표) 수신" 트리거
   구현이 선행돼야 함 — 이번 UI 라운드와 별개 작업으로 봐도 되는지
6. 아이콘/눈금 관련해서는 추가로 준비할 PNG 없음 — 눈금은 전부 코드 구현(2절), 아이콘은 이미
   완료된 33개로 충분해 보임
