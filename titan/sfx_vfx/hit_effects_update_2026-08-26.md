# 피격 이펙트 — 재질(PhysicalMaterial) 배선 (2026-08-26, 동작 확인 완료)

대상 레벨: `New_kadex_0811`

지형·바위·나무·PCG 프록시 전부에서 재질별 피격 이펙트가 나오도록 배선한 작업 기록.
시행착오가 많았던 주제라 **"무엇을 어디에 걸어야 하는가"** 를 먼저 정리한다.

---

## 1. 결론 먼저 — 지금 실제로 동작하는 설정

| 대상 | 어디에 걸었나 | 값 | 저장 위치 |
|---|---|---|---|
| **바위 69개 액터** | 컴포넌트 `PhysMaterialOverride` | PM_Hard | 레벨 |
| **나무 213개 액터** | 컴포넌트 `PhysMaterialOverride` | PM_Wood | 레벨 |
| **PCG 나무 프록시** `Actor_6` (ISM 23개) | 컴포넌트 `PhysMaterialOverride`<br>+ `ObjectType`<br>+ `Visibility` 응답 | PM_Wood<br>`ECC_WorldStatic`<br>`ECR_Block` | 레벨 |
| **지형** | `Land_scape_m/PhysicalMaterials/PM_*` 5종의 `SurfaceType` | 전부 SurfaceType3 (Dirt) | 아트 에셋 |
| **트럭/UGV** | (원래부터) 머티리얼의 `PhysMaterial` | PM_Metal / PM_Glass / PM_Dirt | 아트 에셋 |

**무기 쪽(`SurfaceImpactEffects`)은 원래부터 완성돼 있었다 — 건드릴 것 없음.**
`BP_RCWSProjectile` / `BP_RifleProjectile` 둘 다 Dirt/Wood/Hard/Metal/Glass 5종에
VFX·사운드·데칼·도탄비율이 다 채워져 있다.

### SurfaceType 대응표

`Config/DefaultEngine.ini` 의 `[/Script/Engine.PhysicsSettings]` 에 이름 등록됨.

| SurfaceType | 이름 | 에셋 |
|---|---|---|
| SurfaceType1 | Wood | `/Game/Hit_PhysicalMaterials/PM_Wood` |
| SurfaceType2 | Hard | `/Game/Hit_PhysicalMaterials/PM_Hard` |
| SurfaceType3 | Dirt | `/Game/Hit_PhysicalMaterials/PM_Dirt` |
| SurfaceType4 | Metal | `/Game/Hit_PhysicalMaterials/PM_Metal` |
| SurfaceType5 | Glass | `/Game/Hit_PhysicalMaterials/PM_Glass` |

---

## 2. 동작 원리

`Source/titan_example/Vehicles/RCWSProjectile.cpp` 의 `HandleImpact` (대략 350~412행):

```cpp
TWeakObjectPtr<UPhysicalMaterial> ResolvedPhysMaterial = Hit.PhysMaterial;   // ← 항상 null
...
FCollisionQueryParams MaterialTraceParams(..., /*bTraceComplex=*/true);      // ★ 콤플렉스
MaterialTraceParams.bReturnPhysicalMaterial = true;
LineTraceSingleByChannel(MaterialHit, TraceStart, TraceEnd, ECC_Visibility, MaterialTraceParams);
if (bTraceHit && !ResolvedPhysMaterial.IsValid())
    ResolvedPhysMaterial = MaterialHit.PhysMaterial;
if (ResolvedPhysMaterial.IsValid())
    SurfaceSet = FindSurfaceEffectSet(ResolvedPhysMaterial->SurfaceType);
```

- `Hit.PhysMaterial` 은 CollisionComponent 의 `bReturnMaterialOnMove = false` 때문에 **항상 null**.
  → **재질 판정은 전적으로 저 보조 라인트레이스가 담당한다.**
- 보조 트레이스는 피격 지점에서 **탄도 방향으로 ±50cm**, 채널 `ECC_Visibility`, **콤플렉스**.

### 그래서 두 가지 조건이 필요하다

