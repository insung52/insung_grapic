# Chaos Wheeled Vehicle 아키텍처 조사 (공식 문서 기준)

UE5(5.7~5.8 공식 문서 기준, ChaosVehiclesPlugin) Chaos Vehicles 시스템의 클래스 구조와
설정 워크플로우를 Epic 공식 문서 위주로 조사한 내용. M1A2 복제 방식이든 처음부터 구성하는
방식이든 공통으로 필요한 기반 지식.

---

## 1. 핵심 클래스 구조

```
APawn
 └─ AWheeledVehiclePawn (abstract, ChaosVehicles 플러그인)
      └─ (프로젝트의 AChaosWheeledVehicle 등 구체 클래스)
           ├─ USkeletalMeshComponent (Mesh) — 비히클 본체
           └─ UChaosWheeledVehicleMovementComponent (VehicleMovement)
                ├─ EngineSetup            : FVehicleEngineConfig
                ├─ TransmissionSetup      : FVehicleTransmissionConfig
                ├─ DifferentialSetup      : FVehicleDifferentialConfig
                ├─ SteeringSetup          : FVehicleSteeringConfig
                ├─ WheelSetups            : TArray<FChaosWheelSetup>  (본 이름 ↔ 휠 BP 매핑)
                ├─ Wheels                 : TArray<UChaosVehicleWheel*> (런타임 인스턴스)
                ├─ TorqueControl          : FVehicleTorqueControlConfig      (아케이드 회전 제어)
                ├─ TargetRotationControl  : FVehicleTargetRotationControlConfig
                └─ StabilizeControl       : FVehicleStabilizeControlConfig
```

- `AWheeledVehiclePawn`은 추상 클래스. 기본적으로 `UChaosWheeledVehicleMovementComponent`를
  무브먼트 컴포넌트로 사용.
- `UChaosVehicleWheel`은 **BP 서브클래스로 만드는 것이 표준 워크플로우**(공식 문서가 C++ 서브클래싱
  코드 예시를 제공하지 않음 — BP 전용 문서화되어 있음). 휠 하나당 하나의 BP: Axle Type,
  Wheel Radius, Affected by Handbrake/Engine/Steering, Max Steer Angle 등을 여기서 설정.
- `TorqueControl`/`TargetRotationControl`/`StabilizeControl`은 셋 다 `UChaosVehicleMovementComponent`
  (베이스 클래스) 소속이며 **"ArcadeControl" 카테고리** — 즉 셋 다 "진짜 물리"가 아니라
  아케이드 스타일의 보정용 토크/회전 제어 계층이라는 게 공식 문서의 명시적 분류.

**소스 경로(참고용, UE 소스 배포판 보유 시):**
`Engine/Plugins/Experimental/ChaosVehiclesPlugin/Source/ChaosVehicles/Public/`

