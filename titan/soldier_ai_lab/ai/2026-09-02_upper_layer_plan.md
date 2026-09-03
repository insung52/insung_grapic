# 상위 층(L0~L3) 구조 계획 — 명령 · 분대 · 판단 · 실행

2026-09-02 / 계획(설계 심화 대기) / 애니메이션 층 위에 얹히는 4개 층의 책임 경계·계층 간 계약·소속 판정 규칙·GASP가 이미 제공하는 StateTree 기반 조사·구현 순서. `../animation/2026-09-02_pose_pipeline_spec.md`의 상위 문서.

> **폴더 규칙·진행 상황·미해결 항목**: `../CLAUDE.md` · `../CURRENT_STATE.md` · `../OPEN_ITEMS.md`
>
> **이 문서의 목적**: 애니메이션 층에서 "결정/수렴/자율"과 "8개 카테고리"로 새 항목의 자리를
> 미리 만들어둔 것과 **같은 일을 상위 층에 대해 하는 것.** 새 전술·새 행동이 필요해질 때
> "어느 층이 소유하는가"가 규칙으로 정해지게 한다.
>
> 신뢰도 표기는 포즈 명세와 동일: **[A] 확정 / [B] 잠정 / [C] 미측정**

---

## 1. 층 구조와 이 문서의 범위

```
【L0 COMMAND】 상위 지휘 — 시나리오/지휘부가 내리는 고수준 명령
【L1 SQUAD  】 분대 조율 — 자원 배분(슬롯·회랑·토큰), 사기, 정보 공유
【L2 BRAIN  】 개인 판단 — 유틸리티 스코어러가 Intent 하나를 선택
【L3 ACT    】 실행      — StateTree가 Intent를 태스크 시퀀스로 수행
─────────────────────────────────────────────────────────
 L4 MOTION   → ../animation/2026-09-02_pose_pipeline_spec.md (별도 문서)
```

---

## 2. 소속 판정 규칙 [A]

애니메이션 층의 "결정/수렴/자율"에 대응하는, **상위 층의 판정 규칙**이다.

### 2.1 제1규칙 — 정보 범위

> **"이 결정을 내리려면 무엇을 알아야 하는가?"**

| 알아야 하는 것 | 소속 |
|---|---|
| 전장 전체 상황, 시나리오 의도 | **L0** |
| 다른 분대원의 상태·위치·역할 | **L1** |
| 자기 인지 + 분대가 준 배정 + 자기 몸 상태 | **L2** |
| 이미 정해진 의도의 수행 단계와 즉시 환경 | **L3** |

**예시 판정**

| 항목 | 필요한 정보 | 소속 |
|---|---|---|
| "측면기동을 할까" | 다른 분대원이 제압사격을 유지할 수 있는가 | **L1** — 혼자 측면을 도는 건 자살 |
| "지금 엄폐할까 쏠까" | 내 노출도, 내 탄약, 내가 본 표적 | **L2** |
| "어느 엄폐물로 갈까" | 공간 질의 결과 + 분대 회랑 제약 | **L2가 요청, EQS가 답** |
| "엄폐물에 어떻게 진입할까" | 슬롯의 접점 트랜스폼 | **L3** |
| "누가 제압사격을 맡을까" | 분대 전체의 탄약·위치 | **L1** (토큰 배분) |
| "재장전할까" | 내 잔탄, 내 안전도 | **L2** |

### 2.2 제2규칙 — 아래 층에 "제약"을 주지 "명령"을 주지 않는다 [A]

Killzone 2/3의 회랑(corridor) 개념. 각 층은 아래 층의 **선택지를 좁힐 뿐 선택하지 않는다.**

```
L0 → L1 :  "저 구역을 확보하라, ROE는 자유, 공세적으로"     (목표 + 제약)
L1 → L2 :  "너는 엄호조, 이 영역 안에서, 제압 토큰 보유"     (역할 + 영역 + 자원)
L2 → L3 :  "엄폐한다, 목표 슬롯은 이것"                      (의도 + 파라미터)
L3 → L4 :  FSoldierPoseIntent                                (의미, 숫자가 아님)
```

