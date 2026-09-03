# 원격통제기 목업 GUI (rc_gui) 실행 가이드

2026-09-02 / 완료 / 파이썬 통제기 목업(`ugv_rc_gui`)을 설치·실행해서 UGV 시뮬레이터와 UDP/RTSP 연동을 확인하는 절차.

UGV 시뮬레이터(`titan_example` 리눅스 패키지)와 **UDP+JSON / RTSP로만** 통신하는 통제기 역할
프로그램입니다. 실제 통제기 SW 대신 연동을 확인하는 용도로 만든 목업이며, 시뮬레이터 실행 방법은
`kadex_0902_패키징_실행가이드.md`를 참고하세요.

---

## 1. 실행 환경

- Windows 10 / 11 64bit
- Python 3.11 이상
- **NVIDIA GPU** (영상 하드웨어 디코드에 `nvh264dec` 사용 — 없을 때는 §5)
- 조이스틱(Logitech Extreme 3D Pro)은 **선택**입니다. 없어도 GUI 버튼 + 키보드로 전 기능 사용 가능하며,
  RCWS 조준(Pan/Tilt)만 조이스틱 전용입니다.

---

## 2. 설치 (최초 1회)

### 2-1. Python 패키지

```
pip install -r requirements.txt
```

(`PyQt6`, `pygame-ce` 두 개입니다.)

### 2-2. GStreamer — 별도 설치 필요

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

## 3. 실행

```
python rc_gui_app.py --ugv-ip <UGV 시뮬레이터 PC의 IP>
```

예시:

```
python rc_gui_app.py --ugv-ip 192.168.10.10
python rc_gui_app.py --ugv-ip 127.0.0.1 --rtsp-host 127.0.0.1     # 같은 PC에서 테스트
python rc_gui_app.py --ugv-ip 192.168.10.10 --rtsp-transport udp   # RTSP를 UDP로 받기
python rc_gui_app.py --ugv-ip 192.168.10.10 --log-level DEBUG      # 상세 로그
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

| 증상 | 확인할 것 |
|---|---|
| `RuntimeError: GStreamer(MSVC 64bit) 설치를 찾을 수 없습니다` | §2-2 설치. 설치 직후라면 새 터미널을 열고 다시 실행 |
| `no element "nvh264dec"` 등 엘리먼트 없음 | GStreamer를 "Complete" 옵션으로 다시 설치 |
| 영상 패널이 노란색 "connecting"에서 안 넘어감 | 시뮬레이터가 UGV Host로 레벨에 진입했는지, `--rtsp-host`/`--ugv-ip`가 맞는지, 8554 방화벽 |
| 우측 UGV 상태가 전부 "(수신 대기중)" | "연결" 버튼을 먼저 눌렀는지, 시뮬레이터의 **RC IP**가 이 PC의 IP인지, UDP 8010/8011 방화벽 |
| 주행/조준 명령이 안 먹음 | "제어권 획득 + REMOTE"를 눌렀는지, 비상정지가 걸려있지 않은지 |
| 조이스틱 인식 안 됨 | USB 재연결 후 앱 재시작. 로그에 "조이스틱을 찾지 못함" 경고 확인 |

### NVIDIA GPU가 없는 경우

`video_panel.py`의 `PIPELINE_TEMPLATE`에서 디코더만 바꾸면 됩니다.

```python
PIPELINE_TEMPLATE = (
    "rtspsrc location={url} latency=0 drop-on-latency=true protocols={transport} "
    "! rtph264depay ! h264parse ! d3d11h264dec "
    "! d3d11videosink name=sink sync=true qos=true"
)
```

`{transport}`와 `sync=true qos=true`는 그대로 두세요(각각 `--rtsp-transport`가 들어가는 자리이고,
`sync=false`는 지연이 계속 누적되는 원인입니다).

---

## 6. 더 자세한 내용

저장소의 `README.md` — 화면 구성 상세, 프로토콜 매핑, 파일 구성, 개발용 진단 도구(`tools/`) 등.
