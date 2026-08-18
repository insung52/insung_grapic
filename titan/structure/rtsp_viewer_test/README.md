# RTSP 뷰어/테스트 클라이언트 (UGV축 5스트림 + 자체방호축 7스트림 검증용)

titan(KADEX UGV/자체방호 시뮬레이터) 프로젝트의 순수 영상 스트리밍 테스트 서브태스크
산출물. **UE(언리얼) 작업은 전혀 포함되지 않음** — `protocol_icd.md` §3.3/§4.1에 정의된
UGV축/자체방호축 RTSP 인터페이스(각 축 SW가 RTSP 서버가 되어 카메라 영상(UGV 5개/자체방호
7개)을 내보내는 구조)를 검증하기 위한 **수신 클라이언트**와, 그 클라이언트를 실제 서버 없이도
개발/검증할 수 있게 해주는 **로컬 테스트용 가짜 RTSP 서버**로 구성됨. 원래 UGV축 5스트림만
다뤘으나(초기 산출물), 2026-08-17 RTSP 연결 세션에서 `streams_config.selfdefense.example.json`을
추가해 자체방호축도 같은 클라이언트로 검증 가능해짐 — 코드(`rtsp_test_client.py`) 변경 없음,
config 파일만 추가.

실제 UGV RTSP 서버(UE에서 NVENC+GStreamer로 인코딩해서 송출하는 쪽)는 이 폴더와 무관하게
**다른 세션이 `titan_example` UE 프로젝트에서 별도로 구현 중**이다 (진행상황:
`C:\working\insung_grapic\titan\structure\rtsp_poc_findings.md`). 이 폴더의 코드는 그
작업을 전혀 건드리지 않으며, 서버가 완성되면 URL만 바꿔서 그대로 붙을 수 있도록 만들어졌다.

---

## 폴더 구성

```
rtsp_viewer_test/
  rtsp_test_client.py            # RTSP 수신 테스트 클라이언트 (Python + OpenCV)
  requirements.txt               # 클라이언트 의존성 (opencv-python-headless, numpy)
  streams_config.json            # UGV축 5스트림 목록 (기본: 로컬 테스트 서버를 가리킴)
  streams_config.real.example.json  # 실제 UGV 서버용 예시 설정
  start_local_test_server.ps1    # 로컬 테스트용 가짜 RTSP 서버 기동 스크립트
  stop_local_test_server.ps1     # 위 서버 정지 스크립트
  tools/
    mediamtx.exe, mediamtx.yml   # 경량 RTSP 서버 (다운로드한 릴리스 바이너리)
    local_server.pids.json       # (실행 중일 때만) 뜬 프로세스 PID 기록, stop 스크립트가 사용
  snapshots/                     # 테스트 클라이언트가 저장한 첫/마지막 프레임 JPG
  logs/                          # mediamtx/gstreamer 로그 + 클라이언트 JSON 결과 로그
```

---

## 1. 사전 준비 (이 컴퓨터엔 이미 되어 있음)

| 도구 | 용도 | 상태 |
|---|---|---|
| Python 3.x + `pip install -r requirements.txt` | 클라이언트 실행 (`opencv-python-headless`, `numpy`) | 설치 확인함(Python 3.14) |
| GStreamer (MSVC x86_64, Complete), env `GSTREAMER_1_0_ROOT_MSVC_X86_64` | **로컬 테스트 서버 전용** — 테스트 패턴을 인코딩해서 RTSP로 publish | 이미 설치돼 있음(`C:\Program Files\gstreamer\1.0\msvc_x86_64`, 다른 트랙인 RTSP 인코더 PoC가 설치한 것을 재사용) |
| `tools\mediamtx.exe` (mediamtx v1.20.0, Apache-2.0) | **로컬 테스트 서버 전용** — 경량 RTSP 서버 | 이 폴더에 다운로드해서 포함시킴 |

**ffmpeg/ffplay CLI는 이 컴퓨터에 설치돼 있지 않다** (`where ffmpeg` 실패 확인). 그래서:
- 클라이언트는 ffmpeg CLI를 직접 wrapping하는 대신 **Python `opencv-python`**을 사용함 —
  Windows용 `opencv-python` 휠은 FFmpeg 기반 디코더가 내장되어 있어서 별도 ffmpeg 설치 없이
  RTSP(H.264)를 그대로 받을 수 있다.
- 로컬 테스트용 서버 쪽(테스트 패턴 생성+RTSP publish)은 ffmpeg 대신 **이미 설치되어 있던
  GStreamer**(`gst-launch-1.0` + `videotestsrc`/`x264enc`/`rtspclientsink`)로 대체 구현.