1. **대상이 `ECC_Visibility` 를 Block 해야 한다.** Ignore 하면 트레이스가 관통해서 재질을 못 찾는다.
2. **컴포넌트 `PhysMaterialOverride` 가 걸려 있어야 한다.** (아래 참고)

---

## 3. ★ 물리재질은 컴포넌트 오버라이드로 걸어라

`p.RCWS.ImpactDebug 1` 로그로 실측한 결과다. **경로마다 결과가 다르다.**

| 거는 위치 | 결과 |
|---|---|
| **컴포넌트 `PhysMaterialOverride`** | ✅ **항상 동작** |
| 머티리얼의 `PhysMaterial` | △ 에셋에 따라 다름 (트럭은 되는데 바위/나무는 안 됨) |
| 메시 `BodySetup.PhysMaterial` | ❌ 바위/나무에서 안 됨 |

바위 머티리얼에 `PM_Hard`, BodySetup 에도 `PM_Hard` 를 지정하고 **저장 + 에디터 재시작까지 한 뒤**
찍은 로그:

```
스윕: actor=StaticMeshActor_21 physmat=None | 보조트레이스=적중 actor=StaticMeshActor_21
      physmat=DefaultPhysicalMaterial | 최종 physmat=DefaultPhysicalMaterial surface=0 | SurfaceSet=없음
```

트레이스는 바위를 **정확히 맞히는데** 엔진 기본값이 돌아왔다. 반면 컴포넌트 오버라이드를 쓴
테스트 큐브는 같은 로그에서 정상:

```
스윕: actor=StaticMeshActor_29 | 보조트레이스=적중 physmat=PM_Dirt | surface=3 | SurfaceSet=찾음
```

> **→ 앞으로 레벨에 뭔가 새로 배치하고 피격 이펙트를 붙일 땐 컴포넌트의
> `Collision → Phys Material Override` 에 걸 것.** 머티리얼/BodySetup 은 믿지 말 것.

**보너스: 컴포넌트 오버라이드는 레벨에 저장된다.** 디자이너가 P4 로 머티리얼·메시 새 버전을
올려도 안 날아간다. (원래 이 부분이 걱정거리였는데 저절로 해결됐다.)

---

## 4. 지형은 별도 경로

랜드스케이프 머티리얼 `M_AutoLandscape` 에 **Physical Material Output** 노드가 있고,
입력이 이 순서로 물려 있다:

```
[0] PM_Cliff   [1] PM_MidHigh   [2] PM_MidLow   [3] PM_Ground
```

> **Physical Material Output 이 있으면 Landscape 액터의 `DefaultPhysMaterial` 은 무시된다.**
> (그래서 `DefaultPhysMaterial` 만 바꾼 첫 시도는 아무 효과가 없었다.)

그리고 **베이크된 랜드스케이프 물리재질 데이터가 어디를 쏘든 인덱스 0 = `PM_Cliff` 만 반환한다**
(레이어 가중치가 반영돼 있지 않음). 그래서 처음엔 PM_Cliff 만 Hard 로 뒀더니 평지에서도 Hard
효과가 나왔고, 결국 **5종 전부 SurfaceType3 (Dirt)** 로 통일했다.

| 에셋 (`/Game/Land_scape_m/PhysicalMaterials/`) | SurfaceType |
|---|---|
| `PM_Ground` / `PM_MidLow` / `PM_MidHigh` / `PM_Snow` / `PM_Cliff` | **SurfaceType3 (Dirt)** |

> ⚠️ **`Friction` 은 절대 건드리지 말 것** (전부 0.7). UGV 휠 물리가 이 값을 읽는다.
> SurfaceType 만 바꾸는 건 주행에 영향 없음 — 실측 확인함.

**절벽만 Hard 로 되살리려면** 먼저 랜드스케이프 물리재질 데이터를 다시 빌드해서 레이어 가중치가
제대로 들어가게 한 뒤 `PM_Cliff` 를 SurfaceType2 로 되돌릴 것.

---

## 5. PCG 나무 콜리전 프록시 (`Actor_6`)

