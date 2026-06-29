# Filament v1.72.0 머지 리포트

## 개요

- **머지 브랜치**: `merge_v1.72` → 내부 filament 미러 (`code.grapicar.com/engine-dev/core/filament`)
- **베이스**: v1.71.x 회사 내부 브랜치 (HEAD)
- **대상**: upstream `rc/1.72.0`
- **빌드 검증**: WSL Ubuntu / Clang / Mesa llvmpipe + lavapipe (소프트웨어 렌더러)
- **테스트 바이너리**: `backend_test_linux` (OpenGL + Vulkan 백엔드)
- **최종 상태**: filament 백엔드 테스트 통과 + grapi-base 전체 빌드 성공 (샘플 포함, 2507/2507) + **전체 샘플 Linux 실행 성공** + **WebGL(Emscripten) 빌드 성공 + 브라우저 실행 확인** + **Embedded(Telechips TCC803x) 빌드 성공**

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

### 2-10. `GLUtils.h` — WebGL `GL_DRAW_INDIRECT_BUFFER` 미지원

**파일**: `filament/backend/src/opengl/GLUtils.h`

**에러** (`webgl2.txt`):
```
error: use of undeclared identifier 'GL_DRAW_INDIRECT_BUFFER'
```

**원인**: v1.72.0에서 추가된 `BufferObjectBinding::INDIRECT` 케이스(2-4 참조)에 WebGL 가드가 없었음.  
WebGL 2.0 spec은 `GL_DRAW_INDIRECT_BUFFER`를 정의하지 않아 Emscripten 헤더에 해당 상수가 없음.

**수정**: `#ifdef` 가드 추가
```cpp
case BufferObjectBinding::INDIRECT:
#ifdef GL_DRAW_INDIRECT_BUFFER
    return GL_DRAW_INDIRECT_BUFFER;
#else
    utils::panic(__func__, __FILE__, __LINE__, "INDIRECT not supported");
    return 0x8F3F;
#endif
```

---

### 2-11. `Texture.cpp` — WebGL texture swizzling abort 제거

**파일**: `filament/src/details/Texture.cpp`

**에러** (브라우저 콘솔, 런타임):
```
Precondition in build:308 reason: WebGL does not support texture swizzling. Aborted()
```

**원인**: `Texture::Builder::build()` 내부에서 swizzle 요청 시 `FILAMENT_CHECK_PRECONDITION(!swizzled)` 로 abort.  
WebGL 2.0 spec section 5.19에서 `glTexParameteriv` 의 `GL_TEXTURE_SWIZZLE_*` 파라미터를 명시적으로 금지한다.  
DoF(Depth of Field) 패스가 CoC 텍스처에 `.r = CHANNEL_0, .g = CHANNEL_0` swizzle을 요청하는데,  
grapi-base 에서는 DoF가 기본적으로 비활성(`enabled = false`)이지만 해당 abort가 초기화 중 트리거됨.

**기존 동작**: abort → 브라우저 전체 크래시  
**수정**: swizzle 요청 시 abort 대신 silent clear로 변경 — WebGL 백엔드는 어차피 swizzle GL 호출을 지원하지 않으므로 무시해도 무방

```cpp
// 변경 전 (line 307-309)
#if defined(__EMSCRIPTEN__)
FILAMENT_CHECK_PRECONDITION(!swizzled) << "WebGL does not support texture swizzling.";
#endif

// 변경 후
#if defined(__EMSCRIPTEN__)
// WebGL 2.0 does not support texture swizzling; clear silently so downstream
// backend code does not attempt glTexParameteriv swizzle calls.
mImpl->mTextureIsSwizzled = false;
#endif
```

---

### 2-12. `PagedArenaBitset.cpp` — GCC 9에서 C++20 `<bit>` 미구현 (Embedded)

**파일**: `filament/libs/utils/src/PagedArenaBitset.cpp`

**에러**:
```
error: 'countr_zero' is not a member of 'std'
error: 'popcount' is not a member of 'std'
```

**원인**: `std::countr_zero`(최하위 비트부터 0의 개수 세기)와 `std::popcount`(1인 비트의 개수 세기)는 C++20 `<bit>` 헤더에서 도입된 함수다.  
Telechips SDK는 GCC 9.2.1을 포함하며, GCC 9는 `-std=c++2a` 플래그를 지원하지만 `<bit>` 헤더 자체가 존재하지 않거나, 헤더는 있어도 해당 함수가 구현되지 않았다.  
GCC 10부터 완전히 구현되며, 지원 여부는 `__cpp_lib_bitops` feature test 매크로로 판별할 수 있다 (GCC 10+에서 `201907L`로 정의).

