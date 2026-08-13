# 피격 이펙트 시스템 구현 정리 (2026-08)

`hit_effects_idea.md`(초기 기획)를 바탕으로 실제 구현한 내용과, 구현 과정에서 발견/수정한 버그들을 정리. 특히 버그 파트는 나중에 비슷한 증상 만나면 바로 참고할 것.

---

## 1. 아키텍처

### C++ 흐름
- `ARCWSProjectile::OnHit` (Source/titan_example/Vehicles/RCWSProjectile.cpp)
  1. `Hit.PhysMaterial`이 항상 비어있어서(아래 버그 참고), 임팩트 지점에서 탄도 방향 ±50cm짜리 Complex 라인 트레이스를 별도로 쏴서 정확한 `PhysMaterial`/위치/노말을 구함
  2. `bHitEnemy`(적 여부) 우선 판정 → 아니면 재질별(`SurfaceImpactEffects`) 조회
  3. 우선순위: Enemy 전용 > 재질별 세트 > 범용 기본값(`ImpactEffect`/`ImpactSound`)
  4. `ReportHitToInstigator` → 각 인스티게이터 컴포넌트(`RCWSFireControlComponent`/`AllyFormationComponent`/`EnemyCombatComponent`)의 `Multicast_PlayImpactEffect` RPC → 서버 포함 전원에게 위치 기반으로 방송
  5. `PlayImpactEffect`(static)가 실제로 나이아가라 스폰 + 데칼 스폰 둘 다 수행

- `bReplicates=false`인 발사체라 서버/클라이언트가 각자 로컬로 궤적을 계산(결정론적 포물선이라 화면상 동일). 데미지·이펙트 확정은 서버(`HasAuthority`)만.

### 데이터 구조
- `EImpactSurfaceCategory`: `Wood, Hard, Dirt, Metal, Glass`
- `FImpactSurfaceEffectSet`: `SurfaceCategory`, `Effect`(NS), `Sound`, `DecalMaterial`, `DecalSize`, `DecalLifeSpan`
- `ARCWSProjectile::SurfaceImpactEffects` (TArray) — `BP_RCWSProjectile`/`BP_RifleProjectile`에서 재질별로 채움
- `EnemyDecalMaterial`/`EnemyDecalSize`/`EnemyDecalLifeSpan` — 적 피격 전용(혈흔), 재질 무관
- `MaxActiveImpactDecals` — 전역 데칼 풀 캡(FIFO, 기본 200), 데칼 기본 수명 60초

### 재질 판별
- `Config/DefaultEngine.ini`의 `PhysicalSurfaces`: `SurfaceType1=Wood, 2=Hard, 3=Dirt, 4=Metal, 5=Glass`
- `/Game/Hit_PhysicalMaterials/PM_Wood, PM_Hard, PM_Dirt, PM_Metal, PM_Glass` — 각 SurfaceType에 매핑됨
- 월드 지오메티리에 PM_* 할당 안 되어 있으면 자동으로 범용 폴백(`ImpactEffect`)으로 안전하게 떨어짐

### 데칼은 C++가 유일한 소스
- `UGameplayStatics::SpawnDecalAtLocation`으로 C++에서 직접 스폰(전역 FIFO 풀 관리)
- 나이아가라 시스템 자체에 내장된 Decal 렌더러(`LightDecal`/`BulletDecal`/`ScorchDecal` 이미터)는 전부 `bIsEnabled=false`로 꺼둠 — 안 그러면 `SurfaceImpactEffects.DecalMaterial`을 지정 안 해도 NS가 자체적으로 데칼을 그려서 중복/제어불가 상태가 됨

---

## 2. 구현 완료 현황

### 소총 (`/Game/VFX/Rifle`) — `NS_Rifle_Wood/Hard/Dirt/Metal/Glass`
- `/Game/NiagaraExamples/FX_Weapons/Impacts` 원본 4종(Wood/Hard/Metal/Glass) 재사용 + Dirt 추가 복제
- 전부 `LightDecal` 이미터를 진짜 데칼(NiagaraDecalRendererProperties)로 살려뒀다가 → C++ 데칼과 중복돼서 다시 끔(현재는 렌더러 비활성화 상태, 위치 조회 로직은 재사용 안 함)
- Dirt/Glass: `SurfaceImpactEffects`의 `decalMaterial = None` (총알구멍 데칼 없음 — 기획 의도)
- Wood/Hard/Metal: `M_Decal_Bullet` 데칼 적용

