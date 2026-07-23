# RCWS/QuadCam/UAV 시네마틱 카메라 아키텍처 전환 + 에디터-PIE 노출 불일치 조사(진행중)

> `titan_example` 프로젝트. RCWS/QuadCam(4분할)/UAV 짐벌 세 곳의 씬캡쳐 카메라를
> "디자인팀이 시네마틱 카메라 설정을 직접, 직관적으로 만질 수 있게" 다시 짠 작업과, 그 과정에서
> 겪은 버그 두 건(컴파일 에러 2종, 매 프레임 캡쳐 회귀), 그리고 아직 안 풀린 에디터-PIE 노출
> 불일치 조사 기록.

---

## 1. 배경 — 기존 구조의 문제

기존에는 디자이너가 `SceneCaptureComponent2D`를 직접 배치하고, 필요하면 별도의
`CinematicLensSyncComponent`(DOF/노출/컬러그레이딩만 다른 `CineCameraComponent`에서 복사해오는
보조 컴포넌트)를 추가로 붙이는 구조였음. 문제:

- 어떤 시네카메라가 어떤 씬캡쳐에 영향을 주는지 이름 매칭이 직관적이지 않았음
- 디자이너가 시네마틱 카메라의 렌즈/DOF/노출 기능을 온전히 다 쓰기 어려움 — 씬캡쳐 자체엔
  그런 UI/기능이 없어서 별도 동기화 컴포넌트에 의존
- 에디터에서 보는 것과 씬캡쳐 WBP 화면이 차이가 컸음(당시엔 원인 미상 — 이번 4번 섹션 조사로 이어짐)

**요구사항**: 디자이너는 `UCineCameraComponent` 하나만 배치해서 렌즈/DOF/노출을 Details 패널에서
직접 조정. 실제 렌더링을 담당하는 `SceneCaptureComponent2D`는 코드가 알아서 만들고 위치를
맞춘다. RCWS 뷰어, QuadCam 4분할, UAV 카메라 전부 동일 패턴.

---

## 2. 새 아키텍처

패턴은 세 곳(`URCWSComponent`, `UQuadCamComponent`, `AUAVPawn`) 전부 동일:

1. 디자이너가 `UCineCameraComponent`를 원하는 위치(터렛 마운트/짐벌 등)의 자식으로 배치,
   정해진 이름(`RCWSSightCineCamera`, `Front/Rear/Left/RightCineCamera`, `GimbalCineCamera`)을
   붙이고 렌즈/DOF/노출을 자유롭게 튜닝.
2. `BeginPlay`에서 `FComponentReference`(`*CineCameraRef`, Details에서 재지정 가능)로 이 CineCamera를
   찾고, **코드가 `NewObject<USceneCaptureComponent2D>`로 실제 캡처 컴포넌트를 CineCamera와
   동일한 부모의 형제(sibling)로 생성** — CineCamera의 현재 트랜스폼을 그대로 시작점으로 삼음.
3. 이후 CineCamera는 **다시는 움직이지 않는, 순수 렌즈 설정 참조용**으로만 남고, pan/tilt
   입력(`AddPanTiltInput`/`AddGimbalPanTiltInput`)은 실제 캡처 컴포넌트를 직접 회전시킴.
4. 매 틱 `SyncLensFromCineCamera()`가 `UCameraComponent::GetCameraView()`(엔진이 실제 카메라
   블렌딩에 쓰는 동일 함수)를 호출해서 CineCamera의 `PostProcessSettings`를 캡처 컴포넌트로
   복사. **FOV는 절대 복사하지 않음** — 아래 2.1 참고.

### 2.1 FOV는 절대 CineCamera에서 동기화하면 안 됨 (하드 룰)

RCWS/UAV의 `CameraFOV`/`ZoomLevel` → `SetZoomLevel()`이 캡처의 `FOVAngle`을 소유. 예전
`CinematicLensSyncComponent`(현재 삭제됨)가 `ViewInfo.FOV`를 그대로 캡처에 덮어써서 줌 입력이
먹통이 된 적이 있었음 — `SyncLensFromCineCamera()`는 `PostProcessSettings`/`PostProcessBlendWeight`만
복사하고 FOV는 절대 건드리지 않도록 각 파일에 명시적으로 주석 처리해둠.

