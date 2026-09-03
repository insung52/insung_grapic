# soldier_ai_lab — 세션 공통 규칙

**이 폴더에서 작업하는 모든 세션은 이 문서를 먼저 읽는다.** 상위 `../CLAUDE.md`의 규칙을
따르되, 이 프로젝트 고유의 규칙을 아래에 추가한다(2026-09-03 도입).

---

## 0. 이 폴더가 무엇인가

`titan_example`과 **별개의 언리얼 프로젝트**(`C:\working\works\kadex\anim_test\SoldierLab`,
UE5.8, GASP 기반)에서 진행하는 고사실감 병사 AI/애니메이션 R&D의 문서 저장소.

코드는 다른 프로젝트에 있지만 문서는 titan 문서 체계 안에 둔다(`genesis/`와 동일 패턴).

**최종 목표**: 병사 개개인이 환경·적·아군을 실시간으로 판단해 엄폐/사격/기동하고 분대로
협동하는 시스템. 상위 시나리오는 고수준 "명령"만 내린다.

---

## 1. 시작 지점 — 무엇부터 읽을 것인가

| 상황 | 읽을 것 |
|---|---|
| **처음 오는 세션** | `README.md` → `CURRENT_STATE.md` → 작업할 영역의 폴더 문서 |
| 지금 뭘 해야 하나 | `CURRENT_STATE.md` |
| 미해결 항목이 뭐가 있나 | `OPEN_ITEMS.md` |
| 전체 설계가 궁금 | `design/2026-09-01_architecture.md` |
| 애니메이션 작업 | `animation/` 두 문서 **둘 다** |
| AI/분대 작업 | `ai/2026-09-02_upper_layer_plan.md` |
| 에셋/리깅/디자인팀 | `assets/2026-09-02_asset_supply_and_collaboration.md` |

---

## 2. 폴더 구조

| 폴더 | 담는 것 |
|---|---|
| **(최상위)** | 메타 문서만 — `README` / `CURRENT_STATE` / `OPEN_ITEMS` / `CLAUDE`. **내용 문서를 최상위에 두지 말 것** |
| `design/` | 전체 시스템 설계 — 층 구조, 계층 간 계약, 성능/스케일, 채택·미채택 결정 |
| `animation/` | **L4 모션** — 포즈 파이프라인 명세, GASP ABP 분석, 리그/커브/워핑 |
| `ai/` | **L2 판단 · L3 실행** — 인지, 유틸리티, StateTree |
| `squad/` | **L0 명령 · L1 분대** — 분대 조율, 사기, 토큰, 명령 스키마 *(내용이 생기면 `ai/`에서 분리)* |
| `assets/` | 자산 조달, 스켈레톤/리깅, 디자인팀 협업 |
| `prototypes/` | P0/P1 실험 기록 — 무엇을 시도했고 결과가 무엇이었나. **`prototypes/TEMPLATE.md`를 복사해서 쓸 것**(이 파일만 날짜 규칙 예외) |
| `tools/` | MCP 스크립트, 애니메이션 모디파이어, 베이크 툴 *(생기면 신설)* |

**맞는 폴더가 없으면 신설하고 이 표에 추가한다.** 스테이징 폴더는 두지 않는다.

---

## 3. 문서 작성 규칙

상위 `../CLAUDE.md`와 동일:

1. 파일명 `YYYY-MM-DD_짧은-주제.md`
2. 문서 맨 위 1줄 헤더: `날짜 / 상태 / 한줄요약`
3. 폴더는 위 2절 표에서 고른다

### 3.1 ★ 신뢰도 표기 — 이 프로젝트 고유 규칙

**모든 설계·분석 항목에 신뢰도를 붙인다.**

| 표기 | 뜻 |
|---|---|
| **[A] 확정** | 근거를 확인했다(에셋 실측·엔진 소스·공식 문서). 바뀌면 구조가 바뀐다 |
| **[B] 잠정** | 합리적이나 실측 전. 바뀔 수 있다 |
| **[C] 미측정** | 지금은 모른다. **측정 항목과 판정 기준만** 적는다 |

**왜 필요한가**: 이 프로젝트 초기에 "확인하지 않은 것을 세밀하게 쓴" 항목이 **네 번 틀렸다** —
상하체 분리 / 워핑이 8방향을 줄여준다 / IK는 항상 마지막 / 워핑이 실험 경로에만 있다.
넷 다 재료를 직접 만진 뒤에 바로잡혔다. **세밀하게 쓰는 게 문제가 아니라 확인하지 않은 것을
세밀하게 쓰는 게 문제다.**

**[C]가 줄어드는 것이 곧 진척도다.**

### 3.2 추정과 사실을 섞지 않는다

