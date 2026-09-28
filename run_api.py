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
_VENV_DIR = os.path.join(_ROOT, ".venv")


def _venv_python() -> str | None:
    """Return path to the .venv's python executable, or None if absent."""
    candidates = [
        os.path.join(_VENV_DIR, "bin", "python"),
        os.path.join(_VENV_DIR, "bin", "python3"),
        os.path.join(_VENV_DIR, "Scripts", "python.exe"),  # Windows
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None


def _has_required_deps() -> bool:
    """Checagem rápida: cv2 e facefusion.api.main são importáveis?"""
    try:
        import cv2  # noqa: F401
    except ImportError:
        return False
    try:
        from facefusion.api.main import app  # noqa: F401
    except ImportError:
        return False
    return True


def _maybe_relaunch_in_venv() -> None:
    """Se estamos fora do .venv local e ele existe, re-executa dentro dele.

    Estratégia: se sys.prefix != sys.base_prefix, já estamos em algum
    venv (do usuário) e respeitamos. Se sys.prefix == sys.base_prefix
    (system Python) E existe um .venv local com Python, re-executa
    dentro dele via os.execv — independente de as deps estarem no
    system Python. O relaunch deixa o venv decidir se tem deps; se
    não tiver, vai falhar lá com a mensagem específica do venv.
    """
    # Já estamos dentro de algum venv?
    if sys.prefix != getattr(sys, "base_prefix", sys.prefix):
        # Dentro do nosso .venv? ok.
        if os.path.realpath(sys.prefix).startswith(os.path.realpath(_VENV_DIR)):
            return
        # Outro venv (ex.: criado pelo usuário). Respeitamos.
        return

    # Não estamos em venv. Se existe .venv local, re-executa dentro.
    vpy = _venv_python()
    if vpy is None:
        return  # sem venv local — tenta rodar com system Python
    print(f"[API] relaunching inside .venv: {vpy}", flush=True)
    os.execv(vpy, [vpy, os.path.abspath(__file__), *sys.argv[1:]])


# Auto-activate .venv antes de qualquer import pesado
_maybe_relaunch_in_venv()


# Add the workspace root to sys.path for facefusion package import
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


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


from facefusion.app_context import set_app_context  # noqa: E402

set_app_context("cli")

from facefusion import conda  # noqa: E402

conda.setup()

import uvicorn  # noqa: E402

from facefusion.api.main import app, find_free_port, write_frontend_config  # noqa: E402

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
