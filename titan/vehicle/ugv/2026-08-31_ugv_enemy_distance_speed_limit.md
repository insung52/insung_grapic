# UGV 적 거리 기반 속도 제한 (15/7/3 km/h 선형 보간)

2026-08-31 / 코드+스텝행 완료·PIE 검증 대기 / 자율주행 속도 거버너에 "가장 가까운 적까지의 거리"를
세 번째 입력으로 추가 — 기존 커브 감속/호위 제한과 같은 자리에서 최솟값으로 합쳐짐.

선행 문서: `2026-08-31_ugv-speed-pi-controller.md`(목표속도 추종을 PI로 재작성 — **이번 작업이
얹히는 자리**), `2026-08-22_ugv_corner_braking_dev_guide.md`, `2026-08-26_ugv_obstacle_avoidance.md`.
짝이 되는 적군 쪽 작업: `../../ai_combat/2026-08-31_enemy_squad_reorg.md`.

---

## 1. 요구사항 (memo.md "시나리오 관련 변경")

> ugv 가 1차 전투지에서 1분대 전멸 시킨 후, 남은 도망가는 적군들과 전투 중 특정 거리 이상
> 멀어져서 2차 전투지로 이동 시작할때, 해당 ugv 의 제한속도를 적과의 거리 기반 유동적으로
> 설정하게 하기.
> - 전투 거리 보다 멀면 15km/h, 전투거리일때는 7km/h, 전투거리보다 가까우면 최대 3km/h —
>   선형적으로 자율주행 최대 목표 속도를 제한한다.
> - (명령 출처는 UGV↔통제기 프로토콜이 확정되기 전이므로) 일단 현재 시나리오 시스템 기반으로.

**이번 라운드는 1단계(시나리오 시스템 기반)까지다.** 2단계(임의의 테스트용 프로토콜로 목적지
좌표+최대속도 전송)는 미착수 — 6절 참고. `protocol/`의 실제 LIG ICD는 건드리지 않았다.

## 2. 어디에 얹었나 — 기존 거버너 구조 확인

`AUGVAIController::UpdateChaosPursuit`의 속도 거버너는 이미 **입력 2개가 목표 속도를 내고 낮은
쪽이 이기는** 구조였다(`2026-08-22` 커브 감속 도입 때 통합됨):

```
TargetSpeedKmh = float::Max
  ├ bEnableCornerBraking      → 커브 제동 곡선(ComputeCornerTargetSpeedKmh)
  └ bEscortSpeedLimitActive   → EscortMaxSpeedKmh (아군 동반 구간)
그 다음 PI 제어기가 TargetSpeedKmh를 절대 스로틀로 추종
```

그래서 **세 번째 입력을 같은 자리에 하나 더 끼우는 것**이 정답이었다. 스로틀에 배율을 곱하는
방식은 쓰지 않았다 — `2026-08-31_ugv-speed-pi-controller.md` 3절에서 확인된 대로 그러면 PI
적분과 싸우기 때문(스로틀이 눌린 동안 적분이 쌓이다가 제한이 풀리는 순간 터진다). **목표 속도를
낮추면 오차 자체가 줄어 적분이 애초에 안 쌓인다.**

기존 커브 감속과의 관계: **최솟값이므로 안 부딪힌다.** 커브가 이미 더 낮게 잡고 있으면 그쪽이
유지되고, 적이 가까워서 3km/h면 커브 목표가 40이든 상관없이 3이 이긴다.

## 3. 구현

### 3.1 신규 프로퍼티 (`AUGVAIController`, 카테고리 `UGV AI|Enemy Distance Speed Limit`)