**위반 예시**: L1이 "3번 병사는 좌표 (x,y)로 가서 2초 후 3발 쏴라"고 하면 그건 명령이 아니라
원격 조종이고, 개인이 로봇이 된다. 이것이 현행 `titan_example`의 상태다.

### 2.3 제3규칙 — 모든 층은 "왜 그랬는지" 답할 수 있어야 한다 [A]

유틸리티 AI의 가장 큰 실패 모드는 "왜 저 행동을 골랐는지 아무도 모른다"이다.

```
각 층은 자신의 결정과 그 근거를 구조화된 형태로 남긴다.
   L2 : Intent별 점수와 각 축의 기여도
   L1 : 선택한 플랜과 그 조건, 토큰 배분 현황
   L0 : 발행한 명령과 상태 보고
```

**이것은 디버그 기능이 아니라 층의 필수 출력이다.** 설계 문서 3.7절이 `Debug/`를 1급 시민으로
둔 이유.

---

## 3. GASP가 이미 제공하는 L3 기반 — 조사 결과 [A]

**중요한 발견: GASP 5.8은 애니메이션 샘플이면서 동시에 StateTree AI 샘플이다.**

### 3.1 AI 컨트롤러

```
AIC_NPC_SmartObject  (부모: AIController)
   EventBeginPlay → Delay(2s) → StartLogic(StateTreeAIComponent)
```
전체 코드가 이게 전부다. **모든 행동이 StateTree에 있다.**

### 3.2 제공되는 StateTree 태스크 라이브러리

| 에셋 | 역할 | 우리에게 |
|---|---|---|
| **`STT_SetCharacterInputState`** | 캐릭터의 `inputState`(gait/stance/aim 의도)를 설정 | **AI→애니메이션 다리 그 자체.** 포즈 명세 3.4절이 말한 통합 지점 |
| **`STT_FocusToTarget`** / `STT_ClearFocus` | AIController 포커스 설정/해제 | **컨트롤 로테이션 → `aimingRotation` → 조준 체인 구동** |
| `STT_FindRandomLocation` | 순찰 목적지 탐색 | 우리는 EQS 기반 전술 질의로 대체 |
| `STT_FindSlotTransforms` | 슬롯 접점 트랜스폼 계산 | **엄폐 슬롯 진입에 그대로 사용 가능** |
| `STT_CharacterIgnoreCollisionsWithOtherActor` | 상호작용 중 충돌 무시 | 엄폐물 진입 시 필요 |
| **`STT_FindSmartObject`** | Smart Object 탐색 | **엄폐 슬롯 탐색의 원형** |
| **`STT_ClaimSlot`** | **슬롯 예약** | **설계 문서 10.3절 "중복 선점 방지"가 이미 구현돼 있다** |
| `STT_UseSmartObject` / `STT_ClearHandle` | 사용/해제 | 진입·이탈 |
| `STT_PlayAnimFromBestCost` | **포즈 검색 비용으로 애니메이션 선택 후 재생** | 엄폐 진입 동작을 현재 포즈에 맞게 고르는 데 사용 |
| `STT_PlayAnimMontage` | 몽타주 재생 | 재장전·수신호 |
| `STC_CheckCooldown` / `STT_AddCooldown` | 쿨다운 조건/설정 | 재시도 제한 |
| `STE_GetAIData` | AI 데이터 공급 Evaluator | 우리 blackboard 접근 패턴의 원형 |

내장 태스크로 `StateTreeMoveToTask`, `StateTreeDelayTask`가 쓰인다.

### 3.3 판정

**L3 실행 층은 밑바닥부터 만들지 않는다.** GASP의 태스크 라이브러리를 승계하고 전술 태스크만
추가한다. 특히 **엄폐 시스템의 핵심(SmartObject 탐색 → 예약 → 접점 계산 → 진입 애니메이션)이
이미 동작하는 형태로 존재한다.**

> 이는 애니메이션 층에서 내린 "GASP 승계" 판단과 같은 결론이며, 근거도 같다 —
> 삽입 지점이 이미 설계돼 있다.

---

## 4. L3 ACT — 실행 층

