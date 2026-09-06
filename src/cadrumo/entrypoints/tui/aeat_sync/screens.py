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
    AeatSyncOverviewArea,
    AeatSyncWorkspaceNotificationRowV1,
    AeatSyncWorkspaceProjectionV1,
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
from ..components.workspace_host import replace_workspace_body
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
_OPERATION_LABEL_KEYS: Final = {
    ("operator.profile.edit", "user-profile.censo-review"): "tui.aeat_sync.action.review_census",
    ("operator.live.filed.pull_all", "live.filed-history.pull"): "tui.aeat_sync.action.pull_filed_all",
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


def _fit_columns(
    width: int,
    standalone: tuple[tuple[str, str, int], ...],
    pair: tuple[tuple[str, str, int], ...] = (),
) -> tuple[tuple[str, str, int], ...]:
    """Take columns in priority order, and a comparison pair whole or not at all.

    Shared by every AEAT Sync screen that compares two sides, because the rule
    is the same wherever a comparison is rendered and three copies of it would
    drift. `standalone` columns are taken while they fit; `pair` is taken only
    if BOTH fit after them.

    Dropping one half of a pair is the failure this exists to prevent: a column
    headed "Local value" beside nothing to compare against reads as a value
    AEAT does not hold, rather than a column the terminal had no room for.
    """
    taken: list[tuple[str, str, int]] = []
    used = 0

    def _sized(column: tuple[str, str, int]) -> tuple[str, str, int, int]:
        header = aeat_sync_copy(column[1])
        size = max(column[2], len(header))
        return column[0], header, size, size + 2

    for name, header, size, cost in (_sized(column) for column in standalone):
        if used + cost > width - 1:
            break
        taken.append((name, header, size))
        used += cost

    sized_pair = [_sized(column) for column in pair]
    if sized_pair and used + sum(cost for *_, cost in sized_pair) <= width - 1:
        for name, header, size, _cost in sized_pair:
            taken.append((name, header, size))
    return tuple(taken)


def _census_value(value: str | None) -> str:
    """Render one side of a census comparison, naming an unobserved side."""
    if value is None:
        return aeat_sync_copy("tui.aeat_sync.value.unobserved")
    return _compact(value, 24)


def _census_identity(path: str) -> str:
    """Derive a stable key from the safe canonical census path only."""
    return f"census:{' '.join(path.split()).casefold()}"


def _natural_identity(row: _NaturalRow, *, prefix: str) -> str:
    """Derive a stable key from a public declaration coordinate."""
    return f"{prefix}:{row.modelo}|{row.filing_year}|{row.period.registry_token}"


def _notification_identity(row: AeatSyncWorkspaceNotificationRowV1) -> str:
    """Use the application-projected opaque semantic notification identity."""
    if row.selection_key is None:
        raise ValueError("projected notification row requires a selection key")
    return row.selection_key


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
    CSS = BASE_CSS + tokenised(
        """
        #aeat-sync-page { width: 100%; height: 1fr; overflow-x: hidden; }
        #aeat-sync-navigation, #aeat-sync-rows { width: 100%; }
        #aeat-sync-status {
            width: 100%;
            height: auto;
            padding: $cadrumo-space-0 $cadrumo-space-1;
            color: $warning;
        }
        .aeat-sync-operation { width: 100%; max-width: $cadrumo-control-max-width; }
        """
    )

    zone: AeatSyncWorkspaceZone
    heading: str

    def __init__(self, controller: AeatSyncWorkspaceController, *, id: str) -> None:
        """Retain the controller and initially empty local button catalogue."""
        super().__init__(id=id)
        self.controller = controller
        self._requests: dict[str, AeatSyncOperationRequestV1] = {}
        self._consumed_request_ids: set[str] = set()
        self._consumed_notification_ids: set[str] = set()
        self._in_flight_id: str | None = None
        self._selected_row_key: str | None = None
        self._notification_rows: dict[str, AeatSyncWorkspaceNotificationRowV1] = {}

    @override
    def compose(self) -> ComposeResult:
        yield Static(aeat_sync_copy(self.heading), classes="cadrumo-banner", markup=False)
        with ContentScroll(id="aeat-sync-page", classes="cadrumo-scroll"):
            yield Static(
                aeat_sync_copy("tui.aeat_sync.section.areas"),
                classes="cadrumo-heading",
                markup=False,
            )
            yield ContentDataTable[str](id="aeat-sync-navigation", cursor_type="row", zebra_stripes=True)
            yield Static(
                aeat_sync_copy("tui.aeat_sync.section.detail"),
                classes="cadrumo-heading",
                markup=False,
            )
            yield ContentDataTable[str](id="aeat-sync-rows", cursor_type="row", zebra_stripes=True)
            yield Static(id="aeat-sync-status", markup=False)

    def on_mount(self) -> None:
        """Render all six independent source states and this screen's safe rows."""
        navigation = cast("DataTable[str]", self.query_one("#aeat-sync-navigation", DataTable))
        navigation.add_column(aeat_sync_copy("tui.aeat_sync.column.area"), width=16)
        navigation.add_column(aeat_sync_copy("tui.aeat_sync.column.availability"), width=12)
        navigation.add_column(aeat_sync_copy("tui.aeat_sync.column.sources"), width=38)
        self._render_navigation(navigation)
        rows = cast("DataTable[str]", self.query_one("#aeat-sync-rows", DataTable))
        self.populate_rows(rows)
        self._render_zone_status(rows)
        self._restore_focus(
            navigation,
            rows,
        )

    def _render_zone_status(self, rows: DataTable[str]) -> None:
        """State known-empty and unobservable zones in non-colour text."""
        state = self.controller.state_for(self.zone)
        count = state.item_count
        if count is not None and count != rows.row_count:
            raise ValueError("AEAT Sync zone count and rendered rows disagree")
        status = self.query_one("#aeat-sync-status", Static)
        if str(status.render()).strip():
            return
        rendered_count = str(count) if count is not None else aeat_sync_copy("tui.aeat_sync.value.none")
        status.update(f"{_label(self.zone)} · {_label(state.availability)} · {rendered_count}")

    def _render_navigation(self, navigation: DataTable[str]) -> None:
        """Render every zone with its independent source axes."""
        navigation.clear(columns=False)
        for zone in AeatSyncWorkspaceZone:
            state = self.controller.state_for(zone)
            navigation.add_row(
                _label(zone),
                _label(state.availability),
                aeat_sync_copy(
                    "tui.aeat_sync.sources.joined",
                    entries=", ".join(
                        _compact(
                            aeat_sync_copy(
                                "tui.aeat_sync.sources.entry",
                                source=_label(source.source),
                                availability=_label(source.availability),
                            ),
                            42,
                        )
                        for source in state.sources
                    ),
                ),
                key=zone.value,
            )

    def _restore_focus(self, navigation: DataTable[str], rows: DataTable[str]) -> None:
        """Restore the stable selected row after refresh or child return."""
        focus = self.controller.context.focus
        if focus is not None and focus.semantic_key.startswith(f"aeat_sync.{self.zone.value}") and rows.row_count:
            rows.focus()
            return
        if self._selected_row_key is not None:
            for index, item in enumerate(rows.ordered_rows):
                if str(item.key.value) == self._selected_row_key:
                    rows.move_cursor(row=index)
                    rows.focus()
                    return
        navigation.focus()

    def refresh_projection(self, projection: AeatSyncWorkspaceProjectionV1) -> None:
        """Apply one explicit preloaded snapshot and retain semantic focus."""
        self.controller.replace_projection(projection)
        navigation = cast("DataTable[str]", self.query_one("#aeat-sync-navigation", DataTable))
        rows = cast("DataTable[str]", self.query_one("#aeat-sync-rows", DataTable))
        for button in tuple(self.query(".aeat-sync-operation")):
            button.remove()
        self._requests.clear()
        self._notification_rows.clear()
        navigation.clear(columns=False)
        rows.clear(columns=True)
        self._render_navigation(navigation)
        self.populate_rows(rows)
        self._render_zone_status(rows)
        self._restore_focus(navigation, rows)

    def populate_rows(self, table: DataTable[str]) -> None:
        """Populate one safe public zone body in subclasses."""
        raise NotImplementedError

    def add_operation(self, row: _OperationRow) -> None:
        """Render an explicit mutation button only for a closed admitted pair."""
        request = self.controller.admitted_operation(row.supported_actions, row.supported_operations)
        if request is None:
            if (
                tuple(str(action.action_id) for action in row.supported_actions)
                == ("operator.live.notifications.list",)
                and not row.supported_operations
            ):
                return
            if row.supported_actions or row.supported_operations:
                self.query_one("#aeat-sync-status", Static).update(
                    aeat_sync_copy("tui.aeat_sync.refusal.operation_handoff")
                )
            return
        label_key = _OPERATION_LABEL_KEYS.get((str(request.action.action_id), str(request.operation)))
        if label_key is None:
            self.query_one("#aeat-sync-status", Static).update(
                aeat_sync_copy("tui.aeat_sync.refusal.operation_handoff")
            )
            return
        button_id = f"aeat-sync-operation-{len(self._requests)}"
        self._requests[button_id] = request
        self.query_one("#aeat-sync-page", ContentScroll).mount(
            Button(aeat_sync_copy(label_key), id=button_id, classes="aeat-sync-operation")
        )

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Hand the exact admitted request to the optional owning host door."""
        request_id = event.button.id or ""
        request = self._requests.get(request_id)
        if request is None:
            return
        handoff = self.controller.operation_handoff
        status = self.query_one("#aeat-sync-status", Static)
        if request_id in self._consumed_request_ids:
            status.update(aeat_sync_copy("tui.aeat_sync.operation.already_handled"))
            return
        if self._in_flight_id is not None:
            status.update(aeat_sync_copy("tui.aeat_sync.operation.in_flight"))
            return
        self._consumed_request_ids.add(request_id)
        if handoff is None:
            status.update(aeat_sync_copy("tui.aeat_sync.refusal.operation_handoff"))
            return
        self._in_flight_id = request_id
        self._set_operation_buttons_disabled(True)
        status.update(aeat_sync_copy("tui.aeat_sync.operation.in_flight"))
        try:
            await handoff(request)
        except Exception:  # host boundary must not disclose protected diagnostics
            status.update(aeat_sync_copy("tui.aeat_sync.operation.failed"))
        else:
            status.update(aeat_sync_copy("tui.aeat_sync.operation.handed_off"))
        finally:
            self._in_flight_id = None
            self._set_operation_buttons_disabled(False)
            event.button.disabled = True

    def _set_operation_buttons_disabled(self, disabled: bool) -> None:
        """Make the one-shot operation guard visible during a host handoff."""
        for button in self.query(".aeat-sync-operation"):
            button.disabled = disabled

    async def _select_notification(self, row_key: str) -> None:
        """Open only a row AEAT has explicitly marked read."""
        row = self._notification_rows.get(row_key)
        status = self.query_one("#aeat-sync-status", Static)
        if row is None:
            return
        if row.read_state is not AeatSyncNotificationReadState.READ:
            status.update(aeat_sync_copy("tui.aeat_sync.refusal.unread_notification"))
            return
        if self._in_flight_id is not None:
            status.update(aeat_sync_copy("tui.aeat_sync.operation.in_flight"))
            return
        if row_key in self._consumed_notification_ids:
            status.update(aeat_sync_copy("tui.aeat_sync.notification.already_handled"))
            return
        self._consumed_notification_ids.add(row_key)
        if self.controller.notification_document_handoff is None:
            status.update(aeat_sync_copy("tui.aeat_sync.refusal.notification_handoff"))
            return
        self._in_flight_id = row_key
        status.update(aeat_sync_copy("tui.aeat_sync.operation.in_flight"))
        try:
            opened = await self.controller.retrieve_notification_document(row)
        except Exception:  # host boundary must not disclose protected diagnostics
            status.update(aeat_sync_copy("tui.aeat_sync.operation.failed"))
        else:
            status.update(
                aeat_sync_copy("tui.aeat_sync.notification.document_handed_off")
                if opened
                else aeat_sync_copy("tui.aeat_sync.refusal.notification_handoff")
            )
        finally:
            self._in_flight_id = None

    async def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Request a host-owned internal route only for an observable zone."""
        table = cast("DataTable[str]", event.data_table)
        if table.id == "aeat-sync-rows" and self.zone is AeatSyncWorkspaceZone.NOTIFICATIONS:
            await self._select_notification(str(event.row_key.value))
            return
        if table.id != "aeat-sync-navigation":
            return
        zone = AeatSyncWorkspaceZone(event.row_key.value)
        if not self.controller.can_open(zone):
            self.query_one("#aeat-sync-status", Static).update(aeat_sync_copy("tui.aeat_sync.refusal.source"))
            return
        self.post_message(AeatSyncRouteRequested(self.controller.target(zone)))

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Track semantic identity instead of a mutable row position."""
        table = cast("DataTable[str]", event.data_table)
        if table.id == "aeat-sync-rows":
            self._selected_row_key = str(event.row_key.value)

    def action_back(self) -> None:
        """Dismiss only this child; the installed root owns the return journey."""
        self.dismiss(None)

    def on_aeat_sync_route_requested(self, event: AeatSyncRouteRequested) -> None:
        """Resolve the requested zone here and hand the finished body to the host."""
        # Imported at call time: the route catalogue imports this module for the
        # concrete screens, so a module-scope import would form a cycle.
        from .routes import resolve_aeat_sync_screen

        replace_workspace_body(self.app, resolve_aeat_sync_screen(self.controller, event.target))


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
        table.add_column(aeat_sync_copy("tui.aeat_sync.column.area"), width=15)
        table.add_column(aeat_sync_copy("tui.aeat_sync.column.local"), width=13)
        table.add_column(aeat_sync_copy("tui.aeat_sync.column.aeat"), width=13)
        table.add_column(aeat_sync_copy("tui.aeat_sync.column.difference"), width=16)
        for row in self.controller.projection.overview:
            table.add_row(
                _label(row.area),
                _label(row.local_state),
                _label(row.aeat_state),
                _label(row.discrepancy_kind),
                key=f"overview:{row.area.value}",
            )
            self.add_operation(cast("_OperationRow", row))


class AeatSyncCensusScreen(AeatSyncWorkspaceScreen):
    """Census comparison without taxpayer values."""

    zone = AeatSyncWorkspaceZone.CENSUS
    heading = "tui.aeat_sync.census.title"

    def __init__(self, controller: AeatSyncWorkspaceController) -> None:
        """Build the census body."""
        super().__init__(controller, id="aeat-sync-census-screen")

    _COLUMNS: ClassVar[tuple[tuple[str, str, int], ...]] = (
        ("field", "tui.aeat_sync.column.field", 26),
        ("status", "tui.aeat_sync.column.status", 16),
        ("category", "tui.aeat_sync.column.category", 16),
    )
    """Census columns that stand alone, in priority order.

    Status ranks above the values, and a first ordering that put them below it
    was wrong: the values are the EVIDENCE, the status is the VERDICT, and an
    operator who cannot see whether a field is adopted or in conflict has lost
    the thing that tells them to act. Showing evidence for a verdict they
    cannot read is the worse trade.
    """

    _VALUE_COLUMNS: ClassVar[tuple[tuple[str, str, int], ...]] = (
        ("local_value", "tui.aeat_sync.column.local_value", 22),
        ("aeat_value", "tui.aeat_sync.column.aeat_value", 22),
    )
    """The comparison pair, taken together or not at all.

    Dropping ONE side would leave a column headed "Local value" beside nothing
    to compare it against, which reads as a value AEAT does not hold rather
    than a column the terminal had no room for. Both or neither.
    """

    @override
    def populate_rows(self, table: DataTable[str]) -> None:
        """Render the census comparison, dropping columns before overflowing."""
        taken = _fit_columns(self.app.size.width, self._COLUMNS, self._VALUE_COLUMNS)
        for name, header, size in taken:
            table.add_column(header, key=name, width=size)
        for row in self.controller.projection.census:
            cells = {
                "field": _compact(row.path, 32),
                "category": _label(row.category),
                "status": _label(row.status),
                # An unobserved side is WORDED. A blank cell beside a populated
                # one reads as "AEAT holds nothing", which is a different claim
                # from "nobody has looked" -- and the second is the truth
                # before any pull.
                "local_value": _census_value(row.local_value),
                "aeat_value": _census_value(row.aeat_value),
            }
            table.add_row(
                *(cells[name] for name, _, _ in taken),
                key=_census_identity(row.path),
            )


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
        table.add_column(aeat_sync_copy("tui.aeat_sync.column.declaration"), width=22)
        table.add_column(aeat_sync_copy("tui.aeat_sync.column.local_filing"), width=14)
        table.add_column(aeat_sync_copy("tui.aeat_sync.column.aeat"), width=14)
        table.add_column(aeat_sync_copy("tui.aeat_sync.column.receipt"), width=14)
        for row in self.controller.projection.filed_declarations:
            table.add_row(
                _address(row),
                _label(row.local_filing_state),
                _label(row.aeat_observation_state),
                _label(row.justificante_state),
                key=_natural_identity(row, prefix="filed"),
            )
        for overview in self.controller.projection.overview:
            if overview.area is AeatSyncOverviewArea.FILED_DECLARATIONS:
                self.add_operation(cast("_OperationRow", overview))


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
        table.add_column(aeat_sync_copy("tui.aeat_sync.column.issued"), width=12)
        table.add_column(aeat_sync_copy("tui.aeat_sync.column.read"), width=12)
        table.add_column(aeat_sync_copy("tui.aeat_sync.column.category"), width=16)
        table.add_column(aeat_sync_copy("tui.aeat_sync.column.document_custody"), width=18)
        self._notification_rows.clear()
        for row in self.controller.projection.notifications:
            key = _notification_identity(row)
            self._notification_rows[key] = row
            table.add_row(
                str(row.issued_on),
                _label(row.read_state),
                _label(row.category),
                _label(row.document_custody_state),
                key=key,
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
        taken = _fit_columns(
            self.app.size.width,
            (
                ("declaration", "tui.aeat_sync.column.declaration", 22),
                ("difference", "tui.aeat_sync.column.difference", 16),
                ("local", "tui.aeat_sync.column.local", 13),
                ("aeat", "tui.aeat_sync.column.aeat", 13),
            ),
            (
                ("local_value", "tui.aeat_sync.column.local_value", 18),
                ("aeat_value", "tui.aeat_sync.column.aeat_value", 18),
            ),
        )
        for name, header, size in taken:
            table.add_column(header, key=name, width=size)
        for row in self.controller.projection.evidence_comparison:
            cells = {
                "declaration": _address(row),
                "local": _label(row.local_state),
                "aeat": _label(row.aeat_state),
                "difference": _label(row.discrepancy_kind),
                "local_value": _census_value(row.local_value),
                "aeat_value": _census_value(row.aeat_value),
            }
            table.add_row(
                *(cells[name] for name, _, _ in taken),
                key=_natural_identity(row, prefix="comparison"),
            )
            self.add_operation(cast("_OperationRow", row))


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
        taken = _fit_columns(
            self.app.size.width,
            (
                ("declaration", "tui.aeat_sync.column.declaration", 20),
                ("resolution", "tui.aeat_sync.column.resolution", 14),
                ("difference", "tui.aeat_sync.column.difference", 14),
                ("local", "tui.aeat_sync.column.local", 10),
                ("aeat", "tui.aeat_sync.column.aeat", 10),
            ),
            (
                ("local_value", "tui.aeat_sync.column.local_value", 16),
                ("aeat_value", "tui.aeat_sync.column.aeat_value", 16),
            ),
        )
        for name, header, size in taken:
            table.add_column(header, key=name, width=size)
        for row in self.controller.projection.reconciliation:
            cells = {
                "declaration": _address(row),
                "local": _label(row.local_state),
                "aeat": _label(row.aeat_state),
                "difference": _label(row.discrepancy_kind),
                # The resolution outranks the raw states here: it is what the
                # operator is being asked to accept or change.
                "resolution": _label(row.reconciliation_state),
                "local_value": _census_value(row.local_value),
                "aeat_value": _census_value(row.aeat_value),
            }
            table.add_row(
                *(cells[name] for name, _, _ in taken),
                key=_natural_identity(row, prefix="reconciliation"),
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
