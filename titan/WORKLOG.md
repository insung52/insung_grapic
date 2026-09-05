# WORKLOG — 프로젝트 전체 작업 시간순 기록

2026-08-31 / 진행중 / titan 프로젝트 전체를 실제 작업 순서대로 서술한 타임라인.

`DOCS_INDEX.md`가 "문서가 어디 있는가"의 카탈로그라면, 이 문서는 **"무슨 일이 어떤 순서로
있었는가"**의 서사다. 겹치는 정보가 있는 게 정상 — 목적이 다름. 날짜 출처/불확실성 표기는
`DOCS_INDEX.md` 서두 참고(특히 `2026-07-24 09:40~41` 일괄 이관 건).

---

## 2026년 6월 — 사전 조사, 카메라 파이프라인 초기 구현

- **06-23** `tanksim_tank_analysis.md` — 참고 프로젝트 TankSim의 `ATankPawn` 분석(4분할
  카메라 기능 설계 전 사전조사).
- **06-24** `guide/quadcam_usage_guide.md` — QuadCamModule(4분할 카메라) 플러그인 최초 구현.
- **06-25** `titan_dev_status.md` — QuadCamModule 개발 현황(M키 토글, 플러그인화).

## 2026년 7월 상순 — 조작/탐지/UI 기반 다지기

- **07-06** `guide/pixelstreaming_setup_guide.md`, (구)`ugv_driving_dev_guide.md`(현재
  `_archive/path/`) — Pixel Streaming 테스트, UGV 수동/자동 주행 최초 구현(`kadex_demo` 레벨,
  `BP_UGV`).
- **07-08** `guide/joystick_camera_control_dev_guide.md` — 조이스틱(Logitech Extreme 3D Pro)
  기반 RCWS/UAV 카메라 조작.
- **07-09** `guide/detection_dev_guide.md` — 카메라 기반 객체 탐지(BBox) 모사 구현.
- **07-10** `guide/ui_dev_guide.md` — Monitor1/2 UI 연동(당시 최신, 지금은 레거시로 확인됨).
- **07-12~14** `guide/rcws_fire_control_dev_guide.md` — RCWS 자동/수동 조준·발사 메커니즘.

## 2026년 7월 하순 — 시나리오/아군 시스템 설계 착수

- **07-24 전후** (일괄 이관 타임스탬프) 다수 초기 dev guide/메모 작성 — `all.md`(Phase #4
  시나리오 공식 명세), `chaos.md`/`M1A2_UGV_Conversion.md`(UGV Chaos Vehicle 물리),
  `titan_quadcam_plan.md`(archived) 등.
- **07-28** (구)`ally_and_scenario_system_plan.md`(archived) — 아군 BP+시나리오 관리 설계 논의.
- **07-29** `content_asset_inventory.md` — 디자인팀 제공 Content 폴더 전수 조사(마켓플레이스
  애셋 정리).
- **07-30** (구)`scenario_datatable_system_plan.md`(archived) — 시나리오 DataTable화 설계안.

## 2026년 8월 상순 — LIG 협업 시작, 아키텍처 확정

- **08-04** (구)`scenario_implementation_status.md`, `ally_character_animation_design.md`
  (둘 다 archived) — 아군+UGV 동반이동 구현, 아군 애니메이션 개편 설계.
- **08-05** `infra_architecture/system_architecture_design_spec.md`/`idea.md`/`idea_review.md`,
  (구)`시나리오.md`(archived) — LIG 원본 PDF 분석 시작, 전체 아키텍처 설계 착수.
- **08-06** `_archive/lig_response_0806_review.md`/`nats_infra_setup.md`/`sessions_idea.md`,
  `documents/문의내용0806.md` — LIG 최초 Q&A, NATS 인프라 구축(이후 폐기), 세션 분할 구상.
- **08-07** `_archive/udp_test_findings.md`/`architecture_decisions.md`, `ally_animation_request.md`,
  `ally_move.md` — LIG 참조구현 검토, UDP 전면 통일 결정(NATS 폐기), 아군 애니메이션 요청서.
- **08-10** `ui/kadex_test_dashboard_wbp_spec.md`, `ai_combat/ally_ai_combat_system_status.md`/
  `enemy_ai_combat_system_status.md` — 아군/적군 전투 컴포넌트 최초 구현.
