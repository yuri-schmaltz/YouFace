"""
Shared helper: re-exec an entry-point script inside the project-local
``.venv`` (created by ``install.py``) when invoked from system Python.

Why
---
``install.py --use-venv`` installs all deps into ``./.venv``. After that,
``python run_api.py`` already auto-detects and re-launches inside the venv.
This helper centralizes the same behavior so any entry-point script
(``run_api.py``, ``youface.py``, future tooling) can opt in with two lines
and stay consistent.

Strategy
--------
1. If the current Python is inside ANY virtualenv (project's ``.venv`` or a
   user-activated one) → no-op. We respect the user's choice.
2. If we're on system Python AND ``<project_root>/.venv/bin/python`` (or
   ``Scripts/python.exe`` on Windows) exists → ``os.execv`` into it with the
   same argv. After exec, the rest of the entry-point runs inside the venv.
3. Otherwise (system Python, no local venv) → no-op. The caller will fail
   with the natural ``ModuleNotFoundError``, which is the right diagnostic.

Usage from an entry-point script at the project root::

    import os
    import sys

    _ROOT = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, os.path.join(_ROOT, "scripts"))
    from youface_venv import maybe_relaunch_in_venv
    maybe_relaunch_in_venv(_ROOT)
"""
from __future__ import annotations

import os
import sys
from typing import Optional


def venv_python(project_root: str) -> Optional[str]:
    """Return absolute path to the project ``.venv`` Python, or ``None``.

    Checks POSIX (``bin/python``, ``bin/python3``) and Windows
    (``Scripts/python.exe``) layouts. Returns the first one that exists.
    """
    venv_dir = os.path.join(project_root, ".venv")
    candidates = (
        os.path.join(venv_dir, "bin", "python"),
        os.path.join(venv_dir, "bin", "python3"),
        os.path.join(venv_dir, "Scripts", "python.exe"),  # Windows
    )
    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate
    return None


def in_any_venv() -> bool:
    """True if running inside any virtualenv.

    Uses the standard ``sys.prefix != sys.base_prefix`` heuristic, which
    holds for stdlib ``venv``, ``virtualenv``, ``uv``, ``conda`` (non-base
    envs), and ``pipenv`` shells.
    """
    return sys.prefix != getattr(sys, "base_prefix", sys.prefix)


def maybe_relaunch_in_venv(project_root: str) -> None:
    """Re-exec the current entry-point inside ``<project_root>/.venv``.

    No-op when:
      * already inside any virtualenv (we respect the user's choice), or
      * system Python with no local ``.venv`` present (let the natural
        ``ModuleNotFoundError`` surface so the user knows to install).

    Otherwise calls ``os.execv`` with the venv's Python, the absolute path
    of the entry-point (``sys.argv[0]``), and the rest of ``sys.argv``.
    ``os.execv`` does not return on success.
    """
    if in_any_venv():
        return

    vpy = venv_python(project_root)
    if vpy is None:
        return

    script_path = os.path.abspath(sys.argv[0])
    print(f"[relaunch] entering project .venv: {vpy}", flush=True)
    os.execv(vpy, [vpy, script_path, *sys.argv[1:]])