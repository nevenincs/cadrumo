"""Pure controller and common shell for the Declarations workspace."""

from __future__ import annotations

import unicodedata
from datetime import date, datetime
from typing import ClassVar, Final, cast

from textual.binding import Binding
from textual.message import Message
from textual.screen import Screen
from textual.widgets import DataTable, Static

from ....application.modelo.declarations_calendar import (
    DECLARATIONS_CALENDAR_CONTRACT_VERSION,
    DeclarationsCalendarEntryRefV1,
    DeclarationsCalendarProjectionV1,
    DeclarationsCalendarSource,
    DeclarationsCalendarSourceStateV1,
)
from ....application.modelo.declarations_workspace import (
    DECLARATIONS_WORKSPACE_CONTRACT_VERSION,
    DeclarationsWorkspaceAvailability,
    DeclarationsWorkspaceProjectionV1,
    DeclarationsWorkspaceZone,
    DeclarationsWorkspaceZoneStateV1,
)
from ....application.operator_actions.catalogue import lookup_action
from ....application.operator_actions.models import ActionReference
from ....application.overview.calendar_models import (
    OverviewAeatSubmissionState,
    OverviewLocalFilingState,
    OverviewPeriodState,
)
from ....application.overview.home import HomeAvailability
from ....core.i18n.render import tr
from ....domain.deadlines.models import ObligationStatus
from ....domain.modelos.calculation_revision import CalculationRevisionState
from ....domain.modelos.filing_record import ExternalEvidenceKind, ModeloRecordStatus
from ....domain.modelos.work_unit import WorkUnitState
from ..components.theme import BASE_CSS, tokenised
from ..components.workspace_host import replace_workspace_body
from ..navigation import TuiScreenContextV1
from .models import (
    CalendarEntryHandoffV1,
    CalendarRecoveryHandoffV1,
    DeclarationsCalendarScopeV1,
    DeclarationsDestinationIdV1,
    DeclarationsRouteTargetV1,
    FilingHandoffV1,
    ModeloWorkspaceScreenFactoryV1,
    RevisionHandoffV1,
)

_ZONE_BY_DESTINATION: Final = {
    "declarations.overview": DeclarationsWorkspaceZone.DECLARATIONS,
    "declarations.revisions": DeclarationsWorkspaceZone.CALCULATION_REVISIONS,
    "declarations.filing_history": DeclarationsWorkspaceZone.FILING_HISTORY,
    "declarations.calendar": None,
    "declarations.modelo_workspace": DeclarationsWorkspaceZone.DECLARATIONS,
}
_DESTINATION_KEYS: Final = {
    "declarations.overview": "tui.declarations.destination.overview",
    "declarations.revisions": "tui.declarations.destination.revisions",
    "declarations.filing_history": "tui.declarations.destination.filing_history",
    "declarations.calendar": "tui.declarations.destination.calendar",
    "declarations.modelo_workspace": "tui.declarations.destination.modelo_workspace",
}
_AVAILABILITY_KEYS: Final = {
    DeclarationsWorkspaceAvailability.AVAILABLE: "tui.declarations.availability.available",
    DeclarationsWorkspaceAvailability.LOCKED: "tui.declarations.availability.locked",
    DeclarationsWorkspaceAvailability.STALE: "tui.declarations.availability.stale",
    DeclarationsWorkspaceAvailability.NEVER_CAPTURED: "tui.declarations.availability.never_captured",
    DeclarationsWorkspaceAvailability.UNAVAILABLE: "tui.declarations.availability.unavailable",
}
_WORK_STATE_KEYS: Final = {state: f"tui.declarations.work_state.{state.value}" for state in WorkUnitState}
_REVISION_STATE_KEYS: Final = {
    state: f"tui.declarations.revision_state.{state.value}" for state in CalculationRevisionState
}
_FILING_STATE_KEYS: Final = {
    ModeloRecordStatus.VIGENTE: "tui.declarations.filing_state.vigente",
    ModeloRecordStatus.SUPERSEDIDO: "tui.declarations.filing_state.supersedido",
}
_EVIDENCE_KEYS: Final = {
    ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF: "tui.declarations.evidence.aeat_justificante_pdf",
    ExternalEvidenceKind.AEAT_LIVE_CAPTURE: "tui.declarations.evidence.aeat_live_capture",
}