- **08-11** `rcws/rcws_preview_actor_asset_ref_todo.md`.
- **08-12** `genesis/2026-08-12_genesis_ugv_conversion.md`(별도 병행 트랙, 현재 일시중단),
  `sfx_vfx/hit_effects_idea.md`→`hit_effects_implementation.md` — 피격 이펙트 1차 구현.
- **08-13** `_archive/restructure_status_0813.md`, `sfx_vfx/hit_effects_update_2026-08-13.md`
  — 구조 개편 스냅샷, 피격 이펙트 2차(도탄/혈흔/화염).
- **08-14** `protocol/lig_icd_ugv_rc_full.md`, `replication_audit.md`(§8까지) — **LIG 정식
  ICD 확보**(가장 중요한 전환점 중 하나), 리플리케이션 감사+구현 대부분 완료.

## 2026년 8월 중순 — LIG 프로토콜 구현, RTSP 착수

- **08-16~17** `protocol/ugv_rc_feature_gap_analysis.md`/`selfdefense_rc_feature_gap_analysis.md`
  — UGV축/자체방호축 LIG 프로토콜 구현+cmd별 갭 분석.
- **08-17** `rtsp/rtsp_integration_complete_0817.md` — RTSP 실 카메라(UGV 5+자체방호 7)
  연결 완료, mount 확정.
- **08-18** `rtsp/rtsp_poc_findings.md`(최종), (구)`structure/rc_gui/`(2026-08-31 삭제됨,
  중복 코드베이스로 확인) — NVENC/GStreamer RTSP 파이프라인 PoC 마무리.
- **08-19** `rtsp/linux_wayland_x11_present_bottleneck.md`,
  `rtsp/rtsp_latency_investigation.md`(경과) — Linux 풀스크린 프레임폭락 해결, RTSP 지연 조사 시작.
- **08-20** `camera_pipeline/rtsp_postprocess_parity_0820.md`, `rtsp/rtsp_resolution_customization_0820.md`
  — RTSP 스트림 SSR/피격흔들림 누락 원인 규명, 해상도 커스터마이징+CCTV 잘림버그 해결.
- **08-21** `ui/graphics_settings_analysis.md`, `ui/ingame_settings_input_system.md` — 인게임
  Settings 위젯 Input 완료+Graphics 조사.

## 2026년 8월 하순 — 레벨 디자인/자율주행 집중 스프린트, LIG 1차 답변

- **08-22** 신규 레벨 NavMesh 최초 구축(당시 `newlevel/`, 08-27 갱신판만 남기고
  `vehicle/ugv/2026-08-27_new_kadex_0811_navmesh_autonomous_driving.md`로 2026-08-31 중복
  통합됨 — 상세는 그 문서 참고), `new_kadex_0811_forest_perf.md`,
  `level_new_kadex_0811/scenario.md` — 신규 레벨(New_kadex_0811) NavMesh 구축, 성능 폭락(2.3→31fps) 수정.
- **08-23** `level_new_kadex_0811/scenario_authoring_guide.md`/`scenario_three_stage_combat.md` — 3단계
  전투 시나리오 DataTable 구현 완료.
- **08-24~25** `ai_combat/enemy_locomotion_animation_pipeline.md`/`enemy_hit_reaction_physics_system.md`/
  `enemy_scenario_combat_expansion.md`, `rtsp/rtsp_client_reception_guide.md`
  (2026-08-24) — 적군 AI/애니메이션/전투 대규모 개편(Part A~G 완료), RTSP LIG 공유용 최종
  가이드 작성.
- **08-25** `vehicle/ugv/2026-08-22_ugv_corner_braking_dev_guide.md` — 커브 선행 감속(제동 곡선) 구현 완료.
- **08-26** `vehicle/ugv/2026-08-26_ugv_track_lock_implementation_plan.md`, `sfx_vfx/hit_effects_update_2026-08-26.md`
  — "공중에 뜬 바퀴" 오래된 버그 완전 해결, 피격 이펙트 최종(전체 재질 커버).
- **08-27** `vehicle/ugv/2026-08-26_ugv_obstacle_avoidance.md`(확정),
  `vehicle/ugv/2026-08-27_new_kadex_0811_navmesh_autonomous_driving.md`(갱신판),
  `vehicle/drone/drone_flight_dev_guide.md`, `titan/README.md` 갱신 —
  장애물 회피 4대 원인 해결(실측 34.6km/h), 드론 물리 전면 재구현, 최상위 README 갱신.
- **08-28** `documents/response_0828.md` — **LIG 1차 답변 도착**(요청/응답, 안전장치, ICD
  오기입 정정, RC_ActivateMovement 정체 등 대거 해소).
