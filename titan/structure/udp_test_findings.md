# udp_test 참조구현 조사 결과 — LIG UGV축 UDP+JSON 프로토콜 실제 스펙

`C:\working\works\kadex\udp_test` (UE5.8, LIG가 보내준 "UGV 시뮬레이션 SW ↔ 원격통제기" 참조
구현)를 unreal-mcp(Epic 실험적 Unreal MCP, `EditorToolset`/`ToolsetRegistry` 플러그인 활성화 후)로
블루프린트를 직접 읽어서 조사한 결과. **에셋/블루프린트는 전혀 수정하지 않음(읽기 전용 MCP
tool만 사용: `read_graph_dsl`, `find_nodes`, `get_node_infos`, `list_*`, `get_properties` 등).**

C++(`UdpComponent.h/.cpp`)은 범용 UDP+JSON 유틸이라는 기존 파악이 맞았고, 실제 프로토콜 로직은
전부 `BP_UdpTest` 블루프린트 안에 있었다.

---

## 0. 총평 — 이 참조구현의 성격

**이건 "완성된 프로토콜 구현체"가 아니라 "송신 측 데모/스텁"이다.** 구체적으로:

- **수신 처리가 사실상 없다.** `OnUdpJsonMessage` 이벤트(Ex_recv)는 들어온 `Cmd`/`DataJson`을
  화면·로그에 `PrintString`으로 찍기만 한다. cmd별 분기(Switch on String)도, JSON 파싱도,
  RC_RemoteDriving 같은 제어 명령 처리도 **전혀 없음**.
- **RC→UGV 방향 명령(모드 전환/수동주행/웨이포인트/RCWS 조준/발사 등)이 이 블루프린트
  어디에도 없다.** 8개 `send_UGV_*` 함수는 전부 UGV→RC 방향(주기 상태 통지 + 3개 수동
  응답)뿐이다.
- 죽은 코드 2건(`sendJson`, `sendObj` 함수, `Ex_send` composite)이 있음 — 어디서도 호출되지
  않는 실험/스크래치 코드.
- 전송되는 데이터 값 대부분이 하드코딩된 상수(`Speed=15`, `Batterry=80`,
  `StatusVMU="OFF"` 등) — 실제 시뮬레이션 상태를 반영하지 않는 더미값.
- 액터에 배치된 `UdpComponent`의 실제 IP/Port는 우리가 추정한 `192.168.10.x` 스킴과
  전혀 다르다(§5).

**결론: 이 참조구현은 "cmd 이름 목록 + JSON data 필드 구조 + 봉투 포맷"을 확인하는 용도로는
매우 유용하지만, "요청↔응답 상관관계 처리 방식"이나 "RC_RemoteDriving 실제 로직"은 이
프로젝트에 없다 — 확인 불가가 아니라 애초에 구현되어 있지 않음.**

---

## 1. 봉투(Envelope) 포맷 — 확인됨

`UdpComponent`의 `bParseJsonMessages` 프로퍼티 설명(엔진 툴팁 원문)에 봉투 스키마가 명시돼
있음:

> If true, every incoming UTF-8 message is also tested against the `{ "cmd", "src", "recv",
> "data" }` JSON shape. On a match, `OnUdpJsonMessage` fires in addition to `OnUdpMessage`.

→ `protocol_icd.md` §1(a)의 `{cmd, src, recv, data}` 추정이 **정확히 맞음.**

다만 실제 `src`/`recv` 값은 8개 `send_UGV_*` 함수 전부에서 **리터럴 문자열 `"device"`
(양쪽 다 동일)** 를 사용한다 — `RC`(20)/`UGV`(14)/`UGV_RCWS`(13)/`UGV_ADU`(12) 같은 우리
추정 device 코드는 이 블루프린트 어디에도 없다. §6 질문 목록 참고.

### 봉투 조립 방식 (sendJson/sendObj — 죽은 코드, 참고용)

