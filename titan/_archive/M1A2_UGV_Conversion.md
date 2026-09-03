> [보관됨 2026-08-31, 재확인] 여기서 만든 `BP_UGVFromTank`는 **실사용 UGV가 아님** —
> `replication/replication_audit.md` §1 리플리케이션 감사로 실제 배치된 UGV는
> `BP_UGV_Vehicle`(별도의 순수 블루프린트, `AWheeledVehiclePawn` 직계)임이 확인됨,
> `BP_UGVFromTank`는 병행 시도 중 하나로 남고 채택 안 됨. 사용자 확인: 그래도 엔지니어링
> 지식(Possess/물리활성화 근본원인, 조향 토크 다이얼, 사운드 어테뉴에이션 버그 등)은
> 독립적으로 유용해서 보관.

# M1A2 탱크 → UGV 전환 작업 기록

마켓플레이스 M1A2 탱크 애셋(`BP_M1A2` / `BP_Tank` / `BP_VehicleBase` 상속 체인)을 복제해서
UGV(`BP_UGVFromTank`)로 만든 전체 과정 정리. 나중에 디자인팀 UGV 모델이 나와서 같은 작업을
다시 해야 하거나, 이번에 만든 구조를 다른 차량에 재사용할 때 참고용.

관련 클래스/블루프린트 전체 목록은 문서 맨 아래 "파일 목록" 참고.

---

## 1. 배경 — 왜 커스텀 스켈레탈 메시 대신 M1A2를 복제했나

원래 계획은 블렌더로 UGV 전용 스켈레탈 메시(Root/Wheel/Turret/Barrel)를 처음부터 만들고
C++ Chaos Wheeled Vehicle(`AUGVChaosPawn`/`UUGVChaosWheel`)로 직접 구성하는 것이었음. 이 과정에서:

- 본 축 컨벤션 문제 (블렌더 로컬 Y축 vs 언리얼 X축 — 해결됨, `primary_bone_axis`/`secondary_bone_axis`
  export 파라미터로 교정)
- **Root Body 분리 시 75cm 오프셋 버그**: `USkeletalMeshComponent::FindRootBodyIndex()`가
  "계층상 가장 앞쪽 본 중 Physics Asset 바디가 있는 첫 본"을 무조건 루트 바디로 취급 — Root
  본 자체가 아닌 자식 본에만 물리 바디가 있으면 컨스트레인트 없이 붕괴
- 바퀴 16개의 SuspensionState.ContactPoint가 전부 비슷한 좌표로 붕괴하는 원인불명 버그

등 극도로 오래 걸리는 디버깅 루프에 빠져서, 이미 검증된 M1A2 Chaos Vehicle Blueprint를
복제해서 불필요한 기능을 제거하는 방식으로 방향을 바꿈. 본 계층/Physics Asset/애니메이션을
그대로 물려받아 매번 처음부터 만드는 리스크를 없앰.

기존 C++ 클래스(`UGVChaosPawn.h/.cpp`, `UGVChaosWheel.h/.cpp`)는 참고용으로 삭제하지 않고
남겨둠 — 지금은 안 씀.

---

## 2. 기본 애셋 구성

- `/Game/Vehicles/UGV/ChaosFromTank/BP_UGVFromTank` — `/Game/EvolveStudio/Tanks/M1A2/Blueprint/BP_M1A2`
  복제본. 원본 M1A2 에셋(`/Game/EvolveStudio/...`)은 참고용으로 그대로 둠, 건드리지 않음.
- `/Game/Vehicles/UGV/ChaosFromTank/BP_UGVWheel_FromTank` — `BP_TankWheel_Chaos_M1A2` 복제본.
  독립적으로 튜닝 가능 (원본 탱크 바퀴에 영향 없음).
- `VehicleMovementComp.Mass`: 30000 → 3000 (실제 UGV 스케일에 맞게 축소).
- `BP_UGVWheel_FromTank`의 `Offset` +Z=50 — 스케일 조정 후 바퀴가 지면에 붕 떠 보이던 문제의
  임시방편(사용자가 직접 발견). 근본 원인은 못 찾았지만 실사용에 문제 없음.
- 조향(스키드 스티어)은 별도 구현 불필요했음 — `BP_Tank:TankTurn` 매크로가 이미
  `ChaosMovement->SetYawInput()`을 호출하는 네이티브 Chaos 비히클 기능을 쓰고 있어서, 그냥
  Steering 입력만 흘려주면 됨. 바퀴별 토크 오버라이드 방식은 필요 없었음.

