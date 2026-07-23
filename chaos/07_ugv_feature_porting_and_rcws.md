# UGV 기존 기능 이식 + RCWS 포탑 구현 기록 (2026-07-19 ~ 2026-07-20)

`06_ugv_unreal_implementation_journal.md`가 "실제 UGV 모델을 Chaos Vehicle로 처음부터
구현한 기록"이라면, 이 문서는 그 다음 단계 — **완성된 `BP_UGV_Vehicle`에 기존 UGV
프로토타입들(네이티브 `AUGVPawn`, M1A2 복제본 `BP_UGVFromTank`)이 갖고 있던 수동/자동
주행·RCWS 포탑 기능을 이식한 기록**이다. `BP_UGVFromTank`는 이 작업을 기점으로 완전히
퇴역 처리하기로 확정(사용자 결정) — 레벨에서 제거하고 참고용 애셋으로만 남김.

---

## 0. 최종 구조 요약

- `/Game/UGV/Blueprint/BP_UGV_Vehicle` — 이제 수동/자동 주행 + RCWS 포탑까지 전부 갖춘
  최종 UGV 액터. `WheeledVehiclePawn`(네이티브) 직접 상속이라 M1A2가 겪었던
  "PlayerController가 possess해야만 물리 활성화" 문제 자체가 없음(그 버그는
  `BP_VehicleBase::ReceivePossessed`의 특유 로직 때문 — M1A2_UGV_Conversion.md 3절).
- 주행 제어: `AUGVAIController`(C++, `Source/titan_example/Vehicles/UGVAIController.h/.cpp`)가
  possess한 채로 상시 유지, `DriveMode`(Idle/Manual/Auto)로 제어. 이 컨트롤러는 애초에
  "`SetManualControl`이라는 이름의 함수를 가진 아무 Pawn"에나 붙게 리플렉션 기반으로
  범용 설계되어 있어서, `BP_UGV_Vehicle`도 별도 C++ 작업 없이 그대로 붙었음.
- RCWS: `RCWSMount`/`RCWSSightCamera`/`RCWS`/`TargetDetection`/`DetectableTarget`/
  `RCWSFireControl`/`Muzzle` 컴포넌트 세트를 `BP_UGVFromTank`와 동일한 이름 규칙으로 추가.
  `FComponentReference`가 전부 이름 기반 자동 해석이라 이름만 맞추면 C++ 코드 수정 없이 연결됨.
- 포탑 시각 회전: `Rotation_base2`(좌우)/`RCWS3`(상하) 본을 `ABP_UGV_Vehicle`의 ModifyBone
  노드가 매 프레임 구동. `RCWS_Barrels4`는 조준과 무관하게 발사 중 가속/정지 후 관성
  감속하는 개틀링건 스핀 전용.

---

## 1. 주행 제어 — 대부분 이미 되어 있었음

세션 도중 발견: `BP_UGV_Vehicle`에 `SetManualControl`/`SetBraking` 함수, `AutoPossessAI=
PlacedInWorld`, `AIControllerClass=BP_UGVAIController` 연결까지 **이전 세션에서 이미
끝나 있었다.** `SetManualControl`은 `BP_Tank`의 `TankTurn` 매크로 로직(부호 반전 +
SelectFloat)을 그대로 이식한 패턴 — 후진 중(`ForwardInput<0`)에는 `Yaw`도 반전시켜서
실제 궤도 차량처럼 후진 조향이 직관적으로 느껴지게 함.

이번에 실제로 추가한 것:
- `VehicleMovementComp.NavAgentProps`가 미설정(-1)이었던 것 → `AgentRadius=200`,
  `AgentHeight=144`로 고정 (레벨의 `RecastNavMesh-Tank`와 일치, M1A2 문서 5/10.4절 기준)
- `ChaseCamera`(스프링암 없이 `VehicleMesh`에 직결 — M1A2 패턴 그대로) 신규 추가. 카메라
  자체가 아예 없었음
