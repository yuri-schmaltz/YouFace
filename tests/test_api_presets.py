"""
Tests for presets / recipes (R9 of gauntlet).

Covers:
- CRUD on presets
- Tenant scoping (only owner sees private presets)
- shared flag makes a preset visible across tenants (admin-only)
- Apply merges preset data with client overrides (overrides win)
- Validation: missing name → 422, duplicate name → 409
- Anonymous requests are rejected for non-admin
"""
import os
import pytest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from facefusion.api import presets as presets_mod
from facefusion.api import tenants as tenants_mod


# ---------------------------------------------------------------------------
# Isolated DB
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def isolated_preset_db(tmp_path):
    db_path = tmp_path / "presets.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    from facefusion.api.database import Base
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    with patch.object(presets_mod, "SessionLocal", SessionLocal):
        # Clean rows for each test
        with SessionLocal() as db:
            try:
                db.execute(_truncate("presets"))
                db.commit()
            except Exception:
                db.rollback()
        yield
    try:
        db_path.unlink()
    except Exception:
        pass


def _truncate(table: str):
    from sqlalchemy import text
    return text(f"DELETE FROM {table}")


# ---------------------------------------------------------------------------
# Pure-function tests
# ---------------------------------------------------------------------------

def test_create_preset_returns_id():
    p = presets_mod.create_preset(
        name="instagram-9x16",
        data={"face_swapper_weight": 0.85, "processors": ["face_swapper"]},
        description="Reels preset",
    )
    assert p.id.startswith("prs-")
    assert p.name == "instagram-9x16"
    assert p.data["face_swapper_weight"] == 0.85


def test_duplicate_name_in_same_scope_raises():
    presets_mod.create_preset(name="x", data={"a": 1}, owner_tenant_id="tnt-1")
    with pytest.raises(ValueError, match="already exists"):
        presets_mod.create_preset(name="x", data={"a": 2}, owner_tenant_id="tnt-1")


def test_same_name_different_owners_is_allowed():
    presets_mod.create_preset(name="x", data={"a": 1}, owner_tenant_id="tnt-1")
    p = presets_mod.create_preset(name="x", data={"a": 2}, owner_tenant_id="tnt-2")
    assert p.id


def test_get_preset_round_trips_data():
    p = presets_mod.create_preset(
        name="y",
        data={"face_mask_blur": 0.42, "processors": ["face_swapper", "face_enhancer"]},
    )
    again = presets_mod.get_preset(p.id)
    assert again is not None
    assert again.data["face_mask_blur"] == 0.42
    assert again.data["processors"] == ["face_swapper", "face_enhancer"]


def test_update_preset_partial():
    p = presets_mod.create_preset(name="z", data={"a": 1, "b": 2})
    updated = presets_mod.update_preset(p.id, data={"a": 99})
    assert updated.data["a"] == 99
    # original "b" is gone — update REPLACES, doesn't merge
    assert "b" not in updated.data


def test_update_preset_metadata_only():
    p = presets_mod.create_preset(name="z2", data={"a": 1})
    updated = presets_mod.update_preset(p.id, name="z2-renamed", description="new")
    assert updated.name == "z2-renamed"
    assert updated.description == "new"
    assert updated.data == {"a": 1}


def test_delete_preset():
    p = presets_mod.create_preset(name="k", data={"a": 1})
    assert presets_mod.delete_preset(p.id) is True
    assert presets_mod.get_preset(p.id) is None
    assert presets_mod.delete_preset(p.id) is False


def test_list_filters_by_owner_and_shared():
    presets_mod.create_preset(name="own", data={}, owner_tenant_id="tnt-a")
    presets_mod.create_preset(name="other", data={}, owner_tenant_id="tnt-b")
    presets_mod.create_preset(name="shared", data={}, shared=True)

    visible_a = presets_mod.list_presets(owner_tenant_id="tnt-a")
    visible_b = presets_mod.list_presets(owner_tenant_id="tnt-b")
    admin_visible = presets_mod.list_presets(owner_tenant_id=None)

    names_a = {p.name for p in visible_a}
    names_b = {p.name for p in visible_b}
    names_admin = {p.name for p in admin_visible}

    assert "own" in names_a
    assert "shared" in names_a  # shared always visible to tenants
    assert "other" not in names_a  # private to other tenant
    assert "other" in names_b
    assert "own" not in names_b
    assert {"own", "other", "shared"} == names_admin


