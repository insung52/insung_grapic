# UGV 궤도 잠금(Track Lock) 구현 계획

**작성** 2026-08-25 · **상태** 궤도잠금 / 스킨스티어 / 궤도 비주얼 C++ 이관 / 슬랙 물리 전부 구현 완료(실기 확인) · **대상** `BP_UGV_Vehicle`(실사용 UGV)

한쪽 궤도의 로드휠 8개를 물리적으로 하나의 회전체로 묶어, 공중에 뜬 바퀴가 드라이브트레인
전체를 잠그는 구동 불능 버그를 제거한다.

읽기 좋은 페이지 버전: https://claude.ai/code/artifact/0e18b746-b3cd-4390-8250-2eaf51deff41

---

## 확정된 설계 결정

| 항목 | 결정 |
|---|---|
| 궤도 속도 기준 | 접지 바퀴의 **하중 가중 평균**. 전부 공중이면 궤도를 하나의 플라이휠로 보고 관성 적분 |
| 착지 처리 | **Level 1** — 감속 방향만 변화율 제한. 회전 관성→차체 운동량 변환(Level 2)은 후속 |
| 주입 지점 | `ApplyWheelFrictionForces` override 1개 (바퀴 `Simulate()` 직후) |
| 토크 배분 | 궤도 단위 50:50, 궤도 안에서는 접지 바퀴에 하중 비례 |
| 엔진 수정 | 없음 — 전부 프로젝트 모듈 내 상속 |

---

## 1. 배경 — 무엇을 고치는가

증상: 한쪽 궤도가 장애물에 걸쳐 앞바퀴들이 뜬 상태에서 W/S가 완전히 먹지 않고, A/D만 정상
동작. 원인은 소스 레벨에서 확인된 3단계 연쇄다.

1. **RPM 소스가 바퀴 하나다.** `ProcessMechanicalSimulation`의 RPM 수집 루프는 `FMath::Max`가
   아니라 덮어쓰기라, 차량 전체 엔진 RPM이 **배열 마지막 구동륜 `R_Wheel_08`** 하나에서만 나온다.
2. **임계를 넘으면 16개 전부 토크 0.** `if (WheelSpeedRPM > MaxRPM) TransmissionTorque = 0.f;`
   — 스칼라 하나가 전 바퀴에 배분되므로 접지 여부와 무관하게 동력을 잃는다.
   `GetTorqueFromRPM`에도 같은 하드컷이 하나 더 있다(`|RPM - MaxRPM| < 1.0` → 0).
3. **한 번 걸리면 안 풀린다.** 공중 바퀴 각속도 적분에 감쇠 항이 없어(`Omega += SlipOmega`),
   토크가 0이 되는 순간 회전수가 얼어붙고 → 토크는 계속 0으로 유지된다.

이 프로젝트 값(`MaxRPM=1000`, 1단 총 기어비 `2.85 × 1.5 = 4.275`)에서 토크 컷 임계는 휠
**234 RPM**, 공중 바퀴는 `MaxWheelspinRotation=30 rad/s` → **286 RPM**까지 올라간다.
2단 임계(330 RPM)는 안 넘지만 토크가 0이라 가속을 못 하니 `ChangeUpRPM=800`에 영원히 도달하지
못하는 **1단 잠금**이 된다.

A/D가 되는 이유: `SetYawInput` → `ApplyTorqueControl`이 `AddTorqueInRadians`로 차체 강체에 직접
토크를 건다(`YawTorqueScaling=5.0`). 드라이브트레인도 접지 검사도 거치지 않는다.

> README §4의 기존 이슈 "**UGV 공중에 뜬 바퀴가 계속 회전**"은 별개 문제가 아니라 위 ③의 다른
> 얼굴이다. 감쇠 항을 우리가 소유하게 되면서 같이 사라진다.

`ABP_UGV_Vehicle`은 이미 16개 본을 `WheelRotL`/`WheelRotR` 두 값으로만 돌린다. **비주얼은 이미
"한쪽 8개 = 하나"를 가정하고 있고 물리만 16개 독립**이므로, 이 작업은 물리를 비주얼이 이미
가정한 모델에 맞추는 일이다.

---

## 2. 실현 가능성 검증 결과

| 필요 조건 | 확인 내용 | 판정 |
|---|---|---|
| `UChaosWheeledVehicleSimulation` | `CHAOSVEHICLES_API` export — 게임 모듈에서 상속 가능 | 가능 |
| `ApplyWheelFrictionForces` | `virtual`, 내부에서 `PWheel.Simulate(DeltaTime)` 호출(접지·공중 양쪽) | 가능 |
| `CreatePhysicsVehicle` | `virtual`, 본문 3줄 | 가능 |
| `SetDefaultSubobjectClass` | `WheeledVehiclePawn.h` 클래스 주석이 이 패턴을 공식 문서화 | 가능 |
| 필요 API | `SetAngularVelocity`/`GetAngularVelocity`/`GetWheelLoadForce`/`InContact`/`GetDriveTorque`/`SetDriveTorque` 전부 존재 | 가능 |
| `Build.cs` | `ChaosVehicles` 이미 포함 | 불필요 |
| BP 리페어런트 | 1.5MB BP, 컴포넌트 프로퍼티 오버라이드 다수 | **유일 리스크** |

**쓸 수 없는 것 — 기존 이동거리 기반 궤도 로직(`ChassisDistanceL/R`).** 한쪽 궤도가 전부 뜨면
기준 자체가 사라지는 데다, BP는 게임 스레드 변수이고 이 코드는 **물리 스레드 비동기 콜백**에서
돈다. 서브스텝 때문에 한 프레임에 여러 번 돌 수도 있어 데이터 레이스이자 한 프레임 늦은 값이
된다. 궤도 속도는 PT에서 자체 계산해야 한다.

---

## 3. 알고리즘

물리 틱 순서: `ProcessMechanicalSimulation`(토크 배분·RPM 읽기) → `ApplySuspensionForces`
(하중·접지 갱신) → `ProcessSteering` → `ApplyWheelFrictionForces`(Simulate·마찰력).

마지막 단계를 감싸면 **하중과 접지가 이미 갱신된 상태**에서 작업할 수 있고, 다음 프레임 ①이
읽는 RPM도 자동으로 정상화되어 `ProcessMechanicalSimulation`은 건드릴 필요가 없다.

