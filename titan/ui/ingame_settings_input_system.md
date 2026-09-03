# 인게임 Settings 메뉴 / Input 리매핑 시스템 (2026-08-21)

Axis Selection 화면의 **Settings** 버튼으로 여는 인게임 설정창. 이번 세션에 **Input 탭**(키/조이스틱
리매핑)을 완성했고, Graphics/Network/Sounds 탭은 틀만 있음(다음 세션 작업 대상). 부수적으로
JoystickPlugin의 리눅스 SDL2 링킹 문제도 이번 세션에 해결됨(플러그인 자체 이슈, 아래 0번 참고).

## 0. 배경 — JoystickPlugin 리눅스 대응

`Plugins/JoystickPlugin`(오픈소스 SDL2 래퍼)이 원래 `PlatformAllowList: ["Win64"]`로 리눅스에서
꺼져있었음(SDL2 vs 엔진 자체 SDL3 정적 링크 충돌로 패키징 실패했었기 때문). SDL2를 정적 대신
공유 라이브러리로 크로스컴파일하고(`C:\UnrealToolchains\v26_clang-20.1.8-rockylinux8` 툴체인),
SDL2/SDL3 둘 다에 동일하게 존재하는 8개 함수(`SDL_Init`, `SDL_GetError` 등)를 컴파일 타임에
`-D` 매크로로 리네임해서 심볼 충돌 없이 리눅스 지원 활성화함. 결과물:
- `Plugins/JoystickPlugin/JoystickPlugin.uplugin` — Linux 추가
- `Plugins/JoystickPlugin/Source/JoystickPlugin/JoystickPlugin.Build.cs` — Linux 링크 브랜치 채움
- `Plugins/JoystickPlugin/Source/ThirdParty/SDL2/Linux/libSDL2-2.0.so`, `libSDL2-2.0.so.0` — 크로스컴파일된 실제 바이너리

이 단계에서 근본 원인 하나를 더 발견함: **SDL이 리포트하는 조이스틱 이름이 윈도우/리눅스에서
다름**(예: 윈도우 "Extreme 3D pro" vs 리눅스 "Logitech Extreme 3D pro"). JoystickPlugin은 이
이름을 그대로 FKey 이름에 박아 넣어서(`Joystick_<DeviceName>_Axis_0` 식), IMC에 한쪽 플랫폼
이름으로만 키를 박아두면 다른 플랫폼에서 조용히 매칭 실패함(에러 없이 그냥 입력이 안 들어옴). 이게
바로 아래 Input 탭을 만들게 된 근본 동기 — "어떤 하드웨어를 연결하든 게임 안에서 직접 키를
고를 수 있게" 하면 이 플랫폼별 이름 문제 자체가 사라짐.

## 1. 전체 구조

```
AxisSelectionWidget  ──[Settings 버튼]──▶  GameSettingsWidget (WBP_GameSettings)
                                              ├─ TabSwitcher: Graphics / Network / Sounds / Input
                                              └─ Input 탭
                                                   └─ KeybindListContainer (ScrollBox)
                                                        └─ KeybindRowWidget (행 하나 = 리매핑 가능한 액션 하나)
                                                             ├─ Boolean/Axis1D 행 → KeybindSlotWidget 여러 개(낱개, 자유 추가/삭제)
                                                             └─ Axis2D 행        → KeybindAxisPairWidget 여러 개(X/Y 페어 단위 추가/삭제)
                                                   └─ JoystickViewerButton → JoystickViewerWidget (에디터의 Project Settings ▸
                                                                              Joystick Input ▸ Open Joystick Viewer를 게임 안에
                                                                              재구현한 것 — 조이스틱 축/버튼 실시간 확인용)
```

WBP들은 전부 C++ 클래스에 `BindWidgetOptional`로 이름/타입만 맞으면 자동 연결(그래프 작업 불필요).
실제 위젯 이름 목록은 각 헤더 파일(`Source/titan_example/UI/*.h`) 상단 코멘트에 있음.

## 2. Input 탭 백엔드 — 왜 엔진 기본 시스템을 버렸나

