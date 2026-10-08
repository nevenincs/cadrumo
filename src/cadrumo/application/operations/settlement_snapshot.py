"""Terminal snapshot construction shared by supervised and terminated owners."""

from __future__ import annotations

from ...core.operations import OperationLifecycle
from .models import OperationTerminalReceipt
from .persistence.events import OperationEvent
from .persistence.journal import OperationPersistedSnapshot


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
