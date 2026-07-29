# 디자인팀 제공 Content 폴더 인벤토리 (2026-07-29)

`Content/` 아래 `Characters`, `FPS_Weapon_Bundle`, `NiagaraExamples`,
`Realistic_Starter_VFX_Pack_Vol2`, `ThirdPerson`, `Tutorial` 6개 폴더 조사 기록.
전부 마켓플레이스/에픽 샘플 애셋 패키지로 보이며, 서로 다른 벤더의 패키지가
섞여 있음(이름 규칙이 폴더마다 다른 이유).

## 1. Characters — 캐릭터 메시/스켈레톤/애니메이션

- `Characters/Mannequins/Anims/` — UE5 기본 Mannequin 리타겟용 애니메이션 세트.
  `Rifle/`(총기 소지, Walk 8방향/Jog 8방향/Jump/AIM/HitReact), `Pistol/`(권총
  버전, 동일 구조), `Unarmed/`(맨손, Walk/Jog/Jump/Attack + `BS_Idle_Walk_Run`
  블렌드스페이스 + `ABP_Unarmed`), `Death/`(전신 사망 6종, 방향별).
  → 이미 완비된 로코모션 세트지만 **Mannequin 스켈레톤 전용** — 아래 Tutorial
  세트와는 스켈레톤이 다를 가능성이 높음(확인 필요, 4절 참고).
- `Characters/Soldier/Rifle_Aiming_Idle` — 메시 + 스켈레톤(`Rifle_Aiming_Idle_
  Skeleton`) + 피직스 애셋. 이 스켈레톤 자체엔 애니메이션이 없지만, **Tutorial
  패키지의 애니메이션 세트(6절)가 바로 이 스켈레톤용**으로 확인됨 — 아군 BP의
  메시 후보로 가장 유력.

## 2. FPS_Weapon_Bundle — 총기 모델 (331개 애셋)

**두 종류가 섞여 있음**, 헷갈리기 쉬우니 주의:
- `Weapons/m4/` — 스켈레톤 없는 **모듈형 M4/M16 부품 세트**(스톡/그립/핸드가드/
  머즐브레이크/서프레서/탄창 등을 낱개 스태틱메시로 조합하는 방식,
  `m4noskel_*` 접두). 완성형 무기 하나가 아니라 "레고처럼 조립하는" 구조.
- `Weapons/Meshes/` — **스켈레탈 메시로 완비된 무기 6종**: `AR4`, `Ka47`(AK47
  계열), `KA74U`(AKS-74U), `KA_Val`(VAL/VSS), `SMG11`(MAC-11 계열),
  `G67_Grenade`, `M9_Knife`. 각 무기마다 `SK_*`/`SK_*_Skeleton`/`SK_*_Physics`
  + X/Y 베리언트(부착물 유무 등으로 추정, 미확인) 구성 — **볼트/노리쇠 애니메이션이
  필요하면 이쪽을 써야 함**(m4 세트는 스켈레톤이 없어서 장전 애니메이션 불가).
- `Weapons/Materials/` — 무기별 서브폴더(`AR4`/`Ka47`/`KA74U`/`KA_Val`/`SMG11`/
  `M9_Knife`/`G67_Grenade`) + `Accessories/`(스코프 `M_Scope_25x56`, 도트사이트
  `M_RDS_01~03`, 그립) + `Ammunition/`(9mm/9x18/.45acp/12게이지/40mm유탄/
  7.62x39 — 탄약 머티리얼, 실물 탄피 표현용으로 추정) + `Master_Material/`.
- **아군 BP 용도**: 병사 손에 들릴 총 메시가 필요하면 `Weapons/Meshes/`의 6종
  중 하나 선택(AR4나 Ka47이 범용 소총 느낌에 가장 무난해 보임, 실물 확인 필요).

## 3. NiagaraExamples — 대체로 프로젝트 무관한 샘플 (667개 애셋)

