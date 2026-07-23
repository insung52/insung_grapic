# Chaos Wheeled Vehicle 조사 — 종합 개요 및 의사결정 가이드

`C:\private\chaos` 폴더의 인덱스 문서. 목적은 `intro.md`에서 정한 0차 목표 —
Chaos Wheeled Vehicle의 작동 원리를 충분히 파악해서, **M1A2 복제 방식이든 디자인팀
blend 에셋으로 처음부터 구현하는 방식이든 어느 쪽을 택해도 문제없이 작업할 수 있는
지식**을 확보하는 것. 3갈래로 나눠 조사한 결과를 여기서 통합한다.

## ✅✅✅ 최종 해결 (2026-07-16) — 바퀴 서스펜션 원점 붕괴 버그의 진짜 원인과 해결책

**→ [05_SOLVED_blender_export_scale_bug.md](05_SOLVED_blender_export_scale_bug.md) 필독.**

몇 달째(intro.md 작성 시점부터) 미제였던 "바퀴 서스펜션이 차체 중앙 한 점에 몰리는" 버그의
근본 원인을 chaostest 프로젝트에서 처음부터 재현하며 확정함: **Blender FBX export의 알려진
버그로 스켈레톤 Root 본의 Scale이 100으로 잘못 들어감** — 월드 좌표는 우연히 맞아서 눈으로는
정상으로 보이지만, Chaos Vehicle이 내부적으로 쓰는 "Root 기준 상대 위치" 계산이 이 스케일에
영향받아 바퀴 위치가 전부 1/100로 줄어들어 원점에 뭉침. 검증된 해결 절차(Blender에서 100배
스케일 후 apply, 다시 0.01배로 스케일하되 apply 안 하고 export)까지 확인 완료. **디자인팀
실제 UGV 모델 작업 시작 전 반드시 05번 문서의 절차를 먼저 적용할 것.**

## 문서 구성

| 문서 | 내용 |
|---|---|
| [01_chaos_vehicle_architecture.md](01_chaos_vehicle_architecture.md) | 핵심 클래스 구조, 공식 설정 워크플로우, PhysX→Chaos 변환 가이드, Async Physics, TorqueControl |
| [02_skeleton_physics_asset.md](02_skeleton_physics_asset.md) | 블렌더→언리얼 본 축 정렬, 스켈레톤 구조 요구사항, Physics Asset 구성 규칙 |
| [03_suspension_deep_dive.md](03_suspension_deep_dive.md) | 서스펜션 계산 메커니즘, 스케일 처리 문제, ContactPoint 버그, 다륜 차량 특화 가이드 |
| [04_bone_collapse_investigation.md](04_bone_collapse_investigation.md) | (후속 조사) 바퀴 서스펜션 위치 붕괴 문제 — 여러 가설을 반증해가며 좁혀나간 과정 기록 (최종 원인은 05번 문서) |
| [05_SOLVED_blender_export_scale_bug.md](05_SOLVED_blender_export_scale_bug.md) | **✅ 최종 확정 원인 + 검증된 해결 절차** (스케일 버그 + 후속 회전 버그) |
| [06_ugv_unreal_implementation_journal.md](06_ugv_unreal_implementation_journal.md) | **✅ 실제 UGV 모델로 처음부터 구현한 전체 기록** — Chaos 설정, 궤도 처짐 3요인 모델, 겪은 버그 전부와 해결책 |
| [07_ugv_feature_porting_and_rcws.md](07_ugv_feature_porting_and_rcws.md) | **✅ 최신** — 기존 UGV 기능(수동/자동 주행, RCWS 포탑) 이식 기록. 포탑 본 매핑, 개틀링건 스핀, 포탑 컬링 버그(Physics Asset AABB 바운드), RCWS 미리보기 다이오라마(미해결), 트럭 4분할캠 버그 |
| `C:\private\titan\M1A2_UGV_Conversion.md` | (조사 대상이 아니라 조사의 출발점) M1A2 복제 작업 실전 기록 |

---

## ⚠️ 정정 (사용자 확인, 2026-07-16) — 아래 1절의 "원인 A/B" 가설은 사용자가 실제 겪은 사례와 안 맞음

아래 1절의 원인 A("바퀴 본이 Root 직계 자식이 아님")와 원인 B("스케일이 Offset에 안 곱해짐")는
사용자가 실제로 겪은 버그의 원인이 아니었던 것으로 확인됨:

- **원인 A 반증**: 바퀴 본의 부모 계층은 이미 여러 조합으로 직접 테스트해봤음 — Root 직계 자식
  여부와 무관하게 문제가 있었음.
