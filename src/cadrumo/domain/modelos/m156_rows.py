"""Typed member facts for the Modelo 156 annual contribution record.

AEAT's type-2 design declares twelve independent monthly S/N indicators and
contribution amounts. Missing facts remain missing; N does not imply zero.
These records do not by themselves enroll a filing or editor capability.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.models import STRICT_FROZEN_CONFIG
from ..calculations.registry.form_codes import require_form_fit, require_form_width


class Modelo156MonthlyContribution(BaseModel):
    """One explicitly addressed calendar month, with independent source facts."""

    model_config = STRICT_FROZEN_CONFIG

    month: int = Field(ge=1, le=12)
    status: Literal["S", "N"] | None = None
    amount: Decimal | None = Field(default=None, ge=Decimal("0"), allow_inf_nan=False)


class Modelo156AfiliadoRow(BaseModel):
    """One affiliate; membership number remains text to retain leading zeros."""

    model_config = STRICT_FROZEN_CONFIG

    row_type: Literal["afiliado"] = "afiliado"
    nif: str = Field(min_length=1, max_length=64)
    nombre: str | None = Field(default=None, min_length=1, max_length=256)
    numero_afiliacion: str = Field(pattern=r"^[0-9]+$", max_length=64)
    cotizaciones: tuple[Modelo156MonthlyContribution, ...]

    @field_validator("nif")
    @classmethod
    @pydantic_validation_boundary
    def _nif_fits_the_design(cls, value: str) -> str:
        require_form_fit(value, "m156.nif_max")
        return value

    @field_validator("nombre")
    @classmethod
    @pydantic_validation_boundary
    def _nombre_fits_the_design(cls, value: str | None) -> str | None:
        return require_form_fit(value, "m156.nombre_max")

    @field_validator("numero_afiliacion")
    @classmethod
    @pydantic_validation_boundary
    def _numero_has_the_declared_width(cls, value: str) -> str:
        require_form_width(value, "m156.numero_afiliacion_digits")
        return value

    @field_validator("cotizaciones")
    @classmethod
    @pydantic_validation_boundary
    def _complete_calendar(
        cls, values: tuple[Modelo156MonthlyContribution, ...]
    ) -> tuple[Modelo156MonthlyContribution, ...]:
        if {value.month for value in values} != set(range(1, 13)):
            raise ValueError("monthly contributions must name each calendar month exactly once")
        return tuple(sorted(values, key=lambda value: value.month))
