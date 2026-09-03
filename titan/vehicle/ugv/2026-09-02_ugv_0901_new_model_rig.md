# UGV 신규 모델(6륜) 교체 — SK_UGV_0901 / BP_UGV_0901

2026-09-02 / 완료 / 궤도 16륜 UGV를 차륜 6×6 신규 모델로 교체. 블렌더 리깅~언리얼 BP/ABP/머티리얼/주행 튜닝·총열회전 제거까지 전부 실동작 확인.

---

## 1. 배경

디자인팀에서 UGV 3D 모델이 새로 들어왔다. 기존 `BP_UGV_Vehicle_new`가 쓰던
`SK_UGV_v15`(무한궤도 + 편측 로드휠 8개 = 16륜)와 달리:

- **무한궤도 없음** — 일반 차륜 장갑차 형태
- **바퀴 편측 3개, 총 6개** (6×6)
- **포탑 형태 변경** — U자 요크에 단발 중기관총(M2 계열) 1정. **개틀링 아님**(총열 회전 없음),
  요크 옆에 탄약함 1개

기존 `BP_UGV_Vehicle_new`는 그대로 두고 별도 계보로 새로 만든다.

### 확정된 설계 결정 (사용자)

| 항목 | 결정 |
|---|---|
| 총열 회전 | **제거** — 개틀링이 아니므로 회전 로직·사운드·"스핀업 완료까지 발사 불가" 게이트 전부 제거. 단 **과열 연기(`NS_BarrelSmoke`) 등 나머지 이펙트는 유지** |
| 조향 | **스키드 스티어 유지** — 탱크처럼 좌우 휠이 따로 돌아서 선회. 궤도 비주얼만 빼고 구동 모델은 그대로 |
| 서스펜션 | 유지 (오히려 차륜이라 트래블을 늘림) |

**궤도 잠금(TrackLock) C++는 그대로 쓸 수 있다.** `UUGVWheeledVehicleSimulation`이 좌/우를
`Suspension[i].GetLocalRestingPosition().Y`의 부호로만 나누기 때문에
(`UGVWheeledVehicleSimulation.cpp:123`) 바퀴 개수 가정이 없다. 스키드 스티어도 여기서 나온다 —
`TrackTorque = TorquePerTrack ± SteerTorque`(:284). 실제로 `TorqueControl.enabled = false`,
`yawTorqueScaling = 0`이라 엔진의 `ApplyTorqueControl` 경로는 안 쓰고 있다.

---

## 2. 최종 에셋 구성

전부 `/Game/Vehicles/UGV/UGV_0901/` 아래에 자기완결적으로 모아뒀다 — 구형 UGV 에셋을 건드려도
영향받지 않는다.

| 에셋 | 비고 |
|---|---|
| `SK_UGV_0901` / `_Skeleton` / `_PhysicsAsset` | 본 10개 |
| `Textures/T_{Body,Turret,Tire}_{BaseColor,Metallic,Roughness,Normal}` | 12장, 2048² |
| `Materials/M_UGV0901_PBR` | 구형 `Hull` 복제 마스터(파라미터 4개), 기본 텍스처를 `T_Body_*`로 교체해 구형 의존 제거 |
| `Materials/M_UGV0901_Flat` | 단색용 마스터(BaseColor/Metallic/Roughness 파라미터) |
| `Materials/MI_UGV0901_{Body,Turret,Tire,Light,Glass,ReflectorRed,BrakeLampRed}` | 7개, SK 슬롯 7개에 할당 |
| `BP_UGV_0901` | `BP_UGV_Vehicle_new` 복제 후 개조 |
| `BP_UGV_Wheel_0901` | `BP_UGV_Wheel_new` 복제 후 개조 |
| `ABP_UGV_0901` | `ABP_UGV_Vehicle_new`를 **Retarget** 복제 |

