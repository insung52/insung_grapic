# 그래픽/렌더링 설정 전수 조사 + Graphics 탭 커스텀 가능 항목 정리 (2026-08-21)

인게임 Settings 위젯(`UGameSettingsWidget`)의 **Graphics 탭**을 채우기 전 단계 조사.
"우리 프로젝트에 그래픽 설정이 어디에 뭐가 있고, 그중 무엇을 플레이 중에 실제로 바꿀 수
있는가"만 정리한다. **위젯 UI 구현은 이 문서 범위 밖** — 사용자가 이 문서를 검토한 뒤
별도 세션에서 진행.

관련: `project_ingame_settings_menu`(Input 탭 완성 상태),
`rtsp/rtsp_resolution_customization_0820.md`, `rtsp/rtsp_postprocess_parity_0820.md`,
`rtsp_integration_complete_0817.md`, `linux_wayland_x11_present_bottleneck.md`.

---

## 0. TL;DR — 조사 결론 5줄

1. **`UGameUserSettings` 커스텀 서브클래스는 없다.** 프로젝트는 엔진 기본 클래스를 그대로
   쓰고, 코드에서 부르는 곳도 딱 두 군데뿐이다(§2.1).
2. **가장 큰 함정: 프로젝트가 하드코딩한 그래픽 값들은 런타임 스케일러빌리티 변경으로
   못 바꾼다.** cvar 우선순위 때문이다(§1.8). 품질 드롭다운을 그냥 붙이면 **일부만 먹고
   일부는 조용히 무시되는 뒤섞인 상태**가 된다. Graphics 탭 설계의 핵심 제약.
3. **해상도는 이미 주인이 셋이다** — `UGameUserSettings`, `UStreamResolutionSubsystem`,
   `UMainViewStreamComponent`의 `SetFixedViewportSize`. UGV축에서는 셋째가 이긴다(§2.3).
   Graphics 탭에 "해상도"를 넣으면 **RTSP 송출 해상도와 정면 충돌**한다.
4. **씬 캡쳐 캡쳐 주기는 4종류의 독립된 라운드로빈**으로 돌고 있다(CCTV뿐이 아니다) — 전부
   `GFrameCounter` 기반 틱 카운트 게이트, 전부 C++, 대부분 `UPROPERTY(EditAnywhere)`라
   **런타임 변경이 가장 안전하고 효과가 확실한 후보**다(§3.3).
5. **Windows와 Linux의 그래픽 설정이 갈려 있다** — `[ConsoleVariables]` 블록이
   `WindowsEngine.ini`에만 있어서, Linux 빌드는 그 튜닝을 하나도 안 받는다(§1.7).

---

## 0-1. 조사 방법 / 한계

- **방법**: `Config/**/*.ini` 전수 읽기, `Source` + `Plugins` 전수 grep
  (`SceneCaptureComponent2D` / `RoundRobin` / `GameUserSettings` / `Scalability` /
  `IConsoleVariable` / `Fullscreen`), 엔진
  `C:\Program Files\Epic Games\UE_5.8\Engine\Config\BaseScalability.ini`와 대조.
- **한계 1 — 에디터 미실행**: 이 세션에는 unreal-mcp가 안 붙어서 블루프린트 저작값을
  라이브로 못 읽었다. `.uasset`의 문자열 테이블로 **어떤 프로퍼티가 오버라이드돼 있는지**
  까지만 확인했고(값은 바이너리), 값은 기존 문서 기록에 의존한다.
- **한계 2**: 레벨(`kadex_test`)에 배치된 PostProcessVolume / 라이팅 액터의 저작값은
  이번 조사 대상에서 제외했다(ini/코드 밖). 후속 확인 항목(§8).

---

## 1. Config에 하드코딩된 그래픽 설정 전수

### 1.1 `Config/DefaultEngine.ini` → `[/Script/Engine.RendererSettings]`

전 플랫폼 공통. UE cvar 우선순위상 **`SetByProjectSetting`** 으로 들어간다(§1.8에서 중요해짐).

| 키 | 현재값 | 의미 | 런타임? |
|---|---|---|---|
| `r.Streaming.PoolSize` | `4096` | 텍스처 스트리밍 풀 상한(MB). RealBiomes 4K 텍스처의 VRAM 압박 때문에 일부러 캡을 씌운 값(ini 주석) | △ 콘솔로만 |
| `r.Streaming.LimitPoolSizeToVRAM` | `1` | 풀을 VRAM 크기로 추가 제한 | △ |
| `r.ReflectionMethod` | `1` (Lumen) | **Windows에서는 `WindowsEngine.ini`가 `3`으로 덮음** → 플랫폼별 룩 분기(§1.7) | △ |
| `r.GenerateMeshDistanceFields` | `True` | 쿡 타임 결정 | ✗ 재쿡 |
| `r.DynamicGlobalIlluminationMethod` | `1` (Lumen) | | △ |
| `r.Lumen.TraceMeshSDFs` | `0` | | △ |
| `r.Shadow.Virtual.Enable` | `1` | VSM 사용 | △ |
| `r.DefaultFeature.AutoExposure.ExtendDefaultLuminanceRange` | `True` (중복 2줄) | | ✗ 기본값 성격 |
| `r.AllowStaticLighting` | `False` | 셰이더 퍼뮤테이션 결정 | ✗ 재빌드 |
| `r.SkinCache.CompileShaders` | `True` | 쿡/셰이더 | ✗ |
| `r.RayTracing` | `False` | RHI 초기화 시점 결정 | ✗ 리스타트 |
| `r.RayTracing.RayTracingProxies.ProjectEnabled` | `False` | | ✗ |
| `r.RayTracing.Shadows` | `False` | | ✗ (RT 자체가 off) |
| `r.Substrate` | `True` | 셰이딩 모델 자체 — 셰이더 퍼뮤테이션 | ✗ 재빌드 |
| `r.Substrate.ProjectGBufferFormat` | `0` | | ✗ |
| `r.DefaultFeature.LocalExposure.HighlightContrastScale` | `0.8` | 기본 PP 값 | ✗ (PPV/카메라로 대체) |
| `r.DefaultFeature.LocalExposure.ShadowContrastScale` | `0.8` | | ✗ |
| `r.Nanite.ProjectEnabled` | `False` | **Nanite 꺼져 있음** | ✗ 리스타트 |
| `r.LumenScene.SurfaceCache.CardTexelDensityScale` | `60` | Lumen 씬 업데이트 예산 튜닝(`stat gpu`에서 34% 나와서 낮춘 값 — ini 주석) | △ |
| `r.LumenScene.DirectLighting.UpdateFactor` | `64` | | △ |
| `r.LumenScene.Radiosity.UpdateFactor` | `96` | | △ |
| `r.LumenScene.SurfaceCache.CardCaptureRefreshFraction` | `0.03` | | △ |
| `r.LumenScene.SurfaceCache.CardCapturesPerFrame` | `150` | | △ |

> △ = cvar 자체는 런타임에 바뀌지만, **콘솔/`SetByCode` 급 우선순위로 써야만** 먹는다(§1.8).

### 1.2 `Config/DefaultEngine.ini` → 그 외 그래픽 관련 섹션

