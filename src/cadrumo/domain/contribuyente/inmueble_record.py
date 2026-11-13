"""The property a taxpayer lets, as identification and structural facts.

A record holds what stays true of a property from one ejercicio to the next:
where it is, who holds it and in what right, how it was acquired, its dated
cadastral values, the uses other than letting it has had and, for an
accessory, the property it is let with. It never holds an annual total:
amounts come from the ledger rows that prove them.

Every refusal is a typed error that names the field and never echoes the value
typed. A fact the taxpayer has not stated stays ``None``; the calculation that
needs it refuses that property with its own reason instead of reading zero.

The row key is the position of the record in its profile section. The profile
never reuses a position, so a ledger row or a lease that names it keeps naming
the same property after other properties are removed.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Final, Self

from pydantic import BaseModel, Field, ValidationInfo, field_validator, model_validator

from ...core.errors.hierarchy import ProfileAnswerTypeError, pydantic_validation_boundary
from ...core.models import STRICT_FROZEN_CONFIG

_CATASTRAL_REFERENCE: Final = re.compile(r"^[0-9A-Z]{20}$")
_CENTS: Final = Decimal("0.01")
_PERCENT_CEILING: Final = Decimal(100)


class InmuebleSituacion(StrEnum):
    """Clave of casilla 0065: where the property is and whether it has a cadastral reference."""

    CATASTRAL_COMUN = "1"
    CATASTRAL_PAIS_VASCO = "2"
    CATASTRAL_NAVARRA = "3"
    SIN_REFERENCIA = "4"
    EXTRANJERO = "5"

    @property
    def carries_catastral_reference(self) -> bool:
        """Report whether the clave requires the property's cadastral reference."""
        return self in (self.CATASTRAL_COMUN, self.CATASTRAL_PAIS_VASCO, self.CATASTRAL_NAVARRA)


class InmuebleNaturaleza(StrEnum):
    """Urban or rustic nature of the property (casillas 0067 and 0068)."""

    URBANA = "urbana"
    RUSTICA = "rustica"


class TitularidadRegimen(StrEnum):
    """The right the taxpayer holds over the property."""

    PLENO_DOMINIO = "pleno_dominio"
    NUDA_PROPIEDAD = "nuda_propiedad"
    USUFRUCTO = "usufructo"
    PLENO_DOMINIO_Y_USUFRUCTO = "pleno_dominio_y_usufructo"


class TitularRole(StrEnum):
    """The member of the family unit that holds the property (casilla 0062)."""

    PRIMER_DECLARANTE = "primer_declarante"
    CONYUGE = "conyuge"
    HIJO = "hijo"
    COMUN = "comun"


class AdquisicionTitulo(StrEnum):
    """Whether the property was acquired for value or for free (casillas 0118 and 0119)."""

    ONEROSA = "onerosa"
    LUCRATIVA = "lucrativa"


class ImportesMovimientos(StrEnum):
    """Whether the ledger rows linked to a co-owned property hold whole-property amounts or the taxpayer's own share."""

    INMUEBLE_COMPLETO = "inmueble_completo"
    PARTE_PROPIA = "parte_propia"


class UsoInmuebleTipo(StrEnum):
    """A use of the property other than letting."""

    VIVIENDA_HABITUAL = "vivienda_habitual"
    DISPOSICION_PROPIETARIO = "disposicion_propietario"
    ACTIVIDAD_ECONOMICA = "actividad_economica"


def _refuse(message: str, *, field: str) -> ProfileAnswerTypeError:
    return ProfileAnswerTypeError(message, context={"key": field})


def _two_decimals(value: Decimal) -> bool:
    return value == value.quantize(_CENTS)


