# RTSP 해상도 커스터마이징 + 메인뷰 단일 렌더링 (2026-08-20)

**상태: 동작 확인됨(2026-08-20 사용자 실측) — §8 참고.**

UGV축 RTSP 송출 해상도를 "대시보드 WBP가 화면에 몇 픽셀로 보이나"가 아니라 "축 선택 화면에서
입력한 고정값"이 결정하도록 바꾸고, 그 과정에서 발견한 CCTV 잘림 버그와 RCWS 이중 렌더링을
같이 해결한 작업. 자체방호축은 **검증만 하고 코드는 안 건드림**(사용자 확정).

## TL;DR

- **CCTV 잘림 버그 원인 확정**: 인코더 해상도는 BeginPlay에 1회 고정되는데 RenderTarget은
  대시보드가 매 틱 화면 크기로 리사이즈 → D3D12 `CopyResource` 크기 불일치. 로그 실측으로 확정.
- **"창 크기 따라 RTSP 해상도가 바뀐다"는 전제는 성립한 적이 없음** — 양쪽 축 모두. 자체방호축도
  같은 손상을 이미 갖고 있음(§3).
- **RCWS는 같은 그림을 두 번 렌더하고 있었음** — 메인 뷰포트 + 씬 캡쳐. 씬 캡쳐 픽셀의 소비자는
  RTSP 하나뿐이었음. 메인 뷰 결과를 카피하는 방식으로 전환(§5, B2안).
- 해상도/fps는 `UStreamResolutionSubsystem`(GameInstance) 한 곳에서 결정.

---

## 1. 전제 정리 — RCWS는 카메라가 두 개다

사용자 설명("RCWS 메인 뷰는 언리얼 기본 뷰포트 렌더링을 WBP Image 자리에 붙인 것")과
`rtsp_integration_complete_0817.md` §1(“`GetSightCamera()`가 `USceneCaptureComponent2D`를 반환,
그걸 RTSP에 연결”)이 모순돼 보였는데, **둘 다 맞다**:

| | 컴포넌트 | 렌더 대상 | 용도 |
|---|---|---|---|
| 화면 | `RCWSPrimaryViewCamera` (`UCameraComponent`) | **메인 뷰포트** | `ULocalPlayer::Origin/Size` 서브렉트로 WBP `MainViewImage` 슬롯에 맞춰 렌더(`SyncRCWSViewportRect`) |
| RTSP | `RCWSSightCamera` (`USceneCaptureComponent2D`) | `RT_RCWS_Sight` | 탐지/조준 UV 계산용 + RTSP |

`RCWSComponent.h:253` 주석에 명시: *"SightCamera는 SceneCapture라 화면엔 안 나감"*.

메인 렌더링을 못 끄는 이유도 코드에 기록돼 있다 — `titan_examplePlayerController.h`의
`bDisableWorldRenderingOnStart` 주석(2026-07-22): *"bDisableWorldRendering=true + Lumen GI 켜진
상시 scene capture → PIE 프리즈가 점점 길어지는 버그"*. 영구 false.

---

## 2. CCTV 잘림 버그 — 원인 확정

`URtspStreamComponent::SetupEncoderAndStream()`이 소스 RenderTarget의 `SizeX/SizeY`를 **BeginPlay에
딱 한 번** 읽어 NVENC 세션과 RTSP SDP 해상도를 확정한다. 이후 절대 재확인하지 않는다.

그런데 대시보드 위젯이 같은 RenderTarget을 매 틱 화면 Image 위젯의 픽셀 크기로 `ResizeTarget()`
한다(`UGVTestDashboardWidget::RefreshQuadCamResolution` → `UQuadCamComponent::SetRenderTargetPixelSize`).

그리고 `FNvencD3D12Encoder::EncodeFrame`의 `NativeCmdList->CopyResource(DstResource, SrcResource)`에는
**크기 검사가 전혀 없었다.** D3D12 `CopyResource`는 소스/대상의 크기·포맷이 같아야 유효하고,
불일치는 스펙 위반(드라이버 정의 동작)이라 디버그 레이어 없이는 아무 에러도 안 난다.

### 실측 (`Saved/Logs/titan_example.log`, 2026-08-20 세션)

전부 프레임 189 안에서:

```
:495  Client_OnAxisResolved: created dashboard widget WBP_UGVTestDashboard_C
:614  VehicleRtspBridgeComponent: WireRtspStreams running     ← 위젯 tick/paint 0회
:615  Registered 'ugv/front_cctv' (240x135 @ 30 fps)          ← QuadCam RenderTargetSize C++ 기본값
:955  Registered 'ugv/rcws'       (1226x928 @ 60 fps)         ← BP 저작값
```

위젯이 한 번도 페인트되지 않아 `GetCachedGeometry()`가 0을 반환 → 리사이즈가 아직 안 걸린 상태.
즉 **등록 해상도는 항상 "저작값"**이고, 다음 프레임부터 위젯이 화면 크기로 바꿔 **영구 불일치**.

8/18~8/20 여러 세션(창 크기 제각각)에서 `ugv/rcws`가 예외 없이 1226×928로 기록된 것이 결정적
증거다.

**CCTV가 유독 심한 이유**(추론): CCTV는 폭·높이가 다 바뀌지만, RCWS는 `SetSightAspectRatio`가
높이만 바꾸고 폭은 고정이라 행 피치가 유지돼 손상이 덜 드러난다. 사용자가 관찰한
"주로 오른쪽 CCTV 4분할이 이상하게 잘림"과 일치.

---

## 3. 자체방호축 검증 결과 — 가설과 다름 (수정 안 함)

```
selfdefense/env_camera  640x360     selfdefense/rcws       1116x622
selfdefense/front_cctv  240x135     selfdefense/uav_gimbal 640x360
selfdefense/{rear,left,right}_cctv  240x135
```

