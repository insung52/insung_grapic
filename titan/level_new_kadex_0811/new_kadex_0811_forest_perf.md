# New_kadex_0811 PIE 성능 폭락 — 원인과 해결 (2026-08-22)

## 요약

- **증상**: `New_kadex_0811` 레벨에서 PIE를 켜면 **2~3fps**. 시간이 지나면 30fps대로 "복구"되는 것처럼 보임.
- **원인**: SplineForest PCG가 뿌린 나무/식물 ISM 17개(총 58,400 인스턴스)에 `WorldPositionOffsetDisableDistance = 0`이 걸려 있어, **거리와 무관하게 전 인스턴스가 매 프레임 WPO(바람 흔들림) 정점 연산**을 돌고 있었음. 프로젝트 Nanite가 꺼져 있고(`r.Nanite.ProjectEnabled=False`) 인스턴스가 Movable이라 VSM 캐시도 전혀 못 씀.
- **2차 원인**: 자작나무 `SM_BHF_BirchTreeA`(LOD0 **105,913 tris**, 12,929 인스턴스)의 LOD 전환 거리가 너무 멀어서 근~중거리 전부가 고폴리 LOD로 렌더됨.
- **해결**: `WorldPositionOffsetDisableDistance = 3000`(30m) + 자작나무에만 `InstanceLODDistanceScale = 0.5`. **2.3fps → 31fps (13.5배)**.
- **"시간 지나면 복구"는 착시**: 자발적 회복이 아니라 **시야에서 숲이 빠질 때**(UGV 자율주행 완료로 트인 곳 도착, `ToggleDebugCamera`) 올라간 것. 숲을 정면으로 보는 동안은 2.3~2.6fps가 평평하게 유지됨(최장 1,467초 세션 내내 2.4~3.0).
- **나나이트는 답이 아니었음**: 이 레벨에서 나나이트가 켜진 유일한 나무(소나무)를 통째로 지워도 **2~3fps**밖에 안 오름. 근거는 아래 "나나이트 전수 조사".

---

## 증상

- PIE 시작 직후부터 **2.3~2.6fps**(약 420ms/frame), 몇 분이고 평평하게 유지
- 에디터 뷰포트(PIE 전)는 같은 씬에서 63fps
- RTSP 스트림 5개(UGV CCTV×4 + RCWS 1920x1080)가 켜진 상태였으나 **RTSP는 주범 아님**(아래 배제 참고)

---

## 측정 방법 — 로그 프레임 카운터로 fps 재기

unreal-mcp 툴셋에는 콘솔 명령 실행 툴이 없다(`SearchCVars`는 읽기 전용). 대신 **로그 줄 앞머리의 프레임 카운터**로 fps를 계산했다.

```
[2026.08.22-04.12.14:019][513]LogModelContextProtocol: Running tool: ...
                          ^^^ GFrameCounter % 1000
```

절차:
1. `StartPIE` 후 `IsPIERunning`을 2초 간격으로 3~4번 호출 — 각 호출이 로그에 프레임 스탬프를 남김
2. `grep "Running tool" Saved/Logs/titan_example.log | tail` 로 스탬프 수집
3. `(프레임 차) / (시간 차)` = fps

A/B 테스트는 **PIE 월드 오브젝트**(`/Game/UEDPIE_0_New_kadex_0811.New_kadex_0811:PersistentLevel....`)에 `set_properties`로 값을 바꿔가며 수행했다. PIE 종료 시 전부 폐기되므로 실제 에셋은 안전하다.

과거 세션 분석은 `LogWorld: Bringing World /Game/UEDPIE` ~ `BeginTearingDown` 구간을 파싱하면 된다.

---

## 씬 구성 (조사 결과)

레벨 액터 53개, 월드 파티션 미사용, `.umap` **185MB**(PCG 생성 인스턴스 트랜스폼이 직렬화되어 있음).

### SplineForest PCG 액터 5개 / ISM·HISM 17개 / 총 58,400 인스턴스

