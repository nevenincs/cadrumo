"""``aeat app ledger rule trial``: try an unsaved pattern with the rule engine, without saving it."""

from __future__ import annotations

from uuid import UUID

import typer

from cadrumo_client.commands.profile_binding import require_profile_client
from cadrumo_client.commands.registered_operation import run_registered_operation
from cadrumo_client.commands.registered_operation_errors import invalid_completion_error

from ...application.ledger.rule_trial_operation import (
    LEDGER_RULE_TRIAL_OPERATION_DEFINITION_ID,
    LedgerRuleTrialRequest,
    LedgerRuleTrialResult,
)
from ...core.bucket_pointer import require_active_bucket_id
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .common import emit_envelope
from .ledger_results import LedgerRuleTrialEnvelope


def rule_trial(ctx: typer.Context, description_pattern: str, transaction_id: tuple[str, ...] = ()) -> None:
    """Say whether the engine reads a pattern and which of the named movements it finds."""
    client = require_profile_client(ctx, expected_profile_id=UUID(require_active_bucket_id()))
    completed = run_registered_operation(
        client,
        LedgerRuleTrialRequest(
            profile_id=client.profile_id,
            description_pattern=description_pattern,
            transaction_ids=tuple(transaction_id),
        ),
        definition_id=LEDGER_RULE_TRIAL_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=LedgerRuleTrialResult,
        request_version=1,
        result_version=1,
        timeout=120,
        allow_refusal_detail=False,
    )
    if (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.effect is not OperationEffect.NONE
        or completed.refusal_code is not None
        or completed.projection.profile_id != client.profile_id
    ):
        raise invalid_completion_error(completed)
    answer = completed.projection
    emit_envelope(
        ctx,
        command="ledger.rule.trial",
        result=LedgerRuleTrialEnvelope.model_validate(answer.model_dump(mode="json", exclude={"profile_id"})),
        lines=(
            answer.outcome,
            *(f"{found[:12]}\thit" for found in answer.hits),
            *(f"{found[:12]}\tpending" for found in answer.pending),
        ),
    )


__all__ = ["rule_trial"]
