# RCWS 줌 기준 재정의 · 자동 줌 비활성화 · 전방 우선 표적 선정

2026-09-01 / 완료 / 줌 기본값을 0.5로 재정의(렌즈 25.53mm로 보정해 화면은 동일), 자동 줌은 토글로 끄고, 차체 전방 45도 원뿔 안의 적을 우선 사격하도록 표적 선정 변경.

## 1. 기존 거리별 자동 줌 정리 (변경 전)

`URCWSFireControlComponent::UpdateAutoZoom`:

```cpp
TargetZoom = CurrentAutoAimTarget ? (RangeMeters / ZoomReferenceMeters) : SearchZoomLevel;
// 이후 MaxAutoZoomChangeRatePerSecond로 레이트 제한, RCWS에서 [MinZoomLevel, MaxZoomLevel]로 클램프
```

값: `ZoomReferenceMeters` 100, `SearchZoomLevel` 0.5, `MinZoomLevel` 0.5, `MaxZoomLevel` 16.
(`BP_UGV_Vehicle_new`는 `MaxAutoZoomChangeRatePerSecond` 1, `SearchSweepHalfRangeDegrees` 30,
`SearchSweepSpeedDegPerSec` 5만 오버라이드. 줌 기준값들은 C++ 기본값 그대로였음.)

| 거리 | 배율 |
|---|---|
| 표적 없음 | 0.5배 |
| 50m 이하 | 0.5배(하한 클램프) |
| 100m | 1배 |
| 200m | 2배 |
| 400m | 4배 |
| 800m | 8배 |
| 1600m 이상 | 16배(상한) |

즉 100m당 1배씩 선형 증가. 1600m에서 이미 최대 배율에 닿았고, 표적이 없거나 100m 이내면
0.5배로 줌아웃했음 — 이 두 가지가 "너무 심하다"는 지적의 실체.

## 2. 자동 줌 — 값 조정 후 최종적으로 비활성화

1차로 사용자 요청대로 값을 조정했음:

- `SearchZoomLevel` 0.5 → **1.0** (표적 없을 때 광각으로 빠지는 동작 제거)
- `ZoomReferenceMeters` 100 → **125** (16배 도달 거리 1600m → **2000m**)
- `UpdateAutoZoom`에 **하한 추가**: `TargetZoom = FMath::Max(TargetZoom, SearchZoomLevel)`.
  이게 없으면 `ZoomReferenceMeters`보다 가까운 적에서 비율이 1.0 미만으로 떨어져,
  "넓게 보는 걸 없애 달라"는 요청과 정반대로 적이 코앞일 때 오히려 0.5배까지 줌아웃함.

이후 사용자가 **자동 줌 자체를 끄기로 결정** — UGV 통제기 프로토콜에 줌 배율 조정이 없어서
운용상 배율이 저절로 바뀔 이유가 없음.

```cpp
UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Fire Control|Auto Zoom")
bool bAutoZoomEnabled = false;   // UpdateAutoZoom 진입 직후 return
```

위 1차 조정값들은 **삭제하지 않고 남겨둠**(사용자 요청: "혹시 모르니 다시 킬 수 있게").
에디터에서 체크박스만 켜면 리빌드 없이 조정된 새 매핑으로 복귀함:
표적없음/125m 이하 1.0배 → 250m 2배 → 500m 4배 → 1000m 8배 → 2000m 이상 16배.

## 3. 줌 배율 기준 재정의 (0.5를 기본으로)

앞선 작업에서 카메라를 UGV 쪽으로 당기면서(X -641.67 → **-142.40**) 초점거리를
35mm → **10mm**(CineFOV 99.82°)로 낮춰 놓은 상태였음. 이 상태에서 0.5배로 가면
화면 FOV가 99.82 / 0.5 = **199.6°** → 코드의 170° 클램프에 걸리며 왜곡이 감당 불가.

### 1차 시도 (실패) — 초점거리로 상쇄

