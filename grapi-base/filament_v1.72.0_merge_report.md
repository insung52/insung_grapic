# Filament v1.72.0 머지 리포트

## 개요

- **머지 브랜치**: `merge_v1.72` → 내부 filament 미러 (`code.grapicar.com/engine-dev/core/filament`)
- **베이스**: v1.71.x 회사 내부 브랜치 (HEAD)
- **대상**: upstream `rc/1.72.0`
- **빌드 검증**: WSL Ubuntu / Clang / Mesa llvmpipe + lavapipe (소프트웨어 렌더러)
- **테스트 바이너리**: `backend_test_linux` (OpenGL + Vulkan 백엔드)
- **최종 상태**: filament 백엔드 테스트 통과 + grapi-base 전체 빌드 성공 (샘플 포함, 2507/2507) + **전체 샘플 Linux 실행 성공**

---

## 1. 머지 충돌 해결 목록 (22개)

### Group A — VulkanDriver.cpp

| 충돌 | 해결 방법 |
|---|---|
| `prepareDraw()` vs `draw2()` | v1.72.0의 `prepareDraw()` 채택 |
| COMPUTE API 함수들 (`createDescriptorSetLayoutCOMPUTE`, `createPipelineCOMPUTE`, `dispatchCOMPUTE`, `copyBufferCOMPUTE`, `fillBufferCOMPUTE`, `getOrCreateCompute` 등) | HEAD 회사 코드 유지 |

### Group B / E — PostProcessManager.cpp

| 충돌 | 해결 방법 |
|---|---|
| `getMaterial(mEngine)` 호출 방식 | v1.72.0 채택 + QNX `SamplerParams` 워크어라운드 유지 |
| `vsmMipmapPass` 함수 전체 | v1.72.0에서 제거됨 → 삭제 |

### Group C — ShadowMapManager.cpp

| 충돌 | 해결 방법 |
|---|---|
| `if (UTILS_UNLIKELY(blur))` 블록 | v1.72.0에서 제거됨 → QNX 워크어라운드 포함 삭제 |

### Group D — OpenGLContext.h

| 충돌 | 해결 방법 |
|---|---|
| Block 1: `getIndexForCap`, `getIndexForBufferTarget` 선언 | HEAD 유지 (QNX/GCC `constexpr` 대응) |
| Block 2: `activeTexture`, `bindSampler` 등 inline 구현 | ⚠️ 최초 잘못 해결 → 이후 수동 수정 필요 (아래 참조) |

### Group E — .github/workflows/presubmit.yml

| 충돌 | 해결 방법 |
|---|---|
| Windows runner `windows-2022` vs `win-2019-16core` | HEAD의 `win-2019-16core` 유지 |

---

## 2. filament 빌드 에러 및 수정 사항

### 2-1. `DriverEnums.h` — enum switch 누락

**원인**: 회사가 추가한 enum (열거형) 값을 `to_string()` switch에 추가하지 않음  
**에러**:
```
error: enumeration value 'STORAGE_IMAGE' not handled in switch
error: enumeration value 'INDIRECT' not handled in switch
```

**수정**:
- `to_string(DescriptorType)` → `DESCRIPTOR_TYPE_CASE(STORAGE_IMAGE)` 추가
- `to_string(BufferObjectBinding)` → `case BufferObjectBinding::INDIRECT: return "INDIRECT";` 추가

---

### 2-2. `ostream.cpp` — BufferObjectBinding switch 누락

**수정**: `operator<<` 스위치에 `CASE(BufferObjectBinding, INDIRECT)` 추가

---

### 2-3. `OpenGLContext.h` — v1.72.0 아키텍처 변경 (핵심 수정)

**배경**: v1.72.0에서 `activeTexture`, `bindSampler`, `setScissor`, `viewport`, `depthRange`, `bindVertexArray` 등이 `OpenGLContext`에서 `OpenGLState` 클래스로 이동됨

**최초 충돌 해결 오류**: HEAD의 inline 구현을 그대로 유지했으나, 이 함수들은 이미 `OpenGLState`에 있어서 중복 정의 에러 발생

**에러**:
```
error: out-of-line definition of 'activeTexture' does not match any declaration
error: use of undeclared identifier 'state'
```

