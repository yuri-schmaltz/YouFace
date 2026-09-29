"""
Endpoints for managing job presets / recipes (R9 of gauntlet).

All endpoints require the FACEFUSION_API_TOKEN bearer OR a valid tenant
key (X-API-Key or Authorization: Bearer). Tenants can only see their
own presets + presets that were explicitly marked `shared: true`.

Endpoints:
- GET    /presets                          — list visible presets (filter by ?name=)
- POST   /presets                          — create a preset
- GET    /presets/{id}                     — show one
- PUT    /presets/{id}                     — update name/description/data/shared
- DELETE /presets/{id}                     — delete
- POST   /presets/{id}/apply               — returns merged data ready for /api/jobs
                                              (does NOT create a job — keeps responsibility
                                              with the caller so they can add source/target)
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from facefusion.api.presets import (
    PresetCreate,
    PresetUpdate,
    create_preset,
    get_preset,
    list_presets,
    update_preset,
    delete_preset,
    merge_for_apply,
)

router = APIRouter()


def _resolve_tenant_id(request: Request) -> Optional[str]:
    tenant = getattr(request.state, "tenant", None)
    return tenant.id if tenant is not None else None


def _is_admin(request: Request) -> bool:
    import os, hmac
    expected = os.environ.get("FACEFUSION_API_TOKEN")
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


@router.get("/presets")
def list_visible_presets(request: Request, name: Optional[str] = None) -> Dict[str, Any]:
    tenant_id = _resolve_tenant_id(request)
    if tenant_id is None and not _is_admin(request):
        raise HTTPException(status_code=401, detail="Authentication required to list presets.")
    presets = list_presets(owner_tenant_id=tenant_id, name_filter=name)
    return {"presets": [p.to_dict() for p in presets], "count": len(presets)}


@router.post("/presets")
def create_new_preset(payload: PresetCreate, request: Request) -> Dict[str, Any]:
    tenant_id = _resolve_tenant_id(request)
    is_admin = _is_admin(request)
    # `shared` is admin-only — non-admin tenants cannot make their preset
    # visible to other tenants.
    shared = payload.shared and is_admin
    try:
        preset = create_preset(
            name=payload.name,
            description=payload.description,
            data=payload.data.model_dump(exclude_none=True),
            owner_tenant_id=tenant_id,
            shared=shared,
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return preset.to_dict()


@router.get("/presets/{preset_id}")
def show_preset(preset_id: str, request: Request) -> Dict[str, Any]:
    preset = get_preset(preset_id)
    if preset is None:
        raise HTTPException(status_code=404, detail="Preset not found.")
    tenant_id = _resolve_tenant_id(request)
    if not _is_admin(request) and preset.owner_tenant_id != tenant_id and not preset.shared:
        raise HTTPException(status_code=403, detail="Preset is not visible to this caller.")
    return preset.to_dict()


@router.put("/presets/{preset_id}")
def update_existing_preset(preset_id: str, payload: PresetUpdate, request: Request) -> Dict[str, Any]:
    preset = get_preset(preset_id)
    if preset is None:
        raise HTTPException(status_code=404, detail="Preset not found.")
    tenant_id = _resolve_tenant_id(request)
    if not _is_admin(request) and preset.owner_tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="Only the owner can update this preset.")
    new_data = payload.data.model_dump(exclude_none=True) if payload.data is not None else None
    # shared remains admin-only
    updated = update_preset(
        preset_id,
        name=payload.name,
        description=payload.description,
        data=new_data,
        shared=(payload.data is not None and _is_admin(request)) or None,
    )
    return updated.to_dict() if updated else {}


@router.delete("/presets/{preset_id}")
def remove_preset(preset_id: str, request: Request) -> Dict[str, Any]:
    preset = get_preset(preset_id)
    if preset is None:
        raise HTTPException(status_code=404, detail="Preset not found.")
    tenant_id = _resolve_tenant_id(request)
    if not _is_admin(request) and preset.owner_tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="Only the owner can delete this preset.")
    delete_preset(preset_id)
    return {"deleted": True, "id": preset_id}


class PresetApplyRequest(BaseModel):
    overrides: Optional[Dict[str, Any]] = None


@router.post("/presets/{preset_id}/apply")
def apply_preset(preset_id: str, payload: PresetApplyRequest, request: Request) -> Dict[str, Any]:
    """Returns the merged (preset + overrides) data ready for POST /api/jobs.
    Does NOT create the job — the caller is expected to add source/target
    paths and POST to /api/jobs with the returned data."""
    preset = get_preset(preset_id)
    if preset is None:
        raise HTTPException(status_code=404, detail="Preset not found.")
    tenant_id = _resolve_tenant_id(request)
    if not _is_admin(request) and preset.owner_tenant_id != tenant_id and not preset.shared:
        raise HTTPException(status_code=403, detail="Preset is not visible to this caller.")
    merged = merge_for_apply(preset, payload.overrides)
    return {
        "preset_id": preset_id,
        "merged": merged,
        "ready_for_job_create": True,
    }
