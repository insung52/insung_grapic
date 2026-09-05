# Titan (KADEX 전시회) — 현재 프로젝트 상태

2026-09-01 / 진행중 / 전체 시스템별 현재 상태 스냅샷 — 문서 정리 1차 작업의 산출물.

이 문서는 "지금 뭐가 어디까지 되어 있는가"만 다룬다. 문서 자체의 목록(날짜/위치)은
`DOCS_INDEX.md`, 신규 문서 작성 규칙은 `CLAUDE.md` 참고. 오래되면 이 문서도 다시 갱신 필요 —
아래 각 항목이 가리키는 원본 문서의 날짜를 보고 신뢰도를 판단할 것.

---

## 1. UGV↔원격통제기(LIG) 프로토콜 — 거의 완료

UDP+JSON, LIG 정식 ICD(`protocol/lig_icd_ugv_rc_full.md`) 기준 구현 완료
(`protocol/ugv_rc_feature_gap_analysis.md`). **2026-08-28 LIG 1차 답변**
(`documents/response_0828.md`)으로 대부분의 불확실했던 부분 해소, `RC_ActivateMovement`
오매핑(차량 시동으로 잘못 구현했던 것 → RCWS 조향 게이트로 정정) 2026-08-31 재작업 완료.
남은 것: 자체방호축 PC 고정 IP, LIG에 보낼 후속 질문 3건(§12). 상세: `protocol/protocol_icd.md`
§3, `protocol/lig_questions_0816.md`.

## 2. 자체방호(이동형지휘소)축 로컬 통합 — 거의 완료

조이스틱 입력 → RCWS/UAV 짐벌 배선 완료(EO/IR, 발사모드, 장전, 안전/암, 축전환, 조준 브레이크
전부 연결·실측). 상세: `protocol/selfdefense_rc_feature_gap_analysis.md`.

## 3. RTSP 영상 송출 — 완료

UGV 5스트림 + 자체방호 7스트림(부가 1개 포함) 전부 실 카메라 연결, mount 확정
(`protocol/protocol_icd.md` §3.3/§4.1). 종단 지연 441~484ms → **68ms**로 최적화(수신측
GStreamer+NVDEC). 전송은 TCP interleaved만(UDP 아님). Linux 패키지 빌드 풀스크린 프레임 폭락
(11fps) 원인 규명·해결(Wayland/Xwayland 이슈). RTSP 스트림에 SSR/피격흔들림 안 나오던 문제
(SceneCapture가 메인 뷰포트와 다른 카메라라 `ReflectionMethod=None` 강제되던 것) 원인 규명,
해상도 커스터마이징+CCTV 잘림버그+RCWS 이중렌더링도 해결됨(2026-08-20,
`camera_pipeline/rtsp_postprocess_parity_0820.md`/`rtsp_resolution_customization_0820.md`).
상세: `rtsp/`, `camera_pipeline/`. **순수 Xorg 세션 검증 완료(2026-09-04)** — Wayland/Xorg 양쪽에서
시뮬레이터 실행 + RTSP 수신 확인, 세션 자동 판별 런처(`run_titan_example.sh`) 신설
(`packaging/2026-09-02_linux_package_ugv_host_rc_test_guide.md` §7-1). 남은 것: 자체방호축 6스트림
정밀 지연 재측정. **[2026-08-31 원인 확정+코드 수정 완료]** 자체방호축에서 RCWS
조준 이동 시 전장카메라/CCTV가 떨리는 버그, UGV 발사 반동이 자체방호축 카메라에도 리플리케이션
되는 버그(2-PC 환경) — `SceneCaptureViewParity`/`RCWSProjectile` 수정 완료
(`rcws/2026-08-31_selfdefense_camera_shake_bugs.md`), **2-PC 실환경 검증만 남음**.

## 4. 멀티플레이(리슨서버) 리플리케이션 — 거의 완료

기반 플러밍, RCWS(투사체 판정 서버 권위화 포함), 아군/적군 전투, UGV 구동, UAV까지 리플리케이션
완료 + 실기 테스트 통과. 상세: `replication/replication_audit.md` §0-1/§8.

## 5. 인게임 Settings 위젯 — Input 완료, Graphics 조사 단계

Input 탭 완료. Graphics 탭은 구현 전 전수 조사만 끝남(하드코딩 cvar, SceneCapture 설정,
CCTV 라운드로빈 캡처 등) — 위젯 구현은 아직. 상세: `ui/graphics_settings_analysis.md`,
`ui/ingame_settings_input_system.md`.

