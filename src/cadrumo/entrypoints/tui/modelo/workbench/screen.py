"""The modelo editor workbench: one screen to fill in, calculate, check and record a declaration.

The screen shows one declaration at a time. A three-line header, always in
view, names the modelo, the period and the deadline; states the result in the
filer's words with what needs their attention; and places the declaration on
the filing journey with the one thing to do next. A navigator lists the
official pages and their sections with what each still needs, folding finished
pages away; the casilla list shows the current page, or the whole declaration
sorted another way; and a help band explains the casilla under the cursor --
its words, where its value comes from, what may be done about it, and, once
loaded, its formula, official text and legal basis. Enter opens the box's
panel in the help band's place, with the list still in view above it, and
keeping a value there moves the list on and refills the panel for the next
box; on a terminal too short for both, the panel opens as a centred dialog
instead. ``/`` searches every page, ``g`` goes to a box by number, and ``?``
names the symbols on screen, then opens every symbol and key. ``b`` confirms the assumed values of the section
under the cursor, or of the page, together; never the whole declaration at once.

A page that does not apply this period is dimmed, says so and asks nothing of
the filer. A declaration recorded as filed says so wherever a box is explained,
counts nothing as to do, and offers no key that would change it. While a value
nobody entered is still assumed, nothing reaches the AEAT and no filing is
recorded: ``e`` and F8 say why and offer the assumed values to confirm.

The screen resolves nothing itself. It reads through the port the composition
root hands it, off the event loop, and keeps only presentation state: the page
shown, the filter, the order, the folded pages, the density and the cursor,
which it holds by casilla address so a refresh or a language switch lands on
the same box.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from functools import partial
from typing import ClassVar, override

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import OptionList, Static

from .....application.modelo.casilla_help import ModeloCasillaHelpCardV1
from .....application.modelo.work_form_models import (
    ModeloFormCasillaAddressV1,
    ModeloWorkForm,
    address_key,
    section_fields,
)
from .....application.modelo.work_form_service import ModeloWorkFormLoadV1
from .....core.external_constants import OutputLanguage
from .....core.i18n.render import output_language, tr
from .....core.logging import get_logger
from ...components.account_chrome import AccountChromeScreen
from ...components.theme import toggle_appearance, tokenised
from ...navigation import TuiNavigationTargetV1
from .casilla_list import (
    CasillaList,
)
from .casilla_list_models import (
    AddressKey,
    CasillaListEntry,
    Density,
)
from .editor import (
    CasillaEditorPanel,
)
from .legend import first_open_text, mark_for_glyph
from .navigator import (
    NavigatorState,
    inapplicable_pages,
    presented_form,
)
from .page_items import (
    WorkbenchFilter,
    WorkbenchPage,
    page_items,
    page_of,
    workbench_pages,
)
from .ports import (
    ModeloWorkbenchActionsV1,
    ModeloWorkbenchReaderV1,
    WorkbenchApplyPrerequisite,
)
from .screen_confirmation import WorkbenchConfirmationMixin
from .screen_constants import (
    _GREETED,
)
from .screen_editor import WorkbenchEditorMixin
from .screen_footer import WorkbenchFooterMixin
from .screen_help import WorkbenchHelpMixin
from .screen_help_content import WorkbenchHelpContentMixin
from .screen_navigation import WorkbenchNavigationMixin
from .screen_next_step import WorkbenchNextStepMixin
from .screen_operation import WorkbenchOperationMixin
from .screen_presentation import WorkbenchPresentationMixin
from .screen_review import WorkbenchReviewMixin
from .screen_widgets import NoticeLine, SymbolsPanel
from .search import WorkbenchSearchPanel
from .session import StagedChange, WorkbenchEditSession
from .sorting import SortOrder
from .vocabulary import (
    ATTENTION_MARKS,
    HERE_MARK,
    WorkbenchMark,
)
from .wording import does_not_apply_text


class ModeloWorkbenchScreen(
    WorkbenchFooterMixin,
    WorkbenchPresentationMixin,
    WorkbenchHelpMixin,
    WorkbenchHelpContentMixin,
    WorkbenchNavigationMixin,
    WorkbenchEditorMixin,
    WorkbenchConfirmationMixin,
    WorkbenchReviewMixin,
    WorkbenchNextStepMixin,
    WorkbenchOperationMixin,
    AccountChromeScreen,
):
    """One declaration's workbench."""

    DEFAULT_CSS: ClassVar[str] = tokenised(
        """
        ModeloWorkbenchScreen #wb-header {
            width: 1fr;
            height: $cadrumo-band-height;
        }
        ModeloWorkbenchScreen #wb-identity {
            /* A neutral title bar beneath the account bar: the result, not the title, carries the emphasis. */
            dock: top;
            height: $cadrumo-band-height;
            width: 100%;
            margin-top: $cadrumo-band-height;
            padding: $cadrumo-space-0 $cadrumo-gutter;
            background: $panel;
            color: $foreground;
            text-style: bold;
        }
        ModeloWorkbenchScreen #wb-header {
            color: $foreground;
            text-style: bold;
        }
        ModeloWorkbenchScreen #wb-deadline {
            width: auto;
            height: $cadrumo-band-height;
            padding: $cadrumo-space-0 $cadrumo-space-1;
            background: $panel;
            color: $foreground;
        }
        ModeloWorkbenchScreen #wb-deadline.-soon {
            color: $warning;
        }
        ModeloWorkbenchScreen #wb-deadline.-urgent {
            color: $error;
        }
        ModeloWorkbenchScreen #wb-deadline.-muted {
            color: $secondary;
            text-style: none;
        }
        ModeloWorkbenchScreen.-identity-stacked #wb-identity {
            layout: vertical;
            height: auto;
        }
        ModeloWorkbenchScreen.-identity-stacked #wb-header,
        ModeloWorkbenchScreen.-identity-stacked #wb-deadline {
            width: 100%;
            height: auto;
        }
        ModeloWorkbenchScreen.-identity-stacked #wb-deadline {
            padding: $cadrumo-space-0;
        }
        ModeloWorkbenchScreen #wb-status {
            height: auto;
            padding: $cadrumo-space-0 $cadrumo-gutter;
            background: $surface;
        }
        ModeloWorkbenchScreen .wb-line {
            height: auto;
        }
        ModeloWorkbenchScreen #wb-result {
            width: auto;
            color: $foreground;
            text-style: bold;
        }
        ModeloWorkbenchScreen #wb-result.-to-pay {
            color: $warning;
        }
        ModeloWorkbenchScreen #wb-result.-to-pay.-overdue {
            color: $error;
        }
        ModeloWorkbenchScreen #wb-result.-stale {
            text-style: dim;
        }
        ModeloWorkbenchScreen #wb-stale {
            width: auto;
            margin: $cadrumo-space-0 $cadrumo-space-0 $cadrumo-space-0 $cadrumo-section;
            color: $warning;
        }
        ModeloWorkbenchScreen #wb-file {
            width: auto;
            margin: $cadrumo-space-0 $cadrumo-space-0 $cadrumo-space-0 $cadrumo-section;
            color: $foreground;
        }
        ModeloWorkbenchScreen #wb-file.-out-of-date {
            color: $warning;
        }
        ModeloWorkbenchScreen #wb-chips {
            width: 1fr;
            margin: $cadrumo-space-0 $cadrumo-space-0 $cadrumo-space-0 $cadrumo-section;
        }
        ModeloWorkbenchScreen #wb-marks {
            width: 1fr;
            height: auto;
        }
        ModeloWorkbenchScreen.-outcome-stacked #wb-outcome {
            layout: vertical;
        }
        ModeloWorkbenchScreen #wb-stale.-leading,
        ModeloWorkbenchScreen #wb-file.-leading,
        ModeloWorkbenchScreen #wb-chips.-leading {
            /* First on its line, it starts where the lines above and below start. */
            margin: $cadrumo-space-0;
        }
        ModeloWorkbenchScreen #wb-stepper {
            width: auto;
        }
        ModeloWorkbenchScreen #wb-next {
            width: 1fr;
            margin: $cadrumo-space-0 $cadrumo-space-0 $cadrumo-space-0 $cadrumo-section;
            color: $foreground;
            text-style: bold;
            text-wrap: nowrap;
            text-overflow: ellipsis;
        }
        ModeloWorkbenchScreen #wb-next.-confirm {
            color: $warning;
        }
        ModeloWorkbenchScreen #wb-next.-resolve {
            color: $error;
        }
        ModeloWorkbenchScreen.-next-below #wb-steps {
            layout: vertical;
        }
        ModeloWorkbenchScreen.-next-below #wb-next {
            margin: $cadrumo-space-0;
        }
        ModeloWorkbenchScreen #wb-notice {
            height: auto;
            color: $warning;
        }
        ModeloWorkbenchScreen #wb-legend {
            height: 1fr;
            display: none;
            padding: $cadrumo-space-0 $cadrumo-gutter;
            background: $background;
        }
        ModeloWorkbenchScreen.-legend #wb-legend {
            display: block;
        }
        ModeloWorkbenchScreen.-legend #wb-body {
            display: none;
        }
        ModeloWorkbenchScreen.-legend #wb-help {
            display: none;
        }
        ModeloWorkbenchScreen #wb-body {
            height: 1fr;
        }
        ModeloWorkbenchScreen #wb-sections {
            width: 1fr;
            height: 1fr;
            border: none;
            border-right: $cadrumo-rule $panel;
            background: $background;
        }
        ModeloWorkbenchScreen.-narrow #wb-sections {
            display: none;
        }
        ModeloWorkbenchScreen #wb-main {
            width: 3fr;
            height: 1fr;
        }
        ModeloWorkbenchScreen #wb-crumb {
            height: auto;
            display: none;
            padding: $cadrumo-space-0 $cadrumo-space-1;
            color: $secondary;
        }
        ModeloWorkbenchScreen.-narrow #wb-crumb {
            display: block;
        }
        ModeloWorkbenchScreen.-narrow #wb-page {
            display: none;
        }
        ModeloWorkbenchScreen #wb-page {
            height: $cadrumo-band-height;
            padding: $cadrumo-space-0 $cadrumo-space-1;
            color: $primary;
            text-style: bold;
        }
        ModeloWorkbenchScreen #wb-loading {
            padding: $cadrumo-space-1 $cadrumo-gutter;
            color: $secondary;
        }
        ModeloWorkbenchScreen #wb-search {
            display: none;
        }
        ModeloWorkbenchScreen.-searching #wb-search {
            display: block;
        }
        ModeloWorkbenchScreen.-searching #wb-list {
            display: none;
        }
        ModeloWorkbenchScreen #wb-help {
            height: auto;
            max-height: $cadrumo-help-max-height;
            padding: $cadrumo-space-0 $cadrumo-gutter;
            background: $surface;
            border-top: $cadrumo-rule $panel;
        }
        ModeloWorkbenchScreen.-short #wb-help {
            /* Its rule and one line. */
            max-height: $cadrumo-space-2;
        }
        ModeloWorkbenchScreen #wb-help.-expanded {
            max-height: $cadrumo-help-expanded-max-height;
        }
        ModeloWorkbenchScreen CasillaEditorPanel {
            /* Docked in place of the help band, growing upward over the list. */
            width: 1fr;
            max-height: $cadrumo-editor-dock-max-height;
            padding: $cadrumo-space-0 $cadrumo-gutter;
            border-top: $cadrumo-rule $primary;
        }
        ModeloWorkbenchScreen.-editing #wb-help {
            display: none;
        }
        ModeloWorkbenchScreen.-legend CasillaEditorPanel {
            display: none;
        }
        """
    )

    BINDINGS: ClassVar = [
        Binding("left_square_bracket", "page(-1)", "", show=False),
        Binding("right_square_bracket", "page(1)", "", show=False),
        Binding("f", "cycle_filter", "", show=False),
        Binding("o", "cycle_sort", "", show=False),
        Binding("d", "toggle_density", "", show=False),
        Binding("question_mark,f1", "toggle_help", "", show=False),
        Binding("escape,q", "leave", "", show=False),
        Binding("f3", "toggle_appearance", "", show=False),
        Binding("R", "review", "", show=False),
        Binding("f8", "next_step", "", show=False),
        Binding("c", "calculate", "", show=False),
        Binding("e", "export", "", show=False),
        Binding("i", "issues", "", show=False),
        Binding("b", "bulk_confirm", "", show=False),
        Binding("slash", "search", "", show=False),
        Binding("g", "go_to", "", show=False),
        Binding("left", "fold(0)", "", show=False),
        Binding("right", "fold(1)", "", show=False),
        Binding("space", "fold(-1)", "", show=False),
        # Checked before the list's own keys, so moving to the next thing to
        # do carries on to the next page instead of stopping at this one.
        Binding("n", "next_attention(1)", "", show=False, priority=True),
        Binding("N", "next_attention(-1)", "", show=False, priority=True),
    ]
    _OWN_ACTIONS: ClassVar[frozenset[str]] = frozenset(binding.action.partition("(")[0] for binding in BINDINGS)
    """The workbench's own key actions, which stay quiet while the filer works in the docked box panel."""

    def __init__(
        self,
        reader: ModeloWorkbenchReaderV1,
        *,
        actions: ModeloWorkbenchActionsV1 | None = None,
        navigate: Callable[[TuiNavigationTargetV1], None] | None = None,
        id: str | None = None,
    ) -> None:
        """Hold the ports this workbench reads and acts through, and how it opens another product area.

        Without ``navigate`` the workbench opens another area through the root
        host it runs in, when that host can navigate.
        """
        super().__init__(id=id)
        self._reader = reader
        self._actions = actions
        self._navigate = navigate
        self._operation_in_flight = False
        self._apply_prerequisite: WorkbenchApplyPrerequisite | None = None
        self._load: ModeloWorkFormLoadV1 | None = None
        self._pages: tuple[WorkbenchPage, ...] = ()
        self._inapplicable: frozenset[str] = frozenset()
        self._density_chosen: Density | None = None
        self._explained: CasillaListEntry | None = None
        self._page_index = 0
        self._filter = WorkbenchFilter.ALL
        self._sort = SortOrder.FORM
        self._navigator = NavigatorState()
        self._legend_level = 0
        self._next_words = ""
        self._drawn: dict[str, tuple[WorkbenchMark, ...]] = {}
        self._cards: dict[tuple[str, OutputLanguage], ModeloCasillaHelpCardV1] = {}
        self._help_generation = 0
        self._language = OutputLanguage(output_language())
        self._session = WorkbenchEditSession(self._language)
        self._docked: tuple[CasillaListEntry, CasillaEditorPanel] | None = None

    # ── composition ─────────────────────────────────────────────────────

    @override
    def compose(self) -> ComposeResult:
        with Horizontal(id="wb-identity"):
            yield Static(id="wb-header", markup=False)
            yield Static(id="wb-deadline", markup=False)
        with Vertical(id="wb-status"):
            with Horizontal(id="wb-outcome", classes="wb-line"):
                yield Static(id="wb-result", markup=False)
                with Horizontal(id="wb-marks", classes="wb-line"):
                    yield Static(id="wb-stale", markup=False)
                    yield Static(id="wb-file", markup=False)
                    yield Static(id="wb-chips", markup=False)
            with Horizontal(id="wb-steps", classes="wb-line"):
                yield Static(id="wb-stepper", markup=False)
                yield Static(id="wb-next", markup=False)
            notice = NoticeLine(id="wb-notice", markup=False)
            notice.display = False
            yield notice
        with SymbolsPanel(id="wb-legend"):
            yield Static(id="wb-legend-text", markup=False)
        with Horizontal(id="wb-body"):
            yield OptionList(id="wb-sections")
            with Vertical(id="wb-main"):
                yield Static(id="wb-crumb", markup=False)
                yield Static(id="wb-page", markup=False)
                yield Static(tr("tui.modelo.workbench.loading"), id="wb-loading", markup=False)
                yield WorkbenchSearchPanel(id="wb-search")
                yield CasillaList(language=self._language, id="wb-list")
        yield Static(id="wb-help", markup=False)

    def on_mount(self) -> None:
        """Describe the keys and read the declaration."""
        self._describe_keys()
        self._apply_width(self.size.width)
        self._apply_height(self.size.height or self.app.size.height)
        self.run_worker(self._read, group="workbench-read", exclusive=True)

    def on_resize(self, event: events.Resize) -> None:
        """Fold the navigator away on narrow terminals and shorten the header to fit."""
        self._apply_width(event.size.width)
        self._apply_height(event.size.height)
        self._render_header()
        self._render_progress()
        self._describe_keys()
        self.call_after_refresh(self._render_navigator)
        self.call_after_refresh(self._rewrap_help)

    @override
    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        """Keep the workbench's own keys from acting while the filer works in the docked box panel.

        The panel takes its own keys first; a key it leaves, such as ``q`` on
        one of its buttons, must not leave the workbench or open another view
        under the filer's hands. With the cursor back in the list, every key
        acts again.
        """
        if action in self._OWN_ACTIONS and self._working_in_dock():
            return False
        return super().check_action(action, parameters)

    def on_key(self, event: events.Key) -> None:
        """Take the first-open notice away at the filer's first keypress."""
        del event
        notice = self.query_one("#wb-notice", Static)
        if str(notice.render()) == first_open_text():
            notice.update("")

    # ── reading ─────────────────────────────────────────────────────────

    @property
    def form(self) -> ModeloWorkForm | None:
        """The form currently shown, once read."""
        return None if self._load is None else self._load.form

    @property
    def staged_changes(self) -> tuple[StagedChange, ...]:
        """The changes the filer has staged and not yet applied or discarded."""
        return self._session.changes

    @property
    def recorded(self) -> bool:
        """Whether the declaration is recorded as filed, so it is only read here."""
        load = self._load
        return load is not None and (load.filed or load.form.filing is not None)

    @property
    def pages_shown(self) -> tuple[WorkbenchPage, ...]:
        """The pages as the navigator shows them, under words a filer reads."""
        return self._pages

    @property
    def box_order(self) -> SortOrder:
        """How the boxes are ordered now."""
        return self._sort

    @property
    def box_marks(self) -> tuple[WorkbenchMark, ...]:
        """The states of the boxes the list shows, once per box: its origin and any attention mark."""
        marks: list[WorkbenchMark] = []
        for item in self.query_one(CasillaList).items:
            if isinstance(item, CasillaListEntry):
                glyph = item.origin_mark
                if glyph.strip():
                    marks.append(mark_for_glyph(glyph))
                attention = item.attention
                if attention is not None:
                    marks.append(ATTENTION_MARKS[attention])
        return tuple(marks)

    @property
    def other_marks(self) -> tuple[WorkbenchMark, ...]:
        """Every mark on screen that is not a box's state: the header's, the stepper's, the navigator's, the cursor."""
        marks: list[WorkbenchMark] = [mark for part in self._drawn.values() for mark in part]
        if self.query_one(CasillaList).highlighted is not None:
            marks.append(HERE_MARK)
        return tuple(marks)

    async def _read(self) -> None:
        try:
            load = await asyncio.to_thread(self._reader.load, self._language)
        except Exception as failure:
            get_logger(__name__).error(
                "modelo workbench could not read its declaration: %s", type(failure).__qualname__, exc_info=True
            )
            self.query_one("#wb-loading", Static).update(tr("tui.modelo.workbench.read_failed"))
            return
        self.show_load(load)

    def show_load(self, load: ModeloWorkFormLoadV1) -> None:
        """Show a fresh read, keeping the page and the casilla under the cursor where they still exist."""
        previous_page = self._pages[self._page_index].id if self._pages else None
        self._help_generation += 1
        self._cards.clear()
        self._load = load
        self._pages = workbench_pages(presented_form(load.form, recorded=self.recorded))
        self._inapplicable = inapplicable_pages(load.form)
        page_ids = [page.id for page in self._pages]
        if previous_page in page_ids:
            self._page_index = page_ids.index(previous_page)
        else:
            attention = self._first_attention()
            self._page_index = 0 if attention is None else attention[0]
        loading = self.query("#wb-loading")
        for widget in loading:
            widget.remove()
        # A docked panel describes the box as it was read; a fresh read closes it.
        self._close_dock(refocus=False)
        self._render_all()
        self._describe_keys()
        if previous_page is None:
            attention = self._first_attention()
            if attention is not None and attention[0] == self._page_index:
                self.query_one(CasillaList).focus_address(attention[1])
            self._greet()
        self.query_one(CasillaList).focus()

    def _applies(self, index: int) -> bool:
        """Whether the page at ``index`` applies this period; the calculation details always do."""
        return self._pages[index].id not in self._inapplicable

    def _not_applying_text(self) -> str:
        form = self.form
        return "" if form is None else does_not_apply_text(form.period)

    def _first_attention(self) -> tuple[int, AddressKey] | None:
        """The first box that needs the filer, on a page that applies this period; none once recorded as filed."""
        if self.recorded:
            return None
        staged = self._session.display()
        for index, page in enumerate(self._pages):
            if not self._applies(index):
                continue
            for item in page_items(page, staged=staged):
                if isinstance(item, CasillaListEntry) and item.needs_filer:
                    return index, item.key
        return None

    def _greet(self) -> None:
        """Say once per session, on the notice line, where to find what the symbols mean.

        A short terminal keeps that line for the boxes: there ``?`` still says
        what each symbol means.
        """
        app = self.app
        if app in _GREETED or self.has_class("-short"):
            return
        _GREETED.add(app)
        notice = self.query_one("#wb-notice", Static)
        if not str(notice.render()):
            notice.update(first_open_text())

    # ── rendering ───────────────────────────────────────────────────────

    # ── help ────────────────────────────────────────────────────────────

    # ── navigation ──────────────────────────────────────────────────────

    def on_option_list_option_selected(self, message: OptionList.OptionSelected) -> None:
        """Open the page or section chosen in the navigator."""
        if message.option_list.id != "wb-sections":
            return
        option_id = message.option.id or ""
        kind, _, rest = option_id.partition(":")
        page_text, _, section_id = rest.partition(":")
        if not page_text.isdigit():
            return
        self._sort = SortOrder.FORM
        self._show_page(int(page_text))
        if kind == "section":
            page = self._pages[self._page_index]
            section = next((item for item in page.sections if item.id == section_id), None)
            if section is not None:
                fields = section_fields(section)
                if fields:
                    self.query_one(CasillaList).focus_address(address_key(fields[0].address))
        self.query_one(CasillaList).focus()

    # ── editing ─────────────────────────────────────────────────────────

    def _open_editor(self, entry: CasillaListEntry) -> None:
        field = entry.field
        actions = self._actions
        form = self.form
        recorded = self.recorded
        if actions is None or form is None or not (recorded or form.edit_admitted):
            self._edit_unavailable()
            return
        if self._held_card(field) is None and isinstance(field.address, ModeloFormCasillaAddressV1):
            # The panel says what a change to this box reaches, which only the full help knows: read it first.
            self.run_worker(partial(self._open_editor_once_explained, entry), group="workbench-editor", exclusive=True)
            return
        self._push_editor(entry, actions, self._held_card(field))

    async def _open_editor_once_explained(self, entry: CasillaListEntry) -> None:
        generation = self._help_generation
        card = await self._card_for(entry.field)
        if generation != self._help_generation:
            return
        actions = self._actions
        if actions is not None:
            self._push_editor(entry, actions, card)

    def _go_to(self, key: AddressKey) -> None:
        casilla_list = self.query_one(CasillaList)
        if self._sort is not SortOrder.FORM:
            if casilla_list.focus_address(key):
                casilla_list.focus()
                self.call_after_refresh(casilla_list.reveal_highlighted)
                return
            self._sort = SortOrder.FORM
        index = page_of(self._pages, key)
        if index is None:
            return
        self._show_page(index)
        if not casilla_list.focus_address(key):
            self._filter = WorkbenchFilter.ALL
            self._render_page()
            casilla_list.focus_address(key)
        casilla_list.focus()
        self.call_after_refresh(casilla_list.reveal_highlighted)

    # ── lifecycle ───────────────────────────────────────────────────────

    def action_toggle_appearance(self) -> None:
        """Switch between the two shipped appearances."""
        toggle_appearance(self.app)


__all__ = ["ModeloWorkbenchScreen"]
