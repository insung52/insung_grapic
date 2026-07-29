# CineCamera 렌즈 세팅 미연동 + 씬캡쳐 텍스처 뭉개짐 조사

> `titan_example` 프로젝트. 색감/음영 불일치 문제를
> 해결한 직후 발견된 별개의 세 가지 문제. 전부 해결 완료.

---

## 문제 1: CineCamera 디테일 패널의 렌즈/필름백 세팅이 Play 시 반영 안 됨

**증상**: BP 에디터에서 `UCineCameraComponent`(RCWSSightCineCamera/GimbalCineCamera 등)의 렌즈/필름백/초점거리를
바꿔도 실제 Play에는 반영되지 않음. 노출값/Lumen 설정은 연동되지만 렌즈 관련 설정만 안 됨.

**원인**: `RCWSComponent`/`UAVPawn`/`QuadCamComponent` 전부, 디자이너가 직접 입력하는 고정값 `CameraFOV`
프로퍼티가 FOV를 결정하고 있었고, CineCamera의 렌즈/필름백에서 실제 계산되는 FOV
(`UCineCameraComponent::GetCameraView()`가 채우는 `FMinimalViewInfo::FOV`)는 한 번도 읽어서 쓰인 적이
없었음. 줌 기능과의 과거 충돌 때문에 의도적으로 이렇게 만들어져 있었음.

**수정**: `CameraFOV` 대신 CineCamera에서 읽은 FOV를 줌 나눗셈과 함께 매 틱 적용하도록 변경.
```cpp
SightCamera->FOVAngle  = FMath::Min(ViewInfo.FOV / ZoomLevel, 170.f);  // RCWS
GimbalCamera->FOVAngle = ViewInfo.FOV / ZoomLevel;                    // UAV
Pair.Value->FOVAngle   = ViewInfo.FOV;                                 // QuadCam (줌 없음)
```
`SyncLensFromCineCamera(s)`(매 틱)와 `SetZoomLevel()`(줌 입력 시 즉시 반영) 둘 다 수정.
`CameraFOV`는 CineCamera 미해석 시 폴백값으로만 남김. 3개 파일 전부 적용, 확인 완료.

---

## 문제 2: 씬캡쳐 화면 텍스처가 실제 렌더링보다 미묘하게 뭉개짐 (블러)

**증상**: 색감 문제 해결 후에도, 씬캡쳐로 표시되는 화면이 같은 위치의 실제(백버퍼) 렌더링보다
디테일이 낮고 부드럽게(뭉개져) 보임.

**기각된 가설들** (전부 코드 분석 및 실측으로 확인):
- 텍스처 스트리밍 LOD 저하 — `AddViewInformation` 등록 수식이 엔진의 메인 뷰 등록 코드와 수학적으로
  동일함을 확인, 강제 풀로드(`r.Streaming.FullyLoadUsedTextures 1`) 테스트로도 무관함을 확인.
- TAA — 끄면 오히려 더 나쁨(지글거림). 필요한 설정이었음.
- TSR 미상속 — 씬캡쳐가 메인 뷰의 TSR 업스케일러를 상속받지 못하는 구조적 문제(`bMainViewResolution`
  관련)로 의심했으나, 실제로 켜보니 오히려 화질이 나빠짐(메인 뷰 종횡비에 맞추려 이미지를 강제로
  늘리는 부작용). 무관한 축이었음.
- DOF(피사계 심도) — 꺼봐도 무관함을 확인.
- 렌더타겟 크기와 표시 위젯 크기의 불일치(다운샘플링) — 창을 풀스크린으로 하면 블러가 사라지는
  현상에서 출발한 유력한 가설이었고, 실제로 렌더타겟을 위젯 크기에 맞춰 매 틱 리사이즈하는 로직도
  구현했지만, 로그로 확인해본 결과 리사이즈 자체는 이미 항상 정확했음 — 진짜 원인은 아니었음
  (다만 이 리사이즈 로직 자체는 최종 원인 해결에 필요한 전제 조건이었음, 아래 참고).

