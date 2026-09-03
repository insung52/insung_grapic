# 시나리오 실행 모드 — 데모 / 풀 시스템 분리

2026-09-01 / 진행중(코드 완료, 빌드·PIE 검증 대기) / 통제기·상위체계 없이 언리얼만으로 전체 시나리오가 돌아가는 "데모 모드"를 `AScenarioConfig::RunMode`로 신설.

관련 문서: `scenario.md`(요구사항 원본), `scenario_three_stage_combat.md`(구현 현황),
`scenario_authoring_guide.md`(저작 실무 — 실행 모드 절 추가됨).

---

## 1. 왜 필요했나

지금까지 3단계 전투 시나리오는 **UGV RCWS가 근거리에서 한 발이라도 쏴야**(`UGVFiredNearEnemy`)
1차 교전이 열리고, 그 사격으로 적 3명이 죽어야 2차로 도주하는 구조다. 그런데 실제 납품 구성에선
그 조준·사격을 **LIG 원격통제기 SW**가 담당하므로, 통제기 없이 언리얼만 켜면 아무도 쏘지 않아
`EnemyEngage`에서 시나리오가 멈춘다.

실제로 `DT_ScenarioSteps_ThreeStage`의 `UGVSurveillance`/`UGVAutoFire` 두 행은 현재
`bEnabled=false`로 내려가 있다(통제기가 사격 주체여야 하므로 의도된 상태). 즉 **PIE로 켜면
1차 교전이 시작되지 않는다.**

그래서 실행 구성을 둘로 나눈다:

| 모드 | 구성 | 사격 주체 |
|---|---|---|
| **FullSystem** (기본) | PC 2대(UGV축=리슨서버 호스트 / 자체방호축=클라이언트) + 별도 PC의 통제기·상위체계 | 통제기 SW. 시나리오 시스템은 **적군 행동만** 담당 |
| **Demo** | 언리얼 프로세스 1개(또는 2대 PC 리플리케이션)만 | 시나리오 시스템이 RCWS를 자동사격으로 켜둠 |

---

## 2. 스위치

`AScenarioConfig`(레벨에 1개 배치된 그 액터)에 `Scenario|Run Mode` 카테고리 신설:

| 필드 | 기본 | 의미 |
|---|---|---|
| `RunMode` | `FullSystem` | `Demo`로 두면 아래 3가지가 한꺼번에 켜짐 |
| `bDemoForceUGVAutoFire` | true | UGV RCWS를 레벨 시작 직후 ARM+AutoFire로 |
| `bDemoForceCommandPostAutoFire` | true | 이동형지휘소(트럭) RCWS도 동일하게 |
| `bDemoAutoStartScenario` | true | 콘솔 `BeginScenarioEnemyContact` 없이 자동 시작 |
| `DemoAutoStartDelaySeconds` | 3.0 | 레벨 시작 기준 자동 시작까지의 대기 |

**커맨드라인이 액터 값을 이긴다** — 패키징 빌드 하나로 전시용/실환경용을 둘 다 돌리기 위해:

- `-demo` → 강제 데모
- `-fullsystem` → 강제 풀 시스템 (둘 다 주면 이쪽이 이김: 통제기 연동을 실수로 꺼버리지 않게)

---

## 3. 데모 모드가 실제로 하는 일

### 3.1 통제기/상위체계 연동 차단

`UUGVRemoteControlSubsystem::ShouldBeActive()`에 데모 게이트 추가 → **UDP 소켓을 아예 안 연다**.
수신(RC 명령)도 송신(상태보고)도 없음. 통제기 SW가 옆에서 켜져 있어도 주행모드/조향/안전스위치
명령이 시나리오가 잡아둔 상태를 덮어쓸 수 없다.

> 참고: 원래도 통제기가 패킷을 안 보내면 아무 것도 덮어쓰지 않는다(`ApplyEffectiveDriveMode`는
> RC 핸들러에서만 호출됨). 이 게이트는 "통제기가 켜져 있는 상태에서 데모를 돌려도 안전하게"를
> 보장하는 것 + 포트 점유/로그 소음 제거가 목적.

