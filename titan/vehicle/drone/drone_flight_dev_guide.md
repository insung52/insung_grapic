# 드론(UAV) 비행 시스템 레퍼런스

2026-09-05 / 완료 / `ADronePawn`이 구 `AUAVPawn`/`BP_UAV`를 대체 — 로터별 물리 비행 + 자율비행 + 교전 관측 이동 + 짐벌 + 사운드 + 바람 + 탐지단계 + 시나리오 + 리플리케이션 전부 구현·실동작 확인됨.

> **이 문서는 "드론이 지금 어떻게 동작하는가"를 다루는 에버그린 레퍼런스다**(`CLAUDE.md`
> guide/ 갱신 규칙 참고 — 드론 시스템 동작이 바뀌면 여기를 같이 고칠 것). 시간순 작업 기록은
> 같은 폴더의 날짜 접두 devlog를 볼 것:
> - `2026-09-01_drone_replaces_bp_uav.md` — 자율비행~BP_UAV 대체까지의 작업 경과·함정
> - 리플리케이션 설계 배경: `replication/2026-09-01_drone_client_authoritative.md`

멀티로터 비행 역학을 **물리 원칙(로터별 추력 → 토크 → 강체 운동)** 으로 새로 구현한 것.
기존 `AUAVPawn`의 비행 로직과는 코드/에셋 모두 완전히 분리된 별개 구현이다.

**현재 상태**: 구동계·수동 조종·자율비행·짐벌·프로펠러 사운드·바람 반응·단계별 탐지·시나리오
연동·리플리케이션 전부 구현 완료. 실기 조종 검증 완료(Logitech Extreme 3D Pro), 단일 프로세스
시나리오 검증 완료. **2프로세스(2대 PC) 실환경 검증만 남음**(10.5절).

구 `AUAVPawn`/`BP_UAV`는 아직 코드에 남아 있다 — 시나리오 연동 지점들이 "드론 우선, 없으면 구
UAV" 폴백 구조라 둘이 공존한다. 2프로세스 검증이 끝나면 폴백과 구 클래스를 함께 걷어낸다.

---

## 0. 빠른 시작

### 0.1 수동 조종만 보고 싶을 때

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
| 짐벌 조작 | `IA_Drone_GimbalLook` | 짐벌 팬/틸트(12절) |
| 카메라 전환 | `C` / `Button_2` | 3인칭 → 온보드 → 짐벌 순환 |
| 리셋 | `BackSpace` / `Button_6` | 스폰 지점 2m 위, 완전 정지 |

축이 반대로 움직이면 `BP_Drone`의 `Input|Tuning`에서 `bInvert*Axis` 체크박스만 뒤집으면 됨
(리빌드/재시작 불필요, 6.3절).

### 0.2 자율비행을 보고 싶을 때

레벨에 `ADroneFlightPath`를 하나 배치해 스플라인을 그리고 `PathId`를 정한 뒤, PIE 콘솔(`~`)에서:

```
DroneListPaths          레벨에 있는 경로 목록 출력
DroneFollowPath uavpath  해당 PathId 경로로 비행 시작(5초간 상승 후 경로 진입)
DroneStopPath           자율비행 해제 → 즉시 수동 (스로틀 안 잡고 있으면 떨어짐)
```

### 0.3 전시 시나리오 전체를 보고 싶을 때

`New_kadex_0811`에서 콘솔에 `BeginScenario`. 드론이 `uavpath`를 타고 이륙 → 목표지역 도착 →
낙하산 자동 정찰·줌인 → **그 관측 성공이 UGV 출발 트리거**가 된다(13절).

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
| `DroneFlightComponent.h/.cpp` | 비행 역학 전부 — 제어 루프, 믹서, 모터 지연, 공기역학, Chaos 힘 인가. 단위 상수 `namespace DroneUnits`도 여기 |
| `DroneAutopilotComponent.h/.cpp` | 자율비행 — Pure Pursuit + 제동 곡선. **스틱 입력만 만들어낸다**(11절) |
| `DroneFlightPath.h/.cpp` | 레벨에 배치하는 스플라인 경로 액터(`PathId`로 지목) |
| `DronePropAudioComponent.h/.cpp` | 프로펠러 사운드 — 3가지 모드, 우선순위 보호(14절) |
| `DronePawn.h/.cpp` | 폰 — 콜리전 강체, 메시, 카메라 3개, 짐벌, 탐지, 입력, 콘솔 명령, 리플리케이션 |
| `DroneTestGameMode.h/.cpp` | 테스트 전용 게임모드 (순정 `APlayerController` + `ADronePawn`) |

`titan_example.Build.cs`는 수정 불필요(`EnhancedInput`, `PhysicsCore` 이미 의존성에 있음).

> ⚠️ **새 `Drone/*.cpp`를 추가할 때 익명 네임스페이스에 상수를 두지 말 것.** UE 유니티 빌드가
> 여러 `.cpp`를 한 번역 단위로 합치면서 익명 네임스페이스도 하나로 합쳐져 재정의 오류(C2086)가
> 난다. 실제로 `DroneFlightComponent.cpp`와 `DroneAutopilotComponent.cpp`가 각자 `CmPerMeter`를
> 선언했다가 터졌고, `DroneFlightComponent.h`의 `namespace DroneUnits`로 통합해 해결했다.
> 단위 상수가 필요하면 `using namespace DroneUnits;`를 쓸 것.

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
/Game/Drone/Input/IA_Drone_GimbalLook    (Axis2D, 짐벌 팬/틸트)
/Game/Drone/Input/IMC_DroneTest          (6.2절)
```

기체 메시는 기존 UAV 것을 그대로 재사용(`/Game/Vehicles/UAV/SK_UAV`) — 로터 본 `Wing_01~06`과
짐벌 본 `CamYaw`/`CamPitch`가 있어서 로터 배치와 짐벌 축을 자동으로 읽을 수 있기 때문.

`BP_Drone`에는 짐벌 위치에 `UCineCameraComponent`를 **디자이너가 직접 배치**해 두고, 폰의
`GimbalCineCameraRef`(FComponentReference)로 그걸 지목한다 — 이 프로젝트의 카메라 공통 패턴
(RCWS/QuadCam/구 UAV 전부 동일: CineCamera는 렌즈 참조용, 실제 캡쳐는 코드가 만드는
`USceneCaptureComponent2D`). 자세한 배경은 `camera_pipeline/` 참고.

### 2.3 실사용 레벨(`New_kadex_0811`) 배치

`BP_Drone` 1대 + `ADroneFlightPath`(PathId `uavpath`) + 낙하산 액터. 낙하산은 **PlayerStart로
스폰되는 게 아니라 레벨에 직접 배치**돼 있고, `BP_Drone` 인스턴스의 `ParachuteActor`에 그걸
꽂아줘야 한다 — 비어 있으면 정찰 단계가 아예 시작되지 않는다(로그로 1회 경고, 10.4절).

---

## 3. 제어 흐름

기존과 **순서가 정확히 반대**다. 자세가 결과가 아니라 원인이다.

```
스틱 입력 (스로틀/피치/롤/요)     ← 사람 조종 또는 UDroneAutopilotComponent (11절)
  │                                  둘 다 이 한 입구로만 들어온다
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

