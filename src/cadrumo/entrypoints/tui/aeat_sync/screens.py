"""Six safe, host-neutral AEAT Sync projection screens."""

from __future__ import annotations

from typing import ClassVar, Protocol, cast, override

from textual.app import ComposeResult
from textual.binding import Binding
from textual.message import Message
from textual.screen import Screen
from textual.widgets import Button, DataTable, Static

from ....application.aeat_sync.workspace import AeatSyncWorkspaceZone
from ....application.operations.models import OperationDefinitionId
from ....application.operator_actions.models import ActionReference
from ....core.filing_year import FilingYear
from ....core.period import Period
from ....domain.modelos.codes import ModeloCode
from ..components.widgets import ContentDataTable, ContentScroll
from .controller import AeatSyncWorkspaceController
from .models import AeatSyncOperationRequestV1, AeatSyncRouteTargetV1


def _label(value: object | None) -> str:
    """Render public enum/state tokens without resolving protected values."""
    return "—" if value is None else str(getattr(value, "value", value)).replace("_", " ")


class _OperationRow(Protocol):
    """Safe operation axes which S397 already admitted into a row."""

    supported_actions: tuple[ActionReference, ...]
    supported_operations: tuple[OperationDefinitionId, ...]


class _NaturalRow(Protocol):
    """Public declaration coordinate needed for a safe display label."""

    modelo: ModeloCode
    filing_year: FilingYear
    period: Period


def _address(row: _NaturalRow) -> str:
    """Render only the public Modelo/year/period natural coordinate."""
    return f"Modelo {row.modelo} · {row.filing_year} · {row.period.registry_token}"


class AeatSyncRouteRequested(Message):
    """Ask the owning host to replace this active internal workspace body."""

    def __init__(self, target: AeatSyncRouteTargetV1) -> None:
        """Retain the prevalidated internal target."""
        super().__init__()
        self.target = target


class AeatSyncWorkspaceScreen(Screen[None]):
    """Common one-scroll shell; it reads only the injected immutable projection."""

    BINDINGS: ClassVar = [Binding("escape", "back", "", show=False)]

    zone: AeatSyncWorkspaceZone
    heading: str

    def __init__(self, controller: AeatSyncWorkspaceController, *, id: str) -> None:
        """Retain the controller and initially empty local button catalogue."""
        super().__init__(id=id)
        self.controller = controller
        self._requests: dict[str, AeatSyncOperationRequestV1] = {}

    @override
    def compose(self) -> ComposeResult:
        yield Static(self.heading, classes="cadrumo-banner", markup=False)
        with ContentScroll(id="aeat-sync-page", classes="cadrumo-scroll"):
            yield ContentDataTable[str](id="aeat-sync-navigation", cursor_type="row", zebra_stripes=True)
            yield ContentDataTable[str](id="aeat-sync-rows", cursor_type="row", zebra_stripes=True)
            yield Static(id="aeat-sync-status", markup=False)

    def on_mount(self) -> None:
        """Render all six independent source states and this screen's safe rows."""
        navigation = cast("DataTable[str]", self.query_one("#aeat-sync-navigation", DataTable))
        navigation.add_columns("Area", "Availability", "Sources")
        for zone in AeatSyncWorkspaceZone:
            state = self.controller.state_for(zone)
            navigation.add_row(
                _label(zone),
                _label(state.availability),
                ", ".join(f"{_label(source.source)}: {_label(source.availability)}" for source in state.sources),
                key=zone.value,
            )
        self.populate_rows(cast("DataTable[str]", self.query_one("#aeat-sync-rows", DataTable)))
        self.query_one("#aeat-sync-navigation", DataTable).focus()

    def populate_rows(self, table: DataTable[str]) -> None:
        """Populate one safe public zone body in subclasses."""
        raise NotImplementedError

    def add_operation(self, row: _OperationRow, *, label: str) -> None:
        """Render an explicit mutation button only for a closed admitted pair."""
        request = self.controller.admitted_operation(row.supported_actions, row.supported_operations)
        if request is None:
            return
        button_id = f"aeat-sync-operation-{len(self._requests)}"
        self._requests[button_id] = request
        self.mount(Button(label, id=button_id, classes="aeat-sync-operation"), after="#aeat-sync-status")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Hand the exact admitted request to the optional owning host door."""
        request = self._requests.get(event.button.id or "")
        if request is None:
            return
        handoff = self.controller.operation_handoff
        status = self.query_one("#aeat-sync-status", Static)
        if handoff is None:
            status.update("Operation handoff is unavailable.")
            return
        try:
            await handoff(request)
        except Exception:  # host boundary must not disclose protected diagnostics
            status.update("Operation could not be started.")
        else:
            status.update("Operation handed to the host.")

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Request a host-owned internal route only for an observable zone."""
        table = cast("DataTable[str]", event.data_table)
        if table.id != "aeat-sync-navigation":
            return
        zone = AeatSyncWorkspaceZone(event.row_key.value)
        if not self.controller.can_open(zone):
            self.query_one("#aeat-sync-status", Static).update("This source is unavailable for viewing.")
            return
        self.post_message(AeatSyncRouteRequested(self.controller.target(zone)))

    def action_back(self) -> None:
        """Dismiss only this child; the installed root owns the return journey."""
        self.dismiss(None)