class InmuebleTitularidad(BaseModel):
    """Who holds the property and in what right, as the titularidad ruling states it.

    A percentage carries at most two decimals and lies in ``(0, 100]``; the pair
    never sums beyond 100; each regime requires exactly the percentages it
    attributes; a hijo titular names the child's ordinal and no other titular does.
    """

    model_config = STRICT_FROZEN_CONFIG

    regimen: TitularidadRegimen
    titular: TitularRole
    hijo_ordinal: int | None = Field(default=None, ge=1)
    porcentaje_propiedad: Decimal | None = None
    porcentaje_usufructo: Decimal | None = None

    @field_validator("porcentaje_propiedad", "porcentaje_usufructo")
    @classmethod
    @pydantic_validation_boundary
    def _percentage_is_declarable(cls, value: Decimal | None, info: ValidationInfo) -> Decimal | None:
        if value is None:
            return None
        if value <= 0 or value > _PERCENT_CEILING or not _two_decimals(value):
            raise _refuse(
                "a titularidad percentage lies above 0 up to 100 with two decimals",
                field=info.field_name or "porcentaje_propiedad",
            )
        return value

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _coherent(self) -> Self:
        if (self.titular is TitularRole.HIJO) != (self.hijo_ordinal is not None):
            raise _refuse("only a hijo titular carries, and always carries, the child's ordinal", field="titular")
        owns = self.porcentaje_propiedad is not None
        usufruct = self.porcentaje_usufructo is not None
        required = {
            TitularidadRegimen.PLENO_DOMINIO: (True, False),
            TitularidadRegimen.NUDA_PROPIEDAD: (True, False),
            TitularidadRegimen.USUFRUCTO: (False, True),
            TitularidadRegimen.PLENO_DOMINIO_Y_USUFRUCTO: (True, True),
        }[self.regimen]
        if (owns, usufruct) != required:
            raise _refuse("the percentages stated contradict the titularidad regime", field="titularidad_regimen")
        if (self.porcentaje_propiedad or 0) + (self.porcentaje_usufructo or 0) > _PERCENT_CEILING:
            raise _refuse("the titularidad percentages sum beyond 100", field="porcentaje_usufructo")
        return self


class ValorCatastral(BaseModel):
    """The cadastral values of one IBI year: total (casilla 0123) and construction (casilla 0124).

    ``vigor`` is the year the general collective valuation that set these values
    entered into force, which decides the art. 85 imputation rate; ``None`` when
    it is not stated. It can never follow the IBI year it set.
    """

    model_config = STRICT_FROZEN_CONFIG

    year: int = Field(gt=0)
    total: Decimal = Field(ge=0)
    construccion: Decimal = Field(ge=0)
    vigor: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _construction_within_total(self) -> Self:
        if self.construccion > self.total:
            raise _refuse("the construction value cannot exceed the total cadastral value", field="valores_catastrales")
        if self.vigor is not None and self.vigor > self.year:
            raise _refuse(
                "a collective valuation cannot enter into force after the IBI year it sets", field="valores_catastrales"
            )
        return self


class UsoInmueble(BaseModel):
    """A dated interval in which the property served a use other than letting."""

    model_config = STRICT_FROZEN_CONFIG

    tipo: UsoInmuebleTipo
    desde: date
    hasta: date | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _interval_is_ordered(self) -> Self:
        if self.hasta is not None and self.hasta < self.desde:
            raise _refuse("a use cannot end before it starts", field="usos")
        return self

    def overlaps(self, other: UsoInmueble) -> bool:
        """Report whether two uses of the same type share a day."""
        if self.tipo is not other.tipo:
            return False
        return (self.hasta is None or other.desde <= self.hasta) and (other.hasta is None or self.desde <= other.hasta)


class MejoraInmueble(BaseModel):
    """An improvement made before the ledger covers the property; it is capitalised."""

    model_config = STRICT_FROZEN_CONFIG

    fecha: date
    importe: Decimal = Field(gt=0)


def canonical_referencia_catastral(raw: str, *, field: str) -> str:
    """Return the cadastral reference in its canonical upper-case form or refuse it."""
    canonical = raw.strip().upper()
    if not _CATASTRAL_REFERENCE.fullmatch(canonical):
        raise _refuse("a cadastral reference has twenty letters and digits", field=field)
    return canonical


