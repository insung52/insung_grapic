> [보관됨 2026-08-31] 참고 프로젝트(TankSim) 분석 문서 — Titan 자체 구현(RCWS/QuadCam/UGV)이
> 이미 이 내용을 훨씬 넘어서 발전함. 단, §4 나이트비전 패턴과 §6 미니맵 투영 패턴은 Titan에
> **아직 구현 안 된 아이디어**로 남아있으니, 나중에 그 기능이 필요해지면 이 문서부터 참고할 것.

# TankSim 프로젝트 — 탱크(BP_Tank_B / ATankPawn) 분석 (2026-06-23)

## 목적
Titan 트럭(`BP_TitanTruck`)에 우리가 만든 4방향 SceneCapture + Widget Blueprint 4분할 영상
기능을 실제로 어떻게 활용할지 설계하기 전에, 참고 프로젝트인 `C:\working\TankSim`의
플레이어 탱크가 어떻게 움직이고 어떤 부가 기능(NightVision 등)을 갖고 있는지 코드 레벨로
분석한 문서. 에디터 상 `BP_Tank_B`가 플레이어 탱크 액터이고 부모 C++ 클래스는 `ATankPawn`
(`Source/TankSim/TankPawn.h/.cpp`)으로 확인됨.

---

## 1. 핵심 클래스 구조

| 클래스 | 역할 |
|---|---|
| `ATankPawn` | 플레이어가 조종하는 탱크 본체. 이동/포탑 회전/조준/발사/스코프/나이트비전/미니맵 투영까지 거의 전부 이 클래스 하나에 구현됨 |
| `AMyPlayerController` | 플레이어 컨트롤러. 미니맵 위젯/캡처 액터, Genesis 외부 시뮬레이터 런처를 BeginPlay에서 같이 띄움 |
| `AEnemyTank` | NavMesh 기반으로 순찰하는 적 탱크 Pawn. AI 전용, 플레이어 입력 없음 |
| `AEnemyTankAIController` | `AEnemyTank`를 조종하는 AIController. 랜덤 순찰 + 플레이어 회피 로직 |
| `ATankProjectile` | 포탄 발사체. 즉시명중(Instant Hit) 방식 지원, Niagara/ZibraVDB 폭발 이펙트 트리거 |
| `UUTankMovementComponent` (`ChaosWheeledVehicleMovementComponent` 상속) + `AATankVehiclePawn` (`AWheeledVehiclePawn` 상속) | **레거시/미사용으로 보임.** `ATankPawn`은 이 컴포넌트를 전혀 참조하지 않고 자체 Force 기반 이동을 씀. 실제 플레이 탱크와 무관한 별도 실험적 차량 피직스 구현으로 추정 |
| `UYOLOSubsystem` / `FYOLODetector` | 메인 뷰포트를 캡처해서 YOLO 객체탐지 돌리는 서브시스템. 탱크 동작과는 별개 (별도 분석 필요시 후술) |
| `UVDBCacheSubsystem` | `.zibravdb` 파일과 연계 Niagara 에셋을 게임 시작 시 비동기 프리로드 (로딩 끊김 방지용) |

---

## 2. 이동 방식 — Force 기반 듀얼 트랙 (Chaos Vehicle 아님)

`ATankPawn::Tick()`에서 매 프레임 직접 물리 힘을 가하는 방식:

```
LeftTrack  = clamp(Throttle + Turn*0.1, -1, 1)
RightTrack = clamp(Throttle - Turn*0.1, -1, 1)
BodyMesh->AddForceAtLocation(Forward * LeftTrack  * MoveForce, LeftTrackPos)
BodyMesh->AddForceAtLocation(Forward * RightTrack * MoveForce, RightTrackPos)
```