출처: [AWheeledVehiclePawn](https://dev.epicgames.com/documentation/unreal-engine/API/Plugins/ChaosVehicles/AWheeledVehiclePawn), [UChaosWheeledVehicleMovementComponent](https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Plugins/ChaosVehicles/UChaosWheeledVehicleMovementComp-), [UChaosVehicleMovementComponent](https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Plugins/ChaosVehicles/UChaosVehicleMovementComponent)

---

## 2. 처음부터 구성하는 공식 워크플로우 (How to Set up Vehicles, UE5.8)

필요 애셋 6종: **스켈레탈 메시 / 피직스 애셋 / 애니메이션 블루프린트 / 비히클 블루프린트 /
휠 블루프린트(1개 이상) / 토크 커브(Float Curve)**.

### 2.1 스켈레탈 메시 & 바퀴 본
- 공식 문서는 본 계층 구조의 구체적 요구사항(축 방향, 네이밍 컨벤션 등)을 명시하지 않음 —
  "본 이름을 휠이 제어해야 하는 조인트 이름으로 설정"이라고만 안내. `WheelSetups` 배열의
  각 엔트리가 `BoneName` + `WheelClass`(휠 BP)로 구성됨.
- 휠 배열 순서는 시뮬레이션에 영향 없음(관리 편의상 FL/FR/BL/BR 권장).
- 예시(Buggy 샘플): 서스펜션 조인트(`F_L_Suspension` 등)를 Look-At 노드로 별도 제어해서
  실제 휠 본(`F_L_wheelJNT`)을 따라가게 하는 구조도 사용됨 — 즉 "서스펜션용 본"과
  "휠 회전용 본"을 분리하는 것도 공식적으로 허용/권장되는 패턴.

### 2.2 Physics Asset
- 스켈레탈 메시 우클릭 → Create Physics Asset (Primitive Type: Single Convex Hull 권장).
- **모든 휠 본을 선택 → Body Creation에서 Primitive Type을 Sphere로 → Re-generate Bodies.**
  (휠 콜리전은 구체가 표준)
- **서스펜션 본은 우클릭 → Collision → No Collision** — 서스펜션 조인트 자체가 콜리전을
  갖고 있으면 안 됨(있으면 캐스팅되는 레이/충돌 계산과 간섭 가능성).
- **Root Body 관련 명시적 언급 없음** — 공식 문서가 이 부분을 다루지 않는다는 것 자체가
  중요한 시사점. `USkeletalMeshComponent::FindRootBodyIndex()`의 "계층상 가장 앞쪽에서 물리
  바디가 있는 첫 본을 무조건 루트로 취급"하는 동작은 공식 튜토리얼 수준에서 전혀 경고되지
  않는, 실전에서만 부딪히는 함정으로 보임(M1A2 변환 작업에서 겪은 75cm 오프셋 버그 참고).
  실무 규칙으로 정리하면: **Root 본 자체에 반드시 물리 바디(주로 차체 캡슐/박스)를 만들어야
  하고, Root보다 계층상 앞선 자식 본에만 바디가 있으면 안 됨.**

### 2.3 휠 블루프린트 (`UChaosVehicleWheel` 서브클래스)
필수 설정 5가지 + 서스펜션은 "테스트하며 조정"으로만 안내(공식 문서가 서스펜션 튜닝 값의
의미를 상세히 설명하지 않음 — 이 부분은 별도 조사 필요, 03번 문서 참고):

| 프로퍼티 | 설명 |
|---|---|
| Axle Type | Front / Rear |
| Wheel Radius | 렌더 메시와 일치하는 실측 반지름(cm) |
| Affected by Handbrake | 보통 후륜 |
| Affected by Engine | RWD/FWD/AWD 결정 |
| Affected by Steering | 보통 전륜 |
| Max Steer Angle | 도(°) 단위, 음수면 반대 방향(후륜 반대조향에 사용 가능) |

### 2.4 애니메이션 블루프린트
- `VehicleAnimationInstance`를 부모로 사용, `WheelController` 애니메이션 노드로 휠 본을
  구동. (PhysX 시절엔 `WheelHandler` 노드 — 3절 변환 가이드 참고)

### 2.5 토크 커브
- X축: 엔진 RPM(0~MaxRPM), Y축: 토크(N·m), 전형적으로 역-U자 커브.
- 비히클 무브먼트 컴포넌트 → Mechanical Setup → Engine Setup → Torque Curve에 할당.

출처: [How to Set up Vehicles in Unreal Engine (5.8)](https://dev.epicgames.com/documentation/en-us/unreal-engine/how-to-set-up-vehicles-in-unreal-engine)

---

## 3. PhysX → Chaos 변환 공식 가이드 요약

M1A2 마켓플레이스 에셋처럼 **원래 PhysX 기반으로 만들어졌다가 Chaos로 이식된 에셋**을
다룰 때 참고할 공식 변환 절차(레거시지만 구조 이해에 도움):

1. **휠 BP 재생성**: PhysX 휠의 반지름/서스펜션 최대 상승·하강값/조향각/엔진·브레이크·
   핸드브레이크 적용 여부를 그대로 옮겨서 `ChaosVehicleWheel` 기반 BP로 새로 생성.
2. **비히클 컴포넌트 교체**: `ChaosWheeledVehicleMovementComponent` 추가, PhysX와 동일한
   개수의 휠 설정, **PhysX 스켈레탈 메시의 Bone Name을 그대로 복사**해서 새 휠 클래스에 매핑.
3. **애니메이션 BP 수정**: `WheelHandler` 노드 삭제 → `WheelController` 노드로 교체.
4. **블루프린트 참조 갱신**: `WheeledVehicleMovementComponent4W`(PhysX) 참조하던 모든 BP
   그래프를 `ChaosWheeledVehicleMovementComponent` 참조로 재작성.

즉 **본 구조/스켈레탈 메시/피직스 애셋은 그대로 재사용 가능**하고, 갈아끼우는 건 무브먼트
컴포넌트 종류와 휠 BP 클래스, 애니메이션 노드뿐 — M1A2가 원래 PhysX용으로 설계된 본 구조를
썼더라도 Chaos로 잘 작동하는 이유가 여기서 설명됨.

출처: [How to Convert PhysX Vehicles to Chaos in Unreal Engine](https://dev.epicgames.com/documentation/en-us/unreal-engine/how-to-convert-physx-vehicles-to-chaos-in-unreal-engine)

---

## 4. 물리 시뮬레이션 틱 흐름 (Async Physics)

공식 API 문서는 `TickVehicle`/`UpdateSimulation` 등 내부 함수의 상세 흐름을 문서화하지
않음(헤더/소스 직접 참조 필요, 확인 못함). 다만 UE5의 **Async Physics** 아키텍처 자체는
커뮤니티 자료로 다음과 같이 확인됨:

- UE5는 `Tick Async Physics`를 켜면 물리 시뮬레이션이 게임 스레드와 분리된 **별도 물리
  스레드**에서 고정 타임스텝(constant delta time)으로 도는 구조로 전환 가능.
- 게임 스레드 ↔ 물리 스레드 데이터 교환은 Chaos가 관리하는 `FSimCallbackInput`/
  `FSimCallbackOutput` 버퍼(락프리 큐)를 통해 프레임의 특정 시점에만 이루어짐.
- Chaos Vehicle(특히 Modular Vehicle 플러그인 계열)은 휠/서스펜션 계산을 이 비동기 트리
  안에서 수행하고, 입력은 게임 스레드에서 캡처해서 `FAsyncInputPhysicsPawn` 같은 구조로
  물리 스레드에 전달.
- **실무 시사점**: `SetThrottleInput`/`SetYawInput` 등 BP/C++에서 호출하는 입력 setter는
  "이번 프레임에 즉시 반영"이 아니라 "다음 물리 스텝에 버퍼로 전달"되는 구조일 가능성이
  높음 — 입력 반응이 1틱 정도 지연되는 것처럼 보이는 현상의 원인이 될 수 있음(정확한
  지연 프레임 수는 미확인 — **확인 필요**).

출처: [Taming Chaos: Stable Vehicle Suspensions with Async Physics in UE5](https://levelup.gitconnected.com/taming-chaos-stable-vehicle-suspensions-with-async-physics-in-ue5-566369c7b097) (커뮤니티 블로그, 접근 제한으로 본문 전체 확인은 못했고 검색 스니펫 기준), [Async Physics Tick 사용법 (Level Paradox)](https://levelparadox.com/2024/05/12/how-to-use-async-physics-tick-unreal-engine-5-4-c-blueprint/)

**주의**: 이 절은 공식 API 문서가 아닌 커뮤니티 자료 기반이라 확실성이 낮음. 실제 프로젝트에서
입력 지연이 문제되면 소스 코드(`ChaosVehicleMovementComponent.cpp`의 `TickComponent`/
비동기 콜백 등록 부분)를 직접 확인할 것.

---

## 5. Torque Control / Yaw Torque Scaling

M1A2 변환 작업(섹션 6, `M1A2_UGV_Conversion.md`)에서 "`SetYawInput()`은 입력 저장일 뿐이고
실제 회전 토크는 `TorqueControl.YawTorqueScaling`이 만든다"고 파악했던 내용을 공식 문서
기준으로 재확인:

`FVehicleTorqueControlConfig`의 전체 필드 (Python API 문서 기준, `UChaosVehicleMovementComponent::TorqueControl` 소속):

| 필드명 (Python 스네이크케이스) | 대응 BP 표기 | 설명 |
|---|---|---|
| `enabled` | Enabled | Torque Control 활성화 여부 |
| `yaw_torque_scaling` | Yaw Torque Scaling | **요(좌우 회전) 토크 스케일 — 조향 시 실제 회전력 크기** |
| `roll_torque_scaling` | Roll Torque Scaling | 롤 토크 스케일 |
| `pitch_torque_scaling` | Pitch Torque Scaling | 피치 토크 스케일 |
| `yaw_from_steering` | Yaw From Steering | 조향 입력이 요 토크에 기여하는 비율 |
| `roll_from_steering` | Roll From Steering | 조향 입력이 롤 토크에 기여하는 비율 |
| `yaw_from_roll_torque_scaling` | Yaw From Roll Torque Scaling | 롤 토크가 요 토크로 전이되는 비율 |
| `rotation_damping` | Rotation Damping | 회전 감쇠 |

이 구조체는 `UChaosVehicleMovementComponent` 문서에서 **"ArcadeControl" 카테고리**로
명시적으로 분류됨 — 즉 공식적으로 "아케이드 스타일의 토크 힘을 통한 차량 회전 직접 제어"라고
설명되어 있어, M1A2 문서의 결론과 정확히 일치: **`SetYawInput()`은 입력값 저장이고,
`TorqueControl.Enabled=true` + `YawTorqueScaling`이 실제 회전력의 크기를 결정하는 "아케이드
보정 계층"이다.**

**미확인 사항 (확인 필요)**:
- `enabled`/`yaw_torque_scaling`의 엔진 기본값이 정확히 얼마인지는 공식 문서에 명시 안 됨
  (M1A2 문서는 "엔진 기본값이 0/false"라고 실전에서 확인했다고 기록 — 이건 신뢰할 만한
  1차 관찰이므로 그대로 채택).
- `AddTorqueInRadians(TotalTorque, true, true)` 호출부의 정확한 소스 코드(`bAccelChange=true`
  의미: 관성 텐서 기준으로 자동 정규화된 각가속도 적용)는 GitHub/공식 문서에서 원문을
  재확인하지 못함 — M1A2 문서의 기록을 신뢰하되, 필요시 엔진 로컬 소스
  (`Engine/Plugins/.../ChaosVehiclesPlugin/Source/ChaosVehicles/Private/ChaosVehicleMovementComponent.cpp`)
  직접 열람 권장.

출처: [FVehicleTorqueControlConfig Python API](https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/VehicleTorqueControlConfig?application_version=5.0), [UChaosVehicleMovementComponent API](https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Plugins/ChaosVehicles/UChaosVehicleMovementComponent)

---

## 6. Blueprint vs C++ 차이

- **공식 문서(How to Set up Vehicles)는 BP 워크플로우만 다룸** — C++ 코드 예시가 전혀 없음.
  즉 Epic 공식 튜토리얼 수준에서는 Chaos Vehicle이 "BP로 설정하는 것"을 표준 경로로 간주.
- C++로 갈 경우 확인된 방법(포럼 기반, 확인 필요 표시): `AWheeledVehiclePawn`을 상속해서
  생성자에서 `SetDefaultSubobjectClass`로 커스텀 무브먼트 컴포넌트 지정 가능. 다만 이 프로젝트가
  이전에 시도했던 `AUGVChaosPawn`/`UUGVChaosWheel`(C++ 커스텀) 경로는 정확히 문서화된
  공식 패턴을 못 찾음 — 즉 **C++ 서브클래싱은 비공식 영역**이고, 문제가 생겨도 공식 문서로
  디버깅하기 어렵다는 뜻. (Root Body 75cm 버그, ContactPoint 붕괴 버그 모두 공식 문서에
  안 나오는 것과 같은 맥락 — 03번 문서에서 계속)
- Blueprint 함수 파라미터가 실제로는 `double` 정밀도로 생성된다는 점(M1A2 문서 4절의
  "BP 함수 파라미터 정밀도 함정")은 Chaos Vehicle 고유 이슈가 아니라 **UE5 블루프린트 시스템
  전반의 특성**(UE5부터 BP float가 전부 double) — Chaos Vehicle C++ API가 진짜 `float`를
  기대하는 지점(`ProcessEvent`로 BP 함수 호출 시)에서 특히 문제가 됨.

---

## 확인 필요 항목 (2차 조사 필요)

- Async Physics 틱에서 입력 setter 호출부터 실제 물리 반영까지의 정확한 지연 프레임 수
- `TorqueControl.Enabled`/`YawTorqueScaling`의 엔진 기본값 (공식 changelog/소스 확인 필요)
- C++로 `AWheeledVehiclePawn` 서브클래싱 시 공식 권장 패턴(공식 샘플 프로젝트 "Vehicle Game
  Template" 소스 코드 직접 확인 권장 — Epic Games Launcher/Fab을 통해서만 받을 수 있어
  웹 리서치로는 소스를 못 얻음)
