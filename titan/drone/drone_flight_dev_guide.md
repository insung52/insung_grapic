# 드론 비행 구동계 개발 문서 (2026-08-27 신규 작성)

멀티로터 비행 역학을 **물리 원칙(로터별 추력 → 토크 → 강체 운동)** 으로 새로 구현한 것에 대한
문서. 기존 `AUAVPawn`의 비행 로직과는 코드/에셋 모두 완전히 분리된 별개 구현이며, 기존 UAV는
전혀 건드리지 않았음(나중에 짐벌/시나리오 기능을 이식할 때 참고용으로 그대로 둠).

**현재 상태**: 구동계 + 수동 조종 완성, 실기 조종 검증 완료(Logitech Extreme 3D Pro).
자율비행은 미구현(11절).

---

## 0. 빠른 시작

1. `/Game/Drone/L_DroneTest` 레벨 열고 Play.
2. 스로틀 레버를 최하단에 두고 시작 → 화면 좌상단 `THR 0%` 확인.
3. 스로틀을 **50% 근처**까지 올리면 뜬다(호버 지점 = 1/추력비 = 50%).

| 조작 | 축/키 | 동작 |
|---|---|---|
| 스로틀 레버 | `Joystick_..._Axis_3` | 전체 출력(컬렉티브) |
| 스틱 전후 | `Axis_1` / `W`·`S` | 피치 기울기 → 전후 가속 |
| 스틱 좌우 | `Axis_0` / `A`·`D` | 롤 기울기 → 좌우 가속 |
| 스틱 트위스트 | `Axis_2` / `Q`·`E` | 제자리 선회(요 각속도) |
| 스로틀(키보드) | `R`·`F` | 레버 없을 때만 동작(증감식) |
| 카메라 전환 | `C` / `Button_2` | 3인칭 ↔ 온보드 |
| 리셋 | `BackSpace` / `Button_6` | 스폰 지점 2m 위, 완전 정지 |

축이 반대로 움직이면 `BP_Drone`의 `Input|Tuning`에서 `bInvert*Axis` 체크박스만 뒤집으면 됨
(리빌드/재시작 불필요, 6.3절).

---

## 1. 왜 새로 만들었나 — 기존 방식의 한계

기존 `AUAVPawn`(`Source/titan_example/Vehicles/UAVPawn.cpp`)의 비행은 **운동학(kinematic)
근사**였다:

- 수평축과 수직축이 완전히 독립된 스칼라 시뮬레이션. 자세(attitude)라는 개념 자체가 없음.
- 이동 방향은 `BeginMissionToTarget`에서 정한 직선 하나로 고정. 순항 중 회전 재계산을 안 해서
  (`UAVPawn.cpp:830`) **롤은 영원히 0, 요는 상승 구간 이후 고정**.
- 기체 기울기는 물리 결과가 아니라 `UpdateBodyTilt()`가 가속도를 각도로 사후 사상한 순수
  코스메틱: `기울기 = -추력(m/s²) × TiltDegreesPerAccel(2.0)`, clamp ±12°.

실제 수치를 넣어보면 문제가 명확했다:

| 상황 | 기존 코드의 기울기 | 실제 드론 |
|---|---|---|
| 순항 정착(60km/h) | 드래그 0.06 × 1667cm/s = 1 m/s² → **2°** | 항력 균형상 **15~25°** |
| 최대 가속(3 m/s²) | **6°** (clamp 12°에 닿지도 않음) | `atan(3/9.81)` = **17°** |
| 선회 | **0°** (롤 자체가 없음) | 뱅크 20~35° |
| 기울기 도달 시간 | `HorizontalAccelRampTimeSeconds` = **1초** | 자세 스텝응답 **0.2~0.3초** |

즉 필요각의 1/5~1/8만, 그것도 5배 느리게 기울었다. 짐벌 카메라가 `BodyMesh`의 `CamPitch` 본에
붙어 있어 이 각도가 그대로 화면에 나오는데, 그 결과 "카메라가 레일 위에서 수평으로 미끄러지는"
느낌이 났다(사용자 리포트: "기울어짐이 너무 느릿느릿하고 이상해").

**기울기 값만 키우는 땜질로는 해결이 안 된다.** 기울기와 가속이 인과관계가 아니라 사후 사상이라,
어떤 값을 넣어도 "기울여서 가는 게 아니라 가니까 기울어 보이는" 위화감이 남는다. 그래서 순서를
뒤집은 새 구현이 필요했다.

---

## 2. 파일 / 에셋 구성

### 2.1 C++ (`Source/titan_example/Drone/`)