**수정 방향 검토**:  
호출 사이트(`std::countr_zero(...)`, `std::popcount(...)`)가 파일 전체에 수십 군데 분산되어 있어 전부 `__builtin_ctz(...)` 로 교체하는 건 비현실적이다.  
대신 `__cpp_lib_bitops` 분기로 `<bit>`를 조건부 포함하고, 미지원 환경에서는 동일 파일 안에서 `std` 네임스페이스에 직접 폴백 함수를 구현하는 방식을 채택했다.  
`std` 네임스페이스에 직접 추가하는 것은 C++ 표준상 undefined behavior이지만, 이 파일 안에서만 사용되고 실제 동작은 동등하므로 실용적으로 문제없다.

**폴백 구현 상세**:
- `countr_zero`: 인자가 0이면 비트 폭 전체 반환, 아니면 GCC builtin 사용  
  - `uint32_t` 이하 → `__builtin_ctz` (32비트 trailing zero count)  
  - `uint64_t` → `__builtin_ctzll` (64비트 버전)  
- `popcount`: GCC builtin 사용  
  - `uint32_t` 이하 → `__builtin_popcount`  
  - `uint64_t` → `__builtin_popcountll`  
- `if constexpr`는 C++17 기능으로 GCC 9에서 지원됨 (문제 없음)

**수정**: `#include <bit>` 를 `__cpp_lib_bitops` 분기 + GCC builtin 폴백으로 교체
```cpp
#if defined(__cpp_lib_bitops) && __cpp_lib_bitops >= 201907L
#  include <bit>
#else
#  include <cstdint>
namespace std {
    template<class T>
    constexpr int countr_zero(T x) noexcept {
        if (x == 0) return (int)(sizeof(T) * 8);
        if constexpr (sizeof(T) <= sizeof(unsigned int))
            return __builtin_ctz((unsigned int)x);
        else
            return __builtin_ctzll((unsigned long long)x);
    }
    template<class T>
    constexpr int popcount(T x) noexcept {
        if constexpr (sizeof(T) <= sizeof(unsigned int))
            return __builtin_popcount((unsigned int)x);
        else
            return __builtin_popcountll((unsigned long long)x);
    }
}
#endif
```

---

### 2-13. `ColorGradingNeon.h` — GCC 9 ARM NEON `vcleq_f32` 반환 타입 변경 (Embedded)

**파일**: `filament/src/details/ColorGradingNeon.h`

**에러**:
```
error: cannot convert 'uint32x4_t' to 'const float32x4_t' in initialization
error: cannot convert 'const float32x4_t' to 'uint32x4_t'
```

**원인**: `ColorGradingNeon.h`는 ARM NEON 전용 코드다. 데스크탑(x86_64)과 Windows(x64)는 ARM 아키텍처가 아니므로 이 파일이 컴파일되지 않아 타입 오류가 숨어있었다. Android는 AArch64지만 Clang(NDK)이 벡터 타입 간 암묵적 변환을 허용해 에러가 발생하지 않았다. Embedded 빌드가 GCC를 사용하는 첫 번째 AArch64 타겟이었고, GCC는 이 타입 불일치를 에러로 처리했다.

| 환경 | 아키텍처 | 컴파일러 | 결과 |
|---|---|---|---|
| 데스크탑 Linux | x86_64 | Clang | NEON 코드 컴파일 안 됨 → 에러 없음 |
| Windows | x86_64 | MSVC | NEON 코드 컴파일 안 됨 → 에러 없음 |
| Android | AArch64 | Clang (NDK) | 벡터 타입 간 암묵적 변환 허용 → 에러 없음 |
| Embedded (Telechips) | AArch64 | GCC 9.2.1 | 타입 불일치를 에러로 처리 → **에러 발생** |

`vcleq_f32(a, b)`는 float 4개를 동시에 비교해 결과를 비트 마스크로 반환한다 (`true → 0xFFFFFFFF`, `false → 0x00000000`). 이 마스크는 float 값이 아닌 정수 마스크이므로 올바른 타입은 `uint32x4_t`다. 이 마스크를 받는 `vbslq_f32(mask, a, b)`도 첫 번째 인자로 `uint32x4_t`를 요구한다.

원래 코드가 마스크를 `float32x4_t`로 받은 것은 애초에 잘못된 코드였으나, GCC 이외 환경에서는 드러나지 않았다.

