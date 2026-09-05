# 원격통제기 목업 GUI (rc_gui) 실행 가이드

2026-09-04 / 완료(Windows·Linux 실측 검증) / 파이썬 통제기 목업(`ugv_controller_demo`)을 설치·실행해서 UGV 시뮬레이터와 UDP/RTSP 연동을 확인하는 절차.

UGV 시뮬레이터(`titan_example` 리눅스 패키지)와 **UDP+JSON / RTSP로만** 통신하는 통제기 역할
프로그램입니다. 실제 통제기 SW 대신 연동을 확인하는 용도로 만든 목업이며, 시뮬레이터 실행 방법은
`kadex_0902_패키징_실행가이드.md`를 참고하세요.

**Windows / Linux(Ubuntu) 양쪽에서 실행됩니다.** 설치 절차만 다르고 사용법은 동일합니다
(리눅스 지원 2026-09-04 추가). 시뮬레이터와 **같은 리눅스 PC에서 로컬로** 돌려도 됩니다.

> **리눅스 세션 관련 — 신경 쓰지 않으셔도 됩니다.** 이 프로그램은 Qt를 X11(xcb) 백엔드로 띄우도록
> 코드가 알아서 설정하며, **Wayland 세션(XWayland 경유)과 Xorg 세션 양쪽에서 정상 동작을
> 확인했습니다**(2026-09-04, Ubuntu 22.04 — GUI 구동 / UDP 연동 / RTSP 영상 수신까지 실측).
> 세션 종류를 바꾸거나 확인할 필요 없이 그대로 실행하시면 됩니다.

---

## 1. 실행 환경

| 항목 | Windows | Linux |
|---|---|---|
| OS | Windows 10 / 11 64bit | Ubuntu 20.04 이상 (Wayland/Xorg 세션 모두 가능) |
| Python | 3.11 이상 | 3.11 이상 |
| GPU | NVIDIA 권장 (하드웨어 디코드) | 무관 — 기본이 소프트웨어 디코드 |
| 조이스틱 | 선택 (Logitech Extreme 3D Pro) | 선택 |

조이스틱이 없어도 GUI 버튼 + 키보드로 전 기능을 쓸 수 있습니다. **RCWS 조준(Pan/Tilt)만
조이스틱 전용**입니다.

---

## 2-A. 설치 — Windows (최초 1회)

### Python 패키지

```
pip install -r requirements.txt
```

(`PyQt6`, `pygame-ce` 두 개입니다.)

### GStreamer — 별도 설치 필요

영상 재생용 GStreamer는 pip으로 설치되지 않습니다.
https://gstreamer.freedesktop.org/download/#windows 에서 **MSVC 64bit** 버전으로 아래 둘 다 설치합니다.

- `GStreamer 1.0 Runtime installer` — 필수
- `GStreamer 1.0 Development installer` — 진단 도구(`gst-inspect-1.0.exe`)용, 선택

> ⚠️ 설치 옵션 화면에서 반드시 **"Complete"** 를 선택하세요. "Typical"로 설치하면 이 앱이 쓰는
> `nvcodec` / `d3d11` / `rtsp` / `rtp` 플러그인이 빠집니다.

설치 후 **새 터미널을 열고**(환경변수는 새 프로세스부터 반영) 확인합니다.

```
echo %GSTREAMER_1_0_ROOT_MSVC_X86_64%
```

경로가 출력되면 정상입니다. 앱이 이 환경변수로 설치 위치를 찾으므로 설치 경로가 기본값이 아니어도 됩니다.

---

## 2-B. 설치 — Linux (Ubuntu, 최초 1회)

### ① 세션 — 확인할 것 없음

Wayland 세션이든 Xorg 세션이든 **그대로 실행하면 됩니다.** 프로그램이 Qt를 X11(xcb) 백엔드로
띄우고, Wayland 세션에서는 XWayland가 이를 받습니다. 양쪽 모두 2026-09-04에 실측 확인했습니다.

> 시뮬레이터를 같은 PC에서 같이 돌리는 경우, **Xorg 세션이라면 시뮬레이터를 창모드로 띄우세요**
> (`./run_titan_example.sh`, `-fullscreen` 없이). X11에서는 풀스크린 프레임이 크게 떨어집니다.
> Wayland 세션이면 풀스크린도 정상 속도입니다.