**진짜 원인**: 렌더타겟을 위젯 크기에 맞춰 아무리 정확히 리사이즈해도, UMG 위젯의 실제 화면상
픽셀 크기는 DPI 스케일 커브 때문에 본질적으로 소수점 값이다(예: 위젯 슬롯 크기 1226×928 ×
Scale 0.920211). 

렌더타겟은 정수 크기만 가능하므로, 이를 표시하는 머티리얼 브러시는 매 프레임
"거의 1:1이지만 정확히 1:1은 아닌" 스케일로 리샘플링된다. 

기본 Bilinear 필터링은 이 미세한 스케일 차이에서도 인접 텍셀을 섞기 때문에, 창 크기에 따라 이 스케일 값이 1.0에 가까우면 선명하고 멀면 미묘하게 흐려 보인다 — 리사이즈 도중 "가끔 선명, 가끔 블러"였던 이유. 실제 렌더링(UGV RCWS의
`PrimaryViewCamera`)은 텍스처 샘플링 단계 자체가 없이 백버퍼에 직접 그려지므로 이 문제가 원천적으로
없었다.

**수정**:
1. 각 씬캡쳐의 렌더타겟을 표시 위젯의 실제 픽셀 크기에 맞춰 매 틱 리사이즈 (`SetSightRenderTargetPixelSize`
   / `SetCameraRenderTargetPixelSize` / `SetRenderTargetPixelSize`).
2. 렌더타겟의 텍스처 필터링을 **Nearest**로 설정 — 근사-1:1 스케일에서의 보간 자체를 제거.

RCWS/UAV/QuadCam(트럭+UGV 4방향) 전부 적용.

---

## 문제 3: UGV RCWS(실제 렌더링) FOV가 TitanTruck RCWS(씬캡쳐)보다 좁게 보임

**원인**: `RCWSComponent`의 `PrimaryViewCamera`(UGV RCWS가 쓰는 실제 렌더링 카메라)가
`AspectRatioAxisConstraint`를 기본값(`MaintainYFOV`)으로 두고 있었음 — `ULocalPlayer`가 카메라의
(기본 16:9로 가정된) `AspectRatio` 값을 실제 표시 사각형에 맞춰 재계산하면서 수평 FOV를 좁힘.

**수정**: `bOverrideAspectRatioAxisConstraint=true` + `AspectRatioAxisConstraint=MaintainXFOV` 추가.
확인 완료.

---

## 최종 코드 상태

| 파일 | 변경 내용 |
|---|---|
| `RCWSComponent.h/.cpp` | CineCamera FOV 동기화, `PrimaryViewCamera` AspectRatio 수정, `SightRenderTargetFilter`(기본 Nearest), `bEnableMainViewResolution`(기본 false), `SetSightRenderTargetPixelSize()` |
| `UAVPawn.h/.cpp` | CineCamera FOV 동기화, `CameraRenderTarget->Filter = TF_Nearest`, `SetCameraRenderTargetPixelSize()` |
| `QuadCamComponent.h/.cpp` (QuadCamModule 플러그인) | CineCamera FOV 동기화, 4개 렌더타겟 전부 Nearest 필터, 범용 `SetRenderTargetPixelSize()` |
| `Monitor1Widget.h/.cpp` | `RefreshMainViewResolution()` / `RefreshQuadCamResolution()` / `RefreshUAVCameraResolution()` — `NativeTick`에서 매 틱 호출, 표시 위젯 크기에 맞춰 렌더타겟 리사이즈 |
| `TargetDetectionComponent.cpp` | 디버그 구체 표시(`DrawDebugSphere`) 하드 비활성화 — `bCaptureEveryFrame=true`와 충돌해 프레임 1에서 캡쳐가 얼어붙던 문제의 원인이었음 |

**미적용 범위**: `MissionDashboardWidget`/`Monitor2Widget`/`QuadCamUIWidget`(레거시/보조 대시보드)은
아직 위젯 쪽 리사이즈 호출을 연결하지 않음. 백엔드(Nearest 필터, 리사이즈 함수)는 이미 준비되어
있으므로 필요해지면 `Monitor1Widget`과 동일한 패턴으로 붙이면 됨.