| 액터 | 인스턴스 | 범위 | PCG 그래프 |
|---|---|---|---|
| `BP_SplineForest_tree_C_1` | **38,589** (자작 12,851 + 자작A 12,929 + 소나무 12,809) | **1.65km × 0.9km** | `PCG_SplineForest_tree2` |
| `BP_SplineForest_tree_C_2` | 274 | 소규모 | `PCG_SplineForest_tree2` |
| `BP_SplineForest_tree2_C_1` | 203 | 소규모 | `PCG_SplineForest_tree2` |
| `BP_SplineForest_plant_C_1` | 10,102 | 고사리·마운틴애시 | `PCG_SplineForest_plant` |
| `BP_SplineForest_plant_C_3` | 9,214 | 고사리·마운틴애시 | `PCG_SplineForest_plant` |

### 문제였던 컴포넌트 설정 (수정 전)

| 항목 | 값 | 문제 |
|---|---|---|
| `WorldPositionOffsetDisableDistance` | **0** (전부) | 거리 무관 전 인스턴스 WPO 연산 — **주범** |
| `InstanceEndCullDistance` | 0(식물, 무한) / 1,000,000(나무, 10km) | 거리 컬링 사실상 없음 |
| `Mobility` | Movable (전부) | VSM 캐시 불가 |
| `bAffectDistanceFieldLighting` / `bAffectDynamicIndirectLighting` | true | DF/Lumen 부하 |

### 메시 스펙

| 메시 | Nanite | LOD | tris | threshold | 인스턴스 |
|---|---|---|---|---|---|
| `SM_BHF_BirchTreeA` | OFF | 5 | **105,913** / 52,957 / 26,479 / 13,240 / 8 | 1.5 / 1.0 / 0.9 / 0.6 / 0.25 | 12,929 |
| `SM_BHF_BirchTreeTinnyA` | OFF | 4 | 7,058 / 3,529 / 1,765 / 4 | 1.0 / 0.75 / 0.5 / 0.125 | 12,851 |
| `SM_Scots_Pine_Forest_02` | **ON** | 5 | 7,069 / **16,070** / 2,530 / 861 / 25 | 1.0 / 0.99 / 0.98 / 0.75 / 0.45 | 12,809 |
| `SM_Pine_Fern_Broad_01` | OFF | 3 | 572 / 189 / 64 | 1.0 / 0.25 / 0.15 | 4,881 |
| `SM_Pine_Fern_Broad_Group_01` | ON | 3 | 1,940 / 641 / 194 | 1.0 / 0.1 / 0.1 | 4,875 |
| `SM_Pine_Fern_Broad_Group_02` | ON | 3 | 1,303 / 430 / 131 | 1.0 / 0.5 / 0.2 | 4,874 |
| `SM_Pine_Mountain_Ash_Medium_01` | ON | 3 | 911 / 301 / 63 | 1.0 / 0.35 / 0.15 | 4,686 |

> **소나무 LOD 역전 주의**: `SM_Scots_Pine_Forest_02`는 Nanite가 켜져 있어 LOD0가 Nanite 폴백 메시(7,069)로 대체되고 원본 LOD1(16,070)이 그대로 남아 **LOD1이 LOD0보다 무겁다**. 프로젝트 Nanite가 꺼져 있어 이 폴백 체인으로 렌더된다. 실사용 구간은 대부분 LOD2/LOD3(2,530/861)라 실측상 문제가 되진 않았다.

---

## 배제된 원인들

