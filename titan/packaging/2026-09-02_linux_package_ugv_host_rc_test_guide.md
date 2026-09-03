# 리눅스 패키지 — UGV Host 모드로 통제기 연동(UDP+RTSP) 확인 가이드

2026-09-02 / 완료 / 리눅스 패키지 1개만 넘겨서, 대기실에서 RC IP 입력 → UGV Host로 들어가 통제기와 UDP/RTSP가 붙는지 확인하는 절차.

## 0. 이 문서의 범위

**확인하려는 것 딱 하나**: 우리 리눅스 패키지를 통제기 옆에서 실행했을 때

- **UDP+JSON**(LIG ICD §3.1)이 통제기와 양방향으로 오가는가
- **RTSP 5스트림**(`ugv/*`)을 통제기가 받아가는가

**범위에서 뺀 것**: 자체방호축(Client 버튼), 데모 모드(Solo 버튼), 3단계 전투 시나리오 완주.
시나리오가 끝까지 도는지는 여기서 안 본다 — UGV가 스폰돼서 소켓/스트림이 열리고 통제기 명령에
반응하면 성공이다.

**공유 대상**: 리눅스 패키지 폴더 **하나**. `rc_mockup_tools/`(우리가 만든 RC GUI / UDP 클라이언트 /
RTSP 뷰어)는 내부 테스트 도구라 넘기지 않는다.

---

## 1. 구성

```
  [ 통제기 PC (LIG) ]                        [ 우리 리눅스 PC = UGV 시뮬레이션 SW ]
   RC IP = 192.168.10.20 (예시)               UGV IP = 192.168.10.10 (예시)
                                              titan_example.sh (리슨서버 / Axis=UGV)

   RC → UGV   UDP 8000(주기) / 8001(비주기)  ──▶  0.0.0.0:8000 / 0.0.0.0:8001 로 바인드
   UGV → RC   UDP 8010(주기) / 8011(비주기)  ◀──  RCIP:8010 / RCIP:8011 로 송신
   RTSP       TCP 8554 (interleaved, UDP 미지원) ◀──  rtsp://<UGV IP>:8554/ugv/<stream>
```

- 포트/IP 원문은 `protocol/protocol_icd.md` §3.1. 코드 기본값도 같은 값
  (`Source/titan_example/Network/UGVRemoteControlSubsystem.h`).
- **우리 쪽 수신은 `0.0.0.0` 바인드**라 우리 PC의 IP를 앱에 알려줄 필요가 없다. 앱에 넣어야 하는
  건 **통제기 PC의 IP(RC IP) 하나뿐**이다.
- 통제기 쪽에는 우리 PC의 IP를 알려줘야 한다(UDP 목적지 + RTSP 접속 주소 양쪽).
- IP가 ICD 기본값(192.168.10.x)이 아니어도 대기실 화면에서 바꾸면 된다(§4). Tailscale IP(100.x.x.x)로도
  그대로 동작한다(2PC 테스트 이력 있음).

### RTSP 마운트 5개

| 스트림 | URL |
|---|---|
| RCWS 조준경 | `rtsp://<UGV IP>:8554/ugv/rcws` |
| 전면 CCTV | `rtsp://<UGV IP>:8554/ugv/front_cctv` |
| 후면 CCTV | `rtsp://<UGV IP>:8554/ugv/rear_cctv` |
| 좌측 CCTV | `rtsp://<UGV IP>:8554/ugv/left_cctv` |
| 우측 CCTV | `rtsp://<UGV IP>:8554/ugv/right_cctv` |

기본 해상도는 RCWS 1920×1080 / CCTV 320×180(`UStreamResolutionSubsystem` 기본값), 대기실 화면에서
바꿀 수 있다. 수신 측 저지연 세팅은 `rtsp/rtsp_client_reception_guide.md`(LIG 공유용) 그대로.

---

## 2. 패키징 (Windows 에디터에서 Linux 크로스컴파일)

