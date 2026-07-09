# 카메라 기반 객체 탐지 모사 (RCWS/UAV 바운딩 박스) 개발 문서 (2026-07-09)

## 0. 배경 및 방식 선택

`minimap.md`/`memo.md` 요구사항: RCWS(트럭 자체방호/UGV)·UAV 카메라가 적군을 감지하면
화면에 바운딩 박스를 표시하고(아군 초록/적군 빨강, `minimap.md`), 그 감지 결과가
미니맵의 정확한 위치 마커로도 이어져야 함. `memo.md` 의문사항 1이 "피아식별을 실제
객체탐지 or postprocessing 등으로 처리?"를 미확정으로 남겨뒀던 부분.

**실제 YOLO 등 객체탐지 모델은 채택 안 함.** 우리는 씬에 있는 모든 액터의 정확한
위치/크기를 이미 알고 있으므로(합성 이미지에서 라벨을 역추론하는 게 아니라 애초에
정답을 갖고 시작), 실제 이미지를 픽셀 단위로 분석할 이유가 없음. 대신 **기하학적
투영 + 가시선(occlusion) 판정** 방식— 카메라 시점으로 대상을 투영해서 화면
좌표를 구하고, 라인트레이스로 실제 보이는지 확인해서 "탐지됐다"고 가정하는
postprocessing 방식을 선택. 실제 UE 프로젝트에서 ESP류 표시에 흔히 쓰는 정통적인
기법이고, GPU readback도 필요 없어서 가볍고 디버그하기 쉬움.

진짜 세만틱 세그멘테이션(커스텀 스텐실 ID로 각 액터를 마킹 후 별도 렌더 패스로
픽셀 분석) 방식도 검토했지만, 우리는 액터 리스트를 이미 알고 있어서 그 무거운
GPU readback을 할 이유가 없어 채택 안 함.

## 1. 파일 구조 및 데이터 흐름

```
titan_example/Source/titan_example/Detection/
  DetectionTypes.h                  EMilitaryFaction, FDetectedTarget (플레인 데이터)
  DetectableTargetComponent.h/.cpp  "나는 탐지 대상이다" 마커 + Faction, 레지스트리 자동 등록/해제
  DetectableTargetSubsystem.h/.cpp  UWorldSubsystem 기반 탐지 대상 레지스트리
  TargetDetectionComponent.h/.cpp   핵심 스캔 로직 — 카메라별로 하나씩 붙음

titan_example/Source/titan_example/UI/
  DetectionOverlayWidget.h/.cpp     WBP용 바운딩 박스 그리기 (Slate 커스텀 페인트)
  MissionDashboardWidget.h/.cpp     TruckRCWSDetectionOverlay/UGVRCWSDetectionOverlay/
                                     UAVDetectionOverlay 필드로 연결
```

데이터 흐름:
1. `TitanTruck`/`AUGVPawn`/`AUAVPawn` 생성자에서 `DetectableTargetComponent`(Faction
   마커) + `TargetDetectionComponent`(스캐너)를 둘 다 붙임 — 모든 차량이 "탐지될 수도
   있고 탐지할 수도 있는" 존재
2. `DetectableTargetComponent`는 `BeginPlay`에 `UDetectableTargetSubsystem`에 자기
   자신을 등록(`EndPlay`에 해제)
3. `TargetDetectionComponent`는 0.1초(`ScanIntervalSeconds`)마다 그 레지스트리를
   순회하며 자기 자신을 뺀 모든 대상을 평가, `DetectedTargets` 배열을 갱신
4. `UMissionDashboardWidget`이 매 0.2초(`TextRefreshIntervalSeconds`)마다
   `DetectedTargets`를 해당 카메라의 `UDetectionOverlayWidget`으로 넘겨서 그림

## 2. UDetectableTargetComponent / UDetectableTargetSubsystem

- `Faction`(Friendly/Enemy) 프로퍼티 하나만 가진 아주 작은 마커 컴포넌트. 지금은
  트럭/UGV/UAV 셋 다 `Friendly`로 세팅(차량-대-차량 상호 탐지 테스트 단계 — 6절 참고)
