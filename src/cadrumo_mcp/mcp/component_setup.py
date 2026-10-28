"""Gate setup recovery actions on the journaled local status operation."""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence

from cadrumo.application.components_operations import (
    COMPONENTS_OPERATION_SUBJECT,
    COMPONENTS_STATUS_DEFINITION_ID,
    ProvisionOutcome,
    ProvisionReadRequest,
    ProvisionResult,
)
from cadrumo.application.dependency_contracts import DEPENDENCY_SETUP_RECOVERIES
from cadrumo.application.dependency_registry import dependency_item_declarations
from cadrumo.application.dependency_wording import dependency_held_sentence
from cadrumo.core.operations import OperationTerminalCondition
from cadrumo_client.commands.registered_operation import run_registered_operation
from cadrumo_client.transport.frontend_client import FrontendClient


def gate_setup_actions(
    client: FrontendClient,
    action_ids: Sequence[str],
    *,
    language: Callable[[], str],
    deadline: float,
    status_allowed: bool,
) -> tuple[list[str], list[dict[str, str]]]:
    """Offer actions only when their current local row allows setup."""
    declarations = {item.recovery_action_id: item for item in dependency_item_declarations()}
    named: list[str] = []
    held: list[dict[str, str]] = []
    rows = None
    if status_allowed and any(action in declarations for action in action_ids):
        try:
            timeout = min(30.0, deadline - time.monotonic())
            if timeout <= 0:
                return [action for action in dict.fromkeys(action_ids) if action not in declarations], held
            completed = run_registered_operation(
                client,
                ProvisionReadRequest(),
                definition_id=COMPONENTS_STATUS_DEFINITION_ID,
                subject_ref=COMPONENTS_OPERATION_SUBJECT,
                result_type=ProvisionResult,
                request_version=1,
                result_version=1,
                timeout=timeout,
            )
            if (
                completed.terminal_condition is OperationTerminalCondition.SUCCEEDED
                and completed.refusal_code is None
                and completed.projection.outcome is ProvisionOutcome.OK
            ):
                rows = {row.item_id: row for row in completed.projection.rows}
        except Exception:
            # A status that cannot be read never authorizes a setup offer.
            rows = None
    for action_id in dict.fromkeys(action_ids):
        declaration = declarations.get(action_id)
        if declaration is None:
            named.append(action_id)
            continue
        row = None if rows is None else rows.get(declaration.item_id)
        if row is None:
            continue
        if row.recovery in DEPENDENCY_SETUP_RECOVERIES:
            named.append(action_id)
        else:
            held.append(
                {
                    "recovery_action_id": action_id,
                    "item_id": row.item_id,
                    "state": row.state.value,
                    "sentence": dependency_held_sentence(row, declaration, locale=language()),
                }
            )
    return named, held