- **원인 B 반증**: `Offset`은 원래 (0,0,0)이었고, 서스펜션 위치가 붕 뜨는 걸 상쇄하려고
  **의도적으로** +Z=50을 넣은 것 — 스케일-Offset 곱셈 문제가 아니라 애초에 서스펜션 계산
  위치 자체가 잘못된 곳(모델 원점 근처)에 있었음.

**진짜 증상(사용자 확인)**: 커스텀 스켈레탈 메시로 처음부터 구현 시도했을 때, **모든 바퀴의
실제 서스펜션 계산 위치가 각 바퀴 본의 실제 위치를 무시하고 전부 모델 원점 쪽에 몰려있었음.**
바퀴 본 자체는 스켈레톤 상에서 정상 배치되어 있었던 것으로 보임 — Chaos Vehicle이 그 위치를
제대로 못 읽은 것이 진짜 문제.

이 증상에 대한 후속 조사는 → [04_bone_collapse_investigation.md](04_bone_collapse_investigation.md) 참고.
아래 1절 원인 A/B는 "일반적으로 유효할 수 있는 회피 규칙"으로서는 남겨두되, **우리가 겪은 버그의
확정 원인은 아니라는 점**을 염두에 둘 것.

### 04번 조사 결론 요약 (2026-07-16 소스 코드로 최종 확정됨)

**✅ 확정된 원인 (로컬 UE5.8 엔진 소스 직접 확인, `04_bone_collapse_investigation.md` 0절)**:
`WheelSetups[i].BoneName`에 입력한 문자열이 실제 임포트된 스켈레톤의 `RefSkeleton`에서
매칭되지 않으면(본 이름으로도 소켓 이름으로도), `USkeletalMesh::GetComposedRefPoseMatrix()`
(`SkeletalMesh.cpp:5422`)가 **아무 에러/경고 없이 `FMatrix::Identity`(원점)를 리턴**하고,
그 값이 `UChaosVehicleMovementComponent::LocateBoneOffset()`(`ChaosVehicleMovementComponent.cpp:1529`)를
거쳐 그대로 서스펜션 앵커 위치로 쓰인다. `CanCreateVehicle()`은 `BoneName`이 완전히
비어있을 때만 에러를 띄우며, **문자열이 있지만 스켈레톤에 없는 이름인 경우는 체크를
통과**해서 조용히 원점으로 수렴한다. 바퀴 16개가 전부 원점 근처로 몰린 증상 =
`WheelSetups`에 넣은 `BoneName` 문자열들이 실제 스켈레톤 본 이름과 (아마 전부 동일한
패턴으로) 어긋나 있었다는 뜻으로 사실상 확정됨.

**부가 확인**: 03번 문서의 "스케일이 `Offset`에 안 곱해짐" 가설도 소스로 재확인됨 — Wheel BP의
`Offset` 프로퍼티는 스케일이 전혀 안 곱해지고, 본의 레퍼런스 포즈 위치만 `Mesh->GetRelativeScale3D()`가
곱해진다. 즉 본 매칭이 정상인 경우엔 이 가설이 유효하다.

**남는 대안 가설**: Blender 공식 버그 트래커 이슈([#113073](https://projects.blender.org/blender/blender/issues/113073),
스킨 웨이트 없는 본은 FBX export 시 레스트 포즈가 깨짐)는 여전히 가능성으로 남아있지만,
이건 "이름은 맞는데 좌표가 깨지는" 다른 경로라 위 확정 원인보다 후순위로 의심할 것.

**사용자 질문("본 배치에 정해진 형식/각도가 있는가")에 대한 답**: 있다 — ① 바퀴 본 로컬 축은
X=전방/Y=우측/Z=상단 컨벤션을 따라야 함, ② `BoneName` 문자열이 완전히 일치해야 함(안 맞으면
에러 없이 원점 폴백), ③ 본 트랜스폼이 export 시점에 실제로 "적용(bake)"되어 있어야 함(스킨
안 된 본은 이게 깨지기 쉬움).

**다음 시도 때 반드시 할 것 (이번에 빠졌던 것으로 추정되는 단계)**: import 직후 Skeleton
Editor에서 바퀴 본 하나하나의 실제 Location 좌표값을 **숫자로** 확인할 것 — 육안으로 "위치가
맞아 보인다"는 것만으로는 이 문제를 놓치기 쉽다(16개가 다 비슷하게 틀어지면 상대적으로
정상처럼 보임). 상세 체크리스트는 04번 문서 3절 참고.

