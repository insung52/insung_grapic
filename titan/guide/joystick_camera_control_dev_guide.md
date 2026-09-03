> ⚠️ [guide/ 이관 시 경고, 2026-08-31] 2026-07-08 기준 작성 — 이후 조이스틱 버튼 배선이 LIG
> 프로토콜 연동으로 많이 늘어남(`protocol/selfdefense_rc_feature_gap_analysis.md` §3 버튼맵이
> 최신).

# 조이스틱 기반 RCWS/UAV 카메라 조작 개발 문서 (2026-07-08)

`titan_example` 프로젝트에 Logitech Extreme 3D Pro 조이스틱으로 RCWS(TitanTruck/UGV)
및 UAV 짐벌 카메라의 pan/tilt를 조작하는 기능 구현 기록. memo.md의 "조이스틱 제어에
따른 카메라 회전" 항목 구현. 절반 이상이 **조이스틱을 UE5.8에서 인식시키는 과정의
시행착오**라, 나중에 같은 종류의 하드웨어를 다시 붙일 때 참고용으로 상세히 남김.

> **레벨 조작 명령어**(`SetCameraControlTarget` 등)는 `ugv_driving_dev_guide.md`의
> 0절(빠른 시작)에 다른 차량/주행 명령어와 함께 정리되어 있음 — 이미 하드웨어
> 세팅이 끝난 상태로 그냥 쓰기만 할 거면 그쪽만 봐도 됨. 이 문서는 조이스틱을
> 처음부터 새로 붙이거나 인식 문제를 다시 진단해야 할 때 참고.

## 1. 게임 로직 — 카메라 컨트롤 타겟 전환

RCWS 2개(TitanTruck 자체방호용, UGV 탑재용) + UAV 짐벌 카메라 + Idle(조작 안 함),
총 4개 상태 중 하나로 조이스틱 입력이 어디로 갈지 전환하는 구조. `UGVMovementComponent`의
`EUGVDriveMode`(Idle/Manual/Auto, `ugv_driving_dev_guide.md` 11절 참고)와 완전히
같은 패턴 — possess 여부와 무관하게 명령어로 전환.

### 1.1 `ECameraControlTarget` (`titan_examplePlayerController.h`)
```cpp
enum class ECameraControlTarget : uint8 { Idle, TruckRCWS, UGVRCWS, UAVGimbal };
```
`Atitan_examplePlayerController::CameraControlTarget`(기본값 `Idle`)이 유일한 상태.

### 1.2 명령어 — `SetCameraControlTarget`
```
SetCameraControlTarget Idle | TruckRCWS | UGVRCWS | UAV   (대소문자 무관)
```
`SetUGVMode`와 동일한 스타일의 Exec 함수. 레벨의 `ATitanTruck`/`AUGVPawn`/`AUAVPawn`을
lazy 캐싱해서 찾음 (`GetOrFindTruck`/`GetOrFindUGV`/`GetOrFindUAV`).

### 1.3 입력 → pan/tilt 델타 변환 (`DoCameraLook`)
조이스틱 X/Y를 하나의 Vector2D Input Action(`CameraLookAction`)으로 받아, **매 틱
그 값만큼 각도를 누적**(절대 각도가 아니라 각속도 — 조이스틱을 얼마나 기울였는지가
"얼마나 빨리 회전할지"에 대응하는, 일반적인 조이스틱 pan/tilt 조작감):

```cpp
void DoCameraLook(const FInputActionValue& Value)
{
    if (CameraControlTarget == Idle) return;
    const FVector2D Look = Value.Get<FVector2D>();
    const float PanDelta  = Look.X * CameraLookRateDegPerSec * DeltaTime;
    const float TiltDelta = Look.Y * CameraLookRateDegPerSec * DeltaTime;
    switch (CameraControlTarget) {
        case TruckRCWS:  Truck->RCWS->AddPanTiltInput(PanDelta, TiltDelta); break;
        case UGVRCWS:    UGV->RCWS->AddPanTiltInput(PanDelta, TiltDelta);   break;
        case UAVGimbal:  UAV->AddGimbalPanTiltInput(PanDelta, TiltDelta);   break;
    }
}
```

`CameraLookRateDegPerSec`(기본 90도/초)로 감도 조절. **Roll은 건드리지 않음** —
일반 FPS 카메라처럼 pan(yaw)/tilt(pitch)만.

