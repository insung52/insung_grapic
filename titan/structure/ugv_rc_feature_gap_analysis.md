# UGV RC 프로토콜 — ICD 커맨드 ↔ 실제 구현 갭 분석 (2026-08-16)

`lig_icd_ugv_rc_full.md`(1차 소스)의 cmd 하나하나를 `Network/UGVRemoteControlSubsystem.*`(UE
C++) 구현 및 그 아래에 깔린 실제 게임 기능(RCWS/차량/탐지 등)과 1:1 대조한 결과. **목적은
"cmd가 코드에 있냐"가 아니라 "그 cmd를 보내면 실제로 뭔가 달라지냐"** — 핸들러 함수는 존재해도
내부적으로 라벨만 바꾸고 끝나는 경우(no-op)가 여럿 있어서 이 구분이 중요함.

상태 기호:
- ✅ 실동작 — 실제 게임 상태/물리/렌더에 영향
- ⚠️ 근사/부분 — 뭔가는 하지만 ICD 의미와 정확히 안 맞거나 단순화됨
- 🔶 더미 — 값은 나가지만 실제 소스가 없는 시뮬레이션(시간 경과 등으로 그럴듯하게만)
- ❌ 미구현 — 라벨/상태값만 바뀌고 실제 효과 없음, 또는 로그만 찍는 스텁

---

## 1. UGV → RC (우리가 보내는 메시지)

| cmd | 필드 | 실제 소스 | 상태 | 비고 |
|---|---|---|---|---|
| `UGV_Response_Connection` | `ResponseDevice` | `Handle_RC_Connection` 즉시 응답 | ✅ | |
| `UGV_Period_Basicinfo` | `OperationMode` | `AUGVAIController::GetDriveMode()` 매핑 | ✅ | Idle/Manual/Auto → Stay/Remote/HAD, 실제 DriveMode 반영 |
| | `ConrtrolRight` | `bControlRightHeldByRC` | ✅ | |
| | `Speed` | `UUGVStatusComponent`(실측, Chaos `GetForwardSpeed()`) | ✅ 실측 | |
| | `Gear` | `GearLabel`("P"/"R"/"N"/"1".."5") → Front/Back 매핑 | ⚠️ 근사 | `Turn`은 절대 안 나옴 — 실사용 BP_UGV_Vehicle이 Chaos 휠드라 제자리선회 개념 자체가 없음 |
| | `Batterry` | `UUGVStatusComponent::GenerateDummyData` | 🔶 더미 | 시간 경과로 초당 0.03%씩 깎일 뿐, 실제 전력 소모(주행/발사 등)와 무관 |
| `UGV_Response_BIT` | `StatusVMU` | 항상 `"ON"` 고정 | 🔶 더미 | 실제 VMU 헬스체크 소스 없음 |
| | `CountValue` | `RequestBit` 그대로 echo | ✅ | |
| `UGV_RCWS_Status` | `RCWSStatus` | RCWS 컴포넌트 resolve 성공 여부 | ⚠️ 근사 | "원격통제기와 실제 접속됐는지"가 아니라 "컴포넌트가 존재하는지"만 봄 — 사실상 항상 ON |
| `UGV_Period_ObjectDetectionResult` | `TotalObject`/`Objects[]` BBox·Faction | `UTargetDetectionComponent`(실측 탐지) | ✅ 실측 | 카메라 시야각/거리 기반 실제 탐지 |
| | `ObjectID` | 신규 부여(액터당 안정 ID) | ✅ (신규 구현) | ICD에 대응 개념 없어 이번에 추가 |
| | `ObjectClass` | `Cast<ACharacter>` 여부 | ⚠️ 근사 | Human/Car 2종 판정만, 실제 차량 타입 구분 없음(트럭/UGV/일반차량 다 "Car") |
| | East/North/Zone/Letter | `GeoCoordinateUtils::WorldLocationToUTM` | ✅ (계산은 실측) | UTM Zone/Datum 자체가 실측 대조 안 된 값(§`protocol_icd.md` §6 기존 미확정 항목) |
| | `Velocity`(객체별) | `GetVelocity().Size()` | ✅ 실측 | 단위는 우리 추정(m/s) |
| | `Altitude`(객체별) | 항상 `0` | ❌ 미구현 | 이 프로젝트에 고도 캘리브레이션 자체가 없음(`GeoCoordinateUtils`는 lat/lon 평면만) |
| `UGV_Response_BIT_ADU` | `StatusADU`/`StatusVMU`/`StatusNavigation`/`Status3DLidar`/`StatusRadar`/`StatusOCS` | 전부 `"On"` 고정 | 🔶 더미 | 실제 ADU/센서 헬스 소스 없음(ADU 자체가 현대로템 실물이라 우리는 흉내만 냄) |
| `UGV_Period_BasicInformation` | `Odometer` | `UUGVStatusComponent::DistanceTraveledKm`(실측 누적) | ✅ 실측 | |
| `UGV_Period_NavigationInformation` | East/North/Zone/Letter | 실측 위치 → UTM | ✅ (계산은 실측) | 위와 동일 정확도 이슈 |
| | `Velocity` | 실측 | ✅ | |
| | `Heading` | `GeoCoordinateUtils::SceneYawToBearingDegrees` | ✅ 실측 | |
| | `Altitude` | 항상 `0` | ❌ 미구현 | 위와 동일 |

