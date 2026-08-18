# 리플리케이션 준비도 감사 (1단계: 조사) + 구현 현황

- 조사일: 2026-08-06 (최초 조사) / **2026-08-13 최신화 — 아래 §0-1 참고**
- 대상: `titan_example` (UE5.8), 레벨 `/Game/kadex_demo_0716` (+ 이후 `kadex_lobby`/`kadex_test` 추가)
- 방법: Unreal MCP(에디터 도구)로 레벨/액터/클래스 프로퍼티 조회 + `Source/titan_example` C++ 전수
  grep/read. **§0~7은 최초 조사(2026-08-06) 당시 "코드/레벨 수정 없이 순수 조사" 스냅샷이라 지금은
  상당 부분 옛날 얘기임 — 실제 구현 현황은 §8을 우선 참고.**
- 참고 설계 문서: `architecture_decisions.md` §1(Layer C), 특히 §1.3 리플리케이션 대상 목록.

## 0-1. 2026-08-14 기준 현황 요약 (§8 체크박스 상세는 아래 참고)

리슨서버 멀티플레이(UGV PC=호스트, SelfDefense PC=클라이언트) 전환이 사실상 완료됨:

- **완료**: 기반 플러밍(축 판별 접속/GameMode/GameState/PlayerController possess 흐름), RCWS(UGV+Truck)
  상태·조작권한·발사 이펙트 리플리케이션, 아군/적군 45명 전투 컴포넌트 Tick 서버 전용화 +
  Blueprint 자세/애니메이션 변수 리플리케이션, 시나리오 진행 상태(GameState) + 시나리오 트리거
  Server RPC 전환, **투사체 명중 판정 서버 권위화(데미지 + 명중 이펙트/사운드 전부 서버가 확정해서
  위치 기반 Multicast로 재생, RCWS/아군/적군 공통)**, **UAV(`AUAVPawn`) 미션 물리 + 짐벌/줌
  리플리케이션**, **UGV 구동(`AUGVAIController::Tick` 서버 전용화 + `UUGVStatusComponent`
  대시보드 데이터 리플리케이션 + 수동조작 입력 서버 권위 게이팅, §8 UGV 섹션 참고)**.
- **의도적으로 안 한 것(정석 검토 후 현재 방식이 낫다고 판단)**: 투사체 궤적 자체의 액터
  리플리케이션 — 빠른 소형 오브젝트라 표준 위치 리플리케이션 특유의 끊김이 오히려 더 눈에 띌
  위험이 있어서, 지금처럼 "각 프로세스가 결정론적으로 로컬 재생 + 판정만 서버 권위" 방식을 유지.
  히트스캔 전환도 동일한 이유로 보류(사용자 확정, 2026-08-13).
- **아직 안 한 것 / 미해결**: `physicsReplicationMode` 조회/설정 실패(정확한 프로퍼티 이름을 MCP로
  못 찾음 — 기본값 `Default`로 방치, 클라이언트 화면에서 UGV 움직임 끊김이 체감되면 에디터에서
  직접 확인 필요), RCWS pan/tilt 클라이언트 예측(지금은 서버 왕복 RPC 방식), 아군 `CurrentEnemy` 오브젝트
  레퍼런스 리플리케이션 자체의 원인 불명 버그(우회만 함, §8 RCWS/발사 섹션 참고), **UAV 카메라 줌
  버튼(`SelfDefenseDashboardWidget` 추정)의 Server RPC 라우팅 미확인 — 클라이언트에서 이 버튼이
  조용히 안 먹을 가능성 있음, 실기 테스트로 확인 필요(§8 UAV 섹션 참고)**.

## 0. 한눈에 보기 (TL;DR, 2026-08-06 최초 조사 당시 스냅샷 — 지금은 대부분 해소됨, §0-1/§8 참고)

- **리플리케이션 관련 코드가 프로젝트 전체에 사실상 전무함.** `Source/titan_example` 전체를
  `GetLifetimeReplicatedProps`/`DOREPLIFETIME`/`SetIsReplicated`/`bReplicates =`/`HasAuthority`/
  `Server_`/`NetMulticast` 등으로 grep해도 **단 한 건도 없음**. 지금 켜져 있는 리플리케이션은
  전부 UE 기본값(`APawn`/`ACharacter`의 `bReplicates=true`, `bReplicateMovement=true`)이고,
  커스텀 게임플레이 상태(RCWS 발사/탄약/조준모드, UGV 기어/속도, 시나리오 진행 등)는 전부
  로컬에서만 존재.
- **[정정 — 최초 조사에서 잘못 판단했던 부분]** 레벨에 배치된 실제 UGV(`BP_UGV_Vehicle_C_1`)는
  MCP로 클래스 계보를 재확인한 결과 **`AWheeledVehiclePawn`(Chaos Vehicle) 직계 서브클래스이고,
  `VehicleMovementComponent`도 실제로 `ChaosVehicleMovementComponent`**임 — 설계 문서(§1.3)의
  "Chaos Vehicle" 전제와 **일치**. (최초 보고서는 `AUGVPawn`/`UUGVMovementComponent`(힘-기반
  커스텀 컴포넌트, `UFloatingPawnMovement` 상속)가 실제 구동부라고 썼는데, 이는 헤더 주석만 보고
  넘겨짚은 오판이었음 — 사용자 확인: 그 힘-기반 컴포넌트는 **임시로 만든 것으로 삭제 예정**.
  `search_subclasses`로 재검증: `BP_UGV_Vehicle_C`는 `AUGVPawn`의 서브클래스가 아니며,
  `AWheeledVehiclePawn`의 서브클래스임.) 실제 구동 로직은 §3에서 설명하는 대로
  `AUGVAIController`의 Chaos 전용 pursuit 경로(`UpdateChaosPursuit`)를 탄다 — `UUGVMovementComponent::
  RequestDirectMove`가 아님. `AUGVPawn`/`UUGVMovementComponent`(레벨 미배치, 삭제 예정)와 별개로,
  네이티브 프로토타입 `AUGVChaosPawn`(`Vehicles/UGVChaosPawn.h`, 16휠 스켈레탈 메시 전제)도
  존재하지만 이 역시 레벨 미배치 — `BP_UGV_Vehicle`은 이 둘 중 어느 쪽도 아니고 **자체적으로
  `AWheeledVehiclePawn`을 바로 상속한 블루프린트 전용 구현**(트랙 링크/스플라인/새깅 등 궤도
  비주얼까지 자체 구현)이라는 점에 유의(§1, §3).
- **가장 심각한 두 개의 구조적 블로커** (§3, §6에 상세):
  1. `ATitanTruck::BeginPlay`가 `UGameplayStatics::GetPlayerController(this, 0)->Possess(this)`로
     자기 자신을 하드코딩 possess — 리슨서버에서 두 프로세스 모두에 이 코드가 그대로 실행되면
     클라이언트가 권한 없이 `Possess`를 호출하는 상황이 됨.
  2. `AUGVAIController::IsLocalController()`가 `return true`로 하드코딩 오버라이드돼 있고, 그
     사유가 클래스 헤더에 "이건 네트워킹 없는 싱글플레이 게임이라 항상 true가 맞다"로 명시돼
     있음 — 리플리케이션 도입 시 반드시 재검토/제거 필요한 지점으로 코드에 이미 마킹돼 있음.
     **이 컨트롤러가 실제로 지금 배치된 UGV(`BP_UGV_Vehicle_C_1`)를 그대로 조종하고 있으므로,
     이건 "언젠가"가 아니라 지금 바로 유효한 블로커.**
- 레벨의 아군/적군/차량 배치 수는 설계 문서와 일치: 아군 30 + 적군 15 = 45명, UGV 1, TitanTruck
  1, UAV 1 (§1).
- 스폰 시스템(`UScenarioStateSubsystem`)은 `UGameInstanceSubsystem` — **프로세스(=PC)마다 별도
  인스턴스**이고 서버 권한 체크가 전혀 없음. 45명은 런타임에 스폰되는 게 아니라 **전부 레벨에
  사전 배치**돼 있음 — "스폰 시스템"이라기보다 "사전 배치된 액터들에 대한 로컬 상태 브로드캐스트
  시스템"에 가까움(§5).

---

## 1. 레벨 배치 액터 전수 조사

`find_actors` (Unreal MCP `SceneTools`)로 레벨 `/Game/kadex_demo_0716` 전체 액터 조회 + 이름/클래스
필터로 세부 확인.

