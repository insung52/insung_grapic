# 동적 바람 시스템(AWindSource) 구현 기록 (2026-08-29)

## 요약

- **목적**: 레벨 전역에서 나무/풀/Niagara 이펙트/드론 물리가 하나의 바람 값에 일관되게 반응하도록 `AWindSource` 액터를 신규 구현.
- **핵심 설계**: 액터 하나가 Perlin 노이즈로 방향·세기를 천천히 계산해서, 서로 다른 4곳(자작나무 MPC, RealBiomes MPC, 태그 붙은 Niagara 컴포넌트, 드론 물리 정적 조회)에 매 틱 밀어 넣는다.
- **큰 삽질 하나**: RCWS/UGV VFX(총열 연기, 피격 화염/먼지)에 바람을 연동하다가, Niagara의 `System.WindDirection` 계열 변수가 엔진이 자동으로 채워주는 값이 아니라 완전히 별개의 정적 애셋(`NPC_NiagaraExamples`)에서 온다는 걸 뒤늦게 발견 — 처음엔 "연동됐다"고 착각한 상태로 몇 턴을 보냈다. 최종적으로는 우리 자체 태그+`WindVectorCms` 경로로 전부 통일함.
- **현재 상태**: 식생(자작나무/RealBiomes) + Niagara 이펙트 8종(`NS_FallingLeaves`, `NS_AmbientDust`, `NS_Wind`, `NS_BarrelSmoke`, `NS_Fire_Small_Smoke` 4개 이미터, RCWS 임팩트 5종) 전부 연동 완료. 드론 물리는 별도 연동(`DronePawn.cpp`) 완료.
- **남은 일**: 낙엽/먼지 파티클을 카메라(또는 현재 조종 폰) 추적형으로 바꾸는 작업(설계만 논의, 미구현) — 아래 "다음 작업" 참고.

---

## 아키텍처 — 3가지 연동 방식

`AWindSource`(`Source/titan_example/Environment/WindSource.h/.cpp`)는 `AWindDirectionalSource`를 상속하지만, 그 네이티브 클래스 자체는 "SpeedTree만 반응"이라 이 프로젝트 소비처 중 그걸 직접 읽는 곳은 없다. 상속하는 이유는 Strength/Speed/Direction 프로퍼티와 디테일 패널 아이콘을 공짜로 얻기 위함일 뿐, 실제 값 전달은 아래 세 경로를 자체 구현했다.

### ① MPC(Material Parameter Collection) 직접 푸시 — 식생 머티리얼
- 자작나무: `MPC_BHF_Controller` (`MW_WindDirection`/`MW_WindSpeed`/`MW_WindIntensity`)
- RealBiomes 전체(소나무/마운틴애시/고사리 등): `MPC_Wind` (`Wind Direction`/`Wind Speed`/`Gust LF·HF Influence/Strength`)
- `AWindSource::PushToMaterialCollections()`가 매 틱 `UKismetMaterialLibrary::SetScalarParameterValue`/`SetVectorParameterValue`로 직접 씀. 액터/컴포넌트 태그 개념이 없음 — 전역 MPC라 레벨에 뭘 배치하든 자동으로 먹는다.

### ② 컴포넌트 `"Wind"` 태그 + `User.WindVectorCms` — Niagara 이펙트 (표준 경로)
- `AWindSource::RescanNiagaraTargets()`가 `NiagaraRescanIntervalSeconds`(기본 1초)마다 월드를 스캔해서 컴포넌트 태그 `"Wind"`가 붙은 `UNiagaraComponent`를 캐싱
- `PushToNiagaraTargets()`가 매 틱 캐싱된 컴포넌트들에 `SetVectorParameter("WindVectorCms", ...)`
- 각 Niagara System은 `WindForce` 모듈의 `Wind Speed` 입력을 `User.WindVectorCms`(Vector3f, 시스템에 직접 추가해야 함)에 링크해야 함
- **새 이펙트를 바람에 반응시키는 절차** (코드 수정 불필요):
  1. 해당 Niagara System에 User Vector 파라미터 `WindVectorCms` 추가 (에디터에서 직접 — MCP로 새 User Parameter를 만들면 크래시 위험이 있어 이후엔 `NiagaraToolset_System.AddUserVariables`로 안전하게 확인 후 사용)
  2. `WindForce` 모듈(없으면 추가) → `Wind Speed` 입력을 그 파라미터에 링크
  3. 그 이펙트를 스폰하는 `UNiagaraComponent`에 컴포넌트 태그 `"Wind"`만 붙이면 끝

