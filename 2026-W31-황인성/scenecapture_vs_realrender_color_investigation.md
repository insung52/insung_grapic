# 씬캡쳐 vs 실제 렌더링 색감/음영 불일치 — 완전 조사 기록 (2026-07-24)

> `titan_example` 프로젝트. `camera_pipeline_overhaul_2026-07.md` 6절에서 보류했던 문제
> ("TitanTruck RCWS/UAV 짐벌 씬캡쳐가 UGV RCWS 실제 렌더링보다 색감이 진하고 그림자가 어둡다")를
> 엔진 소스 기준으로 끝까지 판 기록. **완전히 해결되지는 않았지만**, 원인을 두 개의 독립된 축으로
> 명확히 분리하고 각각 실제로 고칠 수 있는 만큼 고쳤다. 남은 건 실용적 보정값(오토익스포저
> 바이어스 -1.0)으로 눈으로 보며 조정하는 단계.
>
> **이 조사 전체의 핵심 한 줄**: 증상의 대부분(사용자 체감 90%+ 이상)은 Lumen이나 노출 같은
> "라이팅 계산"의 차이가 아니라, **`bForceLinearGamma`라는 프로퍼티 하나가 런타임 생성 렌더타겟에서
> 절대 꺼지지 않던 순수 인코딩 버그**였다. 2절에 이걸 왜 그렇게 판단하는지, 정확히 무엇이고 왜
> 씬캡쳐와 메인뷰가 이 점에서 다르게 동작하는지를 집중적으로 정리했다.

---

## TL;DR

1. **텍스처 스트리밍 등록 누락** — 씬캡쳐는 메인뷰와 달리 텍스처 스트리밍 시스템에 자기 위치를
   전혀 등록 안 함(엔진 구조적 한계, 커뮤니티에서도 알려진 이슈). **고침.** 색감/음영과는 무관한
   별개 축(해상도/선명도 문제).
2. **렌더타겟 감마 인코딩 버그** — 런타임 생성 렌더타겥의 `bForceLinearGamma`가 에디터 전용
   동기화 로직 때문에 절대 안 꺼지고 있었음. **진짜 코드 버그였고, 고쳤다.** (단, 이것만으로는
   부족했고 격리 과정에서 한 번 방향이 반대로 튀는 우여곡절이 있었음 — 아래 상세 기록.)
3. **뷰별 독립 Lumen GI/노출** — 씬캡쳐는 메인뷰와 Lumen 씬 데이터·노출 히스토리를 절대
   공유하지 않음(엔진 아키텍처, `CaptureSource`를 뭘 쓰든 무관 — 증명됨). **고칠 방법이 없음.**
   사용자의 정밀한 실측(노출 자유/광원색 조작 실험)으로 이게 진짜 원인이라는 것까지 확인됨.
4. **최종 실용 조치**: CineCamera의 `AutoExposureBias = -1.0`(EV100 값 직접 오프셋 대신 —
   PostProcessVolume의 EV100 락 값이 나중에 바뀌어도 안전하도록) 오버라이드로 임시 보정.
   **완벽한 값은 아니며, 여러 위치를 보면서 추후 조정 필요.**

---

## 1. 텍스처 스트리밍 등록 누락 (해결)

### 발견
엔진 전체에서 `AddStreamingViewInfo()`(뷰 위치를 텍스처 스트리밍 매니저에 등록)를 호출하는
곳은 `GameViewportClient.cpp`의 `Draw()` **단 한 곳뿐**(`UnrealClient.cpp`/헤더 제외 실호출
0건). 이건 **실제 `ULocalPlayer` 뷰에만 해당** — `SceneCaptureComponent2D`는 완전히 다른 렌더
경로(`SceneCaptureRendering.cpp`)를 타서 이 등록을 원천적으로 안 함. 즉 씬캡쳐가 보고 있는
텍스처가 메인뷰 근처에서 우연히 안 겹치면 **가장 낮은 밉레벨로 방치됨.**

