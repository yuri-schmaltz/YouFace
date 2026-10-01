"""
Training endpoints (R12 of gauntlet).

- POST   /train                          — start a training job (synchronous trigger, async work)
- GET    /train/{id}                     — get job status + progress
- GET    /train/{id}/result              — download the prototype .npy file
- GET    /train                          — list recent training jobs (tenant-scoped)
- DELETE /train/{id}                     — cancel / mark failed

Auth: YOUFACE_API_TOKEN OR any tenant key. The training job is tagged
with the caller's tenant_id when a tenant is identified.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from youface.api.trainer import (
    start_training_job,
    get_train_job,
    list_train_jobs,
    cancel_train_job,
)

router = APIRouter()


def _resolve_tenant_id(request: Request) -> Optional[str]:
    tenant = getattr(request.state, "tenant", None)
    return tenant.id if tenant is not None else None


def _is_admin(request: Request) -> bool:
    import hmac
    expected = os.environ.get("YOUFACE_API_TOKEN")
    if expected:
        auth = request.headers.get("authorization")
        if auth and auth.lower().startswith("bearer "):
            presented = auth[7:].strip()
            if hmac.compare_digest(presented, expected):
                return True
    tenant = getattr(request.state, "tenant", None)
    if tenant is not None and getattr(tenant, "is_admin", False):
        return True
    return False


class TrainCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    source_dir: str = Field(min_length=1)
    output_dir: Optional[str] = None  # defaults to jobs_path/models or similar
    notes: Optional[str] = None


def _default_output_dir() -> str:
    """Resolve the default location for saved prototypes."""
    from youface import state_manager
    from youface.filesystem import get_default_path
    base = state_manager.get_item("jobs_path") or get_default_path("data")
    out = os.path.join(base, "trained")
    os.makedirs(out, exist_ok=True)
    return out


@router.post("/train")
def start_train(payload: TrainCreate, request: Request) -> Dict[str, Any]:
    tenant_id = _resolve_tenant_id(request)
    # Auth gate: require YOUFACE_API_TOKEN OR a tenant key. Without
    # either, refuse the request so anonymous callers can't spawn
    # long-running workers.
    if tenant_id is None and not _is_admin(request):
        raise HTTPException(status_code=401, detail="Authentication required to start training.")
    if not payload.source_dir or not os.path.isdir(payload.source_dir):
        raise HTTPException(status_code=400, detail=f"source_dir is not a directory: {payload.source_dir}")
    output_dir = payload.output_dir or _default_output_dir()
    job_id = start_training_job(
        name=payload.name,
        source_dir=payload.source_dir,
        output_dir=output_dir,
        tenant_id=tenant_id,
        notes=payload.notes,
    )
    return {"job_id": job_id, "status": "queued", "poll_url": f"/api/train/{job_id}"}


@router.get("/train")
def list_train(limit: int = 50, request: Request = None) -> Dict[str, Any]:  # type: ignore[assignment]
    tenant_id = _resolve_tenant_id(request)
    # Admin sees everything; tenants only see their own.
    if _is_admin(request):
        rows = list_train_jobs(tenant_id=None, limit=limit)
    else:
        if tenant_id is None:
            raise HTTPException(status_code=401, detail="Authentication required.")
        rows = list_train_jobs(tenant_id=tenant_id, limit=limit)
    return {"jobs": rows, "count": len(rows)}


@router.get("/train/{job_id}")
def show_train(job_id: str, request: Request) -> Dict[str, Any]:
    job = get_train_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Training job not found.")
    tenant_id = _resolve_tenant_id(request)
    if not _is_admin(request) and job.get("tenant_id") != tenant_id:
        raise HTTPException(status_code=403, detail="Not visible to this caller.")
    return job


@router.get("/train/{job_id}/result")
def get_train_result(job_id: str, request: Request):
    job = get_train_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Training job not found.")
    tenant_id = _resolve_tenant_id(request)
    if not _is_admin(request) and job.get("tenant_id") != tenant_id:
        raise HTTPException(status_code=403, detail="Not visible to this caller.")
    if job["status"] != "completed":
        raise HTTPException(
            status_code=409,
            detail=f"Prototype is not ready yet (status={job['status']}).",
        )
    path = job["output_path"]
    if not os.path.isfile(path):
        raise HTTPException(status_code=410, detail="Prototype file missing on disk.")
    return FileResponse(
        path,
        media_type="application/octet-stream",
        filename=os.path.basename(path),
    )


@router.delete("/train/{job_id}")
def cancel_train(job_id: str, request: Request) -> Dict[str, Any]:
    job = get_train_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Training job not found.")
    tenant_id = _resolve_tenant_id(request)
    if not _is_admin(request) and job.get("tenant_id") != tenant_id:
        raise HTTPException(status_code=403, detail="Not visible to this caller.")
    if not cancel_train_job(job_id):
        raise HTTPException(status_code=409, detail="Job already terminal.")
    return {"job_id": job_id, "status": "failed", "cancelled": True}