`sendJson(AltitudeIn)`, `sendObj(input_int)` 둘 다 아무 데서도 호출되지 않는 미사용 함수.
`UDP|Json|MakeEmptyJsonObject` → `AddJsonIntField`/`AddJsonStringField` 체이닝으로 JSON
오브젝트를 만들고 `UDP|Json|SendJsonMessageRaw(Udp, cmd, src, recv, JsonObject)` 로 전송하는
패턴 자체는 실제 8개 함수와 동일 — 헬퍼 함수 실험 흔적으로 보임. cmd값은 `"Comand Code"`(오타),
src/recv는 `"unreal"`/`"device"`로 역시 플레이스홀더.

---

## 2. 실제 cmd 목록

### 2.1 주기(Periodic) — `EventBeginPlay`의 `SetTimerByFunctionName`/`SetTimerByEvent`로 자동 실행

| cmd (실제 문자열) | 방향 | 주기 | data 필드 |
|---|---|---|---|
| `UGV_Period_Basicinfo` | UGV→RC(추정) | **0.1초 반복** | `OperationMode`(string,"Stay"), `ConrtrolRight`(string,"Remote" — 오타, ControlRight 의도로 추정), `Speed`(int,15), `Gear`(string,"Front"), `Batterry`(int,80 — 오타, Battery 의도로 추정) |
| `UGV_RCWS_Status` | UGV_RCWS→RC(추정) | **0.2초 반복** | `RCWSStatus`(string,"OFF") |
| `UGV_Period_BasicInformation` | UGV→RC(추정) | **1회만**(looping=false로 세팅됨 — 반복 아님) | `Odometer`(int,9999) |
| `UGV_Period_NavigationInformation` | UGV_ADU→RC(추정) | **0.2초 반복** | `East`(int), `North`(int), `Zone`(int), `Letter`(string), `Velocity`(int), `Heading`(int), `Altitude`(int) — **UTM류 좌표계**(§4 참고) |
| `SEND_UGV_PERIOD_OBJECTDETECTIONRESULT`(전체 대문자 — 다른 cmd와 표기 불일치) | UGV_ADU→RC(추정) | **0.2초 반복**(커스텀 이벤트 `OnObjectDetectionTimer`를 `SetTimerByEvent`로 트리거) | `TotalObject`(int), `Objects`(array, §3 구조체 참고) |

**주의**: `UGV_Period_Basicinfo`와 `UGV_Period_BasicInformation`은 이름이 비슷하지만 **서로
다른 cmd 문자열, 다른 data 필드를 가진 완전히 별개의 두 함수**다(오타나 중복이 아님) — 문서화
시 절대 하나로 합치지 말 것. 다만 왜 기본정보가 두 cmd로 쪼개져 있는지, 하나는 왜 반복이 아닌
1회성인지는 블루프린트만으로는 알 수 없음(§6 질문).

### 2.2 비주기 — `WBP_SendButton`의 버튼 클릭으로만 수동 트리거됨 (자동 트리거 없음)

| cmd (실제 문자열) | 방향 | 트리거 | data 필드 |
|---|---|---|---|
| `UGV_Response_Connection` | UGV→RC(추정) | Button_94 클릭 | `ResponseDevicer`(string,"1" — 오타, ResponseDevice 의도로 추정) |
| `UGV_Response_BIT` | UGV→RC(추정) | Button 클릭 | `StatusVMU`(string,"OFF"), `CountValue`(string,"9999" — 타입이 string임에 주의, int 아님) |
| `UGV_Response_BIT_ADU` | UGV_ADU→RC(추정) | Button_1 클릭 | `StatusADU`, `StatusVMU`, `StatusNavigation`, `Status3DLidar`, `StatusRadar`, `StatusOCS` (전부 string, 값 "OFF") |

이름에 "Response"가 들어있어 Request/Response 패턴의 응답측으로 보이지만, **이 참조구현
안에서는 어떤 요청에 대한 응답으로 자동 발동하지 않는다** — 순전히 사람이 버튼을 눌러야
나간다. 즉 "이게 실제로 무엇에 대한 응답인지"는 이 코드만으로는 알 수 없음(§6 질문).

### 2.3 죽은 코드 — 실제로 전송되지 않음 (참고용으로만 기록)