### ② 시스템 패키지

```bash
sudo apt update

# GStreamer — 영상 수신/디코드/표시
sudo apt install -y \
  libgstreamer1.0-0 libgstreamer-plugins-base1.0-0 \
  gstreamer1.0-plugins-base gstreamer1.0-plugins-good \
  gstreamer1.0-plugins-bad gstreamer1.0-libav gstreamer1.0-x \
  gstreamer1.0-tools

# Python + Qt6(xcb 백엔드) 런타임
sudo apt install -y python3-pip python3-venv \
  libxcb-cursor0 libxcb-xinerama0 libxkbcommon-x11-0 \
  libxcb-icccm4 libxcb-image0 libxcb-keysyms1 \
  libxcb-randr0 libxcb-render-util0 libxcb-shape0
```

### ③ Python 패키지

`ugv_controller_demo` 폴더에서 가상환경을 만들어 설치합니다(시스템 파이썬을 건드리지 않기 위함 —
Ubuntu 23.04 이상은 `pip install`을 시스템 전역에 하면 막힙니다).

```bash
cd ugv_controller_demo
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

이후 새 터미널을 열 때마다 `source .venv/bin/activate`를 먼저 실행해야 합니다.

### ④ 설치 확인

```bash
gst-inspect-1.0 rtspsrc h264parse avdec_h264 videoconvert ximagesink > /dev/null && echo "GStreamer OK"
```

`No such element or plugin`이 나오면 ②의 패키지 설치를 다시 확인하세요.

---

## 3. 실행

**Windows**

```
python rc_gui_app.py --ugv-ip <UGV 시뮬레이터 PC의 IP>
```

**Linux** (가상환경 활성화 후. 명령어가 `python3`인 것 외에는 동일합니다)

```bash
source .venv/bin/activate
python3 rc_gui_app.py --ugv-ip <UGV 시뮬레이터 PC의 IP>
```

예시:

```
python rc_gui_app.py --ugv-ip 192.168.10.10
python rc_gui_app.py --ugv-ip 127.0.0.1 --rtsp-host 127.0.0.1     # 같은 PC에서 테스트
python rc_gui_app.py --ugv-ip 192.168.10.10 --rtsp-transport udp   # RTSP를 UDP로 받기
python rc_gui_app.py --ugv-ip 192.168.10.10 --log-level DEBUG      # 상세 로그
```

### 리눅스에서 시뮬레이터와 같은 PC로 테스트할 때

시뮬레이터를 **UGV Host로 레벨 진입까지 해둔 상태**에서, 다른 터미널로 아래를 실행합니다.
시뮬레이터 축 선택 화면의 **RC IP에는 `127.0.0.1`** 을 넣어 주세요.

```bash
python3 rc_gui_app.py --ugv-ip 127.0.0.1 --rtsp-host 127.0.0.1
```

### 리눅스 영상 디코더/싱크 바꾸기 (선택)

기본값은 어디서나 뜨는 조합(소프트웨어 디코드 `avdec_h264` + `videoconvert` + `ximagesink`)이고,
Wayland(XWayland)·Xorg 양쪽에서 이 조합으로 영상 수신을 확인했습니다.
NVIDIA GPU가 있으면 하드웨어 디코드로 바꿔 지연을 줄일 수 있고, Xorg 세션이면 `xvimagesink`가
더 가볍습니다. 환경변수로 지정하며 코드 수정은 필요 없습니다.

```bash
# NVIDIA 하드웨어 디코드 (gstreamer1.0-plugins-bad의 nvcodec + NVIDIA 드라이버 필요)
RC_GUI_GST_DECODER="nvh264dec max-display-delay=0" python3 rc_gui_app.py --ugv-ip 127.0.0.1