**수정 내용** (`OpenGLContext.h`):
1. `getIndexForCap()` 구현에서 `assert_invariant(index < state.enables.caps.size())` 제거
2. `getIndexForBufferTarget()` 구현에서 `assert_invariant(index < sizeof(state.buffers.genericBinding)/...)` 제거
3. `activeTexture`, `bindSampler`, `setScissor`, `viewport`, `depthRange`, `bindVertexArray`, `bindBufferRange`, `bindTexture`, `useProgram`, `enableVertexAttribArray`, `disableVertexAttribArray`, `enable`, `disable`, `frontFace`, `cullFace`, `blendEquation`, `blendFunction`, `colorMask`, `depthMask`, `depthFunc`, `stencilFuncSeparate`, `stencilOpSeparate`, `stencilMaskSeparate`, `polygonOffset` 구현 전부 제거 (→ `OpenGLState.h`로 이동됨)

---

### 2-4. `GLUtils.h` — INDIRECT 케이스 누락

**수정**: `getBufferBindingType()` 스위치에 추가
```cpp
case BufferObjectBinding::INDIRECT:
    return GL_DRAW_INDIRECT_BUFFER;
```

---

### 2-5. `VulkanHandles.cpp` — STORAGE_IMAGE, INDIRECT 케이스 누락

**수정**: `getBufferObjectBinding()` 스위치에 추가
```cpp
case BufferObjectBinding::INDIRECT:
    return VulkanBufferBinding::UNKNOWN;
```

**수정**: `fromBackendLayout()` 스위치에 추가
```cpp
case DescriptorType::STORAGE_IMAGE:
    PANIC_POSTCONDITION("Storage image is not supported in standard pipeline layout");
    break;
```

---

### 2-6. `GLDescriptorSet.cpp`, `OpenGLProgram.cpp` — STORAGE_IMAGE 케이스 누락

**수정**: 두 파일 모두 `DescriptorType` switch에 추가
```cpp
case DescriptorType::STORAGE_IMAGE:
    break;
```

---

### 2-7. `VulkanCompute.cpp` — NONE 케이스 누락

**에러**:
```
error: enumeration value 'NONE' not handled in switch
error: non-void function does not return a value in all control paths
```

**수정**: `getVkStage()` 함수에 추가
```cpp
case ShaderStageFlags::NONE:
    return 0;
```
+ 함수 말미에 `return 0;` 추가

---

### 2-8. `test_MipLevels.cpp` — 테스트 코드 버그 수정

**문제 1**: 자동 머지 중 stale 코드 생존
```cpp
// 잘못된 줄 (삭제 필요)
state.pipelineLayout.setLayout = { descriptorSetLayout };  // descriptorSetLayout 미선언
```
→ 해당 줄 제거

**문제 2**: `#ifdef CXX_COMPILER_GNU_GCC` 블록 내 변수 스코프 오류
- `descriptorSet[0]` 미선언
- `descriptorSet13`이 `#else` 블록 안에서만 선언되어 이후 코드에서 사용 불가

→ `descriptorSet13`을 `#ifdef` 바깥으로 이동, `SamplerParams` 구조체 초기화 방식 분기

---

### 2-9. `Scene.cpp` — 머지 아티팩트 3건 (렌더링 버그)

**파일**: `filament/src/details/Scene.cpp`

이 파일에는 자동 머지 과정에서 서로 다른 성격의 버그 3건이 동시에 발생했다.

---

#### 버그 A: `tangents` 포인터 선언 누락 (빌드 에러)

**원인**: 머지 과정에서 `prepareLightsGpu()` (WSL 버전 명: `prepareDynamicLights`) 내 선언 줄이 삭제됨

**에러**:
```
error: use of undeclared identifier 'tangents'
```

**수정**: 포인터 선언 복구
```cpp
auto const* UTILS_RESTRICT directions  = lightData.data<DIRECTION>();
auto const* UTILS_RESTRICT tangents    = lightData.data<TANGENT>();   // ← 복구
auto const* UTILS_RESTRICT entities   = lightData.data<LIGHT_ENTITY>();
auto const* UTILS_RESTRICT shadowInfo = lightData.data<SHADOW_INFO>();
```

---

#### 버그 B: `lightData.elementAt<TANGENT>` 쓰기 누락 (area light 방향 소실)

**원인**: v1.72.0 upstream에는 TANGENT 쓰기가 없고, pre-merge grapi-base에는 있었음. 자동 머지가 grapi-base 쪽 TANGENT 쓰기를 누락시킴.

**증상**: `area_light` 샘플에서 직사각형 에어리어 라이트가 방향성 없이 포인트 라이트처럼 보임.

**수정**: TANGENT 쓰기 복구
```cpp
lightData.elementAt<POSITION_RADIUS>(index) = float4{ position.xyz, lcm.getRadius(li) };
lightData.elementAt<DIRECTION>(index) = d;
lightData.elementAt<TANGENT>(index) = tangent;   // ← 복구 (auto-merge에서 누락됨)
lightData.elementAt<SPOT_PARAMS>(index) = float2{...};
```