| 파일 | 역할 |
|---|---|
| `DroneFlightComponent.h/.cpp` | 비행 역학 전부 — 제어 루프, 믹서, 모터 지연, 공기역학, Chaos 힘 인가 |
| `DronePawn.h/.cpp` | 폰 껍데기 — 콜리전 강체, 메시, 카메라 2개, 입력 바인딩, 디버그 오버레이 |
| `DroneTestGameMode.h/.cpp` | 테스트 전용 게임모드 (순정 `APlayerController` + `ADronePawn`) |

`titan_example.Build.cs`는 수정 불필요(`EnhancedInput`, `PhysicsCore` 이미 의존성에 있음).

### 2.2 에셋 (전부 수동 생성 — 10.3절 참고)

```
/Game/Drone/BP_Drone                     (부모: DronePawn)
/Game/Drone/BP_DroneTestGameMode         (부모: DroneTestGameMode, DefaultPawnClass=BP_Drone)
/Game/Drone/L_DroneTest                  (World Settings GameMode Override=BP_DroneTestGameMode)
/Game/Drone/Input/IA_Drone_Cyclic        (Axis2D)
/Game/Drone/Input/IA_Drone_Yaw           (Axis1D)
/Game/Drone/Input/IA_Drone_Throttle      (Axis1D, 절대값)
/Game/Drone/Input/IA_Drone_ThrottleDelta (Axis1D, 증감)
/Game/Drone/Input/IA_Drone_Reset         (Boolean)
/Game/Drone/Input/IA_Drone_CameraToggle  (Boolean)
/Game/Drone/Input/IMC_DroneTest          (매핑 21개, 6.2절)
```

기체 메시는 기존 UAV 것을 그대로 재사용(`/Game/Vehicles/UAV/SK_UAV`) — 로터 본 `Wing_01~06`이
있어서 로터 배치를 자동으로 읽을 수 있기 때문. 순수 시각 자산이고 옛 UAV 로직과는 연결 없음.

### 2.3 기존 UAV에서 **의도적으로 안 가져온 것**

짐벌 자동정찰, 씬캡쳐 영상피드, 상태 패널 HUD, 탐지 컴포넌트(`UTargetDetectionComponent`),
RTSP 스트림, 시나리오 연동, 지형 회피, 리플리케이션. 구동계 조종감을 다른 시스템 간섭 없이
판단하기 위한 격리이며, 필요해지면 그때 개별적으로 얹는다.

---

## 3. 제어 흐름

기존과 **순서가 정확히 반대**다. 자세가 결과가 아니라 원인이다.

```
스틱 입력 (스로틀/피치/롤/요)
  │
  ├─ 스로틀 ────────────────────────────────► 총추력 지령 (컬렉티브)
  │
  └─ 피치/롤 → 목표 기울기(추력축 방향)
       요    → 목표 요 각속도
             │
             ▼
      [자세 P 루프]  현재 기체 +Z축 → 목표 추력축, 축각 오차 × AttitudeP
             │
             ▼  목표 각속도 (기체 좌표계)
      [각속도 PID]   + 실제 관성텐서 곱하기
             │
             ▼  목표 토크 3축
      [믹서 A⁺]      총추력 + 토크3축 → 로터 6개 개별 추력 (포화 시 자세 우선)
             │
             ▼
      [모터 1차 지연 τ=0.06s]  → 로터별 실제 추력
             │
             ▼
      각 로터 위치에 AddForceAtPosition  +  요 반토크/회전감쇠는 AddTorque
             │
             ▼
      Chaos 강체 적분 (중력·관성·자이로항·충돌 전부 엔진이 처리)
             │
             ▼
      위치 / 자세 → 카메라가 그 자세를 그대로 물려받음
```

**기울어져서 가속하고, 카메라가 기울어 보이는 건 그 자세의 부산물일 뿐이다.**

---

## 4. 물리 모델 상세

### 4.1 부호 규약 (중요)

언리얼 좌표계는 X=전방, Y=우측, Z=상방. 이 구현의 각속도/토크는 전부 각 축에 대한
**오른손 법칙** 기준이다. `FRotator`의 Pitch/Roll은 각각 +Y/+X 축에 대해 부호가 뒤집혀
있으므로(`FRotator::Quaternion()` 유도로 확인) **절대 섞어 쓰지 말 것**.

| 값 | 의미 |
|---|---|
| `Omega.X > 0` | 좌롤 (우측 프로펠러가 올라감) |
| `Omega.Y > 0` | 기수 내림 (nose down) |
| `Omega.Z > 0` | 우선회 |