| 항목 | 내용 |
|---|---|
| **구현** | StateTree (5.8 정식). Intent 하나당 서브트리 하나 |
| **틱** | 매 틱 ~30Hz |
| **입력** | L2가 선택한 `IntentTag` + 파라미터 |
| **출력** | `FSoldierPoseIntent` (포즈 명세 3.2절) |

### 4.1 서브트리 구성 [B]

```
ST_Soldier_Root
 ├ ST_Intent_TakeCover        슬롯 질의 → 예약 → 이동 → 진입 → 자세
 ├ ST_Intent_AimedFire        조준 → 수렴 대기 → 버스트 → 평가
 ├ ST_Intent_SuppressiveFire  구역 조준 → 지속 사격 → 탄약 관리
 ├ ST_Intent_Reposition       슬롯 질의 → 예약 → 이탈 → 이동 → 진입
 ├ ST_Intent_Advance          회랑 내 전진 (엄호 확인)
 ├ ST_Intent_Retreat          이탈 → 엄호 교대 → 후퇴
 ├ ST_Intent_Reload           엄폐 확인 → 몽타주 → 복귀
 ├ ST_Intent_PeekCheck        노출 최소화 자세 → 확인 → 복귀
 ├ ST_Intent_Regroup          집결점 이동
 └ ST_Intent_Idle/Overwatch   경계 슬롯 유지 + 시선 스캔
```

### 4.2 태스크 어휘 — 승계 + 신규 [B]

| 승계 (GASP) | 신규 (우리) |
|---|---|
| `SetCharacterInputState` | `STT_SetPostureTarget` (자세 높이/긴급도) |
| `FocusToTarget` / `ClearFocus` | `STT_SetWeaponPosture` (Lowered/LowReady/ADS/Blind) |
| `FindSmartObject` / `ClaimSlot` / `UseSmartObject` | `STT_QueryTacticalSlot` (EQS 전술 질의) |
| `FindSlotTransforms` | `STT_AimAtTarget` (조준 목표 + 수렴 대기) |
| `PlayAnimFromBestCost` | `STT_FireBurst` (버스트 길이 = 상황) |
| `PlayAnimMontage` | `STT_RequestBodyRealign` (재정렬, 포즈 명세 6.3절) |
| `MoveTo` / `Delay` | `STT_ReleaseToken` / `STT_AcquireToken` |
| `CheckCooldown` / `AddCooldown` | `STC_HasLineOfFire` (사격선 청결) |

### 4.3 규칙 [A]

- **L3는 Intent를 스스로 바꾸지 않는다.** 실패하면 실패를 보고하고 L2가 다시 고른다.
  (예외: 5.3절 인터럽트)
- **L3는 숫자를 만들지 않는다.** `FSoldierPoseIntent`에 의미를 채우고 L4가 숫자로 바꾼다
- **모든 태스크는 중단 가능해야 한다.** 생존 계열 Intent가 언제든 끼어들 수 있다

### 4.4 열린 질문

- **[C-12]** Intent 전환 권한 규칙. `AimedFire` 도중 표적 변경은 판단(L2)인가 실행(L3)인가?
  StateTree가 스스로 Intent를 포기할 수 있는가? (설계 백로그 D6)
- **[C-13]** StateTree 서브트리 하나당 인스턴스 비용. 45명 × 10 서브트리가 감당되는가

---

## 5. L2 BRAIN — 개인 판단

| 항목 | 내용 |
|---|---|
| **구현** | 유틸리티 스코어러 (IAUS 계열, C++) |
| **틱** | 4~10Hz (거리 LOD) |
| **입력** | 인지 결과 + 분대 배정 + 자기 상태 |
| **출력** | `IntentTag` + 파라미터 |

### 5.1 왜 유틸리티인가 [A]

설계 문서 8.1~8.2절에 근거가 있다. 요지: **판단과 실행은 성질이 다르다.** "지금 엄폐할까 쏠까"는
연속적 상황 평가(유틸리티), "엄폐하러 간다"는 순차적·중단 가능한 절차(StateTree).
하나로 합치면 우선순위가 트리 구조에 하드코딩되어 현행 시스템의 문제가 재발한다.