"지금 보이는 화면"을 0.5배로 재정의하려고, CineFOV를 절반으로 줄이고(초점거리 10→25.53mm)
기본 배율을 절반으로 낮췄음. 산수로는 99.82/0.5 = 99.82로 화면이 같아야 맞음.

**사용자 확인 결과 이 방식이 틀렸음**: 화면은 숫자상 같아져도, "렌즈에 넣은 값"(49.91°)과
"실제 보이는 화각"(99.82°)이 계속 어긋난 상태로 남음 — 초점거리를 튜닝할 때마다 2배 암산이
필요하고, 0.5배가 여전히 **문자 그대로 화면을 2배로 넓히는 코드**(`FOVAngle = 렌즈FOV / ZoomLevel`)
위에 얹혀 있는 것이라 근본 해결이 아니었음.

### 2차 (확정) — 계산식에 기준 배율 도입

```cpp
화면 FOV = 렌즈 FOV * (ReferenceZoomLevel / ZoomLevel)   // 예전: 렌즈 FOV / ZoomLevel
```

`URCWSComponent::ReferenceZoomLevel`(신설, 기본 **1.0**) = "화면 FOV가 렌즈 FOV와 정확히
같아지는 배율". 기본 1.0에서는 예전 식과 **완전히 동일**하므로 트럭 등 기존 사용처는 무영향.

`ZoomLevel`과 `ReferenceZoomLevel`을 같은 값으로 두면 **렌즈에 설정한 값이 곧 화면**이 됨.

`RCWSComponent::ZoomLevel`의 C++ 기본값은 **1.0으로 되돌림**. 1차 시도 때 이걸 0.5로 바꿨었는데,
`BP_TitanTruck`이 이 값을 오버라이드하지 않아서 **트럭 화면까지 2배로 넓어지는 부작용**이
있었음(2026-09-01에 발견·수정). 차량별 값은 각 BP에서 명시적으로 오버라이드하는 게 맞음.

식이 쓰이는 곳 3군데를 모두 같이 고쳐야 함: `SyncLensFromCineCamera`, `SetZoomLevel`,
`GetCurrentFOVDegrees`의 폴백.

### 차량별 적용값 — UGV·트럭 통일

두 차량을 **완전히 동일한 세팅**으로 통일함(사용자 요청 — 트럭 렌즈도 UGV와 같은 10mm로).

| | ReferenceZoomLevel | ZoomLevel | 렌즈 | 렌즈 FOV |
|---|---|---|---|---|
| `BP_UGV_Vehicle_new` | **0.5** | **0.5** | 10mm (원래 값 복원) | 99.82° |
| `BP_TitanTruck` | **0.5** | **0.5** | **24mm → 10mm** | 99.82° |

배율별 화면 FOV (두 차량 동일):

| ZoomLevel | 화면 FOV |
|---|---|
| **0.5 (기본)** | **99.82°** |
| 1.0 | 49.91° |
| 2.0 | 24.96° |
| 4.0 | 12.48° |
| 8.0 | 6.24° |
| 16.0 | 3.12° |

**UGV는 기본 화면이 이 변경 전과 정확히 동일**(초점거리를 원래 10mm로 되돌렸으므로 99.82° 그대로).
**트럭은 화면이 실제로 넓어짐** — 예전 기본 화면 52.67°(24mm) → 지금 99.82°(10mm). 렌즈를
UGV와 맞추라는 요청에 따른 의도된 변경이며, 배율 재정의와는 별개의 시각적 변화임.
트럭 `LensSettings`는 그대로(minFocalLength 4라 10mm는 유효 범위 안).

부수 효과 — `MinZoomLevel`(0.5)과 `ReferenceZoomLevel`(0.5)이 같아지면서 **화면 FOV가 렌즈 FOV
보다 넓어질 수 없게 됨**. 170° 안전 클램프가 구조적으로 도달 불가능해짐.

