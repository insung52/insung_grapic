# 구조 개편 현황 스냅샷 (2026-08-13, 갱신)

`replication_audit.md`가 최신화돼서 다시 반영. 이전 버전(당일 앞서 작성)보다 리플리케이션
진행도가 훨씬 앞서 있었음 — **2026-08-11에 이미 실기(2-PC 성격) 테스트로 버그 3개를 찾아
고친 기록이 있음.** 세부는 `replication_audit.md` §8을 우선 신뢰할 것, 이 문서는 스냅샷.

---

## 한눈에

| 영역 | 상태 |
|---|---|
| RTSP 송출(트랙1) | **완료** |
| 리플리케이션 — 기반 플러밍 | **완료** (possess 제거, IsLocalController 네트워크모드 분기, Axis 선택, GameState 도입) |
| 리플리케이션 — RCWS | **완료** (투사체 판정 서버 권위화까지 8/13 마무리) |
| 리플리케이션 — 시나리오 | **완료** (GameState phase sync, Exec→Server RPC) |
| 리플리케이션 — 아군/적군 전투(고위험 항목) | **완료 + 실기 테스트 통과** (8/11, 버그 3개 발견·수정) |
| 리플리케이션 — UGV/차량 | **미착수** |
| 리플리케이션 — UAV | **미착수** |
| UGV축 LIG 프로토콜(트랙5) | **미착수** |
| 자체방호축 단일화(트랙5 범위) | **미착수** |
| LIG 참조구현(`udp_test`) 검토 | **완료** |
| LIG 추가 문의 | **초안 완료, 발송 대기** |
| 좌표계(WGS84 vs UTM) | **미확정** — LIG 답변 대기, 이중 지원 설계로 헤지 |
| NATS | **폐기 결정**, UDP로 전면 통일 |

---

## 1. RTSP — 완료

(변경 없음) UE NVENC(zero-copy)+GStreamer `gst-rtsp-server` 구현 완료, `rtsp_viewer_test/`로
5스트림 검증 완료.

## 2. 리플리케이션 — 대부분 완료, 실기 테스트까지 통과

`replication_audit.md` §8 기준. **8/6 감사 → 구현 → 8/11 2-PC성 실기 테스트 → 8/13 RCWS
투사체 판정 마무리**까지 진행됨.

### 완료된 것
- **기반 플러밍**: `ATitanTruck::BeginPlay`의 하드코딩 possess 제거, `AUGVAIController::
  IsLocalController()`를 `NM_Standalone`(항상 true)/그 외(`HasAuthority()` 기준)로 네트워크
  모드 분기, GameMode 접속 옵션(`?Axis=UGV`/`?Axis=SelfDefense`) 기반 축 판별(`AxisSelectionWidget`
  경유), 커스텀 `Atitan_exampleGameState` 도입.
- **RCWS**: 상태(`CurrentMode`/탄약/줌/마운트 회전 등) `Replicated`+`OnRep`, 조작 트리거 전부
  `Server_*` RPC화, 서버 전용 시뮬레이션과 로컬 UI 계산 분리. **투사체 판정(8/13 확정)**:
  히트스캔 전환도, 투사체 액터 리플리케이션도 둘 다 기각하고 — 궤적은 각 프로세스가 결정론적
  로컬 재생, **명중 판정만 서버가 확정해서 위치 기반 `Multicast_PlayImpactEffect`로 이펙트/
  사운드/데미지를 전파**하는 방식으로 확정(풀 인덱스 동기화 불필요, 패킷 드롭에도 누적
  어긋남 없음 — 기존 발사 트리거 멀티캐스트보다 견고). RCWS/아군/적군 라이플 공통 적용.
  - pan/tilt 클라이언트 예측은 보류 상태 유지하되, **정확성 문제가 아니라 순수 체감지연
    문제라는 것 확인됨**(발사 방향은 서버가 자기 시점 각도로 한 번만 계산해서 뿌리므로
    클라이언트-서버 각도 divergence로 인한 발사 오차 시나리오 자체가 없음).
- **시나리오**: `GameState`에 거친 단계(`EScenarioPhase`) 동기화, 트리거 Exec 커맨드 전부
  `Server_*` RPC화.