class AeatSyncOverviewScreen(AeatSyncWorkspaceScreen):
    """Overview preserving local, AEAT, and discrepancy axes per area."""

    zone = AeatSyncWorkspaceZone.OVERVIEW
    heading = "AEAT Sync overview"

    def __init__(self, controller: AeatSyncWorkspaceController) -> None:
        """Build the overview body."""
        super().__init__(controller, id="aeat-sync-overview-screen")

    @override
    def populate_rows(self, table: DataTable[str]) -> None:
        """Render public overview states without collapsing either source."""
        table.add_columns("Area", "Local", "AEAT", "Difference")
        for row in self.controller.projection.overview:
            table.add_row(
                _label(row.area), _label(row.local_state), _label(row.aeat_state), _label(row.discrepancy_kind)
            )
            self.add_operation(
                cast("_OperationRow", row),
                label=f"Start {_label(row.supported_actions[0].action_id)}" if row.supported_actions else "",
            )


class AeatSyncCensusScreen(AeatSyncWorkspaceScreen):
    """Census comparison without taxpayer values."""

    zone = AeatSyncWorkspaceZone.CENSUS
    heading = "AEAT Sync census"

    def __init__(self, controller: AeatSyncWorkspaceController) -> None:
        """Build the census body."""
        super().__init__(controller, id="aeat-sync-census-screen")

    @override
    def populate_rows(self, table: DataTable[str]) -> None:
        """Render safe census path/category/status metadata only."""
        table.add_columns("Field", "Category", "Status")
        for row in self.controller.projection.census:
            table.add_row(row.path, _label(row.category), _label(row.status))
            self.add_operation(cast("_OperationRow", row), label="Review census")


class AeatSyncFiledDeclarationsScreen(AeatSyncWorkspaceScreen):
    """Filed declaration observation retaining local and AEAT state separately."""

    zone = AeatSyncWorkspaceZone.FILED_DECLARATIONS
    heading = "AEAT Sync filed declarations"

    def __init__(self, controller: AeatSyncWorkspaceController) -> None:
        """Build the filed-declarations body."""
        super().__init__(controller, id="aeat-sync-filed-declarations-screen")

    @override
    def populate_rows(self, table: DataTable[str]) -> None:
        """Render only public filing and receipt state."""
        table.add_columns("Declaration", "Local filing", "AEAT", "Receipt")
        for row in self.controller.projection.filed_declarations:
            table.add_row(
                _address(row),
                _label(row.local_filing_state),
                _label(row.aeat_observation_state),
                _label(row.justificante_state),
            )
            self.add_operation(cast("_OperationRow", row), label="Pull filed declarations")


class AeatSyncNotificationsScreen(AeatSyncWorkspaceScreen):
    """Notification metadata surface with no identity or document content."""

    zone = AeatSyncWorkspaceZone.NOTIFICATIONS
    heading = "AEAT Sync notifications"

    def __init__(self, controller: AeatSyncWorkspaceController) -> None:
        """Build the notifications body."""
        super().__init__(controller, id="aeat-sync-notifications-screen")

    @override
    def populate_rows(self, table: DataTable[str]) -> None:
        """Render dates and public read/custody metadata only."""
        table.add_columns("Issued", "Read", "Category", "Document custody")
        for row in self.controller.projection.notifications:
            table.add_row(
                str(row.issued_on), _label(row.read_state), _label(row.category), _label(row.document_custody_state)
            )


class AeatSyncEvidenceComparisonScreen(AeatSyncWorkspaceScreen):
    """Evidence comparison screen retaining the two observed source states."""

    zone = AeatSyncWorkspaceZone.EVIDENCE_COMPARISON
    heading = "AEAT Sync evidence comparison"

    def __init__(self, controller: AeatSyncWorkspaceController) -> None:
        """Build the evidence-comparison body."""
        super().__init__(controller, id="aeat-sync-evidence-comparison-screen")

    @override
    def populate_rows(self, table: DataTable[str]) -> None:
        """Render a safe public comparison coordinate and discrepancy."""
        table.add_columns("Declaration", "Local", "AEAT", "Difference")
        for row in self.controller.projection.evidence_comparison:
            table.add_row(_address(row), _label(row.local_state), _label(row.aeat_state), _label(row.discrepancy_kind))
            self.add_operation(cast("_OperationRow", row), label="Pull comparison evidence")


class AeatSyncReconciliationScreen(AeatSyncWorkspaceScreen):
    """Reconciliation status surface without a generic mutation path."""

    zone = AeatSyncWorkspaceZone.RECONCILIATION
    heading = "AEAT Sync reconciliation"

    def __init__(self, controller: AeatSyncWorkspaceController) -> None:
        """Build the reconciliation body."""
        super().__init__(controller, id="aeat-sync-reconciliation-screen")

    @override
    def populate_rows(self, table: DataTable[str]) -> None:
        """Render source states, discrepancy, and application-set resolution."""
        table.add_columns("Declaration", "Local", "AEAT", "Difference", "Resolution")
        for row in self.controller.projection.reconciliation:
            table.add_row(
                _address(row),
                _label(row.local_state),
                _label(row.aeat_state),
                _label(row.discrepancy_kind),
                _label(row.reconciliation_state),
            )


__all__ = [
    "AeatSyncCensusScreen",
    "AeatSyncEvidenceComparisonScreen",
    "AeatSyncFiledDeclarationsScreen",
    "AeatSyncNotificationsScreen",
    "AeatSyncOverviewScreen",
    "AeatSyncReconciliationScreen",
    "AeatSyncRouteRequested",
    "AeatSyncWorkspaceScreen",
]
