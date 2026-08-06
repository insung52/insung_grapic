# structure/ — 세션 분할 가이드

이 폴더(`system_architecture_design_spec.md`, `idea_review.md`, `architecture_decisions.md`,
`protocol_icd.md`)는 설계 문서고, 실제 구현은 다른 워크스페이스(`titan_example`, UE5.8,
Perforce)에서 일어남. 이 README는 **그 구현 작업을 여러 Claude 세션으로 어떻게 나눌지**의
계획표 — 새 세션을 열 때 아래에서 자기 트랙을 찾아 그 트랙의 "읽을 문서"만 들고 시작하면 됨,
다른 트랙 진행상황은 몰라도 됨(그러기 위해 `protocol_icd.md`를 계약서 수준으로 엄격하게 만든
것).

**공통 규칙**:
- 모든 트랙은 `architecture_decisions.md` + `protocol_icd.md`를 계약서로 삼는다 — 트랙끼리
  서로의 구현 디테일을 몰라도 이 두 문서만 지키면 나중에 맞물림.
- Perforce라 git worktree 격리가 없음. **자기 트랙 파일 스코프 바깥은 건드리지 않기** —
  특히 `.uasset`은 exclusive checkout이 흔해서 두 세션이 같은 파일을 건드리면 체크아웃 충돌.
- 새 세션 여는 프롬프트는 "프로젝트 계속해줘"가 아니라 **"트랙 N만, 이 문서 이 절만"**으로
  좁게 던질 것.

---

## 의존관계 한눈에

```
[즉시 시작 가능, 서로 완전 독립]
  1. RTSP PoC          2. NATS/JetStream 인프라      3. 상위체계 파이썬 스텁

[에뮬레이터 코드베이스 — titan_example]
  4. Layer C 리플리케이션  ──┐
  5. Layer B 서버측 핸들러  ──┴─ 같은 코드베이스, 순서 상관없음(4 먼저 권장 — 리플리케이션 토대 위에 5가 올라감)

[통제기SW 코드베이스 — 신규]
  6. 공통 플러그인 ──depends on──▶ 7. 축별 UI/조이스틱(UGV, 자체방호 — 6 완료 후 착수)
```

---

## 트랙 1 — RTSP PoC

- **범위**: UE NVENC(zero-copy) 인코딩 + GStreamer `gst-rtsp-server`(appsrc) 서빙 배관 검증.
  고정 텍스처 하나 스트리밍부터, 이후 5/7스트림 동시 성능 측정.
- **읽을 문서**: `protocol_icd.md` §7(구현 방식), §0(전송 계층)
- **의존성**: 없음. 다른 트랙 완성 전에도 독립 실행 가능.
- **완료 기준**: PoC 결과로 §7의 "PoC 1~2일/안정화 1~2주" 추정치 검증, RTSP URL 스킴(§6 미확정)
  확정.
- **시작 프롬프트 예시**: "`protocol_icd.md` §7 기준으로 UE NVENC → gst-rtsp-server RTSP 송출
  PoC만 진행해줘. 다른 트랙은 안 건드림."

## 트랙 2 — NATS/JetStream 인프라

- **범위**: NATS 서버 세팅, JetStream 활성화, `console.<axis>.*`/`hq.<cmd|rpt>.<axis>` subject
  구조 실제 구현.
- **읽을 문서**: `protocol_icd.md` §0(전송 계층), §1(봉투 포맷)
- **의존성**: 없음.
- **완료 기준**: 봉투 포맷(`cmd`/`seq`/`ts`/`payload`) 발행/구독 예제가 두 axis 다 동작.

## 트랙 3 — 상위체계 파이썬 테스트 스텁

- **범위**: 실물 상위체계(모비젠/LIG) 연동 전까지 대신 쓸 파이썬 프로그램. `HQ_*` 발행,
  `RPT_*` 수신, 시나리오 진행에 맞춰 순서대로 명령 하달.
- **읽을 문서**: `protocol_icd.md` §5(Layer A), `architecture_decisions.md` §3(시나리오 체인)
- **의존성**: 트랙 2(NATS 인프라)가 있으면 바로 테스트 가능하지만, 없어도 발행 로직 자체는
  먼저 짤 수 있음.
