> [보관됨 2026-08-31] `kadex_demo` 레벨/`BP_UGV`(구 액터) 기준 문서 — 현재는 `BP_UGV_Vehicle`
> + `kadex_test`/새 레벨 기준. 최신 자율주행/장애물회피 작업은 `vehicle/ugv/ugv_obstacle_avoidance_2026-08-26.md`,
> `vehicle/ugv/ugv_track_lock_implementation_plan.md`, `vehicle/ugv/new_kadex_0811_navmesh_autonomous_driving.md`
> 참고. 다만 Pure Pursuit 알고리즘·NavMesh 도로선호·`EUGVDriveMode` 설계 개념 자체는 지금도
> 유효(사용자 확인, "완전 중요한 게 아니면 아카이브해도 됨"이라 보관만 함, 삭제 아님).

# UGV 수동/자동 주행 개발 문서 및 관련 명령어 정리 (2026-07-06, 2026-07-08 업데이트)

## 0. 빠른 시작 — `kadex_demo` 레벨 실행 가이드

### 0.1 레벨 실행 시 자동으로 벌어지는 일
`kadex_demo` 레벨을 Play 하면(에디터 PIE든 패키징된 빌드든) 아래가 자동으로 실행됨
— 별도 조작 불필요:
- 좌/우 대시보드 위젯(트럭/UGV 패널) 뷰포트에 자동 표시
- 3D 월드 렌더링이 **꺼짐**(대시보드/카메라 피드로만 보는 시나리오 전제, 2절 참고) —
  라이브 3D 뷰가 필요하면 `SetWorldRenderingEnabled true` 콘솔 명령으로 켤 수 있음
- 마우스 커서 항상 표시(캡처 안 됨) — 대시보드 위젯 클릭용
- UGV는 `Auto` 모드로 시작해서 `BP_UGV`의 `TestDestination`으로 자동 주행 시작