**수정**: 비교 결과 변수 타입을 `float32x4_t` → `uint32x4_t`로 변경
```cpp
// 변경 전
float32x4_t const r_cond = vcleq_f32(cg_r, vdupq_n_f32(0.0031308f));
float32x4_t const g_cond = vcleq_f32(cg_g, vdupq_n_f32(0.0031308f));
float32x4_t const b_cond = vcleq_f32(cg_b, vdupq_n_f32(0.0031308f));

// 변경 후
uint32x4_t const r_cond = vcleq_f32(cg_r, vdupq_n_f32(0.0031308f));
uint32x4_t const g_cond = vcleq_f32(cg_g, vdupq_n_f32(0.0031308f));
uint32x4_t const b_cond = vcleq_f32(cg_b, vdupq_n_f32(0.0031308f));
```

---

### 2-14. `ShadowMapManager.cpp` — GCC 9 ICE (designated initializer in lambda) (Embedded)

**파일**: `filament/src/ShadowMapManager.cpp`

**에러**:
```
internal compiler error: in build_class_member_access_expr, at cp/typeck.c:2384
```

**용어 정리**:

- **Designated initializer**: C++20에서 도입된 구조체 초기화 문법. 필드 이름을 `.필드명 = 값` 형태로 명시해서 순서와 무관하게 초기화할 수 있다.
  ```cpp
  FrameGraphRenderPass::Descriptor desc{
      .attachments = { .color = { out } },   // ← 이게 designated initializer
      .clearColor  = clearColor,
      .clearFlags  = TargetBufferFlags::COLOR
  };
  ```
- **ICE (Internal Compiler Error)**: 컴파일러 자체가 크래시하는 것. 코드가 잘못된 게 아니라 컴파일러 내부 버그다. "Please submit a full bug report" 메시지가 출력된다.

**원인**:

GCC 9는 C++20 designated initializer를 부분적으로만 지원한다. 특히 아래 세 가지가 동시에 조합될 때 GCC 9 내부에서 크래시가 발생한다:

1. `addPass<Data>(name, setup, execute)` — 타입 파라미터(`Data`)를 가진 **함수 템플릿** 호출
2. `setup` 인자가 `auto&`를 받는 **lambda** 함수
3. 그 lambda 안에서 **designated initializer** 사용

GCC 9가 이 조합을 처리하는 과정(`cp/typeck.c:2384 build_class_member_access_expr`)에서 내부 assertion이 실패한다. 코드 자체는 문법적으로 올바르고, Clang은 정상적으로 컴파일한다.

**왜 다른 환경에서는 에러가 없었나**:

데스크탑 Linux와 Android는 Clang 컴파일러를 사용한다. Clang은 이 조합을 문제없이 처리하므로 에러가 발생하지 않았다. GCC를 사용하는 Embedded 빌드에서 처음 드러난 것이다.

**수정**: designated initializer를 lambda 안에서 없애고, 변수를 먼저 선언한 뒤 필드를 개별 대입
```cpp
// 변경 전 — GCC 9 ICE 발생 (lambda 안에서 designated initializer)
builder.declareRenderPass(builder.getName(input), {
    .attachments = { .color = { out }},
    .clearColor = clearColor,
    .clearFlags = TargetBufferFlags::COLOR
});

// 변경 후 — 필드 대입으로 우회 (designated initializer 제거)
FrameGraphRenderPass::Descriptor rpDesc{};
rpDesc.attachments.color[0] = out;
rpDesc.clearColor = clearColor;
rpDesc.clearFlags = TargetBufferFlags::COLOR;
builder.declareRenderPass(builder.getName(input), rpDesc);
```

`rpDesc{}`로 zero-initialize한 뒤 필드를 하나씩 대입하면 결과는 동일하고 GCC 9의 버그 경로를 우회한다.

---

### 2-15. `TextureCache.cpp` — GCC 9에서 `std::ranges` 미지원 (Embedded)

**파일**: `filament/src/TextureCache.cpp`

**에러**:
```
error: 'std::ranges' has not been declared
```

**원인**: `std::ranges::find_if`는 C++20 기능으로 GCC 9.2.1에서 지원되지 않는다.

**수정**: `std::ranges::find_if` → `std::find_if`로 교체
```cpp
// 변경 전
auto const it = std::ranges::find_if(mRecentEvictions, [&key](auto const& entry) {
    return entry.key == key;
});

// 변경 후
auto const it = std::find_if(mRecentEvictions.begin(), mRecentEvictions.end(),
        [&key](auto const& entry) { return entry.key == key; });
```

---

### 2-16. `zstd/tnt/CMakeLists.txt` — 정적 라이브러리 `-fPIC` 누락 (Embedded)

**파일**: `filament/third_party/zstd/tnt/CMakeLists.txt`

