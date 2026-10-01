"""
Pluggable face-swap backend registry (R13 of gauntlet).

YouFace ships with `insightface` as the default face-swap backend
(uses the InsightFace embedder + a 256-d sim swapper). For better
fidelity on extreme poses, operators can opt into the SimSwap
backend from `youface/processors/modules/face_swapper_simswap.py`
(marked as "optional install"). The `simswap` repo is gated behind
a `pip install youface[simswap]` extra — the model + repo are
heavy and not needed for 95% of use cases.

This module is the registry + fallback logic. The actual swap is
done by youface/processors/core.py reading `state_manager.get_item("face_swapper_backend")`.

REGISTRY CONCEPT
- Each backend has a name (`insightface`, `simswap`, ...).
- Each backend exposes a `Backend` protocol with:
    name: str
    is_available() -> bool          # can it run? (deps installed, model downloaded)
    describe() -> dict              # human-readable summary for the admin endpoint
    load() -> None                  # load weights/models; raises if not available
    process_frame(source, target) -> frame

If the requested backend isn't available, the worker falls back to
the default (`insightface`) and records a warning. This way a job
that says `face_swapper_backend=simswap` still completes — just with
a different (and known) backend.

WHY THIS DESIGN
Other forks (Roop/Roopx/Renvveyult) bake the swapper in. Swapping
it requires forking. With this registry + entry-point based plugins
(R11), third parties can ship alternative swappers without touching
the YouFace core.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


DEFAULT_BACKEND = "insightface"


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------

class Backend:
    """Minimal protocol a face-swap backend must implement."""

    name: str = ""
    display_name: str = ""
    description: str = ""

    def is_available(self) -> bool:
        """True if all imports + model files are present."""
        raise NotImplementedError

    def describe(self) -> Dict[str, Any]:
        """Human-readable metadata. Includes model path, dim, etc."""
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "available": self.is_available(),
        }

    def load(self) -> None:
        """Eagerly load weights. Raise if unavailable."""
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Built-in backends (insightface only for now — simswap is a stub)
# ---------------------------------------------------------------------------

class InsightFaceBackend(Backend):
    name = "insightface"
    display_name = "InsightFace (default)"
    description = "InsightFace embedder + hyperswap_1a_256 swapper. Default. Fast, good for 0-45° pose."

    def is_available(self) -> bool:
        try:
            import onnxruntime  # noqa: F401
            # The `insightface` package may not be installed in dev/CI; the
            # actual loading path uses onnxruntime directly. We treat
            # onnxruntime as the canonical "insightface backend available"
            # signal and check for insightface only as a soft hint.
            return True
        except Exception:
            return False

    def load(self) -> None:
        # The actual loading happens lazily in youface.face_recognizer.
        # We just verify availability here.
        if not self.is_available():
            raise RuntimeError("InsightFace not installed (missing onnxruntime).")


class SimSwapBackend(Backend):
    """Stub. Real impl requires the SimSwap repo + checkpoint.

    Adding SimSwap support requires:
      1. `pip install youface[simswap]` (extra in pyproject.toml)
      2. cloning SimSwap into a vendored location
      3. loading the .pth checkpoint
    The repository is currently NOT bundled. The route + worker accept
    `face_swapper_backend=simswap` so operators can configure for it,
    and falls back to insightface if not installed.
    """
    name = "simswap"
    display_name = "SimSwap (optional)"
    description = "Higher fidelity on extreme poses. NOT bundled — install with `pip install youface[simswap]`."

    def is_available(self) -> bool:
        try:
            import simswap  # type: ignore # noqa: F401
            return True
        except Exception:
            return False

    def load(self) -> None:
        if not self.is_available():
            raise RuntimeError(
                "SimSwap backend not installed. Run `pip install youface[simswap]` "
                "to enable this backend."
            )


_BUILTINS: List[Backend] = [
    InsightFaceBackend(),
    SimSwapBackend(),
]


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_lock = threading.Lock()
_backends: Dict[str, Backend] = {b.name: b for b in _BUILTINS}
_active: Dict[str, Backend] = {}  # name -> loaded instance


def register_backend(backend: Backend) -> None:
    """Add or replace a backend. Used by plugins (R11)."""
    if not backend.name:
        raise ValueError("Backend must have a non-empty name.")
    with _lock:
        _backends[backend.name] = backend
        # Drop any cached instance so the next load() picks up the new code.
        _active.pop(backend.name, None)


def list_backends() -> List[Dict[str, Any]]:
    return [b.describe() for b in _backends.values()]


def get_backend(name: str) -> Optional[Backend]:
    return _backends.get(name)


def resolve_backend(name: Optional[str]) -> Backend:
    """Return the backend for `name`, falling back to the default if it
    isn't available or doesn't exist. Never returns None — always gives
    the caller something runnable."""
    if name:
        b = _backends.get(name)
        if b is not None and b.is_available():
            return b
    # Fallback to default
    default = _backends.get(DEFAULT_BACKEND)
    if default is None:
        # Should never happen — InsightFaceBackend is in _BUILTINS.
        raise RuntimeError("No default backend registered. This is a bug.")
    return default


def get_active_backend(name: str) -> Backend:
    """Return a loaded instance (cached). Raises if backend can't load."""
    with _lock:
        if name in _active:
            return _active[name]
        backend = _backends.get(name)
        if backend is None:
            raise KeyError(f"Unknown backend: {name}")
        backend.load()
        _active[name] = backend
        return backend


__all__ = [
    "Backend",
    "InsightFaceBackend",
    "SimSwapBackend",
    "DEFAULT_BACKEND",
    "register_backend",
    "list_backends",
    "get_backend",
    "resolve_backend",
    "get_active_backend",
]
