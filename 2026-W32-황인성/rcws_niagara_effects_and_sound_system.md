# RCWS 이펙트 Niagara 전환 + 사운드 시스템(청취 포커스/엔진·프로펠러·발소리) 구현

> `titan_example` 프로젝트. RCWS 발사/피격 이펙트를 Niagara 전용으로 정리하고, 3개 시점
> (TitanTruck/UGV/UAV)을 오가며 운용하는 상황에 맞는 오디오 리스너 전환 시스템을 새로 설계,
> UGV 엔진음/UAV 프로펠러음/병력 발소리까지 MetaSound 레이어 크로스페이드 기반으로 구현.
> 이후 실사용 테스트에서 나온 버그(리스너 원거리 이동 시 무음, 회전 기준 오류, 컴포넌트
> 프로퍼티 미스매치) 3건도 트러블슈팅 섹션에 정리.

---

## 1. RCWS 발사/피격 이펙트 — Niagara 전용으로 정리

### 목적
`BP_UGV_Vehicle`의 `RCWSFireControl`(muzzle flash) / `BP_RCWSProjectile`(impact, enemy impact)
3곳 이펙트가 Cascade(`UParticleSystem`)와 Niagara를 동시에 받던 상태 — Niagara 하나만 받도록
정리.

### 변경 내용
- `URCWSFireControlComponent::MuzzleFlashEffect`(`UParticleSystem*`, Cascade용) 완전히 삭제,
  `MuzzleFlashNiagaraEffect`(`UNiagaraSystem*`) 하나만 유지 (`Fire()`에서 Cascade 스폰 호출도
  같이 제거).
- `ARCWSProjectile::ImpactEffect`/`EnemyImpactEffect` 타입을 `UParticleSystem*` →
  `UNiagaraSystem*`로 변경, `OnHit()`의 스폰 호출을 `UGameplayStatics::SpawnEmitterAtLocation`
  → `UNiagaraFunctionLibrary::SpawnSystemAtLocation`으로 교체.

### 주의
기존에 Cascade 파티클 시스템이 할당돼 있었다면(특히 Impact/EnemyImpact는 타입 자체가 바뀌었으므로)
에디터에서 블루프린트를 다시 열어 Niagara 에셋으로 재할당 필요.

**변경 파일**: `Vehicles/RCWSFireControlComponent.h/.cpp`, `Vehicles/RCWSProjectile.h/.cpp`

---

## 2. MetaSounds 호환성 확인

기존 `FireSound`/`ImpactSound`/`EnemyImpactSound`가 전부 `USoundBase*` 타입이라, `UMetaSoundSource`도
`USoundBase` 상속인 이상 **코드 수정 없이 MetaSound 에셋을 그대로 할당 가능**함을 확인. 이후 추가하는
모든 사운드 프로퍼티(엔진음/프로펠러음/발소리)도 전부 `USoundBase*`로 노출해 동일하게 호환.

동시 재생 개수 제한이 필요하면 `USoundConcurrency` 에셋(그룹별 Max Count + 우선순위 스틸링)을
쓰면 된다는 점도 확인 — 이번 구현 범위엔 포함 안 함(필요 시 후속 작업).

---

## 3. 오디오 청취 포커스 시스템 — 3개 시점 중 하나를 골라 "그 위치에서 듣기"

### 배경
이 프로젝트는 TitanTruck/UGV/UAV 3개 차량을 동시에 모니터링하는데, 실제로 셋은 물리적으로 떨어져
있음(UAV는 특히 수백m~km 단위로 비행). UGV RCWS 화면만 실제 프라이머리 렌더링(진짜 카메라)이고
TitanTruck/UAV는 씬캡쳐로 화면만 픽처-인-픽처로 보여주는 구조 — 하지만 셋 다 실제 3D 월드에 존재하는
액터라 오디오는 항상 리스너(귀) 위치 기준으로 계산됨.

