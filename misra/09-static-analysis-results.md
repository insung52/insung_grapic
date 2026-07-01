# 무료 정적분석 도구 테스트 결과 분석 — grapi-base

> Clang-Tidy(v2 확장 스캔)와 Cppcheck 두 도구를 grapi-base 엔진(`base/` 모듈 131개 파일)에 실제로 돌린 결과를 통합 분석.  
> 원시 결과 파일: `clangtidy_v2.txt`, `cppcheck_result_v3.txt`  
> (2026-06 기준, LLVM 19 / Cppcheck 2.21.0)

---

## 1. 스캔 환경 요약

| 항목 | Clang-Tidy v2 | Cppcheck |
|------|--------------|----------|
| 버전 | LLVM 19 (VS 2022 번들) | 2.21.0 |
| 분석 파일 수 | 131개 | 131개 |
| 외부 라이브러리 제외 | `HeaderFilterRegex` | `--file-filter=*\grapi-base\base\*` |
| 설정 파일 | `.clang-tidy` (v2 확장) | 명령줄 옵션 |
| 결과 저장 | `clangtidy_v2.txt` | `cppcheck_result_v3.txt` |

**환경 노이즈 주의**: VS 2026 Insiders MSVC 헤더가 Clang 20+를 요구해 각 파일마다 `STL1000: Unexpected compiler version` 에러가 발생. 실제 프로젝트 코드 분석에는 영향 없음(suppressed 항목으로 처리됨).

---

## 2. 발견 이슈 전체 요약

| 등급 | 항목 수 | 설명 |
|------|--------|------|
| **A. 잠재적 버그** | 14건 | 실제 런타임 오동작 가능성 있음 — 즉시 검토 필요 |
| **B. 타입/안전성 문제** | ~50건 | 타입 변환 오류·부호 비트 연산·C 스타일 캐스트·다중 포인터 변환 등 |
| **C. 코드 설계 문제** | ~20건 | API 설계·재귀·Rule of Five·virtual 소멸자 등 |
| **D. 성능/스타일 개선** | ~50건 | `= default`, `[[nodiscard]]`, unused 파라미터, TODO 포맷 등 |
| **E. 대량 스타일 (노이즈)** | 100건+ | `misc-const-correctness` 위주 — 기계적으로 수정 가능 |
| **F. 인프라 패턴 (오탐)** | 400건+ | pointer-arithmetic 278건, array-to-pointer-decay 15건, `malloc`/C API 74건 등 불가피한 경고 |

---

## 3. A등급 — 잠재적 버그 (즉시 검토)

### A-1. `if` 조건문 내 대입 연산자 (확인된 버그)
**도구**: Clang-Tidy `bugprone-assignment-in-if-condition`  
**위치**: `vehicle_component.cc:940`

```cpp
void VehicleComponent::setRearSuspension(...) {
  if ((rear_suspension_.min_length_ != min_length) ||
      (rear_suspension_.max_length_ = max_length) ||   // ← 버그: = 대입, != 비교여야 함
      (rear_suspension_.frequency_ != frequency) ||
      (rear_suspension_.damping_ != damping)) {
    rear_suspension_.min_length_ = min_length;
    rear_suspension_.max_length_ = max_length;         // ← 이중 대입
    rear_suspension_.frequency_ = frequency;
    rear_suspension_.damping_ = damping;
    refresh();
  }
}
```

위아래 줄이 모두 `!=` 비교인데 940번 줄만 `=` 대입. `!=`의 오타로 확인.

**실제 부작용 두 가지**:
1. `max_length`가 0이 아닌 이상 이 조건은 항상 `true`가 되어 나머지 `||` 피연산자를 단락(short-circuit)으로 건너뜀 — `frequency`/`damping` 비교가 무의미해짐
2. if 블록 진입 전에 `rear_suspension_.max_length_`가 이미 변경되고, 블록 안(944번 줄)에서 또 한 번 대입되는 이중 대입 발생

**수정**: 940번 줄 `=` → `!=`

---

### A-2. 동일한 true/false 분기 (확인된 복붙 버그)
**도구**: Clang-Tidy `bugprone-branch-clone` + `misc-redundant-expression`  
**위치**: `vehicle_component.cc:144`

```cpp
// 141번 줄 — 정상: isCar() 여부에 따라 다른 배열 사용
glm::quat local_rotation =
    isCar() ? car_wheel_matrics[w] : mortor_wheel_matrics[w];

// 143-144번 줄 — 버그: true/false 양쪽 모두 car_wheel_scale
glm::vec3 correct_scale =
    isCar() ? car_wheel_scale[w] : car_wheel_scale[w];
```

바로 위 `local_rotation` 대입문이 `car_wheel_matrics` vs `mortor_wheel_matrics`로 분기하는 패턴을 복붙한 후 false 브랜치를 `mortor_wheel_scale[w]`(또는 유사 변수)로 수정하지 않은 것으로 보임. `isCar()`가 false여도 항상 `car_wheel_scale`을 사용하게 되어 모터사이클 휠 스케일이 잘못 적용됨.

**수정**: false 브랜치를 올바른 모터사이클용 스케일 배열로 교체 (해당 변수명 확인 필요)

---

### A-3. `else` 분기에서 빈 배열 인덱스 접근 (확인된 복붙 버그)
**도구**: Cppcheck `arrayIndexOutOfBoundsCond`  
**위치**: `geometry_component.cc:554-568`

```cpp
if (!attribute_indices_.empty()) {
    for (vsize i = 0; i < attribute_indices_.size(); ++i) {
        attributes_.positions[attribute_indices_[i]];   // 정상
        morph_target.positions[attribute_indices_[i]];  // 정상
    }
} else {
    // attribute_indices_ 가 비어있을 때 진입하는 분기인데
    for (vsize i = 0; i < morph_target.positions.size(); ++i) {
        attributes_.positions[attribute_indices_[i]];   // ← 버그: empty 배열에 [i] 접근
        morph_target.positions[attribute_indices_[i]];  // ← 버그: 동일
    }
}
```

`else` 분기는 `attribute_indices_`가 비어있는 경우에만 진입하지만, 내부에서 `attribute_indices_[i]`를 인덱스로 사용 — 즉시 OOB(out-of-bounds) 접근. 함수 앞부분의 동일한 패턴(`else` 분기에서 `attributes_.positions[i]`로 직접 `i` 사용)을 복붙 후 `attribute_indices_[i]` → `i` 교체를 빠뜨린 것.

**수정**: else 분기 내 `attribute_indices_[i]` → `i`로 교체

```cpp
} else {
    for (vsize i = 0; i < morph_target.positions.size(); ++i) {
        const glm::vec3& offset = attributes_.positions[i];
        const glm::vec3& v = morph_target.positions[i] + offset;
        ...
    }
}
```

---

### A-4. `malloc` 반환값 null 미체크 (확인됨)
**도구**: Cppcheck `nullPointer` — "If memory allocation fails, then there is a possible null pointer dereference: blocks"  
**위치**: `ktx2_reader.cc:566-567`, `ktx2_reader.cc:647-648`

```cpp
// 두 위치 모두 동일한 패턴
vuint64* const blocks = static_cast<vuint64*>(malloc(length));  // null 가능
memcpy(blocks, level_data, length);  // ← null 체크 없이 즉시 사용 → UB
pbd = new Texture::PixelBufferDescriptor(blocks, length, ...);
```

`malloc` 실패 시 `nullptr`를 반환하지만 즉시 `memcpy`에 전달 — 미정의 동작. `new`는 실패 시 예외를 던지지만 `malloc`은 조용히 `nullptr`를 반환한다는 차이를 고려하지 않은 것.

**수정**:
```cpp
vuint64* const blocks = static_cast<vuint64*>(malloc(length));
if (!blocks) { /* 오류 처리 */ return nullptr; }
memcpy(blocks, level_data, length);
```

---

### A-5. glm 생성자 쉼표 오탐 (F등급 재분류 — 오탐 확인)
**도구**: Cppcheck `suspiciousCommaExpression` — "Found suspicious operator ',', result is not used."  
**위치**: `curve.cc:183, 188, 192, 214, 232`

실제 Cppcheck 출력 확인 결과, 경고가 실제로 존재하지만 **오탐**으로 판단:

```cpp
// curve.cc:183 — Cppcheck가 경고한 줄
normal = glm::vec3(1.0f, 0.0f, 0.0f);

// curve.cc:214
normals[i] = glm::vec3(rotation_matrix * glm::vec4(normals[i], 0.0f));
```

`glm::vec3(1.0f, 0.0f, 0.0f)`의 `,`는 생성자 인자 구분자이지 쉼표 연산자가 아님. Cppcheck가 glm 템플릿 타입을 완전히 파싱하지 못해 `glm::vec3(1.0f)` + 미사용 `0.0f, 0.0f`로 잘못 해석한 것. 코드 로직에 문제 없음.

**처리**: `// cppcheck-suppress suspiciousCommaExpression` 또는 무시.

> **참고**: A-5는 실질적 위험 없음 — F등급(오탐)으로 재분류.

---

### A-6. 재귀 함수 (MISRA 금지 패턴, 확인됨)
**도구**: Clang-Tidy `misc-no-recursion`  
**위치**: `asset_loader.cc:529` (`_recursePrimitives`), `asset_loader.cc:794` (`_recurseEntities`)

```cpp
// _recursePrimitives (line 529)
void AssetLoader::_recursePrimitives(const cgltf_node* node, AssetImpl* asset) {
  // ...
  for (cgltf_size i = 0, len = node->children_count; i < len; ++i) {
    _recursePrimitives(node->children[i], asset);  // ← 자기 자신 호출
  }
}

// _recurseEntities (line 794)
void AssetLoader::_recurseEntities(const cgltf_node* node, Actor* parent, AssetImpl* asset) {
  // ...
  for (cgltf_size i = 0, len = node->children_count; i < len; ++i) {
    _recurseEntities(node->children[i], actor, asset);  // ← 자기 자신 호출
  }
}
```

MISRA C++ Rule 6.4.1 — 재귀 함수는 스택 깊이를 정적으로 보장할 수 없어 금지. glTF 씬 트리 탐색 구조상 의도적 설계이지만, 복잡한 씬에서 깊은 계층이 있을 경우 스택 오버플로 위험.

**수정 방법: `std::stack`을 사용한 반복 방식으로 전환**

**`_recursePrimitives` — 단순 DFS**

부모-자식 의존성 없이 각 노드를 독립적으로 처리하므로 변환이 단순:

```cpp
void AssetLoader::_recursePrimitives(const cgltf_node* root, AssetImpl* asset) {
  std::stack<const cgltf_node*> stack;
  stack.push(root);

  while (!stack.empty()) {
    const cgltf_node* node = stack.top();
    stack.pop();

    String name_str = getNodeName(node);
    const vchar* name = name_str.c_str();
    name = name ? name : "node";

    if (node->mesh) {
      _createPrimitives(node, name, asset);
      asset->mesh_count_++;
    }

    // 스택(LIFO)이라 역순 push해야 원래 순서(0→N) 유지
    for (cgltf_size i = node->children_count; i > 0; --i) {
      stack.push(node->children[i - 1]);
    }
  }
}
```

**`_recurseEntities` — 부모 actor를 자식에게 전달해야 하는 경우**

재귀에서 현재 노드의 `actor`를 자식 호출에 `parent`로 넘기는 구조. 반복으로 바꾸면 `{node, parent_actor}` 쌍을 스택에 저장:

```cpp
void AssetLoader::_recurseEntities(const cgltf_node* root, Actor* root_parent,
                                   AssetImpl* asset) {
  const cgltf_data* src_asset = asset->source_asset_->hierarchy;

  std::stack<std::pair<const cgltf_node*, Actor*>> stack;
  stack.push({root, root_parent});

  while (!stack.empty()) {
    auto [node, parent] = stack.top();
    stack.pop();

    String name_str = getNodeName(node);
    const vchar* name = name_str.c_str();
    name = name ? name : "node";

    Actor* actor = nullptr;
    if (node->mesh)   actor = _createMesh(node, name, asset);
    if (node->light)  actor = _createLight(node->light, name, asset);
    if (node->camera) actor = _createCamera(node->camera, name, asset);

    ObjectFactory* factory = Context::get().getObjectFactory();
    actor = actor ? actor : factory->createActor(name);

    // transform 계산 (기존 코드와 동일)
    glm::quat rotation;
    glm::vec3 scale, translation;
    if (node->has_matrix) {
      filament::math::mat4f local_transform;
      memcpy(&local_transform[0][0], &node->matrix[0], 16 * sizeof(vfloat));
      filament::math::float3 t; filament::math::quatf r; filament::math::float3 s;
      filament::gltfio::decomposeMatrix(local_transform, &t, &r, &s);
      rotation = toQuat(r); scale = toVec3(s); translation = toVec3(t);
    } else {
      const cgltf_float* t = node->translation;
      const cgltf_float* r = node->rotation;
      const cgltf_float* s = node->scale;
      rotation = {r[3], r[0], r[1], r[2]};
      scale = {s[0], s[1], s[2]};
      translation = {t[0], t[1], t[2]};
    }

    actor->setPosition(translation);
    actor->setRotation(rotation);
    actor->setScale(scale);

    BaseID actor_id = actor->getBaseID();
    if (parent) parent->addChild(actor_id);
    asset->actors_.push_back(actor_id);
    asset->node_map_[node - src_asset->nodes] = actor_id;
    asset->name_to_actor_[name].push_back(actor_id);

    // 자식 push — 현재 actor를 자식들의 parent로
    for (cgltf_size i = node->children_count; i > 0; --i) {
      stack.push({node->children[i - 1], actor});
    }
  }
}
```

---

### A-7. 멤버 초기화 누락 (확인됨)
**도구**: Clang-Tidy `cppcoreguidelines-pro-type-member-init`  
**위치**: `material_component.h:74` 선언, `material_component.cc:17` 생성자

```cpp
// MaterialProvider.h (filament external)
enum UvSet : uint8_t { UNUSED = 0, UV0, UV1 };
using UvMap = std::array<UvSet, 8>;   // → uint8_t 8개짜리 배열

// material_component.h:74
filament::gltfio::UvMap uvmap_;   // 초기화 없음 → 쓰레기값 8개

// material_component.cc:17
MaterialComponent::MaterialComponent(Entity e) : Component(e) {
  // uvmap_ 빠짐
}

// material_component.cc:112 — 나중에 읽힘
vint MaterialComponent::_getUvIndex(vuint8 src_index, bool has_texture) const {
  return has_texture ? static_cast<vint>(uvmap_.at(src_index)) - 1 : -1;
}
```

`UvMap`은 `std::array<UvSet, 8>` 즉 `uint8_t` 8개짜리 배열. `std::array`는 명시적으로 초기화하지 않으면 0으로 채워지지 않음(`std::vector`와 다름). `_getUvIndex`에서 `UNUSED(0)`, `UV0(1)`, `UV1(2)` 중 하나를 반환해야 하는데, 쓰레기값이 들어있으면 엉뚱한 텍스처 인덱스를 반환.

실제로 `getMaterial(&key_, &uvmap_, ...)` 호출로 채워진 후 `_getUvIndex`가 불리는 정상 경로에서는 문제없지만, 그 순서가 보장되지 않는 경우나 코드가 변경될 경우를 대비해 초기화가 맞음.

**수정 — `material_component.h`에서 기본값 지정 (권장)**:
```cpp
// 변경 전
filament::gltfio::UvMap uvmap_;

// 변경 후 — 모두 UNUSED(0)으로 초기화
filament::gltfio::UvMap uvmap_ = {};
```

---

**추가 확인된 미초기화 멤버 (Cppcheck)**

**`asset_impl.h:104` — `SourceAsset::hierarchy` (가장 위험)**
```cpp
struct SourceAsset {
  ~SourceAsset() {
    cgltf_free(hierarchy);   // 소멸자에서 포인터 해제
  }
  cgltf_data* hierarchy;     // ← nullptr 초기화 없음
};
```
`hierarchy`가 초기화되지 않은 채 소멸자에서 `cgltf_free`에 쓰레기 포인터가 전달되면 크래시. 세 가지 중 실제 크래시 가능성이 가장 높음.

```cpp
// 수정
cgltf_data* hierarchy = nullptr;
```

**`asset_loader.h:40` — `error_`**
```cpp
bool error_;     // 초기화 없음
// → if (error_) 체크 시 undefined behavior
```
```cpp
// 수정
bool error_ = false;
```

**`ktx2_provider.cc:61` — `QueueItem` 멤버 4개 + `decoder_root_job_`**
```cpp
// 수정 — 실제 타입에 맞는 default member initializer 추가
struct QueueItem {
  Ktx2Reader::Async* async_ = nullptr;
  QueueItemState state_ = QueueItemState::kTranscoding;
  std::atomic<TranscoderState> transcoder_state_{TranscoderState::kNotStarted};
  utils::JobSystem::Job* job_ = nullptr;
};

// 동일 클래스의 decoder_root_job_(line 74)도 같은 패턴
utils::JobSystem::Job* decoder_root_job_ = nullptr;
```

**`ktx2_reader.cc:170` — `level_info`**
```cpp
// 수정: 값 초기화
basist::ktx2_image_level_info level_info{};
transcoder.get_image_level_info(level_info, level_index, layer_index, face_index);
```

**`ktx2_reader.cc:782` — 내부 `info` (line 765의 outer `info`와 별개)**
```cpp
// 수정: 값 초기화 (outer FinalFormatInfo info와 별개 지역변수)
basist::ktx2_image_level_info info{};
if (!transcoder->get_image_level_info(info, level_index, layer_index, face_index)) {
```

**`physics_context.cc:57` — `mObjectToBroadPhase`**

다른 케이스들과 달리 **C 스타일 배열(`JPH::BroadPhaseLayer mObjectToBroadPhase[N]`)** 이라 헤더 선언부에서 `= {}` 초기화가 불가능. C++ 에서 비정적 C 배열은 in-class 기본값을 줄 수 없으므로, 생성자 이니셜라이저 목록(MIL)이 유일한 초기화 수단.

> 개념 참고: [07_structs_and_initialization.md § 9. 멤버 이니셜라이저 목록 (MIL)](../c++/07_structs_and_initialization.md)  
> — MIL vs 본문 대입의 차이 / C 배열은 in-class 초기화 불가 → MIL만 가능 / Clang-Tidy 경고 이유

```cpp
// physics_context.h — C 배열 (헤더에서 = {} 불가)
JPH::BroadPhaseLayer mObjectToBroadPhase[layers::kNumLayers];

// 수정: MIL에서 {} 로 0 초기화 → 본문에서 실제 값으로 덮어씀
BPLayerInterfaceImpl::BPLayerInterfaceImpl() : mObjectToBroadPhase{} {
  mObjectToBroadPhase[layers::kNonMoving] = broad_phase_layers::kNonMoving;
  mObjectToBroadPhase[layers::kMoving]    = broad_phase_layers::kMoving;
  mObjectToBroadPhase[layers::kGhost]     = broad_phase_layers::kMoving;
}
```

**`nine_patch_component.h:143` — `vertices_`**
`std::array<Vertex, 16>` — 헤더 선언부에 `{}` 추가.
```cpp
// 수정 (nine_patch_component.h)
std::array<Vertex, 16> vertices_{};
```

**`image.h:295` — `vertices_`**
`std::array<Vertex, 4>` — 헤더 선언부에 `{}` 추가.
```cpp
// 수정 (image.h)
std::array<Vertex, 4> vertices_{};
```

---

### A-8. 부호 있는 정수에 비트 연산 (확인됨)
**도구**: Clang-Tidy `hicpp-signed-bitwise`  
**총 건수**: 20건 (이전 요약의 5건은 부분 집계)  
**파일별**: `view_impl.cc`(2), `particles_component.cc`(6), `actor_exporter.cc`(5), `freetype_font.cc`(2), `asset_loader.cc`(2), `custom_material_provider.cc`(1), `resource_manager.cc`(1), `scene_impl.cc`(1)

세 가지 패턴으로 분류:

---

**① 사용자 코드 — signed 리터럴/시프트량 (수정 대상, 13건)**

**`view_impl.cc:1141`** (2건)
```cpp
const vuint8 bit = static_cast<vuint8>(1u << (layer & 7));
//                                              ^^^^^^^
//  7이 int(signed) → vuint8이 int로 승격되어 signed 비트 연산 발생 (경고 1)
//  ~bit: vuint8이 int로 승격 후 ~ 적용 → signed 비트 NOT (경고 2)
```
```cpp
// 수정
const vuint8 bit = static_cast<vuint8>(1u << (layer & 7u));
//  ~bit 부분도: static_cast<vuint8>(~static_cast<vuint32>(bit))
```

**`particles_component.cc`** (6건 — 112, 128, 144, 484, 500, 509)
```cpp
active_frames_ |= 1;     // 1이 signed int
active_frames_ <<= 1;    // 시프트량 1이 signed int
```
```cpp
// 수정: u 접미사
active_frames_ |= 1u;
active_frames_ <<= 1u;
```

**`actor_exporter.cc`** (4건 — 2280~2283)
```cpp
key |= static_cast<vuint64>(tex->getMinFilter()) << 0;   // 0이 signed int
key |= static_cast<vuint64>(tex->getMagFilter()) << 8;   // 8이 signed int
key |= static_cast<vuint64>(tex->getWrapModeS()) << 16;
key |= static_cast<vuint64>(tex->getWrapModeT()) << 24;
```
```cpp
// 수정: 시프트량에 u 접미사
key |= static_cast<vuint64>(tex->getMinFilter()) << 0u;
key |= static_cast<vuint64>(tex->getMagFilter()) << 8u;
// ...
```

**`scene_impl.cc:375`** (1건)
```cpp
visible = ibl_->getSkybox()->getLayerMask() & 0xff;  // 0xff가 signed int
```
```cpp
// 수정
visible = ibl_->getSkybox()->getLayerMask() & 0xffu;
```

---

**② STL openmode — NOLINT 처리 (5건)**

`asset_loader.cc:130,224`, `custom_material_provider.cc:28`, `resource_manager.cc:172`, `actor_exporter.cc:2510`

```cpp
std::ifstream in(filename, std::ifstream::ate | std::ifstream::binary);
//  std::ios::openmode 는 MSVC 구현에서 signed 타입 — 직접 수정 불가
```
```cpp
// 처리: NOLINT 주석
std::ifstream in(filename, std::ifstream::ate | std::ifstream::binary);  // NOLINT(hicpp-signed-bitwise)
```

---

**③ 외부 C API 플래그 — NOLINT 처리 (2건)**

`freetype_font.cc:147`

```cpp
FT_Load_Glyph(ft_face_, ft_index, FT_LOAD_DEFAULT | FT_LOAD_NO_HINTING);
//  FreeType 매크로가 int 타입 — 라이브러리 설계상 불가피
```
```cpp
// 처리: NOLINT 주석
FT_Load_Glyph(ft_face_, ft_index, FT_LOAD_DEFAULT | FT_LOAD_NO_HINTING);  // NOLINT(hicpp-signed-bitwise)
```

---

### A-9. 소멸자에서 예외 탈출 가능성 (확인됨)
**도구**: Clang-Tidy `bugprone-exception-escape`  
**위치**: `asset_impl.cc:16` (`~AssetImpl`)  
> 개념 참고: [11_exceptions.md § 4. noexcept / § 8. 소멸자에서 예외 처리](../c++/11_exceptions.md)  
> — 소멸자는 암묵적 `noexcept`, 예외 탈출 시 `std::terminate`, `catch (...)`로 삼키는 이유

소멸자 내에서 예외가 발생할 수 있는 코드가 존재. C++ 표준상 소멸자에서 예외가 탈출하면 `std::terminate()` 호출로 프로세스가 즉시 종료됨.

**수정**: 소멸자 본문 전체를 `try-catch`로 감쌈. `utils::slog`의 `operator<<`가 전부 `noexcept`이므로 catch 블록 안에서 로그 출력 안전.
```cpp
AssetImpl::~AssetImpl() {
  try {
    releaseSourceData();
    if (!detached_) {
      ObjectFactory* factory = Context::get().getObjectFactory();
      for (BaseID const actor_id : actors_) { factory->destroy(actor_id); }
      // ... (나머지 destroy 루프)
    }
  } catch (const std::exception& e) {
    utils::slog.e << "~AssetImpl: cleanup failed: " << e.what() << utils::io::endl;
  } catch (...) {
    utils::slog.e << "~AssetImpl: cleanup failed: unknown exception" << utils::io::endl;
  }
}
```

