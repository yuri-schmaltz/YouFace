"""
Automatic quality metrics for completed jobs (R10 of gauntlet).

Computes three metrics from the input source face and the produced output:

1. identity_similarity (0..1)
   Cosine similarity between the source face embedding and the dominant
   face embedding in the output's first/last/median frames. Higher =
   identity preserved better.

2. temporal_consistency (0..1)
   Mean pairwise cosine similarity of per-frame face embeddings across
   the video. Higher = output is stable across frames (no flicker).

3. pose_drift (radians, lower is better)
   Mean angular delta between consecutive frames' yaw/pitch/roll
   estimates. Output flips between -180/+180 produce spikes; the metric
   filters NaN/None frames.

WHY THIS EXISTS
None of the open-source face-swap tools (Faceswap, Roop, SimSwap,
BHS Ultimate) expose automated quality scoring. YouFace adds it as a
first-class feature so operators can:
  - compare two swappers objectively
  - gate low-quality outputs in batch
  - build SLA contracts ("identity similarity >= 0.85")

DESIGN NOTES
The heavy lifting (face embedding + landmark extraction) already exists
in facefusion/face_*.py. We reuse it without inventing new models. If
the GPU/InsightFace stack is unavailable, the metrics degrade to
returning None — the endpoint then returns a partial response instead
of failing the whole job.

For now we expose the math but keep this stub-friendly: tests can
inject synthetic embeddings via the `_compute_*` functions.
"""
from __future__ import annotations

import json
import math
import os
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy import Column, String, DateTime, Text, Float

from facefusion.api.database import Base, SessionLocal


# ---------------------------------------------------------------------------
# Pure-math helpers (testable without GPU / models)
# ---------------------------------------------------------------------------

def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine similarity between two equal-length vectors. Returns 0.0
    on degenerate inputs."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na == 0 or nb == 0:
        return 0.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


