"""The box panel: what a casilla asks, where its value comes from, and a new value for it.

The panel answers the filer's questions about one box in the same order every
time: what the box asks, what it holds now and who put it there, where a
sourced value comes from, and whether it can be changed here and how. What it
affects comes next, so the filer knows what a change reaches before typing it:
the chain of boxes from this one to the declaration's result, or that it does
not change the result at all. Then comes the new value, with the format it
takes right under the input.

Every keystroke is read by the application's parser in the filer's language
and read back ("will be read as 1.234,56 €"), or refused with a sentence saying
how to fix it, so the filer never keeps a value the application would read
differently. An assumed value opens prefilled and selected: Enter keeps it as
the filer's own, and typing replaces it. Enter, the highlighted action, keeps
the value and asks to move on to the next box that needs the filer; Ctrl+Enter
keeps it and stays. The panel keeps nothing itself: it closes with the filer's
decision, and the workbench's edit session records it for review.

A box that cannot be changed here still opens the panel, without an input:
the answers say why, and where the value can be changed instead, and the
panel offers to open that area of the application. A source the filer cannot
use is not named as where the value comes from: a box no entry of theirs can
reach here, which holds nothing, says only that it is empty and why, and a
carry with no earlier declaration names none. On a declaration recorded as
filed the answer says how to change it: by starting a correction.

The panel is as tall as what it says. When that is more than the terminal
holds, only the answers scroll, between the title and the input and actions,
so those stay in view on a small terminal however long the answers grow.

One panel serves two hosts. The workbench docks it at its foot, under the
list, so the box being changed and its neighbours stay in view; the panel
then says only which box it edits, and closes with a message the workbench
answers. On a terminal too short for both, the panel opens in a centred
dialog instead, which covers the header, so the panel repeats the header's
result line as its first line there.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from types import MappingProxyType
from typing import TYPE_CHECKING, ClassVar, Final, override

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Static

from .....application.modelo.casilla_help import ModeloCasillaHelpCardV1, ModeloHelpBoxV1
from .....application.modelo.edit_parsing import MAX_EDIT_LEXEME_LENGTH
from .....application.modelo.source_policy import SourceFamily, SourceSurface, source_policy
from .....application.modelo.value_presentation import LOCALE_NUMBER_FORMATS, format_casilla_value
from .....application.modelo.work_form_models import (
    ModeloFormCasillaAddressV1,
    ModeloFormEditability,
    ModeloFormField,
    ModeloFormOrigin,
    ModeloFormScalar,
    ModeloWorkForm,
)
from .....core.external_constants import OutputLanguage
from .....core.i18n.render import tr
from .....core.logging import get_logger
from ...components.theme import tokenised
from .casilla_list import CasillaListEntry, description_text, stated_value_text, value_text
from .dialog_width import fit_dialog_width
from .ports import WorkbenchChangeKind, WorkbenchParsed, WorkbenchParseOutcome, WorkbenchRefused
from .sources import OpenSourceSurface, surface_target
from .status_bar import StatusBar
from .vocabulary import (
    SOURCE_WORDED_ORIGINS,
    TYPED_EDITABILITIES,
    editability_text,
    holds_nothing,
    no_earlier_filing,
    origin_explanation,
    origin_source_words_key,
    origin_text,
    origin_words,
    set_by_form,
)
from .wording import period_words

if TYPE_CHECKING:
    from .header import ResultView, StatusLine
    from .session import StagedChange

type Parser = Callable[[ModeloFormField, str, OutputLanguage], WorkbenchParseOutcome]


@dataclass(frozen=True, slots=True)
class EditorDecision:
    """What the filer decided in the editor.

    ``advance`` asks the workbench to move on to the next box that needs the
    filer once the decision is kept; it is ``False`` when the filer asked to
    stay on this box.
    """

    kind: WorkbenchChangeKind
    value: ModeloFormScalar = None
    display: str = ""
    advance: bool = False


EDITOR_HINT_KINDS: Final[tuple[str, ...]] = ("money", "ratio", "decimal", "integer", "boolean", "date", "year", "text")
"""The value kinds the editor explains with its own placeholder and format line; anything else reads as text."""

_AREA_LOCALE_KEYS: Final[Mapping[SourceSurface, str]] = MappingProxyType(
    {
        SourceSurface.LEDGER: "tui.destination.ledger",
        SourceSurface.WITHHOLDING: "tui.destination.withholding",
        SourceSurface.PROFILE: "tui.destination.profile",
        SourceSurface.DECLARATIONS: "tui.destination.declarations",
        SourceSurface.NONE: "tui.modelo.workbench.editor.area.none",
    }
)
"""The words naming the place a sourced value is changed: an owning area by its name in the app menu."""

_CAN_CHANGE_LOCALE_KEYS: Final[Mapping[ModeloFormEditability, str]] = MappingProxyType(
    {
        ModeloFormEditability.EDITABLE_VALUE: "tui.modelo.workbench.editor.can_change.here",
        ModeloFormEditability.EDITABLE_OVERRIDE: "tui.modelo.workbench.editor.can_change.here",
        ModeloFormEditability.CALCULATED: "tui.modelo.workbench.editor.can_change.calculated",
        ModeloFormEditability.DESIGN_CONSTANT: "tui.modelo.workbench.editor.can_change.fixed",
    }
)
"""The answers to "can you change it?" that need nothing but the box's editability."""

