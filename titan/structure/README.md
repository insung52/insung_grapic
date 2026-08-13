# structure/ — 세션 분할 가이드

이 폴더(`system_architecture_design_spec.md`, `idea_review.md`, `architecture_decisions.md`,
`protocol_icd.md`, **`lig_response_0806_review.md`(2026-08-06 LIG 답변 — 가장 최신, 아래
트랙 정의보다 우선함)**)는 설계 문서고, 실제 구현은 다른 워크스페이스(`titan_example`,
UE5.8, Perforce)에서 일어남. 이 README는 **그 구현 작업을 여러 Claude 세션으로 어떻게
나눌지**의 계획표 — 새 세션을 열 때 아래에서 자기 트랙을 찾아 그 트랙의 "읽을 문서"만 들고
시작하면 됨, 다른 트랙 진행상황은 몰라도 됨.

**2026-08-07 갱신**: LIG 답변으로 자체방호축이 단일 프로그램으로 바뀌고 UGV축 원격통제기가
LIG 제작으로 확정되면서 트랙 5~7이 상당히 바뀜(구 트랙 7 삭제, 트랙 6 범위 축소). 아래는
갱신된 버전.

**공통 규칙**:
- 모든 트랙은 `architecture_decisions.md` + `protocol_icd.md`를 계약서로 삼는다 — 트랙끼리
  서로의 구현 디테일을 몰라도 이 두 문서만 지키면 나중에 맞물림.
- Perforce라 git worktree 격리가 없음. **자기 트랙 파일 스코프 바깥은 건드리지 않기** —
  특히 `.uasset`은 exclusive checkout이 흔해서 두 세션이 같은 파일을 건드리면 체크아웃 충돌.
- 새 세션 여는 프롬프트는 "프로젝트 계속해줘"가 아니라 **"트랙 N만, 이 문서 이 절만"**으로
  좁게 던질 것.
- **로컬 테스트 서버 포트도 트랙마다 겹치지 않게 신경 쓸 것** (2026-08-07 실제로 충돌 발생 —
  트랙3의 로컬 RTSP 테스트 서버가 `protocol_icd.md` 잠정 포트 8554를 그대로 썼다가 트랙1의
  실제 UE RTSP PoC와 같은 컴퓨터/같은 포트에서 부딪힘, 8564로 옮겨서 해결). 로컬 개발용
  포트는 실제 배포 포트(§3.1 등)와 다르게 잡는 걸 권장.

---

## 의존관계 한눈에

```
[진행 상황 — 2026-08-07]
  1. RTSP PoC — 진행 중 (titan_example, 언리얼)
  2. UDP 프로토콜 클라이언트(구 NATS 인프라) — 완료 (udp_protocol_client/)
  3. RTSP 뷰어 테스트 클라이언트(구 상위체계 스텁) — 완료 (rtsp_viewer_test/)
  6. UGV축 최소 레퍼런스 클라이언트 — 완료 (2+3의 산출물이 곧 트랙6, 별도 작업 불필요)

[다음 — titan_example 코드베이스, UGV/자체방호 공용. 트랙1이 쓰는 동안은 착수 보류]
  4. Layer C 리플리케이션  ──┐
  5. UGV축 LIG 프로토콜(UDP+JSON) + 자체방호축 로컬 제어 통합  ──┴─ 같은 코드베이스, 4 먼저 권장
```

**삭제됨**: 구 트랙 7(축별 UI/조이스틱) — 자체방호축은 별도 콘솔이 없어져서 필요 없어짐
(트랙 5로 흡수), UGV축 프로덕션 콘솔은 LIG가 만들어서 우리 트랙이 아님(트랙 6으로 스코프
축소).

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

## 트랙 2 — NATS/JetStream 인프라 → UDP 프로토콜 클라이언트로 용도 변경, 완료

- **상태**: 원래 목적(NATS 인프라)은 폐기(2026-08-07, 팀장님 논의). 대신 UGV축 UDP 프로토콜
  클라이언트 구현으로 용도 변경해서 **완료** — `structure/udp_protocol_client/`
  (클라이언트+로컬 목업 UGV 서버+재시도 로직, 테스트 6건 전부 통과).
- **후속 확인 필요**: LIG 봉투 포맷에 요청↔응답 상관관계 필드(seq/request-id)가 없어서
  "cmd 문자열 매칭"으로 가정하고 구현함 — 동시 다중 요청 처리가 필요한지 LIG에 재확인
  필요(`protocol_icd.md` §6).

## 트랙 3 — 상위체계 파이썬 테스트 스텁 → RTSP 뷰어 테스트 클라이언트로 용도 변경, 완료

- **원래 산출물**(`hq_stub/`, NATS 기반)은 전송계층 UDP 통일 결정으로 보류 — Layer A 확정되면
  그때 UDP+JSON으로 다시 짤 것.
- **용도 변경 후 완료**: UGV축 RTSP 뷰어 테스트 클라이언트 — `structure/rtsp_viewer_test/`
  (Python/OpenCV, 로컬 mediamtx+GStreamer 테스트 서버로 5스트림 전부 검증 완료, 실제 서버는
  URL만 바꾸면 됨).

## 트랙 4 — 에뮬레이터: Layer C 리플리케이션

- **범위**: 리슨서버 세팅(UGV PC 기본 호스트, 런타임 선택), 45명 캐릭터 리플리케이션, RCWS
  히트스캔+Multicast, 아군 30명 UGV 종속 팔로워 로직, 차량모드/호스트-클라이언트 런타임 선택.