전부 저작값 고정. **RTSP 송출 해상도는 창 크기를 따라가지 않는다** — `SetupEncoderAndStream`이
BeginPlay 1회성이라 구조적으로 불가능하다. "GPU 카피 기반이라 렌더 크기를 따라갈 것"이라는
가설은 성립하지 않는다.

그리고 자체방호축도 `SelfDefenseMonitor1Widget`이 QuadCam/전장카메라/UAV RenderTarget을 매 틱
화면 크기로 리사이즈하므로 **UGV축과 똑같은 손상을 이미 갖고 있다**(폭까지 바뀌는 심한 쪽).

→ 사용자 지시대로 코드 수정 없음. **UGV축 완료 후 별도 작업**으로 진행하기로 함.

---

## 4. "창 크기 따라 유동 해상도" 기능

RTSP엔 전혀 반영되지 않았다. 원래 목적은 화면 표시 품질(near-1:1 리샘플 블러 제거)이고,
지금은 RTSP를 깨뜨리는 부작용만 낸다. 고정 해상도 기능과 충돌하는 지점은 **RenderTarget 하나를
화면과 RTSP가 공유한다는 것** 하나뿐.

---

## 5. RCWS 이중 렌더링 — 발견과 해결(B2안)

`RCWSComponent.cpp:186~188`에서 `PrimaryViewCamera`는 `SightCamera`의 **자식**이고
`SetRelativeTransform(Identity)`. `:264~268`에서 매 틱 `FieldOfView`/`PostProcessSettings`를 통째로
복사. 즉 **같은 시점·같은 렌즈·같은 포스트프로세스를 두 번 풀 렌더링**하고 있었다(메인 뷰는 매
프레임, 씬 캡쳐는 `CaptureRoundRobinCount`틱마다 1회, Lumen/TAA 전부 켜진 풀 퀄리티).

그리고 `SightRenderTarget`의 **픽셀을 읽는 소비자는 RTSP 하나뿐**이었다 — 이걸 화면에 그리던
`Monitor1Widget`/`Monitor2Widget`/`MissionDashboardWidget`은 전부 legacy(`Client_OnAxisResolved`가
생성하지 않음).

### 채택안 (B2): 메인 뷰포트 렌더 결과를 고정 해상도로 카피

- 렌더 해상도 고정 — 창(=백버퍼) 자체를 그 해상도로 맞춘다(`UGameUserSettings`).
  ⚠️ `FSceneViewport::SetFixedViewportSize`는 **쓰지 않는다** — 크래시 원인이었다, §5-1 참고.
- `ISceneViewExtension::SubscribeToPostProcessingPass(EPostProcessingPass::Tonemap)`으로 톤맵 직후
  씬 컬러를 그 고정 해상도 RenderTarget으로 블릿(`AddDrawTexturePass`).
- `URtspStreamComponent::SourceRenderTarget`(신규)로 그 RenderTarget을 직접 소스로.
- `URCWSComponent::bDisableSightCapture`(신규)로 씬 캡쳐를 끔.

**얻은 것**
- 프레임당 풀 Lumen 렌더 하나 제거.
- 화질 향상 — 메인 뷰의 TSR/TAA 히스토리와 ScreenPercentage가 그대로 반영된다. `SCS_FinalColorLDR`
  씬 캡쳐는 그 히스토리를 가진 적이 없다.
- **SSR/반사와 피격 카메라 셰이크가 자동으로 정상화** — `rtsp_postprocess_parity_0820.md`가 밝힌
  두 원인(엔진이 씬 캡쳐에만 `ReflectionMethod=None` 강제 / 셰이크는 `PlayerCameraManager`에만
  걸림)이 둘 다 "씬 캡쳐이기 때문"이라, 씬 캡쳐를 안 쓰면 애초에 발생하지 않는다.
- UMG가 스트림에 안 섞인다 — 카피가 Slate 합성 **이전**인 톤맵 패스에서 일어나기 때문.
  (백버퍼 카피 방식이었다면 대시보드가 그대로 찍혔을 것.)

**대가 (설계상 불가피)**
- 메인 뷰포트가 실제로 렌더+Present를 계속해야 프레임이 나온다. **창 최소화 = 스트림 정지.**
  → UGV SW는 작은 보더리스 창이라도 계속 띄워야 한다(사용자 확정).
- `rtsp_poc_findings.md` §1.14의 백그라운드 스로틀링이 패키지 빌드에도 있는지는 **여전히 미검증**.
  창을 띄워두는 구성이라 위험은 줄지만, 포커스 없는 상태에서의 실측은 남아 있다.

### 5-1. 크래시 두 번 — 원인과 최종 형태 (2026-08-20, 사용자 실측)

`SetFixedViewportSize`로 렌더 해상도를 고정하려던 시도가 두 번 크래시를 냈고, 결국 **다른
메커니즘**으로 갈아탔다. 두 크래시는 원인이 서로 다르다.

#### 크래시 1 — SetFixedViewportSize가 뷰포트/백버퍼를 어긋나게 함

```
Dest height out of bounds for: 'BackBuffer0' <- 'Tonemap', [1920,1009] <- copying [1920,1080]
```

표준 게임 창의 뷰포트 위젯은 `RenderDirectlyToWindow=true`로 생성된다(`GameEngine.cpp:215~222`)
→ `FSceneViewport::bUseSeparateRenderTarget`이 **생성자에서** false로 굳고(`SceneViewport.cpp:76`,
런타임 세터 없음) 씬이 창 백버퍼에 직접 렌더된다. 여기에 `SetFixedViewportSize`를 걸면 뷰포트만
1920×1080에 고정되고 백버퍼는 창을 따라 계속 리사이즈되므로 어긋난다. PIE는 뷰포트가 에디터 UI
안이라 `RenderDirectlyToWindow=false`(별도 RT) → 안 죽는다. **"PIE는 OK / standalone은 크래시"가
정확히 이 차이.**