**소스 파일**(프로젝트 밖):
`C:\working\mine\UGV_re\UGV_re.blend`(원본, 안 건드림) /
`UGV_0901_rig.blend`(리깅 작업본, **cm 단위**) / `SK_UGV_0901.fbx` / `Tex\` / `rig_check\*.png`

### 물리재질

| 대상 | PhysMaterial |
|---|---|
| `MI_UGV0901_Body` / `_Turret` | PM_Metal |
| `MI_UGV0901_Tire` | PM_Dirt (고무용 SurfaceType이 없어서 구형 UGV도 Metal/Glass/Dirt 3종만 씀) |
| `MI_UGV0901_Light` / `_Glass` / `_ReflectorRed` / `_BrakeLampRed` | PM_Glass |

차량은 **머티리얼의 `PhysMaterial`** 경로로 동작한다(`sfx_vfx/hit_effects_update_2026-08-26.md` §1
— 트럭/UGV는 이 경로가 되는 케이스, 바위/나무는 컴포넌트 오버라이드가 필요). 피직스 에셋
바디에는 오버라이드를 안 걸었다(구형 `SK_UGV_PhysicsAsset`도 안 걸려 있었음).

피직스 에셋 바디는 `Hull1`(시뮬레이션 차체) + `Rotation_base2` + `RCWS3` + 바퀴 6개.
판정만 받는 바디는 **Physics Type=Kinematic / Collision Enabled=Query Only /
Collision Complexity=Use Simple Collision As Complex** 3종 세트 + 컨스트레인트 삭제
(`sfx_vfx/hit_effects_update_2026-08-13.md` §6). 세 번째가 빠지면 발사체의 보조 Complex
트레이스에 안 잡혀 **피격 판정이 아예 안 된다.** 바퀴 바디가 Query Only여야 하는 이유는 Chaos
휠이 레이캐스트 기반이라 물리 충돌이 켜져 있으면 서스펜션과 싸우기 때문.

---

## 3. 스켈레톤 / 좌표

전체를 Z축 +90° 회전해 메시에 베이크했다(§4의 좌표 매핑 참고) — 앞 = +X, 좌 = +Y.
**원점은 차축 높이**(지면은 z = -31.6cm). 아래는 cm.

| 항목 | 값 |
|---|---|
| 전장 / 전폭 / 전고 | 281 / 175 / 146 (바퀴 포함 폭 180) |
| 휠 반지름 / 폭 | **31.6** / 40.3 |
| 축거(앞↔뒤) / 윤거 | 150.15 / 140.1 |
| 앞/중/뒤 축 X | +74.20 / -0.90 / -75.95 |
| 좌/우 휠 Y | +70.05 / -70.05 |
| 포탑 선회축(Yaw) | X=+50.09, Y=0 (링 반지름 22.0, 링 바닥 z=61.3) |
| 포탑 고각축(Pitch) 트러니언 | X=+41.31, Z=+112.72 (핀 지름 10.1, 좌우 x=±10) |
| 총열 축(bore) | Y=-0.4, Z=+110.18 |
| 총구 끝 | X=+111.4 |

트러니언은 눈대중이 아니라 메시에서 뽑았다 — Turret 메시를 루즈 파트로 쪼개면 좌우 대칭인
원판 2개(각 65 verts, 반지름 5.06)가 나오고 둘의 중심이 정확히 같은 (y=-41.31, z=112.72)였다.

### 본 구조

**본 이름을 옛 스켈레톤과 똑같이 유지했다.** `RCWSPreviewActor.cpp`가 `Hull1` /
`Rotation_base2` / `RCWS3`를 하드코딩해서 쓰고(`PoseTurretBones`), ABP도 같은 이름을
`ModifyBone`으로 굴린다. 이름을 맞춰두면 C++는 손 안 대도 되고 ABP는 복제 후 노드만 줄이면 된다.

```
root                      (0, 0, 0)          — 디폼 안 함
└ Hull1                   (0, 0, 0)          — 차체(Body) 전체
  ├ L_Wheel_01            (+74.20, +70.05, 0)   앞-좌
  ├ L_Wheel_02            ( -0.90, +70.05, 0)   중-좌
  ├ L_Wheel_03            (-75.95, +70.05, 0)   뒤-좌
  ├ R_Wheel_01            (+74.20, -70.05, 0)   앞-우
  ├ R_Wheel_02            ( -0.90, -70.05, 0)   중-우
  ├ R_Wheel_03            (-75.95, -70.05, 0)   뒤-우
  └ Rotation_base2        (+50.09,  0,     61.30)  포탑 좌우회전(Yaw)
    └ RCWS3               (+41.31,  0,    112.72)  포탑 상하회전(Pitch)