def test_merge_for_apply_overrides_win():
    p = presets_mod.create_preset(
        name="base",
        data={"face_swapper_weight": 0.5, "face_mask_blur": 0.3, "smoothing": 5},
    )
    merged = presets_mod.merge_for_apply(p, overrides={
        "face_swapper_weight": 0.9,
        "processors": ["face_swapper", "face_enhancer"],  # new key
    })
    assert merged["face_swapper_weight"] == 0.9  # overridden
    assert merged["face_mask_blur"] == 0.3       # preserved
    assert merged["smoothing"] == 5              # preserved
    assert merged["processors"] == ["face_swapper", "face_enhancer"]  # added


def test_name_filter_substring_case_insensitive():
    presets_mod.create_preset(name="Instagram-9x16", data={})
    presets_mod.create_preset(name="YouTube-Shorts", data={})
    presets_mod.create_preset(name="Other", data={})
    hits = presets_mod.list_presets(name_filter="insta")
    assert len(hits) == 1
    assert hits[0].name == "Instagram-9x16"


# ---------------------------------------------------------------------------
# HTTP layer tests
# ---------------------------------------------------------------------------
#
# We test the presets routes by mounting ONLY the presets + tenants routers
# into a minimal FastAPI app — this avoids spinning up the worker thread
# that the full facefusion/api/main.py app starts in its lifespan, which
# would hang the test suite.
# ---------------------------------------------------------------------------

@pytest.fixture
def preset_app(tmp_path):
    """A minimal FastAPI app exposing just the presets + tenants routers."""
    from fastapi import FastAPI
    from facefusion.api.routes import presets as presets_routes
    from facefusion.api.routes import tenants as tenants_routes
    from facefusion.api.middleware import TenantMiddleware
    from facefusion.api.database import get_db, Base

    db_path = tmp_path / "http.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    # Add TenantMiddleware so request.state.tenant is populated. We can't
    # add the other middlewares (RateLimiter/SecurityHeaders/MaxBodySize)
    # because they use FastAPI app.state defaults that the full app sets.
    app.add_middleware(TenantMiddleware)
    app.include_router(presets_routes.router, prefix="/api")
    app.include_router(tenants_routes.router, prefix="/api")

    with patch.object(presets_mod, "SessionLocal", SessionLocal), \
         patch.object(presets_mod, "ensure_preset_tables", lambda: None), \
         patch.object(tenants_mod, "SessionLocal", SessionLocal), \
         patch.object(tenants_mod, "ensure_tenant_tables", lambda: None):
        from fastapi.testclient import TestClient
        with TestClient(app) as c:
            yield c
        try:
            db_path.unlink()
        except Exception:
            pass


def test_list_requires_auth(preset_app):
    """No auth → 401 (admin or tenant required)."""
    res = preset_app.get("/api/presets")
    assert res.status_code == 401


def test_create_and_list_with_admin_token(preset_app):
    with patch.dict(os.environ, {"FACEFUSION_API_TOKEN": "admin"}):
        payload = {
            "name": "reels",
            "description": "Instagram reels preset",
            "data": {
                "face_swapper_weight": 0.85,
                "processors": ["face_swapper"],
                "output_format": "mp4",
            },
        }
        res = preset_app.post("/api/presets", json=payload, headers={"Authorization": "Bearer admin"})
        assert res.status_code == 200
        body = res.json()
        assert body["name"] == "reels"
        pid = body["id"]

        # List now includes it
        res2 = preset_app.get("/api/presets", headers={"Authorization": "Bearer admin"})
        assert res2.status_code == 200
        names = {p["name"] for p in res2.json()["presets"]}
        assert "reels" in names


def test_create_duplicate_name_returns_409(preset_app):
    with patch.dict(os.environ, {"FACEFUSION_API_TOKEN": "admin"}):
        payload = {"name": "dupe", "data": {}}
        r1 = preset_app.post("/api/presets", json=payload, headers={"Authorization": "Bearer admin"})
        assert r1.status_code == 200
        r2 = preset_app.post("/api/presets", json=payload, headers={"Authorization": "Bearer admin"})
        assert r2.status_code == 409


def test_create_with_missing_name_returns_422(preset_app):
    with patch.dict(os.environ, {"FACEFUSION_API_TOKEN": "admin"}):
        res = preset_app.post(
            "/api/presets",
            json={"data": {}},
            headers={"Authorization": "Bearer admin"},
        )
        assert res.status_code == 422