### 6.2 `IMC_DroneTest` 매핑

(아래는 최초 구성 기준. 실제 등록된 매핑 개수는 `EnsureMappingContextApplied()`가 로그에
찍으므로 그걸 보는 게 정확하다 — 이후 짐벌 조작 IA가 추가됐고, 사용자가 에디터에서 직접
편집하는 에셋이다.)

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
**IA_Drone_GimbalLook** (Axis2D, X=팬 Y=틸트) — 짐벌 조작. 전시 세팅에서는 이 IMC가 아니라
자체방호축 조이스틱 경로(`titan_examplePlayerController::ApplyUAVGimbalPanTiltInput`)로 들어온다.

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
| `MaxTiltAngleDegrees` | 35 (**BP_Drone에서 60으로 올려둠**) | 최대 기울기. 수평 가속도 = g·tan(이 각) — 35°=6.9, 60°=17.0 m/s² |
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

> 위 값들은 **조종감(기체가 지령에 얼마나 빨리 반응하는가)** 만 정한다. "자율비행이 너무
> 험하다 / 진자처럼 좌우로 롤한다 / 가감속이 급하다"는 여기가 아니라 오토파일럿 쪽 문제다
> — 11.5절 무게감 3노브를 볼 것.

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

> **전시/촬영 때 끄는 법**: 둘 다 `BP_Drone` 디테일 패널 `Debug` 카테고리의 체크박스다.
> `bShowFlightDebug`를 끄면 화면 좌상단 텍스트(`AUDIO 보이스 1개`, `AUTO 경로 추종`,
> `VIEW Chase` 줄 포함)가 전부 사라지고, `bDrawRotorThrustVectors`를 끄면 노란 추력 선이
> 사라진다. 둘 다 기본값이 켜짐이라 명시적으로 꺼야 한다.

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

### 10.4 낙하산 액터를 안 꽂으면 정찰이 조용히 안 돈다

`BP_Drone` 인스턴스의 `ParachuteActor`가 비어 있으면 `BeginGimbalRecon()`이 아무 일도 안 하고,
UGV도 영원히 출발하지 않는다(그 관측이 출발 트리거이므로). 원인을 못 찾는 걸 막으려고 1회성
경고를 넣어뒀다:

```
[Drone] ParachuteActor가 비어 있어 짐벌 정찰을 시작할 수 없습니다 — 레벨 인스턴스에서 지정할 것.
```

낙하산은 PlayerStart 스폰이 아니라 **레벨에 직접 배치된 액터**라, 레벨을 새로 만들거나 낙하산을
교체하면 이 참조가 끊긴다.

### 10.5 2프로세스 실환경 미검증

리플리케이션(15절)은 단일 프로세스와 PIE 2클라이언트까지만 확인했다. 실제 2대 PC(서버=UGV축,
클라=자체방호축) 환경에서 트랜스폼 동기화 품질, 소유권(`SetOwner`) 확보 타이밍, 보간 자연스러움
검증이 남아 있다.

### 10.6 프로펠러 왜건휠 현상

형광등 아래 선풍기처럼 프로펠러가 느리게/거꾸로 도는 것처럼 보이는 스트로보 현상. 실제 해결은
고회전 시 블러 디스크 메시로 교체하는 것인데 아트 에셋이 필요해서 보류.

### 10.7 경로 고도가 부족하다

교전 관측(16절)이 요구하는 부감 -45~-60°를 실제 경로가 못 채우고 있다(실측 -30~-40°대). 그러면
드론이 상시 "차선" 모드로 돌고, 필요 화각도 90°에 포화해 판정이 불안정해진다. 스플라인을 다시
그릴 때 기준은 **교전 반경 R에 대해 대상보다 R × 1.0~1.25 위**(150m 폭 교전이면 R≈75m이니
95~110m 위, 그때 수평 거리 55~95m).

### 10.8 도주 시작 장면이 화면에 잘 안 보인다

시나리오 4단계("3분대 도망 시작")의 프레이밍 대상이 33개(UGV+아군 전원+적군)라 화각 84°가 되어
도주하는 적이 점으로 보인다. 표를 그대로 구현한 결과이므로, 보여주려면 그 단계만 대상을 좁히는
별도 결정이 필요하다.

### 10.9 기타

- 지형 회피 미구현. 스플라인을 지형 위로 그리는 것으로 대체하고 있다 — 교전 관측 이동이
  자유비행이 아니라 스플라인 위로만 움직이는 이유이기도 하다(16절).
- 짐벌 안정화(기체 자세 상쇄) 미적용 — 짐벌 본은 기체 자세를 물려받는다. 온보드 카메라도
  마찬가지이며, 실제 드론 영상의 "이동 방향으로 기울어지는" 느낌이 여기서 나오므로 의도된 것.

---

## 11. 자율비행

### 11.1 설계 원칙 — 위치를 직접 쓰지 않는다

스플라인 좌표를 `SetActorLocation`으로 밀어넣으면 우리가 만든 물리가 통째로 무의미해진다
(기울지도, 관성도 없는 구 UAV의 "레일 위 미끄러짐"으로 되돌아감). 그래서
`UDroneAutopilotComponent`는 **사람 조종사와 똑같은 4채널 스틱 입력만 만들어내고**,
`UDroneFlightComponent`가 그걸 평소처럼 처리한다. 기울어짐·모터 지연·믹서 포화·항력이 전부
살아있는 채로 경로를 따라가므로 "자연스러운 스로틀/회전"을 따로 만들 필요가 없다.

```
스플라인 → 당근점(Pure Pursuit) → 방향
         → 제동 곡선(거버너)     → 속도 크기
                                   ↓
                    목표 속도 → 속도 PI → 목표 가속도 → 목표 기울기
                                   ↓
                    ComputeStickInput() → 수동과 같은 입구 → 물리
```

### 11.2 상태 기계

| 상태 | 하는 일 |
|---|---|
| `Idle` | 자율비행 꺼짐, 수동 조종 |
| `Takeoff` | 스플라인 첫 포인트로 상승. `TakeoffDurationSeconds`(5초)에서 속도 상한을 역산하므로 스플라인을 20m로 그리든 30m로 그리든 비슷한 시간이 걸린다 |
| `Following` | 경로 추종 |
| `Arrived` | 경로 끝 도달. `bHoverAtEnd`면 그 자리 정지비행 |
| `Observing` | **교전 관측** — 경로 위에서 폰이 지시한 관측 지점을 유지/이동(16절) |

