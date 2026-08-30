"""Explicit, persisted Modelo 210 income classifications for ledger rows.

The generic IRPF category on a transaction cannot identify the official M210
tipo-de-renta code. This record is therefore an independent, operator-supplied
IRNR classification: it preserves the official code and the component facts
needed by the M210 source projection without inferring either from a generic
ledger category or bank narrative.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field, field_validator, model_validator

from ...core import M210_TIPO_RENTA_CODE_PROJECTION, M210PayerMode
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.unit_proportion import UnitProportion
from .errors import TransactionValidationError


class M210IncomeClassification(BaseModel):
    """One explicit M210 income classification persisted on a transaction.

    ``official_tipo_renta_code`` is the two-character code selected from the
    M210 code axis, not the many-to-one conceptual rate token. The aggregation
    resolver additionally verifies that the selected calculation revision
    declares the code before admitting the row.
    """

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
        if code not in M210_TIPO_RENTA_CODE_PROJECTION:
            accepted = ", ".join(sorted(M210_TIPO_RENTA_CODE_PROJECTION))
            raise TransactionValidationError(
                f"official_tipo_renta_code must be a registry-projected Modelo 210 code; got {code!r}. "
                f"Accepted: {accepted}",
            )
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

    @model_validator(mode="after")
    def _validate_payer_mode(self) -> M210IncomeClassification:
        if self.official_tipo_renta_code == "35":
            if self.payer_mode is not M210PayerMode.MULTIPLE_PAYERS_CODE_35 or self.payer_id is not None:
                raise TransactionValidationError(
                    "official tipo-renta code '35' requires payer_mode='multiple_payers_code_35' and no payer_id",
                )
            return self
        if self.payer_mode is not M210PayerMode.SINGLE_PAYER or self.payer_id is None:
            raise TransactionValidationError(
                "non-35 Modelo 210 income requires payer_mode='single_payer' and a non-blank payer_id",
            )
        return self


__all__ = ["M210IncomeClassification"]
