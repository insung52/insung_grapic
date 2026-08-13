"""콘솔 로그 포맷: 타임스탬프 + 어떤 축에서/으로 갔는지 + cmd + payload."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

_RESET = "\033[0m"
_DIM = "\033[2m"
_CYAN = "\033[36m"
_YELLOW = "\033[33m"
_GREEN = "\033[32m"


def _now() -> str:
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


def _payload_str(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False)


def log_outgoing(axis: str, envelope: dict[str, Any]) -> None:
    print(
        f"{_DIM}[{_now()}]{_RESET} {_YELLOW}HQ → {axis:<11}{_RESET} "
        f"{envelope['cmd']} (seq={envelope['seq']}) {_payload_str(envelope['payload'])}"
    )


def log_incoming(axis: str, envelope: dict[str, Any]) -> None:
    print(
        f"{_DIM}[{_now()}]{_RESET} {_GREEN}{axis:<11} → HQ{_RESET} "
        f"{envelope.get('cmd')} (seq={envelope.get('seq')}) "
        f"{_payload_str(envelope.get('payload'))}"
    )


def log_info(message: str) -> None:
    print(f"{_DIM}[{_now()}]{_RESET} {_CYAN}{message}{_RESET}")
