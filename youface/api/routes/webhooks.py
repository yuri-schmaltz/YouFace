"""
Admin endpoints for inspecting webhook deliveries (R8 of gauntlet).

These don't trigger deliveries — they let operators see what happened
with the deliveries the worker dispatched. Useful for debugging "why
didn't my n8n workflow fire?" without scraping logs.

Endpoints:
- GET /admin/webhooks                 — list recent deliveries (filter by ?job_id, ?status)
- GET /admin/webhooks/failed          — convenience: list deliveries with status=failed
- GET /admin/webhooks/{delivery_id}   — show one delivery
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request, Query

from youface.api.webhooks import list_deliveries

router = APIRouter()


def _is_admin(request: Request) -> bool:
    import os
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


def _require_admin(request: Request) -> None:
    if not _is_admin(request):
        raise HTTPException(
            status_code=403,
            detail="Admin endpoints require the YOUFACE_API_TOKEN bearer or an admin tenant.",
        )


@router.get("/admin/webhooks")
def admin_list_webhooks(
    request: Request,
    job_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None, pattern="^(pending|delivered|failed)$"),
    limit: int = Query(50, ge=1, le=500),
) -> List[Dict[str, Any]]:
    _require_admin(request)
    return list_deliveries(job_id=job_id, status=status, limit=limit)


@router.get("/admin/webhooks/failed")
def admin_list_failed_webhooks(request: Request, limit: int = Query(50, ge=1, le=500)) -> List[Dict[str, Any]]:
    _require_admin(request)
    return list_deliveries(status="failed", limit=limit)


@router.get("/admin/webhooks/{delivery_id}")
def admin_show_webhook(delivery_id: str, request: Request) -> Dict[str, Any]:
    _require_admin(request)
    rows = list_deliveries(limit=10000)  # small table expected; OK for now
    for r in rows:
        if r["id"] == delivery_id:
            return r
    raise HTTPException(status_code=404, detail="Delivery not found.")
