# RCWS 자동/수동 조준·발사 매커니즘 개발 문서 (2026-07-12 ~ 2026-07-14)

## 0. 배경 및 스펙

`memo.md` 요구사항: RCWS(트럭/UGV 공용) 기관총 스펙 — 탄약 600발, 대인 사거리 2km(적군은
일반 보병만 존재), 발사속도 분당 1200발. 필요한 것: 어느 정도 현실적인 탄도학(포물선),
안정화(2축 안정기), 목표 자동 조준. 발사 이펙트/반동은 명시적으로 범위 밖(추후 구현).

핵심 설계 결정(사용자 확정 사항):
- 안정화는 on/off 가능, 최대 보정 속도도 커스터마이즈 가능
- 표적 선정 기준: 가장 가까운 적부터
- 자동 조준 시에도 포탑이 너무 빠르게 안 돌게 레이트 제한
- 명중 판정은 실제 발사체(프로젝타일)로 — 1200rpm이라도 풀링하면 성능 문제 없음
- **자동 조준**(조준만)과 **자동 사격**(조준 정렬되면 발사까지)을 분리된 개념으로 — 나중에
  "조작 모드" 시스템으로 정식 통합됨(8절)
- 수동 조준/사격 상태에서도 화면에 조준 가이드(어디를 조준해야 명중하는지) 표시 필요 →
  `UAimPointWidget`(6절)

`UTargetDetectionComponent`(바운딩 박스 탐지, `detection_dev_guide.md`)와
`URCWSComponent`(시선/팬틸트/줌/거리계)는 이 작업에서 **수정하지 않음** — 새 컴포넌트
`URCWSFireControlComponent`가 둘을 참조만 해서 "어디를 조준하고 쏠지 결정"하는 역할을
전담. 이 관례는 프로젝트 전반의 "컴포넌트 하나 = 역할 하나, 참조는 `FComponentReference`
by-name" 패턴(`QuadCamComponent`/`TargetDetectionComponent`와 동일)을 그대로 따름.

## 1. 파일 구조

```
titan_example/Source/titan_example/Vehicles/
  RCWSFireControlComponent.h/.cpp   핵심 컴포넌트 — 안정화/자동조준/자동사격/발사/모드 전부
  RCWSProjectile.h/.cpp             풀링되는 발사체 액터 (UProjectileMovementComponent 기반)
  RCWSTypes.h                       ERCWSControlMode, FRCWSStatusData (표시용 플레인 데이터)
  RCWSComponent.h/.cpp               기존 시선/팬틸트/줌/거리계 — MaxZoomLevel 10→16,
                                      SetZoomLevel FOV 안전 클램프만 추가(8.8절), 그 외 미변경

titan_example/Source/titan_example/Detection/
  DetectableTargetComponent.h/.cpp  SetIncapacitated() 추가 (7.3절)

titan_example/Source/titan_example/UI/
  AimPointWidget.h/.cpp             조준 가이드 십자선 (6절)
  Monitor1Widget.h/.cpp             ModeText/TargetTrackingText/AimPointWidget 연동
  Monitor2Widget.h/.cpp             Monitor1Widget과 동일 로직 중복 구현 (8.4절)

titan_example/Source/titan_example/
  titan_examplePlayerController.h/.cpp   ManualFireAction/RCWSModeToggleAction/
                                          RCWSModePreviousAction/RCWSZoomIn·OutAction 입력,
                                          콘솔 명령, 오디오 리스너 UGV 고정(11.3절)
  titan_example.Build.cs                 "Niagara" 모듈 의존성 추가(11.1절 — 원래 없었음)
```

`/Game/Vehicles/UGV/`에 신규 애셋: `M_RCWSRound`(예광탄/일반탄 밝기용 머티리얼),
`NS_bullet`(사용자가 외부에서 받아온 예광탄 Niagara 시스템), `BP_RCWSProjectile`(발사체 BP,
전부 여기서 기본값 지정).

## 2. 안정화 (`ApplyStabilization`)

차체(hull)의 자체 회전(요/피치, 롤 축 없음 — 실제 2축 안정기)을 상쇄해서 시선이 월드
공간상 고정 방향을 유지하게 함. 매 틱, 이전 틱 이후 hull이 회전한 만큼을 그대로
역회전시켜 `RCWS->AddPanTiltInput(-DeltaYaw, -DeltaPitch)`로 상쇄.

`bStabilizationEnabled`가 켜져 있든 꺼져있든 **무조건 매 틱 돌아감** — 수동/자동조준
입력은 그냥 `AddPanTiltInput`으로 이 위에 얹히는 구조라, 안정화 쪽에서 "이번 틱에 다른
누가 마운트를 움직였는지" 알 필요가 없음.

```cpp
const float MaxDeltaDegrees = MaxStabilizationCorrectionRateDegPerSec * DeltaTime;
const float AppliedDeltaYaw = FMath::Clamp(RawDeltaYaw, -MaxDeltaDegrees, MaxDeltaDegrees);
// ... 부족분은 버리지 않고 LastCorrectedHullYaw/Pitch에 이월 → 다음 틱에 이어서 보정
```

실제 안정기처럼 슬루잉 속도가 유한(`MaxStabilizationCorrectionRateDegPerSec`, 기본
60도/초) — 급격한 hull 회전(급선회, 험지)은 한 틱에 다 못 따라가고, 부족분이 다음
틱들로 이월되어 점진적으로 따라잡음(즉시 손실 안 됨). 이 "레이트 제한 체이스" 패턴은
`UUGVMovementComponent::SmoothedThrottleForce`, 아래 5절 자동조준 슬루잉, 8절 자동 줌
램프에서도 반복적으로 재사용됨 — 이 프로젝트 전체의 표준 관용구.

## 3. 표적 선정 (`SelectNearestEnemyTarget`)

`TargetDetection->DetectedTargets`(이미 매 0.1초 갱신되는 바운딩박스 탐지 결과) 중
`Faction == Enemy`인 것만 대상으로, 시선 위치(`RCWS->GetSightWorldLocation()`) 기준
최단거리 하나를 고름. 자동조준(`UpdateAutoAim`)과 조준점 UI(`UpdateAimPointForUI`)가
공유해서 씀 — "지금의 그 표적"이 항상 같은 정의를 갖도록.

## 4. 탄도학

### 4.1 씬 스케일 보정

