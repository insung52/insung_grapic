#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
rtsp_test_client.py — RTSP 스트림 수신 검증용 테스트 클라이언트.

titan(KADEX UGV/자체방호 시뮬레이터) 프로젝트, RTSP 뷰어 테스트 서브태스크
(C:\\working\\insung_grapic\\titan\\structure\\protocol_icd.md §3.3 참고).

지정한 RTSP URL(들)에 접속해서 일정 시간 동안 프레임을 수신하며
- 접속 성공 여부
- 측정 FPS / 최초 프레임 해상도
- 수신 지속 여부(프레임 간 최대 gap, 중간에 끊겼는지)
- (옵션) 첫/마지막 프레임 스냅샷 저장
을 확인한다. 여러 스트림을 동시에(스레드) 검사할 수 있다.

의존성: opencv-python(-headless) — RTSP(FFMPEG 백엔드)로 프레임을 받는다.
    pip install -r requirements.txt

사용 예:
  # streams_config.json에 정의된 5개 스트림을 10초씩 동시 테스트 + 스냅샷 저장
  python rtsp_test_client.py --config streams_config.json --duration 10 --snapshot

  # 로컬 대신 실제 UGV 서버로 base_url만 바꿔서 테스트 (파일 수정 없이)
  python rtsp_test_client.py --config streams_config.json --base rtsp://192.168.10.10:8554 --duration 10

  # 개별 URL 직접 지정
  python rtsp_test_client.py --urls rtsp://127.0.0.1:8554/front_cctv rtsp://127.0.0.1:8554/rear_cctv

  # 순차 테스트(동시 접속 부하를 피하고 싶을 때)
  python rtsp_test_client.py --config streams_config.json --sequential