---

## 2. RC → UGV (우리가 받는 메시지)

| cmd | 필드 | 실제로 뭘 건드리는지 | 상태 | 비고 |
|---|---|---|---|---|
| `RC_Connection` | `RequestDevice` | 핸드셰이크 응답 트리거 | ✅ | |
| `RC_Request_BIT` | `RequestBit` | BIT 응답 트리거 | ✅ | 응답 내용 자체는 더미(위 1번 표 참고) |
| `RC_Control_Right` | `ControlRight` | `bControlRightHeldByRC` | ✅ | |
| `RC_RemoteDriving` | `Acceleration`/`Brake`/`Steering`/`Gear` | `AUGVAIController::DispatchSetManualControl`/`DispatchSetBraking` | ✅ 실동작 | 이번 세션 로컬 테스트에서 실제 주행 확인(초반 1~2초는 반응, 이후 지속 가속에도 속도가 0으로 떨어지는 현상 관찰됨 — **원인 미조사 상태**, 다만 WASD 수동주행은 정상이라 프로토콜 레이어 문제는 아닌 것으로 보임, 차량 자체 로직 쪽 확인 필요) |
| `RC_EmergencyStop`/`RC_EmergencyStopRelease` | `CommandDevice` | `bEmergencyStopActive` 래치 → `DriveMode=Idle`+브레이크 | ✅ (최소 구현) | "정지"만 함 — 강제 전원차단 등 그 이상의 안전장치는 없음(그런 게 ICD에도 없음) |
| `RC_OperationMode` | `OperationMode` | `RequestedOperationMode` → `DriveMode` | ✅ | |
| `RC_SelectCamera` | `SelectCameraButton` | `RCWS->SetCameraMode` → `ApplyCameraModeVisuals`(`SightCineCamera`에 IR 포스트프로세스 블렌더블) | ✅ 실동작(2026-08-16 구현) | 야간투시경 스타일(밝은곳 그대로/어두운곳 밝기증폭+흑백+녹색틴트, `M_PP_RCWS_IR`). RCWS 뷰어 한정 적용(UGV+TitanTruck 둘 다), QuadCam 등 다른 화면엔 영향 없음(§3 참고) |
| `RC_FireMode` | `FireMode` | `RCWSFireControlComponent::TickComponent`(트리거 사이클 카운팅) | ✅ 실동작(2026-08-16 구현) | 단발=사이클당 1발, 점사=`BurstRoundCount`발, 연사=기존 그대로. 트리거(`bWantsToFire`)가 새로 켜지는 순간을 "새 사이클"로 리셋 |
| `RC_ChargeWeapon` | `ChargeSwitch` | `RCWS.CurrentData.bLoaded` | ✅ 실동작 | `CanFire()` 게이팅에 실제로 쓰임. 단, "장전"은 발사 가능 여부 스위치일 뿐 탄약 리필이 아님(`AmmoCurrent`는 `ConsumeAmmo`로만 깎이고 되채우는 함수가 없음 — 그게 ICD 의도와 맞는지는 확인 필요) |
| `RC_FireWeapon` | `FireButton` | `RCWSFireControlComponent.bManualFireHeld` | ✅ 실동작 | 발사 자체의 배럴스핀 딜레이는 2026-08-16부로 `RC_ActivateFire`(아래) 쪽으로 옮겨짐 — 안전 해제된 상태(`bFireSystemActive`)면 방아쇠는 스핀업 딜레이 없이 즉시 발사 |
| `RC_MotionMode` | `MotionMode` | 로그만 찍음 | ❌ 스텁 | ICD 설명("기동 모션 모드 설정")이 짧아 대응 게임 기능 자체를 특정 못 함 |
| `RC_Movement` | `BrakeButton`/`XAxis`/`YAxis` | `URCWSComponent::AddPanTiltInput` | ✅ 실동작 | 조이스틱 값→각도 변환 감도(`RCWSMovementDegreesPerUnit`)는 우리 임의 설정(ICD에 게인 명시 없음) |
| `RC_ActivateFire` | `ActivateFireToggle` | `RCWSFireControlComponent::bFireSystemActive`(안전/암 스위치) | ✅ 실동작(2026-08-16 재해석) | RC_FireWeapon(방아쇠)과 별개 커맨드 — RELEASE=안전 해제(암), PRESSED=안전(SAFE). 켜지는 순간 배럴이 미리 아이들 스핀업, 꺼지면 방아쇠 당겨도 무조건 발사 안 됨. 이전엔 "스텁, 의미 불명"으로 기록했었는데 재검토 후 이 용도로 확정 |
| `RC_ActivateMovement` | `ActivateMovementToggle` | RCWS 조향 게이트(`UUGVRemoteControlSubsystem::bRCWSSteeringActivated` -> `Handle_RC_Movement`의 AND 게이트) | ✅ **재매핑 완료(2026-08-31)** | 2026-08-16엔 "구동 상태 설정"이라는 이름만 보고 차량 시동/이그니션(`AUGVAIController::bEngineOn`)으로 추정해 구현했는데, **LIG 확인 결과 실제로는 "RCWS 조향(pan/tilt) 모터 활성화" 커맨드**임 — 차량 엔진과 무관. 2026-08-31에 `bEngineOn` 배선을 제거하고 `bRCWSSteeringActivated` 래치로 재배선, `Handle_RC_Movement`에서 `RC_Movement.BrakeButton`과 **AND**(둘 다 `RELEASE`=활성일 때만 `AddPanTiltInput` 호출)로 묶음. 자체방호축 로컬 조이스틱 경로(`bRCWSMovementBraked`)는 건드리지 않음 — 이 게이트는 네트워크 경유 UGV축 전용. `bEngineOn`은 콘솔/BP 전용 개념으로만 남김(`Atitan_examplePlayerController::SetUGVEngineOn`) — **차량 시동/이그니션에 대응하는 별도 프로토콜 커맨드가 있는지는 여전히 미확인, LIG 재질문 중(`lig_questions_0816.md` 1-신규-2)**. |
| `RC_Connection_ADU` | `RequestDevice` | ADU 핸드셰이크 응답(형식만) | ✅ (형식만) | ADU 자체 시뮬레이션이 없어서 응답은 항상 고정값 |
| `RC_Request_BIT_ADU` | `CountValue` | BIT_ADU 응답 트리거 | ✅ (형식만) | 응답 내용은 더미(위 1번 표) |