- `BodyMesh`(루트, `SimulatePhysics=true`)에 좌/우 두 지점(`TrackOffset`만큼 좌우로 떨어진 위치)에서
  각각 전진력을 가하는 **실제 궤도차량(스키드 스티어) 방식의 단순화 모델**. 좌우 트랙 힘 차이로 선회.
- `MoveForward()` / `Turn()`은 `bPlayMode`가 true일 때만 입력을 받음 (스튜디오/선택 모드에서는 무시)
- 포탑(`RotateComponent`)은 별도 `USceneComponent`로, 마우스 X 이동을 누적(`AccumulatedYaw`)해서 Yaw 회전.
  - **플레이 모드**: 포탑이 실제로 Yaw 회전 (`RotateComponent->SetRelativeRotation`)
  - **비플레이 모드(스튜디오/선택 화면 추정)**: 차체(`BodyMesh`) 자체가 회전하고, 목표각(`AccumulatedYawTarget`)에
    부드럽게 `RInterpTo` 따라가는 카메라 회전 연출 + 일정 각도 벗어나면 "리코일"처럼 튕기는 보정(`bStudioCamRecoilNeeded`) 로직 있음 — 전시/쇼케이스용 카메라 회전으로 추정
- 마우스 Y는 포신 피치(`AccumulatedPitch`, -15~5도 클램프)와 카메라 피치를 같이 조정, `TankPoHead`(포탑 헤드 메시)도 같이 회전

## 3. 조준/스코프 모드

- 우클릭 홀드 또는 `V` 키 → `bScopeActive = true`
- 스코프 진입 시:
  - FOV를 `NormalFOV`(기본 90, BeginPlay에서 PlayerCameraManager의 DefaultFOV로 초기화)→`ScopeFOV`(기본 22)로
    `FInterpTo`(속도 `ScopeTransitionSpeed=7`)로 부드럽게 전환
  - 마우스 감도에 `ScopeMouseSensitivityMultiplier`(0.3) 곱해서 줌 상태에서 둔감하게
  - 카메라 위치/피치 약간 변경 (조준경 위치로 이동)
  - `OnScopeModeChanged(bool)` — **BlueprintImplementableEvent**로 BP에서 스코프 UI 오버레이 처리하도록 노출
- 스코프 중 `N` 키 → 나이트비전 토글 (`bNightVisionEnabled`)

## 4. 나이트비전 (NightVisionPP) — 요청하신 기능

- `UPostProcessComponent* NightVisionPP` — `bUnbound=true`(위치 무관 전체 적용), 기본 `bEnabled=false`
- `NightVisionMaterial`(PP 머티리얼, **Blendable Location = After Tonemapping** 으로 설정되어 있어야 함 — 주석에
  "LCC(Lumen?) GS 합성 이후 적용하기 위함"이라고 명시)으로부터 BeginPlay에 `UMaterialInstanceDynamic` 생성
- 머티리얼 파라미터:
  - `NV_GreenGain` (기본 1.5) — 녹색 게인
  - `NV_GrainIntensity` (0.3) — 필름 그레인 노이즈
  - `NV_VignetteIntensity` (1.2) — 비네팅
  - `NV_ScopeRadius` (0.42, 화면 절반 기준 원형 마스크 반지름)
  - `NV_ScopeFeather` (0.06, 마스크 경계 블렌딩 폭)
- 활성화 방식: `NightVisionPP->bEnabled = true` + `AddOrUpdateBlendable(MID, Weight)` — weight를 0↔1로 바꿔 켜고 끔
  (스코프 진입/해제 시에도, `bNightVisionEnabled`가 true면 같이 켜고 꺼짐)
- **즉, 나이트비전은 항상 켜져있는 게 아니라 "스코프 모드 + 나이트비전 토글이 둘 다 활성"일 때만 적용되는
  조준경 전용 효과**로 구현되어 있음. 항상 켜진 1인칭 나이트비전이 필요하면 이 조건 분기를 변경해야 함.

## 5. 발사 / 명중 처리