### 3.2 RCWS 자동사격 강제

`ScenarioConfig::BeginPlay` → `UScenarioStateSubsystem::RegisterScenarioConfig` →
1초 뒤(차량 폰/AI 컨트롤러 스폰 대기) `ApplyDemoRCWSAutoFire()`:

```
FireControl->SetFireSystemActive(true);              // 안전 해제(ARM)
FireControl->SetControlMode(ERCWSControlMode::AutoFire);
```

조종간 안전 풀기/장전 같은 수동 절차 없이 적을 발견하면 바로 락온·사격한다.

**너무 일찍 쏘지 않는 이유**: 적군은 `RevealEnemies` 스텝 전까지 `bIsRevealed=false`이고,
`UTargetDetectionComponent::ScanTargets`가 그런 대상은 **스캔 자체를 건너뛴다**. 그래서 RCWS를
미리 자동사격으로 켜둬도 순서가 앞당겨지지 않는다.

> ⚠️ 2026-09-01 정정 — 원래 여기 "트럭 RCWS도 **유효사거리(2000m)** 밖이라 3차 전투지 전엔
> 자연히 사격하지 않는다"고 적혀 있었으나 부정확했다. 먼저 걸리는 건 무기 유효사거리가 아니라
> **탐지 사거리 `MaxDetectionRange` = 400m**다. 트럭은 가장 가까운 적으로부터 869m 떨어져 있어
> **적을 아예 탐지조차 하지 못한다**(락온·발사 시도 자체가 없음). 결론은 같지만 이유가 5배 다르고,
> "트럭이 안 쏜다"를 축(axis) 버그로 오해하기 쉬운 지점이라 명시해 둠 —
> `2026-09-01_axis_rcws_autofire_investigation.md` 참고.

### 3.2.1 발사 모드 (2026-09-01 추가)

```cpp
UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Scenario|Run Mode")
ERCWSFireMode DemoFireMode = ERCWSFireMode::Burst;   // 데모 기본 = 점사
```

`ApplyDemoRCWSAutoFire`가 ARM/AutoFire와 함께 `RCWS->SetFireMode(DemoFireMode)`를 건다
(`FireMode`는 `URCWSFireControlComponent`가 아니라 `URCWSComponent::CurrentData`에 있음).
데모는 무인 방치로 계속 도는데 연사면 탄약 600발이 금방 마르고 화면도 단조로워져서 점사가 기본.
`BurstRoundCount`(3)와 `AutoFireCycleIntervalSeconds`(1초)가 같이 걸려 **1초 간격 3점사**가 된다.
실환경(FullSystem)에서는 통제기 SW가 `RC_FireMode`로 정하므로 데모 전용 값.

### 3.3 시나리오 자동 시작

`DemoAutoStartDelaySeconds` 후 `BeginEnemyContactScenario()`를 그대로 호출(콘솔 명령과 동일 경로).

---

## 3.5 대기실(kadex_lobby)에서 모드/구성 고르기 (2026-09-01 추가)

패키징하면 시작 레벨이 `kadex_lobby`이고 거기 축 선택 화면(`WBP_AxisSelection2`,
부모 `UAxisSelectionWidget`)에서 Host/Client를 고른다. 여기에 실행 모드 선택과 단독 시작을 얹었다.

### 화면 구성

| 위젯 이름 (WBP에 이 이름으로 배치) | 타입 | 동작 |
|---|---|---|
| `HostButton` | Button | `HostListenServer("UGV", bDemo)` → `open <Map>?Listen?Axis=UGV?Demo=<0\|1>` |
| `ClientButton` + `EditableText_ip` | Button + EditableText | `ConnectToHost(IP, "SelfDefense")` — **모드는 서버가 정함**(체크박스 무시) |
| `SoloButton` | Button | `StartSoloAxis("SelfDefense", bDemo)` → `open <Map>?Axis=SelfDefense?Demo=<0\|1>` |
| `DemoModeCheckBox` | Check Box | Host/Solo에만 적용. WBP에 없으면 Host=해제(풀), Solo=체크(데모)로 간주 |

