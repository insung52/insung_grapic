# ✅ 해결됨 — Blender→Unreal 본 스케일 100배 버그 (바퀴 서스펜션 원점 붕괴의 진짜 원인)

**2026-07-16 확정.** 0차 목표(intro.md)에서 시작된 "바퀴 서스펜션이 차체 중앙 한 점에 몰리는"
버그의 최종 근본 원인과 검증된 해결 절차. **다음에 디자인팀 실제 UGV 모델로 작업할 때 반드시
이 절차를 그대로 적용할 것.**

---

## 근본 원인

Blender의 FBX exporter에 잘 알려진 버그가 있다: **아마추어(스켈레톤)의 바인드 포즈를 구성하는
"transform link matrix"에 원인 불명의 ×100 스케일이 자동으로 끼어든다.** 이게 Unreal에서
**Root 본의 Scale이 100으로 잘못 들어가는** 형태로 나타난다.

이게 무서운 이유: **월드 스페이스 위치는 정상으로 보인다.**
```
World = ParentWorldTransform(Scale=100 포함) × LocalTransform
```
Root의 스케일이 100이면, 자식 본(바퀴)의 Local 값이 원래보다 100배 작게 들어가 있어도
World 계산 시 그 100배가 다시 곱해져서 **결과적으로 월드 좌표는 우연히 맞아떨어진다.**
그래서 에디터 뷰포트, Physics Asset Editor의 바디 배치, 렌더링된 메시 — 전부 눈으로 보기엔
멀쩡했다.

문제는 **Chaos Vehicle의 `LocateBoneOffset()`가 정확히 이 상황에서 깨진다는 것**:
```cpp
FVector LocalBonePosition = RootBodyMTX.InverseTransformPosition(BonePosition);
```
`RootBodyMTX`(Root 본의 컴포즈드 트랜스폼)에 Scale=100이 섞여있으면, 이 역행렬 변환이
World 좌표를 다시 100으로 나눠버린다. 그 결과 바퀴 4개의 서스펜션 계산 위치가 전부
원래 값의 1/100 크기로 줄어들어 사실상 원점 근처(차체 중앙)에 뭉치게 된다 — 겪었던
증상 그대로.

**진단 방법(이번에 발견한 결정적 체크)**: Unreal Skeleton Editor에서 Root의 직계 자식 본을
선택해 **World 좌표와 Local(부모 기준) 좌표를 비교**한다. Root가 identity transform이라면
이 둘은 반드시 같아야 한다. **다르다면(예: World=50, Local=0.5) 이 버그가 발생한 것이다.**
Root 본 자체의 Scale 값을 직접 확인해도 된다 — 1이어야 정상, 100이면 이 버그.

---

## 검증된 해결 절차 (Blender에서, export 직전에)

