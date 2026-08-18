# UGV_RC_ICD 전체 원문 (2026-08-14, LIG 정식 ICD 확보)

원본: `C:\Users\user\Downloads\UGV_RC_ICD (1).xlsx` (암호 보호, 복호화 완료). 4개 시트.
**이 문서가 UGV축 프로토콜의 최종 확정 스펙 — `protocol_icd.md` §3의 "우리 추정치"를 전부
이걸로 교체.** LIG가 예고했던 "cmd 코드 목록/데이터 송수신 참조 모듈"이 바로 이 파일로 보임.

---

## 시트1: 통신 프로토콜 (기존 확인 내용과 동일, 재확인만)

- 전송: UDP, JSON. 데이터 종류: 주기성 메시지 / 이벤트(비주기) 메시지.
- 봉투: `{ cmd, src, recv, data: {...} }`
- device 코드: `RC=20`(원격통제기), `UGV=14`, `UGV_RCWS=13`, `UGV_ADU=12`
- IP/Port: UGV=`192.168.10.10`(8000 주기/8001 비주기), 원격통제기=`192.168.10.20`(8010 주기/8011 비주기)

## 시트2: 슈어 → LIG (**우리가 보내는 메시지**, UGV 시뮬레이션 SW → 원격통제기)

### 차량제어 (src=UGV, 14)

| cmd | 설명 | 필드 | 타입 | 값 | 주기 |
|---|---|---|---|---|---|
| `UGV_Response_Connection` | 연결 응답 | `ResponseDevice` | String | `1`: 원격통제기 | 비주기 |
| `UGV_Period_Basicinfo` | 차량상태보고 | `OperationMode` | String | `Stay`:대기, `Remote`:원격주행, `FAD`:종속주행, `HAD`:자율주행, `5`:전원차단준비, `6`:충전, `Emergency`:비상 | **10Hz** |
| | | `ConrtrolRight`(원문 오타) | String | `None`:없음, `Remote`:원격통제기 | |
| | | `Speed` | Int | 0~100 | |
| | | `Gear` | String | `Front`:전진, `Back`:후진, `Turn`:제자리선회 | |
| | | `Batterry`(원문 오타) | Int | 0~100% | |
| `UGV_Response_BIT` | 차량 운용 정보 보고 | `StatusVMU` | String | `OFF`:해당무, `ON`:해당 | 비주기 |
| | | `CountValue` | String | 원격통제기가 보낸 카운팅값을 그대로 응답 | |

### RCWS (src=UGV_RCWS, 13)

| cmd | 설명 | 필드 | 타입 | 값 | 주기 |
|---|---|---|---|---|---|
| `UGV_RCWS_Status` | RCWS 상태 | `RCWSStatus` | String | `OFF`:비접속, `ON`:접속 | **20Hz** |
| `UGV_Period_ObjectDetectionResult` | RCWS 객체 인식 결과 | `TotalObject` | Int | 0~10 | |
| | | `Objects[]` | Array | 아래 객체 필드 참고 | |

**Objects[] 필드 (RCWS/ADU 공용, 시트2 두 곳 다 동일 구조)**:

| 필드 | 설명 | 타입 | 값 |
|---|---|---|---|
| `ObjectID` | 객체 ID | Int | 1~65535 |
| `ObjectClass` | 객체 분류 | String | `Human`:사람, `Car`:차량 |
| `LeftTopX` | 박스 좌상단 X (우측+) | Int | **65535 스케일링**: `결과 = 픽셀X * 65535 / 영상가로크기` |
| `LeftTopY` | 박스 좌상단 Y (아래+) | Int | `결과 = 픽셀Y * 65535 / 영상세로크기` |
| `RightBottomX` | 박스 우하단 X | Int | 위와 동일 스케일링 |
| `RightBottomY` | 박스 우하단 Y | Int | 위와 동일 스케일링 |
| `East` | 위치(UTM) East | Int | 8자리 |
| `North` | 위치(UTM) North | Int | 10자리 |
| `Zone` | 위치(UTM) Zone | Int | |
| `Letter`(RCWS쪽 원문은 `Latter` 오타) | 위치(UTM) Letter | String | |
| `Velocity` | 속도 | Int | |
| `Altitude` | 고도 | Int | |

**→ 좌표계 확정: UTM(East/North/Zone/Letter), WGS84 lat/lon 아님.** 우리 쪽 의문(§1-2) 해소.
**→ BBox 확정: 정규화 UV(0~1)가 아니라 0~65535 정수 스케일링, 계산식까지 명시됨.**

### 자율 (src=UGV_ADU, 12 — 참고: "[원격통제기(LIG) -> 원격통제처리기(현대로템)]"라는 주석이
있음, 즉 ADU 실물은 현대로템 제품 — 우리는 이 device 응답을 시뮬레이터가 대신 흉내내는 것)

