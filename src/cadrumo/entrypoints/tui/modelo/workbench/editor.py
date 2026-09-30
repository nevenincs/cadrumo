"""Edit one casilla: type a value, see how it will be read, and stage it.

The editor shows the box, its current value and where that value comes from,
what to type, the declared limits in words, and the box's help. Every keystroke
is read by the application's parser in the filer's language and read back
("will be read as 1.234,56 €"), or refused with a sentence saying how to fix it,
so the filer never stages a value the application would read differently. The
editor stages nothing itself: it closes with the filer's decision, and the
workbench's edit session records it.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import ClassVar, Final, override

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Static

from .....application.modelo.edit_parsing import MAX_EDIT_LEXEME_LENGTH
from .....application.modelo.work_form_models import ModeloFormField, ModeloFormScalar
from .....core.external_constants import OutputLanguage
from .....core.i18n.render import tr
from .....core.logging import get_logger
from ...components.theme import tokenised
from .casilla_list import CasillaListEntry, value_text
from .dialog_width import fit_dialog_width
from .ports import WorkbenchChangeKind, WorkbenchParsed, WorkbenchParseOutcome, WorkbenchRefused
from .vocabulary import ORIGIN_GLYPHS, origin_words_key

type Parser = Callable[[ModeloFormField, str, OutputLanguage], WorkbenchParseOutcome]


@dataclass(frozen=True, slots=True)
class EditorDecision:
    """What the filer decided in the editor."""

    kind: WorkbenchChangeKind
    value: ModeloFormScalar = None
    display: str = ""


EDITOR_HINT_KINDS: Final[tuple[str, ...]] = ("money", "ratio", "decimal", "integer", "boolean", "date", "year", "text")
"""The value kinds the editor explains with its own placeholder and format line; anything else reads as text."""


class CasillaEditorScreen(ModalScreen[EditorDecision | None]):
    """A modal editor for one casilla, reading every keystroke through the application parser."""

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
        }
        CasillaEditorScreen #editor-title {
            text-style: bold;
            color: $primary;
        }
        CasillaEditorScreen #editor-current {
            color: $secondary;
            margin-bottom: $cadrumo-stack;
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
        CasillaEditorScreen #editor-hint, CasillaEditorScreen #editor-help {
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

    BINDINGS: ClassVar = [Binding("escape", "cancel", "", show=False)]

    def __init__(
        self,
        field: ModeloFormField,
        *,
        parse: Parser,
        language: OutputLanguage,
        limits: tuple[str, ...] = (),
        can_clear: bool = False,
        can_restore: bool = False,
    ) -> None:
        """Bind the field, the parser and which of clear and restore this field allows."""
        super().__init__()
        self._field = field
        self._parse = parse
        self._language = language
        self._limits = limits
        self._can_clear = can_clear
        self._can_restore = can_restore
        self._parsed: WorkbenchParsed | None = None

    @override
    def compose(self) -> ComposeResult:
        field = self._field
        box = f"[{field.box}] " if field.box else ""
        current = value_text(CasillaListEntry(field), self._language)
        origin = f"{ORIGIN_GLYPHS[field.origin]} {tr(origin_words_key(field.origin))}"
        with Container(id="editor-backdrop"), Vertical(id="editor-panel"):
            yield Static(f"{box}{field.label.text}", id="editor-title", markup=False)
            yield Static(
                tr("tui.modelo.workbench.editor.current", value=current, origin=origin),
                id="editor-current",
                markup=False,
            )
            yield Input(
                placeholder=tr(f"tui.modelo.workbench.editor.placeholder.{self._hint_kind()}"),
                max_length=MAX_EDIT_LEXEME_LENGTH,
                id="editor-input",
            )
            yield Static("", id="editor-readback", markup=False)
            yield Static(self._hint(), id="editor-hint", markup=False)
            if field.help:
                yield Static(field.help, id="editor-help", markup=False)
            with Horizontal(id="editor-actions"):
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
        """Put the cursor in the value field."""
        fit_dialog_width(self, self.app.size.width)
        self.query_one("#editor-input", Input).focus()

    def _hint_kind(self) -> str:
        data_type = self._field.data_type
        return data_type if data_type in EDITOR_HINT_KINDS else "text"

    def _hint(self) -> str:
        parts = [tr(f"tui.modelo.workbench.editor.format.{self._hint_kind()}")]
        parts.extend(self._limits)
        return " ".join(parts)

    def on_input_changed(self, event: Input.Changed) -> None:
        """Read what the filer typed and say how it will be read, or why it cannot be."""
        readback = self.query_one("#editor-readback", Static)
        save = self.query_one("#editor-save", Button)
        lexeme = event.value.strip()
        readback.remove_class("-parsed", "-refused")
        self._parsed = None
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

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Save on Enter when the value reads cleanly."""
        self._save()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Close with the filer's decision."""
        button = event.button.id
        if button == "editor-save":
            self._save()
        elif button == "editor-clear":
            self.dismiss(EditorDecision(kind=WorkbenchChangeKind.CLEAR))
        elif button == "editor-restore":
            self.dismiss(EditorDecision(kind=WorkbenchChangeKind.RESTORE))
        else:
            self.dismiss(None)

    def _save(self) -> None:
        parsed = self._parsed
        if parsed is None:
            return
        self.dismiss(EditorDecision(kind=WorkbenchChangeKind.SET, value=parsed.value, display=parsed.display))

    def action_cancel(self) -> None:
        """Close without a decision."""
        self.dismiss(None)


__all__ = ["EDITOR_HINT_KINDS", "CasillaEditorScreen", "EditorDecision", "Parser"]
