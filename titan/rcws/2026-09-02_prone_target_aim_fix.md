# 엎드린 적을 못 맞히는 문제 — 조준점을 캡슐 중심에서 실제 몸으로

2026-09-02 / 완료 / 조준점이 캡슐 중심(GetActorLocation)이라 엎드려도 서 있는 높이를 겨누던 것을, 스켈레탈 메시 바운드 중심 기준으로 교체.

## 증상

RCWS가 누워 있는(엎드린) 적을 제대로 조준하지 못하고, **서 있는 것 기준으로 계속 사격**함
(사용자 리포트). 탄이 몸 위로 지나감.

## 원인

두 사실이 겹친다.

**1. 조준점이 캡슐 중심이었다.** 조준 관련 코드가 전부 `Target->GetActorLocation()`을 썼는데,
`ACharacter`에서 이 값은 **캡슐 컴포넌트의 중심**이다.

**2. 엎드림이 애니메이션 전용이다.** `UEnemyCombatComponent::ApplyCombatPose`는 BP의 bool
프로퍼티만 바꾼다:

```cpp
case EEnemyBodyPose::Prone:
    ECC_SetBoolPropertyByName(Owner, FName("IsProne"), true);
```

C++ 어디에도 캡슐을 줄이는 코드가 없다(`SetCapsuleSize` 호출 없음). 즉 **메시만 눕고 캡슐은
선 채로 남는다.**

결과: 엎드린 적의 실제 몸통은 지면 근처인데 `GetActorLocation()`은 서 있을 때의 가슴 높이를
그대로 반환 → 조준·탄도 계산이 전부 그 높이를 향함 → 탄이 넘어감.

## 수정

### 조준점 헬퍼 신설

```cpp
FVector URCWSFireControlComponent::GetTargetAimWorldLocation(const AActor* Target) const
```

우선순위:

1. `AimTargetBoneName`이 지정돼 있고 그 뼈가 실제로 있으면 → 그 소켓 위치
2. 스켈레탈 메시가 있으면 → **`Mesh->Bounds.Origin`** (월드 바운드 중심)
3. 둘 다 없으면 → 예전대로 `GetActorLocation()`

**캡슐은 일부러 안 섞는다.** 합집합으로 잡으면 선 채로 남아 있는 캡슐이 조준점을 다시 위로
끌어올려서, 고치려는 문제가 그대로 재현된다.

바운드 중심은 애니메이션 포즈를 따라가므로 엎드리면 같이 낮아지고, 서 있을 때는 예전 캡슐
중심과 거의 같은 가슴 높이라 **기존 동작에 회귀가 없다.**

### 신설 프로퍼티

```cpp
UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Fire Control|Auto-Aim")
FName AimTargetBoneName = NAME_None;   // 비우면 바운드 중심
```

바운드 중심의 정밀도가 부족하면(물리 애셋 바디 배치에 따라 조금 뜰 수 있음) 여기에
`spine_03`이나 `pelvis`를 넣어 특정 부위를 직접 겨누게 할 수 있다. 그 뼈가 없는 대상에서는
조용히 바운드 중심으로 폴백하므로 차량 등에 넣어도 안전하다.

### 교체한 지점 3곳

조준·탄도·UI가 서로 어긋나지 않도록 **전부** 같은 헬퍼를 거치게 했다.

| 위치 | 용도 |
|---|---|
| `UpdateAutoAim` (~541) | 카메라 조준 방향 + 정렬 오차(`CameraAzimuth/ElevationErrorDegrees`) |
| `UpdateMuzzleBallisticAim` (~575) | 총구 탄도 목표점(`MuzzleAimTargetWorldLocation`) |
| `UpdateAimPointForUI` (~902) | 조준점 마커 + 표시 거리 |

`SelectNearestEnemyTarget`의 거리 비교(~409)는 **바꾸지 않았다** — 그건 "누구를 고를까"용
거리라 캡슐 중심으로 충분하고, 매 프레임 후보 전원에 대해 도는 경로라 굳이 비싸게 만들 이유가 없다.

## ⚠️ 중요 정정 — 피격 판정은 캡슐이 아니라 **메시**다

이 프로젝트의 적군은 흔한 예상과 반대로 세팅돼 있다(2026-09-02 실측, `BP_Enemy_kadex`):

