# Chaos Wheeled Vehicle — 스켈레톤 / Physics Asset 구성 요구사항

이전에 블렌더로 UGV 스켈레탈 메시(Root/Wheel/Turret/Barrel)를 처음부터 만들어 C++ Chaos
Wheeled Vehicle로 구성하려다 겪었던 3가지 문제(본 축 컨벤션, Root Body 75cm 오프셋, 바퀴
ContactPoint 붕괴)를 다시 마주치지 않기 위한 웹 리서치 정리. 디자인팀 blend 에셋으로 새로
시작할 때 이 문서의 체크리스트를 그대로 따라가면 됨.

**확인 상태 표기**: ✅ 공식문서/다수 소스로 확인됨 · ⚠️ 커뮤니티 사례 기반(공식 문서 없음) ·
❓ 확인 안 됨(추가 조사 필요)

---

## 0. 실전 체크리스트 (결론 먼저)

1. ✅ **바퀴 본은 반드시 Root 본의 "직계 자식"이어야 한다.** 차체(Body/Chassis) 본을 거쳐서
   달리면 안 됨.
2. ✅ Root 본 자체는 회전값 0, Blender에서 Ctrl+A로 트랜스폼 적용(apply) 완료 상태로 export.
3. ✅ Blender 씬 단위는 Metric, Unit Scale 0.01로 맞추고 export.
4. ✅ Armature FBX export 설정: **Primary Bone Axis = X**, **Secondary Bone Axis = -Y**,
   Main 탭 **Forward = -Y, Up = Z**. "Add Leaf Bones" 체크 해제.
5. ✅ 바퀴 본 피벗은 바퀴 회전 중심에 정확히 위치, 바퀴 중심이 X/Y축 정렬(전후/좌우 대칭)에
   맞아야 함.
6. ✅ Physics Asset에서 바퀴 본들을 전부 선택 → Body Creation에서 Primitive Type = Sphere →
   Re-generate Bodies. Physics Type은 **Simulated**(Kinematic 아님).
7. ✅ `WheelSetups` 배열의 바퀴 본 이름은 스켈레톤의 실제 본 이름과 **대소문자까지 완전히
   일치**해야 함 — 틀려도 에러 없이 그냥 그 바퀴가 죽은 채로 조용히 무시됨.
8. ⚠️ 스켈레탈 메시와 Physics Asset이 서로 다른 스켈레톤을 참조하면 "Could not find root
   physics body" 에러 — 항상 같은 Skeleton 에셋을 가리키는지 확인.
9. ⚠️ 본을 나중에 리네임하면 Physics Asset 바인딩이 깨짐 — UE5 Physics Asset Editor의
   **Tools > Update Bone References**로 점검.

---

## 1. 블렌더 → 언리얼 익스포트 워크플로우

### 축 정렬
Blender 본은 로컬 Y축이 본의 길이 방향(= 본 안에서 앞쪽)이고, FBX/언리얼 본은 -X 정렬을
전제로 함. 이 둘의 컨벤션이 다른 게 흔한 축 꼬임의 근본 원인.

권장 export 설정(Rafael Fernandes 가이드 기준, 다수 소스에서 반복 확인됨):
- **Armature 탭**: Primary Bone Axis = **X Axis**, Secondary Bone Axis = **-Y Axis**
- **Main 탭**: Forward = **-Y**, Up = **Z**
- "Add Leaf Bones" 옵션은 꺼둘 것

