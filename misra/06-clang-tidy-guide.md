# Clang-Tidy 실행 가이드 — grapi-base 프로젝트 기준

> 이 문서는 `C:\working\grapi-base` 엔진 프로젝트에서 Clang-Tidy를 실제로 사용하는 방법을 정리한 실전 가이드.
> 배경/위치 정보는 [03-cppcheck-clangtidy-deepdive.md](03-cppcheck-clangtidy-deepdive.md) §2 참고.
> (2026-06 기준, LLVM 19 / VS 2022·2026 Insiders 환경)

---

## 0. 이 프로젝트 환경 요약

| 항목 | 내용 |
|---|---|
| 프로젝트 경로 | `C:\working\grapi-base` |
| 빌드 시스템 | CMake + Ninja (프리셋: `windows-msvc-x64-debug` 등) |
| 빌드 출력 경로 | `out/build/<presetName>/` |
| 컴파일러 (Windows) | `cl.exe` (MSVC) |
| VS 버전 | 2022 Professional / 2026 Insiders (둘 다 설치됨) |
| clang-tidy 경로 (2022) | `C:\Program Files\Microsoft Visual Studio\2022\Professional\VC\Tools\Llvm\x64\bin\clang-tidy.exe` |
| clang-tidy 경로 (2026) | `C:\Program Files\Microsoft Visual Studio\18\Insiders\VC\Tools\Llvm\x64\bin\clang-tidy.exe` |
| VS 통합 활성화 여부 | **이미 설정됨** (`CMakePresets.json` `platform-base`에 `enableClangTidyCodeAnalysis: true`) |
| `.clang-tidy` 위치 | 프로젝트 루트 (`C:\working\grapi-base\.clang-tidy`) |

**핵심**: Clang-Tidy는 별도 설치 없이 VS C++ 워크로드에 포함되어 있음. LLVM을 따로 받을 필요 없음.

---

## 1. 실행 방법 A — Visual Studio GUI (가장 쉬운 경로)

### 1.1 VS에서 프로젝트 열기

1. VS 2022 또는 VS 2026 실행
2. **파일 → 폴더 열기** → `C:\working\grapi-base` 선택
3. VS가 `CMakePresets.json`을 자동 감지
4. 상단 구성 드롭다운 → **"Windows MSVC x64 Debug"** 선택
5. CMake 구성 자동 실행 (출력 창에서 확인 가능)

### 1.2 Clang-Tidy 결과 확인

CMake 구성이 완료된 후 파일을 열거나 빌드하면 자동으로 분석이 돌아간다.

- **실시간(편집 중)**: 에디터에 물결선으로 표시
- **빌드 시 전체 스캔**: **빌드 → 솔루션 코드 분석 실행** (또는 `Ctrl+Shift+F11`)
- **결과 목록**: **보기 → 오류 목록** 창

### 1.3 체크 설정 우선순위

VS는 다음 순서로 설정을 읽는다 (앞이 뒤를 덮어씀):

```
프로젝트 속성 GUI > CMakePresets.json clangTidyChecks > 프로젝트 루트 .clang-tidy
```

현재 이 프로젝트는 **.clang-tidy 파일을 주 설정으로** 사용하도록 구성되어 있다.
`CMakePresets.json`에 `clangTidyChecks`를 따로 넣으면 `.clang-tidy`보다 우선하므로 주의.

### 1.4 서드파티 코드 제외 확인

현재 `.clang-tidy`의 `HeaderFilterRegex`로 `external/`, `libs/` 디렉토리는 자동 제외된다.
추가로 제외할 디렉토리가 생기면 해당 디렉토리 안에 빈 `.clang-tidy`를 두면 된다:

```yaml
# external/.clang-tidy 또는 libs/.clang-tidy
Checks: '-*'
```

---

## 2. 실행 방법 B — 명령줄(CLI)

CI 자동화나 일괄 스캔 시 사용. VS 통합보다 세밀한 제어가 가능하다.

### 2.1 사전 준비: VS Developer Command Prompt 열기

MSVC include 경로 및 환경 변수가 필요하기 때문에 반드시 VS Dev 환경에서 실행해야 한다.

**방법 1**: 시작 메뉴 → "Developer Command Prompt for VS 2022" 검색 → 실행

**방법 2**: 일반 PowerShell에서 환경 로드
```powershell
& "C:\Program Files\Microsoft Visual Studio\2022\Professional\Common7\Tools\Launch-VsDevShell.ps1" -Arch amd64
```

### 2.2 compile_commands.json 생성

Clang-Tidy CLI 동작의 핵심. 이 파일이 있어야 실제 include 경로·매크로가 정확히 반영된다.
Ninja 제너레이터를 쓰기 때문에 Windows에서도 정상 생성된다.