1차 수정: 별도 RT를 쓰는 뷰포트에서만 `SetFixedViewportSize`, 아니면 창 자체를 Resolution으로.

#### 크래시 2 — 이 확장이 삽입한 백버퍼 카피가 스케일을 못 함 (진짜 근본 원인)

```
Dest width out of bounds for: 'BackBuffer0' <- 'Tonemap', [1703,1080] <- copying [1920,1080]
```

1차 수정이 들어간 빌드에서도 창을 드래그하면 죽었다(로그에 `Window resolution set to 1920x1080`이
찍힌 것으로 확인). 원인은 `SetFixedViewportSize`가 아니라 **이 확장 자체**였다:

`SubscribeToPostProcessingPass(Tonemap)`으로 콜백을 달면 톤매퍼가 더 이상 체인의 마지막이 아니게
되어 자기 출력을 별도 텍스처(`'Tonemap'`)에 쓰고, 대신 **우리 패스가 `OverrideOutput`(=백버퍼)을
받는다.** 그런데 콜백이 돌려주던 `FPostProcessMaterialInputs::ReturnUntouchedSceneColorForPostProcessing`은
포맷이 같으면 `FScreenPassTexture::CopyFromSlice`로 떨어지고(`PostProcessMaterial.cpp:1510`), 그건
`CopyInfo.Size = 소스 ViewRect 크기`로 `AddCopyTexturePass`를 거는 **순수 하드웨어 카피**라
크기가 다르면 스케일이 안 되고 그냥 어서션이다(`ScreenPass.cpp:107~125`).

창을 드래그하면 백버퍼는 새 크기가 되는데 이 프레임의 뷰는 아직 이전 크기다 — 그 한순간의
불일치가 곧바로 크래시. **이 확장이 없으면 톤매퍼가 백버퍼에 직접, 뷰포트 스케일링을 제대로
적용해서 쓰기 때문에 이런 카피 자체가 존재하지 않는다.** 즉 우리가 넣은 문제였다.

**2차 수정(최종)**: `OverrideOutput`이 유효하면 우리가 직접 "항상 래스터라이즈하는" 블릿으로 쓴다 —
`AddDrawTexturePass`의 slice→RenderTarget 오버로드는 `FCopyRectSrvPS`로 무조건 그리므로
(`ScreenPass.cpp:409~426`) 크기가 달라도 스케일해서 안전하게 들어간다. `OverrideOutput`이 없으면
(마지막 패스가 아니면) 기존대로 흘려보낸다 — 그 경로는 크기 불일치가 생길 수 없다.

#### 오동작 3 — 크래시는 없는데 목표와 정반대로 동작

2차 수정에서 `SetFixedViewportSize`를 아예 뺐더니 크래시는 사라졌지만, **렌더 해상도가 창을
그대로 따라가게 됐다**(크기도 비율도). 창을 세로로 길게 하면 그 비율로 렌더되고, 스트림 RT는
1920×1080이라 그걸 늘려서 내보냄 — `ugv_rc_gui`에서 실시간으로 확인됨(사용자 실측). 스트림
해상도만 불변이고 실제 렌더는 창에 종속 = 목표와 정반대.

#### 근본 제약 — 표준 게임 창에서는 구조적으로 불가능

엔진 코드 추적 결과, 창 백버퍼에 직접 그리는 뷰포트에서는 렌더 해상도를 창과 분리할 방법이 없다:

- 씬이 창 백버퍼에 직접 렌더되는데, 백버퍼 크기는 `FSlateApplication::OnSizeChanged`가 **OS 창
  크기를 그대로** `Renderer->RequestResize`에 넘겨 정한다(`SlateApplication.cpp:6970`).
- `SWindow::SetIndependentViewportSize`(뷰포트 크기를 창과 분리하는 Slate 기능)를 걸어도 위 경로는
  그 값을 보지 않는다.
- `SetFixedViewportSize`로 뷰포트만 고정하면 백버퍼와 어긋나 어서션(크래시 1·2).
- 안 걸면 창을 그대로 따라감(오동작 3).

#### 최종 형태 — 게임 뷰포트를 전용 렌더타깃 경로로 전환

`RenderDirectlyToWindow(false)`면 `UseSeparateRenderTarget()`이 true가 되고,
`FSceneViewport::UpdateViewportRHI`가 `RTTSize = (SizeX, SizeY)`로 **뷰포트 크기의 전용
렌더타깃**을 잡는다(`SceneViewport.cpp:2184~2192`). 거기에 `SetFixedViewportSize`를 걸면
`Paint`의 리사이즈 경로가 `bForceViewportSize`로 스킵되므로(`:516`) 창을 아무리 바꿔도 씬은 그
해상도로 렌더된다. 창 백버퍼는 Slate가 그 RT를 창 크기에 맞춰 그리는 데만 쓰이므로 크기/비율이
달라도 무해하다(화면에는 늘어나 보이지만 스트림은 영향 없음).

**이게 에디터 PIE가 쓰는 구성이다** — `PlayLevel.cpp:3374`의 `bRenderDirectlyToWindow = bVRPreview`,
즉 VR이 아니면 false. PIE에서 창을 바꿔도 송출 해상도가 유지된 게 그 증거였다.

`UGameEngine::CreateGameViewportWidget()`이 virtual이므로(`GameEngine.h:52`) 파생 클래스에서
바꿀 수 있다 → **신규 `Utitan_exampleGameEngine`**, `DefaultEngine.ini`의
`[/Script/Engine.Engine] GameEngine=/Script/titan_example.titan_exampleGameEngine`로 지정(적용 완료).

