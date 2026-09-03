"""Projection-only production Home surface for the operator workbench.

The screen renders one already-composed :class:`HomeProjectionV1`.  It neither
reads application state nor invokes an action: its host receives semantic row
selections and owns any later destination or action hand-off.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, Final, cast, override

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.message import Message
from textual.screen import Screen
from textual.widgets import DataTable, Static

from ...application.overview.calendar_models import (
    OverviewAeatSubmissionState,
    OverviewLocalFilingState,
    OverviewPeriodState,
)
from ...application.overview.home import (
    HomeAgendaEntry,
    HomeAvailability,
    HomeDeclarationResume,
    HomeDeclarationState,
    HomeNextAction,
    HomeProjectionV1,
    HomeSessionPosture,
    HomeTargetKind,
    HomeZoneState,
)
from .components.theme import BASE_CSS, tokenised
from .components.widgets import ContentDataTable, ContentScroll


@dataclass(frozen=True, slots=True)
class HomeTarget:
    """A selected Home row identified independently of its rendered position."""

    kind: HomeTargetKind
    identity: str


class HomeTargetSelected(Message):
    """Ask the host to handle an admitted semantic Home selection."""

    def __init__(self, target: HomeTarget) -> None:
        """Carry the already-resolved semantic selection to the host."""
        super().__init__()
        self.target = target


class HomeBackRequested(Message):
    """Ask the host to return without making a business call."""


_AVAILABILITY_COPY: Final = {
    HomeAvailability.AVAILABLE: "Available",
    HomeAvailability.LOCKED: "Locked — unlock the selected profile to view this information",
    HomeAvailability.STALE: "Stale — the last local snapshot needs refresh",
    HomeAvailability.NEVER_CAPTURED: "Not captured yet",
    HomeAvailability.UNAVAILABLE: "Unavailable — this source cannot be read in the current session",
}
_SESSION_COPY: Final = {
    HomeSessionPosture.NO_PROFILE: "No profile selected",
    HomeSessionPosture.LOCKED: "Profile locked",
    HomeSessionPosture.ACTIVE: "Active local session",
    HomeSessionPosture.EXPIRED: "Session expired",
}
_DECLARATION_COPY: Final = {
    HomeDeclarationState.DRAFT: "Draft",
    HomeDeclarationState.NEEDS_REVIEW: "Needs review",
    HomeDeclarationState.READY: "Ready",
    HomeDeclarationState.FILED: "Filed",
    HomeDeclarationState.DISCARDED: "Discarded",
}
_PERIOD_COPY: Final = {
    OverviewPeriodState.DUE: "Due",
    OverviewPeriodState.LATE: "Overdue",
    OverviewPeriodState.FILED: "Filed",
    OverviewPeriodState.UNKNOWN: "Schedule unknown",
}
_LOCAL_COPY: Final = {
    OverviewLocalFilingState.NOT_READY_TO_FILE: "not ready locally",
    OverviewLocalFilingState.READY_TO_FILE: "ready locally",
    OverviewLocalFilingState.EXTERNAL_BASELINE_IMPORTED: "external filing baseline stored locally",
}
_AEAT_COPY: Final = {
    OverviewAeatSubmissionState.NOT_OBSERVED: "not observed at AEAT",
    OverviewAeatSubmissionState.SUBMITTED_OBSERVED: "submission observed at AEAT",
    OverviewAeatSubmissionState.ACCEPTED: "accepted by AEAT",
    OverviewAeatSubmissionState.JUSTIFICANTE_VERIFIED: "AEAT receipt verified",
}
_ACTION_COPY: Final = {
    "fixture.review": "Review declaration",
    "fixture.classify": "Classify Ledger entries",
    "fixture.evidence": "Add missing evidence",
    "fixture.resolve_blocker": "Resolve declaration blocker",
    "fixture.review_blocker": "Review blocked work",
    "fixture.evidence_blocker": "Resolve missing evidence",
}
_ACTION_REASON_COPY: Final = {
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
        return f"{label}; last observed {state.observed_at.strftime('%d/%m/%Y %H:%M UTC')}"
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
    elif item.modelo is None or item.filing_year is None:  # pragma: no cover - projection rejects this shape
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


def _agenda_cells(item: HomeAgendaEntry) -> tuple[str, str, str]:
    return (
        item.due_on.strftime("%d/%m"),
        f"M{item.modelo} {item.period.registry_token}",
        _PERIOD_COPY[item.period_state],
    )


def _evidence_copy(item: HomeAgendaEntry) -> str:
    return f"Local: {_LOCAL_COPY[item.local_filing_state]} · AEAT: {_AEAT_COPY[item.aeat_submission_state]}"


class HomeScreen(Screen[None]):
    """The selected responsive due-driven layout over one immutable projection."""

    WIDE_MINIMUM: ClassVar[int] = 120
    BINDINGS: ClassVar = [Binding("escape", "back", "", show=False)]
    CSS = BASE_CSS + tokenised(
        """
        HomeScreen { layout: vertical; }
        #home-page { width: 100%; height: 1fr; }
        #home-layout, #home-main, #home-sidebar { width: 100%; height: auto; }
        #home-layout { layout: vertical; }
        HomeScreen.wide #home-layout { layout: horizontal; }
        HomeScreen.wide #home-main { width: 2fr; }
        HomeScreen.wide #home-sidebar { width: 1fr; }
        .home-heading { text-style: bold; margin-top: $cadrumo-stack; }
        .home-state { color: $text-muted; height: auto; }
        .home-table { width: 100%; height: auto; }
        """
    )

    def __init__(self, projection: HomeProjectionV1, *, restore_target: HomeTarget | None = None) -> None:
        """Bind one immutable projection and an optional semantic focus target."""
        super().__init__(id="home-screen")
        self._projection = projection
        self._restore_target = restore_target
        self._targets: dict[str, HomeTarget] = {}
        self.selected_target: HomeTarget | None = None
        self.highlighted_target: HomeTarget | None = None
        self.back_requested = False

    @property
    def projection(self) -> HomeProjectionV1:
        """Return the unchanged injected application projection."""
        return self._projection

    @override
    def compose(self) -> ComposeResult:
        projection = self.projection
        yield Static("Home", classes="cadrumo-banner", markup=False)
        yield Static(
            f"{projection.account.profile_label or 'Account'} · Status: {_SESSION_COPY[projection.account.posture]}",
            id="home-session",
            classes="home-state",
            markup=False,
        )
        with ContentScroll(id="home-page", classes="cadrumo-scroll"), Static(id="home-layout"):
            with Static(id="home-main"):
                yield Static("Next actions", classes="home-heading", markup=False)
                yield Static(
                    _state_copy(
                        projection.actions_state,
                        empty_copy="no suggested actions" if not projection.actions else None,
                    ),
                    id="home-actions-state",
                    classes="home-state",
                    markup=False,
                )
                yield ContentDataTable[str](
                    id="home-actions",
                    cursor_type="row",
                    zebra_stripes=True,
                    show_header=False,
                    cell_padding=0,
                    classes="home-table",
                )
                yield Static(id="home-action-contexts", classes="home-state", markup=False)
                yield Static("Declarations", classes="home-heading", markup=False)
                yield Static(
                    _state_copy(
                        projection.declarations_state,
                        empty_copy="no resumable declarations" if not projection.declarations else None,
                    ),
                    id="home-declarations-state",
                    classes="home-state",
                    markup=False,
                )
                yield ContentDataTable[str](
                    id="home-declarations",
                    cursor_type="row",
                    zebra_stripes=True,
                    show_header=False,
                    cell_padding=0,
                    classes="home-table",
                )
            with Static(id="home-sidebar"):
                yield Static("Filing agenda", classes="home-heading", markup=False)
                yield Static(
                    _state_copy(
                        projection.agenda_state,
                        empty_copy="no upcoming filing dates" if not projection.agenda else None,
                    ),
                    id="home-agenda-state",
                    classes="home-state",
                    markup=False,
                )
                yield ContentDataTable[str](
                    id="home-agenda",
                    cursor_type="row",
                    zebra_stripes=True,
                    show_header=False,
                    cell_padding=0,
                    classes="home-table",
                )
                yield Static(id="home-agenda-evidence", classes="home-state", markup=False)
                yield Static(id="home-evidence", classes="home-state", markup=False)
                yield Static("Ledger readiness", classes="home-heading", markup=False)
                yield Static(id="home-ledger", classes="home-state", markup=False)
                yield Static("Messages", classes="home-heading", markup=False)
                yield Static(id="home-messages", classes="home-state", markup=False)

    def on_resize(self, event: events.Resize) -> None:
        """Swap geometry at the measured breakpoint without changing rows."""
        self.set_class(event.size.width >= self.WIDE_MINIMUM, "wide")
        self.set_class(event.size.width < self.WIDE_MINIMUM, "compact")

    def on_mount(self) -> None:
        """Populate display-only lists from the immutable projection."""
        projection = self.projection
        actions = cast("ContentDataTable[str]", self.query_one("#home-actions", ContentDataTable))
        actions.add_column("")
        contexts: list[str] = []
        for item in projection.actions:
            reason, label, context = _action_cells(item)
            actions.add_row(label, key=self._remember(HomeTargetKind.ACTION, _action_identity(item)))
            contexts.append(f"{label} — {reason} · {context}")
        actions.display = bool(projection.actions)
        self.query_one("#home-action-contexts", Static).update("\n".join(contexts))

        declarations = cast("ContentDataTable[str]", self.query_one("#home-declarations", ContentDataTable))
        declarations.add_column("")
        for item in projection.declarations:
            address, name, state = _declaration_cells(item)
            declarations.add_row(
                f"{address} · {name} · {state}",
                key=self._remember(HomeTargetKind.DECLARATION, _declaration_identity(item)),
            )
        declarations.display = bool(projection.declarations)

        agenda = cast("ContentDataTable[str]", self.query_one("#home-agenda", ContentDataTable))
        agenda.add_column("")
        evidence_rows: list[str] = []
        for item in projection.agenda:
            due, address, state = _agenda_cells(item)
            agenda.add_row(
                f"{due} · {address} · {state}",
                key=self._remember(HomeTargetKind.AGENDA, _agenda_identity(item)),
            )
            evidence_rows.append(f"{address} — {_evidence_copy(item)}")
        agenda.display = bool(projection.agenda)
        self.query_one("#home-agenda-evidence", Static).update("\n".join(evidence_rows))

        self.query_one("#home-evidence", Static).update(
            f"AEAT evidence: {_state_copy(projection.agenda_evidence_state)}"
        )
        ledger = projection.ledger
        self.query_one("#home-ledger", Static).update(
            _state_copy(projection.ledger_state)
            if ledger is None
            else (
                f"Available — {ledger.entries} entries; {ledger.requiring_review} need review; "
                f"{ledger.unclassified} unclassified; {ledger.missing_evidence} missing evidence"
            )
        )
        messages = projection.messages_requiring_attention
        self.query_one("#home-messages", Static).update(
            _state_copy(projection.messages_state)
            if messages is None
            else f"Available — {messages} requiring attention"
        )
        first = next((table for table in (actions, declarations, agenda) if table.row_count), None)
        if first is not None and not self._restore((actions, declarations, agenda)):
            self.set_focus(first)
            self._highlight(first.ordered_rows[0].key.value)

    def _remember(self, kind: HomeTargetKind, identity: str) -> str:
        self._targets[identity] = HomeTarget(kind=kind, identity=identity)
        return identity

    def _restore(self, tables: tuple[ContentDataTable[str], ...]) -> bool:
        if self._restore_target is None:
            return False
        for table in tables:
            for row_index, row in enumerate(table.ordered_rows):
                if row.key.value == self._restore_target.identity:
                    table.move_cursor(row=row_index)
                    self.set_focus(table)
                    self.highlighted_target = self._restore_target
                    return True
        return False

    def _highlight(self, row_key: object) -> None:
        self.highlighted_target = self._targets.get(str(row_key))

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Track a semantic target, never a row number."""
        table = cast("DataTable[str]", event.data_table)
        if table is self.focused:
            self._highlight(event.row_key.value)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Notify the host of a selection without dispatching a business action."""
        target = self._targets.get(str(event.row_key.value))
        if target is not None:
            self.selected_target = target
            self.post_message(HomeTargetSelected(target))

    def action_back(self) -> None:
        """Return control to the host without dismissing the application."""
        self.back_requested = True
        self.post_message(HomeBackRequested())


__all__ = ["HomeBackRequested", "HomeScreen", "HomeTarget", "HomeTargetSelected"]
