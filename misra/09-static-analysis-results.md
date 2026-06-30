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

**해결 방향**: 명시적 스택(`std::stack`)을 사용한 반복 방식으로 전환, 또는 최대 깊이 guard 추가.

---

### A-7. 멤버 초기화 누락 (확인됨)
**도구**: Clang-Tidy `cppcoreguidelines-pro-type-member-init`  
**위치**: `material_component.h:74` 선언, `material_component.cc:17` 생성자

```cpp
// material_component.h:74
filament::gltfio::UvMap uvmap_;  // 선언만, 기본값 없음

// material_component.cc:17
MaterialComponent::MaterialComponent(Entity e) : Component(e) {
  // uvmap_ 초기화 없음
}
```

`UvMap`이 trivial 타입(예: `std::array` 기반)인 경우 초기화되지 않은 채로 사용될 위험. `getUVIndex()`(cc:112)에서 `uvmap_.at(src_index)` 호출 시 초기화 여부가 중요.

**수정**:
```cpp
// 방법 1: 헤더에서 기본값 지정
filament::gltfio::UvMap uvmap_ = {};

// 방법 2: 생성자 초기화 목록에 추가
MaterialComponent::MaterialComponent(Entity e) : Component(e), uvmap_() {}
```

Cppcheck 결과에서 추가로 확인된 미초기화 멤버:
- `asset_impl.h:98` — `SourceAsset::hierarchy` 미초기화
- `asset_loader.h:40` — `AssetLoader::error_` 미초기화
- `ktx2_provider.cc:63` — `QueueItem::state_` 미초기화

---

### A-8. 부호 있는 정수에 비트 연산 (확인됨)
**도구**: Clang-Tidy `hicpp-signed-bitwise`  
**위치**: `view_impl.cc:1141`, `asset_loader.cc:130`, `asset_loader.cc:224`, `custom_material_provider.cc:28`

두 가지 패턴이 섞여 있어 대응 방식이 다름:

**① 사용자 코드 — 수정 대상** (`view_impl.cc:1141`)
```cpp
void ViewImpl::setLayerEnabled(vuint8 layer, bool enabled) {
  const vuint8 bit = static_cast<vuint8>(1u << (layer & 7));
  //                                              ^^^^^^^^
  //  layer(uint8) & 7(int) → 정수 승격으로 signed int 연산 발생
  setVisibleLayers(enabled ? (visible_layers_ | bit)
                           : (visible_layers_ & static_cast<vuint8>(~bit)));
}
```
`layer & 7`에서 `7`이 `int`(signed)이므로 `vuint8`이 `int`로 승격되어 signed 비트 연산이 발생.  
수정: `layer & static_cast<vuint8>(7)` 또는 `layer & 7u`

**② STL openmode 조합 — NOLINT 처리 권장** (`asset_loader.cc:130,224`, `custom_material_provider.cc:28`)
```cpp
std::ifstream in(filename, std::ifstream::ate | std::ifstream::binary);
//                         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
//  std::ios::openmode 는 MSVC 구현에서 signed 타입
```
`std::ios::openmode`가 MSVC에서 signed로 구현된 라이브러리 문제. 직접 수정 불가, NOLINT 처리가 현실적.
```cpp
std::ifstream in(filename, std::ifstream::ate | std::ifstream::binary);  // NOLINT(hicpp-signed-bitwise)

---

## 4. B등급 — 타입/안전성 문제

### B-1. 암묵적 정수 축소 변환 (Narrowing Conversion)
**도구**: Clang-Tidy `bugprone-narrowing-conversions`  
**건수**: 약 15건  
**주요 위치**: `text.cc:175`, `catmull_rom_curve.cc:63,65,70`, `view_impl.cc:1178,1180`, `custom_material_component.cc:43,54`, `skeleton.cc:35`, `asset_loader.cc:272,330,977,984~996`

| 변환 패턴 | 위험도 |
|-----------|--------|
| `unsigned int → int32_t` (`BaseID`) | 값이 크면 음수로 둔갑 |
| `size_t → int` / `int → float` | 범위 초과 시 정보 손실 |
| `double → float` (`cgltf` 데이터) | 정밀도 손실 |
| `long long → int` | 오버플로 |

`BaseID → int32_t` 패턴이 여러 파일에 걸쳐 반복됨 — `BaseID`의 타입 정의나 호출부 API 설계를 검토해서 일관된 타입으로 통일하는 것이 근본 해결책.

---

### B-2. 정수 곱셈 결과 암묵적 확장
**도구**: Clang-Tidy `bugprone-implicit-widening-of-multiplication-result`  
**위치**: `typesetter.cc:79, 249, 250`

```cpp
size_t result = int_a * int_b;  // int 범위에서 곱셈 후 확장 → 오버플로 가능
// 수정
size_t result = static_cast<size_t>(int_a) * int_b;
```

텍스트 렌더링의 픽셀 버퍼 크기 계산에서 발생. 큰 텍스트 크기에서 오버플로 가능.

---

### B-3. `reinterpret_cast` 사용
**도구**: Clang-Tidy `cppcoreguidelines-pro-type-reinterpret-cast`  
**건수**: 약 9건  
**주요 위치**: `typesetter.cc:82`, `custom_material_provider.cc:46`, `asset_loader.cc:145,226,317,402,403,406,408,1221`

대부분 cgltf C API와의 인터페이스에서 `void*` ↔ `float*` 등 변환. C API 특성상 완전히 피하기 어려우나, 각 지점마다 의도 주석(`// NOLINT: cgltf C API requires void*`) 추가 권장.

