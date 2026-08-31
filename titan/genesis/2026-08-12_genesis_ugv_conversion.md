# BP_UGV_Vehicle → Genesis 물리 엔진 전환 작업 정리

2026-08-12 (최종 작업일) / 일시중단 / 메인 `titan_example`과 완전히 분리된 별도 프로젝트
(`titan_example_genesis`)에서 UGV 물리를 외부 Python 서버(Genesis)로 교체하는 실험.
**2026-08-31 기준: 최근엔 작업 안 하고 있으나 재개 가능성 있음** — 폐기 아님, 이 폴더
(`titan/genesis/`)에 계속 별도 보관.

> 대상: `titan_example_genesis` 프로젝트 (P4V 원본과 분리된 별도 워킹 카피)
> 목적: 기존 Chaos 차량 물리 기반 `BP_UGV_Vehicle`을 건드리지 않고, 별도 복사본
> `BP_UGV_Vehicle_Genesis`를 만들어 외부 Python 물리 서버(Genesis)로 구동되게 전환.
> 테스트는 격리된 레벨 `kadex_test_genesis`에서만 진행 (운영 시나리오/레벨 영향 없음).
> 최종 목표: 기존 `AUGVAIController`의 C++ pure-pursuit 자율주행을 걷어내고,
> NavMesh 경로를 Genesis 서버가 직접 실시간으로 추종(PathFollowing)하도록 전환.

---

## 1. 전체 구조

```
Unreal Editor (titan_example_genesis)
  └─ Plugins/GenesisOSCBridge  ← UE ↔ Genesis 브릿지 플러그인 (OSC 소켓 통신)
       - AGenesisOSCBridge          레벨에 배치하는 브릿지 액터
       - AGenesisWheeledVehiclePawn 차량 Pawn 베이스 (AWheeledVehiclePawn 상속)
       - UGenesisWheeledVehicleMovementComponent
                                    (UChaosWheeledVehicleMovementComponent 상속 →
                                     기존 SetThrottleInput/SetYawInput/GetForwardSpeed/
                                     GetWheelState 등 Chaos 호환 BP 노드 그대로 사용 가능)

  Python physics_server (별도 프로세스, 사용자가 직접 기동)
       - genesis-world(Genesis 물리 SDK) + URDF로 차량을 재구성해서 시뮬레이션
       - OSC로 UE와 상태/입력을 주고받음
       - UE의 PhysicsAsset/BodyInstance는 전혀 보지 않음 → 질량/충돌형상은 URDF가 유일한 소스
```

핵심 전제: **Genesis는 UE 메시나 PhysicsAsset을 전혀 모른다.** 차량의 질량, 충돌 형상,
바퀴 위치, 서스펜션은 전부 `ugv.urdf` 파일 하나로 정의되고, UE 쪽 메시는 순수 비주얼일 뿐이다.

---

## 2. 환경 구성

- Python 3.13.15 x64 (py launcher로 per-user 설치, 기존 3.14 기본값과 공존, PATH 변경 없음)
- PyTorch (CUDA cu130 빌드, RTX 5060 GPU 사용)
- `genesis-world`, `numpy`, `python-osc`
- `physics_server.py`를 사용자가 직접 기동해서 PIE와 함께 테스트
  (에이전트가 PIE/서버 프로세스를 직접 건드리면 상태가 꼬이는 문제가 있어서,
  이후로는 로그 분석/설정만 담당하고 실행은 사용자가 직접 함)

---

## 3. URDF 세팅과 무게중심(CoM) 버그

`ugv.urdf` (`physics_server/urdf/ugv.urdf`)가 Genesis 쪽 차량의 유일한 물리 소스.

### 3.1 좌표축 변환
기존 `m1a2_tank.urdf`와 대조해서 확인한 변환식:
- `URDF_X = UE_X / 100` (부호 유지)
- `URDF_Y = -UE_Y / 100` (부호 반전)
- `URDF_Z = UE_Z / 100` (부호 유지)

