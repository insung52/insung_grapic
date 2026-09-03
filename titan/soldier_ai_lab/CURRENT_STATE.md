# 현재 상태 — soldier_ai_lab

2026-09-03 / 설계 완료 · P0 착수 직전 (P4 이관 · PC 이동 예정) / GASP 구조 분석과 애니메이션 층 명세가 끝났고, 반입 파이프라인 검증(P0-4)이 다음 작업.

---

## 1. 한 줄 요약

**설계와 조사는 끝났다. 이제 "GASP 클립을 우리 것으로 만들 수 있는가"를 검증할 차례다.**

---

## 2. 프로젝트 현황

| 항목 | 상태 |
|---|---|
| UE 프로젝트 | ✅ 생성 완료 (UE5.8, GASP 기반, C++ 전환됨) |
| **소스컨트롤** | ✅ **Perforce(P4V)로 확정.** `.p4ignore` 작성 완료 (프로젝트 루트) |
| 플러그인 | ⚠️ GASP 기본 + StateTree 툴셋. **AI 계열(SmartObjects·NavCorridor·FullBodyIK 등) 미확인** → `CLAUDE.md` 7.3절 |
| GASP 동작 | ✅ PIE 확인 — 관성 이동·정지·제자리회전·벤치 상호작용 전부 자연스러움 |
| MCP | 포트 8001. **PC를 옮기면 Auto Start Server를 다시 켜야 함** → `CLAUDE.md` 7.4절 |

> **다른 PC에서 처음 시작한다면 `CLAUDE.md` 7절을 먼저 볼 것.**
> 특히 `Binaries/`가 P4에서 제외돼 있어 **C++ 빌드를 먼저 해야 에디터가 열린다.**

---

## 3. 이번 세션(2026-09-01~03)에 확정된 것

### 3.1 P0-1은 사실상 통과했다

**궤적이 플레이어 입력이 아니라 캐릭터 이동 상태에서 생성된다.**
`PoseSearchGenerateTrajectory(forCharacter)`가 캐릭터를 통째로 받는 엔진 함수라, AI가 CMC를
구동하면 동일 경로로 궤적이 나온다. 설계에서 "최대 리스크"로 잡았던 `USoldierTrajectorySource`
자체 구현이 **불필요**하다.

AI가 손댈 것은 정확히 2개: `PreviousDesiredControllerYaw`(위협 방향) + `TrajectoryGenerationData`
재튜닝.

### 3.2 워핑이 무엇을 커버하는지 확정 — 조달 계획이 정밀해졌다

Epic이 GASP 그래프에 남긴 주석으로 확정:

| 카테고리 | Orientation Warping | 결론 |
|---|---|---|
| **정상상태 루프**(직선 이동) | ✅ 커버 — "전진 보행 하나로 여러 각도 스트레이프" | 견착 루프는 **전방 위주 소수 클립으로 충분** |
| **start / stop / pivot / turn** | ❌ 구조적으로 못 함 (직선 구간에서만 동작) | **데이터 필수 — 여기가 진짜 비용** |

### 3.3 반입 클립 필수 커브 3종

```
contact_l / contact_r   발 심기 타이밍     없으면 발 IK 오작동
Enable_Warping          워핑 허용 구간     없으면 방향 커버 0
Disable_AO (선택)       조준 억제 구간
```

**이게 디자인팀 요청 스펙의 핵심 항목이 된다.**

### 3.4 조달 요청의 성격이 바뀌었다

> ~~"라이플 견착 로코모션 클립 수백 개"~~
> → **"라이플 견착 정지 포즈 42개 + 무기 자세 앵커 3개 + 전환 클립 소수"**

조준 공간 전체가 **7 yaw × 3 pitch × 2 자세 = 42 정지 포즈**로 정의된다(로코모션 1,450개의 3%).
정지 포즈는 루트모션도 접지 커브도 필요 없어 **제작 난이도가 완전히 다르다.**

### 3.5 GASP는 AI 샘플이기도 하다

`STT_FindSmartObject → STT_ClaimSlot → STT_UseSmartObject` 흐름이 **중첩 상태**로 구현돼 있다.
부모 상태가 자원을 보유하므로 **상태를 벗어나면 예약이 자동 해제**된다 — 설계에서 "사망 시
가장 위험한 항목"으로 표시했던 SmartObject 예약 누수가 **구조로 해결**된다.

---

## 4. 다음 작업 — 우선순위 순

### ① P0-4 · 반입 파이프라인 검증 (1일) ★ 최우선

**이제 모든 것의 전제가 됐다.** 커브 3종을 만들 수 있는지가 조달 계획 전체를 좌우한다.