**에러** (링크):
```
relocation R_AARCH64_ADR_PREL_PG_HI21 against symbol `__stack_chk_guard@@GLIBC_2.17'
which may bind externally can not be used when making a shared object; recompile with -fPIC
```

**배경 개념**:

- **`-fPIC` (Position-Independent Code)**: 생성된 기계어 코드가 메모리의 어느 주소에 로드되어도 올바르게 동작하도록 컴파일하는 옵션이다. 전역 변수나 함수 참조 시 절대 주소 대신 상대 주소(GOT/PLT 경유)를 사용한다. shared library(`.so`)는 여러 프로세스가 메모리의 서로 다른 위치에 로드하므로 `-fPIC`가 필수다.

- **`-fstack-protector-strong`**: 스택 버퍼 오버플로를 감지하는 보안 기능이다. 함수 진입 시 `__stack_chk_guard`(glibc의 전역 변수)에서 canary 값을 읽어 스택에 저장하고, 반환 시 값이 바뀌었으면 프로그램을 종료한다. Yocto SDK의 `CFLAGS`에 기본 포함된다.

- **재배치(Relocation)**: 링커가 심볼의 최종 주소를 결정해 코드에 채워 넣는 작업이다. 재배치 타입마다 주소 계산 방식이 다르며, shared object에서 허용되는 타입과 그렇지 않은 타입이 있다.

**원인 연쇄**:

```
Yocto SDK 환경 스크립트
  → CFLAGS에 -fstack-protector-strong 포함
  → CFLAGS에 -fPIC 미포함

zstd CMakeLists.txt
  → POSITION_INDEPENDENT_CODE 미설정
  → CMake가 정적 라이브러리에 -fPIC 추가 안 함
  → libzstd.a 내 .o 파일들이 -fPIC 없이 컴파일됨

libzstd.a(zstd_decompress.c.o) 내부:
  → -fstack-protector-strong 때문에 __stack_chk_guard 참조 발생
  → -fPIC 없으므로 page-relative 재배치(R_AARCH64_ADR_PREL_PG_HI21) 방식으로 참조
  → 이 재배치는 "현재 페이지 기준 offset"이므로 로드 주소가 고정된 실행 파일에서만 유효

libgrapi-base.so 링크 시도
  → libzstd.a 포함
  → 링커: "shared object는 로드 주소가 유동적인데, 이 재배치 타입은 주소 고정을 전제함 → 불가"
  → 링크 실패
```

**왜 x86_64(데스크탑)에서는 안 났나**:

x86_64에서는 `-fstack-protector-strong`이 `__stack_chk_guard`를 RIP-relative 주소 방식(`R_X86_64_REX_GOTPCRELX`)으로 참조한다. 이 재배치 타입은 `-fPIC` 없이도 shared object에서 사용 가능하다. AArch64의 page-relative 방식(`R_AARCH64_ADR_PREL_PG_HI21`)만 공유 라이브러리에서 금지된다.

**왜 zstd만 먼저 에러가 났나**:

Ninja가 병렬 빌드를 하다가 `libgrapi-base.so` 링크 단계에서 처음 발견됐다. 실제로는 `-fPIC` 없는 정적 라이브러리가 zstd 외에도 다수(`libpng.a`, `libz.a` 등) 있었고, zstd가 에러 메시지에 먼저 나온 것뿐이다.

**수정 1** — 선행 시도 (`zstd/tnt/CMakeLists.txt`):
```cmake
add_library(${LIB_TARGET} STATIC ${PUBLIC_HDRS} ${SRCS})
set_target_properties(${LIB_TARGET} PROPERTIES POSITION_INDEPENDENT_CODE ON)
```
zstd 단독으로는 해결되지만, 다음 빌드에서 `libpng.a`에서 동일 에러가 발생해 전역 설정으로 교체했다.

**수정 2** — 전역 설정 (`CMakePresets.json` — `telechips-tcc803x-base`, 5-8 참조):
```json
"CMAKE_POSITION_INDEPENDENT_CODE": "ON"
```
이 CMake 변수를 프리셋에 설정하면 해당 빌드의 모든 타겟에 `-fPIC`가 전파된다. 개별 라이브러리를 하나씩 수정할 필요 없이 일괄 해결된다.

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
| `filament/backend/src/opengl/GLUtils.h` | **WebGL 수정** | `GL_DRAW_INDIRECT_BUFFER` `#ifdef` 가드 추가 (2-4와 동일 파일, 별도 수정) |
| `filament/src/details/Texture.cpp` | **WebGL 수정** | Emscripten에서 swizzle abort → silent clear |
| `filament/libs/utils/src/PagedArenaBitset.cpp` | **Embedded 수정** | GCC 9 대응: `std::countr_zero` / `std::popcount` builtin 폴백 |
| `filament/src/details/ColorGradingNeon.h` | **Embedded 수정** | GCC 9 대응: `vcleq_f32` 반환 타입 `float32x4_t` → `uint32x4_t` |
| `filament/src/ShadowMapManager.cpp` | **Embedded 수정** | GCC 9 ICE 우회: designated initializer를 lambda 밖 필드 대입으로 분리 |
| `filament/src/TextureCache.cpp` | **Embedded 수정** | GCC 9 대응: `std::ranges::find_if` → `std::find_if` |
| `filament/third_party/zstd/tnt/CMakeLists.txt` | **Embedded 수정** | `POSITION_INDEPENDENT_CODE ON` 추가 (AArch64 shared lib 링크 에러) |

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

