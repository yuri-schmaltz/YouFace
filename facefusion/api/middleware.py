"""
HTTP middleware for the FaceFusion API.

Provides:
- Simple in-memory rate limiting (per-IP, sliding window) — no external dep
- Security headers (CSP, X-Frame-Options, etc.) — no external dep
- Request size cap (defense against accidental huge uploads)

Why custom (not slowapi/starlette-csp):
- The facefusion API is local-first; we don't need Redis-backed
  distributed rate limiting
- Adding deps for this is overkill; the protection just needs to
  stop a runaway script, not a real attacker
"""
import time
import collections
from typing import Dict, Tuple
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------

class RateLimiter(BaseHTTPMiddleware):
    """
    In-memory per-IP rate limiter.

    Default: 60 requests / 60s per IP. Exceeding returns 429.
    State is per-process; if you scale to multiple workers, this becomes
    per-worker (acceptable for single-user local use).
    """

    def __init__(self, app: ASGIApp, requests_per_window: int = 60, window_seconds: int = 60):
        super().__init__(app)
        self.requests_per_window = requests_per_window
        self.window_seconds = window_seconds
        # IP -> deque of timestamps
        self._hits: Dict[str, collections.deque] = {}

    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for SSE stream endpoints (they're long-lived)
        if request.url.path.endswith("/jobs/stream"):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        window_start = now - self.window_seconds

        if client_ip not in self._hits:
            self._hits[client_ip] = collections.deque()

        # Prune old entries
        dq = self._hits[client_ip]
        while dq and dq[0] < window_start:
            dq.popleft()

        if len(dq) >= self.requests_per_window:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": f"Rate limit exceeded ({self.requests_per_window} req/{self.window_seconds}s). Try again later.",
                },
                headers={"Retry-After": str(self.window_seconds)},
            )

        dq.append(now)
        response = await call_next(request)
        return response


# ---------------------------------------------------------------------------
# Security headers
# ---------------------------------------------------------------------------

class SecurityHeaders(BaseHTTPMiddleware):
    """
    Adds security-related HTTP headers to every response.

    Note: CSP is set to permissive defaults because the cockpit is a
    local-only app (binds 127.0.0.1). For LAN exposure, tighten the
    CSP `connect-src` to your specific domain.
    """

    def __init__(self, app: ASGIApp, csp_connect_src: str = "'self' http://127.0.0.1:* http://localhost:*"):
        super().__init__(app)
        self.csp_connect_src = csp_connect_src

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        # CSP for the API itself (not the SPA — Next.js sets its own when served)
        response.headers["Content-Security-Policy"] = (
            f"default-src 'none'; "
            f"connect-src {self.csp_connect_src}; "
            f"img-src 'self' data:; "
            f"style-src 'unsafe-inline'; "
            f"frame-ancestors 'none'"
        )
        return response


# ---------------------------------------------------------------------------
# Request body size cap
# ---------------------------------------------------------------------------

class MaxBodySize(BaseHTTPMiddleware):
    """
    Rejects requests whose Content-Length exceeds `max_bytes`.
    Defense against accidental huge uploads to /api/media/upload.
    """

    def __init__(self, app: ASGIApp, max_bytes: int = 200 * 1024 * 1024):  # 200 MB
        super().__init__(app)
        self.max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next):
        cl = request.headers.get("content-length")
        if cl and cl.isdigit() and int(cl) > self.max_bytes:
            return JSONResponse(
                status_code=413,
                content={"detail": f"Request too large ({int(cl)} bytes > {self.max_bytes} max)."},
            )
        return await call_next(request)