### 3.2 구조
- 섀시 링크 1개 (box collision) + 바퀴 16개
- 바퀴마다 carrier(현가 prismatic joint) → spin joint(continuous) 2단 체인
- 서스펜션: `axis="0 0 1"`, `limit lower="-0.05" upper="0.075" effort="5000" velocity="2"`

### 3.3 무게중심/충돌박스 버그 (핵심 사고 사례)

**증상:** 수동 조향으로 전진 가속하다가 특정 속도에 도달하면 차량이 뭔가에 부딪힌 것처럼
갑자기 붕 뜨면서 튕겨 나감. 후진에서도 동일 현상 재현.

**잘못된 원인 추정 과정 (교훈으로 기록):**
1. 기어비 배열이 8개로 깨져 있던 것을 발견해서 고쳤지만 (`[2.85,2.02,1.35,1,2.85,2.02,1.35,1]`
   → 정상 5개 `[2.85,2.02,1.35,1,0.8]`), 이건 별개의 버그였고 튕김의 원인은 아니었음.
2. 로그에서 "후진 기어(-1)만 계속 나온다"고 오판 — 실제로는 grep 검색어 자체에
   `gear=-1`이 들어가 있어서 그 줄만 걸러져 보인 것. 기어는 1~5 정상적으로 순환하고 있었음.
3. 두 번째 UGV 인스턴스 중복, `BP_Ally_kadex`(기본 Pawn)가 UGV 내부에 스폰되어 콜리전을
   일으키는 것 아니냐는 가설도 세웠으나, 라이브 PIE에서 액터 트랜스폼을 직접 조회해서
   확인한 결과 둘 다 사실이 아니었음.

**실제 원인 (사용자가 직접 찾음):** 섀시 collision box가 포탑 주포(gun barrel)까지
포함해서 X: -1.81 ~ +3.03 범위로 잡혀 있었음. 실제 바퀴들이 있는 범위보다 훨씬 앞으로
튀어나온 충돌 형상이라, 무게중심이 크게 앞으로 쏠린 것처럼 계산되어 특정 속도 이상에서
불안정하게 피칭/런칭하는 현상으로 나타난 것.

**수정:** "바퀴들 전체를 박스로 잡고 보면 차체 크기랑 비슷하다"는 원칙으로, 바퀴 위치
기준 바운딩 박스 + 여유 0.2m로 재설정.
```
size = "2.3916 2.2064 0.94"   (X: -1.2049 ~ 1.1867, Y: -1.1032 ~ 1.1032 기준 재계산)
origin xyz = "-0.0091 0 0.87"
mass = 3000 kg (바퀴 16개 별도 80kg×16 = 1280kg, 총 4280kg)
inertia: ixx=1437.95 iyy=1650.85 izz=2647.00 (박스 재계산)
```
이후 특정 속도에서의 런칭/튕김 현상 완전히 재현 안 됨.

**교훈:** Genesis 충돌 형상은 비주얼 메시와 무관하게 URDF가 전부다. 비주얼 메시 기준으로
"이 정도면 맞겠지"로 형상을 잡으면 안 되고, 실제 바퀴 배치 기준으로 역산해야 한다.

### 3.4 그 외 URDF/설정 관련 버그
- **구르는 게 안 멈춤 (rolling resistance 누락):** 가속 후 브레이크 밟기 전까지 계속
  굴러감. 바퀴 spin/제동 헛도는 것과는 다른 증상. `WheelOverrides`에
  `bOverrideRollingResistance=true, rollingResistance=0.02` 추가로 해결.
- **A/D 조향 반대:** `SetManualControl`의 `SetYawInput` 호출에
  `(* -1.0 (Math|Float|SelectFloat TurnInput (* TurnInput -1.0) (>= ForwardInput 0)))`
  래핑 추가해서 해결 (후진 시에는 조향 반전 로직 포함).
