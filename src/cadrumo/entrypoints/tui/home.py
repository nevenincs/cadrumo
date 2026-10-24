"""Projection-only production Home surface for the operator workbench.

The screen renders one already-composed :class:`HomeProjectionV1`.  It neither
reads application state nor invokes an action: its host receives semantic row
selections and owns any later destination or action hand-off.  Its links name
the rest of the workbench in words; the host says which of them it can open and
performs whichever one is chosen.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum, auto
from types import MappingProxyType
from typing import ClassVar, Final, cast, override

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.message import Message
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
    HomeTargetKind,
    HomeZoneState,
)
from ...application.search.workbench import WorkbenchDestinationAdmissionState
from ...core.i18n.render import lookup_translation, output_language, tr
from .components.account_chrome import AccountChromeScreen
from .components.language import localized, repaint_tables
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


class HomeLinkV1(StrEnum):
    """One door Home offers into the rest of the workbench.

    Home names the door; the host owns where it leads and whether it opens.
    """

    DECLARATIONS = auto()
    NEW_DECLARATION = auto()
    SEARCH_DECLARATIONS = auto()
    CALENDAR = auto()
    LEDGER = auto()
    AEAT_SYNC = auto()
    REFERENCE = auto()
    PROFILE = auto()
    SIGN_OUT = auto()


HOME_ACCOUNT_LINKS: Final[tuple[HomeLinkV1, ...]] = (HomeLinkV1.PROFILE, HomeLinkV1.SIGN_OUT)
"""The links kept apart under the account heading, after the workbench's own."""

type HomeLinkStatesV1 = Mapping[HomeLinkV1, WorkbenchDestinationAdmissionState]


class HomeLinkSelected(Message):
    """Ask the host to open one of Home's links."""

    def __init__(self, link: HomeLinkV1) -> None:
        """Carry only which link was chosen."""
        super().__init__()
        self.link = link


_AVAILABILITY_LOCALE_KEYS: Final = {
    HomeAvailability.AVAILABLE: "tui.home.availability.available",
    HomeAvailability.LOCKED: "tui.home.availability.locked",
    HomeAvailability.STALE: "tui.home.availability.stale",
    HomeAvailability.NEVER_CAPTURED: "tui.home.availability.never_captured",
    HomeAvailability.UNAVAILABLE: "tui.home.availability.unavailable",
}
_DECLARATION_LOCALE_KEYS: Final = {
    HomeDeclarationState.DRAFT: "tui.home.declaration_state.draft",
    HomeDeclarationState.NEEDS_REVIEW: "tui.home.declaration_state.needs_review",
    HomeDeclarationState.READY: "tui.home.declaration_state.ready",
    HomeDeclarationState.FILED: "tui.home.declaration_state.filed",
    HomeDeclarationState.DISCARDED: "tui.home.declaration_state.discarded",
}
_AEAT_FILING_STATUS_LOCALE_KEYS: Final = {
    OverviewAeatSubmissionState.SUBMITTED_OBSERVED: "tui.home.filing_status.submitted",
    OverviewAeatSubmissionState.ACCEPTED: "tui.home.filing_status.accepted",
    OverviewAeatSubmissionState.JUSTIFICANTE_VERIFIED: "tui.home.filing_status.receipt_verified",
}
_UNFILED_STATUS_LOCALE_KEYS: Final = {
    OverviewPeriodState.DUE: "tui.home.filing_status.due",
    OverviewPeriodState.LATE: "tui.home.filing_status.overdue",
    OverviewPeriodState.UNKNOWN: "tui.home.filing_status.unknown",
}
_LINK_LABEL_LOCALE_KEYS: Final = {
    HomeLinkV1.DECLARATIONS: "tui.destination.declarations",
    HomeLinkV1.NEW_DECLARATION: "workspace.declarations.list.key.new",
    HomeLinkV1.SEARCH_DECLARATIONS: "tui.home.link.search_declarations",
    HomeLinkV1.CALENDAR: "workspace.declarations.destination.calendar",
    HomeLinkV1.LEDGER: "tui.destination.ledger",
    HomeLinkV1.AEAT_SYNC: "tui.destination.aeat_sync",
    HomeLinkV1.REFERENCE: "tui.destination.reference",
    HomeLinkV1.PROFILE: "tui.root.account.profile",
    HomeLinkV1.SIGN_OUT: "tui.root.account.sign_out",
}
_LINK_BINDING_KEYS: Final = {
    HomeLinkV1.DECLARATIONS: "d",
    HomeLinkV1.NEW_DECLARATION: "plus",
    HomeLinkV1.SEARCH_DECLARATIONS: "slash",
    HomeLinkV1.CALENDAR: "c",
    HomeLinkV1.LEDGER: "r",
    HomeLinkV1.AEAT_SYNC: "a",
    HomeLinkV1.PROFILE: "p",
}
"""Keys Home binds itself; Home has no text field, so a bare letter is free here."""
_LINK_KEY_GLYPHS: Final = {
    HomeLinkV1.DECLARATIONS: "d",
    HomeLinkV1.NEW_DECLARATION: "+",
    HomeLinkV1.SEARCH_DECLARATIONS: "/",
    HomeLinkV1.CALENDAR: "c",
    HomeLinkV1.LEDGER: "r",
    HomeLinkV1.AEAT_SYNC: "a",
    HomeLinkV1.PROFILE: "p",
    # Bound by the root on every destination, not by Home.
    HomeLinkV1.SIGN_OUT: "F10",
}
_LINK_STATE_LOCALE_KEYS: Final = {
    WorkbenchDestinationAdmissionState.LOCKED: "tui.home.link_state.locked",
    WorkbenchDestinationAdmissionState.STALE: "tui.home.link_state.stale",
    WorkbenchDestinationAdmissionState.NEVER_CAPTURED: "tui.home.link_state.never_captured",
    WorkbenchDestinationAdmissionState.UNAVAILABLE: "tui.home.link_state.unavailable",
}
_LINK_ROW_PREFIX: Final = "link:"
_IMPORTED_STATUS_LOCALE_KEY: Final = "tui.home.filing_status.imported"
_MARKED_FILED_STATUS_LOCALE_KEY: Final = "tui.home.filing_status.marked_filed"