---

## 1. 가장 중요한 통합 발견 — 우리가 겪은 3가지 버그는 사실 1~2가지 근본 원인이었다 (⚠️ 위 정정 참고)

이전에 커스텀 스켈레탈 메시로 처음부터 구현을 시도했을 때 겪은 두 가지 버그와, M1A2
복제 후 겪은 한 가지 버그는 서로 무관해 보였지만, 이번 조사로 **공통 근본 원인 두 가지로
수렴**한다는 게 확인됐다.

### 원인 A: 바퀴 본이 Root의 직계 자식이 아니었다 / Root 본 자체에 물리 바디가 없었다

- **Root Body 분리 시 75cm 오프셋 버그** (커스텀 메시 시도) ← 이 원인
- **바퀴 16개의 SuspensionState.ContactPoint 붕괴 버그** (커스텀 메시 시도) ← 이 원인

Epic 공식 포럼에서 정확히 같은 증상(바퀴가 지면과 충돌 판정이 안 되고, 콜리전을 옮기면
튕기거나 날아감)을 겪은 사례를 찾았고, 원인은 "바퀴 본이 Root의 직계 자식이 아니라 Body
본을 거쳐 매달려 있었던 것"으로 확정 진단됨(02번 문서 2절). `FindRootBodyIndex()`가
"물리 바디가 있는 계층상 첫 본"을 무조건 루트로 취급하는 동작(M1A2 문서에서 엔진 소스로
확인)과 결합하면, 이 두 버그가 정확히 왜 일어났는지 설명된다.

**회피 규칙(확정)**:
```
Root (원점, 회전 0, 물리 바디 있음)
├── Wheel_1 ~ Wheel_N   ← Root 직계 자식, Body를 거치면 안 됨
└── Body (차체 비주얼, 옵션 — 여기에 물리 바디를 몰아넣지 말 것)
```

### 원인 B: `Offset`/`WheelRadius` 등이 절대 cm 값이라 컴포넌트 스케일이 반영 안 됨

- **스케일 0.5 적용 시 바퀴가 지면 위로 붕 뜨는 버그** (M1A2 복제 후) ← 이 원인

공식 문서 어디에도 `Offset`이 스케일을 반영한다는 언급이 없고, "Physics Asset에서
Kinematic 본과 그 자식은 스케일이 강제로 1로 오버라이드된다"는 확인된 엔진 동작이
정황 증거로 확인됨(03번 문서 2절). `Offset +Z=50` 땜빵이 "실사용에 문제 없었다"는 건
우연이 아니라 스케일 미반영분을 수동으로 정확히 보정한 것과 같은 효과였을 가능성이 높다.

**회피 규칙**: 컴포넌트 스케일을 1이 아닌 값으로 써야 한다면 `Offset`/`WheelRadius`/
`SuspensionMaxRaise`/`SuspensionMaxDrop`을 스케일 비율만큼 수동으로 다시 계산해서 넣을
것. 가장 확실한 회피는 애초에 블렌더에서 최종 크기로 모델링해서 언리얼에서 스케일을
1로 유지하는 것(03번 문서 2.3절).

### 부가 발견: `SetYawInput()`은 진짜 조향력이 아니다 (M1A2 문서 6절 재확인)

01번 문서 5절에서 공식 API 문서 기준으로 재확인: `TorqueControl.YawTorqueScaling`이
공식적으로 "ArcadeControl" 카테고리로 분류됨 — M1A2 문서의 결론(SetYawInput은 입력
저장일 뿐, 실제 회전력은 YawTorqueScaling)이 공식 문서와 정확히 일치. 처음부터 구현할
때도 이 값을 반드시 명시적으로 켜고(`Enabled=true`) 설정해야 한다는 걸 잊지 말 것.

---

## 2. 의사결정: M1A2 복제 vs 처음부터 구현

intro.md에서 아직 미정으로 남겨둔 질문에 대해, 이번 조사 결과를 바탕으로 정리한 판단
기준.

### 처음부터 구현이 이전보다 훨씬 유리해진 이유

이전 시도가 실패한 이유였던 3가지 버그의 원인이 이제 **전부 사전에 회피 가능한 규칙으로
명확해졌다**(위 1절). 이전엔 원인 불명 상태로 며칠을 헤맸지만, 이번엔:
- 본 계층 규칙(Root 직계 자식, Root에 물리 바디)을 처음부터 지키면 원인 A의 두 버그는
  애초에 발생하지 않을 가능성이 높음
