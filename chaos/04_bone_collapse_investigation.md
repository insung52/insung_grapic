# 바퀴 서스펜션 위치가 전부 모델 원점으로 붕괴하는 문제 — 후속 조사

## 🚨 최종 정정 — 이 문서의 결론은 진짜 원인이 아니었음

이 문서 전체(아래 0~4절)는 "`WheelSetups`의 `BoneName` 매칭 실패로 `GetComposedRefPoseMatrix`가
Identity를 리턴한다"는 가설을 소스 코드로 뒷받침하는 내용인데, chaostest 프로젝트에서 실제로
재현/디버깅해본 결과 **이건 틀렸다.** BoneName은 계속 정확히 매칭되고 있었다. 진짜 원인은
**Blender FBX export가 Root 본에 Scale=100을 잘못 굽는 알려진 버그**였다 — 상세 원인과 검증된
해결 절차는 → **[05_SOLVED_blender_export_scale_bug.md](05_SOLVED_blender_export_scale_bug.md) 참고.**

아래 내용은 그 결론에 도달하기까지 반증해나간 과정 기록으로만 남겨둠(소스 코드 호출 체인
분석 자체는 정확하고 여전히 유용함 — `GetWheelRestingPosition`/`LocateBoneOffset`/
`SetupSuspension` 등의 실제 동작 방식 참고용).

---

## ✅ 0. 소스 코드로 최종 확정 (2026-07-16, UE 5.8 로컬 엔진 소스 직접 확인) — ⚠️ 위 정정 참고, 결론은 틀렸음

로컬 엔진 설치(`C:\Program Files\Epic Games\UE_5.8\Engine\...`)에 전체 소스(.cpp 포함)가
있어서, 아래 1절의 [커뮤니티]/[가설] 추정을 **소스 코드로 100% 확정**함. 결론: **1절의
"BoneName 매칭 실패 시 차량 원점 폴백" 가설이 정확히 맞았고, 정확한 메커니즘까지 특정됨.**

### 확정된 호출 체인

```
UChaosWheeledVehicleMovementComponent::GetWheelRestingPosition(WheelSetup)   // ChaosWheeledVehicleMovementComponent.cpp:1695
  Offset = WheelSetup.WheelClass.GetDefaultObject()->Offset + WheelSetup.AdditionalOffset
  return LocateBoneOffset(WheelSetup.BoneName, Offset)
      ↓
UChaosVehicleMovementComponent::LocateBoneOffset(InBoneName, InExtraOffset)  // ChaosVehicleMovementComponent.cpp:1529
  BonePosition = Mesh->GetSkinnedAsset()->GetComposedRefPoseMatrix(InBoneName).GetOrigin() * Mesh->GetRelativeScale3D()
  RootBodyMTX  = GetComposedRefPoseMatrix(RootBody의 BoneName)   // Physics Asset 루트 바디 기준
  LocalBonePosition = RootBodyMTX.InverseTransformPosition(BonePosition)
  return InExtraOffset + LocalBonePosition
      ↓
USkeletalMesh::GetComposedRefPoseMatrix(FName InBoneName)   // SkeletalMesh.cpp:5422
  BoneIndex = GetRefSkeleton().FindBoneIndex(InBoneName)
  if (BoneIndex != INDEX_NONE) return 실제 본의 레퍼런스 포즈 행렬
  else {
      Socket = FindSocket(InBoneName)   // 본이 아니라 소켓 이름일 가능성도 체크
      if (Socket found) return 소켓 기준 보정된 행렬
      else return FMatrix::Identity     // ★★★ 여기 — 본도 소켓도 못 찾으면 그냥 Identity(원점) ★★★
  }
```

### 이게 뜻하는 것

`WheelSetups[i].BoneName`에 적어놓은 문자열이 스켈레톤의 `RefSkeleton`에서 (본 이름으로도,
소켓 이름으로도) **매칭되지 않으면, 아무 에러/경고 없이 `FMatrix::Identity`가 리턴되고
그 바퀴의 기준 위치는 정확히 원점(스케일해도 0×Scale=0)이 된다.** 이건 "차량 원점으로
폴백"이라는 04번 조사 1절의 커뮤니티 기반 가설이 아니라, **소스 코드에 명시적으로 그렇게
짜여 있는 확정된 사실**임 (`SkeletalMesh.cpp:5450`의 `return LocalPose;`가 초기값
`FMatrix::Identity`를 그대로 리턴하는 경로).