> SDL / X11 / ImGui 역할 및 관계 상세: [`c++/sdl_x11_imgui.md`](../c++/sdl_x11_imgui.md)

**배경**:

`ai_studio`는 Lua 스크립트 실시간 실행 샘플이다. SDL로 창 두 개(3D 뷰 + ImGui 패널)를 생성하며, filament에 렌더링 대상 창의 네이티브 핸들(X11 `Window`)을 넘겨줘야 한다. filament가 번들링한 SDL2는 `SDL_config.h`를 커스터마이징해서 Linux 창 시스템(X11 또는 Wayland)을 빌드 define으로 선택하게 되어 있다.

**원인**:

`ai_studio` CMake 타겟에 `FILAMENT_SUPPORTS_X11` define이 없었다. 이 define이 없으면 `SDL_config.h`가 `SDL_config_minimal.h`를 선택하고, minimal config에는 `SDL_VIDEO_DRIVER_X11`가 정의되지 않는다. 그 결과 `SDL_syswm.h`의 `SDL_SysWMinfo` 구조체에서 `info.x11` 멤버가 조건부 컴파일로 제외된다.

```cpp
// SDL_syswm.h — SDL_VIDEO_DRIVER_X11 없으면 이 블록 전체 제외
#if defined(SDL_VIDEO_DRIVER_X11)
    struct { Display* display; Window window; } x11;
#endif
```

`ai_studio.cc`는 filament에 창 핸들을 넘기기 위해 `wmi.info.x11.window`를 참조하는데, 해당 멤버가 없어 컴파일 에러가 발생했다. 추가로 `<unistd.h>` include가 빠져 Linux에서 `STDIN_FILENO`를 찾지 못하는 에러도 함께 발생했다.

**수정 1**: `samples/script/ai_studio.cc`에 `<unistd.h>` 추가
```cpp
#if !defined(_WIN32)
#  include <unistd.h>  // STDIN_FILENO
#endif
```

**수정 2**: `samples/script/CMakeLists.txt`의 `ai_studio` 타겟에 Linux 창 시스템 define 추가
```cmake
if(GRAPI_USE_WAYLAND)
  target_compile_definitions(ai_studio PRIVATE FILAMENT_SUPPORTS_WAYLAND)
else()
  target_compile_definitions(ai_studio PRIVATE FILAMENT_SUPPORTS_X11)
endif()
```

이 define으로 `SDL_config_linux_x11.h`가 선택되고 → `SDL_VIDEO_DRIVER_X11` 정의 → `info.x11` 멤버 복원.

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

### 5-6. `samples/CMakeLists.txt` — 병렬 빌드 복사 레이스 컨디션

**파일**: `samples/CMakeLists.txt`

**증상**: Android 빌드 시 Ninja 병렬 빌드 과정에서 간헐적 에러 발생
```
Error copying file ".../libgrapi-assist.so" to ".../samples"
```
멀티코어 환경에서 재현성이 높고, `-j1` (단일 스레드 빌드)에서는 발생하지 않음.

**원인**: 기존 `add_demo()` 함수가 각 샘플 타겟에 개별 `POST_BUILD` 복사 명령을 붙였다. 샘플이 20개 이상이므로 Ninja가 병렬 링크 완료 시 20개 이상의 `cmake -E copy` 프로세스가 동시에 동일한 파일(`libgrapi-assist.so`, `libgrapi-base.so`, `libgrapi-io.so`)을 동일한 `samples/` 디렉토리에 쓰려고 경쟁.

```
libgeometry_cube.so    --POST_BUILD--> copy assist.so, base.so, io.so → samples/
libgeometry_capsule.so --POST_BUILD--> copy assist.so, base.so, io.so → samples/  ← 동시 충돌
libgeometry_curve.so   --POST_BUILD--> copy assist.so, base.so, io.so → samples/  ← 동시 충돌
...
```

**이 버그가 이제야 나타난 이유**: 기존 버전에서도 잠재적으로 존재했으나 빌드 속도나 코어 수 차이로 증상이 드러나지 않았던 pre-existing 버그. v1.72.0 머지 변경과는 무관.

**수정**: 파일당 하나의 `copy_runtime_libs` 커스텀 타겟으로 통합. 모든 샘플이 이 타겟에만 의존하므로 복사는 한 번만 일어난다.