### 2.2 적용 파일

| 시스템 | CineCamera 레퍼런스 | 실제 캡처 (코드가 생성) | 소유 파일 |
|---|---|---|---|
| RCWS | `SightCineCameraRef` (기본 `RCWSSightCineCamera`) | `SightCamera` | `Vehicles/RCWSComponent.h/.cpp` |
| QuadCam (4분할) | `Front/Rear/Left/RightCineCameraRef` | `FrontCamera` 등 4개 | `Plugins/QuadCamModule/.../QuadCamComponent.h/.cpp` |
| UAV 짐벌 | `GimbalCineCameraRef` (기본 `GimbalCineCamera`) | `GimbalCamera` | `Vehicles/UAVPawn.h/.cpp` |

`CinematicLensSyncComponent`(구 방식)는 완전히 삭제. `TitanTruck.h`에서도 이제 없어진
`FrontCamera/RearCamera/LeftCamera/RightCamera/RCWSSightCamera` 네이티브 필드와 그 생성 코드를
제거 — `QuadCam->GetFrontCamera()` 등 접근자로 대체.

---

## 3. 전환 과정에서 겪은 컴파일 에러 2건

### 3.1 `QuadCamModule.Build.cs`에 `CinematicCamera` 모듈 누락

`titan_example.Build.cs`에는 `CinematicCamera`를 추가했지만, **플러그인 모듈은 게임 모듈과
의존성이 완전히 독립적**이라 `Plugins/QuadCamModule/.../QuadCamModule.Build.cs`에도 따로
추가해야 했음. 안 그러면 `QuadCamComponent.gen.cpp`에서 `CineCameraComponent.h: No such file or
directory` 및 연쇄 UHT 파싱 에러(C4430/C2146/C2737/C2065) 발생.

### 3.2 UAV — Internal Compiler Error (프로퍼티 이름 충돌)

```
Internal Compiler Error: Tried to create a property GimbalCineCamera in scope BP_UAV_C, but
another object (ObjectProperty /Script/titan_example.UAVPawn:GimbalCineCamera) already exists there.
```

원인: `AUAVPawn`(네이티브 C++)에 `UCineCameraComponent* GimbalCineCamera`(private)를 선언했는데,
`BP_UAV`가 `AUAVPawn`을 **상속하는 진짜 서브클래스**라 그 블루프린트에 디자이너가 배치한
`GimbalCineCamera`라는 이름의 SCS 컴포넌트와 네임스페이스가 충돌.

- RCWS의 `SightCineCamera`(대상 컴포넌트 이름은 `RCWSSightCineCamera`)는 애초에 이름이 달라서
  이 문제를 우연히 피함.
- QuadCam의 4개 포인터는 애초에 위험 없음 — `UQuadCamComponent`는 `ATitanTruck`에 **붙는
  컴포넌트**일 뿐 베이스 클래스가 아니라서 프로퍼티 네임스페이스를 공유하지 않음.

**수정**: C++ 필드명을 `ResolvedGimbalCineCamera`로 변경(`UAVPawn.h/.cpp` 전체). 대상
`FComponentReference`(`GimbalCineCameraRef`, 찾는 이름 `"GimbalCineCamera"`)는 그대로 유지 —
찾는 대상 이름과 저장하는 C++ 필드명이 달라도 문제없음.

---

## 4. 렌더 해상도 / 안티에일리어싱 — 확인만 하고 넘어간 것

- **해상도**: `RCWSComponent::RenderTargetSize`(기본 640×360), `QuadCamComponent::RenderTargetSize`
  (기본 240×135, 4개 카메라 공유), `AUAVPawn::RenderTargetSize`(기본 640×360) 전부 이미
  `EditAnywhere`라 BP Details 패널에서 인스턴스별로 바로 조정 가능 — 추가 작업 불필요. WBP
  Image 위젯 크기와 종횡비를 맞추는 게 권장(안 맞으면 늘어나 보이거나 GPU 낭비).
