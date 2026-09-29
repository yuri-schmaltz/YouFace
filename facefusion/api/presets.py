"""
Presets / recipes for the FaceFusion API (R9 of gauntlet).

A preset is a named, reusable bundle of job parameters. Operations teams
process the same kinds of videos all day (Instagram reels, YouTube
shorts, etc.) and want to avoid re-entering the same 30 fields for
each batch.

Design:
- Storage: SQLite table `presets` (id, name, owner_tenant_id, data JSON).
- Schema: Pydantic model `PresetData` covers all JobCreateRequest fields
  so any preset can be applied directly to a job.
- Scoping: presets are tenant-scoped when a tenant is identified on the
  request (the calling tenant_id is stored as owner_tenant_id). Anonymous
  presets are allowed for backwards compat (FACEFUSION_API_TOKEN admin).
- Apply: POST /api/presets/{id}/apply creates a job with the preset's
  data merged with any client overrides.
- Validation: Pydantic validates at write time so we never persist a
  broken preset.
"""
from __future__ import annotations

import datetime
import json
import os
import threading
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import Column, String, DateTime, Text, Boolean, Integer
from sqlalchemy.orm import Session

from facefusion.api.database import Base, SessionLocal


# ---------------------------------------------------------------------------
# Pydantic schema — mirrors JobCreateRequest fields
# ---------------------------------------------------------------------------

class PresetData(BaseModel):
    """Schema for preset data. All fields optional so a preset can hold
    just a subset (e.g. only the model choices)."""
    model_config = ConfigDict(extra="allow")  # allow new upstream fields without code changes

    # Mirror of JobCreateRequest fields
    source_paths: Optional[list] = None
    target_path: Optional[str] = None
    project_name: Optional[str] = None
    face_swapper_weight: Optional[float] = 0.5
    face_mask_blur: Optional[float] = 0.3
    detection_threshold: Optional[float] = 0.5
    smoothing: Optional[int] = 5
    processors: Optional[list] = ["face_swapper"]
    output_format: Optional[str] = "mp4"
    trim_frame_start: Optional[int] = None
    trim_frame_end: Optional[int] = None
    face_swapper_model: Optional[str] = "hyperswap_1a_256"
    face_swapper_pixel_boost: Optional[str] = None
    face_enhancer_model: Optional[str] = "gfpgan_1.4"
    face_enhancer_blend: Optional[int] = 80
    face_enhancer_weight: Optional[float] = 1.0
    frame_enhancer_model: Optional[str] = "span_kendata_x4"
    frame_enhancer_blend: Optional[int] = 80
    face_editor_model: Optional[str] = None
    age_modifier_model: Optional[str] = None
    age_modifier_direction: Optional[int] = None
    lip_syncer_model: Optional[str] = None
    expression_restorer_model: Optional[str] = None
    deep_swapper_model: Optional[str] = None
    frame_colorizer_model: Optional[str] = None
    background_remover_model: Optional[str] = None
    output_video_encoder: Optional[str] = "libx264"
    output_video_preset: Optional[str] = "medium"
    output_audio_encoder: Optional[str] = "aac"
    output_audio_quality: Optional[int] = 80
    output_audio_volume: Optional[int] = 100
    face_mask_types: Optional[list] = None
    face_mask_padding: Optional[list] = None
    face_detector_model: Optional[str] = None
    face_detector_size: Optional[str] = None
    face_detector_angles: Optional[list] = None
    face_landmarker_model: Optional[str] = None
    face_landmarker_score: Optional[float] = None
    face_occluder_model: Optional[str] = None
    face_parser_model: Optional[str] = None


class PresetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: Optional[str] = Field(None, max_length=512)
    data: PresetData
    shared: bool = False  # when true, visible to all tenants (admin-gated create)


class PresetUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=128)
    description: Optional[str] = Field(None, max_length=512)
    data: Optional[PresetData] = None


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

class PresetModel(Base):
    __tablename__ = "presets"

    id: str = Column(String, primary_key=True, index=True)
    name: str = Column(String, nullable=False, index=True)
    description: Optional[str] = Column(Text, nullable=True)
    owner_tenant_id: Optional[str] = Column(String, nullable=True, index=True)
    shared: bool = Column(Boolean, default=False, nullable=False)
    data: str = Column(Text, nullable=False)  # JSON-serialized PresetData
    created_at: datetime.datetime = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at: datetime.datetime = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


_init_lock = threading.Lock()
_initialized = False


def ensure_preset_tables() -> None:
    global _initialized
    with _init_lock:
        if _initialized:
            return
        try:
            Base.metadata.create_all(bind=SessionLocal().bind)  # type: ignore[arg-type]
            _initialized = True
        except Exception:
            pass