웹 검색으로도 독립 확인: "Unreal's streaming system mostly only cares about game viewport
clients... Scene Capture Component 2D... they'll end up getting the lowest possible mipmap
only" ([Epic 포럼](https://forums.unrealengine.com/t/texture-streaming-from-scenecapture2d/408966),
[SteveStreeting.com](https://www.stevestreeting.com/2024/07/24/fixing-blurry-textures-in-ue-capture-components/)).

### 수정
`RCWSComponent.cpp`(`TickComponent`)/`UAVPawn.cpp`(`Tick`)에 `CaptureScene()` 직전, 메인뷰가
`GameViewportClient::Draw()`에서 하는 것과 동일한 계산으로 매 틱 수동 등록 추가:
```cpp
const float HorizontalFOVRadians = FMath::DegreesToRadians(SightCamera->FOVAngle);
const float ScreenSize = static_cast<float>(SightRenderTarget->SizeX);
const float FOVScreenSize = ScreenSize / FMath::Tan(HorizontalFOVRadians * 0.5f);
const float StreamingScale = 1.f / FMath::Clamp(SightCamera->LODDistanceFactor, 0.2f, 1.f);
IStreamingManager::Get().AddViewInformation(SightCamera->GetComponentLocation(), ScreenSize, FOVScreenSize, StreamingScale);
```
(`ScreenSize`/`FOVScreenSize` 공식은 `UnrealClient.cpp`의 `AddStreamingViewInfo()` 실제 구현을
그대로 게임 스레드 버전으로 이식한 것.) `#include "ContentStreaming.h"` 추가.

**색감/음영과는 무관한 별개 축**(해상도/선명도 문제) — 확인 완료, 유지.

### 배제한 관련 가설
- **`LODDistanceFactor`**(팀장님이 언급한 LOD bias) — 라이브 값 확인 결과 `1.0`(기본값 그대로,
  메인뷰와 동일). 우리 코드가 이 값을 건드린 적이 없어서 발동 안 하고 있었음. **원인 아님.**

---

## 2. 렌더타겟 감마 인코딩 버그 — `bForceLinearGamma` (이번 조사 전체의 핵심)

이번 세션에서 확인한 모든 원인 후보(LOD bias, 스크린퍼센티지, 오클루전 쿼리, Lumen 품질 기본값,
카드 갱신 예산, 카메라컷, Lumen 씬 콜드스타트, 텍스처 스트리밍) 중에서 **실제 체감 차이의
대부분을 설명하는 건 이것 하나뿐**이었다. 나머지는 전부 "이론상 존재하지만 이번 증상의 주 원인은
아님"으로 배제되거나 부수적인 축(해상도)이었던 반면, 이건 **매 프레임 매 픽셀에 예외 없이 적용된
순수 인코딩 버그**라서 위치·시점·씬 콘텐츠와 무관하게 항상 같은 방향으로 어긋난다 — "일정하게
편향적"이라는 사용자의 관찰과 정확히 들어맞는 유일한 후보였다.

### 2.1 `bForceLinearGamma`가 정확히 무엇인가

`UTextureRenderTarget2D`(`TextureRenderTarget2D.h:129`)의 `uint8:1` 비트필드 프로퍼티,
생성자 기본값 `true`(`TextureRenderTarget2D.cpp:48`). 이 프로퍼티가 하는 일은 딱 하나:
**"이 렌더타겟에 저장되는 픽셀 데이터가 이미 리니어(선형) 값인지, 아니면 디스플레이용으로 감마
인코딩되어야 하는 값인지"**를 엔진에게 알려주는 스위치다. 실제 소비 지점은
`UTextureRenderTarget2D::GetDisplayGamma()`(`TextureRenderTarget2D.cpp:704`):
```cpp
float UTextureRenderTarget2D::GetDisplayGamma() const
{
    if (TargetGamma > UE_KINDA_SMALL_NUMBER * 10.0f)
        return TargetGamma;                              // 명시적 오버라이드, 기본 0(안 씀)

    EPixelFormat Format = GetFormat();
    if (Format == PF_FloatRGB || Format == PF_FloatRGBA || bForceLinearGamma)
        return 1.0f;   // "나는 리니어 데이터를 담고 있다" — 감마 인코딩 생략 

    return UTextureRenderTarget::GetDefaultDisplayGamma(); // 2.2 — "나는 감마 인코딩된 디스플레이용 데이터를 담는다"
}
```
`bForceLinearGamma=true`가 **왜 기본값인가**: 게임 코드가 `NewObject<UTextureRenderTarget2D>()`로
직접 만드는 렌더타겟은 대부분 "화면에 보여줄 그림"이 아니라 **HDR 씬컬러, 커스텀 포스트프로세스
중간 버퍼, GPU 컴퓨트 출력, VFX 시뮬레이션 데이터** 같은 순수 숫자 데이터 용도다. 이런 용도에선
감마 곡선이 걸리면 오히려 계산이 틀어지므로, 엔진 입장에서 "일단 리니어로 취급"이 더 안전한
기본값이다 — 즉 **이건 버그가 아니라 의도된, 합리적인 기본값**이다. 문제는 우리가 이 기본값을
안 바꾸고 그대로 뒀다는 것.

### 2.2 왜 `SCS_FinalColorLDR`에서는 이 기본값이 틀렸는가 — 씬캡쳐와 메인뷰가 갈라지는 정확한 지점

`SCS_FinalColorLDR`는 "톤매핑까지 끝나고 **감마 인코딩까지 이미 적용된**, 화면에 그대로 띄우면
되는 최종 이미지"를 뽑는 캡쳐소스다(HDR 계열인 `FinalColorHDR`/`FinalToneCurveHDR`과 대비해서
"LDR"이라는 이름 자체가 이 의미). 그런데 실제로 **그 감마 인코딩을 몇 번 걸지는 톤매퍼가 매번
계산 시점에 목적지 렌더타겟에게 직접 물어본다** — `PostProcessTonemap.cpp`의
`GetTonemapperOutputDeviceParameters()`:
```cpp
float Gamma = ...;
InvDisplayGammaValue.X = 1.0f / Family.RenderTarget->GetDisplayGamma();
```
같은 "Final*" 톤매퍼 코드 경로가 실제 게임 백버퍼, 무비렌더큐 출력, 씬캡쳐 등 **여러 종류의
목적지에 재사용**되기 때문에, "이 캡쳐소스면 무조건 감마 2.2"라고 하드코딩하지 않고 목적지
렌더타겟의 `GetDisplayGamma()`를 그대로 신뢰하는 설계다.