```cmd
cd C:\working\grapi-base
cmake --preset windows-msvc-x64-debug -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
```

생성 위치: `out/build/windows-msvc-x64-debug/compile_commands.json`

> **팁**: `-DCMAKE_EXPORT_COMPILE_COMMANDS=ON`을 `CMakePresets.json`의 `cacheVariables`에 영구 추가해도 됨:
> ```json
> "cacheVariables": {
>   "CMAKE_EXPORT_COMPILE_COMMANDS": "ON"
> }
> ```

### 2.3 단일 파일 실행

```cmd
"C:\Program Files\Microsoft Visual Studio\2022\Professional\VC\Tools\Llvm\x64\bin\clang-tidy.exe" ^
  -p out/build/windows-msvc-x64-debug ^
  base/src/renderer.cpp
```

- `-p <빌드디렉토리>`: `compile_commands.json` 위치를 지정
- `.clang-tidy` 파일은 자동으로 읽힘 (프로젝트 루트부터 상위로 탐색)

체크를 명령줄에서 직접 지정하려면:
```cmd
clang-tidy.exe -p out/build/windows-msvc-x64-debug ^
  -checks="-*,bugprone-*,performance-*" ^
  base/src/renderer.cpp
```

### 2.4 전체 소스 일괄 스캔

```cmd
REM run-clang-tidy 사용 (병렬 실행) — VS 설치 버전은 확장자 없음
REM -clang-tidy-binary 필수: 미지정 시 PATH에서 32비트 bin\clang-tidy.exe를 집어들어 전부 크래시(0xC0000005)
python "C:\Program Files\Microsoft Visual Studio\2022\Professional\VC\Tools\Llvm\x64\bin\run-clang-tidy" ^
  -clang-tidy-binary "C:\Program Files\Microsoft Visual Studio\2022\Professional\VC\Tools\Llvm\x64\bin\clang-tidy.exe" ^
  -p out/build/windows-msvc-x64-debug ^
  -j 4 ^
  ".*base\\src\\.*"
```

결과를 txt 파일로 저장 (stdout + stderr 동시 캡처):
```cmd
python "C:\Program Files\Microsoft Visual Studio\2022\Professional\VC\Tools\Llvm\x64\bin\run-clang-tidy" ^
  -clang-tidy-binary "C:\Program Files\Microsoft Visual Studio\2022\Professional\VC\Tools\Llvm\x64\bin\clang-tidy.exe" ^
  -p out/build/windows-msvc-x64-debug ^
  -j 4 ^
  ".*base\\src\\.*" > clangtidy_full.txt 2>&1
```

> `2>&1`: stderr(진행상황/크래시 메시지)도 같은 파일에 합쳐서 저장. 경고만 보고 싶으면 `2>NUL`로 진행 메시지를 버릴 수 있지만, 처음엔 `2>&1`로 전부 남겨두는 게 디버깅에 유리함.
> **주의**: `> file.txt 2>&1` 리다이렉트 시 터미널에 아무것도 안 뜨는 게 정상 — 모든 출력이 파일로 감. 작업 관리자에서 `clang-tidy.exe` 프로세스가 돌고 있으면 실행 중.

화면에 진행 상황을 보면서 동시에 파일도 저장 (PowerShell 전용):
```powershell
python "C:\Program Files\Microsoft Visual Studio\2022\Professional\VC\Tools\Llvm\x64\bin\run-clang-tidy" `
  -clang-tidy-binary "C:\Program Files\Microsoft Visual Studio\2022\Professional\VC\Tools\Llvm\x64\bin\clang-tidy.exe" `
  -p out/build/windows-msvc-x64-debug `
  -j 4 `
  ".*base\\src\\.*" 2>&1 | Tee-Object clangtidy_full.txt
```

> CMD(`^` 연속)와 달리 PowerShell은 `` ` ``(백틱)으로 줄 이음. `Tee-Object`는 PowerShell 내장 명령어라 별도 설치 불필요.

- **`-clang-tidy-binary` 필수**: 미지정 시 스크립트가 PATH에서 `clang-tidy`를 찾는데 `Llvm\bin\` (32비트) 버전을 먼저 집어듦. 32비트 프로세스는 가상 주소 공간 2GB 제한으로 헤더 파싱 도중 Access Violation(0xC0000005)으로 전 파일 크래시. 반드시 `x64\bin\clang-tidy.exe` 명시.
- `-j 4`: CPU 코어 수에 맞게 조정
- 마지막 인자: 분석할 파일을 정규식으로 필터
- **Windows 주의**: `compile_commands.json`의 `file` 경로가 역슬래시(`\`)를 사용하므로, 정규식에서 `/` 대신 `\\` 사용 필수. `\\`은 CMD→Python 전달 시 Python 정규식에서 리터럴 `\` 한 글자와 매칭됨.
- 단일 파일 빠른 테스트 (전체 스캔 전 먼저 확인):
  ```cmd
  "C:\Program Files\Microsoft Visual Studio\2022\Professional\VC\Tools\Llvm\x64\bin\clang-tidy.exe" ^
    -p out/build/windows-msvc-x64-debug ^
    base/src/grapi/base/camera.cc
  ```

### 2.5 자동 수정 적용

```cmd
python "C:\Program Files\Microsoft Visual Studio\2022\Professional\VC\Tools\Llvm\x64\bin\run-clang-tidy" ^
  -p out/build/windows-msvc-x64-debug ^
  -fix ^
  -checks="-*,modernize-use-nullptr,modernize-use-override" ^
  ".*base/src/.*\.(cpp|cc)$"
