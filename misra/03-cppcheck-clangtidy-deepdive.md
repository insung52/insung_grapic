# Cppcheck / Clang-Tidy 심화 조사 — 실전 테스트 준비용

> [02-tools.md](02-tools.md) §2.12~2.13 의 요약을 확장. 실제로 그래픽 엔진 코드베이스에 돌려보기 전에 알아야 할 설정/한계/실무 팁 정리.
> (2026-06 기준 웹 조사)

---

## 1. Cppcheck

### 1.1 가장 먼저 알아야 할 것: "C++를 못 한다"가 아니라 "MISRA C++ 준수검사를 못 한다"
이 둘을 분리해서 이해해야 함.

- **C++ 코드 자체에 대한 일반 정적분석(파싱, 버그탐지)**: 무료 Cppcheck도 **C++17/20 문법을 정상적으로 파싱**하고, null pointer dereference, 메모리 누수, 배열 범위 초과, UB(미정의 동작) 등 **일반 결함탐지는 C++ 코드에도 그대로 동작**한다. "C++를 지원 안 한다"는 게 아님.
- **MISRA "준수 검사" 기능**: 이것만 언어별로 갈린다. `addons/misra.py`는 **MISRA C(2012/2023) 룰셋만 구현**되어 있고, **MISRA C++(2008/2023) 룰셋 체크는 Cppcheck Premium(유료)에서만 제공**됨 — Premium 24.5.0부터 MISRA C++:2023 전체 룰 구현 완료라는 공지 확인.

→ 이 문서에서 Cppcheck는 **"MISRA C++ 준수 검증 도구"로는 다루지 않고, "C++ 코드의 일반 버그탐지(무료) 도구"로 범위를 한정**해서 정리한다. MISRA C++ 준수 자체가 목적이라면 02-tools.md의 상용 도구(Premium 포함) 또는 Clang-Tidy의 일부 겹치는 체커(`cppcoreguidelines-*`, `cert-*`)로 우회하는 정도가 무료 단계의 현실적 한계.