길가 PCG 나무 위치의 보이지 않는 실린더 콜리전 1,719개(ISM 23개).
배경은 `vehicle/ugv/2026-08-27_new_kadex_0811_navmesh_autonomous_driving.md` 참고.

세 가지를 바꿔서 해결했다.

| 항목 | 변경 | 이유 |
|---|---|---|
| `ObjectType` | `ECC_WorldDynamic` → **`ECC_WorldStatic`** | 프로젝타일이 WorldDynamic 을 `ECR_Ignore` 한다(총알끼리 안 부딪히게 하려는 설정). 그래서 총알이 프록시를 그냥 통과했다 |
| `Visibility` 응답 | `ECR_Ignore` → **`ECR_Block`** | 재질 조회 트레이스가 `ECC_Visibility` 를 쓴다 |
| `PhysMaterialOverride` | → **PM_Wood** | |

`Camera` 는 `ECR_Ignore` 유지 — 보이지 않는 실린더가 카메라를 밀어내면 안 되므로.

**`Visibility` Block 은 부작용이 아니라 의도된 동작이다.** `ECC_Visibility` 는
`TargetDetectionComponent.cpp:277` 의 표적 탐지 시야 판정과
`URCWSFireControlComponent::UpdateMuzzleBallisticAim` 의 RCWS 탄도 조준도 쓰는데,
**나무는 시야를 가려야 하고, 나무를 조준하면 그 나무까지의 거리로 조준하는 게 맞다.**

> ✅ **줄기 굵기에 맞춰 축소 완료 (2026-08-26).** 원래는 내비메시 여유폭 기준으로 전 개체
> 반경 50cm / 높이 6m 고정이라, 보이지 않는 기둥이 총알과 시야를 과하게 가렸다. 종별 실측 줄기
> 치수(소나무 반경 16cm·높이 7.0m / 자작나무 반경 22cm·높이 8.6m)에 **각 나무 인스턴스의 원래
> 스케일(0.51~0.89)을 곱해** 개체별로 다시 잡았다 →
> **지름 16.5~39.0cm(중앙값 25.9cm), 높이 3.6~7.6m**, 총 1,931개.
> 같이 정리: 컴포넌트마다 하나씩 있던 **월드 원점(0,0,0) 유령 인스턴스 23개** 제거, 빈 컴포넌트
> `Birch_3_1` 삭제. 절차와 함정은 `vehicle/ugv/2026-08-27_new_kadex_0811_navmesh_autonomous_driving.md` 2절 참고.

**프로젝타일 쪽은 절대 만지지 말 것.** WorldDynamic 응답을 Block 으로 바꾸면 총알끼리 충돌한다.

---

## 6. ❌ 하지 말 것

### `bReturnMaterialOnMove` 를 켜지 말 것

`CollisionComponent->bReturnMaterialOnMove = true` 로 하면 `Hit.PhysMaterial` 이 채워지는데,
스윕은 `bTraceComplexOnMove=false` 라 **심플 셰이프**의 물리재질을 돌려준다. 그 값은 아무것도
지정 안 돼 있어도 **null 이 아니라 `GEngine->DefaultPhysMaterial`(유효 포인터)** 이라:

```cpp
if (!ResolvedPhysMaterial.IsValid())          // ← 유효하니까 건너뜀
    ResolvedPhysMaterial = MaterialHit.PhysMaterial;   // 트럭이 쓰던 경로가 죽는다
```

→ **머티리얼 physmat 으로 동작하던 트럭/UGV 가 SurfaceType_Default 로 떨어져 이펙트를 잃는다.**
실제로 한 번 켰다가 되돌렸다. `RCWSProjectile.cpp` 생성자에 주의 주석을 남겨뒀다.

정말 켜야 한다면 폴백 조건을 같이 고쳐야 한다:
```cpp
if (!ResolvedPhysMaterial.IsValid() || ResolvedPhysMaterial->SurfaceType == SurfaceType_Default)
```

### 머티리얼 / BodySetup 에 physmat 거는 것 (§3)

바위·나무에선 안 먹는다. 이번에 지정했다가 **전부 revert 했다** (아래 목록).

