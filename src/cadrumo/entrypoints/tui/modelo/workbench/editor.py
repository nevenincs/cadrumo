"""The box panel: what a casilla asks, where its value comes from, and a new value for it.

The panel answers the filer's questions about one box in the same order every
time: what the box asks, what it holds now and who put it there, where a
sourced value comes from, whether it can be changed here and how, and which
boxes it affects. Below those answers is the value input, when there is one.

Every keystroke is read by the application's parser in the filer's language
and read back ("will be read as 1.234,56 €"), or refused with a sentence saying
how to fix it, so the filer never keeps a value the application would read
differently. An assumed value opens prefilled and selected: Enter keeps it as
the filer's own, and typing replaces it. Enter keeps the value and asks to move
on to the next box that needs the filer; Ctrl+Enter keeps it and stays. The
panel keeps nothing itself: it closes with the filer's decision, and the
workbench's edit session records it for review.

A box that cannot be changed here still opens the panel, without an input:
the answers say why, and where the value can be changed instead.

The answers scroll between a fixed title and fixed actions, so the input and
the buttons stay in view on a small terminal however long the answers grow.
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
from .....application.modelo.source_policy import SourceSurface
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
from .vocabulary import TYPED_EDITABILITIES, editability_text, origin_source_words_key, origin_text
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
        SourceSurface.LEDGER: "tui.modelo.workbench.editor.area.ledger",
        SourceSurface.WITHHOLDING: "tui.modelo.workbench.editor.area.withholding",
        SourceSurface.PROFILE: "tui.modelo.workbench.editor.area.profile",
        SourceSurface.DECLARATIONS: "tui.modelo.workbench.editor.area.declarations",
        SourceSurface.NONE: "tui.modelo.workbench.editor.area.none",
    }
)
"""The words naming the place a sourced value is changed, per owning area."""

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


def _area_words(field: ModeloFormField) -> str:
    surface = field.bindings[0].policy.surface if field.bindings else SourceSurface.NONE
    return tr(_AREA_LOCALE_KEYS[surface])


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


def where_from_text(field: ModeloFormField) -> str | None:
    """Say which kind of place a sourced value comes from, naming the earlier declarations it is read from."""
    source = field.source
    if source is None:
        return None
    filings = source.earlier_filings
    if not filings:
        return tr(origin_source_words_key(ModeloFormOrigin.IMPORTED, source.family))
    return "; ".join(
        tr(
            "tui.modelo.workbench.origin_source.imported.named_filing",
            modelo=filing.modelo,
            period=period_words(filing.period),
        )
        for filing in filings
    )


def affects_text(feeds: tuple[str, ...]) -> str | None:
    """Name the boxes this box's value is used in; ``None`` when it feeds none."""
    if not feeds:
        return None
    return ", ".join(f"[{box}]" for box in feeds)


def confirm_lexeme(value: ModeloFormScalar, language: OutputLanguage) -> str | None:
    """The text an assumed value is prefilled as, in a form the filer can edit; ``None`` when it has none."""
    if value is None:
        return None
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, Decimal):
        return format(value, "f").replace(".", LOCALE_NUMBER_FORMATS[language].decimal_separator)
    return str(value)


