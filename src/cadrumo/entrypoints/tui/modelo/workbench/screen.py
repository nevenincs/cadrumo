"""The modelo editor workbench: one screen to fill, calculate, review and file a declaration.

The screen shows one declaration at a time. A header names the modelo, the
period and the calculated result; a stepper says how far the filing has got and
offers the one thing to do next; a navigator lists the official pages and their
sections with what each still needs; the casilla list shows the current page;
and a help band explains the casilla under the cursor -- its words, where its
value comes from, what may be done about it, and, once loaded, its formula,
official text and legal basis.

The screen resolves nothing itself. It reads through the port the composition
root hands it, off the event loop, and keeps only presentation state: the page
shown, the filter, the density and the cursor, which it holds by casilla
address so a refresh or a language switch lands on the same box.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from functools import partial
from typing import TYPE_CHECKING, ClassVar, Final, override

from rich.cells import cell_len
from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from .....application.modelo.action_errors import ModeloEditBaselineStaleError
from .....application.modelo.casilla_help import ModeloCasillaHelpCardV1
from .....application.modelo.operation_definitions import (
    MODELO_EDIT_APPLY_OPERATION_DEFINITION_ID,
    MODELO_EXPORT_OPERATION_DEFINITION_ID,
    MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID,
)
from .....application.modelo.work_form_models import (
    ModeloFormAddressV1,
    ModeloFormCasillaAddressV1,
    ModeloFormField,
    ModeloFormLayoutProvenance,
    ModeloFormOrigin,
    ModeloFormTextDisclosure,
    ModeloWorkForm,
    address_key,
    edit_address,
    section_fields,
)
from .....application.modelo.work_form_service import ModeloWorkFormLoadV1, modelo_work_form_changes
from .....core.errors.error_codes import resolve_error_message
from .....core.errors.hierarchy import CadrumoError
from .....core.external_constants import OutputLanguage
from .....core.i18n.render import output_language, tr
from .....core.logging import get_logger
from .....core.operations import OperationTerminalCondition
from ...components.account_chrome import AccountChromeScreen
from ...components.dialogs import ConfirmScreen
from ...components.theme import toggle_appearance, tokenised
from ...navigation import TuiNavigationTargetV1
from ...operations.controller import OperationController
from ...operations.refusal_explanation import public_refusal_explanation
from ...search import TuiSearchHostV1
from ..export_result import ModeloExportResultScreen
from ..m303_evidence import OrdinaryM303FilingEvidenceScreen, OrdinaryM303FilingEvidenceSubmission
from .casilla_list import AddressKey, CasillaList, CasillaListEntry, Density, value_text
from .editor import CasillaEditorScreen, EditorDecision
from .export import WorkbenchExportScreen
from .issues import WorkbenchIssuesScreen
from .keys import describe_bindings
from .page_items import (
    WorkbenchFilter,
    WorkbenchPage,
    first_attention,
    page_items,
    page_of,
    section_nav_text,
    workbench_pages,
)
from .ports import (
    ModeloWorkbenchActionsV1,
    ModeloWorkbenchReaderV1,
    WorkbenchChangeKind,
    WorkbenchExportRequest,
    WorkbenchPreflight,
)
from .progress import NextAction, defaults_text, next_action_text, stepper_text, workbench_progress
from .result import WorkbenchResultScreen, result_lines
from .review import EditReviewScreen, ReviewDecision, ReviewNote, at_risk_text
from .session import Rebase, StagedChange, StageRefusal, WorkbenchEditSession
from .sources import GoToCasilla, OpenSourceSurface, SourcesChoice, WorkbenchSourcesScreen, surface_target
from .vocabulary import ORIGIN_GLYPHS, TYPED_EDITABILITIES, editability_text, origin_words_key
from .wording import modelo_number, modelo_title, period_words

if TYPE_CHECKING:
    from .....application.operations.frontend_projection import OperationPublicProjectionV1

_NARROW: Final[int] = 110
_NAV_MARGIN: Final[int] = 8
_FOOTER_KEY_GAP: Final[int] = 1
_FOOTER_PRIORITY: Final[tuple[str, ...]] = (
    "enter",
    "n",
    "question_mark",
    "escape",
    "f8",
    "R",
    "s",
    "left_square_bracket",
    "right_square_bracket",
    "f",
    "i",
    "c",
    "e",
)
"""Footer keys, most needed first; the footer shows as many as fit and the expanded help names them all."""
_VALUE_CHANGING_OPERATIONS: Final[frozenset[str]] = frozenset(
    {str(MODELO_EDIT_APPLY_OPERATION_DEFINITION_ID), str(MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID)}
)
"""Operations after which the workbench shows which boxes now read differently."""
_NAV_MIN_LABEL: Final[int] = 12
_FRAGMENT_SEPARATOR: Final[str] = " … "
_FILTER_ORDER: Final[tuple[WorkbenchFilter, ...]] = (
    WorkbenchFilter.ALL,
    WorkbenchFilter.ATTENTION,
    WorkbenchFilter.MINE,
)
_NEXT_KEYS: Final[Mapping[NextAction, str]] = {
    NextAction.APPLY: "R",
    NextAction.FILL: "n",
    NextAction.RESOLVE: "i",
    NextAction.CALCULATE: "F8",
    NextAction.VERIFY: "F8",
    NextAction.FILE: "F8",
    NextAction.DONE: "",
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
}
_LIST_LOCALE_KEYS: Final[Mapping[str, str]] = {
    "enter": "tui.modelo.workbench.key.edit",
    "n": "tui.modelo.workbench.key.next_attention",
    "s": "tui.modelo.workbench.key.sources",
}


class ModeloWorkbenchScreen(AccountChromeScreen):
    """One declaration's workbench."""

    DEFAULT_CSS: ClassVar[str] = tokenised(
        """
        ModeloWorkbenchScreen #wb-status {
            height: auto;
            padding: $cadrumo-space-0 $cadrumo-gutter;
            background: $surface;
        }
        ModeloWorkbenchScreen #wb-next {
            color: $accent;
            text-style: bold;
        }
        ModeloWorkbenchScreen #wb-notice {
            height: auto;
            color: $warning;
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
        ModeloWorkbenchScreen #wb-help {
            height: auto;
            max-height: $cadrumo-help-max-height;
            padding: $cadrumo-space-0 $cadrumo-gutter;
            background: $surface;
            border-top: $cadrumo-rule $panel;
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
        Binding("d", "toggle_density", "", show=False),
        Binding("question_mark,f1", "toggle_help", "", show=False),
        Binding("escape,q", "leave", "", show=False),
        Binding("f3", "toggle_appearance", "", show=False),
        Binding("R", "review", "", show=False),
        Binding("f8", "next_step", "", show=False),
        Binding("c", "calculate", "", show=False),
        Binding("e", "export", "", show=False),
        Binding("i", "issues", "", show=False),
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
        self._page_index = 0
        self._filter = WorkbenchFilter.ALL
        self._cards: dict[tuple[str, OutputLanguage], ModeloCasillaHelpCardV1] = {}
        self._language = OutputLanguage(output_language())
        self._session = WorkbenchEditSession(self._language)

    # ── composition ─────────────────────────────────────────────────────

    @override
    def compose(self) -> ComposeResult:
        yield Static(id="wb-header", classes="cadrumo-banner", markup=False)
        with Vertical(id="wb-status"):
            yield Static(id="wb-stepper", markup=False)
            yield Static(id="wb-next", markup=False)
            yield Static(id="wb-notice", markup=False)
        with Horizontal(id="wb-body"):
            yield OptionList(id="wb-sections")
            with Vertical(id="wb-main"):
                yield Static(id="wb-page", markup=False)
                yield Static(tr("tui.modelo.workbench.loading"), id="wb-loading", markup=False)
                yield CasillaList(language=self._language, id="wb-list")
        yield Static(id="wb-help", markup=False)

    def on_mount(self) -> None:
        """Describe the keys and read the declaration."""
        self._describe_keys()
        self._apply_width(self.size.width)
        self.run_worker(self._read, group="workbench-read", exclusive=True)

    def on_resize(self, event: events.Resize) -> None:
        """Fold the navigator away on narrow terminals and shorten the header to fit."""
        self._apply_width(event.size.width)
        self._render_header()
        self._describe_keys()
        self.call_after_refresh(self._render_navigator)

    def _apply_width(self, width: int) -> None:
        self.set_class(width < _NARROW, "-narrow")

    def _key_label(self, key: str, translation_key: str) -> str:
        own = self._bindings.key_to_bindings.get(key)
        binding = own[0] if own else self.query_one(CasillaList).binding_for(key)
        display = key if binding is None else self.app.get_key_display(binding)
        return f"{display} {tr(translation_key)}"

    def _footer_keys(self, width: int) -> frozenset[str]:
        """The keys the footer can show at ``width``, most needed first, without running past the edge."""
        descriptions = {**_LIST_LOCALE_KEYS, **_SCREEN_LOCALE_KEYS}
        others = [
            active.binding
            for key, active in self.active_bindings.items()
            if active.binding.show and key not in descriptions
        ]
        budget = width - sum(
            cell_len(f"{self.app.get_key_display(binding)} {binding.description}") + _FOOTER_KEY_GAP
            for binding in others
        )
        shown: set[str] = set()
        for key in _FOOTER_PRIORITY:
            cost = cell_len(self._key_label(key, descriptions[key])) + _FOOTER_KEY_GAP
            if cost > budget:
                break
            shown.add(key)
            budget -= cost
        return frozenset(shown)

    def _describe_keys(self) -> None:
        shown = self._footer_keys(self.size.width or self.app.size.width)
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
        self._pages = workbench_pages(load.form)
        page_ids = [page.id for page in self._pages]
        if previous_page in page_ids:
            self._page_index = page_ids.index(previous_page)
        else:
            attention = first_attention(self._pages)
            self._page_index = 0 if attention is None else attention[0]
        loading = self.query("#wb-loading")
        for widget in loading:
            widget.remove()
        self._render_all()
        if previous_page is None:
            attention = first_attention(self._pages)
            if attention is not None and attention[0] == self._page_index:
                self.query_one(CasillaList).focus_address(attention[1])
        self.query_one(CasillaList).focus()

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
        modelo = str(form.modelo)
        name = modelo_number(modelo) if self.size.width < _NARROW else modelo_title(modelo, self._language)
        parts = [name, period_words(form.period)]
        results = [field for field in form.fields() if self._is_result(form, field)]
        for field in results[:1]:
            shown = value_text(CasillaListEntry(field), self._language)
            parts.append(tr("tui.modelo.workbench.result", box=field.box or "", value=shown))
        self.query_one("#wb-header", Static).update(" · ".join(parts))

    @staticmethod
    def _is_result(form: ModeloWorkForm, field: ModeloFormField) -> bool:
        address = field.address
        return isinstance(address, ModeloFormCasillaAddressV1) and address.casilla_id in form.result_addresses

    def _render_progress(self) -> None:
        load = self._load
        if load is None:
            return
        staged = len(self._session.changes)
        progress = workbench_progress(load.form, staged=staged, verified=load.verified, filed=load.filed)
        self.query_one("#wb-stepper", Static).update(stepper_text(progress))
        key = _NEXT_KEYS[progress.next_action]
        action = next_action_text(progress)
        line = tr("tui.modelo.workbench.next_line", action=action, key=key) if key else action
        advisory = defaults_text(progress)
        self.query_one("#wb-next", Static).update(f"{line} · {advisory}" if advisory else line)

    def _render_navigator(self) -> None:
        navigator = self.query_one("#wb-sections", OptionList)
        label_width = max(navigator.size.width - _NAV_MARGIN, _NAV_MIN_LABEL)
        navigator.clear_options()
        for index, page in enumerate(self._pages):
            marker = "▸ " if index == self._page_index else "  "
            navigator.add_option(Option(f"{marker}{page.heading.text}", id=f"page:{index}"))
            for section in page.sections:
                label = section_nav_text(section, label_width)
                navigator.add_option(Option(f"  {label}", id=f"section:{index}:{section.id}"))

    def _render_page(self) -> None:
        if not self._pages:
            return
        page = self._pages[self._page_index]
        form = self.form
        position = tr("tui.modelo.workbench.page_position", current=self._page_index + 1, total=len(self._pages))
        notes = [position, tr(f"tui.modelo.workbench.filter.{self._filter.value}")]
        if form is not None and form.layout_provenance is not ModeloFormLayoutProvenance.REVIEWED:
            notes.append(tr(f"tui.modelo.workbench.layout.{form.layout_provenance.value}"))
        self.query_one("#wb-page", Static).update(f"{page.heading.text}   " + " · ".join(notes))
        casilla_list = self.query_one(CasillaList)
        items = page_items(page, staged=self._session.display(), mode=self._filter)
        casilla_list.set_items(items, language=self._language)
        if casilla_list.highlighted is None:
            self._render_help(None)

    # ── help ────────────────────────────────────────────────────────────

    def on_casilla_list_highlighted(self, message: CasillaList.Highlighted) -> None:
        """Explain the casilla now under the cursor, then fetch its full help."""
        self._render_help(message.entry)
        entry = message.entry
        if entry is None or not isinstance(entry.field.address, ModeloFormCasillaAddressV1):
            return
        casilla_id = entry.field.address.casilla_id
        if (str(casilla_id), self._language) not in self._cards:
            self.run_worker(partial(self._fetch_card, entry), group="workbench-help", exclusive=True)

    async def _fetch_card(self, entry: CasillaListEntry) -> None:
        address = entry.field.address
        if not isinstance(address, ModeloFormCasillaAddressV1):
            return
        try:
            card = await asyncio.to_thread(self._reader.help_card, address.casilla_id, self._language)
        except Exception as failure:
            get_logger(__name__).error(
                "modelo workbench help could not be assembled: %s", type(failure).__qualname__, exc_info=True
            )
            return
        self._cards[(str(address.casilla_id), self._language)] = card
        highlighted = self.query_one(CasillaList).highlighted
        if highlighted is not None and highlighted.key == entry.key:
            self._render_help(highlighted)

    def _render_help(self, entry: CasillaListEntry | None) -> None:
        band = self.query_one("#wb-help", Static)
        if entry is None:
            band.update(tr("tui.modelo.workbench.help.empty"))
            return
        field = entry.field
        lines = [self._help_title(entry)]
        state = f"{ORIGIN_GLYPHS[field.origin]} {tr(origin_words_key(field.origin))}"
        lines.append(f"{state} · {editability_text(field)}")
        lines.append(field.help or tr("tui.modelo.workbench.help.no_explanation"))
        card = None
        if isinstance(field.address, ModeloFormCasillaAddressV1):
            card = self._cards.get((str(field.address.casilla_id), self._language))
        if card is not None:
            lines.extend(self._card_lines(card))
        if band.has_class("-expanded"):
            lines.append(tr("tui.modelo.workbench.help.keys", keys=self._all_keys_text()))
        band.update("\n".join(lines))

    def _all_keys_text(self) -> str:
        descriptions = {**_LIST_LOCALE_KEYS, **_SCREEN_LOCALE_KEYS}
        return " · ".join(self._key_label(key, descriptions[key]) for key in _FOOTER_PRIORITY)

    def _help_title(self, entry: CasillaListEntry) -> str:
        field = entry.field
        box = f"[{field.box}] " if field.box else ""
        title = f"{box}{field.label.text}"
        if field.label.disclosure is not ModeloFormTextDisclosure.LOCALIZED:
            title = f"{title} ({tr(f'tui.modelo.workbench.disclosure.{field.label.disclosure.value}')})"
        return title

    @staticmethod
    def _card_lines(card: ModeloCasillaHelpCardV1) -> list[str]:
        lines: list[str] = []
        if card.formula is not None:
            lines.append(tr("tui.modelo.workbench.help.formula", formula=card.formula.text))
        for origin in card.origins:
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

    # ── navigation ──────────────────────────────────────────────────────

    def on_option_list_option_selected(self, message: OptionList.OptionSelected) -> None:
        """Open the page or section chosen in the navigator."""
        option_id = message.option.id or ""
        kind, _, rest = option_id.partition(":")
        page_text, _, section_id = rest.partition(":")
        if not page_text.isdigit():
            return
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
        """Show the previous or next page."""
        self._show_page(self._page_index + delta)

    def action_cycle_filter(self) -> None:
        """Show all fields, then only what needs attention, then only the filer's own values."""
        position = _FILTER_ORDER.index(self._filter)
        self._filter = _FILTER_ORDER[(position + 1) % len(_FILTER_ORDER)]
        self._render_page()

    def action_toggle_density(self) -> None:
        """Show fields on one line or two."""
        casilla_list = self.query_one(CasillaList)
        density: Density = "compact" if casilla_list.density == "comfortable" else "comfortable"
        casilla_list.set_density(density)

    def action_toggle_help(self) -> None:
        """Give the help band more room and every key's name, or return it to its usual size."""
        self.query_one("#wb-help", Static).toggle_class("-expanded")
        self._render_help(self.query_one(CasillaList).highlighted)

    def action_leave(self) -> None:
        """Return to where the workbench was opened from, asking first when changes are staged."""
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

    def _notice(self, message: str) -> None:
        self.query_one("#wb-notice", Static).update(message)

    def _edit_unavailable(self) -> None:
        refusal = self._reader.edit_refusal()
        self._notice(refusal or tr("tui.modelo.workbench.editability.no_admission"))

    def _refresh_after_staging(self) -> None:
        self._render_progress()
        self._render_navigator()
        self._render_page()

    def on_casilla_list_edit_requested(self, message: CasillaList.EditRequested) -> None:
        """Open the editor for the casilla under the cursor, or say why it cannot be edited."""
        field = message.entry.field
        actions = self._actions
        form = self.form
        if actions is None or form is None or not form.edit_admitted:
            self._edit_unavailable()
            return
        if field.editability not in TYPED_EDITABILITIES:
            self._notice(editability_text(field))
            return
        card = None
        if isinstance(field.address, ModeloFormCasillaAddressV1):
            card = self._cards.get((str(field.address.casilla_id), self._language))
        probe = WorkbenchEditSession(self._language)
        self.app.push_screen(
            CasillaEditorScreen(
                field,
                parse=actions.parse,
                language=self._language,
                limits=() if card is None else card.constraints,
                can_clear=probe.stage_clear(field) is None,
                can_restore=probe.stage_restore(field) is None,
            ),
            partial(self._editor_closed, message.entry),
        )

    def _editor_closed(self, entry: CasillaListEntry, decision: EditorDecision | None) -> None:
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

    def _after_stage(self, refusal: StageRefusal | None) -> None:
        if refusal is not None:
            self._notice(tr(f"tui.modelo.workbench.stage_refused.{refusal.value}"))
            return
        self._notice("")
        self._refresh_after_staging()

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
                form, language=self._language, staged=self._session.display(), focus=message.entry.key
            ),
            self._sources_closed,
        )

    def _sources_closed(self, choice: SourcesChoice | None) -> None:
        if isinstance(choice, GoToCasilla):
            self._go_to(choice.key)
        elif isinstance(choice, OpenSourceSurface):
            self._open_surface(choice)

    def _go_to(self, key: AddressKey) -> None:
        index = page_of(self._pages, key)
        if index is None:
            return
        self._show_page(index)
        casilla_list = self.query_one(CasillaList)
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
        self.app.push_screen(EditReviewScreen(self._session.changes, notes=notes, at_risk=at_risk), self._review_closed)

    @staticmethod
    def _entries_unknown(form: ModeloWorkForm) -> bool:
        """Whether the declaration holds a calculation that does not record which values the filer typed."""
        return form.calculation_revision_id is not None and not form.operator_entries_known

    @staticmethod
    def _unattributed_boxes(form: ModeloWorkForm, *, excluding: frozenset[AddressKey] = frozenset()) -> tuple[str, ...]:
        """The boxes holding a value nobody is recorded as having typed, which a recalculation returns to source."""
        return tuple(
            f"[{field.box}]" if field.box else field.label.text
            for field in form.fields()
            if field.origin is ModeloFormOrigin.DEFAULT_TO_CONFIRM and address_key(field.address) not in excluding
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
        progress = workbench_progress(load.form, staged=staged, verified=load.verified, filed=load.filed)
        actions = self._actions
        action = progress.next_action
        if action is NextAction.APPLY:
            self.action_review()
        elif action is NextAction.RESOLVE and load.form.verification is not None:
            self.action_issues()
        elif action in {NextAction.FILL, NextAction.RESOLVE}:
            self.query_one(CasillaList).action_attention(1)
        elif actions is None:
            self._edit_unavailable()
        elif action is NextAction.CALCULATE:
            self._calculate(actions)
        elif action is NextAction.VERIFY:
            self._run_operation(actions.verify)
        elif action is NextAction.FILE:
            self._confirm_file(actions.file)

    def action_calculate(self) -> None:
        """Recalculate the declaration now, keeping the filer's values."""
        actions = self._actions
        if actions is None:
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
                message=at_risk_text(self._unattributed_boxes(form)),
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
        """List what the last verification found, and go to the box of the finding the filer picks."""
        form = self.form
        if form is None:
            return
        if form.verification is None:
            self._notice(tr("tui.modelo.workbench.issues.verdict.none"))
            return

        def closed(key: AddressKey | None) -> None:
            if key is not None:
                self._go_to(key)

        self.app.push_screen(WorkbenchIssuesScreen(form), closed)

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
        self._notice(tr("tui.modelo.workbench.operation.done"))
        projection = outcome.view_model.projection
        actions = self._actions
        if actions is not None:
            self.run_worker(partial(asyncio.to_thread, actions.refresh_product), group="workbench-refresh")
        if projection.definition_id == MODELO_EXPORT_OPERATION_DEFINITION_ID and actions is not None:
            self.run_worker(partial(self._state_export_result, actions, projection), group="workbench-export")
        changes_values = projection.definition_id in _VALUE_CHANGING_OPERATIONS
        before = self._load if changes_values else None
        self.run_worker(
            partial(self._read_after, before, yours),
            group="workbench-read",
            exclusive=True,
        )

    async def _read_after(self, before: ModeloWorkFormLoadV1 | None, yours: frozenset[AddressKey]) -> None:
        """Read the declaration again and, after a recalculation, show what it changed."""
        await self._read()
        after = self._load
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

    async def _state_export_result(
        self, actions: ModeloWorkbenchActionsV1, projection: OperationPublicProjectionV1
    ) -> None:
        self.app.push_screen(ModeloExportResultScreen(await actions.export_result(projection)))

    def action_toggle_appearance(self) -> None:
        """Switch between the two shipped appearances."""
        toggle_appearance(self.app)


__all__ = ["ModeloWorkbenchScreen"]
