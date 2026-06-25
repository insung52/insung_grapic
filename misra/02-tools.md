# 검증 도구 조사 — MISRA / AUTOSAR / ASIL 대응 정적분석 도구

> [01-background.md](01-background.md) 에서 정리한 개념(MISRA, ASIL, TCL, Deviation 등)을 전제로 함.
> 비용은 대부분 비공개(견적 문의) 정책이라 정확한 금액보다 **"무료/오픈소스 vs 상용(견적제)"** 구분과 **기능 차이**에 초점을 맞춤.
> (2026-06 기준 웹 조사. 가격/인증 상태는 변동 가능하므로 구매 전 벤더 확인 필요)

---

## 1. 도구 지형 한눈에 보기

도구들은 대략 4그룹으로 나뉜다.

| 그룹 | 특징 | 해당 도구 |
|---|---|---|
| **A. 풀스택 상용 SAST (자동차/안전 표준 특화)** | MISRA/AUTOSAR/CERT 동시지원 + ASIL Tool Qualification 패키지(TQSK) 제공 | Polyspace, Coverity, Klocwork, Parasoft C/C++test, Helix QAC, LDRA, CodeSonar, Axivion |
| **B. 린트 계열 (경량, 단일목적 강력)** | 정적 패턴/타입 분석 중심, 가벼움, 역사가 깊음 | PC-lint Plus |
| **C. 정형검증(Formal/Abstract Interpretation)** | "런타임 에러 없음"을 수학적으로 증명, ASIL D급 최상위 요구에 사용 | Astrée (AbsInt), Polyspace Code Prover, TrustInSoft Analyzer |
| **D. 무료/오픈소스 또는 저가형** | 비용 부담 없이 시작 가능, MISRA 커버리지는 상용 대비 제한적 | Cppcheck, Clang-Tidy, PVS-Studio(OSS 무료 라이선스), Sonar(SonarQube/SonarCloud) |

그래픽 엔진처럼 **템플릿/SIMD/멀티스레딩/GPU API 바인딩**이 많은 코드베이스에서는, 도구의 "C++ 파서 정확도"와 "오탐(false positive) 처리 편의성(Deviation/Suppression UX)"이 룰 커버리지 숫자보다 실무 영향이 큰 경우가 많다.

---

## 2. 도구별 정리

### 2.1 MathWorks Polyspace (Bug Finder + Code Prover)
- **분류**: A + C. Bug Finder(패턴 기반 결함탐지)와 Code Prover(추상해석 기반 정형검증)로 나뉨.
- **MISRA**: MISRA C:2012, MISRA C++:2008/2023 지원.
- **ASIL**: TÜV 인증 보유, ISO 26262 Tool Qualification Kit 제공. ASIL D 프로젝트에서 표준적으로 채택.
- **특징**: Code Prover는 "오버플로우/배열범위초과/0으로 나누기 등이 없음을 증명"하는 수준까지 감. MATLAB/Simulink 연계 워크플로우와 강하게 결합되어 있어, 모델 기반 개발(MBD) 조직에 특히 유리.
- **라이선스**: 상용, 견적제 (MathWorks 영업 통한 코드라인/시트 기준 가격).

### 2.2 Synopsys (Black Duck) Coverity
- **분류**: A.
- **MISRA/AUTOSAR**: MISRA C/C++, AUTOSAR C++14 지원.
- **ASIL**: TÜV SÜD 인증 (ISO 26262, IEC 61508).
- **특징**: 원래 보안(SAST) 쪽으로 유명했고, interprocedural dataflow 분석이 강함. 대규모 코드베이스의 CI 통합(증분 분석)에 강점 — 그래픽 엔진처럼 빌드가 큰 프로젝트에 적합.
- **라이선스**: 상용, 견적제.

### 2.3 Perforce Klocwork
- **분류**: A.
- **MISRA/AUTOSAR**: MISRA C/C++, AUTOSAR C++14, CERT 지원. 체커 수가 매우 많음(2,000+ 전체, C/C++ 1,000+).
- **ASIL**: TÜV SÜD 인증.
- **특징**: IDE(Visual Studio 등) 통합과 실시간(타이핑 중) 분석에 강점. 대형 임베디드/자동차 조직에서 채택 사례 많음.
- **라이선스**: 상용, 견적제.