---

### A-10. 변환 순서 오류 — 확장 전 캐스트 (확인됨)
**도구**: Clang-Tidy `bugprone-misplaced-widening-cast`  
**위치**: `curve.cc:42`

```
경고: "either cast from 'int' to 'vsize' (aka 'unsigned long long') is ineffective,
      or there is loss of precision before the conversion"
```

`int`에서 `vsize`(uint64)로의 캐스트가 산술 연산 *후*에 적용되어 int 범위에서 먼저 오버플로가 발생하거나, 캐스트 결과가 실제로 쓰이지 않는 패턴. 두 경우 모두 의도와 다른 동작 가능.

**수정**: 덧셈 전에 캐스트를 먼저 적용해 uint64 범위에서 연산:
```cpp
// 변경 전 — int + 1이 int 범위에서 먼저 계산된 후 vsize로 캐스트
cache_arc_lengths_.size() == static_cast<vsize>(arc_length_divisions + 1)

// 변경 후 — 먼저 vsize로 확장 후 덧셈
cache_arc_lengths_.size() == static_cast<vsize>(arc_length_divisions) + 1
```

---

### A-11. `sscanf` 변환 오류 미보고 (확인됨)
**도구**: Clang-Tidy `cert-err34-c`  
**위치**: `ibl.cc:194`

```cpp
// ibl.cc:194 — 실제 코드
vint const n = sscanf(line.c_str(), "(%f,%f,%f)", &band.r, &band.g, &band.b);
if (n != 3) return false;  // ← 반환값은 이미 체크됨
```

**`cert-err34-c`가 정확히 뭘 경고하나**

`sscanf`의 반환값 `n`은 **"몇 개 파싱했냐"** 만 알려줌. 각 변환값이 float 범위 안에 있는지는 알 수 없음.

```
입력: "(1e999,0,0)"
  → sscanf("%f", ...) 실행
  → 1e999는 float 최대값(~3.4e38) 초과
  → 결과 = HUGE_VALF 또는 Inf  ← 오버플로지만 n == 3 반환 (조용히 통과)
```

`strtof`를 쓰면 `errno == ERANGE`로 오버플로를 감지할 수 있어 더 안전. `cert-err34-c`는 이 차이를 경고하는 것.

**왜 NOLINT로 처리했나**

| 근거 | 설명 |
|------|------|
| 반환값 체크 완료 | `if (n != 3) return false` — 파싱 실패는 이미 잡힘 |
| 신뢰된 내부 입력 | sh 파일은 직접 생성하는 내부 포맷, 외부 사용자 입력 아님 |
| float 오버플로 가능성 없음 | 구면 조화 계수는 통상 -10 ~ +10 범위 |
| `strtof` 대체 비용 | `(%f,%f,%f)` 포맷을 `strtof`로 바꾸면 파싱 코드가 수십 줄로 늘어남 |

**처리**: NOLINT
```cpp
vint const n = sscanf(line.c_str(), "(%f,%f,%f)", &band.r, &band.g, &band.b);  // NOLINT(cert-err34-c)
if (n != 3) return false;
```

> **참고**: 같은 위치(`ibl.cc:194`)에서 B-9(`pro-type-vararg`)도 함께 발생 — `sscanf`가 C 가변 인자 함수이기 때문.

---

### A-12. `switch`에 `default` 케이스 없음 (확인됨)
**도구**: Clang-Tidy `bugprone-switch-missing-default-case`  
**위치**: `first_person_controls.cc:19`, `fly_controls.cc:22`

int(또는 non-enum) 값에 대한 switch문에 `default` 케이스가 없어, 예상 범위를 벗어난 입력 값이 들어올 경우 조용히 처리되지 않고 통과.

```cpp
// 예시 패턴
switch (key_code) {
  case KeyW: moveForward(); break;
  case KeyS: moveBackward(); break;
  // default 없음 — 다른 키는 무시되지만 명시적이지 않음
}
```

**수정**: `default: break;` 추가로 의도적 무시를 명시:
```cpp
switch (key_code) {
  case KeyW: moveForward(); break;
  case KeyS: moveBackward(); break;
  default: break;  // 명시적으로 나머지 무시
}
```

---

### A-13. 추가 재귀 함수 (확인됨)
**도구**: Clang-Tidy `misc-no-recursion`  
**위치**: `actor_exporter.cc:319` (`traverseActor`), `raycaster.cc:15` (`intersect`)

A-6에서 `asset_loader.cc`의 재귀 함수 2건을 반복 방식으로 전환 완료. 추가 재귀 함수 2건 확인:

- **`traverseActor` (actor_exporter.cc:319)**: 씬 트리를 순회하며 glTF 노드를 내보내는 함수. A-6의 트리 탐색 패턴과 동일.
- **`intersect` (raycaster.cc:15)**: 액터 트리를 순회하며 레이 교차 검사. `recursive` 플래그로 자식 탐색 여부 제어.

**수정**: A-6과 동일하게 `std::stack` 기반 반복 방식으로 전환. 두 파일 모두 `#include <stack>` 추가.

```cpp
// raycaster.cc — 변경 후
void intersect(BaseID actor_id, const Raycaster& raycaster,
               std::vector<RayIntersectionResult>& intersects, bool recursive) {
  std::stack<BaseID> stack;
  stack.push(actor_id);
  while (!stack.empty()) {
    BaseID const current = stack.top();
    stack.pop();
    if (Actor* actor = Context::get().getObjectFactory()->get<Actor>(current)) {
      actor->raycast(raycaster, intersects);
      if (recursive) {
        for (BaseID const child : actor->getChildren()) {
          stack.push(child);
        }
      }
    }
  }
}
```

```cpp
// actor_exporter.cc — 변경 후
void ActorExporter::traverseActor(Actor* root) {
  std::stack<Actor*> stack;
  stack.push(root);
  while (!stack.empty()) {
    Actor* actor = stack.top();
    stack.pop();
    BaseID const actor_id = actor->getBaseID();
    if (index_maps_.actors.find(actor_id) != index_maps_.actors.end()) {
      continue;  // 이미 수집됨 (사이클 방지)
    }
    vsize const node_index = collected_actors_.size();
    index_maps_.actors[actor_id] = node_index;
    collected_actors_.push_back(actor_id);
    if (actor->isA<Mesh>()) { collectMesh(static_cast<Mesh*>(actor)); }
    if (actor->isA<Camera>()) { collectCamera(static_cast<Camera*>(actor)); }
    if (actor->isA<Light>()) { collectLight(static_cast<Light*>(actor)); }
    // 자식을 역순으로 push → pop 순서가 원본 재귀와 동일한 DFS 순서 유지
    std::vector<BaseID> const children = actor->getChildren();
    for (auto it = children.rbegin(); it != children.rend(); ++it) {
      Actor* child = Engine::get<Actor>(*it);
      if (child) { stack.push(child); }
    }
  }
}
```

> **탐색 순서**: `std::stack`은 LIFO이므로 자식을 순서대로 push하면 마지막 자식부터 처리된다.  
> 원본 재귀 버전의 DFS 순서(첫 번째 자식 먼저)를 유지하려면 자식을 **역순으로 push**해야 함.  
> glTF 노드 인덱스 배치가 원본과 동일하게 유지된다.

---

### A-14. 중복 분기 본문 (확인됨)
**도구**: Clang-Tidy `bugprone-branch-clone`  
**위치**: `joint_component.cc:190`

```cpp
// 실제 코드 (joint_component.cc:190)
if (type_ == JointType::kFixed) {
    // 빈 본문
} else if (type_ == JointType::kPoint) {
    // 빈 본문 — kFixed와 동일(둘 다 비어있어 branch-clone 경고)
} else if (type_ == JointType::kDistance) {
    // 실제 파라미터 업데이트 코드
```

A-2(`vehicle_component.cc:144`)는 실제 복붙 버그였으나, 이 경우는 `kFixed`/`kPoint` 조인트에 런타임 업데이트 파라미터가 없어 의도적 빈 분기.

**수정**: 두 빈 분기를 `||` 조건으로 합쳐 `branch-clone` 경고 제거 + 의도 명시:
```cpp
if (type_ == JointType::kFixed || type_ == JointType::kPoint) {
  // No runtime parameters to update for fixed/point joints
} else if (type_ == JointType::kDistance) {
    // 실제 파라미터 업데이트 코드
```

---

## 4. B등급 — 타입/안전성 문제

### B-1. 암묵적 정수 축소 변환 (Narrowing Conversion, 확인됨)
**도구**: Clang-Tidy `bugprone-narrowing-conversions`  
**건수**: 약 15건

패턴별로 정리:

**① `BaseID → int32_t` (반복 패턴, 3건 이상)**
```cpp
// text.cc:175, skeleton.cc:35, asset_loader.cc:272 — 동일 패턴
Entity::import(font)     // font는 BaseID(uint32_t 추정) → int32_t로 변환
Entity::import(joint_id)
Entity::import(id)
```
`BaseID`가 `uint32_t`라면 상위 비트가 1인 경우 `int32_t`로 변환 시 음수로 읽힘. 여러 파일에 걸쳐 반복되므로 `Entity::import` 시그니처 또는 `BaseID` 타입 자체를 검토해서 통일하는 것이 근본 해결책.

**② `size_t → float` 정밀도 손실**
```cpp
// view_impl.cc:1178
vfloat v = i;   // i는 size_t(64비트) → float(32비트), 대형 값에서 정밀도 손실

// catmull_rom_curve.cc:63
const vfloat p = (l - (closed_ ? 0 : 1)) * t;  // l은 size_t → float 변환
```

**③ `ptrdiff_t → int32` 포인터 차이 축소**
```cpp
// asset_loader.cc:330
vint skin_index = node.skin - &src_asset->skins[0];  // 포인터 차이는 ptrdiff_t → vint32
```
씬에 스킨이 매우 많아지면 범위 초과 가능.

**④ `double → float` (cgltf 카메라 파라미터)**
```cpp
// asset_loader.cc (A-6 리팩터링 후 행 번호 이동 — 현재 994번)
const cgltf_float yfov_degrees =
    180.0 / glm::pi<vfloat>() * projection.yfov;
//  ^^^^^ double 리터럴 → cgltf_float(float)로 저장
```
```cpp
// 수정: 리터럴을 float로
const cgltf_float yfov_degrees =
    180.0f / glm::pi<vfloat>() * projection.yfov;
```
> **수정 시 특이사항**: 이전 세션 요약에서 "977번 setIntensity(light->intensity) — double→float"로 기록됐으나 실제 확인 결과 `cgltf_float = float`이므로 오탐. 진짜 double→float는 카메라 파라미터 코드(994번)였고 A-6 리팩터링으로 행 번호가 이동한 것. 수정 완료.

**⑤ `size_t → int32` 카운트 변환**
```cpp
// custom_material_component.cc:43
vint count = material_->getParameterCount();  // size_t 반환 → vint(int32) 축소
```
```cpp
// 수정
vint count = static_cast<vint>(material_->getParameterCount());
```

**⑥ `size_t → float` (catmull_rom_curve.cc:63)**
```cpp
const vfloat p = (l - (closed_ ? 0 : 1)) * t;  // l은 size_t → float 암묵적 변환
```
```cpp
// 수정
const vfloat p = static_cast<vfloat>(l - (closed_ ? 0u : 1u)) * t;
```

**공통 수정 방향**: `static_cast`를 명시하거나, `BaseID` → `Entity::import` 타입 체인 전체를 unsigned로 통일.

---

### B-2. 정수 곱셈 결과 암묵적 확장 (확인됨)
**도구**: Clang-Tidy `bugprone-implicit-widening-of-multiplication-result`  
**위치**: `typesetter.cc:79, 249, 250`

```cpp
// typesetter.cc:79 — PixelBufferDescriptor에 크기로 전달
filament::backend::PixelBufferDescriptor buffer(
    pixels, width * height,   // width, height 둘 다 vint32 → 곱셈 결과도 int32
    ...);                     // 인자 타입이 size_t이면 오버플로 후 확장

// typesetter.cc:249,250 — 버퍼 할당 및 초기화
vbyte* pixels = new vbyte[width * height];   // int32 곱셈 → size_t로 확장
memset(pixels, 0, width * height);           // 동일
```

