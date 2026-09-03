# 자체방호 축 시나리오 이중 평가 버그 (3차 도주 미발동)

2026-09-02 / 완료 / 레벨 트래블 직후 스텝 평가 루프가 두 벌로 돌아 사망자 기준선이 재설정되던 버그 수정.

## 증상

`kadex_test`에서 **UGV 축(PIE 기본값)으로는 누적 7명 사망 시 적군이 3차 전투지로 도주하는데,
자체방호 축에서는 도주가 안 걸린다.** 다른 스텝은 정상.

## 원인

`UScenarioStateSubsystem`의 스텝 평가 루프가 **두 벌로 돌고, 두 번째 루프가 사망자 기준선을
다시 잡는다.**

로그(자체방호 실행 구간):

```
01:02:55.118  BeginTearingDown (open ?Axis=SelfDefense 트래블)
01:02:55.649  데모 실행 모드 — 자동 시작 예약(3초 후)
01:02:58.219  EnemyApproach 발동     ← 루프 #1 (옛 월드에서 살아남음)
01:03:00.804  UAVMission 발동
01:03:00.804  데모 자동 시작 — BeginEnemyContactScenario() 호출
01:03:00.807  스텝 평가 시작          ← 루프 #2 시작
01:03:01.889  EnemyApproach 재발동
01:03:03.876  UAVMission 재발동
```

이미 발동한 스텝이 재발동하려면 `FiredScenarioSteps`가 비워져야 하고, 그건
`BeginScenarioSteps` 한 곳에서만 일어난다. 그리고 그 20줄 아래:

```cpp
FiredScenarioSteps.Reset();                                   // :831
ScenarioEnemyCountBaseline = CountAliveEnemies(GetWorld());   // :852  ← 범인
```

기준선이 **"지금 살아있는 적 수"로 다시 잡힌다.** 위 로그는 재시작이 첫 사망 전에 들어와서
우연히 7명을 채웠지만, 이미 4명 죽은 뒤에 들어오면 기준선이 15가 아니라 11로 잡혀
`EnemyCasualtyCountAtLeast = 7`이 영원히 안 걸린다.

### 왜 자체방호 축에서만인가

UGV 축은 PIE 기본값이라 트래블 없이 한 번 깨끗하게 시작한다. 자체방호는
`open ...?Axis=SelfDefense` **맵 트래블이 유일한 진입 경로**고, 그 트래블만 재진입 창을
만든다. 축 자체와는 무관하고 **트래블 여부**가 변수다.

### 왜 기존 가드가 못 막았나

```cpp
bScenarioStepsRunning = false;
ScenarioStepTickTimerHandle.Invalidate();   // 핸들만 버림 — 타이머는 계속 돎
```

`FTimerHandle::Invalidate()`는 타이머를 취소하지 않는다. 옛 월드 티어다운과 새 월드 기동이
겹치는 구간에 추적 불가능한 루프가 남고, 뒤이은 `BeginScenarioSteps`는
`bScenarioStepsRunning == false`만 보고 두 번째 루프를 띄운다. 01:02:58 EnemyApproach 앞에
`스텝 평가 시작` 로그가 **없는** 것이 그 증거다.

## 수정 (`UI/ScenarioStateSubsystem.cpp`)

1. **`ResetForNewWorldIfNeeded`** — `ScenarioStateWorld.IsValid()`를
   `if (UWorld* OldWorld = ScenarioStateWorld.Get())`로 바꾸고, 옛 월드의 `FTimerManager`에서
   `ScenarioStepTickTimerHandle` / `DemoAutoFireTimerHandle` / `DemoAutoStartTimerHandle`을
   **실제로 `ClearTimer`** 한 뒤 넘어간다. 근본 원인 차단.
2. **`BeginScenarioSteps` 재진입 가드** — 플래그뿐 아니라
   `GetTimerManager().IsTimerActive(ScenarioStepTickTimerHandle)`도 본다. 참이면
   `bScenarioStepsRunning`을 되살리고 조용히 리턴.

⚠ 2번은 예전에 **단독으로** 쓰다가 stale 핸들 때문에 시나리오가 아예 시작 안 되는 역버그를
만든 적이 있다(2026-09-01). 1번이 핸들을 `ClearTimer`로 확실히 무효화하므로 이제 짝으로만
안전하다 — **2번만 떼서 쓰지 말 것.**

## 곁다리: MCP로 만든 스플라인 길이가 1.0m

같은 날 `kadex_test` 드론 경로에서 발견. 자율비행 시작 로그가 `길이 1.0m`로 찍혔다.

MCP `set_properties`로 `SplineComponent`의 포인트를 써넣으면 좌표는 들어가지만
`UpdateSpline()`이 안 불려서 탄젠트가 기본값 `(100,0,0)`이고 arc-length 테이블이 기본
2포인트 스플라인 것 그대로 남는다. 같은 컴포넌트에 `bClosedLoop`를 `True`→`False`로 토글하면
`PostEditChangeProperty`가 `UpdateSpline()`을 태워서 해결된다(`uavpath` 1.0m → 95.7m,
`uavpath2` → 191.2m). 레벨을 저장하고 **다시 열면** `PostLoad()`가 알아서 고치므로, 만든 그
세션에서 바로 PIE를 켤 때만 나오는 증상이다.

> 참고: 같은 로그의 `속도상한 10.7km/h`는 버그가 아니다. `TakeoffSpeedLimitCmPerSec =
> DistanceToStart / TakeoffDurationSeconds(5초)`로 계산되는 **이륙 전용** 상한이고, 축소판이라
> 첫 웨이포인트가 14.9m밖에 안 떨어져 있어서 낮게 나온다. 순항 속도(`CruiseSpeedKmh`)는 70 그대로.

## 관련 문서

- `scenario_authoring_guide.md` §6 트러블슈팅에 증상 행 추가
- `2026-09-01_scenario_run_modes_demo_fullsystem.md` — 데모/풀시스템 실행 모드
