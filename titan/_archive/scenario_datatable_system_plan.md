> [보관됨 2026-08-31] 최신 버전: `scenario_implementation_status.md`(그 자체도 보관됨, 최신은
> `level_new_kadex_0811/scenario_three_stage_combat.md`). 사유: 여기 제안한 `FScenarioStepRow`/
> `EScenarioTriggerType`/`EScenarioEffectType` 스키마가 `/Game/Scenario/DT_ScenarioSteps`로
> 실제 구현됨(`scenario_implementation_status.md` §2).

# 시나리오 DataTable 시스템 — 설계안 (2026-07-30, 착수 전 정리)

> `시나리오.md` 12절에서 이미 "시퀀서 대신 DataTable, `UScenarioStateSubsystem`을
> 확장해서 읽게 하자"고 결론까지 나 있었는데, 실제 구현은 아직 시작 안 함 —
> 지금까지는 타이밍 값들을 그냥 각 C++ 클래스에 `UPROPERTY(EditAnywhere)`로
> 흩어서 하드코딩해왔음(작동은 함, 근데 한곳에 모여있지 않고 재컴파일 없이
> "시나리오 자체"를 재구성하긴 어려움). 이 문서는 **아직 구현 시작 전** —
> 합의되면 별도로 진행.
>
> **전제**: `시나리오.md`는 "이번 라운드로 질문이 전부 해결됨, 확정 상태"라고
> 적혀 있지만, 사용자가 "시나리오가 아직 확정은 아니다"라고 다시 확인함 —
> 그래서 이 설계는 지금 문서에 있는 8단계(#4-1~#4-8)에 딱 맞춰 하드코딩하지
> 않고, 트리거 종류/파라미터가 최대한 유동적이게 잡음.

---

## 1. `시나리오.md` 대비 구현 현황 갭 분석

| 단계 | 내용 | 현재 상태 |
|---|---|---|
| #4-1 | 침투 상황 보고, UI 메시지 7초 깜빡임 | `BeginEnemyContactScenario()`만 있음(EnemyCube 태그 위치 저장). **UI 메시지는 시나리오.md 자체에도 "미구현 확인됨"으로 적혀있고, 아직도 미구현.** |
| #4-2 | UAV 이륙 + 좌표까지 비행 | 이번 세션 범위 밖 — `AUAVPawn::BeginMissionToTarget` 등 기존 코드 있는지만 확인됨, 이 시나리오 단계와 실제로 연결되어 있는지는 미확인. |
| #4-3 | 적 낙하 식별, UAV 줌 연출 | 이번 세션 범위 밖. |
| #4-4 | UGV 이동명령 + 아군 동반기동 | **거의 구현됨** — FormingUp→Following, RVO+NavMesh 회피, 충돌 방지까지. 단, "UGV 최대속도를 액셀/브레이크로 실제 제한"(기어 제한만으론 내리막 가속 못 막음)은 **미구현**(예전에 논의만 되고 보류됨). |
| #4-5 | UGV 20m 진입 → 아군 매복 전환 + 분대장 산개 수신호 | **트리거가 스펙과 다름.** 시나리오.md는 "UGV가 목표 지점 **20m 반경 진입**"이 트리거인데, 지금 구현은 "UGV가 **완전히 멈춤**(`IsMoving()==false`)"이 트리거임 — 20m 시점(아직 주행 중)이 아니라 정지 후. 또, 시나리오.md엔 이 단계에 수신호가 **하나**(산개)뿐인데, 지금은 우리가 "정지 수신호 → 2초 대기 → 산개 수신호" 2단계로 확장해서 구현함(스펙에 없던 추가). UGV의 "10m 이내 완전 정지"와 "20m 진입 트리거"가 스펙상 서로 다른 두 반경인데 지금은 구분 안 하고 있음. |
| #4-6 | UGV RCWS 적 포착 → 아군 완전 엄폐 + 사격 참여, 분대장 엄폐 수신호 | 브로드캐스트 인프라(`BeginAllyAmbush`/`TakeCoverSignalMontage`)는 있음. **RCWS 실제 탐지 결과(`DetectedTargets` non-empty)에 연결되어 자동 트리거되는지는 미확인** — 지금까지는 콘솔 명령으로 수동 트리거만 검증함. |
| #4-7 | UGV 위협사격, 10명 사망/5명 도주(웨이포인트) | 이번 세션 범위 밖, 구현 여부 미확인. |
| #4-8 | 자체방호 RCWS 전환, 최종 섬멸, 종료+자동재시작 | 이번 세션 범위 밖. |

**핵심 요지**: #4-4는 사실상 다 됐고, #4-5/#4-6은 "인프라는 있는데 트리거 방식이 스펙과 어긋나거나 실제 이벤트에 안 물려있을 수 있음", #4-1/#4-2/#4-3/#4-7/#4-8은 이번 세션에서 손 안 댐(구현 여부 자체를 다시 확인해야 함).

---

## 2. 원칙 — "시나리오 흐름" vs "동작 튜닝값" 분리

DataTable에 다 넣지 말고 성격이 다른 두 종류를 구분하는 걸 제안:

- **시나리오 흐름(DataTable로)**: "언제 무슨 일이 일어나는가" — 트리거 조건, 트리거
  파라미터(거리/이름 등), 스텝 간 대기시간, 어떤 효과를 발동하는가. `시나리오.md`
  11절에서 이미 "스텝별 대기시간 커스텀", "스텝별 자동진행 on/off"를 요구했었음 —
  전부 이 테이블 컬럼으로 자연스럽게 커버됨.
- **동작 튜닝값(각 클래스/컴포넌트에 그대로)**: "그 동작이 물리적으로 어떻게
  보이는가" — 예: 스톱사인 팔을 얼마나 빨리 들고 내리는지(ABP 내부 값), RVO 회피
  반경, 아군 밀어내기 힘, NavMesh 안정화 시간 등. 이런 건 시나리오 진행과 무관하게
  "그 액터가 어떻게 움직이는가"의 문제라 `시나리오.md` 12-1절에서 매복 지점을
  DataTable 대신 마커 액터로 남긴 것과 같은 이유로 컴포넌트 프로퍼티에 남겨두는
  게 맞다고 봄.

**→ 이번에 물어봤던 스톱사인 속도값은 후자(동작 튜닝값)로 분류 — DataTable이 아니라
ABP에 `EditDefaultsOnly` 변수로 노출하는 걸 권장.** DataTable에는 "정지 수신호가
언제 시작되고 얼마나 기다렸다 다음 단계로 넘어가는지"(스텝 전환 타이밍)만 들어감.

---

## 3. DataTable 스키마 제안

```cpp
UENUM(BlueprintType)
enum class EScenarioTriggerType : uint8
{
    Manual,             // 콘솔/코드에서 직접 StartStep 호출
    AfterPreviousStep,  // 이전 스텝 발동 후 TriggerDelaySeconds 뒤 자동 시작
    DistanceThreshold,  // TriggerActorA/B 사이 거리 <= TriggerDistance
    ActorStopped,       // TriggerActorA의 "정지" 감지(UGV IsMoving()==false 패턴 재사용)
    EnemyDetected,       // TargetDetectionComponent 탐지 결과 non-empty
};

UENUM(BlueprintType)
enum class EScenarioEffectType : uint8
{
    None,
    BroadcastAllyState,   // Following/Approaching/Ambush 등 브로드캐스트
    SquadSignal,          // 분대장 수신호(몽타주 또는 스톱사인류 bool 세팅)
    ShowUIMessage,
    SetUGVDestination,
    // 앞으로 #4-1/2/3/7/8 구현하면서 필요한 만큼 계속 추가
};

USTRUCT(BlueprintType)
struct FScenarioStepRow : public FTableRowBase
{
    FName StepId;                 // 예: "4-5_Approach"
    FText DebugLabel;             // 에디터에서 알아보기 쉬운 이름

    EScenarioTriggerType TriggerType;
    float TriggerDelaySeconds = 0.f;       // AfterPreviousStep용
    float TriggerDistanceThreshold = 0.f;  // DistanceThreshold용
    FName TriggerParamA;                   // 범용 참조(액터 태그 등)
    FName TriggerParamB;

    EScenarioEffectType EffectType;
    float EffectFloatParam = 0.f;
    FName EffectNameParam;
    FText EffectTextParam;                 // UI 메시지 등

    bool bAutoAdvanceEnabled = true;       // 이 스텝 자동진행 on/off(11절 요구사항)
};
```

`UScenarioStateSubsystem`이 이 테이블을 순서대로(또는 `StepId` 체이닝으로) 읽어서
각 스텝의 트리거 조건을 평가하다가 만족하면 `EffectType`에 맞는 핸들러 함수를
호출하는 구조로 확장. 지금 있는 `BeginAllyFormUp`/`BeginAllyFollowing`/
`BeginAllyApproach`/`BeginAllyAmbush` 같은 함수들은 그대로 "효과 핸들러"로 재사용
가능 — 지우고 새로 짜는 게 아니라 **호출하는 주체만 바뀜**(지금은 콘솔 커맨드가
직접 부르는데, 나중엔 DataTable을 순회하는 매니저 루프가 부름).

**한계 솔직히 말하면**: 완전히 새로운 종류의 효과(#4-2 UAV 비행, #4-7 도주
웨이포인트 등)는 결국 `EScenarioEffectType`에 케이스 추가 + 핸들러 함수 작성이
필요해서 그 자체는 재컴파일이 필요함 — DataTable이 없애주는 건 "이미 있는 스텝의
타이밍/순서/on-off를 조정하는 것"이지, "완전히 새로운 트리거/효과 종류를 코드
없이 만드는 것"까지는 아님. `시나리오.md` 12절도 원래 이 정도 기대치였다고 이해함.

---

## 4. 현재 하드코딩된 값 중 DataTable로 옮길 후보

| 값 | 현재 위치 | 옮길지 여부 |
|---|---|---|
| `HaltToApproachDelaySeconds`(2초) | `ScenarioStateSubsystem` | **이동** — "정지 수신호 후 대기시간"은 순수 스텝 전환 타이밍 |
| `FormUpAdvanceDelaySeconds`(2초) | 〃 | **이동** — 마찬가지로 스텝 전환 타이밍 |
| `SquadSignalFallbackSeconds`(1.5초) | 〃 | **이동 후보** — 다만 "수신호 몽타주 길이가 없을 때 폴백"이라는 성격이 살짝 다름, 논의 필요 |
| `NavObstacleSettleSeconds`/`FormUpStaggerSeconds`/`UGVArrivalPollIntervalSeconds` | 〃 | **유지** — 이건 시나리오 흐름이 아니라 "NavMesh/폴링이 안정적으로 동작하기 위한" 엔지니어링 튜닝값 |
| `DriftGraceSeconds`/`AllyPushStrength` | `AllyFormationComponent` | **유지** — 동작 튜닝값 |
| 스톱사인 팔 속도(+3.0/-5.0)/클램프 범위 | ABP `ComputeStopsignAlpha` | **유지, 대신 ABP EditDefaultsOnly 변수로 노출**(이번 질문의 실제 답) |
| UGV #4-5 트리거 반경(20m)/정지 반경(10m) | 현재 코드엔 아예 없음(정지 감지로 대체됨) | **신규로 DataTable 컬럼화** — 스펙대로 다시 맞추려면 이게 필요 |

---

## 5. 미확정 — 합의 필요

- [ ] #4-5 트리거를 스펙대로 "20m 진입"(주행 중)으로 되돌릴지, 지금 방식("완전
  정지" 감지 + 정지 수신호 2단계)을 유지할지 — 후자가 사용자 요청으로 이번에
  새로 만든 거라 의도적인 변경일 수도 있음, 확인 필요.
- [ ] #4-6(RCWS 적 포착) 트리거가 실제 `TargetDetectionComponent` 이벤트에
  연결되어 있는지 라이브 확인 필요 — 안 되어 있으면 DataTable 작업과 별개로
  먼저 고쳐야 할 수도 있음.
- [ ] DataTable 스텝을 "순서대로 진행"(선형)으로 할지, 각 스텝이 독립적으로
  자기 트리거만 감시하다 발동하는 "병행 가능"(시나리오.md 3절 "#4-3은 계속
  진행형으로 남아있다가 자연스럽게 #4-4와 병행" 같은 케이스) 구조로 할지 —
  후자가 스펙에 더 맞음, 스키마에 `bRunsInParallel` 같은 플래그가 필요할 수 있음.
  - [ ] `EScenarioEffectType`/`EScenarioTriggerType`을 지금 열거값 정도로 시작할지,
  아니면 #4-1/2/3/7/8까지 미리 다 설계해두고 시작할지(범위가 커짐) — 이번 라운드는
  #4-4~#4-6만 우선 옮기고 나머지는 그때그때 늘리는 걸 권장.
