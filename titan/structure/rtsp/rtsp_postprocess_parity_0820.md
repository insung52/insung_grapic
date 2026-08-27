# RTSP 스트림에 SSR 반사 / 피격 화면 흔들림이 안 나오는 문제 (2026-08-20)

`ugv_rc_gui`로 보는 RTSP 화면에서 금속 표면 반사(SSR)와 총알 피격 시 화면 흔들림이
빠져 보인다는 리포트. **원인 2개 확정, 둘 다 "씬 캡쳐 경로에만 구조적으로 빠지는" 것**이며
서로 무관한 별개 원인이다.

관련 파일: `Plugins/QuadCamModule/Source/QuadCamModule/{Public,Private}/SceneCaptureViewParity.{h,cpp}`(신규),
`Vehicles/RCWSComponent.cpp`, `QuadCamComponent.cpp`, `Vehicles/UAVPawn.cpp`, `Vehicles/TitanTruck.cpp`.

---

## 0. 전제 확인 — "로컬 뷰"와 "RTSP 뷰"는 실제로 서로 다른 카메라다

직전 세션(해상도 커스터마이징)이 지적한 모순은 사실이었다. UGV RCWS는 카메라가 **두 개**다:

| | 컴포넌트 | 용도 |
|---|---|---|
| 실제 메인 뷰포트 | `RCWSPrimaryViewCamera` (`UCameraComponent`) | `SetViewTarget(UGV)` → `AActor::CalcCamera`가 고르는 진짜 뷰 |
| RTSP / RT | `RCWSSightCamera` (`USceneCaptureComponent2D`) | `GetSightCamera()` → `URtspStreamComponent::SourceCapture` |

`RCWSComponent.cpp:179~` 에서 `PrimaryViewCamera`를 `SightCamera`의 **자식**으로 붙여
트랜스폼을 공짜로 공유하고, `TickComponent`에서 FOV/PostProcessSettings만 복사한다.
즉 위치·렌즈는 같지만 **렌더링 경로 자체가 다르다** — 그리고 UE는 이 두 경로를 아래 두 군데에서
다르게 취급한다.

QuadCam CCTV 4방 / UAV 짐벌 / 자체방호 전장카메라도 전부 같은 구조(참조용 CineCamera + 씬 캡쳐)다.

---

## 1. 반사(SSR/Lumen)가 빠지는 이유 — 엔진이 씬 캡쳐에만 `ReflectionMethod=None`을 강제한다

`Engine/Source/Runtime/Renderer/Private/SceneCaptureRendering.cpp:789~822` (UE 5.8):

```cpp
View->StartFinalPostprocessSettings(...);          // ← PPV 블렌딩 + r.ReflectionMethod 등 CVar 반영
if (InheritedMainViewPostProcessSettings) { ... }
else
{
    // By default, Lumen is disabled in scene captures, but can be re-enabled with the
    // post process settings in the component.
    View->FinalPostProcessSettings.DynamicGlobalIlluminationMethod = EDynamicGlobalIlluminationMethod::None;
    View->FinalPostProcessSettings.ReflectionMethod = EReflectionMethod::None;   // ★
    View->FinalPostProcessSettings.LumenSurfaceCacheResolution = 0.5f;
}
if (PostProcessSettings) { View->OverridePostProcessSettings(*PostProcessSettings, Weight); }  // ← 유일한 복구 경로
View->EndFinalPostprocessSettings(...);
```

`ReflectionMethod == None`이면 SSR도 Lumen 반사도 통째로 꺼진다:

- `ScreenSpaceRayTracing.cpp:165` `ShouldRenderScreenSpaceReflections()` — 첫 번째 게이트가
  `View.FinalPostProcessSettings.ReflectionMethod == EReflectionMethod::None → false`.
- `Lumen/LumenReflections.cpp:765` `ShouldRenderLumenReflections()` — `== EReflectionMethod::Lumen` 요구.

남는 건 리플렉션 캡쳐/스카이라이트/플래너 리플렉션 성분뿐 → **금속 표면의 화면공간 반사가 사라진다.**

### 중요한 함정 두 가지

1. **ShowFlags로는 못 고친다.** `ShowFlags.SetScreenSpaceReflections(true)`는 위 게이트의
   *다른* 조건일 뿐, `FinalPostProcessSettings.ReflectionMethod`를 되돌리지 않는다.
   (`QuadCamComponent.cpp`의 2026-07-24 주석 "Lumen GI/Reflections/SSR ... 강제 비활성화를 제거함"이
   실제로는 ShowFlags만 되돌린 것이라 반사는 계속 꺼져 있었다.)
