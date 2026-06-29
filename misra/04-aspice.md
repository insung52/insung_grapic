# ASPICE (Automotive SPICE) 조사

> [01-background.md](01-background.md), [02-tools.md](02-tools.md)에서 다룬 MISRA/ASIL과는 **다른 축**의 개념.
> `new.md`에서 언급된 "ASPICE Level, ASIL 수준, MISRA-C" 3종이 묶여서 외부 업체(고객사/OEM)가 공급사 평가 시 같이 묻는 표준 조합이라 별도 문서로 정리.
> (2026-06 기준 웹 조사)

---

## 1. ASPICE가 뭔가

- **Automotive SPICE** — "SPICE(Software Process Improvement and Capability dEtermination)"라는 국제 프로세스 평가 모델(ISO/IEC 330xx 시리즈 기반)을 자동차 업계에 맞게 만든 버전.
- 관리 주체: 독일 자동차산업협회 **VDA(Verband der Automobilindustrie)** 산하 VDA QMC.
- **평가 대상이 코드나 안전성이 아니라 "개발 프로세스" 자체**라는 게 핵심. "요구사항을 어떻게 관리하고, 설계를 어떻게 하고, 테스트를 어떻게 추적하는가"가 체계적인지를 심사한다.
- 01-background.md §4(검증 단계 7단계)에서 말한 **"6. 추적성(Traceability)/프로세스 검증"** 영역에 거의 그대로 대응한다고 보면 됨.

## 2. 프로세스 영역 (VDA Scope)

ASPICE PAM(Process Assessment Model)은 전체 32개 프로세스를 8개 그룹, 3개 카테고리로 정의하는데, 실무에서 OEM이 요구하는 건 그 전체가 아니라 **VDA Scope**라는 부분집합이다.

| 구분 | 프로세스 그룹 | 내용 |
|---|---|---|
| **Basic Part** (필수, 관리/지원) | MAN.3, SUP.1, SUP.8~SUP.10(+SUP.11) | 프로젝트관리, 품질보증, 형상관리, 문제해결관리 등 |
| **Domain-Specific Part** (분야별 선택) | SYS.1~SYS.5 | 시스템 요구사항/아키텍처/통합/검증 |
| | **SWE.1~SWE.6** | **소프트웨어** 요구사항/아키텍처/상세설계/단위검증/통합검증/검증 — 그래픽 엔진 같은 SW 개발팀이 가장 직접 관련되는 그룹 |
| | HWE.1~HWE.4 | 하드웨어 |
| | MLE.1~MLE.4 | 머신러닝(최근 PAM 4.0에서 추가) |
| Flex Part (프로젝트별 선택) | ACQ, SPL 등 나머지 | 구매/공급 관련 등 |

### SWE 그룹 상세 (소프트웨어팀이 직접 마주치는 부분)
| 프로세스 | 내용 | V-모델 위치 |
|---|---|---|
| SWE.1 | 소프트웨어 요구사항 분석 | 좌측(요구) |
| SWE.2 | 소프트웨어 아키텍처 설계 | 좌측(설계) |
| SWE.3 | 소프트웨어 상세설계 + 단위 구현 | 좌측(구현) |
| SWE.4 | 소프트웨어 단위 검증 | 우측(검증) |
| SWE.5 | 컴포넌트/통합 검증 | 우측(검증) |
| SWE.6 | 소프트웨어 검증(요구사항 대비 최종 확인) | 우측(검증) |

→ "요구사항 → 아키텍처 → 설계 → 구현 → 단위테스트 → 통합테스트 → 검증"이 전부 **문서화되고 추적 가능**해야 한다는 게 골자. 그래픽 엔진 팀이라면 "왜 이 렌더링 기능을 만들었는지(요구사항) → 어떤 모듈 구조로 풀었는지(아키텍처) → 실제 구현 → 테스트 결과"가 서로 링크되어 있어야 통과 가능.

## 3. 등급 체계 — Capability Level 0~5

ASPICE는 ASIL처럼 "A~D" 단일 등급이 아니라, **프로세스 하나하나(SWE.1, SWE.2, ... 각각)마다 개별적으로 0~5 등급**을 매긴다. ("우리 회사는 ASPICE 레벨 3"이라고 통칭할 때는 보통 "평가범위 내 모든 프로세스가 레벨 3 이상"이라는 뜻)

| 레벨 | 이름 | 의미 |
|---|---|---|
| 0 | Incomplete | 결과물이 없거나 활동이 수행 안 됨 |
| 1 | Performed | 결과물은 있으나 통제되지 않음(담당자 개인 역량에 의존) |
| 2 | **Managed** | 일정/리소스가 계획·관리되고 결과물 품질이 보증됨 — **대부분 OEM이 요구하는 실질적 최소선** |
| 3 | Established | 조직 표준 프로세스로 정착, 개인이 바뀌어도 동일 품질 유지 |
| 4 | Predictable | 정량적 지표로 관리되어 결과가 예측 가능 |
| 5 | Innovating | 지속적 개선/혁신이 이루어지는 프로세스 |

### 판정 방식
- 레벨을 매길 때 "프로세스 속성(Process Attribute, PA)"이라는 하위 항목을 **N(0~15%) / P(15~50%) / L(50~85%) / F(85~100%)** 4단계로 채점.
- 레벨 1은 PA 1개, 레벨 2 이상은 PA 2개씩 평가하며, **레벨 i를 달성하려면 그 레벨의 PA가 L 또는 F이고, 그 아래 모든 레벨은 F여야 함** (하위 레벨이 미흡하면 상위 레벨도 인정 안 됨 — 누적식 구조).

## 4. ASIL / MISRA와 어떻게 다른가 (다시 한번 정리)

