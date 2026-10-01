"""
Tests for plugin marketplace support (R11 of gauntlet).

We test by constructing fake distributions on-the-fly via Python's
metadata API. The plugin module reads from importlib.metadata so
patching the entry_points() result is the cleanest way to inject
fake plugins without installing actual packages.
"""
import json
import os
import sys
import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest

from youface.api import plugins as plugins_mod
from youface.api.routes import plugins as plugin_routes


# ---------------------------------------------------------------------------
# Fake entry-point fixtures
# ---------------------------------------------------------------------------

class _FakeEntryPoint:
    def __init__(self, name, target, dist_name="fake-dist", dist_version="1.0.0",
                 load_error=None, docstring="A test plugin"):
        self.name = name
        self._target = target
        self._dist_name = dist_name
        self._dist_version = dist_version
        self._load_error = load_error
        self._docstring = docstring

    def load(self):
        if self._load_error:
            raise self._load_error
        # Return a fake class with a __doc__ so the summary line works
        ns = {"__doc__": self._docstring}
        return type(self._target, (), ns)

    @property
    def dist(self):
        d = _FakeDistribution(self._dist_name, self._dist_version)
        return d


class _FakeDistribution:
    def __init__(self, name, version):
        self.name = name
        self.version = version


class _FakeEntryPoints:
    """Mimics importlib.metadata.EntryPoints.select / __iter__."""

    def __init__(self, eps):
        self._eps = eps

    def select(self, *, group):
        return [ep for ep in self._eps if ep._group == group]

    def __iter__(self):
        return iter(self._eps)


def _make_ep(name, group, target="FakeProcessor", **kwargs):
    ep = _FakeEntryPoint(name, target, **kwargs)
    ep._group = group
    return ep


# ---------------------------------------------------------------------------
# Per-test fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def isolated_plugins(tmp_path, monkeypatch):
    """Reset the cached state + redirect state file to a temp path."""
    plugins_mod._invalidate_cache()
    fake_state = tmp_path / "plugins.json"
    monkeypatch.setattr(plugins_mod, "DEFAULT_STATE_FILE", str(fake_state))
    # Clear cache again because we patched the constant after a previous load
    plugins_mod._invalidate_cache()
    yield
    plugins_mod._invalidate_cache()


def _stub_entry_points(*eps):
    return _FakeEntryPoints(list(eps))


# ---------------------------------------------------------------------------
# Pure discovery tests
# ---------------------------------------------------------------------------

def test_discover_returns_empty_when_no_plugins():
    with patch.object(plugins_mod.importlib.metadata, "entry_points",
                      return_value=_stub_entry_points()):
        result = plugins_mod.discover_plugins()
    assert result == []


def test_discover_returns_plugin_metadata():
    eps = _stub_entry_points(
        _make_ep("my_proc", plugins_mod.ENTRY_POINT_GROUP,
                 target="MyProc", dist_name="acme-youface",
                 dist_version="2.3.4", docstring="Acme plugin."),
    )
    with patch.object(plugins_mod.importlib.metadata, "entry_points",
                      return_value=eps):
        result = plugins_mod.discover_plugins()

    assert len(result) == 1
    p = result[0]
    assert p.name == "my_proc"
    assert p.distribution == "acme-youface"
    assert p.version == "2.3.4"
    assert p.enabled is True
    assert "Acme plugin" in (p.summary or "")


def test_discover_skips_other_groups():
    """Entry points in other groups must be ignored."""
    eps = _stub_entry_points(
        _make_ep("a", "some.other.group"),
        _make_ep("b", plugins_mod.ENTRY_POINT_GROUP),
    )
    with patch.object(plugins_mod.importlib.metadata, "entry_points",
                      return_value=eps):
        result = plugins_mod.discover_plugins()
    assert [p.name for p in result] == ["b"]


