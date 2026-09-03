# 문서 전체 목록 (DOCS_INDEX)

2026-08-31 / 진행중 / titan 폴더 전체 .md 문서 카탈로그, 2026-08-31 시스템별 폴더 재편
반영판.

폴더는 "시스템 하나당 폴더 하나" 축으로 통일됨(`CLAUDE.md` 참고). `guide/`는 에버그린
레퍼런스, 나머지는 전부 devlog(시간순 기록, 안 고침). 날짜는 문서 내용 기준, 없으면
파일명/mtime 기준 — `2026-07-24 전후` 표기는 옛 `C:\private\titan`에서 일괄 이관된
타임스탬프라 실제 작성일이 아닐 수 있음.

이 문서는 목록만 다룬다 — 현재 상태 요약은 `CURRENT_STATE.md`, 전체 시간순 서사는
`WORKLOG.md`, 문서 작성 규칙은 `CLAUDE.md` 참고.

---

## 최상위 (`titan/`)

- `README.md` — 진입점.
- `memo.md` — 사용자 개인 백로그(수정 금지).
- `all.md` — Phase #4 시나리오 공식 명세 원문, 지금도 근거 문서로 유효.
- `content_asset_inventory.md` (2026-07-29) — 디자인팀 제공 Content 폴더 전수 조사.
- `ally_animation_request.md` (2026-08-07) — 디자인팀 아군 애니메이션 요청서, 현재 최신본.
- `ally_move.md` (2026-08-07) — 아군 Posture×Alert×Movement FSM 설계, §10만 구버전.

## `guide/` — 에버그린 레퍼런스 (⚠️ 내용은 대부분 옛날 것, 상단 경고 배너 확인)

- `ui_dev_guide.md` (2026-07-10) — Monitor1/2 UI. `Monitor1Widget` 자체가 레거시로 확인됨,
  현재 위젯 개발기록은 `ui/kadex_test_dashboard_wbp_spec.md`.
- `quadcam_usage_guide.md` (2026-06-24) — QuadCamModule 사용법.
- `titan_dev_status.md` (2026-06-25) — QuadCamModule 내부 아키텍처+VRAM 버그 수정.
  `quadcam_usage_guide.md`와 병합 검토 대상.
- `rcws_fire_control_dev_guide.md` (2026-07-12~14) — RCWS 조준/발사 메커니즘. 최신은
  `protocol/ugv_rc_feature_gap_analysis.md`/`protocol/selfdefense_rc_feature_gap_analysis.md`.
- `pixelstreaming_setup_guide.md` (2026-07-06) — Pixel Streaming. RTSP로 방향 잡힌 뒤
  실사용 여부 불명.
- `real2world.md` (원날짜 불명) — 픽셀↔위경도↔월드좌표 변환. UTM 확정과 대조 필요.
- `joystick_camera_control_dev_guide.md` (2026-07-08) — 조이스틱 RCWS/UAV 조작. 최신
  버튼맵은 `protocol/selfdefense_rc_feature_gap_analysis.md` §3.
- `detection_dev_guide.md` (2026-07-09) — 객체 탐지(BBox) 모사.
- `mcp/unreal-mcp-claude-code.md`, `mcp/additional-mcp-integrations.md` (원날짜 불명) —
  unreal-mcp/Claude Code 연동 설정.

## `vehicle/ugv/` — UGV 주행/자율주행/물리

- `2026-08-26_ugv_obstacle_avoidance.md` (2026-08-27 확정) — 장애물 회피 4대 원인 규명·해결,
  실측 34.6km/h·조향포화 0회. **완료.**
- `2026-08-26_ugv_track_lock_implementation_plan.md` (2026-08-26) — "공중에 뜬 바퀴" 버그 근본원인 3단
  규명·해결. **완료, 실기 확인.**
- `2026-08-22_ugv_corner_braking_dev_guide.md` (2026-08-22/25) — 커브 선행 감속(제동 곡선). **완료.**
- `2026-08-27_new_kadex_0811_navmesh_autonomous_driving.md` (2026-08-27, 최신판) — 신규 레벨
  내비메시 3층 구조 구축(A* 노드 예산/부분경로 버그 절 포함). **2026-08-31 재확인**: 이전엔
  `level_new_kadex_0811/`에도 08-22 시점 구버전 사본이 남아있었는데(내용이 완전히 이 문서의
  부분집합이라 고유 정보 없음 확인됨), 중복 제거하고 이 파일 하나로 통합함 — 레벨
  스플라인/PCG 구성값도 여기 담겨 있으니 레벨 작업 중이어도 이 경로에서 찾을 것.

## `vehicle/drone/`

