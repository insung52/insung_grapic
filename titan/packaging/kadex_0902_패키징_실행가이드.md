# UGV 시뮬레이터 실행 가이드 (Ubuntu)

2026-09-04 / 완료(Wayland·X11 양쪽 실측 검증) / 아무것도 설치되지 않은 Ubuntu에서 패키지 실행 → RC IP 입력 → UGV Host 시작까지.

UGV 시뮬레이션 SW를 실행해서 **원격통제기와 UDP 통신 / RTSP 영상**을 연동하기 위한 문서입니다.
**설치가 전혀 안 된 새 Ubuntu 기준**으로, §1부터 순서대로 그대로 따라 하시면 됩니다.

---

## 0. 먼저 확인해 주세요

| 항목 | 요구 사항 | 확인 명령 |
|---|---|---|
| OS | **Ubuntu 20.04 이상** (22.04 / 24.04 권장) | `lsb_release -d` |
| GPU | **NVIDIA GPU 필수** | `lspci \| grep -i nvidia` |
| 화면 | 모니터가 연결된 **데스크톱 세션**에서 실행 | — |

> ⚠️ **NVIDIA GPU가 없으면 실행되지 않습니다.** 현재 빌드는 NVIDIA 전용 라이브러리
> (`libnvidia-encode.so.1`, `libcuda.so.1`)를 필수로 요구합니다. AMD/Intel GPU, 또는 NVIDIA GPU라도
> 기본 드라이버(nouveau)만 설치된 상태에서는 창이 뜨기 전에 종료됩니다.
>
> ⚠️ **SSH 원격 접속만으로는 실행할 수 없습니다.** 화면 출력이 필요하므로 실제 모니터가 연결된
> PC 앞에서(또는 물리 화면에 연결된 원격 데스크톱 세션에서) 실행해 주세요.

---

## 1. 환경 설치 (최초 1회)

**§1-1 → §1-2 → §1-3 순서대로** 진행해 주세요. 재부팅은 §1-2에서 한 번만 하면 됩니다.

### 1-1. 필수 라이브러리 설치

```bash
sudo apt update

# (1) GStreamer + Vulkan — 없으면 프로그램이 시작조차 안 됨
sudo apt install -y \
  libgstreamer1.0-0 libgstreamer-plugins-base1.0-0 libgstrtspserver-1.0-0 \
  gstreamer1.0-plugins-base gstreamer1.0-plugins-good gstreamer1.0-plugins-bad \
  libvulkan1

# (2) 창 생성 / 입력 / 오디오 런타임 — 데스크톱 설치본이면 대부분 이미 있으나,
#     최소 설치본에서는 빠져 있어 창이 안 뜨는 원인이 됨
sudo apt install -y \
  libwayland-client0 libwayland-cursor0 libwayland-egl1 libxkbcommon0 \
  libx11-6 libx11-xcb1 libxext6 libxcursor1 libxi6 libxrandr2 libxfixes3 libxss1 libxtst6 \
  libasound2 libpulse0 libudev1 libdbus-1-3 libgl1 libstdc++6
```

> ⚠️ (1)의 라이브러리들은 **영상 기능용 선택 사항이 아니라 실행 필수 조건**입니다. 하나라도 없으면
> `error while loading shared libraries: ...` 메시지와 함께 프로그램이 시작되지 않습니다.
> (2)는 프로그램이 실행 중에 찾는 것들이라 없으면 창이 안 뜨거나 소리·입력이 동작하지 않습니다.

### 1-2. NVIDIA 독점 드라이버 + 재부팅

이미 `nvidia-smi`가 정상 동작한다면 재부팅 없이 §1-3으로 넘어가도 됩니다.

```bash
sudo apt install -y ubuntu-drivers-common
sudo ubuntu-drivers install        # 권장 드라이버 자동 선택·설치
sudo reboot                        # 재부팅 필수
```