def declarations_copy(key: str, **values: object) -> str:
    """Resolve authored display copy through the canonical catalogue."""
    return tr(key, **values)


def natural_address(modelo: object, year: object, period: object) -> str:
    """Render the public Modelo/year/period coordinate."""
    token = getattr(period, "registry_token", str(period))
    return f"Modelo {modelo} · {year} · {token}"


def timestamp_label(value: datetime) -> str:
    """Render a deterministic minute-bearing UTC timestamp without locale ambiguity."""
    return value.strftime("%d/%m/%Y %H:%M UTC")


def calendar_date_label(value: date | None) -> str:
    """Render one non-ambiguous legal date."""
    return declarations_copy("tui.declarations.calendar.none") if value is None else value.strftime("%d/%m/%Y")


def availability_label(value: DeclarationsWorkspaceAvailability) -> str:
    """Render one explicit source availability."""
    return declarations_copy(_AVAILABILITY_KEYS[value])


def work_state_label(value: WorkUnitState) -> str:
    """Render a local declaration state."""
    return declarations_copy(_WORK_STATE_KEYS[value])


def revision_state_label(value: CalculationRevisionState) -> str:
    """Render a calculation-revision state."""
    return declarations_copy(_REVISION_STATE_KEYS[value])


def filing_state_label(value: ModeloRecordStatus) -> str:
    """Render local filing-record currency."""
    return declarations_copy(_FILING_STATE_KEYS[value])


def evidence_label(value: ExternalEvidenceKind | None) -> str:
    """Render separately observed AEAT evidence metadata."""
    return (
        declarations_copy("tui.declarations.evidence.none")
        if value is None
        else declarations_copy(_EVIDENCE_KEYS[value])
    )


class DeclarationsWorkspaceController:
    """Custody of an injected safe projection and admitted read references."""

    def __init__(
        self,
        context: TuiScreenContextV1,
        projection: DeclarationsWorkspaceProjectionV1,
        *,
        work_action: ActionReference,
        revisions_action: ActionReference,
        filing_action: ActionReference,
        modelo_workspace_factory: ModeloWorkspaceScreenFactoryV1 | None = None,
        revision_handoff: RevisionHandoffV1 | None = None,
        filing_handoff: FilingHandoffV1 | None = None,
        calendar_projection: DeclarationsCalendarProjectionV1 | None = None,
        calendar_entry_handoff: CalendarEntryHandoffV1 | None = None,
        calendar_recovery_handoff: CalendarRecoveryHandoffV1 | None = None,
    ) -> None:
        """Validate the context, projection version, and declared read actions."""
        if context.destination != "workbench.declarations":
            raise ValueError("Declarations workspace requires the workbench.declarations context")
        if projection.contract_version != DECLARATIONS_WORKSPACE_CONTRACT_VERSION:
            raise ValueError("unsupported Declarations workspace projection contract")
        expected = (
            (work_action, "modelo.work.list"),
            (revisions_action, "modelo.work.revisions"),
            (filing_action, "modelo.filing_record.list"),
        )
        for action, command in expected:
            if lookup_action(action.action_id).target_command_key != command:
                raise ValueError("injected Declarations read action resolves to another application door")
        self.context = context
        self.projection = projection
        self.work_action = work_action
        self.revisions_action = revisions_action
        self.filing_action = filing_action
        self.modelo_workspace_factory = modelo_workspace_factory
        self.revision_handoff = revision_handoff
        self.filing_handoff = filing_handoff
        if (
            calendar_projection is not None
            and calendar_projection.contract_version != DECLARATIONS_CALENDAR_CONTRACT_VERSION
        ):
            raise ValueError("unsupported Declarations calendar projection contract")
        self.calendar_projection = calendar_projection
        self.calendar_entry_handoff = calendar_entry_handoff
        self.calendar_recovery_handoff = calendar_recovery_handoff

    def zone_state(self, zone: DeclarationsWorkspaceZone) -> DeclarationsWorkspaceZoneStateV1:
        """Return one closed zone state."""
        return next(item for item in self.projection.zones if item.zone is zone)

    def target(self, destination: DeclarationsDestinationIdV1) -> DeclarationsRouteTargetV1:
        """Construct a typed target from the closed route map."""
        return DeclarationsRouteTargetV1(destination=destination, zone=_ZONE_BY_DESTINATION[destination])

    def destination_availability(
        self, destination: DeclarationsDestinationIdV1
    ) -> DeclarationsWorkspaceAvailability | HomeAvailability:
        """Return truthful availability for one route authority."""
        zone = _ZONE_BY_DESTINATION[destination]
        if zone is not None:
            return self.zone_state(zone).availability
        if self.calendar_projection is None:
            return HomeAvailability.UNAVAILABLE
        return next(
            item.availability
            for item in self.calendar_projection.sources
            if item.source is DeclarationsCalendarSource.SCHEDULE
        )

    def restored_id(self, semantic_key: str) -> str | None:
        """Return the matching opaque semantic restore token, if any."""
        focus = self.context.focus
        return focus.restore_token if focus is not None and focus.semantic_key == semantic_key else None


