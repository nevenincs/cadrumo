"""Profile editing and the guided setup of an unfinished profile.

Setup presents overview, optional acquisition, required answers, review and
confirmed completion. These stages hold only navigation state. Answers save
immediately through the same field door used by ongoing profile editing;
only an explicit Finish action requests the application's completion check.

The profile page displays schema sections and recorded values, including
each instance of repeatable facts. Optional sections start collapsed and
remain editable without affecting setup progress.

The screen owns no profile policy. The page content is
:func:`~cadrumo.application.user_profile.overview.build_profile_overview`, and an
edit is an authenticated revision-bound fact command.

See Also:
    :class:`~cadrumo.application.user_profile.overview.ProfileOverview`
        The typed projection this screen renders.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import TYPE_CHECKING, ClassVar, override

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Checkbox, DataTable, Footer, Input, ProgressBar, Static
from textual.worker import Worker

from ....application.user_profile.acquisition_sources import (
    AcquisitionSourceCredentialPostureV1,
    ProfileAcquisitionSourceKey,
    ProfileAcquisitionSourceV1,
)
from ....core.i18n.render import tr
from ....domain.user_profile.values import ProfileSetupState
from ..components.account_chrome import AccountChromeScreen
from ..components.status import PinnedStatusBar
from ..components.theme import (
    BASE_CSS,
    NOTICE_BAND_CSS,
    install_cadrumo_themes,
    toggle_appearance,
    tokenised,
)
from ..components.widgets import (
    ContentScroll,
    DisclosureGroup,
)
from .overview_contracts import (
    _COMPLETE_SETUP_ACTION,
    _COMPLETE_SETUP_KEY,
    _CONTINUE_BUTTON_ID,
    _LANGUAGE_ACTION,
    _LANGUAGE_KEY,
    _REQUIRED_ONLY_ID,
    _SEARCH_ID,
)
from .overview_interactions import ProfileOverviewInteractionMixin
from .overview_rendering import ProfileOverviewRenderingMixin
from .overview_setup import (
    ProfileOverviewCompletionMixin,
    ProfileOverviewSetupNavigationMixin,
    ProfileOverviewSetupRenderMixin,
    ProfileOverviewSetupWalkMixin,
)
from .overview_writes import ProfileOverviewWriteMixin
from .setup_journey import SETUP_STAGES, ProfileSetupStage

if TYPE_CHECKING:
    from collections.abc import Mapping
    from decimal import Decimal

    from textual.timer import Timer
    from textual.widgets.data_table import ColumnKey

    from ....application.user_profile.overview import ProfileFieldView, ProfileOverview
    from ....domain.user_profile.plantilla_media import PlantillaMediaState, PlantillaMediaYear


type ProfileFieldPersist = Callable[[str, str, int, str], ProfileOverview]
"""The one-field write door: path, value, and the revision and digest the edit was made against."""


"""The profile field deciding what language this page is written in.

