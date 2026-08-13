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

**좌표계 재검토 중 (2026-08-07)** — 원래 위경도(WGS84)로 확정했었으나, LIG 참조구현
(`udp_test`)에서 `East`/`North`/`Zone`/`Letter` 필드 패턴이 일관되게 발견돼 **UTM일 가능성이
높아짐** — LIG 답변 대기(`lig_questions_0807_draft.md` §1).

**대응 방침: 와이어 포맷은 LIG 답 기다리되, 내부 `Coord` 타입은 처음부터 양쪽 다 지원.**
WGS84 lat/lon ↔ UTM은 결정론적으로 상호 변환 가능(UTM 자체가 위경도+타원체 투영)하므로,
**내부 canonical 저장은 lat/lon 하나로 하고, UTM이 필요한 시점(와이어 직렬화 등)에 변환
함수로 계산**하는 구조로 간다 — lat/lon과 UTM을 각각 따로 저장하면 sync 어긋나는 버그가
생길 수 있어서 피함. 이러면 LIG 답이 뭐로 오든 코드 변경 없이 직렬화 시점의 출력 포맷만
바꾸면 됨(원칙 5: 되돌리기 싼 결정은 미루되, 양쪽 다 되게 만들어 미루는 비용 자체를 없앰).
UTM Zone은 카덱스 시연 장소가 고정 지역이라 사실상 고정값일 가능성 높음(경도로 자동
계산하는 표준 공식도 있음) — 정확한 Zone/Datum은 `lig_questions_0807_draft.md`에서 확인
중. 변환 로직은 `GeoCoordinateUtils.h`에 추가(기존엔 씬 스케일↔위경도만 지원, UTM 변환
함수 추가 필요 — Track4/5 몫).

```
Coord      { "lat": double, "lon": double, "alt": float }
             // lat/lon: WGS84 십진수 도(°), double — 소수점 7자리는 있어야 cm급 정밀도. 이게 canonical 내부 표현.
             // alt: 미터, AGL — 지상 유닛은 0 고정
             // 와이어로 UTM이 필요하면 이 값에서 East/North/Zone/Letter로 변환해서 내보냄(§7 예시 필드명 참고)
BBox       { "x": float, "y": float, "w": float, "h": float }  // 화면 UV 0~1 — 우리가 생성하는 데이터라 이 형태 유지 가능(§6)
Detection  { "id": string, "type": "Person"|"Vehicle", "bbox": BBox, "coord": Coord|null, "confidence": float }
```

**단위 표준**: 거리/반경/고도 = 미터(m), 속도 = m/s, 각도 = 도(°), 배터리 = 0~1 소수,
시간 = ms.

**LIG의 `data` 필드 내부 key/value가 이 타입들과 정확히 어떻게 맞물리는지는 아직 미확인**
— LIG가 예고한 "cmd 코드 목록/데이터 송수신 참조 모듈"(§6) 도착 시 재확인 필요. 좌표를
lat/lon으로 주는지, 우리가 가정한 필드명을 그대로 쓰는지 등은 우리 추정.

---

## 3. UGV축 — UGV 시뮬레이션 SW ↔ 원격통제기 — **외부 확정 스펙 (LIG, 2026-08-06)**

**우리가 설계한 게 아니라 LIG가 이미 구현한 원격통제기에 맞춰서 우리가 구현해야 하는
인터페이스.** 아래 IP/포트/신뢰성 메커니즘은 확정, cmd 값 목록/data 필드 상세는 LIG 참조
모듈 도착 전까지 우리 추정치(원본 PDF p.11 + 이번 답변 종합).

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

### 3.2 메시지 (우리 추정 — LIG 실제 cmd 코드로 교체 예정)

원래 §3.2~3.3에 있던 명령 목록을 LIG 봉투 형식(`cmd`/`src`/`recv`/`data`)으로 재매핑.
`src`/`recv`는 `RC`(원격통제기, 20) / `UGV`(14) / `UGV_RCWS`(13) / `UGV_ADU`(12) 중 하나.

| cmd(추정) | src→recv | data | 매핑 |
|---|---|---|---|
| `SetUGVMode` | RC→UGV | `{ mode: Idle\|Manual\|Auto }` | `SetUGVMode` |
| `ManualDrive` | RC→UGV | `{ forward, turn: [-1,1] }` | `SetManualControl()`, Manual만 |
| `MissionWaypoint` | RC→UGV | `{ target: Coord, radius(m) }` | Auto 모드 목적지 |
| `SetRCWSMode` | RC→UGV_RCWS | `{ mode: 4단계 }` | `SetRCWSMode` |
| `Movement` | RC→UGV_RCWS | `{ pan, tilt }` | RCWS 조준, Remote만 |
| `ManualFire` | RC→UGV_RCWS | `{}` | 발사 |
| `PeriodBasicInfo` | UGV→RC | `{ pos: Coord, speed, battery, driveMode, odometer }` | 주기 |
| `PeriodObjectDetectionResult` | UGV_ADU→RC | `{ targets: Detection[] }` | 주기 |
| `PeriodNavigationInfo` | UGV_ADU→RC | `{ waypoint: Coord, distanceRemaining }` | 주기 |
| `PeriodRCWSStatus` | UGV_RCWS→RC | `{ mode, aimPan, aimTilt, loaded, fireReady, zoom }` | 주기 |