### ③ (초기 오판, 최종적으로 폐기) `NPC_NiagaraExamples` 정적값
- RCWS 임팩트류(`NS_RCWS_Dirt/Glass/Hard/Metal/Wood`, `NS_ImpactFire`)는 원래부터 `WindForce` 모듈이 있었고 `Wind Speed`가 `System.WindDirection`에 링크돼 있어서 "이미 연동된 줄" 착각했음.
- 실제로는 `System.WindDirection`/`WindStrength`/`WindTurbulenceScale`/`WindTurbulenceFrequency`가 엔진 자동 바인딩이 아니라, System 레벨 Set Parameters 모듈이 **`/Game/NiagaraExamples/NPC_NiagaraExamples`**(Epic 예제 콘텐츠, Niagara Parameter Collection)에서 끌어오는 정적값이었다. 이 NPC를 매 틱 써주는 Blueprint/액터가 프로젝트에 전혀 없어서 사실상 고정값 — `AWindSource`와 완전 무관.
- `NS_BarrelSmoke`/`NS_Fire_Small_Smoke`는 애초에 이 System-level Set Parameters 모듈 자체가 없어서 컴파일도 안 됐음(`Transient.FirstFrame`류 에러) — 처음엔 이 NPC 라우팅을 그대로 복제해서 임시로 컴파일만 통과시켰다가, 곧바로 "이거 실제로 안 움직인다"는 걸 깨닫고 ②번 방식으로 재작업(아래 "RCWS/UGV VFX 통합" 참고).

---

## `AWindSource` 프로퍼티 (2026-08-29 최종)

| 프로퍼티 | 기본값 | 설명 |
|---|---|---|
| `BaseSpeedMS` | 4.0 | 베이스 풍속 (m/s) |
| `GustAmplitudeMS` | 3.0 | 돌풍 최대 편차 (m/s) |
| `GustPeriodSeconds` | 6.0 | 돌풍 노이즈 주기 |
| `BaseWindDirectionDegrees` | 0.0 | 배회 기준 방위(월드 Yaw, 0=+X). 액터 자체 회전과 무관하게 디테일 패널에서 직접 조절 가능(원래는 액터 배치 회전을 그대로 썼는데 불편해서 프로퍼티로 분리) |
| `DirectionWanderDegrees` | 45.0 | 기준 방위 ±범위 |
| `DirectionChangePeriodSeconds` | 20.0 | 방향 노이즈 주기 (돌풍 주기와 배수 관계 아니게 일부러 다르게 잡음) |
| `BirchWindCollection` / `RealBiomesWindCollection` | `MPC_BHF_Controller` / `MPC_Wind` | 소비처 MPC 소프트 참조 |
| `RealBiomesBakedGustSuppression` | 0.5 | RealBiomes 셰이더에 원래 있던 베이크된 돌풍 텍스처 스크롤의 억제 강도(0=원본, 1=완전억제). 완전 억제(불리언 on/off)하면 소나무가 "전체가 한 덩어리로 진동"하는 부작용이 있어서 슬라이더로 바꿈(카드형 지오메트리라 정점 위치만으로 자연 분산이 안 나옴, 아래 "소나무" 참고) |
| `NiagaraWindComponentTag` | `"Wind"` | 이 태그 붙은 `UNiagaraComponent`만 `WindVectorCms` 수신 |
| `NiagaraRescanIntervalSeconds` | 1.0 | Niagara 대상 재스캔 주기 |
| `MaterialWindSpeedScale` | 0.25 | 드론용 실제 m/s를 셰이더/Niagara "다이얼" 단위로 줄이는 배율. 각 소비처가 자체 배율(RealBiomes Wind Speed 원래 기본값 1, Niagara WindForce의 Wind Speed Scale 등)을 이미 갖고 있어서, 실제 물리 cm/s를 그대로 넣으면 이중 증폭됨 |

