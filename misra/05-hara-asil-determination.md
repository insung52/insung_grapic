# HARA — ASIL 등급 산정 기준 상세 조사

> [01-background.md](01-background.md) §3에서 ASIL을 "HARA로 사전에 정해지는 합격 기준"이라고 정리했는데, 여기서는 그 **HARA 산정 기준 자체와, 사람이 정하는지/도구가 있는지**를 자세히 다룸.
> (2026-06 기준 웹 조사)

---

## 1. 결론부터: 사람이 정한다 (단, 보조 도구는 있음)

ASPICE와 똑같은 구조다. **최종 등급은 사람(전문가)의 판단으로 정해지고, 도구는 그 판단을 기록·계산·추적하는 걸 도와주는 역할**이다.

- HARA는 "이 코드가 위험한가"를 분석하는 게 아니라, **"이 차량 기능이 오작동하면 어떤 사고가 날 수 있는가"를 시스템/기능 레벨에서 분석**하는 작업이라 도메인 전문가(기능안전 엔지니어, 해당 시스템 담당 엔지니어)의 경험적 판단이 필수로 들어간다.
- 보통 **워크숍 형태**로 진행됨 — 기능안전 컨설턴트/엔지니어 + 해당 시스템 담당자들이 모여서 시나리오별로 S/E/C를 토론하고 합의하는 방식. "정답이 자동으로 계산되어 나오는" 영역이 아니라 **"합의된 판단을 합의된 규칙(테이블)에 대입해 등급을 도출"**하는 반자동 프로세스.
- 등급 산정 **규칙(테이블)** 자체는 ISO 26262 표준에 고정되어 있어서, S/E/C 세 값만 정해지면 그 다음 "등급 도출"은 기계적(표 lookup)이다. → **사람이 어려운 건 S/E/C 값을 매기는 것**이고, 그걸 ASIL로 변환하는 건 단순 매핑.

---

## 2. S/E/C — 세 가지 평가 축

### 2.1 S (Severity, 심각도) — 사고 발생 시 피해 정도
| 등급 | 의미 |
|---|---|
| S0 | 상해 없음 |
| S1 | 경상~중등도 상해 |
| S2 | 심각하고 생명을 위협하는 상해 (생존 가능성 있음) |
| S3 | 치명적 상해 (생존 가능성 낮음/사망) |

### 2.2 E (Exposure, 노출도) — 그 위험 상황에 노출될 확률(빈도)
| 등급 | 의미 |
|---|---|
| E0 | 발생 불가능할 정도로 낮음(Incredible) |
| E1 | 매우 낮은 확률 |
| E2 | 낮은 확률 |
| E3 | 중간 확률 |
| E4 | 높은 확률 (해당 상황이 거의 모든 운행에서 발생) |

### 2.3 C (Controllability, 제어가능성) — 운전자/시스템이 위험을 회피할 수 있는 정도
| 등급 | 의미 |
|---|---|
| C0 | 일반적으로 제어 가능 |
| C1 | 단순히 제어 가능 (대부분의 운전자가 쉽게 회피) |
| C2 | 보통 수준으로 제어 가능 |
| C3 | 제어 불가능하거나 매우 어려움 |

→ 셋 다 **"숫자 측정"이 아니라 "정성적 판단을 등급화"**한 것 — 예를 들어 "이 경고등이 안 켜질 확률이 E2인가 E3인가"는 통계 데이터가 있으면 참고하지만, 최종적으로는 전문가 합의로 정해지는 경우가 많다.

---

## 3. S × E × C → ASIL 결정 테이블 (ISO 26262 고정 규칙)

세 값이 정해지면, 아래 표(ISO 26262 표준에 명시된 고정 매핑)에 그대로 대입해서 등급이 나온다. **S0, E0, C0 중 하나라도 해당되면 무조건 QM**(안전등급 불필요)으로 떨어진다.

**S1 (경상~중등도)**
| | C1 | C2 | C3 |
|---|---|---|---|
| E1 | QM | QM | QM |
| E2 | QM | QM | QM |
| E3 | QM | QM | A |
| E4 | QM | A | B |

**S2 (심각/생명위협)**
| | C1 | C2 | C3 |
|---|---|---|---|
| E1 | QM | QM | QM |
| E2 | QM | QM | A |
| E3 | QM | A | B |
| E4 | A | B | C |

**S3 (치명적)**
| | C1 | C2 | C3 |
|---|---|---|---|
| E1 | QM | QM | A |
| E2 | QM | A | B |
| E3 | A | B | C |
| E4 | B | C | D |

- 가장 가혹한 조합(S3+E4+C3)만 **ASIL D**.
- S, E, C 중 하나라도 한 단계 낮아지면 등급이 보통 한 단계씩 내려가는 경향(정확히는 표 그대로 lookup).
- 이 표는 **합의된 고정 규칙**이라 "표 적용"은 기계적으로 할 수 있다 — 즉 **이 단계는 사실상 자동화 가능한 영역**이고, 실제로 도구들이 이 부분은 자동 계산해준다.

---

## 4. 그럼 "프로그램"은 있는가?

있다. 다만 MISRA 검사 도구처럼 "코드를 넣으면 등급이 나온다"가 아니라, **"전문가가 S/E/C를 입력하면 ASIL을 계산해주고, 그 근거(시나리오, 토의 내용)와 이후 안전요구사항·테스트까지의 추적성을 관리해주는" 워크플로우/문서화 도구**다.

