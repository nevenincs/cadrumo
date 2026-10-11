"""Ledger update refuses the same bad input whichever frontend submits it."""

from __future__ import annotations

from typing import cast

import pytest
from pydantic import ValidationError

from ....core.operations import OperationEffect
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.transactions.enums import TransactionLifecycleState
from ....domain.transactions.errors import TransactionValidationError
from ...operations.models import OperationRequest
from ...operations.owner import OperationExecutorContext
from ...operations.refusal_evidence import OperationRefusalEvidence
from .. import update_contracts as contracts
from .. import update_operation
from ..action_ports import LedgerActionPortsFactory
from ..models import ManualLedgerTransactionPatch
from ..own_account_ports import OwnAccountRepositoryProtocol
from .ledger_input_rule_support import (
    PROFILE,
    RecordingEvents,
    RecordingOperands,
    current_transaction,
    executor_context,
    executor_ports,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _request(**patch: str | None) -> contracts.LedgerUpdateRequest:
    return contracts.LedgerUpdateRequest(
        profile_id=PROFILE,
        transaction_id="b" * 12,
        patch=contracts.LedgerUpdatePatch.model_validate(patch),
        patch_fields=cast(tuple[contracts.LedgerUpdatePatchField, ...], tuple(sorted(patch))),
    )


@pytest.mark.parametrize("field", ["amount", "taxable_base", "iva_amount"])
def test_amounts_carry_at_most_euro_cent_precision(field: str) -> None:
    """A fourth fractional digit is refused where two are accepted."""
    with pytest.raises(ValidationError, match="canonical decimal text"):
        contracts.LedgerUpdatePatch.model_validate({field: "10.1234"})

    assert getattr(contracts.LedgerUpdatePatch.model_validate({field: "10.12"}), field) == "10.12"
    assert getattr(contracts.LedgerUpdatePatch.model_validate({field: "10.5"}), field) == "10.5"


@pytest.mark.parametrize("rate", ["0.052", "0.075", "0.014", "0.005", "0.0175"])
def test_a_rate_keeps_the_fraction_digits_it_has(rate: str) -> None:
    assert contracts.LedgerUpdatePatch.model_validate({"iva_rate": rate}).iva_rate == rate


def test_a_negative_amount_names_the_magnitude_rule_and_a_signed_base_is_still_admitted() -> None:
    """The flow lives in the direction field, so the sign of the amount is refused with that remedy."""
    with pytest.raises(ValidationError, match="non-negative magnitude"):
        contracts.LedgerUpdatePatch(amount="-49.99")

    assert contracts.LedgerUpdatePatch(amount="0.01").amount == "0.01"
    assert contracts.LedgerUpdatePatch(taxable_base="-5").taxable_base == "-5"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("booked_date", None),
        ("amount", None),
        ("currency", None),
        ("direction", None),
        ("description", None),
        ("description", "   "),
        ("notes", ""),
    ],
)
def test_an_update_cannot_blank_or_remove_a_required_fact(field: str, value: str | None) -> None:
    with pytest.raises(ValidationError, match=f"cannot clear {field}"):
        _request(**{field: value})


def test_optional_facts_can_still_be_cleared_and_a_required_fact_can_be_replaced() -> None:
    cleared = _request(counterparty=None, group_label=None, value_date=None)
    replaced = _request(description="Corrected description", notes="checked")

    assert cleared.patch_fields == ("counterparty", "group_label", "value_date")
    assert replaced.patch.description == "Corrected description"


def test_irpf_category_must_be_declared_by_the_published_taxonomy(operation: PinnedAuthorityOperation) -> None:
    accepted = update_operation._manual_patch_values(
        _request(irpf_category=" Actividad_Economica "), operation=operation
    )
    assert accepted["irpf_category"] == "actividad_economica"

    with pytest.raises(TransactionValidationError, match="rental_withholding") as refusal:
        update_operation._manual_patch_values(_request(irpf_category="rental_withholding"), operation=operation)
    assert "arrendamiento_local" in str(refusal.value)


def test_a_blank_category_still_clears_the_stored_one(operation: PinnedAuthorityOperation) -> None:
    values = update_operation._manual_patch_values(_request(irpf_category="  "), operation=operation)
    patch = ManualLedgerTransactionPatch.model_validate(values)

    assert "irpf_category" in patch.model_fields_set
    assert patch.irpf_category is None


def _unused_own_accounts(*, bucket_id: str) -> OwnAccountRepositoryProtocol:
    raise AssertionError(f"unexpected own-account lookup for {bucket_id}")


async def _execute(
    payload: contracts.LedgerUpdateRequest,
    authority: PinnedAuthorityOperation,
    monkeypatch: pytest.MonkeyPatch,
    *,
    lifecycle_state: TransactionLifecycleState = TransactionLifecycleState.ACTIVE,
) -> tuple[str | OperationRefusalEvidence, RecordingEvents, RecordingOperands]:
    monkeypatch.setattr("cadrumo.application.operations.profile_guard.require_active_bucket_id", lambda: str(PROFILE))
    current = current_transaction().model_copy(update={"lifecycle_state": lifecycle_state})
    ports = executor_ports(authority, current)
    events = RecordingEvents()
    operands = RecordingOperands()
    context = executor_context(contracts.LEDGER_UPDATE_OPERATION_DEFINITION_ID, authority, events, operands)
    executor = update_operation.LedgerUpdateExecutor(
        cast(LedgerActionPortsFactory, lambda **_kwargs: ports),
        own_account_repository_factory=_unused_own_accounts,
    )
    request = OperationRequest[contracts.LedgerUpdateRequest](
        definition_id=contracts.LEDGER_UPDATE_OPERATION_DEFINITION_ID,
        subject_ref=context.identity.subject_ref,
        payload=payload.model_copy(update={"transaction_id": current.transaction_id[:12]}),
    )
    result = await executor.execute(request, cast(OperationExecutorContext, context))
    return result, events, operands


@pytest.mark.asyncio
async def test_executor_refuses_an_undeclared_category_before_declaring_any_effect(
    operation: PinnedAuthorityOperation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result, events, operands = await _execute(
        _request(irpf_category="rental_withholding"),
        operation,
        monkeypatch,
    )

    assert isinstance(result, OperationRefusalEvidence)
    assert result.refusal_code == contracts.LEDGER_UPDATE_VALIDATION_REFUSAL_CODE
    assert events.effects == []
    detail = operands.value
    assert isinstance(detail, contracts.LedgerUpdateExecutionResult)
    assert detail.outcome == "validation_error"
    assert "rental_withholding" in detail.validation_messages[0]
    assert "arrendamiento_local" in detail.validation_messages[0]


@pytest.mark.asyncio
async def test_executor_refuses_an_edit_of_a_row_that_is_no_longer_active_with_no_effect(
    operation: PinnedAuthorityOperation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The canonical action's own refusal settles as a validation refusal, not an unknown effect."""
    result, events, operands = await _execute(
        _request(description="Corrected description"),
        operation,
        monkeypatch,
        lifecycle_state=TransactionLifecycleState.ARCHIVED,
    )

    assert isinstance(result, OperationRefusalEvidence)
    assert events.effects == [OperationEffect.UNKNOWN, OperationEffect.NONE]
    detail = operands.value
    assert isinstance(detail, contracts.LedgerUpdateExecutionResult)
    assert "only active ledger transactions can be edited" in detail.validation_messages[0]