| 이름 | 기본값 | 역할 |
|---|---|---|
| `bEnemyDistanceSpeedLimitActive` | false | **on/off 스위치.** 시나리오 스텝/BP/콘솔이 켠다 |
| `EnemyNearDistanceCm` | 2000 | 이 거리 이하로 붙으면 더는 안 느려짐(곡선 가까운 쪽 끝) |
| `EnemyEngagementDistanceCm` | 6000 | **"교전 거리"** — 여기서 정확히 `EngageSpeed`가 됨(곡선 가운데) |
| `EnemyFarDistanceCm` | 12000 | 이 거리 이상 벌어지면 더는 안 빨라짐(곡선 먼 쪽 끝) |
| `EnemyDistanceNearSpeedKmh` | **3** | 요구사항 "가까우면 최대 3km/h" |
| `EnemyDistanceEngageSpeedKmh` | **7** | 요구사항 "교전거리일 때 7km/h" |
| `EnemyDistanceFarSpeedKmh` | **15** | 요구사항 "멀면 15km/h" |
| `bReleaseEnemyDistanceLimitWhenNoEnemy` | true | 적이 하나도 안 남으면 제한을 놓아줌 |

거리 단위는 **cm, 씬 좌표 기준** — 시나리오 스텝의 `TriggerDistanceThreshold`와 같은 단위라
임계값을 그대로 맞춰 쓰면 된다. 속도는 다른 속도 프로퍼티와 동일하게 실제 세계 km/h
(`GeoCoordinateUtils::GetDistanceScaleFactor()` 보정 적용 — New_kadex_0811에서는 배율이
~1.0006이라 사실상 항등, `guide/real2world.md` 참고).

### 3.2 곡선 — 왜 한 직선이 아니라 꺾은선인가

세 지점을 **구간별 기울기가 다른 두 직선**으로 잇는다:

```
 15 ┤                          ┌────────
    │                     ┌────┘
  7 ┤          ┌──────────┘            ← 교전 거리에서 정확히 7
    │     ┌────┘
  3 ┤─────┘
    └──┬──────────┬───────────┬────────► 최근접 적까지 거리
     2000       6000        12000  (cm)
```

Near~Far를 **한 직선으로 이으면 교전 거리에서 9km/h가 나와** 요구(7km/h)와 어긋난다. 그래서
Near→Engage, Engage→Far 두 구간으로 나눴다. 구간 밖은 양 끝 값으로 클램프.
임계 거리가 뒤집혀 입력돼도(Near > Engage 등) 내부에서 `FMath::Max`로 방어한다.

### 3.3 거리 측정

`AUGVAIController::GetNearestEnemyDistanceCm()` — `UDetectableTargetSubsystem`에 등록된
`Faction==Enemy`만 순회해서 최근접 거리를 구한다. 사망 시 `SetIncapacitated(true)`가 등록을
해제하므로 **별도 생존 판정이 필요 없다**(`UScenarioStateSubsystem`의 거리 트리거가 쓰는 것과
같은 인프라·같은 형태).

**컨트롤러가 직접 매 틱 잰다** — 시나리오 서브시스템이 재서 넘겨주는 방식도 가능했지만, 스텝
평가 주기가 0.2초라 그 해상도로는 감속이 계단처럼 끊긴다. 시나리오는 "언제 켜는가"만 쥐고,
"얼마나"는 컨트롤러가 매 틱 계산한다 — `bEscortSpeedLimitActive`와 완전히 같은 역할 분담이다.

### 3.4 적이 하나도 없을 때

`bReleaseEnemyDistanceLimitWhenNoEnemy = true`(기본)면 제한을 놓아준다. 3차 전투지 이후 적이
전멸했는데 UGV가 3km/h로 기어가는 그림이 나오지 않도록 하는 장치 — **제한을 켜둔 채로 시나리오가
끝나도 안전**하다. false로 두면 가장 느린 값(3km/h)으로 잠근다.

