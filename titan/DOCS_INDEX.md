# 문서 전체 목록 (DOCS_INDEX)

2026-08-31 / 진행중 / titan 폴더 전체 .md 문서 카탈로그 — 문서 정리 1차 작업 산출물.

날짜는 가능하면 문서 내용에 적힌 실제 작업일 기준, 없으면 파일명의 날짜, 그것도 없으면
파일 수정시각(mtime) 순. **주의**: `2026-07-24 09:40~41` 시각을 가진 파일들은 전부 같은
분 단위로 찍혀있음 — 실제 작성일이 아니라 `C:\private\titan`에서 이 폴더로 **일괄 이관된
시점**으로 보임(원래 날짜는 유실). 아래에 "(이관, 원날짜 불명)"으로 표시.

이 문서는 목록만 다룬다 — 현재 프로젝트 상태 요약은 `CURRENT_STATE.md`, 신규 문서 작성
규칙은 `CLAUDE.md` 참고.

---

## 최상위 (`titan/`)

- `README.md` (2026-08-27, 최신 갱신) — 프로젝트 개요/시작점. structure/ 트랙 요약, 최근
  작업(레벨디자인/자율주행) 포인터, 알려진 이슈. **가장 먼저 읽을 문서.**
- `memo.md` (~2026-08-27, 계속 갱신 중) — 날짜순 아닌 누적 개인 백로그/아이디어 메모. 맨
  아래가 최신 항목.
- `ingame_settings_input_system.md` (2026-08-21) — 인게임 Settings 위젯 Input 탭 구현 기록.
- `content_asset_inventory.md` (2026-07-29) — 디자인팀 제공 Content 폴더(Characters,
  FPS_Weapon_Bundle, NiagaraExamples, Realistic_Starter_VFX_Pack_Vol2, ThirdPerson, Tutorial)
  전수 조사, 마켓플레이스 애셋 벤더별 정리.
- `ally_animation_request.md` (2026-08-07) — 디자인팀에 보낼 아군 애니메이션 시퀀스 요청서
  (스켈레톤 루트본 특이사항, 인플레이스/루프 조건 등 기술 요구사항). **현재 최신본.**
- `ally_move.md` (2026-08-07) — 아군 이동/애니메이션 설계(Posture×Alert×Movement FSM, 엄폐/
  분대/사격선 회피). §10 애니메이션 목록만 `ally_animation_request.md`로 갱신됐고 나머지
  FSM 설계는 **여전히 유효**.
- `all.md` (이관, 원날짜 불명) — Phase #4 시나리오 **공식 명세** 원문, 시나리오 관련 최상위
  소스 문서. **현재도 근거 문서로 유효.**
- `M1A2_UGV_Conversion.md` (이관, 원날짜 불명) — M1A2 탱크 BP 복제로 `BP_UGVFromTank` 만든
  전체 과정. `BP_UGVFromTank` 자체는 에셋 정리 트랙에서 레거시로 다뤄질 수 있지만, 엔지니어링
  지식(Chaos Vehicle possess 버그, 조향 토크 메커니즘 등)은 독립적으로 유용해서 **그대로 유지
  결정**(2026-08-31, 사용자 확인 — "나중에 필요할 것 같음").
- `tanksim_tank_analysis.md` (2026-06-23, 가장 오래된 날짜 있는 문서) — 참고 프로젝트
  `C:\working\TankSim`의 `ATankPawn` 분석(Titan 트럭 4분할 카메라 기능 설계 전 사전조사).
- `titan_dev_status.md` (2026-06-25) — QuadCamModule 플러그인 개발 현황(4방향 SceneCapture,
  M키 토글, 플러그인화). **현재도 유효.**