### 0.2 명령어 실행 방법
PIE(또는 패키징 빌드) 실행 중 백틱(`` ` `` 또는 `~`) 키로 콘솔 열고 아래 명령어를
그대로 입력. 대소문자 무관.

### 0.3 UGV 주행 모드
| 명령어 | 설명 |
|---|---|
| `SetUGVMode Auto` | NavMesh 기반 자동 주행 (기본 시작 모드) — `TestDestination`까지 경로 재탐색 후 이동 |
| `SetUGVMode Manual` | 수동 조종 활성화 (WASD로 전후진/조향, Space로 브레이크) — **possess 안 해도 바로 조작 가능** |
| `SetUGVMode Idle` | 정지 + 자동 브레이크 고정 (경사로에서도 안 미끄러짐) |

수동 조작 시 WASD/Space는 `Atitan_examplePlayerController`에 바인딩되어 있어서
UGV를 possess하지 않아도 그대로 먹힘 (11.3절).

### 0.4 RCWS/UAV 카메라 조작 (조이스틱)
| 명령어 | 설명 |
|---|---|
| `SetCameraControlTarget TruckRCWS` | TitanTruck RCWS 카메라로 조이스틱 pan/tilt 연결 |
| `SetCameraControlTarget UGVRCWS` | UGV RCWS 카메라로 연결 |
| `SetCameraControlTarget UAV` | UAV 짐벌 카메라로 연결 |
| `SetCameraControlTarget Idle` | 조이스틱 입력 어디에도 안 감 (기본값) |

연결 후 조이스틱 좌우/전후로 해당 카메라 pan/tilt 조작(일반 FPS처럼 yaw/pitch만,
roll 없음). **조이스틱 자체를 처음 세팅하는 방법**(하드웨어 인식, 플러그인 설치 등)은
`joystick_camera_control_dev_guide.md` 참고 — 이미 세팅 끝난 상태라면 위 명령어만
알면 됨.

RCWS/UAV 카메라 화면에 뜨는 아군/적군 바운딩 박스(객체 탐지 모사)는
`detection_dev_guide.md` 참고.

### 0.5 기타 명령어
| 명령어 | 설명 |
|---|---|
| `SetWorldRenderingEnabled true` / `false` | 3D 월드 라이브 렌더링 켜기/끄기 (기본 꺼짐) |

### 0.6 씬별로 조정 가능한 값 (코드 안 건드리고 BP에서)
`BP_UGV`(또는 그 인스턴스) Class Defaults에서 조정 가능한 값들 — 필요하면 씬마다
다르게:
- `Test Destination` — Auto 모드 시작 시 목적지
- `Max Road Distance`(기본 400m) — 이보다 도로에서 멀어지면 자동 텔레포트 (13절)
- `Path Corridor` — 오프 경로 감속용 스플라인 (선택)

`BP_ThirdPersonPlayerController`(또는 실제 쓰는 PlayerController BP)에서:
- `Camera Look Rate Deg Per Sec`(기본 90) — 조이스틱 카메라 조작 감도
- `UGV Move Action`/`UGV Brake Action`/`Camera Look Action` — 입력 액션 애셋 연결
  (이미 세팅되어 있으면 안 건드려도 됨)

> **2026-07-08 업데이트**: 아래 2절이 설명하는 "속력+heading 근사" 방식의 kinematic
> 모델은 이후 **완전 물리 기반(rigid body force) 모델로 전면 재작성**됐음. 2절은
> 과거 기록으로 남겨두고, 현재 구조는 8~10절 참고. NavMesh 관련 5절도 Tank 에이전트
> 반경 값(800)이 이후 200으로 조정됐음 — 10절 참고.
>
> **2026-07-08 추가 업데이트**: 3절이 설명하는 "possess 기반 모드 전환"도 이후
> **명시적 `EUGVDriveMode`(Idle/Manual/Auto) 상태 + 커맨드 전환** 방식으로 대체됨 —
> 11절 참고. 오프로드 속도 처리 방식도 12절에서 재변경. 신규로 맵 이탈 방지(도로
> 경계 텔레포트)를 13절에 추가.
>
> **2026-07-12 업데이트**: **기어 시스템(P/R/N/1~5단)을 14절에 신규 추가** — 8절의
> 단일 `EngineForceMagnitude` 힘 모델이 기어별 토크 테이블 기반으로 확장됨. 조향력을
> 엔진 토크에서 완전히 분리(15절), 스로틀 힘에 램프 + 방향전환 리셋 추가(16절),
> 브레이크를 인위적 힘 주입 방식에서 **마찰력(Coulomb friction) 기반**으로 전면
> 재작성(17절, 12절에서 만든 `PhysicalMaterial` 스위칭 메커니즘 재사용) — 8.4절의
> 마찰 관련 내용은 이제 브레이크 쪽에도 적용되니 같이 참고. UGV 질량도 15톤 placeholder
> 에서 **3톤으로 확정**되고 그에 맞춰 힘 관련 파라미터 전체가 재튜닝됨(18절) — 8절의
> `EngineForceMagnitude=2,000,000` 등 예시 수치는 이제 18절 값으로 대체됨.

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

## 3. 모드 전환 — possess 기반, 전용 토글 없음 (⚠ 11절에서 대체됨, 과거 기록)

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

## 7. 남은 작업 (2026-07-06 시점, 취소선은 이후 해결됨)

- [ ] 탱크 메시 스케일/피벗 보정 (여전히 임시 크기)
- [x] ~~`AUGVPathCorridor` 기반 오프 경로 감속~~ — 배치 후 살아있음. 물리 모델 재작성으로
      `MaxSpeed`를 더 이상 안 쓰게 되면서 한 번 깨질 뻔했다가 `ExternalForceMultiplier`로
      갈아끼워서 계속 작동(10절 참고)
- [x] ~~충돌 처리 개선 + 경사/언덕 등반~~ — 물리 기반 모델 재작성으로 자연스럽게 해결
      (8절). Chaos Vehicle까지는 안 가고 직접 힘 주입 모델로 충분히 해결됨
- [ ] 탱크 ↔ 다른 에이전트 상호 회피(RVO)
- [ ] `bAlwaysVisible` 실전 배치 (듀얼 모니터 대시보드 레이아웃)
- [ ] 4분할 뷰 On 시 FPS 저하(60→48) 최적화 — 캡처 주기/해상도 조정
- [ ] 실제 탱크 모델 도입 후: 포탑 회전, 궤도 회전, MESH FRONT AXIS 보정 코드 제거
- [ ] (신규, 10절) 도심 `road` 액터 도로 선호 미해결
- [ ] (신규, 10절) NavMesh P키 시각화 색상이 항상 검게 나오는 버그 — 기능엔 영향 없음, 원인 미상
- [ ] (신규, 10절) 급경사 구간 `RoadNavMod` 볼륨 Z 스케일 수동 보정 필요할 수 있음
- [x] ~~possess 기반 모드 전환~~ — 명시적 `EUGVDriveMode`(Idle/Manual/Auto) 상태로 대체,
      possess 여부와 완전히 무관하게 동작 (11절)
- [x] ~~오프로드 가속력 자체를 깎는 방식~~ — 저속 가속력 유지가 필요해져서 항력
      증폭 + 선형 감속 방식으로 교체 (12절)
- [x] ~~맵 이탈 방지~~ — 도로 네트워크 기준 거리 초과 시 자동 텔레포트 (13절)

## 8. 물리 기반 주행 모델로 전면 재작성 (2026-07-08)

2절의 kinematic(속력+heading 근사) 모델을 버리고, `BodyMesh`에 실제 리지드바디
시뮬레이션을 켜서 **가상 트랙 두 지점에 힘을 주입하는 방식**으로 다시 만듦. 중력,
경사, 충돌 반응을 물리 엔진이 전부 대신 계산해주므로 이 컴포넌트가 할 일은
`ThrottleInput`/`SteerInput`(-1..1)을 힘으로 변환하는 것뿐. 수동/자동 통합 구조(같은
두 입력값 공유)는 그대로 유지.

### 8.1 핵심 구조

```
BodyMesh->SetSimulatePhysics(true)
BodyMesh->SetMassOverrideInKg(15000kg)
BodyMesh->BodyInstance.COMNudge = (0,0,-100)   // 무게중심 낮춰서 전복 방지
BodyMesh->BodyInstance.AngularDamping = 3.0
```

매 틱(`ApplyTrackForces`):
1. 무게중심(`GetCenterOfMass()`) 기준 좌/우 트랙 접점 계산 (`TrackOffset`, Right축 기준)
   — 컴포넌트 원점이 아니라 실제 무게중심 기준으로 offset해야 좌우 대칭 힘이 진짜
   대칭 토크가 됨 (원점 기준으로 했다가 한쪽으로 계속 쏠리는 버그 겪음)
2. 각 트랙을 전/후 2점씩, 총 4점 접지 검사 (`TrackLengthOffset`) — 슬로프 정상부에
   중심만 뜨고 앞/뒤 중 하나는 닿아있는 경우도 정상적으로 접지 판정하기 위함
3. 접지 안 된 트랙엔 아예 힘을 안 줌 — 이게 없었을 때 슬로프 경계나 최고속도 근처에서
   탱크가 롤러코스터처럼 공중제비 돌던 버그의 원인이었음
4. `Throttle=0, Steer≠0`이면 좌우 반대 방향 힘(제자리 회전), 아니면
   `LeftThrottle=Throttle-Steer`, `RightThrottle=Throttle+Steer`인 스킷-스티어 모델

### 8.2 횡방향 그립 (`ApplyLateralGrip`)

바퀴/궤도가 없는 리지드바디는 실제 마찰이 있어도 회전 중 옆으로 미끄러짐(아이스스케이팅
현상)이 남음. 속도를 `TrueForward` 기준 전진/횡방향으로 분해해서 **횡방향 성분만** 감쇠하는
힘을 추가 (전진/후진 성분은 그대로 둬서 경사면에서 중력에 의한 가속/감속은 안 건드림).
이 시스템은 **엔진 마찰값(8.4절)과 완전히 독립**이라, 마찰을 얼마나 낮춰도 옆으로
미끄러지는 문제는 안 생김.

### 8.3 최고속도 — 하드 캡 제거, 항력 기반으로 전환

처음엔 `MaxSpeed`로 매 틱 속도를 강제로 클램프했는데, 문제가 두 가지:
- 오르막/내리막에서 결국 같은 캡에 걸려서 경사 차이가 거의 안 느껴짐
- 언리얼 엔진 내장 `LinearDamping`은 속도에 **선형** 비례라, 실제 공기/구름 저항(속도의
  **제곱**에 비례)보다 훨씬 약해서 엔진힘을 못 따라잡음 → 그래서 하드 캡이 필요했던 것

**해결**: `ClampMaxSpeed()` 제거, 매 틱 `-velocity_normalized × speed² × AirResistanceCoefficient`
형태의 항력을 힘으로 직접 추가(`ApplyAirResistance`). 엔진힘 = 항력이 같아지는 지점에서
자연스럽게 종단속도가 생기고, 경사에서는 중력의 경사방향 성분이 이 힘 균형에 그대로
더해져서(오르막은 종단속도 ↓, 내리막은 ↑) 실제로 경사 차이가 느껴짐. 온로드/오프로드
최고속도 차이도 더 이상 별도 배율이 필요 없음 — 엔진힘만 줄여도 종단속도가
`sqrt(힘)`에 비례해 자연히 같이 낮아짐 (`OffRoadMaxSpeedMultiplier` 제거).

AI 추종 쪽 스로틀 계산에서도 `DesiredSpeed / MaxSpeed` 정규화를 없앰 — "최대 속도"라는
기준 자체가 없어졌으므로, 회전각에 따른 감속(`ThrottleFactor`)만 남기고 나머지는 항상
풀스로틀(사람이 그냥 액셀 끝까지 밟는 것과 동일한 방식, 실제 속도는 물리가 알아서 정함).

### 8.4 마찰/반발계수 버그 — "왜 엔진힘이 천만이나 필요하지?"

`EngineForceMagnitude`를 거의 1000만(트랙당)까지 줘야 겨우 움직이는 현상 발견. 계산해보니:

```
정지마찰력 ≈ 질량 × 중력 × 마찰계수 = 15000 × 980 × 0.7 ≈ 10,290,000 (UE 힘단위, kg·cm/s²)
```

UGV든 지형이든 어디에도 `PhysicalMaterial`을 지정한 적이 없어서 **언리얼 엔진 하드코딩
기본값(마찰 0.7, 반발계수 0.3)을 그대로 쓰고 있었음** — 우리 트랙 힘은
`AddForceAtLocation`으로 직접 주입하는 방식이라(진짜 바퀴처럼 마찰이 추진력의 원천이
아님) 마찰이 순전히 저항으로만 작용, 엔진힘의 거의 전부가 정지마찰을 겨우 이기는 데
소모되고 있었던 것. 실제 필요한 힘은 F=ma로 역산하면 15톤 기준 트랙당 100~200만
정도면 충분.

**해결**: `BeginPlay`에서 트랜지언트 `PhysicalMaterial`(콘텐츠 브라우저에 안 남는
런타임 전용 오브젝트, 다른 튜닝값들처럼 컴포넌트 프로퍼티로 노출)을 만들어
`SetPhysMaterialOverride`로 적용.
- `GroundFriction`(기본 0.15) — `FrictionCombineMode = Min`이라 지형 쪽 마찰이 뭐든
  이 낮은 값이 항상 이김 (지형 애셋마다 일일이 마찰 낮출 필요 없음)
- `GroundRestitution`(기본 0) — 반발계수 0.3이 남아있으면 범프/착지 때 눈에 띄게
  통통 튀는 느낌이 남았음

수치 재조정: `EngineForceMagnitude` 1000만→200만, `BrakeForceMagnitude` 2000만→400만
(같은 비율 유지).

### 8.5 `ExternalForceMultiplier` — 구 `MaxSpeed` 기반 시스템과의 호환

`AUGVPawn::UpdateOffPathSlowdown()`(`UGVPathCorridor` 기반 오프 경로 감속, 7절의
"남은 작업"에 있던 그 기능)이 `Movement->MaxSpeed`를 직접 조작하는 방식이었는데,
8.3절에서 `MaxSpeed`를 아예 안 쓰게 되면서 조용히 죽은 코드가 될 뻔함. 힘 배율
방식으로 갈아끼움:

```cpp
// UGVMovementComponent: ApplyTrackForces에서 브레이킹 제외 힘에 곱함
float ExternalForceMultiplier = 1.f;

// AUGVPawn::UpdateOffPathSlowdown()
Movement->ExternalForceMultiplier = bOffPath ? PathCorridor->OffPathSpeedMultiplier : 1.f;
```

외부 시스템이 "이 구간에서는 속도를 줄이고 싶다"는 요구를 힘 배율로 표현할 수 있는
범용 훅 — 앞으로 비슷한 요구(예: 특정 구역 서행)가 생기면 이걸 재사용하면 됨.

## 9. AI 추종 — Pure Pursuit Lookahead (2026-07-08)

2절에 설명된 "각도 오차 → 조향/스로틀" 방식은 유지하되, **조향 목표 자체를 바꿈**.

### 문제
`PathFollowingComponent`가 매 틱 주는 `MoveVelocity`는 "현재 향하고 있는 원시
경로점"을 그대로 가리킴. 그 경로점에 도달하는 순간 목표가 다음 경로점으로 **한
프레임 만에 통째로 전환**되고, 방향이 많이 다르면 조향이 순간적으로 확 꺾여서 진동함.
(내비메시 도로 선호(10절)로 폭 좁은 스트립을 타게 되면서 경로점이 더 촘촘/꺾임이
많아져 이 문제가 두드러짐.) 조향 출력 자체에 변화율 제한을 걸어봤지만(너무 느리면
저속 좌우 반복, 너무 빠르면 코너에서 여전히 출렁) 근본 해결은 안 됐음 — **입력(목표
자체)이 이산적으로 튀는 게 원인**이라 출력 필터링으로는 한계가 있었음.

### 해결 — Pure Pursuit
`RequestDirectMove`에서 `MoveVelocity`의 방향을 그대로 안 쓰고, `FindLookaheadTarget`으로
**"현재 위치에서 경로를 따라 `LookaheadDistance`(기본 800cm)만큼 앞선 보간 지점"**을
직접 계산해서 그 지점을 조준:

1. `AAIController → PathFollowingComponent → GetPath()`로 원본 경로점 배열 획득
2. 탱크 현재 위치에서 각 세그먼트에 투영해 가장 가까운 지점(+그 세그먼트 인덱스, t값) 탐색
3. 거기서부터 경로를 따라 `LookaheadDistance`만큼 걸어가며 목표점 보간 (경로 끝을
   넘어가면 최종 목적지를 그대로 조준)

목표점이 실제 경로점이 아니라 경로선 위의 임의 보간점이라, 탱크가 코너에 도달하기
훨씬 전부터 이미 다음 구간 쪽으로 목표가 서서히 이동 — 도착 순간의 이산적 전환
자체가 없어짐. `LookaheadDistance`가 클수록 코너를 더 여유있게 자르고, 작을수록
경로에 밀착하되 예전 문제가 일부 재발할 수 있음.

기존 조향 변화율 제한(`MaxSteerChangeRatePerSecond`)은 안전망으로 계속 남겨둠 —
lookahead 도입 후엔 목표 자체가 부드러우니 이게 걸리는 일은 훨씬 줄어듦.

### 도착 판정 (`DestinationAcceptanceRadius`)
Pure pursuit 자체엔 "도착"이라는 개념이 없어서, 목적지에 다 와서도 정확히 그 점(거리
0)에 도달할 때까지 계속 쫓아가며 제자리에서 맴도는 버그가 있었음.
`FindLookaheadTarget`이 탱크가 경로 최종점에서 `DestinationAcceptanceRadius`(기본
150cm) 안에 들어오면 **탱크의 현재 위치 자체를 목표로 반환** — 방향이 자연스럽게
0이 되어 기존 "방향 0이면 정지" 로직이 그대로 작동.

## 10. NavMesh 도로 선호 시스템 (2026-07-08)

목표: UGV가 Landscape 스플라인 도로(148개 세그먼트) + 도심 `road` 액터를 최대한 타고
이동하도록 경로탐색 비용을 조정하고, 실제 주행 시에도 온로드/오프로드 가속·최고속도가
달라지게 함.

### 10.1 `UNavArea_Road`
```cpp
UCLASS()
class UNavArea_Road : public UNavArea
{
    UNavArea_Road() { DefaultCost = 0.2f; DrawColor = FColor::Orange; }
};
```
기본 영역보다 5배 싸게 잡아서 Recast A*가 다소 돌아가더라도 도로를 선호하게 함.
`DrawColor`는 P키 시각화 구분용 (10.4절 참고 — 지금 시각화 자체가 원인 불명으로
깨져있어서 큰 의미는 없음).

### 10.2 시행착오 — 메시 전체 폭 적용은 안 통함
처음엔 도로 스태틱메시 애셋(`d_road_02`, `d_road_03`, 도심 `road`)의
`NavCollision.bUseSurfaceArea/AreaClass`를 걸어서 메시 전체 폭에 도로 비용을 입히는
방식으로 시작. 결과:
- **Landscape 스플라인 도로 148개는 성공** — 하지만 도로 폭 **전체**(포장+흙길 다)가
  같은 비용을 받다 보니, 경로가 도로 중심이 아니라 가장자리를 아슬아슬하게 스치듯
  지나가고, 그 경계에서 온로드/오프로드 판정이 계속 바뀌며 조향이 출렁이는 문제가
  있었음 (9절 문제의 원인이기도 했음)
- **도심 `road` 액터는 아예 실패** — 이 도로는 원본 Landscape 지형 위에 그냥 얹혀
  있어서(스플라인 도로는 반대로 Landscape 자체를 도로 모양대로 깎아둔 것) 지면과 거의
  같은 높이라, Recast 복셀화 단계에서 두 표면이 병합되며 Landscape의 기본 영역에
  흡수돼버림 (`RecastRasterization.cpp`의 `mergeSpanData` — 높이차가 작으면 영역ID가
  더 큰 쪽이 이김)

### 10.3 해결 — 스플라인 세그먼트 기반 좁은 중심 스트립
실제 포장 부분은 전체 폭의 1/3 정도, 나머지는 흙길이라는 점에 착안 — **도로 폭의
1/4만큼 좁은 중심 스트립**만 저비용 영역으로 만들어서, "회랑 안이면 아무데나
지나가는" Detour 특성상 경로가 자연히 중심으로 몰리게 유도.

Landscape Splines는 일반 `SplineComponent`가 아니라 전용 시스템이라 엔진 내장
`USplineNavModifierComponent`를 못 붙임. 대신 이미 배치된 148개
`SplineMeshComponent`가 각자 자기 구간의 시작/끝/스케일 데이터를 갖고 있다는 점을
이용 — 하나하나 손으로 배치할 필요 없이 스크립트로:

1. 각 세그먼트의 로컬 `startPos`/`endPos`/`startScale`/`endScale`을 월드 좌표로 변환
   (Landscape 액터 위치 + `LandscapeSplinesComponent`의 보정 스케일 0.01 반영 — 이
   둘이 정확히 상쇄되어 순 스케일 1.0이 되는 걸 확인 후 계산)
2. 세그먼트별 실제 폭(로컬 폭 × 그 세그먼트의 startScale, 세그먼트마다 스케일이 다름)의
   1/4로 얇은 `NavModifierVolume` 자동 생성, 세그먼트 방향으로 회전 정렬
3. `AreaClass = NavArea_Road` 지정 → **148개 전부 스크립트 한 번으로 생성 성공**
4. 기존 메시 전체 폭 `NavCollision.bUseSurfaceArea`는 `false`로 되돌려서, 좁은 볼륨과
   충돌하지 않게 함

도심 `road` 액터(도로망 전체가 하나의 거대 메시로 뭉쳐있음, 약 2400m×970m)는 이
방식이 안 통해서 **아직 미해결** — 세그먼트 단위로 쪼갤 수 있는 구조가 아님. 나중에
별도로 다뤄야 함.

### 10.4 Tank 에이전트 반경 800 → 200
도로 스트립 적용 후, Default 에이전트는 정상 반영되는데 **Tank 에이전트만 그대로**인
문제 발견. 원인: Recast는 폴리곤 리전 병합 시 에이전트 크기에 비례한 최소 영역
크기 기준을 쓰는데, Tank의 `AgentRadius=800`(지름 16m!)에 비하면 우리 도로
스트립(대략 300~400cm대)이 너무 작은 영역이라 리전 병합 단계에서 주변 영역에
흡수되어버림. 애초에 실제 UGV 물리 트랙 폭(500cm)보다 Tank 반경이 훨씬 컸던 게
문제 — **200으로 낮춤**(프로젝트 세팅 `DefaultEngine.ini`의 `SupportedAgents`와
레벨의 `RecastNavMesh-Tank` 액터 둘 다). 너무 낮추면 실제 장애물과 충돌 위험이 있어
이 값에서 일단 만족, 필요하면 나중에 **경로점 후처리로 도로 중심 쪽으로 당기는** 방식
추가 고려.

### 10.5 온로드/오프로드 런타임 속도 차등
`UGVMovementComponent::ApplyTrackForces`가 매 틱 도는 4점 접지 레이캐스트 결과를
재사용해서 온로드 여부 판정 — 단, **접지 판정(라인트레이스)과 온로드 판정은 분리된
별도 쿼리**:
- 접지: 기존처럼 `ECC_WorldStatic` 라인트레이스로 실제 지면/도로 메시와 충돌 확인
- 온로드: 같은 지점에서 `ECC_GameTraceChannel1`(전용 채널) 오버랩 쿼리로
  `RoadNavMod` 볼륨(10.3절)에 "RoadSurface" 태그가 있는지 확인

처음엔 "라인트레이스가 부딪힌 컴포넌트에 RoadSurface 태그가 있는지"로 단순하게
했었는데, 이러면 도로 메시 **전체 폭**(포장+흙길)이 온로드로 잡혀버려 10.3절에서
좁힌 의미가 없어짐. 그래서 메시 쪽 태그는 제거하고, 대신 좁은 `RoadNavMod` 볼륨
자체에 오버랩 전용 콜리전(`QueryOnly`, `GameTraceChannel1`에서만 Overlap)과 태그를
줘서, 지면 판정에 전혀 끼어들지 않으면서 좁은 영역만 정확히 감지하게 함.

### 10.6 남은 문제
- 도심 `road` 액터 도로 선호 (10.3절 끝 참고)
- NavMesh P키 시각화가 Default/Tank 둘 다 항상 반투명 검은색으로만 보임 — 레벨 시작
  시점부터 변함없던 현상이라 이번 작업과 무관, 실제 경로탐색 기능엔 영향 없음
  (원인 미상, 우선순위 낮음)
- 급경사 구간에서 `RoadNavMod` 볼륨이 도로 표면을 다 못 덮는 경우 있음 (평평한
  박스라 pitch 회전 없이 생성됨) — 수동으로 Z 스케일 키워서 대응 중

## 11. 모드 전환 재설계 — possess 독립 `EUGVDriveMode` (2026-07-08)

멀티 차량 대시보드(트럭/UGV/UAV 동시 운용)를 염두에 두면, "누가 possess 중인가"로
주행 모드를 유추하는 3절 방식은 한계가 있음 — 대시보드 조작자가 특정 차량을 possess
하지 않은 채로 그 차량의 자동/수동/대기 상태를 전환하고 싶은 경우가 생김. 그래서
**주행 모드를 possess와 완전히 분리된 명시적 상태**로 재설계.

### 11.1 `EUGVDriveMode { Idle, Manual, Auto }`
`UGVPawn.h`에 정의. `UUGVMovementComponent::DriveMode`(기본값 `Auto` — 기존처럼 씬
플레이 시 자동주행 시작하는 동작을 그대로 유지)가 유일한 소스:

```cpp
// UUGVMovementComponent
void SetManualControl(...)   { if (DriveMode != Manual) return; ... }  // Manual 아니면 무시
void RequestDirectMove(...)  { if (DriveMode != Auto)   { 정지; return; } ... }  // Auto 아니면 무시
void SetDriveMode(NewMode)   { DriveMode = NewMode; 입력 리셋; bBraking = (NewMode == Idle); }
```

`AUGVAIController`는 이제 **항상 이 폰을 possess한 채로 유지** (플레이어가 별도로
possess해도 뺏기지 않게 하는 게 아니라, 애초에 possess 여부가 Auto/Manual 판정에
영향을 안 주도록 만든 것 — 기존 `PossessUGV`류 카메라용 possess 메커니즘은 그대로
남아있지만 이제 주행 로직과는 완전히 무관한 별개 개념).

### 11.2 명령어 전환 — `SetUGVMode`
`titan_examplePlayerController`에 `SetUGVMode(FString Mode)` Exec 추가 (기존
`PossessUGV`/`PossessTitanTruck`과 같은 위치, 같은 스타일). 콘솔에서
`SetUGVMode Auto` / `Manual` / `Idle` (대소문자 무관) — possess 안 해도 바로 작동.

### 11.3 Manual 조작도 possess 없이 — 입력 바인딩을 Pawn에서 PlayerController로 이동
기존엔 WASD/Space가 `AUGVPawn::SetupPlayerInputComponent`에 바인딩돼있어서, **pawn을
실제로 possess해야만** 입력 이벤트가 들어왔음 (possess가 곧 "이 pawn이 로컬 플레이어
입력을 받는다"는 엔진 기본 동작이라). Manual 모드도 possess 없이 되게 하려면 이
전제 자체를 없애야 함 — WASD/Space 바인딩을 **PlayerController 쪽**(항상 InputComponent가
존재하는 대상)으로 옮기고, 매 프레임 possess 여부와 무관하게 레벨의 UGV를 찾아
`Movement->SetManualControl(...)`을 직접 호출:

```cpp
// Atitan_examplePlayerController
UInputAction* UGVMoveAction;   // 같은 IA_Move 재사용
UInputAction* UGVBrakeAction;  // 같은 IA_Brake 재사용

void DoUGVMove(const FInputActionValue& Value)
{
    AUGVPawn* UGV = GetOrFindUGV();  // 캐싱된 lazy lookup
    if (UGV && UGV->Movement) UGV->Movement->SetManualControl(Value.Y, Value.X);
}
```

`SetManualControl`이 이미 `DriveMode != Manual`이면 무시하니, 이 바인딩은 possess
여부와 무관하게 항상 걸려있어도 안전함 (Manual 모드일 때만 실제로 반영됨). 기존
Pawn 쪽 바인딩은 그대로 남겨둠 — 혹시 옛 방식대로 possess해서 몰아도 똑같은 값이
중복으로 세팅될 뿐 부작용 없음.

### 11.4 Auto 재진입 시 목적지 재요청
`SetDriveMode`로 Auto에 재진입할 때 `CachedAIController->MoveToDestination(TestDestination)`을
다시 호출 — 안 그러면 Manual/Idle로 한동안 서있는 사이 엔진의 정지/블록 감지가
기존 경로 요청을 조용히 끝내버려서, Auto로 돌아와도 제자리에 가만히 있는 버그가
있었음.

### 11.5 Idle = 자동 브레이크
`SetDriveMode(Idle)`에서 `bBraking = true`로 고정 (Manual이 아니면 `SetBraking`이
무시되므로 다른 데서 이걸 못 풂) — 경사로에 세워둬도 미끄러지지 않게.

## 12. 오프로드 속도 처리 — 항력 증폭 + 선형 감속 (2026-07-08)

10.5절에서 구현했던 온로드/오프로드 판정(`bIsOnRoad`)의 실제 반영 방식이 두 번
바뀜. 처음엔 `OffRoadAccelerationMultiplier`로 **엔진힘 자체**를 오프로드에서
줄이는 방식이었는데, 이러면 오프로드에서 저속/출발 가속력까지 같이 죽어버려서
"흙길에선 출발도 잘 못하는" 비현실적인 느낌이 났음. **엔진힘은 온/오프로드 무관하게
항상 동일**하게 두고, 대신 속도를 깎는 두 항을 오프로드에서만 추가:

```cpp
// ApplyAirResistance
EffectiveAirResistanceCoefficient = bIsOnRoad ? AirResistanceCoefficient
                                              : AirResistanceCoefficient * OffRoadAirResistanceMultiplier;
// 기존 v^2 항력식에 이 계수를 씀 — 저속에선 거의 영향 없고(v^2이라 작음),
// 순항 속도에서만 실질적으로 상한을 낮춤

// 추가: 오프로드에서만 매 틱 전진 속도 성분에 곱함 (직접 속도 조작, 힘이 아님)
if (!bIsOnRoad) ForwardVelocity *= (1.f - OffRoadSpeedDecayPerTick);  // 기본 0.01 (틱당 1%)
```

`OffRoadSpeedDecayPerTick`은 속도 크기와 무관한 고정 비율 감쇠라 저속에도 그대로
적용되지만(구름저항에 더 가까운 성격), `EngineForceMagnitude`는 전혀 안 건드리므로
가속 자체는 오프로드에서도 항상 최대. 감속 성분은 `TrueForward` 기준 전진 속도에만
적용 — 횡방향(`ApplyLateralGrip`)/수직(중력) 속도는 안 건드림.

## 13. 맵 이탈 방지 — 도로 경계 텔레포트 (2026-07-08)

간단한 "탱크가 플레이 영역 밖으로 너무 멀리 나가면 도로 위로 복귀" 로직.

### 13.1 기준: NavMesh 도로 선호에 쓰인 그 볼륨을 재사용
10.3절에서 만든 148개 `RoadNavMod`(`ANavModifierVolume`, `AreaClass = NavArea_Road`)를
`BeginPlay`에서 한 번만 스캔해 캐싱(`AreaClass` 기준 필터 — 라벨/태그가 아니라
클래스 기준이라 이름이 바뀌어도 안전, 도심 `road` 액터처럼 이 볼륨이 없는 대상은
자연히 제외됨). 매 틱, 각 볼륨의 실제 콜리전에 대해
`UPrimitiveComponent::GetClosestPointOnCollision()`을 호출 — 회전된 박스라도
직접 오리엔티드 박스 최근접점 수식을 짤 필요 없이 엔진이 알아서 계산해줌. 전체
볼륨 중 최소 거리를 그 프레임의 "도로까지 거리"로 씀.

```cpp
UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "UGV")
float MaxRoadDistance = 40000.f;  // 40000cm = 400m (기본 큐브 스케일 400 감각으로 설정)
```

거리가 `MaxRoadDistance`(BP_UGV에서 커스터마이즈 가능) 초과 시 그 최근접점으로
텔레포트.

### 13.2 함정 — 텔레포트 높이가 세그먼트마다 들쭉날쭉했던 버그
`GetClosestPointOnCollision`이 돌려주는 점은 **볼륨 자기 자신의 박스 콜리전 표면
위** 점이지, 실제 지형/도로 표면 높이가 아님 (볼륨엔 실제 두께가 있고, 급경사
구간은 사용자가 Z 스케일을 수동으로 더 키워둔 것도 있어 높이가 세그먼트마다 다름).
처음엔 이 점을 그대로 텔레포트 좌표로 썼더니 어떤 세그먼트에선 도로에 딱 붙고
어떤 세그먼트에선 공중에 붕 뜨는 현상 발생.

**원인 진단**: 그 지점에서 실제 지형 표면을 다시 구하려고 `ECC_WorldStatic`
라인트레이스를 추가했는데도 안 고쳐짐 → `RoadNavMod` 볼륨의 콜리전 리스폰스를
직접 조회해보니:

```json
"collisionProfileName": "Custom",
"collisionResponses": {"responseArray": [
  {"channel":"Visibility","response":"ECR_Ignore"},
  {"channel":"Camera","response":"ECR_Ignore"},
  {"channel":"GameTraceChannel1","response":"ECR_Overlap"}
]}
```

`WorldStatic`이 배열에 없어서 Custom 프로파일의 기본값(**Block**)으로 남아있었음
— 즉 지형 높이를 구하려던 `ECC_WorldStatic` 트레이스가 **투명한 볼륨 박스 자체를
맞히고 있었던 것**. 볼륨 높이가 세그먼트마다 다르니 딱 그만큼 텔레포트 높이가
들쭉날쭉했던 것.

**해결**: 트레이스 `FCollisionQueryParams`에 캐싱해둔 148개 `RoadNavMod` 볼륨을
전부 `AddIgnoredActor`로 무시 등록 — 이제 실제 Landscape/도로 메시만 맞음.

```cpp
FVector TeleportLocation = BestPoint;
if (World->LineTraceSingleByChannel(Hit, BestPoint+(0,0,5000), BestPoint-(0,0,5000),
        ECC_WorldStatic, QueryParams /* 148개 볼륨 전부 ignore */))
{
    TeleportLocation = Hit.Location + (0,0,TeleportSurfaceClearance); // 기본 50cm
}
```

### 13.3 텔레포트 시 안전 상태 초기화
- 회전: Pitch/Roll을 0으로 리셋(Yaw는 유지) — 전복된 채로 텔레포트되는 것 방지
- 속도: 물리 기반 이동이라 `SetActorLocation`만으론 기존 선속도/각속도가 그대로
  남음 → `SetPhysicsLinearVelocity`/`SetPhysicsAngularVelocityInDegrees`로 0 초기화

### 13.4 알림
`OnLeftDesignatedArea()` (`BlueprintImplementableEvent`, `BP_UGV`에서 오버라이드해
원하는 WBP 토스트 연결 가능) + `UE_LOG` 경고 + 즉시 확인용
`GEngine->AddOnScreenDebugMessage`("지정 구역을 벗어났습니다") 셋 다 같이 발생.

## 14. 기어 시스템 — P/R/N/1~5단 (2026-07-12)

memo.md 의문사항 5("최대 기어 = 속도 제한?")와 ui.md의 기어 표시 요구사항을 반영.
8절의 단일 `EngineForceMagnitude`(트랙당 고정 힘)를 **기어별 토크 테이블** 기반으로
확장 — 기어마다 자기 자신의 최고속도/토크를 갖고, 자동으로 변속됨.

### 14.1 상태 정의
```cpp
UENUM(BlueprintType)
enum class EUGVGear : uint8 { Park, Reverse, Neutral, Gear1, Gear2, Gear3, Gear4, Gear5 };

