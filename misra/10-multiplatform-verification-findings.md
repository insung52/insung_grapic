# 멀티플랫폼 재검증 결과 (Clang-Tidy: Linux/WebGL/Android, Cppcheck: Linux/WebGL/Android/Telechips/Renesas) — 예비 문서

> **이 문서는 예비 정리본**. **2026-07-06 본 리포트(`C:\private\2026-W27-황인성\260706_황인성_clangtidy_cppcheck_verification_report.md`)에 병합 완료** — A-18~A-21(실버그 2건, 크래시 위험 1건, 미구현 기능 1건), D-29/D-30(신규 카테고리), F-10~F-12(신규 오탐 3종), 기존 A-4/B-1/B-2/B-3/B-8/D-7/D-12/D-16/D-17/D-18/D-19/D-20/D-21/D-25에 추가 확인분 반영. 이 문서는 세부 삽질·교훈 기록의 원본으로 계속 보존.
> [08-multiplatform-verification-plan.md](08-multiplatform-verification-plan.md)에 정리된 명령으로 WSL에서 스캔 수행(2026-07-02~03).
> 원시 결과 (1차, v1):
> - `clangtidy_linux-clang_v1.txt`, `clangtidy_webgl_v1.txt`, `clangtidy_android-arm64_v1.txt`
> - `cppcheck_linux-clang_v1.txt`, `cppcheck_webgl_v1.txt`, `cppcheck_android-arm64_v1.txt`, `cppcheck_telechips-tcc803x_v1.txt`, `cppcheck_renesas-rcar_h3ulcb_v1.txt`
> (전부 `\\wsl.localhost\Ubuntu\home\insung52\grapi-base\`에 위치)
>
> 원시 결과 (최종 재검증, v2 + Windows v13, 2026-07-03 — §3 참고):
> - WSL: `clangtidy_{linux-clang,webgl,android-arm64,android-arm,android-x86,android-x64}_v2.txt`, `cppcheck_{linux-clang,webgl,android-arm64,android-arm,android-x86,android-x64,telechips-tcc803x,renesas-rcar_h3ulcb}_v2.txt` (Android arm/x86/x64는 이번이 최초 스캔)
> - Windows: `clangtidy_v13.txt`(v12은 툴체인 이슈로 전체 실패, 무효), `cppcheck_result_v9.txt`

---

## 0. 배경

Windows MSVC(LLVM 19) 기준으로 D-22~D-28까지 정리한 뒤, 실제로 다른 플랫폼(Linux/WebGL/Android — Clang 계열, Telechips/Renesas — GCC 계열)에서도 동일하게 클린한지 확인하기 위해 멀티플랫폼 재스캔을 진행. Telechips/Renesas는 GCC 툴체인이라 Clang-Tidy는 사용 불가, Cppcheck만 적용(08번 문서 5.4/5.5절 참고).

**중요 전제(2026-07-03 갱신)**: Windows 쪽 코드 수정을 커밋 후 WSL에서 `git pull`로 동기화 완료, WSL 전용 재검증(misc-const-correctness pointee-const, Android NDK clang-tidy 재검증, autoVariables Telechips 재현)까지 전부 완료됨. 이후 **최종 재검증 라운드**(§3)로 Android arm/x86/x64 최초 스캔 + 전 플랫폼 v2/v13 재스캔까지 마치고 신규 발견 7건도 전부 수정·검증 완료. 이 문서의 모든 항목이 최신 상태.

---

## 1. Clang-Tidy — Linux/WebGL/Android

### 1.1 규모 요약

| 플랫폼 | 총 경고 | 총 에러 | 비고 |
|---|---|---|---|
| Linux Clang (LLVM 21) | 695 | 0 | |
| WebGL (LLVM 21) | 695 | 0 | Linux와 거의 동일 |
| Android (NDK LLVM 19.0.1) | 19 | 99(전부 노이즈) | 파일 수가 적어 경고도 적음 |

Windows에서 이미 처리한 D-22~D-28 카테고리(nodiscard, narrowing-conversion, 네이밍, Rule of Five, signed-bitwise, easily-swappable-parameters, enum-size 등)는 **전부 0건** — 플랫폼 넘어서도 D-22~D-28 수정이 유효함을 확인.

### 1.2 misc-const-correctness (pointee-const) — 673건 (Linux/WebGL) — ✅ 완료 (2026-07-03, WSL)

**증상**: `pointee of variable 'mc' of type 'components::PhysicalMaterialComponent *' can be declared 'const'` 형태. `Type* var = getXComponent(...); var->readOnly();` 패턴에서 포인터가 가리키는 대상이 읽기 전용으로만 쓰이는 경우 대량 발생.

**버전 확인 결과**: LLVM 19(Windows 번들)에는 이 서브체크에 대응하는 옵션이 아예 없음(`--dump-config`로 `misc-const-correctness`의 옵션 6개 확인: `AnalyzeReferences`, `AnalyzeValues`, `TransformPointersAsValues`, `TransformReferences`, `TransformValues`, `WarnPointersAsValues` — 전부 포인터 자체의 재대입 여부에 관한 것이지 "포인터가 가리키는 대상의 const 가능 여부"와는 무관). LLVM 21에서 새로 추가된 기능으로 확인, **진짜 버전 제한**.

> **⚠️ 삽질 기록**: `misc-const-correctness.WarnPointersAsValues: true`를 켜면 비슷한 문구("variable 'mc' ... can be declared 'const'", "pointee of" 접두어 없음)의 경고가 Windows에서도 뜨길래 같은 체크인 줄 알고 `.clang-tidy`에 영구 반영 + `-fix`로 84개 파일에 일괄 적용했으나, 실제로는 **포인터 자체를 `T* const`로 만드는 것**(재대입 방지)이지 **포인티(가리키는 대상)를 `const T*`로 만드는 것**(D-23/원래 목표)과는 다른 것이었음. 診断 문구가 미묘하게 달랐던 것(`pointee of variable X` vs `variable X`)을 놓친 것이 원인. 발견 즉시 Python 스크립트로 정밀 복구(원본에 이미 있던 정당한 `* const` 10곳은 보존)하고 `.clang-tidy` 설정도 원복 완료. 컴파일 확인 및 `git diff` 확인으로 완전 복구 검증함.
>
> **교훈**: 클린업 명령어의 진단 메시지가 비슷해 보여도 정확히 같은 워딩인지(특히 "pointee of" 같은 핵심 수식어) 재확인 후 대량 적용할 것. 소규모로 먼저 diff를 확인하고 확산했어야 함.

**처리 방향**: WSL(LLVM 21)에서 직접 `-fix` 적용 예정. 패턴은 균일함(대부분 `ComponentType* var = factory->getXComponent(id); var->읽기전용();` 형태)이 확인되어 D-23과 동일하게 대량 자동 수정 + 리뷰가 안전할 것으로 판단. **Windows 코드 수정 완료 후 커밋 → WSL pull 이후 진행 예정.**

**WSL 적용 결과 (2026-07-03)**: 먼저 `--dump-config`로 재확인한 결과, LLVM21 기본 설정에서 `misc-const-correctness.WarnPointersAsPointers`/`TransformPointersAsPointers`가 **기본값 `true`로 이미 켜져 있음**을 확인 — 이게 정확히 pointee-const(포인티를 const로) 옵션이고, 1.2절 상단에서 착각했던 `WarnPointersAsValues`(포인터 자체를 const로, 기본값 false)와는 반대 개념. `.clang-tidy`에 별도 오버라이드가 없어 기본 설정 그대로 사용 가능함을 확인 후 진행.

`run-clang-tidy.py -fix`(clang-apply-replacements 바이너리 경로를 명시적으로 지정해야 동작 — 기본 탐색 실패) 적용 결과 44개 파일, 258곳 수정. 이후 `ninja`로 `grapi-base` 타겟 빌드한 결과 **44건 컴파일 에러 발생** — 전부 clang-tidy가 선언 지점의 지역 사용만 보고 판단해서, 그 포인터가 함수 밖으로 흘러나가는(non-const 타입으로 리턴/non-const 컨테이너에 저장/non-const 파라미터 API에 전달) 경우를 못 잡아낸 오탐. `constVariablePointer`(2.4절)에서 이미 한 번 겪었던 것과 완전히 동일한 유형의 함정이 clang-tidy 쪽에서도 재현된 것.

| 원인 유형 | 대표 사례 | 건수 |
|---|---|---|
| non-const 타입으로 리턴 | `getMaterialInstanceAt()`, `getPhysicsContext()`(3개 컴포넌트에 중복 정의), `popTexture()`, `createColorGrading()`, `_createCamera()` 등 | 다수 |
| non-const 컨테이너에 저장 | `asset_loader.cc`(`unordered_map<cgltf_node*,...>` 키), `resource_manager.cc`(`pair<Texture*,...>` 캐시), `custom_material_provider.cc`(vector), `actor_exporter.cc`(`std::stack<Actor*>`) | 다수 |
| non-const 파라미터 API에 전달 | `JobSystem::runAndWait(Job*&)`/`parallel_for(...)` — `particles_component.cc` 2곳 + `scene_impl.cc` 11곳(모든 `_run*UpdateSystem`) | 13 |
| C API out-param | `context.cc` — `std::strtol`의 `char** p_end` | 1 |
| `scene_impl.cc` 컴포넌트 포인터가 non-const 멤버 컨테이너(`lights_` 등)에 push/insert | 12 | 12 |

전부 해당 지점의 **지역 변수 선언 하나만** non-const로 되돌리고(파일 내 다른 정당한 pointee-const 수정은 그대로 유지) 재빌드 → 0 에러 확인. 최종 `git diff --stat`: 37개 파일, 214+/214-.

되돌린 44곳은 다음 clang-tidy 재스캔에서도 계속 같은 오탐으로 재검출되므로(로컬 분석 한계는 재스캔해도 안 바뀜), 전부 `// NOLINT(misc-const-correctness) - <구체적 사유>` 주석을 달아 재작업을 방지. 주석 추가 후 재빌드(0 에러) + 재스캔(`misc-const-correctness` 0건) 둘 다 확인 완료.

**최종 검증**: `misc-const-correctness` 전용 재스캔 결과 0건. `git diff --stat`: 44개 파일, 258+/258- (동일 258건, NOLINT 주석은 줄 추가 없이 같은 줄에 덧붙임).

### 1.3 bugprone-unchecked-optional-access — 18건 — ✅ 완료

**대상**: `geometry_component.cc`(6곳), `mesh_component.cc`(4곳), `particles_component.cc`(7~8곳, 플랫폼별 약간 차이).

| 위치 | 판정 | 처리 |
|---|---|---|
| `geometry_component.cc::computeBoundingSphere()` (6곳) | 오탐 — 함수 상단 `if (!has_value()) x = value;` 가드로 이미 보장되나 clang-tidy가 함수 내 반복 역참조를 완전히 추적 못 함 | `Sphere& sphere = *bounding_sphere_; const AABB& box = *bounding_box_;`로 한 번만 역참조하도록 리팩터링 — 반복 오탐 자체를 제거 |
| `mesh_component.cc:184` (`onRebuild()`) | 오탐 — 함수 상단(138번 줄)에 모든 `geometries_[index]`의 `getBoundingBox().has_value()`를 미리 검증하는 루프가 있고, 실패 시 조기 리턴 | NOLINT + 주석 |
| `mesh_component.cc:433` | 오탐 — 바로 위(431~432줄)에서 `has_value()` 체크 후 `computeBoundingSphere()` 호출로 이미 보장 | NOLINT + 주석 |
| `mesh_component.cc:847~848` (`updateGeometryLods()`) | **진짜 버그로 확인, 실제 수정** — `scene_impl.cc:1080`에서 이 함수가 **모든 MeshComponent에 대해 매 프레임 무조건** 호출됨. `onRebuild()`가 한 번도 성공 못 한(예: `Geometry::create()`로 만들고 아직 `setPositions()` 안 부른) 지오메트리가 걸리면 매 프레임 크래시 위험 | `if (std::optional<AABB> aabb = gc->getBoundingBox(); lod_count > 1 && aabb.has_value())`로 가드 추가, 없으면 `new_lod = 0`(기본값) 유지하고 다음 프레임 재시도 |
| `particles_component.cc` (7곳, `counters_->`) | 오탐 — `animate()`가 `_createSelfBuffers()`를 먼저 호출(`counters_`를 무조건 채움)한 뒤에만 `counters_->`에 접근 | NOLINT + 주석 |

**중요 분석 과정**: `mesh_component.cc:184`은 처음엔 진짜 버그로 오판했으나(사전 검증 루프를 못 보고 판단), 재확인 과정에서 오탐으로 정정. 반대로 `847~848`은 처음엔 대충 훑고 넘어갈 뻔했으나 실제 호출 그래프(scene_impl.cc까지 추적)를 확인해 진짜 버그임을 확정. **표면적 코드 유사성만으로 판단하지 않고 실제 호출 경로를 끝까지 추적해야 함**을 재확인.

**부작용 검토 및 폐기한 방안**: 처음엔 `GeometryComponent::bounding_box_`에 생성자 기본값(`= AABB()`)을 주는 근본 수정을 시도했으나, `applyMatrix4()`가 `bounding_box_.has_value()`를 "한 번이라도 계산된 적 있는지" 판단하는 최적화 용도로 쓰고 있어서(변환 적용 시 필요한 경우만 재계산) 이 최적화가 무력화되는 부작용 발견 → 되돌리고 `mesh_component.cc` 쪽에서 방어 체크하는 방식(A안)으로 변경.

**검증**: Windows에서는 이 체크 자체가 발동 안 해서(이 코드에서는 LLVM19도 0건) 로컬 검증 불가 — 컴파일만 확인 완료. **WSL 반영 후 재스캔으로 최종 확인 필요.**

**WSL/Android 재검증 결과 (2026-07-03)**: NDK LLVM19.0.1 clang-tidy로 `base/src` 전체 재스캔 결과, 기존 18건은 전부 재검출되지 않음(모두 정상 처리 확인). 다만 **Android 빌드 경로에서만 새로 걸리는 1건 추가 발견**: `geometry_component.cc:538`(`const AABB& box = *bounding_box_;`, 이번 세션에 추가한 리팩터링 라인) — `computeBoundingBox()`가 무조건 `bounding_box_`에 값을 채워주는 걸 알고 짠 코드지만, 이 체크는 **함수 호출 경계를 넘는 추적을 못 해서** 여전히 오탐. 같은 함수 안의 `bounding_sphere_`(지역 가드로 직접 보장)는 안 걸리고, 다른 함수(`computeBoundingBox()`) 호출로 간접 보장되는 `bounding_box_`만 걸린 것으로 원인 확정. NOLINT 추가 후 재스캔 0건, Android 빌드 재확인 완료.

### 1.4 bugprone-implicit-widening-of-multiplication-result — 1건 (`freetype_font.cc:16`) — ✅ 완료

`FT_Set_Char_Size(ft_face_, size_ * 64, 0, 72, 72);` — `size_ * 64`가 `int`(32비트)로 먼저 계산된 뒤 `FT_F26Dot6`(`signed long`)로 암묵 확장. B-2와 동일 패턴.

**수정**: `static_cast<FT_F26Dot6>(size_) * 64`. Windows에서 재검증 완료(0건).

### 1.5 bugprone-multi-level-implicit-pointer-conversion — 4건 (Android 전용, `actor_exporter.cc`) — ✅ 완료 (검증 완료)

`cgltf_node**`/`char**` → `void*`로 `free()` 호출 시 변환. 코드는 이미 `static_cast<void*>(...)`로 명시적 캐스팅하고 있었으나, Android NDK의 clang-tidy가 다단계 포인터(`T**`) 변환은 `static_cast`로 부족하다고 판단해 경고(Windows/LLVM19에서는 이 체크가 발동 안 함 — 확인 완료, 0건).

**처리**: cgltf가 할당한 C 스타일 배열을 `free()`로 해제하는 불가피한 패턴(B-3과 동일 방침) — 기존 `cppcoreguidelines-no-malloc` NOLINT에 체인 추가.

**검증 보류**: 이 체크가 Windows에서 발동 안 해서 로컬 검증 불가 → **WSL/Android 재스캔 필요**.

**WSL/Android 재검증 결과 (2026-07-03)**: NDK LLVM19.0.1로 재스캔, 기존 4건 NOLINT 모두 정상 억제 확인(재검출 0건). Android 빌드도 정상.

### 1.6 readability-identifier-naming — 1건 (Android 전용, `virtual_machine_env.h::JNI_OnLoad`) — ✅ 완료 (검증 완료)

`static jint JNI_OnLoad(JavaVM* vm);`가 `filament::VirtualMachineEnv::JNI_OnLoad`(Filament 엔진의 JNI 관례)와 이름을 맞춘 의도적 네이밍 — NOLINT 처리.

**검증 보류**: `jni.h` 의존 파일이라 Android 전용, Windows에서 컴파일 자체가 안 됨 → **WSL/Android 재스캔 필요**.

**WSL/Android 재검증 결과 (2026-07-03)**: NDK LLVM19.0.1로 재스캔, NOLINT 정상 억제 확인(재검출 0건).

### 1.7 bugprone-forward-declaration-namespace — 3건 — 조치 불필요

`external/filament/libs/gltfio/src/Utility.h`(서드파티) — 우리 소관 아님. Windows 스캔에서도 동일하게 확인됐던 항목.

---

## 2. Cppcheck — Linux/WebGL/Android/Telechips/Renesas

### 2.1 규모 요약 (base/ 코드 기준)

| 플랫폼 | base/ 발견 건수 | 내용 |
|---|---|---|
| Linux Clang | 196 | `duplInheritedMember` 175(F-5, 기존 확인된 패턴) + `normalCheckLevelMaxBranches` 21(F-7, 정보성) — **신규 없음** |
| WebGL | 196 | Linux와 동일 |
| Android | 196 | Linux와 동일 |
| Renesas | 197 | Linux와 동일 + `missingInclude` 1건(빌드 생성 파일 관련 정보성 메시지, F-7과 동일 성격 — 조치 불필요) |
| **Telechips** | **1298** | 위 F-5/F-7 패턴이 비례 확대(607/99) + **신규 카테고리 다수** |

### 2.2 Telechips가 유독 많은 이유 — 스캔 설정 문제 아님, 실제 코드 경로 차이

처음엔 cppcheck 실행 스크립트가 플랫폼마다 다른 줄 알았으나(08번 문서 명령어는 전부 동일), `compile_commands.json`을 직접 비교한 결과:

```
linux-clang-release:        base/ 182개 파일
linux-telechips-tcc803x-release: base/ 182개 파일  (동일!)
```

**파일 수는 동일** — 즉 스캔 대상 자체는 같음. 그런데도 발견 건수가 4배 이상 차이 나는 건, Telechips(GCC, 임베디드 aarch64 타겟)의 **전처리기 매크로/타입 폭 차이가 같은 파일 안에서 더 많은 `#ifdef` 분기와 코드 경로를 열어젖혀서** cppcheck가 그만큼 더 많은 지점을 분석·보고하는 것으로 확인. 이는 이 검증 작업 초반에 세웠던 가설("플랫폼 분기는 명시적 `#ifdef`만 보는 게 아니라 타입폭/컴파일러 차이까지 봐야 한다")이 실제로 들어맞은 사례.

즉 Telechips 전용으로 새로 뜬 항목들은 스캔 설정 문제가 아니라 **진짜 Telechips 빌드 경로에서만 분석되는 코드**.

### 2.3 Telechips 신규 카테고리 (base/ 기준)

| 체크 | 건수 | 기존 항목과의 대응 | 상태 |
|---|---|---|---|
| `constVariablePointer` | 446 | **D-18과 동일 패턴** (포인터가 가리키는 대상을 const로 선언 가능) | ✅ 완료 (437/446, 9건은 mesh_component.cc 소속으로 재확인 후 8건 적용·1건은 재대입 있어 제외) |
| `constParameterPointer` | 16 | D-18/constVariablePointer와 동일 성격 | ✅ 완료 (10/16 적용, 6건은 실제 컴파일 에러 확인되어 제외) |
| `constParameterReference` | 12 | 상동 | ✅ 완료 (4/12 적용, 8건 제외 — 6건 컴파일 에러성 오탐 + 1건 공개 API 보류 + 1건은 실제로는 안전 확인 후 적용) |
| `constVariableReference` | 2 | 상동 | ✅ 완료 (2/2 적용) |
| `unreadVariable` | 74 | 죽은 코드 정리 + 1건은 진짜 흥미로운 케이스(2.5절) | ✅ 완료 |
| `returnByReference` | 21 | D-16과 완전히 동일한 패턴 | ✅ 완료 |
| `nullPointerOutOfMemory` | 17 | A-4(malloc null 체크)와 동일 패턴 | ✅ 완료 |
| `functionStatic` | 17 | D-21과 동일 패턴 (3건은 미구현 발견으로 보류) | ✅ 완료 (14/17, 3건 보류) |
| `knownConditionTrueFalse` | 8 | D-5/D-12(불리언 단순화)와 동일 패턴 | ✅ 완료 (6/8, 1건 코드 확인 후 되돌림, 1건 관용구라 유지) |
| `uselessOverride` | 6 | 조건부 컴파일 관련 | ✅ 완료 (1/6 적용, 5건은 `#ifdef USE_JOLT`로 인해 Telechips에서만 base와 동일해지는 것이라 보류) |
| `useStlAlgorithm` | 5 | D-19와 동일 패턴 | ✅ 완료 |
| `useInitializationList` | 4 | D-17과 동일 패턴 | ✅ 완료 (3/4 적용, 1건은 이미 세밀하게 검토된 이동 생성자라 보류) |
| `variableScope` | 2 | unreadVariable 정리 때 이미 통째로 삭제됨 | ✅ 완료 (부수 효과로 해소) |
| `shadowVariable` | 2 | 이름 충돌 | ✅ 완료 |
| `invalidPointerCast` | 2 | B-3과 동일 패턴(불가피한 바이너리 파싱) | ✅ 완료 (cppcheck-suppress 추가) |
| `duplicateConditionalAssign` | 2 | 중복 조건 | ✅ 완료 (1/2, 1건은 `#ifdef USE_JOLT`로 보류) |
| `duplicateBreak` | 2 | 도달 불가 코드 | ✅ 완료 |
| `stlFindInsert` | 1 | 성능 — 중복 해시 조회 | ✅ 완료 |
| `shadowArgument` | 1 | 이름 충돌 | ✅ 완료 |
| `nullPointerRedundantCheck` | 1 | **진짜 버그 발견** — `KHR_materials_volume`이 항상 등록되던 문제 | ✅ 완료 |
| `autoVariables` | 1 | 심각도 error인데 Windows에서 재현/특정 불가 | ✅ 완료 (WSL/Telechips에서 재현, 오탐 확정 후 억제) |
| `assignBoolToFloat` | 1 | **진짜 버그 발견** — `TemporalAntiAliasingOptions::upscaling`이 bool로 잘못 모델링되어 있던 문제 (공개 API 타입 변경) | ✅ 완료 |

### 2.4 const-correctness 계열 (constVariablePointer/constParameterPointer/constParameterReference/constVariableReference, 총 476건) — ✅ 완료 (461건 적용, 15건 확인 후 보류)

**패턴 검증**: `physical_material.cc`를 샘플로 확인한 결과, cppcheck는 이미 mutating 메서드 호출 여부를 정확히 구분하고 있음 — 예를 들어 `enableClearcoat()`(mutating)를 호출하는 지점은 플래그되지 않고, `isEnableClearcoat()`/`getClearCoatFactor()`(read-only)를 호출하는 지점만 플래그됨. 즉 **cppcheck의 자체 데이터플로 분석을 신뢰 가능** — D-23 때처럼 사람이 일일이 mutating 호출 여부를 재검증할 필요는 적음.

**분포**: 42개 파일에 분산, 상위는 `physical_material.cc`(62), `extended_material.cc`(52), `standard_material.cc`/`sprite.cc`/`particles.cc`(각 34), `actor_exporter.cc`(25) 등 — 대부분 "공개 API 래퍼가 내부 컴포넌트 포인터를 얻어 읽기 전용으로 쓰는" 패턴(physical_material.cc 등 `base/*.cc` 루트의 공개 API 구현 파일들).

**처리 방법**: cppcheck는 clang-tidy 같은 신뢰할 만한 `-fix` 기능이 없어 직접 코드 수정. 규모가 커서(476건) 개별 확인이 비현실적이라, cppcheck가 지정한 정확한 파일:줄:컬럼 + 변수명 목록을 Python 스크립트로 파싱해 (1) 선언문/if-init/range-for 세 가지 패턴 매칭 → `const` 삽입 위치 계산 (2) 매칭 실패 항목은 자동 적용에서 제외하고 리스트업 (3) 리스트업된 항목은 개별 코드 확인 후 처리, 하는 방식으로 진행. `constVariablePointer` 437건은 스크립트로 일괄 적용 + 전체 컴파일 검증(신규 에러 0건).

**⚠️ 줄번호 드리프트(mesh_component.cc)**: 이번 세션에 이미 편집한 `mesh_component.cc`는 cppcheck 스캔(WSL, 편집 전) 시점의 줄번호가 현재 파일과 어긋나 있었음(9건 중 5건). 자동 매칭에서 제외하고 변수명·타입으로 현재 파일에서 재검색해 8건 적용, 1건(`for (MaterialInstance* mi : material_instances_) { ... mi = nullptr; }`)은 루프 안에서 포인터 자체를 재대입하고 있어 const 불가능함을 확인하고 제외. **이번 세션 중 수정한 파일에 대해 오래된 스캔 결과의 줄번호를 맹신하면 안 된다는 교훈 재확인**(D-24/D-26 때도 유사 이슈 있었음).

**⚠️ 진짜 위험했던 오탐 — `scene_impl.cc`의 `js`/`parent` 파라미터 (14건 중 12건 제외)**: cppcheck가 `JobSystem& js`, `JobSystem::Job* parent`를 전부 const 가능하다고 제안했으나, 실제로는 `js.runAndWait(job)`(비-const 멤버 함수, `void runAndWait(Job*&)`)와 `utils::jobs::parallel_for(js, parent, ...)`(Filament 템플릿 함수, `JobSystem::Job* parent`로 non-const 요구)에 그대로 전달되고 있어 **const로 바꾸면 실제 컴파일 에러**가 발생함을 헤더 직접 확인으로 검증. cppcheck가 서드파티 템플릿 헤더(Filament `JobSystem.h`)까지 완전히 추적하지 못해 발생한 오탐으로 판단, 전부 미적용. (`constVariablePointer` 계열에서 앞서 겪은 "84개 파일 오적용 후 되돌린" 사고를 겪은 뒤라 이번엔 실제 헤더 시그니처를 직접 확인하고서야 적용 — 사전 검증이 실제로 컴파일 에러를 막은 사례.)

**보류 1건 — 공개 API**: `scene.cc::Scene::setGravity(glm::vec3& gravity)`가 `base/include/grapi/base/scene.h`에 선언된 공개 API라 C-1/D-16 방침대로 시그니처 변경 보류, `// cppcheck-suppress constParameterReference` 인라인 억제만 추가.

**적용 완료 예시**:
```cpp
// actor_exporter.h/.cc — private 메서드 7개, .h/.cc 양쪽 다 수정
void _collectMesh(Mesh* mesh);           →  void _collectMesh(const Mesh* mesh);

// image.h/.cc — Filament MaterialInstance::setParameter가 이미
// `Texture const*`/`TextureSampler const&`를 받는 것을 헤더에서 직접 확인 후 적용
void setTexture(filament::Texture* texture, filament::TextureSampler& sampler);
  → void setTexture(const filament::Texture* texture, const filament::TextureSampler& sampler);

// asset_loader.cc:884~886 — output_prim이 끝까지 읽기 전용(*output_prim만 참조,
// 대입 없음)임을 직접 확인 후 prims/output_prim 둘 다 const로 변경
std::vector<BaseID>& prims = ...; BaseID* output_prim = prims.data();
  → const std::vector<BaseID>& prims = ...; const BaseID* output_prim = prims.data();

// animation_mixer.cc:77 — getTracks()가 값으로 반환되는 임시 벡터의 원소를
// 순회하며 읽기만 함
for (auto& track : ac->getTracks())  →  for (const auto& track : ac->getTracks())
```

**최종 검증**: 전체 `base/src/*.cc` 대상 컴파일 확인(`misc-const-correctness` 체크로 clang-tidy 구동) — 에러 270건(기존 노이즈 그대로), 신규 에러 0건.

### 2.5 unreadVariable (74건) — ✅ 완료

**패턴 분류**: 겉보기엔 다 "선언만 하고 안 씀"이지만 실제로는 세 가지 완전히 다른 성격이 섞여 있었음 — 하나만 확인하고 나머지도 같은 방식으로 처리했으면 큰일 날 뻔함.

| 패턴 | 건수 | 처리 |
|---|---|---|
| **부수효과 있는 생성 호출** — `Type& var = factory->createXComponent(e);` 형태로, 반환값(`var`)은 안 쓰지만 **호출 자체가 컴포넌트를 실제로 생성·등록하는 필수 부수효과**를 가짐 | 57건(`object_factory.cc`) | 호출은 유지하고 반환값 캡처만 제거: `factory->createXComponent(e);` — Python 스크립트로 단일행/2행(연속) 패턴 모두 처리, 컴파일 검증 완료 |
| **순수 죽은 코드** — `getXComponent()`/단순 산술처럼 부수효과 없는 값이 계산만 되고 어디서도 안 읽힘 | 8건(`animation_mixer.cc::time`, `custom_material_component.cc`/`extended_material_component.cc`(x2)의 `nc`, `actor_exporter.cc`의 `node_id`/`using_cache`, `mesh_component.cc::material_instance`) | 선언 자체를 삭제(단, `nc`처럼 그 값을 얻기 위해서만 쓰인 상위 변수(`factory`)가 있으면 같이 삭제 — 안 그러면 그 변수가 새로운 unreadVariable이 됨) |
| **플랫폼 조건부 컴파일로 인한 진짜 미사용** — `joint_component.cc::checkBreakDistance()`의 `physics_scene`은 `#ifdef USE_JOLT` 블록 안에서만 쓰이는데, 선언은 그 밖에 있었음. Telechips는 `GRAPI_USE_JOLT: OFF`라 이 빌드에서만 정말로 미사용이 됨(Windows/다른 물리 활성 플랫폼에서는 정상 사용됨) | 1건 | 삭제 대신 **선언 자체를 `#ifdef USE_JOLT` 안으로 이동** — 플랫폼에 따라 실제로 쓰이거나 안 쓰이거나 하는 코드라 삭제하면 안 됨 |
| **계산은 다 하는데 결과를 안 쓰는 지오메트리 코드** — `extrude.h::spline_tube_tangents` | 3건 | 2.4절 이전 논의대로 벡터 전체(선언·resize·대입 3곳) 삭제. 함께 쓰이던 `spline_tube_normals`/`spline_tube_binormals`는 실제로 사용되고 있어 그대로 유지 |

**검증**: 8개 관련 파일 전체 컴파일 확인 — 신규 에러 0건.

### 2.5b nullPointerOutOfMemory (17건, actor_exporter.cc) — ✅ 완료

전부 A-4와 동일한 근본 원인: `calloc()` 결과를 null 체크 없이 바로 역참조. 실제로는 두 개의 서로 다른 지점에서 나온 17건:
- `_allocateCgltfData()`의 `data_ = calloc(1, sizeof(cgltf_data));` 이후 13건 전부 `data_->` 역참조 체인 — 할당 직후 `if (!data_) { _setError(...); return; }` 하나 추가로 13건 동시 해소.
- `_buildLights()`/`_registerExtension()`의 `new_extensions = calloc(new_count, sizeof(char*));` 이후 4건 — 각각 동일한 null 체크 추가(2곳).

**검증**: `actor_exporter.cc` 컴파일 확인 — 신규 에러 0건.

### 2.6b functionStatic (17건) — ✅ 완료 (14/17 적용, 3건 보류)

D-21과 동일 패턴(인스턴스 상태를 안 쓰는 멤버 함수 → `static`). `actor_exporter.h/.cc`(5), `asset_loader.h`(3, `destroyAsset`/`_createLight`/`_createCamera`), `material_component.h`(2, `setMap`/`setUvMatrix`), `extrude.h`(2, inline), `text/typesetter.h/.cc`(2, `const` 트레일링 제거 필요 — static 멤버 함수는 const 불가) — 전부 `this`/인스턴스 멤버 미사용 확인 후 적용.

**⚠️ 진짜 흥미로운 발견 — `AnimationAction::fadeIn()`/`fadeOut()`/`stopFading()`(3건)은 static 적용 보류**: cppcheck 말대로 "static 가능"한 게 맞긴 한데, 이유가 정상이 아니라 **함수 본문이 통째로 비어있어서**(파라미터도 안 씀)였음. `weight_` 멤버가 있고 `crossFadeFrom`/`crossFadeTo`가 이 함수들을 호출해 실제 페이드 효과를 기대하는 구조인데, 실질적으로 완전 미구현 상태 — 지금 이 세 함수를 호출해도 아무 일도 안 일어남. 사용자 확인 결과 지금은 그대로 두기로 결정, static 적용도 보류. **본 리포트 병합 시 A등급 후보(미구현 기능)로 별도 기록 필요.**

**검증**: 전체 `base/src/*.cc` 컴파일 확인 — 신규 에러 0건.

### 2.6c knownConditionTrueFalse (8건) — ✅ 완료 (6/8 적용, 1건 되돌림, 1건 유지)

앞선 `if (...) return;` 가드로 인해 뒤따르는 조건이 항상 참/거짓이 되는 중복 조건 패턴(D-5/D-12와 동일 성격) + 몇 건은 "포인터가 절대 null일 수 없는데도 null 체크하는" 패턴.

| 위치 | 원인 | 처리 |
|---|---|---|
| `animation_action.cc:122` | `_update()` 상단 `if (!playing_ \|\| paused_) return;`로 `playing_`/`!paused_`가 이미 보장됨 | `(playing_ && !paused_) ? time_scale_ : 0.0f` → `time_scale_`로 단순화 |
| `particles_component.cc:128,144` | 두 개의 `burst()` 오버로드 상단에 `if (isPaused() \|\| num <= 0) return;` 있어서 `num > 0`이 이미 보장됨 | `if (num > 0) { active_frames_ \|= 1u; }` → `active_frames_ \|= 1u;`로 단순화 |
| **`particles_component.cc:112`(⚠️)** | `replace_all`로 일괄 치환하다가 **1-인자 `burst(vint num)` 오버로드까지 실수로 같이 바뀜** — 이쪽은 `isPaused()`만 체크하고 `num <= 0` 가드가 없어서 `num > 0` 조건이 실제로 필요함(허위 매칭, cppcheck도 이 줄은 플래그 안 했었음) | 원래대로 되돌림. **일괄 치환 시 같은 텍스트 패턴이 다른 문맥에도 있는지 항상 확인해야 한다는 교훈 재확인** |
| `scene_impl.cc:969` | `if (dirty) {...} else if (!dirty && ...)` — else 분기 자체가 이미 `dirty==false`를 보장하므로 `!dirty &&`가 중복 | `else if (!dirty && dirty_count_ >= 0)` → `else if (dirty_count_ >= 0)` |
| `actor_exporter.cc`(줄번호 드리프트 발견 — 원래 2590이었으나 앞선 A-4 수정으로 2595로 밀림) | `_detectImageExtension()` 상단 `if (!data \|\| size < 4) return;`로 `size >= 4`가 보장돼 그 아래 `size >= 3` 체크가 중복 | `size >= 3 &&` 제거 |
| `asset_loader.cc:890` | `input_prim = &mesh->primitives[0];`(주소 연산은 항상 non-null) | `input_prim ? input_prim->targets_count : 0` → `input_prim->targets_count` |
| `asset_loader.cc:1033` | `name = name_str.c_str();`(`std::string::c_str()`는 항상 non-null 보장) — `name ? name : "texture"` 형태 | **유지** — 코드베이스 전반(`_recursePrimitives`/`_recurseEntities` 등)에 반복되는 방어적 관용구라 이 한 곳만 다르게 고치면 일관성이 깨짐 |

**검증**: 관련 5개 파일 컴파일 확인 — 신규 에러 0건.

### 2.6d uselessOverride (6건) — ✅ 완료 (1/6 적용, 5건 보류)

`MaterialComponent::onRebuild() { return onRefresh(); }`만 base(`Component::onRebuild()`)와 무조건 동일해서 삭제(선언·정의 양쪽). 나머지 5건(`ColliderComponent::onDispose`, `JointComponent::onRefresh`, `RigidbodyComponent::onRefresh`, `VehicleComponent::onRefresh`/`onDispose`)은 전부 본문이 `#ifdef USE_JOLT ... #endif`로 감싸여 있어서, **Telechips(`GRAPI_USE_JOLT: OFF`)에서만 base와 동일해지고 물리 활성 플랫폼(Windows 등)에서는 실제 로직이 있음** — 삭제하면 안 됨. 2.5절의 `physics_scene`(unreadVariable) 때와 동일한 함정.

### 2.6e useStlAlgorithm (5건) — ✅ 완료

D-19와 동일 패턴. `actor_exporter.cc`(all-whitespace 검사 → `std::all_of`), `custom_material_component.cc`(카운트 루프 → `std::count_if`), `collider_component.cc`(반복자 수동 전진 → `std::next`), `typesetter.cc`(변환 루프 → `std::transform`+`std::back_inserter`), `view_impl.cc`(첫 지원 포맷 탐색 → `std::find_if`). 필요한 `<algorithm>`/`<iterator>` 헤더 추가 확인.

### 2.6f useInitializationList (4건) — ✅ 완료 (3/4 적용, 1건 보류)

D-17과 동일 패턴. `rigidbody_component.cc`(`body_data_ = nullptr;`는 헤더에 이미 `= nullptr` 기본 멤버 초기화가 있어 완전히 중복 — 그냥 삭제), `sprite_component.cc`/`text_component.cc`(`image_ = make_unique<Image>();` → 초기화 목록으로 이동, `text_component.cc`는 멤버 선언 순서(`image_`가 `text_field_`보다 먼저 선언됨)에 맞춰 순서 조정 필요).

**보류 1건**: `particles_component.h`의 이동 생성자(`particle_buffer_` 등)는 이번 세션에서 이미 F-9(use-after-move 오탐)로 세밀하게 검토·주석까지 달아둔 코드라, 일부 멤버만 초기화 목록으로 옮기고 `counters_`(옵셔널, 조건부 emplace)는 본문에 남기는 부분적 리팩터링이 득보다 리스크가 커서 보류.

**검증**: 전체 `base/src/*.cc` 컴파일 확인 — 신규 에러 0건.

### 2.7 나머지 소규모 카테고리 (10종, 15건) — ✅ 완료 (15/15)

| 체크 | 내용 | 처리 |
|---|---|---|
| `variableScope`(2) | `using_cache`, `spline_tube_tangents` | unreadVariable 정리 때 변수 자체가 삭제돼서 자동 해소 |
| `shadowVariable`(2) | `asset_loader.cc`의 중첩 `for`문 `len` 변수명 충돌, `mesh_component.cc`의 `im` 재선언 | `len`→`joint_count` 리네임 / `im` 재선언 제거하고 바깥 `im` 재사용(중복 조회이기도 했음) |
| `invalidPointerCast`(2) | `asset_loader.cc`의 `unsigned char*`→`float*` reinterpret_cast(바이너리 애니메이션 타임라인 파싱) | B-3과 동일 — 기존 NOLINT에 `cppcheck-suppress invalidPointerCast` 추가 |
| `duplicateConditionalAssign`(2) | `if (type_!=type) type_=type` 패턴 | `collider_component.cc`는 무조건 중복이라 단순화, `joint_component.cc`는 `#ifdef USE_JOLT` 블록에 `joint_data_=nullptr`가 더 있어서 보류(2.6d와 동일 함정) |
| `duplicateBreak`(2) | `rigidbody_component.h`의 `return expr; return false;` (도달 불가) | 죽은 `return false;` 제거 |
| `stlFindInsert`(1) | `rigidbody_component.cc`의 `find()`+`[]` 중복 해시 조회 | `try_emplace`/저장해둔 iterator 사용으로 재작성(관련 있던 `removeContactedActor`도 같이 정리) |
| `shadowArgument`(1) | `animation_mixer.cc::update(vfloat delta_time)` 내부에 지역 `delta_time` 재선언 | `segment_time`으로 리네임 |
| `nullPointerRedundantCheck`(1) | **실제 버그** — 아래 참고 | 수정 완료 |
| `assignBoolToFloat`(1) | **실제 버그** — 아래 참고 | 수정 완료 |
| `autoVariables`(1) | `extended_material_component.cc` — "지역 auto 변수의 주소가 함수 파라미터에 대입됨"(심각도 error) | ✅ 완료(2026-07-03, WSL) — 아래 참고, 오탐으로 확인 후 억제 |

#### 🐛 실버그 1 — `KHR_materials_volume`이 항상 등록됨 (`actor_exporter.cc`)

`_convertExtendedMaterial()`의 다른 모든 확장 블록(`KHR_materials_transmission` 등)은 `if (drtmat->getXxxFactor() != 기본값)`로 실제 설정된 경우에만 등록하는데, `KHR_materials_volume`만 `if (drtmat) { cgmat->has_volume = true; ... }`로 되어 있어 **null 체크만 하고 사실상 무조건 실행**됨(이 함수 안에서 `drtmat`는 이미 여러 곳에서 조건 없이 역참조되고 있어 null일 수 없음 — cppcheck가 "redundant or null deref"로 지적한 지점).

**근본 원인 분석**: `ExtendedMaterialComponent`에는 `key_.hasVolume`이라는 내부 플래그가 있고(`setVolumeAbsorption()`/`setVolumeThicknessFactor()` 호출 시에만 `true`가 됨) 이게 다른 `key->hasXxxTexture` 필드들과 동일한 역할을 하도록 설계된 것으로 보이나, 이 플래그는 `ExtendedMaterialComponent`(내부 구현)의 private 멤버라 exporter가 쓰는 공개 API(`ExtendedMaterial`)에는 노출이 안 됨. exporter는 다른 블록들처럼 "대표 factor가 기본값과 다른가"로 판단할 수밖에 없는 구조.

**수정**: `if (drtmat)` → `if (drtmat->getVolumeThicknessFactor() != 0.0f)`. glTF `KHR_materials_volume` 스펙상 `thicknessFactor` 기본값이 0이고 0이면 볼륨 효과가 무의미하다는 사양과도 일치.

**영향**: 이 버그로 인해 지금까지 익스포트된 모든 GLB/GLTF 파일에 실제 볼륨 속성을 설정하지 않았어도 `KHR_materials_volume` 확장과 기본 attenuation 값이 항상 끼어들어갔을 것으로 추정 — 뷰어에 따라 렌더링에 영향을 줄 수 있음.

#### 🐛 실버그 2 — `TemporalAntiAliasingOptions::upscaling`이 절대 의도대로 작동할 수 없던 구조 (`view.h`, 공개 API)

우리 공개 API(`base/include/grapi/base/view.h`)의 `TemporalAntiAliasingOptions::upscaling`이 `bool`(업스케일링 on/off)로 정의돼 있었는데, 이 값이 그대로 대입되는 Filament의 `filament::TemporalAntiAliasingOptions::upscaling`은 **업스케일 배율을 나타내는 `float`**(기본값 `1.0f` = "배율 없음")임. `bool`→`float` 암묵 변환으로:
- `upscaling = true` → Filament 쪽엔 `1.0f`(배율 없음, 즉 업스케일링 비활성과 동일한 값)로 들어감
- `upscaling = false` → `0.0f`(무의미한 배율)

즉 **이 옵션은 처음부터 의도한 대로 동작한 적이 없는 구조적 버그**. 영향 범위 확인(레포 내부에는 `view_impl.cc` 자기 자신 외 사용처 없음, `base/samples`에도 미사용) 후 사용자 확인 받아 타입 자체를 `vfloat upscaling = 1.0f;`(진짜 배율)로 변경. 사용처 2곳(대입, dirty-check 비교) 모두 float로도 문법적/의미적으로 자연스럽게 동작 확인.

**검증**: 전체 `base/src/*.cc` 컴파일 확인 — 신규 에러 0건.

#### 🔍 autoVariables(`extended_material_component.cc`) — WSL/Telechips 재현 결과: 오탐 확인

Telechips 크로스 컴파일 환경(`environment-setup-aarch64-telechips-linux` 활성화 후) `cppcheck --project=.../linux-telechips-tcc803x-release/compile_commands.json`으로 재현 성공: `extended_material_component.cc:130:5: error: Address of local auto-variable assigned to a function parameter. [autoVariables]` — `*uvmap = retval;`.

**원인 분석**: `_constrainMaterial(MaterialKey* key, UvMap* uvmap)`에서 `UvMap retval {};`으로 지역 변수를 만들어 채운 뒤 마지막에 `*uvmap = retval;`로 대입. `UvMap`은 `external/filament/libs/gltfio/include/gltfio/MaterialProvider.h:122`에 `using UvMap = std::array<UvSet, 8>;`로 정의된 **POD 배열 타입**(`UvSet`도 `enum : uint8_t`) — `*uvmap = retval`은 `std::array::operator=`를 통한 **값 복사**이지 `retval`의 주소를 저장하는 게 아님. `autoVariables` 체크가 "포인터 역참조 대입" 패턴(`*ptr = local_array`)을 주소-저장으로 오인한 cppcheck 쪽 오탐으로 확정(Windows cppcheck 2.21.0에서 재현 안 됐던 것도 이 체크의 데이터플로 분석이 버전/설정에 민감하다는 방증).

**처리**: `// cppcheck-suppress autoVariables ; UvMap is std::array<UvSet, 8> (POD), this is a value copy, not an address escape` 인라인 억제 추가. Telechips `cppcheck` 재실행으로 억제 확인, Telechips ninja 빌드로 컴파일 재확인(신규 에러 0건, 주석 추가라 애초에 영향 없음).

### 2.6 returnByReference (21건) — ✅ 완료

D-16과 완전히 동일한 패턴(getter가 값 대신 `const&` 반환). 전부 `base/src/`(내부 구현) 클래스라 D-16의 "공개 API는 보류" 예외 없이 21건 모두 적용: `actor_exporter.h`(1), `custom_material_component.h`(1), `joint_component.h`(2), `mesh_component.h`(1), `texture_component.h`(1), `vehicle_component.h`(7), `text/typesetter.h`(1), `view_impl.h`(7). 전부 `return member_;` 단순 패턴이라 `.h` 선언과 `.cc` 정의 양쪽의 반환 타입만 `Type` → `const Type&`로 변경. 전체 `base/src/*.cc` 컴파일 검증 완료(신규 에러 0건).

---

## 3. 최종 재검증 라운드 (2026-07-03, v2 전체 재스캔 + Windows v12→v13)

이 세션의 모든 코드 수정(Windows 배치 + WSL 전용 배치)이 커밋·pull로 양쪽에 동기화된 뒤, 최종 확인 차원에서 전체 플랫폼을 처음부터 다시 스캔(WSL `_v2`, Windows `clangtidy_v13`/`cppcheck_result_v9`). 이 라운드에서 **처음으로 Android arm/x86/x64**(그동안 arm64만 검증)까지 포함해 전 플랫폼을 커버.

### 3.1 스캔 범위 확장 — Android arm/x86/x64 최초 스캔

기존엔 Android는 arm64 하나만 스캔했었음(08번 문서 §5.3에 명령어는 있었지만 실제로 arm/x86/x64는 안 돌림). 08번 문서 §5.3에 3종 전체 명령어를 추가해서 처음으로 커버 — 계획 문서가 처음부터 예측했던 "32비트/64비트 타입 폭 차이"가 실제로 arm/x86에서만 발견됨(아래 §3.3 참고).

### 3.2 Windows clang-tidy 환경 문제 — v12 전체 실패 → v13 해결

**증상**: `clangtidy_v12.txt`에서 스캔 대상 131개 파일 **전부** `Error while processing`로 실패 — 0건이 아니라 애초에 분석 자체가 안 된 상태. 에러 메시지는 `type_traits:723:111: error: '_Ty' does not refer to a value`.

**원인 확인**: PC에 새로 설치된 **VS 18 Insiders**(MSVC STL 14.51, 최신 C++26 문법 포함)가 원인. `CMakeCache.txt`상 `windows-msvc-x64-release`의 실제 컴파일러는 VS2022 Professional의 `cl.exe`(MSVC 14.38)로 정상 설정돼 있었는데, **clang-tidy/clang-cl이 compile_commands.json의 `cl.exe` 경로와 무관하게 설치된 VS 중 가장 최신 버전을 자체적으로 자동 탐지**해서 그 STL 헤더를 사용하는 것으로 확인(`clang-cl.exe ... -v` 로 실제 검색 경로 직접 확인). 이번 세션 내내 기준으로 삼은 VS2022 번들 clang-tidy(LLVM 19.1.5)가 자기보다 새로운 VS18의 STL 문법을 못 읽어서 전부 깨짐. 우리 코드 문제가 아니라 **로컬 PC의 VS 설치 환경 변화로 인한 순수 툴체인 이슈**.

**해결**: clang-cl의 `/vctoolsdir <경로>` 플래그로 VS2022 툴셋을 명시적으로 고정 — 공백 없는 결합형(`/vctoolsdir<경로>`)도 지원되는 것 확인, `run-clang-tidy`에 `-extra-arg="/vctoolsdir<VS2022 MSVC 14.38 경로>"`로 전달.

```powershell
$ClangTidyBin = "C:\Program Files\Microsoft Visual Studio\2022\Professional\VC\Tools\Llvm\x64\bin\clang-tidy.exe"
$VcToolsDir = "C:\Program Files\Microsoft Visual Studio\2022\Professional\VC\Tools\MSVC\14.38.33130"

python "C:\Program Files\Microsoft Visual Studio\2022\Professional\VC\Tools\Llvm\x64\bin\run-clang-tidy" `
  -clang-tidy-binary $ClangTidyBin `
  -p out/build/windows-msvc-x64-release `
  -extra-arg="/vctoolsdir$VcToolsDir" `
  '.*base[\\/]src[\\/].*' `
  > clangtidy_v13.txt 2>&1
```

> **⚠️ 부수 삽질**: 처음 이 명령을 돌렸을 때 `.*base/src/.*`(슬래시)를 그대로 썼더니 `Running clang-tidy for 0 files out of 1963`으로 하나도 안 잡힘. `run-clang-tidy.py` 내부에서 `os.path.join`으로 만든 파일 경로가 Windows에서는 백슬래시(`base\src\...`)인데 정규식은 슬래시만 찾고 있었던 것. `.*base[\\/]src[\\/].*`(백슬래시/슬래시 둘 다 매칭하는 문자 클래스)로 고쳐서 해결 — 131개 파일 정상 매칭 확인.

**최종 결과 (v13)**: 131개 파일 전부 정상 스캔. `base/` 코드 자체의 warning **0건**. 잔여 "Error while processing" 2건(`name_component.cc`, `context.cc`)은 `external/filament/libs/utils/include/utils/StructureOfArrays.h`의 `[[maybe_unused]]` 속성 관련 서드파티 이슈로, v2~v14 스캔 로그 전체에 걸쳐 예전부터 계속 있던 것(이번 세션에 새로 생긴 문제 아님, 우리 소관 아님) 확인. warning 3건은 기존 §1.7에 기록된 서드파티 항목(`bugprone-forward-declaration-namespace`, `external/filament/libs/gltfio/src/Utility.h`)과 정확히 일치. **Windows 쪽 완전히 클린.**

### 3.3 v2 재스캔에서 새로 발견된 7건 — ✅ 전부 수정 완료

기존에 문서화된 항목들은 전부 재확인되어 일치(회귀 없음). 다만 Android arm/x86/x64 최초 스캔 + Linux/WebGL 재스캔에서 다음 7건이 새로 발견되어 전부 수정:

| # | 위치 | 체크 | 플랫폼 | 원인/처리 |
|---|---|---|---|---|
| 1 | `geometry_component.cc:537` (`sphere`) | `bugprone-unchecked-optional-access` | Linux/WebGL (LLVM21) | 538번(`box`)과 같은 성격의 오탐인데 NOLINT를 538에만 달고 537은 놓쳤음. NOLINT 추가 |
| 2 | `ktx2_reader.cc:484` `getTexture()` | `modernize-use-nodiscard` | WebGL | `[[nodiscard]]` 누락 — 추가 |
| 3 | `asset_impl.h:45` | `bugprone-narrowing-conversions` | Android **arm/x86**(32비트, 최초 발견) | `static_cast<vint64>(mesh_count_)`로 64비트로 widening했다가 `vector::iterator::operator+`의 `difference_type`(32비트 int)로 다시 narrowing되던 구조. `static_cast<std::vector<BaseID>::difference_type>(mesh_count_)`로 목표 타입에 직접 캐스팅하도록 수정 |
| 4 | `custom_material_provider.cc:37` | `bugprone-narrowing-conversions` | Android arm/x86 | `std::streamoff`(64비트)→`std::streamsize`(이 ABI에서 32비트) narrowing. `static_cast<std::streamsize>(file.tellg())` 명시 |
| 5 | `actor_exporter.cc:202` `exportAsset()` | `constParameterPointer` | Telechips (cppcheck) | 리포지토리 전체에서 호출부가 없는 공개 API(죽은 코드 아님, SDK 소비자용으로 추정) — 같은 파일의 형제 메서드들(`_collectFromAsset` 등)과 동일하게 `Asset*`→`const Asset*`로 변경(비파괴적 변경) |
| 6 | `actor_exporter.cc:2634` `_detectMimeType()` | `functionStatic` | Telechips (cppcheck) | 이미 static 처리된 형제 함수들(`_getMimeTypeFromExtension` 등)과 동일 패턴인데 빠짐 — `static` 추가 |
| 7 | `asset_loader.cc:405,410` | `invalidPointerCast` | Telechips (cppcheck) | §2.7에서 "완료"로 기록했던 억제가 **실제로는 안 먹히고 있었음**(아래 참고) — 재수정 |

**⚠️ 재수정이 필요했던 사례 — `asset_loader.cc`의 `invalidPointerCast` 억제**: §2.7에서 "기존 NOLINT에 `cppcheck-suppress invalidPointerCast` 추가"로 기록했던 처리가 `// NOLINT(cppcoreguidelines-pro-type-reinterpret-cast) cppcheck-suppress invalidPointerCast`처럼 **한 줄짜리 주석 안에 텍스트로만 이어붙인 것**이었음. C++ 문법상 `//`부터 줄 끝까지는 통째로 하나의 주석이라, `cppcheck-suppress`가 주석 "시작 토큰"이어야 인식하는 cppcheck 입장에서는 그냥 무시되는 일반 텍스트였던 것 — 재스캔해보고서야 발견. **1차 수정 시도**(`// A  // B`처럼 `//`를 하나 더 넣어 두 번째 주석처럼 보이게)도 여전히 같은 이유로 실패(C++엔 "주석 안의 또 다른 //"라는 개념이 없음). **최종 해결**은 cppcheck 표준 관례대로 대상 줄 **바로 위에 `// cppcheck-suppress invalidPointerCast` 전용 줄**을 추가하고, `NOLINT`는 원래 줄에 그대로 둠. 재스캔으로 0건 확인. **교훈**: 억제 주석을 합쳐 쓸 때는 실제로 재스캔해서 먹히는지 반드시 확인할 것 — "코드가 그렇게 보인다"와 "도구가 그렇게 해석한다"는 다를 수 있음.

**검증**: 7건 전부 관련 프리셋(linux-clang-release/linux-webgl-release/linux-android-arm-release/linux-telechips-tcc803x-release) 빌드 + 개별 재스캔으로 0건 확인.

**⚠️ 스캔 아티팩트 주의**: `actor_exporter.cc:202` 재검증 시 `--file-filter`로 스코프를 2개 파일로 좁혀서 재스캔했더니 `unusedFunction`이 새로 뜸. 이건 진짜 신규 문제가 아니라 cppcheck의 `unusedFunction` 체크가 프로젝트 전체를 봐야 정확한데 스코프를 좁혀서 생긴 스캔 아티팩트(원래 전체 스캔인 v2에서는 이 항목이 없었음). **다음 전체 재스캔(v3) 때 이 부분이 실제로 뜨는지 반드시 확인 필요** — `exportAsset()`이 진짜 호출부가 없는 채로 계속 남아있다면 그때는 실제 `unusedFunction`으로 뜰 수 있음(공개 API라 그대로 둘지, 정리할지는 그때 판단).

### 3.4 최종 확인 — Telechips 전체 재스캔(v3) + WebGL/Android x64 빌드

7건 수정 후, 스코프를 좁히지 않은 **Telechips 전체 재스캔**(`cppcheck_telechips-tcc803x_v3.txt`)과 **WebGL/Android x64 빌드**로 최종 확인.

**Telechips v3 결과**: `base/` 기준 findings 582 → 578건(정확히 -4). `diff`로 v2/v3을 줄 단위 비교한 결과:
- **사라짐(수정 확인)**: `actor_exporter.cc:202`(`constParameterPointer`), `actor_exporter.cc:2634`(`functionStatic`), `asset_loader.cc:405,410`(`invalidPointerCast`) — 4건 전부 정확히 사라짐.
- **줄/컬럼만 밀림(실질 변화 아님)**: `asset_loader.cc:1032→1034`(`knownConditionTrueFalse`, §2.6c에 "관용구라 유지"로 이미 기록된 항목이 억제 주석 2줄 추가로 밀림), `ktx2_reader.cc:484:12→484:26`(`duplInheritedMember`, F-5 기존 허용 패턴이 `[[nodiscard]]` 추가로 컬럼만 밀림).
- **§3.3에서 우려했던 `unusedFunction`(`exportAsset`)은 전체 스캔에서 끝내 나타나지 않음** — 스코프 좁힌 재스캔에서만 보였던 순수 아티팩트였음이 확정.

**빌드**: `linux-webgl-release`, `linux-android-x64-release` 둘 다 성공. 이 라운드에서 손댄 7개 파일과 무관하게 나머지 모든 플랫폼 재스캔은 불필요하다고 판단(변경 규모가 작고 이미 관련 플랫폼 전부 개별 검증됨) — **최종 재검증 라운드 완전히 종료**.

---

## 4. 체크리스트 (본 리포트 병합 시 반영 사항)

```
[x] Clang-Tidy 멀티플랫폼 스캔 결과 분석 (Linux/WebGL/Android)
[x] unchecked-optional-access 18건 전수 분석 및 코드 수정
[x] implicit-widening 1건 수정
[x] Android 전용 2개 항목(multi-level-pointer-conversion, JNI_OnLoad naming) NOLINT 처리
[x] Android/WSL 전용 항목 재검증 (WSL 반영 후) — multi-level-pointer-conversion(4건 정상), JNI_OnLoad(정상), unchecked-optional-access(기존 18건 정상 + Android 전용 신규 1건 발견·수정, geometry_component.cc:538)
[x] misc-const-correctness pointee-const 673건 — WSL에서 -fix 적용 완료. 부작용으로 컴파일 에러 44건 발생(clang-tidy가 함수 밖으로 흘러나가는 non-const 요구를 못 봄) → 해당 지점만 개별 되돌리고 NOLINT+사유 주석 추가, 재스캔 0건·빌드 정상 확인
[x] Cppcheck 5개 플랫폼 규모 분석, Telechips 편차 원인 규명(스캔 설정 아님, 실제 코드 경로 차이)
[x] Cppcheck Telechips const-correctness 계열(constVariablePointer/constParameterPointer/constParameterReference/constVariableReference, 476건) 코드 수정 — 461건 적용, 15건 확인 후 보류(오탐/공개API), 컴파일 검증 완료
[x] Cppcheck Telechips 나머지 카테고리(20종, 약 158건) 개별 분석 및 수정 완료 (autoVariables 1건은 WSL/Telechips 재현 후 별도 항목으로 완료 처리, 아래 참고)
[x] 발견한 실버그 2건 수정 — `KHR_materials_volume` 항상 등록되던 문제, `TemporalAntiAliasingOptions::upscaling` bool/float 오설계(공개 API 타입 변경)
[x] Renesas missingInclude 1건 확인 — `context.cc`가 include하는 `generated/resources/base_materials.h`는 빌드 시 자동 생성되는 산출물(셰이더/머티리얼 임베딩 헤더, `out/build/.../generated/resources/`)이라 실제 코드 문제 아님. severity도 `information`(F-7과 동일 성격) — 조치 불필요
[x] autoVariables(extended_material_component.cc) — WSL/Telechips에서 재현 완료, `UvMap`(std::array) 값 복사를 주소-저장으로 오인한 cppcheck 오탐으로 확정, cppcheck-suppress 처리
[x] Android arm/x86/x64 최초 스캔 (그동안 arm64만 검증했었음) — §3.1
[x] Windows clang-tidy 환경 문제(v12 전체 실패, VS18 Insiders STL 자동탐지 충돌) 원인 규명 및 /vctoolsdir 고정으로 해결, v13 재스캔 클린 확인 — §3.2
[x] v2 최종 재스캔 신규 발견 7건 전부 수정 및 재검증 완료 (geometry_component.cc 추가 NOLINT, ktx2_reader.cc nodiscard, asset_impl.h/custom_material_provider.cc narrowing-conversion, actor_exporter.cc const/static 2건, asset_loader.cc invalidPointerCast 억제 재수정) — §3.3
[x] Telechips 전체 재스캔(v3) + WebGL/Android x64 빌드로 최종 확인 — 신규 4건 전부 해소, unusedFunction 아티팩트였음 확정, 회귀 없음 — §3.4
[x] 본 리포트에 병합 완료 (2026-07-06, A-18~A-21/D-29/D-30/F-10~F-12 신규 + 기존 다수 항목에 추가 확인분 반영. 문서 분할은 여전히 별도 결정 사항으로 보류)
```

---

## 5. 관련 문서

- `260706_황인성_clangtidy_cppcheck_verification_report.md` — 병합 대상 본 리포트
- [08-multiplatform-verification-plan.md](08-multiplatform-verification-plan.md) — 이번 스캔에 사용한 명령/환경
- [09-clangtidy-v9-header-findings.md](09-clangtidy-v9-header-findings.md) — 이전 단계(헤더 재스캔) 예비 문서, 이미 본 리포트에 병합 완료