에픽 "Niagara Fluids/이펙트 예제" 애드온 콘텐츠를 통째로 임포트한 것으로 보임
— `BP_TeslaCoil`/`BP_DinoDragon`/`BP_HitDissolveCow`/픽업 버프·디버프 이펙트 등
전부 액션 RPG/슈터 튜토리얼용 범용 샘플이라 이 프로젝트(군사 시뮬레이션)와
직접 관련 없음. 그래도 쓸만한 것 몇 개:
- `FX_Explosions/NS_Explosion`/`NS_Explosion_Medium`/`NS_Explosion_Small`,
  `NS_Dirt_Explosion*` — Niagara 기반 폭발(현재 프로젝트가 쓰는 3절의 Cascade
  폭발 이펙트보다 최신 기술).
- `FX_NDC/NS_NDC_Impacts` — Niagara Decal Component 기반 피격 이펙트.
- `FX_Markers/NS_Marker_Location`/`NS_Marker_Target` — 월드 위치 표시용
  (미니맵/시나리오 마커 연출에 참고할만함, 지금 미사용).
- 나머지(Fog뱅크, 나비/민들레/반딧불이 등 환경 이펙트, 버프/디버프, 텔레포트)는
  이번 프로젝트 범위 밖 — **사실상 노이즈, 필요할 때만 개별적으로 뒤져볼 것**.

## 4. Realistic_Starter_VFX_Pack_Vol2 — 실사 계열 파티클(Cascade), 186개

이미 알려진 `Sparks/P_Sparks_A`(총구화염 대용)/`Hit/P_Default`/
`Blood/P_Blood_Splat_Cone` 포함, 카테고리별로 상당히 풍부함:
- `Particles/Hit/` — 재질별 피격 이펙트 11종(Asphalt/Brick/Ceramic/Concrete/
  Default/Ice/Leather/Paper/Rubber/Vegetation/Wood).
- `Particles/Sparks/` — 7종(A~G) + `Embers_A` — **총구화염 대용으로 P_Sparks_A
  외에 다른 베리언트도 골라볼 수 있음**.
- `Particles/Explosion/`(Big A/B/C, Side, Smoke, Molotov),
  `Particles/Fire/`(Big/Small/Wall/화염방사기), `Particles/Smoke/`(6종),
  `Particles/Destruction/`(건물/세라믹/콘크리트/유리/금속/나무 파괴),
  `Particles/Water/`, `Particles/Environment/`(나비/민들레/반딧불이 등 —
  이번 프로젝트엔 불필요).
- `DemoRoom/` — 벤더의 애셋 프리뷰용 쇼룸(벽/네임플레이트) — 프로젝트와
  무관, 무시해도 됨.
- 전부 **Cascade `UParticleSystem`** (Niagara 아님) — `rcws_fire_control_dev_
  guide.md` 11.4절에 이미 기록된 대로.

## 5. ThirdPerson — 완전히 미사용 스톡 템플릿

`BP_ThirdPersonCharacter`/`BP_ThirdPersonGameMode`/`BP_ThirdPersonPlayerController`
+ 머티리얼 인스턴스 1개, 총 4개 애셋뿐. `get_referencers`로 확인한 결과 **이
4개는 서로만 참조하고 프로젝트의 다른 어떤 애셋에서도 참조되지 않음** —
프로젝트를 ThirdPerson 템플릿으로 처음 생성했을 때 남은 순수 잔재. **완전히
무시해도 되는 폴더**(삭제해도 안전할 가능성 높지만, 굳이 지울 필요도 없음).

## 6. Tutorial — FPS 튜토리얼 팩 (BP_Enemy 소속 패키지 전체)

`BP_Enemy` 하나만 있는 게 아니라 **완전한 FPS 플레이어 캐릭터 템플릿 세트**가
같이 들어있음:
- `Blueprints/Enemy/` — BP_Enemy 본체, 전용 `Enemy_Skeleton`/`Enemy_
  PhysicsAsset`, 전용 애니메이션(`AS_Enemy_*`, `AM_Enemy_*Montage`) — 이전
  세션에 이미 확인한 그대로.