| | ASPICE | ASIL (ISO 26262) | MISRA |
|---|---|---|---|
| 평가 대상 | **프로세스**(어떻게 일하는가) | **위험도/요구 엄격도**(시스템이 사고 시 얼마나 위험한가) | **코드**(코드 패턴이 안전한가) |
| 결과 형태 | 프로세스별 Capability Level 0~5 | 기능별 A~D 등급 (위험분석으로 사전 결정) | 규칙별 위반/통과 |
| 누가 정하나 | 외부 공인 평가자(Assessor)가 실제 프로젝트 산출물을 인터뷰/문서로 심사 | HARA(위험분석)로 시스템 설계 초기에 결정 | 정적분석 도구가 코드를 보고 판정 |
| 1회성 vs 반복 | 프로젝트/조직 단위로 주기적 재평가 | 기능이 바뀌지 않으면 보통 고정 | 빌드/커밋마다 반복 검사 가능 |

→ 셋은 서로 대체 관계가 아니라 **보완 관계**다. ASPICE가 "이 회사는 약속한 대로 일을 했다"를 보여주는 프로세스 증거이고, 그 프로세스의 산출물 중 하나(코드)가 MISRA 위반 검사를 통과해야 하며, 그 코드가 속한 기능의 위험도(ASIL)에 따라 그 모든 활동의 엄격도가 정해진다. OEM이 공급사 RFQ에서 셋을 같이 묻는 이유가 여기 있음 — "프로세스(ASPICE) + 결과물 품질(MISRA) + 안전요구 충족(ASIL)"을 한 묶음으로 확인하려는 것.

## 5. 평가(Assessment)는 어떻게 진행되나

- **평가자**: VDA QMC가 운영하는 국제 평가자 인증제도 **intacs(International Assessor Certification Scheme)**에 등록된 공인 평가자(Assessor)가 필요. "Provisional Assessor"(4일 교육) → "Competent Assessor"(5일 교육, 실무경력 24개월 이상 요구)로 등급이 나뉨.
- **평가 방식**: 실제 프로젝트의 산출물(요구사항 문서, 설계서, 테스트 결과, 형상관리 로그 등)을 평가자가 검토하고 담당자 인터뷰를 진행해서 PA 점수를 매김. "도구를 돌려서 자동 채점"되는 영역이 아니라 **사람이 심사하는 컨설팅/심사 프로세스**임 — 이 점이 MISRA(도구 자동검사)·ASIL(시스템 분석)과 가장 큰 차이.
- **비용/기간**: 정확한 표준 가격은 비공개(평가기관별 견적). 일반적으로 사전 갭분석(Gap Analysis) → 프로세스 개선 → 본평가 순으로 진행되며 **수개월~1년 이상** 걸리는 경우가 흔함(검색에서 정확한 평균 기간/비용 수치는 확인 못 함 — 실제 도입 검토 시 평가기관에 직접 문의 필요).
- 02-tools.md에서 다룬 LDRA 같은 도구는 "추적성(traceability)" 기능으로 ASPICE의 요구사항-설계-테스트 연결 증거를 만드는 데 도움을 줄 수 있지만, **ASPICE 등급 자체를 도구가 발급해주지는 않음**.

## 6. 그래픽 엔진 팀 관점에서 시사점

- ASPICE는 "코드를 어떻게 짰는가"가 아니라 **"요구사항이 왜 생겼고, 그게 설계·구현·테스트까지 추적되는가"**를 본다. 그래픽 엔진 개발 시 흔히 약한 지점:
  - 렌더링 기능 요구사항이 코드/커밋에 명시적으로 연결되어 있지 않은 경우(SWE.1↔SWE.3 추적성 부족)
  - 단위테스트/통합테스트가 체계적으로 문서화되지 않고 수동 확인 위주인 경우(SWE.4~6)
- 차량용(클러스터/HUD/인포테인먼트) 그래픽 엔진을 만드는 회사라면, OEM RFQ 단계에서 "ASPICE Level 2 이상" 요구를 받는 경우가 흔하므로, **MISRA/ASIL 기술적 준비와 별개로 요구사항관리(ALM) 도구·형상관리·테스트 추적 체계를 갖추는 프로세스 작업이 필요**하다는 점을 인지해야 함.

## 7. 출처

- [Automotive SPICE Pocket Guide v4.0 - UL](https://www.ul.com/sites/default/files/2024-10/Automotive_Spice_Pocket_Guide.pdf)
- [Automotive SPICE PAM v4.0 - VDA QMC](https://vda-qmc.de/wp-content/uploads/2023/12/Automotive-SPICE-PAM-v40.pdf)
- [Automotive SPICE Guideline - VDA QMC](https://vda-qmc.de/wp-content/uploads/2026/03/ASPICE_BGB_2.1_Yellow-Volume_final-2.pdf)
- [Understanding the Automotive SPICE Process Assessment Model - UL Solutions](https://www.ul.com/sis/resources/understanding-aspice)
- [ASPICE vs ISO 26262 - Spyrosoft](https://spyro-soft.com/blog/automotive/aspice-vs-iso-26262-what-is-the-difference)
- [ASPICE vs ISO 26262 - autosar.io](https://autosar.io/en/insights/aspice-vs-iso26262)
- [Interpreting the Capability Dimension - Automotive SPICE in Practice](https://dev2u.net/2021/06/03/3-interpreting-the-capability-dimension-automotive-spice-in-practice/)
- [Automotive SPICE Software Processes SWE.1-SWE.6 (PAM 4.0) - UL Solutions resources](https://www.ul.com/sis/resources/process-swe-1)
- [intacs - International Assessor Certification Scheme](https://intacs.info/)
- [Automotive SPICE Certification - VDA QMC](https://vda-qmc.de/en/automotive-spice/automotive-spice-zertifizierung/)
