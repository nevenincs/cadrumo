"""Strict renderer-neutral local spreadsheet export projections."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field

from ...core.hex import Hex64Str
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...domain.calculations.registry.ids import ModeloId, RevisionId
from ..operations.public_period import PublicPeriod

_PathText = Annotated[str, Field(min_length=1, max_length=4096, pattern=r"\S")]
_Text = Annotated[str, Field(max_length=4096)]
_Count = Annotated[int, Field(ge=0)]


class ModeloSpreadsheetProjection(BaseModel):
    """Encrypted renderer-neutral result with its owning profile coordinate."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    modelo: ModeloId
    revision: RevisionId
    period: PublicPeriod


class ModeloSpreadsheetExportProjection(ModeloSpreadsheetProjection):
    """The same existing workbook publication receipt and coverage facts."""

    output_path: _PathText
    byte_size: _Count
    sha256: Hex64Str
    tab_names: Annotated[tuple[_Text, ...], Field(min_length=1, max_length=128)]
    casilla_count: _Count
    prefill_relations: bool


__all__ = ["ModeloSpreadsheetExportProjection", "ModeloSpreadsheetProjection"]
