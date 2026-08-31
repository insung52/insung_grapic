> [보관됨 2026-08-31] 최신 버전: `titan_dev_status.md`. 사유: 이 계획이 그대로 구현되어
> `QuadCamModule` 플러그인으로 완성됨(사용법은 `quadcam_usage_guide.md` 참고).

# Titan 트럭 4분할 카메라 뷰 구현 계획

## 배경
- 대상 프로젝트: `C:\working\kadex\titan_example` (UE 5.7)
- 목표: 군용 Titan 트럭(UGV)의 전방/후방/좌측/우측 카메라 영상을 뷰포트 좌측 상단에 4분할로 실시간 표시
- 참고 이미지: UGV 주행 영상 4분할 (전방/후방/좌측/우측, 각 화면에 라벨 + 신호/HD 아이콘)
- 베이스 차량 에셋: `Content/M725_Truck.uasset` (스태틱 메시 2개로 구성된 간단한 BP) — 그대로 써도 되고 새로 만들어도 됨

## 참고 프로젝트 조사 결과 (C:\working\TankSim)
TankSim에 비슷한 기능이 있다는 얘기를 듣고 전체 소스(31개 파일) 확인함. **결론: 재사용 가능한 구현 없음, 새로 작성 필요.**

- `GenesisViewerBridge.cpp` — Genesis 외부 물리 시뮬레이터와 공유메모리(UDP+SharedMemory)로 통신하는 코드. 천 시뮬레이션/리지드바디 데이터 수신용. 카메라와 무관.
- `MinimapCaptureActor.cpp/h` — `USceneCaptureComponent2D` + `UTextureRenderTarget2D` 사용하지만, 위에서 내려다보는 **단일 미니맵**용 (Orthographic, FollowHeight 99000cm, FOV 15°). 4분할 아님.
- `TankSimViewportClient.cpp/h` — 이름은 비슷하지만 실제로는 (1) 패키징 빌드에서 BackgroundBlur 동작을 위한 렌더타겟 강제 설정, (2) YOLO 객체탐지 바운딩 박스를 Canvas에 그리는 오버레이, (3) F11 창모드 토글. 화면 분할과 무관.
- `YOLOSubsystem.cpp` — 메인 뷰포트 렌더타겟 텍스처를 가져와 YOLO 추론 입력으로 쓰는 코드. UI 표시 기능 아님.
- `TankPawn.cpp` — 미니맵 캡처 컴포넌트의 트랜스폼만 참조. 별도 카메라 없음.
- 나머지 파일(`EnemyTank*`, `PlayWidget`, `MinimapWidget`, `ATankVehiclePawn`, `MyPlayerController` 등)에도 전방/후방/좌측/우측, Quad, MultiCam 관련 코드 없음.

→ 복붙할 기존 코드가 없으므로 titan_example에 C++로 새로 구현.

## 구현 방향 (C++ 기반)

### 1. 카메라 구성 (SceneCaptureComponent2D x4)
M725_Truck(또는 신규 Truck Pawn/Actor) C++ 클래스에 부착:
- **Front**: 트럭 전방, Yaw 0°
- **Rear**: 트럭 후방, Yaw 180°
- **Left**: 트럭 좌측면 부착, 전방 기준 -15° (좌측 15도 틀어서 전방 시야 일부 포함)
- **Right**: 트럭 우측면 부착, 전방 기준 +15°

각 컴포넌트마다 `UTextureRenderTarget2D` 1개씩 연결 (총 4개), `CaptureSource = SCS_FinalColorLDR`, 캡처 주기는 매 프레임 또는 일정 간격(성능 고려 시 `bCaptureEveryFrame` 토글 가능하게).

### 2. UI (UMG 위젯)
- C++ `UUserWidget` 파생 클래스 생성 (예: `UQuadCamWidget`)
- 4개의 `UImage`에 각 RenderTarget을 Brush로 바인딩
- 좌측 상단 앵커, 2x2 그리드 레이아웃 (`UGridPanel` 또는 `UCanvasPanel` + 4분할 좌표)
- 라벨("전방"/"후방"/"좌측"/"우측") + 신호 아이콘 등은 이미지 예시처럼 오버레이 텍스트/아이콘으로 추가 (1차 구현에서는 텍스트 라벨만, 아이콘은 추후)
- 위젯은 `AddToViewport()`로 추가, ZOrder는 다른 HUD 위젯과 충돌 없게 조정

### 3. 활성화 트리거
- 1차: 트럭 Pawn/Actor의 `BeginPlay()`에서 캡처 컴포넌트 생성 + 위젯 자동 생성/표시
- 추가 검토: 에디터에서 해당 BP 선택 시에도 보이게 하는 건 런타임 게임플레이가 아니라 **에디터 프리뷰** 기능이라 별도 처리 필요 (`UActorComponent::OnRegister`나 에디터 전용 코드, 혹은 그냥 BeginPlay 동작만으로 충분한지 먼저 확인 — 우선순위는 BeginPlay 쪽으로 진행)

### 4. 성능 고려사항
- RenderTarget 해상도는 표시 크기에 맞게 작게 설정 (예: 480x270 등, 4개 합쳐도 부담 적게)
- `bCaptureEveryFrame` / `bCaptureOnMovement` 옵션으로 매 프레임 캡처 여부 조정 가능하게 노출
- 4개 SceneCapture를 매 프레임 갱신하면 비용이 있으므로, 필요시 프레임 스킵(예: 2프레임마다 갱신) 고려

## 작업 순서 (초안)
1. titan_example에 신규 C++ 클래스 추가: 트럭 Pawn/Actor (혹은 기존 M725_Truck BP의 부모를 C++ 클래스로 교체)
2. SceneCaptureComponent2D x4 + RenderTarget x4 생성/배치 코드 작성
3. UQuadCamWidget C++ 클래스 작성 (4 UImage 바인딩)
4. BeginPlay에서 위젯 생성 및 AddToViewport
5. 에디터에서 카메라 위치/각도(특히 좌/우 15° 오프셋) 튜닝
6. 라벨/아이콘 등 UI 디테일 보강

## 미해결/확인 필요 사항
- 좌/우 카메라의 정확한 부착 위치(트럭 좌/우 측면 어느 지점)와 "전방에서 15도" 각도가 차량 정면 기준인지 카메라 자체 시야 기준인지 확인 필요
- 트럭 베이스를 기존 `M725_Truck` BP로 갈지, 새로 만들지 결정 필요
- 에디터 선택 시 프리뷰 표시 여부는 우선순위 낮음 (BeginPlay 런타임 표시가 1차 목표)