---

### B-4. `const_cast` 사용
**도구**: Clang-Tidy `cppcoreguidelines-pro-type-const-cast`  
**위치**: `asset_loader.cc:35`

`const` 제거는 const correctness 위반의 신호. 호출 대상 API가 `const`를 받지 않는 설계 문제일 수 있음 — API 시그니처 검토 권장.

---

### B-5. `stringview::data()` 결과 null-termination 미보장
**도구**: Clang-Tidy `bugprone-suspicious-stringview-data-usage`  
**위치**: `asset_loader.cc:523`

```cpp
push_back(string_view.data());  // data()는 null-terminated 미보장
```

`std::string_view::data()`는 null 종결 문자를 보장하지 않음. `std::string(sv)` 또는 `std::string(sv.data(), sv.size())` 로 명시적 변환 후 사용.

---

## 5. C등급 — 코드 설계 문제

### C-1. 인접한 동일 타입 파라미터 (인자 순서 실수 위험)
**도구**: Clang-Tidy `bugprone-easily-swappable-parameters`  
**건수**: 6건

| 위치 | 함수 | 파라미터 |
|------|------|---------|
| `controls.cc:8` | `setViewport` | `vint width, vint height` |
| `orbit_controls.cc:27` | `grabBegin` | `vint x, vint y` |
| `orbit_controls.cc:414` | `_handleMouseWheel` | 2개 |
| `orbit_controls.cc:426` | `_updateZoomParameters` | `vint w, vint h` |
| `catmull_rom_curve.cc:15` | `initNonuniformCatmullRom` | `vfloat` 다수 |
| `skeleton.cc:32` | `setJoint` | 유사 타입 2개 |

호출 시 순서를 바꾸면 컴파일러가 감지 못함. 강한 타입(`Width`, `Height` 등)이나 구조체로 묶는 방식이 근본 해결책.

---

### C-2. Rule of Five 미준수
**도구**: Clang-Tidy `cppcoreguidelines-special-member-functions`  
**위치**: `vehicle_component.cc:32` (`VehicleData`)

소멸자를 정의했으나 복사 생성자, 복사 대입, 이동 생성자, 이동 대입 연산자를 정의하지 않음. 리소스 관리 클래스에서 복사/이동 시 이중 해제(double free) 위험.

```cpp
class VehicleData {
    ~VehicleData() { ... }           // 정의됨
    // 나머지 4개 = ? 명시 필요
};
```

`= delete` 또는 `= default` 중 의도에 맞게 명시.

---

### C-3. Rule of Three 미준수
**도구**: Cppcheck `noCopyConstructor / noOperatorEq`  
**위치**: `resource_manager.cc:54`

소멸자만 있고 복사 생성자와 복사 대입 연산자가 없음. C-2와 유사한 패턴.