class InmuebleRecord(BaseModel):
    """One property of the profile, addressed by ``clave``, the position of its row."""

    model_config = STRICT_FROZEN_CONFIG

    clave: int = Field(ge=0)
    situacion: InmuebleSituacion
    referencia_catastral: str | None = None
    naturaleza: InmuebleNaturaleza | None = None
    direccion: str | None = None
    titularidad: InmuebleTitularidad | None = None
    adquisicion_titulo: AdquisicionTitulo | None = None
    fecha_adquisicion: date | None = None
    fecha_transmision: date | None = None
    importe_adquisicion: Decimal | None = Field(default=None, ge=0)
    gastos_tributos_adquisicion: Decimal | None = Field(default=None, ge=0)
    valor_suelo: Decimal | None = Field(default=None, ge=0)
    mejoras: tuple[MejoraInmueble, ...] = ()
    valores_catastrales: tuple[ValorCatastral, ...] = ()
    usos: tuple[UsoInmueble, ...] = ()
    inmueble_principal: int | None = Field(default=None, ge=0)
    importes_movimientos: ImportesMovimientos | None = None
    amortizacion_acumulada: Decimal | None = Field(default=None, ge=0)
    amortizacion_acumulada_desde: date | None = None
    arrendado_desde: date | None = None
    sin_arrendar: bool = False
    """With ``arrendado_desde``: unstated (no date, ``False``), first let on a date, or never let (``True``)."""

    @field_validator("referencia_catastral")
    @classmethod
    @pydantic_validation_boundary
    def _reference_shape(cls, value: str | None) -> str | None:
        return None if value is None else canonical_referencia_catastral(value, field="referencia_catastral")

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _coherent(self) -> Self:
        _require_reference_matches_situacion(self)
        _require_ordered_acquisition(self)
        _require_distinct_years(self.valores_catastrales, field="valores_catastrales")
        _require_ownership_coherent(self)
        _require_disjoint_uses(self.usos)
        if (self.amortizacion_acumulada is None) != (self.amortizacion_acumulada_desde is None):
            raise _refuse(
                "the attested cumulative amortisation and the date it is attested to travel together",
                field="amortizacion_acumulada",
            )
        if self.sin_arrendar and self.arrendado_desde is not None:
            raise _refuse("a property never let has no date it was first let", field="arrendado_desde")
        return self


def require_letting_start_before_leases(record: InmuebleRecord, lease_starts: Iterable[date]) -> None:
    """Refuse a letting start later than the start of any lease of the property, and a lease of a property never let.

    The earliest lease start never stands in for an unstated ``arrendado_desde``;
    this only judges two stated facts against each other.
    """
    starts = tuple(lease_starts)
    if record.sin_arrendar and starts:
        raise _refuse("a property with a lease has been let", field="sin_arrendar")
    if record.arrendado_desde is not None and any(start < record.arrendado_desde for start in starts):
        raise _refuse("the property cannot be first let after one of its leases starts", field="arrendado_desde")


def _require_reference_matches_situacion(record: InmuebleRecord) -> None:
    if record.situacion.carries_catastral_reference != (record.referencia_catastral is not None):
        raise _refuse(
            "the cadastral reference is required with claves 1 to 3 and absent with the others",
            field="referencia_catastral",
        )


def _require_ordered_acquisition(record: InmuebleRecord) -> None:
    acquired, transmitted = record.fecha_adquisicion, record.fecha_transmision
    if acquired is not None and transmitted is not None and transmitted < acquired:
        raise _refuse("the property cannot be transmitted before it is acquired", field="fecha_transmision")
    land, amount = record.valor_suelo, record.importe_adquisicion
    if land is not None and amount is not None and land > amount:
        raise _refuse("the land value cannot exceed the acquisition amount", field="valor_suelo")


def _require_ownership_coherent(record: InmuebleRecord) -> None:
    if record.inmueble_principal is not None and record.inmueble_principal == record.clave:
        raise _refuse("an accessory property cannot be its own principal", field="inmueble_principal")
    share = record.titularidad.porcentaje_propiedad if record.titularidad is not None else None
    if share is not None and share < _PERCENT_CEILING and record.importes_movimientos is None:
        raise _refuse(
            "a co-owned property states whether its ledger rows hold whole-property or own-share amounts",
            field="importes_movimientos",
        )


def _require_disjoint_uses(usos: tuple[UsoInmueble, ...]) -> None:
    for index, uso in enumerate(usos):
        if any(uso.overlaps(other) for other in usos[index + 1 :]):
            raise _refuse("two uses of the same type cannot share a day", field="usos")


def _require_distinct_years(values: tuple[ValorCatastral, ...], *, field: str) -> None:
    if len({valor.year for valor in values}) != len(values):
        raise _refuse("an IBI year carries one cadastral value", field=field)


__all__ = [
    "AdquisicionTitulo",
    "ImportesMovimientos",
    "InmuebleNaturaleza",
    "InmuebleRecord",
    "InmuebleSituacion",
    "InmuebleTitularidad",
    "MejoraInmueble",
    "TitularRole",
    "TitularidadRegimen",
    "UsoInmueble",
    "UsoInmuebleTipo",
    "ValorCatastral",
    "canonical_referencia_catastral",
    "require_letting_start_before_leases",
]