---

## 7. Revert 한 것 — 다시 손대지 말 것

아래 44개는 시행착오 과정에서 지정했다가 **효과 없음이 확인되어 전부 되돌렸다.**
같은 실수를 반복하지 않도록 기록해 둔다.

```
머티리얼 25종 (PhysMaterial 지정 → revert)
  /Game/MWPaperBirchForest/Materials/Rocks/MTL_BHF_RockA .. RockD              (4)
  /Game/MWPaperBirchForest/Materials/Slopes/MTL_BHF_SlopeRoots                 (1)
  /Game/MWPaperBirchForest/Materials/Trees/MTL_BHF_*                          (15)
  /Game/RealBiomes/Materials/Ground_Base/Pine_Roots/MI_Pine_Ground_Roots_01     (1)
  /Game/RealBiomes/Materials/Vegetation/Trees/Scots_Pine/MI_Scots_Pine_*        (4)

StaticMesh 19종 (BodySetup.PhysMaterial 지정 → revert)
  /Game/MWPaperBirchForest/Meshes/Rocks/SM_BHF_Rock*                           (8)
  /Game/MWPaperBirchForest/Meshes/Trees/SM_BHF_BirchTree*                      (8)
  /Game/RealBiomes/Meshes/Vegetation/Trees/scots_pine/SM_Scots_Pine_*          (3)
```

**결과적으로 아트 에셋은 하나도 안 건드린 상태다** (지형 PM 5종 제외).

---

## 8. 진단 도구 — `p.RCWS.ImpactDebug`

`RCWSProjectile.cpp` 에 심어둔 콘솔 변수. **빌드 한 번 하면 이후엔 런타임 토글.**

```
p.RCWS.ImpactDebug 1
```

히트마다 한 줄:

```
[RCWSImpactDebug] 스윕: actor=? comp=? physmat=? | 보조트레이스=적중/빗나감 actor=? comp=? physmat=?
                  | 최종 physmat=? surface=N | SurfaceSet=찾음/없음
```

| 로그 | 진단 |
|---|---|
| `스윕: actor=Landscape_1 ...` | 노린 대상을 못 맞히고 지형에 맞음 (PCG 인스턴스는 대부분 `NoCollision`) |
| `보조트레이스=빗나감` | 총알은 맞았는데 재질 트레이스가 관통 — 대상이 `ECC_Visibility` 를 Ignore |
| `physmat=DefaultPhysicalMaterial surface=0` | 대상은 맞췄는데 물리재질 미지정 → 이펙트 없음 |
| `physmat=PM_Wood surface=1 SurfaceSet=찾음` | 정상. 그래도 안 보이면 **이펙트 밝기(노출) 문제** |

`surface` : 0=Default(매칭실패), 1=Wood, 2=Hard, 3=Dirt, 4=Metal, 5=Glass

---

## 9. 검증 / 재적용 스크립트

Claude(MCP) 의 `ProgrammaticToolset.execute_tool_script` 에 그대로 넣으면 된다.

### 9-1. 전체 상태 검증 (읽기만)

