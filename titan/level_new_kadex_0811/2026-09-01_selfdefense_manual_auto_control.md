# 자체방호축 수동/자동 조종 — "시네마틱 + 개입 가능"

2026-09-01 / 진행중(코드 1차 완료, 빌드·WBP 배치·DT 마무리 대기) / 기본은 전자동 시네마틱, 사용자가 체크박스로 UAV 또는 트럭 RCWS 하나를 수동으로 넘겨받는 구조.

관련: `2026-09-01_scenario_run_modes_demo_fullsystem.md`(데모/풀 실행 모드 — **이것과는 직교**),
`vehicle/drone/drone_flight_dev_guide.md`, `replication/2026-09-01_drone_client_authoritative.md`.

---

## 1. 개념

전시 구성은 무인 방치해도 그림이 나와야 하고(시네마틱), 시연자가 원할 때만 손을 댈 수 있어야 한다.
그래서 **기본값은 전자동**이고, 사용자가 **명시적으로 체크박스를 눌러야** 그 대상 하나가 수동으로 넘어온다.

> ⚠️ "스틱을 건드리면 자동 해제" 같은 암묵 전환은 **넣지 않는다**(사용자 확정). 조작 실수 한 번에
> 시네마틱이 깨지기 때문. `UDroneAutopilotComponent::bDisengageOnManualInput` 경로는 컴포넌트에
> 남아 있지만 `ADronePawn`이 더 이상 `NotifyManualInput`을 부르지 않아 이 흐름에선 죽어 있다
> (L_DroneTest 같은 직접 조종 워크플로용으로만 의미).

실행 모드(Demo/FullSystem)와는 **직교**다. RunMode는 "통제기가 UGV를 쥐느냐"만 정하고, 자체방호축은
어느 모드든 시나리오 시스템이 다 몰기 때문에 자체방호 입장에선 데모 개념이 사실상 없다.

## 2. 상태 모델 — 새 enum, `ECameraControlTarget` 재사용 안 함

```cpp
UENUM() enum class ESelfDefenseManualTarget : uint8 { None, TruckRCWS, UAV };
```

상호배타(둘 다 on 불가 / 둘 다 off 가능 / 하나 켜면 이전 것 자동 해제)는 **enum이라 공짜**다.

기존 `ECameraControlTarget`을 재사용하지 않은 이유(2026-09-01 사용자 지시로 재검토):

- 그 enum은 "조이스틱 pan/tilt/zoom이 **어디로 라우팅되는가**"라는 입력 배선용이고,
  `Server_ApplyRCWSPanTiltInput` 등 **RPC 10여 개의 인자**로 이미 깊게 박혀 있다.
- 거기엔 `UGVRCWS`가 있는데 이 조작 모델은 **자체방호축 전용**이다 — 자체방호 화면에서 UGV를
  수동으로 넘겨받을 수 있으면 안 된다(UGV는 UGV PC의 통제기가 쥔다).
- `AudioListenerTarget`도 같은 enum을 쓰는데, **오디오 포커스와 수동 조종은 따로** 켜져야 한다
  (트럭 소리를 들으며 드론을 조종하는 조합이 정상).

대신 값이 바뀔 때 `SetCameraControlTarget`을 필요한 만큼만 같이 맞춘다(None이면 `Idle` — 자동
조준/자율비행 중에 스틱이 섞여 들어가는 걸 원천 차단).

상태는 `Atitan_examplePlayerController::SelfDefenseManualTarget` **한 곳에만** 있고 두 창이 그걸
읽어 그리므로 어긋날 수 없다. 실제 상태 변경(RCWS 모드/오토파일럿)은 Server RPC로 서버에서 한다.

## 3. 전환 시 부수효과