`Arrived` 상태에서 폰이 교전 프레이밍을 시작하면 `Observing`으로 넘어간다. 반대로 이륙/경로
추종 중에는 넘어가지 않는다 — 시나리오가 `MoveDroneToPath`로 보낸 이동이 다음 틱에 취소되면
2·3차 전투지 추격이 통째로 안 먹는다.

⚠ **이미 `Observing` 중에 경로가 바뀌면 경로 주행을 하지 않고 레일만 갈아탄다.** `uavpath2`는
"시작점=트럭, 끝점=낙하산"이라 끝까지 날아가면 방금 떠나온 자리로 되돌아간다(실측: 24초간
역주행하는 동안 1차 전투가 끝났다). 교전을 따라가는 경로는 "타고 갈 길"이 아니라 "미끄러질
레일"이다.

**스로틀 스풀업**(`TakeoffSpoolUpSeconds` 1.2초): 이게 없으면 engage 순간 스로틀 지령이 0→75%로
한 프레임에 튀어서 기체가 "팍" 튀어오른다. 이 시간에 걸쳐 지령을 끌어올리면 프로펠러가 점점
빨라지다가 추력이 무게를 넘는 순간 스르륵 뜨는 실제 이륙 그림이 나온다. 지상 아이들 회전은
넣지 않았다 — 실제 드론은 배터리 때문에 뜨기 직전에야 스풀업한다.

시작 스틱값은 engage 시점 값을 이어받는다. 0에서 다시 올리면 **공중에서 engage하는 순간
추락**하기 때문.

### 11.3 유도 — Pure Pursuit

가장 가까운 점이 아니라 전방주시거리만큼 앞선 보간점(당근)을 쫓는다. 정점 도달 시 목표가 한
프레임에 튀는 이산 전환이 없어져 조향 진동이 사라진다. 전방주시거리 = 현재속도 ×
`LookaheadSeconds`(1.0), `LookaheadMinCm`~`MaxCm`(4~30m)로 클램프.

> ⚠️ **당근은 "방향"만 준다. 크기는 거버너가 정한다.** 이걸 헷갈려서 당근을 위치 목표로 쫓게
> 만들었다가 목표 속도가 `전방주시거리 × PositionP`로 고정돼 **45km/h 경로를 10km/h로 기어가는**
> 버그가 났다. 전방주시거리가 속도에 비례하므로 저속에서 최소값에 갇히는 자기강화 루프까지
> 생겼다. 코드에서는 `bFlyThroughAtSpeed` 플래그로 갈린다(true=경로추종, false=이륙/도착).

### 11.4 속도 — 제동 곡선

앞쪽 샘플들의 통과 가능 속도를 구하고 `허용속도 = √(통과속도² + 2·감속도·거리)`를 **모든
샘플에 대해 계산해 최솟값**을 목표로 삼는다. 스플라인 끝은 "통과속도 0인 커브"로 취급하면
도착 감속까지 저절로 된다.

> ⚠️ "앞 N m 안에 커브가 있냐"는 이진 판정으로 목표 속도를 정하면 커브가 창에 들어오는 순간
> 계단식으로 뚝 떨어져 정속 주행 중 갑자기 풀 브레이크가 된다(UGV 1차 구현의 실패).
> 거리가 **판정 조건이 아니라 출력**에 들어가야 매 틱 연속적으로 내려온다.

**커브 통과속도**는 창 안의 꺾임각 → 속도 선형 매핑:
`Lerp(순항속도, MinCornerSpeedKmh, 꺾임각/CornerFullSlowAngleDeg)`.
`√(측면가속도/곡률)` 방식을 쓰다가 갈아엎었다 — 하한이 없어서 반경이 조금만 작아져도 속도가
바닥으로 떨어졌다. 선형 매핑은 최소~순항 사이로 유계라 그런 폭주가 구조적으로 불가능하다.

**곡률 측정 구간(`CurvatureMeasureBaselineCm` 10m)은 샘플 간격(2.5m)과 반드시 분리**해야 한다.
짧게 재면 완만하고 긴 커브가 각도 변화 ≈0으로 나와 감속이 전혀 안 걸린다.

> 💡 **스플라인 점 밀도는 속도에 영향을 주지 않는다.** 속도는 위 두 값(스캔/측정 구간)으로만
> 정해지고, 진행은 거리 기준으로 보간한다. 점을 촘촘히 찍든 듬성듬성 찍든 같은 형상이면 같은
> 속도가 나온다 — 이게 의도된 동작이다.

#### 순항 속도를 올리고 싶을 때

`CruiseSpeedKmh`(오토파일럿, 현재 45) 하나가 최고 속도다. 단 **경로 액터의
`CruiseSpeedOverrideKmh`가 0보다 크면 그쪽이 이긴다** — 값을 올렸는데 안 바뀌면 거기부터 볼 것.

순항 속도는 항력 균형이 정하므로 속도를 올리면 그만큼 더 기울어야 한다. 현재 BP 값
(`MaxTiltAngleDegrees`=60, `DragAreaCdA`=(0.12,0.14,0.30), 4.5kg) 기준:

| 순항 속도 | 필요 기울기 | 스로틀 | 비고 |
|---|---|---|---|
| 45 km/h | ~14° | 0.52 | 현재값 |
| 60 km/h | ~23° | 0.54 | 여유 있음 |
| **70 km/h** | ~32° | 0.59 | **권장 상한** — `CruiseSpeedKmh`만 올리면 됨 |
| 80 km/h | ~44° | 0.70 | 경로 보정 여유가 거의 없음 |
| ~88 km/h | 60°(포화) | — | 물리적 한계, 도달 불가 |

70을 넘길 거면 같이 봐야 할 것:

- **`CurvatureScanDistanceCm`**(6000=60m). 커브를 미리 보는 거리. 80km/h에서 커브 통과속도까지
  줄이려면 제동거리가 **70m**라 60m로는 늦게 밟는다 → 8000~10000으로.
- **`BrakingDecelMetersPerSecSq`**(3.5). 위 대신 이걸 올려도 되지만 감속이 급해진다.
- **`MaxHorizontalAccelMetersPerSecSq`**(BP 4.0). 순항 속도를 제한하진 않지만(항력 상쇄분은
  이 상한 **바깥에서** 더해진다, 11.1절/4.2절) 거기까지 붙는 시간을 정한다. 0→70km/h가 약
  5초. 더 빨리 붙이려면 올릴 것.

`MinCornerSpeedKmh`는 안 건드려도 된다 — 커브 통과속도가 순항속도에서 선형 보간이라 순항을
올리면 완만한 커브 속도도 같이 올라간다.

### 11.5 무게감 3노브

최대 기울기 60°만으로는 g·tan(60°)=17.0m/s²까지 낼 수 있어서, 제한을 안 걸면 목표가 조금만
어긋나도 최대 기울기로 처박는다("너무 험하게 주행함"). 실제 대형기는 낼 수 있어도 그렇게 안 난다.

