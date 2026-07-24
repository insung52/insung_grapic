# 카메라 파이프라인 전면 개편 (CineCamera 통일 → RCWS 실제 렌더링 → AA/Lumen 동기화) — 종합 정리

> `titan_example` 프로젝트. 2026-07-21~23에 걸쳐 RCWS/QuadCam/UAV 카메라 시스템을 여러 단계로
> 손댔고, 중간에 방향이 몇 번 바뀌었다. 기존 문서 2개(`rcws_quadcam_uav_cinecamera_overhaul.md`,
> `rcws_lumen_scenecapture_stutter_investigation.md`)는 각 단계 시점의 스냅샷이라 최신 상태를
> 반영 못 함 — 이 문서가 전체 타임라인과 **최종 코드 상태**를 종합 정리한 것. 앞으로는 이 문서
> 기준으로 참고할 것.

---

## TL;DR — 지금 뭐가 어떻게 되어있나

- **UGV RCWS**: 씬캡쳐가 아니라 **진짜 메인 월드 렌더링**을 씀 (`ULocalPlayer` 서브렉트 방식).
  에디터 뷰포트 수준 화질, Lumen 버벅임 없음. **완료, 안정적으로 확정.**
- **TitanTruck RCWS / UAV 짐벌 / QuadCam(4분할 CCTV)**: 전부 예전처럼 **씬캡쳐 → 렌더타겟 →
  WBP Image** 방식 유지. TitanTruck RCWS도 함께 실제 렌더링으로 확장하는 걸 한 번 시도했으나
  **롤백함**(3번째 섹션 참고). 대신 씬캡쳐 자체의 화질 버그 두 개(지글거림, UAV만 라이팅 이상함)를
  찾아서 고침 — 이제 실제 렌더링만큼은 아니어도 눈에 띄게 좋아짐.
- **아직 안 풀린 문제**: 씬캡쳐 화면(TitanTruck RCWS/UAV)이 UGV RCWS(실제 렌더링) 대비 색감이
  진하고 그림자가 더 어둡게 나옴. 코드 문제는 아닌 것으로 보이고, 레벨 라이팅 세팅(HDRI/Skylight
  세기가 비정상적으로 높고 PostProcessVolume의 EV100을 강제로 고정해서 상쇄시키는 방식) 쪽이
  유력한 원인으로 지목됨 — **사용자가 나중에 처리하기로 하고 보류.** 6절 참고.

---

## 1단계 — CineCamera 아키텍처 통일 (2026-07-21, 완료)

**문제**: 예전엔 디자이너가 `SceneCaptureComponent2D`를 직접 배치하고 `CinematicLensSyncComponent`
(별도 보조 컴포넌트)로 렌즈값을 동기화하는 구조라 다루기 불편했음.

**새 구조** (RCWS/QuadCam/UAV 세 곳 전부 동일 패턴, 지금도 유효):

1. 디자이너는 `UCineCameraComponent` 하나만 원하는 위치에 배치(`RCWSSightCineCamera`,
   `Front/Rear/Left/RightCineCamera`, `GimbalCineCamera`) — 렌즈/DOF/노출을 Details 패널에서
   자유롭게 튜닝.
2. `BeginPlay`에서 코드가 `NewObject<USceneCaptureComponent2D>`로 실제 캡처 컴포넌트를 그 CineCamera와
   같은 부모의 **형제(sibling)**로 생성, 시작 트랜스폼을 그대로 복사.
3. 이후 CineCamera는 **다시는 움직이지 않는 순수 렌즈 설정 참조용**, pan/tilt 입력은 실제 캡처
   컴포넌트(또는 그 마운트)를 직접 회전.
4. 매 틱 `SyncLensFromCineCamera()`가 `UCameraComponent::GetCameraView()`로 CineCamera의
   `PostProcessSettings`만 캡처로 복사. **FOV는 절대 복사 안 함**(줌 입력이 캡처의 `FOVAngle`을
   직접 소유 — 예전 `CinematicLensSyncComponent`가 FOV까지 덮어써서 줌이 먹통됐던 전례 있음).

