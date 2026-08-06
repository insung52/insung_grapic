# 아군(BP_Ally) 부대 이동 + UGV 동반/회피/산개 시스템 구현

> `titan_example` 프로젝트. 시나리오.md #4-4~#4-6 — "UGV 자율주행에 아군 30명이 대형을 갖춰
> 동반 이동하고, 목적지 도착 후 각자 매복 위치로 산개, RCWS 적 포착 시 엄폐+교전"을 구현.
> NavMesh 경로탐색, RVO 회피, 물리적 충돌 완화까지 여러 차례 갈아엎으며 반복 개선.

---

## 전체 흐름

```
BeginAllyFormUpAndAdvance(목적지)
  └─ 아군 전원 각자 UGV 기준 대형 위치로 집결(FormingUp) — 순차 스태거 출발
       └─ 전원 도착 → FormUpAdvanceDelaySeconds(2초) 후 UGV 자율주행 시작 + 아군 Following 전환
            └─ UGV 목적지 도착(정지) 감지
                 └─ 분대장 "정지" 수신호 → HaltToApproachDelaySeconds(2초) 후
                      └─ 분대장 "산개" 수신호 → 전원 Approach 브로드캐스트
                           (동시에 UGV도 SetUGVStandbyDestination으로 지정해둔 대기 위치로 재출발)
                                └─ UGV RCWS 적 포착 → 전원 Ambush(엄폐+사격) 브로드캐스트
```

각 단계 전환은 `UScenarioStateSubsystem`이 오케스트레이션하고(등록된 아군 레지스트리에 브로드캐스트),
실제 이동/전투 로직은 각 `UAllyFormationComponent`(BP_Ally에 부착)가 담당.

---

## 상태별 이동 로직

| 상태 | 목표 | 이동 방식 |
|---|---|---|
| **FormingUp** | UGV(정지) 기준 대형 오프셋 위치 | NavMesh 경로 1회 계산 + 순차 웨이포인트 추종 |
| **Following** | UGV 실제 주행 경로 위 arc-length 기준 위치 | 매 틱 재계산(UGV가 계속 움직이므로), NavMesh 사용 안 함 |
| **Approaching** | 각자의 `AmbushMarker` | NavMesh 경로 1회 계산 + 순차 웨이포인트 추종 |
| **Ambush(따라잡기)** | `AmbushMarker` | 위와 동일한 경로 추종 로직 공유 |

FormingUp/Approaching/Ambush 세 상태가 전부 같은 두 함수(`BeginNavPathMovement` /
`TickNavPathMovement`)를 공유 — 처음엔 FormingUp 전용이었다가 반복되는 요구사항에 맞춰 일반화함.

**정체 감지 + 자동 재탐색**: 1초마다 실제 이동 거리를 체크해서, 20cm도 못 움직였는데 아직 미도착이면
그 시점 위치 기준으로 NavMesh 경로를 다시 계산(정체가 풀릴 때까지 매초 반복). 원래 FormingUp에서만
쓰던 디버깅 로그였는데 실제 대응 로직으로 발전시켜 세 상태 모두에 적용.

**Following의 대형 위치 계산**(`ComputeFormationPointOnPath`): UGV의 실제 주행 경로(폴리라인) 위에서
UGV 자신의 호 길이(arc-length) 기준 전후 거리 + 좌우 오프셋으로 계산. 예전엔 "UGV 로컬 스페이스
오프셋"이었는데, 그러면 UGV가 회전할 때 대형 끝쪽일수록 훨씬 큰 호를 그리며 증폭되는 문제(기차 칸이
선로를 안 따르고 기관차에 고정 각도로 매달려 도는 것과 같은 문제)가 있어서 경로-기반으로 교체.

---

## 회피 시스템 — 반복 개선 끝에 정착한 최종 구조

### 아군 ↔ 아군

- **최종**: 언리얼 내장 RVO(`bUseRVOAvoidance`)
- **폐기된 접근**: 손으로 짠 반응형 회피("가장 가까운 한 명만 보고 고정 접선으로 비켜가기") —
  여러 명이 좁은 곳에서 동시에 서로 피하려 들면 서로 얽혀 도는("개미지옥") 문제가 있었음. 검증된
  다자간 회피 알고리즘(RVO)으로 대체.
- **도착 후 정지 처리**: 도착해서 멈춘 아군은 `AvoidanceWeight`를 0.5(기본, "서로 절반씩 양보"
  전제) → 1.0("나는 코스를 안 바꾼다")으로 올림. 기본값 그대로면 다가오는 아군이 "쟤도 절반은
  비켜줄 것"이라 오판하고 절반만 회피 경로를 잡아 좁은 곳에서 못 지나가는 문제가 있었음(엔진 소스
  `AvoidanceManager.cpp`의 블렌드 공식으로 원인 확인).