`FRotator` 쪽 대응(참고): `FQuat(X축, +a)` = 좌롤, `FQuat(Y축, +a)` = 기수 내림,
`FQuat(Z축, +a)` = 우선회. 즉 `FRotator.Roll`/`.Pitch`는 위 규약의 반대 부호.

반면 **조종 입력(`FDroneStickInput`)은 조종사 직관 기준**(+Pitch=기수 올림, +Roll=우롤,
+Yaw=우선회)이며, 변환은 `ComputeDesiredBodyRates()` 안에서 딱 한 번만 한다.

기체 좌표계 델타 회전은 오른쪽에 곱한다(`Attitude * FQuat(...)`) — `USceneComponent::
AddLocalRotation`과 같은 규약. 월드 델타는 왼쪽(`AddWorldRotation`).

### 4.2 자세 제어 — 목표 추력축 방식

오일러각을 쓰지 않는다(짐벌락/변환 부호 사고 방지). 대신 **목표 추력축 벡터**를 만든다:

```
TanMax     = tan(MaxTiltAngleDegrees)
TanForward = -PitchIn × TanMax     // +Pitch(기수 올림) = 뒤로 기울어 감속
TanRight   =  RollIn  × TanMax
목표축(기수방위 기준) = normalize(TanForward, TanRight, 1)
```

`tan`을 쓰는 이유: 수평 가속도가 정확히 `g·tan(기울기)`이므로 **스틱이 곧 가속도 지령**이 된다.
합성 기울기가 `MaxTilt`를 넘으면 두 성분을 비례 축소.

그 다음 현재 기수 방위(요)만 뽑아 목표축을 월드로 옮기고, 현재 기체 +Z축(`BodyUp`)을 그
목표축으로 돌리는 최소 회전을 축각 벡터로 구한다:

```
ErrorAxis  = BodyUp × 목표축(월드)
ErrorAngle = atan2(|ErrorAxis|, BodyUp · 목표축)
ErrorBody  = 기체좌표계로 변환(정규화 축 × ErrorAngle)

DesiredRates.X = clamp(AttitudeP × ErrorBody.X, ±MaxTiltRate)
DesiredRates.Y = clamp(AttitudeP × ErrorBody.Y, ±MaxTiltRate)
DesiredRates.Z = YawIn × MaxYawRate          // 요는 각도가 아니라 각속도 지령
```

요만 각속도 지령인 것은 실제 비행제어기와 동일 — 스틱을 놓으면 그 방위를 유지한다.

### 4.3 각속도 PID

게인 단위를 토크가 아니라 **각가속도**(1/s, 1/s², s)로 잡았다. 최종 토크는 여기에 실제
관성텐서를 곱해서 만들므로, **콜리전 도형이나 기체 제원을 바꿔도 조종 반응 자체는 유지된다.**

```
RateError = DesiredRates - AngularVelocity(기체좌표계)
적분: 믹서 포화 중이면 누적 중단(안티와인드업), ±RateIntegralLimit로 클램프
미분: 오차가 아니라 실측 각속도의 미분에 건다(derivative kick 방지) + 1차 LPF

AngularAccelCmd = RateP·err + RateI·∫err - RateD·d(ω)/dt
Torque = AngularAccelCmd × 실제관성텐서
```

### 4.4 믹서 — 의사역행렬 + 포화 시 자세 우선

배분 행렬 `A` (4×N), `[총추력, τx, τy, τz]ᵀ = A · [로터추력]ᵀ`:

| 행 | 값 | 의미 |
|---|---|---|
| 0 | `1` | 총추력은 합 |
| 1 | `+y_i` | 우측(+Y) 로터가 세게 밀면 우측이 들려서 +X축 회전 |
| 2 | `-x_i` | 전방(+X) 로터가 세게 밀면 기수가 들려서 -Y축 회전 |
| 3 | `-σ_i·κ` | 로터 반토크(로터 각속도가 +Z면 기체가 받는 반토크는 -Z) |

최소노름 해 `A⁺ = Aᵀ(AAᵀ)⁻¹`. `AAᵀ`가 4×4라 `FMatrix::Inverse()`로 바로 뒤집고, 로터 배치가
확정된 시점(`RebuildMixerPseudoInverse`)에 한 번만 계산해둔다.

**포화 처리**가 핵심이다. 로터 추력을 `a_j·(총추력) + b_j(토크분)` 두 항으로 분리해두면,
`0 ≤ T_j ≤ MaxThrust`를 만족시키는 총추력 구간을 해석적으로 구할 수 있다:

- 구간이 존재하면 → 총추력을 그 구간으로 클램프(**토크=자세를 지키고 총추력을 양보**)
- 요구 토크 자체가 기체 능력을 넘으면 → 성립하는 최대 토크 배율을 이분법 12회로 찾아 토크를 깎음

실제 비행제어기의 airmode/추력 우선순위 처리와 같은 발상이고, **급기동 중에 고도가 살짝
빠지는 그 느낌이 여기서 나온다.**

### 4.5 모터 지연

```
MotorAlpha = 1 - exp(-Dt / MotorTimeConstantSeconds)
T_i += (T_cmd_i - T_i) × MotorAlpha
```

지수 형태로 풀어서 물리 스텝 크기에 관계없이 시상수가 정확하다. **"빠릿함"을 결정하는 가장
중요한 값 하나** — 작을수록 즉각적, 크면 물컹하다.

### 4.6 Chaos 연동 — 힘/토크 인가

적분과 접촉은 전부 언리얼(Chaos) 강체가 담당한다. 이 컴포넌트가 하는 일은 "매 물리 스텝마다
로터 N개가 각각 얼마의 힘을 어디에 주는지" 계산해서 인가하는 것까지다.

```cpp
// 롤/피치 토크는 따로 계산하지 않는다. 로터 위치에 힘을 주면 r×F가 저절로 생긴다.
for (each rotor)
    BodyInstance->AddForceAtPosition(추력방향 × T_i × 100, 로터_월드위치, false);

// 프로펠러 항력 반토크는 한 점에 작용하는 힘이 아니라서 유일하게 직접 토크로 준다.
BodyInstance->AddTorqueInRadians((요반토크 + 회전공기저항) × 10000, false, false);
```

- 등록은 매 프레임 `BodyInstance->AddCustomPhysics(OnCalculateCustomPhysics)`.
  서브스테핑이 켜져 있으면 서브스텝마다, 꺼져 있으면 프레임마다 콜백이 돈다(10.2절).
- 접지 상태로 강체가 잠들면 콜백이 안 돌아 스로틀을 올려도 안 뜨므로, `TickFlight`에서
  `IsInstanceAwake()` 확인 후 `WakeInstance()`.
- **Chaos의 `LinearDamping`/`AngularDamping`은 0으로 끈다.** 저항이 두 군데서 나오면
  튜닝값이 뜻하는 물리량과 실제 거동이 어긋나기 때문. 저항은 오직 4.7절 모델에서만.
- 중력·관성·자이로항(ω×Iω)·충돌은 전부 Chaos가 처리한다.

**단위 변환**: 컴포넌트 내부 계산은 전부 SI(m, kg, N, N·m, rad, s). 언리얼 물리는 kg·cm
단위계라 힘은 ×100, 토크는 ×10000(= ×100 힘 × ×100 거리), 관성은 kg·m² ↔ kg·cm² ×10000.

**질량/관성**: `SetMassOverrideInKg`로 질량을 강제하고, `bMatchInertiaToSpec`이 켜져 있으면
콜리전 도형에서 나온 관성텐서를 `InertiaTensorScale`로 `InertiaKgM2`에 맞게 보정한 뒤 실제
적용값을 로그로 찍는다(현재 이 보정이 목표에 못 미침 — 10.1절).

### 4.7 공기역학

- **항력**: 기체 좌표계 축별 2차 항력. `F_i = -0.5·ρ·CdA_i·|v_i|·v_i`.
  대지속도가 아니라 **대기속도**(속도 − `WindVelocityMS`) 기준이라, 바람 값만 넣으면 자동으로
  기체가 밀리고 제자리 유지에 기울임이 필요해진다.
  수직 성분(`CdA.Z=0.30`)이 큰 이유는 로터 디스크가 하강 시 큰 저항을 만들기 때문(실제
  멀티로터의 하강 속도 제한 원인).
- **회전 공기저항**: `τ_i = -C_i·|ω_i|·ω_i`. 스틱을 놓으면 회전이 스스로 멎게 하는 항.

### 4.8 스로틀

컬렉티브(전체 출력) — 스틱이 곧 총추력이다. 고도 유지 보정 같은 건 없다.
**호버 지점 = 1/추력비**(기본 2.0 → 50%).

`bThrottleTiltCompensation`이 켜져 있으면 기울인 만큼 줄어드는 수직 성분을 `1/cos(기울기)`로
되돌린다(cos는 0.35로 하한 클램프, 총추력은 물리 한계 초과 금지). DJI/Betaflight 등 실제
비행제어기가 전부 하는 보정이라 기본 켜둠. 끄면 순수 수동 스로틀.