"""

import argparse
import json
import os
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

try:
    import cv2
except ImportError:
    print("[FATAL] opencv-python(-headless)가 설치되어 있지 않습니다.")
    print("        pip install -r requirements.txt 로 설치하세요.")
    sys.exit(1)


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SNAPSHOT_DIR = os.path.join(SCRIPT_DIR, "snapshots")
DEFAULT_LOG_DIR = os.path.join(SCRIPT_DIR, "logs")

# 이 시간(초) 안에 첫 프레임이 안 오면 접속 실패로 간주
CONNECT_TIMEOUT_SEC = 8.0
# join() 대기 시 duration 초과 허용 여유(스레드가 block된 채 안 죽는 경우 대비)
JOIN_GRACE_SEC = 5.0


@dataclass
class StreamTarget:
    name: str
    url: str
    label: str = ""


@dataclass
class StreamResult:
    name: str
    url: str
    label: str = ""
    ok: bool = False
    error: str = ""
    frame_count: int = 0
    width: int = 0
    height: int = 0
    elapsed_sec: float = 0.0
    measured_fps: float = 0.0
    max_gap_sec: float = 0.0
    first_frame_at_sec: Optional[float] = None
    snapshot_first: str = ""
    snapshot_last: str = ""
    timed_out_open: bool = False
    reconnects: int = 0
    finished: bool = False


def test_one_stream(target: StreamTarget, duration: float, snapshot: bool,
                     snapshot_dir: str, result: StreamResult):
    """단일 스트림 접속 후 duration초 동안 프레임을 읽으며 통계를 낸다.
    스레드에서 호출되는 것을 전제로 result를 in-place로 채운다.

    cv2.VideoCapture는 RTSP DESCRIBE가 최초 open 시점에 실패(예: 서버가 막 뜨는 중이라
    아직 그 path가 mount되지 않은 경우, 404 등)하면 재시도를 안 하고 그대로 죽는다.
    그래서 "첫 프레임을 아직 못 받은 상태"이거나 "프레임을 받다가 CONNECT_TIMEOUT_SEC
    이상 끊긴 상태"면 캡처를 새로 열어서 재접속을 시도한다 — 실제 UGV 서버가 재시작되거나
    네트워크가 잠깐 끊기는 상황을 흉내내는 것과도 같아서, 테스트 도구 자체의 견고성으로도
    유용하다."""
    cap = None
    last_frame = None
    start = time.monotonic()
    last_frame_time = None
    frame_count = 0
    max_gap = 0.0
    first_frame_time = None
    reconnects = 0
    try:
        attempt_start = start
        while True:
            now = time.monotonic()
            elapsed = now - start
            if elapsed >= duration:
                break

            if cap is None:
                cap = cv2.VideoCapture(target.url, cv2.CAP_FFMPEG)
                try:
                    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                except Exception:
                    pass
                attempt_start = now
                reconnects += 1  # 첫 open도 1로 세고, 마지막에 -1 해서 보고

            # 이번 접속 시도(또는 마지막으로 프레임을 받은 시점) 이후 CONNECT_TIMEOUT_SEC 넘게
            # 프레임이 안 오면 접속을 버리고 새로 연다.
            since = last_frame_time if last_frame_time is not None else attempt_start
            if (now - since) > CONNECT_TIMEOUT_SEC:
                cap.release()
                cap = None
                continue

            ret, frame = cap.read()
            read_time = time.monotonic()
            if not ret or frame is None:
                continue

            frame_count += 1
            if first_frame_time is None:
                first_frame_time = read_time - start
                h, w = frame.shape[0], frame.shape[1]
                result.width, result.height = w, h
                if snapshot:
                    result.snapshot_first = save_snapshot(
                        snapshot_dir, target.name, "first", frame)

            if last_frame_time is not None:
                gap = read_time - last_frame_time
                if gap > max_gap:
                    max_gap = gap
            last_frame_time = read_time
            last_frame = frame

        total_elapsed = time.monotonic() - start
        result.frame_count = frame_count
        result.elapsed_sec = round(total_elapsed, 3)
        result.first_frame_at_sec = (
            round(first_frame_time, 3) if first_frame_time is not None else None
        )
        result.max_gap_sec = round(max_gap, 3)
        result.measured_fps = (
            round(frame_count / total_elapsed, 2) if total_elapsed > 0 else 0.0
        )
        result.reconnects = max(0, reconnects - 1)

        if frame_count == 0:
            result.ok = False
            result.timed_out_open = True
            extra = f" (재접속 {result.reconnects}회 시도)" if result.reconnects else ""
            result.error = f"{CONNECT_TIMEOUT_SEC:.0f}초 내 프레임 수신 실패 (접속/스트림 없음){extra}"
        else:
            result.ok = True
            if snapshot and last_frame is not None:
                result.snapshot_last = save_snapshot(
                    snapshot_dir, target.name, "last", last_frame)

    except Exception as e:  # noqa: BLE001 - 테스트 도구이므로 모든 예외를 결과로 흡수
        result.ok = False
        result.error = f"예외: {e!r}"
    finally:
        result.finished = True
        if cap is not None:
            cap.release()


def save_snapshot(snapshot_dir: str, stream_name: str, tag: str, frame) -> str:
    os.makedirs(snapshot_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{stream_name}_{tag}_{ts}.jpg"
    path = os.path.join(snapshot_dir, filename)
    try:
        cv2.imwrite(path, frame)
        return path
    except Exception:
        return ""


def load_targets_from_config(config_path: str, base_override: Optional[str]) -> List[StreamTarget]:
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    base_url = (base_override or cfg["base_url"]).rstrip("/")
    targets = []
    for s in cfg["streams"]:
        url = f"{base_url}/{s['path'].lstrip('/')}"
        targets.append(StreamTarget(name=s["name"], url=url, label=s.get("label", "")))
    return targets


def load_targets_from_urls(urls: List[str]) -> List[StreamTarget]:
    targets = []
    for i, u in enumerate(urls):
        # URL 마지막 path 조각을 이름으로 사용
        name = u.rstrip("/").split("/")[-1] or f"stream{i}"
        targets.append(StreamTarget(name=name, url=u, label=""))
    return targets


def print_report(results: List[StreamResult]):
    print()
    print("=" * 100)
    print(" RTSP 스트림 수신 테스트 결과")
    print("=" * 100)
    header = f"{'STREAM':<16}{'RESULT':<8}{'FPS':>7}{'해상도':>12}{'프레임수':>9}{'경과(s)':>9}{'최대gap(s)':>11}  URL / 비고"
    print(header)
    print("-" * 100)
    ok_count = 0
    for r in results:
        status = "OK" if r.ok else "FAIL"
        if r.ok:
            ok_count += 1
        res_str = f"{r.width}x{r.height}" if r.width else "-"
        reconnect_note = f"  (재접속 {r.reconnects}회)" if r.ok and r.reconnects else ""
        note = f"{r.url}{reconnect_note}" if r.ok else f"{r.url}  [{r.error}]"
        print(
            f"{r.name:<16}{status:<8}{r.measured_fps:>7.2f}{res_str:>12}"
            f"{r.frame_count:>9}{r.elapsed_sec:>9.2f}{r.max_gap_sec:>11.2f}  {note}"
        )
    print("-" * 100)
    print(f"총 {len(results)}개 중 {ok_count}개 성공, {len(results) - ok_count}개 실패")
    print("=" * 100)


def write_json_log(results: List[StreamResult], log_dir: str) -> str:
    os.makedirs(log_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(log_dir, f"rtsp_test_{ts}.json")
    payload = {
        "timestamp": datetime.now().isoformat(),
        "results": [
            {
                "name": r.name,
                "label": r.label,
                "url": r.url,
                "ok": r.ok,
                "error": r.error,
                "frame_count": r.frame_count,
                "width": r.width,
                "height": r.height,
                "elapsed_sec": r.elapsed_sec,
                "measured_fps": r.measured_fps,
                "max_gap_sec": r.max_gap_sec,
                "first_frame_at_sec": r.first_frame_at_sec,
                "reconnects": r.reconnects,
                "snapshot_first": r.snapshot_first,
                "snapshot_last": r.snapshot_last,
            }
            for r in results
        ],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return path


def main():
    parser = argparse.ArgumentParser(
        description="RTSP 스트림 수신 확인 테스트 클라이언트 (titan UGV/자체방호 RTSP 검증용)"
    )
    src_group = parser.add_mutually_exclusive_group(required=True)
    src_group.add_argument(
        "--config", help="스트림 목록 JSON 설정 파일 (예: streams_config.json)"
    )
    src_group.add_argument(
        "--urls", nargs="+", help="테스트할 RTSP URL 목록 (직접 지정)"
    )
    parser.add_argument(
        "--base", help="--config 사용 시 base_url을 덮어씀 (파일 수정 없이 실제 서버로 전환할 때 사용)"
    )
    parser.add_argument(
        "--duration", type=float, default=10.0, help="스트림당 수신 테스트 시간(초), 기본 10초"
    )
    parser.add_argument(
        "--snapshot", action="store_true", help="첫/마지막 프레임을 JPG로 저장"
    )
    parser.add_argument(
        "--snapshot-dir", default=DEFAULT_SNAPSHOT_DIR, help="스냅샷 저장 폴더"
    )
    parser.add_argument(
        "--log-dir", default=DEFAULT_LOG_DIR, help="JSON 결과 로그 저장 폴더"
    )
    parser.add_argument(
        "--sequential", action="store_true",
        help="스트림을 동시(병렬)가 아니라 하나씩 순차 테스트"
    )
    parser.add_argument(
        "--no-log", action="store_true", help="JSON 로그 파일을 남기지 않음"
    )
    args = parser.parse_args()

    if args.config:
        targets = load_targets_from_config(args.config, args.base)
    else:
        targets = load_targets_from_urls(args.urls)

    if not targets:
        print("[FATAL] 테스트할 스트림이 없습니다.")
        sys.exit(1)

    print(f"[INFO] {len(targets)}개 스트림 테스트 시작 "
          f"({'순차' if args.sequential else '동시'}, 스트림당 {args.duration:.0f}초)")
    for t in targets:
        print(f"       - {t.name} ({t.label}): {t.url}")

    results: List[StreamResult] = [StreamResult(name=t.name, url=t.url, label=t.label) for t in targets]

    if args.sequential:
        for t, r in zip(targets, results):
            print(f"[INFO] 테스트 중: {t.name} ...")
            test_one_stream(t, args.duration, args.snapshot, args.snapshot_dir, r)
    else:
        threads = []
        for t, r in zip(targets, results):
            th = threading.Thread(
                target=test_one_stream,
                args=(t, args.duration, args.snapshot, args.snapshot_dir, r),
                daemon=True,
            )
            threads.append(th)
            th.start()
        for th in threads:
            th.join(timeout=args.duration + CONNECT_TIMEOUT_SEC + JOIN_GRACE_SEC)
        for r in results:
            if not r.finished:
                r.ok = False
                r.error = "타임아웃 (스레드가 응답 없음 — 서버가 연결을 받고도 응답을 안 주는 상태일 수 있음)"

    print_report(results)

    if not args.no_log:
        log_path = write_json_log(results, args.log_dir)
        print(f"[INFO] 결과 로그 저장: {log_path}")

    ok_count = sum(1 for r in results if r.ok)
    sys.exit(0 if ok_count == len(results) else 2)


if __name__ == "__main__":
    main()