```

> **주의**: 일괄 자동 수정은 예상치 못한 변경이 생길 수 있다. 반드시 git branch를 따로 만들고,
> PR diff로 변경 내용을 리뷰한 뒤 머지할 것.

### 2.6 수정 제안만 뽑기 (리뷰 후 선택 적용)

```cmd
clang-tidy.exe -p out/build/windows-msvc-x64-debug ^
  --export-fixes=fixes.yaml ^
  base/src/renderer.cpp

REM 수정 적용 (선택적으로 특정 항목만 적용 가능)
clang-apply-replacements.exe .
```

### 2.7 PATH에 clang-tidy 추가 (선택)

매번 전체 경로를 입력하지 않으려면 VS Dev Command Prompt 세션에서:

```cmd
set PATH=C:\Program Files\Microsoft Visual Studio\2022\Professional\VC\Tools\Llvm\x64\bin;%PATH%
clang-tidy --version
```

---

## 3. 현재 `.clang-tidy` 설정 파일 설명

`C:\working\grapi-base\.clang-tidy` 현재 내용 및 각 항목 의미:

```yaml
Checks: >-
  -*,                                          # 기본 체크 전부 비활성화
  google-*,                                    # Google C++ 스타일 (기존 팀 룰)
  readability-identifier-naming,               # 네이밍 컨벤션 (기존 팀 룰)
  bugprone-*,                                  # 버그패턴 탐지 (추가)
  cppcoreguidelines-avoid-c-arrays,            # C 배열 금지
  cppcoreguidelines-no-malloc,                 # malloc/free 금지
  cppcoreguidelines-pro-type-cstyle-cast,      # C 스타일 캐스트 금지
  cppcoreguidelines-pro-type-reinterpret-cast, # reinterpret_cast 경고
  cppcoreguidelines-pro-bounds-array-to-pointer-decay,  # 배열→포인터 decay 경고
  performance-*,                               # 성능 패턴
  portability-*,                               # 멀티플랫폼 이식성
  modernize-use-nullptr,                       # NULL → nullptr
  modernize-use-override                       # override 누락 탐지

HeaderFilterRegex: '.*(grapi-base/(base|samples)).*\.(h|hpp)$'
# → external/, libs/ 디렉토리의 헤더에서 발생하는 경고는 리포트 안 함

WarningsAsErrors: ''
# → 현재 전부 경고만. 결과 확인 후 일부를 에러로 승격 예정

CheckOptions:
  # 기존 네이밍 컨벤션 설정들...
  - key: readability-identifier-naming.ClassCase
    value: CamelCase
  # (이하 생략)
