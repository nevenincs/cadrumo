"""Correlated exact-profile counterparty operations for the CLI."""

from __future__ import annotations

from uuid import UUID

import typer

from ...application.ledger.counterparty_establishment import confirmed_counterparty_facts_key
from ...application.ledger.counterparty_operation import (
    LEDGER_COUNTERPARTY_OPERATION_DEFINITION_ID,
    LedgerCounterpartyRequest,
    LedgerCounterpartyResult,
)
from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...core.bucket_pointer import require_active_bucket_id
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .runtime_profile_binding import require_profile_client
from .runtime_registered_operation import (
    RegisteredOperationCompletion,
    run_registered_operation,
    submitted_operation_error,
)


def run_counterparty(
    ctx: typer.Context, *, request: LedgerCounterpartyRequest
) -> RegisteredOperationCompletion[LedgerCounterpartyResult]:
    """Run and validate one encrypted result against the submitted question."""
    client = require_profile_client(ctx, expected_profile_id=UUID(require_active_bucket_id()))
    if request.profile_id != client.profile_id:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    completed = run_registered_operation(
        client,
        request,
        definition_id=LEDGER_COUNTERPARTY_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=LedgerCounterpartyResult,
        request_version=1,
        result_version=1,
        timeout=120,
    )
    result = completed.projection
    expected_effect = OperationEffect.UPDATED if result.changed else OperationEffect.NONE
    invalid = (
        request.profile_id != client.profile_id
        or result.profile_id != client.profile_id
        or result.action != request.action
        or result.tax_identifier != request.tax_identifier
        or result.country_code != request.country_code
        or result.evidenced_scope != request.evidenced_scope
        or completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.refusal_code is not None
        or completed.effect is not expected_effect
    )
    if request.action == "confirm":
        invalid = invalid or result.resolution is not None or result.withdrawn is not None
        if result.conflict_context is not None:
            invalid = invalid or result.facts is not None or result.recorded is not None or result.changed
        else:
            invalid = invalid or result.facts is None or result.recorded is None
        if result.facts is not None and result.conflict_context is None:
            expected_key = confirmed_counterparty_facts_key(request.tax_identifier, country_code=request.country_code)
            invalid = (
                invalid
                or result.facts.counterparty_key != expected_key
                or (
                    result.facts.territorial_scope != request.territorial_scope
                    and request.territorial_scope is not None
                )
                or (
                    result.facts.identification_state != request.identification_state
                    and request.identification_state is not None
                )
            )
            invalid = invalid or (result.recorded is True and not result.changed)
            if result.recorded is True:
                invalid = (
                    invalid or result.facts.asserted_by != request.asserted_by or result.facts.note != request.note
                )
    elif request.action == "withdraw":
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
    else:
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
    if invalid:
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=completed.terminal_condition,
            effect=completed.effect,
            refusal_code=completed.refusal_code,
        )
    return completed