1. **`Config/DefaultGame.ini` 확인** — `[/Script/UnrealEd.ProjectPackagingSettings]`에 아래 줄들이
   살아 있어야 한다. 게임 레벨은 문자열 트래블(`open ...`)로만 도달해서 쿠커가 정적 분석으로 못 찾는다.
   ```ini
   +MapsToCook=(FilePath="/Game/kadex_lobby")
   +MapsToCook=(FilePath="/Game/New_kadex_0811")
   +DirectoriesToAlwaysCook=(Path="/Game/Input")
   ```
   ⚠️ 에디터의 Project Settings ▸ Packaging 화면을 열고 저장하면 이 섹션이 덮어써질 수 있다.
   ini를 직접 고쳤으면 **에디터를 재시작한 뒤** 패키징할 것.
2. **빌드 구성은 Development 권장** — 이번 목적이 "로그로 확인"이라서다(§6의 확인용 로그가 전부
   `titan_example.log`에 찍힌다). Shipping으로 뽑으면 §6 절차를 대부분 못 쓴다.
3. Platforms ▸ Linux ▸ Package Project 실행. 툴체인은 `C:\UnrealToolchains\v26_clang-20.1.8-rockylinux8`.
4. **`titan_example_x11_fallback.sh`를 결과물 폴더에 손으로 복사**한다(프로젝트 루트에 있음).
   UE 패키징이 자동으로 넣어주지 않는다. 용도는 §3-2.

결과물은 `titan_example.sh` + `titan_example/`이 들어있는 폴더 하나. 이 폴더를 통째로 넘기면 된다.

> RTSP가 실제로 들어갔는지 의심되면 패키징 로그에서 `[RtspEncoder]` 경고를 확인할 것 —
> NVENC SDK / CUDA / GStreamer 번들이 빌드 PC에 없으면 **빌드는 성공하고 RTSP만 조용히 빠진다**
> (의도된 soft-fail, `rtsp/rtsp_poc_findings.md` §10.3.2).

---

## 3. 대상 리눅스 머신 준비

Ubuntu 22.04 / 24.04 + NVIDIA GPU 기준(둘 다 실행 이력 있음).

### 3-1. 런타임 의존성

```bash
# GStreamer는 패키지에 번들되지 않는다 — 타겟 머신의 시스템 GStreamer를 그대로 쓴다.
sudo apt install -y \
  libgstreamer1.0-0 libgstreamer-plugins-base1.0-0 libgstrtspserver-1.0-0 \
  gstreamer1.0-plugins-base gstreamer1.0-plugins-good gstreamer1.0-plugins-bad \
  gstreamer1.0-tools
```

- 서버 파이프라인이 쓰는 요소: `appsrc`(plugins-base), `h264parse`(plugins-bad), `rtph264pay`(plugins-good).
- 링크는 `libgstreamer-1.0.so.0` 같은 SONAME 기준이라 배포판 버전이 정확히 1.24가 아니어도 되지만
  1.x 계열이어야 한다(빌드 시 참조한 번들은 Ubuntu 24.04 / GStreamer 1.24.2).
- **NVIDIA 독점 드라이버 필수**(NVENC 인코딩 = `libnvidia-encode.so`). 없으면 게임은 뜨는데
  RTSP만 조용히 안 뜬다.
- Vulkan 런타임(`libvulkan1`)도 필요 — UE 리눅스 클라이언트는 Vulkan RHI로 뜬다.

### 3-2. 세션 종류 (Wayland / X11)

- `Config/Linux/LinuxEngine.ini`가 **`VideoDriver=wayland`를 강제**한다. Xwayland 경유 X11 경로에서
  풀스크린 QHD가 11fps까지 떨어지는 문제 때문이다(`rtsp/linux_wayland_x11_present_bottleneck.md`).
- **Wayland 세션이면 그냥 `./titan_example.sh`.**
- **Wayland 컴포지터가 아예 없는 순수 X11 머신이면 창이 안 뜬다**(폴백 없음). 그때는
  `./titan_example_x11_fallback.sh`로 실행할 것(§2-4에서 복사해둔 파일).