# Xorg 세션이면 더 가벼운 싱크로 (videoconvert는 자동으로 앞에 붙으므로 그대로 두면 됨)
RC_GUI_GST_SINK=xvimagesink python3 rc_gui_app.py --ugv-ip 127.0.0.1
```

IP/포트는 전부 실행 인자로만 받습니다(화면에 입력 칸 없음).

| 인자 | 기본값 | 의미 |
|---|---|---|
| `--ugv-ip` | `192.168.10.10` | UGV 시뮬레이터 PC IP |
| `--ugv-periodic-port` / `--ugv-event-port` | `8000` / `8001` | 시뮬레이터로 보내는 포트 |
| `--bind-ip` | `0.0.0.0` | 이 프로그램의 수신 바인드 주소 |
| `--rc-periodic-port` / `--rc-event-port` | `8010` / `8011` | 시뮬레이터에서 받는 포트 |
| `--rtsp-host` | `--ugv-ip`와 동일 | RTSP 서버 호스트 |
| `--rtsp-port` | `8554` | RTSP 포트 |
| `--rtsp-transport` | `tcp` | `tcp` / `udp` — 둘 다 동작 확인됨 |
| `--log-level` | `INFO` | `DEBUG`로 하면 조이스틱 축/버튼 원본값까지 로그에 출력 |

> 시뮬레이터 쪽 축 선택 화면의 **RC IP**에는 **이 프로그램을 실행하는 PC의 IP**를 넣어야 합니다.
> (시뮬레이터가 8010/8011로 보내는 목적지가 그 값입니다.)

방화벽에서 UDP 8010/8011 수신과 RTSP(TCP 8554 또는 UDP)를 막고 있지 않은지 확인하세요.
같은 PC에서 테스트하는 경우는 무관합니다.

---

## 4. 조작 순서

```
┌──────────┬──────────────────────────┬──────────────────┐
│ CCTV 4개 │      RCWS 메인뷰          │ 무장/카메라 제어   │
│ (세로)   │   (탐지 bbox 오버레이)     │ RC 로컬 상태       │
│          │                          │ UGV 수신 상태      │
├──────────┴──────────────────────────┴──────────────────┤
│                      로그 패널                            │
└────────────────────────────────────────────────────────┘
```

1. **"연결"** 버튼 — `RC_Connection` + `RC_Request_BIT` 전송. 우측 상태 패널이 "(수신 대기중)"에서
   실제 값으로 바뀌면 UDP 연동 성공입니다.
2. **"제어권 획득 + REMOTE"** 버튼 — `RC_Control_Right` + `RC_OperationMode(REMOTE)`.
   **이 시점부터** 주행/조준/무장 입력이 실제로 전송됩니다.
3. **주행** — 키보드 `W` `A` `S` `D` (`RC_RemoteDriving`, 20Hz)
4. **RCWS 조준** — 조이스틱 기울임 (`RC_Movement`). 조이스틱이 없으면 조준은 불가합니다.
5. **발사 / 사격모드 / 안전 / 장전 / 카메라(EO·IR)** — 조이스틱 버튼 또는 우측 **"무장/카메라 제어"**
   GUI 버튼. 둘은 같은 상태를 공유합니다. 발사는 홀드형이라 누르고 있어야 합니다.
6. **시동** — 툴바 "시동 끄기/켜기" 버튼.
7. **비상정지 / 비상정지 해제** — 툴바 버튼. 해제해도 REMOTE로 자동 복귀하지 않으므로,
   해제 후 **"제어권 획득 + REMOTE"를 다시 눌러야** 주행이 살아납니다.

시작 시 기본 상태는 **안전해제(ARMED) + 장전 ON + 사격모드 SINGLE + 카메라 EO**입니다.
제어권만 잡으면 바로 사격 가능하며, 안전·장전을 따로 만질 필요는 없습니다.

### 조이스틱 매핑 (Extreme 3D Pro 기준)

| 입력 | 동작 |
|---|---|
| 스틱 X/Y 기울임 | RCWS Pan/Tilt |
| Button 0 (홀드) | 발사 |
| Button 1 | 사격모드 순환 (SINGLE → BRUST → CONTINUS) |
| Button 7 (홀드) | 브레이크 — 누르는 동안 회전 정지 |
| Button 8 | 안전/암 토글 |
| Button 9 | 장전 토글 |
| Button 10 | 카메라 EO / IR 전환 |

다른 장치를 쓸 경우 `--log-level DEBUG`로 실행해 로그 패널의 축/버튼 원본값을 보고
`joystick_control.py` 상단 상수만 고치면 됩니다.

### 탐지 bbox 색

RCWS 메인뷰 위에 탐지 객체가 사각형 + `Class #ID` 라벨로 그려집니다.

