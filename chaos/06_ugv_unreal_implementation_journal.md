# UGV 실제 구현 일지 — Chaos 주행 로직 + Blender↔Unreal 파이프라인

`titan_example` 프로젝트, 디자인팀 실제 UGV 모델(`C:\graphics\assets\UGV_0716_first.blend`)로
Chaos Wheeled Vehicle을 처음부터 구현한 전체 과정 기록. 00~05번 문서(`chaostest` 스크래치
프로젝트에서의 사전 조사)의 후속 — 이번엔 실제 결과물 기준. 나중에 비슷한 애셋을 다시 붙이거나
문제가 재발했을 때 참고할 것.

---

## 0. 최종 결과물 구조 요약

- **`/Game/UGV/Blueprint/BP_UGV_Vehicle`** (부모: `AWheeledVehiclePawn`) — 본체. 서스펜션/조향은
  Chaos의 `ChaosWheeledVehicleMovementComponent`(WheelSetups 16개, 본 이름 `L_Wheel_01~08`/
  `R_Wheel_01~08`)를 그대로 씀. 궤도/바퀴 **시각적** 움직임(트랙 링크 스플라인, 바퀴 회전,
  궤도 처짐)은 전부 **Chaos 물리와 무관한 별도의 킨매틱(kinematic) 계산**으로 구현 — 이유는
  6절 참고.
- **`/Game/UGV/Blueprint/ABP_UGV_Vehicle`** — 바퀴 회전을 Chaos의 물리 기반 회전이 아니라
  `BP_UGV_Vehicle`이 계산한 킨매틱 값으로 오버라이드하려 시도(13절, **미해결로 보류**).
- **`/Game/UGV/SK_UGV`** + **`SK_UGV_Skeleton`** + **`SK_UGV_PhysicsAsset`** — 디자인팀 blend
  파일에서 Blender→FBX→Unreal로 임포트. 이 파이프라인 자체에서 겪은 버그와 해결책이 이 문서의
  핵심 내용(2~5절).
- **`TrackPath_L/R`**(SplineComponent) + **`TrackLinks_L/R`**(InstancedStaticMeshComponent) —
  11포인트 스플라인 + 39개 인스턴스로 궤도 링크를 표현. 매틱 스플라인 포인트를 갱신해서 처짐/
  출렁임을 표현(7절).

---

## 1. Chaos 차량 설정 (요약, 00~05번 문서의 실전 적용)

- `WheelSetups[i].BoneName`은 반드시 스켈레톤의 실제 본 이름과 **글자 그대로** 일치해야 함
  (틀려도 에러 없이 조용히 원점 폴백 — 04번 문서). 이번 UGV는 `L_Wheel_01~08`(인덱스 0~7),
  `R_Wheel_01~08`(인덱스 8~15)로 확인.
- 전/후 바퀴 판별: Blender에서 `L_Wheel_01`의 로컬 X가 +0.987(전방), `L_Wheel_08`이 -1.005
  (후방) — 즉 **인덱스 0=전방, 인덱스 7=후방** (한쪽당 8개 중). R쪽도 동일 패턴 → R 전방=
  인덱스8, R 후방=인덱스15.
- 조향은 `SetYawInput()` + `TorqueControl.YawTorqueScaling`(아케이드 방식) 사용 — 이건 실제
  타이어 마찰 기반 조향이 아니라 섀시에 직접 요 토크를 거는 방식. `BP_UGV_Vehicle:
  SetManualControl` 함수에서 호출.
- 서스펜션 오프셋은 `GetWheelState`+`BreakWheelStatus`의 `NormalizedSuspensionLength`로
  매틱 계산: `Offset = 7.5 - NormalizedSuspensionLength × 12.5` — 이 공식이 이후 궤도 처짐
  계산(7절)에서도 그대로 재사용됨.

---

## 2. ✅ 해결됨 — Root 본 스케일 100배 버그

**[05_SOLVED_blender_export_scale_bug.md](05_SOLVED_blender_export_scale_bug.md) 참고, 이번
실제 UGV 모델에도 그대로 적용해서 확인 완료.** 요약: Blender FBX 익스포터가 아마추어 바인드
포즈에 원인불명의 ×100 스케일을 구워서, Root 본 Scale이 100으로 잘못 들어감 → Chaos의
`LocateBoneOffset()`이 이 스케일 때문에 바퀴 위치를 1/100로 줄여서 전부 원점 근처로 뭉침.
**해결**: Blender에서 export 직전 Scale=100 적용(bake) 후 다시 Scale=0.01로 설정(이번엔
적용 안 함, 오브젝트 트랜스폼에 남겨둠).

