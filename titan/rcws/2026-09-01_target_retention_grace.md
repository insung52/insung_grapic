# 표적 고정 유예 — 락온이 갈팡질팡하던 문제

2026-09-01 / 완료 / 표적 유지 조건을 "이번 스캔 DetectedTargets 멤버십"에서 "탐지 유실 시간 유예(TargetRetentionGraceSeconds)"로 바꿈.

## 증상

RCWS가 적을 발견하고 사격 준비하는 동안 표적을 계속 바꿔 물어서, 락온 게이지가 다 차지
못하고 결국 쏘지 않음. 적군이 움직이는 상황에서 두드러짐.

## 원인

`UpdateAutoAim`의 2026-08 스티키 표적 유지 조건이 이랬음:

```cpp
bCurrentTargetStillValid = Target && IsValid(Target) &&
    TargetDetection->DetectedTargets.ContainsByPredicate(...);   // 이번 스캔 멤버십
if (!bCurrentTargetStillValid) Target = SelectNearestEnemyTarget();
```

`DetectedTargets`는 `ScanIntervalSeconds`(0.1초)마다 재계산되고, 신뢰도 히스테리시스
(획득 0.6 / 상실 0.5, `ConfidenceLerpSpeed` 1.5)로 드나든다. 차폐 샘플 3발 중 1발만 막히면
`VisibleFraction`이 0.33이 되고, 신뢰도가 **0.33초 만에** 0.5 아래로 떨어져 목록에서 빠진다.

연쇄:

1. 적이 나무 뒤로 반쯤 들어감 → 0.33초 뒤 `DetectedTargets`에서 탈락
2. 스티키 조건 깨짐 → `SelectNearestEnemyTarget()` 재실행 → 다른 적이 뽑힐 수 있음
3. 타겟이 바뀌면 `UpdateFireReadinessGauges`가 `LockOnGaugeValue`를 **즉시 0으로 리셋**
   (`CurrentAutoAimTarget != LastLockOnGaugeTarget`)
4. 게이지가 `LockOnGaugeChargeSeconds`(인스턴스 0.4초)를 못 채우고 1~3이 반복 → **영영 발사 안 함**

## 수정

```cpp
UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Fire Control|Auto-Aim", meta = (ClampMin = "0.0"))
float TargetRetentionGraceSeconds = 1.f;   // 0이면 이전 동작(즉시 전환)
```

```cpp
if (bTargetDetectedNow)      TimeSinceTargetLastDetected = 0.f;
else if (bTargetAlive)       TimeSinceTargetLastDetected += DeltaTime;

if (!bTargetAlive || TimeSinceTargetLastDetected > TargetRetentionGraceSeconds)
{
    Target = SelectNearestEnemyTarget();
    TimeSinceTargetLastDetected = 0.f;
}
CurrentAutoAimTarget = Target;
```

놓아주는 조건 두 가지뿐:

- 액터가 유효하지 않게 됨(죽음/파괴) → **유예 없이 즉시**
- `DetectedTargets`에서 **연속으로** 사라진 시간이 유예를 넘김

기본 1.0초는 `LockOnGaugeDischargeSeconds`와 같은 감각("게이지가 다 빠질 만큼 안 보였으면
놓아준다").

### 왜 "락온 게이지가 0이 되면"이 아닌가

사용자 최초 아이디어는 게이지 기준이었으나, 게이지는 `bAligned`(카메라
`AutoAimLockToleranceDegrees` + 총구 `AutoFireTurretAlignmentToleranceDeg` 둘 다 만족)일 때만
차오른다. **타겟을 새로 잡고 포탑이 슬루하는 동안은 정렬 전이라 게이지가 계속 0** — 정작
표적이 튀는 그 구간에 커밋이 전혀 없다. 그래서 정렬과 무관한 "탐지 유실 시간"으로 잡았고,
커밋 시점이 "게이지가 차기 시작한 때"가 아니라 **"표적을 고른 순간"** 으로 앞당겨짐.

`SelectNearestEnemyTarget`은 `DetectedTargets`만 훑으므로, 유예가 끝나 재선정할 때 방금 놓은
표적이 다시 뽑히는 일은 없다(그 시점엔 목록에 없으므로).

## 부수 효과 / 남은 이슈

- **유예 동안엔 안 보여도 계속 조준·발사함**(엄폐물 뒤로 숨은 지점을 계속 겨눔). 최대 1초라
  부자연스럽지 않다고 판단해 그대로 둠. "안 보이면 사격 중지"를 원하면 발사 게이팅에
  `bTargetDetectedNow`를 추가로 물리면 됨.
- **각속도는 별개 문제**(사용자가 따로 작업하기로 함). 표적을 고정해도 포탑이 못 따라가면
  `bAligned`가 안 되어 게이지가 안 참. 적 3m/s 측면 이동 기준 필요 슬루 속도:

  | 거리 | 필요 슬루 |
  |---|---|
  | 100m | 1.7°/s |
  | 50m | 3.4°/s |
  | 20m | 8.6°/s |
  | **10m** | **17°/s** |

  UGV 레벨 인스턴스의 `MaxAutoAimSlewRateDegPerSec`는 2026-09-01 기준 **15**(C++ 기본 45에서
  낮춤)라, 근거리 이동 표적은 구조적으로 조준이 안 됨.
- 전방 45° 우선순위(`bPrioritizeForwardArcTargets`)는 여전히 **재선정 시점에만** 적용됨 —
  유예가 길어진 만큼 전환 빈도도 줄어듦.

## 적용

C++ 변경이라 **리빌드 필요**. 새로 추가한 프로퍼티라 레벨 인스턴스에도 자동 반영됨.
