"""Declaration-register boundary records."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

__all__ = ["Declaracion"]

_STRICT_FROZEN = ConfigDict(
    strict=True,
    frozen=True,
    extra="forbid",
)


class Declaracion(BaseModel):
    """One row from *Consultar declaraciones presentadas*."""

    model_config = _STRICT_FROZEN

    modelo: str = Field(min_length=1, max_length=8)
    ejercicio: int = Field(ge=2000, le=2099)
    period: str = Field(min_length=1, max_length=8)
    expediente_id: str = Field(min_length=12, max_length=32)
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
