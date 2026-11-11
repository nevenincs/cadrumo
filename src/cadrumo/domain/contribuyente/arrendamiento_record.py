"""The lease of a property, as the facts fixed when the contract was signed.

A lease references one property by its row key and holds its contract date, its
period, its tenants and the facts that decide the tier of the art. 23.2 LIRPF
reduction. The reduction rate itself is not stored: it is derived from these
facts and dated registry data, so a fact the taxpayer has not stated stays
``None`` and the derivation refuses instead of reading a default.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Final, Self

from pydantic import BaseModel, Field, field_validator, model_validator

from ...core.errors.hierarchy import ProfileAnswerTypeError, pydantic_validation_boundary
from ...core.models import STRICT_FROZEN_CONFIG

#: The most tenants a lease states: the three numbered pairs of casillas 0091 to 0098 and the rows that follow.
MAX_INQUILINOS: Final = 9

_TAX_ID: Final = re.compile(r"^[0-9A-Z]{5,20}$")


class InquilinoEdad(StrEnum):
    """The age band of a natural-person tenant at signing."""

    DE_18_A_35 = "18_35"
    OTRA = "otra"
    NO_APLICA = "no_aplica"


class ArrendatarioEntidadTipo(StrEnum):
    """A tenant that is not a natural person but takes the reduction's qualifying treatment."""

    ADMINISTRACION_PUBLICA = "administracion_publica"
    ENTIDAD_SIN_FINES_LUCRO = "entidad_sin_fines_lucro"


class ArrendatarioEntidadFinalidad(StrEnum):
    """What the qualifying entity uses the dwelling for."""

    VIVIENDA_ASEQUIBLE_O_SOCIAL = "vivienda_asequible_o_social"
    OTRA = "otra"


def _refuse(message: str, *, field: str) -> ProfileAnswerTypeError:
    return ProfileAnswerTypeError(message, context={"key": field})


class Inquilino(BaseModel):
    """One tenant: the identifier, the age band and whether the identifier is foreign."""

    model_config = STRICT_FROZEN_CONFIG

    nif: str
    franja_edad: InquilinoEdad
    extranjero: bool

    @field_validator("nif")
    @classmethod
    @pydantic_validation_boundary
    def _identifier_shape(cls, value: str) -> str:
        canonical = value.strip().upper()
        if not _TAX_ID.fullmatch(canonical):
            raise _refuse("a tenant identifier has five to twenty letters and digits", field="inquilinos")
        return canonical


class ArrendamientoRecord(BaseModel):
    """One lease of the profile, addressed by ``clave``, the position of its row."""

    model_config = STRICT_FROZEN_CONFIG

    clave: int = Field(ge=0)
    inmueble: int = Field(ge=0)
    fecha_contrato: date
    fecha_inicio: date
    fecha_fin: date | None = None
    uso_vivienda: bool | None = None
    inquilinos: tuple[Inquilino, ...] = Field(default=(), max_length=MAX_INQUILINOS)
    zona_tensionada: bool | None = None
    primer_arrendamiento_vivienda: bool | None = None
    arrendatario_entidad_tipo: ArrendatarioEntidadTipo | None = None
    arrendatario_entidad_finalidad: ArrendatarioEntidadFinalidad | None = None
    rehabilitacion_fecha: date | None = None
    renta_inicial: Decimal | None = Field(default=None, ge=0)
    renta_ultima_contrato_anterior: Decimal | None = Field(default=None, ge=0)
    arrendatario_pariente_art24: bool | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _coherent(self) -> Self:
        if self.fecha_fin is not None and self.fecha_fin < self.fecha_inicio:
            raise _refuse("a lease cannot end before it starts", field="fecha_fin")
        if len({inquilino.nif for inquilino in self.inquilinos}) != len(self.inquilinos):
            raise _refuse("a tenant is stated once", field="inquilinos")
        if self.arrendatario_entidad_finalidad is not None and self.arrendatario_entidad_tipo is None:
            raise _refuse("a purpose needs the entity type it belongs to", field="arrendatario_entidad_finalidad")
        return self


__all__ = [
    "MAX_INQUILINOS",
    "ArrendamientoRecord",
    "ArrendatarioEntidadFinalidad",
    "ArrendatarioEntidadTipo",
    "Inquilino",
    "InquilinoEdad",
]