정적 조회 함수:
- `GetWindVelocityMS(WorldContextObject)` — 실제 물리 m/s (드론 등 커스텀 물리용)
- `GetWindVectorCmsForNiagara(WorldContextObject)` — `PushToNiagaraTargets`와 정확히 같은 배율(×`MaterialWindSpeedScale`×100)로 변환된 cm/s. 태그 재스캔 주기를 못 받는 즉발성 이펙트가 스폰 시점에 한 번 직접 가져다 쓰는 용도

---

## 식생 튜닝 내역

### 자작나무(`MTL_BHF_BirchLeaves`/`Tiny`) — 잎 떨림 원인 규명
잎만 유독 심하게 떨리는데 `MW_WindWorldScale`(텍스처 공간 타일링 크기)을 128→384로 올려도 전혀 변화가 없었음. `MF_MW_Wind` 함수 그래프를 끝까지 추적해서 진짜 원인을 찾음:
- 최종 출력 = `MF_MW_WindLowAmp`(트렁크와 공유, 정상) + `LinearInterpolate(..., Alpha = VertexColor × 거리기반감쇠)` — 잎처럼 트렁크에서 먼 정점일수록 이 디테일 항이 지배적
- 그 안에 **`MW_WindInitialIntensity`**(Vector, R/G=수평, B=수직)라는 **잎 전용(트렁크엔 없는) 머티리얼 인스턴스 오버라이드 파라미터**가 곱해져 있었음
- 적용: `MTL_BHF_BirchLeaves` (0.25,0.25,1.0)→(0.0625,0.0625,0.25), `MTL_BHF_BirchLeavesTiny` (0.2,0.2,0.2)→(0.05,0.05,0.05) — 기존 R:G:B 비율 유지하며 4배 감산

### 소나무(`SM_Scots_Pine_Forest_02`) — 5배 감산 + 트렁크/잎 통일
- 처음엔 트렁크만 5배 낮췄더니 잎/서브줄기가 트렁크에서 "떨어져서" 따로 흔들리는 것처럼 보임 → 트렁크와 잎이 완전히 독립된 머티리얼 함수(정점 계층 연동 없음)라 진단, 잎에도 동일 배율 적용
- `MI_Scots_Pine_Trunks_01`, `MI_Pine_Ground_Roots_01`: Branch H/V Amp, Detail Amp, Wind Sway Amount 전부 ÷5
- `MI_Scots_Pine_Bark_01`(실제 껍질 표면 — 슬롯명이 "sheet"인데 반대로 되어 있음 주의): 동일 ÷5, 별도의 "Use Wind" 스위치가 꺼져 있던 것도 발견해서 켬
- `MI_Scots_Pine_Sheet_01`(잎/침엽 — 슬롯명 "bark"), `MI_Scots_Pine_Xtree_Sheet_02`(임포스터 카드): 동일 ÷5
- 벤더의 베이크된 돌풍 텍스처를 (구버전에서) 완전히 껐을 때 "카드형 지오메트리 특성상 캐노피 전체가 한 덩어리로 진동"하는 부작용 발견 → `RealBiomesBakedGustSuppression`을 불리언에서 0~1 슬라이더로 재설계(위 프로퍼티 표 참고)

### Niagara 낙엽/먼지 (`NS_FallingLeaves`, `NS_AmbientDust`)
- `NS_FallingLeaves`: Wind Speed Scale 300→60→**30** (최종)
- `NS_AmbientDust`(advanced WindForce, Turbulence/Friction/Ground Mask 있는 버전): Wind Speed 로컬값(100,0,0)→`User.WindVectorCms` 링크로 교체, Wind Speed Scale 1→**2**(2배 요청)
- `NS_Wind`(DustMotes+Smoke 이미터): Wind Speed를 `User.WindVectorCms`에 링크(배율은 별도 조정 안 함)

---

## RCWS/UGV VFX 통합 (③→② 방식 전환)

### 대상과 최종 배선
| 시스템:이미터 | 실제 사용처 | Wind Speed Scale (최종, 사용자 직접 조정됨) |
|---|---|---|
| `NS_BarrelSmoke:Smoke` | `BP_UGV_Vehicle`/`_new`(총열 과열 연기, 실사용) + 테스트 레벨 | 6 |
| `NS_Fire_Small_Smoke:NE_Smokes_02` | `BP_RCWSProjectile`(피격 화재 연기, `ImpactFireEffect` 프로퍼티, 풀링됨) | 30 |
| `NS_Fire_Small_Smoke:NE_Ashes` | 〃 | 20 |
| `NS_Fire_Small_Smoke:NE_Flame_01`/`NE_Flame_02` | 〃 | 1 (화염은 세게 넣으면 옆으로 날아가는 것처럼 보여서 낮게) |
| `NS_RCWS_Dirt/Glass/Hard/Metal/Wood:GroundDust` | `BP_RCWSProjectile`(피격 임팩트, 즉발성 `bAutoDestroy=true`) | 1 (초기값, 미세조정 안 함) |