---

## 3. ✅ 해결됨 — Root 직계 자식 본들의 회전 어긋남 (신규, 2026-07-19)

**[05_SOLVED_blender_export_scale_bug.md](05_SOLVED_blender_export_scale_bug.md)의 "후속
해결" 섹션에 상세 기록.** 요약:

- **증상**: 메시 렌더링은 정상인데, Skeleton Editor에서 Root의 직계 자식 본(`Hull1`,
  `L_WheelTrack_01~08` 등) Details 패널 Rotation 값이 identity가 아님. 부모(합성된 root
  래퍼)와 자식이 서로 회전을 상쇄해서 월드 좌표만 맞고, 로컬 회전 자체가 어긋나 있었음 —
  `get_bounds` 같은 월드 스페이스 진단으로는 절대 못 잡음, **Skeleton Editor Details 패널의
  본별 Rotation 수치를 직접 확인해야 함.**
- **원인**: 이 아마추어는 단일 Root 본이 없고 서로 부모 없는 최상위 본이 17개(`Hull` +
  `L_WheelTrack_01~08` + `R_WheelTrack_01~08`) 존재. 언리얼 FBX 임포터가 이걸 감싸는 가상
  "root" 래퍼 본을 자동 합성하는데, 이 과정에서 `primary_bone_axis`/`secondary_bone_axis`
  값에 따라 달라지는 고정 회전 오프셋이 끼어듦(Blender 자체 재-import 왕복 테스트로 FBX 파일
  자체는 문제없음을 확인 — 순수하게 언리얼 임포터 쪽 동작).
- **해결**: `primary_bone_axis='Z'`, `secondary_bone_axis='X'` (기본값 Y/X 대신) — 실측
  데이터 2점(Y/X→Roll90 오차, X/-Y→Pitch90/Yaw-90 오차)으로 상쇄에 필요한 값을 역산해서
  찾음. 최종 검증된 전체 export 옵션 조합:
```python
bpy.ops.export_scene.fbx(
    filepath=...,
    use_selection=True,
    apply_unit_scale=True,
    bake_space_transform=True,
    add_leaf_bones=False,
    axis_forward='-Y',
    axis_up='Z',
    primary_bone_axis='Z',
    secondary_bone_axis='X',
    bake_anim=False,
)
```
- **주의**: 이 `Z`/`X` 값은 **이 UGV의 "다중 독립 최상위 본" 구조에서 실증적으로 역산한 값**.
  다른 리그(단일 Root 본이 이미 있는 구조)에는 그대로 안 맞을 수 있음 — 그 경우 같은 방식
  (기본값으로 export → Root 직계 자식 Rotation 확인 → 역산 → 재검증)으로 다시 찾을 것.

---

## 4. ✅ 해결됨 — 차체 하단/데칼 면 노멀 뒤집힘

**증상**: 차체 하단 일부가 뚫려서 내부(RCWS 등)가 보임 + Logo 데칼(텍스트) 중 일부가 안 보이거나
엉뚱하게 보임. **전부 Blender 소스 자체의 문제**(원본 참고 파일과 비교해도 동일 — Blender
뷰포트에서도 재현되는지는 머티리얼의 backface culling 설정에 따라 다를 수 있어 주의).

**진단 방법 (신뢰도 순)**:
1. ❌ (실패) 월드 스페이스 "중심에서 바깥쪽 방향" 추정 — 곡면이 복잡하면 완전히 틀린 판정을 냄
   (이미 고친 면을 다시 "뒤집힘"으로 오판하는 등). **쓰지 말 것.**
2. ✅ 원본 파일(`UGV_0716_origin.blend`, 있다면)과 **면의 정점 순서(winding, `polygon.vertices`
   튜플)를 직접 비교** — 오브젝트 트랜스폼 차이에 영향 안 받는 가장 확실한 방법. 다만 이건
   "원본 대비 뭐가 바뀌었나"만 알려주고, "지금 상태가 맞는지"는 별도 판정 필요.
3. ✅✅ **가장 신뢰도 높은 방법**: 문제되는 면(예: Logo 데칼)의 월드 노멀을, **가장 가까운
   확실히-정상인 면(예: Hull 기본 재질 면) k개의 노멀 평균과 내적 비교**. 데칼은 차체 표면에
   거의 딱 붙어있으므로 정상이면 내적이 강한 양수, 뒤집혔으면 강한 음수가 나옴. 이 방법으로
   1694개 데칼 면 중 정확히 6개의 뒤집힌 면을 한 번에 찾아냄(1차 시도는 위치 기반 방법으로
   틀렸었음).