**2026-09-03 팔로업 + 실측 완료** — 조사 문서를 그동안의 변경(드론 교체, 프레임 상한 60 도입,
UGV BP 교체, `SceneCaptureViewParity` 재작성, 문서 재편)에 맞춰 갱신(`§0-2`). 계획 변동 2건:
**프레임레이트 상한은 물리 결정성 대책이라 탭에서 60 위로 못 올리게 해야 하고**, 창 모드는 실제
운용이 런치 인자(`-fullscreen`)라 후순위로 내림.

**선행 과제였던 cvar 우선순위 실측 완료**(`DumpCVars -csv` 전수 덤프, `§0-2 F`) — `sg.*` 12개가
전부 `SystemSettingsIni`로 고정돼 있어 **`UGameUserSettings` 품질 변경 경로는 완전 no-op**
(예상했던 "반만 먹는다"보다 나쁨). 우회하려면 `Scalability::SetQualityLevels(L, bForce=true)`.
렌더 스케일은 `r.ScreenPercentage` 직접 세팅으로 가능(1순위 후보 유지). VSync는 패키지에선
정상 동작하나 **에디터에서는 구조적으로 안 먹으니 검증을 패키지에서 할 것**.
**설계·스코프 확정**(문서 §9/§10): ini 하드코딩을 걷어내되 `sg.*`는 신규 `UTitanGraphicsSettings`
(`UDeveloperSettings`, `Config/DefaultGame.ini`)로, 개별 Lumen/VSM 튜닝은
`Config/DefaultScalability.ini`의 프리셋 재정의로 이관. 단일 소스라 **에디터/PIE/패키지가 구조적으로
일치**한다(엔진 기본은 에디터/게임이 서로 다른 ini를 읽어서 갈라짐).

**확정 스코프**: 품질 프리셋 전체(**그림자·GI·반사가 최우선**) + 카메라 캡쳐 주기(CCTV/드론/전장을
**따로** — 셋의 라운드로빈 메커니즘이 다르고 슬롯 엇갈림이 설계의 일부라 묶으면 깨짐) + AA 방식 +
VSync. **제외**: 프레임 상한, 창 모드(이미 최적), 레벨 PPV. **보류**: 렌더 스케일·캡쳐 해상도
(축/RTSP와 얽힘 — 캡쳐 해상도는 축 선택 화면 값과 실제로 겹침).
가장 비싼 남은 과제는 **"품질 4단계가 각각 뭘 의미하는가" 설계**(§10-5) — 현재 튜닝이 GI Medium/
Shadow High 단계에 종속돼 있어 단계를 바꾸면 무의미해진다. → 구현 착수 대기.

## 6. 레벨 디자인 / UGV 자율주행 — 2026-08-21~27 집중 작업, 대부분 완료

신규 레벨 `New_kadex_0811`(PCG 숲) 내비메시 인프라 구축, 성능 폭락 수정(2.3→31fps), 3단계
전투 시나리오 구현. UGV 자율주행: 커브 선행 감속, 궤도 잠금(오래된 "공중에 뜬 바퀴" 버그
해결), 장애물 회피(4가지 원인 규명, 실측 34.6km/h·조향포화 0회) 전부 완료. 상세:
`level_new_kadex_0811/`, `vehicle/ugv/` 폴더(파일별 날짜는 `DOCS_INDEX.md` 참고).

**2026-09-02~03 — UGV 차량 자체가 교체됐다.** 궤도 16륜 `BP_UGV_Vehicle_new` → 6×6 차륜
`BP_UGV_0901`(신규 모델·리깅·머티리얼·주행 튜닝 전부 실동작 확인). 이어서 09-03에 그 BP의
로직을 전부 C++ `AUGV0901Pawn`으로 내리고 죽은 노드 427개·변수 39개를 제거해
`.uasset`을 1,150KB → 67KB로 줄였다 — BP는 이제 컴포넌트와 튜닝 값만 든 데이터 에셋이다.
**UGV를 코드에서 찾을 때는 `BP_TestPlayerController.UGVVehicleClass`가 유일한 진입점**이고
지금 `BP_UGV_0901_C`를 가리킨다. 구형 `BP_UGV_Vehicle_new`는 폴백으로 남아 있다.

## 7. 적군/아군 AI·애니메이션·전투 — 2026-08-24~25 대규모 개편 완료, 분대 재편 검증 대기

