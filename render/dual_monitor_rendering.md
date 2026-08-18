# 듀얼모니터 렌더링 개발 정리 (2026-08)

대상 프로젝트: `titan_example`(메인), `titan_example_0807_linux`(리눅스 긴급 패키징용 백업본, 더 완성된 UI 포함)

## 1. 배경 — 기존 방식과 문제점

### 기존 구현 (폐기됨)
- 창 1개를 듀얼모니터 가상 데스크톱 전체 폭(예: 3840x1080)으로 늘리고, `SetWindowLong`/`SetWindowPos`(Win32 전용)로 타이틀바를 제거해 보더리스로 만든 뒤, 그 위에 하나의 WBP가 왼쪽/오른쪽 콘텐츠를 전부 그리는 방식.
- 담당 코드: `titan_exampleViewportClient::ApplyDualMonitorResolution()`.

### 문제점
1. **Windows 전용 API(`#if PLATFORM_WINDOWS`)** — 리눅스에서는 아예 동작 안 함(빈 함수).
2. **엔진 F11 배선과 충돌** — 엔진이 자체적으로 창모드를 토글하면서 raw Win32로 세팅해둔 상태를 되돌려버림. `bDualMonitorChecked`가 1회만 실행되게 막아놔서 복구 로직도 없음.
3. Wayland는 클라이언트가 자기 창 위치를 임의로 지정하는 것을 프로토콜 레벨에서 막아서, 애초에 "창을 특정 좌표로 이동"시키는 접근 자체가 Wayland에서 성립 안 함.

### 대안 검토 및 결론
- 자동 모니터 감지+배치 대신, **사용자가 창을 수동으로 대상 모니터에 드래그한 뒤 F11로 풀스크린**하는 방식 채택.
  - 이유: 사용자가 직접 드래그하는 건 컴포지터가 처리하는 별개 경로라 X11/Wayland 프로토콜 이슈가 없음. F11(창모드↔풀스크린)은 "지금 이 창이 떠있는 자리에서 풀스크린"이라는 요청이라 어느 모니터에 있든 표준적으로 잘 동작함.
  - 대신 **창을 2개**로 완전히 분리(같은 프로세스): 하나는 언리얼 기본(진짜) 뷰포트 렌더링, 하나는 씬캡쳐 이미지 여러 개를 보여주는 대시보드.

## 2. 최종 아키텍처

### 창 역할 분담
| 창 | 내용 | 호스팅 방식 |
|---|---|---|
| **Monitor2** | RCWS 조준 화면 — 진짜 3D 뷰포트 렌더(placeholder Image + `SyncRCWSViewportRect`로 실제 뷰포트를 그 화면 사각형에 그림), 관련 HUD(조준점/터렛 레티클/탐지 오버레이/방위·고각·줌 리본/RCWS 상태 텍스트) | 기존 메인 창 그대로, `AddToViewport()` |
| **Monitor1** | 씬캡쳐 텍스처만 표시 — QuadCam 4분할, 미니맵, UAV 영상피드, 전장카메라 인셋, (있는 경우) RCWS 3D 모델 프리뷰, 헤더/UGV패널/오디오포커스 등 | 새로 만든 **진짜 네이티브 창**(`SNew(SWindow)` + `FSlateApplication::Get().AddWindow()`) |

핵심 판단 기준: **"진짜 뷰포트 렌더링이 필요한가, 아니면 이미 렌더된 텍스처를 보여주기만 하면 되는가"** — 전자만 메인 창(Monitor2)에 남기고, 후자는 전부 분리된 창(Monitor1)으로. RCWS 관련 콘텐츠(3D 프리뷰 포함)는 전부 Monitor2로 몰아넣음(사용자 확정 — "RCWS 소속이면 다 Monitor2").

