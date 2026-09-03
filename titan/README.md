# Titan (KADEX 전시회 시뮬레이터) — 프로젝트 개요

카덱스(KADEX) 전시회 제출용 언리얼 엔진 기반 시나리오 씬 제작 프로젝트. 실제 코드는
`C:\working\works\kadex\titan_example`(UE5.8, Perforce 관리, git 아님). 이 문서는 **진입점**
— 프로젝트를 처음 보는 사람/세션이 뭘 어디서 찾아야 하는지만 안내하고, 상세 내용은 각 문서로
넘긴다.

**[2026-08-31] 문서 폴더를 시스템별로 전면 재편했다** — 예전엔 "작업 시작한 순서대로"
폴더 이름이 대충 붙어있었고(`newlevel/`, `structure/` 등), `structure/`는 유일하게 다른
폴더들과 다른 축(시스템별이 아니라 "인프라 관련은 다 여기")으로 되어있었음. 지금은 모든
devlog 폴더가 "시스템 하나당 폴더 하나" 축으로 통일됨(아래 표 참고). 옛 폴더 구조를 기억하고
있다면: `path/`→`vehicle/ugv/`, `drone/`→`vehicle/drone/`, `soldiers/`→`ai_combat/`,
`newlevel/`→`level_new_kadex_0811/`, `hit_effects/`→`sfx_vfx/`, `structure/`는 사라지고
`protocol/`/`rtsp/`/`replication/`/`rc_mockup_tools/`/`infra_architecture/`/`ui/`/
`camera_pipeline/`/`rcws/`로 분산됨.

## 뭘 찾고 있나요?

| 궁금한 것 | 볼 문서 |
|---|---|
| **지금 뭐가 어디까지 되어있나** (시스템별 현재 상태) | **`CURRENT_STATE.md`** |
| **문서를 찾고 있다** (전체 문서 카탈로그, 폴더별/날짜별) | **`DOCS_INDEX.md`** |
| **전체 작업이 어떤 순서로 진행됐나** (프로젝트 역사, 타임라인) | **`WORKLOG.md`** |
| **이 시스템이 지금 어떻게 동작하는가** (RCWS/QuadCam/조이스틱/탐지 등 레퍼런스) | **`guide/`** (⚠️ 내용 최신화 진행 중 — 각 문서 상단 경고 배너 확인) |
| **새 문서를 쓸 때 규칙** (파일명/헤더 형식) | **`CLAUDE.md`** |

### 개발 로그(devlog) 폴더 — 시스템별

| 시스템 | 폴더 |
|---|---|
| UGV 주행/자율주행/물리 | `vehicle/ugv/` |
| 드론(UAV) 비행 물리 | `vehicle/drone/` |
| RCWS(포탑 조준/발사) | `rcws/` |
| 카메라 파이프라인(SceneCapture/QuadCam 아키텍처) | `camera_pipeline/` |
| 적/아군 AI·애니메이션·전투 | `ai_combat/` |
| 신규 레벨(New_kadex_0811) 디자인/시나리오 | `level_new_kadex_0811/` |
| 사운드/파티클/환경 이펙트(피격 VFX·SFX, 바람 등) | `sfx_vfx/` |
| UI/대시보드 위젯(WBP) 개발 | `ui/` |
| LIG 원격통제기 UDP/JSON 프로토콜 | `protocol/` |
| RTSP 영상 송출 | `rtsp/` |
| 멀티플레이(리슨서버) 리플리케이션 | `replication/` |
| RC 목업/테스트 클라이언트 도구 | `rc_mockup_tools/` |
| 전체 아키텍처/인프라 결정 기록 | `infra_architecture/` |
| Genesis 물리엔진 병행 실험(일시중단) | `genesis/` |
| 더 이상 최신 아님, 보관용 | `_archive/` |
| LIG 원본 자료(PDF/PPTX/xlsx), Q&A 원문 | `documents/` |

`memo.md`는 사용자 개인 작업 백로그(수정하지 말 것). 전체 요구사항 원문은 `all.md` 참고.

---

## 1. 시뮬레이터 구성 — 무엇을 조작하는가