⚠️ **함정 — `Config/Windows/WindowsEngine.ini`가 이미 `GameEngine=/Script/Engine.GameEngine`을
갖고 있었다.** 플랫폼 ini가 `DefaultEngine.ini`보다 나중 레이어라 그 줄이 이겨서, DefaultEngine.ini에만
넣었을 때는 **Windows standalone에서 커스텀 엔진 클래스가 아예 안 먹었다**(렌더가 계속 창을 따라감).
스톡 `UGameEngine`이 정상적으로 로드되니 Fatal도 안 나고, PIE는 `UnrealEdEngine`이라 무관해서
"PIE만 되고 standalone은 안 됨"으로 보였다. → **양쪽 파일 다 수정해야 한다**(Linux는 해당 키가
없어서 DefaultEngine.ini를 그대로 상속).

진단법: 로그에 `Game viewport widget created with RenderDirectlyToWindow=false`가 있으면 먹은 것,
`Game viewport renders directly to the window backbuffer...` 경고가 있으면 안 먹은 것.

**적용 범위: standalone/패키지 빌드만.** `LaunchEngineLoop.cpp:4767`이 `if (!GIsEditor)`일 때만 이
클래스를 쓰고, 에디터/PIE는 `UnrealEdEngine`을 쓴다 — PIE는 원래부터 전용 RT 경로라 손댈 필요가
없었고 이 변경의 영향도 안 받는다. 클래스 이름이 틀리면 조용히 넘어가지 않고 시작 시
`Failed to load Game Engine class` Fatal로 죽으므로 오타는 바로 드러난다.

- 대가: 씬을 백버퍼에 직접 그리는 빠른 경로 대신 "전용 RT → Slate 합성" 한 단계가 붙는다.
  1920×1080 사각형 하나 그리는 비용이라 작지만 0은 아니다.
- 되돌리기: `[/Script/titan_example.titan_exampleGameEngine] bUseSeparateGameViewportRenderTarget=False`
  (재빌드 불필요) 또는 ini의 `GameEngine=` 줄 삭제. 그러면 `UMainViewStreamComponent`가 자동으로
  폴백(창 해상도 맞추기 + 리스케일)으로 내려가고 경고를 남긴다.
- 안전망은 그대로: `FMainViewFrameSource`의 복사가 항상 스케일 가능한 블릿이라, 어떤 구성에서도
  **스트림은 정확히 Resolution으로 나가고 크래시는 없다.**

#### 참고: PIE fps 저하

"창을 리사이즈/이동하면 fps가 20 이하로 떨어짐"은 1차 수정 이후 해소됨(사용자 확인). 원인은
따로 규명하지 않았으나 `SetFixedViewportSize`로 인한 뷰포트/백버퍼 desync가 유력하고, 최종
형태에서는 그 API를 아예 쓰지 않는다.

---

## 6. 프레임레이트 — "전송률 = 캡처률"이 아니라 "전송률 ≥ 캡처률, 상한 클램프"

### 작업 전 실태

| 스트림 | 실제 콘텐츠 갱신 | RTSP 선언·전송 |
|---|---|---|
| `ugv/rcws` | 게임틱/2 = 30fps @60틱 | 60fps → 절반이 중복 |
| `ugv/*_cctv` | 게임틱/4(라운드로빈 4방) = 15fps @60틱 | 30fps → 절반이 중복 |

### 왜 "똑같이" 맞추면 안 되는가

NVENC는 **제출 1건 분량의 출력 지연**을 갖는다 — `NvEncoder.cpp:381`
`m_nOutputDelay = m_nEncoderBuffer - 1`, 현재 `nExtraOutputDelay=1` + `ULTRA_LOW_LATENCY`(B프레임
없음)라 `m_nEncoderBuffer=2` → 출력 지연 1제출. **방금 캡처한 프레임은 "다음 제출"이 들어와야
인코더 밖으로 나온다.** `rtsp_latency_investigation.md`의 실측(`EncoderBufferCount=2
OutputBufferDelay=1` → rcws 16.7ms@60fps, CCTV 33.3ms@30fps)과 일치.

따라서 CCTV를 콘텐츠 갱신률인 15fps로 낮추면 저 33ms가 **67ms로 2배가 된다**. 중복 프레임은
낭비가 아니라 **파이프라인 플러시** 역할을 하고, 움직임이 없으면 P프레임 수백 바이트라 대역폭
비용도 거의 없다(로그상 CCTV 재접속 시 92~445바이트).

### 결론

| | 콘텐츠 | 전송 |
|---|---|---|
| RCWS (B2 이후) | 메인 뷰 = 게임 fps | `min(게임fps, MaxStreamFps=60)` — 사실상 1:1 |
| CCTV | 게임fps/4 | `CctvTargetFps=30` (의도적으로 콘텐츠보다 높음) |

CCTV를 60으로 올리려면 라운드로빈을 4→2로 바꿔야 하는데 CCTV 캡처 GPU 비용이 2배가 되므로
지금은 보류. 라운드로빈 자체는 유지(사용자 확정).

---

## 7. 변경 파일

### 신규
| 파일 | 내용 |
|---|---|
| `Source/titan_example/Vehicles/StreamResolutionSubsystem.h/.cpp` | `RcwsResolution`(1920×1080) / `CctvResolution`(320×180, 4방 공통) / `MaxStreamFps`(60) / `CctvTargetFps`(30) / `bUseFixedResolution`. `Config=Game` |
| `Plugins/RtspEncoder/.../MainViewFrameSource.h/.cpp` | 톤맵 패스에서 씬 컬러를 고정 크기 RT로 블릿하는 `FSceneViewExtensionBase` |
| `Plugins/RtspEncoder/.../MainViewStreamComponent.h/.cpp` | RT 생성 + `SetFixedViewportSize` + 위 확장 등록/해제 |