| 전환 | 동작 |
|---|---|
| → TruckRCWS | **수동 진입 직전 RCWS 모드를 기억**하고 `Remote`로. 드론은 자동 복귀 |
| → UAV | `Drone->BeginManualControl()` — 자율비행 해제 + 짐벌 자동 중단, **복귀 지점(경로 ID·짐벌 단계) 기억**. 트럭은 기억한 모드로 복원 |
| → None | 양쪽 다 자동으로 복원 |

> 트럭을 `AutoFire`로 **하드코딩하지 않는** 이유: 3차 전투 전에는 시나리오가 아직 자동사격을 안
> 켰을 수도 있는데, 수동 한 번 잡았다 놨다고 거기서 자동사격이 켜지면 흐름이 앞당겨진다.

드론 자동 복귀는 `CommandedPathId`(시나리오가 마지막으로 태운 경로)로 재진입한다. 스플라인 추종은
현재 위치에서 가장 가까운 지점부터 다시 잡히므로(`UpdatePathProgress`) 사용자가 경로를 한참 벗어난
곳에 놔둬도 알아서 복귀한다.

## 4. UI — 창마다 자기 차량 것만

UAV 뷰가 Monitor1, 트럭 RCWS 뷰가 Monitor2라 체크박스도 그렇게 나눴다. 전부 `BindWidgetOptional`.

| 위젯 | 이름 | 타입 |
|---|---|---|
| `WBP` (SelfDefenseMonitor1) | `UAVAudioFocusCheckBox`, `UAVManualControlCheckBox` | Check Box |
| `WBP` (SelfDefenseMonitor2) | `TruckAudioFocusCheckBox`, `TruckManualControlCheckBox` | Check Box |

양쪽 다 매 갱신마다 PlayerController의 실제 상태로 다시 그린다 — 콘솔이나 반대쪽 창에서 바뀌어도
따라온다. `SetIsChecked`는 `OnCheckStateChanged`를 다시 쏘지 않아 루프가 안 생긴다.

콘솔: `SetSelfDefenseManual None|TruckRCWS|UAV`

## 5. 드론 수동 조종 — 빙의가 아니라 라우팅 + 드론 전용 축

드론은 `AIController_0`가 물고 있어서 빙의/IMC 경로를 못 쓴다(로그의
`IMC 등록 보류 — 아직 PlayerController에 빙의되지 않음`이 그 증상). UGV 주행/RCWS 조준과 같은
"빙의 없이 PlayerController가 넘겨주는" 방식으로 바꿨다.

**드론은 다른 차량과 조작 체계 자체가 다르다**(2026-09-01 사용자 확정) — 다른 차량은 스틱 축 0/1이
카메라 각도인데, 드론은 그게 기체 조종이고 카메라는 다른 조이스틱의 4방향 버튼이다. 그래서 기존
`UGVMoveAction`/`CameraLookAction`을 재사용하지 않고 **드론 전용 IA 4종**을 뒀다(다른 차량 배선은 그대로).

| 채널 | Input Action | 타입 | 물리 입력(예시) |
|---|---|---|---|
| 앞뒤·좌우 가속 | `DroneCyclicAction` | Axis2D | 스틱 축 0/1 |
| 기체 상방축 회전(요) | `DroneYawAction` | Axis1D | 스틱 축 2(비틀기) |
| 상승/하강 | `DroneThrottleAction` | Axis1D | 스로틀 레버 또는 버튼 |
| 짐벌 카메라 상하좌우 | `DroneGimbalLookAction` | Axis2D | **다른 조이스틱의 4방향 버튼** |

- 4방향 버튼 → Axis2D는 IMC에서 키 4개에 `Negate` / `Swizzle Axis(YXZ)` 모디파이어를 걸어 묶는다
  (WASD를 하나의 Axis2D로 묶는 표준 방식과 동일).
- `bDroneThrottleAxisIsAbsolute` — 스로틀을 **레버 위치=출력**(절대)으로 볼지 델타로 누적할지.
  기본 false(델타). 레버를 물릴 거면 켤 것(`ADronePawn::OnThrottleAxis`와 같은 해석을 쓴다).
