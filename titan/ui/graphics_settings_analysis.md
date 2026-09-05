# 그래픽/렌더링 설정 전수 조사 + Graphics 탭 커스텀 가능 항목 정리 (2026-08-21)

2026-09-03 / 스코프 확정·구현대기 / Graphics 탭 전수 조사 — `DumpCVars` 실측으로 제약 확정
(§0-2 F), 채택 구조 설계(§9), **사용자 확정 스코프 = 품질 프리셋(그림자/GI/반사) + 캡쳐 주기**(§10).

인게임 Settings 위젯(`UGameSettingsWidget`)의 **Graphics 탭**을 채우기 전 단계 조사.
"우리 프로젝트에 그래픽 설정이 어디에 뭐가 있고, 그중 무엇을 플레이 중에 실제로 바꿀 수
있는가"만 정리한다. **위젯 UI 구현은 이 문서 범위 밖** — 사용자가 이 문서를 검토한 뒤
별도 세션에서 진행.

관련(2026-08-31 문서 재편 후 경로): `ui/ingame_settings_input_system.md`(Input 탭 완성 상태),
`rtsp/rtsp_resolution_customization_0820.md`, `camera_pipeline/rtsp_postprocess_parity_0820.md`,
`rtsp/rtsp_integration_complete_0817.md`, `rtsp/linux_wayland_x11_present_bottleneck.md`,
`rcws/2026-08-31_selfdefense_camera_shake_bugs.md`,
`vehicle/drone/2026-09-01_drone_replaces_bp_uav.md`, `packaging/`.

---

## 0-2. 2026-09-03 팔로업 — 본문 대비 달라진 것

2026-08-21 조사 이후 13일간의 변경분을 코드/ini/엔진 소스로 재검증한 결과. **아래 항목은
본문보다 이 절이 우선한다**(본문 해당 위치에도 인라인으로 반영해 뒀다).

### A. 본문이 틀렸던 것 (정정)

| # | 본문 | 정정 | 결론 영향 |
|---|---|---|---|
| A-1 | §1.8 표 — `[ConsoleVariables]` = `SetByConsoleVariablesIni` | **`ECVF_SetBySystemSettingsIni`(0x05)** 가 맞다. `ConfigCacheIni.cpp:6971`에서 `ApplyCVarSettingsFromIni(TEXT("ConsoleVariables"), *GEngineIni, ECVF_SetBySystemSettingsIni)`로 직접 확인. `SetByConsoleVariablesIni`(0x0A)는 `Engine/Config/ConsoleVariables.ini`의 `[Startup]` 전용 | **없음** — 0x05도 `SetByScalability`(0x02)/`SetByProjectSetting`(0x04)보다 높다. §1.8의 결론 그대로 |
| A-2 | §1.7 "`[ConsoleVariables]`가 Windows에만 있다" | **이제 `DefaultEngine.ini`에도 있다**(2026-08-25 신설, `t.MaxFPS=60` + `p.UGV.SkidSteer.TorqueNm=1600`). 두 섹션은 같은 `GEngineIni`로 병합되므로 Windows는 합집합, Linux는 Default 것만 | **부분** — `sg.*`/Lumen/VSM 블록이 Windows 전용이라는 사실은 그대로. 문장만 정정 |
| A-3 | §1.8 "GameUserSettings 경로는 `SetByScalability`라 못 이긴다" | **과도한 일반화였다.** 그건 스케일러빌리티 그룹에만 해당. `FrameRateLimit`은 `UEngine::SetMaxFPS`가 **cvar의 기존 SetBy 이유를 그대로 승계**해서 쓰기 때문에(`ThisSetReason = LastSetReason`, `UnrealEngine.cpp:12247`) 동일 우선순위로 통과한다 — 실제로 ini의 `t.MaxFPS=60`이 `FrameRateLimit=0`에 지워진 이력이 프로젝트 ini 주석에 남아 있다 | **있음** — §5-A 목록의 근거가 항목별로 갈린다(아래 B-1) |
| A-4 | §1.9 `FrameRateLimit=0.0`(무제한) | **60**. `Config/DefaultGameUserSettings.ini` 신설(2026-08-25). `Saved/.../GameUserSettings.ini`에서는 해당 줄이 삭제돼 기본값으로 떨어지게 해 뒀다 | **큼** — §6 A-2 재설계(아래 C-1) |

### B. 새로 확인한 메커니즘

- **B-1. GameUserSettings 항목별 실제 우선순위** (엔진 소스 확인):
  | 설정 | 적용 경로 | 우선순위 | ini 하드코딩을 이기나 |
  |---|---|---|---|
  | 스케일러빌리티 그룹 | `Scalability::SetQualityLevels` | `SetByScalability`(0x02) | **못 이김** |
  | `FrameRateLimit` | `UEngine::SetMaxFPS` | **기존 이유 승계** | **이김** |
  | `bUseVSync` | `CVar->Set(..., ECVF_SetByGameSetting)`(0x03) | 이김 — 단 ini에 `r.Vsync`가 있으면 엔진이 아예 세팅을 건너뜀(`GameUserSettings.cpp:522`). 우리 프로젝트엔 없음 | 이김 |
  | 싱크 타입 | `r.GTSyncType`, `ECVF_SetByCode`(0x0E) | 이김 |
  → §5의 A등급이 "충돌 없음"인 건 맞지만, **이유가 항목마다 다르다.**
- **B-2. UE 5.8 우선순위 사다리에 중간 단계가 더 있다**: `…ProjectSetting(0x04) < SystemSettingsIni(0x05) < PluginLowPriority(0x06) < DeviceProfile(0x07) < PluginHighPriority(0x08) < GameOverride(0x09) < ConsoleVariablesIni(0x0A) < Preview(0x0C) < Commandline(0x0D) < Code(0x0E) < Console(0x10)`. 본문 §1.8의 사다리는 이 중 일부가 빠져 있었다(결론은 동일).
- **B-3. 캡쳐 게이팅 플래그가 3종으로 늘었다** — 기존 `URCWSComponent::bDisableSightCapture`에 더해
  `ADronePawn::bDisableGimbalCapture`, `ATitanTruck::bDisableBattlefieldCapture` 신설. 전부 "이
  프로세스에선 이 화면을 볼 사람이 없다 → 캡쳐 자체를 스킵" 용도(축 게이팅). §6 A-3은 이
  게이팅 위에 얹는 형태로 설계해야 한다.
- **B-4. 패키징 함정(Input 탭에서 실제로 터진 것)** — 문자열 경로로만 참조되는 애셋은 쿠커가
  정적 분석으로 못 찾아 패키지에서 빠진다. `DA_TitanInputSchema`를 `LoadObject()` 경로 문자열로만
  불러서 **리눅스 패키지에서 Input 탭이 통째로 비어서 떴다.** 대응이 두 겹으로 들어가 있다:
  `DefaultGame.ini`의 `+DirectoriesToAlwaysCook=(Path="/Game/Input")`(ini 주석은 이걸로 해결됐다고
  적고 있음)과, **실제로 확실히 먹은 해법인 생성자 `ConstructorHelpers::FObjectFinder`**
  (`Input/TitanInputBindingSubsystem.cpp:23` — CDO가 진짜 하드 레퍼런스를 갖게 함). 코드/헤더
  주석은 후자를 근본 해법으로 적고 있으니, **경로 문자열 로드를 새로 짤 땐 `FObjectFinder`
  패턴부터 쓸 것.** **Graphics 탭이 프리셋 DataAsset/커브를 경로 문자열로 참조하면 똑같이
  당하고, PIE/에디터에서는 절대 재현되지 않는다.**

### C. 계획이 바뀌는 것

- **C-1. 프레임레이트 상한(§6 A-2)을 자유 조절 항목으로 두면 안 된다.** `t.MaxFPS=60`은 화질/성능
  옵션이 아니라 **물리 결정성 대책**이다 — `bTickPhysicsAsync=false`(엔진 기본)라 물리 dt가 프레임
  dt를 그대로 쓰고, 고사양 PC에서 UGV가 속도를 못 이기고 장애물에 부딪히던 증상이 그것이었다.
  `MaxPhysicsDeltaTime`(1/30)이 느린 쪽을 막고 있으므로 빠른 쪽을 60으로 막아 dt 편차를 4.8배
  → 2배로 줄인 것(`DefaultEngine.ini` `[ConsoleVariables]` 주석). 게다가 캡쳐 라운드로빈이 전부
  틱 카운트 기반이라 fps를 바꾸면 카메라 갱신률도 같이 흔들린다(§2.4).
  → **권고 변경: 상한을 60 **위로** 올리는 선택지는 제공하지 말 것.** 남는 선택지는
  "60(기본) / 30(저사양)" 정도이고, 그마저도 차량 거동이 바뀐다는 경고가 필요하다.
  대안: 상한은 고정하고 **A-1 렌더 스케일 슬라이더로만 성능을 조절**하게 하는 쪽이 안전하다.
  참고로 `Config/DefaultGameUserSettings.ini`의 주석은 **Graphics 탭 세션 앞으로 남긴 메모**다 —
  "프레임 상한은 이 GameUserSettings 경로를 그대로 쓰는 게 맞다(엔진 표준 경로, 저장/로드 구현
  완료)". 즉 *경로*는 그대로 쓰되 *범위*만 제한하면 된다.
- **C-2. 창 모드(§6 A-6)를 A등급에서 B등급으로 내린다.** 실제 운용은 런치 인자다 —
  `./titan_example.sh -fullsystem -fullscreen`(`packaging/2026-09-02_linux_package_ugv_host_rc_test_guide.md` §3-4,
  `packaging/kadex_0902_패키징_실행가이드.md` §2). 커맨드라인(0x0D)이 GameUserSettings보다 높아
  탭에서 바꿔도 다음 실행에 덮인다. §8-8의 "풀스크린 + `SetFixedViewportSize` 조합 검증"은
  이제 가설이 아니라 **현재 운용 조건 그 자체**이므로 우선순위를 올릴 것.
- **C-3. §8-1 실측 항목을 좁힌다.** A-3(`t.MaxFPS` 반례)로 "GameUserSettings는 전부 막힌다"가
  아님이 확인됐으므로, 실측 대상은 **스케일러빌리티 그룹 멤버 cvar 하나**로 정확히 좁혀야 한다.
  절차는 §8-1 그대로(`sg.ShadowQuality 3` → `r.Shadow.Virtual.MaxPhysicalPages` 조회).
- **C-4. §8-5(레벨 PPV 조사)의 대상 레벨이 바뀌었다.** `kadex_test` → **`New_kadex_0811`**.
  패키징 대상은 `kadex_lobby` + `New_kadex_0811` 2개뿐이고 `kadex_test`는 2026-09-01에 제외됐다
  (`DefaultGame.ini`). `New_kadex_0811`에 PostProcessVolume 5, DirectionalLight 6,
  ExponentialHeightFog 6, HDRIBackdrop 10, SkyLight 2 배치 확인.
  노출 기준은 이미 정해져 있다(레벨 노출배율 1e-4, 지면 200nit — `sfx_vfx/` VFX nit 트랙).

### D. 카메라 인벤토리 변경 (§3.1/§3.3 대체)

- **UAV 짐벌이 통째로 교체됐다** — `AUAVPawn::GimbalCamera` → **`ADronePawn::GimbalCapture`**
  (`Source/titan_example/Drone/DronePawn.{h,cpp}`). 구 `AUAVPawn`/`BP_UAV`는 코드에 아직
  남아 있지만 **`New_kadex_0811`에 배치된 건 `BP_Drone`뿐**이고, 2-PC 검증 후 제거 예정.
  | 항목 | 구 `AUAVPawn` | 신 `ADronePawn` |
  |---|---|---|
  | RT 크기 | `RenderTargetSize` 640×360 | **`CameraRenderTargetSize` 1280×720** |
  | 라운드로빈 | Count=2 / Slot=1 | **동일**(`DronePawn.h:304,307`) |
  | RTSP mount | `selfdefense/uav_camera` | **`selfdefense/uav_gimbal`** |
  | 송출 해상도 | — | `OutputResolution = SelfDefenseUavResolution`(640×360) |
  | 캡쳐 스킵 | — | **`bDisableGimbalCapture`**(아무도 안 보면 스킵) |
  | 피격 셰이크 | `FScopedCaptureViewShake` 적용 | **미적용**(반사 패리티만 적용) |
- **UGV BP가 교체됐다** — `BP_UGV_Vehicle` → **`BP_UGV_0901`**(2026-09-02 신규 6×6 차륜 모델,
  `Content/Vehicles/UGV/UGV_0901/`). 캡쳐 관련 오버라이드 3개(`CaptureRoundRobinCount` /
  `RenderTargetSize` / `CameraFOV`)는 그대로 승계됨(uasset 문자열 테이블로 확인, 값은 여전히
  에디터 확인 필요 — §8-4). `BP_Drone`은 캡쳐 관련 오버라이드 **없음** → C++ 기본값 사용.
- **`FSceneCaptureViewParity`가 재작성됐다**(2026-08-31) — `UViewShakeProbeCameraModifier` 신설.
  기존 구현이 "모디파이어 걸리기 전 POV"를 `CalcCamera()`로 그 자리에서 다시 계산해서 카메라
  매니저의 **직전 프레임** 캐시와 뺐던 게 한 프레임 어긋남을 만들었고, 그게 자체방호축
  환경카메라/CCTV 떨림의 원인이었다. 지금은 모디파이어 체인 맨 앞에 프로브를 꽂아 같은 시점
  값을 쓴다. **반사 패리티 로직(`ApplyMainViewReflectionParity`)은 그대로** — `r.ReflectionMethod`
  cvar를 읽어 0~2로 클램프하는 것도 그대로다. 상세: `rcws/2026-08-31_selfdefense_camera_shake_bugs.md`.

### F. ★★ 2026-09-03 실측 완료 — §8-1 확정 (`DumpCVars -csv`, 에디터)

에디터 콘솔에서 `DumpCVars -csv` 한 줄 → `Saved/Logs/ConsoleVars.csv`(9,670개 cvar) 전수 덤프로
§1.8을 **확정**했다. 원본은 `ui/data/2026-09-03_ConsoleVars_setby.csv`로 보관.
SETBY 분포:
`Constructor 9329 / Scalability 173 / ProjectSetting 90 / SystemSettingsIni 40 / Code 26 /
GameSetting 7 / DeviceProfile 2 / ConsoleVariablesIni 2 / Console 1`.