2. **`bOverride_`가 켜진 값만 살아남는다.** 리셋 직후 `OverridePostProcessSettings`가 컴포넌트의
   `PostProcessSettings`를 덮어쓰므로, `bOverride_ReflectionMethod=true`인 경우에만 복구된다.

### 실제 애셋 상태 (확인 완료)

`BP_UGV_Vehicle` / `BP_TitanTruck` / `BP_UAV` 패키지 네임테이블을 직접 뒤진 결과:

```
bOverride_DynamicGlobalIlluminationMethod   ← 있음 (누가 GI만 다시 켜둠)
bOverride_ReflectionMethod                  ← 세 애셋 모두 없음 = false
```

즉 `SyncLensFromCineCamera()`가 CineCamera에서 통째로 복사해오는 `PostProcessSettings`에
`bOverride_ReflectionMethod`가 꺼져 있어서, **모든 씬 캡쳐가 반사 없이 렌더되고 있었다.**
"Lumen은 CineCamera Details에서 켜라"(2026-07-30 결정)를 GI에만 적용하고 반사를 빠뜨린 것.

### 부가 발견 — `r.ReflectionMethod=3`

`Config/DefaultEngine.ini:13` → `r.ReflectionMethod=1` (Lumen)
`Config/Windows/WindowsEngine.ini:45` → `r.ReflectionMethod=3` ← **유효 범위 밖**

`EReflectionMethod`는 `None=0 / Lumen=1 / ScreenSpace=2` 뿐이다(UE 5.8, `EngineTypes.h:472`).
3은 렌더러 입장에서 "None도 Lumen도 아님" → SSR 경로로 떨어진다. 즉 **Windows에서 메인 뷰포트가
실제로 쓰고 있는 건 Lumen 반사가 아니라 SSR**이고, 그래서 사용자 눈에도 "SSR이 빠졌다"로 보인 것.
Linux 쪽엔 이 오버라이드가 없어서 Lumen 반사를 쓴다. **의도한 값인지 확인 필요** — 옛 UE의
4번째 항목(RayTraced) 잔재이거나 `r.DynamicGlobalIlluminationMethod`의 `3=Plugin`과 혼동한 걸로 보임.
(이번 수정은 이 값을 건드리지 않고, 메인 뷰가 쓰는 값을 그대로 따라간다.)

---

## 2. 피격 화면 흔들림이 안 나오는 이유 — 셰이크는 `PlayerCameraManager`에만 걸린다

`RCWSProjectile.cpp:723` → `UGameplayStatics::PlayWorldCameraShake(...)`
→ `APlayerCameraManager::PlayWorldCameraShake` (`PlayerCameraManager.cpp:1359`)
→ 각 `PlayerController->ClientStartCameraShake(...)`
→ `APlayerCameraManager::DoUpdateCamera` 안에서 `ApplyCameraModifiers(DeltaTime, OutVT.POV)`.

즉 셰이크는 **카메라 매니저가 들고 있는 POV에만** 얹힌다. 씬 캡쳐는 자기 컴포넌트 트랜스폼으로
독립적으로 뷰를 만들기 때문에 이 오프셋이 닿을 경로 자체가 없다 — 즉 "배선이 빠진" 게 아니라
**구조적으로 불가능**했던 것. (셰이크 자체는 `Multicast_PlayImpactEffect` 경유라 UGV축 프로세스에도
정상적으로 도착한다. 문제는 도착 이후 경로다.)

---

## 3. 수정 내용

신규 `FSceneCaptureViewParity` (QuadCamModule) — 씬 캡쳐 4종이 전부 같은 구조라 공용화.

### 3.1 `ApplyMainViewReflectionParity(Capture)`

캡쳐의 `PostProcessSettings`에 `bOverride_ReflectionMethod` / `bOverride_DynamicGlobalIlluminationMethod`가
꺼져 있으면, **진짜 뷰가 읽는 것과 같은 CVar**(`r.ReflectionMethod` / `r.DynamicGlobalIlluminationMethod`,
`SceneView.cpp:2119~2127`)에서 값을 읽어 오버라이드를 채워넣는다.
CineCamera 쪽에서 이미 Override를 켜뒀으면 손대지 않는다 → "CineCamera Details가 단일 소스" 방침 유지.

호출 위치는 **`CaptureScene()` 직전**. 이유:
- `SyncLensFromCineCamera()`가 매 틱 `PostProcessSettings`를 통째로 덮으므로 BeginPlay 1회로는 안 됨.
- RCWS의 경우 `PrimaryViewCamera`가 `SightCamera->PostProcessSettings`를 복사한 **뒤**라,
  이 오버라이드가 진짜 뷰(=PPV의 반사 설정을 정상적으로 받는 쪽)로 새지 않는다.

