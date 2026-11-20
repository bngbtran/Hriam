"""Giới hạn tần suất trong bộ nhớ (một tiến trình). Khi chạy nhiều tiến trình, thay bằng Redis (docs/02 §3.1)."""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from .errors import AppError

LIMITS = {  # tên: (số lần, trong bao nhiêu giây)
    "auth": (10, 60),
    "auth_phone": (10, 60),
    "auth_phone_verify": (20, 60),
    "translate": (60, 60),
    "translate_gemini": (12, 60),  # mỗi lượt Gemini tốn credit: chặt hơn dịch bằng mô hình cục bộ
    "contribution": (20, 3600),
    "forum": (20, 3600),
    "report": (30, 3600),
    "feedback": (30, 3600),
    "room_create": (30, 3600),
    "culture_submit": (30, 3600),
}


_hits: dict[str, deque] = defaultdict(deque)
_lock = threading.Lock()
enabled = True


def check(bucket: str, key: str) -> None:
    if not enabled:
        return
    limit, window = LIMITS[bucket]
    now = time.monotonic()
    with _lock:
        q = _hits[f"{bucket}:{key}"]
        while q and now - q[0] > window:
            q.popleft()
        if len(q) >= limit:
            raise AppError(429, "RATE_LIMITED", "Bạn thao tác quá nhanh. Vui lòng thử lại sau ít phút.")
        q.append(now)


def reset() -> None:
    with _lock:
        _hits.clear()
