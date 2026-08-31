# Titan (KADEX 전시회) — 현재 프로젝트 상태

2026-08-31 / 진행중 / 전체 시스템별 현재 상태 스냅샷 — 문서 정리 1차 작업의 산출물.

이 문서는 "지금 뭐가 어디까지 되어 있는가"만 다룬다. 문서 자체의 목록(날짜/위치)은
`DOCS_INDEX.md`, 신규 문서 작성 규칙은 `CLAUDE.md` 참고. 오래되면 이 문서도 다시 갱신 필요 —
아래 각 항목이 가리키는 원본 문서의 날짜를 보고 신뢰도를 판단할 것.

---

## 1. UGV↔원격통제기(LIG) 프로토콜 — 거의 완료

UDP+JSON, LIG 정식 ICD(`structure/lig_icd_ugv_rc_full.md`) 기준 구현 완료
(`structure/ugv_rc_feature_gap_analysis.md`). **2026-08-28 LIG 1차 답변**
(`documents/response_0828.md`)으로 대부분의 불확실했던 부분 해소, `RC_ActivateMovement`
오매핑(차량 시동으로 잘못 구현했던 것 → RCWS 조향 게이트로 정정) 2026-08-31 재작업 완료.
남은 것: 자체방호축 PC 고정 IP, LIG에 보낼 후속 질문 3건(§12). 상세: `structure/protocol_icd.md`
§3, `structure/lig_questions_0816.md`.

## 2. 자체방호(이동형지휘소)축 로컬 통합 — 거의 완료

조이스틱 입력 → RCWS/UAV 짐벌 배선 완료(EO/IR, 발사모드, 장전, 안전/암, 축전환, 조준 브레이크
전부 연결·실측). 상세: `structure/selfdefense_rc_feature_gap_analysis.md`.

## 3. RTSP 영상 송출 — 완료

UGV 5스트림 + 자체방호 7스트림(부가 1개 포함) 전부 실 카메라 연결, mount 확정
(`structure/protocol_icd.md` §3.3/§4.1). 종단 지연 441~484ms → **68ms**로 최적화(수신측
GStreamer+NVDEC). 전송은 TCP interleaved만(UDP 아님). Linux 패키지 빌드 풀스크린 프레임 폭락
(11fps) 원인 규명·해결(Wayland/Xwayland 이슈). 상세: `structure/README.md` 트랙1,
`structure/rtsp/`. 남은 것: 자체방호축 6스트림 정밀 지연 재측정, 순수 Xorg 세션 검증.

## 4. 멀티플레이(리슨서버) 리플리케이션 — 거의 완료

기반 플러밍, RCWS(투사체 판정 서버 권위화 포함), 아군/적군 전투, UGV 구동, UAV까지 리플리케이션
완료 + 실기 테스트 통과. 상세: `structure/replication_audit.md` §0-1/§8.

## 5. 인게임 Settings 위젯 — Input 완료, Graphics 조사 단계

Input 탭 완료. Graphics 탭은 구현 전 전수 조사만 끝남(하드코딩 cvar, SceneCapture 설정,
CCTV 라운드로빈 캡처 등) — 위젯 구현은 아직. 상세: `structure/graphics_settings_analysis.md`,
`ingame_settings_input_system.md`, `structure/README.md` 트랙7.

## 6. 레벨 디자인 / UGV 자율주행 — 2026-08-21~27 집중 작업, 대부분 완료

신규 레벨 `New_kadex_0811`(PCG 숲) 내비메시 인프라 구축, 성능 폭락 수정(2.3→31fps), 3단계
전투 시나리오 구현. UGV 자율주행: 커브 선행 감속, 궤도 잠금(오래된 "공중에 뜬 바퀴" 버그
해결), 장애물 회피(4가지 원인 규명, 실측 34.6km/h·조향포화 0회) 전부 완료. 상세:
`newlevel/`, `path/` 폴더(파일별 날짜는 `DOCS_INDEX.md` 참고).

## 7. 적군/아군 AI·애니메이션·전투 — 2026-08-24~25 대규모 개편 완료

로코모션 버그(시간 2배 흐름) 해결, 피격 리액션을 감쇠조화진동자 물리로 전면 교체, 3단계
전투 확장(Part A~G) 전부 완료(액티브 랙돌 사망, 전투지 3세트, 도주+타겟전환 캐스케이드).
상세: `soldiers/` 폴더.

## 8. 피격 이펙트 — 완료

지형/바위/나무/PCG 전체 재질별 피격 이펙트(파티클/사운드/데칼) 배선 완료. 상세:
`hit_effects/hit_effects_update_2026-08-26.md`.

## 9. 드론(UAV) 물리 재구현 — 구동계 완료, 자율비행 남음

기존 운동학 근사 비행을 로터별 추력→토크→강체 운동 정통 모델로 전면 재구현, 기존
`AUAVPawn`과 완전 분리. 구동계+수동 조종 완성·실기 검증. 자율비행은 미착수. 상세:
`drone/drone_flight_dev_guide.md`.

## 10. 문서 관리 — 2026-08-31 착수

여러 세션이 독립적으로 문서를 만들면서 폴더가 뒤섞임 — `CLAUDE.md`(문서 작성 규칙: 파일명
날짜 접두, 1줄 헤더)와 이 두 인덱스 문서(`CURRENT_STATE.md`, `DOCS_INDEX.md`)를 신설해서
관리 시작. 기존 문서 대량 리네임은 상호 참조 깨짐 위험 때문에 아직 안 함(별도 확인 후 진행).

## 11. 알려진 미해결 이슈 (요약, 상세는 각 원본 문서)

- UGV 공중에 뜬 바퀴 관련은 해결됨(§6) — README에 남아있던 옛 기록은 갱신 필요.
- 자체방호축 PC 고정 IP 미확정(LIG 확인 필요).
- `RC_MotionMode` 용도 불명(LIG도 "차후 논의", 급하지 않음).
- 자율주행 목적지 명령(`HQ_MissionMoveToEngage`)이 LIG 정식 스펙 아님, 확정 대기 중.
- UAV 가속/감속 곡선 부자연스러움, 미니맵 좌표 오차, 피격음이 항상 UGV 위치에서 나는 버그,
  Linux 조이스틱 미작동/듀얼모니터 풀스크린 간헐 실패(`memo.md` 백로그).
- Graphics Settings 위젯 실제 구현 미착수(§5).
- Unreal 에셋/코드 정리(레거시 BP, 폴더 구조) — 별도 세션 착수 예정, 아직 시작 전.

## 12. LIG에 발송 대기 중인 질문

`structure/lig_questions_0816.md` §1 맨 위(1-신규-1~3) + §5(회신할 내용 2건, 아직 미발송) —
RC_OperationMode=EMERGENCY 레거시 가능성, 차량 시동 관련 커맨드 존재 여부, "LLM" 발언 확인,
NavMesh 기능 회신, ObjectClass 세분화 회신.