- **메인 게임 뷰포트**(UGV RCWS가 쓰는 진짜 렌더링)의 목적지는 `UTextureRenderTarget2D`가 아니라
  `FViewport`/`FSceneViewport`가 소유한 진짜 스왑체인 리소스다. 이건 정말로 모니터에 표시될
  데이터라서 `GetDisplayGamma()`가 진짜 디스플레이 감마(~2.2)를 정확히 반환한다.
- **우리 `SightRenderTarget`/`CameraRenderTarget`**은 `NewObject`로 만든 평범한
  `UTextureRenderTarget2D`다. `bForceLinearGamma`를 아무도 명시적으로 끈 적이 없어서 기본값
  `true`가 그대로 남아있었고, `GetDisplayGamma()`가 **1.0을 반환** — 톤매퍼에게 "나는 리니어
  데이터를 원한다"고 잘못 알려준 것.

**결과**: Lumen GI 계산, 톤매핑, 노출 계산까지 — 위 단계 전부 메인뷰와 씬캡쳐가 완전히 동일한
코드로 동일하게 실행된다. 유일하게 갈라지는 지점은 **맨 마지막, "이 값에 감마 곡선을 씌울지
말지"를 결정하는 그 한 줄**뿐이다. 즉 이건 라이팅/노출/Lumen과 전혀 무관한, 순수하게 "출력 인코딩
단계의 설정값 하나"가 부른 문제였다.

