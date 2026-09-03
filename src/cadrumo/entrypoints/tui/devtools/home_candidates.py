"""Pure Textual candidates over an injected immutable Home projection.

The candidates deliberately stop at selection.  They neither read state nor
invoke an application action; later prototype measurement can therefore
compare layout and keyboard cost without acquiring business authority.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import ClassVar, Final, Literal, cast, override

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import DataTable, Static

from ....application.overview.calendar_models import (
    OverviewAeatSubmissionState,
    OverviewLocalFilingState,
    OverviewPeriodState,
)
from ....application.overview.home import (
    HomeAgendaEntry,
    HomeAvailability,
    HomeDeclarationResume,
    HomeDeclarationState,
    HomeNextAction,
    HomeProjectionV1,
    HomeSessionPosture,
    HomeZoneState,
)
from ..components.widgets import ContentDataTable, ContentScroll

type CandidateTargetKind = Literal["action", "declaration", "agenda"]


@dataclass(frozen=True, slots=True)
class HomeCandidateTarget:
    """One semantic prototype selection, independent of row position."""

    kind: CandidateTargetKind
    identity: str


_AVAILABILITY_COPY: Final[dict[HomeAvailability, str]] = {
    HomeAvailability.AVAILABLE: "Available",
    HomeAvailability.LOCKED: "Locked — unlock the selected profile to view this information",
    HomeAvailability.STALE: "Stale — the last local snapshot needs refresh",
    HomeAvailability.NEVER_CAPTURED: "Not captured yet",
    HomeAvailability.UNAVAILABLE: "Unavailable — this source cannot be read in the current session",
}
_SESSION_COPY: Final[dict[HomeSessionPosture, str]] = {
    HomeSessionPosture.NO_PROFILE: "No profile selected",
    HomeSessionPosture.LOCKED: "Profile locked",
    HomeSessionPosture.ACTIVE: "Active local session",
    HomeSessionPosture.EXPIRED: "Session expired",
}
_DECLARATION_COPY: Final[dict[HomeDeclarationState, str]] = {
    HomeDeclarationState.DRAFT: "Draft",
    HomeDeclarationState.NEEDS_REVIEW: "Needs review",
    HomeDeclarationState.READY: "Ready",
    HomeDeclarationState.FILED: "Filed",
    HomeDeclarationState.DISCARDED: "Discarded",
}
_PERIOD_COPY: Final[dict[OverviewPeriodState, str]] = {
    OverviewPeriodState.DUE: "Due",
    OverviewPeriodState.LATE: "Overdue",
    OverviewPeriodState.FILED: "Filed",
    OverviewPeriodState.UNKNOWN: "Schedule unknown",
}
_LOCAL_COPY: Final[dict[OverviewLocalFilingState, str]] = {
    OverviewLocalFilingState.NOT_READY_TO_FILE: "not ready locally",
    OverviewLocalFilingState.READY_TO_FILE: "ready locally",
    OverviewLocalFilingState.EXTERNAL_BASELINE_IMPORTED: "external filing baseline stored locally",
}
_AEAT_COPY: Final[dict[OverviewAeatSubmissionState, str]] = {
    OverviewAeatSubmissionState.NOT_OBSERVED: "not observed at AEAT",
    OverviewAeatSubmissionState.SUBMITTED_OBSERVED: "submission observed at AEAT",
    OverviewAeatSubmissionState.ACCEPTED: "accepted by AEAT",
    OverviewAeatSubmissionState.JUSTIFICANTE_VERIFIED: "AEAT receipt verified",
}
_ACTION_COPY: Final[dict[str, str]] = {
    "fixture.review": "Review declaration",
    "fixture.classify": "Classify Ledger entries",
    "fixture.evidence": "Add missing evidence",
    "fixture.resolve_blocker": "Resolve declaration blocker",
    "fixture.review_blocker": "Review blocked work",
    "fixture.evidence_blocker": "Resolve missing evidence",
}
_ACTION_REASON_COPY: Final[dict[str, str]] = {
    "fixture.review_required": "Declaration needs review",
    "fixture.classification_pending": "Ledger classification is pending",
    "fixture.evidence_missing": "Supporting evidence is missing",
    "fixture.blocked_dependency": "A declaration dependency is blocked",
    "fixture.blocked_review": "Blocked work needs review",
    "fixture.blocked_evidence": "A blocker needs supporting evidence",
}


def _state_copy(state: HomeZoneState, *, empty_copy: str | None = None) -> str:
    label = _AVAILABILITY_COPY[state.availability]
    if state.availability is HomeAvailability.STALE and state.observed_at is not None:
        observed = state.observed_at.strftime("%d %b %Y %H:%M %Z")
        return f"{label}; last observed {observed}"
    if state.availability is HomeAvailability.AVAILABLE and empty_copy is not None:
        return f"{label} — {empty_copy}"
    return label


def _address(modelo: object, filing_year: int, period_token: str) -> str:
    return f"Modelo {modelo} · {filing_year} · {period_token}"


def _action_identity(item: HomeNextAction) -> str:
    action_id = item.action.action.action_id
    if item.period is None:
        return f"action:{action_id}:{item.reason_code}:cross-cutting"
    return f"action:{action_id}:{item.reason_code}:{item.modelo}:{item.filing_year}:{item.period.registry_token}"


def _declaration_identity(item: HomeDeclarationResume) -> str:
    return f"declaration:{item.work_unit_id}"


def _agenda_identity(item: HomeAgendaEntry) -> str:
    return f"agenda:{item.modelo}:{item.filing_year}:{item.period.registry_token}"


def _action_cells(item: HomeNextAction) -> tuple[str, str, str]:
    label = _ACTION_COPY.get(item.action.action.action_id, "Open suggested task")
    reason = _ACTION_REASON_COPY.get(item.reason_code, "Suggested by the local overview")
    if item.period is None:
        context = "Across records"
    elif item.modelo is None or item.filing_year is None:  # pragma: no cover - model validation rejects this
        raise ValueError("an addressed Home action requires Modelo, year, and period")
    else:
        context = _address(item.modelo, item.filing_year, item.period.registry_token)
    return reason, label, context


def _declaration_cells(item: HomeDeclarationResume) -> tuple[str, str, str]:
    return (
        _address(item.modelo, item.filing_year, item.period.registry_token),
        item.name,
        _DECLARATION_COPY[item.state],
    )


def _agenda_cells(item: HomeAgendaEntry) -> tuple[str, str, str, str, str]:
    return (
        item.due_on.strftime("%d %b %Y"),
        f"Modelo {item.modelo} · {item.period.registry_token}",
        _PERIOD_COPY[item.period_state],
        _LOCAL_COPY[item.local_filing_state],
        _AEAT_COPY[item.aeat_submission_state],
    )


def _evidence_copy(item: HomeAgendaEntry) -> str:
    return f"Local: {_LOCAL_COPY[item.local_filing_state]} · AEAT: {_AEAT_COPY[item.aeat_submission_state]}"


class _ProjectionCandidateScreen(Screen[None]):
    """Shared projection binding and responsive-class behavior only."""

    WIDE_MINIMUM: ClassVar[int] = 120
    BINDINGS: ClassVar = [Binding("escape", "close_candidate", "", show=False)]

    def __init__(self, projection: HomeProjectionV1) -> None:
        super().__init__()
        self._projection = projection
        self._selected_target: HomeCandidateTarget | None = None
        self._targets: dict[str, HomeCandidateTarget] = {}
        self._was_closed = False

    @property
    def projection(self) -> HomeProjectionV1:
        """Return the exact immutable projection supplied by the caller."""
        return self._projection

    @property
    def selected_target(self) -> HomeCandidateTarget | None:
        """Return the last keyboard-confirmed prototype target."""
        return self._selected_target

    @property
    def was_closed(self) -> bool:
        """Report whether the operator invoked the prototype return binding."""
        return self._was_closed

    def on_resize(self, event: events.Resize) -> None:
        """Switch layout classes without changing content or selection."""
        self.set_class(event.size.width >= self.WIDE_MINIMUM, "wide")
        self.set_class(event.size.width < self.WIDE_MINIMUM, "compact")

    def _remember(self, kind: CandidateTargetKind, identity: str) -> str:
        self._targets[identity] = HomeCandidateTarget(kind=kind, identity=identity)
        return identity

    def _confirm(self, row_key: object) -> HomeCandidateTarget | None:
        target = self._targets.get(str(row_key))
        if target is not None:
            self._selected_target = target
        return target

    def action_close_candidate(self) -> None:
        """Return from the prototype without executing the selected target."""
        self._was_closed = True
        self.dismiss(None)


class DueDrivenHomeCandidateScreen(_ProjectionCandidateScreen):
    """Actions-first overview with declarations and a deadline/status rail."""

    CSS = """
    DueDrivenHomeCandidateScreen { layout: vertical; }
    #due-page { width: 100%; height: 1fr; }
    #due-layout, #due-main, #due-sidebar { width: 100%; height: auto; }
    #due-layout { layout: vertical; }
    DueDrivenHomeCandidateScreen.wide #due-layout { layout: horizontal; }
    DueDrivenHomeCandidateScreen.wide #due-main { width: 2fr; }
    DueDrivenHomeCandidateScreen.wide #due-sidebar { width: 1fr; }
    .candidate-panel { height: auto; margin: 0 1 1 0; padding: 0 1; border: round $primary-darken-2; }
    .candidate-heading { text-style: bold; margin-top: 1; }
    .candidate-state { color: $text-muted; }
    .candidate-table { width: 100%; height: auto; }
    """

    @override
    def compose(self) -> ComposeResult:
        projection = self.projection
        yield Static("Home · due-driven candidate", id="due-title", classes="candidate-heading", markup=False)
        yield Static(
            f"{projection.account.profile_label or 'Account'} · {_SESSION_COPY[projection.account.posture]}",
            id="due-session",
            markup=False,
        )
        with ContentScroll(id="due-page"), Static(id="due-layout"):
            with Static(id="due-main"):
                yield Static("Next actions", classes="candidate-heading", markup=False)
                yield Static(
                    _state_copy(
                        projection.actions_state,
                        empty_copy="no suggested actions" if not projection.actions else None,
                    ),
                    id="due-actions-state",
                    classes="candidate-state",
                    markup=False,
                )
                yield ContentDataTable[str](
                    id="due-actions", cursor_type="row", zebra_stripes=True, classes="candidate-table"
                )
                yield Static("Declarations", classes="candidate-heading", markup=False)
                yield Static(
                    _state_copy(
                        projection.declarations_state,
                        empty_copy="no resumable declarations" if not projection.declarations else None,
                    ),
                    id="due-declarations-state",
                    classes="candidate-state",
                    markup=False,
                )
                yield ContentDataTable[str](
                    id="due-declarations", cursor_type="row", zebra_stripes=True, classes="candidate-table"
                )
            with Static(id="due-sidebar"):
                yield Static("Filing agenda", classes="candidate-heading", markup=False)
                yield Static(
                    _state_copy(
                        projection.agenda_state,
                        empty_copy="no upcoming filing dates" if not projection.agenda else None,
                    ),
                    id="due-agenda-state",
                    classes="candidate-state",
                    markup=False,
                )
                yield ContentDataTable[str](
                    id="due-agenda", cursor_type="row", zebra_stripes=True, classes="candidate-table"
                )
                yield Static(id="due-evidence", classes="candidate-state", markup=False)
                yield Static("Ledger", classes="candidate-heading", markup=False)
                yield Static(id="due-ledger", classes="candidate-state", markup=False)
                yield Static("Messages", classes="candidate-heading", markup=False)
                yield Static(id="due-messages", classes="candidate-state", markup=False)

    def on_mount(self) -> None:
        """Populate the three keyboard lists from the supplied projection."""
        projection = self.projection
        actions = cast("ContentDataTable[str]", self.query_one("#due-actions", ContentDataTable))
        actions.add_columns("Attention", "Action", "Context")
        for item in projection.actions:
            actions.add_row(*_action_cells(item), key=self._remember("action", _action_identity(item)))
        actions.display = bool(projection.actions)

        declarations = cast("ContentDataTable[str]", self.query_one("#due-declarations", ContentDataTable))
        declarations.add_columns("Declaration", "Name", "Status")
        for item in projection.declarations:
            declarations.add_row(
                *_declaration_cells(item), key=self._remember("declaration", _declaration_identity(item))
            )
        declarations.display = bool(projection.declarations)

        agenda = cast("ContentDataTable[str]", self.query_one("#due-agenda", ContentDataTable))
        agenda.add_columns("Date", "Declaration", "Deadline", "Local", "AEAT")
        for item in projection.agenda:
            agenda.add_row(*_agenda_cells(item), key=self._remember("agenda", _agenda_identity(item)))
        agenda.display = bool(projection.agenda)

        self.query_one("#due-evidence", Static).update(
            f"AEAT evidence: {_state_copy(projection.agenda_evidence_state)}"
        )
        ledger = projection.ledger
        self.query_one("#due-ledger", Static).update(
            _state_copy(projection.ledger_state)
            if ledger is None
            else (
                f"Available — {ledger.entries} entries; {ledger.requiring_review} need review; "
                f"{ledger.unclassified} unclassified; {ledger.missing_evidence} missing evidence"
            )
        )
        messages = projection.messages_requiring_attention
        self.query_one("#due-messages", Static).update(
            _state_copy(projection.messages_state)
            if messages is None
            else f"Available — {messages} requiring attention"
        )
        first = next((table for table in (actions, declarations, agenda) if table.row_count), None)
        if first is not None:
            self.set_focus(first)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Record Enter against a semantic target without executing it."""
        self._confirm(event.row_key.value)