```python
import json
def call(t, p): return execute_tool(t, json.dumps(p))
def getp(ref, names):
    return json.loads(call("editor_toolset.toolsets.object.ObjectTools.get_properties",
        {"instance": {"refPath": ref}, "properties": names})["returnValue"])

def run():
    out = {}
    bad = total = 0
    for folder, want in [("SplineForest/Rock", "PM_Hard"), ("SplineForest/Tree_Plant", "PM_Wood")]:
        for a in call("editor_toolset.toolsets.scene.SceneTools.get_actors_in_folder",
                      {"folder_path": folder, "recursive": True})["returnValue"]:
            for c in call("editor_toolset.toolsets.actor.ActorTools.get_components",
                          {"actor": {"refPath": a["refPath"]},
                           "component_type": {"refPath": "/Script/Engine.StaticMeshComponent"}})["returnValue"]:
                total += 1
                o = getp(c["refPath"], ["BodyInstance"])["BodyInstance"]["physMaterialOverride"]
                got = o["refPath"].split("/")[-1].split(".")[0] if isinstance(o, dict) else "None"
                if got != want: bad += 1
    out["1_rock_tree_overrides"] = f"{total-bad}/{total}"

    comps = call("editor_toolset.toolsets.actor.ActorTools.get_components",
        {"actor": {"refPath": "/Game/New_kadex_0811.New_kadex_0811:PersistentLevel.Actor_6"},
         "component_type": {"refPath": "/Script/Engine.InstancedStaticMeshComponent"}})["returnValue"]
    good = 0
    for c in comps:
        bi = getp(c["refPath"], ["BodyInstance"])["BodyInstance"]
        vis = "Block"
        for e in bi["collisionResponses"]["responseArray"]:
            if e["channel"] == "Visibility": vis = e["response"]
        o = bi["physMaterialOverride"]
        pm = o["refPath"].split("/")[-1].split(".")[0] if isinstance(o, dict) else "None"
        if vis == "ECR_Block" and pm == "PM_Wood" and bi["objectType"] == "ECC_WorldStatic": good += 1
    out["2_pcg_proxies"] = f"{good}/{len(comps)}"

    ls = {}
    for n in ["PM_Cliff", "PM_Ground", "PM_MidHigh", "PM_MidLow", "PM_Snow"]:
        p = f"/Game/Land_scape_m/PhysicalMaterials/{n}.{n}"
        ls[n] = getp(p, ["SurfaceType"])["SurfaceType"]
    out["3_landscape"] = ls

    for cdo in ["/Game/Vehicles/UGV/Effects/BP_RCWSProjectile.Default__BP_RCWSProjectile_C",
                "/Game/Soldiers/Weapons/BP_RifleProjectile.Default__BP_RifleProjectile_C"]:
        out["4_" + cdo.split("/")[-1].split(".")[0]] = getp(
            cdo + ":CollisionComponent", ["bReturnMaterialOnMove"])["bReturnMaterialOnMove"]
    return out
```

**정상 기대값:** `282/282`, `23/23`, 지형 5종 전부 `SurfaceType3`,
`bReturnMaterialOnMove` 는 **둘 다 `false`**.

### 9-2. 컴포넌트 오버라이드 재적용 (레벨이 날아간 경우)

```python
import json
def call(t, p): return execute_tool(t, json.dumps(p))
def run():
    done = 0
    for folder, pm in [("SplineForest/Rock",       "/Game/Hit_PhysicalMaterials/PM_Hard.PM_Hard"),
                       ("SplineForest/Tree_Plant", "/Game/Hit_PhysicalMaterials/PM_Wood.PM_Wood")]:
        for a in call("editor_toolset.toolsets.scene.SceneTools.get_actors_in_folder",
                      {"folder_path": folder, "recursive": True})["returnValue"]:
            for c in call("editor_toolset.toolsets.actor.ActorTools.get_components",
                          {"actor": {"refPath": a["refPath"]},
                           "component_type": {"refPath": "/Script/Engine.StaticMeshComponent"}})["returnValue"]:
                call("editor_toolset.toolsets.object.ObjectTools.set_properties",
                     {"instance": {"refPath": c["refPath"]},
                      "values": json.dumps({"BodyInstance": {"physMaterialOverride": {"refPath": pm}}})})
                done += 1
    return {"components_set": done}
```
나무 213개는 한 번에 돌리면 타임아웃 — `acts[0:106]`, `acts[106:]` 로 쪼갤 것.

### 9-3. 지형 PM 재적용 (P4 업데이트로 날아간 경우)

```python
import json
def call(t, p): return execute_tool(t, json.dumps(p))
def run():
    r = {}
    for n in ["PM_Ground", "PM_MidLow", "PM_MidHigh", "PM_Snow", "PM_Cliff"]:
        ref = f"/Game/Land_scape_m/PhysicalMaterials/{n}.{n}"
        call("editor_toolset.toolsets.object.ObjectTools.set_properties",
             {"instance": {"refPath": ref}, "values": json.dumps({"SurfaceType": "SurfaceType3"})})
        r[n] = json.loads(call("editor_toolset.toolsets.object.ObjectTools.get_properties",
            {"instance": {"refPath": ref}, "properties": ["SurfaceType"]})["returnValue"])["SurfaceType"]
    return r
```

