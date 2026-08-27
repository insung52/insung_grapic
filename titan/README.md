# Titan (kadex 전시회 시뮬레이터) — 프로젝트 개요

카덱스(KADEX) 전시회 제출용 언리얼 엔진 기반 시나리오 씬 제작 프로젝트. 실제 코드는
`C:\working\kadex\titan_example`(UE5.8, Perforce 관리, git 아님). 이 문서는 프로젝트 구조와
지금까지의 작업을 다른 Claude 세션이 빠르게 파악할 수 있도록 정리한 인덱스.

전체 기능 명세/시나리오: `C:\private\titan\all.md` (참고용, 상세 스펙은 `documents/` 폴더의
PDF/PPTX 원본 참고).

**[2026-08-21] 이 README는 씬/캐릭터/카메라 등 게임플레이 개발 기록(`C:\private\titan\*`,
`C:\private\2026-W3x-황인성\*`) 위주로 유지되어 왔음 — 그 사이 별도로 진행된 LIG 원격통제기
프로토콜 연동/RTSP 송출/리플리케이션(멀티플레이)/인게임 설정 화면 작업 전체는
**`structure/README.md`**(트랙별 세션 분할 가이드, 여기가 그쪽 작업의 진짜 인덱스)와 그 폴더의
개별 문서들에 있음 — 아래 §3엔 반영 안 돼 있으니 그쪽 작업 관련이면 `structure/`부터 볼 것.
핵심만 요약하면:
- **UGV↔원격통제기(LIG) UDP+JSON 프로토콜**: 정식 ICD 확보 후 구현 완료
  (`structure/lig_icd_ugv_rc_full.md`, `structure/ugv_rc_feature_gap_analysis.md`).
- **자체방호(이동형지휘소)축 조이스틱 배선**: 완료(`structure/selfdefense_rc_feature_gap_analysis.md`).
- **RTSP 영상 송출(UGV 5스트림+자체방호 7스트림)**: 카메라 연결·지연 최적화(68ms)·Linux
  크로스플랫폼까지 완료(`structure/README.md` 트랙1, `structure/rtsp/`).
- **멀티플레이(리슨서버) 리플리케이션**: 거의 완료, 실기 테스트까지 통과(`structure/replication_audit.md`).
- **인게임 Settings 위젯**: Input 탭 완료, Graphics 탭 조사 단계
  (`structure/graphics_settings_analysis.md`).
- LIG에 확인 필요한 질문 전체는 `structure/lig_questions_0816.md`에 계속 누적 중(아직
  미발송).

---

## 1. 시뮬레이터 구성 — 무엇을 조작하는가

**듀얼 모니터** 세팅(`titan_exampleViewportClient`가 2개 이상 모니터 감지 시 보더리스 창으로
가상 데스크톱 전체를 덮음). 각 모니터에 별도 대시보드 UI(WBP) 표시.

**왼쪽 모니터** — Titan Palantir 이동형 지휘소(트럭) + RCWS + UAV
- `TitanTruck`: 이동 기능은 미구현, 4방향 감시 카메라(CCTV) + 자체방호용 RCWS 장착 (탄약 600발)
- `UAV`(드론): 수동 조종 불가, 시작 신호 수신 시 자동 이륙(5초/20m) → 목표 지점 직선 비행.
  카메라 각도만 사용자가 자유롭게 조작 가능. 적/낙하산 잔해 발견 시 bounding box.

**오른쪽 모니터** — UGV
- `UGV`(무인 전차): 대기/원격(수동)/자동주행 3모드, 목적지 수신 시 자동 경로 주행. 4방향 CCTV +
  RCWS 장착(탄약 1200발, 트럭보다 큼).

**RCWS**(무인 공격 포탑, `URCWSComponent` — TitanTruck과 UGV가 공유하는 컴포넌트): 자동 적 감지/
교전, 피아식별 bounding box, IR 모드, 장전/사격 상태 전환. 조이스틱으로 pan/tilt/zoom 조작.

레이아웃 목업: `C:\private\titan\path\truck.png`(왼쪽), `C:\private\titan\path\ugv.png`(오른쪽).
전체 요구사항 원문: `C:\private\titan\memo.md`.

---

## 2. 코드 구조 핵심 포인트

- `Source/titan_example/Vehicles/` — `TitanTruck`, `UGVPawn`, `UAVPawn`, `RCWSComponent`,
  `RCWSFireControlComponent`, `UGVMovementComponent`, `UGVAIController` 등 차량/무기 로직.
