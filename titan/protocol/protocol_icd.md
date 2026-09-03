# 프로토콜 ICD (Interface Control Document) — 상세 명세(임시)

- claude artifacts 시각화 문서

- https://claude.ai/code/artifact/6089715a-aa43-4dbb-9113-207c796d665d?via=auto_preview

---

`architecture_decisions.md`를 필드 단위로 formalize한 문서. **2026-08-06 LIG 답변
(`lig_response_0806_review.md`)으로 UGV축 인터페이스가 우리 설계가 아니라 외부 확정
스펙으로 바뀌었음 — §3이 그 내용으로 전면 개정됨.** 자체방호축은 별도 프로세스가 아니라
단일 프로그램으로 바뀌어 Layer B 자체가 없음(§4).

---

## 0. 전송 계층 — 두 갈래로 나뉨 (2026-08-07 갱신)

**전송계층은 UDP로 통일 확정 (2026-08-07, 팀장님과 논의 완료). NATS는 폐기.** 실제로는:

| 채널 | 전송 | 성격 | 상태 |
|---|---|---|---|
| UGV축: UGV 시뮬레이션 SW ↔ 원격통제기(LIG) | **UDP, JSON 문자열** | **외부 확정 스펙** — 우리가 선택 불가, LIG가 이미 구현 | 확정 (§3) |
| 자체방호축: 내부 | 없음(같은 프로세스 내 함수 호출) | 단일 프로그램이라 네트워크 계층 자체가 불필요 | 확정 (§4) |
| Layer A: 자체방호통제기SW ↔ 상위체계 | **UDP+JSON**(§3과 같은 패턴, 우리 초안) — LIG가 이 채널 자체를 아직 검토중 | 미정 | 보류 (§5) |
| 영상 | RTSP | 시뮬레이션(UGV SW / 자체방호 통제기SW)이 RTSP 서버 | 확정 |

**NATS 인프라(트랙2 완료분)는 완료된 채로 보류 — 폐기 결정으로 더 이상 투자 안 함.** UGV축이
UDP+JSON으로 이미 확정된 마당에 내부적으로 NATS를 따로 쓸 이유가 없다고 판단, Layer A가
나중에 생겨도 §3과 같은 UDP+JSON 패턴을 따를 가능성이 높음 — 일관성을 위해서도 UDP 통일이
낫다는 결론.

**UDP는 유실을 전제로 설계해야 함** — 테스트도 Postman 같은 HTTP 도구로 안 되니 별도 전략
필요(§8).

## 1. 공통 봉투(Envelope) 포맷 — **두 가지가 공존함, 헷갈리지 말 것**

**(a) UGV축 — LIG 형식 (§3에서 사용, 확정)**:
```json
{ "cmd": "Command Code", "src": "device", "recv": "device", "data": { "key1": "value1" } }
```
device 코드: `RC=20`(원격통제기), `UGV=14`, `UGV_RCWS=13`, `UGV_ADU=12`.

**(b) Layer A — 우리 초안 형식 (§5에서 사용, 미정/보류, 2026-08-07 수정: NATS 전제 폐기)**:
```json
{ "cmd": "<MessageName>", "seq": 0, "ts": 0, "payload": { } }
```
- `seq`: uint32 단조증가(유실/재정렬 감지), `ts`: uint64(세션 시작 후 경과 ms).
- 원래 NATS 채널(TCP)이라 가정하고 설계됐던 봉투 — **지금은 UDP 통일 방침이라 이 형식도
  (a)처럼 `{cmd,src,recv,data}`+앱레벨 ACK/재시도로 다시 맞추는 게 맞을 가능성이 높음.**
  Layer A가 실제로 확정되기 전까지는 굳이 지금 다시 쓰지 않고, 확정 시점에 (a) 패턴으로
  통일해서 재작성 예정 — 지금 이 봉투는 "예전 설계 흔적"으로만 남겨둠.

UGV축은 무조건 (a). Layer A가 실제로 생기면 (a)와 같은 패턴을 따를 전망(§5).

## 2. 공통 타입 · 단위 표준 (양쪽 다 적용)

**좌표계 확정 (2026-08-14): UTM.** 정식 ICD(`lig_icd_ugv_rc_full.md`, `UGV_RC_ICD.xlsx`
복호화 확보)로 최종 확인됨 — `East`(8자리)/`North`(10자리)/`Zone`/`Letter` 정수·문자열 필드,
WGS84 lat/lon 아님. `lig_questions_0807_draft.md`의 좌표계 질문은 해소, 삭제.