class DeclarationsWorkspaceScreen(Screen[None]):
    """One-scroll host-neutral shell with semantic internal navigation."""

    BINDINGS: ClassVar = [Binding("escape", "back", "", show=False)]
    CSS = BASE_CSS + tokenised(
        """
        .declarations-page { width: 100%; height: 1fr; }
        .declarations-refusal { color: $warning; text-style: bold; height: auto; }
        """
    )

    def __init__(self, controller: DeclarationsWorkspaceController, *, id: str) -> None:
        """Retain the injected controller."""
        super().__init__(id=id)
        self.controller = controller
        self.requested_target: DeclarationsRouteTargetV1 | None = None

    def populate_navigation(self) -> None:
        """Populate every closed internal destination exactly once."""
        table = cast("DataTable[str]", self.query_one("#declarations-navigation", DataTable))
        table.add_column(declarations_copy("tui.declarations.column.destination"), key="destination")
        table.add_column(declarations_copy("tui.declarations.column.availability"), key="availability")
        for raw_destination in _DESTINATION_KEYS:
            destination = cast("DeclarationsDestinationIdV1", raw_destination)
            availability = self.controller.destination_availability(destination)
            table.add_row(
                declarations_copy(_DESTINATION_KEYS[destination]),
                declarations_copy(f"tui.declarations.availability.{availability.value}"),
                key=destination,
            )

    def handle_navigation(self, event: DataTable.RowSelected) -> bool:
        """Handle a navigation selection without reading application state."""
        table = cast("DataTable[str]", event.data_table)
        if table.id != "declarations-navigation":
            return False
        destination = cast("DeclarationsDestinationIdV1", event.row_key.value)
        availability = self.controller.destination_availability(destination)
        notice = self.query_one("#declarations-refusal", Static)
        if availability.value not in {
            DeclarationsWorkspaceAvailability.AVAILABLE.value,
            DeclarationsWorkspaceAvailability.STALE.value,
        }:
            notice.update(declarations_copy("tui.declarations.refusal.source"))
            return True
        self.requested_target = self.controller.target(destination)
        notice.update("")
        self.post_message(DeclarationsRouteRequested(self.requested_target))
        return True

    def refuse_handoff(self) -> None:
        """Show an explicit refusal when the host omitted a target."""
        self.query_one("#declarations-refusal", Static).update(declarations_copy("tui.declarations.refusal.handoff"))

    def action_back(self) -> None:
        """Dismiss only this child screen."""
        self.dismiss(None)

    def on_declarations_route_requested(self, event: DeclarationsRouteRequested) -> None:
        """Resolve the requested internal body here and hand it to the host."""
        # Imported at call time: the route catalogue imports this module for the
        # shared shell, so a module-scope import would form a cycle.
        from .routes import resolve_declarations_screen

        replace_workspace_body(self.app, resolve_declarations_screen(self.controller, event.target))