```

### `Checks` 문법 규칙

```
-*                    # 모든 체크 비활성화 (항상 첫 번째)
bugprone-*            # bugprone 카테고리 전부 활성화
-bugprone-macro-*     # bugprone 중 macro 관련만 제외
modernize-use-nullptr # 개별 체크 하나만 활성화
```

- 쉼표 구분, 순서대로 적용 (뒤가 앞을 덮어씀)
- `>-` (YAML 블록 스칼라)로 여러 줄 작성 가능 — 앞뒤 공백/줄바꿈 무시됨

---

## 4. 전체 체크 카테고리 목록 (LLVM 19 기준)

### 4.1 이 프로젝트에서 사용할 카테고리

#### `bugprone-*` — 버그패턴 탐지 (MISRA 관련성: 높음)
> MISRA가 금지하는 여러 패턴과 의도가 겹침. C++ 코드베이스에서 가장 실질적인 가치.

| 체크 | 잡아내는 패턴 |
|---|---|
| `bugprone-use-after-move` | `std::move()` 후 이동된 객체 재사용 (UB) |
| `bugprone-narrowing-conversions` | 암묵적 정수 축소 변환 (`int→short`, `double→float`) |
| `bugprone-integer-division` | 정수 나눗셈 결과를 float에 저장 (소수 부분 소실) |
| `bugprone-signed-char-misuse` | `signed char`를 정수값으로 오용 |
| `bugprone-assert-side-effect` | `assert()` 내부에 부작용 있는 표현식 |
| `bugprone-float-loop-counter` | float을 루프 카운터로 사용 (MISRA Rule 14.1 동일 금지) |
| `bugprone-branch-clone` | if/else 두 분기가 동일한 코드 |
| `bugprone-copy-constructor-init` | 복사 생성자에서 부모 클래스 초기화 누락 |
| `bugprone-dangling-handle` | 임시 객체로부터 `string_view`/`span` 뷰 생성 후 dangling |
| `bugprone-exception-escape` | 소멸자/noexcept 함수 밖으로 예외가 탈출 |
| `bugprone-implicit-widening-of-multiplication-result` | 곱셈 결과 오버플로 후 더 넓은 타입에 저장 |
| `bugprone-inaccurate-erase` | `std::remove` 결과를 `erase` 안 함 |
| `bugprone-macro-parentheses` | 매크로 인자 괄호 누락 (연산자 우선순위 버그) |
| `bugprone-misplaced-operator-in-strlen-in-alloc` | `malloc(strlen(s+1))` 포인터 연산 위치 오류 |
| `bugprone-move-forwarding-reference` | 포워딩 레퍼런스에 `std::move()` 사용 (`std::forward` 의도) |
| `bugprone-multiple-statement-macro` | 여러 구문 매크로를 `do-while`로 감싸지 않은 패턴 |
| `bugprone-not-null-terminated-result` | `strncpy` 등에서 null 종결 문자 누락 가능성 |
| `bugprone-posix-return` | POSIX 함수(`pthread_*`) 반환값 부호 검사 오류 |
| `bugprone-reserved-identifier` | `_Foo` 등 표준 예약 식별자 사용 |
| `bugprone-shared-ptr-array-mismatch` | `shared_ptr<T>`로 배열(`new T[]`) 관리 시 deleter 누락 |
| `bugprone-sizeof-container` | `sizeof(std::vector)` 등 컨테이너 크기 오용 |
| `bugprone-string-constructor` | `std::string(nullptr)` 등 UB 유발 생성자 |
| `bugprone-suspicious-enum-usage` | enum 비트플래그와 일반 값 혼용 |
| `bugprone-suspicious-memory-comparison` | 패딩 포함 구조체를 `memcmp`로 비교 |
| `bugprone-suspicious-string-compare` | `strcmp` 반환값을 bool로 직접 비교 |
| `bugprone-swapped-arguments` | 함수 인자 순서 뒤바뀜 의심 |
| `bugprone-unchecked-optional-access` | `std::optional` 값에 확인 없이 접근 |
| `bugprone-undelegated-constructor` | 위임 생성자처럼 보이지만 임시 객체 생성에 그침 |
| `bugprone-unhandled-self-assignment` | 복사 대입 연산자에서 자기 대입 처리 누락 |
| `bugprone-unique-ptr-array-mismatch` | `unique_ptr<T>`로 배열 관리 시 `T[]` 특수화 미사용 |
| `bugprone-unsafe-functions` | `gets`, `scanf` 등 안전하지 않은 C 함수 |
| `bugprone-unused-return-value` | `[[nodiscard]]` 상당 반환값 무시 |
| `bugprone-virtual-near-miss` | 부모 가상함수와 이름은 같지만 시그니처가 달라 override 안 됨 |
| `bugprone-argument-comment` | 인자 이름 주석이 함수 선언과 불일치 |
| `bugprone-assignment-in-if-condition` | if 조건식 내 대입 (`if (x = 5)`) |
| `bugprone-casting-through-void` | `T* → void* → U*` 이중 캐스트로 타입 안전성 우회 |
| `bugprone-chained-comparison` | `a < b < c` 연쇄 비교 (수학적 의미와 다르게 동작) |
| `bugprone-infinite-loop` | 무한루프 패턴 |
| `bugprone-terminating-continue` | do-while 루프에서 `continue`가 `break`처럼 동작하는 혼동 |

---

#### `cppcoreguidelines-*` — C++ Core Guidelines (MISRA 관련성: 높음)
> Bjarne Stroustrup / Herb Sutter의 C++ Core Guidelines 직접 구현.
> MISRA C++:2023과 규칙 의도가 많이 겹침 ("공식 인증"은 아니지만 방향이 동일).

| 체크 | 잡아내는 패턴 | MISRA C++:2023 대응 |
|---|---|---|
| `pro-type-cstyle-cast` | C 스타일 캐스트 `(Type)val` | Rule 8.2.2 |
| `pro-type-reinterpret-cast` | `reinterpret_cast` 남용 | 유사 규칙 |
| `pro-type-static-cast-downcast` | 안전하지 않은 다운캐스트 | 관련 규칙 |
| `pro-type-const-cast` | `const_cast` 사용 | 유사 규칙 |
| `pro-type-union-access` | union 멤버 접근 (타입 펀닝) | Rule 12.3 |
| `pro-type-vararg` | `va_list`, `...` 가변인자 | Rule 8.4.1 |
| `pro-type-member-init` | 멤버 변수 초기화 누락 | 관련 규칙 |
| `pro-bounds-array-to-pointer-decay` | 배열→포인터 암묵적 변환 | Rule 8.7.1 |
| `pro-bounds-pointer-arithmetic` | 포인터 연산(`p+n`, `p[n]`) | Rule 8.7.2 |
| `pro-bounds-constant-array-index` | 비상수 인덱스로 배열 접근 | 관련 규칙 |
| `no-malloc` | `malloc`/`free` 직접 사용 | Rule 21.6.4 |
| `avoid-goto` | `goto` 사용 | Rule 9.6.1 |
| `avoid-do-while` | `do-while` 루프 | 관련 규칙 |
| `avoid-non-const-global-variables` | 비상수 전역 변수 | 관련 규칙 |
| `avoid-c-arrays` | C 스타일 배열 `int a[]` | 관련 규칙 |
| `slicing` | 파생 클래스 → 기반 클래스 복사 시 데이터 잘림 | — |
| `special-member-functions` | Rule of Five 위반 | — |
| `macro-usage` | 함수형 매크로 → `constexpr`/`inline` 권장 | Rule 19.3.4 |
| `virtual-class-destructor` | 가상 함수 있는 클래스에 가상 소멸자 없음 | — |
| `init-variables` | 선언 시 초기화 누락 | Rule 11.6 |
| `use-enum-class` | 비범위 `enum` → `enum class` | 관련 규칙 |
| `missing-std-forward` | 포워딩 레퍼런스에 `std::forward` 누락 | — |
| `rvalue-reference-param-not-moved` | rvalue ref 파라미터를 move 안 함 | — |
| `prefer-member-initializer` | 생성자 본문 대입 → 멤버 초기화 목록 권장 | — |

---

#### `performance-*` — 성능 패턴 (그래픽 엔진 특히 중요)

| 체크 | 잡아내는 패턴 |
|---|---|
| `performance-for-range-copy` | range-for에서 불필요한 복사 (`auto x` → `auto& x`) |
| `performance-move-const-arg` | const 객체에 `std::move()` (이동 안 되고 복사됨) |
| `performance-noexcept-move-constructor` | `noexcept` 없는 이동 생성자 (컨테이너 재할당 시 복사로 폴백) |
| `performance-noexcept-destructor` | `noexcept` 없는 소멸자 (이동 연산 최적화 방해) |
| `performance-noexcept-swap` | `noexcept` 없는 swap |
| `performance-unnecessary-copy-initialization` | `const auto x = obj` → `const auto& x = obj` |
| `performance-unnecessary-value-param` | 값 전달 파라미터를 내부에서 복사해 사용 → const ref 권장 |
| `performance-inefficient-vector-operation` | `push_back` 전 `reserve` 누락 등 |
| `performance-inefficient-algorithm` | 정렬 컨테이너에 `std::find` (→ `lower_bound` 권장) |
| `performance-type-promotion-in-math-fn` | `float`을 `abs()` 등 double 버전에 전달 → 승격 오버헤드 |
| `performance-avoid-endl` | `std::endl` → `'\n'` 권장 (flush 오버헤드) |
| `performance-enum-size` | enum 기반 타입이 필요 이상으로 큰 경우 |

---

#### `portability-*` — 멀티플랫폼 이식성 (Windows/Linux/Android/QNX)

| 체크 | 잡아내는 패턴 |
|---|---|
| `portability-simd-intrinsics` | `_mm_*`, `__builtin_*` SIMD intrinsic → `std::experimental::simd` 권장 |
| `portability-no-assembler` | 인라인 어셈블리 (`asm`, `__asm__`) |
| `portability-restrict-system-includes` | 플랫폼별 시스템 헤더 직접 포함 제한 |
| `portability-std-allocator-const` | `std::allocator<const T>` (C++20 제거됨) |
| `portability-template-virtual-member-function` | 가상 템플릿 멤버 함수 (일부 컴파일러 미지원) |

---

#### `cert-*` — CERT 보안 코딩 표준 (MISRA 관련성: 높음 / 2단계 추가 권장)

> SEI CERT C/C++ 코딩 표준 구현. 보안 취약점 예방에 집중.
> **주의**: `cert-*` 체크 상당수가 `bugprone-*`/`cppcoreguidelines-*`의 alias임.
> 둘을 동시에 켜면 중복 경고가 나오므로, alias 관계를 확인하고 선별 활성화 권장.

| 체크 | 잡아내는 패턴 |
|---|---|
| `cert-flp30-c` | float 루프 카운터 (MISRA Rule 14.1과 동일) |
| `cert-err34-c` | `atoi`, `atof` 등 오류 검사 불가 변환 함수 |
| `cert-dcl50-cpp` | `va_list` 가변인자 C 스타일 함수 정의 |
| `cert-dcl58-cpp` | `std` 네임스페이스를 사용자가 수정 |
| `cert-err52-cpp` | `setjmp`/`longjmp` 사용 |
| `cert-err58-cpp` | 전역/정적 객체 생성자에서 예외 발생 가능 |
| `cert-msc30-c` | `rand()` 사용 (암호학적으로 안전하지 않은 난수) |
| `cert-msc50-cpp` | `std::rand()` 사용 |
| `cert-oop57-cpp` | `memset`/`memcpy`로 non-trivial 타입 처리 |
| `cert-pos44-c` | 포인터를 정수로 캐스팅 |
| `cert-str34-c` | `signed char`를 `isalpha` 등 문자 분류 함수 인자로 전달 |

---

#### `hicpp-*` — High Integrity C++ (MISRA 관련성: 높음 / 2단계 추가 권장)

> HIC++ 코딩 표준 구현. MISRA C++:2008과 의도적으로 맞춰 설계됨.
> 대부분이 다른 카테고리 체크의 alias. 독자 구현(alias 아님)만 선별해 추가하는 게 효율적.

| 체크 | 잡아내는 패턴 | 비고 |
|---|---|---|
| `hicpp-signed-bitwise` | 부호 있는 정수에 비트 연산 (`&`, `|`, `^`, `~`) | **독자 구현** (MISRA 핵심 규칙) |
| `hicpp-exception-baseclass` | 예외 객체가 `std::exception` 상속 안 함 | **독자 구현** |
| `hicpp-multiway-paths-covered` | switch 문에서 enum 값 일부 미처리 | **독자 구현** |
| `hicpp-no-assembler` | 인라인 어셈블리 | `portability-no-assembler` alias |
| `hicpp-avoid-goto` | goto | `cppcoreguidelines-avoid-goto` alias |
| `hicpp-no-malloc` | malloc/free | `cppcoreguidelines-no-malloc` alias |
| `hicpp-use-nullptr` | NULL/0 → nullptr | `modernize-use-nullptr` alias |
| `hicpp-use-override` | override 누락 | `modernize-use-override` alias |
| `hicpp-vararg` | 가변인자 | `cppcoreguidelines-pro-type-vararg` alias |

---

#### `modernize-*` — 모던 C++ 마이그레이션 (선택적)

| 체크 | 잡아내는 패턴 | 자동 수정 가능 |
|---|---|---|
| `modernize-use-nullptr` | `NULL`/`0` → `nullptr` | ✅ |
| `modernize-use-override` | `override` 누락 | ✅ |
| `modernize-use-auto` | 중복 타입 명시 → `auto` | ✅ |
| `modernize-use-emplace` | `push_back(T(...))` → `emplace_back(...)` | ✅ |
| `modernize-use-equals-default` | 빈 생성자/소멸자 → `= default` | ✅ |
| `modernize-use-equals-delete` | 명시적 삭제 → `= delete` | ✅ |
| `modernize-use-noexcept` | `throw()` → `noexcept` | ✅ |
| `modernize-avoid-c-arrays` | `int arr[]` → `std::array<int, N>` | — |
| `modernize-loop-convert` | C 스타일 for 루프 → range-for | ✅ |
| `modernize-make-shared` | `shared_ptr<T>(new T)` → `make_shared<T>()` | ✅ |
| `modernize-make-unique` | `unique_ptr<T>(new T)` → `make_unique<T>()` | ✅ |
| `modernize-use-using` | `typedef` → `using` | ✅ |
| `modernize-deprecated-headers` | `<string.h>` → `<cstring>` 등 | ✅ |
| `modernize-pass-by-value` | const ref 파라미터가 내부에서 복사 → 값 전달 + move | — |
| `modernize-use-nodiscard` | 반환값 무시 방지 `[[nodiscard]]` 추가 제안 | — |
| `modernize-use-default-member-init` | 생성자 초기화 목록 → 멤버 기본값 초기화 | ✅ |
| `modernize-type-traits` | `::type`/`::value` → `_t`/`_v` 별칭 | ✅ |
| `modernize-use-trailing-return-type` | trailing return type 강제 | ⚠️ **매우 노이즈, 비추천** |

---

#### `misc-*` — 기타 유용한 체크 (선택적)

| 체크 | 잡아내는 패턴 |
|---|---|
| `misc-const-correctness` | const 될 수 있는 변수에 const 누락 |
| `misc-no-recursion` | 재귀 함수 사용 (**MISRA 금지 패턴**) |
| `misc-unused-parameters` | 미사용 함수 파라미터 |
| `misc-redundant-expression` | 동일한 양쪽 피연산자 (`a & a`, `a || a`) |
| `misc-static-assert` | 런타임 assert → `static_assert`로 대체 가능한 경우 |
| `misc-throw-by-value-catch-by-reference` | 예외 throw는 값, catch는 레퍼런스 |
| `misc-include-cleaner` | 불필요한 `#include` 또는 간접 포함 의존 |
| `misc-non-private-member-variables-in-classes` | 클래스 public 멤버 변수 |
| `misc-use-anonymous-namespace` | `static` 전역 → 익명 namespace 권장 |

