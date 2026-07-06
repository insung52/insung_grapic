# 멀티플랫폼 정적분석 검증 계획 — grapi-base

> 지금까지의 Clang-Tidy/Cppcheck 검증([09] 문서, 현재 파일명 `260706_황인성_clangtidy_cppcheck_verification_report.md`)은 전부 **Windows MSVC(`windows-msvc-x64-debug`) 컴파일 DB 하나만** 기준으로 수행됨.  
> WebGL 빌드에서 `-fno-exceptions` 관련 컴파일 에러가 실제로 발생(A-9 후속 수정)하면서, Windows 전용 검증이 다른 플랫폼에 대해 아무 보증도 못 한다는 게 실증됨.  
> 이 문서는 WSL 환경을 이용해 나머지 플랫폼을 어떻게, 어떤 순서로, 어떤 명령어로 검증할지 정리한 계획 문서.  
> (2026-07 작성, 대상 WSL: Ubuntu, clang 21.1.8 / Cppcheck 후보 2.19.0)

---

## 1. 왜 플랫폼별로 다시 봐야 하나

파일에 `#ifdef __ANDROID__` 같은 명시적 분기가 있는지 여부만으로는 부족함. 아래 요인들이 **분기 없는 코드에도** 서로 다른 결과를 만들 수 있음:

| 요인 | 영향 |
|------|------|
| 타입 폭 차이 | `size_t`/포인터 폭이 32비트(Android arm, Telechips 등)와 64비트(데스크톱)에서 다름 → B-1(narrowing conversion), B-2(implicit widening) 계열이 플랫폼마다 다르게 나올 수 있음 |
| 컴파일러/표준 라이브러리 차이 | Windows는 MSVC STL, Linux/Android/WebGL은 libc++ 또는 libstdc++ — 헤더 구현이 다르면 진단도 달라짐 |
| 컴파일 플래그 차이 | `-fno-exceptions`(WebGL), `-fno-rtti`, 아키텍처별 `-m32`/`-m64` 등 — 코드 자체가 아예 컴파일 안 될 수도 있음 (이번 A-9 사례) |
| 매크로/헤더 체인 차이 | 파일 자체엔 분기가 없어도 포함하는 서드파티 헤더(Filament, Jolt 등) 내부에 플랫폼 분기가 있으면 실제 인스턴스화되는 코드가 달라짐 |

**결론**: 각 플랫폼의 실제 `compile_commands.json`으로 `base/` 전체를 다시 스캔하는 것이 정확한 검증. 파일 일부만 골라서 보는 방식은 채택하지 않음.

---

## 2. 플랫폼 현황

CMakePresets.json 기준 전체 타깃과, 현재 WSL 환경에서 바로 가능한지 여부:

| Preset | 툴체인 | WSL 준비 상태 | 비고 |
|--------|--------|---------------|------|
| `windows-msvc-x64-*` | MSVC (`cl.exe`) | (Windows에서 완료됨) | 기존 v2~v7/v8 스캔 |
| `linux-clang-*` | `/usr/bin/clang++` (libc++) | ✅ 즉시 가능 | clang 21.1.8 설치됨 |
| `linux-webgl-*` | Emscripten `em++` | ✅ 즉시 가능 | `~/emsdk` 설치됨, 빌드 성공 확인됨 |
| `linux-android-arm-*` | Android NDK (armv7) | ✅ 즉시 가능 (env만 설정) | NDK 28.2.13676358이 `~/Android/android_sdk/ndk/`에 설치됨. `ANDROID_HOME` 환경변수만 세션마다 export 필요 |
| `linux-android-arm64-*` | Android NDK (aarch64) | ✅ 즉시 가능 (env만 설정) | 상동 |
| `linux-android-x86-*` | Android NDK (x86) | ✅ 즉시 가능 (env만 설정) | 상동 |
| `linux-android-x64-*` | Android NDK (x86_64) | ✅ 즉시 가능 (env만 설정) | 상동 |
| `linux-telechips-tcc803x-*` | Yocto OE 크로스툴체인 (GCC 9.3.0) | ✅ 즉시 가능 (env만 설정) | `/opt/poky-telechips-systemd/`에 설치됨. `environment-setup-aarch64-telechips-linux` 세션마다 source 필요 |
| `linux-renesas-rcar_h3ulcb-*` | Yocto OE 크로스툴체인 (GCC 9.3.0) | ✅ 즉시 가능 (env만 설정) | `/opt/poky/3.1.11/`에 설치 완료(2026-07-02). `environment-setup-aarch64-poky-linux` 세션마다 source 필요 |
| `qnx-*` | QNX SDP | ❌ SDP 미설치 | `intro.md`에도 언급 없음 — 현재 워크플로우 대상 아닌 것으로 보임, 우선순위 낮음 |

