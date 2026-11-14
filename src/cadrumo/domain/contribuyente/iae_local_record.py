"""The premises and tax elements of an IAE activity, as the Modelo 840 states them.

A local is one repeatable profile row tied to the activity row it serves. It
carries the address the record design lists for the local afecto
indirectamente (Apartado V) and the Anexo Relacion de locales, the uso o
destino of an indirectly affected local, and the Total, Rectificada and
Computable square metres the Anexo states for the local.

A surface class is its own repeatable row naming the local it belongs to: one
IAE Regla 14 class of Apartado VI C with its Total, Rectificada and Computable
square metres. Each figure is stated on its own; none is derived from another,
and a figure or class the taxpayer has not stated stays absent rather than
reading zero.

A tax element is one line of Apartado VI A: the element code, its description
and its number of units, for one activity.

Codes are the AEAT table codes the design names (provincia, municipio). They
are checked for shape only; the tables themselves are not bundled.
"""

from __future__ import annotations

import re
from decimal import Decimal
from enum import StrEnum
from typing import Final, Self

from pydantic import BaseModel, Field, ValidationInfo, field_validator, model_validator

from ...core.errors.hierarchy import ProfileAnswerTypeError, pydantic_validation_boundary
from ...core.models import STRICT_FROZEN_CONFIG

#: The widest whole-square-metre figure the design's five numeric positions hold.
SURFACE_MAXIMUM: Final = 99_999
#: The widest number of units Apartado VI A holds: seven integer digits and two decimals.
ELEMENT_UNITS_MAXIMUM: Final = Decimal("9999999.99")
#: The Apartado VI A lines the design opens; lines 5 to 8 are reserved.
ELEMENT_LINES: Final = range(1, 5)

_PROVINCE_CODE: Final = re.compile(r"^\d{2}$")
_MUNICIPALITY_CODE: Final = re.compile(r"^\d{5}$")
_POSTCODE: Final = re.compile(r"^\d{5}$")
_PHONE: Final = re.compile(r"^\d{9}$")
_TABLE_CODE: Final = re.compile(r"^[0-9A-Z]{2}$")
_CENTS: Final = Decimal("0.01")

#: Longest text each address leaf holds, from its width in the record design.
TEXT_WIDTHS: Final = {
    "via_nombre": 25,
    "km": 5,
    "portal": 4,
    "escalera": 2,
    "piso": 2,
    "puerta": 2,
    "municipality_name": 30,
    "uso_destino_description": 50,
    "description": 30,
}


def _refuse(message: str, *, field: str) -> ProfileAnswerTypeError:
    return ProfileAnswerTypeError(message, context={"key": field})


def admitted_code(value: str | None, *, field: str, pattern: re.Pattern[str], message: str) -> str | None:
    """Return ``value`` when it has the code's exact shape; refuse any other stated value."""
    if value is None:
        return None
    if not pattern.fullmatch(value):
        raise _refuse(message, field=field)
    return value


def admitted_text(value: str | None, *, field: str) -> str | None:
    """Return a stated text leaf when it fits its design width and is not blank."""
    if value is None:
        return None
    if not value.strip() or len(value) > TEXT_WIDTHS[field]:
        raise _refuse(f"write between 1 and {TEXT_WIDTHS[field]} characters", field=field)
    return value


def admitted_province_code(value: str | None, *, field: str) -> str | None:
    """A provincia code: two digits."""
    return admitted_code(value, field=field, pattern=_PROVINCE_CODE, message="a provincia code has two digits")


def admitted_municipality_code(value: str | None, *, field: str) -> str | None:
    """A municipio code: five digits."""
    return admitted_code(value, field=field, pattern=_MUNICIPALITY_CODE, message="a municipio code has five digits")


class SuperficieRegla14Clase(StrEnum):
    """The surface classes Modelo 840 Apartado VI C lists, under IAE Regla 14."""

    SIN_REDUCCION = "0.1"
    HOSPEDAJE = "0.2"
    DESCUBIERTA = "1.1"
    INSTALACION_DEPORTIVA_DESCUBIERTA = "1.2"
    GRADAS_DESCUBIERTAS = "1.3"
    PUESTO_TEMPORADA = "2.0"
    CUBIERTA_DEPORTIVA_ESPECTACULO = "3.1"
    GRADAS_CUBIERTAS = "3.2"
    ENSENANZA = "4.0"
    ALMACEN = "5.0"
    APARCAMIENTO_CUBIERTO = "6.0"


class IaeLocalSuperficieRecord(BaseModel):
    """One Regla 14 class of a local, addressed by ``clave``, the never-reused position of its row."""

    model_config = STRICT_FROZEN_CONFIG

    clave: int = Field(ge=0)
    local: int = Field(ge=0)
    clase: SuperficieRegla14Clase
    total: int | None = Field(default=None, ge=0, le=SURFACE_MAXIMUM)
    rectificada: int | None = Field(default=None, ge=0, le=SURFACE_MAXIMUM)
    computable: int | None = Field(default=None, ge=0, le=SURFACE_MAXIMUM)


