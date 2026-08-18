"""
LIG 원격통제기(RC) 역할 목업 — Network/UGVRemoteControlSubsystem.*(UE, titan_example) 검증용.

**이 폴더의 기존 protocol.py/client.py/mock_server.py와는 독립적인 새 파일이다.** 그 셋은
정식 ICD 확보 전(2026-08-07) 우리 추정 cmd 이름/봉투 상관관계 규칙으로 짠 것이라 지금은
obsolete(원격통제기가 이미 "UGV"였고 이 스크립트는 반대로 "RC" 역할 필요 — 방향도 다름).
이 스크립트는 `lig_icd_ugv_rc_full.md`(UGV_RC_ICD.xlsx 복호화본, 1차 소스)의 cmd 이름/필드를
오타(ConrtrolRight, Batterry, BRUST, CONTINUS 등)까지 그대로 사용한다.

## UE측 확정 사항과의 관계
- `RC_EmergencyStop`/`RC_FireWeapon` 등 대부분의 이벤트 커맨드에 ICD가 정의한 UGV측 ACK cmd가
  없다는 게 확인된 상태라(`udp_test_findings.md`도 독립적으로 같은 결론), 이 스크립트도 범용
  재시도/ACK 큐를 만들지 않는다 — 보내고 UGV_Period_* 주기 보고에 반영됐는지 눈으로/로그로
  확인하는 방식.
- 포트 라우팅(주기=8000/8010 vs 이벤트=8001/8011)은 ICD 시트3의 "주기" 컬럼 값을 그대로 따름:
  Hz가 명시된 cmd(RC_Request_BIT/RC_Request_BIT_ADU=1Hz, RC_RemoteDriving=20Hz)만 주기 포트로,
  나머지 "비주기"는 전부 이벤트 포트로 보낸다. **이게 맞는 해석인지는 확정 아님** — ICD가 두
  포트를 "메시지 분류" 기준으로 나눈 건지 "송신 빈도" 기준으로 나눈 건지 원문이 완전히
  명확하진 않다. 현재 UE측 UGVRemoteControlSubsystem은 두 포트 아무 데로 와도 cmd 이름만 보고
  처리하므로(포트로 분기 안 함) 이 스크립트가 분류를 잘못 짰어도 지금 당장은 테스트가 그냥
  통과해버린다 — 실제 LIG 하드웨어와 붙일 때 이 가정이 맞는지 재확인 필요.

## 사용법
    python rc_mock_client.py --ugv-ip 100.x.x.x

    (같은 PC에서 UE가 도는 UGV측을 테스트할 때는 --ugv-ip 127.0.0.1,
     Tailscale로 다른 PC를 테스트할 때는 그 PC의 Tailscale IP)

기본으로 연결 핸드셰이크 -> 제어권 획득 -> 전진 주행 -> 정지 -> 사격모드/장전/발사 -> 카메라
전환 순으로 자동 시나리오를 실행하면서, 들어오는 UGV_Period_*/UGV_Response_* 전부를 로그로
찍는다. Ctrl+C로 언제든 중단 가능(그 시점까지 받은 cmd 통계를 요약 출력).

RTSP 스트림 확인(옵션, ffprobe 필요 — RTSP 서버 자체가 이 프로젝트에서 아직 별도 트랙으로
진행 중이라 URL이 확정 안 됐음, 확정되면 --check-rtsp로 바로 쓸 수 있게 미리 만들어둠):
    python rc_mock_client.py --ugv-ip 100.x.x.x --check-rtsp rtsp://100.x.x.x:8554/front

의존성: 표준 라이브러리만 사용(RTSP 체크는 예외 — 시스템에 설치된 ffprobe 실행파일을 서브
프로세스로 호출, pip 설치 불필요하지만 ffmpeg가 PATH에 있어야 함).
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import socket
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Optional

logger = logging.getLogger("rc_mock")


# ---------------------------------------------------------------------------
# 프로토콜 상수 — lig_icd_ugv_rc_full.md 원문 그대로
# ---------------------------------------------------------------------------

class DeviceCode(IntEnum):
    UGV_ADU = 12
    UGV_RCWS = 13
    UGV = 14
    RC = 20


# ICD 시트3 "주기" 컬럼 값 그대로 — Hz 명시 cmd만 주기 포트, 나머지는 이벤트 포트(위 docstring
# "포트 라우팅" 참고). 값은 cmd별 (device_group, "periodic"|"event") 튜플.
RC_TO_UGV_ROUTING: dict[str, str] = {
    "RC_Connection": "event",              # 비주기(1Hz 재연결)
    "RC_Request_BIT": "periodic",          # 1Hz
    "RC_Control_Right": "event",           # 비주기
    "RC_RemoteDriving": "periodic",        # 20Hz
    "RC_EmergencyStop": "event",           # 비주기
    "RC_EmergencyStopRelease": "event",    # 비주기
    "RC_OperationMode": "event",           # 비주기
    "RC_SelectCamera": "event",            # 비주기
    "RC_FireMode": "event",                # 비주기
    "RC_ChargeWeapon": "event",            # 비주기
    "RC_FireWeapon": "event",              # 비주기
    "RC_MotionMode": "event",              # 비주기
    "RC_Movement": "event",                # 비주기
    "RC_ActivateFire": "event",            # 비주기
    "RC_ActivateMovement": "event",        # 비주기
    "RC_Connection_ADU": "event",          # 비주기
    "RC_Request_BIT_ADU": "periodic",      # 1Hz
    "HQ_MissionMoveToEngage": "event",     # 우리 확장(2026-08-16) — UGV_RC_ICD엔 없음, 일회성 미션 커맨드라 이벤트 포트로 취급
}


@dataclass
class Envelope:
    """공통 봉투 — protocol_icd.md §1(a): { cmd, src, recv, data }."""

    cmd: str
    src: int
    recv: int
    data: dict[str, Any] = field(default_factory=dict)

    def to_json_bytes(self) -> bytes:
        return json.dumps(
            {"cmd": self.cmd, "src": int(self.src), "recv": int(self.recv), "data": self.data},
            ensure_ascii=False,
        ).encode("utf-8")

    @staticmethod
    def from_json_bytes(raw: bytes) -> "Envelope":
        obj = json.loads(raw.decode("utf-8", errors="replace"))
        return Envelope(
            cmd=obj["cmd"],
            src=int(obj.get("src", 0)),
            recv=int(obj.get("recv", 0)),
            data=obj.get("data", {}) or {},
        )


# ---------------------------------------------------------------------------
# RC 클라이언트
# ---------------------------------------------------------------------------

class RCMockClient:
    def __init__(
        self,
        ugv_ip: str,
        ugv_periodic_port: int,
        ugv_event_port: int,
        bind_ip: str,
        rc_periodic_port: int,
        rc_event_port: int,
    ):
        self.ugv_ip = ugv_ip
        self.ugv_periodic_port = ugv_periodic_port
        self.ugv_event_port = ugv_event_port

        self._sock_periodic = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock_periodic.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock_periodic.bind((bind_ip, rc_periodic_port))
        self._sock_periodic.settimeout(0.2)

        self._sock_event = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock_event.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock_event.bind((bind_ip, rc_event_port))
        self._sock_event.settimeout(0.2)

        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []

        self.stats_lock = threading.Lock()
        self.received_counts: dict[str, int] = {}
        self.last_basicinfo: Optional[dict] = None
        self.last_navigation: Optional[dict] = None
        self.last_rcws_status: Optional[dict] = None
        self.last_detection: Optional[dict] = None

    # ------------------------------------------------------------------
    def start(self) -> "RCMockClient":
        t1 = threading.Thread(target=self._recv_loop, args=(self._sock_periodic, "periodic"), daemon=True, name="rc-mock-periodic")
        t2 = threading.Thread(target=self._recv_loop, args=(self._sock_event, "event"), daemon=True, name="rc-mock-event")
        self._threads = [t1, t2]
        t1.start()
        t2.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        for t in self._threads:
            t.join(timeout=2)
        self._sock_periodic.close()
        self._sock_event.close()

    # --- 송신 -----------------------------------------------------------
    def send(self, cmd: str, recv_device: DeviceCode, data: dict) -> None:
        route = RC_TO_UGV_ROUTING.get(cmd, "event")
        sock = self._sock_periodic if route == "periodic" else self._sock_event
        port = self.ugv_periodic_port if route == "periodic" else self.ugv_event_port

        env = Envelope(cmd=cmd, src=int(DeviceCode.RC), recv=int(recv_device), data=data)
        raw = env.to_json_bytes()
        sock.sendto(raw, (self.ugv_ip, port))
        logger.info("[SEND %-8s -> %s:%d] %s", route, self.ugv_ip, port, raw.decode("utf-8"))

    # --- 수신 -----------------------------------------------------------
    def _recv_loop(self, sock: socket.socket, label: str) -> None:
        while not self._stop.is_set():
            try:
                raw, addr = sock.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError:
                break
            try:
                env = Envelope.from_json_bytes(raw)
            except (ValueError, KeyError) as exc:
                logger.warning("[RECV %s] JSON 파싱 실패 from %s: %s (raw=%r)", label, addr, exc, raw[:200])
                continue

            with self.stats_lock:
                self.received_counts[env.cmd] = self.received_counts.get(env.cmd, 0) + 1
                if env.cmd == "UGV_Period_Basicinfo":
                    self.last_basicinfo = env.data
                elif env.cmd == "UGV_Period_NavigationInformation":
                    self.last_navigation = env.data
                elif env.cmd == "UGV_RCWS_Status":
                    self.last_rcws_status = env.data
                elif env.cmd == "UGV_Period_ObjectDetectionResult":
                    self.last_detection = env.data

            logger.info("[RECV %-8s <- %s] cmd=%s data=%s", label, addr, env.cmd, json.dumps(env.data, ensure_ascii=False))

    def print_summary(self) -> None:
        with self.stats_lock:
            counts = dict(self.received_counts)
        print("\n=== 수신 cmd 통계 ===")
        if not counts:
            print("  (아무것도 못 받음 — IP/포트/UE측 소켓 시작 여부 확인)")
        for cmd, n in sorted(counts.items()):
            print(f"  {cmd}: {n}회")
        print("=====================\n")


# ---------------------------------------------------------------------------
# 자동 시나리오 — 연결 -> 제어권 -> 주행 -> 정지 -> 사격 -> 카메라
# ---------------------------------------------------------------------------

def run_scenario(client: RCMockClient) -> None:
    print("\n--- 1) 연결 핸드셰이크 (RC_Connection, 3회 재시도) ---")
    for _ in range(3):
        client.send("RC_Connection", DeviceCode.UGV, {"RequestDevice": 1})
        time.sleep(1.0)
        if client.received_counts.get("UGV_Response_Connection"):
            print("연결 응답 확인됨")
            break
    else:
        print("경고: UGV_Response_Connection을 못 받음 — 이후 단계는 계속 진행하되 IP/포트 확인 필요")

    print("\n--- 2) BIT 요청 (RC_Request_BIT) ---")
    client.send("RC_Request_BIT", DeviceCode.UGV, {"RequestBit": 1})
    time.sleep(0.5)

    print("\n--- 3) 제어권 획득 (RC_Control_Right) + 원격주행 모드 (RC_OperationMode=REMOTE) ---")
    client.send("RC_Control_Right", DeviceCode.UGV, {"ControlRight": 1})
    time.sleep(0.2)
    client.send("RC_OperationMode", DeviceCode.UGV, {"OperationMode": "REMOTE"})
    time.sleep(0.5)

    print("\n--- 4) 전진 주행 (RC_RemoteDriving, 20Hz로 3초) ---")
    end_time = time.time() + 3.0
    while time.time() < end_time:
        client.send("RC_RemoteDriving", DeviceCode.UGV, {
            "Acceleration": 30, "Brake": 0, "Steering": 0, "Gear": "FRONT",
        })
        time.sleep(0.05)
    if client.last_basicinfo:
        print(f"마지막 UGV_Period_Basicinfo: {client.last_basicinfo}")

    print("\n--- 5) 정지 (Acceleration=0, Brake=100) 후 대기 모드 ---")
    client.send("RC_RemoteDriving", DeviceCode.UGV, {"Acceleration": 0, "Brake": -100, "Steering": 0, "Gear": "FRONT"})
    time.sleep(0.5)
    client.send("RC_OperationMode", DeviceCode.UGV, {"OperationMode": "STAY"})
    time.sleep(0.5)

    print("\n--- 6) 사격 계열 (FireMode/ChargeWeapon/FireWeapon 눌렀다 뗌) ---")
    client.send("RC_FireMode", DeviceCode.UGV_RCWS, {"FireMode": "BRUST"})
    time.sleep(0.2)
    client.send("RC_ChargeWeapon", DeviceCode.UGV_RCWS, {"ChargeSwitch": "ON"})
    time.sleep(0.2)
    client.send("RC_FireWeapon", DeviceCode.UGV_RCWS, {"FireButton": "PRESSED"})
    time.sleep(0.3)
    client.send("RC_FireWeapon", DeviceCode.UGV_RCWS, {"FireButton": "RELEASE"})
    time.sleep(0.2)

    print("\n--- 7) 카메라 전환 (EO -> IR -> EO) ---")
    client.send("RC_SelectCamera", DeviceCode.UGV_RCWS, {"SelectCameraButton": "PRESSED"})  # IR
    time.sleep(0.5)
    client.send("RC_SelectCamera", DeviceCode.UGV_RCWS, {"SelectCameraButton": "RELEASE"})  # EO
    time.sleep(0.5)

    print("\n--- 8) 3초 더 대기하며 주기 보고 수신 확인 (Basicinfo/RCWS_Status/Nav/Detection) ---")
    time.sleep(3.0)


def send_mission(client: RCMockClient, east: int, north: int, zone: int, letter: str, radius: float, wait_sec: float = 30.0) -> None:
    """HQ_MissionMoveToEngage(우리 확장, LIG 미확인) 하나 보내고 RPT_ObjectiveReached 올 때까지
    대기 — --send-mission 전용 경량 테스트 경로(전체 시나리오 없이 이것만 확인하고 싶을 때)."""
    print(f"\n--- HQ_MissionMoveToEngage 전송 (East={east} North={north} Zone={zone} Letter={letter} Radius={radius}m) ---")
    client.send("HQ_MissionMoveToEngage", DeviceCode.UGV, {
        "East": east, "North": north, "Zone": zone, "Letter": letter, "Radius": radius,
    })

    print(f"RPT_ObjectiveReached 대기 중 (최대 {wait_sec}초)...")
    deadline = time.time() + wait_sec
    baseline = client.received_counts.get("RPT_ObjectiveReached", 0)
    while time.time() < deadline:
        if client.received_counts.get("RPT_ObjectiveReached", 0) > baseline:
            print("도착 보고(RPT_ObjectiveReached) 수신 확인됨")
            return
        time.sleep(0.2)
    print("경고: 시간 내에 RPT_ObjectiveReached를 못 받음 — UGV가 실제로 도착 못 했거나(경로/장애물),")
    print("       AUGVAIController::bEngineOn이 꺼져있어서 애초에 안 움직였을 수 있음")


# ---------------------------------------------------------------------------
# RTSP 스트림 확인 (옵션 — ffprobe 서브프로세스, RTSP 서버 자체는 아직 다른 트랙에서 진행 중)
# ---------------------------------------------------------------------------

def check_rtsp(url: str, timeout_sec: float = 5.0) -> None:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        print(f"[RTSP] ffprobe를 PATH에서 못 찾음 — ffmpeg 설치 필요(pip 아님, https://ffmpeg.org). 건너뜀: {url}")
        return

    print(f"[RTSP] {url} 확인 중 (최대 {timeout_sec}초)...")
    try:
        result = subprocess.run(
            [ffprobe, "-v", "error", "-rtsp_transport", "tcp",
             "-show_entries", "stream=codec_name,width,height,avg_frame_rate",
             "-of", "json", url],
            capture_output=True, text=True, timeout=timeout_sec,
        )
    except subprocess.TimeoutExpired:
        print(f"[RTSP] 실패 — {timeout_sec}초 내 응답 없음: {url}")
        return

    if result.returncode != 0:
        print(f"[RTSP] 실패 — ffprobe 에러: {result.stderr.strip()[:500]}")
        return

    try:
        info = json.loads(result.stdout)
        streams = info.get("streams", [])
    except json.JSONDecodeError:
        streams = []

    if not streams:
        print(f"[RTSP] 실패 — 스트림 정보 없음: {url}")
        return

    print(f"[RTSP] 성공 — {url}")
    for s in streams:
        print(f"       codec={s.get('codec_name')} {s.get('width')}x{s.get('height')} fps={s.get('avg_frame_rate')}")


# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ugv-ip", default="192.168.10.10", help="UGV 시뮬레이션 SW(UE) IP — Tailscale IP 등으로 오버라이드")
    parser.add_argument("--ugv-periodic-port", type=int, default=8000)
    parser.add_argument("--ugv-event-port", type=int, default=8001)
    parser.add_argument("--bind-ip", default="0.0.0.0", help="RC 자신의 수신 바인드 IP")
    parser.add_argument("--rc-periodic-port", type=int, default=8010)
    parser.add_argument("--rc-event-port", type=int, default=8011)
    parser.add_argument("--no-scenario", action="store_true", help="자동 시나리오 생략 — 수신만 계속 로그(Ctrl+C로 종료)")
    parser.add_argument("--check-rtsp", metavar="URL", help="RTSP 스트림 확인(옵션, ffprobe 필요) — 예: rtsp://<ip>:8554/front")
    parser.add_argument("--send-mission", metavar="EAST,NORTH,ZONE,LETTER,RADIUS",
                         help="HQ_MissionMoveToEngage(우리 확장, LIG 미확인) 하나 보내고 RPT_ObjectiveReached "
                              "대기 후 종료 — 예: --send-mission 428165,4196584,52,S,5")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", stream=sys.stdout)

    client = RCMockClient(
        ugv_ip=args.ugv_ip,
        ugv_periodic_port=args.ugv_periodic_port,
        ugv_event_port=args.ugv_event_port,
        bind_ip=args.bind_ip,
        rc_periodic_port=args.rc_periodic_port,
        rc_event_port=args.rc_event_port,
    ).start()

    print(f"RC 목업 시작 — UGV {args.ugv_ip}:{args.ugv_periodic_port}(주기)/{args.ugv_event_port}(이벤트)로 송신, "
          f"{args.bind_ip}:{args.rc_periodic_port}(주기)/{args.rc_event_port}(이벤트)에서 수신 대기")

    try:
        if args.check_rtsp:
            check_rtsp(args.check_rtsp)

        if args.send_mission:
            east_s, north_s, zone_s, letter, radius_s = args.send_mission.split(",")
            send_mission(client, int(east_s), int(north_s), int(zone_s), letter, float(radius_s))
        elif args.no_scenario:
            print("수신 전용 모드 — Ctrl+C로 종료")
            while True:
                time.sleep(1)
        else:
            run_scenario(client)
    except KeyboardInterrupt:
        pass
    finally:
        client.print_summary()
        client.stop()


if __name__ == "__main__":
    main()