커뮤니티에 알려진 워크어라운드([Blender addons #47043](https://projects.blender.org/blender/blender-addons/issues/47043),
UE 포럼 다수)를 그대로 적용해서 실제로 해결 확인함:

1. **아마추어 오브젝트 + 스킨된 메시 오브젝트 전부 선택**
2. **Scale을 (100, 100, 100)으로 설정 → Apply(굽기)**
   - Blender: `Object > Apply > Scale`, 또는 `bpy.ops.object.transform_apply(scale=True)`
   - 이 시점에 본 rest position이 실제 좌표값으로 100배 커져서 구워짐(예: 0.5 → 50)
3. **같은 오브젝트들의 Scale을 다시 (0.01, 0.01, 0.01)로 설정 — 이번엔 Apply하지 않고
   그대로 남겨둔다** (오브젝트 트랜스폼에 0.01이 살아있는 상태로 export)
4. 이 상태로 FBX export. 확인된 export 옵션 조합:
   - `apply_unit_scale=True`
   - `bake_space_transform=True`
   - `use_armature_deform_only=True`
   - `add_leaf_bones=False`
   - `axis_forward='-Y'`, `axis_up='Z'`
   - (`primary_bone_axis`/`secondary_bone_axis`는 명시적으로 지정하지 않음 — Blender
     기본값 사용. 명시 지정 시 본 로컬 축이 회전 변환을 거치면서 다른 문제와 섞일 수 있어서
     제외함. 축 방향 자체가 올바른지는 별도 확인 필요, 아래 "남은 확인 사항" 참고)

**결과**: Root 본 Scale = 1로 정상, World/Local 좌표 일치, 바퀴 서스펜션 정상 작동 확인됨
(사용자 직접 확인 완료).

---

## 부가 확인된 사항

- **Armature 오브젝트 이름**: "Armature"(기본값) 대신 **"root"로 이름을 바꿔서** export.
  이름을 바꾸지 않으면 FBX export 시 스케일이 깨진다는 커뮤니티 보고([grifnmore.com
  가이드](https://grifnmore.com/blender-to-ue-armature-fbx-export-steps/))가 있어 적용함.
  다만 이번 해결에서 **100배 bake+0.01 잔여 스케일 트릭이 핵심**이었고, 이름 변경이 별도로
  얼마나 기여했는지는 명확히 분리 검증 못함 — 안전하게 둘 다 유지 권장.
- **본 계층 단순화**: Root(wrapper, FBX export가 자동으로 Armature 오브젝트를 본으로
  변환해서 삽입함 — 이건 불가피한 구조, 04번 문서 참고) → 바퀴 4개 직속. 차체 메시는
  이 Root(wrapper)에 직접 스킨(버텍스 그룹 이름을 Armature 오브젝트 이름과 일치시킴).
  중간에 별도 "차체 전용 본"을 끼워넣을 필요 없음 — 오히려 혼란만 가중됨(경험함).

## ✅ 후속 해결 (2026-07-19) — Root 직계 자식 본들의 회전 어긋남 (Primary/Secondary Bone Axis)

**증상**: 위 스케일 버그와는 별개로, 언리얼 Skeleton Editor에서 Root의 **직계 자식** 본들
(디자인팀 실제 UGV 모델 기준 `Hull1`, `L_WheelTrack_01~08`, `R_WheelTrack_01~08` 등)을
선택하면 Details 패널의 Rotation 값이 identity(0,0,0)가 아니었다. **메시 렌더링/스킨은
완전히 정상으로 보였다** — 이게 함정이었다. 부모(합성된 root 래퍼 본)와 자식이 서로 회전을
상쇄해서 최종 월드 트랜스폼만 맞춰져 있고, 각 본의 **로컬(부모 기준) 회전값 자체는 어긋나
있었다.** `WheelSetups`가 읽는 값이나 Chaos Vehicle 내부 계산 다수가 본의 로컬/본-스페이스
데이터를 직접 참조하기 때문에, 겉보기엔(메시·좌표 다 정상) 문제가 없어 보여도 실제 서스펜션/
바퀴 회전축 계산에 영향을 준다. **`get_bounds`처럼 월드 스페이스 결과만 보는 진단으로는
이 버그를 절대 못 잡는다** — 반드시 Skeleton Editor Details 패널에서 본별 Rotation 수치를
직접 확인할 것.

**근본 원인**: 이 UGV 아마추어는 (다른 대부분의 리그와 달리) **단일 Root 본이 없고, 서로
부모가 없는 최상위 본이 17개**(`Hull` + `L_WheelTrack_01~08` + `R_WheelTrack_01~08`)
존재하는 구조다. FBX/언리얼은 스켈레톤에 본이 하나만 있어야 하므로, **언리얼의 FBX
임포터가 이 다중 최상위 본 구조를 감싸는 가상의 "root" 래퍼 본을 자동 합성**한다. 이
합성 과정에서 **정확히 요구되는 회전 변환은 export 시 지정한 `axis_forward`/`axis_up`이나
바퀴 개수/구조와 무관하게, 오직 `primary_bone_axis`/`secondary_bone_axis` 값에만 좌우되는
고정 오프셋**이 끼어든다는 게 실증으로 확인됨(Blender 자체 재-import 왕복 테스트로 FBX
파일 자체엔 이상이 없다는 것도 별도 확인함 — 순수하게 **언리얼 임포터 쪽**의 동작).

**실증 데이터** (모두 `axis_forward='-Y'`, `axis_up='Z'`, `bake_space_transform=True` 고정,
`primary_bone_axis`/`secondary_bone_axis`만 변경):
- `primary_bone_axis`/`secondary_bone_axis` 미지정(=Blender 기본값 Y/X): Root 직계 자식
  Rotation = **(Roll=90, Pitch=0, Yaw=0)**
- `primary_bone_axis='X'`, `secondary_bone_axis='-Y'`: Rotation = **(Roll=0, Pitch=90, Yaw=-90)**
- 위 두 값으로부터 "Roll=90 오프셋을 상쇄하려면 X축 기준 -90도 회전이 필요"를 역산 →
  `primary_bone_axis='Z'`, `secondary_bone_axis='X'`로 계산 → **실제 디자인팀 UGV 모델에
  적용해서 Root 직계 자식 Rotation이 (0,0,0)으로 정상화됨을 확인 완료 (사용자 직접 확인).**

**검증된 최종 export 옵션 조합** (스케일 버그 회피 절차와 함께 적용):
```python
bpy.ops.export_scene.fbx(
    filepath=...,
    use_selection=True,
    apply_unit_scale=True,
    bake_space_transform=True,
    add_leaf_bones=False,
    axis_forward='-Y',
    axis_up='Z',
    primary_bone_axis='Z',      # ← 이번에 확정
    secondary_bone_axis='X',    # ← 이번에 확정
    bake_anim=False,
)
```

**주의**: 이 `primary_bone_axis='Z'`/`secondary_bone_axis='X'` 값은 **이번 UGV 아마추어의
"다중 독립 최상위 본" 구조에서 실증적으로 역산된 값**이라, 만약 다른 리그가 이미 단일 Root
본을 갖고 있어서 언리얼이 래퍼 본을 합성할 필요가 없는 구조라면 이 특정 값이 그대로
적용되지 않을 수 있다. 그 경우 이번과 같은 방식(기본값으로 export → Root 직계 자식 Rotation
수치 확인 → 상쇄에 필요한 축 계산 → 검증)으로 다시 역산할 것.

## 남은 확인 사항 (다음 단계)

- 이 워크어라운드(스케일+회전 둘 다)가 **디자인팀이 만든 실제 UGV 모델**에 적용되어 정상
  작동함을 확인 완료 (2026-07-19) — 더 이상 "확인 필요" 항목 아님.
- 바퀴가 실제로 굴러가는 애니메이션(회전 방향/축)까지 최종 확인은 여전히 권장.