---

### C-4. `virtual` + `override` 중복 지정
**도구**: Clang-Tidy `modernize-use-override`  
**위치**: `context.cc:67`

```cpp
virtual void getCustomization() override;  // virtual 중복, override로 충분
```

---

### C-5. 네이밍 컨벤션 불일치
**도구**: Clang-Tidy `readability-identifier-naming`  
**위치**: `capsule_geometry.cc:9,10,11`

파라미터 이름(`capSegments`, `radialSegments`, `heightSegments`)이 프로젝트 컨벤션(`lower_case`)을 따르지 않음.

---

## 6. D등급 — 성능 / 스타일 개선

### D-1. `std::endl` → `'\n'`
**도구**: Clang-Tidy `performance-avoid-endl`  
**건수**: 5건  
**위치**: `custom_material_provider.cc:32, 39, 48, 59, 69`

`std::endl`은 출력 후 `flush()`를 강제 호출. 로그 출력처럼 빈번한 경우 성능 영향. `-fix` 플래그로 자동 수정 가능.

---

### D-2. `push_back(T(...))` → `emplace_back(...)`
**도구**: Clang-Tidy `modernize-use-emplace`  
**위치**: `asset_loader.cc:523`

불필요한 임시 객체 생성 제거. `-fix`로 자동 수정 가능.

---

### D-3. 소멸자 `= default` 대체 가능
**도구**: Clang-Tidy `modernize-use-equals-default`  
**위치**: `swing_twist_joint.cc:19`, `point_joint.cc:19`

빈 소멸자 본문을 `= default`로 교체 — 컴파일러가 trivial destructor로 최적화 가능. `-fix`로 자동 수정 가능.

---

### D-4. `[[nodiscard]]` 누락
**도구**: Clang-Tidy `modernize-use-nodiscard`  
**위치**: `catmull_rom_curve.cc:24` (`calc` 함수)

반환값을 무시하면 버그가 되는 함수에 `[[nodiscard]]` 부재. 호출자 실수 방지용으로 추가 권장.

---

### D-5. boolean 식 단순화
**도구**: Clang-Tidy `readability-simplify-boolean-expr`  
**위치**: `plane.cc:141`

```cpp
return !(a > eps || b > eps || c > eps);
// → DeMorgan 적용:
return a <= eps && b <= eps && c <= eps;
```

---

## 7. E등급 — 대량 스타일 (기계적 적용 가능)

### E-1. `const` 선언 누락 (misc-const-correctness)
**건수**: 약 100건+  
**분포**: 거의 모든 파일에 걸쳐 분산

초기화 후 변경되지 않는 지역 변수에 `const` 미선언. 컴파일러 최적화 힌트 및 의도 명확화에 유리.

**일괄 적용 방법**:
```cmd
python "...\run-clang-tidy" ^
  -clang-tidy-binary "...\clang-tidy.exe" ^
  -p out/build/windows-msvc-x64-debug ^
  -fix -checks="-*,misc-const-correctness" ^
  ".*base\\src\\.*"
```

> **주의**: `-fix` 전 반드시 git branch 생성. 자동 수정 후 빌드 확인 필수.

---

## 8. F등급 — 인프라 패턴 (오탐/의도적 패턴)

아래는 억제(NOLINT / suppress) 처리 권장.

| 체크 | 위치 | 이유 |
|------|------|------|
| `pro-bounds-pointer-arithmetic` | `asset_loader.cc` 전반 | cgltf C API — `data[offset]` 패턴이 C API 스펙 |
| `pro-bounds-array-to-pointer-decay` | `context.cc:166~217` | filament 빌드 시스템이 생성하는 바이너리 리소스 매크로 |
| `pro-type-reinterpret-cast` | `asset_loader.cc` cgltf 관련 | cgltf의 `void*` 인터페이스 — C API 특성상 불가피 |
| `avoid-c-arrays` | `vehicle_component.cc` 물리 코드 | JPH(JoltPhysics) C++ API 요구 사항 |
| `duplInheritedMember` (Cppcheck) | RTTI 패턴 전반 | `kTypeInfo` 설계 패턴 — 의도적 |

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
