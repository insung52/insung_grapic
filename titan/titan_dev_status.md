# Titan 트럭 4분할 카메라 (QuadCamModule) — 개발 현황 (2026-06-25)

전장 시뮬레이션 프로젝트의 군용 차량 액터 구현. Fab 무료 군용 트럭(M725 앰뷸런스) 모델을
베이스로, 전/후/좌/우 4방향 SceneCapture 카메라와 M키로 토글되는 4분할 화면을 구현했다.
초기엔 `titan_example` 모듈 안에 직접 구현했으나, 다른 차량·다른 프로젝트에도 재사용할 수
있도록 **`QuadCamModule` 플러그인**(코드 + Content 포함)으로 모듈화했다.

## 1. 전체 구조

```
titan_example/Plugins/QuadCamModule/
  QuadCamModule.uplugin
  Source/QuadCamModule/
    Public/QuadCamComponent.h        — UActorComponent, 카메라 4개 + 토글 로직
    Public/QuadCamUIWidget.h         — UUserWidget 베이스 (BindWidgetOptional)
    Private/QuadCamComponent.cpp
    Private/QuadCamUIWidget.cpp
  Content/
    WBP_QuadCam.uasset               — 실제 4분할 레이아웃 (디자인은 여기서)
```

`ATitanTruck`(`titan_example/Source/titan_example/Vehicles/TitanTruck.h/.cpp`)이 이 플러그인을
사용하는 예시 액터. 본체/창문 메시는 Fab `Retextured_M725_Military_Ambulance_00`의
`Object003_Material__24_0`(`BodyMesh`)/`Object003_001_Material_001_0`(`WindowMesh`), 원본이
~100배 크게 임포트되어 있어 `MeshScale = 0.03`으로 보정(실제 약 4.9m x 2.0m x 2.2m).

## 2. 핵심 구현 — QuadCamComponent

### 카메라 연결: FComponentReference
`UQuadCamComponent`는 4개의 `USceneCaptureComponent2D`를 직접 소유하지 않고,
`FComponentReference`(`FrontCameraRef`/`RearCameraRef`/`LeftCameraRef`/`RightCameraRef`)로
**같은 액터에 있는 다른 컴포넌트를 이름으로 참조**한다. 생성자에서 기본값을
`"FrontCamera"`/`"RearCamera"`/`"LeftCamera"`/`"RightCamera"`로 미리 채워두기 때문에,
C++에서 정확히 이 이름으로 카메라를 만든 액터(`ATitanTruck`처럼)에는 자동으로 연결되고,
BP에서 직접 만든 카메라는 Details 패널에서 드롭다운으로 한 번 지정해주면 된다.

이 방식 덕분에 카메라의 위치/회전은 **BP 뷰포트에서 평범하게 드래그로 배치**할 수 있다 —
QuadCamComponent가 카메라 트랜스폼을 코드에서 덮어쓰지 않기 때문.

### BeginPlay 흐름 (`QuadCamComponent.cpp`)
1. `ResolveCameras()` — 4개 레퍼런스를 실제 컴포넌트 포인터로 변환, 실패하면 경고 로그
2. `SetupCaptures()` — 카메라 4개에 각각 `UTextureRenderTarget2D`(기본 480x270) 생성·연결,
   `CaptureSource = SCS_FinalColorLDR`, `bCaptureOnMovement = false`, `bCaptureEveryFrame = false`
   (위젯이 보일 때만 캡처 — 평소엔 꺼둠)
3. `CreateAndHideWidget()` — `QuadCamWidgetClass`로 위젯 생성, RenderTarget 4개를 바인딩,
   `AddToViewport()` 후 즉시 `Collapsed`로 숨김

### 토글 & possession 게이팅 (`TickComponent`)
- `ToggleKey`(기본 M)를 `WasInputKeyJustPressed`로 매 프레임 직접 읽음 — 별도 Input
  바인딩/Enhanced Input 액션 불필요
- **소유 Pawn이 로컬 플레이어에게 Possess된 상태일 때만** 키 입력에 반응
  (`OwnerPawn->GetController() == UGameplayStatics::GetPlayerController(this, 0)`)
- Possess를 잃으면(다른 차량으로 옮겨탐) 보이고 있던 QuadCam을 자동으로 끔 — 동시에 여러
  차량의 4분할 화면이 겹쳐 보이는 상황을 방지

### 위젯 — QuadCamUIWidget / WBP_QuadCam
- `UQuadCamUIWidget`(C++ 베이스)은 `FrontImage`/`RearImage`/`LeftImage`/`RightImage`
  4개의 `UImage*`를 `BindWidgetOptional`로 선언만 하고, 실제 레이아웃(보더, 라벨, 그리드 배치
  등)은 `WBP_QuadCam`에서 디자인
- `SetRenderTargets()`가 `FSlateBrush::SetResourceObject()`로 RenderTarget을 각 Image의
  브러시에 바인딩 — UMG `SetBrushFromTexture()`는 `UTexture2D`만 받기 때문에 `UTextureRenderTarget2D`
  에는 이 방법을 써야 함