로코모션 버그(시간 2배 흐름) 해결, 피격 리액션을 감쇠조화진동자 물리로 전면 교체, 3단계
전투 확장(Part A~G) 전부 완료(액티브 랙돌 사망, 전투지 3세트, 도주+타겟전환 캐스케이드).
**2026-08-31**: 적 15명을 5명씩 3분대로 재편(분대별 도주 경로/NavMesh 필터) — **PIE
재검증 대기**(`ai_combat/2026-08-31_enemy_squad_reorg.md`). 애니메이션 애셋 전수 목록(디자인팀
공유용)도 정리됨(`ai_combat/2026-09-01_animation_asset_inventory.md`). 상세: `ai_combat/` 폴더.

## 8. 피격 이펙트 — 완료

지형/바위/나무/PCG 전체 재질별 피격 이펙트(파티클/사운드/데칼) 배선 완료. 상세:
`sfx_vfx/hit_effects_update_2026-08-26.md`.

## 9. 드론(UAV) 물리 재구현 + 교전 관측 이동 — 완료, 2프로세스 검증만 남음

기존 운동학 근사 비행을 로터별 추력→토크→강체 운동 정통 모델로 전면 재구현
(`ADronePawn`). **2026-09-01 기준 구 `BP_UAV` 대체 작업까지 전부 완료** — 구동계·수동 조종
(실기 검증), 자율비행(스플라인 경로 추종, Pure Pursuit+제동곡선), 짐벌 카메라+자동 정찰,
프로펠러 사운드, 바람 반응, 단계별 탐지(아군 → +낙하산 → +적군), 시나리오 연동, RTSP
(`selfdefense/uav_gimbal`), 리플리케이션.

시나리오가 바뀌었다: **드론의 낙하산 관측 성공이 UGV 출발 트리거**가 됐다(예전엔 "UAV 적 감지").
적 탐색 단계와 아군 집결 대기는 제거됨. `DT_ScenarioSteps_ThreeStage`에 `DroneSeeEnemies`/
`DroneWideView` 행 신설.

리플리케이션은 **클라이언트(자체방호축) 권위** — 조종 주체가 그쪽이기 때문. Chaos
Resimulation은 RTSP 지연 +33ms와 UGV 거동 변화 때문에 기각
(`replication/2026-09-01_drone_client_authoritative.md`).

**2026-09-03~05 — 교전 관측 이동 추가, 실동작 확인 완료.** 교전이 시작되면 드론이 **활성 경로
스플라인 위에서 "전황을 가장 잘 보여주는 지점"으로 스스로 이동**한다(짐벌은 각도만 바꿀 뿐
거리를 못 줄이므로). 자유비행이 아니라 그려진 선 위에서만 고르는 구조라 지형 회피가 필요 없다.
프레이밍 대상은 시나리오 단계별로 정해지고 **레지스트리에서 직접** 읽는다 — 탐지 결과를 쓰면
`줌아웃→탐지해제→프레이밍축소→줌인` 순환 의존이 생긴다. 도주 중인 적은 대상에서 뺀다.

이 과정에서 유도 루프의 구조 결함 3연쇄를 해결했다(적분 와인드업 → 축별 안티와인드업 누락 →
**속도 피드포워드 부재로 인한 ζ=0.51 저감쇠 진동**). 경로 추종이 원래 부드러웠던 건 거버너
속도를 쓰는 이미 피드포워드 구조였기 때문이고, 관측만 순수 위치 피드백이라 6.8초 주기로
출렁였다. 겉보기 크기 필터(`MinScreenSizeFraction`)가 화각에 반비례해 교전 광각에서 탐지
사거리를 800m→45m로 무너뜨리던 버그도 같이 잡았다.

남은 것: **2대 PC 실환경 검증**, 그 후 구 `AUAVPawn`/`BP_UAV`와 폴백 분기 제거, 경로 고도
상향(부감이 선호 범위 -45~-60°를 못 채움 — 교전 반경 R 대비 R×1.0~1.25 위가 기준), 도주 시작
장면 프레이밍 개선(4단계 대상이 33개라 도주하는 적이 점으로 보임). 상세:
`vehicle/drone/drone_flight_dev_guide.md`(레퍼런스),
`vehicle/drone/2026-09-01_drone_replaces_bp_uav.md`·`2026-09-05_drone_engagement_observation.md`
(작업 경과).

## 10. 문서 관리 — 2026-08-31, 1단계 완료