def _has_copy(translation_key: str) -> bool:
    """Whether the active language authors this key.

    :func:`tr` never reports a miss: it humanises the key's last segment, so
    comparing its result with the key cannot tell an authored sentence from
    an invented one.
    """
    return lookup_translation(translation_key, locale=output_language()) is not None


def _state_copy(state: HomeZoneState, *, empty_key: str | None = None) -> str:
    """Render one zone's availability as words, never as colour alone.

    A zone that is not showing its data says why, from the reason the
    application attached, because the generic line can only guess at a cause
    and an operator acts on the cause. The generic line remains for a reason
    this page has no words for yet.
    """
    if state.reason_code is not None and state.availability is not HomeAvailability.STALE:
        reason_key = f"tui.home.availability.reason.{state.reason_code}"
        if _has_copy(reason_key):
            return tr(reason_key)
    label = tr(_AVAILABILITY_LOCALE_KEYS[state.availability])
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


def home_target_action_id(target: HomeTarget) -> str | None:
    """Return the action a next-action row names, read back from its identity."""
    if target.kind is not HomeTargetKind.ACTION:
        return None
    return target.identity.split(":")[1]


def home_target_work_unit_id(target: HomeTarget) -> str | None:
    """Return the work unit a resumable-declaration row names."""
    if target.kind is not HomeTargetKind.DECLARATION:
        return None
    return target.identity.removeprefix("declaration:")


def home_target_agenda_address(target: HomeTarget) -> tuple[str, str, str] | None:
    """Return the Modelo, filing year and period an agenda row names."""
    if target.kind is not HomeTargetKind.AGENDA:
        return None
    _kind, modelo, year, period = target.identity.split(":", 3)
    return modelo, year, period


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
    reason = tr(reason_key) if _has_copy(reason_key) else tr("tui.home.action.reason")
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
        tr(_DECLARATION_LOCALE_KEYS[item.state]),
    )