### 2.3 왜 하필 "그림자가 더 어둡고 색감이 진해지는" 증상으로 나타나는가 (수학적 이유)

감마 인코딩은 `E = L^(1/2.2)` 형태(L=리니어 밝기, 0~1)다. `0<L<1` 구간에서 `1/2.2 ≈ 0.4545`
지수는 값을 **끌어올린다** — 예를 들어 `L=0.5`면 `E ≈ 0.73`. 우리 씬캡쳐는 이 인코딩을 생략하고
`L`을 그대로 저장했으므로, 나중에 그 값이 화면에 "이미 감마 인코딩된 것"처럼 취급되어 표시되면
**의도한 값(E)보다 항상 어둡게(L<E)** 보인다.

이 감마 곡선은 **어두운 영역일수록 곡선의 기울기가 훨씬 가파르다** — 즉 그림자처럼 `L`이 작은
영역에서, 인코딩을 빼먹었을 때 생기는 절대적인 밝기 손실이 하이라이트보다 훨씬 크다. 이게 정확히
"그림자가 유독 더 어둡게 보인다"는 증상의 수학적 이유다. 그리고 이렇게 어두운 쪽으로 눌린 상태에서
채널 간 상대적인 밝기 차(=색의 채도감)는 그대로 유지되거나 오히려 두드러지게 되어, 육안으로는
"색이 더 진하다/선명하다"로 인지된다 — 이것도 색공간 문헌에서 "리니어 이미지를 감마 보정 없이
그대로 표시하면 어둡고 대비/채도가 과하게 보인다"로 잘 알려진 전형적인 증상과 정확히 일치한다.

### 2.4 1차 수정과 과보정 (실패, 원인 규명 후 재수정)

`bForceLinearGamma=false`만 추가(기존 `RenderTargetFormat=RTF_RGBA8_SRGB`+`SRGB=true`는
유지한 채) → 빌드 결과 **오히려 훨씬 밝게 과다노출**됨.

원인 추적 결과: `UTextureRenderTarget2D::IsSRGB()`(GPU 텍스처의 `TexCreate_SRGB` 하드웨어
플래그를 실제로 결정하는 함수)가 `InitAutoFormat` 대상(`OverrideFormat==PF_Unknown`, 우리 경우)
에서는:
```cpp
if (OverrideFormat == PF_Unknown)
    return RenderTargetFormat == RTF_RGBA8_SRGB;  // 원시 SRGB 프로퍼티는 아예 안 봄
```
엔진 자체 주석: *"in theory you'd like the 'bool SRGB' variable to == this, but it does not"*.
즉 **`SRGB` 원시 프로퍼티를 아무리 바꿔도 하드웨어 디코드 플래그는 안 바뀌고, 오직
`RenderTargetFormat`만 본다.** `RTF_RGBA8_SRGB`를 유지한 채 `bForceLinearGamma`만 고치니:
쓸 때(톤매퍼)는 이제 제대로 감마 인코딩하는데, 읽을 때(Slate가 샘플링) GPU가 **또 한 번**
sRGB→리니어 디코드를 해서 두 단계가 서로 다른 가정 위에서 겹쳐 과다노출이 남.

**재수정**: `RenderTargetFormat`을 `RTF_RGBA8`(plain, `_SRGB` 아님)로 되돌림 — `bForceLinearGamma`
는 `false` 유지. 이러면 하드웨어 디코드가 아예 안 걸려서, 톤매퍼가 쓴 감마 인코딩된 바이트가
그대로(추가 처리 없이) 화면에 표시됨. `SRGB` 원시 프로퍼티도 `false`로 되돌려 일관성 유지(어차피
`IsSRGB()`가 무시하지만).