---

#### `readability-*` — 가독성/스타일 (선택적, 노이즈 많음)

> 대규모 기존 코드베이스에 전체 활성화하면 경고가 수천 건씩 쏟아질 수 있음.
> 선별적으로 항목을 골라 쓰거나, 신규 파일에만 적용하는 전략 권장.

주요 체크: `readability-identifier-naming`(현재 사용 중), `readability-braces-around-statements`,
`readability-const-return-type`, `readability-function-cognitive-complexity`,
`readability-magic-numbers`(⚠️ 그래픽 수식에서 실용 불가), `readability-simplify-boolean-expr`

---

#### `clang-analyzer-*` — 깊은 경로 감지 정적분석 (선택적)

> Clang Static Analyzer(CSA)를 Clang-Tidy 인터페이스로 실행.
> AST 분석보다 깊은 **경로 감지(path-sensitive)** 분석 — 분석 시간이 크게 늘어남.
> 일반 CI 매 커밋보다는 **주기적 풀스캔(야간 빌드 등)** 에 한정 권장.

| 서브카테고리 | 대표 체크 |
|---|---|
| `clang-analyzer-core.*` | `core.NullDereference`, `core.DivideZero`, `core.UndefinedBinaryOperatorResult` |
| `clang-analyzer-cplusplus.*` | `cplusplus.NewDelete`, `cplusplus.STLAlgorithmModeling` |
| `clang-analyzer-deadcode.*` | `deadcode.DeadStores` (결과가 사용되지 않는 대입) |
| `clang-analyzer-security.*` | `security.FloatLoopCounter`, `security.insecureAPI.*` |
| `clang-analyzer-unix.*` | `unix.Malloc`, `unix.MismatchedDeallocator` |