**수정**: `bpy.ops.mesh.flip_normals()`를 문제 면만 선택해서 실행(Edit Mode, bmesh selection).
`mesh.normals_make_consistent(inside=False)`(전체 자동)는 **isolated/disconnected 아일랜드가
많은 메시에서 오판할 수 있어 주의** — 가능하면 위 3번 방법으로 정확한 대상만 골라서 수동
`flip_normals()`.

**부가 팁 — 텍스처 내용 확인**: 어떤 UV가 어느 텍스트/이미지에 대응하는지 헷갈릴 때는
Blender 노드에서 이미지 파일 경로를 따라가 원본 PNG를 직접 열어보고(Read 툴), 필요하면
Python(PIL)으로 UV 좌표를 픽셀로 환산해서 크롭 후 확인. 텍스트 블록 위치를 정확히 찾으려면
`scipy.ndimage.label`로 어두운 픽셀(배경이 순백이 아니라 약간 회색인 경우가 많으니 히스토그램
확인 후 임계값 잡을 것) 블롭을 자동 검출하는 게 눈대중보다 훨씬 정확함.

---

## 5. ✅ 해결됨 — Logo 데칼 텍스트 흰 배경 (머티리얼 BlendMode)

**증상**: 데칼 텍스트 주변이 투명해야 하는데 불투명한 흰 사각형으로 보임.

**원인**: `/Game/UGV/Logo` 머티리얼(Blender에서 안 가져오고 기존에 손으로 만들어둔 애셋
재사용 — 스켈레탈 메시 임포트를 전부 `import_materials=False`로 했기 때문)의 `BlendMode`가
`BLEND_Opaque`로 되어 있었음. `OpacityMaskClipValue`(0.333, 엔진 기본값)는 이미 설정돼 있어서
애초에 Masked로 쓸 생각이었던 것으로 보이나 BlendMode 전환을 빠뜨린 상태였던 것으로 추정.

**해결**: `BlendMode`를 `BLEND_Masked`로 변경 + 텍스처의 Alpha 출력을 `MP_OpacityMask`에 연결.
텍스처 자체의 `CompressionNoAlpha=false` 확인(알파 데이터 보존됨).

---

## 6. ⚠️ 미해결 — 데칼 텍스트가 표면에서 살짝 뜬 것처럼 보이는 가짜 그림자

**증상**: 로고/텍스트 데칼이 차체 표면에 완전히 밀착돼 있어야 하는데, 마치 살짝 떠서 그
아래에 그림자가 진 것처럼 보임. 시점을 바꿔도 그림자가 그대로 있음(각도 의존적인 패럴랙스
착시는 아닌 것으로 보임). **가까이서 봐야 눈에 띄는 정도**. Blender에서는 전혀 안 보이고
언리얼에서만 보임.

**시도했으나 효과 없었던 것들**:
- 노멀맵 그린 채널 반전(`bFlipGreenChannel` true↔false) — 효과 없음
- ORM 텍스처의 AO(R채널) 확인 — 텍스트 모양의 그림자가 박혀있지 않음(스크래치/마모 패턴일 뿐)
- `bCastRayTracedShadows=false`로 레이트레이스 섀도우 비활성화 — 효과 없음
- 머티리얼에서 `MP_Normal` 연결을 아예 끊어서 노멀맵 자체를 제거 — 효과 없음
- `MP_WorldPositionOffset`/`MP_PixelDepthOffset` 확인 — 애초에 연결 안 돼 있음(변위 효과
  아님이 확정됨)

**아직 안 해본 것 (다음에 시도할 것)**:
- 데칼 지오메트리가 Hull 표면과 진짜로 미세하게 떨어져 있는지(Z-fighting/살짝 띄워서 모델링된
  경우) — Blender에서 데칼 면의 버텍스와 바로 아래 Hull 면의 버텍스 사이 실제 거리를 직접
  측정해볼 것 (본 문서 4절의 "이웃 면과 비교" 기법을 거리 측정에도 응용 가능)
- SSAO(스크린 스페이스 AO) 자체를 콘솔 변수로 꺼보고 비교(`r.AmbientOcclusion.Method 0` 등) —
  포스트 프로세스 레벨 원인인지 머티리얼 레벨 원인인지 분리 진단
- Lumen/글로벌 일루미네이션이 꺼져있는지, 켜져있다면 Lumen의 디테일 트레이싱이 얇은 데칼
  지오메트리에서 self-occlusion을 만드는지 확인
- 라이트매스/베이크된 라이팅이 남아있다면 리빌드(스켈레탈 메시는 보통 정적 라이트맵을 안
  쓰지만, 혹시 관련 세팅이 있다면 확인)