USTRUCT(BlueprintType)
struct FUGVGearParams
{
    float MaxSpeedKmH = 20.f;      // 이 기어의 토크 커브가 ~0에 도달하는 속도
    float TorqueMultiplier = 1.f;  // EngineForceMagnitude에 곱하는 배수
};
```
`GearTable`(`TArray<FUGVGearParams>`, 인덱스 0=1단)로 1~5단 관리. **R(후진)은 별도
엔트리 없이 `GearTable[0]`(1단) 값을 그대로 재사용** — 스펙: "R 후진은 1단과 같은
토크, 속력". `MaxGear`로 자동변속이 도달 가능한 최고 기어를 제한(콘솔 `SetUGVMaxGear
<N>`) — 의문사항 5가 여기서 해결됨: 기어마다 자기 최고속도가 있으니, `MaxGear`를
낮추면 더 빠른(높은) 기어로 못 올라가서 자동으로 속도 제한이 걸림.

### 14.2 상태 전환 (`UpdateGear`, 매 틱 `ApplyTrackForces` 전에 호출)
```
DriveMode == Idle                                          → Park
ThrottleInput < -ReverseThrottleThreshold(0.05)             → Reverse
정지 근접(<NeutralSpeedThresholdKmH=1) && Throttle/Steer 둘 다 ~0 → Neutral
그 외                                                        → Gear1~5 (히스테리시스 자동변속)
```
Gear1~5 변속: `UpshiftSpeedFraction`(기본 0.85)만큼 현재 기어 자신의 `MaxSpeedKmH`에
도달하면 상위 기어로, 하위 기어 진입은 그 기어 자신의 upshift 지점보다
`GearHysteresisKmH`(기본 3) 아래로 떨어져야 — 경계에서 매 틱 왔다갔다하는 플리커
방지(`UTargetDetectionComponent`의 Acquire/LoseConfidenceThreshold와 동일한 아이디어).

**Neutral은 의도적으로 아무 힘도/고정력도 안 걺** — 실제 자동차의 N처럼 경사에서
중력 따라 구름. Park(Idle 모드)만 브레이크로 고정됨(17절). 처음엔 Neutral도
고정시켰다가("브레이크 뗐더니 서서히 미끄러짐" 버그로 오인) 사용자가 "N은 원래
굴러가는 게 맞다"고 정정 — 되돌림.

### 14.3 토크 커브 (`ComputeGearForceMagnitude`)
```cpp
TorqueFactor = (1 - SpeedFraction)^TorqueFalloffExponent;   // 기본 지수 3
Force = EngineForceMagnitude * GearTable[i].TorqueMultiplier * TorqueFactor;
```
정지 시(SpeedFraction=0) 풀토크, 그 기어의 `MaxSpeedKmH`에 가까워질수록 토크가
지수형으로 감소(`TorqueFalloffExponent`가 클수록 대부분 구간은 토크 유지하다가
막판에 급격히 떨어짐) — 실제 achieved 최고속도는 항력이 줄어드는 토크를 따라잡는
지점에서 `MaxSpeedKmH`보다 살짝 낮게 형성됨(8.3절과 같은 원리).

**함정 — 절대속도 vs 방향정렬 속도**: 처음엔 `SpeedFraction = Abs(CurrentSpeed) /
MaxSpeedKmH`로 계산했는데, 이러면 40km/h로 전진 중 후진(S)을 걸 때 `Abs(40)/12`(R은
1단 기준 최고속도 12)가 1.0을 훌쩍 넘겨 클램프되어 **토크가 거의 0으로 나와 브레이크
대비 후진 감속력이 10배 이상 약해지는** 버그가 있었음. **해결**: 그 기어의 "자기
방향" 기준으로 부호 있는 속도를 계산하고 0 미만은 0으로 클램프 —
```cpp
GearDirectionSign = (CurrentGear == Reverse) ? -1.f : 1.f;
AlignedSpeedKmH = Max((CurrentSpeed * 0.036f) * GearDirectionSign, 0.f);
SpeedFraction = Clamp(AlignedSpeedKmH / EffectiveMaxSpeedKmH, 0, 1);
```
반대 방향으로 움직이는 중이면 "이미 그 기어 최고속도 초과"가 아니라 "그 기어
방향으로는 아직 0에서 시작"으로 읽혀서 자연스럽게 풀토크. 모든 기어에 공통 적용되는
일반 공식(후진 전용 특례 아님).

### 14.4 대시보드 연동
`FUGVStatusData::GearLabel`(FString, "P"/"R"/"N"/"1".."5") +
`MaxGear`(int32) — `UUGVMovementComponent::GetGearLabel()` →
`AUGVPawn::UpdateUGVStatusData` → `UUGVStatusComponent::SetGearData(GearLabel,
MaxGear)`. `UMonitor1Widget`(활성 대시보드 — `MissionDashboardWidget`은 회귀테스트용
레거시)에 `UGVSpeedText`/`UGVCurrentGearText`/`UGVMaxGearText` 3개 텍스트 위젯
추가(`BindWidgetOptional`).

## 15. 조향력을 엔진 토크에서 분리 (2026-07-12)

**버그**: 조향(A/D)이 `ComputeGearForceMagnitude()`(14.3절, 기어/속도에 따라 변하는
토크 커브)를 그대로 곱해서 썼음 — 저속(토크 풀)에서는 각속도가 과하게 빠르고,
고속(현재 기어 최고속도 근처, 토크가 0에 수렴)에서는 조향이 거의 안 먹는 현상.

**해결**: 조향 전용 고정 힘 `SteerForceMagnitude`(기본 200만) 신설 — 기어/속도와
완전히 무관, 항상 일정. `LeftForce = ThrottleForce - SteerForce`, `RightForce =
ThrottleForce + SteerForce`로 스로틀 힘과 완전히 독립적으로 합산.

## 16. 스로틀 힘 램프 + 방향전환 반동(rubber-band) 방지 (2026-07-12)

**버그 1**: 전진↔후진을 빠르게 왔다갔다하면 관성을 완전히 무시하고 순간적으로 속도가
튀는 느낌. **해결**: `MaxThrottleForceChangeRatePerSecond`(기본 4000만/초)로 실제
적용되는 힘(`SmoothedThrottleForce`)이 목표 힘으로 순간이동하지 않고 서서히
램프업/다운되도록 제한. **조향은 이 램프 대상이 아님** — 즉각 반응 유지(이 프로젝트의
"수동 입력은 항상 즉각적이어야 한다"는 기존 철학과 일치).

**버그 2 (버그 1의 부작용) — "고무줄 반동"**: 램프를 추가하고 나니, 고속(예:
50km/h)으로 전진하다 후진을 걸면 감속은 부드러운데, **정확히 0을 통과해서 실제
후진이 시작되는 순간 원래 전진 속도에 비례해서 확 튕겨나가는** 현상 발생. 원인:
14.3절의 방향정렬 속도 계산상 "전진 중에는 속도가 얼마든 반대방향으로 취급 → 목표
힘이 항상 풀토크로 고정" → 감속에 걸리는 시간이 길수록(원래 속도가 빠를수록)
램프가 그 풀토크를 향해 그만큼 더 오래 쌓임 → 실제로 방향이 바뀌는 순간 그 쌓인
큰 힘이 새 방향에 그대로 얹힘.

**해결**: 실제 속도의 부호가 뒤바뀌는 순간을 감지해서 그 시점에 램프값을 0으로
리셋:
```cpp
// PreviousSpeedSign 멤버로 프레임 간 부호 추적, 5cm/s 데드존으로 노이즈 방지
if (CurrentSpeedSign != 0 && PreviousSpeedSign != 0 && CurrentSpeedSign != PreviousSpeedSign)
    SmoothedThrottleForce = 0.f;
