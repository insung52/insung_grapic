> ⚠️ [guide/ 이관 시 경고, 2026-08-31] 2026-06-24 기준 작성 — 이후 코드가 바뀌었을 수 있음,
> 실제 동작은 에디터/코드로 재확인 권장.

# QuadCamModule 사용 가이드 (2026-06-24)

`QuadCamModule`은 임의의 Pawn/Actor에 **전방/후방/좌측/우측 4분할 카메라 뷰**를 붙일 수 있는
플러그인입니다. 코드 + UI 에셋이 통째로 들어있어서, 플러그인 폴더만 복사하면 다른 프로젝트에도
그대로 적용됩니다 (현재 titan_example, TankSim 양쪽에서 동작 확인됨).

## 0. 새 프로젝트에 플러그인 가져오기 (최초 1회)
1. `Plugins/QuadCamModule` 폴더 전체를 대상 프로젝트의 `Plugins/`로 복사
   (복사 전에 `Binaries`/`Intermediate` 폴더는 지우고 가져갈 것 — 다른 프로젝트 빌드 캐시라 충돌 가능)
2. 대상 프로젝트의 `.uproject` → `Plugins` 배열에 추가:
   ```json
   { "Name": "QuadCamModule", "Enabled": true }
   ```
3. Generate Visual Studio project files → 빌드
4. `Content/WBP_QuadCam`(플러그인 Content 안에 같이 들어있음)이 자동으로 사용 가능

## 1. 임의의 Pawn/Actor에 적용하기
1. 대상 액터(BP 또는 C++)에 **Scene Capture Component 2D 4개** 추가
   - 이름은 자유 (구분하기 쉽게 `FrontCamera`/`RearCamera`/`LeftCamera`/`RightCamera` 추천)
   - 뷰포트에서 위치/방향 직접 배치: 전방(Yaw 0°), 후방(Yaw 180°), 좌측(전방 기준 -15°), 우측(전방 기준 +15°) 등 원하는 대로
2. **QuadCam Component** 추가 (검색창에 "QuadCam")
3. Details 패널에서:
   - `FrontCameraRef` / `RearCameraRef` / `LeftCameraRef` / `RightCameraRef` → 1번에서 만든 4개 컴포넌트를 드롭다운으로 각각 지정
     - 단, **C++로 `FrontCamera`/`RearCamera`/`LeftCamera`/`RightCamera`라는 정확한 이름으로 컴포넌트를 만든 경우** (예: `ATitanTruck`) 자동으로 연결되어 있어서 이 단계 생략 가능
   - `QuadCamWidgetClass` → `WBP_QuadCam` 지정 (필수 — 안 지정하면 위젯이 안 뜸, Output Log에 경고 남음)
   - `Camera FOV`, `Render Target Size`, `Toggle Key`(기본 `M`)는 필요시 조정

## 2. 런타임 동작
- 게임 시작 시 자동으로는 안 뜨고, **`Toggle Key`(기본 M)를 누르면 화면에 4분할 표시 / 다시 누르면 숨김**
- **이 액터를 현재 로컬 플레이어가 Possess하고 있을 때만** M키가 반응합니다. Possess 안 한(조종 안 하는) 차량의 QuadCam은 비활성 상태
- 다른 액터로 Possess가 넘어가면, 이전에 켜져 있던 QuadCam은 **자동으로 꺼집니다** (동시에 여러 개 켜져있는 상황 방지)
- 숨겨진 동안은 SceneCapture 캡처 자체도 멈춰서(`bCaptureEveryFrame=false`) 성능 낭비 없음

## 3. 테스트용 차량 전환 (`NextVehicle`)
정식 선택 UI는 아직 없어서, 지금은 **PIE 콘솔 명령**으로 테스트합니다.
1. PIE 실행
2. `~` (틸드)로 콘솔 열기
3. `NextVehicle` 입력 → Enter

레벨에 있는 **`UQuadCamComponent`를 가진 모든 `APawn`**을 순서대로 찾아서, 현재 Possess 중인 것의
다음 차례를 Possess합니다 (끝까지 가면 처음으로 순환). 트럭이든 다른 Pawn이든, 위 1번 적용 단계만
끝냈으면 이 순환 대상에 자동으로 포함됩니다. (구현 위치: `Atitan_examplePlayerController::NextVehicle()`,
`titan_examplePlayerController.cpp`)

## 4. 알아두면 좋은 것들
- **`bAlwaysPersistRenderingState`**: 4개 SceneCapture 컴포넌트에 항상 켜져있음. 캡처를 껐다 켰다 반복해도
  Lumen/TAA 같은 템포럴 렌더 상태를 매번 새로 할당하지 않아서, M키를 반복 토글해도 비디오 메모리가
  계속 늘어나지 않음 (이 설정 없으면 토글마다 VRAM 경고 발생했었음)
- 위젯(`WBP_QuadCam`)은 `UQuadCamUIWidget`을 부모로 하며, `FrontImage`/`RearImage`/`LeftImage`/`RightImage`라는
  정확한 이름의 `Image` 위젯 4개가 있어야 텍스처가 바인딩됩니다 (이름 틀리면 그냥 빈 화면)
- 같은 레벨에 여러 대를 배치해도 서로 간섭 없이 독립 동작 (각자 RenderTarget 따로 가짐)

## 5. 알려진 한계 / 다음에 손볼 거리
- 차량 선택은 아직 콘솔 명령(`NextVehicle`)뿐 — 추후 별도 UI로 교체 예정
- 좌/우 카메라 각도(±15°) 등은 액터별로 수동 배치해야 함 (자동 계산 없음)
- `QuadCamWidgetClass`를 안 지정하면 조용히(경고 로그만 남기고) 아무 일도 안 일어남 — 처음 적용할 때 까먹기 쉬운 포인트
