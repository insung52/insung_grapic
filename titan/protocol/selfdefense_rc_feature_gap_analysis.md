# 자체방호축 RC 프로토콜 — ICD 커맨드 ↔ 실제 구현 갭 분석 (2026-08-16, 2026-08-17 갱신)

`protocol_icd.md` §4(자체방호축)의 원칙 — "네트워크 메시지가 아니라 같은 프로세스 내 함수
호출, §3.2의 UGV축 대응 함수와 개념적으로 동일한 것들을 로컬로 부르면 됨" — 을 기준으로,
UGV축 ICD(`lig_icd_ugv_rc_full.md`) 커맨드를 개념 대응시켜 `titan_examplePlayerController.*`
(트랙5) 구현과 1:1 대조한 결과. `ugv_rc_feature_gap_analysis.md`(UGV축 버전)와 같은 목적·같은
포맷 — "cmd가 코드에 있냐"가 아니라 "그 cmd를 보내면(=조이스틱 버튼을 누르면) 실제로 뭔가
달라지냐"가 기준.

상태 기호:
- ✅ 실측 확인 — 사용자가 실제 조이스틱으로 테스트해서 확인
- 🔧 배선 완료, 실측 대기 — 코드+IA_ 애셋+IMC 매핑까지 끝났지만 컴파일/실제 조이스틱 테스트 전
- ⛔ 범위 밖 — ICD엔 있으나 자체방호축 자체가 이 기능의 전제(주행 등)가 없어서 대응 불가
- ❌ 미착수

---

## 1. RCWS 관련 (UGV축 §3.2 RC_* 개념 대응)

| cmd(UGV축 원문 기준) | 자체방호축 배선 | 상태 | 비고 |
|---|---|---|---|
| `RC_FireWeapon` | `ManualFireAction` → `DoManualFireStarted/Completed` → `Server_SetManualFireHeld` → `bManualFireHeld` | ✅ | 이번 세션 이전부터 완료, 사용자 실측 확인 |
| `RC_Movement`(XAxis/YAxis) | `CameraLookAction` → `DoCameraLook` → `ApplyRCWSPanTiltForTarget`/`Server_ApplyRCWSPanTiltInput` → `AddPanTiltInput` | ✅ | 위와 동일, 기존 완료 |
| `RC_Movement`(BrakeButton) | `RCWSMovementBrakeAction`(Joystick Button_10) → `DoRCWSMovementBrakeStarted/Completed` → `bRCWSMovementBraked` → `DoCameraLook` 게이트 | 🔧 | 신규(2026-08-16). 극성: 기본값=자유 회전, PRESSED 동안만 브레이크("물리적 브레이크 레버처럼 누르면 잠김"). UGV축(`Handle_RC_Movement`)도 이후 동일한 극성으로 수정됨(2026-08-16) — **두 축 일치, 더 이상 불일치 아님.** ICD 원문 의도와 맞는지는 여전히 LIG 확인 필요 |
| `RC_SelectCamera`(EO/IR) | `RCWSCameraModeToggleAction`(Button_1) → `DoRCWSCameraModeToggle` → `SetCameraMode`/`Server_SetRCWSCameraMode`(신규 RPC) | ✅ | 사용자 실측 확인(2026-08-17). 단, 배선 자체는 처음부터 맞았고 별도 버그(트럭 RCWS 인스턴스의 `IRPostProcessMaterial`이 `None`으로 오버라이드돼있던 것) 때문에 처음엔 화면이 안 바뀌었음 — §1-1 참고 |
| `RC_FireMode`(단발/점사/연사) | `RCWSFireModeCycleAction`(Button_6) → `DoRCWSFireModeCycle` → `SetFireMode`/`Server_SetRCWSFireMode`(기존 RPC 재사용) | 🔧 | 사이클 로직(`RCWSFireControlComponent::TickComponent`)도 컴포넌트 공용이라 UGV축 검증 결과 그대로 적용될 것으로 보이나, 이 버튼 자체는 아직 사용자가 명시적으로 테스트 안 함 |
| `RC_ChargeWeapon`(장전) | `RCWSChargeToggleAction`(Button_9) → `DoRCWSChargeToggle` → `SetLoaded`/`Server_SetRCWSLoaded`(신규 RPC) | 🔧 | "재장전"(탄약수 보충)이 아니라 발사 가능 여부 스위치(`bLoaded`, `CanFire()`가 체크) — 기본값 true라 안 눌러도 발사가 되므로 아직 명시적으로 테스트된 적 없음. ICD 의도와 일치하는지도 여전히 LIG 확인 필요 |
| `RC_ActivateFire`(안전/암) | `RCWSFireSystemActiveToggleAction`(Button_7) → `DoRCWSFireSystemActiveToggle` → `bFireSystemActive`/`Server_SetRCWSFireSystemActive`(기존 RPC 재사용) | ✅ | 사용자 실측 확인(2026-08-17) — 안전 해제 후 발사 확인됨 |
| `RC_MotionMode` | — | ⛔ | "기동 모션 모드 설정" — 차량 주행 개념. 자체방호축은 주행 자체가 없음(§2 참고) |
| `RC_ActivateMovement` | — | ⛔ | "구동 상태 설정" — UGV축은 차량 시동(`bEngineOn`)으로 추정 매핑했으나(LIG 미확인), 자체방호 트럭엔 애초에 구동계(주행)가 없어서 대응 개념 자체가 없음 |

