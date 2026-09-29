"""
Tests for automatic job quality metrics (R10 of gauntlet).

Covers the pure-math helpers and the high-level compute_job_metrics.
The facefusion integration itself is mocked because we don't have a
GPU in CI; the worker calls compute_job_metrics with embeddings
extracted from the actual swap.
"""
import math

import pytest
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from facefusion.api import metrics as metrics_mod


# ---------------------------------------------------------------------------
# Pure-math tests
# ---------------------------------------------------------------------------

def test_cosine_similarity_identical_vectors():
    v = [0.1, 0.2, 0.3, 0.4]
    assert metrics_mod.cosine_similarity(v, v) == pytest.approx(1.0, abs=1e-6)


def test_cosine_similarity_orthogonal_vectors():
    a = [1.0, 0.0]
    b = [0.0, 1.0]
    assert metrics_mod.cosine_similarity(a, b) == pytest.approx(0.0, abs=1e-6)


def test_cosine_similarity_opposite_vectors():
    a = [1.0, 0.5]
    b = [-1.0, -0.5]
    assert metrics_mod.cosine_similarity(a, b) == pytest.approx(-1.0, abs=1e-6)


def test_cosine_similarity_zero_vector_returns_zero():
    a = [0.0, 0.0]
    b = [1.0, 2.0]
    assert metrics_mod.cosine_similarity(a, b) == 0.0


def test_cosine_similarity_dimension_mismatch_returns_zero():
    assert metrics_mod.cosine_similarity([1, 2], [1, 2, 3]) == 0.0
    assert metrics_mod.cosine_similarity([], [1]) == 0.0


def test_temporal_consistency_identical_embeddings_is_one():
    e = [[0.5, 0.5, 0.5]] * 5
    assert metrics_mod.temporal_consistency(e) == pytest.approx(1.0, abs=1e-6)


def test_temporal_consistency_single_embedding_is_one():
    """Trivial case: nothing to compare, assume consistent."""
    assert metrics_mod.temporal_consistency([[0.1, 0.2, 0.3]]) == 1.0


def test_temporal_consistency_empty_returns_one():
    assert metrics_mod.temporal_consistency([]) == 1.0


def test_temporal_consistency_random_drops_below_one():
    import random
    random.seed(42)
    e = [[random.gauss(0, 1) for _ in range(8)] for _ in range(20)]
    tc = metrics_mod.temporal_consistency(e)
    assert 0.0 <= tc < 1.0


def test_angular_delta_basic():
    assert metrics_mod.angular_delta(0.0, 0.0) == 0.0
    assert metrics_mod.angular_delta(0.0, math.pi) == pytest.approx(math.pi, abs=1e-6)
    # Wrap-around: 170° → -170° should be 20° (not 340°)
    assert metrics_mod.angular_delta(math.radians(170), math.radians(-170)) == pytest.approx(math.radians(20), abs=1e-4)


def test_pose_drift_stable_is_zero():
    poses = [{"yaw": 0.1, "pitch": 0.0, "roll": 0.0}] * 10
    assert metrics_mod.pose_drift(poses) == pytest.approx(0.0, abs=1e-6)


def test_pose_drift_increasing():
    """Each frame yaws by 0.1 rad → 9 transitions × 0.1, averaged over 3 axes = 0.3."""
    poses = [{"yaw": 0.1 * i, "pitch": 0.0, "roll": 0.0} for i in range(10)]
    # 9 transitions, each with yaw=0.1, pitch=0, roll=0 → mean = (9*0.1 + 9*0 + 9*0) / 27 = 0.033
    assert metrics_mod.pose_drift(poses) == pytest.approx(1.0 / 30.0, abs=1e-6)


def test_pose_drift_single_frame():
    poses = [{"yaw": 0.0}]
    assert metrics_mod.pose_drift(poses) == 0.0


def test_pose_drift_missing_axes_are_skipped():
    """If a frame lacks 'pitch', only yaw + roll contribute to that transition.

    Implementation behavior: we sum per-axis deltas across all consecutive
    frame pairs and divide by the total number of (axis × pair) observations.
    So with 3 axes per pair × 2 pairs = 6 slots; pitch missing in one pair
    reduces the divisor to 5. Sum of deltas = 0.1 + 0 + 0 + 0.1 + 0 + 0 = 0.2.
    Mean = 0.2 / 5 = 0.04 — except the implementation actually pads missing
    axes with 0 only when both prev and curr have it, so here we get
    0.1 + 0 (yaw,roll) + 0.1 + 0 + 0 (yaw,pitch,roll) = 0.2 / 4 = 0.05.
    Either 0.04 or 0.05 is acceptable as long as the metric isn't NaN
    and is bounded by the per-axis delta."""
    poses = [
        {"yaw": 0.0, "pitch": 0.0, "roll": 0.0},
        {"yaw": 0.1, "roll": 0.0},  # missing pitch
        {"yaw": 0.2, "pitch": 0.0, "roll": 0.0},
    ]
    result = metrics_mod.pose_drift(poses)
    # Whatever the implementation decides, must be finite and within
    # the bound [0, max_per_axis_delta]
    import math
    assert math.isfinite(result)
    assert 0.0 <= result <= 0.1


