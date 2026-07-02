# 무료 정적분석 도구 테스트 결과 분석 — grapi-base

> Clang-Tidy(v2 확장 스캔)와 Cppcheck 두 도구를 grapi-base 엔진(`base/` 모듈 131개 파일)에 실제로 돌린 결과를 통합 분석.  
> 원시 결과 파일: `clangtidy_v2.txt`, `cppcheck_result_v3.txt`  
> (2026-06 기준, LLVM 19 / Cppcheck 2.21.0)  
> **v5 스캔 (2026-07)**: 수정 적용 후 재스캔 — 유저 코드 경고 9건 확인 및 전 건 수정 완료  
> **v6 스캔 (2026-07)**: 유저 코드 경고 **0건** — 전 항목 처리 완료 확인 (⚠️ 2026-07-02 확인 결과 이 "0건"은 사실 **`.cc` 파일 기준**이었음 — 정정 내용은 아래 "Clang-Tidy v9 재스캔" 항목 참고)  
> **Cppcheck v4 재스캔 (2026-07)**: 별도 Cppcheck 단독 재스캔(`cppcheck_result_v4.txt`) — 유저 코드(`base/`) 신규 94건 발견. 분류 결과 A-5와 중복 5건, 정보성 메시지 21건(F-7), 신규 버그 3건(A-15, 코드 수정 완료), 기존 D-8 중복 3건(코드 수정 완료), 신규 스타일/성능 개선 60건(D-16~D-21, 55건 코드 적용 + 4건 공개 API 보류 + 1건 디버그 전용 필드 유지; ktx2_provider.cc:89는 삭제로 D-18/D-21 항목을 동시에 해소), 오탐성 2건(F-8) — 전 건 분류·문서화 및 코드 적용 완료 (테스트/빌드 검증은 사용자가 별도 진행)  
> **Cppcheck v5/v6 재스캔 (2026-07, 사용자 빌드/재스캔)**: v5에서 두 가지 잔여 문제 발견 — ① A-5 억제 주석의 ID(`suspiciousCommaExpression`)가 실존하지 않는 잘못된 값이라 억제가 작동하지 않고 있었음(`Unmatched suppression` 메시지로 노출) → 실측으로 정확한 ID(`constStatement`) 확인 후 수정. ② `ktx2_reader.cc`의 세 번째 `createTexture` 오버로드에서 A-15 당시 놓쳤던 별개의 미사용 변수(`level_indices`) 발견 → 삭제 대신 주석 처리로 보존. 이어서 D-16/F-8/D-21에서 의도적으로 보류했던 7건(공개 API 4건, `random.h` 2건, `FinalFormatInfo::name` 1건)에도 정확한 ID(`returnByReference`, `redundantInitialization`, `unusedStructMember`, 모두 `--errorlist`로 실측 확인)로 억제 주석을 추가해 향후 재스캔 시 재발견되지 않도록 조치. v6 재스캔에서 `base/`의 잔여 28건이 모두 "의도적으로 보류한 항목"과 정확히 일치함을 확인(신규/누락 없음).  
> **Cppcheck v7/v8 재스캔 (2026-07, 사용자 빌드/재스캔)**: v7에서 `random.h` 억제 주석이 여전히 안 먹히는 걸 발견(ID는 맞았으나 주석을 `} value = {};` 선언 줄에 달아 실제 경고가 찍히는 overwrite 줄과 위치가 어긋남) → overwrite 줄로 이동해 수정. **v8 재스캔에서 `base/`에 남은 항목이 정보성 메시지(F-7) 21건뿐임을 확인 — 그 외 경고 0건.** Cppcheck v4 재스캔에서 시작된 94건 전부(코드 수정 55건, 공개 API/디버그 필드 등 의도적 보류 + 억제 주석 7건, 오탐 확인 5+2건, 정보성 21건) 최종 정리 완료.  
> **Clang-Tidy v9 재스캔 — `HeaderFilterRegex` 설정 버그 발견 (2026-07-02, 중요)**: WSL에서 Linux/WebGL 플랫폼용 Clang-Tidy를 재검증하던 중([08-multiplatform-verification-plan.md](08-multiplatform-verification-plan.md)), `.clang-tidy`의 `HeaderFilterRegex: '.*(grapi-base/(base|samples)).*\.(h|hpp)$'`가 슬래시(`/`) 기준인데 Windows 컴파일 DB 경로는 백슬래시(`\`)라 **한 번도 매치된 적이 없었고**, 그 결과 **헤더 파일(`.h`) 안의 clang-tidy 진단이 이번 검증 시작(v2)부터 지금까지 전부 숨겨져 있었음**이 드러남(증거: `clangtidy_v2.txt` 1852건 전체가 `.cc` 파일 경고뿐, `.h` 파일 경고 0건). 즉 "v6~v8 유저 코드 경고 0건"은 실제로는 "`.cc` 파일 기준 0건"이었음.  
> **수정**: `HeaderFilterRegex`를 `'.*grapi-base[/\\](base|samples)[/\\].*\.(h|hpp)$'`로 변경(양쪽 슬래시 모두 매치). 이후 재스캔한 `clangtidy_v9.txt`에서 헤더 파일 기준 신규 findings 대량 발견(중복 제거 후 고유 위치 1,833건 — 대부분 `modernize-use-nodiscard`처럼 대량/기계적 처리 가능한 성격, 잠재적 실버그 후보는 6건 중 2건(A-16, A-17) 확인 후 수정 완료, 나머지는 오탐이거나 기존 항목(D-26 등)에 통합). 상세 분류는 예비 문서 [09-clangtidy-v9-header-findings.md](09-clangtidy-v9-header-findings.md) 참고 — 대량 카테고리(D-22~D-27) 및 개별 소량 카테고리(D-28) 모두 본 리포트에 병합·코드 수정·재검증(v14) 완료.  
> **Cppcheck는 영향 없음**: `HeaderFilterRegex`는 clang-tidy 전용 설정이라 cppcheck 결과(v4~v8)는 그대로 유효, 재스캔 불필요.

---

## 1. 스캔 환경 요약

| 항목 | Clang-Tidy | Cppcheck | Clang-Tidy (수정 후) |
|------|--------------|----------|--------------|
| 버전 | LLVM 19 (VS 2022 번들) | 2.21.0 | LLVM 19 (VS 2022 번들) |
| 분석 파일 수 | 131개 | 131개 | 131개 |
| 외부 라이브러리 제외 | `HeaderFilterRegex` | `--file-filter=*\grapi-base\base\*` | `HeaderFilterRegex` |
| 설정 파일 | `.clang-tidy` | 명령줄 옵션 | `.clang-tidy` |
| 결과 저장 | `clangtidy_v2.txt` | `cppcheck_result_v3.txt` | `clangtidy_v6.txt` |
| 유저 코드 경고 | 다수 | 다수 | **0건** ✅ |

**환경 노이즈 주의**: 빌드 설정이 VS 2026 Insiders 기준이라 `compile_commands.json`에 VS 2026 STL 헤더 경로가 포함됨. VS 2026 STL은 내부적으로 `__builtin_is_implicit_lifetime` (Clang 20+ 전용 builtin)을 사용하는데, VS 2022 번들 clang-tidy (구버전)는 이를 인식 못 해 각 파일마다 `clang-diagnostic-error` 2건 발생. `.clang-tidy`의 `ExtraArgs: -D_ALLOW_COMPILER_AND_STL_VERSION_MISMATCH`는 이 문제와 무관(별도의 MSVC STL1000 경고용). **해결책**: VS 2026 clang-tidy (`C:\Program Files\Microsoft Visual Studio\18\Insiders\VC\Tools\Llvm\x64\bin\clang-tidy.exe`)로 스캔 시 해소됨. 실제 프로젝트 코드 분석에는 영향 없음.

---

## 2. 발견 이슈 전체 요약

| 등급 | 항목 수 | 설명 |
|------|--------|------|
| **A. 잠재적 버그** | 17건 | 실제 런타임 오동작 가능성 있음 — 즉시 검토 필요 (Cppcheck v4 재스캔 A-15 추가 + Clang-Tidy v9 재스캔 A-16/A-17 추가, 전 건 수정 완료) |
| **B. 타입/안전성 문제** | ~50건 | 타입 변환 오류·부호 비트 연산·C 스타일 캐스트·다중 포인터 변환 등 |
| **C. 코드 설계 문제** | ~20건 | API 설계·재귀·Rule of Five·virtual 소멸자 등 |
| **D. 성능/스타일 개선** | ~1,936건 | `= default`, `[[nodiscard]]`, unused 파라미터, TODO 포맷, getter const& 리턴, pointer-to-const, narrowing conversion, 네이밍, Rule of Five, signed-bitwise, swappable-parameters, enum-size 등 (Cppcheck v4 재스캔 D-16~D-21 63건 + Clang-Tidy v9 헤더 재스캔 D-22~D-28 1,823건 추가, 전 건 코드 적용 완료·일부 공개 API/디버그 필드/불가피한 패턴은 NOLINT 보류) |
| **E. 대량 스타일 (노이즈)** | 100건+ | `misc-const-correctness` 위주 — 기계적으로 수정 가능 |
| **F. 인프라 패턴 (오탐)** | ~420건+ | pointer-arithmetic 278건, array-to-pointer-decay 15건, `malloc`/C API 74건, Cppcheck 정보성 메시지 21건(F-7), redundant-init 오탐 2건(F-8), use-after-move 오탐 1건(F-9) 등 불가피한 경고 |

> **Cppcheck v4 재스캔 (2026-07) 요약**: 유저 코드(`base/`) 94건 발견 → A-5 중복 5건 / 정보성 메시지 21건(F-7) / 신규 버그 3건(A-15, 코드 수정 완료) / 기존 D-8 중복 3건(코드 수정 완료) / 신규 스타일·성능 60건(D-16~D-21, 55건 코드 적용·5건 보류/유지) / 오탐 2건(F-8). 전 건 분류·문서화 및 코드 적용 완료.  
> **최종 확인 (v8 재스캔, 2026-07, 사용자 빌드/재스캔)**: 빌드 성공 확인. 재스캔 과정에서 억제 주석 오류 2건(A-5 잘못된 ID, F-8 잘못된 줄 위치) 및 A-15 관련 잔여 미사용 변수 1건을 추가로 발견·수정. **v8 최종 결과: `base/` 잔여 경고 0건 (정보성 메시지 21건만 남음).**  
> **Clang-Tidy v9 재스캔 (2026-07) 요약**: `.clang-tidy`의 `HeaderFilterRegex`가 Windows 경로(백슬래시)와 매치되지 않던 설정 버그를 발견·수정(6장 D-22 앞 배경 설명 참고) — 이 버그로 인해 프로젝트 시작 이래 헤더 파일(`.h`) 진단이 전부 숨겨져 있었음. 수정 후 재스캔에서 헤더 전용 신규 경고 1,833건 노출. 잠재 버그 후보 6건 전수 검토(2건 실버그 확인·수정 → A-16/A-17, 1건 오탐 → F-9, 3건은 D-26 Rule of Five로 통합) + 대량 카테고리 6종(D-22~D-27, 1,723건) + 개별 소량 19종(D-28, 100건) 전부 분류·코드 수정 완료.  
> **최종 확인 (v14 재스캔, 2026-07)**: D-22~D-28 전 작업 완료 후 처음부터 다시 전체 재스캔(v10→v14, 5회 반복) — 그 과정에서 자체 회귀 버그 2건(D-26 5건 포함 총 7건, D-28 절 참고) 발견·즉시 수정. **v14 최종 결과: `base/` 코드 경고 0건**(잔여 3건은 전부 `external/filament` 서드파티, 우리 소관 아님). 에러 270건은 v9부터 있던 환경 노이즈로 불변 확인.

---

## 3. A등급 — 잠재적 버그 (즉시 검토)

### A-1. `if` 조건문 내 대입 연산자 (확인된 버그) ✅ 완료
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

### A-2. 동일한 true/false 분기 (확인된 복붙 버그) ✅ 완료
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

### A-3. `else` 분기에서 빈 배열 인덱스 접근 (확인된 복붙 버그) ✅ 완료
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

### A-4. `malloc` 반환값 null 미체크 (확인됨) ✅ 완료
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

### A-5. glm 생성자 쉼표 오탐 (F등급 재분류 — 오탐 확인) ✅ 완료
**도구**: Cppcheck — "Found suspicious operator ',', result is not used." (실제 체크 ID `constStatement`, 아래 참고)  
**위치**: `curve.cc:183, 188, 192, 214, 232`

실제 Cppcheck 출력 확인 결과, 경고가 실제로 존재하지만 **오탐**으로 판단:

```cpp
// curve.cc:183 — Cppcheck가 경고한 줄
normal = glm::vec3(1.0f, 0.0f, 0.0f);

// curve.cc:214
normals[i] = glm::vec3(rotation_matrix * glm::vec4(normals[i], 0.0f));
```

`glm::vec3(1.0f, 0.0f, 0.0f)`의 `,`는 생성자 인자 구분자이지 쉼표 연산자가 아님. Cppcheck가 glm 템플릿 타입을 완전히 파싱하지 못해 `glm::vec3(1.0f)` + 미사용 `0.0f, 0.0f`로 잘못 해석한 것. 코드 로직에 문제 없음.

**처리**: 인라인 주석 `// cppcheck-suppress constStatement`를 코드에 삽입하여 경고 억제.

> **참고**: A-5는 실질적 위험 없음 — F등급(오탐)으로 재분류.

> **Cppcheck v4 재스캔 확인**: 동일 5건(`curve.cc:183,188,192,214,232`)이 그대로 재발견됨.

> **⚠️ v5 재스캔에서 발견된 문제 — 억제 ID 오류**: 최초 적용 시 `// cppcheck-suppress suspiciousCommaExpression`로 처리했으나, v5 재스캔 결과 경고가 **그대로 재발생**했고 동시에 `information: Unmatched suppression: suspiciousCommaExpression` 메시지까지 새로 나타남. `suspiciousCommaExpression`은 실제로 존재하지 않는(추측으로 지어낸) 체크 ID였음 — 억제가 전혀 작동하지 않고 있었던 것.  
> **원인 확인 방법**: `cppcheck --project=... "--file-filter=*curve.cc" --enable=warning,style` (기본 템플릿, `--template=vs` 미사용)로 단독 실행하면 메시지 끝에 `[constStatement]`가 표시되어 정확한 ID 확인 가능.  
> **수정**: 5곳 모두 `constStatement`로 교체. v6 재스캔에서 경고 및 `Unmatched suppression` 메시지 모두 사라짐을 확인 완료.
>
> **교훈**: cppcheck 억제 ID는 메시지 문구만 보고 추측하지 말고, `--errorlist` 또는 기본 템플릿(ID 표시) 실행으로 반드시 실제 ID를 확인한 뒤 주석을 작성해야 함. 틀린 ID를 넣으면 억제가 조용히 실패하고 `Unmatched suppression` 정보 메시지만 늘어난다.

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

### A-8. 부호 있는 정수에 비트 연산 (확인됨) ✅ 완료
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

### A-9. 소멸자에서 예외 탈출 가능성 (확인됨) ✅ 완료
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

> **⚠️ WebGL(Emscripten) 빌드 에러 발견 및 수정 (2026-07)**: 위 `try/catch` 수정이 데스크톱(MSVC)에서는 문제없지만, WebGL 타깃(`em++`, `-fno-exceptions -fno-rtti -fno-unwind-tables`)에서는 컴파일 자체가 실패함:
> ```
> asset_impl.cc:21:3: error: cannot use 'try' with exceptions disabled
> ```
> 예외가 꺼진 빌드에서는 애초에 예외가 발생할 수 없으므로(모든 throw 지점이 abort/trap으로 대체됨) try/catch가 없어도 동작은 동일함. 표준 기능 테스트 매크로 `__cpp_exceptions`(MSVC/GCC/Clang/Emscripten 공통 지원, Filament의 `utils/Panic.h`도 유사하게 `__EXCEPTIONS`로 동일 패턴 사용)로 조건부 컴파일 처리:
> ```cpp
> AssetImpl::~AssetImpl() {
> #if __cpp_exceptions
>   try {
> #endif
>     releaseSourceData();
>     if (!detached_) {
>       // ... (기존 destroy 루프)
>     }
> #if __cpp_exceptions
>   } catch (const std::exception& e) {
>     utils::slog.e << "~AssetImpl: cleanup failed: " << e.what() << utils::io::endl;
>   } catch (...) {
>     utils::slog.e << "~AssetImpl: cleanup failed: unknown exception" << utils::io::endl;
>   }
> #endif
> }
> ```
> **교훈**: 이 프로젝트는 데스크톱(MSVC) 외에 WebGL(Emscripten, `-fno-exceptions`), 임베디드(Telechips) 등 예외가 아예 비활성화된 빌드 타깃을 함께 지원하므로, 앞으로 `try`/`catch`/`throw`를 새로 추가하는 수정은 항상 `#if __cpp_exceptions`로 감싸거나 애초에 예외를 쓰지 않는 방식(에러 코드 리턴 등)을 우선 검토해야 함.

---

### A-10. 변환 순서 오류 — 확장 전 캐스트 (확인됨) ✅ 완료
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

### A-11. `sscanf` 변환 오류 미보고 (확인됨) ✅ 완료
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

### A-12. `switch`에 `default` 케이스 없음 (확인됨) ✅ 완료
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

### A-13. 추가 재귀 함수 (확인됨) ✅ 완료
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

### A-14. 중복 분기 본문 (확인됨) ✅ 완료
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

### A-15. KTX2 레벨별 offset/length 버퍼 범위 검증 누락 (확인됨) ✅ 완료
**도구**: Cppcheck `unreadVariable` — "Variable 'level_index_size' is assigned a value that is never used." (최초 단서, 실제 원인은 코드 추적으로 확인)  
**위치**: `ktx2_reader.cc` — `Ktx2Reader::load()`, `FAsync::doTranscoding()`

**호출 경로 확인**: `Ktx2Provider::pushTexture()`(ktx2_provider.cc:91, filament `TextureProvider` 구현체 — glTF 에셋의 텍스처 바이너리를 받음) → `Ktx2Reader::asyncCreate()` → `createTexture(transcoder_, ...)` → BasisU transcoder 초기화 실패 시 `createTexture(data, size)`(범위 검증 있는 오버로드) 호출 → `second = 1` → `FAsync::doTranscoding()`에서 실제 파싱. `load()`도 내부적으로 동일한 `createTexture(transcoder_, data, size, transfer, second)`를 거치므로 같은 구조.

**최초 분석의 정정**: cppcheck는 `level_index_size`가 계산만 되고 안 쓰인다고 지적했는데, 처음에는 "범위 체크가 통째로 빠졌다"고 판단했다. 하지만 실제로는:
1. `second != 0`(또는 `second == 1`) 분기에 들어왔다는 것 자체가 `createTexture(data, size)`(검증 있는 오버로드, line 862 이후)가 이미 성공했다는 뜻 — 즉 `size >= sizeof(Ktx2Header) + level_index_size`는 **이미 검증된 상태**. `level_indices` 배열 자체를 읽는 것은 안전했다.
2. **진짜 문제**는 `level_indices[level].byte_offset`/`byte_length` — 이 두 값은 KTX2 바이너리 파일 내부에 직접 들어있는 값(공격자/손상 파일이 통제 가능)인데, 이 값으로 계산한 `offset`/`length`가 실제 버퍼 범위 안에 있는지는 **어디에서도 검증하지 않았다.**

**수정 전 (`load()`, 손상된 파일 시 OOB read 가능)**:
```cpp
for (vuint32 level = 0; level < header->level_count; ++level) {
  vsize const offset = level_indices[level].byte_offset;   // 파일에서 읽은 값, 미검증
  vsize const length = level_indices[level].byte_length;   // 파일에서 읽은 값, 미검증
  const vuint8* level_data = reinterpret_cast<const vuint8*>(data) + offset;
  vuint64* const blocks = static_cast<vuint64*>(malloc(length));
  if (blocks == nullptr) { engine_.destroy(texture); return nullptr; }
  memcpy(blocks, level_data, length);  // ← offset/length가 버퍼 밖이면 OOB read
```
`blocks`(목적지)는 `length` 크기로 정확히 할당되어 쓰기 오버플로는 없지만, 읽기 쪽(`data + offset`, `length`바이트)이 원본 버퍼(`size`)를 넘어서면 그대로 OOB read가 발생. `FAsync::doTranscoding()`의 `else` 분기(`source_buffer_` 기반)도 동일한 패턴.

**적용한 수정**:
1. **버퍼 범위 대조**: 두 위치 모두 `memcpy` 전에 offset/length를 버퍼 크기와 대조 (오버플로 없는 순서로 비교):
```cpp
// ktx2_reader.cc — Ktx2Reader::load()
for (vuint32 level = 0; level < header->level_count; ++level) {
  vsize const offset = level_indices[level].byte_offset;
  vsize const length = level_indices[level].byte_length;
  if (offset > size || length > size - offset) {
    engine_.destroy(texture);
    return nullptr;
  }
  // ... 이하 기존 코드
}

// ktx2_reader.cc — FAsync::doTranscoding()
for (vuint32 level = 0; level < header->level_count; ++level) {
  vsize const offset = level_indices[level].byte_offset;
  vsize const length = level_indices[level].byte_length;
  if (offset > source_buffer_.size() || length > source_buffer_.size() - offset) {
    return Result::kCompressedTranscodeFailure;
  }
  // ... 이하 기존 코드
}
```

2. **레벨 수 검증 추가 (보안 개선)**:
비동기 fallback 경로(`second == 1`) 등에서 비정상적인 KTX2 파일로 인해 `level_count`가 최대 지원 개수(`KTX2_MAX_SUPPORTED_LEVEL_COUNT` = 16)를 초과해 `FAsync::doTranscoding` 내부의 `transcoder_results_` 배열 범위를 침범하고 `FAsync` 멤버 포인터를 오염시키는 힙 오버플로우(Heap OOB Write) 문제를 방지하기 위해, `createTexture(const void* data, vsize size)` 함수 초입에 검증 및 디버그 로깅 코드 추가:
```cpp
// ktx2_reader.cc — Ktx2Reader::createTexture()
const Ktx2Header* header = reinterpret_cast<const Ktx2Header*>(data);
if (header->level_count == 0 || header->level_count > KTX2_MAX_SUPPORTED_LEVEL_COUNT) {
  if (!quiet_) {
    utils::slog.e << "KTX2 invalid or unsupported level count: "
                  << header->level_count << utils::io::endl;
  }
  return nullptr;
}
```

**부수 정리**: 두 위치에서 실제로 쓰이지 않던 `vsize const level_index_size = sizeof(Ktx2LevelIndex) * header->level_count;` 계산도 함께 제거(cppcheck가 지적한 원래 대상). 이 값은 `level_indices` 배열 자체의 범위 검증용인데, 그 검증은 호출 이전 단계(`createTexture(const void*, vsize)`)에서 이미 끝난 상태라 여기서는 불필요한 죽은 코드였음. 해당 오버로드(line 869~872)의 동일 변수는 그대로 유지(정상적으로 사용 중).

> **v5 재스캔에서 추가로 발견된 동일 계열 이슈**: `createTexture(const void* data, vsize size)` 오버로드(범위 검증이 있는 "정상" 버전) 자체에도 별개의 죽은 코드가 남아있었음 — `const Ktx2LevelIndex* level_indices = reinterpret_cast<...>(level_index_ptr);`를 계산해놓고 이 함수는 텍스처 메타데이터(width/height/levels/format/sampler)만 빌드하고 반환하며 실제 픽셀 데이터는 채우지 않아 `level_indices`를 전혀 읽지 않음. cppcheck `unreadVariable` — "Variable 'level_indices' is assigned a value that is never used."(당시 라인 871).  
> **처리**: 삭제 대신 주석 처리로 보존(향후 이 함수에서도 이미지 데이터를 채우게 될 가능성 대비) — `level_index_ptr`, `level_indices` 계산 두 줄을 주석으로 남기고 사유 설명 추가. v6 재스캔에서 해당 경고 사라짐 확인.

---

### A-16. `ContactListenerImpl::body_interface_` 멤버 초기화 누락 (확인됨) ✅ 완료
**도구**: Clang-Tidy `cppcoreguidelines-pro-type-member-init`  
**위치**: `physics_context.h:85`  
**발견 경위**: `.clang-tidy`의 `HeaderFilterRegex`가 Windows 경로(백슬래시)와 안 맞아 헤더 파일 진단이 전부 숨겨져 있던 버그를 발견·수정한 뒤(v9 재스캔), 처음으로 드러난 헤더 전용 findings 중 하나. 상세 경위는 [09-clangtidy-v9-header-findings.md](09-clangtidy-v9-header-findings.md) 참고.

A-7과 동일 패턴. `ContactListenerImpl`에 생성자가 없어 암묵 기본생성자가 `body_interface_`(raw pointer)를 초기화하지 않은 채로 둠.

```cpp
// physics_context.h — 변경 전
class ContactListenerImpl : public JPH::ContactListener {
  ...
 private:
  JPH::Mutex mutex_;
  std::vector<std::pair<JPH::BodyID, JPH::BodyID>> added_contacts_;
  std::vector<std::pair<JPH::BodyID, JPH::BodyID>> removed_contacts_;
  JPH::BodyInterface* body_interface_;   // ← 초기화 없음
};
```

**호출 경로 확인**: `pollContactAdded()`/`pollContactRemoved()`에서 `body_interface_->GetUserData(...)`로 역참조. 세팅하는 유일한 경로 `setBodyInterface()`는 `SceneImpl::getPhysicsContext()`(scene_impl.cc:625~644)에서 `PhysicsContext` 생성 직후 바로 호출되고, `contact_listener`를 쓰는 모든 곳(`_runPhysicsFeedbackSystem` 등)이 이 게터를 거치므로 **현재 코드 경로에서 미초기화 역참조는 발생하지 않음**. 다만 호출 순서가 바뀌거나 새 호출부가 추가되면 크래시 소지가 있는 잠재적 지뢰라 A-7과 동일하게 방어적으로 수정.

```cpp
// 수정
JPH::BodyInterface* body_interface_ = nullptr;
```

---

### A-17. `Sphere` 생성자 정점 수 계산 — 확장 전 캐스트 (확인됨) ✅ 완료
**도구**: Clang-Tidy `bugprone-misplaced-widening-cast`  
**위치**: `geometries/sphere.h:26-27`  
**발견 경위**: A-16과 동일 (`HeaderFilterRegex` 버그 수정 후 v9 재스캔에서 신규 발견).

A-10(`curve.cc:42`)과 동일 패턴 — 연산이 확장 전 타입(`int`) 범위에서 먼저 수행된 후 캐스트가 적용됨.

```cpp
// sphere.h — 변경 전
const vsize vertex_count =
  static_cast<vsize>((width_segments + 1) * (height_segments + 1));
//                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
//                    width_segments/height_segments가 vint(int)라
//                    곱셈이 int 범위에서 먼저 계산됨
```

`width_segments`, `height_segments`가 둘 다 대략 46,341(`INT_MAX`의 제곱근 근처) 이상이면 곱셈 자체가 부호 있는 정수 오버플로(UB)를 일으키고, 그 쓰레기 값이 `vsize`로 캐스트되어 `vertices_.reserve(vertex_count)`에 비정상적인 크기가 전달될 수 있음. 실사용 세그먼트 수(수십~수백)로는 발생 가능성 낮지만 방어적 수정 가치 있음.

```cpp
// 수정 — 곱셈 전에 각 항을 먼저 vsize로 확장
const vsize vertex_count =
    static_cast<vsize>(width_segments + 1) * static_cast<vsize>(height_segments + 1);
```

---

## 4. B등급 — 타입/안전성 문제

### B-1. 암묵적 정수 축소 변환 (Narrowing Conversion) ✅ 완료
**도구**: Clang-Tidy `bugprone-narrowing-conversions`  
**건수**: 134건 (v4 스캔 기준) + v5 추가 4건 — 전 건 `static_cast` 명시 처리 완료

**v5 스캔 추가 발견 (2파일 4건)**:

| 파일 | 라인 | 내용 | 수정 |
|------|------|------|------|
| `curve.cc` | :15,26 | `static_cast<vfloat>(d) / divisions` — `divisions`(vint) 암묵적 vfloat 변환 | `/ static_cast<vfloat>(divisions)` |
| `collider_component.cc` | :88,113 | `vint const primitive_count = mc->getPrimitiveCount()` — vsize→vint 축소 | `static_cast<vint>(mc->getPrimitiveCount())` |

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

### B-2. 정수 곱셈 결과 암묵적 확장 ✅ 완료
**도구**: Clang-Tidy `bugprone-implicit-widening-of-multiplication-result`  
**건수**: 11건 (v4 스캔 기준)

| 파일 | 라인 | 패턴 | 수정 |
|------|------|------|------|
| particles_component.cc | :531~535 | `4 * max_particles_` (vuint32×int → size_t) | `static_cast<vsize>(4) * max_particles_` |
| particles_component.cc | :630 | `max_particles_ * 6` (vuint32×int → size_t) | `static_cast<vsize>(max_particles_) * 6` |
| ktx2_reader.cc | :196 | `bytes_per_pix * width * row_count` (uint32×uint32 → vsize) | `static_cast<vsize>(bytes_per_pix) * ...` |
| ibl.cc | :55 | `w * h * n * sizeof(vfloat)` (vint×vint → size_t) | `static_cast<vsize>(w) * static_cast<vsize>(h) * static_cast<vsize>(n) * sizeof(...)` |
| ibl.cc | :64 | `w * h * sizeof(float3)` (vint×vint → size_t) | `static_cast<vsize>(w) * static_cast<vsize>(h) * sizeof(...)` |
| ibl.cc | :337 | `w * h * sizeof(vuint32)` (vint×vint → size_t) | `static_cast<vsize>(w) * static_cast<vsize>(h) * sizeof(...)` |
| animation_mixer.cc | :217 | `num_morph_targets * 2` (vint×int → ptrdiff_t) | `static_cast<ptrdiff_t>(num_morph_targets) * 2` |

**원인**: 좁은 정수(int/uint32)끼리 곱셈이 32비트에서 먼저 수행된 뒤 size_t/ptrdiff_t로 확장. 결과가 2³²를 넘으면 오버플로 후 확장 → 잘못된 크기로 메모리 접근.  
**수정 방향**: 곱셈 전에 한쪽 피연산자를 `static_cast<vsize>` 또는 `static_cast<ptrdiff_t>`로 먼저 올려서 64비트 산술로 수행.

---

### B-3. `reinterpret_cast` 사용 ✅ 완료
**도구**: Clang-Tidy `cppcoreguidelines-pro-type-reinterpret-cast`  
**건수**: 29건 (v4 스캔 기준) — 전 건 NOLINT 처리

| 파일 | 라인 | 패턴 |
|------|------|------|
| asset_loader.cc | :228 | `vuint8*` → `char*` (istream::read C++ API) |
| ktx2_reader.cc | :551,553,557,566,637,642,834,868 | raw binary → KTX2 구조체 포인터 파싱 |
| mesh_component.cc | :228 | `glm::vec3*` → `filament::math::float3*` (동일 레이아웃 type-pun) |
| geometry_component.cc | :909 | `glm::vec3*` → `const float*` (meshopt C API) |
| ibl.cc | :59 | `void*` → `image::LinearImage*` (lambda 내 user 포인터 복원) |
| ibl.cc | :65 | `float*` → `filament::math::float3*` (stbi C API) |
| ibl.cc | :304 | `void(*)(void*)` → `PixelBufferDescriptor::Callback` (Filament API) |
| scene_impl.cc | :540 | `uint64` → `RigidBody*` (Jolt UserData 복원, 기존 NOLINT 체인 추가) |
| rigidbody_component.cc | :126,153 | `RigidBody*` → `uint64` (Jolt UserData 저장) |
| physics_context.cc | :140,141,175,176 | `uint64` → `RigidBody*` (Jolt UserData 복원, 기존 NOLINT 체인 추가) |
| vehicle_component.cc | :1081 | `uint64` → `RigidBody*` (Jolt UserData 복원, 기존 NOLINT 체인 추가) |
| animation_mixer.cc | :142,161,182,259 | `vfloat*` → `float3*/quatf*` (GLTF binary type-pun) |
| actor_exporter.cc | :2428,2528,2826 | `vuint8*`/`void*` → `char*` (ostream::write/istream::read C++ API) |

**처리 방침**: 모두 C/C++ API 경계 또는 바이너리 파싱 불가피 패턴. `NOLINT(cppcoreguidelines-pro-type-reinterpret-cast)` 일괄 적용. 이미 `performance-no-int-to-ptr` NOLINT가 있던 경우 콤마로 체인.

---

### B-4. `const_cast` 사용 ✅ 완료
**도구**: Clang-Tidy `cppcoreguidelines-pro-type-const-cast`  
**건수**: 4건 (v4 스캔 기준)

| 파일 | 라인 | 패턴 | 처리 |
|------|------|------|------|
| actor.cc | :284 | `const_cast<Actor*>(this)->body()` — const에서 non-const 위임 (Scott Meyers 패턴) | NOLINT |
| actor.cc | :296 | `const_cast<Actor*>(this)->vehicle()` — 동일 패턴 | NOLINT |
| scene_impl.cc | :672 | `const_cast<SceneImpl*>(this)->getPhysicsContext()` — 동일 패턴 | NOLINT |
| asset_impl.cc | :11 | `const_cast<cgltf_data*>(src_asset)` — cgltf C API 경계, SourceAsset이 non-const 요구 | NOLINT |

`const_cast<T*>(this)` 패턴은 const/non-const 오버로드 간 코드 중복을 제거하는 관용적 C++ 패턴으로 실질 위험 없음.

---

### B-5. `StringView::data()` null-termination 미보장 (확인됨) ✅ 완료
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

### B-6. C 스타일 캐스트 사용 (확인됨) ✅ 완료
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

### B-7. 정수 → 포인터 변환 최적화 저해 (확인됨) ✅ 완료
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

### B-8. 다중 포인터 암묵적 변환 (확인됨) ✅ 완료
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

### B-9. C 가변 인자 함수 사용 ✅ 완료
**도구**: Clang-Tidy `cppcoreguidelines-pro-type-vararg`  
**건수**: 1건 (v4 스캔 기준)

| 파일 | 라인 | 내용 | 처리 |
|------|------|------|------|
| ibl.cc | :196 | `sscanf(...)` — 이미 `cert-err34-c` NOLINT 있음 | 체인에 `cppcoreguidelines-pro-type-vararg` 추가 |

```cpp
// 처리 후
vint const n = sscanf(...);  // NOLINT(cert-err34-c, cppcoreguidelines-pro-type-vararg)
```

---

## 5. C등급 — 코드 설계 문제

### C-1. 인접한 동일 타입 파라미터 (인자 순서 실수 위험) ✅ 완료
**도구**: Clang-Tidy `bugprone-easily-swappable-parameters`  
**건수**: 31건 (v4 스캔 기준) + v5 추가 4건 — 전 건 NOLINT 처리

**v5 스캔 추가 발견**: 멀티라인 함수 시그니처에서 NOLINT가 첫 번째 줄에만 있고 경고가 두 번째 줄에서 발생하는 케이스 4건. 해당 파라미터 줄에 NOLINT 추가.

| 파일 | 경고 라인 | 조치 |
|------|-----------|------|
| `vehicle_component.cc:1332` | lambda `in_longitudinal_friction, float in_lateral_friction` | 해당 줄에 NOLINT 추가 |
| `actor_exporter.cc:2711` | `BaseID texture_id` 파라미터 줄 | 해당 줄에 NOLINT 추가 |
| `animation_mixer.cc:125` | `vsize prev_index, vsize next_index` 줄 | 해당 줄에 NOLINT 추가 |
| `joint_component.cc:1001` | `const vfloat damping` 파라미터 줄 | 해당 줄에 NOLINT 추가 |

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

### C-2. Rule of Five 미준수 ✅ 완료
**도구**: Clang-Tidy `cppcoreguidelines-special-member-functions`  
**건수**: 3건 (v4 스캔 기준)

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

### C-3. Rule of Three 미준수 (확인됨) ✅ 완료
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

### C-4. `virtual` + `override` 중복 지정 (확인됨) ✅ 완료
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

### C-5. 네이밍 컨벤션 불일치 ✅ 완료
**도구**: Clang-Tidy `readability-identifier-naming`  
**건수**: 7건 (v4 스캔 기준)

`.clang-tidy` 규칙: `VariableCase: lower_case`, `StaticConstantCase: CamelCase + k prefix`, `ClassMemberSuffix: _` (멤버 변수만)

| 파일 | 라인 | 변경 전 | 변경 후 | 이유 |
|------|------|---------|---------|------|
| `asset_loader.cc` | :35 | `kDefaultMatName` | `default_mat_name` | 함수 내 지역 상수 → `lower_case` |
| `extended_material_component.cc` | :17 | `MAX_INDEX` | `max_index` | 함수 내 지역 상수 → `lower_case` |
| `geometry_component.cc` | :842 | `remapAttribute` | `remap_attribute` | 람다 지역 변수 → `lower_case` |
| `ibl.cc` | :260 | `face_suffix` | `kFaceSuffix` | `static const` → `k` prefix CamelCase |
| `scene_impl.cc` | :714 | `dirty_` | `dirty` | 지역 변수 (멤버 아님) → `_` 접미사 제거 |
| `view_impl.cc` | :1209 | `kDepthFormats` | `depth_formats` | 함수 내 비정적 지역 상수 → `lower_case` |
| `actor_exporter.cc` | :1946 | `tex_name_path_` | `tex_name_path` | 지역 변수 (멤버 아님) → `_` 접미사 제거 |

**주요 수정 사항**:
- `scene_impl.cc`: `dirty_` → `dirty` 변환 시 `pending_dirty_`·`dirty_count_` 멤버 변수와 혼동 주의. 지역 변수 `dirty_` 단독 패턴(`bool dirty_ =`, `        dirty_ = true;`, `dirty_ = (dirty_ || `, `if (dirty_)`, `else if (!dirty_`)만 선택적 대체.
- `extended_material_component.cc`: `MAX_INDEX` → `max_index` replace_all 13건(선언 1 + 사용 12).
- `geometry_component.cc`: `remapAttribute` → `remap_attribute` replace_all 10건(선언 1 + 호출 9).

> **수정 시 특이사항** (capsule_geometry.cc 1건, 이전 세션 완료):  
> 문서에는 `capsule_geometry.cc`와 헤더만 언급됐으나, `createCapsuleGeometry` 구현 체인도 수정 필요. 총 4개 파일(`capsule_geometry.h`, `capsule_geometry.cc`, `object_factory.h`, `object_factory.cc`) 수정.

---

### C-6. `virtual` 소멸자가 `protected` — 접근 제어 불명확 ✅ 완료
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

**처리**: NOLINT 억제

`Ktx2Reader`가 `friend`로 선언되어 유일한 삭제 경로(`asyncDestroy`)를 가지는 factory 패턴. `protected`로 외부 직접 삭제를 차단하고 `virtual`로 `FAsync::~FAsync()` 호출을 보장하는 의도적 설계이므로 `public virtual` 변경보다 NOLINT가 적합.

```cpp
// ktx2_reader.h:154 — Async 기반 클래스
virtual ~Async();  // NOLINT(cppcoreguidelines-virtual-class-destructor)

// ktx2_reader.cc:469 — FAsync 파생 클래스
// v5 스캔에서 경고가 소멸자 라인(489)이 아닌 클래스 선언 라인(469)에서 발생함을 확인
// cppcoreguidelines-virtual-class-destructor는 클래스 정의 라인을 경고 위치로 보고함
class FAsync : public Async {  // NOLINT(cppcoreguidelines-virtual-class-destructor)
```

---

## 6. D등급 — 성능 / 스타일 개선

### D-1. `std::endl` → `'\n'` (확인됨) ✅ 완료
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

### D-2. `push_back(T(...))` → `emplace_back(...)` ✅ 완료
**도구**: Clang-Tidy `modernize-use-emplace`  
**건수**: 3건 (v4 스캔 기준)

| 파일 | 라인 | 수정 |
|------|------|------|
| `asset_loader.cc` | :523 | B-5와 동시 적용 — `emplace_back(uri.data(), uri.size())` |
| `physics_context.cc` | :113 | `push_back(std::pair<...>(id1, id2))` → `emplace_back(id1, id2)` |
| `physics_context.cc` | :121 | 동일 패턴 — `removed_contacts_` |

```cpp
// physics_context.cc — 변경 전
added_contacts_.push_back(
    std::pair<JPH::BodyID, JPH::BodyID>(in_body1.GetID(), in_body2.GetID()));

// 변경 후
added_contacts_.emplace_back(in_body1.GetID(), in_body2.GetID());
```

`push_back`은 임시 `std::pair` 객체를 먼저 만든 후 이동. `emplace_back`은 생성자 인자를 직접 전달해 불필요한 임시 객체 제거.

---

### D-3. 빈 소멸자 `= default` 대체 가능 ✅ 완료
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

### D-4. `[[nodiscard]]` 누락 (확인됨) ✅ 완료
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

### D-5. boolean 식 단순화 (확인됨) ✅ 완료
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

### D-6. 빈 소멸자 `= default` 대체 — 추가 9건 ✅ 완료
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

### D-3/D-6 추가. `performance-trivially-destructible` ✅ 완료
**도구**: Clang-Tidy `performance-trivially-destructible`  
**건수**: 2건 (v4 스캔 기준)  
**위치**: `body.h:27`, `vehicle.h:27`

`.cc`에 `= default`가 있어도 헤더 선언이 `~Body()`이면 다른 TU에서 user-defined 소멸자로 보여 trivially destructible로 인식되지 않음. 헤더 선언부에서 직접 `= default` 해야 `std::is_trivially_destructible`이 true가 됨.

```cpp
// 변경 전 (body.h / vehicle.h)
~Body();
~Vehicle();

// 변경 후 — 헤더에서 직접 default
~Body() = default;
~Vehicle() = default;
```

`.cc`의 중복 `= default` 정의는 제거.

---

### D-7. `[[nodiscard]]` 누락 — 추가 5건 (확인됨) ✅ 완료
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

### D-8. `override` 누락 (확인됨) ✅ 완료
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

> **Cppcheck v4 추가 발견 (3건)** — 소멸자가 `virtual`은 있지만 `override` 없이 base 소멸자를 오버라이드하는 동일 패턴 (수정 완료):
>
> | 파일 | 위치 |
> |------|------|
> | `first_person_controls.h:20` | `~FirstPersonControls` (base `Controls` 소멸자 오버라이드) |
> | `fly_controls.h:23` | `~FlyControls` (base `Controls` 소멸자 오버라이드) |
> | `map_controls.h:20` | `~MapControls` (base `OrbitControls` 소멸자 오버라이드) |
>
> ```cpp
> // 수정 완료 (virtual 키워드 제거하고 override 추가)
> ~FirstPersonControls() override = default;
> ~FlyControls() override = default;
> ~MapControls() override = default;
> ```

---

### D-9. `new` 대신 `std::make_unique` 사용 (확인됨) ✅ 완료
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

### D-10. 값 파라미터 → `const` 참조로 변경 (확인됨) ✅ 완료
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

### D-11. enum 크기 최소화 (확인됨) ✅ 완료
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

### D-12. boolean 식 단순화 — 추가 5건 (확인됨) ✅ 완료
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

### D-13. TODO 포맷 불일치 (확인됨) ✅ 완료
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

### D-14. 미사용 파라미터 (확인됨) ✅ 완료
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

### D-15. `using namespace` 전체 네임스페이스 오염 ✅ 완료
**도구**: Clang-Tidy `google-build-using-namespace`  
**건수**: 2건 (v4 스캔 기준)  
**위치**: `ktx2_reader.cc:32,33`

```cpp
using namespace basist;   // NOLINT(google-build-using-namespace)
using namespace filament;  // NOLINT(google-build-using-namespace)
```

`basist` 타입(`ktx2_transcoder`, `ktx2_image_level_info` 등)이 26건 이상 사용되고, 모두 외부 라이브러리 네임스페이스이며 `.cc` 파일(헤더 아님)이라 오염 범위가 해당 TU에 한정됨. 개별 `using` 선언으로 교체하면 코드가 크게 늘어나므로 NOLINT 처리.

---

### D-16. getter가 값 대신 `const&` 리턴해야 함 (Cppcheck v4 신규) ✅ 완료 (9건 적용 / 4건 공개 API로 보류)
**도구**: Cppcheck `performance` (returnByReference 계열)  
**건수**: 13건

코드 적용 전, 각 클래스가 `include/`(공개 헤더, `BASE_PUBLIC` export)인지 `src/`(내부 구현)인지 확인 후 처리를 나눔. C-1에서 확립된 방침("공개 API는 시그니처 유지, 내부 구현만 실제 변경")을 그대로 따름 — 리턴 타입 변경은 파라미터 이름과 달리 실제 시그니처/ABI 변경이라 공개 API에는 적용하지 않음.

**적용 완료 (9건 — 모두 `src/` 내부 구현 클래스)**:

| 파일 | 라인 | 함수 | 비고 |
|------|------|------|------|
| `asset_impl.h` | :27 | `getActors()` | `AssetImpl`은 PIMPL 내부 구현, `Asset::getActors()`(공개)는 시그니처 그대로 유지 |
| `asset_impl.h` | :31 | `getLightActors()` | 상동 |
| `asset_impl.h` | :35 | `getCameraActors()` | 상동 |
| `asset_impl.h` | :43 | `getAnimations()` | 상동 |
| `asset_impl.h` | :47 | `getResourceUris()` | 상동 |
| `context.h` | :59 | `getConfig()` | `Context`는 내부 싱글턴, `Engine::getConfig()`(공개)는 유지 |
| `components/animation_component.h` | :16 | `getTracks()` | ECS 컴포넌트, 내부 전용. 호출부(`animation_mixer.cc`) 확인 — 반환값 non-const 변경 없음 |
| `components/light_component.h` | :81 | `getShadowOptions()` | 상동, 호출부(`light.cc`) 확인 |
| `text/freetype_font.h` | :36 | `getUri()` | 내부 클래스, 호출부(`font_component.cc`) 삼항연산자 호환 확인 |

```cpp
// 적용 예 (asset_impl.h)
// 변경 전
std::vector<BaseID> getActors() const { return actors_; }
// 변경 후
const std::vector<BaseID>& getActors() const { return actors_; }
```

**보류 (4건 — `include/`, `BASE_PUBLIC` 공개 API)**:

| 파일 | 라인 | 함수 | 보류 사유 |
|------|------|------|-----------|
| `curve_path.h` | :51 | `getCurves()` | `class BASE_PUBLIC CurvePath` — 공개 export 클래스 |
| `keyframe_track.h` | :78 | `getTimes()` | `class BASE_PUBLIC KeyframeTrack` — 공개 export 클래스 |
| `keyframe_track.h` | :87 | `getValues()` | 상동 |
| `shape.h` | :47 | `getHoles()` | `class BASE_PUBLIC Shape` — 공개 export 클래스 |

이 4건은 C-1의 `Controls::setViewport` NOLINT 처리와 동일한 논리로 보류. 코드는 변경하지 않음.

> **추가 조치 (v5 재스캔 후)**: 보류 4건도 향후 재스캔 시 계속 "신규 경고"처럼 재발견되는 것을 막기 위해 `// cppcheck-suppress returnByReference` 인라인 억제 주석을 각 선언부에 추가(실제 코드 시그니처는 변경하지 않음). 정확한 체크 ID는 `curve_path.cc`를 `--file-filter`로 단독 스캔해 `[returnByReference]`로 직접 확인(A-5의 ID 실수 이후 추측 대신 항상 실측하도록 변경). `curve_path.cc`, `keyframe_track.cc`, `shape.cc`를 각각 `--inline-suppr`로 재스캔해 경고 및 `Unmatched suppression` 메시지 모두 사라짐을 확인 완료.
> ```cpp
> // 예 (curve_path.h)
> // 공개 API 시그니처 유지를 위해 const&로 변경하지 않음 (D-16 참고)
> std::vector<std::shared_ptr<Curve>> getCurves() const;  // cppcheck-suppress returnByReference
> ```

---

### D-17. 생성자 본문 대입 대신 초기화 목록 사용 (Cppcheck v4 신규) ✅ 완료
**도구**: Cppcheck `performance` — "Variable is assigned in constructor body. Consider performing initialization in initialization list."  
**건수**: 3건  
**위치**: `ray.h:36,37,38` (`origin`, `direction`, `direction_inverse`)

```cpp
// 변경 전
Ray::Ray(const glm::vec3& origin, const glm::vec3& direction) {
  this->origin = origin;
  this->direction = direction;
  this->direction_inverse = 1.0f / direction;
}

// 변경 후 — 멤버 초기화 목록(MIL) 사용
Ray::Ray(const glm::vec3& origin, const glm::vec3& direction)
    : origin(origin), direction(direction), direction_inverse(1.0f / direction) {}
```

동작 차이는 없으나 MIL을 쓰면 불필요한 기본 생성 후 재대입을 피하고, 컴파일러가 초기화 순서를 더 명확히 최적화할 수 있음.

---

### D-18. 변수를 pointer/reference to const로 선언 가능 (Cppcheck v4 신규) ✅ 완료
**도구**: Cppcheck `constVariablePointer` / `constVariableReference`  
**건수**: 22건

| 파일 | 라인 | 변수 | 종류 |
|------|------|------|------|
| `asset.cc` | :17 | `temp` | pointer |
| `bvh.h` | :122, 145 | `node` (×2) | reference |
| `components/geometry_component.cc` | :39, 253 | `ib` (×2) | pointer |
| `components/name_component.cc` | :28 | `names` | pointer |
| `custom_material_provider.cc` | :180 | `material` | pointer |
| `engine.cc` | :33 | `factory` | pointer |
| `first_person_controls.cc` | :217, 226 | `actor` (×2) | pointer |
| `fly_controls.cc` | :178, 187 | `actor` (×2) | pointer |
| `orbit_controls.cc` | :445, 454 | `actor` (×2) | pointer |
| `providers/ktx2_reader.cc` | :538 | `iter` | pointer (`begin()/end()` → `cbegin()/cend()`로 교체) |
| `providers/ktx2_provider.cc` | :235 | `item` | reference |
| `providers/ktx2_provider.cc` | :89 | `texture` | pointer → **D-21과 겹쳐 변수 자체를 삭제로 처리** (아래 D-21 참고) |
| `resource_manager.cc` | :38, 45 | `iter` (×2) | reference |
| `resource_manager.cc` | :39, 46, 112 | `texture` (×3) | pointer |

```cpp
// 패턴 예시 (orbit_controls.cc:445)
// 변경 전
Actor* actor = Context::get().getObjectFactory()->get<Actor>(actor_id);
// 변경 후 (해당 스코프에서 non-const 멤버 호출이 없다면)
const Actor* actor = Context::get().getObjectFactory()->get<Actor>(actor_id);
```

전 건 각 위치에서 해당 변수를 통해 non-const 멤버 함수를 호출하거나 값을 변경하지 않는지(예: `engine->destroy(const T*)` 오버로드 존재 여부, getter의 `const` 여부) 개별 확인 후 `const` 추가. 코드 적용 완료.

---

### D-19. raw loop → 표준 알고리즘 (Cppcheck v4 신규) ✅ 완료
**도구**: Cppcheck `useStlAlgorithm`  
**건수**: 8건

| 파일 | 라인 | 제안 알고리즘 |
|------|------|---------------|
| `asset_impl.cc` | :78, 109 | `std::copy` (×2) |
| `components/geometry_component.cc` | :50, 637 | `std::transform` (×2) |
| `custom_material_provider.cc` | :200 | `std::transform` |
| `providers/ktx2_reader.cc` | :529 | `std::any_of` |
| `providers/ktx2_provider.cc` | :137, 236 | `std::find_if` (×2) |

```cpp
// ktx2_reader.cc:529 예시 — 변경 전
for (Texture::InternalFormat const fmt : requested_formats_) {
  if (fmt == format) return Result::kFormatAlreadyRequested;
}

// 변경 후
if (std::any_of(requested_formats_.begin(), requested_formats_.end(),
                [format](auto fmt) { return fmt == format; })) {
  return Result::kFormatAlreadyRequested;
}
```

기능은 동일하며 가독성/의도 명확화 목적. 성능 차이는 미미함.

---

### D-20. 변수/인자가 outer scope를 shadow (Cppcheck v4 신규) ✅ 완료
**도구**: Cppcheck `shadowVariable` / `shadowArgument`  
**건수**: 7건

| 파일 | 라인 | 내용 |
|------|------|------|
| `orbit_controls.cc` | :483 | 인자 `target`이 outer 멤버를 shadow |
| `ray.cc` | :23, 36, 49 | 인자 `direction`이 outer 멤버를 shadow (×3) |
| `providers/ktx2_reader.cc` | :788 | 지역 변수 `info`가 outer 변수를 shadow (A-7에서 다룬 `FinalFormatInfo info`와 별개 지역변수) |
| `resource_manager.cc` | :148, 161 | 지역 변수 `iter`가 outer 변수를 shadow (×2) |

의도적으로 같은 이름을 재사용한 경우가 대부분(예: 멤버와 동일한 의미의 파라미터)이라 실질 버그는 아니지만, 가독성을 위해 이름 구분 권장 (예: `iter` → `inner_iter`, 파라미터 `direction` → `dir`).

---

### D-21. 기타 개별 스타일 항목 (Cppcheck v4 신규) ✅ 완료 (6건 적용 / 1건 검토 후 유지)
**건수**: 7건

| 파일 | 라인 | 도구/내용 | 처리 |
|------|------|-----------|------|
| `ibl.cc` | :264 | `style` — 변수 `num_levels`의 스코프를 좁힐 수 있음 | ✅ 적용 — 함수 스코프에서 실제 사용되는 내부 `{}` 블록 안으로 선언 이동 |
| `providers/ktx2_reader.cc` | :713 | `style` — 멤버 함수 `asyncDestroy`가 static일 수 있음 | ✅ 적용 — `Ktx2Reader`가 `src/` 내부 클래스(비공개)라 `static` 추가. 호출부는 모두 `reader->asyncDestroy(...)` 형태라 static 메서드도 동일 문법으로 호출 가능, 영향 없음 |
| `providers/ktx2_reader.h` | :51 | `style` — `Ktx2Reader` 생성자가 인자 1개인데 `explicit` 없음 | ✅ 적용 — `explicit` 추가. 암묵적 변환 형태 호출부 없음 확인 |
| `providers/ktx2_reader.cc` | :42 | `style` — 구조체 멤버 `FinalFormatInfo::name`이 사용되지 않음 | **보류 + 억제** — 코드 추적 결과 `#if BASISU_FORCE_DEVEL_MESSAGES` 블록(825~828번 줄) 안에서 `info.name`을 로그로 출력하는 디버그 전용 필드로 확인됨(주석에도 "for debug purposes only" 명시). 해당 매크로가 기본 빌드에서 꺼져 있어 cppcheck가 미사용으로 오인. 삭제하지 않고 `// cppcheck-suppress unusedStructMember` 추가로 재스캔 시 재발견되지 않도록 처리 |
| `providers/ktx2_provider.cc` | :89 | `style` — 변수 `texture`가 대입만 되고 이후 사용되지 않음 | ✅ 적용 — 죽은 변수 삭제 (D-18의 같은 위치 항목과 동일 지점, 삭제로 두 항목 동시 해소) |
| `text/freetype_font.cc` | :38, 42 | `style` — `isSpace`, `isNewline` 멤버 함수가 static일 수 있음 (×2) | ✅ 적용 — `static` 추가. 호출부(`typesetter.cc`)는 모두 `font->isSpace(...)` 형태라 영향 없음 |

---

### D-22. `[[nodiscard]]` 누락 — 헤더 대량 (Clang-Tidy v9 신규) ✅ 완료
**도구**: Clang-Tidy `modernize-use-nodiscard`  
**건수**: 1,376건

`.clang-tidy`의 `HeaderFilterRegex` 버그(6장 앞부분 참고) 수정 후 새로 노출된 대량 항목. D-4/D-7에서 개별 처리한 것은 이 중 극히 일부였고, 헤더 전체 기준으로는 1,376건. 거의 전부 헤더에 선언된 getter/조회성 함수.

**적용**: `run-clang-tidy -fix -checks="-*,modernize-use-nodiscard"`로 일괄 자동 적용.

**이슈 발견 및 수정**: 적용 후 `components/joint_component.h`에서 `[[nodiscard]] [[nodiscard]]` 형태의 중복 삽입 31건 발견(병렬 `-fix` 적용 과정의 레이스 컨디션으로 추정). `sed -i 's/\[\[nodiscard\]\] \[\[nodiscard\]\]/[[nodiscard]]/g'`로 일괄 정리 후 재확인 완료.

---

### D-23. `const` 선언 누락 — 헤더 대량 (Clang-Tidy v9 신규) ✅ 완료
**도구**: Clang-Tidy `misc-const-correctness`  
**건수**: 128건

E-1(`.cc` 파일 기준 100+건)과 동일 성격의 헤더 몫. E-1에서 정리한 "의도적 non-const 구분표"(루프 변수, 외부 API 전달용 등)를 동일 기준으로 적용.

**적용**: `run-clang-tidy -fix -checks="-*,misc-const-correctness"`로 일괄 적용. 재대입되는 변수에 잘못 `const`가 붙는 등의 오적용 사례 없이 정상 적용 완료.

---

### D-24. Narrowing Conversion — 헤더 대량 (Clang-Tidy v9 신규) ✅ 완료
**도구**: Clang-Tidy `bugprone-narrowing-conversions`  
**건수**: 90건

B-1(`.cc` 파일 기준)과 동일 패턴의 헤더 몫. **이 체크는 clang-tidy `-fix` 자동 수정을 지원하지 않아** 전 건 수동으로 `static_cast<T>()` 래핑.

| 파일 | 건수 | 패턴 |
|------|------|------|
| `component_factory.h` | 23 | `Entity::import(id)` 인자 캐스트 |
| `geometries/capsule.h` | 19 | 루프 인덱스(`i`,`j`)/세그먼트 수 곱셈·나눗셈 캐스트 |
| `geometries/extrude.h` | 17 | `_addVertex(a/b/c/d)` 인자, `next_index = vertices_.size()` 등 |
| `geometries/box.h` | 8 | 세그먼트 분할/uv 계산 |
| `geometries/plane.h` | 6 | 상동 |
| `geometries/torus.h` | 4 | 상동 |
| `geometries/cylinder.h` | 3 | 상동 |
| `bvh.h` | 3 | `node.offset`/`node.count` 캐스트 |
| `viewport.h` | 2 | `width` 계산(`std::min(...) - left`) |
| `geometries/sphere.h` | 2 | 정점 수 계산 (A-17과 별개 지점) |
| `asset_impl.h` | 1 | `actors_.begin() + mesh_count_` iterator 산술 |
| `physics_context.h` | 1 | `kTimestep * kAccuracy` |
| `shape_utils.h` | 1 | `contour.size()` 캐스트 |

```cpp
// 패턴 예시 (geometries/box.h)
// 변경 전
vfloat u = ix / segment_width;
// 변경 후
vfloat u = static_cast<vfloat>(ix) / static_cast<vfloat>(segment_width);
```

**검증**: 수정 후 `bugprone-narrowing-conversions` 체크만 활성화한 재스캔에서 잔여 경고 0건 확인 완료(2026-07-02).

---

### D-25. 네이밍 컨벤션 — 헤더 대량 (Clang-Tidy v9 신규) ✅ 완료
**도구**: Clang-Tidy `readability-identifier-naming`  
**건수**: 63건

C-5(`.cc` 기준 7건)와 동일 성격의 헤더 몫.

**적용 전 예외 처리 (서드파티 심볼 보호)**: `providers/ktx2_reader.h:32`의 `class ktx2_transcoder;`는 BasisU 서드파티 라이브러리 타입의 전방선언 — 일괄 rename 대상에 걸리면 실제 라이브러리 심볼명과 어긋나 링크가 깨짐. `-fix` 적용 전 `// NOLINT(readability-identifier-naming)`을 선제적으로 추가해 보호.

**대표 사례**:

| 파일 | 변경 | 비고 |
|------|------|------|
| `actor.h` | `last_error_` → `last_error` | 멤버 네이밍 정정 |
| `material_component.h` | `_setMap` → `setMap`, `_setUvMatrix` → `setUvMatrix` | `protected` 메서드가 private 전용 `_` 접두사를 잘못 사용하던 것 정정 |
| `actor_exporter.h` | private 메서드 54건 | `_` 접두사 추가 |
| `custom_material_provider.h` | 메서드 다수 rename | 호출부 전체 정상 반영 확인 |

**적용**: `run-clang-tidy -fix -checks="-*,readability-identifier-naming"`로 일괄 적용 후 호출부(`.cc`) 자동 반영 여부 확인 완료.

---

### D-26. Rule of Five 미준수 — 헤더 전반 (Clang-Tidy v9 신규) ✅ 완료
**도구**: Clang-Tidy `cppcoreguidelines-special-member-functions` (+ 근본 원인이 같은 `bugprone-exception-escape` 3건 통합)  
**건수**: 40건 (40개 클래스) + 예비 문서 A-16(가칭) 예외탈출 3건 통합 = 43개 클래스

C-2(자원 소유 클래스 6건)에서 다룬 패턴이 헤더 전반에 훨씬 넓게 존재. 자동 수정 미지원 — 클래스별로 실제 자원 소유/복사 의미를 코드에서 확인 후 수동 적용.

**통합 3건 (`bugprone-exception-escape`, 근본 원인 동일)**: `keyframe_track.h`(`KeyframeTrack`), `components/collider_component.h`(`ColliderComponent`), `components/rigidbody_component.h`(`RigidbodyComponent`) — 셋 다 소멸자/복사/이동을 하나도 명시적으로 선언 안 해서 컴파일러가 암묵 생성했고, clang-tidy가 그 암묵 생성분의 noexcept 여부를 정적으로 증명 못 해 "예외 가능"으로 보수적 판단한 것(D-26 나머지 40건과 동일 근본 원인).
- `KeyframeTrack`(공개 API, `std::vector<KeyframeTrack>`로 값 복사되며 사용됨 확인) → 복사/이동 전부 `= default` 명시.
- `ColliderComponent`/`RigidbodyComponent`(둘 다 `Component` 파생) → `Component`가 이미 복사 delete/이동 default로 처리돼 있어 파생 클래스도 암묵적으로 동일하게 동작 중이었음(기능적으로는 문제 없었음) — `~override = default` 소멸자만 명시해 clang-tidy가 증명 가능하도록 정리(`ParticlesComponent`와 동일 패턴).

**⚠️ MSVC C++20 aggregate-initialization 함정**: `CMakeLists.txt`에서 MSVC만 `/std:c++latest`(C++20+)로 빌드하고 나머지 플랫폼은 `-std=c++17`. C++20부터는 생성자를 하나라도 선언(`= delete` 포함)하면 그 타입은 aggregate 자격을 잃는 반면, C++17은 user-*provided* 생성자만 aggregate 자격을 배제하고 defaulted/deleted는 영향 없음. `asset_impl.h`의 `SourceAsset`이 `new SourceAsset{hierarchy}` 형태의 aggregate 초기화로 생성되고 있었는데, 여기 단순히 복사/이동 생성자만 `= delete` 추가했다면 **MSVC 빌드만 깨지는** 문제가 발생했을 것. 명시적 생성자(`explicit SourceAsset(cgltf_data* h) : hierarchy(h) {}`)를 먼저 추가해 aggregate 자격을 없앤 뒤 Rule of Five를 적용해 우회.

**그룹별 처리**:

| 그룹 | 처리 | 대상 클래스 (총 40개) |
|------|------|------------------------|
| 1. 이동 가능 / 복사 불가 (2) | 복사 delete + 이동 default | `component.h`(`Component`), `components/particles_component.h`(`~ParticlesComponent() override = default`만 추가) |
| 2. 복사·이동 모두 불가 (19) | 전부 delete, 소멸자 명시 | `body.h`, `cone_joint.h`, `controls.h`, `curve.h`, `distance_joint.h`, `extrude_geometry.h`(`UVGenerator`), `first_person_controls.h`, `fixed_joint.h`, `fly_controls.h`, `hinge_joint.h`, `hitbox_2d.h`(예외 — 아래 참고), `joint.h`, `map_controls.h`, `point_joint.h`, `sixdof_joint.h`, `slider_joint.h`, `swing_twist_joint.h`, `vehicle.h`, `component_manager_interface.h` |
| 3. 복사·이동 불가 (싱글턴/리소스 소유, 15) | 전부 delete | `actor_exporter.h`, `asset_impl.h`(`AssetImpl` + 중첩 `SourceAsset`, 위 aggregate 함정 참고), `component_factory.h`, `ibl.h`, `image.h`, `instance_manager.h`, `object_factory.h`, `renderer_impl.h`, `rigid_body.h`(예외 — 아래 참고), `scene_impl.h`, `text/freetype_font.h`, `text/text_field.h`, `text/typesetter.h`, `view_impl.h` |
| 4. 소멸자/이동만 누락 (4) | 누락분만 추가 | `component_manager.h`(`~ComponentManager() override = default`), `context.h`(`~Context() = default`), `custom_material_provider.h`(이동 delete), `resource_manager.h`(이동 delete) |

**예외 3건** (일괄 패턴을 그대로 적용하지 않고 실제 코드 확인 후 다르게 처리):
- `hitbox_2d.h` — 다른 클래스와 달리 핸들이 아닌 **순수 값 타입**으로 쓰여서, 복사/이동을 `delete`하지 않고 전부 `= default`로 명시(그룹 2 나머지와 반대 방향).
- `rigid_body.h` — C-2의 `VehicleData`와 동일하게 Jolt 네이티브 핸들을 실제로 소유하는 리소스 오너라 복사/이동 전부 `delete`.
- `asset_impl.h::SourceAsset` — 위 MSVC aggregate-init 함정으로 명시적 생성자 선추가 필요.

**⚠️ 재스캔(v10)에서 발견된 회귀 버그 5건 — 빌드 에러 (전부 수정 완료)**

D-22~D-27 코드 수정 완료 후 `clangtidy_v10.txt`로 전체 재스캔한 결과, 새 컴파일 에러 29건 발생(경고가 아니라 **빌드가 깨지는 에러**). 원인은 동일: 대상 클래스에 **기존에 사용자 선언 생성자가 전혀 없어 암묵적 기본 생성자에 의존하고 있었는데**, 복사/이동 생성자를 `= delete`로 추가하는 순간(설령 delete라도 "사용자 선언"으로 간주되어) 암묵적 기본 생성자 생성이 함께 억제되어 버림. 아래 5개 클래스가 실제로 기본 생성되고 있던 지점이 존재해 빌드 에러로 표면화됨:

| 파일 | 클래스 | 실제 기본 생성 지점 | 수정 |
|------|--------|----------------------|------|
| `curve.h` | `Curve` | `CatmullRomCurve`/`CubicBezierCurve`/`EllipseCurve`/`LineCurve`/`QuadraticBezierCurve`/`SplineCurve`/`CurvePath` 등 7개 파생 클래스 생성자가 베이스 초기화 없이 암묵적 기본 생성에 의존 | `Curve() = default;` 추가 |
| `component_manager_interface.h` | `ComponentManagerInterface` | `ComponentManager<T>`(18개 컴포넌트 타입 전부)가 베이스 초기화 없이 암묵적 기본 생성에 의존 | `ComponentManagerInterface() = default;` 추가 |
| `extrude_geometry.h` | `UVGenerator` | 파생 클래스 `WorldUVGenerator`가 (컨테이너 등에서) 기본 생성됨 | `UVGenerator() = default;` 추가 |
| `object_factory.h` | `ObjectFactory` | `context.cc:233`의 `std::make_unique<ObjectFactory>()` | `ObjectFactory() = default;` 추가 |
| `text/typesetter.h` | `Typesetter` | `text_field.cc:5`의 `std::make_unique<Typesetter>()` | `Typesetter() = default;` 추가 |

**교훈**: Rule of Five 적용 시 복사/이동을 `delete`하는 클래스라도, 그 클래스(또는 파생 클래스)가 어딘가에서 기본 생성(`make_unique<T>()`, 파생 클래스의 암묵적 베이스 초기화, 컨테이너의 기본 생성 등)되고 있다면 **기본 생성자를 명시적으로 `= default`로 선언해줘야 함** — 자동 수정이 지원되지 않는 체크라 이런 부작용은 실제 컴파일까지 해봐야 드러남. 전 40개 클래스에 대해 `bugprone-narrowing-conversions`처럼 좁게 재스캔한 것이 아니라 **전체 재빌드에 준하는 clang-tidy 전체 재스캔(v10)** 을 돌린 덕분에 발견. `clangtidy_v9.txt`(D-26 적용 전) 대비 v10의 신규 컴파일 에러(299−270=29건)와 정확히 일치.

---

### D-27. 부호 있는 정수 비트연산 — 헤더 대량 (Clang-Tidy v9 신규) ✅ 완료
**도구**: Clang-Tidy `hicpp-signed-bitwise`  
**건수**: 26건

A-8과 동일 패턴. `enum`/`enum class`로 비트 플래그를 정의하는 4개 파일에 분산.

| 파일 | 건수 | 원인 / 수정 |
|------|------|--------------|
| `components/joint_component.h` | 5 | `enum FLAGS : uint32_t`로 underlying type은 있었으나 시프트량(`<< 0`)이 부호 있는 `int` 리터럴이라 잔존 → `1u << 0u`처럼 좌우 리터럴 모두 unsigned화 |
| `components/particles_component.h` | 3 | `enum class Flags : vuint32`도 동일하게 시프트량에 `u` 누락 → 동일 수정 |
| `components/rigidbody_component.h` | 12 | `enum Flags`에 underlying type 자체가 없어 `1u`를 붙여도 enum 값이 `int`로 추론됨 → `enum Flags : vuint32`로 타입 고정 + 시프트량에도 `u` 추가 |
| `random.h` | 1 | `nextFloat()`의 `>> 9`(시프트량) → `>> 9u` |

```cpp
// components/rigidbody_component.h — 변경 전
enum Flags {
  kEmpty = 0,
  kDisableDeactivation = 1 << 0,
  kStartDeactivated = 1 << 1,
};

// 변경 후
enum Flags : vuint32 {
  kEmpty = 0,
  kDisableDeactivation = 1u << 0u,
  kStartDeactivated = 1u << 1u,
};
```

**교훈**: `hicpp-signed-bitwise`를 완전히 해소하려면 (1) enum에 명시적 unsigned underlying type 지정과 (2) 시프트 연산의 좌·우변 리터럴 모두에 `u` 접미사, 두 가지가 다 필요함 — 하나만 하면 다른 하나에서 경고가 남는다.

---

### D-28. 개별 소량 카테고리 — 헤더 (Clang-Tidy v9 신규, 19종·100건) ✅ 완료

D-22~D-27 등 대량 카테고리를 제외한 나머지 헤더 전용 신규 발견. 대부분 기존 항목(C-1, D-11, D-8 등)과 동일 패턴의 헤더 몫이라 동일 방침을 적용. 체크별로 정리:

**자동 수정 적용 (2종, 27건)**

| 체크 | 건수 | 내용 |
|------|------|------|
| `modernize-use-override` | 14 | `override` 누락 추가(9개 joint 계열 헤더) + `virtual`+`override` 중복 제거(`physics_context.h` 4곳, D-8과 동일 패턴) |
| `modernize-use-emplace` | 13 | `push_back({...})` → `emplace_back(...)` (`box.h`, `capsule.h`, `torus.h`, `shape_utils.h`) |

`run-clang-tidy -fix -checks="-*,modernize-use-override,modernize-use-emplace"`로 일괄 적용, 재검증 0건.

**NOLINT 처리 — 공개 API/불가피 패턴 (C-1, B-3, F-4, F-2, C-6과 동일 방침, 3종, 26건)**

| 체크 | 건수 | 내용 |
|------|------|------|
| `bugprone-easily-swappable-parameters` | 17 | `Box`/`Capsule`/`Cylinder`/`Plane`/`Sphere`/`Torus`/`Ray`/`AABB`/`Hitbox2D`/`Viewport` 등 지오메트리·수학 타입의 공개 생성자(radius/height/segments류) + `_buildPlane`/`_addCap`/`_sidewalls` 등 델리케이트한 내부 정점 계산 헬퍼. C-1과 동일하게 공개 API·위험도 낮은 내부 알고리즘은 재구조화 대신 NOLINT |
| `cppcoreguidelines-pro-type-reinterpret-cast` | 3 | `bvh.h`(원시 바이트 버퍼→`Node*`/`vuint32*` 수동 배치), `rigid_body.h`(`glm::mat4`↔`JPH::Float4` 동일 레이아웃 type-pun). B-3과 동일 패턴 |
| `cppcoreguidelines-virtual-class-destructor` | 2 | `base_api.h`(`BaseAPI`), `ktx2_reader.h`(`Async`, 클래스 선언 줄이 경고 위치라는 C-6의 교훈대로 위치 재확인). 둘 다 protected virtual 소멸자로 "파생 클래스를 통해서만 소멸 가능"하게 만드는 의도적 팩토리 패턴 — C-6과 동일 방침 |
| `cppcoreguidelines-avoid-c-arrays` | 5(중 1) | `ibl.h`의 `bands_[9]`는 Filament C API에 포인터로 전달돼서 NOLINT(나머지 4건은 아래 실제 수정 참고) |
| `cppcoreguidelines-pro-bounds-array-to-pointer-decay` | 1 | `ibl.h`의 `getSphericalHarmonics()`가 `bands_`를 포인터로 반환 — 위와 동일 이유 |

**실제 코드 수정 (14종, 47건)**

| 체크 | 건수 | 내용 |
|------|------|------|
| `performance-enum-size` | 17(중 14) | 값 범위에 맞춰 `vuint8`(음수 있는 `orbit_controls.h::State`는 `vint8`)로 축소. **예외 3건**: `joint_component.h`/`particles_component.h`/`rigidbody_component.h`의 비트플래그 enum은 D-27에서 이미 `: vuint32`로 고정한 것 — 축소하면 비트연산 시 `int`로 승격되어 `hicpp-signed-bitwise`가 재발하므로 NOLINT 유지 |
| `cppcoreguidelines-avoid-c-arrays` | 5(중 4) | `bvh.h::stack`, `physics_context.h::mObjectToBroadPhase`, `rigid_body.h::prev_wheel_positions/rotations` → `std::array`로 교체(순수 인덱스 접근만 하는 배열이라 안전) |
| `performance-unnecessary-value-param` | 6 | `AnimationMixer`/`FlyControls`/`OrbitControls`의 `std::function` 콜백 세터에서 대입 시 `std::move()` 적용 (시그니처는 값 전달 그대로 유지, 내부만 이동으로 변경) |
| `google-readability-casting` | 6 | `geometries/capsule.h`의 `(vfloat)i`/`(vfloat)j` C스타일 캐스트 → `static_cast`(D-24에서 놓친 잔여분) |
| `hicpp-multiway-paths-covered` + `bugprone-switch-missing-default-case` | 4+4 | `aabb.h::corner()`, `gltf_enums.h`의 3개 switch문에 `default:` 추가(A-12와 동일 패턴) |
| `readability-simplify-boolean-expr` | 2 | `aabb.h::isValid()`, `math_utils.h::rayTriangleIntersects()` — De Morgan 법칙 적용(D-5와 동일 패턴) |
| `misc-no-recursion` | 2 | `bvh.h::subdivide()`/`intersects()` — 재귀 트리 순회를 이미 파일에 있던 `intersectsFirst()`의 고정 크기 스택(`std::array<vuint32, 64>`) 패턴으로 통일해 반복문으로 전환(A-6과 동일 방침, 외부 호출 시그니처는 그대로 유지) |
| `performance-move-const-arg` | 1 | `component_manager.h`의 `std::move(entities_.back())` — `utils::Entity`가 trivially-copyable이라 `std::move`가 무의미, 제거 |
| `google-readability-namespace-comments` | 1 | `ktx2_reader.h` 네임스페이스 종료 주석이 `grapi::base`를 가리키고 있었음 → `grapi::base::providers`로 정정 |
| `google-explicit-constructor` | 1 | `geometries/capsule.h`의 `Capsule(vfloat radius = 1, ...)` — 전 인자 디폴트값이 있어 단일 인자로도 호출 가능 → `explicit` 추가 |
| `google-build-namespaces` | 1 | `component_factory.h`의 헤더 내 익명 네임스페이스(23개 `getXxxComponent(BaseID)` 래퍼 함수) — 78개 포함 파일마다 중복 컴파일되는 문제라 익명 네임스페이스를 걷어내고 각 함수에 `inline` 추가(링커가 중복 정의를 병합, 동작 동일) |
| `modernize-use-equals-default` | 0 | 발견 당시 이미 D-26 작업 중 자연스럽게 해소됨(별도 조치 불필요) |

```cpp
// bvh.h — misc-no-recursion 수정 예 (intersects, 기존 intersectsFirst 패턴과 통일)
// 변경 전 — 재귀
void intersects(const T& primitive, vuint32 node_index, const Callback& callback) const {
  const Node& node = nodes[node_index];
  if (!node.aabb.intersects(primitive)) return;
  if (node.isLeaf()) { for (...) callback(...); }
  else {
    intersects(primitive, node.left, callback);
    intersects(primitive, node.left + 1, callback);
  }
}

// 변경 후 — 고정 크기 스택 기반 반복 (파일 내 intersectsFirst()와 동일 패턴)
void intersects(const T& primitive, vuint32 root_index, const Callback& callback) const {
  std::array<vuint32, 64> stack{};
  vuint32 stack_count = 0;
  stack[stack_count++] = root_index;
  while (stack_count > 0) {
    const vuint32 node_index = stack[--stack_count];
    const Node& node = nodes[node_index];
    if (!node.aabb.intersects(primitive)) continue;
    if (node.isLeaf()) { for (...) callback(...); }
    else {
      stack[stack_count++] = node.left;
      stack[stack_count++] = node.left + 1;
    }
  }
}
```

> **⚠️ D-28 작업 중 발견한 회귀 버그 2건 — 재검증 과정에서 즉시 발견·수정**
>
> 1. **`ColliderComponent`/`RigidbodyComponent` 이동 억제 (빌드 에러)**: D-26 통합 작업(구 A-16, 예외탈출 3건 처리) 때 두 클래스에 `~override = default` 소멸자만 추가했는데, 소멸자를 사용자 선언하면 암묵적 이동 생성자/이동 대입 생성이 억제됨. `ComponentManager<T>::destroy()`의 swap-remove(`components_[index] = std::move(components_.back())`)가 이동 연산자를 못 찾고 `const&` 오버로드로 폴백을 시도하다 베이스 클래스(`Component`)의 `= delete`된 복사 대입에 걸려 **컴파일 에러** 발생. 전체 재스캔(`clangtidy_v12.txt`)에서 `component_manager.h`/`component_factory.cc`의 신규 컴파일 에러로 발견 → 두 클래스에 `이동 = default` 명시적으로 추가해 해결(복사는 계속 delete 유지). D-26의 5건 회귀(본 문서 D-26 절 참고)와 동일한 유형의 함정.
> 2. **`gltf_enums.h` 분기 중복 (`bugprone-branch-clone`)**: 위 `switch` `default:` 케이스 추가 시, 마지막 `case`와 완전히 동일한 반환문을 가진 `default:`를 별도로 작성해 "두 분기가 동일하다"는 새 경고가 발생. `case GL_LINEAR_MIPMAP_LINEAR: default: return ...;`처럼 두 라벨이 반환문 하나를 공유하도록(fallthrough) 합쳐서 해결 — 동작은 동일, 중복 코드만 제거.
>
> 두 건 다 **본 카테고리를 고치다가 생긴 부작용**이며, D-22~D-28 전체를 마친 뒤 처음부터 다시 전체 재스캔(v12~v14)해서 잡아냄. 부분 스캔(체크 단위)만으로는 놓칠 수 있는 상호작용이라, 대량 작업 이후엔 전체 재스캔이 필수라는 교훈을 다시 확인.

**최종 검증**: `clangtidy_v14.txt`(전체 재스캔) 기준 `base/` 코드 경고 **0건**. 잔여 경고 3건은 전부 `external/filament`(서드파티) `bugprone-forward-declaration-namespace` — 우리 소관 아님. 에러 270건은 v9 때부터 있던 `type_traits`/`maybe_unused` 환경 노이즈로 D-22~D-28 작업과 무관(불변 확인).

---

## 7. E등급 — 대량 스타일 (기계적 적용 가능)

### E-1. `const` 선언 누락 (misc-const-correctness) ✅ 완료
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

### F-1. `pro-bounds-pointer-arithmetic` (확인됨) ✅ 완료
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

### F-2. `pro-bounds-array-to-pointer-decay` (확인됨) ✅ 완료
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

### F-3. `pro-type-reinterpret-cast` — cgltf 관련 (확인됨) ✅ 완료
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

### F-4. `avoid-c-arrays` (확인됨) ✅ 완료
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

### F-5. `duplInheritedMember` — kTypeInfo 패턴 (확인됨) ✅ 완료
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

### F-6. `malloc`/`free` 직접 사용 — cgltf C API 패턴 (확인됨) ✅ 완료
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

### F-7. Cppcheck 정보성 메시지 — "Limiting analysis of branches" (Cppcheck v4 신규, 처리 불필요) ✅ 확인 완료
**도구**: Cppcheck `information`  
**건수**: 21건  
**위치**: `asset.cc`, `asset_impl.cc`, `capsule.cc`, `catmull_rom_curve.cc`, `components/camera_component.cc`, `components/geometry_component.cc`, `components/light_component.cc`, `components/name_component.cc`, `curve.cc`, `curve_path.cc`, `custom_material_provider.cc`, `ellipse_curve.cc`, `first_person_controls.cc`, `hitbox_2d.cc`, `ibl.cc`, `orbit_controls.cc`, `plane.cc`, `providers/ktx2_reader.cc`, `providers/ktx2_provider.cc`, `resource_manager.cc`, `sphere.cc` (각 파일당 1건, 라인 번호 `0`)

```
파일명(0): information: Limiting analysis of branches. Use --check-level=exhaustive to analyze all branches.
```

> **경고 설명**: 실제 코드 결함이 아니라 Cppcheck가 기본 분석 레벨(`--check-level=normal`)에서 해당 함수의 분기 조합을 전부 검사하지 않았다는 **안내 메시지**. `severity`가 `information`이지 `warning`/`style`/`error`가 아님.

**처리**: 조치 불필요. 전 분기를 검사하려면 `--check-level=exhaustive` 옵션으로 재스캔 가능하나, 분석 시간이 크게 늘어나고 해당 함수들은 이미 다른 항목(A-3, A-15 등)에서 개별 확인을 거쳤으므로 현재는 무시.

---

### F-8. Union `= {}` 초기화 직후 대입 — Redundant initialization (Cppcheck v4 신규, 오탐/의도적 패턴) ✅ 확인 완료
**도구**: Cppcheck `style` — "Redundant initialization for 'value'. The initialized value is overwritten before it is read."  
**건수**: 2건  
**위치**: `random.h:48` (`nextInt()`), `random.h:77` (`nextFloat()`)

```cpp
constexpr vint64 nextInt() {
  union {
    vuint64 u;
    vint64 i;
  } value = {};        // ← Cppcheck가 "곧바로 덮어써서 불필요"로 지적
  value.u = nextUint();
  return value.i;
}
```

`value = {}`는 union을 0으로 초기화해 `.u`에 값을 대입하기 전 미정의 상태로 두지 않으려는 의도적 안전 패턴(그리고 `constexpr` 함수에서 활성 멤버가 아닌 값을 읽는 것을 피하기 위한 초기화). 실질적으로 대입 직후 값이 덮어써지는 건 맞지만 UB 방지 목적이 있어 제거하지 않는 것이 안전.

**처리**: 코드 변경 없이 유지 + 재스캔 시 반복 재발견 방지를 위해 두 위치 모두 `// cppcheck-suppress redundantInitialization` 인라인 억제 추가. ID는 `--errorlist`로 실존 여부 확인 후 적용(A-5의 ID 실수 이후 추측 대신 항상 실측).

> **⚠️ v7 재스캔에서 발견된 문제 — 억제 주석 위치 오류**: 최초 적용 시 억제 주석을 `} value = {};` 선언 줄에 달았으나, v7 재스캔 결과 경고가 **그대로 재발생**(`random.h(49)`, `random.h(79)`)했고 동시에 `information: Unmatched suppression: redundantInitialization`(`random.h(48)`, `random.h(78)`)까지 나타남.  
> **원인**: cppcheck는 이 체크를 "선언 줄"이 아니라 **값을 실제로 덮어쓰는 줄**(`value.u = nextUint();` 등)에서 보고함. ID는 맞았지만(A-5와 달리) 주석을 엉뚱한 줄에 달아서 매칭이 안 된 것 — "같은 줄 억제"는 정확히 경고가 찍히는 줄에 달아야 함을 재확인.  
> **수정**: 주석을 `} value = {};` 줄에서 실제 overwrite 줄(`value.u = nextUint();` / `value.u = 0x3f800000u | ...`)로 이동. v8 재스캔에서 경고 및 `Unmatched suppression` 모두 사라짐을 확인 완료.

```cpp
// 최종 적용본
constexpr vint64 nextInt() {
  union {
    vuint64 u;
    vint64 i;
  } value = {};
  value.u = nextUint();  // cppcheck-suppress redundantInitialization
  return value.i;
}
```

> **교훈 (A-5와 함께)**: cppcheck 인라인 억제는 (1) 정확한 체크 ID, (2) 경고가 실제로 찍히는 정확한 줄 — 이 두 가지가 모두 맞아야 동작한다. 둘 중 하나라도 틀리면 억제는 조용히 실패하고 `Unmatched suppression` 정보 메시지만 남는다. 반드시 재스캔으로 검증할 것.

---

### F-9. `use-after-move` 오탐 — 베이스 서브오브젝트 이동과 파생 멤버 이동 혼동 (Clang-Tidy v9 신규, 오탐 확인) ✅ 확인 완료
**도구**: Clang-Tidy `bugprone-use-after-move`  
**위치**: `components/particles_component.h:177` (`ParticlesComponent(ParticlesComponent&& other)`)

```cpp
ParticlesComponent(ParticlesComponent&& other) noexcept
    : Component(std::move(other)) {          // ← 여기서 'other' 이동됐다고 경고
  particle_buffer_ = std::move(other.particle_buffer_);  // ← "이동 후 재사용" 오탐
  alive_list_ = std::move(other.alive_list_);
  ...
```

**분석**: `Component(std::move(other))`는 `other` 전체가 아니라 **베이스 클래스(`Component`) 서브오브젝트만** 슬라이싱해서 이동함(`entity_`/`dirty_flag_` 두 멤버로 구성된 별개 서브오브젝트). 이후 접근하는 `other.particle_buffer_` 등은 전부 `ParticlesComponent` 자신의 멤버라 베이스 슬라이싱과 무관하게 아직 손 안 댄 상태 — 실제 UB 아님. clang-tidy가 "베이스 서브오브젝트만 이동됨"과 "객체 전체가 이동됨"을 구분하지 못해 발생하는 알려진 오탐 패턴.

**처리**: 코드 변경 없이 유지 + `// NOLINT(bugprone-use-after-move)` 인라인 억제 추가(재스캔 시 재발견 방지).

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

> **v6 스캔 (2026-07) 기준 유저 코드 경고 0건 확인 — 전 항목 완료**  
> **Cppcheck v4 재스캔 (2026-07)**: Clang-Tidy와 별개로 Cppcheck만 재스캔한 결과 신규 94건 발견 — 분류·문서화 및 A-15 코드 수정까지 전 건 완료 (아래 5단계 참고)

```
1단계 — 즉시 (A등급)
─────────────────────────────────────────────────────────────────
✅ vehicle_component.cc:940 — if 조건 대입 오류 (= vs !=) (A-1)
✅ vehicle_component.cc:144 — 동일한 true/false 분기 로직 수정 (A-2)
✅ geometry_component.cc:554-555 — else 분기 OOB 접근 수정 (A-3)
✅ ktx2_reader.cc:567,648 — malloc null 체크 추가 (A-4)
✅ asset_loader.cc:529,794 — 재귀 함수 반복 방식 전환 (A-6)
✅ ktx2_reader.cc:767 — FinalFormatInfo info{} 초기화 추가 (A-7)
✅ view_impl.cc, particles_component.cc, actor_exporter.cc 등 — signed bitwise 20건 수정 (A-8)
✅ asset_impl.cc:16 — 소멸자 예외 탈출 방지 try-catch 추가 (A-9)
✅ curve.cc:42 — 변환 순서 수정 (static_cast 위치 교정) (A-10)
✅ ibl.cc:194 — sscanf NOLINT(cert-err34-c) 처리 (A-11)
✅ first_person_controls.cc:19, fly_controls.cc:22 — switch default 추가 (A-12)
✅ actor_exporter.cc:319, raycaster.cc:15 — 재귀 함수 반복 방식 전환 (A-13)
✅ joint_component.cc:190 — 중복 분기 통합 (A-14)

2단계 — 단기 (B/C등급)
─────────────────────────────────────────────────────────────────
✅ bugprone-narrowing-conversions 134건 + v5 추가 4건 — static_cast 명시 완료 (B-1)
✅ bugprone-implicit-widening-of-multiplication-result 11건 — static_cast<vsize/ptrdiff_t> 완료 (B-2)
✅ cppcoreguidelines-pro-type-reinterpret-cast 29건 — C API 경계 NOLINT 완료 (B-3)
✅ cppcoreguidelines-pro-type-const-cast 4건 — NOLINT 완료 (B-4)
✅ asset_loader.cc:523 — stringview.data() → emplace_back(uri.data(), uri.size()) (B-5)
✅ extended_material_component.cc 16건 + ktx2_reader.cc 2건 + actor_exporter.cc 1건 — C 스타일 캐스트 교체 (B-6)
✅ scene_impl/physics_context/vehicle 6건 — int→ptr NOLINT(performance-no-int-to-ptr) (B-7)
✅ actor_exporter.cc 4건 — static_cast<void*> 명시 (B-8)
✅ ibl.cc:196 — NOLINT(cert-err34-c, cppcoreguidelines-pro-type-vararg) (B-9)
✅ bugprone-easily-swappable-parameters 31건 + v5 추가 4건 — 전 건 NOLINT 완료 (C-1)
✅ cppcoreguidelines-special-member-functions 3건 — Rule of Five 완료 (C-2)
✅ resource_manager.cc:54 — 복사 = delete 추가 (C-3)
✅ context.cc:67 — virtual + override 중복 제거 (C-4)
✅ readability-identifier-naming 7건 — 네이밍 수정 완료 (C-5)
✅ ktx2_reader.cc:469 — NOLINT(cppcoreguidelines-virtual-class-destructor) 클래스 선언 라인으로 이동 (C-6)

3단계 — 중기 (D등급 + F등급 정리)
─────────────────────────────────────────────────────────────────
✅ performance-avoid-endl 5건 — custom_material_provider.cc '\n' 교체 (D-1)
✅ modernize-use-emplace 3건 — push_back → emplace_back (D-2)
✅ modernize-use-equals-default — swing_twist_joint.cc, point_joint.cc (D-3)
✅ modernize-use-nodiscard — catmull_rom_curve.cc:24 [[nodiscard]] 추가 (D-4)
✅ readability-simplify-boolean-expr — plane.cc:141 DeMorgan 정리 적용 (D-5)
✅ modernize-use-equals-default 9건 — fixed/sixdof/hinge/slider/distance/cone_joint, body, vehicle (D-6)
✅ modernize-use-nodiscard 5건 — ktx2_provider.cc Queue 상태 조회 함수 (D-7)
✅ modernize-use-override 2건 — ktx2_provider.cc:24, ktx2_reader.cc:484 (D-8)
✅ modernize-make-unique 1건 — ktx2_provider.cc:250 (D-9)
✅ performance-unnecessary-value-param 2건 — curve_path.cc, ibl.cc const& 교체 (D-10)
✅ performance-enum-size 2건 — ktx2_provider.cc QueueItemState, TranscoderState uint8_t (D-11)
✅ readability-simplify-boolean-expr 5건 — texture/mesh/rigidbody/aabb/hitbox_2d (D-12)
✅ google-readability-todo 6건 — .clang-tidy에서 비활성화 (D-13)
✅ misc-unused-parameters 17건 — 파라미터 이름 제거 / body.cc 버그 수정 (D-14)
✅ google-build-using-namespace 2건 — ktx2_reader.cc NOLINT (D-15)
✅ F-1 278건 — .clang-tidy에서 cppcoreguidelines-pro-bounds-pointer-arithmetic 제거
✅ F-2 15건 — cgltf/Filament C API 배열 decay NOLINT 완료
✅ F-4 27건 — std::array 교체 7건 + NOLINT 19건 + 오탐 1건
✅ F-5 — cppcheck-suppressions.txt로 duplInheritedMember 일괄 억제
✅ F-6 74건 — .clang-tidy에서 cppcoreguidelines-no-malloc 제거

4단계 — 일괄 적용 (E등급)
─────────────────────────────────────────────────────────────────
✅ misc-const-correctness 100건+ — -fix 플래그로 일괄 적용

5단계 — Cppcheck v4 재스캔 신규 항목 (2026-07)
─────────────────────────────────────────────────────────────────
✅ ktx2_reader.cc — load()/FAsync::doTranscoding() 레벨별 offset/length 버퍼 범위 검증 추가 + 미사용 level_index_size 제거 (A-15)
✅ first_person_controls.h/fly_controls.h/map_controls.h — 소멸자 override 추가 3건 (D-8 추가분)
✅ getter 13건 — const& 리턴 9건 적용 + 공개 API 4건 보류(억제 주석 추가) (D-16)
✅ ray.h:36-38 — 생성자 초기화 목록 사용 (D-17)
✅ pointer/reference to const 22건 — 21건 const 추가 + 1건(ktx2_provider.cc:89) 삭제로 처리 (D-18)
✅ raw loop → 표준 알고리즘 8건 (D-19)
✅ outer scope shadow 7건 — 변수/인자명 구분 (D-20)
✅ 기타 개별 스타일 7건 — 6건 적용 + 1건(FinalFormatInfo::name, 디버그 전용 필드, 억제 주석 추가) 검토 후 유지 (D-21)
✅ curve.cc 쉼표 오탐 5건 — A-5와 동일, 억제 주석 추가 (재확인)
✅ Cppcheck 정보성 메시지 21건 — 조치 불필요 (F-7)
✅ random.h union 초기화 2건 — 조치 불필요, 의도된 패턴, 억제 주석 추가 (F-8)

6단계 — 사용자 빌드/재스캔 후 잔여 이슈 정리 (v5~v8, 2026-07)
─────────────────────────────────────────────────────────────────
✅ v5 재스캔 — A-5 억제 ID 오류(`suspiciousCommaExpression`→`constStatement`) 발견 및 수정
✅ v5 재스캔 — ktx2_reader.cc 세 번째 createTexture 오버로드의 잔여 미사용 변수(level_indices) 발견, 주석 처리로 보존
✅ v6 재스캔 — D-16/F-8/D-21 보류 7건에 억제 주석 추가(returnByReference/redundantInitialization/unusedStructMember), 잔여 28건이 의도적 보류와 일치함 확인
✅ v7 재스캔 — random.h 억제 주석 위치 오류(선언 줄 vs overwrite 줄) 발견 및 수정
✅ v8 재스캔 — base/ 잔여 경고 0건 확인 (정보성 메시지 21건만 남음), 최종 완료
```

---

## 11. 관련 문서 및 원시 결과

- [06-clang-tidy-guide.md](06-clang-tidy-guide.md) — Clang-Tidy 실행 가이드
- [07-verification-report.md](07-verification-report.md) — v1 스캔 결과 요약
- [08-cppcheck-guide.md](08-cppcheck-guide.md) — Cppcheck 실행 가이드
- 원시 결과: `C:\working\grapi-base\clangtidy_v2.txt`
- 원시 결과: `C:\working\grapi-base\cppcheck_result_v3.txt`
- 원시 결과: `C:\working\grapi-base\clangtidy_v5.txt` — 수정 후 재스캔, 유저 코드 경고 9건
- 원시 결과: `C:\working\grapi-base\clangtidy_v6.txt` — 전 항목 수정 후 재스캔, **유저 코드 경고 0건**
- 원시 결과: `C:\working\grapi-base\cppcheck_result_v4.txt` — Cppcheck 단독 재스캔(2026-07), 유저 코드(`base/`) 94건 → A-15, D-16~D-21, F-7, F-8로 분류·문서화
- 원시 결과: `C:\working\grapi-base\cppcheck_result_v5.txt` — 코드 적용 후 재스캔, A-5 억제 ID 오류 및 `ktx2_reader.cc` 잔여 미사용 변수 1건 발견
- 원시 결과: `C:\working\grapi-base\cppcheck_result_v6.txt` — 위 2건 수정 + 보류 항목 7건 억제 주석 추가 후 재스캔, 유저 코드(`base/`) 잔여 28건 전부 의도적 보류 항목과 일치 확인 (신규/누락 없음)
- 원시 결과: `C:\working\grapi-base\cppcheck_result_v7.txt` — `random.h` 억제 주석 위치 오류(선언 줄 vs overwrite 줄) 발견, D-16/D-21 억제는 정상 동작 확인
- 원시 결과: `C:\working\grapi-base\cppcheck_result_v8.txt` — `random.h` 억제 주석 위치 수정 후 최종 재스캔, `base/` 잔여 경고 **0건**(정보성 메시지 21건만 남음) — Cppcheck v4 재스캔 94건 전 항목 처리 완료 최종 확인
- 원시 결과: `C:\working\grapi-base\clangtidy_v9.txt` — `HeaderFilterRegex` 버그 수정 후 재스캔, 헤더 파일 기준 신규 findings 발견(고유 위치 1,833건). 잠재 버그 후보 6건 중 A-16/A-17 확인·수정 완료, 나머지는 오탐/기존 항목 통합
- [09-clangtidy-v9-header-findings.md](09-clangtidy-v9-header-findings.md) — v9 신규 findings 전체 분류 예비 문서 (대량 카테고리 D-22~D-27, 개별 소량 D-28 — 전부 본 리포트에 병합 완료)
- 원시 결과: `C:\working\grapi-base\clangtidy_v10.txt` — D-24(narrowing) 코드 수정 직후 재스캔, D-26(Rule of Five) 관련 컴파일 에러 29건 신규 발견(암묵 기본 생성자 억제 회귀)
- 원시 결과: `C:\working\grapi-base\clangtidy_v11.txt` — D-26 회귀 5건 수정 후 재스캔, `base/` 코드 경고 0건 확인 + 4장 개별 소량 카테고리(D-28) 19종 100건 원본 데이터
- 원시 결과: `C:\working\grapi-base\clangtidy_v12.txt` — D-28 코드 수정 완료 후 전체 재스캔, `ColliderComponent`/`RigidbodyComponent` 이동 억제 회귀(컴파일 에러) + `bugprone-branch-clone`/`performance-noexcept-move-constructor`/`bugprone-use-after-move` 신규 발견
- 원시 결과: `C:\working\grapi-base\clangtidy_v13.txt` — 위 회귀 수정 후 재스캔, `bugprone-exception-escape` 3건 잔존 확인(noexcept 명시에도 clang-tidy 보수적 오탐)
- 원시 결과: `C:\working\grapi-base\clangtidy_v14.txt` — NOLINT 최종 처리 후 재스캔, **`base/` 코드 경고 0건 최종 확인**(잔여 3건은 `external/filament` 서드파티)
- [08-multiplatform-verification-plan.md](08-multiplatform-verification-plan.md) — `HeaderFilterRegex` 버그를 발견하게 된 멀티플랫폼 검증 작업 계획