> **정정 (최초 작성 시 오판)**: Android/Telechips/Renesas를 처음엔 "미설치"로 판단했었는데, 이는 환경변수(`ANDROID_HOME`, `OECORE_NATIVE_SYSROOT`)를 활성화하지 않은 새 셸에서 확인해서 생긴 오류(Android/Telechips)이거나, 확인 시점엔 실제로 미설치였다가 이후 설치 완료(Renesas)된 것. 셋 다 이제 스캔 전 세션에서 환경 활성화만 해주면 됨.

**QNX 하나 빼고 전 플랫폼이 즉시 진행 가능한 상태.** 5장에 플랫폼별 실행 명령어가 정리되어 있음.

---

## 3. WSL 환경 준비

### 3.1 Clang-Tidy 설치

설치된 `clang`이 21.1.8이므로 버전을 맞춰 `clang-tidy-21` 설치 (버전 불일치 시 Windows에서 겪었던 것과 유사한 진단 노이즈 발생 가능):

```bash
sudo apt update
sudo apt install -y clang-tidy-21 clang-tools-21

# 버전 확인
clang-tidy-21 --version

# 편의를 위해 심볼릭 링크 (선택)
sudo ln -sf /usr/bin/clang-tidy-21 /usr/local/bin/clang-tidy
```

### 3.2 `run-clang-tidy` 스크립트 확보

Windows는 VS 번들 LLVM에 포함되어 있었지만, Ubuntu APT 패키지에는 포함되어 있지 않음. LLVM 공식 저장소에서 버전 맞춰 받기:

```bash
mkdir -p ~/llvm-tools
curl -o ~/llvm-tools/run-clang-tidy.py \
  https://raw.githubusercontent.com/llvm/llvm-project/release/21.x/clang-tools-extra/clang-tidy/tool/run-clang-tidy.py
chmod +x ~/llvm-tools/run-clang-tidy.py
```

### 3.3 Cppcheck 설치

```bash
sudo apt install -y cppcheck
cppcheck --version   # 2.19.0 예상 (Windows 2.21.0과 마이너 버전 차이 — 큰 차이 없음, 문서화만 해둘 것)
```

### 3.4 WebGL(Emscripten) 환경 활성화

`em++`가 PATH에 없는 새 셸에서는 매번 활성화 필요:

```bash
source ~/emsdk/emsdk_env.sh
em++ --version   # 정상 출력되는지 확인
```

---

## 4. compile_commands.json 생성

`CMAKE_EXPORT_COMPILE_COMMANDS`는 루트 `CMakeLists.txt`에 이미 `ON`으로 고정되어 있어 별도 옵션 불필요. `cmake --preset`만 실행하면 `out/build/<preset>/compile_commands.json`이 자동 생성됨.

```bash
cd ~/grapi-base   # WSL 쪽 경로 (Windows에서는 \\wsl.localhost\Ubuntu\home\insung52\grapi-base)

# Linux Clang
cmake --preset linux-clang-release

# WebGL
source ~/emsdk/emsdk_env.sh
cmake --preset linux-webgl-release
```

> 실제 빌드(`ninja -C out/build/<preset>`)까지 할 필요는 없음 — `compile_commands.json` 생성은 cmake configure 단계에서 끝남. 다만 빌드 자체가 통과하는지도 같이 확인하고 싶다면 `cmake --build out/build/<preset>`까지 실행.

---

## 5. 플랫폼별 스캔 명령어

Windows에서 쓰던 것과 동일한 옵션 체계(`07-cppcheck-guide.md`, `06-clang-tidy-guide.md`) 유지 — 결과 비교가 쉬워지도록.

### 5.1 Linux Clang (`linux-clang-release`)