**원본에서 제거 검토했던 것들** (실제로는 대부분 손 안 댐, 필요 없어지면 나중에 정리):
피격/파괴 시스템(`VehicleHealth`/`HealthTank` 등), 무기 관련 구성 요소 일부(`MainGunSpringOnFire`,
`Shell Hatch`, 연막탄), 라이트, 시네마틱 자동경로 시스템, 전투 HUD(`Crosshair`/`WBP_CrosshairSystem`).
유지한 것: `VehicleIMC`, 트랙 비주얼 시스템(`TrackPath_L/R`, `ChassisDistance*`, `Sagging*`,
`WheelRot*`), `TankTurn`/`SetYawInput`, `VehicleMovement`/기어.

---

## 3. Possess / 물리 활성화 — 가장 오래 걸린 디버깅 (2026-07-15)

**증상**: `BP_UGVFromTank`를 GameMode의 `DefaultPawnClass`로 직접 자동 스폰/Possess하면 연기/엔진
사운드는 나오는데 WASD 입력이 전혀 안 먹힘. `AIControllerClass`로 AI 컨트롤러가 possess해도
마찬가지 — 물리 시뮬레이션 자체가 절대 안 켜짐(공중에 뜬 채 정지).

**근본 원인 (엔진 소스 + 라이브 PIE 읽기로 확정)**:
`BP_VehicleBase`의 `ReceivePossessed` 이벤트가 `NewController`를 `CastToPlayerController`로
캐스팅해서 성공했을 때만 `VehiclePossessed()`를 호출함. 이 함수가 `SetVehicleState(...)`를
호출해야 `Event Tick`의 `SwitchOnE_VehicleState` 분기가 `SetSimulatePhysics(Mesh, true)` +
`ResetVehicle()`을 실행함 — 즉 **진짜 `APlayerController`가 possess해야만** 물리가 켜지는
구조. `AAIController`는 이 캐스팅에 항상 실패해서 물리가 영원히 안 켜짐.

여러 단계로 진단/시도했음(전부 실패 또는 근본 해결 아님):
1. `VehiclePossessed()`를 리플렉션으로 직접 호출 — 부족했음.
2. 물리 활성화 네이티브 함수(`SetSimulatePhysics`/`SetAllBodiesPhysicsBlendWeight`/`ResetVehicle`)를
   `AUGVAIController::ActivateVehicle()`에서 직접 호출 — `ResetVehicle()`이 내부적으로
   `RecreatePhysicsState()`를 호출해서 매 틱 파괴+재생성 루프에 빠짐, 여전히 실패.
3. `ResetVehicle()` 제거해도 동일 증상.
4. **결정적 단서**: 진짜 `PlayerController`(`Atitan_examplePlayerController::PossessUGVFromTank`
   콘솔 커맨드)로 possess하면 완전히 정상 작동 확인 — 컨트롤러 "타입" 자체가 원인 확정.
5. `AUGVAIController`를 `AAIController` 대신 **`APlayerController` 상속**으로 전면 재작성
   (엔진 소스로 `APawn::SpawnDefaultController()`가 `AAIController` 타입을 강제하지 않음을
   확인) — 그래도 여전히 물리 안 켜짐.
6. **진짜 마지막 원인**: `APlayerController::IsLocalController()`가 `GetNetDriver()==nullptr`
   이고 `ULocalPlayer`가 안 붙어있으면(헤드리스 봇은 항상 그럼) false를 리턴 — Chaos Vehicle의
   물리 시뮬레이션이 이 값에 의존하는 것으로 추정. `AUGVAIController::IsLocalController()`를
   오버라이드해서 무조건 `true` 리턴하는 것으로 최종 해결(싱글플레이·논네트워크 게임이라
   안전한 최소 수정).

**결과**: `AUGVAIController`는 이제 `AAIController`가 아니라 **헤드리스 `APlayerController`**임
(실제 Player/뷰포트 없이 존재, `IsLocalController()`만 오버라이드). `AutoPossessAI`/
`AIControllerClass` 설정은 엔진이 타입을 강제 안 해서 그대로 작동.

---

## 4. 구동 로직 (Manual/Auto/Idle)

옛 `AUGVPawn`(C++, `UUGVMovementComponent`)의 아키텍처를 최대한 재사용하되, Chaos Vehicle엔
`RequestDirectMove`(AI 이동 훅) 같은 게 전혀 없어서(엔진 소스로 확인) 새로 설계함.