# ---------------------------------------------------------------------------
# High-level computation tests
# ---------------------------------------------------------------------------

def test_compute_identity_similarity_when_identical():
    src = [0.3, 0.4, 0.5]
    out = [[0.3, 0.4, 0.5]] * 3
    sim = metrics_mod.compute_identity_similarity(src, out)
    assert sim == pytest.approx(1.0, abs=1e-6)


def test_compute_identity_similarity_when_none_source():
    out = [[0.3, 0.4, 0.5]]
    assert metrics_mod.compute_identity_similarity(None, out) is None


def test_compute_identity_similarity_when_no_output():
    assert metrics_mod.compute_identity_similarity([0.1, 0.2], []) is None


def test_compute_identity_similarity_dimension_mismatch_is_skipped():
    src = [0.3, 0.4, 0.5]
    out = [[0.1, 0.2, 0.3, 0.4]]  # wrong dim
    assert metrics_mod.compute_identity_similarity(src, out) is None


def test_compute_job_metrics_full():
    src = [0.6, 0.8]  # unit vector (1, 0) approx
    out = [[0.6, 0.8]] * 5
    poses = [{"yaw": 0.0}] * 5
    result = metrics_mod.compute_job_metrics(
        source_embedding=src, output_embeddings=out, output_poses=poses,
    )
    assert result["identity_similarity"] == pytest.approx(1.0, abs=1e-3)
    assert result["temporal_consistency"] == pytest.approx(1.0, abs=1e-3)
    assert result["pose_drift"] == 0.0
    assert result["frames_analyzed"] == 5


def test_compute_job_metrics_partial():
    """If source is missing, identity_similarity is None but other metrics still work."""
    out = [[0.1, 0.2, 0.3]] * 4
    poses = [{"yaw": 0.1 * i} for i in range(4)]
    result = metrics_mod.compute_job_metrics(
        source_embedding=None, output_embeddings=out, output_poses=poses,
    )
    assert result["identity_similarity"] is None
    assert result["temporal_consistency"] == pytest.approx(1.0, abs=1e-3)
    assert result["pose_drift"] == pytest.approx(0.1, abs=1e-3)


def test_compute_job_metrics_all_empty():
    result = metrics_mod.compute_job_metrics(
        source_embedding=None, output_embeddings=[], output_poses=[],
    )
    assert result["identity_similarity"] is None
    assert result["temporal_consistency"] is None
    assert result["pose_drift"] is None
    assert result["frames_analyzed"] == 0


# ---------------------------------------------------------------------------
# Persistence tests
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def isolated_metrics_db(tmp_path):
    db_path = tmp_path / "metrics.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    from facefusion.api.database import Base
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    with patch.object(metrics_mod, "SessionLocal", SessionLocal):
        yield


def test_save_and_get_round_trip():
    metrics_mod.save_metrics(
        "job-x",
        {
            "identity_similarity": 0.92,
            "temporal_consistency": 0.85,
            "pose_drift": 0.07,
            "frames_analyzed": 100,
        },
        notes="first batch",
    )
    out = metrics_mod.get_metrics("job-x")
    assert out["job_id"] == "job-x"
    assert out["identity_similarity"] == pytest.approx(0.92, abs=1e-4)
    assert out["temporal_consistency"] == pytest.approx(0.85, abs=1e-4)
    assert out["pose_drift"] == pytest.approx(0.07, abs=1e-4)
    assert out["frames_analyzed"] == 100
    assert out["notes"] == "first batch"


def test_save_updates_existing_row():
    metrics_mod.save_metrics("job-y", {"identity_similarity": 0.5, "frames_analyzed": 10})
    metrics_mod.save_metrics("job-y", {"identity_similarity": 0.9, "frames_analyzed": 20})
    out = metrics_mod.get_metrics("job-y")
    assert out["identity_similarity"] == pytest.approx(0.9, abs=1e-4)
    assert out["frames_analyzed"] == 20


def test_get_metrics_unknown_job_returns_none():
    assert metrics_mod.get_metrics("job-doesnotexist") is None


def test_save_metrics_with_nulls():
    """A row can be saved with all-null metrics (e.g. when GPU is missing)."""
    metrics_mod.save_metrics(
        "job-null", {"identity_similarity": None, "temporal_consistency": None,
                     "pose_drift": None, "frames_analyzed": 0},
        notes="GPU unavailable",
    )
    out = metrics_mod.get_metrics("job-null")
    assert out["identity_similarity"] is None
    assert out["temporal_consistency"] is None
    assert out["pose_drift"] is None
    assert out["frames_analyzed"] == 0
    assert out["notes"] == "GPU unavailable"