처음엔 UE5.8 내장 `UEnhancedInputUserSettings`("Player Mappable Keys")를 그대로 썼는데, 이 시스템은
**IMC가 미리 정의해둔 고정 슬롯의 키만 갈아끼우는** 구조라는 게 드러남 — "플레이어가 원본 IMC에
없던 완전히 새 슬롯(예: 새 조이스틱 버튼)을 추가한다"는 시나리오 자체를 지원 못 함. 구체적으로 겪은
버그들:
- **대각선 버그**: CameraLook처럼 한 Row에 X축(모디파이어 없음)/Y축(Swizzle 모디파이어) 슬롯이
  같이 있으면, 엔진의 `GetPlayerMappedKeysForRebuildControlMappings()`가 슬롯을 구분 안 하고
  느슨하게 매칭해서 서로 다른 슬롯의 키가 섞여 들어감 → 조이스틱을 어느 방향으로 움직여도 항상
  대각선(45도)으로만 카메라가 움직임.
- **새로 추가한 슬롯이 반영 안 됨**: IMC에 원래 없던 슬롯(예: Shoot에 조이스틱 버튼 새로 추가)은
  대응하는 static IMC 엔트리가 없어서, RebuildControlMappings의 순회 대상 자체가 안 됨 — Add는
  UI상 성공한 것처럼 보이는데 실제 게임에는 전혀 반영이 안 됨.

슬롯 필터링을 좁히면 두 번째 문제가 나오고, 느슨하게 풀면 첫 번째 문제가 재발하는 근본적인
트레이드오프였음(커스텀 `UEnhancedPlayerMappableKeyProfile` 서브클래스로 여러 번 시도함 —
`git log`/과거 세션 기록 참고, 최종적으로는 이 접근 자체를 폐기).

**최종 해법**: 엔진 시스템을 버리고 IMC를 "런타임에 우리가 매번 통째로 다시 조립하는 대상"으로
취급하는 자체 시스템(`UTitanInputBindingSubsystem`)을 만듦.

## 3. UTitanInputBindingSubsystem — 새 아키텍처

`Source/titan_example/Input/` 폴더:

| 파일 | 역할 |
|---|---|
| `TitanInputTypes.h` | 데이터 구조 — `FTitanRowSchema`(행 스키마), `FTitanInputRole`(그룹 안 역할 하나), `FTitanKeyBinding`(실제 배정된 키 하나) |
| `TitanInputSchemaData.h` | `UDataAsset` — 모든 행의 스키마 + 관리 대상 IMC 목록을 담는 에셋. **실체: `/Game/Input/DA_TitanInputSchema`** |
| `TitanInputSaveGame.h` | 우리 전용 세이브(엔진 기본 세이브 포맷 안 씀) |
| `TitanInputBindingSubsystem.h/.cpp` | 실제 백엔드(`UGameInstanceSubsystem`) |

핵심 동작:
- 각 행(Row)은 "그룹" 단위로 관리됨. **Boolean/Axis1D 행**(Shoot, RCWS 토글류)은 그룹 = 물리 키
  1개(대체키를 늘리려면 그룹을 추가). **Axis2D 행**(CameraLook)은 그룹 = X/Y 페어(한 조이스틱당
  한 그룹, 페어 단위로만 추가/삭제).
- 키를 설정/삭제하면 `UInputMappingContext::MapKey()` / `UnmapAllKeysFromAction()`(엔진 공개
  API)로 관리 대상 IMC의 해당 액션 매핑을 즉시 다시 조립함. 이 두 함수 다 내부적으로
  `RequestRebuildControlMappingsUsingContext()`를 호출해서 **즉시 라이브 반영**됨.
- Axis2D 행의 Y 역할에는 `UInputModifierSwizzleAxis`(Order=YXZ)를 코드에서 직접 붙여줌 — 이게
  "Y축엔 Swizzle 필요"라는 규칙을 코드 한 곳에만 박아두는 핵심. 이 덕분에 **어떤 물리 키를
  고르든**(조이스틱 브랜드가 뭐든, 키보드든) 항상 올바르게 X/Y로 들어감 — IMC에 하드웨어별로
  미리 슬롯을 심어둘 필요가 아예 없음.
- 세이브/로드는 우리가 만든 `UTitanInputSaveGame`(슬롯명 `"TitanInputBindings"`)로 함. 게임 시작
  시(`Atitan_examplePlayerController::SetupInputComponent()`가 IMC를 `AddMappingContext`한 직후)
  자동으로 세이브를 불러와서 반영 — Settings 창을 한 번도 안 열어도 정상 동작함.

### 새 리매핑 가능한 액션 추가하는 법
1. `/Game/Input/DA_TitanInputSchema` 에셋 열기
2. `Rows` 배열에 새 항목 추가: `RowName`(Input 탭에 표시될 이름), `Action`(대상 UInputAction),
   `Roles`(Boolean이면 1개, Axis2D면 2개 — 두 번째에 `bApplySwizzleYXZ=true`), `DefaultGroups`(세이브
   파일 없을 때 시드할 기본 키 — 조이스틱 특정 브랜드 키는 절대 넣지 말 것, 키보드 기본값만)