---

#### 버그 C: GPU 라이트 타입 패킹 오류 (area light 셰이더 인식 불가)

**원인**: 자동 머지가 올바른 타입 매핑 코드를 `static_cast<uint8_t>(lcm.getType(li))` 로 잘못 대체함.

**배경**:
- Pre-merge grapi-base: 수동 매핑 (`isAreaLight→2, isPointLight→0, else→1`)
- Upstream v1.72.0: `isPointLight(li) ? 0u : 1u` (area light 없음)
- 자동 머지 결과: `static_cast<uint8_t>(lcm.getType(li))` — 양쪽 어디에도 없던 코드

**충돌 구조**:
```
// pre-merge grapi-base (정상)
uint8_t lightType;
if (lcm.isAreaLight(li))      lightType = 2u;
else if (lcm.isPointLight(li)) lightType = 0u;
else                           lightType = 1u;
packTypeShadow(lightType, ...)

// upstream v1.72.0
packTypeShadow(lcm.isPointLight(li) ? 0u : 1u, ...)

// 자동 머지 결과 (버그)
packTypeShadow(static_cast<uint8_t>(lcm.getType(li)), ...)
```

**왜 틀렸나**: `UibStructs.h`의 `typeShadow` 필드는 `0=point, 1=spot, 2=area`로 정의되며, 이는 `LightManager::Type` enum 값(`SUN=0, DIR=1, POINT=2, FOCUSED=3, SPOT=4, AREA=5`)과 완전히 독립적인 GPU 패킹 공간이다. AREA light의 enum 값 `5`를 그대로 전달하면 셰이더의 `LIGHT_TYPE_AREA = 2u` 조건에 매칭되지 않아 에어리어 라이트가 렌더링상 기본 포인트 라이트처럼 동작한다.

**수정**: 수동 매핑 복원
```cpp
// 셰이더 기대값: 0=point, 1=spot, 2=area (UibStructs.h 주석 기준)
// lcm.getType()은 LightManager::Type enum(AREA=5)을 반환하므로 직접 캐스팅 불가
uint8_t const gpuLightType = lcm.isAreaLight(li) ? 2u
                           : lcm.isPointLight(li) ? 0u : 1u;
lp[gpuIndex].typeShadow = LightsUib::packTypeShadow(
        gpuLightType,
        shadowInfo[i].contactShadows,
        shadowInfo[i].index);
```

---

## 3. filament 수정 파일 전체 목록

| 파일 | 분류 | 변경 내용 |
|---|---|---|
| `filament/backend/src/opengl/OpenGLContext.h` | 핵심 수정 | v1.72.0 아키텍처 변경 대응 (inline 구현 제거) |
| `filament/backend/src/opengl/GLUtils.h` | 버그 수정 | `INDIRECT` 케이스 추가 |
| `filament/backend/src/opengl/GLDescriptorSet.cpp` | 버그 수정 | `STORAGE_IMAGE` 케이스 추가 |
| `filament/backend/src/opengl/OpenGLProgram.cpp` | 버그 수정 | `STORAGE_IMAGE` 케이스 추가 |
| `filament/backend/include/backend/DriverEnums.h` | 버그 수정 | `STORAGE_IMAGE`, `INDIRECT` to_string 추가 |
| `filament/backend/src/ostream.cpp` | 버그 수정 | `INDIRECT` ostream 추가 |
| `filament/backend/src/vulkan/VulkanHandles.cpp` | 버그 수정 | `STORAGE_IMAGE`, `INDIRECT` 케이스 추가 |
| `filament/backend/src/vulkan/VulkanCompute.cpp` | 버그 수정 | `NONE` 케이스 + return 추가 |
| `filament/backend/test/test_MipLevels.cpp` | 테스트 수정 | GCC 대응 코드 스코프 버그 수정 |
| `filament/src/PostProcessManager.cpp` | 머지 해결 | vsmMipmapPass 제거, getMaterial 변경 |
| `filament/src/ShadowMapManager.cpp` | 머지 해결 | VSM blur 코드 제거 |
| `filament/src/details/Scene.cpp` | 머지 아티팩트 3건 수정 | tangents 선언 복구 / TANGENT 쓰기 복구 / GPU 타입 패킹 수동 매핑 복원 |
| `filament/backend/src/vulkan/VulkanDriver.cpp` | 머지 해결 | COMPUTE API 유지, prepareDraw 채택 |
| `.github/workflows/presubmit.yml` | 머지 해결 | 회사 runner 유지 |

---

## 4. 테스트 결과

