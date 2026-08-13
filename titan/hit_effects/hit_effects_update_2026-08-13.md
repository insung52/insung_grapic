# 피격 이펙트 시스템 — 후속 작업 정리 (2026-08-13)

`hit_effects_idea.md`(초기 기획)/`hit_effects_implementation.md`(1차 구현+버그 트러블슈팅)는 기록용으로 그대로 두고, 그 이후 진행한 작업(도탄, 혈흔/화염 VFX, 사운드 연결·어테뉴에이션, 오디오 채널 고갈 버그 수정, 총알 휘바람 소리, UGV/TitanTruck 차량 피격 재질 판정)을 새로 정리한 문서. 시간순.

---

## 1. 도탄(Ricochet) 시스템

### 반사 판정 로직 (`ARCWSProjectile::OnHit`)
```
GrazingFactor   = 1 - |dot(ImpactDirection, EffectNormal)|         // 0=수직, 1=평행
RicochetRandom  = FMath::FRandRange(RicochetRandomFactorMin, Max)  // 기본 0.3~1.0
ReflectedSpeed  = OldSpeed * GrazingFactor * SurfaceSet->RicochetAbsorptionRatio * RicochetRandom
성공 조건       = ReflectedSpeed >= MaxRicochetReferenceSpeedCmS * MinRicochetSpeedRatio
                  && RicochetBounceCount < MaxRicochetBounces
ReflectedDir    = ImpactDirection - 2*dot(ImpactDirection, EffectNormal)*EffectNormal  (표준 반사 공식)
```

- **재질별 확률을 따로 안 둠**: 재질(흡수율)·각도(그레이징)는 이미 반사 속도 공식에 녹아있으므로, 그 위에 다시 별도 확률 레이어를 얹지 않고 **반사속도 계산 자체에 0.3~1.0 난수를 곱하는 방식**으로 매번 다른 결과가 나오게 함(사용자 제안, 최초 설계보다 채택). 방향 흔들림(VRandCone 스캐터)은 이번엔 명시적으로 미적용.
- 이펙트 크기: 도탄 성공 시 `SpeedLostFraction = (OldSpeed-ReflectedSpeed)/MaxRicochetReferenceSpeedCmS`를 `RicochetEffectScaleMin`(기본 0.3)~1.0 사이로 Lerp해서 나이아가라 스폰 스케일에 반영(데칼 크기는 그대로). 도탄 실패(일반 명중)는 항상 1.0.
- 도탄 사운드: `FImpactSurfaceEffectSet::RicochetSound`(재질별 지정 가능, 현재는 전부 `MS_Ricochet` 공용) — 우선순위상 재질별 Sound/EnemyImpactSound보다 위.
- 무한 도탄 방지: `MaxRicochetBounces`(기본 3).
- 스폰 위치: 반사면 노말 방향으로 `RicochetSpawnOffsetCm`(기본 15cm)만큼 띄워서 재충돌 방지.

### 신규 프로퍼티 (`RCWSProjectile.h`)
- `FImpactSurfaceEffectSet`: `RicochetAbsorptionRatio`, `RicochetSound`
- `ARCWSProjectile`: `MaxRicochetReferenceSpeedCmS`, `MinRicochetSpeedRatio`, `RicochetEffectScaleMin`, `RicochetSpawnOffsetCm`, `MaxRicochetBounces`, `RicochetRandomFactorMin/Max`

### 값 세팅 (BP_RCWSProjectile / BP_RifleProjectile, MCP로 CDO 편집)
- `RicochetAbsorptionRatio`: Metal 0.8 / Hard 0.7 / Wood 0.3 / Dirt 0.2 / Glass 0.1
- `MaxRicochetReferenceSpeedCmS`: RCWS = 70000 (실제 탄속 850m/s → `SceneMuzzleVelocityCmS()`의 씬 스케일 보정 ≈1.21 적용해서 역산). **Rifle = 70000은 미검증 placeholder** — 소총 실제 탄속을 C++/`BP_Ally_kadex` 이벤트그래프 어디서도 못 찾음(소총 발사는 전부 블루프린트 이벤트 기반). 나중에 실제 값 확인되면 재조정 필요.

