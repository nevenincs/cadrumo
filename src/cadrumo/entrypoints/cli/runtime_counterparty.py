"""Correlated exact-profile counterparty operations for the CLI."""

from __future__ import annotations

from uuid import UUID

import typer

from ...application.ledger.counterparty_operation import (
    LEDGER_COUNTERPARTY_OPERATION_DEFINITION_ID,
    LedgerCounterpartyRequest,
    LedgerCounterpartyResult,
)
from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...core.bucket_pointer import require_active_bucket_id
from ...core.operations import profile_operation_subject
from .counterparty_correlation import (
    counterparty_confirmation_invalid,
    counterparty_receipt_invalid,
    counterparty_resolution_invalid,
    counterparty_withdrawal_invalid,
)
from .registered_operation_contracts import RegisteredOperationCompletion
from .registered_operation_errors import invalid_completion_error
from .runtime_profile_binding import require_profile_client
from .runtime_registered_operation import run_registered_operation


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
    invalid = counterparty_receipt_invalid(completed, result, request, client.profile_id)
    if request.action == "confirm":
        invalid = counterparty_confirmation_invalid(invalid, request, result)
    elif request.action == "withdraw":
        invalid = counterparty_withdrawal_invalid(invalid, request, result)
    else:
        invalid = counterparty_resolution_invalid(invalid, request, result)
    if invalid:
        raise invalid_completion_error(completed)
    return completed