```
"아직 감속(브레이크처럼 작동) 중"과 "이제 진짜 반대 방향으로 새로 가속 시작"을
구분해서, 후자는 항상 0부터 다시 시작 — 감속 단계에서 쌓인 힘이 가속 단계로
새어나가지 않음.

## 17. 브레이크 — 마찰력(Coulomb friction) 기반으로 전면 재작성 (2026-07-12)

**버그**: 기존 브레이크는 매 틱 `FMath::Sign(현재속도)` 방향으로
`BrakeForceMagnitude`(고정값)를 그대로 꽂는 On/Off 방식이었음 — 경사에 정지해있으면
중력이 미세하게 미는 속도조차 매 틱 최대 힘으로 반대로 튕겨내면서 격렬하게
떨리는(bang-bang 진동) 현상 발생.

**해결 — 인위적 힘 대신 실제 마찰력을 올림**: 8.4절에서 만든 트랜지언트
`PhysicalMaterial` 스위칭 메커니즘을 재사용해서, 평소 주행용 저마찰
`GroundContactMaterial`과 별도로 고마찰 `BrakeContactMaterial`(`BrakeFriction`,
기본 1.75)을 만들고, `bBraking`이 바뀌는 **전환 시점에만**(매 틱 아님)
`BodyInstance.SetPhysMaterialOverride()`로 교체. 감속과 정지 유지 둘 다 물리
엔진의 접촉 솔버가 처리 — 인위적인 `AddForceAtLocation` 없음, 그래서 진동도
원천적으로 없음.

**정지마찰(Coulomb friction)의 물리적 성질이 정확히 원하는 동작과 일치**: 버틸 수
있는 최대 경사각은 `atan(BrakeFriction)`로 결정됨 — 즉 웬만한 경사에서는 완전히
정지, 아주 가파른 경사에서만 자연스럽게 미끄러짐. `FrictionCombineMode`는 평소
주행용과 동일하게 **Min 유지**(낮은 쪽이 이김) — 물리적으로 이게 정석(빙판 위에서는
브레이크를 걸어도 미끄러지는 게 현실적)이고, 지금 프로젝트엔 어차피 지형에 별도
`PhysicalMaterial`이 지정된 게 없어서 경쟁 상대가 없는 상태라 Max로 바꿀 실익도
없음.

기존 `BrakeForceMagnitude` 프로퍼티는 완전히 제거됨(대체된 게 아니라 이 방식 자체가
다른 메커니즘이라 새 값 `BrakeFriction`으로 대체).

## 18. 질량 3톤 확정 + 물리 파라미터 재튜닝 (2026-07-12)

8절 도입 당시 15톤은 placeholder였음 — **3톤으로 확정**, 사용자가 에디터에서 직접
테스트하며 아래 값들을 재튜닝하고 저장. 실제 배치된 `BP_UGV` 인스턴스에서 MCP로 값을
읽어와 C++ 기본값도 동일하게 반영(향후 새 인스턴스나 리셋 시에도 이 값에서 시작하도록):

| 값 | 기존(15톤 기준) | 신규(3톤, 2026-07-12) |
|---|---|---|
| `EngineForceMagnitude` | 200만 | **400만** |
| `AirResistanceCoefficient` | 7.8 | **0.01** |
| `GroundFriction` | 0.15 | **0.01** |
| `OffRoadAirResistanceMultiplier` | 3 | **10** |
| `OffRoadTopSpeedMultiplier` | 0.6 | **1**(비활성화 — 저항 배율만으로 온/오프로드 차등 충분하다고 판단) |
| `UpshiftSpeedFraction` | 0.9 | **0.85** |
| `GearTable`(1~5단, 속도km/h·토크배수) | 12·1.0 / 24·0.85 / 38·0.7 / 55·0.55 / 75·0.45 | **12·5.0 / 24·2.5 / 36·1.67 / 48·1.25 / 60·1.0** |

`SteerForceMagnitude`/`TrackOffset`/`TrackLengthOffset`/`LateralGripStrength`/
`OffRoadSpeedDecayPerTick`/`TorqueFalloffExponent`/`GearHysteresisKmH`/`MaxGear`는
15톤 기준 기본값과 이미 동일해서 안 건드림. `BodyMesh->SetMassOverrideInKg`도
15000 → 3000으로 수정.

