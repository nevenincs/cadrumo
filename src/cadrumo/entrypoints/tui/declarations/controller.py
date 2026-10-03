"""Pure controller and common shell for the Declarations workspace."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
from typing import ClassVar, Final, cast

from textual.binding import Binding
from textual.message import Message
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
from ....application.overview.calendar_models import (
    OverviewAeatSubmissionState,
    OverviewLocalFilingState,
    OverviewPeriodState,
)
from ....application.overview.home import HomeAvailability
from ....core.errors.error_codes import resolve_error_message
from ....core.errors.hierarchy import CadrumoError
from ....core.i18n.render import lookup_translation, output_language, tr
from ....core.period import Period
from ....core.text_fold import fold_for_matching
from ....domain.deadlines.models import ObligationStatus
from ....domain.modelos.calculation_revision import CalculationRevisionState
from ....domain.modelos.filing_record import ExternalEvidenceKind, ModeloRecordStatus
from ..action_target import require_action_target
from ..components.account_chrome import AccountChromeScreen
from ..components.theme import BASE_CSS, tokenised
from ..components.workspace_host import replace_workspace_body
from ..navigation import TuiScreenContextV1
from .action_guards import require_canonical_declarations_actions
from .models import (
    CalendarEntryHandoffV1,
    CalendarRecoveryHandoffV1,
    DeclarationsCalendarScopeV1,
    DeclarationsDestinationIdV1,
    DeclarationsRouteTargetV1,
    DeclarationsWorkspaceWiringV1,
)

_ZONE_BY_DESTINATION: Final = {
    "declarations.overview": DeclarationsWorkspaceZone.DECLARATIONS,
    "declarations.revisions": DeclarationsWorkspaceZone.CALCULATION_REVISIONS,
    "declarations.filing_history": DeclarationsWorkspaceZone.FILING_HISTORY,
    "declarations.calendar": None,
    "declarations.modelo_workspace": DeclarationsWorkspaceZone.DECLARATIONS,
}
_DESTINATION_LOCALE_KEYS: Final = {
    "declarations.overview": "tui.declarations.destination.overview",
    "declarations.revisions": "tui.declarations.destination.revisions",
    "declarations.filing_history": "tui.declarations.destination.filing_history",
    "declarations.calendar": "tui.declarations.destination.calendar",
    "declarations.modelo_workspace": "tui.declarations.destination.modelo_workspace",
}
_REVISION_STATE_KEYS: Final = {
    state: f"tui.declarations.revision_state.{state.value}" for state in CalculationRevisionState
}
_FILING_STATE_LOCALE_KEYS: Final = {
    ModeloRecordStatus.VIGENTE: "tui.declarations.filing_state.vigente",
    ModeloRecordStatus.SUPERSEDIDO: "tui.declarations.filing_state.supersedido",
}
_EVIDENCE_LOCALE_KEYS: Final = {
    ExternalEvidenceKind.AEAT_CSV_REGISTER: "tui.declarations.evidence.aeat_csv_register",
    ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF: "tui.declarations.evidence.aeat_justificante_pdf",
    ExternalEvidenceKind.AEAT_LIVE_CAPTURE: "tui.declarations.evidence.aeat_live_capture",
}


_WORK_CREATE_REFUSAL_LOCALE_KEYS: Final = {
    # The application's wording names the CLI command; here the same fix is a key away.
    "application.modelo.errors.profile_readiness_setup_incomplete": (
        "tui.declarations.calendar.recovery.setup_incomplete"
    ),
}


def work_create_refusal_message(refusal: CadrumoError) -> str:
    """Render a work-creation refusal as its own reason, worded for the TUI where the fix differs."""
    tui_key = _WORK_CREATE_REFUSAL_LOCALE_KEYS.get(refusal.translated_message or "")
    return tr(tui_key) if tui_key is not None else resolve_error_message(refusal)


def natural_address(modelo: object, year: object, period: object) -> str:
    """Render the public Modelo/year/period coordinate."""
    from ..modelo.workbench.wording import period_words

    words = period_words(period) if isinstance(period, Period) else f"{year} · {period}"
    return f"Modelo {modelo} · {words}"


def timestamp_label(value: datetime) -> str:
    """Render a deterministic minute-bearing UTC timestamp without locale ambiguity."""
    return value.strftime("%d/%m/%Y %H:%M UTC")


def calendar_date_label(value: date | None) -> str:
    """Render one non-ambiguous legal date."""
    return tr("tui.declarations.calendar.none") if value is None else value.strftime("%d/%m/%Y")


def revision_state_label(value: CalculationRevisionState) -> str:
    """Render a calculation-revision state."""
    return tr(_REVISION_STATE_KEYS[value])


def filing_state_label(value: ModeloRecordStatus) -> str:
    """Render local filing-record currency."""
    return tr(_FILING_STATE_LOCALE_KEYS[value])


def evidence_label(value: ExternalEvidenceKind | None) -> str:
    """Render separately observed AEAT evidence metadata."""
    return tr("tui.declarations.evidence.none") if value is None else tr(_EVIDENCE_LOCALE_KEYS[value])


class DeclarationsWorkspaceController:
    """Custody of an injected safe projection and admitted read references."""

    def __init__(
        self,
        context: TuiScreenContextV1,
        projection: DeclarationsWorkspaceProjectionV1,
        wiring: DeclarationsWorkspaceWiringV1,
    ) -> None:
        """Validate the context, projection version, and declared read actions."""
        if context.destination != "workbench.declarations":
            raise ValueError("Declarations workspace requires the workbench.declarations context")
        if projection.contract_version != DECLARATIONS_WORKSPACE_CONTRACT_VERSION:
            raise ValueError("unsupported Declarations workspace projection contract")
        require_canonical_declarations_actions(
            work_action=wiring.work_action,
            revisions_action=wiring.revisions_action,
            filing_action=wiring.filing_action,
        )
        self.context = context
        self.projection = projection
        self.work_action = wiring.work_action
        self.revisions_action = wiring.revisions_action
        self.filing_action = wiring.filing_action
        self.modelo_workspace_factory = wiring.modelo_workspace_factory
        self.revision_handoff = wiring.revision_handoff
        self.filing_handoff = wiring.filing_handoff
        if (
            wiring.calendar_projection is not None
            and wiring.calendar_projection.contract_version != DECLARATIONS_CALENDAR_CONTRACT_VERSION
        ):
            raise ValueError("unsupported Declarations calendar projection contract")
        self.calendar_projection = wiring.calendar_projection
        self.calendar_entry_handoff = wiring.calendar_entry_handoff
        self.calendar_entry_can_open = wiring.calendar_entry_can_open
        self.calendar_recovery_handoff = wiring.calendar_recovery_handoff
        self.work_create_handoff = wiring.work_create_handoff
        self.creation_targets = wiring.creation_targets
        self.refresh_data = wiring.refresh_data

    def refresh_from_capture(self) -> bool:
        """Replace safe facts only when the refreshed data still names this profile bucket."""
        if self.refresh_data is None:
            return False
        projection, calendar_projection = self.refresh_data()
        if (
            projection.contract_version != DECLARATIONS_WORKSPACE_CONTRACT_VERSION
            or projection.bucket_id != self.projection.bucket_id
            or (
                calendar_projection is not None
                and calendar_projection.contract_version != DECLARATIONS_CALENDAR_CONTRACT_VERSION
            )
        ):
            raise ValueError("Declarations refresh data changed its profile bucket")
        self.projection = projection
        self.calendar_projection = calendar_projection
        return True

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

    def destination_reason_code(self, destination: DeclarationsDestinationIdV1) -> str | None:
        """Return why one destination is not available, as the application said it."""
        zone = _ZONE_BY_DESTINATION[destination]
        if zone is not None:
            return self.zone_state(zone).reason_code
        if self.calendar_projection is None:
            return None
        return next(
            item.reason_code
            for item in self.calendar_projection.sources
            if item.source is DeclarationsCalendarSource.SCHEDULE
        )

    def restored_id(self, semantic_key: str) -> str | None:
        """Return the matching opaque semantic restore token, if any."""
        focus = self.context.focus
        return focus.restore_token if focus is not None and focus.semantic_key == semantic_key else None


class DeclarationsWorkspaceScreen(AccountChromeScreen):
    """One-scroll host-neutral shell with semantic internal navigation."""

    BINDINGS: ClassVar = [Binding("escape", "back", "", show=False)]
    IS_WORKSPACE_OVERVIEW: ClassVar[bool] = False
    """Whether Back from this body leaves the workspace rather than returning to its overview."""
    CSS = BASE_CSS + tokenised(
        """
        .declarations-page { width: 100%; height: 1fr; }
        .declarations-refusal { color: $warning; text-style: bold; height: auto; }
        .declarations-empty { color: $text-muted; height: auto; }
        /* The heading above a form insets its text by the cell padding, so
           the form's labels and fields take the same inset: one left edge. */
        .declarations-work-form { height: auto; padding-left: $cadrumo-cell-padding; }
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
        table.add_column(tr("tui.declarations.column.destination"), key="destination")
        table.add_column(tr("tui.declarations.column.availability"), key="availability")
        for raw_destination in _DESTINATION_LOCALE_KEYS:
            destination = cast("DeclarationsDestinationIdV1", raw_destination)
            availability = self.controller.destination_availability(destination)
            table.add_row(
                tr(_DESTINATION_LOCALE_KEYS[destination]),
                tr(f"tui.declarations.availability.{availability.value}"),
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
            notice.update(self._refusal_copy(destination))
            return True
        self.requested_target = self.controller.target(destination)
        notice.update("")
        self.post_message(DeclarationsRouteRequested(self.requested_target))
        return True

    def _refusal_copy(self, destination: DeclarationsDestinationIdV1) -> str:
        """Say why a destination cannot open, from the application's own reason.

        The generic line only says the source is unavailable; the reason often
        names something the operator can fix, such as incomplete profile
        details. A reason without authored words falls back to the generic
        line rather than to an invented phrase.
        """
        reason = self.controller.destination_reason_code(destination)
        if reason is not None:
            key = f"tui.declarations.refusal.reason.{reason}"
            if lookup_translation(key, locale=output_language()) is not None:
                return tr(key)
        return tr("tui.declarations.refusal.source")

    def show_empty(self) -> None:
        """Say that a table has nothing in it, on the muted line, not the warning one."""
        self.query_one("#declarations-empty", Static).update(tr("tui.declarations.empty"))

    def refuse_handoff(self) -> None:
        """Show an explicit refusal when the host omitted a target."""
        self.query_one("#declarations-refusal", Static).update(tr("tui.declarations.refusal.handoff"))

    def action_back(self) -> None:
        """Return an area to the Declarations overview; leave the workspace only from the overview."""
        # An overview that cannot open would bounce Back straight back here.
        overview_opens = self.controller.destination_availability("declarations.overview") in {
            DeclarationsWorkspaceAvailability.AVAILABLE,
            DeclarationsWorkspaceAvailability.STALE,
        }
        if self.IS_WORKSPACE_OVERVIEW or not overview_opens:
            self.dismiss(None)
            return
        self.post_message(DeclarationsRouteRequested(self.controller.target("declarations.overview")))

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
        entry_can_open: Callable[[DeclarationsCalendarEntryRefV1], bool] | None = None,
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
        self.entry_can_open = entry_can_open
        self.recovery_handoff = recovery_handoff
        _validate_calendar_recovery_actions(projection)

    def source(self, source: DeclarationsCalendarSource) -> DeclarationsCalendarSourceStateV1:
        """Return one explicit source state."""
        return next(item for item in self.projection.sources if item.source is source)

    def can_open(self, row: DeclarationsCalendarEntryRefV1) -> bool:
        """Require an installed action admitted for the exact selected natural address."""
        return self.entry_handoff is not None and (self.entry_can_open is None or self.entry_can_open(row))

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
        terms = tuple(part for part in fold_for_matching(query).split() if part)
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


_RECOVERY_ACTION_REFUSAL: Final[str] = "calendar recovery action is not the canonical create action"


def _validate_calendar_recovery_actions(projection: DeclarationsCalendarProjectionV1) -> None:
    for row in projection.entries:
        action = row.recovery_action
        if action is None:
            continue
        if action.action.action_id != "operator.modelo.work.create":
            raise ValueError(_RECOVERY_ACTION_REFUSAL)
        require_action_target(action.action, "modelo.work.create", _RECOVERY_ACTION_REFUSAL)
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
    return calendar_address_focus_key(modelo, year, period)


def calendar_address_focus_key(modelo: object, year: object, period: str) -> str:
    """Return the calendar focus key for a Modelo, filing year and period.

    Separate from :func:`calendar_focus_key` so a caller holding only the
    natural address -- a Home agenda row -- lands on the same calendar row.
    """
    return f"declarations.calendar.m{modelo}.y{year}.p{period.casefold()}"


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
        calendar_date_label(row.closes_on),
        calendar_date_label(row.adjusted_closes_on),
        calendar_date_label(row.payment_cutoff_on),
        calendar_date_label(row.evaluated_on),
        str(row.days_overdue) if row.days_overdue is not None else "",
        row.shift_reason,
    )
    return fold_for_matching(" ".join(values))


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
    return tr(f"tui.declarations.calendar.legal.{value.value.lower()}")


def calendar_user_label(value: OverviewPeriodState) -> str:
    """Render the safe derived user-facing schedule state."""
    return tr(f"tui.declarations.calendar.user.{value.value}")


def calendar_local_label(value: OverviewLocalFilingState | None) -> str:
    """Render local filing state without implying AEAT acceptance."""
    key = "unknown" if value is None else value.value
    return tr(f"tui.declarations.calendar.local.{key}")


def calendar_aeat_label(value: OverviewAeatSubmissionState | None) -> str:
    """Render observed AEAT evidence state without inference."""
    key = "unknown" if value is None else value.value
    return tr(f"tui.declarations.calendar.aeat.{key}")


__all__ = [
    "DeclarationsCalendarController",
    "DeclarationsRouteRequested",
    "DeclarationsWorkspaceController",
    "DeclarationsWorkspaceScreen",
    "calendar_address_focus_key",
    "calendar_aeat_label",
    "calendar_date_label",
    "calendar_focus_key",
    "calendar_legal_label",
    "calendar_local_label",
    "calendar_user_label",
    "evidence_label",
    "filing_state_label",
    "natural_address",
    "revision_state_label",
    "timestamp_label",
    "work_create_refusal_message",
]