class IaeLocalAfectacion(StrEnum):
    """How a local serves its activity."""

    #: The activity is exercised in it (Apartado VI C, Anexo Relacion de locales).
    EJERCICIO = "ejercicio"
    #: It is afecto indirectamente to the activity (Apartado V).
    INDIRECTA = "indirecta"


class IaeLocalRecord(BaseModel):
    """One local of the profile, addressed by ``clave``, the never-reused position of its row."""

    model_config = STRICT_FROZEN_CONFIG

    clave: int = Field(ge=0)
    actividad: int = Field(ge=0)
    afectacion: IaeLocalAfectacion
    via_sg: str | None = None
    via_nombre: str | None = None
    numero: int | None = Field(default=None, ge=0, le=99_999)
    km: str | None = None
    portal: str | None = None
    escalera: str | None = None
    piso: str | None = None
    puerta: str | None = None
    postcode: str | None = None
    province_code: str | None = None
    municipality_code: str | None = None
    municipality_name: str | None = None
    telefono: str | None = None
    uso_destino_code: str | None = None
    uso_destino_description: str | None = None
    superficie_total: int | None = Field(default=None, ge=0, le=SURFACE_MAXIMUM)
    superficie_rectificada: int | None = Field(default=None, ge=0, le=SURFACE_MAXIMUM)
    superficie_computable: int | None = Field(default=None, ge=0, le=SURFACE_MAXIMUM)

    @field_validator("via_nombre", "km", "portal", "escalera", "piso", "puerta", "municipality_name")
    @classmethod
    @pydantic_validation_boundary
    def _address_text(cls, value: str | None, info: ValidationInfo) -> str | None:
        return admitted_text(value, field=str(info.field_name))

    @field_validator("uso_destino_description")
    @classmethod
    @pydantic_validation_boundary
    def _use_text(cls, value: str | None) -> str | None:
        return admitted_text(value, field="uso_destino_description")

    @field_validator("via_sg", "uso_destino_code")
    @classmethod
    @pydantic_validation_boundary
    def _table_code(cls, value: str | None, info: ValidationInfo) -> str | None:
        field = str(info.field_name)
        return admitted_code(value, field=field, pattern=_TABLE_CODE, message="a table code has two letters or digits")

    @field_validator("province_code")
    @classmethod
    @pydantic_validation_boundary
    def _province(cls, value: str | None) -> str | None:
        return admitted_province_code(value, field="province_code")

    @field_validator("municipality_code")
    @classmethod
    @pydantic_validation_boundary
    def _municipality(cls, value: str | None) -> str | None:
        return admitted_municipality_code(value, field="municipality_code")

    @field_validator("postcode")
    @classmethod
    @pydantic_validation_boundary
    def _postcode(cls, value: str | None) -> str | None:
        return admitted_code(value, field="postcode", pattern=_POSTCODE, message="a postcode has five digits")

    @field_validator("telefono")
    @classmethod
    @pydantic_validation_boundary
    def _phone(cls, value: str | None) -> str | None:
        return admitted_code(value, field="telefono", pattern=_PHONE, message="a telephone number has nine digits")

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _coherent(self) -> Self:
        if self.afectacion is IaeLocalAfectacion.EJERCICIO and (
            self.uso_destino_code is not None or self.uso_destino_description is not None
        ):
            raise _refuse("only a local afecto indirectamente states its uso o destino", field="uso_destino_code")
        return self


class IaeElementoTributarioRecord(BaseModel):
    """One Apartado VI A line of an activity, addressed by ``clave``, its row position."""

    model_config = STRICT_FROZEN_CONFIG

    clave: int = Field(ge=0)
    actividad: int = Field(ge=0)
    linea: int = Field(ge=ELEMENT_LINES.start, le=ELEMENT_LINES.stop - 1)
    code: str
    description: str | None = None
    numero: Decimal = Field(ge=0, le=ELEMENT_UNITS_MAXIMUM)

    @field_validator("code")
    @classmethod
    @pydantic_validation_boundary
    def _code(cls, value: str) -> str:
        if not _TABLE_CODE.fullmatch(value):
            raise _refuse("an element code has two letters or digits", field="code")
        return value

    @field_validator("description")
    @classmethod
    @pydantic_validation_boundary
    def _description(cls, value: str | None) -> str | None:
        return admitted_text(value, field="description")

    @field_validator("numero")
    @classmethod
    @pydantic_validation_boundary
    def _two_decimals(cls, value: Decimal) -> Decimal:
        if not value.is_finite() or value != value.quantize(_CENTS):
            raise _refuse("write a number of units with at most two decimals", field="numero")
        return value


__all__ = [
    "ELEMENT_LINES",
    "ELEMENT_UNITS_MAXIMUM",
    "SURFACE_MAXIMUM",
    "TEXT_WIDTHS",
    "IaeElementoTributarioRecord",
    "IaeLocalAfectacion",
    "IaeLocalRecord",
    "IaeLocalSuperficieRecord",
    "SuperficieRegla14Clase",
    "admitted_code",
    "admitted_municipality_code",
    "admitted_province_code",
    "admitted_text",
]