여기서 **기존 코드의 잠재 버그 하나를 같이 막았다**: 거버너 블록에 진입했는데 유효한 목표 속도를
낸 입력이 하나도 없으면(= 이 제한만 켜져 있고 적이 없는 경우) `TargetSpeedKmh`가 `float::Max`로
남아 PI가 매 틱 스로틀을 가득 밀고 **조향컷이 통째로 무시된다**(거버너가 꺼져 있을 때보다 오히려
위험). `bHasSpeedTarget` 가드를 넣어 그 경우 거버너가 꺼진 것과 동일하게 취급한다(조향컷만 반영된
스로틀 유지 + 적분 비움). 기존 두 입력만 있을 때는 도달 불가능한 상태였으므로 회귀 없음.

### 3.5 켜고 끄는 경로

| 경로 | 용도 |
|---|---|
| `EScenarioEffectType::EnableUGVEnemyDistanceSpeedLimit` / `Disable...` | **정식 흐름** — 스텝 테이블 |
| `UScenarioStateSubsystem::SetUGVEnemyDistanceSpeedLimit(bool)` | BP/코드 진입점 (위 이펙트의 구현부) |
| 콘솔 `SetUGVEnemyDistanceSpeedLimit 1` / `0` | **테이블 저작 전에 PIE에서 바로 켜보고 곡선 튜닝**하는 용도. 기존 시나리오 Exec 커맨드들과 동일하게 서버 권위 라우팅(`Server_*` RPC) |
| `AUGVAIController::SetEnemyDistanceSpeedLimitActive(bool)` | 최종 진입점. 끌 때 텔레메트리도 초기화 |

`MoveUGVToZone1/2/3Destination` 이펙트는 **호위 제한(`bEscortSpeedLimitActive`)만 끄고 이쪽은
안 건드린다** — 목적지를 바꿔도 이 제한은 유지된다(끄려면 Disable 이펙트를 쓸 것).

### 3.6 진단

`FUGVPursuitTelemetry`에 3필드 추가 — `bEnemyDistanceLimited`(지금 이 제한이 목표를 쥐고
있는가), `NearestEnemyDistanceCm`(적 없으면 -1), `EnemyDistanceTargetKmh`.
`UUGVDriveTuningWidget`이 읽을 수 있고, `bLogPursuitDiagnostics` 로그에도 실렸다:

```
[UGVPursuit] v=6.8km/h cornerTarget=39.2 spdTgt=6.9 spdI=0.31 pitch=1.2 | enemyDist=5800cm enemyTgt=6.9* | angErr=1deg ... throttle=0.44
```
`enemyTgt` 뒤의 `*`가 "지금 이 제한이 실제로 이기고 있다"는 표시다.

## 4. 스텝 테이블 저작 — **완료**

`DT_ScenarioSteps_ThreeStage`에 행 하나 추가하고 저장했다(기존 행은 하나도 안 건드림):

| RowName | Prereq | Trigger | 값 | Effect |
|---|---|---|---|---|
| `UGVSpeedLimitOn` | `UGVMoveZone2` | `TimerOnly` | 0s | **`EnableUGVEnemyDistanceSpeedLimit`** |

`UGVMoveZone2`(= `LeaderDistanceFromEnemyAtLeast` 5500cm 트리거로 발동, UGV가 2차 목적지로
출발하는 행)를 Prerequisite로 잡으면 요구사항의 "2차 전투지로 이동을 시작하는 시점부터"와
정확히 일치한다.

> 이 테이블은 `New_kadex_0811`과 `kadex_test`가 공유하지만, 추가된 행은 기존 흐름에 영향을 주지
> 않는다(Prereq 체인 끝에 매달린 잎 노드). 메인 전투 레벨은 `New_kadex_0811`이고 적 15기 배치와
> 분대 저작이 끝났으므로(짝 문서 4절) 이제 `UGVMoveZone2` → `UGVSpeedLimitOn` 체인이 실제로
> 흐른다.

끄고 싶은 지점이 생기면 같은 방식으로 `DisableUGVEnemyDistanceSpeedLimit` 행을 추가한다
(기본값 `bReleaseEnemyDistanceLimitWhenNoEnemy=true` 덕에 **안 꺼도 안전**하다).