전부 `BindWidgetOptional` — WBP에 안 놓으면 그 기능만 조용히 빠진다(기존 계약 그대로).

### `SoloButton`이 필요한 이유

Client 버튼은 **서버가 그 IP로 이미 떠 있어야** 레벨로 들어간다. 전시용 1 PC 데모에는 붙을 서버가
없다 — 그래서 순수 standalone으로 여는 경로가 따로 필요하다.

축을 **자체방호로 고정**한 이유: 알림 토스트와 미니맵이 붙는 `SelfDefenseMonitor1`이 이 축에서만
생성된다(`Client_OnAxisResolved`). UGV축 단독으로 띄우면 시나리오는 다 돌지만 알림이 아무데도 안 뜬다
(§4-3의 축 게이트). UGV는 축과 무관하게 `AUGVAIController`가 몰고 시나리오 시스템이 RCWS를 쥐므로
전체 흐름은 동일하다.

> ⚠️ **Solo에 `?Listen`을 붙이면 안 된다.** 자체방호축이 리슨서버가 되면 "UGV PC = 호스트"(§1.2)
> 전제가 뒤집히고, `UUGVRemoteControlSubsystem`이 "UGV축 + 서버"에서만 활성이라 통제기 연동이
> 영영 안 붙는다. 나중에 다른 PC를 붙일 생각이면 Solo가 아니라 Host로 시작할 것.

### 실행 모드는 서버 권위 — 2 PC에서 섞일 수 없다

`?Demo=`는 `Atitan_exampleGameMode::InitGame`이 읽어 `UScenarioStateSubsystem`에 URL 오버라이드로
넣고, 서버가 **실효 모드**를 확정해 `Atitan_exampleGameState::bDemoRunMode`(Replicated)에 게시한다.
`IsDemoMode()`는 **클라이언트면 자기 값을 아예 안 보고 이 GameState 값만 읽는다.**

**우선순위(서버): 커맨드라인 `-demo`/`-fullsystem` > 접속 URL `?Demo=` > 레벨 `AScenarioConfig::RunMode`**

- 축 선택 화면을 거치면 체크 해제도 명시적 선택이므로 `?Demo=0`을 실어 보낸다 — 레벨에 저장된
  `RunMode=Demo`를 덮어쓴다. 이 화면을 안 거치는 실행(직접 PIE 등)은 `?Demo=`가 없어 레벨 값이 그대로 산다.
- 게시 지점 3곳: `SetRunModeUrlOverride`(보통 GameState 전이라 no-op) / `GameMode::InitGameState` /
  `RegisterScenarioConfig`(레벨 값까지 반영된 최종 확정).

> 참고: 지금 데모 모드의 동작(통제기 차단·RCWS 자동사격·자동 시작)은 **전부 서버에서만** 일어나므로
> 이 리플리케이션이 없어도 실해는 없었다. 다만 그건 우연이지 보장이 아니라서, 클라 쪽 동작이
> 생기더라도 자동으로 서버 기준이 되도록 한 곳으로 모아둔 것이다.

### 콘솔로도 됨

- `HostListenServer UGV 1` — 데모로 호스트
- `StartSoloAxis SelfDefense 1` — 자체방호축 단독 데모
- `ConnectToHost 192.168.10.10 SelfDefense` — 접속(모드는 서버 값)

## 4. 풀 시스템(2 PC) 쪽에서 같이 고친 것

리슨서버 구조·적/아군 틱 서버 전용화·RCWS 서버 권위+멀티캐스트 이펙트는 이미 되어 있었고
(`replication/replication_audit.md` §5/§8), 구멍 2개만 막았다.

1. **`BeginScenarioEnemyContact`가 Server RPC가 아니었음** — 다른 시나리오 Exec은 전부
   `HasAuthority ? 로컬 : Server_*` 패턴인데 이것만 무조건 로컬 서브시스템을 불렀다. 자체방호 PC
   (클라이언트)에서 콘솔로 치면 **그 프로세스에서만** 시나리오가 돌아 서버와 화면이 갈렸다.
   → `Server_BeginScenarioEnemyContact` 신설, 같은 패턴으로 통일.
