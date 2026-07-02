# Clang-Tidy v9 — HeaderFilterRegex 수정 후 신규 발견 (예비 문서)

> **이 문서는 예비 정리본**. 검토/처리는 전부 완료되어 `260702_황인성_clangtidy_cppcheck_verification_report.md`(이하 "본 리포트")에 병합 완료됨 (A-16/A-17, D-26, D-22~D-28, F-9).  
> **최종 상태 (2026-07-02)**: 2장의 잠재 버그 후보 6건 전수 처리 완료 — 실버그 2건(구 A-18/A-19)은 본 리포트 A-16/A-17로 병합, 구 A-16(예외탈출 3건)은 D-26 Rule of Five에 통합, 구 A-17(use-after-move)은 오탐으로 F-9 신규 등록. 3장 대량 카테고리(D-22~D-27, 1,723건)와 4장 개별 소량 카테고리(D-28, 19종 100건) 전부 코드 수정 + `clangtidy_v10`~`v14` 재검증까지 완료. 상세 내용은 본 리포트 6장(D-22~D-28) 참고.
> 원시 결과: `C:\working\grapi-base\clangtidy_v9.txt` (2026-07-02, Windows `windows-msvc-x64-release`, LLVM 19)  
> 비교 대상: `clangtidy_v8`까지의 "유저 코드 경고 0건" 결과, WSL `clangtidy_linux-clang_v1.txt`

---

## 0. 배경 — 왜 이 문서가 생겼나