- 스케일을 1로 유지하는 모델링 관행을 지키면 원인 B도 애초에 안 생김
- Physics Asset 셋업 순서(휠 Sphere 프리미티브, Physics Type=Simulated, BoneName
  대소문자 일치)가 02/03번 문서에 체크리스트로 정리됨

즉 이전 실패는 "Chaos Vehicle이 원래 어려워서"가 아니라 "본 계층 구조에 대한 암묵적
전제(공식 문서에 안 나와 있는)를 몰라서" 발생한 것으로 보인다. 이 암묵적 전제를 이제
알고 있으므로, 재도전 시 성공 확률이 크게 올라갔다고 볼 수 있다.

### 그래도 M1A2 복제 쪽이 유리한 부분

- **애니메이션 블루프린트 / 궤도 비주얼(ISM+스플라인) 로직**은 M1A2 원본이 이미 검증된
  구현을 갖고 있고, 이건 Chaos Vehicle 자체의 문제가 아니라 순수 비주얼 엔지니어링
  분량이라 그대로 재사용하면 시간이 크게 절약됨(M1A2 문서 12절)
- **탱크/궤도형 다륜 차량의 조향(스키드 스티어)**에 대한 커뮤니티 표준 정답은 사실상
  없고(03번 문서 5.4절), M1A2가 쓰는 방식(TankTurn 매크로 → SetYawInput + YawTorqueScaling)이
  이미 검증되어 있어 이걸 새로 설계하는 것보다 훨씬 안전함
- Possess/AI 컨트롤러 관련 대형 디버깅(M1A2 문서 3절, `IsLocalController` 오버라이드 등)도
  이미 M1A2 기반에서 해결되어 있어서, 처음부터 다시 만들면 똑같은 삽질을 반복할 위험 있음
  (이 부분은 스켈레탈 메시/Physics Asset과 무관하게 Pawn/Controller 아키텍처 문제라 어느
  쪽을 택하든 동일하게 마주침 — 재사용 가능하면 재사용하는 게 이득)

### 권장 방향 (하이브리드)

이번 조사 결과, 극단적인 양자택일보다 다음이 합리적:

1. **본체/바퀴/서스펜션 물리 구조**: 디자인팀 blend 에셋으로 처음부터 구성 — 이제
   회피 규칙을 알고 있으니 리스크가 낮아짐. 최종 비주얼 품질이 M1A2 로우폴리보다
   훨씬 중요한 항목이라 어차피 새 메시로 가야 함.
2. **AI 컨트롤러/구동 로직/RCWS/사운드/WBP 연동**(M1A2 문서 3~14절): 거의 전부 Pawn
   클래스와 컴포넌트 이름 기반 리플렉션으로 설계되어 있어서 **메시가 바뀌어도 재사용
   가능**한 코드가 대부분(`AUGVAIController`, `RCWSComponent` 등은 오너 클래스 비의존
   설계). 이 부분은 그대로 재사용.
3. **궤도 비주얼(ISM+스플라인)**: M1A2 구현(12절)을 참고해서 새 메시에 재구현 — 그대로
   복사는 불가(메시가 다름)하지만 알고리즘/구조는 그대로 가져다 쓸 수 있음.

즉 "M1A2를 복제하느냐 마느냐"보다, **"어떤 부분을 재사용하고 어떤 부분을 새로 만드느냐"**가
더 정확한 질문이며, 위 3단 분리가 그 답이다. 이 판단은 1차 목표(blend 에셋 구조를 Blender
MCP로 확인)를 마친 뒤 실제 메시 구조를 보고 다시 조정할 것.

---

## 3. 처음부터 구현 시 실전 체크리스트 (3개 문서 통합판)

### 블렌더 단계
- [ ] 씬 단위 Metric, Unit Scale 0.01
- [ ] 최종 크기로 모델링 (언리얼에서 컴포넌트 스케일 1 유지 목표 — 2절 원인 B 회피)
- [ ] Root 본: 회전 0, 스케일 1(identity), Ctrl+A로 Transform 적용 후 export
- [ ] 바퀴 본: Root의 **직계 자식**으로 배치 (Body를 거치면 안 됨)
- [ ] 바퀴 본 피벗은 바퀴 회전 중심(허브)에 정확히, X/Y축 정렬 대칭
- [ ] FBX export: Primary Bone Axis=X, Secondary Bone Axis=-Y, Forward=-Y, Up=Z, Add Leaf Bones 해제
  **⚠️ 이 줄은 스케일 버그(05번 문서) 발견 이전에 쓴 낡은 초안으로 추정됨 — 실제 UGV 모델
  작업(06번 문서)에서는 이 값 그대로 안 맞았고, 다른 근본 원인(회전 버그, 06번 문서 3절)까지
  겪은 뒤 `Primary=Z, Secondary=X`로 재확정함. 새로 작업할 땐 06번 문서를 우선 참고하고, 이
  줄의 값을 검증 없이 믿지 말 것.**

