"""Proofs for operand declarations on definitions and effect-receipt narrowing."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....core.operations import OperationInteractionKind
from ..financial_operand import OperationTransientFinancialOperandDeclaration
from ..financial_operand_custody import (
    OperationFinancialOperandCrashClassification,
    OperationFinancialOperandCustodyCheckpoint,
    OperationFinancialOperandCustodyState,
)
from ..registry import (
    OperationDefinition,
    OperationEffectReceipt,
    OperationReconciliationPolicy,
)
from .test_registry import definition

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_T0 = datetime(2026, 3, 4, 9, 0, 0, tzinfo=UTC)


def _declaration(operand_kind: str = "pago.fraccionado") -> OperationTransientFinancialOperandDeclaration:
    return OperationTransientFinancialOperandDeclaration(
        operand_kind=operand_kind,
        currency="EUR",
        scale=2,
        minimum=Decimal("0.00"),
        maximum=Decimal("1000.00"),
        lifetime=timedelta(minutes=5),
    )


def _operand_definition(**overrides: object) -> OperationDefinition:
    base = definition(definition_id="operations.financial-operand")
    values = base.model_dump()
    values.update(
        {
            "request_type": base.request_type,
            "result_type": base.result_type,
            "executor_factory": base.executor_factory,
            "capabilities": base.capabilities,
            "interaction_kinds": frozenset({OperationInteractionKind.INPUT}),
            "transient_financial_operands": (_declaration(),),
        }
    )
    values.update(overrides)
    return OperationDefinition(**values)  # type: ignore[arg-type]


def _custody(
    classification: OperationFinancialOperandCrashClassification | None,
) -> OperationFinancialOperandCustodyCheckpoint:
    return OperationFinancialOperandCustodyCheckpoint(
        operand_kind="pago.fraccionado",
        interaction_id="interaction-1",
        sequence=5,
        state=OperationFinancialOperandCustodyState.RELEASED,
        recorded_at=_T0,
        crash_classification=classification,
    )


def test_a_definition_carries_its_declared_operands() -> None:
    """An operation states which amounts it may ask for while it runs."""
    definition_under_test = _operand_definition()

    assert len(definition_under_test.transient_financial_operands) == 1
    assert definition_under_test.transient_financial_operands[0].operand_kind == "pago.fraccionado"


def test_a_definition_cannot_declare_one_operand_kind_twice() -> None:
    """Two declarations of one kind leave the wait ambiguous."""
    with pytest.raises(ValidationError):
        _operand_definition(transient_financial_operands=(_declaration(), _declaration()))


def test_an_operand_operation_cannot_resume_after_owner_loss() -> None:
    """The amount died with the process, so resuming would have to invent it."""
    with pytest.raises(ValidationError):
        _operand_definition(reconciliation_policy=OperationReconciliationPolicy.RESUME_FROM_CHECKPOINT)


def test_an_operand_operation_must_declare_the_input_it_waits_on() -> None:
    """An operand arrives through an input interaction or it never arrives."""
    with pytest.raises(ValidationError):
        _operand_definition(interaction_kinds=frozenset({OperationInteractionKind.REVIEW}))


def test_a_definition_without_operands_is_unaffected() -> None:
    """The declaration is additive; existing definitions keep validating."""
    plain = definition(definition_id="operations.plain")

    assert plain.transient_financial_operands == ()


def test_a_receipt_exposes_no_operand_material() -> None:
    """The resolver reads a custody classification and never an amount."""
    forbidden = ("amount", "value", "digest", "hash", "operand")
    for name in OperationEffectReceipt.model_fields:
        assert not any(token in name.lower() for token in forbidden), name
