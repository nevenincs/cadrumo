"""Terminal snapshot construction shared by supervised and terminated owners."""

from __future__ import annotations

from ...core.logging import get_logger
from ...core.operations import OperationLifecycle, OperationTerminalCondition
from .models import OperationTerminalReceipt
from .persistence.events import OperationEvent
from .persistence.journal import OperationPersistedSnapshot

_log = get_logger(__name__)


def settlement_successor(
    snapshot: OperationPersistedSnapshot,
    receipt: OperationTerminalReceipt,
    events: tuple[OperationEvent, ...],
) -> OperationPersistedSnapshot:
    """Materialize the terminal snapshot from the committed receipt events."""
    return snapshot.model_copy(
        update={
            "revision": receipt.revision,
            "lifecycle": OperationLifecycle.TERMINAL,
            "terminal_condition": receipt.condition,
            "effect": receipt.effect,
            "updated_at": receipt.settled_at,
            "event_cursor": events[-1].sequence,
            "events": events,
            "terminal_receipt": receipt,
            "pending_interaction": None,
        }
    )


def log_settlement(receipt: OperationTerminalReceipt, *, cause: str) -> None:
    """Name every settled operation once, so a log reader can match it to what a frontend showed.

    Only registered codes and opaque references are written; operands and
    exception text never reach the log.
    """
    log = _log.info if receipt.condition is OperationTerminalCondition.SUCCEEDED else _log.warning
    log(
        "operation settled operation=%s definition=%s condition=%s effect=%s cause=%s"
        " refusal=%s failure=%s diagnostic=%s",
        receipt.identity.operation_id,
        receipt.identity.definition_id,
        receipt.condition.value,
        receipt.effect.value,
        cause,
        receipt.refusal_ref or "-",
        receipt.failure_error_code or "-",
        receipt.diagnostic_ref or "-",
    )