### 멀티플레이 설계
- RNG(`FMath::FRandRange`)는 `OnHit`의 서버 권위(`HasAuthority()`) 분기 안에서만 실행 — 클라이언트는 재계산 안 하고 서버가 확정한 결과(위치/속도)만 받아서 재생.
- `ARCWSProjectile`은 `bReplicates=false`라 직접 `NetMulticast` 선언 불가 → 기존 `Multicast_PlayImpactEffect`와 동일하게, 쏜 주체(RCWS 차량/아군/적군)의 컴포넌트를 거쳐 `Multicast_LaunchRicochet` 호출.
- 도탄 자식 투사체는 **풀에 편입 안 하고 독립적으로 `SpawnActor`** — 기존 코드 주석("`Multicast_PlayImpactEffect`의 위치기반 설계가 풀 인덱스 동기화보다 더 견고")과 같은 철학.
- 아군/적군 컴포넌트는 발사 자체가 블루프린트 이벤트(`FireAtEnemy`) 기반이라 C++ `ProjectileClass` 필드가 없음 → `TSubclassOf<ARCWSProjectile>`를 원본 투사체의 `GetClass()`에서 뽑아 파라미터로 명시적으로 넘김(3개 컴포넌트 공통).

### 수정 파일
`RCWSProjectile.h/.cpp`, `RCWSFireControlComponent.h/.cpp`, `AllyFormationComponent.h/.cpp`, `EnemyCombatComponent.h/.cpp`

---

## 2. VFX 추가

### 혈흔 (`/Game/VFX/Blood`)
- `NS_Blood_Splat` — `NS_Rifle_Metal` 복제. `Sparks`→핏방울(BigDroplet), `SecondarySparks`→미세비산(FineMist), 머티리얼 `M_sangue`(반투명 데칼 불필요, 스프라이트로 직접 사용 가능), 색상 다크레드로 Direct-Set, 크기/수명 튜닝(Sparks 2~6cm/1.5~2.5s, SecondarySparks 0.15~0.35s), Restitution 0.05(덜 튕기게). `BP_RifleProjectile.EnemyImpactEffect`에 할당.
- `NS_Blood_Splat_RCWS` — 위 걸 복제 + `Explosion` 이미터 추가(`NE_Explosion` 기반, 머티리얼 `MI_ExplosionRoil_8x8`), "약하게" 튜닝(Spawn Count 15, 크기 40~80cm, 수명 1~1.5s). `BP_RCWSProjectile.EnemyImpactEffect`에 할당.

### 나무 화염 (`NS_RCWS_Wood`)
- `Fire` 이미터 신규 추가(`NE_GroundDust` 기반). **머티리얼 버그 발견/수정**: 처음 쓴 `MI_FireRoil_8x8`이 이름과 달리 스모크와 같은 `M_SmokeAndFire_Sprites` 마스터 머티리얼(구름 형태 텍스처)이라 색만 바꿔선 불처럼 안 보였음 → 셰이더 그래프 추적(`MaterialTools.get_property_input`/`get_expression_inputs`) 끝에 `NS_Fire_01`이 실제로 쓰는 `M_Fire_01` + `T_Flame_01`로 교체, 파티클 Color는 흰색으로 리셋(텍스처가 이미 색을 가짐).
- 최종 튜닝: 크기 60~150cm(초기 대비 3배), 수명 5~10초, `WindForce` 모듈 비활성화(바람에 밀려다니던 것 제거).

### 파티클 성능 튜닝 (RCWS 5개 재질 시스템 공통)
연사 시 렉 문제로: Debris 개수 1/5배, SparkDebris 1/3배, GroundDust 개수 40개 고정.

---

## 3. SFX 연결 및 어테뉴에이션

### MetaSound 연결 (`/Game/SFX/MetaSounds/`)
`BP_RCWSProjectile`/`BP_RifleProjectile`의 `SurfaceImpactEffects[].Sound`, `RicochetSound`, `EnemyImpactSound`에 이름 매칭으로 연결:
- 재질별: `MS_hit_{rifle,rcws}_{wood,hard,dirt,metal,glass}`
- 적 피격: `MS_hit_{rifle,rcws}_enemy`
- 도탄: `MS_Ricochet` (양쪽 무기, 5개 재질 전부 공용 1개)

### 사운드 어테뉴에이션 재조정
기존 값이 심하게 어긋나 있던 걸 발견해서 재설정(`ImpactSoundAttenuationRadiusCm`/`ImpactSoundFalloffDistanceCm`):
- **RCWS**: 10cm/150cm(1.6m 밖이면 안 들림) → **1500cm/25000cm**(약 265m까지, "폭발음답게 멀리 퍼지도록")
- **Rifle**: 1000cm/150000cm(1.5km까지 들리던 과도한 값) → **300cm/3000cm**(약 33m, 소화기다운 범위)

---

## 4. 오디오 채널 고갈 버그 — UGV 엔진/UAV 드론 루프 소리가 연사 중 끊김