`memo.md` 스펙은 실제 세계 값(850m/s급 무기, 대인사거리 2km)인데, 이 프로젝트의 씬은
`GeoCoordinateUtils::GetDistanceScaleFactor()`(≈1.227, "씬 1cm당 실제 몇 cm인지")만큼
실제보다 작게 지어져 있음(RCWS RangeMeters/UAV 고도-속도/미니맵 축척바에 이미 쓰이던
동일한 계수). 탄속과 중력을 **둘 다 같은 비율로** 축소:

```cpp
double SceneMuzzleVelocityCmS() const  // MuzzleVelocityMps * 100 / Scale
double SceneEffectiveGravityCmS2() const  // |WorldGravityZ| * (1/Scale)
```

R(사거리)과 v(탄속)이 똑같이 축소되므로 비행시간 T=R/v는 실제와 동일하게 유지되면서,
동시에 궤적의 수직/수평 비율도 균일 축소된 씬과 시각적으로 맞아떨어짐. **투사체 자신의
`ProjectileGravityScale`만** 건드리고, 월드 전역 중력은 절대 안 건드림(UGV 물리 등
다른 시스템이 실제 중력값에 의존하기 때문).

### 4.2 사격 해법 (`SolveBallisticElevationDegrees`)

표준 탄도학 사격 해법 방정식, 저각(직사화기) 해만 사용(박격포식 고각 해는 버림):

```
tan(θ) = (v² − √(v⁴ − g(gR² + 2dv²))) / (gR)
```

판별식이 음수면(무기의 물리적 사거리 밖) 직선 시선각으로 폴백. `ComputeFiringSolution`이
이걸 감싸서 **리드(예측 사격)**까지 처리: 1차로 대상의 현재 위치로 대충 풀어서 비행시간을
추정 → 그 시간만큼 대상 속도로 미래 위치를 예측 → 그 예측 위치로 한 번 더 풀어서 최종
방위각/고각을 냄(1회 반복으로 충분히 정확, 이 사거리/탄속대에서).

## 5. 자동 조준 (`UpdateAutoAim`)

표적이 있으면: `ComputeFiringSolution`으로 리드 보정된 목표 방위각/고각을 구하고,
`MaxAutoAimSlewRateDegPerSec`(기본 45도/초)로 레이트 제한된 슬루잉(2절과 동일 패턴)으로
`AddPanTiltInput` 호출. 오차가 `AutoAimLockToleranceDegrees`(기본 1도) 이내면
`bIsLockedOn = true` — 이게 자동 사격의 게이트.

표적이 없으면: **탐색 스윕**(`UpdateSearchSweep`, 8.2절)으로 대체 — 원래는 "조준 중"이라는
별도 모드였다가, 8절에서 "자동 조준/자동 발사 모드가 표적 없을 때 취하는 폴백 동작"으로
재정의됨.

## 6. 조준점 UI (`UAimPointWidget` / `UpdateAimPointForUI`)

가장 가까운 적을 맞추려면 지금 어디를 조준해야 하는지(탄도 보정 반영) 계산해서 RCWS
시야의 스크린 UV로 변환 — **`CurrentMode`와 무관하게 항상 계산**됨(자동조준이 꺼져있어도
수동 조작자가 조준 가이드로 볼 수 있어야 하므로). `TargetDetectionComponent`의
`ProjectToScreenUV`(원래 private)를 `ProjectWorldPointToCameraUV`라는 이름의 **public
static**으로 승격해서 재사용 — 바운딩박스 투영과 완전히 동일한 뷰/투영 수학을 아임포인트
계산에도 그대로 씀.

`SAimPointMarker : SLeafWidget`가 `detection_dev_guide.md` 4절의
`SDetectionOverlay`/`LineGraphWidget`/`CompassWidget`과 동일한 "Slate 커스텀 페인트를
UWidget으로 감싸는" 패턴을 그대로 재사용. `RCWSViewImage`/`RCWSDetectionOverlay`와
정확히 같은 위치/크기로 겹쳐 배치.

## 7. 발사와 피격

### 7.1 `ARCWSProjectile` — 풀링되는 발사체

`UProjectileMovementComponent`가 실제 포물선 비행(중력 기반)을 전부 처리 — 수동 궤적
계산 불필요. 1200rpm(초당 20발) 기준 spawn/destroy는 낭비라 **풀링**
(`ProjectilePoolSize`, 기본 64개): 발사 시 숨김 해제/콜리전 켬(`LaunchFrom`), 명중 또는
`MaxFlightTimeSeconds`(5초) 초과 시 숨김+콜리전 끔+속도 0(`Deactivate`) — 실제
스폰/파괴는 세션 내내 한 번뿐.

콜리전: `"Projectile"`이라는 이름의 프로파일은 이 UE5.8 프로젝트에 **존재하지 않음**
(ThirdPersonMP 템플릿 관례를 착각한 것 — `BaseEngine.ini` grep으로 확인 후 명시적으로
직접 구성):

```cpp
CollisionComponent->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
CollisionComponent->SetCollisionObjectType(ECollisionChannel::ECC_WorldDynamic);
CollisionComponent->SetCollisionResponseToAllChannels(ECollisionResponse::ECR_Block);
CollisionComponent->SetCollisionResponseToChannel(ECollisionChannel::ECC_Visibility, ECollisionResponse::ECR_Ignore);
CollisionComponent->SetCollisionResponseToChannel(ECollisionChannel::ECC_Camera, ECollisionResponse::ECR_Ignore);
```

`MuzzleForwardOffsetCm`(기본 100cm) — 발사 지점을 시선 위치가 아니라 그 방향으로 조금
앞으로 오프셋해서 스폰. 발사체가 발사 차량 자신의 포탑/차체 메시 안에서 스폰되는 걸
방지(정확한 시선 카메라 마운트 위치에 따라 필요할 수 있음). 범용적으로 설계해서 나중에
적군 자체 사격 기믹에도 재사용 가능. `LaunchFrom` 시점에 `MoveIgnoreActors`에 발사
차량을 추가해서 자기 자신과의 즉시 충돌도 방지.

### 7.2 데미지 — 표준 엔진 데미지 파이프라인 사용

`BP_Enemy`(`/Game/Tutorial/Blueprints/Enemy/BP_Enemy`)를 MCP로 확인해보니 이미 `Event
AnyDamage`(네이티브 `AActor::TakeDamage()`/`OnTakeAnyDamage` 델리게이트) 그래프가
health 감소/사망 판정을 전부 처리하고 있었음. 처음엔 커스텀 `OnHitByProjectile` 델리게이트를
만들었다가(`BlueprintImplementableEvent`를 컴포넌트에 달았는데 소유 액터의 BP에서
오버라이드가 안 보이는 실수를 겪음 — 8.3절), 이 발견 이후 **완전히 제거**하고 표준
경로로 교체:

```cpp
UGameplayStatics::ApplyPointDamage(OtherActor, DamagePerHit, ShotDirection, Hit,
    InstigatorController, this, DamageTypeClass);
```

`BP_Enemy`의 기존 `Event AnyDamage` 그래프는 **코드 한 줄도 안 건드려도** 자동으로
반응함 — `TakeDamage()`가 표준 델리게이트를 자동으로 브로드캐스트하기 때문.

### 7.3 무력화된 대상 제외 — `SetIncapacitated`

`UDetectableTargetComponent::SetIncapacitated(true)`를 호출하면
`UDetectableTargetSubsystem`에서 자기 자신을 언레지스터(`BeginPlay`/`EndPlay`가 쓰는
것과 완전히 동일한 등록/해제 메커니즘 재사용) — 그러면 **모든** 스캐너의
`DetectedTargets`(자동조준 타겟팅 + 바운딩박스 오버레이 둘 다)에서 진짜로 사라짐. 별도
"이 타겟이 아직 유효한지" 체크 로직이 다른 곳에 하나도 필요 없음. 자동조준은 매 틱
`SelectNearestEnemyTarget()`을 다시 스캔하므로, 다음 틱에 자연스럽게 그 다음으로 가까운
대상으로 넘어감.

**사용자가 직접 해야 할 일**(그래프/노드 편집은 MCP로 불가): `BP_Enemy`에
`DetectableTargetComponent`(`Faction=Enemy`) 추가, 기존 `Event AnyDamage`의 사망 분기에
`SetIncapacitated(true)` 호출 연결.

## 8. 조작 모드 시스템 (2026-07-13)

### 8.1 배경 — 4단계 선형 모드에서 2축 독립 모드로

처음엔 `TargetTrackingText` 하나에 수동/추적/조준/자동사격 4단계를 선형으로 배치하려
했으나, 사용자가 다음과 같이 정정: **두 개의 독립된 축**으로 분리해야 함 —

1. **조작 모드** — 원격 제어(수동)/자동 조준/자동 발사. 이미 존재하던(지금까지는 껍데기
   더미였던) `ModeText`/`ERCWSControlMode`에 연동.
2. **표적 추적** — 추적 중(기본)/비활성화(감지 끄기, **나중에 구현**). `TargetTrackingText`에
   연동하되 이번 패스는 그냥 "추적 중" 고정 표시만.

즉 옛 "추적 중" 단계(무대상 시 탐색 스윕)는 별도 모드가 아니라 **자동 조준/자동 발사가
표적 없을 때 취하는 폴백 동작**으로 흡수됨(5절 참고).

### 8.2 `ERCWSControlMode` — 유일한 진짜 상태

```cpp
// RCWSTypes.h
enum class ERCWSControlMode : uint8 { Remote, AutoSurveillance, AutoAim, AutoFire };
```

(2026-07-13, 첫 구현은 3값 Remote/AutoAim/AutoFire였다가 같은 날 8.7절 사유로 `AutoSurveillance`가
Remote와 AutoAim 사이에 추가되어 4값이 됨 — 뒤에 추가하지 않고 순환/표시 순서에 맞게 중간에
끼워 넣음.)

`URCWSFireControlComponent::CurrentMode`가 유일한 진짜 상태로 승격 — 기존
`bAutoAimEnabled`/`bAutoFireEnabled` 독립 불리언 2개를 대체. 내부 게이팅은 전부
`CurrentMode` 비교: 자동조준류(슬루잉/스윕/자동줌)는 `CurrentMode != Remote`, 실제
조준/락온(표적 있을 때 슬루잉+줌인)은 `CurrentMode == AutoAim || AutoFire`만(즉
`AutoSurveillance`는 제외 — 8.7절), 자동사격은 `CurrentMode == AutoFire`.
`SetControlMode()`가 모드 전환 + 임시 상태 리셋(탐색 스윕 오프셋 0으로). 처음엔 버튼
하나로 한 방향만 순환하는 `CycleControlMode()`였다가, 사용자 요청으로 다음/이전 자유
이동이 가능하게 `CycleControlModeNext()`/`CycleControlModePrevious()` 둘로 분리(순서는
동일하게 Remote↔AutoSurveillance↔AutoAim↔AutoFire, 양방향) — 조이스틱 버튼 2개
(`RCWSModeToggleAction`=다음, `RCWSModePreviousAction`=이전)와 WBP
`CycleActiveRCWSModeNext()`/`CycleActiveRCWSModePrevious()`가 각각 호출.

`bStabilizationEnabled`는 이 모드 축과 무관하게 독립 토글 그대로 유지.

`Monitor1Widget`/`Monitor2Widget`의 `ModeText`는 `Data.ControlMode`(예전에는 항상
Remote만 나오는 더미)를 거치지 않고 **`ActiveFireControl->CurrentMode`를 직접 읽음** —
`StabilizationText`가 이미 `bStabilizationEnabled`를 직접 읽던 전례를 그대로 따름.
텍스트/색상(2026-07-13 확정): 원격 제어=흰색, 자동 감시=하늘색(`#17B9FF`, 기존
활성색과 통일), 자동 조준=노란색, 자동 발사=빨간색.

### 8.3 수동 줌 — 6단계 + 끊기지 않는 램프 (Remote 모드 전용)

```cpp
TArray<float> ManualZoomLevels = { 0.5f, 1.f, 2.f, 4.f, 8.f, 16.f };
float ZoomStepDurationSeconds = 0.4f;
```

`AddManualZoomStep(int32 Delta)`(WBP 줌인/줌아웃 버튼이 호출, `CurrentMode != Remote`면
no-op) — 목표 인덱스만 바꿈. **첫 구현**은 "시작값/경과시간/총소요시간"을 저장해두고
Lerp하는 방식이었는데, 연타로 목표가 바뀔 때마다 총소요시간이 재계산되면서 방금
보여주던 값과 새 Alpha가 어긋나 순간적으로 앞뒤로 튀는 버벅임이 있었음(사용자 버그
리포트, 9.6절). **현재 구현**은 매 틱 `RCWS->GetZoomLevel()`(현재 실제값)에서 목표로
로그2 공간 레이트 제한 체이스 — 상태를 아예 안 남기므로 목표가 몇 번을 바뀌든 항상
"그 순간의 실제 값"에서 이어짐:

