"""
HTTP middleware for the YouFace API.

Provides:
- Simple in-memory rate limiting (per-IP, sliding window) — no external dep
- Security headers (CSP, X-Frame-Options, etc.) — no external dep
- Request size cap (defense against accidental huge uploads)
- Multi-tenant identification + per-tenant quota headers (X-RateLimit-*)

Why custom (not slowapi/starlette-csp):
- The youface API is local-first; we don't need Redis-backed
  distributed rate limiting
- Adding deps for this is overkill; the protection just needs to
  stop a runaway script, not a real attacker
"""
import time
import collections
from typing import Dict, Tuple, Optional
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

    def __init__(self, app: ASGIApp, requests_per_window: int = 600, window_seconds: int = 60):
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

        # Localhost (cockpit UI) is exempt — this is a single-user local-first
        # tool; rate-limiting ourselves makes the UI flicker between 429s and
        # data. Real abuse (external network) still hits the 600 req/min cap.
        if client_ip in ("127.0.0.1", "::1", "localhost"):
            return await call_next(request)
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
        # CSP: precisa servir o cockpit estático do Next.js (que tem seus
        # próprios chunks CSS/JS em /_next/static) E a API. 'self' cobre
        # ambos. 'unsafe-inline' para style é necessário por causa do
        # Next.js (style tags inline no HTML). 'unsafe-inline' para
        # scripts é o trade-off padrão para SPA — o app é local-only.
        response.headers["Content-Security-Policy"] = (
            f"default-src 'self'; "
            f"connect-src {self.csp_connect_src}; "
            f"img-src 'self' data: blob:; "
            f"style-src 'self' 'unsafe-inline'; "
            f"style-src-elem 'self' 'unsafe-inline'; "
            f"script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            f"script-src-elem 'self' 'unsafe-inline' 'unsafe-eval'; "
            f"font-src 'self' data:; "
            f"frame-ancestors 'none'; "
            f"media-src 'self' blob:; "
            f"worker-src 'self' blob:; "
            f"connect-src 'self' {self.csp_connect_src}"
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


# ---------------------------------------------------------------------------
# Multi-tenant identification + quota headers
# ---------------------------------------------------------------------------

class TenantMiddleware(BaseHTTPMiddleware):
    """
    Identifies the calling tenant (if any) via X-API-Key or Bearer header,
    attaches the resolved tenant to `request.state.tenant`, and decorates
    responses with X-RateLimit-* headers reflecting the current month usage.

    This middleware does NOT enforce the quota by itself — that would block
    small admin queries once a tenant is exhausted. Instead, the
    `/api/admin/usage` and `/api/admin/tenants` endpoints (and the
    job-create endpoint for write paths) check quota before charging work.

    Identification order:
        1. X-API-Key header (preferred for tenant auth)
        2. Authorization: Bearer <key>
    If neither is present, request.state.tenant is None (anonymous /
    local-mode user).
    """

    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        raw_key = self._extract_key(request)
        tenant = None
        if raw_key:
            try:
                # Lazy import to avoid pulling the tenants module at startup
                # before ensure_tenant_tables() runs.
                from youface.api.tenants import get_tenant_by_key
                tenant = get_tenant_by_key(raw_key)
            except Exception:
                tenant = None
        request.state.tenant = tenant

        response = await call_next(request)

        # Always advertise the resolved tenant id (or "anonymous").
        if tenant is not None:
            response.headers["X-Tenant-Id"] = tenant.id
            response.headers["X-Tenant-Name"] = tenant.name

            # Always decorate with quota headers so clients can introspect
            # their state on every response. Quota == -1 (UNLIMITED) is
            # surfaced as "unlimited" instead of a numeric.
            try:
                from youface.api.tenants import (
                    get_usage_minutes,
                    remaining_quota_minutes,
                    _current_period,
                    UNLIMITED_QUOTA,
                )
                used = get_usage_minutes(tenant.id)
                remaining = remaining_quota_minutes(tenant)
                response.headers["X-RateLimit-Limit"] = (
                    "unlimited" if tenant.monthly_quota_minutes == UNLIMITED_QUOTA
                    else str(tenant.monthly_quota_minutes)
                )
                response.headers["X-RateLimit-Used"] = f"{used:.2f}"
                response.headers["X-RateLimit-Remaining"] = (
                    "unlimited" if remaining is None else f"{remaining:.2f}"
                )
                response.headers["X-RateLimit-Period"] = _current_period()
            except Exception:
                pass

        return response

    @staticmethod
    def _extract_key(request: Request) -> Optional[str]:
        x_api_key = request.headers.get("x-api-key")
        if x_api_key:
            return x_api_key.strip()
        auth = request.headers.get("authorization")
        if auth and auth.lower().startswith("bearer "):
            presented = auth[7:].strip()
            # Only treat as tenant key if it looks like one (not the legacy
            # YOUFACE_API_TOKEN). Heuristic: tenant keys start with
            # 'fftk_' (set on rotation) OR are token_urlsafe(32) (no prefix).
            # The legacy admin token typically is user-chosen; we therefore
            # DON'T sniff the prefix — the tenants table is keyed by hash,
            # so a stale YOUFACE_API_TOKEN simply won't match any row.
            return presented or None
        return None