**듀얼 모니터** 세팅(`titan_exampleViewportClient`가 2개 이상 모니터 감지 시 보더리스 창으로
가상 데스크톱 전체를 덮음). 각 모니터에 별도 대시보드 UI(WBP) 표시 — 현재 실사용 위젯은
`SelfDefenseMonitor1Widget`/`SelfDefenseMonitor2Widget`/`AxisSelectionWidget`/Settings 위젯류/
`UGVTestDashboardWidget`/ConfirmDialog/Noti류(2026-08-31 확인, `guide/ui_dev_guide.md`가 다루는
구 `Monitor1Widget`은 레거시 — 현재 위젯들의 개발 기록은 `ui/kadex_test_dashboard_wbp_spec.md`).

**왼쪽 모니터(자체방호축)** — Titan Palantir 이동형 지휘소(트럭) + RCWS + UAV
- `TitanTruck`: 이동 기능은 미구현, 4방향 감시 카메라(CCTV) + 자체방호용 RCWS 장착(탄약 600발).
- `UAV`(드론, `ADronePawn`): 2026-08-27부로 로터별 추력→강체운동 정통 물리로 재구현되고,
  2026-09-01에 구 `BP_UAV`를 대체 완료(`vehicle/drone/drone_flight_dev_guide.md`) — 수동 조종,
  스플라인 경로 자율비행, 짐벌 카메라+자동 정찰, 프로펠러 사운드, 바람 반응, 단계별 탐지,
  시나리오 연동, RTSP 송출까지. **드론의 낙하산 관측이 UGV 출발 트리거**다. 리플리케이션은
  자체방호축 클라이언트 권위(`replication/2026-09-01_drone_client_authoritative.md`).

**오른쪽 모니터(UGV축)** — UGV(무인 전차): 대기/원격(수동)/자동주행 3모드, 목적지 수신 시
자동 경로 주행(NavMesh 기반, `vehicle/ugv/` 최신 문서 참고). 4방향 CCTV + RCWS 장착(탄약
1200발).

**RCWS**(무인 공격 포탑, `URCWSComponent` — TitanTruck과 UGV가 공유): 자동 적 감지/교전,
피아식별 bounding box, IR 모드, 장전/사격 상태 전환. 조이스틱으로 pan/tilt/zoom 조작. LIG
원격통제기 프로토콜로도 원격 조작됨(`protocol/protocol_icd.md` §3). 개발 기록은 `rcws/`.

## 2. 코드 구조 핵심 포인트

- `Source/titan_example/Vehicles/` — `TitanTruck`, `UAVPawn`, `RCWSComponent`,
  `RCWSFireControlComponent`, `AUGVAIController` 등 차량/무기 로직. 실사용 UGV는
  `BP_UGV_Vehicle`(순수 블루프린트, `AWheeledVehiclePawn` 직계) — `UGVPawn`/
  `UUGVMovementComponent`는 레거시(에셋 정리 트랙 대상 후보).
- `Source/titan_example/UI/` — 대시보드 C++ 베이스 클래스들, `Detection/` 하위
  `TargetDetectionComponent`(피아식별 UV 투영 계산).
- `Source/titan_example/titan_examplePlayerController.h/.cpp` — 조이스틱 입력, 카메라 컨트롤
  타겟 전환, 대시보드 위젯 스폰.
- `Plugins/QuadCamModule/` — 4방향 CCTV 카메라 재사용 플러그인(`UQuadCamComponent`).
  `SceneCaptureViewParity.{h,cpp}`(2026-08-31 신규)는 RCWS/카메라 셰이크 정합성 관련
  (`camera_pipeline/`, `rcws/` 참고).
- `Plugins/RtspEncoder/` — NVENC+GStreamer RTSP 송출 플러그인(완료, `rtsp/` 폴더).
- **카메라 아키텍처 공통 패턴**: 디자이너는 `UCineCameraComponent`만 배치, 코드가 `BeginPlay`에서
  실제 `USceneCaptureComponent2D`를 자동 생성(RCWS/QuadCam/UAV 전부 동일). CineCamera 자체는
  움직이지 않는 순수 렌즈 참조용 — 상세 배경은 `guide/`와 `camera_pipeline/
  rtsp_postprocess_parity_0820.md`(SceneCapture와 메인 뷰포트가 실제로 다른 카메라라는 것) 참고.

---

## 알려진 미해결 이슈 / 다음 작업 예정

`CURRENT_STATE.md` §11/§12에서 관리 — 중복 방지를 위해 여기서는 반복하지 않음.