- **읽을 문서**: `architecture_decisions.md` §1(Layer C 전체)
- **감사 대상 코드** (§1.3, 2026-08-06 감사 기준 — **아래 신규 코드는 그 이후 추가돼 감사에
  안 잡혀 있음, Track4 착수 시 같이 검토 필요**): `RCWSComponent`/`RCWSFireControlComponent`,
  `UGVMovementComponent`/`UGVAIController`, `titan_examplePlayerController`, 아군/시나리오
  스폰 시스템.
- **신규(2026-08-09~12, 감사 대상에 추가 필요)**: `AllyFormationComponent`(자세 상태머신
  `EAllyCombatPoseState`, 버스트 사격 `BurstShotsRemaining`, 조준 보정, `GaitTopSpeed`/
  `SmoothedMaxWalkSpeed` 등)와 신규 `EnemyCombatComponent`(Move/Combat/Flee 상태머신) —
  전부 로컬 전용 상태로 새로 추가됨(`soldiers/ally_ai_combat_system_status.md`,
  `soldiers/enemy_ai_combat_system_status.md` 참고). 감사 시점(8/6) 이후 생긴 코드라 아직
  리플리케이션 관점 검토가 안 됨.
- **의존성**: 없음(다른 트랙과 독립) — 단, 트랙 5가 이 위에 올라가므로 먼저 하는 게 자연스러움.
- **완료 기준**: UGV PC/자체방호 PC 두 인스턴스가 하나의 배틀필드를 공유(45명+RCWS+차량 동기화,
  신규 전투 상태머신 포함).

## 트랙 5 — UGV축 LIG 프로토콜 구현 + 자체방호축 로컬 제어 통합 (2026-08-07 전면 개정)

**UGV축**: `titan_example`(UGV 모드)에 원격통제기(LIG)와의 UDP+JSON 인터페이스를 구현.
NATS 아님 — LIG가 이미 그렇게 만들어놨음.
- **범위**: UDP 소켓(포트 8000/8001, 로컬 IP 192.168.10.10), `{cmd,src,recv,data}` 봉투
  파싱/생성, 주기 메시지(Request/Response)·이벤트 메시지(Message/ACK) 재시도 로직,
  `protocol_icd.md` §3.2 명령을 기존 함수(`SetUGVMode` 등)에 매핑.
- **읽을 문서**: `protocol_icd.md` §3(UGV축, 전면 개정판), `architecture_decisions.md` §2

**자체방호축**: 조이스틱 입력을 시뮬레이션(같은 프로세스) 컴포넌트에 직접 연결 — 네트워크
계층 없음, 그냥 로컬 함수 호출 배선.
- **범위**: 조이스틱(제닉스 타이탄 GP5 등) → UAV 짐벌/RCWS 조준·발사 컴포넌트 직결, RTSP
  서버로 CCTV/RCWS 영상 송출.
- **읽을 문서**: `protocol_icd.md` §4, `architecture_decisions.md` §1.5

- **의존성**: 트랙 4(리플리케이션)와 같은 코드베이스라 순서 조율 필요(4 먼저 권장). UGV축은
  트랙 2(NATS) 불필요.
- **완료 기준**: UGV축 — 트랙 6(테스트 클라이언트) 또는 LIG 원격통제기 실물로 명령 보내면
  반응, 텔레메트리가 주기 발행됨. 자체방호축 — 조이스틱으로 UAV/RCWS 직접 조작 가능, RTSP로
  영상 확인됨.

## 트랙 6 — UGV축 최소 테스트 클라이언트 (완료 — 트랙2/3이 나눠서 처리함)

**프로덕션 원격통제기는 LIG가 만듦 — 이건 우리 자체 검증용 도구일 뿐.** UDP 절반은 트랙2가
(`udp_protocol_client/`), RTSP 절반은 트랙3이(`rtsp_viewer_test/`) 완료 — 아래는 원래 계획
기록용, 새로 작업 안 해도 됨.

- **범위**: RTSP 수신 뷰어(영상 5종이 잘 오는지) + UDP/JSON 기본 왕복 테스트(명령 보내면
  응답/텔레메트리 오는지) 정도. 조이스틱 하드웨어 통합, 정식 UI 불필요.
  - **UDP 테스트는 Postman으로 안 됨** — 자체 Python 스크립트(`socket` 모듈, LIG의
    Request/Response·Message/ACK 재시도 시퀀스까지 구현)가 핵심 산출물. 트랙3
    `hq_stub/`과 비슷한 패턴이지만 NATS 대신 raw UDP로. 보조로 Packet Sender(빠른 수동
    테스트), Wireshark(와이어 레벨 검증, `192.168.10.10` 필터)도 활용.
- **읽을 문서**: `protocol_icd.md` §3, §8(테스트 도구), `architecture_decisions.md` §8
- **의존성**: 트랙 1(RTSP PoC), 트랙 5(UGV축 LIG 프로토콜) 결과를 검증 대상으로 씀 —
  병행 개발은 가능(둘 다 미완성이어도 목업으로 시작 가능).
- **완료 기준**: RTSP 스트림 5종 화면에 뜸, UDP/JSON 명령 보내고 응답 받는 것 확인됨,
  재시도/ACK 시퀀스도 의도적으로 패킷 드롭시켜서 검증됨.

---

## 아직 이 표에 없는 것

- LIG가 예고한 "cmd 코드 목록/데이터 송수신 참조 모듈" 도착 시 트랙 5/6 문서 재확인 필요.
- UGV축↔자체방호축 리플리케이션 링크 존재 여부 LIG 재확인 결과에 따라 트랙 4 범위가 바뀔 수
  있음(`lig_response_0806_review.md` §1-③).
- 리플리케이션 감사(트랙 4) 세부 티켓화 — 지금은 뭉뚱그려져 있음, 착수 시 더 쪼갤 수 있음.