### 5.2 스코어링 [A]

```cpp
Score = BaseWeight;
for (Consideration& C : Considerations)
    Score *= C.Evaluate(Blackboard.Get(C.InputName));   // 곱셈 — 하나라도 0이면 탈락

// 축 개수가 많을수록 불리해지는 것을 상쇄 (IAUS의 make-up value)
const float Mod = 1.f - 1.f / Considerations.Num();
Score = Score + (1.f - Score) * Mod * Score;
```

- **히스테리시스**: 현재 Intent에 +10~15% 보너스 (없으면 매 틱 진동)
- **최소 지속시간**: Intent별 0.5~2초
- **인터럽트**: `TakeCover`/`Retreat` 등 생존 계열은 최소 지속시간을 무시하고 끼어들 수 있다

### 5.3 개체차는 데이터다 [A]

같은 스코어러에 **커브 파라미터만 다르게** 주면 "겁 많은 신병 / 침착한 정예 / 공세적인 분대장"이
나온다. `FIntentDefinition`을 DataAsset으로 두고 프로파일별로 만든다.

```
Profile_Recruit   : 생존 축 가중↑, 조준 수렴 느림, 사기 하한 낮음
Profile_Veteran   : 균형, 수렴 빠름
Profile_Leader    : 공세 축↑, 사기 하한 높음
```

**이것이 "병사 하나하나가 살아있는 것처럼"의 가장 저렴한 구현이다.**

### 5.4 인지와의 공유 [A]

설계 문서 7.5절의 `Exposure`(내가 남에게 얼마나 보이는가)는 **인지 계산의 입력이면서 동시에
유틸리티 "생존" 축의 입력**이다. 같은 숫자를 두 시스템이 공유한다 — 이 설계의 경제성.

### 5.5 열린 질문

- **[C-14]** 축의 커브 파라미터 초기값. 튜닝 없이는 무의미하므로 **글래스박스 UI가 선행되어야 함**
- **[C-15]** 4~10Hz 판단 주기가 실제로 충분한가 (반응이 굼떠 보이지 않는가)

---

## 6. L1 SQUAD — 분대 조율

| 항목 | 내용 |
|---|---|
| **구현** | `USquadComponent` + `FSquadBlackboard` |
| **틱** | 2~4Hz |
| **출력** | 역할·슬롯·회랑·토큰 배분 |

### 6.1 하이브리드 — 배분만 하고 실행은 분산 [A]

- 중앙집중형: 분대장이 다 지시 → 개인이 로봇 (우리가 벗어나려는 상태)
- 완전 분산형: 다섯이 같은 엄폐물로 몰리고 아무도 엄호를 안 하고 다 같이 재장전
- **하이브리드**: 분대는 ①슬롯/역할 ②회랑(영역) ③토큰만 배분. 개인은 그 안에서 자유 판단

### 6.2 토큰 — 협동을 창발시키는 최소 장치 [A]

```
SuppressionTokens : 동시에 제압사격할 수 있는 인원 상한
MovementTokens    : 동시에 이동할 수 있는 인원 상한
```

**이동 토큰만으로 바운딩 오버워치가 창발한다** — 상한 이하로만 움직이니 나머지는 자동으로
엄호 상태가 된다. 별도 로직이 필요 없다.

### 6.3 사기(Morale) [A]

Days Gone이 분대 사기를 수치로 두고 분대 행동을 구동한 것을 채택.

```
Morale ← 초기값(명령의 공세성)
       − 사상자 × w1 − 피제압 총량 × w2 − 수적 열세 × w3
       + 적 사상 × w4 + 분대장 생존 × w5 + 아군 지원 근접 × w6
```

임계 이하 → 플랜이 `Withdraw`로, 개인의 `Retreat` 축도 함께 상승.

**이것으로 현행 시나리오의 하드코딩(`LastStandZoneIndex`)을 파라미터로 대체할 수 있다** —
"1분대는 사기 하한이 높아 후퇴하지 않는다" = 결사 항전.

### 6.4 전술 플랜 템플릿 [B]