- 좌클릭 → `Fire()`. 쿨다운(`FireCooldown=2초`), 탄약(`AmmoCount`), 엔진온도(`EngineTemperature<100`) 조건 체크
- 발사 시 엔진온도가 `*=1.025`로 누적 상승 → 너무 빨리 연사하면 과열로 발사 불가 (3초마다 자연 냉각, `*0.985`, 최소 82도)
- **자동 조준 보조**: 매 틱 포신 방향으로 레이캐스트(원통형 판정, 반지름 150)해서 사거리 내 가장 가까운 `AEnemyTank`를
  `OutlinedEnemy`로 잡고 아웃라인 표시(`SetOutline(true)`)
- 발사 시 `OutlinedEnemy`가 있으면 `ATankProjectile::InstantHit()`으로 **발사체 비행 없이 즉시 명중 처리**
  (탄도 시뮬레이션은 시각적 트레일/이펙트용이고, 실제 명중 판정은 레이캐스트 기반)
- 발사 반동: `CameraRecoilCurve`(0~1 정규화 커브)로 카메라가 `CameraRecoilDistance`(5cm)만큼 뒤로 밀렸다가 복귀

## 6. 미니맵 연동 (참고 — Titan 4분할 카메라와 유사한 패턴)

- `AMyPlayerController`가 BeginPlay에서 `AMinimapCaptureActor`(SceneCapture 기반 탑다운 캡처)와
  `UMinimapWidget`을 생성, `MinimapWidget->InitializeMinimap(RenderTarget)`으로 연결
- `ATankPawn::Tick()`에서 미니맵 캡처의 `SceneCaptureComponent2D` 트랜스폼을 가져와 적 탱크들의 월드 좌표를
  **수동으로 원근 투영(perspective division)** 해서 `MinimapPosArray`(화면 NDC 좌표, -1~1)에 저장
  → 미니맵 위젯이 이 배열을 받아 적 아이콘(`EnemyIconTexture`)을 오버레이로 그리는 방식
- 우리가 만든 `ATitanTruck`의 4방향 카메라는 SceneCapture→RenderTarget→Widget Image 연결까지만
  구현했고, 이 미니맵처럼 "캡처 좌표계로 객체 위치를 NDC로 투영해서 오버레이 그리는" 패턴은 아직 없음.
  필요시(예: 4분할 화면에 적 탱크 마커 표시) 이 코드가 좋은 참고가 됨.

## 7. EnemyTank (AI 적 탱크) 이동/사망 처리 — Titan 트럭에 참고될 수 있는 부분

- `UFloatingPawnMovement` + `AEnemyTankAIController`(NavMesh 기반 `MoveTo`)로 경로 추종.
  **물리 시뮬레이션 없이 `SetActorLocationAndRotation`으로 직접 위치/회전 갱신** (Force 기반 아님)
- 매틱 지면 레이캐스트(4프레임마다, `bTraceComplex`)로 지형 높이/경사를 구해서 `SmoothedNormal`로 부드럽게
  보간 → 탱크가 경사면에 자연스럽게 정렬(Pitch/Roll)되도록 처리. **차체를 지면에 스냅시키는 좋은 참고 패턴**
  (우리가 트럭 바퀴 Z=0 정렬 고민했던 것과 유사한 문제를 런타임에 동적으로 해결하는 방식)
- 속도 방향 기반 Yaw 회전(`pivot-and-drive`: 각도차 클수록 선회 속도 증가, 큰 각도 전환 시 속도 캡)
- 탱크 간 겹침 방지: 매틱 다른 `AEnemyTank`와의 XY 거리 체크해서 밀어내는 separation 로직
- 피격(`OnBodyHit`) → AI 이동 중단, 화염 이펙트 부착, `BurnDuration`(10초) 후 `OnDeathTimerExpired` → 액터
  제거 + ZibraVDB/Niagara 폭발 스폰

