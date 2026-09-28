"""
API routes package.

The thick route definitions live in `facefusion/api/_legacy_routes.py`
(pre-R2 monolithic file with 21 routes). This package split extracts
domain-specific submodules from it; for now only `projects` is migrated,
and the rest is re-exported from the legacy module so existing
imports (`from facefusion.api.routes import router`) keep working.

R2 status: 1 of 8 routes extracted (projects). The remaining media,
jobs, diagnostic, preview, video routes are still in _legacy_routes.py.
R2 followups will move them incrementally.

Submodules:
- hardware: GPU/CPU/RAM telemetry and provider enumeration
- config:   system config GET/POST
- common:   internal helpers (validate_safe_path, get_allowed_directories)
- projects: list, create, open-folder, delete  [R2 migrated]
"""
from facefusion.api._legacy_routes import (
    router,
    model_download_state,
    download_thread,
    # Pydantic models re-exported in case tests import them from this path
    DownloadModelsRequest,
    ConfigUpdateRequest,
    JobCreateRequest,
    FaceMapping,
    FaceAnalyzeRequest,
)
# ProjectCreateInput lives in the projects submodule (migrated in R2).
from facefusion.api.routes.projects import ProjectCreateInput

# Re-export sub-routers so callers can mount them individually if needed
from facefusion.api.routes import projects as _projects  # noqa: E402
from facefusion.api.routes import hardware as _hardware  # noqa: E402
from facefusion.api.routes import config as _config  # noqa: E402
from facefusion.api.routes import common as _common  # noqa: E402


# Include sub-routers from migrated submodules into the main `router`.
# The legacy file's own definitions are registered on the SAME router,
# so including here just adds the migrated ones (FastAPI de-dupes by path).
router.include_router(_projects.router)
router.include_router(_hardware.router)
router.include_router(_config.router)


__all__ = [
    "router",
    "model_download_state",
    "download_thread",
    "DownloadModelsRequest",
    "ProjectCreateInput",
    "ConfigUpdateRequest",
    "JobCreateRequest",
    "FaceMapping",
    "FaceAnalyzeRequest",
]
