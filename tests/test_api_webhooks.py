"""
Tests for webhook dispatch (R8 of gauntlet).

Covers:
- Successful delivery (HTTP 200)
- Retry on 5xx with exponential backoff
- Give-up after max_attempts
- HMAC signature is present and correct when secret is provided
- X-Webhook-Id header carries the job id (idempotency)
- Failed deliveries land in the webhook_deliveries table
- /api/admin/webhooks is gated by admin token
- list_deliveries filters by job_id and status
"""
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, List
from unittest.mock import patch

import pytest

from facefusion.api import webhooks as webhooks_mod


# ---------------------------------------------------------------------------
# Test consumer (mini HTTP server)
# ---------------------------------------------------------------------------

_STATE = {"requests": [], "respond_with": 200}


def _next_status() -> int:
    """Decide the next status code based on `_STATE["respond_with"]`.

    Supports three shapes:
      - int: always respond with that status
      - list[int]: pop statuses in order
      - callable: callable() -> int, called per request
    """
    val = _STATE["respond_with"]
    if callable(val):
        return int(val())
    if isinstance(val, list):
        if not val:
            return 200
        return int(val.pop(0))
    return int(val)


class _Recorder(BaseHTTPRequestHandler):
    """Records each incoming request so tests can assert on them."""

    def do_POST(self):  # noqa: N802 — required by BaseHTTPRequestHandler
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length > 0 else b""
        _STATE["requests"].append({
            "path": self.path,
            "headers": {k: v for k, v in self.headers.items()},
            "body": body,
        })
        status = _next_status()
        if 200 <= status < 300:
            self.send_response(status)
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"OK")
        else:
            self.send_response(status)
            self.send_header("Content-Length", "0")
            self.end_headers()

    def log_message(self, *_args):  # silence stderr noise during tests
        return


@pytest.fixture
def consumer_server():
    """Starts a tiny HTTP server in a daemon thread. Tests can:
        - read `consumer_server.requests` to inspect what was sent
        - set `consumer_server.respond_with` to control the next response
        - call `consumer_server.reset()` to clear the recorder
    """
    _STATE["requests"] = []
    _STATE["respond_with"] = 200

    server = HTTPServer(("127.0.0.1", 0), _Recorder)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    class Wrapper:
        url = f"http://127.0.0.1:{port}/hook"

        @property
        def requests(self):
            return list(_STATE["requests"])

        @property
        def respond_with(self):
            return _STATE["respond_with"]

        @respond_with.setter
        def respond_with(self, value):
            _STATE["respond_with"] = value

        def reset(self):
            _STATE["requests"] = []

        def shutdown(self):
            server.shutdown()
            thread.join(timeout=2)

    wrapper = Wrapper()
    yield wrapper
    wrapper.shutdown()


# ---------------------------------------------------------------------------
# Per-test DB isolation
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def isolated_webhook_db(tmp_path):
    """Point webhooks.SessionLocal at a private SQLite file per test.

    The global SessionLocal from facefusion.api.database is shared across
    modules and accumulates state across tests. For webhook tests we want
    a clean slate: separate file, ensure tables, then restore the global.
    """
    from sqlalchemy import create_engine, event
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    db_path = tmp_path / "webhooks.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    from facefusion.api.database import Base
    Base.metadata.create_all(bind=engine)

    with patch.object(webhooks_mod, "SessionLocal", SessionLocal):
        yield

    # Cleanup
    try:
        db_path.unlink()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Pure-function tests on deliver()
# ---------------------------------------------------------------------------

def test_deliver_returns_delivered_on_2xx(consumer_server):
    consumer_server.respond_with = 200
    result = webhooks_mod.deliver(
        job_id="job-1",
        url=consumer_server.url,
        payload=webhooks_mod.WebhookPayload(
            job_id="job-1", status="completed", output_url="/out.mp4",
            error_message=None, duration_seconds=10.0, progress=100,
            timestamp="2026-09-28T00:00:00Z",
        ),
    )
    assert result["status"] == "delivered"
    assert result["attempts"] == 1
    assert len(consumer_server.requests) == 1


def test_deliver_retries_on_5xx_then_succeeds(consumer_server):
    """First response 500, then 200 — should retry and succeed on attempt 2."""
    consumer_server.respond_with = [500, 200]
    payload = webhooks_mod.WebhookPayload(
        job_id="job-2", status="completed", output_url=None,
        error_message=None, duration_seconds=1.0, progress=100,
        timestamp="2026-09-28T00:00:00Z",
    )
    # Use small backoff so the test is fast
    result = webhooks_mod.deliver(
        job_id="job-2",
        url=consumer_server.url,
        payload=payload,
        max_attempts=3,
        backoff_base=0.05,
    )
    assert result["status"] == "delivered"
    assert result["attempts"] == 2
    assert len(consumer_server.requests) == 2