3. IMC가 바뀌었으면 `ManagedContexts`도 확인(보통 `IMC_MouseLook` 하나만 있으면 됨)
4. 코드 재컴파일 불필요 — 에셋만 저장하면 바로 반영됨

## 4. 자잘한 UMG/UE5.8 관련 이슈들 (재발 방지용 메모)

- **`UUserWidget::Initialize()`와 이름 충돌**: 커스텀 위젯에 `Initialize(...)`라는 멤버함수를 만들면
  안 됨 — `UUserWidget`에 이미 인자 없는 가상함수 `Initialize()`가 있어서 이름이 겹치면
  오버로드가 가려짐. **MSVC(윈도우)는 조용히 통과시키는데 리눅스 clang은 `-Woverloaded-virtual`을
  에러로 취급해서 빌드가 깨짐** — 윈도우에서 멀쩡히 빌드되다가 리눅스 패키징에서만 터지는 흔한
  원인. `InitializeSlot`/`InitializePair`/`InitializeForRow`처럼 이름을 다르게 지어서 회피.
- **`NativeConstruct`는 같은 인스턴스에 여러 번 불릴 수 있음**(엔진 자체 문서화된 동작 — 위젯이
  재사용되면서 `TakeWidget()`이 다시 호출되는 경우 등). `AddDynamic`은 중복 바인딩 시 ensure로
  죽으므로, 매번 `RemoveDynamic`으로 먼저 정리한 뒤 `AddDynamic`해서 멱등하게 만들어야 함.
- **RawInput(deprecated) 플러그인 노이즈**: 프로젝트에 `RawInputSettings`로 `GenericUSBController_*`
  키가 등록돼있는데, 이게 JoystickPlugin과 별개로 같은 물리 조이스틱을 중복 캡처해서 상시 미세한
  analog 노이즈를 만듦 — "Listen(다음 입력 캡처)" 버튼을 누르자마자 이 노이즈가 먼저 걸려서
  엉뚱한 키로 캡처되는 버그가 있었음. `KeybindSlotWidget`의 후보 키 목록에서 `GenericUSBController`로
  시작하는 키를 아예 제외해서 해결.
- **애셋을 문자열 경로(`LoadObject`)로만 참조하면 패키징에서 빠짐**: `DA_TitanInputSchema`를
  `LoadObject(하드코딩 경로)`로 불러왔더니 리눅스 패키징에서 통째로 빠짐(쿠커는 진짜 UPROPERTY
  레퍼런스만 의존성으로 침, 문자열 경로는 안 따라감). `Config/DefaultGame.ini`의
  `+DirectoriesToAlwaysCook`도 이 프로젝트 쿡 파이프라인에서는 안 먹혔음 — 최종 해법은
  `ConstructorHelpers::FObjectFinder`를 서브시스템 **생성자**에서 호출해서 CDO 자체가 진짜 하드
  레퍼런스를 갖게 만드는 것(`titan_examplePlayerController`의 `TankVehicleIMC` 로딩과 동일한
  패턴). 이런 식으로 "런타임에 경로로 불러오는 로직" 코드를 새로 짤 때는 항상 이 패턴을 먼저
  고려할 것 — `Content/Paks` 안에 실제로 들어갔는지는 패키징해서 실행해보기 전까진 에디터/PIE에서
  절대 안 드러남(uncooked 애셋은 전부 접근 가능해서).
- **UE5.8의 Enhanced Input 슬롯 삭제 개념 부재**: `UnMapPlayerKey()`는 실제로 슬롯을 지우는 게
  아니라 `ResetToDefault()`(원래 기본 키로 되돌림)만 함 — "삭제"가 필요한 UI에는 안 맞음. 이번에
  만든 자체 시스템은 우리가 데이터를 완전히 소유해서 이 문제 자체가 없음(Remove = 배열에서
  진짜로 지움).

## 5. 남은 작업

- Graphics/Network/Sounds 탭: 틀만 있음(빈 페이지), 기능 없음 — 다음 세션.
- `[AxisDebug]`/`[KeybindDebug]` 등 이번 세션에 쓴 임시 디버깅 로그는 전부 비활성화(주석 처리)해둠
  — 필요하면 각 파일에서 "비활성화"/"TEMP DEBUG" 검색하면 바로 찾아서 주석 해제 가능.
