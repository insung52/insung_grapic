# kadex_test 대시보드 WBP 스펙 (2026-08, BindWidgetOptional 방식으로 전환)

- **2026-08 업데이트**: 처음엔 "C++ 슬롯만 두고 나머지는 WBP 그래프에서 직접 호출" 방식으로
  갔었는데, 기존 `Monitor1Widget`(WBP_kadex2)이 애초에 `BindWidgetOptional` 방식(이름/타입만
  맞춰 배치하면 그래프 작업 없이 자동 연결)으로 짜여 있었던 것과 일관성이 없다는 지적을 받아
  **동일한 패턴으로 다시 구현함.** 아래는 최종 버전.
- 대상: `BP_TestPlayerController`(부모 `Atitan_examplePlayerController`)의 3개 WBP 슬롯.

| 슬롯 | 부모 클래스 | 방식 |
|---|---|---|
| `AxisSelectionWidgetClass` | `UserWidget`(엔진 기본) | **그래프 직접 작성** — 이미 완료됨(사용자가 직접 버튼 3개 연결). 요소가 3개뿐이라 BindWidgetOptional 도입 안 함 |
| `UGVTestDashboardWidgetClass` | **`UUGVTestDashboardWidget`** (신규 C++ 클래스) | **BindWidgetOptional** — 이름/타입만 맞춰 배치 |
| `SelfDefenseDashboardWidgetClass` | **`USelfDefenseDashboardWidget`** (신규 C++ 클래스) | **BindWidgetOptional** — 이름/타입만 맞춰 배치 |

**WBP 만들 때 부모 클래스를 반드시 위 표대로 지정할 것** — 안 그러면 아래 이름들을 배치해도
연결 안 됨. WBP_kadex2가 `Monitor1Widget`을 부모로 뒀던 것과 완전히 동일한 방식.

---

## 0. 자동으로 연결된 것

- `BeginPlay`: `AxisSelectionWidgetClass` 표시(풀스크린 오버레이, ZOrder=100로 3D 씬 위에 덮음).
- `Client_OnAxisResolved`(서버→소유 클라이언트): 선택화면 제거 + 축에 맞는 대시보드 위젯 생성 +
  뷰타겟/카메라 전환(UGV: UGV RCWS / SelfDefense: 전장카메라).
- **추가로 자동화됨**: `UUGVTestDashboardWidget::NativeConstruct`가 `QuadCam->bAlwaysVisible = true`를
  스스로 설정 — 예전에 "WBP Event Construct에서 직접 설정" 하라고 안내했던 부분은 이제 필요 없음.
- **2026-08 버그 수정**: `SetWorldRenderingEnabled(false)` 호출을 완전히 제거함 — 월드 렌더링은
  **항상 켜진 채로 유지**됨(§4 참고, 씬캡쳐-Lumen 충돌로 인한 프레임 저하 버그 재발 방지).
  선택 화면은 그냥 풀스크린으로 3D 씬 위에 덮어서 가릴 뿐, 뒤에서 계속 렌더링됨(성능상 무해).

---

## 1. 초기 화면 — `AxisSelectionWidgetClass`

**변경 없음** — 이미 완료됨(Host/Client 버튼 + IP 텍스트박스, `Get Owning Player` → Cast →
`HostListenServer`/`ConnectToHost` 그래프).

---

## 2. UGV 화면 — `UGVTestDashboardWidgetClass` (부모: `UUGVTestDashboardWidget`)

`Source/titan_example/UI/UGVTestDashboardWidget.h`에 선언된 이름/타입 그대로 WBP에 배치하면
자동 연결. **이름은 대소문자까지 정확히 일치해야 함.**

### 카메라/오버레이