**대응 방침(그대로 유효)**: 내부 canonical 저장은 lat/lon, 와이어(UTM)로 낼 때 변환 함수로
계산 — UTM이 최종 확정됐어도 내부적으로 lat/lon을 쓰는 이유는 그대로 유효(계산/다른 좌표계
소비처와의 호환성). 변환 로직은 `GeoCoordinateUtils.h`에 UTM 변환 함수 추가 필요(Track4/5
몫). Zone/Datum 정확한 값은 ICD에 안 나와 있어 여전히 확인 필요(카덱스 시연 장소가 고정
지역이라 Zone은 사실상 고정값 — 경도로 자동 계산하는 표준 공식으로 임시 결정 후 실측 대조).

```
Coord      { "lat": double, "lon": double, "alt": float }
             // 내부 canonical 표현. 와이어(UTM)로 낼 때: East(Int,8자리)/North(Int,10자리)/Zone(Int)/Letter(String)로 변환
BBox       { "leftTopX": int, "leftTopY": int, "rightBottomX": int, "rightBottomY": int }
             // 확정(ICD): 0~65535 정수 스케일링, 결과값 = 픽셀좌표 * 65535 / 영상 가로|세로 크기
             // 기존 {x,y,w,h} 0~1 UV 타입은 폐기 — ICD가 좌상단/우하단 절대좌표쌍+스케일링 방식으로 못박음
Detection  { "objectID": int(1~65535), "objectClass": ObjectClass, "bbox": BBox,
             "east": int, "north": int, "zone": int, "letter": string, "velocity": int, "altitude": int }
             // 필드명은 ICD 원문 그대로(대소문자 등) — `lig_icd_ugv_rc_full.md` 시트2 참고
ObjectClass "Ally" | "Enemy" | "UGV" | "MobileCommandPost" | "Drone" | "Parachute"
             // 2026-09-02 확장. ICD 원문은 "Human"|"Car" 2값 — LIG 1차 답변(Q10, response_0828.md)이
             // "구분 가능하면 세분화해서 보내도 되고 Car로만 보내도 된다"고 우리 재량으로 확정해준
             // 필드라 스펙 위반이 아님(결정 통보는 lig_questions_0816.md §5-2).
             // 2단계 계층(Human->Ally/Enemy, Car->UGV/...)이 아니라 플랫 6값인 이유: 드론이 "Car"에
             // 안 들어감. 이 시나리오엔 적 차량/적 드론이 없어서 장비 3종(UGV/이동형지휘소/드론)은
             // 항상 아군 자산 — 플랫으로 펴도 피아식별 정보가 사라지지 않음.
             // 확장 계기: 낙하산(BP_Parachute)이 ACharacter가 아니라 AActor라 else 가지인 "Car"로
             // 나가던 버그(실측 발견). 구현/판정 순서는 2026-09-02_object_class_expansion.md 참고.
```

**단위 표준**: 거리/반경/고도 = 미터(m), 속도 = m/s, 각도 = 도(°), 배터리 = 0~1 소수(단,
ICD 원문은 0~100 Int% — §3.2 참고, 필드별로 ICD 값 우선), 시간 = ms.

**§3.2 전체가 이제 ICD 확정값** — 아래 표 그대로 구현 대상. `data` 필드 key/value는
`lig_icd_ugv_rc_full.md`가 원문 그대로(오타 포함) 기록.

---

## 3. UGV축 — UGV 시뮬레이션 SW ↔ 원격통제기 — **외부 확정 스펙, ICD 원문 확보 완료 (2026-08-14)**

**우리가 설계한 게 아니라 LIG가 이미 구현한 원격통제기에 맞춰서 우리가 구현해야 하는
인터페이스.** IP/포트/신뢰성 메커니즘/cmd 목록/data 필드 전부 **정식 ICD로 확정**
(`lig_icd_ugv_rc_full.md`, `UGV_RC_ICD.xlsx`) — 더 이상 추정치 아님.

### 3.1 전송/네트워크

| 단말 | IP | Port(주기) | Port(비주기) |
|---|---|---|---|
| UGV | 192.168.10.10 | 8000 | 8001 |
| 원격통제기 | 192.168.10.20 | 8010 | 8011 |