2. **스텝 평가 루프에 클라이언트 가드** — `BeginScenarioSteps()` 초입에 `NM_Client` 리턴.
   `UScenarioStateSubsystem`은 GameInstanceSubsystem이라 클라 프로세스에도 인스턴스가 살아 있어서,
   거기서도 평가하면 적군 이동/RCWS 모드 전환이 한 벌 더 돈다.

3. **알림·미니맵 마커를 GameState로 전달** (위 1·2의 필연적 후속). 스텝 평가가 서버 전용이 되면
   서버에서 발동한 알림이 클라(자체방호 PC) 화면에 안 뜬다 — 그런데 **알림 토스트가 실제로
   보여야 하는 곳이 바로 자체방호축 Monitor1**이다. 그래서:
   - `Atitan_exampleGameState::Multicast_ShowScenarioNotification(Kind, Duration)` 신설 —
     `UScenarioStateSubsystem::ShowScenarioNotification()`이 이 멀티캐스트로 뿌리고, 각 프로세스가
     자기 로컬 `UNotificationSubsystem`으로 띄운다. 서버 자신에서도 같이 실행되므로 호출부는 한 번만.
     기존 직접 호출 2곳(`BeginEnemyContactScenario`의 `EnemyContact`, `ShowUIMessage` 이펙트)을 교체.
   - 미니맵 "적 예상 위치" 좌표는 **Replicated 프로퍼티**로(`bHasEnemyPredictedLocation`/
     `EnemyPredictedLocation`) — 멀티캐스트와 달리 나중에 접속한 클라이언트도 초기 리플리케이션으로
     값을 받는다. `UScenarioStateSubsystem::HasEnemyPredictedLocation()/GetEnemyPredictedLocation()`이
     GameState 값을 먼저 보도록 바뀌어서, 이 값을 읽는 `Monitor1Widget`/`SelfDefenseMonitor1Widget`
     코드는 손대지 않았다.

   - **알림은 자체방호축에서만 띄운다**(2026-09-01 사용자 확정). 멀티캐스트 구현부와 폴백 양쪽에
     `PlayerAxis == SelfDefense` 게이트를 건다. UGV축 프로세스엔 `SelfDefenseMonitor1`이 없어서
     `UNotificationSubsystem`의 호스트 패널 탐색이 실패하고 토스트가 `AddToViewport()` 폴백으로
     **메인 뷰포트 = UGV RCWS 화면**에 붙어버리기 때문.

   **경우의 수 4가지 전부에서 자체방호 Monitor1에 알림이 뜬다:**

   | | 1 PC (단일 프로세스) | 2 PC (host=UGV / client=자체방호) |
   |---|---|---|
   | **Demo** | 축이 SelfDefense면 ✅ / **UGV축이면 안 뜸**(의도됨) | ✅ 호스트(UGV)=안 뜸, 클라(자체방호)=뜸 |
   | **FullSystem** | 위와 동일 | ✅ 위와 동일 |

   > 이 프로젝트의 **실제 2 PC 구성에서는 항상 자체방호 PC에 뜬다.** 1 PC로 UGV축만 돌리는
   > 경우에만 알림이 아무데도 안 뜨는데, "UGV 화면엔 안 떠도 된다"는 요구와 일치한다.
   > (`New_kadex_0811`의 GameMode `DefaultAxisWhenUnspecified=UGV`라 **그냥 PIE는 UGV축**이다 —
   > 1 PC에서 알림까지 보려면 축을 SelfDefense로 띄워야 한다.)

### RTSP 송출에 알림이 새는가 — 안 샌다 (2026-09-01 코드 확인)