## 1-1. 트럭(BP_TitanTruck) 전용 버그 발견/수정 (2026-08-17)

프로토콜 매핑(입력 배선)은 처음부터 맞았는데, **그 아래 시각/청각 구현이 트럭 쪽에서만
따로 빠져있던 버그 3개**를 실측 중 발견해서 고침. UGV(`BP_UGV_Vehicle`)는 전부 정상이었던
걸 보면, 애초에 트럭 쪽 리그를 만들 때 이 부분들이 누락된 채로 남아있었던 것으로 보임.

| 버그 | 원인 | 수정 |
|---|---|---|
| EO/IR 전환해도 화면 안 바뀜 | `BP_TitanTruck_C_*`(레벨 배치 인스턴스)의 `RCWS.IRPostProcessMaterial`이 `None`으로 인스턴스 오버라이드돼있었음(클래스 기본값엔 `M_PP_RCWS_IR`이 이미 제대로 들어있었음 — 인스턴스만 어긋나있던 케이스) | UGV와 동일한 `M_PP_RCWS_IR` 머티리얼로 인스턴스 값 직접 재지정 |
| 총열이 발사해도 안 돎 | `BP_TitanTruck`의 `EventTick`이 `UpdateTurretVisuals` 함수를 호출하는 노드 자체가 없었음(함수는 존재하지만 아무도 안 부름 — 조준이 되는 것처럼 보인 건 `RCWSTurretBase`가 `RCWSMount`의 자식이라 부모 트랜스폼을 그냥 따라간 것뿐) | `EventTick` → `UpdateTurretVisuals(DeltaSeconds)` 호출 노드 신규 추가·연결. 겸사겸사 `UpdateTurretVisuals` 안에 총열 회전 로직도 추가(`BarrelSpinAngle`/`BarrelSpinMaxSpeed`=1440deg/s 변수 신규, `RCWSFireControl->GetBarrelSpinGaugeValue()`로 각도 누적해서 `RCWSBarrels`에 로컬 Roll로 적용 — UGV `UpdateTurretVisuals`와 동일 공식) |
| 총열 회전 소리 안 남 | `UBarrelSpinAudioComponent`(UGV는 `Muzzle`에 부착돼있음) 자체가 트럭 액터엔 없었음 | 동일 컴포넌트를 트럭에 신규 추가, `Muzzle`에 부착, UGV와 동일한 MetaSound(`MS_barrel_spin`) + `bAutoActivate=true` 설정 |

**작업 중 알게 된 점(다음에 이 블루프린트 만질 때 참고)**: `unreal-mcp`로 `compile_blueprint`를
부르면 레벨에 배치된 해당 클래스 액터가 재생성됨(`BP_TitanTruck_C_3` → `_C_1`처럼 인스턴스
번호가 바뀜) — 그때마다 인스턴스 레벨 오버라이드(`IRPostProcessMaterial` 등)가 날아갔는지
매번 재확인해야 했음. 다행히 이번엔 살아남았지만, 인스턴스 오버라이드에 의존하는 값이 있다면
컴파일 후 항상 재확인 권장.

## 1-2. 자체방호축 고유 (UGV축엔 없는 개념, §4)

| 기능 | 배선 | 상태 | 비고 |
|---|---|---|---|
| UAV 짐벌 pan/tilt/zoom | `CameraLookAction`(CameraControlTarget=UAVGimbal일 때) → `ApplyUAVGimbalPanTiltInput`/`Server_ApplyUAVGimbalPanTiltInput`, 줌은 `BeginUAVManualZoomTransition`(Monitor1 UI 버튼) | 🔧 | 코드 경로 자체는 이전부터 있었음 — 아래 축전환 버튼이 없어서 실사용 불가능했던 게 이번에 풀림 |
| TruckRCWS ↔ UAVGimbal 축전환 | `RCWSUAVAxisToggleAction`(Button_8) → `DoRCWSUAVAxisToggle` → `SetCameraControlTarget` | 🔧 | 이전엔 콘솔 명령(`SetCameraControlTarget "UAV"`)으로만 가능, 이번에 버튼 추가 |
| RTSP 7종(환경카메라/CCTV×4/RCWS뷰어/UAV드론뷰) | 소스 컴포넌트 7개 전부 식별 완료(`BattlefieldCapture`/`QuadCam`/`GetSightCamera()`/`GetGimbalCamera()`) | ❌ | 인코드·송출 파이프라인(`RtspEncoder` 플러그인)은 활성화 확인+회전 큐브 테스트로 검증 완료(트랙1), 실제 카메라에 `URtspStreamComponent` 연결은 미착수 — 자체방호축에 남은 유일한 큰 작업 |