- 만약 나중에 ffmpeg CLI를 새로 설치한다면 클라이언트는 그대로 두고 써도 되고, 로컬 서버
  스크립트를 `ffmpeg -re -f lavfi -i testsrc ... -f rtsp rtsp://.../stream`류로 바꿔도 된다
  (필수는 아님 — 지금 방식으로 충분히 검증됨).

---

## 2. 사용법

### 2.1 로컬 테스트 서버 띄우기 (실제 UGV 서버 없이 클라이언트 검증)

```powershell
cd C:\working\insung_grapic\titan\structure\rtsp_viewer_test
.\start_local_test_server.ps1
```

mediamtx(RTSP 서버, **포트 8564** — 이유는 §4 참고)를 백그라운드로 띄우고, GStreamer로
UGV축 5스트림 이름에 맞는 테스트 패턴 영상 5개를 그 서버로 publish한다. 스트림마다 다른
테스트패턴 + 타임코드 오버레이(실시간 갱신 확인용) + 스트림 이름 텍스트를 넣어서, 실제로
5개가 서로 다른 영상으로 구분되는지 스냅샷으로도 눈으로 확인 가능.

```
rtsp://127.0.0.1:8564/front_cctv    (전면CCTV)
rtsp://127.0.0.1:8564/rear_cctv     (후면CCTV)
rtsp://127.0.0.1:8564/left_cctv     (좌측CCTV)
rtsp://127.0.0.1:8564/right_cctv    (우측CCTV)
rtsp://127.0.0.1:8564/rcws_viewer   (RCWS뷰어)
```

멈출 때:
```powershell
.\stop_local_test_server.ps1
```

### 2.2 테스트 클라이언트 실행

```powershell
pip install -r requirements.txt   # 최초 1회

# streams_config.json에 정의된 5개 스트림을 10초씩 "동시에" 테스트 + 스냅샷 저장
python rtsp_test_client.py --config streams_config.json --duration 10 --snapshot

# 개별 URL 직접 지정 (5개 다 안 띄웠거나 하나만 볼 때)
python rtsp_test_client.py --urls rtsp://127.0.0.1:8564/front_cctv --duration 5

# 동시 접속 부하를 피하고 하나씩 순서대로 테스트
python rtsp_test_client.py --config streams_config.json --sequential
```

출력 예시(콘솔에 표로 요약, `logs/rtsp_test_<타임스탬프>.json`에도 상세 저장):

```
STREAM          RESULT      FPS         해상도     프레임수    경과(s)   최대gap(s)  URL / 비고
front_cctv      OK        24.54    1280x720       74     3.02       0.04  rtsp://127.0.0.1:8564/front_cctv
rear_cctv       OK        18.27    1280x720       55     3.01       0.05  rtsp://127.0.0.1:8564/rear_cctv
...
총 5개 중 5개 성공, 0개 실패
```

종료 코드: 전부 성공하면 `0`, 하나라도 실패하면 `2` (CI/스크립트에서 체크용).

---

## 3. 로컬 테스트 결과 (실제로 실행해서 확인함)

- `start_local_test_server.ps1`로 5스트림을 띄우고 `rtsp_test_client.py --config
  streams_config.json --duration 10 --snapshot`로 **동시에** 검증 → **5개 스트림 전부
  OK, 해상도 1280x720 정상 수신, `max_gap` 전부 0.03~0.07초 수준**(끊김/프리즈 없이 계속
  들어옴을 의미).
- 스냅샷(`snapshots/*_first_*.jpg`, `*_last_*.jpg`)을 열어서 확인한 결과, 타임코드
  오버레이 값이 첫 프레임과 마지막 프레임 사이에 실제로 흘러가 있음(예: `0:00:30.037` →
  `0:00:35.035`) — **정적 이미지가 아니라 실시간으로 갱신되는 영상이 실제로 오고 있음**을
  확인.
- FPS는 스트림당 **11~28 사이로 변동** — 인코딩 목표는 30fps인데, 이 컴퓨터에서 **소프트웨어
  x264 인코더 5개를 동시에 돌리다 보니 CPU 자원 경합으로 인코딩 자체가 30fps를 못 채운 것**
  (max_gap이 낮은 걸 보면 네트워크/수신 쪽 문제가 아니라 송출 쪽 인코딩 속도 문제).
  **실제 UGV 서버는 NVENC 하드웨어 인코딩**(`protocol_icd.md` §7)이라 이런 CPU 경합 자체가
  없음 — 이 변동폭은 로컬 테스트 하네스(소프트웨어 인코딩 5중 구동)의 한계이지, 클라이언트나
  프로토콜의 문제가 아님.