- **C++ 인터페이스(`IUGVDrivable`) 방식은 폐기** — unreal-mcp 툴셋에 블루프린트에
  `ImplementedInterfaces`를 추가하는 도구가 없어서 완결이 불가능했음.
- 대신 **이름 기반 리플렉션**: `SetManualControl(float ForwardInput, float TurnInput)`이라는
  이름의 UFUNCTION을 가진 폰이면 그냥 `FindFunction`+`ProcessEvent`로 호출 — 인터페이스 등록
  불필요, MCP `add_function_graph`만으로 BP에 직접 만들 수 있음.
- `BP_UGVFromTank`에 `SetManualControl` 함수 신규 생성(MCP로). `TurningSpeedLimit()`은
  `BP_Tank`의 진짜 함수(상속되어 호출 가능)라 재사용, `TankTurn`은 매크로라 자식 BP에서 호출
  불가능해서 그 안의 로직 3단계(부호 반전, `SelectFloat`)를 직접 재구현.
- 반전(후진) 버그: `SetThrottleInput(ForwardInput)`에 음수를 넣으면
  `ChaosVehicleMovementComponent::CalcThrottleBrakeInput()`이 무조건 0~1로 클램프해서 후진이
  전혀 안 됐음. 실제 정답은 `bReverseAsBrake=true`(이 비히클 설정) — 양수 `ForwardInput`은
  `SetThrottleInput`, 음수는 `SetBrakeInput`으로 분리해서 넣어야 엔진 자체가 자동으로
  기어를 후진으로 바꾸고 브레이크 크기를 후진 스로틀로 씀. `AUGVAIController::
  DispatchSetManualControl`에 이 분리 로직 있음.
- `DriveMode`(Idle/Manual/Auto)는 `AUGVAIController` 소유(옛날처럼 Movement 컴포넌트 소유가
  아님, Chaos 비히클엔 그런 컴포넌트가 없어서). `SetDriveMode(Idle)`이 자동으로 풀브레이크까지
  겸함.
- 브레이크: `BP_UGVFromTank`에 `SetBraking(bool)` 함수 신규 생성 — `SetThrottleInput(0)` +
  `SetBrakeInput(1.0)`.
- Possess 여부와 무관하게 수동/자동 전환 가능 — `AUGVAIController`가 항상 possess한 채로
  유지하고 `DriveMode`만 바뀜(플레이어가 수동 조작해도 Possess() 호출 안 함,
  `Atitan_examplePlayerController::DoUGVFromTankMove`가 리플렉션으로 직접 입력 주입).

**BP 함수 파라미터 정밀도 함정**: BP에서 만든 float 파라미터는 실제로는 double 정밀도로
생성됨(C++ 진짜 float와 다름) — `FNumericProperty::SetFloatingPointPropertyValue`로 안전하게
맞춰써야 함(`DispatchSetManualControl`/`DispatchSetBraking` 참고).

---

## 5. AI 자동주행

`AUGVAIController`가 `APlayerController` 기반으로 바뀌면서 `AAIController` 전용 API
(`MoveToLocation`, `PathFollowingComponent`)를 잃음 — 직접 구현으로 대체:

- `UNavigationSystemV1::FindPathToLocationSynchronously`로 직접 경로 계산 (동기, 즉시 전체
  경로 확보 가능).
- Pure-pursuit 조향/스로틀 로직은 옛 `UUGVMovementComponent::RequestDirectMove`/
  `FindLookaheadTarget`을 거의 그대로 포팅(`UpdateChaosPursuit`/`FindChaosLookaheadTarget`) —
  경로 투영 → lookahead 지점 → heading error → steer/throttle. `UpdatedComponent` 대신
  `GetPawn()->GetActorLocation()`/`GetActorRotation()` 사용.
- 탱크는 로컬 +X가 진짜 전방(표준 컨벤션) — 옛 플레이스홀더 메시의 -X 특이사항 없음, 실측
  확인됨.
- `MaxSteerChangeRatePerSecond` 레이트 리밋은 의도적으로 뺌 — Chaos의 `YawInputRate`가 이미
  자체 스무딩하므로 중복 방지.
- 레벨에 탱크 전용 내비메시(`RecastNavMesh-Tank`, AgentRadius=200/AgentHeight=144)가 이미
  있었고, `VehicleMovementComp.NavAgentProps`를 여기 맞춰 설정 완료.