`width * height`가 `int32` 범위에서 먼저 계산됨. 큰 텍스트(예: 2000×2000)면 `4,000,000`으로 `int32` 범위 내지만 더 커지면 오버플로 → 잘못된 크기로 할당.

```cpp
// 수정: 한쪽을 vsize로 캐스트해서 곱셈 전에 확장
vbyte* pixels = new vbyte[static_cast<vsize>(width) * height];
memset(pixels, 0, static_cast<vsize>(width) * height);
```

---

### B-3. `reinterpret_cast` 사용 (확인됨)
**도구**: Clang-Tidy `cppcoreguidelines-pro-type-reinterpret-cast`  
**건수**: 9건  
**위치**: `typesetter.cc:82`, `asset_loader.cc:145,317,402,403,406,408,1221`, `custom_material_provider.cc:46`

세 가지 패턴으로 분류되며 위험도가 다름:

---

**패턴 A — `void*` ↔ 타입 포인터 (C API 경계)**
```cpp
// asset_loader.cc:402,406 — cgltf 버퍼 접근
reinterpret_cast<const vuint8*>(timeline_accessor->buffer_view->data)
// cgltf_buffer_view::data 가 void* → 불가피

// typesetter.cc:82 — filament PixelBufferDescriptor 해제 콜백
[](void* data, vsize, void*) {
    delete[] reinterpret_cast<vbyte*>(data);  // void*로 받아서 원래 타입 복원
}
```
C API 설계 상 `void*`로 넘어오는 데이터를 복원하는 것. 완전히 피할 방법 없음. **실질 위험도: 낮음**

---

**패턴 B — 바이트 버퍼 → 구조체 포인터 (binary data 해석)**
```cpp
// asset_loader.cc:145 — gltf 스키닝 가중치
glm::vec4* weights = reinterpret_cast<glm::vec4*>(bytes);  // uint8* → vec4*

// asset_loader.cc:403,408 — 애니메이션 타임라인
reinterpret_cast<const vfloat*>(timeline_blob + offset)    // uint8* → float*

// asset_loader.cc (A-6 이후 행 이동 — 현재 1237번) — filament LinearColor
*reinterpret_cast<const filament::LinearColor*>(attenuation_color)
```
gltf 바이너리는 메모리상 float 배열로 들어있어 C++ 구조체로 재해석. 기술적으로 **strict aliasing 위반(UB)** 이지만 MSVC/GCC/Clang 모두 실제로는 올바르게 동작. cgltf 라이브러리 자체도 같은 방식으로 설계됨.

표준을 엄격히 따르려면 `memcpy`로 대체:
```cpp
// reinterpret_cast 대신
glm::vec4 weights;
memcpy(&weights, bytes, sizeof(glm::vec4));  // 표준 준수, 컴파일러도 최적화함
```
단, 포인터가 아닌 값이 필요한 경우에만 적용 가능. **실질 위험도: 기술적 UB이나 실용적으로 안전**

> **수정 시 특이사항 (LinearColor)**: `attenuation_color`는 인덱스로 접근 가능한 `const vfloat*`이므로 reinterpret_cast 없이 명시적 생성이 가능. NOLINT 대신 실제 수정 적용:
> ```cpp
> // 수정 — reinterpret_cast 완전 제거
> const filament::LinearColor attenuation_color_lc{
>     attenuation_color[0], attenuation_color[1], attenuation_color[2]};
> filament::Color::absorptionAtDistance(attenuation_color_lc, attenuation_distance);
> ```

---

**패턴 C — typed* ↔ `char*`/`uint8_t*` (표준 API 인터페이스)**
```cpp
// custom_material_provider.cc:46 — 파일 읽기
file.read(reinterpret_cast<char*>(buffer.data()), size)  // uint8_t* → char*

// asset_loader.cc:317 — memcpy 대상
memcpy(reinterpret_cast<vuint8*>(inverse_bind_matrices.data()), src, size)
```
`std::istream::read()`가 `char*`를 요구하는 C++ 표준 API 설계 때문. `char*`/`unsigned char*` ↔ 다른 포인터 변환은 C++ 표준에서 **명시적으로 허용된 예외** (aliasing rule). **실질 위험도: 없음**

---

**처리 방침 요약**

| 패턴 | 건수 | 위험도 | 처리 |
|------|------|--------|------|
| A: `void*` 변환 | 3건 | 낮음 | NOLINT |
| B: 바이트→구조체 타입 펀닝 | 5건 | 기술적 UB | 이상적으론 `memcpy`, 현실적으론 NOLINT |
| C: `uint8_t*`↔`char*` | 1건 | 없음 | NOLINT |

```cpp
// 일괄 처리 예시
reinterpret_cast<glm::vec4*>(bytes);  // NOLINT(cppcoreguidelines-pro-type-reinterpret-cast)
```

---

### B-4. `const_cast` — 문자열 리터럴에 적용 (확인됨, 위험)
**도구**: Clang-Tidy `cppcoreguidelines-pro-type-const-cast`  
**위치**: `asset_loader.cc:35`

```cpp
static const cgltf_material kDefaultMat = {
    const_cast<vchar*>("Default GLTF material"),  // 문자열 리터럴의 const 제거
    ...
};
```

`cgltf_material.name`이 `char*`(non-const)를 요구하기 때문에 `const_cast`로 우회. 문자열 리터럴은 읽기 전용 메모리에 저장되므로 만약 cgltf 내부에서 `name`에 쓰기 시도 시 UB(크래시).

```cpp
// 수정: 배열에 복사해서 사용
static vchar kDefaultMatName[] = "Default GLTF material";
static const cgltf_material kDefaultMat = { kDefaultMatName, ... };
```

---

### B-5. `StringView::data()` null-termination 미보장 (확인됨)
**도구**: Clang-Tidy `bugprone-suspicious-stringview-data-usage`  
**위치**: `asset_loader.cc:523`

```cpp
for (StringView uri : resource_uris) {
    asset->resource_uris_.push_back(uri.data());  // data()는 null 종결 미보장
}
```

`StringView::data()`는 `const char*`를 반환하지만 null 종결 문자(`\0`)를 보장하지 않음. `resource_uris_`에 저장된 포인터를 나중에 C 문자열로 사용하면 오버런 위험. 또한 `uri`가 루프 스코프 내 임시 객체라면 포인터가 댕글링될 수 있음.

```cpp
// 수정: size를 명시해서 null 종단 없이도 안전하게 std::string 생성
// + D-2(emplace_back) 동시 적용
asset->resource_uris_.emplace_back(uri.data(), uri.size());
```

> **수정 시 특이사항**: 문서상 수정 예시는 `push_back(std::string(uri))` 였으나, D-2(`push_back → emplace_back`) 개선과 합쳐 `emplace_back(uri.data(), uri.size())`로 수정. `uri.size()`를 명시해 null 종단 불필요 + 임시 객체 없이 직접 생성.

---

### B-6. C 스타일 캐스트 사용 (확인됨)
**도구**: Clang-Tidy `google-readability-casting`  
**건수**: 19건  
**파일별**: `extended_material_component.cc`(16건), `ktx2_reader.cc`(2건), `actor_exporter.cc`(1건)

```cpp
// extended_material_component.cc — 22,25,31,38,45,52,59,66,73,80,87,94,101,108,117,125번 줄
retval[key->baseColorUV] = (UvSet) index++;   // 변경 전

// ktx2_reader.cc:681 (2건) — const void* → vuint8* C 스타일 캐스트
Buffer ktx2content((vuint8*)data, (vuint8*)data + size);  // 변경 전

// actor_exporter.cc:2793 — void*로의 불필요한 캐스트 (이미 void*)
<< (void*)data_->buffers[0].data   // 변경 전
```

**수정 후**:
```cpp
// extended_material_component.cc — replace_all로 일괄 수정
retval[key->baseColorUV] = static_cast<UvSet>(index++);

// ktx2_reader.cc:681 — const 유지하며 명시적 변환
const vuint8* const data_bytes = static_cast<const vuint8*>(data);
Buffer ktx2content(data_bytes, data_bytes + size);

// actor_exporter.cc:2793 — 불필요한 캐스트 제거
<< data_->buffers[0].data
```

---

### B-7. 정수 → 포인터 변환 최적화 저해 (확인됨)
**도구**: Clang-Tidy `performance-no-int-to-ptr`  
**건수**: 6건  
**위치**: `scene_impl.cc:540`, `physics_context.cc:140,141,175,176`, `vehicle_component.cc:1081`

```cpp
// 실제 패턴 — Jolt Physics GetUserData() → vuint64 → RigidBody* 복원
vuint64 const userdata = body_interface.GetUserData(body_id);
RigidBody* body_data = reinterpret_cast<RigidBody*>(userdata);  // 경고 발생
```

Jolt Physics `BodyInterface::SetUserData()`가 `uint64_t`로 포인터를 저장, `GetUserData()`로 정수를 돌려받아 다시 포인터로 복원하는 API 패턴. 라이브러리 설계 제약으로 변경 불가.

**처리**: NOLINT 억제 (6곳 적용):
```cpp
RigidBody* body_data = reinterpret_cast<RigidBody*>(userdata);  // NOLINT(performance-no-int-to-ptr)
```

---

### B-8. 다중 포인터 암묵적 변환 (확인됨)
**도구**: Clang-Tidy `bugprone-multi-level-implicit-pointer-conversion`  
**건수**: 4건  
**위치**: `actor_exporter.cc:103`, `114`, `893`, `2694`

```cpp
// actor_exporter.cc:103 — cgltf_node** → void* (skins joints 해제)
free(data_->skins[i].joints);           // 변경 전

// actor_exporter.cc:114,893,2694 — char** → void* (extensions_used 해제)
free(const_cast<char**>(data_->extensions_used));  // 변경 전
```

cgltf C API가 `free(void*)` 호출로 내부 배열을 해제하는 패턴. `T**` → `void*` 변환을 명시적으로 표현.

**수정**:
```cpp
// 명시적 static_cast<void*> 추가 (F-6 NOLINT도 함께 처리)
free(static_cast<void*>(data_->skins[i].joints));                          // NOLINT(cppcoreguidelines-no-malloc)
free(static_cast<void*>(const_cast<char**>(data_->extensions_used)));      // NOLINT(cppcoreguidelines-no-malloc)
```

---

### B-9. C 가변 인자 함수 사용 (확인됨)
**도구**: Clang-Tidy `cppcoreguidelines-pro-type-vararg`  
**건수**: 2건  
**위치**: `collider_component.cc:168`, `ibl.cc:194`

```cpp
// ibl.cc:194 — A-11과 동일 위치 (NOLINT 처리 완료)
sscanf(line.c_str(), "(%f,%f,%f)", ...);  // NOLINT(cert-err34-c) 처리됨

// collider_component.cc:168 — snprintf로 에러 메시지 포매팅
vchar text[1024];
snprintf(text, sizeof(text), "CreateRigidBodyShape failed, shape_result: %s",
         shape_result.GetError().c_str());
utils::slog.e << text;
```

**수정**:
- `ibl.cc:194` — A-11에서 NOLINT 처리 완료.
- `collider_component.cc:168` — `slog`가 `<<` 체이닝을 지원하므로 중간 버퍼 제거:
```cpp
utils::slog.e << "CreateRigidBodyShape failed, shape_result: "
              << shape_result.GetError().c_str();
```

---

## 5. C등급 — 코드 설계 문제

### C-1. 인접한 동일 타입 파라미터 (인자 순서 실수 위험, 확인됨)
**도구**: Clang-Tidy `bugprone-easily-swappable-parameters`  
**건수**: 6건

```cpp
// controls.cc:8
void Controls::setViewport(vint width, vint height)

// orbit_controls.cc:27
void OrbitControls::grabBegin(vint x, vint y, vint button)

// orbit_controls.cc:414
void OrbitControls::_handleMouseWheel(vfloat delta_y, vint x, vint y)

// orbit_controls.cc:426
void OrbitControls::_updateZoomParameters(vint x, vint y)

// catmull_rom_curve.cc:15 — 가장 위험, 7개 vfloat
void initNonuniformCatmullRom(vfloat x0, vfloat x1, vfloat x2, vfloat x3,
                              vfloat dt0, vfloat dt1, vfloat dt2)

// skeleton.cc:32 — vsize vs BaseID, 타입이 달라 실질 위험 낮음
void Skeleton::setJoint(vsize bone_index, BaseID joint_id)
```