### 증상 및 원인
연사(RCWS 최대 1200rpm) 시 UGV 엔진 소리(그리고 UAV 프로펠러 소리)가 끊기는 문제. 원인:
- `/Game/Vehicles/UGV/sounds/UGV_Gunshot`(발사음, 매 발마다 스폰)이 자체 concurrency 제한이 전혀 없고, `Priority=1`(기본값)로 다른 모든 소리와 동률.
- 엔진 루프 `MS_UGVEngine`/`MS_UAVEngine`도 똑같이 `Priority=1`, concurrency 제한 없음, `VirtualizationMode=PlayWhenSilent`.
- 전역 채널 한도(프로젝트 커스텀 설정 없음, 엔진 기본 Max Channels)를 발사음이 순식간에 채우면, 우선순위 동률인 엔진 루프가 voice-stealing으로 정지될 수 있음. UAV도 같은 전역 채널 풀을 공유해서 같이 영향받음.

### 적용한 수정
1. **에셋 레벨(리빌드 불필요)**: `MS_UGVEngine`, `MS_UAVEngine` 둘 다 `Priority` 1→90, `bBypassVolumeScaleForPriority=true`로 설정 — 채널 경합 시 이 루프들이 (현재 소리가 작더라도) 항상 마지막까지 살아남도록.
2. **C++ 셀프힐(리빌드 필요)**: 두 루프 다 "한 번 시작되면 절대 끊기면 안 되는 지속 루프"라서, 우선순위만으로는 100% 보장이 안 됨 → 매 틱 `IsPlaying()`을 체크해서 꺼져있으면 즉시 `Play()`로 재시작.
   - `VehicleEngineAudioComponent::TickComponent` (Source/titan_example/Vehicles/VehicleEngineAudioComponent.cpp)
   - `AUAVPawn::UpdatePropellerAudio` (Source/titan_example/Vehicles/UAVPawn.cpp)

발사/피격/도탄/발소리 등 나머지 사운드는 사용자 판단으로 이번엔 손 안 댐(엔진/드론 루프처럼 "절대 끊기면 안 되는" 소리가 아니라서).

---

## 5. 총알 휘바람(Whiz-by) 소리

### 방식
언리얼이 도플러를 자동으로 안 해줌(발사 즉시 사라지는 fire-and-forget 사운드엔 애초에 적용 대상이 아님). 실제 슈팅 게임(Squad/Insurgency류)과 동일하게 **근접 통과 감지** 방식으로 구현:
- 매 틱 `ARCWSProjectile::Tick`에서 "직전 위치 → 현재 위치" 선분과 로컬 플레이어 카메라 사이 최근접 거리를 계산.
- **성능 최적화(2단계 컷)**: 먼저 선분 양 끝점이 `WhizBroadPhaseRadiusCm`(기본 1500cm) 밖이면 정밀 계산 자체를 스킵(싼 거리제곱 비교). 통과했을 때만 `FMath::ClosestPointOnSegment`로 정밀 최근접점 계산, `WhizDetectionRadiusCm`(기본 200cm) 이내면 그 지점에서 `WhizSound` 1회 재생(`bWhizPlayed` 플래그, 총알 하나당 한 번).
- **로컬 전용, 리플리케이션 없음**: `FLocalPlayerIterator`로 로컬 플레이어만 검사 — AI/서버는 들을 필요 없고, 데디케이트 서버는 로컬 플레이어가 없어 루프가 자동으로 비어 사실상 공짜로 스킵됨. 각 프로세스가 이미 자기 로컬 풀 투사체를 독립적으로 Tick하는 기존 구조를 그대로 활용.
- 아군 30 + 적군 15 + UGV RCWS 규모에서도 부담 없는 이유: 상호 체크가 아니라 "각 클라이언트 vs 자기 로컬 플레이어 카메라 1~2개"만 비교, 게다가 1차 컷으로 대부분의 원거리 총알이 정밀 계산 전에 걸러짐.

### 신규 프로퍼티 (`RCWSProjectile.h`)
`WhizSound`, `WhizDetectionRadiusCm`(200), `WhizBroadPhaseRadiusCm`(1500), `WhizSoundAttenuationRadiusCm`(300), `WhizSoundFalloffDistanceCm`(1000)

### 남은 작업
- **실제 녹음된 휘바람/크랙 SFX 에셋이 아직 없음** — 합성이 아니라 녹음된 소스가 필요, 나중에 `WhizSound`에 연결.
- 빌드 후 PIE에서 감지 반경/사운드 튜닝 확인 필요.

---

## 6. 차량(UGV / TitanTruck) 피격 재질 판정 — 완료

