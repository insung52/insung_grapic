# v1.72.0 머지 충돌 해결 가이드

## 전체 충돌 목록 및 분류

### Group A — CMakeLists.txt (12개 파일, 단순 패턴)
**패턴**: `WEBGL` → `WASM` 이름 변경 + 회사가 추가한 `QNX` 조건 유지
**해결 방법**: v1.72.0 코드 채택, `QNX` 관련 조건은 HEAD에서 복원

| 파일 | 상태 |
|---|---|
| `CMakeLists.txt` (6개 블록) | 진행 중 |
| `filament/backend/CMakeLists.txt` | 대기 |
| `filament/test/CMakeLists.txt` | 대기 |
| `libs/camutils/CMakeLists.txt` | 대기 |
| `libs/filameshio/CMakeLists.txt` | 대기 |
| `libs/geometry/CMakeLists.txt` | 대기 |
| `libs/image/CMakeLists.txt` | 대기 |
| `libs/imagediff/CMakeLists.txt` | 대기 |
| `libs/imageio-lite/CMakeLists.txt` | 대기 |
| `libs/ktxreader/CMakeLists.txt` | 대기 |
| `libs/viewer/CMakeLists.txt` | 대기 |
| `tools/filamesh/CMakeLists.txt` | 대기 |

---

### Group B — v1.72.0 채택 (간단)
**패턴**: 주석 변경, 로직 정리, 구조 리팩토링. 회사 커스텀 없음.

| 파일 | 변경 내용 | 상태 |
|---|---|---|
| `libs/filamat/src/GLSLPostProcessor.cpp` | 주석 문구 변경 + 빈 줄 제거 | 대기 |
| `filament/backend/src/opengl/platforms/PlatformEGL.cpp` | `assert_invariant` 위치 정리 | 대기 |
| `libs/gltfio/src/FilamentAsset.cpp` | `textureIndex` → `gltfTextureIndex/assetTextureIndex` 리팩토링 | 대기 |
| `filament/src/details/Scene.cpp` (2블록) | `TANGENT/LIGHT_INSTANCE` → `SPOT_PARAMS/LIGHT_ENTITY` 데이터 구조 변경 | 대기 |
| `filament/test/filament_test.cpp` | 테스트 데이터 새 구조 반영 | 대기 |

---

### Group C — QNX 패치 보존 + v1.72.0 API 변경 병합
**패턴**: v1.72.0이 API를 바꿨지만 회사의 QNX 워크어라운드도 유지해야 함

| 파일 | 변경 내용 | 상태 |
|---|---|---|
| `filament/backend/src/opengl/OpenGLContext.h` (2블록) | 네임스페이스 `filament`→`filament::backend` + QNX 조건부 함수 선언 유지 | 대기 |
| `filament/src/PostProcessManager.cpp` (3블록) | API 변경(`getMaterial` 시그니처) + QNX designated initializer 워크어라운드 유지 | 대기 |
| `filament/src/ShadowMapManager.cpp` | v1.72.0이 blur 블록 구조 변경, QNX 워크어라운드 포함된 블록 제거됨 | 대기 |

---

### Group D — 회사 추가 코드 + v1.72.0 리팩토링 병합
| 파일 | 변경 내용 | 상태 |
|---|---|---|
| `filament/backend/src/vulkan/VulkanDriver.cpp` | 회사 추가 COMPUTE API 함수 보존 + v1.72.0의 `draw2`→`prepareDraw` 변경 적용 | 대기 |

---

### Group E — GitHub Actions (비중요)
| 파일 | 변경 내용 | 상태 |
|---|---|---|
| `.github/workflows/presubmit.yml` | CI 설정 (빌드에 영향 없음) | 대기 |

---

## 진행 기록

### 완료 항목
- (없음)

### 현재 작업
- Group A CMakeLists.txt 해결 중
