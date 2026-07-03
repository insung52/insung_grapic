# 정적 분석 도구 실행 보고서 — grapi-base 엔진

> **목적**: grapi-base 그래픽 엔진에 무료 정적 분석 도구를 실제로 적용해본 결과 정리  
> **대상 엔진**: `C:\working\grapi-base`  
> **작성일**: 2026-06-29  
> **작성자**: insung52  
>
> 관련 문서:
> - [01-background.md](../misra/01-background.md) — MISRA / ASIL / ASPICE 기초 개념
> - [02-tools.md](../misra/02-tools.md) — 정적 분석 도구 전체 조사 (상용/무료 비교)
> - [03-cppcheck-clangtidy-deepdive.md](../misra/03-cppcheck-clangtidy-deepdive.md) — Clang-Tidy / Cppcheck 심화 조사
> - [06-clang-tidy-guide.md](../misra/06-clang-tidy-guide.md) — Clang-Tidy 상세 실행 가이드
> - [07-cppcheck-guide.md](../misra/07-cppcheck-guide.md) — Cppcheck 상세 실행 가이드

---

## 1. Clang-Tidy

### 1.1 환경

| 항목 | 내용 |
|------|------|
| 도구 | Clang-Tidy (LLVM 19, VS 2022 Professional 번들) |
| 실행 바이너리 | `C:\Program Files\Microsoft Visual Studio\2022\Professional\VC\Tools\Llvm\x64\bin\clang-tidy.exe` |
| 스크립트 | `...\Llvm\x64\bin\run-clang-tidy` (`.py` 확장자 없음) |
| 빌드 프리셋 | `windows-msvc-x64-debug` |
| 컴파일 DB | `out/build/windows-msvc-x64-debug/compile_commands.json` |
| 활성 체크 | `google-*`, `readability-identifier-naming` |
| 결과 파일 | `clangtidy_full.txt` |

> 상세 실행 가이드 → [06-clang-tidy-guide.md](../misra/06-clang-tidy-guide.md)

---

### 1.2 실행 명령

```cmd
cd C:\working\grapi-base

python "C:\Program Files\Microsoft Visual Studio\2022\Professional\VC\Tools\Llvm\x64\bin\run-clang-tidy" ^
  -clang-tidy-binary "C:\Program Files\Microsoft Visual Studio\2022\Professional\VC\Tools\Llvm\x64\bin\clang-tidy.exe" ^
  -p out/build/windows-msvc-x64-debug ^
  -j 4 ^
  ".*base\\src\\.*" ^
  > clangtidy_full.txt 2>&1
```

**실행 중 발견된 이슈**:
- `-clang-tidy-binary` 생략 시 PATH의 32-bit 바이너리 선택 → 모든 파일 `Access Violation (0xC0000005)` 크래시. x64 바이너리 명시 필수.
- 파일 필터 정규식에 `/` 사용 시 0개 매칭. `compile_commands.json`의 경로가 백슬래시이므로 `\\` 사용 필요.

---

### 1.3 현재 .clang-tidy 설정

```yaml
Checks: -*,google-*,readability-identifier-naming
```

`readability-identifier-naming` 네이밍 규칙 (구글 스타일 기반):

| 항목 | 규칙 |
|------|------|
| 클래스 / 구조체 / 열거형 | `CamelCase` |
| 메서드 / 함수 | `camelBack` |
| 멤버 변수 | `lower_case_` (trailing `_`) |
| 파라미터 / 로컬 변수 | `lower_case` |
| 상수 (constexpr / static / global) | `kCamelCase` |
| 네임스페이스 | `lower_case` |

---

### 1.4 스캔 결과 (2026-06-29)

**스캔 범위**: `base/src/grapi/base/` 하위 131개 `.cc` 파일  
**경고 없는 파일**: 131개 중 115개 (88%)

#### 카테고리별 경고 건수

| 체크 | 건수 |
|------|------|
| `google-readability-casting` — C 스타일 캐스트 | 14건 |
| `readability-identifier-naming` — 네이밍 컨벤션 | ~11건 |
| `google-readability-todo` — TODO 형식 | 6건 |
| `google-build-using-namespace` — using namespace | 2건 |
| `clang-diagnostic-error` — 외부 라이브러리 파싱 오류 | 4건 |

#### `google-readability-casting` — C 스타일 캐스트

| 파일 | 건수 | 예시 |
|------|------|------|
| `extended_material_component.cc` | **13건** | `(UvSet)value` → `static_cast<UvSet>(value)` |
| `actor_exporter.cc:2784` | 1건 | `(void*)ptr` → `static_cast<void*>(ptr)` |

#### `readability-identifier-naming` — 네이밍 컨벤션

