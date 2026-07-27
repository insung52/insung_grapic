# UGV NavMesh 기반 자율주행 구현 — kadex_demo_0716 레벨 (2026-07-24~)

## 0. 목표

`kadex_demo_0716` 레벨에서 `BP_UGV_Vehicle`(실제 사용 중인 UGV — `BP_UGVFromTank`/`BP_UGVChaosPawn`/구 `AUGVPawn` 계열은 전부 예전 테스트용 프로토타입, 이 레벨 기준으로는 무관)이 **도로를 우선으로 NavMesh 자율주행**하도록 만드는 작업. 전체 흐름:

1. **(완료, 이 문서의 1절)** 레벨의 도로 콜리전 활성화 — 이게 안 되어 있으면 NavMesh가 도로 표면을 제대로 인식 못 하고, UGV도 도로 위에서 붕 뜨거나 파고듦.
2. **(예정, 2절에 추후 추가)** 도로 스플라인을 추적해서 NavMesh 가중치 볼륨(`NavModifierVolume`, `AreaClass = NavArea_Road`) 배치 — 옛 프로젝트(`ugv_driving_dev_guide.md` 10절)에서 다른(더 단순한) 지형에 했던 것과 같은 접근을 이 레벨의 실제 Datasmith 도로망에 적용.
3. **(예정)** NavMesh Supported Agents에 UGV용 에이전트 등록, 실제 자율주행 테스트 및 경로 추종 검증.

작업은 전부 `unreal-mcp`(에디터에 붙는 MCP 서버) 스크립트/툴 호출로 진행 — C++ 리빌드 없이 에디터에서 바로 반영·저장.

---

## 1. 1단계 — 도로 콜리전 활성화

### 1.1 증상

레벨의 모든 도로(시가지 내부 도로 + 숲으로 이어지는 산길 도로 전부)에 **콜리전이 전혀 없었음**. `bodyInstance.collisionEnabled`는 인스턴스마다 `QueryAndPhysics`로 정상 표시되는데도, 피직스 켠 액터를 떨어뜨려보거나 Alt+C(플레이어 콜리전 보기)로 확인하면 실제로는 그냥 통과함. 시가지 도로는 지형과 높이차가 적어 티가 잘 안 났지만, 지형 위로 솟은 산길 도로는 눈에 띄게 뚫림.

### 1.2 원인

`bodyInstance.collisionEnabled`는 "이 콜리전을 어떤 용도로 켤지"를 정하는 스위치일 뿐이고, **실제 부딪힐 지오메트리(`BodySetup.AggGeom`, 단순 콜리전)가 완전히 비어있었음** — sphere/box/convex/sphyl 전부 0개. Datasmith 임포트가 단순 콜리전을 자동 생성해주지 않는 게 근본 원인. 나나이트 on/off는 이번 조사에서 무관한 것으로 확인됨(둘 다 AggGeom이 비어있었음) — 예전에 나나이트를 껐을 때 콜리전이 됐던 기억은 아마 그때 우연히 다른 요인(재임포트 등)으로 단순 콜리전이 생겼다가 이후 다시 사라진 것으로 추정.

### 1.3 대상 메시 — 11개

`/Game/Data_Smith/` 아래, 레벨 전체 도로가 재사용하는 스태틱 메시 에셋 11개 (전부 콜리전 없었음):

```
/Game/Data_Smith/d_road_02/Geometries/d_road_02        (나나이트 ON — 산길/숲 도로, Landscape Spline 160개 세그먼트가 재사용)
/Game/Data_Smith/d_road_02/Geometries/d_road_03        (나나이트 ON — 위 폴더 안에 있는 별도 변형)
/Game/Data_Smith/d_road_03/Geometries/d_road_03        (나나이트 OFF, 55개 세그먼트)
/Game/Data_Smith/d_road_03/Geometries/d_road_03_m_01   (나나이트 OFF, 6개 세그먼트)
/Game/Data_Smith/d_road_03/Geometries/d_road_03_m_02   (나나이트 OFF, 3개 세그먼트)
/Game/Data_Smith/d_road_06/Geometries/d_road_06        (나나이트 OFF, 29개 세그먼트)
/Game/Data_Smith/d_road_07/Geometries/d_road_07        (나나이트 OFF — 개별 배치 도로 타일)
/Game/Data_Smith/d_road_09/Geometries/d_road_09        (나나이트 OFF — 개별 배치 도로 타일)
/Game/Data_Smith/d_road_04/Geometries/d_road_04        (나나이트 OFF)
/Game/Data_Smith/d_road_05/Geometries/d_road_05        (나나이트 OFF)
/Game/Data_Smith/road/Geometries/road                  (나나이트 OFF — 시가지 도로 통짜 메시)
```