- `drone_flight_dev_guide.md` (최종 2026-09-01) — **드론 시스템 에버그린 레퍼런스.** 로터별
  추력→강체운동 물리, 자율비행(Pure Pursuit+제동곡선), 짐벌, 프로펠러 사운드, 바람, 단계별
  탐지, 시나리오 연동, 클라이언트 권위 리플리케이션까지 전부. `guide/`에 드론 문서가 없어서
  이 파일이 그 역할을 겸한다 — **드론 동작이 바뀌면 여기를 같이 고칠 것.**
- `2026-09-01_drone_replaces_bp_uav.md` — 구 `BP_UAV` 갭 분석과 대체 작업 경과, 겪은 함정 6건
  (짐벌 본 공간, 자율주행 10km/h 고정, 커브 감속 무효, 바람 과잉상쇄, 트리거 불일치, 유니티
  빌드 상수 재정의). **2프로세스 실환경 검증만 남음.**

## `rcws/` — RCWS 전용 devlog

- `2026-08-31_selfdefense_camera_shake_bugs.md` — 자체방호축 카메라 떨림 + UGV 발사 셰이크
  누출 버그 2건, 원인 확정+코드 수정 완료(`SceneCaptureViewParity`/`RCWSProjectile`).
  **2-PC 실환경 검증 대기.**
- `rcws_preview_actor_asset_ref_todo.md` (2026-08-11) — `RCWSPreviewActor` 하드코딩 에셋
  경로 정리 방법. **아직 미착수 TODO.**

## `camera_pipeline/` — SceneCapture/QuadCam 아키텍처

- `rtsp_postprocess_parity_0820.md` (2026-08-20) — RTSP 스트림에 SSR/피격흔들림 안 나오던
  원인 규명(RCWS 메인뷰 카메라와 RTSP용 SceneCapture가 실제로 다른 카메라, 엔진이
  SceneCapture에 `ReflectionMethod=None` 강제). `SceneCaptureViewParity` 모듈 도입 —
  `rcws/2026-08-31_selfdefense_camera_shake_bugs.md`의 선행 문서.

## `ai_combat/` — 적/아군 AI·애니메이션·전투

- `2026-09-01_enemy_spin_on_hit_investigation.md` (2026-09-01) — 살아있는 적이 이동 중 피격되면
  몸이 회전하는 현상 조사. 후보 2개(총구 Yaw 되먹임 / 소총 Pitch 무클램프 적분기)를 세워 진단
  로그로 실측했으나 **두 차례 모두 재현 실패 → 보류.** 증상 형태(이동 중에만 발생, 정지하면
  자연 복구)는 총구 Yaw 되먹임 가설과 일치하나 미확증. 재발 시 로그 되살려 재개.
- `2026-09-01_animation_asset_inventory.md` (2026-09-01) — **디자인팀 공유용**. 아군/적군이 실제로
  재생 중인 애니메이션 시퀀스 전체 목록(블렌드스페이스 3종·슬롯별 단발 동작·적군 전용)과,
  애니메이션 없이 코드로 구현한 동작들(기울임/조준각/사주경계/피격 반응/사망 랙돌 등) 정리.
  미사용 추정 애셋 목록과 개발 확인 예정 항목 4건 포함.
- `2026-08-31_enemy_squad_reorg.md` (2026-08-31) — 적 15명 3분대 재편, 분대별 도주 경로/NavMesh
  필터, 경로 가중치 근본원인 수정. **PIE 재검증 대기.**
- `enemy_locomotion_animation_pipeline.md`/`enemy_hit_reaction_physics_system.md`/
  `enemy_scenario_combat_expansion.md` (2026-08-24~25) — 3단계 전투 확장(Part A~G 완료),
  피격 리액션 감쇠조화진동자 전환, 로코모션 시간-2배-흐름 버그 수정. **전부 완료.**
- `ally_ai_combat_system_status.md`/`enemy_ai_combat_system_status.md` (2026-08-10) —
  전투 컴포넌트 최초 구현 기록, 위 문서들 이전 상태.

## `level_new_kadex_0811/` — 신규 레벨 디자인/시나리오

- `scenario_authoring_guide.md`/`scenario_three_stage_combat.md` (2026-08-23) — 3단계 전투
  시나리오 DataTable 구현. **완료.**
- `scenario.md` (2026-08-22) — 위 시나리오 요구사항 정리판(구현 전).
- `new_kadex_0811_forest_perf.md` (2026-08-22) — PIE 2.3→31fps 성능 폭락 수정. **완료.**
- **[2026-08-31] 내비메시 구축 문서는 여기 없음** — `vehicle/ugv/
  2026-08-27_new_kadex_0811_navmesh_autonomous_driving.md` 참고(예전엔 이 폴더에도 08-22
  시점 구버전 사본이 있었는데, 완전히 그 문서의 부분집합이라 중복 제거함).