- `UGVStatusComponent` 신규 추가 (대시보드 속도/기어 텔레메트리 — 로직은 이미
  `AUGVAIController::UpdateTankUGVStatusData`에 범용으로 구현되어 있어서 컴포넌트만
  달면 바로 작동)

**PIE 정적 확인**: AI 컨트롤러 정상 possess, `DriveMode=Auto`, 서스펜션 안정적으로 정지
유지(전복/폭발 없음) 확인. 실제 WASD 조작감/자동주행 목적지 이동은 라이브 플레이 테스트가
필요 — 콘솔에서 키 입력을 넣을 방법이 없어서 여기까지만 정적으로 확인함.

---

## 2. RCWS 컴포넌트 이식

`BP_UGVFromTank`에서 쓰던 컴포넌트 세트와 튜닝값을 그대로 복사:

- `RCWSMount`(`USceneComponent`, `VehicleMesh` 자식, 대략 `(X=40,Y=0,Z=210)` — 눈대중
  배치, 정밀 좌표 아님) → `RCWSSightCamera`(`USceneCaptureComponent2D`, 자식) → `Muzzle`
  (`USceneComponent`, 자식)
- `RCWS`(`AmmoMax=1200`, `CameraFOV=65`), `TargetDetection`(`MaxDetectionRange=40000`),
  `DetectableTarget`, `RCWSFireControl`(`ProjectileClass`/`MuzzleFlashNiagaraEffect`/
  `FireSound`/반동값 전부 트럭·구형 UGV와 동일값으로 복사)

`FComponentReference` 자동 해석(`SightCameraRef`→"RCWSSightCamera", `RCWSRef`→"RCWS",
`TargetDetectionRef`→"TargetDetection", `MuzzleRef`→"Muzzle")이 컴포넌트 이름만 맞으면
알아서 연결되므로 별도 배선 작업 불필요 — 실제로 이름 일치 확인만 하고 끝남.

---

## 3. 포탑 시각 회전 — 본 매핑을 두 번 고쳤음

### 3.1 첫 시도 (틀림) → 사용자 정정

처음엔 `Rotation_base2`=좌우, `RCWS_Barrels4`=상하로 매핑했는데, 사용자가 정정:

> "좌우 회전은 rotation base 가 차체 기준으로 돌아가면되고, 상하 회전은 rcws 자체가
> 총열 포함해서 위아래로 돌아가면됨."

본 계층은 `Hull1 → Rotation_base2(선회) → RCWS3(센서/포탑 몸통) → RCWS_Barrels4(포신)`.
**`RCWS3`가 상하로 돌아야 그 자식인 `RCWS_Barrels4`(포신)까지 자동으로 같이 따라감** —
즉 상하 회전은 `RCWS_Barrels4`가 아니라 `RCWS3`에 걸어야 함. `RCWS_Barrels4`는 대신
발사 중 개틀링건처럼 자체 축(Roll) 회전을 맡김(3.3절).

### 3.2 데이터 흐름

`BP_UGV_Vehicle`의 신규 함수 `UpdateTurretVisuals`(매 틱 호출, DeltaSeconds 파라미터):
```
RCWS->GetMount()->GetRelativeRotation()  (차체 기준 상대 팬/틸트)
  → BreakRotator → Yaw를 TurretYaw 변수에, Pitch를 GunPitch 변수에 저장
```
`ABP_UGV_Vehicle`(AnimBP)의 `Blueprint Update Animation` 이벤트가 매 프레임 이 두
변수를 자기 로컬 변수로 복사(기존 `WheelRotL`/`WheelRotR` 동기화와 완전히 동일한
패턴). AnimGraph에 ModifyBone 노드 2개 추가:
- `Rotation_base2`: RotationMode=Replace, Space=BoneSpace, Rotation=MakeRotator(Yaw=TurretYaw)
- `RCWS3`: 위와 동일, Rotation=MakeRotator(Pitch=GunPitch)