- 세 비행 채널은 축마다 트리거 프레임이 달라서 **묶어서 한 번에** 보낸다 — 각자 보내면 그 프레임에
  안 움직인 채널이 0으로 덮여 기체가 튄다.
- 드론 수동 중에도 `CameraControlTarget`은 **`UAVGimbal`로 정상 유지**한다 — 그 값은 "조작자가 지금
  어느 차량을 붙들고 있나"라는 의미라, 위젯/오디오/축전환 등 그 값을 읽는 다른 로직과 어긋나면 안 된다.
  메인 스틱이 짐벌로 새는 문제는 **`DoCameraLook`에서 입력 경로만 끊어서** 해결한다
  (`SelfDefenseManualTarget == UAV`면 조기 리턴). 같은 물리 축에 `CameraLookAction`과
  `DroneCyclicAction`이 동시에 물려 있으면 두 핸들러가 다 불리므로 이 게이트가 없으면 짐벌과 기체가
  같이 움직인다.
  > 2026-09-01 1차 구현에선 `Idle`로 떨어뜨렸는데, 그러면 "드론을 수동으로 쥐고 있다"는 사실이
  > `CameraControlTarget`에서 사라져 다른 로직과 상태가 갈린다 — 사용자 지적으로 정정.

**인게임 Input 설정 화면**: `UTitanInputSchemaData`(`/Game/Input/DA_TitanInputSchema`)가 완전히
데이터 주도라 **C++ 수정 없이** 행만 추가하면 노출된다 — `RowName` + `Action`(위 IA) + `Roles`
(Axis1D/Boolean은 1개, Axis2D는 X/Y 2개) + `DefaultGroups`. 그 IMC도 `ManagedContexts`에 넣을 것.

### 5.1 ⚠️ 드론 IMC는 상시로 올리면 안 된다 (2026-09-01 실측으로 확정)

**증상**: 드론 수동 조종에서 **사이클릭(앞뒤좌우)만** 안 먹었다. 요·스로틀·짐벌은 정상.

**원인**: 드론 사이클릭은 조이스틱 축 0/1인데 **RCWS 조준(`IA_CameraLook`)도 같은 축**을 쓴다.
`IMC_DroneManual`을 `DefaultMappingContexts`에 넣어 `IMC_MouseLook`과 **같은 우선순위(0)로 동시에**
올려두면, 먼저 처리된 쪽이 `bConsumeInput=true`로 축을 먹어서 **드론 사이클릭 액션이 아예 발동조차
하지 않는다**. 요·스로틀은 축 2/3이라 안 겹쳐서 멀쩡했고, 그래서 "사이클릭만 안 되는" 기묘한 증상이 됐다.

**해결**: `IMC_DroneManual`은 `DefaultMappingContexts`에 **넣지 않고**,
`Atitan_examplePlayerController::DroneManualMappingContext`에 지정해서 **수동 조종 중에만**
`AddMappingContext(우선순위 10)` / 해제 시 `RemoveMappingContext` 한다.

- 기본 IMC들이 0으로 올라가므로 10이면 겹치는 축을 가져온다.
- 부수 효과로, 수동이 아닐 때는 드론 IA가 아예 안 올라가서 조이스틱이 RCWS 조준으로만 깔끔히 간다.
- IMC는 **생성자에서 `ConstructorHelpers`로도 물어둔다** — 이 프로젝트는 MCP로 CDO에 직접 쓴 값이
  재컴파일 때 초기화된 전례가 있어서(`NotificationSubsystem.h` 주석), 코드 기본값을 안전망으로 둔다.
- 적용 실패 시 `[자체방호] 드론 조종 IMC 적용 실패 — IMC=..., LocalPC=...` 경고가 남는다.
  증상이 "조이스틱이 통째로 안 먹음"이라 원인 추적이 오래 걸렸던 지점이다.