### 2.4 Parasoft C/C++test
- **분류**: A.
- **MISRA/AUTOSAR**: MISRA C/C++, AUTOSAR C++14 지원.
- **특징**: 정적분석뿐 아니라 단위테스트/커버리지(MC/DC 포함) 생성까지 한 제품에 포함 — "검증 단계 1+5"를 한 도구로 커버하려는 포지셔닝.
- **라이선스**: 상용, 견적제.

### 2.5 Perforce Helix QAC (구 QA-C/QA-C++)
- **분류**: A.
- **MISRA**: MISRA C/C++ 커버리지가 업계에서 가장 깊다고 평가받는 축. MISRA 위원회 멤버사 출신 도구라 룰 해석의 "정합성"이 강점.
- **ASIL**: TCL1 분류 보유(검색 결과 기준), ISO 26262 대응 다수 사례.
- **특징**: 비교적 합리적인 초기 비용으로 평가됨(타 상용 툴 대비). Helix ALM 등 Perforce 생태계와 연계.
- **라이선스**: 상용, 견적제 (상대적으로 진입비용 낮은 편이라는 평가).

### 2.6 LDRA Tool Suite / TBvision
- **분류**: A (+ 일부 동적분석/커버리지/추적성까지 풀스택).
- **MISRA/AUTOSAR**: 폭넓게 지원. 요구사항 추적성(traceability)까지 묶어서 "ISO 26262 전 생애주기"를 한 제품군으로 커버하려는 포지셔닝.
- **ASIL**: 다수 TÜV/인증 사례, 항공(DO-178C) 쪽에도 강함.
- **특징**: 기능이 매우 광범위한 만큼 도입/설정 비용과 학습곡선이 큰 편이라는 평가가 일반적.
- **라이선스**: 상용, 견적제 (검색결과 기준 타 도구 대비 셋업 비용 높은 편).

### 2.7 Axivion Suite (구 Bauhaus Suite, 現 Qt 산하)
- **분류**: A.
- **MISRA/AUTOSAR**: MISRA C/C++, AUTOSAR C++14 지원.
- **ASIL**: TÜV 인증("Dual-Layer Code Quality Analysis"로 마케팅).
- **특징**: 아키텍처 준수 검사(의존성 규칙, 모듈 경계 위반 탐지)가 강점 — 대규모 엔진처럼 모듈 구조가 복잡한 코드베이스의 "아키텍처 침식" 방지에 유용.
- **라이선스**: 상용, 견적제 (고기능 대비 셋업비용 높은 편 평가).

### 2.8 GrammaTech/CodeSecure CodeSonar
- **분류**: A.
- **MISRA**: MISRA-C 2012/2023/2025, MISRA-C++:2023, AUTOSAR C++14, CERT, JSF++(록히드마틴 C++ 가이드라인, 게임/항공 분야에서도 종종 참조됨) 지원.
- **특징**: 보안취약점(CWE) 탐지와 안전성 분석을 동시 지원하는 포지셔닝. Whole-program 분석.
- **라이선스**: 상용, 견적제.

### 2.9 PC-lint Plus (Vector Informatik 산하)
- **분류**: B.
- **MISRA**: MISRA C 2012/2023/2025, MISRA C++:2023, AUTOSAR(17/19), CERT C 지원 — 최신 MISRA C++:2023까지 빠르게 따라가는 편.
- **ASIL**: exida 인증 (ISO 26262, IEC 61508, IEC 62304).
- **특징**: 전통적인 "린트" 계열 — 가볍고 빠르며 온프레미스(사내 서버) 분석에 적합. 추가 기능에 별도 과금이 없다는 점을 마케팅 포인트로 내세움(번들형 가격).
- **라이선스**: 상용, 견적제(Vector를 통한 견적).