### 수정
| 파일 | 내용 |
|---|---|
| `RtspEncoder.Build.cs` | `Renderer` 의존 추가 |
| `RtspStreamComponent.h/.cpp` | `SourceRenderTarget` 추가(`SourceCapture`보다 우선), `ResolveSourceRenderTarget()` |
| `NvencD3D12Encoder.h/.cpp` | `CopyResource` 앞 크기 가드(불일치 시 1회 로그 후 프레임 스킵) |
| `VehicleRtspBridgeComponent.h/.cpp` | 해상도/fps 적용 + RCWS 메인뷰 경로 구성. `bStreamRcwsFromMainView`로 되돌리기 가능 |
| `RCWSComponent.h/.cpp` | `bDisableSightCapture` |
| `AxisSelectionWidget.h/.cpp` | `RcwsWidthText`/`RcwsHeightText`/`CctvWidthText`/`CctvHeightText` (`BindWidgetOptional`) |
| `UGVTestDashboardWidget.h/.cpp` | 고정 모드에서 RT 리사이즈/`SyncRCWSViewportRect` 스킵, 1회 재바인딩 |
| `titan_examplePlayerController.h/.cpp` | `bCreateUGVTestDashboard`(기본 true) |

WBP(`WBP_AxisSelection`)의 텍스트박스 배치는 사용자가 직접. 이름만 위와 맞추면
`BindWidgetOptional`이 자동 연결하며, 배치 안 한 필드는 기본값이 그대로 쓰인다.

---

## 8. 검증 상태

### 확인됨 (사용자 실측, 2026-08-20)

- **등록 해상도가 고정값으로 나옴** — 로그에서 `ugv/{front,rear,left,right}_cctv` 320×180,
  `ugv/rcws` 1920×1080 확인. `ugv_rc_gui` 수신 쪽에서 **창 크기와 무관하게 해상도가 유지됨**.
- **창 리사이즈해도 크래시 없음** — §5-1의 두 크래시 모두 해소.
- **standalone FHD 50fps** — RCWS 씬 캡쳐 제거 효과 포함.
- **PIE 창 조절 시 fps 저하 해소** — §5-1 참고.

### 아직 미검증

1. **RCWS 스트림에 SSR 반사/피격 흔들림이 보이는지** — B2 경로가 실제로 메인 뷰를 읽고 있다는
   가장 확실한 증거다(씬 캡쳐 경로에서는 구조적으로 안 나온다, §5). 해상도만으로는 이 부분이
   증명되지 않으므로 눈으로 확인할 것.
2. **CCTV 잘림이 실제로 사라졌는지** — 창 비율을 WBP와 다르게 만들어 대시보드가 잘리는 상태에서
   `ugv_rc_gui`의 CCTV 4분할이 멀쩡한지. `LogRtspEncoderNvenc`에 `source texture is ... but this
   encoder session was created for ...` 에러가 뜨면 어딘가 아직 RenderTarget을 리사이즈하는
   코드가 남아 있다는 뜻.
3. **`bCreateUGVTestDashboard=false`로 UI 없이** 스트림이 정상인지.
4. **백그라운드/포커스 없는 상태의 프레임레이트** — (`rtsp_poc_findings.md` §1.14, 패키지 빌드
   미검증 항목). 최소화는 이 구조상 멈추는 게 정상.
5. **성능 세부** — 이번 변경으로 CCTV 240×135→320×180(1.78배), RCWS 1226×928→1920×1080(1.82배)로
   올라가는 동시에 `rtsp_postprocess_parity_0820.md`가 씬 캡쳐 5~7개에 반사를 켰다. 반면 RCWS
   풀 Lumen 캡처 하나가 사라진다. 50fps는 세 요인이 겹친 결과다.

## 8-1. 리눅스 영향 검토 (2026-08-20)

Windows에서 동작 확인 후 리눅스 패키징/실행 관점으로 전 변경사항을 훑음.

| 변경 | 리눅스 영향 |
|---|---|
| `NvencD3D12Encoder.{h,cpp}` 크기 가드 | **없음.** `Private/Windows/`·`Public/Windows/` 아래라 UBT의 경로 기반 플랫폼 제외로 리눅스 빌드에 아예 안 들어감(Build.cs에 그 의도가 명시돼 있음). |
| `RtspEncoder.Build.cs`에 `Renderer` 추가 | 플랫폼 분기 밖(`PublicDependencyModuleNames`)이라 리눅스에도 적용. `Renderer`는 리눅스에도 있으므로 문제 없음. |
| `FMainViewFrameSource` / `UMainViewStreamComponent` | RDG/ScreenPass/Slate만 써서 RHI 비의존. RenderTarget은 `RTF_RGBA8`(=`PF_B8G8R8A8`)로, Vulkan 인코더의 `ExportableImage`가 쓰는 포맷과 일치(`FNvencVulkanEncoder.cpp:182`). |
| `Utitan_exampleGameEngine` + ini | **리눅스도 적용됨** — `Config/Linux/LinuxEngine.ini`에 `GameEngine` 키가 없어서 `DefaultEngine.ini`를 그대로 상속한다(Windows만 플랫폼 ini에 별도 값이 있었던 것). 즉 리눅스 standalone/패키지도 전용 RT 경로로 간다 = 의도한 동작. |
| 나머지 게임 모듈 변경 | 전부 플랫폼 비의존. |

### 리눅스는 원래 크래시가 아니라 "조용한 잘림"이었다

같은 크기 불일치를 리눅스에서는 이미 겪었고 2026-08-18에 클램프로 막아뒀다
(`FNvencVulkanEncoder.cpp`의 `CopyInfo.Size` 주석: RCWS RT가 세션 중 928→961로 자라서
`VUID-vkCmdCopyImage-dstOffset-00151` + 엔진 ensure로 프로세스가 멈췄던 건). 그래서 지금은
`FMath::Min`으로 겹치는 영역만 복사 = **잘린 그림이 조용히 나감**. Windows처럼 죽지는 않지만
로그가 없어서 눈으로 보기 전엔 알 수 없었다.