- **차체 붕 뜬 채로 조종 안 됨:** PIE를 재시작 없이 반복하다 보면 발생. 에디터를
  껐다 켜면 해결 — Genesis 서버-PIE 세션 동기화 문제로 추정, 근본 원인 미해결이지만
  재현 조건(에디터 장시간 유지) 회피로 대응 중.
- **XML 주석의 `--`:** URDF 주석 안에 리터럴 더블하이픈이 있으면
  `xml.etree.ElementTree.ParseError`. 총 3번 반복해서 겪음 — 주석 작성 시 항상 확인.

### 3.5 프리셋 상수 관련 피드백 (2026-08-11, 교수님 URDF 리뷰)

`tank_skid_belt` 프리셋은 40톤급 탱크 기준으로 튜닝된 상수를 쓰는데, 이 UGV는 4.3톤이라
일부 프리셋 상수가 체급에 안 맞는다는 지적. 4가지 항목 확인 결과:

**① TopSpeed 미설정 — 액션 필요, 확인됨**
프리셋 기본 `omega_max_drive = 150 rad/s`는 탱크 기준 최고속 67 km/h에 해당하는데,
12cm 바퀴짜리 4.3톤 UGV엔 과함. 실제로 `VehicleSetup.bUseTopSpeedOverride`가 `false`로
꺼져 있어서 지금까지 이 탱크 기본값(67km/h)을 그대로 쓰고 있었던 것으로 확인됨 — Sweep
Table은 40km/h(11.111 m/s)로 측정해놓고 정작 차량 최고속 제한은 걸려있지 않았던 상태.
→ `bUseTopSpeedOverride=true, TopSpeed=11.111 m/s`로 맞춰 적용 완료 (Sweep Table 측정
조건(40km/h)과 실주행 최고속 설정 일치시킴). `GenesisOSCBridge_0.VehicleSetup`에 반영,
`kadex_test_genesis` 레벨 저장됨.

**② 발진 시 휠스핀 — 정보성, 현재는 안전한 범위**
프리셋 `t_drive_max = 30,000 N·m`(기어캡 0.3 적용 시 유효 9,000 N·m)가 이 차량의 접지
마찰 한계(4,692 N·m, μ=0.9)의 약 2배. 마찰원(friction circle)에서 잘리기 때문에 폭주는
없지만, 출발 시 휠스핀이 거칠게 나타날 수 있음. UE 쪽에서 이 프리셋 내부 상수(t_drive_max,
기어캡)를 직접 노출/조정하는 프로퍼티는 없음 — `VehicleSetup.MaxTorque`는 툴팁상
"Engine Model이 켜져있을 때만 사용"인데 이 플러그인에 Engine Model 토글 자체가 노출되어
있지 않아 사실상 SkidSteer 프리셋에는 미적용. 개선하려면 `bUseManualJointMapping=true`로
켜고 `DrivingJoints[].ForceLimit`을 접지 한계 근처로 수동 설정하는 방법이 있음 (10개 구동
조인트를 전부 수동으로 나열해야 해서 구조가 커짐) — 지금 당장 문제로 보고된 적은 없어서
보류, 발진이 실제로 거슬리면 그때 적용.

**③ 섀시 visual 박스 지면 파묻힘 — 정보성, 물리 영향 없음**
URDF 확인 결과 `<visual>` 박스가 `size="4.84 2.89 1.2"` `origin xyz="0 0 0"` 그대로
남아있음 — 이건 3.3절에서 고친 원래의(포신 포함) 전체 메시 바운딩 박스이고, `<collision>`/
`<inertial>`만 바퀴 기준으로 재설정하고 `<visual>`은 갱신을 안 한 것. 바퀴 접지면이 섀시
로컬 z=+0.018인데 visual 박스는 z=-0.6~+0.6이라 바닥 아래로 0.6m 파묻힌 것처럼 보임.
Genesis 기본 `--vis_mode collision`에서는 안 보이고, `--vis_mode visual`로 바꿔야 보이는
디버그 렌더링 문제라 물리 시뮬레이션 자체엔 영향 없음. 관성 텐서가 collision 박스 치수와
정확히 일치하는 것도 재확인됨 (collision 쪽이 실제 치수, visual은 플레이스홀더). 디버그
비주얼을 정확하게 볼 일이 생기면 `<visual>` box도 collision과 동일하게 맞추면 됨 — 급하지 않음.

