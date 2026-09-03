# 고사실감 병사 AI/애니메이션 R&D — 아키텍처 설계

2026-09-01 / 설계 확정·프로젝트 생성 대기 / 병사 개개인이 환경·적·아군을 실시간으로 판단해 엄폐/사격/기동하고 분대로 협동하는 시스템의 전체 설계 — UE5.8 네이티브 스택(Motion Matching + StateTree + Smart Objects + EQS) 기반, 스켈레톤을 UE5 Mannequin 규격으로 전면 교체, 애니메이션은 **풀바디 베이스 + 절차적 워핑**(상하체 레이어 분리 폐기), 상위 시나리오는 고수준 "명령"만 내리는 구조.

> **폴더 규칙·진행 상황·미해결 항목**: `../CLAUDE.md` · `../CURRENT_STATE.md` · `../OPEN_ITEMS.md`
>
> **개정 이력**
> - 2026-09-01 초안 — 8개 요구항목 전체 설계
> - 2026-09-01 개정 1 — 3절 전면 재작성. 스켈레톤 실측 결과(Mixamo·Root 본 없음)에 따라 UE5
>   Mannequin 규격 전면 교체 확정, 기존 애니메이션 자산 미승계, GASP 조달/프로젝트 생성 절차서 추가
> - 2026-09-01 개정 2 — **5.5절 결론 뒤집음.** "하체 MM + 상체 레이어 블렌드" 하이브리드를 폐기하고
>   **풀바디 베이스 + Orientation Warping + additive 보정**으로 교체(5.5.1~5.5.5). 5.6(지형·환경
>   연동 파이프라인) / 5.7(연구 기술) / 5.8(기성 구현체) 신설, 6.1절을 GASP 5.8 Look-At 솔버 기반으로
>   재작성, P0-2(견착 워핑 검증) 추가
> - 2026-09-01 개정 3 — 착수 전 문서 검토에서 발견된 **구조적 누락 4건 반영**:
>   **4.3 권위/리플리케이션**(초안에 통째로 없었음 — titan_example이 리슨서버 멀티플레이),
>   **6.5 피격·부상·사망**(MM 중단 방식 + `EHealthState` + 사망 정리 체크리스트),
>   **3.7.1 아군/적군 단일 코드 원칙**, **5.5.6 조준 한계각과 재정렬(re-plant)**.
>   나머지 미비점 9건은 15.3절에 설계 백로그로 등록