- **안티에일리어싱**: `CineCameraComponent`에는 AA 설정 자체가 없음. 프로젝트 전역
  `Project Settings → Engine - Rendering → Anti-Aliasing Method`가 메인 뷰포트/모든 씬캡쳐에
  동일 적용됨(카메라별 개별 방식 선택 불가, on/off 토글만 `SceneCaptureComponent2D`의
  Show Flag Settings로 가능). TAA/TSR은 여러 프레임 누적(temporal)이 필요한데, RCWS/QuadCam/UAV가
  당시엔 타이머 기반 수동 캡처(매 프레임이 아님)라 메인 뷰포트보다 AA 수렴이 덜 될 수 있다는
  점을 지적함 — 5절의 "매 프레임 캡쳐" 요청과 이어짐.

---

## 5. 회귀 버그 — `bCaptureEveryFrame` 도입 시도가 RCWS/UAV 화면을 완전히 멈추게 함

### 5.1 요청과 시도

"RCWS/UAV 화면은 매 프레임 캡쳐해야 함" 요청에 따라, 기존의 `CaptureFPS` 기반 타이머 캡처
(`TickCaptureTimer()`가 매 틱 `CaptureScene()`을 수동 호출하던 방식, `CaptureFPS=0`이라 사실
이미 매 프레임 캡쳐하고 있었음)를 정리한다며 엔진의 `bCaptureEveryFrame = true` 플래그로
교체하고, 중복이라 판단해 수동 `CaptureScene()` 호출을 제거함.

### 5.2 증상

RCWS/UAV 화면이 **첫 프레임(지형 텍스쳐도 아직 안 입혀진, 검은 지형+하늘만 있는 이미지)에
완전히 멈춤** — 카메라를 돌려도 전혀 갱신 안 됨.

### 5.3 원인 (UE 5.8 엔진 소스로 확인)

`Engine/Source/Runtime/Engine/Private/Components/SceneCaptureComponent.cpp` 확인 결과:

- `bCaptureEveryFrame`의 실제 매 프레임 재캡쳐는 **`USceneCaptureComponent2D::TickComponent()`
  자기 자신의 틱 안에서** `CaptureSceneDeferred()`를 호출하는 방식으로 구현되어 있음
  (회전/이동과는 무관).
- 이동(회전 포함) 트리거 캡쳐는 `SendRenderTransform_Concurrent()`에 있는데, 이건
  `bCaptureOnMovement && !bCaptureEveryFrame`일 때만 동작 — RCWS/UAV는 `bCaptureOnMovement=false`로
  두고 있어서 이 경로 자체가 애초에 막혀있었음(카메라 돌려도 갱신 안 된 이유).
- `BeginPlay` 도중 `NewObject` + `RegisterComponent()`로 **동적 생성/등록한** 캡처 컴포넌트의
  경우, `TickComponent()` 기반의 `bCaptureEveryFrame` 자동 갱신이 안정적으로 걸리지 않음(정확한
  근본 원인은 미상이나, 재현은 100% 확실) — 결과적으로 `BeginPlay`의 최초 1회
  수동 `CaptureScene()` 호출분만 렌더링되고 이후 영원히 멈춤.

### 5.4 수정

`bCaptureEveryFrame`을 다시 `false`로 되돌리고, 대신 **우리 자신의(확실히 매 틱 도는)**
`URCWSComponent::TickComponent()` / `AUAVPawn::Tick()`에서 `CaptureScene()`을 무조건 매 틱
호출하도록 변경. 더 이상 쓸모없어진 `CaptureFPS`/`TimeSinceLastCapture`/`TickCaptureTimer()`는
RCWS/UAV 양쪽 헤더·cpp에서 완전히 제거(죽은 코드로 안 남기고 삭제). QuadCam은 건드리지 않음
(모니터링 피드용으로 스로틀 유지가 의도된 설계라 요청 대상도 아니었음).

---

## 6. Lumen 실험 — RCWS CineCamera에 고급 렌더링 옵션 강제 on (성능 문제로 확인/조정 필요)

에디터-PIE 화면 차이(7절)를 테스트해볼 겸, `BP_UGV_Vehicle`의 `RCWSSightCineCamera`
`PostProcessSettings`에 다음 6개 오버라이드를 언리얼 프로퍼티 편집으로 켬:

- `DynamicGlobalIlluminationMethod = Lumen`, `ReflectionMethod = Lumen`
- `LumenSceneDetail`/`LumenFinalGatherQuality`/`LumenReflectionQuality`/`LumenSceneLightingQuality`
  전부 2로 상향(기본 1)