- `sendJson`, `sendObj` 함수 — 아무 이벤트에서도 호출 안 됨.
- `EventGraph` 안의 `Ex_send` composite 노드 — `UDP|Json|SendJsonMessage(Udp, Cmd, Src, Recv,
  Data:Map<String,String>)` 호출부(East/North/Zone/Letter/Velocity/Heading/Altitude 조립)가
  있으나 **진입 exec 핀에 아무 연결도 없어 절대 실행되지 않는 고아 노드**. 참고로 이 함수는
  `SendJsonMessageRaw`(JsonObject 인자)가 아니라 `SendJsonMessage`(문자열 맵 인자)라는 별도
  오버로드를 씀 — C++에 두 가지 전송 경로가 존재한다는 뜻일 수 있음.

### 2.4 수신 측 — 처리 로직 없음

`Ex_recv` composite = `UdpComponent.OnUdpJsonMessage(Cmd, Src, Recv, DataJson, Sender)`
바인딩 이벤트. 내용은:
```
Sequence:
  분기0: PrintString(Cmd)       // 화면/로그에 cmd 이름만 출력
  분기1: PrintString(DataJson)  // 화면/로그에 raw JSON 문자열 출력
```
`Src`/`Recv`/`Sender` 핀은 아예 연결 안 됨(미사용). **cmd 문자열 기반 분기(Switch on
String) 자체가 없다** — 즉 이 블루프린트는 무엇을 받든 그냥 로그만 찍고 아무 것도 안 한다.

---

## 3. `S_DetectedObject` 구조체 필드 (확정 — `BreakSDetectedObject`/`MakeSDetectedObject` 노드 pin에서 직접 확인)

| 필드명 | 타입 |
|---|---|
| `ObjectID` | Integer |
| `ObjectClass` | String |
| `LeftTopX` | Integer |
| `LeftTopY` | Integer |
| `RightBottomX` | Integer |
| `RightBottomY` | Integer |
| `East` | Integer |
| `North` | Integer |
| `Zone` | Integer |
| `Letter` | String |
| `Velocity` | Integer |
| `Altitude` | Integer |

**BBox가 우리 추정(`{x,y,w,h}` 0~1 정규화 UV)과 다름** — 실제로는 `LeftTopX/Y`,
`RightBottomX/Y` 정수 좌표쌍(픽셀 또는 절대 좌표로 추정, 어느 쪽인지 블루프린트만으론
불명 — §6 질문). 또한 객체별로 `East/North/Zone/Letter`(위치)와 `Velocity`/`Altitude`까지
포함 — 우리 `Detection`/`Coord` 타입에 없던 필드.

`Ex_objects` composite(EventBeginPlay에서 `CurrentDetectedObjects`의 초기값으로 대입)는
`MakeSDetectedObject` 2개로 구성된 **하드코딩 더미 배열**: `ObjectClass="Human"` 1개,
`ObjectClass="Car"` 1개, 나머지 필드 전부 임의 상수(9999, 65535 등 — 테스트용 명백).
실제 객체탐지 결과가 아니라 데모용 고정 데이터.

---

## 4. 좌표계 — WGS84 위경도 아님, UTM류

`protocol_icd.md` §2에서 "좌표는 위경도(WGS84)로 확정"이라 명시했지만, 이 참조구현에서
발견된 좌표 필드(`UGV_Period_NavigationInformation`의 data, `S_DetectedObject`의 East/North,
그리고 죽은 코드 sendJson/sendObj까지 전부)는 예외 없이 **`East`(int) / `North`(int) /
`Zone`(int) / `Letter`(string)** 4필드 조합 — 이건 **UTM(Universal Transverse Mercator)
좌표계의 Easting/Northing/Zone Number/Zone Letter** 표기와 정확히 일치하는 패턴이다.
`Altitude`는 별도 int 필드로 항상 같이 붙어 다님.

**이건 확정된 사실(필드명 패턴)이지 추측이 아니다** — 다만 이게 정말 UTM인지, 단위가
무엇인지(미터? cm?), 어느 UTM Zone/Datum을 쓰는지는 블루프린트만으로는 알 수 없음(§6 질문).
어느 쪽이든 §2의 "좌표는 WGS84 lat/lon" 결론과 **정면으로 배치**되므로 최우선 재확인 필요.

---

## 5. `BP_UdpTest` 액터의 `UdpComponent` 실제 설정값 (레벨 `/Game/NewMap`에 배치된 인스턴스에서 직접 조회)