class DeclarationsRouteRequested(Message):
    """Request that the owning host replace the current internal body."""

    def __init__(self, target: DeclarationsRouteTargetV1) -> None:
        """Retain the typed internal target."""
        super().__init__()
        self.target = target


class DeclarationsCalendarController:
    """Pure custody and filtering for one injected safe calendar projection."""

    def __init__(
        self,
        context: TuiScreenContextV1,
        projection: DeclarationsCalendarProjectionV1,
        *,
        entry_handoff: CalendarEntryHandoffV1 | None = None,
        recovery_handoff: CalendarRecoveryHandoffV1 | None = None,
    ) -> None:
        """Validate and retain only the injected safe calendar facts and callbacks."""
        if context.destination != "workbench.declarations":
            raise ValueError("Declarations calendar requires the workbench.declarations context")
        if projection.contract_version != DECLARATIONS_CALENDAR_CONTRACT_VERSION:
            raise ValueError("unsupported Declarations calendar projection contract")
        self.context = context
        self.projection = projection
        self.entry_handoff = entry_handoff
        self.recovery_handoff = recovery_handoff
        _validate_calendar_recovery_actions(projection)

    def source(self, source: DeclarationsCalendarSource) -> DeclarationsCalendarSourceStateV1:
        """Return one explicit source state."""
        return next(item for item in self.projection.sources if item.source is source)

    def replace_projection(self, projection: DeclarationsCalendarProjectionV1) -> None:
        """Accept a fresh injected snapshot without performing a read."""
        if projection.contract_version != DECLARATIONS_CALENDAR_CONTRACT_VERSION:
            raise ValueError("unsupported Declarations calendar projection contract")
        _validate_calendar_recovery_actions(projection)
        self.projection = projection

    def visible_entries(
        self, scope: DeclarationsCalendarScopeV1, query: str
    ) -> tuple[DeclarationsCalendarEntryRefV1, ...]:
        """Apply closed scope semantics and Unicode AND search to safe fields only."""
        aeat_observable = self.source(DeclarationsCalendarSource.AEAT_EVIDENCE).availability in {
            HomeAvailability.AVAILABLE,
            HomeAvailability.STALE,
        }
        rows = [
            row for row in self.projection.entries if _scope_matches(row, scope, self.projection.as_of, aeat_observable)
        ]
        terms = tuple(part for part in _fold(query).split() if part)
        if terms:
            rows = [row for row in rows if all(term in _calendar_search_text(row) for term in terms)]
        return tuple(sorted(rows, key=lambda row: (row.adjusted_closes_on, *row.semantic_key())))

    def context_identity(self) -> str | None:
        """Resolve a safe natural row identity carried by the route focus key."""
        focus = self.context.focus
        if focus is None or not focus.semantic_key.startswith("declarations.calendar"):
            return None
        return next(
            (
                _calendar_identity(row)
                for row in self.projection.entries
                if calendar_focus_key(row) == focus.semantic_key
            ),
            None,
        )


def _calendar_identity(row: DeclarationsCalendarEntryRefV1) -> str:
    modelo, year, period = row.semantic_key()
    return f"{modelo}|{year}|{period}"


