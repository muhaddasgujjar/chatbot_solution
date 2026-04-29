"""
In-process metrics for dashboards and operational visibility.
Thread-safe; bounded sample buffers to cap memory. Resets on process restart.
"""

from __future__ import annotations

import time
from collections import deque
from threading import Lock
from typing import Any, Deque, Dict, List

_MAX_SAMPLES = 1000
_ROLE_KEYS = ("faculty", "student", "alumni", "all")

_lock = Lock()
_http_total = 0
_http_4xx = 0
_http_5xx = 0
_http_latency_ms: Deque[int] = deque(maxlen=_MAX_SAMPLES)

_chats: Dict[str, int] = {k: 0 for k in _ROLE_KEYS}
_handoffs: Dict[str, int] = {k: 0 for k in _ROLE_KEYS}
_chat_latency_ms: Dict[str, Deque[int]] = {k: deque(maxlen=_MAX_SAMPLES) for k in _ROLE_KEYS}


def normalize_metric_role(role: str | None) -> str:
    r = (role or "all").strip().lower()
    return r if r in _ROLE_KEYS else "all"


def record_http_request(status_code: int, latency_ms: int) -> None:
    global _http_total, _http_4xx, _http_5xx
    lat = max(0, int(latency_ms))
    with _lock:
        _http_total += 1
        if 400 <= status_code < 500:
            _http_4xx += 1
        elif status_code >= 500:
            _http_5xx += 1
        _http_latency_ms.append(lat)


def record_chat_turn(role: str, latency_ms: int, requires_handoff: bool) -> None:
    bucket = normalize_metric_role(role)
    lat = max(0, int(latency_ms))
    with _lock:
        _chats[bucket] += 1
        if requires_handoff:
            _handoffs[bucket] += 1
        _chat_latency_ms[bucket].append(lat)


def _percentiles(samples: List[int]) -> tuple[int, int]:
    if not samples:
        return 0, 0
    s = sorted(samples)
    n = len(s)

    def pct(p: float) -> int:
        if n == 1:
            return int(s[0])
        idx = min(int(round((p / 100.0) * (n - 1))), n - 1)
        return int(s[idx])

    return pct(50), pct(95)


def snapshot() -> Dict[str, Any]:
    with _lock:
        http_samples = list(_http_latency_ms)
        chats = dict(_chats)
        handoffs = dict(_handoffs)
        http_total = _http_total
        http_4xx = _http_4xx
        http_5xx = _http_5xx
        chat_lat = {k: list(v) for k, v in _chat_latency_ms.items()}

    hp50, hp95 = _percentiles(http_samples)
    by_role: Dict[str, Any] = {}
    for key in _ROLE_KEYS:
        c = chats[key]
        h = handoffs[key]
        p50, p95 = _percentiles(chat_lat[key])
        by_role[key] = {
            "chat_requests": c,
            "handoff_count": h,
            "handoff_rate": round(h / c, 4) if c else 0.0,
            "latency_p50_ms": p50,
            "latency_p95_ms": p95,
        }

    err_den = max(http_total, 1)
    return {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "uptime_note": "Counters reset on process restart; chat latencies are full SSE stream duration.",
        "global": {
            "http_requests": http_total,
            "http_4xx": http_4xx,
            "http_5xx": http_5xx,
            "http_error_rate": round((http_4xx + http_5xx) / err_den, 4),
            "latency_p50_ms": hp50,
            "latency_p95_ms": hp95,
        },
        "by_role": by_role,
    }
