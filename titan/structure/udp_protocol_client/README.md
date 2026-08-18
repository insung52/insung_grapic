> **2026-08-15 갱신**: 아래 `protocol.py`/`client.py`/`mock_server.py`/`run_demo.py`/
> `tests/`는 정식 ICD(`lig_icd_ugv_rc_full.md`) 확보 **이전**(2026-08-07)에 우리 추정 cmd로
> 짠 것이라 지금은 obsolete — cmd 이름도 실제와 다르고 애초에 "UGV 역할" 목업이라 방향도 반대
> (지금 필요한 건 titan_example 프로젝트가 UGV를 구현했으니 그 반대인 "RC 역할" 목업). 정식
> ICD 기준 실제 테스트는 **`rc_mock_client.py`**(독립 파일, 아래 나머지와 무관) 사용 —
> `titan_example`의 `Network/UGVRemoteControlSubsystem.*`(UE, C++) 구현체를 상대로 실제 cmd
> 이름/필드로 왕복 확인. 이 파일들은 "Postman 대신 자체 스크립트로 UDP 테스트"라는 방법론
> 자체는 여전히 유효해서 참고용으로만 남겨둠.

# udp_protocol_client — UGV축 UDP+JSON 프로토콜 클라이언트 + 목업 서버

**범위**: 순수 Python/네트워크 서브태스크. 언리얼/UE 작업 없음, 이 컴퓨터에 `titan_example`
UE 프로젝트도 없음. 목적은 LIG가 2026-08-06 확정한 UGV축 UDP+JSON 프로토콜(전송/봉투/IP·포트/
ACK+재시도 메커니즘)을 실제로 구현·검증하는 것 — Postman류 HTTP 도구로는 raw UDP를 테스트할
수 없다는 문제의식(`architecture_decisions.md` §8, `protocol_icd.md` §6·§8)에서 나온 작업.

참고만 하고 수정하지 않은 문서: `../protocol_icd.md` §3, `../architecture_decisions.md` §2·§8.

## 파일 구성

| 파일 | 역할 |
|---|---|
| `protocol.py` | 봉투(Envelope) 포맷, device 코드, IP/포트 상수, cmd 레지스트리(우리 추정치) |
| `client.py` | `UDPProtocolClient` — Request/Response·Message/ACK 재시도 로직 캡슐화 |
| `mock_server.py` | `MockUGVServer` — 로컬 목업 UGV(127.0.0.1), 패킷 유실 시뮬레이션 훅 포함 |
| `run_demo.py` | 실제 UGV 포트 스킴(8000/8001)으로 목업을 띄우고 정상/비정상 6가지 시나리오를 눈으로 보여주는 수동 데모 |
| `tests/test_roundtrip.py` | `unittest` 자동 테스트 6건 (정상 3 + 유실/재시도 3) |
| `test_results.txt` | 테스트 실행 로그 (전부 OK) |
| `demo_output.txt` | `run_demo.py` 실행 로그 (와이어 바이트열 포함) |

의존성: 표준 라이브러리만 사용(`socket`, `json`, `threading`, `dataclasses`, `unittest`). 외부
패키지 설치 불필요. Python 3.10+ (타입힌트에 `tuple[...]`, `dict[...]` PEP 585 문법 사용,
이 환경은 3.14.6에서 확인).

## 실행 방법

```powershell
cd C:\working\insung_grapic\titan\structure\udp_protocol_client

# 자동 테스트 (6건, 콘솔 한글 깨짐 방지 위해 UTF-8 IO 강제)
$env:PYTHONUTF8=1; python -m unittest discover -s tests -v

# 수동 데모 (실제 UGV 포트 스킴 8000/8001을 127.0.0.1에 재현, 정상+비정상 6가지 시나리오)
python run_demo.py

# 목업 서버만 단독 기동(다른 프로세스에서 직접 두들겨보고 싶을 때)
python mock_server.py
```

`UDPProtocolClient`를 실제 하드웨어에 붙일 때는 주소만 바꾸면 된다:

```python
from client import UDPProtocolClient, RetryConfig
from protocol import DeviceCode, UGV_IP, UGV_PERIODIC_PORT, UGV_EVENT_PORT, RC_PERIODIC_PORT, RC_EVENT_PORT

client = UDPProtocolClient(
    my_device=DeviceCode.RC,
    local_periodic_addr=("0.0.0.0", RC_PERIODIC_PORT),   # 원격통제기 쪽 로컬 바인딩
    local_event_addr=("0.0.0.0", RC_EVENT_PORT),
    remote_periodic_addr=(UGV_IP, UGV_PERIODIC_PORT),      # 실제 UGV
    remote_event_addr=(UGV_IP, UGV_EVENT_PORT),
    retry_config=RetryConfig(),  # 기본값 = 아래 표
)

data = client.request("PeriodBasicInfo", recv_device=int(DeviceCode.UGV), data={})
client.send_event("ManualFire", recv_device=int(DeviceCode.UGV_RCWS), data={})
```

## 재시도 파라미터 — 뭘 정했는지 (원본 스펙 빈칸 채운 값)