---

### 4.2 이 프로젝트에서 불필요한 카테고리

| 카테고리 | 이유 |
|---|---|
| `abseil-*` | Abseil 라이브러리 전용 — 프로젝트에서 미사용 |
| `altera-*` | FPGA/OpenCL 커널 전용 |
| `boost-*` | Boost 라이브러리 전용 |
| `darwin-*` | macOS/Darwin 전용 |
| `fuchsia-*` | Fuchsia OS 전용 스타일 |
| `linuxkernel-*` | Linux 커널 전용 |
| `llvm-*` | LLVM 내부 코드베이스 전용 |
| `llvmlibc-*` | LLVM libc 구현 전용 |
| `mpi-*` | MPI 병렬 프로그래밍 전용 |
| `objc-*` | Objective-C 전용 |
| `zircon-*` | Zircon OS 전용 |

---

## 5. 억제(Suppression) 방법

### 5.1 인라인 억제 (기본 방식)

```cpp
// 한 줄 억제 (같은 줄)
int* p = (int*)malloc(10); // NOLINT(cppcoreguidelines-no-malloc)

// 다음 줄 억제
// NOLINTNEXTLINE(modernize-use-nullptr)
int* q = NULL;

// 블록 억제
// NOLINTBEGIN(performance-unnecessary-value-param)
void legacyApiWrapper(std::string s) {
    legacyApi(s.c_str());
}
// NOLINTEND(performance-unnecessary-value-param)

// 카테고리 전체 억제 (특정 규칙 지정 없이)
int arr[10]; // NOLINT
```