```cpp
// 좌/우 분류는 Suspension[i].GetLocalRestingPosition().Y 부호로 최초 1회 캐시
void UUGVWheeledVehicleSimulation::ApplyWheelFrictionForces(float DeltaTime)
{
    if (!GTrackLock.Enabled) { Super::ApplyWheelFrictionForces(DeltaTime); return; }
    EnsureSideIndexCached();

    // ── ① 구동토크 재배분 (Super 호출 전) ─────────────────────────
    //    ProcessMechanicalSimulation이 방금 16개에 1/16씩 균등 배분해둔 상태
    if (GTrackLock.RedistributeTorque)
    {
        float Total = 0.f;
        for (auto& W : PVehicle->Wheels) Total += W.GetDriveTorque();
        const float PerSide = Total * 0.5f;

        for (int S = 0; S < 2; ++S)
        {
            float SumLoad = 0.f;
            for (int i : SideWheels[S])
                if (PVehicle->Wheels[i].InContact())
                    SumLoad += PVehicle->Wheels[i].GetWheelLoadForce();

            for (int i : SideWheels[S])
            {
                auto& W = PVehicle->Wheels[i];
                W.SetDriveTorque(SumLoad > KINDA_SMALL_NUMBER
                    ? (W.InContact() ? PerSide * W.GetWheelLoadForce() / SumLoad : 0.f)
                    : PerSide / SideWheels[S].Num());   // 전부 공중 → 균등
            }
        }
    }

    // ── ② 엔진 원본: 바퀴별 Simulate + 마찰력을 차체에 적용 ────────
    Super::ApplyWheelFrictionForces(DeltaTime);

    // ── ③ 궤도 각속도 통일 (Super 호출 후) ────────────────────────
    for (int S = 0; S < 2; ++S)
    {
        float SumW = 0.f, SumWOmega = 0.f, SideDrive = 0.f, SideInertia = 0.f;
        for (int i : SideWheels[S])
        {
            auto& W = PVehicle->Wheels[i];
            SideDrive   += W.GetDriveTorque();
            SideInertia += CachedWheelInertia[i];       // 0.5 * WheelMass * WheelRadius²
            if (W.InContact())
            {
                const float L = W.GetWheelLoadForce();
                SumW      += L;
                SumWOmega += L * W.GetAngularVelocity();
            }
        }

        float Target;
        if (SumW > KINDA_SMALL_NUMBER)
        {
            Target = SumWOmega / SumW;                  // 하중 가중 평균
        }
        else                                            // 전부 공중 — 지면 기준 없음
        {
            Target  = TrackOmega[S] + (SideDrive / SideInertia) * DeltaTime;
            Target -= Target * GTrackLock.AirDamping * DeltaTime;
        }

        // Level 1 — 감속 방향만 변화율 제한 (착지 팝 방지)
        if (FMath::Abs(Target) < FMath::Abs(TrackOmega[S]))
        {
            const float MaxStep = GTrackLock.SpinDownDecel * DeltaTime;
            Target = FMath::Clamp(Target, TrackOmega[S] - MaxStep, TrackOmega[S] + MaxStep);
        }

        TrackOmega[S] = Target;
        for (int i : SideWheels[S]) PVehicle->Wheels[i].SetAngularVelocity(Target);
    }
}
```

### 설계 근거

- **하중 가중인 이유.** 살짝만 닿은 바퀴가 궤도 속도를 지배하면 안 된다. 장애물 케이스에서
  하중을 다 받는 뒷바퀴가 지배하게 되는 것이 물리적으로 맞고, 막 닿기 시작한 바퀴는 하중≈0이라
  가중치≈0 → 접촉 전이가 연속적이다. 단순 평균은 접지 개수가 바뀔 때마다 계단식으로 점프한다.
- **슬립이 보존된다.** 접지 바퀴가 미끄러지는 중이면 그 바퀴 Ω에 슬립분이 이미 들어 있어,
  궤도 속도가 차체 속도보다 높게 나온다. 헛도는 연출이 살아있다.
- **감속 방향만 제한하는 이유.** Level 1의 목적은 착지 순간의 큰 감속 하나다. 양방향으로 걸면
  정상 가속 응답까지 둔해진다.
- **토크 재배분이 필요한 이유.** `TorqueRatio = 1.f / GetNumDrivenWheels()`가 접지와 무관하게
  1/16 고정이라, 8개가 떠 있으면 구동토크 절반이 허공에서 버려진다. Ω만 통일해서는 안 고쳐진다.

### 빌드에서 실제로 걸린 함정