| 케이스 | 위험도 | 실제 조치 |
|--------|--------|----------|
| `initNonuniformCatmullRom` 7개 `vfloat` | 높음 | `NonuniformParams` 구조체 도입 — 수정 완료 |
| `_handleMouseWheel`, `_updateZoomParameters` (private) | 중간 | `glm::ivec2 pos`로 묶음 — 수정 완료 |
| `Controls::setViewport`, `grabBegin` (공개 virtual API) | 중간 | NOLINT — 시그니처 변경 시 외부 사용자 코드 파손 |
| `Raycaster::setViewport` (공개 API) | 중간 | NOLINT — 동일 이유 |
| `setJoint(vsize, BaseID)` | 낮음 (타입 다름) | 조치 불필요 (타입이 달라 컴파일러가 잡음) |

```cpp
// private 메서드 — 실제 수정 완료
void _handleMouseWheel(vfloat delta_y, glm::ivec2 pos);  // orbit_controls.h
void _updateZoomParameters(glm::ivec2 pos);

// 호출부 (orbit_controls.cc)
_handleMouseWheel(-scroll_delta * 100.0f, {x, y});
_updateZoomParameters({x, y});

// initNonuniformCatmullRom — 실제 수정 완료 (catmull_rom_curve.cc)
struct NonuniformParams { vfloat x0, x1, x2, x3; vfloat dt0, dt1, dt2; };
void initNonuniformCatmullRom(const NonuniformParams& p);
// 호출부
px.initNonuniformCatmullRom({p0.x, p1.x, p2.x, p3.x, dt0, dt1, dt2});

// 공개 API — NOLINT 처리 (controls.h, raycaster.h)
void setViewport(vint width, vint height);  // NOLINT(bugprone-easily-swappable-parameters)
virtual void grabBegin(vint x, vint y, vint button) = 0;  // NOLINT(bugprone-easily-swappable-parameters)
```

> **수정 시 특이사항**: 문서 권장 조치는 `grabBegin`을 포함한 모든 좌표 쌍을 `glm::ivec2`로 변경하는 것이었으나, `grabBegin`은 가상 함수(base + 3개 override)이고 라이브러리 공개 API이므로 외부 호출자 코드가 깨짐. 공개 API는 NOLINT, private 메서드만 실제 수정 적용.

---

### C-2. Rule of Five 미준수 (확인됨)
**도구**: Clang-Tidy `cppcoreguidelines-special-member-functions`  
**위치**: `vehicle_component.cc:32` (`VehicleData`)

> **Rule of Five란?**  
> C++ 클래스가 소멸자(`~T`), 복사 생성자(`T(const T&)`), 복사 대입(`operator=(const T&)`) 중 하나라도 직접 정의하면, 나머지 4개와 이동 생성자(`T(T&&)`) + 이동 대입(`operator=(T&&)`)까지 총 5개를 모두 명시적으로 선언해야 한다는 규칙.  
> 이유: 컴파일러 자동 생성 버전(default)은 단순 포인터 복사(얕은 복사)를 수행하므로, raw pointer를 직접 소유하는 클래스에서 **이중 해제(double free)** 또는 **댕글링 포인터**가 발생한다.

```cpp
struct VehicleData {
  PhysicsContext* physics_context = nullptr;
  JPH::VehicleConstraint* vehicle_constraint = nullptr;

  void cleanUp() {
    // vehicle_constraint를 physics_system에서 제거 후 nullptr 세팅
    physics_context->physics_system.RemoveStepListener(vehicle_constraint);
    physics_context->physics_system.RemoveConstraint(vehicle_constraint);
    vehicle_constraint = nullptr;
  }

  ~VehicleData() { cleanUp(); }
  // 복사 생성자, 복사 대입, 이동 생성자, 이동 대입 — 없음
};
```

소멸자에서 `vehicle_constraint`를 physics system에서 직접 제거하는 리소스 관리 구조체. 기본 복사 시 두 복사본이 같은 포인터를 가지고, 하나가 소멸될 때 `RemoveConstraint`로 제거되면 나머지 복사본은 이미 제거된 constraint를 가리켜 이중 해제 또는 댕글링 포인터 발생.

```cpp
// 수정 — 복사 금지, 이동만 허용 (소유권 이전 의미)
struct VehicleData {
  VehicleData() = default;
  ~VehicleData() { cleanUp(); }

  VehicleData(const VehicleData&) = delete;
  VehicleData& operator=(const VehicleData&) = delete;
  VehicleData(VehicleData&&) = default;
  VehicleData& operator=(VehicleData&&) = default;
  // ...
};
```

> **추가 확인된 Rule of Five 미준수** (Clang-Tidy v3, `cppcoreguidelines-special-member-functions`)
> - `ktx2_provider.cc:20` — `Ktx2Provider`: 소멸자 정의, 복사/이동 연산자 4개 없음
> - `ktx2_reader.cc:468` — `FAsync`: 소멸자 정의, 복사/이동 연산자 4개 없음 (→ C-6 `virtual-class-destructor` 참고)
> - `joint_component.cc:23` — `Constraint`: 소멸자 정의, 복사/이동 연산자 4개 없음
>
> 세 클래스 모두 리소스를 소유하거나 물리 시스템과 연결된 구조이므로, `VehicleData`와 동일하게 복사 `= delete` + 이동 `= default` 명시 적용 필요.

---

### C-3. Rule of Three 미준수 (확인됨)
**도구**: Cppcheck `noCopyConstructor / noOperatorEq`  
**위치**: `resource_manager.cc:54`

> **Rule of Three란?**  
> C++03 시절의 규칙. 소멸자, 복사 생성자, 복사 대입 연산자 중 하나를 정의했다면 나머지 두 개도 반드시 정의해야 한다.  
> C++11 이후 이동 연산 두 개가 추가되어 Rule of Five로 확장됨. Rule of Three를 위반하면 컴파일러가 생성한 얕은 복사본이 같은 raw pointer를 두 곳에서 동시에 소유하게 되어 이중 해제 위험이 생긴다.  
> `= delete`로 복사 자체를 막는 것도 Rule of Three/Five를 "명시적으로 지킨 것"으로 인정한다.

```cpp
// 소멸자에서 raw pointer 직접 해제
ResourceManager::~ResourceManager() {
  // ...
  delete stb_decoder_;   // raw pointer 소유
  delete ktx_decoder_;   // raw pointer 소유
}
// 복사 생성자, 복사 대입 연산자 없음
```

`stb_decoder_`, `ktx_decoder_`를 직접 소유하는데 복사 시 포인터만 복사되어 이중 해제 위험. `ResourceManager`는 전역 singleton 성격이므로 복사 자체를 막는 것이 맞음.

```cpp
// 수정
ResourceManager(const ResourceManager&) = delete;
ResourceManager& operator=(const ResourceManager&) = delete;
```

---

### C-4. `virtual` + `override` 중복 지정 (확인됨)
**도구**: Clang-Tidy `modernize-use-override`  
**위치**: `context.cc:67`

```cpp
// 변경 전
virtual VulkanPlatform::Customization getCustomization()
    const noexcept override {
  return customization_;
}

// 변경 후 — virtual 제거, override 하나로 충분
VulkanPlatform::Customization getCustomization()
    const noexcept override {
  return customization_;
}
```

`override`가 이미 "이 함수는 가상 함수다"를 내포함. `virtual`을 함께 쓰는 건 관습적 잔재.

---

### C-5. 네이밍 컨벤션 불일치 (확인됨)
**도구**: Clang-Tidy `readability-identifier-naming`  
**위치**: `capsule_geometry.cc:9,10,11`

```cpp
// 변경 전 — camelCase
CapsuleGeometry* CapsuleGeometry::create(const String& name, vfloat radius,
                                         vfloat height, vint capSegments,
                                         vint radialSegments,
                                         vint heightSegments)

// 변경 후 — 프로젝트 컨벤션 lower_case
CapsuleGeometry* CapsuleGeometry::create(const String& name, vfloat radius,
                                         vfloat height, vint cap_segments,
                                         vint radial_segments,
                                         vint height_segments)
```

헤더와 호출부도 함께 수정 필요.

> **수정 시 특이사항**: 문서에는 `capsule_geometry.cc`와 헤더(`capsule_geometry.h`)만 언급됐으나, 실제 수정 시 `createCapsuleGeometry` 구현 체인도 파라미터 이름을 통일해야 했음. 총 4개 파일 수정:
> - `capsule_geometry.h` — public API 선언, 주석
> - `capsule_geometry.cc` — 구현
> - `object_factory.h` — `createCapsuleGeometry` 선언
> - `object_factory.cc` — `createCapsuleGeometry` 구현 + `geometries::Capsule` 생성자 인자

---

### C-6. `virtual` 소멸자가 `protected` — 접근 제어 불명확 (확인됨)
**도구**: Clang-Tidy `cppcoreguidelines-virtual-class-destructor`  
**위치**: `ktx2_reader.cc:468` (`FAsync`)

```cpp
class FAsync {
protected:
  virtual ~FAsync() { ... }   // ← protected virtual 소멸자
  // 복사/이동 연산자 없음 (C-2 참고: Rule of Five 미준수)
};
```

C++ Core Guidelines: 다형성 기반 클래스의 소멸자는 **`public virtual`** 이거나 **`protected non-virtual`** 이어야 함.
- `public virtual`: 기반 클래스 포인터를 통해 안전하게 `delete` 가능
- `protected non-virtual`: 기반 클래스 포인터로 직접 삭제를 컴파일 타임에 차단 (파생 클래스만 삭제 가능)

현재 `protected virtual` 조합은 두 방식의 의도가 섞여 불명확. Jolt Physics 연동 코드에서 `FAsync`가 비동기 작업 기반 클래스로 사용되는 패턴이라면 `public virtual`로 변경이 적합.

**처리**: NOLINT 억제 (`ktx2_reader.h:154`)

`Ktx2Reader`가 `friend`로 선언되어 유일한 삭제 경로(`asyncDestroy`)를 가지는 factory 패턴. `protected`로 외부 직접 삭제를 차단하고 `virtual`로 `FAsync::~FAsync()` 호출을 보장하는 의도적 설계이므로 `public virtual` 변경보다 NOLINT가 적합.

```cpp
virtual ~Async();  // NOLINT(cppcoreguidelines-virtual-class-destructor)
```

---

## 6. D등급 — 성능 / 스타일 개선

### D-1. `std::endl` → `'\n'` (확인됨)
**도구**: Clang-Tidy `performance-avoid-endl`  
**건수**: 5건  
**위치**: `custom_material_provider.cc:32, 39, 48, 59, 69`

```cpp
// 현재 코드 (5군데 동일 패턴)
std::cerr << "CustomMaterialProvider: Failed to open file: "
          << filepath << std::endl;   // flush() 강제 호출

std::cerr << "CustomMaterialProvider: Invalid package data" << std::endl;

std::cerr << "CustomMaterialProvider: Material::Builder failed"
          << std::endl;
```

`std::endl` = `'\n'` + `std::flush`. 에러 로그라서 `flush`가 필요해 보이지만, `std::cerr`는 기본적으로 **unbuffered** — 즉 이미 즉시 출력되므로 명시적 `flush`가 불필요. 빈번한 로그 경로에서 `flush` 오버헤드 발생.

```cpp
// 수정 — '\n'으로 교체 (cerr는 unbuffered라 flush 불필요)
std::cerr << "CustomMaterialProvider: Failed to open file: "
          << filepath << '\n';
```

`clang-tidy --fix`로 자동 일괄 수정 가능.

---

### D-2. `push_back(T(...))` → `emplace_back(...)` (확인됨)
**도구**: Clang-Tidy `modernize-use-emplace`  
**위치**: `asset_loader.cc:523`

```cpp
// 현재 코드
for (StringView uri : resource_uris) {
  asset->resource_uris_.push_back(uri.data());  // uri.data()로 임시 std::string 생성 후 push
}

// 수정 — B-5(null 종단 미보장)와 동시 적용
for (StringView uri : resource_uris) {
  asset->resource_uris_.emplace_back(uri.data(), uri.size());  // 직접 생성 + 길이 명시
}
```

`push_back`은 임시 `std::string` 객체를 먼저 만든 후 이동. `emplace_back`은 생성자 인자를 전달해 컨테이너 내부에서 직접 생성하므로 이동 1회 절감.