```cpp
void UpdateManualZoomRamp(float DeltaTime)
{
    const float TargetZoom = ManualZoomLevels[ManualZoomTargetIndex];
    const float CurrentLog2Zoom = FMath::Log2(RCWS->GetZoomLevel());
    const float TargetLog2Zoom = FMath::Log2(TargetZoom);
    const float MaxLog2Delta = DeltaTime / ZoomStepDurationSeconds;
    const float NewLog2Zoom = FMath::Clamp(TargetLog2Zoom, CurrentLog2Zoom - MaxLog2Delta, CurrentLog2Zoom + MaxLog2Delta);
    RCWS->SetZoomLevel(FMath::Exp2(NewLog2Zoom));
}
```

로그 공간을 쓰는 이유: `ManualZoomLevels`의 인접 단계가 전부 정확히 2배씩이라
(0.5,1,2,4,8,16 → log2 값은 -1,0,1,2,3,4로 등간격) 이러면 몇 단계를 건너뛰든 "한
단계=`ZoomStepDurationSeconds`초" 감각이 8x/16x 근처에서도 그대로 유지됨 — 선형
공간에서 그냥 값을 더했다면 8→16 구간(격차 8)이 0.5→1 구간(격차 0.5)보다 16배
오래 걸렸을 것.

`RCWSComponent::MaxZoomLevel`을 10→16으로 상향(2026-07-13) — 안 그러면 수동 줌 마지막
단계(16x)가 `SetZoomLevel`의 내부 클램프에 걸려 10x로 잘림.

### 8.4 탐색 스윕 (AutoAim/AutoFire, 표적 없을 때)

```cpp
float SearchSweepSpeedDegPerSec = 15.f;      // 기존 MaxAutoAimSlewRateDegPerSec 재사용 안 함(확정)
float SearchSweepHalfRangeDegrees = 100.f;   // ±100도 = 좌우 200도
float SearchZoomLevel = 0.5f;
```

차체 forward heading을 중심으로 오프셋을 매 틱 `±SearchSweepSpeedDegPerSec×DeltaTime`만큼
진행, ±`SearchSweepHalfRangeDegrees`에서 방향 반전. 목표 오프셋 자체가 이미 일정한
속도로 서서히 움직이므로, 2절과 동일한 레이트 제한 슬루잉으로 그 목표를 쫓아가면
결과적으로 일정 속도의 연속 회전이 됨(별도의 "부드럽게 만드는" 로직 불필요).

### 8.5 조준 시 거리비례 자동 줌

```cpp
TargetZoom = RangeMeters / ZoomReferenceMeters;  // ZoomReferenceMeters 기본 100, 튜닝용
```

6단계 스냅이 아니라 **연속적인 비율 계산**(사용자 확정 사항). 탐색 줌(8.4절)과 조준 줌
둘 다 목표값이 매 틱 계속 바뀔 수 있어서(스윕 중 갑자기 대상 발견 등), 8.3절의 계단식
램프 대신 **초당 최대 변화량 제한**(`MaxAutoZoomChangeRatePerSecond`, 기본 2.0)이라는
더 단순한 공용 램프를 씀 — 2절 안정화, 5절 자동조준 슬루잉과 같은 레이트 제한 체이스
관용구의 세 번째 적용 사례.

### 8.6 입력 경로

- 조이스틱 pan/tilt(`DoCameraLook`): `CurrentMode != Remote`면 드롭 — Remote에서만 조작자
  입력이 통과됨(기존엔 `bAutoAimEnabled` 체크였던 걸 모드 체크로 교체)
- 콘솔: `SetRCWSAutoAim`/`SetRCWSAutoFire`(불리언 2개) 제거 →
  `SetRCWSMode Remote|AutoSurveillance|AutoAim|AutoFire` 하나로 통합(`SetUGVMode`와 동일한
  FString 파싱 스타일)
- 신규 조이스틱 버튼 3개(`ManualFireAction`과 동일한 프로퍼티-only 선언 방식, 실제 IA_
  애셋/키 바인딩은 사용자 몫):
  - `RCWSModeToggleAction` — `Started` 트리거 시 `CycleControlMode()`
  - `RCWSZoomInAction`/`RCWSZoomOutAction` — `Started` 트리거 시
    `AddManualZoomStep(+1)`/`(-1)` (8.3절). `IA_RCWSZoomIn`/`IA_RCWSZoomOut`(신규 생성,
    미사용 `IA_Interact` 복제)를 CDO에 지정.
- WBP: `ModeText`를 감싼 Button → `Monitor1Widget::CycleActiveRCWSMode()`, 줌인/줌아웃
  버튼 → `AddZoomStepToActiveRCWS(±1)` — 이 프로젝트의 확립된 컨벤션대로 클릭 처리
  자체는 WBP 그래프에서, C++은 BlueprintCallable 진입점만 제공(`UAVZoom1xText` 주석 참고)

### 8.7 자동 감시(`AutoSurveillance`) — Remote의 배타성

**배경**: `CameraControlTarget`(`Atitan_examplePlayerController`, Idle/TruckRCWS/UGVRCWS/
UAVGimbal)이 기본값 `Idle`이라 `SetCameraControlTarget` 콘솔 명령을 수동으로 쳐야만
조이스틱이 아무 RCWS에도 반응하지 않았던 문제 + "트럭/UGV RCWS 2개와 UAV 짐벌 중 지금
조이스틱이 실제로 향한 것 딱 하나만 '원격 제어' 상태여야 하고, 나머지는 그냥 놀고 있지
말고 감시라도 하고 있어야 한다"는 사용자 아이디어가 겹쳐서 나온 설계.

**기본값 변경**: `CameraControlTarget` 기본값을 `Idle`→`UGVRCWS`로 변경 — 처음부터
조이스틱이 UGV RCWS를 조작.

**`AutoSurveillance` 모드**: `AutoAim`과 거의 같은 코드 경로(`UpdateAutoAim`)를 타지만,
**표적이 감지돼도 절대 조준/줌인/락온하지 않고 항상 탐색 스윕만**(8.4절) — "누군가 지켜는
보고 있지만 교전 의사는 없는" 상태. 구현은 `UpdateAutoAim` 맨 앞에 분기 하나만 추가:
`CurrentMode == AutoSurveillance`면 `SelectNearestEnemyTarget()` 자체를 호출하지 않고
곧장 `UpdateSearchSweep`로 감(8.5절의 거리비례 자동줌도 `CurrentAutoAimTarget`이 항상
null이라 자연히 `SearchZoomLevel`만 씀 — 별도 분기 불필요).