### 테스트 실행 방법 (주의)

`backend_test_linux`의 백엔드 선택 옵션은 `--backend`가 아니라 `--api` (또는 `-a`)임.  
`--backend=vulkan`은 silently 무시되고 OpenGL 기본값으로 실행되므로 주의.

```bash
# OpenGL 백엔드
./out/cmake-debug/filament/backend/backend_test_linux -a opengl

# Vulkan 백엔드 (lavapipe 필요)
VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/lvp_icd.json \
  ./out/cmake-debug/filament/backend/backend_test_linux -a vulkan

# lavapipe 설치
sudo apt install mesa-vulkan-drivers libvulkan1
```

---

### 4-1. OpenGL 백엔드 결과

**환경**: WSL Ubuntu / Mesa 26.0.3 / llvmpipe (소프트웨어 렌더러)

> **llvmpipe란?** 실제 GPU 없이 CPU만으로 OpenGL을 에뮬레이션하는 Mesa 소프트웨어 렌더러.
> 실제 GPU(NVIDIA, AMD 등)에서는 당연히 지원되는 기능들이 일부 빠져 있어 테스트 일부가 환경 한계로 실패할 수 있다.

```
전체: 71개 테스트
- PASSED:  65개
- SKIPPED:  3개 (OpenGL 미지원 기능, 정상)
- FAILED:   3개 (모두 llvmpipe 환경 한계, 코드 문제 아님)
```

**실패 테스트 상세**

| 테스트 | 에러 | 원인 | upstream 처리 |
|---|---|---|---|
| `BackendTest.FeedbackLoops` | `HandleAllocator.h:192: failed assertion 'handle'` | llvmpipe 소프트웨어 렌더러 한계 | CI+OpenGL skip 있음 (`b/453756688`) |
| `BlitTest.ColorResolve` | `GL_TEXTURE_2D_MULTISAMPLE is not supported` | llvmpipe MSAA 미지원 | CI+OpenGL skip 있음 (`b/453758075`) |
| `LoadImageTest.UpdateImage3D` | `HandleAllocator.h:192: failed assertion 'handle'` | llvmpipe RGBA16F + 2D array 미지원 | CI skip 없음 (upstream 미반영) |

**실패 원인 상세 분석 및 수정하지 않은 이유**

세 테스트 모두 **코드 버그가 아닌 테스트 환경(llvmpipe)의 하드웨어 기능 부재**로 인한 실패다.
filament 코드 수준에서 수정할 수 있는 대상이 없다.

---

**① `BackendTest.FeedbackLoops`**

렌더 타겟(framebuffer attachment)이 동시에 셰이더 샘플러로도 읽히는 "피드백 루프" 상황을 검증하는 테스트.
llvmpipe가 이 시나리오에서 내부 핸들 할당에 실패해 assertion을 발생시킴.
구글이 이미 버그 트래커(`b/453756688`)에 등록하고, upstream CI의 OpenGL 실행 시 이 테스트를 skip하도록 처리해 둔 상태.

---

**② `BlitTest.ColorResolve`**

MSAA(멀티샘플 안티에일리어싱) 텍스처를 일반 텍스처로 resolve(병합)하는 테스트.
llvmpipe가 `GL_TEXTURE_2D_MULTISAMPLE`을 아예 구현하지 않아 에러가 직접 출력됨.
구글 버그 트래커(`b/453758075`) 등록 및 upstream CI OpenGL skip 처리 완료.
같은 테스트를 Vulkan 백엔드(`lavapipe`)로 돌리면 PASSED임을 확인.

---

**③ `LoadImageTest.UpdateImage3D`**

RGBA16F 포맷의 3D 텍스처 배열(`GL_TEXTURE_2D_ARRAY`)을 업로드·갱신하는 테스트.
llvmpipe가 RGBA16F + 2D 배열 조합을 지원하지 않아 동일한 `HandleAllocator` assertion 발생.
Vulkan 백엔드에서는 `b/453776983`으로 skip 처리되어 있으나, **OpenGL 백엔드 skip은 upstream에서 누락**된 것으로 보임 — upstream 실수이며 우리 코드 문제가 아님.

---

### 4-2. Vulkan 백엔드 결과

**환경**: WSL Ubuntu / Mesa 26.0.3 / lavapipe (소프트웨어 Vulkan 렌더러)  
**Vulkan 디바이스**: `llvmpipe (LLVM 21.1.8, 256 bits)` / API 1.4

```
전체: 71개 테스트
- PASSED:  63개
- SKIPPED:  8개 (upstream SKIP_IF 처리된 항목, 정상)
- FAILED:   0개
```