- 전송: UDP. 페이로드: JSON 문자열, §1(a) 봉투.
- **신뢰성은 애플리케이션 레벨 ACK+재시도** (`image.png`, LIG 제공 시퀀스도):
  - **주기성 메시지** (Request/Response): 송신→Request, 수신→Response. 응답이 `( )`회까지
    안 오면 Request 재시도(정확한 재시도 횟수/타임아웃 값은 LIG 원본에 빈칸 — 확인 필요).
  - **이벤트 메시지** (Message/ACK): 송신→Message, 수신→ACK. `( )msec` 내 ACK 없으면
    **3회까지** Message 재시도(원본에 3회로 명시됨, 타임아웃 msec 값만 미기재).

### 3.2 메시지 — **ICD 확정 (전체 원문은 `lig_icd_ugv_rc_full.md`)**

`src`/`recv`는 `RC`(원격통제기,20) / `UGV`(14) / `UGV_RCWS`(13) / `UGV_ADU`(12).

**UGV→RC (우리가 보냄)**:

| cmd | src | 주기 | data 핵심 필드 |
|---|---|---|---|
| `UGV_Response_Connection` | UGV/UGV_ADU | 비주기 | `ResponseDevice` |
| `UGV_Period_Basicinfo` | UGV | **10Hz** | `OperationMode`(Stay/Remote/FAD/HAD/5/6/Emergency), `ConrtrolRight`(원문 오타), `Speed`(0~100), `Gear`(Front/Back/Turn — **Turn은 LIG 확인상 이번 사업에서 안 보내도 됨, 2026-08-28**), `Batterry`(원문 오타, 0~100%) |
| `UGV_Response_BIT` | UGV | 비주기 | `StatusVMU`, `CountValue` |
| `UGV_RCWS_Status` | UGV_RCWS | **20Hz** | `RCWSStatus`(ON/OFF) |
| `UGV_Period_ObjectDetectionResult` | UGV_RCWS 또는 UGV_ADU(동일 cmd, src로 구분) | — | `TotalObject`, `Objects[]`(BBox+UTM+속도+고도, §2) |
| `UGV_Response_BIT_ADU` | UGV_ADU | 비주기 | `StatusADU`/`StatusVMU`/`StatusNavigation`/`Status3DLidar`/`StatusRadar`/`StatusOCS` |
| `UGV_Period_BasicInformation` | UGV_ADU | — | `Odometer`(m) |
| `UGV_Period_NavigationInformation` | UGV_ADU | — | `East`/`North`/`Zone`/`Letter`, `Velocity`, `Heading`, `Altitude` |

**RC→UGV (우리가 받아서 처리, 예전에 비어있던 부분 전부 확정됨)**:

