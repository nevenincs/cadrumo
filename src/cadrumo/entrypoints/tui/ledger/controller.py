"""Pure controller and common interaction shell for Ledger destinations."""

from __future__ import annotations

from typing import ClassVar, Final, cast

from textual.binding import Binding
from textual.message import Message
from textual.screen import Screen
from textual.widgets import DataTable, Static

from ....application.ledger.models import (
    LedgerSourceImportResult,
    ManualLedgerTransactionPatch,
    ManualLedgerTransactionResult,
)
from ....application.ledger.workspace import (
    LEDGER_WORKSPACE_CONTRACT_VERSION,
    LedgerWorkspaceArea,
    LedgerWorkspaceAreaStateV1,
    LedgerWorkspaceAvailability,
    LedgerWorkspaceProjectionV1,
    LedgerWorkspaceStatus,
)
from ....application.operator_actions.catalogue import lookup_action
from ....application.operator_actions.models import ActionReference
from ....core.i18n.render import tr
from ....core.identity import TransactionId
from ..components.theme import BASE_CSS, tokenised
from ..navigation import TuiScreenContextV1
from .models import (
    LedgerClassificationSubmissionV1,
    LedgerClassificationSubmitterV1,
    LedgerDestinationIdV1,
    LedgerEntryRowV1,
    LedgerImportSubmitterV1,
    LedgerPreparedImportV1,
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
    {
        LedgerWorkspaceArea.OVERVIEW,
        LedgerWorkspaceArea.ENTRIES,
        LedgerWorkspaceArea.REVIEW,
        LedgerWorkspaceArea.IMPORT,
        LedgerWorkspaceArea.CLASSIFICATION,
    }
)

_AREA_LOCALE_KEYS: Final = {
    LedgerWorkspaceArea.OVERVIEW: "tui.ledger.area.overview",
    LedgerWorkspaceArea.ENTRIES: "tui.ledger.area.entries",
    LedgerWorkspaceArea.REVIEW: "tui.ledger.area.review",
    LedgerWorkspaceArea.IMPORT: "tui.ledger.area.import",
    LedgerWorkspaceArea.CLASSIFICATION: "tui.ledger.area.classification",
    LedgerWorkspaceArea.EVIDENCE: "tui.ledger.area.evidence",
    LedgerWorkspaceArea.RECONCILIATION: "tui.ledger.area.reconciliation",
}
_AVAILABILITY_LOCALE_KEYS: Final = {
    LedgerWorkspaceAvailability.AVAILABLE: "tui.ledger.availability.available",
    LedgerWorkspaceAvailability.LOCKED: "tui.ledger.availability.locked",
    LedgerWorkspaceAvailability.STALE: "tui.ledger.availability.stale",
    LedgerWorkspaceAvailability.NEVER_CAPTURED: "tui.ledger.availability.never_captured",
    LedgerWorkspaceAvailability.UNAVAILABLE: "tui.ledger.availability.unavailable",
}
_REVIEW_STATUS_LOCALE_KEYS: Final = {
    "pending": "tui.ledger.review_status.pending",
    "reviewed": "tui.ledger.review_status.reviewed",
    "skipped": "tui.ledger.review_status.skipped",
}
_STATUS_LOCALE_KEYS: Final = {
    LedgerWorkspaceStatus.READY: "tui.ledger.status.ready",
    LedgerWorkspaceStatus.EMPTY: "tui.ledger.status.empty",
    LedgerWorkspaceStatus.NEEDS_ATTENTION: "tui.ledger.status.needs_attention",
    LedgerWorkspaceStatus.UNMEASURED: "tui.ledger.status.unmeasured",
}
_LEDGER_LOCALE_KEYS: Final = (
    "tui.ledger.column.destination",
    "tui.ledger.column.availability",
    "tui.ledger.column.items",
    "tui.ledger.column.area",
    "tui.ledger.column.status",
    "tui.ledger.column.entry",
    "tui.ledger.column.review_status",
    "tui.ledger.column.next",
    "tui.ledger.refusal.application_state",
    "tui.ledger.refusal.destination_pending",
    "tui.ledger.overview.title",
    "tui.ledger.overview.quality",
    "tui.ledger.overview.affected_declarations",
    "tui.ledger.entries.title",
    "tui.ledger.entries.redacted",
    "tui.ledger.entries.empty",
    "tui.ledger.review.title",
    "tui.ledger.review.filter_all",
    "tui.ledger.review.open",
    "tui.ledger.review.empty",
    "tui.ledger.unavailable.title",
    "tui.ledger.refusal.submission_unavailable",
    "tui.ledger.classification.title",
    "tui.ledger.classification.prompt",
    "tui.ledger.classification.target",
    "tui.ledger.classification.business",
    "tui.ledger.classification.personal",
    "tui.ledger.classification.excluded",
    "tui.ledger.classification.confirm",
    "tui.ledger.classification.cancel",
    "tui.ledger.classification.confirming",
    "tui.ledger.classification.progress",
    "tui.ledger.classification.success",
    "tui.ledger.classification.failure",
    "tui.ledger.flow.in_flight_refusal",
    "tui.ledger.import.title",
    "tui.ledger.import.prompt",
    "tui.ledger.import.provider.bank",
    "tui.ledger.import.source.prepared",
    "tui.ledger.import.confirm",
    "tui.ledger.import.cancel",
    "tui.ledger.import.confirming",
    "tui.ledger.import.progress",
    "tui.ledger.import.success",
    "tui.ledger.import.failure",
    "tui.ledger.import.empty",
    *_AREA_LOCALE_KEYS.values(),
    *_AVAILABILITY_LOCALE_KEYS.values(),
    *_REVIEW_STATUS_LOCALE_KEYS.values(),
    *_STATUS_LOCALE_KEYS.values(),
)