> ⚠️ **Secure Boot가 켜져 있으면** 드라이버 설치 중에 비밀번호(MOK) 등록 화면이 나오고,
> **재부팅 시 파란 화면에서 "Enroll MOK"를 선택해 그 비밀번호를 입력해야** 드라이버가 활성화됩니다.
> 이 과정을 놓치면 재부팅 후에도 `nvidia-smi`가 실패합니다 — 그 경우 BIOS에서 Secure Boot를 끄고
> `sudo apt install --reinstall nvidia-driver-<버전>` 후 다시 재부팅하는 게 가장 간단합니다.

> ⚠️ **`nvidia-smi`가 나온다고 Vulkan까지 되는 건 아닙니다.** `nvidia-smi`는 커널 모듈만 확인하는데,
> 이 프로그램은 Vulkan으로 렌더링하므로 드라이버의 유저스페이스 부분(Vulkan ICD)도 필요합니다.
> §1-3의 Vulkan 확인을 반드시 거치세요.

### 1-3. 설치 검증 (재부팅 후)

먼저 드라이버부터 확인합니다. 표 형태로 GPU 정보가 나오면 정상입니다.

```bash
nvidia-smi
```

이어서 아래를 그대로 복사해서 실행하세요. **10줄 모두 `OK`** 여야 합니다.

```bash
for lib in libnvidia-encode.so.1 libcuda.so.1 libvulkan.so.1 \
           libglib-2.0.so.0 libgobject-2.0.so.0 \
           libgstreamer-1.0.so.0 libgstapp-1.0.so.0 libgstrtspserver-1.0.so.0 \
           libwayland-client.so.0 libxkbcommon.so.0; do
  if ldconfig -p | grep -q "$lib"; then echo "OK    $lib"; else echo "없음  $lib"; fi
done
```

`없음`이 나오면:

| 없는 라이브러리 | 해결 |
|---|---|
| `libnvidia-encode.so.1`, `libcuda.so.1` | §1-2 (NVIDIA 드라이버). `nvidia-smi`부터 확인 |
| `libvulkan.so.1` | §1-1 (1) |
| `libgstreamer-*`, `libgstapp-*`, `libgstrtspserver-*`, `libglib-*`, `libgobject-*` | §1-1 (1) |
| `libwayland-client.so.0`, `libxkbcommon.so.0` | §1-1 (2) |

#### ⚠️ Vulkan 드라이버(ICD) 확인 — 위 검사만으로는 부족합니다

`libvulkan.so.1`은 **로더**일 뿐이고, 실제 그림을 그리는 건 GPU 벤더가 제공하는 **드라이버 등록
파일(ICD)** 입니다. 로더만 있고 ICD가 없으면 위 검사는 전부 `OK`인데 실행 시
**"Failed to load Vulkan Driver which is required to run the engine."** 로 종료됩니다.
`nvidia-smi`도 이 경우 정상 동작합니다(커널 모듈만 보기 때문) — 실제로 이 조합으로 실행이 막힌
사례가 있었습니다.

```bash
sudo apt install -y vulkan-tools

# ① ICD 파일이 있어야 함 — NVIDIA면 nvidia_icd.json
ls /usr/share/vulkan/icd.d/

# ② 실제로 GPU가 잡히는지 (driverName / deviceName 이 나와야 정상)
vulkaninfo --summary | head -30
```

`/usr/share/vulkan/icd.d/`가 비어 있거나 `vulkaninfo`가 장치를 못 찾으면 드라이버의 유저스페이스
부분이 빠진 것입니다. 드라이버를 재설치하세요.

```bash
sudo apt install --reinstall nvidia-driver-550    # 설치된 버전에 맞게. nvidia-smi 우측 상단에 표시됨
sudo reboot
```

> `nvidia-headless-*` / `nvidia-driver-*-server` 계열이나 `.run` 설치본을 옵션 없이 설치하면
> 커널 모듈만 깔리고 Vulkan ICD(`libnvidia-gl-<버전>`)가 빠질 수 있습니다.

### 1-4. 방화벽 (사용 중일 때만)