### 2.5 최종 재검증 — 파이프라인 전체 재확인 (2026-07-24)

사용자 요청으로 전체 조합을 다시 처음부터 재검증:
- **`RTF_RGBA8` vs `RTF_RGBA8_SRGB`가 실제로 다른 픽셀 포맷인지**: `TextureRenderTarget2D.h:52-53`
  확인 결과 **둘 다 `PF_B8G8R8A8`로 동일** — sRGB 플래그만 격리되어 바뀌고 저장 정밀도/채널
  순서는 무관, 부수효과 없음 확인.
- **`InitAutoFormat()` 호출 순서**: `bForceLinearGamma=false` 설정 직후 호출하는데 혹시 내부에서
  다시 리셋하는지 확인 → 리셋 로직 자체가 주석 처리되어 죽어있음(`//bForceLinearGamma = true;`).
  순서 문제 없음.
- **`TargetGamma`**(별도의 명시적 감마 오버라이드): 기본값 `0.f`("0이면 리소스에서 상속") —
  아무것도 오버라이드 안 함, 확인 완료.
- **`CaptureSource=SCS_FinalColorLDR`의 정의**: HDR 계열(`FinalColorHDR`="Linear Working Color
  Space", `FinalToneCurveHDR`="Linear sRGB gamut")과 대비해 리니어가 아님(=감마 인코딩된
  디스플레이용)이 재확인됨 — 우리 선택 자체는 맞음.

**최종 상태**: `SCS_FinalColorLDR` + `RTF_RGBA8`(plain) + `SRGB=false` + `bForceLinearGamma=false`
— 내적으로 일관됨, 더 이상 모순 지점 없음. **이 축은 완료로 결론.**

### 2.6 CaptureSource를 FinalToneCurveHDR로 바꾸면 완전히 동일해질 수 있는지 (조사 완료 — 불가능하다는 게 증명됨)

`SceneCaptureRendering.cpp:230-233`:
```cpp
static bool CaptureNeedsSceneColor(ESceneCaptureSource CaptureSource)
{
    return CaptureSource != SCS_FinalColorLDR && CaptureSource != SCS_FinalColorHDR && CaptureSource != SCS_FinalToneCurveHDR;
}
```
`FinalColorLDR`/`FinalColorHDR`/`FinalToneCurveHDR` **셋 다 `EngineShowFlags.PostProcessing`을
안 끔** — 디퍼드 라이팅+Lumen GI+톤매핑까지 완전히 동일한 파이프라인을 다 돌린 뒤, 그 체인의
어느 지점에서 뽑아내느냐만 다름. Lumen GI 계산 자체는 포스트프로세스보다 훨씬 앞단이라
`CaptureSource`가 뭐든 전혀 영향 안 받음. 그리고 3절의 독립 Lumen 씬 메커니즘 코드에도
`CaptureSource`를 체크하는 조건문이 단 하나도 없음. **결론: CaptureSource를 바꿔도 3절의
근본 원인(독립 Lumen/노출)은 전혀 해결 안 됨 — 증명됨, 이 방향은 실익 없음.**

---

## 3. 뷰별 독립 Lumen GI / 노출 — 근본 원인 (구조적으로 해결 불가능함이 증명됨)

### 3.1 독립 Lumen 씬 데이터 — 공유할 방법이 없음

`SceneViewState.h:100-102` 주석: *"Cube map captures share an origin, allowing them to share
things like global distance fields and Lumen scene data. Otherwise, this will just be the same
as UniqueID."* 실제 공유 코드(`SceneCaptureComponent.cpp:414`)는:
```cpp
if ((ViewStates.Num() > 1) && IsCube())
    ViewStates.Last().ShareOrigin(&ViewStates[0]);
```
**큐브맵 캡쳐 6면끼리만** 공유 — 일반 2D 캡쳐(우리 SightCamera/GimbalCamera)가 메인뷰와 공유할
경로는 **엔진에 아예 없음.** `FSceneViewState`(`RendererScene.cpp:378-386`) 생성 시
`ShareOriginTarget`이 없으면 `ShareOriginUniqueID = UniqueID`(자기 자신) — 각 뷰가 무조건 자기만의
`FLumenSceneData`를 가짐.