| 분류 | 클래스(배치된 것) | 개수 | 인스턴스 라벨 | bReplicates | bReplicateMovement | AutoPossessAI |
|---|---|---|---|---|---|---|
| 아군 | `BP_Ally_kadex_C` | 30 | `BP_Ally_kadex_C_2`~`_31` | true | true | PlacedInWorld |
| 적군 | `BP_Enemy_kadex_C` | 15 | `BP_Enemy_kadex_C_4`~`_18`, `_9`~ 등 | true | true | PlacedInWorldOrSpawned |
| UGV | `BP_UGV_Vehicle_C` (`AWheeledVehiclePawn`/Chaos Vehicle 직계, `VehicleMovementComponent`=`ChaosVehicleMovementComponent`) | 1 | `BP_UGV_Vehicle_C_1` | true | true | PlacedInWorld (AIControllerClass=`BP_UGVAIController`) |
| 자체방호(트럭) | `BP_TitanTruck_C` (`ATitanTruck`) | 1 | `BP_TitanTruck_C_2` | true | true | PlacedInWorld (AIControllerClass 미지정 → 엔진 기본 `AAIController`) |
| UAV | `BP_UAV_C` (`AUAVPawn`) | 1 | `BP_UAV_C_1` | (미확인, 아래 질문 참고) | — | — |

- **아군/적군 45명 = 설계 문서 §1.3의 "45명" 수치와 정확히 일치.** 전부 `bReplicates`/
  `bReplicateMovement`가 `true`인 상태 — 단, 이건 `ACharacter`의 **엔진 기본값**이지 프로젝트가
  의도적으로 세팅한 게 아님(둘 다 인스턴스 오버라이드 없이 클래스 기본값 그대로). AI 컨트롤러도
  커스텀 없이 엔진 기본 `AAIController` 사용.