| ObjectClass | 색 |
|---|---|
| `Ally` | 초록 |
| `Enemy` | 빨강 |
| `Parachute` | 주황 |
| `UGV` / `MobileCommandPost` / `Drone` | 하늘색 |
| 그 외 / 모르는 값 | 회색 |

---

## 5. 문제 해결

### 공통

| 증상 | 확인할 것 |
|---|---|
| 영상 패널이 노란색 "connecting"에서 안 넘어감 | 시뮬레이터가 UGV Host로 레벨에 진입했는지, `--rtsp-host`/`--ugv-ip`가 맞는지, 8554 방화벽 |
| 우측 UGV 상태가 전부 "(수신 대기중)" | "연결" 버튼을 먼저 눌렀는지, 시뮬레이터의 **RC IP**가 이 PC의 IP인지, UDP 8010/8011 방화벽 |
| 주행/조준 명령이 안 먹음 | "제어권 획득 + REMOTE"를 눌렀는지, 비상정지가 걸려있지 않은지 |
| 조이스틱 인식 안 됨 | USB 재연결 후 앱 재시작. 로그에 "조이스틱을 찾지 못함" 경고 확인 |

### Windows

| 증상 | 확인할 것 |
|---|---|
| `RuntimeError: GStreamer(MSVC 64bit) 설치를 찾을 수 없습니다` | §2-A 설치. 설치 직후라면 새 터미널을 열고 다시 실행 |
| `no element "nvh264dec"` 등 엘리먼트 없음 | GStreamer를 "Complete" 옵션으로 다시 설치 |
| NVIDIA GPU가 없음 | `set RC_GUI_GST_DECODER=d3d11h264dec` 후 실행(DXVA 디코드로 전환) |

### Linux

| 증상 | 확인할 것 |
|---|---|
| `RuntimeError: GStreamer 라이브러리를 찾을 수 없습니다` | §2-B ②의 apt 설치 |
| `no element "avdec_h264"` | `gstreamer1.0-libav` 설치 누락 |
| `no element "ximagesink"` | `gstreamer1.0-x` 설치 누락 |
| `Internal data stream error` + `not-negotiated (-4)` | 디코더 출력(YUV)과 싱크가 안 맞는 것. 기본 파이프라인은 `videoconvert`를 자동으로 넣으므로, 직접 `gst-launch`로 테스트할 때만 나옴 — 디코더와 싱크 사이에 `videoconvert`를 넣을 것 |
| `qt.qpa.plugin: Could not load the Qt platform plugin "xcb"` | §2-B ②의 `libxcb-*` 패키지 설치 누락. `QT_QPA_PLATFORM=xcb:debug`로 실행하면 어떤 라이브러리가 없는지 출력됩니다 |
| 창은 뜨는데 **영상 자리가 검은색** | GStreamer 파이프라인이 못 뜬 것입니다. 터미널의 `[ERROR] rc_gui.video:` 줄에 원인이 그대로 찍힙니다 |
| 영상은 나오는데 CPU 사용률이 높음 | 기본이 소프트웨어 디코드입니다. NVIDIA GPU가 있으면 `RC_GUI_GST_DECODER="nvh264dec max-display-delay=0"`으로 실행 |

> 디코더/싱크는 환경변수 `RC_GUI_GST_DECODER` / `RC_GUI_GST_SINK`로 바꿉니다 — `video_panel.py`를
> 직접 고칠 필요 없습니다. 저지연 옵션(`latency=0`, `sync=true qos=true`)은 실측으로 검증된
> 구성이라 코드에 고정되어 있습니다(`sync=false`는 지연이 계속 누적되는 원인이었습니다).

---

## 6. 더 자세한 내용

저장소의 `README.md` — 화면 구성 상세, 프로토콜 매핑, 파일 구성, 개발용 진단 도구(`tools/`) 등.
