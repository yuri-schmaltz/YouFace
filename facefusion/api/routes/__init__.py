"""
API routes package.

Split into domain-specific submodules for maintainability:
- hardware: GPU/CPU/RAM telemetry and provider enumeration
- config:   system config GET/POST
- media:    upload, output, cleanup, analyze-faces
- projects: list, create, open-folder, delete
- jobs:     create, list, query, cancel, stream (SSE)
- models:   download, status, cancel
- diagnostic: PII-sanitized export zip
- preview:  single-frame preview generation
- video:    video diagnostic wizard
- misc:     internal helpers (validate_safe_path, get_allowed_directories)

The original facefusion/api/routes.py is preserved as a thin re-export
shim so existing tests / imports keep working.
"""
