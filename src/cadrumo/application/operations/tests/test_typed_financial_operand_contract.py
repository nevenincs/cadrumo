"""Concrete in-memory financial model admission remains distinct from wire DTOs."""

from __future__ import annotations

from datetime import timedelta
from typing import cast

import pytest
from pydantic import BaseModel, ValidationError

from ..financial_operand_contract import (
    OperationTransientFinancialOperandDeclarationV1,
    OperationTransientFinancialOperandPublicDeclarationV1,
    financial_operand_model_identity,
)
from .financial_operand_models import FinancialOperandBaseline, FinancialOperandBatch

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _baseline(operand: BaseModel) -> BaseModel:
    return cast(FinancialOperandBatch, operand).baseline


def _baseline_reference(baseline: BaseModel) -> str:
    return cast(FinancialOperandBaseline, baseline).baseline_id


async def _no_receipt(requirement: object) -> None:
    return None


def _declaration() -> OperationTransientFinancialOperandDeclarationV1:
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


def test_typed_decimal_batch_has_an_identity_without_a_wire_schema_exemption() -> None:
    """Different JSON modes are legitimate for a model that never crosses as a persisted request."""
    assert FinancialOperandBatch.model_json_schema(mode="validation") != FinancialOperandBatch.model_json_schema(
        mode="serialization"
    )
    declaration = _declaration()
    assert declaration.operand_type is FinancialOperandBatch
    assert declaration.baseline_type is FinancialOperandBaseline


def test_mismatched_concrete_model_cannot_borrow_a_registered_schema_identity() -> None:
    """A matching-looking schema cannot replace the declared concrete type."""
    declaration = _declaration()
    wrong = declaration.operand_schema.model_copy(update={"schema_fingerprint": "f" * 64})
    with pytest.raises(ValidationError, match="does not reproduce"):
        OperationTransientFinancialOperandDeclarationV1(
            operand_type=FinancialOperandBatch,
            operand_schema=wrong,
            baseline_type=FinancialOperandBaseline,
            baseline_schema=declaration.baseline_schema,
            baseline_accessor=_baseline,
            baseline_reference=_baseline_reference,
            lifetime=timedelta(minutes=5),
            effect_receipt_resolver=_no_receipt,
        )


def test_exact_production_batch_including_all_intent_families_has_a_model_identity() -> None:
    """The accepted operand is the existing complete domain submission, without a wire mirror."""
    from ...modelo.edit_models import ModeloEditSubmissionV1

    identity = financial_operand_model_identity(
        schema_id="modelo.edit.submission", schema_version=1, model_type=ModeloEditSubmissionV1
    )
    assert identity.schema_id == "modelo.edit.submission"
    assert set(ModeloEditSubmissionV1.model_fields) >= {
        "scalar_intents",
        "binding_intents",
        "row_intents",
        "detail_row_intents",
    }


@pytest.mark.parametrize("lifetime", [0.0, -1.0, 1801.0, float("inf"), float("nan")])
def test_published_financial_lifetime_is_positive_finite_and_bounded(lifetime: float) -> None:
    declaration = _declaration()
    with pytest.raises(ValidationError):
        OperationTransientFinancialOperandPublicDeclarationV1(
            operand_schema=declaration.operand_schema,
            baseline_schema=declaration.baseline_schema,
            lifetime_seconds=lifetime,
        )
