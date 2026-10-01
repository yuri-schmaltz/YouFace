"""
Tests for multi-tenant support (R7 of gauntlet).

Covers:
- Tenant CRUD (create/list/get/disable/enable/rotate)
- Quota ledger (record, retrieve, remaining)
- API key hashing (raw key only returned once)
- Admin endpoints require the YOUFACE_API_TOKEN or admin tenant
- Disabled tenants cannot authenticate
- Non-admin tenants cannot hit admin endpoints

Uses an isolated in-memory SQLite + a fresh app instance to avoid
leaking tenant state across tests.
"""
import os
import pytest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from youface.api.database import Base
from youface.api import tenants as tenants_mod


# --- isolated in-memory DB ---------------------------------------------------

@pytest.fixture(scope="module")
def isolated_engine():
    """Per-module engine + tables for tenant tests.

    We don't reuse the global SessionLocal because we want tenant tests
    to start from a clean slate (no leftover tenants from other test files).
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return engine


@pytest.fixture(autouse=True)
def reset_tenants(isolated_engine):
    """Patch SessionLocal to use our isolated engine, then clear rows."""
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=isolated_engine)

    with patch.object(tenants_mod, "SessionLocal", SessionLocal):
        # Truncate between tests
        with SessionLocal() as db:
            for table in ("tenant_usage", "tenants", "jobs"):
                try:
                    db.execute(_truncate(table))
                    db.commit()
                except Exception:
                    db.rollback()
        yield


def _truncate(table: str):
    from sqlalchemy import text
    return text(f"DELETE FROM {table}")


# --- Pure function tests ----------------------------------------------------

def test_create_tenant_returns_raw_key_only_once(isolated_engine):
    """The raw key is in the return value but never in the DB."""
    tenant, raw_key = tenants_mod.create_tenant(name="alice")
    assert tenant.name == "alice"
    assert raw_key
    assert len(raw_key) >= 32

    # Look it up by the raw key — should hit
    again = tenants_mod.get_tenant_by_key(raw_key)
    assert again is not None
    assert again.id == tenant.id

    # The raw key must NOT appear in the DB row
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=isolated_engine)
    with SessionLocal() as db:
        row = db.query(tenants_mod.TenantModel).filter_by(id=tenant.id).first()
        assert raw_key not in row.api_key_hash


def test_create_tenant_duplicate_name_raises():
    tenants_mod.create_tenant(name="bob")
    with pytest.raises(ValueError, match="already exists"):
        tenants_mod.create_tenant(name="bob")


def test_create_tenant_empty_name_raises():
    with pytest.raises(ValueError, match="must not be empty"):
        tenants_mod.create_tenant(name="   ")


def test_get_tenant_by_key_unknown_returns_none():
    assert tenants_mod.get_tenant_by_key("nope-not-a-real-key") is None
    assert tenants_mod.get_tenant_by_key("") is None


def test_disable_then_get_by_key_returns_none():
    _, key = tenants_mod.create_tenant(name="carol")
    t = tenants_mod.get_tenant_by_key(key)
    assert t is not None
    assert tenants_mod.disable_tenant(t.id) is True
    assert tenants_mod.get_tenant_by_key(key) is None


def test_enable_restores_authentication():
    t, key = tenants_mod.create_tenant(name="dave")
    tenants_mod.disable_tenant(t.id)
    assert tenants_mod.get_tenant_by_key(key) is None
    tenants_mod.enable_tenant(t.id)
    assert tenants_mod.get_tenant_by_key(key) is not None


def test_rotate_changes_key():
    t, old_key = tenants_mod.create_tenant(name="eve")
    new_key = tenants_mod.rotate_tenant_key(t.id)
    assert new_key is not None
    assert new_key != old_key
    assert tenants_mod.get_tenant_by_key(old_key) is None
    assert tenants_mod.get_tenant_by_key(new_key) is not None


def test_rotate_unknown_tenant_returns_none():
    assert tenants_mod.rotate_tenant_key("tnt-doesnotexist") is None


def test_list_tenants_excludes_disabled_by_default():
    tenants_mod.create_tenant(name="frank")
    tenants_mod.create_tenant(name="gina")
    gina_id = tenants_mod.get_tenant_by_key(
        next(iter(t.api_key_hash for t in tenants_mod.list_tenants(include_disabled=True) if t.name == "gina"))
    ) if False else None  # noqa: E501
    # simpler: disable via id from list
    listing = tenants_mod.list_tenants(include_disabled=True)
    gina = next(t for t in listing if t.name == "gina")
    tenants_mod.disable_tenant(gina.id)
    visible = [t.name for t in tenants_mod.list_tenants(include_disabled=False)]
    assert "frank" in visible
    assert "gina" not in visible
    all_visible = [t.name for t in tenants_mod.list_tenants(include_disabled=True)]
    assert "gina" in all_visible


def test_update_quota():
    t, _ = tenants_mod.create_tenant(name="hank", monthly_quota_minutes=100)
    assert tenants_mod.update_tenant_quota(t.id, 500)
    again = tenants_mod.get_tenant_by_id(t.id)
    assert again.monthly_quota_minutes == 500


# --- Quota ledger ----------------------------------------------------------

def test_record_and_get_usage():
    t, _ = tenants_mod.create_tenant(name="ivy")
    assert tenants_mod.get_usage_minutes(t.id) == 0.0
    tenants_mod.record_job_completion(t.id, duration_seconds=120)  # 2 min
    tenants_mod.record_job_completion(t.id, duration_seconds=30)   # 0.5 min
    used = tenants_mod.get_usage_minutes(t.id)
    assert used == pytest.approx(2.5, abs=0.01)


def test_record_skips_anonymous_and_zero_duration():
    tenants_mod.record_job_completion(None, 60)  # no-op
    tenants_mod.record_job_completion("tnt-x", 0)
    tenants_mod.record_job_completion("tnt-x", -10)


def test_remaining_quota_unlimited_returns_none():
    t, _ = tenants_mod.create_tenant(name="jane", monthly_quota_minutes=tenants_mod.UNLIMITED_QUOTA)
    assert tenants_mod.remaining_quota_minutes(t) is None


def test_remaining_quota_decreases_with_usage():
    t, _ = tenants_mod.create_tenant(name="karl", monthly_quota_minutes=10)
    assert tenants_mod.remaining_quota_minutes(t) == 10.0
    tenants_mod.record_job_completion(t.id, 60 * 4)  # 4 min
    assert tenants_mod.remaining_quota_minutes(t) == pytest.approx(6.0, abs=0.01)
    tenants_mod.record_job_completion(t.id, 60 * 60)  # 60 min
    assert tenants_mod.remaining_quota_minutes(t) == 0.0  # clamped at 0


# --- HTTP layer tests ------------------------------------------------------

@pytest.fixture
def http_client(isolated_engine):
    """A fresh FastAPI TestClient backed by our isolated DB.

    Patches tenants.SessionLocal so TenantMiddleware + admin routes
    use the test DB.
    """
    from fastapi.testclient import TestClient
    from youface.api.main import app
    from youface.api.database import get_db

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=isolated_engine)

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    # Use patches so both admin endpoints and TenantMiddleware hit our DB.
    # The admin routes import helpers (create_tenant, etc.) directly from
    # youface.api.tenants, so a single patch on that module covers all
    # of them. The middleware also imports get_tenant_by_key from there.
    with patch.object(tenants_mod, "SessionLocal", SessionLocal), \
         patch.object(tenants_mod, "ensure_tenant_tables", lambda: None):
        # Replace the app's DB dependency so /api/jobs and similar endpoints
        # don't crash if they happen to be hit during these tests.
        app.dependency_overrides[get_db] = override_get_db
        # Disable bearer auth so anonymous endpoints respond.
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("YOUFACE_API_TOKEN", None)
            with TestClient(app) as c:
                yield c
        app.dependency_overrides.clear()


def test_admin_create_requires_admin_token(http_client):
    """No auth at all → 403 from the admin guard."""
    res = http_client.post("/api/admin/tenants", json={"name": "noauth"})
    assert res.status_code == 403


def test_admin_create_with_env_token(http_client):
    """YOUFACE_API_TOKEN as bearer grants admin."""
    with patch.dict(os.environ, {"YOUFACE_API_TOKEN": "secret123"}):
        res = http_client.post(
            "/api/admin/tenants",
            json={"name": "first"},
            headers={"Authorization": "Bearer secret123"},
        )
        assert res.status_code == 200
        body = res.json()
        assert "api_key" in body
        assert body["tenant"]["name"] == "first"
        assert "Store this key now" in body["warning"]


def test_admin_create_duplicate_returns_409(http_client):
    with patch.dict(os.environ, {"YOUFACE_API_TOKEN": "secret123"}):
        http_client.post(
            "/api/admin/tenants",
            json={"name": "dup"},
            headers={"Authorization": "Bearer secret123"},
        )
        res = http_client.post(
            "/api/admin/tenants",
            json={"name": "dup"},
            headers={"Authorization": "Bearer secret123"},
        )
        assert res.status_code == 409


def test_admin_list(http_client):
    with patch.dict(os.environ, {"YOUFACE_API_TOKEN": "admin"}):
        http_client.post("/api/admin/tenants", json={"name": "a"}, headers={"Authorization": "Bearer admin"})
        http_client.post("/api/admin/tenants", json={"name": "b"}, headers={"Authorization": "Bearer admin"})
        res = http_client.get("/api/admin/tenants", headers={"Authorization": "Bearer admin"})
        assert res.status_code == 200
        names = {t["name"] for t in res.json()}
        assert {"a", "b"}.issubset(names)


def test_admin_rotate_returns_new_key(http_client):
    with patch.dict(os.environ, {"YOUFACE_API_TOKEN": "admin"}):
        c = http_client.post("/api/admin/tenants", json={"name": "rot"}, headers={"Authorization": "Bearer admin"}).json()
        tid = c["tenant"]["id"]
        old_key = c["api_key"]
        r = http_client.post(f"/api/admin/tenants/{tid}/rotate", headers={"Authorization": "Bearer admin"})
        assert r.status_code == 200
        assert r.json()["api_key"] != old_key


def test_tenant_x_api_key_authenticates(http_client):
    """After creation, the new tenant's X-API-Key identifies the caller
    and the response carries X-Tenant-Id + X-RateLimit-* headers."""
    with patch.dict(os.environ, {"YOUFACE_API_TOKEN": "admin"}):
        c = http_client.post("/api/admin/tenants", json={"name": "authed"}, headers={"Authorization": "Bearer admin"}).json()
        key = c["api_key"]
    res = http_client.get("/api/admin/usage", headers={"X-API-Key": key})
    assert res.status_code == 200
    assert res.headers.get("X-Tenant-Id") == c["tenant"]["id"]
    assert res.headers.get("X-Tenant-Name") == "authed"
    assert res.headers.get("X-RateLimit-Limit") == str(tenants_mod.DEFAULT_MONTHLY_QUOTA_MINUTES)


def test_disabled_tenant_loses_authentication(http_client):
    with patch.dict(os.environ, {"YOUFACE_API_TOKEN": "admin"}):
        c = http_client.post("/api/admin/tenants", json={"name": "killme"}, headers={"Authorization": "Bearer admin"}).json()
        tid = c["tenant"]["id"]
        key = c["api_key"]
        http_client.post(f"/api/admin/tenants/{tid}/disable", headers={"Authorization": "Bearer admin"})
    res = http_client.get("/api/admin/usage", headers={"X-API-Key": key})
    # TenantMiddleware finds no tenant → admin endpoint returns 401
    assert res.status_code == 401


def test_non_admin_tenant_cannot_create_others(http_client):
    """A non-admin tenant can hit /admin/usage for themselves but NOT
    POST /admin/tenants."""
    with patch.dict(os.environ, {"YOUFACE_API_TOKEN": "admin"}):
        c = http_client.post(
            "/api/admin/tenants",
            json={"name": "regular", "is_admin": False},
            headers={"Authorization": "Bearer admin"},
        ).json()
        key = c["api_key"]
    res = http_client.post(
        "/api/admin/tenants",
        json={"name": "another"},
        headers={"X-API-Key": key},
    )
    assert res.status_code == 403


def test_quota_headers_unlimited_tenant(http_client):
    """If a tenant has -1 quota, X-RateLimit-Remaining is 'unlimited'."""
    with patch.dict(os.environ, {"YOUFACE_API_TOKEN": "admin"}):
        c = http_client.post(
            "/api/admin/tenants",
            json={"name": "free", "monthly_quota_minutes": -1},
            headers={"Authorization": "Bearer admin"},
        ).json()
        key = c["api_key"]
    res = http_client.get("/api/admin/usage", headers={"X-API-Key": key})
    assert res.status_code == 200
    assert res.headers["X-RateLimit-Remaining"] == "unlimited"