def test_disable_marks_plugin_disabled():
    eps = _stub_entry_points(
        _make_ep("p1", plugins_mod.ENTRY_POINT_GROUP),
        _make_ep("p2", plugins_mod.ENTRY_POINT_GROUP),
    )
    with patch.object(plugins_mod.importlib.metadata, "entry_points",
                      return_value=eps):
        assert plugins_mod.disable_plugin("p1") is True
        # After disable, default discover excludes it
        visible = plugins_mod.discover_plugins(include_disabled=False)
        names = {p.name for p in visible}
        assert names == {"p2"}

        # But include_disabled=True still shows it (with enabled=False)
        all_visible = plugins_mod.discover_plugins(include_disabled=True)
        all_map = {p.name: p.enabled for p in all_visible}
        assert all_map == {"p1": False, "p2": True}


def test_enable_restores_plugin():
    eps = _stub_entry_points(_make_ep("p1", plugins_mod.ENTRY_POINT_GROUP))
    with patch.object(plugins_mod.importlib.metadata, "entry_points",
                      return_value=eps):
        plugins_mod.disable_plugin("p1")
        assert plugins_mod.enable_plugin("p1") is True
        visible = plugins_mod.discover_plugins(include_disabled=False)
        assert [p.name for p in visible] == ["p1"]


def test_disable_unknown_returns_false():
    eps = _stub_entry_points(_make_ep("p1", plugins_mod.ENTRY_POINT_GROUP))
    with patch.object(plugins_mod.importlib.metadata, "entry_points",
                      return_value=eps):
        assert plugins_mod.disable_plugin("doesnotexist") is False


def test_enable_unknown_returns_false():
    eps = _stub_entry_points(_make_ep("p1", plugins_mod.ENTRY_POINT_GROUP))
    with patch.object(plugins_mod.importlib.metadata, "entry_points",
                      return_value=eps):
        assert plugins_mod.enable_plugin("doesnotexist") is False


def test_state_persisted_to_disk(tmp_path):
    """Disabling a plugin writes to the state file."""
    eps = _stub_entry_points(_make_ep("p1", plugins_mod.ENTRY_POINT_GROUP))
    state_path = plugins_mod.DEFAULT_STATE_FILE
    with patch.object(plugins_mod.importlib.metadata, "entry_points",
                      return_value=eps):
        plugins_mod.disable_plugin("p1")
    assert Path(state_path).exists()
    data = json.loads(Path(state_path).read_text())
    assert data["disabled"] == ["p1"]


def test_state_loaded_from_existing_disk(tmp_path):
    """On startup, a disabled plugin must come back as disabled."""
    state_path = Path(plugins_mod.DEFAULT_STATE_FILE)
    state_path.write_text(json.dumps({"disabled": ["p1"]}))
    plugins_mod._invalidate_cache()

    eps = _stub_entry_points(_make_ep("p1", plugins_mod.ENTRY_POINT_GROUP))
    with patch.object(plugins_mod.importlib.metadata, "entry_points",
                      return_value=eps):
        plugins = plugins_mod.discover_plugins(include_disabled=True)
    p1 = next(p for p in plugins if p.name == "p1")
    assert p1.enabled is False


def test_load_plugin_class_returns_class():
    eps = _stub_entry_points(_make_ep("p1", plugins_mod.ENTRY_POINT_GROUP,
                                       target="MyProcessor"))
    with patch.object(plugins_mod.importlib.metadata, "entry_points",
                      return_value=eps):
        cls = plugins_mod.load_plugin_class("p1")
    assert cls is not None
    assert cls.__name__ == "MyProcessor"


def test_load_plugin_class_returns_none_for_disabled():
    eps = _stub_entry_points(_make_ep("p1", plugins_mod.ENTRY_POINT_GROUP))
    with patch.object(plugins_mod.importlib.metadata, "entry_points",
                      return_value=eps):
        plugins_mod.disable_plugin("p1")
        cls = plugins_mod.load_plugin_class("p1")
    assert cls is None


def test_load_plugin_class_returns_none_for_unknown():
    with patch.object(plugins_mod.importlib.metadata, "entry_points",
                      return_value=_stub_entry_points()):
        assert plugins_mod.load_plugin_class("nope") is None


def test_load_failure_is_recorded_as_summary():
    eps = _stub_entry_points(
        _make_ep("broken", plugins_mod.ENTRY_POINT_GROUP,
                 load_error=ImportError("missing dep")),
    )
    with patch.object(plugins_mod.importlib.metadata, "entry_points",
                      return_value=eps):
        plugins = plugins_mod.discover_plugins()
    assert "failed to load" in (plugins[0].summary or "")