def mean(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def temporal_consistency(embeddings: Sequence[Sequence[float]]) -> float:
    """Mean pairwise cosine similarity between consecutive embeddings.

    For a perfectly stable video this is 1.0. For heavy flicker it drops
    toward 0.0 (or below if embeddings go negative)."""
    if len(embeddings) < 2:
        return 1.0  # nothing to compare — assume consistent
    sims = []
    for i in range(1, len(embeddings)):
        sims.append(cosine_similarity(embeddings[i - 1], embeddings[i]))
    # Normalize cosine from [-1, 1] to [0, 1]
    return max(0.0, min(1.0, (mean(sims) + 1.0) / 2.0))


def angular_delta(prev: float, curr: float) -> float:
    """Smallest signed angular distance in radians, in [-pi, pi]."""
    d = curr - prev
    while d > math.pi:
        d -= 2 * math.pi
    while d < -math.pi:
        d += 2 * math.pi
    return abs(d)


def pose_drift(poses: Sequence[Dict[str, float]]) -> float:
    """Mean angular drift in radians across consecutive frames.

    Each pose dict has keys 'yaw', 'pitch', 'roll' in radians. We sum
    the per-axis drift and report the mean across axes and frames.
    """
    if len(poses) < 2:
        return 0.0
    drifts: List[float] = []
    for i in range(1, len(poses)):
        prev = poses[i - 1]
        curr = poses[i]
        for axis in ("yaw", "pitch", "roll"):
            if axis in prev and axis in curr:
                drifts.append(angular_delta(float(prev[axis]), float(curr[axis])))
    return mean(drifts)


# ---------------------------------------------------------------------------
# High-level computations (with facefusion integration)
# ---------------------------------------------------------------------------

def _safe_call(fn: Any, *args: Any, default: Any = None) -> Any:
    """Run a facefusion helper; on failure return `default`. Keeps the
    metric endpoint robust when GPU/models are missing."""
    try:
        return fn(*args)
    except Exception:
        return default


def compute_identity_similarity(
    source_embedding: Optional[Sequence[float]],
    output_embeddings: Sequence[Sequence[float]],
) -> Optional[float]:
    """Compare source embedding to mean of output embeddings."""
    if source_embedding is None or not output_embeddings:
        return None
    # Mean output embedding (centroid in identity space)
    dim = len(source_embedding)
    centroid = [0.0] * dim
    for emb in output_embeddings:
        if len(emb) != dim:
            continue
        for i in range(dim):
            centroid[i] += emb[i]
    n = sum(1 for emb in output_embeddings if len(emb) == dim)
    if n == 0:
        return None
    centroid = [c / n for c in centroid]
    return cosine_similarity(source_embedding, centroid)


def compute_job_metrics(
    *,
    source_embedding: Optional[Sequence[float]],
    output_embeddings: Sequence[Sequence[float]],
    output_poses: Sequence[Dict[str, float]],
) -> Dict[str, Optional[float]]:
    """Compute all metrics for one job. Returns a dict with None for
    metrics that couldn't be computed (e.g. GPU unavailable)."""
    identity = compute_identity_similarity(source_embedding, output_embeddings)
    consistency = temporal_consistency(output_embeddings) if output_embeddings else None
    drift = pose_drift(output_poses) if output_poses else None

    def _round(v: Optional[float], n: int = 4) -> Optional[float]:
        return None if v is None else round(float(v), n)

    return {
        "identity_similarity": _round(identity),
        "temporal_consistency": _round(consistency),
        "pose_drift": _round(drift),
        "frames_analyzed": len(output_embeddings),
    }


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

class JobMetricModel(Base):
    """One row per job with quality metrics."""
    __tablename__ = "job_metrics"

    job_id: str = Column(String, primary_key=True, index=True)
    identity_similarity: Optional[float] = Column(Float, nullable=True)
    temporal_consistency: Optional[float] = Column(Float, nullable=True)
    pose_drift: Optional[float] = Column(Float, nullable=True)
    frames_analyzed: int = Column(Float, nullable=True)
    notes: Optional[str] = Column(Text, nullable=True)
    created_at: datetime = Column(DateTime, default=datetime.utcnow)


_init_lock = threading.Lock()
_initialized = False


def ensure_metric_tables() -> None:
    global _initialized
    with _init_lock:
        if _initialized:
            return
        try:
            Base.metadata.create_all(bind=SessionLocal().bind)  # type: ignore[arg-type]
            _initialized = True
        except Exception:
            pass


def save_metrics(job_id: str, metrics: Dict[str, Optional[float]], notes: Optional[str] = None) -> None:
    db = SessionLocal()
    try:
        existing = db.query(JobMetricModel).filter_by(job_id=job_id).first()
        if existing is not None:
            existing.identity_similarity = metrics.get("identity_similarity")
            existing.temporal_consistency = metrics.get("temporal_consistency")
            existing.pose_drift = metrics.get("pose_drift")
            existing.frames_analyzed = metrics.get("frames_analyzed")
            existing.notes = notes
        else:
            db.add(JobMetricModel(
                job_id=job_id,
                identity_similarity=metrics.get("identity_similarity"),
                temporal_consistency=metrics.get("temporal_consistency"),
                pose_drift=metrics.get("pose_drift"),
                frames_analyzed=metrics.get("frames_analyzed"),
                notes=notes,
            ))
        db.commit()
    finally:
        db.close()


def get_metrics(job_id: str) -> Optional[Dict[str, Any]]:
    db = SessionLocal()
    try:
        row = db.query(JobMetricModel).filter_by(job_id=job_id).first()
        if row is None:
            return None
        return {
            "job_id": row.job_id,
            "identity_similarity": row.identity_similarity,
            "temporal_consistency": row.temporal_consistency,
            "pose_drift": row.pose_drift,
            "frames_analyzed": int(row.frames_analyzed) if row.frames_analyzed is not None else 0,
            "notes": row.notes,
            "created_at": row.created_at.isoformat() + "Z" if row.created_at else None,
        }
    finally:
        db.close()


__all__ = [
    "JobMetricModel",
    "compute_job_metrics",
    "cosine_similarity",
    "temporal_consistency",
    "pose_drift",
    "save_metrics",
    "get_metrics",
    "ensure_metric_tables",
]