- `--urls`로 존재하지 않는 path를 지정해서 실패 케이스도 확인함 → `FAIL`, "8초 내 프레임
  수신 실패" 에러 메시지 정확히 출력, 정상 스트림과 섞여도 서로 영향 없이 개별 판정됨.
- `--sequential`(순차) / 동시 모드 둘 다 정상 동작 확인.
- 클라이언트는 **최초 접속(open) 실패 시 자동 재접속을 시도**한다(`CONNECT_TIMEOUT_SEC=8초`
  간격으로, 전체 `--duration` 안에서). 서버가 막 올라오는 중이라 아직 해당 path가 안 열려
  있는 경우나(예: 실제 UGV 서버가 재시작 중) 네트워크가 잠깐 끊겼다가 복구되는 상황을
  흉내내는 테스트에서도 이 재접속 로직으로 복구되는 것까지 확인함(결과표에 "재접속 N회"로
  표시).

---

## 4. 로컬 테스트 서버가 포트 8554가 아니라 **8564**를 쓰는 이유

`protocol_icd.md` §3.3의 UGV RTSP 잠정 포트는 8554다. 하지만 **이 컴퓨터에서 다른 세션이
`titan_example` UE 프로젝트의 실제 RTSP PoC 작업을 진행 중**이고, 그 PoC도 로컬에서
`rtsp://127.0.0.1:8554/poc/stream0`로 테스트한다(`rtsp_poc_findings.md` §6, VLC로 재생
확인하는 절차). 실제로 이 작업 도중 그 세션의 VLC/클라이언트가 8554로 붙는 시도가 mediamtx
로그에 잡히는 걸 확인했다 — **두 로컬 테스트가 같은 포트를 놓고 충돌할 뻔한 상황**이라,
이 폴더의 로컬 가짜 서버는 **8564로 분리**해서 절대 안 겹치게 했다(`tools/mediamtx.yml`의
`rtspAddress`, `start_local_test_server.ps1`의 `-Port` 기본값). 필요 없는 RTMP/HLS/WebRTC/SRT
프로토콜도 `mediamtx.yml`에서 꺼서 포트 점유를 최소화했고, RTSP 전송도 TCP만 열어서
(`rtspTransports: [tcp]`) UDP 8000/8001(공교롭게도 `protocol_icd.md` §3.1의 UGV 커맨드
UDP 포트와 같은 번호)까지 열리지 않게 함 — 다른 트랙(UDP 프로토콜 클라이언트)의 로컬
테스트와도 포트 충돌 여지를 없앴다.

**이건 로컬 테스트 서버끼리의 문제일 뿐, 클라이언트 사용법에는 영향 없다** — 클라이언트는
어떤 포트든 URL로 그대로 받는다.

---

## 5. 실제 UGV RTSP 서버가 준비되면 (URL만 바꿔서 그대로 쓰는 법)

이 클라이언트는 로컬/실제 서버를 코드 수정 없이 URL만으로 전환하도록 만들어졌다. 세 가지
방법 중 편한 걸 쓰면 됨:

**방법 A — `--base`로 그때그때 덮어쓰기 (파일 수정 없음, 가장 간단)**
```powershell
python rtsp_test_client.py --config streams_config.json --base rtsp://192.168.10.10:8554 --duration 10
```

**방법 B — `streams_config.json`의 `base_url`을 실제 서버로 직접 수정**
```json
"base_url": "rtsp://192.168.10.10:8554"
```
(IP `192.168.10.10`은 `protocol_icd.md` §3.3 기준 확정, 포트 `8554`는 잠정치 — 실제 값은
LIG 참조 모듈 도착 후 확인 필요)

**방법 C — `streams_config.real.example.json` 참고/복사**
이미 실제 서버용 예시로 채워서 같이 넣어뒀다(`base_url: rtsp://192.168.10.10:8554`). 그대로
`--config streams_config.real.example.json`으로 쓰거나, 실제 값 확정되면 이 파일 자체를
고쳐서 정식 설정으로 승격시켜도 됨.

**주의할 점**:
- `path`는 이제 **실제 값으로 확정됨**(2026-08-17, `protocol_icd.md` §3.3/§4.1 갱신 —
  UGV축 `ugv/front_cctv` 등, 자체방호축 `selfdefense/front_cctv` 등, `<axis>/<stream>` 패턴).
  `streams_config.real.example.json`이 이미 이 값으로 갱신돼 있음 — UGV축 실제 서버가 뜨면
  그대로 `--config streams_config.real.example.json`으로 붙이면 됨.