- **08-29** `sfx_vfx/wind_system.md` — 동적 바람 시스템.

## 2026년 8월 31일 — LIG 답변 반영, 문서 정리 착수

- LIG 답변을 `protocol/protocol_icd.md`/`ugv_rc_feature_gap_analysis.md`/
  `protocol/lig_questions_0816.md`에 전부 반영, 후속 질문 3건 정리.
- UGV축 세션이 `RC_ActivateMovement` 재매핑(차량 시동 → RCWS 조향 게이트) 실제 구현 완료.
- **문서 정리 이니셔티브 시작**: `CLAUDE.md`(문서 작성 규칙) 도입, `CURRENT_STATE.md`/
  `DOCS_INDEX.md` 신설, 중복/레거시 문서 정리(`structure/rc_gui/`·`README_save.md` 삭제,
  `genesis/` 재정리, 레거시 dev guide 16개 `_archive/`로 이동), `guide/` 폴더 신설(레퍼런스성
  dev guide 9개 이동, 최신화 필요 경고 배너 부착), 이 `WORKLOG.md` 작성.
- `rcws/2026-08-31_selfdefense_camera_shake_bugs.md` — 자체방호축 카메라 버그 2건
  (RCWS 조향 시 환경카메라/CCTV 떨림, UGV 발사 셰이크가 자체방호 3화면 오염) **원인 확정 +
  코드 수정 완료**. 둘 다 셰이크 경로 하나에서 갈라진 문제였고, 사용자 최초 가설(공유 트랜스폼
  리플리케이션 노이즈)은 반증됨. `SceneCaptureViewParity`(프로브 모디파이어 신설) +
  `RCWSProjectile`(명중 셰이크 발사자 게이팅) 수정. **2-PC 실환경 검증은 미실시**.

## 2026년 8월 28일 ~ 9월 1일 — 드론이 구 BP_UAV를 대체

08-27에 구동계만 완성돼 있던 새 물리 드론(`ADronePawn`)에 나머지 기능을 전부 얹어 구
`AUAVPawn`/`BP_UAV`를 대체한 작업. 상세는 `vehicle/drone/2026-09-01_drone_replaces_bp_uav.md`,
동작 레퍼런스는 같은 폴더 `drone_flight_dev_guide.md`.

- **08-28** 짐벌 이식(BP CineCamera + 런타임 SceneCapture, 구 UAV와 같은 패턴). 본 회전을
  컴포넌트 공간 절대값으로 넘겨야 한다는 걸 몰라서 2회 재작업 — "밖에선 팬이 도는데 짐벌
  시점에선 안 먹는" 증상.
- **08-28** 프로펠러 사운드(평균/편차/로터별 3모드 + 구 UAV식 우선순위 보호), 자율비행 1차 구현.
  설계 원칙은 "**위치를 직접 쓰지 않는다**" — 오토파일럿이 사람과 똑같은 4채널 스틱 입력만
  만들어서 물리를 그대로 살린다.
- **08-29** 다른 세션이 만든 바람 시스템(`sfx_vfx/wind_system.md`) 연동. 자율비행 버그 3건
  해결 — 45km/h 경로를 10km/h로 기어가던 Pure Pursuit 오배선, 커브 감속이 아예 안 걸리던
  `√(a/κ)` 공식, 바람을 미리 읽어 완벽 상쇄하던 비현실적 항력 피드포워드. 셋 다 UGV 자율주행
  로직을 **구조만 보고 옮긴** 것이 원인이었다.
- **08-29** 시나리오 재배선 — **드론의 낙하산 관측 성공이 UGV 출발 트리거**가 됐다(예전엔
  "UAV 적 감지"). 적 탐색 단계·아군 집결 대기는 제거. 트리거 `UAVParachuteObserved`와
  이펙트 2개 신설, `DT_ScenarioSteps_ThreeStage`에 드론 행 2개 추가.
- **08-30** 단계별 탐지(아군만 → +낙하산 → +적군), 클라이언트 권위 리플리케이션, 위젯 배선.
  드론 조종 주체가 서버(UGV축)가 아니라 클라이언트(자체방호축)라 방향을 뒤집었다. Chaos
  Resimulation은 RTSP 지연 +33ms와 UGV 거동 변화 때문에 기각
  (`replication/2026-09-01_drone_client_authoritative.md`).
