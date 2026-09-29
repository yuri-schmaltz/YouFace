"""
Endpoint for job quality metrics (R10 of gauntlet).

- GET /jobs/{job_id}/metrics  — return the metrics row, or 404 if not computed yet.

The actual computation runs inside the worker (see facefusion/api/worker.py)
when the job reaches a terminal state. If models are unavailable, the
worker records a row with all-null metrics + a note, and this endpoint
returns that partial data so the consumer knows the job ran but the
scoring failed.
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from facefusion.api.metrics import get_metrics

router = APIRouter()


@router.get("/jobs/{job_id}/metrics")
def job_metrics(job_id: str) -> Dict[str, Any]:
    """Return the quality metrics for a job. 404 if no metrics computed."""
    metrics = get_metrics(job_id)
    if metrics is None:
        raise HTTPException(
            status_code=404,
            detail="No metrics computed for this job (yet, or GPU/models unavailable).",
        )
    return metrics