def _new_id() -> str:
    return f"prs-{uuid.uuid4().hex[:12]}"


@dataclass
class Preset:
    id: str
    name: str
    description: Optional[str]
    owner_tenant_id: Optional[str]
    shared: bool
    data: Dict[str, Any]
    created_at: datetime.datetime
    updated_at: datetime.datetime

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "owner_tenant_id": self.owner_tenant_id,
            "shared": self.shared,
            "data": self.data,
            "created_at": self.created_at.isoformat() + "Z" if self.created_at else None,
            "updated_at": self.updated_at.isoformat() + "Z" if self.updated_at else None,
        }


def _model_to_preset(m: PresetModel) -> Preset:
    try:
        data = json.loads(m.data) if m.data else {}
    except Exception:
        data = {}
    return Preset(
        id=m.id,
        name=m.name,
        description=m.description,
        owner_tenant_id=m.owner_tenant_id,
        shared=bool(m.shared),
        data=data,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


def create_preset(
    *,
    name: str,
    data: Dict[str, Any],
    description: Optional[str] = None,
    owner_tenant_id: Optional[str] = None,
    shared: bool = False,
) -> Preset:
    preset_id = _new_id()
    db = SessionLocal()
    try:
        # Reject duplicates within the same scope (name + owner)
        existing = db.query(PresetModel).filter_by(
            name=name, owner_tenant_id=owner_tenant_id
        ).first()
        if existing is not None:
            raise ValueError(f"Preset '{name}' already exists in this scope.")
        m = PresetModel(
            id=preset_id,
            name=name,
            description=description,
            owner_tenant_id=owner_tenant_id,
            shared=shared,
            data=json.dumps(data, separators=(",", ":")),
        )
        db.add(m)
        db.commit()
        db.refresh(m)
        return _model_to_preset(m)
    finally:
        db.close()


def get_preset(preset_id: str) -> Optional[Preset]:
    db = SessionLocal()
    try:
        m = db.query(PresetModel).filter_by(id=preset_id).first()
        return _model_to_preset(m) if m else None
    finally:
        db.close()


def list_presets(
    *,
    owner_tenant_id: Optional[str] = None,
    include_shared: bool = True,
    name_filter: Optional[str] = None,
) -> List[Preset]:
    """Return presets visible to a given tenant:
        - presets owned by the tenant (owner_tenant_id == tenant_id)
        - shared presets (shared == True), if include_shared

    If owner_tenant_id is None, returns ALL presets (admin mode).
    """
    db = SessionLocal()
    try:
        q = db.query(PresetModel)
        if owner_tenant_id is not None:
            from sqlalchemy import or_
            conditions = [PresetModel.owner_tenant_id == owner_tenant_id]
            if include_shared:
                conditions.append(PresetModel.shared.is_(True))
            q = q.filter(or_(*conditions))
        if name_filter:
            from sqlalchemy import func
            q = q.filter(func.lower(PresetModel.name).like(f"%{name_filter.lower()}%"))
        rows = q.order_by(PresetModel.created_at.asc()).all()
        return [_model_to_preset(m) for m in rows]
    finally:
        db.close()


def update_preset(
    preset_id: str,
    *,
    name: Optional[str] = None,
    description: Optional[Any] = None,
    data: Optional[Dict[str, Any]] = None,
    shared: Optional[bool] = None,
) -> Optional[Preset]:
    db = SessionLocal()
    try:
        m = db.query(PresetModel).filter_by(id=preset_id).first()
        if m is None:
            return None
        if name is not None:
            m.name = name
        if description is not None:
            m.description = description
        if data is not None:
            m.data = json.dumps(data, separators=(",", ":"))
        if shared is not None:
            m.shared = bool(shared)
        db.commit()
        db.refresh(m)
        return _model_to_preset(m)
    finally:
        db.close()


def delete_preset(preset_id: str) -> bool:
    db = SessionLocal()
    try:
        m = db.query(PresetModel).filter_by(id=preset_id).first()
        if m is None:
            return False
        db.delete(m)
        db.commit()
        return True
    finally:
        db.close()


def merge_for_apply(preset: Preset, overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Merge a preset's data with client overrides. Overrides take precedence.
    Returns a dict suitable for spreading into JobCreateRequest."""
    merged = dict(preset.data)
    if overrides:
        for k, v in overrides.items():
            if v is not None:
                merged[k] = v
    return merged


__all__ = [
    "Preset",
    "PresetModel",
    "PresetCreate",
    "PresetUpdate",
    "PresetData",
    "create_preset",
    "get_preset",
    "list_presets",
    "update_preset",
    "delete_preset",
    "merge_for_apply",
    "ensure_preset_tables",
]