`.clang-tidy`의 `HeaderFilterRegex`가 `'.*(grapi-base/(base|samples)).*\.(h|hpp)$'`로 되어 있었는데, 이 정규식은 슬래시(`/`)를 쓰는 반면 Windows 컴파일 DB의 경로는 백슬래시(`\`)를 씀. **정규식이 Windows에서 한 번도 매치된 적이 없었고**, HeaderFilterRegex가 매치 안 되면 clang-tidy는 헤더 파일(`.h`) 안의 진단을 전부 숨김(기본 동작).

**증거**: 최초 베이스라인(`clangtidy_v2.txt`, 1852건) 전체에서 `.h`/`.hpp` 파일을 가리키는 경고는 **0건** — 전부 `.cc` 파일 경고였음. 즉 지금까지 문서화된 "유저 코드 경고 0건"(v6~v8)은 **"`.cc` 파일만 봤을 때 0건"**이었지, 헤더 파일은 애초에 검사된 적이 없었음.

**수정**: `.clang-tidy`의 `HeaderFilterRegex`를 `'.*grapi-base[/\\](base|samples)[/\\].*\.(h|hpp)$'`로 변경(양쪽 슬래시 모두 매치, `C:\working\grapi-base`와 `/home/insung52/grapi-base` 양쪽 저장소에 동일 적용). 이후 재스캔한 것이 `clangtidy_v9.txt`.

이 발견은 WSL에서 Linux/WebGL 플랫폼용 재검증([08-multiplatform-verification-plan.md](08-multiplatform-verification-plan.md)) 작업 중 우연히 드러남 — Linux clang-tidy는 경로가 전부 `/`라 정규식이 정상 매치되어 헤더 경고가 그대로 노출되었고, Windows와 비교하다 원인을 역추적함.

---

## 1. 규모

| 항목 | 수치 |
|------|------|
| 원시 `warning:` 라인 수 (base/, external 제외) | 76,517 |
| **중복 제거 후 고유 위치 수** | **1,833** |
| 중복 원인 | 헤더 하나가 여러 `.cc` 파일에 include될 때마다 동일 위치가 매번 다시 보고됨 (예: `object.h:35`가 133개 TU에서 각각 보고 → 133회 집계) |
| 체크 종류 수 | 29종 |

> **집계 방법**: `grep "warning:" clangtidy_v9.txt`로 `base/`(external 제외) 라인만 추출 → `file:line:col [checkID]`만 남기고 `sort -u`로 중복 제거.

Linux(WSL, LLVM 21) 쪽 동일 방식 집계는 고유 위치 2,475건 — Windows(1,833건)보다 많음. 이 차이는 플랫폼 고유 버그라기보다 **LLVM 버전 차이**(21이 19보다 일부 체크가 더 정교함, 예: `misc-const-correctness`의 pointee-const 하위 체크)로 추정됨. 정밀 비교는 추후 진행.

---

## 2. A등급 후보 — 잠재적 실버그 (6건, 최우선 검토)

### A-16(가칭). 생성자에서 예외 탈출 가능성 (3건)
**체크**: `bugprone-exception-escape`

| 위치 | 클래스 |
|------|--------|
| `keyframe_track.h:13` | `KeyframeTrack` |
| `components/collider_component.h:14` | `ColliderComponent` |
| `components/rigidbody_component.h:11` | `RigidbodyComponent` |

A-9(`AssetImpl` **소멸자**)와 유사하지만 이번엔 **생성자**. 생성자에서 예외가 탈출하는 것 자체는 소멸자만큼 치명적이진 않음(객체가 생성되지 않은 것으로 처리되어 스택 언와인딩이 정상 동작) — 다만 WebGL(`-fno-exceptions`) 빌드에서 애초에 예외 관련 코드가 있으면 안 되므로, A-9와 동일하게 해당 클래스들이 왜 "예외를 던질 수 있는" 것으로 판단됐는지(멤버 초기화 리스트에서 예외를 던지는 생성자를 가진 멤버가 있는지 등) 확인 필요.

> **✅ 처리 완료 — D-26에 통합**: 경고 위치가 셋 다 생성자가 아니라 **클래스 선언 줄 자체**(`class KeyframeTrack {` 등)를 가리킴. 공통점: 세 클래스 모두 소멸자/복사/이동 연산자를 **하나도 명시적으로 선언 안 함** → 암묵 생성된 이동/소멸자의 noexcept 여부를 clang-tidy가 정적으로 증명 못 해 보수적으로 "예외 가능" 판단. D-26(Rule of Five)에 통합해 세 클래스 모두 명시적 Rule-of-Five 적용(`KeyframeTrack`은 값 타입이라 복사/이동 전부 `= default`, `ColliderComponent`/`RigidbodyComponent`는 `Component` 파생이라 복사 delete/이동 default) + 이동 생성자·대입에 `noexcept` 명시. 그래도 `bugprone-exception-escape`가 3건 다 남아 최종적으로 NOLINT 처리(`noexcept` 명시로 계약은 이미 지켜짐, clang-tidy가 `std::list`/`JPH::ShapeRefC` 등 멤버까지 완전 추적 못 하는 보수적 오탐). 상세는 본 리포트 D-26/D-28 절 참고.

### A-17(가칭). Move 이후 재사용 (1건, 진짜 버그 가능성 높음)
**체크**: `bugprone-use-after-move`
**위치**: `components/particles_component.h:176:34`
**메시지**: `'other' used after it was moved`

`other`라는 변수/파라미터를 `std::move()`한 뒤 다시 읽는 패턴 — 실제로 미정의 동작(UB)일 수 있음. 코드 확인 후 실제 버그인지, 아니면 move 후 재대입 등으로 안전한 상황인지 판단 필요.

> **✅ 처리 완료 — 오탐 확인, F-9로 등록**: 실제 코드는 `ParticlesComponent(ParticlesComponent&& other) noexcept : Component(std::move(other)) { particle_buffer_ = std::move(other.particle_buffer_); ... }` — `std::move(other)`는 **베이스 클래스(`Component`) 서브오브젝트로 슬라이싱하는 이동**(entity_/dirty_flag_ 두 멤버만 있는 별개 서브오브젝트)이고, 이후 접근하는 `other.particle_buffer_` 등은 전부 `ParticlesComponent` 자신의 멤버라 베이스 슬라이싱과 무관하게 아직 손 안 댄 상태. clang-tidy가 "베이스 서브오브젝트만 이동됨"과 "객체 전체가 이동됨"을 구분 못 해서 나는 알려진 오탐 패턴 — **실제 버그 아님**. 본 리포트 F-9로 신규 등록, `// NOLINT(bugprone-use-after-move)` 적용 완료(최초엔 NOLINT를 엉뚱한 줄에 달았다가 재스캔에서 재발견 → 실제 경고가 찍히는 줄로 이동해 해결, F-8과 동일 교훈).

### A-18(가칭 → 본 리포트 A-16으로 병합 완료 ✅). 멤버 초기화 누락 (1건)
**체크**: `cppcoreguidelines-pro-type-member-init`
**위치**: `physics_context.h:68:7`
**메시지**: `constructor does not initialize these fields: body_interface_`

A-7과 동일 패턴(생성자가 특정 멤버를 초기화 안 함). `body_interface_`가 Jolt Physics 관련 멤버로 추정 — 사용 전 항상 별도 초기화 함수를 거치는지, 아니면 초기화 없이 바로 쓰일 경로가 있는지 확인 필요.

> **✅ 1차 검토 완료 (코드 확인함) — 실제 갭, 현재는 안전 (A-7과 동일 성격)**: `ContactListenerImpl`은 생성자가 없어 암묵 기본생성자가 `body_interface_`(raw pointer)를 그대로 둠. `pollContactAdded()`/`pollContactRemoved()`에서 `body_interface_->GetUserData(...)`로 역참조하지만, 세팅하는 유일한 경로 `setBodyInterface()`가 `SceneImpl::getPhysicsContext()`(scene_impl.cc:625~644)에서 `PhysicsContext` 생성 직후 바로 호출됨. `contact_listener`를 쓰는 모든 곳(`_runPhysicsFeedbackSystem` 등)이 이 게터를 거치므로 **현재 코드 경로에서 미초기화 역참조는 발생 안 함** — 다만 호출 순서가 바뀌거나 다른 경로가 추가되면 크래시 소지가 있는 잠재적 지뢰. A-7과 동일하게 `= nullptr` 기본값 지정 권장.

### A-19(가칭 → 본 리포트 A-17로 병합 완료 ✅). 확장 전 캐스트 (1건)
**체크**: `bugprone-misplaced-widening-cast`
**위치**: `geometries/sphere.h:27:7`
**메시지**: `either cast from 'int' to 'vsize' ... is ineffective, or there is loss of precision before the conversion`

A-10(`curve.cc:42`)과 동일 패턴 — 연산 후 캐스트가 적용되어 의도한 확장이 안 됨.

> **✅ 1차 검토 완료 (코드 확인함) — 실제 버그, A-10과 동일 패턴**: `Sphere` 생성자에서 `width_segments`/`height_segments`(둘 다 `vint`)로 `(width_segments + 1) * (height_segments + 1)`을 **int 범위에서 먼저 계산**한 후에야 `static_cast<vsize>` 적용(sphere.h:26-27). 세그먼트 수가 대략 46,341 이상이면(`INT_MAX` 제곱근 근처) int 오버플로(부호 있는 정수 오버플로 UB) 발생 가능 → `vertices_.reserve(vertex_count)`에 쓰레기 크기 전달 위험. 실사용 세그먼트 수(수십~수백)로는 발생 가능성 낮지만 방어적 수정 가치 있음.
> ```cpp
> // 수정
> const vsize vertex_count =
>     static_cast<vsize>(width_segments + 1) * static_cast<vsize>(height_segments + 1);
> ```

---

## 3. 대량/기계적 처리 가능 (1,663건, 91%)

### D-22(가칭). `[[nodiscard]]` 누락 — 대량 (1,376건)
**체크**: `modernize-use-nodiscard`

거의 전부 헤더에 선언된 getter/조회성 함수들. D-4, D-7에서 일부(개별 함수) 처리했지만 그건 빙산의 일각이었음 — 헤더 전체 기준으로는 1,376건.

```cpp
// 샘플
// aabb.h:101 — bool intersects(...) const;
// aabb.h:127 — glm::vec3 projectToScreen(...) const;
// aabb.h:130 — glm::vec3 getMin() const;
```

**처리 방향**: 성격이 균일해서 `run-clang-tidy -fix -checks="-*,modernize-use-nodiscard"`로 일괄 자동 수정 가능성 높음. 다만 수가 워낙 많아 적용 후 빌드 전체 재확인 필수.

### D-23(가칭). `const` 선언 누락 — 헤더 (128건)
**체크**: `misc-const-correctness`
E-1(기존 `.cc` 파일 대상 100+건)과 동일 성격, 헤더 파일 몫이 새로 추가됨. 동일하게 "의도적 non-const"가 섞여있을 수 있어 일괄 적용 전 검토 필요(기존 E-1 문서의 검토표 그대로 적용 가능).

### D-24(가칭). Narrowing Conversion — 헤더 (90건)
**체크**: `bugprone-narrowing-conversions`
B-1과 동일 패턴. `viewport.h`, `asset_impl.h`, `bvh.h`, `component_factory.h` 등에 분산.

### D-25(가칭). 네이밍 컨벤션 — 헤더 (63건)
**체크**: `readability-identifier-naming`
C-5(7건, `.cc` 기준)와 동일 성격. `actor.h`의 `last_error_`, `actor_exporter.h`의 private 메서드 케이스 등.

### D-26(가칭). Rule of Five 미준수 — 헤더 전반 (40건)
**체크**: `cppcoreguidelines-special-member-functions`
C-2(3건 + 추가 3건)에서 다룬 것과 동일 패턴이 헤더 전반에 훨씬 많이 존재. `body.h`, `cone_joint.h`(joint 계열 전반 의심), `controls.h`, `curve.h`, `distance_joint.h`, `extrude_geometry.h`, `first_person_controls.h`, `fixed_joint.h` 등. Joint/Body 계열 클래스가 자원을 소유하는 구조라면(C-2의 `VehicleData` 사례처럼) 실질 위험 있는 것과 단순 스타일인 것을 구분하는 검토 필요.

### D-27(가칭). 부호있는 정수 비트연산 — 헤더 (26건)
**체크**: `hicpp-signed-bitwise`
A-8과 동일 패턴. `components/joint_component.h` 등.

---

## 4. 개별 검토 필요 (나머지, 소량)

| 체크 | 건수 | 비고 |
|------|------|------|
| `bugprone-easily-swappable-parameters` | 19 | C-1과 동일 패턴, 헤더 함수 시그니처 |
| `performance-enum-size` | 17 | D-11과 동일 패턴 |
| `modernize-use-override` | 14 | D-8과 동일 패턴 |
| `modernize-use-emplace` | 13 | D-2와 동일 패턴 |
| `performance-unnecessary-value-param` | 6 | D-10과 동일 패턴 |
| `google-readability-casting` | 6 | B-6과 동일 패턴 |
| `cppcoreguidelines-avoid-c-arrays` | 5 | F-4와 동일 패턴 (대부분 NOLINT 대상일 가능성) |
| `hicpp-multiway-paths-covered` | 4 | switch문 커버리지 |
| `bugprone-switch-missing-default-case` | 4 | A-12와 동일 패턴 |
| `cppcoreguidelines-pro-type-reinterpret-cast` | 3 | B-3과 동일 패턴, NOLINT 대상일 가능성 |
| `readability-simplify-boolean-expr` | 2 | D-5/D-12와 동일 패턴 |
| `performance-move-const-arg` | 2 | 개별 확인 필요 |
| `misc-no-recursion` | 2 | A-6/A-13과 동일 패턴 — 반복문 전환 검토 |
| `cppcoreguidelines-virtual-class-destructor` | 2 | C-6과 동일 패턴 |
| `modernize-use-equals-default` | 1 | D-3/D-6과 동일 패턴 |
| `google-readability-namespace-comments` | 1 | 개별 확인 |
| `google-explicit-constructor` | 1 | 개별 확인 |
| `google-build-namespaces` | 1 | 개별 확인 |
| `cppcoreguidelines-pro-bounds-array-to-pointer-decay` | 1 | F-2와 동일 패턴 |

---

## 5. 본 리포트 병합 시 반영 사항 (체크리스트)

```
[x] .clang-tidy HeaderFilterRegex 버그 — 본 리포트 6장 D-22 앞 배경 설명 + 2장 요약 blockquote에 정정 사항 반영 완료
[x] "v6/v7/v8 유저 코드 경고 0건" 표현 정정 — "(.cc 파일 기준)" 명시 완료 (본 리포트 2장 blockquote, 11장 v9 원시 결과 항목)
[x] A-16~A-19(가칭) — 잠재 버그 6건 전부 1차 검토 완료. 실버그 2건(구 A-18/A-19) → 코드 수정 + 본 리포트 A-16/A-17로 병합 완료. 구 A-16(예외탈출 3건)은 D-26에 통합 완료, 구 A-17(use-after-move)은 오탐 결론 → F-9로 신규 등록 완료
[x] D-22~D-27(가칭) — 대량 카테고리 6종 전부 D-22~D-27로 D등급에 편입, 코드 수정 + 재검증(v10~v14) 완료
[x] 4장 개별 항목들 — D-28로 통합해 19종 100건 전부 코드 수정(자동수정/실제수정/NOLINT) + 재검증 완료. 기존 대응 항목(C-1, D-11, D-8, B-3, C-6, F-2, F-4, A-12, D-5, A-6 등)과 동일 방침 적용, 본 리포트 D-28 절에 교차 참조 명시
[ ] Linux 고유 2,475건과의 차이(642건) 원인 분석 — LLVM 19 vs 21 체크 차이 정밀 비교 (08번 문서 6장 방법론 활용) — 미착수, 필요 시 별도 진행
[x] cppcheck_result_v8.txt는 이번 건과 무관 — cppcheck는 HeaderFilterRegex 영향 안 받음, 재스캔 불필요 (기존 결과 유효, 변동 없음)
```

---

## 6. 관련 문서

- `260702_황인성_clangtidy_cppcheck_verification_report.md` — 병합 대상 본 리포트
- [08-multiplatform-verification-plan.md](08-multiplatform-verification-plan.md) — 이 버그를 발견하게 된 멀티플랫폼 검증 작업
- 원시 결과: `C:\working\grapi-base\clangtidy_v9.txt` (Windows, 수정된 HeaderFilterRegex 적용 후 첫 스캔)
- 원시 결과: `\\wsl.localhost\Ubuntu\home\insung52\grapi-base\clangtidy_linux-clang_v1.txt` (Linux, 비교 참고용)