- [ ] Mixamo 라이플 견착 walk 클립 1개 다운로드(인플레이스)
- [ ] IK Retargeter → UE5 Manny (골반/힙 배치 확인)
- [ ] `UEncodeRootBoneModifier` → 루트모션 합성
- [ ] `UMotionExtractorModifier` → `contact_l`/`contact_r` 생성
- [ ] **`Enable_Warping` 커브 생성 방법 확립** ← 미검증 영역. 루트 `RotationSpeed` 기반 유력
- [ ] Root Motion 활성화 → PSD 편입 → MM으로 재생

**판정**: 발 미끄러짐 없이 재생되고, 워핑이 실제로 켜지는가

### ② P0-0 잔여 셋업 (반나절)

- [ ] 플러그인 활성화 확인 — SmartObjects, GameplayBehaviorSmartObjects, FullBodyIK,
      NavCorridor, AnimationBudgetAllocator, SignificanceManager, AnimationSharing,
      **AnimationModifierLibrary**, GameplayInsights
- [ ] 프로젝트 설정 — NavMesh Dynamic, EQS 프레임 예산 3ms, Cover 트레이스 채널
- [ ] P4 워크스페이스 등록 + `p4 set P4IGNORE=.p4ignore` 후 초기 제출
- [ ] Rewind Debugger / Pose Search Debugger 켜서 동작 확인

### ③ P0-1 · AI가 MM 구동 (2~3일)

궤적 문제가 해결됐으므로 **배선 작업**이다.
- [ ] GASP 캐릭터에 AIController 부착, `inputState`를 AI가 채우도록 교체
- [ ] `SetFocus`/컨트롤 로테이션으로 조준 구동
- [ ] `PreviousDesiredControllerYaw` 공급
- [ ] 급선회 품질 확인 → `TrajectoryGenerationData` 재튜닝 **[C-1]**
  - ⚠️ Epic이 Steering 노드를 "작업 중, 원치 않는 거동 있음"으로 표기 — 첫 번째 의심 대상

### ④ P0-2 재정의 · 견착 이동 품질 (2일)

"워핑 각도 한계"가 아니라 **"전환 데이터 없이 견착 이동이 얼마나 버티는가"** 로 바뀌었다.
- [ ] 소총 메시를 `ik_hand_gun`에 부착, 임시 견착 포즈
- [ ] 루프는 워핑으로 커버되는지 확인
- [ ] **전환(출발/정지/급선회)에서 얼마나 무너지는지 측정** ← 이게 조달 규모를 정한다

### ⑤ P0-3 · 엄폐 슬롯 루프 (1~2일)

GASP의 `FindSmartObject → ClaimSlot → UseSmartObject` 중첩 패턴을 그대로 쓰고 **탐색만 EQS로 교체**.

---

## 5. 막혀 있는 것 / 결정 대기

| # | 항목 | 상태 |
|---|---|---|
| ~~Q4~~ | ~~소스컨트롤~~ | ✅ **Perforce(P4V) 확정** (2026-09-03) |
| Q8 | 캐릭터 메시 (기존 리스킨 / 신규 / MetaHuman) | P1 후반으로 미룸 |
| Q10 | 견착 전환 동작 조달 방안 (A/B/C안) | P0-2 결과 후 |
| Q7 | 디자인팀 공지 시점 | P0 완료 후 비교 영상과 함께 |

---

## 6. 협업 상태

- 디자인팀은 현재 **기존 22종 시퀀스 정리 + 기존 스켈레톤 스킨 웨이팅 수정** 중
- 그 작업은 **낭비가 아니다** — `titan_example` 현재 빌드의 품질을 올리는 작업
- 리그 교체 제안은 **한 번 보류된 상태**. P0 검증 + 비교 영상을 만든 뒤 재제안
- 타임박스: **1주**. 안 되면 접고 현행 유지 (`assets/...` 11절)

---

## 7. 리스크

| 리스크 | 완화 |
|---|---|
| `Enable_Warping` 커브를 자동 생성 못 하면 방향 커버가 0 | P0-4에서 최우선 검증 |
| 견착 전환 데이터를 못 구하면 이동 품질이 무너짐 | 복수 DB 반환을 이용한 **점진적 폴백**(총내림 클립 혼합) — `animation/..._gasp_abp_analysis.md` 15.3절 |
| 리그 교체가 무산될 수 있음 | **설계 7~12절(AI 시스템)은 스켈레톤과 무관** — 전체의 75%가 생존 |
| Steering 노드가 실험적 | P0-1에서 급선회 품질 관찰 시 첫 의심 대상 |