| cmd | 주기 | data 핵심 필드 | 매핑 |
|---|---|---|---|
| `RC_Connection` | 비주기(1Hz 재연결) | `RequestDevice`(0/1) | 연결 핸드셰이크 |
| `RC_Request_BIT` | 1Hz | `RequestBit` | BIT 응답 트리거 |
| `RC_Control_Right` | 비주기 | `ControlRight`(0/1) | 제어권 설정(p.11 상태도의 "제어권 설정?") |
| **`RC_RemoteDriving`** | **20Hz** | `Acceleration`(0~100), `Brake`(-0~-100), `Steering`(-100~100), `Gear`(FRONT/BACK) | `SetManualControl()` 계열 — **필드 그대로 매핑 가능** |
| `RC_EmergencyStop` / `RC_EmergencyStopRelease` | 비주기 | `CommandDevice`(1==동작) | **구현 완료** — `bEmergencyStopActive` 래치 → `DriveMode=Idle`+브레이크(`ugv_rc_feature_gap_analysis.md`) |
| **`RC_OperationMode`** | 비주기 | `OperationMode`(**STAY/REMOTE만 실제 설정값 — EMERGENCY는 ICD 오기입, 2026-08-28 LIG 확인**) | 구현 완료(`RequestedOperationMode → DriveMode`), 매핑 확정은 아래 참고 |
| `RC_SelectCamera` | 비주기 | `SelectCameraButton`(RELEASE=EO/PRESSED=IR) | EO/IR 전환 |
| `RC_FireMode` | 비주기 | `FireMode`(SINGLE/BRUST/CONTINUS, 원문 오타) | `SetFireMode` — 단발(PRESSED=1발/RELEASE=재격발가능), 점사(PRESSED=3회/RELEASE=재격발가능), 연사(PRESSED=지속/RELEASE=중지+재격발가능) — 2026-08-28 LIG 확인, 우리 구현과 일치 |
| `RC_ChargeWeapon` | 비주기 | `ChargeSwitch`(OFF/ON) | 장전 |
| **`RC_FireWeapon`** | 비주기 | `FireButton`(RELEASE=대기/PRESSED=사격) | `ManualFireAction` — PRESSED/RELEASE는 조이스틱 이벤트 발생 시에만 1회 전송(프레임마다 아님, 2026-08-28 확인). **`RELEASE` 패킷 유실 시 사격 지속 상태로 남는 것에 대한 안전장치가 LIG 쪽에도 없음(확인됨)** — 우리 쪽 워치독 구현 필요(§ 아래 §6 참고) |
| `RC_MotionMode` | 비주기 | `MotionMode`(RELEASE=활성/PRESSED=비활성) | 용도 불명, LIG도 "차후 논의 대상"(2026-08-28) — 당분간 스텁 유지, 재질문 불필요 |
| `RC_Movement` | 비주기 | `BrakeButton`, `XAxis`(12bit,-100~100), `YAxis`(12bit,-100~100) | RCWS pan/tilt+브레이크. `BrakeButton`=RELEASE(풀림)→회전 활성 해석이 맞음(2026-08-28 확인) — 단, `RC_ActivateMovement`와 AND 조건(아래) |
| `RC_ActivateFire` | 비주기 | `ActivateFireToggle`(RELEASE=활성/PRESSED=비활성) | 조정간 안전(사격계통 안전/암 스위치) — 우리 구현과 일치(2026-08-28 확인) |
| **`RC_ActivateMovement`** | 비주기 | `ActivateMovementToggle`(RELEASE=활성/PRESSED=비활성) | **✅ 재매핑 완료(2026-08-31) — 차량 시동/이그니션이 아니라 "RCWS 조향(pan/tilt) 모터 활성화" 커맨드임.** `RC_Movement.BrakeButton`과 **AND 조건**: `RC_ActivateMovement`=RELEASE(활성) **AND** `BrakeButton`=RELEASE(풀림)일 때만 RCWS 조준 입력이 먹힘. 2026-08-31 재배선 완료 — `UUGVRemoteControlSubsystem::bRCWSSteeringActivated` 래치를 `Handle_RC_Movement`에서 `BrakeButton`과 AND로 묶어 `AddPanTiltInput`을 게이팅. `bEngineOn`(차량 엔진) 배선은 제거됨(콘솔/BP 전용으로만 남음) |
| `RC_Connection_ADU` / `RC_Request_BIT_ADU` | 비주기/1Hz | `RequestDevice`/`CountValue` | ADU측 핸드셰이크(자율축, 원문 주석: 실제 ADU는 현대로템 제품, 우리는 시뮬레이터가 이 응답을 대신 함) |

**`RC_OperationMode` ↔ `EUGVDriveMode` 매핑 — 2026-08-28 LIG 답변으로 대부분 해소**:
`RC_OperationMode`는 실제로 `STAY`/`REMOTE` 두 값만 설정 가능 — ICD에 `EMERGENCY`가 값으로
적혀있던 건 **오기입**이었고, `UGV_Period_Basicinfo.OperationMode`가 `Emergency`로 바뀌는
건 오직 `RC_EmergencyStop`/`RC_EmergencyStopRelease`를 통해서만 일어남(LIG 확인). 즉:
`RC_OperationMode(STAY/REMOTE)` + `RC_Control_Right` → `EUGVDriveMode(Idle/Manual)` 매핑이고,
`RC_EmergencyStop` 래치는 그 위에 별도로 얹혀서 `OperationMode` 보고값을 강제로 `Emergency`로
덮어씀(우리 구현은 이미 이 방향으로 되어 있음, `ugv_rc_feature_gap_analysis.md`). **남은
확인 필요**: 실제 원격통제기 소프트웨어가 이 오기입 때문에 실제로 `RC_OperationMode=EMERGENCY`
값을 보낼 가능성이 있는지(레거시 동작) — 방어적으로 그 값이 오면 무시하거나 EmergencyStop과
동일하게 처리하도록 남겨둘 것(`lig_questions_0816.md` 후속 질문 후보).