- **완료 기준**: #4-1~#4-8 시나리오 메시지 체인을 순서대로 실행하는 스크립트/CLI.
- **비고**: UE 지식 불필요 — 다른 인력 배정도 가능.

## 트랙 4 — 에뮬레이터: Layer C 리플리케이션

- **범위**: 리슨서버 세팅(UGV PC 기본 호스트, 런타임 선택), 45명 캐릭터 리플리케이션, RCWS
  히트스캔+Multicast, 아군 30명 UGV 종속 팔로워 로직, 차량모드/호스트-클라이언트 런타임 선택.
- **읽을 문서**: `architecture_decisions.md` §1(Layer C 전체)
- **감사 대상 코드** (§1.3): `RCWSComponent`/`RCWSFireControlComponent`,
  `UGVMovementComponent`/`UGVAIController`, `titan_examplePlayerController`, 아군/시나리오
  스폰 시스템.
- **의존성**: 없음(다른 트랙과 독립) — 단, 트랙 5가 이 위에 올라가므로 먼저 하는 게 자연스러움.
- **완료 기준**: UGV PC/자체방호 PC 두 인스턴스가 하나의 배틀필드를 공유(45명+RCWS+차량 동기화).

## 트랙 5 — 에뮬레이터: Layer B 서버측 핸들러

- **범위**: `titan_example`에 NATS 클라이언트를 붙여서 `RC_*` 수신 → 기존 함수 호출
  (`SetUGVMode`, `SetRCWSMode` 등), `TRK_*`/`*_Period_*` 발행.
- **읽을 문서**: `protocol_icd.md` §2~4(공통 타입, Layer B 양축), `architecture_decisions.md` §2
- **의존성**: 트랙 2(NATS 인프라) 필요, 트랙 4(리플리케이션)와 같은 코드베이스라 순서 조율
  필요(파일 스코프 겹칠 수 있음 — 같은 세션에서 4→5 순서로 진행하는 것도 방법).
- **완료 기준**: 트랙 3(파이썬 스텁) 또는 임시 NATS 클라이언트로 명령 보내면 에뮬레이터가
  반응, 텔레메트리가 10Hz로 발행됨.

## 트랙 6 — 통제기SW: 공통 플러그인

- **범위**: NATS 프로토콜 클라이언트, RTSP 수신(`UMediaPlayer`+`UMediaTexture`→WBP Image,
  안 되면 `finger563/unreal-rtsp-display` 등 대안), 공용 WBP 베이스 위젯.
- **읽을 문서**: `protocol_icd.md` 전체, `architecture_decisions.md` §1.4
- **의존성**: 트랙 1(RTSP PoC) 결과가 수신 경로 선택에 참고됨(직접 의존은 아님 — 병행 가능).
- **완료 기준**: 더미 NATS 메시지로 텔레메트리 위젯이 갱신되고, RTSP 테스트 스트림이 WBP에
  뜸.

## 트랙 7 — 통제기SW: 축별 UI/조이스틱 (UGV, 자체방호)

- **범위**: 조이스틱 하드웨어 바인딩(UGV=TRUSTMASTER T-1600M FCS, 자체방호=제닉스 타이탄
  GP5), 축별 UI 레이아웃, `protocol_icd.md` §3/§4의 축별 명령 발행.
- **읽을 문서**: `protocol_icd.md` §3(UGV) 또는 §4(자체방호) — **자기 축만**, 다른 축은 안 읽어도 됨.
- **의존성**: 트랙 6(공통 플러그인) 완료 필요.
- **완료 기준**: 조이스틱 입력이 `RC_*` 메시지로 나가고, 자기 축 텔레메트리가 UI에 표시.
- **비고**: UGV용/자체방호용은 서로 다른 세션으로 나눠도 됨(파일 스코프가 자연히 분리됨).

---

## 아직 이 표에 없는 것

- **UGV 통제기SW 외주 확인 결과에 따른 트랙 7 범위 조정** — 외주 확정되면 트랙 7-UGV는
  "우리 자체 테스트용 레퍼런스 구현"으로 축소되고, 실제 납품용은 그쪽 트랙(다른 회사 몫).
- 리플리케이션 감사(트랙 4) 세부 티켓화 — 지금은 뭉뚱그려져 있음, 착수 시 더 쪼갤 수 있음.