| 이름(정확히 일치) | 타입 |
|---|---|
| `MainViewImage` | Image |
| `MainViewDetectionOverlay` | Detection Overlay (`UDetectionOverlayWidget`) — `MainViewImage`와 동일 위치/크기로 겹쳐 배치 |
| `MainViewAimPointWidget` | Aim Point (`UAimPointWidget`) — `MainViewImage`와 동일 위치/크기. **탄도 보정된 "여기를 조준해야 명중" 지점**(가장 가까운 적 탐지 시에만 표시, 자체 그리기 십자선) — 아래 TurretReticle과는 다른 개념 |
| `MainViewTurretReticleImage` | Image (일반 이미지, 디자이너가 배치한 고정 크로스헤어 PNG) — `MainViewImage`와 동일 위치/크기의 **Canvas Panel 자식**이어야 함(코드가 매 프레임 위치만 옮김). **지금 실제로 포신이 향한 방향**(항상 유효) — `MainViewAimPointWidget`(탄도 조준점, 적 탐지 시에만 유효)과 헷갈리지 말 것 |
| `AzimuthRibbon` | **Open Scrolling Ruler Widget** (`UScrollingRulerWidget`) — ⚠️ 처음에 `Compact Heading Ribbon`으로 잘못 연결했던 걸 수정함(§4). `bWrapMode=true, MajorTickInterval=30, bShowNumericLabels=true, bShowCardinalLabels=true, bShowMidTicks=true, MinorTicksPerMajor=5` |
| `AzimuthRibbonText` | Text — 리본이 자체 라벨을 안 그려서 이 텍스트가 그 역할, 형식 "330"(정수) |
| `ElevationRibbon` | Open Scrolling Ruler Widget — `bWrapMode=false, MinValue=-20, MaxValue=20, bShowSpine=true, bMirrored=false` |
| `ElevationRibbonText` | Text — `ElevationText`와 동일 형식(`+04.6°`), 위치만 다른 두 번째 표시용 |
| `ZoomRibbon` | Open Scrolling Ruler Widget — `bWrapMode=false, MinValue=0.5, MaxValue=10.0, bInvertAxis=true, bShowSpine=true, bMirrored=true, ValueBreakpoints={0.5,1,2,4,8,16}` |
| `ZoomText` | Text — 형식 "2.5x" |
| `QuadCamFrontImage` / `QuadCamRearImage` / `QuadCamLeftImage` / `QuadCamRightImage` | Image |

### RCWS 상태 (`FRCWSStatusData` + `RCWSFireControl->CurrentMode`)

| 이름 | 내용 |
|---|---|
| `AmmoText` | "현재 / 최대" |
| `CameraModeText` | EO/IR |
| `FireModeText` | 단발/점사/연사 |
| `ControlModeText` | 원격 제어/자동 감시/자동 조준/자동 발사 |
| `AzimuthText` | 방위각 판독값, 형식 "%.1f°" — `AzimuthRibbonText`(정수 "330")와 형식 다름 |
| `ElevationText` | 고각, 형식 "+04.6°" |
| `RangeText` | 거리, 형식 "RNG 1234 m" |
| `PowerVoltageText` | 전원 전압 |
| `SystemStatusText` / `ConnectionStatusText` / `WarningStatusText` / `StabilizationStatusText` / `SystemTemperatureText` | 각 상태 문자열 |

### UGV 상태 (`FUGVStatusData`)

| 이름 | 내용 |
|---|---|
| `SpeedText` | 속도 |
| `GearText` | "기어 / 최대기어" |
| `DriveModeText` | 주행모드 |
| `DistanceTraveledText` | 누적 주행거리 |
| `BatteryText` | 배터리 % |
| `VehicleTempText` | 차체 온도 |
| `InclineText` | "피치 / 롤" |
| `UGVSystemStatusText` / `UGVCommStatusText` | 상태 문자열 |
| `EmergencyStopText` | 비상정지 여부 |

---

## 3. SelfDefense(이동형지휘소) 화면 — `SelfDefenseDashboardWidgetClass` (부모: `USelfDefenseDashboardWidget`)

`Source/titan_example/UI/SelfDefenseDashboardWidget.h` 참고. **이번 라운드 범위**: 트럭/UGV/UAV
위치 마커까지만 — 아군/적군 마커, FOV 콘, 미니맵 클릭-좌표 표시는 Monitor1Widget에 있었지만
이번엔 뺐음(다음 라운드).

### 메인뷰/전장카메라 인셋/트럭 QuadCam