HTN의 "메서드"에서 아이디어만 차용하되 계획기 없이 스코어 기반 선택.

| 플랜 | 조건 | 역할 배분 |
|---|---|---|
| `Hold` | 방어 명령, 적 미확인 | 전원 경계 슬롯, 부채꼴 시야 분담 |
| `BaseOfFire` | 교전 명령, 적 위치 확인, 사기 보통↑ | 전원 사격 슬롯, 제압 토큰 순환 |
| `BoundingOverwatch` | 전진 명령 + 접촉 중 | 팀 A 엄호 ↔ 팀 B 전진, 교대 |
| `Flank` | 교전 중 + 측면 경로 + 사기 높음 | 고정조(제압) + 기동조(회랑) |
| `Withdraw` | 사기 낮음 or 철수 명령 | 후위 엄호조 + 이탈조 |
| `Regroup` | 분산도 높음 | 집결점 수렴 |

### 6.5 정보 공유 [A]

개인의 `Awareness`가 `Confirmed`에 도달하면 분대 blackboard에 올린다. 다른 멤버는
`bSharedBySquad=true`, `Confidence=0.6`으로 받는다(직접 본 것보다 낮게).
→ "무전으로 들었지만 나는 아직 못 봤다"가 자연스럽게 표현되고, "직접 확인하러 간다"의 근거가 된다.

### 6.6 열린 질문

- **[C-16]** 분대 동적 생성(Days Gone 방식)을 쓸 것인가, 사전 배정을 쓸 것인가
- **[C-17]** 토큰 수 초기값과 분대 규모의 관계

---

## 7. L0 COMMAND — 명령

| 항목 | 내용 |
|---|---|
| **구현** | `FSoldierOrder` + `USoldierCommandSubsystem` |
| **틱** | 이벤트 |

### 7.1 원칙 [A]

> **명령은 "무엇을 원하는가"와 "어떤 제약 아래에서"만 말한다. "어떻게"는 절대 말하지 않는다.**

현행 `EScenarioEffectType`은 정반대다 — `BeginEnemyFleeZone2`처럼 **대상·행동·목적지가 한
덩어리로 고정**돼 있어 새 연출마다 enum과 C++ 분기가 하나씩 늘어난다.

### 7.2 스키마 [A]

설계 문서 11.2절 참고. 요지:

```
FSoldierOrder {
    Recipient   : Squad / Element / Individual / AllOfFaction
    Verb        : MoveTo / Occupy / Engage / Suppress / Advance /
                  Withdraw / HoldFire / Regroup / Overwatch / Follow
    Target      : Location / Actor / Zone / Direction
    Constraints : ROE, Aggression, MoraleFloor, Formation,
                  CorridorId, StandoffDistance, bAllowFlanking
    Priority / ExpiresAfterSec / SourceStepId
}
```

**동사 × 대상 × 제약의 조합으로 표현이 폭발한다.** enum을 늘리는 대신.

### 7.3 역방향 — 상태 보고 [A]

상위가 명령만 내리고 결과를 모르면 시나리오를 못 짠다.

```
FOrderStatusReport { OrderId, Status(Received/InProgress/Achieved/Failed/Aborted),
                     Progress, Casualties, SquadMorale, SquadCentroid, ConfirmedEnemyCount }
```

이게 있으면 시나리오 트리거를 `EnemyCasualtyCountAtLeast` 같은 저수준 카운터 대신
**`OrderStatus(1분대, Occupy Zone1) == Achieved`처럼 의미 단위**로 쓸 수 있다.

### 7.4 titan_example 접속 [A]

기존 `FScenarioStepRow`에 **이펙트 타입 하나만 추가**한다:
```
EScenarioEffectType::IssueOrder  +  FSoldierOrder (또는 Order DataTable RowName)
```
기존 28개 effect enum은 그대로 두고(하위호환), 새 연출부터 `IssueOrder`로 저작한다.
트리거 쪽은 손대지 않는다.

---

## 8. 계층 간 계약 요약 [A]