### 1.2 MISRA C addon 실제 사용법 (C++ 코드에는 적용되지 않음에 유의)
```bash
# 1) 분석용 dump 생성
cppcheck --dump main.cpp

# 2) MISRA 룰 텍스트 파일 준비 (저작권 때문에 cppcheck 저장소에 룰 "문구"는 없음 — 번호만 나옴)
#    - 유료 MISRA PDF를 보유하고 있다면 자동 변환 스크립트 사용 가능:
python3 scripts/cppcheck-misra-parsetexts.py /path/to/MISRA_C_2012.pdf
#    -> misra_c_2012_headlines.txt 같은 룰텍스트 파일 생성

# 3) 실제 MISRA 검사 실행
python misra.py --rule-texts=misra_c_2012_headlines.txt main.cpp.dump
```
- `--rule-texts` 를 안 주면 **위반 룰 "번호"만 출력**되고 설명 문구는 안 나옴(라이선스 문제로 cppcheck가 룰 본문을 배포할 수 없기 때문) → 결국 [MISRA 공식 PDF](02-tools.md#3-1-misra-공식-문서가이드라인-pdf-자체의-가격) 구매가 실질적으로 필요해짐. 무료 도구지만 "제대로 된 리포트"를 위해선 유료 문서가 끼게 되는 구조.
- `daca2`(cppcheck 자체 CI 룰셋)나 GUI에서도 misra addon을 설정 파일(`misra.json`)로 등록해 쓸 수 있음:
  ```json
  { "script": "misra.py", "args": ["--rule-texts=misra_c_2012_headlines.txt"], "ctu": true }
  ```
  `"ctu": true` 는 Cross-Translation-Unit 분석(여러 파일에 걸친 분석) 활성화 옵션 — 정확도는 올라가지만 분석 시간이 늘어남.

### 1.3 CI에 넣을 때 핵심 옵션
```bash
cppcheck --enable=all --inline-suppr \
  --suppress=missingIncludeSystem \
  --error-exitcode=1 \
  -I include/ \
  --project=compile_commands.json
```
| 옵션 | 용도 |
|---|---|
| `--enable=all` | warning/style/performance/portability/information 전부 활성화(기본은 error만) |
| `--inline-suppr` | 코드 내 `// cppcheck-suppress <id>` 주석으로 개별 억제 허용 |
| `--suppress=<id>:<file>:<line>` | 특정 위반을 파일/라인 단위로 억제 (Deviation 기록 대체용으로 활용 가능) |
| `--error-exitcode=1` | error 등급 발견 시 비정상 종료 → CI 게이트에 연결 |
| `--exitcode-suppressions=<file>` | "표시는 하되 빌드는 안 깨지게" 할 룰을 파일로 관리 — 점진적 도입(처음엔 경고만, 나중에 강제)에 유용 |
| `--project=compile_commands.json` | CMake 등에서 뽑은 컴파일 DB 사용 → 실제 include 경로/매크로를 정확히 반영, 오탐 감소 |

### 1.4 알려진 한계 (그래픽 엔진 관점에서 특히 중요)
- **파일 단위 분석이 기본** — `ctu`(Cross-Translation-Unit) 옵션 없이는 다른 .cpp 파일에 정의된 함수/전역 상태를 모르고 분석 → 멀티 .cpp로 쪼개진 엔진 모듈 구조에서 거짓음성(missed bug) 가능성.
- **매크로/인라인 어셈블리/템플릿**에서 오탐이 잦다고 공식적으로 언급됨. SIMD intrinsic(`_mm_*` 등)이나 헤비 템플릿 메타프로그래밍이 많은 렌더러 코드에서 노이즈가 늘어날 가능성이 높음 → 처음 도입 시 `--suppress`로 화이트리스트를 만드는 작업이 꽤 필요할 것으로 예상.
- **성능**: 약 90만 라인 C/C++ 펌웨어 코드베이스를 10분 이내 분석한 사례가 있는 반면, 4900만 라인 같은 초대형 코드베이스는 수 시간이 걸린 사례도 있음 → 코드량과 분석시간이 선형이 아니므로, 엔진 전체보다 **변경된 파일만 증분 분석**하는 CI 전략이 필요.
- 같은 비교 자료에서 cppcheck의 MISRA 룰 커버리지가 상용 대형 도구(Klocwork/Coverity) 대비 낮게 평가된 사례가 있었음(02-tools.md 참고) — "전부 잡아준다"고 기대하면 안 됨.

### 1.5 실전 테스트 1차 체크리스트 (제안)
1. `compile_commands.json` 먼저 뽑기 (CMake: `-DCMAKE_EXPORT_COMPILE_COMMANDS=ON`)
2. 엔진 코어(렌더러, 수학 라이브러리 등 핵심 모듈) 한 개만 골라 `--enable=all --project=compile_commands.json` 로 1차 스캔, 노이즈 비율 체감
3. 서드파티 코드/벤더 SDK는 분석 대상에서 제외 (`-i` 옵션 또는 `--suppress` 로 경로 단위 제외)
4. MISRA C 적용 대상 모듈이 있다면(예: 펌웨어 연동 C 코드) misra.py 별도 실행
5. 반복적으로 뜨는 오탐 패턴(템플릿/SIMD)을 모아서 팀 차원의 suppression 정책 문서화

---

## 2. Clang-Tidy

### 2.1 포지셔닝 다시 확인
- 공식 MISRA 체커 없음 (LLVM 측이 비공개 라이선스 표준의 직접 구현에 보수적인 입장이라는 논의가 LLVM Discourse에 있었음).
- 대신 **모던 C++ 품질/버그패턴/CERT 가이드라인** 커버리지가 강력해서, "MISRA 인증용"이 아니라 **"좋은 C++ 작성 습관 강제"** 목적으로 그래픽 엔진 팀 일상 워크플로우에 넣기 좋음.
- 체크 카테고리: `bugprone-*`, `cert-*`, `clang-analyzer-*`, `cppcoreguidelines-*`, `hicpp-*`, `modernize-*`, `performance-*`, `portability-*`, `readability-*` 등.
  - `cppcoreguidelines-*` 와 `hicpp-*` 는 MISRA/AUTOSAR 가 금지하는 패턴(예: C 캐스트 금지, 소유권 불명확한 raw pointer 사용 등)과 실질적으로 많이 겹침 → "MISRA 공식 인증은 아니지만 정신은 비슷한" 체크로 활용 가능.

### 2.2 기본 사용법
```bash
# 단일 파일
clang-tidy main.cpp -- -std=c++20 -Iinclude

# 컴파일 DB 기반(권장) - CMake가 만든 compile_commands.json 자동 인식
clang-tidy -p build/ src/renderer.cpp

# 체크 목록 커스터마이즈
clang-tidy -checks='-*,bugprone-*,cppcoreguidelines-*,performance-*' src/renderer.cpp
```
`-checks=` 는 `,`로 구분된 양/음수 glob 목록. `-*` 로 기본값 전부 끈 다음 원하는 카테고리만 켜는 패턴이 일반적.

### 2.3 `.clang-tidy` 프로젝트 설정 파일
프로젝트 루트(또는 하위 디렉토리별)에 두면 자동 적용됨. 디렉토리별로 다른 설정을 둘 수 있어, **서드파티 코드 디렉토리에는 빈 설정(`Checks: '-*'`)을 둬서 분석 대상에서 제외**하는 패턴이 흔히 쓰임.

```yaml
Checks: >
  -*,
  bugprone-*,
  cert-*,
  cppcoreguidelines-*,
  performance-*,
  portability-*,
  modernize-use-nullptr,
  modernize-use-override
WarningsAsErrors: ''
HeaderFilterRegex: '^(src|include)/'
FormatStyle: file
```

### 2.4 Visual Studio 통합 — 더 쉬운 경로
CLI를 직접 안 다뤄도 되는 경로가 이미 있다. 그래픽 엔진 팀이 VS를 메인 IDE로 쓴다면 진입장벽이 가장 낮은 방법.

- **별도 설치 불필요**: VS 2019 16.4 이상에서 **C++ 워크로드**를 설치하면 Clang-Tidy 실행 파일이 자동으로 같이 설치됨. LLVM을 따로 받을 필요 없음.
- **자동 실행**: VS의 "Code Analysis" 기능에 통합되어 있어, 코드 작성 중 **백그라운드로 자동 분석**되고 에디터 물결선 + 오류 목록 창에 결과가 뜸. CLI 명령을 직접 칠 필요가 없음.
- **MSVC 코드분석과의 관계**:
  - **clang-cl(LLVM 도구체인)로 빌드** → Clang-Tidy가 기본 분석기로 자동 동작 (이때는 MS Code Analysis 사용 불가)
  - **MSVC 도구체인으로 빌드** → 기존 MS Code Analysis와 **병행 실행하거나 대체**하도록 선택적으로 설정 가능
- **설정 위치**:
  - MSBuild 프로젝트: 프로젝트 속성 → `Code Analysis` → `코드 분석` → `Clang-Tidy` 페이지에서 체크 목록(`--checks`에 대응), 추가 옵션(`--extra-args`), 병렬 프로세스 수 등을 GUI로 설정.
  - CMake 프로젝트: `CMakeSettings.json` / `CMakePresets.json`에 아래 키 사용.
    ```json
    {
      "configurations": [{
        "name": "x64-debug",
        "clangTidyChecks": "cppcoreguidelines-*, bugprone-*, -modernize-use-trailing-return-type",
        "enableMicrosoftCodeAnalysis": true,
        "enableClangTidyCodeAnalysis": true
      }]
    }
    ```
- **주의할 점**: 기본 상태는 "활성화는 되어 있지만 체크 목록이 비어 있음"이라, 실제로 쓸모 있으려면 `clangTidyChecks`(또는 프로젝트 속성의 Clang-Tidy 검사 항목)에 §2.3의 `.clang-tidy` 설정과 동일한 카테고리(`cppcoreguidelines-*`, `bugprone-*` 등)를 직접 채워야 함. CLI에서 쓰던 `.clang-tidy` 파일을 그대로 둬도 VS가 자동으로 읽음.
- **CLI vs VS 통합 선택 기준**: 로컬 개발 중 실시간 피드백(타이핑하며 바로 확인)은 VS 통합이 편하고, CI 게이트(§2.5)나 대규모 일괄 스캔/`--export-fixes` 같은 자동화는 여전히 CLI(`run-clang-tidy.py`)가 적합 — 둘은 같은 엔진을 쓰므로 설정(.clang-tidy)을 공유하면 결과가 일관됨.

### 2.5 대규모 코드베이스 / CI에서 돌리기
```bash
# LLVM이 제공하는 병렬 실행 스크립트
run-clang-tidy.py -p build/ -j $(nproc) 'src/.*\.(cpp|h)$'

# 자동 수정까지 한 번에 (주의: 리뷰 없이 일괄 적용은 위험, PR diff로 확인 후 머지)
run-clang-tidy.py -p build/ -fix -checks='-*,modernize-use-nullptr'

# 수정 제안만 별도 파일로 뽑아서 리뷰
clang-tidy -p build/ --export-fixes=fixes.yaml src/renderer.cpp
```
- 풀스캔은 느리므로, CI에서는 **PR에서 변경된 파일만** 대상으로 돌리는 게 일반적 (예: `git diff --name-only` 결과를 `run-clang-tidy.py` 마지막 정규식 인자로 넘김).
- 신규 체크를 한번에 전체 적용하면 기존 코드에 수천 건씩 뜰 수 있으므로, 흔히 쓰는 점진 도입 패턴: **"새로 추가/수정되는 코드에만 강제 적용"** → `WarningsAsErrors`는 신규 체크 일부에만 걸고, 기존 위반은 baseline으로 묻어두고 천천히 줄여나가는 방식.

### 2.6 억제(Suppression) 방법
```cpp
int* p = (int*)malloc(10); // NOLINT(cppcoreguidelines-no-malloc)

// NOLINTNEXTLINE(modernize-use-nullptr)
int* q = NULL;

// NOLINTBEGIN(performance-unnecessary-value-param)
void legacyApi(std::string s) { ... }
// NOLINTEND(performance-unnecessary-value-param)
```
- Cppcheck의 `--suppress`(외부 파일 관리)와 달리, Clang-Tidy는 **코드 인라인 주석이 기본 방식** — Deviation을 코드와 함께 추적하기엔 편하지만, "왜 억제했는지" 사유를 별도로 남기는 팀 규칙이 필요함(MISRA Deviation Record와 같은 정신으로).

### 2.7 알려진 한계
- 분석 속도가 느린 편(템플릿이 많은 C++ 코드에서 특히) → 풀스캔보다 증분 적용이 거의 필수.
- 컴파일 DB(`compile_commands.json`)가 정확하지 않으면(include 경로/매크로 불일치) 엉뚱한 오탐이나 분석 실패가 흔함 — 빌드 시스템과 100% 동일한 컴파일 옵션을 확보하는 게 정확도의 전제조건.
- 체크별로 성숙도 차이가 큼 — 일부 `cert-*`/`hicpp-*` 체크는 오탐률이 높다는 커뮤니티 리포트가 있어, 도입 시 카테고리 전체를 켜기보다 개별 체크 단위로 테스트 후 채택 권장.

### 2.8 실전 테스트 1차 체크리스트 (제안)
1. `compile_commands.json` 생성 (Cppcheck와 공유 가능)
2. `.clang-tidy` 를 일단 `cppcoreguidelines-*`, `bugprone-*` 만 켜서 좁게 시작
3. 엔진 핵심 모듈 1개에 먼저 돌려서 위반 건수/체감 노이즈 확인
4. 서드파티/벤더 코드 디렉토리는 `HeaderFilterRegex` 또는 하위 `.clang-tidy`(`Checks: '-*'`)로 제외
5. 노이즈 적은 체크부터 `WarningsAsErrors`로 승격해 CI 게이트화, 나머지는 경고만 누적 관찰

---

## 3. Cppcheck vs Clang-Tidy 빠른 정리

| | Cppcheck (OSS) | Clang-Tidy |
|---|---|---|
| MISRA C | addon으로 가능(룰 텍스트는 유료 PDF 필요) | 미지원 |
| MISRA C++ | **미지원(Premium 유료에서만)** | 미지원 |
| 일반 버그탐지(널포인터, 누수 등) | 강함 | 보통(Clang Static Analyzer 쪽이 더 깊음) |
| 모던 C++ 품질/스타일 | 약함 | 매우 강함 |
| 분석 속도(대형 코드베이스) | 비교적 빠름 | 느린 편(템플릿 많을수록) |
| 컴파일 DB 필요성 | 권장(없어도 동작) | 거의 필수(정확도를 위해) |
| 억제 방식 | 외부 파일(`--suppress`) + 인라인 주석 | 인라인 주석(NOLINT) 위주 |
| CI 적합성 | 가벼워서 풀스캔도 비교적 용이 | 증분(변경분만) 분석 권장 |

**결론**: 둘 다 "MISRA 준수를 보증"하는 도구는 아니다. 무료 단계에서는 **Cppcheck(버그탐지 위주) + Clang-Tidy(모던 C++ 품질 위주)를 병행**해서 코드 기초체력을 올리고, 실제 ASIL/MISRA 준수 "증명"이 필요한 시점에는 02-tools.md의 상용 도구(TÜV 인증 보유) 도입이 불가피하다는 점을 전제로 PoC를 설계하는 게 합리적.

---

## 4. 출처

- [cppcheck/addons/misra.py - GitHub](https://github.com/danmar/cppcheck/blob/main/addons/misra.py)
- [cppcheck/addons/README.md](https://github.com/danmar/cppcheck/blob/main/addons/README.md)
- [Cppcheck Premium 25.8.0 — Full MISRA C:2025 Coverage](https://www.cppcheck.com/product-news/cppcheck-premium-25.8.0-released-full-misra-c2025-coverage)
- [Cppcheck Premium 24.5.0 release notes (MISRA C++:2023)](https://www.cppcheck.com/product-news/cppcheck-premium-24.5.0-released-0)
- [Cppcheck official manual](https://cppcheck.sourceforge.io/manual.html)
- [Cppcheck man page](https://linux.die.net/man/1/cppcheck)
- [Troubleshooting Cppcheck in Large C++ Codebases - Mindful Chase](https://www.mindfulchase.com/explore/troubleshooting-tips/code-quality/troubleshooting-cppcheck-reducing-noise,-improving-accuracy,-and-ci-integration-in-large-c-codebases.html)
- [Uncovering EDK2 Firmware Flaws (cppcheck performance data)](https://arxiv.org/pdf/2409.14416)
- [Clang-Tidy official documentation](https://clang.llvm.org/extra/clang-tidy/)
- [Clang-Tidy Checks list](https://clang.llvm.org/extra/clang-tidy/checks/list.html)
- [Using clang-tidy with CMake - Daniel Sieger](https://danielsieger.com/blog/2021/12/21/clang-tidy-cmake.html)
- [Integrate Clang-Tidy into CMake](https://ortogonal.github.io/cmake-clang-tidy/)
- [Will clang frontend plan/accept misra check tools? - LLVM Discourse](https://discourse.llvm.org/t/will-clang-frontend-plan-accept-misra-check-tools/84754)
- [Troubleshooting Clang-Tidy in Large-Scale C++ Projects - Mindful Chase](https://www.mindfulchase.com/explore/troubleshooting-tips/code-quality/troubleshooting-clang-tidy-in-large-scale-c-projects.html)