UGV RCWS 스트림은 `FMainViewFrameSource`가 **포스트프로세스 체인 안의 tonemapped 씬 컬러**를
RenderTarget으로 복사해서 만든다(`SubscribeToPostProcessingPass` → `CopyTonemappedSceneColor`).
Slate/UMG는 그보다 **뒤에 백버퍼로 합성**되므로 씬 컬러에 들어갈 수 없다. 즉 위젯이 로컬 화면에
떠 있어도 송출 영상엔 절대 안 나온다. 위 축 게이트는 "로컬 UGV 화면에도 안 뜨게" 하는 이중 안전장치.

   > 이전 상태: "서버에서 시나리오 시작 → 클라 알림 없음"은 **원래부터 있던 구멍**이었고, 클라에서
   > 콘솔로 직접 치면 그 프로세스가 시나리오를 한 벌 더 돌리는 바람에 우연히 떴던 것뿐이다.
   > `Server_BeginScenarioEnemyContact`로 그 우회로가 없어지면서 이 멀티캐스트가 필수가 됐다.
   >
   > 아직 남은 것: `AUGVAIController`의 `RoadExitWarning` 알림은 여전히 서버 로컬 — 자체방호 PC엔
   > 안 뜬다(시나리오 알림이 아니라 UGV 주행 경고라 이번 범위 밖, 원래부터 그랬음).

---

## 5. 바뀐 파일

| 파일 | 내용 |
|---|---|
| `UI/ScenarioConfig.h` | `EScenarioRunMode` enum + 실행 모드 필드 5개, `BeginPlay`/`EndPlay` 오버라이드 |
| `UI/ScenarioConfig.cpp` | 서브시스템에 자기 자신 등록/해제 |
| `UI/ScenarioStateSubsystem.h/.cpp` | `IsDemoMode()`, `Register/UnregisterScenarioConfig()`, `ApplyDemoRunModeSetup()`, `ApplyDemoRCWSAutoFire()`, `DemoAutoStartScenario()`, 커맨드라인 오버라이드 해석, `BeginScenarioSteps` 클라이언트 가드 |
| `Network/UGVRemoteControlSubsystem.cpp` | `ShouldBeActive()` 데모 게이트 |
| `titan_examplePlayerController.h/.cpp` | `Server_BeginScenarioEnemyContact` |

설계상 서브시스템이 매번 `GetActorOfClass`로 ScenarioConfig를 찾지 않고 **액터가 BeginPlay에서
자신을 등록**하는 방식을 택했다 — `ShouldBeActive()`가 50Hz(`PollIntervalSeconds=0.02`)로
`IsDemoMode()`를 물어보기 때문.

---

## 5.2 버그 수정 — 데모(UGV축)에서 UGV가 1차 목적지로 출발 안 함 (2026-09-01)

**증상**: `RunMode=Demo`, UGV축(단독 PIE 또는 UGV 호스트)에서 UGV가 1차 목적지로 출발하지 않음.
2차 목적지 이동은 정상이라 더 헷갈렸음.

**원인**: 드론 시뮬레이션 주체 판정. `ADronePawn`은 축 판정 후
`bShouldSimulate = (LocalAxis == SelfDefense || Unspecified)`로 시뮬 주체를 정했는데, **UGV축
프로세스에서는 이게 false**라 `Tick`이 `TickRemoteInterpolation`만 하고 조기 리턴한다 →
비행/자율비행/짐벌 정찰이 전부 안 돌고 → `HasObservedParachute()`가 영원히 false →
`UAVParachuteObserved` 트리거가 안 켜짐 → **`UAVSpotted` 행이 안 발동 →
`MoveUGVToZone1Destination`이 실행되지 않음.**

2차가 멀쩡했던 이유: `UGVMoveZone2`는 `LeaderDistanceFromEnemyAtLeast`(적군 거리) 트리거라
드론과 무관하다. 이펙트 코드(`MoveUGVToZone1/2/3Destination`)는 1·2·3차가 **완전히 같은
분기**를 쓰므로 이펙트 쪽 문제가 아니었다.

> 곁다리로 `RevealEnemies` / `DroneSeeEnemies` / `DroneWideView`(전부 `UAVSpotted` 체인)도 같이
> 죽어 있었다. 적군이 그래도 교전에 들어간 건 `EnemyApproach`/`EnemyEngage` 행이 prereq 없이
> 조건만으로 발동하도록 설계돼 있었기 때문(저작 가이드 §2.5의 그 규칙이 여기서 효과를 봄).