- **08-31** 유니티 빌드가 익명 네임스페이스를 합치면서 난 상수 재정의 오류 정리.
- **09-01** 단일 프로세스 `New_kadex_0811`에서 시나리오 전체 흐름 검증 완료, 문서 최신화.
  **2대 PC 실환경 검증만 남음.**
- **09-02** UGV 탐지 `ObjectClass`를 ICD 원문 `Human`/`Car` 2값에서 플랫 6값
  (Ally/Enemy/UGV/MobileCommandPost/Drone/Parachute)으로 확장. 낙하산이 `Car`로 나가던 원인은
  `BP_Parachute`가 `ACharacter`가 아닌 `AActor` 직속이라 2분류의 else 가지로 떨어진 것 —
  `Faction==EnemyEvidence`로 집는다. LIG가 재량으로 확정해준 항목이라 답변 대기 없이 구현,
  통보만 남음(`protocol/2026-09-02_object_class_expansion.md`).
- **09-02** **UGV를 디자인팀 신규 모델(궤도 없는 차륜 6×6, 단발 중기관총 포탑)로 교체** —
  블렌더 리깅(본 10개, 옛 이름 유지)부터 `SK_UGV_0901`/`BP_UGV_0901`/`ABP_UGV_0901`/머티리얼
  7종/주행 튜닝까지. 궤도 비주얼·총열 회전 제거, 스키드 스티어와 TrackLock C++은 그대로 재사용
  (좌우 분류가 휠 개수에 무관해서 6륜에도 그대로 동작). 주행·포탑·서스펜션·시나리오 자율주행·
  피격 재질 판정 전부 실동작 확인. 총열 회전 발사 게이트는 `bUseBarrelSpin` 플래그로 제거
  (`URCWSFireControlComponent`를 개틀링인 TitanTruck과 공유해서 통째로 못 걷어냄 — 기본값 true라
  트럭은 그대로). **작업 완료**, BP 고아 노드 정리만 나중 과제로 남음.
  휠 반지름 15→31.6cm·개수 16→6이 주행에 미친 영향과 스케일 규칙, 블렌더 FBX 루트 스케일 100
  함정, ABP Retarget이 EventGraph 캐스트를 안 바꾸는 함정 전부
  `vehicle/ugv/2026-09-02_ugv_0901_new_model_rig.md`에 정리.

- **09-03** `ui/graphics_settings_analysis.md` 팔로업 — 8/21 Graphics 탭 사전조사 문서를 그동안의
  변경분에 맞춰 재검증·갱신(`§0-2`). 정정 4건(가장 큰 것: `[ConsoleVariables]`의 cvar 우선순위가
  `SetByConsoleVariablesIni`가 아니라 `SetBySystemSettingsIni` — 결론은 동일), 계획 변동 2건
  (프레임 상한은 물리 결정성 대책이라 탭에서 60 위로 열면 안 됨 / 창 모드는 실제 운용이
  `-fullscreen` 런치 인자라 후순위). 카메라 인벤토리도 드론·UGV BP 교체분 반영.
  이어서 `DumpCVars` 전수 실측으로 **`UGameUserSettings` 품질 경로가 완전 no-op**임을 확정하고
  (`sg.*` 12개가 전부 `SystemSettingsIni` 고정), 채택 구조(`UTitanGraphicsSettings` 단일 소스)와
  최종 세팅 후보 목록을 문서 §9/§10에 정리. **구현은 미착수, 사용자 검토 대기.**

- **09-03** `BP_UGV_0901` 블루프린트 로직 C++ 이관 + 죽은 노드 전면 정리. 9/2 문서 §9에 남겨둔
  "고아 노드 ~250개" 과제였는데 실제로는 4개 그래프에 걸쳐 **427개 + 변수 39개**였다
  (`UpdateTurretVisuals` 안에만 168개 — 살아있는 체인의 중복 복제본이 통째로 남아 있었음).
  정리하는 김에 남은 BP 로직 4개(`UpdateTurretVisuals` / `SetManualControl` / `SetBraking` /
  Tick)를 새 부모 **`AUGV0901Pawn`**(`AUGVWheeledVehiclePawn` 서브클래스)으로 전부 내렸다.
  BP는 로직 0줄 · 변수 0개의 순수 데이터 에셋이 됐고 `.uasset`이 **1,150KB → 67KB**.
  구형 `BP_UGV_Vehicle_new`는 안 건드림(같은 부모를 쓰고 아직 자기 BP에서 같은 니아가라
  파라미터를 굴리므로, 부모에 넣었으면 이중 구동이 됐다 — 그래서 서브클래스).
  함정 2건: **죽은 노드를 "연결된 노드"로 판정하면 안 된다**(exec 선만 끊긴 체인이 Tick의
  `DeltaSeconds` 데이터 핀에 아직 물려 있어서 249개 중 230개가 살아있는 걸로 나옴 — exec
  도달성 + 데이터 생산자 역추적 2단계로 해야 4개가 나온다), **BP의 기본 float은 실제로
  double**(C++를 `float`로 잡았더니 ABP가 타입 불일치로 컴파일 실패 — BP가 핀으로 직접 읽는
  프로퍼티는 `double`이어야 함). 컴포넌트 22개·차량 튜닝 값 전부 보존 확인, ABP 캐스트가
  새 C++ 부모로 정상 해석됨, PIE에서 네이티브 Tick 포탑 추종 확인.
  과열 연기 실사격 확인과 실주행 확인은 남음. `vehicle/ugv/2026-09-03_ugv_0901_bp_to_cpp.md`.