- RCWS 쪽은 `URCWSComponent::AddPanTiltInput`을 그대로 재사용 — 이미 memo.md 스펙대로
  구현되어 있었음 (pan 자유회전, tilt는 `Min/MaxElevationDegrees`로 클램프).
- UAV는 이 기능이 없어서 신규 추가: `AUAVPawn::AddGimbalPanTiltInput` + 클램프용
  `MinGimbalPitchDegrees`(-80)/`MaxGimbalPitchDegrees`(20) — 드론 짐벌이라 아래쪽
  범위를 훨씬 넓게 줌.

> **[2026-09-01 갱신] `UAVGimbal` 타겟은 이제 새 드론(`ADronePawn`)으로 간다.**
> `ApplyUAVGimbalPanTiltInput`이 레벨에서 `ADronePawn`을 먼저 찾고, 없을 때만 구
> `AUAVPawn`으로 폴백한다(구 UAV 제거 전까지의 과도기 구조). 오디오 리스너/뷰타겟 결정과
> 수동 줌 전환(`Server_BeginUAVManualZoomTransition`)도 같은 드론 우선 구조다.
> `ADronePawn`의 클램프는 `MinGimbalPitchDegrees`(-80) / `MaxGimbalPitchDegrees`(**45**),
> 감도는 폰 쪽 `GimbalLookRateDegPerSec`(60). 짐벌 본 회전 구현은
> `vehicle/drone/drone_flight_dev_guide.md` 12절 참고 — 본 회전을 컴포넌트 공간 **절대값**으로
> 넘겨야 한다는 함정이 있다.

바인딩은 `Atitan_examplePlayerController::SetupInputComponent`에서 하고(possess
여부 무관하게 항상 활성 — UGV 수동조작과 같은 이유, 11.3절 참고), `Triggered`
이벤트만 바인딩 — 조이스틱이 중앙으로 돌아오면 그냥 값이 0이 되어 회전이 멈출
뿐이라 `Completed` 핸들러가 따로 필요 없음.

## 2. 조작 UX 부수 변경

카메라 시점 전환이 마우스가 아니라 조이스틱으로 바뀌면서:

- **마우스 커서 항상 표시**: `PlayerController::BeginPlay`에 `bShowMouseCursor = true`
  + `FInputModeGameAndUI`(커서 캡처 안 함) 추가. 예전처럼 뷰포트 클릭 시 마우스가
  사라지는 3인칭 마우스룩 캡처 방식이 이제 안 맞음 — 대시보드 위젯도 클릭해야 하니
  커서가 항상 자유로워야 함. `GameAndUI`라 키보드/조이스틱 입력은 여전히 게임 쪽으로
  들어감.
- **월드 렌더링 기본 OFF**: `bDisableWorldRenderingOnStart`(기본 `true`) 추가,
  `BeginPlay`에서 자동으로 `SetWorldRenderingEnabled(false)` 호출. 대시보드 시나리오는
  QuadCam/RCWS 스캔캡처 피드로만 보여지는 게 목적이라 라이브 3D 뷰포트가 필요 없음
  (렌더 비용 자체가 절약됨, 단순히 숨기는 게 아니라). 필요하면 여전히
  `SetWorldRenderingEnabled(true)` 커맨드로 켤 수 있음.

## 3. 조이스틱 하드웨어 인식 — 시행착오 전체 기록

### 3.1 1차 시도: 엔진 내장 `Raw Input` 플러그인 — 결국 실패

**설정 과정**:
1. Edit > Plugins에서 `RawInput` 활성화 (엔진 내장, `Engine/Plugins/Experimental/RawInput` —
   UE5.8에서 **deprecated 표시**됨, 곧 제거 예정)
2. Project Settings > Raw Input에 컨트롤러 등록: Vendor/Product ID는 **10진수로 입력**
   (16진수 `046D`/`C215` → 10진수 `1133`/`49685`). 장치관리자 하드웨어 ID에서 확인.
3. Axis Properties 배열(디바이스 하나당 24개 축, 96개 버튼 슬롯 고정 준비됨)에서
   실제 쓸 축(X/Y)의 "키" 필드는 이미 기본값 `Generic USB Controller Axis 1/2`로
   채워져 있음 — 이름을 새로 지정하는 게 아니라 그 슬롯을 "활성화"만 해주면 됨.
   "게임패드 스틱" 체크는 켜면 별도로 가상 게임패드(`Gamepad_LeftX/Y`) 쪽으로도
   값을 보냄 — 켜고 끄고 둘 다 테스트했지만 무관하게 안 됐음(아래 참고).