```bash
sudo ufw allow 8000/udp   # 통제기 → UGV (주기)
sudo ufw allow 8001/udp   # 통제기 → UGV (비주기)
sudo ufw allow 8554/tcp   # RTSP
```

---

## 2. 패키지 준비

전달받은 압축을 풀면 아래 구조입니다.

```
run_titan_example.sh              ← ★ 이걸로 실행하세요 (세션 자동 판별)
titan_example.sh                  ← 엔진이 생성한 원본 실행 스크립트
titan_example_x11_fallback.sh     ← X11 강제용 (run_titan_example.sh를 쓰면 불필요)
titan_example/                    ← 게임 데이터
Engine/
```

압축 방식에 따라 실행 권한이 사라지므로, 압축을 푼 폴더에서 아래를 실행해 주세요.

```bash
chmod +x run_titan_example.sh titan_example.sh titan_example_x11_fallback.sh
chmod +x titan_example/Binaries/Linux/titan_example
```

이어서 실행 전 최종 점검입니다. **아무것도 출력되지 않아야** 정상입니다.

```bash
ldd titan_example/Binaries/Linux/titan_example | grep "not found"
```

`not found`가 나오면 그 라이브러리가 빠진 것이므로 §1-3의 표를 참고해 주세요.

---

## 3. 실행

```bash
./run_titan_example.sh
```

이 스크립트가 **현재 세션이 Wayland인지 X11인지 자동으로 판별해서** 알맞은 옵션으로 실행합니다.
세션 종류를 미리 확인하실 필요 없습니다. 실행 시 어느 쪽으로 떴는지 한 줄 출력됩니다.

| 세션 | 스크립트 동작 | 결과 |
|---|---|---|
| Wayland | 옵션 없이 실행 | 네이티브 Wayland |
| X11(Xorg) 또는 Wayland 없는 PC | `-sdlvideodriver=x11` 추가 | 네이티브 X11 |

**양쪽 모두 2026-09-04에 Ubuntu 22.04에서 실측 확인했습니다.** XWayland 경유로 잘못 뜨는 경우는
없습니다(Wayland 세션이면 네이티브 Wayland로 보내기 때문).

제대로 떴는지는 로그로도 확인할 수 있습니다.

```bash
grep "SDL video driver" titan_example/Saved/Logs/titan_example.log
# X11  : Command line override: SDL video driver set to 'x11'  / Using SDL video driver 'x11'
# Wayland: INI override: SDL video driver set to 'wayland'     / Using SDL video driver 'wayland'
```

전체화면으로 띄우려면 뒤에 `-fullscreen`을 붙입니다(그 외 인자도 그대로 전달됩니다).

```bash
./run_titan_example.sh -fullscreen
```

<details>
<summary>수동으로 지정하고 싶을 때</summary>

```bash
./titan_example.sh                        # Wayland 세션 전용 (기본 설정이 wayland 강제)
./titan_example.sh -sdlvideodriver=x11    # X11 세션
```

⚠️ Wayland 컴포지터가 없는 PC에서 `./titan_example.sh`를 옵션 없이 실행하면
`Could not initialize SDL: wayland not available`로 **즉시 종료**됩니다. 이 경우 위의
`-sdlvideodriver=x11`을 주거나 `run_titan_example.sh`를 쓰세요.

</details>

- **반드시 터미널에서 실행해 주세요.** 실행에 실패하면 원인이 터미널 출력에만 표시됩니다
  (라이브러리 문제로 못 뜨는 경우에는 로그 파일도 생성되지 않습니다).
- **`-vulkan` / `-dx12` / `-opengl` / `-sm5` 같은 렌더러 인자는 주지 마세요.** 리눅스는 Vulkan이
  기본이고 다른 값은 지원하지 않습니다. 실행이 안 될 때 이런 인자로 우회를 시도하면
  `Trying to force specific Vulkan feature level but it is not supported.` 같은 **다른 에러로
  바뀌기만 해서** 원인 파악이 더 어려워집니다. 인자 없이 실행하고 §6을 보세요.