프로퍼티 재조회로 이 6개만 정확히 켜지고 나머지(DOF/노출/색보정 등)는 안 건드려졌음을 확인.
다만 **RCWS 캡쳐가 매 프레임 무제한으로 도는 상태에서 Lumen GI+Reflection Quality 2를 추가로
얹은 결과 심각한 프레임 끊김 발생** — 메인 뷰포트의 Lumen 렌더링에 사실상 하나를 더 얹는
꼴이라 무거움. 사용자가 Lumen을 끄니 끊김 해소 확인. 결론: 이 설정은 성능 문제로 인해 그대로
유지하기 어려움 — 나중에 Quality를 낮추거나 RCWS 캡쳐 프레임레이트를 다시 제한하는 식으로
재검토 필요.

(참고: 같은 세션에서 별개로 "HLOD 클러스터 재빌드 필요" 경고, "텍스쳐 스트리밍 풀 초과" 경고도
발생했으나 둘 다 이 Lumen/노출 이슈와는 무관한 별개 사안으로 확인 — HLOD는 정적 지오메트리
LOD 병합 시스템, 이 레벨은 월드 파티션이 꺼져있어 `Window → Hierarchical LOD Outliner`로
수동 빌드해야 함.)

---

## 7. 진행 중 — 에디터 "Lit" 뷰 vs PIE WBP 캡쳐 노출/밝기 불일치 (미해결)

### 7.1 증상

에디터에서 UGV 선택 시 보이는 메인 뷰포트, 그리고 CineCamera 자체의 에디터 내장 프리뷰
인셋(RCWS 사이트 카메라와 동일 렌즈/트랜스폼)은 둘 다 자연스러운 노출로 보임. 반면 **실제 PIE
중 RCWS WBP 화면은 나무 등 밝은 부분이 심하게 날아가고(흰색으로 클리핑), 동시에 배경 산은
그림자가 뭉개지듯 더 어둡게** 나옴 — 단순 밝기 차이가 아니라 콘트라스트 자체가 다른 느낌.

사용자가 찾은 유일한 우회법: 레벨의 HDRIBackdrop/Skylight 강도(비정상적으로 높게 세팅되어
있었음)를 낮추고, `PostProcessVolume`의 `Min EV100 = Max EV100 = 10`(완전 고정) 락을 풀면
에디터와 PIE가 똑같아짐.

### 7.2 조사해서 배제한 원인들 (라이브 값/엔진소스로 확인 완료)

- `PostProcessVolume`: `AutoExposureMethod = AEM_Histogram`(Manual 아님), `bUnbound=true`,
  `Min=Max EV100=10`.
- `r.DefaultFeature.AutoExposure.ExtendDefaultLuminanceRange = 1` — "10"이 EV100 단위로 정확히
  해석됨(구버전 luminance 단위 혼동 아님).
- `r.EyeAdaptation.MethodOverride = -1`, `ShowFlag.EyeAdaptation = 2`(둘 다 오버라이드 없음) —
  전역적으로 Manual 노출 모드가 강제되고 있지 않음.
- `RCWSSightCineCamera`(CineCamera)는 `DepthOfFieldFstop`(Av 2.8)만 오버라이드, 노출 관련 필드는
  전혀 안 건드림 — 카메라가 볼륨의 노출값을 덮어쓰는 게 아님.
- 에디터 뷰포트 자체의 "Exposure" 툴바 설정은 **"Game Settings"**(레벨의 PostProcessVolume을
  그대로 따라감) — Fixed EV100 직접 지정은 애초에 비활성화되어 있었음. PPV의 min/max를 바꾸면
  에디터 뷰포트에도 실시간 반영됨(사용자 직접 확인) — 즉 에디터가 별도의 독립 노출 경로를 쓰는
  게 아님.

### 7.3 남은 유력 가설 (미확정)