### RCWS (`/Game/VFX/RCWS`) — `NS_RCWS_Wood/Hard/Dirt/Metal/Glass`
- `NS_Dirt_Explosion_Small` 복제 기반, 재질별 파편/먼지/색상 튜닝
- Hard/Metal: `M_Decal_Bullet` 데칼. Metal은 `M_ScorchMark_01`(그을린 자국)로 교체
- Dirt/Glass: 데칼 이미터 자체를 제거(총알구멍 없음)
- **주의**: 이번 세션에서 발견된 나이아가라 그래프 버그 수정(아래 3~5번 항목)은 **소총 쪽만 검증 완료**. RCWS 쪽도 `Sparks`/`Dust`류 이미터가 있다면 같은 종류의 문제가 있을 수 있음 — 아직 실측 테스트 안 함, 나중에 확인 필요.

### 미구현 (기획서에 있지만 아직 손 안 댐)
- Wood: 폭발로 불붙는 효과
- Glass: 실제로 유리가 깨지는 연출(정적 데칼로는 불가능 — 아래 "유리 파손" 섹션 참고)
- Enemy: 혈흔 파티클(현재는 `EnemyDecalMaterial` 필드만 있고 실제 할당 여부 미확인)
- `BP_RifleProjectile`의 `SurfaceImpactEffects` 값이 제대로 다 채워져 있는지 최종 재확인 필요

---

## 3. 유리(Glass) 데칼 — 왜 안 되는지, 뭘 해야 하는지

디퍼드 데칼(`UDecalComponent`/Niagara Decal Renderer)은 오파크 GBuffer 패스에만 합성됨. 반투명 머티리얼은 그 패스를 안 타서 **데칼이 원천적으로 유리 표면에 못 얹힘**(설정 문제가 아니라 엔진 구조적 한계). 그래서 지금은 Glass에 총알 데칼 자체를 안 넣기로 함.

나중에 "진짜 유리 파손"을 구현하려면 두 방향:
1. **표면 정렬 스프라이트로 위장**(쉬움): 총알구멍+크랙 텍스처를 유리 표면에 딱 붙인 반투명 평면/스프라이트로 스폰. 반투명 제약 없음, 작은 총알구멍 수준엔 충분히 그럴듯함. 하루이틀 작업.
2. **Chaos Destruction으로 진짜 파손**(어려움): Geometry Collection으로 프랙처링 후 피격 시 로컬 파괴(Field) 또는 전체 shatter. 프랙처 패턴/성능/네트워크 리플리케이션까지 별도 설계 필요한 큰 작업.

→ 방향 결정 안 됨, 나중에 다시 논의하기로 함.

---

## 4. 트러블슈팅 노트 — 이번 세션에서 잡은 버그들

작업 순서대로. 비슷한 증상 나오면 여기부터 확인.

### 4.1 `Hit.Location` vs `Hit.ImpactPoint`
스윕(구체 콜리전)이 고속 발사체를 원거리에서 맞히면 터널링으로 `Hit.Location`이 표면 안쪽으로 파고든 값이 나옴. `Hit.ImpactPoint`(실제 표면 접촉점)를 대신 써야 함. → 오파크 메시에 이펙트가 파묻혀 안 보이던 문제 해결.

### 4.2 `Hit.PhysMaterial`이 항상 비어있음
`ProjectileMovementComponent`의 스윕 히트는 심플 콜리전 기반이라 `PhysMaterial`을 안 채워줌(항상 `None`). 재질 매칭이 전혀 안 되던 근본 원인.
→ **해결**: 임팩트 지점 기준 탄도 방향 ±50cm 짜리 별도 Complex 라인 트레이스(`bTraceComplex=true, bReturnPhysicalMaterial=true`)를 쏴서 진짜 `PhysMaterial`/정확한 `ImpactPoint`/`ImpactNormal`을 구함. 이 트레이스 결과가 지금 이펙트/데칼 위치·노말의 최종 소스.
- 트레이스 축은 `Hit.Normal`이 아니라 **탄환의 실제 진행 방향(`ImpactDirection`)** 을 써야 함 — `Hit.Normal`은 물리엔진이 침투 깊이(MTD)를 못 구하면 `UpVector`로 대체되는 신뢰 불가 값이라, 이걸 축으로 쓰면 엉뚱한 방향으로 트레이스가 나감(예전에 "이펙트가 항상 위로만 나옴" 버그의 원인).
- 탄환 진행 방향에서 봤을 때 뒷면을 잡았으면(`dot(TraceNormal, ImpactDirection) > 0`) 원래 스윕 값으로 폴백.

### 4.3 `GetVelocity()` 캐시 지연 → 근거리 피격 시 속도 0
`AActor::GetVelocity()`(`RootComponent->ComponentVelocity`)는 무브먼트 컴포넌트가 자기 Tick 끝에서 갱신하는 캐시값. 발사 직후 첫 틱 안에 바로 맞으면(10m 이내 근거리에서 자주 발생) 아직 갱신 전이라 `Deactivate()`가 리셋해둔 0이 그대로 읽힘. → `ImpactVelocity`/`ImpactDirection`이 0벡터가 되고, 그 여파로 보조 트레이스도 실패, 나이아가라 방향 계산도 깨짐.
→ **해결**: `ProjectileMovement->Velocity`를 직접 읽음(캐시 지연 없이 항상 최신). `Deactivate()`가 이 프로퍼티도 0으로 리셋하므로 그 전에 읽어야 함.