| 파일 | 위반 식별자 | 수정 방향 |
|------|------------|-----------|
| `scene_impl.cc:707` | `dirty_` | 로컬 변수에 멤버 suffix `_` 불필요 → `dirty` |
| `extended_material_component.cc:17` | `MAX_INDEX` | 로컬 변수 UPPER_CASE → `max_index` |
| `view_impl.cc:1207` | `kDepthFormats` | StaticConstant 명명 규칙 불일치 |
| `geometry_component.cc:785` | `remapAttribute` | 람다 변수 camelCase → `remap_attribute` |
| `capsule_geometry.cc:9-11` | `capRadius`, `capHeight`, `numSides` | 파라미터 camelCase → snake_case |
| `actor_exporter.cc:1937` | `tex_name_path_` | 로컬 변수에 `_` suffix → `tex_name_path` |
| `object_factory.cc:489-490` | `capSegments`, `radialSegments`, `heightSegments` | 파라미터 camelCase → snake_case |

#### `google-readability-todo` — TODO 형식

| 파일 | 건수 |
|------|------|
| `ktx2_reader.cc` | 2건 |
| `ktx2_provider.cc` | 1건 |
| `joint_component.cc` | 1건 (한국어 주석) |
| `rigidbody_component.cc` | 2건 |

수정 형식: `// TODO:` → `// TODO(insung52): 내용`

#### `google-build-using-namespace`

| 파일 | 내용 |
|------|------|
| `ktx2_reader.cc:31-32` | `using namespace basist;`, `using namespace filament;` |

#### `clang-diagnostic-error` — 외부 라이브러리 오류 (수정 불필요)

| 파일 | 원인 |
|------|------|
| `context.cc`, `name_component.cc` | `external/filament/.../StructureOfArrays.h:759` — Filament의 `[[maybe_unused]]` 매크로 파서 호환 문제 |

→ 프로젝트 코드 문제 아님. `// NOLINT(clang-diagnostic-error)` 또는 `-line-filter`로 억제 가능.

---

### 1.5 추가 가능한 체크 패턴

현재 `google-*` + `readability-identifier-naming`만 활성. 아래 추가 시 잠재적 버그 탐지 범위 확대.

#### 즉시 추가 권장

```yaml
Checks: -*,google-*,readability-identifier-naming,bugprone-*,performance-*,portability-*
```

| 카테고리 | 주요 탐지 내용 |
|----------|--------------|
| `bugprone-use-after-move` | move 후 객체 재사용 |
| `bugprone-narrowing-conversions` | 암묵적 축소 변환 |
| `bugprone-unused-return-value` | 반환값 미사용 |
| `bugprone-infinite-loop` | 무한 루프 |
| `performance-unnecessary-copy-initialization` | 불필요한 복사 생성 |
| `portability-simd-intrinsics` | SIMD 이식성 문제 |

#### 중간 단계

```yaml
Checks: ...,modernize-use-nullptr,modernize-use-override,cert-*
```

| 카테고리 | 주요 탐지 내용 |
|----------|--------------|
| `modernize-use-nullptr` | `NULL`/`0` → `nullptr` |
| `modernize-use-override` | 가상함수 `override` 누락 |
| `cert-err33-c` | C stdlib 반환값 미확인 |

---

### 1.6 종합 평가

| 항목 | 평가 |
|------|------|
| 코드 품질 | **양호** — 131개 파일 중 88%가 경고 없음 |
| 최우선 수정 | `extended_material_component.cc` C 스타일 캐스트 13건 |
| 중간 우선순위 | TODO 형식 6건, 파라미터 네이밍 위반 |
| 외부 라이브러리 | Filament 파서 오류 4건 — 프로젝트 코드 무관, 필터 처리 권장 |
| 향후 과제 | `bugprone-*` 추가 활성화 후 재스캔 |

---

## 2. Cppcheck

### 2.0 grapi-base에서 Cppcheck의 역할 범위

grapi-base는 **C++ 프로젝트**이므로 Cppcheck MISRA 기능 적용에 근본적 제한이 있음.

| 기능 | 무료 Cppcheck | Cppcheck Premium (유료) |
|------|--------------|------------------------|
| MISRA C (2012/2023) 체크 | `misra.py` addon 가능 | 가능 |
| MISRA C++ (2008/2023) 체크 | **불가** — 미구현 | 가능 (v24.5.0부터) |
| 일반 C++ 버그 탐지 | 가능 | 가능 |

→ 무료 Cppcheck의 `misra.py` addon은 C 코드 전용. C++ 코드에는 동작하지 않으며, 이는 유료/무료 차이가 아니라 구현 자체가 없기 때문.  
→ **이 프로젝트에서 Cppcheck의 목적: MISRA 준수 검증이 아닌 일반 C++ 버그 탐지** (널 포인터, 미초기화 변수, Rule of Three 위반 등).