- GNOME/Wayland에서 창 테두리·타이틀바가 없는 건 정상이다(SDL에 libdecor가 없고 Mutter가
  서버사이드 데코레이션을 안 함). `Super` + 드래그로 창을 옮길 수 있다.

### 3-3. 방화벽

```bash
sudo ufw allow 8000/udp   # RC → UGV 주기
sudo ufw allow 8001/udp   # RC → UGV 비주기
sudo ufw allow 8554/tcp   # RTSP (TCP interleaved만 씀)
```

### 3-4. 실행

```bash
chmod +x titan_example.sh titan_example_x11_fallback.sh
./titan_example.sh -fullsystem                 # 창모드 (§4-2 참고 — -fullsystem 권장)
./titan_example.sh -fullsystem -fullscreen     # 풀스크린
```

---

## 4. ⭐ 대기실(kadex_lobby) — 여기가 핵심

실행하면 `kadex_lobby`의 축 선택 화면(`WBP_AxisSelection2`)이 뜬다. **UGV Host 버튼을 누르기 전에**
아래 두 가지를 반드시 한다.

### 4-1. RC IP 입력 — 입력 후 반드시 **Enter**

| 입력 필드 | 넣을 값 | 기본값 |
|---|---|---|
| **RC IP** | **통제기가 돌아갈 PC의 IP** | `192.168.10.20` |
| RC Periodic Port | 보통 그대로 | `8010` |
| RC Event Port | 보통 그대로 | `8011` |
| UGV Listen Periodic Port | 보통 그대로 | `8000` |
| UGV Listen Event Port | 보통 그대로 | `8001` |
| RCWS / CCTV 해상도 | 필요하면 | 1920×1080 / 320×180 |

> ⚠️ **가장 흔한 실수**: 값을 타이핑만 하고 바로 Host를 누르는 것. 이 필드들은 `OnTextCommitted`
> (= **Enter를 치거나, 다른 곳을 클릭해서 포커스가 빠질 때**)에만 반영된다. Host 버튼 핸들러는
> 텍스트 필드를 다시 읽지 않는다(`UAxisSelectionWidget::HandleHostClicked`).
> **필드마다 Enter를 한 번씩 칠 것.**
>
> 반영됐는지는 로그로 확인된다 — 커밋할 때마다
> `[AxisSelectionWidget] ApplyNetworkFieldsToSubsystem — RCIPValue='...'` 줄이 찍힌다.

입력값은 `UUGVRemoteControlSubsystem`(GameInstance 서브시스템)에 들어가므로 **레벨 트래블 후에도
유지**된다. 소켓도 커밋 즉시 재오픈된다.

### 4-2. 데모 모드 체크박스는 **반드시 해제**

⚠️ **이걸 놓치면 통제기 연동이 통째로 안 붙는다.** 지금 `New_kadex_0811`의 `ScenarioConfig_1`은
레벨에 **`RunMode=Demo`로 저장**돼 있고(전시용 1PC 데모 세팅), 데모 모드에서는
`UUGVRemoteControlSubsystem::ShouldBeActive()`가 **UDP 소켓을 아예 안 연다**(수신도 송신도 없음).

- 대기실에서 **체크박스를 해제한 채로** Host를 누르면 `?Demo=0`이 실려서 레벨 저장값을 덮어쓴다 → 풀 시스템.
- 체크박스가 WBP에 없으면 Host의 기본값이 "해제(=풀 시스템)"다.
- 더 확실하게 하려면 실행 인자에 `-fullsystem`을 주면 된다(커맨드라인이 URL·레벨값을 모두 이긴다):
  ```bash
  ./titan_example.sh -fullsystem
  ```
  **넘기는 쪽에는 이 인자를 기본으로 안내하는 게 안전하다.**