| cmd | 설명 | 필드 | 타입 | 값 | 주기 |
|---|---|---|---|---|---|
| `UGV_Response_BIT_ADU` | 자율주행 상태 응답 | `StatusADU` | String | `On`:정상, `Off`:비정상 | 비주기 |
| | | `StatusVMU` | String | `On`:정상(Ethernet), `Off`:연결끊김 | |
| | | `StatusNavigation` | String | `On`:정상(Serial), `Off`:연결끊김 | |
| | | `Status3DLidar` | String | `On`:정상(Ethernet), `Off`:연결끊김 | |
| | | `StatusRadar` | String | `On`:정상(Ethernet), `Off`:연결끊김 | |
| | | `StatusOCS` | String | `On`:정상(Ethernet), `Off`:연결끊김 | |
| `UGV_Period_BasicInformation` | 자율주행 기본정보 | `Odometer` | Int | 단위: m | |
| `UGV_Period_NavigationInformation` | 자율주행 네비게이션 정보 | `East`/`North`/`Zone`/`Letter` | Int/Int/Int/String | UTM(8자리/10자리) | |
| | | `Velocity` | Int | | |
| | | `Heading` | Int | 자세(헤딩) | |
| | | `Altitude` | Int | | |
| `UGV_Period_ObjectDetectionResult` | 자율주행 객체 탐색 결과 | (RCWS와 동일 Objects[] 구조) | | | |
| `UGV_Response_Connection` | 연결 요청 응답 | `ResponseDevice` | String | `Remote`: 원격통제장치 | 비주기 |

> 주의: `UGV_Period_ObjectDetectionResult`는 **RCWS(13)와 ADU(12) 양쪽에서 같은 cmd 이름을
> 재사용** — `src` 필드로만 구분됨.

---

## 시트3: LIG → 슈어 (**우리가 받아서 처리해야 하는 메시지**, 원격통제기 → UGV 시뮬레이션 SW)

**이게 그동안 비어있던 RC→UGV 제어 명령 전체 목록입니다** — `udp_test` 참조구현엔 전무했던
바로 그 부분.

### 차량제어

| cmd | 설명 | 필드 | 타입 | 값 | 주기 |
|---|---|---|---|---|---|
| `RC_Connection` | 연결요청 | `RequestDevice` | Int | `0`:None, `1`:RC (재연결 시도 1Hz) | 비주기 |
| `RC_Request_BIT` | 비트요청 | `RequestBit` | Int | MAX INT까지 | 1Hz |
| `RC_Control_Right` | 제어권 상태 | `ControlRight` | Int | `0`:None, `1`:원격통제기 | 비주기 |
| **`RC_RemoteDriving`** | **차량 주행 명령** | `Acceleration` | Int | 0~100 | **20Hz** |
| | | `Brake` | Int | -0~-100 | |
| | | `Steering` | Int | `0`:None, `0<우조향`(0~100), `0>좌조향`(-0~-100) | |
| | | `Gear` | Int | `FRONT`:전진, `BACK`:후진 | |
| `RC_EmergencyStop` | 비상정지 명령 | `CommandDevice` | Int | `1`==동작 | 비주기 |
| `RC_EmergencyStopRelease` | 비상정지 해제 명령 | `CommandDevice` | Int | `1`==동작 | 비주기 |
| **`RC_OperationMode`** | **주행 모드 설정** | `OperationMode` | String | `STAY`:대기, `REMOTE`:원격주행, `EMERGENCY`:비상 | 비주기 |
| `RC_SelectCamera` | 카메라 종류 설정 | `SelectCameraButton` | String | `RELEASE`:EO, `PRESSED`:IR | 비주기 |
| `RC_FireMode` | 발사 모드 설정 | `FireMode` | String | `SINGLE`:단발, `BRUST`(원문):점사, `CONTINUS`(원문):연사 | 비주기 |
| `RC_ChargeWeapon` | 장전 명령 | `ChargeSwitch` | String | `OFF`:비장전, `ON`:장전 | 비주기 |
| **`RC_FireWeapon`** | **발사 명령** | `FireButton` | String | `RELEASE`:대기, `PRESSED`:사격 | 비주기 |
| `RC_MotionMode` | 기동 모션 모드 설정 | `MotionMode` | String | `RELEASE`:활성, `PRESSED`:비활성 | 비주기 |
| `RC_Movement` | RCWS 조준 관련 | `BrakeButton` | String | `RELEASE`:활성, `PRESSED`:비활성 (브레이크 모션) | 비주기 |
| | | `XAxis`(12bit) | Int | `0`:None, `0<우조향`(0~100), `0>좌조향`(-0~-100) — 화면 x축 모션 | |
| | | `YAxis`(12bit) | Int | `0`:None, `0<상조향`(0~100), `0>하조향`(-0~-100) — 화면 y축 모션 | |
| `RC_ActivateFire` | 발사 상태 설정 | `ActivateFireToggle` | String | `RELEASE`:활성, `PRESSED`:비활성 | 비주기 |
| `RC_ActivateMovement` | 구동 상태 설정 | `ActivateMovementToggle` | String | `RELEASE`:활성, `PRESSED`:비활성 | 비주기 |