`SurfaceImpactEffects` 재질 판정 자체(§1~3의 소총/RCWS 발사체 로직)는 이미 되어있었지만, 차량 두 종류에 실제로 재질을 입히고 제대로 맞는지 검증하는 작업. 둘 다 최종적으로 정상 작동 확인됨.

### TitanTruck — 콜리전 프리셋 버그 발견/수정
피직스 매터리얼을 스킨 머티리얼에 다 채웠는데도 총알이 트럭을 완전히 무시하고 통과하는 문제 발생. 원인 추적 결과:
- `ARCWSProjectile::CollisionComponent`가 커스텀 콜리전 프로파일을 쓰는데, `WorldDynamic` 채널 응답이 **명시적으로 Ignore**로 되어있음(`EngineTraceChannel1`=Block, `Visibility`/`Camera`/`WorldDynamic`=Ignore).
- `BP_TitanTruck`의 `BodyMesh` + RCWS 터렛 부품 4종(`RCWSTurretBase/Body/Barrels/AmmoBox`) 전부 콜리전 프리셋이 `BlockAllDynamic`(ObjectType=`WorldDynamic`)이었음 — Datasmith 임포트 시 기본값으로 딸려온 것으로 추정, 이번 작업 전부터 있던 버그.
- 참고로 `BP_UGV_Vehicle.VehicleMesh`는 프리셋이 `Vehicle`(ObjectType=`ECC_Vehicle`)이라 투사체의 무시 목록에 안 걸려서 원래부터 정상 작동하고 있었음 — 즉 트럭만 프로젝트의 "차량은 Vehicle 프리셋" 컨벤션에서 벗어나 있었음.
→ **수정**: 위 5개 컴포넌트의 콜리전 프리셋을 `BlockAllDynamic` → `Vehicle`로 통일. 이후 스킨 머티리얼별 Phys Material 지정만으로 정상적으로 재질별 피격 판정됨(스태틱 메시라 Complex 트레이스가 실제 삼각형 기준으로 재질을 찾아줌 — 콜리전 도형 자체는 손댈 필요 없었음).

### BP_UGV_Vehicle — 스켈레탈 메시 + 피직스 에셋
스켈레탈 메시는 스태틱 메시와 달리 기본적으로 삼각형 단위 Complex 콜리전이 없어서(피직스 에셋의 프리미티브 바디만 존재), 재질 판정 해상도가 딱 피직스 에셋의 바디 개수만큼만 나옴(기존엔 차체 박스 1개, 총열 캡슐 1개뿐).

**Per-Poly Collision은 검토 후 기각**: `USkeletalMeshComponent::bEnablePerPolyCollision`을 켜면 쿼리 전용으로 추가되는 게 아니라 `InitArticulated`(피직스 에셋 기반 바디 생성, Chaos Vehicle의 서스펜션/차체 시뮬레이션이 의존)를 통째로 대체해버리는 것으로 UE 5.8 엔진 소스(`SkeletalMeshComponentPhysics.cpp`) 확인 결과 드러남 — 켰으면 차량 물리가 깨졌을 것.

→ **채택한 방법**: 피직스 에셋에 재질 영역별로 바디를 세밀하게 추가(Multi Convex Hull 자동 생성 활용), 기존 시뮬레이션 바디(차체/총열)는 그대로 둔 채 새 바디들만 다음 설정으로 완전히 수동적(passive)이게 만듦:
- `Physics Type = Kinematic` (본 트랜스폼을 그대로 따라감, 자체 시뮬레이션 안 함)
- `Collision Enabled = Query Only` (충돌 반응/질량에 기여 안 함, 트레이스/쿼리에만 응답)
- `Collision Complexity = Use Simple Collision As Complex` (피직스 에셋 바디는애초에 진짜 Complex 콜리전이 없어서 필수 — 이게 꺼져있으면 `OnHit`의 보조 Complex 트레이스에 아예 안 잡힘)
- 바디별 `Phys Material Override`로 재질 지정(스태틱 메시처럼 머티리얼 슬롯이 아니라 바디 단위)
- Query Only이므로 성능 부담 없음(피격 시에만 발동하는 이벤트성 쿼리라 헐 개수가 많아도 매 틱 비용과 무관) — 다만 헐 정밀도를 과하게 높일 필요는 없음(재질 경계 구분이 목적, 형상 완벽 재현 아님).

피직스 에셋 바디 배치는 사용자가 직접 작업.

---

## 7. 아직 안 끝난 것

- 유리(Glass) 파손 연출 — 방향 결정 안 됨(스프라이트 위장 vs Chaos Destruction), `hit_effects_implementation.md` §3 참고. 현재 유일하게 남은 항목.