#: What a declaration recorded as filed allows: no change here, and a correction to change it.
_RECORDED_LOCALE_KEY: Final[str] = "tui.modelo.workbench.editor.can_change.recorded"

_CHAIN_JOIN: Final[str] = " → "
_OTHERS_NAMED: Final[int] = 3
"""Up to this many other boxes a change reaches are named; past it, they are counted."""
"""Joins the boxes a change travels through, in the order it reaches them."""


def source_surface(field: ModeloFormField) -> SourceSurface:
    """The area of the application that owns the source of ``field``'s value, as the sources view opens it."""
    return field.bindings[0].policy.surface if field.bindings else SourceSurface.NONE


def area_words(surface: SourceSurface) -> str:
    """Name an owning area once, as the app menu names it."""
    return tr(_AREA_LOCALE_KEYS[surface])


def _area_words(field: ModeloFormField) -> str:
    return area_words(source_surface(field))


def can_change_text(field: ModeloFormField, language: OutputLanguage) -> str:
    """Answer "can you change it?" for one box, with the place to change it when it is not here.

    A value carried from a source that the filer may replace says what it
    replaces, when the box still shows the source's own value.
    """
    editability = field.editability
    key = _CAN_CHANGE_LOCALE_KEYS.get(editability)
    if key is not None:
        return tr(key)
    if editability is ModeloFormEditability.OVERRIDABLE_SOURCE:
        if field.origin is ModeloFormOrigin.IMPORTED and field.value is not None:
            source_value = value_text(CasillaListEntry(field), language)
            return tr("tui.modelo.workbench.editor.can_change.replace", value=source_value)
        return tr("tui.modelo.workbench.editor.can_change.replace_unknown")
    if editability is ModeloFormEditability.LOCKED_SOURCE:
        return tr("tui.modelo.workbench.editor.can_change.not_here", area=_area_words(field))
    if editability is ModeloFormEditability.EDIT_AT_PROFILE:
        return tr("tui.modelo.workbench.editor.can_change.not_here", area=tr(_AREA_LOCALE_KEYS[SourceSurface.PROFILE]))
    if editability is ModeloFormEditability.SOURCE_POLICY_UNDECIDED:
        return tr("tui.modelo.workbench.editor.can_change.not_yet", area=_area_words(field))
    return editability_text(field)


def read_only_reason(field: ModeloFormField, language: OutputLanguage, *, recorded: bool = False) -> str | None:
    """Why the panel for ``field`` has no input, and where to change it; ``None`` when it can be typed into.

    ``recorded`` is the declaration being recorded as filed, which makes every
    box read-only, whatever it would otherwise allow.
    """
    if recorded:
        return tr(_RECORDED_LOCALE_KEY)
    if field.editability in TYPED_EDITABILITIES:
        return None
    return can_change_text(field, language)