- GNOME/Wayland에서는 **창 테두리와 타이틀바가 없는 것이 정상**입니다. `Super` 키를 누른 채
  드래그하면 창을 옮길 수 있습니다.
- 첫 실행은 셰이더 준비 때문에 시간이 조금 걸릴 수 있습니다.

---

## 4. 축 선택 화면 — 입력 항목

실행하면 축 선택 화면이 먼저 뜹니다. **UGV Host 버튼을 누르기 전에** 아래 값을 입력합니다.

### 필수 — RC IP

| 항목 | 넣을 값 | 기본값 |
|---|---|---|
| **RC IP** | **원격통제기 SW가 실행되는 PC의 IP** | `192.168.10.20` |

> ⚠️ **입력 후 반드시 Enter를 눌러주세요.** 입력값은 Enter를 누르거나 다른 곳을 클릭해서 커서가
> 빠져나갈 때 반영됩니다. 타이핑만 하고 바로 Host 버튼을 누르면 기본값이 그대로 사용됩니다.

### 선택 — 포트

기본값이 ICD 규격값이라 보통 바꿀 필요가 없습니다. 바꿀 경우 각 칸마다 Enter를 눌러주세요.

| 항목 | 기본값 |
|---|---|
| RC Periodic Port | `8010` |
| RC Event Port | `8011` |
| UGV Listen Periodic Port | `8000` |
| UGV Listen Event Port | `8001` |

### 선택 — RTSP 송출 해상도

바꾸지 않으면 기본값으로 송출됩니다. 역시 각 칸마다 Enter가 필요합니다.

| 항목 | 기본값 |
|---|---|
| RCWS 조준경 (가로 × 세로) | `1920` × `1080` |
| CCTV 4방 공통 (가로 × 세로) | `320` × `180` |

### 데모 모드 체크박스

기본값(해제) 그대로 두세요. 체크하면 통제기 없이 혼자 돌아가는 데모로 실행되어 UDP 통신이 되지
않습니다.

### UGV Host 버튼

입력을 마쳤으면 **UGV Host** 버튼을 누릅니다. 시나리오 레벨로 이동하면서 UDP 소켓과 RTSP 스트림이
열립니다.

> 옆에 있는 **Client** / **호스트 없이 시작** 버튼은 다른 용도(이동형지휘소 축, 단독 데모)입니다.
> 통제기 연동 확인에는 사용하지 않습니다.

---

## 5. 통제기 쪽 접속 정보

`<UGV IP>` = 이 프로그램을 실행한 PC의 IP (`ip addr`로 확인).

### UDP (JSON)

| 방향 | 주소 |
|---|---|
| 통제기 → UGV | `<UGV IP>` : **8000**(주기) / **8001**(비주기) |
| UGV → 통제기 | 축 선택 화면에 입력한 **RC IP** : **8010**(주기) / **8011**(비주기) |

### RTSP (5개 스트림)

| 스트림 | URL |
|---|---|
| RCWS 조준경 | `rtsp://<UGV IP>:8554/ugv/rcws` |
| 전면 CCTV | `rtsp://<UGV IP>:8554/ugv/front_cctv` |
| 후면 CCTV | `rtsp://<UGV IP>:8554/ugv/rear_cctv` |
| 좌측 CCTV | `rtsp://<UGV IP>:8554/ugv/left_cctv` |
| 우측 CCTV | `rtsp://<UGV IP>:8554/ugv/right_cctv` |

- 코덱은 H.264 High Profile, B프레임 없음. RTP 전송은 TCP(interleaved) / UDP 둘 다 됩니다.
- 스트림은 UGV Host로 레벨에 진입한 뒤에 열립니다. 축 선택 화면 상태에서는 아직 접속되지 않습니다.

연결 확인용 예시입니다. 이 명령에만 필요한 패키지를 먼저 설치해 주세요
(`avdec_h264`는 §1-1에서 설치한 패키지들에 들어있지 않고 `gstreamer1.0-libav`에 있습니다).

