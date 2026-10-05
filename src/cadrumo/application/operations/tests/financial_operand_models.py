"""Concrete shared models for typed financial operand contract and custody tests."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel

from ....core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG


class FinancialOperandBaseline(BaseModel):
    """Strict immutable synthetic baseline for the exact operand handoff."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    baseline_id: str


class FinancialOperandBatch(BaseModel):
    """Strict immutable Decimal batch retaining its concrete baseline."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    baseline: FinancialOperandBaseline
    values: tuple[Decimal, ...]