- `UDetectableTargetSubsystem`은 `TArray<TWeakObjectPtr<UDetectableTargetComponent>>`
  레지스트리만 들고 있는 `UWorldSubsystem`. 매 스캔마다
  `UGameplayStatics::GetAllActorsOfClass`로 레벨 전체를 훑는 대신 이 레지스트리만
  순회 — 지금은 차량 몇 대뿐이라 체감 차이 없지만, 나중에 병사 45명이 추가돼도
  가벼움

## 3. UTargetDetectionComponent — 핵심 스캔 로직

### 3.1 카메라 참조

`URCWSComponent::SightCameraRef`와 똑같은 `FComponentReference`-by-name 패턴.
기본값은 `"RCWSSightCamera"`(트럭/UGV RCWS 공통 이름)이고, `AUAVPawn`은 생성자에서
`TargetDetection->CameraRef.ComponentProperty = FName("GimbalCamera")`로 재지정.

### 3.2 화면 투영 수학 (`ProjectToScreenUV`)

씬 캡처 컴포넌트는 플레이어 카메라가 아니라서 `UGameplayStatics::ProjectWorldToScreen`을
못 씀 — 직접 View/Projection 행렬을 구성해서 투영:

```cpp
const FMatrix ViewMatrix = FTranslationMatrix(-ViewLocation) * FInverseRotationMatrix(ViewRotation) *
    FMatrix(FPlane(0,0,1,0), FPlane(1,0,0,0), FPlane(0,1,0,0), FPlane(0,0,0,1));

const float AspectRatio = TextureTarget->SizeX / (float)TextureTarget->SizeY;
const float HalfFOVRadians = FMath::DegreesToRadians(Camera->FOVAngle) * 0.5f;
const FMatrix ProjectionMatrix = FPerspectiveMatrix(HalfFOVRadians, AspectRatio, 1.f, LocalNearPlane);

const FVector4 Clip = (ViewMatrix * ProjectionMatrix).TransformFVector4(FVector4(WorldPoint, 1.0));
// Clip.W <= 0 → 카메라 뒤. NDC = Clip.XY / Clip.W, UV = NDC를 0..1로 리매핑(Y는 뒤집음)
```

이 식은 감으로 짠 게 아니라 **UE 5.8 엔진 소스를 직접 대조해서 검증**함:
- 뷰 행렬 구성 순서/축 스왑 — `Engine/Private/SceneView.cpp`의
  `FViewMatrices::UpdateViewMatrix` 그대로
- 투영 행렬(half-FOV, aspect 적용 방식) — 실제 씬 캡처가 쓰는
  `Renderer/Private/SceneCaptureRendering.cpp`의 `BuildProjectionMatrix`
  (`FMinimalViewInfo`/플레이어 카메라용 `CalculateProjectionMatrixGivenViewRectangle`이
  아니라 이쪽이 진짜 씬 캡처 경로 — 둘이 FOV를 다루는 방식이 미묘하게 다름, 8.3절
  트러블슈팅 참고)

가장자리 근처 판정: 클립 좌표의 원시 NDC가 프러스텀 경계(±1.0)를 살짝 넘는
±1.2까지는 허용(`ProjectToScreenUV`가 여기서 false 반환) — 바운딩박스 코너
하나가 화면 밖으로 살짝 나가도 나머지로 그럴듯한 박스를 그리기 위함. 그보다
심하게 벗어난(카메라 완전히 반대편을 보는 등) 코너는 버림.

### 3.3 오리엔티드(회전 반영) 바운딩 박스

`AActor::GetActorBounds()`/`GetComponentsBoundingBox()`는 **월드 축 정렬** 박스라서,
차량이 카메라 기준 대각선으로 서있으면 회전된 형태를 다 담으려고 박스가 실제보다
커짐(단, 이 효과 자체는 미미함 — 8.1절에서 실제 원인이 아니었다고 재확인한 기록
있음). 대신 `AActor::CalculateComponentsBoundingBoxInLocalSpace()`로 **액터 로컬
좌표계** 박스를 구하고, 8개 꼭짓점을 액터의 실제 월드 트랜스폼(회전 포함)으로
개별 변환한 뒤 투영:

```cpp
const FBox LocalBox = CandidateTarget->CalculateComponentsBoundingBoxInLocalSpace(false);
const FTransform ActorTransform = CandidateTarget->GetActorTransform();
// 8개 꼭짓점(Min/Max 조합) 각각을 ActorTransform.TransformPosition()으로 개별 변환 후 투영
```

이러면 차량이 어느 각도로 서있든 실제 형태에 맞는 박스가 나옴. 8개 코너의 월드 Z
범위(`MinWorldZ`/`MaxWorldZ`)도 여기서 같이 뽑아서 3.4절 오클루전 샘플링에 재사용
(별도로 월드 AABB를 다시 구하지 않음).

### 3.4 다중 포인트 오클루전 샘플링 + Confidence 히스테리시스

라인트레이스 하나로 중심점만 확인하면 반쯤 가려진 상황이 "전부 보임"/"전혀 안
보임" 둘 중 하나로만 판정됨 — 실제 객체탐지 모델의 "많이 보일수록 탐지 확률이
높아진다"는 특성과 안 맞음. 그래서:

1. 타겟의 세로축(3.3절 박스의 Min~Max Z)을 `SamplePointCount`(기본 3)개로 나눠
   각각 라인트레이스 — 단, `VerticalSampleInsetFraction`(기본 0.2)만큼 상/하단에서
   안쪽으로 들여서 샘플링(20%~80% 구간). 포탑 끝처럼 얇게 튀어나온 부분에 샘플이
   찍히면, 언덕 너머로 그 끝만 살짝 보여도 계속 "탐지됨"으로 남는 문제가 있었음
   (8.4절 트러블슈팅)
2. 이번 스캔의 `VisibleFraction = 안 가려진 점 개수 / 전체 점 개수`
3. 타겟별로 유지되는 `Confidence`(0..1)가 `VisibleFraction` 쪽으로
   `FMath::FInterpConstantTo`(초당 `ConfidenceLerpSpeed`, 기본 1.5)로 서서히
   이동 — 즉시 스냅 안 하고 부드럽게, 한 스캔의 순간적 흔들림을 완화
4. **히스테리시스**: 신규 탐지는 `Confidence >= AcquireConfidenceThreshold`(0.6)
   넘어야 뜨고, 이미 탐지된 건 `Confidence >= LoseConfidenceThreshold`(0.5)로만
   유지. `SamplePointCount=3`일 때 `VisibleFraction`은 0, 1/3(0.33), 2/3(0.67),
   1만 나올 수 있는데, 0.5는 1/3과 2/3의 정확한 중간이라 **3점 중 최소 2점이
   보여야만 탐지가 유지**되고 양쪽으로 여유가 똑같이 남음. (기어 변속 히스테리시스
   — `UUGVMovementComponent::GearHysteresisKmH` — 와 같은 아이디어)

### 3.5 탐지 거리