**전환 트리거 — `Atitan_examplePlayerController::SyncRCWSControlModeForCameraTarget`**:
`SetCameraControlTarget` 호출 시(및 `BeginPlay`에서 초기 상태를 맞추기 위해 `Idle→
CameraControlTarget`으로 한 번) `(이전 타겟, 새 타겟)`을 받아:

```cpp
// 조이스틱이 떠난 RCWS: Remote로 얼어붙어 있었을 때만 자동 감시로. AutoAim/AutoFire
// 중이었다면 그대로 둠(조이스틱과 무관하게 계속 자동 교전해야 하므로).
if (OldFireControl && OldFireControl->CurrentMode == ERCWSControlMode::Remote)
    OldFireControl->SetControlMode(ERCWSControlMode::AutoSurveillance);

// 조이스틱이 새로 향한 RCWS: 무조건 Remote로(조작자가 직접 잡았다는 뜻이므로 이전
// 모드가 뭐였든 덮어씀).
if (NewFireControl) NewFireControl->SetControlMode(ERCWSControlMode::Remote);
```

`ResolveFireControlFor(ECameraControlTarget)`(신규, `ResolveActiveFireControl()`과 달리
임의의 타겟을 인자로 받음 — 이전/새 타겟 둘 다 조회해야 해서 "현재 멤버 기준" 버전만으론
부족)로 TruckRCWS/UGVRCWS만 실제 `URCWSFireControlComponent`를 반환, UAVGimbal/Idle은
`nullptr`(UAV는 짐벌 전용 카메라라 이 컴포넌트 자체가 없음 — "3개 중 하나" 셈에는
들어가지만 자동 감시 상태를 가질 방법도 필요도 없음).

### 8.8 저배율(0.5x) 화면 암전 — FOV 안전 클램프 (`RCWSComponent::SetZoomLevel`)

`URCWSComponent::SightCamera->FOVAngle = CameraFOV / ZoomLevel`(`CameraFOV` 기본
90도) — `MinZoomLevel`(0.5)에서 90/0.5 = **정확히 180도**가 나옴. 원근투영 카메라는
FOV가 180도에 닿거나 넘으면 투영행렬이 특이(degenerate)해져서 렌더링이 깨짐(9.5절 —
실제로 "0.5배율에서 화면이 검게 됨" 버그로 재현됨). `CameraFOV`는 여전히 인스턴스별로
튜닝 가능한 값(Details 패널, `BP_TitanTruck`/`BP_UGV`의 RCWS 컴포넌트)이지만, 그 값이
얼마든 결과 FOV가 절대 위험 구간에 들어가지 않도록 `SetZoomLevel` 안에서 한 번 더
안전 클램프:

```cpp
SightCamera->FOVAngle = FMath::Min(CameraFOV / ZoomLevel, 170.f);
```

170도는 하드코딩된 안전 상한(엔진 차원의 물리적 한계에 가까운 값이라 EditAnywhere로
노출 안 함) — `CameraFOV`를 낮추면(예: 60~70도) 170도 클램프에 걸리기 전에 이미
0.5x에서의 "너무 넓어 보이는" 체감 자체를 줄일 수 있음.

### 8.9 줌 배율 연동 조이스틱 감도 보정 (`DoCameraLook`)

`CameraLookRateDegPerSec`(기본 90도/초)은 화면 FOV와 무관한 고정 각속도라, 배율이
높을수록(FOV가 좁을수록) 같은 조이스틱 입력이 화면상 훨씬 빠르게 움직여 보임 — "1x에서
딱 맞던 감도가 16x에서 너무 빠름" 증상. FOV가 `CameraFOV/ZoomLevel`로 배율에 반비례해서
좁아지므로, 각속도를 그 RCWS(또는 UAV 짐벌)의 현재 `GetZoomLevel()`로 나누면 화면상
체감 속도가 배율과 무관하게 일정해짐:

```cpp
const float ZoomScale = FMath::Max(Truck->RCWS->GetZoomLevel(), KINDA_SMALL_NUMBER);
Truck->RCWS->AddPanTiltInput(PanDeltaBase / ZoomScale, TiltDeltaBase / ZoomScale);
```

트럭/UGV RCWS뿐 아니라 UAV 짐벌(`AUAVPawn::GetZoomLevel()`, 1x/2.5x 두 단계)도 같은
`CameraFOV/ZoomLevel` 공식을 쓰므로 동일하게 보정 — 세 타겟 전부 `DoCameraLook`의
`switch` 안에서 각자 대상의 `GetZoomLevel()`로 나눔.

## 9. 트러블슈팅 기록 (겪은 순서대로)

### 9.1 `bLoaded`/`bFireReady` 기본값이 `false`라 수동 사격이 아예 안 됨

사용자 증상: "자동사격만 끄면 수동으로 발사 가능한거 맞아? 로그 추가해줄래?" — RPM이나
사격 조건 문제로 오판하기 쉬운 증상이었지만, 실제 원인은 `RCWSTypes.h`의
`bLoaded`/`bFireReady`가 둘 다 `false`로 초기화된 채 그걸 `true`로 바꿀 UI/로직이
어디에도 없었던 것(장전/사격대기 전환 컨트롤 자체가 아직 미구현). 기본값을 `true`로
변경(2026-07-13) — "장전/대기 전환" UI가 생기기 전까지는 배치된 RCWS는 항상 전투
준비완료 상태로 가정(AmmoCurrent가 처음부터 가득 찬 것과 같은 전제). 요청받은 대로
진단 로그(차단된 발사 시도를 1초 스로틀로 로깅)도 같이 추가.

### 9.2 발사 후 씬 캡처 화면들이 검은색으로 깜빡임

증상: "발사를 하고 나면 wbp의 모든 씬 캡쳐 뷰어 이미지들이 막 검은색으로 꺼졌다가
켜지고... rcws 3d 렌더링 화면도 미니맵처럼 안꺼지고 잘 보여." 미니맵(드물게 갱신)과
RCWS 3D 디오라마(별도 렌더 경로)는 안 그러는데 자주 갱신되는 씬 캡처만 그런 걸로 봐서,
발사 시 카메라 렌즈 바로 앞을 지나가는 뭔가에 오토 익스포저가 반응하는 것으로 추정(이전
세션의 RCWS 디오라마 오토 익스포저 버그와 증상 패턴은 비슷하나 원인은 다를 수 있음).
`ARCWSProjectile::bDrawDebugTrail`(매 틱 디버그 스피어 draw)이 유력 용의자라 기본값을
`true`→`false`로 변경 — 확인 결과 해결됨("잘 작동해"). 오토 익스포저/눈 적응 설정 자체를
건드리는 건 유보 — 이전에 UAV 짐벌 카메라에서 눈 적응을 껐다가 반대로 화면이 하얗게
날아가는 다른 버그를 겪은 적이 있어서, 안전한 일괄 변경이 아님을 알고 있었음.