| 컴포넌트 | 오브젝트 타입 | 탄환(`WorldDynamic`) 응답 |
|---|---|---|
| `CollisionCylinder` (캡슐) | Pawn, QueryAndPhysics | **ECR_Ignore** — 탄환이 그냥 통과 |
| `CharacterMesh0` (메시) | Pawn, QueryOnly | **ECR_Block** — 탄환이 여기 맞음 |

`ARCWSProjectile`의 오브젝트 타입이 `ECC_WorldDynamic`인데, **캡슐은 그 채널을 명시적으로
Ignore**, **메시는 명시적으로 Block**으로 설정해 놨다. 부위별 피격과 히트리액션 본
(`TriggerHitReactionPhysics(HitBoneName)`)이 성립하려면 이래야 하므로 의도된 세팅이다.

또한 **캡슐과 메시 둘 다 `Visibility = Ignore`** 라 시야 차폐에도 안 쓰인다.
→ **캡슐이 실제로 담당하는 건 이동과 내비게이션뿐이다.**

이 사실이 위 수정의 의미를 바꾼다: 예전 캡슐 중심 조준은 단순히 "높이 겨눈" 게 아니라
**피격 형상이 아예 없는 지점을 겨누고 있었다.** 엎드린 적에게 탄이 안 맞던 진짜 메커니즘이
이것이고, 메시 바운드 중심으로 옮긴 이번 수정은 조준점을 **실제 피격 형상과 일치**시킨 것이다.

## 해결됨 — 탐지 박스에서 캡슐 제외 (2026-09-02)

`UTargetDetectionComponent::CalculateVisualBoundsLocalSpace`는 **콜리전이 켜진 모든 프리미티브의
합집합**으로 박스를 만든다. 캡슐이 선 채로 남아 있으므로 엎드린 적의 화면 바운딩 박스가
서 있는 높이로 나왔다.

### 코드 수정 없이 해결 — `NoBounds` 태그

이 함수에는 **이미 per-component 제외 장치가 있다**:

```cpp
const FName BoundsExcludedTag(TEXT("NoBounds"));
...
if (Primitive->ComponentHasTag(BoundsExcludedTag)) continue;
```

그래서 적군의 `CollisionCylinder`에 **Component Tag `NoBounds`만 추가**하면 끝난다.
C++ 수정도 리빌드도 필요 없고, 액터별로 켜고 끌 수 있어 차량 등 다른 대상엔 영향이 없다.

### 왜 안전한가

`CalculateVisualBoundsLocalSpace`의 소비처는 **딱 3개뿐**이다:

1. 화면 바운딩 박스(UV) → WBP 오버레이
2. 크기 게이트(`MinScreenSizeFraction` / `MinScreenSizePixels`)
3. 차폐 샘플 3점의 Z 범위

**피격·사망·이동·내비게이션·물리 콜리전 어디에도 쓰이지 않는다.** 게다가 위에서 확인했듯
캡슐은 `Visibility = Ignore`라 차폐 트레이스에도 원래 안 걸린다. 캡슐을 빼면 오히려 탐지
박스가 실제 피격 형상(메시)과 일치해서 더 정합적이 된다.

### 적용 범위 (2026-09-02)

| 대상 | 적용 |
|---|---|
| `BP_Enemy_kadex` (BP CDO) | ✔ |
| 레벨의 적군 인스턴스 `BP_Enemy_kadex_C_1` ~ `_15` | ✔ 15명 전부 |
| 아군 `BP_Ally_kadex` | ✖ 미적용 — 아군 캡슐은 `Visibility = Block`으로 **일부러 켜놔서**(`AllyFormationComponent.cpp:291`) 성격이 다름. 필요하면 별도 판단 |

⚠️ BP CDO에 넣어도 **레벨 인스턴스에는 전파되지 않는다**(2026-09-01에 데인 그 함정) —
실제로 CDO만 넣었을 때 인스턴스 15명 전부 빈 배열이었다. 인스턴스에 직접 넣고 재확인했음.

### 부수 효과

엎드린 적의 화면 박스가 실제 크기로 줄어들면서, `MinScreenSizePixels` 게이트에 걸려
**엎드린 적은 더 가까워야 탐지된다.** 물리적으로 맞는 동작이다("엎드리면 잘 안 보인다").
현재 임계값이 UGV 5px / 트럭 12px라 체감 변화는 크지 않을 것.

## 적용

C++ 변경이라 **리빌드 필요**. BP/레벨 값 변경 없음.
