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
| **A. 잠재적 버그** | 8건 | 실제 런타임 오동작 가능성 있음 — 즉시 검토 필요 |
| **B. 타입/안전성 문제** | ~30건 | 타입 변환 오류·부호 비트 연산·미초기화 등 |
| **C. 코드 설계 문제** | ~15건 | API 설계·재귀·Rule of Five 등 |
| **D. 성능/스타일 개선** | ~10건 | `std::endl`, `emplace_back`, `= default` 등 |
| **E. 대량 스타일 (노이즈)** | 100건+ | `misc-const-correctness` 위주 — 기계적으로 수정 가능 |
| **F. 인프라 패턴 (오탐)** | 다수 | C API/매크로 사용으로 인한 불가피한 경고 |

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

**`ktx2_provider.cc:63` — `QueueItem::state_`**
```cpp
// 수정 (타입에 맞는 초기값으로)
StateType state_ = StateType::kInitial;  // 실제 타입 확인 후 적용
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

```cpp
// cgltf 바이너리 버퍼 순회 — C API 스펙
vuint8* bytes = static_cast<vuint8*>(data->buffer_view->buffer->data);
bytes += data->offset + data->buffer_view->offset;   // 포인터 산술
for (cgltf_size i = 0, n = data->count; i < n; ++i, bytes += data->stride) {
  glm::vec4* weights = reinterpret_cast<glm::vec4*>(bytes);
  // ...
}
```

cgltf는 glTF 바이너리 버퍼를 `void*` 기반으로 제공하고, 오프셋·스트라이드로 탐색하는 것이 공식 사용 패턴. `std::span` 등으로 대체 불가. NOLINT 처리가 맞음.

```cpp
// 적용 완료 — asset_loader.cc 4곳
bytes += data->offset + data->buffer_view->offset;  // NOLINT(cppcoreguidelines-pro-bounds-pointer-arithmetic)
for (..., bytes += data->stride) {                  // NOLINT(cppcoreguidelines-pro-bounds-pointer-arithmetic)
src_buffer = bytes + src_matrices->offset;          // NOLINT(cppcoreguidelines-pro-bounds-pointer-arithmetic)
bytes + src_matrices->offset + ...->offset;         // NOLINT(cppcoreguidelines-pro-bounds-pointer-arithmetic)
```

---

### F-2. `pro-bounds-array-to-pointer-decay` (확인됨)
**도구**: Clang-Tidy  
**위치**: `context.cc:166~217`

```cpp
// generated/resources/base_materials.h (빌드 시스템 자동 생성)
extern const uint8_t BASE_MATERIALS_PACKAGE[];
#define BASE_MATERIALS_BLIT_DATA (BASE_MATERIALS_PACKAGE + BASE_MATERIALS_BLIT_OFFSET)
// ↑ C 배열 → 포인터 decay + 포인터 산술

// context.cc에서 사용
filament::Material::Builder()
    .package(BASE_MATERIALS_BLIT_DATA, BASE_MATERIALS_BLIT_SIZE)
    .build(*engine_);
```

`base_materials.h`는 filament 빌드 시스템이 자동 생성하는 파일. 직접 수정 불가. Filament의 `.package()` API가 `const void*`를 요구하므로 이 패턴이 필수. NOLINT 처리가 맞음.

```cpp
// 적용 완료 — context.cc 5곳 (.package() 호출마다)
.package(BASE_MATERIALS_BLIT_DATA, BASE_MATERIALS_BLIT_SIZE)          // NOLINT(cppcoreguidelines-pro-bounds-array-to-pointer-decay)
.package(BASE_MATERIALS_IMAGE_DATA, BASE_MATERIALS_IMAGE_SIZE)         // NOLINT(...)
.package(BASE_MATERIALS_PARTICLE_DATA, BASE_MATERIALS_PARTICLE_SIZE)   // NOLINT(...)
.package(BASE_MATERIALS_EXTENDED_DATA, BASE_MATERIALS_EXTENDED_SIZE)   // NOLINT(...)
createUbershaderProvider(engine_, UBERARCHIVE_DEFAULT_DATA, ...)        // NOLINT(...)
```

---

### F-3. `pro-type-reinterpret-cast` — cgltf 관련 (확인됨)
**도구**: Clang-Tidy  
**위치**: `asset_loader.cc:145` 외

```cpp
// cgltf 바이너리 버퍼에서 특정 타입으로 해석
glm::vec4* weights = reinterpret_cast<glm::vec4*>(bytes);  // uint8_t* → glm::vec4*
```

B-3에서 언급한 엄격한 앨리어싱 이슈와 동일한 패턴이나, cgltf C API가 강제하는 구조. cgltf 없이는 glTF 로딩 자체가 불가하므로 불가피. NOLINT 처리가 맞음.  
※ 핵심 가중치 계산 경로라면 `memcpy` 기반으로 교체하는 것이 더 엄밀하나, 실용상 NOLINT 억제가 현실적.

---

### F-4. `avoid-c-arrays` (확인됨)
**도구**: Clang-Tidy  
**위치**: `vehicle_component.cc:97~127`

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

---

### F-5. `duplInheritedMember` — kTypeInfo 패턴 (확인됨)
**도구**: Cppcheck  
**위치**: 헤더 전반 (`directional_light.h`, `collider.h`, `actor.h` 등 모든 클래스)

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
□ vehicle_component.cc:940 — if 조건 대입 오류 확인 (= vs ==)
□ vehicle_component.cc:144 — 동일한 true/false 분기 로직 검토
□ geometry_component.cc:554-555 — 배열 인덱스 범위 guard 추가
□ ktx2_reader.cc:567,648 — 널 포인터 검사 순서 수정
□ curve.cc:183~232 — suspiciousCommaInReturn 5건 수정
□ asset_loader.cc:529,794 — 재귀 함수 반복 방식 전환 또는 깊이 제한
□ material_component.cc:17 + Cppcheck 3건 — uninit 멤버 초기화 추가

2단계 — 단기 (B/C등급)
─────────────────────────────────────────────────────────────────
□ hicpp-signed-bitwise 5건 — 비트 연산 타입을 uint로 교체
□ bugprone-narrowing-conversions 15건 — BaseID→int32_t 타입 통일 검토
□ typesetter.cc:79,249,250 — 곱셈 전 명시적 캐스트 추가
□ asset_loader.cc:523 — stringview.data() null-termination 처리
□ vehicle_component.cc:32 — VehicleData Rule of Five 명시
□ resource_manager.cc:54 — Rule of Three 적용

3단계 — 중기 (D등급 + F등급 정리)
─────────────────────────────────────────────────────────────────
□ std::endl → '\n' 5건 (자동 수정 가능)
□ emplace_back, = default, [[nodiscard]], override 정리 (자동 수정)
□ NOLINT 주석으로 F등급 인프라 패턴 억제 (cgltf, filament 매크로)

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