(아래 "기본값"은 C++ 기본값이고, **BP_Drone에서 조정된 실제 값은 괄호 안**이다.)

| 프로퍼티 | 기본값 | 역할 |
|---|---|---|
| `MaxHorizontalAccelMetersPerSecSq` | 5.0 (**BP 4.0**) | **가속 중** 기울기를 직접 정한다: `atan(값/9.81)` → 2.5=14°, 4.0=22°, 8.2=40° |
| `CommandSmoothingSeconds` | 0.6 (**BP 0.1**) | 스틱 지령 1차 지연. 저크 제한 — 방향 전환이 툭툭 끊기지 않게. **"가속/감속 시간 늘리는 값"이 이것** |
| `VelocityP` / `PositionP` | 1.4 / 0.7 | 캐스케이드 감쇠비. 진자처럼 좌우로 롤하면 `VelocityP`를 올리거나 `PositionP`를 낮춘다 |

⚠️ 정속 순항 중 기울기는 **항력 균형**이 정하므로 위 값과 무관하다(45km/h=15°, 70km/h=32°).
순항 중에도 크게 기울이고 싶으면 `CruiseSpeedKmh`를 올려야 한다.

⚠️ 위치 루프는 자세 루프(`AttitudeP`=8)보다 3~5배 느려야 한다. `PositionP`/`VelocityP`가
1~2 대역을 넘으면 캐스케이드가 진동한다.

### 11.6 바람 — 절대 미리 상쇄하지 말 것

레벨의 `AWindSource`(sfx_vfx/wind_system.md, 다른 세션 구현)를 폰이 매 틱 읽어
`Flight->WindVelocityMS`에 넣는다. 항력은 **대기속도**(속도−바람) 기준이라 그것만으로 기체가
밀리고, 제자리 유지에 기울임이 필요해진다.

> ⚠️ 자율비행의 항력 피드포워드는 **대지속도만** 쓴다(`bDragFeedforward`). 예전엔 대기속도
> 기준으로 계산해서 바람을 지연 없이 완벽히 상쇄했는데, 그게 "너무 비현실적으로 잘 버틴다"의
> 원인이었다 — 실제 드론엔 풍속계가 없어 바람을 미리 알 수 없고, **밀린 결과로만** 감지한다.
> 지금은 `VelocityI`(0.5) 적분기가 사후에 흡수하므로 돌풍마다 눈에 보이게 흔들린다.

### 11.7 경로 액터 `ADroneFlightPath`

| 프로퍼티 | 의미 |
|---|---|
| `PathId` | 콘솔/시나리오가 지목하는 이름 |
| `CruiseSpeedOverrideKmh` | 이 경로 전용 순항속도(오토파일럿 기본값보다 우선) |
| `bUsePathRotationForHeading` | 기수를 스플라인 회전값으로 잡을지 |
| `bHoverAtEnd` | 끝에서 정지비행 유지 |

**비행 중 재경로**가 가능하다 — 이미 떠 있는 상태에서 `BeginPathFollowing`을 부르면 이륙 단계를
건너뛰고 현재 위치를 새 경로에 투영해 순항 속도로 이어받는다. 2·3차 전투지로 도주하는 적을
따라가는 연출이 이걸 쓴다(`MoveDroneToPath` 이펙트).

### 11.8 수동 개입

자율비행 중 스틱을 `ManualOverrideThreshold`(0.35) 이상 움직이면 자동 해제된다
(`bDisengageOnManualInput`, 실제 오토파일럿과 같은 동작).

---

## 12. 짐벌 카메라

### 12.1 구조

`SK_UAV` 스켈레톤의 `CamYaw`(팬) / `CamPitch`(틸트) 본을 `UPoseableMeshComponent`로 직접 돌린다.
BP에 배치된 `UCineCameraComponent`가 그 본 소켓에 붙어 있고, 코드가 `BeginPlay`에서
`USceneCaptureComponent2D`를 만들어 렌즈 설정을 그대로 복사한다(`SyncGimbalLensFromCineCamera`).

- `C`키 시점 순환에 짐벌이 포함된다 — 짐벌이 실제로 어디를 보는지(렌즈/DOF까지) 메인 화면에서
  바로 확인할 수 있다.
- 캡쳐는 라운드로빈(`GimbalRoundRobinSlot`/`Count`)으로 매 프레임 안 돈다.
- 자체방호축에서만 캡쳐가 살아있다 — 다른 축 프로세스에서는 `bDisableGimbalCapture`로 꺼서
  아무도 안 보는 풀퀄리티 캡쳐가 도는 걸 막는다.

### 12.2 본 회전 — 컴포넌트 공간 절대값 (함정)

`SetBoneRotationByName(..., ComponentSpace)`는 **델타가 아니라 그 본의 절대 CS 방향**을 받고,
엔진이 내부에서 부모의 현재 CS로 나눈다. 그래서 정답은 이렇다:

```cpp
const FQuat Yaw(FVector::ZAxisVector,  FMath::DegreesToRadians(GimbalYawDeg));
const FQuat Pitch(FVector::YAxisVector, -FMath::DegreesToRadians(GimbalPitchDeg));
BodyMesh->SetBoneRotationByName(GimbalYawBoneName,   (Yaw * GimbalYawRestCS).Rotator(),         EBoneSpaces::ComponentSpace);
BodyMesh->SetBoneRotationByName(GimbalPitchBoneName, (Yaw * Pitch * GimbalPitchRestCS).Rotator(), EBoneSpaces::ComponentSpace);
```

두 가지를 동시에 지켜야 한다:

1. **델타를 왼쪽에 곱한다**(월드/컴포넌트 공간 회전). 오른쪽에 곱하면 본 로컬 축 기준이 돼서
   틸트가 엉뚱한 방향으로 돈다.
2. **CamPitch에도 부모의 Yaw를 곱해서 넘긴다.** 안 그러면 CamPitch에 넘긴 절대 방향이 부모의
   yaw를 상쇄해버려서, 밖에서 볼 땐 팬이 도는데 짐벌 시점에선 팬이 안 먹는다.

증상이 "좌우는 도는데 위아래가 이상한 방향 / 짐벌 시점에선 위아래만 되고 좌우가 안 먹음"이면
이 두 가지 중 하나다. 순서도 중요해서 `CamYaw`를 먼저 설정한 뒤 `CamPitch`를 설정한다.

`RefreshBoneTransforms()` → `UpdateChildTransforms()`를 같은 프레임에 불러야 소켓에 붙은
카메라가 그 프레임에 따라온다.

### 12.3 자동 정찰 단계

