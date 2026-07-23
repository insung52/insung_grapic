# RCWS Lumen 버벅임 → 원인 확정 → RCWS 실제 월드 렌더링 전환까지 (해결 완료)

> `titan_example` 프로젝트. UGV RCWS의 CineCamera에 Lumen GI를 켜면 PIE 중 **버벅임이 점점 길어지는
> 버그**를 조사하다가, 근본 해결책으로 **RCWS 조준 화면을 씬캡쳐 사본이 아니라 실제 메인 월드
> 렌더링으로 교체**하는 작업까지 진행해서 **2026-07-22 완료**됨. 이 문서는 전체 과정(원인 조사 →
> 확정 → 재설계 → 구현 중 만난 3개의 서브 버그 → 최종 해결)을 기록.

---

## 요약 (TL;DR)

1. **버그 증상**: RCWS Lumen 캡쳐 활성화 시, PIE 중 "정상 작동 구간 ↔ 완전 정지 구간"이 번갈아
   나타나고 그 주기가 점점 길어지는 버벅임.
2. **원인**: `GameViewportClient::bDisableWorldRendering = true`(메인 뷰포트 3D 렌더링을 통째로
   끔) + Lumen을 쓰는 지속형(persistent) 씬캡쳐가 동시에 존재하면 발생. 원래 이 프로젝트는 메인
   뷰포트를 화면에 안 쓰고(대시보드가 각 카메라의 씬캡쳐만 보여줌) FPS 절약 목적으로 껐었는데,
   이게 Lumen 서페이스 캐시 갱신 페이싱을 망가뜨림.
3. **해결책**: 안 쓰던 메인 뷰포트 렌더링을 "낭비"로 끄는 대신, 가장 크고 중요한 RCWS 조준
   화면에 **실제로 활용**하는 쪽으로 재설계 — `ULocalPlayer::Origin`/`Size`(스플릿스크린이 쓰는
   서브렉트 지정 메커니즘)로 화면의 정확히 그 자리에만 메인 카메라가 실제 렌더링되게 하고, 메인
   뷰포트가 상시 켜져있으니 Lumen 버벅임도 자연히 해소됨. 나머지 씬캡쳐(UAV/미니맵/쿼드캠)는
   그대로 유지.
4. **부수 작업**: UAV의 `GimbalCamera`가 UGV/TitanTruck과 달리 BP 에디터에 노출되어 있던 문제도
   같은 세션에서 원인 규명 후 정리.

---

## 1. 증상 (조사 시작 시점)

- UGV(`BP_UGV_Vehicle`)의 RCWS 시네마틱 카메라(`RCWSSightCineCamera`)에서 Lumen Global
  Illumination을 켜는 순간부터 발생. 꺼져있으면 문제없음.
- 패턴이 **일반적인 "무거워서 fps 떨어짐"이 아니라, 정상 작동 구간과 완전 정지 구간이 번갈아
  나타나고 그 주기가 시간이 갈수록 커짐** (몇 초 뒤엔 10초 이상 멈추기도 함).
- **씬 내용(콘텐츠 복잡도)과 무관** — 나무/텍스처 하나 없는 빈 레벨에서도 재현됨(속도만 느림).

## 2. 확정된 원인

**`GameViewportClient::bDisableWorldRendering = true` + Lumen GI를 쓰는 지속형 씬캡쳐가 동시에
존재하면 발생.**

- `Atitan_examplePlayerController::BeginPlay()`가 `bDisableWorldRenderingOnStart`(기본값
  `true`)일 때 `SetWorldRenderingEnabled(false)` → `Viewport->bDisableWorldRendering = true`를
  호출. 원래 이유: "메인 뷰포트는 화면에 안 쓰이니(대시보드가 씬캡쳐만 보여줌) FPS 절약 목적으로
  꺼둠".
- **검증**: `bDisableWorldRenderingOnStart`를 `false`로 바꾸고 나머지는 전혀 안 건드린 채
  PIE → 버벅임 완전히 사라짐. 그 상태에서 콘솔 명령어로 월드 렌더링을 껐다 켰다 하면서 **그
  자리에서 버벅임이 나타났다 사라졌다 하는 걸 실시간으로 확인** — 상관관계가 아니라 인과관계로
  증명됨.
- **메커니즘 추정** (엔진 소스로 100% 확정은 못 함): Lumen의 서페이스 캐시/글로벌 디스턴스 필드
  갱신은 프레임마다 정해진 예산 안에서 점진적으로 처리되도록 설계되어 있는데, 이 페이싱이 "메인
  뷰가 실제로 매 프레임 렌더링되고 있다"는 걸 어느 정도 전제로 하는 것으로 보임. 메인 뷰가 아예
  안 그려지면 갱신이 계속 밀리다가 한꺼번에 몰아서 처리(blocking flush)하는 방식으로 보정되는
  듯 — "정상 구간이 점점 짧아지고 멈춤 구간이 점점 길어지는" 패턴과 정확히 일치.