### Physics Asset 단계
- [ ] **Root 본 자체에도 물리 바디 생성** (`FindRootBodyIndex()` 오인 방지)
- [ ] 바퀴 본 전체 선택 → Primitive Type=Sphere → Re-generate Bodies
- [ ] 바퀴 물리 바디 Physics Type = **Simulated** (Kinematic 아님 — 스케일 강제 1 문제 회피)
- [ ] 서스펜션 전용 본이 있다면 Collision > No Collision
- [ ] 스켈레탈 메시와 Physics Asset이 같은 Skeleton 에셋 참조하는지 확인

### Chaos Vehicle 설정 단계
- [ ] `WheelSetups`의 BoneName이 스켈레톤 본 이름과 대소문자까지 완전 일치 (틀려도 에러 없이 조용히 무시됨 — 최우선 의심 지점)
- [ ] `TorqueControl.Enabled=true` + `YawTorqueScaling` 명시적 설정 (기본값 꺼져있음)
- [ ] 다륜 차량이면 하중 배분 공식의 분모를 실제 바퀴 수로 재계산
- [ ] 스케일을 1이 아닌 값으로 쓸 수밖에 없다면 `Offset`/`WheelRadius`/`SuspensionMaxRaise`/`SuspensionMaxDrop`을 스케일 비율만큼 수동 보정

### 문제 재발 시 진단 순서 (03번 문서 6절)
1. `p.Vehicle.DisableConstraintSuspension` 토글 — 제약 기반 서스펜션의 특이 영역인지 분리
2. 스케일을 1.0으로 되돌려서 재현되는지 확인
3. 바퀴 본 Physics Type (Simulated/Kinematic) 확인
4. `WheelSetups` BoneName 정확성 재확인
5. 바퀴 본이 Root 직계 자식인지, Root 자체에 물리 바디가 있는지 확인
6. Blender Root 본 Transform이 identity였는지 확인
7. 절대값 프로퍼티들의 스케일 수동 보정 필요 여부

---

## 4. 남은 확인 필요 항목 (2차 조사 후보, 우선순위순)

1. **`FindRootBodyIndex()`/`RootBodyData` 소스 재확인** — 엔진 로컬 설치 경로에서
   `SkeletalMeshComponentPhysics.cpp` 직접 열람 (이전 세션엔 확인했었다는데 이번 웹
   리서치로는 원문 재현 못함)
2. **`Offset`이 로컬/월드 어느 좌표계 기준인지** — 실제로 프로젝트에서 스몰 스케일 테스트로 직접 검증 가능
3. **`SuspensionState.ContactPoint` 계산식 소스 레벨 근거** — 공식 문서/포럼에 없음, 엔진 소스 직접 확인 필요
4. Async Physics 입력 지연 프레임 수 — `ChaosVehicleMovementComponent.cpp`의 `TickComponent` 직접 확인
5. UE 5.4 "물리 꺼도 바퀴 계속 회전" 회귀 버그가 5.8(우리 엔진 버전)에서도 재현되는지
6. **(04번 조사 추가)** `BoneName` 매칭 실패 시 "차량 원점 폴백"이 정확히 엔진 소스 어느
   지점(`FindBoneIndex` 호출부 등)에서 일어나는지 원문 확인 — 04번 문서 조사 시 grokipedia
   접근이 403으로 막혀서 확정 못함
7. **(04번 조사 추가)** 이전 시도에서 바퀴 본이 실제로 타이어 메시에 스킨 웨이트로 묶여
   있었는지 여부 자체가 불명 — 다음 시도 때 이것부터 먼저 확인하면 "Blender 레스트 포즈
   깨짐 버그"(04번 문서 2절) 가설의 적용 여부를 바로 판단 가능

이 항목들은 실제로 처음부터 구현을 시작해서 막히는 시점에 우선순위를 정해 엔진 소스
직접 열람으로 확인하는 게 효율적 — 지금 단계에서 전부 파고들 필요는 없음.

---

## 다음 단계

이 조사로 0차 목표는 일단 충분히 달성됐다고 판단됨. intro.md에서 정한 1차 목표(디자인팀
blend 에셋 구조를 Blender MCP로 확인)로 넘어가는 것을 제안.
