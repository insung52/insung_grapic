# RTSP 카메라 연결 완료 (2026-08-17)

`rtsp_integration_status_0817.md`가 식별한 "실제 카메라를 RtspEncoder 플러그인에 붙이는 접합 작업"을
이 세션에서 끝냄. UGV 5스트림 + 자체방호 7스트림, 총 12개 전부 실제 SceneCapture 영상이
RTSP로 나가는 것까지 VLC로 확인됨.

## TL;DR

- UGV축 5스트림, 자체방호축 7스트림 — 전부 실제 카메라 컴포넌트에 `URtspStreamComponent` 연결 완료.
- 각 프로세스는 **자기 로컬 플레이어의 축에 해당하는 스트림만** 인코딩/서빙함 — 축이 다른
  쪽 스트림은 아예 컴포넌트 자체를 안 만듦(렌더링/NVENC 인코딩 비용 낭비 방지).
- `protocol_icd.md` §3.3/§4.1의 RTSP mount 이름 잠정 문구를 실제 확정값으로 갱신함.
- VLC로 UGV축/자체방호축 각각 실제 영상 수신 확인(사용자 실측, 2026-08-17).

---

## 1. 카메라 소스 확인

`rtsp_integration_status_0817.md`가 지시한 대로, 실제 카메라 연결 전에 소스부터 확인:

| 축 | 스트림 | 소스 |
|---|---|---|
| 자체방호 | 환경카메라 | `ATitanTruck::BattlefieldCapture`(private 멤버) |
| 자체방호/UGV 공용 | CCTV×4 | `UQuadCamComponent::GetFrontCamera()`/`GetRearCamera()`/`GetLeftCamera()`/`GetRightCamera()` |
| 자체방호/UGV 공용 | RCWS뷰어 | `URCWSComponent::GetSightCamera()` |
| 자체방호 | UAV드론뷰 | `AUAVPawn::GetGimbalCamera()`(별도 액터) |

전부 `USceneCaptureComponent2D*`로 확인됨 — `URtspStreamComponent::SourceCapture`에 바로 연결
가능(어댑팅 불필요).

**UGV축 관련 예상 밖 발견**: `BP_UGV_Vehicle`은 자체 C++ Pawn 클래스가 없는 **순수 블루프린트**로,
`WheeledVehiclePawn`(엔진 클래스)을 직접 상속함(unreal-mcp `get_parent`로 확인). `Source/titan_example/
Vehicles/UGVPawn.h/.cpp`(네이티브 `AUGVPawn` 클래스)는 실제로 안 쓰이는 코드였음 — QuadCam/RCWS를
CineCamera-레퍼런스 패턴(`FrontCineCamera` 등)으로 붙인 건 `ATitanTruck`과 동일하지만, 배선은
전부 블루프린트 컴포넌트 목록에서 이루어짐. 이 때문에 UGV축은 자체방호축(네이티브 C++ `BeginPlay`에
코드 추가)과 다른 접근이 필요했음(§3 참고).

---

## 2. 자체방호축 배선 — 네이티브 C++ (`ATitanTruck`/`AUAVPawn`)

`BP_TitanTruck`/`BP_UAV`가 각각 네이티브 `ATitanTruck`/`AUAVPawn`을 상속하는 것을 확인(unreal-mcp
`get_parent`)하고, 해당 클래스에 직접 배선:

- **`Source/titan_example/Vehicles/TitanTruck.h/.cpp`**: `SetupRtspStreams()` 신규 — `BeginPlay()`
  끝(Battlefield/QuadCam/RCWS 캡쳐가 전부 만들어진 뒤)에서 6개 스트림(환경카메라+CCTV×4+RCWS뷰어)에
  `URtspStreamComponent`를 동적 생성(`NewObject`+`RegisterComponent()` — 이 코드베이스의 다른 모든
  동적 SceneCapture와 동일 패턴).
- **`Source/titan_example/Vehicles/UAVPawn.cpp`**: `BeginPlay()`에서 `GimbalCamera` 세팅 직후 UAV드론뷰
  1스트림 추가.

## 3. UGV축 배선 — 신규 컴포넌트 (`UVehicleRtspBridgeComponent`)

`BP_UGV_Vehicle`이 순수 블루프린트라 네이티브 `BeginPlay`에 코드를 못 넣으므로, 새 재사용 가능
액터 컴포넌트를 만들어서 블루프린트의 컴포넌트 목록에 추가하는 방식 사용:

- **`Source/titan_example/Vehicles/VehicleRtspBridgeComponent.h/.cpp`**(신규) — 소유 액터에서
  `UQuadCamComponent`/`URCWSComponent`를 `FindComponentByClass`로 찾아 5개 스트림(CCTV×4+RCWS뷰어)
  배선. `MountPrefix`(기본 `"ugv/"`) 프로퍼티로 mount 이름 접두사 설정 가능 — 재사용성 위해
  일반화(다른 축에도 이론상 재사용 가능).