---

## 7. 궤도 처짐/출렁임 구현 — 3번의 실패와 최종 물리적 모델

가장 많은 시행착오를 거친 부분. 최종 채택된 방식은 **"중력 + 관성 + 마찰" 3요인 가산 모델**이며,
아래는 그 경로.

### 7.1 배경 — 스플라인 11포인트 구간 분류
Construction Script가 만드는 11개 스플라인 포인트는 4구간으로 나뉨:
- **0,1,9,10** = 접지 구간(바닥과 바퀴 사이) — **Event Tick에서 절대 손대면 안 됨**
- **2,3** = 후방 랩업 구간, **7,8** = 전방 랩다운 구간 (바퀴를 감아 올라가고 내려가는 부분)
- **4,5,6** = 탑런(윗면) 구간 — 차체 내부라 안 보임, 최종적으로 우선순위 낮음

### 7.2 실패한 시도들
1. **서스펜션 오프셋을 접지 구간에 직접 반영** — 접지 구간은 바닥/바퀴 사이에 끼어있어서 위아래로
   움직이면 안 되는데 그렇게 만듦 → 오히려 더 뻣뻣해짐.
2. **FInterpTo 기반 지연을 접지 구간에** — 등속 주행 시 값이 거의 안 변해서 아무 효과 없음.
3. **가속도 기반 스프링을 접지 구간에** — 접지 구간이 바퀴를 뚫고 올라가는 것처럼 보임(물리적으로
   말이 안 됨 — 유저가 정확히 지적).
4. **M1A2 참고 후 구간별 처리 + Tautness(팽팽함) 스칼라 + 사인파** — M1A2의 실제
   `PointLocationCalculation`을 리버스엔지니어링해서 구간별 클램프+방향성 램프+사인파 지터
   방식임을 확인하고 UGV에 이식. **버그**: Tautness가 "이동거리" 누적이라 후진하면 0으로
   클램프돼서 출렁임이 완전히 사라짐("태엽 감기듯"). 등속 주행에서도 사인파가 계속 돌아서
   비현실적(유저 지적: "등속이면 쳐짐이 없어야 함").

### 7.3 최종 채택 — 물리적 3요인 모델 (사인파 완전 폐기)

유저가 직접 도출한 요구사항: **① 중력에 의한 기본 처짐(랩존 링크는 이웃 링크로만 지지)**,
**② 순간 가속/감속+궤도 관성으로 인한 랩존 팽팽함/처짐(등속이면 0)**, **③ 궤도-지면 마찰로
인한 팽팽함/처짐(현재 속도 기반, 등속이어도 일정하게 존재 가능)**.

```
Accel = (ForwardSpeed_현재 - PrevForwardSpeed) / DeltaSeconds   // 거리 누적 아님, 순간 가속도
InertiaBias  = Clamp(Accel × TrackSagInertiaCoeff, -1, 1)
FrictionBias = Clamp(ForwardSpeed_현재 × TrackSagFrictionCoeff, -1, 1)
TotalBias    = Clamp(InertiaBias + FrictionBias, -1, 1)

// 급격한 변화를 그대로 반영하면 "너무 즉각적"이라는 피드백 → 관성 지연 추가
TrackSagCurrentBias = FInterpTo(이전값, TotalBias, DeltaSeconds, TrackSagBiasInterpSpeed)

SagDelta  = TrackSagBaseAmplitude × TrackSagCurrentBias
RearSagZ  = -(TrackSagGravityAmount + SagDelta)
FrontSagZ = -(TrackSagGravityAmount - SagDelta)
```

- 랩존 포인트(2,3,7,8)에 기존 바퀴 서스펜션 오프셋(뻣뻣한 범프 반응) + 위 SagZ(중력+관성+마찰
  처짐)를 **더해서** 적용.
- `TrackSagBaseAmplitude`의 **부호가 전체 방향(어느 쪽이 팽팽해지는지)을 결정** — 실차 구동륜
  위치에 따라 달라서 이론적으로 예측 안 되므로 PIE에서 보고 부호만 뒤집으면 됨(그래프 재작업
  불필요).
- 탑런(4,5,6)은 안 보이는 부분이라 이전 방식(Tautness+사인파)을 그대로 방치, 손 안 댐.

**커스텀 변수** (Blueprint 디폴트 값으로 노출, `ObjectTools.set_properties`를
`Default__BP_UGV_Vehicle_C`에 호출해서 초기값 설정): `TrackSagGravityAmount`(1.5),
`TrackSagBaseAmplitude`(2.5, 부호로 방향 전환), `TrackSagInertiaCoeff`(0.05),
`TrackSagFrictionCoeff`(0.01), `TrackSagBiasInterpSpeed`(3.0, 관성 지연 속도).