모두 `Wind Speed → User.WindVectorCms` 링크, `Wind Speed Scale`은 단순 스칼라(랜덤레인지 아닌 고정값). `NS_ImpactFire`는 코드/블루프린트 어디서도 참조되지 않는 미사용 애셋으로 확인되어 손대지 않음.

### WindForce 모듈 추가 시 겪은 문제들 (교훈)

1. **`System.WindStrength`/`WindDirection`류는 엔진 자동 바인딩이 아니다** — 위 "아키텍처 ③" 참고. `WindForce`를 새로 넣을 땐 반드시 `Wind Speed`를 `User.WindVectorCms`에 직접 링크해야 하고, 이 User Parameter가 없으면 먼저 추가해야 한다(`AddUserVariables`, MCP로 안전).

2. **`WindForce`는 `ParticleState`보다 뒤, `SolveForcesAndVelocity`보다 앞에 있어야 한다** — `ParticleState`가 초기화하는 `Transient.FirstFrame`을 `WindForce`가 읽는데, 먼저 안 오면 컴파일 자체가 깨진다(`Variable Transient.FirstFrame was read before being set`). 반대로 `SolveForcesAndVelocity`보다 뒤에 있으면 컴파일은 되지만 **그 프레임에 계산한 힘이 전혀 반영 안 되는 실질적 무동작 상태**가 된다(Niagara `GetStackIssues`가 "unmet post-dependency: SolveForcesAndVelocity"로 감지는 해주지만 dismissible이라 컴파일은 통과해버림 — 눈으로 반응 확인하기 전엔 놓치기 쉽다).

3. **`WindForce`는 `Drag`(또는 `Aerodynamic Drag`) 모듈이 반드시 필요하다** — 없으면 hard 의존성 에러. `Drag`는 `WindForce`와 `SolveForcesAndVelocity` 사이에 위치해야 함.

4. **검증된 최종 순서**: `ParticleState → WindForce → Drag → SolveForcesAndVelocity → (Color/DynamicMaterialParameters 등 렌더링용 모듈)`. `GroundDust`/`ImpactFire`(벤더가 원래 이 순서로 만들어둠)를 정답 템플릿으로 참고했다.

5. **상속(Inherited) 이미터의 함정** — `NS_Fire_Small_Smoke`의 4개 이미터는 부모 템플릿에서 `ParticleState`/`SolveForcesAndVelocity`가 **`Solve → ParticleState` 순서로 고정 상속**돼 있어서, `WindForce`가 요구하는 두 조건("ParticleState 뒤" AND "Solve 앞")을 동시에 만족하는 자리가 물리적으로 없었다. Niagara의 `ApplyStackIssueFix`(공식 자동수정)로 "Solve 앞으로 이동"을 적용해봐도 즉시 `ParticleState` 관련 컴파일 에러로 재발 — 상속을 그대로 둔 채로는 도구로 우회할 방법이 없었다. **최종 해결: 4개 이미터 전부 상속을 끊고(Break Inheritance)** `ParticleState`/`SolveForcesAndVelocity`를 로컬 모듈로 만든 뒤 수동으로 위 4번 순서에 맞게 재배치.

### C++ 변경사항

**`Source/titan_example/Environment/WindSource.h/.cpp`**
- `BaseWindDirectionDegrees` 프로퍼티 추가 (기존엔 액터 배치 회전을 그대로 기준 방향으로 썼음 — 디테일 패널에서 직접 조절 가능하게 분리)
- `RealBiomesBakedGustSuppression`을 불리언→0~1 float로 변경, 조건부(`if (>0)`) 적용 로직을 무조건 매 틱 적용으로 수정(슬라이더를 0으로 내려도 이전 값이 안 남게)
- `GetWindVectorCmsForNiagara(WorldContextObject)` 정적 함수 신규 추가 — 태그 재스캔을 못 받는 즉발성 이펙트용