```cpp
L0 → L1   FSoldierOrder            // 목표 + 제약
L1 → L2   FSquadAssignment         // 역할 + 슬롯 + 회랑 + 토큰
L2 → L3   FIntentSelection         // IntentTag + 파라미터 + 선택 근거(디버그)
L3 → L4   FSoldierPoseIntent       // 의미 (포즈 명세 3.2절)

L1 → L0   FOrderStatusReport       // 진척 · 사상 · 사기
L2 → L1   FSoldierStatus           // 인지 결과 · 탄약 · 체력 · 현재 Intent
L3 → L2   FTaskResult              // 성공/실패/중단 사유
```

**각 경계는 구조체 하나다.** 새 정보가 필요하면 구조체에 필드를 추가하지, 층을 건너뛰어
직접 읽지 않는다. 이것이 이전 프로젝트의 "직접 결합이 하나씩 늘어난" 문제를 막는 장치다.

---

## 9. 데이터 저작 방식 [B]

| 데이터 | 형식 | 이유 |
|---|---|---|
| Intent 정의 (축·커브) | **DataAsset** | 에디터에서 실시간 튜닝, 프로파일별 파생 |
| 병사 프로파일 (신병/정예/분대장) | DataAsset | 위와 동일 |
| 분대 플랜 템플릿 | DataAsset | 조건과 역할 배분 |
| 명령 (시나리오) | **DataTable** | 기존 시나리오 스텝 시스템과 동형 |
| 자세 앵커 / 구간 모드 | DataAsset | 포즈 명세 6.2절 |
| EQS 질의 | EQS 에셋 | 엔진 표준 |
| 실행 트리 | StateTree | 엔진 표준 |

**원칙: 튜닝 대상은 전부 데이터. 코드에 상수를 박지 않는다.**

---

## 10. 관찰 가능성 (Debug) [A]

2.3절 규칙의 구현. **이것은 나중에 붙이는 기능이 아니라 L2 착수와 동시에 만든다.**

| 층 | 보여줄 것 |
|---|---|
| L2 | Intent별 점수 막대 + **각 축의 기여도**. 왜 이 Intent가 이겼는가 |
| L2 | 커브 파라미터 실시간 조정 UI |
| L1 | 현재 플랜, 슬롯 배정도, 토큰 보유 현황, 사기 게이지 |
| L1 | 회랑 영역 시각화 |
| L0 | 활성 명령 목록 + 상태 보고 |
| 인지 | 각 병사의 `Awareness` 값, 마지막 목격 위치, `Exposure` |
| 엄폐 | EQS 후보 슬롯의 점수 히트맵 |
| L4 | 총구 궤적 (교란이 실제로 오차를 만드는지 — 포즈 명세 5.5절) |

---

## 11. 구현 순서와 검수 기준 [B]

애니메이션 층(P0~P1 전반)과 병행/후속.

| 단계 | 내용 | 검수 기준 |
|---|---|---|
| **A1** | 인지 모델 (설계 문서 7절) + 디버그 시각화 | 병사가 적을 "점진적으로" 인지하고, 시야를 벗어나면 서서히 잃는다 |
| **A2** | 엄폐 슬롯 생성 + EQS 질의 + SmartObject 예약 | 3명이 서로 다른 슬롯을 예약해 들어간다 (P0-3) |
| **A3** | L2 유틸리티 + 글래스박스 UI + L3 서브트리 4종 | **병사 1 vs 1이 마커 없는 임의 레벨에서 교전한다** |
| **A4** | L1 분대 (blackboard·토큰·사기·플랜 4종) | **5 vs 5가 바운딩 오버워치로 전진하고, 사기가 무너지면 교대 후퇴한다** |
| **A5** | L0 명령 + 상태 보고 | 명령 하나로 분대가 알아서 전투를 수행한다 |
| **A6** | 45명 성능 + LOD 티어 | 60fps 유지 (설계 문서 12절) |

**A3의 "글래스박스 UI 먼저"가 중요하다.** 유틸리티는 튜닝 없이는 무의미하고, 튜닝은 점수가
보여야 가능하다. UI 없이 축을 늘리면 이전 프로젝트와 같은 상태가 된다.

---