### 5.2 `.clang-tidy`로 파일/경로 단위 제외

```yaml
# 외부 라이브러리 전체 제외
HeaderFilterRegex: '.*(grapi-base/(base|samples)).*\.(h|hpp)$'

# 특정 체크만 제외
Checks: '-*,bugprone-*,-bugprone-macro-parentheses'
```

### 5.3 하위 디렉토리별 별도 설정

```yaml
# external/.clang-tidy (external 디렉토리 전체 체크 비활성화)
Checks: '-*'
```

### 5.4 억제 기록 원칙 (MISRA Deviation 정신)

NOLINT를 쓸 때는 **왜 억제하는지** 사유를 함께 남기는 팀 규칙 권장:

```cpp
// NOLINTNEXTLINE(cppcoreguidelines-pro-type-reinterpret-cast)
// 이유: GPU 드라이버 API가 void* 인터페이스를 요구하므로 불가피
auto* gpuPtr = reinterpret_cast<GpuBuffer*>(driverHandle);
```

---

## 6. 단계별 도입 전략

```
1단계 (현재)
─────────────────────────────────────────────────────────────────
활성화: bugprone-*, 핵심 cppcoreguidelines-*, performance-*, portability-*,
        modernize-use-nullptr, modernize-use-override
WarningsAsErrors: 비워둠 (경고만, 빌드 안 깨짐)
목표: 현재 위반 건수 파악, 오탐 패턴 식별

2단계 (1단계 위반 정리 후)
─────────────────────────────────────────────────────────────────
추가: hicpp-signed-bitwise, hicpp-exception-baseclass,
      cert-flp30-c, cert-err34-c, misc-no-recursion, misc-const-correctness
WarningsAsErrors: 1단계 체크 중 노이즈 적은 것 일부 승격

3단계 (MISRA 준비 단계)
─────────────────────────────────────────────────────────────────
추가: cppcoreguidelines-pro-type-member-init, cppcoreguidelines-avoid-goto,
      cppcoreguidelines-pro-bounds-pointer-arithmetic, cppcoreguidelines-pro-type-vararg,
      hicpp-multiway-paths-covered
WarningsAsErrors: 안전-핵심 체크 전부 승격
목표: CI 빌드 게이트 적용

4단계 (CI 완전 통합)
─────────────────────────────────────────────────────────────────
- PR 변경 파일만 증분 분석 (run-clang-tidy.py + git diff)
- 주기적 풀스캔에 clang-analyzer-* 추가 (야간 빌드)
- NOLINT 사용 시 코드 리뷰에서 사유 확인 의무화
```