## 2-1. 자율주행 미션 커맨드 — UGV_RC_ICD엔 없음, 우리 확장으로 추가 (2026-08-16)

확인 결과 **`RC_OperationMode`엔 STAY/REMOTE/EMERGENCY뿐, FAD/HAD(자율주행)로 전환시키는
커맨드 자체가 UGV_RC_ICD에 없음** — "여기로 자율주행해"에 해당하는 목적지/좌표 필드를 가진
커맨드가 아예 없다. 원래 이 역할은 프로젝트 내부 `UScenarioStateSubsystem`이 대신하고 있었는데,
**"내부 시나리오 시스템은 외부(원격통제기/상위체계)와의 실제 통신을 흉내내던 임시방편이었고,
이제 그 역할은 진짜 외부 통신이 가져가야 한다"는 방향으로 결정**(2026-08-16 세션) — 구조상
UGV SW는 LIG 원격통제기를 거쳐야만 상위체계와 연결되므로, 새 소켓을 열지 않고 기존 RC
채널(8000~8011)에 얹었다.

| cmd | 방향 | 필드 | 상태 |
|---|---|---|---|
| `HQ_MissionMoveToEngage` | RC→UGV(우리 확장) | `East`/`North`/`Zone`/`Letter`(UTM), `Radius`(m) | ✅ 구현(`Handle_HQ_MissionMoveToEngage` → `AUGVAIController::MoveToDestination`) |
| `RPT_ObjectiveReached` | UGV→RC(우리 확장) | `Radius`(m, 요청받은 값 그대로 echo) | ✅ 구현(`IsMoving()` true→false 전환 감지, `TickPoll`에서 폴링) |

원문은 `protocol_icd.md` §5 "Layer A"(상위체계↔UGV, LIG도 아직 미확정) 초안에서 그대로 가져옴 —
cmd 이름(`HQ_`/`RPT_` 접두어)도 LIG의 `RC_`/`UGV_` 스킴과 구분되게 일부러 그대로 유지했음.
**LIG 확정 스펙이 전혀 아니므로 다음 문의 리스트에 반드시 포함** — 이름/필드/포트분류(지금은
이벤트 포트로 보냄) 전부 우리 임의 결정.

---

## 3. 반대 방향 — 게임엔 있는데 ICD에 원격 커맨드가 없는 기능