def _source_labels(field: ModeloFormField) -> tuple[str, ...]:
    """Name each source feeding ``field`` once, in the order the form lists them."""
    source = field.source
    keys = [binding.policy.label_key for binding in field.bindings]
    if not keys and source is not None and source.source_kind is not None:
        keys.append(source_policy(source.source_kind).label_key)
    return tuple(dict.fromkeys(tr(key) for key in keys))


def _unreachable_entry(field: ModeloFormField) -> bool:
    """Whether a box is fed by the filer's own entries, none of which can reach it here, and holds nothing."""
    source = field.source
    return (
        source is not None
        and source.family is SourceFamily.YOUR_ENTRIES
        and field.editability not in TYPED_EDITABILITIES
        and holds_nothing(field.value)
    )


def where_from_text(
    field: ModeloFormField, *, aeat_imported: date | None = None, language: OutputLanguage | None = None
) -> str | None:
    """Say where a sourced value comes from, beyond the kind of place its "Now" line already names.

    The answer names each source that feeds the box, and the earlier
    declarations a carried value is read from. The kind of place leads only
    when the "Now" line does not already say it, as for an assumed or a typed
    value over a source. A value taken from imported AEAT data names only
    that, with the day it was imported when ``aeat_imported`` gives it, because
    the sources its binding would otherwise read did not supply it. A box fed
    by the filer's entries that none of them can reach here, and that holds
    nothing, names no source: nothing the filer can use puts a value there. A
    carry with no earlier declaration to carry from names no filing either: it
    says why the box holds zero, or nothing when the "Now" line has said it.
    """
    source = field.source
    if source is None or _unreachable_entry(field):
        return None
    if no_earlier_filing(field):
        return origin_explanation(field)
    if source.family is SourceFamily.AEAT_DRAFT and aeat_imported is not None and language is not None:
        imported = field.model_copy(update={"origin": ModeloFormOrigin.IMPORTED})
        return origin_words(imported, aeat_imported=aeat_imported, language=language)
    family_words = tr(origin_source_words_key(ModeloFormOrigin.IMPORTED, source.family))
    worded = field.origin in SOURCE_WORDED_ORIGINS or set_by_form(field)
    lines: list[str] = [] if worded else [family_words]
    if source.family is not SourceFamily.AEAT_DRAFT:
        labels = _source_labels(field)
        if labels:
            lines.append(" · ".join(labels))
        lines.extend(
            tr(
                "tui.modelo.workbench.origin_source.imported.named_filing",
                modelo=filing.modelo,
                period=period_words(filing.period),
            )
            for filing in source.earlier_filings
        )
    return "\n".join(lines or [family_words])


def open_area_target(field: ModeloFormField) -> SourceSurface | None:
    """The area the panel can open for the source of ``field``'s value; ``None`` when no area owns it."""
    surface = source_surface(field)
    return surface if surface_target(surface) is not None else None


def _label(form: ModeloWorkForm | None, step: ModeloHelpBoxV1) -> str | None:
    """The form's own name for the box ``step`` passes through; ``None`` when the form does not list it."""
    if form is None:
        return None
    for field in form.fields():
        address = field.address
        if isinstance(address, ModeloFormCasillaAddressV1) and address.casilla_id == step.casilla_id:
            return field.label.text
    return None


def _result_step(form: ModeloWorkForm | None, step: ModeloHelpBoxV1, result: ResultView | None) -> str:
    """The result box at the chain's end, with what the declaration settles now once it is calculated."""
    settling = None if form is None else form.result
    calculated = (
        form is not None
        and settling is not None
        and settling.casilla_id == step.casilla_id
        and settling.value is not None
        and form.calculation_revision_id is not None
    )
    if calculated and result is not None and not result.failed:
        if result.settled is not None:
            words, amount = result.settled
            now = tr("tui.modelo.workbench.editor.affects.now", amount=amount)
            return f"{step.box} {words} {now}"
        return f"{step.box} {result.short_text}"
    label = _label(form, step)
    return step.box if label is None else f"{step.box} {label}"