### 2.10 Astrée (AbsInt)
- **분류**: C (순수 정형검증/추상해석).
- **MISRA**: MISRA 지원하나, 주목적은 "런타임 에러 부재의 수학적 증명"(오버플로우, 배열범위, NULL 역참조, 데이터 레이스 등).
- **ASIL**: TÜV 인증, ASIL D/원자력/항공/우주 분야에서 최상위 신뢰도 요구 시 채택 (에어버스 A340/A380 비행제어 SW 사례로 유명).
- **특징**: False negative(누락) 없음을 지향하는 "sound" 분석기라 매우 보수적/엄격함. 대신 대규모 코드 전체에 적용하면 분석 시간/리소스 부담이 크고, 일반적인 애플리케이션 로직보다는 안전 critical 핵심 모듈에 선택적으로 적용하는 경우가 많음.
- **라이선스**: 상용, 견적제 — 최상위 정형검증 도구군이라 가격대도 높은 편으로 알려짐.

### 2.11 TrustInSoft Analyzer
- **분류**: C. Astrée와 유사하게 형식검증(formal verification) 기반.
- **특징**: "C 표준의 미정의 동작(UB) 전체를 형식적으로 검증"하는 포지셔닝. 보안(CWE)·안전 양쪽에서 인용됨.
- **라이선스**: 상용, 견적제.

### 2.12 Cppcheck / Cppcheck Premium
- **분류**: D.
- **무료(오픈소스) 버전**: 기본 정적분석 체커 제공. MISRA addon 스크립트가 있으나, **MISRA 텍스트(규칙 설명) 자체는 MISRA 라이선스가 있어야 전체 리포트 텍스트를 볼 수 있음** (addon은 규칙 ID만 매핑, 실제 규칙 문구는 별매 MISRA 문서 필요).
- **유료(Premium) 버전**: MISRA C/C++ 풀 리포트, AUTOSAR, CERT 지원 강화 + 상용 지원.
- **특징**: 오픈소스라 가볍게 CI에 넣기 좋음. 단, 비교 자료에서 룰 커버리지(특히 MISRA)는 상용 대형 도구 대비 낮게 평가되는 경향(앞서 조사에서 Klocwork 13 : Coverity 11 : Cppcheck 3 비교 사례 — 이 숫자 자체보다 "격차가 있다"는 추세로 참고할 것).
- **결론**: 비용 없이 1차 필터로 쓰기 좋고, 정식 MISRA 준수 증명이 필요하면 상용 도구 병행 필요.

### 2.13 Clang-Tidy / Clang Static Analyzer
- **분류**: D.
- **무료/오픈소스**: 완전 무료. LLVM 생태계라 최신 C++ 표준(C++20/23) 파싱 정확도가 높음 — 그래픽 엔진의 최신 C++ 기능(컨셉, 코루틴 등) 사용 시 강점.
- **MISRA**: 공식 MISRA 체커는 없음(LLVM 측은 MISRA 같은 비공개 라이선스 표준의 직접 구현을 꺼리는 입장 — LLVM Discourse 논의 참고). 다만 일부 룰은 일반 체커(`bugprone-*`, `cppcoreguidelines-*` 등)로 우연히 커버되거나, 서드파티/사내 커스텀 체커로 매핑해서 쓰는 경우가 있음.
- **결론**: "MISRA 준수 증명" 용도로는 부적합, "코드 품질/모던 C++ 베스트프랙티스" 용도로는 매우 강력하고 그래픽 엔진 팀에서 일상적으로 쓰기 좋음.

### 2.14 PVS-Studio
- **분류**: D(오픈소스 프로젝트 한정 무료) / A(상용).
- **무료 조건**: 오픈소스 프로젝트, 학생, MVP 등에게 무료 라이선스 제공.
- **MISRA/AUTOSAR**: C/C++ 한정으로 MISRA, AUTOSAR 룰셋 보유.
- **상용 가격**: 비공개, 견적 문의(시트/기능별).
- **특징**: 원래 버그 탐지(패턴 기반) 중심으로 출발해 MISRA/AUTOSAR로 확장한 도구. Windows/Visual Studio 친화적.