| 후보 | 확인 방법 | 결과 |
|---|---|---|
| **RTSP / 씬 캡쳐** | 스트림 5개 전부 켠 채로 숲만 숨김 | **배제** — 2.3 → 48~58fps. RTSP가 붙어 있어도 숲만 없으면 정상 |
| **지형(랜드스케이프) 텍스쳐** | `MI_GlacierValley` 텍스처 파라미터 전수 확인 | **배제** — 2K 텍스처 8장(4레이어 × BaseColor/Normal)뿐. VRAM/샘플 부하 아님 |
| **랜드스케이프 그래스(풀)** | `GT_*` 5종 GrassVariety 전수 확인 | **배제** — `GT_Ground`/`GT_MidHigh`는 `grassMesh=None`, `GT_MidLow`는 `grassDensity=0`, `GT_Cliff`/`GT_Snow`는 variety 없음. **실제로 생성되는 풀이 하나도 없음** |
| **PCG 생성 비용(PIE 시작 시 재생성)** | `bGenerated` 플래그 + PIE start 시간 | **배제** — 5개 전부 `GenerateOnLoad`지만 `bGenerated=true`라 재생성 안 함. PIE start 1.0초 |
| **랜드스케이프 Nanite** | `bEnableNanite` 확인 | 해당 없음 — false(일반 LOD 랜드스케이프) |
| **그림자** | 숲 전체 `castShadow=false` | 기여 작음 — 2.3 → 2.9~3.9fps |
| **Titan_Truck 폴리곤(983,577 tris)** | LOD 생성 + `forcedLodModel` 강제 | **배제**(아래 "폐기한 시도" 참고) |

---

## 결정적 증거

### 1. 숲이 전부다

| 조건 | fps |
|---|---|
| 현재 상태 (baseline) | **2.3** |
| SplineForest 5개 액터 전부 숨김 | 48~58 |
| `BP_SplineForest_tree_C_1` **하나만** 숨김 | 54 |

### 2. 숲 비용의 정체는 WPO

| 조건 | fps |
|---|---|
| baseline | 2.3 |
| 그림자만 끔 (WPO 유지) | 2.9~3.9 |
| **WPO 끔** (그림자 유지) | **22~24** |
| WPO 끔 + 그림자도 끔 | 25~28 |
| 거리 컬링 추가 (WPO 고친 상태에서) | 24~26 (효과 미미) |

### 3. WPO DisableDistance 거리별 곡선

| DisableDistance | fps |
|---|---|
| 0 (무제한 = 수정 전) | 2.3 |
| 20000 (200m) | 2.9~3.4 |
| 10000 (100m) | 6.7~7.3 |
| 5000 (50m) | 15.5~17.6 |
| **3000 (30m) ← 채택** | **21.0~22.5** |
| 2000 (20m) | 21~24 |
| WPO 완전 off | 22~24 |

효과가 꺾이는 지점(knee)은 **20~50m 구간**. 200m는 사실상 이득이 없다 — 빽빽한 숲이 200m 안에 다 들어오기 때문.

### 4. 남은 비용은 자작나무 (나나이트가 답이 아닌 이유)

WPO 30m 적용 후(약 21fps) 나무를 종류별로 숨겨서 측정:

| 조건 | 인스턴스 | Nanite | fps |
|---|---|---|---|
| baseline | — | — | 19.7~21 |
| **자작나무만 숨김** (`BirchTreeA` + `TinnyA`) | 25,780 | **OFF** | **29.7~35.8** |
| **소나무만 숨김** (`Scots_Pine_Forest_02`) | 12,976 | **ON** | 22.7~23.2 |

→ **나나이트가 켜진 유일한 나무를 통째로 지워도 2~3fps.** 남은 비용은 거의 전부 자작나무 쪽이고, 자작나무는 `MWPaperBirchForest` 팩(146개 메시 **전부 Nanite OFF**) 소속.

### 5. 자작나무 LOD 배율

`InstanceLODDistanceScale` — 엔진 설명: *"Smaller values make LODs transition earlier."*

| 자작나무 InstanceLODDistanceScale | fps |
|---|---|
| 1.0 (기본) | 21.8 |
| **0.5 ← 채택** | **32.0~32.3** |
| 0.35 | 35.7~36.1 |
| 0.25 | 37.7~38.4 |

소나무/식물에도 0.5를 걸면 오히려 26~30fps로 나빠짐 → **자작나무에만 적용할 것.**

