"""
Run the YouFace API + frontend cockpit.

Auto-detects a project-local .venv (created by the smart installer) and
re-launches inside it if the current Python doesn't have the required
deps. This way 'python run_api.py' works regardless of which interpreter
the user invokes it with.

Usage:
    python run_api.py                # auto-picks venv if present
    .venv/bin/python run_api.py     # explicit venv invocation

The startup script prints the URL of the cockpit (e.g.
http://127.0.0.1:8000) on stdout.
"""
import os
import sys


_ROOT = os.path.dirname(os.path.abspath(__file__))

# Auto-activate o .venv local antes de qualquer import pesado.
# A lógica de detecção/relaunch vive em scripts/youface_venv.py para ser
# compartilhada com outros entry-points (youface.py, ferramentas CLI).
sys.path.insert(0, os.path.join(_ROOT, "scripts"))
from youface_venv import maybe_relaunch_in_venv  # noqa: E402

maybe_relaunch_in_venv(_ROOT)


# Add the workspace root to sys.path for youface package import
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


def _has_required_deps() -> bool:
    """Checagem rápida: cv2 e youface.api.main são importáveis?"""
    try:
        import cv2  # noqa: F401
    except ImportError:
        return False
    try:
        from youface.api.main import app  # noqa: F401
    except ImportError:
        return False
    return True


# Eagerly probe deps again after potential relaunch — fail fast with a
# helpful message if something is still missing.
if not _has_required_deps():
    print(
        "[API] FATAL: dependências não encontradas no Python ativo.\n"
        "Rode: python install.py --auto --use-venv --yes\n"
        "Depois: python run_api.py (ou source .venv/bin/activate && python run_api.py)",
        flush=True,
    )
    sys.exit(1)


from youface.app_context import set_app_context  # noqa: E402

set_app_context("cli")

from youface import conda  # noqa: E402

conda.setup()

import uvicorn  # noqa: E402

from youface.api.main import app, find_free_port, write_frontend_config  # noqa: E402

if __name__ == "__main__":
    host = "127.0.0.1"
    try:
        port = find_free_port(8000)
    except Exception:
        port = 8000

    write_frontend_config(port)
    print(f"[API] starting uvicorn on {host}:{port}", flush=True)
    # Use app object directly instead of string import to avoid reload/import
    # issues in PyInstaller.
    uvicorn.run(app, host=host, port=port)
