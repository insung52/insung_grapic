# UGV 시뮬레이터 실행 가이드 (리눅스 패키지)

2026-09-02 / 완료 / 패키지 실행 → 축 선택 화면에서 RC IP 입력 → UGV Host 시작까지의 절차.

UGV 시뮬레이션 SW를 실행해서 **원격통제기와 UDP 통신 / RTSP 영상**을 연동하기 위한 문서입니다.

---

## 1. 실행 전 준비 (최초 1회)

Ubuntu 22.04 / 24.04 + NVIDIA GPU 환경 기준입니다.

```bash
sudo apt install -y \
  libgstreamer1.0-0 libgstreamer-plugins-base1.0-0 libgstrtspserver-1.0-0 \
  gstreamer1.0-plugins-base gstreamer1.0-plugins-good gstreamer1.0-plugins-bad
```

- **NVIDIA 독점 드라이버**가 설치되어 있어야 합니다(영상 인코딩에 NVENC를 사용). 없으면 게임은
  실행되지만 RTSP 영상만 나오지 않습니다.
- 방화벽을 쓰신다면 아래 포트를 열어주세요.
  ```bash
  sudo ufw allow 8000/udp   # 통제기 → UGV (주기)
  sudo ufw allow 8001/udp   # 통제기 → UGV (비주기)
  sudo ufw allow 8554/tcp   # RTSP
  ```

---

## 2. 실행

```bash
chmod +x titan_example.sh titan_example_x11_fallback.sh
./titan_example.sh
```

- 전체화면으로 띄우려면 `-fullscreen`을 추가합니다.
- 창이 뜨지 않으면(순수 X11 환경) `./titan_example_x11_fallback.sh`로 실행해 주세요.
- GNOME/Wayland 환경에서는 창 테두리와 타이틀바가 표시되지 않는 것이 정상입니다.
  `Super` 키 + 드래그로 창을 이동할 수 있습니다.

---

## 3. 축 선택 화면 — 입력 항목

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

---

## 4. UGV Host 버튼

입력을 마쳤으면 **UGV Host** 버튼을 누릅니다. 시나리오 레벨로 이동하면서 UDP 소켓과 RTSP 스트림이
열립니다.

> 옆에 있는 **Client** / **호스트 없이 시작** 버튼은 다른 용도(이동형지휘소 축, 단독 데모)입니다.
> 통제기 연동 확인에는 사용하지 않습니다.

---

## 5. 통제기 쪽 접속 정보

`<UGV IP>` = 이 프로그램을 실행한 PC의 IP.

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

연결 확인용 예시:

```bash
gst-launch-1.0 rtspsrc location=rtsp://<UGV IP>:8554/ugv/rcws latency=0 \
  ! rtph264depay ! h264parse ! avdec_h264 ! autovideosink
```

---

## 6. 확인이 필요할 때

로그 파일: `titan_example/Saved/Logs/titan_example.log`

| 확인할 내용 | 찾을 문자열 |
|---|---|
| UDP 소켓이 열렸는지, 목적지 IP가 맞는지 | `UDP 소켓 시작` |
| RTSP 스트림 5개가 열렸는지 | `Registered RTSP mount` |

| 증상 | 확인할 것 |
|---|---|
| UDP가 전혀 오가지 않음 | 데모 모드 체크박스가 해제된 상태로 시작했는지 |
| UGV → 통제기 방향만 안 감 | 로그의 `UDP 소켓 시작` 줄에 찍힌 목적지 IP가 입력한 RC IP인지 (§3의 Enter) |
| 통제기 → UGV 방향만 안 옴 | 통제기가 `<UGV IP>`의 8000/8001로 보내고 있는지, 방화벽(§1) |
| RTSP 접속이 안 됨 | UGV Host로 레벨에 들어갔는지, GStreamer 설치(§1), 8554 방화벽 |
| 창이 안 뜸 | `titan_example_x11_fallback.sh`로 실행(§2) |
| 전체화면에서 프레임이 매우 낮음 | Wayland 세션으로 로그인 후 실행(§2) |