0.5를 채택한 이유: 자작나무 LOD 체인이 `105,913 → 52,957 → 26,479 → 13,240 → 8`로 마지막 단계가 8삼각형 빌보드다. 배율을 낮출수록 이 빌보드 전환이 가까이 당겨져 팝핑이 눈에 띌 수 있다. 화질 확인 후 0.35까지는 올릴 여지가 있다.

---

## 적용한 수정

### (1) WorldPositionOffsetDisableDistance = 3000 (30m)

**적용 위치 2곳** — 둘 다 해야 한다:

| 대상 | 경로 |
|---|---|
| PCG 그래프 (향후 재생성용 기본값) | `PCG_SplineForest_tree2` → `StaticMeshSpawner_0` → MeshSelectorWeighted → `meshEntries[].descriptor` (메시 3종) |
| | `PCG_SplineForest_plant` → `StaticMeshSpawner_3` → 동일 (메시 4종) |
| 레벨의 기존 인스턴스 컴포넌트 | `New_kadex_0811` 의 ISM/HISM **17개** |

> **중요**: 그래프만 고치면 **이미 생성된 인스턴스에는 반영되지 않는다**(`wpo`가 0 그대로). PCG를 강제 재생성하면 58,400개 인스턴스가 다시 뿌려져 숲 배치가 바뀔 위험이 있으므로, 레벨 컴포넌트에 직접 적용하고 그래프는 향후 재생성용 기본값으로 남겨두는 방식을 택했다.

의미: **카메라 기준 30m 안쪽 나무는 평소대로 바람에 흔들리고, 그 밖은 WPO 계산을 끈다(정지).**

### (2) InstanceLODDistanceScale = 0.5 (자작나무 2종에만)

| 대상 | 경로 |
|---|---|
| PCG 그래프 | `PCG_SplineForest_tree2` 의 `SM_BHF_BirchTreeA` / `SM_BHF_BirchTreeTinnyA` 엔트리 (소나무는 1.0 유지) |
| 레벨 컴포넌트 | 자작나무 ISM/HISM **6개** |

공용 메시 에셋(`SM_BHF_BirchTreeA`)의 LOD threshold 자체는 **건드리지 않았다.** 컴포넌트 단 배율이라 다른 레벨/다른 팀 작업에 영향 없이 이 레벨에서만 되돌릴 수 있다.

### 변경된 파일 (P4)

```
Content/New_kadex_0811.umap                          #2 - edit
Content/SplineForest/PCG_SplineForest_plant.uasset   #2 - edit
Content/SplineForest/PCG_SplineForest_tree2.uasset   #1 - edit
```

### 누적 결과

| 단계 | fps |
|---|---|
| 최초 | 2.3 |
| + WPO DisableDistance 30m | 21 |
| + 자작나무 InstanceLODDistanceScale 0.5 | **31** |

---

## 나나이트 전수 조사

디자인팀 결정 사항이라 함부로 못 바꾸는 영역이므로 전체 맥락을 따로 정리한다.

### 프로젝트 전역 설정 — 누가 언제 껐나

```ini
Config/DefaultEngine.ini:34   r.Nanite.ProjectEnabled=False
Config/DefaultEngine.ini:77   bGenerateNaniteFallbackMeshes=False   ; [LinuxTargetSettings]
```

P4 annotate 결과 **둘 다 CL 288 (2026-07-22, user5@DESKTOP-JUNYOUNG)**, 커밋 메시지 *"나나이트, 루멘 off, scalability setting 최적화"*. 같은 사람이 바로 다음 CL 289에서 루멘은 다시 켰지만(`lumen on`) 나나이트는 끈 채로 유지됐다. CL 292에서 `r.Streaming.PoolSize=4096` + `LimitPoolSizeToVRAM=1`로 텍스처 풀 캡을 걸었고, ini 주석에 *"텍스처 풀이 진짜 원인, 나나이트는 마지막 한 방울"*이라고 적혀 있다 — **당시 껐던 전제가 지금은 달라졌을 가능성이 있다.**

같은 CL에서 `Config/Windows/WindowsEngine.ini`도 함께 수정됨: `sg.ShadowQuality=2`, `sg.GlobalIlluminationQuality=1`, `r.Shadow.Virtual.MaxPhysicalPages=1024`(엔진 기본 4096) 등.

