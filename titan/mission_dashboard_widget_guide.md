# 테스트용 통합 대시보드 위젯 (MissionDashboardWidget) 가이드 (2026-07-07)

`memo.md`/`truck.png`/`ugv.png` 기반 최종 대시보드로 가기 전에, **씬캡쳐 뷰들이랑 실제
데이터 연동이 잘 되는지부터 디자인 신경 안 쓰고 확인**하는 용도의 WBP. StatusHUD 만들
때(`status_hud_dev_guide.md`)와 똑같은 패턴 — C++이 위젯 "이름"만 선언해두고, WBP에서
그 이름으로 위젯을 배치하면 자동으로 값이 채워짐. 그래프 노드 연결 같은 거 할 필요 없음.

## 1. 지금 진짜로 연동되는 것 / 더미인 것

| 데이터 | 상태 |
|---|---|
| TitanTruck/UGV 4분할 카메라 (8개) | ✅ 실제 씬캡쳐 |
| UAV 단일 카메라 | ✅ 실제 씬캡쳐 |
| 미니맵 | ✅ 실제 씬캡쳐 (Top-Down) |
| UAV 고도/속도/방향 | ✅ 실제 드론 이동값 |
| UGV 속도/주행거리 | ✅ 실제 UGV 이동값 |
| TitanTruck/UGV RCWS 조준뷰 카메라 | ✅ 실제 씬캡쳐 (팬/틸트는 `RCWS->AddPanTiltInput()`로만 가능, 아직 입력 바인딩 없음) |
| UAV 배터리, UGV 배터리/시스템 상태 | ⚠️ 더미 (자연스럽게 변화하는 값) |
| RCWS 탄약(장전/사격 이펙트 없음) | ⚠️ 더미 (`SetLoaded`/`SetFireReady` 등으로 값만 갈아끼우는 stub) |

## 2. WBP_test에서 배치해야 할 위젯 이름

`WBP_test`(부모 클래스 = `MissionDashboardWidget`, 이미 설정되어 있음)에서 아래 이름으로
위젯을 배치하면 값이 자동으로 채워짐. 이름이 틀리거나 타입이 다르면 조용히 무시되고 그
항목만 안 보임(에러 안 남) — StatusHUDWidget과 동일한 방식.

### 카메라 (Image 위젯, 브러시가 시작할 때 한 번만 자동으로 연결됨)

| 이름 | 소스 |
|---|---|
| `TruckFrontImage` / `TruckRearImage` / `TruckLeftImage` / `TruckRightImage` | TitanTruck 4분할 |
| `UGVFrontImage` / `UGVRearImage` / `UGVLeftImage` / `UGVRightImage` | UGV 4분할 |
| `UAVCameraImage` | UAV 짐벌 카메라 |
| `TruckMinimapImage` / `UGVMinimapImage` | 미니맵 (둘 다 같은 소스 — 레벨에 `AMinimapCaptureActor` 배치되어 있어야 함) |
| `TruckRCWSImage` | TitanTruck RCWS 조준뷰 (자체방호용, 탄약 600) |
| `UGVRCWSImage` | UGV RCWS 조준뷰 (탄약 1200) |

### 상태 텍스트 (TextBlock, 0.2초마다 자동 갱신)

| 이름 | 내용 | 실제/더미 |
|---|---|---|
| `UAVAltitudeText` | "152 m" | 실제 |
| `UAVSpeedText` | "32.6 km/h" | 실제 |
| `UAVHeadingText` | "312°" | 실제 |
| `UAVBatteryText` | "78%" | 더미 |
| `UGVSpeedText` | "12.4 km/h" | 실제 |
| `UGVDistanceText` | "3.27 km" | 실제 |
| `UGVBatteryText` | "87%" | 더미 |
| `UGVSystemStatusText` | "정상" | 더미 |
| `TruckRCWSAmmoText` | "600 / 600" | 더미(stub) |
| `UGVRCWSAmmoText` | "1200 / 1200" | 더미(stub) |

## 3. 만드는 법

1. `WBP_test` 열기 (부모 클래스는 이미 `MissionDashboardWidget`으로 되어있음 — 확인만)
2. 팔레트에서 **Image** 위젯을 필요한 만큼 드래그해서 배치 (Canvas Panel 안에 아무렇게나
   놔도 됨, 지금은 위치 안 중요 — 씬캡쳐 나오는지만 확인)