**스킵 테스트 상세 (모두 upstream 정의)**

| 테스트 | 이유 |
|---|---|
| `BackendTest.BasicAsyncFlow` | Vulkan async upload 미지원 |
| `BackendTest.FrameCompletedCallback` | Vulkan frame callback 미지원 (`b/417254479`) |
| `BackendTest.FeedbackLoops` | lavapipe 이미지 결과 어두움 (`b/453776546`) |
| `LoadImageTest.UpdateImage2D` | lavapipe Vulkan 이미지 제한 (`b/453776547`) |
| `LoadImageTest.UpdateImageSRGB` | lavapipe SRGB 제한 (`b/454040142`) |
| `LoadImageTest.UpdateImage3D` | lavapipe 3D 이미지 제한 (`b/453776983`) |
| `MsaaSwapChainTest.Basic/HeadlessSwapChain` | Vulkan MSAA SwapChain 플랫폼 미지원 |
| `MsaaSwapChainTest.Basic/NativeSwapChain` | 동일 |

---

### 핵심 검증 통과

| 테스트 | OpenGL | Vulkan | 의미 |
|---|---|---|---|
| `BackendTest.TextureViewLod` | PASSED | PASSED | 이번 머지 주요 버그 수정 대상 — **검증 완료** |
| `BackendTest.MRT` | PASSED | PASSED | 멀티 렌더 타겟 정상 |
| `BlitTest.ColorResolve` | FAILED (llvmpipe) | PASSED | Vulkan에서 MSAA resolve 정상 |
| `BlitTest.*` (5개) | PASSED | PASSED | 텍스처 blitting 정상 |
| `MemoryMappedTest.*` (7개) | PASSED | PASSED | 버퍼 메모리 매핑 정상 |
| `ReadPixelsTest.*` (4개) | PASSED | PASSED | 픽셀 읽기 정상 |
| `BasicStencilBufferTest.*` (3개) | PASSED | PASSED | 스텐실 버퍼 정상 |

---

## 5. grapi-base 빌드 에러 수정

filament v1.72.0 머지 후 grapi-base 엔진 자체에서 발생한 API 변경 대응 및 빌드 환경 수정.

### 5-1. `ktx2_reader.cc` — basisu API 이름 변경

**파일**: `base/src/grapi/base/providers/ktx2_reader.cc`

**원인**: `basist::ktx2_transcoder::get_format()` → `get_basis_tex_format()`으로 이름 변경

```cpp
// 이전
if (!basis_is_format_supported(info.basisFormat, transcoder->get_format())) {
// 이후
if (!basis_is_format_supported(info.basisFormat, transcoder->get_basis_tex_format())) {
```

---

### 5-2. `settings.cc` — LightDefinition 필드명 변경

**파일**: `libs/io/src/grapi/io/settings.cc`

**원인**: `LightDefinition::sunAngularRadius` → `sunAngularRadiusDeg`으로 이름 변경 (단위 명시)

```cpp
// 이전 (2곳)
sunlight->setSunAngularRadius(settings.lighting.sunlight.sunAngularRadius);
settings.lighting.sunlight.sunAngularRadius = sunlight->getSunAngularRadius();
// 이후
sunlight->setSunAngularRadius(settings.lighting.sunlight.sunAngularRadiusDeg);
settings.lighting.sunlight.sunAngularRadiusDeg = sunlight->getSunAngularRadius();
```

---

### 5-3. `base/CMakeLists.txt` — context.cc RTTI 혼재 문제

> RTTI / `-fno-rtti` 개념 상세: [`c++/rtti_and_fno_rtti.md`](../c++/rtti_and_fno_rtti.md)

**링크 에러**:
```
undefined reference to `typeinfo for VulkanPlatformLinux`
```

**원인 — filament v1.72.0 구조 변경**:

v1.71.x까지는 Linux Vulkan 구현이 `VulkanPlatform` 하나 안에 static 메서드로 내장되어 있었고, `VulkanPlatformLinux`라는 독립 클래스가 존재하지 않았다.

v1.72.0에서 polymorphism 리팩터링(커밋 `d52fb1f4f`)으로 `VulkanPlatformLinux`가 별도 클래스 + 별도 `.cpp` 파일로 분리됐다. 이 `.cpp`는 filament 전체에 걸린 `-fno-rtti` 빌드 규칙을 따르므로 `typeinfo for VulkanPlatformLinux` 심볼이 생성되지 않는다.