### 3.3 RTSP — UGV축 (5스트림)

`전면CCTV`, `후면CCTV`, `좌측CCTV`, `우측CCTV`, `RCWS뷰어`. Q&A 원문: *"시뮬레이션이 RTSP
서버가 되어 필요한 곳에서 스트리밍"* — 즉 **UGV 시뮬레이션 SW(192.168.10.10)가 RTSP 서버**.

**Mount 이름 확정(2026-08-17, `rtsp_integration_status_0817.md` 후속 세션)** —
`<axis>/<stream>` 패턴으로 확정, `URtspStreamComponent::MountPath`에 그대로 반영됨
(`BP_UGV_Vehicle`에 추가한 `UVehicleRtspBridgeComponent`가 배선, `MountPrefix="ugv/"`):

| 스트림 | Mount | 소스 컴포넌트 |
|---|---|---|
| 전면CCTV | `ugv/front_cctv` | `QuadCam->GetFrontCamera()` |
| 후면CCTV | `ugv/rear_cctv` | `QuadCam->GetRearCamera()` |
| 좌측CCTV | `ugv/left_cctv` | `QuadCam->GetLeftCamera()` |
| 우측CCTV | `ugv/right_cctv` | `QuadCam->GetRightCamera()` |
| RCWS뷰어 | `ugv/rcws` | `RCWS->GetSightCamera()` |

URL: `rtsp://192.168.10.10:8554/ugv/<stream>` — 포트(8554)는 `RtspServerSubsystem` 기본값
그대로 유지. 인코딩 방식은 §7.

**전송/지연(2026-08-19 확정)** — RTP는 **TCP interleaved만 지원(UDP 미지원)**, gst-rtsp-server
설정상 그렇게 고정됨(§0의 "영상=RTSP" 전송계층 표에 이 세부가 빠져있었는데 실측으로 확정).
종단(glass-to-glass) 지연은 최초 441~484ms에서 서버(NVENC 버퍼 최소화)+수신측(GStreamer
저지연 옵션) 튜닝으로 **68ms(30~100ms 변동)**까지 개선됨 — 수신 구현 가이드/실측 수치는
`rtsp/rtsp_client_reception_guide.md`, 조사 전체 기록은 `rtsp/rtsp_latency_investigation.md`
참고.

---

## 4. 자체방호축 — Layer B 없음 (2026-08-07, 단일 프로그램으로 확정)

**이전 버전(NATS 기반 `console.selfdefense.*`)은 전부 폐기.** LIG 시스템 구성도 확인 결과
자체방호(이동형지휘소)축은 에뮬레이터+콘솔 분리가 아니라 **"자체방호 통제기 SW" 하나의
프로그램**이 조이스틱(USB) 입력을 직접 받아 시뮬레이션하고, 그 결과를 RTSP로 상위체계에
바로 송출함. 즉 이전에 여기 있던 `RC_UAVGimbal`/`RC_SetRCWSMode`/`TRK_Period_*` 같은
메시지들은 **네트워크 메시지가 아니라 같은 프로세스 내 함수 호출**로 남는다 — 프로토콜
문서에 실을 이유가 없어짐(구현 시엔 그냥 조이스틱 입력 → 컴포넌트 함수 직접 호출, §3.2의
UGV축 대응 함수와 개념적으로 동일한 것들을 로컬로 부르면 됨).

### 4.1 RTSP — 자체방호축 (7스트림) — 유일하게 남는 외부 인터페이스

`환경카메라`, `전면CCTV`, `후면CCTV`, `좌측CCTV`, `우측CCTV`, `RCWS뷰어`, `UAV드론뷰`.
자체방호 통제기 SW가 RTSP 서버.

**Mount 이름 확정(2026-08-17, `rtsp_integration_status_0817.md` 후속 세션)** — UGV축(§3.3)과
동일한 `<axis>/<stream>` 패턴, `ATitanTruck::SetupRtspStreams()`/`AUAVPawn::BeginPlay()`가 배선:

| 스트림 | Mount | 소스 컴포넌트 |
|---|---|---|
| 환경카메라 | `selfdefense/env_camera` | `ATitanTruck::BattlefieldCapture` |
| 전면CCTV | `selfdefense/front_cctv` | `QuadCam->GetFrontCamera()` |
| 후면CCTV | `selfdefense/rear_cctv` | `QuadCam->GetRearCamera()` |
| 좌측CCTV | `selfdefense/left_cctv` | `QuadCam->GetLeftCamera()` |
| 우측CCTV | `selfdefense/right_cctv` | `QuadCam->GetRightCamera()` |
| RCWS뷰어 | `selfdefense/rcws` | `RCWS->GetSightCamera()` |
| UAV드론뷰 | `selfdefense/uav_gimbal` | `AUAVPawn::GetGimbalCamera()`(별도 액터) |

URL: `rtsp://<selfdefense-pc-ip>:8554/selfdefense/<stream>` — 포트(8554)는 UGV축과 동일한
`RtspServerSubsystem` 기본값. 실제 IP는 여전히 미확정(UGV처럼 고정 IP를 LIG가 지정했는지
확인 필요, §6) — mount 이름/포트만 이번에 확정됨.

**검증 상태(2026-08-19)**: 인코더/서버 코드가 UGV축과 완전히 공유되는 구조라 전송 방식(TCP
interleaved만, UDP 미지원)과 저지연 튜닝(§3.3 참고)은 동일하게 적용됨. 6개 마운트(환경카메라
제외 — 상위체계로는 부가 스트림) 전부 GStreamer+NVDEC 파이프라인으로 접속·하드웨어 디코드까지
확인됨. 단 정밀 지연 재측정(§3.3의 68ms 실측 같은 스크린샷 방식)은 아직 안 함 — UGV축과 동등
수준으로 기대만 하는 상태, 확정치 아님. 상세는 `rtsp/rtsp_client_reception_guide.md` §1.2.

---

## 5. Layer A — 자체방호통제기SW ↔ 상위체계 — **미정, LIG 검토중**

Q&A 원문(2026-08-06): *"금일 확인 한 내용으로는 아직 자체방호통제기에서 상위 체계로 가는
ICD 정의는 안되어있고, 향후 추가 여부도 LIG 검토중에 있습니다."* 시스템 구성도에도 이
방향 화살표에 프로토콜 라벨이 없음(RTSP 영상 업로드만 확정, 명령 하달 채널은 없음).

**이 절 전체가 "확정 스펙"이 아니라 "LIG가 채널을 추가하기로 하면 바로 쓸 수 있는 선제
설계"다.** 폐기하지 않고 유지 — 아래 메시지 목록/의미는 그대로 유효하나, **봉투 포맷은
§1(b)(NATS 가정, 낡음)가 아니라 확정되는 시점에 §3과 같은 UDP+`{cmd,src,recv,data}`
패턴으로 다시 감쌀 예정**(전송계층 UDP 통일 결정, §0).

| 메시지 | 방향 | payload |
|---|---|---|
| `HQ_EnemyContactReport` | 상위체계→자체방호SW | `{ "contactId": string, "coord": Coord }` |
| `RPT_TargetsIdentified` | 자체방호SW→상위체계 | `{ "targets": Detection[] }` |
| `HQ_MissionMoveToEngage` | 상위체계→UGV SW | `{ "target": Coord, "radius": float(m) }` |
| `RPT_ObjectiveReached` | UGV SW→상위체계 | `{ "radius": float }` (FYI) |
| `RPT_ContactDetected` | UGV SW→상위체계 | `{ "targets": Detection[] }` |
| `HQ_EngagementAuthorization` | 상위체계→UGV SW | `{ "approved": bool, "contactId": string }` |
| `RPT_EngagementInitiated` | UGV SW→상위체계 | `{}` (FYI) |
| `RPT_EngagementResult` | UGV SW→상위체계 | `{ "kia": int, "fleeing": int }` |
| `HQ_MissionEngageFleeing` | 상위체계→자체방호SW | `{ "coord": Coord }` |
| `RPT_ScenarioComplete` | 자체방호SW→상위체계 | `{ "result": string }` |

> 참고: 이 표는 "상위체계→UGV SW"라고 적혀 있지만, LIG 구성도상 UGV축은 원격통제기(LIG)를
> 거쳐야 상위체계와 만남 — 실제로 이 채널이 생긴다면 상위체계↔UGV 쪽은 원격통제기가
> 중계할 가능성이 있음(우리 관할 밖). 이 표는 주로 **자체방호SW↔상위체계** 쪽에 의미가
> 있다고 봐야 함.

---

## 6. 결정된 것 / 남은 미확정 (2026-08-14 재갱신 — 정식 ICD 확보로 대부분 해소)