- **Following 중엔 RVO를 꺼둠**: 대형 위치가 이미 매 틱 충돌 없이 계산되는 결정론적 값이라 상호
  협상이 불필요 — 오히려 RVO가 "이웃과 가깝다"고 판단해 불필요하게 흔들면 대형이 흐트러짐.
- **최종 안전망 — 물리적 밀어내기**: RVO도 기하학적으로 못 푸는 상황(정지한 두 명 사이 틈이 캡슐
  지름보다 좁음, 여러 명이 뒤엉켜 로컬 미니멈에 빠짐)이 실사용에서 발견됨. 아군 캡슐의 Pawn 채널
  콜리전을 Block → Overlap으로 낮추고(지형/장애물은 그대로 Block), 매 틱 `ResolveAllyOverlapPush`가
  겹친 만큼 방향을 누적해 부드럽게 밀어냄.
- **드리프트 복구**: Approach/Ambush 도착 후 밀려서 `ArrivalToleranceCm` 밖으로 벗어난 채
  `DriftGraceSeconds`(3초) 이상 지속되면 원래 위치로 재이동(밀리자마자 즉시 반응하면 밀어내는
  힘과 계속 힘겨루기하듯 보여서 유예를 둠).

### 아군 ↔ UGV

**경로 계산 시점(path-time) + 실이동 시점(move-time), 2단 방어 구조**로 최종 정착:

1. **경로 계산 시점** — `UNavArea_UGVBody`(신규 NavArea, 기본 비용 1.0=중립)를
   `UNavModifierComponent`로 UGV 발밑에 항상 붙여둠. 아군 전용 쿼리 필터(`UNavQueryFilter_Infantry`)
   에서만 이 영역에 매우 높은 비용(1,000,000)을 오버라이드 — 아군 경로탐색은 "경로를 짤 때부터"
   UGV를 피해가고, UGV 자기 자신의 경로탐색(이 필터를 안 씀)은 전혀 영향받지 않음. 그래서 예전처럼
   "UGV 출발 직전에 급히 장애물을 떼어내야 하는" 제약이 없어져 항상 붙여둘 수 있게 됨.
2. **실이동 시점** — `UUGVAvoidanceProxyComponent`(신규, `UMovementComponent`+
   `IRVOAvoidanceInterface` 구현)를 UGV 폰에 런타임 부착. 실제로 조향은 안 하고, 매 틱 UGV의
   진짜 위치/속도(Chaos 물리 바디에서 직접 읽음)/크기를 언리얼 RVO 매니저에 발행만 함 — 아군들의
   기존 RVO 계산이 UGV도 자동으로 "속도를 가진 장애물"로 인식해서 현재 위치뿐 아니라 예측 궤적까지
   반영해 피함.

**폐기된 접근들**:
- UGV NavMesh 장애물을 `UNavArea_Null`(전원 통행 불가)로 표시 — UGV 자기 자신도 막혀서 출발 직전에
  반드시 떼어내야 했음. 필터별 비용 오버라이드 방식으로 교체하며 이 제약이 사라짐.
- 손으로 짠 반응형 UGV 회피(`ApplyUGVAvoidance`, "항상 오른쪽 접선으로 비켜가기") — 정지한 UGV
  기준으로 설계된 규칙이라, UGV가 움직이면(Following, 또는 Approach 중 대기 위치 재출발) 목표가
  계속 움직이면서 궤도를 도는 버그가 반복 재현됨. RVO 프록시로 완전히 대체, 함수 자체 삭제.
- (오진 기록) 한때 "RVO가 `UCrowdManager` 초기화 실패 때문에 고장났다"고 진단하고 RVO를 꺼놨던
  적이 있었는데, 엔진 소스 확인 결과 `bUseRVOAvoidance`는 `UCrowdManager`를 전혀 안 쓰고 완전히
  별개인 `UAvoidanceManager`를 씀 — 오진이었음, 재활성화.

### UGV 위치 계산 관련 확인

아군들이 UGV를 피할 때 "회피 중심이 이상한 곳에 있다"는 리포트가 있었음 — `GetActorBounds()`의
`bOnlyCollidingComponents` 인자를 `false`(콜리전 여부 상관없이 모든 프리미티브 컴포넌트 포함)로
쓰고 있어서, 콜리전 없는 다른 컴포넌트(탐지용 스피어 등)가 바운딩 박스 중심/크기를 오염시킨 게
원인이었음(엔진 소스로 확인 — `GetComponentsBoundingBox`는 `UPrimitiveComponent`만 순회하므로
카메라류는 애초에 무관함을 별도로 검증). `true`로 바꿔서 실제 콜리전 있는 형상(차체+터렛)만
정확히 반영되도록 수정.