**주의: 위 cmd 이름/필드명은 우리 쪽 추정치다.** 실제 값은 LIG가 "내일 중 전달"하기로 한
데이터 송수신 참조 모듈에서 확정됨 — 도착 즉시 이 표를 그걸로 교체.

### 3.3 RTSP — UGV축 (5스트림)

`전면CCTV`, `후면CCTV`, `좌측CCTV`, `우측CCTV`, `RCWS뷰어`. Q&A 원문: *"시뮬레이션이 RTSP
서버가 되어 필요한 곳에서 스트리밍"* — 즉 **UGV 시뮬레이션 SW(192.168.10.10)가 RTSP 서버**.
URL 잠정: `rtsp://192.168.10.10:8554/<stream>` — 정확한 포트/경로 규칙은 LIG 참조 모듈
또는 PoC 이후 확정. 인코딩 방식은 §7.

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
자체방호 통제기 SW가 RTSP 서버. URL 잠정: `rtsp://<selfdefense-pc-ip>:8554/<stream>` —
실제 IP는 미확정(UGV처럼 고정 IP를 LIG가 지정했는지 확인 필요, §6).

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

## 6. 결정된 것 / 남은 미확정 (2026-08-07 재갱신)

**결정됨**:
- **UGV축 전송/IP/포트**: LIG 확정(§3.1).
- **UGV축 신뢰성 메커니즘**: 앱레벨 ACK+재시도(§3.1), NATS/JetStream 아님.
- **자체방호축엔 Layer B 자체가 없음**: 단일 프로그램(§4). 단, **RTSP는 여전히 필요** —
  에뮬레이터↔콘솔 간 RTSP는 통합으로 불필요해졌지만, **자체방호통제기SW→상위체계로 가는
  RTSP는 별개 링크로 계속 필요**(LIG 시스템 구성도에도 명시).
- **JSON 페이로드**: 이건 어차피 LIG도 JSON이라 자연스럽게 일치.
- **UGV/자체방호축 배틀필드 공유**: 자체 결정, LIG 확인 불필요 — 계획대로 리플리케이션 유지.
- **RC→UGV 제어 명령(RC_RemoteDriving 등) 구현 주체**: 참조구현(§7 하단)에 없어도 우리가
  ICD 기준으로 직접 구현.
- **재시도 횟수/ACK 타임아웃**: 자체 결정 + 설정 가능하게 노출(`udp_protocol_client/`의
  `RetryConfig` 패턴) — LIG 확정값 안 기다림.
- **요청↔응답 상관관계**: 봉투에 seq/request-id가 없어서(§7 참고) 완벽한 해법은 없음 —
  **"같은 cmd는 이전 응답을 받은 뒤에만 다음 요청, 서로 다른 cmd끼리는 동시 요청 허용"**
  방식으로 확정(전면 동기보다 나은 절충안, `udp_protocol_client/` 코드 업데이트 필요).
- **Bounding Box 좌표 기준**: `UGV_Period_ObjectDetectionResult`는 우리가 생성하는 데이터라
  우리가 설계 — 카메라별로 명확히 구분되게 필드 설계, LIG 확인 대상 아님.
- **`UGV_Response_Connection`/`BIT`/`BIT_ADU` 정확한 의미**: 추측해서 구현, 필요시 나중에
  LIG와 맞춤.

**아직 미확정 (LIG 답변 대기, `lig_questions_0807_draft.md` 발송 예정)**:
- **좌표계가 위경도(WGS84)인지 UTM(Easting/Northing/Zone/Letter)인지** (2026-08-07,
  `udp_test_findings.md`에서 UTM류 필드 패턴 발견 — **§2의 "WGS84 확정"이 틀렸을 가능성
  높음, 미확정으로 되돌림**). 답 오기 전까지는 UTM 가능성 열어두고 설계.
- **LIG cmd 코드 목록/data 필드 상세** — 참조구현(`udp_test`)에서 실제 cmd 이름 다수
  확인됐으나(§7 하단, `udp_test_findings.md`), RC→UGV 방향 명령이 통째로 없고 값도 대부분
  더미라 신뢰도 낮음 — 진짜 최종본 대기.
- **device 코드(RC=20/UGV=14/UGV_RCWS=13/UGV_ADU=12) 실사용 여부** — 참조구현에서 `src`/
  `recv`가 전부 리터럴 `"device"`라 확인 안 됨.
- **참조구현의 IP(192.168.0.84)/포트(7777/7778 단일쌍)가 개발용 임시값인지**.
- **UGV축 RTSP 정확한 URL/포트**(우리가 정해서 통보 예정, LIG는 임의 URL 접속 가능 여부만
  확인).
- **자체방호축 PC의 고정 IP 여부**(상위체계행 RTSP 서버 주소용).

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
