# "다른 축 RCWS가 작동 안 함" 조사 — 실제 원인은 사거리

2026-09-01 / 완료(1차 원인 확정) / 트럭이 안 쏘는 건 axis 버그가 아니라 탐지 사거리 밖(869m vs 400m). 부수로 데모 발사 모드를 점사로 추가.

## 신고 내용

PIE 창 하나로 테스트 중, **자기 축이 아닌 RCWS가 잘 작동하지 않음**:

- UGV 축(demo) → UGV는 완벽, **트럭은 적 감지·자동사격이 전혀 안 됨**
- 자체방호 축(demo solo) → UGV가 감지는 되는 것 같은데 이상하게 작동

> ## ⚠️ 2026-09-02 정정 — 1번의 결론이 틀렸음
>
> 사용자 확인: **3차 전투지는 트럭 바로 앞**이고, 시나리오 로그에도 `EnemyFleeToZone3` →
> `CommandPostFire`가 정상 발동했다. 즉 적은 `MaxDetectionRange`(400m) 안으로 들어왔고,
> 아래 "사거리 밖" 설명은 **초기 배치 좌표만 보고 내린 잘못된 결론**이었다.
>
> 진짜 원인은 4절 — **50픽셀 게이트 + 광각 렌즈 + 자동줌 비활성이 겹쳐 보병 탐지 사거리가
> 약 20~35m로 붕괴**한 것. 아래 1절은 "초기 배치 기준 거리"라는 사실 관계로만 남겨둔다.

## 1. (정정됨) 초기 배치 기준 거리 — 결론은 틀렸으나 수치는 유효

레벨 실측:

| | 위치 | 가장 가까운 적까지 |
|---|---|---|
| `BP_TitanTruck_C_4` | (57330, 12280, -3920) | **869m** |
| `BP_UGV_Vehicle_new_C_3` | (약 -1732, 18529, 4127) | **291m** |

트럭 `TargetDetection.MaxDetectionRange` = **40000cm = 400m**.

`UTargetDetectionComponent::EvaluateTarget`은 거리 검사에서 조기 return한다:

```cpp
if (FVector::Dist(CameraLocation, WorldCenter) > MaxDetectionRange) return Result;
```

869m > 400m이므로 트럭은 **적을 하나도 탐지하지 못한다** → `CurrentAutoAimTarget`이 영원히 null
→ `bWantsAutoFire` false → 발사 시도 자체가 없음.

이게 로그와 정확히 맞는다: 트럭에 대해 `발사!`도 없고 **`발사 시도했지만 CanFire() 실패` 경고조차
없다**(그 경고는 "쏘고 싶은데 막혔을 때"만 찍힘). 즉 막힌 게 아니라 **애초에 쏘려 하지 않는** 상태.

**축과 무관하다** — 어느 축에서 돌려도 동일하다. 자체방호 축에서 트럭이 쏘는 것처럼 보였다면
그때는 적이 400m 안으로 들어왔거나 다른 단계였을 것.

### 문서의 기존 설명이 부정확했음

`2026-09-01_scenario_run_modes_demo_fullsystem.md` 3.2절에 "트럭 RCWS도 **유효사거리(2000m)**
밖이라 3차 전투지 전엔 자연히 사격하지 않는다"고 적혀 있는데, 실제로 먼저 걸리는 건
**무기 유효사거리 2000m가 아니라 탐지 사거리 400m**다. 결론(안 쏜다)은 같지만 이유가 5배 다르다.

### 선택지

- **그대로 둔다** — 시나리오상 트럭은 3차 전투지에서만 교전. 적이 400m 안으로 들어오면 자동으로 쏜다.
- **트럭 `MaxDetectionRange`를 올린다** — 예: 100000(1km). 단, 그러면 데모 시작부터 트럭이
  원거리 사격을 시작해 시나리오 흐름이 앞당겨질 수 있음(3.2절이 "너무 일찍 쏘지 않는다"고
  보장하던 근거가 사라짐).

→ **사용자 판단 필요.** 코드로 바꾸지 않고 남겨둠.

## 2. 로그로 확인된 정상 동작

두 축 모두에서 데모 자동사격 전환은 정상:

```
[ScenarioStateSubsystem] 데모 자동사격: UGV(BP_UGV_Vehicle_new_C_3) RCWS를 ARM + AutoFire로 전환.
[ScenarioStateSubsystem] 데모 자동사격: 이동형지휘소(BP_TitanTruck_C_4) RCWS를 ARM + AutoFire로 전환.
```

`ApplyDemoRCWSAutoFire`는 축을 전혀 보지 않고 두 대 다 켠다 — 여기엔 축 게이트가 없다.

UGV는 **약 1초 간격**으로 계속 발사(로그 11:50:51 → 11:50:52.6 → 11:50:53.4 …). 같은 날 추가한
`AutoFireCycleIntervalSeconds`(단발/점사 사이클 재시작)가 의도대로 동작 중임을 확인.

## 3. 진짜 축 의존 지점 (2차 이슈, 미수정)

