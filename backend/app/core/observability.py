import json
import logging
import time
import uuid
from collections import defaultdict, deque
from threading import Lock
from typing import Deque, Dict

from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.config import settings

logger = logging.getLogger("ou_chatbot_api")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)

_RATE_LIMIT_STATE: Dict[str, Deque[float]] = defaultdict(deque)
_RATE_LIMIT_LOCK = Lock()


def get_request_id(request: Request) -> str:
    return request.headers.get("x-request-id") or str(uuid.uuid4())


def check_rate_limit(client_key: str) -> bool:
    now = time.time()
    window_start = now - 60
    with _RATE_LIMIT_LOCK:
        events = _RATE_LIMIT_STATE[client_key]
        while events and events[0] < window_start:
            events.popleft()
        if len(events) >= settings.rate_limit_per_minute:
            return False
        events.append(now)
        return True


def rate_limit_response(request_id: str) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={
            "detail": "Rate limit exceeded. Please retry after a minute.",
            "request_id": request_id,
        },
        headers={"x-request-id": request_id},
    )


def log_request(request: Request, status_code: int, latency_ms: int, request_id: str) -> None:
    record = {
        "event": "request_completed",
        "method": request.method,
        "path": request.url.path,
        "status_code": status_code,
        "latency_ms": latency_ms,
        "client_ip": request.client.host if request.client else "unknown",
        "request_id": request_id,
    }
    logger.info(json.dumps(record))