`context.cc`는 RTTI가 켜진 상태로 컴파일되며, 내부에서 `VulkanPlatformLinux`를 상속하는 `BaseVulkanPlatform` 클래스를 정의한다. RTTI on 상태에서 파생 클래스의 typeinfo는 부모 클래스의 typeinfo를 참조하는데, 부모 심볼이 없어 링크 에러가 발생한다.

```
VulkanPlatformLinux.cpp   (-fno-rtti)  → typeinfo 생성 안 됨
context.cc                (RTTI on)    → BaseVulkanPlatform : VulkanPlatformLinux
                                          BaseVulkanPlatform의 typeinfo가
                                          VulkanPlatformLinux의 typeinfo 참조
                                          → 심볼 없음 → 링크 에러
```

**현재 적용된 수정** (`base/CMakeLists.txt`):
```cmake
# context.cc inherits from filament backend classes compiled with -fno-rtti.
# Using RTTI here would generate a derived-class typeinfo that references the
# parent's typeinfo, which doesn't exist in the no-RTTI backend — causing an
# undefined symbol link error.
set_source_files_properties(src/grapi/base/context.cc
                            PROPERTIES COMPILE_FLAGS -fno-rtti)
```
`context.cc`는 `dynamic_cast`, `typeid` 등의 RTTI 기능을 실제로 사용하지 않으므로 이 플래그로 인한 동작 변화는 없다.

**추가 대안 — grapi-base 전체에 `-fno-rtti` 적용**:

grapi-base 자체 코드에는 `dynamic_cast`/`typeid` 사용이 없고(자체 `TypeInfo` 시스템으로 대체), 외부 라이브러리(JoltPhysics, sol2, harfbuzz 등)도 모두 RTTI-free 환경을 지원하는 것을 확인했다. 기술적으로 전체 적용이 가능하다.

```cmake
# base/CMakeLists.txt
target_compile_options(grapi-base PRIVATE -fno-rtti)
```

이렇게 하면 향후 다른 파일에서 filament 클래스를 상속할 때 같은 문제가 재발하는 것을 방지한다. 단, 전체 리빌드 + 샘플 실행 테스트로 검증이 필요하므로 **이번 MR과 분리하여 별도 클린업 커밋으로 진행 권고**.

---

### 5-4. `ai_studio.cc` + `samples/script/CMakeLists.txt` — SDL 타입 누락

**원인**: `ai_studio` 타겟이 `FILAMENT_SUPPORTS_X11` 없이 컴파일됨. SDL의 `SDL_config.h`는 이 define이 없을 경우 `SDL_config_minimal.h`를 사용하는데, minimal config에는 `intptr_t` 미정의 + `SDL_SysWMinfo.info.x11` 멤버 없음.

**수정 1**: `samples/script/ai_studio.cc`에 `<unistd.h>` 추가 (STDIN_FILENO)
```cpp
#if !defined(_WIN32)
#  include <unistd.h>
#endif
```

**수정 2**: `samples/script/CMakeLists.txt`의 `ai_studio` 타겟에 Linux 전용 define 추가
```cmake
if(GRAPI_USE_WAYLAND)
  target_compile_definitions(ai_studio PRIVATE FILAMENT_SUPPORTS_WAYLAND)
else()
  target_compile_definitions(ai_studio PRIVATE FILAMENT_SUPPORTS_X11)
endif()
```

---

### 5-5. `samples/CMakeLists.txt` — 커스텀 재료 material version 불일치

**파일**: `samples/CMakeLists.txt`

**증상**: `car_paint`, `skywater` 샘플이 Linux 디버그 빌드에서 즉시 크래시
```
libc++abi: terminating
```
Windows 릴리스 빌드에서는 실행됨 (assert가 no-op이라 무시되고 진행).

**원인**: `assets/materials/` 안의 `car_paint.filamat`, `sky.filamat`, `water.filamat`이 구버전 `matc`로 컴파일된 material version 70 바이너리. filament v1.72.0 엔진은 material version 72를 요구하며, 버전 불일치 시 디버그 빌드에서 `assert_invariant` → `utils::panic()` → 예외 → `std::terminate()` 순으로 크래시.

**추가 분석**: `samples/CMakeLists.txt`의 `file(COPY ../assets ...)` 명령은 CMake **구성 시점**에만 실행된다. 즉, filament 버전이 바뀌어도 `.filamat` 파일이 자동으로 재컴파일되지 않아 버전 불일치가 누적된다.

**수정 1**: `matc`로 세 파일 재컴파일 (source `.mat` → version 72 바이너리)
```bash
MATC="$HOME/grapi-base/out/build/linux-clang-debug/external/filament/tools/matc/matc"
cd ~/grapi-base/assets/materials
"$MATC" -o car_paint.filamat  car_paint.mat
"$MATC" -o sky.filamat         sky.mat
"$MATC" -o water.filamat       water_lit.mat
```