> 이 문서는 **별도 언리얼 프로젝트**(`C:\working\works\kadex\` 밑, 3절 참고)에서 진행할 R&D의
> 설계 원본이다. 코드는 `titan_example`이 아닌 신규 프로젝트에 들어가지만, 검증된 기법은
> 나중에 `titan_example`로 이식할 것을 전제로 설계했다(엔진 버전 UE5.8 동일).
>
> **후속 문서 (전부 2026-09-02, 착수 전 같이 볼 것)**
> - `../assets/2026-09-02_asset_supply_and_collaboration.md` — 자산 조달(3.8절 대체) + 디자인팀 협업/공유 시점
> - `../animation/2026-09-02_gasp_abp_analysis.md` — **GASP 애님BP 전수 분석.** 노드 위상·설정값·인과 맵·
>   삽입 지점·확장 판정. "무엇을 건드리면 무엇이 바뀌는가"의 지도
> - `../animation/2026-09-02_pose_pipeline_spec.md` — **애니메이션 층(L4) 명세.** 축별 정의·합성 순서·
>   권한 규칙·`FSoldierPoseIntent` 계약·필요 앵커 산정. **5·6절을 대체·심화**
> - `../ai/2026-09-02_upper_layer_plan.md` — 상위 층(L0~L3) 구조 계획·계층 간 계약·구현 순서
>
> 선행/관련 문서:
> - `../../ai_combat/ally_ai_combat_system_status.md` — 현행 아군 AI(`UAllyFormationComponent`)
> - `../../ai_combat/enemy_ai_combat_system_status.md` — 현행 적군 AI(`UEnemyCombatComponent`)
> - `../../ai_combat/2026-08-31_enemy_squad_reorg.md` — 분대/도주 경로/시나리오 트리거 현황
> - `../../level_new_kadex_0811/scenario_three_stage_combat.md` — 시나리오 DataTable 스텝 구조

---

## 목차

1. [문제 정의 — 지금 무엇이 부족한가](#1-문제-정의--지금-무엇이-부족한가)
2. [레퍼런스 조사](#2-레퍼런스-조사)
3. [프로젝트 셋업 (신규 UE5.8 프로젝트)](#3-프로젝트-셋업-신규-ue58-프로젝트) ← **자산/리그 전략 + 실행 절차서**
4. [전체 아키텍처 — 5개 레이어](#4-전체-아키텍처--5개-레이어) ← **4.3 권위/리플리케이션**
5. [로코모션](#5-로코모션-요구항목-1) ← **5.5 조준 자세 / 5.6 지형·환경 연동 / 5.7 연구기술 / 5.8 기성 구현체**
6. [사격/무기 처리](#6-사격무기-처리-요구항목-2) ← **6.5 피격·부상·사망**
7. [인지(Perception)](#7-인지perception-요구항목-3)
8. [개별 판단(의사결정)](#8-개별-판단의사결정-요구항목-4)
9. [분대/팀 협동](#9-분대팀-협동-요구항목-5)
10. [엄폐 시스템](#10-엄폐-시스템-요구항목-6)
11. [명령 인터페이스](#11-명령-인터페이스-요구항목-7)
12. [성능/스케일 목표](#12-성능스케일-목표-요구항목-8)
13. [의도적으로 채택하지 않은 것들](#13-의도적으로-채택하지-않은-것들)
14. [구현 로드맵과 검증 프로토타입 제안](#14-구현-로드맵과-검증-프로토타입-제안)
15. [결정 사항 및 남은 질문](#15-결정-사항-및-남은-질문) ← **15.3 설계 백로그(D1~D9)**
16. [참고 자료 목록](#16-참고-자료-목록)

---

## 1. 문제 정의 — 지금 무엇이 부족한가

### 1.1 현행 시스템의 실제 구조

`titan_example`의 병사 AI는 `UAllyFormationComponent`(1856줄) / `UEnemyCombatComponent`(2144줄)
두 개의 액터 컴포넌트에 들어 있고, 구조는 이렇다:

```
최상위 상태머신(적: Move → Combat → Flee)
   └─ 자세 사이클(4단계): Cover → TransitioningToFiring → Firing → TransitioningToCover
         └─ 각 상태의 목표 위치 = 레벨에 사람이 손으로 꽂아둔 마커 액터
              (FiringPose.Marker / CoverPose.Marker / NoTargetPose.Marker / EngagePoint / ExfilPoint)
```

이 구조는 **잘 동작한다.** 조준 보정(총구 기준 Yaw/Pitch), 버스트 사격, 거리 비례 전환 타임아웃,
탄 퍼짐, 사격선 안전장치, RVO + 겹침 밀어내기까지 실전 버그를 다 밟고 안정화된 코드다. 문제는
품질이 아니라 **표현력의 상한**이다.

### 1.2 상한이 어디서 오는가 — 4가지 구조적 제약

| # | 제약 | 구체적 증상 |
|---|---|---|
| C1 | **전술 위치가 데이터가 아니라 저작물** | 엄폐 위치를 병사가 "고르는" 게 아니라, 사람이 마커를 꽂아둔 곳으로 "간다". 적이 예상 밖 방향에서 오면 그 마커는 더 이상 엄폐가 아니지만 병사는 계속 그리로 간다. 레벨이 바뀌면 전부 다시 꽂아야 한다. |
| C2 | **판단이 없고 순서만 있다** | `Cover → Firing → Cover`는 타이머와 도착 판정으로만 넘어간다. "지금 쏘는 게 유리한가", "전진할 때인가"를 평가하는 지점이 코드 어디에도 없다. 랜덤 대기 시간(2~4초)이 "판단"의 자리를 대신하고 있다. |
| C3 | **아군끼리 아무것도 공유하지 않는다** | 각자 자기 스피어 오버랩으로 적을 찾고 각자 쏜다. 협동으로 보이는 것(대형, 사격선 회피)은 전부 기하학적 규칙이지 정보 공유가 아니다. 한 명이 본 적을 옆 사람은 모른다. |
| C4 | **시나리오가 개별 행동을 직접 트리거한다** | `EScenarioEffectType`이 28개 verb의 평면 enum인데, 그 내용이 `MoveUGVToZone2Destination`, `BeginEnemyFleeZone3`, `RetargetEnemiesToCommandPost`처럼 **대상·행동·목적지가 전부 하드코딩**돼 있다. 새 연출 하나 = enum 하나 + C++ 분기 하나. |

목표는 이 네 가지를 각각 다음으로 바꾸는 것이다:

- C1 → **환경에서 실시간으로 뽑는 전술 지점**(Smart Object + EQS)
- C2 → **유틸리티 기반 의도 선택기**(매 판단 틱마다 후보 행동을 점수화)
- C3 → **분대 blackboard + 역할 배분**(정보 공유와 슬롯 할당)
- C4 → **명령 스키마**(무엇을 원하는지만 내리고, 어떻게는 병사가 정함)

### 1.3 애니메이션 쪽 상한

현행은 `ABP_Ally_kadex2`의 블렌드스페이스 + 상태머신 + 수동 IK 조합이다. 여기서 나온 실제 버그
목록(속도 정규화가 1을 넘음, 감속 램프가 분모를 같이 줄여서 절대속도 정보 소실, `Direction`
미충전으로 스트레이프 방향 반대)은 전부 **"애니메이션이 실제 이동을 따라가게 만드는 배관"을
사람이 손으로 짜고 있어서** 생긴 것이다. Motion Matching은 정확히 이 배관을 없애는 기술이다 —
포즈 선택 기준이 "속도 비율 float"가 아니라 "과거 궤적 + 미래 궤적 + 현재 포즈"이기 때문에,
감속/가속/방향전환이 데이터에서 자동으로 나온다.

---

## 2. 레퍼런스 조사

### 2.1 전술 AI 계보 — 무엇을 어디서 가져올 것인가

| 레퍼런스 | 핵심 기법 | 이 프로젝트에 가져올 것 | 가져오지 않을 것 |
|---|---|---|---|
| **F.E.A.R.** (2005, Jeff Orkin, GDC 2006 "Three States and a Plan") | 상용 최초 GOAP. FSM은 단 3상태(Animate/GoTo/UseSmartObject)로 두고, 그 위에서 A*로 **액션 시퀀스를 계획**. 분대는 "제압사격 담당 / 전진 담당"으로 역할을 나눠 동시에 움직임 | ① **FSM을 얇게 유지**한다는 원칙(상태 폭발 방지) ② 분대 행동을 "역할 배분"으로 표현 ③ 스마트오브젝트가 행동을 들고 있는 구조(UE Smart Objects와 같은 계보) | GOAP 플래너 자체 — 8절 참고 |
| **Killzone 2/3** (Guerrilla, GDC/AIGameDev, Game AI Pro Ch.29) | 계층형: **전략(commander) → 분대(HTN 플래너) → 개인(HTN)**. 분대 플래너가 위치/경로 질의를 돌려 **전략 경로를 "회랑(corridor)"으로 내려주고**, 개인은 그 회랑 안에서 자율 판단. 초당 500 플랜 | ① **회랑 개념** — 분대는 영역을 주고 개인이 그 안에서 위치를 고른다(11절 명령 스키마의 `AreaConstraint`) ② 3계층 분리 | 도메인 독립 HTN 플래너 전체 구현(과함) |
| **Killzone 1** (Straatman, "dynamic procedural combat tactics") | 웨이포인트/지형 주석 기반 전술 위치 평가 + 절차적 분대 전술(측면, 제압, 후퇴) | 지형 주석 아이디어 → UE에서는 Smart Object 슬롯 + EQS로 대체 | 웨이포인트 그래프(NavMesh가 대체) |
| **Days Gone** (Bend, GDC 2021 "Squad Coordination in Days Gone") | **분대를 런타임에 동적으로 생성**. 아군/적군 위치로 "아군 공간 / 적군 공간"을 분석해 분대를 배치. **분대 사기(morale) 수치가 분대 행동을 구동**. 레벨 저작 툴과 통합 | ① **동적 분대 생성**(사전 배정이 아니라 근접/시야로 묶기) ② **사기 수치**를 분대 레벨 상태로 채택(9절) ③ 공간 분석 → 영향맵(influence map) 경량 버전 | 오픈월드용 대규모 무리(horde) 관리 |
| **The Last of Us / Part II** (Naughty Dog, GDC 2014·2021) | 컨텍스트 인지 대화 시스템(개인 지식/집단 지식/월드 상태 구분), 동료 AI의 "살아있음" 연출, 적의 점진적 인지 | ① **개인 지식 vs 분대 공유 지식을 명시적으로 분리**(7절) ② 점진적 인지(awareness 누적) | 대사/보이스 시스템(범위 밖) |
| **Escape from Tarkov** (BSG, 2024~2025 AI 패치) | 우선순위 **레이어드 비헤이비어 트리**. 감지가 이산적이지 않음 — 거리·각도(주변시야)·날씨에 따라 **인지까지 걸리는 시간**이 달라지고, 시야를 벗어나도 **점진적으로** 잃음. 청각은 자기 체력/이동/벽/날씨에 영향받음 | ① **"감지 = 시간이 걸리는 과정"** 모델을 그대로 채택 ② 청각 감쇠에 차폐 반영 | 레이어드 BT 구조(우리는 유틸리티+StateTree로) |
| **Ready or Not** (VOID, 1.0 SWAT AI) | 4종 대형(single/double file, diamond, wedge), 스택업/브리칭, 상황별 비살상 선택 | 대형을 **명령 파라미터**로 노출(11절) | 실내 CQB 전용 로직 |
| **Arma 3 / Squad** | 분대장→팀→개인의 명령 위임, **바운딩 오버워치**(한 조가 엄호하는 동안 다른 조가 전진) | ① 바운딩 오버워치를 분대 전술 플랜 템플릿으로 ② 명령 위임 계층 | 시뮬레이터급 탄도/부상 모델 |
| **Six Days in Fallujah** (Highwire) | 절차적 건물 생성 + 그에 대응하는 **"블록 스케일 AI"** — 맵이 매번 달라도 AI가 스토킹/측면/매복을 함 | **"AI가 레벨 저작에 의존하지 않는다"**는 목표 자체. 우리 C1 제약의 정확한 반대편 사례 | 절차적 건축 |
| **Game AI Pro Ch.26** — Tactical Position Selection (Matthew Jack, Crytek) | 전술 위치 질의어: **Generation(후보 생성) → Conditions(필터, 전부 통과해야 유효) → Weights(0~1 정규화 후 가중합)** 3단 구조 | **UE EQS가 정확히 이 구조**다(Generator/Test/Score). 질의 설계 원칙을 그대로 차용(10절) | 자체 DSL 구현 |
| **GDC "Believable Tactics for Squad AI"** (Champandard/Jack/Dunstan) | 분대 동기화의 **중앙집중 설계 vs 분산 설계** 트레이드오프, 측면기동/제압/유도 | **하이브리드 채택 근거**(9절) — 분대는 슬롯만 배분, 실행은 분산 | — |
| **Dave Mark, IAUS** (GDC 2013 "Architecture Tricks") | 무한축 유틸리티: 행동마다 여러 "축"의 점수를 곱/가중합, 커브를 튜닝해서 행동 조정. FSM처럼 깨질 관계가 없어 **행동 추가가 기존을 안 부순다** | **개별 판단의 본체로 채택**(8절) | 완전 IAUS 프레임워크(경량 구현으로) |
| **DOOM (2016)** (id, GDC 2018 "Bringing Hell to Life") | AI 결정과 **풀바디 애니메이션 선택을 같은 층에서** 다룸 — 행동이 곧 애니메이션 | 행동↔애니메이션 계약을 명시적으로 두는 설계(5·6절의 Action ↔ Motion 계약) | — |

### 2.2 애니메이션 계보

| 레퍼런스 | 배울 점 |
|---|---|
| **The Last of Us Part II** (GDC 2021, Mach/Zhuravlov) | 풀바디 Motion Matching으로 최고 수준 도달. 동시에 **"수백~수천 클립을 잘게 썰어 넣어야 커버리지가 나온다"**는 비용도 같이 공개됨 — 초기엔 기쁨, 중반엔 좌절. → 우리처럼 클립 예산이 작은 프로젝트는 **풀바디 MM 전면 채택이 함정**이라는 근거 |
| **Epic Game Animation Sample (GASP)** — UE5.4 도입, **5.8용 업데이트본 존재** | 다중 Pose Search 데이터베이스 + Chooser 기반 DB 스와핑의 **레퍼런스 구현**. 우리 프로젝트의 출발 베이스. **단 내용은 비무장 로코모션 + 트래버설까지이고 라이플 조준 자산은 없다**(3.2·3.8절) |
| **GDC "Fitting the World: A Biomechanical Approach to Foot IK"** | 발 배치를 "본을 지면에 붙이기"가 아니라 **생체역학적 자세 보정**으로 다루는 접근 — 경사/계단/장애물 위 자세의 근거 |
| **GDC "IK Rig: Procedural Pose Animation"** | 절차적 포즈 수정의 구조. UE의 IK Rig/Retargeter가 이 계보 |
| **GTA V / RDR2 (Euphoria/NaturalMotion)** | 물리 기반 반응의 상한선. 우리는 **피격 반응에만 한정**해서 참고(현행 `../../ai_combat/enemy_hit_reaction_physics_system.md`가 이미 이 방향) |
| **Environment-aware Motion Matching** (Ponton 외, ACM TOG / SIGGRAPH Asia **2025**) | 환경 충돌을 **매칭 비용의 페널티**로 넣어 자세와 궤적을 동시에 적응시킴. "애니메이션이 지형과 연동된다"의 학술적 최신형 — 개념 차용(5.7절) |
| **Learned Motion Matching** (Holden 외, Ubisoft 2020) | MM 데이터베이스를 신경망으로 압축(590MB → 8.5MB). DB가 커졌을 때의 대비책(5.7절) |
| **Advanced Third Person Shooter Project** (Fab 상용) | MM + 조준 + 엄폐 AI를 실제로 통합한 상용 구현. **ProPose**(절차적 풀바디 포즈 조정)가 우리 접근과 같은 계열 — 뜯어볼 가치(5.8절) |

### 2.3 UE5.8 네이티브 스택 — 로컬 엔진 실사 결과

`C:\Program Files\Epic Games\UE_5.8\Engine\Plugins`의 `.uplugin` 메타데이터를 직접 읽어
성숙도를 확인했다(웹 문서보다 이쪽이 정확하다):

| 플러그인 | 5.8 상태 | 우리 용도 | 채택 |
|---|---|---|---|
| **PoseSearch** (Motion Matching) | 정식 (Experimental/Beta 플래그 없음). 5.8에서 **Pose Search Interaction Assets** 추가 — 여러 스켈레탈 메시 간 포즈 검색 + 모션워프 접점 정렬(`Motion Match Multi`) | **풀바디** 로코모션 전체 + 다인/물체 상호작용 | ✅ 핵심 |
| **BlendStack** | 정식 | MM의 다중 블렌드 관리 | ✅ (MM 필수 동반) |
| **AnimationWarping** (= Pose Warping 노드군) | 정식 (Stride/Orientation/Slope + Root Motion Delta). ⚠ 단 공식 문서가 **Slope Warping은 "개발 중이니 프로젝트를 여기 의존하지 말 것"**, Stride Warping도 "아직 다듬는 중"으로 표기 | **Orientation Warping이 이 설계의 핵심 부품**(5.5.2절) — 조준방향/이동방향 분리, 8방향 클립 조합 폭발 방지 | ✅ 핵심 |
| **PhysicsControl / ControlRigPhysics** | 5.7에서 별도 플러그인으로 분리. Control Rig Physics는 5.8에서 **Beta** 승격(+ Control Rig Dynamics로 5배 성능 개선) | 피격 반응, 장구류 물리 | ⏸ 2차 |
| **Chooser** | 정식 | 상황별 MM 데이터베이스 스와핑(서있기/앉기/부상/무기별) | ✅ |
| **AnimationModifierLibrary** | 정식. `UEncodeRootBoneModifier`(가중 본으로부터 루트 위치/회전 인코딩), `UCopyBonesModifier`, `UZeroOutRootBoneModifier`, `UMotionExtractorModifier` 등 보유 | **인플레이스 무료 클립을 루트모션 클립으로 변환** — 조달 전략의 핵심 도구(`../assets/2026-09-02_asset_supply_and_collaboration.md` 4절) | ✅ **핵심** |
| **FullBodyIK** | 정식 | Control Rig 안의 풀바디 IK 솔버 | ✅ |
| **ControlRig / IKRig** | 정식 | 발 배치, 손 IK, 상체 조준 보정 | ✅ 핵심 |
| **SmartObjects** | 정식 (Experimental 플래그 없음) — **예약(reservation) 시스템 내장** | 엄폐 슬롯, 상호작용 지점 | ✅ 핵심 |
| **StateTree / GameplayStateTree** | 정식. 5.8에서 시작 상태 지정·컴파일러 매니저·양방향 프로퍼티 바인딩 추가 | 선택된 의도의 **실행** | ✅ 핵심 |
| **AIModule (EQS, AIPerception, NavMesh, Detour Crowd)** | 정식. 5.8에서 스태틱메시별 NavArea 비용 지정 추가 | 전술 질의, 인지, 경로 | ✅ 핵심 |
| **MotionTrajectory** | ⚠️ Experimental (v0.1) | MM 질의용 궤적 생성 | ⚠️ 채택하되 **자체 래핑**(11절 위험) |
| **ContextualAnimation** | ⚠️ Experimental | 다인 상호작용(부축, 제압) | ⏸ 2차 |
| **MotionWarping** | 정식 | 엄폐 진입/장애물 넘기 시 정확한 접점 정렬 | ✅ |
| **Mover / ChaosMover** | ⚠️ Experimental (5.8에서 크게 개선, 아직 미졸업) | CharacterMovementComponent 대체 | ❌ 이번엔 안 씀(13절) |
| **UAF/AnimNext** | ⚠️ Experimental (v0.1) | 차세대 애니메이션 프레임워크 | ❌ 이번엔 안 씀(13절) |
| **MassEntity/MassAI/MassCrowd/ZoneGraph** | ⚠️ Experimental (MassAI v0.4, ZoneGraph v0.5). 5.8에서 Mass Signals가 코어로 편입되고 프로세서 실행 대폭 개편 | 수천 단위 에이전트 | ❌ 이번엔 안 씀(13절) |
| **HTNPlanner** | 존재하되 사실상 샘플 수준 | — | ❌ |
| **AnimationBudgetAllocator / SignificanceManager / AnimationSharing** | 정식 | 다수 캐릭터 애님 비용 제어 | ✅ 12절 |

**결론**: "사실적인 병사 하나"를 만드는 데 필요한 UE5.8 부품은 **전부 정식 등급으로 존재한다.**
실험적 등급인 것들(Mass/Mover/AnimNext/ZoneGraph)은 전부 "수천 명" 또는 "차세대 프레임워크"
쪽이고, 우리 목표(수십 명 × 고품질)에는 필요 없다. 이게 이 설계의 가장 중요한 전제다.

---

## 3. 프로젝트 셋업 (신규 UE5.8 프로젝트)

> **이 절은 사용자가 직접 실행하는 절차서다.** 2026-09-01 확정 사항: 스켈레톤 규격을 UE5
> Mannequin으로 교체하고, `titan_example`의 기존 병사 애니메이션 자산은 **승계하지 않는다**.

### 3.0 확정된 자산/리그 전략 (2026-09-01 결정)

#### 결정 1 — 스켈레톤 규격을 UE5 Mannequin으로 교체

현행 `titan_example` 병사 스켈레톤(`Rifle_Aiming_Idle_Skeleton`)을 실측한 결과:

```
Hips → Spine → Spine1 → Spine2 → Neck → Head ...        (mixamorig: 접두어)
Root 본: 없음        IK 본(ik_foot_root / ik_hand_gun 등): 없음
```

**Mixamo 리그이며 지면 높이의 Root 본이 존재하지 않는다.** 그 결과:

| 문제 | 영향 |
|---|---|
| Root 본 없음 → 루트모션 불가 | **Motion Matching이 원천적으로 불가능.** MM의 검색 질의는 루트 본의 과거/미래 궤적이고, Epic 문서가 "로코모션 클립은 루트모션을 포함해야 하며 Root Motion 속성이 켜져 있어야 한다"고 명시. 인플레이스 클립은 궤적이 전부 0이라 "걷는 클립"과 "선 클립"이 구분되지 않는다 |
| Hip이 루트 역할 | 발 IK의 골반 하강 보정, Animation Warping의 Root Motion Delta가 전제를 잃음 |
| `ik_hand_gun` / `ik_foot_root` 없음 | 무기 부착·왼손 IK·발 IK가 엔진 표준 규약을 못 씀 → 현행처럼 총 액터 상대회전을 매 틱 수동 보정하는 배관이 계속 필요 |
| Mixamo 생태계 | 사실상 동결. 신규 클립 공급이 없고 전부 Root 본이 없어 MM 시대에 구조적으로 부적합 |

→ **UE5 Mannequin(UEFN_Mannequin) 규격을 표준으로 채택한다.** `root → pelvis → spine_01~05`
+ `ik_foot_root`/`ik_hand_root`/`ik_hand_gun` 표준 IK 본을 갖는 계층. 이것이 GASP·Lyra·Fab
마켓·Control Rig 기본 자산·IK Rig 프리셋이 전부 전제하는 규격이다.

#### 결정 2 — 기존 애니메이션 자산은 전량 승계하지 않는다

`Content/Soldiers/AnimationSequences/`의 50개(Aim Walk 8방향, Crouch Aim Walk 8방향, Jog
8방향, Cover Pop-up/down, Weapon Raise/Lower, Turn 등)는 **가져오지 않는다.**

- 로코모션 루프는 루트모션이 없어 MM DB에 넣을 수 없다.
- 제자리 전환 동작(Cover Pop-up/down, 수신호 등)은 리타깃하면 기술적으로 살릴 수 있으나,
  **리그가 다른 자산이 섞이면 추적이 어려워진다**는 판단으로 전량 신규 조달을 택한다.
- 기존 자산은 `titan_example`에 그대로 남아 현행 시스템을 계속 구동한다 — 버리는 것이 아니라
  **분리**다.

#### 결정 3 — SoldierLab의 병사가 최종적으로 titan_example의 병사를 대체한다

이식 방향을 명확히 못박는다. 코드만 이식하고 캐릭터는 그대로 두는 방식(런타임 리타깃)은
비용과 품질 손실 때문에 채택하지 않는다.

```
[지금]      titan_example 병사 (Mixamo 리그, 블렌드스페이스)     ← 현행 시스템 유지
[SoldierLab] 신규 병사 (UE5 Manny 리그, Motion Matching)         ← R&D
[최종]      titan_example의 병사를 SoldierLab 병사로 교체
```

이 결정의 결과로 **디자인팀 애니메이션 요청 스펙이 뒤집힌다.** 기존
`../../ally_animation_request.md`는 "인플레이스, 루트모션 반드시 제외"였으나, 앞으로는:

> **UE5 Mannequin 스켈레톤 기준 / Root 본 필수 / 루트모션 포함 / Root Motion 속성 활성화**

이 변경은 디자인팀에 별도로 공지해야 한다(15절 Q7).

### 3.1 프로젝트 위치와 이름

```
C:\working\works\kadex\anim_test\SoldierLab\        ← 신규 UE5.8 프로젝트
```

`titan_example`의 파생이 아니라 독립 실험장이므로 접두어 없는 `SoldierLab`을 쓴다.

### 3.2 베이스 — Game Animation Sample(GASP)

#### GASP에 실제로 들어있는 것 / 없는 것 (조사 결과)

Epic 공식 문서 기준으로 GASP의 내용은 다음과 같다. **"라이플 슈터에 필요한 게 다 들어있다"는
기대는 사실과 다르므로**, 조달 계획을 세울 때 이 구분이 중요하다.

| | 내용 |
|---|---|
| **✅ 들어있음** | 비무장 로코모션(idle/walk/run, 8방향, **start/stop/pivot/turn-in-place**), 트래버설(볼팅·맨틀·난간 오르기), 슬라이드, **UEFN_Mannequin 스켈레톤**, MetaHuman 바디 변형(`CPB_Sandbox_MetaHuman_Bodies`, 숫자키 1~9로 교체), Pose Search 스키마/데이터베이스 세트, **Chooser 기반 DB 스와핑**(`CHT_PoseSearchDatabases`), Motion Trajectory 배선, Offset Root Bone |
| **❌ 없음** | **라이플 견착 조준 로코모션(8방향 스트레이프)**, 조준 Aim Offset 포즈, 사격/반동, 재장전, 엄폐 진입/이탈, 수신호, 피격/사망 |
| **⚠ 혼동 주의** | GitHub의 `GASP-ALS` 계열 저장소들이 "Overlay Layering System / Weapon Attach System / 라이플·피스톨 상태머신"을 제공하는데, **이건 커뮤니티가 ALS를 얹은 것이지 Epic 공식 GASP의 내용이 아니다.** ALS 자산의 라이선스를 별도로 확인해야 하며, 참고 구현으로만 볼 것 |

GASP의 DB는 `Content/Characters/UEFN_Mannequin/Animations/MotionMatchingData/Databases`에
walk / run / idle / pivot 등으로 **이미 분리되어** 있고, Chooser로 상황에 따라 스왑한다 —
우리가 5.5절에서 계획한 "Aim-Stand / Aim-Crouch / Lowered" DB 분리와 정확히 같은 패턴이라
그대로 확장하면 된다.

#### 그래서 GASP를 쓰는 이유

- **하체 로코모션과 트래버설은 GASP로 끝난다.** 특히 MM 품질을 좌우하는 start/stop/pivot 데이터가
  들어있는데, 이건 직접 만들면 가장 비싼 부분이다.
- MM 파이프라인의 **레퍼런스 구현**(스키마 채널 구성, DB 분리 기준, Chooser 배선, 궤적 컴포넌트)이
  통째로 들어있다. 밑바닥부터 세팅하면 여기서 몇 주가 날아간다.
- 스켈레톤이 UEFN_Mannequin이라 **결정 1과 자동으로 정합**된다.

#### 주의사항

- GASP는 **플레이어 조작 기준**이다. AI 구동 전환(궤적을 입력이 아니라 NavMesh 경로에서 생성)이
  P0의 첫 작업이다(5.3절).
- `Offset Root Bone` 노드는 공식 문서상 **실험적**이며, 이동 오프셋에 충돌 검사가 없어 지오메트리를
  뚫을 수 있고 몽타주 재생 시 원치 않는 이동이 생길 수 있다고 명시돼 있다. AI 병사에게 이 노드가
  필요한지 P0에서 판단하고, 문제가 생기면 끄는 것을 우선 검토한다.

### 3.3 GASP 받기 — 절차

1. **Fab에서 라이브러리에 추가**
   - https://www.fab.com 접속 → Epic 계정으로 로그인
   - "Game Animation Sample" 검색 (Epic Games 배포, 무료)
   - **Add to My Library** 클릭
2. **Epic Games Launcher에서 프로젝트 생성**
   - Epic Games Launcher → **Unreal Engine** → **Library** 탭
   - 아래 **Fab Library**(구 Vault) 목록에서 `Game Animation Sample` 찾기
   - **Create Project** 클릭
   - 엔진 버전 **5.8** 선택
   - 저장 위치를 `C:\working\works\kadex\anim_test\` 로, 프로젝트 이름을 `SoldierLab` 으로 지정
3. **확인 사항**
   - 용량이 크다 — 설치 전 디스크 여유 확인
   - 5.8용 업데이트본인지 확인(엔진 버전 선택 목록에 5.8이 있어야 함)
   - GASP는 **프로젝트 템플릿**이지 콘텐츠 팩이 아니다. 기존 프로젝트에 "추가"하는 방식이
     아니라, GASP로부터 새 프로젝트를 만드는 것이 정상 경로다
4. **첫 실행 검증**
   - 에디터가 열리면 PIE로 캐릭터를 조작해본다. 걷기/달리기/정지/급선회/볼팅이 정상 동작하고
     발이 안 미끄러지는지 확인 → 여기까지 되면 MM 파이프라인이 살아있는 것

### 3.4 C++ 프로젝트로 전환

GASP는 블루프린트 프로젝트로 생성된다. C++ 모듈이 필요하므로:

1. 에디터 상단 **Tools → New C++ Class...**
2. 부모 클래스는 아무거나(예: `None` 또는 `Actor`) 선택, 이름 `SoldierLabDummy` 정도로 생성
3. 이 시점에 프로젝트가 C++ 프로젝트로 전환되고 `Source/` 폴더와 `.sln`이 만들어진다
4. 에디터를 닫고, `SoldierLab.uproject` 우클릭 → **Generate Visual Studio project files**
5. Visual Studio에서 빌드 후 에디터 재실행

> 이후 3.7절의 모듈 레이아웃대로 폴더를 나눠 쓴다. 더미 클래스는 나중에 지운다.

### 3.5 활성화할 플러그인

에디터 **Edit → Plugins**에서 켠다. GASP는 애니메이션 쪽 플러그인이 이미 켜져 있는 상태로
오므로, 실제로 새로 켜야 하는 것은 AI 계열이 대부분이다.

**이미 켜져 있을 가능성이 높음(확인만)**
```
PoseSearch, BlendStack, AnimationWarping, MotionTrajectory, Chooser,
MotionWarping, ControlRig, IKRig, DeformerGraph
```

**새로 켜야 함**
```
StateTree, GameplayStateTree              ← 실행 레이어(8절)
SmartObjects, GameplayBehaviorSmartObjects ← 엄폐 슬롯(10절)
FullBodyIK                                 ← Control Rig 풀바디 IK 솔버(5·6절)
NavCorridor                                ← 궤적 평활화(5.3절)
AnimationBudgetAllocator, SignificanceManager, AnimationSharing  ← 성능(12절)
```

**선택**
```
GameplayAbilities        ← 6절 무기 처리를 GAS로 갈지에 따라(기본은 안 씀, 13절)
ModelContextProtocol     ← unreal-mcp 작업 편의. titan_example에서 쓰던 것과 동일
PythonScriptPlugin, EditorScriptingUtilities  ← 엄폐 슬롯 베이크 툴 작성용(10.2절)
```

플러그인을 켜면 에디터 재시작이 필요하고, C++ 프로젝트라면 해당 모듈을
`SoldierLab.Build.cs`의 `PublicDependencyModuleNames`에도 추가해야 한다:

```csharp
PublicDependencyModuleNames.AddRange(new string[] {
    "Core", "CoreUObject", "Engine", "InputCore",
    "AIModule", "NavigationSystem", "GameplayTasks", "GameplayTags",
    "StateTreeModule", "GameplayStateTreeModule",
    "SmartObjectsModule",
    "PoseSearch", "AnimationWarpingRuntime", "MotionTrajectory", "Chooser",
    "MotionWarping", "ControlRig"
});
```
> 모듈 이름은 5.8 기준으로 실제 `.Build.cs`를 확인하며 맞출 것 — 플러그인 이름과 모듈 이름이
> 다른 경우가 있다(예: AnimationWarping → `AnimationWarpingRuntime`).

### 3.6 프로젝트 초기 설정

| 설정 | 값 | 이유 |
|---|---|---|
| Project Settings → Engine → **Navigation Mesh** → Runtime Generation | `Dynamic` | 동적 장애물(UGV/파괴물) 대응(10.2절) |
| Navigation System → Agents | 병사 캡슐 반경/높이로 에이전트 정의 | |
| **Environment Query System** → Max Allowed Time Per Frame | `0.003` (3ms) | EQS 전역 타임슬라이스 예산(10.4·12.2절) |
| Engine → General Settings → **Fixed Frame Rate** | 사용 안 함 | 성능 측정을 위해 |
| Crowd Manager (Detour Crowd) | 활성 | 회피(5.4절) |
| Project Settings → **Collision** | `Cover` 트레이스 채널 추가 | 엄폐 판정용 전용 채널 |
| Editor Preferences → **Live Coding** | 켬 | 반복 작업 속도 |

### 3.7 C++ 모듈 레이아웃

```
Source/SoldierLab/
├── Command/        FSoldierOrder, USoldierCommandSubsystem  (11절)
├── Squad/          USquadComponent, FSquadBlackboard, 전술 플랜 템플릿  (9절)
├── Soldier/        USoldierBrainComponent(유틸리티), StateTree 스키마/태스크  (8절)
├── Perception/     USoldierPerceptionComponent, FThreatMemory  (7절)
├── Tactical/       엄폐 슬롯 생성기, EQS 커스텀 Generator/Test, 사격선/시야 유틸  (10절)
├── Weapon/         조준 해(解) 계산, 발사/재장전, 총구 IK 타깃  (6절)
├── Motion/         MM 파라미터 브리지, 궤적 생성, IK 컨트롤 타깃  (5절)
└── Debug/          시각화(의도 점수, 엄폐 후보 스코어, 인지 상태) — 1급 시민으로 취급
```

`Debug/`를 처음부터 넣는 이유: 유틸리티 AI의 가장 큰 실패 모드는 "왜 저 행동을 골랐는지 아무도
모른다"이다. IAUS 계열 시스템을 쓰는 모든 사례가 **글래스박스 디버깅 UI**를 함께 만든다.

#### 3.7.1 **아군/적군은 코드 한 벌** — 진영은 데이터다 (2026-09-01 개정 3에서 명문화)

문서 전체가 "병사"로 통칭하고 모듈도 `Soldier/` 하나인데, 이것이 암묵적으로 남아 있었다.
**명시적으로 못박는다: 아군과 적군은 같은 클래스를 쓰고, 차이는 전부 데이터다.**

```
USoldierBrainComponent   ← 아군·적군 공용. 진영별 파생 클래스를 만들지 않는다
   ├─ Faction              (GameplayTag — Ally / Enemy / Neutral)
   ├─ FIntentDefinition[]  (DataAsset — 성향/숙련도 커브. 신병 vs 정예 vs 분대장)
   └─ FOrderConstraints    (명령이 준 ROE·공세성·대형)
```

**근거:**

- 현행 `titan_example`은 `UAllyFormationComponent`(1856줄)와 `UEnemyCombatComponent`(2144줄)
  **두 벌**이고, 그 결과 같은 버그를 두 번 고치는 일이 실제로 반복됐다 — "버스트 도중 조기
  엄폐" 버그는 양쪽에서 각각 수정해야 했다(`../../ai_combat/ally_ai_combat_system_status.md` 8절 =
  `../../ai_combat/enemy_ai_combat_system_status.md` 6절, 같은 버그의 두 기록).
- 현행 문서도 공통 베이스 통합을 **"회귀 위험 때문에 의도적으로 미룸"** 이라고 기록해 두었다.
  즉 합치는 게 옳다는 건 이미 알고 있었고, 타이밍이 문제였을 뿐이다. **신규 프로젝트는 그
  부채를 물려받을 이유가 없다.**
- 유틸리티 구조(8절)는 진영차를 **커브 파라미터**로 표현할 수 있다. 코드 분기가 필요 없다.

**진영별로 실제로 달라지는 것**(전부 데이터/설정):

| 항목 | 표현 방법 |
|---|---|
| 적대 관계 판정 | `Faction` 태그 비교 (7절 인지의 후보 필터) |
| 성향(공세적/방어적), 명중률, 반응속도 | `FIntentDefinition` 커브 + 6.2절 숙련도 파라미터 |
| NavMesh 경로 선호 | 쿼리 필터 클래스(현행 `UNavQueryFilter_Enemy` 계열 패턴 그대로) |
| 사기 하한(결사 항전 등) | `FOrderConstraints::MoraleFloor` (9.4·11.2절) |
| 메시/머티리얼 | 캐릭터 에셋 |

> **예외 규칙**: 아군 전용 개념(UGV 동행 등)이 필요해지면 **파생 클래스가 아니라 별도
> 컴포넌트**로 붙인다. 상속으로 갈라지기 시작하면 현행과 같은 상태로 돌아간다.

### 3.8 애니메이션 조달 계획 — GASP가 못 채우는 부분

> ⚠️ **2026-09-02: 이 절은 `../assets/2026-09-02_asset_supply_and_collaboration.md` 3~6절로 대체되었다.**
> 아래 표의 **카테고리 구분은 여전히 유효**하지만, **조달처는 무효**다. 새로 확인된 제약:
> ① 디자인팀은 애니메이션을 0부터 제작할 수 없다(리깅·리타깃·수정만 가능)
> ② 유료 에셋을 사지 않기로 했다
> ③ 기존 22종도 자체 제작이 아니라 Mixamo 다운로드였다
>
> 그 결과 조달은 **"무료 인플레이스 클립 → 리타깃 → `EncodeRootBoneModifier`로 루트모션
> 합성"** 파이프라인으로 재설계됐다. 아래 "유료 후보" 표는 참고용으로만 남긴다.

3.2절에서 확인했듯 **GASP에는 라이플 견착 조준 로코모션이 없다.** 병사 AI에 필요한 클립을
"GASP가 채우는 것 / 따로 구해야 하는 것"으로 나누면:

| 카테고리 | 출처 | 상태 |
|---|---|---|
| 비무장 idle/walk/run 8방향 루프 | GASP | ✅ 확보 |
| **start / stop / pivot / turn-in-place** | GASP | ✅ 확보 (가장 비싼 데이터인데 공짜) |
| 트래버설(볼팅/맨틀/난간) | GASP | ✅ 확보 |
| **라이플 견착 로코모션 (서기)** — 8방향이 아니라 **전진/후진 중심 2~4방향**이면 됨 | 별도 조달 | ❌ 필요 |
| **라이플 견착 로코모션 (앉기)** — 동일 | 별도 조달 | ❌ 필요 |
| 라이플 견착 start / stop / pivot | 별도 조달 | ❌ 필요 (품질을 좌우하는 부분) |
| **라이플 견착 turn-in-place (좌/우 90°·180°), 자세별** | 별도 조달 | ❌ 필요 — **5.5.6절 재정렬(re-plant)의 필수 자산**. 없으면 적이 등 뒤에 있을 때 몸이 미끄러지듯 돈다 |
| 조준 Aim Offset 극단 포즈 5~9개 | 별도 조달 | ❌ 필요 |
| 피격 리액션 (방향별), 사망, 부상 절뚝임 | 별도 조달 또는 커스텀 | ❌ 필요 — 6.5.1절의 "중간 강도" MM DB용 |
| 사격 반동 / 재장전 / 무기 들기·내리기 | 별도 조달 | ❌ 필요 |
| 엄폐 진입·이탈, 낮은 엄폐물 위 사격 | 별도 조달 또는 커스텀 | ❌ 필요 |
| 수신호(정지/전진/집합), 피격, 사망 | 별도 조달 또는 커스텀 | ❌ 필요 |

#### 조달처 후보 — 반드시 이 3가지 기준으로 검증할 것

무엇을 사든 아래를 먼저 확인한다. 하나라도 실패하면 MM DB에 못 넣는다:

1. **UE5 Mannequin(UEFN_Mannequin) 스켈레톤인가?** 아니면 IK Retargeter 작업이 추가된다
   (5.8의 IK Retargeter는 foot plane/toe 정의와 Retarget Override Set이 추가되어 품질이
   전보다 낫다 — 리타깃 자체는 현실적인 선택지다).
2. **루트모션이 포함되어 있는가?** ← 가장 중요. 인플레이스 전용 팩은 MM에 쓸 수 없고,
   **Orientation Warping도 루트모션을 요구한다**(5.5.2절). 이 이유로 Mixamo는 후보에서 제외된다.
3. **정상상태 루프만 있는가, start/stop/pivot도 있는가?** 루프만 있으면 MM 품질이 안 나온다
   (다만 로코모션 전환은 GASP가 커버하므로, 라이플 팩은 루프 위주여도 차선책은 된다).

> **구매 규모는 P0-2(견착 strafe 워핑 검증, 14절) 결과가 나온 뒤에 확정한다.** Orientation
> Warping이 견착 자세에서 얼마나 잘 버티느냐에 따라 필요한 방향 클립 수가 2개에서 8개까지
> 달라진다. 그 전에 큰 팩을 사면 낭비 위험이 있다.

| 후보 | 성격 |
|---|---|
| **Lyra Starter Game** (Epic, 무료) | 라이플 조준/사격/재장전. UE5 Manny 규격이라 정합성 최상. **가장 먼저 확인할 것** |
| MoCap Online — Rifle Shooter Pro / Shooter Animation Pack (Fab, 유료) | 군용 라이플 모캡. 커버리지가 넓음 |
| KINEMATION — Tactical Shooter Pack (Fab, 유료) | GASP 연동 가이드를 자체 제공할 만큼 궁합이 맞음 |
| ActorCore / Reallusion (유료) | 모캡 라이브러리 |
| 커스텀 제작(디자인팀) | 엄폐 진입/이탈, 낮은 엄폐물 사격, 수신호 — 시중 팩에 잘 없는 것들 |

#### 권장 순서

1. **P0에서는 아무것도 사지 않는다.** GASP 기본 캐릭터(비무장)로 "AI가 MM을 구동하는가"만
   검증한다. 라이플 자산은 이 검증 결과와 무관하다.
2. P0 통과 후 Lyra를 먼저 확인해서 무료로 얼마나 채워지는지 본다.
3. 남는 구멍만 유료 팩 또는 디자인팀 커스텀으로 채운다. 이때 요청 스펙은 3.0절 결정 3의
   새 규격(**Manny 스켈레톤 / Root 본 / 루트모션 포함**)을 따른다.

---

## 4. 전체 아키텍처 — 5개 레이어

```
┌──────────────────────────────────────────────────────────────────────────┐
│ L0  COMMAND — 상부 지휘 (나중에 titan_example 시나리오 시스템이 여기 접속)│
│     FSoldierOrder 발행: "1분대, 저 건물 교전 개시, ROE=자유, 공세적"      │
│     비율: 초당 0~수회. 사람이 저작하는 유일한 레이어                       │
└───────────────────────────────┬──────────────────────────────────────────┘
                                │ Order (무엇을) — 어떻게는 안 말함
┌───────────────────────────────▼──────────────────────────────────────────┐
│ L1  SQUAD — 분대 조율 (USquadComponent, 2~4Hz)                            │
│     · 명령 → 전술 플랜 선택(정면제압 / 바운딩오버워치 / 측면 / 철수)      │
│     · 전술 슬롯 생성·배분(누가 엄호, 누가 기동), 회랑(corridor) 지정      │
│     · 분대 blackboard: 공유 위협 목록, 사기, 제압사격 토큰                 │
└───────────────────────────────┬──────────────────────────────────────────┘
                                │ Assignment (역할 + 영역 + 우선순위)
┌───────────────────────────────▼──────────────────────────────────────────┐
│ L2  BRAIN — 개인 판단 (USoldierBrainComponent, 유틸리티 스코어러, 4~10Hz) │
│     후보 의도(Intent)를 전부 점수화 → 최고점 하나 선택 + 히스테리시스     │
│     TakeCover / Suppress / AimedFire / Reposition / Advance / Retreat /   │
│     Reload / PeekCheck / Regroup / Revive / Grenade ...                   │
│     입력: 인지 결과 + 분대 assignment + 자기 상태(탄약/체력/피제압도)     │
└───────────────────────────────┬──────────────────────────────────────────┘
                                │ Intent (+ 파라미터: 목표 슬롯, 목표 적)
┌───────────────────────────────▼──────────────────────────────────────────┐
│ L3  ACT — 실행 (StateTree, 매 틱)                                         │
│     의도를 구체적 태스크 시퀀스로: 경로 이동 → Smart Object 슬롯 진입 →   │
│     자세 전환 → 조준 → 사격 버스트 → 이탈. 실패/중단 처리, 애니메이션 계약 │
└───────────────────────────────┬──────────────────────────────────────────┘
                                │ Motion Request (속도/방향/자세/조준/이벤트)
┌───────────────────────────────▼──────────────────────────────────────────┐
│ L4  MOTION — 몸 (Motion Matching + Warping + Control Rig IK, 매 프레임)   │
│     풀바디 MM · Orientation/Stride Warping · 발 배치 IK · 손 IK · 총구 정렬 │
└──────────────────────────────────────────────────────────────────────────┘

    ┌──────────────────┐        ┌────────────────────────────────────┐
    │ PERCEPTION (L2↔) │        │ TACTICAL QUERY (L1·L2가 호출)       │
    │ 시야/청각/기억   │        │ Smart Object 슬롯 + EQS 스코어링     │
    └──────────────────┘        └────────────────────────────────────┘
```

### 4.1 이 분할의 근거

- **L0/L1/L2 3계층 분리는 Killzone 2/3의 검증된 구조**(전략→분대 HTN→개인 HTN)를 그대로
  따른다. 우리는 분대/개인 레이어의 *구현 기법*만 HTN에서 유틸리티로 바꿨다.
- **L2와 L3를 나눈 것이 이 설계의 핵심 결정이다.** "무엇을 할지 고르는 것"(판단)과 "그것을
  어떻게 수행하는지"(실행)를 한 트리 안에 섞으면 현행 시스템과 똑같은 문제가 재발한다 —
  우선순위가 트리 모양에 하드코딩되어 상황 변화에 못 따라간다. 8절에서 상세히.
- **L4를 완전히 분리**한 이유: 현행 시스템의 애니메이션 버그가 전부 "AI 로직이 애니메이션
  파라미터를 직접 만졌다"에서 나왔다. L3는 *의미*(달린다/앉는다/조준한다)만 전달하고,
  *숫자*(재생속도, 블렌드 가중치)는 L4가 혼자 정한다.

### 4.2 틱 예산 요약

| 레이어 | 주기 | 근거 |
|---|---|---|
| L0 Command | 이벤트 | 시나리오 스텝 발화 시 |
| L1 Squad | 2~4 Hz | Days Gone의 분대 재평가와 같은 급. 이보다 빠르면 분대 결정이 요동친다 |
| L2 Brain | 4~10 Hz (거리 LOD) | 유틸리티 재평가. 사람 반응시간(200~300ms)과 맞음 |
| L3 Act | 매 틱 (또는 10~30Hz) | 도착 판정, 사격 타이밍 |
| L4 Motion | 매 프레임 | 애님 평가 |
| Perception | 10 Hz, 라운드로빈 분산 | 12절 |

### 4.3 권위(Authority)와 리플리케이션

> **2026-09-01 개정 3에서 추가.** 초안에 이 항목이 통째로 빠져 있었다. 나중에 얹으면 L2/L3/L4
> 경계를 다시 그려야 하므로 **레이어 설계 단계에서 못박는다.**

#### 4.3.1 왜 지금 정해야 하는가

`titan_example`은 **리슨서버 멀티플레이 프로젝트**다(`../../replication/replication_audit.md`).
그리고 이미 다음이 구현·검증되어 있다:

- 아군/적군 **45명 전부 `bReplicates=true`**
- **전투 컴포넌트 Tick의 서버 전용화** — 판단은 서버만 돈다
- 발사 이펙트/사운드는 **위치 기반 Multicast**로 재생(RCWS/아군/적군 공통)
- 자동 표적 선정(`SelectNearestEnemyTarget`)은 서버에서만, 결과만 복제

3.0절 결정 3("SoldierLab 병사가 titan_example 병사를 대체한다")을 확정한 이상, 새 병사는
**이 권위 모델 위에 착지해야 한다.** 싱글플레이 전제로 만들어놓고 나중에 복제를 얹는 것은
이 설계에서 가장 비싼 실수가 된다.

#### 4.3.2 레이어별 권위 배치

| 레이어 | 어디서 도는가 | 복제되는 것 | 근거 |
|---|---|---|---|
| **L0 Command** | **서버 전용** | `FSoldierOrder`(선택적 — 클라이언트 UI가 명령 상태를 보여줄 필요가 있을 때만) | 시나리오 발화는 원래 서버 권위. 현행 Exec 콘솔 커맨드도 "서버에서만 실제 상태를 바꾸도록" 정리된 상태 |
| **L1 Squad** | **서버 전용** | 없음(파생 상태) | 분대 blackboard는 서버 내부 상태. 클라이언트가 알 필요 없음 |
| **L2 Brain (유틸리티)** | **서버 전용** | **선택된 `IntentTag`만** 복제 | 유틸리티 점수 전체를 복제할 이유가 없다. 결과 1개만 보내면 클라이언트가 애니메이션을 맞출 수 있다 |
| **L3 Act (StateTree)** | **서버 전용** | **자세/조준 상태 등 "L4 입력"만** 복제(아래 4.3.3) | 현행 "전투 컴포넌트 Tick 서버 전용화"와 같은 패턴 |
| **L4 Motion (MM + IK)** | **각 클라이언트에서 로컬 실행** | 실행 안 함 — 입력만 받아서 각자 평가 | 포즈를 복제하는 건 불가능하고 불필요. 단 4.3.4의 함정이 있다 |
| Perception | **서버 전용** | 없음 | 인지 결과는 판단의 입력일 뿐 |

**원칙: "판단은 서버, 몸은 각자."** 복제 대역은 L2/L3가 만들어내는 **소수의 스칼라/열거형**으로
한정한다.

#### 4.3.3 복제해야 하는 최소 상태 (`FSoldierReplicatedState`)

```cpp
USTRUCT()
struct FSoldierReplicatedState
{
    FGameplayTag  CurrentIntent;      // L2 결과. 애니메이션 상태 선택의 최상위 힌트
    uint8         Stance;             // Standing / Crouch / Prone
    uint8         WeaponState;        // Lowered / Aiming / Firing / Reloading
    FVector_NetQuantize  AimTarget;   // 조준점(월드). 상체 정렬·Look-At의 입력
    uint8         LeanState;          // None / Left / Right
    uint8         HealthState;        // Healthy / Injured / Downed / Dead  (6.5절)
    // 이동 자체는 CharacterMovementComponent의 기존 복제를 그대로 사용
};
```

- 이동/속도/회전은 **CMC의 기존 복제 경로를 그대로 쓴다.** 우리가 추가로 복제하는 것은
  "몸이 무엇을 하는 중인가"뿐이다.
- `AimTarget`은 **위치**로 복제한다(각도가 아니라). 그래야 클라이언트에서 자세가 조금 달라도
  총구가 같은 지점을 향한다.
- 궤적(5.3절)은 **복제하지 않는다.** 각 클라이언트가 복제된 이동 상태로부터 자기 궤적을
  재구성한다 — 궤적은 프레임당 수십 개 샘플이라 복제 비용이 감당이 안 된다.

#### 4.3.4 함정 — 명중 판정이 포즈에 의존한다

6.1절의 설계는 **총구 소켓의 실제 월드 트랜스폼에서 발사 트레이스를 쏜다.** 그런데 L4(MM)는
클라이언트마다 로컬 실행이라 **포즈가 미세하게 다를 수 있다**(MM은 결정적이지 않고, 프레임
타이밍·보간 상태가 다르다). 즉 총구 위치가 머신마다 다르다.

**해결: 판정과 연출을 분리한다.**

| | 기준 | 근거 |
|---|---|---|
| **명중 판정** | **서버의 논리적 조준선** — `AimTarget` + 6.2절의 정확도 콘. 서버가 자기 스켈레톤 평가 결과(또는 소켓 근사 트랜스폼)로 트레이스 | 서버 권위. 클라이언트 포즈에 판정이 흔들리면 안 됨 |
| **시각 연출** (총구 화염, 트레이서, 탄피) | **각 클라이언트의 로컬 총구 소켓** | 보이는 것과 총구가 어긋나면 안 됨 |
| 결과 전파 | 현행과 동일하게 **위치 기반 Multicast** | `../../replication/replication_audit.md`의 검증된 패턴 재사용 |

트레이서 시작점이 클라이언트마다 몇 cm 다른 것은 아무도 눈치채지 못한다. 반대로 명중이
클라이언트마다 다르면 게임이 무너진다.

#### 4.3.5 서버 애니메이션 비용 — 12절 예산의 숨은 항목

서버도 명중 판정을 위해 스켈레톤을 어느 정도는 평가해야 한다. 전략:

- 서버는 **T2 티어 수준의 축소 평가**만 수행하고(12.3절), 총구 위치는 **자세+조준으로부터
  해석적으로 근사**한다. 즉 서버는 MM을 돌리지 않는다.
- 정밀도가 문제되면 사격하는 개체에 한해 그 프레임만 소켓을 정확히 평가한다(현행
  `titan_example`이 총구 보정을 코드로 하고 있는 것과 같은 계열의 절충).
- **리슨서버는 호스트가 곧 클라이언트**라 이 비용이 12.2절 예산에 그대로 얹힌다는 점에
  주의. 데디케이티드가 아니다.

#### 4.3.6 SoldierLab 단계에서의 취급

SoldierLab은 R&D이므로 **P0~P2는 싱글플레이(리슨서버 1인)로 개발한다.** 다만:

- **처음부터 서버 권위 게이트를 넣어둔다** — 모든 L0~L3 Tick 진입점에 `HasAuthority()` 체크,
  L4는 권위와 무관하게 동작. 게이트만 있으면 나중에 실제 2프로세스 검증으로 넘어가는 비용이
  작다(현행 프로젝트가 나중에 이 작업을 했고, 그때 든 비용이 `../../replication/replication_audit.md`에 남아 있다).
- **P3에서 2프로세스 실검증**을 한다(12절 성능 측정과 같은 단계).

---

## 5. 로코모션 (요구항목 1)

### 5.1 채택: **풀바디** Motion Matching + Pose Warping + Control Rig IK

**결정**: 로코모션의 뼈대는 `PoseSearch` Motion Matching으로 간다. 블렌드스페이스/스테이트머신
기반 로코모션은 폐기한다. **MM은 하체 전용이 아니라 풀바디를 담당하며**, 조준 자세도 상체
레이어 블렌드가 아니라 풀바디 견착 클립을 MM DB에 넣어 해결한다(5.5절).

**근거**:
1. 1.3절의 실제 버그들이 전부 "속도→애니메이션 파라미터 수동 매핑"에서 나왔다. MM은 이 매핑
   자체가 없다 — 질의는 `(과거 궤적, 미래 궤적, 현재 포즈)`이고, 감속·회전·정지가 데이터에서
   나온다.
2. UE5.8에서 `PoseSearch`는 실험 딱지가 없는 정식 기능이고, GASP라는 대규모 레퍼런스
   데이터셋이 5.8용으로 제공된다 — **단 비무장 로코모션까지이고 라이플 자산은 없다**(3.2절).
3. TLOU2가 증명한 품질 상한이 여기 있다.

### 5.2 발걸음/보행 사이클과 발 배치

| 요소 | 방식 | 근거 |
|---|---|---|
| 보행 사이클 | MM이 클립에서 직접 선택 (Stride Warping으로 보폭↔실제 속도 정합, `StrideScale = 이동속도 / 루트모션속도`) | 발 미끄러짐(foot sliding)의 근본 해결. ⚠ 공식 문서가 이 노드를 "아직 다듬는 중"이라고 표기 — P0에서 실측 |
| 발 지면 배치 | Control Rig 후처리: 발밑 트레이스 → 발 위치/회전 보정 → 골반 높이 하강 → 반대발 보정 | "Fitting the World: A Biomechanical Approach to Foot IK"의 접근. 발만 붙이면 다리가 늘어나 보이므로 **골반까지 같이 내리는 것이 핵심**. GASP 5.7의 Footplacement Control Rig가 출발점 |
| 경사면 | Slope Warping (`AnimationWarping`) + 발 회전 IK | ⚠ **성숙도 주의**: 공식 문서가 *"이 노드는 아직 개발 중이니 프로젝트를 여기 의존하지 말 것, 테스트 환경에서의 적용은 권장"* 이라고 명시. **경사 처리는 Control Rig 자체 구현을 폴백으로 준비**할 것 |
| 이동방향 ≠ 몸방향 (스트레이프/조준 이동) | **Orientation Warping** — 다리 IK 본 회전 + 스파인 테이퍼 분배 | **이 설계의 핵심 부품.** 현행 `Direction` 변수 계산 버그의 구조적 해결책이자, 8방향 클립 조합 폭발을 막는 수단. 상세는 5.5.2절 |
| 정지/출발 | Distance Matching + MM (GASP 패턴) | 목표점에 정확히 멈춤. 현행의 "감속 램프로 MaxWalkSpeed를 줄이는" 방식은 폐기 |
| 발소리 | `AnimNotify_Footstep` + `UFootstepAudioComponent` 패턴 재사용 | 현행 구현이 검증됐으므로 **로직만** 이식(자산은 3.0절 결정 2에 따라 신규) |

### 5.3 AI가 Motion Matching을 구동하는 방법 (중요)

MM은 **미래 궤적(trajectory)** 을 질의로 요구하는데, GASP를 포함한 모든 샘플이 이걸 **플레이어
입력**에서 만든다. AI는 입력이 없다. 해결:

```
NavMesh 경로(FNavPathSharedPtr)
   → 앞으로 N초 동안의 예상 위치/방향 샘플 K개 생성 (경로 위를 목표 속도로 따라간다고 가정)
   → 조향 보정(회피/RVO/근접 아군)을 반영
   → UCharacterTrajectoryComponent(MotionTrajectory)에 주입
   → Pose Search 질의
```

- `NavCorridor` 플러그인(정식)이 경로를 "통로"로 확장해줘서 궤적 평활화에 쓸 수 있다.
- **위험**: `MotionTrajectory`는 5.8에서도 Experimental(v0.1)이다. 따라서 궤적 생성을
  `USoldierTrajectorySource`라는 자체 인터페이스로 감싸서, 플러그인 API가 바뀌어도 한 파일만
  고치면 되게 한다.
- 5.8의 Mover/ChaosMover가 "motion-matching workflow용 궤적 예측"을 추가했지만, Mover 자체가
  아직 Experimental이라 이번엔 CharacterMovementComponent + 자체 궤적으로 간다(13절).

### 5.4 지형/장애물 인지 이동

| 상황 | 처리 |
|---|---|
| 일반 회피 | Detour Crowd (현행 RVO 대체 또는 병행) + 겹침 밀어내기(현행 `ResolveAllyOverlapPush` 이식) |
| 낮은 엄폐물 넘기 / 창문 / 난간 | **Smart Object "traversal" 슬롯** + Motion Warping. 접점(손·발)이 실제 지오메트리에 정확히 닿게 워핑 |
| 낮은 엄폐물 뒤 자세 전환 | 엄폐 슬롯 메타데이터가 `Standing/Crouch/Prone`과 `LeanLeft/Right/OverTop`을 들고 있음(10절) → L3가 자세를 요청, L4가 MM 데이터베이스를 Chooser로 스와핑 |
| 좁은 통로 | NavMesh 폭 + Detour Crowd. 분대 대형은 통로에서 자동으로 종대로 축소(9절) |
| 문/사다리 등 | Smart Object 슬롯 (2차 범위) |

### 5.5 조준 자세를 어떻게 만들 것인가 — **풀바디 베이스 + 절차적 워핑**

> **2026-09-01 개정.** 이 절의 초안은 "하체 MM + 상체 레이어 블렌드"라는 하이브리드를 제안했다.
> **그 방식은 이 프로젝트가 이미 실패로 확인한 접근이므로 폐기한다.** 개정 근거는 아래 5.5.1.

#### 5.5.1 왜 "상하체 분리"를 쓰지 않는가 — 프로젝트 자체의 실증

`../../ally_animation_request.md`(디자인팀 요청서)에 이미 결론이 적혀 있다:

> **안 되는 것 — 로코모션(걷기/뛰기) 중에 상반신만 다른 파지자세로 레이어/블렌드 하는 것.**
> 걷기/뛰기는 발맞춤에 동기화된 전신 움직임이라, 상반신과 하반신을 따로 블렌드하면 상체가
> 허공에 붕 뜬 채 고정되고 다리만 뛰는 이음새가 눈에 띔.

그래서 "조준 상태로 이동"을 **이동상태 × 무장상태 조합마다 풀바디 클립으로** 받았던 것이다.
이 판단은 옳았고 지금도 유효하다. 문제는 그 다음이었다 — 풀바디 클립을 **블렌드스페이스**로
이어붙이니 전환(출발/정지/급선회)이 뻣뻣했고, 1.3절의 속도 정규화 버그들이 따라왔다.

**정리하면 두 축은 독립적인 문제다.**

| 축 | 나쁜 답 | 좋은 답 |
|---|---|---|
| 상체가 하체와 따로 노는 문제 | 레이어 블렌드 | **풀바디 클립** |
| 전환이 뻣뻣한 문제 | 블렌드스페이스 | **Motion Matching** |

지금까지 이 둘을 하나의 선택지처럼 다뤄서 "풀바디 클립 = 블렌드스페이스"에 묶여 있었다.
**둘을 분리하면 답은 "풀바디 견착 클립을 MM 데이터베이스에 넣는다"** 이다.

#### 5.5.2 조합 폭발을 막는 것 — Orientation Warping

풀바디 견착으로 가면 즉시 걱정되는 것이 조합 폭발(이동 8방향 × 조준각 × 자세 3)이다. 이걸
막는 것이 **Orientation Warping**(`AnimationWarping` 플러그인, 5.8 정식)이다. Epic 공식
Pose Warping 문서의 서술:

> 캐릭터가 **상체 방향을 유지한 채 하체만 이동 입력에 맞춰 적응**하게 한다.
> 전진 애니메이션 하나에 이 노드를 적용하면 **상체는 원래 방향을 유지한 채 하체는 180도
> 전체를 커버**한다.

작동 방식은 **다리 IK 본을 목표 이동방향으로 회전시키고, 그 회전을 스파인 본들에 테이퍼해서
분배**하는 것이다. 즉 **원본이 풀바디 클립 하나**이고 그것을 절차적으로 비틀 뿐이다.

**이것이 레이어 블렌드와 근본적으로 다른 이유:**

```
레이어 블렌드:   클립A(하체) + 클립B(상체)  →  두 클립은 서로를 모름  →  이음새·붕 뜸
워핑:            클립A(풀바디)를 회전 분배로 변형  →  포즈 일관성이 원천적으로 유지됨
```

- **전제 조건**: **루트모션 애니메이션 + IK Rig가 필수**다(공식 문서 명시). 3.0절의 스켈레톤
  교체 결정이 여기서도 전제 조건이 된다.
- **한계**: 극단 각도(순수 측면/후진)에서는 워핑만으로 완벽하지 않다. 그래서 실무 조합은
  **"전진/후진(±) 중심의 소수 풀바디 클립 + 워핑"** 이다. 8방향을 전부 받을 필요는 없다.

#### 5.5.3 채택하는 4층 구조

```
[1] 베이스 포즈      Motion Matching  ←  풀바디 견착 클립 DB
                     (Aim-Stand / Aim-Crouch / Lowered 로 DB 분리, Chooser 스왑)
[2] 이동방향 적응    Orientation Warping (다리 IK 회전 + 스파인 테이퍼)
                     Stride Warping (StrideScale = 이동속도 / 루트모션속도)
[3] 조준각 적응      Aim Offset(피치 중심, 애디티브) — 풀바디 베이스에 대한 "작은 편차"라
                     레이어 블렌드와 달리 포즈를 무너뜨리지 않는다
[4] 정밀 보정        Control Rig — 총구 소켓이 조준선에 오도록 스파인/쇄골/팔 미세 조정,
                     시선 추적(GASP 5.8 Look-At POI 솔버, additive)
```

**3층과 4층은 "덮어쓰기"가 아니라 "얹기"다.** GASP 5.8에 새로 들어온 Look-At Point-Of-Interest
솔버가 정확히 이 원칙으로 만들어져 있다 — Control Rig으로 구현된 **additive** 솔버이고,
**기존 애니메이션을 덮어쓰지 않고 그 위에 얹히며, 신체 부위별로 추적 강도를 개별 제어**한다.
샘플 레벨에 **순찰 NPC의 스캔 방향 제어** 데모가 포함돼 있어 7.2절의 시야 스캔 요구와 그대로
겹친다. 조준 보정도 이 솔버를 베이스로 확장한다(6.1절).

#### 5.5.4 클립 요구량 재산정

| | 워핑 없이 | Orientation/Stride Warping 적용 |
|---|---|---|
| 스탠스당 로코모션 루프 | 8방향 × 속도 3종 = 24+ | **전진/후진 중심 2~4방향** (극단 각도 품질 보강용) |
| start / stop / pivot / turn-in-place | 필수 | 필수 (비무장분은 GASP가 커버) |
| 3스탠스 합계 | 150~250 | **60~90** |

#### 5.5.5 전신 전환 동작은 별도

엄폐 진입/이탈, 장애물 넘기, 피격 반응, 사망, 부축은 워핑 대상이 아니라 **전용 풀바디
클립/몽타주 또는 전용 MM DB로 전체를 일시 점유**한다. 5.8의 **Pose Search Interaction
Assets**(여러 스켈레탈 메시 간 포즈 검색 + 모션워프 접점 정렬 자동화, `Motion Match Multi`)를
엄폐물·무기·2인 상호작용에 쓸 수 있는지 P1에서 평가한다.

#### 5.5.6 조준 한계각과 재정렬(re-plant) — 적이 등 뒤에 있을 때

> **2026-09-01 개정 3에서 추가.** 개정 2에서 5.5절을 재작성하면서 초안에 있던 re-plant 트리거가
> 누락됐다. "적이 뒤에 있으면 무슨 일이 일어나는가"가 정의돼 있지 않으면 구현이 막힌다.

Orientation Warping은 **하체를 180°까지** 커버하지만, 그건 "상체 방향 대비 이동 방향"의 범위다.
**조준 방향 자체가 몸 뒤로 넘어가는 경우는 워핑이 풀어주지 않는다.** 사람 몸도 마찬가지다 —
허리를 90° 넘게 비틀 수 없으니 **발을 다시 딛는다.**

각도 구간별로 처리를 나눈다(각도는 `몸통 정면 → 조준 목표`의 Yaw 차이):

| 구간 | 처리 | 담당 |
|---|---|---|
| **0~45°** (`AimDeadzone`) | 몸통은 그대로, **Aim Offset + Control Rig 보정만**으로 조준 | L4 |
| **45~90°** (`AimTwistMax`) | 상체 비틀기 + **몸통을 천천히 목표 쪽으로 보간**(기존 회전 관성 패턴). 이동 중이면 Orientation Warping이 하체를 흡수 | L4 + L3 |
| **90° 초과** | **재정렬(re-plant) 트리거** — L3가 "몸통 재정렬" 태스크를 발행. 정지 중이면 turn-in-place 클립, 이동 중이면 pivot 클립을 MM이 선택 | **L3가 판단, L4가 수행** |
| **135° 초과 + 즉시 대응 필요** | 급선회 pivot을 우선 재생하고, 그동안 **사격을 보류**(6.2절 조준 수렴 조건이 자동으로 막아준다) | L3 |

**설계 규칙 3가지:**

1. **재정렬은 L4가 몰래 하지 않는다.** 몸통을 트는 건 자세와 사격 가능 여부를 바꾸는 행동이라
   L3의 태스크로 표현한다. 그래야 "지금 돌고 있어서 못 쏜다"가 판단 레이어에 보인다.
2. **재정렬 중에는 조준 수렴 타이머가 리셋된다**(6.2절). 몸을 홱 돌려서 즉사시키는 것이
   구조적으로 불가능해지는 지점이 여기다.
3. **한계각은 자세마다 다르다.** 엎드린 자세(Prone)는 상체 비틀기 여유가 거의 없어
   `AimTwistMax`가 훨씬 작고, 재정렬 비용(몸 전체를 돌려야 함)이 크다 → 유틸리티의
   `Reposition` 점수에 "현재 자세에서 표적 각도가 불리함"이 이미 축으로 들어가 있다(8.3절).

**필요한 클립**: turn-in-place(좌/우 90°/180°)와 pivot이 **자세별로** 필요하다. GASP가
비무장분은 커버하므로, 조달 대상은 견착 자세의 turn/pivot이다(3.8절 표에 반영).

### 5.6 조준·지형·환경 연동 파이프라인

"실시간 애니메이션이 주변 지형·적 방향과 전부 연동되어야 한다"는 요구를 하나의 그림으로
정리하면 — 각 입력이 어느 노드로 들어가는지가 곧 구현 명세다.

```
[적 방향 / 조준 목표]
   ├─→ MM 질의의 facing            → 견착 DB에서 적절한 포즈 선택            (5.5.3 [1])
   ├─→ Orientation Warping 입력    → 몸방향은 적, 다리는 이동방향             (5.5.3 [2])
   ├─→ Aim Offset (피치)           → 상하 조준각                              (5.5.3 [3])
   ├─→ Control Rig 총구 정렬       → 총구 소켓이 실제 조준선에 오도록          (6.1절)
   └─→ Look-At POI 솔버            → 머리/시선. 조준과 별개로 "보는 방향"      (7.2절 시야 스캔)

[지형]
   ├─→ Slope Warping               → 경사면 발 배치 + 골반 보정   ⚠ 성숙도 주의(5.2절)
   ├─→ 발 IK (Control Rig)         → 요철/계단. 골반까지 같이 하강
   ├─→ Stride Warping              → 실제 속도와 보폭 정합 → 발 미끄러짐 제거
   └─→ NavMesh 경로 → 궤적 생성    → MM 질의의 미래 궤적          (5.3절)

[엄폐물 / 장애물 / 동적 물체]
   ├─→ SmartObject 슬롯 메타데이터 → 자세 선택(서기/앉기/엎드림), lean/over-top  (10.2절)
   ├─→ Motion Warping              → 진입/넘기 시 손·발 접점을 실제 지오메트리에 정렬
   ├─→ Pose Search Interaction Asset (5.8) → 접점 정합 자동화                (5.5.5)
   └─→ (연구 차용) 충돌 페널티를 MM 비용에 반영                              (5.7절)

[피격 / 물리]
   └─→ Control Rig Physics / PhysicsControl → 물리 기반 반응, 장구류 흔들림
```

**설계 원칙**: 위 입력들은 전부 **L3(StateTree)가 "의미"로 전달하고 L4가 숫자로 바꾼다**(4.1절).
AI 로직이 블렌드 가중치나 본 각도를 직접 만지지 않는다 — 현행 시스템의 애니메이션 버그가
전부 그 지점에서 나왔다.

### 5.7 연구 단계 기술 — 차용할 개념

당장 도입하지는 않지만 방향을 정할 때 근거가 되는 최신 연구:

| 연구 | 내용 | 우리에게 주는 것 |
|---|---|---|
| **Environment-aware Motion Matching** (Ponton·Andrews·Andujar·Pelechano, ACM TOG / SIGGRAPH Asia 2025, arXiv 2510.22632) | mocap DB에서 shape/pose/trajectory 특징을 전처리하고, 런타임에 **동적 환경과의 충돌을 페널티로 매칭 비용에 넣는다** → 캐릭터가 장애물·군중을 피하려 **자세와 궤적을 동시에** 조정 | "지형 연동"의 학술적 최신형. 프로덕션 구현체는 없으나 **개념 차용 가능** — MM 질의 비용에 "엄폐물/아군/장애물 근접 페널티" 커스텀 채널 추가. 우리 EQS·SmartObject가 이미 그 정보를 들고 있다 |
| **Learned Motion Matching** (Holden et al., Ubisoft 2020) | DB를 신경망으로 압축. **590MB → 8.5MB** (양자화 포함), 품질·응답성 유지 | 라이플 DB가 3스탠스로 불어나 메모리가 문제되면 꺼낼 카드. UE5 구현체가 GitHub에 존재 |

### 5.8 기성 구현체 — 참고/구매 후보

바닥부터 만들기 전에 **먼저 뜯어볼 가치가 있는 것들**. 특히 첫 번째는 우리 요구에 가장 가깝다.

| 제품 | 볼 이유 |
|---|---|
| **Advanced Third Person Shooter Project (ATPS)** — Fab, UE5.5~5.8 | MM 완전 통합 + **MM 전용으로 새로 만든 aim offset 세트** + **ProPose**(데이터테이블 기반 절차적 **풀바디** 포즈 조정 — 레이어 블렌드가 아니라 우리와 같은 계열) + **엄폐·MM 트래버설을 하는 적 AI** + 코너 트래버스 |
| Third Person Shooter Kit v2.2 — Fab | GASP 기반 MM 통합, 무기 그립 포스트프로세스 시스템. 100% 블루프린트 |
| Tactical Shooter Kit V1 — Fab | 택티컬 특화 |
| GASP-ALS (GitHub, 무료) | ALS 오버레이 레이어링 방식. **우리가 채택하지 않는 방식이지만 "왜 안 되는지" 직접 비교하는 용도로 유용** |

---

## 6. 사격/무기 처리 (요구항목 2)

### 6.1 조준의 진실 원천(single source of truth)

현행은 액터 Yaw를 총구 오프셋으로 보정하고, 피치는 총 액터의 상대회전을 매 틱 보정하는 방식이다
(동작은 하지만 "애니메이션이 만든 포즈를 코드가 사후에 비틀고" 있다). 새 설계는 순서를 뒤집는다:

```
1) L2/L3가 "조준 목표(FAimSolution)"를 결정
     = 목표 위치 + 리드(예측사격) + 탄도 낙차 보정 + 정확도 콘 + 조준 수렴 속도