### 9.3 `OnHitByProjectile`이 `BP_Enemy` 블루프린트에서 오버라이드로 안 보임

`UDetectableTargetComponent`에 `BlueprintImplementableEvent`를 달아서 컴포넌트 자체가
피격을 알리게 설계했었는데, **컴포넌트에 붙은 `BlueprintImplementableEvent`는 소유
액터의 블루프린트에서 오버라이드할 수 없다**는 UE의 기본 동작을 놓친 설계 실수였음.
`OnComponentHit`/`OnComponentBeginOverlap`과 동일하게 `BlueprintAssignable` 동적
멀티캐스트 델리게이트로 바꿨다가, 7.2절의 발견(이미 `Event AnyDamage`가 존재) 이후 이
델리게이트 자체를 통째로 제거함 — 최종적으로는 표준 데미지 파이프라인만 남음.

### 9.4 148개 `NavModifierVolume`과 발사체가 충돌 판정

증상 로그: `대상=NavModifierVolume_3 컴포넌트=BrushComponent0`. `ugv_driving_dev_guide.md`
§13.2에서 이미 한 번 겪은 것과 **정확히 같은 함정** — `Custom` 콜리전 프로파일에서
일부 채널만 명시하면 명시 안 된 채널(`WorldDynamic`)은 조용히 **Block**으로 남는다.
그때는 UGV 맵 이탈 텔레포트 쪽에서 소비자 코드가 별도 무시 리스트로 우회했지만, 이번엔
**근본 원인 자체를 고침** — 148개 볼륨 전부의
`BrushComponent0.bodyInstance.collisionResponses.responseArray`에 `WorldDynamic:
ECR_Ignore` 항목을 MCP 배치 스크립트로 추가(기존 `Visibility`/`Camera`/`GameTraceChannel1`
응답과 `AreaClass=NavArea_Road`는 그대로 보존). 첫 시도는 PIE(Play In Editor) 도중이라
액터 경로가 임시 `/Game/UEDPIE_0_...` 월드로 풀려서 148개 중 다수가 실패 — Play 정지
후 재실행해서 148개 전부 성공.

**교훈**: `Custom` 콜리전 프로파일 액터를 새로 만들 때는 처음부터 필요한 채널을 전부
명시할 것 — 명시 안 된 채널의 기본값이 Block이라는 게 두 번이나 발목을 잡음.

### 9.5 0.5배율에서 화면이 검게 암전

증상: "배율 0.5배가 시야각이 너무 커져서 그런건지 엄청 넓어지다가 결국엔 검은색으로
화면이 아무것도 안보이게 됨." 8.8절 참고 — `CameraFOV`(90) / `MinZoomLevel`(0.5) =
정확히 180도라 원근투영이 특이점에 걸린 것. `SetZoomLevel`에 170도 안전 클램프를
추가해 해결.

**참고**: 이전에 보고됐던 "`RCWSModeToggleAction` 조이스틱 버튼을 눌러도 모드가 안
바뀜" 증상(9.4절 이후 향후 작업에 미확인 버그로 남겨뒀던 것)은 이후 "다 잘 작동함"으로
확인됨 — C++ 쪽엔 문제가 없었던 걸로 봐서 `IMC_Default`의 `IA_Reload` 키 매핑 쪽
이슈였던 것으로 추정(정확한 원인은 사용자가 직접 해결, 별도 기록 없음).

### 9.6 수동 줌 버튼 연타 시 배율이 버벅거림

증상: "줌 배율 조정 버튼 빠르게 누르면 화면이 버벅거리던데? 0.5에서 16까지 일정하게
변하는게 아니라 막 배율이 버벅거려." 원인/수정은 8.3절 참고 — "시작값/경과시간/
총소요시간 저장 후 Lerp" 방식이 연타로 목표가 바뀔 때마다 총소요시간을 재계산해서
방금 보여주던 값과 어긋나는 게 근본 원인이었음. 사용자가 직접 "목표 배율 값 변수
하나 두고 틱마다 현재 배율에 일정값 +-" 방식을 제안했고, 그 방향으로 재작성(로그
공간 레이트 제한 체이스)해서 해결.

### 9.7 "Niagara" 모듈 누락으로 빌드 실패

증상: `NiagaraComponent.h` 관련 컴파일 에러 다수(`형식 지정자가 없습니다`,
`Z_Construct_UClass_UNiagaraComponent: 선언되지 않은 식별자입니다` 등) — 전형적인
"헤더를 못 찾아서 타입 자체가 안 보이는" 증상. 원인: Niagara 플러그인 자체는 이미
프로젝트에서 쓰이고 있었지만(`NS_Damage`, `NS_Jump_Trail` 등 기존 애셋 존재),
`titan_example.Build.cs`의 `PublicDependencyModuleNames`엔 `"Niagara"`가 없었음 — 애셋과
C++ 모듈 의존성은 별개라는 걸 놓친 실수. 추가하고 나니 정상 빌드(단, `.Build.cs` 변경은
Live Coding으로 안 잡히고 전체 리빌드 필요).

### 9.8 투사체끼리 서로 충돌 — 총구 앞에서 가끔 피격 이펙트

증상: "총알끼리 부딪히기도 하나? 왜 총구 바로앞에서 가끔씩 피격 이펙트가 보이지?"
사용자가 정확히 원인을 짚음 — `ARCWSProjectile::CollisionComponent`가 오브젝트 타입
`ECC_WorldDynamic`인데(7.1절), 콜리전 응답을 "전체 Block + Visibility/Camera만
Ignore"로 설정해서 `WorldDynamic` 채널 자체는 여전히 Block이었음. 투사체들이 전부
같은 오브젝트 타입이라 서로 물리적으로 막고 있었던 것 — 발사 빈도가 높은 총구
근처가 겹칠 확률이 가장 높아 거기서 자주 목격됨.

```cpp
CollisionComponent->SetCollisionResponseToChannel(ECollisionChannel::ECC_WorldDynamic, ECollisionResponse::ECR_Ignore);
```

실제 표적(차량 메시/적군 캡슐)은 코드상 `WorldDynamic`을 명시적으로 쓰는 곳이 없어서
(기본 콜리전 프로파일이라 대부분 `WorldStatic`/`Pawn`) 이 변경으로 진짜 명중 판정이
깨질 위험은 없음.

## 10. 향후 작업