우선순위: `커맨드라인 -demo/-fullsystem` > `접속 URL ?Demo=` > `레벨 AScenarioConfig::RunMode`.

### 4-3. Host 버튼

`HostListenServer("UGV", false)` → `open New_kadex_0811?Listen?Axis=UGV?Demo=0`.
이 프로세스가 **리슨서버 + UGV축**이 되고, **그 조합에서만** 통제기 연동 서브시스템이 활성화된다.

- **Client 버튼**(자체방호축 접속), **호스트 없이 시작(Solo) 버튼**은 이번 범위가 아니다. 누르지 말 것.
  - 특히 Solo는 자체방호축 standalone이라 통제기 연동이 **영영 안 붙는다**.
- 콘솔로도 같다: `` ` `` 키 → `HostListenServer UGV 0`

---

## 5. 통제기 쪽에 알려줄 값

| 항목 | 값 |
|---|---|
| UGV 시뮬레이터 IP | 우리 리눅스 PC의 IP |
| UGV 수신 포트 | UDP 8000(주기) / 8001(비주기) |
| 통제기 수신 포트 | UDP 8010(주기) / 8011(비주기) — 우리가 여기로 쏜다 |
| RTSP | `rtsp://<우리 PC IP>:8554/ugv/{rcws,front_cctv,rear_cctv,left_cctv,right_cctv}` |
| RTSP 전송 | **TCP interleaved만**(`protocols=tcp`), H.264 High, B프레임 없음 |

---

## 6. 확인 절차

로그 위치: `<패키지폴더>/titan_example/Saved/Logs/titan_example.log` (Development 빌드 기준)

### 6-1. 풀 시스템으로 떴는지

```bash
grep "데모 실행 모드" titan_example.log
```
→ **이 줄이 나오면 실패다**(데모로 뜬 것). §4-2로 돌아갈 것. **안 나오는 게 정상.**

### 6-2. UDP 소켓이 열렸는지

```bash
grep "UGVRemoteControlSubsystem" titan_example.log
```
기대되는 줄:
```
UGVRemoteControlSubsystem: UDP 소켓 시작 — recv 8000(주기)/8001(비주기), send-to <RC IP>:8010(주기)/8011(비주기)
```
- `send-to`의 IP가 **입력한 RC IP인지 반드시 눈으로 확인**할 것. 여기가 `192.168.10.20`으로 남아
  있으면 §4-1의 Enter를 안 친 것이다.
- `UDP 소켓 바인딩 실패` → 8000/8001을 다른 프로세스가 쓰고 있음.
- `RCIP '...' 파싱 실패` → IP 문자열 오타.

소켓 확인:
```bash
ss -lunp | grep -E '8000|8001'
```

### 6-3. RTSP 마운트가 등록됐는지

```bash
grep -E "RTSP server listening|Registered RTSP mount" titan_example.log
```
기대:
```
RTSP server listening on port 8554
Registered RTSP mount 'ugv/rcws' (1920x1080 @ ... fps) -> rtsp://<host>:8554/ugv/rcws
Registered RTSP mount 'ugv/front_cctv' ...        (총 5줄)
```
- RTSP 서버 자체는 프로세스 시작 시(= 대기실에서 이미) 뜨고, **마운트 5개는 레벨에 들어가 UGV가
  스폰된 다음**에 등록된다. 대기실 상태에서 마운트가 없는 건 정상.
- `GStreamer failed to initialize` / `RtspEncoder built without GStreamer support` → §2-4 / §3-1 확인.

### 6-4. 실제 영상 (우리 쪽에서 먼저 확인)

같은 리눅스 머신이나 옆 PC에서:
```bash
gst-launch-1.0 rtspsrc location=rtsp://<UGV IP>:8554/ugv/rcws latency=0 drop-on-latency=true protocols=tcp \
  ! rtph264depay ! h264parse ! avdec_h264 ! autovideosink sync=true qos=true
```
NVIDIA가 있으면 `avdec_h264` 대신 `nvh264dec max-display-delay=0`. VLC로도 열리지만 지연이 크다
(수신측 튜닝 근거는 `rtsp/rtsp_client_reception_guide.md`).