`d_road_02`(160개 세그먼트, 나나이트 ON)가 지형 위로 솟은 산길/숲 도로의 핵심 메시. `Landscape_0` 액터의 `LandscapeSplinesComponent_3` 아래 총 253개 `SplineMeshComponent`가 이 계열 메시들(`d_road_02`/`d_road_03`/`d_road_06`)을 스플라인에 맞춰 배치한 것 — 이게 옛 문서(`ugv_driving_dev_guide.md` 10.3절)가 다뤘던 "Landscape 스플라인 도로 148개" 시스템과 정확히 같은 구조(세그먼트 개수만 다름).

### 1.4 적용한 수정

**(1) 각 메시에 컨벡스 헐 콜리전 생성** — `StaticMeshTools.generate_convex_collisions` (hull_count=6, max_hull_verts=32, hull_precision=100000) 11개 전부에 적용. 우선 이걸로 "콜리전이 아예 없는" 상태는 해결됨.

**(2) `CollisionTraceFlag`를 `CTF_UseComplexAsSimple`로 변경** — 스플라인 도로는 `SplineMeshComponent`가 스플라인을 따라 정점 단위로 구부러지는데, (1)에서 만든 컨벡스 헐은 세그먼트 양 끝 두 단면에만 정점이 있어서 구부러짐이 "시작→끝을 잇는 직선"으로만 근사됨. 실제 렌더 메시(정점 단위로 정확히 구부러짐)를 그대로 콜리전으로 쓰게 하면 이 부분이 나아질 거라 기대하고 적용.

**결과**: (1)은 유효했음(콜리전 자체는 생김). (2)는 **효과 없었음** — 1.5절 참고, 이유가 따로 있었음.

적용은 `ProgrammaticToolset.execute_tool_script`로 11개 메시를 한 번에 순회 처리. 예시 스크립트 골격:

```python
def run():
    mesh_paths = [ ... 위 11개 경로 ... ]
    for path in mesh_paths:
        mesh = {"refPath": f"{path}.{path.split('/')[-1]}"}
        execute_tool("editor_toolset.toolsets.static_mesh.StaticMeshTools.generate_convex_collisions",
                      json.dumps({"mesh": mesh, "hull_count": 6, "max_hull_verts": 32, "hull_precision": 100000}))
        body = execute_tool("editor_toolset.toolsets.object.ObjectTools.get_properties",
                             json.dumps({"instance": mesh, "properties": ["bodySetup"]}))
        # body_ref = 파싱해서 bodySetup.refPath 사용 (BodySetup_0/1 등 인덱스가 메시마다 다름 — "bodySetup" 프로퍼티로 조회해야 정확함, ":BodySetup_0"으로 하드코딩하면 일부 메시에서 실패함)
        execute_tool("editor_toolset.toolsets.object.ObjectTools.set_properties",
                      json.dumps({"instance": body_ref, "values": json.dumps({"collisionTraceFlag": "CTF_UseComplexAsSimple"})}))
```

**주의**: `BodySetup` 서브오브젝트 이름이 메시마다 다름(`BodySetup_0`, `BodySetup_1` 등) — `StaticMesh.bodySetup` 프로퍼티로 실제 경로를 조회해서 써야 함. 하드코딩하면 일부(`d_road_03`, `d_road_03_m_01`, `d_road_03_m_02`)에서 "not valid Object" 에러 남.

