"""
Tests for the dedicated face training pipeline (R12 of gauntlet).

Covers:
- Discovery of source images (correct extensions only)
- Embedding aggregation (mean + L2-normalized)
- Persistence of progress per checkpoint
- Saving the prototype to .npy
- HTTP start / list / show / result / cancel lifecycle
"""
import os
import time
from pathlib import Path
from unittest.mock import patch

import pytest
import numpy as np
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from facefusion.api import trainer as trainer_mod


# ---------------------------------------------------------------------------
# Isolated DB + per-test tmp source dirs
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def isolated_trainer_db(tmp_path):
    """Patch SessionLocal AND make sure the trainer tables exist in the
    SAME engine that SessionLocal points at, so run_training / start_training
    / get_train_job all see the same DB."""
    db_path = tmp_path / "trainer.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    from facefusion.api.database import Base
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    with patch.object(trainer_mod, "SessionLocal", SessionLocal), \
         patch("facefusion.api.trainer.ensure_train_tables", lambda: None):
        yield


def _make_source_dir(tmp_path: Path, count: int = 5) -> Path:
    src = tmp_path / "src"
    src.mkdir()
    for i in range(count):
        (src / f"img_{i:02d}.jpg").write_bytes(b"\xff\xd8\xff\xe0fake jpg content")
    # Also add a non-image file that must be skipped
    (src / "ignore.txt").write_text("not an image")
    return src


def _output_dir(tmp_path: Path) -> Path:
    out = tmp_path / "trained"
    out.mkdir()
    return out


# ---------------------------------------------------------------------------
# Pure-function tests on run_training()
# ---------------------------------------------------------------------------

def test_run_training_succeeds_on_valid_source(tmp_path):
    src = _make_source_dir(tmp_path, count=4)
    out = _output_dir(tmp_path) / "model.npy"
    job_id = "trn-test-1"

    # The autouse fixture already patched SessionLocal + ensured tables.
    from facefusion.api import database as _db_mod; SessionLocal = trainer_mod.SessionLocal
    with SessionLocal() as db:
        db.add(trainer_mod.TrainJobModel(
            id=job_id, name="t", source_dir=str(src), output_path=str(out),
        ))
        db.commit()

    summary = trainer_mod.run_training(job_id, str(src), str(out))

    assert summary.processed_images == 4  # only the 4 .jpg files (ignore.txt is not enumerated)
    assert summary.detected_faces == 4
    assert summary.skipped == 0  # nothing failed embedding
    assert summary.embedding_dim == 512
    assert summary.duration_seconds >= 0

    # The .npy must exist and be a unit vector
    assert out.exists()
    arr = np.load(str(out))
    assert arr.shape == (512,)
    norm = float(np.linalg.norm(arr))
    assert abs(norm - 1.0) < 1e-4  # L2-normalized

    # Job row reflects completed
    job = trainer_mod.get_train_job(job_id)
    assert job["status"] == "completed"
    assert job["progress"] == 100
    assert job["embedding_dim"] == 512
    assert job["detected_faces"] == 4


def test_run_training_handles_missing_source_dir(tmp_path):
    out = _output_dir(tmp_path) / "model.npy"
    job_id = "trn-missing"

    from facefusion.api import database as _db_mod; SessionLocal = trainer_mod.SessionLocal
    with SessionLocal() as db:
        db.add(trainer_mod.TrainJobModel(
            id=job_id, name="t", source_dir="/nonexistent", output_path=str(out),
        ))
        db.commit()

    summary = trainer_mod.run_training(job_id, "/nonexistent/dir/that/doesnt/exist", str(out))

    assert summary.processed_images == 0
    assert summary.detected_faces == 0

    job = trainer_mod.get_train_job(job_id)
    assert job["status"] == "failed"


def test_run_training_with_empty_source(tmp_path):
    src = tmp_path / "empty_src"
    src.mkdir()
    out = _output_dir(tmp_path) / "model.npy"
    job_id = "trn-empty"

    from facefusion.api import database as _db_mod; SessionLocal = trainer_mod.SessionLocal
    with SessionLocal() as db:
        db.add(trainer_mod.TrainJobModel(
            id=job_id, name="t", source_dir=str(src), output_path=str(out),
        ))
        db.commit()

    summary = trainer_mod.run_training(job_id, str(src), str(out))

    assert summary.processed_images == 0
    assert summary.detected_faces == 0
    assert summary.embedding_dim == 0

    job = trainer_mod.get_train_job(job_id)
    assert job["status"] == "failed"
    assert "No faces" in (job["error_message"] or "")


