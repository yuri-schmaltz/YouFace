"""
Multi-tenant support for the YouFace API.

This module adds lightweight multi-tenant isolation on top of the existing
single-token bearer auth. Key ideas:

- Each tenant is identified by an API key (`X-API-Key` header) or
  by an Authorization: Bearer <key> header.
- Quotas are tracked per-tenant per-calendar-month (UTC) in the same
  SQLite database the jobs use.
- Admin endpoints (create / list / disable / rotate key) require the
  existing YOUFACE_API_TOKEN env var (or any active admin tenant).

Design choices (kept simple on purpose):
- Storage: SQLite via SQLAlchemy, same engine as jobs. No Redis.
- Hashing: secrets.token_urlsafe(32) for the key + stored SHA-256 hash.
- Quota unit: "completed job-minute" — sum of (wall_time_seconds/60)
  for each completed/failed job in the calendar month.
- Default quota: 1000 minutes/month (configurable per tenant).
- Admin CLI: there is no admin CLI yet. Use POST /api/admin/tenants
  with the YOUFACE_API_TOKEN.

Backward compatibility:
- When no tenants exist and the YOUFACE_API_TOKEN is unset,
  requests are accepted as "anonymous tenant" with a generous quota.
  This preserves the current local-only mode.
- When YOUFACE_API_TOKEN is set, it is treated as an implicit
  admin tenant with no quota (the existing BearerAuthMiddleware
  still gates the request before we get here).
"""
from __future__ import annotations

import datetime
import hashlib
import os
import secrets
import threading
from dataclasses import dataclass
from typing import Optional, List, Dict, Any

from sqlalchemy import Column, String, Integer, DateTime, Boolean, Text
from sqlalchemy.orm import Session

from youface.api.database import Base, SessionLocal, JobModel


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Default monthly quota for newly created tenants (minutes of job time).
DEFAULT_MONTHLY_QUOTA_MINUTES = 1000

#: Sentinel value meaning "no quota enforced" (admin / local-only).
UNLIMITED_QUOTA = -1


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------

class TenantModel(Base):
    """A tenant of the YouFace API.

    `api_key_hash` stores the SHA-256 of the raw key. The raw key is only
    returned ONCE on creation/rotation; it cannot be recovered.
    """
    __tablename__ = "tenants"

    id: str = Column(String, primary_key=True, index=True)
    name: str = Column(String, nullable=False, unique=True)
    api_key_hash: str = Column(String, nullable=False, index=True)
    enabled: bool = Column(Boolean, default=True, nullable=False)
    monthly_quota_minutes: int = Column(Integer, default=DEFAULT_MONTHLY_QUOTA_MINUTES, nullable=False)
    is_admin: bool = Column(Boolean, default=False, nullable=False)
    notes: Optional[str] = Column(Text, nullable=True)
    created_at: datetime.datetime = Column(DateTime, default=datetime.datetime.utcnow)
    last_used_at: Optional[datetime.datetime] = Column(DateTime, nullable=True)


class TenantUsageModel(Base):
    """Monthly quota ledger. One row per (tenant, year-month)."""
    __tablename__ = "tenant_usage"

    tenant_id: str = Column(String, primary_key=True, index=True)
    period: str = Column(String, primary_key=True, index=True)  # 'YYYY-MM'
    minutes_used: float = Column(Integer, default=0, nullable=False)
    last_updated: datetime.datetime = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hash_key(raw_key: str) -> str:
    """SHA-256 hex digest of a raw API key. Constant-time safe (we use
    hashing, not compare)."""
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def _now_utc() -> datetime.datetime:
    return datetime.datetime.utcnow()


def _current_period(now: Optional[datetime.datetime] = None) -> str:
    now = now or _now_utc()
    return f"{now.year:04d}-{now.month:02d}"


def _new_id() -> str:
    return f"tnt-{secrets.token_hex(8)}"


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

