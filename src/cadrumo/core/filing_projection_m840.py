"""Typed premises and anexo-sheet references for Modelo 840 filing projections.

The DR840 Anexo record ("Relación de locales") prints nine premises slots on one
sheet, and the form numbers its sheets ("Hoja") with a "C (Compl.)" indicator on
a further one, each sheet closing with its own partial sums. So a premises row is
addressed by its slot inside the sheet, and the sheet by its render occurrence:
the tenth premises opens a second sheet rather than being refused or dropped.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

from .models import STRICT_FROZEN_CONFIG


class M840LocalField(StrEnum):
    """Closed fields of one Apartado II premises row, transcribed from the DR840 Anexo."""

    SG_TABLA = "sg_tabla"
    NOMBRE_VIA = "nombre_via"
    NUMERO = "numero"
    KM = "km"
    ESCALERA = "escalera"
    PISO = "piso"
    PUERTA = "puerta"
    CODIGO_POSTAL = "codigo_postal"
    PROVINCIA_CODIGO = "provincia_codigo"
    MUNICIPIO_CODIGO = "municipio_codigo"
    MUNICIPIO_NOMBRE = "municipio_nombre"
    #: AEAT labels the three surface columns only Total, Rectificada and Computable.
    TOTAL = "total"
    RECTIFICADA = "rectificada"
    COMPUTABLE = "computable"


class M840LocalProjectionRef(BaseModel):
    """One field of the premises row printed in a numbered slot of an Anexo sheet."""

    model_config = STRICT_FROZEN_CONFIG

    projection_kind: Literal["m840_local"]
    slot: int = Field(ge=1)
    field: M840LocalField


class M840AnexoHojaField(StrEnum):
    """Closed per-sheet fields of the DR840 Anexo: the partial sums of its premises slots."""

    SUMA_PARCIAL_TOTAL = "suma_parcial_total"
    SUMA_PARCIAL_RECTIFICADA = "suma_parcial_rectificada"
    SUMA_PARCIAL_COMPUTABLE = "suma_parcial_computable"


class M840AnexoHojaProjectionRef(BaseModel):
    """One per-sheet field of a Modelo 840 Anexo sheet.

    No slot: the record repeats once per sheet and the occurrence identifies it.
    """

    model_config = STRICT_FROZEN_CONFIG

    projection_kind: Literal["m840_anexo_hoja"]
    field: M840AnexoHojaField


__all__ = [
    "M840AnexoHojaField",
    "M840AnexoHojaProjectionRef",
    "M840LocalField",
    "M840LocalProjectionRef",
]
