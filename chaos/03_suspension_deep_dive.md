# Chaos Wheeled Vehicle 서스펜션 딥다이브 (UE5.8 기준)

목표: M1A2 복제 방식이든 처음부터 구현하는 방식이든 서스펜션을 설계/튜닝/디버깅할 때
자신 있게 다룰 수 있는 수준의 이해 확보. 특히 `M1A2_UGV_Conversion.md` 2절에서 겪었던
"휠 스케일 0.5 적용 시 지면에서 붕 뜨는 버그"와 커스텀 스켈레탈 메시 시도에서 겪은
"바퀴 16개의 SuspensionState.ContactPoint 붕괴 버그"를 다시 만났을 때 빠르게 진단할 수
있도록 하는 것.

확인 여부 표기: **[공식]** = Epic 공식 문서/API, **[커뮤니티]** = 포럼/블로그/제3자 분석
(신뢰도 있으나 비공식), **[가설]** = 이번 조사로 직접 확인은 못했지만 정황상 유력한 추정.

---

## 1. 서스펜션 계산 메커니즘

### 1.1 프로퍼티 전체 목록 [공식]

`UChaosVehicleWheel`(Python API 문서 기준, 5.0~5.3 동일)의 서스펜션 관련 프로퍼티:

| 프로퍼티 | 타입 | 설명 |
|---|---|---|
| `SuspensionMaxRaise` | float | 서스펜션이 정지 위치보다 위로(압축 방향 반대) 늘어날 수 있는 최대 거리 |
| `SuspensionMaxDrop` | float | 서스펜션이 정지 위치보다 아래로(신장 방향) 늘어날 수 있는 최대 거리 |
| `SuspensionDampingRatio` | float | 감쇠비, [0~1] 범위. 클수록 더 빨리 정지 |
| `SpringRate` | float | 스프링 힘, N/m |
| `SpringPreload` | float | 스프링 예압, N/m |
| `SuspensionAxis` | Vector | 서스펜션 힘이 적용되는 로컬 방향 (보통 -Z축) |
| `SuspensionForceOffset` | Vector | 서스펜션 힘 적용 지점의 수직 오프셋 |
| `Offset` | Vector | 휠을 본(bone) 위치 또는(BoneName 미지정 시) 차량 원점에서 오프셋 |
| `WheelRadius` | float | 휠 반지름 |
| `WheelMass` | float | 휠 질량 (kg) |
| `WheelWidth` | float | 휠 너비 |

출처: [unreal.ChaosVehicleWheel Python API (5.3)](https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/ChaosVehicleWheel?application_version=5.3)

### 1.2 레이캐스트/트레이스 방식 [커뮤니티]