---

## 10. P4 안전성 — 날아갈 수 있는 것

| 설정 | 저장 위치 | 디자이너 P4 업데이트 |
|---|---|---|
| 바위·나무 컴포넌트 오버라이드 282개 | 레벨 (`__ExternalActors__`) | ✅ 안 날아감 |
| `Actor_6` 프록시 설정 | 레벨 | ✅ 안 날아감 |
| `p.RCWS.ImpactDebug` + 주의 주석 | C++ 소스 | ✅ 안 날아감 |
| **지형 PM 5종 SurfaceType** | `Land_scape_m/PhysicalMaterials/` | ⚠️ **이것만 날아갈 수 있음** |

**→ P4 업데이트 후 복구가 필요한 건 지형 PM 5종뿐이다.** §9-1 로 확인, §9-3 으로 복구.

**증상:** 지형을 쏴도 흙먼지가 안 나오는데 바위·나무는 정상 → 지형 PM 이 날아간 것.

---

## 11. 알려진 한계 / 남은 작업

### 숲 안쪽 PCG 나무·바위는 총알이 통과한다
`BP_SplineForest_tree_C` / `BP_SplineForest_plant_C` 의 ISM·HISM 이 전부 **`NoCollision`** 이다
(`ISM_SM_BHF_BirchTreeA`, `ISM_SM_Scots_Pine_Forest_02`, `ISM_SM_Pine_Rock_Small_01` 등).
성능 때문에 의도된 설계이고, 길가 나무만 `Actor_6` 프록시로 콜리전을 준다.
→ 숲 깊숙한 곳의 나무·작은 바위를 쏘면 총알이 통과해 뒤의 지형에 맞는다.

### Dirt / Wood 는 총알구멍 데칼이 없다
`SurfaceImpactEffects` 배열에서 `Dirt`·`Wood`·(RCWS의 `Glass`) 행의 **`DecalMaterial` 이 비어 있다.**
파티클·사운드는 나오는데 탄흔이 안 남는다. `Hard`·`Metal` 은 `M_Decal_Bullet` 지정돼 있음.
흙·나무에도 탄흔을 원하면 해당 행에 데칼 머티리얼을 채우면 된다.

### ~~프록시 실린더 반경 축소~~ → 완료 (2026-08-26)
종별 실측 줄기 치수 × 나무별 원래 스케일로 재산정. 지름 16.5~39.0cm(중앙값 25.9cm),
높이 3.6~7.6m, 1,931개. 유령 인스턴스 23개도 같이 제거. §"해법 1" 박스와
`vehicle/ugv/2026-08-27_new_kadex_0811_navmesh_autonomous_driving.md` 2절 참고.

### 이펙트 자체의 밝기
연기가 검게 나오고 스파크가 잘 안 보이는 건 재질 배선과 무관한 **노출 문제**다.
이 레벨은 노출이 고정(지면 ≈200 nit)이라 VFX 를 nit 단위로 맞춰야 한다.
memory `project-vfx-nit-scale` / `project-vfx-nit-scale-applied-values` 참고.

---

## 12. 피격 이펙트 자체의 밝기 (nit 스케일)

재질 배선이 끝난 뒤, **스파크와 불꽃이 검게 나오는** 문제가 남았다. 재질과 무관한 노출 문제다 —
이 레벨은 노출이 고정이고 지면이 약 **200 nit** 이라, `Unlit` 머티리얼을 쓰는 이미터의 색은
**그대로 nit 값**이 된다. 1 nit 짜리 흰색은 200 nit 배경에 완전히 묻힌다.

### 어느 이미터가 Unlit인가 (= 색이 곧 nit)

