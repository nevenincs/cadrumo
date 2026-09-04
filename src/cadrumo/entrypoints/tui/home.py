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

from ...adapters.persistence.storage.recovery_key import generate_recovery_key  # defect

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
from ...core.i18n.render import tr
from .components.theme import BASE_CSS, tokenised
from .components.widgets import ContentDataTable, ContentScroll
from .search import workbench_action_label


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


_AVAILABILITY_KEYS: Final = {
    HomeAvailability.AVAILABLE: "tui.home.availability.available",
    HomeAvailability.LOCKED: "tui.home.availability.locked",
    HomeAvailability.STALE: "tui.home.availability.stale",
    HomeAvailability.NEVER_CAPTURED: "tui.home.availability.never_captured",
    HomeAvailability.UNAVAILABLE: "tui.home.availability.unavailable",
}
_SESSION_KEYS: Final = {
    HomeSessionPosture.NO_PROFILE: "tui.home.session.no_profile",
    HomeSessionPosture.LOCKED: "tui.home.session.locked",
    HomeSessionPosture.ACTIVE: "tui.home.session.active",
    HomeSessionPosture.EXPIRED: "tui.home.session.expired",
}
_DECLARATION_KEYS: Final = {
    HomeDeclarationState.DRAFT: "tui.home.declaration_state.draft",
    HomeDeclarationState.NEEDS_REVIEW: "tui.home.declaration_state.needs_review",
    HomeDeclarationState.READY: "tui.home.declaration_state.ready",
    HomeDeclarationState.FILED: "tui.home.declaration_state.filed",
    HomeDeclarationState.DISCARDED: "tui.home.declaration_state.discarded",
}
_PERIOD_KEYS: Final = {
    OverviewPeriodState.DUE: "tui.home.period_state.due",
    OverviewPeriodState.LATE: "tui.home.period_state.late",
    OverviewPeriodState.FILED: "tui.home.period_state.filed",
    OverviewPeriodState.UNKNOWN: "tui.home.period_state.unknown",
}
_LOCAL_KEYS: Final = {
    OverviewLocalFilingState.NOT_READY_TO_FILE: "tui.home.local_state.not_ready_to_file",
    OverviewLocalFilingState.READY_TO_FILE: "tui.home.local_state.ready_to_file",
    OverviewLocalFilingState.EXTERNAL_BASELINE_IMPORTED: "tui.home.local_state.external_baseline_imported",
}
_AEAT_KEYS: Final = {
    OverviewAeatSubmissionState.NOT_OBSERVED: "tui.home.aeat_state.not_observed",
    OverviewAeatSubmissionState.SUBMITTED_OBSERVED: "tui.home.aeat_state.submitted_observed",
    OverviewAeatSubmissionState.ACCEPTED: "tui.home.aeat_state.accepted",
    OverviewAeatSubmissionState.JUSTIFICANTE_VERIFIED: "tui.home.aeat_state.justificante_verified",
}


def _state_copy(state: HomeZoneState, *, empty_key: str | None = None) -> str:
    """Render one zone's availability as words, never as colour alone."""
    label = tr(_AVAILABILITY_KEYS[state.availability])
    if state.availability is HomeAvailability.STALE and state.observed_at is not None:
        return tr(
            "tui.home.availability.stale_observed",
            label=label,
            observed_at=state.observed_at.strftime("%d/%m/%Y %H:%M UTC"),
        )
    if state.availability is HomeAvailability.AVAILABLE and empty_key is not None:
        return tr("tui.home.availability.available_empty", label=label, detail=tr(empty_key))
    return label


def home_address(modelo: object, filing_year: int, period_token: str) -> str:
    """Format the shared non-sensitive natural address for a Home row."""
    return tr("tui.home.address", modelo=modelo, filing_year=filing_year, period=period_token)


def home_action_identity(item: HomeNextAction) -> str:
    """Return a stable Home action identity independent of row order."""
    action_id = item.action.action.action_id
    if item.period is None:
        return f"action:{action_id}:{item.reason_code}:cross-cutting"
    return f"action:{action_id}:{item.reason_code}:{item.modelo}:{item.filing_year}:{item.period.registry_token}"


def home_declaration_identity(item: HomeDeclarationResume) -> str:
    """Return the canonical declaration-resumption identity."""
    return f"declaration:{item.work_unit_id}"