def _validate_calendar_recovery_actions(projection: DeclarationsCalendarProjectionV1) -> None:
    for row in projection.entries:
        action = row.recovery_action
        if action is None:
            continue
        if (
            action.action.action_id != "operator.modelo.work.create"
            or lookup_action(action.action.action_id).target_command_key != "modelo.work.create"
        ):
            raise ValueError("calendar recovery action is not the canonical create action")
        bindings = {item.argument_name: item.value for item in action.argument_bindings}
        if bindings != {
            "modelo": str(row.modelo),
            "year": row.filing_year,
            "period": row.period.registry_token,
        }:
            raise ValueError("calendar recovery action contradicts its natural address")


def calendar_focus_key(row: DeclarationsCalendarEntryRefV1) -> str:
    """Return a NamespacedId-compatible public natural calendar focus key."""
    modelo, year, period = row.semantic_key()
    return f"declarations.calendar.m{modelo}.y{year}.p{period.casefold()}"


def _fold(value: str) -> str:
    return "".join(
        character
        for character in unicodedata.normalize("NFKD", value).casefold()
        if not unicodedata.combining(character)
    )


def _calendar_search_text(row: DeclarationsCalendarEntryRefV1) -> str:
    values = (
        natural_address(row.modelo, row.filing_year, row.period),
        str(row.modelo),
        str(row.filing_year),
        row.period.registry_token,
        calendar_legal_label(row.legal_status),
        calendar_user_label(row.user_state),
        calendar_local_label(row.local_filing_state),
        calendar_aeat_label(row.aeat_submission_state),
        calendar_date_label(row.opens_on),
        calendar_date_label(row.adjusted_closes_on),
        calendar_date_label(row.payment_cutoff_on),
    )
    return _fold(" ".join(values))


def _scope_matches(
    row: DeclarationsCalendarEntryRefV1,
    scope: DeclarationsCalendarScopeV1,
    as_of: date,
    aeat_observable: bool,
) -> bool:
    if scope is DeclarationsCalendarScopeV1.ALL:
        return True
    if scope is DeclarationsCalendarScopeV1.PAST:
        return row.adjusted_closes_on < as_of
    if scope is DeclarationsCalendarScopeV1.UPCOMING:
        return row.adjusted_closes_on >= as_of and row.user_state is OverviewPeriodState.DUE
    if scope is DeclarationsCalendarScopeV1.OVERDUE:
        return row.adjusted_closes_on < as_of and row.user_state is OverviewPeriodState.LATE
    if scope is DeclarationsCalendarScopeV1.FILED:
        return row.user_state is OverviewPeriodState.FILED
    return not aeat_observable


def calendar_legal_label(value: ObligationStatus) -> str:
    """Render legal deadline status."""
    return declarations_copy(f"tui.declarations.calendar.legal.{value.value.lower()}")


def calendar_user_label(value: OverviewPeriodState) -> str:
    """Render the safe derived user-facing schedule state."""
    return declarations_copy(f"tui.declarations.calendar.user.{value.value}")


def calendar_local_label(value: OverviewLocalFilingState | None) -> str:
    """Render local filing state without implying AEAT acceptance."""
    key = "unknown" if value is None else value.value
    return declarations_copy(f"tui.declarations.calendar.local.{key}")


def calendar_aeat_label(value: OverviewAeatSubmissionState | None) -> str:
    """Render observed AEAT evidence state without inference."""
    key = "unknown" if value is None else value.value
    return declarations_copy(f"tui.declarations.calendar.aeat.{key}")


__all__ = [
    "DeclarationsCalendarController",
    "DeclarationsRouteRequested",
    "DeclarationsWorkspaceController",
    "DeclarationsWorkspaceScreen",
    "availability_label",
    "calendar_aeat_label",
    "calendar_date_label",
    "calendar_focus_key",
    "calendar_legal_label",
    "calendar_local_label",
    "calendar_user_label",
    "declarations_copy",
    "evidence_label",
    "filing_state_label",
    "natural_address",
    "revision_state_label",
    "timestamp_label",
    "work_state_label",
]