- **표적 추적 비활성화 토글**(8.1절) — 지금은 `TargetTrackingText`가 "추적 중" 고정.
  실제 감지 on/off 로직은 아직 미구현.
- 반동 — 처음부터 범위 밖으로 확정, 계속 유지.
- 아군 30명 — `detection_dev_guide.md` 6절 참고, 별도 경량 액터로 아직 미착수.
- **사운드 애셋 미할당** — `FireSound`/`ImpactSound`/`EnemyImpactSound` 전부 아직 비어있음
  (12.3절 감쇠 로직은 이미 구현돼있어서, 사운드 애셋만 Details 패널에 꽂으면 바로 거리
  감쇠까지 적용됨).
- **`NS_RCWSTracer`(기존 `NS_Jump_Trail` 복제본) 정리 여부** — `TracerTrailEffect`가
  `NS_bullet`(12.1절)로 교체되면서 이제 안 씀, 삭제할지는 미정.
- **`Muzzle` 소켓 실제 추가** — 12.4절의 자동 감지 로직은 준비돼있지만, 지금 플레이스홀더
  RCWS 마운트(큐브)엔 "Muzzle"이라는 이름의 자식 컴포넌트/소켓이 아직 없어서 항상 폴백
  경로(사이트+오프셋 근사치)만 씀. 실제 RCWS 메시가 생기면 거기에 소켓만 추가하면 됨.
- 사용자가 직접 해야 할 것: `BP_Enemy`에 `DetectableTargetComponent` 추가 +
  `Event AnyDamage` 사망 분기에 `SetIncapacitated(true)` 연결(7.3절), `IMC_Default`에
  `IA_Shoot`/`RCWSModeToggleAction`/`RCWSModePreviousAction`/`IA_RCWSZoomIn`/
  `IA_RCWSZoomOut` 키 바인딩, WBP에서 `ModeText`/줌 버튼의 OnClicked 그래프 연결(8.6절),
  `NS_bullet`(예광탄 리본) 색상/두께 튜닝(12.1절 — MCP로 Niagara 그래프 편집 불가).

## 11. 발사/피격 VFX (`ARCWSProjectile`)

### 11.1 예광탄 — 항상 보이는 메시 + Niagara 트레일

투사체가 완전히 안 보이던 상태(7.1절 당시 VFX 미착수)에서, 모든 탄에 작은 실린더
메시(`RoundMesh`, 엔진 기본 `/Engine/BasicShapes/Cylinder`, `CollisionComponent`의 자식,
`NoCollision`)를 추가 — "일반탄도 실제로 그려지긴 해야 함"(사용자 확정)이라 항상
붙어있고, 예광탄인지 아닌지는 밝기로만 구분:

```cpp
UPROPERTY(...) FLinearColor TracerEmissiveColor = FLinearColor(6.f, 2.f, 0.f, 1.f);
UPROPERTY(...) FLinearColor NormalEmissiveColor = FLinearColor(0.02f, 0.02f, 0.02f, 1.f);
```

신규 머티리얼 `M_RCWSRound`(`/Game/Vehicles/UGV/`, MCP `MaterialTools`로 노드 그래프째
생성 — `create_material`/`add_expression`(VectorParameter "EmissiveColor")/
`connect_to_output`(MP_EmissiveColor)/`recompile`): `BeginPlay`에서
`RoundMesh->CreateAndSetMaterialInstanceDynamicFromMaterial()`로 MID 하나 만들어두고,
`LaunchFrom`이 매 발 `SetVectorParameterValue("EmissiveColor", ...)`로 밝기만 바꿔치기
(메시/머티리얼 애셋 교체 없음).

예광탄일 때만 **Niagara 리본 트레일**(`TracerTrailComponent`, `UNiagaraComponent`)도
같이 켬 — 투사체 자체가 풀링되는 구조라 매 발 스폰/파괴 대신 **미리 만들어두고
Activate/Deactivate만**:

```cpp
if (bIsTracer) TracerTrailComponent->Activate(true);  // true=리셋, 재사용 시 새 궤적으로
else           TracerTrailComponent->Deactivate();
```

`Deactivate()`(풀 반환 시)에서도 반드시 꺼서, 재사용된 인스턴스가 이전 궤적 중간부터
이어지지 않게 함.

**처음엔 `NS_Jump_Trail`(플랫포밍 템플릿의 기존 점프 이펙트 Niagara 시스템, Ribbon
렌더러+SpawnPerUnit 구조 확인 후) 복제본(`NS_RCWSTracer`)을 썼는데, 사용자가 참고
영상(유튜브 튜토리얼)의 제작자가 만든 전용 "bullet" Niagara 시스템을 직접 받아와서
그걸로 교체함** — `NS_bullet.uasset`을 `Content/Vehicles/UGV/`에 파일로 직접 복사하는
방식으로 임포트(에디터 임포트 다이얼로그가 안 먹혔던 것으로 보임). 의존성 조회
(`get_dependencies`) 결과 전부 엔진 기본 `/Niagara/...` 모듈만 참조해서 깨진 참조 없이
깔끔하게 로드됨 — 리본+스프라이트 렌더러 둘 다 있는 구성.

**MCP 한계**: Niagara 시스템 내부 그래프(에미터/렌더러 모듈, 리본 색상·너비·수명)는
편집 도구가 MCP에 없음(`MaterialTools` 같은 전용 툴셋이 Niagara엔 없음) — 애셋
복제/파일 복사까지는 MCP/직접 조작으로 가능하지만, 실제 색상·크기 튜닝은 사용자가
Niagara 에디터에서 직접.

### 11.2 예광탄 패턴 — `TracerInterval`

```cpp
UPROPERTY(...) int32 TracerInterval = 4;   // 일반탄 3 + 예광탄 1 반복
private: int32 ShotsFiredCount = 0;         // 트리거 놓았다 다시 잡아도 안 끊김(누적)
```

`Fire()`에서 `const bool bIsTracer = (++ShotsFiredCount % TracerInterval) == 0;`.

### 11.3 시야 확보 — 트레일 스케일 + FOV/충돌 버그

`NS_bullet`을 그대로 붙였더니 안 보인다는 리포트 — 유튜버가 근거리 FPS 데모용으로
만든 거라 리본 너비가 그 스케일에 맞춰져 있어서, RCWS 교전거리(수십~수백m)에서는
사실상 서브픽셀이라 안 보였을 가능성이 큼(노출/밝기보다 스케일이 더 유력한 원인으로
판단). `TracerTrailScale`(기본 `FVector(4,4,4)`, `BeginPlay`에서
`TracerTrailComponent->SetRelativeScale3D()`)을 추가해서 Niagara 그래프 안 건드리고도
크기 조정 가능하게 함 — 이후 사용자가 `NS_bullet` 자체에서도 직접 사이즈를 키워서
해결. 별개로 겪은 진짜 원인 2건은 9.7/9.8절(빌드 실패, 투사체 자기충돌) 참고.