### 레벨이 실제로 쓰는 메시 18종

**Nanite ON (4종, 전부 RealBiomes 식생 — 전부 폴백으로 렌더 중, `NaniteFallbackPercent=100.0`)**

| 메시 | Nanite tris | 폴백(LOD0) | 인스턴스 |
|---|---|---|---|
| `SM_Scots_Pine_Forest_02` | 53,511 | 7,069 | 12,976 |
| `SM_Pine_Fern_Broad_Group_01` | 7,982 | 1,940 | 4,875 |
| `SM_Pine_Fern_Broad_Group_02` | 4,811 | 1,303 | 4,874 |
| `SM_Pine_Mountain_Ash_Medium_01` | 2,465 | 911 | 4,686 |

**Nanite OFF (14종)**: 자작나무 2종, `SM_Pine_Fern_Broad_01`, **`Titan_Truck`(983,577 tris, LOD 1개)**, UGV 포탑 4종, 트랙링크, HDRI 돔, Cube/Cylinder, 도로 메시

### Landscape / 풀

- **Landscape**: `bEnableNanite = false`. 일반 LOD 랜드스케이프 (`LOD0ScreenSize=0.5`, `LODDistributionSetting=3`, `MaxLODLevel=-1`)
- **랜드스케이프 그래스**: 실제로 생성되는 게 없음(위 "배제된 원인들" 참고). `GT_MidLow`가 참조만 해둔 `SM_Grass_Forest_03` / `SM_Grass_Generic_Base_01`은 둘 다 Nanite ON
- 화면에 보이는 "풀"은 전부 PCG `BP_SplineForest_plant`가 뿌린 고사리/마운틴애시 ISM

### 프로젝트 전체 분포 (에셋 레지스트리 `NaniteEnabled` 태그 기준, 로드 없이 집계)

| 폴더 | 스태틱메시 | Nanite ON |
|---|---|---|
| `/Game` 전체 | 926 | **233 (25%)** |
| `RealBiomes` | 181 | 98 |
| `MWPaperBirchForest` | 146 | **0** |
| `NGrassPack_1` | 22 | 22 |
| `Data_Smith` (건물/도로) | 53 | 23 |
| `Fab` (메가스캔) | 286 | 6 |
| `Vehicles` | 8 | 1 (`TankX`, 미사용) |

패턴상 **개별 메시의 Nanite 플래그는 대부분 에셋 벤더 기본값**이다 — RealBiomes/NGrassPack은 켜서 배포, MWPaperBirchForest는 꺼서 배포. 메시별로 판단한 흔적은 없고, 실제 프로젝트 결정은 `r.Nanite.ProjectEnabled=False` 한 줄뿐.

### 나나이트를 켠다면 VRAM은?

GPU: **7,895MB (약 8GB)**

**(1) 지오메트리 데이터 — 매우 작다.** 나나이트 데이터는 **인스턴스가 아니라 유니크 메시 단위**라 58,400개를 뿌려도 메시 7종 분량뿐이다.

| 메시 | 나나이트 데이터 |
|---|---|
| `SM_Scots_Pine_Forest_02` | 1.13 MB |
| `SM_Pine_Fern_Broad_Group_01` | 0.17 MB |
| `SM_Pine_Fern_Broad_Group_02` | 0.11 MB |
| `SM_Pine_Mountain_Ash_Medium_01` | 0.04 MB |
| **이 레벨 합계** | **약 1.45 MB** |

자작나무 2종을 추가 변환 시 소나무 비율(약 22 bytes/나나이트 tri)로 환산해 **+3~5MB** 수준. 프로젝트 전체 233개를 다 합쳐도 143.7MB.

**(2) 나나이트 스트리밍 풀 — 이게 진짜 항목이다.**

```
r.Nanite.Streaming.StreamingPoolSize   = 512   (MB, 씬 크기와 무관한 고정 예약)
r.Nanite.Streaming.NumInitialRootPages = 2048
r.Nanite.Streaming.ReservedResources   = 1     ← DefaultEngine.ini에서 이미 켜둠
```