def test_deliver_gives_up_after_max_attempts(consumer_server):
    consumer_server.respond_with = 502
    payload = webhooks_mod.WebhookPayload(
        job_id="job-3", status="failed", output_url=None,
        error_message="boom", duration_seconds=1.0, progress=0,
        timestamp="2026-09-28T00:00:00Z",
    )
    result = webhooks_mod.deliver(
        job_id="job-3",
        url=consumer_server.url,
        payload=payload,
        max_attempts=3,
        backoff_base=0.01,
    )
    assert result["status"] == "failed"
    assert result["attempts"] == 3
    assert result["last_status_code"] == 502
    assert len(consumer_server.requests) == 3


def test_signature_header_present_and_correct(consumer_server):
    import hmac, hashlib
    consumer_server.respond_with = 200
    secret = "topsecret"
    payload = webhooks_mod.WebhookPayload(
        job_id="job-sig", status="completed", output_url="/x.mp4",
        error_message=None, duration_seconds=1.0, progress=100,
        timestamp="2026-09-28T00:00:00Z",
    )
    result = webhooks_mod.deliver(
        job_id="job-sig",
        url=consumer_server.url,
        payload=payload,
        secret=secret,
        backoff_base=0.01,
    )
    assert result["status"] == "delivered"
    assert len(consumer_server.requests) == 1
    req = consumer_server.requests[0]
    body = req["body"]
    sig = req["headers"].get("X-Webhook-Signature", "")
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert sig == expected


def test_webhook_id_header_for_idempotency(consumer_server):
    consumer_server.respond_with = 200
    payload = webhooks_mod.WebhookPayload(
        job_id="job-uniq-1234", status="completed", output_url=None,
        error_message=None, duration_seconds=1.0, progress=100,
        timestamp="2026-09-28T00:00:00Z",
    )
    webhooks_mod.deliver(job_id="job-uniq-1234", url=consumer_server.url, payload=payload)
    req = consumer_server.requests[0]
    assert req["headers"].get("X-Webhook-Id") == "job-uniq-1234"


def test_payload_contains_expected_fields(consumer_server):
    import json
    consumer_server.respond_with = 200
    payload = webhooks_mod.WebhookPayload(
        job_id="job-payload", status="completed", output_url="/api/output.mp4",
        error_message=None, duration_seconds=42.5, progress=100,
        timestamp="2026-09-28T00:00:00Z", tenant_id="tnt-abc",
    )
    webhooks_mod.deliver(job_id="job-payload", url=consumer_server.url, payload=payload)
    body = json.loads(consumer_server.requests[0]["body"].decode("utf-8"))
    assert body["job_id"] == "job-payload"
    assert body["status"] == "completed"
    assert body["output_url"] == "/api/output.mp4"
    assert body["duration_seconds"] == 42.5
    assert body["progress"] == 100
    assert body["tenant_id"] == "tnt-abc"


def test_failed_delivery_recorded_in_db(consumer_server):
    """A failed dispatch must persist to webhook_deliveries with status='failed'."""
    consumer_server.respond_with = 500
    payload = webhooks_mod.WebhookPayload(
        job_id="job-failed", status="failed", output_url=None,
        error_message="nope", duration_seconds=1.0, progress=0,
        timestamp="2026-09-28T00:00:00Z",
    )
    webhooks_mod.deliver(
        job_id="job-failed", url=consumer_server.url, payload=payload,
        max_attempts=2, backoff_base=0.01,
    )
    rows = webhooks_mod.list_deliveries(job_id="job-failed")
    assert len(rows) == 1
    assert rows[0]["status"] == "failed"
    assert rows[0]["attempts"] == 2
    assert rows[0]["last_status_code"] == 500


def test_list_deliveries_filter_by_status(consumer_server):
    consumer_server.respond_with = 200
    payload = webhooks_mod.WebhookPayload(
        job_id="job-ok", status="completed", output_url=None,
        error_message=None, duration_seconds=1.0, progress=100,
        timestamp="2026-09-28T00:00:00Z",
    )
    webhooks_mod.deliver(job_id="job-ok", url=consumer_server.url, payload=payload)

    consumer_server.respond_with = 500
    bad_payload = webhooks_mod.WebhookPayload(
        job_id="job-bad", status="failed", output_url=None,
        error_message=None, duration_seconds=1.0, progress=0,
        timestamp="2026-09-28T00:00:00Z",
    )
    webhooks_mod.deliver(job_id="job-bad", url=consumer_server.url, payload=bad_payload,
                         max_attempts=1, backoff_base=0.01)

    delivered = webhooks_mod.list_deliveries(status="delivered")
    failed = webhooks_mod.list_deliveries(status="failed")
    assert any(d["job_id"] == "job-ok" for d in delivered)
    assert any(d["job_id"] == "job-bad" for d in failed)