요구사항: UAV 시점에서 들으면 UAV 프로펠러 소리가 크게, UGV 시점에서 들으면 UGV 엔진음이 기본이고
UAV가 머리 위를 지나갈 때 거리 기반으로 자연스럽게 커졌다 작아지는("슝") 식으로 — 즉 **리스너 자체를
선택한 차량 위치로 옮기는 것**이 정답(개별 사운드 on/off 뮤트가 아님).

### 기존 코드에 이미 있던 메커니즘 재사용
`Atitan_examplePlayerController::BeginPlay()`가 이미 `SetAudioListenerOverride(UGV->GetRootComponent(),
...)`로 리스너를 UGV에 한 번 고정해두고 있었음(발사/피격 사운드 거리감쇠가 "조작자가 UGV에 있다"는
전제로 계산되도록). 이 호출을 한 번만 하지 않고, 사용자가 청취 대상을 바꿀 때마다 다시 호출하도록
일반화.

### 구현
- `ECameraControlTarget`(기존에 조이스틱 조작 대상으로 쓰던 enum: Idle/TruckRCWS/UGVRCWS/UAVGimbal)을
  청취 대상 표현에도 재사용 — 단, **조작 대상(`CameraControlTarget`)과 완전히 독립적인 별도 상태**
  (`AudioListenerTarget`)로 분리(사용자 확정: UGV를 몰면서 UAV 소리만 듣는 것도 가능해야 함).
- `Atitan_examplePlayerController::SetAudioListenerTarget(ECameraControlTarget)` — 각 타겟의 실제
  액터를 찾아(`ResolveAudioListenerComponent`) `SetAudioListenerOverride`로 리스너를 옮김. `Idle`은
  `ClearAudioListenerOverride()`로 리스너 오버라이드 자체를 해제(전체 무음).
- `SetAudioListenerTargetByName(FString)` — 콘솔 진입점(`SetCameraControlTarget`과 동일한 파싱
  스타일). 콘솔 사용: `SetAudioListenerTargetByName UAV`.
- UGVRCWS 타겟 해석은 `FindUGVRCWS()`를 거쳐 `AUGVPawn`(네이티브)/`BP_UGVFromTank`(블루프린트) 둘 다
  커버 — 기존 BeginPlay 코드보다 더 일반화됨.

### UI — Monitor1Widget에 청취 포커스 버튼 3개
- 라디오 버튼처럼 하나만 활성화, 이미 켜진 버튼을 다시 누르면 꺼져서 전체 무음(사용자 요청).
- 소리/음소거 두 아이콘 전환은 `UCheckBox`(엔진이 이미 Checked/Unchecked 각각 다른 브러시를 지원)로
  구현 — 별도 위젯 없이 WBP에 `UCheckBox` 3개(`TruckAudioFocusCheckBox`/`UGVAudioFocusCheckBox`/
  `UAVAudioFocusCheckBox`) 배치하고 Style의 Checked/Unchecked Image만 지정하면 끝.
- `OnCheckStateChanged` 콜백 3개가 각각 `SetAudioListenerTargetFromUI()`를 호출 → 체크된 쪽으로 포커스
  이동, 이미 활성이던 버튼이 꺼진 경우(`bNewCheckedState==false`)는 `Idle`(무음)로.
- `RefreshAudioListenerButtons()`가 매 갱신 주기(`NativeTick`의 스로틀 루프)마다 실제 상태
  (`PC->GetAudioListenerTarget()`)로 세 체크박스를 재동기화 — 콘솔 명령으로 외부에서 바뀐 경우도 UI에
  반영됨. `UCheckBox::SetIsChecked()`는 `OnCheckStateChanged`를 재발화하지 않으므로 무한루프 걱정 없음.

**변경 파일**: `titan_examplePlayerController.h/.cpp`, `UI/Monitor1Widget.h/.cpp`

---

## 4. UGV 엔진음 — MetaSound RPM 크로스페이드