### 체크 추가 시 권장 순서

```
1. .clang-tidy에 체크 추가 (WarningsAsErrors는 비워둔 채로)
2. 전체 스캔 후 위반 건수/패턴 파악
3. 명백한 버그 패턴 → 즉시 수정
4. 오탐 또는 레거시 예외 → NOLINT + 사유 주석
5. 위반 0건 또는 관리 가능 수준 도달 후 WarningsAsErrors에 추가
```

---

## 7. 결과 출력 형식 이해

```
C:\working\grapi-base\base\src\renderer.cpp:42:15: warning: use nullptr instead of NULL [modernize-use-nullptr]
    int* ptr = NULL;
               ^~~~
               nullptr
```

| 항목 | 설명 |
|---|---|
| `base/src/renderer.cpp:42:15` | 파일 경로, 줄 번호, 열 번호 |
| `warning` / `error` | `WarningsAsErrors`에 해당 체크가 있으면 `error`로 격상됨 |
| `[modernize-use-nullptr]` | 위반한 체크 이름 — NOLINT 인자로 그대로 사용 |
| `^~~~` / `nullptr` | 위반 위치 + 수정 제안 (자동 수정 가능 체크의 경우) |

### severity 기준

| severity | 의미 | CI 동작 |
|---|---|---|
| `warning` | `WarningsAsErrors`에 없는 체크 | 빌드 계속 진행 |
| `error` | `WarningsAsErrors`에 포함된 체크 | `--error-exitcode=1`과 함께 쓰면 CI 실패 |
| `note` | 보조 정보 (실제 위반은 아님) | 무시 |

---

## 8. 출처

- [Clang-Tidy official documentation](https://clang.llvm.org/extra/clang-tidy/)
- [Clang-Tidy Checks list (LLVM 19)](https://clang.llvm.org/extra/clang-tidy/checks/list.html)
- [Using Clang-Tidy in Visual Studio (Microsoft Learn)](https://learn.microsoft.com/ko-kr/cpp/code-quality/clang-tidy?view=msvc-170)
- [CMakePresets.json Clang-Tidy 통합 — Microsoft](https://learn.microsoft.com/ko-kr/cpp/build/cmake-presets-vs?view=msvc-170)
- [C++ Core Guidelines Clang-Tidy checks](https://clang.llvm.org/extra/clang-tidy/checks/cppcoreguidelines/index.html)
- [CERT C/C++ Coding Standard](https://wiki.sei.cmu.edu/confluence/pages/viewpage.action?pageId=88046682)
- [HIC++ Coding Standard](https://www.perforce.com/resources/qac/high-integrity-cpp-coding-standard)
