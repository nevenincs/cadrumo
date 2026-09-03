"""Six safe, host-neutral AEAT Sync projection screens."""

from __future__ import annotations

from enum import Enum
from typing import ClassVar, Final, Protocol, cast, override

from textual.app import ComposeResult
from textual.binding import Binding
from textual.message import Message
from textual.screen import Screen
from textual.widgets import Button, DataTable, Static

from ....application.aeat_sync.workspace import (
    AeatSyncNotificationReadState,
    AeatSyncWorkspaceNotificationRowV1,
    AeatSyncWorkspaceZone,
)
from ....application.operations.models import OperationDefinitionId
from ....application.operator_actions.models import ActionReference
from ....core.filing_year import FilingYear
from ....core.i18n.render import tr
from ....core.period import Period
from ....domain.modelos.codes import ModeloCode
from ..components.theme import BASE_CSS, tokenised
from ..components.widgets import ContentDataTable, ContentScroll
from .controller import AeatSyncWorkspaceController
from .models import AeatSyncOperationRequestV1, AeatSyncRouteTargetV1

_LABEL_PREFIXES: Final = {
    "AeatSyncWorkspaceZone": "tui.aeat_sync.zone",
    "AeatSyncWorkspaceAvailability": "tui.aeat_sync.availability",
    "AeatSyncWorkspaceSource": "tui.aeat_sync.source",
    "AeatSyncOverviewArea": "tui.aeat_sync.area",
    "AeatSyncSourceState": "tui.aeat_sync.source_state",
    "AeatSyncDiscrepancyKind": "tui.aeat_sync.discrepancy",
    "AeatSyncCensusCategory": "tui.aeat_sync.census_category",
    "AeatSyncCensusStatus": "tui.aeat_sync.census_status",
    "AeatSyncLocalFilingState": "tui.aeat_sync.local_filing_state",
    "AeatSyncAeatObservationState": "tui.aeat_sync.aeat_observation_state",
    "AeatSyncJustificanteState": "tui.aeat_sync.justificante_state",
    "AeatSyncNotificationCategory": "tui.aeat_sync.notification_category",
    "AeatSyncNotificationReadState": "tui.aeat_sync.notification_read_state",
    "AeatSyncDocumentCustodyState": "tui.aeat_sync.document_custody_state",
    "AeatSyncReconciliationState": "tui.aeat_sync.reconciliation_state",
}


def aeat_sync_copy(key: str, **values: object) -> str:
    """Resolve every operator-facing AEAT Sync string through one boundary."""
    return tr(key, **values)


def _label(value: Enum | None) -> str:
    """Render a public enum through its authored semantic catalogue key."""
    if value is None:
        return aeat_sync_copy("tui.aeat_sync.value.none")
    prefix = _LABEL_PREFIXES.get(type(value).__name__)
    if prefix is None:
        raise ValueError("unsupported AEAT Sync operator label")
    return aeat_sync_copy(f"{prefix}.{value.value}")


def _compact(value: str, width: int) -> str:
    """Keep safe labels inside the fixed terminal content column."""
    if len(value) <= width:
        return value
    return f"{value[: width - 1]}…"


def _census_identity(path: str) -> str:
    """Derive a stable key from the safe canonical census path only."""
    return f"census:{' '.join(path.split()).casefold()}"


def _natural_identity(row: _NaturalRow, *, prefix: str) -> str:
    """Derive a stable key from a public declaration coordinate."""
    return f"{prefix}:{row.modelo}|{row.filing_year}|{row.period.registry_token}"