| 섹션 | 키 | 값 | 비고 |
|---|---|---|---|
| `[/Script/WindowsTargetPlatform.WindowsTargetSettings]` | `DefaultGraphicsRHI` | `DefaultGraphicsRHI_DX12` (중복 2줄) | **RHI 선택. 프로세스 시작 시점 확정 → 런타임 불가** |
| 〃 | `D3D12TargetedShaderFormats` | `-PCD3D_SM5` / `+PCD3D_SM6` | 쿡 타임 |
| 〃 | `D3D11TargetedShaderFormats` | `PCD3D_SM5` | 쿡 타임 |
| `[/Script/LinuxTargetPlatform.LinuxTargetSettings]` | `+TargetedRHIs` | `SF_VULKAN_SM6` | 리눅스는 Vulkan SM6 |
| 〃 | `bGenerateNaniteFallbackMeshes` | `False` | 쿡 타임 |
| `[/Script/MacTargetPlatform.MacTargetSettings]` | `TargetedRHIs` | `SF_METAL_SM6` | (미사용 플랫폼) |
| `[/Script/HardwareTargeting.HardwareTargetingSettings]` | `TargetedHardwareClass` | `Desktop` | 스케일러빌리티 기본 프로파일의 출발점 |
| 〃 | `DefaultGraphicsPerformance` | `Maximum` | 〃 |
| `[/Script/Engine.Engine]` | `GameEngine` | `/Script/titan_example.titan_exampleGameEngine` | **§2.2 — 렌더 경로 자체를 바꾸는 설정** |
| 〃 | `GameViewportClientClassName` | `/Script/titan_example.titan_exampleViewportClient` | 〃 |

> `titan_exampleGameEngine.h`가 언급하는 `[/Script/titan_example.titan_exampleGameEngine]`
> 섹션(`bUseSeparateGameViewportRenderTarget=False`로 되돌리는 스위치)은 **현재 ini에 없다** —
> 즉 코드 기본값 `true`로 동작 중. 필요하면 추가하는 형태(재빌드 불필요).

### 1.3 `Config/Windows/WindowsEngine.ini`

플랫폼 ini는 `DefaultEngine.ini`보다 **나중 레이어**라 같은 키를 덮는다.

**`[/Script/Engine.Engine]`**

| 키 | 값 | 비고 |
|---|---|---|
| `GameEngine` | `/Script/titan_example.titan_exampleGameEngine` | Default쪽과 **양쪽 다** 필요. 한쪽만 고쳤을 때 Windows standalone에서만 조용히 안 먹은 이력 있음(ini 주석) |
| `GameViewportClientClassName` | `/Script/titan_example.titan_exampleViewportClient` | |

**`[/Script/Engine.GameUserSettings]`** — 프로젝트가 제공하는 **초기 기본값**
(사용자 `Saved/.../GameUserSettings.ini`가 생기기 전에만 의미)

| 키 | 값 | 해석 |
|---|---|---|
| `FullscreenMode` | `2` | `EWindowMode::Windowed` (0=Fullscreen, 1=WindowedFullscreen, 2=Windowed) |
| `LastConfirmedFullscreenMode` | `2` | |
| `PreferredFullscreenMode` | `2` | |

> Windowed가 기본인 건 우연이 아니다 — 자체방호축은 창 2개를 수동 배치 후 F11로 풀스크린하는
> 운용이고(`titan_examplePlayerController.cpp:254`), UGV축 메인뷰 카피 경로는 창이 떠 있어야
> 프레임이 나온다(`MainViewStreamComponent.h`의 마지막 ★ 주석).

**`[ConsoleVariables]`** — ★ Graphics 탭에서 가장 문제가 되는 블록

| 키 | 값 | 비고 |
|---|---|---|
| `sg.ResolutionQuality` | `0` | 0 = "프로젝트 기본 스크린 퍼센티지 사용"(엔진 `BaseScalability.ini` 주석) |
| `sg.ViewDistanceQuality` | `3` | Epic |
| `sg.AntiAliasingQuality` | `3` | Epic |
| `r.AntiAliasingMethod` | `4` | TSR |
| `sg.ShadowQuality` | `2` | **High (Epic 아님)** |
| `sg.GlobalIlluminationQuality` | `1` | **Medium** — Lumen이 `IrradianceFieldGather` 경로로 감 |
| `sg.ReflectionQuality` | `3` | Epic |
| `sg.PostProcessQuality` | `3` | Epic |
| `sg.TextureQuality` | `3` | Epic |
| `sg.EffectsQuality` | `3` | Epic |
| `sg.FoliageQuality` | `3` | Epic |
| `sg.ShadingQuality` | `3` | Epic |
| `r.Lumen.TraceMeshSDFs` | `0` | |
| `r.Lumen.ScreenProbeGather.DownsampleFactor` | `2` | |
| `r.Lumen.ScreenProbeGather.TracingOctahedronResolution` | `4` | |
| `r.Lumen.SurfaceCache.MaxAtlasSize` | `1024` | |
| `r.LumenScene.SurfaceCache.CardMinResolution` | `4` | |
| `r.Lumen.SurfaceCache.UpdateRate` | `0.5` | |
| `r.Lumen.FinalGatherMethod` | `0` | Irradiance Field Gather |
| `r.Lumen.IrradianceFieldGather.ClipmapWorldExtent` | `10000` | 원거리 커버리지 튜닝(2026-07-30, ini에 긴 근거 주석) |
| `r.Lumen.IrradianceFieldGather.NumClipmaps` | `5` | 〃 |
| `r.Lumen.IrradianceFieldGather.NumProbesToTraceBudget` | `128` | 〃 |
| `r.ReflectionMethod` | `3` | **유효 범위(0~2) 밖.** 렌더러는 SSR로 떨어뜨림 → Windows=SSR / Linux=Lumen 반사로 룩이 갈려 있음. `rtsp_postprocess_parity_0820.md` §1 끝 참고 |
| `r.Shadow.Virtual.MaxPhysicalPages` | `1024` | |
| `r.Shadow.Virtual.ResolutionLodBiasLocal` | `2` | |
| `r.Shadow.Virtual.ResolutionLodBiasDirectional` | `0` | |

### 1.4 `Config/Linux/LinuxEngine.ini`

| 섹션 | 키 | 값 |
|---|---|---|
| `[Linux.SDL]` | `VideoDriver` | `wayland` |

**Graphics 탭 후보에서 제외 권장.** 근거:

- SDL 비디오 드라이버는 **SDL 초기화 시점**(엔진 부트, 게임 루프 이전)에 한 번 읽히고 끝이라
  구조적으로 런타임 변경 대상이 아니다. 잘해야 "설정 저장 → 다음 실행에 반영" 형태인데,
- 이미 그 용도의 배포 수단이 있다 — 프로젝트 루트 `titan_example_x11_fallback.sh`가
  `-sdlvideodriver=x11`(커맨드라인 = INI보다 우선)로 뒤집는다.
- 성격이 "성능 옵션"이 아니라 **플랫폼 부트스트랩 기본값 고정**이다(순수 X11 머신에서 이
  값이면 SDL 초기화가 아예 실패 — 폴백 없음, ini 주석).
- → 굳이 노출한다면 Graphics 탭이 아니라 **읽기 전용 진단 정보**(현재 비디오 드라이버 표시)
  정도가 적절.

배경: `linux_wayland_x11_present_bottleneck.md` / `rtsp/RTSP_Perf_Investigation.md` — Xwayland
경유 Present가 해상도에 비례해 CPU 병목을 만들어 풀스크린 QHD 11fps → wayland 강제 후 200fps+.

### 1.5 `Config/DefaultGame.ini`