2) L4가 그 목표를 향해 몸을 만든다  (5.5.3의 4층 구조)
     [1] MM이 견착 풀바디 포즈 선택
     [2] Orientation Warping이 이동방향과 몸방향을 분리
     [3] Aim Offset(피치 중심 애디티브)으로 대략 조준
     [4] Control Rig이 총구(muzzle) 소켓을 조준선에 정확히 정렬 — additive 보정
         (spine/clavicle/upperarm 체인, 팔꿈치 극점 유지)
3) 왼손은 무기 그립 소켓을 IK로 따라감. **`ik_hand_gun` 표준 본을 활용**(3.0절 결정 1)
4) 실제 발사 트레이스는 총구 소켓의 실제 월드 트랜스폼에서 나감
5) 시선(머리/눈)은 조준과 **별개 채널** — Look-At 솔버가 담당 (7.2절 시야 스캔과 연동)
```

**핵심 원칙: "총구가 실제 조준과 일치"는 코드가 총을 돌려서가 아니라, 총구 소켓을 IK 타깃으로
삼아 몸을 정렬해서 달성한다.** 그래야 자세(서기/앉기/기대기)가 바뀌어도 자동으로 성립한다.

#### 4단계 보정의 베이스 — GASP 5.8 Look-At POI 솔버

밑바닥부터 만들지 않는다. GASP 5.8에 들어온 **Look-At Point-Of-Interest 솔버**를 베이스로
확장한다. 이 솔버의 성질이 정확히 우리가 필요한 것이다:

- **Control Rig으로 전부 구현**되어 있음 → 우리가 읽고 고칠 수 있음
- **Additive** — **기존 애니메이션을 덮어쓰지 않고 그 위에 얹힌다**. 이것이 5.5.1의 실패
  (레이어 블렌드가 베이스 포즈를 파괴)를 반복하지 않는 핵심 성질
- **신체 부위별로 추적 강도를 개별 제어** → 머리는 100%, 흉부는 40%, 골반은 0% 같은 배분
- 샘플 레벨에 **순찰 NPC의 스캔 방향 제어** 데모 포함 — 우리 7.2절 요구와 그대로 겹침
- 상태: 실험적(Experimental). 따라서 **복사해서 우리 리그로 가져와** 쓰고, GASP 원본 갱신에
  종속되지 않게 한다

확장할 것: 대상이 "바라볼 지점"이 아니라 **"총구가 향해야 할 지점"** 인 변형을 하나 더 만들고,
체인을 spine→clavicle→upperarm으로 잡아 총구 소켓을 최종 이펙터로 삼는다.

### 6.2 조준 수렴 = 사격 타이밍의 물리적 근거

현행은 "회전 오차 5° 이내가 되면 발사 허용"이다. 이 개념은 좋다 — 유지하되 확장한다:

| 항목 | 설계 |
|---|---|
| 조준 수렴 | 목표 조준선과 현재 총구선의 각도차가 `AimSettleThreshold` 이하 + **일정 시간 유지**되어야 발사 허용 |
| 수렴 속도 | 병사 숙련도 파라미터(`AimSpeedDegPerSec`, `SettleTimeSec`)로 개체차. 정예/신병 구분 |
| 표적 전환 | 새 표적으로 넘어갈 때 수렴 타이머 리셋 → "확 돌려서 즉사"가 구조적으로 불가능해짐 |
| 이동 중 사격 | 이동 속도에 비례해 정확도 콘(`BulletSpreadDegrees`, 현행 자산 재사용) 확대 |
| 피제압 상태 | 피제압도(7.4절)에 비례해 콘 확대 + 수렴 시간 증가 |
| 호흡/반동 | 반동 회복 커브 + 미세 흔들림(procedural sway)을 Control Rig에서 |

이렇게 하면 "사격 타이밍"이 랜덤 타이머가 아니라 **몸 상태의 결과**가 된다. Tarkov가 2024~25
패치에서 한 것과 같은 방향이다(즉시 명중 → 시간이 걸리는 과정).

### 6.3 재장전/제스처

| 동작 | 처리 |
|---|---|
| 재장전 | 몽타주(단계별 노티파이: 탄창빼기/삽입/노리쇠) + 손 IK 일시 해제. 현행 3단계 사운드 시퀀스 자산 재사용 |
| 수신호 (정지/전진/집합/적발견) | 상체 몽타주. **분대 통신의 시각적 표현**으로 L1이 트리거(9.5절). 현행 `SetStopsignRaised` 개념의 일반화 |
| 무기 조작 (안전장치, 총열 확인, 재정렬) | 유휴 시 idle 변형으로 랜덤 재생 — "살아있는 느낌"의 저비용 고효율 요소 |
| 수류탄 | 투척 궤적 계산 + 몽타주 + Motion Warping으로 팔 목표 정렬 (2차) |
| 부상/사망 | 현행 물리 히트리액션 시스템(`../../ai_combat/enemy_hit_reaction_physics_system.md`) 이식 |

### 6.4 발사 로직

현행 `BP_AR4Rifle.Shoot()`의 구조(쿨다운/탄약 게이트/자동 재장전/탄퍼짐)는 검증된 자산이므로
**C++로 옮겨서** 그대로 쓴다. 새로 추가되는 것은 위층의 판단뿐이다:

- **버스트 길이**를 상황이 정한다: 제압사격이면 길게(6~10발), 정밀사격이면 2~3발, 탄약 부족이면
  단발. 현행은 항상 3~4 랜덤.
- **탄약 관리**를 판단에 넣는다: 잔탄이 임계 이하면 `Reload` 의도의 점수가 올라가고, 엄폐 중일
  때 더 올라간다(= 알아서 안전할 때 재장전).

### 6.5 피격 · 부상 · 사망 — MM 스택과의 접점

> **2026-09-01 개정 3에서 추가.** 초안은 "현행 히트리액션을 이식한다" 한 줄뿐이었다. 새 스택
> (MM + SmartObject 예약 + 분대 blackboard)에서는 **피격/사망이 건드려야 할 상태가 훨씬 많아진다.**

#### 6.5.1 피격 반응이 MM을 어떻게 중단하는가

MM은 "다음 프레임에 가장 잘 맞는 포즈"를 계속 고르는 시스템이라, 외부 반응을 **중단시키는
방법을 명시하지 않으면 피격 모션이 즉시 씹힌다.**

| 피격 강도 | 처리 | 이유 |
|---|---|---|
| **경미** (원거리 피탄, 방탄복 흡수) | **애디티브 상체 플린치**를 MM 위에 얹음. MM은 계속 돌아감 | 로코모션을 끊으면 오히려 부자연스럽다. 5.5.3의 "얹기" 원칙 그대로 |
| **중간** (유효타, 부상 발생) | **전용 히트리액션 MM 데이터베이스로 Chooser 스왑** — 방향별 리액션 클립을 넣어두고 MM이 방향에 맞는 것을 고름 | 몽타주로 강제 재생하면 이동 중 발이 미끄러진다. 데이터베이스 스왑이면 궤적 연속성이 유지됨 |
| **치명/사망** | **MM 완전 이탈** → 사망 몽타주 또는 래그돌(물리) 전환 | 여기서부터는 애니메이션 시스템의 관할이 아니다 |
| **넉백/폭발** | Control Rig Physics / PhysicsControl로 물리 반응 후 MM 복귀 | 2차(13절) |

**중간 강도가 이 설계의 핵심 결정이다.** 현행 `titan_example`은 몽타주 기반이고 그래서
"죽는 모션이 안 나오는" 류의 슬롯 배선 문제를 겪었다(`../../ai_combat/enemy_ai_combat_system_status.md` 4절).
MM DB 스왑 방식은 슬롯 경합 자체가 없다.

#### 6.5.2 부상 상태 모델 (`EHealthState`)

초안의 유틸리티 축에는 `체력↓` 스칼라 하나뿐이었다. 상태를 명시적으로 둔다:

```
Healthy  → Injured  → Downed  → Dead
```

| 상태 | 신체 영향 | 판단 영향 (8.3절 축으로 연결) |
|---|---|---|
| `Healthy` | — | — |
| `Injured` | 이동속도 ↓, 조준 수렴 시간 ↑(6.2절), 정확도 콘 ↑, 절뚝임 MM DB로 스왑 | `TakeCover`/`Retreat` 점수 ↑, `Advance` 점수 ↓. 분대 사기 감소 요인 |
| `Downed` | 이동 불가, 사격 불가, 포복만 | 본인은 행동 없음. **주변 아군의 `Revive`/`Assist` Intent 점수를 올림** |
| `Dead` | — | 6.5.3의 정리 절차 |

`Injured`가 있어야 `Revive`/`Assist`(8.3절, 2차)와 사기 시스템(9.4절)이 실제로 의미를 갖는다.
`Downed`를 쓸지(아군 구조 연출이 필요한지)는 시나리오 요구에 달렸으므로 **상태만 정의해두고
전이 조건은 P2에서 결정**한다.

#### 6.5.3 사망 시 정리 절차 — **반드시 전부 수행** (누락하면 버그)

병사 하나가 죽을 때 건드려야 하는 상태가 여러 시스템에 흩어져 있다. 하나라도 빠지면 조용히
망가진다. `USoldierBrainComponent::HandleDeath()`에 **단일 진입점**으로 모아둔다.

- [ ] **SmartObject 엄폐 슬롯 예약 해제** ← **가장 중요.** 안 하면 죽은 병사가 슬롯을 영구
      점유해서 아무도 그 자리를 못 쓴다(10.3절 예약 시스템의 특성상 조용히 실패한다)
- [ ] 분대 blackboard에서 자신 제거 — `AssignedSlots` 배정 해제
- [ ] **보유 중인 토큰 반환** — 제압 토큰 / 이동 토큰(9.5절). 안 하면 분대가 서서히 마비된다
- [ ] 분대 사기 갱신(9.4절 `사상자 수` 항)
- [ ] 분대장이었다면 **차순위 승계**(9.5절)
- [ ] 표적 레지스트리 등록 해제 — 현행 `UDetectableTargetSubsystem`과 같은 역할.
      **시나리오 트리거가 이 등록 해제에 의존한다**(`../../ai_combat/2026-08-31_enemy_squad_reorg.md`)
- [ ] 나를 표적으로 삼고 있던 다른 병사들의 `FThreatMemory` 무효화 → 재표적 유도
- [ ] 진행 중이던 명령(`FSoldierOrder`)의 상태 보고 갱신(11.5절 `Casualties`)
- [ ] **모든 Tick 정지** — 현행 프로젝트에서 "죽은 뒤에도 회전 보간이 계속 돌아 시체가 빙글빙글
      도는" 버그가 정확히 이걸 빠뜨려서 났다(`../../ai_combat/enemy_ai_combat_system_status.md` 4절)
- [ ] 무기 분리 + 물리 활성화 + 지연 후 정리 (현행 로직 패턴 재사용)

> 현행 프로젝트가 이 목록의 절반을 **버그로 발견하며** 하나씩 채웠다. 새 프로젝트는 처음부터
> 체크리스트로 들고 간다.

---

## 7. 인지(Perception) (요구항목 3)

### 7.1 채택: UE AIPerception을 베이스로 하되, "감지 = 시간이 걸리는 과정"으로 교체

`UAIPerceptionComponent`의 Sight/Hearing/Damage 감각을 **감지 이벤트 소스**로만 쓰고, 그 위에
자체 **인지 누적 모델(awareness accumulator)** 을 얹는다.

```
매 인지 틱, 각 후보 대상마다:
    visible = 시야각/거리/차폐(트레이스) 통과 여부
    if visible:
        rate = f(거리) · f(각도-주변시야) · f(대상 이동속도) · f(대상 은엄폐도) · f(조명/기상)
        awareness += rate · dt
    else:
        awareness -= decayRate · dt        ← 즉시 0이 아니라 점진 감소
    awareness ∈ [0,1] 을 3구간으로 해석:
        0.0~0.3  Unaware       (모름)
        0.3~0.7  Suspicious    ("뭔가 있다" — 그 방향을 본다, 경계 자세)
        0.7~1.0  Confirmed     (표적으로 확정, 분대에 공유)