> **수정 시 특이사항**: B-5(`uri.data()` null 종단 미보장) 이슈와 합쳐 `emplace_back(uri.data(), uri.size())`로 수정 완료. `uri.size()`를 명시해 null 종단 없이도 올바른 길이로 `std::string`이 생성됨. (B-5 섹션 참고)

---

### D-3. 빈 소멸자 `= default` 대체 가능 (확인됨)
**도구**: Clang-Tidy `modernize-use-equals-default`  
**위치**: `swing_twist_joint.cc:19`, `point_joint.cc:19`

```cpp
// 현재 — swing_twist_joint.cc:19
SwingTwistJoint::~SwingTwistJoint() {
}

// 현재 — point_joint.cc:19
PointJoint::~PointJoint() {
}
```

```cpp
// 수정 — 두 파일 동일 패턴
SwingTwistJoint::~SwingTwistJoint() = default;
PointJoint::~PointJoint() = default;
```

빈 소멸자 본문은 컴파일러가 trivial destructor로 처리하지 못함. `= default` 선언 시 trivial로 인식되어 인라인 최적화 및 타입 특성 추론(`std::is_trivially_destructible`)에 유리. `-fix`로 자동 수정 가능.

---

### D-4. `[[nodiscard]]` 누락 (확인됨)
**도구**: Clang-Tidy `modernize-use-nodiscard`  
**위치**: `catmull_rom_curve.cc:24`

```cpp
// 현재 코드
vfloat calc(vfloat t) const {
  const vfloat t2 = t * t;
  const vfloat t3 = t2 * t;
  return c0_ + c1_ * t + c2_ * t2 + c3_ * t3;
}

// 수정 — 반환값 무시 시 경고 발생
[[nodiscard]] vfloat calc(vfloat t) const {
  // ...
}
```

`calc`는 Catmull-Rom 스플라인 보간 계산 함수. 반환값을 사용하지 않으면 계산 결과가 버려지는 것이므로 호출자 실수를 컴파일 타임에 잡는 것이 바람직.

---

### D-5. boolean 식 단순화 (확인됨)
**도구**: Clang-Tidy `readability-simplify-boolean-expr`  
**위치**: `plane.cc:141`

```cpp
// 현재 코드 — 이중 부정 패턴
return !(uvw_difference.x > std::numeric_limits<vfloat>::epsilon() ||
         uvw_difference.y > std::numeric_limits<vfloat>::epsilon() ||
         uvw_difference.z > std::numeric_limits<vfloat>::epsilon());

// 수정 — DeMorgan 법칙 적용: !(A || B || C) == !A && !B && !C
return uvw_difference.x <= std::numeric_limits<vfloat>::epsilon() &&
       uvw_difference.y <= std::numeric_limits<vfloat>::epsilon() &&
       uvw_difference.z <= std::numeric_limits<vfloat>::epsilon();
```

의미는 동일하나 이중 부정 없이 더 직관적으로 읽힘.

---

### D-6. 빈 소멸자 `= default` 대체 — 추가 9건 (확인됨)
**도구**: Clang-Tidy `modernize-use-equals-default`  
**건수**: 9건 (D-3의 2건과 별개)  
**위치**: `fixed_joint.cc:19`, `sixdof_joint.cc:19`, `joint.cc:11`, `hinge_joint.cc:19`, `body.cc:12`, `slider_joint.cc:19`, `distance_joint.cc:18`, `vehicle.cc:13`, `cone_joint.cc:19`

D-3에서 `swing_twist_joint.cc`, `point_joint.cc` 2건 처리 완료. 조인트/바디 관련 파일 전반에 동일 패턴 9건 추가 확인.

```cpp
// 각 파일 동일 패턴
FixedJoint::~FixedJoint() {}  →  FixedJoint::~FixedJoint() = default;
SixDofJoint::~SixDofJoint() {}  →  SixDofJoint::~SixDofJoint() = default;
// ...
```

**수정 완료**: 9개 파일 모두 `= default` 적용.

> `= default` vs `{}` 차이 → [12_special_member_functions.md § 2](../c++/12_special_member_functions.md)

---

### D-7. `[[nodiscard]]` 누락 — 추가 5건 (확인됨)
**도구**: Clang-Tidy `modernize-use-nodiscard`  
**건수**: 5건 (D-4의 1건과 별개)  
**위치**: `ktx2_provider.cc:34,35,37,40,43`
- `getPushMessage()` (line 34)
- `getPopMessage()` (line 35)
- `getPushedCount()` (line 37)
- `getPoppedCount()` (line 40)
- `getDecodedCount()` (line 43)

KTX2 텍스처 스트리밍 큐의 상태 조회 함수들. 반환값을 사용하지 않으면 호출 자체가 의미 없음.

```cpp
// 수정 완료 (ktx2_provider.cc 로컬 클래스 선언부)
[[nodiscard]] const char* getPushMessage() const final;
[[nodiscard]] const char* getPopMessage() const final;
[[nodiscard]] vsize getPushedCount() const final;
[[nodiscard]] vsize getPoppedCount() const final;
[[nodiscard]] vsize getDecodedCount() const final;
```

---

### D-8. `override` 누락 (확인됨)
**도구**: Clang-Tidy `modernize-use-override`  
**건수**: 2건 (C-4의 1건과 별개)  
**위치**: `ktx2_provider.cc:24`, `ktx2_reader.cc:484`

두 위치 모두 파생 클래스 소멸자에 `override` 누락:

```cpp
// 수정 완료
// ktx2_provider.cc:24 — TextureProvider 상속
~Ktx2Provider() override;

// ktx2_reader.cc:484 — Async 상속
~FAsync() override;
```

---

### D-9. `new` 대신 `std::make_unique` 사용 (확인됨)
**도구**: Clang-Tidy `modernize-make-unique`  
**건수**: 1건  
**위치**: `ktx2_provider.cc:250`

```cpp
// 변경 전 (ktx2_provider.cc:250)
ktx_reader_.reset(new Ktx2Reader(*engine, quiet));

// 변경 후
ktx_reader_ = std::make_unique<Ktx2Reader>(*engine, quiet);
```

`make_unique`는 예외 안전성 향상(new와 생성자 호출 사이의 예외 누수 방지)과 코드 간결성을 동시에 제공.

---

### D-10. 값 파라미터 → `const` 참조로 변경 (확인됨)
**도구**: Clang-Tidy `performance-unnecessary-value-param`  
**건수**: 2건  
**위치**: `curve_path.cc:105` (`curve`), `ibl.cc:151` (`path`)

```cpp
// curve_path.cc:105 — shared_ptr 값 복사 → const 참조
void CurvePath::add(std::shared_ptr<Curve> curve)         // 변경 전
void CurvePath::add(const std::shared_ptr<Curve>& curve)  // 변경 후 (헤더 포함)

// ibl.cc:151 — 람다 파라미터 utils::Path 값 복사 → const 참조
auto create_ktx = [](utils::Path path)         // 변경 전
auto create_ktx = [](const utils::Path& path)  // 변경 후
```

함수 내에서 파라미터를 수정하지 않는 경우, `const&`로 받아 불필요한 복사 제거.

---

### D-11. enum 크기 최소화 (확인됨)
**도구**: Clang-Tidy `performance-enum-size`  
**건수**: 2건  
**위치**: `ktx2_provider.cc:48` (`QueueItemState`), `ktx2_provider.cc:55` (`TranscoderState`)

```cpp
// 변경 전 — 기본 타입 int(4바이트)
enum class QueueItemState { kTranscoding, kReady, kPopped };
enum class TranscoderState { kNotStarted, kError, kSuccess };

// 변경 후 — 값 범위에 맞는 최소 타입 (1바이트)
enum class QueueItemState : std::uint8_t { kTranscoding, kReady, kPopped };
enum class TranscoderState : std::uint8_t { kNotStarted, kError, kSuccess };
```

`QueueItem` 구조체 멤버로 쓰이며 (`std::atomic<TranscoderState>` 포함), 큐 아이템이 많이 생성될수록 절약 효과 커짐.

---

### D-12. boolean 식 단순화 — 추가 5건 (확인됨)
**도구**: Clang-Tidy `readability-simplify-boolean-expr`  
**건수**: 5건 (D-5의 1건과 별개)  
**위치**: `texture_component.cc:121`, `mesh_component.cc:448`, `rigidbody_component.cc:67`, `aabb.cc:110`, `hitbox_2d.cc:8`

두 가지 하위 패턴:

**① `== false` / if-return 단순화** (`texture_component.cc`, `mesh_component.cc`, `rigidbody_component.cc`):
```cpp
// texture_component.cc — if/return 패턴
if (progress < 1.0f) { return false; }
return true;
→ return progress >= 1.0f;

// mesh_component.cc — == false 비교
if (ray_local.intersects(bounding_box.value()) == false) continue;
→ if (!ray_local.intersects(bounding_box.value())) continue;

// rigidbody_component.cc — == false 비교
const bool refresh = physicsobject.body_id.IsInvalid() == false;
→ const bool refresh = !physicsobject.body_id.IsInvalid();
```

**② DeMorgan 전개** (`aabb.cc`, `hitbox_2d.cc`):
```cpp
// aabb.cc
return !(point.x > max.x || point.x < min.x || point.y > max.y ||
         point.y < min.y || point.z > max.z || point.z < min.z);
→ return point.x <= max.x && point.x >= min.x && point.y <= max.y &&
         point.y >= min.y && point.z <= max.z && point.z >= min.z;

// hitbox_2d.cc
return !(position.x + size.x < point.x || position.x > point.x || ...);
→ return position.x + size.x >= point.x && position.x <= point.x && ...;
```

---

### D-13. TODO 포맷 불일치 (확인됨)
**도구**: Clang-Tidy `google-readability-todo`  
**건수**: 6건  
**위치**: `ktx2_provider.cc:202`, `ktx2_reader.cc:744,753`, `joint_component.cc:144`, `rigidbody_component.cc:218,263`

```cpp
// 현재 — 담당자/버그 번호 없음
// TODO: 나중에 처리

// Google 스타일 가이드 권장 형식
// TODO(username): 설명
// TODO(b/123456): 버그 번호 포함 설명
```

코드 리뷰나 버그 추적 시 담당자 불명확. 팀 코딩 표준이 다르다면 `.clang-tidy`에서 `google-readability-todo`를 비활성화하는 것이 현실적.

**처리**: `.clang-tidy`에서 `-google-readability-todo` 추가로 비활성화. `google-*` 와일드카드로 포함되던 것을 명시적으로 제외.

---

### D-14. 미사용 파라미터 (확인됨)
**도구**: Clang-Tidy `misc-unused-parameters`  
**건수**: 17건  
**파일별**:

| 파일 | 줄 | 파라미터 | 건수 |
|------|-----|---------|------|
| `line_curve.cc` | 25 | `t` | 1 |
| `scene_impl.cc` | 1128,1313,1370 | `js`, `parent`(×3) | 4 |
| `physics_context.cc` | 110,111 | `in_manifold`, `io_settings` | 2 |
| `ktx2_provider.cc` | 82 | `mime_type` | 1 |
| `ktx2_reader.cc` | 147 | `userdata` | 1 |
| `actor_exporter.cc` | 2360 | `tex` | 1 |
| `first_person_controls.cc` | 13 | `x`, `y` | 2 |
| `custom_material_component.cc` | 127 | `modulate` | 1 |
| `body.cc` | 254 | `value` | 1 |
| `instance_manager.cc` | 354 | `buffer`, `size` | 2 |
| `custom_material_provider.cc` | 116 | `name` | 1 |

두 가지 원인:
1. **가상 함수 오버라이드** — 기반 클래스 시그니처 유지를 위해 파라미터가 있어야 하지만 이 구현에서 사용 안 함 (`physics_context.cc`의 Jolt Physics 콜백 등)
2. **실제 미구현** — 기능이 추가 예정이거나 삭제 예정인 파라미터

**처리 완료**: 케이스별 분류 후 수정:

| 케이스 | 처리 |
|--------|------|
| 가상함수/콜백 고정 시그니처 (`line_curve`, `scene_impl`×3, `physics_context`×2, `ktx2_provider`, `ktx2_reader`, `first_person_controls`) | 파라미터 이름 `/*name*/` 제거 |
| 람다 콜백 (`instance_manager`) | `/*buffer*/`, `/*size*/` 제거 |
| 미래 기능 예약 (`custom_material_component`, `custom_material_provider`) | `/*modulate*/`, `/*name*/` 제거 |
| `actor_exporter::processTextureUri` — `tex` 사용 안 함 (줄 번호 이동) | `/*tex*/` 제거 |
| **버그 수정** `body.cc` — `setStartDeactivated(true)` 하드코딩 | `value` 전달로 수정 |