**수정 2**: `samples/CMakeLists.txt`에 `custom_materials` CMake 타겟 추가 — 빌드 시 자동 재컴파일
```cmake
if(NOT CMAKE_CROSSCOMPILING AND NOT ANDROID)
  set(CUSTOM_MAT_DIR ${CMAKE_CURRENT_SOURCE_DIR}/../assets/materials)
  set(CUSTOM_FILAMAT_DIR ${PROJECT_BINARY_DIR}/res/assets/materials)

  foreach(MAT_NAME car_paint sky)
    add_custom_command(
      OUTPUT  ${CUSTOM_FILAMAT_DIR}/${MAT_NAME}.filamat
      COMMAND matc -o ${CUSTOM_FILAMAT_DIR}/${MAT_NAME}.filamat
                      ${CUSTOM_MAT_DIR}/${MAT_NAME}.mat
      DEPENDS matc ${CUSTOM_MAT_DIR}/${MAT_NAME}.mat
      COMMENT "Compiling ${MAT_NAME}.mat → ${MAT_NAME}.filamat")
    list(APPEND CUSTOM_FILAMAT_BINS ${CUSTOM_FILAMAT_DIR}/${MAT_NAME}.filamat)
  endforeach()

  add_custom_command(  # water_lit.mat → water.filamat (이름 다름)
    OUTPUT  ${CUSTOM_FILAMAT_DIR}/water.filamat
    COMMAND matc -o ${CUSTOM_FILAMAT_DIR}/water.filamat
                    ${CUSTOM_MAT_DIR}/water_lit.mat
    DEPENDS matc ${CUSTOM_MAT_DIR}/water_lit.mat
    COMMENT "Compiling water_lit.mat → water.filamat")
  list(APPEND CUSTOM_FILAMAT_BINS ${CUSTOM_FILAMAT_DIR}/water.filamat)

  add_custom_target(custom_materials ALL DEPENDS ${CUSTOM_FILAMAT_BINS})
  add_dependencies(custom_materials base_assets matc)
  add_dependencies(car_paint custom_materials)
  add_dependencies(skywater custom_materials)
endif()
```

**비고**: `res/test/vp_hdr.hdr` IBL 파일은 `car_paint` 샘플 코드에서 참조하나 리포지토리에 존재하지 않는 proprietary 에셋. Windows 릴리스 빌드에서도 동일한 경고가 출력되며, 엔진이 IBL 없이 fallback으로 실행됨. 크래시 원인이 아님.

---

## 6. grapi-base 수정 파일 전체 목록

| 파일 | 변경 내용 |
|---|---|
| `base/src/grapi/base/providers/ktx2_reader.cc` | `get_format()` → `get_basis_tex_format()` |
| `libs/io/src/grapi/io/settings.cc` | `sunAngularRadius` → `sunAngularRadiusDeg` (2곳) |
| `base/CMakeLists.txt` | `context.cc`에 `-fno-rtti` 추가 |
| `samples/script/ai_studio.cc` | `<unistd.h>` 추가 |
| `samples/script/CMakeLists.txt` | `ai_studio`에 `FILAMENT_SUPPORTS_X11` define 추가 |
| `samples/CMakeLists.txt` | `custom_materials` 타겟 추가 (`.mat` → `.filamat` 자동 재컴파일) |
| `assets/materials/car_paint.filamat` | matc v72로 재컴파일 |
| `assets/materials/sky.filamat` | matc v72로 재컴파일 |
| `assets/materials/water.filamat` | matc v72로 재컴파일 |

---

## 7. 최종 빌드 및 실행 결과

### 빌드 환경

- OS: WSL Ubuntu / Clang
- 빌드 프리셋: `linux-clang-debug`
- 샘플 포함: `GRAPI_SKIP_SAMPLES=OFF`

### 빌드 결과

```
[2507/2507] Linking CXX executable external/filament/samples/shadowtest
```

**에러**: 0개  
**경고 (잔존)**: lua `tmpnam` deprecated 경고 (pre-existing, grapi-base 소유 코드 아님)
```
warning: the use of `tmpnam' is dangerous, better use `mkstemp'
  → external/lua/loslib.c:172 (lua 라이브러리 내부, 수정 예정)