클래스 기본값 `MaxDetectionRange = 40000.f`(400m, memo.md의 미해결 "UAV 영상 피드의
400m" 수치를 그대로 채용 — UAV는 이 기본값 사용). `AUGVPawn`/`ATitanTruck`은
생성자에서 `200000.f`(2km, 실제 UGV RCWS 스펙)로 오버라이드.

## 4. WBP 연동 — UDetectionOverlayWidget

`Source/titan_example/UI/LineGraphWidget.h`(`SLineGraph`)·`CompassWidget.h`
(`SCompass`)와 동일한 "Slate 커스텀 페인트를 `UWidget`으로 감싸는" 기존 패턴을
그대로 재사용:

- `SDetectionOverlay : public SLeafWidget` — `OnPaint`에서 `Detections` 배열을
  순회하며 `ScreenMinUV`~`ScreenMaxUV`를 `AllottedGeometry.GetLocalSize()`에 곱해
  로컬 픽셀 좌표로 변환, `FSlateDrawElement::MakeLines`로 사각형 4변을 그림
  (Faction별 초록/빨강)
- `UDetectionOverlayWidget : public UWidget` — WBP 디자이너에 드래그해서 쓸 수 있는
  래퍼. `LineThickness`/`FriendlyColor`/`EnemyColor` 노출

**중요한 전제**: 이 오버레이 위젯은 대응하는 카메라 `Image` 위젯과 **정확히 같은
위치/크기**로 겹쳐놔야 함 — `ScreenMinUV`/`MaxUV`가 카메라가 찍은 프레임 전체를
기준으로 한 0..1 비율이기 때문에, 오버레이 위젯의 로컬 0..1 공간이 그 프레임과 1:1로
맞아떨어져야 함(8.1절 트러블슈팅에서 이 전제가 깨진 게 아닌지 의심했다가 결국
아니었던 것으로 결론).

### WBP 설정 방법

1. `TruckRCWSImage`/`UGVRCWSImage`/`UAVCameraImage` 각각 위에 **`Detection Overlay
   Widget`을 정확히 같은 Position/Size로** 얹기
2. 이름을 각각 정확히 `TruckRCWSDetectionOverlay` / `UGVRCWSDetectionOverlay` /
   `UAVDetectionOverlay`로 (`MissionDashboardWidget`의 `BindWidgetOptional` 이름
   매칭 — 그래프 작업 불필요)
3. 컴파일 → Play

## 5. 시각적 디버그 (`bDebugDrawDetection`)

`TargetDetectionComponent`의 `bDebugDrawDetection`(기본 false)을 켜면:
- 매 스캔 세로 샘플 포인트 위치에 `DrawDebugSphere`(안 가려짐=초록, 가려짐=빨강)
- 로그에 `visible=... confidence=... active=...` 한 줄
- 박스 크기 디버깅용 상세 로그(`box-size-check`) — 대상의 로컬 박스 크기, 카메라와의
  거리, FOV/aspect, 계산된 UV 범위까지 한 줄에 출력 (8.2절 참고)

**주의**: `bDebugDrawDetection`을 켠 상태로 플레이하면 WBP의 모든 `Image` 위젯이
검은 화면이 되는 버그가 있음(8.1절) — 확인 끝나면 반드시 꺼야 함. 평소 동작 확인은
로그만으로 충분(로그는 이 버그와 무관).

## 6. 향후 작업 — 적군/아군 병사 연동

지금은 차량 3대(트럭/UGV/UAV)가 서로를 Friendly로 탐지하는 상태까지만 구현됨
(파이프라인 검증 목적, 회전·거리·오클루전 다 정상 확인됨). 실제 적군 15명/아군
30명(`memo.md`)은 아직 스폰 로직 자체가 없음.

조사해둔 것: `Content/Tutorial/Blueprints/Enemy/BP_Enemy`가 이미 프로젝트에 있고
(에픽 기본 템플릿이 아니라 별도 FPS 튜토리얼 애셋팩), 낙하산 강하 → 랜덤 지점
배회 → 피격 시 사망(체력/사망 애니메이션 2종/래그돌/자동 삭제) 로직까지 완비돼있고
**능동적 전투 AI는 전혀 없음**(순수 배회+반응만) — RCWS 사격 판정에서
`ApplyDamage`/`ApplyPointDamage`만 호출해주면 바로 쓸 수 있는 상태. 계획은:
- 적군: `BP_Enemy`를 거의 그대로 재사용, `UDetectableTargetComponent`(`Faction=Enemy`)만
  추가
- 아군: `Content/Characters/Soldier/Rifle_Aiming_Idle` 메시(정적 사주경계 포즈) 활용,
  더 가벼운 액터로 별도 구현 예정 — 아직 미착수

## 7. 트러블슈팅 기록 (겪은 순서대로)

### 7.1 `DrawDebugSphere` 켜면 WBP `Image` 위젯이 전부 검은 화면

이 프로젝트가 `bDisableWorldRenderingOnStart=true`(월드 렌더링 기본 꺼짐,
`ugv_driving_dev_guide.md` 참고)인 상태에서 `DrawDebugSphere`/`DrawDebugLine`을
호출하면, 메인 뷰포트 렌더링 패스에서 같이 플러시됐어야 할 디버그 라인배처가
그 패스가 스킵되면서 처리 안 되고, Slate/UMG가 같이 쓰는 렌더 자원에 영향을 줘서
WBP 렌더링 자체가 깨지는 것으로 보임(엔진 내부 메커니즘까지 100% 규명은 못 했지만,
이 프로젝트에서 최소 2번 독립적으로 재현됨 — 이전엔 트랙 접지 판정 디버그
스피어에서도 동일 증상). `bDisableWorldRendering` 자체가 씬 캡처를 막는 건
아님(엔진 소스로 확인 — `GameViewportClient.cpp`에서 메인 플레이어 뷰만 감쌈).

**대응**: `bDebugDrawDetection`은 기본 꺼짐으로 두고, 확인 끝나면 바로 끄기. 평소엔
로그만으로 검증.

### 7.2 UAV 박스가 대상보다 ~10배, 트럭/탱크는 ~5배 크게 그려짐

두 가지가 겹쳐있었음:

1. **UAV 전용 — 실제 원인**: `BP_UAV`의 `BodyMesh`에 붙어있던 메시가
   `/ControlRig/Controls/ControlRig_Diamond_3mm`(애니메이션 리깅용 기즈모 다이아몬드
   플레이스홀더, 드론 메시 아님). 이름의 "3mm"는 컨트롤리그 에디터에서 화면상 항상
   일정 크기로 보이게 하는 특수 렌더링 규칙을 가리키는 거고, 실제 메시 로컬 바운드는
   MCP로 직접 확인해보니 100×100×140cm — 일반 StaticMeshComponent로 스케일 1.0
   그대로 붙이면 그 실제 크기가 적용됨. 트럭(스케일 0.03, 490×200×220cm)/UGV(스케일
   0.5, 567×253×179cm)는 원본 메시 크기 대비 스케일 보정이 이미 되어 있어서 정상.
   → 코드 버그 아님, 드론용 임시 메시를 나중에 제대로 된 것으로 교체하거나 스케일
   조정 필요(아직 미해결, 우선순위 낮음).

2. **트럭/탱크도 처음엔 "회전 때문"이라고 오판**했었음 — 사용자가 "정육면체가
   회전하면 화면 면적이 커지는 게 당연하다, 그 정도로는 5배 설명 안 된다"고
   정확히 지적해서 재검증. 투영 행렬을 엔진 소스와 다시 대조했으나 수식 자체는
   문제 없었고(3.2절), 실제로는 **재빌드/재시작 이후 문제가 저절로 해결됨**
   (정확한 근본 원인은 특정 못함 — 아마 이전 빌드/에디터 상태가 꼬여있었던 것으로
   추정, Live Coding 관련 이슈였을 가능성). 3.3절의 오리엔티드 박스 수정 자체는
   여전히 유효하고 유지함(회전 시 박스가 실루엣에 더 타이트하게 맞음 — 정상적인
   동작이지, "터무니없이 큰" 문제의 원인은 아니었음).

**교훈**: 코드를 재검증하기 전에 먼저 관련 애셋(특히 플레이스홀더로 대충 붙여둔
메시)의 실제 스케일/바운드부터 MCP로 확인하는 게 빠름.

### 7.3 언덕 너머로 대상이 거의 안 보이는데 박스가 안 사라짐

3.4절 참고 — 세로 샘플 포인트가 대상의 진짜 꼭대기(포탑 끝)에 딱 붙어있어서, 그
끝만 언덕 위로 살짝 튀어나와도 3점 중 1점(confidence 0.33)이 계속 잡히고, 당시
`LoseConfidenceThreshold=0.25`였어서 0.33 > 0.25라 안 떨어져 나감.
`VerticalSampleInsetFraction`로 샘플을 안쪽으로 들이고, `LoseConfidenceThreshold`를
0.5로 올려서(3점 중 2점 이상 필요) 해결.