def affects_text(
    card: ModeloCasillaHelpCardV1 | None, form: ModeloWorkForm | None = None, *, result: ResultView | None = None
) -> str | None:
    """Say what a change to this box reaches: the chain to the result, or that it does not change it.

    ``card`` is the box's help, ``None`` while it has not been read, when
    nothing is said: an unread card is never presented as a box that affects
    nothing. The chain runs along the fewest calculations from this box to the
    declaration's result, the first box named as the form names it and the
    result with what it settles now, from ``result``, the header's result for
    ``form``; the count of further boxes the change also reaches follows it. A
    box no calculation leads from to the result says so, with the boxes it is
    used in. Where the form names no result, the boxes this one is used in
    are listed, and nothing is said when there are none.
    """
    if card is None:
        return None
    if card.is_result:
        return tr("tui.modelo.workbench.editor.affects.is_result")
    reach = card.reach
    if reach is None:
        return ", ".join(card.feeds) or None
    if not reach.path:
        lines = [tr("tui.modelo.workbench.editor.affects.not_result")]
        if card.feeds:
            lines.append(tr("tui.modelo.workbench.help.feeds", boxes=", ".join(card.feeds)))
        return "\n".join(lines)
    steps = [step.box for step in reach.path]
    first = reach.path[0]
    label = _label(form, first)
    if label is not None and len(steps) > 1:
        steps[0] = f"{first.box} {label}"
    steps[-1] = _result_step(form, reach.path[-1], result)
    lines = [_CHAIN_JOIN.join(steps)]
    if reach.others:
        # A few boxes are named, so the filer can look at them; past that, how many.
        named = ", ".join(box.box for box in reach.others) if len(reach.others) <= _OTHERS_NAMED else len(reach.others)
        lines.append(tr("tui.modelo.workbench.editor.affects.others", count=named))
    return "\n".join(lines)


def confirm_lexeme(value: ModeloFormScalar, language: OutputLanguage) -> str | None:
    """The text an assumed value is prefilled as, in a form the filer can edit; ``None`` when it has none."""
    if value is None:
        return None
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, Decimal):
        return format(value, "f").replace(".", LOCALE_NUMBER_FORMATS[language].decimal_separator)
    return str(value)


type EditorOutcome = EditorDecision | OpenSourceSurface
"""What the panel closes with: the filer's decision about the value, or a request to open the source's area."""


