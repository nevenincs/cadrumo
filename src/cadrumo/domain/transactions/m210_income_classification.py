"""Typed Modelo 210 income-classification boundary.

The selected Modelo 210 registry revision owns the income-code catalogue,
labels, and payer applicability. This module retains only the transaction
validation/type shell while that registry declaration is consumed by the
calculation path.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from ...core.irnr import M210PayerMode
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.unit_proportion import UnitProportion
from .errors import TransactionValidationError


class M210IncomeClassification(BaseModel):
    """One operator-supplied M210 income classification."""

    model_config = STRICT_FROZEN_CONFIG

    official_tipo_renta_code: str = Field(min_length=2, max_length=2)
    gross_income_amount: Decimal = Field(ge=Decimal("0"))
    applicable_rate: UnitProportion
    payer_mode: M210PayerMode = M210PayerMode.SINGLE_PAYER
    payer_id: str | None = Field(default=None, min_length=1, max_length=128)
    asset_or_right_id: str | None = Field(default=None, min_length=1, max_length=128)

    @field_validator("official_tipo_renta_code")
    @classmethod
    def _validate_official_tipo_renta_code(cls, value: str) -> str:
        code = value.strip()
        if not code.isdecimal():
            raise TransactionValidationError(
                "official_tipo_renta_code must be a two-character numeric code",
            )
        # TODO(fact-relocation): resolve M210 income-code catalogue and multiple-payer applicability from selected registry revision
        return code

    @field_validator("payer_mode", mode="before")
    @classmethod
    def _coerce_payer_mode(cls, value: object) -> object:
        if isinstance(value, str) and not isinstance(value, M210PayerMode):
            return M210PayerMode(value)
        return value

    @field_validator("payer_id", "asset_or_right_id")
    @classmethod
    def _trim_optional_identity(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        return trimmed or None


__all__ = ["M210IncomeClassification"]