Chaos Vehicle의 서스펜션은 기본적으로 PhysX 시절 비히클 시스템(raycast 기반 서스펜션)을 계승한 구조다. 실제로 Epic 공식 문서인 [How to Convert PhysX Vehicles to Chaos](https://dev.epicgames.com/documentation/en-us/unreal-engine/how-to-convert-physx-vehicles-to-chaos-in-unreal-engine)에서 "바퀴 반지름, 서스펜션 최대 상승/하강값, 조향각도 등을 그대로 복사하면 된다"고 안내하는 것 자체가 두 시스템의 서스펜션 개념이 거의 1:1 대응됨을 시사한다.

비동기 물리 커스텀 서스펜션 샘플 프로젝트([Async-Physics-Suspension](https://github.com/fgrenoville/Async-Physics-Suspension), 관련 글 [Taming Chaos: Stable Vehicle Suspensions with Async Physics in UE5](https://levelup.gitconnected.com/taming-chaos-stable-vehicle-suspensions-with-async-physics-in-ue5-566369c7b097))에서 확인한 트레이스 길이 공식:

```
trace_distance = TravelCm + WheelRadiusCm
```

여기서 `TravelCm`은 `SuspensionMaxRaise + SuspensionMaxDrop`에 대응하는 개념으로 보인다(정확한 엔진 내부 변수명까지는 이번 조사로 확인 못함, **[가설]**). 즉 **레이캐스트/스윕 시작점은 서스펜션 부착 위치(본 위치 + Offset) 기준으로 위쪽 SuspensionMaxRaise만큼, 끝점은 아래쪽 SuspensionMaxDrop + WheelRadius만큼**이라는 통상적인 vehicle raycast suspension 모델과 일치한다. NVIDIA PhysX 공식 문서([Vehicles - PhysX SDK 3.4.0](https://archive.docs.nvidia.com/gameworks/content/gameworkslibrary/physx/guide/Manual/Vehicles.html))에도 동일한 "최대 압축 시 타이어 상단 바로 위 ~ 최대 신장 시 타이어 하단 바로 아래"까지 레이캐스트한다는 설명이 있어 Chaos가 이 모델을 계승했을 가능성이 높다.

### 1.3 스프링-댐퍼 힘 계산 (커뮤니티 경험칙) [커뮤니티]

공식 문서에는 정확한 내부 공식이 명시되어 있지 않지만, 튜닝 가이드([Tuning Chaos Vehicle Configurations](https://medium.com/@fulton_shaun/tuning-chaos-vehicle-configurations-in-unreal-engine-bcb13810737d))와 포럼 스레드([Chaos Vehicle Load and Suspension](https://forums.unrealengine.com/t/chaos-vehicle-load-and-suspension/680687))를 종합하면:

- `SpringRate`는 "1kg 기준 질량당 압축 1m에 필요한 힘"으로 근사되는 값 — 예: 1500kg 세단, 바퀴 4개 기준 바퀴당 약 3750N을 4cm 정지압축으로 지지하려면 SpringRate 250~400 정도에서 시작해서 튜닝
- `SpringPreload`는 특별한 이유 없으면 0 유지 권장
- `SuspensionDampingRatio`는 가장 중요한 튜닝값. 0에 가까우면 바운스, 1에 가까우면 스무스하지만 둔함. 스포츠카 0.45~0.65, 오프로드 차량 0.35~0.50이 커뮤니티 경험적 권장 범위 ([StraySpark 블로그](https://www.strayspark.studio/blog/chaos-vehicles-masterclass-shipping-racing-game-2026) 등에서 유사 수치 반복 언급)
- 포럼 사용자가 직접 계산한 예시 공식: `스프링 상수 = (분담 질량 × 중력) / 정지압축거리`, `바퀴당 하중 = 차량 총질량 × 중력 / 바퀴 수`

**주의**: 이 수치들은 "이렇게 하면 대체로 작동한다"는 커뮤니티 경험칙이지 엔진이 강제하는 공식이 아니다. UGV처럼 4륜이 아닌 다륜(6~8개 이상) 차량은 바퀴당 하중 배분 공식(위 예시)에서 분모를 실제 바퀴 개수로 바꿔서 다시 계산해야 한다.

### 1.4 서스펜션 제약(Constraint) 시스템의 존재 [커뮤니티, 중요]

포럼 스레드 [Chaos Vehicle Load and Suspension](https://forums.unrealengine.com/t/chaos-vehicle-load-and-suspension/680687)에서 결정적인 단서를 발견했다:

> "`p.Vehicle.DisableConstraintSuspension` 콘솔 변수를 켜면(=제약 기반 서스펜션을 끄면) '진짜' 물리 기반 서스펜션 설정값대로 작동하게 된다"

즉 **Chaos Vehicle에는 서스펜션을 순수 레이캐스트+스프링힘으로 처리하는 경로와, 물리 엔진 레벨의 "서스펜션 제약(Constraint)"으로 처리하는 경로 두 가지가 존재하며 기본값은 제약 기반으로 추정된다.** 이는 엔진 소스에 `FSuspensionConstraintPhysicsProxy`라는 클래스가 존재한다는 사실과도 부합한다(검색으로 클래스 존재는 확인했으나 내부 구현 상세까지는 확인 못함, **[가설]**).

**실전 함의**: SpringRate/SpringPreload를 "물리 교과서 공식"대로 계산해 넣었는데 예상과 다르게 동작한다면, `p.Vehicle.DisableConstraintSuspension`을 콘솔에 입력해서 거동이 달라지는지부터 확인할 것. 달라진다면 제약 기반 서스펜션 시스템 자체의 알려진 특이 동작 영역에 들어와 있는 것이다.

---

## 2. 스케일(Scale) 처리 문제 — M1A2 "붕 뜨는 버그"의 정황 증거

### 2.1 관련성 있는 알려진 엔진 동작 [공식/커뮤니티 혼합]

이번 조사로 "Chaos Vehicle Offset이 스케일을 무시한다"는 것을 딱 짚어 확인해주는 Epic 공식 문서나 버그 리포트는 찾지 못했다. 하지만 **스켈레탈 메시/Physics Asset 스케일 처리 자체가 UE에서 반복적으로 문제가 되어온 영역**이라는 강한 정황 증거를 확인했다:

1. **Kinematic 본의 스케일 강제 1 처리** [커뮤니티, 매우 유력한 원인 후보] — 포럼 검색 결과: "Physics Asset에서 Kinematic으로 설정된 본과 그 자식들은 스케일이 강제로 1로 오버라이드된다"는 보고. 즉 **본이 Kinematic이면 컴포넌트/스켈레탈 메시의 스케일 설정(우리 경우 0.5)이 무시되고 그 본과 관련된 물리 처리는 항상 스케일 1 기준으로 계산될 가능성이 있다.**
2. **PhAT(Physics Asset Tool)의 스케일 처리 비일관성** [커뮤니티] — "PhAT은 Constraint 위치에 스케일을 적용할 때와 안 할 때가 일관되지 않아서, Preview Skeletal Mesh가 non-identity 스케일이면 컨스트레인트가 제대로 작동 안 하는 경우가 있다"(포럼 [Physics Asset Scaling Issues](https://forums.unrealengine.com/t/physics-asset-scaling-issues/120603)). UE 4.15에서 일부 개선되었다고 하나 완전히 해결되지는 않은 것으로 보임.
3. Blender→UE 익스포트 파이프라인에서 아마추어(Armature) 스케일 처리 버그도 다수 보고됨(Armature 오브젝트 이름이 정확히 "Armature"일 때 특히 심화, Min Bone Size 설정과 "Use Percentage Based Scaling" 옵션이 우회책으로 언급됨). 이는 우리가 겪은 문제와 직접 인과관계는 아니지만 "블렌더-언리얼 파이프라인에서 스케일이 물리 시스템에 온전히 전달 안 되는 사례가 흔하다"는 배경을 뒷받침한다.

### 2.2 우리가 겪은 버그에 대한 가설 [가설]

M1A2 문서 기록: `BP_UGVWheel_FromTank`의 스케일을 0.5로 낮췄더니 탱크가 공중에 뜬 채로 이동, `Offset` +Z=50으로 임시 해결.

가장 유력한 설명(정황 증거 기반, 100% 확정은 아님):

- `Offset`은 **cm 단위의 절대 벡터값**으로 저장되는 프로퍼티다(1.1절 공식 문서 기준 "Vector" 타입, 단위 변환/스케일 곱 처리에 대한 언급이 문서 어디에도 없음).
- 본(bone)의 **위치 자체**는 스켈레탈 메시 컴포넌트 스케일에 따라 정상적으로 스케일되어 이동한다(본 계층 자체는 정상 스케일링됨).
- 하지만 `Offset` Vector 값은 BoneName 기준 상대 오프셋을 더할 때 **스케일이 곱해지지 않고 원래 cm 값 그대로 더해지는 것으로 추정**된다. 즉 스케일을 0.5로 줄이면 본 위치는 절반으로 줄어드는데, `Offset`에 넣은 (예: 이전 스케일 1.0 기준으로 튜닝된) 값은 그대로 절대 cm 단위로 남아서 상대적으로 "너무 큰" 오프셋이 되어버려 — 혹은 반대로 서스펜션 레이캐스트 시작점 자체가 축소된 본 위치를 기준으로 계산되면서 `WheelRadius`(마찬가지로 스케일 미반영 절대값)와 어긋나 접지 판정이 깨지는 방식 — 지면과의 관계가 무너졌을 가능성이 높다.
- 여기에 2.1-1)의 **Kinematic 본 스케일 강제 1** 현상까지 겹치면, 바퀴 본이 Kinematic으로 설정되어 있는 경우 물리 계산에서는 스케일이 아예 반영되지 않는 채로 처리됐을 수 있다.

**결론**: `Offset +Z=50` 땜빵이 "실사용에 문제 없었다"는 M1A2 문서의 기록은, 이 가설이 맞다면 우연이 아니라 **"스케일 미반영분을 수동으로 보정"한 것과 정확히 같은 효과**를 낸 것으로 보인다.

### 2.3 진단 체크리스트 — 스케일 관련 문제 재발 시

1. 문제가 재현되는 컴포넌트/스켈레탈 메시의 스케일을 **1.0으로 되돌려서** 증상이 사라지는지 먼저 확인 (스케일 원인인지 아닌지부터 확정)
2. Physics Asset에서 바퀴 본의 Physics Type이 **Simulated인지 Kinematic인지** 확인 — Kinematic이면 스케일 강제 1 오버라이드 가능성을 최우선 의심
3. `WheelRadius`, `Offset`, `SuspensionMaxRaise`/`SuspensionMaxDrop` 같은 절대값 프로퍼티들을 **스케일 비율만큼 수동으로 곱해서** 재설정해보고 증상이 개선되는지 확인 (예: 스케일 0.5면 이 값들도 원래 값의 절반으로)
4. Blender 익스포트 시 Armature/메시에 Ctrl+A로 Transform을 모두 적용(스케일 1로 정규화)한 후 재익스포트해서, "언리얼 컴포넌트 스케일을 굳이 1이 아닌 값으로 쓸 필요 자체를 없애는" 방향도 근본적 회피책으로 고려 (가장 권장 — 스케일을 조정해야 하는 상황 자체를 안 만드는 것이 가장 확실한 회피)

---

## 3. `Offset` 프로퍼티의 정확한 의미

**[공식, 1.1절 인용]**: `Offset`은 "휠을 본(bone) 위치 또는(BoneName이 없으면) 차량 원점에서 오프셋"시키는 Vector.

로컬 좌표계 기준(본의 로컬 축 기준)인지 월드 좌표계 기준인지는 공식 문서에 명시되어 있지 않았다 **[확인 필요]**. 다만 일반적인 UE 컴포넌트 오프셋 컨벤션(예: SkeletalMeshSocket, Physics Asset 등)에 비추어 보면 **본의 로컬 좌표계 기준 상대 오프셋**일 가능성이 높다(다른 벤더 가이드에서 "바퀴 콜리전 캡슐에 X-28 같은 오프셋을 준다"는 사례가 로컬 X축 기준 서술이었던 것도 이를 뒷받침).

포럼에서 확인한 실전 사용 사례([Chaos Vehicle Wheel Debug](https://forums.unrealengine.com/t/chaos-vehicle-wheel-debug/584969) 등 유사 스레드 계열): 본 위치가 실제 바퀴 중심과 정확히 일치하지 않는 애셋에서 `Offset`으로 수동 보정하는 것이 일반적인 워크어라운드로 통용됨. 즉 **`Offset`은 "본을 다시 안 찍고 코드/BP에서 미세 조정하는 땜빵용 값"으로 설계된 것에 가깝고, 애초에 본 위치 자체가 정확하면 `Offset`은 0으로 둬도 되는 게 정상**이라는 것이 커뮤니티의 공통된 태도다.

---

## 4. ContactPoint / SuspensionState 관련 알려진 버그

### 4.1 API 구조 [공식]

`UChaosWheeledVehicleMovementComponent`의 `BreakWheelStatus` 함수가 반환하는 값 중: `Contact`(bool), `ContactPoint`(Vector), `NormalizedSuspensionLength`, `SpringForce`, `SlipAngle`, `IsSlipping`, `SlipMagnitude`, `IsSkidding`, `SkidMagnitude` 등이 있다. `ContactPoint`는 레이캐스트/스윕이 지면과 접촉한 월드 좌표다.

출처: [unreal.ChaosWheeledVehicleMovementComponent Python API](https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/ChaosWheeledVehicleMovementComponent?application_version=5.0)

### 4.2 "여러 바퀴의 ContactPoint가 비슷한 좌표로 붕괴"하는 문제에 대한 정황 증거 [가설]

이 정확한 증상을 보고한 공식 버그 리포트나 포럼 스레드는 이번 조사로 찾지 못했다. 하지만 우리가 커스텀 스켈레탈 메시 시도에서 겪었던 상황(바퀴 16개가 전부 비슷한 좌표로 붕괴)과 정확히 같은 패턴의 원인으로 지목되는 사례들을 여러 건 확인했다:

1. **`WheelSetups`의 BoneName 불일치** [공식+커뮤니티] — 공식 문서/커뮤니티 모두 일관되게 강조: "BoneName은 스켈레톤의 본 이름과 대소문자·언더스코어까지 정확히 일치해야 하며, 불일치 시 **에러 메시지 없이 조용히 무시**된다." 여러 바퀴의 BoneName 설정에 오타/복붙 실수가 있었다면, 매칭 실패한 바퀴들이 전부 동일한 폴백 위치(차량 원점 등)로 수렴했을 가능성이 있다.
2. **바퀴 본이 루트 본의 직속 자식이 아닌 경우** [커뮤니티, 포럼 사례 직접 확인] — [Chaos vehicle is acting odd on one particular skeletal mesh](https://forums.unrealengine.com/t/chaos-vehicle-is-acting-odd-on-one-particular-skeletal-mesh/629713) 스레드에서 정확히 이 패턴의 버그가 보고/해결됨: "바퀴 본이 루트 본의 직속 자식이 아니면 Chaos 시스템이 휠을 잘못된 축에 부착"하는 문제였고, 해결책은 바퀴 본들을 전부 루트 본의 직속 자식으로 재배치하는 것이었다. **이는 우리 M1A2 문서 1절에서 기록한 "Root Body 분리 시 75cm 오프셋 버그"와도 본질적으로 같은 계열의 문제(본 계층 구조가 Chaos의 암묵적 가정과 어긋남)로 보인다.**
3. **Physics Asset에서 루트 본 자체에 물리 바디가 없는 경우** [커뮤니티, 우리 자체 기록과 일치] — `FindRootBodyIndex()`가 "물리 바디가 있는 첫 본을 무조건 루트로 취급"한다는 M1A2 문서의 분석과, 이번에 확인한 "루트 본 회전이 identity가 아니면 Physics Asset이 통째로 어긋난다"는 [Medium 글](https://medium.com/@python-javascript-php-html-css/fixing-unreal-engine-physics-asset-misalignment-in-custom-skeletal-mesh-movement-1279e5c4d32c)의 사례가 같은 근본 원인군(루트 본 처리의 특수성)을 가리킨다.

### 4.3 이 문제를 처음부터 피하는 규칙 (종합)

- 바퀴 본은 **반드시 루트 본의 직속 자식**으로 배치 (조부모-손자 관계 금지)
- 루트 본 자체는 Blender에서 **회전 0, 스케일 1(identity)** 로 만들고 Ctrl+A로 Transform 적용 후 export
- `WheelSetups` BoneName은 스켈레톤 본 이름과 문자 그대로(대소문자/언더스코어 포함) 일치하는지 매번 재확인 — 이름을 바꿨다면 반드시 함께 갱신
- Physics Asset에서 루트 본 자체에도 물리 바디(콜리전)를 만들어서 `FindRootBodyIndex()`가 엉뚱한 자식 본을 루트로 오인하지 않게 함 (M1A2 문서 1절 원인 분석 재확인 — 이번 조사로 이 처방을 뒤집는 근거는 못 찾음, 유효한 회피책으로 유지)

---

## 5. 서스펜션 셋업 실전 가이드 (다륜 차량 특화)

### 5.1 바퀴 개수 제한 [공식]

Chaos Vehicle은 바퀴 개수에 제한이 없다. `WheelSetups` 배열에 필요한 만큼 엔트리를 추가하면 된다. 일반적으로 조향/구동/핸드브레이크 영향을 받는 타입과 안 받는 타입, 최소 2종류의 Wheel Blueprint가 필요하다(반지름/질량/너비/서스펜션이 다른 축을 위해 3종 이상도 가능).

출처: [How to Set up Vehicles in Unreal Engine](https://dev.epicgames.com/documentation/en-us/unreal-engine/how-to-set-up-vehicles-in-unreal-engine)

### 5.2 스켈레톤/본 배치 규칙 [커뮤니티, Neutronio 가이드 기준]

- 각 바퀴 앞면이 +X축을 향해야 함
- 모든 바퀴는 개별 오브젝트여야 함(메시 병합 금지)
- 바퀴 오브젝트의 원점(center)이 바퀴 지오메트리 중심에 있어야 함
- 모든 바퀴 중심/축이 X축·Y축 위에 정확히 위치해야 함(대칭 배치가 아니면 문제 소지)
- 계층 구조: `Root` → `Wheel_Rear_Left`, `Wheel_Rear_Right`, `Wheel_Front_Left`, `Wheel_Front_Right` 형태(탱크/UGV류는 축 수만큼 확장)

출처: [The Ultimate Chaos Vehicle Guide - Neutronio Games](https://neutroniogames.wordpress.com/2024/01/17/the-ultimate-chaos-vehicle-guide/)

### 5.3 Physics Asset 요구사항 [커뮤니티, 다수 소스 일치]

- 바퀴 본마다 콜리전 바디(구/캡슐 권장) 존재
- 바퀴 본의 Physics Type은 **Simulated**(Kinematic 아님) — 2.1절의 스케일 강제 1 문제와도 직결되므로 특히 주의
- 바퀴 본마다 현실적인 질량 값 설정
- 루트/섀시 바디는 컨벡스 헐이나 박스로 차체 전체를 덮고, 질량은 섀시 바디에 설정

### 5.4 다륜(6~8개 이상) 차량 특화 주의점 [가설 + 부분 확인]

- 1.3절의 하중 배분 공식은 바퀴 4개 가정이므로, 실제 바퀴 수로 분모를 바꿔서 다시 계산할 것
- 궤도/트랙형 차량(탱크류)에 대한 Chaos 공식 지원은 제한적으로 보인다. 관련 포럼 스레드([Tracked Chaos Vehicles](https://forums.unrealengine.com/t/tracked-chaos-vehicles/735606), [Rigging and Animating Tank Treads for Chaos Vehicle Physics](https://forums.unrealengine.com/t/rigging-and-animating-tank-treads-for-chaos-vehicle-physics/683580), [Controlling a Tanks individual Tracks in UE5](https://forums.unrealengine.com/t/controlling-a-tanks-individual-tracks-in-ue5/610143))을 확인했으나, 명확히 "이렇게 하면 된다"는 검증된 정답이 커뮤니티에 존재하지 않는다 — 다들 각자 방식(스키드 스티어를 일반 WheelSetups로 흉내내는 방식, PID 컨트롤러 등)으로 우회하고 있다. **M1A2 문서 2절에서 확인한 "TankTurn 매크로가 SetYawInput()을 호출하는 방식"이 실제로는 표준 Chaos Wheeled Vehicle의 개별 휠 조향이 아니라 차체 전체에 요 토크를 가하는 스키드 스티어 흉내 방식이라는 뜻인데, 이는 커뮤니티에서도 사실상 표준으로 통용되는 접근으로 보인다.**
- `SetSuspensionParams`로 런타임에 SpringRate/Preload를 바꾸면 전진력이 절반가량 감소하는 등 부작용이 보고됨([포럼](https://forums.unrealengine.com/t/chaos-vehicle-set-suspension-params-is-wierd-changing-spring-rate-and-preload/1522446)) — `Wheel Load Ratio`를 0보다 큰 값으로 설정하면 완화된다는 보고가 있으니, 런타임 서스펜션 튜닝 UI를 만들 계획이라면 이 프로퍼티를 반드시 같이 노출할 것
- UE5.4대에서 "물리 시뮬레이션을 꺼도 바퀴가 계속 회전"하는 회귀 버그 보고([포럼](https://forums.unrealengine.com/t/ue5-4-2-chaos-vehicle-strange-wheel-and-suspension-behavior/1933027))가 있었음 — 5.8 기준 재현되는지 별도 확인 필요. 원인은 특정 안 됐고, 사용자 사례에서는 매틱 `SetAngularDamping()` 호출 코드가 얽혀서 발생 — 매틱 물리 프로퍼티를 직접 건드리는 코드가 있다면 의심 대상 1순위

---

## 6. 종합 진단 체크리스트 (서스펜션 문제 재발 시)

1. **콘솔 변수 토글**: `p.Vehicle.DisableConstraintSuspension` 켜고 끄면서 거동 변화 확인 → 제약 기반 서스펜션의 알려진 특이 영역인지 먼저 분리
2. **스케일 원점 확인**: 문제 컴포넌트를 스케일 1.0으로 되돌려서 재현되는지 확인
3. **Physics Type 확인**: 바퀴 본이 Simulated인지 Kinematic인지(Kinematic이면 스케일 무시 가능성)
4. **BoneName 정확성**: `WheelSetups`의 BoneName과 스켈레톤 본 이름이 대소문자/언더스코어까지 일치하는지
5. **본 계층 확인**: 바퀴 본이 루트 본의 직속 자식인지, 루트 본 자체에 물리 바디가 있는지
6. **루트 본 Transform**: Blender에서 루트 본 회전/스케일이 identity인지, Ctrl+A로 적용됐는지
7. **Offset/WheelRadius 등 절대값 프로퍼티**: 컴포넌트 스케일 비율만큼 수동 보정이 필요한지 (2.3절)
8. **런타임 서스펜션 변경 여부**: `SetSuspensionParams`를 코드/BP에서 호출하고 있다면 `Wheel Load Ratio` > 0 설정 여부 확인

---

## 핵심 요약 (5가지)

1. Chaos Vehicle 서스펜션은 PhysX 시절의 레이캐스트(trace = SuspensionMaxRaise+MaxDrop+WheelRadius) 개념을 계승하면서, 동시에 물리 엔진 레벨의 "서스펜션 제약(Constraint, `FSuspensionConstraintPhysicsProxy`)" 경로가 기본으로 켜져 있다. `p.Vehicle.DisableConstraintSuspension`으로 두 경로를 구분해서 디버깅할 수 있다.
2. `Offset`/`WheelRadius` 등은 절대 cm 값이며 컴포넌트 스케일이 자동으로 곱해지지 않는 것으로 강하게 추정된다(공식 문서에 스케일 처리 명시 없음 + Kinematic 본 스케일 강제 1이라는 확인된 엔진 동작 + M1A2에서 겪은 증상 전부 이 가설과 정합적). 스케일을 1이 아닌 값으로 쓸 거라면 이 값들을 수동으로 스케일 비율만큼 보정해야 한다.
3. "바퀴들의 ContactPoint가 붕괴"하는 버그는 커뮤니티에서 동일 증상으로 보고된 바 없지만, ① BoneName 불일치(조용히 무시됨) ② 바퀴 본이 루트 직속 자식이 아님 ③ 루트 본에 물리 바디 없음 — 이 세 가지가 정확히 같은 계열의 "본 계층/매칭 오류"로 유사 증상을 일으킨다는 실제 포럼 사례를 확인했다.
4. 스켈레톤 요구사항은 명확하다: 바퀴는 개별 오브젝트, 중심이 지오메트리 중심, X/Y축 위에 배치, 루트의 직속 자식. 루트 본은 Blender에서 회전/스케일 identity로 export.
5. 탱크/UGV형 다륜 궤도 차량에 대한 "정답"은 커뮤니티에도 없다 — M1A2가 쓰는 스키드 스티어(요 토크 방식)가 사실상 업계 표준 우회책이며, 우리가 이미 그 방식을 쓰고 있는 것은 합리적인 선택이었다.