- **아군/적군 전투 컴포넌트(가장 회귀 위험 크다던 항목) — 구현+재빌드+실기 테스트 전부 완료.**
  `AllyFormationComponent`/`EnemyCombatComponent` Tick 서버 전용화 + Blueprint 자세/애니메이션
  변수(`IsProne`/`AimPitch`/`BurstShotsRemaining` 등) 리플리케이트. **8/11 실기 테스트로 발견해서
  고친 것**:
  1. 아군 `CurrentEnemy`/`HasTarget`가 클라이언트에서 계속 안 잡히던 문제 — 원인은 C++
     컴포넌트가 아니라 **캐릭터 블루프린트 자체**의 오버랩 감지/`EventTick`이 게이팅 없이 로컬
     실행되던 것(Q7이 우려했던 바로 그 사각지대). `Switch Has Authority`로 서버 전용화해서
     해결 — 단 `CurrentEnemy` 오브젝트 레퍼런스 자체의 근본 원인은 미확정으로 남고 우회
     완료(`IsValid(CurrentEnemy)` 게이트 제거).
  2. 적군 낙하산이 클라이언트에서 안 사라지던 문제 — `IsParachuting`을 `RepNotify`로 전환해서
     해결.
  3. (이전 발견) 발사 트리거를 `NetMulticast`로 감싸서 총알/이펙트/사운드 클라이언트 반영.
  - **교훈 기록됨**: "C++ 컴포넌트만 감사해선 못 보는 Blueprint 전용 로직이 있을 수 있다"는
    전제로 접근할 것 — 앞으로 캐릭터 블루프린트 수정 시 유의.
- **테스트 인프라**: `kadex_test`(단독 빠른 테스트용, `BP_KadexTestGameMode`, 축선택 화면
  없이 바로 UGV/호스트 진입) / `kadex_lobby`(실제 Host/Client 선택 화면 필요한 진입점,
  `BP_TestGameMode`) 레벨 분리 완료. 아군1 vs 적군1 최소 교전 세팅도 구성됨.

### 아직 안 된 것
- **UGV/차량**: `AUGVAIController`의 매틱 로직(`UpdateChaosPursuit` 등) `HasAuthority()` 게이팅,
  `DriveMode`/기어 리플리케이트, `physicsReplicationMode`(`Default`→적절한 값) 검토,
  `SetManualControl` 블루프린트 구현 확인 — **전부 미착수**(UGV PC가 항상 서버라 당장 체감
  버그는 없지만 설계상 구멍).
- **UAV**: 리플리케이션 편입 자체가 미착수.
- Q3(엔진 소스 레벨 근본원인) — 네트워크 모드 분기로 우회는 됐지만 근본 원인 미확인 상태로
  남음(치명적이지 않음).

## 3. UGV축 LIG 프로토콜 / 자체방호축 통합 — 미착수 (트랙5)

(변경 없음) 리플리케이션 핵심부가 거의 끝나가므로 이제 슬슬 착수 가능한 시점에 가까워짐 —
남은 리플리케이션 항목(UGV/차량, UAV)은 트랙5랑 병행해도 큰 무리 없어 보임(서로 다른 서브
시스템).

## 4. LIG 커뮤니케이션 — 진행 중 (변경 없음)

`udp_test_findings.md`, `lig_questions_0807_draft.md` 그대로 유효, 발송 대기.

## 5. 인프라/전송계층 — 결정 완료 (변경 없음)

NATS 폐기, UDP 통일.

---

## 다음 단계 제안 (갱신)

1. **UGV/차량 리플리케이션** 마저 진행(§2 "아직 안 된 것") — 남은 리플리케이션 작업 중
   유일하게 손 안 댄 영역.
2. **UAV 리플리케이션 편입**.
3. 위 둘 다 상대적으로 작은 범위라, **트랙5(UGV축 LIG 프로토콜 + 자체방호축 통합) 착수를
   같이 저울질해도 될 시점** — 서로 다른 서브시스템이라 병행 가능성 있음.
4. LIG 질문 발송 — 계속 병행 가능, 여전히 미발송.