| 단계 | 동작 |
|---|---|
| `Idle` | 대기 |
| `ObservingParachute` | 좌우로 스윕하며 "찾는 척" → `GimbalGuaranteedFindDelaySeconds`(5초) 후 낙하산으로 스냅 + 줌인(`GimbalZoomInLevel` 2.5) → `ParachuteObserveDurationSeconds`(5초) 관찰 |
| `ParachuteObserved` | `HasObservedParachute()`가 true. **시나리오가 이걸 UGV 출발 트리거로 쓴다** |
| `WideEngagementView` | 교전 시작 후 — 아군/UGV/적군이 전부 한 화면에 들어오도록 조준과 FOV를 매 틱 다시 계산(`ComputeFramingForPoints`) |

경로 끝 도착 시 `bAutoStartReconOnArrival`로 자동 시작된다.

---

## 13. 탐지 단계와 시나리오 연동

### 13.1 단계별 탐지 (`EDroneDetectionPhase`)

처음부터 다 보이면 "드론이 정찰해서 알아냈다"는 연출이 성립하지 않는다. 그래서 탐지 범위가
시나리오 진행에 따라 넓어진다:

| 단계 | 보이는 것 | 누가 올리나 |
|---|---|---|
| `FriendlyOnly` | 아군만 | 초기값 |
| `PlusEvidence` | + 낙하산(EnemyEvidence) | 경로 끝 도착 시 드론이 **스스로**(`bAutoAdvanceDetectionOnArrival`) |
| `All` | + 적군 전부 | UGV가 적을 발견하면 시나리오 이펙트(`EnableDroneEnemyDetection`) |

구현은 `UTargetDetectionComponent`에 추가한 `DetectableFactions`(진영 필터) 하나다.

> ⚠️ **겉보기 크기 필터(`MinScreenSizeFraction`/`MinScreenSizePixels`)를 드론에서 켜지 말 것**
> (2026-09-04). 이건 거리가 아니라 **화면 점유율** 기준이라 화각에 반비례한다. 1.8m 병사 기준
> 유효 탐지거리가 짐벌 화각 30°면 150m인데 교전 광각(88°)에서는 **45m로 무너져**
> `MaxDetectionRange`(800m)가 통째로 무의미해진다. "너무 멀면 못 알아본다"는 연출은 위 단계별
> 진영 필터가 이미 하고 있다.
>
> 한때 폰에 `DetectionMinScreenSizeFraction` 미러를 두고 `BeginPlay`에서 컴포넌트에 써넣었는데,
> **BP에서 끈 설정이 매 플레이마다 되살아나는** 함정이었다("왜 안 먹지"의 정체). 지금은 미러를
> 없애서 `TargetDetection` 컴포넌트의 자기 프로퍼티가 유일한 기준이다.
>
> UGV/트럭 RCWS는 조준경이라 화각 변동이 작아 이 필터를 의도적으로 쓴다(트럭
> `MinScreenSizePixels=12`). 다만 같은 결합은 있어서, 줌 0.5배(최대 광각)에서만 235m로 조여지고
> 1배 이상이면 `MaxDetectionRange`가 먼저 걸린다.

### 13.1-1 프레이밍 대상 — **탐지 결과를 쓰지 않는다**

교전 광각 프레이밍(16절)에 넣을 대상은 `UDetectableTargetSubsystem` 레지스트리에서 **실시간
위치를 직접** 읽는다. 짐벌이 지금 뭘 알아봤는지와 무관하다.

이유는 순환 의존이다 — 탐지 결과를 프레이밍 입력으로 쓰면 `줌아웃 → 대상이 작아짐 → 겉보기
크기 필터에 걸려 탐지 해제 → 프레이밍에서 빠짐 → 줌인 → 반복`이 된다. 게다가 레지스트리
폴백이 "탐지 0명"일 때만 발동해서 5명 중 1명만 잡히면 나머지 4명이 영영 빠졌다(실측).
자동 정찰은 연출이지 센서 시뮬레이션이 아니다.

**예외는 낙하산 관측 판정 하나**(`IsParachuteCurrentlyDetected`) — 거기서는 "카메라가 실제로
알아봤는가"가 곧 연출의 요점이라 `TargetDetection`을 쓰는 게 맞다.

### 13.2 `DT_ScenarioSteps_ThreeStage` 드론 관련 행

| 행 | 선행 | 트리거 | 이펙트 |
|---|---|---|---|
| `UAVMission` | — | `TimerOnly` 3s | `BeginUAVMission` (`UAVPathId`=`uavpath`) |
| `UAVSpotted` | `UAVMission` | **`UAVParachuteObserved`** | `MoveUGVToZone1Destination` |
| `RevealEnemies` | `UAVSpotted` | `TimerOnly` 0s | `RevealEnemies` |
| `DroneSeeEnemies` | `UGVSurveillance` | `EnemyDetected` | `EnableDroneEnemyDetection` |
| `DroneWideView` | `DroneSeeEnemies` | `TimerOnly` 2s | `UAVEngagementZoomOut` |
| `UAVDetectionOff` | `UAVSpotted` | `TimerOnly` 2s | `DisableUAVTargetDetection` (**bEnabled=false**, 단계별 탐지로 대체됨) |

> ⚠️ `UAVSpotted`의 트리거가 예전엔 `UAVEnemyDetected`였다. 행 설명은 "UAV가 낙하산 발견"인데
> 실제 판정은 "적 감지"라서 서로 달랐고, **드론이 낙하산을 찾아 줌인해도 UGV가 출발하지 않는**
> 증상이 났다. `UAVParachuteObserved`(신설 트리거)로 교체해서 설명과 판정을 일치시켰다.

행이 제대로 흐르면 로그에 이 순서로 찍힌다:

```
[Drone] 낙하산 관찰 완료 — UGV 출발 트리거 조건 충족.
[Drone] 탐지 단계 → 전부.
[Drone] 교전 광각 전환 — 고정 지점 N개 + 감지 중인 적군.
```

"고정 지점 N개"의 N은 **아군 수 + 1(UGV)** 이어야 한다.

### 13.3 신설 이펙트 / 트리거 (`ScenarioStepTypes.h`)

- 트리거 `UAVParachuteObserved` — `ADronePawn::HasObservedParachute()`
- 이펙트 `EnableDroneEnemyDetection` — 탐지 단계를 `All`로
- 이펙트 `MoveDroneToPath` — 행의 `UAVPathId` 경로로 재경로(2·3차 전투지 추격용)
- 행 필드 `FName UAVPathId` — 드론이 따라갈 `ADroneFlightPath`의 `PathId`

`UScenarioStateSubsystem`은 `FindSceneDrone()`으로 드론을 먼저 찾고, 없으면 구 `AUAVPawn`으로
폴백한다(`UAVArrived`/`BeginUAVMission`/`UAVEngagementZoomOut`/`DisableUAVTargetDetection` 전부).
`EnemyCube` 태그로 목적지를 정하던 구 방식은 폐기됐다 — 이제 스플라인 경로가 목적지다.

---

## 14. 프로펠러 사운드