## `sfx_vfx/` — 사운드/파티클/환경 이펙트

- `hit_effects_update_2026-08-26.md` (2026-08-26) — **최신.** 지형/바위/나무/PCG 전체 재질별
  피격 이펙트, `PhysMaterialOverride` 필수 교훈, VFX 노출 수정.
- `hit_effects_update_2026-08-13.md` (2026-08-13) — 도탄/혈흔·화염 VFX/사운드.
- `hit_effects_implementation.md` (2026-08-12) — 1차 구현+트러블슈팅.
- `hit_effects_idea.md` (2026-08-12 이전) — 최초 기획 메모.
- `wind_system.md` (2026-08-29) — `AWindSource` 동적 바람, 식생+Niagara 8종+드론 물리 연동.

## `ui/` — WBP 위젯 개발

- `kadex_test_dashboard_wbp_spec.md` (2026-08, 최신) — **현재 실사용 위젯**
  (`UGVTestDashboardWidget`/`SelfDefenseDashboardWidget`/`AxisSelectionWidget`)의
  `BindWidgetOptional` 필드 스펙 + 버그 수정 이력. `guide/ui_dev_guide.md`(구 Monitor1Widget)
  를 대체하는 현재 UI 개발 기록.
- `graphics_settings_analysis.md` (2026-08-21) — 인게임 Settings 위젯 Graphics 탭 사전조사.
- `ingame_settings_input_system.md` (2026-08-21) — Settings 위젯 Input 탭 구현. **완료.**
- `truck.png`/`ugv.png` — 듀얼 모니터 레이아웃 목업 이미지.

## `protocol/` — LIG 원격통제기 UDP/JSON 프로토콜

- `protocol_icd.md` (최종 2026-08-31) — **필드 단위 명세, 가장 자주 참조되는 핵심 문서.**
- `ugv_rc_feature_gap_analysis.md` (최종 2026-08-31) — UGV축 cmd별 구현 상태 대조표.
- `selfdefense_rc_feature_gap_analysis.md` (2026-08-17) — 자체방호축 동일 성격 대조표.
- `lig_questions_0816.md` (최종 2026-09-02) — **LIG 문의 통합본, 최신.** 1차 답변 반영 완료,
  후속 질문 3건 + 회신 2건 발송 대기(§5-2는 질문이 아니라 결정 통보).
- `2026-09-02_object_class_expansion.md` (2026-09-02) — 탐지 `ObjectClass`를 `Human`/`Car`
  2값에서 플랫 6값으로 확장. 낙하산이 `Car`로 나가던 원인 조사 + 판정 순서.
- `lig_icd_ugv_rc_full.md` (2026-08-14) — LIG 정식 ICD 원문 전체 전사.
- `lig_questions_0807_draft.md`/`lig_questions_udp_reliability_0814.md` — **폐기, 기록용**
  (`lig_questions_0816.md`로 통합됨).

## `rtsp/` — RTSP 영상 송출

- `rtsp_poc_findings.md` (2026-08-18 최종) — NVENC/GStreamer PoC 전체 기록(크로스플랫폼 포함).
- `rtsp_integration_complete_0817.md` (2026-08-17) — 실 카메라 연결 완료, mount 확정.
- `rtsp_integration_status_0817.md` (해소됨 — 위 문서로 대체).
- `linux_wayland_x11_present_bottleneck.md` (2026-08-19) — Linux 풀스크린 프레임폭락 해결.
- `rtsp_client_reception_guide.md` (2026-08-24) — **LIG 공유용 최종 수신 가이드.**
- `rtsp_latency_investigation.md` (2026-08-19 최종) — 지연 441ms→68ms 조사 전체.
- `RTSP_Perf_Investigation.md` (2026-08-19) — 위 조사 원본 진행 로그.
- `rtsp_resolution_customization_0820.md` (2026-08-20) — 해상도 커스터마이징+CCTV 잘림버그+
  RCWS 이중렌더링 해결. **완료.**

## `replication/`

- `replication_audit.md` (최종 2026-08-14, §8 최신) — 리플리케이션 감사+구현 로그, 거의 완료.
  ⚠️ §8의 "UAV(2026-08-13 구현 완료)" 항목은 구 `AUAVPawn` 기준이라 옛날 얘기 — 새 드론은
  아래 문서 참고.
- `2026-09-01_drone_client_authoritative.md` — 새 드론은 서버가 아니라 **자체방호축 클라이언트가
  시뮬레이션**한다(조종 주체가 그쪽이라). Chaos Resimulation 기각 근거(RTSP +33ms, UGV 거동
  변화), 배선, `SetOwner` 소유권 함정. 2대 PC 실환경 검증 대기.