### 5.2 시뮬 주체 기준 라우팅 — solo / client 양쪽에서 동작 (2026-09-01)

드론 조종은 **solo든, host에 접속한 client든 똑같이** 되어야 한다(자체방호축이 조종 주체이므로).
그런데 드론 시뮬 주체는 구성에 따라 다르다(§`replication/2026-09-01_drone_client_authoritative.md`).

| 구성 | 드론 시뮬 주체 |
|---|---|
| solo(standalone) | 로컬 |
| Demo + 2PC | 서버(UGV 호스트) |
| FullSystem + 2PC | **클라이언트(자체방호)** |

그래서 두 가지를 시뮬 주체 기준으로 맞췄다:

1. **수동 상태를 리플리케이트** — `ADronePawn::bManualControlActive`가
   `ReplicatedUsing = OnRep_ManualControlActive`. `BeginManualControl`/`EndManualControl`은 서버 전용
   진입점으로 **상태만** 바꾸고, 실제 효과(자율비행 해제/스로틀 시드/경로·짐벌 복귀)는
   `HandleManualControlChanged()`가 **`bSimulationAuthority`인 프로세스에서만** 실행한다.
   > 예전엔 서버에서만 플래그를 세워서 FullSystem 2PC에서 **정작 드론을 도는 클라가 수동 상태를 몰랐다.**
2. **입력도 시뮬 주체로** — `HasAuthority()`가 아니라 `Drone->IsSimulationAuthority()`로 분기.
   로컬이 시뮬 주체면 바로 적용, 서버가 시뮬 주체면 Server RPC. 짐벌도 동일(그쪽에서 돌려야
   RTSP 화면도 거기서 만들어진다).

### 5.3 스로틀 인수인계 (2026-09-01)

자율비행 중엔 오토파일럿이 스로틀까지 만들어 쓰므로 **수동 누적값(`AccumulatedThrottle01`)은 0**이다.
그대로 넘겨받으면 추력이 사라져 기체가 떨어지고, 그 상태에선 사이클릭을 넣어도 아무 일도 안 일어난다.
→ 수동 진입 시 호버 지점(`1/ThrustToWeightRatio`, 실측 약 50%)으로 시드한다.

## 6. 전투 단계별 프레이밍 (사용자 확정 기준)

| 단계 | 한 화면에 들어와야 하는 것 |
|---|---|
| 1차 | UGV + 적군 |
| 2차 | UGV + 아군 + 적군 |
| 3차 | 이동형지휘소 + 적군 |

적군은 어느 세트에서든 드론이 자기 탐지 목록/레지스트리에서 스스로 모은다.

**바뀐 점**: 예전엔 트리거 시점의 아군/UGV 위치를 **한 번 찍어서** 넘겼다(적군만 매 틱 갱신).
그러면 UGV가 2차 목적지로 이동하거나 아군이 매복 지점으로 흩어지면 옛 위치를 붙들고 화면이 어긋난다.
이제 `EDroneFramingSet`(세트 종류)만 알려주고, 실제 위치는 매 틱 살아있는 액터에서 다시 읽는다
(`UScenarioStateSubsystem::CollectFramingActorsForSet` — 드론이 아군 레지스트리나 ScenarioConfig를
직접 알 필요가 없게).

## 7. 낙하산 조기 감지 버그 수정

예전엔 `GimbalGuaranteedFindDelaySeconds`(5초)가 **무조건** 흘러야 다음으로 넘어갔다. 그래서 스윕
도중 낙하산이 화면에 뻔히 잡혀 있어도 5초를 다 채울 때까지 "못 찾은 척"을 했다(사용자 리포트).

이제 보장 시간은 **하한선이 아니라 상한선**이다 — 탐지 컴포넌트가 실제로 낙하산을 잡으면 즉시 스냅
단계로 넘어가고, 관찰 시간(`ParachuteObserveDurationSeconds`)은 **잡은 시점부터** 센다.