## 2026년 9월 3일 ~ 5일 — 드론 교전 관측 이동

교전이 시작되면 드론이 **경로 스플라인 위에서 "전황을 가장 잘 보여주는 지점"으로 스스로
이동**하는 시스템. 짐벌은 각도만 바꿀 뿐 거리를 못 줄여서, 교전이 2·3차 전투지로 옮겨가면
"전원이 담기긴 하는데 아무것도 분간이 안 되는" 그림이 남던 문제. 상세:
`vehicle/drone/2026-09-05_drone_engagement_observation.md`, 동작 레퍼런스는 같은 폴더
`drone_flight_dev_guide.md` 16절.

- **09-03** 관측 지점 선정 구현. 처음엔 "내가 정한 이상적 거리·고도에 가까운 곳"이라는 대리
  지표로 짰다가 사용자 지적으로 **실제 프레이밍 결과**(필요 화각·조준 부감)로 갈아엎음. 이어서
  연속 최적화가 3분간 25m씩 21회 기어가는 래칫을 만들어, **제약 만족**(조건을 만족하는 동안은
  움직일 이유가 없다) 방식으로 재설계.
- **09-03** 프레이밍 대상을 `TargetDetection`에서 분리 — 탐지 결과를 입력으로 쓰면
  `줌아웃→탐지해제→프레이밍축소→줌인` 순환 의존이 생긴다. 레지스트리 직결로 전환.
- **09-04** 유도 루프 구조 결함 3연쇄 해결. 적분 와인드업 → 그 수정이 축별이 아니라 3차원
  전체를 얼리던 것 → **속도 피드포워드 부재로 인한 ζ=0.51 저감쇠 진동**(주기 6.8초). 경로
  추종이 원래 부드러웠던 건 거버너 속도를 쓰는 이미 피드포워드 구조였기 때문이고, 관측만
  순수 위치 피드백이었다.
- **09-04** 겉보기 크기 필터가 **화각에 반비례**해 교전 광각에서 탐지 사거리를 800m→45m로
  무너뜨리던 버그. 폰의 미러 프로퍼티가 BP 컴포넌트 설정을 매 플레이마다 덮어쓰고 있었다.
- **09-05** 카메라와 기체 방향 분리(짐벌 요는 원래 무제한이라 기수가 피사체를 향할 이유가
  없었다), 도주 중인 적 트래킹 제외, 3차 전환을 시나리오 스텝이 아니라 월드 상태로 게이트.
  **실동작 확인 완료.**

---

## 다음에 예정된 것 (이 시점 기준)

- 드론 **2프로세스(2대 PC) 실환경 검증** → 통과하면 구 `AUAVPawn`/`BP_UAV`와 시나리오 폴백
  분기 제거. 2·3차 전투지 추격 스플라인 추가(코드 준비됨, 레벨 작업만).
- 자체방호축 카메라 버그 2건 **2-PC 실환경 검증**(코드 수정은 완료, 빌드/실측만 남음 —
  `rcws/2026-08-31_selfdefense_camera_shake_bugs.md` §3의 절차).
- `guide/` 문서 내용 실제 최신화(2단계, 시스템별로 별도 세션 — 아직 착수 전).
- 언리얼 에셋/코드 정리(레거시 BP, 폴더 구조) — 별도 세션 착수 예정, 아직 시작 전.
- LIG 후속 질문 3건 + 회신 2건 발송 대기(`protocol/lig_questions_0816.md`).
- 레벨 디자인/UGV 자율주행 지속.
