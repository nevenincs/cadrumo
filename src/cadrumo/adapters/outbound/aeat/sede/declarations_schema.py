"""Declaration-register boundary records."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator

from .....core.filing_year import FilingYear
from .....core.identity import AeatExpedienteId
from .....core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from .....core.period import Period

__all__ = ["Declaracion"]


class Declaracion(BaseModel):
    """One row from *Consultar declaraciones presentadas*."""

    model_config = _STRICT_FROZEN

    modelo: str = Field(min_length=1, max_length=8)
    ejercicio: FilingYear
    period: Period
    expediente_id: AeatExpedienteId
    estado: str = Field(min_length=1, max_length=16)
    tipo_solicitud: str | None = Field(default=None, max_length=128)
    observaciones: str | None = Field(default=None, max_length=512)
    presented_at: datetime
    justificante_link_text: str | None = Field(default=None, max_length=32)
    archive_link_text: str | None = Field(default=None, max_length=32)
    declaration_copy_link_text: str | None = Field(default=None, max_length=32)
    justificante_cell_index: int = Field(default=7, ge=0)
    archive_cell_index: int | None = Field(default=8, ge=0)
    declaration_copy_cell_index: int | None = Field(default=None, ge=0)
    mode: Literal["read"] = "read"

    @model_validator(mode="after")
    def _period_year_matches_ejercicio(self) -> Self:
        if self.period.filing_year != self.ejercicio:
            raise ValueError("period.filing_year must match ejercicio")
        return self