`UDronePropAudioComponent`. 3가지 모드를 에디터에서 고른다:

| 모드 | 보이스 수 | 용도 |
|---|---|---|
| `SingleAveraged` | 1 | 6로터 평균 회전율 하나만. **현재 이걸 쓴다** — 가장 안정적이고 비용이 낮음 |
| `SingleWithSpread` | 1 | 평균 + 로터 간 편차(`SpinSpread`)를 파라미터로 추가 전달 |
| `PerRotor` | 6 | 각 로터 위치에 보이스를 배치. 가장 현실적이지만 비쌈 |

메타사운드에 넘기는 파라미터는 `SpinRatioParameterName`(기본 `SpinRatio`, 0~1) 하나면 충분하다 —
그걸로 pitch/volume을 조절하는 게 표준 사용법. `SpinSpread`는 선택.

**우선순위 보호**(구 UAV에서 이식): `SoundPriority`=25로 높게 잡고, `bSelfHealIfStopped`로 다른
소리에 밀려 끊기면 스스로 다시 재생한다. 드론 소리는 전시 중 끊기면 안 되기 때문.

`PerRotor` 모드는 보이스 6개가 겹쳐 볼륨이 √6배로 커지므로 1/√N 보정이 자동으로 들어간다
(추가 조정은 `PerRotorVolumeTrim`).

---

## 15. 리플리케이션 — 클라이언트 권위 (단, 데모 모드는 서버)

**전시 구성은 2대 PC 2프로세스다: 서버=UGV축, 클라이언트=자체방호축. 그리고 드론을 조종하는
쪽이 클라이언트다.** 그래서 서버 권위로 하면 입력 지연이 그대로 드러난다.

**시뮬 주체 판정은 `ADronePawn::ResolveShouldSimulateDrone()` 3단계**(2026-09-01 개정):
① 단독 실행(`NM_Standalone`)이면 무조건 이 프로세스 → ② `SelfDefense`/`Unspecified` →
③ **데모 실행 모드(`ScenarioConfig::RunMode == Demo`)의 리슨서버면 서버**.

> ③이 없으면 자체방호 클라이언트가 안 붙는 데모 구성(전시용 1 PC, UGV축 호스트 단독)에서
> 시뮬 주체가 아예 없어 **드론이 안 날고, 낙하산 관측 → UGV 1차 목적지 출발 체인이 멈춘다**
> (2026-09-01 실사용 버그). 배경은 `replication/2026-09-01_drone_client_authoritative.md` §3.1.

### 15.1 왜 Chaos Resimulation을 안 썼나

엔진의 네트워크 물리 예측+롤백(`EPhysicsReplicationMode::Resimulation`)은 UE5.8에서 아직 WIP인
데다 `bTickPhysicsAsync`를 요구한다. 그걸 켜면:

- 이 프로젝트가 441ms → **68ms**까지 낮춰둔 RTSP 종단 지연이 **+33ms** 늘어난다.
- 튜닝이 끝난 UGV Chaos 차량 거동이 바뀐다.

전용 LAN의 전시 장비 2대라 클라이언트를 신뢰해도 위협 모델상 문제가 없어서, **클라이언트
권위 시뮬레이션**을 골랐다.

### 15.2 방향별 배선

```
시뮬 클라(자체방호) → 서버 : Server_ReportState (Unreliable, WithValidation)
                              위치/회전/속도/짐벌각/줌 — 30Hz(StateReportHz)
서버 → 전원                : 위 값을 Replicated 프로퍼티로 재전파
                              + 시나리오 명령(CommandedPathId, DetectionPhase, 교전 프레이밍 지점)
```

- **비신뢰 RPC**를 쓰는 이유: 매 프레임 최신값만 의미 있고 유실돼도 다음 패킷이 덮으므로,
  신뢰 전송의 재전송 비용이 낭비다.
- **시뮬 주체가 아닌 프로세스는 물리를 아예 안 돌린다**(`SimulatePhysics` off, Flight 틱 off).
  두 프로세스가 각자 물리를 돌리면 미세한 차이가 누적돼 화면이 어긋난다. 받은 값만
  `RemoteInterpSpeed`(12/s)로 보간해 적용한다.
- 명령 계열은 `ReplicatedUsing` + **카운터**를 같이 둔다(`CommandedPathCounter`,
  `EngagementFocusCounter`) — 같은 값을 다시 보내도 OnRep이 뜨게 하기 위함.

### 15.3 소유권 함정

클라이언트가 Server RPC를 보내려면 **그 PC가 드론의 Owner**여야 한다(엔진이 RPC 호출 권한을
소유권으로 판정). 그래서 `Atitan_exampleGameMode::PostLogin`에서 축이 `SelfDefense`인 PC에게
`Drone->SetOwner(TitanPC)`를 해준다. **빙의(Possess)는 하지 않는다** — 자체방호축은 트럭 RCWS를
빙의 중이고, 드론 조종은 빙의 없이 컨트롤러 라우팅으로 한다.

소유권을 못 넘기면 조용히 상태만 안 올라가므로 경고 로그를 넣어뒀다:

```
PostLogin: 레벨에서 ADronePawn을 못 찾아 소유권을 못 넘겼습니다 — 드론 상태가 서버로 전달되지 않습니다.
```

### 15.4 RTSP

짐벌 캡쳐가 자체방호축 7스트림 중 하나로 나간다 — mount `selfdefense/uav_gimbal`.
송출 해상도는 `UStreamResolutionSubsystem::SelfDefenseUavResolution`으로 고정하고, 위젯이 창
크기에 맞춰 리사이즈하는 `CameraRenderTarget`과 별개로 인코딩 직전에 스케일 복사한다 — 씬을
두 번 렌더하지 않는다. 자세한 배경은 `rtsp/`, `camera_pipeline/` 참고.

---

## 16. 교전 관측 이동 (2026-09-05)

교전이 시작되면 드론이 **활성 경로 스플라인 위에서 "지금 전황을 가장 잘 보여주는 지점"으로
스스로 이동**한다. 짐벌은 각도만 바꿀 뿐 거리를 못 줄여서, 교전이 옮겨가면 "전원이 담기긴
하는데 아무것도 분간이 안 되는" 그림이 되기 때문.

**자유비행은 하지 않는다.** 이 드론엔 지형 회피가 없고 스플라인이 그 역할을 대신하므로,
"어디로든 날아가서 잘 보는 곳"이 아니라 "그려진 선 위에서 가장 잘 보이는 지점"을 고른다 —
안전이 저작 단계에서 보장된다. 마스터 스위치는 `BP_Drone → Gimbal|Observation →
bAutoRepositionForEngagement`(기본 켜짐).

### 16.1 역할 분담

