"""Pure controller and common interaction shell for Ledger destinations."""

from __future__ import annotations

from typing import ClassVar, Final, cast

from textual.binding import Binding
from textual.message import Message
from textual.screen import Screen
from textual.widgets import DataTable, Static

from ....application.ledger.workspace import (
    LEDGER_WORKSPACE_CONTRACT_VERSION,
    LedgerWorkspaceArea,
    LedgerWorkspaceAreaStateV1,
    LedgerWorkspaceAvailability,
    LedgerWorkspaceProjectionV1,
)
from ....application.operator_actions.models import ActionReference
from ....core.i18n.render import tr
from ....core.identity import TransactionId
from ..components.theme import BASE_CSS, tokenised
from ..navigation import TuiScreenContextV1
from .models import (
    LedgerDestinationIdV1,
    LedgerEntryRowV1,
    LedgerReviewRowV1,
    LedgerRouteRefusalV1,
    LedgerRouteTargetV1,
)

_DESTINATION_BY_AREA: Final = {
    LedgerWorkspaceArea.OVERVIEW: "ledger.overview",
    LedgerWorkspaceArea.ENTRIES: "ledger.entries",
    LedgerWorkspaceArea.REVIEW: "ledger.review",
    LedgerWorkspaceArea.IMPORT: "ledger.import",
    LedgerWorkspaceArea.CLASSIFICATION: "ledger.classification",
    LedgerWorkspaceArea.EVIDENCE: "ledger.evidence",
    LedgerWorkspaceArea.RECONCILIATION: "ledger.reconciliation",
}

_IMPLEMENTED_AREAS: Final = frozenset(
    {LedgerWorkspaceArea.OVERVIEW, LedgerWorkspaceArea.ENTRIES, LedgerWorkspaceArea.REVIEW}
)


def ledger_copy(key: str, *, default: str, **values: object) -> str:
    """Resolve all operator copy through the canonical catalogue boundary."""
    return tr(key, default=default, **values)


def area_label(area: LedgerWorkspaceArea) -> str:
    """Return an operator label without displaying an internal enum token."""
    return ledger_copy(f"tui.ledger.area.{area.value}", default=area.value.replace("_", " ").title())


def availability_label(availability: LedgerWorkspaceAvailability) -> str:
    """Render availability with a textual cue independent of colour."""
    defaults = {
        LedgerWorkspaceAvailability.AVAILABLE: "Available",
        LedgerWorkspaceAvailability.LOCKED: "Locked",
        LedgerWorkspaceAvailability.STALE: "Stale",
        LedgerWorkspaceAvailability.NEVER_CAPTURED: "Not captured",
        LedgerWorkspaceAvailability.UNAVAILABLE: "Unavailable",
    }
    return ledger_copy(f"tui.ledger.availability.{availability.value}", default=defaults[availability])


def review_status_label(status: str) -> str:
    """Translate a source status without leaking its transport spelling."""
    defaults = {"pending": "Pending", "reviewed": "Reviewed", "skipped": "Skipped"}
    return ledger_copy(f"tui.ledger.review_status.{status}", default=defaults.get(status, "Other"))


class LedgerWorkspaceController:
    """Read-only custody of one injected application projection and shell context."""

    def __init__(self, context: TuiScreenContextV1, projection: LedgerWorkspaceProjectionV1) -> None:
        """Admit an outer Ledger context and retain its immutable snapshot."""
        if context.destination != "workbench.ledger":
            raise ValueError("Ledger workspace requires the workbench.ledger screen context")
        if projection.contract_version != LEDGER_WORKSPACE_CONTRACT_VERSION:
            raise ValueError("unsupported Ledger workspace projection contract")
        self.context = context
        self.projection = projection
        self._states = {row.area: row for row in projection.areas}

    def state_for(self, area: LedgerWorkspaceArea) -> LedgerWorkspaceAreaStateV1:
        """Return the application-owned area state."""
        return self._states[area]

    def route_target(self, area: LedgerWorkspaceArea) -> LedgerRouteTargetV1:
        """Build an internal semantic target without invoking it."""
        return LedgerRouteTargetV1(destination=cast("LedgerDestinationIdV1", _DESTINATION_BY_AREA[area]), area=area)

    def refusal_for(self, area: LedgerWorkspaceArea) -> LedgerRouteRefusalV1 | None:
        """Preserve application refusal separately from deferred screen availability."""
        target = self.route_target(area)
        state = self.state_for(area)
        if state.availability is not LedgerWorkspaceAvailability.AVAILABLE:
            return LedgerRouteRefusalV1(
                target=target,
                availability=state.availability,
                reason_key="tui.ledger.refusal.application_state",
            )
        if area not in _IMPLEMENTED_AREAS:
            return LedgerRouteRefusalV1(
                target=target,
                availability=LedgerWorkspaceAvailability.UNAVAILABLE,
                reason_key="tui.ledger.refusal.destination_pending",
            )
        return None

    def entry_rows(self) -> tuple[LedgerEntryRowV1, ...]:
        """Narrow safe application entry references without recovering payloads."""
        return tuple(
            LedgerEntryRowV1(
                transaction_id=row.transaction_id,
                review_status=row.review_status,
                source=row,
            )
            for row in self.projection.entries
        )

    def review_rows(self) -> tuple[LedgerReviewRowV1, ...]:
        """Join review identities to safe entry references, refusing contradictions."""
        by_id = {row.transaction_id: row for row in self.projection.entries}
        rows: list[LedgerReviewRowV1] = []
        for transaction_id in self.projection.review_transaction_ids:
            source = by_id.get(transaction_id)
            if source is None:
                raise ValueError("Ledger review identity is absent from the projected entry catalogue")
            rows.append(
                LedgerReviewRowV1(
                    transaction_id=transaction_id,
                    review_status=source.review_status,
                    action=ActionReference(action_id="operator.ledger.review"),
                    source=source,
                )
            )
        return tuple(rows)