3. 각 Image를 위 표의 이름으로 정확히 변경 (Details 패널 맨 위 이름 필드) — 다 배치할
   필요 없고, 확인하고 싶은 것만 몇 개 배치해도 됨
4. **TextBlock**도 마찬가지로 필요한 만큼 배치 + 이름 변경
5. 컴파일 + 저장 후 PIE로 재생 — 카메라 4개 + UAV + 미니맵 화면에 뭔가 찍히는지,
   텍스트가 실제 속도/고도랑 같이 변하는지 확인

## 4. 주의할 점

- `AMinimapCaptureActor`를 레벨에 배치 안 했으면 `MinimapImage`는 그냥 비어있음 (에러 아님)
- UAV가 아직 `BeginMissionToTarget()`을 호출받기 전(Idle 상태)이면 고도/속도가 0으로
  찍힘 — PIE 콘솔에서 `BeginMissionToTarget X Y Z` 실행하거나 BP에서 호출해서 움직여봐야
  값 변화 확인 가능
- 이 WBP는 possess 여부랑 무관하게 항상 갱신됨 (StatusHUD의 M키 토글/possession 게이팅과
  다름 — 대시보드는 원래 상시 표시가 목적이라 그런 게이팅 자체가 없음)
- 미니맵처럼 "양쪽 모니터가 같은 걸 보여줘야 하는" 항목은 이름을 하나로 재사용 못 함 — 하나의
  WBP 안에서는 위젯 이름이 중복될 수 없어서(UMG 제약) `TruckMinimapImage`/`UGVMinimapImage`
  두 이름으로 나눠뒀음(같은 `MinimapRenderTarget`을 가리킴). 나중에 진짜로 Left/Right WBP를
  분리하면 각자 독립된 트리라 그때는 둘 다 그냥 `MinimapImage`로 써도 됨

## 5. 다음 단계 (지금 안 한 것)

- truck.png/ugv.png처럼 실제 두 모니터로 나눠서 배치하는 건 이 WBP_test 다음에 진행 —
  지금은 하나의 테스트 캔버스에 다 몰아넣은 것뿐
- RCWS는 방위각/고각(`AzimuthDegrees`/`ElevationDegrees`), 카메라 모드(EO/IR), 사격 모드
  (단발/점사/연사), 장전/사격대기 상태는 아직 이름 안 만들어둠 — 지금은 조준뷰 카메라 +
  탄약만 확인 가능. 필요하면 위 표랑 같은 방식으로 `TruckRCWSAzimuthText` 등 이름만
  추가하면 됨
- RCWS 자체가 실제 탐지/조준/사격 로직이 없는 stub이라(`RCWSComponent.h` 주석 참고),
  `AddPanTiltInput()`도 아직 어떤 입력(조이스틱/마우스)에도 안 묶여있음 — 지금은 BP에서
  직접 호출해야 카메라가 움직임


화면 조작 관련

기본적으로 마우스 보이는 상태에서 시작(아무것도 possess 안한 상태로 시작해야하나?)

tab : 마우스 커서 활성화 해서 다른 장비(ugv, uav, truck) 선택 가능, 근데 tab 누른다고 해서 바로 possess 해제해야하나?

마우스로 화면의 각 장비 구역들을 누르면 해당 장비를 possess? 아니면 따로 각 장비를 선택 가능하게?

허나 possess 랑 자동/수동 전환 기능은 따로 분리해야함.

uav 카메라 : 자동 시점 이동 기능 없음. 사용자가 선택 시 시점 조정 가능

ugv : 자동 주행, 자동 사격 기능 존재. 해당 상태는 따로 변수로 만들고 on off 가능하게 해야함. 즉 possess = 자동 주행 비활성화 및 수동 주행 활성화가 아님.

truck : 주행기능 아예 없음. rcws 에만 자동 사격 기능 존재.

필요한것 : wbp 에서 어떤 구역 


setUGVMode 명령어처럼, rcws 2개 + uav 카메라 + idle(수동 카메라 조정 off) 4개 상태를 전환하는 명령어 추가

logitech extreme 3d pro 조이스틱을 usb 연결 - 해당 컨트롤러로 카메라 상하좌우 각도 조절 가능하게.