1. **런타임 생성 RenderTarget의 감마 플래그 미설정**: `UTextureRenderTarget2D`는 생성자에서
   `bForceLinearGamma = true`가 기본값이며, `RTF_RGBA8_SRGB`로 설정할 때만(그리고
   `PostEditChangeProperty()` — 에디터 Details 패널 편집시에만 호출됨 — 안에서만) 이 플래그와
   `SRGB` 텍스처 플래그가 올바르게 재동기화됨. RCWS/UAV 코드는 `RenderTargetFormat = RTF_RGBA8`
   (`_SRGB` 아님)를 순수 C++로 설정하고 `PostEditChangeProperty`를 거치지 않으므로, `CaptureSource
   = SCS_FinalColorLDR`(이미 톤매핑+감마 보정된 최종 색상)가 실제로는 잘못된 감마 플래그를 가진
   렌더타겟에 쓰여, WBP Image 위젯이 샘플링할 때 감마를 잘못 해석할 가능성.
   - 근거: CineCamera 에디터 프리뷰 인셋은 RCWS와 완전히 동일한 렌즈/트랜스폼으로 같은 걸 보는데도
     정상으로 보임 — 이 인셋은 언리얼 엔진 자체 내장 카메라 프리뷰 기능이라 RCWSComponent의
     캡쳐/렌더타겟 생성 코드를 전혀 거치지 않음. "같은 씬, 같은 카메라 설정인데 결과가 다르다"는
     건 라이팅/렌즈 문제가 아니라 우리 코드의 캡쳐 파이프라인 자체를 가리킴.
   - 아직 라이브 PIE 세션에서 `SightRenderTarget`의 실제 `SRGB`/`bForceLinearGamma` 값을 직접
     조회해서 확정하지 못한 상태(PIE가 꺼져있어서 조회 불가했음).
2. 사용자가 찾은 "HDRI/Skylight 낮추기 + EV100 락 풀기" 우회법은 위 가설과 모순되지 않음 —
   오히려 뒷받침함: 락이 걸린 상태에선 에디터-RCWS 간에 존재하는 (원인 불명의) 곱연산적 밝기
   차이가 하이라이트 클리핑 임계값을 넘을 만큼 밝을 때만 시각적으로 드러나고, HDRI를 낮추면
   그 차이가 클리핑 영역 밖으로 밀려나서 안 보이게 됨. EV100 락을 풀면 각 뷰가 자기 화면 내용
   기준으로 각자 알아서 재보정하면서 차이가 가려짐. 즉 이 우회법은 **회피책**이지 근본 원인
   특정은 아님.
3. `AutoExposureApplyPhysicalCameraExposure = true`(프로젝트 기본값, 오버라이드 아님)가 잠재적
   지뢰로 남아있음 — `EyeAdaptation` show flag가 꺼진 뷰에서만 Manual 노출로 폴백되며 그때
   CineCamera의 Aperture(2.8)가 실제로 반영됨. 현재는 어디서도 EyeAdaptation을 끄지 않아 안 걸리는
   것으로 보이나(UAV 코드에 "EyeAdaptation 끄면 노출 이상해진다"는 기존 주석이 있음), 완전히
   배제된 건 아님.

### 7.4 다음 확인 단계 (미착수)

- PIE 켠 상태에서 `SightCamera`의 실제 PostProcessSettings/ShowFlags, `SightRenderTarget`의
  `SRGB`/`bForceLinearGamma` 라이브 값을 직접 조회.
- `Show → Visualize → HDR (Eye Adaptation)`로 에디터/PIE의 실제 적용 EV100 숫자를 직접 비교 —
  숫자가 같으면 노출 문제가 아니라 렌더타겟 감마 가설 쪽으로 확정, 다르면 노출 계산 자체의
  뷰별 차이를 다시 파야 함.

---

## 8. 요약 — 상태

| 항목 | 상태 |
|---|---|
| CineCamera 아키텍처 전환 (RCWS/QuadCam/UAV) | 완료 |
| 컴파일 에러 2건 (모듈 의존성, 프로퍼티 이름 충돌) | 해결 |
| 해상도/AA 설정 확인 | 완료(추가 작업 불필요 확인) |
| RCWS/UAV 매 프레임 캡쳐 | 완료 (엔진 `bCaptureEveryFrame` 대신 수동 `CaptureScene()` 매 틱 호출로 구현) |
| RCWS Lumen 고품질 실험 | 성능 문제로 보류 — 재검토 필요 |
| 에디터-PIE 노출/밝기 불일치 | **미해결, 조사 진행중** — 다음 세션에서 7.4 단계부터 이어감 |