```

**근거**:
- Tarkov가 2024~25 패치에서 정확히 이 방향으로 갔다: 거리가 멀수록 인지에 시간이 더 걸리고,
  주변시야에 있으면 덜 보이고, 시야를 벗어나도 **점진적으로** 잃는다. 그 전의 "임계선을 넘는
  순간 즉시 인지"가 봇이 에임봇처럼 느껴지던 원인이었다.
- TLOU 계열도 같은 3단계 인지(모름/의심/확정) 구조를 쓴다.
- 현행 시스템은 **스피어 오버랩 = 즉시 표적 확정**이다. 이것이 "기계적"으로 느껴지는 가장 큰
  단일 원인이라고 본다.

### 7.2 시야

| 파라미터 | 설계 |
|---|---|
| 중심시(foveal) | ±15°, 인지율 배수 1.0 |
| 주변시(peripheral) | ±15~60°, 배수 0.3~0.7 (각도에 따라 감쇠) |
| 최대 시야 | ±110° 정도, 배수 ~0.1 |
| 거리 | 100m까지 유효, 인지율은 거리 제곱에 반비례에 가깝게 감쇠 |
| 차폐 | 눈 위치 → 대상의 3~5개 샘플점(머리/가슴/어깨) 트레이스. **부분 가시**를 0~1 비율로 |
| 시선 방향 | 조준방향과 별개로 **머리 회전(look-at)** 을 따로 둔다 → 스캔 행동(주변 훑기)이 인지에 실제로 영향 |

### 7.3 청각

- 총성/발소리/폭발/무전을 `UAISense_Hearing` 이벤트로 발생.
- **감쇠에 차폐 반영**: 소리 발생점→귀 사이 벽이 있으면 유효 거리 축소(Tarkov 모델).
- 청각은 **방향 정보만** 준다 — 위치가 아니라 "그 방향에 뭔가 있다". 이것이
  `LastKnownPosition`의 정확도를 낮추고, 그 결과 "대략적인 방향으로 경계하며 접근하는" 자연스러운
  행동이 나온다.

### 7.4 기억 — `FThreatMemory`

각 병사는 표적별로 다음을 기억한다:

```cpp
struct FThreatMemory
{
    TWeakObjectPtr<AActor> Target;
    FVector   LastKnownLocation;      // 마지막 목격 위치
    FVector   LastKnownVelocity;      // 마지막 목격 속도 (추정 이동 예측용)
    float     Confidence;             // 0~1, 시간이 지나면 감쇠
    float     TimeSinceLastSeen;
    float     Awareness;              // 7.1의 누적값
    bool      bSharedBySquad;         // 내가 직접 봤나, 분대가 알려줬나  ← TLOU의 개인지식/집단지식 구분
    float     ThreatLevel;            // 나에게 얼마나 위험한가 (거리·무기·조준여부)
};
```

- `Confidence` 감쇠 → 시간이 지나면 "거기 있을 것 같은데 확실치 않다" → `PeekCheck` 의도의 점수
  상승 → 확인하러 감. **이게 "살아있는" 행동의 핵심 부품이다.**
- `LastKnownLocation + LastKnownVelocity · t`로 추정 위치를 갱신하면, 놓친 적을 **추적하는** 행동이
  공짜로 나온다.
- `bSharedBySquad`를 구분하는 이유(TLOU 계보): 남이 알려준 정보는 신뢰도가 낮아야 자연스럽고,
  "직접 확인하러 간다"는 행동의 근거가 된다.

### 7.5 피탐지 확률 — 반대 방향의 모델

내가 남에게 얼마나 잘 보이는가(`Exposure`)를 병사마다 매 틱 계산해 둔다:

```
Exposure = f(자세: 서기1.0 / 앉기0.6 / 엎드리기0.35)
         · f(엄폐물에 의한 가림 비율)
         · f(이동 속도: 정지 0.7 / 걷기 1.0 / 달리기 1.4)
         · f(사격 중: 총구 화염/소음 → 1.5)
         · f(조명·연막)