class CasillaEditorPanel(Vertical):
    """The box panel for one casilla, reading every keystroke through the application parser.

    The panel keeps nothing and closes nothing itself: it posts
    :class:`CasillaEditorPanel.Closed` with the filer's decision, and its host,
    the workbench's dock or the centred dialog, answers it.
    """

    class Closed(Message):
        """The filer decided about the box: a value to keep, a request to open the source's area, or nothing."""

        def __init__(self, panel: CasillaEditorPanel, outcome: EditorOutcome | None) -> None:
            """Carry the panel that closed and what it closed with."""
            super().__init__()
            self.panel = panel
            self.outcome = outcome

    SCOPED_CSS: ClassVar[bool] = False
    DEFAULT_CSS: ClassVar[str] = tokenised(
        """
        CasillaEditorPanel {
            height: auto;
            background: $surface;
            padding: $cadrumo-gutter-y $cadrumo-gutter;
        }
        CasillaEditorPanel #editor-head {
            dock: top;
            height: auto;
        }
        CasillaEditorPanel #editor-status {
            height: auto;
        }
        CasillaEditorPanel #editor-title {
            height: auto;
            text-style: bold;
            color: $foreground;
        }
        CasillaEditorPanel #editor-foot {
            dock: bottom;
            height: auto;
        }
        CasillaEditorPanel #editor-body {
            height: auto;
            max-height: 100%;
        }
        CasillaEditorPanel #editor-body:focus {
            background-tint: $foreground 4%;
        }
        CasillaEditorPanel .editor-block, CasillaEditorPanel #editor-entry {
            height: auto;
        }
        CasillaEditorPanel .editor-block-label {
            width: $cadrumo-term-width;
            color: $secondary;
        }
        CasillaEditorPanel .editor-block-text {
            width: 1fr;
            height: auto;
        }
        CasillaEditorPanel #editor-entry .editor-block-label {
            padding-top: $cadrumo-gutter-y;
        }
        CasillaEditorPanel #editor-field {
            width: 1fr;
            height: auto;
        }
        CasillaEditorPanel #editor-readback {
            height: auto;
        }
        CasillaEditorPanel #editor-readback.-refused {
            color: $error;
            text-style: bold;
        }
        CasillaEditorPanel #editor-readback.-parsed {
            color: $success;
        }
        CasillaEditorPanel #editor-readback.-confirm {
            color: $warning;
        }
        CasillaEditorPanel #editor-hint, CasillaEditorPanel #editor-keys {
            color: $secondary;
            height: auto;
        }
        CasillaEditorPanel #editor-alternatives, CasillaEditorPanel #editor-actions {
            height: auto;
            margin-top: $cadrumo-stack;
            align-horizontal: right;
        }
        CasillaEditorPanel #editor-alternatives Button, CasillaEditorPanel #editor-actions Button {
            margin-left: $cadrumo-control-gap;
        }
        CasillaEditorPanel #editor-alternatives Button:first-of-type,
        CasillaEditorPanel #editor-actions Button:first-of-type {
            margin-left: $cadrumo-space-0;
        }
        """
    )

    BINDINGS: ClassVar = [
        Binding("escape", "cancel", "", show=False),
        Binding("ctrl+enter", "keep", "", show=False),
        Binding("a", "open_area", "", show=False),
    ]

    def __init__(
        self,
        field: ModeloFormField,
        *,
        parse: Parser,
        language: OutputLanguage,
        limits: tuple[str, ...] = (),
        can_clear: bool = False,
        can_restore: bool = False,
        read_only_reason: str | None = None,
        affects: str | None = None,
        calculation: str | None = None,
        status_line: StatusLine | None = None,
        recorded: bool = False,
        aeat_imported: date | None = None,
        staged: StagedChange | None = None,
    ) -> None:
        """Bind the field, the parser, which of clear and restore it allows, and what a change to it reaches.

        With a ``read_only_reason`` the panel explains a box that cannot be
        changed here: it shows the reason, and the way to change it, in place
        of an input, and offers to open the area that owns the value's source.
        ``affects`` is what :func:`affects_text` says a change reaches, and no
        "Affects" answer is shown without it. ``status_line``
        is the header's result line, shown first when the host covers it.
        ``recorded`` is the declaration being recorded as filed, whose "Now"
        line says what a box holds rather than asking the filer for a value.
        ``aeat_imported`` is the day the AEAT tax data the calculation took
        values from was imported, which a value taken from it names.
        """
        super().__init__(id="editor-panel")
        self._field = field
        self._staged = staged
        self._recorded = recorded
        self._aeat_imported = aeat_imported
        self._parse = parse
        self._language = language
        self._limits = limits
        self._read_only_reason = read_only_reason
        self._can_clear = can_clear and read_only_reason is None
        self._can_restore = can_restore and read_only_reason is None
        self._affects = affects
        self._calculation = calculation
        self._status_line = status_line
        self._open_area = open_area_target(field) if read_only_reason is not None else None
        self._parsed: WorkbenchParsed | None = None
        self._decided = False
        self._prefill = None
        if read_only_reason is None:
            if staged is not None:
                if staged.kind is WorkbenchChangeKind.SET and staged.value is not None:
                    self._prefill = (
                        format_casilla_value(staged.value, data_type=field.data_type, language=language)
                        if isinstance(staged.value, bool)
                        else confirm_lexeme(staged.value, language)
                    )
            elif field.origin is ModeloFormOrigin.DEFAULT_TO_CONFIRM:
                self._prefill = confirm_lexeme(field.value, language)

    @property
    def field(self) -> ModeloFormField:
        """The box this panel edits."""
        return self._field

    @property
    def read_only(self) -> bool:
        """Whether the panel explains the box instead of taking a value for it."""
        return self._read_only_reason is not None

    @property
    def open_area(self) -> SourceSurface | None:
        """The area the panel offers to open for the value's source; ``None`` when it offers none."""
        return self._open_area

    def _current(self) -> str:
        if self._staged is not None:
            return self._staged.text
        return value_text(CasillaListEntry(self._field, recorded=self._recorded), self._language)

    @staticmethod
    def _block(block_id: str, label_key: str, text: str) -> Horizontal:
        return Horizontal(
            Static(tr(label_key), classes="editor-block-label", markup=False),
            Static(text, classes="editor-block-text", id=f"{block_id}-text", markup=False),
            id=block_id,
            classes="editor-block",
        )

    def _now_text(self) -> str:
        """What the box holds and who put it there; a box holding nothing says only that, once, in its origin words."""
        if self._staged is not None:
            return f"{self._staged.text} · Δ {tr('tui.modelo.workbench.attention.staged')}"
        return self._saved_text()

    def _saved_text(self) -> str:
        """The saved value and its original provenance, distinct from the current draft."""
        field = self._field
        origin = origin_text(field, recorded=self._recorded, aeat_imported=self._aeat_imported, language=self._language)
        held = stated_value_text(CasillaListEntry(field, recorded=self._recorded), self._language)
        return origin if held is None else f"{held} · {origin}"

    def _answers(self) -> list[Horizontal]:
        field = self._field
        asks = description_text(field) or tr("tui.modelo.workbench.help.no_explanation")
        blocks = [
            self._block("editor-asks", "tui.modelo.workbench.editor.block.asks", asks),
            self._block("editor-now", "tui.modelo.workbench.editor.block.now", self._now_text()),
        ]
        if self._staged is not None:
            blocks.append(
                self._block("editor-saved", "tui.modelo.workbench.editor.block.saved_value", self._saved_text())
            )
        if self._calculation is not None:
            blocks.append(
                self._block("editor-calculation", "tui.modelo.workbench.editor.block.calculation", self._calculation)
            )
        where = where_from_text(field, aeat_imported=self._aeat_imported, language=self._language)
        if where is not None:
            blocks.append(self._block("editor-where", "tui.modelo.workbench.editor.block.where_from", where))
        if self._recorded:
            can_change = tr(_RECORDED_LOCALE_KEY)
        else:
            can_change = self._read_only_reason or can_change_text(field, self._language)
        blocks.append(self._block("editor-can-change", "tui.modelo.workbench.editor.block.can_change", can_change))
        return blocks

    def _entry(self) -> ComposeResult:
        with Horizontal(id="editor-entry"):
            yield Static(tr("tui.modelo.workbench.editor.block.new_value"), classes="editor-block-label", markup=False)
            with Vertical(id="editor-field"):
                yield Input(
                    value=self._prefill or "",
                    placeholder=tr(f"tui.modelo.workbench.editor.placeholder.{self._hint_kind()}"),
                    max_length=MAX_EDIT_LEXEME_LENGTH,
                    id="editor-input",
                )
                yield Static(self._hint(), id="editor-hint", markup=False)
                yield Static("", id="editor-readback", markup=False)

    def _keys_text(self) -> str | None:
        if not self.read_only:
            return tr(
                "tui.modelo.workbench.editor.keys",
                save_next=tr("tui.modelo.workbench.editor.save_next"),
                save=tr("tui.modelo.workbench.editor.save"),
            )
        if self._open_area is None:
            return None
        return tr(
            "tui.modelo.workbench.editor.open_keys",
            open=self._open_label(self._open_area),
            back=tr("tui.modelo.workbench.key.back"),
        )

    @staticmethod
    def _open_label(surface: SourceSurface) -> str:
        return tr("tui.modelo.workbench.editor.open_area", area=area_words(surface))

    def _actions(self) -> ComposeResult:
        if self.read_only:
            with Horizontal(id="editor-actions"):
                yield Button(tr("tui.modelo.workbench.key.back"), id="editor-cancel")
                if self._open_area is not None:
                    yield Button(self._open_label(self._open_area), id="editor-open", variant="primary")
            return
        if self._can_clear or self._can_restore:
            with Horizontal(id="editor-alternatives"):
                if self._can_clear:
                    yield Button(tr("tui.modelo.workbench.editor.clear"), id="editor-clear")
                if self._can_restore:
                    yield Button(tr("tui.modelo.workbench.editor.restore"), id="editor-restore")
        with Horizontal(id="editor-actions"):
            yield Button(tr("tui.modelo.workbench.editor.cancel"), id="editor-cancel")
            yield Button(tr("tui.modelo.workbench.editor.save"), id="editor-save", disabled=True)
            yield Button(
                tr("tui.modelo.workbench.editor.save_next"), id="editor-save-next", variant="primary", disabled=True
            )

    @override
    def compose(self) -> ComposeResult:
        field = self._field
        box = f"[{field.box}] " if field.box else ""
        with Vertical(id="editor-head"):
            if self._status_line is not None:
                yield StatusBar(self._status_line, id="editor-status")
            yield Static(f"{box}{field.label.text}", id="editor-title", markup=False)
        with Vertical(id="editor-foot"):
            if self._affects is not None:
                yield self._block("editor-affects", "tui.modelo.workbench.editor.block.affects", self._affects)
            if not self.read_only:
                yield from self._entry()
            keys = self._keys_text()
            if keys is not None:
                yield Static(keys, id="editor-keys", markup=False)
            yield from self._actions()
        with VerticalScroll(id="editor-body", can_focus=True):
            yield from self._answers()

    def on_mount(self) -> None:
        """Put the cursor in the value field, with an assumed value selected so typing replaces it."""
        if self.read_only:
            self.query_one("#editor-cancel", Button).focus()
            return
        field_input = self.query_one("#editor-input", Input)
        self._read(field_input.value)
        field_input.focus()

    def _hint_kind(self) -> str:
        data_type = self._field.data_type
        return data_type if data_type in EDITOR_HINT_KINDS else "text"

    def _hint(self) -> str:
        parts = [tr(f"tui.modelo.workbench.editor.format.{self._hint_kind()}")]
        parts.extend(self._limits)
        return " ".join(parts)

    def _confirming(self, lexeme: str) -> bool:
        return self._staged is None and self._prefill is not None and lexeme == self._prefill

    def _allow_keep(self, allowed: bool) -> None:
        for button_id in ("#editor-save", "#editor-save-next"):
            self.query_one(button_id, Button).disabled = not allowed

    def _read(self, text: str) -> None:
        readback = self.query_one("#editor-readback", Static)
        lexeme = text.strip()
        readback.remove_class("-parsed", "-refused", "-confirm")
        readback.display = bool(lexeme)
        self._parsed = None
        if self._confirming(lexeme):
            readback.update(tr("tui.modelo.workbench.editor.confirm_hint", value=self._current()))
            readback.add_class("-confirm")
            self._allow_keep(True)
            return
        if not lexeme:
            readback.update("")
            self._allow_keep(False)
            return
        try:
            outcome = self._parse(self._field, lexeme, self._language)
        except Exception as failure:
            get_logger(__name__).error("the casilla parser failed: %s", type(failure).__qualname__, exc_info=True)
            outcome = WorkbenchRefused(message=tr("tui.modelo.workbench.editor.unreadable"))
        if isinstance(outcome, WorkbenchParsed):
            self._parsed = outcome
            readback.update(tr("tui.modelo.workbench.editor.read_as", value=outcome.display))
            readback.add_class("-parsed")
            self._allow_keep(True)
            return
        readback.update(f"× {outcome.message}")
        readback.add_class("-refused")
        self._allow_keep(False)

    def on_input_changed(self, event: Input.Changed) -> None:
        """Read what the filer typed and say how it will be read, or why it cannot be."""
        self._read(event.value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Keep the value on Enter when it reads cleanly, and ask to move on to the next box."""
        event.stop()
        self._keep(advance=True)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Close with the filer's decision."""
        event.stop()
        button = event.button.id
        if button == "editor-save-next":
            self._keep(advance=True)
        elif button == "editor-save":
            self._keep(advance=False)
        elif button == "editor-clear":
            self._close(EditorDecision(kind=WorkbenchChangeKind.CLEAR))
        elif button == "editor-restore":
            self._close(EditorDecision(kind=WorkbenchChangeKind.RESTORE))
        elif button == "editor-open":
            self.action_open_area()
        else:
            self._close(None)

    def _close(self, outcome: EditorOutcome | None) -> None:
        """Hand the filer's decision to the host, once; the panel ignores what follows until it is gone."""
        if self._decided:
            return
        self._decided = True
        self.post_message(self.Closed(self, outcome))

    def _keep(self, *, advance: bool) -> None:
        if self.read_only:
            return
        if self._confirming(self.query_one("#editor-input", Input).value.strip()):
            self._close(
                EditorDecision(
                    kind=WorkbenchChangeKind.SET, value=self._field.value, display=self._current(), advance=advance
                )
            )
            return
        parsed = self._parsed
        if parsed is None:
            return
        self._close(
            EditorDecision(kind=WorkbenchChangeKind.SET, value=parsed.value, display=parsed.display, advance=advance)
        )

    def action_keep(self) -> None:
        """Keep the value and stay on this box."""
        self._keep(advance=False)

    def action_open_area(self) -> None:
        """Close asking the workbench to open the area that owns the value's source, when the panel offers one."""
        if self._open_area is not None:
            self._close(OpenSourceSurface(self._open_area))

    def action_cancel(self) -> None:
        """Close without a decision."""
        self._close(None)


class CasillaEditorScreen(ModalScreen[EditorOutcome | None]):
    """The box panel in a centred dialog, for a terminal too short to dock it under the list.

    The dialog is only a container: it holds one :class:`CasillaEditorPanel`,
    built from the same arguments, and closes with whatever the panel decides.
    """

    SCOPED_CSS: ClassVar[bool] = False
    DEFAULT_CSS: ClassVar[str] = tokenised(
        """
        CasillaEditorScreen #editor-backdrop {
            width: 1fr;
            height: 1fr;
            align: center middle;
        }
        CasillaEditorScreen CasillaEditorPanel {
            width: $cadrumo-modal-width;
            max-height: $cadrumo-modal-height;
            border: $cadrumo-radius-overlay $primary;
        }
        CasillaEditorScreen.-narrow CasillaEditorPanel {
            width: 100%;
            max-height: 100%;
        }
        """
    )

    def __init__(
        self,
        field: ModeloFormField,
        *,
        parse: Parser,
        language: OutputLanguage,
        limits: tuple[str, ...] = (),
        can_clear: bool = False,
        can_restore: bool = False,
        read_only_reason: str | None = None,
        affects: str | None = None,
        calculation: str | None = None,
        status_line: StatusLine | None = None,
        recorded: bool = False,
        aeat_imported: date | None = None,
        staged: StagedChange | None = None,
    ) -> None:
        """Build the panel the dialog holds; the arguments are the panel's own."""
        super().__init__()
        self._panel = CasillaEditorPanel(
            field,
            parse=parse,
            language=language,
            limits=limits,
            can_clear=can_clear,
            can_restore=can_restore,
            read_only_reason=read_only_reason,
            affects=affects,
            calculation=calculation,
            status_line=status_line,
            recorded=recorded,
            aeat_imported=aeat_imported,
            staged=staged,
        )

    @property
    def panel(self) -> CasillaEditorPanel:
        """The panel this dialog holds."""
        return self._panel

    @property
    def read_only(self) -> bool:
        """Whether the panel explains the box instead of taking a value for it."""
        return self._panel.read_only

    @property
    def open_area(self) -> SourceSurface | None:
        """The area the panel offers to open for the value's source; ``None`` when it offers none."""
        return self._panel.open_area

    @override
    def compose(self) -> ComposeResult:
        with Container(id="editor-backdrop"):
            yield self._panel

    def on_resize(self, event: events.Resize) -> None:
        """Take the whole width on a narrow terminal."""
        fit_dialog_width(self, event.size.width)

    def on_mount(self) -> None:
        """Take the whole width when the terminal is already narrow."""
        fit_dialog_width(self, self.app.size.width)

    def on_casilla_editor_panel_closed(self, message: CasillaEditorPanel.Closed) -> None:
        """Close with the panel's decision."""
        message.stop()
        self.dismiss(message.outcome)


__all__ = [
    "EDITOR_HINT_KINDS",
    "CasillaEditorPanel",
    "CasillaEditorScreen",
    "EditorDecision",
    "EditorOutcome",
    "Parser",
    "affects_text",
    "area_words",
    "can_change_text",
    "confirm_lexeme",
    "open_area_target",
    "read_only_reason",
    "source_surface",
    "where_from_text",
]