@dataclass
class Tenant:
    """In-memory representation of a tenant."""
    id: str
    name: str
    enabled: bool
    monthly_quota_minutes: int
    is_admin: bool
    notes: Optional[str]
    created_at: datetime.datetime
    last_used_at: Optional[datetime.datetime]

    def to_dict(self, include_admin: bool = False) -> Dict[str, Any]:
        out = {
            "id": self.id,
            "name": self.name,
            "enabled": self.enabled,
            "monthly_quota_minutes": self.monthly_quota_minutes,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() + "Z" if self.created_at else None,
            "last_used_at": self.last_used_at.isoformat() + "Z" if self.last_used_at else None,
        }
        if include_admin:
            out["is_admin"] = self.is_admin
        return out


def _model_to_tenant(model: TenantModel) -> Tenant:
    return Tenant(
        id=model.id,
        name=model.name,
        enabled=bool(model.enabled),
        monthly_quota_minutes=int(model.monthly_quota_minutes),
        is_admin=bool(model.is_admin),
        notes=model.notes,
        created_at=model.created_at,
        last_used_at=model.last_used_at,
    )


def generate_api_key() -> str:
    """Generate a fresh API key (returned once on creation)."""
    return secrets.token_urlsafe(32)


def create_tenant(
    name: str,
    *,
    monthly_quota_minutes: int = DEFAULT_MONTHLY_QUOTA_MINUTES,
    is_admin: bool = False,
    notes: Optional[str] = None,
    enabled: bool = True,
    raw_key: Optional[str] = None,
) -> tuple[Tenant, str]:
    """Create a new tenant. Returns (Tenant, raw_api_key). The raw key is
    only available in this return value."""
    if not name or not name.strip():
        raise ValueError("Tenant name must not be empty")

    if raw_key is None:
        raw_key = generate_api_key()

    key_hash = _hash_key(raw_key)
    tenant_id = _new_id()

    db = SessionLocal()
    try:
        existing = db.query(TenantModel).filter_by(name=name).first()
        if existing is not None:
            raise ValueError(f"Tenant name already exists: {name}")

        model = TenantModel(
            id=tenant_id,
            name=name.strip(),
            api_key_hash=key_hash,
            enabled=enabled,
            monthly_quota_minutes=int(monthly_quota_minutes),
            is_admin=is_admin,
            notes=notes,
        )
        db.add(model)
        db.commit()
        db.refresh(model)
        return _model_to_tenant(model), raw_key
    finally:
        db.close()


def get_tenant_by_id(tenant_id: str) -> Optional[Tenant]:
    db = SessionLocal()
    try:
        m = db.query(TenantModel).filter_by(id=tenant_id).first()
        return _model_to_tenant(m) if m else None
    finally:
        db.close()


def get_tenant_by_key(raw_key: str) -> Optional[Tenant]:
    """Look up a tenant by raw API key. Returns None for unknown keys
    AND for disabled tenants (so disabling immediately blocks auth)."""
    if not raw_key:
        return None
    key_hash = _hash_key(raw_key)
    db = SessionLocal()
    try:
        m = db.query(TenantModel).filter_by(api_key_hash=key_hash).first()
        if m is None:
            return None
        if not bool(m.enabled):
            return None
        # touch last_used_at (best-effort; ignore errors so we don't block requests)
        try:
            m.last_used_at = _now_utc()
            db.commit()
        except Exception:
            db.rollback()
        return _model_to_tenant(m)
    finally:
        db.close()


def list_tenants(include_disabled: bool = False) -> List[Tenant]:
    db = SessionLocal()
    try:
        q = db.query(TenantModel)
        if not include_disabled:
            q = q.filter_by(enabled=True)
        rows = q.order_by(TenantModel.created_at.asc()).all()
        return [_model_to_tenant(m) for m in rows]
    finally:
        db.close()


def disable_tenant(tenant_id: str) -> bool:
    db = SessionLocal()
    try:
        m = db.query(TenantModel).filter_by(id=tenant_id).first()
        if m is None:
            return False
        m.enabled = False
        db.commit()
        return True
    finally:
        db.close()


def enable_tenant(tenant_id: str) -> bool:
    db = SessionLocal()
    try:
        m = db.query(TenantModel).filter_by(id=tenant_id).first()
        if m is None:
            return False
        m.enabled = True
        db.commit()
        return True
    finally:
        db.close()