```

- 7.1의 인지율 계산에 `대상.Exposure`가 곱해진다.
- **동시에 8절 유틸리티의 "생존" 축 입력이 된다** — 즉 병사가 "지금 내가 너무 노출됐다"를
  스스로 알고 엄폐를 고른다. 인지 모델과 판단 모델이 같은 숫자를 공유하는 것이 이 설계의
  경제성이다.

---

## 8. 개별 판단(의사결정) (요구항목 4)

### 8.1 후보 비교

| 방식 | 강점 | 이 문제에서의 약점 | 대표 사례 |
|---|---|---|---|
| **비헤이비어 트리** | 성숙, 디버깅 툴, 인력 친숙 | **우선순위가 트리 구조에 하드코딩**된다. "보통은 엄폐가 먼저지만 탄약 충분하고 적이 노출됐으면 사격이 먼저"같은 걸 표현하려면 조건 노드가 폭발한다 | 대다수 UE 프로젝트 |
| **StateTree** | BT+FSM 하이브리드, 5.8 정식, 데이터 바인딩, 디버거 | 위와 같은 한계를 공유(선택이 구조에 묶임). **다만 실행 표현력은 BT보다 좋다** | UE 네이티브 |
| **GOAP** | 목표에서 역방향 계획, 창발적 시퀀스 | 월드 상태를 심볼로 표현해야 하고 플래너 디버깅이 어렵다. **우리 문제는 계획 길이가 2~3단계로 짧다** — 계획기의 이점이 거의 안 나온다 | F.E.A.R. |
| **HTN** | 분대급 다단계 전술 계획에 강함, 실시간 성능 검증됨(500 plan/s) | 도메인 저작 비용이 크다. 개인 레벨엔 과함 | Killzone 2/3 |
| **유틸리티(IAUS)** | 상황을 **연속값**으로 다룸. 행동 추가가 기존을 안 부순다. 개체차(성격/숙련도)를 커브로 표현 | 튜닝 감각 필요, **디버깅 UI 없으면 지옥** | Dave Mark 계열, 다수 AAA |

### 8.2 결정: 유틸리티(판단) + StateTree(실행) 2계층, 분대는 플랜 템플릿

```
L2 BRAIN   =  유틸리티 스코어러  →  Intent 하나 선택
L3 ACT     =  Intent 하나당 StateTree 서브트리 →  실제 태스크 수행
L1 SQUAD   =  HTN에서 아이디어만 차용한 "전술 플랜 템플릿" 선택 (9.2절)
```

**왜 이 조합인가:**

1. **판단과 실행은 성질이 다르다.** "지금 엄폐할까 쏠까"는 연속적 상황 평가 문제(유틸리티가
   최적)이고, "엄폐하러 간다"는 순차적·중단 가능한 절차 문제(StateTree가 최적)다. 하나로 합치면
   둘 중 하나가 망가진다. 현행 시스템은 이 둘을 합쳐놓았고, 그래서 판단 자리에 랜덤 타이머가
   들어가 있다.
2. **GOAP을 안 쓰는 이유**: F.E.A.R.의 GOAP가 빛난 지점은 "문이 잠겼으면 창문으로 돈다" 같은
   *대체 경로 계획*이다. 우리 시나리오(개활지/시가지 진지 전투)는 행동 시퀀스가 짧고, 대신
   **위치 선택의 질**이 품질을 좌우한다. 계획기보다 공간 질의(EQS)에 투자하는 게 옳다.
3. **StateTree 단독을 안 쓰는 이유**: 5.8에서 정식이고 툴도 좋지만, 상태 선택 로직이 여전히
   트리 구조 + 조건이다. C2 제약을 그대로 재현한다. 다만 **실행 레이어로는 최적**이다 —
   태스크·전환·데이터 바인딩·디버거가 다 있고, Smart Object/EQS와의 통합이 네이티브다.
4. **유틸리티는 개체차를 공짜로 준다.** 같은 스코어러에 커브 파라미터만 다르게 주면 "겁 많은
   신병 / 침착한 정예 / 공세적인 분대장"이 나온다. 이게 "병사 하나하나가 살아있는 것처럼"이라는
   목표에 직결된다.

### 8.3 Intent 목록과 스코어링 축

각 Intent는 여러 축(Consideration)의 점수를 곱한다(IAUS 방식 — 곱셈이라 하나라도 0이면 탈락).

| Intent | 주요 축 | 대략적 스코어 형태 |
|---|---|---|
| `TakeCover` | 자기 노출도↑, 피격 최근성↑, 피제압도↑, 유효 엄폐 슬롯 가용성↑, 체력↓ | 노출 커브(볼록) × 슬롯가용(0/1) × (1-현재엄폐질) |
| `AimedFire` | 표적 신뢰도↑, 표적 노출도↑, 조준 수렴도↑, 탄약↑, 사격선 청결(아군 없음) | 신뢰도 × 표적노출 × 탄약커브 × 사격선 |
| `SuppressiveFire` | 분대 제압 요청↑, 표적 대략 위치 알려짐, 탄약 여유↑, 아군 기동 중↑ | 분대토큰(0/1) × 탄약커브 × 아군기동 |
| `Reposition` | 현재 위치 노출도↑, 표적 각도 불리↑, 더 나은 슬롯 존재↑, 적 근접↓ | (더나은슬롯점수 - 현재슬롯점수) 정규화 |
| `Advance` | 명령 공세성↑, 분대 사기↑, 엄호사격 진행 중↑, 목표까지 거리↑ | 명령 × 사기 × 엄호존재 |
| `Retreat` | 체력↓, 분대 사기↓, 탄약↓, 명령 철수↑, 수적 열세↑ | (1-체력) × (1-사기) |
| `Reload` | 잔탄↓, 위협 임박도↓(안전할 때), 엄폐 중↑ | 잔탄역커브 × 안전도 |
| `PeekCheck` | 표적 신뢰도 중간대(0.3~0.7)↑, 시간 경과↑, 위협 낮음 | 신뢰도의 중간 볼록 커브 |
| `Regroup` | 분대와 거리↑, 고립도↑, 명령 집합↑ | 거리커브 × 고립도 |
| `Grenade` | 표적 엄폐 중↑, 거리 적정, 아군 안전, 수류탄 보유 | (2차) |
| `Revive`/`Assist` | 아군 부상 근접, 위협 낮음 | (2차) |

> **부상 상태(6.5.2절)의 연결**: 위 표의 `체력↓` 축은 스칼라 하나가 아니라 `EHealthState`
> (Healthy/Injured/Downed/Dead)와 함께 쓴다. `Injured`는 `TakeCover`/`Retreat`를 올리고
> `Advance`를 내리며, 근처 아군의 `Revive`/`Assist` 점수를 올린다.

**히스테리시스**: 현재 Intent의 점수에 `+10~15%` 보너스를 준다. 없으면 두 행동 점수가 비슷할 때
매 틱 진동한다(유틸리티 AI의 대표적 실패 모드).

**최소 지속시간**: Intent마다 최소 유지 시간(0.5~2초)을 둔다. 단, `TakeCover`/`Retreat` 같은
생존 계열은 이를 무시하고 끼어들 수 있다(우선순위 인터럽트).

### 8.4 엄폐 위치 선정 / 사격 타이밍 / 기동 판단이 여기서 나오는 방식

- **엄폐 위치**: `TakeCover`/`Reposition` Intent가 선택되면 L3가 EQS 질의를 발행(10절). 질의
  결과의 최고 점수 슬롯을 Smart Object로 예약한다. **"어디로"는 유틸리티가 아니라 공간 질의가
  답한다** — 역할 분담이 명확하다.
- **사격 타이밍**: `AimedFire` Intent가 선택되고 → StateTree가 조준 → 6.2절의 수렴 조건 충족 →
  발사. 즉 타이밍은 (판단 점수) × (몸의 물리적 준비 상태)의 합작이다.
- **전진/후퇴/측면**: `Advance`/`Retreat`는 개인 유틸리티에도 있지만, **측면기동(flank)은 분대
  레벨 결정**이다(9절) — 혼자 측면을 도는 건 자살이고, 실제 전술에서도 분대 단위다. 개인은
  분대가 준 회랑 안에서 `Advance`를 실행한다.

### 8.5 구현 스케치

```cpp
// 축(Consideration): 입력값 → 0~1 커브
USTRUCT()
struct FConsideration
{
    FName            InputName;        // "SelfExposure", "TargetConfidence", ...
    EResponseCurve   Curve;            // Linear/Quadratic/Logistic/Logit
    float            Slope, Exponent, XShift, YShift;   // IAUS 표준 4파라미터
    float            Evaluate(float RawInput) const;
};