→ 2026-08-20, Windows 가드와 짝이 되는 **1회 경고 로그**를 Vulkan 경로에도 추가했다. 처리 방식은
일부러 다르게 뒀다: Windows는 `CopyResource`가 불일치를 못 다루므로 **프레임 스킵**, 리눅스는
이미 클램프가 있으므로 **잘린 채로 계속 송출**. 해상도가 고정된 지금은 정상 경로에서 둘 다 안 걸린다.

### 리눅스에서 실측이 필요한 것

- **전용 RT 경로의 성능** — "씬을 백버퍼에 직접" 대신 "전용 RT → Slate 합성"이 한 단계 붙는다.
  리눅스는 Xwayland/libxcb Present 병목 전력이 있어서(`linux_wayland_x11_present_bottleneck.md`,
  `SDL_VIDEODRIVER=wayland`로 해결) 이 합성 한 단계가 그 경로와 어떻게 맞물리는지 측정 필요.
- **패키지 빌드에서 ini가 실제로 먹는지** — 확인법은 Windows와 동일하게 로그 한 줄
  (`Game viewport widget created with RenderDirectlyToWindow=false`).

## 8-2. 자체방호축 (2026-08-20) — 표시는 그대로, 송출만 고정

UGV축과 요구사항이 **정반대**라 접근이 다르다.

| | UGV축 | 자체방호축 |
|---|---|---|
| 렌더 해상도 | 창과 무관하게 고정 | **창 크기를 따라가야 함**(운용자 모니터가 QHD면 그만큼 고화질 — SW 품질 요구사항 그 자체) |
| 송출 해상도 | 렌더 해상도와 동일 | 고정. 값 자체는 덜 중요(상위체계 상황판단용, 통제기 정밀조작용이 아님) |

### 채택: `URtspStreamComponent::OutputResolution` + 인코딩 직전 스케일 복사

```
표시용 RT (창 따라 유동 — 코드 0 변경)
        ↓ 크기 다를 때만 스케일 블릿 (씬 재렌더 아님)
고정 크기 중간 RT  →  NVENC/SDP (영원히 불변)
```

- **`SelfDefenseMonitor1/2Widget`을 한 줄도 안 건드렸다** → 창 추종 렌더가 구조적으로 보존됨
- 소스와 출력 크기가 같으면 중간 RT를 아예 안 만든다(추가 비용 0)
- Windows 프레임 스킵 / Linux 잘림 폴백이 양쪽 축에서 사라짐

**비용**: 블릿은 씬 렌더가 아니라 이미 렌더된 텍스처를 풀스크린 쿼드로 한 번 그리는 것
(`FCopyRectPS`). 대역폭 바운드고 7스트림 전부 합쳐 프레임당 약 1.6M 픽셀(≈6.5MB 쓰기),
60fps에서 1GB/s 미만 — 요즘 GPU 대역폭의 0.2% 수준. 반대로 이번에 제거하는 RCWS 중복 풀
Lumen 렌더가 수 ms라 **순증이 아니라 큰 폭의 순감**이다.

### RCWS 이중 렌더 제거

`bDisableSightCapture=true` + `UMainViewStreamComponent`(`bPinViewportResolution=false`).
자체방호축은 메인 뷰가 Monitor2의 `MainViewImage` 사각형에 국한돼 렌더되는데
(`SyncRCWSViewportRect`), `FMainViewFrameSource`가 씬 컬러의 `ViewRect`(=바로 그 사각형)만
복사하므로 그대로 동작한다. 목적지 RT를 처음부터 송출 해상도로 만들어서 **블릿은 총 1회**.

`SetSightAspectRatio`는 **그대로 둔다** — 캡쳐를 안 해도 탐지/조준 오버레이 UV 계산이 그 RT의
화면비를 쓰기 때문(`UTargetDetectionComponent::ProjectWorldPointToCameraUV`).

### 송출 해상도 커스터마이징

Axis selection에 자체방호축 4종 필드 추가(전부 `BindWidgetOptional`, 배치 안 하면 기본값):

| 필드 | 기본값 | 비고 |
|---|---|---|
| `SdRcwsWidthText`/`SdRcwsHeightText` | 1280×720 | |
| `SdCctvWidthText`/`SdCctvHeightText` | 320×180 | 기존 240×135는 상위체계에서 보기엔 작음 |
| `SdEnvWidthText`/`SdEnvHeightText` | 640×360 | 기존값 유지 |
| `SdUavWidthText`/`SdUavHeightText` | 640×360 | 기존값 유지 |

UGV축 필드(`RcwsWidthText` 등)와 별개다 — 그쪽은 렌더 해상도 겸 송출 해상도고, 이쪽은
**송출 전용**이라 의미가 다르기 때문.

## 8-3. 탐지 UV / 65535 정규화 — 화면비 회귀와 수정 (2026-08-20)

RTSP 해상도를 고정한 뒤, UDP로 나가는 탐지 바운딩박스가 여전히 맞는지 점검하다 **이번 작업이
UGV축에 만든 회귀**를 발견함.

### 65535 변환 자체는 정상

`UGVRemoteControlSubsystem.cpp:53~56`이 `ScreenMinUV/MaxUV × 65535`를 보내고 ICD가
`픽셀 = 값 × 영상크기 / 65535`로 역산한다. UV가 0..1 정규화값이라 정확하다.

**정규화라서 스케일에 강하다**: 소스를 다른 크기로 늘려도 정규화 좌표는 보존되므로,
§8-2의 스케일 블릿이 껴도 UV는 그대로 유효하다. (자체방호축이 이 성질 덕에 무사하다.)

