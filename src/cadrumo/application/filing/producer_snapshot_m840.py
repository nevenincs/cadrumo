"""Typed filing facts for the Modelo 840 Anexo premises.

The Anexo "Relación de locales" lists the premises where an activity is carried on or
that serve it, with their address and their Regla 14 surfaces. The rows come from the
operator's stored IAE premises; nothing here derives or defaults one.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from ...core.models import STRICT_FROZEN_CONFIG

_Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
_Digits = Annotated[str, StringConstraints(pattern=r"^\d+$")]
_SquareMetres = Annotated[int, Field(ge=0)]


class Modelo840LocalRow(BaseModel):
    """One Apartado II premises row of the Modelo 840 Anexo.

    Members are ``M840LocalField``'s values verbatim, so the projection reference and the
    row that answers it stay in lock-step. An absent member is an absent fact and renders
    the slot's blank fill; it is never a zero.
    """

    model_config = STRICT_FROZEN_CONFIG

    sg_tabla: _Text | None = None
    nombre_via: _Text | None = None
    numero: _Digits | None = None
    km: _Text | None = None
    escalera: _Text | None = None
    piso: _Text | None = None
    puerta: _Text | None = None
    codigo_postal: _Digits | None = None
    provincia_codigo: _Text | None = None
    municipio_codigo: _Text | None = None
    municipio_nombre: _Text | None = None
    total: _SquareMetres | None = None
    rectificada: _SquareMetres | None = None
    computable: _SquareMetres | None = None


class Modelo840ProfileFacts(BaseModel):
    """The premises rows a Modelo 840 Anexo lists, in the order the operator stored them."""

    model_config = STRICT_FROZEN_CONFIG

    local_rows: tuple[Modelo840LocalRow, ...] = ()


__all__ = ["Modelo840LocalRow", "Modelo840ProfileFacts"]