| 도구 | 역할 |
|---|---|
| **Ansys medini analyze** | HARA 전용 분석 도구. HARA 워크시트 + S/E/C 입력 시 ASIL 자동 산정 + FMEA/FTA/FMEDA까지 연계 분석. 기능안전 분야에서 가장 많이 언급되는 전용 툴. |
| **Siemens Polarion** | 원래 ALM(요구사항관리) 도구지만 HARA 템플릿을 구성해서 S/E/C 평가 → ASIL 계산 → 안전목표(Safety Goal)→안전요구사항→구현→테스트까지 추적성 관리. |
| **EnCo SOX HARA** | ISO 26262/IEC 61508 대상 HARA 전용 소프트웨어. |
| **codeBeamer, DOORS, Jama** 등 | medini analyze 같은 전용 HARA 툴과 연계(integration)되어, HARA 산출물을 요구사항관리 체계에 묶어주는 역할. |

**이 도구들이 실제로 하는 일**:
1. S/E/C 값을 입력하면 §3 테이블에 따라 **ASIL을 자동 계산** (이 부분만큼은 자동화됨, 사람이 표를 직접 찾아볼 필요 없음)
2. 위험 시나리오, 평가 근거, 참여자 의견 등을 **문서화하고 버전관리**
3. 산정된 ASIL → 이후 안전목표/안전요구사항/설계/테스트까지 **추적성(traceability)을 연결**해서 ASPICE/ISO 26262 심사 때 증거로 제출 가능하게 함

**이 도구들이 못 하는(안 하는) 일**:
- "이 기능은 S2다"처럼 **S/E/C 값 자체를 도구가 알아서 판단해주지 않음** — 이건 여전히 사람(기능안전 엔지니어 + 도메인 전문가)이 워크숍에서 논의해 입력해야 하는 값.

→ 비유하면, **"채점 규칙(표)은 자동화되어 있지만, 시험 답안(S/E/C 값)을 채워 넣는 건 사람"**인 구조. MISRA 검사 도구가 "코드→자동 판정"인 것과 비교하면, HARA 도구는 "사람의 판단→자동 계산+문서화"라는 점에서 자동화 수준이 한 단계 낮다.

---

## 5. 누가 수행하나 (프로세스 관점)

- ISO 26262 Part 3 (개념 단계, Concept Phase)에서 수행되며, 양산 차량 개발의 **가장 초기 단계**(코드를 쓰기도 전)에 끝나 있어야 함.
- 보통 **기능안전 매니저/컨설턴트 주도 워크숍**으로 진행: 시스템 엔지니어, 해당 기능 담당자, 안전 전문가가 모여 "오작동 시나리오"를 브레인스토밍하고 각각에 S/E/C를 매김.
- 기능안전 교육과정(ISO 26262 자격증 과정)에 보통 HARA 워크숍이 1~2일 별도 세션으로 포함될 정도로, **실무 교육이 필요한 전문 영역**으로 취급됨.
- 학계/업계에서는 이 과정이 "사람마다 판단이 달라질 수 있다(주관성)"는 문제가 지속적으로 제기되어, 이를 객관화(objectification)하려는 연구도 진행 중 (예: 시뮬레이션 기반 정량화 시도) — 즉 현재도 "완전히 객관적/자동화된 산정"은 업계 표준이 아니라는 뜻.

---

## 6. 그래픽 엔진 관점 요약

- 그래픽 엔진 팀이 HARA를 직접 수행할 일은 거의 없음 — 이건 **차량 시스템/안전 엔지니어링 조직이 차량 전체 또는 해당 ECU/기능 단위로 미리 끝내놓는 작업**.
- 그래픽 엔진팀이 받는 입력은 보통 **"이 화면/이 렌더링 기능은 ASIL B다"라는 이미 산정된 결과**이고, 거기서부터 02-tools.md/03번 문서에서 다룬 "그 등급에 맞는 도구/엄격도로 코드를 검증"하는 단계로 넘어감.
- 다만 외부 업체가 "과거 프로젝트의 ASIL 수준"을 물어본 것(new.md)은, **그 회사가 시스템 차원에서 HARA를 직접 해봤거나, 적어도 고객사가 산정해준 ASIL 요구를 받아 처리한 경험이 있는지**를 묻는 것으로 해석하면 됨.

---

## 7. 출처

- [HARA: Hazard Analysis & Risk Assessment ISO 26262 Guide](https://piembsystech.com/hara-hazard-analysis-risk-assessment-iso-26262/)
- [ISO 26262 Part 3 Concept Phase: HARA, Hazard Analysis & Safety Goals Guide](https://piembsystech.com/iso-26262-part-3-concept-phase-hara-safety-goals/)
- [What is a HARA? - FuSi Engineering](https://fusi-engineering.de/en/blog/hara-hazard-analysis-risk-assessment-iso-26262)
- [What Is ASIL? - Jama Software](https://www.jamasoftware.com/requirements-management-guide/automotive-engineering/guide-to-automotive-safety-integrity-levels-asil/)
- [ASIL Levels Explained - piEmbSysTech](https://piembsystech.com/asil-levels-explained/)
- [ASIL Risk Classification Tool - NicheCalcs](https://www.nichecalcs.com/asil_from_sec)
- [ISO 26262 ASIL: How it is Determined - Embitel](https://www.embitel.com/blog/embedded-blog/understanding-how-iso-26262-asil-is-determined-for-automotive-applications)
- [Ansys medini analyze](https://www.ansys.com/products/safety-analysis/ansys-medini-analyze)
- [Functional Safety based on ISO 26262 - Siemens Polarion blog](https://blogs.sw.siemens.com/polarion/functional-safety-based-on-iso-26262/)
- [HARA Software by EnCo SOX](https://www.enco-software.com/hara/)
- [Towards increased reliability by objectification of HARA - ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0925753517305763)
- [HARA Automotive: ISO 26262 Functional Safety Journey - Embitel](https://www.embitel.com/blog/embedded-blog/hara-iso-26262-friend-in-deed-of-your-functional-safety-journey)
