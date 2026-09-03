# 적군 동士사격 방지 — 사격선 안전장치 이식

2026-09-02 / 완료 / 아군에만 있던 `FireLaneAllyMarginCm` 장치를 적군에 `FireLaneFriendlyMarginCm`으로 이식. 발사 3개 지점 전부 적용.

## 증상

적군 보병이 자기 앞에 다른 적군이 서 있는데도 그대로 쏴서 서로 죽이는 일이 잦음(사용자 리포트).

## 원인

아군(`UAllyFormationComponent`)에는 2026-08-06부터 **사격선 안전장치**가 있었다
(`ally_move.md` 9절 3차 안전망): 발사 직전 나-표적 사이 선분에 다른 아군이 `FireLaneAllyMarginCm`
(60cm) 이내로 걸쳐 있으면 발사를 보류한다.

**적군(`UEnemyCombatComponent`)에는 이에 해당하는 장치가 아예 없었다.** 조준·사격 로직은 아군을
많이 참고해 만들어졌지만 이 안전망만 빠져 있었음.

## 수정

### 신설 프로퍼티

```cpp
// EnemyCombatComponent.h
UPROPERTY(EditAnywhere, Category = "Enemy|Combat", meta = (ClampMin = "0.0"))
float FireLaneFriendlyMarginCm = 60.f;   // 0이면 끔(이전 동작)
```

아군 쪽과 같은 기본값(60cm).

### 판정 — 아군과 같은 계산, 다른 후보 출처

```cpp
bool UEnemyCombatComponent::IsFireLaneBlockedByFriendlyEnemy(const FVector& MuzzleLocation,
                                                             const FVector& TargetLocation) const
```

선분 위 사영(`AlongLine`)으로 "사선 뒤쪽"과 "표적 너머"를 걸러내고, 선분까지의 수직거리가
마진보다 가까우면 차단 — 아군 `IsFireLaneBlockedByAlly`와 동일한 기하 계산이다.

**후보 출처만 다르다**:

| | 후보 출처 |
|---|---|
| 아군 | `UScenarioStateSubsystem::GetRegisteredAllies()` (아군 전용 레지스트리) |
| 적군 | `UDetectableTargetSubsystem`에서 `Faction == Enemy`만 필터 |

적군 전용 레지스트리가 따로 없어서, `PickTargetFromOverlaps`가 이미 쓰고 있는 탐지 레지스트리를
재사용했다. 부수 이점 — **사망한 적은 `SetIncapacitated`로 레지스트리에서 빠지므로 시체 때문에
사격이 막히지 않는다.**

### 적용 지점 3곳

| 위치 | 상황 |
|---|---|
| `TickCombatPoseCycle` (~1217) | 교전 중 3~4발 버스트(`Multicast_TriggerFireAtAlly`) |
| `TickAmbush` 계열 (~949) | 매복 단발(`Multicast_TriggerFireSingleShotAtNearestAlly`) |
| 동일 패턴 (~1056) | 또 다른 단발 경로 |

버스트 쪽은 기존 `bCoverAllowsFire` 조건에 `&& !bLaneBlocked`를 추가했다. **쿨다운을 리셋하지
않으므로** 막혔을 때는 다음 틱에 바로 재확인된다 — 쏘기를 포기하는 게 아니라 기회를 미루는 것
(아군 쪽과 동일한 처방).

## 한계 (아군과 동일)

- **총구를 상하로 비껴 쏘는 2차 회피는 없다.** 전용 애니메이션이 필요해 아군에서도 범위 밖으로
  미뤄둔 항목. 지금은 "막혀 있으면 잠깐 기다렸다 재확인"만 한다.
- 전투 자세 마커 배치가 서로를 계속 가리도록 되어 있으면 뒤쪽 개체가 오래 사격을 못 할 수 있다.
  마진(60cm)을 줄이거나 마커 간격을 벌리는 것으로 조정.
- 판정 기준점은 총구가 아니라 `Owner->GetActorLocation()`(액터 중심) — 아군 쪽도 같다.

## 적용

C++ 변경이라 **리빌드 필요**. BP/레벨 값 변경 없음. 마진 조정은 각 적군의 `EnemyCombat`
컴포넌트에서 `FireLaneFriendlyMarginCm`으로.