### 위젯 분리
- 기존 하나로 합쳐져 있던 위젯 클래스를 둘로 쪼갬(원본 클래스는 되돌리기 대비용으로 그대로 남겨둠, 새 클래스만 사용):
  - `titan_example`: `SelfDefenseDashboardWidget` → `SelfDefenseMonitor1Widget` + `SelfDefenseMonitor2Widget`
  - `titan_example_0807_linux`: `Monitor1Widget`(기존 파일 그대로 유지, Monitor2 관련 멤버만 제거) + `Monitor2Widget`(신규 작성, 예전 버전 파일이 있었지만 최신 로직과 안 맞아 전면 재작성)
- WBP도 기존 것을 복제해서 각각 재부모 지정 후, 안 쓰는 위젯을 디자이너에서 삭제하는 방식으로 진행(위젯트리 편집은 MCP/코드로 안전하게 못 건드리는 영역이라 수동 작업).

### 생성/배선 (PlayerController)
- `titan_example`: 축 시스템(`EPlayerAxis`) 존재 — SelfDefense 축일 때만 `Client_OnAxisResolved`에서 두 위젯 생성. **UGV 축은 전혀 안 건드림**(UGV는 최종적으로 창 자체를 안 띄우고 RTSP로 렌더 결과만 송출할 계획, 아직 미구현이라 지금은 `UGVTestDashboardWidgetClass`로 임시 대체 중).
- `titan_example_0807_linux`: 축 구분 없는 단일 PC 버전 — `BeginPlay`에서 무조건 둘 다 생성.
- 기존 `LeftDashboardWidgetClass`/`RightDashboardWidgetClass`(구 스팬 방식의 잔재) 프로퍼티는 삭제하지 않고 **비워서** 남겨둠 — 중복 생성 방지.

## 3. 발견/해결한 버그 (근본 원인까지 정리)

### (1) Monitor1 창이 "에디터/PIE 스타일"로 뜨는 문제
- **원인**: `SNew(SWindow)`의 기본값이 Slate 커스텀 크롬(타이틀바를 OS가 아니라 Slate가 직접 그림) — 언리얼 에디터 본체나 "New Editor Window PIE"가 쓰는 것과 같은 스타일.
- **해결**: `.UseOSWindowBorder(true)` 지정. 리눅스 SDL 백엔드(`LinuxWindow.cpp`)도 이 플래그를 대칭적으로 처리하는 것을 엔진 소스로 확인 — 크로스플랫폼 안전.

### (2) Monitor1에서 F11이 아예 안 먹힘
- **원인**: 엔진의 F11 자동 풀스크린 처리는 `GEngine->GameViewport`(진짜 뷰포트가 달린 메인 창) 전용으로 배선되어 있음. Monitor1은 뷰포트 없는 순수 Slate 창이라 그 배선 대상이 아님.
- **해결**: 위젯에서 `NativeOnKeyDown` 오버라이드로 F11을 직접 받아 `Window->SetWindowMode()` 토글. 단, `SetIsFocusable(true)` + 창 생성 직후 `FSlateApplication::Get().SetKeyboardFocus(...)`로 실제 키보드 포커스를 넘겨줘야 키 이벤트가 옴(안 하면 아무 데도 안 감).

### (3) 리눅스에서 F11 풀스크린 시 검은 여백 발생
- **원인**: `FLinuxWindow::SetWindowMode()`가 풀스크린 전환 시 `OnSizeChanged`를 **창 생성 시점의 옛날 캐시 크기**(`VirtualWidth`/`VirtualHeight`)로 쏨. 반면 엔진 기본 F11 경로(`ReshapeWindow` 경유, 진짜 뷰포트가 있는 창이 씀)는 이 캐시를 제대로 갱신함. 커스텀 창(Monitor1)은 `SetWindowMode`만 호출해서 이 버그를 그대로 밟음.
- **해결**: 풀스크린 전환 직후, 창이 걸쳐있는 모니터의 실제 해상도(`FDisplayMetrics`로 조회)로 강제 `Window->Resize()`를 한 번 더 호출 — `Resize()`는 `ReshapeWindow` 경로를 타므로 캐시가 정상적으로 갱신됨.