USTRUCT()
struct FIntentDefinition
{
    FGameplayTag              IntentTag;        // Intent.TakeCover 등
    TArray<FConsideration>    Considerations;
    float                     BaseWeight = 1.f;
    float                     MinDurationSec = 0.5f;
    TObjectPtr<UStateTree>    ExecutionTree;    // L3에서 실행할 서브트리
};

// 스코어링: 곱셈 + 보정 계수(축 개수가 많을수록 불리해지는 것을 상쇄 — IAUS의 make-up value)
float Score = BaseWeight;
for (const FConsideration& C : Considerations) Score *= C.Evaluate(Blackboard.Get(C.InputName));
const float Modification = (1.f - 1.f / Considerations.Num());
Score = Score + (1.f - Score) * Modification * Score;
```

`FIntentDefinition`은 DataAsset으로 두고, **커브 파라미터를 에디터에서 실시간 조정**할 수 있게
한다(3.7절 `Debug/`의 글래스박스 UI가 여기 붙는다).

---

## 9. 분대/팀 협동 (요구항목 5)

### 9.1 채택: 하이브리드 (분대는 배분, 개인은 결정)

"Believable Tactics for Squad AI"가 비교한 중앙집중형/분산형 중 **중앙은 자원 배분만, 실행은
분산**을 택한다.

- **중앙집중형의 문제**: 분대장 AI가 모든 걸 지시하면 개인이 로봇이 된다(우리가 벗어나려는
  바로 그 상태).
- **완전 분산형의 문제**: 다섯 명이 같은 엄폐물로 몰리고, 아무도 엄호를 안 하고, 다 같이
  재장전한다.
- **하이브리드**: 분대는 (a) **슬롯/역할**, (b) **회랑(영역)**, (c) **토큰**(제압사격 인원 상한,
  동시 이동 인원 상한)만 배분한다. 개인은 그 제약 안에서 유틸리티로 자유 판단.

Killzone 2/3의 "분대 플래너가 전략 경로를 회랑으로 내려주고 개인이 그 안에서 판단"과 정확히
같은 구조다.

### 9.2 분대 전술 플랜 템플릿

L1은 명령 + 상황을 보고 플랜 하나를 고른다(HTN의 "메서드"에서 아이디어를 차용하되, 계획기 없이
스코어 기반 선택):

| 플랜 | 조건 | 역할 배분 |
|---|---|---|
| `Hold` | 방어 명령, 적 미확인 | 전원 경계 슬롯, 부채꼴 시야 분담 |
| `BaseOfFire` (정면 제압) | 교전 명령, 적 위치 확인, 사기 보통↑ | 전원 사격 슬롯, 제압 토큰 N개 순환 |
| `BoundingOverwatch` | 전진 명령 + 적과 접촉 중 | 팀 A 엄호(정지·사격) ↔ 팀 B 전진, 도착하면 교대 |
| `Flank` | 교전 중 + 측면 경로 존재 + 사기 높음 | 고정조(제압) + 기동조(회랑 따라 측면) |
| `Withdraw` | 사기 낮음 or 철수 명령 | 후위 엄호조 + 이탈조, 교대 후퇴 |
| `Regroup` | 분대 분산도 높음 | 집결점으로 수렴 |

바운딩 오버워치는 Arma/Squad 계열 전술의 표준이고, "한 조가 쏘는 동안 다른 조가 움직인다"는
F.E.A.R.가 1개 분대 수준에서 이미 보여준 가장 인상적인 창발 행동이다.

### 9.3 분대 blackboard (공유 정보)

```cpp
struct FSquadBlackboard
{
    TArray<FSharedThreat>   KnownThreats;      // 누가 봤는지, 신뢰도, 마지막 위치
    TArray<FSquadSlot>      AssignedSlots;     // 슬롯 → 멤버 배정
    float                   Morale;            // 0~1  (Days Gone 계보)
    int32                   SuppressionTokens; // 동시 제압사격 인원 상한
    int32                   MovementTokens;    // 동시 이동 인원 상한 (= 항상 누군가는 엄호 중)
    FVector                 FriendlyCentroid, EnemyCentroid;   // 공간 분석
    FBox                    AssignedCorridor;  // 상위 명령이 준 영역 제약
    EPlanType               CurrentPlan;
};
```

**표적 정보 공유**: 개인의 `Awareness`가 `Confirmed`에 도달하면 분대 blackboard에 올린다. 다른
멤버는 그것을 `bSharedBySquad=true`, `Confidence=0.6` 정도로 받는다(직접 본 것보다 낮게).
→ "무전으로 알려줬지만 나는 아직 못 봤다"가 자연스럽게 표현된다.

### 9.4 사기(Morale) — 분대 행동의 구동축

Days Gone이 분대 사기를 명시적 수치로 두고 분대 행동을 구동한 것을 그대로 채택한다.

```
Morale ← 초기값(명령의 공세성) 
       - 사상자 수 × w1
       - 피제압 총량 × w2
       - 수적 열세 × w3
       + 적 사상 × w4
       + 분대장 생존 × w5
       + 아군 지원(UGV/화력) 근접 × w6
```

- `Morale`이 임계 이하 → 플랜이 `Withdraw`로, 개인 유틸리티의 `Retreat` 축도 같이 올라감.
- 이것으로 **"1분대는 1차 전투지에서 전멸"** 같은 현행 시나리오 연출을 하드코딩된
  `LastStandZoneIndex` 게이트 대신 **사기 파라미터**로 표현할 수 있다(예: "1분대는 사기 하한이
  높아 후퇴하지 않는다" = 결사 항전). 이게 명령 인터페이스가 지향하는 방향이다.

### 9.5 제압사격 분담과 중복 방지

| 문제 | 해법 |
|---|---|
| 동시에 다 쏘고 다 재장전 | **제압 토큰**: 동시에 `SuppressiveFire`를 수행할 수 있는 인원 상한. 토큰을 못 받으면 그 Intent 점수가 0 |
| 동시에 다 움직임 | **이동 토큰**: 상한 이하로만 동시 이동. 나머지는 자동으로 엄호 상태 유지 → 바운딩 오버워치가 토큰만으로 창발 |
| 같은 엄폐물 중복 선점 | **Smart Object 예약 시스템**(10.3절) — UE 네이티브 기능. 슬롯을 예약하면 다른 에이전트가 못 씀 |
| 사격선에 아군 | 현행 `FireLaneAllyMarginCm` 로직을 이식 + `AimedFire` 유틸리티 축으로 승격 |
| 분대장-팀원 역할 | 분대장은 (a) 명령 해석·플랜 선택 주체, (b) 수신호 재생 주체, (c) 사기 보너스 원천. 사망 시 차순위 승계 |

---

## 10. 엄폐 시스템 (요구항목 6)

### 10.1 3층 구조

```
[층 1] 슬롯 생성 (Cover Slot Generation)      — 어디에 엄폐 가능 지점이 있는가
[층 2] 슬롯 평가 (Tactical Query / EQS)       — 지금 상황에서 어느 슬롯이 좋은가
[층 3] 슬롯 점유 (Smart Object Reservation)   — 그 슬롯을 내가 쓴다고 선언하고 진입
```

이 3층 분리는 Game AI Pro Ch.26(Crytek TPS)의 **Generation / Conditions+Weights / 사용**과 정확히
같은 분해이며, UE의 EQS가 이미 이 모양이라 임피던스가 없다.

### 10.2 층 1 — 엄폐 슬롯을 어떻게 뽑는가

**하이브리드: 오프라인 베이크(정적) + 런타임 등록(동적).**

| 소스 | 방법 | 근거 |
|---|---|---|
| **정적 지오메트리** | 에디터 커밋렛/툴로 NavMesh 경계를 훑으면서, 경계 바깥쪽으로 트레이스를 쏴서 벽/장애물을 찾고, 높이별로(엎드림 40cm / 앉기 100cm / 서기 180cm) 차폐 여부를 판정. 통과하면 그 지점에 **Smart Object 슬롯**을 자동 생성 | 런타임 계산은 비싸다. "NavMesh 경계 = 장애물이 있는 곳"이라는 무료 정보를 쓴다. UE4 시절 CoverGenerator 플러그인들이 검증한 접근 |
| **슬롯 메타데이터** | 각 슬롯이 `CoverHeight(Low/High)`, `LeanLeft/Right 가능`, `OverTop 사격 가능`, `벽 법선`, `연결된 NavMesh 폴리` 를 들고 있음 | 5.4절의 자세 전환과 6절 조준이 이 데이터를 직접 씀 |
| **동적 장애물** (차량, UGV, 파괴 잔해) | 액터에 `UCoverProviderComponent`를 붙이면 자기 슬롯을 런타임에 Smart Object 서브시스템에 등록/해제 | 우리 프로젝트는 UGV가 전장을 돌아다닌다 — 움직이는 엄폐물이 필수 |
| **파괴/변형** | 슬롯 무효화 이벤트 → 점유 중인 병사에게 즉시 재평가 신호 | |
| **수동 저작** | 사람이 특정 지점을 강제로 슬롯으로 지정(연출용) | 현행 마커 시스템의 상위호환 — 하위호환 경로 |

> **현행 마커 시스템과의 관계**: 기존 `FiringPose.Marker`/`CoverPose.Marker`는 "수동 저작 슬롯"
> 하나로 흡수된다. 즉 **이식 시 기존 레벨 저작이 버려지지 않는다.**

### 10.3 층 3 — 왜 Smart Objects인가 (중복 선점 문제의 근본 해결)

UE Smart Objects는 **예약(reservation) 시스템을 내장**한다 — 에이전트가 슬롯을 예약하면 그
슬롯이 해제될 때까지 다른 에이전트가 쓸 수 없다. "같은 엄폐물 중복 선점 방지"라는 요구사항이
자체 클레임 시스템을 만들지 않고 **엔진 기능으로 해결된다.**

추가로:
- Smart Object는 **슬롯에 행동(behavior)을 붙일 수 있다** — F.E.A.R.의 "스마트오브젝트가 애니메이션을
  들고 있다" 구조와 같은 계보. 엄폐 슬롯이 "여기 진입할 때 재생할 애니메이션"과 "여기서 가능한
  사격 자세"를 직접 들고 있게 만들 수 있다.
- StateTree와 네이티브 통합된다(GameplayInteractions는 Experimental이므로, 우리는 SmartObject
  서브시스템 API를 직접 쓰고 StateTree 태스크는 자체 작성한다).

### 10.4 층 2 — EQS 질의 설계

```
Query: FindCoverAgainstThreats
  Generator: 반경 R 내 등록된 Cover Slot (커스텀 Generator — Smart Object 서브시스템 조회)
  Conditions (전부 통과해야 유효 = TPS의 Conditions):
    - 예약되지 않았을 것
    - NavMesh로 도달 가능할 것 (경로 존재)
    - 분대가 준 회랑(AssignedCorridor) 안일 것
    - 주 위협 방향에 대해 실제로 차폐될 것 (슬롯 법선 vs 위협 방향)
  Weights (0~1 정규화 후 가중합 = TPS의 Weights):
    + 위협 차폐도                       ×  3.0
    + 사격 가능성(엄폐에서 표적을 볼 수 있나 — lean/over-top 포함)  × 2.5
    + 이동 비용(가까울수록 좋음, 이동 중 노출 시간)                × 2.0
    + 분대 응집(다른 멤버와 적정 간격 — 너무 붙어도 감점)          × 1.0
    + 목표 방향 전진성(명령이 공세적일 때만 가중)                  × 0~1.5
    - 다른 위협에 대한 노출                                        × 2.0
    - 최근에 있던 자리(같은 자리 반복 방지)                        × 0.5