기존 바퀴 8×2개 ModifyBone 체인(Pose 링크) 맨 뒤에 이 2개를 이어붙이는 방식으로 삽입 —
기존 그래프는 한 노드도 안 건드림.

**카메라-포탑 레이턴시**: M1A2는 RCWS 마운트(카메라)와 실제 스켈레탈 포탑(`AC_WeaponTank`
구동)이 완전히 별개 시스템이라, 카메라는 즉각 반응하고 포탑은 자기 속도로 느리게
따라가는 간극이 있었고, 그 간극을 보여주는 전용 조준선 위젯(`GetTurretReticleScreenUV`)까지
필요했음. 우리 구조는 본이 마운트 회전값을 **매 프레임 그대로 복사**(자체 슬루/지연 없음)
하므로 카메라와 포탑이 항상 완전히 동기화됨 — M1A2식 레이턴시 로직도, 별도 조준선
위젯도 필요 없음(사용자 확인, 2026-07-20).

### 3.3 개틀링건 스핀업/스핀다운

`RCWS_Barrels4`의 Roll을 매 틱 누적(`BarrelSpinAngle`). "발사 중"이라는 이벤트가
`RCWSFireControlComponent`에 따로 노출돼있지 않아서, **`RCWS->GetCurrentData().AmmoCurrent`가
이전 틱보다 줄었는지**로 발사 감지. 1200RPM(초당 20발) 기준 개별 발사 사이 간격(0.05초)
동안에도 "계속 발사 중"으로 유지되도록 유예 시간(`FireDetectionGraceSeconds`=0.2초) 둠.

```
발사 감지 시: BarrelSpinSpeed를 BarrelSpinUpRate(3000deg/s²)로 최대
              BarrelSpinMaxSpeed(1440deg/s, 초당 4바퀴)까지 가속
발사 중단 시: BarrelSpinDownRate(400deg/s², 가속의 약 1/7)로 서서히 감속
```
전부 `BP_UGV_Vehicle` Details 패널에서 튜닝 가능한 변수.

### 3.4 진짜 심각했던 버그 — write_graph_dsl이 실행 체인을 통째로 안 이었음

개틀링건 로직 추가하며 `UpdateTurretVisuals` 함수 전체를 DSL(`write_graph_dsl`)로
재작성했는데, **컴파일은 에러 없이 성공했지만 실제로는 아무 것도 실행되지 않고
있었음.** `FunctionEntry`부터 이어져야 할 실행(exec) 체인이 `Set` 노드 6개 전부에서
빠진 채로 생성됨 — 데이터 배선(어떤 값을 어디 넣을지)은 전부 정확했는데, "언제 실행할지"
연결이 하나도 없었던 것. 컴파일러는 "연결 안 된 고아 노드"를 에러로 안 잡아서 겉으로는
멀쩡해 보였음.

**발견 과정**: 라이브 PIE에서 `RCWSMount`의 `RelativeRotation`을 직접 강제로 바꿔넣고,
`BP_UGV_Vehicle`의 `TurretYaw`/`GunPitch`가 그 값을 반영하는지 확인 → 항상 0으로 고정된
걸 보고 함수가 아예 안 도는 것을 확정. `get_node_infos`로 `FunctionEntry`의 `then` 출력
핀이 `connected_pins: []`(빈 배열)인 걸 보고 원인 확정.

**수정**: `FunctionEntry → SetTurretYaw → SetGunPitch → SetTimeSinceLastFireDetected →
SetPrevAmmoCurrent → SetBarrelSpinSpeed → SetBarrelSpinAngle` 순서로 `connect_pins`를
수동으로 6번 호출해서 이어붙임.

**교훈**: `write_graph_dsl`로 순차 실행문이 여러 개(특히 pure bind와 exec 문이 섞여있는
경우) 있는 함수를 작성한 뒤엔, 컴파일 성공 여부와 무관하게 **`get_node_infos`로
`FunctionEntry`부터 시작하는 실행 체인이 실제로 끝까지 이어져 있는지 반드시 확인할 것.**
"컴파일 에러 없음"이 "제대로 작동함"을 보장하지 않는다.