def home_agenda_identity(item: HomeAgendaEntry) -> str:
    """Return the natural address used to restore an agenda row."""
    return f"agenda:{item.modelo}:{item.filing_year}:{item.period.registry_token}"


def _action_cells(item: HomeNextAction) -> tuple[str, str, str]:
    """Name the action and its reason from the ids the application ranked.

    Both come from catalogues rather than from local prose: the verb resolves
    through the same authority the command palette uses, so a suggested task
    and the command that performs it are never described differently, and an
    unrecognised reason code degrades to the honest generic line instead of
    exposing its identifier.
    """
    label = workbench_action_label(str(item.action.action.action_id))
    reason_key = f"tui.home.reason.{item.reason_code}"
    reason = tr(reason_key)
    if reason == reason_key:
        reason = tr("tui.home.action.reason")
    if item.period is None:
        context = tr("tui.home.action.context_across_records")
    elif item.modelo is None or item.filing_year is None:  # pragma: no cover - projection rejects this shape
        raise ValueError("an addressed Home action requires Modelo, year, and period")
    else:
        context = home_address(item.modelo, item.filing_year, item.period.registry_token)
    return reason, label, context


def _declaration_cells(item: HomeDeclarationResume) -> tuple[str, str, str]:
    return (
        home_address(item.modelo, item.filing_year, item.period.registry_token),
        item.name,
        tr(_DECLARATION_KEYS[item.state]),
    )


def _agenda_cells(item: HomeAgendaEntry) -> tuple[str, str, str]:
    return (
        item.due_on.strftime("%d/%m"),
        f"M{item.modelo} {item.period.registry_token}",
        tr(_PERIOD_KEYS[item.period_state]),
    )