---

## 8. ✅ 해결됨 — 제자리 회전(스키드 스티어) 시 궤도가 안 도는 버그

**증상**: A/D로 제자리 회전 시 궤도가 살짝 움직였다가 멈추고, 키를 떼면 되돌아옴.

**원인**: 궤도 이동거리 킨매틱 공식이 `ChassisXMoveComponent`(전후진 누적) +
`ChassisZRotComponent`(회전 누적)인데, 후자가 **매틱 그 순간의 델타만 계산하고 누적을 안 하고
있었음**(변수는 선언돼 있었지만 Set을 안 함). 제자리 회전은 전후진 델타가 거의 0이라
`ChassisXMoveComponent`가 안 늘어나고, `ChassisZRotComponent`도 누적이 안 되니 매틱 리셋되는
것처럼 보였음.

**해결**: `ChassisZRotComponent{L,R}`을 `ChassisXMoveComponent`와 똑같은 패턴(이전값 Get +
이번 틱 델타 Add → Set)의 진짜 누적기로 변경. 추가로 요-차동 계수를 M1A2 원본 값(±2.52, 다른
트랙 게이지용으로 캘리브레이션됨)에서 이 UGV의 실제 반트랙폭(~90cm)에 맞게 10배(±25.2)로
재조정.

---

## 9. ⚠️ 미해결(우선순위 낮음, 방치) — 접지 안 된 바퀴의 시각적 회전 관성

**증상**: W/S를 살짝 눌렀다 떼면, 지면에 안 닿은 바퀴가 실제 물리 회전 관성으로 계속 헛돎 —
궤도 링크(킨매틱 계산)의 속도와 안 맞음.

**시도한 것**: ABP에 `WheelController` 이후 16개 `ModifyBone`(BMM_Replace, BCS_BoneSpace)을
추가해서 바퀴 회전을 `BP_UGV_Vehicle`의 킨매틱 `WheelRotL/R` 값으로 강제 오버라이드. 본
이름/배선/`AnimNode_ModifyBone.cpp` 소스 레벨까지 전부 확인했지만 이론상 완벽한데도 증상이
그대로였음. Chaos 엔진 소스(`AnimNode_WheelController.cpp`, `VehicleAnimationInstance.cpp`)까지
확인했지만 우회 경로가 없는 것도 확인함. **원인 특정 실패, 사용자가 우선순위 낮다고 판단해서
보류.** 다음에 재시도한다면: `MakeRotator`에 고정값(예: Pitch=90)을 하드코딩해서 오버라이드
파이프라인 자체가 동작하는지부터 이분법으로 확인할 것(아직 안 해본 진단).

---

## 10. 파이프라인 작업 시 일반 팁 모음

- **재수출 시 항상 새 파일명/새 애셋으로 먼저 테스트**하고, 검증되면 프로덕션 애셋에 반영.
  프로덕션에 반영할 때도 `import_file`은 "새 애셋 생성"만 가능(기존 애셋에 덮어쓰는 진짜
  Reimport 기능 없음) — 기존 애셋을 다른 이름으로 rename(백업)한 뒤 원래 경로에 새로 import,
  PhysicsAsset/머티리얼 슬롯을 수동으로 재할당하는 방식으로 우회.
- 스켈레탈 메시를 기존 Skeleton 애셋에 바인딩해서 재임포트할 때, 본 이름만 같으면 되고
  Skeleton 애셋 자체를 새로 만들 필요는 없음(AnimBP가 특정 Skeleton에 종속되므로 스켈레톤을
  바꾸면 AnimBP 재연결이 필요해짐 — 웬만하면 기존 스켈레톤 유지).
- Blender 작업 중 다른 원본 파일(`_origin.blend` 등)과 비교할 땐 `bpy.ops.wm.open_mainfile`로
  전환 후 **반드시 원래 작업 파일로 다시 전환하는 것까지 스크립트에 포함**시킬 것 — 세션이
  엉뚱한 파일에 남아있으면 이후 모든 작업이 잘못된 파일에 적용됨.
- 큰 JSON/텍스트 결과가 토큰 한도를 넘으면 파일로 저장되니, Bash+Python(또는 jq)으로 슬라이싱해서
  읽을 것. 여러 틱에 걸친 비교가 필요하면 중간 결과를 디스크에 캐싱(`json.dump`)해서 파일
  전환 중에도 데이터를 잃지 않게 할 것.