**로그로 확인된 사실**: 디바이스 자체는 정상 인식됨
```
LogRawInputWindows: VendorID:046D ProductID:C215
LogRawInputWindows: Device was registered succesfully and is connected (Usage:4 UsagePage:1)
```

**증상**: 엔진 내장 `PlayerInputDebugger`(아래 3.2절)로 확인해보니 `GenericUSBController_Axis1~5`
같은 **Slate 레벨 raw 이벤트는 계속 들어옴**(조이스틱 움직이는 대로 값 반응) — 근데
**Enhanced Input의 "Player" 레벨 이벤트는 단 한 번도 안 뜸**. 즉 OS→엔진까지는
정상 도달하는데, Enhanced Input(PlayerInput)이 그 이벤트를 전혀 소비하지 못함.

**원인 추정**: RawInput 플러그인 소스(`RawInputWindows.cpp`) 직접 확인 —
`MessageHandler->OnControllerAnalog(KeyName, PrimaryPlatformUser, DefaultInputDevice, Value)`
호출 자체는 정상적인 Primary User/Default Device로 이뤄지는데도 Enhanced Input까지
안 올라감. 웹 검색으로 확인한 UE 5.6+ 알려진 회귀 버그(RawInput 축이 Enhanced Input에
안 들어감, 버튼은 정상)와 증상이 정확히 일치 — RawInput이 UE5.1+ 도입된 최신
Input Device/Platform User 매핑 시스템과 근본적으로 안 맞물리는 것으로 결론.
플러그인 자체가 deprecated인 것과도 일치.

**교훈**: 확실히 "설정 문제 아님"을 진단하려면 (a) 장치 자체 인식 로그 확인 →
(b) `PlayerInputDebugger`로 raw 이벤트가 Slate까지 오는지 확인 → (c) 같은 도구로
Enhanced Input "Player" 이벤트가 뜨는지 확인, 이 세 단계를 분리해서 봐야 함. 이번엔
(a)(b)는 통과, (c)만 계속 실패해서 "설정이 아니라 플러그인 자체 문제"라고 확신할
수 있었음.

### 3.2 `PlayerInputDebugger` — 엔진 내장 디버깅 툴 (마켓플레이스 아님)

`Engine/Plugins/Experimental/PlayerInputDebugger` — Epic 공식, 기본 비활성. 활성화 후
**Window > Developer Tools > Player Input Debugger**로 열림. Slate 레벨 raw 입력
이벤트(`FSlateDebugging::InputEvent`)와 Enhanced Input이 실제 처리한 액션 레벨
이벤트(`FPlayerInputDebugging`)를 **한 테이블에 같이** 실시간 로그로 보여줌 — 각 행에
정확한 FKey 이름, Raw Value, (Player 이벤트면) 어떤 액션/컨트롤러로 갔는지까지 표시.
"raw 키가 엔진에 도달하는가"와 "Enhanced Input이 그걸 액션으로 처리하는가"를 분리해서
보고 싶을 때 이게 정답. (참고: `showdebug EnhancedInput` 콘솔 명령도 액션값 실시간
오버레이를 보여주지만, Slate 레벨 raw 이벤트까지는 안 보여줌 — 더 상위 레벨만 확인
가능.)

### 3.3 2차 시도: vJoy + x360ce (XInput 에뮬레이션) — 포기

RawInput이 근본적으로 안 되니, 조이스틱을 가상 Xbox 컨트롤러(XInput)로 위장시켜서
UE의 네이티브 게임패드 지원(`Gamepad_LeftX/Y` 등, Input Device 시스템과 완전히
호환)으로 우회하는 시도.

- x360ce 최신판(4.17.15.0, x64)이 VC++ 2015-2019 Redistributable(x86) 설치를
  요구했는데 계속 "다른 버전이 이미 설치됨" 충돌 발생 — 결국 안 풀림
- 대체로 구버전(3.2.10.82, x64)을 받아서 실행했더니 `SetupDiGetDeviceRegistryPropertyW`
  Win32 API 에러(코드 122)로 주기적 디바이스 스캔마다 크래시 — 최신 Windows에서 오래된
  SharpDX 기반 코드가 겪는 실제 호환성 버그로 판단, 이 경로는 포기

**교훈**: x360ce는 마지막 정식 릴리즈가 2020년이라 최신 Windows에서 이런 마찰이
생길 여지가 있음. VC++ 재배포 패키지 자체는 지금도 유효하게 관리되는 링크
(`https://aka.ms/vs/17/release/vc_redist.x86.exe` 등, MS 상시 갱신 URL)라 오래된
프로그램 탓은 아니고, x360ce 쪽 구버전 크래시가 실제 원인.