### 문제 — UV를 만들 때 쓰는 화면비

`TargetDetectionComponent.cpp:325`가 투영 행렬의 AspectRatio를 **씬 캡쳐의 RenderTarget**에서
가져온다:

```cpp
const float AspectRatio = (float)Camera->TextureTarget->SizeX / (float)Camera->TextureTarget->SizeY;
```

그런데 UGV축은 이제 실제 렌더/송출이 메인 뷰포트 1920×1080(화면비 **1.778**)인데,
`SightRenderTarget`은 BP 저작값 1226×928(**1.321**)에 멈춰 있었다 —
`bDisableSightCapture`를 켜면서 `UGVTestDashboardWidget`의 `SetSightAspectRatio` 호출도 같이
막혔기 때문.

세로 NDC가 **1.321/1.778 = 0.743배**로 눌려서, 화면 맨 위(v=0)의 표적이 **v≈0.13**으로 보고된다.
가로는 `FOVAngle`이 수평 FOV라 영향 없음. UDP 탐지 박스뿐 아니라
`URCWSFireControlComponent::GetAimPointScreenUV`/`GetTurretReticleScreenUV`(조준점·레티클)도 동일.

### 수정

`UVehicleRtspBridgeComponent::SetupMainViewRcwsSource`에서 `bDisableSightCapture = true` 직후:

```cpp
RCWS->SetSightRenderTargetPixelSize(Resolution);   // 화면비를 송출 해상도와 일치시킴
```

캡쳐를 껐으니 이 RT엔 아무것도 렌더되지 않는다 — 필요한 건 크기(화면비)뿐이다. 그렇다고
해제하면 안 되는 게, `ProjectWorldPointToCameraUV`는 `TextureTarget`이 null이면 false를 반환한다
(= 탐지/조준 UV가 통째로 안 나감).

### 자체방호축은 무사

`SetSightAspectRatio`를 그대로 뒀으므로 RT 화면비가 실제 렌더되는 서브렉트를 계속 따라간다.
송출이 1280×720으로 스케일돼도 정규화 좌표는 보존되므로 수신측 역산이 맞다.

### 검증 방법

수신측에서 바운딩 박스를 그려보면 바로 드러난다 — 수정 전에는 박스가 **세로로 중앙 쪽에 몰려서**
표적보다 안쪽에 그려진다(화면 위/아래 가장자리 표적일수록 오차가 큼).

### 후속 정리 — 화면비를 렌더타깃에서 빼내기 (2026-08-20)

위 패치는 증상만 막은 것이라, 원인인 **"렌더타깃이 화면비 저장소로 오용되던 구조"** 자체를 정리함.

**정리 전**: `ProjectWorldPointToCameraUV`가 `Camera->TextureTarget->SizeX/SizeY`에서 화면비를
몰래 읽음 → RCWS가 메인 뷰포트로 넘어간 뒤로 그 렌더타깃은 "실제 렌더되는 이미지"가 아니게 됐고,
두 숫자를 저장하려고 `ResizeTarget()`(= RHI 리소스 재생성)을 매 프레임 호출하는 상태.
동기화 지점이 위젯 4곳 + 배선 코드로 흩어져 있었고, 실제로 회귀도 냈음.

**정리 후**:

| | |
|---|---|
| `ProjectWorldPointToCameraUV(Camera, **AspectRatio**, WorldPoint, OutUV)` | 화면비를 명시 인자로 받음. `TextureTarget` 의존 제거 |
| `UTargetDetectionComponent::GetCaptureAspectRatio(Camera)` | "캡쳐가 곧 렌더 결과"인 경우용 헬퍼(UAV 짐벌/CCTV/전장) — 이 경우엔 RT에서 읽는 게 정당 |
| `UTargetDetectionComponent::SetRenderedAspectRatio()` / `ResolveAspectRatio()` | 설정돼 있으면 그 값, 아니면 캡쳐 RT 폴백 |
| `URCWSComponent::SetRenderedViewSize()` / `GetRenderedAspectRatio()` | **화면비의 단일 소유자.** 설정 시 소유 액터의 탐지 컴포넌트(그게 이 SightCamera를 볼 때만)에 자동 전달 |
| `URCWSComponent::SetSightAspectRatio()` | **삭제** |

호출부는 "실제 렌더 크기를 아는 쪽"으로 통일:
- 화면 사각형에 렌더하는 위젯 4개(`Monitor1`, `SelfDefenseDashboard`, `SelfDefenseMonitor2`,
  `UGVTestDashboard`) → 그 사각형 크기
- `UVehicleRtspBridgeComponent` → 송출 해상도

**얻은 것**: 렌더타깃 재할당 처닝 소멸(자체방호 창 드래그 중 매 프레임 RHI 재생성이 없어짐),
동기화 지점이 개념적으로 1개로 수렴, 캡쳐를 꺼도 화면비가 깨지지 않음.

**남은 것(선택)**: 캡쳐가 꺼진 RCWS의 `SightRenderTarget`은 이제 아무 데도 안 쓰이므로 해제해서
메모리를 회수할 수 있다. 다만 `GetSightRenderTarget()`을 참조하는 레거시 위젯
(`Monitor1Widget`/`MissionDashboardWidget` — 현재 생성 안 됨)이 되살아나면 null을 받게 되므로
이번엔 손대지 않았다.

**교훈**: 렌더 소스를 바꿀 때는 "이 렌더타깃이 픽셀 말고 다른 것도 공급하고 있지 않은가"를 같이
봐야 한다. 여기선 화면비였다.

## 8-4. 리눅스 실측 (2026-08-20) — 검증 결과 + 잡힌 버그 1건

Ubuntu 22.04.5 / RTX 4070 SUPER / Vulkan+Wayland 패키지 빌드에서 자체방호축 실행.

### 검증된 것