```cpp
// 이름 제거 패턴 예시
void OnContactAdded(const JPH::Body& in_body1, const JPH::Body& in_body2,
                    const JPH::ContactManifold& /*in_manifold*/,
                    JPH::ContactSettings& /*io_settings*/) override;

// 버그 수정 (body.cc)
rc->setStartDeactivated(value);  // 기존: true 하드코딩
```

---

## 7. E등급 — 대량 스타일 (기계적 적용 가능)

### E-1. `const` 선언 누락 (misc-const-correctness)
**건수**: 약 100건+ (추정 — 저장된 스캔 로그에 별도 집계 없음)  
**분포**: 거의 모든 파일에 걸쳐 분산

초기화 후 코드상 변경이 없는 지역 변수에 `const` 미선언. 컴파일러 최적화 힌트 및 코드 의도 명확화에 유리.

**⚠️ 중요 — 일괄 자동 수정 전 반드시 검토 필요**

이 체크는 "현재 코드에서 변경이 없다"는 기계적 판단이라, 의도적으로 `const`를 생략한 경우가 섞여 있을 수 있음:

| 상황 | const 안 한 이유 | 처리 방향 |
|------|-----------------|-----------|
| 루프 변수 `auto x = ...` — 나중에 수정 의도 | 설계상 non-const | 유지 |
| 외부 API에 non-const ref/pointer로 전달 필요 | 함수 시그니처 제약 | 유지 |
| 단순히 const를 쓰지 않은 습관 | 실수 | 추가 가능 |
| 임시 결과를 받아두고 최종 값만 읽음 | const 추가해도 무방 | 추가 권장 |

**일괄 적용 방법 (검토 후 적용)**:
```cmd
python "...\run-clang-tidy" ^
  -clang-tidy-binary "...\clang-tidy.exe" ^
  -p out/build/windows-msvc-x64-debug ^
  -fix -checks="-*,misc-const-correctness" ^
  ".*base\\src\\.*"
```

> **주의**: `-fix` 전 반드시 git branch 생성. 자동 수정 후 각 변경사항을 직접 검토하여 의도적 non-const를 되돌릴 것. `const`를 붙인 뒤 해당 변수를 수정하게 되면 코드를 다시 바꿔야 하는 번거로움이 생김.

---

## 8. F등급 — 인프라 패턴 (오탐/의도적 패턴)

아래는 실제 코드 확인 결과 모두 의도적 패턴으로 확인됨. NOLINT / suppress 처리 권장.

---

### F-1. `pro-bounds-pointer-arithmetic` (확인됨)
**도구**: Clang-Tidy  
**위치**: `asset_loader.cc:143~144` 외 전반

> **경고 설명**: "포인터에 직접 산술 연산(`+`, `-`, `[]`)하지 마라."  
> 포인터 산술은 범위 체크가 없어서 버퍼 범위를 벗어나도 컴파일러가 잡지 못함 → 런타임 크래시 또는 메모리 손상.  
> Core Guidelines 권장 대안은 `std::span` — 포인터와 크기를 묶어 범위를 보장.

```cpp
// cgltf 바이너리 버퍼 순회 — C API 스펙
vuint8* bytes = static_cast<vuint8*>(data->buffer_view->buffer->data);
bytes += data->offset + data->buffer_view->offset;   // 포인터 산술
for (cgltf_size i = 0, n = data->count; i < n; ++i, bytes += data->stride) {
  glm::vec4* weights = reinterpret_cast<glm::vec4*>(bytes);
  // ...
}
```

glTF 바이너리 포맷 자체가 "버퍼 + 오프셋 + 스트라이드"로 데이터를 기술하는 구조. cgltf C API는 이 포맷 그대로 `void*`와 정수 오프셋만 반환하므로, `std::span`으로 감싸려면 cgltf 전체를 래핑하는 수준의 작업이 필요 → 대안 없음. NOLINT 처리가 맞음.

```cpp
// 적용 완료 — asset_loader.cc 4곳
bytes += data->offset + data->buffer_view->offset;  // NOLINT(cppcoreguidelines-pro-bounds-pointer-arithmetic)
for (..., bytes += data->stride) {                  // NOLINT(cppcoreguidelines-pro-bounds-pointer-arithmetic)
src_buffer = bytes + src_matrices->offset;          // NOLINT(cppcoreguidelines-pro-bounds-pointer-arithmetic)
bytes + src_matrices->offset + ...->offset;         // NOLINT(cppcoreguidelines-pro-bounds-pointer-arithmetic)
```

> **처리**: 잔여 278건 전부 C API 경계(`cgltf`, `freetype`, `ktx2`) 파일에 집중. 우리 로직 코드에서는 포인터 산술을 쓸 이유가 없으므로 `.clang-tidy`에서 `cppcoreguidelines-pro-bounds-pointer-arithmetic` 체크 자체를 제거.

---

### F-2. `pro-bounds-array-to-pointer-decay` (확인됨)
**도구**: Clang-Tidy  
**위치**: `context.cc`, `asset_loader.cc`, `ktx2_reader.cc`, `ibl.cc`  
**총 건수**: 15건 (v4 기준)

> **경고 설명**: "C 배열이 포인터로 암묵 변환(decay)되는 것을 허용하지 마라."  
> C 배열 `T arr[]`을 함수에 넘기거나 포인터 연산에 쓰면 크기 정보가 소멸되어 `T*`가 됨.  
> 이후 배열 크기를 알 수 없으니 범위 초과 접근을 컴파일러가 잡지 못함.
> ```cpp
> void foo(const uint8_t* data);  // 크기 모름
> uint8_t arr[100];
> foo(arr);   // decay 발생 — arr의 100이라는 크기 정보 소멸
> ```

모든 경고가 C API 구조체 멤버 배열을 포인터로 전달하거나, Filament 자동생성 헤더 배열을 API에 넘기는 불가피한 패턴. NOLINT 처리.

**처리 완료 목록** (15건 전체):

| 파일 | 위치 | 내용 |
|------|------|------|
| `context.cc` | :216~217 | Filament 자동생성 `UBERARCHIVE_DEFAULT_DATA`, `BASE_MATERIALS_INSTANCED_DATA` → `createUbershaderProvider` 전달 |
| `asset_loader.cc` | :37 | `kDefaultMatName[]` → cgltf_material 구조체 초기화 |
| `asset_loader.cc` | :689 | `element_uint[4]` → `cgltf_accessor_read_uint` 전달 |
| `asset_loader.cc` | :849~851 | cgltf_node의 `translation[]`, `rotation[]`, `scale[]` 멤버 포인터 취득 |
| `asset_loader.cc` | :1117 | cgltf `base_color_factor[]` → BasicMaterial 설정 |
| `asset_loader.cc` | :1196 | cgltf `sheen_color_factor[]` → PBRMaterial 설정 |
| `asset_loader.cc` | :1235 | cgltf `attenuation_color[]` → PBRMaterial 설정 |
| `asset_loader.cc` | :1282 | cgltf `specular_color_factor[]` → PBRMaterial 설정 |
| `asset_loader.cc` | :1327 | cgltf `base_color_factor[]` → StandardMaterial 설정 |
| `ktx2_reader.cc` | :837 | `header->identifier[]` → `memcmp` 전달 (KTX2 바이너리 식별자 확인) |
| `ibl.cc` | :166 | `bands_[]` → `getSphericalHarmonics` 전달 |
| `ibl.cc` | :217 | `bands_[]` → Filament `.irradiance()` 전달 |

```cpp
// context.cc:216~217
materials_ = filament::gltfio::createUbershaderProvider(  // NOLINT(cppcoreguidelines-pro-bounds-array-to-pointer-decay)
    engine_, UBERARCHIVE_DEFAULT_DATA, ..., BASE_MATERIALS_INSTANCED_DATA, ...);  // NOLINT(...)

// asset_loader.cc:849~851
const cgltf_float* t = current->translation;  // NOLINT(cppcoreguidelines-pro-bounds-array-to-pointer-decay)
const cgltf_float* r = current->rotation;     // NOLINT(cppcoreguidelines-pro-bounds-array-to-pointer-decay)
const cgltf_float* s = current->scale;         // NOLINT(cppcoreguidelines-pro-bounds-array-to-pointer-decay)

// ibl.cc:217
.irradiance(3, bands_)  // NOLINT(cppcoreguidelines-pro-bounds-array-to-pointer-decay)
```

---

### F-3. `pro-type-reinterpret-cast` — cgltf 관련 (확인됨)
**도구**: Clang-Tidy  
**위치**: `asset_loader.cc:145` 외

> **경고 설명**: "`reinterpret_cast`를 쓰지 마라."  
> `reinterpret_cast`는 타입 시스템을 완전히 우회해 비트 패턴을 다른 타입으로 재해석함.  
> **엄격한 앨리어싱(strict aliasing) 규칙** 위반 시 UB 발생:
> ```cpp
> uint8_t* bytes = ...;
> glm::vec4* v = reinterpret_cast<glm::vec4*>(bytes);  // 컴파일러가 최적화 중 오동작 가능
> ```
> 안전한 대안은 `memcpy` — 타입 규칙을 우회하지 않고 바이트 단위로 복사:
> ```cpp
> glm::vec4 v;
> memcpy(&v, bytes, sizeof(v));  // UB 없음, 컴파일러가 최적화 가능
> ```

```cpp
// cgltf 바이너리 버퍼에서 특정 타입으로 해석
glm::vec4* weights = reinterpret_cast<glm::vec4*>(bytes);  // uint8_t* → glm::vec4*
```

cgltf가 `void*` 기반 버퍼를 제공하고 스트라이드 순회 후 타입을 직접 재해석하는 것이 공식 사용 패턴. `memcpy`로 교체하면 배열 전체 복사가 필요해 성능/코드량 모두 비현실적. NOLINT 처리가 맞음.

---

### F-4. `avoid-c-arrays` (확인됨)
**도구**: Clang-Tidy  
**위치**: `vehicle_component.cc:97~127`

> **경고 설명**: "C 스타일 배열(`T arr[]`, `T arr[N]`) 대신 `std::array` 또는 `std::vector`를 써라."  
> C 배열은 decay(F-2), 범위 체크 없음, 복사 불가 등 여러 함정이 있음.  
> `std::array<T, N>`은 크기를 타입에 포함하고, `at()` 범위 체크, 복사/이동 지원.
> ```cpp
> T arr[4];                     // C 배열 — 경고
> std::array<T, 4> arr;         // 권장
> ```

```cpp
// 로컬 초기화용 C 스타일 배열
const BaseID car_wheel_entities[] = {
    getWheelEntity(WheelPosition::kFrontLeft),
    getWheelEntity(WheelPosition::kFrontRight),
    getWheelEntity(WheelPosition::kRearLeft),
    getWheelEntity(WheelPosition::kRearRight),
};
const glm::vec3 car_wheel_scale[] = {
    {0.625f, 0.625f, 0.625f}, {0.625f, 0.625f, 0.625f},
    {0.7f,   0.7f,   0.7f},   {0.7f,   0.7f,   0.7f},
};
```

기술적으로는 `std::array<BaseID, 4>`로 교체 가능하지만, 이니셜라이저 목록을 그대로 쓸 수 있는 C 배열 패턴이 여기서 더 간결. 실질적 위험 없음.

> **수정 시 특이사항**: `std::array` 교체 대신 NOLINT 적용으로 결정. 두 함수(`simulateWheel`, `updateWheelPhysics`) 내 배열 10개 전체에 적용 완료.
> ```cpp
> const BaseID car_wheel_entities[] = {     // NOLINT(cppcoreguidelines-avoid-c-arrays)
> const BaseID motor_wheel_entities[] = {   // NOLINT(cppcoreguidelines-avoid-c-arrays)
> const glm::quat car_wheel_matrics[] = {  // NOLINT(cppcoreguidelines-avoid-c-arrays)
> const glm::quat mortor_wheel_matrics[] = { // NOLINT(...)
> const glm::vec3 car_wheel_scale[] = {    // NOLINT(...)  ← 첫 번째 함수에만 존재
> const glm::vec3 mortor_wheel_scale[] = { // NOLINT(...)  ← 첫 번째 함수에만 존재
> ```