| 프로퍼티 | 실제값 | `protocol_icd.md` §3.1 추정 |
|---|---|---|
| `ListenIp` | `0.0.0.0` | (명시 안 됨) |
| `ListenPort` | `7777` | UGV 기준 `8000`(주기)/`8001`(비주기) |
| `RemoteIp` | `192.168.0.84` | RC 기준 `192.168.10.20` |
| `RemotePort` | `7778` | RC 기준 `8010`(주기)/`8011`(비주기) |
| `bAutoStart` | `true` | — |
| `bParseJsonMessages` | `true` | — |
| `PollIntervalMs` | `100` | — |

**완전히 다름.** `7777`/`7778`은 C++ 기본값 그대로이고, `192.168.0.84`는 우리가 가정한
`192.168.10.x` 대역과 무관한 IP(개발자 로컬 PC로 추정) — 이 인스턴스는 "LIG가 실제 배포
환경에 맞춰 설정해 놓은 값"이 아니라 **개발/테스트용 임시 설정**으로 보인다. 또한 포트가
단일 쌍(7777/7778)뿐이라 "주기 포트/비주기 포트 분리(8000/8001)" 개념 자체가 이 인스턴스
설정에는 반영돼 있지 않음(코드상 분리 불가능하다는 뜻은 아니고, 이 컴포넌트 인스턴스가
그렇게 안 쓰고 있다는 뜻).

---

## 6. 질문 목록 (블루프린트만으로 확정 불가 — LIG에 재확인 필요)

1. **RC→UGV 방향 제어 명령(모드 전환/수동주행/웨이포인트/RCWS 조준/발사 등)이 이 참조구현에
   전혀 없다.** LIG가 별도로 보낼 예정인지, 아니면 이 프로젝트 범위 밖(원격통제기 측 구현)인지
   확인 필요.
2. **요청↔응답 상관관계**: `Ex_recv`가 cmd를 로그만 찍고 아무 처리도 안 하므로, "어떤 응답이
   어떤 요청에 대한 것인지" 매칭하는 메커니즘을 이 참조구현에서 전혀 확인할 수 없었다.
   seq/request-id 필드가 봉투에 없다는 우리 쪽 발견(`protocol_icd.md` §6)이 그대로 유효 —
   이 참조구현도 답을 주지 못함.
3. **`UGV_Response_Connection`/`UGV_Response_BIT`/`UGV_Response_BIT_ADU`가 실제로 무엇에
   대한 응답인지.** 이름상 "연결 확인"/"BIT(자체진단) 확인" 요청에 대한 응답으로 추정되나,
   그 요청 cmd 자체가 이 프로젝트 어디에도 없음(수신 로직이 없으므로).
4. **`src`/`recv` 값이 전부 리터럴 문자열 `"device"`인 이유.** 우리가 가정한 device 코드
   (`RC=20`/`UGV=14`/`UGV_RCWS=13`/`UGV_ADU=12`)가 실제로 쓰이는지, 아니면 이 문자열 자체가
   실제 스펙인지, 이 참조구현이 단순히 값을 채워 넣지 않은 테스트 스텁인지 불명확.
5. **좌표계가 WGS84 lat/lon이 아니라 UTM류(East/North/Zone/Letter)로 보이는 것**(§4) — 확정
   재확인 필요. 단위(m? cm?), Zone/Datum 기준도 불명.
6. **`LeftTopX/Y`, `RightBottomX/Y`가 픽셀 좌표인지 정규화 좌표인지, 어느 영상 스트림(§3.3
   RTSP 5채널 중 어디) 기준인지.**
7. **`UGV_Period_Basicinfo`(0.1초 반복)와 `UGV_Period_BasicInformation`(1회성)이 왜 별도
   cmd로 나뉘어 있는지, 의도된 설계인지 구현 실수인지.**
8. **`CountValue`(BIT 응답), `ResponseDevicer`(연결 응답) 필드가 왜 int가 아니라 string
   타입인지** — 오타/설계 실수인지 의도적인지.
9. **`UdpComponent`의 실제 설정값(§5: 7777/7778, 192.168.0.84)이 개발용 임시값인지, 아니면
   LIG가 실제로 이 포트 스킴을 쓰는지** — `protocol_icd.md` §3.1의 `192.168.10.x:8000번대`
   가정과 완전히 다르므로 반드시 확인.
