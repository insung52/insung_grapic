# 빌드 경고 정리 (전 플랫폼)

> filament v1.72.0 머지 이후 전 플랫폼 빌드에서 수집한 경고 목록.  
> 에러 없이 빌드 성공 상태에서 잔존하는 경고들.

---

## 요약

| # | 경고 | 플랫폼 | 발생 위치 | 우선순위 |
|---|------|--------|-----------|----------|
| W-1 | MSVC D9002: `-fno-rtti` 알 수 없는 옵션 | Windows | filament 서드파티 CMakeLists | 낮음 |
| W-2 | MSVC D9025: `/std:c++latest` → `/std:c++17` 재정의 | Windows | filament 내부 CMakeLists | 낮음 |
| W-3 | MSVC D9025: `/W0` → `/W2` 재정의 | Windows | filament 내부 CMakeLists | 낮음 |
| W-4 | CMake: HarfBuzz CMake 지원은 커뮤니티 유지 | Linux / Android / Embedded | `external/harfbuzz/CMakeLists.txt:4` | 낮음 |
| W-5 | GCC cc1: `-fno-rtti`를 C 파일에 전달 | Embedded | filament 서드파티 CMakeLists | 낮음 |
| W-6 | Clang: 알 수 없는 `-Wno-nontrivial-memcall` 옵션 | Android x86 | `external/filament/third_party/assimp` | 낮음 |
| W-7 | `tmpnam` deprecated (보안 위험) | Android x86 | `external/lua/loslib.c:172` | 중간 |

---

## W-1 — MSVC D9002: `-fno-rtti` (Windows)

**경고 메시지**
```
cl : 명령줄 warning D9002 : 알 수 없는 '-fno-rtti' 옵션을 무시합니다.
```

**발생 빈도**: 수백 회 (빌드 타겟 수만큼 반복)  
**발생 위치**: filament 서드파티 라이브러리들의 CMakeLists.txt

**원인**:  
`-fno-rtti`는 GCC/Clang 전용 플래그 (RTTI 비활성화). MSVC에서는 `/GR-`에 해당.  
filament 내 여러 서드파티 라이브러리가 `target_compile_options`에 `-fno-rtti`를 하드코딩.  
MSVC는 이 플래그를 인식하지 못해 경고 후 무시 → 빌드 결과에는 영향 없음.

**영향**: 없음 (MSVC가 플래그를 무시하고 컴파일 계속)  
**수정 방법**: 서드파티 CMakeLists.txt에서 컴파일러별 분기 처리 필요 (upstream 이슈)  
**권고**: 수정 불필요 (third-party 코드, upstream에서 관리)

---

## W-2 — MSVC D9025: `/std:c++latest` → `/std:c++17` 재정의 (Windows)

**경고 메시지**
```
cl : 명령줄 warning D9025 : '/std:c++latest'을(를) '/std:c++17'(으)로 재정의합니다.
```

**발생 위치**: filament 내부 일부 타겟

**원인**:  
filament 내부에서 특정 타겟에 `/std:c++latest`를 지정하지만,  
grapi-base의 `CMAKE_CXX_STANDARD: 17` 설정이 이를 `/std:c++17`로 덮어씀.  
마지막으로 지정된 `/std:c++17`이 실제 적용되므로 동작에는 영향 없음.

**영향**: 없음  
**권고**: 수정 불필요

---

## W-3 — MSVC D9025: `/W0` → `/W2` 재정의 (Windows)

**경고 메시지**
```
cl : 명령줄 warning D9025 : '/W0'을(를) '/W2'(으)로 재정의합니다.
```

**원인**:  
filament 서드파티 타겟이 내부적으로 `/W0` (경고 없음) 지정 →  
프로젝트 레벨에서 `/W2`로 덮어씀.  
실제 적용 경고 수준은 `/W2`.

**영향**: 없음  
**권고**: 수정 불필요

---

## W-4 — CMake HarfBuzz 경고 (Linux / Android / Embedded)

**경고 메시지**
```
CMake Warning at external/harfbuzz/CMakeLists.txt:4 (message):
  The main build system for HarfBuzz is Meson. CMake build support is
  community-maintained and is not actively supported by HarfBuzz developers.
```

**발생 플랫폼**: Linux Desktop, Android (arm64/arm/x64/x86), Embedded  
**발생 위치**: `external/harfbuzz/CMakeLists.txt:4`