### 시행착오
처음엔 `AUGVPawn`(네이티브 UGV 클래스)에 엔진음 프로퍼티를 붙였는데, 실제로 레벨에서 굴러다니는
`BP_UGV_Vehicle`은 `AUGVPawn`이 아니라 **엔진 자체의 `AWheeledVehiclePawn`(Chaos Vehicles
플러그인)을 직접 상속**하는 블루프린트였음(`.uasset` 파일 문자열 검사로 확인 — "UGVPawn" 참조가
전혀 없고 "WheeledVehiclePawn"만 있음. 컨트롤러 코드의 2026-07-17 주석 "M1A2 클론에서 실제
디자인팀 UGV 메시(BP_UGV_Vehicle)로 전환"도 근거). `AUGVPawn` 쪽 프로퍼티는 죽은 코드였던 셈 —
그대로 남겨두고(혹시 그 네이티브 클래스가 다른 곳에서 쓰일 가능성 대비), 대신 **아무 Pawn에나
붙일 수 있는 독립 컴포넌트**로 다시 만듦.

### 사운드 방식 — 피치시프트 대신 MetaSound 레이어 크로스페이드
단순 `SetPitchMultiplier`로 루프 하나의 재생 속도만 바꾸는 건 배음 구조 전체가 그대로 밀려 올라가는
"다람쥐 목소리" 효과를 만들어 부자연스러움. 저/중/고 RPM 녹음을 각각 레이어링하고 그 사이를
볼륨 크로스페이드하는 게 표준 해법 — 이 블렌딩은 C++이 아니라 **MetaSound 그래프 안에서** 처리(7번
섹션 참고). C++은 정규화된 `[0,1]` 값 하나만 계산해서 `SetFloatParameter`로 MetaSound 입력
파라미터에 넘겨주는 역할만 함.

### `UVehicleEngineAudioComponent` (신규, `UAudioComponent` 상속)
- 컴포넌트 자신의 상속받은 `Sound` 프로퍼티에 MetaSound를 직접 할당(컴포넌트를 골라서 그 자체의
  Sound 필드에 넣는 것 — 별도 래퍼 프로퍼티 없음, 아래 9번 트러블슈팅에서 왜 이게 중요한지 설명).
  `bAutoActivate` 기본값(true)을 그대로 둬서 할당만 하면 자동 재생/루프.
- 매 틱 `SpeedParameterName`(기본 `"SpeedRatio"`) 파라미터에 0~1 비율을 `SetFloatParameter`로 전달.
- **비율 계산은 RPM 우선**: 오너 액터에서 `UChaosWheeledVehicleMovementComponent`를 찾아지면
  (`GetEngineRotationSpeed() / GetEngineMaxRotationSpeed()`, 실제 시뮬레이션된 RPM 대 레드라인)
  그걸 사용 — 같은 속도라도 기어에 따라 RPM이 완전히 다르고, 정차 중 아이들 RPM도 있어서 속도보다
  RPM이 진짜 엔진 사운드에 맞는 신호이기 때문. Chaos 차량이 아닌 오너는 기존처럼 속도 기반
  (`ReferenceSpeedKmh`)으로 자동 폴백.
- 거리감쇠: `bOverrideAttenuation`+`AttenuationOverrides`를 생성자에서 직접 세팅(풀볼륨 5m, 150m에서
  무음, `NaturalSound` 감쇠 커브 + Air Absorption으로 멀어질수록 고음 먹먹해짐).

**사용법**: `BP_UGV_Vehicle`에 Add Component → "Engine" 검색 → `Vehicle Engine Audio` 추가 →
그 컴포넌트의 `Sound`에 저/중/고 MetaSound 할당.

**변경/신규 파일**: `Vehicles/VehicleEngineAudioComponent.h/.cpp`(신규),
`Vehicles/UGVPawn.h/.cpp`(예전 접근 — 죽은 코드로 남아있음)

---

## 5. UAV 프로펠러음 — MetaSound 스핀비율 크로스페이드

UAV는 `BP_UAV`가 실제로 네이티브 `AUAVPawn`을 상속하는 것을 확인(`.uasset` 문자열에 "UAVPawn" 참조
있음 — UGV와 달리 이쪽은 네이티브 클래스가 맞았음), 그래서 `AUAVPawn`에 직접
`UAudioComponent* PropellerAudioComponent` 추가.

- UGV와 동일하게 MetaSound `SetFloatParameter`(`PropellerSpeedParameterName`, 기본 `"SpinRatio"`)
  방식으로 전환 — 저/고 RPM 레이어 크로스페이드.
- 비율은 이미 있던 `CurrentPropSpinRateDegPerSec`(ABP_UAV가 프로펠러 시각 회전에 쓰는 바로 그 값 —
  지상 대기 중엔 0, 이착륙/순항 중엔 `PropMaxSpinRateDegPerSec`까지 램프)을 재사용 — 별도 비행
  상태 분기 없이 지상에서는 자연히 무음.
- 거리감쇠: 풀볼륨 3m, 200m에서 무음(소형 드론 프로펠러 실측 청취 거리 기준), 나머지는 UGV와
  동일한 패턴.

**변경 파일**: `Vehicles/UAVPawn.h/.cpp`

---

## 6. 병력 발소리 — `UFootstepAudioComponent` (신규)

`BP_Ally_kadex`/`BP_Enemy_kadex`는 순수 블루프린트(`BP_ThirdPersonCharacter` 상속, 전투 로직은
`UAllyFormationComponent`가 리플렉션으로 건드리는 구조)라 네이티브 프로퍼티를 바로 못 붙임 — 같은
해법으로, 아무 Pawn/Character에나 붙일 수 있는 독립 `UActorComponent`로 구현.

### 두 가지 트리거 모드
- **타이머 근사치(기본, `bTriggerFromAnimNotify=false`)**: 매 틱 실제 이동 속도만 보고 일정 간격마다
  발소리 재생. 애니메이션 애셋 작업 없이 바로 동작하지만, 실제 발이 땅에 닿는 정확한 프레임과는
  안 맞을 수 있음(사용자 피드백으로 발견).
- **AnimNotify 기반(`bTriggerFromAnimNotify=true`)**: 신규 `UAnimNotify_Footstep`을 애니메이션의
  실제 발 딛는 프레임에 배치하면 그 순간 `PlayFootstepNow()`를 직접 호출 — 샘플 단위로 정확함.
  프로젝트 조사 결과 실제 로코모션 애니메이션(`AS_Walking`/`AS_Run_Forward`, `BP_Ally_kadex` →
  `BP_ThirdPersonCharacter` → `ABP_PlayerCharacter` → `BS_Movement` 블렌드스페이스 경유로 확인)엔
  노티파이가 하나도 없어서 직접 추가해야 함(에디터에서 타임라인 스크럽 후 Add Notify — 툴로 자동화는
  불가능해 수동 작업 필요). 프로젝트에 남아있던 `NiagaraExamples/FX_Footstep/AN_Footstep`은 Epic
  샘플 콘텐츠 잔재로 어디에도 안 쓰이는 별개 애셋(나이아가라 전용, 사운드 없음) — 혼동 주의.
- 두 모드 다 사운드 선택/거리감쇠 로직(`PlayFootstepSound`)을 공유해서 중복 구현 없음.

### 랜덤 배리에이션
`WalkFootstepSound`/`RunFootstepSound`(단일) → `WalkFootstepSounds`/`RunFootstepSounds`(배열)로
교체. 매 스텝 배열에서 랜덤으로 하나 선택하되, **직전에 재생한 것과 같은 걸 연속으로 고르지
않도록**(`PickRandomSound`) 처리 — 순수 균등 랜덤은 가끔 같은 소리가 연달아 나와 오히려 "규칙적으로
랜덤"인 티가 남.

**사용법**: 두 블루프린트에 Add Component → "Footstep" 검색 → `Footstep Audio Component` 추가 →
`Walk/Run Footstep Sounds` 배열에 각각 여러 개(2~4개) 할당. AnimNotify 모드로 전환하려면 위 두
애니메이션에 노티파이 배치 후 `Trigger From Anim Notify` 체크.

**신규 파일**: `Soldiers/FootstepAudioComponent.h/.cpp`, `Soldiers/AnimNotify_Footstep.h/.cpp`

---

## 7. MetaSound 레이어 크로스페이드 그래프 — 공용 구조

UGV/UAV 엔진음 둘 다 동일한 그래프 패턴(저/중/고 3레이어, UAV는 저/고 2레이어)으로 구성:

1. Wave Player 노드 N개(레이어별), 각각 Loop 켜기, 소스가 스테레오면 `Wave Player (Mono)` 사용
   권장(3D 포지셔널 사운드라 좌우 공간감은 리스너 거리/각도가 자동으로 만들어주므로 모노가 더
   단순하고 정확 — 최종 Output 포맷도 Mono로 생성).
2. Input 노드의 `On Play` 트리거 → 각 Wave Player의 `Play` 트리거로 팬아웃.
3. `Map Range (Float)` 노드로 구간별 gain 계산(예: 3레이어면 `low_gain`/`high_gain`을 각각 0~0.5,
   0.5~1 구간에서 Map Range로 뽑고 `mid_gain = 1 - low_gain - high_gain`).
4. 각 Wave Player 출력 × 해당 gain(`Multiply(Audio,Float)`) → `Add(Audio)`로 합산 → Output의
   `Out Mono`.
5. (선택) 같은 입력 파라미터를 `Map Range`로 ±2~4 semitone 정도의 작은 범위에 매핑해서 전체 Wave
   Player들의 `Pitch Shift` 입력에 공용으로 연결 — 레이어 크로스페이드 위에 살짝 연속적인 피치
   변화를 더해 더 자연스럽게 들림(±10 semitone처럼 큰 값은 다시 "다람쥐 목소리"가 되므로 지양).
6. Output의 `On Finished` 트리거는 연결 안 해도 무방(루핑 배경음이라 "끝나는 시점" 자체가 없음 —
   에디터가 띄우는 미연결 경고는 무시 가능).

---

## 8. 트러블슈팅 — 리스너가 멀리 갔다 오면 소리가 영구 무음

### 증상
청취 포커스를 UAV(멀리)로 옮겼다가 UGV로 복귀하면 UGV 엔진음이 꺼진 채로 안 돌아옴 — 반대 방향도
동일.

### 원인
언리얼 오디오 엔진은 **루핑 사운드가 들리는 범위를 벗어나면 자동으로 가상화(Virtualize)**해서
실제 렌더링을 멈추는 최적화가 있음(`au.VirtualLoops.*`, 거리 기반, 채널 수 압박과 무관하게 항상
동작). 다시 들리는 범위로 돌아왔을 때 어떻게 복귀할지는 `USoundBase::VirtualizationMode`
(Voice Management 카테고리)가 결정하는데, 기본값 `Restart`에서 MetaSound는 복귀 시 내부 그래프
상태(Wave Player 등)가 제대로 안 살아나는 경우가 있어 증상과 정확히 일치.

### 해결
`MS_UGVEngine`/`MS_UAVEngine` 두 MetaSound 에셋의 `Virtualization Mode`를 `Restart` →
`Play When Silent`(안 들려도 가상화 안 하고 계속 실제로 시뮬레이션 유지)로 변경. 언리얼 MCP 툴로
직접 두 에셋의 프로퍼티를 확인·수정·저장까지 완료.

---

## 9. 트러블슈팅 — 회전 기준이 차체(hull)라 좌우 방향이 안 맞음

### 증상
UGV/트럭 RCWS 터렛이나 UAV 짐벌이 차체와 독립적으로 좌우를 돌릴 수 있는데(예: 차체는 정면인데
터렛만 90도 돌아간 상태), 리스너가 차체 회전 기준으로 고정돼 있어서 화면에 보이는 방향과 소리의
좌우가 어긋남.

### 원인
`ResolveAudioListenerComponent()`가 리스너를 차량의 **루트 컴포넌트(차체)** 회전에 붙여놨었음.

### 해결
리스너를 차체가 아니라 **실제로 보고 있는 카메라 컴포넌트**에 붙이도록 변경:
- TruckRCWS/UGVRCWS → `URCWSComponent::GetSightCamera()`(조준경 시야 카메라, 팬/틸트로 실시간 회전)
- UAVGimbal → `AUAVPawn::GetGimbalCamera()`(짐벌 카메라, 자유 시점 회전)

`SetAudioListenerOverride`는 붙여둔 컴포넌트의 회전을 매 프레임 실시간으로 다시 읽으므로
(`APlayerController::GetAudioListenerPosition`, 엔진 소스로 확인), 한 번만 붙여두면 터렛/짐벌이
계속 돌아가는 동안에도 항상 "화면에 보이는 방향 = 소리의 정면"이 자동으로 유지됨. 카메라가 아직
준비 안 된 시점엔 안전하게 차체 루트로 폴백.

**변경 파일**: `titan_examplePlayerController.cpp` (`ResolveAudioListenerComponent`)

---

## 10. 트러블슈팅 — UAV 프로펠러 소리가 아예 안 남

### 증상
UGV 방식대로 `PropellerAudioComponent`를 선택해서 그 컴포넌트 자신의 `Sound`에 MetaSound를
할당했는데도 재생 안 됨.

### 원인
`AUAVPawn`에 `PropellerAudioComponent`(컴포넌트)와는 별개로 `PropellerSound`라는 **완전히 다른
프로퍼티**가 있었고, C++ 코드는 그 `PropellerSound`만 읽어서 `SetSound()`+`Play()`를 호출하도록
짜여 있었음(컴포넌트 자체는 `bAutoActivate(false)`로 꺼둔 채). 컴포넌트 자신의 `Sound`엔 할당해도
코드가 보는 별도 필드는 계속 비어있어서 재생이 트리거되지 않았던 것 — UGV(`VehicleEngineAudioComponent`)는
처음부터 컴포넌트 자체가 `Sound`를 갖는 구조라 문제없었는데, UAV만 예전 방식이 남아있었음.

### 해결
UAV도 UGV와 동일한 구조로 통일: 별도 `PropellerSound` 프로퍼티 삭제, `bAutoActivate(false)` 제거
(기본값 true로 자동 재생), 코드가 `PropellerAudioComponent->Sound`(컴포넌트 자신의 값)를 직접
읽도록 변경.

**교훈**: 오디오 컴포넌트를 감싸는 새 프로퍼티를 만들 땐, 사용자가 "컴포넌트 자체의 Sound 필드"에
할당하는 직관적인 워크플로우와 실제로 코드가 읽는 필드가 반드시 일치해야 함 — 두 채널로 나뉘면
말없이 무음이 됨.

**변경 파일**: `Vehicles/UAVPawn.h/.cpp`

---

## 종합 — 사용자가 에디터에서 할 일

| 항목 | 위치 | 할 일 |
|---|---|---|
| Muzzle/Impact/EnemyImpact | `BP_UGV_Vehicle`/`BP_RCWSProjectile` | Niagara 에셋 재할당(타입 바뀜) |
| 청취 포커스 버튼 | `WBP_kadex`(Monitor1Widget) | `UCheckBox` 3개 배치 + Checked/Unchecked 아이콘 지정 |
| UGV 엔진음 | `BP_UGV_Vehicle` | `Vehicle Engine Audio` 컴포넌트 추가 → `Sound`에 MetaSound 할당 |
| UAV 프로펠러음 | `BP_UAV` | `PropellerAudioComponent`의 `Sound`에 MetaSound 할당 |
| 병력 발소리 | `BP_Ally_kadex`/`BP_Enemy_kadex` | `Footstep Audio Component` 추가 + Walk/Run 사운드 배열 할당 |
| (선택) 발소리 프레임 동기화 | `AS_Walking`/`AS_Run_Forward` | `UAnimNotify_Footstep` 배치 + `Trigger From Anim Notify` 체크 |
| MetaSound 가상화 설정 | `MS_UGVEngine`/`MS_UAVEngine` | 완료(Play When Silent로 이미 수정/저장함) |

모든 사운드 프로퍼티가 `USoundBase*`라 Sound Cue든 MetaSound든 그대로 동작.