---

## 4. Blueprint DSL 툴 사용 시 함정 (한국어 로컬라이즈 프로젝트 특유)

이 프로젝트 에디터가 한국어로 로컬라이즈되어 있어서, `write_graph_dsl`의 내장 연산자
설탕(`+`, `-`, `*`, `<`, `<=`, `select` 등)이 전부 영어 노드 이름을 가정하고 있어
그대로 쓰면 실패한다:

- `(< a b)` → `Utilities|Operators|Less(<)` 를 찾다가 실패. 실제로는
  `유틸리티|연산자|작음(<)` 같은 한국어 이름으로 직접 호출해야 함
- `(select cond a b)` → `Utilities|Select` 를 찾다가 실패. `수학|플로트|SelectFloat`을
  `:A`/`:B`/`:bPickA` 키워드 인자로 직접 호출해야 함
- `self` 자동 바인딩(별도 노드 없이 자기 자신 참조)도 `Variables|Getareferencetoself`라는
  영어 이름을 찾다가 실패 — 이건 대체 노드 이름을 못 찾아서 결국 우회함(6절 참고)

**정확한 한국어 노드 이름을 찾는 법**: `find_node_types`의 `context_pins` 파라미터에
기존 노드의 핀 하나를 넘기면(드래그해서 노드 검색하는 것과 동일한 컨텍스트), 그 핀에
연결 가능한 노드 후보 목록이 나온다 — 이 안에서 정확한 로컬라이즈 이름을 찾을 수 있음.
특히 AnimGraph의 SkeletalControl 노드(ModifyBone 등)는 `find_node_types`를 빈 필터로
검색해도 아예 안 나오는데, `context_pins`로 기존 포즈 체인 핀을 넘기면 나온다
(`본트랜스폼(변경)` = Transform (Modify) Bone).

**`get_node_type_pins`의 부작용**: 일반 그래프에서 호출하면 "미리보기용" 노드가
생겼다가 사라지는 것처럼 보이지만(실제로 존재하지 않는 프리뷰), **공유 그래프
(EventGraph 등)에서 호출하면 진짜 고아 노드가 남는다** — 정리 안 하면 그래프에
잔해가 쌓임. `write_graph_dsl`은 대상 그래프를 통째로 재생성하는 것으로 보이므로
(실패한 시도에서 이전에 만든 노드까지 같이 사라지는 것으로 확인), 격리된 함수 그래프
에서만 안전하고 EventGraph처럼 이미 방대한 내용이 있는 공유 그래프에는 **절대 쓰면
안 됨** — 대신 `create_node`+`connect_pins`+`break_pins`로 기존 체인의 딱 한 지점만
잘라서 새 노드 하나 끼워넣는 방식(splice)을 써야 함.

---

## 5. 포탑 컬링 버그 — 근본 원인 확정, 임시방편 적용

### 5.1 증상

RCWS 씬캡쳐뿐 아니라 **일반 에디터 뷰포트 카메라로 봐도** 동일하게 발생: 차체(Hull)가
화면/캡쳐 프러스텀 밖으로 나가면 포탑까지 통째로 사라짐. 포탑 자체가 화면 안에 있어도
상관없이, 오직 차체 기준으로만 컬링 여부가 결정되는 것처럼 보임.

### 5.2 근본 원인 (UE 5.7 엔진 소스 확인, `SkinnedMeshComponent.cpp`)

```cpp
// If we have a PhysicsAsset (with at least one matching bone), and we can use it, do so to calc bounds.
else if( bHasPhysBodies && bCanUsePhysicsAsset && UsePhysicsAsset )
{
    NewBounds = FBoxSphereBounds(PhysicsAsset->CalcAABB(this, LocalToWorld));
}
```