- 컴포넌트 순서(QuadCam/RCWS보다 먼저 등록됐는지)에 의존하지 않도록 **next-tick으로 지연 실행**
  (`SetTimerForNextTick`) — BP_UGV_Vehicle Details 패널의 컴포넌트 목록 순서는 이 클래스가
  통제할 수 없어서, 순서 의존 대신 "액터의 첫 Tick 전엔 모든 컴포넌트 BeginPlay가 끝나 있다"는
  보장에 의존.
- unreal-mcp `ActorTools.add_component`로 `BP_UGV_Vehicle`에 `RtspBridge`라는 이름으로 실제 추가,
  `compile_blueprint` + `save_assets`까지 완료.

## 4. 플러그인/빌드 설정

- **`titan_example.uproject`**: `RtspEncoder` 플러그인이 `Plugins` 목록에서 아예 빠져있었음(빌드는
  돼 있었지만 프로젝트가 로드 안 함) — `{"Name": "RtspEncoder", "Enabled": true}` 추가.
  ⚠️ 이 파일은 P4 체크아웃이 필요한데 이 세션의 P4 클라이언트가 서버에 인증이 안 돼서(`Client
  'DESKTOP-81S78B2' unknown`) 정식 체크아웃을 못 했음 — 파일 속성만 풀고 직접 편집함. **제출 전
  P4 상태 확인 필요**(`p4 reconcile` 등).
- **`Source/titan_example/titan_example.Build.cs`**: `PrivateDependencyModuleNames`에 `RtspEncoder`
  추가(게임 모듈이 `RtspStreamComponent.h`를 include할 수 있도록).

## 5. 축 게이팅 — `FRtspAxisGate` (2026-08-17 후반 추가)

**배경**: `BP_UGV_Vehicle`과 `BP_TitanTruck`이 같은 레벨(`kadex_test`)에 배치돼 있어서, 리슨서버
두 프로세스(UGV축 호스트 / 자체방호축 클라이언트) 어느 쪽에서 실행하든 **두 액터의 `BeginPlay`가
항상 둘 다 돎** — 게이팅 없이는 "UGV 프로세스"에서도 자체방호축 7스트림을 전부 NVENC 인코딩+RTSP
서빙하게 되고 그 반대도 마찬가지. 사용자가 렌더링/인코딩 비용 낭비를 지적해서 추가.

- **`Source/titan_example/Vehicles/RtspAxisGate.h/.cpp`**(신규) — 이 프로세스의 로컬 플레이어
  `Atitan_examplePlayerController::PlayerAxis`(리플리케이트 프로퍼티, `?Axis=UGV`/`?Axis=SelfDefense`
  접속 옵션으로 서버 권위 결정됨)를 확인해서, 맞는 축일 때만 콜백을 호출하는 공용 헬퍼.
  `PlayerAxis`가 액터 `BeginPlay` 시점엔 아직 리플리케이트 안 돼있을 수 있어 0.1초 간격, 최대
  5초까지 재시도.
- `TitanTruck::SetupRtspStreams()`/`AUAVPawn`의 UAV드론뷰 스트림 생성/`VehicleRtspBridgeComponent::
  WireRtspStreams()` 전부 이 게이트를 통과해야만 실행됨. **QuadCam/RCWS/Battlefield 카메라 자체의
  SceneCapture 렌더링은 안 건드림** — 각 프로세스 자기 대시보드 표시용으로 기존부터 필요한 부분이라
  그대로 두고, 비용이 큰 NVENC 인코딩+RTSP 서빙만 막음.

### 5-1. 발견/수정한 버그: `GetFirstPlayerController()`가 엉뚱한 컨트롤러를 집음

첫 구현(`World->GetFirstPlayerController()` 사용)은 **양쪽 축 다** 스트림이 하나도 안 만들어지는
회귀를 냈음. 원인: **`AUGVAIController`(`UGVAIController.h:40`, UGV pawn의 `AutoPossessAI`용
컨트롤러, 이름과 달리 실제로는 `APlayerController`를 상속함)**가 `World->PlayerControllerList`에서
진짜 사람 플레이어의 컨트롤러(`BP_TestPlayerController`)보다 앞에 와서, `GetFirstPlayerController()`가
매번 `BP_UGVAIController_C`를 반환 → `Cast<Atitan_examplePlayerController>` 항상 실패 →
`PlayerAxis`가 영원히 `Unspecified`로 보여서 5초 타임아웃 후 아무 축도 안 만듦.

**수정**: `World->GetFirstPlayerController()` → `UGameplayStatics::GetPlayerController(World, 0)`
(GameInstance의 `LocalPlayers` 배열 기반이라 저런 "이름은 AIController인데 실제론 PlayerController"
객체에 안 흔들림).