| 시스템 | 이미터 | 머티리얼 |
|---|---|---|
| `NS_RCWS_*` 5종 전부 | `SparkDebris` | `M_Sparks` [Unlit/Masked] |
| `NS_RCWS_Wood` | `Fire` | `M_Fire_01` [Unlit/Translucent] |
| `NS_Rifle_*` 5종 전부 | `Sparks`, `SecondarySparks` | `M_Sparks` [Unlit/Masked] |
| (미조정) `NS_RCWS_Hard/Wood/Metal`, `NS_Rifle_*` | `BulletDecal`/`ScorchDecal`/`LightDecal` 안의 밝은 코어 | `M_BrightCore` [Unlit/Additive] |

**스파크는 금속뿐 아니라 흙·나무·돌·유리 전부에 있다.** 금속에 개수가 많아 눈에 띄었을 뿐,
5종 다 같은 값으로 검게 나오고 있었다.

나머지(`Explosion`, `GroundDust`, `Dust`, `Debris`, 데칼)는 `DefaultLit` 이라 씬 조명을 받아
정상 동작한다 — **건드리지 말 것.**

### 적용값 (2026-08-26)

| 대상 | 원본 → 적용 |
|---|---|
| `NS_RCWS_*` 5종 / `SparkDebris` / `InitializeParticle > Color > [MaskLinearColorBySpawnGroup] > Masked Linear Color` | (20, 8.25, 0.938, a1) → **(4000, 1650, 187.6, a1)** ×200, 색조 유지 |
| `NS_RCWS_Wood` / `Fire` / `InitializeParticle > Color` | (1, 1, 1, a1) → **(2500, 2500, 2500, a1)** |
| `NS_Rifle_*` 5종 / `Sparks`, `SecondarySparks` / `InitializeParticle > Color` | (1, 1, 1, a1) → **(4000, 4000, 4000, a1)** |

총 16개 이미터. 10개 시스템 전부 컴파일 정상 확인.

### RCWS 피격의 "작은 화염" — 블랙바디 발광이 꺼진 게 아니라 1 nit 이었다

RCWS 5종의 `Explosion` 이미터가 쓰는 `MI_ExplosionRoil_8x8` 에는 화염 시스템이 **이미 켜져 있다**:

```
SW Use Blackbody = True            ← 온도 기반 화염 발광 ON
S  Temperature Min = 1200 / Max = 7000   (켈빈)
S  Emissive Gain = 1               ← ★ nit 배율. 이것 때문에 1 nit 이라 안 보였다
V  Emissive Color = (1,1,1,1)
SW Use Particle Color For Emissive = False   → 파티클 색은 BaseColor 전용
```

`Emissive Gain` 만 올리면 되는데, **`MI_ExplosionRoil_8x8` 은 공유 자산이라 직접 고치면 안 된다.**
참조처: NiagaraExamples 의 `NS_Explosion*` / `NS_Dirt_Explosion*` / `NE_Explosion` / `NE_GroundDust` /
`NE_Core` / `NE_DustExplosion`, 그리고 **`VFX/Blood/NS_Blood_RCWS`, `NS_Blood_Splat_RCWS`(혈흔)**.
→ 그냥 올리면 **피가 빛난다.**

**처리 (2026-08-26)**

| 항목 | 내용 |
|---|---|
| 신규 | `/Game/VFX/RCWS/MI_RCWS_ImpactFire` — `MI_ExplosionRoil_8x8` 복제 |
| 값 | `Emissive Gain` 1 → **2000** (나머지 파라미터 전부 동일) |
| 배선 | `NS_RCWS_*` 5종의 **`Explosion`** 이미터 렌더러만 새 MI 로 교체 |
| 유지 | **`GroundDust` 는 원본 MI 그대로** — 먼지는 빛나면 안 되므로 |

원본 `MI_ExplosionRoil_8x8` 은 `Emissive Gain = 1` 무수정 확인. 5종 컴파일 정상.

### 소총 쪽도 같은 구조 — 처리 완료

`NS_Rifle_*` 에는 `Explosion` 이미터가 없고 **`Dust`** 가 그 역할이다. 이 `Dust` 가 쓰는 MI 들도
`Use Blackbody = True` + `Emissive Gain = 1` 로 같은 상태였다(숨은 잔불이 안 보임).
원본은 `NS_Impact_Concrete/Glass/Wood/Metal`, `NS_NDC_Impacts`,
`NS_Player_Electricity_Looping` 이 공유하므로 **역시 복제로 처리**.