**2026-08 변경 — 메인뷰/인셋 역할이 뒤바뀜(§4 참고)**: UGV 화면과 통일하기 위해 메인뷰는 이제
트럭 RCWS(실제 뷰포트 렌더), 전장 카메라는 QuadCam 인셋들과 동급의 작은 scene-capture 인셋으로
축소됨. **기존에 `RCWSInsetImage`/`RCWSInsetDetectionOverlay`/`RCWSInsetAimPointWidget`/
`RCWSInsetTurretReticleImage`/`MainViewImage`로 배치했던 위젯이 있다면 아래 새 이름으로
WBP에서 다시 이름 바꿀 것** — BindWidgetOptional은 정확한 이름 일치가 필수라 이름을 안 바꾸면
연결이 끊어짐.

| 이름 | 타입 |
|---|---|
| `MainViewImage` | Image (**트럭 RCWS, 실제 뷰포트 렌더** — 예전 `RCWSInsetImage` 자리, UGV 화면의 `MainViewImage`와 동일 기법) |
| `MainViewDetectionOverlay` | Detection Overlay — `MainViewImage`와 동일 위치/크기 (예전 `RCWSInsetDetectionOverlay`) |
| `MainViewAimPointWidget` | Aim Point — `MainViewImage`와 동일 위치/크기 (예전 `RCWSInsetAimPointWidget`) |
| `MainViewTurretReticleImage` | Image (고정 크로스헤어 PNG, Canvas Panel 자식) — `MainViewImage`와 동일 위치/크기, 실제 포신 방향 (예전 `RCWSInsetTurretReticleImage`) |
| `BattlefieldCameraInsetImage` | Image (**전장 카메라, scene capture 인셋** — 예전 `MainViewImage` 자리, QuadCam 인셋들과 동급) |
| `TruckQuadCamFrontImage` / `RearImage` / `LeftImage` / `RightImage` | Image |
| `TruckAzimuthRibbon` | Open Scrolling Ruler Widget (UGV 화면의 `AzimuthRibbon`과 동일 세팅) |
| `TruckAzimuthRibbonText` | Text — 형식 "330"(정수) |
| `TruckElevationRibbon` | Open Scrolling Ruler Widget (UGV 화면의 `ElevationRibbon`과 동일 세팅) |
| `TruckElevationRibbonText` | Text |
| `TruckZoomRibbon` | Open Scrolling Ruler Widget (UGV 화면의 `ZoomRibbon`과 동일 세팅) |
| `TruckZoomText` | Text — 형식 "2.5x" |

### 트럭 RCWS 상태

`TruckAmmoText`, `TruckCameraModeText`, `TruckFireModeText`, `TruckControlModeText`,
`TruckAzimuthText`, `TruckElevationText`, `TruckRangeText`, `TruckPowerVoltageText`,
`TruckSystemStatusText`, `TruckConnectionStatusText`, `TruckWarningStatusText`,
`TruckStabilizationStatusText`, `TruckSystemTemperatureText` — 전부 Text, UGV 화면과 동일한
필드/형식.

### UAV 패널 (`AUAVPawn::StatusHUD`, `TitanTruck` 자신의 StatusHUD 아님 — §5 참고)

| 이름 | 타입 |
|---|---|
| `UAVViewImage` | Image |
| `UAVViewDetectionOverlay` | Detection Overlay |
| `UAVBatteryText` / `UAVAltitudeText` / `UAVSpeedText` / `UAVHeadingText` | Text |
| `UAVGpsText` | Text ("고정타입 (위성수)") |
| `UAVLinkText` | Text ("상태 (품질%)") |
| `UAVMissionText` | Text |
| `UAVWaypointText` | Text ("현재 / 전체") |
| `UAVSignalText` | Text (dBm) |
| `UAVFlightTimeText` | Text |

### 미니맵

| 이름 | 타입 |
|---|---|
| `MinimapImage` | Image (배경, `AMinimapCaptureActor->MapTexture` 자동 바인딩) |
| `MinimapTruckMarker` / `MinimapUGVMarker` / `MinimapUAVMarker` | Vehicle Marker (`UVehicleMarkerWidget`) — **반드시 Canvas Panel의 자식이어야 함**(위치를 `CanvasPanelSlot::SetPosition`으로 매 갱신마다 옮김) |

---

## 4. 오늘 코드에서 고친 것 (재빌드 필요)