```
시나리오 세트(Zone1/2/3)  →  프레이밍 대상 (레지스트리 직결, 13.1-1절)
                                    │
                    ┌───────────────┴───────────────┐
        폰: 관측 지점 선정                   짐벌: 조준 + 줌 (12절)
        (화각/부감 제약 만족)
                    │
                    ▼
        자율비행: 유도점 흘려보내기 → 피드포워드 + 위치 P → 스틱
```

**"어디서 볼지"는 렌즈·화각을 아는 폰이 정하고**(`ADronePawn::UpdateObservationHoldPoint`),
자율비행(`EDroneAutopilotState::Observing`)은 지시받은 스플라인 진행거리까지 부드럽게 날아가는
것만 책임진다.

### 16.2 프레이밍 대상 — 시나리오 단계별

| 단계 | 조건 | 대상 |
|---|---|---|
| 1 | 경로 도착 | 낙하산 (정찰 단계, 12.3절) |
| 2 | UGV가 적군 감지 | UGV + 적군 전체 |
| 3 | 아군이 적군 감지 | UGV + 적군 전체 + 아군 전체 |
| 4 | 3분대 도주 시작 | 〃 (변경 없음) |
| 5 | **3분대 제외 전멸** | 이동형지휘소만 |
| 6 | 트럭 RCWS가 3분대 포착 | 이동형지휘소 + 마지막 분대 |

두 가지가 **시나리오 스텝이 아니라 월드 상태**로 판정된다 — 스텝 타이밍만 믿었다가 아직 싸우는
적을 통째로 버린 적이 있다(2026-09-04 실측):

- **5번 진입**: `ResolveEffectiveFramingSet()` — 마지막 분대가 아닌 적이 살아 있으면 시나리오가
  Zone3를 지시해도 **직전 세트를 유지**한다.
- **6번 진입**: 이동형지휘소 `RCWSFireControlComponent::CurrentAutoAimTarget` 유무(래치).
  자동조준은 대상을 놓쳤다 잡았다 하므로 한 번 켜지면 안 되돌린다.
  ⚠ **Zone3에서만 검사할 것** — UGV도 RCWS를 달고 있어서 1차 전투지에서 래치가 걸린다.

**도주 중인 개체(`EEnemyState::Flee`)는 어느 단계에서도 대상에서 뺀다.** 연출상 "도망친 놈은
놓아주고 다음 전투지에서 다시 잡는다"가 맞고, 실질적으로도 전장 밖으로 빠르게 멀어져
프레이밍을 폭주시키는 주범이다(16.5절).

### 16.3 관측 지점 선정 — 줌이 먼저, 이동은 나중

```
진입: 경로 끝점(= 저작 규약상 초기 관측 자리)에서 시작
매 1초:
  ├ 지금 자리로 충분한가?  → 아무것도 안 함 (줌만 조절)      ← 대부분의 시간
  └ 아니면 → 두 조건을 만족하는 "가장 가까운" 지점으로 이동
              없으면 → 차선(덜 나쁜 곳) + 경고 로그
```

조건 두 가지:
1. **전원이 최대 화각(90°) 안에 들어올 것** — 못 담으면 뒤로 물러나 거리를 번다
2. **조준 부감이 -60~-45°일 것** — 옆에서 보면 나무가 겹쳐 아무것도 안 보인다

> **부감 범위는 선호일 뿐 조준 방향을 바꾸지 않는다.** 조준은 언제나 개체들의 각도상 중점을
> 따라가고, 이 범위는 오직 "어느 지점에 설지" 고를 때만 쓴다. 억지로 이 각도로 돌리면 정작
> 개체들이 화면 밖으로 나간다.

**슈미트 트리거** — 목적지로 고를 땐 엄격하게(화각 여유 10%, 밴드 안), 지금 자리를 유지할지
볼 땐 느슨하게(밴드 ±8°). 문턱이 하나면 경계에 걸터앉아 1초마다 판정이 뒤집히고 그때마다
기체가 움직인다.

⚠ **화각 초과량은 반드시 클램프 전 원본으로 판정할 것.** `ComputeFramingFromLocation`은
결과를 Min/Max로 클램프해서 돌려주므로, 그 값으로 초과량을 계산하면 `90 - 90 = 0`이 되어
"뒤로 물러나라" 신호가 통째로 사라진다(실제로 겪은 버그). 그래서 `OutUnclampedFOVDegrees`를
따로 반환한다.

### 16.4 이동 — 유도점 + 속도 피드포워드

**지령 지점을 그대로 쫓지 않는다.** 지령은 불연속으로 튈 수 있으므로, 그쪽으로 흘러가는
**유도점**을 따로 두고 기체는 그것만 쫓는다. 경로 추종의 당근점과 같은 구조다.

```
ObservationDistanceCm       폰이 내려준 목표 (튀어도 됨)
ObservationGuideDistanceCm  거기로 사다리꼴 프로파일로 흘러가는 유도점 (항상 연속)
                            → 그 진행 속도를 속도 피드포워드로 넘김
```

세 가지가 함께 있어야 안 흔들린다:

- **사다리꼴 프로파일** — 가속도 제한(`ObservationGuideAccelMetersPerSecSq`) + 남은 거리에서
  멈출 수 있는 속도 상한(`v ≤ √(2a·d)`). 유도점 속도 자체가 연속이 된다.
- **속도 피드포워드** — 유도점이 얼마나 빨리 흐르는지 이미 아니까 그대로 넣는다. 이게 없으면
  기체는 위치 오차만으로 속도를 짜내야 해서 순항 중에도 약 12m 뒤처진 채 루프가 계속 일하고,
  캐스케이드의 저감쇠 모드가 계속 여기된다.
- **관측 모드 적분 축소**(`ObservationIntegralScale` 0.15) — 적분기는 ζ를 0.71에서 0.51로
  깎는데, 위치 유지 모드에서 얻는 건 정상상태 droop 제거뿐이라 관측에는 손해가 크다.

> **왜 경로 추종은 원래 부드러웠나**: `bFlyThroughAtSpeed=true`는 거버너 속도를 그대로 쓰는,
> 즉 이미 순수 피드포워드였다. 관측만 순수 위치 피드백이라 아래 모드를 계속 때렸다:
> ```
> s³ + Kv·s² + (Kv·Kp + Ki)·s + Ki·Kp = 0
> Kp=0.7, Kv=1.4, Ki=0.5 → ζ = 0.51, 주기 6.8초   (내부 루프 지연 0.29s 포함 시 실효 0.4)
> ```

**`ObservationGuideAccelMetersPerSecSq`가 "천천히 기울어지게"의 노브다.** 유도점 속도 → 피드포워드
→ 요구 가속도 → 기울기로 이어지므로. d미터 보정 시 최고속도가 `√(2a·d)`이고 그만큼 기울었다
펴진다. 별도의 저크 리미터를 두지 않는 이유가 이것 — 같은 일을 하면서 위상 지연(감쇠에 불리)이
없다.

### 16.5 기수와 카메라는 완전히 분리