**퍼포스**: 에셋 수정 후 `save_assets`는 해당 파일들이 체크아웃되어 있어야 성공함(`false` 리턴 시 체크아웃 안 된 상태). 이번엔 11개 다 사용자가 수동으로 체크아웃한 뒤 저장 성공.

### 1.5 알려진 한계 — 세그먼트 내부 진행방향 굴곡 미표현

**증상**: 산길 도로 세그먼트 하나 안에서, 지형이 오목/볼록해도 도로 표면은 항상 "시작 단면 → 끝 단면을 잇는 매끈한 하나의 면"으로만 보임. 1.4절 (2)를 적용해도 변화 없음.

**원인**: 콜리전 방식 문제가 아니라 **베이스 메시 자체가 길이 방향으로 정점을 딱 2줄(시작 단면, 끝 단면)만 가지고 있음** — (1)에서 생성된 컨벡스 헐의 정점 좌표를 찍어보면 전부 로컬 X = ±249.19 두 값만 나옴(중간 정점 없음). `SplineMeshComponent`가 정점 단위로 스플라인을 따라 구부리긴 하지만, 구부릴 정점 자체가 양 끝뿐이라 결과는 항상 두 단면을 잇는 매끈한 면 하나 — 렌더 메시도, (2)로 바꾼 콤플렉스 콜리전도 결국 같은 지오메트리라 똑같이 안 나옴.

즉 **콜리전 세팅으로는 해결 불가** — 지오메트리(또는 세그먼트 밀도) 자체를 바꿔야 함.

### 1.6 개선 방법 (지금은 보류 — 나중에 요청 오면 진행)

도로가 그렇게 복잡하지 않아서 지금 당장은 문제 없음. 나중에 수정 요청이 오면 아래 방향으로:

- **A) 스플라인 세그먼트를 더 잘게 쪼개기 (스크립트로 가능, 권장)** — `LandscapeSplinesComponent`의 컨트롤 커브를 더 촘촘한 간격으로 리샘플링해서, 지금보다 짧고 많은 `SplineMeshComponent`로 재배치. 메시 자체는 안 건드리고 배치 밀도만 높이는 거라 MCP 스크립트로 처리 가능. 세그먼트 수가 (촘촘함 정도에 따라) 160개에서 수백~천 단위로 늘어날 수 있음 — 늘어난 만큼 1.4절의 콜리전 생성도 다시 돌려야 함(혹은 새 인스턴스가 같은 메시 에셋을 재사용하면 자동으로 적용됨, 메시가 안 바뀌므로).
- **B) 메시 자체에 길이 방향 중간 루프(정점) 추가** — 진짜 도로 표면에 굴곡을 새기려면 메시를 다시 손봐야 함. 정점 단위 편집이라 현재 MCP `StaticMeshTools`로는 불가능 — Blender/3ds Max 등 DCC 툴에서 리토폴로지 후 재임포트 필요.

---

## 2. 2단계 — NavMesh 가중치 볼륨 배치 (완료, 2026-07-24)

### 2.1 목표

도로 중심선을 따라 이어지는 `NavModifierVolume`(`AreaClass = NavArea_Road`, 1절에서 이미 확인한 그 클래스)을 배치해서, NavMesh가 도로를 우선 선호하도록 만듦. 이번 작업 범위는 **NavMesh Bounds Volume 구역 확정과 무관하게, Landscape 스플라인 도로 전체(253개 세그먼트)에 볼륨을 깔고 사용자가 눈으로 배치 상태를 확인하는 것까지**.

### 2.2 방식 — `ugv_driving_dev_guide.md` 10.3절과 동일한 접근

`Landscape_0.LandscapeSplinesComponent_3` 아래 253개 `SplineMeshComponent`(1절에서 콜리전 붙인 그 도로들) 각각에 대해:

1. `SplineMeshComponent.SplineParams.StartPos/EndPos`(컴포넌트 로컬 좌표) → 월드 좌표 변환: `WorldPos = Landscape액터위치 + 컴포넌트RelativeLocation + StartPos/EndPos`. `LandscapeSplinesComponent`의 0.01 보정 스케일과 Landscape `DrawScale`(100)이 상쇄되어 순배율 1.0이고, 컴포넌트 자신의 `RelativeRotation`/`RelativeScale3D`도 항등이라 단순 덧셈으로 충분함(직접 값 확인해서 검증함).
2. 세그먼트 진행방향(시작→끝 벡터)으로 Yaw 계산, 중점(Z는 살짝 위로 오프셋)에 배치.
3. 세그먼트 길이 = 볼륨의 Scale.X (기본 큐브 브러시가 200×200×200이라 `Scale = 실제크기/200`).
4. `NavModifierVolume` 스폰 → `AreaClass = NavArea_Road` 지정 → `BrushComponent`에 `RoadSurface` 태그 부착 + 콜리전을 `QueryOnly`/`GameTraceChannel1만 Overlap`(`WorldStatic`은 `Ignore`)으로 세팅. 이 콜리전 세팅이 없으면 `AUGVAIController::UpdateOffRoadSpeedDecay`/`UpdateRoadBoundary`의 지면 판정용 `ECC_WorldStatic` 라인트레이스를 볼륨 박스 자체가 가로막아버림 — `ugv_driving_dev_guide.md` 13.2절에서 이미 겪었던 함정과 동일해서 처음부터 반영.
5. 아웃라이너에서 구분하기 쉽도록 라벨을 `RoadNavMod_Mountain_N`(산길, `d_road_02` 메시 세그먼트 160개) / `RoadNavMod_City_N`(시가지, 나머지 93개)으로 분리.

전부 `unreal-mcp`의 `ProgrammaticToolset.execute_tool_script`(파이썬 스크립트를 서버 쪽에서 실행, 개별 툴 호출을 수백 번 왕복 없이 한 번에 처리)로 진행.

### 2.3 폭/높이 튜닝 — 시행착오

- **1차**: 세그먼트별 실제 메시 폭(`StaticMeshTools.get_bounds`의 로컬 Y 범위 × `SplineParams.StartScale`) 기준으로 산길은 1/3, 시가지는 1/4 비율의 "좁은 중심 스트립" 폭 계산. 산길은 높이(Z스케일)도 2→10으로 키움(급경사 구간 대비, `ugv_driving_dev_guide.md` 10.6절에서 예견했던 문제).
- **버그 발생**: 산길 볼륨 폭/높이만 부분 수정하려고 `set_actor_transform`에 `{"scale": ...}`만 넘기고 `location`/`rotation`을 안 넘겼는데, 툴 문서상 "안 넘긴 필드는 유지"라고 되어 있음에도 실제로는 world space에서 안 넘긴 필드가 0으로 덮어써지는 버그성 동작이 있었음 → 산길 볼륨 160개 전부 원점(0,0,0)으로 이동해버림.
- **대응**: 부분 수정 대신 기존 볼륨 전체 삭제 후 처음부터 다시 스폰하는 방식으로 스크립트를 재작성(2.4절 스크립트가 그 버전) — 이 문제 자체가 재발 안 하는 구조. **교훈: 이 MCP 환경에서 기존 액터의 트랜스폼을 일부만 바꾸고 싶어도, 항상 현재 위치/회전/스케일 셋 다 채워서 `set_actor_transform`을 호출할 것 (또는 아예 삭제 후 재생성).**
- **2차 (최종)**: 사용자가 에디터에서 직접 눈으로 확인한 뒤, 세그먼트별 비율 계산 대신 **전 구간(산길/시가지 구분 없이) Y스케일(폭) 고정값 0.5**로 통일 — 세그먼트마다 메시 스케일이 달라 비율 계산 폭이 들쭉날쭉했던 것으로 추정. 이 값은 사용자가 언리얼 에디터에서 직접 적용함(스크립트 재실행 안 함). 높이는 산길 2000cm(Z스케일 10)/시가지 400cm(Z스케일 2) 구분 그대로 유지.

### 2.4 재사용 가능한 스크립트