Named here because the page reaches for it directly, which it does for no
other field: changing it changes every label on screen including the ones
that would lead an operator to it.
"""


class ProfileManagerScreen(
    ProfileOverviewInteractionMixin,
    ProfileOverviewSetupNavigationMixin,
    ProfileOverviewSetupRenderMixin,
    ProfileOverviewSetupWalkMixin,
    ProfileOverviewCompletionMixin,
    ProfileOverviewWriteMixin,
    ProfileOverviewRenderingMixin,
    AccountChromeScreen,
):
    """Full-screen profile overview with in-place editing."""

    SCOPED_CSS = False
    DEFAULT_CSS = (
        BASE_CSS
        + NOTICE_BAND_CSS
        + """
    #manager-context { width: 100%; height: auto; }
    #manager-requirements { width: 100%; height: auto; }
    .manager-section DataTable { height: auto; width: 100%; background: $surface; }
    """
        + tokenised("""
    #manager-onboarding { height: auto; padding: $cadrumo-space-0 $cadrumo-gutter; }
    #onboarding-heading { text-style: bold; }
    #onboarding-actions { height: auto; }
    #onboarding-continue { width: auto; }
    #onboarding-previous { width: auto; margin-right: $cadrumo-control-gap; }
    #onboarding-step {
        width: 1fr;
        height: auto;
        padding-left: $cadrumo-control-gap;
        content-align: left middle;
    }
    #onboarding-progress { width: 100%; }
    #onboarding-progress Bar { width: 1fr; }
    #onboarding-stages { height: auto; }
    #onboarding-stages Button { width: 1fr; min-width: 0; }
    #onboarding-stages .setup-current { text-style: bold; background: $primary; color: $background; }
    #onboarding-stage-title { text-style: bold; height: auto; }
    #onboarding-stage-copy { height: auto; margin-bottom: $cadrumo-space-1; }
    #onboarding-checklist { height: auto; color: $text-muted; margin-bottom: $cadrumo-space-1; }
    #onboarding-stage-title.setup-success { color: $success; }
    #onboarding-stage-title, #onboarding-stage-copy, #onboarding-checklist, #manager-edit-intro {
        padding-left: $cadrumo-gutter;
        padding-right: $cadrumo-gutter;
    }
    #manager-tools { height: auto; padding: $cadrumo-space-0 $cadrumo-gutter; }
    #manager-search { width: 1fr; }
    #manager-required-only { width: auto; }
    #manager-search-empty { height: auto; }
    .manager-section-summary { color: $text-muted; }
    #manager-field-help {
        dock: bottom;
        height: auto;
        max-height: $cadrumo-help-max-height;
        padding: $cadrumo-space-0 $cadrumo-gutter;
        color: $text-muted;
        background: $surface;
        display: none;
    }
    """)
    )

    BINDINGS: ClassVar = [
        # Shown in the footer, unlike the others. The language of the page
        # is the one setting an operator may need to change before they can
        # read the page well enough to find it, so it cannot be one more
        # row in a table they are struggling with.
        #
        # Neither half of that showing is settled here, though: Textual
        # hides a binding carrying no description, and a description
        # written in a class body would be resolved once at import in
        # whichever language the process started in. Both are written by
        # :meth:`_offer_language_in_footer` on every render instead.
        Binding(_LANGUAGE_KEY, _LANGUAGE_ACTION, "", show=True),
        # After the language key, so the footer reads in key order here as it
        # does on every other destination; described by the account chrome.
        Binding("f3", "toggle_appearance", "", show=False),
        # Named on its own button rather than in the footer, which has no
        # room left for it on an eighty-column terminal.
        Binding(_COMPLETE_SETUP_KEY, _COMPLETE_SETUP_ACTION, "", show=False),
        Binding("slash", "focus_search", "", show=False),
        Binding("q", "quit", "", show=False),
        Binding("escape", "quit", "", show=False),
    ]

    def __init__(
        self,
        overview: ProfileOverview,
        *,
        persist: ProfileFieldPersist,
        add_row: Callable[[str, Mapping[str, str], int, str], ProfileOverview] | None = None,
        update_row: Callable[[str, str, Mapping[str, str], Sequence[str], int, str], ProfileOverview] | None = None,
        remove_row: Callable[[str, str, int, str], ProfileOverview] | None = None,
        complete_setup: Callable[[], ProfileOverview] | None = None,
        validate: Callable[[str, str], str | None] | None = None,
        launch_source: Callable[[ProfileAcquisitionSourceV1], Awaitable[None]] | None = None,
        credential_postures: Sequence[AcquisitionSourceCredentialPostureV1] | None = None,
        open_document_reader: Callable[[], Screen[None]] | None = None,
        list_plantilla_media: Callable[[], Sequence[PlantillaMediaYear]] | None = None,
        set_plantilla_media: Callable[[int, Decimal, PlantillaMediaState], ProfileOverview] | None = None,
        remove_plantilla_media: Callable[[int], ProfileOverview] | None = None,
    ) -> None:
        """Initialize the overview with injected projection and write doors."""
        super().__init__()
        self.overview = overview
        self._open_document_reader = open_document_reader
        """Builds the document reader page, or ``None`` when this host offers none."""
        self._complete_setup = complete_setup
        """Declares setup complete and hands back the page as storage now holds it.

        Injected like ``persist``. The store judges the record at its
        strictest setting and refuses a record still missing a required
        answer, so the page never decides completeness itself. A host that
        supplies none offers no such action at all."""
        self._launch_source = launch_source
        """Starts one declared acquisition source's operation, or ``None``.

        Injected exactly like ``persist``: this page names which source the
        operator picked and reports the intent, it does not compose an
        ``OperationController`` or know how a source actually runs. A host
        that supplies none renders every source action as present but
        disabled, never as a silent no-op button."""
        self._credential_postures: dict[ProfileAcquisitionSourceKey, AcquisitionSourceCredentialPostureV1] = {
            posture.source: posture for posture in (credential_postures or ())
        }
        """Whether each source's declared AEAT-authentication requirement is
        currently met, keyed by source. Injected from
        ``resolve_acquisition_source_credential_postures`` against the
        real :class:`AuthState`, never guessed here. A host that supplies
        none renders every source without a credential badge -- an unknown
        posture is not the same claim as "credential missing"."""
        self._validate_field = validate
        """Why the write door would refuse one path's value, or ``None``.

        Injected beside the write door and from the same authority, so the
        dialog refuses exactly what storage would refuse. A host that
        supplies none leaves every box unchecked until the write — which is
        where the refusal used to arrive, unhelpfully."""
        self._persist_field = persist
        """Writes one field and hands back the page as storage now holds it.

        Injected, not imported: the adapter tier renders a view-model and
        reports intents, exactly as the status page does. Returning the
        reloaded overview rather than ``None`` is what keeps the screen
        from ever displaying its own optimistic guess — whatever the store
        made of the value is what appears."""
        self._add_row = add_row
        self._update_row = update_row
        self._remove_row = remove_row
        """Shared repeatable-row doors, bound by composition to one profile.

        Calls carry the overview baseline captured when the dialog opened;
        completion never substitutes whichever profile happens to be visible.
        """
        self._list_plantilla_media = list_plantilla_media
        self._set_plantilla_media = set_plantilla_media
        self._remove_plantilla_media = remove_plantilla_media
        """Average-workforce doors, bound by composition to one profile.

        A year is its own identity, so these take the year rather than a
        row key or an overview baseline: the application service reads the
        record once and compare-and-swaps against that read. The writes hand
        back the page as storage now holds it, like every other door here,
        so the page and its revision never go stale behind a declared year.
        """
        self._pending_listing: Worker[tuple[PlantillaMediaYear, ...]] | None = None
        """The in-flight read of the declared years, or ``None``.

        Read off the event loop for the reason writes are: it decrypts the
        record. At most one runs, so a double press opens one dialog."""
        self._field_by_key: dict[str, ProfileFieldView] = {}
        self._table_by_section: dict[str, DataTable[str]] = {}
        """The live table per section, so a single-field edit can address a
        cell instead of rebuilding the widget tree.

        Repopulated by every full render, which is the only thing that
        replaces these widgets; an entry here is therefore always the table
        currently mounted for that section."""
        self._columns_by_section: dict[str, list[ColumnKey]] = {}
        """Column keys as ``add_columns`` handed them back, per section.

        ``update_cell`` addresses a cell by (row key, column key), and the
        row key is already the field path. Retaining the column keys is the
        only missing half of that coordinate."""
        self._pending_write: Worker[ProfileOverview] | None = None
        """The one in-flight field write, or ``None`` when storage is idle.

        Writes are serialised rather than overlapped because the door is a
        read-modify-write of the WHOLE fact set: it loads the record, merges
        the new fact into the existing set, and saves the result. Two writes
        in flight together would each merge into the same pre-edit snapshot,
        so the second save would drop the first operator's field. Serialising
        is a correctness requirement here, not a tidiness preference."""
        self._pending_write_path: str | None = None
        """Which field the in-flight write is for, or ``None`` when idle.

        Kept because one field decides how the whole page is worded, so
        settling its write needs a different redraw from every other."""
        self._pending_completion: Worker[ProfileOverview] | None = None
        """The in-flight setup completion, or ``None``.

        Serialised against field writes for the reason those are serialised
        against each other: both replace the whole record."""
        self._onboarding = complete_setup is not None and overview.setup_state is ProfileSetupState.INCOMPLETE
        """Whether this page opened as the setup walk of an unfinished profile.

        Fixed at construction so the walk's header stays in place after the
        last step, where it hands the operator on to the workbench."""
        self._setup_stage = ProfileSetupStage.OVERVIEW
        self._sources_skipped = False
        self._required_only = self._onboarding
        """Whether sections show only the answers setup requires right now."""
        self._query = ""
        """The operator's search text; empty shows every field the filter allows."""
        self._search_timer: Timer | None = None
        self._walking = False
        """Whether Continue is leading the operator from one required answer to the next.

        Set when Continue opens a question and cleared as soon as the
        operator cancels, a save is refused, or nothing required is left, so
        a later unrelated edit never reopens the walk by surprise."""
        self._render_lock = asyncio.Lock()
        """Serialises every rebuild of the section tables.

        A search, a settled write and a language change each rebuild tables
        across several loop turns; two interleaved would mount rows into
        tables the other has already replaced."""

    @override
    def compose(self) -> ComposeResult:
        yield Static(id="manager-banner", classes="cadrumo-banner")
        yield PinnedStatusBar(id="manager-status")
        if self._onboarding:
            # Only what the operator acts on stays pinned: where they are and
            # the one control that moves them on. The explanation scrolls with
            # the page, so a short terminal still has room for the questions.
            with Vertical(id="manager-onboarding"):
                yield Static(id="onboarding-heading", markup=False)
                with Horizontal(id="onboarding-stages"):
                    for stage in SETUP_STAGES:
                        yield Button("", id=f"setup-stage-{stage.value}", compact=True)
                yield ProgressBar(id="onboarding-progress", show_eta=False, show_percentage=False)
                with Horizontal(id="onboarding-actions"):
                    yield Button("", id="onboarding-previous", compact=True)
                    yield Button("", id=_CONTINUE_BUTTON_ID, classes="-primary", compact=True)
                    yield Static(id="onboarding-step", markup=False)
        with Horizontal(id="manager-tools"):
            yield Input(id=_SEARCH_ID, compact=True)
            yield Checkbox("", value=self._required_only, id=_REQUIRED_ONLY_ID, compact=True)
        with ContentScroll(id="manager-body", classes="cadrumo-scroll"), Vertical(classes="cadrumo-column"):
            if self._onboarding:
                yield Static(id="onboarding-stage-title", markup=False)
                yield Static(id="onboarding-stage-copy", markup=False)
                yield Static(id="onboarding-checklist", markup=False)
            else:
                yield Static(tr("flows.manager.setup.edit_intro"), id="manager-edit-intro", markup=False)
            yield Vertical(id="manager-context")
            yield Static(id="manager-search-empty", classes="cadrumo-note", markup=False)
            # Filled by :meth:`_redraw`, not here: a card's text is fixed when
            # it is built, so cards composed once would keep the language the
            # page opened in after the operator changes it.
            with DisclosureGroup(title="", id="manager-sources-fold"):
                yield Static(id="manager-sources-summary", classes="manager-section-summary", markup=False)
                yield Vertical(id="manager-sources", classes="cadrumo-panel")
            missing = frozenset(self.overview.missing_required)
            for section in self.overview.sections:
                # Only a section still owing a required answer starts open.
                # Decided here rather than on render: a fold that opens scrolls
                # itself into view, which would open the page mid-way down.
                owing = any(field.path in missing for field in section.fields)
                with DisclosureGroup(title="", collapsed=not owing, id=f"fold-{section.key}"):
                    yield Static(id=f"summary-{section.key}", classes="manager-section-summary", markup=False)
                    yield Static(id=f"section-{section.key}", classes="manager-section cadrumo-panel")
        # Explains whichever row the cursor is on, so the page answers "what
        # is this and where do I find it" without opening anything.
        yield Static(id="manager-field-help", markup=False)
        yield Footer()

    async def on_mount(self) -> None:
        """Install the presentation theme and render the supplied overview."""
        install_cadrumo_themes(self.app)
        # The shared theme sizes every Input to the full row, which would push
        # the required-only switch beside the search box off the screen.
        self.query_one(f"#{_SEARCH_ID}", Input).styles.width = "1fr"
        if self._onboarding:
            for stage in SETUP_STAGES:
                button = self.query_one(f"#setup-stage-{stage.value}", Button)
                button.styles.width = f"{100 / len(SETUP_STAGES):g}%"
                button.styles.min_width = 0
                button.styles.border = ("none", "transparent")
                button.styles.height = 1
        await self._redraw()
        if self._onboarding:
            self.query_one(f"#{_CONTINUE_BUTTON_ID}", Button).focus()
        # Whatever took focus while the page was building may have scrolled
        # the body; the page opens at its top.
        body = self.query_one("#manager-body", ContentScroll)
        self.call_after_refresh(body.scroll_home, animate=False, immediate=True)

    # ── rendering ───────────────────────────────────────────────────────

    # ── editing ─────────────────────────────────────────────────────────

    # ── setup walk ──────────────────────────────────────────────────────

    # ── search and filters ──────────────────────────────────────────────

    # ── setup completion ────────────────────────────────────────────────

    @override
    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        """Hide the completion key once there is nothing to complete."""
        if action == _COMPLETE_SETUP_ACTION:
            return self._completion_offered
        return super().check_action(action, parameters)

    async def action_quit(self) -> None:
        """Leave the manager, unless a field write is still landing.

        A thread-backed write cannot be cancelled safely: quitting would only
        detach its result while encrypted storage may still complete the
        save, so the operator would leave believing an edit was lost that in
        fact landed. Waiting for the one in-flight write is the honest
        behaviour, and it is bounded by a single storage round trip.

        """
        if self._pending_write is not None or self._pending_completion is not None:
            self._refuse(tr("flows.manager.edit.write_in_flight"))
            return
        self.dismiss(None)

    def action_toggle_appearance(self) -> None:
        """Flip between the light and dark appearance."""
        toggle_appearance(self.app)


__all__ = [
    "ProfileFieldPersist",
    "ProfileManagerScreen",
]