- `AutoPossessAI=PlacedInWorld`, `AIControllerClass=UGVAIController`(현재는
  `BP_UGVAIController`, 6절 참고) 설정.

---

## 6. 조향 토크 — 진짜 조향력의 정체 (2026-07-16)

사용자가 `MaxTurningSpeed`/`YawInputRate`를 아무리 올려도 조향이 안 빨라진다고 보고. 엔진
소스(`ChaosVehicleMovementComponent.cpp`)를 직접 추적해서 확정:

- `SetYawInput()`은 단순 입력 저장이고, 실제 회전력은 완전히 별개 메커니즘인
  **`TorqueControl.YawTorqueScaling`**이 만듦:
  ```cpp
  TotalTorque += VehicleState.VehicleUpAxis * ControlInputsPT.YawInput * TorqueControl.YawTorqueScaling;
  AddTorqueInRadians(TotalTorque, true, true); // bAccelChange=true → 관성 텐서로 자동 정규화된 각가속도
  ```
- `TorqueControl.Enabled`/`YawTorqueScaling` 모두 **엔진 기본값이 0/false** — `MaxTurningSpeed`/
  `YawInputRate`는 입력 램프업 속도만 조절할 뿐, 실제 토크 크기와는 무관함.
- 우리 인스턴스는 `Enabled=true`, `YawTorqueScaling=3`으로 이미 설정되어 있었음(마켓플레이스
  기본값) — 이 값을 **20**으로 올려서 조향 반응성 개선 완료.
- **진짜 조향 속도 다이얼은 `VehicleMovementComp.TorqueControl.YawTorqueScaling`** — 필요시
  이 값 하나만 조정하면 됨.

---

## 7. 회전 속도 커스터마이징 노출

- `MaxTurningSpeed`: 45 → 90 (`BP_UGVFromTank` 자체 인스턴스, `TurningSpeedLimit()`이 참조하는
  각속도 상한 — 이 값 도달 시 조향 입력을 0으로 끊는 거버너).
- `VehicleMovementComp.YawInputRate`: RiseRate/FallRate 2.5/5 → 6/10 (입력 램프업 속도, 스로틀과
  동일하게 맞춤).
- 포탑 회전 속도(`AC_WeaponTank.Weapons[0].turretRotationSpeed`/`gunRotationSpeed`): 40/10 →
  120/120 — 카메라 팬/틸트 속도(90°/sec, `Atitan_examplePlayerController::
  CameraLookRateDegPerSec`)보다 약간 빠르게 맞춰서 좌우 2배·상하 5배 차이 해소.
  `BP_UGVFromTank` 자체 오버라이드 배열이라 원본 M1A2엔 영향 없음.
- **`BP_UGVAIController`** (`AUGVAIController`의 블루프린트 서브클래스, `/Game/Vehicles/UGV/
  ChaosFromTank/BP_UGVAIController`) 신규 생성 — `AUGVAIController`의 EditAnywhere 프로퍼티
  전부(조향/AI pursuit 튜닝값 + 아래 8절 도로 관련 값)가 여기서 Class Defaults로 편집 가능.
  `BP_UGVFromTank.AIControllerClass`를 이걸로 교체함.

---

## 8. 오프로드 감속 + 도로 이탈 강제 복귀 (2026-07-16)

옛 `AUGVPawn`/`UUGVMovementComponent`에 있던 두 기능을 `AUGVAIController`로 포팅(Chaos 차량은
그 컴포넌트 자체가 없어서 새로 구현):

- **오프로드 감속**: `UpdateOffRoadSpeedDecay()` — 폰 위치 기준 `RoadSurfaceTag`("RoadSurface")
  태그가 붙은 컴포넌트와의 오버랩 체크(옛날의 4점 트랙 체크 대신 단순화된 1점 체크, Chaos엔
  트랙별 힘주입 개념이 없어서). 도로 위가 아니면 매틱 전진 속도의 일정 비율(기본 1%,
  `OffRoadSpeedDecayPerTick`)을 직접 깎음 — 힘이 아니라 속도 직접 편집이라 어떤 스로틀
  모델이든 무관하게 작동.
- **도로 이탈 강제 복귀**: `UpdateRoadBoundary()` — `BeginPlay`에서 레벨의 `RoadNavMod`
  볼륨(`AreaClass=UNavArea_Road`)들을 캐싱해두고, 매틱 그 중 가장 가까운 지점까지 거리 계산.
  `MaxRoadDistance`(기본 400m) 초과 시 그 지점 지면으로 텔레포트 + 속도/각속도 리셋 +
  `OnLeftDesignatedArea` 이벤트 + 화면 메시지.