또한 `CanCreateVehicle()`(`ChaosWheeledVehicleMovementComponent.cpp:1291`)은 **`BoneName ==
NAME_None`(완전히 비어있음)일 때만** 차량 생성을 막고 경고를 띄운다 — **BoneName에 값이
있지만 스켈레톤에 실제로 없는 이름인 경우는 이 체크를 통과**하고, 위 흐름을 타고 조용히
원점으로 수렴한다. 즉 **"본은 스켈레톤에 정상 배치돼 있는데 서스펜션은 원점에 몰림"이라는
사용자의 정확한 증상 = `WheelSetups`에 입력한 `BoneName` 문자열이 실제 임포트된 스켈레톤의
본 이름과 글자 단위로 어긋나 있었다는 뜻이 됨.** (대소문자는 `FName` 비교가 기본적으로
대소문자 무시라 원인이 아닐 가능성이 높음 — 언더스코어, 접두사/접미사, 오타, 혹은 FBX
임포트 시 자동으로 붙는 이름 변경/중복 접미사(`_1` 등)를 의심할 것.)

**16개 전부가 동시에 실패했다는 점**은 오히려 단서다 — 하나하나 손으로 오타 냈을 확률보다는,
`WheelSetups`를 만들 때 쓴 이름 패턴(예: 템플릿에서 복사한 이름 형식)과 Blender→FBX→언리얼
임포트 후 실제로 붙은 본 이름 패턴이 **애초에 체계적으로 달랐을 가능성**이 높다 (예:
"Wheel_01" vs 실제로는 "wheel_01" 뒤에 임포트 시 원치 않는 접미사가 붙었거나, 소켓으로
착각하고 만들었거나 등).

### 이번 소스 확인으로 폐기/보강되는 부분

- 04번 문서 1절의 "BoneName 미매칭 시 차량 원점 폴백" → **[커뮤니티]에서 [확인됨]으로 격상**,
  정확한 함수/라인까지 특정됨(`SkeletalMesh.cpp:5422-5451`).
- 04번 문서 2절의 "Blender 레스트 포즈 깨짐 버그"는 **여전히 유효한 별도 가능성으로 남음** —
  본이 스킨 안 돼서 export 시 좌표 자체가 깨지는 경우에도 결과적으로 "본은 있지만 좌표가
  이상함" 상태가 될 수 있는데, 이 경우는 `FindBoneIndex`는 성공(Identity 폴백이 아니라
  진짜 깨진 좌표 리턴)하므로 위 원점 폴백 메커니즘과는 **다른 경로**다. 다음 시도에서 실제
  증상이 재현되면 "본 이름 자체가 매칭 안 됨(이번 확정 사항)"인지 "이름은 맞는데 좌표 값이
  깨짐(2절 가설)"인지 Skeleton Editor에서 본 이름 매칭 여부부터 확인해서 구분할 것.
- 03번 문서 2절의 "스케일이 `Offset`에 안 곱해짐" 가설도 소스로 재확인됨: 위 호출 체인에서
  `InExtraOffset`(Wheel BP의 `Offset` 프로퍼티, 사용자가 넣은 +Z=50)은 **스케일이 전혀
  곱해지지 않고 그대로 더해짐**. 반면 본의 레퍼런스 포즈 위치(`BonePosition`)는
  `* Mesh->GetRelativeScale3D()`로 **스케일이 곱해짐**. 즉 본 매칭이 정상인 상황에서는
  03번 문서의 가설이 맞다(Offset만 스케일 미반영) — 다만 사용자가 이번에 겪은 "전부 원점에
  몰림" 증상 자체는 위 원점 폴백(BoneName 매칭 실패)이 훨씬 유력한 설명임.

### `CreateSuspension` 이후 — 이 값이 실제로 쓰이는 지점

