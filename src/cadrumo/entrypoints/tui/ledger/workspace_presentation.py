"""Reusable Ledger workspace layout, focus, and confirmation mechanics."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from typing import ClassVar, override

from textual.widgets import DataTable, Static

from ....core.identity import TransactionId
from ..components.widgets import ContentDataTable, ContentScroll
from .controller import LedgerWorkspaceController, LedgerWorkspaceScreen, ledger_copy
from .models import LedgerFlowState

#: The legal moves of a confirmed Ledger flow, as a state a caller can read.
#:
#: A state absent from this mapping is terminal and absorbing: ``SUCCEEDED``,
#: ``FAILED`` and ``CANCELLED`` admit no move at all, so a screen cannot be
#: driven back into an editable state after its command has settled.
#:
#: Two absences are the safety of the machine rather than gaps in it.
#: ``EDITING`` cannot reach ``SUBMITTING``, so nothing is written without
#: passing the confirmation step; and ``SUBMITTING`` cannot reach
#: ``CANCELLED``, so a write already in flight cannot be abandoned — which is
#: what :meth:`LedgerConfirmationFlowScreen.action_back` refuses out loud.
#:
#: Held here rather than rebuilt inside the transition method so the machine
#: can be read and tested as the specification it is.
ALLOWED_FLOW_TRANSITIONS: dict[LedgerFlowState, frozenset[LedgerFlowState]] = {
    LedgerFlowState.EDITING: frozenset({LedgerFlowState.CONFIRMING, LedgerFlowState.CANCELLED}),
    LedgerFlowState.CONFIRMING: frozenset({LedgerFlowState.SUBMITTING, LedgerFlowState.CANCELLED}),
    LedgerFlowState.SUBMITTING: frozenset({LedgerFlowState.SUCCEEDED, LedgerFlowState.FAILED}),
}


@contextmanager
def ledger_workspace_page() -> Generator[ContentDataTable[str]]:
    """Compose the one scroll owner and canonical workspace navigation table."""
    with ContentScroll(id="ledger-page", classes="cadrumo-scroll ledger-page"):
        yield ContentDataTable[str](id="ledger-navigation", cursor_type="row", zebra_stripes=True)


def restore_transaction_focus(
    *,
    navigation: DataTable[str],
    table: DataTable[str],
    transaction_id: TransactionId | None,
) -> None:
    """Focus a transaction by semantic identity or return focus to navigation."""
    if transaction_id is None:
        navigation.focus()
        return
    row_index = next((index for index, row in enumerate(table.ordered_rows) if row.key.value == transaction_id), None)
    if row_index is not None:
        table.move_cursor(row=row_index)
        table.focus()


class LedgerConfirmationFlowScreen(LedgerWorkspaceScreen):
    """Shared presentation state machine for confirmed, one-shot Ledger flows."""

    FLOW_NAME: ClassVar[str]

    def __init__(self, controller: LedgerWorkspaceController, *, id: str) -> None:
        """Initialise the shared flow state around an injected workspace controller."""
        super().__init__(controller, id=id)
        self._flow_state = LedgerFlowState.EDITING

    @property
    def flow_state(self) -> LedgerFlowState:
        """Expose the guarded interaction state without a public setter."""
        return self._flow_state

    def _transition(self, target: LedgerFlowState) -> None:
        if target not in ALLOWED_FLOW_TRANSITIONS.get(self._flow_state, frozenset()):
            raise RuntimeError(f"invalid {self.FLOW_NAME} flow transition")
        self._flow_state = target

    def _cancel_flow(self) -> None:
        raise NotImplementedError

    @override
    def action_back(self) -> None:
        """Refuse abandonment after submission; otherwise unwind confirmation."""
        if self.flow_state is LedgerFlowState.SUBMITTING:
            self.query_one("#ledger-flow-status", Static).update(ledger_copy("tui.ledger.flow.in_flight_refusal"))
            return
        if self.flow_state is LedgerFlowState.CONFIRMING:
            self._cancel_flow()
            return
        super().action_back()