같은 판정을 수동 조종에도 쓴다(`TickManualParachuteObservation`): 사용자가 카메라를 돌려 낙하산을
화면에 넣고 유지하면 발견 완료. 도중에 화면 밖으로 나가면 카운트가 리셋된다(스쳐 지나간 것으론 완료 안 됨).

## 8. 바뀐 파일

`titan_examplePlayerController.h/.cpp`(enum·상태·Server RPC·부수효과·드론 입력 라우팅) ·
`Drone/DronePawn.h/.cpp`(수동 진입/해제, 프레이밍 세트, 낙하산 조기 감지) ·
`UI/ScenarioStepTypes.h`(이펙트 3종) · `UI/ScenarioStateSubsystem.h/.cpp`(프레이밍 액터 해석) ·
`UI/SelfDefenseMonitor1Widget.h/.cpp` · `UI/SelfDefenseMonitor2Widget.h/.cpp`

## 9. 남은 작업

1. ✅ **빌드** 완료(사용자).
2. ✅ **DT 마무리 완료**(23행, 저장됨). 드론 관련 행 최종 상태:

| RowName | 선행 | 트리거 | 이펙트 | 경로 |
|---|---|---|---|---|
| `UAVMission` | — | TimerOnly 3s | `BeginUAVMission` | `uavpath` |
| `UAVSpotted` | UAVMission | `UAVParachuteObserved` | `MoveUGVToZone1Destination` | — |
| `DroneSeeEnemies` | **EnemyEngage** | TimerOnly 0s | `EnableDroneEnemyDetection` | — |
| `DroneWideView` | DroneSeeEnemies | TimerOnly 1s | **`SetDroneFramingZone1`** | — |
| `DroneChasePath` | EnemyFleeToZone2 | TimerOnly 0s | `MoveDroneToPath` | **`uavpath2`** |
| `DroneFrameZone2` | AllyAmbush | TimerOnly 0s | **`SetDroneFramingZone2`** | — |
| `DroneFrameZone3` | EnemyFleeToZone3 | TimerOnly 0s | **`SetDroneFramingZone3`** | — |

   흐름: 낙하산 발견 → (드론 대기, 아무것도 안 함) → **UGV 근거리 최초 사격** → 적 탐지 확장 →
   1초 뒤 1차 프레이밍(UGV+적) → 적 2차 도주 시 추격 스플라인 + 아군 매복 시 2차 프레이밍
   (UGV+아군+적) → 적 3차 도주 시 3차 프레이밍(지휘소+적).
   - ✅ 이미 적용: `DroneSeeEnemies`의 선행을 `UAVSpotted` → **`EnemyEngage`**(= UGV가 근거리에서
     최초 사격한 뒤)로 옮김 + `DroneWideView` 지연 1초. 낙하산 발견 직후엔 드론이 아무 것도 안 한다.
   - ✅ 이미 적용: `DroneChasePath` 행 신설(선행 `EnemyFleeToZone2`, `MoveDroneToPath`,
     `UAVPathId=uavpath2`) — 레벨에 추가된 추격 스플라인.
3. ✅ **레벨**: 추격 스플라인 `uavpath2` 추가됨(사용자).
4. ✅ **WBP**: 체크박스 4개 배치 완료(사용자).
5. **IA/IMC**: 드론 전용 IA 4종 생성 + PC 클래스 디폴트 지정 + (원하면) `DA_TitanInputSchema`에
   행 추가(사용자) — §5.
6. Monitor1(서브창) 체크박스 클릭이 실제로 먹는지 확인 — 닫기 버튼이 되는 걸로 봐선 될 것으로 보이나 미검증.
7. (Phase D, 보류) 낙하산 위치 힌트 UI, `PathPreviewFX` 부활로 목표/경로 시각화.
