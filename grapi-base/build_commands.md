# grapi-base 빌드 명령어 참고

## Windows (MSVC x64)

> `build.bat`은 샘플을 기본으로 스킵하므로 샘플 포함 빌드는 cmake 직접 사용.  
> **cmd** 또는 **PowerShell**에서 `C:\working\grapi-base` 기준으로 실행.

```bat
:: 샘플 포함 (cmake 직접)
cmake --preset windows-msvc-x64-release
cmake --build out\build\windows-msvc-x64-release -j 16

:: 샘플 제외 (build.bat)
build.bat release

:: CMake 강제 재실행 (CMakeLists.txt 변경 시)
build.bat -f release
```

**클린 빌드**
```bat
:: 전체 out/ 삭제 후 빌드
build.bat -c release

:: 특정 플랫폼만 클린 (전체 삭제 없이)
rd /s /q out\build\windows-msvc-x64-release
cmake --preset windows-msvc-x64-release
cmake --build out\build\windows-msvc-x64-release -j 16
```

---

## Linux Desktop (Clang)

> WSL Ubuntu 기준. `~/grapi-base`에서 실행.

```bash
# 샘플 포함 (cmake 직접)
cmake --preset linux-clang-release
cmake --build out/build/linux-clang-release -j $(nproc)

# 샘플 제외 (build.sh)
./build.sh -p desktop release

# CMake 강제 재실행
./build.sh -p desktop -f release
```

**클린 빌드**
```bash
# 전체 out/ 삭제 후 빌드
./build.sh -c -p desktop release

# 특정 플랫폼만 클린 (전체 삭제 없이)
rm -rf out/build/linux-clang-release
cmake --preset linux-clang-release
cmake --build out/build/linux-clang-release -j $(nproc)
```

---

## Android

> WSL Ubuntu 기준. `ANDROID_HOME` 환경변수 필요.  
> Android는 샘플이 `.so` 라이브러리 형태로 빌드됨 (실행 바이너리 없음).

```bash
# 전체 ABI (arm64 / arm / x64 / x86)
./build.sh -p android release

# CMake 강제 재실행
./build.sh -p android -f release

# 환경변수 미설정 시
export ANDROID_HOME=~/Android/android_sdk
./build.sh -p android release
```

**클린 빌드**
```bash
# 전체 out/ 삭제 후 빌드
./build.sh -c -p android release

# ABI별 개별 클린
rm -rf out/build/linux-android-arm64-release
rm -rf out/build/linux-android-arm-release
rm -rf out/build/linux-android-x64-release
rm -rf out/build/linux-android-x86-release
./build.sh -p android release
```

빌드 결과물:
```
out/build/linux-android-arm64-release/samples/lib*.so
out/build/linux-android-arm-release/samples/lib*.so
out/build/linux-android-x64-release/samples/lib*.so
out/build/linux-android-x86-release/samples/lib*.so
```

---

## WebGL (Emscripten)

> WSL Ubuntu 기준. Telechips SDK를 source한 터미널과 **분리된 새 터미널**에서 실행.  
> `EMSDK` 환경변수 필요.

```bash
# emsdk 환경 설정 (터미널 새로 열었을 때)
source ~/emsdk/emsdk_env.sh

# 빌드
./build.sh -p webgl release

# CMake 강제 재실행
./build.sh -p webgl -f release
```

**클린 빌드**
```bash
# 전체 out/ 삭제 후 빌드
./build.sh -c -p webgl release

# WebGL만 클린
rm -rf out/build/linux-webgl-release
./build.sh -p webgl release
```

빌드 결과물 확인:
```bash
ls out/build/linux-webgl-release/web/
```

브라우저 테스트 (결과물 디렉토리에서):
```bash
python3 -m http.server 8000
# → 브라우저에서 http://localhost:8000 접속
```

---

## Embedded (Telechips TCC803x)

> WSL Ubuntu 기준. Yocto SDK 환경 설정 필요.  
> 샘플 실행 바이너리는 빌드되지 않음 (`.so`만 생성).

```bash
# SDK 환경 설정 (터미널 새로 열었을 때)
source /opt/poky-telechips-systemd/nodistro.0/environment-setup-aarch64-telechips-linux

# SDK cmake 충돌 방지 (최초 1회)
# mv /opt/poky-telechips-systemd/.../cmake /opt/.../cmake.bak

# 빌드
./build.sh -p embedded release
# → 보드 선택 메뉴에서 tcc803x 선택

# CMake 강제 재실행
./build.sh -p embedded -f release
```

**클린 빌드**
```bash
# 전체 out/ 삭제 후 빌드
./build.sh -c -p embedded release

# Embedded만 클린
rm -rf out/build/linux-telechips-tcc803x-release
./build.sh -p embedded release
```

빌드 결과물:
```
out/build/linux-telechips-tcc803x-release/*.so
```

---

## 주의사항

| 항목 | 내용 |
|------|------|
| WebGL + Embedded | 같은 터미널에서 실행 금지. SDK 환경이 Python 경로를 오염시켜 emcc 실패 |
| CMake 강제 재실행 | CMakeLists.txt 또는 CMakePresets.json 수정 시 `-f` 플래그 필요 |
| Android NDK | `~/Android/android_sdk/ndk/` 아래 버전 확인 (`build/android/ndk.version` 참조) |
| Windows 샘플 빌드 | `build.bat`은 항상 샘플 스킵 → cmake 직접 사용 필요 |
