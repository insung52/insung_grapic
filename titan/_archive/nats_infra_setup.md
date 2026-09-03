# NATS/JetStream 인프라 세팅 (트랙 2)

로컬 개발용 NATS/JetStream 백본 세팅 결과. 근거: `protocol_icd.md` §0(전송 계층), §1(공통
봉투 포맷), §5(Layer A subject). 이 문서는 인프라 구조와 검증 결과만 다룸 — 메시지
스키마/필드는 `protocol_icd.md`가 원본.

파일 위치: `C:\working\insung_grapic\titan\infra\nats\`

```
infra/nats/
  nats-server.conf     # JetStream 활성화 서버 설정
  start-nats.ps1        # 재사용 가능한 기동 스크립트
  setup-streams.js      # 스트림 생성(멱등 — 재실행 안전)
  test-pubsub.js         # pub/sub + 재연결 유실 없음 검증
  package.json           # nats.js(v2) 의존성
  data/                   # JetStream 파일 스토리지 (git-ignore 대상, 런타임 생성)
```

## 1. 서버 기동

```powershell
cd C:\working\insung_grapic\titan\infra\nats
.\start-nats.ps1
```

기본적으로 사용자 로컬 컴퓨터의 `C:\Users\user\Downloads\nats-server-v2.14.4-windows-amd64\...\nats-server.exe`
를 그대로 사용(재다운로드 안 함). 다른 컴퓨터에서 돌릴 땐 같은 버전(v2.14.4, windows-amd64)을
받아서 `-NatsServerPath`로 경로를 넘기면 됨.

`nats-server.conf` 핵심:
- client 포트 4222, 모니터링(HTTP) 포트 8222 (`http://localhost:8222`)
- `jetstream { store_dir: ".../infra/nats/data", max_file_store: 10GB }` — 파일 스토리지라
  서버 재기동해도 메시지 보존됨
- 인증 없음 — 로컬 개발 전용 의도적 결정. 배포 토폴로지 확정 후 별도로 잠글 것
  (`protocol_icd.md` §6, 이번 트랙 범위 밖)

## 2. Subject / 스트림 구조

`protocol_icd.md` §0/§5의 subject를 그대로 따름:

| 스트림 | subject | 대응 |
|---|---|---|
| `CONSOLE_UGV` | `console.ugv.>` | Layer B, UGV축 — `console.ugv.cmd`/`evt`/`telemetry` |
| `CONSOLE_SELFDEFENSE` | `console.selfdefense.>` | Layer B, 자체방호축 — `console.selfdefense.cmd`/`evt`/`telemetry` |
| `HQ_UGV` | `hq.cmd.ugv`, `hq.rpt.ugv` | Layer A, UGV축 — `HQ_*`/`RPT_*` |
| `HQ_SELFDEFENSE` | `hq.cmd.selfdefense`, `hq.rpt.selfdefense` | Layer A, 자체방호축 — `HQ_*`/`RPT_*` |

각 스트림 설정: `retention: limits`, `storage: file`, `max_age: 24h`, `max_msgs: 1,000,000`,
`discard: old`. `console.<axis>.cmd/evt/telemetry` 3종을 축 하나당 스트림 하나로 묶은 이유는
관리 단위를 "축(axis)"으로 맞추는 게 향후 축별 보존정책 조정(예: 자체방호축만 retention
늘리기)이나 장애 대응 시 더 직관적이기 때문. hq 쪽은 `cmd`/`rpt` 두 subject를 명시 나열(와일드
카드 대신) — Layer A는 subject 개수가 고정이라 명시가 더 안전.

생성/재생성:
```powershell
cd C:\working\insung_grapic\titan\infra\nats
node setup-streams.js
```
이미 있으면 update, 없으면 add — 여러 번 돌려도 안전.

## 3. 검증 결과

```powershell
node test-pubsub.js
```

**[1] core NATS 라이브 구독 — 통과**
살아있는 구독자에게 `console.ugv.telemetry`로 봉투 포맷(`{cmd, seq, ts, payload}`) 그대로
`UGV_Period_BasicInfo` 3건 발행 → 3건 모두 즉시 수신, `cmd`/`seq`(순서대로)/`ts`/`payload`
필드 전부 확인.

**[2] JetStream 재연결 캐치업 — 통과 (핵심 요구사항)**
1. `hq.rpt.ugv`에 대해 durable consumer(`test_hq_ugv_watcher`) 생성 후 구독자 연결 종료
2. 구독자가 없는 상태에서 `RPT_ContactDetected` 3건(seq 101/102/103) 발행
3. **같은 durable 이름**으로 재연결 → 끊긴 동안의 3건을 순서/내용 그대로 전부 수신 확인

→ 연결이 끊겼다 재연결해도 그 사이 메시지를 놓치지 않는다는 JetStream 핵심 동작 확인됨.
단, 이건 **durable consumer 이름을 재연결 시에도 동일하게 써야** 성립 — 클라이언트(UE
console/에뮬레이터) 구현 시 구독자마다 고정된 durable 이름을 쓰도록 해야 함 (예:
`console-sw-ugv`, `hq-relay-selfdefense` 등). durable 이름 없이 매번 새로 구독하면 JetStream
스트림 자체엔 메시지가 남아있어도 "어디까지 읽었는지"를 잃어버려 캐치업이 안 됨.

또한 core `nc.publish()`(JetStream API를 거치지 않는 일반 발행)로 보낸 메시지도 subject가
스트림에 매칭되면 자동으로 스트림에 캡처됨을 확인함(모니터링 엔드포인트로 메시지 수 확인) —
즉 발행 측(UE 등)은 JetStream을 의식하지 않고 그냥 `nats.publish(subject, envelope)`만 하면
되고, 영속성/재전송은 구독 측이 durable consumer를 쓰느냐에 달려 있음.

검증 후 테스트로 생성된 메시지는 4개 스트림 모두 purge해서 정리함 — 서버는 현재 스트림
구조만 있고 메시지는 비어있는 상태.

## 4. 다음 트랙에서 참고할 점

- **발행측(console SW / 에뮬레이터 양쪽)**: subject만 맞춰 일반 publish. 봉투 포맷은
  `protocol_icd.md` §1 그대로.
- **구독측**: 유실 없는 수신이 필요하면(Layer A 보고, 텔레메트리 등 놓치면 안 되는 것) durable
  pull/push consumer + 고정 durable 이름 사용. 단순 실시간 표시용(예: 조이스틱 echo)이면 core
  구독으로 충분 — 스트림엔 어차피 다 남아있으니 필요할 때 durable consumer로 다시 붙어도 됨.
- **인증**: 지금 서버는 무인증. 배포 토폴로지(상위체계/통제기SW/에뮬레이터가 물리적으로 어떻게
  나뉘는지) 확정되면 `nats-server.conf`에 계정/자격증명 추가 필요 — 이번 트랙에서 결정하지
  않음.