- 둘 다 `DriveMode`(Auto/Manual) 무관하게 항상 적용 — 옛 `AUGVPawn`도 이 둘은 possess/드라이브
  모드 무관하게 항상 돌았던 것과 동일하게 맞춤.
- `AWheeledVehiclePawn` 타입 체크로 게이팅해서 기존 `AUGVPawn`(이미 자기 버전 있음)에는
  이중 적용 안 됨.

---

## 9. RCWS / 포탑 연동

- **핵심 아이디어**: M1A2의 기존 `AC_WeaponTank` 컴포넌트(포탑/포신 조준 시스템, `BP_Tank`에
  정의됨)를 그대로 재사용 — `TargetPoint`(월드 좌표 조준 목표)만 매 틱 RCWS 쪽에서 넣어주면
  `TurretGunRotation()`이 알아서 포탑/포신을 그 방향으로 부드럽게 회전시킴.
- `BP_UGVFromTank`에 RCWS 관련 컴포넌트 신규 추가: `RCWSMount`(빈 씬 컴포넌트), `RCWSSightCamera`
  (`USceneCaptureComponent2D`), `RCWS`(`URCWSComponent`), `TargetDetection`
  (`UTargetDetectionComponent`), `RCWSFireControl`(`URCWSFireControlComponent`),
  `DetectableTarget`(`UDetectableTargetComponent`), `Muzzle`(빈 씬 컴포넌트, 실제 총구 소켓
  트래킹용).
- 이 컴포넌트들은 전부 오너 클래스를 가정하지 않고 이름 기반 `FComponentReference`로 대상을
  찾는 설계라(기존 코드베이스 확립된 패턴) BP에 이름만 맞춰 추가하면 C++ 수정 없이 바로
  작동함.
- `BP_UGVFromTank`의 EventGraph `Event Tick`에 신규 로직 추가(MCP `create_node`+`connect_pins`로
  직접 그래프 편집):
  1. `RCWS->GetSightWorldLocation()`/`GetSightWorldRotation()`으로 카메라가 보는 방향 계산 →
     `AC_WeaponTank->GetMaxAimDist()`만큼 앞선 지점을 `AC_WeaponTank->SetTargetPoint()`로 전달.
  2. `VehicleMesh`의 `M1A2Socket`(실제 포신 끝, `SkeletalMeshTools`로 본 계층 확인함:
     `body → turret → main_gun`, 소켓은 `main_gun`에 부착) 소켓 위치/회전을 매틱
     `Muzzle` 컴포넌트에 `SetWorldLocationAndRotation`으로 복사 — 진짜 SCS 소켓 부착 도구가
     MCP에 없어서 이 방식으로 대체.
- `Atitan_examplePlayerController`/`Monitor1Widget`의 RCWS 관련 Resolve 함수들을 전부 갱신 —
  기존 `AUGVPawn` 우선 탐색, 없으면 `FindComponentByClass`로 `BP_UGVFromTank`(via
  `UGVTankRef`)에서 대신 찾도록 일반화(`FindUGVRCWS`/`FindUGVFireControl` 등).

---

## 10. 사격 시스템

- `RCWSFireControl` 컴포넌트 추가 시 필요한 애셋들 옛 `BP_UGV`에서 그대로 복사: `ProjectileClass`,
  `MuzzleFlashEffect`, `FireSound`, 반동 관련 값(`RecoilImpulseMagnitude`,
  `RecoilMountKickPitchDegrees`, `RecoilMountKickYawJitterDegrees`).
- 총구 발사 이펙트에 나이아가라 지원 추가 — `MuzzleFlashNiagaraEffect`(`UNiagaraSystem*`) 신규
  프로퍼티, 기존 Cascade `MuzzleFlashEffect`와 독립적으로 둘 다 발사 가능.
- **자동발사 게이팅을 실제 포탑 각도 기준으로 변경**: 기존엔 RCWS 마운트(카메라)의 명령 방향만
  기준으로 `bIsLockedOn`을 판정했음 — 실제 포탑(AC_WeaponTank가 구동하는 물리 본)이 아직
  따라오는 중이어도 발사됨. `GetMuzzleWorldRotation()`(실제 총열 소켓의 현재 트랜스폼)까지
  추가로 확인하도록 수정, 허용오차는 `AutoFireTurretAlignmentToleranceDeg`(기본 2°).
