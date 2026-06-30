# C++ 컴파일러: GCC vs Clang vs MSVC

## 컴파일러란?

C++ 소스 코드(`.cpp`)를 CPU가 실행할 수 있는 기계어(`.o`, `.exe`, `.so` 등)로 변환하는 프로그램.  
언어 표준(C++17, C++20 등)은 ISO가 정의하지만, **컴파일러 플래그(옵션) 체계는 각 컴파일러가 독자적으로 정의한다.**

---

## 세 컴파일러 비교

| | GCC | Clang | MSVC |
|---|---|---|---|
| 정식 명칭 | GNU Compiler Collection | LLVM/Clang | Microsoft Visual C++ |
| 제작 | GNU 프로젝트 | LLVM 커뮤니티 (Apple·Google 참여) | Microsoft |
| 주요 플랫폼 | Linux, 임베디드 | macOS, Android, Linux | Windows |
| 실행 파일 | `gcc`, `g++` | `clang`, `clang++` | `cl.exe` |
| 플래그 접두사 | `-` (하이픈) | `-` (하이픈, GCC 호환) | `/` (슬래시) |
| 플래그 호환성 | — | GCC 플래그 대부분 지원 | GCC/Clang 플래그 **거의 지원 안 함** |

---

## GCC

Linux 생태계의 기본 컴파일러. 오픈소스 C++ 빌드 대부분이 GCC를 기준으로 작성됨.

```bash
g++ -std=c++17 -O2 -fno-rtti -Wall main.cpp -o main
```

- 내부적으로 `cc1`(C 컴파일러), `cc1plus`(C++ 컴파일러)를 드라이버가 호출
- **임베디드 크로스컴파일**에서 많이 사용: `aarch64-linux-gnu-g++`, `arm-linux-gnueabihf-g++`

---

## Clang

LLVM 프로젝트의 C/C++ 프론트엔드. GCC 플래그를 대부분 그대로 받아들임.

```bash
clang++ -std=c++17 -O2 -fno-rtti -Wall main.cpp -o main
```

**GCC와의 주요 차이점:**
- 에러/경고 메시지가 더 친절하고 자세함
- macOS 기본 컴파일러 (`apple-clang`)
- **Android NDK 컴파일러** — Android 빌드는 항상 Clang (NDK r18 이후 GCC 제거됨)
- GCC 플래그 호환이 높아 CMakeLists.txt를 거의 수정 없이 재사용 가능

---

## MSVC

Windows 전용. Visual Studio에 포함되어 있으며 `cl.exe`로 실행.  
**플래그 체계가 GCC/Clang과 완전히 다르다.**

```bat
cl.exe /std:c++17 /O2 /GR- /W2 main.cpp
```

**플래그 대응표:**

| 기능 | GCC/Clang | MSVC |
|------|-----------|------|
| C++17 표준 | `-std=c++17` | `/std:c++17` |
| 최신 C++ 표준 | `-std=c++2a` / `-std=c++20` | `/std:c++latest` |
| RTTI 비활성화 | `-fno-rtti` | `/GR-` |
| 경고 없음 | `-w` / `-W0` | `/W0` |
| 경고 레벨 2 | `-Wall` (비슷) | `/W2` |
| 최적화 | `-O2` | `/O2` |
| 위치독립코드 | `-fPIC` | 해당 없음 (x86 Windows는 항상 PIC) |
| 스택 보호 | `-fstack-protector` | `/GS` (기본 활성화) |

MSVC는 `-fno-rtti`, `-fPIC` 등 GCC 플래그를 입력받으면 **D9002 경고를 출력하고 무시**한다.

---

## 어떤 플랫폼에서 어떤 컴파일러를 쓰는가?

| 플랫폼 | 컴파일러 | 비고 |
|--------|---------|------|
| Windows | MSVC | `cl.exe`, Visual Studio |
| Linux Desktop | GCC 또는 Clang | grapi-base는 Clang 사용 |
| macOS | apple-clang | Xcode에 포함된 Clang |
| Android | Clang (NDK) | arm64/arm/x86/x64 크로스컴파일 |
| Embedded (Telechips TCC803x) | GCC 9.2.1 | Yocto SDK 제공 AArch64 크로스컴파일러 |
| WebGL (Emscripten) | emcc (Clang 기반) | WASM으로 컴파일 |

---

## CMakeLists.txt에서 컴파일러 분기 처리

서드파티 라이브러리들은 종종 컴파일러 분기 없이 GCC 플래그를 하드코딩한다.

```cmake
# 잘못된 방식 (MSVC에서 D9002 경고 발생)
target_compile_options(mylib PRIVATE -fno-rtti)

# 올바른 방식
if(NOT MSVC)
    target_compile_options(mylib PRIVATE -fno-rtti)
else()
    target_compile_options(mylib PRIVATE /GR-)
endif()

# 또는 CMake 추상화 활용
set_target_properties(mylib PROPERTIES
    CXX_RTTI OFF   # CMake 3.x: 내부적으로 컴파일러별 플래그로 변환
)
```

CMake가 제공하는 `$<CXX_COMPILER_ID:MSVC>` generator expression을 쓰면 더 간결하게 분기 가능.

---

## W-1 경고 연결: filament에서 발생하는 이유

→ [`rtti_and_fno_rtti.md`](rtti_and_fno_rtti.md) 참조

filament 서드파티 라이브러리들의 CMakeLists.txt에는 MSVC 분기 없이  
`-fno-rtti`가 하드코딩되어 있다:

```cmake
# filament 서드파티 CMakeLists.txt (예시)
target_compile_options(${LIB_TARGET} PRIVATE -fno-rtti)
```

- **GCC/Clang**: 정상 처리 → RTTI 비활성화
- **MSVC**: D9002 경고 출력 후 무시 → **RTTI가 활성화된 채로 컴파일됨**

결과적으로 Windows 빌드에서는 filament 서드파티가 RTTI on 상태로 컴파일된다.  
그러나 filament 자체가 `dynamic_cast`/`typeid`를 사용하지 않으므로 런타임 동작에는 영향 없음.

**수정 방법**: filament upstream CMakeLists.txt에 MSVC 분기 추가.  
upstream 이슈이므로 grapi-base에서 직접 수정 불필요.