에셋/코드를 직접 읽어 확인한 것과 이름·패턴으로 추론한 것을 **문장 안에서 구분**한다.
추론에는 **(추정)** 을 붙인다. 나중에 뒤집히면 정정 절을 추가하되 **원래 서술을 지우지 말고
취소선으로 남긴다** — 왜 그렇게 판단했는지가 다음 세션에 필요하다.

### 3.3 정정은 문서 끝에 절을 추가한다

본문을 통째로 고쳐쓰면 판단의 이력이 사라진다. 본문에는 `→ 정정: N절 참고`만 달고,
문서 끝에 정정 절을 붙인다. (예: `animation/2026-09-02_gasp_abp_analysis.md`의 14~16절)

---

## 4. 미해결 항목 관리

**모든 미해결 항목은 ID를 갖고 `OPEN_ITEMS.md`에 등록된다.**

| 접두 | 뜻 | 어디서 |
|---|---|---|
| `C-n` | 측정해야 아는 것 (실험 필요) | 각 명세의 [C] 항목 |
| `D-n` | 설계 백로그 (해당 단계에서 채움) | design 문서 |
| `Q-n` | 사용자 결정 필요 | design 문서 |
| `R-n` | 추가 조사 필요 | 각 문서 |
| `U-n` | GASP 미확인 항목 | animation 분석 문서 |
| `W-n` | 분석에서 파생된 작업 | animation 분석 문서 |

- **새 항목을 만들면 `OPEN_ITEMS.md`에 반드시 등록한다.** ID는 전역으로 유일해야 한다
- **해결되면 원 문서에 결과를 쓰고 `OPEN_ITEMS.md`에서 해결 표시**한다. 지우지 않는다

---

## 5. 작업 원칙 (설계 결정에서 파생된 것)

이건 문서 규칙이 아니라 **구현할 때 지켜야 하는 규칙**이다. 어겼을 때 되돌리기 어렵다.

| # | 원칙 | 근거 |
|---|---|---|
| P1 | **GASP ABP를 복제해서 확장한다. 애님 그래프를 새로 짜지 않는다** | MM은 부분적 정확성이 부분적 품질을 주지 않는다. `animation/..._pose_pipeline_spec.md` 8.1절 |
| P2 | **원본 GASP 캐릭터를 지우지 않는다** — 같은 레벨에서 A/B 비교 기준으로 유지 | 위와 동일 |
| P3 | **L4는 `FSoldierPoseIntent`와 월드 말고 아무것도 읽지 않는다** | 액터 변수 직접 참조가 `titan_example` 버그의 근원 |
| P4 | **아군/적군은 코드 한 벌.** 진영은 데이터 | 현행이 두 벌이라 같은 버그를 두 번 고쳤다 |
| P5 | **모든 L0~L3 Tick 진입점에 `HasAuthority()` 게이트** | `titan_example`은 리슨서버 멀티플레이 |
| P6 | **튜닝 대상은 전부 데이터**(DataAsset/DataTable). 코드에 상수를 박지 않는다 | |
| P7 | **디버그 표시는 1급 시민.** 축을 구현하기 전에 HUD 골격부터 | 값이 안 보이면 튜닝이 불가능 |
| P8 | **반입 클립은 커브 3종 필수** — `contact_l/r`, `Enable_Warping`, (선택)`Disable_AO` | 없으면 발 IK·워핑이 조용히 오작동 |

---

## 6. 언리얼 작업 환경

| 항목 | 값 |
|---|---|
| 프로젝트 | `C:\working\works\kadex\anim_test\SoldierLab` (UE5.8, GASP 기반) |
| MCP 포트 | **8001** (`titan_example`이 8000을 쓰므로 분리) |
| `.mcp.json` | `anim_test/` 와 `anim_test/SoldierLab/` 양쪽에 있음 |
| MCP 사전 조건 | Project Settings → Model Context Protocol → **Auto Start Server 켜기** (프로젝트별 설정) |
| 유용한 툴셋 | `editor_toolset.*`, `state_tree_toolset.*`, `animation_toolset.*`, `ProgrammaticToolset`(배치 실행) |

### 6.1 MCP로 **접근이 안 되는 것** (에디터에서 수동 확인 필요)

- 애님 스테이트머신 내부 그래프
- **BlendStack 내부 그래프**(`AnimationBlendStackGraph`) — MM 노드 더블클릭으로 열림
- 노드의 프로퍼티 **바인딩** 대상
- Chooser 테이블의 **Result 컬럼**
- StateTree의 `get_node_description` (구조는 읽히나 설명은 실패)

### 6.2 GASP 콘솔 변수

```
DDCvar.DrawCharacterDebugShapes 1        디버그 도형 (궤적·접지)
DDCVar.LocomotionSetupCMC <int>          로코모션 경로 전환 ★ 실제 스위치
DDCvar.MMDatabaseLOD 0|1|2               데이터 밀도 티어
a.animnode.offsetrootbone.enable 0|1     ⚠ 끄면 조준/발이 깨진다 (규약 문제)
DDCVar.ThreadSafeAnimationUpdate.Enable  45명 규모에서 필수
DDCVar.ExperimentalStateMachine.Enable   ❌ 덮어써져서 효과 없음
```

