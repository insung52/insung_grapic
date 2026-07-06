# UGV 수동/자동 주행 개발 문서 (2026-07-06)

`titan_example` 프로젝트에 추가한 UGV(무인 지상 탱크) 주행 시스템 — WASD 수동 조종과
NavMesh 기반 자동 경로 주행을 같은 물리 모델로 통합 구현. `path.md`의 1차 목표
("수동 주행 + 목적지 입력 시 자동 주행")를 임시 탱크 메시(`SM_UGV_Tank_Temp`)로
구현/검증한 결과.

## 1. 파일 구조

```
titan_example/Source/titan_example/Vehicles/
  UGVPawn.h/.cpp              AUGVPawn — 폰 본체, 컴포넌트 구성, 입력 바인딩, possess 기반 모드 전환
  UGVMovementComponent.h/.cpp UUGVMovementComponent — 속력+heading 기반 탱크 주행 물리
  UGVAIController.h/.cpp      AUGVAIController — MoveToLocation + 경로 포인트 JSON 추출
  UGVPathCorridor.h/.cpp      AUGVPathCorridor — 오프 경로 감속용 스플라인 액터 (미검증, 우선순위 낮음)

Plugins/QuadCamModule/Source/QuadCamModule/
  Public/QuadCamComponent.h, Private/QuadCamComponent.cpp
                              bAlwaysVisible 옵션 추가 (듀얼 모니터 대시보드 대비, 기본 false)

/Game/Vehicles/UGV/
  SM_UGV_Tank_Temp            임시 탱크 스태틱 메시 (Sketchfab류 무료 에셋, 760 tri)
  BP_UGV                      AUGVPawn 파생 블루프린트

/Game/Input/Actions/
  IA_Brake                    신규 — 스페이스바 브레이크
```

`titan_example.Build.cs`에 `Json`, `NavigationSystem` 모듈 의존성 추가.
`titan_examplePlayerController`는 **변경 없음** — 기존 `NextVehicle()` Exec 함수를 차량
선택 메커니즘으로 그대로 재사용 (아래 3번 참고).

## 2. 주행 물리 — 속력 + heading 모델

`UUGVMovementComponent`(`UFloatingPawnMovement` 상속)는 월드 스페이스 velocity를
그대로 적용하는 대신, **탱크 스타일로 직접 설계한 모델**을 씀:

- `CurrentSpeed`(스칼라, 전진+/후진-) + `CurrentAngularSpeed`(스칼라, 초당 회전각) 두
  값만 상태로 저장. "방향"은 별도 변수가 아니라 컴포넌트의 실제 Transform Rotation이 곧
  그 역할을 함.
- 매 틱: 목표 속력/각속도 계산 → `Acceleration`/`Deceleration`/`TurnAccelerationDegPerSec2`로
  서서히 근사(관성) → 그 순간의 heading으로 `CurrentSpeed × DeltaTime`만큼 스윕 이동.
  **속도 벡터를 누적하는 게 아니라 매 틱 heading 기준으로 재계산**하므로, 감속 중
  회전해도 옛 방향으로 미끄러지는 드리프트가 없음 (실제 궤도 차량처럼 제자리 회전 가능,
  회전 반경은 속도와 무관).
- **수동/자동 완전히 같은 물리 공유**: 사람이든 AI든 결국 `ThrottleInput`/`SteerInput`
  (둘 다 -1..1) 두 값만 세팅하고, `TickComponent`는 이 값만 보고 동작 — 소스가 다를
  뿐 물리 로직 분기 없음.
  - 수동: `SetManualControl(Forward, Turn)` — `IA_Move` 값 그대로 직결
  - 자동: `RequestDirectMove(MoveVelocity, ...)` (AIController의 PathFollowingComponent가
    매 틱 호출) — 아래 "AI 추종 알고리즘" 참고