**핵심 한 줄** — `r.Shadow.Virtual.MaxPhysicalPages,1024,SystemSettingsIni`.
→ `SetByScalability`(0x02) < `SetBySystemSettingsIni`(0x05) → **품질 드롭다운으로 못 바꾼다.**

**그런데 결론이 "반만 먹는다"보다 나쁘다 — `UGameUserSettings` 경로는 완전 no-op이다.**

`sg.*` 12개가 **전부** `SystemSettingsIni`로 고정돼 있다(실측):
```
sg.AntiAliasingQuality,3   sg.EffectsQuality,3    sg.FoliageQuality,3
sg.GlobalIlluminationQuality,1   sg.PostProcessQuality,3   sg.ReflectionQuality,3
sg.ResolutionQuality,0     sg.ShadingQuality,3    sg.ShadowQuality,2
sg.TextureQuality,3        sg.ViewDistanceQuality,3
```
그리고 엔진 구조상:
- `Scalability::SetQualityLevels()` → `SetQualityLevelCVar()` → **`Set(v, ECVF_SetByScalability)`**
  (`Scalability.cpp:907`) → `sg.*`가 0x05라 **거부됨**.
- 그룹 멤버는 `sg.*` cvar의 **`SetOnChangedCallback`이 떠야만** 적용된다
  (`Scalability.cpp:625` → `OnChangeShadowQuality` → `SetGroupQualityLevel`).
- `sg.*` Set이 거부되면 그 콜백이 **아예 안 뜬다** → **멤버가 하나도 재적용되지 않는다.**

→ **`UGameUserSettings::SetShadowQuality(3) + ApplySettings()`는 아무 일도 일으키지 않는다.**
본문 §1.8의 "반만 먹는다"는 실제로는 "**전혀 안 먹는다**"가 맞다.

**우회 경로 4가지 (실측 기반 정리)**

| 방법 | `sg.*` 자체 | 그룹 멤버 |
|---|---|---|
| `UGameUserSettings::ApplySettings()` (원래 계획) | **거부**(0x02<0x05) | **전혀 안 바뀜 — 완전 no-op** |
| **`Scalability::SetQualityLevels(L, bForce=true)`** | 바뀜 (`SetWithCurrentPriority`, `Scalability.cpp:891`) | 핀 안 된 것만 바뀜 = **진짜 "반만"** |
| 콘솔 `sg.ShadowQuality 3` (`SetByConsole` 0x10) | 바뀜 | 핀 안 된 것만 바뀜 = "반만" |
| 콘솔로 **개별 멤버** 직접 (`r.Shadow.Virtual.MaxPhysicalPages 2048`) | — | **전부 바뀜** |

→ **`bForce=true`가 가장 현실적인 진입점**(엔진 공개 API, 코드 한 줄). 단 그래도 핀된 멤버는
안 움직이므로 §1.8 (B)안(ini 하드코딩 제거)을 같이 하지 않으면 "프리셋에 없는 조합"은 그대로다.

**실측으로 확인된 "실제로 바뀌는 것" (SETBY=Scalability, 173개 중 일부)**
`r.ShadowQuality=5`, `r.Shadow.MaxResolution=1024`, `r.VolumetricFog=1`,
`r.Lumen.DiffuseIndirect.Allow=1`, `r.LumenScene.SurfaceCache.AtlasSize=2048`,
`r.MaxAnisotropy=8`, `r.SSR.Quality=3`, `r.TSR.History.ScreenPercentage=200` …

**실측으로 확인된 "핀돼서 안 바뀌는 것"**
- `SystemSettingsIni`(프로젝트 `[ConsoleVariables]`): `r.Shadow.Virtual.MaxPhysicalPages=1024`,
  `ResolutionLodBiasLocal=2`, `ResolutionLodBiasDirectional=0`, `r.Lumen.FinalGatherMethod=0`,
  `r.Lumen.ScreenProbeGather.DownsampleFactor=2`/`TracingOctahedronResolution=4`,
  `r.Lumen.IrradianceFieldGather.*`, `r.Lumen.TraceMeshSDFs=0`,
  `r.LumenScene.SurfaceCache.CardMinResolution=4`, `r.ReflectionMethod=3`,
  `r.AntiAliasingMethod=4`, `t.MaxFPS=60`, `p.UGV.SkidSteer.TorqueNm=1600`
- `ProjectSetting`(`[/Script/Engine.RendererSettings]`): `r.Streaming.PoolSize=4096`,
  `r.Streaming.LimitPoolSizeToVRAM=1`, `r.LumenScene.SurfaceCache.CardTexelDensityScale=60`,
  `r.LumenScene.DirectLighting.UpdateFactor=64`, `r.DynamicGlobalIlluminationMethod=1`,
  `r.Nanite.ProjectEnabled=0`, `r.Substrate=1`

**A-1(렌더 스케일)도 경로를 바꿔야 한다** — `sg.ResolutionQuality`가 핀돼 있어
`SetResolutionScaleNormalized()+ApplySettings()`는 no-op이다. 하지만
**`r.ScreenPercentage`는 `Constructor`(=아무도 안 건드림)** 라 직접 세팅하면 그대로 먹는다.
→ A-1은 `r.ScreenPercentage`를 직접 쓰는 방식으로 구현할 것. **여전히 1순위 후보.**

**우선순위에 안 막히는 두 경로(확인됨)** — 둘 다 GameUserSettings 그대로 써도 된다:
- `t.MaxFPS` ← `UEngine::SetMaxFPS`가 기존 우선순위 승계(`UnrealEngine.cpp:12253`).
- `r.SetRes` ← `FSystemResolution::RequestResolutionChange`가 **`SetWithCurrentPriority`**
  (`UnrealEngine.cpp:19151`). 즉 **해상도/창모드 변경은 우선순위로 막히지 않는다.**

### F-2. ⚠ 에디터가 대표성이 없는 항목 — VSync (앞선 "에디터로 충분" 주장의 예외)