### 2.15 SonarQube / SonarCloud (Sonar)
- **분류**: D~A 경계 (Community 무료 / Enterprise 유료).
- **MISRA**: 2024~2025년부터 **MISRA C++:2023** 지원을 Early Access로 추가 발표 (검색 결과: Sonar 공식 블로그). 이전에는 MISRA보다 일반 코드품질/보안(SonarQube 룰셋) 중심이었음.
- **특징**: 이미 SonarQube를 코드품질 게이트로 쓰고 있는 조직이라면, MISRA 지원 확장이 매력적인 추가 옵션이 될 수 있음. 다만 안전인증(TCL) 레벨의 공식 자료는 상대적으로 신생이라 추가 확인 필요.
- **라이선스**: Community Edition은 무료(MISRA 등 고급 룰셋은 유료 Edition 한정일 가능성 높음 — 도입 전 에디션별 기능표 확인 필요).

---

## 3. 요약 비교표

| 도구 | 유형 | MISRA C | MISRA C++ 2008 | MISRA C++ 2023 | AUTOSAR C++14 | ASIL 인증(TÜV/exida) | 가격모델 |
|---|---|---|---|---|---|---|---|
| Polyspace | A+C | ✅ | ✅ | ✅ | — | ✅ | 상용/견적 |
| Coverity | A | ✅ | ✅ | (확인필요) | ✅ | ✅ | 상용/견적 |
| Klocwork | A | ✅ | ✅ | (확인필요) | ✅ | ✅ | 상용/견적 |
| Parasoft C/C++test | A | ✅ | ✅ | (확인필요) | ✅ | (확인필요) | 상용/견적 |
| Helix QAC | A | ✅ | ✅ | (확인필요) | ✅ | ✅(TCL1) | 상용/견적(상대적 저가) |
| LDRA | A | ✅ | ✅ | (확인필요) | ✅ | ✅ | 상용/견적(고가) |
| Axivion | A | ✅ | ✅ | (확인필요) | ✅ | ✅ | 상용/견적(고가) |
| CodeSonar | A | ✅ | — | ✅ | ✅ | (확인필요) | 상용/견적 |
| PC-lint Plus | B | ✅ | — | ✅ | ✅ | ✅(exida) | 상용/견적 |
| Astrée | C | 부분 | 부분 | (확인필요) | — | ✅ | 상용/견적(고가) |
| TrustInSoft | C | 부분 | — | — | — | (확인필요) | 상용/견적 |
| Cppcheck(Premium) | D | ✅(Premium) | 제한적 | 제한적 | △(Premium) | — | 무료(제한)/유료 |
| Clang-Tidy | D | ❌(공식無) | ❌ | ❌ | ❌ | — | 완전무료 |
| PVS-Studio | D/A | ✅ | ✅ | (확인필요) | ✅ | — | OSS무료/상용견적 |
| SonarQube/Cloud | D/A | — | — | ✅(2024~ EA) | — | (확인필요) | Community무료/Enterprise유료 |

`(확인필요)` 표시는 이번 웹조사에서 명확한 출처를 찾지 못한 항목 — 실제 도입 검토 시 벤더에 직접 확인 필요.

---

## 4. 그래픽 엔진 관점 권장 접근 (제안)

1. **1차 필터: 무료 도구로 먼저 체감** — Clang-Tidy(모던 C++ 품질) + Cppcheck(기본 MISRA 패턴)를 CI에 우선 연동해서, 자사 코드베이스가 MISRA 위반을 어느 정도 규모로 갖고 있는지 가늠. 본격 ASIL 대응 전 "체감 비용" 추정에 유용.
2. **차량용(클러스터/HUD) 등 ASIL 적용 대상이 명확하다면** → TÜV/exida 인증 보유 + TQSK(Tool Qualification Support Kit) 제공 도구(Polyspace, Coverity, Klocwork, Helix QAC, PC-lint Plus, Axivion 등) 중에서 견적/PoC 비교가 필요. 인증서가 있으면 "도구 자체의 TCL 검증 부담"을 줄여줌.
3. **최상위 안전요구(ASIL D 핵심 모듈)가 있다면** → Astrée류 정형검증 도구를 해당 모듈에 한정 적용하는 하이브리드 전략이 비용 대비 합리적 (전체 엔진에 적용은 비용/시간 부담 큼).
4. **그래픽 엔진 특유의 코드 패턴(SIMD intrinsic, 템플릿 중첩, GPU API C 바인딩, 멀티스레드 잡 시스템)**은 도구별로 파서 정확도/오탐률 차이가 크게 날 수 있는 영역이므로, 표 비교만 믿지 말고 **자사 코드 샘플로 PoC(체험판)를 먼저 돌려보는 것**을 권장. 대부분 벤더가 평가판/PoC를 제공함.
5. **AUTOSAR C++14 도 같이 검토 가치 있음** — 차량용이라면 MISRA C++ 단독보다 AUTOSAR C++14(또는 MISRA C++:2023, 양쪽이 통합 추세)까지 같이 보는 게 실무에서 더 일반적인 흐름.