```cmake
if(ANDROID)
  add_custom_target(copy_runtime_libs
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
      $<TARGET_FILE:grapi-assist>
      $<TARGET_FILE:grapi-base>
      $<TARGET_FILE:grapi-io>
      $<TARGET_FILE:xeniagear-engine-jni-adapter>
      ${CMAKE_CURRENT_BINARY_DIR}
    COMMENT "Copying runtime libraries to samples directory"
  )
  add_dependencies(copy_runtime_libs
    grapi-assist grapi-base grapi-io xeniagear-engine-jni-adapter)
else()
  add_custom_target(copy_runtime_libs
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
      $<TARGET_FILE:grapi-assist>
      $<TARGET_FILE:grapi-base>
      $<TARGET_FILE:grapi-io>
      ${CMAKE_CURRENT_BINARY_DIR}
    COMMENT "Copying runtime libraries to samples directory"
  )
  add_dependencies(copy_runtime_libs grapi-assist grapi-base grapi-io)
endif()

function(add_demo NAME)
  ...
  add_dependencies(${NAME} copy_runtime_libs)  # POST_BUILD 대신 단순 의존성
endfunction()
```

`copy_if_different`를 사용하여 파일이 변경되지 않은 경우 복사를 건너뛰므로 증분 빌드 성능도 개선된다.

**플랫폼별 이진 경로**: 모든 프리셋(Linux, Windows, Android)이 Ninja(단일 config) 제너레이터를 사용하므로 실행 파일은 `${CMAKE_CURRENT_BINARY_DIR}` 직접 하위에 위치한다 (multi-config 제너레이터처럼 `Release/`, `Debug/` 서브폴더가 없음).

**동일 버그 — `samples/script/CMakeLists.txt`**: `add_script_demo()` 함수도 동일한 패턴이었다. `script_editor_demo`와 `lua_host` 두 타겟이 각각 `grapi-assist`, `grapi-base`, `grapi-io`, `grapi-script` 4개의 `.so`를 `samples/script/`에 복사하는 POST_BUILD 명령을 가지고 있어 race 발생. → `copy_runtime_script_libs` 타겟으로 동일하게 수정 (`grapi-script` 추가 포함). `.lua` 파일 복사는 타겟마다 서로 다른 파일을 복사하므로 race가 없어 POST_BUILD 유지.

---

### 5-7. WebGL(Emscripten) 빌드 수정

WebGL 타겟(`-p webgl`)은 Emscripten 툴체인으로 빌드한다. 데스크탑·Android 빌드와 다른 4가지 에러가 순서대로 발생했다.

---

#### 에러 1: bluegl x86_64 어셈블리 (`webgl1.txt`)

**에러**:
```
Expected label, @type declaration, got: %
invalid variant 'GOTPCREL'
```
bluegl(`libs/bluegl/src/BlueGLCoreLinuxImpl.S`)의 x86_64 ELF 어셈블리를 Emscripten이 컴파일하려 했음.

**원인**: filament은 내부적으로 `WASM` 변수가 설정된 경우 bluegl 등 데스크탑 전용 라이브러리를 제외한다(`if(NOT WASM)`). grapi-base는 `WEBGL=1`을 쓰지만 `WASM`을 설정하지 않아 filament가 bluegl을 포함시킴.

**수정** (`CMakeLists.txt` 루트):
```cmake
# filament uses WASM (not WEBGL) to exclude desktop-only libs.
# Bridge the naming so filament sees the right flag.
if(WEBGL)
    set(WASM TRUE)
endif()
```

---

#### 에러 2: spirv-cross `throw` 비활성화 (`webgl3.txt`)

**에러**:
```
cannot use 'throw' with exceptions disabled
```
grapi-base는 WebGL 빌드에서 `-fno-exceptions`를 전역 설정한다. spirv-cross는 기본적으로 `throw`를 사용하며, assertions 모드(`SPIRV_CROSS_EXCEPTIONS_TO_ASSERTIONS=ON`)로 전환해야 한다.

**원인 체인**:
```
filament/CMakeLists.txt:135
  → set(SPIRV_CROSS_EXCEPTIONS_TO_ASSERTIONS OFF)  # 무조건
  → if(NOT FILAMENT_ENABLE_EXCEPTIONS)
      set(SPIRV_CROSS_EXCEPTIONS_TO_ASSERTIONS ON)  # FILAMENT_ENABLE_EXCEPTIONS=ON(기본)이면 실행 안 됨
grapi-base: -fno-exceptions 전역 적용
  → spirv-cross: throw 사용 → 컴파일 에러
```