## 12. 열린 질문 [C] 목록

| # | 항목 | 시점 |
|---|---|---|
| C-12 | Intent 전환 권한 규칙 (L2/L3 경계) | A3 |
| C-13 | StateTree 인스턴스 비용 × 45명 | A6 |
| C-14 | 유틸리티 커브 초기값 (글래스박스 UI 선행) | A3 |
| C-15 | 4~10Hz 판단 주기의 체감 반응성 | A3 |
| C-16 | 분대 동적 생성 vs 사전 배정 | A4 |
| C-17 | 토큰 수 ↔ 분대 규모 | A4 |
| C-18 | 아군/적군 단일 코드 원칙이 실제로 유지되는가 (설계 3.7.1절) | A3 |
| C-19 | 서버 권위 게이트가 모든 L0~L3 진입점에 적용됐는가 (설계 4.3절) | A5 |

---

## 13. 추가 조사가 필요한 것

| # | 항목 | 결과 |
|---|---|---|
| ~~R1~~ | ~~StateTree 서브트리 구성이 가능한가~~ | **✅ 가능.** 아래 13.1 |
| ~~R2~~ | ~~EQS로 SmartObject 슬롯을 뽑는 방법~~ | **✅ 방향 확인.** 아래 13.2 |
| R3 | `STT_PlayAnimFromBestCost`의 동작 | 엄폐 진입 동작을 현재 포즈에 맞게 고르는 데 쓸 수 있는지 |
| R4 | `STE_GetAIData` Evaluator 패턴 | 분대 blackboard 접근 방식의 원형으로 쓸 수 있는지 |
| R5 | GASP `ST_NPC_SandboxCharacter_SmartObject`의 실제 상태 구성 | **MCP로 조회 불가**(StateTree 에셋이 프로퍼티를 노출하지 않음). 에디터에서 수동 확인 |

### 13.1 R1 해결 — StateTree 서브트리 구성 가능 [A]

UE 5.4부터 **StateTree 에셋 안에서 다른 StateTree 에셋을 링크**할 수 있다. 상태 타입에
`State / Group / Linked / LinkedAsset / Subtree`가 있다.

→ **4.1절의 "Intent 하나당 서브트리 하나" 구성이 그대로 가능하다.** 각 Intent 서브트리를 별도
에셋으로 만들고 루트에서 `LinkedAsset`으로 참조한다.

**추가로 중요한 성질**: 서브트리 내부의 `Tree Succeeded` / `Tree Failed` 전환은 **링크한 상태까지만
전파되고 그 위로는 안 간다**(단, 링크가 아니라 전환으로 진입한 경우엔 트리 전체에 영향).

→ 4.3절의 규칙 "L3는 실패를 보고하고 L2가 다시 고른다"가 **엔진 기능으로 자연스럽게 표현된다.**
Intent 서브트리가 실패하면 링크 지점까지만 올라오고, 거기서 L2에게 결과를 넘기면 된다.

### 13.2 R2 해결 — 마찰은 질의가 아니라 예약이다 [B]

조사 결과, **EQS로 SmartObject를 찾는 것 자체는 문제가 아니다.** 커스텀 Generator는
`EnvQueryGenerator_BlueprintBase` 상속(BP) 또는 C++로 만들 수 있고, C++ 쪽이 성능이 낫다
(45명 규모면 C++로 간다).

실제 마찰 지점은 **"EQS로 찾은 슬롯을 실제로 예약(claim)하는 것"** 이다 — 커뮤니티에서
반복 보고되는 문제다.

**그런데 GASP에 이미 답이 있다**: `STT_FindSmartObject` → **`STT_ClaimSlot`** → `STT_UseSmartObject`
→ `STT_ClearHandle` 흐름이 동작하는 형태로 존재한다(3.2절). 우리는 **탐색 부분만 EQS 기반
전술 질의로 교체**하고 예약 이후는 승계하면 된다.

```
[GASP 원본]  STT_FindSmartObject (근접/타입 기준)  → ClaimSlot → Use → Clear
[우리]       STT_QueryTacticalSlot (EQS 스코어링)  → ClaimSlot → Use → Clear
                     ↑ 여기만 교체                     ↑ 이하 승계
```