### 4.4 나이아가라 그래프 — World/Local 좌표계 이중 변환
`System.Burst Direction`/`System.Local Hit Velocity`(SystemSpawnScript)가 `TransformVector` 다이나믹 인풋으로 `User.Hit Direction`/`Normal`(월드 스페이스)을 **World→Local로 변환**하고 있었는데, 정작 이걸 쓰는 `Sparks`/`Dust`/`Debris` 이미터는 전부 `bLocalSpace: false`(월드 스페이스 시뮬레이션)라 이 변환이 필요 없었음 — 오히려 스폰 회전만큼 방향이 꼬임.
→ `TransformVector`의 `Destination Space`를 `Local`→`World`로 수정(5개 라이플 시스템 전부).
- **추가로** `AddVelocity` 모듈 자체의 `Rotation Coordinate Space`도 `Local`로 남아있어서 같은 이중 변환이 한 번 더 일어나고 있었음 → 이것도 `World`로 수정.
- **그런데 이걸 다 고쳐도 실제로는 여전히 스폰 회전에 따라 결과가 같이 회전해버리는 게 실측으로 확인됨**(레벨에 NS를 액터로 직접 배치해서 Hit Normal만 세팅하고 회전을 Identity vs 180도로 바꿔가며 비교 테스트). 그래프 내부에 위 두 곳 말고도 뭔가 스폰 트랜스폼에 종속된 경로가 더 있는 것으로 보이나 원인을 끝까지 못 찾음.
→ **최종 해결**: 나이아가라 스폰 회전을 아예 `FRotator::ZeroRotator`(Identity)로 고정. 방향은 순전히 `User.Hit Normal/Direction/Velocity`(월드 스페이스 값)만으로 계산되게 함. 데칼 스폰 회전(`FRotationMatrix::MakeFromX(-Normal)`)은 완전히 별개 호출이라 영향 없음, 계속 정확하게 동작.

### 4.5 `AddVelocity002`가 탄환의 원본(입사) 속도를 그대로 더함 — 스파크 방향 오염
`AddVelocity002`가 `System.Local Hit Velocity`(= 탄환이 날아온 방향 그대로, 표면 안쪽을 향함)를 파티클 속도에 그대로 더하고 있었음. 이게 `AddVelocity001`의 올바른 반사 버스트(`System.Burst Direction`, 바깥쪽)와 비슷한 크기로 정면 충돌해서 방향이 상쇄/역전됨.
- Dust(연기)는 노이즈 확산이 커서 안 티 났지만, Sparks(빠르고 선명한 궤적)는 뚜렷하게 "반대 방향"으로 보였음.
→ **해결**: `AddVelocity002` 모듈 자체를 비활성화(Sparks/Dust, 5개 시스템 전부). `AddVelocity001`(Cone 기반, `Particles.BurstSpeed`로 이미 잘 튜닝된 50~500 범위) 혼자로도 방향·속도 다 정상.
- 참고: `AddVelocity002`의 속도 스케일도 처음엔 0.005로 낮췄었음(탄속 7~8만 유닛/초를 그대로 꽂아넣어서 파티클이 실제 총알 속도로 날아가던 별개 버그) — 지금은 모듈 자체를 꺼서 이 스케일 값 자체가 무의미해짐.

### 4.6 나이아가라 에셋 자체의 데칼이 C++ 데칼과 중복 스폰
`SurfaceImpactEffects.DecalMaterial`을 지정 안 해도 총알구멍이 나오는 문제 — NS 자체의 `LightDecal`/`BulletDecal`/`ScorchDecal` 이미터 안의 Decal 렌더러가 독립적으로 항상 데칼을 그리고 있었음(원래 데칼 렌더링 자체가 안 되던 걸 고치는 과정에서 살려놨다가 발생).
→ 모든 재질 NS의 Decal 렌더러(rendererIndex 2)를 `bIsEnabled=false`로 끔. Light/Sprite 렌더러(섬광/불꽃)는 그대로 유지. 총알구멍 데칼은 이제 오직 C++(`SurfaceImpactEffects.DecalMaterial`)에서만 제어.

---

## 5. 다음에 할 일 (우선순위 순)

1. RCWS 쪽도 4.4/4.5와 같은 좌표계·벡터 충돌 버그 있는지 확인(라이플만 검증했음)
2. `BP_RifleProjectile`의 `SurfaceImpactEffects` 최종 값 재확인
3. 유리 파손 방향 결정(스프라이트 위장 vs Chaos Destruction) 후 구현
4. Wood 화염 효과
5. Enemy 혈흔 파티클 신규 구현