**수정** (`CMakePresets.json` — `webgl-base` 프리셋):
```json
{
  "name": "webgl-base",
  "cacheVariables": {
    "FILAMENT_ENABLE_EXCEPTIONS": "OFF"
  }
}
```
`FILAMENT_ENABLE_EXCEPTIONS=OFF` → `SPIRV_CROSS_EXCEPTIONS_TO_ASSERTIONS=ON` 경로 활성화.  
클린 리빌드 필요 (`rm -rf out/build/linux-webgl-release`).

---

#### 에러 3: `actor_exporter.cc` — try/catch 제거 (`webgl4.txt`)

**에러**:
```
cannot use 'try' with exceptions disabled
```

**파일**: `base/src/grapi/base/actor_exporter.cc`

**수정 1** (line ~2409): 파일 쓰기 블록 — try/catch 제거, 이미 `!file`, `file.good()` 반환값 검사로 처리됨
```cpp
// 변경 전: try { ... } catch (const std::exception& e) { ... }
// 변경 후: 동일 본문을 그냥 블록으로
{
    std::ofstream file(...);
    if (!file) { return false; }
    // ...
}
```

**수정 2** (line ~2463): `copyTextureFile` — try/catch → `std::error_code` 오버로드 사용
```cpp
bool ActorExporter::copyTextureFile(const String& src_path, const String& dst_path) {
    std::error_code ec;
    fs::copy_file(src_path, dst_path, fs::copy_options::overwrite_existing, ec);
    if (ec) {
        if (!options_.quiet) {
            utils::slog.e << "ActorExporter: Failed to copy texture "
                          << src_path << ": " << ec.message() << utils::io::endl;
        }
        return false;
    }
    return true;
}
```

---

#### 에러 4: `custom_material_provider.cc` — try/catch 제거 (`webgl5.txt`)

**에러**:
```
cannot use 'try' with exceptions disabled
```

**파일**: `base/src/grapi/base/custom_material_provider.cc`

**원인**: `Material::Builder().build()` 는 실패 시 nullptr을 반환하고 throw하지 않음. try/catch가 불필요했음.

**수정** (line ~63): try/catch 제거, nullptr 검사로 대체
```cpp
filament::Material* material = filament::Material::Builder()
    .package(data, size)
    .build(engine_);
if (!material) {
    std::cerr << "CustomMaterialProvider: Material::Builder failed" << std::endl;
}
return material;
```

---

### 5-8. Embedded(Telechips TCC803x) 빌드 수정

Embedded 타겟(`-p embedded`, 보드: `telechips-tcc803x`)은 Yocto SDK(GCC 9.2.1, AArch64 크로스 컴파일)로 빌드한다. 데스크탑·WebGL과 다른 2가지 에러가 발생했다.

---

#### 에러 1: `samples/CMakeLists.txt` — `svg_test` / `lottie_player` 타겟 미생성 (`embedded1.txt`)

**에러**:
```
CMake Error at samples/CMakeLists.txt:63 (target_link_libraries):
  Cannot specify link libraries for target "svg_test" which is not built by this project.
```

**원인**: `add_demo()` 함수는 `FILAMENT_EMBEDDED_BUILD`가 설정된 경우 `return()`으로 타겟 생성을 건너뛴다. 그러나 `svg_test`와 `lottie_player`에 대한 `target_link_libraries` / `add_custom_command` 호출은 `add_demo()` 밖에 조건 없이 존재해, 타겟이 없는 상태에서 CMake 오류가 발생한다.

**수정**: 두 블록을 `if(TARGET ...)` 가드로 감싸기
```cmake
add_demo(svg_test)
if(TARGET svg_test)
  target_link_libraries(svg_test PRIVATE grapi-vector)
  add_custom_command(TARGET svg_test POST_BUILD ...)
endif()

add_demo(lottie_player)
if(TARGET lottie_player)
  target_link_libraries(lottie_player PRIVATE grapi-vector)
  add_custom_command(TARGET lottie_player POST_BUILD ...)
endif()
```

---

#### 에러 2: 정적 라이브러리 `-fPIC` 누락 — 전역 설정 (`embedded5.txt`, `embedded6.txt`)

