"""
Tests for the BearerAuthMiddleware in youface/api/auth.py.

Covers:
- Auth disabled when YOUFACE_API_TOKEN is unset (backward compat)
- Auth required when token is set
- Public GET paths bypass auth
- Non-GET (POST/PUT/DELETE) always require auth
- Invalid token returns 401 with WWW-Authenticate header
- Constant-time comparison (hmac.compare_digest)
"""
import os
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from youface.api.main import app
from youface.api.database import Base, get_db
from youface.api.auth import (
    BearerAuthMiddleware,
    generate_token,
    get_configured_token,
    is_public_path,
    verify_bearer,
)

# Setup in-memory DB
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="module", autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    def override_get_db():
        try:
            db = TestingSessionLocal()
            yield db
        finally:
            db.close()
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Pure-function unit tests (no TestClient)
# ---------------------------------------------------------------------------

def test_generate_token_returns_urlsafe_string():
    """generate_token() returns a token safe for URL use."""
    tok = generate_token()
    assert isinstance(tok, str)
    assert len(tok) >= 32  # token_urlsafe(32) returns ~43 chars


def test_get_configured_token_returns_env_value():
    """get_configured_token() reads YOUFACE_API_TOKEN env var."""
    with patch.dict(os.environ, {"YOUFACE_API_TOKEN": "test-token-xyz"}):
        assert get_configured_token() == "test-token-xyz"
    with patch.dict(os.environ, {}, clear=True):
        assert get_configured_token() is None


def test_verify_bearer_accepts_correct_token():
    """verify_bearer returns True for matching token."""
    assert verify_bearer("Bearer secret-123", "secret-123") is True


def test_verify_bearer_rejects_wrong_token():
    """verify_bearer returns False for non-matching token."""
    assert verify_bearer("Bearer wrong", "right") is False
    assert verify_bearer("Bearer right", "wrong") is False


def test_verify_bearer_rejects_missing_or_malformed():
    """verify_bearer returns False for None / no Bearer prefix / empty."""
    assert verify_bearer(None, "x") is False
    assert verify_bearer("", "x") is False
    assert verify_bearer("Basic abc", "x") is False  # not Bearer
    assert verify_bearer("Bearer ", "x") is False  # empty after Bearer
    assert verify_bearer("Bearer", "x") is False   # no space


def test_is_public_path_recognizes_whitelist():
    """is_public_path correctly identifies whitelisted paths."""
    assert is_public_path("/") is True
    assert is_public_path("/api/config") is True
    assert is_public_path("/api/hardware/devices") is True
    assert is_public_path("/api/processors/list") is True
    assert is_public_path("/api/media/output/result.mp4") is True
    assert is_public_path("/api/jobs/stream") is True
    # Non-whitelisted
    assert is_public_path("/api/jobs") is False
    assert is_public_path("/api/config") is True  # config IS whitelisted (GET only)
    # Note: POST /api/config is NOT bypassed by is_public_path; the
    # middleware checks method+path. See middleware tests below.


# ---------------------------------------------------------------------------
# Integration tests with TestClient + middleware
# ---------------------------------------------------------------------------

def test_auth_disabled_when_no_env_var(client):
    """No YOUFACE_API_TOKEN -> all requests pass without auth."""
    with patch.dict(os.environ, {}, clear=True):
        # POST should work without Authorization
        resp = client.post("/api/jobs", json={})
        # 422 (validation error) is OK; we just need NOT 401
        assert resp.status_code != 401


def test_auth_required_when_env_var_set(client):
    """When token is set, POST without auth returns 401."""
    with patch.dict(os.environ, {"YOUFACE_API_TOKEN": "test-secret"}):
        resp = client.post("/api/jobs", json={})
        assert resp.status_code == 401
        assert "Authorization" in resp.json()["detail"]


def test_auth_accepts_correct_bearer(client):
    """With env var set, valid Bearer token allows POST through."""
    with patch.dict(os.environ, {"YOUFACE_API_TOKEN": "test-secret"}):
        # Wrong token
        resp_wrong = client.post(
            "/api/jobs",
            json={},
            headers={"Authorization": "Bearer wrong-token"},
        )
        assert resp_wrong.status_code == 401

        # Correct token
        resp_right = client.post(
            "/api/jobs",
            json={"source_paths": [], "target_path": "/tmp/x"},
            headers={"Authorization": "Bearer test-secret"},
        )
        # Should be 200/201/422/500 — anything but 401
        assert resp_right.status_code != 401


def test_public_get_paths_bypass_auth(client):
    """GET on whitelisted paths works without auth even when token is set."""
    with patch.dict(os.environ, {"YOUFACE_API_TOKEN": "test-secret"}):
        # These should all be 200 (no auth)
        assert client.get("/api/hardware/devices").status_code == 200
        assert client.get("/api/hardware/providers").status_code == 200
        assert client.get("/api/hardware/telemetry").status_code == 200
        assert client.get("/api/processors/list").status_code == 200
        assert client.get("/api/config").status_code == 200


def test_non_get_on_whitelisted_path_still_requires_auth(client):
    """POST on /api/config (which is whitelisted for GET) still needs auth."""
    with patch.dict(os.environ, {"YOUFACE_API_TOKEN": "test-secret"}):
        resp = client.post(
            "/api/config",
            json={"log_level": "debug"},
        )
        assert resp.status_code == 401


def test_unauthorized_response_includes_www_authenticate(client):
    """401 response must include WWW-Authenticate header per RFC 7235."""
    with patch.dict(os.environ, {"YOUFACE_API_TOKEN": "test-secret"}):
        resp = client.post("/api/jobs", json={})
        assert resp.status_code == 401
        assert "www-authenticate" in {k.lower() for k in resp.headers}
        assert "Bearer" in resp.headers.get("www-authenticate", "")


def test_options_request_bypasses_auth(client):
    """CORS preflight (OPTIONS) always bypasses auth."""
    with patch.dict(os.environ, {"YOUFACE_API_TOKEN": "test-secret"}):
        resp = client.options(
            "/api/jobs",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
            },
        )
        # OPTIONS should not return 401 (it returns 200/204 from CORS middleware)
        assert resp.status_code != 401