`Filmback`(23.76×13.365mm)과 `LensSettings`(4~1000mm, F22, 9블레이드)는 건드리지 않음.

### `ManualZoomTargetIndex`는 상수로 두면 안 됨

Remote 모드로 들어가는 순간 `UpdateManualZoomRamp`가 아무도 누르지 않았는데 이 인덱스의
배율로 램프해버리는데, **차량마다 기본 배율이 다름**(UGV 0.5, 트럭 1.0). 그래서 상수 대신
`BeginPlay`의 `SyncManualZoomIndexToCurrentZoom()`이 RCWS의 실제 현재 배율과 가장 가까운
단계로 맞춤. 거리 비교는 **로그2 공간**에서 — `ManualZoomLevels`가 배수 눈금(0.5,1,2,…,16)이라
선형 거리로 재면 큰 배율 쪽으로 쏠림.

## 4. 전방 45도 우선 표적 선정

`SelectNearestEnemyTarget()`이 무조건 전체 최근접 적을 고르던 것을, 한 번의 순회에서
후보를 두 갈래로 모으도록 변경:

- `NearestInArc` — 차체 전방 원뿔 안의 최근접 적
- `NearestOverall` — 기존과 동일한 전체 최근접 적

전방 후보가 있으면 그걸, 없으면 전체 최근접으로 폴백. 즉 **"전방에 적이 있으면 무조건
그쪽부터, 없으면 예전 그대로"**.

```cpp
bool  bPrioritizeForwardArcTargets = true;    // 끄면 이전과 완전히 동일
float ForwardPriorityHalfAngleDegrees = 45.f; // 반각 — 좌우 각 45도, 총 90도 원뿔
```

구현 주의점:

- 차체 전방은 `UpdateSearchSweep`과 똑같이 `Owner->GetActorRotation().Yaw`를 그대로 씀.
  `InitialMountYawOffsetDegrees`를 더하면 안 됨 — 2026-07-28 스윕 중심 버그와 같은 함정.
- 판정은 **XY 평면에 투영**해서 함. 3D forward를 쓰면 차체가 경사에서 기울 때마다 같은 적이
  원뿔에 들어왔다 나갔다 하며 표적이 깜빡임.
- 총구 바로 위/아래에 겹쳐 수평 방향이 정의되지 않는 적은 전방 판정에서 제외(전체 최근접
  후보로는 이미 잡혀 있음).

### 남은 이슈 — 스티키 표적과의 상호작용

`UpdateAutoAim`의 2026-08 스티키 표적 로직이 상위에 있어서, 이 우선순위는 **표적을 새로 잡는
순간에만** 적용됨. 이미 후방의 적을 물고 있으면 전방에 새 적이 나타나도 기존 표적이
`DetectedTargets`에서 빠지기 전까지 안 바꿈. "전방 적이 나타나면 즉시 전환"까지 원하면
스티키 조건에 원뿔 검사를 추가해야 하는데, 2026-08 "사용자 확정 사항"을 뒤집는 것이라
일부러 안 건드림 — **사용자 판단 필요**.

## 변경 파일

- `Source/titan_example/Vehicles/RCWSComponent.h` — `ZoomLevel` 기본값 0.5
- `Source/titan_example/Vehicles/RCWSFireControlComponent.h` — `bAutoZoomEnabled`,
  `bPrioritizeForwardArcTargets`, `ForwardPriorityHalfAngleDegrees`, `SearchZoomLevel` 1.0,
  `ZoomReferenceMeters` 125, `ManualZoomTargetIndex` 0
- `Source/titan_example/Vehicles/RCWSFireControlComponent.cpp` — `UpdateAutoZoom` 가드+하한,
  `SelectNearestEnemyTarget` 전방 우선
- `BP_UGV_Vehicle_new` (MCP) — `RCWSSightCineCamera.CurrentFocalLength` 25.5285

C++ 변경이라 **리빌드 필요**. BP는 별도 저장 필요.
