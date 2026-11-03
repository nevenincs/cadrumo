"""``aeat app ledger staged-check``: the backend's answer for staged ledger work, without writing it."""

from __future__ import annotations

from uuid import UUID

import typer
from pydantic import ValidationError

from cadrumo_client.commands.profile_binding import require_profile_client
from cadrumo_client.commands.registered_operation import run_registered_operation
from cadrumo_client.commands.registered_operation_contracts import RegisteredOperationCompletion
from cadrumo_client.commands.registered_operation_errors import invalid_completion_error
from cadrumo_client.commands.secure_input import (
    MachineSecretPayload,
    read_machine_secret_payload,
    select_machine_secret_channel,
)

from ...application.ledger.staged_check_contracts import (
    LEDGER_STAGED_CHECK_OPERATION_DEFINITION_ID,
    LedgerStagedCheckRequest,
    LedgerStagedCheckResult,
    LedgerStagedDraft,
    LedgerStagedRow,
)
from ...core.bucket_pointer import require_active_bucket_id
from ...core.external_constants import OutputLanguage
from ...core.i18n.render import output_language, tr
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...domain.transactions.errors import TransactionValidationError
from .common import emit_envelope
from .ledger_results import LedgerStagedCheckEnvelope
from .machine_secret_json_items import json_array_items


class StagedCheckSecrets(MachineSecretPayload):
    """Machine-channel staged work for ``app ledger staged-check``.

    Each field holds a JSON array: ``rows`` of movement objects with ``transaction_id``,
    ``cells`` and optional ``evidence_staged`` and ``m210_staged``; ``drafts`` of new
    movements with ``key`` and ``fields``. Blank is none.
    """

    rows: str = ""
    drafts: str = ""


def _request(
    profile_id: UUID, row: tuple[str, ...], draft: tuple[str, ...], category: tuple[str, ...]
) -> LedgerStagedCheckRequest:
    try:
        return LedgerStagedCheckRequest(
            profile_id=profile_id,
            rows=tuple(LedgerStagedRow.model_validate_json(text) for text in row),
            drafts=tuple(LedgerStagedDraft.model_validate_json(text) for text in draft),
            categories=tuple(category),
            output_language=OutputLanguage(output_language()),
        )
    except (ValueError, ValidationError) as exc:
        # The values are private figures, so the refusal names the shape and not the input.
        raise TransactionValidationError(tr("cli.ledger.staged_check_invalid")) from exc


def _is_clean_read(completed: RegisteredOperationCompletion[LedgerStagedCheckResult], profile_id: UUID) -> bool:
    """Return whether the operation settled as a successful read of this profile with no effect."""
    return (
        completed.terminal_condition is OperationTerminalCondition.SUCCEEDED
        and completed.effect is OperationEffect.NONE
        and completed.refusal_code is None
        and completed.projection.profile_id == profile_id
    )


def _report_lines(answer: LedgerStagedCheckResult) -> tuple[str, ...]:
    return (
        *(
            f"{item.transaction_id[:12]}\t{route.field}\t{route.route or route.refused}"
            for item in answer.rows
            for route in item.routes
        ),
        *(
            f"{item.transaction_id[:12]}\t{blocker.kind}\t{','.join(blocker.fields)}"
            for item in answer.rows
            for blocker in item.blockers
        ),
        *(
            f"{item.key}\t{blocker.kind}\t{','.join(blocker.fields)}"
            for item in answer.drafts
            for blocker in item.blockers
        ),
    )


def staged_check(
    ctx: typer.Context,
    category: tuple[str, ...] = (),
    secrets_stdin: bool = False,
    secrets_fd: int | None = None,
) -> None:
    """Answer staged cells, new movements and categories the way the writers would take them."""
    client = require_profile_client(ctx, expected_profile_id=UUID(require_active_bucket_id()))
    selection = select_machine_secret_channel(secrets_stdin=secrets_stdin, secrets_fd=secrets_fd)
    staged = (
        read_machine_secret_payload(StagedCheckSecrets, selection=selection)
        if selection is not None
        else StagedCheckSecrets()
    )
    try:
        row, draft = json_array_items(staged.rows), json_array_items(staged.drafts)
    except ValueError as exc:
        raise TransactionValidationError(tr("cli.ledger.staged_check_invalid")) from exc
    completed = run_registered_operation(
        client,
        _request(client.profile_id, row, draft, category),
        definition_id=LEDGER_STAGED_CHECK_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=LedgerStagedCheckResult,
        request_version=1,
        result_version=1,
        timeout=120,
        allow_refusal_detail=False,
    )
    if not _is_clean_read(completed, client.profile_id):
        raise invalid_completion_error(completed)
    answer = completed.projection
    emit_envelope(
        ctx,
        command="ledger.staged-check",
        result=LedgerStagedCheckEnvelope.model_validate(answer.model_dump(mode="json", exclude={"profile_id"})),
        lines=_report_lines(answer),
    )


__all__ = ["StagedCheckSecrets", "staged_check"]