---

## 5. 로터 자동 인식

암 길이나 배치를 코드에 박지 않는다. `InitializeRotorsFromMesh()`가 `BeginPlay`에서:

1. 메시 본 중 접두사 `Wing_`으로 시작하는 것을 전부 수집
2. 월드 → 액터 로컬로 되돌림(메시 컴포넌트의 오프셋/회전/스케일이 자동 반영 → 디자인팀이
   메시를 옮기거나 키워도 물리가 따라감)
3. `bRecenterRotorsOnCentroid`면 링 중심을 원점으로(메시 원점이 어긋나 있어도 호버가 한쪽으로
   안 기울게)
4. **방위각 순으로 정렬한 뒤 회전방향을 번갈아 배정** → 호버 중 총 반토크가 정확히 0,
   요 조작은 한쪽 방향 로터들만 더 밀어서 만듦
5. 실패(본 4개 미만, 반경 2cm 미만) 시 `FallbackRotorCount`/`FallbackArmLengthMeters`로 만든
   정다각형 배치로 폴백

`SK_UAV` 기준 실측 로그:

```
[Drone] 로터 6개를 본에서 인식(최대 암 길이 0.291m).
```

`BP_Drone`의 콜리전 박스도 `bAutoSizeCollisionFromRotors`가 켜져 있으면 이 반경에 맞춰
`BeginPlay`에서 자동으로 크기가 잡힌다(반드시 `SetSimulatedBody` 전에 — 도형이 바뀌면 관성이
다시 계산되므로).

프로펠러 시각 회전은 `T = k·ω²`를 역으로 풀어 `ω = ωmax·√(T/Tmax)`로 로터마다 따로 구한다.
**추력이 로터마다 다르므로 회전 속도도 각각 달라서, 기동 중 어느 쪽이 감기고 어느 쪽이
풀리는지가 눈에 보인다.** 애님 블루프린트 없이 `UPoseableMeshComponent`로 본을 직접 돌린다.

---

## 6. 조종 입력

### 6.1 구조

조이스틱 하나의 4축이면 끝난다(실제 RC 송신기와 동일한 채널 구성). 입력 라우팅은 폰이
직접 하고, 컨트롤러 쪽에는 아무것도 없다(순정 `APlayerController`).

IMC 등록은 `EnsureMappingContextApplied()` 한 곳으로 모아서 `NotifyControllerChanged`와
`SetupPlayerInputComponent` **양쪽에서** 부른다 — 초기 빙의 시 둘의 호출 순서가 상황(게임모드
스폰/수동 배치/리스타트)에 따라 달라져서, 한쪽만 믿으면 조용히 아무것도 안 붙는 경우가 있다.
실패 시 어느 단계에서 왜 실패했는지 전부 로그로 남긴다:

```
[Drone][NotifyControllerChanged] IMC 등록 완료 — 'IMC_DroneTest' 매핑 21개. (Cyclic=... )
[Drone][SetupPlayerInputComponent] IMC 등록 보류 — 아직 PlayerController에 빙의되지 않음(...)
[Drone][...] IMC 등록 실패 — PlayerController에 LocalPlayer가 없음 / 서브시스템 없음 / null
```

`DroneMappingContext`가 비어 있으면 경로(`/Game/Drone/Input/IMC_DroneTest`)로 런타임 재로드를
시도한다 — IMC를 지웠다 같은 이름으로 새로 만들어도 동작한다.

### 6.2 `IMC_DroneTest` 매핑 21개

**IA_Drone_Cyclic** (Axis2D, X=롤 Y=피치)

| 키 | 모디파이어 |
|---|---|
| `Joystick_Extreme_3D_pro_Axis_0` | — |
| `Joystick_Extreme_3D_pro_Axis_1` | Swizzle(YXZ) → Negate |
| `Gamepad_Right2D` | — |
| `D` | — |
| `A` | Negate |
| `W` | Swizzle(YXZ) |
| `S` | Swizzle(YXZ) → Negate |

**IA_Drone_Yaw** — `Axis_2`(—), `Gamepad_LeftX`(—), `E`(—), `Q`(Negate)
**IA_Drone_Throttle** — `Axis_3`(—)
**IA_Drone_ThrottleDelta** — `Gamepad_LeftY`(—), `R`(—), `F`(Negate)
**IA_Drone_Reset** — `BackSpace`, `Gamepad_FaceButton_Top`, `Joystick_..._Button_6`
**IA_Drone_CameraToggle** — `C`, `Gamepad_FaceButton_Right`, `Joystick_..._Button_2`