**정본(팀 공유용, 2026-07-24부터)**: `titan_example` 프로젝트 안 `Tools\unreal-mcp\place_road_navmod_volumes.py` (같은 폴더 `README.md`에 실행법 정리) — 퍼포스로 관리되는 프로젝트 안에 넣어서 다른 사용자도 바로 찾아 쓸 수 있게 함. 2.3절 최종(고정 폭 0.5) 버전. (이 문서 폴더에 있던 초기 사본은 정리됨 — 이 경로 하나만 유지.)

`ProgrammaticToolset.execute_tool_script`에 파일 내용을 그대로 붙여넣어 실행. 재실행하면 기존 `NavModifierVolume`을 전부 지우고 처음부터 다시 배치함(1절의 도로 콜리전과 달리, 이 볼륨들은 에셋이 아니라 레벨에 배치된 액터라 별도 체크아웃/저장 없이 레벨 저장만 하면 됨).

폭/높이를 다시 튜닝하고 싶으면 파일 상단의 `FIXED_WIDTH_SCALE`/`HEIGHT_MOUNTAIN`/`HEIGHT_CITY` 상수만 고치고 재실행.

### 2.5 결과

253개 전부 에러 없이 생성, 항공샷으로 산길 커브 구간 확인 결과 도로 중심선을 잘 따라감 (사용자 육안 확인 완료). NavMesh Bounds Volume 구역이 아직 안 정해진 상태라 실제 경로탐색/자율주행 테스트는 3단계로 남겨둠.

**추가(2026-07-24)**: 사용자가 실제로 `Build Paths` 후 `P`키로 내비메시 시각화 확인 — `BP_UGV_Vehicle` 밑에 깔리는 내비메시가 검은색(`Tank` 에이전트, 프로젝트 세팅에 반경 200cm로 등록되어 있던 그 값)으로 나와서, **UGV가 실제로 Tank 크기 에이전트로 길찾기하고 있음을 확인함.** (이 확인 전엔 `BP_UGV_Vehicle`에 `NavAgentProperties`류 필드 자체가 리플렉션에 없어서 Default(34cm) 에이전트로 새는 게 아닌지 의심했었는데, 실제로는 정상이었음 — 아마 프로젝트가 등록된 `SupportedAgents` 중 하나만 있으면 그걸 기본으로 잡는 식으로 동작하는 듯. 정확한 내부 동작은 미확인이지만 결과는 확인됨.)

### 2.6 실주행 테스트 중 발견된 콜리전 버그 2건 (2026-07-24)

2.5절 확인 후 사용자가 실제 자율주행을 테스트하다가 발견한 버그 둘 — 둘 다 `RoadNavMod` 볼륨의 `BrushComponent` 콜리전 설정 문제였고, 2.4절 스크립트에 전부 반영 완료.

**버그 A — 맵 이탈 방지 로직 폭주 (UGV가 Play 시작하자마자 계속 위로 텔레포트)**

증상: Play 시작하자마자 매 틱 "지정 구역을 벗어났습니다" 뜨면서 UGV가 X/Y는 고정인 채 Z만 계속 상승. 처음엔 `AUGVAIController::MaxRoadDistance`(400m) 값 문제이거나, `UpdateRoadBoundary`의 지면 재트레이스가 UGV 자기 자신의 메시를 맞혀서 그 위에 클리어런스만큼씩 계속 쌓이는 거라고 추정했었음 — **틀림**. 사용자가 "애초에 도로 400m 안에 있는데 왜 처음부터 텔레포트되냐", "한 번 텔레포트하면 도로와 거리가 0에 가까워지는데 왜 계속 재발동하냐"고 반박했고, 실제 원인은 따로 있었음:

- 원인: 2.4절에서 `BrushComponent.BodyInstance`에 `CollisionEnabled`/`CollisionResponses`만 개별로 `set_properties`로 덮어썼는데, **`CollisionProfileName`을 `"Custom"`으로 안 바꿔서** 언리얼이 `NavModifierVolume`의 기본 프로파일(`"NoCollision"`)을 계속 우선시함 — 개별로 설정한 값은 조용히 무시되고, 볼륨은 런타임에 실제로는 **콜리전이 아예 없는 상태**였음.
- 그 결과: `UpdateRoadBoundary`가 `GetClosestPointOnCollision`으로 "도로까지 거리"를 재는데, 253개 볼륨 전부 콜리전이 없으니 전부 실패 → `BestDistance`가 초기값(사실상 무한대)에서 안 바뀜 → **실제 거리와 무관하게 매 틱 "400m 초과"로 오판**. 거리 계산 자체가 실제 위치를 안 보므로, 텔레포트를 아무리 해도 다음 틱에 똑같이 재발동. 이게 "처음부터 발동"과 "텔레포트해도 계속 재발동" 둘 다 설명함.
- Z만 계속 오르는 이유: 거리 계산이 실패하면 `BestPoint`가 "현재 위치 그대로"로 폴백되고, 그 지점에서 지면 재트레이스를 하는데 `RoadVolumeIgnoreParams`에 UGV 자신이 안 빠져있어서 자기 메시를 맞혀 클리어런스(50cm)만큼씩 매 틱 위로 쌓인 것 — 이건 부차적 증폭 원인.
- **해결**: 253개 볼륨의 `CollisionProfileName`을 `"Custom"`으로 명시 설정. PIE로 재확인 — UGV가 지면(Z≈-3579)에 그대로 안정적으로 있고 더 이상 안 뜸.
- **아직 안 고친 부차적 버그**: `RoadVolumeIgnoreParams`가 `ControlledPawn`(UGV 자신)을 무시 목록에 안 넣는 문제는 남아있음 — 근본 원인이 고쳐져서 지금은 안 드러나지만, 실제로 도로 이탈 텔레포트가 진짜로 발동하는 상황(맵 경계 밖으로 실수로 벗어났을 때 등)에서 자기 메시를 맞히는 문제가 재발할 수 있음. C++ 수정 필요 (`UpdateRoadBoundary`에서 지면 재트레이스용 `QueryParams`에 `ControlledPawn` 추가) — **미적용, 다음에 처리**.

**버그 B — 볼륨 콜리전을 고치니 이번엔 UGV가 물리적으로 부딪힘**

버그 A를 고쳐서 볼륨 콜리전이 실제로 켜지자, UGV가 도로 위를 달릴 때 볼륨 자체에 물리적으로 부딪히는 문제 발생.

- 원인 추정: `Custom` 콜리전 프로파일에서 명시적으로 설정 안 한 채널은 기본 Block으로 해석되는 것으로 보임. 기존엔 `WorldStatic`(Ignore)과 `GameTraceChannel1`(Overlap)만 명시했고, Chaos Vehicle의 바퀴 서스펜션 등이 실제로 쓰는 다른 채널(`Vehicle`/`PhysicsBody`/`Pawn` 등, 정확히 어느 채널인지는 미확인)은 그대로 Block으로 남아있었던 것으로 추정.
- **해결**: 차량이 실제로 쓸 만한 채널 전부(`WorldStatic`/`WorldDynamic`/`Pawn`/`Visibility`/`Camera`/`PhysicsBody`/`Vehicle`/`Destructible`)를 명시적으로 Ignore로 깔고, `GameTraceChannel1`(온로드 판정 전용)만 Overlap으로 유지. 253개 전부 반영 완료, 스크립트도 갱신.

## 3. 3단계 — 자율주행 테스트 마무리 (진행 중)

남은 항목:
- [ ] 버그 A의 부차적 원인(`RoadVolumeIgnoreParams`에 `ControlledPawn` 미포함) C++ 수정
- [ ] 실제 자율주행 시나리오 전체 경로 테스트 (사용자 진행 중)
- [ ] `ChaosFromTank`/구 UGV(`AUGVPawn`, `BP_UGVFromTank`, `AUGVChaosPawn` 등) 관련 미사용 코드/에셋 정리 — 별도 작업으로 예정 (`BP_UGVAIController`는 이미 `/Game/UGV/Blueprint/`로 이동 완료, 남은 `Vehicles/UGV` 폴더는 `UGV_OLD`로 개명됨)

*(추후 작업 후 이 절에 정리 예정)*

