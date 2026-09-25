from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.headers.setdefault("Content-Security-Policy", "default-src 'self'; connect-src 'self' http://127.0.0.1:8000 http://localhost:8000; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'")
        return response


class LoginRateLimitMiddleware(BaseHTTPMiddleware):
    """Small in-process limiter for the local Windows profile.

    A shared Redis-backed limiter should replace this before multi-instance deployment.
    """

    def __init__(self, app, limit: int = 60, window_seconds: int = 60) -> None:
        super().__init__(app)
        self.limit = limit
        self.window_seconds = window_seconds
        self._requests: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path.endswith("/auth/login") and request.method == "POST":
            client = request.client.host if request.client else "unknown"
            now = time.monotonic()
            with self._lock:
                bucket = self._requests[client]
                while bucket and now - bucket[0] > self.window_seconds:
                    bucket.popleft()
                if len(bucket) >= self.limit:
                    return JSONResponse(status_code=429, content={"detail": "Too many login attempts; try again later"})
                bucket.append(now)
        return await call_next(request)
