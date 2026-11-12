"""A saver's position: an account, a term deposit or a securities account.

A record holds what identifies the position from one ejercicio to the next: its
kind, the entity that pays its income, the state the income comes from, the
taxpayer's ownership share over a dated interval and the operator's own
identifier for it. It never holds an amount: income comes from the ledger rows
that prove it, and the withholding from the payer's record.

The payer's identifier is the key that joins the position to the payer's
suffered-withholding record. The record only checks its shape; the checksum and
the state's catalogue membership are judged where the pinned authority is held.

The row key is the position of the record in its profile section. The profile
never reuses a position, so a ledger row that names it keeps naming the same
position after other positions are removed.
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

_CENTS: Final = Decimal("0.01")
_PERCENT_CEILING: Final = Decimal(100)
_PAYER_ID: Final = re.compile(r"^[0-9A-Z]{5,20}$")
_COUNTRY: Final = re.compile(r"^[A-Z]{2}$")
_NAME_LIMIT: Final = 256
_IDENTIFIER_LIMIT: Final = 64


class PosicionTipo(StrEnum):
    """The kind of position; later records extend this closed set."""

    CUENTA = "cuenta"
    DEPOSITO = "deposito"
    VALORES_NEGOCIABLES = "valores_negociables"


def _refuse(message: str, *, field: str) -> ProfileAnswerTypeError:
    return ProfileAnswerTypeError(message, context={"key": field})


def canonical_payer_identifier(raw: str, *, field: str) -> str:
    """Return a payer identifier in its canonical upper-case form or refuse its shape."""
    canonical = raw.strip().upper()
    if not _PAYER_ID.fullmatch(canonical):
        raise _refuse("a payer identifier has five to twenty letters and digits", field=field)
    return canonical


class PosicionRecord(BaseModel):
    """One position of the profile, addressed by ``clave``, the position of its row."""

    model_config = STRICT_FROZEN_CONFIG

    clave: int = Field(ge=0)
    tipo: PosicionTipo
    pagador_nif: str
    pagador_nombre: str
    pais_origen: str
    porcentaje_titularidad: Decimal
    fecha_inicio: date
    fecha_fin: date | None = None
    identificador: str | None = None

    @field_validator("pagador_nif")
    @classmethod
    @pydantic_validation_boundary
    def _payer_identifier_shape(cls, value: str) -> str:
        return canonical_payer_identifier(value, field="pagador_nif")

    @field_validator("pagador_nombre")
    @classmethod
    @pydantic_validation_boundary
    def _payer_name_stated(cls, value: str) -> str:
        name = value.strip()
        if not name or len(name) > _NAME_LIMIT:
            raise _refuse("a payer name is stated, in at most 256 characters", field="pagador_nombre")
        return name

    @field_validator("pais_origen")
    @classmethod
    @pydantic_validation_boundary
    def _country_shape(cls, value: str) -> str:
        code = value.strip().upper()
        if not _COUNTRY.fullmatch(code):
            raise _refuse("a source state is its two-letter ISO 3166-1 code", field="pais_origen")
        return code

    @field_validator("porcentaje_titularidad")
    @classmethod
    @pydantic_validation_boundary
    def _share_is_declarable(cls, value: Decimal) -> Decimal:
        if value <= 0 or value > _PERCENT_CEILING or value != value.quantize(_CENTS):
            raise _refuse("an ownership share lies above 0 up to 100 with two decimals", field="porcentaje_titularidad")
        return value

    @field_validator("identificador")
    @classmethod
    @pydantic_validation_boundary
    def _identifier_stated(cls, value: str | None) -> str | None:
        if value is None:
            return None
        identifier = value.strip()
        if not identifier or len(identifier) > _IDENTIFIER_LIMIT:
            raise _refuse("an identifier is stated, in at most 64 characters", field="identificador")
        return identifier

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _interval_is_ordered(self) -> Self:
        if self.fecha_fin is not None and self.fecha_fin < self.fecha_inicio:
            raise _refuse("an ownership share cannot end before it starts", field="fecha_fin")
        return self


__all__ = ["PosicionRecord", "PosicionTipo", "canonical_payer_identifier"]