def _evidence_copy(item: HomeAgendaEntry) -> str:
    return tr(
        "tui.home.evidence",
        local=tr(_LOCAL_KEYS[item.local_filing_state]),
        aeat=tr(_AEAT_KEYS[item.aeat_submission_state]),
    )


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
        HomeScreen.wide #home-main { width: 2fr; padding-right: $cadrumo-control-gap; }
        HomeScreen.wide #home-sidebar { width: 1fr; }
        /* Rhythm comes from the shared .cadrumo-heading rule. */
        /* Same inset as the headings and the table rows: a state line that
           starts a cell to their left reads as belonging to something else. */
        .home-state {
            color: $text-muted;
            height: auto;
            padding-left: $cadrumo-cell-padding;
        }
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
    def home_targets(self) -> tuple[HomeTarget, ...]:
        """The domain identities this rendering offered, in mounted order."""
        return tuple(self._targets.values())

    @property
    def projection(self) -> HomeProjectionV1:
        """Return the unchanged injected application projection."""
        return self._projection

    @override
    def compose(self) -> ComposeResult:
        projection = self.projection
        yield Static(tr("tui.home.title"), classes="cadrumo-banner", markup=False)
        yield Static(
            tr(
                "tui.home.session_line",
                label=projection.account.profile_label or tr("tui.home.account_fallback"),
                status=tr(_SESSION_KEYS[projection.account.posture]),
            ),
            id="home-session",
            classes="home-state",
            markup=False,
        )
        with ContentScroll(id="home-page", classes="cadrumo-scroll"), Static(id="home-layout"):
            with Static(id="home-main"):
                yield Static(
                    tr("tui.home.heading.actions"),
                    classes="cadrumo-heading cadrumo-heading-lead",
                    markup=False,
                )
                yield Static(
                    _state_copy(
                        projection.actions_state,
                        empty_key="tui.home.empty.actions" if not projection.actions else None,
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
                    classes="home-table",
                )
                yield Static(id="home-action-contexts", classes="home-state", markup=False)
                yield Static(tr("tui.home.heading.declarations"), classes="cadrumo-heading", markup=False)
                yield Static(
                    _state_copy(
                        projection.declarations_state,
                        empty_key="tui.home.empty.declarations" if not projection.declarations else None,
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
                    classes="home-table",
                )
            with Static(id="home-sidebar"):
                yield Static(tr("tui.home.heading.agenda"), classes="cadrumo-heading", markup=False)
                yield Static(
                    _state_copy(
                        projection.agenda_state,
                        empty_key="tui.home.empty.agenda" if not projection.agenda else None,
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
                    classes="home-table",
                )
                yield Static(id="home-agenda-evidence", classes="home-state", markup=False)
                yield Static(id="home-evidence", classes="home-state", markup=False)
                yield Static(tr("tui.home.heading.ledger"), classes="cadrumo-heading", markup=False)
                yield Static(id="home-ledger", classes="home-state", markup=False)
                yield Static(tr("tui.home.heading.messages"), classes="cadrumo-heading", markup=False)
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
            actions.add_row(label, key=self._remember(HomeTargetKind.ACTION, home_action_identity(item)))
            contexts.append(tr("tui.home.action_context", label=label, reason=reason, context=context))
        actions.display = bool(projection.actions)
        self.query_one("#home-action-contexts", Static).update("\n".join(contexts))

        declarations = cast("ContentDataTable[str]", self.query_one("#home-declarations", ContentDataTable))
        declarations.add_column("")
        for item in projection.declarations:
            address, name, state = _declaration_cells(item)
            declarations.add_row(
                f"{address} · {name} · {state}",
                key=self._remember(HomeTargetKind.DECLARATION, home_declaration_identity(item)),
            )
        declarations.display = bool(projection.declarations)

        agenda = cast("ContentDataTable[str]", self.query_one("#home-agenda", ContentDataTable))
        agenda.add_column("")
        evidence_rows: list[str] = []
        for item in projection.agenda:
            due, address, state = _agenda_cells(item)
            agenda.add_row(
                f"{due} · {address} · {state}",
                key=self._remember(HomeTargetKind.AGENDA, home_agenda_identity(item)),
            )
            evidence_rows.append(tr("tui.home.agenda_evidence_row", address=address, evidence=_evidence_copy(item)))
        agenda.display = bool(projection.agenda)
        self.query_one("#home-agenda-evidence", Static).update("\n".join(evidence_rows))

        self.query_one("#home-evidence", Static).update(
            tr("tui.home.aeat_evidence", state=_state_copy(projection.agenda_evidence_state))
        )
        ledger = projection.ledger
        self.query_one("#home-ledger", Static).update(
            _state_copy(projection.ledger_state)
            if ledger is None
            else tr(
                "tui.home.ledger_summary",
                entries=ledger.entries,
                requiring_review=ledger.requiring_review,
                unclassified=ledger.unclassified,
                missing_evidence=ledger.missing_evidence,
            )
        )
        messages = projection.messages_requiring_attention
        self.query_one("#home-messages", Static).update(
            _state_copy(projection.messages_state)
            if messages is None
            else tr("tui.home.messages_summary", count=messages)
        )
        first = next((table for table in (actions, declarations, agenda) if table.row_count), None)
        if first is not None and not self._restore((actions, declarations, agenda)):
            self.set_focus(first)
            self._highlight(first.ordered_rows[0].key.value)
            # Focusing scrolls the target into view, and in the single-column
            # layout the first table is far enough down that doing so scrolls
            # the top of the page away: the operator arrives on Home already
            # past its opening heading, with no indication anything is above.
            # This is a FRESH arrival with nothing to restore, so the top is
            # where they belong; the restored-selection branch above keeps its
            # own scroll position deliberately.
            # After the refresh, not during it: the scroll that focusing causes
            # is applied once layout settles, so a scroll issued here in mount
            # order is simply overwritten by it.
            self.call_after_refresh(self._scroll_to_top)
        if first is None:
            # Every zone is empty or refused, so the three tables are hidden and
            # nothing on the page can take focus. Home is the destination an
            # operator lands on first, and a keyboard user needs somewhere to
            # arrive: the page itself takes focus so the zone states can be
            # read and scrolled, and Escape still returns.
            page = self.query_one("#home-page", ContentScroll)
            page.can_focus = True
            self.set_focus(page)

    def _scroll_to_top(self) -> None:
        """Return the page to its opening heading after focus has settled."""
        self.query_one("#home-page", ContentScroll).scroll_home(animate=False)

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


__all__ = [
    "HomeBackRequested",
    "HomeScreen",
    "HomeTarget",
    "HomeTargetSelected",
    "home_action_identity",
    "home_address",
    "home_agenda_identity",
    "home_declaration_identity",
]