`FixupSkeletalMesh()`(`ChaosWheeledVehicleMovementComponent.cpp:1256-1257`)에서
`GetWheelRestingPosition(WheelSetup)`으로 계산한 로컬 좌표(`LocalWheel`)를
`FPhysicsInterface::CreateSuspension(Chassis, LocalWheel)`에 그대로 넘겨서, **섀시(루트
바디) 기준 상대 위치로 서스펜션 제약(Constraint)의 앵커를 만든다.** 이 값이 원점이면 진짜
물리 엔진 레벨에서 그 바퀴는 섀시 원점에 서스펜션이 붙은 것으로 취급된다 — 콜리전/시각
메시가 멀쩡해 보여도 물리적으로는 완전히 다른 곳에 앵커가 잡히는 게 소스 레벨에서
당연한 결과임이 확인됨.

---


`01`~`03`번 문서의 후속 조사. 사용자가 직접 정정한 내용을 바탕으로 재조사한 결과
(`00_overview.md`의 정정 사항 참고): 이전에 "Root 직계 자식 여부"나 "스케일-Offset
곱셈 문제"로 지목했던 원인은 사용자가 이미 배제한 가설이었다. 실제 증상은 **바퀴
16개의 서스펜션 계산 위치(ContactPoint 등)가 각 바퀴 본의 실제 위치와 무관하게 전부
모델 원점 근처로 몰려있었다**는 것.

확인 표기: **[공식]** Epic 공식 문서 · **[커뮤니티]** 포럼/블로그(신뢰도 있으나 비공식) ·
**[가설]** 정황 증거 기반 추정, 미확정.

---

## 결론 먼저 — 사용자 질문("본 배치에 정해진 형식/각도가 있는가")에 대한 답

**있다.** 다음 세 가지가 언리얼/Chaos Vehicle이 실질적으로 강제하는 "형식"이다.

1. **바퀴 본의 회전(각도) 컨벤션**: 각 바퀴 본은 로컬 축이 **X=전방, Y=우측, Z=상단**을
   향하도록 배치되어야 한다 [커뮤니티, Neutronio 가이드 — 다수 튜토리얼에서 반복 확인].
   이건 02번 문서에서 다룬 "전체 스켈레톤 축 정렬(export 설정)"과는 별개로, **바퀴 본
   개별의 로컬 회전**에 대한 요구사항이다. 이게 틀어지면 바퀴가 잘못된 축으로
   구르거나 서스펜션이 엉뚱한 방향으로 압축/신장한다.
2. **본 이름은 글자 그대로(대소문자·언더스코어) 일치해야 함**: `WheelSetups`의
   `BoneName`이 스켈레톤의 실제 본 이름과 정확히 일치하지 않으면 **에러 없이 조용히
   실패**한다 [공식+커뮤니티, 02번 문서에서도 이미 확인].
3. **본 위치(트랜스폼)가 export 시점에 실제로 "적용(bake)"되어 있어야 함**: 아래 2절에서
   자세히 다루는, 이번 조사의 핵심 발견.

이 세 가지 중 하나라도 어긋나면 "본은 스켈레톤 트리에서 눈으로 보기엔 정상 위치에
있는데 Chaos Vehicle은 엉뚱한 곳을 서스펜션 기준점으로 쓴다"는, 정확히 사용자가 겪은
증상이 재현된다.

---

## 1. 결정적 발견 — BoneName 매칭 실패 시 정확히 "차량 원점"으로 폴백된다

이번 조사에서 찾은 가장 중요한 단서 [커뮤니티, 다수 소스 교차 확인]:

> **"본 이름을 지정(BoneName)했으면 서스펜션 오프셋 계산 기준점은 그 본의 위치가 된다.
> 본 이름이 지정되지 않았거나(또는 매칭 실패로 사실상 못 찾으면) 기준점은 차량(Pawn)의
> 원점이 된다."**

즉 Chaos Vehicle의 휠 위치 계산에는 애초에 **명시적인 폴백 경로가 "차량 원점"으로
설계되어 있다.** 사용자가 겪은 "바퀴 16개가 전부 모델 원점 근처로 몰림" 증상은,
개별 바퀴 위치가 조금씩 어긋난 게 아니라 **다수(혹은 전부)의 바퀴 본 이름 매칭이
실패해서 전부 동일한 폴백 지점(차량 원점)으로 수렴한 것**이라는 설명과 정확히
일치한다. 콜리전/시각적 위치가 눈으로는 정상으로 보였다는 것도 모순되지 않는다 —
스켈레탈 메시 렌더링과 애니메이션은 본 트랜스폼을 그대로 쓰지만, `WheelSetups`의
`BoneName` 문자열 매칭은 완전히 별개의 조회 과정이기 때문에, 본 자체는 정상이어도
이름 문자열만 어긋나면 조용히 실패한다.