def ledger_copy(key: str, **values: object) -> str:
    """Resolve all operator copy through the canonical catalogue boundary."""
    return tr(key, **values)


def area_label(area: LedgerWorkspaceArea) -> str:
    """Return an operator label without displaying an internal enum token."""
    return ledger_copy(_AREA_LOCALE_KEYS[area])


def availability_label(availability: LedgerWorkspaceAvailability) -> str:
    """Render availability with a textual cue independent of colour."""
    return ledger_copy(_AVAILABILITY_LOCALE_KEYS[availability])


def review_status_label(status: str) -> str:
    """Translate a source status without leaking its transport spelling."""
    key = _REVIEW_STATUS_LOCALE_KEYS.get(status)
    if key is None:
        raise ValueError("unsupported Ledger review status")
    return ledger_copy(key)


def status_label(status: LedgerWorkspaceStatus) -> str:
    """Render source status through its authored catalogue key."""
    return ledger_copy(_STATUS_LOCALE_KEYS[status])


def item_count_label(state: LedgerWorkspaceAreaStateV1) -> str:
    """Keep an unmeasured denominator distinct from a measured numeric zero."""
    return status_label(state.status) if state.status is LedgerWorkspaceStatus.UNMEASURED else str(state.item_count)


class LedgerWorkspaceController:
    """Read-only custody of one injected application projection and shell context."""

    def __init__(
        self,
        context: TuiScreenContextV1,
        projection: LedgerWorkspaceProjectionV1,
        *,
        review_action: ActionReference,
        classify_action: ActionReference | None = None,
        classification_target: TransactionId | None = None,
        classification_submitter: LedgerClassificationSubmitterV1 | None = None,
        prepared_imports: tuple[LedgerPreparedImportV1, ...] = (),
        import_submitter: LedgerImportSubmitterV1 | None = None,
    ) -> None:
        """Admit an outer Ledger context and retain its immutable snapshot."""
        if context.destination != "workbench.ledger":
            raise ValueError("Ledger workspace requires the workbench.ledger screen context")
        if projection.contract_version != LEDGER_WORKSPACE_CONTRACT_VERSION:
            raise ValueError("unsupported Ledger workspace projection contract")
        self.context = context
        self.projection = projection
        visible_ids = {row.transaction_id for row in projection.entries}
        if classification_target is not None and classification_target not in visible_ids:
            raise ValueError("classification target is absent from the visible Ledger projection")
        if (
            classify_action is not None
            and lookup_action(classify_action.action_id).target_command_key != "ledger.classify"
        ):
            raise ValueError("injected Ledger classification action does not resolve to the canonical command")
        choice_ids = tuple(choice.choice_id for choice in prepared_imports)
        if len(choice_ids) != len(set(choice_ids)):
            raise ValueError("prepared import choice identities must be unique")
        self.review_action = review_action
        self.classify_action = classify_action
        self.classification_target = classification_target
        self.classification_submitter = classification_submitter
        self.prepared_imports = prepared_imports
        self.import_submitter = import_submitter
        self._states = {row.area: row for row in projection.areas}

    def classification_target_coordinate(self) -> tuple[int, int, str]:
        """Return a safe position and redacted identifier from the visible projection."""
        target = self.classification_target
        if target is None:
            raise RuntimeError("classification target is unavailable")
        position = next(
            index for index, row in enumerate(self.projection.entries, start=1) if row.transaction_id == target
        )
        return position, len(self.projection.entries), str(target)[:12]

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
        missing_door = (
            area is LedgerWorkspaceArea.CLASSIFICATION
            and (
                self.classify_action is None
                or self.classification_target is None
                or self.classification_submitter is None
            )
        ) or (area is LedgerWorkspaceArea.IMPORT and (not self.prepared_imports or self.import_submitter is None))
        if area not in _IMPLEMENTED_AREAS or missing_door:
            return LedgerRouteRefusalV1(
                target=target,
                availability=LedgerWorkspaceAvailability.UNAVAILABLE,
                reason_key=(
                    "tui.ledger.refusal.submission_unavailable"
                    if missing_door
                    else "tui.ledger.refusal.destination_pending"
                ),
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

    def restored_transaction_id(self) -> TransactionId | None:
        """Resolve a transaction focus by semantic identity, never by row position."""
        focus = self.context.focus
        if focus is None or focus.semantic_key != "ledger.transaction" or focus.restore_token is None:
            return None
        candidate = focus.restore_token
        return candidate if any(row.transaction_id == candidate for row in self.projection.entries) else None

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
                    action=self.review_action,
                    source=source,
                )
            )
        return tuple(rows)

    async def submit_classification(
        self, patch: ManualLedgerTransactionPatch
    ) -> ManualLedgerTransactionResult:
        """Submit an explicit patch through the injected authorized door."""
        if self.classify_action is None or self.classification_target is None or self.classification_submitter is None:
            raise RuntimeError("classification submission is unavailable")
        submission = LedgerClassificationSubmissionV1(
            action=self.classify_action,
            transaction_id=self.classification_target,
            patch=patch,
        )
        result = await self.classification_submitter(submission)
        if result.ref.transaction_id != self.classification_target:
            raise ValueError("classification result transaction identity disagrees")
        return result

    async def submit_import(self, prepared: LedgerPreparedImportV1) -> LedgerSourceImportResult:
        """Pass an opaque pre-resolved command to the injected import door."""
        if self.import_submitter is None or prepared not in self.prepared_imports:
            raise RuntimeError("import submission is unavailable")
        return await prepared.submit_with(self.import_submitter)


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


class LedgerEntrySelected(Message):
    """Host-facing semantic selection of one safe Ledger entry reference."""

    def __init__(self, transaction_id: TransactionId) -> None:
        """Store only the application projection's safe transaction identity."""
        super().__init__()
        self.transaction_id = transaction_id


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
        table.add_column(ledger_copy("tui.ledger.column.destination"), key="destination")
        table.add_column(ledger_copy("tui.ledger.column.availability"), key="availability")
        table.add_column(ledger_copy("tui.ledger.column.items"), key="items")
        for area in LedgerWorkspaceArea:
            state = self.controller.state_for(area)
            refusal = self.controller.refusal_for(area)
            availability = state.availability if refusal is None else refusal.availability
            table.add_row(area_label(area), availability_label(availability), item_count_label(state), key=area.value)

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
                ledger_copy(refusal.reason_key)
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
    "LedgerEntrySelected",
    "LedgerReviewRequested",
    "LedgerRouteRequested",
    "LedgerWorkspaceController",
    "LedgerWorkspaceScreen",
    "area_label",
    "availability_label",
    "item_count_label",
    "ledger_copy",
    "review_status_label",
    "status_label",
]