- **새 C++ 클래스 2개 추가**: `UI/UGVTestDashboardWidget.h/.cpp`, `UI/SelfDefenseDashboardWidget.h/.cpp`
  — Monitor1Widget과 동일한 `BindWidgetOptional` 계약, `NativeConstruct`(액터/컴포넌트 캐싱 +
  QuadCam 상시캡처 설정 + 카메라 이미지 1회 바인딩)/`NativeTick`(리본·뷰포트싱크는 매프레임,
  나머지 텍스트/오버레이/해상도 매칭은 `RefreshIntervalSeconds`마다) 구조.
- `Atitan_examplePlayerController::UGVTestDashboardWidgetClass`/`SelfDefenseDashboardWidgetClass`
  타입을 `TSubclassOf<UUserWidget>`에서 각각 `TSubclassOf<UUGVTestDashboardWidget>`/
  `TSubclassOf<USelfDefenseDashboardWidget>`로 강타이핑 — **WBP 만들 때 부모 클래스를 반드시
  이 타입으로 지정해야 슬롯에 지정 가능.**
- `UAimPointWidget::SetAimPoint`, `UDetectionOverlayWidget::SetDetections`에
  `UFUNCTION(BlueprintCallable)` 추가(이전 라운드) — 이번엔 C++에서 직접 호출하므로 필수는
  아니지만 그대로 유지(다른 곳에서 BP로 쓸 수도 있으니 무해).
- `HostListenServer`/`ConnectToHost` 트래블 직전 `AxisSelectionWidget->RemoveFromParent()` 버그
  수정(이전 라운드, 계속 유효).
- **버그 수정**: `AzimuthRibbon`/`TruckAzimuthRibbon`을 처음에 `UCompactHeadingRibbonWidget`(4분할
  캠용 소형 리본 클래스)으로 잘못 연결했음 — Monitor1Widget 원본은 이 자리에
  `UScrollingRulerWidget`(Open Scrolling Ruler Widget)을 씀. 타입 수정.
- **추가**: `MainViewTurretReticleImage`/`RCWSInsetTurretReticleImage`(실제 포신 방향 크로스헤어,
  기존에 빠뜨렸던 `RCWSTurretReticleImage` 대응), `AzimuthText`/`TruckAzimuthText`,
  `ElevationRibbon`/`TruckElevationRibbon`+`ElevationRibbonText`/`TruckElevationRibbonText`,
  `ZoomRibbon`/`TruckZoomRibbon`+`ZoomText`/`TruckZoomText` — Monitor1Widget의 RCWS 조준화면
  섹션 전체를 이번에 포팅 완료.
- **버그 수정(성능)**: `BeginPlay`/`Client_OnAxisResolved`의 `SetWorldRenderingEnabled(false)`/
  `(true)` 호출을 완전히 제거함. `titan_examplePlayerController.h`의
  `bDisableWorldRenderingOnStart` 주석에 이미 기록된 사고(2026-07-22,
  `bDisableWorldRendering=true`가 Lumen GI 켜진 상시 scene capture와 충돌해 PIE가 갈수록
  버벅이다 멈추는 버그, 라이브 토글로 확인됨 — 그래서 그 프로퍼티는 이미 영구 `false`로
  고정돼 있었음)를 Axis 선택화면 로직이 그대로 재현하고 있었음(사용자 리포트로 발견). 이제
  월드 렌더링은 항상 켜둔 채로, 선택화면은 풀스크린으로 덮어서 가리기만 함.
- **버그 수정**: `AxisSelectionWidget`이 `Client_OnAxisResolved`보다 먼저 뜬다는 가정이 틀렸음이
  실측 로그로 확인됨(리슨서버 자신의 로컬 플레이어는 순서가 뒤집힐 수 있음) — `BeginPlay`가
  `PlayerAxis == Unspecified`일 때만 선택화면을 띄우도록 순서 무관하게 수정.