`USkinnedMeshComponent::CalcMeshBound()`(→ `USkeletalMeshComponent::CalcBounds()`도
내부적으로 이 함수를 그대로 호출)는 **애니메이션된 라이브 포즈를 따라다니며 바운드를
계산하지 않는다.** 물리 시뮬레이션 중인 컴포넌트(우리 차체 — Chaos Vehicle이라
`bHasValidBodies=true`)는 **Physics Asset의 AABB**를 렌더링 바운드로 씀. 물리
시뮬레이션이 아닌 경우에도 `GetSkinnedAsset()->GetBounds()`(메시 애셋에 미리 구워진
정적 바운드)를 쓸 뿐, 어느 경로로도 "지금 이 순간 본이 실제로 어디 있는지"를 반영하지
않는다.

`SK_UGV_PhysicsAsset`은 차체/바퀴용 바디만 있고 `Rotation_base2`/`RCWS3`/
`RCWS_Barrels4`엔 바디가 없음 — 포탑이 아무리 돌아도 `CalcAABB()` 계산에 전혀
포함되지 않는다. 그래서 차체(바운드의 유일한 근원)가 프러스텀 밖으로 나가면 포탑까지
통째로 컬링됨.

### 5.3 적용한 임시방편

`VehicleMesh.BoundsScale`을 1.0 → **4.0**(사용자 최종 튜닝값)으로 인상. 이 프로퍼티는
엔진 자체 설명대로 "프러스텀 컬링용 바운드 크기 배율"일 뿐이고, 실제 충돌
콜리전(Physics Asset의 바디 형태)이나 서스펜션 레이캐스트, 질량 계산엔 전혀 영향을
안 준다 — 순수 렌더링/컬링 판정용 숫자.

사용자 확인: 실제 차체(`VehicleMesh`)는 이걸로 해결됨("오케이. 작동한다").

### 5.4 정확한 해결책 (미착수, 추후 작업)

Physics Asset Editor에서 `Rotation_base2`/`RCWS3`/`RCWS_Barrels4`에 **시뮬레이션 안
하는(킨매틱 전용) 바디**를 추가하면 `CalcAABB()` 계산에 포함되어 근본적으로 해결됨.
Physics Asset을 직접 편집하는 MCP 툴이 없어서 이번엔 시도 못함 — 사용자가 Physics
Asset Editor에서 직접 해야 함.

### 5.5 부수적으로 고친 것 (컬링과 무관, 별개로 유효한 개선)

`VehicleMesh.VisibilityBasedAnimTickOption`을 `AlwaysTickPoseAndRefreshBones`로 강제.
이건 컬링 버그의 원인이 아니었던 것으로 판명(적용해도 컬링 자체는 안 고쳐짐)됐지만,
`SetWorldRenderingEnabled(false)`(대시보드 모드, 메인 뷰포트 렌더링 자체를 끔) 상황에서
메인 뷰가 이 메시를 "본 적 없음"으로 판단해 애니메이션 틱 자체를 건너뛸 수 있는
최적화 옵션이라 — 켜두는 게 안전해서 그대로 유지.

---

## 6. RCWS 미리보기 다이오라마(`RCWSPreviewActor`) — 스켈레탈 방식으로 전환, 아직 미해결

### 6.1 발견한 기존 인프라

`ARCWSPreviewActor`(`Source/titan_example/UI/RCWSPreviewActor.h/.cpp`)와
`Monitor1Widget`의 `RCWSPreviewImage`/`RCWSPreviewReflectionImage` 바인딩이 **이미
완성되어 있었음**(`ui_dev_guide.md` 691~800절 참고). 맵 밖(Z≈-6000)에 고정 카메라 +
미니 터렛 메시로 된 디오라마를 만들어서 크로마키로 WBP에 합성하는 구조 — "고정"은
카메라 각도만 고정이고, 터렛 자체는 실시간으로 실제 조준 방향을 따라감.