이 가설을 뒷받침하는 것: Epic 공식 포럼 스레드 [Chaos Vehicles - VehicleMovement
Component Wheel Setup problem](https://forums.unrealengine.com/t/chaos-vehicles-vehiclemovement-component-wheel-setup-problem/768602)에서
정확히 같은 증상(바퀴들이 전부 비슷한 위치에 생성됨)이 보고됐고, 2024년 다른
사용자(SpaceCake1999)도 **공식 예제와 동일한 본 계층을 그대로 따랐는데도** 같은 문제를
겪었다고 증언 — 즉 이 문제는 "계층 구조를 잘못 짜서"가 아니라 **이름 매칭/트랜스폼
데이터 자체가 깨지는 더 근본적인 지점**에서 발생할 수 있다는 뜻이다. 이 스레드는
**미해결로 남아있다** — 즉 커뮤니티도 정확한 근본 원인을 콕 집어내지 못했다는 뜻이므로,
아래 2절의 "왜 이름 매칭이 실패했을 가능성이 있는가"를 반드시 함께 볼 것.

---

## 2. 왜 이름 매칭 자체가 실패했을 수 있는가 — Blender FBX export의 알려진 버그

가설 1(스킨 웨이트 없는 본이 제거됨)과 가설 2(바인드 포즈 시점 문제)를 조사하는 과정에서,
서로 무관해 보였던 두 가설이 **Blender FBX 익스포터의 알려진 버그 하나로 합쳐진다**는
것을 발견했다.

### 2.1 핵심 버그: "스킨된 메시가 없는 본은 export 시 레스트 포즈가 깨진다" [커뮤니티, Blender 공식 버그 트래커]

Blender 공식 버그 트래커에 등록된 이슈 [FBX export of armature changes rest pose if
without weighted mesh](https://projects.blender.org/blender/blender/issues/113073):

> 스킨 웨이트가 바인딩된 메시 없이 아마추어(스켈레톤)를 export하면, **"레스트 포즈"
> 자체가 export 안 되고, 그 대신 export 시점의 "현재 포즈"가 레스트 포즈로 둔갑해서
> 저장된다.**

이게 바퀴 본에 어떻게 적용되는지: 바퀴 본이 실제 지오메트리(타이어 메시)에 버텍스
그룹으로 스킨되어 있지 않고 **순수 관절/기준점(소켓 용도) 본으로만 존재**하는 경우 —
이런 구조는 실제로 매우 흔하다(바퀴가 개별 스태틱 메시이거나, 스켈레탈 메시 안에서도
바퀴 지오메트리가 다른 방식으로 붙어있는 경우) — Blender가 "이 본은 어차피 스킨
안 됐으니 레스트 포즈를 제대로 기록 안 해도 된다"고 판단하고, 그 순간 뷰포트에
표시되던 포즈(혹은 완전히 예측 불가능한 값)를 그대로 export해버릴 수 있다는 뜻이다.

이 버그가 실제로 일어났다면, 결과는 다음 둘 중 하나로 나타날 수 있다:
- 언리얼이 import한 본 위치가 Blender 뷰포트에서 보던 것과 다름(하지만 애니메이션이나
  단순 배치 확인으로는 눈치채기 어려움 — 특히 16개 바퀴처럼 반복되는 구조는 하나하나
  꼼꼼히 좌표까지 확인하지 않으면 놓치기 쉬움)
- 본 자체의 트랜스폼 데이터가 손상되어, `WheelSetups`가 본 위치를 읽어올 때 비정상적인
  값(예: 0에 가까운 값, 즉 아마추어 원점 근처)을 돌려받음

### 2.2 관련 버그 — "메시 없이 export된 본은 임포트 시 취급이 불안정" [커뮤니티]

같은 계열의 추가 버그 리포트([Armature Transform being Applied to Root bone on Export,
changing Bindpose](https://github.com/KhronosGroup/glTF-Blender-IO/issues/994) — glTF
익스포터 사례지만 근본 메커니즘은 FBX와 유사한 "본 트랜스폼이 export 파이프라인에서
재계산되며 어긋난다"는 동일 패턴)도 확인됨. 결론적으로 **"메시에 스킨되지 않은 본의
트랜스폼이 export 과정에서 신뢰할 수 없게 된다"는 것은 Blender→FBX 파이프라인 전반에
걸쳐 반복적으로 보고되는 알려진 취약 지점**이다.

### 2.3 가설 1(스킨 웨이트 없는 본이 물리적으로 "제거"됨)은 반은 맞고 반은 다르다

원래 조사하려던 가설(언리얼이 스킨 안 된 본을 아예 제거/스트립한다)은 정확히는
확인되지 않았다 — 오히려 언리얼 Skeleton Editor는 "이 본은 메시에 쓰이지만 스킨
웨이트가 없다"는 **경고만 띄우고 본 자체는 유지**하는 것으로 보인다 [공식 문서 기준,
`FBX Import Errors` 문서]. 즉 **본이 사라지는 게 아니라, 그 본에 담긴 좌표값 자체가
Blender export 단계에서 이미 틀어져 있었을 가능성이 훨씬 높다** — 문제가 언리얼
쪽이 아니라 Blender export 단계에 있다는 쪽으로 결론이 이동함.

### 2.4 종합 — 가장 설득력 있는 인과 사슬

```
바퀴 본이 타이어 지오메트리에 스킨 웨이트로 안 묶여 있음(순수 관절/기준점 본)
   ↓ [Blender FBX 익스포터 알려진 버그, projects.blender.org #113073]
export 시 레스트 포즈가 깨져서 실제 좌표와 다른 값(원점 근처일 가능성 높음)으로 export됨
   ↓
언리얼이 이 잘못된 좌표를 "본의 위치"로 그대로 import — 스켈레톤 트리에서 봐도
잘못됐다는 걸 눈치채기 어려움(16개가 다 비슷하게 틀어지면 상대적으로 "정상처럼" 보임)
   ↓ [Chaos Vehicle 공식 동작 — 1절]
BoneName은 정확히 매칭되지만, 그 본이 가리키는 좌표 자체가 이미 원점 근처이므로
서스펜션 계산 기준점도 원점 근처로 몰림
```

**주의**: 이건 [가설]이다. "본 이름 매칭 실패로 원점 폴백"(1절)과 "본 좌표 자체가
export 단계에서 깨짐"(2절) 둘 다 최종 증상(원점 근처로 붕괴)은 동일하게 설명하지만,
정확히 어느 쪽이었는지는 이번 웹 리서치만으로는 확정할 수 없다. 다음 시도에서
3절의 진단 절차로 실제 구분 가능.

---

## 3. 재발 방지 / 빠른 진단 체크리스트

### 3.1 Blender 단계에서 예방
- [ ] 바퀴 본을 만들 때 **타이어 메시에 최소한의 버텍스 웨이트라도 바인딩**해둘 것
      (완전히 스킨 안 된 순수 관절 본으로 두지 말 것 — 2.1절 버그 회피). 바퀴가
      개별 스태틱 메시라도, 스켈레탈 메시 쪽에 더미 버텍스 하나라도 그 본에 약하게
      웨이트를 줘서 "스킨된 본"으로 만들어두는 게 안전.
- [ ] 바퀴 본의 로컬 축이 X=전방/Y=우측/Z=상단이 되도록 배치 (1절 형식 요구사항)
- [ ] export 직전 Blender에서 **Pose Mode가 아니라 반드시 Rest Position(레스트
      포지션)**인 상태인지 확인 (현재 포즈가 export 시 레스트 포즈로 둔갑하는
      버그의 직접적 회피)
- [ ] Ctrl+A로 전체 오브젝트(아마추어+메시) 트랜스폼 적용 후 export

### 3.2 Import 직후 언리얼에서 검증 (가장 중요 — 이번에 놓쳤던 단계로 추정)
- [ ] Skeleton Editor에서 **바퀴 본 하나씩 선택해서 Details 패널의 실제 Location
      좌표값을 숫자로 확인** — 육안으로 "위치가 맞아 보인다"만으로 넘어가지 말 것.
      16개 바퀴라면 좌우/전후 대칭이 되는지 좌표를 직접 대조.
- [ ] 특히 **여러 바퀴 본의 좌표가 서로 의심스럽게 비슷하거나 0에 가까우면** 이번에
      발견한 버그가 재현된 것 — export 단계로 돌아가 2.1절 회피책 적용
- [ ] Physics Asset Editor에서 바퀴 물리 바디들이 생성된 후, 뷰포트에서 **스켈레탈
      메시 콜리전을 와이어프레임으로 겹쳐서** 각 구체가 실제 바퀴 위치와 겹치는지 확인

### 3.3 Chaos Vehicle 설정 후 런타임 진단
- [ ] PIE 중 `BreakWheelStatus` 결과(`ContactPoint` 등)를 화면에 디버그 출력해서 실제
      값이 각 바퀴 본 위치와 얼마나 가까운지 수치로 비교 (본 위치는 Import 검증
      단계에서 이미 기록해둔 값과 대조)
- [ ] `WheelSetups`의 `BoneName` 필드를 하나하나 **스켈레톤 트리에서 복사-붙여넣기**로
      다시 채워서, 手打(수동 타이핑)로 인한 오타 가능성을 원천 차단
- [ ] 위 과정 후에도 재현되면: 바퀴 본 하나만 있는 최소 재현 프로젝트(바퀴 1개 + 루트만)를
      새로 만들어서 동일 export 파이프라인으로 테스트 — 최소 구성에서도 재현되면 Blender
      export 버그가 원인이라는 게 사실상 확정됨(변수 제거)

---

## 출처

- [Chaos Vehicles - VehicleMovement Component Wheel Setup problem (Epic 포럼, 정확히 같은 증상 · 미해결)](https://forums.unrealengine.com/t/chaos-vehicles-vehiclemovement-component-wheel-setup-problem/768602)
- [The Ultimate Chaos Vehicle Guide - Neutronio Games (바퀴 본 회전/축 요구사항, BoneName 미지정 시 차량 원점 폴백)](https://neutronio.games/gamedev/unreal-engine/unreal-the-ultimate-chaos-vehicle-guide/)
- [FBX export of armature changes rest pose if without weighted mesh (Blender 공식 버그 트래커)](https://projects.blender.org/blender/blender/issues/113073)
- [FBX export of armature changes rest pose if without weighted mesh (blender-addons 트래커, 중복 이슈)](https://projects.blender.org/blender/blender-addons/issues/104937)
- [Armature Transform being Applied to Root bone on Export, changing Bindpose (glTF 익스포터, 동일 패턴 참고용)](https://github.com/KhronosGroup/glTF-Blender-IO/issues/994)
- [FBX Import Errors in Unreal Engine (공식문서, 스킨 웨이트 없는 본 경고 메시지)](https://dev.epicgames.com/documentation/en-us/unreal-engine/fbx-import-errors-in-unreal-engine)
- [Importing an fbx skeletal mesh from Blender ... bones too small (Blender 애드온 트래커, 관련 워크어라운드)](https://projects.blender.org/blender/blender-addons/issues/47043)

## 확인 안 된 부분 (추가 조사 필요)

- ~~1절의 "BoneName 미매칭 시 차량 원점 폴백"이 실제 엔진 소스의 정확히 어느 함수/라인에서
  일어나는지~~ → **0절에서 소스로 확정 완료** (`ChaosVehicleMovementComponent.cpp:1529`
  `LocateBoneOffset`, `SkeletalMesh.cpp:5422` `GetComposedRefPoseMatrix`).
- 2절의 "레스트 포즈 깨짐" 버그가 정확히 어떤 Blender 버전/FBX 익스포터 버전에서
  재현되는지, 현재 프로젝트가 쓰는 Blender 버전에서도 재현되는지 미확인. 다만 0절 확정
  사항으로 이 가설이 없어도 증상이 완전히 설명되므로 우선순위는 낮아짐 — 다음 시도에서
  BoneName 매칭부터 확인해서 문제 없으면 그때 이 가설로 넘어갈 것.
- 사용자가 실제로 겪었던 시도에서 `WheelSetups[i].BoneName`에 정확히 어떤 문자열을
  입력했었는지, 그리고 실제 임포트된 스켈레톤의 본 이름이 무엇이었는지 — 이 둘을 대조할
  방법이 이제는 없음(그 프로젝트가 남아있지 않다면). 다음 시도에서는 **처음부터
  Skeleton Editor에서 본 이름을 복사해서 WheelSetups에 붙여넣는 방식**으로 이 문제
  자체를 원천 차단할 것 (3.2절 체크리스트 참고).
