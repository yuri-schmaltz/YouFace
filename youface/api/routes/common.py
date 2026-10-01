"""
Shared helpers used by all route submodules.
- get_user_projects_dir: ~/Videos/YouFace_Projects (XDG fallback)
- get_allowed_directories: list of roots where file ops are permitted
- validate_safe_path: LFI mitigation (P1-3 of SWOT)
"""
import os
from typing import List, Optional
from fastapi import HTTPException

from youface import state_manager
from youface.filesystem import get_default_path


def get_user_projects_dir() -> str:
    """Resolve the per-user YouFace projects directory (XDG-aware)."""
    home = os.path.expanduser("~")
    videos_dir = os.path.join(home, "Vídeos")
    if not os.path.exists(videos_dir):
        videos_dir = os.path.join(home, "Videos")
    if not os.path.exists(videos_dir):
        os.makedirs(videos_dir, exist_ok=True)
    projects_dir = os.path.join(videos_dir, "YouFace_Projects")
    os.makedirs(projects_dir, exist_ok=True)
    return os.path.abspath(projects_dir)


def get_allowed_directories() -> List[str]:
    """Return the list of absolute paths where file operations are permitted."""
    jobs_path = state_manager.get_item("jobs_path") or get_default_path('data')
    temp_path = state_manager.get_item("temp_path") or get_default_path('temp')
    cache_path = get_default_path('cache')
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    return [
        os.path.abspath(jobs_path),
        os.path.abspath(temp_path),
        os.path.abspath(cache_path),
        get_user_projects_dir(),
        root_dir,
    ]


def validate_safe_path(target_path: str, allowed_dirs: Optional[List[str]] = None) -> str:
    """
    Ensure `target_path` resolves inside one of `allowed_dirs`.
    Raises HTTPException(400) if not.
    Used by media upload, project, and diagnostic routes to prevent LFI.
    """
    if allowed_dirs is None:
        allowed_dirs = get_allowed_directories()
    abs_target = os.path.abspath(target_path)
    for allowed in allowed_dirs:
        abs_allowed = os.path.abspath(allowed)
        try:
            if os.path.commonpath([abs_target, abs_allowed]) == abs_allowed:
                return abs_target
        except ValueError:
            continue
    raise HTTPException(
        status_code=400,
        detail=f"Acesso negado: o arquivo '{target_path}' reside fora dos diretórios autorizados.",
    )