class CasillaEditorScreen(ModalScreen[EditorDecision | None]):
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
            height: $cadrumo-modal-height;
            border: $cadrumo-radius-overlay $primary;
            background: $surface;
            padding: $cadrumo-gutter-y $cadrumo-gutter;
        }
        CasillaEditorScreen.-narrow #editor-panel {
            width: 100%;
        }
        CasillaEditorScreen #editor-title {
            text-style: bold;
            color: $primary;
        }
        CasillaEditorScreen #editor-body {
            height: 1fr;
        }
        CasillaEditorScreen #editor-body:focus {
            background-tint: $foreground 4%;
        }
        CasillaEditorScreen .editor-block, CasillaEditorScreen #editor-entry {
            height: auto;
        }
        CasillaEditorScreen .editor-block-label {
            width: 22;
            color: $secondary;
        }
        CasillaEditorScreen .editor-block-text {
            width: 1fr;
            height: auto;
        }
        CasillaEditorScreen #editor-entry .editor-block-label {
            padding-top: 1;
        }
        CasillaEditorScreen #editor-field {
            width: 1fr;
            height: auto;
        }
        CasillaEditorScreen #editor-readback {
            height: auto;
            margin-top: $cadrumo-tight;
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
        CasillaEditorScreen #editor-actions {
            height: auto;
            margin-top: $cadrumo-stack;
            align-horizontal: right;
        }
        CasillaEditorScreen #editor-actions Button {
            margin-left: $cadrumo-control-gap;
        }
        """
    )

    BINDINGS: ClassVar = [
        Binding("escape", "cancel", "", show=False),
        Binding("ctrl+enter", "keep", "", show=False),
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
    ) -> None:
        """Bind the field, the parser, which of clear and restore it allows, and the boxes it feeds.

        With a ``read_only_reason`` the panel explains a box that cannot be
        changed here: it shows the reason, and the way to change it, in place
        of an input. ``feeds`` names the boxes this box's value is used in.
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

    def _blocks(self) -> list[Horizontal]:
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
        affects = affects_text(self._feeds)
        if affects is not None:
            blocks.append(self._block("editor-affects", "tui.modelo.workbench.editor.block.affects", affects))
        return blocks

    @override
    def compose(self) -> ComposeResult:
        field = self._field
        box = f"[{field.box}] " if field.box else ""
        with Container(id="editor-backdrop"), Vertical(id="editor-panel"):
            yield Static(f"{box}{field.label.text}", id="editor-title", markup=False)
            with VerticalScroll(id="editor-body", can_focus=True):
                yield from self._blocks()
                if not self.read_only:
                    yield Static(self._hint(), id="editor-hint", markup=False)
            if not self.read_only:
                with Horizontal(id="editor-entry"):
                    yield Static(
                        tr("tui.modelo.workbench.editor.block.new_value"),
                        classes="editor-block-label",
                        markup=False,
                    )
                    with Vertical(id="editor-field"):
                        yield Input(
                            value=self._prefill or "",
                            placeholder=tr(f"tui.modelo.workbench.editor.placeholder.{self._hint_kind()}"),
                            max_length=MAX_EDIT_LEXEME_LENGTH,
                            id="editor-input",
                        )
                yield Static("", id="editor-readback", markup=False)
                yield Static(
                    tr(
                        "tui.modelo.workbench.editor.keys",
                        save_next=tr("tui.modelo.workbench.editor.save_next"),
                        save=tr("tui.modelo.workbench.editor.save"),
                    ),
                    id="editor-keys",
                    markup=False,
                )
            with Horizontal(id="editor-actions"):
                if self.read_only:
                    yield Button(tr("tui.modelo.workbench.key.back"), id="editor-cancel", variant="primary")
                    return
                yield Button(tr("tui.modelo.workbench.editor.cancel"), id="editor-cancel")
                if self._can_clear:
                    yield Button(tr("tui.modelo.workbench.editor.clear"), id="editor-clear")
                if self._can_restore:
                    yield Button(tr("tui.modelo.workbench.editor.restore"), id="editor-restore")
                yield Button(tr("tui.modelo.workbench.editor.save"), id="editor-save", variant="primary", disabled=True)

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

    def _read(self, text: str) -> None:
        readback = self.query_one("#editor-readback", Static)
        save = self.query_one("#editor-save", Button)
        lexeme = text.strip()
        readback.remove_class("-parsed", "-refused", "-confirm")
        self._parsed = None
        if self._confirming(lexeme):
            readback.update(tr("tui.modelo.workbench.editor.confirm_hint", value=self._current()))
            readback.add_class("-confirm")
            save.disabled = False
            return
        if not lexeme:
            readback.update("")
            save.disabled = True
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
            save.disabled = False
            return
        readback.update(f"× {outcome.message}")
        readback.add_class("-refused")
        save.disabled = True

    def on_input_changed(self, event: Input.Changed) -> None:
        """Read what the filer typed and say how it will be read, or why it cannot be."""
        self._read(event.value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Keep the value on Enter when it reads cleanly, and ask to move on to the next box."""
        self._keep(advance=True)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Close with the filer's decision."""
        button = event.button.id
        if button == "editor-save":
            self._keep(advance=False)
        elif button == "editor-clear":
            self.dismiss(EditorDecision(kind=WorkbenchChangeKind.CLEAR))
        elif button == "editor-restore":
            self.dismiss(EditorDecision(kind=WorkbenchChangeKind.RESTORE))
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

    def action_cancel(self) -> None:
        """Close without a decision."""
        self.dismiss(None)


__all__ = [
    "EDITOR_HINT_KINDS",
    "CasillaEditorScreen",
    "EditorDecision",
    "Parser",
    "affects_text",
    "can_change_text",
    "confirm_lexeme",
    "read_only_reason",
    "where_from_text",
]