```

- **핵심 트레이드오프는 "차폐 vs 사격 가능성"** 이다. 완벽히 숨으면 못 쏜다. 이 두 가중치의
  비율이 병사 성향(공세적/방어적)을 결정한다 → 명령 파라미터로 노출(11절).
- **성능**: EQS는 중앙 매니저가 프레임당 시간 예산(`Max Allowed Time Per Frame`, 기본값 조정)으로
  타임슬라이싱한다. 우리는 전역 3ms로 잡고, 질의는 전부 비동기로 발행한다(12절).

### 10.5 "완벽한 엄폐"만 찾지 않는다

TPS/EQS 계열의 함정은 최적 지점만 고르면 전원이 같은 곳으로 몰리고 행동이 예측 가능해진다는
것이다. 대응:
- 상위 N개(예: 상위 3개) 중 점수 가중 랜덤 선택.
- 병사별 성향 노이즈(±10%).
- 최근 점유 위치 감점(위 질의의 마지막 항).

---

## 11. 명령 인터페이스 (요구항목 7)

### 11.1 설계 원칙

> **명령은 "무엇을 원하는가"와 "어떤 제약 아래에서"만 말한다. "어떻게"는 절대 말하지 않는다.**

현행 `EScenarioEffectType`은 이 원칙의 정반대다:

| 현행 | 문제 | 새 스키마에서 |
|---|---|---|
| `BeginEnemyFleeZone2` | 대상(적 전원) + 행동(도주) + 목적지(zone2)가 한 덩어리로 고정 | `Order{ Recipient: Squad(1,2,3), Verb: Withdraw, Target: Zone(2) }` |
| `RetargetEnemiesToCommandPost` | "표적을 X로 바꿔라"는 개인 판단 영역 침범 | `Order{ Verb: Engage, Target: Actor(CommandPost), Priority: High }` — 병사는 그래도 자기가 위협 판단 |
| `BeginAllyFormUpAndAdvance` | 대형+전진이 한 덩어리 | `Order{ Verb: Advance, Target: Location, Params:{ Formation: Wedge } }` |
| `MoveUGVToZone2Destination` | 차량 전용 하드코딩 | `Order{ Recipient: Vehicle(UGV1), Verb: MoveTo, Target: Zone(2) }` |

새 enum이 계속 늘어나는 대신, **동사 × 대상 × 파라미터의 조합**으로 표현이 폭발한다.

### 11.2 스키마

```cpp
UENUM(BlueprintType)
enum class EOrderVerb : uint8
{
    None,
    MoveTo,       // 지정 위치/구역으로 이동 (교전은 부차적)
    Occupy,       // 구역을 점령·확보하고 방어 태세
    Engage,       // 지정 대상/구역과 교전 개시
    Suppress,     // 지정 구역/대상을 제압 (명중보다 억제 우선)
    Advance,      // 교전하면서 전진 (바운딩 오버워치 자동 선택 가능)
    Withdraw,     // 이탈 — 교대 엄호 포함
    HoldFire,     // 사격 금지 (교전규칙만 바꿈)
    Regroup,      // 집결
    Overwatch,    // 지정 방향/구역 감시, 접촉 시 교전
    Follow,       // 지정 액터 동행 (현행 UGV 동행 대체)
};

UENUM(BlueprintType)
enum class EOrderRecipientType : uint8 { Squad, Element, Individual, AllOfFaction };

USTRUCT(BlueprintType)
struct FOrderTarget                 // 목표는 4가지 중 하나
{
    EOrderTargetType Type;          // Location / Actor / Zone / Direction
    FVector          Location;
    TWeakObjectPtr<AActor> Actor;
    FName            ZoneId;        // 레벨의 전투구역 볼륨 이름
    FVector          Direction;
};

USTRUCT(BlueprintType)
struct FOrderConstraints            // "어떻게"가 아니라 "어떤 범위 안에서"
{
    EEngagementRule  ROE = Free;          // Free / ReturnFireOnly / HoldFire / PositiveIDRequired
    float            Aggression = 0.5f;   // 0=최대한 안전하게, 1=속도 우선  → 10.4 가중치에 직접 영향
    float            MoraleFloor = 0.f;   // 이 이하로는 안 무너짐 (결사항전 연출용, 9.4절)
    EFormationType   Formation = Wedge;   // Column/Wedge/Line/Diamond  (Ready or Not 계보)
    FName            CorridorId;          // 이동 회랑 (Killzone 계보). 비우면 자유
    float            StandoffDistance = 0.f;  // 목표에 이 거리 이상 붙지 말 것
    bool             bAllowFlanking = true;
};

USTRUCT(BlueprintType)
struct FSoldierOrder
{
    FGuid                 OrderId;
    EOrderRecipientType   RecipientType;
    FName                 RecipientId;     // SquadId, ElementId, 액터 태그
    EOrderVerb            Verb;
    FOrderTarget          Target;
    FOrderConstraints     Constraints;
    int32                 Priority = 0;     // 높을수록 기존 명령을 덮어씀
    float                 ExpiresAfterSec = 0.f;   // 0 = 무기한
    FName                 SourceStepId;     // 시나리오 스텝 추적용(디버깅)
};
```

### 11.3 명령이 자율 행동으로 번역되는 경로

```
FSoldierOrder
   → USoldierCommandSubsystem 이 수신자 분대에 배달 (우선순위/만료 관리)
   → USquadComponent: Verb + 현재 상황 → 전술 플랜 선택 (9.2절)
        예) Verb=Advance + 적과 접촉 중 + 사기 높음      → BoundingOverwatch
            Verb=Advance + 접촉 없음                     → 대형 이동
            Verb=Engage  + 측면 경로 존재 + 사기 높음    → Flank
            Verb=Engage  + 사기 낮음                     → BaseOfFire (제자리 제압)
   → 플랜이 슬롯/역할/토큰/회랑을 개인에게 배분
   → 개인 유틸리티가 그 제약 하에서 매 판단 틱 스스로 결정 (8절)
   → StateTree가 실행, Motion 레이어가 몸을 만듦