---

### 2.1 환경

| 항목 | 내용 |
|------|------|
| 도구 | Cppcheck 2.21.0 (오픈소스) |
| 컴파일 DB | `out/build/windows-msvc-x64-debug/compile_commands.json` |
| 활성 체크 | `--enable=all` |
| 결과 파일 | `cppcheck_result_v3.txt` |

> 상세 실행 가이드 → [07-cppcheck-guide.md](../misra/07-cppcheck-guide.md)

---

### 2.2 실행 명령

```cmd
cd C:\working\grapi-base

cppcheck ^
  --project=out/build/windows-msvc-x64-debug/compile_commands.json ^
  "--file-filter=*\grapi-base\base\*" ^
  --enable=all ^
  --suppress=missingIncludeSystem ^
  --suppressions-list=cppcheck-suppressions.txt ^
  --inline-suppr ^
  --template=vs ^
  -j 4 ^
  2> cppcheck_result_v3.txt
```

**실행 중 발견된 이슈**:
- `--suppress=*:*\external\*` (백슬래시) — Windows에서 동작하지 않음
- `--suppress=*:*/external/*` (포워드슬래시) — 출력 경로가 상대 백슬래시 형식이라 매칭 실패
- `.cppcheck` XML 프로젝트 파일의 `<exclude>` — 소스 경로 미지정 시 "no C or C++ source files found" 오류
- **최종 해결**: `--file-filter=*\grapi-base\base\*` 로 분석 대상 파일 자체를 필터링. include된 external 헤더 경고는 출력에 혼재되나 결과 파일에서 `base\` 경로만 참조하면 됨.

---

### 2.3 스캔 결과 (2026-06-29)

**스캔 범위**: `base\` 하위 프로젝트 파일 (`--file-filter` 적용)

#### 실제 버그 가능성 — 우선 검토 필요

| 파일 | 등급 | 체크ID | 내용 |
|------|------|--------|------|
| `geometry_component.cc:554-555` | warning | `arrayIndexOutOfBoundsCond` | `attribute_indices_.empty()` 조건이 있음에도 `attribute_indices_[i]` 범위 초과 접근 가능 — 로직 오류 가능성 |
| `ktx2_reader.cc:567, 648` | warning | `nullPointerArithmeticRedundantCheck` | `new` 실패 시 `blocks` null pointer dereference |
| `resource_manager.cc:54` | warning | `noCopyConstructor` / `noOperatorEq` | 동적 메모리 관리 클래스에 복사 생성자 / `operator=` 없음 (Rule of Three 위반) |
| `curve.cc:183,188,192,214,232` | warning | `suspiciousCommaInReturn` | 콤마 연산자 결과 미사용 — 의도치 않은 로직일 가능성 |

#### 미초기화 멤버 변수

| 파일 | 미초기화 변수 |
|------|-------------|
| `asset_impl.h:98` | `SourceAsset::hierarchy` |
| `asset_loader.h:40` | `AssetLoader::error_` |
| `ktx2_provider.cc:63` | `QueueItem::state_` |

#### 오탐 — 억제 처리 권장

`duplInheritedMember` (warning): `kTypeInfo` static 멤버 변수를 각 파생 클래스에서 의도적으로 재선언하는 패턴 (커스텀 RTTI 대체 설계). Cppcheck가 경고로 분류하나 설계 의도에 부합.

영향 클래스: `Actor`, `Geometry`, `BoxGeometry`, `CapsuleGeometry`, `CylinderGeometry`, `PlaneGeometry`, `SphereGeometry`, `TorusGeometry`, `Light`, `SpotLight`, `FocusedSpotLight`, `DirectionalLight`, `Renderer`, `View`

`AssetImpl`, `RendererImpl`, `ViewImpl`, `CurvePath`, `LineCurve` 등 Pimpl 패턴 클래스의 메서드 재선언도 동일 경고 다수 발생. → `// cppcheck-suppress duplInheritedMember` 로 억제 권장.

#### `performance` 경고

| 파일 | 내용 |
|------|------|
| `ray.h:36-38` | 생성자 본문 초기화 → 초기화 목록 사용 권장 |
| `context.h:59` | `getConfig()` by-value 반환 → const reference 권장 |
| `asset_impl.h` | getter 5개 by-value 반환 → const reference 권장 |
| `animation_component.h:16` | `getTracks()` const ref 반환 권장 |
| `light_component.h:81` | `getShadowOptions()` const ref 반환 권장 |
| `keyframe_track.h:78,87` | `getTimes()`, `getValues()` const ref 반환 권장 |
| `curve_path.h:51` | `getCurves()` const ref 반환 권장 |
| `shape.h:47` | `getHoles()` const ref 반환 권장 |
| `freetype_font.h:36` | `getUri()` const ref 반환 권장 |
| `ibl.cc:151` | `path` 파라미터 const reference 전달 권장 |