**④ 서스펜션 — 확인 완료, 이상 없음**
URDF에 `<dynamics>` 태그가 없어서 질량 기반으로 자동 유도된 값: 강성 k=36,788 N/m,
감쇠비 ζ=0.80, 승차 주파수 2.23 Hz, 정적 처짐 50mm (= `rest_stroke` 0.10m의 절반 근처,
탱크 프리셋 설계점과 일치). dt=0.02 기준 안정도 비 0.7 (발산 임계 0.86 대비 여유 있음) —
정상 범위. 별도 조정 불필요.

---

## 4. SkidSteer 차량 설정

`GenesisOSCBridge_0` 액터의 `VehicleSetup` (`FGenesisVehicleMapping`):
```
DriveType            = SkidSteer
DrivetrainStrategy   = PerSide
CouplingStrategy     = SameSideBelt   (같은 쪽 바퀴들이 벨트로 묶인 것처럼 커플링 — 탱크 트랙 방식)
```
스키드스티어 판별 근거: 16개 바퀴 전부 `bAffectedBySteering=false`, `DifferentialSetup=AllWheelDrive`,
L_/R_ 접두사 네이밍 컨벤션.

---

## 5. 메인 내용 — NavMesh 경로 → Genesis PathFollowing (S/T 값 파이프라인)

기존 `AUGVAIController`는 C++로 직접 구현한 pure-pursuit 로직으로 NavMesh 경로를 따라가며
스로틀/조향을 계산했다. 이 목표는 **그 로직을 걷어내고, NavMesh로 계산한 경로점만 Genesis
서버에 넘긴 뒤, Genesis 자체 PathFollowing 컨트롤러가 서버 권위(authoritative)로 실시간
스티어링/스로틀(S/T)을 계산**하게 만드는 것.

### 5.1 전체 파이프라인

```
1. NavMesh 경로 계산
   AUGVAIController::MoveToDestination(ugv_move_point)
     → UNavigationSystemV1::FindPathToLocationSynchronously(this, 시작위치, 목표위치, ControlledPawn)
     → GetLastPathPoints() 로 성긴 코너 포인트 배열 획득

2. Coarse → Dense 리샘플링 (플러그인 내장 BP_WaypointPath 재사용)
   NavMesh 코너 포인트들을  →  MakeSWaypoint(Speed=1.0, HeadingYaw=0, bAutoHeading=true)
   → BP_WaypointPath.CoarseWaypoints 에 세팅
   → BP_WaypointPath.Divisions = 8
   → BP_WaypointPath.GetWaypoints() 호출
        내부적으로 SplineComponent에 Coarse 포인트들을 World 스페이스로 추가하고
        UpdateSpline() (기본 Curve=Catmull-Rom 자동 탄젠트) 후,
        구간마다 Divisions개로 쪼개서 GetLocationAtSplineInputKey로 실제 위치 샘플링,
        Speed/HeadingYaw/bAutoHeading은 양 끝 Coarse 포인트 사이 선형보간(Lerp)
   → 부드럽게 리샘플링된 Dense Waypoint 배열(S_Waypoint) 획득

3. Genesis에 경로 전달
   SetTargetPathFromWaypointArray(GenesisOSCBridge, TargetIndex=0, DenseWaypoints, Settings)
   StartTargetPathFollowing(GenesisOSCBridge, TargetIndex=0)

4. Genesis 서버가 매 프레임 S/T(Steer/Throttle) 계산
   - Sweep Table(차량별 캘리브레이션 CSV)을 기준으로 목표 지점까지 lookahead 방식으로
     조향각/속도를 산출, SkidSteer이므로 좌우 트랙 속도차로 변환되어 차량에 적용됨
   - 이 계산 로직 자체는 Python 쪽 컴파일된 모듈(.pyd)이라 소스 확인 불가 —
     UE 헤더의 파라미터 이름/기본값과 공식 가이드 문서로만 거동 유추 가능
```