| 섹션 | 키 | 값 | 비고 |
|---|---|---|---|
| `[/Script/EngineSettings.GeneralProjectSettings]` | `bShouldWindowPreserveAspectRatio` | `False` | `UGameEngine::CreateGameWindow`가 `SWindow::ShouldPreserveAspectRatio`로 넘김. 창 자유 리사이즈용. **창 생성 시점 1회** → 런타임 불가 |

(같은 파일의 `[/Script/UnrealEd.ProjectPackagingSettings] MapsToCook`은 쿠킹 설정이라 무관.)

### 1.6 `Config/DefaultEditor.ini` / `DefaultEditorPerProjectUserSettings.ini`

전수 확인 결과 그래픽 **런타임** 설정 없음 — 에디터 Asset Viewer 프리뷰 프로파일
(`[/Script/AdvancedPreviewScene.SharedProfiles]`)뿐. Graphics 탭과 무관.

### 1.7 ★ 플랫폼 비대칭 — `[ConsoleVariables]`가 Windows에만 있다

`grep -rn "ConsoleVariables" Config/` 결과가 `Config/Windows/WindowsEngine.ini:15` **한 줄**이다.
`Config/Linux/LinuxEngine.ini`에는 `[Linux.SDL]`밖에 없다.

즉 리눅스 빌드는:

- `sg.*` 12개를 **하나도 안 받는다** → `UGameUserSettings` 기본값(desktop 기준 전부 Epic=3)으로 시작.
- Lumen 튜닝 6줄 + IrradianceFieldGather 3줄 + VSM 3줄을 **안 받는다**.
- `r.ReflectionMethod`가 `DefaultEngine.ini`의 `1`(Lumen)로 남는다.
- `r.AntiAliasingMethod` 명시값이 없어 엔진 기본(UE5는 TSR로 알려짐, **콘솔 실측 권장** — §8)으로 감.

**Graphics 탭 관점 함의**: "현재 품질 값"을 UI에 표시할 때 ini를 읽어 표시하면 리눅스에서
전부 틀린 값이 나온다. 반드시 **런타임 cvar / `Scalability::GetQualityLevels()`를 읽어서** 표시할 것.

### 1.8 ★★ cvar 우선순위 — 하드코딩된 값은 런타임 스케일러빌리티로 안 바뀐다

UE의 cvar 세터 우선순위(낮음 → 높음):

```
SetByConstructor < SetByScalability < SetByGameSetting < SetByProjectSetting
  < SetBySystemSettingsIni < SetByDeviceProfile < SetByConsoleVariablesIni
  < SetByCommandline < SetByCode < SetByConsole
```

낮은 우선순위의 `Set()`은 **조용히 무시**된다. 우리 값들을 대입하면:

| 출처 | 우선순위 | 예 |
|---|---|---|
| `[/Script/Engine.RendererSettings]` (DefaultEngine.ini) | `SetByProjectSetting` | `r.Streaming.PoolSize=4096`, `r.LumenScene.*` |
| `[ConsoleVariables]` (WindowsEngine.ini) | `SetByConsoleVariablesIni` | `sg.*`, `r.Lumen.*`, `r.ReflectionMethod=3`, `r.Shadow.Virtual.*` |
| `Scalability::SetQualityLevels()` / `UGameUserSettings::ApplySettings()` | **`SetByScalability`** (거의 최하위) | Graphics 탭이 쓰려던 경로 |
| `UKismetSystemLibrary::ExecuteConsoleCommand()` / 콘솔 입력 | `SetByConsole` (최상위) | |

**결론**: `UGameUserSettings::SetShadowQuality(n)` + `ApplySettings()` 를 그대로 붙이면,
그 그룹 안에서 **프로젝트가 안 건드린 cvar만 바뀌고, 하드코딩한 cvar는 그대로 남는다.**

엔진 `BaseScalability.ini`와 대조해 실제로 충돌하는 항목:

| 스케일러빌리티 그룹 | 그룹이 세팅하려는 cvar 중 **우리가 이미 못박은 것** |
|---|---|
| `sg.GlobalIlluminationQuality` | `r.Lumen.FinalGatherMethod`, `r.LumenScene.SurfaceCache.CardTexelDensityScale`, `r.LumenScene.SurfaceCache.CardMinResolution`, `r.LumenScene.DirectLighting.UpdateFactor`, `r.LumenScene.Radiosity.UpdateFactor`, `r.Lumen.ScreenProbeGather.DownsampleFactor`, `r.Lumen.ScreenProbeGather.TracingOctahedronResolution`, `r.Lumen.TraceMeshSDFs(.Allow)` |
| `sg.ShadowQuality` | `r.Shadow.Virtual.MaxPhysicalPages`, `r.Shadow.Virtual.ResolutionLodBiasLocal`, `r.Shadow.Virtual.ResolutionLodBiasDirectional` |
| `sg.TextureQuality` | `r.Streaming.PoolSize`, `r.Streaming.LimitPoolSizeToVRAM` |
| `sg.ReflectionQuality` | 직접 충돌 없음 — 단 `r.ReflectionMethod=3`이 별도로 못박혀 있어 반사 **방식**은 절대 안 바뀜 |
| `sg.AntiAliasingQuality` | 직접 충돌 없음 — `r.AntiAliasingMethod`가 별도로 못박혀 있어 AA **방식**은 안 바뀌고 "품질"만 바뀜 |
| `sg.ResolutionQuality` | 충돌 없음(`r.ScreenPercentage`만 건드림) ← **가장 깨끗한 후보** |

그래서 GI/Shadow/Texture 드롭다운은 **반쯤만 먹는다**. 예: GI를 Epic으로 올리면
`r.Lumen.DiffuseIndirect.Allow`, `AtlasSize`, `CardMaxResolution`, `Radiosity.ProbeSpacing`
등은 Epic 값으로 바뀌는데 `FinalGatherMethod`는 `0`(Medium 전용 경로)에 묶여 있어
**어느 프리셋에도 해당하지 않는 조합**이 만들어진다.

**Graphics 탭 설계 선택지 3가지 (사용자 결정 필요)**

- **(A) 콘솔 경로로 적용** — `ExecuteConsoleCommand(TEXT("sg.ShadowQuality 3"))`.
  `SetByConsole`이라 전부 먹는다. 가장 적은 코드로 "실제로 바뀌는" 탭이 된다.
  대가: 성능 때문에 낮춰둔 Lumen 예산 등 하드코딩 튜닝이 사용자 조작으로 날아갈 수 있음.
- **(B) 하드코딩을 걷어내고 GameUserSettings에 주인 넘기기** — `[ConsoleVariables]`의 `sg.*`를
  `Saved/.../GameUserSettings.ini`의 `[ScalabilityGroups]`로 이관. 정석이지만 리눅스/윈도우
  기본값 재정리 + 성능 재검증이 따라온다.
- **(C) 스케일러빌리티는 건드리지 않고, 우리가 소유한 값만 노출** — 캡쳐 주기, 스크린
  퍼센티지, VSync, 프레임레이트 상한 등(§6의 A등급). 충돌이 0이고 이번 단계에 가장 안전.

> 이 §1.8의 우선순위 판정은 엔진 규칙 기반 추론이다. **탭 구현 전에 실측 1회 권장** — §8-1.

### 1.9 `Saved/Config/WindowsEditor/GameUserSettings.ini` (런타임 저장 파일, 참고용)

에디터 인스턴스가 저장한 현재값. 패키지 빌드는
`Saved/Config/Windows/GameUserSettings.ini`(리눅스는 `.../Linux/`)에 별도로 생긴다.