- `ui_dev_guide.md`, `quadcam_usage_guide.md`, `rcws_fire_control_dev_guide.md`,
  `pixelstreaming_setup_guide.md` (전부 이관, 원날짜 불명) — UI/대시보드/피처별 dev guide
  모음. `ui_dev_guide.md`는 원문 자체에 "최신화 안 됨" 명시하지만 `Monitor1Widget` 위젯 이름
  기준(§8)으로는 여전히 최신·유일한 레퍼런스 — 단, `Monitor1Widget` 자체도 2026-08-31 사용자
  확인상 현재 실사용 UI(`SelfDefenseMonitor1/2Widget` 등)가 아니므로, 이 문서도 조만간 재검토
  필요할 수 있음(아직 archive는 안 함, `ui_dev_guide.md`는 다른 위젯도 다뤄서 완전 대체는 아님).

## `mcp/`

- `unreal-mcp-claude-code.md`, `additional-mcp-integrations.md` (전부 이관, 원날짜 불명) —
  unreal-mcp/Claude Code 연동 설정 메모.

## `path/` — UGV 주행/AI

- `path\new_kadex_0811_navmesh_autonomous_driving.md` (2026-08-27) — **최신판.**
  `newlevel/`의 동명 문서(08-22)의 갱신본, A* 노드 예산/부분경로 버그 절 추가. 중복 아님.
- `path\ugv_obstacle_avoidance_2026-08-26.md` (2026-08-27 확정) — 장애물 회피 4대 원인 규명·
  해결, 실측 34.6km/h·조향포화 0회. **완료.**
- `path\ugv_track_lock_implementation_plan.md` (2026-08-26) — "공중에 뜬 바퀴 계속 회전" 버그
  근본원인 3단 규명·해결. **완료, 실기 확인됨.**
- `path\ugv_corner_braking_dev_guide.md` (2026-08-25 확인, 08-22 작업) — 커브 선행 감속(제동
  곡선) 구현. **완료.**
- `path\real2world.md`, `path\joystick_camera_control_dev_guide.md`,
  `path\detection_dev_guide.md` (전부 이관, 원날짜 불명) — 좌표보정 데이터/조이스틱 하드웨어
  세팅/탐지 시스템, 전부 지금도 유효한 레퍼런스.

## `soldiers/` — 적/아군 AI·전투

- `enemy_scenario_combat_expansion.md`, `enemy_hit_reaction_physics_system.md`,
  `enemy_locomotion_animation_pipeline.md` (전부 2026-08-24~25) — 3단계 전투 확장(Part A~G
  완료), 피격 리액션 감쇠조화진동자 전환, 로코모션 시간-2배-흐름 버그 수정. **전부 완료.**
- `ally_ai_combat_system_status.md`, `enemy_ai_combat_system_status.md` (2026-08-10) —
  아군/적군 전투 컴포넌트(`AllyFormationComponent`/`EnemyCombatComponent`) 최초 구현 기록,
  위 08-24~25 문서들 이전 상태.

## `newlevel/` — 신규 레벨(New_kadex_0811)

- `wind_system.md` (2026-08-29) — `AWindSource` 동적 바람 시스템, 식생+Niagara 8종+드론 물리
  연동 완료.
- `scenario_authoring_guide.md`, `scenario_three_stage_combat.md` (2026-08-23) — 3단계 전투
  시나리오 저작 가이드+구현(DataTable 17행). **완료.**
- `scenario.md` (2026-08-22) — 위 시나리오의 요구사항 정리판(구현 전).
- `new_kadex_0811_forest_perf.md` (2026-08-22) — PIE 2.3fps→31fps 성능 폭락 수정(나무 인스턴스
  설정 2건). **완료.**
- `new_kadex_0811_navmesh_autonomous_driving.md` (2026-08-22, **구버전** — `path/`의 동명
  파일이 최신) — 신규 레벨 내비메시 3층 구조 구축.

## `hit_effects/` — 피격 이펙트