class LedgerRouteRequested(Message):
    """Host-facing request to replace the active Ledger destination body."""

    def __init__(self, target: LedgerRouteTargetV1) -> None:
        """Store the internal semantic target for the owning host."""
        super().__init__()
        self.target = target


class LedgerReviewRequested(Message):
    """Host-facing request naming a real application query and transaction focus."""

    def __init__(self, *, transaction_id: TransactionId, action: ActionReference) -> None:
        """Store the safe transaction identity and canonical query action."""
        super().__init__()
        self.transaction_id = transaction_id
        self.action = action


class LedgerBackRequested(Message):
    """Request that the owning host return to the parent destination."""


class LedgerWorkspaceScreen(Screen[None]):
    """Shared one-scroll shell and semantic navigation behavior."""

    BINDINGS: ClassVar = [Binding("escape", "back", "", show=False)]
    CSS = BASE_CSS + tokenised(
        """
        .ledger-page { width: 100%; height: 1fr; }
        .ledger-section { width: 100%; height: auto; margin-bottom: $cadrumo-stack; }
        .ledger-refusal { color: $warning; text-style: bold; height: auto; }
        .ledger-empty { color: $text-muted; height: auto; }
        """
    )

    def __init__(self, controller: LedgerWorkspaceController, *, id: str | None = None) -> None:
        """Retain the read-only controller and interaction observations."""
        super().__init__(id=id)
        self.controller = controller
        self.requested_target: LedgerRouteTargetV1 | None = None
        self.refusal: LedgerRouteRefusalV1 | None = None
        self.back_requested = False

    def populate_navigation(self) -> None:
        """Populate the complete seven-area catalogue in canonical order."""
        table = cast("DataTable[str]", self.query_one("#ledger-navigation", DataTable))
        table.add_column(ledger_copy("tui.ledger.column.destination", default="Destination"), key="destination")
        table.add_column(ledger_copy("tui.ledger.column.availability", default="Availability"), key="availability")
        table.add_column(ledger_copy("tui.ledger.column.items", default="Items"), key="items")
        for area in LedgerWorkspaceArea:
            state = self.controller.state_for(area)
            refusal = self.controller.refusal_for(area)
            availability = state.availability if refusal is None else refusal.availability
            table.add_row(area_label(area), availability_label(availability), str(state.item_count), key=area.value)

    def handle_navigation_selection(self, event: DataTable.RowSelected) -> bool:
        """Handle the common navigation table and expose refusals as visible copy."""
        event_table = cast("DataTable[str]", event.data_table)
        if event_table.id != "ledger-navigation":
            return False
        area = LedgerWorkspaceArea(str(event.row_key.value))
        refusal = self.controller.refusal_for(area)
        notice = self.query_one("#ledger-refusal", Static)
        if refusal is not None:
            self.refusal = refusal
            notice.update(
                ledger_copy(
                    refusal.reason_key,
                    default="This destination is not available in the current workspace.",
                )
            )
            return True
        target = self.controller.route_target(area)
        self.requested_target = target
        notice.update("")
        self.post_message(LedgerRouteRequested(target))
        return True

    def action_back(self) -> None:
        """Ask the host to return; never terminate the application."""
        self.back_requested = True
        self.post_message(LedgerBackRequested())


__all__ = [
    "LedgerBackRequested",
    "LedgerReviewRequested",
    "LedgerRouteRequested",
    "LedgerWorkspaceController",
    "LedgerWorkspaceScreen",
    "area_label",
    "availability_label",
    "ledger_copy",
    "review_status_label",
]
