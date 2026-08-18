# rc_gui — UGV 원격통제기(RC) 목업 GUI

`Network/UGVRemoteControlSubsystem.*`(UE, titan_example)을 상대로 실제 조이스틱/키보드 입력 +
RTSP 영상 확인까지 되는 임시 통제기 프로그램. `udp_protocol_client/rc_mock_client.py`의
프로토콜 레이어(Envelope 인코딩/포트 라우팅/연결 시맨틱)를 그대로 재사용한다.

## 화면 구성

```
┌──────────┬──────────────────────────┬──────────────┐
│ CCTV 4개 │      RCWS 메인뷰          │  UGV 상태정보 │
│ (세로)   │      (크게)               │  (텍스트)     │
├──────────┴──────────────────────────┴──────────────┤
│                    로그 패널                          │
└──────────────────────────────────────────────────────┘
```

- RTSP 마운트는 `VehicleRtspBridgeComponent.h`에 확정된 UGV축 5-스트림 이름을 그대로 씀:
  `<rtsp-base>/ugv/{front_cctv, rear_cctv, left_cctv, right_cctv, rcws}`
- 우측 상태 패널은 UE측이 실제로 보내는 cmd(`UGV_Period_*`, `UGV_Response_*`, `RPT_ObjectiveReached`)를
  전부 원문 필드 그대로 나열함 — `main_window.py`의 `STATUS_GROUPS` 참고.

## 설치

```
pip install -r requirements.txt
```

Python 3.14 기준 `pygame`(정식)은 아직 이 버전용 prebuilt wheel이 없어서 **`pygame-ce`**(커뮤니티
에디션, API 동일 — `import pygame`으로 그대로 씀)를 대신 씀.

## 실행

```
python rc_gui_app.py --ugv-ip 192.168.10.10
python rc_gui_app.py --ugv-ip 100.x.x.x --rtsp-host 100.x.x.x   # Tailscale 등 IP 다를 때
python rc_gui_app.py --ugv-ip 127.0.0.1 --rtsp-host 127.0.0.1 --log-level DEBUG
```

IP/포트는 전부 실행 인자로만 받는다(UI에 입력 필드 없음) — `rc_mock_client.py`와 동일한
`--ugv-ip`/`--ugv-periodic-port`/`--ugv-event-port`/`--bind-ip`/`--rc-periodic-port`/
`--rc-event-port` 세트 그대로. RTSP는 `--rtsp-host`(기본값 `--ugv-ip`와 동일)/`--rtsp-port`
(기본 8554).

실행 후 순서:
1. 상단 "연결" 버튼 — `RC_Connection` + `RC_Request_BIT`
2. "제어권 획득 + REMOTE" 버튼 — `RC_Control_Right` + `RC_OperationMode(REMOTE)`, 이 시점부터
   조이스틱/키보드 입력이 실제로 송신되기 시작함
3. 주행: **키보드 WASD** (`RC_RemoteDriving`, 20Hz)
4. RCWS 조준: **조이스틱** 기울임 (`RC_Movement`)
5. 조이스틱 버튼: 사격/장전/암스위치/시동/사격모드/카메라전환/비상정지 (`joystick_control.py` 상단 상수 참고)

## 조이스틱 매핑 — 확인 필요 (placeholder)

실제 연결된 장치는 **Extreme 3D Pro**(단일 스틱, 축 4개/버튼 12개)로 확인됨(2026-08-18).
듀얼스틱 게임패드가 아니라서 주행/조준을 한 스틱으로 동시에 못 하고, 사용자 결정으로:
- **주행 = 키보드 WASD** (`keyboard_driving.py`)
- **조이스틱 = RCWS 조준(Pan/Tilt) 전용 + 사격 관련 버튼** (`joystick_control.py`)

버튼 인덱스(`BUTTON_FIRE` 등)는 아직 실기기로 검증 안 된 placeholder다. `--log-level DEBUG`로
실행하면 로그 패널에 매 tick 축/버튼 원본 값이 찍히니, 조이스틱을 눌러보면서 어떤 인덱스가
뭔지 확인 후 `joystick_control.py` 맨 위 상수만 고치면 됨.

## 알려진 제약 (v1 스코프)

- **탐지 객체 bbox 오버레이 없음** — 우측 상태 패널에 텍스트 리스트로만 표시(ID/Class/속도/UTM).
  영상 위에 사각형을 그리려면 별도 투명 오버레이 위젯이 필요해서 다음 단계로 미룸.
- **영상 재접속**: `rtsp_viewer_test/rtsp_test_client.py`와 동일한 접근(OpenCV `CAP_FFMPEG`,
  8초간 프레임 없으면 재접속) — python-vlc 등 새 의존성 대신 이미 이 프로젝트에서 실측 검증된
  스택을 그대로 재사용함.
- **RC_Control_Right/RC_MotionMode** 등 UE측이 스텁이거나 의미가 불명확한 cmd는 이 GUI도
  그냥 값만 보낼 뿐 별도 처리 없음 — `ugv_rc_feature_gap_analysis.md` 참고.