- `hit_effects_update_2026-08-26.md` (2026-08-26) — **최신.** 지형/바위/나무/PCG 전체 재질별
  피격 이펙트 배선 완료, `PhysMaterialOverride` 필수 교훈, VFX 노출 문제 수정.
- `hit_effects_update_2026-08-13.md` (2026-08-13) — 도탄/혈흔·화염 VFX/사운드/차량 재질판정.
- `hit_effects_implementation.md` (2026-08-12) — 1차 구현+트러블슈팅(PhysMaterial 항상
  비어있는 버그 우회 등).
- `hit_effects_idea.md` (2026-08-12, 이전) — 최초 기획 메모(RCWS 탄종/폭발 이펙트 아이디어).

## `drone/`

- `drone_flight_dev_guide.md` (2026-08-27) — UAV 비행을 로터별 추력→토크→강체운동 정통 물리로
  전면 재구현, 기존 `AUAVPawn`과 완전 분리. 구동계+수동조종 완료, 자율비행 미착수.

## `genesis/` — 별도 병행 연구 트랙(일시중단, 재개 가능성 있어 계속 보관)

- `2026-08-12_genesis_ugv_conversion.md` (2026-08-12, 2026-08-31 상태 확인) — `titan_example`의
  P4V 워킹카피와 **분리된 별도 프로젝트 `titan_example_genesis`**에서, UGV를 Chaos Vehicle
  대신 외부 Python 물리 서버(Genesis)로 구동시키는 실험(격리 레벨 `kadex_test_genesis`에서만
  테스트, 운영 시나리오 영향 없음). **2026-08-31 사용자 확인: 최근 작업 안 함, 폐기 아님 —
  재개 가능성 있어 이 폴더에 계속 별도 보관.**

## `documents/` (.md만, PDF/PPTX/XLSX 원본은 별도)

- `response_0828.md` (2026-08-28) — **LIG 1차 답변 원문.** `structure/lig_questions_0816.md`에
  반영 완료.
- `문의내용0806.md` (2026-08-06) — 최초 LIG 문의 원문(시스템 구성/역할 분담 등). 답변은
  `structure/lig_response_0806_review.md`에서 분석함.
- (비-md 원본: `260420_UGV에뮬레이터_상세설계_v1.pdf`, `260508_임무장비 모의기 상세설계_송부용.pdf/.pptx`,
  `용역과제계획서(...)_20260624.pptx`, `임무장비모의기_일정_2026_황인성.xlsx` — 인덱스 대상 아님.)

---

## `structure/` — LIG 프로토콜/RTSP/리플리케이션/인프라 트랙

**이 폴더는 `structure/README.md`가 이미 트랙 단위(트랙1~7)로 관리 중 — 더 자세한 서사는
그쪽을 볼 것.** 아래는 파일 단위 평면 목록(빠뜨리기 쉬운 것 방지용).

- `protocol_icd.md` (최종 갱신 2026-08-31) — **UGV/자체방호축 프로토콜 필드 단위 명세, 가장
  자주 참조되는 핵심 문서.**
- `ugv_rc_feature_gap_analysis.md` (최종 갱신 2026-08-31) — UGV축 cmd별 구현 상태 1:1 대조표.
- `selfdefense_rc_feature_gap_analysis.md` (2026-08-17) — 자체방호축 동일 성격 대조표.
- `lig_questions_0816.md` (최종 갱신 2026-08-28) — **LIG 문의 통합본, 최신.** 1차 답변 반영
  완료, 후속 질문 3건 발송 대기 중.
- `lig_icd_ugv_rc_full.md` (2026-08-14) — LIG 정식 ICD 원문 전체 전사.
- `replication_audit.md` (최종 갱신 2026-08-14, §8이 최신) — 멀티플레이 리플리케이션 감사+구현
  로그, 거의 완료.