설계 문서 10절의 3층 구조(생성 / 평가 / 점유)에서 **점유 층이 이미 확보돼 있다는 뜻이다.**

---

## 14. R5 해결 — GASP StateTree 실제 구조 (2026-09-03) [A]

StateTree 툴셋 플러그인을 활성화한 뒤 MCP로 직접 읽었다.

### 14.1 `ST_NPC_SandboxCharacter_SmartObject`

```
Root
 └ Smart Object State                            [OnStateCompleted → Patrol State]
    ├ UsingSmartObj          cond: STC_CooldownEntranceCheck
    │   └ FindSmartObject    tasks: STT_SetCharacterInputState, STT_FindSmartObject
    │       └ ClaimSlot      tasks: STT_ClaimSlot
    │           └ UseSmartObject   tasks: STT_UseSmartObject
    └ Patrol State                               [OnStateCompleted → Smart Object State]
        └ Patrol                                 [OnStateCompleted → Smart Object State]
```

### 14.2 `ST_NPC_SandboxCharacter_Patrol_Subtree`

```
FindRandomLocation   tasks: STT_SetCharacterInputState, STT_FindRandomLocation
 ├ MoveToRandomLocation   tasks: StateTreeMoveToTask   [OnStateCompleted → FindRandomLocation]
 └ Wait                   tasks: StateTreeDelayTask    [OnStateSucceeded → None]
```

### 14.3 ★ 핵심 관찰 — 자원 점유를 "중첩 상태"로 표현한다

SmartObject 사용이 **순차 실행이 아니라 부모-자식 중첩**으로 되어 있다.

```
FindSmartObject   ← 부모. 찾은 오브젝트를 보유
  └ ClaimSlot     ← 자식. 예약을 보유
      └ UseSmartObject  ← 자식. 실제 사용
```

StateTree에서 **자식 상태로 들어가도 부모의 태스크는 계속 실행 중**이다. 즉 부모가 자원(찾은
오브젝트 / 예약된 슬롯)을 붙잡고 있고, 자식이 다음 단계를 수행한다. **상태를 빠져나가면 부모의
태스크가 정리(예약 해제)를 수행한다.**

**우리 엄폐 시스템의 정확한 원형이다:**

```
QueryTacticalSlot     ← 부모. EQS 질의 결과 보유
  └ ClaimSlot         ← 자식. SmartObject 예약 보유
      └ OccupyCover   ← 자식. 자세 유지·사격
```

그리고 이것이 **포즈 명세 6.5.3절의 "사망 시 SmartObject 예약 해제"를 자동으로 해결한다** —
병사가 죽어 상태 트리를 벗어나면 부모 상태의 종료 처리가 예약을 푼다. 우리가 사망 정리
체크리스트에서 가장 위험하다고 표시한 항목이 **구조로 해결된다.**

> 단, 이 이점은 **자원을 부모 상태가 보유하도록 구성했을 때만** 얻어진다. 태스크를 한 상태에
> 나열하는 방식으로 짜면 이 성질이 사라진다. **L3 서브트리 작성 규칙으로 못박는다.**

### 14.4 최상위 구성 — 두 모드 교대

```
Smart Object State  ⟷  Patrol State      (OnStateCompleted로 서로 전환)
```

우리 병사는 이 자리에 **Intent별 LinkedAsset 서브트리**가 들어간다(4.1절). 구조는 같고 항목만
늘어난다.

### 14.5 상위층 계획에 반영

| 항목 | 반영 |
|---|---|
| 4.1 서브트리 구성 | 유효함이 확인됨. `LinkedAsset` + 중첩 상태 패턴 |
| 4.2 태스크 어휘 | `STT_SetCharacterInputState`가 **모든 상태의 첫 태스크**로 쓰인다 — gait/stance 의도를 상태 진입 시 설정하는 패턴. 우리도 동일하게 간다 |
| **신규 규칙** | **자원(슬롯 예약·토큰)은 그것을 보유하는 상태가 부모여야 한다.** 해제를 상태 종료에 위임 |