```
bUseVSync=False              bUseDynamicResolution=False
ResolutionSizeX=1920         ResolutionSizeY=1080
FullscreenMode=1             (=WindowedFullscreen)
FrameRateLimit=0.000000      (=무제한)
AudioQualityLevel=0
DynamicResolutionFrameTarget=0.000000
bUseHDRDisplayOutput=False   HDRDisplayOutputNits=1000
Version=5
```

★ 주목: **`[ScalabilityGroups]` 섹션이 없다.** 이 프로젝트는 지금까지 스케일러빌리티를
`UGameUserSettings`로 저장한 적이 한 번도 없다. §1.8 (B)안을 고르면 이 섹션이 새로 생기고,
그때부터 ini 하드코딩과 저장값이 **둘 다** 존재하는 이중 소유 상태가 된다(우선순위상 ini가 이김).
(B)를 고른다면 `[ConsoleVariables]`의 `sg.*` 12줄을 반드시 같이 지워야 한다.

---

## 2. 메인(기본) 뷰포트 렌더링

### 2.1 `UGameUserSettings` — 커스텀 서브클래스 **없음**

`grep -rn "GameUserSettings|Scalability|SetScreenResolution|ApplySettings|sg\."` 결과, 게임 코드
전체에서 `UGameUserSettings`를 참조하는 곳은 **2곳뿐**:

| 위치 | 하는 일 | 현재 상태 |
|---|---|---|
| `Source/titan_example/titan_exampleViewportClient.cpp:87-92` | `ApplyDualMonitorResolution()` — 가상 데스크톱 전체 폭으로 해상도 설정 + Windowed | **호출 꺼져 있음**(`Tick()`의 호출부가 주석 처리, 창 2개 방식으로 교체됨). 구현만 남아 있음 |
| `Plugins/RtspEncoder/.../MainViewStreamComponent.cpp:150-168` | `ApplyWindowResolution()` — 창을 `Resolution`으로 맞추고 Windowed 고정 | **폴백 경로 전용.** 전용 렌더타깃을 못 쓰는 구성에서만 실행 |

`DefaultEngine.ini`에 `GameUserSettingsClassName=` 같은 지정도 없다 →
**엔진 기본 `UGameUserSettings`를 그대로 사용.**

Graphics 탭이 `UGameUserSettings`를 쓰기로 하면 커스텀 서브클래스를 새로 만들 필요는 없다
(§6 A등급 대부분이 기본 클래스 API로 커버됨). 캡쳐 주기 같은 프로젝트 고유 값을 같이 저장하고
싶으면 그때 서브클래스나 별도 `UGameInstanceSubsystem`(`Config=Game`)이 필요.

### 2.2 커스텀 GameEngine / ViewportClient — 렌더 경로 자체를 바꾸는 설정

| 클래스 | 목적 | Graphics 탭 관련성 |
|---|---|---|
| `Utitan_exampleGameEngine` (`titan_exampleGameEngine.h/.cpp`) | `CreateGameViewportWidget()`을 오버라이드해 `RenderDirectlyToWindow(false)` → 게임 뷰포트가 **창 백버퍼 직접 렌더가 아니라 전용 렌더타깃**에 그림. `bUseSeparateGameViewportRenderTarget`(기본 `true`, Config로 끌 수 있음) | **"렌더 해상도를 창 크기와 분리"가 가능한 유일한 지점.** 비용: 전용 RT → Slate 합성 한 단계 추가 |
| `Utitan_exampleViewportClient` (`titan_exampleViewportClient.h/.cpp`) | `LayoutPlayers()` 오버라이드 — 로컬 플레이어 1명일 때 표준 리레이아웃을 건너뛰어 `SyncRCWSViewportRect`의 커스텀 서브렉트를 보존 | **메인뷰가 화면 전체가 아니라 대시보드 패널 사각형에만 렌더된다**는 뜻 — "해상도" 개념이 단순하지 않은 이유 |

### 2.3 ★ 해상도의 실제 주인 — 3중 구조

```
① UGameUserSettings.ResolutionSizeX/Y                 → OS 창 크기(백버퍼)
② FSceneViewport::SetFixedViewportSize()              → 씬 렌더 해상도   ← UGV축에서 ①과 분리됨
③ ULocalPlayer::Origin/Size (SyncRCWSViewportRect)    → ② 안에서 실제로 씬이 그려지는 사각형
```

축별 현재 동작:

| 축 | 메인뷰 렌더 해상도 결정자 | 근거 |
|---|---|---|
| **UGV** | `UStreamResolutionSubsystem::RcwsResolution`(기본 **1920×1080**) → `UMainViewStreamComponent::SetResolution()` → `bPinViewportResolution=true` → `SetFixedViewportSize()`. **창을 어떻게 바꿔도 씬은 이 해상도로 렌더** | `VehicleRtspBridgeComponent.cpp:123`, `MainViewStreamComponent.cpp:80-95` |
| **자체방호** | **창 크기를 그대로 따라감(의도된 요구사항)** — `bPinViewportResolution=false`, `bApplyWindowResolution=false`. 운용자 모니터가 QHD면 그만큼 고화질로 렌더 | `TitanTruck.cpp:213-223` |

> 참고: `SetFixedViewportSize`는 **전용 렌더타깃 경로일 때만** 걸린다
> (`AsSlateViewport->UseSeparateRenderTarget()` 체크, `MainViewStreamComponent.cpp:80`).
> 그 경로가 아니면 폴백으로 `UGameUserSettings::SetScreenResolution()`로 창을 맞추는 데까지만
> 하고 경고 로그를 남긴다 — 백버퍼 직접 렌더에 `SetFixedViewportSize`를 걸면 어서션으로 죽는다.

**Graphics 탭에 "해상도"를 넣을 때의 충돌**:

- UGV축에서 `UGameUserSettings::SetScreenResolution()`을 바꿔도 **씬 렌더 해상도는 안 바뀐다**
  (창 크기만 바뀜). 사용자 눈에는 "해상도를 바꿨는데 화질이 그대로"로 보인다.
- 반대로 `SetFixedViewportSize`를 런타임에 바꾸면 **RTSP 인코더 세션이 깨진다** —
  `URtspStreamComponent::SetupEncoderAndStream()`이 `BeginPlay`에 크기를 **1회만** 읽어
  NVENC/SDP를 확정하고, 이후 불일치는 크기 가드에 걸려 스트림이 멈춘다(일부러 그렇게 설계됨 —
  `MainViewStreamComponent.h:86-88`).
- 자체방호축은 창 리사이즈로 렌더 해상도가 바뀌는 게 **정상 기능**이므로, 탭에서 해상도를
  강제하면 그 요구사항을 깬다.

→ **권고: Graphics 탭에 "렌더 해상도"를 넣지 말 것.** 넣는다면 "창 크기(Windowed 시)"로 이름을
정확히 붙이고, UGV축에서는 스트림/씬 해상도와 무관하다는 걸 UI에 명시.
스크린 퍼센티지(`sg.ResolutionQuality` / `r.ScreenPercentage`)가 **이 충돌을 피하면서
화질↔성능을 조절할 수 있는 대안**이다(§6 A-1).

### 2.4 프레임레이트

| 항목 | 현재 | 비고 |
|---|---|---|
| `UGameUserSettings::FrameRateLimit` | `0.0` (무제한) | 런타임 변경 완전 가능(`SetFrameRateLimit` + `ApplyNonResolutionSettings`) |
| `bUseVSync` | `False` | 런타임 변경 가능(`SetVSyncEnabled`) |
| `bUseDynamicResolution` | `False` | 런타임 변경 가능 |
| `t.MaxFPS` | ini에 없음 | `FrameRateLimit`이 내부적으로 이걸 씀 |