- `architecture_decisions.md` (2026-08-07) — Layer C/UGV축/Layer A 아키텍처 결정 기록.
- `graphics_settings_analysis.md` (2026-08-21) — 인게임 Settings 위젯 Graphics 탭 사전조사.
- `README.md` (2026-08-21) — 트랙 1~7 인덱스.
- `restructure_status_0813.md` (2026-08-13) — 구조 개편 스냅샷(옛날, 대부분 위 문서들로 대체됨).
- `rtsp_integration_complete_0817.md` (2026-08-17) — RTSP 실 카메라 연결 완료 기록.
- `rtsp_integration_status_0817.md` (2026-08-17, **해소됨** — 위 문서로 대체) — 갭 분석.
- `rtsp_poc_findings.md` (2026-08-18 최종 갱신) — RTSP PoC 전체 기록(NVENC/GStreamer, 크로스
  플랫폼 포함).
- `linux_wayland_x11_present_bottleneck.md` (2026-08-19) — Linux 풀스크린 프레임폭락 원인/해결.
- `kadex_test_dashboard_wbp_spec.md` (2026-08-10), `rcws_preview_actor_asset_ref_todo.md`
  (2026-08-11) — 대시보드 위젯/RCWS 프리뷰 애셋 관련 TODO.
- `udp_test_findings.md` (2026-08-07), `lig_response_0806_review.md`/`nats_infra_setup.md`/
  `sessions_idea.md` (2026-08-06) — 초기 LIG 답변 분석/NATS 인프라(폐기)/세션 분할 아이디어.
- `system_architecture_design_spec.md`/`idea.md`/`idea_review.md` (2026-08-05) — 최초 PDF
  분석+아이디어 리뷰(프로젝트 시작점 기록).
- `lig_questions_0807_draft.md`/`lig_questions_udp_reliability_0814.md` (**둘 다 폐기, 기록용
  — `lig_questions_0816.md`로 통합됨**, 원문 자체에 이미 명시됨).

### `structure/` 하위 폴더

- `rtsp/rtsp_client_reception_guide.md` (2026-08-24) — **LIG 공유용 최종 RTSP 수신 가이드.**
- `rtsp/rtsp_latency_investigation.md` (2026-08-19 최종) — 지연 441ms→68ms 조사 전체 기록.
- `rtsp/RTSP_Perf_Investigation.md` (2026-08-19) — 위 조사의 원본 진행 로그(중복 아님, 참고용
  원본이라고 문서 자체에 명시).
- `rtsp/rtsp_postprocess_parity_0820.md` (2026-08-20) — RTSP 스트림에 SSR/피격 흔들림 안 나오던
  문제 원인 규명(SceneCapture와 메인뷰포트가 실제로 다른 카메라였음, 엔진이 SceneCapture에
  `ReflectionMethod=None` 강제).
- `rtsp/rtsp_resolution_customization_0820.md` (2026-08-20) — RTSP 해상도 커스터마이징+CCTV
  잘림버그+RCWS 이중렌더링 해결. **완료(사용자 실측 확인).**