| 시스템 | CineCamera 레퍼런스 | 실제 캡처(코드 생성) | 파일 |
|---|---|---|---|
| RCWS | `SightCineCameraRef`(`RCWSSightCineCamera`) | `SightCamera` | `Vehicles/RCWSComponent.h/.cpp` |
| QuadCam | `Front/Rear/Left/RightCineCameraRef` | `FrontCamera` 등 4개 | `Plugins/QuadCamModule/.../QuadCamComponent.h/.cpp` |
| UAV 짐벌 | `GimbalCineCameraRef`(`GimbalCineCamera`) | `GimbalCamera` | `Vehicles/UAVPawn.h/.cpp` |

**겪은 컴파일 에러 2건** (둘 다 해결됨, 재발 방지용 기록):
- `QuadCamModule.Build.cs`에 `CinematicCamera` 모듈 누락 — 플러그인은 게임 모듈과 의존성이
  독립적이라 따로 추가해야 함.
- UAV에서 `UCineCameraComponent* GimbalCineCamera`(private 필드)를 선언하니 Internal Compiler
  Error 발생 — `AUAVPawn`은 `BP_UAV`가 진짜 상속하는 베이스 클래스라, 블루프린트에 배치된 SCS
  컴포넌트와 이름이 겹치면 충돌. `ResolvedGimbalCineCamera`로 필드명을 바꿔서 해결(대상
  `FComponentReference`가 찾는 이름 `"GimbalCineCamera"`는 그대로 유지 — 찾는 이름과 저장하는
  C++ 필드명은 달라도 무방).

---

## 2단계 — RCWS Lumen 버벅임 → UGV 실제 렌더링 전환 (2026-07-22, 완료)

RCWS 조준 카메라에 Lumen GI를 켜면 PIE 중 "정상 구간 ↔ 완전 정지 구간"이 번갈아 나며 그 주기가
점점 길어지는 버그 발생.