`protocol_icd.md` §3.1 / `architecture_decisions.md` §2 원문: 주기성 메시지는 "( )회까지"
재시도, 이벤트 메시지는 "( )msec" 내 ACK 없으면 **3회까지**(이 숫자만 원본에 명시) 재시도.

| 파라미터 | 값 | 근거 |
|---|---|---|
| 주기성(Request/Response) 재시도 횟수 | **3회** (최초 1 + 재시도 3 = 총 4회 전송) | 원본 빈칸. 태스크 지시문이 제시한 예시값("예: 3회")을 그대로 채택 — 이벤트 메시지 쪽과 대칭을 맞춰서 두 메커니즘의 재시도 횟수를 통일 |
| 주기성 응답 대기 타임아웃 | **500ms**(운영 기본값, `RetryConfig.periodic_timeout_sec`) | 원본에 값 자체가 없음(빈칸으로 지목된 건 횟수뿐). 주기 메시지 특성상(상태 폴링) 초 단위 미만이면 충분하다고 보고 500ms로 설정. 테스트에서는 속도를 위해 150ms 사용 |
| 이벤트(Message/ACK) 재시도 횟수 | **3회**(최초 1 + 재시도 3 = 총 4회 전송) | 원본에 이미 명시된 값 — 우리가 정한 게 아님, 그대로 구현 |
| 이벤트 ACK 대기 타임아웃 | **300ms**(`RetryConfig.event_timeout_sec`) | 원본 빈칸. 태스크 지시문이 제시한 권장 범위(200~500ms) 중간값 채택 |

모두 `client.py`의 `RetryConfig` 데이터클래스 필드이고, `UDPProtocolClient(...).retry_config=`나
`request()`/`send_event()` 호출 시 `timeout=`/`max_retries=` 키워드로 콜 단위 override도 가능.
**LIG가 실제 수치를 알려주면 `RetryConfig`의 기본값 4개만 바꾸면 전체 시스템에 반영된다.**

"최초 전송 포함 총 몇 회냐"는 원본 문구가 "N회까지 재시도"(재시도 횟수를 말함)로 통일되게
해석했다 — 즉 `max_retries=3`이면 **최초 1회 + 재시도 3회 = 최대 4회 전송**. 테스트/데모
로그에도 `attempt=X/4` 형태로 이 해석이 그대로 드러난다.

## 봉투/매칭 로직에서 우리가 추가로 가정한 것 (LIG 원본에 없는 부분)

LIG가 확정한 건 봉투 포맷 `{cmd, src, recv, data}` / device 코드 / IP·포트 / "Request→Response",
"Message→ACK" 두 가지 흐름이 있다는 것까지다. **봉투 안에 상관관계 필드(seq/request-id 같은 것)가
없어서**, 어떤 응답이 어떤 요청에 대한 것인지 매칭할 방법을 우리가 정해야 했다:

- **Response 매칭 규칙(우리 추정, `protocol.py: Envelope.is_response_for`)**: Response는 Request와
  **동일한 `cmd` 문자열**을 `src`/`recv`만 뒤집어 돌려준다고 가정.
- **ACK 매칭 규칙(우리 추정, `Envelope.is_ack_for`)**: ACK는 `cmd="ACK"` + `data.ackCmd=<원본 cmd>`
  형태라고 가정(원본 cmd 값을 그대로 에코하는 필드가 있어야 이벤트 메시지 여러 종류를 구분 가능).
- **동시성 모델**: 이 클라이언트는 **한 번에 하나의 in-flight 요청만 지원하는 동기(blocking)
  모델**이다. 위 매칭 규칙이 cmd명 하나로만 상관관계를 잡기 때문에, 같은 cmd로 된 요청을
  동시에 여러 개 보내면 응답을 구분할 수 없다. UGV축 프로토콜이 실제로 이런 동시성을 요구하는지
  (예: 여러 `PeriodBasicInfo` 요청이 파이프라인될 수 있는지)는 LIG 원본 시퀀스도(`image.png`,
  우리는 미보유)로 확인 필요 — **다음 라운드에 LIG에 물어봐야 할 항목으로 플래그.**

이 두 매칭 규칙은 `protocol.py`의 `Envelope.is_response_for`/`is_ack_for`/`build_response`/
`build_ack` 네 곳에만 있고 `client.py`/`mock_server.py`는 이 인터페이스만 호출하므로, 실제 LIG
스펙이 다르게 오면 **이 네 함수만 교체하면 나머지 재시도/소켓/타임아웃 로직은 그대로 재사용
가능**하도록 분리해뒀다.

## 검증 결과 요약

- **자동 테스트 6건 전부 통과** (`tests/test_roundtrip.py`, 실행 로그 `test_results.txt`):
  1. 주기성 정상 왕복 — 재시도 0회로 즉시 성공
  2. 주기성 유실 2회 후 3번째 시도에서 성공 — `server.requests_received==3`으로 재시도가
     실제로 3번 전송됐음을 확인
  3. 주기성 완전 유실 — 최대 재시도(설정값 2) 소진 후 `ProtocolTimeoutError`, 서버 수신
     횟수(3회 = 최초1+재시도2)로 정확히 그만큼만 재전송했음을 확인
  4. 이벤트 정상 왕복 — ACK 즉시 수신
  5. 이벤트 유실 2회 후 3번째 시도에서 ACK 수신
  6. 이벤트 완전 유실 — 스펙 명시대로 3회 재시도(총 4회 전송) 후 `ProtocolTimeoutError`