배제한 가설들(더 이상 의심 안 해도 됨): PostProcessVolume의 Lumen 차단, RCWS 노출(EV100) 불안정,
`SyncLensFromCineCamera()`의 매 틱 PostProcessSettings 재할당, 텍스쳐 스트리밍 풀 크기, 씬
콘텐츠(숲/텍스처) 무게, 물리 시뮬레이션 카메라 흔들림, RCWSComponent 자체 코드, Monitor1Widget의
Tick 로직 전부, UMG Property Binding, `AddLumenSceneData()`의 Lumen Scene 복제 메커니즘 자체(이건
실재하지만 직접 원인은 아님).

---

## 3. 최종 해결책 — RCWS를 실제 월드 렌더링으로 전환

`bDisableWorldRenderingOnStart`를 그냥 껐다 켰다 하는 미봉책 대신, **UGV RCWS 조준 화면
(`RCWSViewImage`, 대시보드에서 가장 크고 중요한 패널)을 씬캡쳐 사본이 아니라 진짜 메인 월드
렌더링으로 교체**하는 재설계로 근본 해결. 메인 뷰포트가 상시 "실제로 쓰이는" 상태가 되니 Lumen
버벅임 원인 자체가 사라지고, 렌더링 자원 낭비도 없어짐. 트럭 RCWS 등 나머지 씬캡쳐는 그대로 유지
(사용자 확정: RCWS 실제 렌더링은 카메라 컨트롤 타겟과 무관하게 항상 UGV 고정).

### 3.1 핵심 메커니즘 — `ULocalPlayer::Origin`/`Size` 서브렉트

Unreal 스플릿스크린이 내부적으로 쓰는 정규화(0~1) 서브렉트 지정 필드를 로컬 플레이어 1명에게
그대로 적용 — 두 번째 플레이어 없이, 화면의 특정 픽셀 사각형(=`RCWSViewImage`가 화면에서 차지하는
자리) 안에만 실제 3D 렌더링이 나오고 나머지는 검은색으로 남는다. 매 프레임 `RCWSViewImage`의 실제
지오메트리를 읽어서 계산하므로(3840×1080 같은 디자인 해상도를 하드코딩하지 않음) 런타임
해상도/DPI 스케일이 디자인과 달라도 항상 정확히 따라감.

### 3.2 구현 (파일별)

**`Vehicles/RCWSComponent.h/.cpp`**
- 기존 `SightCamera`(`USceneCaptureComponent2D`, 조준 상태의 진짜 소유자 — pan/tilt/zoom이 전부
  여기 반영됨)는 그대로 유지, 여전히 레티클/탐지박스 UV 계산(`ProjectWorldPointToCameraUV`)에
  쓰임.
- 새 `UCameraComponent* PrimaryViewCamera` 추가 — **`SightCamera`의 자식으로 부착**해서 위치/
  회전이 자동으로 항상 `SightCamera`와 동일(마운트 유무와 무관하게 매 틱 동기화 코드 불필요).
  FOV/PostProcessSettings만 매 틱 `SightCamera`에서 복사. 진짜 CineCamera(`RCWSSightCineCamera`)는
  건드리지 않되 `SetActive(false)`로 비활성화(안 그러면 `AActor::CalcCamera`가 먼저 찾아서 씀).
  `UCineCameraComponent`가 아니라 일반 `UCameraComponent`를 쓴 이유: CineCamera는 FOV를 초점거리
  에서 매 프레임 재계산하므로 직접 FOV를 세팅하는 이 용도엔 안 맞음.
- `SetSightAspectRatio(float)` 신규 함수 — `SightCamera`의 렌더타겟 종횡비를 실제 화면 사각형에
  맞춤(레티클 UV 계산이 이 종횡비를 쓰므로, 실제 표시 비율과 안 맞으면 레티클이 어긋남).
  `UTextureRenderTarget2D::ResizeTarget()`은 크기가 같으면 no-op이라 매 프레임 호출해도 안전.

**`titan_examplePlayerController.h/.cpp`**
- `bDisableWorldRenderingOnStart` 기본값 `true → false`로 영구 확정.
- `BeginPlay()`에서 `FindUGVRCWS()->GetOwner()`로 UGV를 찾아 `SetViewTarget()` 고정(카메라
  컨트롤 타겟/Possess와 무관하게 항상 UGV RCWS를 봄).