10. **ACK/재시도 로직**(주기 메시지 미응답 시 재시도, 이벤트 메시지 3회 재시도) — 이
    참조구현 어디에도 타임아웃/재시도 카운터 로직이 없음. `protocol_icd.md` §3.1에 적힌
    메커니즘은 이 코드가 아니라 LIG 원본 시퀀스도에서 나온 것이므로 그대로 유효하나, 이
    참조구현이 그걸 구현 예시로 보여주지는 않는다는 점은 기록해 둠.

---

## 7. `protocol_icd.md` §3.2 대조표

| 우리 추정 cmd | 실제 대응(있으면) | 판정 |
|---|---|---|
| `SetUGVMode` | 없음 | **불일치 — 실제구현에 RC→UGV 제어 cmd 자체가 없음** |
| `ManualDrive` | 없음(RC_RemoteDriving 포함 어떤 조향/가속 로직도 발견 안 됨) | **불일치** |
| `MissionWaypoint` | 없음 | **불일치** |
| `SetRCWSMode` | 없음 | **불일치** |
| `Movement`(pan/tilt) | 없음 | **불일치** |
| `ManualFire` | 없음 | **불일치** |
| `PeriodBasicInfo` | `UGV_Period_Basicinfo` **+** `UGV_Period_BasicInformation`(2개로 분리, 필드도 다름) | **이름·구조 둘 다 불일치, 실제로는 두 cmd로 쪼개짐** |
| `PeriodObjectDetectionResult` | `SEND_UGV_PERIOD_OBJECTDETECTIONRESULT`(표기 스타일도 다름 — 전체 대문자) | **이름 불일치, data 구조도 완전히 다름**(§3) |
| `PeriodNavigationInfo` | `UGV_Period_NavigationInformation` | **이름 유사하나 정확히는 다름, data 구조는 좌표계부터 완전히 다름**(§4) |
| `PeriodRCWSStatus` | `UGV_RCWS_Status`(필드가 mode/aimPan/aimTilt/loaded/fireReady/zoom이 아니라 단일 `RCWSStatus` 문자열) | **이름 유사, data 구조 완전히 다름 — 훨씬 단순** |
| (표에 없던 것) | `UGV_Response_Connection`, `UGV_Response_BIT`, `UGV_Response_BIT_ADU` | **우리 표에 없던 새 cmd 3개 — 비주기, 수동 트리거만 확인됨** |
| device 코드(RC=20/UGV=14/UGV_RCWS=13/UGV_ADU=12) | 미확인(`src`/`recv`가 전부 리터럴 `"device"`) | **실제 사용 확인 안 됨** |
| IP/Port(UGV 192.168.10.10:8000/8001, RC 192.168.10.20:8010/8011) | 배치 인스턴스는 `0.0.0.0:7777` / `192.168.0.84:7778`(단일 포트쌍) | **불일치 — 개발용 임시값으로 추정, LIG 확인 필요** |
| 좌표: WGS84 lat/lon | 실제 필드는 East/North/Zone/Letter(UTM류) | **불일치** |
| BBox: `{x,y,w,h}` 0~1 UV | 실제는 `LeftTopX/Y`, `RightBottomX/Y` 정수 절대좌표 | **불일치** |
| ACK/재시도 메커니즘 | 이 참조구현엔 미구현(로직 없음) | 판정 보류 — 원본 시퀀스도 근거는 유지, 코드 예시는 없음 |
| seq/request-id 없음(우리 발견) | 그대로 확인됨(Ex_recv도 상관관계 처리 없음) | **일치(같은 갭이 실제구현에도 그대로 있음)** |

**총평: cmd 이름·데이터 구조 추정치는 거의 전부 틀렸다.** 특히 RC→UGV 제어 명령 6개가
통째로 실제구현에 없다는 것과, 좌표계가 WGS84가 아니라 UTM류라는 것이 가장 임팩트가 큰
두 가지 발견 — `protocol_icd.md` §2·§3 전면 개정이 필요해 보임(단, 이건 문서 작업자 판단
사항이라 이 조사 문서에서는 사실만 기록).