### 자율 [원격통제기(LIG) → 원격통제처리기(현대로템)]

| cmd | 설명 | 필드 | 타입 | 값 | 주기 |
|---|---|---|---|---|---|
| `RC_Connection_ADU` | 자율처리기 연결 요청 | `RequestDevice` | String | `REMOTE` 원격통제장치 (재연결 1Hz) | 비주기 |
| `RC_Request_BIT_ADU` | 자율처리기 상태정보 요청 | `CountValue` | Int | MAX INT까지 | 1Hz |

---

## 시트4: SQ_Diagram (시퀀스/상태 다이어그램)

이미지로 별도 확인(`C:\Users\user\Pictures\초기접속SQ.png`, `주기메세지SQ.png`,
`주행명령상태천이.png` — RCWS명령상태천이는 빈 시트라 이미지 없음). 내용은 원본 PDF p.11과
사실상 동일 — 아래는 이번에 새로 명확해진 것만:

- **주행명령 상태천이**: `RC_RemoteDriving` 수신 시 → 제어권 설정 확인(`RC_Control_Right`,
  0/1) → 주행모드 확인(`RC_OperationMode`: STAY/EMERGENCY면 무시, REMOTE면 진행) → 기어상태
  (`Gear` 필드: FRONT→전진가속/BACK→후진가속+감속). **`제어권`/`주행모드`/`기어`가 서로 다른
  3개 커맨드(`RC_Control_Right`/`RC_OperationMode`/`RC_RemoteDriving.Gear`)의 조합으로
  풀린다는 게 이번에 확정됨** — 예전에 우리가 "Idle이 STAY/EMERGENCY를 커버하니 폐기"라고
  결정했던 것을 재검토해야 함(§ 아래 "우리 설계와의 차이" 참고).

---

## 우리 설계와의 차이 — 반영 필요

1. **좌표계 UTM 확정** — `protocol_icd.md` §2의 "재검토 중" 상태를 "확정: UTM"으로 전환.
   `lig_questions_0807_draft.md` §1 질문 삭제(해소됨).
2. **RC→UGV 명령 전체 확정** — `protocol_icd.md` §3.2 전면 교체. `RC_RemoteDriving`(조향/가속/
   브레이크/기어), `RC_FireWeapon`(발사), `RC_OperationMode`(STAY/REMOTE/EMERGENCY) 등 실제
   구현 대상 함수와 매핑 필요(`SetUGVMode`, `RC_ManualDrive` 등 우리 추정 이름 전부 폐기하고
   이 표의 실제 cmd 이름 사용).
3. **`RC_OperationMode`의 STAY/EMERGENCY가 실제로 존재** — `replication_audit.md`/
   `architecture_decisions.md`에서 "Idle이 STAY/EMERGENCY 커버, 폐기"라고 결정했던 부분 재검토
   필요. `EUGVDriveMode(Idle/Manual/Auto)`가 `RC_OperationMode`(STAY/REMOTE/EMERGENCY)와
   어떻게 매핑되는지 재정의 필요 — 특히 `EMERGENCY`(비상정지, `RC_EmergencyStop`/
   `RC_EmergencyStopRelease` 별도 커맨드도 있음)는 우리 쪽에 대응 개념이 아예 없었음.
4. **device 코드 실사용 확인됨** — `udp_test` 참조구현에서 `src`/`recv`가 리터럴 `"device"`
   였던 것과 달리, 이 정식 ICD엔 값이 명확히 정의돼 있음(RC=20 등) — 다만 이 정식 ICD
   자체엔 `src`/`recv`를 실제로 어떻게 채우는지 예시가 없어서, 각 cmd 표의 소속 그룹(차량제어/
   RCWS/자율)이 곧 `src`(우리가 보낼 때)/`recv`(우리가 받을 때 검증용) 값이라고 해석.
5. **BBox가 0~65535 정수 스케일링** — `protocol_icd.md`의 `BBox {x,y,w,h} 0~1 UV` 타입을
   이 스케일링 방식으로 교체(계산식 명시됨).
6. **`RC_Movement`가 RCWS 조준+브레이크를 한 커맨드로 묶음** (`BrakeButton`+`XAxis`+`YAxis`) —
   우리가 짰던 `Movement{pan,tilt}`보다 필드가 더 많고 이름도 다름.
7. **`lig_questions_0807_draft.md` 대폭 정리 필요** — 좌표계, cmd 목록, device 코드 실사용
   여부 질문 전부 이 문서로 해소됨. 남는 건 참조구현(`udp_test`)의 IP/포트가 임시값인지, 자체
   방호축 고정 IP, RTSP URL 정도.