**Clang-Tidy**:
```bash
cd ~/grapi-base
python3 ~/llvm-tools/run-clang-tidy.py \
  -clang-tidy-binary=/usr/bin/clang-tidy-21 \
  -p=out/build/linux-clang-release \
  -j$(nproc) \
  '.*base/src/.*' \
  > clangtidy_linux-clang_v2.txt 2>&1
```

**Cppcheck**:
```bash
cd ~/grapi-base
cppcheck \
  --project=out/build/linux-clang-release/compile_commands.json \
  "--file-filter=*/grapi-base/base/*" \
  --enable=all \
  --suppress=missingIncludeSystem \
  --inline-suppr \
  -j$(nproc) \
  2> cppcheck_linux-clang_v2.txt
```

### 5.2 WebGL (`linux-webgl-release`)

```bash
source ~/emsdk/emsdk_env.sh
cd ~/grapi-base
```

**Clang-Tidy**:
```bash
python3 ~/llvm-tools/run-clang-tidy.py \
  -clang-tidy-binary=/usr/bin/clang-tidy-21 \
  -p=out/build/linux-webgl-release \
  -j$(nproc) \
  '.*base/src/.*' \
  > clangtidy_webgl_v2.txt 2>&1
```
> `em++`가 내부적으로 clang 프론트엔드이긴 하나, `run-clang-tidy`는 `-clang-tidy-binary`로 지정한 별도 `clang-tidy-21`을 사용해 `compile_commands.json`의 플래그(`-fno-exceptions` 등)만 그대로 재사용함. em++ 자체를 clang-tidy 대신 쓰는 게 아니므로 위 방식이 맞음.

**Cppcheck**:
```bash
cppcheck \
  --project=out/build/linux-webgl-release/compile_commands.json \
  "--file-filter=*/grapi-base/base/*" \
  --enable=all \
  --suppress=missingIncludeSystem \
  --inline-suppr \
  -j$(nproc) \
  2> cppcheck_webgl_v2.txt
```

### 5.3 Android (`linux-android-arm64-release` 등 4종)

Android SDK/NDK가 `~/Android/android_sdk`에 이미 설치되어 있음(NDK 28.2.13676358). `ANDROID_HOME`만 세션마다 export:

```bash
export ANDROID_HOME=~/Android/android_sdk
cd ~/grapi-base
cmake --preset linux-android-arm64-release
```

**Clang-Tidy** — NDK에 번들된 clang-tidy(LLVM 19.0.1) 사용 권장. 배포용 clang-tidy-21과 버전이 다르므로 반드시 NDK 것을 지정할 것 (버전 불일치 시 Windows에서 겪은 것과 같은 노이즈 발생 가능):

```bash
NDK_CLANG_TIDY=~/Android/android_sdk/ndk/28.2.13676358/toolchains/llvm/prebuilt/linux-x86_64/bin/clang-tidy

python3 ~/llvm-tools/run-clang-tidy.py \
  -clang-tidy-binary=$NDK_CLANG_TIDY \
  -p=out/build/linux-android-arm64-release \
  -j$(nproc) \
  '.*base/src/.*' \
  > clangtidy_android-arm64_v2.txt 2>&1
```

**Cppcheck**:
```bash
cppcheck \
  --project=out/build/linux-android-arm64-release/compile_commands.json \
  "--file-filter=*/grapi-base/base/*" \
  --enable=all \
  --suppress=missingIncludeSystem \
  --inline-suppr \
  -j$(nproc) \
  2> cppcheck_android-arm64_v2.txt
```

> 4개 ABI(`arm`, `arm64`, `x86`, `x64`) 전부 도는 게 이상적이나, 32비트(`arm`, `x86`)와 64비트(`arm64`, `x64`)에서 타입 폭 관련 체크(B-1/B-2)가 갈릴 가능성이 가장 높으므로 시간이 부족하면 **`arm`(32비트 대표) + `arm64`(64비트 대표) 2종 우선** 진행. preset 이름만 바꿔서 동일 명령 반복.

**나머지 3종(`arm`/`x86`/`x64`) 전체 명령어** (2026-07-03 추가 — arm64만 먼저 스캔했던 것을 뒤늦게 인지, 나머지도 필요 시 아래 그대로 실행):