### (4) Monitor2 창모드 리사이즈 시 가로세로 비율이 고정됨 (Windows/Linux 공통)
- **원인**: 엔진이 메인 게임 창을 만들 때(`UGameEngine::CreateGameWindow`) 프로젝트 설정 `bShouldWindowPreserveAspectRatio`(기본값 `true`, Project Settings > Description > "Should Window Preserve Aspect Ratio")를 그대로 `SWindow`의 `ShouldPreserveAspectRatio`에 넘김.
- **해결**: `Config/DefaultGame.ini`에 `bShouldWindowPreserveAspectRatio=False` 추가. Monitor1(커스텀 창)은 이 옵션 자체를 안 쓰고 Slate 기본값도 `false`라 원래부터 해당 없음.

### (5) Monitor1 콘텐츠가 창 크기 변화에 전혀 반응 안 함 — **가장 핵심적인 버그**
- **증상**: 창 자체는 리사이즈/풀스크린 시 크기가 잘 바뀌는데(Slate 레이아웃은 정상), 안의 UMG 위젯들은 항상 디자인 캔버스 크기 그대로 고정됨. 진단 로그(`GetCachedGeometry()` 비교)로 확정.
- **원인**: `AddToViewport()`로 붙는 위젯은 엔진의 `SGameLayerManager`가 내부적으로 `SDPIScaler`로 감싸서 `UUserInterfaceSettings::GetDPIScaleBasedOnSize(뷰포트크기)` 기준 DPI Curve 스케일을 적용해줌(엔진 소스 `SGameLayerManager::GetGameViewportDPIScale()` 확인). 커스텀 창은 이 경로를 전혀 안 거쳐서 스케일링 자체가 없었음.
  - (시행착오: 처음엔 `SBox`로 `HAlign/VAlign Fill`을 명시하면 해결될 거라 생각했으나, `SBox`의 기본값이 이미 Fill이라 아무 효과 없는 수정이었음 — 진단 로그로 실제 데이터를 보고서야 진짜 원인을 확정함)
- **해결**: `SGameLayerManager`와 동일한 계산을 직접 복제 — Monitor1 창 콘텐츠를 `SDPIScaler`로 감싸고, `DPIScale`을 창의 현재 크기 기준 `GetDPIScaleBasedOnSize()` 값으로 매 프레임 갱신(`TAttribute`/람다). 이 스케일은 가로/세로에 **동일한 값 하나**를 곱하는 균등 스케일이라 내부 비율이 절대 안 깨짐 — 창 비율이 안 맞으면 여백으로 남고, 맞으면 꽉 채움(Monitor2와 동일한 방식).

### (6) 알림/확인창(`WBP_Noti`)이 엉뚱한 창(Monitor2)에만 뜸
- **원인**: `UNotificationSubsystem`의 `Toast->AddToViewport()`/`Dialog->AddToViewport(100)`은 항상 `GEngine->GameViewport`(=메인 창=Monitor2)에만 붙음. Monitor1은 뷰포트가 없는 창이라 애초에 `AddToViewport()`로 닿을 방법이 없음.
- **해결**: `SelfDefenseMonitor1Widget`(/`Monitor1Widget`)에 화면 전체를 덮는 `NotificationHostPanel`(CanvasPanel, BindWidgetOptional) 추가 + `GetNotificationHostPanel()` 게터. PlayerController에 `GetSelfDefenseMonitor1WidgetInstance()`(/`GetMonitor1WidgetInstance()`) 퍼블릭 게터 추가. `NotificationSubsystem`이 `AddToViewport()` 대신 이 패널에 `AddChild`(Monitor1이 아직 준비 안 됐으면 `AddToViewport()`로 폴백). 토스트 가로 중앙 정렬도 예전 고정폭(3840 통합캔버스 절반 가정) 대신 앵커 50%로 바꿔서 실제 창 크기에 자동으로 맞게 함.