`LumenSurfaceCacheResolution`(씬 캡쳐 전용 0.5 기본값)은 의도적으로 그대로 뒀다 — 반사가
나오냐/안 나오냐와 달리 순수 품질·비용 트레이드오프라, 기존 방침대로 CineCamera Override로 조절.

### 3.2 `GetLocalViewShakeOffset(ViewOwner)` + `FScopedCaptureViewShake`

로컬 `PlayerCameraManager`의 최종 POV에서 **모디파이어 적용 전 POV**(= 그 액터의 활성
`UCameraComponent` 트랜스폼, `AActor::CalcCamera`)를 빼서 셰이크분만 역산하고,
카메라 **로컬 공간** 오프셋으로 돌려준다(방향이 다른 CCTV 캡쳐에도 그대로 얹을 수 있게).

- 그 액터가 로컬 뷰타겟이 아니면(예: UGV축 프로세스의 자체방호 액터들) Identity.
- 뷰타겟 블렌드 중(`PendingViewTarget.Target != nullptr`)이면 Identity — 블렌드분을 셰이크로 오인 방지.
- 오프셋이 200cm / 30°를 넘으면 Identity (텔레포트·뷰타겟 전환 방어).

적용은 `CaptureScene()` 구간에서만 얹었다가 즉시 원복하는 RAII(`FScopedCaptureViewShake`).
**상시로 얹으면 안 되는 이유**: `SightCamera`의 트랜스폼은 이 프로젝트에서 "조준 방향" 그 자체로도
읽힌다(`UpdateRangeTrace` 사거리 트레이스, `RefreshAzimuthElevation` 방위·고각, 사격통제).
상시 적용은 게임플레이(탄착점)를 바꿔버린다. `CaptureScene()`은 `SendAllEndOfFrameUpdates()`로
트랜스폼을 렌더 스레드에 밀어넣고 동기적으로 캡쳐하므로 이 타이밍이 성립한다.
`PrimaryViewCamera`는 `SightCamera`의 자식이지만, 카메라 매니저는 이미 `TG_PrePhysics`에서
POV를 캐시한 뒤라 이 순간의 일시적 트랜스폼 변화에 영향받지 않는다(→ 메인 뷰 이중 셰이크 없음).

### 3.3 적용 지점

| 파일 | 캡쳐 | 반사 패리티 | 셰이크 |
|---|---|---|---|
| `RCWSComponent.cpp` | `SightCamera` | BeginPlay + Tick 라운드로빈 | Tick 라운드로빈 |
| `QuadCamComponent.cpp` | Front/Rear/Left/Right | 라운드로빈 + 위젯 표시 시 | 라운드로빈 |
| `UAVPawn.cpp` | `GimbalCamera` | BeginPlay + Tick 라운드로빈 | Tick 라운드로빈 |
| `TitanTruck.cpp` | `BattlefieldCapture` | BeginPlay + Tick 라운드로빈 | Tick 라운드로빈 |

---

## 4. 검증 (미완 — 빌드 필요)

이 세션에선 빌드/실행을 하지 않았다. 확인 순서:

1. **코드 없이 진단만 먼저 확인하고 싶다면**: 에디터에서 `BP_UGV_Vehicle`의
   `RCWSSightCineCamera` → Details → Post Process → Rendering Features →
   **Reflection Method** 의 Override 체크를 켜고 `Screen Space`로 두고 컴파일 → PIE →
   RTSP 화면에서 금속 반사가 돌아오면 §1 확정. (이번 C++ 수정은 이걸 모든 카메라에 자동으로
   해주는 것과 같다.)
2. 빌드 후 PIE/패키지 실행 → `ugv_rc_gui`로 `ugv/rcws`, `ugv/*_cctv` 스트림 확인:
   - 금속 표면 반사가 메인 뷰포트와 같이 보이는지
   - RCWS로 사격 → 탄착 시 RTSP 화면이 메인 뷰포트와 같이 흔들리는지
3. 성능 확인: 반사가 켜지면 씬 캡쳐 5~7개 × 반사 비용이 새로 붙는다. UGV축에서 프레임이
   떨어지면 CineCamera Override로 카메라별로 `None`/`Screen Space`를 골라 낮출 수 있다
   (재빌드 불필요).

## 5. 남은 확인거리

- `Config/Windows/WindowsEngine.ini`의 `r.ReflectionMethod=3` — 의도한 값인지 확인 필요(§1 끝).
  Windows=SSR / Linux=Lumen으로 두 플랫폼 룩이 갈려 있는 상태.
- `LumenSurfaceCacheResolution`이 씬 캡쳐에서만 0.5 — Lumen 반사를 쓰는 Linux 빌드에서
  반사 디테일이 메인 뷰보다 거칠 수 있음. 필요하면 CineCamera Override로 1.0.
