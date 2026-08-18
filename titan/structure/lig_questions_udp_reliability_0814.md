# LIG 문의 — UDP 비주기 명령 유실 시 확인/재시도 메커니즘 부재 (2026-08-14, 신규)

**[2026-08-16] 이 문서는 `lig_questions_0816.md`로 통합됨 — 더 이상 갱신 안 함, 기록용으로만
남김. 새 질문은 `lig_questions_0816.md`에 추가할 것.**

**우선순위: 높음 — `lig_questions_0807_draft.md`보다 먼저, 별도로 확정 답변 받아야 함.**
안전(비상정지/사격)에 직접 걸리는 문제라 "우리가 알아서 방어적으로 구현"만으로 덮기엔 위험이
남는다고 판단, 정식으로 LIG 확인 필요.

---

## 1. 배경 — 왜 문제인가

UDP는 전송 계층에서 순서보장·재전송·수신확인이 전혀 없다. ICD(`lig_icd_ugv_rc_full.md`)가
명시하는 신뢰성 메커니즘은 두 가지뿐이다:

- **주기성 메시지(Request/Response)**: 응답이 몇 회까지 안 오면 Request 재시도(횟수 미기재)
- **이벤트 메시지(Message/ACK)**: `( )msec` 내 ACK 없으면 **3회까지** Message 재시도(msec 값
  미기재)

문제는 시트3(RC→UGV, `RC→UGV (우리가 받아서 처리)`) 커맨드 대부분이 **이 두 패턴 중 어느
쪽에도 명시적으로 편입돼 있지 않다**는 점이다 — cmd 자체는 "비주기"로만 표기돼 있고, 대응하는
`UGV_Response_*`/ACK cmd가 시트2(UGV→RC)에 없다. 즉 **ICD상 어떤 재시도/확인 규칙을 적용해야
하는지 정의가 안 된 명령들이 다수 존재**한다. 유일하게 응답 짝이 있는 건 `RC_Connection`
(↔`UGV_Response_Connection`)과 `RC_Request_BIT`(↔`UGV_Response_BIT`) 뿐.

---

## 2. 위험도 분류

### 2-1. 유실돼도 자체 치유되는 것들 — 질문 불필요

**연속 스트림 성격(20Hz), 다음 패킷이 최신 상태로 자연 덮어씀:**
- `RC_RemoteDriving` (조향/가속/브레이크/기어)
- `RC_Movement` (RCWS pan/tilt + 브레이크)

**ICD가 이미 Request/Response+1Hz 재시도로 명시:**
- `RC_Connection` / `RC_Connection_ADU`
- `RC_Request_BIT` / `RC_Request_BIT_ADU`

### 2-2. 잠재적으로 자체 치유 가능 — 단, LIG 쪽 구현에 달려 있어 확인 필요

`RC_Control_Right`(제어권)와 `RC_OperationMode`는 전용 ACK는 없지만, UGV가 `UGV_Period_
Basicinfo`(10Hz)로 `ConrtrolRight`/`OperationMode` 필드를 계속 방송한다. **원격통제기(LIG)
소프트웨어가 이 주기 필드를 보고 "명령이 반영됐는지" 확인 후 재시도하는 구조라면** 최대
~100ms 안에 자체 치유되지만, **원격통제기가 단순 fire-and-forget으로 한 번만 보내고 끝이라면**
2-3의 것들과 동일하게 위험하다 — 이건 우리가 알 수 없고 LIG 확인이 필요한 부분(질문 Q2).

### 2-3. 위험한 것들 — 유실되면 그냥 끝, 텔레메트리로도 확인 불가

전용 ACK도 없고, 주기 메시지 어디에도 이 상태를 반영하는 필드가 없음:
- `RC_SelectCamera`, `RC_FireMode`, `RC_ChargeWeapon` — 유실되면 조작자가 설정했다고 믿는
  값과 실제 상태가 어긋남. 운용상 성가신 수준, 안전사고는 아님.

### 2-4. 안전 최우선 — 위험도가 차원이 다른 2개

- **`RC_EmergencyStop`** — 유실되면 비상정지 명령이 UGV에 아예 안 들어감. 재시도 규칙조차
  ICD에 명시가 없어(비주기로만 표기) 애초에 재시도가 되는지도 불확실 — **단일 실패 지점 중
  가장 위험.** (`RC_OperationMode=EMERGENCY`와의 관계도 불명확 — Q3 참고.)
- **`RC_FireWeapon`의 `RELEASE`(방아쇠 뗌)** — `PRESSED`(사격) 유실은 "안 쏨"으로 fail-safe지만,
  **`RELEASE` 유실은 "방아쇠 뗐는데 계속 쏨"** — 오발/폭주 사격 시나리오. `FireButton`이 조이스틱
  축처럼 연속 반복 전송되는 게 아니라 버튼 전환 시점 1회성 이벤트라면(ICD가 Hz 표기 없이
  "비주기"로만 되어 있어 그렇게 보임), 실질적으로 가장 위험한 지점.

---

## 3. LIG에 물어볼 것