**기체는 피사체를 향할 필요가 없다.** 짐벌 요는 클램프가 없고(`Fmod`만) 목표를 매 틱 기체
좌표계로 변환하므로, 기수가 어디를 보든 카메라는 대상을 정확히 문다. 실제 멀티로터도 뒤로·옆으로
그냥 평행이동한다.

기수 방향을 진입 시 대상 쪽으로 래치하고, 이후엔 `ObservationHeadingSlewDegPerSec`(8°/s) 상한
안에서만 돌린다. 낮게 잡아야 하는 이유가 둘: (1) 옆으로 수백 미터를 날면서 피사체를 계속 향하면
방위각이 빠르게 쓸려 기체가 빙글빙글 돈다, (2) 기체가 빨리 돌면 짐벌이 슬루 한계(25°/s) 때문에
못 따라와 화면까지 흔들린다.

### 16.6 노브 정리

`BP_Drone → Gimbal|Observation` (지점 선정):

| 프로퍼티 | 기본값 | 역할 |
|---|---|---|
| `bAutoRepositionForEngagement` | true | 마스터 스위치 |
| `ObservationPreferredPitchMin/MaxDeg` | -60 / -45 | 부감 선호 범위 |
| `ObservationSampleStepCm` | 1000 | 스플라인 후보 간격 |
| `ObservationEvalIntervalSeconds` | 1.0 | 재평가 주기 |
| `ObservationMinHoldSeconds` | 5.0 | 이동 후 최소 체류 |
| `ObservationPitchBandHysteresisDeg` | 8.0 | 유지 판정 여유(슈미트 낮은 문턱) |
| `ObservationEnterFOVSafetyRatio` | 0.9 | 목적지 화각 여유 |
| `ObservationFallbackImproveMargin` | 0.15 | 차선 모드에서 옮길 최소 개선폭 |
| `ObservationLastStandZoneIndex` | 2 | 마지막 분대 판정(3분대=2) |

`BP_Drone → Autopilot → Drone|Autopilot|Observation` (이동):

| 프로퍼티 | 기본값 | 역할 |
|---|---|---|
| `ObservationSpeedKmh` | 30 | 근거리 유도점 속도 |
| `ObservationFarTransitSpeedKmh` | 55 | 원거리 이동 속도(전투지 전환) |
| `ObservationFarTransitDistanceCm` | 15000 | 위 속도를 다 쓰는 거리 |
| `ObservationGuideAccelMetersPerSecSq` | **0.6** | **기울기 변화 속도** |
| `ObservationCatchUpRatio` | 1.5 | 기체 속도 상한 = 유도점 속도 × 이 값 |
| `ObservationIntegralScale` | 0.15 | 관측 모드 적분 비율 |
| `ObservationHeadingSlewDegPerSec` | 8 | 기수 회전 상한(0=고정) |

여전히 출렁이면 `ObservationGuideAccelMetersPerSecSq`를 0.3까지 내리고, 그래도 남으면
`PositionP` 0.7→0.4 / `VelocityP` 1.4→1.8을 시험(ζ 0.85).

### 16.7 진단 로그

```
[Drone] 교전 관측 모드 — 경로 'uavpath2' 끝점(994m)에서 시작. ...
[Drone] 관측 지점 이동 — 경로 'uavpath2' 740m 지점 (대상 13개[적 12], 필요화각 61.7°, 부감 -50.4°).
[Drone] 관측 조건 회복 — 지금 자리 유지(필요화각 64.4°, 부감 -48.8°).
[Drone] 실제 적용 프레이밍 세트 2 → 2 (이전 전투지 잔존 적이 있어 3차 전환 보류).
[Drone] 이동형지휘소 RCWS 교전 개시 포착 — 이제부터 마지막 분대도 프레이밍에 포함합니다.
Warning: [Drone] 경로 '...' 어디에서도 대상 N개 전원 프레이밍 + 부감 ...을 동시에 만족할 수 없습니다
```

**`대상 N개[적 M]`이 가장 중요한 진단값**이다. N이 30을 넘으면 필요 화각이 90°에 포화하고,
그러면 "지금 자리 유지" 판정이 영영 거짓이 되어 체류시간 주기마다 관측 지점이 새로 뽑힌다 —
그게 5초 주기로 가속/감속을 반복하는 턱턱거림으로 나타난다. 마지막 경고가 계속 뜨면 **경로
고도가 부족**하다는 뜻이고, 교전 반경 R에 대해 대상보다 **R × 1.0~1.25 위**가 기준이다.

---

## 17. 작업 이력

| 날짜 | 내용 |
|---|---|
| 2026-08-27 | 기존 UAV 비행 로직 분석, 카메라 기울기 위화감 원인 규명(1절) |
| 2026-08-27 | 6로터 강체 모델 신규 구현. 처음엔 자체 6-DOF 적분기 |
| 2026-08-27 | **Chaos 강체로 전환** — 자체 적분기는 콜리전이 없어 라인트레이스 1발로만 지면을 알았고, 경사면·구조물 착지/장애물 충돌이 불가능했음. 물리 모델(로터 추력/믹서/PID/항력)은 그대로 두고 적분·접촉만 엔진에 넘김 |
| 2026-08-27 | 조종 입력(IMC/IA), 테스트 레벨/게임모드/BP 구성, 실기 조종 검증 완료 |
| 2026-08-27 | IMC 등록 이중화 + 진단 로그 추가(6.1절), 테스트 코스 박스 29개 배치(9절) |
| 2026-08-28 | 짐벌 이식(12절) — 본 회전 공간 문제로 2회 재작업 |
| 2026-08-28 | 프로펠러 사운드(14절), 자율비행 1차 구현(11절) |
| 2026-08-29 | 바람 연동(11.6절), 자율비행 속도/무게감 버그 3건 해결 |
| 2026-08-29 | 시나리오 재배선 — 낙하산 관측이 UGV 출발 트리거(13절) |
| 2026-08-30 | 단계별 탐지(13.1절), 클라이언트 권위 리플리케이션(15절), 위젯 배선 |
| 2026-08-31 | 유니티 빌드 상수 재정의 정리(`namespace DroneUnits`, 2.1절) |
| 2026-09-01 | 단일 프로세스 시나리오 전체 검증 완료, 문서 최신화 |
| 2026-09-03 | **교전 관측 이동 신규**(16절) — 스플라인 위 관측 지점 자동 선정. 프레이밍을 TargetDetection에서 분리(13.1-1절) |
| 2026-09-04 | 유도 루프 구조 결함 3연쇄 해결 — 적분 와인드업 → 축별 안티와인드업 → 속도 피드포워드(16.4절). 겉보기 크기 필터가 탐지를 무력화하던 버그(13.1절) |
| 2026-09-05 | 기수/카메라 분리(16.5절), 도주 중인 적 트래킹 제외, 3차 전환 상태 게이트. **실동작 확인 완료** |