**문제 1**: `SyncTurretMesh()`가 `Cast<UStaticMeshComponent>(ActiveRCWS->GetMount())`로
마운트에서 스태틱 메시를 복사하는 구조 — M1A2/구형 UGV 시절 "마운트 자체가 큐브
스태틱메시"였던 전제로 짜여있음. `BP_UGV_Vehicle`의 `RCWSMount`는 빈 `USceneComponent`라
복사할 스태틱메시 자체가 없음.

**문제 2(발견 즉시 수정)**: `ResolveActiveRCWS()`가 UGV 쪽을 여전히 옛날 네이티브
`AUGVPawn` 클래스로만 찾고 있었음 — 그 클래스는 이제 레벨에 없으니 **애초에 UGV RCWS를
못 찾고 있었음.** `Atitan_examplePlayerController::FindUGVFromTankInstance`와 동일한
소프트 클래스 경로 + `FindComponentByClass` 패턴으로 폴백 추가.

### 6.2 적용한 해결책 — UPoseableMeshComponent

`ARCWSPreviewActor`에 `TurretPoseableMesh`(`UPoseableMeshComponent`) 신규 추가:
- `SK_UGV`를 그대로 로드(`SetSkinnedAssetAndUpdate` — `SetSkeletalMesh`는 UE5.1+
  deprecated)
- `BeginPlay`에서 포탑 3개 본(`Rotation_base2`/`RCWS3`/`RCWS_Barrels4`) 빼고 44개 본을
  전부 `HideBoneByName`으로 숨김(차체/바퀴/트랙 체인 + 블렌더 익스포트 잔재 orphan
  본들)
- 매 틱 `PoseTurretBones()`가 `Rotation_base2`(yaw)/`RCWS3`(pitch)를 실제 차량과 동일한
  로직으로 포즈. `PoseableMeshComponent::SetBoneRotationByName`은 `EBoneSpaces::Type`이
  `WorldSpace`/`ComponentSpace`만 있고 "부모 본 기준" 옵션이 없어서(엔진 소스
  `SkinnedMeshComponent.h` 확인, `LocalSpace`는 주석 처리되어 존재 안 함), 쿼터니언을
  직접 합성: `자식ComponentSpace = 부모ComponentSpace * 로컬델타쿼터니언`
- 트럭의 기존 스태틱메시 경로(`TurretMesh`)는 그대로 보존 — `Tick()`에서
  `Cast<UStaticMeshComponent>(Mount)` 성공 여부로 트럭(스태틱)/UGV(스켈레탈) 중 어느
  쪽을 보여줄지 분기하고 나머지는 숨김

이 작업은 **C++ 파일 수정**이라 Claude가 직접 컴파일 불가 — 사용자가 라이브
코딩/에디터 재시작으로 리빌드해야 반영됨.

### 6.3 카메라 재배치

기존 `Capture`는 작은 큐브가 액터 원점 근처에 있다는 전제로 위치/각도가 잡혀있었음.
실제 포탑은 원점에서 떨어진 `(대략 40,0,210)` 부근에 있어서, 그 지점을 바라보도록
역산해서 재배치: 위치 `(-360,-400,360)`, 회전 `(Pitch=-14.85,Yaw=45,Roll=0)`, FOV
30→60도.

### 6.4 ⚠️ 미해결 — 로딩 초반 전체 실루엣 잠깐 노출 후 완전히 사라짐

`TurretPoseableMesh`에도 실제 차체와 동일한 `BoundsScale=4` 처방을 적용했으나
**해결 안 됨**(사용자 확인, 2026-07-20). 증상: PIE 시작 로딩 중(프레임이 느릴 때)
잠깐 UGV 전체(포탑만이 아니라 차체까지 포함한) 검은 실루엣이 보였다가, 그 이후
완전히 안 보이게 됨.