```

**명령이 바뀌면 그 즉시 유틸리티 축의 입력값이 바뀔 뿐이다** — 상태를 강제로 갈아끼우지 않는다.
그래서 "교전 중 철수 명령"이 와도 병사는 버스트를 마치고 엄폐를 확보한 뒤 이탈하는, 자연스러운
전이를 스스로 만든다.

### 11.4 titan_example 시나리오 시스템과의 접속 (나중)

기존 `FScenarioStepRow`에 **이펙트 타입 딱 하나만 추가**하면 된다:

```
EScenarioEffectType::IssueOrder   +  FSoldierOrder 를 담는 필드(또는 별도 Order DataTable의 RowName 참조)
```

- 기존 28개 effect enum은 **그대로 두고**(하위호환), 새 연출부터 `IssueOrder`로 저작한다.
- 기존 effect들을 하나씩 `IssueOrder` 조합으로 재작성하는 마이그레이션은 선택적·점진적.
- 트리거(`EScenarioTriggerType`) 쪽은 **손대지 않는다** — 그쪽은 이미 "언제"만 다루고 있고 잘
  동작한다(2026-08-31 문서의 결론과 동일).

### 11.5 명령 인터페이스가 제공해야 하는 피드백(역방향)

상부가 명령만 내리고 결과를 모르면 시나리오를 못 짠다. 최소한의 상태 보고를 정의한다:

```cpp
struct FOrderStatusReport
{
    FGuid    OrderId;
    EOrderStatus Status;   // Received / InProgress / Achieved / Failed / Aborted
    float    Progress;     // 0~1 (예: 목표 구역까지의 진척)
    int32    Casualties;
    float    SquadMorale;
    FVector  SquadCentroid;
    int32    ConfirmedEnemyCount;
};
```

이게 있으면 시나리오 트리거를 `EnemyCasualtyCountAtLeast` 같은 저수준 카운터 대신
`OrderStatus(1분대, Occupy Zone1) == Achieved`처럼 **의미 단위**로 쓸 수 있다.

---

## 12. 성능/스케일 목표 (요구항목 8)

### 12.1 목표치

| 항목 | 목표 | 근거 |
|---|---|---|
| 동시 병사 수 | **45명** (아군 30 + 적군 15) — `titan_example` 현행 규모와 동일 | 이식이 최종 목표이므로 같은 규모에서 성립해야 의미가 있음 |
| 스트레치 목표 | 64명 | 여유 마진 |
| 프레임 목표 | **60 fps** (16.6ms) | 현행 프로젝트 기준 |
| 대상 하드웨어 | 데스크톱 GPU(RTX 4070급) + 8코어 CPU. 개발 PC 기준 | 이 프로젝트는 시연/시뮬레이션용이지 콘솔 출하가 아님 |
| CPU 예산 (AI+애님 합계) | **≤ 5.0 ms / frame** | 전체 16.6ms 중 렌더 스레드/게임 나머지를 감안 |

### 12.2 예산 분해

| 항목 | 예산 | 방법 |
|---|---|---|
| 애니메이션 평가 (MM + IK) | 2.5 ms | 아래 LOD 티어 + Animation Budget Allocator |
| 인지 (트레이스 포함) | 0.7 ms | 10Hz, 라운드로빈으로 프레임 분산, 후보 선필터(거리/각도)로 트레이스 수 억제 |
| 유틸리티 판단 | 0.3 ms | 4~10Hz. 축 계산은 대부분 캐시된 스칼라 |
| StateTree 실행 | 0.5 ms | 30Hz 이하 |
| EQS | 0.7 ms | 전역 타임슬라이스 예산 + 비동기. 슬롯 후보를 반경/그리드로 선필터 |
| 이동/경로 (CMC + Detour Crowd) | 1.0 ms | 경로 재계산 빈도 제한 |
| 분대 조율 | 0.1 ms | 2~4Hz |

### 12.3 3-티어 LOD

| 티어 | 대상 | 애니메이션 | AI |
|---|---|---|---|
| **T0 — 근접/주시 중** (≤8명) | 카메라 30m 이내 또는 화면 중앙 | 풀 MM + 전체 워핑(Orientation/Stride/Slope) + 풀바디 IK(발/손/총구 정렬) + Look-At 솔버 | 판단 10Hz, 인지 10Hz, EQS 전체 |
| **T1 — 중거리** (~20명) | 30~80m | MM(축소 DB, Chooser로 스와핑) + Orientation/Stride Warping + 발 IK. 총구 정밀 정렬·Look-At 생략 | 판단 5Hz, 인지 5Hz, EQS 간소화 질의 |
| **T2 — 원거리/비가시** (나머지) | 80m+ 또는 컬링됨 | URO(프레임 스킵) + 단순 블렌드스페이스. Animation Sharing 후보 | 판단 2Hz, 인지 2Hz(트레이스 대폭 축소), 엄폐는 캐시된 슬롯 사용 |

- 티어 결정은 `SignificanceManager`로. 애님 비용 상한은 `AnimationBudgetAllocator`가 전역으로
  강제(설정한 ms 예산을 넘으면 자동으로 URO를 올림).
- **IK 노드는 LOD Threshold로 끈다** — 원거리 캐릭터의 발 IK/조준 보정은 눈에 안 보이는데 비싸다.

### 12.4 확장성 판단 — 왜 Mass가 아닌가

45~64명은 **일반 Actor + 컴포넌트로 충분히 감당되는 규모**다. Mass Entity로 가면:
- 스켈레탈 메시 개체별 고품질 애님(MM + Control Rig)과의 통합이 여전히 미성숙(MassCrowd는
  ISM/VAT 기반 군중용).
- MassAI/ZoneGraph가 5.8에서도 Experimental이고, 5.8에서 프로세서 실행이 대폭 개편되는 등
  API가 아직 움직이고 있다.
- 우리 요구는 "많은 병사"가 아니라 **"진짜 같은 병사"** 다. 축이 다르다.

수백 명 규모가 필요해지면 그때 T2 티어만 Mass로 내리는 하이브리드가 정석 경로다 — 이 설계는
티어가 분리돼 있어 그 교체가 국소적이다.

---

## 13. 의도적으로 채택하지 않은 것들

각 항목에 대해 "왜 지금은 아닌가"와 "언제 재검토하는가"를 남긴다.

| 기술 | 왜 지금은 아닌가 | 재검토 시점 |
|---|---|---|
| **상체/하체 레이어 블렌드 방식** (ALS 오버레이, Lyra의 Linked Anim Layer, GASP-ALS) | **이 프로젝트가 이미 실패로 확인한 방식**(5.5.1절). 로코모션은 발맞춤에 동기화된 전신 움직임이라 상체만 다른 클립으로 갈아끼우면 상체가 붕 뜬다. UE 슈터 템플릿 대다수가 이 방식이라 자료가 많지만, 그게 이 방식이 맞다는 근거는 아니다 | 채택하지 않음. 다만 GASP-ALS는 **"왜 안 되는지" 비교 실험용**으로 볼 수 있다(5.8절) |
| **Mover / ChaosMover** | 5.8에서 크게 개선됐지만 여전히 Experimental. CharacterMovementComponent를 갈아엎으면 현행 검증된 이동/충돌 로직(RVO, 겹침 밀어내기, 정체 감지 재탐색)을 전부 재작성해야 한다. 그 위험을 이번 R&D에 얹을 이유가 없다. **단 GASP 5.7부터 Mover 기반 캐릭터가 샘플에 포함**되므로, GASP 갱신을 따라갈지 여부는 별도 판단이 필요하다 | Mover가 정식 등급이 되면. 또는 ChaosMover의 궤적 예측이 5.3절 자체 구현보다 명확히 나을 때 |
| **UAF / AnimNext** | Experimental v0.1. GASP가 5.8에서 UAF 캐릭터를 포함하기 시작했다는 건 방향성은 확실하다는 뜻이지만, R&D의 토대로 삼기엔 이르다 | UAF가 Beta 이상이 되고 GASP의 UAF 캐릭터가 레퍼런스로 성숙하면 |
| **Mass Entity / MassAI / MassCrowd / ZoneGraph** | 12.4절 | 동시 병사 수 목표가 200+로 올라가면 |
| **GOAP / HTN 플래너 전면 도입** | 8.1절. 우리 문제는 계획 길이가 짧고 위치 선택이 지배적 | 다단계 실내 작전(문 개방→진입→방 정리) 같은 시퀀스가 핵심이 되면 |
| **GameplayInteractions 플러그인** | Experimental. Smart Object 자체는 정식이므로 서브시스템 API를 직접 쓴다 | 정식 등급 시 |
| **GameplayAbilitySystem(GAS)** | 무기/능력을 GAS로 짜면 확장성은 좋지만 학습·배선 비용이 크고, `titan_example`이 GAS를 안 쓴다 → 이식 시 임피던스 | 이식 대상 프로젝트가 GAS를 도입하면 |
| **머신러닝 기반 애니메이션/행동(Learning Agents, ML Deformer)** | 재현성·디버깅·저작 통제가 이 프로젝트 요구(시연/검증용)와 안 맞음 | — |

---

## 14. 구현 로드맵과 검증 프로토타입 제안

> 설계 승인 완료(2026-09-01). 프로젝트 생성/GASP 조달은 **사용자가 직접 수행**(3.3~3.6절
> 절차서), 그 다음 단계부터 착수한다.

### P0 — 검증 프로토타입 (1~2일 규모)

**목표: 이 설계의 가장 큰 두 가지 미지수를 먼저 깬다. 자산은 아무것도 사지 않는다(3.8절).**

#### P0-0. 셋업 (사용자 수행)

- [ ] Fab에서 Game Animation Sample을 라이브러리에 추가 (3.3절)
- [ ] Epic Games Launcher → Fab Library → Create Project → 엔진 5.8 →
      `C:\working\works\kadex\anim_test\SoldierLab` (3.3절)
- [ ] PIE로 기본 캐릭터 조작 확인 — 걷기/정지/급선회/볼팅, 발 미끄러짐 없음 (3.3절 4항)
- [ ] Tools → New C++ Class 로 C++ 프로젝트 전환 + VS 프로젝트 파일 생성 + 빌드 (3.4절)
- [ ] 플러그인 활성화 (3.5절), 프로젝트 설정 (3.6절)
- [ ] 스켈레톤 확인: `UEFN_Mannequin`에 `root` / `pelvis` / `ik_foot_root` / `ik_hand_gun`이
      실제로 있는지 눈으로 확인 — 3.0절 결정 1의 전제
- [ ] **소스컨트롤 결정 및 초기 커밋**(Q4) — GASP는 대용량 바이너리라 Perforce냐 Git-LFS냐를
      **프로젝트 생성 직후** 정해야 한다. 나중에 옮기면 히스토리가 꼬인다
- [ ] **서버 권위 게이트 규약 확인**(4.3.6절) — 앞으로 만드는 모든 L0~L3 Tick 진입점에
      `HasAuthority()` 체크를 넣는다는 원칙을 팀/자신에게 못박아 둘 것. P0~P2는 싱글로
      개발하지만 게이트는 처음부터 넣는다

#### P0-1. AI가 Motion Matching을 구동할 수 있는가 (**최대 리스크**, 5.3절)

- [ ] GASP 캐릭터를 플레이어 조작에서 분리, AIController를 붙인다
- [ ] `MoveTo`로 NavMesh 경로를 받아 이동시킨다
- [ ] 경로에서 미래 궤적 샘플을 생성해 `CharacterTrajectory` 컴포넌트에 주입한다
      (입력 기반 궤적 생성 경로를 대체 — 이 부분이 자체 구현이 필요한 유일한 핵심 지점)
- [ ] 궤적 생성은 `USoldierTrajectorySource` 인터페이스로 감싼다 (MotionTrajectory가 5.8에서도
      Experimental이므로 API 변경에 대비, 5.3절)

**판정 기준**: 목표점으로 걸어가고 → 감속해서 **정확히 멈추고** → 발이 안 미끄러지고 →
방향 전환이 자연스러운가. **여기서 막히면 로코모션 전략 전체를 재검토해야 하므로 반드시
먼저 한다.**

**막혔을 때의 대안(순서대로 시도)**: ① Detour Crowd의 속도 벡터로 궤적 생성 →
② `NavCorridor`로 경로를 통로화한 뒤 평활화 → ③ CMC의 목표 속도를 적분해 궤적 근사 →
④ (최후) 5.5절 하이브리드에서 MM 비중을 줄이고 블렌드스페이스 폴백

#### P0-2. 견착 자세에서 Orientation Warping이 버티는가 (**클립 구매 규모를 결정**, 5.5.2절)

라이플 클립을 사기 **전에** 반드시 먼저 할 것. 이 결과가 조달 규모를 2배~4배 바꾼다.

- [ ] GASP 기본 캐릭터에 소총 메시를 `ik_hand_gun`에 붙이고, 견착 비슷한 포즈를 임시로 잡는다
      (정식 견착 클립이 없어도 된다 — 상체가 고정된 상태에서 하체가 워핑되는지만 본다)
- [ ] Orientation Warping 노드를 켜고, 캐릭터가 **한 방향을 계속 바라본 채** 전후좌우로 이동
- [ ] 각도별로 품질을 기록: 0° / 45° / 90°(순수 측면) / 135° / 180°(후진)
- [ ] 동시에 Stride Warping / Slope Warping도 실측 — 둘 다 공식 문서가 성숙도 경고를 붙여둔
      노드다(5.2절). 특히 Slope Warping은 폴백(Control Rig 자체 구현)이 필요한지 판단

**판정 기준**: 어느 각도까지 워핑만으로 자연스러운가?
- 90° 이상까지 버틴다 → **전진 클립 중심 2방향**이면 충분. 조달 최소
- 45°까지만 버틴다 → **4방향** 필요
- 45°도 어색하다 → **8방향** 필요 + 워핑은 보조로만. 이 경우 조달 비용이 가장 커진다

#### P0-4. 루트모션 인코딩 파이프라인이 도는가 (조달 전략의 전제)

`../assets/2026-09-02_asset_supply_and_collaboration.md` 4절의 파이프라인을 Mixamo 클립 **1개**로
끝까지 돌려본다. 이게 안 되면 무료 조달 가능 범위가 GASP/Lyra로 확 좁아진다.

- [ ] Mixamo에서 라이플 견착 walk 클립 1개 다운로드(인플레이스)
- [ ] IK Retargeter로 UE5 Manny 스켈레톤에 리타깃 — **골반/힙 배치가 튀지 않는지 확인**
- [ ] `UEncodeRootBoneModifier` 적용 (발 2개 + 골반 가중 평균으로 루트 계산)
- [ ] Root Motion 활성화 → Pose Search Database에 편입 → MM으로 재생
- [ ] 판정: 발 미끄러짐 없이 재생되는가, 궤적 채널이 0이 아닌 값을 갖는가

#### P0-3. 엄폐 슬롯 → EQS → Smart Object 예약 루프가 도는가

- [ ] 벽 몇 개짜리 테스트 레벨
- [ ] 슬롯 자동 생성 툴의 최소 버전(에디터 유틸리티 또는 Python) — NavMesh 경계에서 트레이스로
      엄폐 지점을 찾아 Smart Object로 등록 (10.2절)
- [ ] 커스텀 EQS Generator로 등록된 슬롯을 후보로 뽑고, 10.4절 질의의 축소판으로 점수화
- [ ] 병사 3명이 **서로 다른 슬롯을 예약**해서 들어가는가 (중복 없음 — 10.3절 예약 시스템 검증)

이 셋이 되면 나머지는 "많은 작업"이지 "미지의 위험"이 아니다.

### P1 — 개인 병사 완성 (3~4주 규모)

**자산 트랙**(3.8절): Lyra 라이플 자산 확인 → 부족분 유료 팩/커스텀 조달 → 필요 시 IK
Retargeter로 Manny 규격 정합 → **라이플 MM 데이터베이스 구축**(Aim-Stand / Aim-Crouch /
Lowered로 분리, GASP의 `CHT_PoseSearchDatabases` 패턴 확장) → 캐릭터 메시 결정(Q8) 및 리스킨.

**시스템 트랙**: 로코모션 파이프라인 정식화(워핑/발IK/상체레이어) → 조준·사격 IK(6절) →
인지 모델(7절) → 유틸리티 판단 + StateTree 실행(8절) → 엄폐 슬롯 생성 툴 정식화(10절).

**검수 기준: 병사 1명 vs 병사 1명이, 마커 하나 없는 임의의 레벨에서 자연스럽게 교전한다.**

### P2 — 분대 (2~3주 규모)

분대 컴포넌트/blackboard/사기/토큰 → 플랜 템플릿 4종(Hold/BaseOfFire/BoundingOverwatch/Withdraw)
→ 정보 공유 → 수신호.
**검수 기준: 5명 vs 5명이 바운딩 오버워치로 전진하고, 사기가 무너지면 교대 엄호하며 물러난다.**

### P3 — 명령 인터페이스 + 스케일 (1~2주 규모)

`FSoldierOrder` 발행/배달/상태보고 → 콘솔·디버그 UI로 명령 주입 → 45명 규모 성능 측정 및 LOD
티어 튜닝.
**검수 기준: 45명 60fps 유지, 명령 하나로 분대가 알아서 전투를 수행한다.**

### P4 — titan_example 이식 (별도 판단)

3.0절 결정 3에 따라 **"SoldierLab의 병사가 titan_example의 병사를 대체한다"** 방향으로 간다.

1. 코드/시스템 이식: 명령 이펙트 1개 추가(11.4절) + 컴포넌트 이식
2. **캐릭터 교체**: titan_example의 `BP_ThirdPersonCharacter`/`BP_Enemy_kadex`를 SoldierLab
   병사(Manny 리그)로 교체. 기존 Mixamo 리그 병사와 **병행 가동 기간**을 두어 개체 단위로
   점진 전환(현행 "커스텀 포즈 시스템이 있으면 그쪽, 없으면 기존 경로" 하위호환 패턴과 동일)
3. 레벨 저작 이관: 기존 포즈 마커는 "수동 저작 슬롯"으로 흡수(10.2절)

> 런타임 리타깃(Manny 애니메이션 → Mixamo 리그)으로 캐릭터를 유지하는 방식은 비용과 품질
> 손실 때문에 **채택하지 않는다**(2026-09-01 결정).

---

## 15. 결정 사항 및 남은 질문

### 15.1 확정된 것 (2026-09-01)

| # | 항목 | 결정 |
|---|---|---|
| Q1 | 프로젝트 이름/위치 | ✅ `C:\working\works\kadex\anim_test\SoldierLab\` |
| Q2 | GASP 베이스 | ✅ 채택. 단 GASP에 라이플 조준 자산은 **없음**(3.2·3.8절) |
| Q3 | 스켈레톤/캐릭터 | ✅ **UE5 Mannequin(UEFN_Mannequin) 규격으로 전면 교체.** 기존 Mixamo 리그 병사 자산은 승계하지 않고 전량 신규 조달(3.0절 결정 1·2) |
| Q6 | 규모 목표 | ✅ 45명 유지 |
| — | 이식 방향 | ✅ SoldierLab 병사가 titan_example 병사를 **대체**한다(3.0절 결정 3) |

### 15.2 아직 열린 것

| # | 질문 | 기본안 | 언제까지 |
|---|---|---|---|
| Q4 | 이 프로젝트도 Perforce에 넣나, 로컬/Git인가 | 확인 필요(titan_example은 P4) | 프로젝트 생성 직후 |
| Q5 | P1의 순서 — 로코모션 품질 먼저인가, AI 판단 먼저인가 | 로코모션 먼저(P0-1이 최대 리스크) | P0 완료 시 |
| ~~Q7~~ | ~~디자인팀 애니메이션 요청 스펙 변경 공지~~ | **✅ 2026-09-02 결정 완료** — `../assets/2026-09-02_asset_supply_and_collaboration.md` 7절: **P0 검증(1주 타임박스)을 혼자 끝낸 뒤 비교 영상과 함께 공유**한다. 지금은 공유하지 않는다 | — |
| **Q8** | **캐릭터 메시를 어떻게 할 것인가** — 기존 병사 메시를 Manny 스켈레톤에 리스킨할지, Fab에서 신규 구매할지, MetaHuman으로 갈지 | 기존 메시 리스킨(외형 연속성 + titan_example 대체 용이) | **P1 후반** — P0는 GASP 기본 캐릭터로 진행하므로 지금 결정 불필요 |
| ~~Q9~~ | ~~라이플 애니메이션 조달 — 유료 팩 구매 여부~~ | **✅ 2026-09-02 결정 완료** — **유료 배제.** 조달 전략은 `../assets/2026-09-02_asset_supply_and_collaboration.md` 3~6절로 대체 | — |
| **Q10** | **견착 전환 동작(start/stop/pivot/turn)을 어떻게 채울 것인가** — 무료 소스에 사실상 없는 유일한 카테고리. A안(요구 수준을 낮추고 연출로 흡수) / B안(GASP 전환 동작을 오프라인으로 견착 변환) / C안(이 부분만 유료 재협의) | **A안 우선, B안 실험** | P0-2 결과 확인 후 |

### 15.3 착수 단계에서 채울 항목 (설계 백로그)

2026-09-01 문서 검토에서 발견된 미비점 중, **구조를 바꾸지 않으므로 해당 단계 착수 시점에
채워도 되는 것들**. 잊지 않도록 여기 모아둔다. (구조를 바꾸는 4건 — 리플리케이션 4.3절,
피격/사망 6.5절, 단일 코드 3.7.1절, 조준 한계각 5.5.6절 — 은 개정 3에서 이미 반영 완료.)

| # | 항목 | 왜 필요한가 | 채울 시점 |
|---|---|---|---|
| **D1** | **애니메이션 메모리 예산** | 12절이 CPU만 다룬다. MM DB는 메모리를 크게 먹고 라이플 3스탠스로 늘면 더 커진다. **기준선이 없으면 5.7절의 Learned Motion Matching을 언제 꺼낼지 판단할 수 없다** | P1 (DB 구축 시작 시) |
| **D2** | **엄폐 슬롯 베이크 산출물의 저장·버전관리** | 레벨 액터인가 별도 DataAsset인가, 지오메트리 변경 시 재생성 정책은, **재베이크가 수동 저작 슬롯을 날리지 않는 보장**은 | P0-3 (슬롯 툴 최소 버전 만들 때) |
| **D3** | **테스트 레벨 사양 + 성능 측정 방법** | 각 단계에 검수 기준은 있는데 그걸 볼 레벨이 없다. 짐 레벨(평지/벽/경사/계단/낮은·높은 엄폐물) + 45명 성능 레벨. 측정은 Unreal Insights / `stat anim` / `stat AI` / EQS 프로파일러 | P0 (짐 레벨), P3 (성능 레벨) |
| **D4** | **애님 노티파이 규약** | 발소리만 언급돼 있다. 총구 화염·탄피·재장전 3단계·발 접지(IK 게이팅)·"이 프레임부터 사격 가능"은 **L3↔L4 계약의 일부** | P1 |
| **D5** | **LOD 티어 전환 팝핑 대책** | T0↔T1에서 발 IK와 총구 정렬이 켜졌다 꺼지면 튄다. 히스테리시스 + 가중치 페이드 필요 | P3 |
| **D6** | **Intent 전환 권한 규칙** (L2/L3 경계) | `AimedFire` 도중 표적 변경은 판단인가 실행인가? **StateTree가 스스로 Intent를 포기할 수 있는가?** 8.3절의 히스테리시스·최소지속시간이 부분적으로만 다룬다 | P1 (StateTree 태스크 설계 시) |
| **D7** | `EOrderRecipientType::Individual`의 의미 | 개인 직접 명령이 분대 레이어(L1)를 우회하는지, 분대장이 중계하는지 | P3 |
| **D8** | UGV/차량 상호작용 | `Follow` verb가 있고 사기 계산에 "UGV 근접"이 들어있는데 SoldierLab엔 UGV가 없다. 더미로 검증할지, 이식 시점으로 미룰지 | P3 또는 P4 |
| **D9** | P1 검수 범위 경계 | "1명 vs 1명"은 분대가 없는 상태라 `SuppressiveFire`/`Regroup` Intent 점수가 항상 0이다. P1에서 어느 Intent까지 구현할지 명확히 | P1 착수 시 |

---

## 16. 참고 자료 목록

**전술 AI**
- Jeff Orkin, *Three States and a Plan: The AI of F.E.A.R.*, GDC 2006 — [gamedevs.org PDF](https://www.gamedevs.org/uploads/three-states-plan-ai-of-fear.pdf) / [GDC Vault](https://gdcvault.com/play/1013282/Three-States-and-a-Plan)
- Guerrilla Games, *HTN Planning in Decima* / *Killzone 2 Multiplayer Bots* — [guerrilla-games.com](https://www.guerrilla-games.com/read/htn-planning-in-decima)
- *Hierarchical AI for Multiplayer Bots in Killzone 3*, Game AI Pro Ch.29 — [PDF](http://www.gameaipro.com/GameAIPro/GameAIPro_Chapter29_Hierarchical_AI_for_Multiplayer_Bots_in_Killzone_3.pdf)
- Remco Straatman, *Killzone's AI: dynamic procedural combat tactics* — [PDF](http://cse.unl.edu/~choueiry/Documents/straatman_remco_killzone_ai.pdf)
- Tobias Karlsson, *AI Summit: Squad Coordination in 'Days Gone'*, GDC 2021 — [GDC Vault](https://www.gdcvault.com/play/1027066/AI-Summit-Squad-Coordination-in) / [YouTube](https://www.youtube.com/watch?v=7TQ-WS3MPlE)
- Champandard/Jack/Dunstan, *Believable Tactics for Squad AI*, GDC — [GDC Vault](https://www.gdcvault.com/play/1015665/Believable-Tactics-for-Squad)
- Matthew Jack, *Tactical Position Selection: An Architecture and Query Language*, Game AI Pro Ch.26 — [PDF](https://www.gameaipro.com/GameAIPro/GameAIPro_Chapter26_Tactical_Position_Selection.pdf)
- Dave Mark, *Architecture Tricks: Managing Behaviors in Time, Space, and Depth* (IAUS), GDC 2013 — [GDC Vault](https://www.gdcvault.com/play/1018040/Architecture-Tricks-Managing-Behaviors-in) / [IAUS 개요](https://www.gameai.com/iaus.php)
- Naughty Dog, *The Last of Us: Human Enemy AI* / *A Context-Aware Character Dialog System*, GDC 2014 — [GDC Vault](https://www.gdcvault.com/play/1020338/The-Last-of-Us-Human)
- Naughty Dog, *Bringing Allies to Life in The Last of Us Part II*, GDC 2021 — [GDC Vault](https://gdcvault.com/play/1027207/Bringing-Allies-to-Life-in)
- Escape from Tarkov AI 패치 분석 — [PCGamesN](https://www.pcgamesn.com/escape-from-tarkov/patch-AI-changes) / [FinalBoss](https://finalboss.io/escape-from-tarkov-finally-dials-back-its-aimbot)
- Six Days in Fallujah, *Procedural Architecture* — [sixdays.com](https://www.sixdays.com/news/introducing-procedural-architecture)
- Bounding overwatch (전술 개념) — [Wikipedia](https://en.wikipedia.org/wiki/Bounding_overwatch)

**애니메이션**
- Michal Mach & Maks Zhuravlov, *Motion Matching in The Last of Us Part II*, GDC 2021 — [GDC Vault](https://gdcvault.com/play/1027118/Motion-Matching-in-The-Last)
- Epic, *Motion Matching and the Game Animation Sample in UE 5.4*, Unreal Fest 2024 — [YouTube](https://www.youtube.com/watch?v=tNw9lD2PW3U) / [Epic Dev Community](https://dev.epicgames.com/community/learning/talks-and-demos/0y9w/unreal-engine-motion-matching-and-the-game-animation-sample-in-ue-5-4-unreal-fest-2024)
- Epic, *Game Animation Sample Project* — [블로그](https://www.unrealengine.com/en-US/blog/game-animation-sample) / [UE5.8 문서](https://dev.epicgames.com/documentation/en-us/unreal-engine/game-animation-sample-project-in-unreal-engine) — 수록 내용(UEFN_Mannequin, 로코모션·트래버설, DB 분리, Chooser, Offset Root Bone 실험적 제한)의 근거
- Motion Matching의 **루트모션 필수** 요구사항 — [Motion Matching 튜토리얼](https://www.unreal-university.blog/motion-matching-unreal-engine-tutorial/) 및 [공식 문서](https://dev.epicgames.com/documentation/en-us/unreal-engine/motion-matching-in-unreal-engine)
- `GASP-ALS` 커뮤니티 저장소(오버레이/무기 시스템은 **공식 GASP가 아님**, 참고 구현) — [GitHub](https://github.com/PolygonHive/GASPALS)
- 현행 병사 스켈레톤이 Mixamo 리그이고 Root 본이 없다는 사실은 `titan_example/Content/Characters/Soldier/Rifle_Aiming_Idle_Skeleton.uasset`의 본 이름 테이블을 직접 덤프해 확인(2026-09-01)
- *Fitting the World: A Biomechanical Approach to Foot IK*, GDC — [GDC Vault](https://www.gdcvault.com/play/1023316/Fitting-the-World-A-Biomechanical)
- *IK Rig: Procedural Pose Animation*, GDC — [GDC Vault](https://www.gdcvault.com/play/1023279/IK-Rig-Procedural-Pose)
- *Bringing Hell to Life: AI and Full Body Animation in DOOM*, GDC 2018 — [GDC Vault](https://www.gdcvault.com/play/1024186/Bringing-Hell-to-Life-AI)
- **Pose Warping** (Orientation / Stride / Slope Warping) 공식 문서 — [UE5.8](https://dev.epicgames.com/documentation/unreal-engine/pose-warping-in-unreal-engine) — 5.5.2절 인용의 출처, 성숙도 경고 포함
- Ponton, Andrews, Andujar, Pelechano, *Environment-aware Motion Matching*, ACM TOG / SIGGRAPH Asia 2025 — [arXiv:2510.22632](https://arxiv.org/abs/2510.22632)
- Holden et al., *Learned Motion Matching*, Ubisoft 2020 — [해설](https://80.lv/articles/ubisoft-s-low-cost-deep-learning-model-for-natural-character-movement) / [UE5 구현체](https://github.com/E1P3/Learned_Motion_Matching_UE5)
- GASP 5.7 업데이트(Mover 통합, +400 애니메이션, Smart Object 레벨, 슬라이드, Footplacement Control Rig) — [정리 글](https://www.biunivoca.com/en/blog/unreal-engine-5-7-what-changes-in-the-game-animation-sample-project)
- GASP 5.8 업데이트(신규 물리 / 모션매칭 / Pose Search Interaction / **additive Look-At POI Control Rig 솔버**) — [Epic 테크 블로그](https://www.unrealengine.com/tech-blog/download-the-latest-game-animation-sample-project-now-updated-for-ue-5-8) / [요약](https://www.projprod.com/post/game-animation-sample-project-unreal-engine-5-8)
- 기성 구현체: [Advanced Third Person Shooter Project](https://www.fab.com/listings/a57ab996-ef4b-4b79-ad9b-ce02a656dcf3) / [Third Person Shooter Kit v2.2](https://www.fab.com/listings/6d3abb8e-ba57-4d13-b232-601d7a478645) / [Tactical Shooter Kit V1](https://www.fab.com/listings/ec4e2da2-7bfc-483b-a410-2094e7c9c38e) / [GASP-ALS(비교용, 공식 아님)](https://github.com/PolygonHive/GASPALS)

**UE5.8 공식 문서**
- [Motion Matching in Unreal Engine](https://dev.epicgames.com/documentation/en-us/unreal-engine/motion-matching-in-unreal-engine)
- [State Tree in Unreal Engine](https://dev.epicgames.com/documentation/en-us/unreal-engine/state-tree-in-unreal-engine)
- [Smart Objects — Overview](https://dev.epicgames.com/documentation/unreal-engine/smart-objects-in-unreal-engine---overview) / [Quick Start](https://dev.epicgames.com/documentation/en-us/unreal-engine/smart-objects-in-unreal-engine---quick-start)
- [Environment Query System](https://dev.epicgames.com/documentation/unreal-engine/environment-query-system-in-unreal-engine)
- [Animation Budget Allocator](https://dev.epicgames.com/documentation/unreal-engine/animation-budget-allocator-in-unreal-engine)
- [Unreal Engine 5.8 Release Notes](https://dev.epicgames.com/documentation/unreal-engine/unreal-engine-5-8-release-notes)
- 플러그인 성숙도는 로컬 엔진(`C:\Program Files\Epic Games\UE_5.8\Engine\Plugins\**\*.uplugin`)의
  `IsExperimentalVersion`/`IsBetaVersion` 필드를 직접 확인한 값(2026-09-01 기준).
