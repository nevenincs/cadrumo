"""The box panel: what a casilla asks, where its value comes from, and a new value for it.

The panel answers the filer's questions about one box in the same order every
time: what the box asks, what it holds now and who put it there, where a
sourced value comes from, and whether it can be changed here and how. The new
value comes straight after those answers, with the format it takes right under
the input, and then the boxes it affects.

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
panel offers to open that area of the application.

The panel is as tall as what it says. When that is more than the terminal
holds, only the answers scroll, between the title and the input and actions,
so those stay in view on a small terminal however long the answers grow.
Because the panel covers the header, it can repeat the header's result line
as its first line, so the filer sees the result while changing a value.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from types import MappingProxyType
from typing import ClassVar, Final, override

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Static

from .....application.modelo.edit_parsing import MAX_EDIT_LEXEME_LENGTH
from .....application.modelo.source_policy import SourceFamily, SourceSurface, source_policy
from .....application.modelo.value_presentation import LOCALE_NUMBER_FORMATS
from .....application.modelo.work_form_models import (
    ModeloFormEditability,
    ModeloFormField,
    ModeloFormOrigin,
    ModeloFormScalar,
)
from .....core.external_constants import OutputLanguage
from .....core.i18n.render import tr
from .....core.logging import get_logger
from ...components.theme import tokenised
from .casilla_list import CasillaListEntry, description_text, value_text
from .dialog_width import fit_dialog_width
from .ports import WorkbenchChangeKind, WorkbenchParsed, WorkbenchParseOutcome, WorkbenchRefused
from .sources import OpenSourceSurface, surface_target
from .vocabulary import (
    SOURCE_WORDED_ORIGINS,
    TYPED_EDITABILITIES,
    editability_text,
    origin_source_words_key,
    origin_text,
)
from .wording import period_words

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

_RECORDED_LOCALE_KEY: Final[str] = "tui.modelo.workbench.editor.can_change.recorded"


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


def where_from_text(field: ModeloFormField) -> str | None:
    """Say where a sourced value comes from, beyond the kind of place its "Now" line already names.

    The answer names each source that feeds the box, and the earlier
    declarations a carried value is read from. The kind of place leads only
    when the "Now" line does not already say it, as for an assumed or a typed
    value over a source. A value taken from imported AEAT data names only
    that, because the sources its binding would otherwise read did not supply
    it.
    """
    source = field.source
    if source is None:
        return None
    family_words = tr(origin_source_words_key(ModeloFormOrigin.IMPORTED, source.family))
    lines: list[str] = [] if field.origin in SOURCE_WORDED_ORIGINS else [family_words]
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


def affects_text(feeds: tuple[str, ...]) -> str | None:
    """Name the boxes this box's value is used in; ``None`` when it feeds none.

    The help card already writes each one as the filer reads it, a bracketed
    box number or the phrase for a working figure, so they are only joined.
    """
    if not feeds:
        return None
    return ", ".join(feeds)


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


class CasillaEditorScreen(ModalScreen[EditorOutcome | None]):
    """The box panel for one casilla, reading every keystroke through the application parser."""

    SCOPED_CSS: ClassVar[bool] = False
    DEFAULT_CSS: ClassVar[str] = tokenised(
        """
        CasillaEditorScreen #editor-backdrop {
            width: 1fr;
            height: 1fr;
            align: center middle;
        }
        CasillaEditorScreen #editor-panel {
            width: $cadrumo-modal-width;
            height: auto;
            max-height: $cadrumo-modal-height;
            border: $cadrumo-radius-overlay $primary;
            background: $surface;
            padding: $cadrumo-gutter-y $cadrumo-gutter;
        }
        CasillaEditorScreen.-narrow #editor-panel {
            width: 100%;
            max-height: 100%;
        }
        CasillaEditorScreen #editor-head {
            dock: top;
            height: auto;
        }
        CasillaEditorScreen #editor-status {
            height: auto;
        }
        CasillaEditorScreen #editor-title {
            height: auto;
            text-style: bold;
            color: $foreground;
        }
        CasillaEditorScreen #editor-foot {
            dock: bottom;
            height: auto;
        }
        CasillaEditorScreen #editor-body {
            height: auto;
            max-height: 100%;
        }
        CasillaEditorScreen #editor-body:focus {
            background-tint: $foreground 4%;
        }
        CasillaEditorScreen .editor-block, CasillaEditorScreen #editor-entry {
            height: auto;
        }
        CasillaEditorScreen .editor-block-label {
            width: $cadrumo-term-width;
            color: $secondary;
        }
        CasillaEditorScreen .editor-block-text {
            width: 1fr;
            height: auto;
        }
        CasillaEditorScreen #editor-entry .editor-block-label {
            padding-top: $cadrumo-gutter-y;
        }
        CasillaEditorScreen #editor-field {
            width: 1fr;
            height: auto;
        }
        CasillaEditorScreen #editor-readback {
            height: auto;
        }
        CasillaEditorScreen #editor-readback.-refused {
            color: $error;
            text-style: bold;
        }
        CasillaEditorScreen #editor-readback.-parsed {
            color: $success;
        }
        CasillaEditorScreen #editor-readback.-confirm {
            color: $warning;
        }
        CasillaEditorScreen #editor-hint, CasillaEditorScreen #editor-keys {
            color: $secondary;
            height: auto;
        }
        CasillaEditorScreen #editor-alternatives, CasillaEditorScreen #editor-actions {
            height: auto;
            margin-top: $cadrumo-stack;
            align-horizontal: right;
        }
        CasillaEditorScreen #editor-alternatives Button, CasillaEditorScreen #editor-actions Button {
            margin-left: $cadrumo-control-gap;
        }
        CasillaEditorScreen #editor-alternatives Button:first-of-type,
        CasillaEditorScreen #editor-actions Button:first-of-type {
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
        feeds: tuple[str, ...] = (),
        status_line: str | None = None,
    ) -> None:
        """Bind the field, the parser, which of clear and restore it allows, and the boxes it feeds.

        With a ``read_only_reason`` the panel explains a box that cannot be
        changed here: it shows the reason, and the way to change it, in place
        of an input, and offers to open the area that owns the value's source.
        ``feeds`` names the boxes this box's value is used in. ``status_line``
        is the header's result line, shown first because the panel covers it.
        """
        super().__init__()
        self._field = field
        self._parse = parse
        self._language = language
        self._limits = limits
        self._read_only_reason = read_only_reason
        self._can_clear = can_clear and read_only_reason is None
        self._can_restore = can_restore and read_only_reason is None
        self._feeds = feeds
        self._status_line = status_line
        self._open_area = open_area_target(field) if read_only_reason is not None else None
        self._parsed: WorkbenchParsed | None = None
        self._prefill = (
            confirm_lexeme(field.value, language)
            if read_only_reason is None and field.origin is ModeloFormOrigin.DEFAULT_TO_CONFIRM
            else None
        )

    @property
    def read_only(self) -> bool:
        """Whether the panel explains the box instead of taking a value for it."""
        return self._read_only_reason is not None

    @property
    def open_area(self) -> SourceSurface | None:
        """The area the panel offers to open for the value's source; ``None`` when it offers none."""
        return self._open_area

    def _current(self) -> str:
        return value_text(CasillaListEntry(self._field), self._language)

    @staticmethod
    def _block(block_id: str, label_key: str, text: str) -> Horizontal:
        return Horizontal(
            Static(tr(label_key), classes="editor-block-label", markup=False),
            Static(text, classes="editor-block-text", id=f"{block_id}-text", markup=False),
            id=block_id,
            classes="editor-block",
        )

    def _answers(self) -> list[Horizontal]:
        field = self._field
        asks = description_text(field) or tr("tui.modelo.workbench.help.no_explanation")
        blocks = [
            self._block("editor-asks", "tui.modelo.workbench.editor.block.asks", asks),
            self._block(
                "editor-now", "tui.modelo.workbench.editor.block.now", f"{self._current()} · {origin_text(field)}"
            ),
        ]
        where = where_from_text(field)
        if where is not None:
            blocks.append(self._block("editor-where", "tui.modelo.workbench.editor.block.where_from", where))
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
        with Container(id="editor-backdrop"), Vertical(id="editor-panel"):
            with Vertical(id="editor-head"):
                if self._status_line is not None:
                    yield Static(self._status_line, id="editor-status", markup=False)
                yield Static(f"{box}{field.label.text}", id="editor-title", markup=False)
            with Vertical(id="editor-foot"):
                if not self.read_only:
                    yield from self._entry()
                affects = affects_text(self._feeds)
                if affects is not None:
                    yield self._block("editor-affects", "tui.modelo.workbench.editor.block.affects", affects)
                keys = self._keys_text()
                if keys is not None:
                    yield Static(keys, id="editor-keys", markup=False)
                yield from self._actions()
            with VerticalScroll(id="editor-body", can_focus=True):
                yield from self._answers()

    def on_resize(self, event: events.Resize) -> None:
        """Take the whole width on a narrow terminal."""
        fit_dialog_width(self, event.size.width)

    def on_mount(self) -> None:
        """Put the cursor in the value field, with an assumed value selected so typing replaces it."""
        fit_dialog_width(self, self.app.size.width)
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
        return self._prefill is not None and lexeme == self._prefill

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
        self._keep(advance=True)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Close with the filer's decision."""
        button = event.button.id
        if button == "editor-save-next":
            self._keep(advance=True)
        elif button == "editor-save":
            self._keep(advance=False)
        elif button == "editor-clear":
            self.dismiss(EditorDecision(kind=WorkbenchChangeKind.CLEAR))
        elif button == "editor-restore":
            self.dismiss(EditorDecision(kind=WorkbenchChangeKind.RESTORE))
        elif button == "editor-open":
            self.action_open_area()
        else:
            self.dismiss(None)

    def _keep(self, *, advance: bool) -> None:
        if self.read_only:
            return
        if self._confirming(self.query_one("#editor-input", Input).value.strip()):
            self.dismiss(
                EditorDecision(
                    kind=WorkbenchChangeKind.SET, value=self._field.value, display=self._current(), advance=advance
                )
            )
            return
        parsed = self._parsed
        if parsed is None:
            return
        self.dismiss(
            EditorDecision(kind=WorkbenchChangeKind.SET, value=parsed.value, display=parsed.display, advance=advance)
        )

    def action_keep(self) -> None:
        """Keep the value and stay on this box."""
        self._keep(advance=False)

    def action_open_area(self) -> None:
        """Close asking the workbench to open the area that owns the value's source, when the panel offers one."""
        if self._open_area is not None:
            self.dismiss(OpenSourceSurface(self._open_area))

    def action_cancel(self) -> None:
        """Close without a decision."""
        self.dismiss(None)


__all__ = [
    "EDITOR_HINT_KINDS",
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