---

## 5. 출처

- [Klocwork Review 2026](https://appsecsanta.com/klocwork)
- [List of tools for static code analysis - Wikipedia](https://en.wikipedia.org/wiki/List_of_tools_for_static_code_analysis)
- [Tool Qualification TCL ISO 26262 – Complete Guide](https://piembsystech.com/tool-qualification-tcl-iso-26262/)
- [ISO 26262 - A static analysis tools perspective](https://embeddedcomputing.com/application/automotive/iso-26262-a-static-analysis-tools-perspective)
- [Tool Classification and Qualification in Compliance with ISO 26262 - MES](https://model-engineers.com/en/blog/tool-classification-and-qualification-in-compliance-with-iso-26262/)
- [CppDepend MISRA C++ documentation](https://www.cppdepend.com/documentation/misra-cpp)
- [cppcheck MISRA C++ 2023 discussion - SourceForge](https://sourceforge.net/p/cppcheck/discussion/general/thread/67580f66bd/)
- [Will clang frontend plan/accept misra check tools? - LLVM Discourse](https://discourse.llvm.org/t/will-clang-frontend-plan-accept-misra-check-tools/84754)
- [Clang-Tidy documentation](https://clang.llvm.org/extra/clang-tidy/)
- [Helix QAC vs LDRA Testbed and TBvision - PeerSpot](https://www.peerspot.com/products/comparisons/helix-qac_vs_ldra-testbed-and-tbvision)
- [Axivion Suite: TÜV Certified - Qt](https://www.qt.io/product/quality-assurance/axivion-suite)
- [Free PVS-Studio license for Open Source](https://pvs-studio.com/en/order/open-source-license/)
- [PVS-Studio Reviews 2026 - G2](https://www.g2.com/products/pvs-studio/reviews)
- [PC-lint Plus official site](https://pclintplus.com/)
- [PC-lint Plus MISRA C++](https://pclintplus.com/coding-standards/misra-cpp/)
- [MISRA C 2023 Guidelines Support in PC-lint Plus 2.1](https://pclintplus.com/pc-lint-plus-2-1-misra-c-2023-update-support/)
- [PC-Lint Plus - Cost Overview - Vector](https://vector-softwarequality.com/static-code-analysis/pc-lint-plus/quotation)
- [Astrée (static analysis) - Wikipedia](https://en.wikipedia.org/wiki/Astr%C3%A9e_(static_analysis))
- [The Astrée Static Analyzer](https://www.astree.ens.fr/)
- [AbsInt official site](https://www.absint.com/)
- [CodeSonar - GrammaTech/CodeSecure](https://www.grammatech.com/learn/latest-version-of-codesonar-improves-on-functional-safety-misra-support-c-parsing-and-visualization/)
- [CodeSonar - Verifysoft](https://www.verifysoft.com/en_codesonar.html)
- [MISRA C++:2023 Compliance Early Access - Sonar](https://www.sonarsource.com/blog/misra-c-plus-plus-compliance-early-access)
- [misra c++ official](https://misra.org.uk/misra-c-plus-plus/)
- [C++ in Automotive - AUTOSAR C++14 - Parasoft](https://www.parasoft.com/blog/breaking-down-the-autosar-c14-coding-guidelines-for-adaptive-autosar/)
- [What is MISRA? - Synopsys](https://www.synopsys.com/glossary/what-is-misra.html)
- [MISRA C/C++ Is for More Than Just Automotive Apps](https://www.electronicdesign.com/technologies/embedded/software/video/55277791/electronic-design-misra-c-c-is-for-more-than-just-automotive-apps)
