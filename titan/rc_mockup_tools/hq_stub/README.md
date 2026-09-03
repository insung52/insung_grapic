# hq_stub — 상위체계 테스트용 파이썬 스텁

`protocol_icd.md` §5(Layer A)와 `architecture_decisions.md` §3(시나리오 단계별 메시지 체인)에
정의된 **상위체계 ↔ 통제기SW** 인터페이스를, 실물 상위체계(모비젠/LIG 영역, 우리가 안 만듦)가
붙기 전까지 대신 흉내내는 순수 파이썬 스텁이다. 실물 상위체계가 연결되면 이 스텁은
버리고 교체하면 된다(신호 소스 교체 원칙, `architecture_decisions.md` §4-3).

이 스텁은 **상위체계 역할**을 맡는다:
- `hq.cmd.<axis>` 에 `HQ_*` 명령을 발행(하달)
- `hq.rpt.<axis>` 를 구독해 `RPT_*` 보고를 수신·로그

`<axis>` = `ugv` | `selfdefense`.

## 설치

```
pip install -r requirements.txt
```

(nats-py 하나만 필요.)

## 실행

`rc_mockup_tools/` 디렉터리에서:

```
python -m hq_stub --mode manual
python -m hq_stub --mode auto
```

옵션:

| 옵션 | 기본값 | 설명 |
|---|---|---|
| `--nats-url` | `nats://127.0.0.1:4222` | NATS 서버 주소 |
| `--mode` | `manual` | `manual`=엔터/커맨드로 단계별 수동 트리거, `auto`=자동 재생 |
| `--jetstream` | 꺼짐 | JetStream 경유 발행/구독. **주의**: 스트림은 이 스텁이 만들지 않음(인프라 소관) — `hq.cmd.<axis>`/`hq.rpt.<axis>`를 커버하는 스트림(예: `HQ_UGV`, `HQ_SELFDEFENSE`)이 서버에 이미 있어야 함. 없으면 core NATS(기본값)로 충분 |
| `--no-auto-approve` | (미지정=자동승인) | `auto` 모드에서 #4-6 교전승인을 자동으로 거부하고 싶을 때 |

NATS 서버는 트랙 2(다른 세션)가 세팅 중인 걸 그대로 쓰면 된다. 없다면 아무 로컬
`nats-server`(선택적으로 `-js`)를 띄우고 `--nats-url`로 가리키면 됨 — 메시지
스키마/subject는 그대로라 나중에 실제 서버로 바꿔도 코드 변경 없음.

## 모드

### manual (기본)

각 단계 앞에서 사람이 하는 발화("적 침투 감지됨", "UGV 교전 위치로 이동 명령" 등)를
콘솔에 띄우고, 엔터를 누르면 그 시점에 해당 `HQ_*`를 발행한다. `q`를 입력하면 그
자리에서 시나리오를 중단한다. `RPT_*`는 이 모드와 무관하게 도착 즉시 항상 로그된다.

`#4-6` 교전승인만은 예/아니오를 직접 묻는다(`Y/n`, 기본 예 — 미승인/승인 둘 다
테스트 가능).

### auto

같은 순서를 사람 개입 없이 자동 재생한다. 각 단계 사이 1.5초 대기. `#4-6` 교전승인은
`--no-auto-approve`를 안 주면 자동 승인.

## 시나리오 체인 (protocol_icd.md §5 / architecture_decisions.md §3)

```
#4-1 상위체계 → 자체방호SW : HQ_EnemyContactReport{contactId, coord}
#4-2~3 (에뮬레이터/SW 내부 처리)
       자체방호SW → 상위체계 : RPT_TargetsIdentified{targets}      (FYI)
#4-4 상위체계 → UGV SW      : HQ_MissionMoveToEngage{target, radius}
#4-5 UGV SW → 상위체계      : RPT_ObjectiveReached{radius}          (FYI)
#4-6 UGV SW → 상위체계      : RPT_ContactDetected{targets}
     상위체계 → UGV SW      : HQ_EngagementAuthorization{approved, contactId}  ← 승인 게이트
#4-7 UGV SW → 상위체계      : RPT_EngagementInitiated{}             (FYI)
     UGV SW → 상위체계      : RPT_EngagementResult{kia, fleeing}
#4-8 상위체계 → 자체방호SW  : HQ_MissionEngageFleeing{coord}
     자체방호SW → 상위체계  : RPT_ScenarioComplete{result}
```

좌표(`coord`)는 전부 위경도 WGS84 `{lat, lon, alt}` (`protocol_icd.md` §2). 테스트용
더미 좌표/반경 값은 `scenario.py` 상단 상수(`ENEMY_COORD`, `ENGAGE_TARGET`,
`ENGAGE_RADIUS`, `FLEEING_COORD`, `CONTACT_ID`)에 있고, 필요하면 그 자리에서 바로 수정.

## 파일 구성

| 파일 | 내용 |
|---|---|
| `envelope.py` | 공통 봉투 `{cmd, seq, ts, payload}` 빌더 (`protocol_icd.md` §1) |
| `messages.py` | Layer A 메시지 이름/payload 빌더 (`protocol_icd.md` §2, §5) |
| `nats_client.py` | `hq.cmd.<axis>`/`hq.rpt.<axis>` 발행/구독 래퍼 |
| `logger.py` | 타임스탬프 + 축 + cmd + payload 콘솔 로그 |
| `scenario.py` | 시나리오 체인 드라이버 (auto/manual 공용) + `ReportBus`(수신 로그·대기) |
| `main.py` / `__main__.py` | CLI 진입점 (`python -m hq_stub`) |

## 확인된 사항 (2026-08-06 검증)

- 로컬 NATS(core 모드, `--jetstream` 없이)로 전체 체인(#4-1~#4-8) 왕복 확인함 — 상대편
  SW를 흉내내는 임시 스크립트로 각 `HQ_*`에 대응하는 `RPT_*`를 순서대로 응답시켜 검증.
- `--jetstream` 모드도 확인함. 단, JetStream 스트림(`HQ_UGV`/`HQ_SELFDEFENSE` 등)은 이
  스텁이 만들지 않으므로 인프라 쪽에 이미 있어야 동작함. 첫 연결 시 durable
  consumer(`hq-stub-ugv`/`hq-stub-selfdefense`)가 스트림에 남아있는 과거 메시지부터
  재생하는 게 JetStream의 정상 동작(재연결 시 놓친 것부터 재생, `architecture_decisions.md`
  §3)이니 당황하지 말 것 — 다른 테스트가 쌓아둔 이력이 있으면 첫 실행에 몰려서 나올 수 있음.
- Windows 콘솔 기본 코드페이지(cp949)에서 한글/특수기호 출력 시 `UnicodeEncodeError`가
  나서 `main.py`에서 stdout/stderr를 UTF-8로 강제 재설정하도록 처리함. 한글이 깨져
  보이면 터미널에서 `chcp 65001` 실행 권장.
