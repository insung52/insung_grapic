# 적군이 드론을 쏘는 문제 — 최후순위 표적 도입

2026-09-02 / 완료 / 적군 표적 선정을 2단(Preferred/Fallback)에서 3단으로 확장, 드론은 다른 표적이 하나도 없을 때만 선택.

## 증상

적군 보병이 공중의 드론을 표적으로 잡고 사격함. 현실적으로 틀린 건 아니지만, 눈앞의
보병·UGV를 놔두고 하늘을 쏘고 있으면 연출이 이상함(사용자 리포트).

## 원인

`UEnemyCombatComponent::PickTargetFromOverlaps`는 `UDetectableTargetSubsystem` 레지스트리에서
**`Faction == Friendly`인 모든 대상**을 후보로 담는다. `ADronePawn`은 생성자에서
`DetectableTarget->Faction = Friendly`로 등록되므로 보병·UGV·트럭과 **완전히 동등한 후보**가 된다.

거리순 정렬 후 상위 `TargetCandidatePoolSize`명 중 무작위로 뽑기 때문에, 드론이 가까이 있으면
정상적으로 자주 뽑힌다 — 버그가 아니라 설계대로 동작한 결과.

## 수정 — 3단 우선순위

기존 구조는 2단이었다:

- `Preferred` — `TargetPreference`(Infantry/Vehicle/SpecificActor)에 맞는 후보
- `Fallback` — 유효한 모든 후보. `Preferred`가 비었을 때만 사용

여기에 **`LastResort`** 를 추가:

```cpp
TArray<TPair<float, AActor*>>& Candidates =
    Preferred.Num() > 0 ? Preferred : (Fallback.Num() > 0 ? Fallback : LastResort);
```

`LastResort`에 담기는 조건은 새 프로퍼티:

```cpp
// DetectableTargetComponent.h
UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Detection")
bool bLowPriorityForEnemyTargeting = false;
```

이 값이 켜진 대상은 **선호도 판정과 `Fallback` 양쪽에서 빠지고** `LastResort`에만 담긴다.
따라서 사거리 안에 다른 유효 표적이 하나라도 있으면 **절대 안 뽑힌다.**

완전히 표적에서 제외하지 않은 이유: 주변에 아무도 없는데도 드론을 무시하고 멍하니 있으면
그것대로 부자연스럽기 때문(같은 파일의 LOS 폴백이 "전부 막혀 있으면 최근접으로라도 쏜다"를
택한 것과 같은 판단).

### 적용 대상

| 클래스 | 값 | 비고 |
|---|---|---|
| `ADronePawn` | `true` | 생성자에서 설정 |
| `AUAVPawn` | `true` | ADronePawn으로 대체됐지만 레벨 잔존 대비 |
| UGV / 트럭 / 아군 보병 | `false`(기본) | 변경 없음 |

C++ 생성자 기본값이라 BP나 레벨 인스턴스에서 따로 켤 필요 없음. 다른 액터를 최후순위로
돌리고 싶으면 그 액터의 `DetectableTargetComponent`에서 체크박스만 켜면 된다.

### 구현 주의

`UDetectableTargetComponent` 조회를 **항상** 하도록 바꿨다. 예전엔 `bIsInfantry`가 false일 때만
찾았는데(유효성 판정에만 썼으므로), 이제 최후순위 판정에도 필요하다.

## 영향 범위

**적군 보병의 표적 선정에만** 영향을 준다. RCWS/드론 카메라의 탐지
(`UTargetDetectionComponent` — 바운딩 박스 오버레이, 아군 자동조준)와는 무관하다. 드론은
여전히 화면에 정상적으로 탐지 표시된다.

## 적용

C++ 변경이라 **리빌드 필요**. BP/레벨 값 변경 없음.