**Q1. `RC_EmergencyStop`/`RC_EmergencyStopRelease`의 신뢰성 메커니즘.**
전용 응답(ACK) cmd가 없는데, 원격통제기가 이 명령을 보낸 뒤 UGV의 수신/실행 여부를 어떻게
확인하나요? (a) 저희 쪽에 새 응답 cmd(예: `UGV_Response_EmergencyStop`) 추가를 요청해도 되는지,
(b) 아니면 원격통제기가 이미 다른 방식(예: 반복 송신, 또는 아래 Q3의 `OperationMode` 필드 감시)
으로 확인하고 있는지 알고 싶습니다. 안전 관련 최우선 명령이라 유실 시 무대응이 되는 상황은
피해야 한다고 판단합니다.

**Q2. `RC_FireWeapon`(특히 `RELEASE`)의 신뢰성 메커니즘.**
`PRESSED`(사격 시작)/`RELEASE`(사격 중지) 각각이 매 프레임 반복 전송되는 값인가요, 아니면
버튼 상태가 바뀌는 시점에만 1회 전송되는 이벤트인가요? 후자라면 `RELEASE` 유실 시 UGV가 계속
사격 상태로 남을 위험이 있는데, 이에 대한 별도 안전장치(예: 발사 지속시간 상한, watchdog
타임아웃으로 자동 정지 등)가 UGV 쪽(혹은 LIG 원격통제기 쪽)에 이미 있는지 확인 부탁드립니다.
없다면 저희 UGV 시뮬레이션 SW 구현에 "N초 이상 `RC_RemoteDriving`류 갱신이 없으면 자동
정지"에 준하는 자체 워치독을 넣는 게 맞는지 검토 중입니다.

**Q3. `RC_Control_Right`/`RC_OperationMode`와 `UGV_Period_Basicinfo`의 `ConrtrolRight`/
`OperationMode` 필드 간의 관계.**
이 두 명령은 전용 ACK는 없지만, UGV가 10Hz 주기 메시지로 현재 `ConrtrolRight`/`OperationMode`
값을 계속 보고합니다. 원격통제기 소프트웨어가 이 주기 필드를 명령 반영 여부의 확인 수단으로
사용해서 필요 시 재전송하는 구조인가요? 그렇다면 저희 쪽에서 별도 ACK를 요청할 필요는 없다고
판단됩니다.

**Q4. `RC_EmergencyStop`과 `RC_OperationMode=EMERGENCY`의 관계.**
이 둘이 같은 상태를 가리키는 건지(즉 `RC_EmergencyStop` 수신 시 UGV가 내부적으로
`OperationMode`를 `Emergency`로 전환해서 10Hz 방송에 반영하는지), 아니면 서로 독립된 별개
개념인지(예: `EmergencyStop`=즉시 물리 제동, `OperationMode=EMERGENCY`=주행 입력을 무시하는
모드 플래그) 확인 부탁드립니다. 전자라면 Q1의 확인 수단으로 `OperationMode` 필드를 그대로 쓸
수 있어 문제가 상당 부분 해소됩니다.

**Q5. `RC_SelectCamera`/`RC_FireMode`/`RC_ChargeWeapon`의 상태 확인 수단.**
이 세 명령은 유실 시 조작자가 인지한 설정과 실제 UGV 상태가 어긋날 수 있는데, 현재 상태를
확인할 수 있는 주기 필드나 응답 cmd가 ICD에 없어 보입니다. 누락된 건지, 아니면 원격통제기 UI
자체에서 별도로 상태를 보여주는 방식이 있는지 확인 부탁드립니다.

---

## 4. 답변 오기 전까지 우리 쪽 임시 대응 (참고용, LIG 질문 아님)

- Q1/Q2 답변이 늦어질 경우를 대비해, UGV 시뮬레이션 SW 자체에 **`RC_RemoteDriving`/`RC_Movement`
  류 갱신이 일정 시간(예: 500ms~1s) 끊기면 자동으로 안전 정지**하는 워치독을 구현 검토 —
  이건 LIG 프로토콜을 벗어나지 않는 우리 쪽 방어적 구현이라 확인 없이도 진행 가능.
- `RC_FireWeapon`도 동일한 워치독 대상에 포함 — 마지막 `PRESSED` 이후 일정 시간(예: 2-3초)
  넘게 갱신이 없으면(정상이라면 `RELEASE`가 왔어야 할 상황) 자동으로 사격 중단하는 자체
  타임아웃을 안전장치로 추가하는 방향을 검토 중.
- 이 임시 대응은 Q1/Q2 답변으로 대체되거나 조정될 수 있음 — 지금은 "최악의 경우에도 UGV가
  스스로 멈춘다"는 fail-safe만 확보하는 목적.

---

## 5. 관련 문서

- `lig_questions_0807_draft.md` — 다른 남은 문의(요청/응답 상관관계 ID, UTM Zone/Datum,
  `udp_test` IP/포트, 자체방호축 고정 IP, RTSP URL). 이 문서와 별개로 발송하거나, 같이 묶어서
  한 번에 보내도 무방.
- `protocol_icd.md` §3.1(신뢰성 메커니즘 원문 요약), §3.2(cmd 표)
- `lig_icd_ugv_rc_full.md` (ICD 원문 전체)