`Axis_1`에 Negate를 붙이는 이유: 조이스틱은 앞으로 밀 때 −1이 들어오는데 게임패드/키보드(W)는
+1이라, **IMC 단계에서 기기 차이를 흡수**해서 `bInvertPitchAxis` 하나로 양쪽을 다 커버하기 위함.

Extreme 3D Pro 축 대응: `Axis_0`=스틱 좌우, `Axis_1`=스틱 전후, `Axis_2`=트위스트,
`Axis_3`=스로틀 레버.

### 6.3 기기 차이 흡수 (`BP_Drone` → `Input|Tuning`)

| 증상 | 프로퍼티 | 기본값 |
|---|---|---|
| 스틱 앞으로 미는데 뒤로 감 | `bInvertPitchAxis` | **true** |
| 좌우 반대 | `bInvertRollAxis` | false |
| 트위스트 반대 | `bInvertYawAxis` | false |
| 레버 올리면 출력 내려감 | `bInvertThrottleAxis` | false |
| 레버가 0~1로 들어옴 | `bThrottleAxisIsBipolar` | true(−1~1) |
| 중립에서 미세하게 흔들림 | `StickDeadzone` | 0.06 |
| 키보드 스로틀 속도 | `KeyboardThrottleRatePerSecond` | 0.6 /초 |

스로틀은 **절대 축이 한 번이라도 들어오면 그때부터 래치**되어 키보드 누적을 무시한다
(레버가 정확히 중앙 0을 지나가는 순간에 값이 튀지 않게). 데드존은 롤/피치/요와
키보드 스로틀 증감에 적용되고, 절대 스로틀에는 적용되지 않는다.

> ⚠️ 스로틀 극성이 반대면 레버가 쉬는 위치에서 출력 100%로 읽혀 **시작하자마자 튀어 오른다.**
> 첫 실행은 반드시 레버 최하단에서 `THR 0%` 확인하고 시작할 것.

---

## 7. 파라미터 튜닝 가이드

전부 `BP_Drone`의 디테일 패널에서 조정 가능(리빌드 불필요).

### 7.1 기체 제원 (`Drone|Airframe`)

| 프로퍼티 | 기본값 | 설명 |
|---|---|---|
| `MassKg` | 4.5 | 강체에 강제되는 실제 질량 |
| `InertiaKgM2` | (0.08, 0.08, 0.15) | 목표 관성텐서. X=롤 Y=피치 Z=요 |
| `bMatchInertiaToSpec` | true | 콜리전 도형 관성을 위 값에 맞게 보정 시도 |
| `ThrustToWeightRatio` | 2.0 | 최대 총추력/무게. 호버 스로틀 = 1/이 값 |
| `MotorTimeConstantSeconds` | 0.06 | **빠릿함의 핵심.** 작을수록 즉각적 |
| `YawTorqueCoefficient` | 0.016 | 로터 반토크 계수 κ(m). 요 힘 |
| `DragAreaCdA` | (0.12, 0.14, 0.30) | 축별 Cd·A(m²). 최고속도/감속감 |
| `AirDensityKgM3` | 1.225 | |
| `AngularDragCoefficient` | (0.03, 0.03, 0.02) | 회전 감쇠. 스틱 놓았을 때 멎는 속도 |
| `WindVelocityMS` | (0,0,0) | 월드 바람. 넣으면 자동으로 밀림 |

### 7.2 조종 특성 (`Drone|Control`)

| 프로퍼티 | 기본값 | 설명 |
|---|---|---|
| `MaxTiltAngleDegrees` | 35 | 최대 기울기. 수평 가속도 = g·tan(이 각) ≈ 6.9 m/s² |
| `MaxYawRateDegPerSec` | 120 | 선회 속도 |
| `AttitudeP` | 8.0 | 자세 오차 → 각속도 지령 게인(1/s). 목표 기울기로 붙는 속도 |
| `MaxTiltRateDegPerSec` | 300 | 롤/피치 각속도 상한 |
| `RateP` | (25, 25, 20) | 각속도 P (1/s) |
| `RateI` | (6, 6, 4) | 각속도 I (1/s²) |
| `RateD` | (0.35, 0.35, 0.05) | 각속도 D (s) |
| `RateDerivativeFilterSeconds` | 0.02 | D항 LPF. 제어 루프가 60Hz라 넉넉하게 |
| `RateIntegralLimit` | 2.0 | I항 누적 상한 |
| `bThrottleTiltCompensation` | true | 기울여도 고도가 덜 빠지게 |
| `CyclicExpo` / `YawExpo` | 0.3 / 0.2 | 스틱 엑스포. 중앙 근처 완만 |