---

## UGV 대기 위치 (신규 기능)

Approach 단계에서 UGV가 원래 목적지에 계속 서있지 않고 별도 위치로 재출발할 수 있게
`SetUGVStandbyDestination(FVector)` 콘솔 명령 추가 — 저장만 해두고, `BeginAllyApproach` 시점에
자동으로 그 위치로 `MoveToDestination` 호출. 계획상 추후 `UDataTable` 기반으로 정식화 예정, 현재는
콘솔로 간단히 지정하는 임시 구현.

---

## NavMesh 경사 조정

바위 등 급경사 지형에도 NavMesh가 듬성듬성 붙어서 병사들이 올라가려 드는 문제 확인 —
`RecastNavMesh`의 `AgentMaxSlope`를 엔진 기본값 44도에서 30도로 낮춤(`DefaultEngine.ini`).
※ 이미 레벨에 배치된 NavMesh 액터가 이 값을 즉시 반영하지 않으면 액터를 지우고 재생성하거나
Details 패널에서 직접 맞춰야 할 수 있음.

---

## 남은 이슈 / 개선 여지

- **Approach 중 UGV 근접 시각적 클리핑 가능성**: UGV가 대기 위치로 이동하는 것과 아군들이 각자
  매복 위치로 이동하는 것이 동시에 일어나면서, 아군이 UGV에 바짝 붙어 스쳐 지나가는 경우가 관찰됨.
  실제 물리적으로 밀리는 건 불가능(`bEnablePhysicsInteraction=false` + 콜리전 유지, 이번 변경
  범위 밖)하지만 시각적으로 아슬아슬함. 개선 후보(우선순위순): ① `UUGVAvoidanceProxyComponent`의
  `RadiusPaddingCm` 상향, ② Approach 시작을 UGV NavMesh 갱신 시간만큼 살짝 지연(FormingUp의
  `NavObstacleSettleSeconds`와 같은 패턴), ③ UGV 이동 중엔 `AvoidanceConsiderationRadius`를
  일시적으로 확대(상태 인식 로직 필요, 가장 복잡).
- FormUp 단계에서 일부 개체의 NavMesh 경로탐색이 실패해 직선 이동으로 폴백한 사례가 과거 1회
  있었음(원인 미상, 재현 여부 미확인).
- NavAgent 높이 설정(144cm)과 아군 캡슐 실제 전체 높이(180cm)가 살짝 어긋나 있음 — 당장 문제를
  일으키진 않았지만 점검 필요.

---

## 최종 코드 상태

| 파일 | 변경 내용 |
|---|---|
| `Soldiers/AllyFormationComponent.h/.cpp` | 상태머신(FormingUp/Following/Approaching/Ambush), NavMesh 경로추종 공유 로직(`BeginNavPathMovement`/`TickNavPathMovement`), 정체 감지+재탐색, RVO on/off 상태별 제어, 도착 시 `AvoidanceWeight` 상향, 아군 상호 밀어내기(`ResolveAllyOverlapPush`) + 드리프트 복구, 분대장 수신호(정지/산개/엄폐) 재생 |
| `Soldiers/NavQueryFilter_Infantry.h/.cpp` | 보병 전용 NavMesh 쿼리 필터 — 도로 가중치 중립화 + `NavArea_UGVBody` 고비용 오버라이드 |
| `Vehicles/UGVAvoidanceProxyComponent.h/.cpp` (신규) | UGV를 RVO 시스템에 참가시키는 프록시 컴포넌트 — 위치/속도/크기 매 틱 발행 |
| `Vehicles/NavArea_UGVBody.h/.cpp` (신규) | UGV 발밑 NavMesh 영역(중립 비용, 보병 필터에서만 고비용) |
| `Vehicles/UGVAIController.h/.cpp` | `IsMoving()` 공개 접근자, `OnPossess`에서 회피 프록시 컴포넌트 자동 부착 |
| `UI/ScenarioStateSubsystem.h/.cpp` | 시나리오 단계 오케스트레이션 전체 — FormUp 스태거 출발, UGV NavMesh 장애물 등록(상시 유지로 단순화), UGV 도착 폴링(`PollUGVArrival`) + 정지/산개 수신호 시퀀스, UGV 대기 위치 저장/재출발 |
| `titan_examplePlayerController.h/.cpp` | 콘솔 커맨드: `BeginAllyFormUpAndAdvance`, `BeginAllyFollowing`, `BeginAllyApproach`, `BeginAllyAmbush`, `SetUGVStandbyDestination` |
| `Config/DefaultEngine.ini` | `RecastNavMesh.AgentMaxSlope` 44 → 30 |