이렇게 맞추는 이유는 언리얼이 +X를 "전방", Z를 "위"로 쓰는 것과 본 축을 일치시켜서, 애니메이션
없이도 본을 소켓처럼 바로 회전 없이 쓸 수 있게 하기 위함. 단, 애니메이션(스켈레탈 애니메이션)이
있는 리그에서는 이 축 보정이 "보정된" 방향과 애니메이션 자체의 방향이 어긋날 수 있다는 경고가
있음 — 본 자체를 처음부터 이 컨벤션으로 만들고 애니메이션도 같은 컨벤션에서 제작하는 게 안전.
(출처: [Rafael Fernandes 가이드](https://ragatol.github.io/artigos/FBX_Blender_to_UE4/en.html))

### 흔한 실수 — 90도/특정 오프셋 회전 버그
"물리 애셋이 마치 90도 회전된 것처럼 충돌 판정된다"는 사례들의 공통 원인은 **Root 본 자체가
0이 아닌 회전값을 가진 채로 export됨**. Blender와 언리얼의 좌표계 차이 때문에 이 회전이 물리
애셋에는 반영 안 되고 시각 메시에만 반영되는 식으로 어긋남.

**수정**: export 전에 Blender에서 `Ctrl+A`로 회전/스케일 트랜스폼을 전부 적용(apply)해서 Root
본의 회전값이 정확히 0이 되도록 만들 것. (출처: [Physics Asset Misalignment 글](https://medium.com/@python-javascript-php-html-css/fixing-unreal-engine-physics-asset-misalignment-in-custom-skeletal-mesh-movement-1279e5c4d32c))

### 단위 스케일
Blender 프로젝트를 Metric, Unit Scale **0.01**로 맞춰서 export하는 게 관례로 확인됨 — 이걸
안 맞추면 다른 스케일 관련 버그(바퀴 위치가 원점에 스폰되는 등)로 번질 수 있음. ⚠️ (출처:
Chaos Vehicle 포럼 스레드, 아래 3절 참고)

---

## 2. Chaos Vehicle용 스켈레톤 구조 요구사항 — 가장 중요한 발견

### ✅ 핵심 규칙: 바퀴 본은 Root의 직계 자식이어야 함

여러 공식/커뮤니티 소스에서 일관되게 확인된 규칙:

> "Individual wheel bones for each wheel... **must be parented to the root bone, not the
> body bone**." (Chaos Vehicle 셋업 가이드 요약)

즉 권장 계층은:
```
Root (원점, 회전 0)
├── Body (차체 비주얼용, 옵션)
├── Wheel_Front_Left
├── Wheel_Front_Right
├── Wheel_Rear_Left
└── Wheel_Rear_Right
```
바퀴 본이 `Root → Body → Wheel_*` 식으로 Body를 거쳐서 매달리면 안 되고, `Root → Wheel_*`로
바로 붙어야 함.

### ✅ 실제 버그 사례로 재확인됨

Epic 공식 포럼 스레드(["Chaos vehicle is acting odd on one particular skeletal mesh"](https://forums.unrealengine.com/t/chaos-vehicle-is-acting-odd-on-one-particular-skeletal-mesh/629713))에서
정확히 우리가 겪었던 것과 같은 계열의 증상이 보고됨: 바퀴가 입력에 반응해서 회전은 하는데
지면과 충돌 판정이 전혀 안 됨, 콜리전 박스 위치를 옮기면 튕기거나 미끄러지거나 날아가버림.

원인 진단(KaidoomDev): **"the wheel bones are not direct children of root"** — 바퀴 본이
Root의 직계 자식이 아니었던 것.

수정 방법: 기존 아마추어를 고치려 하지 말고 **삭제 후 재구성**. 바퀴 본을 Root 직계 자식으로,
X/Y/Z 축 정렬 맞춰서 새로 배치 → 기존 버텍스 그룹을 새 본에 재할당 → 재export. 사용자 확인:
"정상 작동함."

**우리 사례와의 연결**: intro.md/M1A2 문서에서 언급한 "바퀴 16개의 SuspensionState.ContactPoint가
전부 비슷한 좌표로 붕괴하는 원인불명 버그"와 "Root Body 분리 시 75cm 오프셋 버그"는 십중팔구
**바퀴 본이 Root 직계 자식이 아니라 Body(차체) 본을 거쳐 매달려 있었던 것**이 원인일 가능성이
매우 높음. 다음 항목(3절)의 `FindRootBodyIndex()` 동작과 결합하면 정확히 이 증상(붕괴/오프셋)이
설명됨.

### ⚠️ 다른 계열 시스템(AVS 등)과의 차이 주의

마켓플레이스 서드파티 비히클 시스템(예: Advanced Vehicle System/AVS)의 문서에는 반대로 "Chassis가
곧 Root 본이어야 한다"는 안내도 있었음. 이건 **AVS 자체의 독자적인 컨벤션**이라 네이티브 Chaos
Vehicle(`UChaosWheeledVehicleMovementComponent`)의 정식 컨벤션과 다를 수 있음 — 네이티브 Chaos
Vehicle을 쓸 거면 위의 "Root ≠ Body, 바퀴는 Root 직계 자식" 규칙을 따르는 게 맞음. ❓ AVS와
네이티브 Chaos의 차이가 실제로 구조적인지, 단순 용어 차이인지는 추가 확인 필요.

---

## 3. Physics Asset 구성 규칙

### `FindRootBodyIndex()` / RootBodyData 관련

`USkeletalMeshComponent`에는 `RootBodyData`(물리 애셋 계층에서 "최상위 바디"의 인덱스를 담는
프로퍼티)가 있고, 이걸 계산하는 로직이 "계층상 가장 앞쪽 본 중 Physics Asset 바디가 존재하는
첫 본"을 자동으로 루트 바디로 선택하는 방식이라는 것까지는 이전 M1A2 작업 때 엔진 소스 레벨에서
확인된 상태(재확인은 못 함, ❓ 이번 리서치에서는 공식 문서/포럼에 이 함수명을 직접 언급하는
자료를 찾지 못함 — 엔진 소스 재열람 필요).

이번 리서치로 간접 확인된 사실: **Root 본 자체에 물리 바디가 없고 자식 본(Body)에만 물리
바디가 있는 구조는 여러 사례에서 문제(붕괴, 오프셋, 이상 거동)의 원인으로 지목됨.** 안전한
회피 규칙:

- **Root 본 자체에도 최소한의 물리 바디(작은 박스/캡슐 등)를 만들어서, 물리 애셋의 "루트 바디"가
  실제 Root 본과 일치하도록 강제할 것.** 이렇게 하면 `FindRootBodyIndex()`가 엉뚱한 자식 본을
  집어갈 여지가 없어짐.
- 위 2절의 규칙(바퀴는 Root 직계 자식)과 같이 지키면 이중으로 안전.

### 바퀴/서스펜션 바디 생성

공식 문서(["How to Set up Vehicles in Unreal Engine"](https://dev.epicgames.com/documentation/en-us/unreal-engine/how-to-set-up-vehicles-in-unreal-engine),
UE5.8) 기준 확인된 절차:

1. Physics Asset Editor에서 Skeleton Tree의 바퀴 본들을 전부 선택
2. Tools 창 → Body Creation → Primitive Type = **Sphere** → **Re-generate Bodies**
   (구르는 동작에 적합하도록 컨벡스 헐 대신 구체 프리미티브 사용)
3. 서스펜션 관련 본(있다면)은 우클릭 → **Collision > No Collision**으로 콜리전 자체를 꺼둠
4. 바퀴 물리 바디의 **Physics Type = Simulated**(Kinematic이면 안 됨) — 이 항목은 여러 트러블슈팅
   자료에서 "빠뜨리면 조용히 실패"하는 항목으로 반복 지적됨

차체(Chassis/Body)는 컨벡스 헐이나 박스로 전체를 덮는 콜리전을 만들고 Mass를 여기 설정
(승용차 기준 1500~2000kg 정도가 예시로 언급됨 — 우리 UGV는 M1A2 문서 기준 Mass=3000으로
이미 스케일 조정된 값 사용 중이니 참고만).

### 바퀴 본 이름 매칭

`WheelSetups`(또는 `ChaosWheeledVehicleComponent`의 바퀴 설정 배열)에 등록하는 바퀴 본 이름은
스켈레톤의 실제 본 이름과 **글자 하나까지 완전히 일치**해야 함. 틀리면 에러 메시지 없이 그냥 그
바퀴가 죽은 채로(입력 무시, 서스펜션 미작동) 조용히 넘어감 — 디버깅 우선순위 1번으로 항상 먼저
스켈레톤 트리와 대조해서 복붙으로 채울 것.

### "Could not find root physics body" 에러

증상: 스켈레탈 메시는 정상 스폰되는데 물리 바디가 하나도 안 붙음. 확인된 원인: **스켈레탈
메시와 Physics Asset이 서로 다른 Skeleton 에셋을 참조**하고 있을 때 발생. 본을 리네임하거나
스켈레톤을 재생성했을 때 이 불일치가 생기기 쉬움 — Physics Asset Editor의 **Tools > Update
Bone References**로 바인딩이 깨졌는지 점검 가능(UE5 기능). (출처: [Epic 포럼](https://forums.unrealengine.com/t/could-not-find-root-physics-body/488194))

---

## 4. 바퀴 본(Wheel Bone) 배치 규칙

- 바퀴 본 피벗은 **바퀴가 실제로 회전하는 중심**(휠 허브 중심)에 정확히 위치해야 함 — 여기가
  어긋나면 시각적으로 바퀴가 미끄러지듯 돌거나, 서스펜션 압축/신장 애니메이션이 이상하게 보임.
- 바퀴 중심은 **X축(전후) / Y축(좌우) 기준으로 정렬**되어 있어야 함 — 예: 좌우 바퀴가 Y=0 기준
  대칭, 앞뒤 바퀴 축이 X축에 나란히.
- 바퀴의 "정면"이 X축을 향해야 함(= 차량 전체의 전방과 동일 컨벤션) — 개별 바퀴 본이 서로 다른
  회전 기준을 갖고 있으면 안 됨.
- ⚠️ 알려진 함정: 구버전 Blender의 FBX export 플러그인이 **바퀴 본의 트랜스폼을 제대로 적용하지
  않고 원점(0,0,0)에 스폰시키는 버그**가 있다는 커뮤니티 보고 있음 — export 후 반드시 Unreal
  Physics Asset Editor에서 바퀴 본 실제 좌표를 눈으로 확인할 것. (출처: Neutronio Games 가이드)
- **서스펜션 ContactPoint에 영향을 주는 요소**(확인된 것): 바퀴 본 위치(서스펜션의 "정지
  위치" 기준점), 바퀴 물리 바디의 반지름(Sphere 프리미티브 크기), `SuspensionMaxRaise`/
  `SuspensionMaxDrop`(서스펜션이 늘어나고 줄어들 수 있는 범위 — 이 범위 밖이면 지면 접촉을
  못 찾음). ContactPoint 자체의 정확한 계산식(솔버 내부)은 이번 리서치 범위에서 확인 못함 —
  03번 서스펜션 문서(다른 리서치 트랙)에서 더 깊게 다룰 것으로 예상됨. ❓

---

## 5. 콜리전 위치와 비주얼 위치 불일치 문제

intro.md에서 언급된 "콜리전 기준 위치와 시각적 위치가 불일치" 증상의 확인된 원인들:

1. **가장 흔한 원인 (✅ 다수 확인)**: Blender에서 **Root 본에 0이 아닌 회전값**이 남아있는 채로
   export됨. Blender와 언리얼의 좌표계 차이 때문에 이 회전이 스켈레탈 메시(비주얼)에는
   반영되지만 물리 애셋 바디 배치 기준에는 어긋나게 반영되어, "마치 물리 애셋이 90도 회전된
   것처럼" 보이는 결과가 나옴. → **해결**: export 전 Blender에서 Ctrl+A로 트랜스폼을 전부
   적용(apply)해서 Root 본 회전이 정확히 0인 상태로 만들 것.
2. **본 리네임 후 바인딩 깨짐 (⚠️)**: Physics Asset의 바디는 본 이름으로 바인딩되는데, 본을
   리네임하면 바인딩이 깨진 채로 조용히 어긋난 위치를 참조할 수 있음 — Update Bone References로
   점검.
3. **피벗 오프셋 자체 문제 (❓)**: 메시 자체의 피벗(Origin)이 예상 위치에 있지 않은 경우도
   흔한 원인으로 언급되지만, 구체적 사례/수치는 이번 리서치에서 추가로 못 찾음.

디버깅 팁(확인됨): 문제가 의심되면 `DrawDebugHelpers`로 물리 콜리전 범위를 직접 그려서 비주얼
메시와 겹쳐보고 육안으로 어긋난 정도/방향을 확인하는 방법이 실전에서 쓰임.

---

## 출처

- [How to Set up Vehicles in Unreal Engine (UE5.8 공식문서)](https://dev.epicgames.com/documentation/en-us/unreal-engine/how-to-set-up-vehicles-in-unreal-engine)
- [How to Convert PhysX Vehicles to Chaos in Unreal Engine (공식문서)](https://dev.epicgames.com/documentation/en-us/unreal-engine/how-to-convert-physx-vehicles-to-chaos-in-unreal-engine)
- [Chaos vehicle is acting odd on one particular skeletal mesh (Epic 포럼, 바퀴 본-Root 직계자식 버그 실사례)](https://forums.unrealengine.com/t/chaos-vehicle-is-acting-odd-on-one-particular-skeletal-mesh/629713)
- [Could not find root physics body (Epic 포럼)](https://forums.unrealengine.com/t/could-not-find-root-physics-body/488194)
- [Rafael Fernandes — Exporting models from Blender to Unreal Engine 4 (본 축 export 설정)](https://ragatol.github.io/artigos/FBX_Blender_to_UE4/en.html)
- [Fixing Unreal Engine Physics Asset Misalignment in Custom Skeletal Mesh Movement (Root 본 회전 미적용 문제)](https://medium.com/@python-javascript-php-html-css/fixing-unreal-engine-physics-asset-misalignment-in-custom-skeletal-mesh-movement-1279e5c4d32c)
- [The Ultimate Chaos Vehicle Guide — Neutronio Games](https://neutronio.games/gamedev/unreal-engine/unreal-the-ultimate-chaos-vehicle-guide/)
- [Fix: Unreal Chaos Vehicle Not Moving or Responding to Input — Bugnet Blog](https://bugnet.io/blog/fix-unreal-chaos-vehicle-not-moving)

## 확인 안 된 부분 (추가 조사 필요 목록)

- `FindRootBodyIndex()`/`RootBodyData` 계산 로직의 정확한 소스코드 재확인 (이전 세션에서 엔진
  소스를 직접 읽고 확인했었다는데, 이번 웹 리서치로는 재현 못함 — 엔진 설치 경로에서
  `SkeletalMeshComponentPhysics.cpp` 등을 직접 열람 권장)
- `SuspensionState.ContactPoint` 계산식 자체의 소스 레벨 근거 (다른 서스펜션 조사 트랙 참고)
- AVS 등 서드파티 비히클 시스템의 "Chassis=Root" 컨벤션이 네이티브 Chaos와 실제로 다른 요구사항인지,
  단순 명명 차이인지