## 5. 검증 방법 / 아직 안 된 것

- [x] **빌드** — 사용자가 직접 완료(2026-08-31).
- [ ] PIE에서 UGV `bLogPursuitDiagnostics`를 켜고 콘솔 `SetUGVEnemyDistanceSpeedLimit 1` →
      적에게 접근/이탈시키며 `enemyDist`와 `spdTgt`가 15→7→3으로 따라오는지. 스텝 테이블 저작
      전에 **곡선만 단독으로 검증**할 수 있는 가장 빠른 경로다.
- [ ] 임계 거리 3개(2000/6000/12000cm)를 New_kadex_0811의 실제 교전 거리에 맞춰 재튜닝.
      지금 값은 요구사항의 형태만 맞춘 초기값이고, 실제 "교전 거리"는 적 감지 스피어
      (`AllyDetectRange`, kadex_test 기준 20000cm)와 RCWS 유효사거리
      (`MaxEffectiveRangeMeters` 2000m)를 보고 정해야 한다.
- [ ] 3km/h가 이 차의 구동계에서 **실제로 유지되는지.** `2026-08-31_ugv-speed-pi-controller.md`
      4절에서 확인된 대로 지금 병목은 제어기가 아니라 구동력이고, 그건 "목표에 못 미치는" 방향의
      문제라 저속 목표에는 오히려 유리하다. 다만 **1~2단에서 아이들링 토크만으로 3km/h를 넘겨
      브레이크가 계속 걸리는** 반대 증상이 나올 수 있으니 실측 필요.
- [ ] 커브 감속과 동시에 걸리는 구간에서 목표가 튀지 않는지(최솟값이라 이론상 문제 없지만
      `CornerTargetReleaseRateKmhPerSec` 램프와 겹칠 때의 체감 확인).

## 6. 2단계(테스트용 프로토콜) — 미착수

사용자 요청대로 **1단계 성공 확인 후 진행 여부를 상의**하기로 한 부분. 지금 구조는 그쪽으로
넘어가기 좋게 돼 있다 — 프로토콜 수신부가
`AUGVAIController::SetEnemyDistanceSpeedLimitActive()` + `MoveToDestination()`을 부르기만 하면
같은 동작이 재현되고, 시나리오 시스템 경로와 완전히 독립이다.

착수하게 되면 지켜야 할 것(사용자 명시):
- `protocol/`의 실제 LIG ICD 문서/코드는 **건드리지 않는다.**
- 기존 `HQ_MissionMoveToEngage`류 확장이 아니라 **새 이름의 완전히 별개 임시 경로**로.
- "우리가 임의로 만든 테스트/프로토타입"임을 문서와 코드 주석에 명시.

## 7. 코드 변경 목록

```
수정 (p4 edit 완료)
  Vehicles/UGVAIController.h    bEnemyDistanceSpeedLimitActive + 임계/속도 프로퍼티 6개 +
                                bReleaseEnemyDistanceLimitWhenNoEnemy,
                                SetEnemyDistanceSpeedLimitActive(),
                                GetNearestEnemyDistanceCm(), ComputeEnemyDistanceTargetSpeedKmh(),
                                FUGVPursuitTelemetry 3필드
  Vehicles/UGVAIController.cpp  거버너 3번째 입력 배선 + bHasSpeedTarget 가드 + 진단 로그 확장
  UI/ScenarioStepTypes.h        EScenarioEffectType::Enable/DisableUGVEnemyDistanceSpeedLimit
  UI/ScenarioStateSubsystem.h/.cpp  SetUGVEnemyDistanceSpeedLimit() + 이펙트 케이스
  titan_examplePlayerController.h/.cpp  Exec `SetUGVEnemyDistanceSpeedLimit` (+ Server_ RPC)
```