> **잔여 27건 전체 처리 완료** (총 37건 → 0건 목표):
>
> | 파일 | 건수 | 처리 방법 |
> |------|------|-----------|
> | `geometry_component.cc` | 14건 | `unique_ptr<T[]>` 패턴 — Filament API에 `.release()` 포인터 전달하는 구조라 `std::vector` 교체 시 콜백도 변경 필요. NOLINT 적용 |
> | `aabb.cc` | 1건 | `const glm::vec4 corners[8]` → `std::array<glm::vec4, 8>` 교체 |
> | `mesh_component.cc` | 1건 | `glm::vec3 const corners[8]` → `std::array<glm::vec3, 8>` 교체 |
> | `view_impl.cc` | 1건 | `const IF kDepthFormats[4]` → `std::array<IF, 4>` 교체 |
> | `ibl.cc` | 1건 | `static const vchar* face_suffix[6]` → `std::array<const vchar*, 6>` 교체 |
> | `particles_component.cc` | 2건 | `Vertex kQuadVertices[4]`, `vuint16 kQuadIndices[6]` → `std::array` 교체 |
> | `ktx2_reader.cc` | 4건 | 상수 `kKtx2Identifier[12]` → `std::array<vuint8, 12>` 교체 + `.data()` 추가; 구조체 멤버 `identifier[12]` NOLINT (KTX2 바이너리 형식 매핑); 클래스 멤버 `transcoder_results_[KTX2_MAX_SUPPORTED_LEVEL_COUNT]` NOLINT (`std::atomic` non-movable 제약) |
> | `asset_loader.cc` | 2건 | `char kDefaultMatName[]` — cgltf API가 `char*` 요구; `element_uint[4]` — cgltf C API 전달. 두 건 모두 NOLINT |
> | `collider_component.cc` | 1건 | `triangle.mV[0]` — JPH::Triangle 구조체 멤버 접근 (배열 선언 아님). 오탐 — 무시 |

---

### F-5. `duplInheritedMember` — kTypeInfo 패턴 (확인됨)
**도구**: Cppcheck  
**위치**: 헤더 전반 (`directional_light.h`, `collider.h`, `actor.h` 등 모든 클래스)

> **경고 설명**: "파생 클래스가 기반 클래스의 멤버와 같은 이름의 멤버를 선언함 (shadowing)."  
> 보통 실수로 기반 클래스 멤버를 가리는 경우를 잡는 것.
> ```cpp
> class Base { int value; };
> class Derived : public Base { int value; };  // 경고 — Base::value를 가림
> ```

```cpp
// base/include/grapi/base/actor.h
class Actor : public Object {
  static constexpr TypeInfo kTypeInfo{"grapi::base::Actor", &Object::kTypeInfo};
  // ↑ Object도 kTypeInfo 가짐 → Cppcheck가 "상속된 멤버 중복"으로 경고
};

// base/include/grapi/base/camera.h
class Camera : public Actor {
  static constexpr TypeInfo kTypeInfo{"grapi::base::Camera", &Actor::kTypeInfo};
  // ↑ Actor의 kTypeInfo를 참조하면서 동시에 자신도 선언
};
```

이는 런타임 타입 식별(RTTI 대체) 패턴 — 각 클래스가 자신만의 `TypeInfo`를 가지고, 부모 `kTypeInfo`를 체인으로 연결해 `isA<T>()` 등의 타입 검사를 구현하는 의도적 설계. Cppcheck가 이 패턴을 이해하지 못하는 오탐. Cppcheck suppress 처리.

> **수정 시 특이사항**: 헤더가 55개 이상이라 파일마다 inline suppress(`// cppcheck-suppress duplInheritedMember`) 추가 대신 suppressions 파일 방식 적용.
> - `cppcheck-suppressions.txt` 신규 생성 (`grapi-base/` 루트)
> - Cppcheck 실행 명령에 `--suppressions-list=cppcheck-suppressions.txt` 추가 (verification_report.md 업데이트 완료)
> ```
> duplInheritedMember
> ```

---

### F-6. `malloc`/`free` 직접 사용 — cgltf C API 패턴 (확인됨)
**도구**: Clang-Tidy `cppcoreguidelines-no-malloc`  
**건수**: 74건  
**파일별**: `actor_exporter.cc`(68건), `ktx2_reader.cc`(5건), `ktx2_provider.cc`(1건)

> **경고 설명**: "`malloc`/`free`/`realloc`을 직접 쓰지 마라."  
> C 방식 동적 할당은 예외 안전하지 않음 — `malloc` 후 초기화 전에 예외가 나면 메모리 누수.  
> C++ 방식(`new`/`delete`, `std::unique_ptr`, `std::make_unique`)은 RAII로 자동 해제 보장.
> ```cpp
> // C 방식 — 예외 발생 시 누수
> T* p = (T*)malloc(sizeof(T));
> risky_init(p);   // 여기서 예외 → free(p) 호출 안 됨
>
> // C++ 방식 — 예외 안전
> auto p = std::make_unique<T>();
> risky_init(p.get());  // 예외 발생해도 소멸자가 해제
> ```

```cpp
// actor_exporter.cc — cgltf 데이터 구조 직접 할당 (60~132번 줄 집중)
cgltf_data* data = (cgltf_data*)malloc(sizeof(cgltf_data));
cgltf_free(data);   // cgltf 전용 해제 함수

// ktx2_reader.cc — KTX2 레벨 데이터 버퍼 할당 (A-4 관련)
vuint64* const blocks = static_cast<vuint64*>(malloc(length));
```

**원인 분석**:
- `actor_exporter.cc` 68건: cgltf C API 구조체(`cgltf_data`, `cgltf_node`, `cgltf_mesh` 등)를 직접 `malloc`으로 할당하는 glTF 내보내기 코드. cgltf 라이브러리가 `cgltf_free()`를 제공하므로 RAII 패턴으로 전환하려면 커스텀 deleter가 필요.
- `ktx2_reader.cc` 5건: `malloc` + `memcpy` 패턴으로 KTX2 레벨 버퍼 할당. A-4(null 체크 미비)에서 이미 분석.

**처리**: F등급 — cgltf/KTX2 C API 설계상 불가피. `.clang-tidy`에서 `cppcoreguidelines-no-malloc` 체크 제거로 해결.

> **해결 방법**: F-1(pointer-arithmetic)과 동일하게 `.clang-tidy`에서 해당 체크를 제거.  
> 74건 전체(`actor_exporter.cc` 68건, `ktx2_reader.cc` 5건, `ktx2_provider.cc` 1건)가 모두 cgltf/KTX2 C API 필수 패턴이므로 개별 NOLINT보다 체크 제거가 더 현실적.  
> `cgltf_free()`가 내부적으로 `free()`를 호출하는 라이브러리 특성상 C++ RAII 패턴으로 대체 불가.

---

## 9. 도구별 비교

| 항목 | Clang-Tidy v2 | Cppcheck |
|------|-------------|---------|
| 잠재적 버그 탐지 | 4건 (대입오류, 동일분기, 재귀, 멤버초기화) | 4건 (배열범위, 널포인터, 쉼표반환, uninit) |
| 중복 탐지 | 멤버 미초기화 | 멤버 미초기화 |
| 독자 강점 | 타입 변환 패턴, 비트 연산, 파라미터 설계 | 경로 감지(path-sensitive) 버그, 쉼표 오용 |
| 노이즈 주원인 | `misc-const-correctness` (100건+) | external 헤더 경고 혼재 |
| MISRA C++ 지원 | 부분적 (체크명으로 대응) | 미지원 (무료 버전) |

---

## 10. 조치 권장 순서

```
1단계 — 즉시 (A등급)
─────────────────────────────────────────────────────────────────
□ vehicle_component.cc:940 — if 조건 대입 오류 (= vs !=)
□ vehicle_component.cc:144 — 동일한 true/false 분기 로직 검토 (A-2)
□ geometry_component.cc:554-555 — 배열 인덱스 범위 guard 추가 (A-3)
□ ktx2_reader.cc:567,648 — malloc null 체크 추가 (A-4)
□ asset_loader.cc:529,794 — 재귀 함수 반복 방식 전환 (A-6, 수정 완료)
✅ ktx2_reader.cc:767 — FinalFormatInfo info{} 초기화 추가 (A-7, v4 잔여 1건)
□ asset_impl.cc:16 — 소멸자 예외 탈출 방지 noexcept (A-9)
□ curve.cc:42 — 변환 순서 수정 (A-10)
□ ibl.cc:194 — sscanf → strtof 교체 (A-11)
□ first_person_controls.cc:19, fly_controls.cc:22 — switch default 추가 (A-12)
□ actor_exporter.cc:319, raycaster.cc:15 — 재귀 함수 반복 방식 전환 (A-13)
□ joint_component.cc:190 — 중복 분기 수정 (A-14)

2단계 — 단기 (B/C등급)
─────────────────────────────────────────────────────────────────
□ hicpp-signed-bitwise 20건 — 비트 연산 타입을 uint로 교체 (A-8)
□ bugprone-narrowing-conversions 15건 — BaseID→int32_t 타입 통일 검토 (B-1)
□ typesetter.cc:79,249,250 — 곱셈 전 명시적 캐스트 추가 (B-2)
□ asset_loader.cc:523 — stringview.data() null-termination 처리 (B-5, 수정 완료)
□ extended_material_component.cc 16건 + ktx2/exporter 3건 — C 스타일 캐스트 교체 (B-6)
□ scene_impl/physics_context/vehicle 6건 — int→ptr NOLINT (B-7)
□ actor_exporter.cc 4건 — 다중 포인터 명시적 캐스트 (B-8)
□ vehicle_component.cc:32 — VehicleData Rule of Five 명시 (C-2)
□ ktx2_provider.cc:20, ktx2_reader.cc:468, joint_component.cc:23 — Rule of Five (C-2 추가)
□ resource_manager.cc:54 — Rule of Three 적용 (C-3)
□ ktx2_reader.cc:468 — FAsync public virtual 소멸자 + Rule of Five (C-6)

3단계 — 중기 (D등급 + F등급 정리)
─────────────────────────────────────────────────────────────────
□ = default 9건 — fixed/sixdof/hinge/slider/distance/cone_joint, body, vehicle (D-6)
□ [[nodiscard]] 5건 — ktx2_provider.cc Queue 상태 조회 함수 (D-7)
□ override 2건 — ktx2 files (D-8)
□ make_unique 1건 — ktx2_provider.cc:250 (D-9)
□ const& 파라미터 2건 — curve_path.cc, ibl.cc (D-10)
□ enum 타입 최소화 2건 — ktx2_provider.cc QueueItemState, TranscoderState (D-11)
□ bool 단순화 5건 — 자동 수정 가능 (D-12)
□ TODO 포맷 6건 — 팀 표준 확인 후 처리 (D-13)
□ 미사용 파라미터 17건 — 이름 제거 또는 삭제 (D-14)
□ F-1 278건 — cgltf/freetype pointer-arithmetic NOLINT 일괄 적용
✅ F-2 15건 — cgltf/Filament C API 배열 decay 불가피 패턴. NOLINT 15건 처리 완료
✅ F-4 27건 — std::array 교체 7건 + NOLINT 19건 + 오탐 1건 처리 완료
✅ F-6 74건 — cgltf/KTX2 C API 필수 패턴. `.clang-tidy`에서 `cppcoreguidelines-no-malloc` 제거

4단계 — 일괄 적용 (E등급)
─────────────────────────────────────────────────────────────────
□ misc-const-correctness 100건+ — -fix 플래그로 일괄 적용
   (별도 브랜치에서 빌드 확인 후 머지)
```

---

## 11. 관련 문서 및 원시 결과

- [06-clang-tidy-guide.md](06-clang-tidy-guide.md) — Clang-Tidy 실행 가이드
- [07-verification-report.md](07-verification-report.md) — v1 스캔 결과 요약
- [08-cppcheck-guide.md](08-cppcheck-guide.md) — Cppcheck 실행 가이드
- 원시 결과: `C:\working\grapi-base\clangtidy_v2.txt`
- 원시 결과: `C:\working\grapi-base\cppcheck_result_v3.txt`