```bash
sudo apt install -y gstreamer1.0-tools gstreamer1.0-libav

gst-launch-1.0 rtspsrc location=rtsp://<UGV IP>:8554/ugv/rcws latency=0 \
  ! rtph264depay ! h264parse ! avdec_h264 ! autovideosink
```

- `no element "avdec_h264"` → 위 `gstreamer1.0-libav` 설치 누락
- `autovideosink`에서 오류가 나면 `ximagesink`로 바꿔서 다시 시도
- **창이 뜨긴 하는데 계속 검은 화면이면 그대로 두지 마시고 알려주세요.** 접속은 됐는데 영상
  데이터가 안 오는 상태이며, 시뮬레이터 쪽 로그를 같이 봐야 합니다.

---

## 6. 문제 해결

### 실행이 안 될 때

| 터미널에 나오는 메시지 / 증상 | 원인과 조치 |
|---|---|
| **`Failed to load Vulkan Driver which is required to run the engine.`** | Vulkan ICD 없음. `nvidia-smi`가 되더라도 발생합니다 → §1-3의 Vulkan 확인 |
| **`Could not initialize SDL: wayland not available`** + `InitSDL() failed` | Wayland가 없는 X11 전용 환경 → §3의 X11 실행 방법 |
| `Vulkan Driver is required to run the engine.` (`-vulkan` 지정 시) | 위와 동일 원인 |
| `Trying to force specific Vulkan feature level but it is not supported.` | `-sm5` 같은 RHI 인자를 준 경우 → §3 참고, 인자를 빼고 실행 |
| `error while loading shared libraries: libnvidia-encode.so.1` 또는 `libcuda.so.1` | NVIDIA 독점 드라이버 미설치 → §1-2 |
| `error while loading shared libraries: libgst...` / `libglib...` | GStreamer 미설치 → §1-1 (1) |
| `Permission denied` | 실행 권한 없음 → §2의 `chmod +x` |
| 창이 안 뜨고 SDL / video driver 관련 메시지 | 세션 종류 확인(§3). `x11`이면 `titan_example_x11_fallback.sh`로 실행. 그래도 안 되면 §1-1 (2) 설치 확인 |
| Vulkan / RHI 관련 오류 | `libvulkan1`(§1-1)과 `nvidia-smi`(§1-2) 확인. `sudo apt install -y vulkan-tools` 후 `vulkaninfo \| head`로 NVIDIA 드라이버가 잡히는지 추가 확인 가능 |
| 소리가 안 남 / 오디오 장치 오류 | §1-1 (2)의 `libasound2`, `libpulse0` 설치 확인 (실행 자체에는 지장 없음) |
| 전체화면에서 프레임이 매우 낮음 | X11 세션에서는 정상입니다(알려진 제약). 창모드로 쓰시거나, Wayland 세션이 있는 PC라면 그쪽에서 실행하세요 |

### 통신이 안 될 때

로그 파일: `titan_example/Saved/Logs/titan_example.log`

| 확인할 내용 | 로그에서 찾을 문자열 |
|---|---|
| UDP 소켓이 열렸는지, 목적지 IP가 맞는지 | `UDP 소켓 시작` |
| RTSP 스트림 5개가 열렸는지 | `Registered RTSP mount` |

| 증상 | 확인할 것 |
|---|---|
| UDP가 전혀 오가지 않음 | 데모 모드 체크박스가 해제된 상태로 시작했는지(§4) |
| UGV → 통제기 방향만 안 감 | 로그의 `UDP 소켓 시작` 줄에 찍힌 목적지 IP가 입력한 RC IP인지 (§4의 Enter) |
| 통제기 → UGV 방향만 안 옴 | 통제기가 `<UGV IP>`의 8000/8001로 보내고 있는지, 방화벽(§1-4) |
| RTSP 접속이 안 됨 | UGV Host로 레벨에 들어갔는지, 8554 방화벽(§1-4) |