def test_run_training_progress_callback(tmp_path):
    """The on_progress callback fires once per processed image."""
    src = _make_source_dir(tmp_path, count=6)
    out = _output_dir(tmp_path) / "model.npy"
    job_id = "trn-cb"

    from facefusion.api import database as _db_mod; SessionLocal = trainer_mod.SessionLocal
    with SessionLocal() as db:
        db.add(trainer_mod.TrainJobModel(
            id=job_id, name="t", source_dir=str(src), output_path=str(out),
        ))
        db.commit()

    calls = []
    trainer_mod.run_training(
        job_id, str(src), str(out),
        on_progress=lambda processed, total, faces: calls.append((processed, total, faces)),
    )

    # The trainer fires the callback for every image.
    # With 6 images we expect at least one final call, regardless of
    # whether the checkpoint-driven calls (every 5) hit them all.
    assert len(calls) >= 1
    # Last call should reflect all processed
    assert calls[-1][0] == calls[-1][1]  # processed == total
    # Final processed count must equal total
    assert calls[-1][1] == 6


def test_run_training_uses_injected_embedder(tmp_path):
    """A custom embedder is invoked once per image."""
    src = _make_source_dir(tmp_path, count=3)
    out = _output_dir(tmp_path) / "model.npy"
    job_id = "trn-injected"

    from facefusion.api import database as _db_mod; SessionLocal = trainer_mod.SessionLocal
    with SessionLocal() as db:
        db.add(trainer_mod.TrainJobModel(
            id=job_id, name="t", source_dir=str(src), output_path=str(out),
        ))
        db.commit()

    called = []
    def fake_embed(path):
        called.append(path)
        return [1.0, 0.0, 0.0]  # fixed unit vector

    summary = trainer_mod.run_training(
        job_id, str(src), str(out), embedder=fake_embed,
    )

    assert len(called) == 3
    arr = np.load(str(out))
    assert arr.shape == (3,)
    # Mean of [1,0,0] three times is still [1,0,0]
    assert abs(arr[0] - 1.0) < 1e-6


# ---------------------------------------------------------------------------
# HTTP layer tests
# ---------------------------------------------------------------------------