def rotate_tenant_key(tenant_id: str) -> Optional[str]:
    """Generate a fresh API key for a tenant. Returns the new raw key
    (only available here) or None if tenant not found."""
    raw_key = generate_api_key()
    key_hash = _hash_key(raw_key)
    db = SessionLocal()
    try:
        m = db.query(TenantModel).filter_by(id=tenant_id).first()
        if m is None:
            return None
        m.api_key_hash = key_hash
        db.commit()
        return raw_key
    finally:
        db.close()


def update_tenant_quota(tenant_id: str, monthly_quota_minutes: int) -> bool:
    db = SessionLocal()
    try:
        m = db.query(TenantModel).filter_by(id=tenant_id).first()
        if m is None:
            return False
        m.monthly_quota_minutes = int(monthly_quota_minutes)
        db.commit()
        return True
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Quota tracking
# ---------------------------------------------------------------------------

def _bump_quota(tenant_id: str, minutes: float, period: Optional[str] = None) -> None:
    """Add `minutes` to the tenant's ledger for the given period."""
    if minutes <= 0:
        return
    period = period or _current_period()
    db = SessionLocal()
    try:
        row = db.query(TenantUsageModel).filter_by(tenant_id=tenant_id, period=period).first()
        if row is None:
            row = TenantUsageModel(tenant_id=tenant_id, period=period, minutes_used=0.0)
            db.add(row)
        row.minutes_used = float(row.minutes_used or 0) + float(minutes)
        db.commit()
    finally:
        db.close()


def get_usage_minutes(tenant_id: str, period: Optional[str] = None) -> float:
    period = period or _current_period()
    db = SessionLocal()
    try:
        row = db.query(TenantUsageModel).filter_by(tenant_id=tenant_id, period=period).first()
        return float(row.minutes_used) if row else 0.0
    finally:
        db.close()


def remaining_quota_minutes(tenant: Tenant, period: Optional[str] = None) -> Optional[float]:
    """Return minutes remaining, or None if tenant has no quota."""
    if tenant.monthly_quota_minutes == UNLIMITED_QUOTA:
        return None
    used = get_usage_minutes(tenant.id, period=period)
    return max(0.0, float(tenant.monthly_quota_minutes) - used)


def record_job_completion(tenant_id: Optional[str], duration_seconds: float) -> None:
    """Called by the worker when a job reaches a terminal state (completed or
    failed). Charges the quota if a tenant is associated.

    The duration is converted to minutes (rounded up to 0.1 minute to avoid
    free-rides on sub-second jobs)."""
    if not tenant_id:
        return
    if duration_seconds is None or duration_seconds <= 0:
        return
    minutes = max(0.1, duration_seconds / 60.0)
    _bump_quota(tenant_id, minutes)


# ---------------------------------------------------------------------------
# Schema bootstrap (called from database.init_db)
# ---------------------------------------------------------------------------

_init_lock = threading.Lock()
_initialized = False


def ensure_tenant_tables() -> None:
    """Create the tenant tables if they don't exist. Idempotent."""
    global _initialized
    with _init_lock:
        if _initialized:
            return
        try:
            Base.metadata.create_all(bind=SessionLocal().bind)  # type: ignore[arg-type]
            _initialized = True
        except Exception:
            # Don't block startup on a transient DB issue; routes that
            # need tenants will surface a clearer error.
            pass


__all__ = [
    "Tenant",
    "TenantModel",
    "TenantUsageModel",
    "DEFAULT_MONTHLY_QUOTA_MINUTES",
    "UNLIMITED_QUOTA",
    "generate_api_key",
    "create_tenant",
    "get_tenant_by_id",
    "get_tenant_by_key",
    "list_tenants",
    "disable_tenant",
    "enable_tenant",
    "rotate_tenant_key",
    "update_tenant_quota",
    "get_usage_minutes",
    "remaining_quota_minutes",
    "record_job_completion",
    "ensure_tenant_tables",
]
