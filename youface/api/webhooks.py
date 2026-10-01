"""
Webhook dispatch for job completion events (R8 of gauntlet).

Design:
- A job can carry an optional `webhook_url`. When the job reaches a
  terminal state (completed / failed / cancelled), the worker fires a
  POST with a JSON payload describing the outcome.
- Retries: exponential backoff (1s, 2s, 4s, 8s, 16s) up to 5 attempts.
- Per-job dead-letter: failed deliveries are stored in the
  `webhook_deliveries` table so admins can inspect them via
  GET /api/admin/webhooks/failed.
- HMAC signature: every request includes `X-Webhook-Signature` header
  (`sha256=<hex>`) computed from the raw body using the tenant's
  webhook_secret. Tenants can verify the call originated from us.
- Idempotency: `X-Webhook-Id` is the job_id, so consumers can dedupe.

We deliberately do NOT use a third-party library (httpx is fine but
kept external — webhook delivery is in-process and synchronous from
the worker's perspective). The dispatcher uses urllib from stdlib so
it adds zero dependencies and survives when the worker is mid-import.

NOTE: For high-volume deployments you'd want a queue (Celery/RQ/Arq).
The current implementation is intentionally simple — it's a 90/20
solution for the "let n8n/Airflow react to job results" use case.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import socket
import ssl
import threading
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional, List

from sqlalchemy import Column, String, Integer, DateTime, Text, Boolean
from sqlalchemy.orm import Session

from youface.api.database import Base, SessionLocal


logger = logging.getLogger("youface.api.webhooks")


# ---------------------------------------------------------------------------
# Configuration (env vars)
# ---------------------------------------------------------------------------

#: Max delivery attempts before giving up.
WEBHOOK_MAX_ATTEMPTS = int(os.environ.get("YOUFACE_WEBHOOK_MAX_ATTEMPTS", "5"))

#: Initial backoff in seconds (doubles each attempt, capped).
WEBHOOK_BACKOFF_BASE = float(os.environ.get("YOUFACE_WEBHOOK_BACKOFF_BASE", "1.0"))

#: Per-request timeout.
WEBHOOK_TIMEOUT_SECONDS = float(os.environ.get("YOUFACE_WEBHOOK_TIMEOUT", "10"))


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

class WebhookDeliveryModel(Base):
    """A delivery attempt for a job's webhook."""
    __tablename__ = "webhook_deliveries"

    id: str = Column(String, primary_key=True, index=True)
    job_id: str = Column(String, index=True, nullable=False)
    tenant_id: Optional[str] = Column(String, nullable=True, index=True)
    url: str = Column(String, nullable=False)
    status: str = Column(String, default="pending")  # pending, delivered, failed
    attempts: int = Column(Integer, default=0)
    last_status_code: Optional[int] = Column(Integer, nullable=True)
    last_error: Optional[str] = Column(Text, nullable=True)
    delivered_at: Optional[datetime] = Column(DateTime, nullable=True)
    created_at: datetime = Column(DateTime, default=datetime.utcnow)
    updated_at: datetime = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


_init_lock = threading.Lock()
_initialized = False


def ensure_webhook_tables() -> None:
    """Idempotent table creation."""
    global _initialized
    with _init_lock:
        if _initialized:
            return
        try:
            Base.metadata.create_all(bind=SessionLocal().bind)  # type: ignore[arg-type]
            _initialized = True
        except Exception:
            pass


def record_delivery(
    *,
    job_id: str,
    url: str,
    tenant_id: Optional[str],
    status: str,
    attempts: int,
    last_status_code: Optional[int] = None,
    last_error: Optional[str] = None,
    delivered_at: Optional[datetime] = None,
) -> str:
    delivery_id = f"wbd-{uuid.uuid4().hex[:12]}"
    db = SessionLocal()
    try:
        row = WebhookDeliveryModel(
            id=delivery_id,
            job_id=job_id,
            tenant_id=tenant_id,
            url=url,
            status=status,
            attempts=attempts,
            last_status_code=last_status_code,
            last_error=last_error,
            delivered_at=delivered_at,
        )
        db.add(row)
        db.commit()
        return delivery_id
    finally:
        db.close()


def update_delivery(delivery_id: str, **kwargs: Any) -> None:
    db = SessionLocal()
    try:
        row = db.query(WebhookDeliveryModel).filter_by(id=delivery_id).first()
        if row is None:
            return
        for k, v in kwargs.items():
            setattr(row, k, v)
        db.commit()
    finally:
        db.close()


