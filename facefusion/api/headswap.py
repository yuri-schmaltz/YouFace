"""
Head-swap module (R14 of gauntlet).

Wraps facefusion/processors/modules/live_portrait.py to expose a
"head swap" mode that replaces not just the face but the full head
(face + hair + ears + neck). The underlying network (LivePortrait)
already produces pose/expression warps that cover the surrounding
region; we just need a different masking strategy.

Why this is "head swap" vs "face swap":
- Face swap only modifies the skin inside a face-parsing mask
  (cheeks, nose, mouth). Hair, ears, and the edge of the jaw are
  unchanged — visible when source has different hair/length/skin.
- Head swap extends the modified region to cover the entire cranium
  silhouette (via a wider segmentation mask). Result looks like the
  full head was replaced.

DESIGN (R14)
- New `head_swap` flag in JobCreateRequest. When True, the worker
  invokes LivePortrait with an extended mask.
- The actual network invocation is unchanged (LivePortrait already
  accepts a mask parameter). What changes is the mask we generate.
- For testing purposes we don't run the network — we record the
  intent in the job row so consumers can inspect what mode was used.

This module is a thin orchestration layer. Heavy lifting (segmentation
model, warping fields) lives in facefusion/processors/live_portrait.py.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional


class SwapMode(str, Enum):
    """The kind of swap a job is performing."""
    FACE = "face"            # default: skin-only mask
    HEAD = "head"            # extended: full cranium silhouette
    EXPRESSION_ONLY = "expression_only"  # pose/expression only, no identity


@dataclass
class HeadSwapConfig:
    """Configuration for head-swap mode.

    All fields are optional; sensible defaults are applied at the
    processor level.
    """
    enabled: bool = False
    # Mask expansion in pixels (relative to face box). 0 = same as
    # face-swap. Positive values extend the mask outward.
    mask_expansion_px: int = 80
    # Whether to include hair in the modified region.
    include_hair: bool = True
    # Whether to include ears.
    include_ears: bool = True
    # Whether to include the neck (for shots where the neck is visible).
    include_neck: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "mask_expansion_px": self.mask_expansion_px,
            "include_hair": self.include_hair,
            "include_ears": self.include_ears,
            "include_neck": self.include_neck,
        }

    @classmethod
    def from_request(cls, data: Optional[Dict[str, Any]]) -> "HeadSwapConfig":
        if not data:
            return cls(enabled=False)
        return cls(
            enabled=bool(data.get("enabled", False)),
            mask_expansion_px=int(data.get("mask_expansion_px", 80)),
            include_hair=bool(data.get("include_hair", True)),
            include_ears=bool(data.get("include_ears", True)),
            include_neck=bool(data.get("include_neck", False)),
        )


def mode_for_job(head_swap_enabled: bool) -> SwapMode:
    """Resolve the swap mode from the boolean flag."""
    return SwapMode.HEAD if head_swap_enabled else SwapMode.FACE


def summary_for_api(head_swap: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """What we expose to the API for /api/jobs/{id}/head-swap-info."""
    cfg = HeadSwapConfig.from_request(head_swap)
    return {
        "mode": "head" if cfg.enabled else "face",
        "config": cfg.to_dict(),
    }


__all__ = [
    "SwapMode",
    "HeadSwapConfig",
    "mode_for_job",
    "summary_for_api",
]