### 3.4 최종 해결: `JoystickPlugin` (SDL2 기반 오픈소스)

https://github.com/JaydenMaalouf/JoystickPlugin

GitHub: `JaydenMaalouf/JoystickPlugin`. RawInput 관련 가이드를 직접 쓴 사람도 결국
이 플러그인으로 갈아타길 권장할 정도로 커뮤니티에서 안정적이라고 알려짐.

**설치**:
1. 릴리즈(4.7.0 기준)에 **UE5.8용 프리빌트 바이너리가 아직 없음**(5.4~5.7까지만) —
   `JoystickPlugin-5.7.zip` 다운받아서 `Plugins/JoystickPlugin/`에 압축 해제 (소스
   포함이라 5.8로 재컴파일 가능)
2. `.uproject` 우클릭 > Generate Visual Studio project files > 빌드
3. Edit > Plugins에서 활성화 확인 → 에디터 재시작
4. **`JoystickPlugin.uplugin`의 `"EngineVersion": "5.7.0"`을 `"5.8.0"`으로 직접
   수정** — 안 그러면 실행할 때마다 "5.7.0용으로 만들어졌는데 그래도 로드할까요?"
   팝업이 매번 뜸 (5.8로 재빌드해서 실제로 잘 작동하니 그냥 메타데이터 표기 문제).

**자체 디버깅 툴**: Project Settings > Plugins > **Joystick Input** > "Open Joystick
Viewer" 버튼 — 연결된 디바이스의 축/버튼/햇스위치 실시간 값을 바로 확인 가능. 로그
파싱이나 별도 디버거 없이 이걸로 바로 확인됨 (RawInput 때와 달리 문제없이 잘 나옴).

**FKey 네이밍 규칙** (`JoystickInputDevice.cpp`, `EKeys::AddKey`로 **디바이스가
연결된 시점에 동적으로 등록**):
```
Joystick_{디바이스이름}_Axis_{번호}   (1부터 시작, "Joystick" 카테고리)
```
정확한 문자열은 디바이스 이름이 그대로 들어가므로, IMC 키 선택창에서 "Joystick"으로
검색해서 눈으로 확인하는 게 제일 확실함 (조이스틱 뷰어에서 반응한 축 번호와
매칭해서 X/Y 고르면 됨).

## 4. Enhanced Input 배선 시 겪은 함정

### 4.1 Swizzle 모디파이어 빠뜨림
X축 키는 Vector2D 액션에 기본으로 X 슬롯에 들어가지만, **Y축 키는 Swizzle Input
Axis Values (YXZ) 모디파이어를 명시적으로 걸어야** Y 슬롯으로 들어감. 이거 없으면
두 축 다 X로만 들어가서 Y가 영영 안 바뀜 — WASD(`IA_Move`)에서 이미 같은 패턴을
썼던 걸 깜빡하고 처음에 빠뜨렸었음.

### 4.2 MCP `ObjectTools.get_properties`로 IMC `Mappings` 배열 읽으면 항상 빈 배열
`UInputMappingContext.Mappings`는 `TArray<FEnhancedActionKeyMapping>`인데, 이 구조체
안에 Trigger/Modifier가 **폴리모픽 UObject 배열**로 들어있어서인지, MCP로 조회하면
실제로 매핑이 있어도 `{"Mappings":[]}`로 잘못 읽힘. **에디터에서 직접 눈으로
확인하는 게 진실** — MCP 조회 결과만 믿고 "매핑이 비어있다"고 판단했다가 틀린 진단을
내린 적 있음 (사용자가 스크린샷으로 실제 매핑이 있는 걸 보여줘서 정정).

### 4.3 확인 순서 정리 (다음에 비슷한 문제 생기면)
1. 로그에서 디바이스 자체가 인식/등록됐는지 (`LogRawInputWindows` 류)
2. `PlayerInputDebugger`(또는 각 플러그인 자체 뷰어)로 raw 값이 실제로 들어오는지
3. IMC 매핑이 에디터에서 실제로 존재하는지 (**MCP 조회 결과 말고 직접 확인**)
4. `showdebug EnhancedInput`으로 액션 값이 최종적으로 바뀌는지

이 네 단계를 순서대로 분리해서 확인하면 "어느 레이어에서 끊겼는지" 바로 특정됨.