---

## 7. 새 환경(다른 PC)에서 시작하기

> 2026-09-03 추가. 프로젝트가 Perforce(P4V)로 관리되며, 작업 PC가 바뀔 수 있다.
> **아래 순서를 건너뛰면 에디터가 안 열리거나 MCP가 안 붙는다.**

### 7.1 순서

```
1. P4에서 SoldierLab 워크스페이스 동기화
2. ★ C++ 빌드          ← Binaries/ 가 P4에서 제외돼 있으므로 필수
3. 에디터 최초 실행     ← 셰이더 컴파일 + DDC 빌드로 오래 걸림 (에셋 5.5GB)
4. MCP Auto Start Server 켜기   ← 프로젝트별 설정이라 PC마다 다시 켜야 함
5. Claude Code 재시작 → /mcp 로 연결 확인
6. 플러그인 활성화 확인 (7.3)
7. PIE 동작 확인 → CURRENT_STATE.md 읽고 작업 시작
```

### 7.2 ★ 가장 흔한 함정 — C++ 빌드를 안 하고 여는 것

`.p4ignore`가 `Binaries/`·`Intermediate/`를 제외하므로, **동기화 직후에는 컴파일된 모듈이
없다.** 그냥 `.uproject`를 더블클릭하면 "모듈이 없습니다. 다시 빌드하시겠습니까?"가 뜨거나
실패한다.

```
1) SoldierLab.uproject 우클릭 → Generate Visual Studio project files
2) 생성된 .sln 열어서 Development Editor / Win64 로 빌드
3) 그 다음에 에디터 실행
```

### 7.3 플러그인 확인 — `.uproject`가 진실이다

플러그인 활성화는 `SoldierLab.uproject`에 기록되고 P4로 추적되므로 **동기화하면 따라온다.**
다만 아래는 아직 켜지지 않았을 수 있으니 확인할 것(2026-09-03 기준 미확인):

```
SmartObjects, GameplayBehaviorSmartObjects, StateTree, GameplayStateTree,
FullBodyIK, NavCorridor, AnimationModifierLibrary,
AnimationBudgetAllocator, SignificanceManager, AnimationSharing,
GameplayInsights(=Animation Insights, Rewind Debugger)
```

**⚠ 이름에 `UAF`가 붙은 것은 켜지 말 것** — 차세대 프레임워크(AnimNext)용 별도 모듈이고
우리는 기존 Animation Blueprint 경로를 쓴다. `UAF Chooser` / `UAF Pose Search` 등이 검색에
같이 나오니 주의.

### 7.4 MCP 재설정

`.mcp.json`(포트 8001)은 P4로 추적되므로 따라온다. **하지만 언리얼 쪽 서버는 프로젝트별
사용자 설정이라 PC마다 다시 켜야 한다:**

```
Project Settings → Model Context Protocol → Auto Start Server  체크
(포트 8001 확인 → 에디터 재시작)
```

붙었는지 확인: Claude Code에서 `/mcp`, 또는 레벨 액터 조회를 한 번 시켜볼 것.

### 7.5 경로에 대하여

문서에 나오는 절대경로는 **최초 작업 PC 기준의 참고값**이다. 새 환경에서는 다를 수 있다.

| 항목 | 최초 PC 경로 | 새 환경 |
|---|---|---|
| UE 프로젝트 | `C:\working\works\kadex\anim_test\SoldierLab` | P4 워크스페이스 위치에 따름 |
| 엔진 | `C:\Program Files\Epic Games\UE_5.8` | 설치 위치에 따름 |
| 문서(이 폴더) | `C:\working\insung_grapic\titan\soldier_ai_lab` | 문서 저장소 위치에 따름 |
| `titan_example` | `C:\working\works\kadex\titan_example` | **없을 수도 있다** — 참조용이며 필수 아님 |

`../../ai_combat/` 같은 상위 참조는 **titan 문서 저장소가 함께 있을 때만** 열린다. 없어도
soldier_ai_lab 문서만으로 작업할 수 있게 써 두었다.

### 7.6 첫 세션 체크리스트

- [ ] C++ 빌드 성공, 에디터 열림
- [ ] `Content/Levels/DefaultLevel` PIE — 캐릭터 조작 정상
- [ ] `Content/Levels/NPCLevel` PIE — AI NPC 3기가 순찰·벤치 상호작용
- [ ] MCP 연결 (`/mcp`)
- [ ] `DDCvar.DrawCharacterDebugShapes 1` 동작
- [ ] `CURRENT_STATE.md` 4절의 "다음 작업" 확인
