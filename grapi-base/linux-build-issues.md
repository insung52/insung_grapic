# GrapiBase Linux(WSL Ubuntu) 빌드 이슈 정리

## Desktop 빌드 (`./build.sh release`)

### 1. Filament 백엔드 테스트 컴파일 실패 (Linux + Clang)

**증상**
```
test_MipLevels.cpp:175:44: error: use of undeclared identifier 'descriptorSetLayout';
did you mean 'Shader::getDescriptorSetLayout'?
```

**원인**
- `external/filament`은 Google 공식 repo가 아니라 사내 미러(`code.grapicar.com/engine-dev/core/filament.git`)로, Google 공식 태그(v1.67.0 등)를 주기적으로 머지해서 받아옴 — 버전 자체는 최신.
- Filament가 Vulkan 백엔드를 디스크립터 셋 방식으로 리팩토링하는 중인데, `test_MipLevels.cpp` 테스트 코드 일부가 덜 고쳐진 채 남아 있음.
- 이 깨진 테스트(`backend_test_linux`)는 `filament/filament/backend/CMakeLists.txt`에서
  ```cmake
  if (LINUX AND CMAKE_CXX_COMPILER_ID MATCHES "Clang")
      add_executable(backend_test_linux test/linux_runner.cpp ${BACKEND_TEST_SRC})
  ```
  로 **Linux + Clang 조합에서만 빌드되도록** 조건이 걸려 있어, Windows(MSVC)에서는 한 번도 빌드된 적이 없어 드러나지 않았음.

**해결**: `external/CMakeLists.txt`의 `FILAMENT_SUPPORTS_VULKAN` 설정 블록 바로 아래에 추가.
```cmake
set(FILAMENT_BUILD_TESTING
    OFF
    CACHE BOOL "" FORCE)
```
캐시에 이미 ON으로 박혀있을 수 있으므로 `./build.sh -f release`로 강제 재설정.

(Windows 쪽은 해당 테스트가 빌드되지 않으므로 이 수정이 필요 없어 되돌림. Linux 전용 이슈.)

---

## Android 빌드 (`./build.sh -p android release`)

### 2. cmake 버전 체크 스크립트 버그

**증상**
```
Error: cmake version 3.19+ is required, 4.2 installed, exiting
```
설치된 cmake는 4.2로 요구 버전(3.19)보다 훨씬 최신인데도 에러 발생.

**원인**: `build.sh`의 버전 비교 로직 버그.
```bash
if [[ "${BASH_REMATCH[1]}" -lt "${CMAKE_MAJOR}" ]] || \
   [[ "${BASH_REMATCH[2]}" -lt "${CMAKE_MINOR}" ]]; then
```
"major < 3 이거나 minor < 19면 에러"로 되어 있어서, major 버전이 3보다 큰 경우(4.2처럼)는 고려하지 않고 minor(2) < 19만 보고 거짓으로 에러를 냄.

**해결**: `build.sh`에서 해당 조건을 아래로 수정 (major 버전이 더 높으면 통과하도록).
```bash
if [[ "${BASH_REMATCH[1]}" -lt "${CMAKE_MAJOR}" ]] || \
   { [[ "${BASH_REMATCH[1]}" -eq "${CMAKE_MAJOR}" ]] && \
     [[ "${BASH_REMATCH[2]}" -lt "${CMAKE_MINOR}" ]]; }; then
```
Windows 쪽엔 이 체크 함수(Android 빌드 전용 검증)가 호출되지 않아 영향 없음. WSL `~/grapi-base/build.sh`에 직접 수정 필요.

### 3. Lua `tmpnam` deprecated 경고 (무해)

**증상**
```
loslib.c:172:3: warning: 'tmpnam' is deprecated: tmpnam is unsafe, use mkstemp or tmpfile instead
```
Android NDK 툴체인이 `tmpnam()` 사용을 경고로 표시. Lua의 `os.tmpname` 구현이 오래된 방식을 쓰고 있어서 발생하는 경고일 뿐, **빌드를 막지 않는 단순 경고**라 무시해도 됨.

### 샘플 관련 참고사항

안드로이드 빌드에도 desktop과 동일하게 `GRAPI_SKIP_SAMPLES=ON`이 기본 적용되어 `samples/`의 데모들은 컴파일되지 않음. 설령 켜더라도 Android에서는 `add_demo()`가 실행파일이 아닌 `.so` 공유 라이브러리를 만들기 때문에, 폰에서 바로 열어볼 수 있는 형태가 아님 — 이를 패키징할 Gradle/Android Studio 앱 프로젝트가 별도로 필요함 (현재 저장소엔 `android/xeniagear-android-jni`라는 JNI 브릿지 코드만 있고 앱 프로젝트는 없음).

---

## 요약 체크리스트 (다음에 같은 문제 만나면)

| 증상 | 원인 | 해결 |
|---|---|---|
| Linux Clang에서만 컴파일 에러 | Filament 자체 테스트 코드 버그 (Linux+Clang 조건부 빌드) | `FILAMENT_BUILD_TESTING OFF` 캐시 강제 설정 |
| Android 빌드 시 "cmake 3.19+ required" 오류 (최신 cmake인데도) | `build.sh` 버전 비교 로직 버그 (major 버전 역전 미고려) | `build.sh`의 비교 조건문 수정 |
| Lua `tmpnam` deprecated 경고 | NDK 툴체인의 경고, 빌드엔 무해 | 무시 가능 |
