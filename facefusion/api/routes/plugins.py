"""
Admin endpoints for plugin discovery (R11 of gauntlet).

Endpoints:
- GET    /admin/plugins                       — list discovered plugins
- GET    /admin/plugins/{name}                — show one
- POST   /admin/plugins/{name}/disable        — disable (loaded will skip it)
- POST   /admin/plugins/{name}/enable         — re-enable
- POST   /admin/plugins/reload                — re-scan entry points

All endpoints require admin auth (FACEFUSION_API_TOKEN or admin tenant).
"""
from __future__ import annotations

import os
import hmac
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Request

from facefusion.api.plugins import (
    discover_plugins,
    get_plugin,
    disable_plugin,
    enable_plugin,
    reload_discovery,
    load_plugin_class,
)

router = APIRouter()


def _is_admin(request: Request) -> bool:
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


def _require_admin(request: Request) -> None:
    if not _is_admin(request):
        raise HTTPException(
            status_code=403,
            detail="Admin endpoints require the FACEFUSION_API_TOKEN bearer or an admin tenant.",
        )


@router.get("/admin/plugins")
def admin_list_plugins(request: Request, include_disabled: bool = True) -> List[Dict[str, Any]]:
    _require_admin(request)
    return [p.to_dict() for p in discover_plugins(include_disabled=include_disabled)]


@router.get("/admin/plugins/{name}")
def admin_show_plugin(name: str, request: Request) -> Dict[str, Any]:
    _require_admin(request)
    p = get_plugin(name)
    if p is None:
        raise HTTPException(status_code=404, detail="Plugin not found.")
    return p.to_dict()


@router.post("/admin/plugins/{name}/disable")
def admin_disable_plugin(name: str, request: Request) -> Dict[str, Any]:
    _require_admin(request)
    if not disable_plugin(name):
        raise HTTPException(status_code=404, detail="Plugin not found.")
    return {"name": name, "enabled": False}


@router.post("/admin/plugins/{name}/enable")
def admin_enable_plugin(name: str, request: Request) -> Dict[str, Any]:
    _require_admin(request)
    if not enable_plugin(name):
        raise HTTPException(status_code=404, detail="Plugin not found.")
    return {"name": name, "enabled": True}


@router.post("/admin/plugins/reload")
def admin_reload_plugins(request: Request) -> Dict[str, Any]:
    _require_admin(request)
    return reload_discovery()


# Re-export for tests that want to introspect a loaded class
__all__ = ["router", "load_plugin_class"]