- `SyncRCWSViewportRect(PixelPos, PixelSize, FullViewportPixelSize)` 신규 함수 — 픽셀 좌표를
  받아 `ULocalPlayer::Origin`/`Size`(정규화 비율)로 변환 적용.

**`UI/Monitor1Widget.cpp`**
- `ResolveActiveRCWS()`에서 트럭 분기 제거 → 항상 UGV RCWS로 귀결(리본/레티클/탐지오버레이/영상
  전부 이 함수 하나로 통일되어 일관되게 UGV 고정).
- `RefreshRCWSPanel()`의 `SetImageRenderTarget(RCWSViewImage, ...)` 호출 삭제(더 이상 렌더타겟
  안 씀).
- `BindCameraImages()`에서 `RCWSViewImage`를 `HitTestInvisible` + `RenderOpacity=0`으로 설정
  (아래 3.3의 이유로 `Hidden`은 안 됨).
- 기존에 있던, 매 프레임 도는 레티클 갱신 블록에 `RCWSViewImage`의 절대좌표→뷰포트 픽셀 변환
  (`USlateBlueprintLibrary::AbsoluteToViewport`) + `RCWS->SetSightAspectRatio()` +
  `PC->SyncRCWSViewportRect()` 호출 추가.

**`titan_exampleViewportClient.h/.cpp`** (기존 듀얼모니터 창 배치용 커스텀 뷰포트 클라이언트)
- `LayoutPlayers()` 오버라이드 추가 — 아래 3.3의 세 번째 버그 참고.

### 3.3 구현 중 만난 서브 버그 3개 (전부 실제로 겪고 해결한 것 — 재발 시 참고용)

1. **`ESlateVisibility::Hidden`이 `GetCachedGeometry()`를 영구히 (0,0)으로 고정시킴.**
   처음엔 `RCWSViewImage`를 `Hidden`으로 설정했는데, 이 프로젝트의 페인트 경로에서는 `Hidden`
   위젯이 `Collapsed`처럼 취급되어 지오메트리 캐시가 아예 갱신 안 됨(라이브 로깅으로
   `RawLocalSize=(0,0)` 확정). **`HitTestInvisible` + `SetRenderOpacity(0.f)`로 교체**해서
   해결 — 정상적으로 페인트 경로를 타되(지오메트리 캐시 정상 갱신) 화면엔 안 보이게.
2. **`FGeometry::LocalToAbsolute()`의 절대좌표는 데스크톱 좌표지 뷰포트 픽셀이 아님.**
   `titan_exampleViewportClient`가 듀얼모니터 가상 데스크톱 좌상단(자주 (0,0)이 아님) 기준으로
   창을 배치하므로, 절대좌표를 그대로 픽셀로 쓰면 창 오프셋만큼 어긋남. **반드시
   `USlateBlueprintLibrary::AbsoluteToViewport()`로 변환**해야 함(DPI 스케일도 같이 처리해줌).
3. **`UGameViewportClient::LayoutPlayers()`가 매 프레임 `Draw()` 직전에 로컬 플레이어 1명을
   "None" 스플릿스크린 타입으로 취급해서 `Origin`/`Size`를 (0,0)/(1,1)로 강제 리셋함.**
   가장 오래 걸린 버그 — `SyncRCWSViewportRect()`가 매 프레임 정확한 값을 계산해서 쓰는 것까지
   라이브 로그로 확인했는데도(`LP->Origin=(0.4960,0.0935) LP->Size=(0.3085,0.8592)` 등 정상값)
   실제 렌더링은 계속 풀스크린이었음 — 그 직후 엔진이 매 프레임 자체적으로 되돌리고 있었기
   때문. 웹 검색으로 "`LayoutPlayers()`는 `Draw()` 직전에 매 프레임 실행되고 현재 스플릿스크린
   타입 기준으로 리레이아웃한다"는 걸 확인 후, `titan_exampleViewportClient`에서
   `LayoutPlayers()`를 오버라이드해서 **로컬 플레이어가 1명일 땐 그냥 스킵**하도록 해서 해결
   (2명 이상이면 `Super::LayoutPlayers()` 정상 호출, 미래에 실제 스플릿스크린 쓸 경우 대비).

### 3.4 검증 완료
사용자 확인: PIE에서 `RCWSViewImage` 자리에 실제 3D 렌더링이 정확히 그 사각형 안에만 나오고,
조이스틱 pan/tilt/zoom도 정상 추적되고, Lumen 버벅임도 재현 안 됨.

---

## 4. 부수 작업 — UAV `GimbalCamera`의 BP 에디터 노출 문제