- `Source/titan_example/UI/` — `Monitor1Widget`(대시보드 C++ 베이스, WBP_kadex가 붙는 클래스),
  `Detection/` 하위 `TargetDetectionComponent`(피아식별 UV 투영 계산).
- `Source/titan_example/titan_examplePlayerController.h/.cpp` — 조이스틱 입력, 카메라 컨트롤
  타겟 전환(`ECameraControlTarget`: TruckRCWS/UGVRCWS/UAVGimbal), 대시보드 위젯 스폰.
- `Plugins/QuadCamModule/` — 4방향 CCTV 카메라를 재사용 가능한 플러그인으로 분리(`UQuadCamComponent`).
  다른 프로젝트에도 폴더째 복사해서 재사용 가능하도록 설계됨.
- **카메라 아키텍처 공통 패턴** (RCWS/QuadCam/UAV 전부 동일, 자세한 배경은 3절 문서 참고):
  디자이너는 `UCineCameraComponent`만 배치해서 렌즈/DOF/노출을 직접 튜닝하고, 코드가
  `BeginPlay`에서 실제 `USceneCaptureComponent2D`(또는 UGV RCWS의 경우 실제 메인 렌더링용
  `UCameraComponent`)를 그 옆에 자동 생성한다. CineCamera 자체는 절대 안 움직이는 순수 렌즈
  참조용.

---

## 3. 문서 인덱스 (주제별)

### 최근 작업 — 아군 액터 애니메이션 개편 (2026-08-04, 설계 단계)
- **`ally_character_animation_design.md`** ← `BS_Movement` 저속 슬라이딩 근본 원인
  (`AxisToScaleAnimation=BSA_None`, 수정 완료) 진단부터 시작해서, 상체 무기 자세(들고
  조준/내림) 토글, 웅크리기/무릎/엎드림 정리, 둘러보기 유휴 변주, 30명 동기화 문제까지
  다음에 구현할 아군 캐릭터 애니메이션 시스템 전체 설계. **아직 구현 전, 논의용 초안.**