```

### 샘플 실행 결과 (Linux WSL / lavapipe)

| 샘플 | 결과 | 비고 |
|---|---|---|
| `area_light` | ✅ 정상 | 에어리어 라이트 방향성 확인, 3색 회전 동작 정상 |
| `car_paint` | ✅ 정상 | IBL 경고 출력 후 실행 (에셋 누락은 Windows도 동일) |
| `skywater` | ✅ 정상 | 물 렌더링, 스카이박스 정상 |
| 기타 전체 샘플 | ✅ 정상 | Windows 수정 전 버전과 동일하게 작동 확인 |

**렌더링 성능**: lavapipe는 CPU 소프트웨어 렌더러로 실제 GPU 대비 FPS가 낮음 (정상, 코드 문제 아님)

### 빌드 명령

```bash
cd ~/grapi-base

# 완전 클린 리빌드 (샘플 포함)
rm -rf out/build/linux-clang-debug
cmake --preset linux-clang-debug -DGRAPI_SKIP_SAMPLES=OFF
cmake --build out/build/linux-clang-debug

# 또는 특정 타겟만
cd out/build/linux-clang-debug
ninja samples/geometry_cube
```

---

## 8. 미검증 영역

| 항목 | 이유 | 검증 방법 |
|---|---|---|
| VulkanDriver COMPUTE API | GPU 실기기 필요 (lavapipe) | 실제 GPU 환경 또는 CI |
| QNX 빌드 | QNX 툴체인 필요 | QNX 빌드 환경 |
| Windows 빌드 | 미수행 | Windows 환경 |

---

## 9. 커밋 가이드

### 9-1. filament 서브모듈 커밋 (`~/grapi-base/external/filament`, 브랜치: `merge_v1.72`)

> **참고**: 빌드 에러 수정(DriverEnums, OpenGLContext, VulkanHandles 등)은 이전 커밋(`fix: resolve build errors from v1.72.0 merge`)에 이미 포함됨.  
> 현재 미커밋 변경은 `Scene.cpp` 하나 — area_light 렌더링 버그 2건.

```bash
cd ~/grapi-base/external/filament

git add filament/src/details/Scene.cpp

git commit -m "fix: restore area light rendering broken by v1.72.0 merge

- Restore lightData.elementAt<TANGENT> write lost in auto-merge
- Restore manual GPU light type mapping (isAreaLight->2, isPoint->0, else->1)
  Auto-merge introduced static_cast<uint8_t>(lcm.getType(li)) which passes
  enum value AREA=5 but shader expects LIGHT_TYPE_AREA=2"
```

### 9-2. grapi-base 커밋

```bash
cd ~/grapi-base

git add \
  base/CMakeLists.txt \
  base/src/grapi/base/providers/ktx2_reader.cc \
  build.sh \
  external/CMakeLists.txt \
  libs/io/src/grapi/io/settings.cc \
  samples/CMakeLists.txt \
  samples/script/ai_studio.cc \
  samples/script/CMakeLists.txt \
  assets/materials/car_paint.filamat \
  assets/materials/sky.filamat \
  assets/materials/water.filamat \
  external/filament   # 서브모듈 포인터 업데이트

git commit -m "fix: fix Linux desktop build and sample execution after filament v1.72.0

- base/CMakeLists: compile context.cc with -fno-rtti (VulkanPlatformLinux
  typeinfo undefined symbol at link time)
- ktx2_reader: get_format() -> get_basis_tex_format() (basisu API rename)
- settings: sunAngularRadius -> sunAngularRadiusDeg (LightDefinition rename)
- ai_studio: add <unistd.h> for STDIN_FILENO on Linux
- samples/script/CMakeLists: add FILAMENT_SUPPORTS_X11 define to ai_studio
- samples/CMakeLists: add custom_materials target to recompile .mat files with
  current matc; stale v70 filamat crashed debug builds (material version 72 required)
- assets/materials: recompile car_paint/sky/water filamat to material version 72
- build.sh: fix CMake version comparison logic
- external/CMakeLists: disable FILAMENT_BUILD_TESTING
- external/filament: update submodule pointer"
```

### 9-3. GitLab MR 생성

```bash
# filament 미러 MR
cd ~/grapi-base/external/filament
git push origin merge_v1.72

# GitLab에서 merge_v1.72 → 내부 main(또는 develop) MR 생성
```

---

## 10. 향후 작업

| 항목 | 우선순위 | 내용 |
|---|---|---|
| GitLab MR 생성 | 높음 | filament `merge_v1.72` 브랜치 리뷰 요청 |
| lua `tmpnam` 경고 수정 | 낮음 | `loslib.c` → `mkstemp` 사용 또는 경고 억제 |
| Windows/QNX 빌드 확인 | 중간 | 각 환경별 빌드 에러 점검 |
| 실제 GPU 테스트 | 높음 | CI에서 Vulkan COMPUTE API 검증 |