- **반동을 실제 포탑에도 적용**: 기존엔 RCWS 마운트만 반동 킥을 받았음(카메라가 흔들림) —
  포탑/포신은 마운트와 물리적으로 분리된 별개 조립체라 실제로는 흔들리지 않았음. 발사 시 같은
  랜덤 킥 값을 `AC_WeaponTank`의 `TurretRotCur[0]`/`GunRotCur[0]`(현재 회전 상태를 담는 내부
  배열 변수, 리플렉션으로 직접 조작)에도 적용 — 다음 프레임부터
  `TurretGunRotation()`의 `RInterpTo_Constant`가 원래 목표로 자연스럽게 되돌림(킥+복귀 효과가
  별도 로직 없이 공짜로 나옴).

---

## 11. 사운드 버그 (두 번 수정)

**증상**: 총알 피격/발사 사운드가 거리와 무관하게 항상 같은 볼륨으로 재생됨.

**1차 시도(실패)**: `SpawnSoundAtLocation`이 어테뉴에이션 애셋 없이 호출되면
`AudioComponent->bAllowSpatialization`을 false로 설정한다고 판단해서, 스폰 직후 수동으로
`true`로 재설정 + `AdjustAttenuation()` 호출. **효과 없었음.**

**진짜 원인**: `SpawnSoundAtLocation`은 리턴하기 *전에* 내부적으로 `AudioComponent->Play()`를
이미 호출함. `Play()`가 "이 사운드에 어테뉴에이션을 적용할지"(`bHasAttenuationSettings`)를 그
순간 확정해버리는데, 이때는 아직 `AdjustAttenuation()`을 호출하기 전이라 어테뉴에이션 없음으로
굳어짐. 함수가 리턴한 *후에* 부르는 `AdjustAttenuation()`은 이미 재생 중인 사운드에 값만 밀어
넣을 뿐, "쓸지 말지" 플래그 자체는 못 바꿈.

**진짜 수정**: `SpawnSoundAtLocation` 호출 *전에* 진짜 `USoundAttenuation` 오브젝트를 런타임
생성(`NewObject<USoundAttenuation>`, 첫 발사/피격 때 한 번만 만들고 재사용)해서 파라미터로
직접 전달. `ARCWSProjectile::ImpactSoundAttenuationAsset`, `URCWSFireControlComponent::
FireSoundAttenuationAsset` 두 곳 모두 동일 패턴으로 수정.

---

## 12. 궤도/바퀴 시각 효과 — 조사만 함 (향후 UGV 모델 참고용)

M1A2가 어떻게 궤도를 표현하는지 실제 노드 그래프 추적으로 확인:

- **궤도(캐터필러) 본체**: `UseGeometricTracks=true`, `TrackStaticMeshes` 배열에 링크 메시
  4종(`SM_M1A2_Track_01~04`). `InstanceTracksCreation` 함수가 Construction Script에서
  `AddInstancedStaticMeshComponent`로 **`UInstancedStaticMeshComponent`를 런타임 생성**,
  `TracksAmount=76`개 인스턴스 배치. `SetTracksTransform`이 매틱 `UpdateInstanceTransform`을
  인스턴스별로 호출해서 스플라인 기반 위치/회전 갱신 — **진짜 지오메트리가 실제로 움직이는
  체인**임(UV 스크롤이 아님, 처음에 잘못 판단했었음).
  - 성능이 괜찮은 이유: ISM은 메시 종류당 드로우콜 1개(76개 인스턴스 → 최대 4개 드로우콜),
    `UpdateInstanceTransform`은 가벼운 버퍼 갱신이라 76개 정도는 부담 없음.
- **바퀴**: `WheelRotationDefinition`이 미끄럼 없는 구름 공식(각도=이동거리/반경)으로 실제
  스켈레탈 본을 회전시킴(로드휠/스프로킷), 추가로 표면 디테일용 UV 보정도 살짝 얹는 하이브리드.
- **스플라인**: 개별 링크 배치의 실제 기준선(위 ISM 배치가 이걸 따름) + 바퀴 사이 처짐/진동
  연출(`SaggingCalculation`/`VibrationCalculation`)에 사용.

