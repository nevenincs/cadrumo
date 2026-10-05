"""Concrete shared models for typed financial operand contract and custody tests."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import cast

from pydantic import BaseModel

from ....core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ..financial_operand_contract import (
    OperationTransientFinancialOperandDeclarationV1,
    financial_operand_model_identity,
)


class FinancialOperandBaseline(BaseModel):
    """Strict immutable synthetic baseline for the exact operand handoff."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    baseline_id: str


class FinancialOperandBatch(BaseModel):
    """Strict immutable Decimal batch retaining its concrete baseline."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    baseline: FinancialOperandBaseline
    values: tuple[Decimal, ...]


def _baseline(operand: BaseModel) -> BaseModel:
    return cast(FinancialOperandBatch, operand).baseline


def _baseline_reference(baseline: BaseModel) -> str:
    return cast(FinancialOperandBaseline, baseline).baseline_id


async def _no_receipt(requirement: object) -> None:
    return None


def financial_operand_declaration() -> OperationTransientFinancialOperandDeclarationV1:
    return OperationTransientFinancialOperandDeclarationV1(
        operand_type=FinancialOperandBatch,
        operand_schema=financial_operand_model_identity(
            schema_id="test.batch", schema_version=1, model_type=FinancialOperandBatch
        ),
        baseline_type=FinancialOperandBaseline,
        baseline_schema=financial_operand_model_identity(
            schema_id="test.baseline", schema_version=1, model_type=FinancialOperandBaseline
        ),
        baseline_accessor=_baseline,
        baseline_reference=_baseline_reference,
        lifetime=timedelta(minutes=5),
        effect_receipt_resolver=_no_receipt,
    )