- **자체방호축(7스트림) 설정은 `streams_config.selfdefense.example.json`에 별도로 있음**
  (이전엔 이 폴더가 UGV축 5스트림만 다뤘음 — 2026-08-17에 추가). `base_url`의
  `<selfdefense-pc-ip>`만 실제 IP로 바꾸면 됨(고정 IP 여부 미확정 — `protocol_icd.md` §6).
- 로컬 테스트 서버(`start_local_test_server.ps1`)는 실제 서버가 준비되면 더 이상 필요
  없다. 그냥 안 띄우고 클라이언트만 실제 서버 URL로 실행하면 됨.
- 실제 UGV 서버는 NVENC 하드웨어 인코딩이라 §3에서 관찰된 것 같은 소프트웨어 인코딩발
  FPS 변동은 없을 것으로 예상 — 대신 실제 네트워크(192.168.10.x LAN) 지연/유실 특성이
  로컬 loopback 테스트와는 다를 수 있으니, `max_gap_sec`/`measured_fps` 값을 다시
  기준선으로 삼아 비교하면 됨.

---

## 6. 클라이언트 옵션 요약

```
python rtsp_test_client.py --config streams_config.json [--base URL] [--duration SEC]
                            [--snapshot] [--snapshot-dir DIR] [--log-dir DIR]
                            [--sequential] [--no-log]
python rtsp_test_client.py --urls URL [URL ...] [기타 옵션 동일]
```

| 옵션 | 설명 |
|---|---|
| `--config` | 스트림 목록 JSON (`streams_config.json` 등). `--urls`와 상호 배타 |
| `--urls` | RTSP URL을 직접 나열 |
| `--base` | `--config` 사용 시 `base_url`을 일시적으로 덮어씀 (파일 수정 없이 서버 전환) |
| `--duration` | 스트림당 수신 테스트 시간(초), 기본 10 |
| `--snapshot` | 첫/마지막 프레임을 `snapshots/`에 JPG로 저장 |
| `--sequential` | 5개를 동시가 아니라 하나씩 순차로 테스트 |
| `--no-log` | `logs/`에 JSON 결과 로그를 안 남김 |

측정 항목: 접속 성공 여부(`OK`/`FAIL`), 측정 FPS, 해상도, 수신 프레임 수, 경과 시간,
프레임 간 최대 gap(끊김 감지), 재접속 횟수, (옵션) 스냅샷 경로.

---

## 7. 트러블슈팅

- **`giolibproxy.dll` 관련 GStreamer 경고**: `logs/gst_*.err.log`에 항상 나오는데 무해함
  (프록시 자동감지 모듈 하나가 없다는 경고일 뿐, 로컬 loopback 테스트엔 영향 없음).
- **`start_local_test_server.ps1` 실행 시 일부 스트림이 재시도됨**: 로컬에서 소프트웨어
  인코더 5개를 순간적으로 같이 띄우다 보니 가끔 mediamtx가 막 뜬 직후 특정 publish 요청을
  일시적으로 거부하는 경우가 있어서, 스크립트가 스트림당 최대 3회까지 자동 재시도한다.
  최종적으로도 실패하면 콘솔에 `WARNING`으로 어느 스트림인지, 어느 로그(`logs/gst_<name>.err.log`)를
  볼지 알려준다 — 재실행(`stop` → `start`)하면 대개 해결됨.
- **Windows 방화벽 프롬프트**: `mediamtx.exe`를 처음 실행하면 방화벽 허용 팝업이 뜰 수
  있음(로컬 loopback만 쓰면 굳이 허용 안 해도 되지만, 다른 PC에서 이 로컬 서버에 접속해서
  보고 싶으면 허용 필요).
- **서버 띄우고 바로 테스트하면 일부 스트림 프레임 수가 비정상적으로 적게 나옴**: 로컬
  소프트웨어 인코더 5개가 갓 시작한 직후(수 초 이내)는 인코딩 파이프라인이 아직 완전히
  안정화되지 않은 상태라 프레임이 드문드문 들어올 수 있다. `start_local_test_server.ps1`
  실행 후 몇 초 여유를 두고 클라이언트를 실행하거나, `--duration`을 8~10초 이상으로 주면
  이 워밍업 구간의 영향이 상대적으로 작아져서 안정적인 수치가 나온다. 실제 UGV 서버(단일
  하드웨어 인코더)는 이런 "5개 동시 워밍업" 상황 자체가 없다.
- **클라이언트가 계속 FAIL**: 먼저 `.\start_local_test_server.ps1`이 정상적으로 5개 다
  띄웠는지(경고 없이 끝났는지) 확인하고, `logs/mediamtx.log`에 `stream is available and
  online` 라인이 5개 다 있는지 확인. 실제 서버 대상이면 방화벽/네트워크(192.168.10.x 대역
  라우팅) 문제일 수 있음.