```

전부 head→tail이 +Y, roll 0 → **10개 본 모두 로컬축 항등**(스크립트로 확인).
`RCWS_Barrels4`(총열 회전)는 넣지 않았다.

**스키닝** — 전부 리지드(weight 1.0):

| 메시 | 본 |
|---|---|
| Body (47,709 v) | `Hull1` |
| Wheel_FL/ML/RL_Tire (각 19,302 v) | `L_Wheel_01/02/03` |
| Wheel_FR/MR/RR_Tire | `R_Wheel_01/02/03` |
| Turret — 요크 + 탄약함 + 링 + 측면판 (987 v) | `Rotation_base2` |
| Turret — 총몸 + 총열 + 크레이들 + 트러니언 + 급탄슈트/탄띠 (15,004 v) | `RCWS3` |

포탑 분리는 손으로 고른 게 아니라 **루즈 파트 32개를 좌우 폭으로 자동 분류**했다 —
`|lateral| > 0.16 m`이면 요크쪽(Yaw), 아니면 총쪽(Pitch). 총 어셈블리는 요크 팔 사이에
들어가야 해서 폭이 최대 0.144인 반면 요크/탄약함/링은 0.22~0.37이라 경계가 깨끗하게 갈린다.

---

## 4. 블렌더 → 언리얼 파이프라인 (재현용)

### 좌표 매핑

**블렌더 (bx, by, bz) → 언리얼 (bx, -by, bz).**
근거: 블렌더 FBX 익스포터가 `axis_forward='-Z', axis_up='Y'`로 `(bx,by,bz)→FBX(bx, bz, -by)`를
만들고, 언리얼 FBX 임포터가 Y-up→Z-up 변환 후 `ConvertPos`에서 Y를 뒤집어
`FBX(fx,fy,fz)→UE(fx, fz, fy)`를 만든다.

⇒ **블렌더에서 차량 앞 = +X, 좌측 = +Y**여야 언리얼에서 앞 = +X, 좌측 = -Y가 된다.
받은 모델은 앞이 -Y였으므로 전체를 Z +90° 회전해서 메시 데이터에 베이크했다.

### ★ 스켈레톤 루트에 Scale 100이 붙는 문제 (실제로 밟음)

첫 임포트에서 **스켈레톤 루트 본(`SK_UGV_0901`)에 Scale 100**이 박혀 들어왔다.
Import Uniform Scale을 건드린 게 아니었고, 원인은 블렌더 익스포터 쪽이었다. FBX를 직접 뜯어보니:

- 좌표가 **미터 그대로**(`L_Wheel_01` Lcl Translation = `0.742`)
- `UnitScaleFactor` = **1.0** (= FBX 단위가 cm라는 선언)
- 오브젝트 노드 9개(메시 8 + 아마추어)에 **`Lcl Scaling = 100`**

`apply_scale_options='FBX_SCALE_NONE'`("All Local")은 m→cm 변환(×100)을 **좌표에 굽지 않고 각
오브젝트 노드의 스케일로 넘긴다.** 그 아마추어 노드가 언리얼에서 루트 본이 되므로 루트에
Scale 100이 남는다. `apply_unit_scale=False`로 꺼도 노드 스케일은 그대로였다.

**해결 — 블렌더 씬 자체를 cm로:**

1. 메시 데이터 + 오브젝트 location + `armature.data.transform()`을 전부 **×100** 베이크
2. `scene.unit_settings.scale_length = 0.01` (1 블렌더 유닛 = 1 cm)
   → 익스포터의 단위 변환 계수가 `100 × 0.01 = 1`이 되어 **노드 스케일을 안 붙인다**

결과: 모든 `Lcl Scaling` = 1.0, 좌표 = cm(74.2), `UnitScaleFactor` = 1.0
→ **언리얼에서 Import Uniform Scale 1.0(기본값)으로 1:1 임포트**. 임포트 옵션을 만질 필요가 없다.

> **검증은 FBX 바이너리를 직접 파싱하는 게 제일 빠르다.** 모든 `Lcl Scaling`이 `[1,1,1]`인지,
> 본 `Lcl Translation`이 cm 숫자인지, `UnitScaleFactor`가 1.0인지. 언리얼에 넣어보고 판단하면
> 왕복이 길어진다.

### 익스포트 설정

```python
# 전제: 씬이 cm 단위 (좌표 ×100 베이크 + scene.unit_settings.scale_length = 0.01)
bpy.ops.export_scene.fbx(
    filepath=r"C:\working\mine\UGV_re\SK_UGV_0901.fbx",
    use_selection=False, object_types={'ARMATURE','MESH'},
    use_mesh_modifiers=True, mesh_smooth_type='FACE',
    use_armature_deform_only=False,
    add_leaf_bones=False,               # _end 본 생기면 언리얼에서 지저분해짐
    primary_bone_axis='Y', secondary_bone_axis='X',   # ★ 본 보정 안 함 = 항등 본 유지
    axis_forward='-Z', axis_up='Y',
    bake_space_transform=False,
    global_scale=1.0, apply_unit_scale=True, apply_scale_options='FBX_SCALE_NONE',
    bake_anim=False, path_mode='AUTO', embed_textures=False,
)
```

### 임포트 설정

| 옵션 | 값 |
|---|---|
| Skeleton | None (새로 생성) |
| Import Uniform Scale | **1.0** (FBX가 이미 cm) |
| Import Rotation / Force Front X Axis | 0,0,0 / 끄기 |
| Import Materials / Textures | 끄기 (슬롯 이름은 FBX에서 그대로 옴) |
| Normal Import Method | Import Normals |

### 2026-07 때 밟았던 지뢰 — 이번에 어떻게 피했나

`_archive/M1A2_UGV_Conversion.md` §1에 기록된, 예전에 블렌더로 UGV 스켈레탈 메시를 만들다가
포기하게 만든 문제들.

| 옛 문제 | 이번 대응 |
|---|---|
| **본 축 컨벤션**(블렌더 로컬 Y축 vs 언리얼 X축) | 모든 본을 **블렌더 +Y / roll 0**으로 생성 → `matrix_local` 회전이 항등. 익스포트에서 `primary_bone_axis='Y'`(기본값)를 써서 **본 보정 행렬을 아예 적용 안 함**. 결과적으로 언리얼에서 본 로컬축 = 컴포넌트축이라 `ModifyBone`을 BoneSpace로 쓰든 ComponentSpace로 쓰든 레스트 포즈에서 같다. 언리얼 비히클 템플릿(`AnimNode_WheelController`)이 가정하는 것도 이 항등 본 |
| **Root Body 분리 시 75cm 오프셋**(`FindRootBodyIndex()`) | `root`와 `Hull1`을 **둘 다 원점에 배치**. 어느 쪽에 바디를 달아도 오프셋이 생길 수 없음 |
| **바퀴 16개 ContactPoint 붕괴**(원인 미상) | 바퀴가 6개로 줄었고, 검증된 `BP_UGV_Vehicle_new` 계보를 복제해서 씀 |

---

## 5. 궤도 / 총열회전 제거 내역

### ABP_UGV_0901

바퀴 `ModifyBone` 16개 + 고아 1개 + `RCWS_Barrels4` 노드 삭제, 체인 재연결. **443KB → 119KB.**

```
LocalRefPose → LocalToComponentSpace → WheelController
             → ModifyBone(Rotation_base2) → ModifyBone(RCWS3)
             → ComponentToLocalSpace → Root