★ **프레임레이트는 캡쳐 주기와 직결된다.** 라운드로빈이 전부 `GFrameCounter` 기반
**틱 카운트** 게이트라, 게임 fps를 제한하면 **CCTV/UAV/전장카메라 갱신률이 같은 비율로 떨어진다**
(예: 60fps 제한 → CCTV 각 방향 15fps, 30fps 제한 → 7.5fps). Graphics 탭에 프레임레이트 제한을
넣으려면 이 부수효과를 UI에 설명하거나 §6 A-3(캡쳐 주기)과 묶어서 노출할 것.

### 2.5 창 모드 / 멀티모니터

| 항목 | 위치 | 런타임? |
|---|---|---|
| 기본 창 모드 Windowed | `WindowsEngine.ini [/Script/Engine.GameUserSettings] FullscreenMode=2` | ○ (`SetFullscreenMode`) — 단 UGV축 메인뷰 카피 경로는 **창 최소화 시 스트림 정지**, 풀스크린 전환도 검증 필요(§8-8) |
| 자체방호 Monitor1 창의 F11 토글 | `SelfDefenseMonitor1Widget.cpp:273-295` (커스텀 `SWindow`라 엔진 기본 F11 대상이 아니어서 직접 구현 + 리눅스 SDL 버그 우회 포함) | 이미 F11로 동작 |
| 듀얼모니터 스팬 창 | `titan_exampleViewportClient::ApplyDualMonitorResolution()` | **호출 비활성**(창 2개 방식으로 교체) |
| 창 종횡비 고정 해제 | `DefaultGame.ini bShouldWindowPreserveAspectRatio=False` | ✗ 창 생성 시점 |

---

## 3. 각 SceneCapture 렌더링 설정 + 캡처 주기

### 3.1 카메라 인벤토리 (`rtsp_integration_complete_0817.md` §1 재검증 완료)

| # | 카메라 | 소유 | 생성 위치 | RT 기본 크기 | RTSP mount |
|---|---|---|---|---|---|
| 1 | `RCWSSightCamera` | `URCWSComponent` (UGV·트럭 공용) | `RCWSComponent.cpp:189` (`BeginPlay`에 `NewObject`, CineCamera의 시블링) | `RenderTargetSize` = **640×360** (BP 오버라이드 있음) | `*/rcws` — **단, 양 축 모두 지금은 이 캡쳐를 안 씀**(§3.3) |
| 2~5 | `FrontCamera` / `RearCamera` / `LeftCamera` / `RightCamera` (CCTV) | `UQuadCamComponent` (플러그인) | `QuadCamComponent.cpp` `CreateCaptures()` | `RenderTargetSize` = **240×135** (BP 오버라이드 있음) | `ugv/*_cctv`, `selfdefense/*_cctv` |
| 6 | `GimbalCamera` (UAV 드론뷰) | `AUAVPawn` | `UAVPawn.cpp:198` | `RenderTargetSize` = **640×360** | `selfdefense/uav_camera` |
| 7 | `BattlefieldCapture` (전장/환경 카메라) | `ATitanTruck` | `TitanTruck.cpp:257` | `BattlefieldRenderTargetSize` = **640×360** | `selfdefense/env_camera` |

비활성/부수 캡쳐(참고, Graphics 탭 대상 아님):

- `ARCWSPreviewActor::Capture` — RC GUI 프리뷰용. `bCaptureEveryFrame=false` + 필요 시 수동 1회.
- `ATestSceneCapture` / `ARtspPocTestActor` — PoC/테스트 전용(`bCaptureEveryFrame=true`).
- `AMinimapCaptureActor` — **씬 캡쳐 제거됨**(2026-07-20, 정적 위성사진 `/Game/widget/m_map`로 대체).

> 공통 아키텍처: **디자이너는 `UCineCameraComponent`만 배치**하고, 실제
> `USceneCaptureComponent2D`는 `BeginPlay`에서 코드가 그 시블링으로 생성한다. 렌즈/DOF/노출/
> PostProcess는 매 틱 CineCamera → Capture로 **통째로 복사**된다(`SyncLensFromCineCamera(s)`).
> 즉 **캡쳐의 룩을 바꾸는 진짜 저작 지점은 BP의 CineCamera**지 캡쳐 컴포넌트가 아니다.

### 3.2 공통 캡쳐 설정 (4종 전부 동일)

| 설정 | 값 | 근거/주의 |
|---|---|---|
| `CaptureSource` | `SCS_FinalColorLDR` | 전부 동일 |
| `bCaptureOnMovement` | `false` | |
| `bCaptureEveryFrame` | **`false`** | 엔진 자동 캡쳐를 끄고 **전부 수동 `CaptureScene()`**. 시간 기반 스로틀(`TickInterval`/누적 DeltaTime)은 실 프레임 델타가 목표를 넘으면 no-op로 퇴화해서 두 번(30fps·15fps) 실패한 이력이 있어 틱 카운트 게이트로 교체됨 |
| `bAlwaysPersistRenderingState` | `true` | 껐다 켤 때 Lumen/TAA 히스토리 재할당으로 VRAM이 늘던 문제 대응 |
| `ShowFlags.TemporalAA` | **`true` (명시)** | 씬 캡쳐 기본(ESFIM_Game)은 TAA가 **꺼져 있음** — 그게 예전 시머링/노이즈 원인이었음. RCWS는 `bEnableTemporalAA` 프로퍼티로 노출(기본 true) |
| `ShowFlags.MotionBlur` | `false` (QuadCam/UAV/Battlefield) / RCWS는 미지정(=켜짐) | RCWS만 "메인 게임 뷰에 준하는 풀 퀄리티"로 취급 |
| `ShowFlags.EyeAdaptation` | **끄지 않음** | 끄면 고정 노출로 떨어져 화면이 하얗게 날아감(QuadCam 주석) |
| `bMainViewResolution` | RCWS만 `bEnableMainViewResolution`로 노출(기본 **false**) | true면 메인 뷰 화면비에 맞춰 늘어남. 수동 `CaptureScene()` 경로에서는 애초에 효과 없음 |
| RT 포맷 | `RTF_RGBA8`, `bForceLinearGamma=false`, `SRGB=true` | sRGB 디코드는 `M_SceneCaptureDisplay` 머티리얼 안에서 명시적으로 처리 |
| RT 필터 | `TF_Nearest` | 근사 1:1 리샘플 시 바이리니어 블러 방지. RCWS는 `SightRenderTargetFilter`로 노출 |
| 텍스처 스트리밍 등록 | 매 틱 `IStreamingManager::AddViewInformation()` 수동 호출 | 씬 캡쳐는 스트리밍 시스템에 자기 등록을 안 함(`GameViewportClient::Draw()`가 엔진 내 유일한 호출자) → 안 하면 최저 밉으로 뜸 |
| 반사/GI 패리티 | 캡쳐 직전 `FSceneCaptureViewParity::ApplyMainViewReflectionParity()` | **다른 세션 영역** — §7 |
| 피격 셰이크 | `FScopedCaptureViewShake` RAII(캡쳐 구간에만 오프셋) | **다른 세션 영역** — §7 |

### 3.3 ★ 캡처 주기 — 라운드로빈은 **4종류**가 독립적으로 돈다

CCTV만이 아니다. 정확한 구현 위치와 현재값:

| # | 대상 | 방식 | 구현 위치 | 기본값 | 실효 갱신률 |
|---|---|---|---|---|---|
| 1 | **CCTV 4방** | 인덱스 순환 — 매 컴포넌트 틱마다 **4개 중 1개만** 캡쳐 | `Plugins/QuadCamModule/.../QuadCamComponent.cpp:256-292` (`TickCaptureTimer()`); 인덱스는 `RoundRobinIndex` (`QuadCamComponent.h:178`, **private / 노출 안 됨**) | 하드코딩 `% 4` | 각 방향 = **게임틱 / 4** (60틱이면 15fps) |
| 2 | **RCWS SightCamera** | 틱 카운트 게이트 `GFrameCounter % Count == Slot` | `Vehicles/RCWSComponent.cpp:302-319` | `CaptureRoundRobinCount=2`, `Slot=0` (`RCWSComponent.h:71,99`, **`UPROPERTY(EditAnywhere)`**) | 게임틱 / Count |
| 3 | **UAV 짐벌** | 동일 | `Vehicles/UAVPawn.cpp:352-364` | `GimbalRoundRobinCount=2`, `Slot=1` (`UAVPawn.h:126,129`) | 게임틱 / 2 |
| 4 | **전장(환경) 카메라** | 동일 | `Vehicles/TitanTruck.cpp:303-312` | `BattlefieldRoundRobinCount=2`, `Slot=0` (`TitanTruck.h:105,108`) | 게임틱 / 2 |

**슬롯 설계 의도**: #3(Slot=1)과 #4(Slot=0)가 같은 Count=2 그룹이라 **짝수 프레임엔 전장카메라,
홀수 프레임엔 UAV 짐벌**이 돌아 둘이 절대 같은 프레임에 안 겹친다. #2는 자기 슬롯에서 별개로 돔.

**추가로: CCTV는 캡쳐 자체가 조건부다.** `UQuadCamComponent::TickComponent`는
`bAlwaysVisible || bVisible`일 때만 `TickCaptureTimer()`를 부른다(`QuadCamComponent.cpp:249-253`).
즉 대시보드가 안 띄운 차량의 CCTV는 아예 안 돈다.