- **수동 데모**(`run_demo.py`, 로그 `demo_output.txt`)로 실제 UGV 포트 스킴(8000/8001, RC는
  8010/8011)을 loopback에 재현해 같은 6가지 시나리오를 재확인. 와이어에 나가는 정확한 JSON
  바이트열도 출력해서 봉투 포맷을 육안 확인:
  ```
  [WIRE Request] 78 bytes -> '{"cmd": "PeriodBasicInfo", "src": 20, "recv": 14, "data": {"query": "status"}}'
  [WIRE Message] 56 bytes -> '{"cmd": "ManualFire", "src": 20, "recv": 13, "data": {}}'
  ```
  `src=20`(RC), `recv=14`(UGV)/`13`(UGV_RCWS) — device 코드가 스펙대로 정확히 나가는 것을 확인.

### Wireshark/실제 와이어 캡처 — 생략함 (선택 항목)

이 환경엔 Wireshark/tshark가 설치돼 있지 않고(`where tshark`/`where wireshark` 모두 실패),
Windows 내장 `pktmon.exe`는 있으나 loopback 캡처에 관리자 권한이 필요한데 이 세션엔 관리자
권한이 없다(`net session` 확인 결과 `NOT_ADMIN`). 태스크 지시문에 "안 되면 생략해도 됨"으로
명시돼 있어 생략. 대신 위처럼 `run_demo.py`가 **sendto() 직전 실제 바이트열을 그대로 로그에
출력**하도록 해서 대체 확인 수단으로 삼았다 — UDP는 페이로드가 프레임에 그대로 실리는
구조라 이 바이트열이 곧 와이어 페이로드와 동일하다. 나중에 관리자 권한이 있는 환경에서
`pktmon start --etw -c <필터> -p 0`이나 Npcap 설치 후 Wireshark로 재확인 가능.

## LIG 실제 cmd 코드 목록이 오면 뭘 바꿔야 하는지

1. **`protocol.py: CMD_REGISTRY`** — 지금은 `protocol_icd.md` §3.2의 추정 cmd 이름
   (`SetUGVMode`, `ManualDrive`, `PeriodBasicInfo` 등)을 그대로 옮겨놓은 것. LIG 참조 모듈
   도착 시 실제 cmd 값/방향(src→recv)/kind(periodic|event)로 전면 교체.
2. **`protocol.py: ACK_CMD`, `Envelope.is_ack_for`/`is_response_for`/`build_ack`/`build_response`**
   — 위 "우리가 추가로 가정한 것" 섹션 참고. LIG 시퀀스도가 실제로 Response/ACK를 어떤
   cmd 값·필드로 보내는지 확인되면 이 4곳만 고치면 된다(다른 파일은 안 건드려도 됨).
3. **`client.py: RetryConfig` 기본값 4개** — LIG가 재시도 횟수/타임아웃 정확한 수치를 알려주면
   여기만 갱신.
4. **`mock_server.py: _default_response_data`** — 지금은 요청 데이터를 그대로 echo하는
   더미 응답. 실제 `data` 필드 스키마(§2 "공통 타입" 참고 — 좌표 WGS84 lat/lon 등)가 확정되면
   cmd별로 그럴듯한 응답을 만들도록 확장하면 UGV 시뮬레이션 SW 개발 중에도 계속 유용하게
   쓸 수 있음.
5. **동시성 모델 재검토** — 위에서 플래그한 대로, LIG 원본이 여러 요청을 동시에 다루는
   시나리오를 요구하면(예: 여러 주기성 채널이 겹쳐서 온다거나) 지금의 "cmd명만으로 매칭하는
   1-in-flight 동기 모델"을 확장해야 함. seq/id 필드가 실제로 있는 게 확인되면 그걸 상관관계
   키로 쓰도록 `Envelope`/매칭 로직을 바꾸는 게 훨씬 견고함.

## 알려진 한계 (설계상 의도적으로 단순화한 부분)

- 소켓은 블로킹(synchronous) 모델 — asyncio 미사용. 테스트/디버그 클라이언트 용도로는
  충분하지만, UGV 시뮬레이션 SW 본체(언리얼 프로세스)에 이 로직을 이식할 때는 UE의
  게임스레드를 막지 않도록 별도 스레드/논블로킹 소켓으로 감싸는 작업이 필요함(이건 UE
  통합 작업이라 이 서브태스크 범위 밖).
- `mock_server.py`의 응답 데이터는 echo뿐이라 실제 UGV 상태값(배터리, 위치 등)을 흉내내진
  않음 — 프로토콜/재시도 메커니즘 검증이 목적이라 의도적으로 최소화.