**`Wheel.Setup()`을 호출하면 `LNK2019`가 난다.** `TVehicleSystem`은 API 매크로가 없는 순수
템플릿인데, 이를 상속하는 `FSimpleWheelSim`이 `CHAOSVEHICLESCORE_API`로 export되면서 MSVC가
베이스 템플릿 멤버까지 dllimport로 취급한다. 그런데 그 인스턴스화가 `ChaosVehiclesCore.dll`에
실제로 export되어 있지 않다. 대신 **`Wheel.SetupPtr`을 직접 쓴다** — 데이터 멤버라 링키지가
없고, `VehicleSystemTemplate.h`가 주석으로 이 사용법을 안내한다("Setup data pointer is public
if you want to use it directly"). 엔진 플러그인 내부 코드는 같은 모듈이라 `Setup()`을 그냥
쓰지만, 게임 모듈에서 상속할 때는 못 쓴다.

### 그 외 확인할 것

`FSimpleWheelSim::Inertia`에는 public getter가 없다. `Setup().WheelMass` / `Setup().WheelRadius`로
`0.5 * m * r²`을 직접 캐시할 것(엔진 생성자와 동일한 식). `SetDriveTorque`는 내부 `DriveTorque`를
쓰므로, BP_UGV_Wheel의 `ExternalTorqueCombineMethod`가 `None`인 현재 상태에서는 `Simulate()`가
우리 값을 덮어쓰지 않는다. **이 값을 바꾸면 재배분이 무력화되니 주의.**

---

## 4. 파일 구성

| 파일 | 클래스 | 역할 |
|---|---|---|
| `Vehicles/UGVWheeledVehicleSimulation.h/.cpp` | `UUGVWheeledVehicleSimulation : UChaosWheeledVehicleSimulation` | 위 override. `TrackOmega[2]`, `SideWheels[2]`, `CachedWheelInertia` 상태 보유. 콘솔 변수 정의 |
| `Vehicles/UGVWheeledVehicleMovementComponent.h/.cpp` | `UUGVWheeledVehicleMovementComponent : UChaosWheeledVehicleMovementComponent` | `CreatePhysicsVehicle()` override — `MakeUnique<UUGVWheeledVehicleSimulation>()`로 교체 후 `UChaosVehicleMovementComponent::CreatePhysicsVehicle()` 호출. 비주얼 연동용 BP 노출 `GetTrackAngularVelocity(Side)` / `GetTrackLinearSpeed(Side)` 포함 |
| `Vehicles/UGVWheeledVehiclePawn.h/.cpp` | `AUGVWheeledVehiclePawn : AWheeledVehiclePawn` | 생성자에서 `ObjectInitializer.SetDefaultSubobjectClass<…>(AWheeledVehiclePawn::VehicleMovementComponentName)`. BP_UGV_Vehicle의 새 부모 |

기존 `UGVChaosPawn` / `UGVChaosWheel`은 건드리지 않는다. 현재 안 쓰이는 옛 경로이고 설계가
다르다(그쪽은 `ExternalTorqueCombineMethod=Override` 기반 per-wheel 토크).

---

## 5. 튜닝 — 콘솔 변수

엔진의 `p.Vehicle.*`와 같은 `FAutoConsoleVariableRef` 패턴. GT→PT 마샬링 불필요, PIE에서 즉시
A/B 비교 가능, BP 수정 불필요.

| 변수 | 단위 | 초기값 | 의미 |
|---|---|---|---|
| `p.UGV.TrackLock.Enabled` | 0/1 | 1 | 전체 on/off. **런타임 킬스위치 겸용** |
| `p.UGV.TrackLock.RedistributeTorque` | 0/1 | 1 | ①번 토크 재배분만 따로 끄기 |
| `p.UGV.TrackLock.SpinDownDecel` | rad/s² | 120 | 착지 감속률 상한. 120이면 30 rad/s → 0에 약 0.25초 |
| `p.UGV.TrackLock.AirDamping` | 1/s | 1.5 | 공중 궤도 회전 감쇠율. 손 떼고 약 2~3초에 정지 |

초기값은 계산으로 잡은 출발점이며 실측으로 조정한다.

---

## 6. 실행 순서

각 단계가 끝날 때마다 게임이 정상 동작해야 한다. 되돌릴 지점을 단계 경계에 맞추기 위한 구성.

### 01. C++ 3개 클래스 추가 — 게임 동작 변화 없음

클래스만 추가하고 BP는 아직 리페어런트하지 않는다. 이 시점엔 새 클래스를 아무도 안 쓰므로
**게임 동작이 100% 이전과 같아야 한다.** 빌드 통과 + 기존 주행 정상이면 통과.

> 빌드는 사용자가 직접 수행. Live Coding으로는 새 UCLASS가 안 잡히므로 에디터를 닫고 풀 빌드.

### 02. 기능은 끈 채로 BP 리페어런트

`p.UGV.TrackLock.Enabled` 기본값을 **0으로 두고** 리페어런트한다. "리페어런트가 깨뜨린 것"과
"새 로직이 바꾼 것"을 분리해서 진단하기 위함.

1. P4에서 `BP_UGV_Vehicle.uasset` 체크아웃
2. Class Settings → Parent Class → `UGVWheeledVehiclePawn`
3. 컴파일 → 저장
4. 아래 **보존 검증 스냅샷** 표로 값 대조
5. 평지 주행이 리페어런트 전과 동일한지 확인

### 03. 기능 활성화 및 튜닝

`p.UGV.TrackLock.Enabled 1`로 켜고 검증 체크리스트를 돈다. 감속률·감쇠율을 실측으로 조정한 뒤
기본값으로 굳히고, 그때 `Enabled` 기본값도 1로 바꾼다.

---

## 7. 리페어런트 보존 검증 스냅샷

작업 전 `BP_UGV_Vehicle.uasset`에서 직접 읽은 현재 값. 리페어런트 후 그대로인지 대조할 것.

| 위치 | 프로퍼티 | 값 |
|---|---|---|
| EngineSetup | `MaxRPM` | 1000 |
| EngineSetup | `EngineIdleRPM` | 100 |
| EngineSetup | `MaxTorque` | 500 |
| EngineSetup | `TorqueCurve` | FC_Torque_UGV |
| TransmissionSetup | `ForwardGearRatios` | 2.85 / 2.02 / 1.35 / 1.0 / 0.8 |
| TransmissionSetup | `FinalRatio` | 1.5 |
| TransmissionSetup | `ChangeUpRPM` / `ChangeDownRPM` | 800 / 400 |
| TransmissionSetup | `GearChangeTime` | 0.3 |
| DifferentialSetup | `DifferentialType` | AllWheelDrive |
| TorqueControl | `YawTorqueScaling` | 5.0 |
| TorqueControl | `YawFromSteering` | 1.0 |
| Vehicle Setup | `ChassisWidth` / `ChassisHeight` | 289 / 175 |
| Vehicle Setup | `bEnableCenterOfMassOverride` | true |
| WheelSetups | 개수 / 순서 | 16 · L_Wheel_01–08 → R_Wheel_01–08 |
| WheelSetups | `WheelClass` (전체) | BP_UGV_Wheel_C |

무브먼트 컴포넌트 클래스가 `UGVWheeledVehicleMovementComponent`로 바뀌었는지도 확인.
안 바뀌었다면 `SetDefaultSubobjectClass`가 안 먹은 것이므로 그 자리에서 멈추고 롤백.

---

## 8. 검증 체크리스트

### 버그 재현 시나리오

- [ ] 장애물에 한쪽 궤도를 걸친 상태에서 **W/S가 반응한다** (핵심 판정)
- [ ] `showdebug vehicle`에서 **RPM이 1000에 고착되지 않는다** — 고착 여부가 이 버그의 지문
- [ ] W를 뗐을 때 RPM이 정상적으로 떨어진다
- [ ] 공중에 뜬 바퀴가 **몇 초 안에 회전을 멈춘다** (README §4 기존 이슈)
- [ ] 착지 순간 궤도 속도가 한 프레임에 튀지 않는다 (Level 1 확인)
- [ ] 한쪽 궤도 8개 바퀴 회전이 육안으로 완전히 동기화

### 회귀 — 기능이 꺼져 있을 때와 같아야 하는 것

- [ ] 평지 가속 곡선·최고속도·정지거리 동일
- [ ] A/D 선회 감각 동일 (TorqueControl 경로라 영향 없어야 정상)
- [ ] 변속(1→5단) 정상
- [ ] `SetUGVFromTankMode Auto` + `MoveUGVFromTankTo` 자율주행 정상
- [ ] 커브 선행 감속(`2026-08-22_ugv_corner_braking_dev_guide.md`) 동작 유지
- [ ] `BeginScenarioEnemyContact` 전체 시나리오 완주
- [ ] 대시보드 엔진 RPM·기어 표시 정상

### 별도 확인 필요 — 리플리케이션

`TrackOmega[2]`는 PT에 사는 우리 상태인데 Chaos 네트워크 예측의 rewind 상태에는 포함되지 않는다.
리심이 일어나면 stale 값을 쓰게 된다. `replication/replication_audit.md`에 아직 안 끝난 차량
`HasAuthority()` 게이팅 항목이 있으므로 교차 확인할 것. 리슨서버 2인 테스트로 클라 쪽 궤도
거동을 육안 확인하는 것이 최소 검증.

---

## 9. 롤백

- **즉시(재빌드 없이)** — `p.UGV.TrackLock.Enabled 0`. 코드는 두고 기능만 끈다. 데모 중 문제가
  생기면 이걸 쓴다.
- **BP만 되돌리기** — P4에서 `BP_UGV_Vehicle.uasset` revert → 부모가 `WheeledVehiclePawn`으로
  복귀. C++ 클래스는 남아 있어도 아무도 안 쓰므로 무해.
- **전체 되돌리기** — BP revert + 소스 3쌍 삭제 후 재빌드.

단계 01과 02가 나뉜 이유가 이것이다. 02에서 문제가 생기면 BP만 되돌리면 되고 01로 갈 필요가 없다.

---

## 10. 이번 범위 밖 (후속)

| 항목 | 내용 |
|---|---|
| **Level 2** 착지 운동량 전달 | 감속 토크를 종방향 힘으로 차체에 전달해 "착지하며 앞으로 확 나가는" 물리 구현. 궤도 각속도 상태가 생긴 뒤라 얹기 쉬움. 현재 값 기준 상한은 궤도당 약 0.79 m/s(2.8 km/h), 양쪽 5.7 km/h — 체감되는 크기 |
| **WheelMass 재검토** | `WheelMass=80kg × 16 = 1280kg`인데 차체 `Mass=1500kg`의 85%. Chaos가 이 값을 차체 질량에 더하지 않고 회전 관성에만 쓰기 때문에 지금까진 안 드러났지만, Level 2로 가면 곧바로 착지 충격 크기가 된다. C++ `UGVChaosWheel`은 같은 자리에 20kg 사용 |
| **궤도 비주얼 연동** (보고된 문제 2) | 현재 `WheelRotL/R`은 BP가 따로 계산한 값이라 서스펜션·슬립과 무관하게 굴러간다. **C++ 훅은 이미 넣어둠** — `GetTrackAngularVelocity(Side)` / `GetTrackLinearSpeed(Side)`가 BlueprintPure로 노출되어 있으므로, BP에서 `WheelRotL/R` 계산과 궤도 스크롤의 입력만 이 값으로 갈아끼우면 된다. 남은 건 BP 작업 |
| **진짜 스킨스티어** | 지금 A/D는 차체에 직접 yaw 토크를 거는 `TorqueControl`(`YawTorqueScaling=5.0`)이라 접지와 무관. 궤도 단위 토크 배분이 생겼으니 좌우 토크 차등으로 대체할 여지가 열린다. 다만 주행 감각이 통째로 바뀌므로 별도 과제 |
| **SpringPreload / DampingRatio** | BP_UGV_Wheel의 `SpringPreload=180`은 UE 5.8에서 소비되지 않는 죽은 값(솔버에서 주석 처리). `SuspensionDampingRatio=6.0`은 문서상 범위 0~1의 6배. 이번 작업과 무관하지만 서스펜션 손댈 때 재확인 대상 |

---

근거: UE 5.8 엔진 소스(`ChaosWheeledVehicleMovementComponent` / `WheelSystem` / `EngineSystem` /
`TransmissionUtility`)와 `BP_UGV_Vehicle.uasset` · `BP_UGV_Wheel.uasset`에서 직접 읽은 저장값 기준.


---

# 부록 — 구현하며 실제로 걸린 것들 (2026-08-25)

계획 단계에서 예상 못 했던 함정들. 대부분 원인이 엉뚱한 곳에 있어서 두세 번씩 헛짚었다.

## A-1. 리페어런트 대신 복제본으로 진행

원본 `BP_UGV_Vehicle`을 리페어런트하지 않고 복제본을 만들어 A/B 비교가 가능하게 했다.
갈라질 리소스는 처음부터 같이 복제했다.

| 에셋 | 비고 |
|---|---|
| `BP_UGV_Vehicle_new` | 부모 = `AUGVWheeledVehiclePawn` |
| `BP_UGV_Wheel_new` | 16개 휠 전부 이걸 참조 |
| `BP_UGVAIController_new` | 부모는 여전히 C++ `AUGVAIController`, BP 튜닝값만 분리 |
| `ABP_UGV_Vehicle_new` | 아래 A-2 때문에 필수 |

**게임모드가 새 차량을 인식하게 하려면** `BP_TestPlayerController`의 Class Defaults →
`Vehicle Select → UGV Vehicle Class`를 바꾸면 된다. `FindUGVFromTankInstance()`가 UGV를 찾는
유일한 경로이고 콘솔 명령/대시보드/시나리오가 전부 이걸 거친다. 두 대를 레벨에 같이 두고
이 프로퍼티만 토글해 A/B 전환이 가능하다(둘은 형제 클래스라 서로 안 집힌다).

## A-2. ABP가 구 클래스로 하드 캐스트 — 복제 시 반드시 같이 처리

`ABP_UGV_Vehicle`의 `EventBlueprintUpdateAnimation`이 `CastToBP_UGV_Vehicle`로 폰을 캐스트해서
`WheelRotL/R`·`TurretYaw`·`GunPitch`·`BarrelSpinAngle`을 읽는다. 복제본은 원본의 **자식이 아니라
형제**라 이 캐스트가 실패하고, 바퀴 회전과 터렛/건/배럴이 통째로 멈춘다(궤도 링크는 폰 BP가
직접 돌려서 계속 움직이므로 "바퀴는 멈췄는데 궤도는 돈다"는 기묘한 증상이 된다).

`ABP_UGV_Vehicle_new`를 만들고 캐스트를 `CastToBP_UGV_Vehicle_new`로 교체 후
`VehicleMesh.AnimClass`를 새 ABP로 지정했다. 참고로 `retarget_node_class` MCP 툴은 새 출력 핀만
추가하고 기존 연결을 안 옮기므로, DSL로 이벤트를 다시 쓰는 편이 확실하다.

## A-3. 제자리선회가 0.5~1초 만에 멈추던 진짜 원인 — Chaos 슬립 판정

**이번 작업에서 가장 오래 헤맨 것.** `p.UGV.*` 튜닝이 하나도 안 먹어서 원인을 두 번 헛짚었다
(엔진브레이크 → ABP 캐스트 → 실제로는 슬립).

`UChaosVehicleMovementComponent::ProcessSleeping`의 깨움 판정에서 **조향만 유독 '변화량'을 본다**:

```cpp
(ControlInputs.ThrottleInput >= ControlInputWakeTolerance)             // 값
(ControlInputs.BrakeInput    >= ControlInputWakeTolerance)             // 값
(FMath::Abs(ControlInputs.SteeringInput - PrevSteeringInput) >= ...)   // 델타!
(RollInput / PitchInput / YawInput >= ControlInputWakeTolerance)       // 값
```

A를 누르고 있으면 입력이 1.0에 포화된 순간부터 "입력 없음"이 된다. 게다가 잠들 조건은
**선속도만** 보므로(`SleepThreshold=10cm/s`) 각속도만 있는 제자리선회는 '정지'로 분류된다.
`SleepCounterThreshold`(15**프레임**) 뒤 차량이 잠들고,
`UChaosVehicleSimulation::TickVehicle`의 `if (!VehicleState.bSleeping)` 때문에 우리 시뮬까지
통째로 스킵된다.

관찰된 증상이 전부 이걸로 설명된다 — 램프업 동안만 회전 / 손 떼면 잠깐 움직임 / W·S로 조금이라도
굴러가면 정상 / 저fps에서 간격이 길어짐(프레임 카운터라서) / cvar 전부 무효.

**수정**: `UUGVWheeledVehicleMovementComponent::ProcessSleeping` override에서 조향 유지 중 슬립 무효화.
`p.UGV.KeepAwakeWhileSteering`(기본 1).

## A-4. 엔진 RPM이 세 군데로 새어나간다

`ProcessMechanicalSimulation`의 단일 바퀴 RPM 오염은 구동토크 컷뿐 아니라 **자동변속 판정**과
**엔진 브레이크 세기**(`EngineBraking = EngineRPM * EngineBrakeEffect`)에도 쓰인다. 스로틀이 0인
A/D 단독 조작에서 엔진 브레이크가 켜지고, `FSimpleWheelSim::Simulate`의
`bool Braking = BrakeTorque > FMath::Abs(DriveTorque)`가 브레이크가 조금이라도 넘으면 구동력을
**섞지 않고 통째로 버린다**(절벽).

**수정**: `ProcessMechanicalSimulation` override에서 드라이브트레인 회전수를 **좌우 궤도 평균**으로
바꿔치기(Omega 임시 교체 → Super 호출 → 원복). 실제 궤도차량 변속기 출력축이 좌우 평균인 것과 같다.
제자리선회면 평균 0이라 엔진이 아이들에 머문다.

> 부작용: 제자리선회 중 엔진 RPM이 안 오른다. 물리적으로는 이게 맞지만 **사운드는 부자연스럽다.**
> 메타사운드는 엔진 RPM 대신 `GetTrackLinearSpeed` 좌우 절댓값의 최댓값에 물리는 게 맞다.

## A-5. 빌드 함정 — `Setup()` 호출 시 LNK2019

`TVehicleSystem`은 API 매크로가 없는 순수 템플릿인데 이를 상속하는 `FSimpleWheelSim`이
`CHAOSVEHICLESCORE_API`로 export되면서 MSVC가 베이스 템플릿 멤버를 dllimport로 취급한다.
그 인스턴스화가 DLL에 export되어 있지 않아 게임 모듈에서 `Wheel.Setup()`을 부르면 링크가 깨진다.

**대신 `Wheel.SetupPtr`을 직접 쓴다** — 데이터 멤버라 링키지가 없고, `VehicleSystemTemplate.h`가
주석으로 이 사용법을 안내한다. `FSimpleSteeringSim::GetSteeringFromVelocity`도 내부에서 `Setup()`을
타므로 같은 이유로 못 쓴다(그래서 속도 기반 조향 감쇠를 직접 구현했다).

## A-6. 스킨스티어 (yaw 토크 완전 제거)

기존 조향은 BP가 `SetYawInput` → `ApplyTorqueControl`이 차체에 직접 요 토크를 걸었다.
`bAccelChange=true`라 질량·속도·접지와 무관하게 **항상 같은 각가속도**였고(고속 코너 이탈의 원인),
차량에 세팅된 `SteeringCurve`(0→1.0, 20→0.8, 60→0.4, 120→0.3)는 `SteeringInput` 기반 바퀴
조향각에만 적용되므로 **한 번도 쓰이지 않았다.**

**수정**:
- `TorqueControl.Enabled = false`, 모든 스케일 0
- BP `SetManualControl`: `SetYawInput(부호뒤집기)` → `SetSteeringInput(TurnInput)`
- 좌우 궤도 차동 토크로 회전. 엔진 토크를 나누는 게 아니라 **별도로 얹는다**(스로틀 0에서도
  제자리선회가 되어야 하므로)
- 속도 감쇠는 cvar로 직접 구현

```
p.UGV.SkidSteer.TorqueNm 900 / FalloffStartKmh 5 / FalloffEndKmh 45 / FalloffMinScale 0.25
p.UGV.SkidSteer.FlipInReverse 1        (후진 시 A/D 반대 — 기존 BP 동작 유지)
```

> 차동 토크는 그냥 두면 진행 방향과 무관하게 같은 쪽으로 돈다(좌측에 항상 +가 실리므로).
> 기존 BP가 손으로 뒤집던 동작이라 옵션으로 되살렸다. 물리적 정답이 있는 문제가 아니라 조작 매핑 취향.

## A-7. 프레임률 상한 — `[SystemSettings]`도 `t.MaxFPS`도 단독으로는 안 먹는다

두 단계로 막혔다.

1. **`[SystemSettings]`는 UE5에서 cvar 섹션이 아니다.** UE4의 `FSystemSettings`가 제거돼서 그 섹션을
   cvar로 읽는 코드가 엔진에 없다. 정식 경로는 `DefaultEngine.ini`의 **`[ConsoleVariables]`**
   (`FConfigCacheIni::LoadConsoleVariablesFromINI`가 `ECVF_SetBySystemSettingsIni`로 적용).
2. **그래도 안 먹는다.** 엔진 초기화 뒤쪽에서 `UGameUserSettings::ApplyNonResolutionSettings`가
   `SetFrameRateLimitCVar(FrameRateLimit)` → `GEngine->SetMaxFPS(...)`로 `t.MaxFPS`를 덮어쓴다.
   `FrameRateLimit` 기본값이 0이라 60이 지워졌다.

**최종**: `Config/DefaultGameUserSettings.ini`에 `FrameRateLimit=60.000000`. 각 PC의
`Saved/Config/<Platform>/GameUserSettings.ini`에 저장값이 있으면 그쪽이 이기므로 배포 시 주의.
인게임 Settings 위젯 Graphics 탭의 프레임 상한도 이 경로를 그대로 쓰면 된다.

적용 확인은 콘솔에 값 없이 `t.MaxFPS`.

## A-8. 궤도/바퀴 비주얼을 물리에 연결

기존 EventGraph는 **차체 이동을 적분해서** 궤도 거리를 만들었다:
```
XMoveL/R += ForwardSpeed * dt         (좌우 공용)
ZRotL/R  += dYaw * (-/+25.2)          (요 회전에서 역산한 좌우 차이)
DistanceL/R = XMove + ZRot
WheelRotL/R = Distance / 12.37 * -57.29578
```
차체가 움직인 거리지 궤도가 돈 거리가 아니라, 제자리선회나 공중 헛돌기를 표현할 수 없었다.

**수정**: `XMove` 누적 입력을 `GetTrackLinearSpeed(Side) * dt`로 교체하고 `ZRot` 델타는 0으로
끊었다(요 성분이 궤도 속도에 이미 포함되어 이중 계산이 되므로). 궤도 링크 스크롤도 같은
`ChassisDistance`를 읽으므로 바퀴 회전과 자동으로 같은 소스를 보게 됐다.

C++ 접근자는 폰(`AUGVWheeledVehiclePawn`)과 무브먼트 컴포넌트 양쪽에 있다. **BP에서는 폰 쪽을 쓸 것** —
컴포넌트 쪽은 서브클래스 캐스트가 필요해 impure 캐스트 노드를 실행 체인에 끼워야 한다.
MCP `create_node`로 만들 때 `declaring_class`를 폰으로 명시하지 않으면 컴포넌트 오버로드가 잡힌다.

## A-9. 서스펜션 → 궤도 비주얼 (진행 중)

BP는 이미 매 틱 `WheelsZOffsets[0..15]`를 채우고 있었다:
```
WheelsZOffsets[i] = 7.5 - (GetWheelState(i).NormalizedSuspensionLength * 12.5)
```

**두 가지 문제:**

1. **상수가 stale.** `BP_UGV_Wheel_new`가 `MaxRaise=10 / MaxDrop=5`로 커스텀되어 총 트래블이 15인데
   공식은 7.5 / 12.5(옛 값 7.5+5) 그대로다. 기준점도 스케일도 틀렸다. 휠 값을 바꾸면 같이 바꿔야 하는
   하드코딩이라, C++ 이관 시 `MaxRaise`/`MaxDrop`에서 직접 읽게 만든다.
2. **소비처가 4개뿐.** 인덱스 0/7/8/15(각 궤도 첫·마지막 바퀴)만 읽고, 그것도 **바닥면이 아니라
   감김부**(스플라인 점 2,3,7,8)에 적용된다. 바닥면(점 9,10,0,1)은 아예 갱신되지 않아 Z=0 고정이다.

**스플라인 실제 형태** (좌측, 11점 닫힌 루프. Construction Script가 절차적으로 생성):

| 점 | X | Z | 구간 |
|---|---|---|---|
| 9, 10, 0, 1 | 94.2 / 4.2 / 0.0 / −95.9 | 0 | 바닥면 (갱신 안 됨) |
| 2, 3 | −127, −155 | 22, 54 | 후방 감김 |
| 4, 5, 6 | −158, 8, 162 | 95, 95, 90 | 윗면 (새그 모델) |
| 7, 8 | 155, 128 | 53, 23 | 전방 감김 |

바닥면이 실질 3점(10과 0이 4cm 간격으로 중복)이라 로드휠 8개를 표현할 해상도가 없다.

**결정**: 스플라인 구축·갱신을 C++로 이관. 점 배치를 `GetWheelRestingPosition(WheelSetups[i])`에서
생성해 하드코딩 좌표와 인덱스를 없앤다. 영향 범위는 확인 완료 —

- C++ 코드 의존성 없음(`ScenarioStateSubsystem.cpp`에 주석 언급만)
- 내비메시 영향 없음. `TrackLinks_L/R`은 `NoCollision`이라 내비 계산 제외, 실제 장애물은 `NavObstacleBox`
- ABP는 `WheelRotL/R` 등만 읽으므로 무관
- BP는 `ChassisDistance` 적분 / `WheelRotL/R` / 궤도 링크 39개 배치 루프를 **그대로 유지**
  (링크 배치는 스플라인을 거리로 샘플링하므로 점이 바뀌어도 동작)
- 비활성화 대상: `SetLocationAtSplinePoint` 14개 + 새그 계산 체인 + Construction Script의
  하드코딩 `AddSplinePoint` 22개 (삭제하지 않고 연결만 끊어 롤백 가능하게)


---

# 부록 B — 궤도 비주얼 C++ 이관과 슬랙 물리 (2026-08-25~26)

서스펜션을 궤도에 반영하는 작업에서 시작해, 궤도 스플라인 구축/갱신을 통째로 C++로 옮기고
사인파 새그를 물리 기반 슬랙 모델로 교체하기까지의 기록.

## B-1. 최종 구조

**C++가 소유**: 스플라인 점 생성(`BuildTrackSpline`) + 매 틱 갱신(`UpdateTrackSpline`).
바닥면 점은 로드휠 위치에서 절차적으로 생성되고, 감김부/윗면 7점은 `FUGVTrackProfilePoint`
배열로 디테일 패널에 노출.

**BP가 유지**: `ChassisDistance` 적분, `WheelRotL/R`, 궤도 링크 39개 배치 루프, 터렛/건 비주얼.
기존 `SetLocationAtSplinePoint` 14개와 사인 새그 체인은 **삭제하지 않고 연결만 끊음**(롤백용).

**BP 호출**: Construction Script에서 `BuildTrackSpline(Spline, Side)`,
Tick에서 `UpdateTrackSpline(Spline, Side, ChassisDistance, DeltaTime)`.

## B-2. 스플라인 형상 (좌측 기준, 15점 닫힌 루프)

| 구간 | 점 | 좌표 | 타입 |
|---|---|---|---|
| 바닥 뒤쪽 | 0~3 | X −15.1 / −43.6 / −72.0 / −100.5, Z=BaseZ | Linear |
| 후방 감김 | 4~5 | (−127.2, 22.3) (−154.6, 53.7) | Curve |
| 윗면 | 6~8 | (−158.1, 95.4) (7.7, 95.3) (161.7, 89.9) | Curve |
| 전방 감김 | 9~10 | (155.1, 52.9) (127.6, 22.6) | Curve |
| 바닥 앞쪽 | 11~14 | X 98.7 / 70.2 / 41.8 / 13.3 | Linear |

로드휠은 X +98.7 ~ −100.5, 간격 28.5cm 균등, Y ±90.3, Z 4.9.
`BaseZ = 휠Z − WheelRadius + BottomRunZOffset`.

## B-3. 이 과정에서 걸린 함정 (전부 실측으로 확인)

**① `Wheels` 배열은 런타임 전용.** `BuildTrackSpline`은 컨스트럭션 스크립트에서 도는데 그
시점엔 `Wheels`가 비어 있다. `GetTrackWheelRadius()`가 0을 반환해서 바닥면이 바퀴 반지름만큼
통째로 위로 밀렸다(로그에 `반지름 0.00`으로 잡힘). `WheelSetups`의 클래스 기본값에서 읽는
폴백 필수 — `GetSuspensionTravel`에는 넣어놓고 반지름 쪽엔 빠뜨렸던 실수.

**② 루프 시작점(이음매)은 바닥 한가운데 두어야 한다.** 궤도 링크 39개는 스플라인 길이를
균등 분할해 배치되므로, 개수가 길이에 나누어떨어지지 않으면 시작과 끝이 만나는 곳에서
간격·각도가 어긋난다. 기존 스플라인이 X=0(바닥 가운데)에서 시작한 것이 그 이음매를 바퀴
사이에 숨기려던 설계였다. 맨 앞 바퀴로 옮겼더니 앞쪽 3개 링크의 각도가 틀어졌다.
바닥면을 앞/뒤로 쪼개 `[바닥 뒤]→감김→윗면→감김→[바닥 앞]→닫힘` 순서로 배치해 복원.

**③ 컨스트럭션 스크립트 상태를 런타임에 들고 가면 안 된다.** PIE는 에디터 월드를 복제하면서
컨스트럭션 스크립트를 **다시 돌리지 않고**, 복제 시 직렬화되는 건 `UPROPERTY`뿐이다. 순수
C++ 멤버에 인덱스 매핑을 캐시해뒀더니 PIE에서 전부 비어 바닥면 갱신이 통째로 죽었다.
→ `ComputeTrackLayout()`으로 Build/Update 양쪽에서 매번 계산.

**④ 컨스트럭션 스크립트는 PIE 시작으로 재실행되지 않는다.** 값을 바꿔도 반영이 안 되면
BP 컴파일 / 액터 이동 / 레벨 재로드 중 하나가 필요하다. 진단 중 여러 번 헷갈렸다.

**⑤ 바닥면은 `Linear`, 감김부/윗면은 `Curve`.** 실제 궤도는 로드휠 사이에서 팽팽한 직선이고,
`Curve`(auto tangent)를 쓰면 서스펜션으로 점마다 Z가 달라질 때 오버슈트가 생긴다.

**⑥ 없어진 하드코딩 상수들.** 전부 "휠 값을 바꾸면 BP도 같이 고쳐야 하는" 부류였다.

| 상수 | 정체 | 대체 |
|---|---|---|
| `7.5` / `12.5` | 옛 MaxRaise / 총 트래블 | `GetSuspensionTravel()` |
| `12.37` | 바퀴 반지름 | `GetTrackWheelRadius()` |
| `±25.2` | 궤도 반폭 환산 | 궤도 속도에 이미 포함 |
| 스플라인 좌표 22개 | 손으로 찍은 점 | 로드휠 위치에서 생성 |

## B-4. 슬랙 재분배 모델 (사인파 대체)

### 왜 사인파로는 안 되나

궤도는 **길이가 고정된 닫힌 루프**다. 처짐은 진폭의 문제가 아니라 **여유 길이(슬랙)가 어느
구간에 몰려 있느냐**의 문제다. 한쪽이 팽팽해지면 반드시 반대쪽이 늘어진다. 사인파에는 이
보존이 없어 양쪽이 따로 논다.

원본 BP에 이미 `TrackSagCurrentBias`(= 앞뒤 쏠림)라는 개념이 있었는데, 1차 이관에서 계산만
해두고 쓰지 않아 사인파만 남았던 것이 이 작업의 출발점이었다.

### 모델

궤도는 전진 시 **앞에서 바닥면으로 들어가 뒤로 빠져나간다**(차체 기준). 따라서:

| 상황 | 앞 경사면 | 뒤 경사면 |
|---|---|---|
| 가속 시작 | 공급 과잉 → **처짐** | 끌려감 → **팽팽** |
| 정속 | 구름저항분만큼 살짝 튀어나옴 | 거의 팽팽 |
| 감속·제동 | **팽팽** | **처짐** |
| 제자리선회 | 좌우 반대 | 좌우 반대 |

```
BiasTarget = clamp( Accel×InertiaGain + DriveSpeed×FrictionGain + Slip×SlipToBiasGain, ±1 )
SlackBias  = FInterpTo(SlackBias, BiasTarget, dt, BiasResponseSpeed)

FrontSlack = TotalSlack × 0.5 × (1 + SlackBias)      ← 합이 항상 TotalSlack (보존)
RearSlack  = TotalSlack × 0.5 × (1 − SlackBias)

Bow  = BowGain × sqrt(Slack)                          ← 포물선 근사
Wave = WaveGain × Slack × sin(TrackDistance×Freq + Phase)
변위 = (Bow + Wave) × SagWeight × SagDirection
```

출렁임 진폭이 슬랙에 비례하므로 **팽팽한 쪽은 저절로 떨리지 않는다.** 사인파 모델과의 결정적
차이.

### 설계에서 두 번 고친 것

**슬립 하나로 통합하려 했으나 실패.** Chaos는 접지 바퀴 각속도를 매 틱 지면 속도로 스냅한다
(`WheelSystem.cpp`: `Omega += (GroundOmega - Omega + SlipOmega)`). 그래서 궤도 표면속도와
지면속도가 구조적으로 같아지고 **슬립이 거의 0**이다. 바퀴가 실제로 헛돌 때만 값이 생긴다.
원본 BP가 관성항/마찰항을 따로 둔 이유가 이것 — 셋 다 필요하다.

**가속은 차체가 아니라 궤도 자체의 것.** 슬랙을 만드는 건 궤도 재료가 가속되며 생기는
관성이다. 바퀴가 헛돌아 차체는 안 나가고 궤도만 스핀업하는 상황, 궤도가 공중에서 도는
상황에서도 반응해야 하므로 `d(DriveSpeed)/dt`를 쓴다. 마찰항도 같은 이유로 궤도 속도 기준.

### 변위 방향

`SagDirection`이 영벡터면 그 지점 접선을 XZ에서 90도 돌려 루프 바깥쪽으로 민다. 감김부는
45도 경사라 Z로만 밀면 실제 처짐의 71%만 나오고 경사면을 따라 미끄러지는 것처럼 보인다.

## B-5. 튜닝 파라미터 전체 목록

### `BP_UGV_Vehicle_new` 디테일 → `UGV|Track`

| 값 | 기본 | 역할 |
|---|---|---|
| `Bottom Run Z Offset` | 3.17 | 궤도가 지면 위로 뜨는 높이(링크 피벗 보정). 묻히면 올림 |
| `Bottom Run Front/Rear Up Vector` | (0,0,1) | 바닥면 양 끝 링크가 눕는 방향 |
| `Rear/Top/Front ... Profile` | — | 감김부 2 / 윗면 3 / 감김부 2 점의 형상 |

프로파일 점 하나당: `Offset`(X,Z) / `UpVector` / `SagWeight`(0~1) /
`SagDirection`(영=자동) / `WavePhase`.
현재 `SagWeight`는 감김부 안쪽 1.0, 바깥쪽 0.7, 윗면 0.

### `UGV|Track|Slack`

| 값 | 기본 | 역할 |
|---|---|---|
| `Total Slack` | 12.0 | 궤도가 얼마나 느슨한가 [cm]. 전체 스케일 |
| `Inertia Gain` | 0.004 | 궤도 가속 → 쏠림 (과도 상태) |
| `Friction Gain` | 0.0005 | 궤도 속도 → 쏠림 (정상 상태) |
| `Slip To Bias Gain` | 0.02 | 실제 헛돎 → 쏠림 |
| `Bias Response Speed` | 4.0 | 쏠림 재분배 속도 = 궤도 자체 관성 |
| `Bow Gain` | 2.0 | 슬랙 → 부풀어오름 |
| `Wave Gain` / `Wave Frequency` | 0.15 / 0.02 | 출렁임 (슬랙 비례) |

### `BP_UGV_Wheel_new` — 코드가 직접 읽으므로 바꾸면 궤도가 따라옴

| 값 | 궤도에 미치는 영향 |
|---|---|
| `Wheel Radius` | 지상고. `BottomRunZOffset`과의 차이가 12.37로 유지되면 바퀴–궤도–지면 스택이 맞음 |
| `Suspension Max Raise / Drop` | 바닥면 상하 이동 범위 |
| `Spring Rate` / `Damping Ratio` | 바닥면이 지형을 따라가는 부드러움 |
| `Max Wheelspin Rotation` | 공중 궤도 최대 회전 |
| `Friction Force Multiplier` | 접지력 |

### 콘솔 변수

```
p.UGV.TrackLock.Enabled / RedistributeTorque / SpinDownDecel / AirDamping / DebugLogInterval
p.UGV.SkidSteer.TorqueNm / FalloffStartKmh / FalloffEndKmh / FalloffMinScale
                         / FlipInReverse / ReverseFlipThresholdCmS
p.UGV.KeepAwakeWhileSteering / SteeringWakeThreshold
```

### 튜닝 순서

`Total Slack`(전체 느슨함) → `Bow Gain`(정지 시 부푸는 양) → `Inertia Gain`(급가속 극적임)
→ `Bias Response Speed`(굼뜸) → `Friction Gain`(정속 시 비대칭) → `Wave` 디테일.

`p.UGV.TrackLock.DebugLogInterval 10`으로 `accel / target / bias / front / rear` 실측을 보며
잡으면 빠르다. 로그 레벨은 `Log` — `VeryVerbose`로 넣으면 기본 설정에서 안 찍힌다(한 번 겪음).

## B-6. 남은 것

- 새그를 감김부가 아니라 다른 구간에 주고 싶으면 `SagWeight`만 옮기면 된다(코드 수정 불필요)
- 비활성화만 해둔 BP 노드들(스플라인 14개 + 사인 새그 체인 + 하드코딩 AddSplinePoint 22개)
  정리는 안정화 후에
- `TotalSlack`을 속도에 따라 줄이는 항(원심력으로 팽팽해짐)은 필요해지면 추가