```

궤도 차량은 좌우 바퀴를 `WheelRotL/R` 두 값으로 일괄 회전시키는 `ModifyBone` 16개를 썼는데,
차륜이므로 엔진의 `WheelController` 노드에 맡겼다. 커스텀 시뮬이
`PVehicle->Wheels[i].SetAngularVelocity(TargetOmega)`로 각속도를 써넣으므로
(`UGVWheeledVehicleSimulation.cpp:402`) Chaos가 `AngularPosition`을 적분하고 `WheelController`가
그걸 읽는다 — **좌우 일괄 회전이 그대로 유지되고, 서스펜션 상하 움직임도 같이 나온다**
(궤도 시절엔 `ModifyBone`이 회전만 덮어써서 상하가 안 보였음).

EventGraph도 정리: `CastToBP_UGV_Vehicle_new` → **`CastToBP_UGV_0901`**, 죽은 라인
(`SetWheelRotL/R`, `SetBarrelSpinAngle`) 제거. 13노드 → 7노드, 변수는 `TurretYaw`/`GunPitch` 둘뿐.

### BP_UGV_0901

- **Tick** — `UpdateTurretVisuals` 이후의 궤도 비주얼 구간 전체 절단
- **ConstructionScript** — `BuildTrackSpline` ×2 + 트랙링크 `AddInstance` 루프 절단
  (ISM에 인스턴스가 안 생기므로 궤도가 안 보임)
- **`UpdateTurretVisuals`** — `SetBarrelSpinSpeed` / `SetBarrelSpinAngle` 제거, 니아가라 4개 중
  `SpinRadialSpeed`만 제거. 최종 체인:
  `SetTurretYaw → SetGunPitch → SpawnRate → HazeSpawnRate → HazeDistortionStrength`
  (**과열 연기·아지랑이 3개는 유지**)
- 컴포넌트 5개 삭제(사용자): `TrackLinks_L/R`, `TrackPath_L/R`, `BarrelSpinAudio`

### 발사 게이트 (C++)

기존 동작: `bWantsBarrelSpinUp = bFireSystemActive`라 **안전 해제 후 `BarrelSpinUpSeconds`(2초)
동안 스핀업이 끝나야 발사 가능**. 신규 UGV는 개틀링이 아니라 이 대기가 없어야 한다.

**`URCWSFireControlComponent`가 `BP_TitanTruck`과 공유**인데 트럭은 진짜 개틀링이다
(`RCWSBarrels` + `SM_UGV_TurretBarrels` + `BarrelSpinAudio` + `BarrelSpinGaugeValue` 바인딩).
그래서 통째로 걷어내지 않고 **`bUseBarrelSpin` 플래그(기본 true)** 로 분기했다.

| 파일 | 변경 |
|---|---|
| `RCWSFireControlComponent.h:353` | `UPROPERTY(EditAnywhere) bool bUseBarrelSpin = true;` 추가 |
| `RCWSFireControlComponent.cpp:180` | `const bool bBarrelReady = !bUseBarrelSpin \|\| BarrelSpinGaugeValue >= 1.f;` 로 게이트 교체 |
| `RCWSFireControlComponent.cpp:623` | `UpdateFireReadinessGauges`에서 false면 두 게이지를 0으로 두고 조기 반환 |

조기 반환 위치는 안전하다 — 락온 게이지는 그 위에서 계산되고 배럴스핀 블록이 함수의 마지막이다.
**과열 연기는 영향 없음**(`UpdateBarrelHeat()`가 별도 함수). 두 게이지를 읽는 곳은
`BarrelSpinAudioComponent` 하나뿐이라 0으로 눕히면 컴포넌트가 남아 있어도 무음이 된다.

빌드 후 `BP_UGV_0901`의 `RCWSFireControl`에 **`bUseBarrelSpin` = false** 를 세팅했다(기본값이
true라 이걸 해야 적용된다). **안전 → 사격 전환 즉시 발사 가능** 실동작 확인됨.
`BP_TitanTruck`은 기본값 true라 그대로 개틀링 동작.

---

## 6. 차량 튜닝 — 휠 반지름·개수 변경의 파급

교체 직후 "코너에서 속도를 주체 못 하고 부딪힌다"는 증상. UE5.8 엔진 소스로 원인 3개를 확정했다.

### ① 제동력은 기어비 보상을 못 받는다 — `WheelSystem.cpp:80-81`

```cpp
AppliedLinearDriveForce = DriveTorque / Re;   // Re = WheelRadius
AppliedLinearBrakeForce = BrakeTorque / Re;
```

`DriveTorque`는 기어박스를 통과하므로 `finalRatio`를 반지름 비율(2.107배)만큼 올린 것으로
상쇄된다(구동력·최고속 불변). 그런데 **`BrakeTorque`는 기어박스를 안 거치고 휠에 직접 걸린다.**

### ② 코너링 강성은 휠당 상수라 휠 수에 비례한다 — `WheelSystem.cpp:157`

```cpp
FinalLateralForce = FMath::Abs(SlipAngle) * CorneringStiffness;   // 하중 스케일 없음
```

휠 16 → 6개면 총 횡력이 **62.5% 감소**. 반면 마찰원
(`AvailableGrip = ForceIntoSurface × SurfaceFriction × FrictionMultiplier`)은 휠당 하중이
2.67배 커져서 **총량이 불변**이다. 즉 "미끄러진다"가 아니라 **같은 슬립각에서 나오는 복원
횡력이 약해 바깥으로 밀리는** 것. 그래서 `FrictionForceMultiplier`는 건드리면 과보정이다.

### ③ 자율주행 컨트롤러의 물리 가정이 옛 차량 기준 — `UGVAIController.h`

`CornerDecelMetersPerSecSq = 2.0`(제동 곡선 역산), `CornerMaxLateralAccelMps2 = 2.5`(커브 통과
속도 역산). 차가 못 내는 성능을 낼 수 있다고 가정하고 브레이킹 포인트와 진입 속도를 정한다.

### ★ 제동 토크는 반지름뿐 아니라 휠 수에도 비례한다 (1차 계산 오류)

1차로 `MaxBrakeTorque`를 반지름 비율만 적용해 50 → 105로 올렸는데 **부족했다.** 브레이크 토크는
휠당 값이라 총 제동력은 휠 수에도 비례한다:

| | 계산 | 차량 감속도 (1500kg) |
|---|---|---|
| 구형 (16륜, r=0.15) | 16 × (50 / 0.15) = 5333 N | **3.56 m/s²** |
| 1차 수정 (6륜, r=0.316, 105) | 6 × (105 / 0.316) = 1994 N | **1.33 m/s²** ← 컨트롤러 가정(2.0)보다 낮음 |
| 최종 (6륜, r=0.316, 400) | 6 × (400 / 0.316) = 7595 N | **5.06 m/s²** |

즉 물리 등가를 맞추려면 **반지름 비율 × 휠 수 비율 = 2.107 × 2.667 = 5.62배**(50 → 281)가
맞았다. 사용자가 실주행으로 400/600을 찾았고 그게 구형보다 여유 있는 값이라 잘 동작한다.

### 최종 값

**`BP_UGV_Wheel_0901`**

| 프로퍼티 | 구형(궤도) | 신규 | 근거 |
|---|---|---|---|
| `WheelRadius` / `WheelWidth` | 15 / 36.66 | **31.6 / 40.3** | 실측 |
| `MaxBrakeTorque` | 50 | **400** | 실주행 확정(계산상 등가는 281) |
| `MaxHandBrakeTorque` | 100 | **600** | 실주행 확정 |
| `CorneringStiffness` | 1000 | **2670** | × 16/6 |
| `SpringRate` / `SpringPreload` | 350 / 180 | **900 / 450** | × 16/6 |
| `SuspensionMaxRaise` / `MaxDrop` | 10 / 5 | **12 / 12** | 차륜은 트래블이 김 |
| `SuspensionDampingRatio` | 0.7 | 0.7 | 유지 |
| `FrictionForceMultiplier` | 10 | **10 유지** | 총 마찰 불변 — 올리면 과보정 |
| `bAffectedBySteering` | false | false | 스키드 스티어 |
| `WheelMass` | 80 | 80 | 유지 |

**`BP_UGV_0901` 무브먼트 컴포넌트**

| 프로퍼티 | 구형 | 신규 | 근거 |
|---|---|---|---|
| `TransmissionSetup.finalRatio` | 1.5 | **3.16** | 휠 반지름 15→31.6이라 그대로 두면 최고속 2.1배 |
| `CenterOfMassOverride` | (0,0,**-90**) | **(0,0,+10)** | 구형 메시 원점 기준값. 신규는 원점이 차축 높이라 -90이면 무게중심이 지면 58cm 아래 |
| `ChassisWidth` / `ChassisHeight` | 289 / 175 | **175 / 146** | 신규 헐 치수(항력용) |
| `Mass` / `DifferentialSetup` | 1500 / AllWheelDrive | 유지 | |

> **스케일 규칙 요약** — 반지름을 바꾸면 `MaxBrakeTorque`·`MaxHandBrakeTorque`,
> 휠 개수를 바꾸면 `CorneringStiffness`·`SpringRate`·`SpringPreload`,
> **둘 다 곱해야 하는 것이 제동 토크**. `FrictionForceMultiplier`는 어느 쪽도 아니다.

---

## 7. 옛 UGV를 가리키던 참조들

교체 후 "시나리오 자율주행이 안 붙는다"(`MoveUGVToZone1Destination: UGV 또는 AUGVAIController를
못 찾음`)로 드러남. **하드코딩이 아니라 PlayerController의 프로퍼티 하나였다.**

C++의 UGV 조회는 전부 `Atitan_examplePlayerController::FindUGVFromTankInstance()` 한 곳을 거치고,
그게 `UGVVehicleClass`로 `GetActorOfClass`를 한다. 게임모드 체인:
`BP_KadexTestGameMode` → `kadex_test_Blueprints/BP_TestPlayerController`.

| 위치 | 상태 |
|---|---|
| `kadex_test_Blueprints/BP_TestPlayerController.UGVVehicleClass` | **`BP_UGV_0901_C`로 수정 완료** |
| 같은 BP의 `UGVVehicleLegacyClass` | `BP_UGV_Vehicle_new` (폴백, 그대로 둠) |
| `titan_examplePlayerController.cpp:48` C++ CDO 기본값 | 아직 `BP_UGV_Vehicle_new`. BP 오버라이드가 이기므로 무해 — 헤더 주석도 "BP 서브클래스에서 오버라이드하면 recompile 불필요"라고 명시 |
| `RCWSPreviewActor.cpp:20,27` | `BP_UGV_Vehicle` + `SK_UGV` 하드 레퍼런스(RCWS 미니어처 프리뷰). **대응 안 함 — 지금 안 쓰는 액터**(2026-09-02 사용자 확인) |
| 레벨 `/Game/New_kadex_0811` | 구형 UGV 액터를 신규로 **교체 완료** |

**이 프로퍼티 하나에 딸려 있는 것들**: 시나리오 자율주행, `UGVRemoteControlSubsystem`(LIG
프로토콜 전체 — 항법정보/기본정보/RCWS 명령), `Monitor1Widget`, `MissionDashboardWidget`,
`PossessUGVFromTank`/`MoveUGVFromTankTo`/`SetUGVFromTankMode` 콘솔 명령.
수동 조종·포탑이 먼저 됐던 건 그 경로가 possess된 폰을 직접 쓰기 때문이다.

---

## 8. 이번에 밟은 함정 (MCP/툴링)

- **MCP 배열은 크기와 내용을 동시에 못 바꾼다** — `WheelSetups` 16→6으로 줄이면서 값도 바꾸면
  `ArrayRemove: removed elements are ambiguous`. **크기만 먼저 줄이고 그다음 내용 교체**로 2단계.
- **`MaterialInstanceTools.set_parent`는 패키지를 dirty로 안 만든다** — `get_properties`는 새
  부모를 돌려주는데 `is_dirty`가 false라 `save_assets`가 건너뛰고 디스크는 옛 값 그대로.
  `ObjectTools.set_properties`로 다시 쓰면 정상 저장. **MCP 읽기 말고 .uasset 바이너리로 검증할 것.**
- **`SkeletalMeshTools.set_material`이 `importedMaterialSlotName`을 `None`으로 지운다** — FBX
  재임포트 시 슬롯 매칭에 쓰는 값이라 복구 필요.
- **`UMaterialInstance::PhysMaterial`에는 오버라이드 체크박스가 없다**(UE5.8 `MaterialInstance.h:637`,
  평범한 `UPROPERTY(EditAnywhere, Category=MaterialInstance)`). MI 에디터에서 체크박스가 붙는 건
  Parameter Groups와 Material Property Overrides 두 군데뿐.
- **ABP를 Retarget 복제해도 EventGraph의 캐스트 대상은 원본 그대로** — AnimGraph만 새 스켈레톤을
  따라가고 `CastToBP_UGV_Vehicle_new`가 남아서 매 프레임 실패, 포탑이 안 돌았다.
  `retarget_node_class`로 클래스를 바꾸면 **새 출력 핀이 추가될 뿐 옛 핀이 남아** 컴파일 에러
  (`In use pin ... no longer exists`)가 나므로, 옛 핀에 물린 게터를 지우고 새 클래스로 재생성해야 한다.

---

## 9. 남은 일

**하나만 남았고, 급하지 않다.**

- `BP_UGV_0901` 이벤트그래프의 궤도 계산 **고아 노드 ~250개 + 미사용 변수 24개**
  (`TrackSag*` 15개, `WheelRot*`, `Chassis*`, `HullZRot`, `BasePoints*`, `TrackTautness*`,
  `TrackWhip*`, `WheelsZOffsets`, `BarrelSpin*`) 정리. Tick/ConstructionScript에서 실행 경로가
  끊겨 있어 **런타임 비용은 0**이고 컴파일도 통과한다 — 순수 정리 작업이라 나중에 해도 됨
  (2026-09-02 사용자 판단).

**검토했으나 대응 안 하기로 한 것** (2026-09-02 사용자 확인):

| 항목 | 사유 |
|---|---|
| `NavObstacleBox` 크기가 구형 차체(289폭) 기준 | 지금 안 쓰는 경로 |
| `RCWSPreviewActor`의 `SK_UGV`/`BP_UGV_Vehicle` 하드 레퍼런스 | 지금 안 쓰는 액터 |
| `titan_examplePlayerController.cpp:48`의 C++ CDO 기본값 | BP 오버라이드가 이기므로 무해 |

`CornerMaxLateralAccelMps2`(2.5) / `CornerScanDistance`(8000) / COM(z=+10)은 브레이크 토크
400/600으로 주행이 해결돼서 손대지 않았다.

---

## 10. 검증 상태 — 전부 완료

- [x] 본 10개 전부 로컬축 항등
- [x] 포탑 Yaw ±70° / Pitch +45°·-15° — 트러니언 회전, 관통 없음 (블렌더 렌더 `rig_check/`)
- [x] 언리얼 임포트 — 방향(+X), 스케일(루트 본 Scale 1), 머티리얼 7슬롯
- [x] 주행 — 정상
- [x] 포탑 회전 — 정상 (ABP 캐스트 수정 후)
- [x] 서스펜션 — `WheelController`가 상하 트래블까지 적용
- [x] 코너 제동 — 브레이크 토크 400/600으로 해결
- [x] 시나리오 자율주행 — `UGVVehicleClass` 수정 후 정상
- [x] 총열 회전 제거 — C++ 빌드 + `bUseBarrelSpin=false`, 안전→사격 전환 즉시 발사 확인
- [x] 피격 재질 판정 — 실사격 확인