# ---------------------------------------------------------------------------
# HTTP layer tests (admin endpoints)
# ---------------------------------------------------------------------------

@pytest.fixture
def admin_client(tmp_path):
    """A TestClient with FACEFUSION_API_TOKEN set + admin auth header.

    No real webhook deliveries — the admin tests insert rows directly
    via webhooks_mod.record_delivery, then hit the admin endpoint.
    """
    from fastapi.testclient import TestClient
    from facefusion.api.main import app
    from facefusion.api import tenants as tenants_mod
    from facefusion.api import webhooks as wh_mod
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from facefusion.api.database import Base, get_db

    db_path = tmp_path / "admin.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    with patch.object(wh_mod, "SessionLocal", SessionLocal), \
         patch.object(wh_mod, "ensure_webhook_tables", lambda: None), \
         patch.object(tenants_mod, "SessionLocal", SessionLocal), \
         patch.object(tenants_mod, "ensure_tenant_tables", lambda: None):
        app.dependency_overrides[get_db] = override_get_db
        with patch.dict(os.environ, {"FACEFUSION_API_TOKEN": "admin-token"}):
            with TestClient(app) as c:
                yield c, SessionLocal, "Bearer admin-token"
        app.dependency_overrides.clear()


def test_admin_webhook_list_requires_auth(tmp_path):
    """No FACEFUSION_API_TOKEN + no admin tenant → 403."""
    from fastapi.testclient import TestClient
    from facefusion.api.main import app
    from facefusion.api import tenants as tenants_mod
    from facefusion.api import webhooks as wh_mod
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from facefusion.api.database import Base, get_db

    db_path = tmp_path / "noauth.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    with patch.object(wh_mod, "SessionLocal", SessionLocal), \
         patch.object(wh_mod, "ensure_webhook_tables", lambda: None), \
         patch.object(tenants_mod, "SessionLocal", SessionLocal), \
         patch.object(tenants_mod, "ensure_tenant_tables", lambda: None):
        app.dependency_overrides[get_db] = override_get_db
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("FACEFUSION_API_TOKEN", None)
            with TestClient(app) as c:
                res = c.get("/api/admin/webhooks")
                assert res.status_code == 403
        app.dependency_overrides.clear()


def test_admin_webhook_list_returns_recent_deliveries(admin_client):
    """Insert deliveries directly + list via admin endpoint."""
    client, SessionLocal, auth = admin_client
    # Insert two delivery rows directly so we don't depend on real HTTP
    webhooks_mod.record_delivery(
        job_id="job-list-1", url="http://nowhere/hook", tenant_id=None,
        status="delivered", attempts=1, last_status_code=200,
    )
    webhooks_mod.record_delivery(
        job_id="job-list-2", url="http://nowhere/hook", tenant_id=None,
        status="delivered", attempts=1, last_status_code=200,
    )
    res = client.get("/api/admin/webhooks", headers={"Authorization": auth})
    assert res.status_code == 200
    rows = res.json()
    ids = {r["job_id"] for r in rows}
    assert {"job-list-1", "job-list-2"}.issubset(ids)


def test_admin_webhook_list_filter_by_job(admin_client):
    client, SessionLocal, auth = admin_client
    for i in range(3):
        webhooks_mod.record_delivery(
            job_id=f"job-fil-{i}", url="http://nowhere/hook", tenant_id=None,
            status="delivered", attempts=1,
        )
    res = client.get("/api/admin/webhooks?job_id=job-fil-1", headers={"Authorization": auth})
    assert res.status_code == 200
    rows = res.json()
    assert len(rows) == 1
    assert rows[0]["job_id"] == "job-fil-1"


def test_admin_webhook_failed_filter(admin_client):
    client, SessionLocal, auth = admin_client
    webhooks_mod.record_delivery(
        job_id="job-ok", url="http://nowhere", tenant_id=None,
        status="delivered", attempts=1,
    )
    webhooks_mod.record_delivery(
        job_id="job-bad", url="http://nowhere", tenant_id=None,
        status="failed", attempts=5, last_status_code=502,
        last_error="HTTP 502",
    )
    res = client.get("/api/admin/webhooks/failed", headers={"Authorization": auth})
    assert res.status_code == 200
    rows = res.json()
    assert all(r["status"] == "failed" for r in rows)
    assert any(r["job_id"] == "job-bad" for r in rows)
