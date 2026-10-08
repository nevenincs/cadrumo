"""Action-specific shape and receipt correlation for counterparty operations."""

from __future__ import annotations

from uuid import UUID

from ...application.ledger.counterparty_establishment import confirmed_counterparty_facts_key
from ...application.ledger.counterparty_operation import (
    CounterpartyFactProjection,
    LedgerCounterpartyRequest,
    LedgerCounterpartyResult,
)
from ...core.operations import OperationEffect, OperationTerminalCondition
from .registered_operation_contracts import RegisteredOperationCompletion


def counterparty_confirmation_shape_invalid(invalid: bool, result: LedgerCounterpartyResult) -> bool:
    """Counterparty confirmation shape invalid."""
    invalid = invalid or result.resolution is not None or result.withdrawn is not None
    return invalid


def counterparty_resolution_shape_invalid(invalid: bool, result: LedgerCounterpartyResult) -> bool:
    """Counterparty resolution shape invalid."""
    invalid = invalid or any(
        (
            result.resolution is None,
            result.facts is not None,
            result.recorded is not None,
            result.withdrawn is not None,
            result.conflict_context is not None,
            result.changed,
        )
    )
    return invalid


def counterparty_recorded_fact_invalid(
    invalid: bool,
    result: LedgerCounterpartyResult,
    request: LedgerCounterpartyRequest,
    facts: CounterpartyFactProjection,
) -> bool:
    """Counterparty recorded fact invalid."""
    if result.recorded is True:
        invalid = invalid or facts.asserted_by != request.asserted_by or facts.note != request.note
    return invalid


def counterparty_receipt_invalid(
    completed: RegisteredOperationCompletion[LedgerCounterpartyResult],
    result: LedgerCounterpartyResult,
    request: LedgerCounterpartyRequest,
    profile_id: UUID,
) -> bool:
    """Counterparty receipt invalid."""
    expected_effect = OperationEffect.UPDATED if result.changed else OperationEffect.NONE
    invalid = (
        request.profile_id != profile_id
        or result.profile_id != profile_id
        or result.action != request.action
        or result.tax_identifier != request.tax_identifier
        or result.country_code != request.country_code
        or result.evidenced_scope != request.evidenced_scope
        or completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.refusal_code is not None
        or completed.effect is not expected_effect
    )
    return invalid


def counterparty_confirmation_invalid(
    invalid: bool, request: LedgerCounterpartyRequest, result: LedgerCounterpartyResult
) -> bool:
    """Correlate the confirmation shape without losing an earlier receipt mismatch."""
    invalid = counterparty_confirmation_shape_invalid(invalid, result)
    if result.conflict_context is not None:
        invalid = invalid or result.facts is not None or result.recorded is not None or result.changed
    else:
        invalid = invalid or result.facts is None or result.recorded is None
    if result.facts is not None and result.conflict_context is None:
        invalid = counterparty_confirmed_facts_invalid(invalid, request, result, result.facts)
    return invalid


def counterparty_withdrawal_invalid(
    invalid: bool, request: LedgerCounterpartyRequest, result: LedgerCounterpartyResult
) -> bool:
    """Correlate the withdrawal shape without losing an earlier receipt mismatch."""
    invalid = invalid or any(
        (
            result.withdrawn is None,
            result.facts is not None,
            result.resolution is not None,
            result.recorded is not None,
            result.conflict_context is not None,
            result.changed != result.withdrawn,
        )
    )
    return invalid


def counterparty_resolution_invalid(
    invalid: bool, request: LedgerCounterpartyRequest, result: LedgerCounterpartyResult
) -> bool:
    """Correlate the resolution shape without losing an earlier receipt mismatch."""
    invalid = counterparty_resolution_shape_invalid(invalid, result)
    resolution = result.resolution
    if resolution is not None:
        invalid = invalid or (
            (resolution.territorial_scope is None) != (resolution.territorial_source is None)
            or (resolution.identification_state is None) != (resolution.identification_source is None)
            or (resolution.contradiction_detail is None) != (resolution.confirmed_scope is None)
            or (resolution.contradiction_detail is None) != (resolution.evidenced_scope is None)
            or (resolution.contradiction_detail is not None and resolution.territorial_scope is not None)
            or (resolution.evidenced_scope is not None and resolution.evidenced_scope != request.evidenced_scope)
        )
    return invalid


def counterparty_confirmed_facts_invalid(
    invalid: bool,
    request: LedgerCounterpartyRequest,
    result: LedgerCounterpartyResult,
    facts: CounterpartyFactProjection,
) -> bool:
    """Check the confirmed fact key, answered axes and actor details in original order."""
    expected_key = confirmed_counterparty_facts_key(request.tax_identifier, country_code=request.country_code)
    invalid = (
        invalid
        or facts.counterparty_key != expected_key
        or (facts.territorial_scope != request.territorial_scope and request.territorial_scope is not None)
        or (facts.identification_state != request.identification_state and request.identification_state is not None)
    )
    invalid = invalid or (result.recorded is True and not result.changed)
    invalid = counterparty_recorded_fact_invalid(invalid, result, request, facts)
    return invalid