- **콜드스타트 가설**: 배제됨. `AddLumenSceneData()`(`SceneViewState.cpp:557`)가
  `SceneData->CopyInitialData(*Scene->DefaultLumenSceneData)`로 메인뷰 데이터를 최초 1회
  복사해서 시작 — 0에서 시작하는 게 아님. 그 이후로만 독립적으로 갈라짐.
- **카드 갱신 예산 경합 가설**: 배제됨. `UpdateSurfaceCacheMeshCards(FLumenSceneData&, ...)`가
  `FLumenSceneData` 인스턴스마다 별도 호출되고 예산 카운터가 매 호출 로컬 초기화 — 메인뷰와
  캡쳐가 프레임당 카드 갱신 예산을 각자 100% 독립적으로 받음, 경합 없음.
- **카메라컷 리셋 가설**: 배제됨. `bCameraCutThisFrame`을 `true`로 세팅하는 코드가 엔진 전체에
  0건, 우리 코드도 안 건드림 — 항상 `false`, 컷 없이 이어지는 히스토리 정상 유지.
- **Lumen 수렴 속도(`LumenSceneLightingUpdateSpeed`/`LumenFinalGatherLightingUpdateSpeed`) 가설**:
  실제로 존재하는 진짜 노브(카드 갱신 배수/디퓨즈 GI 히스토리 누적 프레임 수 조절, 최대치로
  올리면 수렴이 빨라짐)이지만, **사용자가 일정하게 편향된 차이(위치 무관하게 늘 같은 방향)라고
  재확인**해서 이 시간적 수렴/노이즈 계열 가설 자체가 기각됨 — 일정한 편향은 수렴 속도가 아니라
  구조적인 차이를 가리킴.

### 3.2 독립 노출(PreExposure) 히스토리

`FViewInfo::UpdatePreExposure()`(`PostProcessEyeAdaptation.cpp:1504`)가
`ViewState->PreExposure`에 매 프레임 저장 — 뷰스테이트(캡쳐 하나당 하나)마다 독립 관리.
공식 자체(`GlobalExposure = GetLastEyeAdaptationExposure()`)엔 `bIsSceneCapture` 분기가 전혀
없음(순수 알고리즘은 동일) — 차이는 오직 **각자의 누적 히스토리**에서만 발생.

### 3.3 결정적 실험 — 사용자가 직접 확인 (2026-07-24)

- **HDRI/Skylight 강도 0 + PostProcessVolume EV100 락 해제 + 오토익스포저 자유** → 노출값이
  최대한 밝게 잡혀서 색감 차이는 하이라이트로 날아가 안 보이지만, **그림자 음영 차이는 여전히
  존재.** 노출이 자유롭게 최대치로 풀렸는데도 어두운 부분 차이가 안 사라짐 = 노출값(EV100) 문제가
  아님.
- **광원 색을 어둡게(노출은 안 건드림)** → EV100 강제고정 때와 동일한 증상(색감 진해짐, 어두운
  부분 더 어두워짐) 재현.

이 둘을 합치면: **차이의 실체는 노출값이 아니라 Lumen GI가 실제로 만들어내는 밝기/색 값 자체**
— 3.1의 독립 Lumen 씬 메커니즘과 정확히 부합. **이 조사에서 가장 강력한 실증적 증거.**

### 3.4 결론 — 엔진 아키텍처상 완전한 해결 불가능

