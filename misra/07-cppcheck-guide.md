# Cppcheck 실행 가이드 — grapi-base 프로젝트 기준

> 이 문서는 `C:\working\grapi-base` 엔진 프로젝트에서 Cppcheck를 실제로 사용하는 방법 정리.  
> 도구 개요·한계·Clang-Tidy와의 비교는 [03-cppcheck-clangtidy-deepdive.md](03-cppcheck-clangtidy-deepdive.md) §1 참고.  
> (2026-06 기준, Cppcheck 2.21.0)

---

## 0. 이 프로젝트 환경 요약

| 항목 | 내용 |
|------|------|
| 엔진 경로 | `C:\working\grapi-base` |
| 컴파일 DB | `out/build/windows-msvc-x64-debug/compile_commands.json` |
| 외부 라이브러리 | `external/filament/` — 분석 대상 제외 필요 |
| 분석 대상 | `base/src/grapi/base/` |

> `compile_commands.json`은 Clang-Tidy 설정 시 이미 생성됨. 없을 경우:
> ```cmd
> cd C:\working\grapi-base
> cmake --preset windows-msvc-x64-debug -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
> ```

---

## 1. 설치

### 1.1 Windows 인스톨러 (권장)

[https://sourceforge.net/projects/cppcheck/](https://sourceforge.net/projects/cppcheck/) 에서 최신 버전 다운로드.

- 파일명: `cppcheck-2.21.0-x64-Setup.msi` (약 23MB)
- 설치 후 기본 경로: `C:\Program Files\Cppcheck\cppcheck.exe`

설치 확인:
```cmd
cppcheck --version
```
출력 예: `Cppcheck 2.21.0`

> PATH에 자동 등록됨. 안 됐다면 `C:\Program Files\Cppcheck` 을 시스템 환경변수 PATH에 수동 추가.

### 1.2 Chocolatey (패키지 관리자 사용 시)

```powershell
choco install cppcheck
```

---

## 2. 기본 실행

### 2.1 단일 파일 (빠른 테스트용)

```cmd
cppcheck --enable=all C:\working\grapi-base\base\src\grapi\base\scene_impl.cc
```

### 2.2 compile_commands.json 기반 전체 스캔 (권장)

```cmd
cd C:\working\grapi-base

cppcheck ^
  --project=out/build/windows-msvc-x64-debug/compile_commands.json ^
  "--file-filter=*\grapi-base\base\*" ^
  --enable=all ^
  --suppress=missingIncludeSystem ^
  --inline-suppr ^
  --template=vs ^
  -j 4 ^
  2> cppcheck_result.txt
```

> **주의**: Cppcheck의 진단 출력은 **stdout이 아닌 stderr**로 나옴. 파일로 저장하려면 `2>` 사용.  
> **외부 라이브러리 제외**: `--suppress`로 경로 필터링이 Windows에서 동작하지 않음 (백슬래시/포워드슬래시 모두 실패). `--file-filter`로 분석 대상 파일 자체를 제한하는 것이 유일하게 동작하는 방법. include된 external 헤더 경고는 출력에 혼재될 수 있으나 `base\` 경로 결과만 참조.

---

## 3. 주요 옵션 설명

| 옵션 | 설명 |
|------|------|
| `--project=<path>` | CMake가 생성한 compile_commands.json 사용. include 경로·매크로를 자동 반영해 정확도 향상 |
| `--enable=all` | 모든 체크 활성화 (기본은 `error`만). `warning`, `style`, `performance`, `portability`, `information`, `unusedFunction` 포함 |
| `--enable=warning,style,performance` | 필요한 카테고리만 선택 활성화 |
| `--suppress=missingIncludeSystem` | 시스템 헤더 누락 경고 억제 (Windows에서 빈번히 발생) |
| `"--file-filter=*\grapi-base\base\*"` | 분석 대상 파일을 패턴 일치 파일로 제한. external/ 전체 제외에 유일하게 동작하는 방법 (suppress 경로 필터는 Windows에서 동작 안 함) |
| `--inline-suppr` | 코드 내 `// cppcheck-suppress <id>` 주석으로 개별 억제 허용 |
| `--error-exitcode=1` | error 등급 발견 시 비정상 종료 (CI 게이트 연동용). 로컬 스캔 시엔 `0`으로 두기 |
| `--xml` | 결과를 XML 형식으로 출력 (도구 연동용) |
| `--template=vs` | Visual Studio 형식으로 출력 (`파일(줄): 메시지`) |
| `--template=gcc` | GCC 형식으로 출력 (`파일:줄:열: 메시지`) |
| `-j 4` | 병렬 스레드 수 (빠른 분석) |
| `--ctu` | Cross-Translation-Unit 분석 — 파일 간 연관 분석으로 정확도 향상, 분석 시간 증가 |

### 3.1 enable 카테고리 상세

| 카테고리 | 탐지 내용 |
|----------|-----------|
| `error` | 명백한 버그 (기본 활성) — 널 포인터 역참조, 범위 초과, 메모리 누수 등 |
| `warning` | 잠재적 버그 — 초기화되지 않은 변수, 부호 있는/없는 비교 등 |
| `style` | 코딩 스타일 — 사용하지 않는 변수/함수, 불필요한 코드 등 |
| `performance` | 성능 — 불필요한 복사, 비효율적 문자열 연산 등 |
| `portability` | 이식성 — 플랫폼 의존적 코드 |
| `information` | 분석 정보 — 분석 불가 파일 알림 등 |
| `unusedFunction` | 사용되지 않는 함수 (단일 파일 분석 시 많은 오탐 → 전체 스캔에서만 의미 있음) |

---

## 4. 외부 라이브러리 제외

`--project=compile_commands.json` 사용 시 컴파일 DB에 포함된 모든 파일이 분석 대상이 됨. Filament 등 서드파티 코드는 제외해야 노이즈가 줄어듦.

### 방법: --file-filter로 분석 대상 파일 제한 (유일하게 동작하는 방법)

```cmd
"--file-filter=*\grapi-base\base\*"
```

compile_commands.json에 등록된 파일 중 패턴에 맞는 파일만 분석. external/ 전체가 분석에서 제외됨.

> **suppress 방식은 Windows에서 동작하지 않음**:  
> - `--suppress=*:*\external\*` (백슬래시) — 매칭 안 됨  
> - `--suppress=*:*/external/*` (포워드슬래시) — 매칭 안 됨  
> - `.cppcheck` XML `<exclude>` — `<paths>` 없으면 "no C or C++ source files found" 오류  
>
> 위 방법을 모두 시도했으나 Windows에서 경로 매칭 실패. `--file-filter`만 정상 동작 확인됨.

> **참고**: include된 external 헤더 경고는 출력에 일부 혼재될 수 있음. `base\` 경로가 포함된 라인만 참조하면 됨.

---

## 5. 경고 억제 방법

### 5.1 코드 내 인라인 억제

```cpp
// 단일 라인 억제
int* p = nullptr;
p->func(); // cppcheck-suppress nullPointer

// 다음 라인 억제
// cppcheck-suppress uninitvar
int x;
use(x);
```

`--inline-suppr` 옵션을 줘야 인라인 억제가 동작함.

### 5.2 억제 목록 파일

반복적으로 뜨는 오탐을 파일로 관리:

```
// cppcheck-suppressions.txt
missingIncludeSystem
// 외부 라이브러리 억제 (포워드슬래시 필수)
*:*/external/filament/*
*:*/external/thorvg/*
*:*/external/basisu/*
```

```cmd
cppcheck --suppressions-list=cppcheck-suppressions.txt ...
```

### 5.3 특정 룰+파일 단위 억제

```
// 형식: <rule_id>:<file_path>:<line>
uninitvar:base/src/grapi/base/scene_impl.cc:707
```

---

## 6. 출력 형식 및 파일 저장

### 6.1 기본 텍스트 저장 (CMD)

```cmd
cppcheck --project=... --enable=all 2> cppcheck_result.txt
```

### 6.2 VS 에러 형식으로 저장

```cmd
cppcheck --project=... --enable=all --template=vs 2> cppcheck_result.txt
```

출력 예:
```
C:\working\grapi-base\base\src\grapi\base\scene_impl.cc(707): error: ...
```

### 6.3 XML 출력 (도구 파이프라인용)

```cmd
cppcheck --project=... --enable=all --xml 2> cppcheck_result.xml
```

HTML 리포트로 변환 (cppcheck 설치 폴더에 스크립트 포함):
```cmd
python "C:\Program Files\Cppcheck\htmlreport\cppcheck-htmlreport.py" ^
  --file=cppcheck_result.xml ^
  --report-dir=cppcheck_html ^
  --source-dir=C:\working\grapi-base
```

→ `cppcheck_html\index.html`로 브라우저에서 확인 가능.

---

## 7. grapi-base 권장 실행 명령

단계별로 노이즈를 줄이며 진행하는 순서:

### Step 1 — error만 (가장 중요한 것부터)

```cmd
cd C:\working\grapi-base

cppcheck ^
  --project=out/build/windows-msvc-x64-debug/compile_commands.json ^
  "--file-filter=*\grapi-base\base\*" ^
  --enable=error ^
  --suppress=missingIncludeSystem ^
  --template=vs ^
  2> cppcheck_step1_error.txt
```

### Step 2 — warning, performance 추가

```cmd
cd C:\working\grapi-base

cppcheck ^
  --project=out/build/windows-msvc-x64-debug/compile_commands.json ^
  "--file-filter=*\grapi-base\base\*" ^
  --enable=error,warning,performance ^
  --suppress=missingIncludeSystem ^
  --inline-suppr ^
  --template=vs ^
  2> cppcheck_step2_warning.txt
```

### Step 3 — 전체 (style, portability 포함)

```cmd
cd C:\working\grapi-base

cppcheck ^
  --project=out/build/windows-msvc-x64-debug/compile_commands.json ^
  "--file-filter=*\grapi-base\base\*" ^
  --enable=all ^
  --suppress=missingIncludeSystem ^
  --inline-suppr ^
  --template=vs ^
  -j 4 ^
  2> cppcheck_full.txt
```

---

## 8. 결과 해석 — 출력 형식

```
파일경로(줄번호): 등급 id: 메시지 [체크ID]
```

예시:
```
C:\working\grapi-base\base\src\grapi\base\scene_impl.cc(707): warning: Member variable 'SceneImpl::dirty_' is not initialized in the constructor. [uninitMemberVar]
```

### 등급 분류

| 등급 | 의미 |
|------|------|
| `error` | 명확한 버그 — 거의 무조건 수정 필요 |
| `warning` | 잠재적 버그 — 검토 후 수정 여부 판단 |
| `style` | 코딩 컨벤션/품질 — 팀 정책에 따라 처리 |
| `performance` | 성능 개선 가능 지점 |
| `portability` | 타 플랫폼(Linux/Android/QNX 빌드) 이식성 문제 |
| `information` | 분석 메타 정보 — 무시 가능 |

---

## 9. Clang-Tidy와 역할 분담

> 두 도구를 병행하면 서로의 탐지 공백을 보완함.

| 탐지 영역 | Cppcheck | Clang-Tidy |
|-----------|----------|------------|
| 널 포인터 역참조 | 강함 | 보통 |
| 메모리 누수 | 강함 | 보통 |
| 초기화 안 된 변수 | 강함 | 보통 |
| 배열 범위 초과 | 강함 | 약함 |
| C 스타일 캐스트 | 약함 | **강함** |
| 네이밍 컨벤션 | 없음 | **강함** |
| 모던 C++ 패턴 (`override`, `nullptr` 등) | 약함 | **강함** |
| 성능 패턴 (불필요한 복사 등) | 보통 | **강함** |
| 컴파일 DB 없이 실행 | 가능 | 사실상 불가 |
| 분석 속도 | 빠름 | 느림 |

---

## 10. 관련 문서

- [03-cppcheck-clangtidy-deepdive.md](03-cppcheck-clangtidy-deepdive.md) — Cppcheck 한계·MISRA addon 사용법 상세
- [06-clang-tidy-guide.md](06-clang-tidy-guide.md) — Clang-Tidy 상세 실행 가이드
- [07-verification-report.md](07-verification-report.md) — 도구별 실행 결과 보고서 (Clang-Tidy + Cppcheck 결과 포함)
- [02-tools.md](02-tools.md) — 상용 도구 비교 (MISRA 인증 필요 시)