- `rc_gui/README.md` (2026-08-18) — ⚠️ **중복 코드베이스 발견**: 여기 `structure/rc_gui/`에
  `net_client.py`/`video_panel.py`/`main_window.py` 등 완전한 Python GUI 코드가 있는데, 이후
  대화에서 언급되는 실제 사용 도구는 `C:\working\works\kadex\ugv_rc_gui\`(별도 위치)다. 파일
  구성이 겹쳐 보여서(`video_panel.py` 등) 이게 그 도구의 **더 이전 버전/원형**이거나, 반대로
  이 폴더가 안 쓰이는 죽은 사본일 가능성이 있음 — 확인 후 하나로 정리 권장(에셋/코드 정리
  세션 후보 항목으로 등록 권장).
- `udp_protocol_client/README.md` (2026-08-15), `rtsp_viewer_test/README.md` (2026-08-17),
  `hq_stub/README.md` (2026-08-06) — 트랙2/3/구트랙2 산출물 각각의 README. `hq_stub`은 NATS
  기반이라 전송계층 UDP 통일 결정으로 보류 상태(README.md 트랙3 참고).

---

## `_archive/` — 보관된 문서(2026-08-31, 최신 문서로 대체됨)

폴더 구조(하위 폴더 포함)는 보관 전 그대로 유지. 각 파일 맨 위에 `[보관됨]` 한 줄 노트로
최신 버전 경로/사유를 남겨둠 — 자세한 사유는 그 노트 참고, 아래는 요약만.

- `_archive/charts.md` — 보관됨, 최신: `status_hud_dev_guide.md` (차트 위젯 목업 → 실구현).
- `_archive/aim.md` — 보관됨, 최신: `rcws_fire_control_dev_guide.md` (RCWS on/off 커맨드가
  `ERCWSControlMode` 통합 시스템으로 대체).
- `_archive/chaos.md` — 보관됨, 최신: `M1A2_UGV_Conversion.md` (제안했던 접근 자체가 폐기됨).
- `_archive/titan_quadcam_plan.md` — 보관됨, 최신: `titan_dev_status.md` (계획이 그대로 구현됨).
- `_archive/minimap.md` — 보관됨, 최신: `ui_dev_guide.md` §4 (요구사항이 `MinimapOverlayWidget`
  으로 구현됨).
- `_archive/mission_dashboard_widget_guide.md` — 보관됨, 최신: `ui_dev_guide.md` §5/§8
  (`MissionDashboardWidget`→`Monitor1Widget` 전환).
- `_archive/시나리오.md` — 보관됨, 최신: `newlevel/scenario_three_stage_combat.md` (옛 레벨
  시나리오 → 새 레벨 3단계 전투로 대체).
- `_archive/scenario_implementation_status.md` — 보관됨, 최신: 상동. 단 아군 이동/회피 근본원인
  수정 기록(§1, §7)은 옛 레벨 기준이어도 참고 가치 있음.
- `_archive/ally_character_animation_design.md` — 보관됨, 최신: `ally_move.md` (Posture/Alert/
  Movement FSM으로 재설계됨).
- `_archive/ally_and_scenario_system_plan.md` — 보관됨, 최신: `scenario_implementation_status.md`
  (착수 전 설계 논의 → 구현 완료).
- `_archive/scenario_datatable_system_plan.md` — 보관됨, 최신: 상동 §2 (`DT_ScenarioSteps`로
  실제 구현됨).
- `_archive/path/ugv_navmesh_autonomous_driving_dev_guide.md` — 보관됨, 최신:
  `path/new_kadex_0811_navmesh_autonomous_driving.md` (옛 레벨 NavMesh 구축 → 새 레벨로 이전).
- `_archive/path/path.md` — 보관됨, 최신: `path/ugv_driving_dev_guide.md`였으나 그 문서도
  이후 아카이브됨(아래 참고) — 실제 최신은 `path/ugv_obstacle_avoidance_2026-08-26.md` 등.
- `_archive/status_hud_dev_guide.md` — 보관됨(2026-08-31), 사유: `Monitor1Widget` 체계 자체가
  현재 안 쓰임(사용자 확인, 현재는 `SelfDefenseMonitor1/2Widget` 등) — 전용 후속 문서 없음.
- `_archive/ui.md` — 보관됨(2026-08-31), 사유: 상동("모니터 1" = 구 `Monitor1Widget`).
- `_archive/path/ugv_driving_dev_guide.md` — 보관됨(2026-08-31), 사유: `kadex_demo`/`BP_UGV`
  기준 구버전 문서, 실제 최신은 `path/ugv_obstacle_avoidance_2026-08-26.md`/
  `ugv_track_lock_implementation_plan.md`/`new_kadex_0811_navmesh_autonomous_driving.md` — 단
  Pure Pursuit·NavMesh 도로선호·`EUGVDriveMode` 설계 개념 자체는 여전히 유효(사용자 확인,
  "완전 중요한 게 아니면 archive해도 됨"이라 삭제 아닌 보관만 함).

---

## 파일명에 날짜 없음(리네임 후보, 실행 안 함 — `_archive/`로 옮겨진 13개는 이 목록에서 제외)

아래는 `YYYY-MM-DD_` 접두 규칙을 안 따르는 파일들 — 이번 1차 정리에서 리네임은 안 함(상호
참조 깨짐 위험, `titan_docs_cleanup_initiative` 메모리 참고). 목록만 남김:

```
README.md, memo.md, ingame_settings_input_system.md, content_asset_inventory.md,
ally_animation_request.md, ally_move.md, all.md, M1A2_UGV_Conversion.md,
tanksim_tank_analysis.md, titan_dev_status.md, ui_dev_guide.md,
quadcam_usage_guide.md, rcws_fire_control_dev_guide.md, pixelstreaming_setup_guide.md,
mcp/unreal-mcp-claude-code.md, mcp/additional-mcp-integrations.md,
path/real2world.md, path/joystick_camera_control_dev_guide.md,
path/detection_dev_guide.md, path/ugv_corner_braking_dev_guide.md,
path/ugv_track_lock_implementation_plan.md,
soldiers/ally_ai_combat_system_status.md, soldiers/enemy_ai_combat_system_status.md,
soldiers/enemy_scenario_combat_expansion.md, soldiers/enemy_hit_reaction_physics_system.md,
soldiers/enemy_locomotion_animation_pipeline.md, newlevel/wind_system.md, newlevel/scenario.md,
newlevel/scenario_authoring_guide.md, newlevel/scenario_three_stage_combat.md,
drone/drone_flight_dev_guide.md, documents/문의내용0806.md, documents/response_0828.md,
structure/README.md, structure/protocol_icd.md, structure/ugv_rc_feature_gap_analysis.md,
structure/selfdefense_rc_feature_gap_analysis.md, structure/lig_questions_0816.md,
structure/lig_icd_ugv_rc_full.md, structure/replication_audit.md,
structure/architecture_decisions.md, structure/graphics_settings_analysis.md,
structure/idea.md, structure/idea_review.md, structure/system_architecture_design_spec.md,
structure/sessions_idea.md, structure/nats_infra_setup.md, structure/udp_test_findings.md,
structure/lig_response_0806_review.md, structure/kadex_test_dashboard_wbp_spec.md,
structure/rcws_preview_actor_asset_ref_todo.md, structure/rtsp_poc_findings.md,
structure/rtsp_integration_complete_0817.md, structure/rtsp_integration_status_0817.md,
structure/linux_wayland_x11_present_bottleneck.md, structure/lig_questions_0807_draft.md,
structure/lig_questions_udp_reliability_0814.md, structure/rtsp/rtsp_client_reception_guide.md,
structure/rtsp/rtsp_latency_investigation.md, structure/rtsp/RTSP_Perf_Investigation.md,
structure/udp_protocol_client/README.md,
structure/rtsp_viewer_test/README.md, structure/hq_stub/README.md
```

(`README_save.md`, `structure/rc_gui/`는 2026-08-31에 삭제됨 — 목록에서 제외. `_archive/`로
옮겨진 16개(13개 1차분 + `status_hud_dev_guide.md`/`ui.md`/`path/ugv_driving_dev_guide.md`
2차분)도 제외, 위 `_archive/` 섹션 참고.)

(파일명에 이미 날짜가 있는 것: `genesis_ugv_conversion_0812.md`, `hit_effects_update_2026-08-13.md`,
`hit_effects_update_2026-08-26.md`, `new_kadex_0811_*.md`, `ugv_obstacle_avoidance_2026-08-26.md`,
`rtsp_postprocess_parity_0820.md`, `rtsp_resolution_customization_0820.md` 등은 제외됨.)