### (7) (환경 문제, 코드 버그 아님) 창이 2배 폭으로 뜸
- **원인**: 게임 코드가 아니라 **이 컴퓨터 에디터의 로컬 Play 설정 캐시**(`Saved/Config/WindowsEditor/EditorPerProjectUserSettings.ini`의 `[/Script/UnrealEd.LevelEditorPlaySettings]` 섹션, `NewWindowWidth=3834` 등) — 옛날 듀얼모니터 스팬 방식 시절 창 크기가 "마지막 Standalone 창 크기"로 남아있던 것.
- **해결**: 해당 ini 값을 1920x1080/정상 위치로 직접 수정. **패키지 빌드에는 영향 없는 사안**(이 ini는 에디터 전용, 패키지 출력물에는 안 들어감) — 리눅스 배포판에서는 애초에 문제 안 됐을 것으로 판단.

## 4. 크로스플랫폼(X11/Wayland) 관련 결정 사항

- 자동 모니터 배치를 포기한 결정적 이유: Wayland는 클라이언트가 `xdg_toplevel`의 절대 위치를 지정하는 것을 프로토콜 차원에서 금지함. UE 5.8 리눅스 백엔드(`LinuxWindow.cpp`) 확인 결과 `MoveWindowTo`가 Wayland 툴레벨 창에 대해서는 요청 좌표를 무시하고 무조건 `(0,0)`으로 캐시만 갱신(`SDL_SetWindowPosition(HWnd, 0, 0)`), 실제 이동 시도조차 안 함.
- 풀스크린 요청(`SDL_SetWindowFullscreen`)은 대상 디스플레이 지정 없이 "지금 위치 기준"으로 동작 — 이건 프로토콜이 허용하는 표준 동작이라 X11/Wayland 모두 문제 없음. 그래서 "사용자가 드래그 → F11"이 두 프로토콜 모두에서 성립하는 유일한 신뢰 가능한 방법.
- `UseOSWindowBorder` 플래그도 리눅스 SDL 백엔드에서 대칭적으로 처리됨을 소스로 확인(`HasOSWindowBorder`가 꺼져있으면 `SDL_PROP_WINDOW_CREATE_BORDERLESS_BOOLEAN` + `UTILITY` 플래그를 명시적으로 세팅 — 이게 커졌던 "에디터 툴창처럼 보이던" 원인이었음).

## 5. 남은 일 / 알려진 제약

- **WBP 디자이너 작업**: 각 프로젝트에서 Monitor1/Monitor2용 WBP를 복제 후 재부모 지정했지만, 안 쓰는 위젯 삭제와 `NotificationHostPanel`(화면 전체 CanvasPanel) 배치는 디자이너에서 수동으로 완료해야 함.
- **창 위치는 세션 간 기억 안 됨**: 매 실행마다 사용자가 Monitor1 창을 드래그해서 원하는 모니터로 옮겨야 함(리부팅이 잦지 않은 고정 설치 환경이라 수용 가능하다고 판단, 필요하면 나중에 마지막 위치 저장/복원 기능 추가 가능).
- **소크 테스트 권장**: Monitor1(씬캡쳐 전용 창)이 Lumen GI + 상시 씬캡쳐만 도는 상태에서 예전에 "시간이 갈수록 버벅이다 멈추는" 버그가 있었던 이력이 있음(`bDisableWorldRenderingOnStart` 관련 사고). 지금은 같은 프로세스에서 Monitor2가 진짜 뷰포트를 계속 렌더링 중이라 재현 안 될 것으로 예상되지만, 확실히 하려면 Monitor1만 켜놓고 20~30분 이상 프레임타임 우상향 여부를 체크할 것.
- **`titan_example_0807_linux`에서 실측 완료, `titan_example`은 이식 후 미검증** — 위 3), 4), 5), 6)번 수정을 메인 프로젝트에도 동일 적용했으나, 리눅스 실기 테스트는 백업 프로젝트에서만 했고 메인 프로젝트는 아직 실기 검증 전.