## `rc_mockup_tools/` — RC 목업/테스트 클라이언트

- `udp_protocol_client/README.md` (2026-08-15), `rtsp_viewer_test/README.md` (2026-08-17) —
  UDP/RTSP 테스트 도구.
- `hq_stub/README.md` (2026-08-06) — NATS 기반이라 전송계층 UDP 통일 결정으로 보류 상태.

## `packaging/` — 패키징/배포 실행 절차

- `2026-09-02_ugv_host_run_guide.md` — **패키지와 함께 넘기는 실행 가이드(단독 배포용).** 실행 방법,
  축 선택 화면 입력값(RC IP 필수 / 포트·해상도 선택), UGV Host 시작, 접속 정보(UDP 포트·RTSP URL).
- `2026-09-02_rc_gui_run_guide.md` — **통제기 목업 GUI(`ugv_rc_gui`) 실행 가이드(단독 배포용).**
  GStreamer 설치, 실행 인자, 조작 순서(연결 → 제어권+REMOTE → 주행/조준), 조이스틱 매핑, 탐지 bbox 색.
- `2026-09-02_linux_package_ugv_host_rc_test_guide.md` — 위 문서들의 **내부용 상세판**. 패키징 절차,
  데모/풀 시스템 스위치 배경, 코드 근거, 로그 확인 포인트까지 포함.

## `infra_architecture/`

- `architecture_decisions.md` (2026-08-07) — Layer C/UGV축/Layer A 아키텍처 결정 기록.
- `system_architecture_design_spec.md` (2026-08-05) — 최초 PDF 분석 데이터화.

## `genesis/` — 별도 병행 연구 트랙(일시중단, 재개 가능성 있어 보관)

- `2026-08-12_genesis_ugv_conversion.md` — `titan_example_genesis`(별도 프로젝트 카피)에서
  UGV를 외부 Python 물리 서버(Genesis)로 구동. 2026-08-31 확인: 최근 작업 안 함, 폐기 아님.

## `documents/` (.md만)

- `response_0828.md` (2026-08-28) — LIG 1차 답변 원문. `protocol/lig_questions_0816.md`에
  반영 완료.
- `문의내용0806.md` (2026-08-06) — 최초 LIG 문의 원문.
- (비-md 원본: PDF/PPTX/xlsx — 인덱스 대상 아님.)

## `_archive/` — 보관된 문서

각 파일 상단에 `[보관됨]` 노트로 사유/최신 문서 포인터 있음. 목록만:
`M1A2_UGV_Conversion.md`(BP_UGVFromTank는 채택 안 된 병행 시도, 엔지니어링 지식만 보관),
`tanksim_tank_analysis.md`, `aim.md`, `ally_and_scenario_system_plan.md`,
`ally_character_animation_design.md`, `chaos.md`, `charts.md`, `minimap.md`,
`mission_dashboard_widget_guide.md`, `scenario_datatable_system_plan.md`,
`scenario_implementation_status.md`, `status_hud_dev_guide.md`, `titan_quadcam_plan.md`,
`ui.md`, `시나리오.md`, `path/path.md`, `path/ugv_driving_dev_guide.md`,
`path/ugv_navmesh_autonomous_driving_dev_guide.md`(이 3개는 `_archive/path/` 하위) — 이상은
2026-08-31 이전 1차 정리분.

**2026-08-31 2차 정리(구조 재편)로 추가 보관**: `structure_README_track_index.md`(옛
`structure/README.md` 트랙 인덱스, `CURRENT_STATE.md`/`DOCS_INDEX.md`로 대체됨),
`sessions_idea.md`/`restructure_status_0813.md`/`idea.md`/`idea_review.md`(세션 분할·구조
개편 과정 기록, `WORKLOG.md`에 이미 흡수됨), `udp_test_findings.md`(LIG 참조구현 udp_test
분석, 정식 ICD로 대부분 대체됨), `lig_response_0806_review.md`(초기 LIG 답변 분석,
`protocol/`로 대체됨), `nats_infra_setup.md`(NATS 인프라, 폐기 결정됨).

---

## 파일명에 날짜 없음 (리네임 후보, 실행 안 함)

`guide/`, 대부분의 root 파일, `protocol/`·`rtsp/`·`replication/`·`infra_architecture/`의
핵심 문서 다수가 아직 `YYYY-MM-DD_` 접두 규칙 이전에 만들어짐 — 상호 참조 깨짐 위험 때문에
일괄 리네임은 안 함. 새로 만드는 문서부터 규칙 적용(`CLAUDE.md`).