**향후 UGV 적용 시 실전 요약**:
- 직선 구간 대부분: 링크 메시 여러 개를 ISM으로 스플라인 따라 배치하는 방식(M1A2와 동일)이
  검증된 방법. World Position Offset(높이맵+UV스크롤) 트릭으로 대체하는 것도 가능하고 더
  저렴할 수 있지만, **바퀴/스프로킷을 감아 도는 구간**은 개별 링크가 살짝씩 다른 각도로 꺾이며
  각지게 감기는 느낌이 진짜 리지드 인스턴스 없인 재현이 어려움 — 그 구간만 ISM, 나머지는
  WPO로 하이브리드도 고려 가능.
- 바퀴는 실제 본 회전(거리/반경 공식) + 필요시 표면 디테일 UV 보정.

---

## 13. 트랙/서스펜션 애니메이션이 멈췄던 버그 (2026-07-16)

**증상**: RCWS 작업 이후 어느 시점부터 궤도 스크롤/서스펜션 움직임이 완전히 멈춤 — 원인
불명으로 사용자가 발견.

**원인**: 9절에서 `BP_UGVFromTank`에 RCWS용 `Event Tick` 노드를 새로 만들면서, 부모
(`BP_VehicleBase`)가 이미 갖고 있던 자기 `Event Tick`(매틱 `VehicleTick()` 함수를 호출 —
이게 바로 `BP_Tank`가 오버라이드하는 트랙/서스펜션 애니메이션 로직)을 완전히 덮어써버림.
블루프린트는 자식이 `Event Tick`을 새로 만들면 "Parent: Event Tick" 호출 노드를 명시적으로
넣지 않는 한 부모 로직이 자동으로 이어지지 않음(C++ 가상함수와 다름).

**수정**: "Parent: Event Tick" 노드 자체는 MCP 툴로 생성 불가(찾아지지 않음) — 대신 부모가
실제로 하는 일을 재현: 우리 Tick 체인 맨 앞에 `SetDeltaSeconds(DeltaSeconds)` →
`VehicleTick()` 호출을 추가하고, 그 뒤에 기존 RCWS 로직이 이어지도록 재배선.
`VehicleTick()`이 내부적으로 `DeltaSeconds` 클래스 변수를 읽어서 트랙 이동 거리를 계산하는
구조라 이 변수를 먼저 세팅해주는 게 필수였음.

**교훈**: 블루프린트 자식 클래스에 `Event Tick`/`Event BeginPlay` 등 네이티브 이벤트 오버라이드를
새로 만들 때는 항상 부모가 같은 이벤트를 이미 쓰고 있는지 확인하고, 있으면 "Parent: 함수" 호출을
반드시 넣을 것 (이번엔 `BeginPlay`는 이미 제대로 되어 있었고 `Tick`만 빠뜨렸었음).

---

## 14. WBP 대시보드 연동 (WBP_kadex / Monitor1Widget)

- `Monitor1Widget`이 옛 `AUGVPawn`(`UGVRef`) 하드코딩 구조였던 걸, `BP_UGVFromTank`용
  `UGVTankRef`(`APawn*`, `Atitan_examplePlayerController::FindUGVFromTankInstance`로 탐색)를
  같이 두고 RCWS/TargetDetection/FireControl/UGVStatus 전부 "UGVRef 없으면 UGVTankRef에서
  `FindComponentByClass`로 대신 찾기" 패턴으로 일반화.
- RCWS 조준 화면, 모드 텍스트, 방위각/고각/줌 리본, 조준점 마커(`RCWSAimPointWidget`, 탄도
  보정 지점) 전부 자동 연동됨.
- **실제 포탑이 현재 보는 방향 실시간 표시**: 기존 크로스헤어 PNG(WBP에 이미 배치되어 있던
  것)를 매프레임 이동시키도록 구현. `RCWSFireControlComponent::GetTurretReticleScreenUV()`가
  `GetMuzzleWorldRotation()`(실제 포신 소켓 방향) 기준으로 먼 지점을 잡아 RCWS 시야 카메라
  화면 좌표로 투영, `Monitor1Widget`이 `RCWSTurretReticleImage`(신규 `UImage*` 필드,
  BindWidgetOptional)를 그 좌표로 `UCanvasPanelSlot::SetPosition`. 매 프레임 부드럽게 움직이게
  하려고 스로틀되는 `RefreshRCWSPanel()`이 아니라 언스로틀 `RefreshSmoothValues()`에 배치.
  - (참고: 처음엔 "azimuth/elevation 리본에 보조 마커를 추가"하는 걸로 잘못 구현했다가
    사용자 피드백으로 롤백 — 원하는 건 화면 중앙 크로스헤어를 실제로 움직이는 것이었음.)