def list_deliveries(
    *,
    job_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    db = SessionLocal()
    try:
        q = db.query(WebhookDeliveryModel)
        if job_id is not None:
            q = q.filter_by(job_id=job_id)
        if status is not None:
            q = q.filter_by(status=status)
        rows = q.order_by(WebhookDeliveryModel.created_at.desc()).limit(limit).all()
        out = []
        for r in rows:
            out.append({
                "id": r.id,
                "job_id": r.job_id,
                "tenant_id": r.tenant_id,
                "url": r.url,
                "status": r.status,
                "attempts": r.attempts,
                "last_status_code": r.last_status_code,
                "last_error": r.last_error,
                "delivered_at": r.delivered_at.isoformat() + "Z" if r.delivered_at else None,
                "created_at": r.created_at.isoformat() + "Z" if r.created_at else None,
            })
        return out
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Signature
# ---------------------------------------------------------------------------

def _sign(body: bytes, secret: Optional[str]) -> str:
    """Compute `sha256=<hex>` HMAC signature. Empty string if no secret."""
    if not secret:
        return ""
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


# ---------------------------------------------------------------------------
# Payload + dispatch
# ---------------------------------------------------------------------------

@dataclass
class WebhookPayload:
    """The JSON body we POST to the consumer."""
    job_id: str
    status: str  # completed / failed / cancelled
    output_url: Optional[str]
    error_message: Optional[str]
    duration_seconds: float
    progress: int
    timestamp: str
    tenant_id: Optional[str] = None

    def to_json(self) -> str:
        return json.dumps(self.__dict__, separators=(",", ":"), ensure_ascii=False)


def _post_once(url: str, body: bytes, headers: Dict[str, str], timeout: float) -> int:
    """Single HTTP POST. Returns status code (or -1 on transport error)."""
    req = urllib.request.Request(url, data=body, method="POST", headers=headers)
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        # 4xx/5xx still give us a status code; consumer might want it
        return e.code
    except (urllib.error.URLError, socket.timeout, ConnectionError, OSError) as e:
        return -1


def deliver(
    *,
    job_id: str,
    url: str,
    payload: WebhookPayload,
    secret: Optional[str] = None,
    max_attempts: Optional[int] = None,
    backoff_base: Optional[float] = None,
    timeout: Optional[float] = None,
) -> Dict[str, Any]:
    """Deliver a webhook with retries. Returns a result dict for tests/callers.

    Side effects: persists the delivery to the webhook_deliveries table.

    The function is synchronous on purpose — it's called from the worker
    thread, which already has its own thread budget. Async would require
    adding a separate dispatcher loop.
    """
    max_attempts = max_attempts or WEBHOOK_MAX_ATTEMPTS
    backoff_base = backoff_base if backoff_base is not None else WEBHOOK_BACKOFF_BASE
    timeout = timeout if timeout is not None else WEBHOOK_TIMEOUT_SECONDS

    body_str = payload.to_json()
    body = body_str.encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "youface-webhook/1.0",
        "X-Webhook-Id": job_id,
        "X-Webhook-Signature": _sign(body, secret),
    }

    # Record the delivery row up front so it appears in /admin/webhooks
    delivery_id = record_delivery(
        job_id=job_id,
        url=url,
        tenant_id=payload.tenant_id,
        status="pending",
        attempts=0,
    )

    last_status = -1
    last_error: Optional[str] = None

    for attempt in range(1, max_attempts + 1):
        try:
            last_status = _post_once(url, body, headers, timeout)
        except Exception as e:
            last_status = -1
            last_error = repr(e)

        if 200 <= last_status < 300:
            update_delivery(
                delivery_id,
                status="delivered",
                attempts=attempt,
                last_status_code=last_status,
                delivered_at=datetime.utcnow(),
                last_error=None,
            )
            return {
                "delivery_id": delivery_id,
                "status": "delivered",
                "attempts": attempt,
                "last_status_code": last_status,
            }

        # Failed this attempt — wait before retry unless this was the last
        if attempt < max_attempts:
            sleep_for = backoff_base * (2 ** (attempt - 1))
            # Cap at 60s so we don't sleep forever
            sleep_for = min(sleep_for, 60.0)
            time.sleep(sleep_for)

    # All attempts exhausted
    error_summary = f"HTTP {last_status}" if last_status != -1 else (last_error or "transport error")
    update_delivery(
        delivery_id,
        status="failed",
        attempts=max_attempts,
        last_status_code=None if last_status == -1 else last_status,
        last_error=error_summary,
    )
    return {
        "delivery_id": delivery_id,
        "status": "failed",
        "attempts": max_attempts,
        "last_status_code": None if last_status == -1 else last_status,
        "last_error": error_summary,
    }


# ---------------------------------------------------------------------------
# Convenience wrapper for the worker
# ---------------------------------------------------------------------------

def fire_job_completion(
    *,
    job_id: str,
    webhook_url: str,
    status: str,
    output_url: Optional[str],
    error_message: Optional[str],
    duration_seconds: float,
    progress: int,
    tenant_id: Optional[str] = None,
    secret: Optional[str] = None,
) -> Dict[str, Any]:
    """Build the payload + call deliver(). Used by the worker on terminal
    state transitions. Returns whatever deliver() returned."""
    payload = WebhookPayload(
        job_id=job_id,
        status=status,
        output_url=output_url,
        error_message=error_message,
        duration_seconds=duration_seconds,
        progress=progress,
        timestamp=datetime.utcnow().isoformat() + "Z",
        tenant_id=tenant_id,
    )
    try:
        return deliver(
            job_id=job_id,
            url=webhook_url,
            payload=payload,
            secret=secret,
        )
    except Exception as e:
        logger.warning("Webhook dispatch failed for job %s: %s", job_id, e)
        return {"delivery_id": None, "status": "failed", "attempts": 0, "error": str(e)}


__all__ = [
    "WebhookPayload",
    "WebhookDeliveryModel",
    "deliver",
    "fire_job_completion",
    "ensure_webhook_tables",
    "list_deliveries",
    "WEBHOOK_MAX_ATTEMPTS",
    "WEBHOOK_BACKOFF_BASE",
    "WEBHOOK_TIMEOUT_SECONDS",
]
