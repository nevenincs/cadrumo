"""The modelo editor workbench: one screen to fill in, calculate, check and record a declaration.

The screen shows one declaration at a time. A three-line header, always in
view, names the modelo, the period and the deadline; states the result in the
filer's words with what needs their attention; and places the declaration on
the filing journey with the one thing to do next. A navigator lists the
official pages and their sections with what each still needs, folding finished
pages away; the casilla list shows the current page, or the whole declaration
sorted another way; and a help band explains the casilla under the cursor --
its words, where its value comes from, what may be done about it, and, once
loaded, its formula, official text and legal basis. ``/`` searches every page,
``g`` goes to a box by number, and ``?`` names the symbols on screen, then
opens every symbol and key. ``b`` confirms the assumed values of the section
under the cursor, or of the page, together; never the whole declaration at once.

A page that does not apply this period is dimmed, says so and asks nothing of
the filer. A declaration recorded as filed says so wherever a box is explained,
counts nothing as to do, and offers no key that would change it.

The screen resolves nothing itself. It reads through the port the composition
root hands it, off the event loop, and keeps only presentation state: the page
shown, the filter, the order, the folded pages, the density and the cursor,
which it holds by casilla address so a refresh or a language switch lands on
the same box.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from functools import partial
from typing import TYPE_CHECKING, ClassVar, Final, override
from weakref import WeakSet

from rich.cells import cell_len
from textual import events
from textual.actions import SkipAction
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from .....application.modelo.action_errors import ModeloEditBaselineStaleError
from .....application.modelo.casilla_help import ModeloCasillaHelpCardV1
from .....application.modelo.operation_definitions import (
    MODELO_EDIT_APPLY_OPERATION_DEFINITION_ID,
    MODELO_EXPORT_OPERATION_DEFINITION_ID,
    MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID,
    MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID,
)
from .....application.modelo.work_form_models import (
    ModeloFormAddressV1,
    ModeloFormCasillaAddressV1,
    ModeloFormField,
    ModeloFormLayoutProvenance,
    ModeloFormOrigin,
    ModeloFormResultDirection,
    ModeloFormTextDisclosure,
    ModeloWorkForm,
    address_key,
    confirmable,
    edit_address,
    section_fields,
)
from .....application.modelo.work_form_service import ModeloWorkFormLoadV1, modelo_work_form_changes
from .....core.errors.error_codes import resolve_error_message
from .....core.errors.hierarchy import CadrumoError
from .....core.external_constants import OutputLanguage
from .....core.i18n.render import lookup_translation, output_language, tr
from .....core.logging import get_logger
from .....core.operations import OperationTerminalCondition
from .....domain.modelos.verification_report import VerificationCompletenessStatus
from ...components.account_chrome import AccountChromeScreen
from ...components.dialogs import ConfirmScreen
from ...components.theme import CADRUMO_CSS_TOKENS, toggle_appearance, tokenised
from ...navigation import TuiNavigationTargetV1
from ...operations.controller import OperationController
from ...operations.refusal_explanation import public_refusal_explanation
from ...search import TuiSearchHostV1
from ..export_result import ModeloExportResultScreen
from ..m303_evidence import OrdinaryM303FilingEvidenceScreen, OrdinaryM303FilingEvidenceSubmission
from .bulk_confirm import BulkConfirmScreen
from .casilla_list import (
    AddressKey,
    CasillaList,
    CasillaListEntry,
    Density,
    description_text,
    grid_cell_title,
    rate_note,
)
from .editor import CasillaEditorScreen, EditorOutcome, read_only_reason
from .export import WorkbenchExportScreen
from .header import (
    DeadlineTone,
    ResultLine,
    attention_chips,
    deadline_help,
    deadline_view,
    fit_identity,
    fit_result_line,
    is_result_field,
    result_line_text,
    result_view,
)
from .issues import WorkbenchIssuesScreen
from .keys import describe_bindings
from .legend import first_open_text, legend_panel, mark_for_glyph, more_text, on_screen_text
from .navigator import (
    NavigatorState,
    breadcrumb,
    checked_boxes,
    inapplicable_pages,
    navigator_rows,
    page_counts,
    presented_form,
    section_of,
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
    WorkbenchChangeKind,
    WorkbenchExportRequest,
    WorkbenchPreflight,
)
from .progress import (
    NextAction,
    fit_next_line,
    next_action_text,
    record_filing_text,
    stepper_marks,
    stepper_text,
    workbench_progress,
)
from .result import WorkbenchResultScreen, result_lines
from .review import EditReviewScreen, ReviewDecision, ReviewNote, recalculation_risk_text
from .search import SearchMode, WorkbenchSearchPanel, search_entries
from .session import Rebase, StagedChange, StageRefusal, WorkbenchEditSession
from .sorting import SORT_LOCALE_KEYS, SortOrder, next_order, sorted_items
from .sources import GoToCasilla, OpenSourceSurface, SourcesChoice, WorkbenchSourcesScreen, surface_target
from .vocabulary import (
    ATTENTION_MARKS,
    HERE_MARK,
    SOURCE_WORDED_ORIGINS,
    TYPED_EDITABILITIES,
    WorkbenchMark,
    attention_words_key,
    editability_text,
    origin_text,
)
from .wording import does_not_apply_text, wrap_words

if TYPE_CHECKING:
    from .....application.operations.frontend_projection import OperationPublicProjectionV1

_NARROW: Final[int] = 110
_SHORT: Final[int] = 30
"""Below this many rows the list shows one line per box and the help band one line, so ten or more boxes fit."""
_GUTTERS: Final[int] = 2 * int(CADRUMO_CSS_TOKENS["cadrumo-gutter"])
_NEXT_GAP: Final[int] = int(CADRUMO_CSS_TOKENS["cadrumo-section"])
_FOOTER_KEY_GAP: Final[int] = 1
_NO_BREAK_SPACE: Final[str] = "\u00a0"
_PALETTE_FRAME: Final[int] = 2
"""The command palette key's rule on its left and its gap on its right, beside its words, in the compact footer."""
_FOOTER_PRIORITY: Final[tuple[str, ...]] = (
    "enter",
    "n",
    "question_mark",
    "escape",
    "f8",
    "R",
    "s",
    "slash",
    "g",
    "o",
    "left_square_bracket",
    "right_square_bracket",
    "f",
    "i",
    "c",
    "e",
    "b",
)
"""Footer keys, most needed first; the footer shows as many as fit and the expanded help names them all."""
_HELP_ONLY_KEYS: Final[tuple[str, ...]] = ("space",)
"""Keys the help and the legend name that the footer never shows."""
_CHANGE_KEYS: Final[frozenset[str]] = frozenset({"R", "b", "c", "f8", "n"})
"""Footer keys that change a declaration or lead to what is left to do; a declaration recorded as filed shows none."""
_ASKS_THE_FILER: Final[frozenset[ModeloFormOrigin]] = frozenset(
    {ModeloFormOrigin.NEEDS_INPUT, ModeloFormOrigin.DEFAULT_TO_CONFIRM}
)
"""Origins whose words ask the filer to act, which a declaration recorded as filed no longer does."""
_NONE_TO_CONFIRM_LOCALE_KEYS: Final[Mapping[bool, str]] = {
    True: "tui.modelo.workbench.bulk_confirm.none_in_section",
    False: "tui.modelo.workbench.bulk_confirm.none_on_page",
}
"""What ``b`` says with nothing assumed in the section under the cursor (``True``) or on the page."""
_VALUE_CHANGING_OPERATIONS: Final[frozenset[str]] = frozenset(
    {str(MODELO_EDIT_APPLY_OPERATION_DEFINITION_ID), str(MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID)}
)
"""Operations after which the workbench shows which boxes now read differently."""
_SELF_REPORTING_OPERATIONS: Final[frozenset[str]] = frozenset(
    {str(MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID), str(MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID)}
)
"""Operations whose notice says what they concluded, read from the declaration once it is read again."""
_NAV_MIN_LABEL: Final[int] = 12
_FRAGMENT_SEPARATOR: Final[str] = " … "
_CHIP_GAP: Final[str] = "   "
_FILTER_ORDER: Final[tuple[WorkbenchFilter, ...]] = (
    WorkbenchFilter.ALL,
    WorkbenchFilter.ATTENTION,
    WorkbenchFilter.MINE,
)
_NEXT_KEYS: Final[Mapping[NextAction, str]] = {
    NextAction.APPLY: "R",
    NextAction.FILL: "n",
    NextAction.CONFIRM: "n",
    NextAction.RESOLVE: "i",
    NextAction.CALCULATE: "F8",
    NextAction.VERIFY: "F8",
    NextAction.EXPORT: "e",
    NextAction.RECORDED: "",
}
_CHECKED_LOCALE_KEYS: Final[Mapping[VerificationCompletenessStatus, str]] = {
    VerificationCompletenessStatus.COMPLETE: "tui.modelo.workbench.operation.checked.complete",
    VerificationCompletenessStatus.INCOMPLETE: "tui.modelo.workbench.operation.checked.incomplete",
    VerificationCompletenessStatus.BLOCKED: "tui.modelo.workbench.operation.checked.blocked",
}
_DEADLINE_TONE_CLASSES: Final[Mapping[DeadlineTone, str]] = {
    DeadlineTone.NORMAL: "-normal",
    DeadlineTone.SOON: "-soon",
    DeadlineTone.URGENT: "-urgent",
    DeadlineTone.MUTED: "-muted",
}
_SCREEN_LOCALE_KEYS: Final[Mapping[str, str]] = {
    "left_square_bracket": "tui.modelo.workbench.key.previous_page",
    "right_square_bracket": "tui.modelo.workbench.key.next_page",
    "f": "tui.modelo.workbench.key.filter",
    "question_mark": "tui.modelo.workbench.key.help",
    "escape": "tui.modelo.workbench.key.back",
    "R": "tui.modelo.workbench.key.review",
    "f8": "tui.modelo.workbench.key.next_step",
    "c": "tui.modelo.workbench.key.calculate",
    "e": "tui.modelo.workbench.key.export",
    "i": "tui.modelo.workbench.key.issues",
    "n": "tui.modelo.workbench.key.next_attention",
    "slash": "tui.modelo.workbench.key.search",
    "g": "tui.modelo.workbench.key.go_to",
    "o": "tui.modelo.workbench.key.sort",
    "b": "tui.modelo.workbench.bulk_confirm.title",
    "space": "tui.modelo.workbench.key.fold",
}
_LIST_LOCALE_KEYS: Final[Mapping[str, str]] = {
    "enter": "tui.modelo.workbench.key.edit",
    "s": "tui.modelo.workbench.key.sources",
}
_CLOSE_LOCALE_KEY: Final[str] = "tui.modelo.workbench.key.close"
_LEGEND_KEYS: Final[frozenset[str]] = frozenset({"escape"})
_SCROLL_LOCALE_KEY: Final[str] = "tui.modelo.workbench.key.scroll"
"""The only keys the footer shows while the symbols panel is open."""
_GREETED: Final[WeakSet[object]] = WeakSet()
"""The applications whose filer has already been told once where to find what the symbols mean."""


