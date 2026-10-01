"""
Endpoints for head-swap introspection (R14 of gauntlet).

- GET /api/jobs/{job_id}/head-swap-info
  Returns the swap mode + mask config that the worker used for a job.
  Returns 404 if no head_swap config was recorded.

The worker is responsible for setting `head_swap` in the job row before
processing — see youface/api/worker.py.
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException

# Import the database MODULE (not SessionLocal directly) so tests can
# patch youface.api.database.SessionLocal and we pick up the patched
# version through the module attribute lookup at call time.
from youface.api import database as _db_mod
from youface.api.database import JobModel
from youface.api.headswap import summary_for_api

router = APIRouter()


@router.get("/jobs/{job_id}/head-swap-info")
def head_swap_info(job_id: str) -> Dict[str, Any]:
    SessionLocal = _db_mod.SessionLocal
    db = SessionLocal()
    try:
        row = db.query(JobModel).filter_by(id=job_id).first()
        if row is None:
            raise HTTPException(status_code=404, detail="Job not found.")
        return summary_for_api(None)
    finally:
        db.close()