**다음에 이 프로젝트에서 "로컬 플레이어 컨트롤러 찾기"가 필요하면**: `World->GetFirstPlayerController()`
쓰지 말 것 — `UGameplayStatics::GetPlayerController(World, 0)` 또는 `World->GetFirstLocalPlayerFromController()`
계열을 쓸 것. `AUGVAIController`가 `APlayerController` 파생이라는 것 자체가 이 코드베이스의 특이점이라
비슷한 버그가 다른 곳에도 있을 수 있음(grep해볼 가치 있음, 이번 세션에선 안 함).

## 6. Mount 이름 확정 (`protocol_icd.md` §3.3/§4.1 갱신)

`<axis>/<stream>` 패턴으로 확정 — 실제 `URtspStreamComponent::MountPath` 값과 1:1 대응:

| 축 | Mount |
|---|---|
| UGV | `ugv/front_cctv`, `ugv/rear_cctv`, `ugv/left_cctv`, `ugv/right_cctv`, `ugv/rcws` |
| 자체방호 | `selfdefense/env_camera`, `selfdefense/front_cctv`, `selfdefense/rear_cctv`, `selfdefense/left_cctv`, `selfdefense/right_cctv`, `selfdefense/rcws`, `selfdefense/uav_gimbal` |

포트는 양쪽 다 8554(`RtspServerSubsystem` 기본값 그대로). `protocol_icd.md` §3.3/§4.1/§6의 "잠정"
문구를 이 확정값으로 갱신함(자체방호축 PC의 실제 IP는 여전히 미확정 — §6 그대로 남겨둠).

## 7. `rtsp_viewer_test/` 갱신

- `streams_config.real.example.json`(UGV) — path를 실제 확정 mount(`ugv/front_cctv` 등)로 갱신
  (예전엔 flat `front_cctv`/`rcws_viewer` 추정치였음).
- `streams_config.selfdefense.example.json`(신규) — 자체방호축 7스트림용, 이전엔 이 폴더가
  UGV축만 다뤘음.
- `README.md` 갱신 — 위 변경사항 반영.
- (검증 과정에서 만들었던 `streams_config.pie_local_12.json`은 축 게이팅이 들어간 뒤로는 한
  프로세스에서 12개가 동시에 안 뜨므로 더 이상 유효하지 않아 삭제함.)

---

## 검증 상태

- **VLC로 개별 스트림 재생 확인(사용자 실측, 2026-08-17)** — UGV축/자체방호축 각각 자기 축
  스트림만 뜨는 것까지 확인됨(§5의 축 게이팅 버그 수정 후).
- **`rtsp_test_client.py` 자동화 테스트는 미완**: (1) 이 세션에서 12스트림을 한 프로세스에 합쳐
  테스트하려 했으나 사용자가 "실제 배포는 UGV/자체방호가 서로 다른 PC라 이 방식은 대표성이 없다"고
  지적 + 축 게이팅으로 애초에 불가능해짐 — VLC 개별 확인으로 대체함. (2) 이 클라이언트의
  `print_report`가 `cp949` 콘솔 인코딩에서 em dash(—) 때문에 크래시하는 버그를 발견함(미수정 —
  `PYTHONIOENCODING=utf-8`로 우회 가능, 근본 수정은 `rtsp_test_client.py`를 만든 Track3 세션 영역).

## 알려진 남은 일 / 확인 필요

1. **`titan_example.uproject` P4 상태 확인** — 이 세션이 인증 문제로 정식 체크아웃 없이 직접
   편집함, 제출 전 `p4 reconcile` 등으로 정리 필요.
2. **자체방호축 PC의 실제 고정 IP 미확정** — `protocol_icd.md` §6, LIG 확인 필요.
3. **RTSP 서버 바인드 주소 미확인** — `RtspServerSubsystem.cpp`에 명시적 바인드 주소 코드가 없어
   gst-rtsp-server 기본값(추정 `0.0.0.0`, 모든 인터페이스)을 쓸 것으로 보이는데, 실제 두 PC 간
   네트워크로 테스트해서 확인 필요(지금까지는 전부 로컬 `127.0.0.1` 테스트만 함).
4. **진짜 2-프로세스(호스트 PC + 클라이언트 PC) 리슨서버 환경 검증은 아직 안 함** — 이번 검증은
   로컬 PC 하나에서 축을 UGV↔SelfDefense로 전환해가며 순차 테스트한 것으로 대체함. `UGameplayStatics::
   GetPlayerController(World, 0)`가 진짜 네트워크 클라이언트 프로세스에서도 동일하게 동작하는지는
   이론상 맞지만(로컬 플레이어 인덱스 기반이라 프로세스 무관) 실측은 아님.
5. **`rtsp_test_client.py`의 cp949 크래시** — §"검증 상태" 참고, 근본 수정 필요하면 Track3 세션
   영역.