여러 세션이 독립적으로 문서를 만들면서 폴더가 뒤섞인 문제를 해결 중. **1단계(구조 재편) 완료**:
`CLAUDE.md`(문서 작성 규칙: 파일명 날짜 접두, 1줄 헤더), `DOCS_INDEX.md`(전체 카탈로그),
`WORKLOG.md`(전체 작업 시간순 서사, 신규), `guide/` 폴더 신설(레퍼런스성 dev guide 9개를 이동,
전부 "최신화 필요" 경고 배너 부착 — **내용 자체는 아직 옛날 것**), 레거시/중복 문서 16개
`_archive/`로 이동, `structure/rc_gui/`(중복 코드)·`README_save.md` 삭제, `genesis/` 재정리.
기존 문서 대량 리네임(날짜 접두 소급 적용)은 상호 참조 깨짐 위험 때문에 안 함.

**2단계(아직 착수 전)**: `guide/`의 각 문서 내용을 실제 최신 코드/동작에 맞게 다시 쓰는 작업 —
시스템별(RCWS, UGV 주행, UI, 카메라 파이프라인 등)로 쪼개서 별도 세션 필요, 한 번에 다 하긴 큼.

## 11. 알려진 미해결 이슈 (요약, 상세는 각 원본 문서)

- 자체방호축 카메라 떨림/발사반동 누출 버그 — 코드 수정 완료, 2-PC 실환경 검증만 남음(§3).
- 적 3분대 재편 — 코드 구현 완료, PIE 재검증 대기(§7).
- 자체방호축 PC 고정 IP 미확정(LIG 확인 필요).
- `RC_MotionMode` 용도 불명(LIG도 "차후 논의", 급하지 않음).
- 자율주행 목적지 명령(`HQ_MissionMoveToEngage`)이 LIG 정식 스펙 아님, 확정 대기 중.
- 드론 2프로세스(2대 PC) 실환경 검증 대기 — 코드 완료, 단일 프로세스/PIE까지만 확인(§9).
- 구 `AUAVPawn`/`BP_UAV` 및 시나리오 폴백 분기 제거 — 위 검증 후 착수(§9).
- 살아있는 적이 이동 중 피격되면 몸이 회전하는 현상 — 재현 실패로 보류
  (`ai_combat/2026-09-01_enemy_spin_on_hit_investigation.md`).
- 버스트 사격 중 사격선(아군 관통) 재검사 없음 — 사격 시작 시점에만 검사
  (`ai_combat/2026-09-03_enemy_combat_fixes.md`).
- **리눅스 패키지가 GStreamer/NVIDIA 라이브러리를 `DT_NEEDED`로 직접 링크** — 타겟 머신에
  `libgstreamer-1.0.so.0`/`libgstapp-1.0.so.0`/`libgstrtspserver-1.0.so.0`/`libnvidia-encode.so.1`/
  `libcuda.so.1`이 없으면 **RTSP만 꺼지는 게 아니라 프로세스가 로더 단계에서 즉시 죽는다**(2026-09-03
  외부 테스터 실행 실패로 확인). nouveau/Mesa 머신은 실행 불가. 런타임 soft-fail(dlopen 전환)
  미착수 — `packaging/2026-09-02_linux_package_ugv_host_rc_test_guide.md` §3-1.
- **Vulkan ICD 미설치 시 `Failed to load Vulkan Driver`로 실행 불가** — `nvidia-smi`가 되고
  `libvulkan1`이 있어도 발생한다(로더 ≠ 드라이버). 검증은 `vulkaninfo --summary`로 해야 함.
  같은 문서 §7-1.
- Graphics Settings 위젯 실제 구현 미착수(§5).
- `guide/` 문서 내용 최신화 — 위 §10 2단계, 아직 시작 전.
- Unreal 에셋/코드 정리(레거시 BP, 폴더 구조) — 별도 세션 착수 예정, 아직 시작 전.

## 12. LIG에 발송 대기 중인 질문

`protocol/lig_questions_0816.md` §1 맨 위(1-신규-1~3) + §5(회신할 내용 2건, 아직 미발송) —
RC_OperationMode=EMERGENCY 레거시 가능성, 차량 시동 관련 커맨드 존재 여부, "LLM" 발언 확인,
NavMesh 기능 회신, ObjectClass 회신.

- **ObjectClass(§5-2)는 이제 질문이 아니라 "결정 통보"** — LIG가 Q10에서 우리 재량으로
  확정해준 항목이라 답변을 기다리지 않고 2026-09-02에 플랫 6값(`Ally`/`Enemy`/`UGV`/
  `MobileCommandPost`/`Drone`/`Parachute`)으로 확장 구현 완료. 남은 건 발송뿐, 답변 대기
  아님. 상세는 `protocol/2026-09-02_object_class_expansion.md`.