같은 세션에서 발견/해결한 별개 이슈. UGV/TitanTruck은 씬캡쳐 컴포넌트가 BP 에디터에 안 뜨는데
UAV만 `GimbalCamera`(`USceneCaptureComponent2D`)가 BP_UAV 에디터에 "C++에서 편집 가능"으로 표시,
삭제/잘라내기 회색 처리되어 안 지워지는 문제.

**원인**: `UAVPawn.h`의 `ResolvedGimbalCineCamera` 필드 주석에 이미 답이 적혀 있었음 — BP_UAV는
`AUAVPawn`의 블루프린트 서브클래스라서, **네이티브 UPROPERTY 이름이 블루프린트에 배치된 SCS
컴포넌트 이름과 정확히 같으면 그 SCS 노드가 "네이티브에 바인딩됨"으로 잠김**(그래서
`GimbalCineCameraRef`가 대상 컴포넌트 이름 "GimbalCineCamera"와 다르게
`ResolvedGimbalCineCamera`로 지어짐). `RCWSComponent::SightCamera`/`QuadCamComponent`의
Front/Rear/Left/RightCamera는 전부 `private`+`UPROPERTY(Transient)`(에디터/블루프린트에 전혀 안
보임)라서 애초에 이 충돌 검사 대상이 아니었는데, `GimbalCamera`만 `public`+`VisibleAnywhere`+
`BlueprintReadOnly`로 노출되어 있었던 게 원인 — 2026-07-21에 `CreateDefaultSubobject`를 안 쓰는
방식으로 바꾸면서 이 부분만 놓친 것으로 보임(블루프린트 쪽에 예전에 수동으로 추가됐던 동명의
SCS 컴포넌트가 잔재로 남아있던 상태였음).

**해결**: `GimbalCamera`를 `private`+`UPROPERTY(Transient)`로 이동(다른 씬캡쳐들과 동일 패턴),
외부 접근용 `GetGimbalCamera()` 접근자 추가, `Monitor1Widget.cpp`의 직접 접근 2곳을 접근자
호출로 교체. 빌드 후 BP_UAV 에디터에서 잔재 컴포넌트 정상 삭제됨.

---

## 5. 현재 코드 상태 (2026-07-22, 최종)

- `titan_example/Source/titan_example/Vehicles/RCWSComponent.h/.cpp` — `PrimaryViewCamera` +
  `SetSightAspectRatio()` 추가됨(3.2절). 프로덕션 코드로 확정.
- `titan_example/Source/titan_example/titan_examplePlayerController.h/.cpp` —
  `bDisableWorldRenderingOnStart` 기본값 `false`로 영구 확정. `SetViewTarget`/
  `SyncRCWSViewportRect` 추가됨.
- `titan_example/Source/titan_example/UI/Monitor1Widget.cpp` — RCWS 관련 로직 3.2절대로 수정
  완료. 디버깅용으로 추가했던 `[RCWSRectDbg]` 임시 로그는 문제 해결 후 전부 제거됨.
  `ResolveActiveRCWS()`는 이제 트럭 분기 없이 항상 UGV.
- `titan_example/Source/titan_example/titan_exampleViewportClient.h/.cpp` — `LayoutPlayers()`
  오버라이드 추가됨(3.3절 3번 버그).
  `titan_example/Source/titan_example/Vehicles/UAVPawn.h/.cpp` — `GimbalCamera` private화 +
  `GetGimbalCamera()` 접근자(4절).
- `titan_example/Source/titan_example/TestSceneCapture.h/.cpp`,
  `TestCaptureWidget.h/.cpp` — 이전 세션 조사용으로 만든 독립 테스트 클래스. 이제 원인/해결책
  둘 다 확정됐으니 **더 이상 필요 없음 — 삭제해도 됨**(재사용 가치 낮음, RCWSComponent를 직접
  안 건드리는 격리된 코드라 삭제해도 프로덕션에 영향 없음).
- `/Game/test` 레벨(평면+라이트만 있는 미니멀 테스트 레벨) — 조사용으로 만들었던 것, 더 이상
  필요 없음. `WorldSettings.DefaultGameMode` 오버라이드나 `GameDefaultMap` 설정이 이 레벨을
  가리키고 있었다면 원래 시작 맵으로 되돌려놨는지 확인 권장(이전 세션에서 발견한 이슈, 이번에
  재확인 안 함).
- `BP_UGV_Vehicle`의 `RCWSSightCineCamera` — Lumen GI/Reflections + 품질 스칼라 오버라이드는
  그대로 켜진 상태 유지(이제 안전 — 버그 원인이 해결됐으므로).