### 11.4 머즐 플래시/피격 이펙트 (Cascade)

`Realistic_Starter_VFX_Pack_Vol2`(전부 Cascade `UParticleSystem`, Niagara 아님) 사용 —
`UGameplayStatics::SpawnEmitterAtLocation`으로 스폰, 풀링 불필요(콜리전/물리 상태 없는
원샷 연출이라 투사체 풀링과 이유 자체가 다름).

**전용 머즐 플래시 애셋은 프로젝트에 없어서**(`FPS_Weapon_Bundle`엔 무기 메시의
"Muzzle_Break" 파츠만 있음) `Sparks/P_Sparks_A`를 대용으로 지정(스타터 팩에 전용
애셋이 없을 때 흔한 방식, `EditAnywhere`라 언제든 교체 가능).

피격 이펙트는 대인화기 스케일에 맞게 `Explosion/`(차량급 대폭발) 대신 `Hit/`+`Blood/`
계열: 일반(환경) 피격 = `Hit/P_Default`, 적(Faction==Enemy `DetectableTargetComponent`)
피격 = `Blood/P_Blood_Splat_Cone`(null이면 일반 이펙트로 폴백) — `BP_Enemy`의 기존
래그돌/사망 애니메이션(`Event AnyDamage`)과는 완전히 독립적인 순수 코스메틱 파티클.

## 12. 사운드·조준 정밀도 개선 (2026-07-14)

### 12.1 사운드 거리 감쇠 — 별도 애셋 없이 런타임 오버라이드

`FireSound`(`RCWSFireControlComponent`)/`ImpactSound`/`EnemyImpactSound`
(`ARCWSProjectile`) 재생 시 거리에 따라 작아지는 감쇠가 필요했는데, `USoundAttenuation`
애셋을 만드는 MCP 도구가 없고(프로젝트에 기존 애셋도 없음) 사용자가 아직 실제 사운드
파일도 안 찾은 상태라 "사운드 애셋 자체의 감쇠 설정에 의존"하는 방식은 못 씀. 대신
`UGameplayStatics::PlaySoundAtLocation`(고정 볼륨) 대신 `SpawnSoundAtLocation`이 돌려주는
`UAudioComponent`에 `AdjustAttenuation()`으로 런타임에 감쇠 설정을 얹음 — 별도 애셋 없이
코드만으로 항상 감쇠 적용됨(나중에 어떤 사운드 애셋을 꽂아도 자동 적용):

```cpp
if (UAudioComponent* AC = UGameplayStatics::SpawnSoundAtLocation(World, FireSound, MuzzleLocation))
{
    FSoundAttenuationSettings Settings;
    Settings.bAttenuate = true;
    Settings.bSpatialize = true;
    Settings.AttenuationShape = EAttenuationShape::Sphere;
    Settings.AttenuationShapeExtents = FVector(FireSoundAttenuationRadiusCm, 0.f, 0.f);
    Settings.FalloffDistance = FireSoundFalloffDistanceCm;
    AC->AdjustAttenuation(Settings);
}
```

`FireSoundAttenuationRadiusCm`/`FalloffDistanceCm`(발사음), `ImpactSoundAttenuationRadiusCm`/
`FalloffDistanceCm`(피격음) 둘 다 `EditAnywhere`로 튜닝 가능(기본 반경 1000cm, 페이드
거리 150000cm=1.5km).

### 12.2 오디오 리스너를 UGV에 고정

이 프로젝트는 `bDisableWorldRenderingOnStart`로 3D 뷰포트 자체를 안 그리는 대시보드
방식(`ugv_driving_dev_guide.md`)이라, 기본 오디오 리스너 위치(PlayerController의 뷰
타겟/카메라 기준)가 실제 조작 중인 차량과 무관한 곳일 수 있음 — "듣는 위치는
기본적으로 UGV로"(사용자 요청)에 맞춰 `Atitan_examplePlayerController::BeginPlay`에서
명시적으로 고정:

```cpp
SetAudioListenerOverride(UGV->GetRootComponent(), FVector::ZeroVector, FRotator::ZeroRotator);
```

`AttachToComponent` 파라미터라 UGV가 움직이면 리스너도 같이 따라감. CameraControlTarget
전환(8.7절)과는 별개 로직 — 지금은 "기본적으로 UGV" 요구사항만 반영, 조작 타겟 전환에
따라 리스너도 같이 옮기는 건 안 함(요청 범위 밖).

### 12.3 총구-사이트 오프셋 자동 감지 — `MuzzleRef`

"나중에 UGV RCWS 카메라 위치랑 실제 총구 위치가 이격될 것 같은데, 자동으로 감지해서
조준 계산에 반영하는 로직"(사용자 요청, 선제적 설계) — `RCWSRef`/`TargetDetectionRef`와
동일한 `FComponentReference`-by-name 관례로 `MuzzleRef`(기본 이름 "Muzzle") 추가:

```cpp
FVector GetMuzzleWorldLocation() const
{
    if (MuzzleComponent) return MuzzleComponent->GetComponentLocation();
    return RCWS->GetSightWorldLocation() + RCWS->GetSightWorldRotation().Vector() * MuzzleForwardOffsetCm; // 폴백
}
```

**핵심은 이 함수 하나를 실제 발사 스폰 지점(`Fire()`)뿐 아니라 탄도 계산
(`ComputeFiringSolution`)과 조준점 UI(`UpdateAimPointForUI`)에도 전부 통일해서 쓰는
것** — 지금(플레이스홀더 마운트, "Muzzle" 소켓 없음)은 항상 폴백 경로라 기존 동작과
100% 동일하지만, 나중에 실제 RCWS 메시에 "Muzzle"이라는 이름의 소켓/컴포넌트만 추가하면
사이트-총구 오프셋(특히 좌우/상하로 어긋난 경우의 패럴랙스)이 코드 변경 없이 자동으로
조준 계산에 반영됨. 이전엔 `MuzzleForwardOffsetCm`(순수 전방 오프셋)이 발사 스폰
지점에만 쓰였는데, 탄도 계산 자체는 여전히 사이트 위치를 원점으로 삼고 있었던 것도
이번에 같이 통일됨.