- `Blueprints/Weapons/` — `BP_BaseWeapon`/`BP_BaseFullAutoWeapon`/
  `BP_BaseSemiAutoWeapon` (완전 자동/반자동 무기 베이스 클래스 — 실제 발사
  로직 포함된 것으로 추정, RCWS와는 별개의 캐릭터 휴대무기 시스템).
- `Blueprints/WeaponPickups/`, `Blueprints/Magazines/`(HeldMags/DroppedMag —
  탄창 교체 연출), `Blueprints/Interfaces/BP_Interaction`,
  `Blueprints/ENUMS/ENUM_WeaponType` — **플레이어가 총을 줍고 장전하는 FPS
  루프 전체**가 갖춰져 있음. 지금 프로젝트는 RCWS 중심이라 이 무기 습득/장전
  시스템 자체를 쓸 일은 없어 보이지만, **애니메이션 트리거 방식(몽타주
  재생 등)은 아군 BP 설계에 참고할만함**.
- `Animation/AnimationBlueprints/ABP_PlayerCharacter` + `Animation/
  AnimationSequences/`(`AS_Idle`/`AS_RifleIdle`/`AS_RifleAim`/`AS_Walking`/
  `AS_Run`/`AS_Run_Forward`/`AS_Knee`/`AS_StandtoKnee`/`AS_ProneIdle`/
  `AS_ProneToKneel`/`AS_Reloading`/`AM_Reloading`/`AS_Dead`) + `BlendSpaces/
  BS_Movement` — **이 세트 전체가 `Rifle_Aiming_Idle_Skeleton`(1절) 대상**
  (레퍼런서 조회로 확인됨). `ABP_PlayerCharacter`는 원래 "플레이어 조작
  캐릭터"용으로 만들어진 애님 블루프린트지만, 이동속도 기반 Idle/Walk/Run
  블렌딩 로직이 이미 구현돼 있을 가능성이 높아서 **아군 BP의 애님
  블루프린트를 이걸 복제해서 시작하는 게 처음부터 새로 짜는 것보다 훨씬
  빠를 것** — 열어서 실제 그래프 구조 확인 권장.
- `Parachute/` — `SM_Parachute` 메시 + 머티리얼/텍스처. 시나리오 #4-3의
  "나무에 걸린 낙하산" 소품이 바로 이것.
- **정리 필요(경미)**: `Tutorial/Blueprints/BP_Enemy`(Enemy 하위폴더 밖에
  있는 것)는 실제 애셋이 아니라 **`ObjectRedirector`**(예전에 `Blueprints/`
  루트에서 `Blueprints/Enemy/`로 옮기고 남은 포인터 스텁) — 기능적으로 문제
  없지만 나중에 "Fix Up Redirectors"로 정리하면 깔끔해짐. 실제 BP_Enemy는
  `Tutorial/Blueprints/Enemy/BP_Enemy`이고, 레벨(`/Game/kadex_demo`)에서도
  이미 참조되고 있는 것으로 확인됨(실제 배치 여부와는 별개 — 소프트 참조만
  있을 수도 있음, 라이브 확인 필요).

## 7. 아군 BP 관점 결론

- **메시/스켈레톤**: `Characters/Soldier/Rifle_Aiming_Idle`
- **애니메이션 세트**: `Tutorial/Animation/AnimationSequences/*` +
  `BS_Movement` — 걷기/뛰기/무릎쏴/엎드리기/사망까지 이미 다 있음.
- **애님 블루프린트**: `Tutorial/Animation/AnimationBlueprints/
  ABP_PlayerCharacter`를 복제해서 시작 (그래프 내용은 미확인, 다음 확인
  단계에서 열어볼 것).
- **총 메시**: `FPS_Weapon_Bundle/Weapons/Meshes/`의 6종 중 선택(장전
  애니메이션까지 필요하면 필수로 이쪽, m4 부품 세트는 스켈레톤이 없어서
  캐릭터가 손에 들고 흔들 수 없음).
- **VFX**: 총구화염은 `Realistic_Starter_VFX_Pack_Vol2/Particles/Sparks/`
  중 선택, 피격은 `Particles/Hit/`(재질별) 또는 `Particles/Blood/`.