def _filing_status_key(item: HomeAgendaEntry) -> str:
    """Name the one status an agenda row shows.

    AEAT evidence outranks the local record and the local record outranks the
    deadline, so a row never repeats a claim a stronger source already settled.
    A locally recorded filing still says AEAT has not confirmed it.
    """
    aeat_key = _AEAT_FILING_STATUS_LOCALE_KEYS.get(item.aeat_submission_state)
    if aeat_key is not None:
        return aeat_key
    if item.local_filing_state is OverviewLocalFilingState.EXTERNAL_BASELINE_IMPORTED:
        return _IMPORTED_STATUS_LOCALE_KEY
    if (
        item.local_filing_state is OverviewLocalFilingState.READY_TO_FILE
        or item.period_state is OverviewPeriodState.FILED
    ):
        return _MARKED_FILED_STATUS_LOCALE_KEY
    return _UNFILED_STATUS_LOCALE_KEYS[item.period_state]


def _link_label(link: HomeLinkV1) -> str:
    """Name one link after the key that opens it."""
    return f"{_LINK_KEY_GLYPHS.get(link, ''):<3} {tr(_LINK_LABEL_LOCALE_KEYS[link])}"


def _link_cell(link: HomeLinkV1, state: WorkbenchDestinationAdmissionState) -> tuple[str, int]:
    """Name one link, and say on a second line why it cannot open.

    A link the session cannot open stays listed, so the operator learns the
    page exists and why it is closed rather than finding it missing.
    """
    state_key = _LINK_STATE_LOCALE_KEYS.get(state)
    if state_key is None:
        return _link_label(link), 1
    return f"{_link_label(link)}\n{'':<3} {tr(state_key)}", 2


def _agenda_cells(item: HomeAgendaEntry) -> tuple[str, str, str]:
    return (
        item.due_on.strftime("%d/%m"),
        f"M{item.modelo} {item.period.registry_token}",
        tr(_filing_status_key(item)),
    )