**결정됨(ICD로 확정)**:
- **UGV축 전송/IP/포트/신뢰성 메커니즘**: LIG 확정(§3.1).
- **cmd 목록/data 필드 전체**: `lig_icd_ugv_rc_full.md` — RC→UGV 방향(그동안 비어있던 부분)
  포함 전부 확정. 더 이상 추정 아님.
- **좌표계 = UTM**(East/North/Zone/Letter) — WGS84 lat/lon 아님, §2 확정.
- **BBox = 0~65535 정수 스케일링**(좌상단/우하단 절대좌표쌍) — 우리가 짰던 `{x,y,w,h}` UV
  타입 폐기.
- **device 코드(RC=20/UGV=14/UGV_RCWS=13/UGV_ADU=12) 실사용** — ICD 원문에 명시, 확정.
- **자체방호축엔 Layer B 자체가 없음**: 단일 프로그램(§4). RTSP는 상위체계행으로 계속 필요.
- **UGV/자체방호축 배틀필드 공유**: 자체 결정, LIG 확인 불필요.
- **재시도 횟수/ACK 타임아웃**: 자체 결정 + 설정 가능하게 노출(`udp_protocol_client/`의
  `RetryConfig` 패턴).
- **요청↔응답 상관관계**: ICD에도 seq/request-id 없음(확정 사실, 추정 아니게 됨). **[2026-08-28
  갱신]** LIG 확인: 원격통제기는 응답을 기다리지 않고 같은 cmd를 동시에 여러 번 보낼 수 있는
  구조 — 저희가 예전에 검토했던 "같은 cmd는 순차 처리만" 정책은 **우리가 강제할 필요 없음**,
  받는 요청마다 그 즉시 개별 응답을 보내주면 됨(상태 없는 즉시 응답 방식). UGV축 수신 처리
  로직이 동일 cmd의 중첩/연속 요청을 큐잉 없이 매번 즉시 응답하는지 재확인 권장.

**추가로 해소됨(2026-08-17~19)**:
- **RTSP 실제 카메라 연결** — UGV 5스트림 + 자체방호 7스트림(부가 1개 포함) 전부
  `URtspStreamComponent`를 실 카메라에 연결 완료, mount 이름 확정(§3.3/§4.1). 상세:
  `rtsp_integration_complete_0817.md`.
- **RTSP 종단 지연 최적화** — 441~484ms → 68ms(30~100ms 변동)로 개선(수신측 GStreamer+NVDEC
  채택). 상세: `rtsp/rtsp_latency_investigation.md`, `rtsp/rtsp_client_reception_guide.md`.
- **Linux 패키지 빌드 풀스크린 프레임 폭락(11fps)** — RTSP와 무관, SDL2가 Wayland 세션에서도
  Xwayland 경유 X11을 골라 소프트웨어 Present 카피를 하던 것이 원인으로 확정, `LinuxEngine.ini`
  `VideoDriver=wayland` 기본값 설정으로 해결(200fps+ 회복). 상세: `linux_wayland_x11_present_bottleneck.md`.

**LIG 1차 답변으로 해소됨(2026-08-28, `documents/response_0828.md`)**:
- `RC_OperationMode`↔`EUGVDriveMode` 매핑 — 대부분 해소(§3.2 하단 참고), 남은 건 레거시
  EMERGENCY 오기입 값이 실제로 오는지 여부만 후속 확인.
- `RC_EmergencyStop`/`Release`↔`OperationMode=Emergency` 관계, `RC_Control_Right`/
  `RC_OperationMode`의 주기 필드 확인 방식, 포트 분류 가정, `RC_FireWeapon` PRESSED/RELEASE
  이벤트 특성, `RC_ActivateFire` 의미, `Gear=Turn` 불필요 — 전부 확인/확정됨.
- ~~**`RC_ActivateMovement` 재매핑 필요(코드 수정 대상)**~~ — 차량 시동이 아니라 RCWS 조향 모터
  활성화였음(§3.2 표 참고). **2026-08-31 재매핑 완료** — `UUGVRemoteControlSubsystem::
  Handle_RC_ActivateMovement`가 `bEngineOn` 대신 `bRCWSSteeringActivated` 래치를 세우고,
  `Handle_RC_Movement`가 그 래치와 `BrakeButton`을 AND로 묶어 `AddPanTiltInput`을 게이팅한다.
  `bEngineOn`은 콘솔/BP 전용(`SetUGVEngineOn`)으로만 남김 — 차량 시동에 해당하는 별도 커맨드
  존재 여부는 `lig_questions_0816.md` 1-신규-2로 재질문 중.