`ShareOriginUniqueID`/`FLumenSceneData` 독립 메커니즘은 일반 2D 씬캡쳐에 대해 메인뷰와 공유할
공개 API가 존재하지 않음(2.6절에서 CaptureSource로도 우회 불가능함이 증명됨). **코드로 완전히
없앨 수 있는 문제가 아님** — 남은 선택지는 두 독립 계산이 실제로 비슷한 답에 수렴하도록
입력(레벨 라이팅)을 안정시키거나, 결과 차이를 사후 보정하는 것뿐.

---

## 4. 최종 조치 — 오토익스포저 바이어스 보정 (2026-07-24, 임시)

사용자가 TitanTruck RCWS/UAV 짐벌의 CineCamera(`RCWSSightCineCamera`/`GimbalCineCamera`)
PostProcessSettings에 **`AutoExposureBias = -1.0`** 오버라이드를 적용. `bForceLinearGamma` 수정
이후 이 보정 하나만으로 육안상 95% 이상 일치하는 결과를 얻음.

**EV100 절대값 오프셋이 아니라 바이어스(상대 보정)를 택한 이유**: 레벨의 PostProcessVolume이
잠가둔 EV100 절대값(현재 10)은 나중에 라이팅 작업하면서 바뀔 수 있음 — 절대값 오프셋(예:
"항상 13으로 고정")은 그 락 값이 바뀌면 다시 안 맞게 되지만, **바이어스(상대 보정, 현재 -1.0)는
락 값이 얼마로 바뀌든 그 값 기준으로 상대적으로 계속 적용**되어 더 안전함.

### 4.1 왜 단 하나의 상수 보정값으로 95% 이상 맞아떨어지는가 — 코드로 뒷받침되는 설명

`bForceLinearGamma`를 고치기 전에는 EV100/노출값을 아무리 만져도 톤앤매너 자체가 안 맞았다(이건
2.3절의 감마 곡선 자체가 틀렸으니 당연 — 곡선 모양이 다른 걸 밝기 스칼라 하나로는 못 고침).
감마를 고친 지금은 곡선 자체는 맞고, 남은 차이가 오직 3절의 "뷰마다 독립적으로 수렴하는 Lumen
GI/노출"뿐이라는 게 이 조사로 확정된 상태다. 그렇다면 **왜 그 독립 수렴 차이가 상수 하나로
거의 다 상쇄되는가**를 코드로 뒷받침해본다.

`AutoExposureBias`의 실제 소비 코드(`PostProcessEyeAdaptation.cpp:451-459`):
```cpp
float AutoExposureBias = Settings.AutoExposureBias;
...
return FMath::Pow(2.0f, AutoExposureBias);   // 최종 노출 스케일 = 2^AutoExposureBias
```
**`AutoExposureBias`는 순수 EV(로그2) 스케일의 덧셈값이고, 실제 밝기에는 `2^bias`라는 배율로
곱해진다.** 이게 핵심이다: 만약 두 독립된 Lumen 씬이 만들어내는 최종 장면 밝기(간접광 포함)의
차이가 화면 전체에 걸쳐 **대략 일정한 배율(k배)**로 어긋나는 성격이라면 — 이건 정확히
`log2(k)`만큼의 EV(로그2) 오프셋과 수학적으로 동일한 형태다. `AutoExposureBias = -log2(k)`로
정확히 상쇄할 수 있는, **딱 노출 보정이 원래 하도록 설계된 바로 그 종류의 오차**라는 뜻이다.

**이게 우리가 지금 코드로 증명할 수 있는 것과 증명 못하는 것의 경계**:
- **증명됨(코드)**: `AutoExposureBias`가 정확히 이런 "전역 균일 배율 보정" 메커니즘이라는 것 —
  위 코드로 100% 확인.