- **버그 수정**: `kadex_lobby`에서 PIE 렌더링이 전혀 안 되던 문제 — `titan_exampleViewportClient::
  LayoutPlayers()`가 로컬 플레이어 1명일 때 `Super::LayoutPlayers()`를 무조건 스킵하도록 돼있어서
  `ULocalPlayer::Origin/Size`를 애초에 풀스크린으로 채워주는 코드 경로가 사라졌던 것(RCWS
  대시보드가 있는 레벨에선 `SyncRCWSViewportRect`가 매 틱 채워줘서 안 드러났음) — `Size`가 아직
  유효하지 않을 때만 풀스크린 기본값(`Origin(0,0)/Size(1,1)`)을 채우도록 수정.
- **버그 수정**: `BP_TestPlayerController`의 `DefaultMappingContexts`/`UGVMoveAction`/
  `CameraLookAction` 등 입력 관련 프로퍼티가 전부 비어있어서 WASD/조이스틱이 하나도 안 먹던 문제
  — `BP_ThirdPersonPlayerController`의 값을 그대로 복사해서 채움(코드 변경 아님, BP 값만).
- **GameMode 변경**: `bDefaultUnspecifiedAxisToSelfDefense`(bool) → `DefaultAxisWhenUnspecified`
  (`EPlayerAxis` 3단계: Unspecified/UGV/SelfDefense)로 확장 — `kadex_test`를 에디터에서 직접 열고
  PIE해도(로비를 안 거쳐도) 축 선택 없이 곧장 UGV(호스트)로 시작하기 위함. `kadex_lobby`용
  GameMode는 `Unspecified` 유지(선택화면), `kadex_test`용은 별도 GameMode BP를 만들어 `UGV`로
  설정 예정(재빌드 후 MCP로 마저 진행).
- **2026-08 (이번 라운드)**: SelfDefense 대시보드 메인뷰/인셋 역할을 UGV 화면과 통일 —
  - `ATitanTruck::BattlefieldCamera`(단순 `UCameraComponent`, `ActivateBattlefieldCameraAsMainView`로
    직접 ViewTarget에 얹던 방식)를 삭제하고, RCWS/QuadCam과 동일한 "디자이너는
    `UCineCameraComponent`만 배치, 실제 캡쳐는 `BeginPlay`가 코드로 생성" 패턴으로 되돌림 —
    `BattlefieldCineCameraRef`(기본 이름 `"BattlefieldCineCamera"`), `BattlefieldCapture`
    (`USceneCaptureComponent2D`), `BattlefieldRenderTarget`. **BP_TitanTruck 액션 아이템**: 기존에
    있던 전장 카메라 컴포넌트가 CineCamera가 아니라면(플레인 SceneCapture 등) `UCineCameraComponent`
    타입으로 바꾸고 이름을 `BattlefieldCineCamera`로 맞출 것 — 위치/화각은 그 컴포넌트에서 그대로
    잡으면 됨.
  - `Client_OnAxisResolved`의 SelfDefense 분기에서 `ActivateBattlefieldCameraAsMainView()` 호출
    제거 — 메인뷰는 이제 트럭 RCWS(`PrimaryViewCamera`, 항상 기본 active)라 `SetViewTarget(Truck)`
    만으로 충분.
  - 전장 카메라 캡쳐는 매 틱 다 찍지 않고 `AUAVPawn`의 짐벌 캡쳐(`GimbalRoundRobinSlot=1`)와
    번갈아 렌더(`BattlefieldRoundRobinSlot=0`, 둘 다 `Count=2`) — GPU 비용 최적화, RCWS/UAV가 이미
    쓰던 것과 동일한 `GFrameCounter % Count == Slot` 기법.
  - WBP 필드 이름 변경은 위 "메인뷰/전장카메라 인셋/트럭 QuadCam" 표 참고.

---

## 5. 확인이 필요한 것

1. **`ATitanTruck::StatusHUD`의 실제 용도** — `FUAVStatusData` 타입을 쓰는 컴포넌트인데 왜
   트럭에도 붙어 있는지 불명확. UAV 패널엔 `AUAVPawn::StatusHUD`를 씀(코드에 이미 그렇게 구현),
   `Truck->StatusHUD`는 이번 SelfDefense 대시보드 어디에도 안 씀 — 여전히 용도 불명인 채로 남음.

**해결됨**: `Truck->QuadCam->bAlwaysVisible` — `true`로 확인(3절 반영, 코드가 새로 안 건드림).