- 스페이스바 브레이크(`IA_Brake` → `SetBraking(true)`): 그냥 스로틀 0이 아니라 별도
  `BrakeDeceleration`(기본 1200, `Deceleration` 600보다 훨씬 큼)으로 감속 — 안 그러면
  W 떼는 것과 체감 차이가 없어서 의미 없음.

### 메시 전후방 축 문제
임시 탱크 메시가 로컬 **-X를 전면으로** export돼있음 (언리얼 표준 +X 아님). 콜리전과
비주얼이 같은 컴포넌트라 어긋날 일이 없도록, **부모/자식 회전 분리 대신 코드에서 -X를
"진짜 전진 방향"으로 취급**하는 방식으로 처리 (`UGVMovementComponent.h`의 "MESH FRONT
AXIS" 주석 참고). 나중에 진짜 탱크 모델 들어오면 이 상수만 없애면 됨.

### AI 추종(pursuit) 알고리즘
처음엔 AI가 매 틱 "목표 방향으로 heading을 절대각으로 스냅"하는 방식이었는데, 웨이포인트
지날 때마다 목표각이 홱홱 바뀌어 진동(꼬리치기)하고, 회전 속도 제한 때문에 좁은 코너에서
장애물에 부딪히는 문제가 있었음. **사람 운전하듯 각도 오차 → 조향/스로틀로 변환하는
추종 컨트롤러**로 교체:

```
AngleError = 목표 방향과 현재 heading의 차이 (부호 있음, ±180)
SteerInput = clamp(AngleError / SteerFullLockAngleDeg, -1, 1)          // 45도 이상이면 풀 조향
ThrottleFactor = clamp(1 - |AngleError| / ThrottleCutoffAngleDeg, 0, 1) // 90도 이상이면 스로틀 0 (제자리 회전)
ThrottleInput = clamp(요청속력 / MaxSpeed, 0, 1) × ThrottleFactor
```

코너 앞에서 자동으로 감속(먼저 회전, 그다음 전진)하게 되어 장애물 회피 여유가 생기고,
수동 조종과 같은 관성 물리를 타므로 진동도 줄어듦.

**보류된 항목** (나중에 궤도 기반 움직임으로 갈 때 한꺼번에 다시 다루기로 함, 지금은
손대지 않음):
- 충돌 시 `CurrentSpeed`가 즉시 0이 되지 않는 문제 (막힌 상태에서 계속 내부적으로
  가속되다가 방향 틀면 갑자기 튀어나감)
- 충돌 시 미끄러짐(`SlideAlongSurface`) 처리
- 완만한 경사/언덕 등반 (현재는 바닥 트레이스가 없어 순수 수평 이동만 함 — 낮은 경사도
  벽처럼 인식해서 못 올라감)
- 탱크 ↔ 사람 등 에이전트 간 상호 회피(RVO) — 사람 캐릭터는 `bUseRVOAvoidance` 체크박스로
  간단히 되지만, 우리 커스텀 무브먼트는 `UAvoidanceManager` 연동을 직접 구현해야 함

## 3. 모드 전환 — possess 기반, 전용 토글 없음

`EUGVDriveMode`(Manual/Auto)는 별도 상태 변수가 아니라 `GetDriveMode()`로 **현재
컨트롤러 타입에서 계산**함 (`APlayerController`면 Manual, 아니면 Auto). 이유:

- 기존 `titan_examplePlayerController::NextVehicle()`이 이미 레벨의 모든
  `UQuadCamComponent` 보유 Pawn을 순회하며 possess를 넘기는 로직을 갖고 있음 — UGV도
  QuadCam을 붙이므로 코드 수정 없이 그 순환에 자동 포함됨. **차량 선택은 이 기존
  메커니즘을 그대로 재사용**, UGV 전용 "모드 전환 키"는 만들지 않음.
- `AUGVPawn`은 `AutoPossessAI = PlacedInWorldOrSpawned`로 스폰 시 자동으로
  `AUGVAIController`가 possess (Auto 시작). `PossessedBy`/`UnPossessed` 오버라이드로:
  - `UnPossessed()`: 즉시 재-possess하지 않고 `bNeedsAIRepossess = true` 플래그만 세팅
    (같은 Possess() 호출 스택 안에서 다른 컨트롤러가 곧바로 이어받는 정상 케이스와
    재귀 호출이 꼬이는 걸 피하기 위해 한 틱 지연)
  - `Tick()`에서 `bNeedsAIRepossess && GetController() == nullptr`일 때만 캐싱해둔
    AIController로 재-possess + `MoveToDestination(TestDestination)` 재요청 (이전
    PathFollowingComponent 요청이 possess 전환 중에 남아있을 거라 믿지 않고 새로 요청)
- **속도/관성은 possess 전환 시에도 유지됨** — `StopMovementImmediately()`를 오버라이드해
  `CurrentSpeed`를 강제로 0으로 만들지 않도록 함 (이걸 빼먹었을 때 possess 전환마다
  탱크가 뚝 멈추는 버그가 있었음). 대신 `ThrottleInput`/`SteerInput`만 0으로 리셋해서
  자연스럽게 `Deceleration`으로 감속.

## 4. 카메라

- `ChaseCamera`: possess 시 메인 시점용 (TitanTruck엔 없던 것 — UGV는 실제로 몰아야 하니
  필요). 스프링암 없는 단순 추적 카메라.
- `FrontCamera`/`RearCamera`/`LeftCamera`/`RightCamera` (`SceneCaptureComponent2D`):
  `QuadCamComponent` 4분할 뷰용, TitanTruck과 동일 패턴 (컴포넌트 이름으로 자동 연결).
  메시가 -X 전면이라 배치 좌표가 TitanTruck과 좌우/전후 반대 — 정확한 위치는 대략치이니
  BP 뷰포트에서 눈으로 보고 조정 필요.
- `QuadCamComponent`에 `bAlwaysVisible`(기본 false) 추가 — 나중에 듀얼 모니터
  대시보드(한쪽 UGV, 한쪽 TitanTruck+UAV)에서 possess 여부와 무관하게 상시 표시할 때
  씀. 지금은 기존 M키+possess 게이팅 그대로.

## 5. NavMesh — 탱크 전용 넓은 반경 에이전트

임시 탱크 메시가 스케일 보정 전이라 실제 콜리전 바운딩 실린더가 매우 큼(~11m급). 이걸
그대로 두면 `FNavAgentProperties`가 -1(미설정)일 때 언리얼이 콜리전 바운드에서 반경/높이를
자동 계산해버려서(약 621cm) 어떤 네비메시도 감당 못 해 경로탐색이 통째로 실패하는 문제가
있었음. 그래서:

- **프로젝트 세팅 > Navigation System > Supported Agents**에 `Default`(반경 34, 사람용)와
  `Tank`(반경 800, UGV용) 두 개 에이전트 등록. 리빌드하면 레벨에 `RecastNavMesh-Default`와
  `RecastNavMesh-Tank` 두 개가 각자 생성됨.
- `AUGVPawn` 생성자에서 `Movement->NavAgentProps.AgentRadius = 800.f`로 명시적으로 고정
  (Tank 에이전트와 매칭) — 이러면 실제 메시 크기가 나중에 바뀌어도 내비게이션 반경은
  안전하게 고정됨.
- 사람 캐릭터(`BP_NavTestCharacter` 등)는 기본값(34) 그대로 둬서 좁은 반경 네비메시를
  사용 — 둘이 서로 다른 반경으로 장애물을 피해감.

### 겪었던 네비게이션 관련 함정들 (참고용)
- **`RecastNavMesh` 액터는 한 번 생성되면 자기만의 `AgentRadius` 값을 갖고, 이후 프로젝트
  세팅에서 기본값을 바꿔도 자동으로 안 따라감.** "Build Paths"는 액터가 이미 갖고 있는
  설정으로 다시 굽는 것뿐, 프로젝트 세팅 값을 새로 끌어오지 않음. → 액터 자체의 값을
  직접 바꾸거나(에디터 Details 패널), 아예 새로 생성되게 해야 함.
- **Supported Agents 배열에 새 항목을 추가할 때 기존 항목을 실수로 대체할 수 있음** —
  배열이 1개짜리로 남아있으면 "추가"가 아니라 "교체"된 것. 사람용 `Default`가 통째로
  사라지는 사고가 실제로 있었음.
- **수동으로 `RecastNavMesh` 액터를 만들고 `AgentRadius`만 손으로 설정하면 제대로 된
  에이전트로 인식 안 될 수 있음** — Supported Agents 목록에 정의해두고 엔진이 리빌드 시
  자동 생성하게 하는 게 정석 (수동 생성 시도는 실패했음, 삭제하고 이 방식으로 재시도해서
  성공).
- 각 `RecastNavMesh` 액터엔 `bEnableDrawing` 플래그가 따로 있어서, 하나가 꺼져있으면
  `P`키를 눌러도 그 네비메시만 안 보임 (경로탐색 자체는 정상 작동하는 것과 무관).

## 6. 반복적으로 겪은 엔진 함정 — Blueprint 인스턴스 값 고정(sticky override)

이번 작업에서 가장 많이 반복된 디버깅 패턴: **C++ 생성자의 기본값을 바꿔도, 이미
컴파일/배치된 Blueprint 인스턴스는 예전 값을 그대로 들고 있음.** (`AutoPossessAI`,
`bCanEverAffectNavigation`, `MoveAction`/`BrakeAction` 할당, 컴포넌트 부착 관계 등에서
반복 발생.) 원인 각각 다르지만 공통 증상은 같음 — 코드/CDO는 고쳤는데 씬에 이미 있는
액터만 안 바뀜. 대응: 해당 인스턴스에 직접 프로퍼티를 재설정하거나, 액터를 지우고 새로
스폰. **구조적인 변경(루트 컴포넌트 교체 등) 후에는 기존 배치 액터를 삭제하고 새로
스폰하는 게 제일 안전함** — 이번에 카메라 부착이 통째로 끊기는 사고(부모 컴포넌트 `null`)도
이 경로로 발생했었음.

## 7. 남은 작업

- [ ] 탱크 메시 스케일/피벗 보정 (여전히 임시 크기)
- [ ] `AUGVPathCorridor` 기반 오프 경로 감속 — 스플라인 배치 후 테스트 필요 (우선순위 낮음,
      실제로는 blocking으로 대체될 예정이라 크게 중요하지 않다고 판단)
- [ ] 충돌 처리 개선(속력 감쇠, 미끄러짐) + 경사/언덕 등반 — 궤도 기반 움직임 전환 시 함께
- [ ] 탱크 ↔ 다른 에이전트 상호 회피(RVO)
- [ ] `bAlwaysVisible` 실전 배치 (듀얼 모니터 대시보드 레이아웃)
- [ ] 4분할 뷰 On 시 FPS 저하(60→48) 최적화 — 캡처 주기/해상도 조정
- [ ] 실제 탱크 모델 도입 후: 포탑 회전, 궤도 회전, MESH FRONT AXIS 보정 코드 제거

사람 용 navmesh (반경 작음), 탱크 용 navmesh (반경 큼) 따로 존재가능함.

경로 point 는 경로상 꺽이는 부분들을 return
보간을 통해 더 늘리거나, maxSimplificationError 값을 높여서 point 개수를 줄이기 가능(실제로 경로가 단순해짐)

경사를 오르거나 현실적인 이동, 충돌 구현하려면 chaos vehicle 같은거 써야함

듀얼모니터