**현재까지의 가설**(미검증): `HideBoneByName`의 렌더 상태 반영이 첫 프레임엔 아직 안
먹어서 전체 메시가 그대로 보이다가(그래서 포탑만이 아니라 전체 실루엣), 이후
본 숨기기는 적용되지만 5절과 같은 바운드 문제(이번엔 물리 시뮬레이션이 없는
컴포넌트라 `PhysicsAsset->CalcAABB()` 경로가 아니라 `GetSkinnedAsset()->GetBounds()`
정적 바운드 경로)로 컬링되는 것으로 추정 — 그러나 `BoundsScale=4`를 이미 적용했는데도
여전히 사라지는 걸 보면 이 가설만으로는 설명이 부족함. **사용자가 다음으로 미룸**
("일단 이거는 나중에 고쳐야 될거같아").

**다음에 시도해볼 것**:
- `BoundsScale`을 훨씬 더 크게(예: 10) 올려서 바운드 크기 자체가 원인인지 완전히
  배제/확정
- `bComponentUseFixedSkelBounds`/`bHiddenInGame`/`Capture`의 `ShowOnlyComponents` 등
  다른 가시성 관련 프로퍼티 재점검
- **대안(사용자가 제안, 아직 안 함)**: 포탑 부분(`Rotation_base` 이하)만 블렌더에서
  별도 스태틱 메시로 뽑아서 원래 `SyncTurretMesh`(스태틱메시 카피) 경로를 그대로
  쓰는 방식. Claude 판단으로는 지금 방식(SK_UGV 재사용)이 텍스처/모델 변경 시 자동
  동기화되는 장점이 있어 먼저 저 위 항목들부터 시도해보고, 그래도 안 되면 이
  대안으로 전환 권장. 만약 전환한다면 스켈레탈이 아니라 **스태틱 메시 하나**로
  뽑는 걸 권장(힌지 분리 포기, 작은 미리보기 아이콘이라 티 안 남) — 나중에
  TitanTruck에 실제 포탑 모델 필요해지면 그대로 재사용 가능.

---

## 7. TitanTruck 4분할 카메라 검은 화면 — 별개 버그, 해결 완료

RCWS/포탑 작업과 무관한 별개 버그지만 같은 세션에서 발견/수정.

**증상**: WBP_kadex에서 트럭 4방향 카메라 이미지가 전부 검은색, 방위각 표시하는 룰러
위젯은 정상.

**원인**: `QuadCamComponent::TickComponent`(플러그인, `QuadCamModule`)이
`bAlwaysVisible || bVisible`일 때만 `CaptureScene()`을 호출. `bVisible`은 M키 팝업
토글용 내부 상태라 possess 안 하면 절대 true가 안 되고, `bAlwaysVisible`은 기본값
`false`. WBP_kadex는 그 팝업 위젯을 안 거치고 `GetFrontRenderTarget()` 등을 직접
바인딩하는 구조라, **캡처 자체가 한 번도 안 돌아서 렌더타겟이 항상 초기(검은) 상태로
남아있었음.** 룰러 위젯은 순수 숫자 기반이라 이 문제와 무관하게 정상 표시됨.

**해결**: `BP_TitanTruck.QuadCam.bAlwaysVisible = true` (CDO + 레벨 배치 인스턴스 둘 다).
블루프린트 프로퍼티라 리빌드 불필요, 즉시 반영. `ugv_driving_dev_guide.md`에 이미
"나중에 대시보드에서 상시 표시할 때 씀. 지금은 기존 M키+possess 게이팅 그대로"라고
적혀있던 걸 보면, 이 플래그 자체는 미리 만들어놓고 실제로 켜는 걸 깜빡했던 것으로
보임.

---

## 8. 남은 미해결 항목 정리

1. **RCWS 미리보기 다이오라마 실루엣 소실** (6.4절) — 최우선 후속 작업 대상
2. **포탑 컬링의 정확한 해결책** (Physics Asset에 킨매틱 바디 추가, 5.4절) —
   `BoundsScale` 임시방편으로 일단 봉합됨, 근본 수정은 미착수
3. **바퀴 회전 관성 미해결** (`project_ugv_wheel_rotation_sync_unresolved` 메모리 참고) —
   이번 세션에서 안 건드림, 계속 후순위
