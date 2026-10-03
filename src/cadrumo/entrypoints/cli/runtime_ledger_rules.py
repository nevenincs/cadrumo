"""Authenticated CLI bridge for canonical ledger-rule operations."""

from __future__ import annotations

from typing import Never
from uuid import UUID

import typer
from pydantic import BaseModel

from ...adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ...application.ledger.rule_operation import (
    LEDGER_RULE_ADD_OPERATION_DEFINITION_ID,
    LEDGER_RULE_APPLY_OPERATION_DEFINITION_ID,
    LEDGER_RULE_LIST_OPERATION_DEFINITION_ID,
    LEDGER_RULE_VALIDATION_REFUSAL_CODE,
    LedgerRuleAddProjection,
    LedgerRuleAddRequest,
    LedgerRuleApplyProjection,
    LedgerRuleApplyRequest,
    LedgerRuleListProjection,
    LedgerRuleListRequest,
)
from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .common import active_bucket_id_or_refuse
from .runtime_profile_binding import require_profile_client
from .runtime_registered_operation import (
    RegisteredOperationCompletion,
    run_registered_operation,
    submitted_operation_error,
)


def _client(ctx: typer.Context, profile_id: UUID) -> RuntimeFrontendClient:
    """Return only the runtime client bound to the active immutable profile."""
    expected_profile_id = UUID(active_bucket_id_or_refuse())
    if profile_id != expected_profile_id:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    return require_profile_client(ctx, expected_profile_id=expected_profile_id)


def _invalid[ProjectionT: BaseModel](completed: RegisteredOperationCompletion[ProjectionT]) -> Never:
    raise submitted_operation_error(
        completed.operation_id,
        RuntimeRefusalCode.INVALID_FRAME.value,
        terminal_condition=completed.terminal_condition,
        effect=completed.effect,
        refusal_code=completed.refusal_code,
    )


def _submit[ProjectionT: BaseModel](
    ctx: typer.Context,
    request: BaseModel,
    *,
    definition_id: str,
    result_type: type[ProjectionT],
    allow_refusal_detail: bool,
) -> RegisteredOperationCompletion[ProjectionT]:
    """Submit one secure operation against the exact active profile subject."""
    profile_id = getattr(request, "profile_id", None)
    if not isinstance(profile_id, UUID):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    client = _client(ctx, profile_id)
    return run_registered_operation(
        client,
        request,
        definition_id=definition_id,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=result_type,
        request_version=1,
        result_version=1,
        timeout=120,
        allow_refusal_detail=allow_refusal_detail,
    )


def submit_ledger_rule_add(
    ctx: typer.Context,
    request: LedgerRuleAddRequest,
) -> RegisteredOperationCompletion[LedgerRuleAddProjection]:
    """Submit rule creation and correlate its complete row or refusal receipt."""
    completed = _submit(
        ctx,
        request,
        definition_id=LEDGER_RULE_ADD_OPERATION_DEFINITION_ID,
        result_type=LedgerRuleAddProjection,
        allow_refusal_detail=True,
    )
    projection = completed.projection
    if projection.profile_id != request.profile_id:
        _invalid(completed)
    if projection.outcome == "validation_error":
        if (
            completed.terminal_condition is not OperationTerminalCondition.REFUSED
            or completed.effect is not OperationEffect.NONE
            or completed.refusal_code != LEDGER_RULE_VALIDATION_REFUSAL_CODE
            or projection.rule is not None
            or projection.validation_code is None
            or not projection.validation_messages
        ):
            _invalid(completed)
        return completed

    rule = projection.rule
    expected_category = request.category_id.strip() or None if request.category_id is not None else None
    expected_actor = request.actor or str(request.profile_id) or "operator"
    if (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.effect is not OperationEffect.UPDATED
        or completed.refusal_code is not None
        or rule is None
        or rule.description_pattern != request.description_pattern
        or rule.classification is not request.classification
        or rule.category_id != expected_category
        or rule.priority != request.priority
        or rule.actor != expected_actor
    ):
        _invalid(completed)
    return completed


def submit_ledger_rule_list(
    ctx: typer.Context,
    request: LedgerRuleListRequest,
) -> RegisteredOperationCompletion[LedgerRuleListProjection]:
    """Submit one read-only complete profile rule-list request."""
    completed = _submit(
        ctx,
        request,
        definition_id=LEDGER_RULE_LIST_OPERATION_DEFINITION_ID,
        result_type=LedgerRuleListProjection,
        allow_refusal_detail=False,
    )
    if (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.effect is not OperationEffect.NONE
        or completed.refusal_code is not None
        or completed.projection.profile_id != request.profile_id
    ):
        _invalid(completed)
    return completed


def submit_ledger_rule_apply(
    ctx: typer.Context,
    request: LedgerRuleApplyRequest,
) -> RegisteredOperationCompletion[LedgerRuleApplyProjection]:
    """Submit one canonical preview or live apply and correlate its receipt."""
    completed = _submit(
        ctx,
        request,
        definition_id=LEDGER_RULE_APPLY_OPERATION_DEFINITION_ID,
        result_type=LedgerRuleApplyProjection,
        allow_refusal_detail=True,
    )
    projection = completed.projection
    if projection.profile_id != request.profile_id:
        _invalid(completed)
    if projection.outcome == "validation_error":
        if (
            completed.terminal_condition is not OperationTerminalCondition.REFUSED
            or completed.effect not in {OperationEffect.NONE, OperationEffect.PARTIAL}
            or completed.refusal_code != LEDGER_RULE_VALIDATION_REFUSAL_CODE
            or projection.validation_code is None
            or not projection.validation_messages
        ):
            _invalid(completed)
        return completed

    if projection.outcome == "dry_run":
        valid_receipt = (
            completed.terminal_condition is OperationTerminalCondition.SUCCEEDED
            and completed.effect is OperationEffect.NONE
            and completed.refusal_code is None
        )
    else:
        expected_effect = OperationEffect.UPDATED if projection.bucket_event_count else OperationEffect.NONE
        valid_receipt = (
            completed.terminal_condition is OperationTerminalCondition.SUCCEEDED
            and completed.effect is expected_effect
            and completed.refusal_code is None
        )
    if not valid_receipt:
        _invalid(completed)

    if projection.outcome == "dry_run":
        if not request.dry_run or projection.dry_run is not True:
            _invalid(completed)
    elif request.dry_run:
        _invalid(completed)
    return completed


__all__ = ["submit_ledger_rule_add", "submit_ledger_rule_apply", "submit_ledger_rule_list"]