#### `style` 주요 경고

| 파일 | 내용 |
|------|------|
| `first_person_controls.h:20` | `~FirstPersonControls` — `override` 누락 |
| `fly_controls.h:23` | `~FlyControls` — `override` 누락 |
| `map_controls.h:20` | `~MapControls` — `override` 누락 |
| `ktx2_reader.h:51` | 단일 인자 생성자에 `explicit` 누락 |
| `ktx2_provider.cc:24` | `~Ktx2Provider` — `override` 누락 |
| `ray.cc:23,36,49` | `direction` 파라미터가 멤버 변수 섀도잉 |
| `orbit_controls.cc:483` | `target` 파라미터가 멤버 변수 섀도잉 |
| `random.h:48,77` | 초기화 후 즉시 덮어쓰기 — 불필요한 초기화 |
| `freetype_font.cc:38,42` | `isSpace()`, `isNewline()` — static 가능 |
| `asset_impl.cc:70,101` | raw loop → `std::copy` 권장 |
| `geometry_component.cc:37,624` | raw loop → `std::transform` 권장 |
| `ktx2_provider.cc:134,233` | raw loop → `std::find_if` 권장 |
| `ktx2_reader.cc:553,634,858` | 할당 후 미사용 변수 |
| `ktx2_reader.cc:41` | 사용되지 않는 struct 멤버 `FinalFormatInfo::name` |

---

### 2.4 종합 평가

| 항목 | 내용 |
|------|------|
| 실제 버그 가능성 | 4건 — `geometry_component.cc` 배열 범위 초과, `ktx2_reader.cc` null 포인터, `resource_manager.cc` Rule of Three, `curve.cc` 콤마 연산자 |
| 미초기화 멤버 | 3건 — 초기화 목록에 추가 권장 |
| 오탐 | `duplInheritedMember` 다수 — Pimpl/RTTI 설계 패턴, 억제 처리 권장 |
| performance | getter의 const reference 반환 미적용이 전반적으로 많음 |
| style | override 누락 소멸자 4개, explicit 누락 생성자, 변수 섀도잉 |

---

## 3. 도구 비교 및 결과 요약

| 항목 | Clang-Tidy | Cppcheck |
|------|------------|----------|
| 분석 방식 | AST 기반 (컴파일러 수준) | 독자 파서 기반 |
| MISRA C++ 지원 | 없음 (유사 패턴 간접 탐지) | 없음 (무료 버전 미구현) |
| 네이밍 컨벤션 체크 | 강함 | 없음 |
| 실제 버그 탐지 | 보통 | **강함** (null 포인터, 미초기화, Rule of Three) |
| 외부 라이브러리 필터링 | `HeaderFilterRegex` 로 용이 | Windows 경로 패턴 매칭 제한 — `--file-filter` 사용 |
| 분석 속도 | 느림 (파일당 3~4초) | 빠름 (`-j 4` 병렬 시) |
| 라이선스 | Apache 2.0 | GPL v3 |

### grapi-base 스캔 결과 요약

| 구분 | Clang-Tidy | Cppcheck |
|------|------------|----------|
| 스캔 파일 수 | 131개 (.cc) | 131개 (.cc) |
| 실제 버그 가능성 | 없음 (스타일/컨벤션 위주) | **4건** |
| 미초기화 변수 | 미탐지 | 3건 |
| 코드 스타일/성능 | 33건 | 73건 |
| 외부 라이브러리 오류 | 4건 (Filament) | 혼재 (필터링 한계) |

**결론**: 두 도구가 탐지하는 영역이 다름. Clang-Tidy는 컨벤션·스타일·캐스트 패턴에 강하고, Cppcheck는 실제 런타임 버그 가능성(null 포인터, 미초기화, 소유권 위반) 탐지에 강함. 병행 사용이 효과적.

---

## 4. 참고 문서

- [06-clang-tidy-guide.md](../misra/06-clang-tidy-guide.md) — Clang-Tidy 실행 가이드 (체크 카테고리 전체 목록 포함)
- [07-cppcheck-guide.md](../misra/07-cppcheck-guide.md) — Cppcheck 실행 가이드
- [03-cppcheck-clangtidy-deepdive.md](../misra/03-cppcheck-clangtidy-deepdive.md) — 두 도구 심화 비교
- [02-tools.md](../misra/02-tools.md) — 상용 도구 비교 (MISRA 인증 필요 시)
- [01-background.md](../misra/01-background.md) — MISRA / ASIL / ASPICE 기초 개념