## 3. 비디오 메모리(VRAM) 이슈와 해결

M키를 반복해서 켜고 끌 때마다 VRAM 사용량이 계속 누적되어 결국 경고가 뜨는 문제가 있었다.
원인은 `bCaptureEveryFrame`을 끄고 켤 때마다 Lumen/TAA 같은 **템포럴 렌더 상태(이전 프레임
히스토리 버퍼 등)가 매번 새로 할당**되기 때문이었다.

해결: 4개 SceneCapture 컴포넌트 전부에 `bAlwaysPersistRenderingState = true`를 설정.
이 플래그를 켜두면 캡처를 멈춰도(`bCaptureEveryFrame = false`) 템포럴 렌더 상태가 유지되어,
다시 켰을 때 재할당하지 않는다. 토글 자체는 여전히 `SetQuadCamVisible()`에서
`Cam->bCaptureEveryFrame = bVisible`로 처리 — 캡처를 멈추는 것 자체는 그대로 두고, "멈췄다가
다시 캐는" 과정에서 매번 재할당되는 부분만 막은 것. 추가로, 매뉴얼 `CaptureScene()` 호출처럼
불필요하게 캡처를 강제로 트리거하던 코드도 제거했다.

## 4. 사용법

### 기존 차량(`ATitanTruck`)에서
- 이미 `FrontCamera`/`RearCamera`/`LeftCamera`/`RightCamera` + `QuadCam` 컴포넌트가
  생성자에 박혀 있음. `BP_TitanTruck`에서 카메라 4개의 위치/회전만 뷰포트로 조정하고,
  `QuadCam` 컴포넌트 Details의 `QuadCamWidgetClass`에 `WBP_QuadCam`을 지정하면 끝.

### 새 액터/새 프로젝트에 적용하기
1. `Plugins/QuadCamModule` 폴더 전체를 대상 프로젝트의 `Plugins/`로 복사
   (`Binaries`/`Intermediate`는 복사 전 삭제 — 다른 프로젝트 빌드 캐시라 충돌 가능)
2. 대상 프로젝트 `.uproject`의 `Plugins` 배열에 추가:
   ```json
   { "Name": "QuadCamModule", "Enabled": true }
   ```
3. Generate Visual Studio project files → 빌드
4. 대상 Pawn/Actor에 `Scene Capture Component 2D` 4개 추가 (이름 자유, 추천:
   `FrontCamera`/`RearCamera`/`LeftCamera`/`RightCamera`) → 뷰포트에서 원하는 위치/방향 배치
5. **QuadCam Component** 추가 → Details에서:
   - `FrontCameraRef`~`RightCameraRef`: 4번에서 만든 컴포넌트로 지정
     (이름이 정확히 `FrontCamera`/`RearCamera`/`LeftCamera`/`RightCamera`면 자동 연결됨)
   - `QuadCamWidgetClass`: `WBP_QuadCam` 지정 (필수 — 안 하면 위젯이 안 뜨고 경고 로그만 남음)
   - `Camera FOV`/`Render Target Size`/`Toggle Key`는 필요시 조정

### 런타임 동작
- M키로 4분할 화면 토글, 현재 로컬 플레이어가 Possess 중인 액터에서만 반응
- 다른 액터로 Possess가 넘어가면 이전 QuadCam은 자동으로 꺼짐
- 같은 레벨에 여러 대를 배치해도 각자 독립적인 RenderTarget을 가져서 서로 간섭 없음

### 테스트용 차량 전환 — `NextVehicle` 콘솔 명령
정식 차량 선택 UI 이전 단계의 테스트 수단. PIE 중 `~`로 콘솔을 열고 `NextVehicle` 입력 →
레벨에 있는 **`UQuadCamComponent`를 가진 모든 `APawn`**을 순서대로 찾아 다음 차례를 Possess
(끝까지 가면 처음으로 순환). 구현 위치: `Atitan_examplePlayerController::NextVehicle()`
(`titan_examplePlayerController.h/.cpp`).

## 5. 현재 상태 / 다음 단계

- QuadCamModule: titan_example, TankSim(테스트 배포 후 현재는 titan_example만 유지) 양쪽에서
  동작 확인 완료. 플러그인 구조 자체는 안정적으로 검증됨.
- `WBP_QuadCam` 디테일 디자인은 1차 레이아웃 수준 (제목 바 + 2x2 그리드 + 반투명 라벨).
  레퍼런스 디자인 수준으로 다듬는 작업은 보류 상태.
- 카메라 위치/FOV는 수동 드래그로 잡은 초기값 — 실제 주행 시야 기준 최종 튜닝 필요.
- 같은 트럭에 동반 기능으로 "UAV 상태 정보" 오버레이(배터리/고도/속도/방향/GPS/링크/임무/신호)
  를 추가했고, 같은 M키로 QuadCam과 같이 토글됨 — 별도 문서 `status_hud_dev_guide.md` 참고.
