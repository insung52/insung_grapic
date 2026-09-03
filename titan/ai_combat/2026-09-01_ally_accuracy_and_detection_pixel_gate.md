# 아군 사격 정확도 너프 · 탐지 최소 픽셀 크기 게이트

2026-09-01 / 완료 / 아군 탄 퍼짐 1.5→3.0도, TargetDetectionComponent에 MinScreenSizePixels 신설(화면상 50px 미만이면 미탐지) — UGV/트럭에 50 적용 완료.

## 1. 아군 사격 정확도 너프

아군 사격은 C++이 아니라 **`BP_AR4Rifle`의 `BulletSpreadDegrees`** 로 되어 있음
(`ai_combat/ally_ai_combat_system_status.md` 5절 — 발사 시 총구 정면 기준 원뿔 안에서
`RandomUnitVectorInConeInDegrees`로 방향을 뽑아 스폰 회전과 물리 속도 양쪽에 동일 적용).

**아군(`BP_AR4Rifle`)과 적군(`BP_EnemyRifle`)은 별개 에셋**이라 아군만 조정 가능 —
둘 다 1.5°였고, 아군만 **3.0°** 로 올림(적군은 1.5° 유지).

기존 문서의 권장 밴드("일반 아군 3~5°, 정예 0.5° 이하")의 가장 완만한 끝값을 골랐음.

탄 퍼짐 반각별 탄착 반경(m):

| 반각 | 25m | 50m | 100m | 200m |
|---|---|---|---|---|
| 1.5° (이전) | 0.65 | 1.31 | 2.62 | 5.24 |
| **3.0° (현재)** | **1.31** | **2.62** | **5.24** | **10.48** |
| 4.0° | 1.75 | 3.50 | 6.99 | 13.99 |
| 5.0° | 2.19 | 4.37 | 8.75 | 17.50 |

더 너프하려면 4~5°, 되돌리려면 1.5°. 아군 개체별로 다른 값을 주면 정예/일반 차등도 가능.

## 2. 탐지 최소 픽셀 크기 게이트

### 배경

"화면에서 10픽셀도 안 되어 보이는 대상을 감지해버리면 누가 봐도 실제 객체탐지가 아니라
흉내만 낸 것" — 사용자 지적. 최소 50픽셀로 보여야 감지되도록.

### 이미 있던 것

`UTargetDetectionComponent::MinScreenSizeFraction`(화면 비율 기준 겉보기 크기 필터)이
**이미 구현돼 있었고 값만 0(꺼짐)** 이었음. 로직 자체는 8개 바운딩박스 코너를 화면 UV로
투영해 만든 박스의 긴 변을 임계값과 비교하는 방식으로 정상 동작.

### 왜 비율이 아니라 픽셀을 새로 만들었나

이 프로젝트는 RTSP 송출/모니터 위젯마다 렌더 해상도가 제각각이라(`rtsp/` 문서), 같은
비율이라도 실제 보이는 픽셀 수가 다름. "사람 눈에 몇 픽셀로 보이느냐"가 곧 "알아볼 수
있느냐"이므로 픽셀이 더 맞는 기준. 그래서 비율 필터는 그대로 두고 픽셀 필터를 병렬로 추가.

### 구현

```cpp
// TargetDetectionComponent.h
UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Detection", meta = (ClampMin = "0.0"))
float MinScreenSizePixels = 0.f;   // 0 = 끔(기본)

void SetRenderedViewSize(FIntPoint InSize);   // 화면비도 같이 갱신
FIntPoint ResolveRenderedResolution() const;  // 위젯 표시 크기 > 캡쳐 렌더타깃 크기 > (0,0)
```

판정(`EvaluateTarget`, UV 박스를 구한 직후):

```cpp
PixelsX = ScreenSizeUV.X * Resolution.X;   // UV는 0~1이라 축별 해상도를 각각 곱해야 함
PixelsY = ScreenSizeUV.Y * Resolution.Y;   // (16:9는 같은 UV라도 가로 픽셀이 더 많음)
if (FMath::Max(PixelsX, PixelsY) < MinScreenSizePixels) -> 미탐지
```

**해상도를 모르면(둘 다 미설정) 조용히 통과시킴** — 모른다고 전부 걸러버리면 탐지가 통째로
죽음. 켜 놨는데 아무것도 안 잡히면 여기부터 의심할 것(`bDebugDrawDetection`을 켜면
거절된 대상의 픽셀 크기와 기준 해상도가 로그에 찍힘).

### 해상도 전달 경로 (이번에 뚫은 것)

모니터 위젯들(`Monitor1Widget`, `SelfDefenseDashboardWidget`, `SelfDefenseMonitor2Widget`,
`UGVTestDashboardWidget`)이 이미 매 틱 자기 슬롯의 실제 픽셀 크기를
`URCWSComponent::SetRenderedViewSize(FIntPoint)`로 넘기고 있었는데, 그 함수가 **화면비만
뽑아 쓰고 픽셀 수는 버리고 있었음**. 이제 탐지 컴포넌트로 그대로 전달함
(가드는 기존 `SetRenderedAspectRatio`와 동일 — 그 탐지 컴포넌트가 실제로 이 SightCamera를
보고 있을 때만).

즉 기준이 되는 "화면"은 **조작자가 모니터에서 실제로 보는 크기**임. 줌인하면 같은 대상이
커 보이므로 다시 잡히고, 이는 "멀어서 뭔지 모르겠다 → 줌으로 확인한다"는 실제 관측 절차와
일치함(기존 `MinScreenSizeFraction` 주석의 설계 의도 그대로).

### BP 값 설정 (리빌드 후 완료됨)

`MinScreenSizePixels` 기본값은 **0(꺼짐)** 으로 뒀음 — 이 컴포넌트를 같이 쓰는 드론 짐벌/
CCTV/전장 카메라의 동작을 말없이 바꾸지 않기 위함(기존 `MinScreenSizeFraction`이 같은 이유로
0을 기본으로 둔 것과 동일한 관례).

따라서 아래 두 곳에 50을 넣어야 실제로 켜짐 — **리빌드 후 MCP로 적용 완료(값 확인함)**:

- `BP_UGV_Vehicle_new` → `TargetDetection` → Detection → Min Screen Size Pixels = **50** ✔
- `BP_TitanTruck` → `TargetDetection` → 동일 ✔

(새로 추가한 C++ 프로퍼티라 리빌드 전에는 에디터가 이 프로퍼티를 몰라서 MCP로도 못 넣었음 —
`could not be set` 에러로 확인. 리빌드 후 정상 적용됨. 두 BP 모두 **저장 필요**.)

드론 짐벌/CCTV/전장 카메라는 여전히 0(꺼짐) — 필요해지면 각 BP에서 개별로 켜면 됨.

## 변경 파일

- `Detection/TargetDetectionComponent.h` — `MinScreenSizePixels`, `SetRenderedViewSize`,
  `ResolveRenderedResolution`, `RenderedViewSize`
- `Detection/TargetDetectionComponent.cpp` — 픽셀 게이트 판정 + `ResolveRenderedResolution` 구현
- `Vehicles/RCWSComponent.cpp` — `SetRenderedViewSize`가 픽셀 크기를 탐지 컴포넌트로 전달
- `BP_AR4Rifle` (MCP) — `BulletSpreadDegrees` 3.0 ※ **P4 체크아웃 후 저장 필요**

## 미해결 — 나뭇잎 관통 탐지

별도 문서 `level_new_kadex_0811/2026-09-01_foliage_occlusion_ideas.md` 참고.