- ~~`ObjectClass` 세분화(트럭/UGV/민간차량 구분)~~ — LIG는 선택사항으로 확인(세분화해도 되고
  `Car`로 통일해도 됨). **2026-09-02 결정+구현 완료** — 플랫 6값(`Ally`/`Enemy`/`UGV`/
  `MobileCommandPost`/`Drone`/`Parachute`)으로 확장(§2 `ObjectClass` 타입 참고). LIG엔 질문이
  아니라 결정 통보만 남음(`lig_questions_0816.md` §5-2, 미발송).

**아직 미확정**:
- **자체방호축 PC의 고정 IP 여부** — 상위체계행 RTSP 서버 주소용, LIG 확인 필요.
- **UTM Zone/Datum 정확한 값** — ICD에 필드는 있으나 시연 장소의 실제 Zone 번호는 미기재,
  확인 필요.
- **참조구현(`udp_test`)의 IP(192.168.0.84)/포트(7777/7778)가 개발용 임시값인지** — 정식
  ICD의 192.168.10.x:8000번대와 다름, 참조구현 자체가 스텁이라 우선순위 낮음.

**UDP 테스트 도구**: Postman 등 HTTP 중심 도구로는 raw UDP 테스트 불가. 전략은
`architecture_decisions.md` §8 참고(자체 Python UDP 스크립트가 1순위, Wireshark로 와이어
레벨 검증, Packet Sender는 보조용).

## 7. LIG 참조구현(`udp_test`) 대조 요약 (2026-08-07)

`C:\working\works\kadex\udp_test` — LIG가 보내준 UGV축 UDP+JSON 참조 구현. 전체 대조는
`udp_test_findings.md` 참고, 핵심만:

- **송신측 데모/스텁 수준** — RC→UGV 제어 명령 없음, 수신 처리 없음(로그만), 죽은 코드/
  더미값 다수. cmd 이름·필드 추정치로 신뢰하기엔 이르지만, **필드 네이밍 패턴(특히 좌표계)은
  신빙성 있는 단서**로 취급.
- 확인된 cmd 예시(전부 미확정 취급, 최종본 아님): `UGV_Period_Basicinfo`,
  `UGV_RCWS_Status`, `UGV_Period_BasicInformation`, `UGV_Period_NavigationInformation`,
  `SEND_UGV_PERIOD_OBJECTDETECTIONRESULT`, `UGV_Response_Connection`, `UGV_Response_BIT`,
  `UGV_Response_BIT_ADU`.
- `S_DetectedObject` 구조체 확인: `ObjectID`/`ObjectClass`/`LeftTopX/Y`/`RightBottomX/Y`/
  `East`/`North`/`Zone`/`Letter`/`Velocity`/`Altitude` — 우리 `Detection`/`BBox` 타입과
  다름(절대좌표 정수쌍, UTM류 위치정보 포함).
- 요청↔응답 상관관계 필드 없음 — 우리 발견이 참조구현에서도 그대로 확인됨(구조적 한계로
  간주, 위 §6 "요청↔응답 상관관계" 결정 참고).

## 7. RTSP 구현 방식 (변경 없음, LIG 답변으로 방향 재확인됨)

- **RTSP 송출**: UE에서 NVENC로 직접 인코딩(zero-copy, CUDA-D3D11 interop) → 인코딩된 H.264
  비트스트림만 GStreamer `gst-rtsp-server`의 `appsrc`에 공급 → RTSP 세션 협상/SDP/RTP 패킷화는
  GStreamer가 담당. live555는 대안, 완전 자체구현은 비추천(RFC 6184 등 표준 준수 부담).
  GStreamer/gst-rtsp-server는 LGPL — 내부 데모 용도라 실무상 문제 소지는 낮으나 최종 납품
  형태에 따라 법무 확인 권장. 일정 리스크: PoC 1~2일, 프로덕션 안정화까지 1~2주로 예상.
- LIG 답변(*"시뮬레이션이 RTSP 서버가 되어 필요한 곳에서 스트리밍"*)이 이 방향과 정확히
  일치 — 변경 불필요, 트랙1 계속 진행.