실측에 `r.VSync,0,SystemSettingsIni`가 찍혔는데, 출처가 **`Engine/Config/BaseEngine.ini:2481`의
`[SystemSettingsEditor]` 섹션 — 에디터 전용**이다(`SystemSettings.cpp:31-32`,
`GetSectionName(bIsEditor)`). 게다가 `UGameUserSettings::ApplyNonResolutionSettings`는
에디터에서 `ConfigSection="SystemSettingsEditor"`를 보고 그 키가 있으면 **VSync 세팅을 통째로
건너뛴다**(`GameUserSettings.cpp:511-524`, 주석: *"VSync was already set by system settings.
We are not capable of setting it here."*).

→ **패키지 빌드에서는 `ConfigSection="SystemSettings"`를 보는데 엔진에도 우리 프로젝트에도
그 섹션에 `r.Vsync`가 없다** → VSync가 정상적으로 `ECVF_SetByGameSetting`으로 세팅되고,
그걸 막는 상위 우선순위도 없다. **즉 §6 A-4(VSync 토글)는 패키지에서 정상 동작한다.
에디터에서 테스트하면 "안 먹네?"로 보이는 게 정상이다** — 이 항목만은 패키지에서 확인할 것.
(`r.SetRes,1920x992w,SystemSettingsIni`도 같은 계열의 에디터 창 상태값이라 패키지와 무관.)

### E. 변한 게 없다고 재확인한 것 (본문 그대로 유효)

- `Config/Windows/WindowsEngine.ini`의 `[ConsoleVariables]` `sg.*`/Lumen/VSM 블록 — 2026-08-20
  이후 무변경. `[/Script/Engine.RendererSettings]` 블록도 무변경. `Config/Linux/LinuxEngine.ini` 무변경.
- **`UGameUserSettings` 커스텀 서브클래스 여전히 없음**, 참조처도 여전히 2곳(그중 하나는 호출 꺼짐).
- **`Saved/.../GameUserSettings.ini`에 `[ScalabilityGroups]` 여전히 없음** → §1.9의 (B)안 논의 유효.
- `QuadCamComponent` / `MainViewStreamComponent` / `StreamResolutionSubsystem` /
  `Utitan_exampleGameEngine` / `Utitan_exampleViewportClient` 전부 무변경 → §2.2/§2.3/§3.4 유효.
- `URCWSComponent`의 캡쳐 관련 프로퍼티 전부 무변경(파일은 커졌지만 줌/탄착산포/표적유지 등
  게임플레이 쪽 변경) → §3.2/§3.3의 RCWS 항목 유효.
- **`r.ReflectionMethod=3` 여전히 미해결** → §7/§8-7 유효.
- **`UGameSettingsWidget` 무변경(2026-08-21)** — `WBP_GameSettings`에 `tab_graphics` 페이지는
  있으나 그래픽 컨트롤 위젯은 하나도 없음. **Graphics 탭 미구현 확정.**
- RTSP 해상도 입력이 축 선택 화면(`WBP_AxisSelection2`)에 있고, 이제 **운용 절차서의 정식
  단계**로 문서화됐다(패키징 가이드 §4-1 표). → §4의 "RTSP 영역에 남기자" 권고가 더 강해짐.

---

## 0. TL;DR — 조사 결론 5줄

1. **`UGameUserSettings` 커스텀 서브클래스는 없다.** 프로젝트는 엔진 기본 클래스를 그대로
   쓰고, 코드에서 부르는 곳도 딱 두 군데뿐이다(§2.1).
2. **가장 큰 함정: 프로젝트가 하드코딩한 그래픽 값들은 런타임 스케일러빌리티 변경으로
   못 바꾼다.** cvar 우선순위 때문이다(§1.8). **2026-09-03 실측(§0-2 F)으로 확정됐고, 예상보다
   심각하다** — `sg.*` 12개가 전부 고정돼 있어서 `UGameUserSettings` 품질 경로는 "일부만 먹는"
   게 아니라 **완전 no-op**이다. `Scalability::SetQualityLevels(L, bForce=true)`로 우회하면
   그때부터 "일부만 먹는" 상태가 된다. Graphics 탭 설계의 핵심 제약.
3. **해상도는 이미 주인이 셋이다** — `UGameUserSettings`, `UStreamResolutionSubsystem`,
   `UMainViewStreamComponent`의 `SetFixedViewportSize`. UGV축에서는 셋째가 이긴다(§2.3).
   Graphics 탭에 "해상도"를 넣으면 **RTSP 송출 해상도와 정면 충돌**한다.
4. **씬 캡쳐 캡쳐 주기는 4종류의 독립된 라운드로빈**으로 돌고 있다(CCTV뿐이 아니다) — 전부
   `GFrameCounter` 기반 틱 카운트 게이트, 전부 C++, 대부분 `UPROPERTY(EditAnywhere)`라
   **런타임 변경이 가장 안전하고 효과가 확실한 후보**다(§3.3).
5. **Windows와 Linux의 그래픽 설정이 갈려 있다** — 품질 튜닝 블록(`sg.*` 12개 + Lumen/VSM)이
   `WindowsEngine.ini`의 `[ConsoleVariables]`에만 있어서, Linux 빌드는 그 튜닝을 하나도 안
   받는다(§1.7). *(2026-09-03: `DefaultEngine.ini`에도 `[ConsoleVariables]`가 생겼지만 거긴
   물리 결정성 값뿐이라 이 결론은 그대로.)*

---

## 0-1. 조사 방법 / 한계

- **방법**: `Config/**/*.ini` 전수 읽기, `Source` + `Plugins` 전수 grep
  (`SceneCaptureComponent2D` / `RoundRobin` / `GameUserSettings` / `Scalability` /
  `IConsoleVariable` / `Fullscreen`), 엔진
  `C:\Program Files\Epic Games\UE_5.8\Engine\Config\BaseScalability.ini`와 대조.
- **한계 1 — 에디터 미실행**: 이 세션에는 unreal-mcp가 안 붙어서 블루프린트 저작값을
  라이브로 못 읽었다. `.uasset`의 문자열 테이블로 **어떤 프로퍼티가 오버라이드돼 있는지**
  까지만 확인했고(값은 바이너리), 값은 기존 문서 기록에 의존한다.
- **한계 2**: 레벨(당시 `kadex_test`, 현재는 `New_kadex_0811`)에 배치된 PostProcessVolume / 라이팅 액터의 저작값은
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

### 1.7 ★ 플랫폼 비대칭 — 품질 튜닝 블록이 Windows에만 있다

> **[2026-09-03 정정]** 원문은 "`[ConsoleVariables]`가 Windows에만 있다"였는데, 2026-08-25에
> `Config/DefaultEngine.ini`에도 `[ConsoleVariables]` 섹션이 신설됐다(`t.MaxFPS=60`,
> `p.UGV.SkidSteer.TorqueNm=1600` — 둘 다 물리 결정성 대책, 그래픽 품질 아님). 두 파일의 같은
> 이름 섹션은 같은 `GEngineIni`로 병합되므로 Windows는 합집합, Linux는 Default 것만 받는다.
> **아래 "품질 튜닝 블록(`sg.*`/Lumen/VSM)이 Windows 전용"이라는 결론은 그대로 유효하다.**

`Config/Windows/WindowsEngine.ini:15`의 `[ConsoleVariables]`에만 `sg.*` 12개 + Lumen/VSM 튜닝이
있다. `Config/Linux/LinuxEngine.ini`에는 `[Linux.SDL]`밖에 없다.

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
SetByConstructor(0x00) < SetByScalability(0x02) < SetByGameSetting(0x03)
  < SetByProjectSetting(0x04) < SetBySystemSettingsIni(0x05) < SetByPluginLowPriority(0x06)
  < SetByDeviceProfile(0x07) < SetByPluginHighPriority(0x08) < SetByGameOverride(0x09)
  < SetByConsoleVariablesIni(0x0A) < SetByPreview(0x0C) < SetByCommandline(0x0D)
  < SetByCode(0x0E) < SetByConsole(0x10)
```
*(UE 5.8 `IConsoleManager.h:155~187` 실측값. 2026-09-03에 중간 단계를 보강했다.)*

낮은 우선순위의 `Set()`은 **조용히 무시**된다. 우리 값들을 대입하면:

| 출처 | 우선순위 | 예 |
|---|---|---|
| `[/Script/Engine.RendererSettings]` (DefaultEngine.ini) | `SetByProjectSetting` (0x04) | `r.Streaming.PoolSize=4096`, `r.LumenScene.*` |
| `[ConsoleVariables]` (Engine ini — Default + 플랫폼 병합) | **`SetBySystemSettingsIni` (0x05)** ← 2026-09-03 정정 | `sg.*`, `r.Lumen.*`, `r.ReflectionMethod=3`, `r.Shadow.Virtual.*`, `t.MaxFPS` |
| `Scalability::SetQualityLevels()` (= `ApplySettings()`의 스케일러빌리티 부분) | **`SetByScalability`** (0x02, 거의 최하위) | Graphics 탭이 쓰려던 경로 |
| `UKismetSystemLibrary::ExecuteConsoleCommand()` / 콘솔 입력 | `SetByConsole` (0x10, 최상위) | |

> **[2026-09-03 정정]** 원문은 `[ConsoleVariables]`를 `SetByConsoleVariablesIni`(0x0A)로 적었으나
> **`ECVF_SetBySystemSettingsIni`(0x05)가 맞다** — `ConfigCacheIni.cpp:6971`,
> `ApplyCVarSettingsFromIni(TEXT("ConsoleVariables"), *GEngineIni, ECVF_SetBySystemSettingsIni)`.
> `SetByConsoleVariablesIni`는 `Engine/Config/ConsoleVariables.ini`의 `[Startup]` 섹션 전용이다.
> 0x05도 `SetByScalability`(0x02)/`SetByProjectSetting`(0x04)보다 높으므로 **아래 결론은 그대로**.

**결론**: ~~`UGameUserSettings::SetShadowQuality(n)` + `ApplySettings()` 를 그대로 붙이면,
그 그룹 안에서 **프로젝트가 안 건드린 cvar만 바뀌고, 하드코딩한 cvar는 그대로 남는다.**~~

> **[2026-09-03 실측으로 정정 — 결론이 더 나쁘다]** "반만 먹는다"가 아니라 **아무것도 안 먹는다.**
> `sg.*` 12개가 전부 `SystemSettingsIni`(0x05)로 고정돼 있어서 `Scalability::SetQualityLevels`의
> `Set(v, ECVF_SetByScalability)`(0x02)가 **`sg.*` 자체부터 거부**당하고, 그룹 멤버는 `sg.*`의
> `SetOnChangedCallback`이 떠야만 적용되므로 **콜백이 안 뜨면 멤버도 하나도 안 바뀐다.**
> 즉 `UGameUserSettings` 경로는 **완전 no-op**이다. 실측 데이터와 우회 경로 4가지는 §0-2 F 참고.
> 실용적 진입점은 **`Scalability::SetQualityLevels(Levels, /*bForce=*/true)`**
> (`SetWithCurrentPriority`를 써서 `sg.*`를 통과시킴 → 그때부터 진짜 "반만 먹는" 상태가 됨).

> **[2026-09-03 중요 보강]** 위 결론은 **스케일러빌리티 그룹에만** 해당한다. `UGameUserSettings`의
> 다른 항목들은 각자 다른 경로/우선순위를 쓰고 **하드코딩을 이긴다** — 특히 `FrameRateLimit`은
> `UEngine::SetMaxFPS`가 cvar의 **기존 SetBy 이유를 그대로 승계**해서 쓰기 때문에
> (`ThisSetReason = LastSetReason`, `UnrealEngine.cpp:12247`) 동일 우선순위로 통과한다. 항목별
> 표는 §0-2 B-1 참고. 즉 "GameUserSettings는 전부 막힌다"로 일반화하면 안 된다.

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
AudioQualityLevel=0
DynamicResolutionFrameTarget=0.000000
bUseHDRDisplayOutput=False   HDRDisplayOutputNits=1000
Version=5
```

> **[2026-09-03 갱신]** `FrameRateLimit` 줄이 이 파일에서 **삭제됐다**(원래 `0.000000`이었음).
> 대신 `Config/DefaultGameUserSettings.ini`(2026-08-25 신설)의 `FrameRateLimit=60.000000`이
> 기본값으로 적용된다 — Saved 파일에 값이 남아 있으면 그쪽이 이기기 때문에 일부러 지운 것.
> 그 ini 파일의 주석은 **Graphics 탭 세션 앞으로 남긴 메모**이기도 하다("프레임 상한은 이
> GameUserSettings 경로를 그대로 쓰는 게 맞다 — 엔진 표준 경로이고 저장/로드가 이미 구현돼 있음").
> 다만 값의 **성격**이 성능 옵션이 아니라 물리 결정성 대책이라는 점은 §0-2 C-1 참고.

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
| `UGameUserSettings::FrameRateLimit` | **`60.0`** (2026-08-25 변경, 이전 `0.0`=무제한) | 런타임 변경 완전 가능(`SetFrameRateLimit` + `ApplyNonResolutionSettings`). **단 자유롭게 열면 안 됨 — §0-2 C-1** |
| `bUseVSync` | `False` | 런타임 변경 가능(`SetVSyncEnabled`, `ECVF_SetByGameSetting`) |
| `bUseDynamicResolution` | `False` | 런타임 변경 가능 |
| `t.MaxFPS` | **`60`** (`DefaultEngine.ini` `[ConsoleVariables]`, 2026-08-25 신설) | `FrameRateLimit`이 `UEngine::SetMaxFPS`로 이걸 덮어쓴다 — 값을 바꿀 땐 **두 곳을 같이** 바꿔야 함(ini 주석) |

> **[2026-09-03 ★] 프레임 상한은 그래픽 옵션이 아니라 물리 결정성 대책이다.**
> `bTickPhysicsAsync=false`(엔진 기본)라 물리 dt가 프레임 dt를 그대로 쓰기 때문에, PC 성능에
> 따라 차량 거동이 달라졌다(고사양 PC에서 UGV가 속도를 못 이기고 장애물에 부딪히던 증상).
> `MaxPhysicsDeltaTime`(1/30)이 느린 쪽을 이미 막고 있으므로 빠른 쪽만 60으로 막아 dt 편차를
> 4.8배(6.9~33.3ms) → 2배(16.7~33.3ms)로 줄인 것이다. **Graphics 탭에서 이 값을 올리게 하면
> 차량 거동이 바뀐다.** 상세 근거는 `Config/DefaultEngine.ini` `[ConsoleVariables]` 주석.

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
| 6 | ~~`GimbalCamera`~~ → **`GimbalCapture`** (드론뷰) | ~~`AUAVPawn`~~ → **`ADronePawn`** | `Drone/DronePawn.cpp:306` | ~~640×360~~ → **`CameraRenderTargetSize` 1280×720** | ~~`selfdefense/uav_camera`~~ → **`selfdefense/uav_gimbal`** |
| 7 | `BattlefieldCapture` (전장/환경 카메라) | `ATitanTruck` | `TitanTruck.cpp:257` | `BattlefieldRenderTargetSize` = **640×360** | `selfdefense/env_camera` |

> **[2026-09-03] #6 교체됨** — 드론 물리 재구현으로 `AUAVPawn`/`BP_UAV`가 `ADronePawn`/`BP_Drone`
> 으로 대체됐다(`vehicle/drone/2026-09-01_drone_replaces_bp_uav.md`). 구 `AUAVPawn` 코드는 아직
> 남아 있지만 **`New_kadex_0811`에 배치된 건 `BP_Drone`뿐**이며, 2-PC 실환경 검증 후 제거 예정.
> 캡쳐 패턴(CineCamera 참조 + 런타임 `NewObject` 캡쳐 + 수동 `CaptureScene()`)은 동일하다.
> 차이점 표는 §0-2 D 참고 — RT가 2배 이상 커졌고(1280×720), `bDisableGimbalCapture` 게이팅이
> 생겼고, 피격 셰이크(`FScopedCaptureViewShake`)는 **적용하지 않는다**(반사 패리티만).
>
> **[2026-09-03] 실사용 UGV BP도 교체됨** — `BP_UGV_Vehicle` → **`BP_UGV_0901`**
> (`Content/Vehicles/UGV/UGV_0901/`, 2026-09-02 신규 6×6 차륜 모델). `#1`/`#2~5`의 소유 액터가
> 이걸로 바뀌었을 뿐 컴포넌트 구조는 동일.

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
| 3 | **드론 짐벌** (구 UAV 짐벌) | 동일 | **`Drone/DronePawn.cpp:776-781`** (구: `Vehicles/UAVPawn.cpp:352-364`) | `GimbalRoundRobinCount=2`, `Slot=1` (**`DronePawn.h:304,307`**) — 값 동일 | 게임틱 / 2 |
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

**BP 저작값** *(2026-09-03 재확인)*: **`Content/Vehicles/UGV/UGV_0901/BP_UGV_0901.uasset`**
(구 `BP_UGV_Vehicle`에서 교체됨)의 문자열 테이블에 `CaptureRoundRobinCount` / `RenderTargetSize` /
`CameraFOV`가 존재 → **BP에서 오버라이드돼 있음**(구 BP의 값이 그대로 승계된 것으로 보임).
`rtsp/rtsp_latency_investigation.md` §2 #11 기록에 따르면 **2 → 1로 변경 후 저장 확인됨
(`is_dirty=false`)**. `BP_TitanTruck`은 `RenderTargetSize` / `CameraFOV`만 오버라이드하고
라운드로빈은 C++ 기본값을 쓴다. **`BP_Drone`은 캡쳐 관련 오버라이드가 하나도 없다** → C++ 기본값
(1280×720, Count=2/Slot=1) 그대로. (값 자체는 에디터 재확인 필요 — §8-4.)

**[2026-09-03] 캡쳐 게이팅 플래그가 3종으로 늘었다.** `URCWSComponent::bDisableSightCapture`에
더해 **`ADronePawn::bDisableGimbalCapture`**(`DronePawn.cpp:258`, "이 프로세스에선 짐벌 화면을
볼 곳이 없다")와 **`ATitanTruck::bDisableBattlefieldCapture`**(`TitanTruck.h:165`)가 신설됐다.
전부 축 게이팅 용도 — 즉 **자기 축이 아닌 프로세스에서는 해당 캡쳐가 아예 안 돈다.**
§6 A-3(캡쳐 주기 드롭다운)은 이 게이팅을 대체하는 게 아니라 그 **위에 얹는** 형태로 설계할 것.

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
| 프레임레이트 상한 | `SetFrameRateLimit` + `ApplyNonResolutionSettings`. `UEngine::SetMaxFPS`가 `t.MaxFPS`의 기존 우선순위를 승계해서 쓰므로 ini를 이긴다(§0-2 B-1). ⚠ **범위는 60 이하로 제한할 것** — §0-2 C-1 |
| 스크린 퍼센티지(해상도 스케일) | `sg.ResolutionQuality` 또는 `r.ScreenPercentage` — **스케일러빌리티 그룹 중 유일하게 하드코딩과 충돌 없음** |
| 캡쳐 주기(드론짐벌 / 전장) | `GimbalRoundRobinCount`(`ADronePawn`) / `BattlefieldRoundRobinCount` 직접 대입. RCWS(`CaptureRoundRobinCount`)는 캡쳐 자체가 꺼져 있어 효과 없음 |
| 캡쳐 주기(CCTV) | **소코드 변경 후** 가능(§3.3) |
| RCWS TemporalAA | `URCWSComponent::bEnableTemporalAA` (다음 틱 반영) |
| RT 필터(Nearest/Bilinear) | `URCWSComponent::SightRenderTargetFilter` |
| 동적 해상도 | `SetDynamicResolutionEnabled` (현재 false) |

> **[2026-09-03] "창 모드(창/전체화면)"를 이 표에서 뺐다** — `SetFullscreenMode` 자체는 여전히
> 런타임에 동작하지만, 실제 운용이 `-fullscreen` 런치 인자(커맨드라인 0x0D)라 탭에서 바꿔도
> 다음 실행에 덮인다. §6 B-8로 내렸다.

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

> **[2026-09-03] 이 절은 §10으로 대체됐다.** 실측(§0-2 F)과 구조 조사(§9-2)로 등급이 바뀐
> 항목이 여러 개다(특히 렌더 스케일이 씬 캡쳐에 효과가 없다는 S-1). **최종 후보는 §10을 볼 것.**
> 이 절은 그 등급이 어떻게 나왔는지의 근거 기록으로 남긴다.

### A등급 — 이번에 넣기 권장 (충돌 없음, 즉시 반영, 효과 명확)

| # | 항목 | UI 컨트롤 | 범위/옵션 | 비고 |
|---|---|---|---|---|
| A-1 | 렌더 스케일 (Screen Percentage) | **슬라이더** | 50~100% (5% 단위) | **여전히 1순위.** 단 **2026-09-03 실측으로 적용 경로가 바뀐다** — `sg.ResolutionQuality`도 핀돼 있어 `SetResolutionScaleNormalized()+ApplySettings()`는 no-op다. **`r.ScreenPercentage`(실측 `Constructor` = 무주공산)를 직접 세팅할 것**(§0-2 F) |
| A-2 | 프레임레이트 상한 | **드롭다운** | ~~무제한 / 144 / 120 / 60 / 30~~ → **60(기본) / 30** | ⚠ **2026-09-03 재설계** — 60은 물리 결정성 대책이라 **위로 올리는 선택지를 주면 안 된다**(§2.4 ★, §0-2 C-1). 적용 경로는 `FrameRateLimit`이 맞음(ini 주석의 권고). 바꾸면 A-3 갱신률도 같이 흔들림 |
| A-3 | 카메라 피드 갱신 주기 | **드롭다운** ×1 (묶음) | 최고(1) / 높음(2) / 보통(4) / 낮음(8) | `*RoundRobinCount` + CCTV `% N`을 한 값으로 묶는 안. **2026-09-03: 실제 대상은 CCTV·드론짐벌·전장카메라 3종**(RCWS는 양 축 모두 캡쳐가 꺼져 있음). 기존 축 게이팅 플래그 위에 얹을 것 |
| A-4 | 수직 동기화 | **토글** | On / Off (현재 Off) | 패키지에선 정상 동작(`ECVF_SetByGameSetting`, 막는 상위값 없음). ⚠ **에디터에서는 안 먹는 게 정상** — 엔진 `BaseEngine.ini [SystemSettingsEditor] r.VSync=0` 때문에 GameUserSettings가 세팅을 스킵한다. **이 항목만은 패키지에서 검증할 것**(§0-2 F-2) |
| A-5 | 동적 해상도 | **토글** | On / Off (현재 Off) | 켜면 `DynamicResolutionFrameTarget` 슬라이더 동반 필요 |
| ~~A-6~~ → B-8 | 창 모드 | 드롭다운 | 창 / 전체화면 | ⚠ **2026-09-03 B등급으로 강등** — 실제 운용이 런치 인자(`./titan_example.sh -fullsystem -fullscreen`)이고 커맨드라인(0x0D)이 GameUserSettings보다 높아 다음 실행에 덮인다. §8-8 검증도 선행 필요 |

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
A등급 중 `UGameUserSettings` 소관(A-1 / A-2 / A-4 / A-5)은 `ApplySettings(false)` +
`SaveSettings()`로 `GameUserSettings.ini`에 맡기고, 프로젝트 고유 값(A-3 캡쳐 주기)만
별도 보관처(`UGameInstanceSubsystem` + `Config=Game` — `UStreamResolutionSubsystem`과 동일 패턴)를
쓰는 게 기존 관례와 맞는다.

> **[2026-09-03] 패키징 함정 — Input 탭에서 실제로 터진 것.** 상세는 §0-2 B-4.
> 요약: 경로 문자열로만 참조되는 애셋은 패키지에서 빠진다. Graphics 탭이 프리셋 DataAsset/커브를
> 만들게 되면 **생성자 `ConstructorHelpers::FObjectFinder`로 하드 레퍼런스를 잡을 것**
> (`DirectoriesToAlwaysCook`도 같이 넣되, 그것만 믿지 말 것). PIE/에디터에서는 절대 재현되지 않는다.

> **[2026-09-03] 기본값 배포 경로.** 프레임 상한 작업(2026-08-25)이 만든 선례대로,
> `UGameUserSettings` 소관 항목의 프로젝트 기본값은 **`Config/DefaultGameUserSettings.ini`**에
> 넣으면 된다. 단 각 PC의 `Saved/Config/<Platform>/GameUserSettings.ini`에 값이 남아 있으면
> 그쪽이 이기므로, 기본값을 바꿀 땐 그 파일의 해당 줄을 지우거나 같이 바꿔야 반영된다.

---

## 7. 다른 트랙과 겹치는 항목 (명시)

| 항목 | 겹치는 트랙 | 이번 세션에서의 처리 |
|---|---|---|
| SceneCapture의 SSR/Lumen 반사 누락 (`ApplyMainViewReflectionParity`) | **`camera_pipeline/rtsp_postprocess_parity_0820.md`** *(2026-08-31 재편으로 `rtsp/` → `camera_pipeline/` 이동)* — 원인 확정 + 코드 수정 완료 | **재조사하지 않음.** Graphics 탭에서 반사 품질을 노출하면 이 보정 로직과 상호작용하므로 그 세션 결과를 먼저 볼 것. 2026-09-03 재확인: 이 로직 자체는 무변경 |
| 피격 카메라 셰이크가 캡쳐에 안 닿는 문제 (`FScopedCaptureViewShake`) | 동일 + **`rcws/2026-08-31_selfdefense_camera_shake_bugs.md`** | **2026-08-31에 재작성됨** — `UViewShakeProbeCameraModifier` 신설로 "한 프레임 어긋난 POV 샘플" 버그 수정(자체방호축 환경카메라/CCTV 떨림의 원인이었음). **2-PC 실환경 검증 대기.** Graphics 탭과 직접 충돌은 없음 |
| `r.ReflectionMethod=3` (유효 범위 밖, Windows=SSR / Linux=Lumen 분기) | 위 문서 §1 끝 + `rtsp_resolution_customization_0820.md` §9 | **미해결 상태로 남아 있음.** Graphics 탭에 반사 항목을 넣으려면 **이걸 먼저 정리해야 한다**(의도 확인 필요) |
| `LumenSurfaceCacheResolution`이 씬 캡쳐에서만 0.5 | `rtsp_postprocess_parity_0820.md` §5 | Linux 빌드에서 반사 디테일이 메인 뷰보다 거칠 수 있음. CineCamera Override로 1.0 가능 |
| RTSP 송출 해상도(축별 커스텀) | **`rtsp/rtsp_resolution_customization_0820.md`** — 양 축 완료, 리눅스 실측까지 확인 | §4에 후보로 정리만 하고 **판단은 사용자에게**. 기본 권고: RTSP 영역에 남김 |
| UGV축 메인 뷰포트 렌더 해상도 고정 | 동일 | Graphics 탭의 "해상도" 항목과 **정면 충돌** — §2.3. 넣지 않기를 권고 |
| 축 선택 화면(`UAxisSelectionWidget`)의 width/height | 사용자 명시: **네트워크 설정** | 어떤 탭도 건드리지 않음(`feedback_ingame_settings_scope`) |
| 리눅스 Wayland/X11 | `linux_wayland_x11_present_bottleneck.md` | 커스텀 후보 제외 권고 — §1.4 |

---

## 8. 확인 필요 / 미확정 (다음 단계 전 처리)

1. ~~**[실측] cvar 우선순위 확정**~~ → ✅ **2026-09-03 완료. 결과는 §0-2 F.**
   `DumpCVars -csv` 한 줄(에디터 콘솔)로 9,670개 전수 덤프 → `Saved/Logs/ConsoleVars.csv`.
   결론: `r.Shadow.Virtual.MaxPhysicalPages,1024,SystemSettingsIni` → §1.8 판정 확정.
   **더 나아가 `UGameUserSettings` 품질 경로는 "반만"이 아니라 완전 no-op임이 확인됐다.**
   아래는 절차 기록(재측정이 필요할 때 참고).

   **A/B 테스트가 필요 없다.** UE 콘솔은 cvar를 값 없이 조회하면 **누가 마지막에 세팅했는지를
   같이 찍어준다**(`ConsoleManager.cpp:3247`):
   ```
   r.Shadow.Virtual.MaxPhysicalPages
   → r.Shadow.Virtual.MaxPhysicalPages = "1024"      LastSetBy: SystemSettingsIni
   ```
   `LastSetBy: SystemSettingsIni`면 **§1.8 판정 확정** — `SetByScalability`(0x02)는
   `SetBySystemSettingsIni`(0x05)를 못 이기므로 품질 드롭다운으로는 절대 안 바뀐다.
   `LastSetBy: Scalability`면 반대로 그 cvar는 자유롭게 바뀐다는 뜻.
   한 번에 훑으려면 `DumpCVars r.Shadow.Virtual` / `DumpCVars sg.` / `DumpCVars r.Lumen -csv`
   (`-csv`는 `Saved/Logs/`에 파일로 떨어짐).

   **PIE도 패키지 빌드도 필요 없다** — 이유 셋:
   - cvar 상태는 **프로세스 단위**다. 에디터와 PIE는 같은 프로세스·같은 cvar 테이블이고, PIE에
     들어간다고 `[ConsoleVariables]`가 다시 적용되거나 우선순위가 바뀌지 않는다.
   - `Config/Windows/WindowsEngine.ini`는 **에디터에서도 로드된다**. config 계층의 `<Platform>`은
     `FPlatformProperties::IniPlatformName()`(= 실행 중인 플랫폼 "Windows")이라 에디터/게임이
     같다. 프로젝트 자체 근거: `DefaultEngine.ini` `[ConsoleVariables]` 주석 "에디터에도
     적용된다. 작업 중 일시 해제는 콘솔에서 `t.MaxFPS 0`".
   - `UGameUserSettings::ApplySettings`(→ `Scalability::SetQualityLevels`, `SetByScalability`)는
     **에디터 시작 때도 돈다**(`EditorEngine.cpp:1372-1376`, `ApplySettings(true)`). 즉 우선순위
     충돌이 패키지 게임과 같은 형태로 에디터에서도 이미 벌어져 있다.

   ⚠ **함정** — `sg.ShadowQuality 3`을 쳐서 "거부됨" 로그를 보려는 방식은 기본 설정에서 **안
   보인다**. 엔진이 `OldPri == SetBySystemSettingsIni`인 경우를 **Verbose**로 로깅하기 때문
   (`ConsoleManager.cpp:293-296`, 주석: *"Set by an ini that has to be hand edited, a deliberate
   fail"*). 굳이 보려면 먼저 `log LogConsoleManager Verbose`.

   ⚠ 검증 대상은 반드시 **스케일러빌리티 그룹 멤버 cvar**여야 한다. `t.MaxFPS`는 `SetMaxFPS`가
   기존 우선순위를 승계하는 별도 경로라 반례로 잡힌다(§0-2 A-3/B-1) — "GameUserSettings가
   이기더라"를 보고 §1.8이 틀렸다고 결론내면 안 된다.

   **반대로 에디터로는 확인 못 하는 것**(패키지/standalone 필요):
   - **리눅스 쪽 값** — `WindowsEngine.ini`를 안 받으므로 시작값 자체가 다르다(§1.7, §8-6).
   - **§8-8 풀스크린 + `SetFixedViewportSize`** — PIE는 `UnrealEdEngine`이라 원래부터 전용 RT
     경로고 `-fullscreen`도 없다. 이건 반드시 패키지/standalone에서.
   - 에디터 뷰포트 스케일러빌리티는 `EditorPerProjectUserSettings.ini`가 따로 몰기도 하므로,
     "**패키지에서 실제로 어떤 값으로 시작하나**"는 패키지에서 봐야 한다(우선순위 판정과는 무관).
2. **[사용자 판단] §1.8의 (A)/(B)/(C) 중 어느 방향으로 갈 것인가.**
3. **[사용자 판단] §4의 RTSP 항목을 Graphics 탭에 넣을 것인가.**
4. **[에디터 확인] BP 저작값** — **`BP_UGV_0901`**(구 `BP_UGV_Vehicle`에서 교체)의
   `CaptureRoundRobinCount` / `RenderTargetSize` / `CameraFOV`, `BP_TitanTruck`의
   `RenderTargetSize` / `CameraFOV` 실제 값. `BP_Drone`은 오버라이드 없음(확인 완료).
   (2026-08-21·2026-09-03 두 세션 모두 unreal-mcp 미연결이라 오버라이드 **존재 여부**만 확인함.)
5. **[에디터 확인] 레벨 PostProcessVolume / 라이팅 액터 저작값** — 대상 레벨이
   ~~`kadex_test`~~ → **`New_kadex_0811`**로 바뀌었다(패키징 대상도 `kadex_lobby` +
   `New_kadex_0811` 2개뿐, `kadex_test`는 2026-09-01 제외). 배치 확인됨: PostProcessVolume 5,
   DirectionalLight 6, ExponentialHeightFog 6, HDRIBackdrop 10, SkyLight 2.
   노출/색보정을 Graphics 탭에 넣을 생각이면 필요하며, 이 레벨은 이미 노출 기준이
   잡혀 있다(노출배율 1e-4, 지면 200nit — `sfx_vfx/` VFX nit 트랙)는 점을 전제로 할 것.
6. ~~**[확인] Linux 빌드의 실제 `r.AntiAliasingMethod` 값**~~ → ✅ **해소(§9-2 S-8).**
   엔진 cvar 기본값이 `4`(TSR)로 선언돼 있다(`SceneView.cpp:236`). 리눅스도 TSR.
7. **[결정] `Config/Windows/WindowsEngine.ini`의 `r.ReflectionMethod=3`** — 의도인지 오타인지.
   Windows/Linux 룩 분기의 원인이고 Graphics 탭 반사 항목의 전제.
8. ~~**[검증 ★우선순위 상향]**~~ → **우선순위 내림(2026-09-03).** 사용자가 "창 모드는 이미
   최적 상태로 맞췄으니 건드리지 말 것"으로 확정 — 운용 중 문제가 없다는 게 실증된 셈이고
   Graphics 탭도 이 항목을 안 건드린다. 기록으로만 남긴다.
   **[원문] 풀스크린이 UGV축 RTSP 스트림에 미치는 영향** —
   `bPinViewportResolution=true` + `SetFixedViewportSize` 상태에서 풀스크린 전환 시 백버퍼/뷰포트
   불일치가 안 나는지. 과거 이 조합에서 어서션 크래시 이력 있음
   (`rtsp_resolution_customization_0820.md` §5-1 크래시 1).
   **2026-09-03: 가설이 아니라 현재 운용 조건이다** — 패키징 가이드가 `./titan_example.sh
   -fullsystem -fullscreen`을 정식 실행 방법으로 안내한다(`packaging/` 2건). Graphics 탭에
   창 모드를 넣든 안 넣든 이 조합 자체는 이미 돌고 있으므로, 탭과 무관하게 확인해 둘 것.

### [2026-09-03 신규] 추가 확인 항목 (일부는 §9/§10에서 해소됨)

9. **[사용자 판단] 프레임 상한을 Graphics 탭에 노출할 것인가** — 노출한다면 60 이하로만
   (§0-2 C-1). 아예 안 넣고 A-1 렌더 스케일만 두는 것도 선택지다.
10. **[확인] 드론 짐벌에 피격 셰이크가 빠진 것이 의도인지** — RCWS/CCTV/전장카메라는
    `FScopedCaptureViewShake`를 적용하는데 `ADronePawn`은 반사 패리티만 적용한다
    (`DronePawn.cpp:779-781`). 공중에 뜬 드론이라 지상 피격 셰이크가 안 실리는 게 오히려
    맞을 수 있다 — 의도면 그대로 두고 문서에만 남기면 된다. Graphics 탭 범위는 아니고
    `camera_pipeline/` 트랙 쪽 항목.
11. **[정리 대기] 구 `AUAVPawn`/`BP_UAV` 제거 후 §3.1 표 재확인** — 2-PC 검증 통과 시
    제거될 예정이므로(`CURRENT_STATE.md` §9), 그때 씬 캡쳐 개수가 한 번 더 줄어든다.

---

## 9. 채택 방향 — ini 하드코딩 제거 + 단일 소스 (2026-09-03 설계 논의)

§1.8의 (A)/(B)/(C) 중 **(B) "ini 하드코딩을 걷어내고 주인을 옮긴다"** 방향으로 정리 중.
다만 실측(§0-2 F)과 아래 §9-2 조사를 거치면서 **"ini를 걷어내는 것만으로는 오히려 상황이
나빠진다"**는 게 드러났다. 이 절은 그 이유와 대안 구조를 남긴다. *(구현 착수 전 설계안 —
사용자 검토 대기)*

### 9-1. 왜 "ini 걷어내기"만으로는 안 되는가

요구사항이 3개였다(사용자, 2026-09-03):

1. 에디터에서 **실시간**으로 품질이 바뀔 것
2. **기본값을 현재 하드코딩된 값**으로 그대로 가져올 것
3. **에디터에서 설정한 값이 PIE/패키지에도 그대로** 나올 것 — "에디터는 A인데 패키지는 B"를 막을 것

1·2는 핀만 걷어내면 거의 공짜다. **문제는 3이다.**

```
엔진 기본 (LaunchEngineLoop.cpp:2866)
  에디터/PIE : Scalability::LoadState(GEditorSettingsIni)
               ← Saved/Config/WindowsEditor/EditorSettings.ini   (개발자 PC 로컬, P4 안 올라감)
  패키지     : Scalability::LoadState(GGameUserSettingsIni)
               ← Saved/Config/<Platform>/GameUserSettings.ini (+ Config/DefaultGameUserSettings.ini)
```

**읽는 파일이 애초에 다르다.** 즉 "에디터 A / 패키지 B"는 버그가 아니라 **엔진이 보장하는 동작**
이고, 지금 그 현상이 안 보이는 유일한 이유가 `[ConsoleVariables]` 하드코딩이 양쪽에 다 먹고
있어서다. → **`sg.*`를 그냥 걷어내면 지금 걱정하는 문제가 새로 생긴다.**

### 9-2. ★ 이번에 새로 찾은 구조적 걸림돌

| # | 내용 | 근거 | 영향 |
|---|---|---|---|
| S-1 | **씬 캡쳐는 스크린 퍼센티지를 안 받는다.** 엔진이 씬 캡쳐 뷰패밀리에 `ScreenPercentage=false` + 해상도 배율 1.0을 강제한다(주석 그대로: *"Screen percentage is still not supported in scene capture"*). `bMainViewResolution`을 켜야 상속되는데 이 프로젝트는 **의도적으로 off**(`bEnableMainViewResolution=false`) | `SceneCaptureRendering.cpp:951-955` | ★ **렌더 스케일(A-1)은 메인 뷰 전용 레버다.** CCTV/드론짐벌/전장카메라 비용은 1원도 안 준다. 씬 캡쳐 비용을 줄이는 레버는 **캡쳐 주기와 캡쳐 RT 크기뿐** |
| S-2 | **PIE는 프로젝트의 스크린 퍼센티지를 무시한다.** `r.Editor.Viewport.OverridePIEScreenPercentage=1`(기본 켜짐). 툴팁: *"Override project's default screen percentage settings with editor viewports' settings in PIE"*. 게다가 Editor Preferences(사용자별)라 **개발자마다 다르다** | `EditorPerformanceSettings.h:109-112`, `LegacyScreenPercentageDriver.cpp:205-211` | A-1을 **PIE로 검증하면 패키지와 안 맞는다.** 프로젝트 기본으로 `0`을 박아둘 것 |
| S-3 | 에디터/게임 스케일러빌리티 **소스 ini가 다름** | `LaunchEngineLoop.cpp:2866` | §9-1. 단일 소스 설계의 근거 |
| S-4 | **VSync는 에디터에서만 핀돼 있다** — 엔진 `BaseEngine.ini [SystemSettingsEditor] r.VSync=0` | §0-2 F-2 | VSync 검증은 반드시 패키지에서 |
| S-5 | **`Config/*.ini`가 P4 read-only다**(`-r--r--r--` 확인). `UDeveloperSettings`+`defaultconfig`는 Project Settings에서 편집 시 `Config/DefaultGame.ini`에 쓴다 | 파일 권한 실측 | 편집하려면 **P4 체크아웃 선행**. 에디터 소스컨트롤 연동이 프롬프트를 띄우지만, 체크아웃 안 하면 조용히 저장 실패할 수 있음 |
| S-6 | **ReadOnly cvar 확정** — `r.Nanite.ProjectEnabled` / `r.Substrate` / `r.AllowStaticLighting`이 전부 `ECVF_ReadOnly` | `RenderUtils.cpp:36,2072`, `ConsoleManager.cpp:4241` | 재시작으로도 안 되고 **프로세스 재시작 필수**. 탭 후보에서 완전 제외 |
| S-7 | **품질 변경은 RTSP 화질에도 그대로 반영된다** — 씬 캡쳐가 메인 뷰와 같은 렌더러/같은 cvar를 쓰므로 `sg.*`가 그대로 먹는다(스크린 퍼센티지만 예외, S-1) | S-1의 반대편 | 품질을 낮추면 **상위체계로 나가는 영상 품질도 같이 떨어진다.** 운용상 의미가 있으니 UI에 명시 필요 |
| S-8 | **`r.AntiAliasingMethod`는 ReadOnly가 아니다**(`ECVF_RenderThreadSafe`), 엔진 기본값이 **4(TSR)** | `SceneView.cpp:236-246` | §8-6(리눅스 AA 값 확인) **해소** — 리눅스도 TSR이다. AA 방식은 런타임 변경 가능 |

### 9-3. 대안 구조 — `UDeveloperSettings` 단일 소스

```cpp
UCLASS(config = Game, defaultconfig, meta = (DisplayName = "Titan Graphics Defaults"))
class UTitanGraphicsSettings : public UDeveloperSettings
{
    // sg.* 12개 + 렌더 스케일 + 캡쳐 주기 …
};
```

| 요구 | 해결 지점 |
|---|---|
| 에디터 실시간 | `PostEditChangeProperty` → `Scalability::SetQualityLevels(L, /*bForce=*/true)` + cvar 직접 세팅 |
| 기본값 승계 | C++ 기본값 + `Config/DefaultGame.ini`에 현재 하드코딩 값 그대로 이관 |
| **에디터=PIE=패키지** | `defaultconfig` → `Config/DefaultGame.ini` 저장 = **P4 공유 + 패키징 포함**. 에디터·게임 **양쪽** `FCoreDelegates::OnPostEngineInit`에서 동일 함수 호출 → **읽는 파일이 하나** |
| 인게임 탭 | 이걸 "공장 기본값"으로 읽고, 사용자 변경분만 `UGameUserSettings`에 저장 |

**소유 3층 구조**

```
① Config/DefaultGame.ini  (UTitanGraphicsSettings)   ← 프로젝트 기본값, P4 공유, 에디터/PIE/패키지 공통
② Saved/.../GameUserSettings.ini                      ← 최종 사용자가 인게임 탭에서 바꾼 값
③ 런타임 cvar                                          ← ①을 적용한 뒤 ②로 덮어쓴 결과
```

### 9-4. ini 이관 계획 (성격별 4분류)

| 분류 | 대상 | 처리 |
|---|---|---|
| **(가)** `sg.*` 12줄 | `WindowsEngine.ini [ConsoleVariables]` | **걷어내고** `UTitanGraphicsSettings`로 이관. **플랫폼 비대칭(§1.7)이 덤으로 해소된다** |
| **(나)** 프리셋 종속 개별 튜닝 (Lumen 8개 + VSM 3개) | 〃 | **지우지 말고 `Config/DefaultScalability.ini`의 `[GlobalIlluminationQuality@1]`/`[ShadowQuality@2]`로 이관.** 엔진 프리셋을 프로젝트가 오버라이드하는 정식 경로(`Scalability`도 `EKnownIniFile`이라 Engine/Game과 동일 계층 로딩 — `ConfigCacheIni.cpp:6399`). 이러면 `SetByScalability`로 적용돼 **우선순위 충돌이 원천 소멸** |
| **(다)** 성격이 다른 것 | `t.MaxFPS`, `p.UGV.SkidSteer.TorqueNm`, `r.Streaming.PoolSize`/`LimitPoolSizeToVRAM`, `r.AntiAliasingMethod` | **그대로 둔다.** 물리 결정성 / VRAM 안전장치 / 방식 선택이라 품질 프리셋 소관이 아님 |
| **(라)** 선행 정리 필요 | `r.ReflectionMethod=3` | 유효 범위(0~2) 밖. **반사 품질을 탭에 열기 전에 의도부터 확정**(§7, §8-7) |

> ⚠ **(나)의 대가**: 튜닝이 "Medium을 골랐을 때만" 적용된다. Epic으로 올리면 엔진 기본값이 나온다.
> 지금 튜닝은 `New_kadex_0811` 숲 기준으로 잡힌 값이라, 모든 품질 단계에서 유지하려면 `@0~@3`에
> 복제해야 한다 — 이건 값 옮기기가 아니라 **"품질 슬라이더가 각 단계에서 뭘 의미하는가"를 정하는
> 설계 작업**이라 (가)보다 훨씬 비싸다.

### 9-5. 제안 순서

1. **(가) + `UTitanGraphicsSettings` 골격** — 저비용, 플랫폼 비대칭 해소, 3번 요구 충족
2. **§10 A등급으로 탭을 일단 동작하게** — (나) 없이 전부 동작함
3. 리허설 후 "품질 프리셋이 실제로 필요하다"가 확인되면 그때 **(나)** 착수

---

## 10. 확정 스코프 (2026-09-03 사용자 결정)

§6의 A/B/C 등급을 실측(§0-2 F) + 구조 조사(§9-2) + **사용자 확정**으로 다시 매긴 최종 목록.
§6과 충돌하면 **이 절이 우선**한다.

**적용 대상 표기**: `메인` = 플레이어 뷰포트(= RCWS 조준화면 + `*/rcws` 스트림) /
`캡쳐` = CCTV 4방·드론 짐벌·전장카메라 씬 캡쳐 / `양쪽`

### 10-1. ★ 이번에 만든다 — 품질 프리셋 계열 (최우선)

사용자 확정: **"B는 다 중요함. 그림자·GI·반사가 가장 중요."**
→ §9-4의 **(가)+(나) 이관이 선택이 아니라 필수 경로**가 됐다.

| # | 항목 | 대상 | 컨트롤 | 선행 조건 |
|---|---|---|---|---|
| Q-1 | **전체 품질 프리셋** | 양쪽 | 드롭다운 4단 + "커스텀" | (가)+(나) |
| Q-2 | **그림자 품질** | 양쪽 | 드롭다운 4단 | (가)+(나) — VSM 3줄 이관 |
| Q-3 | **GI(Lumen) 품질** | 양쪽 | 드롭다운 4단 | (가)+(나) — Lumen 8줄 이관. **가장 비쌈**(§10-4) |
| Q-4 | **반사 품질** | 양쪽 | 드롭다운 4단 | (가)+(나)+**(라) `r.ReflectionMethod=3` 정리** |
| Q-5 | 텍스처 품질 | 양쪽 | 드롭다운 4단 | (가). `r.Streaming.PoolSize`는 VRAM 안전장치라 고정 유지 |
| Q-6 | 시야거리 / 이펙트 / 폴리지 / 셰이딩 / 포스트프로세스 품질 | 양쪽 | 드롭다운 4단 ×5 | **(가)만으로 충분** — 개별 핀 없음(실측 확인) |
| Q-7 | 안티에일리어싱 방식 | 양쪽 | 드롭다운 (TSR/TAA/FXAA/없음) | 없음 — `r.AntiAliasingMethod`, ReadOnly 아님(S-8) |
| Q-8 | 수직 동기화 | 메인 | 토글 | 없음. ⚠ 에디터에선 구조적으로 안 먹음(S-4), 패키지에서 검증 |

> Q-6의 "포스트프로세스 품질"은 `sg.PostProcessQuality`(블룸/DOF/모션블러 **품질 단계**)를
> 말한다. 사용자가 "필요없다"고 한 **포스트프로세스는 §10-3의 레벨 PPV(노출/색보정)** 쪽이다 —
> 성격이 완전히 다르고, 전체 품질 프리셋이 `sg.PostProcessQuality`를 포함하므로 Q-6에서 빼면
> 오히려 프리셋이 반쪽이 된다. *(이 해석이 틀렸으면 Q-6에서 빼면 됨.)*

> ⚠ **S-7**: 품질을 낮추면 **RTSP로 상위체계에 나가는 영상 품질도 같이 떨어진다.**
> 씬 캡쳐가 메인 뷰와 같은 렌더러·같은 cvar를 쓰기 때문. UI에 명시 필요.

### 10-2. ★ 이번에 만든다 — 캡쳐 주기 (카메라별로 분할)

사용자 지적: **"cctv / uav / env 카메라 별로 round robin 이 다 다른데 여러 개로 분할해야
되는 거 아니냐"** → **맞다.** 하나의 드롭다운으로 묶으려던 §6 A-3 안은 폐기.

실제로 세 카메라가 **서로 다른 메커니즘**을 쓴다:

| 카메라 | 현재 메커니즘 | 위치 | 실효 갱신률 |
|---|---|---|---|
| **CCTV 4방** | 인덱스 순환 — 매 틱 **4개 중 1개**만 캡쳐. Count 프로퍼티 자체가 **없음**(하드코딩 `% 4`) | `QuadCamComponent.cpp:270-272` (`RoundRobinIndex`, private) | 각 방향 = 틱/4 |
| **드론 짐벌** | 틱 카운트 게이트 `GFrameCounter % Count == Slot` | `DronePawn.cpp:776-777` | Count=2, Slot=**1** → 틱/2 |
| **전장(환경)** | 동일 | `TitanTruck.cpp:324-325` | Count=2, Slot=**0** → 틱/2 |

**Slot이 설계의 일부다** — 드론(1)과 전장(0)이 같은 Count=2 그룹에서 **일부러 엇갈리게** 잡혀
있어서 같은 프레임에 씬을 두 번 렌더하지 않는다. 하나의 값으로 묶으면 이 짝이 깨진다.

**제안 컨트롤 (3개로 분할)**

| # | 항목 | 대상 | 컨트롤 | 구현 메모 |
|---|---|---|---|---|
| R-1 | CCTV 갱신 주기 | CCTV 4방 | 드롭다운 (틱/4, /8, /12, /16) | **소코드 변경 필요** — `UQuadCamComponent`에 `CaptureEveryNTicks` UPROPERTY 추가해 `TickCaptureTimer()`를 게이트. 각 방향 = 틱/(4×N) |
| R-2 | 드론 짐벌 갱신 주기 | 드론 | 드롭다운 (매틱/2/4/8) | `GimbalRoundRobinCount` 대입 |
| R-3 | 전장 카메라 갱신 주기 | 전장 | 드롭다운 (매틱/2/4/8) | `BattlefieldRoundRobinCount` 대입 |

- **Slot은 UI에 노출하지 않는다.** 설정 적용 시 코드가 자동 배분(드론/전장이 같은 Count면
  Slot 0/1로 엇갈리게, 다르면 충돌 최소화 배분).
- **축에 따라 살아있는 카메라가 다르다** — UGV 프로세스는 CCTV 4방만, 자체방호 프로세스는
  CCTV 4방 + 전장 + 드론 짐벌. 게다가 `bDisableGimbalCapture` / `bDisableBattlefieldCapture` /
  `bAlwaysVisible||bVisible`(CCTV) 게이팅이 이미 있다(§3.3, B-3). UI는 **현재 축에서 실제로
  도는 것만 보여주거나**, 전부 보여주되 안 도는 건 비활성 표시할 것.
- ★ **이게 씬 캡쳐 비용을 줄이는 유일한 레버다**(S-1 — 렌더 스케일은 씬 캡쳐에 효과 0).

### 10-3. 이번에 안 만든다 (사용자 확정)

| 항목 | 사용자 판단 | 비고 |
|---|---|---|
| **프레임레이트 상한** | **필요 없음** | 물리 결정성 대책으로 60 고정 유지(§2.4 ★). 탭에 안 넣으면 그 리스크도 같이 사라짐 |
| **창 모드 / 풀스크린** | **건드리지 말 것 — 이미 최적 상태** | 운용이 `-fullscreen` 런치 인자로 확정돼 있음. §8-8 검증도 우선순위 내림(운용 중 문제 없음이 실증됨) |
| **레벨 PostProcessVolume**(노출/색보정/블룸) | **지금은 필요 없음** | `New_kadex_0811`은 노출 기준이 이미 잡혀 있음(1e-4, 지면 200nit — `sfx_vfx/` VFX nit 트랙). 열면 VFX 밝기가 통째로 어긋남 |
| 동적 해상도 | 미언급 → 제외 | 렌더 스케일 계열이고, 프레임 상한을 안 여는 이상 목표 프레임 개념이 애매 |

### 10-4. 보류 — 축/RTSP와 얽혀 있어 추가 검토 필요

사용자: **"실행 축(ugv/selfdefense), rtsp 등등 관련된 게 많아서 이건 좀 더 생각해봐야 함."**

| 항목 | 축 선택 화면과 겹치나 | 정확한 관계 |
|---|---|---|
| **캡쳐 해상도** | **겹친다 ✅** | 축 선택 화면의 CCTV/RCWS 해상도 입력 → `UStreamResolutionSubsystem` → 브리지가 캡쳐 RT를 `ResizeTarget()` **+ RTSP 송출 해상도까지 같이 결정**. 즉 "그래픽 설정"이자 "송출 규격"이라 한 값이 두 역할을 겸한다 |
| **렌더 스케일** | **안 겹친다 ✗** | 축 선택 화면에 스크린 퍼센티지 항목은 없다. 다만 UGV축에선 `RcwsResolution`이 `SetFixedViewportSize`로 **메인 뷰 렌더 해상도를 절대값으로 못박고**, 렌더 스케일은 그 위에 곱해지는 **배율**이다(1920×1080 × 75% = 1440×810 렌더 → 1920×1080으로 업스케일해 송출). 둘은 곱셈 관계 |

**보류 이유(정리)**

1. 한 값이 **렌더 해상도 + RTSP SDP 해상도 + 탐지 UV 화면비** 세 가지를 동시에 결정한다.
2. **축마다 의미가 다르다** — UGV축은 창과 무관한 고정 렌더 해상도, 자체방호축은 창 추종이
   요구사항(§2.3).
3. RTSP는 `BeginPlay`에 SDP가 확정돼 **런타임 변경이 구조적으로 불가**(§5-C). 반면 렌더
   스케일은 런타임 가능 → **두 항목의 성질이 정반대**인데 UI에서는 비슷해 보인다.
4. 축 선택 화면 입력이 이미 **운용 절차서의 정식 단계**로 문서화돼 있다
   (`packaging/2026-09-02_linux_package_ugv_host_rc_test_guide.md` §4-1).

→ 결론 나기 전까지 Graphics 탭에 넣지 않는다. 결정해야 할 것: *"축 선택 화면과 Graphics 탭 중
어느 쪽이 이 값의 주인인가"*, *"렌더 스케일만 따로 떼서 런타임 항목으로 열 것인가"*.

### 10-5. ★ 남은 진짜 설계 과제 — "품질 4단계가 각각 뭘 의미하는가"

(나) 이관의 본질은 값 복사가 아니라 이것이다. 현재 프로젝트는
**GI=Medium(1) / Shadow=High(2) / 나머지 Epic(3)** 을 고른 뒤 **그 단계 위에서** 추가 튜닝을
얹은 상태다. 그래서 단계를 바꾸면 그 튜닝이 의미를 잃는다. 특히:

- `r.Lumen.FinalGatherMethod`: `0`(IrradianceFieldGather, 엔진 `@1`) ↔ `1`(ScreenProbeGather,
  엔진 `@2`/`@3`). **GI 경로 자체가 바뀐다.**
- 우리 `IrradianceFieldGather.ClipmapWorldExtent=10000 / NumClipmaps=5 / NumProbesToTraceBudget=128`
  튜닝은 **`FinalGatherMethod=0`에서만 유효**하다. 높음/최고로 올리면 무의미해지고, 대신
  ScreenProbeGather 쪽 튜닝이 따로 필요하다.
- VSM도 마찬가지 — 우리 `MaxPhysicalPages=1024`는 엔진 `@2`의 `2048`을 **절반으로 줄인 값**이다.

**제안 방향(측정 필요, 확정 아님)**: 사용자에게 보이는 4단계의 **중앙에 "현재 검증된 세팅"을
놓고** 위아래를 만든다. 그래야 어느 단계를 골라도 룩이 깨지지 않는다.

| 단계 | GI 제안 | 그림자 제안 |
|---|---|---|
| 낮음 | Lumen off (`r.Lumen.DiffuseIndirect.Allow=0`, DFAO 폴백) | 엔진 `@1` |
| **보통(기본)** | **현재값 그대로**(IrradianceFieldGather + 우리 clipmap 튜닝) | **현재값 그대로**(VSM 1024 / LodBiasLocal 2) |
| 높음 | ScreenProbeGather(엔진 `@2`) + 우리 SurfaceCache 값 유지 | 엔진 `@2`(VSM 2048 / LodBias 0) |
| 최고 | 엔진 `@3` | 엔진 `@3` |

→ `Config/DefaultScalability.ini`에 `[GlobalIlluminationQuality@0~3]` / `[ShadowQuality@0~3]`를
**전부 우리가 정의**하는 형태가 된다. 각 단계 fps 실측이 필요하며, `New_kadex_0811`은 이미
거리별 fps 곡선 실측 이력이 있어 비교 기준은 있다(`level_new_kadex_0811/`).

### 10-6. 작업 순서 (확정 스코프 기준)

1. **(라) `r.ReflectionMethod=3` 정리** — Q-4의 선행 조건이자 Windows/Linux 룩 분기 해소
2. **(가) `sg.*` 12줄 → `UTitanGraphicsSettings`** + 적용 함수(에디터/게임 공통) — §9-3
3. **R-1 소코드 변경**(`UQuadCamComponent::CaptureEveryNTicks`) + R-2/R-3 배선
4. **(나) `DefaultScalability.ini` 프리셋 정의** — §10-5의 설계 + 단계별 fps 실측 ← **가장 비쌈**
5. 위젯 UI (Q-1~Q-8, R-1~R-3)

---

## 11. 구현 진행 (2026-09-03 착수)

§10-6 순서대로 진행 중. **빌드는 사용자가 직접** 하므로 여기 코드는 컴파일 미검증 상태다.

### 11-1. ✅ (라) `r.ReflectionMethod` — 양 플랫폼 SSR로 통일 (2026-09-03 적용 완료)

**결정(사용자)**: *"windows 랑 linux 에서 다른 게 좀 문제일 수도 있겠네. 무조건 통일하는 게 맞아.
일단은 기본값은 윈도우로 되어있는 SSR을 기본값으로 하자."* → §11-1 이전 안 중 **(ㄱ) 양 플랫폼 SSR**.

**적용 내용**
- `Config/DefaultEngine.ini` `[/Script/Engine.RendererSettings]`: `r.ReflectionMethod=1` → **`2`**
- `Config/Windows/WindowsEngine.ini` `[ConsoleVariables]`: `r.ReflectionMethod=3` **줄 삭제**
- → 반사 방식의 소스가 `DefaultEngine.ini` 한 줄로 단일화됐다.

**왜 Windows는 룩이 안 바뀌는가 (엔진 소스로 확인)**
- `ShouldRenderScreenSpaceReflections`는 `ReflectionMethod == None`만 배제한다. 주석 그대로:
  *"intentionally allow falling back to SSR from other reflection methods, which may be disabled
  by scalability"* (`ScreenSpaceRayTracing.cpp:165-172`).
- `ShouldRenderLumenReflections`는 `== EReflectionMethod::Lumen`을 요구한다(`LumenReflections.cpp:770`).
- → `2`도 `3`도 "Lumen 반사 off + SSR on"으로 **기능적으로 동일**. Windows는 무변화.

**바뀌는 쪽은 Linux다** — 기존에 `DefaultEngine.ini`의 `1`(Lumen 반사)을 그대로 받고 있었다.
LIG 납품물이 Linux 패키지이므로, 통일 전까지는 **개발 중 보는 화면(Windows=SSR)과 실제로 나가는
빌드(Linux=Lumen 반사)의 반사가 서로 달랐다.** 이번 변경으로 그 분기가 사라진다.

> **검증 필요**: Linux 패키지에서 금속 표면 반사가 의도한 대로 보이는지 1회 확인.
> (SSR은 화면 밖 정보를 못 쓰므로 Lumen 반사보다 반사가 덜 잡히는 구간이 있을 수 있다.)

> ℹ️ 부수 효과 — `FSceneCaptureViewParity::ApplyMainViewReflectionParity`가 `r.ReflectionMethod`를
> 0~2로 클램프하고 있었는데(범위 밖 `3` 대응), 이제 그 클램프는 순수 방어 코드로만 남는다.
> 동작이 바뀌지는 않으므로 코드는 그대로 둔다.

> ⚠️ **이전 판(2026-09-03 오전) 정정**: 이 절의 초안은 `memo.md`의 *"금속 표면에서의 SSR 반사
> 효과 … 빠져있는 거 같음"* 문장을 **요구사항 근거로 인용**했는데, 사용자 확인 결과 **그런
> 요구사항은 없었고** `memo.md`는 그때그때 문제를 적어두는 개인 메모(최신화 안 함)라 근거로
> 쓸 문서가 아니다. 그리고 그 문장이 가리키던 "RTSP에 반사가 안 보인다" 문제 자체는
> `camera_pipeline/rtsp_postprocess_parity_0820.md`에서 **이미 해결됐다**(엔진이 씬 캡쳐에만
> `ReflectionMethod=None`을 강제하던 것). 이번 건은 그것과 무관한 **플랫폼 불일치** 문제다.

### 11-2. ✅ (가) 골격 — `UTitanGraphicsSettings` 신규 작성

**신규 파일 4개** (`Source/titan_example/Settings/`) — 전부 신규라 **P4 add 필요**:

| 파일 | 역할 |
|---|---|
| `TitanGraphicsSettings.h/.cpp` | `UDeveloperSettings`(`config=Game, defaultconfig`). 스케일러빌리티 12축 + 캡쳐 주기 3종 보관, `Apply()`로 엔진에 반영 |
| `TitanGraphicsSubsystem.h/.cpp` | `UEngineSubsystem`. `FCoreDelegates::OnPostEngineInit`에서 `Apply()` 호출 |

**설계상 확정한 것들**

- ~~**`Build.cs` 수정 불필요**~~ → **틀렸음. 수정 필요했다(2026-09-03 빌드로 확인).**
  `DeveloperSettings`는 분명히 `Engine.Build.cs`의 `PublicDependencyModuleNames`에 있는데
  (114행), 그것만으로는 **링크가 안 된다**. 증상: 컴파일은 통과하고
  (`PublicIncludePathModuleNames`에도 들어 있어 헤더는 찾아짐) **링크에서 LNK2001/LNK2019 무더기**.
  근거는 에러 심볼 목록이다 — `GetCategoryName`/`GetSectionName`/`GetSectionText` 등
  헤더에 `DEVELOPERSETTINGS_API`가 붙은 함수들이 **`__declspec(dllimport)` 없이** 찍혔다.
  즉 UBT가 우리 모듈에 그 API 매크로를 import로 정의해주지 않았다는 뜻이다.
  → **`UDeveloperSettings`를 상속할 거면 `titan_example.Build.cs`의
  `PublicDependencyModuleNames`에 `"DeveloperSettings"`를 명시적으로 적어야 한다.** 적용 완료.
- **모듈 클래스도 손 안 댐** — `titan_example.cpp`이 `FDefaultGameModuleImpl`이라 `StartupModule()`
  훅이 없는데, 그걸 고치면 P4 체크아웃이 필요하다. `UEngineSubsystem`은 `UEngine::Init`에서
  에디터/게임 **양쪽 다** 생성되므로 신규 파일만으로 같은 목적을 달성한다.
- **적용 시점은 `OnPostEngineInit`** — 그 앞에 `Scalability::LoadState`(`LaunchEngineLoop.cpp:2866`,
  `PreInitPreStartupScreen`)와 `UGameUserSettings::ApplyNonResolutionSettings`(`GameEngine.cpp:1250`)가
  먼저 돌아 스케일러빌리티를 건드린다. 브로드캐스트는 한참 뒤(`:4062/:4835`)라 우리 값이 최종으로 남는다.
- **`SetQualityLevels(L, bForce=true)`** — `bForce`가 `SetWithCurrentPriority`를 타서
  (`Scalability.cpp:891`) `sg.*`가 어떤 우선순위로 박혀 있든 통과한다.
- **`UGameUserSettings::ScalabilityQuality`도 같이 동기화** — 안 하면 패키지에서 창 모드/해상도가
  바뀌는 순간(`GameViewportClient.cpp:4129/4212`가 `ApplySettings(false)` 호출) 우리 값이
  LoadSettings 시점 스냅샷으로 **통째로 되돌아간다.** 실제로 밟기 쉬운 함정이라 코드에 주석으로 남김.
- **사용자 오버라이드 존중** — 패키지에서 `GameUserSettings.ini`에 `[ScalabilityGroups]`가 있으면
  프로젝트 기본값을 적용하지 않는다(소유 3층 구조 ②). 그래서 **`Config/DefaultGameUserSettings.ini`에는
  `[ScalabilityGroups]`를 절대 넣으면 안 된다** — 넣는 순간 이 판정이 항상 참이 되어 단일 소스가 깨진다.

**후속 함정(코드 주석에도 남김)**: 한 번이라도 `UGameUserSettings::SaveSettings`가 불리면
`Scalability::SaveState`가 `[ScalabilityGroups]`를 쓰고(`GameUserSettings.cpp:679`), **그 PC에서는
이후 `Config/DefaultGame.ini`를 고쳐도 안 먹는다.** 프레임 상한 때와 같은 종류의 함정
(`Config/DefaultGameUserSettings.ini` 주석 참고). 대응: 배포 시 `Saved/Config/<Platform>/GameUserSettings.ini`
정리 + 인게임 탭에 "기본값으로 되돌리기" 버튼.

### 11-3. ✅ (가) `sg.*` 12줄 이관 완료 — 순서를 지켜서 진행함

**순서가 중요했다.** `sg.*`를 코드보다 먼저 지우면 `UTitanGraphicsSettings`가 빌드되기 전까지
**품질이 조용히 엔진 기본값(전부 Epic)으로 올라간다.** 특히 GI가 Medium(1) → Epic(3)으로 뛰면서
Lumen 경로 자체가 IrradianceFieldGather → ScreenProbeGather로 바뀌고, `New_kadex_0811` 숲에서
프레임이 크게 떨어질 수 있다(그 레벨은 2.3 → 31fps 튜닝 이력이 있다). 그래서 아래 순서로 했다:

1. ✅ 신규 4파일 `p4 add` + 빌드 (`Build.cs`에 `"DeveloperSettings"` 추가 후 통과)
2. ✅ 에디터 `Project Settings ▸ Project ▸ Titan Graphics` 표시 확인(사용자)
3. ✅ **적용 로그로 실제 동작 확인** — 값이 ini와 정확히 일치:
   ```
   [TitanGraphics] 적용 — Res=0 VD=3 AA=3 Shadow=2 GI=1 Refl=3 PP=3 Tex=3 FX=3 Foliage=3
                          Shading=3 Landscape=3 / 캡쳐주기 CCTV=x1 Drone=2 Env=2
   ```
   즉 `UEngineSubsystem` → `OnPostEngineInit` 훅이 의도대로 떴고, `SetQualityLevels(bForce=true)`도
   통과했다는 뜻이다.
4. ✅ `Config/Windows/WindowsEngine.ini`의 `sg.*` 12줄 삭제(이관 경위를 주석으로 남김)
5. ⏸ **재확인 남음** — 콘솔 `DumpCVars sg.` 로 `LastSetBy`가 `SystemSettingsIni` → **`Scalability`**
   로 바뀌었는지 볼 것. 바뀌었으면 이제 인게임 탭에서 품질을 바꿀 수 있다는 뜻이다.

> **`ResolutionQuality=0`이 안전한 이유(확인함)** — `Scalability::SetResolutionQualityLevel`은
> 0이면 명시적 NOP다(`Scalability.cpp:534-538`, 주석 그대로 *"NOP: just use the project's default
> screen percentage"*). 그래서 `r.ScreenPercentage`는 `Constructor`(0) 그대로 남고, 이관 전후
> 동작이 같다.

### 11-4. ✅ (가) 이관 실측 확인 완료

`sg.*` 12줄 삭제 후 `DumpCVars sg.` 결과 — **전부 `Scalability`로 바뀌었고 값은 그대로**:

```
sg.ResolutionQuality = "0"          LastSetBy: Scalability
sg.ViewDistanceQuality = "3"        LastSetBy: Scalability
sg.AntiAliasingQuality = "3"        LastSetBy: Scalability
sg.ShadowQuality = "2"              LastSetBy: Scalability
sg.GlobalIlluminationQuality = "1"  LastSetBy: Scalability
sg.ReflectionQuality = "3"          LastSetBy: Scalability
sg.PostProcessQuality = "3"         LastSetBy: Scalability
sg.TextureQuality = "3"             LastSetBy: Scalability
sg.EffectsQuality = "3"             LastSetBy: Scalability
sg.FoliageQuality = "3"             LastSetBy: Scalability
sg.ShadingQuality = "3"             LastSetBy: Scalability
sg.LandscapeQuality = "3"           LastSetBy: Scalability
```

→ **§1.8의 전제(하드코딩이 런타임 품질 변경을 막는다)가 해소됐다.** 이제 인게임 탭에서 품질을
바꾸면 실제로 먹는다.

> ★ **덤프에서 새로 나온 사실 — 스케일러빌리티는 4단계가 아니라 5단계다.**
> 모든 그룹의 `sg.<X>.NumLevels`가 **`5`** 로 찍혔다. 0~3(낮음/보통/높음/에픽) + **4=Cine**이다
> (엔진 `BaseScalability.ini`에 `[ReflectionQuality@Cine]` 같은 섹션이 실제로 있다).
> Cine은 오프라인 렌더용이라 실시간 전시 빌드에 노출할 이유가 없다고 보고
> `UTitanGraphicsSettings`는 `ClampMax=3`으로 잠가뒀다. §10-5 설계도 0~3 기준으로 간다.

### 11-5. ✅ R-1/R-2/R-3 캡쳐 주기 배선 (2026-09-03)

**R-1 — `UQuadCamComponent::CaptureEveryNTicks` 신설**(플러그인)
- 기존 동작은 "매 컴포넌트 틱마다 4개 중 1개"라 각 방향이 이미 틱/4. 이 값은 그 위에 곱해지는
  **배수**로, N이면 각 방향이 틱/(4N)이 된다. **기본 1 = 기존 동작과 완전히 동일.**
- 게이트를 `SyncLensFromCineCameras()` **뒤**에 뒀다 — 렌즈 동기화는 PostProcessSettings 복사뿐이라
  싸고, 건너뛰면 다음 캡쳐가 낡은 렌즈값으로 찍힌다. RCWS/드론/전장이 라운드로빈 게이트를
  `CaptureScene()` 바로 앞에만 두는 것과 같은 이유.
- `GFrameCounter` 기준인 것도 의도 — 시간 기반 스로틀은 실 프레임 델타가 목표를 넘으면 no-op으로
  퇴화해서 정작 느릴 때 효과가 없다(이 프로젝트가 30fps/15fps에서 두 번 겪은 이력).

**R-2/R-3 — 설정값을 살아있는 액터에 밀어넣기**
- `UTitanGraphicsSettings::ApplyCaptureRates(UWorld*)` 신설. `TActorIterator`로 월드를 훑어
  `UQuadCamComponent` / `ADronePawn` / `ATitanTruck`에 값을 적용.
- **왜 "밀어넣기"인가**: 스케일러빌리티와 달리 이건 cvar가 아니라 **컴포넌트 프로퍼티**라 자동 반영
  경로가 없다. 게다가 `UQuadCamComponent`는 별도 플러그인이라 게임 모듈의 설정 클래스를 **볼 수
  없다**(`UStreamResolutionSubsystem` → `UVehicleRtspBridgeComponent`와 동일한 구조적 제약).
- **Slot은 UI에 노출하지 않고 자동 배분** — 전장 카메라 `Slot=0`, 드론 짐벌 `Slot=(Count>=2 ? 1 : 0)`.
  둘이 같은 프레임에 씬을 두 번 렌더하지 않게 하는 게 원래 설계였다.
- **호출 지점 2개**:
  * `UTitanGraphicsSubsystem`이 `FWorldDelegates::OnPostWorldInitialization` → 그 월드의
    `UWorld::OnWorldBeginPlay`에 2단으로 걸어서 레벨이 열릴 때마다 적용.
    (`FWorldDelegates`에는 BeginPlay 이벤트가 없다 — `OnWorldBeginPlay`는 `UWorld`의 멤버
    델리게이트다, `World.h:2830`. 그래서 2단 구조가 필요했다.)
  * `Apply()` 안에서 살아있는 Game/PIE 월드에 재적용 — 런타임 변경(인게임 탭 / 에디터
    Project Settings 편집) 대응. 엔진 시작 시점엔 월드가 없어 0회 도는 게 정상.

### 11-6. ⏸ 남은 것

| 파일 | 할 일 | 상태 |
|---|---|---|
| `Config/DefaultEngine.ini` | (라) 반사 SSR 통일 | ✅ 완료 |
| `Config/Windows/WindowsEngine.ini` | (라) 반사 오버라이드 삭제 / **(가)** `sg.*` 12줄 삭제 | ✅ 완료 |
| `Source/titan_example/Settings/*` (신규 4개) | 작성 + `p4 add` + 빌드 + 실측 확인 | ✅ 완료 |
| `titan_example.Build.cs` | `"DeveloperSettings"` 추가 | ✅ 완료 |
| `QuadCamComponent.h/.cpp` | **R-1** `CaptureEveryNTicks` | ✅ 완료 (빌드 대기) |
| `TitanGraphicsSettings`/`Subsystem` | **R-2/R-3** 배선 | ✅ 완료 (빌드 대기) |
| `Config/DefaultScalability.ini` | **(나)** 프리셋 재정의 (신규 파일) | ⏸ §10-5 설계 확정 후 |
| 인게임 위젯 | Q-1~Q-8 / R-1~R-3 UI | ⏸ 마지막 |
| Linux 패키지 | 반사 SSR 전환 후 룩 확인 | ⏸ 검증 |
| PIE | 캡쳐 주기 로그(`[TitanGraphics] 캡쳐 주기 적용`) 확인 | ✅ 완료 |

### 11-7. ✅ 배선 실측 확인 (2026-09-03, 재빌드 후)

```
[TitanGraphics] 적용 — Res=0 VD=3 AA=3 Shadow=2 GI=1 Refl=3 PP=3 Tex=3 FX=3 Foliage=3 Shading=3 Landscape=3
[TitanGraphics] 캡쳐 주기 적용(New_kadex_0811) — QuadCam 2개=x1, Drone 1개=2틱, Truck 1개=2틱
```

두 훅 다 정상. `OnPostWorldInitialization` → `UWorld::OnWorldBeginPlay` 2단 구조가 PIE에서 동작하고,
그 시점 `WorldType`이 이미 `PIE`라 걱정했던 필터 문제도 없었다. 액터 개수도 예상과 일치 —
**QuadCam 2개**(UGV + 트럭), 드론 1, 트럭 1. PIE는 단일 프로세스라 축 게이팅과 무관하게 세 차량이
다 떠 있으므로 QuadCam이 2개인 게 맞다.

> ⚠️ 이 확인 과정에서 한 번 헛짚었다 — 첫 시도에서 캡쳐 주기 로그가 안 떠서 훅 문제를 의심했는데,
> 실제로는 **빌드가 안 들어간 상태**였다(DLL 16:48 빌드 vs 소스 16:52~54 수정). `[TitanGraphics] 적용`
> 줄은 설정 **필드값**을 출력할 뿐이라 구 빌드에서도 똑같이 찍혀서 헷갈리기 쉽다. 앞으로 이런 확인은
> `Binaries/**/UnrealEditor-*.dll` mtime과 로그 오픈 시각(`Log file open, …`)부터 대조할 것.

---

## 12. 품질 단계 설계 — (나) `DefaultScalability.ini` (2026-09-03 설계)

§10-5의 "품질 4단계가 각각 뭘 의미하는가"를 실측 + 엔진 프리셋 대조로 구체화한 것.
**아직 적용 전 — 사용자 검토 대기.**

### 12-1. 실측 (2026-09-03, PIE `New_kadex_0811`, 사용자)

| 조작 | 결과 |
|---|---|
| `sg.ShadowQuality` 2 → 0 | **50 → 57fps** (+14%). 즉시 반응, 되돌리기도 즉시 |
| `sg.GlobalIlluminationQuality` 1 → 0 | 전환 직후 **약 1분간 프레임 폭락**. 정상 상태 이득은 미측정 |

**GI 히칭 분석** — 셰이더 컴파일은 **아니다**(로그의 `LogShaderCompilers`가 그 구간에 2개·0.6초뿐).
로그상 GI@0에서 바뀐 건 `r.DistanceFieldAO:0` + `r.Lumen.DiffuseIndirect.Allow:0` 두 개고, 되돌릴 때
반대로 켜진다. 즉 **Lumen 씬/디스턴스필드 재구축에 따르는 전환 비용**이지 정상 상태 비용이 아니다.

**운용상 이 문제는 사실상 없다**(사용자 지적): 그래픽 설정은 무거운 `New_kadex_0811`이 아니라
**`kadex_lobby`(축 선택 화면)에서 하고**, 그 뒤 레벨 트래블이 일어난다. 가벼운 로비에서 전환하고
레벨 로드가 재구축을 흡수하므로 사용자는 히칭을 거의 못 느낀다.
→ **UI 배치 결정**: Graphics 탭의 품질 항목은 로비에서 바꾸는 것을 전제로 한다. 인게임(전투 중)
에서도 열 수 있게 하되, 품질 변경에는 "레벨 진입 전에 바꾸는 것을 권장" 안내를 붙일 것.

### 12-2. ★ 결정적 발견 — 작업량이 생각보다 훨씬 작다

`Scalability::SetGroupQualityLevel`은 `ApplyCVarSettingsFromIni(<섹션>, GScalabilityIni, SetByScalability)`
로 **그 섹션에 적힌 키를 전부** 적용한다(`Scalability.cpp:446`). 엔진이 정한 고정 목록이 아니라
**ini 섹션 내용 그대로**다. 그리고 config 계층은 섹션을 **키 단위로 병합**하므로,
`Config/DefaultScalability.ini`에 필요한 키만 적어도 엔진 `BaseScalability.ini`의 나머지는 그대로 남는다.

→ **두 가지가 따라온다.**
1. 우리 값을 단계별로 넣기 위해 엔진 프리셋을 통째로 베껴 쓸 필요가 없다. **덮을 키만** 적으면 된다.
2. **그룹 멤버가 아닌 cvar도 그룹 섹션에 넣으면 적용된다.**

우리 핀 값을 엔진 그룹 멤버 여부로 갈라 보면(`BaseScalability.ini` 실측):

| 우리가 박아둔 값 | 엔진 그룹 멤버? | 함의 |
|---|---|---|
| `r.Lumen.FinalGatherMethod` | ✅ (4단계 전부) | 이관 **필수** — 안 옮기면 GI 단계가 경로를 못 바꿈 |
| `r.Lumen.ScreenProbeGather.DownsampleFactor` / `TracingOctahedronResolution` | ✅ (3단계) | 이관 필수 |
| `r.LumenScene.SurfaceCache.CardMinResolution` | ✅ (4단계) | 이관 필수 |
| `r.LumenScene.SurfaceCache.CardTexelDensityScale` | ✅ (4단계) | 이관 필수 — **RendererSettings에 있음** |
| `r.LumenScene.DirectLighting.UpdateFactor` | ✅ (4단계) | 〃 |
| `r.LumenScene.Radiosity.UpdateFactor` | ✅ (4단계) | 〃 |
| `r.Shadow.Virtual.MaxPhysicalPages` / `ResolutionLodBiasLocal` / `ResolutionLodBiasDirectional` | ✅ | 이관 필수 |
| `r.Lumen.TraceMeshSDFs` | ❌ (엔진은 `…TraceMeshSDFs.Allow`를 씀 — **다른 cvar**) | 전역으로 남겨도 됨 |
| `r.Lumen.SurfaceCache.MaxAtlasSize` | ❌ (엔진은 `r.LumenScene.SurfaceCache.AtlasSize`) | 〃 |
| `r.Lumen.SurfaceCache.UpdateRate` | ❌ | 〃 |
| `r.Lumen.IrradianceFieldGather.*` ×3 | ❌ | 〃 |
| `r.LumenScene.SurfaceCache.CardCapturesPerFrame` / `CardCaptureRefreshFraction` | ❌ | 〃 |

> ★ **§10-5의 걱정이 해소됐다.** "단계를 올리면 IrradianceFieldGather 튜닝이 의미를 잃는다"고 봤는데,
> 그 값들은 **애초에 그룹 멤버가 아니라 어느 단계에서도 덮이지 않는다.** `FinalGatherMethod=0`인
> 단계에서만 효력이 있고 나머지 단계에선 조용히 무시될 뿐 **해가 되지 않는다.** 그대로 두면 된다.

**RendererSettings(0x04)에 있는 3줄은 이제 로그로도 보인다** — `sg.*` 이관 후 실제 PIE 로그:
```
LogConsoleManager: Warning: Setting the console variable 'r.LumenScene.SurfaceCache.CardTexelDensityScale'
  with 'SetByScalability' was ignored as it is lower priority than the previous 'SetByProjectSetting'.
```
`SetByProjectSetting`이 막는 경우는 엔진이 **Warning**으로 찍는다(`SetBySystemSettingsIni`가 막을 때만
Verbose라 안 보였던 것 — §8-1 함정 참고). 즉 **(나) 이관이 끝났는지를 이 경고가 사라지는지로 확인**할 수 있다.

### 12-3-A. ✅ 채택안 (2026-09-04 사용자 확정) — 단계는 4개, **현재 쓰는 단계만 덮는다**

아래 12-3의 "사다리를 새로 설계한다"는 안은 **과설계였다.** 사용자가 §12-2를 보고 단순안을
택했다 — *"4개로 ㄱ"*.

> **채택**: 단계 수는 엔진과 동일하게 4개(0~3). 우리는 **지금 쓰고 있는 단계에만** 튜닝값을
> 덮어씌우고, 나머지 단계는 엔진 표준값 그대로 쓴다.

| 단계 | 그림자 | GI |
|---|---|---|
| 0 낮음 | 엔진 그대로 | 엔진 그대로 (Lumen 끔) |
| 1 보통 | 엔진 그대로 | **← 우리 값으로 덮음(현재 화면)** |
| 2 높음 | **← 우리 값으로 덮음(현재 화면)** | 엔진 그대로 (ScreenProbeGather) |
| 3 최고 | 엔진 그대로 | 엔진 그대로 |

이 방식의 장점:
- **기본 상태의 화면이 지금과 100% 동일**하다(값을 그 자리에 그대로 넣으므로). 검증이 쉽다.
- 단계별 숫자를 새로 발명할 필요가 없다 — 엔진 프리셋이 이미 검증된 사다리다.
- 작업량이 ini 파일 하나, 섹션 2개, 10줄이다.

주의: 사용자가 그림자를 "최고"로 올리면 엔진 기본(VSM 4096)이 적용돼 **지금보다 많이 무거워진다.**
전시 운용에서 문제가 되면 위젯에서 선택지를 3개로 줄이거나 상한을 걸면 된다(코드 변경 불필요 —
`UTitanGraphicsSettings`의 `ClampMax`만 조정).

**적용 완료 (2026-09-04)**

| 파일 | 변경 |
|---|---|
| `Config/DefaultScalability.ini` | **신규.** `[ShadowQuality@2]` 3줄 + `[GlobalIlluminationQuality@1]` 7줄 |
| `Config/Windows/WindowsEngine.ini` | 그룹 멤버 7줄 삭제(Lumen 4 + VSM 3). 비멤버 6줄은 그대로 유지 |
| `Config/DefaultEngine.ini` | `[/Script/Engine.RendererSettings]`에서 Lumen 예산 3줄 삭제. `CardCapturesPerFrame`/`CardCaptureRefreshFraction`은 비멤버라 유지 |

이관 대상 10개가 전부 옮겨진 것 확인(구 ini 0건 / 신 ini 1건씩).

**검증 방법** — 기본 상태에서 **룩·fps가 변화 없어야 정상**이고, PIE 로그에서 아래 경고 3줄이
사라져야 한다:
```
LogConsoleManager: Warning: Setting the console variable 'r.LumenScene.SurfaceCache.CardTexelDensityScale'
  with 'SetByScalability' was ignored as it is lower priority than the previous 'SetByProjectSetting'.
```

### 12-3-B. ✅ 플랫폼 통일 (2026-09-04 사용자 확정 — *"두개 플랫폼 동일하게 ㄱㄱ"*)

12-3-A 이관 후에도 `WindowsEngine.ini`에 Windows 전용 렌더링 값 6줄이 남아 있었다.
**LIG 납품물은 Linux 패키지인데 그쪽은 그 튜닝을 하나도 못 받고 있었다** — 특히
IrradianceFieldGather 원거리 커버리지 보정은 이 레벨을 보고 실측으로 잡은 값이다. 즉 개발 중
보는 화면(Windows)과 실제로 나가는 빌드(Linux)의 GI가 달랐다. 반사(§11-1)와 같은 종류의 문제였고,
같은 결론(통일)으로 처리했다.

**`Config/Windows/WindowsEngine.ini` → `Config/DefaultEngine.ini`의 `[ConsoleVariables]`로 이동:**

| 값 | 비고 |
|---|---|
| `r.AntiAliasingMethod=4` | 엔진 cvar 기본값도 4(`SceneView.cpp:236`)라 실질 무변화. 명시적으로 못박아 둠 |
| `r.Lumen.SurfaceCache.MaxAtlasSize=1024` | Linux는 못 받고 있었음 |
| `r.Lumen.SurfaceCache.UpdateRate=0.5` | 〃 |
| `r.Lumen.IrradianceFieldGather.ClipmapWorldExtent=10000` | 〃 — **원거리 GI 커버리지 보정** |
| `r.Lumen.IrradianceFieldGather.NumClipmaps=5` | 〃 |
| `r.Lumen.IrradianceFieldGather.NumProbesToTraceBudget=128` | 〃 |

- **섹션 이름을 `[ConsoleVariables]` 그대로 유지한 것도 의도다** — 우선순위
  (`ECVF_SetBySystemSettingsIni`)와 적용 경로가 원래와 같아야 Windows 동작이 안 바뀐다.
  `[/Script/Engine.RendererSettings]`로 옮기면 `SetByProjectSetting`으로 낮아진다.
- `r.Lumen.TraceMeshSDFs=0`은 **옮기지 않았다** — `[/Script/Engine.RendererSettings]`에 이미 같은
  값이 있고 그쪽은 플랫폼 공통이라 애초에 비대칭이 없었다. 중복으로 두면 한쪽만 고치는 사고가 난다.

**결과**: `WindowsEngine.ini`에 남은 실제 설정은 `[/Script/Engine.Engine]`(GameEngine /
ViewportClient 클래스 지정)과 `[/Script/Engine.GameUserSettings]`(창 모드 기본값)뿐이다.
`[ConsoleVariables]`는 빈 섹션 + "여기에 렌더링 값을 새로 추가하기 전에 한 번 더 생각할 것"
경고 주석만 남겼다.

> **Windows는 무변화, 바뀌는 쪽은 Linux다.** Linux 패키지에서 원경 GI/밝기가 개선되는 방향으로
> 바뀔 것으로 예상되나 **실측 확인 필요**(§12-5 검증 목록).

---

### 12-3. ~~제안 사다리~~ (폐기 — 12-3-A로 대체, 근거 기록용) — "현재값을 **높음**에 놓는다"

현재 세팅은 이미 성능을 위해 낮춰둔 상태다(Shadow는 엔진 `@2`에서 VSM 페이지 반토막, GI는 `@1`).
그래서 **중앙이 아니라 "높음"에 놓는다** — 아래로 2칸(프레임이 모자랄 때)이 실제 니즈이고, 위로는
1칸이면 충분하다(전시 PC에서 에픽을 고를 일이 없다).

**ShadowQuality** — 엔진 `@2`의 기능 구성(VolumetricFog·DistanceFieldShadowing 켜짐)을 유지한 채
VSM 예산만 조절한다. 엔진 `@0`/`@1`은 그 둘을 꺼버려서 룩이 크게 달라지므로 그대로 쓰지 않는다.

| 단계 | `MaxPhysicalPages` | `LodBiasLocal` | 그 외 |
|---|---|---|---|
| 0 낮음 | 512 | 3 | `r.VolumetricFog=0` (가장 큰 비용 하나만 끔) |
| 1 보통 | 512 | 3 | 엔진 `@2` 그대로 |
| 2 **높음(기본, 현재값)** | **1024** | **2** | `LodBiasDirectional=0` |
| 3 최고 | 2048 | 0 | = 엔진 `@2` 원본 |

**GlobalIlluminationQuality** — `FinalGatherMethod`가 바뀌는 단계에서 **GI 경로 자체가 갈린다**
(0=IrradianceFieldGather ↔ 1=ScreenProbeGather). 룩이 눈에 띄게 달라지므로 UI에 표시 필요.

| 단계 | 내용 |
|---|---|
| 0 낮음 | 엔진 `@0` 그대로 — Lumen 끔(`DiffuseIndirect.Allow=0`), DFAO 폴백. 절감 최대, 룩 최대 변화 |
| 1 보통 | 현재 경로 유지(`FinalGatherMethod=0`) + 예산 축소(`DirectLighting.UpdateFactor=128`, `Radiosity.UpdateFactor=128`, `CardTexelDensityScale=50`) |
| 2 **높음(기본, 현재값)** | `FinalGatherMethod=0`, `CardTexelDensityScale=60`, `DirectLighting.UpdateFactor=64`, `Radiosity.UpdateFactor=96`, `CardMinResolution=4` |
| 3 최고 | 엔진 `@2`(ScreenProbeGather, `DownsampleFactor=32`) — 경로가 바뀌는 유일한 단계 |

> 참고: 현재값의 `DirectLighting.UpdateFactor=64`는 엔진 `@1`의 `128`보다 **더 자주 갱신 = 더 비싸다.**
> 즉 지금은 "`@1` 경로 + `@2`급 예산"에 가깝다. 그래서 "보통"을 예산만 줄인 단계로 두면
> 경로 전환 없이 실효 절감이 나온다 — 히칭도 없다(경로가 안 바뀌니 Lumen 씬 재구축이 없음).

### 12-5. 검증 목록 (빌드 불필요 — ini만 바뀜, 에디터 재시작으로 확인)

| # | 확인할 것 | 기대 결과 |
|---|---|---|
| 1 | 에디터/PIE에서 **화면이 지금과 동일한가** | 동일해야 정상. 값을 그 자리에 그대로 옮겼음 |
| 2 | PIE 로그의 `SetByProjectSetting` 거부 경고 3줄 | **사라져야** 함(= (나) 이관 완료 신호) |
| 3 | `DumpCVars r.Shadow.Virtual` / `r.Lumen` | `LastSetBy`가 `Scalability`(그룹 이관분) 또는 `SystemSettingsIni`(전역 유지분) |
| 4 | `sg.ShadowQuality 0` / `3` | 이제 VSM 값까지 같이 움직여야 함 |
| 5 | **Linux 패키지** 원경 GI/밝기 | **바뀐다.** 개선 방향으로 예상되나 실측 필요 |
| 6 | Linux 패키지 반사(§11-1) | Lumen 반사 → SSR로 바뀜. 같이 확인 |

> 참고: `DefaultEngine.ini`에 `DefaultGraphicsRHI=` / `r.DefaultFeature.AutoExposure.
> ExtendDefaultLuminanceRange=`가 각각 2번씩 적혀 있다(값은 동일). 이번 작업 이전부터 있던 것이고
> 무해해서 손대지 않았다.

### 12-4. 실행 계획

1. `Config/DefaultScalability.ini` 신규 — 위 표의 **덮을 키만** 8개 섹션에 작성
2. `Config/Windows/WindowsEngine.ini` `[ConsoleVariables]`에서 **그룹 멤버인 것만** 삭제
   (`FinalGatherMethod`, `ScreenProbeGather.*` ×2, `CardMinResolution`, `Shadow.Virtual.*` ×3)
   — 나머지(`TraceMeshSDFs`, `SurfaceCache.MaxAtlasSize`/`UpdateRate`, `IrradianceFieldGather.*`)는 **그대로 둔다**
3. `Config/DefaultEngine.ini` `[/Script/Engine.RendererSettings]`에서 3줄 삭제
   (`CardTexelDensityScale`, `DirectLighting.UpdateFactor`, `Radiosity.UpdateFactor`)
   — `CardCapturesPerFrame`/`CardCaptureRefreshFraction`은 그룹 멤버가 아니므로 유지
4. **검증**: 기본(높음)에서 룩·fps가 **변화 없어야** 정상. PIE 로그에서 위 `SetByProjectSetting` 경고
   3줄이 사라졌는지 확인. 그다음 단계별 fps 실측해서 표의 값을 조정.