**수정**: `ADronePawn::ResolveShouldSimulateDrone()` 신설 — ① 단독 실행이면 무조건 이 프로세스
② `SelfDefense`/`Unspecified` ③ **데모 모드의 리슨서버면 서버**. FullSystem 구성의 클라이언트
권위는 그대로 둔다(조종 지연 때문에 내린 결정이므로). 상세는
`replication/2026-09-01_drone_client_authoritative.md` §3.1.

**같이 고친 잠재 버그**: 이 축 판정 블록이 통째로 `#if TITAN_RTSP_ENABLED` 안에 있어서, RTSP를
끄고 빌드하면 `ApplySimulationAuthority`가 아예 안 불려 `bAxisResolved=false`로 남고 드론
`Tick`이 통째로 조기 리턴했다(= 드론이 아무것도 안 함). 축 판정을 `#if` 밖으로 뺐다.

## 5.3 버그 수정 — 레벨 트래블(`open`) 후 시나리오가 영영 안 시작됨 (2026-09-01)

**증상**: `open New_kadex_0811?Axis=SelfDefense`(= `StartSoloAxis`)로 축을 바꿔 들어가면 새 레벨에서
**시나리오가 아무것도 안 돈다**. 3초 자동 시작도, 콘솔 `BeginScenarioEnemyContact`를 직접 쳐도
반응이 없다. 로그엔 `데모 자동 시작 — BeginEnemyContactScenario() 호출`까지만 찍히고
`시나리오 스텝 발동:`이 한 줄도 없다(경고도 없음).

> 드론이 안 움직이는 걸로 먼저 발견됐지만 **드론만의 문제가 아니었다** — 적군도 안 움직였다
> (트래블 이후 `[EnemyPath]` 로그가 하나도 없음). §5.2의 드론 시뮬 주체 문제와는 **별개의 버그**다.

**원인**: `UScenarioStateSubsystem`은 `UGameInstanceSubsystem`이라 **레벨 트래블을 넘어 살아남는데**,
월드 단위 상태를 리셋하는 곳이 없었다. 특히 `BeginScenarioSteps`의 중복 실행 방지가

```cpp
if (GetWorld()->GetTimerManager().IsTimerActive(ScenarioStepTickTimerHandle)) return;
```

인데, 여기 쓰인 핸들은 **죽은 옛 월드의 FTimerManager가 발급한 것**이다. 새 월드의 TimerManager에
그 핸들을 물어보면 ID가 다른 타이머와 겹쳐 "돌고 있다"는 오답이 나올 수 있고, 그러면 이 함수가
**경고 한 줄 없이 조용히 리턴**해서 스텝 평가가 영영 시작되지 않는다. 몇 번을 다시 호출해도 같다.

**수정**:
- 명시 플래그 `bScenarioStepsRunning`으로 교체(타이머 핸들 조회로 상태를 추측하지 않는다).
- `ResetForNewWorldIfNeeded()` 신설 — 월드가 바뀌면 타이머 핸들 3개 / `FiredScenarioSteps` /
  스텝 시작 시각 / 사망자·아군사격 기준값 / RCWS 발사 감시 / `FormUpLeader` / 적 예상 좌표 등
  월드 단위 상태를 전부 초기화. 진입점 3곳(`BeginScenarioSteps`, `BeginEnemyContactScenario`,
  `RegisterScenarioConfig`)에서 맨 앞에 호출.
- 진단용으로 `스텝 평가 시작 — 테이블 ..., 주기 ...초` 로그 추가(이번에 "시작됐는지 아닌지"를
  로그만으로 구분할 수 없어서 원인 추적이 오래 걸렸다).

> 아군/적군 컴포넌트 레지스트리는 각자 `EndPlay`에서 스스로 해제하므로 이 리셋에서 건드리지 않는다.

## 5.5 패키징 대상 레벨 (2026-09-01)

`Config/DefaultGame.ini`의 `[/Script/UnrealEd.ProjectPackagingSettings]` — **레벨 2개만** 쿡한다:

```ini
+MapsToCook=(FilePath="/Game/kadex_lobby")      ; GameDefaultMap, 축 선택 화면
+MapsToCook=(FilePath="/Game/New_kadex_0811")   ; 실제 시나리오 레벨
```

