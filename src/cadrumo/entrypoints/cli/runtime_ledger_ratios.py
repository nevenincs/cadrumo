"""CLI transport bridge for profile-bound ledger-ratios operations."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import typer

from ...adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ...application.ledger.ratios_contracts import (
    LEDGER_RATIOS_CENSO_MISMATCH_REFUSAL_CODE,
    LEDGER_RATIOS_ELIGIBLE_OPERATION_DEFINITION_ID,
    LEDGER_RATIOS_LIST_OPERATION_DEFINITION_ID,
    LEDGER_RATIOS_NO_OVERRIDE_REFUSAL_CODE,
    LEDGER_RATIOS_SET_OPERATION_DEFINITION_ID,
    LEDGER_RATIOS_UNSET_OPERATION_DEFINITION_ID,
    LEDGER_RATIOS_VALIDATE_OPERATION_DEFINITION_ID,
    LedgerRatiosEligibleProjection,
    LedgerRatiosEligibleRequest,
    LedgerRatiosListProjection,
    LedgerRatiosListRequest,
    LedgerRatiosSetProjection,
    LedgerRatiosSetRequest,
    LedgerRatiosUnsetProjection,
    LedgerRatiosUnsetRequest,
    LedgerRatiosValidateProjection,
    LedgerRatiosValidateRequest,
)
from ...application.runtime.contracts import RuntimeRefusalCode
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .common import active_bucket_id_or_refuse
from .errors import CliRefusedBoundaryError
from .registered_operation_contracts import RegisteredOperationCompletion
from .registered_operation_errors import submitted_operation_error
from .runtime_profile_binding import require_profile_client
from .runtime_registered_operation import run_registered_operation


def _client(ctx: typer.Context) -> RuntimeFrontendClient:
    """Bind every ratio request to the invocation's selected profile."""
    return require_profile_client(ctx, expected_profile_id=UUID(active_bucket_id_or_refuse()))


def _operation_error(completed: RegisteredOperationCompletion[Any], *, code: str) -> CliRefusedBoundaryError:
    return submitted_operation_error(
        completed.operation_id,
        code,
        terminal_condition=completed.terminal_condition,
        effect=completed.effect,
        refusal_code=completed.refusal_code,
    )


def list_ratios(ctx: typer.Context, *, year: int) -> RegisteredOperationCompletion[LedgerRatiosListProjection]:
    """Read bounded override rows, or their registered censo refusal detail."""
    client = _client(ctx)
    completed = run_registered_operation(
        client,
        LedgerRatiosListRequest(profile_id=client.profile_id, year=year),
        definition_id=LEDGER_RATIOS_LIST_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=LedgerRatiosListProjection,
        request_version=1,
        result_version=1,
        timeout=120,
        allow_refusal_detail=True,
    )
    projection = completed.projection
    expected_refusal = projection.outcome == "censo_mismatch"
    invalid = (
        projection.profile_id != client.profile_id
        or completed.effect is not OperationEffect.NONE
        or completed.terminal_condition
        is not (OperationTerminalCondition.REFUSED if expected_refusal else OperationTerminalCondition.SUCCEEDED)
        or completed.refusal_code != (LEDGER_RATIOS_CENSO_MISMATCH_REFUSAL_CODE if expected_refusal else None)
    )
    if invalid:
        raise _operation_error(completed, code=RuntimeRefusalCode.INVALID_FRAME.value)
    return completed


def set_ratio(
    ctx: typer.Context,
    *,
    category: str,
    ratio: str,
    year: int,
) -> RegisteredOperationCompletion[LedgerRatiosSetProjection]:
    """Persist one override through the invocation's immutable profile worker."""
    client = _client(ctx)
    completed = run_registered_operation(
        client,
        LedgerRatiosSetRequest(profile_id=client.profile_id, category=category, ratio=ratio, year=year),
        definition_id=LEDGER_RATIOS_SET_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=LedgerRatiosSetProjection,
        request_version=1,
        result_version=1,
        timeout=120,
    )
    projection = completed.projection
    if (
        projection.profile_id != client.profile_id
        or projection.requested_category != category
        or projection.ratio != ratio
        or completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.effect is not OperationEffect.UPDATED
        or completed.refusal_code is not None
    ):
        raise _operation_error(completed, code=RuntimeRefusalCode.INVALID_FRAME.value)
    return completed


def unset_ratio(
    ctx: typer.Context,
    *,
    category: str,
) -> RegisteredOperationCompletion[LedgerRatiosUnsetProjection]:
    """Clear one override or return its registered no-override refusal detail."""
    client = _client(ctx)
    completed = run_registered_operation(
        client,
        LedgerRatiosUnsetRequest(profile_id=client.profile_id, category=category),
        definition_id=LEDGER_RATIOS_UNSET_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=LedgerRatiosUnsetProjection,
        request_version=1,
        result_version=1,
        timeout=120,
        allow_refusal_detail=True,
    )
    projection = completed.projection
    refused = projection.outcome == "no_override"
    invalid = (
        projection.profile_id != client.profile_id
        or projection.requested_category != category
        or completed.terminal_condition
        is not (OperationTerminalCondition.REFUSED if refused else OperationTerminalCondition.SUCCEEDED)
        or completed.effect is not (OperationEffect.NONE if refused else OperationEffect.UPDATED)
        or completed.refusal_code != (LEDGER_RATIOS_NO_OVERRIDE_REFUSAL_CODE if refused else None)
    )
    if invalid:
        raise _operation_error(completed, code=RuntimeRefusalCode.INVALID_FRAME.value)
    return completed


def list_eligible_ratios(
    ctx: typer.Context,
    *,
    year: int,
) -> RegisteredOperationCompletion[LedgerRatiosEligibleProjection]:
    """Read eligible ratio rows and dated defaults from the pinned authority."""
    client = _client(ctx)
    completed = run_registered_operation(
        client,
        LedgerRatiosEligibleRequest(profile_id=client.profile_id, year=year),
        definition_id=LEDGER_RATIOS_ELIGIBLE_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=LedgerRatiosEligibleProjection,
        request_version=1,
        result_version=1,
        timeout=120,
    )
    if (
        completed.projection.profile_id != client.profile_id
        or completed.projection.year != year
        or completed.projection.count != len(completed.projection.rows)
        or completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.effect is not OperationEffect.NONE
        or completed.refusal_code is not None
    ):
        raise _operation_error(completed, code=RuntimeRefusalCode.INVALID_FRAME.value)
    return completed


def validate_ratios(ctx: typer.Context) -> RegisteredOperationCompletion[LedgerRatiosValidateProjection]:
    """Read the existing validation report for the exact active profile."""
    client = _client(ctx)
    completed = run_registered_operation(
        client,
        LedgerRatiosValidateRequest(profile_id=client.profile_id),
        definition_id=LEDGER_RATIOS_VALIDATE_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=LedgerRatiosValidateProjection,
        request_version=1,
        result_version=1,
        timeout=120,
    )
    projection = completed.projection
    if (
        projection.profile_id != client.profile_id
        or completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.effect is not OperationEffect.NONE
        or completed.refusal_code is not None
    ):
        raise _operation_error(completed, code=RuntimeRefusalCode.INVALID_FRAME.value)
    return completed


__all__ = ["list_eligible_ratios", "list_ratios", "set_ratio", "unset_ratio", "validate_ratios"]