**`Source/titan_example/Vehicles/RCWSProjectile.cpp`**
- `#include "Environment/WindSource.h"` 추가
- `TrySpreadFire()`(풀링된 화염, `ImpactFireEffect`=`NS_Fire_Small_Smoke`): 최초 스폰 시 `FireComponent->ComponentTags.AddUnique(FName("Wind"))`로 자동 태그 — 풀링되어 오래 사는 컴포넌트라 태그 기반 재스캔이 통함
- `ReportHitToInstigator()`(RCWS 5종 임팩트, `bAutoDestroy=true` 즉발성): `Component->SetVectorParameter(FName("WindVectorCms"), AWindSource::GetWindVectorCmsForNiagara(World))`를 스폰 직후 1회 직접 주입 — 수명이 너무 짧아 태그 재스캔 주기를 못 받을 수 있어서

**빌드 필요**: 이 두 파일 수정 후 사용자가 직접 빌드해야 반영됨(이 세션에서 빌드는 안 함).

### MCP 도구 한계 — Blueprint SCS 컴포넌트 태그
`BP_UGV_Vehicle`/`_new`의 실제 `BarrelSmokeFX` 컴포넌트(SCS 템플릿)에 `"Wind"` 태그를 붙이려 했으나, `ObjectTools.set_properties`로 값을 바꿔도 **패키지가 dirty로 표시되지 않아 저장이 전혀 안 되는** MCP 도구 한계를 발견함(`compile_blueprint` 호출해도 dirty 안 됨). 레벨에 배치된 액터 인스턴스는 이 문제가 없어서 정상 저장됨 — SCS 템플릿 전용 문제로 추정.
- **해결 안 됨 — 사용자가 직접 처리 필요**: `BP_UGV_Vehicle`(및 `_new`) 열기 → Components 패널 `BarrelSmokeFX` 선택 → Details → Tags 배열에 `Wind` 추가 → 컴파일+저장

### 크래시 이후 데이터 유실 이슈
작업 중 에디터가 한 번 예기치 않게 종료됐는데, 그 직전 `save_assets`가 `true`를 반환했음에도 실제로는 레벨 액터 컴포넌트 태그 변경이 디스크에 반영되지 않았던 사례가 있었음(재저장 후 파일 수정시각으로 재확인함). **MCP `save_assets`의 `true` 반환을 곧이곧대로 믿지 말고, 특히 크래시 전후엔 파일 mtime이나 재읽기로 실제 반영 여부를 다시 확인할 것.**

---

## 성능/설계 관련 미해결 논의 — 다음 작업

`NS_FallingLeaves`/`NS_AmbientDust` 현황 확인 중 나온 이슈:
- 두 시스템 다 `Shape Location` 모듈의 `Shape Origin`이 `StackContext.Position`(=Niagara 액터 자신의 고정 배치 위치)에 묶여 있어, 카메라/플레이어를 따라다니지 않고 **배치된 자리 기준 고정 반경**(FallingLeaves 3000cm/30m, AmbientDust 200cm/2m)에서만 스폰됨. 지금은 레벨 전체를 덮고 있지 않음.
- Niagara는 화면 밖/원거리라고 자동으로 시뮬레이션을 스킵해주지 않는다(명시적 Scalability/LOD 컬링 없이는). 넓은 숲 레벨에 이 스폰 범위를 그대로 깔면 낭비.
- UGV/UAV 등 개별 차량에 붙이는 방식은 "먼지가 차량을 졸졸 따라다니는" 부자연스러운 결과가 나오고 차량마다 중복 관리해야 해서 비권장.
- **권장 방향(합의만 됨, 미구현)**: 카메라(또는 현재 조종 중인 폰) 위치를 매 틱 따라가는 앵커 하나로 통일 — UGV/드론/도보 상관없이 "지금 보고 있는 곳 근처"에만 스폰되고, 시스템은 하나만 유지. 작은 Blueprint/C++로 카메라 위치를 Niagara 액터에 매 틱 반영하는 정도로 구현 가능할 것으로 예상.

관련 문서: [[new_kadex_0811_forest_perf]] (PCG 식생 WPO 성능 문제, 이 바람 작업과는 별개 이슈지만 같은 나무 에셋들을 다룸)