**★ 지금 실제로 안 도는 것 — RCWS(#2)**

- **UGV축**: `UVehicleRtspBridgeComponent::SetupMainViewRcwsSource()`가
  `RCWS->bDisableSightCapture = true` (`VehicleRtspBridgeComponent.cpp:194`)
  → SightCamera는 `CaptureScene()`을 아예 안 돈다. 대신 메인 뷰포트 렌더 결과를
  `FMainViewFrameSource`가 카피.
- **자체방호축**: `ATitanTruck::SetupRtspStreams()`도 동일(`TitanTruck.cpp:228`).
- 즉 **양 축 모두** RCWS 씬 캡쳐는 꺼져 있고, `CaptureRoundRobinCount`는 폴백 경로
  (고정 해상도 설정이 없을 때)에서만 의미를 갖는다.

**BP 저작값**: `Content/Vehicles/UGV/Blueprint/BP_UGV_Vehicle.uasset`의 문자열 테이블에
`CaptureRoundRobinCount` / `RenderTargetSize` / `CameraFOV`가 존재 → **BP에서 오버라이드돼 있음.**
`rtsp/rtsp_latency_investigation.md` §2 #11 기록에 따르면 **2 → 1로 변경 후 저장 확인됨
(`is_dirty=false`)**. `BP_TitanTruck`은 `RenderTargetSize` / `CameraFOV`만 오버라이드하고
라운드로빈은 C++ 기본값을 쓴다. `BP_UAV`는 셋 다 오버라이드 없음.
(값 자체는 에디터 재확인 필요 — §8-4.)

**Graphics 탭 후보로서의 평가: ★★★ 가장 좋은 후보.** 이유:

- 대부분 `UPROPERTY(EditAnywhere)` → 런타임 대입만으로 즉시 반영, 재시작 불필요.
- cvar 우선순위 문제(§1.8)와 완전히 무관 — **우리 코드가 100% 소유한 값**.
- 성능 효과가 크고 예측 가능(캡쳐 하나 = 풀 씬 렌더 하나).
- 단 CCTV는 `% 4`가 하드코딩이라 노출하려면 **작은 코드 변경 필요**
  (`RoundRobinIndex` 옆에 `int32 CaptureEveryNTicks = 1;` 같은 `UPROPERTY`를 추가해
  `TickCaptureTimer()`를 게이트).

### 3.4 캡쳐 해상도(RenderTarget 크기)의 주인 — 상황에 따라 3가지

| 상황 | RT 크기를 정하는 주체 | 코드 |
|---|---|---|
| UGV축 + `bUseFixedResolution=true` (**현재 기본**) | `UStreamResolutionSubsystem` 값으로 브리지가 `BeginPlay` 직후 `ResizeTarget()` 1회. 이후 대시보드는 **리사이즈 안 함** | `VehicleRtspBridgeComponent.cpp:80-84`, `UGVTestDashboardWidget.cpp:310-324` |
| 자체방호축 (**의도적으로 미적용**) | **대시보드 위젯이 매 틱 화면 Image 위젯의 실제 픽셀 크기로 `ResizeTarget()`** — 창이 커지면 캡쳐 해상도도 커짐(요구사항) | `SelfDefenseDashboardWidget.cpp:324-350`, `SelfDefenseMonitor1Widget.cpp:195-215` |
| 폴백(설정 없음) | 컴포넌트의 C++/BP `RenderTargetSize` 기본값 | §3.1 표 |

★ **숨은 결합**: `SightRenderTarget`은 픽셀 공급자이자 **화면비 공급자**였다. 지금은
`URCWSComponent::SetRenderedViewSize()`로 일원화됐지만, 탐지 UV/조준 레티클이 이 화면비를
쓰므로 **RCWS 관련 해상도를 건드리면 UDP 탐지 바운딩박스(65535 정규화)까지 영향**을 받는다.
과거 세로 UV가 0.74배로 눌리는 회귀를 낸 적이 있음
(`rtsp_resolution_customization_0820.md` §8-3).
→ **Graphics 탭에서 RCWS 해상도는 건드리지 말 것.**

### 3.5 SceneCapture 관련 — 다른 세션과 겹치는 부분

§7에 정리. 요약: **SSR/반사 패리티와 피격 셰이크는 `rtsp_postprocess_parity_0820.md`
세션 영역이고 코드 수정까지 끝나 있다** — 이번 Graphics 탭에서 중복 조사/재설계하지 말 것.

---

## 4. RTSP 인코딩 설정 (Graphics 탭 vs RTSP 영역 — 사용자 판단 필요)

`URtspStreamComponent` (`Plugins/RtspEncoder/.../RtspStreamComponent.h`):

| 프로퍼티 | 기본값 | 실제 사용값 | 런타임? |
|---|---|---|---|
| `TargetFps` | `30` | UGV RCWS 60 (`VehicleRtspBridgeComponent.h:63` `RcwsTargetFps`), CCTV 30 (`CctvTargetFps`) — 전부 `MaxStreamFps=60`으로 클램프 | △ 프로퍼티 대입은 되지만 SDP는 이미 확정됨 |
| `BitrateKbps` | `4000` | 어디서도 오버라이드 안 함 → **전 스트림 4000kbps** | ✗ `BeginPlay`에 NVENC 세션 확정 |
| `OutputResolution` | `(0,0)` | 자체방호축만 사용(`SelfDefense*Resolution`) | ✗ 〃 |

`UStreamResolutionSubsystem` (`Source/titan_example/Vehicles/StreamResolutionSubsystem.h`,
`UCLASS(Config=Game)` GameInstance 서브시스템):

| 프로퍼티 | 기본값 | 비고 |
|---|---|---|
| `RcwsResolution` | `1920×1080` | **UGV축에서는 곧 메인 뷰포트 렌더 해상도**(§2.3) |
| `CctvResolution` | `320×180` | CCTV 4방 공통 |
| `MaxStreamFps` | `60` | 전송 fps 상한 |
| `CctvTargetFps` | `30` | 콘텐츠는 게임틱/4지만 의도적으로 높게(NVENC 출력 지연이 "제출 1건" 단위라서) |
| `SelfDefenseRcwsResolution` | `1280×720` | 송출 해상도에만 적용(렌더는 창 추종) |
| `SelfDefenseCctvResolution` | `320×180` | |
| `SelfDefenseEnvResolution` | `640×360` | |
| `SelfDefenseUavResolution` | `640×360` | |
| `bUseFixedResolution` | `true` | false면 이 서브시스템 이전 동작으로 폴백 |

**모두 `BeginPlay` 이전에만 의미가 있다.** 값 입력 UI는 이미 존재한다 — `kadex_lobby`의
축 선택 화면(`UAxisSelectionWidget`)에서 레벨 트래블 전에 받는다.

> **판단 필요 (사용자)**: 이 항목들을 Graphics 탭에 넣을 것인가?
>
> - **RTSP 영역으로 남기는 쪽에 무게**: (a) 값의 성격이 "그래픽 품질"이 아니라 **상위체계로
>   내보내는 영상 규격**(LIG ICD 협의 대상, `protocol_icd.md` §3.3/§4.1), (b) 런타임 변경이
>   구조적으로 불가능(NVENC 세션/SDP가 `BeginPlay`에 확정), (c) **입력 UI가 이미 축 선택
>   화면에 있고**, 그 화면의 width/height는 사용자가 명시적으로 "네트워크 설정"이라고 못박은
>   값이다(`feedback_ingame_settings_scope`).
> - **Graphics 탭에 넣는다면**: "적용은 다음 실행부터"라고 명시하는 저장 전용 항목이어야 하고,
>   축 선택 화면 입력과 **어느 쪽이 이기는지**를 정해야 한다.
> - 별도 세션이 진행 중인 "축별 커스텀 해상도" 작업(`rtsp_resolution_customization_0820.md`)과
>   직접 겹친다 — §7.

---

## 5. 런타임 커스텀 가능성 분류

### A. 플레이 중 즉시 반영 — 충돌 없음 (권장)

| 항목 | 적용 API |
|---|---|
| VSync | `UGameUserSettings::SetVSyncEnabled` + `ApplyNonResolutionSettings` |
| 프레임레이트 상한 | `SetFrameRateLimit` + `ApplyNonResolutionSettings` (`t.MaxFPS`) |
| 스크린 퍼센티지(해상도 스케일) | `sg.ResolutionQuality` 또는 `r.ScreenPercentage` — **스케일러빌리티 그룹 중 유일하게 하드코딩과 충돌 없음** |
| 캡쳐 주기(RCWS / UAV / 전장) | `CaptureRoundRobinCount` / `GimbalRoundRobinCount` / `BattlefieldRoundRobinCount` 직접 대입 |
| 캡쳐 주기(CCTV) | **소코드 변경 후** 가능(§3.3) |
| RCWS TemporalAA | `URCWSComponent::bEnableTemporalAA` (다음 틱 반영) |
| RT 필터(Nearest/Bilinear) | `URCWSComponent::SightRenderTargetFilter` |
| 창 모드(창/전체화면) | `SetFullscreenMode` + `ApplyResolutionSettings` — **UGV축 스트림 영향 검증 필요**(§8-8) |
| 동적 해상도 | `SetDynamicResolutionEnabled` (현재 false) |

### B. 런타임 변경은 되지만 **하드코딩과 충돌** — 콘솔 경로 필요 + 부작용 있음

| 항목 | 문제 |
|---|---|
| `sg.ShadowQuality` | VSM 3개 cvar이 못박혀 있어 반쯤만 먹음(§1.8) |
| `sg.GlobalIlluminationQuality` | Lumen 8개 cvar 못박힘 — 어느 프리셋에도 없는 조합이 됨 |
| `sg.TextureQuality` | `r.Streaming.PoolSize` 못박힘(VRAM 대책이라 **일부러** 그런 것) |
| `sg.ReflectionQuality` / `r.ReflectionMethod` | `r.ReflectionMethod=3`(범위 밖) 고정 — 반사 **방식**은 안 바뀜 |
| `r.AntiAliasingMethod` | ini 고정. 콘솔로는 바뀌지만 **씬 캡쳐 TAA 설정과의 상호작용** 확인 필요 |
| `sg.ViewDistanceQuality` / `EffectsQuality` / `FoliageQuality` / `ShadingQuality` / `PostProcessQuality` | 직접 충돌 항목은 못 찾았지만 `[ConsoleVariables]`가 그룹값 자체를 못박고 있어 **실측 필요** |

### C. 재시작 / 재빌드 / 구조적으로 런타임 불가

| 항목 | 이유 |
|---|---|
| RHI (`DX12` / `Vulkan`) | 프로세스 시작 시 확정 |
| Nanite (`r.Nanite.ProjectEnabled=False`) | 리스타트 |
| Ray Tracing (`r.RayTracing=False`) | RHI 초기화 |
| Substrate (`r.Substrate=True`) | 셰이더 퍼뮤테이션 — 재빌드/재쿡 |
| Static Lighting (`r.AllowStaticLighting=False`) | 〃 |
| Mesh Distance Fields | 쿡 타임 |
| 리눅스 SDL `VideoDriver` | SDL 초기화 1회 |
| 창 종횡비 고정 해제 | 창 생성 1회 |
| **RTSP 해상도 / 비트레이트 / `OutputResolution`** | NVENC 세션 + SDP가 `BeginPlay`에 확정 |
| **UGV축 씬 렌더 해상도** | `SetFixedViewportSize`를 도중에 바꾸면 인코더 크기 가드에 걸려 스트림 정지(§2.3) |

---

## 6. Graphics 탭 후보 목록 + UI 컨트롤 제안

### A등급 — 이번에 넣기 권장 (충돌 없음, 즉시 반영, 효과 명확)

| # | 항목 | UI 컨트롤 | 범위/옵션 | 비고 |
|---|---|---|---|---|
| A-1 | 렌더 스케일 (Screen Percentage) | **슬라이더** | 50~100% (5% 단위) | `sg.ResolutionQuality`. 해상도 충돌을 피하면서 화질↔성능을 조절하는 유일하게 깨끗한 축 |
| A-2 | 프레임레이트 상한 | **드롭다운** | 무제한 / 144 / 120 / 60 / 30 | **A-3에 영향**을 준다는 안내 문구 필요(§2.4) |
| A-3 | 카메라 피드 갱신 주기 | **드롭다운** ×1 (묶음) | 최고(1) / 높음(2) / 보통(4) / 낮음(8) | `*RoundRobinCount` 3종 + CCTV `% N`을 한 값으로 묶는 안. 개별 노출은 과함 |
| A-4 | 수직 동기화 | **토글** | On / Off (현재 Off) | |
| A-5 | 동적 해상도 | **토글** | On / Off (현재 Off) | 켜면 `DynamicResolutionFrameTarget` 슬라이더 동반 필요 |
| A-6 | 창 모드 | **드롭다운** | 창 / 전체화면(테두리 없음) | ⚠ UGV축 스트림 영향 검증 후 결정(§8-8). 자체방호는 F11이 이미 있음 |

### B등급 — 넣으려면 §1.8의 (A)/(B) 결정이 선행되어야 함

| # | 항목 | UI 컨트롤 | 비고 |
|---|---|---|---|
| B-1 | 전체 품질 프리셋 | 드롭다운 (낮음/보통/높음/에픽/커스텀) | 가장 사용자 친화적이지만 **하드코딩 튜닝을 통째로 날림.** (B)안 선행 필요 |
| B-2 | 그림자 품질 | 드롭다운 4단 | VSM 3개 cvar 충돌 |
| B-3 | GI 품질 | 드롭다운 4단 | Lumen 8개 cvar 충돌 — **가장 위험** |
| B-4 | 반사 품질 | 드롭다운 4단 | `r.ReflectionMethod=3` 고정 문제 동반(§7) |
| B-5 | 텍스처 품질 | 드롭다운 4단 | VRAM 대책과 충돌 |
| B-6 | 안티에일리어싱 | 드롭다운 (없음/FXAA/TAA/TSR) | 씬 캡쳐 TAA와의 상호작용 확인 필요 |
| B-7 | 시야거리 / 이펙트 / 폴리지 / 셰이딩 / 포스트프로세스 품질 | 드롭다운 4단 ×5 | 충돌 미확인 — 실측 후 A등급 승격 가능 |

### C등급 — 탭에 넣지 말 것 / 읽기 전용 표시만

| 항목 | 처리 제안 |
|---|---|
| 해상도 | **넣지 말 것**(§2.3). 정보 표시만: "렌더 1920×1080 / 창 ????×????" |
| RHI, Nanite, Ray Tracing, Substrate | 읽기 전용 상태 표시 또는 완전 제외 |
| 리눅스 SDL VideoDriver | 읽기 전용 진단 표시(§1.4) |
| RTSP 해상도 / 비트레이트 / fps | **RTSP 영역** — §4 / §7 |
| RCWS 캡쳐 해상도 | **넣지 말 것** — 탐지 UV / 조준 레티클과 결합(§3.4) |

### 저장 방식 제안

Input 탭이 엔진 자체 SaveGame 슬롯(`UEnhancedInputUserSettings`)을 쓰는 것과 대칭으로,
A등급 중 `UGameUserSettings` 소관(A-1 / A-2 / A-4 / A-5 / A-6)은 `ApplySettings(false)` +
`SaveSettings()`로 `GameUserSettings.ini`에 맡기고, 프로젝트 고유 값(A-3 캡쳐 주기)만
별도 보관처(`UGameInstanceSubsystem` + `Config=Game` — `UStreamResolutionSubsystem`과 동일 패턴)를
쓰는 게 기존 관례와 맞는다.

---

## 7. 다른 트랙과 겹치는 항목 (명시)

| 항목 | 겹치는 트랙 | 이번 세션에서의 처리 |
|---|---|---|
| SceneCapture의 SSR/Lumen 반사 누락 (`ApplyMainViewReflectionParity`) | **`rtsp/rtsp_postprocess_parity_0820.md`** — 원인 확정 + 코드 수정 완료(빌드 검증 미완) | **재조사하지 않음.** Graphics 탭에서 반사 품질을 노출하면 이 보정 로직과 상호작용하므로 그 세션 결과를 먼저 볼 것 |
| 피격 카메라 셰이크가 캡쳐에 안 닿는 문제 (`FScopedCaptureViewShake`) | 동일 | 동일 |
| `r.ReflectionMethod=3` (유효 범위 밖, Windows=SSR / Linux=Lumen 분기) | 위 문서 §1 끝 + `rtsp_resolution_customization_0820.md` §9 | **미해결 상태로 남아 있음.** Graphics 탭에 반사 항목을 넣으려면 **이걸 먼저 정리해야 한다**(의도 확인 필요) |
| `LumenSurfaceCacheResolution`이 씬 캡쳐에서만 0.5 | `rtsp_postprocess_parity_0820.md` §5 | Linux 빌드에서 반사 디테일이 메인 뷰보다 거칠 수 있음. CineCamera Override로 1.0 가능 |
| RTSP 송출 해상도(축별 커스텀) | **`rtsp/rtsp_resolution_customization_0820.md`** — 양 축 완료, 리눅스 실측까지 확인 | §4에 후보로 정리만 하고 **판단은 사용자에게**. 기본 권고: RTSP 영역에 남김 |
| UGV축 메인 뷰포트 렌더 해상도 고정 | 동일 | Graphics 탭의 "해상도" 항목과 **정면 충돌** — §2.3. 넣지 않기를 권고 |
| 축 선택 화면(`UAxisSelectionWidget`)의 width/height | 사용자 명시: **네트워크 설정** | 어떤 탭도 건드리지 않음(`feedback_ingame_settings_scope`) |
| 리눅스 Wayland/X11 | `linux_wayland_x11_present_bottleneck.md` | 커스텀 후보 제외 권고 — §1.4 |

---

## 8. 확인 필요 / 미확정 (다음 단계 전 처리)

1. **[실측 5분] cvar 우선순위 확정** — 패키지 빌드 콘솔에서 `sg.ShadowQuality 3` 입력 후
   `r.Shadow.Virtual.MaxPhysicalPages` 조회. `1024`가 유지되면 §1.8 판정이 맞고,
   `2048`로 바뀌면 B등급 항목 대부분이 A등급으로 올라간다.
   **Graphics 탭 설계가 여기서 갈리므로 가장 먼저 할 것.**
2. **[사용자 판단] §1.8의 (A)/(B)/(C) 중 어느 방향으로 갈 것인가.**
3. **[사용자 판단] §4의 RTSP 항목을 Graphics 탭에 넣을 것인가.**
4. **[에디터 확인] BP 저작값** — `BP_UGV_Vehicle`의 `CaptureRoundRobinCount` /
   `RenderTargetSize` / `CameraFOV`, `BP_TitanTruck`의 `RenderTargetSize` / `CameraFOV` 실제 값.
   (이 세션은 unreal-mcp 미연결이라 오버라이드 **존재 여부**만 확인함.)
5. **[에디터 확인] 레벨(`kadex_test`)의 PostProcessVolume / 라이팅 액터 저작값** — ini 밖이라
   이번 조사에서 제외. 노출/색보정을 Graphics 탭에 넣을 생각이면 필요.
6. **[확인] Linux 빌드의 실제 `r.AntiAliasingMethod` 값** — `[ConsoleVariables]`가 없어
   엔진 기본값에 의존. 콘솔 조회 1줄이면 끝.
7. **[결정] `Config/Windows/WindowsEngine.ini`의 `r.ReflectionMethod=3`** — 의도인지 오타인지.
   Windows/Linux 룩 분기의 원인이고 Graphics 탭 반사 항목의 전제.
8. **[검증] 창 모드 변경(A-6)이 UGV축 RTSP 스트림에 미치는 영향** —
   `bPinViewportResolution=true` + `SetFixedViewportSize` 상태에서 풀스크린 전환 시 백버퍼/뷰포트
   불일치가 안 나는지. 과거 이 조합에서 어서션 크래시 이력 있음
   (`rtsp_resolution_customization_0820.md` §5-1 크래시 1).
