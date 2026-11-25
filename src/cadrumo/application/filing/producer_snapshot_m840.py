"""Typed filing facts for Modelo 840: the declaration header, its activity and its premises.

The pages state the AEAT Delegación and Administración, the municipality names that
pair with the coded casillas, the Apartado VI A tax elements, the Apartado VI B
machines and the Apartado VI C surface classes of the one local the declaration
covers. The Anexo "Relación de locales" lists the premises where the activity is
carried on, with their address and their Regla 14 surfaces. Every value comes from the
operator's stored profile facts; nothing here derives or defaults one, and an absent
member is an absent fact that renders the field's blank fill, never a zero.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from ...core.models import STRICT_FROZEN_CONFIG
from ...domain.contribuyente.iae_local_record import (
    ELEMENT_LINES,
    ELEMENT_UNITS_MAXIMUM,
    SURFACE_MAXIMUM,
    SuperficieRegla14Clase,
)

_Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
_Name = Annotated[str, StringConstraints(min_length=1, max_length=30)]
_Digits = Annotated[str, StringConstraints(pattern=r"^\d+$")]
_SquareMetres = Annotated[int, Field(ge=0, le=SURFACE_MAXIMUM)]
_Units = Annotated[int, Field(ge=0, le=9_999_999)]
#: DR840 types the Anexo "Núm." Num, so a street number is a whole number; its field width bounds it.
_StreetNumber = Annotated[int, Field(ge=0)]


class Modelo840LocalRow(BaseModel):
    """One Apartado II premises row of the Modelo 840 Anexo.

    Members are ``M840LocalField``'s values verbatim, so the projection reference and the
    row that answers it stay in lock-step. An absent member is an absent fact and renders
    the slot's blank fill; it is never a zero.
    """

    model_config = STRICT_FROZEN_CONFIG

    sg_tabla: _Text | None = None
    nombre_via: _Text | None = None
    numero: _StreetNumber | None = None
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


class Modelo840ElementoLinea(BaseModel):
    """One Apartado VI A line: the element's two-character code, its description and its units."""

    model_config = STRICT_FROZEN_CONFIG

    linea: int = Field(ge=ELEMENT_LINES.start, le=ELEMENT_LINES.stop - 1)
    codigo: Annotated[str, StringConstraints(pattern=r"^[0-9A-Z]{2}$")]
    descripcion: Annotated[str, StringConstraints(min_length=1, max_length=30)] | None = None
    numero: Decimal = Field(ge=Decimal(0), le=ELEMENT_UNITS_MAXIMUM)


class Modelo840SuperficieClase(BaseModel):
    """One Apartado VI C Regla 14 class of the declared local, each figure stated on its own."""

    model_config = STRICT_FROZEN_CONFIG

    clase: SuperficieRegla14Clase
    total: _SquareMetres | None = None
    rectificada: _SquareMetres | None = None
    computable: _SquareMetres | None = None


class Modelo840ProfileFacts(BaseModel):
    """The stored facts a Modelo 840 states, for the one activity it declares."""

    model_config = STRICT_FROZEN_CONFIG

    local_rows: tuple[Modelo840LocalRow, ...] = ()
    delegacion_codigo: Annotated[str, StringConstraints(pattern=r"^\d{2}$")] | None = None
    administracion_codigo: Annotated[str, StringConstraints(pattern=r"^\d{3}$")] | None = None
    administracion_nombre: Annotated[str, StringConstraints(min_length=1, max_length=20)] | None = None
    sujeto_pasivo_municipio: _Name | None = None
    actividad_provincia_codigo: Annotated[str, StringConstraints(pattern=r"^\d{2}$")] | None = None
    actividad_municipio: _Name | None = None
    local_indirecto_municipio: _Name | None = None
    elementos: tuple[Modelo840ElementoLinea, ...] = ()
    maquinas_tipo_a: _Units | None = None
    maquinas_tipo_b: _Units | None = None
    expositores_autoventa: _Units | None = None
    superficies: tuple[Modelo840SuperficieClase, ...] = ()


__all__ = [
    "Modelo840ElementoLinea",
    "Modelo840LocalRow",
    "Modelo840ProfileFacts",
    "Modelo840SuperficieClase",
]
