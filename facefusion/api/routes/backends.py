"""
Endpoint for inspecting face-swap backends (R13 of gauntlet).

- GET /api/backends                 — list registered backends + availability
- GET /api/backends/{name}          — detail for one
- GET /api/backends/{name}/active   — what's currently active for this name
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from facefusion.api.backends import (
    list_backends,
    get_backend,
    get_active_backend,
    resolve_backend,
)

router = APIRouter()


@router.get("/backends")
def all_backends() -> Dict[str, Any]:
    """List all registered backends. Public — read-only metadata."""
    return {
        "backends": list_backends(),
        "default": resolve_backend(None).name,
    }


@router.get("/backends/{name}")
def backend_detail(name: str) -> Dict[str, Any]:
    b = get_backend(name)
    if b is None:
        raise HTTPException(status_code=404, detail=f"Unknown backend: {name}")
    return b.describe()


@router.get("/backends/{name}/active")
def backend_active(name: str) -> Dict[str, Any]:
    """Return the loaded instance metadata. Loads on demand."""
    try:
        b = get_active_backend(name)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    return {
        "name": b.name,
        "loaded": True,
        "available": b.is_available(),
    }
