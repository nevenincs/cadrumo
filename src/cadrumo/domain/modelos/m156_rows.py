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
    nif: str = Field(min_length=1, max_length=9)
    nombre: str | None = Field(default=None, min_length=1, max_length=40)
    numero_afiliacion: str = Field(pattern=r"^[0-9]{12}$")
    cotizaciones: tuple[Modelo156MonthlyContribution, ...] = Field(min_length=12, max_length=12)

    @field_validator("cotizaciones")
    @classmethod
    @pydantic_validation_boundary
    def _complete_calendar(
        cls, values: tuple[Modelo156MonthlyContribution, ...]
    ) -> tuple[Modelo156MonthlyContribution, ...]:
        if {value.month for value in values} != set(range(1, 13)):
            raise ValueError("monthly contributions must name each calendar month exactly once")
        return tuple(sorted(values, key=lambda value: value.month))