### 7.3 튜닝 순서 (권장)

대부분 이 4개만 만지면 잡힌다:

1. **`MotorTimeConstantSeconds`** — 전체 반응의 "무게감". 물컹하면 낮추고 너무 신경질적이면 올림
2. **`RateP`** — 각속도 추종. 낮으면 흐물거리고 너무 높으면 진동(고주파 떨림)
3. **`AttitudeP`** — 스틱을 꺾었을 때 목표 기울기까지 붙는 속도
4. **`MaxTiltAngleDegrees`** — 최대 가속도와 최고 속도(항력 균형)를 동시에 좌우

진동이 생기면 `RateP`를 내리거나 `RateD`를 조금 올린다. 저속에서 좌우로 스멀스멀 흐르면
`RateI`를 올린다.

---

## 8. 디버그 오버레이

`BP_Drone`의 `bShowFlightDebug`(기본 켜짐)로 화면 좌상단에 4줄 출력.

```
THR  50%  (호버 50%)   TILT 12.3°   ALT   18.4m
SPD  31.2km/h   V/S  +0.4m/s   RATE p   +12 q   -84 r    +0 °/s
ROTOR N:  9.2  11.4  12.1  10.8   8.9   9.6   (최대 14.7/개)
I (0.044, 0.044, 0.074) kg·m²   [믹서 포화 — 자세 우선, 총추력 양보 중]
```

| 항목 | 읽는 법 |
|---|---|
| `THR` | 컬렉티브. 호버 지점이 괄호로 같이 나옴 |
| `TILT` | 수직축 기준 총 기울기 |
| `RATE p/q/r` | 각속도(4.1절 부호 규약). q가 +면 기수 내림 |
| `ROTOR N` | 로터별 실제 추력(뉴턴). 최대치에 붙어 있으면 포화 |
| 4행 | Chaos가 실제로 쓰는 관성텐서 + 믹서 포화 여부 |

`bDrawRotorThrustVectors`를 켜면 로터별 추력이 기체 위에 노란 3D 선(길이 = 추력 비율)으로
그려진다 — 어느 로터가 얼마나 밀고 있는지 한눈에 보인다.

---

## 9. 테스트 레벨 `L_DroneTest`

바닥은 원점 중심 약 ±45m. 드론 스폰 = 원점, 기수 +X. 아웃라이너 `DroneCourse` 폴더에
박스 29개가 6그룹으로 정리되어 있다.

| 그룹 | 내용 | 용도 |
|---|---|---|
| `Pads` (3) | 높이 0.8 / 2 / 3.5m 단 | 콜리전 착지 테스트 |
| `Gates` (2세트) | 폭 9m × 높이 5m / 7m 문틀 | 통과 비행, 고도·좌우 정밀도 |
| `Slalom` (5) | 높이 8~13m 기둥 지그재그 | 롤 기동, 뱅크각 감각 |
| `Steps` (5) | 2/6/10/14/18m 계단탑 | 고도 감각 기준자 (HUD `ALT`와 대조) |
| `Scatter` (8) | 2m 큐브 산개 | 속도·거리감 |
| `Landmarks` (2) | 16m / 25m 대형 박스 | 원거리 위치 기준 |

메시는 `/Game/LevelPrototyping/Meshes/SM_Cube`(100cm, 피벗이 최소 모서리 — 크기 `(W,D,H)`
박스를 `(cx,cy)` 중심으로 지면에 놓으려면 `location = (cx-W/2, cy-D/2, 0)`, `scale = (W,D,H)/100`).

**조명 미비**: 레벨에 `DirectionalLight` 하나뿐이고 `SkyLight`/`SkyAtmosphere`가 없어서
그림자 진 면이 새까맣게 나온다. 색깔 머티리얼도 프로젝트에 `MI_Solid_Blue`/`MI_Solid_Yellow`
둘뿐이라 프로토타입 그리드 3종과 섞어 썼다. 둘 다 미해결.

---

## 10. 알려진 이슈 / 제약

### 10.1 관성텐서 보정이 목표에 못 미침

```
[Drone] 질량 4.50kg, 관성텐서 실제 적용값 (0.0442, 0.0442, 0.0735) kg·m² (목표 0.0800, 0.0800, 0.1500).
```

4.5kg / 58×58×24cm 박스의 자연 관성이 약 (0.149, 0.149, 0.25)인데, `목표²/자연`이 관측값과
맞아떨어진다 — **`InertiaTensorScale`이 한 번이 아니라 두 번 곱해진 것으로 보임**
(`UpdateMassProperties()`가 명시적 호출 외에 한 번 더 도는 듯).

