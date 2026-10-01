"""
Plugin marketplace support (R11 of gauntlet).

YouFace exposes a Python entry-point group `youface.processors` so
third parties can publish `pip install youface-processor-X` packages
without touching this repo. A plugin is just a class that subclasses
the same contract as the built-in processors.

This module:
- Discovers installed plugins via importlib.metadata.entry_points
- Provides a runtime registry (with enable/disable toggle) so admins
  can shadow a plugin without uninstalling it
- Exposes API endpoints to list / enable / disable / reload

NOTE: The actual processor wiring (passing source/target frames) is
done inside youface/processors/core.py. A plugin only needs to
expose `process_frame(...)` — same signature as the built-ins. We
introspect this at load time to give admins a useful summary.

DISABLED PLUGIN STATE
Stored in a tiny JSON file (youface/api/plugins.json by default)
rather than in SQLite — it has to be readable before the DB is up,
and we want admins to be able to inspect it directly.
"""
from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

import importlib.metadata


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

#: Entry-point group name. Plugin packages declare their processors here.
ENTRY_POINT_GROUP = "youface.processors"

#: Default state file path (relative to the api package).
DEFAULT_STATE_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "plugins.json"
)


# ---------------------------------------------------------------------------
# Plugin dataclass
# ---------------------------------------------------------------------------

@dataclass
class PluginInfo:
    """Public representation of a discovered plugin."""
    name: str
    distribution: str
    version: str
    enabled: bool
    summary: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# State (enable/disable file)
# ---------------------------------------------------------------------------

_lock = threading.Lock()
_state_cache: Optional[Dict[str, bool]] = None


def _load_state() -> Dict[str, bool]:
    """Read the disabled-set from disk. Missing file → empty set (all enabled)."""
    global _state_cache
    with _lock:
        if _state_cache is not None:
            return _state_cache
        if not os.path.exists(DEFAULT_STATE_FILE):
            _state_cache = {}
            return _state_cache
        try:
            with open(DEFAULT_STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Schema: {"disabled": ["name1", "name2"]}
            disabled = set(data.get("disabled", []))
            _state_cache = {name: False for name in disabled}
        except Exception:
            _state_cache = {}
        return _state_cache


def _save_state() -> None:
    with _lock:
        if _state_cache is None:
            return
        disabled = sorted(name for name, enabled in _state_cache.items() if not enabled)
        tmp = DEFAULT_STATE_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"disabled": disabled}, f, indent=2)
        os.replace(tmp, DEFAULT_STATE_FILE)


def _invalidate_cache() -> None:
    global _state_cache
    with _lock:
        _state_cache = None


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

def discover_plugins(include_disabled: bool = False) -> List[PluginInfo]:
    """Find all plugins via entry_points.

    Returns a list of PluginInfo. If include_disabled is False, only
    enabled plugins are returned.
    """
    state = _load_state()
    out: List[PluginInfo] = []
    try:
        eps = importlib.metadata.entry_points()
        # Python 3.10+ has select(group=...) but the older .get() works everywhere
        try:
            group_eps = eps.select(group=ENTRY_POINT_GROUP)
        except AttributeError:  # pragma: no cover — Python < 3.10 fallback
            group_eps = eps.get(ENTRY_POINT_GROUP, [])  # type: ignore[union-attr]
        for ep in group_eps:
            try:
                dist = ep.dist
                dist_name = dist.name if dist else "unknown"
                dist_version = dist.version if dist else "0.0.0"
            except Exception:
                dist_name = "unknown"
                dist_version = "0.0.0"
            enabled = state.get(ep.name, True)
            if not include_disabled and not enabled:
                continue
            summary: Optional[str] = None
            try:
                loaded = ep.load()
                summary = (loaded.__doc__ or "").strip().splitlines()[0] if loaded.__doc__ else None
            except Exception as e:
                summary = f"failed to load: {e}"
            out.append(PluginInfo(
                name=ep.name,
                distribution=dist_name,
                version=dist_version,
                enabled=enabled,
                summary=summary,
            ))
    except Exception as e:
        # Discovery failure shouldn't break the API; return what we have
        return out
    return out


def get_plugin(name: str) -> Optional[PluginInfo]:
    for p in discover_plugins(include_disabled=True):
        if p.name == name:
            return p
    return None


def load_plugin_class(name: str) -> Optional[Any]:
    """Resolve a plugin entry point to its actual class. Returns None if
    the plugin is disabled or doesn't exist."""
    state = _load_state()
    if state.get(name, True) is False:
        return None
    try:
        eps = importlib.metadata.entry_points()
        try:
            group_eps = eps.select(group=ENTRY_POINT_GROUP)
        except AttributeError:  # pragma: no cover
            group_eps = eps.get(ENTRY_POINT_GROUP, [])  # type: ignore[union-attr]
        for ep in group_eps:
            if ep.name == name:
                return ep.load()
    except Exception:
        return None
    return None


def disable_plugin(name: str) -> bool:
    state = _load_state()
    if get_plugin(name) is None:
        return False
    state[name] = False
    _save_state()
    return True


def enable_plugin(name: str) -> bool:
    state = _load_state()
    if get_plugin(name) is None:
        return False
    state[name] = True
    _save_state()
    return True


def reload_discovery() -> Dict[str, Any]:
    """Force re-scan of installed entry points. Useful after `pip install`."""
    _invalidate_cache()
    plugins = discover_plugins(include_disabled=True)
    return {
        "reloaded": True,
        "found": len(plugins),
        "enabled": sum(1 for p in plugins if p.enabled),
        "disabled": sum(1 for p in plugins if not p.enabled),
    }


__all__ = [
    "PluginInfo",
    "ENTRY_POINT_GROUP",
    "discover_plugins",
    "get_plugin",
    "load_plugin_class",
    "disable_plugin",
    "enable_plugin",
    "reload_discovery",
]