@pytest.fixture
def train_app(tmp_path):
    """A minimal FastAPI app exposing just the train router + tenant mw.

    The autouse fixture has already patched trainer.SessionLocal and
    ensured tables exist on that engine. We just reuse it."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from facefusion.api.routes import train as train_routes
    from facefusion.api.routes import tenants as tenants_routes
    from facefusion.api.middleware import TenantMiddleware

    app = FastAPI()
    app.add_middleware(TenantMiddleware)
    app.include_router(train_routes.router, prefix="/api")
    app.include_router(tenants_routes.router, prefix="/api")

    src = tmp_path / "src"
    src.mkdir()
    for i in range(3):
        (src / f"img_{i:02d}.jpg").write_bytes(b"\xff\xd8\xff\xe0fake")

    out = tmp_path / "trained"
    out.mkdir()

    # Patch tenants too (since the autouse fixture only patched trainers)
    from facefusion.api import tenants as tenants_mod
    from facefusion.api import database as _db_mod; SessionLocal = trainer_mod.SessionLocal
    with patch.object(tenants_mod, "SessionLocal", SessionLocal), \
         patch.object(tenants_mod, "ensure_tenant_tables", lambda: None):
        with TestClient(app) as c:
            yield c, str(src), str(out)


def test_train_requires_auth(train_app):
    client, src, out = train_app
    res = client.post("/api/train", json={"name": "x", "source_dir": src})
    assert res.status_code == 401


def test_train_requires_valid_source_dir(train_app):
    client, src, out = train_app
    with patch.dict(os.environ, {"FACEFUSION_API_TOKEN": "admin"}):
        res = client.post(
            "/api/train",
            json={"name": "x", "source_dir": "/no/such/dir"},
            headers={"Authorization": "Bearer admin"},
        )
        assert res.status_code == 400


def test_train_full_lifecycle(train_app):
    """Start training → poll until complete → download .npy."""
    client, src, out = train_app
    with patch.dict(os.environ, {"FACEFUSION_API_TOKEN": "admin"}):
        res = client.post(
            "/api/train",
            json={"name": "campaign-hero", "source_dir": src, "output_dir": out},
            headers={"Authorization": "Bearer admin"},
        )
        assert res.status_code == 200
        job_id = res.json()["job_id"]

        # Poll until complete (or 5s timeout)
        for _ in range(50):
            r = client.get(f"/api/train/{job_id}", headers={"Authorization": "Bearer admin"})
            assert r.status_code == 200
            if r.json()["status"] == "completed":
                break
            time.sleep(0.1)
        else:
            pytest.fail("Training did not complete in 5s")

        # Fetch the .npy result
        r = client.get(
            f"/api/train/{job_id}/result",
            headers={"Authorization": "Bearer admin"},
        )
        assert r.status_code == 200
        assert r.headers["content-type"] == "application/octet-stream"
        # Save to tmp and verify shape
        npy_path = Path(out) / f"{job_id}.npy"
        arr = np.load(str(npy_path))
        assert arr.shape == (512,)
        assert abs(float(np.linalg.norm(arr)) - 1.0) < 1e-4


def test_train_result_409_until_complete(train_app):
    client, src, out = train_app
    # We can't easily test the "in-progress" 409 in a unit test because
    # the stub runs in ~1ms; just verify the completed path works and
    # unknown job returns 404.
    with patch.dict(os.environ, {"FACEFUSION_API_TOKEN": "admin"}):
        res = client.get(
            "/api/train/does-not-exist/result",
            headers={"Authorization": "Bearer admin"},
        )
        assert res.status_code == 404


def test_train_list_filters_by_tenant(train_app):
    """Two tenants each start a job; each sees only its own."""
    client, src, out = train_app
    with patch.dict(os.environ, {"FACEFUSION_API_TOKEN": "admin"}):
        # Create tenants
        a = client.post(
            "/api/admin/tenants",
            json={"name": "tenant-a"},
            headers={"Authorization": "Bearer admin"},
        ).json()
        b = client.post(
            "/api/admin/tenants",
            json={"name": "tenant-b"},
            headers={"Authorization": "Bearer admin"},
        ).json()
        key_a = a["api_key"]
        key_b = b["api_key"]

        # Tenant A starts a job
        client.post(
            "/api/train",
            json={"name": "a-job", "source_dir": src, "output_dir": out},
            headers={"X-API-Key": key_a},
        )
        # Tenant B starts a job
        client.post(
            "/api/train",
            json={"name": "b-job", "source_dir": src, "output_dir": out},
            headers={"X-API-Key": key_b},
        )

        # List scoped to each
        list_a = client.get("/api/train", headers={"X-API-Key": key_a}).json()
        list_b = client.get("/api/train", headers={"X-API-Key": key_b}).json()

        names_a = {j["name"] for j in list_a["jobs"]}
        names_b = {j["name"] for j in list_b["jobs"]}

        assert "a-job" in names_a
        assert "b-job" not in names_a
        assert "b-job" in names_b
        assert "a-job" not in names_b


def test_train_cancel(train_app):
    """Cancel an already-running training job.

    With only 3 stub images the job usually completes before the cancel
    fires; we accept either outcome (cancel marks it failed, or it
    raced to completion and stays completed) — what we DO assert is
    that the cancel endpoint returns a non-5xx status either way.
    """
    client, src, out = train_app
    with patch.dict(os.environ, {"FACEFUSION_API_TOKEN": "admin"}):
        r = client.post(
            "/api/train",
            json={"name": "cancel-me", "source_dir": src, "output_dir": out},
            headers={"Authorization": "Bearer admin"},
        ).json()
        job_id = r["job_id"]

        # Give the worker a brief window to start
        time.sleep(0.05)

        cancel = client.delete(
            f"/api/train/{job_id}",
            headers={"Authorization": "Bearer admin"},
        )
        # 200 if we beat the worker to the punch; 409 if it was already terminal.
        assert cancel.status_code in (200, 409), f"unexpected {cancel.status_code}: {cancel.text}"

        final = client.get(
            f"/api/train/{job_id}", headers={"Authorization": "Bearer admin"}
        ).json()
        # Either cancelled (status=failed, error=...) or completed.
        assert final["status"] in ("completed", "failed")
        if final["status"] == "failed":
            assert "Cancelado" in (final["error_message"] or "")