### 5.2 왜 Dense 리샘플링이 필요했나

처음에는 NavMesh의 `GetLastPathPoints()` 결과(성긴 코너 점들)를 그대로
`SetTargetPath`에 넘겼다. 이 상태에서 자율주행 중 코너에서 장애물에 계속
부딪히는 문제가 있었음.

원인 조사 중 `GENESIS_UE_USER_GUIDE.md`와 플러그인 콘텐츠(`BP_WaypointPath`,
`BP_CoarsePointHandle`, `BP_DensePointHandle`)를 확인한 결과, 플러그인이 원래
의도한 파이프라인은 "성긴 Coarse 포인트 → 스플라인 보간 → 촘촘한 Dense 포인트"였고,
`SetTargetPathFromWaypointArray`가 바로 이 Dense 배열을 받도록 설계되어 있었음
(`SetTargetPath`는 이미 완성된 배열을 그대로 받는 저수준 API).

NavMesh 코너점을 리샘플링 없이 바로 넣으면 Lookahead(350cm)짜리 추종 알고리즘이
중간 안내점 없이 코너를 크게 잘라 들어가게 됨 — 이게 장애물 충돌의 핵심 원인으로 추정,
BP_WaypointPath의 `GetWaypoints()`를 그대로 재사용해서 해결.

구현은 `BP_UGV_Vehicle_Genesis`의 `EventBeginPlay`에서 매번 임시로
`BP_WaypointPath`를 스폰 → CoarseWaypoints 세팅 → GetWaypoints() 호출 →
결과만 뽑아 쓰고 바로 DestroyActor로 정리하는 방식 (레벨에 시각적 잔여물 안 남음).

### 5.3 NavMesh 에이전트 반경 확인 (Default vs Tank)

레벨에 `RecastNavMesh-Default`(사람 크기, radius 30)와 `RecastNavMesh-Tank`
(UGV용으로 키운 radius 200) 두 개가 존재 — 자율주행이 잘못된(더 작은) NavMesh를
쓰고 있는 게 아니냐는 의심이 있었음.

UE 5.8 엔진 소스 확인 결과:
- `APawn::GetNavAgentPropertiesRef()` = `FindComponentByInterface<INavMovementInterface>()`
  즉 **Pawn에 붙은 컴포넌트 중 가장 먼저 등록된 것**의 NavAgentProps를 사용
- `AGenesisWheeledVehiclePawn`은 `AWheeledVehiclePawn`을 상속하므로, 베이스 클래스
  생성자가 먼저 실행되어 네이티브 `VehicleMovementComp`가 먼저 등록되고,
  파생 클래스가 나중에 `GenesisVehicleMovementComponent`를 추가로 붙임
- 따라서 `FindComponentByInterface`는 항상 **먼저 등록된 네이티브 VehicleMovementComp**를
  반환 — 그리고 이 컴포넌트에는 `BP_UGV_Vehicle`(원본)에서 물려받은
  `NavAgentProps = {agentRadius: 200, agentHeight: 144}`가 그대로 남아있음
  (`DefaultEngine.ini`의 Tank SupportedAgents 항목과 정확히 일치)
- 결론: **NavMesh 선택 자체는 처음부터 문제없이 Tank용으로 정상 동작 중이었음.**
  (참고로 실제 구동을 담당하는 `GenesisVehicleMovementComp`는 NavAgentProps가
  `{-1, -1}`(미설정)이지만, 컴포넌트 등록 순서상 경로탐색에는 관여하지 않음)

---

## 6. PathFollowing 튜닝 히스토리

`FGenesisPathFollowingSettings` (경로 추종 파라미터) 값 변화:

| 파라미터 | 최초 | 1차 조정 | 현재 (MuLat 적용 후 재상향) | 사유 |
|---|---|---|---|---|
| SkidSteerGain (VehicleSetup) | 1.0 | 0.45 | **0.65** | 1차: 제자리 빙글빙글 완화. 재상향: MuLat으로 옆미끄러짐이 잡혀서 게인을 다시 올려도 안정적 |
| YawGain | 1.5 | 0.6 | **1.0** | 위와 동일 |
| ApproachGain | 1.0 | 1.0 (유지) | **1.8** | 도착 직전 구간에서만 반응성 집중 강화 (overshoot 대응, 아래 참고) |
| SteerCap | 0.5 | 0.5 (유지) | **0.65** | 도착 직전 급조향이 캡에 잘리지 않도록 |
| ArrivalGoalCm | 150 | 150 (유지) | **500** | 도착 판정 범위 확대 |
| LookaheadCm | 350 | 350 (유지) | 350 (유지) | |

**바퀴 횡방향 마찰(MuLat) 추가:** 위 게인들을 낮춘 뒤에도 회전 시 "꼬리치는"(뒷부분이
미끄러지며 좌우로 흔들리는) 현상이 남아있었음. `WheelOverrides`를 확인해보니
`MuLat`(횡방향 마찰)이 전혀 오버라이드 안 되어 있었고(SDK 프리셋 기본값 그대로),
URDF에도 마찰 값이 없었음. 스키드스티어는 원래 좌우 바퀴 속도차로 트랙을 옆으로
긁으면서 도는 구조라 횡방향 그립이 부족하면 요(yaw) 반응이 과민해지고 미끄러졌다
잡히는 걸 반복 → 꼬리치는 현상으로 나타남.

```
WheelOverrides[0]: bOverrideMuLat=true, MuLat=2.2   (전역 씬 기본 마찰 2.0보다 살짝 높게)
```
적용 후 꼬리치는 현상 완전히 사라짐.

**부작용 및 후속 튜닝 (적용 완료):** MuLat을 올린 만큼 회전 자체가 둔해져서, 목표
지점 근처에서 방향을 제때 못 꺾고 스쳐 지나가는(overshoot) 현상 발생. MuLat이
횡방향 미끄러짐을 물리적으로 억제해주고 있어서 게인을 다시 올려도 예전처럼 쉽게
진동하지 않을 거라는 판단으로, `ApproachGain`(도착 직전 접근 단계 전용으로 추정,
1.0→1.8)과 `SteerCap`(0.5→0.65), `YawGain`(0.6→1.0), `SkidSteerGain`(0.45→0.65)을
함께 완만하게 재상향, `ArrivalGoalCm`도 150→500으로 확대. **PIE 재검증 대기 중.**

---

## 7. 알려진 이슈 / 다음 단계

- [x] `VehicleSetup.bUseTopSpeedOverride=true, TopSpeed=11.111 m/s(40km/h)` 적용
      (교수님 URDF 리뷰로 발견 — Sweep Table 측정 조건과 실제 최고속 제한이 안 맞았음. 적용 완료)
- [ ] `ApproachGain`(1.8)/`SteerCap`(0.65)/`YawGain`(1.0)/`SkidSteerGain`(0.65)/
      `ArrivalGoalCm`(500) 재상향 적용 완료 — **PIE 재검증 대기 중** (overshoot 개선 및
      꼬리치기 재발 여부 확인 필요)
- [ ] `Divisions=8` 값 튜닝 여지 있음 — 코너가 급격한 구간에서 Catmull-Rom 보간이
      원래 폴리라인보다 바깥으로 부풀어 나갈 수 있음 (아직 실측 문제 보고는 없음)
- [ ] "에디터 장시간 유지 시 차량 물리 꺼짐" 현상 근본 원인 미확인 (재발 시 에디터
      재시작으로 회피 중)
