"""
Tests for the face-swap backend registry (R13 of gauntlet).

Covers:
- Built-in backends are registered
- Availability reflects installed deps
- resolve_backend falls back when requested backend is missing
- register_backend adds a new backend
- HTTP endpoints expose the registry
"""
import pytest

from youface.api import backends as backends_mod


@pytest.fixture(autouse=True)
def reset_registry():
    """Restore the original built-ins after each test in case a test
    registered a custom backend."""
    original = list(backends_mod._backends.items())
    yield
    backends_mod._backends = dict(original)
    backends_mod._active.clear()


def test_builtins_registered():
    """insightface and simswap are both registered at import."""
    names = list(backends_mod._backends.keys())
    assert "insightface" in names
    assert "simswap" in names


def test_list_backends_returns_dicts():
    rows = backends_mod.list_backends()
    assert isinstance(rows, list)
    assert all("name" in r and "available" in r for r in rows)


def test_insightface_availability():
    b = backends_mod.get_backend("insightface")
    assert b is not None
    # onnxruntime is installed in the test env, so this should be True
    assert b.is_available() is True


def test_simswap_not_available_in_default_env():
    b = backends_mod.get_backend("simswap")
    assert b is not None
    assert b.is_available() is False


def test_resolve_backend_returns_requested_if_available():
    b = backends_mod.resolve_backend("insightface")
    assert b.name == "insightface"


def test_resolve_backend_falls_back_when_unavailable():
    b = backends_mod.resolve_backend("simswap")
    # simswap isn't installed → falls back to default (insightface)
    assert b.name == "insightface"


def test_resolve_backend_falls_back_for_unknown_name():
    b = backends_mod.resolve_backend("totally-fake-backend")
    assert b.name == "insightface"


def test_resolve_backend_returns_default_when_no_name():
    b = backends_mod.resolve_backend(None)
    assert b.name == backends_mod.DEFAULT_BACKEND


def test_get_backend_unknown_returns_none():
    assert backends_mod.get_backend("nope") is None


def test_register_backend_adds_new_one():
    class FakeBackend(backends_mod.Backend):
        name = "fakex"
        display_name = "Fake"
        description = "Test backend"

        def is_available(self) -> bool:
            return True

        def load(self) -> None:
            pass

    backends_mod.register_backend(FakeBackend())
    assert backends_mod.get_backend("fakex") is not None
    assert backends_mod.get_backend("fakex").name == "fakex"


def test_register_backend_requires_name():
    class Nameless(backends_mod.Backend):
        name = ""
        def is_available(self) -> bool: return True
        def load(self) -> None: pass
    with pytest.raises(ValueError, match="non-empty name"):
        backends_mod.register_backend(Nameless())


def test_register_backend_replaces_existing():
    """Registering with the same name replaces the previous one."""
    class Replacement(backends_mod.Backend):
        name = "insightface"
        display_name = "Replacement insightface"
        def is_available(self) -> bool: return False
        def load(self) -> None: pass

    backends_mod.register_backend(Replacement())
    b = backends_mod.get_backend("insightface")
    assert b.display_name == "Replacement insightface"
    assert b.is_available() is False


def test_get_active_backend_loads_and_caches():
    b = backends_mod.get_active_backend("insightface")
    assert b.name == "insightface"
    # Second call returns the same instance (cached in _active)
    b2 = backends_mod.get_active_backend("insightface")
    assert b is b2


def test_get_active_backend_raises_for_unknown():
    with pytest.raises(KeyError, match="Unknown backend"):
        backends_mod.get_active_backend("doesnotexist")


def test_get_active_backend_raises_if_unavailable():
    """Trying to load an unavailable backend surfaces the install hint."""
    with pytest.raises(RuntimeError, match="not installed"):
        backends_mod.get_active_backend("simswap")


# ---------------------------------------------------------------------------
# HTTP layer
# ---------------------------------------------------------------------------

def test_http_backends_list():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    app = FastAPI()
    app.include_router(__import__("youface.api.routes.backends", fromlist=["router"]).router, prefix="/api")
    with TestClient(app) as c:
        res = c.get("/api/backends")
        assert res.status_code == 200
        body = res.json()
        assert "backends" in body
        assert "default" in body
        names = {b["name"] for b in body["backends"]}
        assert {"insightface", "simswap"}.issubset(names)


def test_http_backend_detail_404():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    app = FastAPI()
    app.include_router(__import__("youface.api.routes.backends", fromlist=["router"]).router, prefix="/api")
    with TestClient(app) as c:
        res = c.get("/api/backends/ghost")
        assert res.status_code == 404


def test_http_backend_active_loads():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    app = FastAPI()
    app.include_router(__import__("youface.api.routes.backends", fromlist=["router"]).router, prefix="/api")
    with TestClient(app) as c:
        res = c.get("/api/backends/insightface/active")
        assert res.status_code == 200
        assert res.json()["loaded"] is True


def test_http_backend_active_503_for_unavailable():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    app = FastAPI()
    app.include_router(__import__("youface.api.routes.backends", fromlist=["router"]).router, prefix="/api")
    with TestClient(app) as c:
        res = c.get("/api/backends/simswap/active")
        assert res.status_code == 503
        assert "not installed" in res.json()["detail"]