class SymbolsPanel(VerticalScroll):
    """The "Symbols and keys" panel, which scrolls with the arrow keys and says so in the footer."""

    BINDINGS: ClassVar = [Binding("up", "scroll_up", "", show=True, key_display="↑↓")]

    def describe_keys(self) -> None:
        """Name the scroll key in the language now on screen."""
        describe_bindings(self._bindings.key_to_bindings, {"up": _SCROLL_LOCALE_KEY})


class ModeloWorkbenchScreen(AccountChromeScreen):
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
        ModeloWorkbenchScreen.-outcome-stacked #wb-stale {
            margin: $cadrumo-space-0;
        }
        ModeloWorkbenchScreen.-outcome-stacked #wb-chips.-leading {
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
        ModeloWorkbenchScreen #wb-banner {
            height: auto;
            display: none;
            color: $warning;
        }
        ModeloWorkbenchScreen.-recorded #wb-banner {
            display: block;
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
        self._language = OutputLanguage(output_language())
        self._session = WorkbenchEditSession(self._language)

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
                    yield Static(id="wb-chips", markup=False)
            with Horizontal(id="wb-steps", classes="wb-line"):
                yield Static(id="wb-stepper", markup=False)
                yield Static(id="wb-next", markup=False)
            yield Static(tr("tui.modelo.workbench.filed.read_only"), id="wb-banner", markup=False)
            yield Static(id="wb-notice", markup=False)
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

    def on_key(self, event: events.Key) -> None:
        """Take the first-open notice away at the filer's first keypress."""
        del event
        notice = self.query_one("#wb-notice", Static)
        if str(notice.render()) == first_open_text():
            notice.update("")

    def _apply_width(self, width: int) -> None:
        self.set_class(width < _NARROW, "-narrow")

    def _apply_height(self, height: int) -> None:
        """On a short terminal show more boxes: one line each, a one-line help band that ``?`` expands."""
        short = 0 < height < _SHORT
        self.set_class(short, "-short")
        if self._density_chosen is None:
            self.query_one(CasillaList).set_density("compact" if short else "comfortable")

    def _width(self) -> int:
        return self.size.width or self.app.size.width

    def _key_label(self, key: str, translation_key: str) -> str:
        own = self._bindings.key_to_bindings.get(key)
        binding = own[0] if own else self.query_one(CasillaList).binding_for(key)
        display = key if binding is None else self.app.get_key_display(binding)
        return f"{display} {tr(translation_key)}"

    def _footer_keys(self, width: int) -> frozenset[str]:
        """The keys the footer can show at ``width``, most needed first, without running under the palette key.

        A declaration recorded as filed shows no key that would change it or
        lead to something left to do.
        """
        descriptions = {**_LIST_LOCALE_KEYS, **_SCREEN_LOCALE_KEYS}
        others = [
            active.binding
            for key, active in self.active_bindings.items()
            if active.binding.show and key not in descriptions
        ]
        budget = (
            width
            - self._palette_cost()
            - sum(
                cell_len(f"{self.app.get_key_display(binding)} {binding.description}") + _FOOTER_KEY_GAP
                for binding in others
            )
        )
        hidden = _CHANGE_KEYS if self.recorded else frozenset()
        shown: set[str] = set()
        for key in _FOOTER_PRIORITY:
            if key in hidden:
                continue
            cost = cell_len(self._key_label(key, descriptions[key])) + _FOOTER_KEY_GAP
            if cost > budget:
                break
            shown.add(key)
            budget -= cost
        return frozenset(shown)

    def _palette_cost(self) -> int:
        """The cells the footer keeps at its right edge for the command palette key, when it shows one."""
        app = self.app
        if not app.ENABLE_COMMAND_PALETTE:
            return 0
        active = self.active_bindings.get(app.COMMAND_PALETTE_BINDING)
        if active is None:
            return 0
        binding = active.binding
        return cell_len(f"{app.get_key_display(binding)} {binding.description}") + _PALETTE_FRAME

    def _describe_keys(self) -> None:
        if self._legend_level == 2:
            # The symbols panel has its own keys: close it, and scroll it.
            describe_bindings(self._bindings.key_to_bindings, _SCREEN_LOCALE_KEYS, shown=_LEGEND_KEYS)
            describe_bindings(self._bindings.key_to_bindings, {"escape": _CLOSE_LOCALE_KEY}, shown=_LEGEND_KEYS)
            self.query_one(SymbolsPanel).describe_keys()
            self.refresh_bindings()
            return
        shown = self._footer_keys(self._width())
        describe_bindings(self._bindings.key_to_bindings, _SCREEN_LOCALE_KEYS, shown=shown)
        self.query_one(CasillaList).describe_keys(_LIST_LOCALE_KEYS, shown=shown)
        self.refresh_bindings()

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
    def drawn_marks(self) -> tuple[WorkbenchMark, ...]:
        """Every mark on screen now: the list's box states, then the header's, the stepper's and the navigator's."""
        return (*self.box_marks, *self.other_marks)

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
        self._load = load
        self._pages = workbench_pages(presented_form(load.form, recorded=self.recorded))
        self._inapplicable = inapplicable_pages(load.form)
        self.set_class(self.recorded, "-recorded")
        page_ids = [page.id for page in self._pages]
        if previous_page in page_ids:
            self._page_index = page_ids.index(previous_page)
        else:
            attention = self._first_attention()
            self._page_index = 0 if attention is None else attention[0]
        loading = self.query("#wb-loading")
        for widget in loading:
            widget.remove()
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
        """Say once per session, on the notice line, where to find what the symbols mean."""
        app = self.app
        if app in _GREETED:
            return
        _GREETED.add(app)
        notice = self.query_one("#wb-notice", Static)
        if not str(notice.render()):
            notice.update(first_open_text())

    # ── rendering ───────────────────────────────────────────────────────

    def _render_all(self) -> None:
        self._render_header()
        self._render_progress()
        self._render_navigator()
        self._render_page()

    def _render_header(self) -> None:
        form = self.form
        if form is None:
            return
        width = max(self._width() - _GUTTERS, 1)
        recorded = self.recorded
        deadline = deadline_view(form, self._language, recorded=recorded)
        self.query_one("#wb-header", Static).update(fit_identity(form, self._language, deadline, width))
        deadline_widget = self.query_one("#wb-deadline", Static)
        deadline_widget.display = deadline is not None
        deadline_widget.update("" if deadline is None else deadline.text)
        for tone, css_class in _DEADLINE_TONE_CLASSES.items():
            deadline_widget.set_class(deadline is not None and deadline.tone is tone, css_class)
        view = result_view(form, self._language, staged=len(self._session.changes), recorded=recorded)
        chips = attention_chips(form, recorded=recorded)
        line = ResultLine("", None, chips) if view is None else fit_result_line(view, chips, width)
        result = self.query_one("#wb-result", Static)
        result.update(line.result)
        result.display = bool(line.result)
        result.set_class(line.stale is not None, "-stale")
        # Colour only reinforces the words: a result to pay reads as a warning, as an error once the deadline passed.
        to_pay = form.result is not None and form.result.direction is ModeloFormResultDirection.TO_PAY and not recorded
        result.set_class(to_pay, "-to-pay")
        result.set_class(to_pay and form.deadline is not None and form.deadline.days_overdue is not None, "-overdue")
        stale = self.query_one("#wb-stale", Static)
        stale.update(line.stale or "")
        stale.display = line.stale is not None
        chips_widget = self.query_one("#wb-chips", Static)
        chips_widget.update(_CHIP_GAP.join(chip.text for chip in line.chips))
        chips_widget.set_class(line.stale is None, "-leading")
        # Too narrow for one line: the result on its own, the stale mark and the chips on the next.
        self.set_class(line.stacked, "-outcome-stacked")
        stale_marks = () if view is None or line.stale is None else view.marks
        self._drawn["header"] = (*stale_marks, *(chip.mark for chip in line.chips))

    def _render_progress(self) -> None:
        load = self._load
        if load is None:
            return
        progress = workbench_progress(
            load.form, staged=len(self._session.changes), verified=load.verified, filed=self.recorded
        )
        stepper = stepper_text(progress)
        self.query_one("#wb-stepper", Static).update(stepper)
        self._drawn["stepper"] = stepper_marks(progress)
        key = _NEXT_KEYS[progress.next_action]
        action = next_action_text(progress, self._language)
        self._next_words = f"{action} [{key}]" if key else action
        then = record_filing_text() if progress.next_action is NextAction.EXPORT else None
        width = max(self._width() - _GUTTERS, 1)
        line = fit_next_line(action, key, width, then=then)
        # Beside the stepper when it fits there, else on a line of its own: never wrapped.
        self.set_class(cell_len(line) > width - cell_len(stepper.plain) - _NEXT_GAP, "-next-below")
        next_widget = self.query_one("#wb-next", Static)
        next_widget.update(line)
        next_widget.set_class(progress.next_action is NextAction.CONFIRM, "-confirm")
        next_widget.set_class(progress.next_action is NextAction.RESOLVE, "-resolve")

    def _render_navigator(self) -> None:
        form = self.form
        if form is None or not self._pages:
            return
        if self.has_class("-narrow"):
            self._render_breadcrumb()
            return
        navigator = self.query_one("#wb-sections", OptionList)
        highlighted = navigator.highlighted
        kept = None if highlighted is None else navigator.get_option_at_index(highlighted).id
        label_width = max(navigator.scrollable_content_region.width, _NAV_MIN_LABEL)
        rows = navigator_rows(
            self._pages,
            current=self._page_index,
            state=self._navigator,
            checked=checked_boxes(form),
            width=label_width,
            show_attention=not self.recorded,
            inapplicable=self._inapplicable,
            not_applying=self._not_applying_text(),
        )
        navigator.clear_options()
        for row in rows:
            navigator.add_option(Option(row.prompt, id=row.option_id))
        self._drawn["navigator"] = tuple(mark for row in rows for mark in row.marks)
        ids = [row.option_id for row in rows]
        if kept is not None and kept in ids:
            navigator.highlighted = ids.index(kept)

    def _render_breadcrumb(self) -> None:
        form = self.form
        if form is None or not self._pages or not self.has_class("-narrow"):
            return
        entry = self.query_one(CasillaList).highlighted
        page = self._pages[self._page_index]
        section = None if entry is None else section_of(page, entry.key)
        line, marks = breadcrumb(
            self._pages,
            current=self._page_index,
            section=section,
            checked=checked_boxes(form),
            show_attention=not self.recorded,
            not_applying=None if self._applies(self._page_index) else self._not_applying_text(),
        )
        self.query_one("#wb-crumb", Static).update(line)
        self._drawn["navigator"] = marks

    def _render_page(self) -> None:
        if not self._pages:
            return
        form = self.form
        casilla_list = self.query_one(CasillaList)
        filter_words = tr(f"tui.modelo.workbench.filter.{self._filter.value}")
        staged = self._session.display()
        if self._sort is SortOrder.FORM:
            page = self._pages[self._page_index]
            title = page.heading.text
            position = tr("tui.modelo.workbench.page_position", current=self._page_index + 1, total=len(self._pages))
            notes = [position, filter_words]
            if not self._applies(self._page_index):
                notes.insert(1, self._not_applying_text())
            casilla_list.set_items(page_items(page, staged=staged, mode=self._filter), language=self._language)
        else:
            title = tr("tui.modelo.workbench.sort.all_pages")
            notes = [tr(SORT_LOCALE_KEYS[self._sort]), filter_words]
            items = sorted_items(self._pages, order=self._sort, staged=staged, mode=self._filter)
            casilla_list.set_items(items, language=self._language)
        if form is not None and form.layout_provenance is not ModeloFormLayoutProvenance.REVIEWED:
            notes.append(tr(f"tui.modelo.workbench.layout.{form.layout_provenance.value}"))
        self.query_one("#wb-page", Static).update(f"{title}   " + " · ".join(notes))
        if casilla_list.highlighted is None:
            self._render_help(None)

    # ── help ────────────────────────────────────────────────────────────

    def on_casilla_list_highlighted(self, message: CasillaList.Highlighted) -> None:
        """Explain the casilla now under the cursor, then fetch its full help."""
        self._render_help(message.entry)
        self._render_breadcrumb()
        entry = message.entry
        if entry is not None:
            self._ask_for_card(entry)

    def _ask_for_card(self, entry: CasillaListEntry) -> None:
        """Fetch a box's full help off the event loop, unless it is already held."""
        if not isinstance(entry.field.address, ModeloFormCasillaAddressV1):
            return
        casilla_id = entry.field.address.casilla_id
        if (str(casilla_id), self._language) not in self._cards:
            self.run_worker(partial(self._fetch_card, entry), group="workbench-help", exclusive=True)

    def _held_card(self, field: ModeloFormField) -> ModeloCasillaHelpCardV1 | None:
        address = field.address
        if not isinstance(address, ModeloFormCasillaAddressV1):
            return None
        return self._cards.get((str(address.casilla_id), self._language))

    async def _card_for(self, field: ModeloFormField) -> ModeloCasillaHelpCardV1 | None:
        """A box's full help, read off the event loop once and then held; ``None`` for a binding input or a failure."""
        address = field.address
        if not isinstance(address, ModeloFormCasillaAddressV1):
            return None
        held = self._held_card(field)
        if held is not None:
            return held
        try:
            card = await asyncio.to_thread(self._reader.help_card, address.casilla_id, self._language)
        except Exception as failure:
            get_logger(__name__).error(
                "modelo workbench help could not be assembled: %s", type(failure).__qualname__, exc_info=True
            )
            return None
        self._cards[(str(address.casilla_id), self._language)] = card
        return card

    async def _fetch_card(self, entry: CasillaListEntry) -> None:
        if await self._card_for(entry.field) is None:
            return
        if self._explained is not None and self._explained.key == entry.key:
            self._render_help(self._explained)

    def _render_help(self, entry: CasillaListEntry | None) -> None:
        self._explained = entry
        band = self.query_one("#wb-help", Static)
        expanded = band.has_class("-expanded")
        lines: list[str] = []
        if expanded:
            lines.extend((on_screen_text(self.box_marks, self.other_marks), more_text()))
        if entry is None:
            lines.append(tr("tui.modelo.workbench.help.empty"))
        else:
            lines.extend(self._box_help(entry))
        form = self.form
        if expanded and form is not None:
            shifted = deadline_help(form, self._language, recorded=self.recorded)
            if shifted is not None:
                lines.append(shifted)
            lines.append(tr("tui.modelo.workbench.help.keys", keys=self._all_keys_text()))
        band.update("\n".join(self._band_lines(band, lines)))

    def _band_lines(self, band: Static, lines: list[str]) -> list[str]:
        """The band's lines, a line holding a no-break space broken here so it never breaks there.

        The terminal would break a line at any space, splitting "art. 71"; a
        line that holds a no-break space and does not fit is broken only at
        the other spaces. Every other line is left to wrap as it would.
        """
        width = band.content_region.width or max(self._width() - _GUTTERS, 1)
        shown: list[str] = []
        for line in lines:
            if _NO_BREAK_SPACE in line and cell_len(line) > width:
                shown.extend(wrap_words(line, width))
            else:
                shown.append(line)
        return shown

    def _rewrap_help(self) -> None:
        """Lay the help band out again for the width the terminal now has."""
        if self._pages and not self._legend_level:
            self._render_help(self.query_one(CasillaList).highlighted)

    def _box_help(self, entry: CasillaListEntry) -> list[str]:
        """What the band says about one box: its name, its marks in words, its description and its card."""
        field = entry.field
        lines = [self._help_title(entry), self._state_line(entry)]
        lines.append(description_text(field) or tr("tui.modelo.workbench.help.no_explanation"))
        note = rate_note(entry)
        if note is not None:
            lines.append(note)
        card = None
        if isinstance(field.address, ModeloFormCasillaAddressV1):
            card = self._cards.get((str(field.address.casilla_id), self._language))
        if card is not None:
            lines.extend(self._card_lines(card, field))
        form = self.form
        if form is not None and is_result_field(form, field):
            view = result_view(form, self._language, staged=len(self._session.changes), recorded=self.recorded)
            if view is not None:
                lines.extend(view.help)
        return lines

    def _all_keys_text(self) -> str:
        """Every key the help and the legend name; on a declaration recorded as filed, none that would change it."""
        descriptions = {**_LIST_LOCALE_KEYS, **_SCREEN_LOCALE_KEYS}
        hidden = _CHANGE_KEYS if self.recorded else frozenset()
        return " · ".join(
            self._key_label(key, descriptions[key])
            for key in (*_FOOTER_PRIORITY, *_HELP_ONLY_KEYS)
            if key not in hidden
        )

    def _help_title(self, entry: CasillaListEntry) -> str:
        field = entry.field
        box = f"[{field.box}] " if field.box else ""
        title = f"{box}{grid_cell_title(entry) or field.label.text}"
        if field.label.disclosure is not ModeloFormTextDisclosure.LOCALIZED:
            title = f"{title} ({tr(f'tui.modelo.workbench.disclosure.{field.label.disclosure.value}')})"
        return title

    def _state_line(self, entry: CasillaListEntry) -> str:
        """Where the box's value stands and what may be done about it, in the words the row uses.

        On a declaration recorded as filed the second half is why it cannot be
        changed, and a state that asks the filer to act is not said at all.
        """
        field = entry.field
        if self.recorded:
            parts = [] if field.origin in _ASKS_THE_FILER else [origin_text(field)]
            reason = read_only_reason(field, self._language, recorded=True)
            if reason is not None:
                parts.append(reason)
            return " · ".join(parts)
        state = origin_text(field)
        attention = entry.attention
        if attention is not None:
            state = f"{state} · {ATTENTION_MARKS[attention].glyph} {tr(attention_words_key(attention))}"
        return f"{state} · {editability_text(field)}"

    def _said_by_origin(self, field: ModeloFormField) -> frozenset[str]:
        """The sources' sentences the origin words already say: those of the kind of place they name."""
        source = field.source
        if field.origin not in SOURCE_WORDED_ORIGINS or source is None:
            return frozenset[str]()
        said: set[str] = set()
        for binding in field.bindings:
            if binding.policy.family is source.family:
                sentence = lookup_translation(binding.policy.origin_sentence_key, locale=self._language.value)
                if sentence:
                    said.add(sentence)
        return frozenset(said)

    def _card_lines(self, card: ModeloCasillaHelpCardV1, field: ModeloFormField) -> list[str]:
        lines: list[str] = []
        if card.formula is not None:
            lines.append(tr("tui.modelo.workbench.help.formula", formula=card.formula.text))
        said = self._said_by_origin(field)
        for origin in card.origins:
            if origin not in said:
                lines.append(tr("tui.modelo.workbench.help.origin", origin=origin))
        if card.feeds:
            lines.append(tr("tui.modelo.workbench.help.feeds", boxes=", ".join(card.feeds)))
        for quote in card.quotes:
            quoted = _FRAGMENT_SEPARATOR.join(quote.fragments)
            lines.append(tr("tui.modelo.workbench.help.official", source=quote.source, text=quoted))
        if card.legal_basis:
            lines.append(
                tr("tui.modelo.workbench.help.legal", citations="; ".join(item.text for item in card.legal_basis))
            )
        lines.extend(card.constraints)
        return lines

    def action_toggle_help(self) -> None:
        """Name the symbols on screen in a larger band, then open every symbol and key, then close it all."""
        self._legend_level = (self._legend_level + 1) % 3
        self._show_legend_level()

    def _show_legend_level(self) -> None:
        band = self.query_one("#wb-help", Static)
        band.set_class(self._legend_level == 1, "-expanded")
        panel_open = self._legend_level == 2
        if panel_open:
            text = legend_panel(
                self.box_marks,
                others=self.other_marks,
                keys=self._all_keys_text(),
                close=self._key_label("escape", _CLOSE_LOCALE_KEY),
            )
            self.query_one("#wb-legend-text", Static).update(text)
        self.set_class(panel_open, "-legend")
        self._describe_keys()
        if panel_open:
            self.query_one(SymbolsPanel).focus()
        else:
            self._render_help(self.query_one(CasillaList).highlighted)
            self.query_one(CasillaList).focus()

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

    def _show_page(self, index: int) -> None:
        if not self._pages:
            return
        self._page_index = max(0, min(len(self._pages) - 1, index))
        self._render_navigator()
        self._render_page()

    def action_page(self, delta: int) -> None:
        """Show the previous or next page, in form order."""
        self._sort = SortOrder.FORM
        self._show_page(self._page_index + delta)

    def action_cycle_filter(self) -> None:
        """Show all fields, then only what needs attention, then only the filer's own values."""
        position = _FILTER_ORDER.index(self._filter)
        self._filter = _FILTER_ORDER[(position + 1) % len(_FILTER_ORDER)]
        self._render_page()

    def action_cycle_sort(self) -> None:
        """Order the boxes as the form prints them, by box number, by amount, or what needs attention first."""
        self._sort = next_order(self._sort)
        self._render_page()

    def action_fold(self, direction: int) -> None:
        """Close (0), open (1) or flip (-1) the navigator page under its cursor, or the current page."""
        navigator = self.query_one("#wb-sections", OptionList)
        index = self._page_index
        if self.focused is navigator and navigator.highlighted is not None:
            option_id = navigator.get_option_at_index(navigator.highlighted).id or ""
            page_text = option_id.partition(":")[2].partition(":")[0]
            if page_text.isdigit():
                index = int(page_text)
        elif self.focused is not self.query_one(CasillaList):
            raise SkipAction
        if not self._pages or self.form is None:
            return
        page = self._pages[index]
        counts = page_counts(page, checked_boxes(self.form))
        self._navigator.toggle(
            page,
            current=index == self._page_index,
            counts=counts,
            open_=None if direction < 0 else bool(direction),
            applies=self._applies(index),
        )
        self._render_navigator()
        if self.focused is navigator:
            ids = [navigator.get_option_at_index(position).id for position in range(navigator.option_count)]
            target = f"page:{index}"
            if target in ids:
                navigator.highlighted = ids.index(target)

    def action_next_attention(self, direction: int) -> None:
        """Move to the next thing to do, carrying on to the next page that has one."""
        if self.focused is not self.query_one(CasillaList):
            raise SkipAction
        self._advance_attention(direction)

    def _advance_attention(self, direction: int) -> None:
        casilla_list = self.query_one(CasillaList)
        before = casilla_list.highlighted
        casilla_list.action_attention(direction)
        after = casilla_list.highlighted
        if after is not None and (before is None or after.key != before.key):
            return
        if self._sort is SortOrder.FORM and self._pages:
            forward = direction > 0
            indices = range(self._page_index + 1, len(self._pages)) if forward else range(self._page_index - 1, -1, -1)
            for index in indices:
                if not self._applies(index):
                    continue
                targets = [
                    item
                    for item in page_items(self._pages[index], staged=self._session.display(), mode=self._filter)
                    if isinstance(item, CasillaListEntry) and item.needs_filer
                ]
                if targets:
                    self._show_page(index)
                    casilla_list.focus_address(targets[0 if forward else -1].key)
                    casilla_list.focus()
                    return
        if direction > 0:
            self._notice(tr("tui.modelo.workbench.browse.last_to_do", action=self._next_words))

    def action_search(self) -> None:
        """Search every page by box number or words."""
        self._open_search(SearchMode.SEARCH)

    def action_go_to(self) -> None:
        """Go straight to a box by its number."""
        self._open_search(SearchMode.GO_TO)

    def _open_search(self, mode: SearchMode) -> None:
        if not self._pages:
            return
        entries = search_entries(self._pages, staged=self._session.display(), language=self._language)
        self.add_class("-searching")
        self.query_one(WorkbenchSearchPanel).open(mode, entries)

    def _close_search(self) -> None:
        self.remove_class("-searching")
        casilla_list = self.query_one(CasillaList)
        self._render_help(casilla_list.highlighted)
        casilla_list.focus()

    def on_workbench_search_panel_highlighted(self, message: WorkbenchSearchPanel.Highlighted) -> None:
        """Explain in the help band the hit the filer is on, fetching its full help once."""
        staged = self._session.display()
        entry = next(
            (
                item
                for page in self._pages
                for item in page_items(page, staged=staged)
                if isinstance(item, CasillaListEntry) and item.key == message.key
            ),
            None,
        )
        if entry is None:
            return
        self._render_help(entry)
        self._ask_for_card(entry)

    def on_workbench_search_panel_chosen(self, message: WorkbenchSearchPanel.Chosen) -> None:
        """Go to the box the filer found."""
        self._close_search()
        self._go_to(message.key)

    def action_toggle_density(self) -> None:
        """Show fields on one line or two; the filer's choice then holds whatever the terminal's height."""
        casilla_list = self.query_one(CasillaList)
        density: Density = "compact" if casilla_list.density == "comfortable" else "comfortable"
        self._density_chosen = density
        casilla_list.set_density(density)

    def action_leave(self) -> None:
        """Close the open panel, or leave for where the workbench was opened from, asking first about staged changes."""
        if self._legend_level:
            self._legend_level = 0
            self._show_legend_level()
            return
        if self.has_class("-searching"):
            self._close_search()
            return
        self._leave_then(lambda: self.dismiss(None))

    def _leave_then(self, leave: Callable[[], object]) -> None:
        if not self._session.dirty:
            leave()
            return

        def closed(discard: bool | None) -> None:
            if discard:
                self._session.discard()
                leave()

        self.app.push_screen(
            ConfirmScreen(
                title=tr("tui.modelo.workbench.leave.title"),
                message=tr("tui.modelo.workbench.leave.message", count=len(self._session.changes)),
                confirm_label=tr("tui.modelo.workbench.leave.discard"),
                cancel_label=tr("tui.modelo.workbench.leave.stay"),
            ),
            closed,
        )

    # ── editing ─────────────────────────────────────────────────────────

    def _status_line(self) -> str | None:
        """The header's result line, for a dialog that covers the header to repeat at its top."""
        form = self.form
        if form is None:
            return None
        return result_line_text(form, self._language, staged=len(self._session.changes), recorded=self.recorded) or None

    def _notice(self, message: str) -> None:
        self.query_one("#wb-notice", Static).update(message)

    def _edit_unavailable(self) -> None:
        if self.recorded:
            self._notice(tr("tui.modelo.workbench.filed.read_only"))
            return
        refusal = self._reader.edit_refusal()
        self._notice(refusal or tr("tui.modelo.workbench.editability.no_admission"))

    def _refresh_after_staging(self) -> None:
        self._render_header()
        self._render_progress()
        self._render_navigator()
        self._render_page()

    def on_casilla_list_edit_requested(self, message: CasillaList.EditRequested) -> None:
        """Open the panel for the casilla under the cursor; one that cannot be typed into says why and where."""
        self._open_editor(message.entry)

    def _open_editor(self, entry: CasillaListEntry) -> None:
        field = entry.field
        actions = self._actions
        form = self.form
        recorded = self.recorded
        if actions is None or form is None or not (recorded or form.edit_admitted):
            self._edit_unavailable()
            return
        if self._held_card(field) is None and isinstance(field.address, ModeloFormCasillaAddressV1):
            # The panel names the boxes this one affects, which only the full help knows: read it first.
            self.run_worker(partial(self._open_editor_once_explained, entry), group="workbench-editor", exclusive=True)
            return
        self._push_editor(entry, actions, self._held_card(field))

    async def _open_editor_once_explained(self, entry: CasillaListEntry) -> None:
        card = await self._card_for(entry.field)
        actions = self._actions
        if actions is not None:
            self._push_editor(entry, actions, card)

    def _push_editor(
        self, entry: CasillaListEntry, actions: ModeloWorkbenchActionsV1, card: ModeloCasillaHelpCardV1 | None
    ) -> None:
        field = entry.field
        recorded = self.recorded
        probe = WorkbenchEditSession(self._language)
        self.app.push_screen(
            CasillaEditorScreen(
                field,
                parse=actions.parse,
                language=self._language,
                limits=() if card is None else card.constraints,
                can_clear=probe.stage_clear(field) is None,
                can_restore=probe.stage_restore(field) is None,
                read_only_reason=read_only_reason(field, self._language, recorded=recorded),
                feeds=() if card is None else card.feeds,
                status_line=self._status_line(),
            ),
            partial(self._editor_closed, entry),
        )

    def _editor_closed(self, entry: CasillaListEntry, decision: EditorOutcome | None) -> None:
        if isinstance(decision, OpenSourceSurface):
            self._open_surface(decision)
            return
        if decision is None:
            return
        field = entry.field
        if decision.kind is WorkbenchChangeKind.SET:
            refusal = self._session.stage_value(field, decision.value, decision.display)
        elif decision.kind is WorkbenchChangeKind.CLEAR:
            refusal = self._session.stage_clear(field)
        else:
            refusal = self._session.stage_restore(field)
        self._after_stage(refusal)
        if refusal is None and decision.advance:
            self._advance_attention(1)

    def _after_stage(self, refusal: StageRefusal | None) -> None:
        if refusal is not None:
            self._notice(tr(f"tui.modelo.workbench.stage_refused.{refusal.value}"))
            return
        self._notice("")
        self._refresh_after_staging()

    def action_bulk_confirm(self) -> None:
        """List the assumed values of the section under the cursor, or of the page, to confirm them together.

        Never the whole declaration at once: the filer reads the values of one
        part of the form before saying they are right. Where none of the
        assumed values here can be confirmed from a list, the first one's panel
        opens instead, which says what can be done about it.
        """
        if not self._may_confirm():
            self._edit_unavailable()
            return
        fields, in_section = self._confirm_scope()
        assumed = tuple(field for field in fields if field.origin is ModeloFormOrigin.DEFAULT_TO_CONFIRM)
        if not assumed:
            self._notice(tr(_NONE_TO_CONFIRM_LOCALE_KEYS[in_section]))
            return
        if not any(confirmable(field) for field in assumed):
            self._open_box(address_key(assumed[0].address))
            return
        self.app.push_screen(
            BulkConfirmScreen(assumed, language=self._language, status_line=self._status_line()), self._bulk_confirmed
        )

    def _open_box(self, key: AddressKey) -> None:
        """Put the cursor on one box and open its panel."""
        self._go_to(key)
        entry = self.query_one(CasillaList).highlighted
        if entry is not None and entry.key == key:
            self._open_editor(entry)

    def _may_confirm(self) -> bool:
        form = self.form
        return self._actions is not None and form is not None and not self.recorded and form.edit_admitted

    def _confirm_scope(self) -> tuple[tuple[ModeloFormField, ...], bool]:
        """The fields ``b`` offers: the section under the cursor, else the page; and whether it is a section."""
        entry = self.query_one(CasillaList).highlighted
        index = self._page_index if entry is None else page_of(self._pages, entry.key)
        if not self._pages or index is None:
            return (), False
        page = self._pages[index]
        section = None if entry is None else section_of(page, entry.key)
        if section is not None:
            return section_fields(section), True
        return page.fields(), False

    def _confirm_next(self) -> None:
        """Offer the assumed values here, or go to the next part of the form that holds one and offer those.

        A page that does not apply this period holds nothing to do, so its
        assumed values are passed over here; ``b`` still offers them on request.
        """
        if not self._may_confirm():
            self._edit_unavailable()
            return
        fields, _ = self._confirm_scope()
        here = bool(self._pages) and self._applies(self._page_index)
        if here and any(field.origin is ModeloFormOrigin.DEFAULT_TO_CONFIRM for field in fields):
            self.action_bulk_confirm()
            return
        target = self._next_assumed()
        if target is not None:
            self._go_to(target)
        self.action_bulk_confirm()

    def _next_assumed(self) -> AddressKey | None:
        """The next assumed box after the cursor in form order, on a page that applies, coming round to the start."""
        entry = self.query_one(CasillaList).highlighted
        ordered = [
            address_key(field.address)
            for index, page in enumerate(self._pages)
            if self._applies(index)
            for field in page.fields()
            if field.origin is ModeloFormOrigin.DEFAULT_TO_CONFIRM
        ]
        if not ordered:
            return None
        position = {
            address_key(field.address): order
            for order, field in enumerate(field for page in self._pages for field in page.fields())
        }
        here = -1 if entry is None else position.get(entry.key, -1)
        return next((key for key in ordered if position[key] > here), ordered[0])

    def _bulk_confirmed(self, confirmed: tuple[ModeloFormField, ...] | None) -> None:
        if not confirmed:
            return
        refusals = [refusal for field in confirmed if (refusal := self._session.stage_confirmation(field)) is not None]
        self._refresh_after_staging()
        self._notice(tr(f"tui.modelo.workbench.stage_refused.{refusals[0].value}") if refusals else "")

    def on_casilla_list_clear_requested(self, message: CasillaList.ClearRequested) -> None:
        """Stage removing the value the filer declared on the casilla under the cursor."""
        self._after_stage(self._session.stage_clear(message.entry.field))

    def on_casilla_list_revert_requested(self, message: CasillaList.RevertRequested) -> None:
        """Drop the change staged on the casilla under the cursor."""
        if self._session.revert(message.entry.key):
            self._notice("")
            self._refresh_after_staging()

    def on_casilla_list_source_requested(self, message: CasillaList.SourceRequested) -> None:
        """Open the declaration's sources, on the casilla under the cursor when a source feeds it."""
        form = self.form
        if form is None:
            return
        self.app.push_screen(
            WorkbenchSourcesScreen(
                form,
                language=self._language,
                staged=self._session.display(),
                focus=message.entry.key,
                status_line=self._status_line(),
            ),
            self._sources_closed,
        )

    def _sources_closed(self, choice: SourcesChoice | None) -> None:
        if isinstance(choice, GoToCasilla):
            self._go_to(choice.key)
            entry = self.query_one(CasillaList).highlighted
            if entry is not None and entry.key == choice.key and entry.field.editability in TYPED_EDITABILITIES:
                self._open_editor(entry)
        elif isinstance(choice, OpenSourceSurface):
            self._open_surface(choice)

    def _go_to(self, key: AddressKey) -> None:
        casilla_list = self.query_one(CasillaList)
        if self._sort is not SortOrder.FORM:
            if casilla_list.focus_address(key):
                casilla_list.focus()
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

    def _open_surface(self, choice: OpenSourceSurface) -> None:
        navigate = self._navigate
        root = self.app
        if navigate is None and isinstance(root, TuiSearchHostV1):
            navigate = root.navigate_to
        target = surface_target(choice.surface)
        if navigate is None or target is None:
            self._notice(tr("tui.modelo.workbench.sources.not_here"))
            return
        self._leave_then(lambda: navigate(target))

    def action_review(self) -> None:
        """Check every staged change with the application, then open their review."""
        if not self._session.dirty:
            self._notice(tr("tui.modelo.workbench.review.none"))
            return
        self.run_worker(self._open_review, group="workbench-review", exclusive=True)

    async def _open_review(self, *, rebased: bool = False) -> None:
        actions = self._actions
        preflight = WorkbenchPreflight()
        if actions is not None:
            try:
                preflight = await actions.preflight(self._session.payload())
            except CadrumoError as refusal:
                self._notice(resolve_error_message(refusal))
                return
            except Exception as failure:
                get_logger(__name__).error(
                    "modelo workbench could not check the staged changes: %s",
                    type(failure).__qualname__,
                    exc_info=True,
                )
                self._notice(tr("tui.modelo.workbench.review.check_failed"))
                return
        if preflight.stale:
            if rebased:
                self._notice(tr("tui.modelo.workbench.rebase.still_moving"))
                return
            if await self._rebase() and self._session.dirty:
                await self._open_review(rebased=True)
            return
        form = self.form
        at_risk = None
        if form is not None and (preflight.operator_entries_unknown or self._entries_unknown(form)):
            staged = frozenset(change.key for change in self._session.changes)
            at_risk = self._unattributed_boxes(form, excluding=staged)
        notes = tuple(
            ReviewNote(box=self._box_of(finding.address), message=finding.message, blocking=finding.blocking)
            for finding in preflight.findings
        )
        self.app.push_screen(
            EditReviewScreen(self._session.changes, notes=notes, at_risk=at_risk, status_line=self._status_line()),
            self._review_closed,
        )

    @staticmethod
    def _entries_unknown(form: ModeloWorkForm) -> bool:
        """Whether the declaration holds a calculation that does not record which values the filer typed."""
        return form.calculation_revision_id is not None and not form.operator_entries_known

    @staticmethod
    def _unattributed_boxes(form: ModeloWorkForm, *, excluding: frozenset[AddressKey] = frozenset()) -> tuple[str, ...]:
        """The boxes holding a value nobody is recorded as having typed, which a recalculation returns to source.

        Every such box is named, a zero in an optional box as much as an
        assumed value: the question is what applying changes, not what is to do.
        """
        return tuple(
            f"[{field.box}]" if field.box else field.label.text
            for field in form.fields()
            if field.unattributed and address_key(field.address) not in excluding
        )

    def _box_of(self, address: ModeloFormAddressV1 | None) -> str | None:
        form = self.form
        if address is None or form is None:
            return None
        for field in form.fields():
            if field.address == address or edit_address(field) == address:
                return field.box or field.label.text
        return None

    async def _rebase(self) -> bool:
        """Read the declaration again and keep the staged changes that still apply, saying what moved."""
        try:
            load = await asyncio.to_thread(self._reader.load, self._language)
        except Exception as failure:
            get_logger(__name__).error(
                "modelo workbench could not read its declaration again: %s", type(failure).__qualname__, exc_info=True
            )
            self._notice(tr("tui.modelo.workbench.read_failed"))
            return False
        outcome = self._session.rebase(load.form)
        self.show_load(load)
        self._notice(self._rebase_text(outcome))
        return True

    @staticmethod
    def _rebase_text(outcome: Rebase) -> str:
        parts = [tr("tui.modelo.workbench.rebase.moved")]
        if outcome.changed:
            parts.append(tr("tui.modelo.workbench.rebase.changed", count=len(outcome.changed)))
        if outcome.dropped:
            parts.append(tr("tui.modelo.workbench.rebase.dropped", count=len(outcome.dropped)))
        return " ".join(parts)

    def _review_closed(self, decision: ReviewDecision | None) -> None:
        actions = self._actions
        if decision is ReviewDecision.APPLY and actions is not None:
            self._session.acknowledge()
            changes = self._session.payload()
            self._run_operation(partial(actions.apply, changes), applies_changes=True)
        elif decision is ReviewDecision.DISCARD:
            self._session.discard()
            self._notice(tr("tui.modelo.workbench.review.discarded"))
            self._refresh_after_staging()

    # ── lifecycle ───────────────────────────────────────────────────────

    def action_next_step(self) -> None:
        """Run the next step the stepper offers."""
        load = self._load
        if load is None:
            return
        staged = len(self._session.changes)
        progress = workbench_progress(load.form, staged=staged, verified=load.verified, filed=self.recorded)
        actions = self._actions
        action = progress.next_action
        if action is NextAction.RECORDED:
            self._edit_unavailable()
        elif action is NextAction.APPLY:
            self.action_review()
        elif action is NextAction.CONFIRM:
            self._confirm_next()
        elif action is NextAction.RESOLVE and load.form.verification is not None:
            self.action_issues()
        elif action in {NextAction.FILL, NextAction.RESOLVE}:
            self._advance_attention(1)
        elif actions is None:
            self._edit_unavailable()
        elif action is NextAction.CALCULATE:
            self._calculate(actions)
        elif action is NextAction.VERIFY:
            self._run_operation(actions.verify)
        else:
            self._confirm_file(actions.file)

    def action_calculate(self) -> None:
        """Recalculate the declaration now, keeping the filer's values."""
        actions = self._actions
        if actions is None or self.recorded:
            self._edit_unavailable()
            return
        if self._session.dirty:
            self._notice(tr("tui.modelo.workbench.calculate.apply_first"))
            return
        self._calculate(actions)

    def _calculate(self, actions: ModeloWorkbenchActionsV1) -> None:
        """Recalculate, first asking the filer to accept losing values nobody is recorded as having typed."""
        form = self.form
        if form is None or not self._entries_unknown(form):
            self._calculate_now(actions)
            return

        def closed(proceed: bool | None) -> None:
            if proceed:
                self._calculate_now(actions)
            else:
                self._notice(tr("tui.modelo.workbench.calculate.kept"))

        self.app.push_screen(
            ConfirmScreen(
                title=tr("tui.modelo.workbench.calculate.at_risk_title"),
                message=recalculation_risk_text(self._unattributed_boxes(form)),
                confirm_label=tr("tui.modelo.workbench.calculate.at_risk_proceed"),
                cancel_label=tr("tui.modelo.workbench.calculate.at_risk_cancel"),
            ),
            closed,
        )

    def _calculate_now(self, actions: ModeloWorkbenchActionsV1) -> None:
        need = actions.calculation_evidence()
        if need is None:
            self._run_operation(actions.calculate)
            return

        def answered(submission: OrdinaryM303FilingEvidenceSubmission | None) -> None:
            if submission is None:
                self._notice(tr("tui.modelo.m303_evidence.cancelled"))
            elif submission.work_unit_id != need.work_unit_id:
                self._notice(tr("tui.modelo.m303_evidence.stale_context"))
            else:
                self._run_operation(partial(actions.calculate, submission))

        self.app.push_screen(
            OrdinaryM303FilingEvidenceScreen(work_unit_id=need.work_unit_id, asks_modelo_390=need.asks_modelo_390),
            answered,
        )

    def action_issues(self) -> None:
        """List everything to look at, what the last check found and the assumed values, and go where one leads."""
        form = self.form
        if form is None:
            return

        def closed(key: AddressKey | None) -> None:
            if key is not None:
                self._go_to(key)

        self.app.push_screen(WorkbenchIssuesScreen(form, status_line=self._status_line()), closed)

    def action_export(self) -> None:
        """Export the verified declaration where and how the filer asks."""
        actions = self._actions
        load = self._load
        if actions is None or load is None:
            self._edit_unavailable()
            return
        if not load.verified:
            self._notice(tr("tui.modelo.workbench.export.verify_first"))
            return

        def asked(request: WorkbenchExportRequest | None) -> None:
            if request is not None:
                self._run_operation(partial(actions.export, request))

        self.app.push_screen(WorkbenchExportScreen(actions.export_offer()), asked)

    def _confirm_file(self, submit: Callable[[], Awaitable[OperationController]]) -> None:
        def closed(confirmed: bool | None) -> None:
            if confirmed:
                self._run_operation(submit)
            else:
                self._notice(tr("application.modelo.lifecycle.file_cancelled"))

        self.app.push_screen(
            ConfirmScreen(
                title=tr("application.modelo.lifecycle.file_confirm_title"),
                message=tr("application.modelo.lifecycle.file_confirm_message"),
                confirm_label=tr("application.modelo.lifecycle.file_confirm_accept"),
                cancel_label=tr("application.modelo.lifecycle.file_confirm_cancel"),
            ),
            closed,
        )

    def _run_operation(
        self, submit: Callable[[], Awaitable[OperationController]], *, applies_changes: bool = False
    ) -> None:
        if self._operation_in_flight:
            return
        self._operation_in_flight = True
        self.run_worker(
            partial(self._open_operation, submit, applies_changes), group="workbench-operation", exclusive=True
        )

    async def _open_operation(
        self, submit: Callable[[], Awaitable[OperationController]], applies_changes: bool
    ) -> None:
        from ...operations.modal import OperationModal

        try:
            controller = await submit()
        except ModeloEditBaselineStaleError:
            self._operation_in_flight = False
            if applies_changes and await self._rebase() and self._session.dirty:
                await self._open_review(rebased=True)
            return
        except CadrumoError as refusal:
            self._operation_in_flight = False
            self._notice(resolve_error_message(refusal))
            return
        except Exception as failure:
            self._operation_in_flight = False
            get_logger(__name__).error(
                "modelo workbench operation failed before it opened: %s", type(failure).__qualname__, exc_info=True
            )
            self._notice(tr("operation.modal.terminal.failed"))
            return
        self.app.push_screen(OperationModal(controller), partial(self._operation_settled, applies_changes))

    def _operation_settled(self, applies_changes: bool, outcome: object) -> None:
        from ...operations.modal import OperationModalSettledOutcomeV1

        self._operation_in_flight = False
        if not isinstance(outcome, OperationModalSettledOutcomeV1):
            return
        condition = outcome.view_model.projection.terminal_condition
        if condition is not OperationTerminalCondition.SUCCEEDED:
            explanation = (
                public_refusal_explanation(outcome.view_model.receipt_ref)
                if outcome.view_model.receipt_kind == "refusal"
                else None
            )
            message = tr("tui.modelo.workbench.operation.not_done")
            self._notice(message if explanation is None else f"{message} {explanation}")
            if applies_changes:
                self.run_worker(self._rebase, group="workbench-read", exclusive=True)
            return
        yours = frozenset(change.key for change in self._session.changes) if applies_changes else frozenset()
        if applies_changes:
            self._session.discard()
        projection = outcome.view_model.projection
        definition = str(projection.definition_id)
        reports_itself = not applies_changes and definition in _SELF_REPORTING_OPERATIONS
        if not reports_itself:
            self._notice(tr("tui.modelo.workbench.operation.done"))
        actions = self._actions
        if actions is not None:
            self.run_worker(partial(asyncio.to_thread, actions.refresh_product), group="workbench-refresh")
        if projection.definition_id == MODELO_EXPORT_OPERATION_DEFINITION_ID and actions is not None:
            self.run_worker(partial(self._state_export_result, actions, projection), group="workbench-export")
        changes_values = projection.definition_id in _VALUE_CHANGING_OPERATIONS
        before = self._load if changes_values else None
        self.run_worker(
            partial(self._read_after, before, yours, definition if reports_itself else None),
            group="workbench-read",
            exclusive=True,
        )

    async def _read_after(
        self, before: ModeloWorkFormLoadV1 | None, yours: frozenset[AddressKey], reporting: str | None = None
    ) -> None:
        """Read the declaration again, say what a calculation or a check concluded, and show what changed."""
        await self._read()
        after = self._load
        if reporting is not None and after is not None:
            self._notice(self._outcome_text(reporting, after.form))
        if before is None or after is None or after is before:
            return
        changes = modelo_work_form_changes(before.form, after.form)
        if not changes:
            self._notice(tr("tui.modelo.workbench.result_diff.nothing_changed"))
            return
        lines = result_lines(
            changes,
            before=before.form,
            after=after.form,
            yours=yours,
            language=self._language,
        )

        def closed(key: AddressKey | None) -> None:
            if key is not None:
                self._go_to(key)

        self.app.push_screen(WorkbenchResultScreen(lines), closed)

    def _outcome_text(self, definition: str, form: ModeloWorkForm) -> str:
        """What a finished calculation or check concluded, in the filer's words."""
        if definition == str(MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID):
            verdict = form.verification
            if verdict is None:
                return tr("tui.modelo.workbench.operation.done")
            return tr(_CHECKED_LOCALE_KEYS[verdict], key="i")
        view = result_view(form, self._language, staged=0, recorded=self.recorded)
        if view is None or view.settled is None:
            return tr("tui.modelo.workbench.operation.done")
        direction, value = view.settled
        return tr("tui.modelo.workbench.operation.calculated", direction=direction, value=value)

    async def _state_export_result(
        self, actions: ModeloWorkbenchActionsV1, projection: OperationPublicProjectionV1
    ) -> None:
        self.app.push_screen(ModeloExportResultScreen(await actions.export_result(projection)))

    def action_toggle_appearance(self) -> None:
        """Switch between the two shipped appearances."""
        toggle_appearance(self.app)


__all__ = ["ModeloWorkbenchScreen", "SymbolsPanel"]