| 신규 | 복제원 | `Emissive Gain` | 사용처 |
|---|---|---|---|
| `/Game/VFX/Rifle/MI_Rifle_ImpactDust` | `MI_SmokePuffLight_8x8_Emissive` | 1 → **1500** | `NS_Rifle_Dirt / Glass / Hard / Wood` 의 `Dust` |
| `/Game/VFX/Rifle/MI_Rifle_ImpactDust_Wispy` | `MI_SmokeWispy_8x8_Emissive` | 1 → **1500** | `NS_Rifle_Metal` 의 `Dust` |

원본 2종 `Emissive Gain = 1` 무수정 확인. `NS_Rifle_*` 5종 컴파일 정상.
RCWS(2000)보다 낮게 잡은 건 소총탄이 더 작은 피격이기 때문 — 노브는 `Emissive Gain` 하나.

> ⚠️ **`User.Dirt Color` 는 건드리지 말 것.** `SparkDebris` 는 `MaskLinearColorBySpawnGroup` 으로
> 한 이미터에서 **뜨거운 스파크(Masked Linear Color)** 와 **어두운 파편(User.Dirt Color)** 을 같이
> 뿌린다. 파편 색까지 올리면 흙덩이가 빛나 버린다.

**튜닝 노브:** 스파크 피크 4000, 불 2500. 더 뜨겁게 하려면 이 값만 올리면 된다.
참고로 이 프로젝트의 다른 기준값 — 트레이서 7650, 총구 화염 10000, 과열 연기 피크 1350.

---

## 13. 부록 — 같은 날 함께 작업한 VFX 밝기 조정

피격 이펙트와 별개지만 같은 세션에서 건드린 것들.

| 에셋 | 항목 | 원본 → 적용 |
|---|---|---|
| `NS_MuzzleFlash_UGV`, `NS_MuzzleFlash` | `User.Flash Base Color` | (100, 23.909069, 1.215285, a0.5) → **(10000, 2390.9069, 121.5285, a0.5)** |
| 〃 | `Flash_Center` / ParticleUpdate / `Light_Attributes` | `Volumetric Scattering` 스위치 `Unset(0)` → **`Apply(1)`**, `Light Volumetric Scattering` → **8.0** |
| `NS_bullet`, `NS_Rifle_Tracer` | `Empty` / ParticleSpawn / `InitializeParticle` / `Color` | (255, 70.264885, 0, a1) → **(7650, 2107.94654, 0, a1)** |
| `NS_BarrelSmoke` | `Smoke` / ParticleSpawn / `InitializeParticle` / `Color` 알파 | 0.0608696 → **0.45** |
| `/Game/VFX/RCWS/MI_RCWS_BarrelSmoke` **(신규)** | `MI_SmokeLoop_02` 복제, 부모는 원본 `M_SmokeMuzzle_01` 유지 | `Mult` 1 → **1500** |
| `NS_BarrelSmoke` | `Smoke` 렌더러 0 의 Material | → 위 신규 MI |

주의점:
- `M_SmokeMuzzle_01` 은 **`MP_BaseColor` 미연결 = 조명을 안 받는 emissive 전용** 머티리얼이다.
  검은 연기의 원인은 라이팅이 아니라 `Mult`(nit 스케일)였다.
- 스프라이트 렌더러가 `FacingMode = FaceCamera` 라
  **`TranslucencyLightingMode` 를 `Surface ForwardShading` 계열로 바꾸면 안 된다.**
  법선이 카메라를 따라 돌아서 카메라 각도만 바꿔도 검정↔흰색으로 뒤집힌다(실측 확인).
- 총구 화염 라이트 색 = `Particles.Initial.Color` = `User.Flash Base Color`
  (`Light_Attributes` 의 `Use Light Color` = false). 스프라이트와 라이트가 같이 스케일된다.
  분리하려면 `Use Light Color` 를 켜고 `Light Color` 를 별도 User Parameter 에 링크.