- `Utitan_exampleGameEngine` 적용됨 — `Game viewport widget created with RenderDirectlyToWindow=false`
  (`Config/Linux/LinuxEngine.ini`엔 `GameEngine` 키가 없어 `DefaultEngine.ini`를 상속, 예상대로)
- 해상도 서브시스템 값 정상 반영, 자체방호 7스트림 전부 고정 해상도로 등록
- RCWS 메인뷰 카피 + `SightCamera` 캡쳐 비활성화 동작
- CCTV 스케일 블릿 동작

### 잡힌 버그 — `OutputResolution`의 조건부 중간 RT

로그에 §8-1에서 추가한 Vulkan 경고가 14회:
```
EncodeFrame: source texture is 1388x646 but this encoder session was created for 640x360
  — cropping to the overlap.
```
전부 640×360 스트림(`env_camera`, `uav_gimbal`).

**원인**: 중간 RT를 "BeginPlay 시점에 소스 크기가 출력과 다를 때만" 만들도록 했는데, 이 두
스트림은 시작 시 소스가 마침 640×360이라 중간 RT가 안 만들어졌다. 이후 위젯이 창 크기에 맞춰
소스를 리사이즈하자 그대로 인코더로 흘러가 잘렸다. **자체방호축은 소스가 나중에 바뀌는 게
정상**인데(그게 그 축의 요구사항) 시작 시점 크기로 판단한 게 잘못이었다.
CCTV(240×135 → 320×180)는 시작부터 달라서 중간 RT가 생겨 정상이었다.

**수정**: `OutputResolution`이 설정되면 **무조건** 중간 RT를 만든다. 크기가 같은 동안에는
`AddDrawTexturePass`가 하드웨어 카피로 떨어져(`ScreenPass.cpp:337`) 비용이 DMA 한 번이고,
"인코더가 보는 텍스처는 언제나 중간 RT"라는 불변식이 생겨 같은 종류의 버그가 구조적으로
불가능해진다. 조건부 경로를 남겨 DMA 한 번을 아끼는 안(B)도 검토했으나, 이 축은 소스 크기가
출력과 다른 게 정상 상태라 절약이 거의 발생하지 않고 이번 버그가 정확히 조건부 경로에서 나왔다.

**부수 효과**: UGV축 CCTV도 중간 RT를 갖게 된다(소스를 320×180으로 고정해두므로 항상 DMA 카피).
프레임당 230K 픽셀이라 무시할 수준이고, 대시보드 게이팅이 나중에 풀려도 안 깨진다.

**교훈**: 이 경고 로그(§8-1에서 "조용한 잘림을 눈으로 보기 전엔 알 수 없어서" 추가한 것)가
바로 그 역할을 했다. 없었으면 리눅스에서 화면이 잘리는 걸 눈으로 발견할 때까지 몰랐을 것.

### 별건 — 리눅스 창 테두리 없음 (우리 변경과 무관)

Wayland에서 두 창 모두 타이틀바/테두리가 안 나온다. 원인:

- UE 5.8 번들 SDL3(`libSDL3_fPIC.a`) 심볼 확인: `wayland` ✓ / `x11` ✓ /
  `xdg_toplevel_decoration` ✓ (서버사이드 데코레이션 프로토콜) / **`libdecor` ✗ (0개)**
- 환경은 Ubuntu 22.04 = GNOME/Mutter인데, **Mutter는 서버사이드 데코레이션을 구현하지 않는다**
  (클라이언트가 그리도록 강제). SDL엔 libdecor가 없어서 그릴 수 없음 → 데코레이션 없음.

즉 `VideoDriver=wayland`(§Present 병목 대응) + GNOME + libdecor 없는 SDL 빌드의 필연적 결과.
엔진이 만드는 메인 창까지 똑같이 테두리가 없다는 게 우리 코드 문제가 아니라는 증거.

- **당장**: GNOME에서 `Super` + 드래그로 창 이동 가능(타이틀바 불필요)
- **근본**: KDE Plasma 세션이면 KWin이 SSD를 지원 → 테두리 복구 + Wayland 성능 유지
- x11 폴백 스크립트로도 복구되지만 Present 병목이 재발
- 자동 모니터 배치는 여전히 불가(Wayland는 클라이언트가 자기 창 위치를 지정하는 프로토콜이 없음)

## 9. 남은 것 / 다른 세션 영역

- **자체방호축** — §3. UGV축 완료 후 사용자 승인 하에 별도 작업.
- **`FSceneCaptureViewParity::GetLocalViewShakeOffset`의 컨트롤러 선택**
  (`rtsp_postprocess_parity_0820.md` 영역) — `World->GetPlayerControllerIterator()`로 첫
  `IsLocalController()`를 잡는데, `AUGVAIController`가 이름과 달리 `APlayerController` 파생이고
  UGV 폰을 점유하므로 `GetViewTarget() == ViewOwner` 필터를 통과해 먼저 잡힐 수 있다. 2026-08-17에
  RTSP 축 게이팅을 통째로 죽였던 것과 같은 유형(`RtspAxisGate.cpp` 주석 참고).
  → `UGameplayStatics::GetPlayerController(World, 0)` 권장.
- **`UAxisSelectionWidget`의 네트워크 포트 5필드가 `FText::AsNumber` 사용** — 천단위 구분자가
  들어가서(20001 → "20,001") 사용자가 안 건드리고 커밋하면 `FCString::Atoi`가 쉼표에서 끊겨
  20을 읽는다. 이번에 추가한 해상도 4필드는 `FString::FromInt`로 회피했지만, 기존 5필드는
  LIG 프로토콜 트랙이라 손대지 않았다.
- **`Config/Windows/WindowsEngine.ini`의 `r.ReflectionMethod=3`** — 유효 범위 밖(0..2).
  `rtsp_postprocess_parity_0820.md` §1 참고.
