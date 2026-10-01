"""
Tests for the head-swap module (R14 of gauntlet).

Covers:
- HeadSwapConfig defaults + from_request
- SwapMode enum
- summary_for_api contract
- HTTP endpoint /api/jobs/{id}/head-swap-info
"""
import pytest

from youface.api import headswap as headswap_mod


# ---------------------------------------------------------------------------
# HeadSwapConfig
# ---------------------------------------------------------------------------

def test_config_defaults_when_none():
    cfg = headswap_mod.HeadSwapConfig.from_request(None)
    assert cfg.enabled is False
    assert cfg.mask_expansion_px == 80
    assert cfg.include_hair is True
    assert cfg.include_ears is True
    assert cfg.include_neck is False


def test_config_defaults_when_empty_dict():
    cfg = headswap_mod.HeadSwapConfig.from_request({})
    assert cfg.enabled is False
    assert cfg.mask_expansion_px == 80


def test_config_overrides():
    cfg = headswap_mod.HeadSwapConfig.from_request({
        "enabled": True,
        "mask_expansion_px": 200,
        "include_hair": False,
        "include_ears": False,
        "include_neck": True,
    })
    assert cfg.enabled is True
    assert cfg.mask_expansion_px == 200
    assert cfg.include_hair is False
    assert cfg.include_ears is False
    assert cfg.include_neck is True


def test_config_to_dict_round_trip():
    cfg = headswap_mod.HeadSwapConfig(enabled=True, mask_expansion_px=150)
    d = cfg.to_dict()
    assert d["enabled"] is True
    assert d["mask_expansion_px"] == 150
    # Round trip through from_request
    cfg2 = headswap_mod.HeadSwapConfig.from_request(d)
    assert cfg2.enabled == cfg.enabled
    assert cfg2.mask_expansion_px == cfg.mask_expansion_px


def test_config_mask_expansion_coerced_to_int():
    cfg = headswap_mod.HeadSwapConfig.from_request({"mask_expansion_px": "120"})
    assert cfg.mask_expansion_px == 120
    assert isinstance(cfg.mask_expansion_px, int)


# ---------------------------------------------------------------------------
# SwapMode
# ---------------------------------------------------------------------------

def test_swap_mode_face_when_disabled():
    assert headswap_mod.mode_for_job(False) == headswap_mod.SwapMode.FACE


def test_swap_mode_head_when_enabled():
    assert headswap_mod.mode_for_job(True) == headswap_mod.SwapMode.HEAD


def test_swap_mode_values():
    assert headswap_mod.SwapMode.FACE.value == "face"
    assert headswap_mod.SwapMode.HEAD.value == "head"


# ---------------------------------------------------------------------------
# summary_for_api
# ---------------------------------------------------------------------------

def test_summary_for_api_disabled():
    out = headswap_mod.summary_for_api(None)
    assert out["mode"] == "face"
    assert out["config"]["enabled"] is False


def test_summary_for_api_enabled():
    out = headswap_mod.summary_for_api({"enabled": True, "mask_expansion_px": 100})
    assert out["mode"] == "head"
    assert out["config"]["enabled"] is True
    assert out["config"]["mask_expansion_px"] == 100


# ---------------------------------------------------------------------------
# HTTP layer
# ---------------------------------------------------------------------------

@pytest.fixture
def headswap_app(tmp_path):
    """A minimal FastAPI app exposing the head-swap endpoint."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from youface.api.database import Base
    from youface.api.routes import headswap as headswap_routes
    from youface.api import database as db_mod

    db_path = tmp_path / "head.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    # Patch the module-level SessionLocal so the endpoint hits our DB
    import unittest.mock
    with unittest.mock.patch.object(db_mod, "SessionLocal", SessionLocal):
        app = FastAPI()
        app.include_router(headswap_routes.router, prefix="/api")
        with TestClient(app) as c:
            yield c, SessionLocal
    try:
        db_path.unlink()
    except Exception:
        pass


def test_head_swap_info_returns_default_when_no_job(headswap_app):
    client, _ = headswap_app
    res = client.get("/api/jobs/no-such-job/head-swap-info")
    assert res.status_code == 404


def test_head_swap_info_returns_summary(headswap_app):
    """When a job exists, the endpoint returns a valid summary."""
    client, SessionLocal = headswap_app
    from youface.api.database import JobModel
    with SessionLocal() as db:
        db.add(JobModel(
            id="job-head-1",
            status="completed",
            source_paths="[]",
            target_path="/tmp/x",
            output_path="/tmp/out",
        ))
        db.commit()

    res = client.get("/api/jobs/job-head-1/head-swap-info")
    assert res.status_code == 200
    body = res.json()
    assert body["mode"] in ("face", "head")
    assert "config" in body
    assert "mask_expansion_px" in body["config"]