### 최근 작업 — 시나리오 자동화 전면 정비 (2026-08-02~04, 진행 중)
- **`scenario_implementation_status.md`** ← **가장 최신, 이 폴더에서 제일 먼저 읽을 문서.**
  아군+UGV 동반 이동(포메이션/NavMesh 회피/RVO/물리적 안전망/UGV 에스코트 속도 제한),
  시나리오 스텝 테이블 전체 체인, UAV 카메라 자동 프레이밍, 적군 이동 버그, MCP 편집 툴의
  알려진 함정까지 전부 정리된 현재 상태 스냅샷. `시나리오.md`(#4-1~#4-8 스펙 원문),
  `ally_and_scenario_system_plan.md`/`scenario_datatable_system_plan.md`(초기 설계
  논의, 역사적 참고용)보다 우선.

### 최근 작업 — 씬캡쳐 vs 실제 렌더링 색감 불일치 (2026-07-24~26, 완전 해결)
- **`C:\working\insung_grapic\2026-W31-황인성\scenecapture_vs_realrender_color_investigation.md`**
  ← TitanTruck RCWS/UAV/QuadCam 씬캡쳐 화면이 실제 렌더링보다 색이 진하고 어둡게 나오던 문제,
  **완전히 해결됨**(사후 보정값 없이 완전 동일). 최종 원인 두 가지: (1) 엔진이 모든 씬캡쳐의
  Lumen GI/Reflections를 기본 OFF시킴, (2) 렌더타겟의 `GetDisplayGamma()`를 Slate(UI 표시)와
  톤매퍼(색상 계산)가 서로 반대 목적으로 읽어서 생기는 구조적 충돌 — 렌더타겟 프로퍼티가 아니라
  UMG에서 렌더타겟을 그리는 방식을 텍스처 브러시 → 머티리얼 브러시(`M_SceneCaptureDisplay`)로
  바꿔서 해결. 아래 4절의 "미해결 이슈" 항목이었던 것 — 이제 해결됨.

### 카메라 파이프라인 전반 (2026-07-21~23)
- **`C:\private\2026-W30-황인성\camera_pipeline_overhaul_2026-07.md`** ← 카메라 관련 종합
  정리본. CineCamera 아키텍처 통일, RCWS Lumen 버벅임 버그 → UGV RCWS를 씬캡쳐 대신 진짜 메인
  렌더링(`ULocalPlayer` 서브렉트)으로 전환, TitanTruck/UAV까지 확장 시도 후 롤백한 경위, 씬캡쳐
  지글거림(TAA 기본 꺼짐) 및 UAV 라이팅 버그 수정 등. **씬캡쳐-vs-실제렌더링 색감 불일치는 이
  문서(6절)에서 미해결로 남겨뒀었으나, 위 최신 문서에서 완전히 해결됨.**
- (참고용, 최신 문서로 대체됨) `C:\private\2026-W30-황인성\rcws_quadcam_uav_cinecamera_overhaul.md`,
  `rcws_lumen_scenecapture_stutter_investigation.md` — 위 종합 문서에 다 흡수됨, 개별 조회 불필요.

### 주행/AI
- **`path\ugv_obstacle_avoidance_2026-08-26.md`** ← **UGV가 자율주행 중 나무에 부딪히던 문제
  해결 기록(2026-08-26).** 원인이 네 겹이었다 — 조향 PI 게인 부족 / 커브 감속의 비물리적 각도
  매핑 / 뒤쪽 커브까지 세면서 생긴 과감속 / 도로 중앙 당김이 안전 여유를 깨뜨림. 나무 콜리전
  프록시를 에디터 버튼으로 재생성하는 툴(`ATreeCollisionProxyBuilder`)도 여기 있음.
- **`path\new_kadex_0811_navmesh_autonomous_driving.md`** ← **새 레벨(`New_kadex_0811`) 자율주행
  내비메시 작업, 이 주제에서 제일 먼저 읽을 문서 (2026-08-22).** PCG 숲 경계 스플라인으로 흙길을
  정의하고, 나무 콜리전 프록시 + `SplineNavModifier` 가중치 + 적군 전용 NavArea/쿼리 필터로
  구성한 3층 구조. 예전 레벨과 지형 구성이 달라 접근법이 통째로 다르니 아래 두 문서를 그대로
  따라 하면 안 됨.
- `path\ugv_navmesh_autonomous_driving_dev_guide.md` — (구 레벨 `kadex_demo_0716`) 도로 메시
  콜리전 생성 + `NavModifierVolume` 253개 스크립트 배치. 콜리전 프로파일 함정 등은 여전히 유효.
- **`path\ugv_corner_braking_dev_guide.md`** — 커브 선행 감속(제동 곡선, 2026-08-22). 경로 위
  나무 장애물을 회피 조향으로 지나가려다 부딪히던 문제 해결. 계단식 감속으로 만들었다가 갈아엎은
  과정과 최종 파라미터 표 포함.
- `C:\private\titan\path\ugv_driving_dev_guide.md` — UGV 주행 기능 구현 과정.
- `C:\private\titan\path\path.md` — 경로/이동 관련 메모.

### 카메라 조작 / 입력
- `C:\private\titan\path\joystick_camera_control_dev_guide.md` — 조이스틱 기반 카메라 조작
  (RCWS/UAV 짐벌 pan/tilt/zoom, 카메라 컨트롤 타겟 전환) 구현 과정.
- `C:\private\titan\quadcam_usage_guide.md` — QuadCamModule(4분할 CCTV) 사용법.

### 감지/교전
- `C:\private\titan\path\detection_dev_guide.md` — 피아식별 bounding box(`TargetDetectionComponent`) 구현.
- `C:\private\titan\rcws_fire_control_dev_guide.md` — RCWS 자동 조준/발사(`RCWSFireControlComponent`) 구현.

### UI/대시보드
- `C:\private\titan\path\ui_dev_guide.md` — WBP와 실제 액터 연결 과정. **주의: 최신화 안 되어
  있음** (원문 주석 그대로 유지).
- `C:\private\titan\mission_dashboard_widget_guide.md` — (레거시) `MissionDashboardWidget`/
  `WBP_test` 회귀테스트용 대시보드. 지금 실제 쓰이는 건 `Monitor1Widget`/`WBP_kadex`.
- `C:\private\titan\status_hud_dev_guide.md` — 상태 패널(UAV 배터리/고도/속도 등) 위젯.
- `C:\private\titan\minimap.md` — 미니맵(위성사진 느낌 씬캡쳐 + 아군/적군 마커) 관련 메모.
- `C:\private\titan\ui.md` — UI 스펙 메모.

### 좌표/실측 보정
- `C:\private\2026-W30-황인성\real2world_geo_calibration.md` — `GeoCoordinateUtils.h`의 나침반/
  방위각 좌우 반전 버그 수정 기록(2026-07-21 해결). 씬 스케일 ↔ 실좌표(위경도) 변환 보정 포함.
- `C:\private\titan\path\real2world.md` — 관련 메모.

### 차량/물리 (Chaos Vehicle)
- **`drone\drone_flight_dev_guide.md`** — **드론 비행 구동계 (2026-08-27 신규).** 로터 6개
  개별 추력 → 믹서 → Chaos 강체로 재구현(기존 `AUAVPawn`의 운동학 근사 폐기, 그쪽 코드는
  안 건드림). 수동 조종 완성/실기 검증 완료, 자율비행 미구현. 부호 규약·믹서 포화 처리·
  파라미터 튜닝 순서·테스트 레벨 코스 포함.
- `C:\private\titan\chaos.md`, `C:\private\titan\M1A2_UGV_Conversion.md` — UGV 물리 모델 관련.
- `C:\private\chaos\06_ugv_unreal_implementation_journal.md` — BP_UGV_Vehicle 빌드 전체 기록
  (Chaos 세팅, 트랙 처짐 물리 모델, Blender↔Unreal 스케일/회전 버그 및 수정).
- `C:\private\chaos\07_*` — RCWS 등 기능을 BP_UGV_Vehicle에 포팅한 기록.

### 기타 인프라
- `C:\private\titan\pixelstreaming_setup_guide.md` — 픽셀 스트리밍 세팅.
- `C:\private\titan\mcp\` — unreal-mcp/Claude Code 연동 관련 메모.

---

## 4. 알려진 미해결 이슈 (다음 세션에서 참고)

- **UGV 공중에 뜬 바퀴가 계속 회전** — deprioritized, 재조사 보류 요청 상태.
- QuadCam 4분할 CCTV의 라운드로빈 캡쳐 — **[2026-08-21 갱신] 착수됨**: `BP_UGV_Vehicle`의
  `CaptureRoundRobinCount` 프로퍼티로 실제 존재/튜닝된 상태(RTSP 지연 조사 중 2→1로 조정,
  `structure/rtsp/rtsp_latency_investigation.md` §2 #11) — 인게임 Settings 위젯 Graphics
  탭 후보로도 재조사됨(`structure/graphics_settings_analysis.md`). 위 "아이디어만 기록됨"은
  더 이상 최신 상태 아님.
- `ui_dev_guide.md`는 최신화 안 됨 — WBP 실제 구조와 다를 수 있음, 참고만 하고 실제 코드/에디터로 재확인 권장.

---

## 5. 다음 작업 예정 — 레벨 디자인 / UGV 자율주행 (참고용 시작점)

- 현재 자율주행 진입점: `SetUGVFromTankMode Auto` + `MoveUGVFromTankTo (X=...,Y=...,Z=...)`
  콘솔 명령(`titan_example/README.md` §2), 내부적으로 `AUGVAIController::MoveToDestination`.
  LIG 프로토콜에도 같은 경로가 `HQ_MissionMoveToEngage`(우리 임시 확장, 정식 LIG 스펙 아님)로
  얹혀 있음 — `structure/ugv_rc_feature_gap_analysis.md` §2-1.
- 주행/AI 관련 기존 기록: `C:\private\titan\path\ugv_driving_dev_guide.md`,
  `C:\private\titan\path\path.md`, 아군 동반 이동(포메이션/NavMesh 회피/RVO)은
  `scenario_implementation_status.md`.
- 자율주행 관련 알려진 갭(착수 전 참고): `RC_OperationMode`(STAY/REMOTE/EMERGENCY) ↔
  `EUGVDriveMode`(Idle/Manual/Auto) 매핑이 아직 우리 쪽에서도 완전히 정리 안 됨
  (`structure/protocol_icd.md` §3.2 하단), `Gear=Turn`(제자리선회) 판정 미구현,
  UGV/차량 쪽 `HasAuthority()` 게이팅·`physicsReplicationMode` 검토가 리플리케이션 작업에서
  아직 안 끝남(`structure/replication_audit.md`) — 레벨 디자인으로 주행 경로/장애물이 바뀌면
  이 리플리케이션 상태와 충돌 여부도 같이 점검 권장.