**원인**: `GameViewportClient::bDisableWorldRendering=true`(메인 뷰포트 3D 렌더링을 통째로 끔,
대시보드가 씬캡쳐만 보여주니 FPS 절약 목적으로 꺼뒀었음) + Lumen 쓰는 지속형 씬캡쳐가 동시에
있으면 발생. 실시간으로 월드 렌더링을 껐다 켰다 하며 버그가 그 자리에서 나타났다 사라졌다 하는
걸 확인해서 인과관계로 증명함. (정확한 엔진 메커니즘은 "Lumen 서페이스 캐시 갱신이 메인 뷰가
실제로 그려지고 있다는 걸 전제로 페이싱되는 듯"이라는 추정 수준 — 100% 소스 확정은 아님.)

**해결책**: 안 쓰이던 메인 뷰포트를 그냥 켜두는 미봉책 대신, **가장 크고 중요한 RCWS 조준 화면
자체를 진짜 메인 렌더링으로 활용**하는 재설계.

### 핵심 메커니즘 — `ULocalPlayer::Origin`/`Size`
스플릿스크린이 쓰는 정규화(0~1) 서브렉트 필드를 로컬 플레이어 1명에 그대로 적용 — 화면의
`RCWSViewImage`가 차지하는 자리에만 실제 3D 렌더링이 나오고 나머지는 검은색. 매 프레임
`RCWSViewImage`의 실제 지오메트리를 읽어서 계산(해상도 하드코딩 없음).

### 구현
- **`Vehicles/RCWSComponent.h/.cpp`**: `SightCamera`(기존 씬캡쳐, 계속 레티클/탐지 UV 계산용으로
  씀)의 **자식**으로 `UCameraComponent* PrimaryViewCamera`를 신규 생성 — 자식이라 위치/회전은
  자동 상속, FOV/PostProcessSettings만 매틱 복사. `UCineCameraComponent` 대신 일반
  `UCameraComponent`를 쓴 이유: CineCamera는 FOV를 초점거리에서 매번 재계산해서 직접 FOV
  세팅과 충돌. `SightCineCamera`는 `SetActive(false)`로 비활성화(안 그러면 `AActor::CalcCamera`가
  먼저 찾아서 씀). `SetSightAspectRatio(float)` 신규 — 실제 화면 사각형 종횡비에 맞춰
  `SightRenderTarget` 리사이즈(레티클 UV 계산이 이 종횡비를 쓰므로 안 맞으면 어긋남).
- **`titan_examplePlayerController.h/.cpp`**: `bDisableWorldRenderingOnStart` 기본값
  `true→false`로 영구 확정. `BeginPlay()`에서 `FindUGVRCWS()->GetOwner()`로 `SetViewTarget()`
  고정(카메라 컨트롤 타겟/Possess와 무관하게 항상 UGV). `SyncRCWSViewportRect(...)` 신규 —
  픽셀 좌표를 `ULocalPlayer::Origin/Size` 정규화 비율로 변환.
- **`UI/Monitor1Widget.cpp`**: `ResolveActiveRCWS()`에서 트럭 분기 제거(항상 UGV로 귀결).
  `RCWSViewImage`는 `HitTestInvisible`+`RenderOpacity(0)`로("Hidden"은 안 됨, 아래 버그 참고).
  기존 매프레임 레티클 갱신 블록에 좌표변환+`SetSightAspectRatio`+`SyncRCWSViewportRect` 호출 추가.
- **`titan_exampleViewportClient.h/.cpp`**: `LayoutPlayers()` 오버라이드 추가(아래 버그 3번).

### 구현 중 만난 서브 버그 3개 (재발 시 참고)
1. **`ESlateVisibility::Hidden`은 `GetCachedGeometry()`를 영구히 (0,0)으로 고정시킴** — 이
   프로젝트 페인트 경로에서 `Hidden`이 `Collapsed`처럼 취급됨. `HitTestInvisible`+
   `RenderOpacity(0.f)`로 대체해서 해결(페인트는 정상적으로 타되 안 보이게).
2. **`FGeometry::LocalToAbsolute()`는 데스크톱 좌표지 뷰포트 픽셀이 아님** — 듀얼모니터 창이
   가상 데스크톱 좌상단(자주 (0,0) 아님) 기준으로 배치되므로, 반드시
   `USlateBlueprintLibrary::AbsoluteToViewport()`로 변환해야 함(DPI 스케일도 처리해줌).
3. **`UGameViewportClient::LayoutPlayers()`가 매 프레임 `Draw()` 직전에 로컬 플레이어를 표준
   스플릿스크린 레이아웃으로 강제 리셋함** — `SyncRCWSViewportRect()`가 매 프레임 정확한 값을
   쓰는 것까지 로그로 확인해도 렌더링은 계속 풀스크린이었던 원인. `titan_exampleViewportClient`
   에서 `LayoutPlayers()`를 오버라이드해서 **로컬 플레이어가 1명일 땐 스킵**하도록 해서 해결
   (현재 코드 상태: 이 "1명일 때만 스킵" 조건 그대로 유지 — 3단계에서 "항상 스킵"으로
   일반화했다가 3단계 자체가 롤백되면서 다시 이 형태로 돌아옴).

### 부수 작업 — UAV `GimbalCamera` BP 에디터 노출 문제 (완료)
UGV/TitanTruck과 달리 UAV만 `GimbalCamera`(씬캡쳐 컴포넌트)가 BP_UAV 에디터에 "네이티브에 고정,
삭제 불가"로 표시되던 문제. **원인**: `AUAVPawn`은 `BP_UAV`가 진짜 상속하는 클래스라, 네이티브
UPROPERTY 이름이 블루프린트 SCS 컴포넌트 이름과 겹치면 그 SCS 노드가 잠김 — `GimbalCamera`가
`public`+`VisibleAnywhere`로 노출되어 있던 게 원인(2026-07-21 리팩터링 때 다른 캡처들처럼
`private`+`Transient`로 안 바꾸고 빠뜨림). `private`+`Transient`로 이동, `GetGimbalCamera()`
접근자 추가로 해결.

---

## 3단계 — TitanTruck/UAV까지 실제 렌더링으로 확장 시도 → 롤백 (2026-07-22~23)

UGV RCWS가 실제 렌더링으로 잘 되니, TitanTruck RCWS + UAV 짐벌도 각각 자기만의 `ULocalPlayer`를
추가로 만들어서(총 3개, 카메라 전용 더미 플레이어) 동시에 실제 렌더링하는 방향으로 확장 시도.

**구현했던 것** (전부 나중에 롤백/삭제됨, 기록만 남김):
- `CameraOnlyPlayerController.h/.cpp`(신규 파일) — 입력 없는 카메라 전용 컨트롤러 베이스 +
  TitanTruck/UAV용 서브클래스 2개. `SetPlayer()`를 오버라이드해서 뷰타겟 설정(BeginPlay가 아니라
  `SetPlayer()` 시점에 해야 함 — `SpawnActor()`가 `BeginPlay()`를 `SetPlayer()` 호출보다 먼저
  동기적으로 실행시켜서, BeginPlay에서 SetViewTarget하면 그 직후 SetPlayer가 덮어써서 무효화됨.
  실제로 겪은 버그 — "이상한 플레이어 하나가 스폰되고 그 시점(월드 원점)을 보여준다" 증상으로
  나타남).
- `UAVPawn.h/.cpp`에 RCWS와 동일한 `PrimaryViewCamera` 패턴 이식 + `SetGimbalAspectRatio()`.
- `RCWSComponent.cpp`의 카메라 비활성화 로직을 일반화 — `SightCineCamera`뿐 아니라 액터의 다른
  모든 `UCameraComponent`를 순회하며 비활성화(TitanTruck은 쿼드캠용 CineCamera 4개가 항상
  active라, `AActor::CalcCamera`가 그것들 중 하나를 먼저 집을 수 있어서 필요했음).
- `titan_exampleViewportClient::LayoutPlayers()`를 "플레이어 수 무관 항상 스킵"으로 일반화.
- `titan_examplePlayerController::BeginPlay()`에 `CreateLocalPlayer(1/2, ...)` +
  `SpawnActor<TitanTruckCameraController/UAVCameraController>` + `SetPlayer()` 호출 추가.
- `Monitor1Widget.cpp`의 `MainViewImage`/`UAVCameraImage`도 `RCWSViewImage`와 같은 패턴으로 전환.

**롤백 이유 — Lumen 다중 뷰 화질 문제**: 3개 뷰(UGV/TitanTruck/UAV) 동시에 풀 Lumen 렌더링하니
"무거운 씬에서 3번째 뷰부터 나무에 비정상적인 흰색 반사광 증폭"과 "줌/시점 이동 시 화면 가장자리에
LED 조명 같은 알록달록 노이즈"가 발생. 후자는 평면+라이트만 있는 미니멀 테스트 레벨에서도 뷰
개수에 비례해서 나타남(1개=없음, 2개=약간, 3개=확실). 원인은 Lumen의 Radiance Cache/Screen
Probe가 프레임당 정해진 트레이스 예산으로 점진적으로 수렴하는 구조인데, 동시 렌더링되는 뷰가
늘수록(각 뷰가 예산을 나눠 쓰거나, 단순히 프레임 비용이 늘어 수렴에 필요한 실제 시간이 길어지거나)
노이즈가 심해지는 것으로 추정(엔진 소스로 100% 확정은 못함, `r.LumenScene.RadianceCache.
NumProbesToTraceBudget` 콘솔변수가 실존하는 프레임당 예산 개념이라는 것까지는 확인).

**최종 결정**: 3개 동시 실제 렌더링은 포기, **UGV RCWS만 실제 렌더링 유지, TitanTruck RCWS/UAV
짐벌/QuadCam은 전부 씬캡쳐 방식으로 되돌림.** 위에 나열한 신규 코드는 전부 삭제/원상복구됨
(`CameraOnlyPlayerController.h/.cpp` 파일 자체가 삭제됨, `UAVPawn`의 `PrimaryViewCamera`도
제거됨, `LayoutPlayers()`는 "1명일 때만 스킵"으로 되돌아감, `titan_examplePlayerController::
BeginPlay()`엔 UGV `SetViewTarget()` 호출 하나만 남음, `Monitor1Widget`의 `MainViewImage`/
`UAVCameraImage`는 `SetImageRenderTarget()`으로 되돌아감).

**향후 최적화 아이디어 (미착수, 범위 밖으로 기록만)**: `QuadCamComponent`의 `TickCaptureTimer`
(10fps 스로틀)가 스로틀 틱마다 4개 카메라를 한꺼번에 다 캡쳐함 — 전체 게임 fps가 10 이하로
떨어지면 스로틀 자체가 무력화되어 매 프레임 캡쳐하는 것과 동일해짐(`QuadCamComponent.cpp:
200-212` 확인됨). 4개를 한 틱에 하나씩 순서대로(라운드로빈) 캡쳐하면 개별 갱신 주기는 늘지만
스로틀 틱당 GPU 부하는 1/4로 줄어듦.

---

## 4단계 — 씬캡쳐 지글거림(shimmer) 원인 확정: TAA는 기본 꺼짐 (2026-07-23, 완료)

3단계 롤백 후에도, TitanTruck RCWS/QuadCam/UAV 화면이 지글거리는(특히 나뭇잎 등 고주파
지오메트리의 그림자 경계가 매 프레임 다르게 흔들리는) 문제가 남아있었음.

**중요한 정정** — 이전 문서(`rcws_quadcam_uav_cinecamera_overhaul.md` 4절)는 "AA는 프로젝트
전역 설정 하나로 메인뷰포트/모든 씬캡쳐에 동일 적용되고 카메라별로 따로 설정 불가"라고
기록했었는데, **이건 틀린 정보였음.** 실제로는 `USceneCaptureComponent2D::ShowFlags.
SetTemporalAA(bool)`로 캡처별 개별 제어가 가능하고, **씬캡쳐는 이 플래그가 기본적으로 꺼진 채로
시작함**(메인 뷰포트는 켜진 채로 시작 — 둘의 기본값 자체가 다름). TAA/TSR은 여러 프레임에 걸친
시간적 누적(temporal accumulation)으로 지오메트리 경계 노이즈를 지워주는 게 핵심 역할이라, 이게
꺼진 씬캡쳐는 매 프레임 다른 노이즈 패턴이 raw하게 그대로 찍힘 — 메인 뷰포트(TAA 켜짐, 항상
매끈)와 차이가 나는 원인.

**해결**: `RCWSComponent.cpp`와 `UAVPawn.cpp`의 `SyncLensFromCineCamera()`에
`SightCamera->ShowFlags.SetTemporalAA(true);` / `GimbalCamera->ShowFlags.SetTemporalAA(true);`
명시적으로 추가(캡처 생성 시 한 번이 아니라 매 틱 강제 — 이 함수가 매틱 `PostProcessSettings`를
통째로 재할당하는 곳이라 그 근처에 넣어야 안정적). `QuadCamComponent`는 사용자가 지금의
저해상도/노이즈 있는 "CCTV 느낌"을 마음에 들어해서 **의도적으로 그대로 둠**(범위 제외).

**결과**: TitanTruck RCWS는 이 수정만으로 UGV RCWS(실제 렌더링)와 거의 동일한 수준으로 개선됨
(색감 차이 제외). UAV는 이 수정만으로는 부족했음 — 5단계로 이어짐.

---

## 5단계 — UAV 짐벌 라이팅 품질 동기화 (2026-07-23, 완료)

4단계 수정 후에도 UAV 화면만 유독 그림자가 지글거리고 나뭇잎 등에 비정상적인 흰색 반사광이
증폭되어 보임(QuadCam 저해상도 CCTV 화면과 비슷한 수준으로 낮은 품질).

**원인**: `UAVPawn.cpp`의 `BeginPlay()`에 다음이 남아있었음:
```cpp
GimbalCamera->ShowFlags.SetLumenGlobalIllumination(false);
GimbalCamera->ShowFlags.SetLumenReflections(false);
GimbalCamera->ShowFlags.SetScreenSpaceReflections(false);
GimbalCamera->ShowFlags.SetReflectionEnvironment(false);
```
1단계 리팩터링 당시 UAV를 QuadCam/Minimap과 같은 "저가형 모니터링 피드" 취급으로 남겨뒀던
잔재. 반면 `RCWSComponent.cpp`의 `SightCamera`는 애초에 이런 걸 전혀 안 건드리고(주석: "Unlike
QuadCam/UAV/Minimap, this is treated as close to a main gameplay view... keeps full rendering
quality") 풀 품질을 유지함. Lumen GI/리플렉션이 다 꺼지면 간접광(바운스 라이팅)이 없어져서
오토익스포저가 전체를 밝게 보정하고, 그 상태에서 직사광 스페큘러만 남아 나뭇잎 등에서 흰색으로
날아가 보이고, 그림자도 Lumen의 소프트 보정 없이 raw 래스터 그림자만 남아 더 지글거림.

**해결**: 저 4줄 삭제(→ RCWS와 동일하게 Lumen GI/리플렉션 전부 프로젝트 기본값 그대로 씀).
`SetTemporalAA(true)`/`SetMotionBlur(false)`만 유지.

**추가로 확인/적용한 것**: Lumen 서페이스 캐시 해상도가 **씬캡쳐에서만** 기본 0.5(절반 해상도)로
떨어지는 엔진 동작을 발견(`SceneCaptureRendering.cpp`, 프로퍼티 주석: "Defaults to 0.5 for Scene
Captures if not overridden"). `SyncLensFromCineCamera()`(RCWS/UAV 둘 다)에서 매틱
`PostProcessSettings.bOverride_LumenSurfaceCacheResolution=true; LumenSurfaceCacheResolution=1.f;`
강제하도록 추가 — **다만 이건 6절의 색감/밝기 문제 해결엔 효과가 없었음**(테스트로 확인됨). 그래도
이론적으로는 더 정확한 설정이라 코드에 남겨둠(해가 되진 않음).

---

## 6단계 — 씬캡쳐 vs 실제렌더링 색감/밝기 불일치 (미해결, 보류)

**증상**: 4~5단계 수정 후에도, TitanTruck RCWS/UAV 화면이 UGV RCWS(실제 렌더링)보다 색이 진하고
(나뭇잎이 더 진한 초록), 그림자가 더 어둡고, 디테일이 살짝 무뎌 보임. 렌더타겟 크기와 WBP Image
크기는 이미 맞춰져 있어 단순 업스케일 흐림이 아님.

### 조사해서 배제한 것들 (효과 없음 확인됨)
- **`CaptureSource` 선택**: `SCS_FinalColorLDR`(최종 톤매핑+감마 적용된 색) 확인 결과 올바른
  선택이었음 — `SceneColor*` 계열은 후처리 전 raw HDR이라 완전히 다른 그림이 나오고,
  `FinalColorHDR`/`FinalToneCurveHDR`은 리니어 색공간이라 8비트 렌더타겟과 안 맞음. 커뮤니티에서도
  이 증상의 표준 해결책으로 확인된 설정.
- **렌더타겟 sRGB 플래그**: `RenderTargetFormat`을 `RTF_RGBA8` → `RTF_RGBA8_SRGB`로 변경 +
  `SRGB=true` 원시 프로퍼티도 명시적으로 세팅(엔진 소스 확인: `IsSRGB()`가 계산하는 값과 별개로
  `UTexture::SRGB` 원시 프로퍼티가 따로 존재하고 기본값 `false` — Slate가 이걸 직접 참조할 수도
  있어서 둘 다 맞춤). **테스트 결과 전혀 변화 없음.**
- **Lumen 서페이스 캐시 해상도**: 위 5단계에서 1.0으로 강제. **효과 없음.**
- **CineCamera별 PostProcessSettings 값 차이**: UGV/TitanTruck의 `RCWSSightCineCamera` 라이브
  프로퍼티를 직접 비교(unreal-mcp) — 둘 다 `bOverride_DynamicGlobalIlluminationMethod`(Lumen
  켜는 것) 하나만 오버라이드되어 있고 나머지(색보정/노출 등)는 전부 꺼져있음 → **인스턴스별 설정
  차이가 원인이 아님.**
- **PostProcessVolume이 씬캡쳐에 영향을 안 준다는 가설**: 처음엔 "월드 PPV 블렌딩은
  `APlayerCameraManager`가 메인 카메라에만 해주고 씬캡쳐는 못 받는다"고 추정했으나, **사용자가
  실측으로 반박함** — PPV의 EV100 Min/Max를 토글하면 씬캡쳐 화면도 실제로 바뀜. 이 가설은 폐기.

### 유력한 실제 원인 (사용자가 직접 찾음, 미적용)
레벨의 라이팅 세팅 자체가 정상 범위를 벗어나 있음:
- `HDRIBackdrop`의 Intensity = **150** (정상은 1.0 근처)
- 그 자식 `Skylight`의 Intensity = **900**
- 레벨에 배치된 `PostProcessVolume`이 `EV100 Min = Max = 10`으로 강제 고정해서 위 비정상적으로
  강한 빛을 억눌러 "보기엔 정상"으로 상쇄시켜둔 상태.

이게 "구름에 햇빛이 가려 direct light는 약하고 Lumen 간접광 위주로 보이는" 흐린 날씨를 표현하려던
의도로 보이나, **광원 세기를 비정상적으로 올리고 노출로 억누르는 방식은 그 순간 딱 하나의 뷰에서만
우연히 균형 잡히는 불안정한 세팅**임. Lumen GI/리플렉션은 뷰마다 독립적으로 계산되므로(지속형
캡처마다 자기만의 Lumen Scene 사본을 따로 유지 — 이전 세션에서 확인됨), 광원이 정상 범위보다
100배 이상 벗어나 있으면 두 개의 독립된 렌더 패스가 계산하는 아주 작은 차이도 톤매퍼/블룸 임계값
근처에서 크게 증폭됨. 정상 값이었다면 무시할 오차가, 이 극단적인 값에서는 눈에 띄게 벌어지는 것 —
사용자가 EV100 고정을 풀고 HDRI/Skylight 세기를 정상으로 되돌리자 씬캡쳐와 실제 렌더링이 거의
완전히 일치했다는 실측 결과가 이 설명과 정확히 부합함.

**권장 조치 (미적용)**: `HDRIBackdrop`/`Skylight` Intensity를 정상값(1.0 근처)으로 되돌리고,
`PostProcessVolume`의 극단적인 EV100 고정을 풀거나 훨씬 완만한 범위로 변경. 원하는 흐린 날씨
룩은 **광원 세기 조작이 아니라** DirectionalLight 세기/색을 낮추고(구름 통과한 햇빛은 원래 약함)
하늘 콘텐츠(Volumetric Cloud 밀도/커버리지, HDRI 자체)로 표현하는 게 물리적으로 올바르고 다른
뷰(씬캡쳐 등)에서도 안정적임.

**상태**: 사용자가 나중에 처리하기로 하고 **보류**. 코드 쪽에서 할 수 있는 건 다 확인/시도했고
(sRGB 포맷, Lumen 서페이스캐시), 남은 건 레벨 콘텐츠(라이팅) 조정이라 이번 범위에서 제외.

---

## 최종 코드 상태 요약 (2026-07-23 기준)

- **`Vehicles/RCWSComponent.h/.cpp`**: `PrimaryViewCamera` 패턴 확정 유지(UGV+TitanTruck 둘 다
  이 클래스 공유). `SetSightAspectRatio()`, `SyncLensFromCineCamera()`에 `SetTemporalAA(true)` +
  `LumenSurfaceCacheResolution=1.0` 강제 포함. `SightRenderTarget`은 `RTF_RGBA8_SRGB`+`SRGB=true`.
- **`Vehicles/UAVPawn.h/.cpp`**: `PrimaryViewCamera` 패턴은 **없음**(3단계 롤백으로 제거됨) —
  여전히 순수 씬캡쳐. `BeginPlay()`의 Lumen GI/리플렉션 강제 비활성화 4줄 제거됨.
  `SyncLensFromCineCamera()`에 `SetTemporalAA(true)` + `LumenSurfaceCacheResolution=1.0` 강제
  포함. `CameraRenderTarget`도 `RTF_RGBA8_SRGB`+`SRGB=true`.
- **`titan_examplePlayerController.h/.cpp`**: `bDisableWorldRenderingOnStart=false` 확정.
  `BeginPlay()`엔 UGV `SetViewTarget()` 호출 하나만 있음(TitanTruck/UAV용 `CreateLocalPlayer`
  코드는 3단계 롤백으로 없음). `SyncRCWSViewportRect()`/`ApplyLocalPlayerViewportRect()` 존재.
- **`titan_exampleViewportClient.h/.cpp`**: `LayoutPlayers()`는 "로컬 플레이어 1명일 때만 스킵"
  형태(3단계에서 일반화했다가 롤백으로 원상복구).
- **`UI/Monitor1Widget.cpp`**: `RCWSViewImage`만 `HitTestInvisible`+opacity 0 처리(실제 렌더링용).
  `MainViewImage`/`UAVCameraImage`는 `SetImageRenderTarget()`으로 씬캡쳐 렌더타겟 바인딩(원래
  방식). `ResolveActiveRCWS()`는 트럭 분기 없이 항상 UGV.
- **`CameraOnlyPlayerController.h/.cpp`**: 파일 자체가 존재하지 않음(3단계 롤백으로 삭제됨).
- **QuadCamComponent**: 이번 작업 범위에서 전혀 안 건드림 — 저해상도/노이즈 있는 CCTV 룩 그대로
  유지(사용자 의도).
- **레벨 라이팅**(`HDRIBackdrop` Intensity=150, `Skylight` Intensity=900, `PostProcessVolume`
  EV100 Min/Max=10 고정): **아직 그대로 남아있음** — 6단계 권장 조치 미적용 상태.