`kadex_test`(예전 경량 테스트 레벨)는 목록에서 제거. 두 레벨 다 World Partition이 아니라
(`Content/__ExternalActors__/`에 항목 없음) `.umap` 하나씩이면 되고, 별도 서브레벨 처리도 필요 없다.

왜 명시가 필요한가: 게임 레벨은 대기실에서 `open <경로>?Axis=...` **문자열 트래블**로만 도달해서
쿠커가 정적 분석으로 못 찾는다(2026-08-18 리눅스 패키징에서 "레벨을 찾을 수 없다"로 발견).
반대로 `MapsToCook`이 비어 있지 않으면 쿠커는 여기 적힌 맵과 그 참조만 쿡하므로,
`Content/`에 굴러다니는 마켓플레이스 데모 맵 40여 개가 자동으로 빠지는 효과도 같이 얻는다.

- `+DirectoriesToAlwaysCook=(Path="/Game/Input")`은 그대로 유지(`DA_TitanInputSchema`가
  `LoadObject()` 하드코딩 경로라 같은 이유로 필요).
- ⚠️ ini를 에디터 실행 중에 고쳤으므로 **에디터를 재시작한 뒤 패키징**할 것. 그리고 에디터의
  Project Settings ▸ Packaging 화면을 열어 저장하면 이 섹션이 덮어써질 수 있다.

## 6. 남은 작업

**2026-09-01 완료분** (빌드 후 에디터 반영·저장까지 끝):

- [x] `DT_ScenarioSteps_ThreeStage`의 `DroneSeeEnemies` 행 prereq를 `UGVSurveillance` → **`UAVSpotted`**로
      이동. 이걸로 죽어 있던 `DroneSeeEnemies` → `DroneWideView` 체인이 살아남.
- [x] `New_kadex_0811`의 `ScenarioConfig_1`을 **`RunMode=Demo`**로 설정(나머지 데모 플래그는 기본값
      그대로: UGV/지휘소 자동사격 켬, 자동 시작 켬, 3초).
- [x] 빌드 반영 확인 — 액터 디테일에 새 필드 5개가 뜸.
- [x] `BP_KadexTestGameMode`의 `GameStateClass`가 `Atitan_exampleGameState`인 것 확인
      (알림 멀티캐스트 경로가 실제로 유효).
- [x] `DT_NotificationWidgets`에 `EnemyContact`/`ScenarioComplete` 행 존재 확인(스텝 테이블이 쓰는 두 종류).
- [x] 두 에셋 저장 완료.

**남은 것**:

1. **PIE 1회 완주 검증** — 로그의 `[ScenarioStateSubsystem] 데모 실행 모드 —` 줄, `데모 자동사격: …
   ARM + AutoFire로 전환` 2줄, 그 뒤 `시나리오 스텝 발동:` 순서 확인.
2. **WBP 작업(사용자)**: `WBP_AxisSelection2`에 `SoloButton`(Button), `DemoModeCheckBox`(Check Box)
   배치. 이름만 맞추면 그래프 작업 없이 붙는다(§3.5).
   - 참고: 그냥 PIE로 `New_kadex_0811`을 직접 열면 여전히 **UGV축**이라 알림이 안 뜬다
     (`DefaultAxisWhenUnspecified=UGV`). 알림까지 보려면 대기실 → "호스트 없이 시작"으로 가거나,
     콘솔에 `StartSoloAxis SelfDefense 1`.
3. `UGVZone3Destination`이 비어 있고 `UGVMoveZone3` 행도 꺼져 있음 — 3차 전투지에서 UGV를 움직일지 결정 필요.
4. 2 PC 실환경 검증(드론 2프로세스 검증도 아직 미완 — `CURRENT_STATE.md` §9).
5. **납품/실환경 전환 시**: `RunMode`를 `FullSystem`으로 되돌리거나 실행 인자에 `-fullsystem`을 줄 것.
6. `AUGVAIController`의 `RoadExitWarning` 알림은 여전히 UGV축 로컬 — 이것도 빼야 하는지 미정.