축에 따라 실제로 갈리는 건 이것들이다:

**(a) `bDisableSightCapture`** — `ATitanTruck::BeginPlay`와 `UVehicleRtspBridgeComponent`가
로컬 축이 자기 축이 아니면 `RCWS->bDisableSightCapture = true`로 조준경 씬 캡쳐를 끈다(아무도 안
보는 풀퀄리티 캡쳐를 막는 성능 목적). **탐지 로직에는 무해** — 트랜스폼/FOV는 계속 갱신되고,
탐지는 수학적 투영 + 라인트레이스라 렌더 결과가 필요 없다.

**(b) `SetRenderedViewSize` 호출자가 각 축 자기 모니터 위젯뿐** ← 이쪽이 문제

`Monitor1Widget`/`UGVTestDashboardWidget`(UGV축)과 `SelfDefenseDashboardWidget`/
`SelfDefenseMonitor2Widget`(자체방호축)만 `RCWS->SetRenderedViewSize()`를 부른다. 따라서
**비로컬 축 차량은 아무도 이걸 안 불러준다.**

그러면 같은 날 추가한 `MinScreenSizePixels`(50px) 게이트의 기준 해상도가
`UTargetDetectionComponent::ResolveRenderedResolution()`에서 폴백된다:

| | 로컬 축 | 비로컬 축(폴백) |
|---|---|---|
| 기준 해상도 | 모니터 위젯의 실제 슬롯 픽셀 | 조준경 RT 크기 (UGV **1226x928** / 트럭 **1116x622**) |

즉 **"화면상 50픽셀"의 실제 각크기가 축에 따라 최대 2배까지 달라진다.** 탐지 사거리가 축마다
다르게 나오는 셈 — "자체방호 축에서 UGV가 이상하게 작동"의 유력 후보.

### 어떻게 고칠지 (미결)

두 가지 의미론 중 선택이 필요하다:

1. **실제 표시 크기 유지**(현재) — 사용자 원래 요구("화면 상 50픽셀")에 충실하지만, 창 크기와
   보는 축에 따라 AI 탐지 사거리가 달라진다.
2. **고정 기준 해상도로 전환** — 조준경 RT 크기(또는 별도 기준 해상도)만 쓰고 위젯 크기는
   화면비 계산에만 사용. 축·창 크기와 무관하게 항상 같은 동작. AI 거동을 "누가 보고 있는지"에
   의존시키지 않는다는 점에서 설계적으로는 이쪽이 옳다.

→ 의미론 선택이라 임의로 바꾸지 않고 남겨둠.

## 4. 데모 발사 모드 = 점사 (구현 완료)

```cpp
// ScenarioConfig.h
UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Scenario|Run Mode")
ERCWSFireMode DemoFireMode = ERCWSFireMode::Burst;
```

`ApplyDemoRCWSAutoFire`가 ARM/AutoFire와 함께 `RCWS->SetFireMode(Config->DemoFireMode)`를 건다.
`FireMode`는 `URCWSFireControlComponent`가 아니라 `URCWSComponent::CurrentData`에 있으므로
RCWS 쪽에 건다는 점만 주의.

점사가 기본인 이유: 데모는 무인 방치로 계속 도는데 연사면 탄약 600발이 금방 마르고 화면도
단조로워진다. 실환경(FullSystem)에서는 통제기 SW가 `RC_FireMode`로 정하므로 이 값은 데모 전용.

`BurstRoundCount`(기본 3)와 같은 날 추가한 `AutoFireCycleIntervalSeconds`(기본 1초)가 같이 걸려서,
데모에서는 **1초 간격 3점사**가 된다.

## 5. 진짜 원인 (2026-09-02) — 50px 게이트 × 광각 렌즈 × 자동줌 OFF

2026-09-01 하루 동안 각각은 타당했던 세 변경이 겹치면서 탐지 사거리가 무너졌다:

1. `MinScreenSizePixels = 50` 신설 (사용자 요청: "화면상 50픽셀은 돼야 감지")
2. 조준경 렌즈 35mm → **10mm** (수평 화각 37.5° → **99.8°**, 약 2.7배 광각)
3. **자동 줌 비활성화**(`bAutoZoomEnabled=false`) → 배율이 기본 0.5x에 영구 고정

화각이 2.7배 넓어지면 같은 표적의 화면상 픽셀 수는 2.7배 작아진다. 게다가 자동 줌이 꺼져 있어
**확대해서 확인할 방법 자체가 없다.**

보병(약 1.8m × 0.6m)이 50픽셀로 보이는 최대 거리:

| 배율 | 기준 1920×1080 | 트럭 RT 1116×622 | UGV RT 1226×928 |
|---|---|---|---|
| **0.5x (기본)** | **33 m** | **19 m** | **28 m** |
| 1.0x | 66 m | 38 m | 57 m |
| 2.0x | 132 m | 76 m | 113 m |
| 4.0x | 264 m | 152 m | 227 m |
| 8.0x | 528 m | 304 m | 454 m |
| 16.0x | 1056 m | 608 m | 907 m |