**원인**:  
HarfBuzz 프로젝트가 Meson을 공식 빌드 시스템으로 전환.  
grapi-base는 CMake 빌드를 사용하므로 HarfBuzz CMakeLists.txt가 직접 경고 출력.

**영향**: 없음 (빌드 정상 완료)  
**권고**: 수정 불필요. HarfBuzz 버전 업그레이드 시 CMake 지원 유지 여부 모니터링.

---

## W-5 — GCC cc1: `-fno-rtti`를 C 파일에 전달 (Embedded)

**경고 메시지**
```
cc1: warning: command line option '-fno-rtti' is valid for C++/D/ObjC++ but not for C
```

**발생 빈도**: 수십 회  
**발생 위치**: filament 서드파티 라이브러리 내 C 소스 파일 컴파일

**원인**:  
W-1과 동일한 근본 원인. `-fno-rtti`가 C++ 전용 플래그인데 C 파일 컴파일에도 전달됨.  
GCC는 이를 경고하고 무시. C 언어에는 RTTI 개념 자체가 없으므로 실제 영향 없음.

**영향**: 없음  
**권고**: 수정 불필요 (third-party 코드, upstream 이슈)

---

## W-6 — Clang: 알 수 없는 경고 플래그 `-Wno-nontrivial-memcall` (Android x86)

**경고 메시지**
```
warning: unknown warning option '-Wno-nontrivial-memcall';
  did you mean '-Wno-nontrivial-memaccess'? [-Wunknown-warning-option]
```

**발생 위치**: `external/filament/third_party/assimp/tnt` — `ioapi.c`, `unzip.c`  
**발생 플랫폼**: Android x86 (Clang 19)만 해당 (다른 ABI에서는 미발생)

**원인**:  
assimp 라이브러리가 존재하지 않는 경고 억제 플래그 `-Wno-nontrivial-memcall` 사용.  
올바른 플래그는 `-Wno-nontrivial-memaccess`.  
Android x86에서만 재구성이 필요해 Clang 19가 이를 파싱하면서 경고 출력.  
다른 ABI는 캐시 재사용으로 해당 파일 미재컴파일.

**영향**: 없음 (경고 억제 실패로 추가 경고가 나올 수 있으나 빌드/런타임 영향 없음)  
**권고**: upstream assimp 이슈. 수정 불필요.

---

## W-7 — `tmpnam` deprecated (Android x86 / Linux)

**경고 메시지**
```
/home/.../external/lua/loslib.c:172:3: warning: 'tmpnam' is deprecated:
  tmpnam is unsafe, use mkstemp or tmpfile instead [-Wdeprecated-declarations]
```

**발생 위치**: `external/lua/loslib.c:172`  
**발생 플랫폼**: Android x86 빌드 로그에서 확인 (Linux 빌드 로그에도 존재)

**원인**:  
lua 표준 라이브러리(`loslib.c`)가 `tmpnam()`을 사용.  
`tmpnam()`은 경쟁 조건(race condition)으로 인한 보안 취약점이 있어 deprecated.  
POSIX 표준에서 `mkstemp()` 또는 `tmpfile()` 사용을 권장.

**영향**:
- 런타임 영향: 없음 (경고만 출력, 빌드 성공)
- 보안 관점: `tmpnam()` 반환 경로를 다른 프로세스가 가로채는 TOCTOU 취약점 이론적 존재
- 실제 위험: lua의 `os.tmpname()` 함수를 사용하지 않으면 코드 경로 미실행

**권고**: 낮은 우선순위로 수정 검토.  
`lua_tmpnam` 매크로를 `mkstemp` 기반으로 교체 가능 (`loslib.c` 수정 또는 매크로 재정의).

---

## 전체 평가

| 항목 | 내용 |
|------|------|
| 빌드 차단 경고 | **없음** |
| 런타임 영향 경고 | **없음** (W-7 이론적 보안 이슈 제외) |
| 수정 권고 대상 | **W-7** (`tmpnam` deprecated) — lua 교체 또는 매크로 재정의 |
| 수정 불필요 대상 | W-1, W-2, W-3, W-4, W-5, W-6 — third-party 코드 또는 무해한 충돌 |
| pre-existing 여부 | 전체 경고 모두 v1.72.0 머지 이전부터 존재했던 것으로 추정 |