- **속도/기어 대시보드**: `BP_UGVFromTank`에 `UGVStatus`(`UUGVStatusComponent`) 신규 추가,
  `AUGVAIController::UpdateTankUGVStatusData()`가 매틱 Chaos 고유 API(`GetForwardSpeed()`,
  `GetCurrentGear()`, `IsParked()`, `TransmissionSetup.ForwardGearRatios.Num()`)로 옛
  `AUGVPawn::UpdateUGVStatusData`와 동일한 포맷(속도 km/h, P/R/N/1~4 기어 라벨, 최대기어)을
  채움. `Monitor1Widget::RefreshUGVPanel()`도 동일 패턴으로 폴백 추가 — WBP 그래프 수정 없이
  기존 위젯 이름(`UGVSpeedText`/`UGVCurrentGearText`/`UGVMaxGearText`) 그대로 재사용됨.

---

## 15. 알려진 이슈 / 남은 작업

- 레벨에 배치된 `BP_UGVFromTank` 인스턴스의 `AIControllerClass`가 CDO 변경 이전 값으로 박제되는
  문제가 예전에 한 번 있었음(6절에서 `BP_UGVAIController`로 교체한 것도 같은 리스크) — 레벨
  열어서 실제 값 확인 필요.
- 궤도/바퀴 애니메이션은 M1A2 원본 지오메트리 기준이라, 디자인팀 UGV 모델이 나오면 12절 방식
  중 하나로 다시 구현해야 함(그대로 재사용 불가 — 메시가 다름).
- `AC_WeaponTank`가 `BP_Tank`에 정의된 컴포넌트라 리플렉션 경로가 서브클래스가 아닌 정의
  클래스(`BP_Tank`) 기준이어야 함 — 나중에 비슷한 상속 컴포넌트 다룰 때 참고
  (`/Game/EvolveStudio/.../BP_Tank.BP_Tank_C:AC_WeaponTank_GEN_VARIABLE` 형태).
- 오프로드/도로 경계 로직(8절)은 방금 추가되어 재빌드 후 실제 테스트 필요.

---

## 파일 목록

**C++ (Source/titan_example/Vehicles/)**
- `UGVAIController.h/.cpp` — 헤드리스 PlayerController 기반 AI 컨트롤러. 경로탐색, pure-pursuit,
  드라이브모드, 오프로드/도로경계, UGV 상태 대시보드 데이터, 리플렉션 디스패치
  (`DispatchSetManualControl`/`DispatchSetBraking`) 전부 여기.
- `RCWSComponent.h/.cpp`, `RCWSFireControlComponent.h/.cpp`, `RCWSProjectile.h/.cpp`,
  `RCWSTypes.h` — 기존 RCWS 시스템, 오너 클래스 비의존적 설계라 그대로 재사용.
- `NavArea_Road.h/.cpp` — 도로 NavMesh 영역 클래스 (옛 UGV용, 그대로 재사용).
- `UGVPawn.h/.cpp`, `UGVMovementComponent.h/.cpp` — 옛 네이티브 UGV, 안 건드림·삭제 안 함
  (포팅 원본 참고용으로 계속 유지).
- `UGVChaosPawn.h/.cpp`, `UGVChaosWheel.h/.cpp` — 폐기된 커스텀 메시 시도, 참고용 보존.

**C++ (Source/titan_example/UI/)**
- `Monitor1Widget.h/.cpp` — WBP_kadex 백엔드, UGVTankRef 폴백 전부.
- `UGVStatusComponent.h/.cpp` — 속도/기어 데이터 싱크(오너 비의존).
- `ScrollingRulerWidget.h/.cpp` — 방위각/고각/줌 리본 (건드렸다가 롤백, 원상태).
- `AimPointWidget.h/.cpp` — 탄도 보정 조준점 마커(기존 그대로).

**블루프린트**
- `/Game/Vehicles/UGV/ChaosFromTank/BP_UGVFromTank` — 메인 UGV 폰.
- `/Game/Vehicles/UGV/ChaosFromTank/BP_UGVWheel_FromTank` — 바퀴.
- `/Game/Vehicles/UGV/ChaosFromTank/BP_UGVAIController` — `AUGVAIController` 블루프린트
  서브클래스, 모든 튜닝값 노출용.
