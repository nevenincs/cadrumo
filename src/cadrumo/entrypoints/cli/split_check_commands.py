"""``aeat app ledger split-check``: the backend's answer for an unsaved split, without writing it."""

from __future__ import annotations

from uuid import UUID

import typer
from pydantic import ValidationError

from cadrumo_client.commands.profile_binding import require_profile_client
from cadrumo_client.commands.registered_operation import run_registered_operation
from cadrumo_client.commands.registered_operation_errors import invalid_completion_error
from cadrumo_client.commands.secure_input import (
    MachineSecretPayload,
    read_machine_secret_payload,
    select_machine_secret_channel,
)

from ...application.ledger.split_check_operation import (
    LEDGER_SPLIT_CHECK_OPERATION_DEFINITION_ID,
    LedgerSplitCheckPart,
    LedgerSplitCheckRequest,
    LedgerSplitCheckResult,
)
from ...core.bucket_pointer import require_active_bucket_id
from ...core.i18n.render import tr
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...domain.transactions.errors import TransactionValidationError
from .common import emit_envelope
from .ledger_results import LedgerSplitCheckEnvelope
from .machine_secret_json_items import json_array_items


class SplitCheckSecrets(MachineSecretPayload):
    """Machine-channel unsaved parts for ``app ledger split-check``.

    ``parts`` holds a JSON array of objects with ``description`` and ``amount``; a null
    ``amount`` on the last part asks for what the others leave.
    """

    parts: str = ""


def _request(profile_id: UUID, transaction_id: str, parts: str) -> LedgerSplitCheckRequest:
    try:
        return LedgerSplitCheckRequest(
            profile_id=profile_id,
            transaction_id=transaction_id,
            parts=tuple(LedgerSplitCheckPart.model_validate_json(text) for text in json_array_items(parts)),
        )
    except (ValueError, ValidationError) as exc:
        # The values are private figures, so the refusal names the shape and not the input.
        raise TransactionValidationError(tr("cli.ledger.split_check_invalid")) from exc


def split_check(
    ctx: typer.Context,
    transaction_id: str,
    secrets_stdin: bool = False,
    secrets_fd: int | None = None,
) -> None:
    """Answer unsaved split parts the way the split writer would take them."""
    client = require_profile_client(ctx, expected_profile_id=UUID(require_active_bucket_id()))
    selection = select_machine_secret_channel(secrets_stdin=secrets_stdin, secrets_fd=secrets_fd)
    staged = (
        read_machine_secret_payload(SplitCheckSecrets, selection=selection)
        if selection is not None
        else SplitCheckSecrets()
    )
    completed = run_registered_operation(
        client,
        _request(client.profile_id, transaction_id, staged.parts),
        definition_id=LEDGER_SPLIT_CHECK_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=LedgerSplitCheckResult,
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
    problem = answer.problem
    emit_envelope(
        ctx,
        command="ledger.split-check",
        result=LedgerSplitCheckEnvelope.model_validate(answer.model_dump(mode="json", exclude={"profile_id"})),
        lines=(problem.kind if problem is not None else "ok", answer.remainder or ""),
    )


__all__ = ["SplitCheckSecrets", "split_check"]