- **UGV는 1대만 배치**돼 있고, 클래스는 `BP_UGV_Vehicle`(부모 `AWheeledVehiclePawn`, Chaos
  Vehicle) — `list_properties`로 확인한 서브오브젝트에 `vehicleMovementComponent`
  (`ChaosVehicleMovementComponent`), `mesh`(SkeletalMeshComponent), 좌우 `trackLinks_L/R`
  (InstancedStaticMeshComponent) + `trackPath_L/R`(SplineComponent) + 다수의 track-sag 시뮬레이션
  변수(`trackSagCurrentL/R`, `trackWhipOffset` 등, 궤도 처짐을 코스메틱하게 표현하는 자체 로직으로
  보임) 확인됨. RCWS/RCWSFireControl/TargetDetection/DetectableTarget/UGVStatus/
  VehicleEngineAudio 등 §2에서 다룬 컴포넌트들도 전부 이 액터에 붙어 있음. `physicsReplicationMode`
  프로퍼티(UE5.8 Chaos 물리 리플리케이션 모드 — Default/PredictiveInterpolation/Resimulation/None)가
  존재하는 것도 확인했으나 **현재 값은 `Default`(엔진 기본값, 멀티플레이용으로 검토/설정된 흔적
  없음)**.
  - 참고로 코드베이스엔 UGV 관련 클래스가 이 외에도 여럿 있으나 **전부 미배치**: `AUGVPawn`
    (+ `UUGVMovementComponent`, 힘-기반 커스텀 구동 — **사용자 확인: 임시 구현, 삭제 예정**),
    네이티브 프로토타입 `AUGVChaosPawn`(16휠 스켈레탈 메시 전제, 클래스 주석에 "AUGVPawn을
    대체하는 게 아니라 병렬로 도는 프로토타입"이라 명시), `UGV_OLD` 폴더의 `BP_UGV`/
    `BP_UGV_wheeled`/`BP_UGVChaosPawn`/`BP_UGVFromTank` — 전부 레거시/실험 흔적. **실제 리플리케이션
    감사·설계 대상은 오직 `BP_UGV_Vehicle`(현재 배치본) 하나로 좁혀도 됨.**
- **TitanTruck은 AIControllerClass 미지정 + AutoPossessAI=PlacedInWorld** → BeginPlay 시점에
  엔진이 먼저 기본 `AAIController`로 auto-possess한 뒤, `ATitanTruck::BeginPlay`가 곧바로
  `PlayerController(0)`로 재-possess하는 흐름(§3 참고). 의도적으로 그렇게 짠 것인지, 단순히
  AutoPossessAI를 꺼두지 않은 것인지는 확인 필요(질문 목록 Q1).
- RCWS는 **별도 액터가 아니라 TitanTruck/UGV pawn에 붙은 컴포넌트**(`URCWSComponent` +
  `URCWSFireControlComponent`)라 액터 리플리케이션 목록엔 안 잡힘 — 설계 문서 §1.3의 "RCWS 발사는
  액터 리플리케이션 안 함, 히트스캔+Multicast RPC" 방향과 일치하는 배치. 다만 현재 발사체
  (`ARCWSProjectile`)는 히트스캔이 아니라 **실제로 날아가는 풀링된 Actor**이고(§2), 그 자체가
  bReplicates 관련 코드 없이 로컬 전용으로 스폰/이동함.
- 그 외 다수의 `DatasmithSceneActor`, `RoadNavMod`(148개, NavMesh 도로 스트립), `TargetPoint` 등은
  전부 정적 레벨 지오메트리/네비게이션 보조 액터로 리플리케이션 감사 범위 밖(정적 레벨 콘텐츠는
  서버/클라이언트 양쪽에 동일하게 로드되므로 별도 처리 불필요).

---

## 2. RCWSComponent / RCWSFireControlComponent

**지금 상태**: 완전히 로컬 전용. 아래 항목 전부 프로젝트 전체 grep(`SetIsReplicated`,
`GetLifetimeReplicatedProps`, `DOREPLIFETIME`, `HasAuthority`, `Server_`/`_Server`,
`NetMulticast`)에서 **0건**.

- `URCWSComponent` (`Vehicles/RCWSComponent.h`): 생성자에서 `SetIsReplicated`류 호출 없음(=
  `UActorComponent` 기본값인 `bReplicates=false` 그대로). `AddPanTiltInput`/`AddZoomInput`/
  `SetLoaded`/`SetFireReady`/`SetCameraMode`/`SetFireMode` 전부 그냥 `UFUNCTION(BlueprintCallable)`
  — Server/Client/NetMulticast 지정 없음, 즉 **호출한 그 프로세스에서만 실행되고 다른 쪽엔 전혀
  전파 안 됨**. 상태 저장용 `FRCWSStatusData CurrentData`(탄약/조준모드/줌 등)도 `Replicated`
  UPROPERTY가 아니라 그냥 private 멤버.
- `URCWSFireControlComponent` (`Vehicles/RCWSFireControlComponent.h`): `CurrentMode`
  (`ERCWSControlMode` — Remote/AutoSurveillance/AutoAim/AutoFire), `bIsLockedOn`,
  `CurrentAutoAimTarget` 등 조준/교전의 핵심 상태가 전부 `Transient` UPROPERTY일 뿐 리플리케이션
  대상이 아님. `Fire()`(발사 실행), `SetControlMode`/`CycleControlModeNext` 등 조작 함수도 전부
  로컬 실행 — 호출부(`titan_examplePlayerController::DoManualFireStarted` 등)도 로컬 함수 호출로만
  연결돼 있고 서버 RPC 경유 없음.
- **`ARCWSProjectile`(발사체)도 로컬 전용**: `URCWSFireControlComponent::Fire()`가 풀에서 꺼내
  `LaunchFrom()`으로 직접 발사 — 설계 문서(§1.3) "히트스캔 + Multicast RPC" 방향과 다르게, 지금은
  **실제로 날아가는 Actor를 각 프로세스가 로컬로 스폰/시뮬레이션**하는 구조. 발사 판정
  (`UProjectileMovementComponent` 기반 포물선 + `OnHit`)도 전부 로컬.
- **탐지(Detection) 쪽도 동일**: `Detection/` 폴더 전체 grep에서도 리플리케이션 관련 코드 0건.
  `UTargetDetectionComponent`(RCWS의 표적 탐지)가 완전히 로컬 계산이라, 서버/클라이언트가 각자
  독립적으로 "누가 가장 가까운 적인가"를 계산 — 리슨서버 환경에서 두 프로세스의 탐지 결과가
  갈리면(예: 미세한 시뮬레이션 오차, 틱 타이밍 차이) 자동조준/자동사격 판단이 서로 달라질 수 있음.

**리플리케이션 되려면 뭘 고쳐야 하는지** (설계 문서 §1.3 방향 기준):
- `CurrentMode`/`bIsLockedOn`/탄약(`AmmoCurrent`)/`ZoomLevel` 등 "다른 쪽 화면에도 보여야 하는
  상태"를 `Replicated` + `OnRep_*`로 전환.
- `SetManualFireHeld`/`Fire()` 트리거 경로를 서버 권위로 이동 — 클라이언트 입력은 `Server_Fire`류
  RPC로 서버에 전달, 실제 판정(탄착점 계산)은 서버가 수행.
- 발사 결과(탄착 위치/명중 여부/트레이서 표시)는 액터 리플리케이션이 아니라 `NetMulticast RPC`로
  각 클라이언트에 뿌려 로컬로 이펙트만 재생 — 지금의 `ARCWSProjectile` 풀링 방식 자체를 히트스캔
  판정 + 화면 연출용 로컬 트레이서로 재설계해야 함(설계 문서가 이미 명시한 방향).
- 자동조준/자동사격의 표적 선정(`SelectNearestEnemyTarget`)은 서버에서만 수행하고 결과(락온 대상/
  상태)만 클라이언트로 리플리케이트 — 클라이언트가 각자 계산하게 두면 안 됨.

---

## 3. UGVMovementComponent / UGVAIController (+ TitanTruck 구동)

> **[정정 안내]** 이 섹션은 최초 조사에서 "실제 배치된 UGV = `AUGVPawn` + 힘-기반
> `UUGVMovementComponent`"라고 잘못 판단하고 썼던 내용을 사용자 확인(2026-08-06)에 따라 다시 쓴
> 버전임. 실제 배치된 UGV(`BP_UGV_Vehicle_C_1`)는 **`AWheeledVehiclePawn`(Chaos Vehicle) 직계
> 서브클래스**이고, `UUGVMovementComponent`(및 그걸 쓰는 `AUGVPawn`)는 **임시 구현이라 삭제
> 예정**인 코드임(§1 참고). 아래는 이 정정된 이해를 기준으로 다시 정리한 내용.

**지금 상태**:

- **실제 UGV 구동 = Chaos Vehicle(`ChaosVehicleMovementComponent`), 조작 로직은
  `AUGVAIController`의 Chaos 전용 경로.** `AUGVAIController.h` 107~124행 클래스 코멘트에 이미
  명시돼 있는 설계: "`AUGVPawn`의 `UUGVMovementComponent::RequestDirectMove`는 네이티브
  `NavMovementComponent` 훅이라 Chaos Vehicle엔 없음(`UChaosVehicleMovementComponent`/
  `UChaosWheeledVehicleMovementComponent` 둘 다 확인함) → 그래서 이 컨트롤러의 `Tick` 기반
  경로(`UpdateChaosPursuit`)가 그 대체"라고 직접 적혀 있음 — 이게 지금 실제로 쓰이는 경로.
  `UpdateChaosPursuit`은 `FindChaosLookaheadTarget`으로 pure-pursuit 목표점을 구한 뒤,
  **리플렉션**(`FindFunction`/`ProcessEvent`)으로 폰의 `SetManualControl(float, float)` 함수를
  찾아 호출하는 방식(`DispatchSetManualControl`, C++ 인터페이스가 아니라 이름/시그니처 규약).
  `BP_UGV_Vehicle`이 이 규약에 맞는 `SetManualControl` 함수를 자체 구현하고 있을 것으로 보이나,
  블루프린트 그래프 내부까지는 이번 조사에서 열어보지 않음(질문 목록 Q2 참고).
- `AUGVAIController`엔 `HasAuthority`/`Server_`/`NetMulticast` 패턴이 전혀 없음(grep 0건) —
  `UpdateChaosPursuit`/`UpdateRoadBoundary`/`UpdateOffRoadSpeedDecay` 등 매 틱 로직이 전부 로컬
  실행. 이 컨트롤러가 possess한 프로세스(지금은 사실상 항상 로컬 싱글플레이라 자기 자신)에서
  물리 입력을 직접 던지는 구조라, 리슨서버가 되면 "이 로직이 서버에서만 돌아야 하는지"가
  명시적으로 정해져 있지 않음.
- Chaos Vehicle 자체는 UE5.8 엔진이 `physicsReplicationMode`(Default/PredictiveInterpolation/
  Resimulation/None) 같은 네트워크 물리 리플리케이션 옵션을 기본 제공하지만(§1에서 확인,
  현재 `Default`), **이건 서버가 액터의 물리를 시뮬레이션하고 클라이언트에 전파하는 것을
  전제로 한 옵션** — 지금처럼 `AUGVAIController::IsLocalController()`가 무조건 `true`를
  반환하는 상태로는 "서버 권위 시뮬레이션 + 클라이언트 보정"이라는 이 옵션들의 전제 자체가
  성립하지 않음(바로 아래 항목).
- **`AUGVAIController`가 `AAIController`가 아니라 `APlayerController`를 상속**(`UGVAIController.h`
  1~28행 클래스 코멘트에 사유 명시: BP_Tank의 `ReceivePossessed`가 `APlayerController` 캐스트
  성공을 요구해서 우회한 것). 이 자체가 향후 리플리케이션 설계에서 "AI가 조종하는 폰의 컨트롤러가
  실제로는 PlayerController 취급을 받는다"는 특이 케이스를 만듦 — `APlayerController`는 보통
  `OwningConnection` 등 네트워크 커넥션과 강하게 엮인 클래스라, 실제 플레이어가 없는 "headless
  bot"으로 계속 써도 되는지 재검토 필요.
- **`AUGVAIController::IsLocalController() const override { return true; }`** —
  `UGVAIController.h` 289~307행에 사유가 직접 적혀 있음: 엔진의 `APlayerController::
  IsLocalController()`가 `GetNetDriver()==nullptr && ULocalPlayer 없음`이면 false를 반환하는데,
  Chaos Vehicle 관련 로직이 이 값에 따라 로컬 시뮬레이션 여부를 결정하는 것으로 보여서
  "**이건 네트워킹 없는 싱글플레이 게임이라 항상 true가 맞음**"이라는 근거로 강제 오버라이드.
  **리슨서버 두 프로세스 환경이 되면 이 가정이 깨짐** — 두 프로세스 모두에서 "로컬"이라고
  응답하게 되므로, 클라이언트 쪽에서도 이 컨트롤러가 자기 로컬 시뮬레이션 권한이 있다고
  오판할 수 있음. 코드 자체에 "diagnostic 성격, root-cause 확인되면 재검토" 뉘앙스가 있어 이미
  기술 부채로 인지되고 있던 지점으로 보임.
- `ATitanTruck` 자체 조향/주행 기능 없음(설계 문서 §1.2와 일치, 확인됨) — 카메라/RCWS만 있음.
  단, **`ATitanTruck::BeginPlay`(TitanTruck.cpp 90~97행)가
  `UGameplayStatics::GetPlayerController(this, 0)->Possess(this)`를 호출** — "Player 0"을
  하드코딩. 리슨서버에서 이 액터가 서버(UGV PC)와 클라이언트(자체방호 PC) 양쪽 프로세스에
  동일하게 존재/BeginPlay가 실행되면:
  - 서버 프로세스에서 `GetPlayerController(this, 0)`은 서버의 로컬 플레이어(보통 호스트 자신).
  - 클라이언트 프로세스에서도 이 코드가 그대로 실행되면 클라이언트의 로컬
    `APlayerController`가 `Possess()`를 호출하게 되는데, **`AController::Possess()`는 서버
    권위 하에서만 유효한 동작**이라 클라이언트에서 호출 시 정상 동작 보장 안 됨(엔진 버전에 따라
    경고 로그만 찍고 무시되거나, 애초에 클라이언트가 소유하지 않은 액터라 아예 씹힐 가능성).
    자체방호 PC가 자기 트럭을 실제로 조종하려면 이 로직 자체를 "그 PC의 로컬 플레이어가 자기
    쪽 TitanTruck 인스턴스를 조종한다"는 네트워크 인지 방식으로 다시 짜야 함.

**리플리케이션 되려면 뭘 고쳐야 하는지**:
- `AUGVAIController::IsLocalController()`의 하드코딩 오버라이드 제거(또는 네트워크 모드 인지
  분기 추가)가 최우선 — 지금 실제로 배치된 Chaos Vehicle UGV를 이 컨트롤러가 직접 조종하고
  있으므로, 이 오버라이드가 왜 필요했는지(엔진 소스 확인 결과는 "Chaos Vehicle의 로컬-시뮬레이션
  게이팅이 `IsLocallyControlled()`를 본다"는 것) 원인을 먼저 재확인한 뒤, 리슨서버 환경에서
  서버만 물리 권위를 갖도록 재설계 필요.
- `ATitanTruck::BeginPlay`의 `GetPlayerController(this, 0)->Possess(this)`를 제거하고, 각 PC의
  로컬 플레이어가 접속 시점에 "자기 축(UGV/자체방호)에 해당하는 차량"을 서버 RPC 또는
  GameMode의 `RestartPlayer`/`Login` 경로로 정상 possess하도록 변경.
- Chaos Vehicle의 `physicsReplicationMode`를 `Default`가 아니라 (탱크처럼 무겁고 저속인 궤도
  차량 특성에 맞는) 적절한 모드로 명시적으로 검토/설정 — `PredictiveInterpolation`/
  `Resimulation` 중 어느 쪽이 이 프로젝트의 요구(초저지연보다는 시각적 안정성이 더 중요해
  보임)에 맞는지 판단 필요.
- `AUGVAIController`의 `UpdateChaosPursuit`/`SetDriveMode`/`MoveToDestination` 등 매 틱·명령
  경로를 서버 전용(`HasAuthority()` 게이팅)으로 명시하고, `DriveMode`/`CurrentGear`류 UI 노출
  상태는 `Replicated`+`OnRep`로 클라이언트에 전파.
- `AUGVMovementComponent`/`AUGVPawn`(삭제 예정)은 이번 리플리케이션 작업 범위에서 제외 — 계속
  유지보수하며 리플리케이션을 붙일 필요 없음.

---

## 4. titan_examplePlayerController

**지금 상태**: 완전히 "로컬 입력 → 로컬 함수 직접 호출" 패턴. `titan_examplePlayerController.cpp`
전체에서 Server RPC 패턴(`_Server`, `Server_`, `NetMulticast`) grep 0건.

- `DoCameraLook`/`DoUGVMove`/`DoManualFireStarted`/`DoRCWSModeNext` 등 입력 핸들러가 전부
  `GetActorOfClass`로 대상 액터를 즉석에서 찾아 그 위의 컴포넌트 함수를 **직접 호출**
  (`ResolveActiveFireControl()->CycleControlModeNext()` 등) — 소유 클라이언트 로컬 실행을
  전제로 짜여 있고, 서버로 전달하는 경로 자체가 없음.
- `NextVehicle`/`PossessTitanTruck`/`PossessUGV`/`SetUGVMode`/`SetRCWSMode`/
  `BeginAllyFormUpAndAdvance` 등 **`UFUNCTION(Exec)` 콘솔 커맨드가 대량으로 존재**하고, 전부
  같은 방식(로컬에서 액터 찾아 직접 함수 호출)으로 동작. `Exec` 함수는 입력을 받은 그
  PlayerController가 있는 프로세스에서 로컬로 실행되는 게 기본이라, 리슨서버에서 클라이언트가
  이 커맨드를 치면 서버 상태에 반영되지 않음.
- `Possess()`를 직접 호출하는 `PossessTitanTruck`/`PossessUGV`/`PossessUGVChaos`/
  `PossessUGVFromTank`도 전부 로컬에서 즉시 호출 — 3번 항목의 `ATitanTruck::BeginPlay`와 같은
  문제(서버 권위 밖에서의 `Possess()` 호출) 소지가 있음.
- 카메라/오디오 리스너 타겟(`CameraControlTarget`/`AudioListenerTarget`) 등은 UI 표시용 로컬
  상태라 리플리케이션 필요성은 낮아 보이나(각 PC가 자기 화면만 신경 쓰면 됨), RCWS 모드 전환
  (`SyncRCWSControlModeForCameraTarget`)은 위 §2의 `CurrentMode`와 맞물려 있어서 결국 서버 권위로
  옮겨야 함.

**리플리케이션 되려면 뭘 고쳐야 하는지**:
- 게임플레이에 영향을 주는 입력(발사, RCWS 모드 전환, UGV 드라이브 모드, 시나리오 트리거 계열
  Exec 커맨드)은 "로컬 함수 직접 호출"에서 "서버 RPC 호출 → 서버가 실제 상태 변경 →
  리플리케이트/멀티캐스트로 결과 전파" 패턴으로 전환 필요.
- 반대로 카메라 look 입력(`DoCameraLook`)처럼 "내가 조종하는 RCWS를 내 화면에서 바로 반응시켜야
  하는" 것들은 클라이언트 예측(로컬 즉시 적용) + 서버에는 별도로 최종 각도만 동기화하는 구조가
  적합해 보임 — 매 프레임 조준 입력을 전부 RPC로 보내면 과도한 트래픽이 될 수 있음(설계
  판단 필요, 질문 목록 Q4).
- `PossessTitanTruck`/`PossessUGV`류는 "자기 PC가 담당하는 차량만 possess 가능"하도록
  서버 권위 체크(+ 어느 PC가 어느 차량 축인지 식별하는 로직)를 추가해야 함 — 지금은 아무 클라도
  아무 차량이나 즉시 possess 시도 가능한 상태.

---

## 5. 스폰 시스템 (`UScenarioStateSubsystem` 등)

**지금 상태**: 이름과 달리 "런타임 액터 스폰" 시스템이 아니라 **"레벨에 이미 사전 배치된 45명
액터들에게 상태 전환을 브로드캐스트하는 시스템"**에 가까움 — §1에서 확인했듯 아군/적군 45명은
`find_actors`로 전부 레벨에 정적으로 배치돼 있는 게 확인됨(런타임 `SpawnActor` 흔적 없음).
프로젝트 내 유일한 "스포너"류 클래스인 `CombatEnemySpawner`는 엔진 템플릿의 `Variant_Combat`
데모 콘텐츠 소속이고, 이 프로젝트의 `BP_Ally_kadex`/`BP_Enemy_kadex`/시나리오 로직과는 연결점이
전혀 없음(grep 확인) — 즉 **실질적으로 미사용 코드**.

- `UScenarioStateSubsystem`은 `UGameInstanceSubsystem` — **`UGameInstance`는 프로세스(=PC)마다
  하나씩**이라, 리슨서버 두 프로세스 환경에서는 **서버와 클라이언트가 각자 독립적인 인스턴스를
  가짐**. 서로 자동으로 동기화되지 않음(엔진이 대신 해주는 게 아니라, 명시적으로 리플리케이트할
  데이터/RPC를 만들어야 함).
- `RegisterAlly`/`UnregisterAlly`가 컴포넌트 포인터를 로컬 배열(`RegisteredAllies`)에 등록하는
  로컬 레지스트리 패턴 — 서버에서 등록된 아군 목록과 클라이언트에서 등록된 아군 목록이 각자
  따로 존재.
- `BeginAllyFormUp`/`BeginAllyFollowing`/`BeginAllyApproach`/`BeginAllyAmbush` 등 시나리오 단계
  전환 함수들이 `HasAuthority` 체크 없이 호출된 프로세스에서 곧바로 로컬 브로드캐스트
  (`RegisteredAllies` 순회하며 각 컴포넌트에 직접 함수 호출) — 서버 전용으로 제한돼 있지 않고,
  **어느 프로세스에서 호출해도(현재는 `titan_examplePlayerController`의 Exec 커맨드를 통해서만
  호출되긴 함) 그 프로세스 안에서는 즉시 실행됨**.
- 타이머(`FTimerManager`)도 로컬 — `BeginScenarioSteps`/`TickScenarioSteps`의 스텝 진행 판정
  (`DT_ScenarioSteps` 데이터테이블 기반)이 전부 그 프로세스의 로컬 시간 기준으로 동작.
- UGV를 NavMesh 장애물로 등록하는 `AddUGVNavObstacle`(`UNavModifierComponent` 동적 부착)도
  로컬 전용 — NavMesh 자체가 각 프로세스에서 독립적으로 빌드되는 구조라, 서버/클라이언트의
  아군 경로가 미세하게 달라질 수 있음.

**리플리케이션 되려면 뭘 고쳐야 하는지**:
- 시나리오 진행 상태(현재 어느 단계인지, 어느 스텝이 발동됐는지)를 **서버가 유일한 권위자**로
  갖고, 클라이언트는 그 상태를 구독만 하는 구조로 재설계 필요 — 예: 서버 전용
  `AGameStateBase` 서브클래스나 리플리케이트되는 액터에 시나리오 상태를 옮기고,
  `UScenarioStateSubsystem`은 그 상태를 읽어 로컬 연출(수신호 몽타주 재생 등 각 클라이언트에서
  보여지기만 하면 되는 것)만 담당하도록 역할 분리.
- `BeginAllyFormUpAndAdvance` 등 시나리오 트리거 Exec 커맨드는 **서버에서만 실제 상태를 바꾸도록**
  — 지금처럼 아무 PlayerController에서나 직접 서브시스템 함수를 호출하는 방식이면 클라이언트가
  쳐도 그 클라이언트 프로세스 안에서만 효과가 나고 서버/다른 클라이언트엔 반영 안 됨.
- 아군 30명(§1.3: "UGV에 종속된 로컬 팔로워, 별도 통신 없음")은 설계상 "UGV를 호스트하는 프로세스
  (=UGV PC=서버)의 AI 로직으로만 계산하고, 그 결과(위치/애니메이션/상태)만 표준
  캐릭터 리플리케이션으로 클라이언트에 전파"하는 방향이 설계 문서와 일치 — 지금 아군의
  `AAIController`/이동 로직이 서버 전용으로 실행되도록 강제하는 코드는 없음(그냥 로컬에서 도는
  구조라 서버 프로세스에서 돌면 결과적으로 맞게 되지만, 클라이언트 프로세스에서 우연히 같이
  돌면 안 됨 — 명시적 게이팅 필요).

---

## 6. GameMode / PlayerController 클래스 설정

**지금 상태**: 완전 싱글플레이 전제. 네트워킹/리슨서버를 조금이라도 염두에 둔 설정은 발견 안 됨.

- 실제 사용 중인 GameMode: `BP_ThirdPersonGameMode`(부모 `Atitan_exampleGameMode` : `AGameModeBase`)
  — `DefaultEngine.ini`의 `GlobalDefaultGameMode`로 지정, 레벨 WorldSettings의 GameMode 오버라이드는
  `None`(프로젝트 기본값을 그대로 씀).
  - `DefaultPawnClass = None` — 플레이어가 접속해도 GameMode가 자동으로 폰을 스폰하지 않음.
    지금은 `ATitanTruck::BeginPlay`의 자기-possess(§3)와 `AutoPossessAI`로 각 차량이 스스로
    컨트롤러를 갖는 방식으로 우회하고 있음 — 정상적인 멀티플레이어 `Login`/`RestartPlayer` 흐름을
    타지 않음.
  - `PlayerControllerClass = BP_ThirdPersonPlayerController`(부모
    `Atitan_examplePlayerController`) — 특별한 네트워크 관련 오버라이드(예: 커스텀
    `GetSeamlessTravelActorList`, `OnRep_Pawn` 등) 없음.
  - `GameStateClass`/`PlayerStateClass`/`HUDClass` 전부 **엔진 기본값 그대로**
    (`GameStateBase`/`PlayerState`/`HUD`) — 시나리오 진행 상태나 UGV/트럭 소유권 같은 것을 담을
    커스텀 `GameState`가 없음. §5에서 지적한 "서버 권위 시나리오 상태를 어디에 둘 것인가" 문제와
    직결 — 지금 그 역할을 할 클래스 자체가 없음.
  - `bUseSeamlessTravel = false`, `bStartPlayersAsSpectators = false` — 기본값, 리슨서버
    전환에는 문제 없는 값들이지만 의도적으로 설정된 건 아님(그냥 기본값).
- `Atitan_examplePlayerController` 자체에도 네트워크 모드 분기(`IsServer()`, `GetNetMode()`,
  `HasAuthority()` 등)가 전혀 없음(grep 0건) — 항상 "나 = 유일한 로컬 플레이어"라고 가정하고 짜여
  있음(§4).
- `AUGVAIController`가 `APlayerController`를 상속하는 특이 구조(§3)라, GameMode 관점에서 "이건
  실제 접속한 플레이어의 컨트롤러가 아니라 로컬 AI 봇"이라는 것을 구분할 장치가 없음 — 두 PC가
  붙는 리슨서버 환경에서 `AUGVAIController` 같은 "headless 봇 PlayerController"가 실제 접속
  플레이어와 섞여도 안전한지 검증 필요(질문 목록 Q3).

**리플리케이션 되려면 뭘 고쳐야 하는지**:
- 커스텀 `AGameStateBase` 서브클래스를 도입해 시나리오 진행 상태(§5) 등 "모두가 같은 값을 봐야
  하는" 서버 권위 상태를 명시적으로 리플리케이트.
- `DefaultPawnClass`를 비워두는 대신, GameMode의 `Login`/`PostLogin`에서 "이 접속이 UGV PC인지
  자체방호 PC인지" 판별해 해당 차량을 정식으로 possess시키는 로직 추가(현재의
  `GetPlayerController(this,0)` 하드코딩 대신) — 축 판별 방법 자체는 아직 미정(질문 목록 Q5).
- `Atitan_examplePlayerController`/`AUGVAIController`에 `HasAuthority()`/`GetNetMode()` 분기를
  추가해 "이 코드가 서버에서 도는지 클라이언트에서 도는지"를 명시적으로 구분하는 지점부터 시작.

---

## 7. 확인 필요 사항 (질문 목록 — 추측하지 않고 남겨둠)

1. **TitanTruck의 `AutoPossessAI=PlacedInWorld` + AIControllerClass 미지정**은 의도적 설정인가,
   아니면 그냥 꺼두지 않은 것인가? (BeginPlay가 어차피 바로 재-possess하므로 지금은 결과적으로
   무해하지만, 리슨서버로 가면 "누가 먼저 possess하는가" 타이밍이 중요해짐.)
2. **(해소됨, 확인용으로만 남김)** UGV 구동 방식은 사용자 확인으로 Chaos Vehicle
   (`BP_UGV_Vehicle`) 확정, 힘-기반 `UUGVMovementComponent`/`AUGVPawn`은 삭제 예정 — 다만
   `BP_UGV_Vehicle`이 `AUGVAIController::DispatchSetManualControl`이 리플렉션으로 찾는
   `SetManualControl(float, float)` 함수를 실제로 구현하고 있는지는 블루프린트 그래프를 열어
   직접 확인 필요(이번 조사는 C++ 레이어만 봤음, §7-7과 동일한 제약).
3. `AUGVAIController`가 `APlayerController`를 상속하고 `IsLocalController()`를 강제 true로
   오버라이드한 것 — 클래스 주석상 사유는 "Chaos Vehicle 관련 로직이 `IsLocallyControlled()`를
   보고 로컬 시뮬레이션 여부를 결정하는 것 같다"는 추정이었는데, 실제로 어느 Chaos 서브시스템이
   그 값을 참조하는지(엔진 소스의 정확한 호출 지점) 원 작성자가 더 구체적으로 확인해둔 게
   있는지 필요. 리슨서버 도입 시 이 클래스를 진짜 `AAIController`로 되돌릴 수 있는지, 아니면
   다른 방식(네트워크 모드 분기)으로 남겨야 하는지도 결정 필요.
4. RCWS pan/tilt 같은 고빈도 조작 입력을 리슨서버 환경에서 어떤 정책으로 처리할지(매 프레임
   서버 RPC vs 클라이언트 예측 + 주기적 동기화 vs 소유 클라이언트가 자기 차량 RCWS는 전권 소유)
   — 설계 문서에 아직 명시 없음.
5. 리슨서버 접속 시 "이 PC가 UGV 축인지 자체방호 축인지"를 어떻게 판별할 것인가(커맨드라인
   인자, 로그인 옵션 문자열, 별도 설정 파일 등) — GameMode의 `Login`/`PostLogin`에서 이 판별
   로직이 필요한데 설계 문서에 구체적 메커니즘이 없음.
6. `UAVPawn`(`BP_UAV_C_1`)의 `bReplicates`/조작 방식은 이번 조사에서 상세히 안 봤음(스코프
   밖 — 설계 문서 §1.3 리플리케이션 대상 목록에 UAV가 명시되어 있지 않음). UAV도 리플리케이션
   대상에 포함되는지 확인 필요.
7. 아군 30명의 전투 로직(사격 등)이 `BP_ThirdPersonCharacter`(부모 BP) 쪽에 **블루프린트로만**
   구현돼 있고 C++ 헤더가 없음(`AllyFormationComponent`가 리플렉션으로 접근) — 이 블루프린트
   전투 로직 자체를 감사하려면 에디터에서 직접 그래프를 열어 확인해야 함(C++ grep으로는 안 보임).
   이번 조사는 C++ 레이어만 봤다는 점 명시.

---

## 8. 구현 TODO (조사 완료 후 확정, 실행 대기)

Q1/Q4/Q5/Q6 답변 반영(2026-08-06, `architecture_decisions.md` §1.4 참고). 체크박스는 실제
구현 착수 시 갱신.

**최우선 — 지금 배치된 액터에 바로 영향, 리슨서버 켜기 전 필수**
- [x] (2026-08) `ATitanTruck::BeginPlay`의 `GetPlayerController(this,0)->Possess(this)` 하드코딩
      제거 완료 — `TitanTruck.h`/`.cpp` 클래스 코멘트에 이전 동작 기록만 남아있고 실제 코드는
      제거됨. Axis 판별로 정상 possess(아래 GameMode 항목 참고).
- [x] (2026-08) `AUGVAIController::IsLocalController()` — `return true` 하드코딩을 네트워크 모드
      분기로 교체 완료(`UGVAIController.h`): `NM_Standalone`이면 기존과 동일하게 항상 true(단일
      플레이/PIE 단일 프로세스 하위호환), 리슨서버가 켜진 뒤로는 `HasAuthority()` 기준(서버
      인스턴스만 true) — Q3(어느 Chaos 서브시스템이 이 값을 참조하는지)는 근본 원인 설명이 헤더에
      남아있고 그대로 유효함이 확인됨.
- [x] (2026-08) GameMode 접속 Options 문자열 기반 축 판별 구현 완료 — `Atitan_examplePlayerController::
      HostListenServer(Axis)`가 `open <레벨>?Listen?Axis=<Axis>`, `ConnectToHost(ServerIP, Axis)`가
      `open <서버IP>?Axis=<Axis>`를 실행(`AxisSelectionWidget` UI 경유). `Login`/`PostLogin`을 직접
      오버라이드하는 대신 `open` 커맨드의 URL 옵션 + `InitNewPlayer`에서 파싱하는 방식(Q5 방향과
      실질적으로 동일한 결과).
- [x] (2026-08) `Atitan_exampleGameState`(커스텀 `AGameStateBase` 서브클래스) 도입 완료 —
      `EScenarioPhase` 등 서버 권위 상태를 여기로 이전(아래 "시나리오 시스템" 섹션 참고).

**RCWS / 발사**
- [x] (2026-08) `CurrentMode`/`bIsLockedOn`/`CurrentAutoAimTarget`/`bStabilizationEnabled`
      (RCWSFireControlComponent) + `CurrentData`(탄약/줌/거리 등 전체)/`ZoomLevel`/
      `ReplicatedMountRelativeRotation`(RCWSComponent)을 `Replicated`+`OnRep_*`로 전환 완료.
- [x] (2026-08) `AddPanTiltInput`/`SetZoomLevel`을 HasAuthority 가드로 서버 전용화, 마운트 raw
      relative rotation을 리플리케이트해서 OnRep에서 클라이언트 쪽 마운트에 되돌려 적용(진북
      변환 역산 불필요).
- [x] (2026-08) `RCWSFireControlComponent::TickComponent`를 서버 전용 시뮬레이션(안정화/자동조준/
      총구 탄도 슬루/줌 램프/반동/발사)과 모든 프로세스 공통 UI 계산(조준점/레티치 마커)으로 분리
      — 클라이언트 자신의 화면은 계속 부드럽게 갱신되면서 실제 상태 변경은 서버 권위로 통일.
      `SelectNearestEnemyTarget`은 이 분리의 부수 효과로 UpdateAutoAim(서버 전용) 경로에서는 이미
      서버 전용이 됨 — 단, UpdateAimPointForUI(UI 힌트 목적, 로컬 탐지 사용)의 별도 호출은 의도적으로
      게이팅 안 함(Detection 시스템 자체가 아직 로컬 전용이라 §2 항목과 별개 후속 과제로 유지).
- [x] (2026-08) `SetManualFireHeld`/`CycleControlModeNext/Previous`/`SetControlMode`(SetRCWSMode)/
      `AddManualZoomStep`/`bStabilizationEnabled`/pan-tilt/`SyncRCWSControlModeForCameraTarget`
      트리거 경로를 전부 `Atitan_examplePlayerController`의 `Server_*` RPC로 전환(HasAuthority면
      로컬 직접 호출, 아니면 RPC) — UGV축 PC(서버)는 지연 없음, SelfDefense 클라이언트는 RPC
      왕복 지연 발생(아래 항목 참고).
- [ ] RCWS pan/tilt 클라이언트 예측(Q4 확정 방향 중 후반부) — 지금은 단순화를 위해 서버 왕복
      방식으로 구현함(위 항목). 실제 네트워크 지연이 체감되면, 소유 클라이언트가 즉시 로컬
      반영 + 스로틀된 주기로 서버에 결과 각도만 보내 검증/리플리케이트하는 방식으로 개선 필요.
      **2026-08-13 확인 — 포탑 각도 자체는 divergence 위험 없음**: `Fire()`가 서버 전용 Tick에서만
      호출되므로 발사 방향은 서버가 자기 시점의 진짜 각도로 딱 한 번 계산해서 Multicast로 그
      결과값을 뿌림 — 클라이언트가 자기 화면의 (지연된) 포탑 각도로 재계산하는 구조가 아니라서
      "서버 각도 vs 클라이언트 각도가 달라서 발사 방향이 갈리는" 시나리오는 애초에 안 일어남. 이
      항목은 순수하게 "체감 지연"(왕복 시간) 개선용이지 정확성 문제가 아님.
- [x] (2026-08-13) **투사체 명중 판정 서버 권위화 — 히트스캔 전환 대신 이 방식으로 확정.**
      사용자 검토 후 결정: 투사체 궤적 자체의 액터 리플리케이션(표준 위치 리플리케이션이 빠른
      소형 오브젝트에 취약해 오히려 끊겨 보일 위험)도, 히트스캔 전환(현재의 "실제로 날아가는
      투사체" 비주얼을 포기해야 함)도 모두 기각 — 대신:
      - `ARCWSProjectile::OnHit()`이 `HasAuthority()`가 아니면 로컬 투사체를 그냥 멈추기만 하고
        즉시 리턴(데미지도 이펙트도 재생 안 함) — 서버의 로컬 사본만 명중을 확정.
      - 서버가 확정한 명중(데미지 적용 + 이펙트/사운드 선택)을 `ReportHitToInstigator()`가
        투사체를 쏜 주체(RCWS 차량 또는 아군/적군 캐릭터)에 붙은 컴포넌트를 찾아 새
        `Multicast_PlayImpactEffect(위치, 법선, 이펙트, 사운드, 감쇠값)`로 전달.
      - `URCWSFireControlComponent`/`UAllyFormationComponent`/`UEnemyCombatComponent` 세 곳 모두
        동일 시그니처의 `Multicast_PlayImpactEffect`를 추가(RCWS + 아군/적군 라이플 공통 — 라이플
        투사체 `BP_RifleProjectile`이 `ARCWSProjectile`을 그대로 상속해서 OnHit 로직도 공유됨).
        실제 스폰은 `ARCWSProjectile::PlayImpactEffect()` static 함수 하나로 통일.
      - **위치 기반이라 풀 슬롯 매칭이 필요 없음** — 발사 트리거(`Multicast_FireEffects`)가 쓰는
        암묵적 풀 인덱스 동기화(Unreliable RPC 드롭 시 영구 어긋남 위험, §8 자체적으로 확인됨)와
        달리, 이 멀티캐스트는 드롭돼도 다음 발엔 그냥 정상화됨(누적 어긋남 없음) — 더 견고한 설계.
      - `BP_Enemy_Base`의 `Health`를 `Replicated`로 전환(기존엔 `IsDead`만 리플리케이트, `Health`는
        서버에서만 바뀌고 클라이언트엔 안 보이고 있었음).
      - 명중 이펙트의 "적/기타 어느 쪽 이펙트를 재생할지"(`bHitEnemy`) 판정 자체는 서버 전용으로
        옮기지 않음 — `UDetectableTargetComponent::Faction`이 런타임에 안 바뀌는 정적 값이라 로컬
        판정도 항상 서버와 일치, 서버 권위가 필요한 건 "맞았는지 자체"(표적 위치 리플리케이션
        지연으로 로컬 판정이 갈릴 수 있는 부분)뿐이라는 걸 확인 후 범위를 거기로 좁힘.
      - 궤적 자체(비행 중 위치)는 여전히 각 프로세스 로컬 재생 — 결정론적 포물선이라 화면상
        동일하게 보이고, 이 판단 자체가 정석(표준 위치 리플리케이션은 이런 빠른 오브젝트엔 오히려
        부적합)이라는 걸 확인.
      - 부수 작업: 원인 확정 전까지 남겨뒀던 진단용 `UE_LOG`(`AllyFormationComponent`/
        `EnemyCombatComponent`의 발사멀티캐스트 로그, `LogFireMulticastDiagnostic` 헬퍼) 제거.

**UGV / 차량 (2026-08-14 구현 완료)**
- [x] `AUGVAIController::Tick()` 전체(`UpdateChaosPursuit`/`UpdateOffRoadSpeedDecay`/
      `UpdateRoadBoundary`/`UpdateTankUGVStatusData`)를 `HasAuthority()`로 서버 전용화 —
      아군/적군 컴포넌트와 동일하게 통째로 게이팅. **조사 결과 이 컨트롤러는 애초에 클라이언트에서
      존재조차 안 함**(헤드리스 봇, `AutoPossessAI`로 스폰되는 컨트롤러는 엔진 자체가
      `APawn::SpawnDefaultController()`에서 `NetMode==NM_Client`면 얼리리턴 — 즉 이 게이팅은
      이론상 이미 안전했던 것을 명시적으로 강제한 방어 조치에 가까움). 위치/회전은 표준
      `AWheeledVehiclePawn`/`ChaosVehicleMovementComponent` 이동 리플리케이션이 처리.
- [x] `UUGVStatusComponent::CurrentData`(대시보드 속도/기어/배터리 등)를 `Replicated`(RCWS의
      `CurrentData`와 동일 패턴, 빈 스텁 `OnRep`)로 전환 — 컨트롤러가 클라이언트에 없다는 건
      `UpdateTankUGVStatusData`가 클라이언트에선 한 번도 안 불린다는 뜻이라, 이거 없이는
      클라이언트 UGV 대시보드가 영원히 `bUseDummyData`의 가짜 값만 보여주고 있었음(실제 버그,
      추정이 아니라 코드로 확인됨). `TickComponent`의 `GenerateDummyData` 호출도 `HasAuthority()`로
      막아서 클라이언트가 리플리케이트된 값을 자기 로컬 더미 생성으로 덮어쓰지 못하게 함.
- [x] `Atitan_examplePlayerController::DoUGVFromTankMove`/`DoUGVFromTankMoveCompleted`/
      `DoUGVFromTankBrakeStarted`/`DoUGVFromTankBrakeCompleted`/`SetUGVFromTankMode`/
      `MoveUGVFromTankTo`(콘솔 커맨드) 전부 `HasAuthority()` 가드 추가 — 이 함수들이
      `AUGVAIController::DispatchSetManualControl`을 서버 체크 없이 직접 호출하고 있었음(위
      "컨트롤러가 클라이언트에 없음" 덕에 우연히 무해했겠지만, "UGV는 host에서만 조종 가능"이라는
      사용자 확정 요구사항을 코드로 명시적으로 강제).
- [x] `BP_UGV_Vehicle`의 자체 `EventTick`(궤도/트랙 시각 효과 — track sag/tautness/wheel 회전) 확인
      — `ChaosWheeledVehicleMovementComponent::GetForwardSpeed()`/메시 월드 회전만 읽는 순수 로컬
      코스메틱이라 게이팅 불필요(이미 리플리케이트되는 물리 상태를 그대로 반영하는 구조). 아군/적군
      때와 달리 이번엔 블루프린트 쪽에 숨은 위험 로직이 없었음.
- [ ] `physicsReplicationMode`(Chaos 물리 리플리케이션 모드, `VehicleMesh` 컴포넌트 추정)를
      MCP로 조회/설정 시도했으나 정확한 프로퍼티 이름을 못 찾아 실패 — 기본값(`Default`) 그대로
      둠. 클라이언트 화면에서 UGV 움직임이 끊겨 보이면 에디터에서 직접
      `VehicleMesh`(SkeletalMeshComponent)의 Physics/Replication 카테고리를 확인해서
      `Predictive Interpolation`으로 바꿔볼 것.
- [ ] `BP_UGV_Vehicle`이 `DispatchSetManualControl`이 찾는 `SetManualControl(float,float)`을
      실제로 구현하는지 확인(Q2) — **2026-08-14 확인: 구현돼 있음** — `SetManualControl`/
      `SetBraking` 함수 그래프가 실제로 존재(list_graphs로 확인). Q2 완전 해소.

**시나리오 시스템**
- [x] (2026-08, 저위험 1차) `Atitan_exampleGameState`에 `EScenarioPhase`(Idle/FormingUp/Advancing/
      Approaching/Ambush/EnemyFleeing) 추가, `Replicated`+`OnRep`. `UScenarioStateSubsystem`의
      `BeginAllyFormUp`/`StartUGVAdvance`/`BroadcastAllyApproach`/`BroadcastAllyAmbush`/
      `BeginEnemyFlee`가 전환 시점마다 `GameState->SetScenarioPhase(...)` 호출 — "지금 크게 어느
      단계인가"만 거칠게 요약해서 모든 프로세스가 같은 값을 보게 함. `UScenarioStateSubsystem`
      자체의 상세 내부 상태(집결 큐/수신호 타이머/스텝 발동 기록 등)는 그대로 안 건드림 —
      전면 이전은 하지 않았음(범위 밖으로 판단).
- [x] (2026-08, 저위험 1차) `BeginAllyFormUpAndAdvance`/`BeginAllyFollowing`/`BeginAllyApproach`/
      `BeginAllyAmbush`/`BeginEnemyFlee`/`SetUGVStandbyDestination` Exec 커맨드를
      `Server_*` RPC로 전환(HasAuthority면 로컬 직접 호출, 아니면 RPC) — RCWS의 발사/모드전환
      트리거와 동일 패턴. 클라이언트가 쳐도 이제 서버(UScenarioStateSubsystem의 서버 인스턴스)에
      실제로 반영됨.
- [x] (2026-08, 고위험 후속 — 구현+재빌드+실기 테스트 전부 완료, 아래 두 항목의 버그를 거쳐 최종
      정상화됨) `AllyFormationComponent`/
      `EnemyCombatComponent`의 `TickComponent` 전체를 `HasAuthority()` 가드로 서버 전용화(RCWS와
      달리 UI 전용으로 뺄 계산이 없어 통째로 게이팅). 위치/회전은 `ACharacter` 표준 이동
      리플리케이션이 자동 전파하지만, 두 컴포넌트가 리플렉션(`SetBoolPropertyByName`류)으로 건드리는
      Blueprint 전용 자세/애니메이션 변수(`IsProne`/`IsKneeling`/`IsHoldingWeapon?`/`HasTarget`/
      `CurrentEnemy`(Ally)·`CurrentAlly`(Enemy)/`AimPitch`/`LeanAlpha`/`CurrentRifle`/
      `BurstShotsRemaining`/`IsReloading?`/`IsDead`(Enemy)/`IsLeftArmBlending`(Ally, 정지수신호)/
      `TargetLocation`)는 C++에서 직접 못 건드려서 `BP_ThirdPersonCharacter`(Ally 부모)/
      `BP_Ally_kadex`(LeanAlpha)/`BP_Enemy_Base`(Enemy 부모) 쪽에서 MCP로 각각 `Replicated`로
      전환 — 안 하면 클라이언트 화면에서 위치는 맞아도 자세/애니메이션이 안 맞음. **RCWS보다
      회귀 리스크가 크다고 사전에 밝혔던 지점(30+15명 규모, "이번 세션에 안정화됨" 코드) — 재빌드
      후 최소 아군1 vs 적군1(레벨에 배치, 서로 교전하도록 테스트 세팅 완료 — 아래 참고) 기준으로
      양쪽 화면에서 위치/애니메이션이 다 정상인지, 클라이언트 쪽에서 로컬 시뮬레이션과 다투는
      rubber-banding이 없는지 먼저 확인 필요. 45명 전체로 확장하기 전 이 최소 케이스로 먼저 검증.**

- [x] (2026-08, 사용자 리포트 "총알/발사 이펙트/소리 안 됨") — 위 Tick 게이팅의 후속 사각지대:
      `TickAmbush`/`TickMove`/`TickCombat`가 `CallVoidEventByName`으로 직접 부르던
      `FireAtEnemy`(Ally)/`FireSingleShotAtNearestAlly`·`FireAtAlly`(Enemy) 트리거를 각각
      `Multicast_TriggerFireAtEnemy`/`Multicast_TriggerFireSingleShotAtNearestAlly`/
      `Multicast_TriggerFireAtAlly`(전부 `NetMulticast`)로 교체 — RCWS `Fire()`와 동일한 문제
      (서버 전용 틱에서 트리거되니 그 아래 체인의 투사체 스폰/머즐 화염/사운드가 클라이언트엔
      전혀 안 보임). Blueprint 그래프(`FireAtEnemy`→`FireBurstShot`→`CurrentRifle->Shoot()`) 자체는
      전혀 안 건드림 — MCP에 이벤트 단위 리플리케이션(Multicast) 설정 도구가 없어서, 대신 C++ 쪽
      트리거 호출 지점만 멀티캐스트로 감쌈. 탄약(`AmmoInMag`)은 리플리케이트 안 했지만, 모든
      프로세스가 동일한 멀티캐스트 호출 순서를 그대로 재생하는 구조라 시작값만 같으면 자연히
      동기 상태 유지(RCWS 발사체 풀 인덱스 동기화와 동일 논리).

- [x] (2026-08-11, 실기 테스트 중 발견 — 아군 `CurrentEnemy`/`HasTarget`가 클라이언트에서 계속
      `None`/`false`) 근본 원인은 **`AllyFormationComponent`/`EnemyCombatComponent`의 Tick 게이팅과
      전혀 무관한, `BP_ThirdPersonCharacter` 캐릭터 블루프린트 자체의 두 군데 게이팅 안 된 로직**
      이었음(C++ 컴포넌트만 감사해선 못 찾음 — Q7이 지적했던 바로 그 사각지대):
      1. 캐릭터의 `OnComponentBeginOverlap/EndOverlap(EnemyDetectRange)` — 콜리전 오버랩으로
         `CurrentEnemy`/`HasTarget`를 직접 세팅/해제하는 로직이 서버/클라이언트 각자 로컬로
         독립 실행되고 있었음(Enemy 쪽엔 이런 오버랩 기반 타게팅이 아예 없어서 비대칭이었던 것—
         `CurrentAlly`는 순수 `EnemyCombatComponent` Tick으로만 세팅돼 문제 없었음). 두 이벤트
         각각에 `Switch Has Authority` 노드를 끼워 서버 전용화.
      2. 캐릭터의 `EventTick`(C++ 컴포넌트와 별개로 캐릭터 블루프린트 자체에 있던, 훨씬 이전부터
         있던 로직) — 매 프레임 `HasTarget`이 true면 `IsValid(CurrentEnemy)`를 검사해서 invalid하면
         `HasTarget`/`CurrentEnemy`를 리셋하는 코드가 역시 게이팅 없이 전 프로세스에서 실행 중.
         클라이언트에서 서버의 리플리케이트된 `CurrentEnemy`가 도착하기 전 타이밍에 이 Tick이
         먼저 돌면 즉시 다시 리셋해버려서, 리플리케이션된 값이 클라이언트에 영원히 안착 못 함.
         `AimPitch`/`TargetLocation`은 이미 Replicated라 이 블록 전체를 `Switch Has Authority`로
         서버 전용화해도 클라이언트 조준 표시엔 영향 없음.
      - 위 두 개를 고쳐도 `HasTarget`은 정상화됐지만 **`CurrentEnemy`(오브젝트 레퍼런스) 자체는
        여전히 클라이언트에서 계속 `None`** — 근본 원인 미확정(액터 레퍼런스 리플리케이션 관련
        원인 불명 이슈로 남음, `bReplicates`/`NetCullDistanceSquared`/`NetUpdateFrequency`/
        `NetDormancy` 전부 Enemy와 동일 확인했지만 미해결). `FireBurstShot`의 `IsValid(CurrentEnemy)`
        게이트를 확인해보니 `Shoot()` 자체는 `CurrentEnemy`를 소비하지 않고(`self`=`CurrentRifle`뿐)
        순수 게이트 용도였고, 이 체인은 이미 서버가 유효성을 확인한 뒤에만 멀티캐스트로 트리거되는
        구조라 클라이언트에서 재검증할 필요가 없다고 판단 — `IsValid(CurrentEnemy)` 노드를 체인에서
        제거하고 `IsValid(CurrentRifle)`만으로 게이팅하도록 배선 변경(근본 수정이 아니라 우회지만,
        실사용엔 영향 없음).
- [x] (2026-08-11, 실기 테스트 — 적군 낙하산이 클라이언트에서 안 사라짐) 낙하산 숨김 로직이
      `EventOnLanded`(네이티브 캐릭터 무브먼트 착지 이벤트)에 걸려있었는데, 이게 시뮬레이션
      프록시인 클라이언트에서 안정적으로 안 터지는 게 원인 — `BP_Enemy_Base`의 `IsParachuting`을
      `RepNotify`로 전환하고, `OnRep_IsParachuting`에서 `false`가 되면 낙하산 메시를 숨기도록 배선
      추가(서버 권위로 확정, 클라이언트는 리플리케이션만 신뢰).

**테스트용 레벨 세팅 (2026-08, kadex_test)** — 아군/적군 각 1명 배치된 걸 서로 교전하도록 최소
구성:
- `BP_Ally_kadex_C_1.AllyFormation.bAutoBeginAmbushForTesting = true` — BeginPlay 즉시 Ambush
  상태 진입(AmbushMarker 비워둠 — 없으면 즉시 그 자리에서 엎드리는 안전한 폴백이라 타깃포인트
  불필요했음).
- `BP_Enemy_kadex_C_1.EnemyCombatComponent`: `EngagePoint = TP_Enemy1_EngagePoint`(신규 배치한
  TargetPoint, 적 현재 위치와 동일 좌표 — EngagePoint는 null이면 TickMove가 영원히 아무것도 안
  해서 필수), `bAutoBeginMoveForTesting = true`.
- FiringPose/CoverPose(양쪽 다)는 안 건드림 — 마커 없으면 항상 Prone 폴백으로 안전하게 동작.
  더 정교한 엄폐 연출이 필요해지면 그때 타깃포인트로 채우면 됨.

**UAV (2026-08-13 구현 완료)**
- [x] `AUAVPawn` — 위치/회전은 `APawn` 기본 리플리케이션(변경 없이 그대로 작동). 미션 물리 전체
      (`TickAscending`/`TickHovering`/`TickCruising`/`UpdateTerrainAvoidanceAccel`)와 짐벌 자동정찰
      (`UpdateGimbalRecon` 및 하위 4개 함수)를 `Tick()` 안에서 `HasAuthority()`로 서버 전용화 —
      아군/적군 컴포넌트와 동일하게 통째로 게이팅(RCWS처럼 따로 뺄 UI 계산이 없음).
- [x] `MissionState`/`GimbalYawDeg`/`GimbalPitchDeg`/`ZoomLevel`/`CurrentPropSpinRateDegPerSec`/
      `PropSpinAngleDeg`/`CurrentBodyTiltPitchDeg`를 `Replicated`(+필요한 것만 `OnRep`)로 전환.
      `GimbalYawDeg`/`PitchDeg`/`ZoomLevel`은 ABP_UAV/`SyncLensFromCineCamera`가 매 프레임 직접
      읽어 쓰므로 OnRep 불필요. `MissionState`는 RCWS의 `CurrentMode`와 동일하게 빈 스텁 OnRep.
      `CurrentBodyTiltPitchDeg`는 예외적으로 실제 동작하는 `OnRep_CurrentBodyTiltPitchDeg` 필요 —
      `UpdateBodyTilt`가 `BodyMesh->SetRelativeRotation`을 C++에서 직접 호출하는데 그 함수 자체가
      서버 전용 Tick 안에 깊이 물려있어서(TickAscending/Hovering/Cruising 내부), 클라이언트에선
      대신 OnRep이 동일한 적용을 반복.
      `CurrentPropSpinRateDegPerSec`/`PropSpinAngleDeg`도 같은 이유(`UpdatePropSpin`이 그 세 함수
      내부에서만 호출됨)로 함수 자체를 안 건드리고 결과값만 리플리케이트 — 프로펠러 회전이 클라
      이언트에서 60Hz 로컬 보간만큼 매끄럽진 않을 수 있으나 순수 코스메틱이라 무방하다고 판단.
- [x] `AddGimbalPanTiltInput`/`SetZoomLevel`/`BeginManualZoomTransition`/`BeginMissionToTarget`에
      `HasAuthority()` 가드 추가. 짐벌 pan/tilt와 미션 시작(`BeginMissionToTarget`)은 이미
      `Atitan_examplePlayerController`의 `Server_ApplyUAVGimbalPanTiltInput`/
      `Server_BeginUAVMissionToTarget`(이번에 신설, `BeginAllyFormUpAndAdvance`와 동일 패턴)로
      트리거 경로가 서버로 묶여있어서 가드가 실질적으로 무해함.
      **⚠️ 미해결 — `SetZoomLevel`/`BeginManualZoomTransition`(UAV 카메라 줌)은 대응하는 Server RPC가
      없음.** `ManualZoomTransitionDurationSeconds`의 기존 헤더 코멘트에 "SelfDefenseDashboardWidget"
      전용이라고 명시돼 있어 그 줌 버튼이 클라이언트(SelfDefense PC) 쪽 위젯에서 직접
      `BeginManualZoomTransition`을 호출하고 있을 가능성이 있음 — 그렇다면 이번 HasAuthority
      가드로 그 버튼이 클라이언트에서 조용히 no-op됨(회귀). 위젯이 실제로 어디서/어떻게 이 함수를
      호출하는지 확인 후, 필요하면 RCWS의 `Server_AddManualZoomStep`과 동일한 패턴으로 RPC를 추가
      배선해야 함 — 이번 라운드에서 WBP 그래프까지는 안 열어봄(범위 밖으로 판단, 사용자 확인 필요).

**추가 조사 필요 (구현 아님)**
- [ ] Q3: `IsLocalController()`를 실제로 참조하는 Chaos 서브시스템 엔진 소스 확인(네트워크 모드
      분기로 이미 우회했지만 — 위 UGV/차량 섹션의 `[x]` 항목 — 근본 원인 자체는 여전히 미확인).
- [x] Q7: 아군 전투 블루프린트(`BP_ThirdPersonCharacter` 계열) 에디터에서 직접 열어 로직 확인 —
      2026-08-11 실기 테스트 중 필요해져서 열어봄, 위 "시나리오 시스템" 섹션의 두 버그 항목이 그
      결과물. `OnComponentBeginOverlap/EndOverlap(EnemyDetectRange)` + `EventTick`이 C++ 컴포넌트와
      완전히 별개로 게이팅 안 된 로직을 갖고 있었던 것이 확인된 핵심 위험 패턴 — 앞으로 이
      캐릭터/Enemy 계열 블루프린트를 추가로 수정할 일이 있으면 "C++만 감사해선 안 보이는 로직이
      더 있을 수 있다"는 전제로 접근할 것.

**kadex_test 레벨 Axis 선택 화면 인프라 (2026-08)**
- [x] `kadex_test`용 `BP_KadexTestGameMode`(부모 `Atitan_exampleGameMode`) 신설 —
      `PlayerControllerClass=BP_TestPlayerController`, `DefaultAxisWhenUnspecified=UGV`로
      에디터에서 레벨을 직접 열었을 때 축 선택 화면 없이 바로 UGV/호스트로 진입. `kadex_lobby`는
      기존 `BP_TestGameMode`(`DefaultAxisWhenUnspecified=Unspecified`)를 그대로 써서 Host/Client
      선택 화면(`AxisSelectionWidget`)이 계속 뜸 — 두 레벨의 역할(하나는 빠른 단독 테스트용, 하나는
      실제 Host/Client 선택이 필요한 진입점)에 맞게 분리 완료.