ICD가 "원격통제기가 수동으로 다 조작한다"는 전제로만 짜여있어서, 실제 프로젝트에 이미 구현된
아래 기능들은 **LIG 프로토콜로 원격 제어할 방법 자체가 없음**(우리가 안 만든 게 아니라 ICD에
그 커맨드가 없음):

- **RCWS 줌**(`AddZoomInput`/`SetZoomLevel`, 0.5~16배 6단계) — 원격 줌 커맨드 없음.
- **RCWS 안정화 on/off**(`bStabilizationEnabled`) — 원격 토글 커맨드 없음.
- **`ERCWSControlMode`(Remote/AutoSurveillance/AutoAim/AutoFire) 전환** — ICD의 `RC_FireWeapon`/
  `RC_Movement`는 전부 "Remote(완전 수동)" 모드를 전제로 한 조작이고, RC가 UGV를
  AutoAim/AutoFire 모드로 원격 전환시키는 커맨드가 없음. 즉 지금 ICD만으로는 UGV RCWS를
  자동조준/자동사격 모드로 원격으로 못 바꿈(로컬 조이스틱/콘솔로만 가능).
  **(2026-08-17)** 애초에 요구사항에 없던 임의 확장이라, 조이스틱 포커스가 다른 RCWS로
  옮겨갈 때 자동으로 Remote↔AutoSurveillance를 전환시키던 로직
  (`SyncRCWSControlModeForCameraTarget`)은 완전히 비활성화(no-op)함 — 테스트 중 클라이언트
  접속 시 공유 UGV RCWS가 의도치 않게 AutoSurveillance로 튀는 버그가 있었고, 트럭
  RCWS↔UAV 짐벌 전환에도 같은 이유로 재발 방지 차원에서 동일 적용. 이제 모든 RCWS는
  스폰 시 기본값(`Remote`) 그대로 계속 유지되며, 모드 전환은 콘솔(`SetRCWSMode`)이나
  시나리오 스텝(`SetUGVAutoSurveillance` 등 명시적 스크립트)으로만 발생함.

이 갭들은 "우리가 못 만든 것"이 아니라 **ICD 자체의 표현 범위 밖**이라 LIG 확인이 필요한
항목으로 분류하는 게 맞아 보임.

---

## 4. 종합 우선순위

**진짜 작동, 신뢰 가능**: 연결/BIT 핸드셰이크, 제어권, 주행모드 전환, 실제 주행(단 지속주행 시
정지 현상 조사 필요), 비상정지, RCWS pan/tilt, 장전 게이팅+발사, 발사모드(단발/점사/연사),
안전/암 스위치(`RC_ActivateFire`), IR 카메라(RCWS 뷰어 한정, 야간투시경식 밝기증폭 포함),
탐지 결과(BBox/Faction/속도), 주행거리(Odometer), 실측 위치/속도/헤딩.

**LIG 답변으로 틀린 것으로 확인됐다가 재작업 완료(✅, 2026-08-31)**: `RC_ActivateMovement` —
차량 시동이 아니라 RCWS 조향 모터 활성화였음. `bEngineOn` 배선 제거 + `bRCWSSteeringActivated`
래치를 `RC_Movement.BrakeButton`과 AND로 묶어 `AddPanTiltInput` 게이팅으로 재배선. 위 §2 표 참고.

**의도적으로 구현하지 않음(2026-08-31 결정)**: 통신 두절 워치독(`RELEASE` 유실 시 자동 사격
중단, 주행/조준 갱신 끊김 시 자동 안전 정지). LIG가 §2 답변에서 "`RELEASE` 신호 유실 시 사격
상태로 남겨지는 내용은 현재 진행한 사업에서는 고려하지 않고 개발된 것으로 알고 있다"고 확인해준
사항 — 실장비에 없는 안전 로직을 우리 쪽에만 넣으면 동작이 어긋나는 게 더 큰 문제라, 프로토콜
동작(`PRESSED`/`RELEASE` 이벤트 상태천이)을 그대로 따르기로 함. 한 번 구현했다가 되돌린 이력이
있으니 다시 넣지 말 것.

**라벨만 있고 실제 효과 없음(❌, 구현 필요 시 별도 작업)**:
1. **`RC_MotionMode`** — 의미 자체가 ICD상 불명확해서 여전히 스텁 상태.

**더미 시뮬레이션(🔶, 실제 헬스체크 소스가 생기면 교체 필요)**: `StatusVMU`, `StatusADU` 등 BIT
계열 상태값 전부, `Batterry`(시간 경과로만 깎임).

**완전 미구현(❌, 다른 트랙 영역)**: 고도(`Altitude`, 항상 0), RTSP 영상 송출(별도 트랙에서
PoC 진행 중, 이 코드베이스엔 아직 한 줄도 없음 — `titan_examplePlayerController.h`에 "아직
미구현"이라고 명시돼 있음).