**조종감 영향은 작다.** PID 게인이 각가속도 단위이고 컨트롤러가 실제 관성값을 읽어 토크를
만들기 때문에 지령에 대한 반응 속도는 설계대로 나온다. 달라지는 건 토크 포화 여유뿐이라
스펙보다 약간 더 민첩하다. 스펙대로 맞추고 싶으면 콜리전 박스 크기를 줄이는 게 가장 확실한
레버.

### 10.2 제어 루프가 60Hz

이 프로젝트는 물리 서브스테핑이 꺼져 있고 `t.MaxFPS=60`이다(`DefaultEngine.ini` 7~15행,
UGV 거동 편차 때문에 의도적으로 설정된 것). 그래서 커스텀 물리 콜백이 프레임당 한 번,
즉 60Hz로 돈다. 각도 모드 비행엔 충분하지만 실제 비행제어기(수백~수천 Hz)보다는 느리다.

코드는 서브스테핑이 켜지면 자동으로 서브스텝마다 돌게 되어 있으나, **켜면 UGV Chaos 차량
거동까지 같이 바뀌므로** 지금은 안 건드림.

### 10.3 에셋은 MCP로 만들지 말 것

`IMC_DroneTest`를 unreal-mcp로 생성했을 때 문제가 있었다: `get_properties`로는 매핑 21개가
정상으로 보이고 디스크 `.uasset`에도 키 이름이 전부 들어있는데, **에디터의 에셋 편집 창에는
계속 비어 보였고**(에디터 재시작 후에도), 반대로 사용자가 에디터에서 추가한 매핑은 MCP 읽기에
안 나타났다. 같은 에디터 프로세스인데 객체 뷰가 갈렸다. 원인 미규명.

**결론: IMC/IA/레벨 등 새 에셋은 수동으로 생성한다.** 기존 에셋의 프로퍼티 읽기/수정,
레벨에 액터 배치는 MCP로 해도 문제없다(9절 박스 29개는 MCP로 배치했고 정상).

### 10.4 기타

- 리플리케이션 미구현. 단일 프로세스 전용.
- 프로펠러 사운드 없음.
- 짐벌 카메라 없음 — 온보드 카메라가 기체에 고정되어 자세를 그대로 물려받는다(의도. 실제
  드론 영상의 "이동 방향으로 기울어지는" 느낌이 여기서 나옴). 안정화가 필요하면 별도 구현.

---

## 11. 다음 단계 — 자율비행

구동계가 끝났으므로 껍데기만 얹으면 된다:

```
목표위치 → 위치 P제어 → 목표속도(클램프) → 속도 PI → 목표 가속도 → 목표 경사각
                                                    → 수동 조종과 동일한 입구(SetStickInput)로 투입
```

- `BeginMissionToTarget` / `EnemyCube` 태그 / `DT_ScenarioSteps` 인터페이스는 기존 UAV 것을
  그대로 재사용 가능.
- 지형 회피는 라인트레이스 결과를 "고도 명령 하한"으로 바꿔 넣으면 된다 — 기존 UAV처럼
  추력에 직접 더하던 방식보다 훨씬 단순해진다.
- 짐벌/영상피드/탐지/RTSP는 기존 `AUAVPawn`에서 필요한 것만 골라 이식.

기존 UAV를 이 구동계로 교체할 때는 전시 일정 리스크를 감안해, 자율비행이 완성될 때까지
구 경로를 살려두는 편이 안전하다.

---

## 12. 작업 이력

| 날짜 | 내용 |
|---|---|
| 2026-08-27 | 기존 UAV 비행 로직 분석, 카메라 기울기 위화감 원인 규명(1절) |
| 2026-08-27 | 6로터 강체 모델 신규 구현. 처음엔 자체 6-DOF 적분기 |
| 2026-08-27 | **Chaos 강체로 전환** — 자체 적분기는 콜리전이 없어 라인트레이스 1발로만 지면을 알았고, 경사면·구조물 착지/장애물 충돌이 불가능했음. 물리 모델(로터 추력/믹서/PID/항력)은 그대로 두고 적분·접촉만 엔진에 넘김 |
| 2026-08-27 | 조종 입력(IMC/IA), 테스트 레벨/게임모드/BP 구성, 실기 조종 검증 완료 |
| 2026-08-27 | IMC 등록 이중화 + 진단 로그 추가(6.1절), 테스트 코스 박스 29개 배치(9절) |