```bash
export ANDROID_HOME=~/Android/android_sdk
cd ~/grapi-base
NDK_CLANG_TIDY=~/Android/android_sdk/ndk/28.2.13676358/toolchains/llvm/prebuilt/linux-x86_64/bin/clang-tidy

# ── arm (32비트) ──
cmake --preset linux-android-arm-release

python3 ~/llvm-tools/run-clang-tidy.py \
  -clang-tidy-binary=$NDK_CLANG_TIDY \
  -p=out/build/linux-android-arm-release \
  -j$(nproc) \
  '.*base/src/.*' \
  > clangtidy_android-arm_v2.txt 2>&1

cppcheck \
  --project=out/build/linux-android-arm-release/compile_commands.json \
  "--file-filter=*/grapi-base/base/*" \
  --enable=all \
  --suppress=missingIncludeSystem \
  --inline-suppr \
  -j$(nproc) \
  2> cppcheck_android-arm_v2.txt

# ── x86 ──
cmake --preset linux-android-x86-release

python3 ~/llvm-tools/run-clang-tidy.py \
  -clang-tidy-binary=$NDK_CLANG_TIDY \
  -p=out/build/linux-android-x86-release \
  -j$(nproc) \
  '.*base/src/.*' \
  > clangtidy_android-x86_v2.txt 2>&1

cppcheck \
  --project=out/build/linux-android-x86-release/compile_commands.json \
  "--file-filter=*/grapi-base/base/*" \
  --enable=all \
  --suppress=missingIncludeSystem \
  --inline-suppr \
  -j$(nproc) \
  2> cppcheck_android-x86_v2.txt

# ── x64 ──
cmake --preset linux-android-x64-release

python3 ~/llvm-tools/run-clang-tidy.py \
  -clang-tidy-binary=$NDK_CLANG_TIDY \
  -p=out/build/linux-android-x64-release \
  -j$(nproc) \
  '.*base/src/.*' \
  > clangtidy_android-x64_v2.txt 2>&1

cppcheck \
  --project=out/build/linux-android-x64-release/compile_commands.json \
  "--file-filter=*/grapi-base/base/*" \
  --enable=all \
  --suppress=missingIncludeSystem \
  --inline-suppr \
  -j$(nproc) \
  2> cppcheck_android-x64_v2.txt
```

우선순위: `arm`(32비트 타입폭 차이 커버, 가장 중요) > `x64` > `x86`(대체로 `arm`/`x64`와 겹칠 가능성 높음, 여유 없으면 생략 가능).

### 5.4 Telechips TCC803x (`linux-telechips-tcc803x-release`)

`/opt/poky-telechips-systemd/`에 이미 설치되어 있음. 세션마다 환경 활성화 필요:

```bash
source /opt/poky-telechips-systemd/nodistro.0/environment-setup-aarch64-telechips-linux
cd ~/grapi-base
cmake --preset linux-telechips-tcc803x-release
```

> **Clang-Tidy는 사용 불가**: 실제 확인 결과 이 툴체인은 `aarch64-telechips-linux-g++` — **GCC 기반**(`CMakePresets.json`의 `FILAMENT_ENABLE_EXPERIMENTAL_GCC_SUPPORT: ON`과 일치). GCC 전용 빌트인/확장이 섞인 sysroot 헤더를 clang 프론트엔드 기반 clang-tidy가 파싱하다 오탐/파싱 에러가 날 가능성이 높아 **Cppcheck만 사용**.

**Cppcheck**:
```bash
cppcheck \
  --project=out/build/linux-telechips-tcc803x-release/compile_commands.json \
  "--file-filter=*/grapi-base/base/*" \
  --enable=all \
  --suppress=missingIncludeSystem \
  --inline-suppr \
  -j$(nproc) \
  2> cppcheck_telechips-tcc803x_v2.txt
```

### 5.5 Renesas R-Car H3ULCB (`linux-renesas-rcar_h3ulcb-release`)

`/opt/poky/3.1.11/`에 설치 완료(2026-07-02). 세션마다 환경 활성화 필요:

```bash
source /opt/poky/3.1.11/environment-setup-aarch64-poky-linux
cd ~/grapi-base
cmake --preset linux-renesas-rcar_h3ulcb-release
```

