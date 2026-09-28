"""
Bearer token authentication for the FaceFusion API.

Design: simple shared-secret token. Set via env var FACEFUSION_API_TOKEN.
If unset, authentication is disabled (local-only mode preserved).

NOT a full JWT/OAuth implementation. This is a pragmatic stop-gap for
LAN deployments where you want a single shared password. For multi-user
or production deployments, replace with a real auth provider (the
middleware is a single dependency injection point).

Usage from the client:
  fetch("/api/jobs", { headers: { "Authorization": "Bearer <token>" } })

Usage from the server:
  app.add_middleware(BearerAuthMiddleware, token="...")

Whitelist:
  - /api/hardware/* : always public (the frontend needs to poll these
    for the status bar; the data is non-sensitive)
  - /api/processors/list : always public (just a list of strings)
  - /api/config GET : public (so the frontend can load defaults)
  - /api/media/output/* : public (the file URLs are served as <a href>
    in the browser, no auth header is sent)

Other endpoints require a valid Authorization header.
"""
import os
import secrets
import hmac
from typing import Optional
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp


# Public endpoints that don't require auth
PUBLIC_PATHS = (
    "/",
    "/config",
    "/hardware/",
    "/processors/list",
    "/media/output/",
    "/media/upload/",   # the URL is shared in browser, no auth header
    "/jobs/stream",     # SSE — auth would be redundant w/ bearer
)


def generate_token() -> str:
    """Generate a cryptographically random token (for first-run setup)."""
    return secrets.token_urlsafe(32)


def get_configured_token() -> Optional[str]:
    """Read the API token from env. None means auth is disabled."""
    return os.environ.get("FACEFUSION_API_TOKEN") or None


def is_public_path(path: str) -> bool:
    """Check whether a path is in the public whitelist."""
    if path in PUBLIC_PATHS:
        return True
    for prefix in ("/hardware/", "/media/output/", "/media/upload/"):
        if path.startswith(prefix):
            return True
    return False


def verify_bearer(auth_header: Optional[str], expected_token: str) -> bool:
    """
    Constant-time compare to avoid timing attacks.
    Returns True iff Authorization header is a valid Bearer token.
    """
    if not auth_header or not auth_header.startswith("Bearer "):
        return False
    presented = auth_header[7:].strip()
    if not presented or not expected_token:
        return False
    return hmac.compare_digest(presented, expected_token)


class BearerAuthMiddleware(BaseHTTPMiddleware):
    """
    Bearer token gate. Skip if FACEFUSION_API_TOKEN is not configured.

    Methods allowed without auth: GET on public paths. POST/PUT/DELETE
    on those paths still require auth.
    """

    def __init__(self, app: ASGIApp, token: Optional[str] = None):
        super().__init__(app)
        # If explicit token is None, pull from env. If still None, auth disabled.
        self.token = token if token is not None else get_configured_token()

    async def dispatch(self, request: Request, call_next):
        # Auth disabled (local-only mode)
        if not self.token:
            return await call_next(request)

        # Always allow OPTIONS (CORS preflight)
        if request.method == "OPTIONS":
            return await call_next(request)

        # Whitelist: GET on public paths
        if request.method == "GET" and is_public_path(request.url.path):
            return await call_next(request)

        # Verify Authorization header
        auth_header = request.headers.get("authorization")
        if not verify_bearer(auth_header, self.token):
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing or invalid Authorization header. Set 'Authorization: Bearer <token>'."},
                headers={"WWW-Authenticate": 'Bearer realm="facefusion"'},
            )

        return await call_next(request)
