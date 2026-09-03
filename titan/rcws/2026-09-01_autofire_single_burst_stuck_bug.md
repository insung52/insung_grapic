# 자동사격 + 단발/점사가 한 발만 쏘고 멈추는 버그

2026-09-01 / 완료 / 자동사격에는 "뗄 트리거"가 없어 사이클 리셋이 락온 시점 한 번만 걸리던 문제 — AutoFireCycleIntervalSeconds로 시간 기반 재시작 추가.

## 증상

RCWS 제어 모드가 **AutoFire**인 상태에서 발사 모드가 **단발(Single)** 이면, 타겟을 잡고
한 발 쏜 뒤 **다시는 쏘지 않음**. 타겟이 바뀌어야(=죽거나 놓쳐서 락온이 풀렸다 다시 걸려야)
그때 또 한 발. 점사(Burst)도 동일 — `BurstRoundCount`발 쏘고 영영 멈춤.
연사(Auto)는 정상.

## 원인

`URCWSFireControlComponent::TickComponent`의 2026-08-16 발사 모드 게이팅:

```cpp
if (bWantsToFire && !bWasWantingToFireLastTick)   // 트리거 엣지
{
    ShotsFiredThisTrigger = 0;
}
bWasWantingToFireLastTick = bWantsToFire;
```

Single/Burst는 `ShotsFiredThisTrigger`가 허용 발수에 도달하면 더 안 쏘고, 이 카운트는
**`bWantsToFire`의 false→true 엣지에서만** 리셋된다. 수동 트리거라면 조작자가 손을 떼는
순간 false가 되니 정상 동작한다.

그런데 자동사격의 `bWantsToFire`는

```cpp
bWantsAutoFire = bFireSystemActive && CurrentMode == AutoFire && bIsLockedOn
                 && BarrelSpinGaugeValue >= 1.f && CurrentAutoAimTarget != nullptr;
```

로, **락온이 유지되는 동안 계속 true**다. 즉 엣지가 락온 시작 시점에 딱 한 번만 발생하고,
그 뒤로는 락온이 풀릴 때까지 리셋될 기회가 없다 — **자동사격에는 뗄 트리거가 없다**는 게
문제의 본질. "타겟이 바뀌지 않는 한"이라는 사용자 관찰이 정확히 이 조건이었음.

## 수정

허용 발수를 먼저 구하고(`ShotsAllowedThisCycle`), **자동사격일 때만** 사이클 완료 후
경과 시간을 재서 스스로 다음 사이클을 시작하도록 함:

```cpp
if (bWantsAutoFire && !bManualFireHeld && ShotsFiredThisTrigger >= ShotsAllowedThisCycle)
{
    TimeSinceCycleComplete += DeltaTime;
    if (TimeSinceCycleComplete >= AutoFireCycleIntervalSeconds)
    {
        ShotsFiredThisTrigger = 0;
        TimeSinceCycleComplete = 0.f;
    }
}
const bool bFireModeAllowsMoreShots = ShotsFiredThisTrigger < ShotsAllowedThisCycle;
```

신설 프로퍼티:

```cpp
UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Fire Control|Weapon", meta = (ClampMin = "0.0"))
float AutoFireCycleIntervalSeconds = 1.f;   // 자동사격 중 단발/점사 사이클 간격
```

`TimeSinceCycleComplete`는 **매 발사 시 0으로 리셋**하므로 실질적으로 "마지막 탄 발사 이후
경과 시간". 즉 점사면 마지막 3번째 탄부터 1초 뒤 다음 점사가 나간다.

### 설계상 지킨 것

- **수동 트리거는 그대로.** `bManualFireHeld`면 이 로직을 타지 않음 — 수동은 조작자가 직접
  떼었다 당기는 게 맞는 동작이고, "쥐고 있으면 한 발만"이라는 기존 의미를 유지해야 함.
- **연사(Auto)는 무영향.** `ShotsAllowedThisCycle`이 `int32` 최대값이라 위 블록 자체가
  절대 참이 되지 않음.
- 사이클 **내부** 발사 간격은 기존 `ShotIntervalSeconds`(FireRateRPM 유래, 1200rpm이면
  0.05초)가 그대로 담당. 이번에 추가한 건 사이클 **사이** 간격뿐.

## 튜닝

`AutoFireCycleIntervalSeconds` 기본 1.0초 — 자동 교전에서 단발이면 초당 1발, 점사면
1초 간격으로 3점사. 더 촘촘하게 하려면 낮추고, 뜸하게 하려면 올리면 됨.
`BP_UGV_Vehicle_new` / `BP_TitanTruck` 어디서든 인스턴스 편집 가능.

## 적용

C++ 변경이라 **리빌드 필요**. BP 값 변경은 없음.

⚠ 새로 추가한 프로퍼티라, 리빌드하면 레벨 인스턴스에도 자동 반영됨(인스턴스에 직렬화된
오버라이드가 없는 프로퍼티라서). 기존 프로퍼티였다면 레벨 인스턴스에 따로 넣어야 했음 —
같은 날 겪은 함정, `2026-09-01_rcws_zoom_baseline_and_target_priority.md` 참고.