> **cmake 버전 주의(intro.md 언급 사항)**: SDK에 내장된 cmake가 3.16.5로 프로젝트 최소 요구(3.19) 미달. 확인 결과 이 WSL 환경은 시스템 `cmake`(4.2.3, `/usr/bin/cmake`)가 PATH 우선순위상 SDK 내장 cmake보다 먼저 잡혀서 별도 조치 없이 `cmake --preset`가 정상 동작함. 만약 다른 환경에서 `cmake --version`이 3.16.5로 나오면 intro.md 안내대로 SDK 내장 cmake를 `.bak`으로 이름 변경할 것.
>
> **Clang-Tidy는 사용 불가**: `$CXX` 확인 결과 `aarch64-poky-linux-g++ (GCC) 9.3.0` — Telechips와 동일하게 **GCC 기반**. Cppcheck만 사용.

**Cppcheck**:
```bash
cppcheck \
  --project=out/build/linux-renesas-rcar_h3ulcb-release/compile_commands.json \
  "--file-filter=*/grapi-base/base/*" \
  --enable=all \
  --suppress=missingIncludeSystem \
  --inline-suppr \
  -j$(nproc) \
  2> cppcheck_renesas-rcar_h3ulcb_v2.txt
```

### 5.6 결과 파일 위치

WSL 쪽에서 생성된 결과 파일(`~/grapi-base/*.txt`)은 Windows에서 아래 경로로 그대로 열람 가능:
```
\\wsl.localhost\Ubuntu\home\insung52\grapi-base\clangtidy_linux-clang_v2.txt
\\wsl.localhost\Ubuntu\home\insung52\grapi-base\cppcheck_linux-clang_v2.txt
\\wsl.localhost\Ubuntu\home\insung52\grapi-base\clangtidy_webgl_v2.txt
\\wsl.localhost\Ubuntu\home\insung52\grapi-base\cppcheck_webgl_v2.txt
\\wsl.localhost\Ubuntu\home\insung52\grapi-base\clangtidy_android-arm64_v2.txt
\\wsl.localhost\Ubuntu\home\insung52\grapi-base\cppcheck_android-arm64_v2.txt
\\wsl.localhost\Ubuntu\home\insung52\grapi-base\cppcheck_telechips-tcc803x_v2.txt
\\wsl.localhost\Ubuntu\home\insung52\grapi-base\cppcheck_renesas-rcar_h3ulcb_v2.txt
```

---

## 6. 결과 분석 방법 — Windows 결과와 비교

목표는 "완전히 새로 처음부터 분류"가 아니라 **Windows 스캔에서 못 보던 플랫폼 고유 항목만 추려내는 것**.

### 6.1 유저 코드(`base/`)만 필터링

Linux 경로 구분자는 `/`이므로 기존 Windows용 grep 패턴(`^base\\`)과 다름:

```bash
grep -E "^base/|/base/" clangtidy_linux-clang_v2.txt | grep -v "external/"
grep -E "^base/" cppcheck_linux-clang_v2.txt | grep -v "external/"
```

### 6.2 기존 항목과의 대조

`260706_황인성_clangtidy_cppcheck_verification_report.md`에 이미 정리된 A~F 등급 항목(특히 B-1/B-2 narrowing/widening 계열, F-1~F-6 플랫폼 불가피 패턴)과 대조:

- **동일한 항목이 나오면**: 이미 처리/문서화된 것이므로 스킵.
- **Windows에서 안 보이던 새 항목**: 플랫폼 고유 이슈 — 신규 등급 부여 후 처리 (예: `G-1` 등 새 섹션으로 문서 추가).
- **Windows에서 있었는데 여기선 없는 항목**: 타입 폭 차이 등으로 이 플랫폼에선 해당 없음 — 참고만 하고 무시.

### 6.3 우선순위가 높은 체크

타입 폭 의존적인 체크는 특히 주의 깊게 볼 것:
- `bugprone-narrowing-conversions` (B-1)
- `bugprone-implicit-widening-of-multiplication-result` (B-2)
- Cppcheck의 `portability` 카테고리 전체 (`--enable=portability`에 이미 포함됨)

---

## 7. 아직 SDK 설치가 필요한 플랫폼

Android/Telechips/Renesas 전부 설치 완료되어 5.3~5.5로 편입됨(환경변수만 세션마다 활성화). 남은 건 QNX 하나뿐:

### 7.1 QNX

`intro.md`에 QNX 관련 안내 자체가 없음 — 현재 실제 빌드/배포 워크플로우에 포함되지 않는 것으로 보임. SDP 라이선스/설치가 필요한 별도 사안이라 **우선순위 최하** (필요 시점에 별도 확인 권장).

---

## 8. 작업 순서 체크리스트

```
1단계 — WSL 도구 설치 (3장)
─────────────────────────────────────────────────────────────────
[ ] clang-tidy-21 설치 및 버전 확인
[ ] run-clang-tidy.py 다운로드
[ ] cppcheck 설치
[ ] emsdk 환경 활성화 확인

2단계 — 즉시 가능한 플랫폼 스캔 (5장) — Android/Telechips/Renesas 전부 설치 확인됨, env만 활성화하면 됨
─────────────────────────────────────────────────────────────────
[ ] linux-clang-release compile_commands.json 생성
[ ] linux-clang: Clang-Tidy 스캔 → clangtidy_linux-clang_v2.txt
[ ] linux-clang: Cppcheck 스캔 → cppcheck_linux-clang_v2.txt
[ ] linux-webgl-release compile_commands.json 생성
[ ] webgl: Clang-Tidy 스캔 → clangtidy_webgl_v2.txt
[ ] webgl: Cppcheck 스캔 → cppcheck_webgl_v2.txt
[ ] ANDROID_HOME export 후 linux-android-arm64-release compile_commands.json 생성
[ ] android-arm64: NDK clang-tidy 스캔 → clangtidy_android-arm64_v2.txt
[ ] android-arm64: Cppcheck 스캔 → cppcheck_android-arm64_v2.txt
[ ] android-arm(32비트, 타입 폭 차이 확인용 최우선): 5.3절 명령으로 compile_commands.json 생성 → clangtidy_android-arm_v2.txt / cppcheck_android-arm_v2.txt
[ ] (여유 되면) android-x64/android-x86: 5.3절 명령으로 동일 반복 → clangtidy_android-{x64,x86}_v2.txt / cppcheck_android-{x64,x86}_v2.txt
[ ] Telechips environment-setup source 후 linux-telechips-tcc803x-release compile_commands.json 생성
[ ] telechips: Cppcheck 스캔 → cppcheck_telechips-tcc803x_v2.txt (GCC 툴체인이라 Clang-Tidy 제외)
[ ] Renesas environment-setup source 후 linux-renesas-rcar_h3ulcb-release compile_commands.json 생성
[ ] renesas: Cppcheck 스캔 → cppcheck_renesas-rcar_h3ulcb_v2.txt (GCC 툴체인이라 Clang-Tidy 제외)

3단계 — 결과 분석 (6장)
─────────────────────────────────────────────────────────────────
[ ] base/ 유저 코드만 필터링
[ ] 기존 A~F 등급 문서와 대조, 신규 항목만 추출
[ ] 신규 항목 있으면 원인 분석 및 수정 (이번 A-9 WebGL 건과 동일한 방식)
[ ] 문서에 플랫폼별 결과 반영

4단계 — 남은 플랫폼 (7장)
─────────────────────────────────────────────────────────────────
[ ] QNX SDP 설치 여부/필요성 확인 (우선순위 낮음, intro.md에도 없음)
[ ] 설치 시 2~3단계 반복
```

---

## 9. 관련 문서

- `260706_황인성_clangtidy_cppcheck_verification_report.md` — Windows MSVC 기준 기존 검증 결과 (A~F 등급 전체)
- [06-clang-tidy-guide.md](06-clang-tidy-guide.md) — Clang-Tidy 옵션/사용법 상세 (Windows 기준, 대부분 Linux에도 적용됨)
- [07-cppcheck-guide.md](07-cppcheck-guide.md) — Cppcheck 옵션/사용법 상세 (Windows 기준, 대부분 Linux에도 적용됨)
- `C:\private\grapi-base\intro.md` — 플랫폼별 SDK 설치/빌드 가이드 원본(Android NDK 버전, Emscripten, Renesas/Telechips 툴체인 설치 스크립트 출처). 이 문서의 3장/5.3/5.4/7장 내용의 근거