def test_get_update_delete_lifecycle(preset_app):
    with patch.dict(os.environ, {"FACEFUSION_API_TOKEN": "admin"}):
        # create
        c = preset_app.post(
            "/api/presets",
            json={"name": "lifecycle", "data": {"face_swapper_weight": 0.5}},
            headers={"Authorization": "Bearer admin"},
        ).json()
        pid = c["id"]

        # get
        g = preset_app.get(f"/api/presets/{pid}", headers={"Authorization": "Bearer admin"})
        assert g.status_code == 200
        assert g.json()["name"] == "lifecycle"

        # update
        u = preset_app.put(
            f"/api/presets/{pid}",
            json={"name": "lifecycle-v2", "description": "new"},
            headers={"Authorization": "Bearer admin"},
        )
        assert u.status_code == 200
        assert u.json()["name"] == "lifecycle-v2"
        assert u.json()["description"] == "new"

        # delete
        d = preset_app.delete(f"/api/presets/{pid}", headers={"Authorization": "Bearer admin"})
        assert d.status_code == 200

        # get after delete
        g2 = preset_app.get(f"/api/presets/{pid}", headers={"Authorization": "Bearer admin"})
        assert g2.status_code == 404


def test_apply_returns_merged_data(preset_app):
    with patch.dict(os.environ, {"FACEFUSION_API_TOKEN": "admin"}):
        c = preset_app.post(
            "/api/presets",
            json={
                "name": "merge-base",
                "data": {
                    "face_swapper_weight": 0.5,
                    "face_mask_blur": 0.3,
                    "processors": ["face_swapper"],
                },
            },
            headers={"Authorization": "Bearer admin"},
        ).json()
        pid = c["id"]

        res = preset_app.post(
            f"/api/presets/{pid}/apply",
            json={"overrides": {"face_swapper_weight": 0.95, "smoothing": 9}},
            headers={"Authorization": "Bearer admin"},
        )
        assert res.status_code == 200
        body = res.json()
        assert body["ready_for_job_create"] is True
        merged = body["merged"]
        assert merged["face_swapper_weight"] == 0.95  # overridden
        assert merged["face_mask_blur"] == 0.3        # preserved
        assert merged["processors"] == ["face_swapper"]  # preserved
        assert merged["smoothing"] == 9                # added


def test_tenant_sees_only_own_and_shared(preset_app):
    """Two tenants + an admin; each tenant sees only their own + shared."""
    # Create tenant A and B via admin
    with patch.dict(os.environ, {"FACEFUSION_API_TOKEN": "admin"}):
        a = preset_app.post(
            "/api/admin/tenants",
            json={"name": "tenant-a"},
            headers={"Authorization": "Bearer admin"},
        ).json()
        b = preset_app.post(
            "/api/admin/tenants",
            json={"name": "tenant-b"},
            headers={"Authorization": "Bearer admin"},
        ).json()
        key_a = a["api_key"]
        key_b = b["api_key"]

        # Tenant A creates a private preset
        preset_app.post(
            "/api/presets",
            json={"name": "a-private", "data": {"a": 1}},
            headers={"X-API-Key": key_a},
        )
        # Admin creates a shared preset (only admin can mark shared=true)
        admin_shared = preset_app.post(
            "/api/presets",
            json={"name": "shared-preset", "data": {}, "shared": True},
            headers={"Authorization": "Bearer admin"},
        ).json()

        # Tenant A sees its own + the shared preset
        list_a_res = preset_app.get(
            "/api/presets", headers={"X-API-Key": key_a}
        )
        assert list_a_res.status_code == 200, f"Expected 200, got {list_a_res.status_code}: {list_a_res.text}"
        list_a = list_a_res.json()["presets"]
        names_a = {p["name"] for p in list_a}
        assert "a-private" in names_a
        assert "shared-preset" in names_a

        # Tenant B sees only the shared one
        list_b_res = preset_app.get(
            "/api/presets", headers={"X-API-Key": key_b}
        )
        assert list_b_res.status_code == 200, f"Expected 200, got {list_b_res.status_code}: {list_b_res.text}"
        list_b = list_b_res.json()["presets"]
        names_b = {p["name"] for p in list_b}
        assert "a-private" not in names_b
        assert "shared-preset" in names_b
