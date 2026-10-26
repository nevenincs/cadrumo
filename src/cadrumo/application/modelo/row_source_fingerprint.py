"""Safe public provenance for one replayed Modelo row coordinate."""

from __future__ import annotations

from pydantic import BaseModel, Field

from ...core.aggregation import BindingSourceKind
from ...core.identity.digest import ContentDigest
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...domain.calculations.registry.ids import BindingId


class ModeloRowSourceFingerprint(BaseModel):
    """Safe public provenance for one replayed row coordinate."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    binding_id: BindingId
    row_index: int = Field(ge=1)
    source_kind: BindingSourceKind
    fingerprint: ContentDigest


__all__ = ["ModeloRowSourceFingerprint"]