## 8. ZibraVDB 연동 (지난번 라이선스 에러의 출처)

- `ATankProjectile`, `AEnemyTank`에 `UZibraVDBVolume4*` 필드 다수 (머즐플래시/탱크피격폭발/지형폭발, 각각 `_2`
  변종 포함 — 추정상 같은 이펙트를 두 개의 다른 압축 볼륨/스타일로 동시에 띄우는 것으로 보임)
- `AZibraVDBActor`를 런타임에 스폰하고 `UZibraVDBAssetComponent::SetZibraVDBVolume()`으로 볼륨 할당,
  `UZibraVDBPlaybackComponent`로 프레임 재생 제어 (`Framerate`, `StartFrame`, `Animate`)
- `ApplyVDBMaterial()`(`VDBMaterialHelper.h`)로 DensityScale/ScatteringColor/FlameScale 같은 머티리얼
  파라미터를 코드에서 직접 주입
- → 지난번 봤던 "ZibraVDB: Failed to initialize decompressor: license 필요" 에러는 바로 이 `.zibravdb` 볼륨들을
  재생하려 할 때 발생하는 것. 라이선스 없으면 폭발/화염 이펙트가 안 보일 뿐, 탱크 동작 자체(이동/사격/명중)에는
  영향 없음.

## 9. YOLO 객체탐지 (탱크 동작과는 독립적인 부가 기능)

- `UYOLOSubsystem`이 50프레임마다 한 번씩 메인 뷰포트를 GPU 리드백 → 백그라운드 스레드에서 ONNX Runtime
  기반 YOLO 추론(`FYOLODetector`) → 결과를 `UTankSimViewportClient::DrawYOLOBoxes()`가 화면에 바운딩박스로 그림
- 탱크가 이 결과를 직접 쓰는 코드는 없음 (적 탱크 조준은 위 6번의 레이캐스트 방식이 따로 있음). 별도의
  "화면에 뭐가 보이는지 실시간 탐지해서 표시"하는 데모/디버그용 기능으로 보임.

---

## 10. Titan 트럭 4분할 카메라에 적용 시 고려할 점 (분석 결론)

1. **나이트비전**: TankSim의 NightVisionPP 패턴(After-Tonemapping PP Material + Blendable weight 토글)을
   그대로 가져다 4방향 카메라 중 하나(또는 전체)에 적용하는 게 가능. 다만 TankSim은 "메인 카메라"에만 적용하는
   구조라, SceneCapture로 찍은 RenderTarget 화면에도 같은 효과를 내려면 **SceneCaptureComponent2D의
   PostProcessSettings에 직접 Blendable을 추가**하는 방식으로 가야 함 (메인 뷰포트의 PostProcessComponent와는
   분리된 설정).
2. **미니맵 투영 패턴(6번)**: 4분할 화면 위에 적/장애물 마커를 오버레이하고 싶다면, `ATankPawn::Tick()`의
   "SceneCapture 트랜스폼 기준 perspective division" 코드를 거의 그대로 재사용 가능 — 각 카메라(전/후/좌/우)별로
   같은 공식을 4번 돌리면 됨.
3. **지면 정렬(7번)**: 트럭이 정지 상태가 아니라 향후 주행 기능이 들어가면, `AEnemyTank`의 동적 지면 스냅
   로직(레이캐스트 + 경사면 보간)이 바로 참고가 됨.
4. **이동 방식**: TankSim 플레이어 탱크는 Chaos Vehicle이 아니라 단순 Force 기반 듀얼 트랙. Titan 트럭도
   주행 기능을 넣게 되면 굳이 복잡한 차량 피직스 없이 이 방식으로 충분히 구현 가능해 보임.
5. **ZibraVDB는 탱크 핵심 기능과 무관**한 부가 VFX이므로, 라이선스 문제는 4분할 카메라 작업과는 별개로
   취급하고 넘어가도 무방.