class TaskLauncherHomeCandidateScreen(_ProjectionCandidateScreen):
    """Single quick-task chooser with contextual detail and compact signals."""

    CSS = """
    TaskLauncherHomeCandidateScreen { layout: vertical; }
    #launcher-page { width: 100%; height: 1fr; }
    #launcher-layout { width: 100%; height: auto; layout: vertical; }
    TaskLauncherHomeCandidateScreen.wide #launcher-layout { layout: horizontal; }
    #launcher-chooser-panel, #launcher-detail-panel { width: 100%; height: auto; }
    TaskLauncherHomeCandidateScreen.wide #launcher-chooser-panel { width: 3fr; }
    TaskLauncherHomeCandidateScreen.wide #launcher-detail-panel { width: 2fr; }
    .candidate-panel { height: auto; margin: 0 1 1 0; padding: 0 1; border: round $primary-darken-2; }
    .candidate-heading { text-style: bold; margin-top: 1; }
    .candidate-state { color: $text-muted; }
    .candidate-table { width: 100%; height: auto; }
    """

    def __init__(self, projection: HomeProjectionV1) -> None:
        """Bind one projection and an initially empty detail catalogue."""
        super().__init__(projection)
        self._details: dict[str, str] = {}

    @override
    def compose(self) -> ComposeResult:
        projection = self.projection
        yield Static("Home · task-launcher candidate", id="launcher-title", classes="candidate-heading", markup=False)
        yield Static(
            f"{projection.account.profile_label or 'Account'} · {_SESSION_COPY[projection.account.posture]}",
            id="launcher-session",
            markup=False,
        )
        with ContentScroll(id="launcher-page"):
            yield Static(id="launcher-signals", classes="candidate-state candidate-panel", markup=False)
            with Static(id="launcher-layout"):
                with Static(id="launcher-chooser-panel", classes="candidate-panel"):
                    yield Static("Quick tasks", classes="candidate-heading", markup=False)
                    yield ContentDataTable[str](
                        id="launcher-chooser", cursor_type="row", zebra_stripes=True, classes="candidate-table"
                    )
                    yield Static(id="launcher-empty", classes="candidate-state", markup=False)
                with Static(id="launcher-detail-panel", classes="candidate-panel"):
                    yield Static("Task detail", classes="candidate-heading", markup=False)
                    yield Static("Choose a task to inspect its context.", id="launcher-detail", markup=False)

    def on_mount(self) -> None:
        """Build one unified chooser; compact signals remain non-interactive."""
        projection = self.projection
        chooser = cast("ContentDataTable[str]", self.query_one("#launcher-chooser", ContentDataTable))
        chooser.add_columns("Quick task", "Status")

        for item in projection.actions:
            identity = self._remember("action", _action_identity(item))
            reason, label, context = _action_cells(item)
            chooser.add_row(label, "Suggested", key=identity)
            self._details[identity] = f"{reason}. {context}."
        for item in projection.declarations:
            identity = self._remember("declaration", _declaration_identity(item))
            address, name, state = _declaration_cells(item)
            chooser.add_row(f"Resume {address}", state, key=identity)
            self._details[identity] = f"{name}. Local declaration status: {state}."
        for item in projection.agenda:
            identity = self._remember("agenda", _agenda_identity(item))
            due, address, state, _local, _aeat = _agenda_cells(item)
            chooser.add_row(f"Inspect {address}", state, key=identity)
            self._details[identity] = f"Due {due}. {_evidence_copy(item)}."

        self.query_one("#launcher-empty", Static).update(
            "No quick tasks are available from the captured local information."
            if not chooser.row_count
            else "Use Up/Down to choose and Enter to confirm."
        )
        chooser.display = bool(chooser.row_count)
        self.query_one("#launcher-signals", Static).update("\n".join(self._signal_lines()))
        if chooser.row_count:
            self.set_focus(chooser)
            self._show_detail(chooser.ordered_rows[0].key.value)

    def _signal_lines(self) -> Iterable[str]:
        projection = self.projection
        actions = _state_copy(
            projection.actions_state,
            empty_copy="none suggested" if not projection.actions else None,
        )
        declarations = _state_copy(
            projection.declarations_state,
            empty_copy="none resumable" if not projection.declarations else None,
        )
        agenda = _state_copy(
            projection.agenda_state,
            empty_copy="no dates" if not projection.agenda else None,
        )
        yield f"Actions: {actions}"
        yield f"Declarations: {declarations}"
        yield f"Agenda: {agenda}"
        yield f"AEAT evidence: {_state_copy(projection.agenda_evidence_state)}"
        if projection.ledger is None:
            yield f"Ledger: {_state_copy(projection.ledger_state)}"
        else:
            yield f"Ledger: Available — {projection.ledger.requiring_review} need review"
        if projection.messages_requiring_attention is None:
            yield f"Messages: {_state_copy(projection.messages_state)}"
        else:
            yield f"Messages: Available — {projection.messages_requiring_attention} requiring attention"

    def _show_detail(self, row_key: object) -> None:
        detail = self._details.get(str(row_key))
        if detail is not None:
            self.query_one("#launcher-detail", Static).update(detail)

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Keep detail synchronized with arrow-key selection."""
        self._show_detail(event.row_key.value)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Record Enter against a semantic target without executing it."""
        target = self._confirm(event.row_key.value)
        if target is not None:
            self._show_detail(target.identity)


__all__ = [
    "CandidateTargetKind",
    "DueDrivenHomeCandidateScreen",
    "HomeCandidateTarget",
    "TaskLauncherHomeCandidateScreen",
]