def _notification_identity(row: AeatSyncWorkspaceNotificationRowV1, index: int) -> str:
    """Derive a safe deterministic key without retaining private identity."""
    return (
        f"notification:{row.issued_on}|{row.read_on}|{row.read_state.value}|"
        f"{row.category.value}|{row.document_custody_state.value}|{index}"
    )


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
    return aeat_sync_copy(
        "tui.aeat_sync.address.declaration",
        modelo=row.modelo,
        filing_year=row.filing_year,
        period=row.period.registry_token,
    )


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
        yield Static(aeat_sync_copy(self.heading), classes="cadrumo-banner", markup=False)
        with ContentScroll(id="aeat-sync-page", classes="cadrumo-scroll"):
            yield ContentDataTable[str](id="aeat-sync-navigation", cursor_type="row", zebra_stripes=True)
            yield ContentDataTable[str](id="aeat-sync-rows", cursor_type="row", zebra_stripes=True)
            yield Static(id="aeat-sync-status", markup=False)

    def on_mount(self) -> None:
        """Render all six independent source states and this screen's safe rows."""
        navigation = cast("DataTable[str]", self.query_one("#aeat-sync-navigation", DataTable))
        navigation.add_columns(
            aeat_sync_copy("tui.aeat_sync.column.area"),
            aeat_sync_copy("tui.aeat_sync.column.availability"),
            aeat_sync_copy("tui.aeat_sync.column.sources"),
        )
        for zone in AeatSyncWorkspaceZone:
            state = self.controller.state_for(zone)
            navigation.add_row(
                _label(zone),
                _label(state.availability),
                aeat_sync_copy(
                    "tui.aeat_sync.sources.joined",
                    entries=", ".join(
                        aeat_sync_copy(
                            "tui.aeat_sync.sources.entry",
                            source=_label(source.source),
                            availability=_label(source.availability),
                        )
                        for source in state.sources
                    ),
                ),
                key=zone.value,
            )
        self.populate_rows(cast("DataTable[str]", self.query_one("#aeat-sync-rows", DataTable)))
        self.query_one("#aeat-sync-navigation", DataTable).focus()

    def populate_rows(self, table: DataTable[str]) -> None:
        """Populate one safe public zone body in subclasses."""
        raise NotImplementedError

    def add_operation(self, row: _OperationRow, *, label: str) -> None:
        """Render an explicit mutation button only for a closed admitted pair."""
        request = self.controller.admitted_operation(
            getattr(row, "supported_actions", ()), getattr(row, "supported_operations", ())
        )
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
            status.update(aeat_sync_copy("tui.aeat_sync.refusal.operation_handoff"))
            return
        try:
            await handoff(request)
        except Exception:  # host boundary must not disclose protected diagnostics
            status.update(aeat_sync_copy("tui.aeat_sync.operation.failed"))
        else:
            status.update(aeat_sync_copy("tui.aeat_sync.operation.handed_off"))

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Request a host-owned internal route only for an observable zone."""
        table = cast("DataTable[str]", event.data_table)
        if table.id != "aeat-sync-navigation":
            return
        zone = AeatSyncWorkspaceZone(event.row_key.value)
        if not self.controller.can_open(zone):
            self.query_one("#aeat-sync-status", Static).update(aeat_sync_copy("tui.aeat_sync.refusal.source"))
            return
        self.post_message(AeatSyncRouteRequested(self.controller.target(zone)))

    def action_back(self) -> None:
        """Dismiss only this child; the installed root owns the return journey."""
        self.dismiss(None)


class AeatSyncOverviewScreen(AeatSyncWorkspaceScreen):
    """Overview preserving local, AEAT, and discrepancy axes per area."""

    zone = AeatSyncWorkspaceZone.OVERVIEW
    heading = "tui.aeat_sync.overview.title"

    def __init__(self, controller: AeatSyncWorkspaceController) -> None:
        """Build the overview body."""
        super().__init__(controller, id="aeat-sync-overview-screen")

    @override
    def populate_rows(self, table: DataTable[str]) -> None:
        """Render public overview states without collapsing either source."""
        table.add_columns(
            aeat_sync_copy("tui.aeat_sync.column.area"),
            aeat_sync_copy("tui.aeat_sync.column.local"),
            aeat_sync_copy("tui.aeat_sync.column.aeat"),
            aeat_sync_copy("tui.aeat_sync.column.difference"),
        )
        for row in self.controller.projection.overview:
            table.add_row(
                _label(row.area), _label(row.local_state), _label(row.aeat_state), _label(row.discrepancy_kind)
            )
            self.add_operation(
                cast("_OperationRow", row),
                label=aeat_sync_copy("tui.aeat_sync.action.review_census") if row.supported_actions else "",
            )


class AeatSyncCensusScreen(AeatSyncWorkspaceScreen):
    """Census comparison without taxpayer values."""

    zone = AeatSyncWorkspaceZone.CENSUS
    heading = "tui.aeat_sync.census.title"

    def __init__(self, controller: AeatSyncWorkspaceController) -> None:
        """Build the census body."""
        super().__init__(controller, id="aeat-sync-census-screen")

    @override
    def populate_rows(self, table: DataTable[str]) -> None:
        """Render safe census path/category/status metadata only."""
        table.add_columns(
            aeat_sync_copy("tui.aeat_sync.column.field"),
            aeat_sync_copy("tui.aeat_sync.column.category"),
            aeat_sync_copy("tui.aeat_sync.column.status"),
        )
        for row in self.controller.projection.census:
            table.add_row(row.path, _label(row.category), _label(row.status))
            self.add_operation(cast("_OperationRow", row), label=aeat_sync_copy("tui.aeat_sync.action.review_census"))


class AeatSyncFiledDeclarationsScreen(AeatSyncWorkspaceScreen):
    """Filed declaration observation retaining local and AEAT state separately."""

    zone = AeatSyncWorkspaceZone.FILED_DECLARATIONS
    heading = "tui.aeat_sync.filed_declarations.title"

    def __init__(self, controller: AeatSyncWorkspaceController) -> None:
        """Build the filed-declarations body."""
        super().__init__(controller, id="aeat-sync-filed-declarations-screen")

    @override
    def populate_rows(self, table: DataTable[str]) -> None:
        """Render only public filing and receipt state."""
        table.add_columns(
            aeat_sync_copy("tui.aeat_sync.column.declaration"),
            aeat_sync_copy("tui.aeat_sync.column.local_filing"),
            aeat_sync_copy("tui.aeat_sync.column.aeat"),
            aeat_sync_copy("tui.aeat_sync.column.receipt"),
        )
        for row in self.controller.projection.filed_declarations:
            table.add_row(
                _address(row),
                _label(row.local_filing_state),
                _label(row.aeat_observation_state),
                _label(row.justificante_state),
            )
            self.add_operation(cast("_OperationRow", row), label=aeat_sync_copy("tui.aeat_sync.action.pull_filed"))


class AeatSyncNotificationsScreen(AeatSyncWorkspaceScreen):
    """Notification metadata surface with no identity or document content."""

    zone = AeatSyncWorkspaceZone.NOTIFICATIONS
    heading = "tui.aeat_sync.notifications.title"

    def __init__(self, controller: AeatSyncWorkspaceController) -> None:
        """Build the notifications body."""
        super().__init__(controller, id="aeat-sync-notifications-screen")

    @override
    def populate_rows(self, table: DataTable[str]) -> None:
        """Render dates and public read/custody metadata only."""
        table.add_columns(
            aeat_sync_copy("tui.aeat_sync.column.issued"),
            aeat_sync_copy("tui.aeat_sync.column.read"),
            aeat_sync_copy("tui.aeat_sync.column.category"),
            aeat_sync_copy("tui.aeat_sync.column.document_custody"),
        )
        for row in self.controller.projection.notifications:
            table.add_row(
                str(row.issued_on), _label(row.read_state), _label(row.category), _label(row.document_custody_state)
            )


class AeatSyncEvidenceComparisonScreen(AeatSyncWorkspaceScreen):
    """Evidence comparison screen retaining the two observed source states."""

    zone = AeatSyncWorkspaceZone.EVIDENCE_COMPARISON
    heading = "tui.aeat_sync.evidence_comparison.title"

    def __init__(self, controller: AeatSyncWorkspaceController) -> None:
        """Build the evidence-comparison body."""
        super().__init__(controller, id="aeat-sync-evidence-comparison-screen")

    @override
    def populate_rows(self, table: DataTable[str]) -> None:
        """Render a safe public comparison coordinate and discrepancy."""
        table.add_columns(
            aeat_sync_copy("tui.aeat_sync.column.declaration"),
            aeat_sync_copy("tui.aeat_sync.column.local"),
            aeat_sync_copy("tui.aeat_sync.column.aeat"),
            aeat_sync_copy("tui.aeat_sync.column.difference"),
        )
        for row in self.controller.projection.evidence_comparison:
            table.add_row(_address(row), _label(row.local_state), _label(row.aeat_state), _label(row.discrepancy_kind))
            self.add_operation(cast("_OperationRow", row), label=aeat_sync_copy("tui.aeat_sync.action.pull_comparison"))


class AeatSyncReconciliationScreen(AeatSyncWorkspaceScreen):
    """Reconciliation status surface without a generic mutation path."""

    zone = AeatSyncWorkspaceZone.RECONCILIATION
    heading = "tui.aeat_sync.reconciliation.title"

    def __init__(self, controller: AeatSyncWorkspaceController) -> None:
        """Build the reconciliation body."""
        super().__init__(controller, id="aeat-sync-reconciliation-screen")

    @override
    def populate_rows(self, table: DataTable[str]) -> None:
        """Render source states, discrepancy, and application-set resolution."""
        table.add_columns(
            aeat_sync_copy("tui.aeat_sync.column.declaration"),
            aeat_sync_copy("tui.aeat_sync.column.local"),
            aeat_sync_copy("tui.aeat_sync.column.aeat"),
            aeat_sync_copy("tui.aeat_sync.column.difference"),
            aeat_sync_copy("tui.aeat_sync.column.resolution"),
        )
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