---

## 2. 완료 기준 대비 현황

원 지시사항 완료 기준: *"조이스틱으로 UAV 짐벌/RCWS 실제 조작 가능(리슨서버 클라이언트 프로세스에서), RTSP로 7개 스트림 영상 확인됨."*

- RCWS 조준/발사 — ✅ 실측 확인(EO/IR·안전스위치·총열회전 시청각까지 포함)
- UAV 짐벌 — 🔧 코드/버튼 다 있음, 축전환 버튼이 이번에 생겨서 이제 실측 가능한 상태 — 아직 사용자가 명시적으로 UAV 축전환/짐벌 조작까지는 테스트 안 함
- RTSP 7스트림 — ❌ 미착수, 자체방호축에 남은 유일한 큰 작업

## 3. 조이스틱 버튼 맵 (Extreme 3D Pro 테스트 장비 기준, `IMC_MouseLook`)

실제 GP5로 교체 시 `Joystick_<디바이스명>_...` 패턴만 그대로 다시 매핑하면 됨(JoystickPlugin이
연결된 디바이스 이름 기준으로 동적 등록 — `SelfDefenseInputForwarder` 관련 세션 기록 참고).

| 버튼 | 액션 |
|---|---|
| Axis_0 / Axis_1 | `CameraLookAction`(RCWS/UAV 공용 pan/tilt) |
| Button_0 | `ManualFireAction` |
| Button_1 | `RCWSCameraModeToggleAction`(EO/IR) |
| Button_2 | (비워둠, 예비) |
| Button_3 | `RCWSZoomOutAction` |
| Button_4 | `RCWSModePreviousAction`(자동조준/발사 모드 순환 — ICD에 대응 커맨드 없는 로컬 전용 기능, §1 표 참고) |
| Button_5 | `RCWSZoomInAction` |
| Button_6 | `RCWSFireModeCycleAction` |
| Button_7 | `RCWSFireSystemActiveToggleAction` |
| Button_8 | `RCWSUAVAxisToggleAction` |
| Button_9 | `RCWSChargeToggleAction` |
| Button_10 | `RCWSMovementBrakeAction` |

`RCWSModeToggleAction`(모드 "다음" 방향)은 2026-08-16부로 IMC 매핑 제거 — 자동조준/자동발사
모드 순환 자체가 ICD 대응 커맨드가 없는 로컬 전용 기능이라 조이스틱 버튼을 안 씀(콘솔 명령
`SetRCWSControlMode`/`SetCameraControlTarget`으로는 여전히 가능). 전용 애셋(`IA_RCWSModeToggle`)
으로 이름은 정리했지만 미매핑 상태로 둠.

## 4. 다음 액션

1. **남은 실측** — EO/IR·안전스위치·발사·총열회전(시청각)은 확인 완료(2026-08-17). 아직
   명시적으로 테스트 안 된 것: `RCWSFireModeCycleAction`(발사모드 순환), `RCWSChargeToggleAction`
   (장전), `RCWSUAVAxisToggleAction`(UAV축전환) + UAV 짐벌 조작, `RCWSMovementBrakeAction`
   (조이스틱 있어야 눈으로 확인 가능 — "안 누르면 자유회전, 누르면 잠김" 극성 확인 최우선).
2. **RTSP 7스트림 연결** — 유일하게 남은 큰 작업.
3. **LIG 문의 리스트에 추가할 것**: `RC_ActivateMovement`(UGV축 시동 매핑 추정치), `RC_MotionMode`
   (의미 불명), `RC_Movement.BrakeButton` 극성(두 축 모두 "기본 자유회전, PRESSED 시 브레이크"로
   통일됨(2026-08-16) — 이 해석 자체가 ICD 원본 의도와 맞는지는 여전히 확인 필요).
4. **BP_TitanTruck 리그 재점검** — §1-1에서 발견된 3개 버그(IR 머티리얼/총열회전/총열사운드)가
   전부 "UGV엔 있는데 트럭엔 원래부터 빠져있던 것"이었다는 점을 보면, 다른 UGV↔트럭 공용
   기능 중에도 비슷하게 누락된 게 더 있을 수 있음 — 여유 있을 때 UGV `EventGraph`/컴포넌트
   구성과 트럭을 한 번 더 통째로 대조해볼 가치 있음.