즉 **기본 상태에서 보병은 19~33m 안에 들어와야만 탐지된다.** 트럭이 3차 전투지에서 코앞의 적을
못 잡은 이유가 이것이다(적이 트럭 19m 안까지 들어와야 함). `MaxDetectionRange` 400m는 애초에
발동조차 못 하는 상한이었다.

### 왜 이게 "물리적으로는 맞는" 값인가

100° 화각 화면에서 200m 거리의 사람은 1080p 기준 **실제로 약 8픽셀**이다. 사용자의 최초 문제
제기("10픽셀도 안 되는데 감지해버리면 흉내만 낸 것")는 정확한 관찰이었다 — 광각에서 원거리
표적이 몇 픽셀에 불과한 건 사실이다.

원래 `MinScreenSizeFraction` 설계 주석도 이 전제였다: *"줌인하면 같은 대상이 다시 잡힌다 —
'멀어서 뭔지 모르겠다 → 줌으로 확인한다'는 실제 관측 절차와 맞는다."* **그런데 그 줌을
꺼버렸다.** 확인 수단 없이 게이트만 남은 것이 이번 사고의 본질.

### ⚠️ 결정적 정정 (2026-09-02) — 값이 차량마다 달랐다

위 표는 "양쪽 다 50px"을 전제로 썼는데 **사실이 아니었다.** 실측:

| | `MinScreenSizePixels` |
|---|---|
| UGV (BP + 레벨 인스턴스) | **5** — 사용자가 낮춰둠, 정상 반영돼 있었음 |
| 트럭 (BP + 레벨 인스턴스) | **50** — 안 바뀜 |

**이게 "UGV는 잘 되는데 트럭은 전혀 안 됨"의 진짜 이유다.** 축(axis)과 아무 상관이 없었다.
두 차량의 탐지 임계값이 10배 달랐을 뿐이다:

| 임계값 | 0.5x 보병 탐지 최대거리 (기준 1920×1080) |
|---|---|
| **5px** (UGV였던 값) | **330 m** |
| **12px** (트럭 적용값) | **137 m** |
| 20px | 82 m |
| 50px (트럭이었던 값) | **33 m** |

조사 과정에서 세션 초반에 읽은 "UGV=50"을 계속 인용한 것이 오진의 원인이었다 — **값을
바꾼 뒤에는 반드시 다시 읽을 것**(BP CDO와 레벨 인스턴스 양쪽 다).

### 적용 (2026-09-02)

| | 적용 값 |
|---|---|
| 트럭 (BP + 레벨 인스턴스) | 50 → **12** |
| UGV | **5 유지** — 사용자가 직접 고른 값이라 건드리지 않음 |

두 차량 임계값이 다른 상태(5 vs 12)이므로, 통일하고 싶으면 한쪽으로 맞출 것.

자동 줌 재활성화(`bAutoZoomEnabled=true`)나 렌즈 되돌림(10→25mm)도 대안이지만, 자동 줌은
통제기 프로토콜 근거로 끈 것이고 광각도 의도된 것이라 임계값 조정으로 해결했다.

## 6. 고정 기준 해상도 적용 (3번, 완료)

```cpp
UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Detection")
FIntPoint ScreenSizeReferenceResolution = FIntPoint(1920, 1080);   // 0,0이면 예전 동작
```

`ResolveRenderedResolution()`이 이 값을 최우선으로 반환한다. 화면비(`ResolveAspectRatio`)는
그대로 실제 렌더 기준을 쓴다 — 그쪽은 UV 투영 정확도 문제라 실제 프레임을 따라가야 맞다.

이로써 탐지 결과가 **보는 축·창 크기와 무관하게 결정적**이 된다. 부수적으로 트럭 기준
해상도가 1116×622 → 1920×1080이 되면서 탐지 사거리가 19m → 33m로 늘었다(여전히 부족 —
5절 참고).

## 7. 진단 로그 추가

```cpp
UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Fire Control|Debug")
bool bLogAutoFireReadiness = false;
```

AutoFire인데 발사가 안 될 때 **어느 관문에서 막혔는지** 초당 1회로 찍는다:

```
[RCWSFireControl] BP_TitanTruck_C_4 자동사격 대기: Armed=Y Detected=0 Target=none
  CamErr=(0.00,0.00)/3.00 MuzErr=0.00/2.00 LockGauge=0.00 SpinGauge=1.00
```

읽는 법 — `Detected=0`이면 탐지 문제(사거리/픽셀 게이트/차폐), 타겟은 있는데 `CamErr`가
허용오차보다 크면 슬루가 못 따라가는 것, 정렬은 됐는데 `LockGauge`가 안 차면 표적이 계속
바뀌는 것, `SpinGauge=0`이면 `bFireSystemActive`가 꺼진 것.

## 적용

C++ 변경이라 **리빌드 필요**. `DemoFireMode`/`ScreenSizeReferenceResolution`/
`bLogAutoFireReadiness` 모두 새 프로퍼티라 레벨 인스턴스에도 자동 반영됨.