class HomeScreen(AccountChromeScreen):
    """The selected responsive due-driven layout over one immutable projection."""

    WIDE_MINIMUM: ClassVar[int] = 120
    BINDINGS: ClassVar = [
        Binding("escape", "back", "", show=False),
        *(Binding(key, f"open_link('{link.value}')", "", show=False) for link, key in _LINK_BINDING_KEYS.items()),
    ]
    CSS = BASE_CSS + tokenised(
        """
        HomeScreen { layout: vertical; }
        #home-page { width: 100%; height: 1fr; }
        #home-layout, #home-main, #home-sidebar { width: 100%; height: auto; }
        #home-layout { layout: vertical; }
        HomeScreen.wide #home-layout { layout: horizontal; }
        HomeScreen.wide #home-main { width: 2fr; padding-right: $cadrumo-control-gap; }
        HomeScreen.wide #home-sidebar { width: 1fr; }
        /* Wide, the links head the side column in plain view. At the floor
           that column follows the zones, so one line of keys at the top
           names every link before any scrolling. */
        HomeScreen.wide #home-link-keys { display: none; }
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

    def __init__(
        self,
        projection: HomeProjectionV1,
        *,
        restore_target: HomeTarget | None = None,
        link_states: HomeLinkStatesV1 | None = None,
    ) -> None:
        """Bind one immutable projection, an optional semantic focus target, and link admissions.

        A link the host does not mention is offered as open: a standalone host
        has no catalogue to consult, and choosing a link only sends a message.
        """
        super().__init__(id="home-screen")
        self._projection = projection
        self._restore_target = restore_target
        self._link_states: HomeLinkStatesV1 = MappingProxyType(dict(link_states or {}))
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
        yield localized(Static(tr("tui.home.title"), classes="cadrumo-banner", markup=False), "tui.home.title")
        with ContentScroll(id="home-page", classes="cadrumo-scroll"):
            yield Static(id="home-link-keys", classes="home-state", markup=False)
            with Static(id="home-layout"):
                yield from self._compose_zones(projection)

    def _compose_links(self) -> ComposeResult:
        """The doors to every other page, kept in the column beside the work.

        A rail of their own would cost the main column the width its
        declaration rows need at the wide breakpoint.
        """
        yield localized(
            Static(tr("tui.home.heading.navigation"), classes="cadrumo-heading", markup=False),
            "tui.home.heading.navigation",
        )
        yield ContentDataTable[str](id="home-links", cursor_type="row", show_header=False, classes="home-table")
        yield localized(
            Static(tr("tui.home.heading.account"), classes="cadrumo-heading", markup=False),
            "tui.home.heading.account",
        )
        yield ContentDataTable[str](id="home-account-links", cursor_type="row", show_header=False, classes="home-table")

    def _compose_zones(self, projection: HomeProjectionV1) -> ComposeResult:
        with Static(id="home-main"):
            yield localized(
                Static(
                    tr("tui.home.heading.actions"),
                    classes="cadrumo-heading cadrumo-heading-lead",
                    markup=False,
                ),
                "tui.home.heading.actions",
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
            yield localized(
                Static(tr("tui.home.heading.declarations"), classes="cadrumo-heading", markup=False),
                "tui.home.heading.declarations",
            )
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
            yield from self._compose_links()
            yield localized(
                Static(tr("tui.home.heading.agenda"), classes="cadrumo-heading", markup=False),
                "tui.home.heading.agenda",
            )
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
            yield Static(id="home-evidence", classes="home-state", markup=False)
            yield localized(
                Static(tr("tui.home.heading.ledger"), classes="cadrumo-heading", markup=False),
                "tui.home.heading.ledger",
            )
            yield Static(id="home-ledger", classes="home-state", markup=False)
            yield localized(
                Static(tr("tui.home.heading.messages"), classes="cadrumo-heading", markup=False),
                "tui.home.heading.messages",
            )
            yield Static(id="home-messages", classes="home-state", markup=False)

    def on_resize(self, event: events.Resize) -> None:
        """Swap geometry at the measured breakpoint without changing rows."""
        self.set_class(event.size.width >= self.WIDE_MINIMUM, "wide")
        self.set_class(event.size.width < self.WIDE_MINIMUM, "compact")

    def on_mount(self) -> None:
        """Populate display-only lists from the immutable projection."""
        projection = self.projection
        actions = cast("ContentDataTable[str]", self.query_one("#home-actions", ContentDataTable))
        self._populate_actions(actions, projection.actions)
        declarations = cast("ContentDataTable[str]", self.query_one("#home-declarations", ContentDataTable))
        self._populate_declarations(declarations, projection.declarations)
        agenda = cast("ContentDataTable[str]", self.query_one("#home-agenda", ContentDataTable))
        self._populate_agenda(agenda, projection.agenda)
        self._render_zone_summaries(projection)
        self._populate_links()
        self._focus_initial_table((actions, declarations, agenda))

    @override
    async def refresh_language(self) -> None:
        """Reword the retained projection without moving its semantic selection."""
        await super().refresh_language()
        projection = self.projection

        def paint() -> None:
            self._populate_actions(self.query_one("#home-actions", ContentDataTable), projection.actions)
            self._populate_declarations(self.query_one("#home-declarations", ContentDataTable), projection.declarations)
            self._populate_agenda(self.query_one("#home-agenda", ContentDataTable), projection.agenda)
            self._render_zone_summaries(projection)
            self._populate_links()

        repaint_tables(self, paint)
        for zone, state, items in (
            ("actions", projection.actions_state, projection.actions),
            ("declarations", projection.declarations_state, projection.declarations),
            ("agenda", projection.agenda_state, projection.agenda),
        ):
            self.query_one(f"#home-{zone}-state", Static).update(
                _state_copy(state, empty_key=f"tui.home.empty.{zone}" if not items else None)
            )

    def link_state(self, link: HomeLinkV1) -> WorkbenchDestinationAdmissionState:
        """Return whether the host can open one link now."""
        return self._link_states.get(link, WorkbenchDestinationAdmissionState.AVAILABLE)

    def _populate_links(self) -> None:
        for table_id, links in (
            ("#home-links", tuple(link for link in HomeLinkV1 if link not in HOME_ACCOUNT_LINKS)),
            ("#home-account-links", HOME_ACCOUNT_LINKS),
        ):
            table = cast("ContentDataTable[str]", self.query_one(table_id, ContentDataTable))
            table.add_column("")
            for link in links:
                text, height = _link_cell(link, self.link_state(link))
                table.add_row(text, height=height, key=f"{_LINK_ROW_PREFIX}{link.value}")
        # Only the links that can open are promised in the line of keys.
        self.query_one("#home-link-keys", Static).update(
            " · ".join(
                f"{_LINK_KEY_GLYPHS[link]} {tr(_LINK_LABEL_LOCALE_KEYS[link])}"
                for link in HomeLinkV1
                if link in _LINK_KEY_GLYPHS and self.link_state(link) is WorkbenchDestinationAdmissionState.AVAILABLE
            )
        )

    def _populate_actions(
        self,
        table: ContentDataTable[str],
        items: tuple[HomeNextAction, ...],
    ) -> None:
        table.add_column("")
        contexts: list[str] = []
        for item in items:
            reason, label, context = _action_cells(item)
            table.add_row(label, key=self._remember(HomeTargetKind.ACTION, home_action_identity(item)))
            contexts.append(tr("tui.home.action_context", label=label, reason=reason, context=context))
        table.display = bool(items)
        self.query_one("#home-action-contexts", Static).update("\n".join(contexts))

    def _populate_declarations(
        self,
        table: ContentDataTable[str],
        items: tuple[HomeDeclarationResume, ...],
    ) -> None:
        table.add_column("")
        for item in items:
            address, name, state = _declaration_cells(item)
            table.add_row(
                f"{address} · {name} · {state}",
                key=self._remember(HomeTargetKind.DECLARATION, home_declaration_identity(item)),
            )
        table.display = bool(items)

    def _populate_agenda(
        self,
        table: ContentDataTable[str],
        items: tuple[HomeAgendaEntry, ...],
    ) -> None:
        table.add_column("")
        for item in items:
            due, address, state = _agenda_cells(item)
            table.add_row(
                f"{due} · {address} · {state}",
                key=self._remember(HomeTargetKind.AGENDA, home_agenda_identity(item)),
            )
        table.display = bool(items)

    def _render_zone_summaries(self, projection: HomeProjectionV1) -> None:
        # Only a missing, locked or stale AEAT read changes how the agenda
        # statuses should be read; a current read needs no line of its own.
        evidence_state = projection.agenda_evidence_state
        evidence = self.query_one("#home-evidence", Static)
        evidence.update(tr("tui.home.aeat_evidence", state=_state_copy(evidence_state)))
        evidence.display = evidence_state.availability is not HomeAvailability.AVAILABLE
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

    def _focus_initial_table(self, tables: tuple[ContentDataTable[str], ...]) -> None:
        first = next((table for table in tables if table.row_count), None)
        if first is not None and not self._restore(tables):
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
            # Every zone is empty or refused, so the three tables are hidden.
            # Home is the destination an operator lands on first, and a
            # keyboard user needs somewhere to arrive: the links are always
            # there, and from them every other page is one key away.
            self.set_focus(self.query_one("#home-links", ContentDataTable))
            self.call_after_refresh(self._scroll_to_top)

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
        # The links are not a Home row to restore; moving through them keeps
        # the row the operator last stood on.
        if table is self.focused and not str(event.row_key.value).startswith(_LINK_ROW_PREFIX):
            self._highlight(event.row_key.value)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Notify the host of a selection without dispatching a business action."""
        row_key = str(event.row_key.value)
        if row_key.startswith(_LINK_ROW_PREFIX):
            self.action_open_link(row_key.removeprefix(_LINK_ROW_PREFIX))
            return
        target = self._targets.get(row_key)
        if target is not None:
            self.selected_target = target
            self.post_message(HomeTargetSelected(target))

    def action_open_link(self, link: str) -> None:
        """Ask the host to open one link; the host refuses a link it cannot open."""
        self.post_message(HomeLinkSelected(HomeLinkV1(link)))

    def action_back(self) -> None:
        """Return control to the host without dismissing the application."""
        self.back_requested = True
        self.post_message(HomeBackRequested())


__all__ = [
    "HOME_ACCOUNT_LINKS",
    "HomeBackRequested",
    "HomeLinkSelected",
    "HomeLinkStatesV1",
    "HomeLinkV1",
    "HomeScreen",
    "HomeTarget",
    "HomeTargetSelected",
    "home_action_identity",
    "home_address",
    "home_agenda_identity",
    "home_declaration_identity",
    "home_target_action_id",
    "home_target_agenda_address",
    "home_target_work_unit_id",
]