- **증명 안 됨(실측 필요, 안 함)**: 실제 두 Lumen 씬의 차이가 정말로 "대략 균일한 배율"에
  가까운 성격인지 자체는 라이브 픽셀 비교 없이는 단정 불가. 다만 **95% 이상 일치라는 실측
  결과 자체가, 그 가정이 이 씬/이 두 카메라 조합에 한해서는 상당히 잘 맞아떨어진다는 간접
  증거**다. 반대로 "완벽하진 않다"는 것도 이 설명과 모순되지 않는다 — 균일 배율이 아닌 나머지
  성분(국소적 그림자 패턴 차이 등)은 상수 하나로는 원리적으로 못 잡기 때문.

즉 지금 상태는 "가장 큰 성분(감마 곡선 자체가 틀림, ~버그)은 코드로 완전히 고쳤고, 남은 두
번째로 큰 성분(독립 Lumen 수렴의 균일 배율 오차)은 정확히 그 성질에 맞는 도구(`AutoExposureBias`)
로 근사 보정 중"이라는 그림으로 요약된다.

**주의**: 이 값(-1.0)은 정밀 튜닝된 최종값이 아님 — 여러 위치/각도에서 화면을 보면서 계속
조정 필요. 3절에서 확인했듯 이 차이가 정확히 위치에 얼마나 의존적인지까지는 다 밝히지 못했음
(사용자가 "일정하게 편향적"이라고 재확인했지만, 그 편향의 정확한 크기가 씬 콘텐츠에 따라
미세하게 다를 가능성은 남아있음 — Lumen GI 자체가 결국 콘텐츠 의존적이므로).

---

## 5. 최종 코드 상태 (2026-07-24)

- **`Vehicles/RCWSComponent.cpp`**: `SightRenderTarget->RenderTargetFormat = RTF_RGBA8;`(plain),
  `SRGB = false;`, `bForceLinearGamma = false;`(BeginPlay). `TickComponent()`에
  `IStreamingManager::Get().AddViewInformation(...)` 매 틱 호출 추가(`CaptureScene()` 직전).
  `#include "ContentStreaming.h"` 추가.
- **`Vehicles/UAVPawn.cpp`**: `CameraRenderTarget`에 동일 패턴(`RTF_RGBA8`/`SRGB=false`/
  `bForceLinearGamma=false`). `Tick()`에 동일한 스트리밍 등록 추가.
- **레벨/BP 쪽**: `RCWSSightCineCamera`(TitanTruck)/`GimbalCineCamera`(UAV)의
  PostProcessSettings에 `AutoExposureBias = -1.0` 오버라이드 추가(사용자가 직접, 코드 아님).
  값은 추후 조정 예정.
- 이전 세션에 이미 적용된 `LumenSurfaceCacheResolution=1.0` 강제, `ShowFlags.SetTemporalAA(true)`
  등은 그대로 유지.

---

## 6. 남은 것 / 다음 세션 참고

- **AutoExposureBias 값 정밀 튜닝**: -1.0은 1차 추정치, 실제 여러 씬/각도에서 눈으로 보며 재조정
  필요.
- **2번째 조사 방향(멀티 씬 렌더링 N개 한계)**: 이번 세션에서 전혀 착수 안 함 — 여전히 대기 중.
  목표는 N=3~7개 카메라를 1개 렌더링 성능/퀄리티로 처리하는 방법 조사(이전 세션에서 3개 동시
  실제 렌더링 시 Lumen 노이즈 증폭으로 롤백한 경험 있음, `camera_pipeline_overhaul_2026-07.md`
  3절 참고).
- 최근 다른 작업자가 진행 중인 것으로 보이는 **레벨 라이팅 재조정 작업**(SkyLight를
  CapturedScene 모드로 전환, SkyAtmosphere 액터 추가, EV100 락 재검증 등, task #28-35) —
  이 문서의 3.3절 실험(HDRI/Skylight 세기 조정)과 밀접하게 연관될 수 있어 보임. 그쪽 작업
  결과에 따라 이 문서의 AutoExposureBias 값도 재조정이 필요할 가능성 있음 — 두 작업 진행 상황을
  서로 참고할 것.