`ReservedResources=1`(+`ReservedResourceIgnoreInitialRootAllocation=1`) 덕에 root page 초기 할당은 예약만 하고 실제 커밋은 온디맨드.

**총 증가 = 512MB(고정 풀) + 수 MB(지오메트리) + 나나이트 버퍼(1080p 기준 수십 MB) = 대략 550~600MB / 8GB 중.**

### 결론: 성능 목적으로는 켤 이유가 없다

- 나나이트가 켜진 유일한 나무(소나무)를 통째로 지워도 **2~3fps**
- `r.Nanite.ProjectEnabled=True` 한 줄만 되돌리면 소나무·고사리만 전환되고, **정작 무거운 `SM_BHF_BirchTreeA`(105,913 tris, 12,929개)는 그대로 non-Nanite로 남는다**
- 효과를 보려면 프로젝트 cvar + **자작나무 메시 2종에 나나이트를 새로 켜는 에셋 변경**이 같이 가야 한다
- 나나이트는 masked(알파컷) 머티리얼을 programmable raster로 처리해 opaque 대비 상당히 비싸고, WPO가 켜진 나나이트 폴리지는 VSM 무효화를 똑같이 일으킨다 — "폴리지에 나나이트 = 공짜 이득"은 성립하지 않는다

> **디자인팀 전달용 한 줄**: *"나나이트 on/off는 이 레벨 성능에 2~3fps 차이밖에 안 만든다. 진짜 문제는 자작나무 메시의 LOD 세팅이었고, 그건 컴포넌트 단에서 해결했다."*

**참고**: `r.Nanite.ProjectEnabled`는 시작 시에만 읽히는 값이라 PIE 중 토글 불가. 검증하려면 ini 수정 후 에디터 재시작이 필요하다.

---

## 폐기한 시도들

### (1) 나나이트 켜기 — 안 함

위 참고. 2~3fps 얻자고 512MB 고정 예약 + 디자인팀 합의 + 에디터 재시작.

### (2) `r.OptimizedWPO.AffectNonNaniteShaderSelection=1` — 안 함

cvar 원문: *"Whether the per primitive WPO flag should affect shader selection for non-nanite primitives. It increases the chance of selecting the position only depth VS at the cost of updating cached draw commands whenever the WPO flag changes."*

처음엔 권장 항목으로 올렸으나 측정 후 폐기:

- 이 옵션이 걸리는 건 컴포넌트 단위 `bEvaluateWorldPositionOffset` **불리언이 꺼졌을 때**다. 우리가 적용한 건 인스턴스별 거리 기반 설정이고 불리언은 여전히 true.
- 실측에서 **WPO 완전 off 22~24fps vs 거리 3000 21~24fps**로 차이가 노이즈 수준 — 셰이더 선택으로 더 먹을 여지가 있었다면 완전 off가 눈에 띄게 높았어야 한다.
- "WPO 플래그가 바뀔 때마다 캐시된 draw command 재생성" 비용이 붙는다. 자작나무만 25,780개가 경계를 넘나드는 씬이라 히칭 위험. 기본값이 off인 이유이기도 하다.

### (3) `Titan_Truck` LOD 생성 — 만들었다가 revert

LOD 3단계 생성 성공(LOD0 983,577 → LOD1 344,251 → LOD2 118,029 → LOD3 39,343, threshold `[2.0, 1.465, 0.956, 0.296]`). 그러나:

| 조건 | fps |
|---|---|
| LOD 적용 전 | 27.1~31.6 |
| LOD 적용 후 | 29.3~30.9 |
| 트럭을 LOD3(39,343 tris)로 강제 | 30.4~30.9 |
| 트럭 BodyMesh 통째로 숨김 | 31.3~31.6 |

**삼각형을 25배 줄여도 fps가 안 움직였다.** 이유 두 가지:

1. **트럭이 UGV에서 13.3m 거리에 있다** — 스폰 위치 기준 바로 옆이라 화면상 크기가 커서 LOD threshold와 무관하게 LOD0/LOD1이 선택된다. LOD가 개입할 수 있는 상황이 아니었다.
2. 조사 초반에 관측했던 "트럭 숨기면 +15%"는 **baseline이 21fps일 때(자작나무 수정 전) 잰 값**이다. 자작나무를 고쳐 30fps로 올라온 뒤엔 트럭이 병목에서 빠졌다.

에셋 크기가 21.6MB → 40.0MB(+18MB)로 늘고 Datasmith 임포트 에셋이라, 효과 없는 변경을 남길 이유가 없어 `p4 revert` 했다.

> **주의**: revert 후에도 에디터 메모리에는 LOD 4개짜리가 남아 있다(`dirty=false`라 자동 재저장은 안 됨). 콘텐츠 브라우저에서 해당 에셋 **Reload** 하거나 에디터 재시작하면 원본으로 돌아온다.

### (4) `forcedLodModel` 강제 지정 — 절대 쓰지 말 것

ISM 컴포넌트에 `forcedLodModel=3`을 걸었더니 **0.2fps로 폭락**했다. ISM의 GPU LOD 선택 경로가 깨지는 것으로 보인다. (일반 StaticMeshComponent인 트럭에서는 정상 동작했다.)

---

## 남은 이슈

### 리눅스 빌드 나나이트 폴백 (성능 아님 — 렌더 정합성)

`[/Script/LinuxTargetPlatform.LinuxTargetSettings] bGenerateNaniteFallbackMeshes=False`는 *"나나이트가 항상 도니까 폴백은 버려라"* 는 뜻인데, **같은 CL에서 나나이트를 껐다.** 이 조합이면 리눅스 패키지 빌드에서 나나이트 메시 233종이 지오메트리 없이 나올 수 있다. 이 레벨만 봐도 소나무 12,976개가 해당된다.

로컬 `Saved/Cooked`는 폰트만 들어간 17MB 스텁이라 검증이 불가능했다. **리눅스 패키지 빌드를 한 번 띄워서 소나무·고사리가 정상적으로 보이는지 눈으로 확인**하면 끝난다. 잘 보이면 넘어가고, 안 보이면 그 한 줄만 지우면 된다.

**나나이트를 안 켜기로 해도 이 건은 남는다.**

### P4 동시 체크아웃

변경한 3개 파일 모두 `user2@user2_jiseong`도 열어둔 상태다. 서브밋 전 확인 필요.

### 추가 여지

- 자작나무 `InstanceLODDistanceScale`을 0.35로 조이면 36fps까지 (화질 확인 후 판단)
- 숲을 통째로 숨겼을 때가 48~58fps이므로 이론상 여유가 더 있으나, 알파컷 폴리지의 오버드로 영역이라 비용 대비 효과는 떨어진다
- `InstanceEndCullDistance`는 실측상 효과가 거의 없었다(24 → 25fps). RCWS가 16배까지 줌인하는 씬이라 거리 컬링은 화질 리스크만 크다

---

## 재현/검증 방법

1. `New_kadex_0811` 열고 PIE 시작
2. 위 "측정 방법" 절차로 fps 측정 — **31fps 근처**면 정상
3. 되돌려서 확인하려면 레벨의 ISM/HISM 17개에 `WorldPositionOffsetDisableDistance = 0`을 넣으면 다시 2.3fps로 떨어진다

---

## 관련 문서

- `ui/graphics_settings_analysis.md` — 그래픽 설정 전반
- `vehicle/ugv/2026-08-27_new_kadex_0811_navmesh_autonomous_driving.md` — 같은 레벨의 내비메시 3층 구조 (`TreeCollisionProxy`가 PCG 나무 위치를 참조하므로, 스플라인을 수정하면 그쪽 스크립트도 재실행 필요)
- `rtsp/linux_wayland_x11_present_bottleneck.md` — 리눅스 패키지 빌드 프레임 폭락 (별건)