- [x] 자율주행 트리거를 `EventBeginPlay` 자동 실행 → **`I` 키 입력**으로 변경함. 처음엔
      `BP_UGV_Vehicle_Genesis` 자체에 `Input|KeyboardEvents|I`를 붙였는데 전혀 반응 안 함 —
      원인은 아래 "중요 아키텍처 노트" 참고(이 Pawn은 Possess된 적이 없어서 입력이 안 옴).
      최종적으로 `BP_UGV_Vehicle_Genesis`에 Custom Event `StartAutoDrive`를 만들어 기존
      "제네시스 상태 대기 → MoveToDestination → 경로 리샘플링 → PathFollowing 시작" 체인을
      그대로 연결하고, `BP_TestPlayerController_Genesis`에서 `I` 키를 받아 UGV 인스턴스를
      찾아 이 Custom Event를 호출하는 구조로 변경. `EventBeginPlay`는 현재 빈 노드로
      남아있음(무해, 굳이 안 지움). 목적지는 여전히 하드코딩(`ugv_move_point`, 6460,830,0)
      — 콘솔 커맨드화는 아직 미착수
- [x] **`O` 키로 자율주행 중지 → 수동 복귀** 추가함. 최초 구현은 `StopTargetPathFollowing`만
      호출했는데, `I` 키 트리거 시 이미 `SetDriveMode(Idle)`로 바꿔둔 상태가 그대로 남아있어서
      PathFollowing만 꺼지고 차량은 Idle(풀브레이킹) 상태에 머무는 문제가 있었음 → 수정해서
      `O` 키가 `Self → GetController → CastToUGVAIController → SetDriveMode(Manual)` 을 먼저
      실행한 뒤 `GetActorOfClass(GenesisOSCBridge) → Cast → StopTargetPathFollowing(bridge, 0)`
      순서로 실행하도록 변경. 이제 WASD 수동 조향이 바로 복귀됨.
      **중요 아키텍처 노트:** `BP_UGV_Vehicle_Genesis`는 플레이어가 직접 Possess하는 Pawn이
      아님 — `BP_TestGameMode_Genesis`의 `DefaultPawnClass`는 `BP_Ally_kadex`(군인)이고, UGV는
      `Atitan_examplePlayerController`(네이티브 C++)가 Enhanced Input으로 WASD를 받아
      `AUGVAIController::DispatchSetManualControl()`로 원격 호출하는 RCWS 패턴. 그래서 UGV
      Pawn 자체에 `K2Node_InputKey`를 붙여도 입력이 절대 안 옴(언리얼은 Possess된
      Pawn+Controller에만 입력 라우팅) — `I`/`O` 키는 `BP_UGV_Vehicle_Genesis`의 Custom Event
      (`StartAutoDrive`/`StopAutoDrive`)로 만들고, 실제 키 입력은 `BP_TestPlayerController_Genesis`
      에서 받아서 `GetActorOfClass(BP_UGV_Vehicle_Genesis)` → Cast → Custom Event 호출로 연결함.
- [ ] (낮은 우선순위) 발진 시 휠스핀이 실제로 거슬리면 `bUseManualJointMapping=true` +
      `DrivingJoints[].ForceLimit`을 접지 마찰 한계(~4,692 N·m) 근처로 수동 설정 검토
- [ ] (낮은 우선순위) URDF `<visual>` 박스가 옛날 전체 메시 바운딩 박스로 남아있음 —
      `--vis_mode visual`로 디버그 렌더링할 일이 생기면 collision 박스 치수로 맞추기
- [x] **Sweep Table 재측정 완료** — `MuLat=2.2` 적용 후 캘리브레이션이 stale해진 상태였어서
      동일 조건(`--urdf urdf/ugv.urdf --preset tank_skid_belt --top-speed 11.111
      --output path_profiles/ugv.csv`, CPU가 더 빨라서 `--gpu` 제외)으로 `path_profiles/ugv.csv`
      재생성함. `CalibrationProfileId="ugv"`가 그대로 이 파일을 참조하므로 별도 설정 변경 불필요.