### 6-5. 통제기와 실제로 주고받는지

- **UGV→RC**: 통제기 화면에 속도/기어/배터리(`UGV_Period_Basicinfo`, 10Hz)와 RCWS 상태
  (`UGV_RCWS_Status`, 20Hz)가 갱신되면 송신 OK.
- **RC→UGV**: 통제기에서 제어권 획득(`RC_Control_Right`) → 운용모드 REMOTE(`RC_OperationMode`) →
  주행(`RC_RemoteDriving`) 순으로 주면 화면의 UGV가 움직여야 한다. 이 순서가 아니면 Idle이라 안 움직인다.
  - `RC_OperationMode=REMOTE` **AND** 제어권 보유 → Manual(움직임)
  - 둘 중 하나라도 아니면 Idle
  - 비상정지 래치가 걸려 있으면 무조건 Idle (해제해도 STAY로 떨어짐 — REMOTE로 자동 복귀 안 함)
- **RCWS 조준**: `RC_ActivateMovement`=RELEASE(활성) **AND** `RC_Movement.BrakeButton`=RELEASE일 때만
  pan/tilt가 먹는다(AND 조건, 2026-08-31 재매핑). 하나만 줘서는 안 돈다.
- 파싱 문제는 로그에 `JSON 파싱 실패` / `처리되지 않는 cmd '...'`(Verbose)로 남는다.

---

## 7. 자주 걸리는 것

| 증상 | 원인 / 조치 |
|---|---|
| UDP가 한 방향도 안 감, `UDP 소켓 시작` 로그 없음 | 데모 모드로 떴음 → `-fullsystem` 또는 체크박스 해제(§4-2) |
| 로그의 `send-to`가 `192.168.10.20`으로 남음 | RC IP 입력 후 Enter를 안 침(§4-1) |
| UGV→RC는 가는데 RC→UGV가 안 옴 | 통제기가 우리 PC IP의 8000/8001로 쏘고 있는지 + 방화벽(§3-3) |
| 창이 아예 안 뜸 | 순수 X11 머신 → `./titan_example_x11_fallback.sh`(§3-2) |
| 풀스크린에서 10fps대 | X11/Xwayland 경로로 뜬 것 → Wayland 세션에서 실행(§3-2) |
| RTSP 접속 거부 | 마운트가 아직 등록 안 됨(대기실 상태) / 8554 방화벽 / GStreamer 미설치 |
| RTSP는 붙는데 영상이 안 나옴 | 수신측이 UDP 전송을 시도 중 — `protocols=tcp` 필수 |
| RTSP 마운트 로그가 아예 없음 | 빌드 PC에 NVENC SDK/CUDA/GStreamer가 없어 RTSP가 빠진 채 패키징됨(§2) |
| UGV가 통제기 명령에 반응 안 함 | 제어권 → REMOTE 순서, 비상정지 래치 확인(§6-5) |

---

## 8. 참고 문서

- `protocol/protocol_icd.md` §3 — UDP/JSON ICD(IP·포트·메시지 전량), §3.3 RTSP 마운트
- `protocol/lig_icd_ugv_rc_full.md` — LIG ICD 원문
- `rtsp/rtsp_client_reception_guide.md` — **LIG 공유용** 수신측 저지연 가이드
- `rtsp/linux_wayland_x11_present_bottleneck.md` — Wayland/X11 프레임 폭락 원인·해결
- `level_new_kadex_0811/2026-09-01_scenario_run_modes_demo_fullsystem.md` — 데모/풀 시스템 스위치,
  대기실 버튼 계약, 패키징 대상 레벨
- `ui/kadex_test_dashboard_wbp_spec.md` — 대시보드 / 축 선택 위젯 구조
- `rtsp/rtsp_poc_findings.md` §10 — 리눅스 크로스컴파일 / GStreamer 번들 배경