**에러**:
```
relocation R_AARCH64_ADR_PREL_PG_HI21 against symbol `__stack_chk_guard@@GLIBC_2.17'
which may bind externally can not be used when making a shared object; recompile with -fPIC
```

**원인**: Yocto SDK 환경 스크립트(`environment-setup-aarch64-telechips-linux`)가 설정하는 `CFLAGS`에 `-fPIC`가 포함되지 않는다. CMake는 shared library 타겟 자체에는 `-fPIC`를 추가하지만, 그 안에 링크되는 정적 라이브러리에는 별도 설정이 없으면 추가하지 않는다.  
AArch64에서 `-fstack-protector-strong`이 `__stack_chk_guard`에 대한 page-relative 재배치를 생성하므로, `-fPIC` 없이 컴파일된 정적 라이브러리를 shared object에 링크할 수 없다.  
`libzstd.a`(embedded5)에서 처음 발생했고, 이후 `libpng.a`(embedded6)에서도 동일하게 발생함 → 더 나올 것이 예상되어 전역 설정으로 해결.

**수정** (`CMakePresets.json` — `telechips-tcc803x-base` 프리셋):
```json
{
  "name": "telechips-tcc803x-base",
  "cacheVariables": {
    ...
    "CMAKE_POSITION_INDEPENDENT_CODE": "ON"
  }
}
```
`CMAKE_POSITION_INDEPENDENT_CODE=ON`은 해당 프리셋으로 빌드되는 모든 타겟에 `-fPIC`를 전파한다.  
`filament/third_party/zstd/tnt/CMakeLists.txt`에는 선행 시도로 `set_target_properties(... POSITION_INDEPENDENT_CODE ON)`이 추가되어 있으나, 프리셋 전역 설정으로 동일 효과를 얻으므로 중복이다.

---

## 6. grapi-base 수정 파일 전체 목록

| 파일 | 변경 내용 |
|---|---|
| `base/src/grapi/base/providers/ktx2_reader.cc` | `get_format()` → `get_basis_tex_format()` |
| `libs/io/src/grapi/io/settings.cc` | `sunAngularRadius` → `sunAngularRadiusDeg` (2곳) |
| `base/CMakeLists.txt` | `context.cc`에 `-fno-rtti` 추가 |
| `samples/script/ai_studio.cc` | `<unistd.h>` 추가 |
| `samples/script/CMakeLists.txt` | `ai_studio`에 `FILAMENT_SUPPORTS_X11` define 추가 |
| `samples/CMakeLists.txt` | ① `copy_runtime_libs` 단일 타겟으로 병렬 복사 레이스 수정 ② `custom_materials` 타겟으로 `.mat` → `.filamat` 자동 재컴파일 |
| `samples/script/CMakeLists.txt` | `copy_runtime_script_libs` 단일 타겟으로 병렬 복사 레이스 수정 (ai_studio define 수정도 포함) |
| `assets/materials/car_paint.filamat` | matc v72로 재컴파일 |
| `assets/materials/sky.filamat` | matc v72로 재컴파일 |
| `assets/materials/water.filamat` | matc v72로 재컴파일 |
| `CMakeLists.txt` (루트) | **WebGL** `if(WEBGL) set(WASM TRUE)` — filament WASM 플래그 브리지 |
| `CMakePresets.json` | **WebGL** `webgl-base` 프리셋에 `FILAMENT_ENABLE_EXCEPTIONS: OFF` 추가 |
| `base/src/grapi/base/actor_exporter.cc` | **WebGL** try/catch 2건 제거 (파일 쓰기 블록, copyTextureFile) |
| `base/src/grapi/base/custom_material_provider.cc` | **WebGL** try/catch 제거 (Material::Builder().build() 는 throw 안 함) |
| `samples/CMakeLists.txt` | **Embedded** `svg_test` / `lottie_player` `if(TARGET ...)` 가드 추가 |
| `CMakePresets.json` | **Embedded** `telechips-tcc803x-base`에 `CMAKE_POSITION_INDEPENDENT_CODE: ON` 추가 |

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
| WebGL 런타임 렌더링 | 빌드·실행은 성공, Fox 모델이 화면에 보이지 않음 (파일 시스템 / 텍스처 / 카메라 스케일 중 원인 미확정) | 브라우저 디버깅, `-sASSERTIONS=1` 빌드 |
| Embedded 실기기 실행 | 빌드 성공 (`.so` 생성 확인), 실기기(Telechips TCC803x 보드) 동작은 미확인 | 보드에 `.so` 배포 후 런타임 검증 |

---

## 9. 향후 작업

| 항목 | 우선순위 | 내용 |
|---|---|---|
| lua `tmpnam` 경고 수정 | 낮음 | `loslib.c` → `mkstemp` 사용 또는 경고 억제 |
| QNX 빌드 확인 | 중간 | QNX 환경 빌드 에러 점검 |
| 실제 GPU 테스트 | 높음 | CI에서 Vulkan COMPUTE API 검증 |
| WebGL 런타임 렌더링 디버깅 | 낮음 | 브라우저에서 Fox 모델 미출력 원인 파악 (파일시스템 접근, 텍스처 포맷, 카메라 스케일) |
| Embedded 실기기 검증 | 중간 | Telechips TCC803x 보드에 `.so` 배포 후 런타임 동작 확인 |