def test_reload_returns_counts():
    eps = _stub_entry_points(
        _make_ep("p1", plugins_mod.ENTRY_POINT_GROUP),
        _make_ep("p2", plugins_mod.ENTRY_POINT_GROUP),
        _make_ep("p3", plugins_mod.ENTRY_POINT_GROUP),
    )
    with patch.object(plugins_mod.importlib.metadata, "entry_points",
                      return_value=eps):
        plugins_mod.disable_plugin("p2")
        result = plugins_mod.reload_discovery()
    assert result["reloaded"] is True
    assert result["found"] == 3
    assert result["enabled"] == 2
    assert result["disabled"] == 1


# ---------------------------------------------------------------------------
# HTTP admin endpoints
# ---------------------------------------------------------------------------

def test_admin_list_plugins_requires_auth(tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    app = FastAPI()
    app.include_router(plugin_routes.router, prefix="/api")
    with TestClient(app) as c:
        res = c.get("/api/admin/plugins")
        assert res.status_code == 403


def test_admin_endpoints_round_trip(tmp_path, monkeypatch):
    """Full HTTP flow: list → disable → list → enable → list."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from youface.api.middleware import TenantMiddleware

    fake_state = tmp_path / "plugins.json"
    monkeypatch.setattr(plugins_mod, "DEFAULT_STATE_FILE", str(fake_state))
    plugins_mod._invalidate_cache()

    eps = _stub_entry_points(
        _make_ep("alpha", plugins_mod.ENTRY_POINT_GROUP, target="Alpha"),
        _make_ep("beta", plugins_mod.ENTRY_POINT_GROUP, target="Beta"),
    )
    app = FastAPI()
    app.add_middleware(TenantMiddleware)
    app.include_router(plugin_routes.router, prefix="/api")

    with patch.object(plugins_mod.importlib.metadata, "entry_points",
                      return_value=eps):
        with patch.dict(os.environ, {"YOUFACE_API_TOKEN": "adm"}):
            with TestClient(app) as c:
                # List
                res = c.get("/api/admin/plugins", headers={"Authorization": "Bearer adm"})
                assert res.status_code == 200
                assert {p["name"] for p in res.json()} == {"alpha", "beta"}

                # Disable alpha
                res = c.post("/api/admin/plugins/alpha/disable",
                              headers={"Authorization": "Bearer adm"})
                assert res.status_code == 200
                assert res.json() == {"name": "alpha", "enabled": False}

                # List with include_disabled=False hides it
                res = c.get(
                    "/api/admin/plugins?include_disabled=false",
                    headers={"Authorization": "Bearer adm"},
                )
                assert res.status_code == 200
                assert {p["name"] for p in res.json()} == {"beta"}

                # List with include_disabled=True shows both with alpha.enabled=False
                res = c.get(
                    "/api/admin/plugins?include_disabled=true",
                    headers={"Authorization": "Bearer adm"},
                )
                enabled_map = {p["name"]: p["enabled"] for p in res.json()}
                assert enabled_map == {"alpha": False, "beta": True}

                # Enable alpha
                res = c.post("/api/admin/plugins/alpha/enable",
                              headers={"Authorization": "Bearer adm"})
                assert res.status_code == 200
                assert res.json() == {"name": "alpha", "enabled": True}

                # Reload
                res = c.post("/api/admin/plugins/reload",
                              headers={"Authorization": "Bearer adm"})
                assert res.status_code == 200
                assert res.json()["reloaded"] is True


def test_admin_show_unknown_returns_404(tmp_path, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    fake_state = tmp_path / "plugins.json"
    monkeypatch.setattr(plugins_mod, "DEFAULT_STATE_FILE", str(fake_state))
    plugins_mod._invalidate_cache()

    app = FastAPI()
    app.include_router(plugin_routes.router, prefix="/api")
    with patch.object(plugins_mod.importlib.metadata, "entry_points",
                      return_value=_stub_entry_points()):
        with patch.dict(os.environ, {"YOUFACE_API_TOKEN": "adm"}):
            with TestClient(app) as c:
                res = c.get("/api/admin/plugins/ghost", headers={"Authorization": "Bearer adm"})
                assert res.status_code == 404
