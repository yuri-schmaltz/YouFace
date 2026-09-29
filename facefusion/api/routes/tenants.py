"""
Admin endpoints for multi-tenant management (R7 of gauntlet).

All routes here require the FACEFUSION_API_TOKEN bearer token (admin),
or any admin tenant's X-API-Key. We piggy-back on the existing
BearerAuthMiddleware for the admin path; tenant-scoped callers use
their X-API-Key and are restricted to GETs on their own data.

Endpoints:
- POST   /admin/tenants                       — create tenant (returns raw key ONCE)
- GET    /admin/tenants                       — list tenants
- GET    /admin/tenants/{id}                  — show one tenant + current usage
- POST   /admin/tenants/{id}/rotate           — rotate API key (returns new raw key ONCE)
- POST   /admin/tenants/{id}/disable          — disable tenant
- POST   /admin/tenants/{id}/enable           — re-enable tenant
- POST   /admin/tenants/{id}/quota            — update monthly quota
- DELETE /admin/tenants/{id}                  — remove tenant (soft-delete via disable)
- GET    /admin/usage                         — current caller's usage if tenant-scoped
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from facefusion.api.tenants import (
    DEFAULT_MONTHLY_QUOTA_MINUTES,
    UNLIMITED_QUOTA,
    TenantModel,
    create_tenant,
    disable_tenant,
    enable_tenant,
    get_tenant_by_id,
    get_usage_minutes,
    list_tenants,
    remaining_quota_minutes,
    rotate_tenant_key,
    update_tenant_quota,
    _current_period,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def _is_admin_request(request: Request) -> bool:
    """True iff the caller is the FACEFUSION_API_TOKEN env var (admin) OR
    an admin tenant identified by TenantMiddleware."""
    expected = os.environ.get("FACEFUSION_API_TOKEN")
    if expected:
        auth = request.headers.get("authorization")
        if auth and auth.lower().startswith("bearer "):
            import hmac
            presented = auth[7:].strip()
            if hmac.compare_digest(presented, expected):
                return True
    tenant = getattr(request.state, "tenant", None)
    if tenant is not None and getattr(tenant, "is_admin", False):
        return True
    return False


def _require_admin(request: Request) -> None:
    if not _is_admin_request(request):
        raise HTTPException(
            status_code=403,
            detail="Admin endpoints require the FACEFUSION_API_TOKEN bearer or an admin tenant.",
        )


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class TenantCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    monthly_quota_minutes: int = DEFAULT_MONTHLY_QUOTA_MINUTES
    is_admin: bool = False
    notes: Optional[str] = None


class TenantQuotaUpdate(BaseModel):
    monthly_quota_minutes: int


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/admin/tenants")
def admin_create_tenant(payload: TenantCreate, request: Request) -> Dict[str, Any]:
    _require_admin(request)
    try:
        tenant, raw_key = create_tenant(
            name=payload.name,
            monthly_quota_minutes=payload.monthly_quota_minutes,
            is_admin=payload.is_admin,
            notes=payload.notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return {
        "tenant": tenant.to_dict(include_admin=True),
        "api_key": raw_key,
        "warning": "Store this key now — it cannot be retrieved later.",
    }


@router.get("/admin/tenants")
def admin_list_tenants(request: Request, include_disabled: bool = False) -> List[Dict[str, Any]]:
    _require_admin(request)
    return [t.to_dict(include_admin=True) for t in list_tenants(include_disabled=include_disabled)]


@router.get("/admin/tenants/{tenant_id}")
def admin_show_tenant(tenant_id: str, request: Request) -> Dict[str, Any]:
    _require_admin(request)
    t = get_tenant_by_id(tenant_id)
    if t is None:
        raise HTTPException(status_code=404, detail="Tenant not found.")
    period = _current_period()
    used = get_usage_minutes(t.id, period=period)
    remaining = remaining_quota_minutes(t, period=period)
    out = t.to_dict(include_admin=True)
    out["usage"] = {
        "period": period,
        "minutes_used": used,
        "minutes_remaining": remaining,
    }
    return out


@router.post("/admin/tenants/{tenant_id}/rotate")
def admin_rotate_tenant(tenant_id: str, request: Request) -> Dict[str, Any]:
    _require_admin(request)
    new_key = rotate_tenant_key(tenant_id)
    if new_key is None:
        raise HTTPException(status_code=404, detail="Tenant not found.")
    return {
        "tenant_id": tenant_id,
        "api_key": new_key,
        "warning": "Store this key now — it cannot be retrieved later.",
    }


@router.post("/admin/tenants/{tenant_id}/disable")
def admin_disable_tenant(tenant_id: str, request: Request) -> Dict[str, Any]:
    _require_admin(request)
    if not disable_tenant(tenant_id):
        raise HTTPException(status_code=404, detail="Tenant not found.")
    return {"tenant_id": tenant_id, "enabled": False}


@router.post("/admin/tenants/{tenant_id}/enable")
def admin_enable_tenant(tenant_id: str, request: Request) -> Dict[str, Any]:
    _require_admin(request)
    if not enable_tenant(tenant_id):
        raise HTTPException(status_code=404, detail="Tenant not found.")
    return {"tenant_id": tenant_id, "enabled": True}


@router.post("/admin/tenants/{tenant_id}/quota")
def admin_update_quota(tenant_id: str, payload: TenantQuotaUpdate, request: Request) -> Dict[str, Any]:
    _require_admin(request)
    if payload.monthly_quota_minutes < UNLIMITED_QUOTA:
        raise HTTPException(status_code=422, detail="monthly_quota_minutes must be >= -1 (-1 = unlimited).")
    if not update_tenant_quota(tenant_id, payload.monthly_quota_minutes):
        raise HTTPException(status_code=404, detail="Tenant not found.")
    t = get_tenant_by_id(tenant_id)
    return {"tenant": t.to_dict(include_admin=True) if t else None}


@router.delete("/admin/tenants/{tenant_id}")
def admin_delete_tenant(tenant_id: str, request: Request) -> Dict[str, Any]:
    """Soft-delete: just disables the tenant. Use /admin/tenants/<id>/enable
    to bring it back. (We never hard-delete because the usage ledger is
    referenced from finished jobs.)"""
    _require_admin(request)
    if not disable_tenant(tenant_id):
        raise HTTPException(status_code=404, detail="Tenant not found.")
    return {"tenant_id": tenant_id, "deleted": False, "disabled": True}


@router.get("/admin/usage")
def admin_my_usage(request: Request) -> Dict[str, Any]:
    """Returns the caller's own usage if they're a tenant. Admins see
    their own too (admin tenants are tracked as tenants)."""
    tenant = getattr(request.state, "tenant", None)
    if tenant is None:
        raise HTTPException(status_code=401, detail="This endpoint requires a tenant key or admin token.")
    period = _current_period()
    used = get_usage_minutes(tenant.id, period=period)
    remaining = remaining_quota_minutes(tenant, period=period)
    return {
        "tenant_id": tenant.id,
        "tenant_name": tenant.name,
        "monthly_quota_minutes": tenant.monthly_quota_minutes,
        "period": period,
        "minutes_used": used,
        "minutes_remaining": remaining,
    }
