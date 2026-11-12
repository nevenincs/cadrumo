"""The statements a declaration serves, offered together so the filer can make several in one review.

The form serves each statement the filer can make about a family of boxes:
the action, what it states, and what it does. The dialog lists every one the
form serves, in the order it serves them and in its words, each with a tick;
the workbench names no family and chooses none. Ticking several stages them
all, and leaving one staged earlier unticked withdraws it, so the dialog
always shows what the review will hold. Nothing is applied from here.

The dialog covers the header, so it can repeat the header's result line as its
first line.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, override

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.content import Content
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Static

from .....application.modelo.work_form_models import ModeloFormCarryAttestation
from .....core.i18n.render import tr
from ...components.language import localized, refresh_localized_widgets
from ...components.theme import tokenised
from .bulk_confirm import TickBox
from .dialog_width import fit_dialog_width
from .status_bar import StatusBar

if TYPE_CHECKING:
    from .header import StatusLine


class StatementsScreen(ModalScreen[tuple[ModeloFormCarryAttestation, ...] | None]):
    """Offer every statement the form serves; close with the ones ticked, in the order served."""

    SCOPED_CSS: ClassVar[bool] = False
    DEFAULT_CSS: ClassVar[str] = tokenised(
        """
        StatementsScreen #statements-backdrop {
            width: 1fr;
            height: 1fr;
            align: center middle;
        }
        StatementsScreen #statements-panel {
            width: $cadrumo-modal-width;
            height: $cadrumo-modal-height;
            border: $cadrumo-radius-overlay $primary;
            background: $surface;
            padding: $cadrumo-gutter-y $cadrumo-gutter;
        }
        StatementsScreen.-narrow #statements-panel {
            width: 100%;
        }
        StatementsScreen #statements-status {
            height: auto;
        }
        StatementsScreen #statements-title {
            text-style: bold;
            color: $foreground;
        }
        StatementsScreen #statements-intro {
            color: $secondary;
            height: auto;
            margin-bottom: $cadrumo-stack;
        }
        StatementsScreen #statements-body {
            height: 1fr;
        }
        StatementsScreen .statement-tick > .toggle--button {
            color: $foreground;
        }
        StatementsScreen .statement-tick.-on > .toggle--button {
            color: $text-success;
        }
        StatementsScreen .statement-words {
            height: auto;
            color: $secondary;
            padding: $cadrumo-space-0 $cadrumo-space-0 $cadrumo-space-0 $cadrumo-gutter;
            margin-bottom: $cadrumo-stack;
        }
        StatementsScreen #statements-actions {
            height: auto;
            margin-top: $cadrumo-stack;
            align-horizontal: right;
        }
        StatementsScreen #statements-actions Button {
            margin-left: $cadrumo-control-gap;
        }
        """
    )

    BINDINGS: ClassVar = [Binding("escape", "cancel", "", show=False)]

    def __init__(
        self,
        statements: tuple[ModeloFormCarryAttestation, ...],
        *,
        staged: frozenset[int] = frozenset(),
        status_line: StatusLine | None = None,
    ) -> None:
        """Hold every statement the form serves, in its order.

        ``staged`` holds the positions among ``statements`` already staged,
        which open ticked. ``status_line`` is the header's result line, shown
        first because the dialog covers it.
        """
        super().__init__()
        self._statements = statements
        self._staged = staged
        self._status_line = status_line

    @property
    def statements(self) -> tuple[ModeloFormCarryAttestation, ...]:
        """The statements the dialog lists, in the order the form serves them."""
        return self._statements

    @override
    def compose(self) -> ComposeResult:
        with Container(id="statements-backdrop"), Vertical(id="statements-panel"):
            if self._status_line is not None:
                yield StatusBar(self._status_line, id="statements-status")
            yield localized(
                Static(tr("tui.modelo.statements.title"), id="statements-title", markup=False),
                "tui.modelo.statements.title",
            )
            yield localized(
                Static(tr("tui.modelo.statements.intro"), id="statements-intro", markup=False),
                "tui.modelo.statements.intro",
            )
            with VerticalScroll(id="statements-body"):
                for position, statement in enumerate(self._statements):
                    # The served words are shown as written, never read as markup.
                    yield TickBox(
                        Content(statement.action_words),
                        value=position in self._staged,
                        id=f"statement-{position}",
                        classes="statement-tick",
                        compact=True,
                    )
                    yield Static(statement.statement_words, classes="statement-words", markup=False)
            with Horizontal(id="statements-actions"):
                yield localized(
                    Button(tr("workspace.modelo.editor.cancel"), id="statements-cancel"),
                    "workspace.modelo.editor.cancel",
                )
                yield localized(
                    Button(
                        tr("tui.modelo.statements.stage"),
                        id="statements-stage",
                        variant="primary",
                        disabled=True,
                    ),
                    "tui.modelo.statements.stage",
                )

    def on_resize(self, event: events.Resize) -> None:
        """Take the whole width on a narrow terminal."""
        fit_dialog_width(self, event.size.width)

    def on_mount(self) -> None:
        """Fit the terminal and put the cursor on the first statement."""
        fit_dialog_width(self, self.app.size.width)
        if self._statements:
            self.query_one("#statement-0", Checkbox).focus()

    def chosen(self) -> tuple[ModeloFormCarryAttestation, ...]:
        """The statements ticked now, in the order the form serves them."""
        return tuple(
            statement
            for position, statement in enumerate(self._statements)
            if self.query_one(f"#statement-{position}", Checkbox).value
        )

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        """Offer staging once the ticks differ from what is staged."""
        del event
        ticked = frozenset(
            position
            for position in range(len(self._statements))
            if self.query_one(f"#statement-{position}", Checkbox).value
        )
        self.query_one("#statements-stage", Button).disabled = ticked == self._staged

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Close with the statements ticked, or with nothing."""
        if event.button.id == "statements-stage":
            self.dismiss(self.chosen())
            return
        self.dismiss(None)

    def action_cancel(self) -> None:
        """Close without staging or withdrawing anything."""
        self.dismiss(None)

    async def refresh_language(self) -> None:
        """Reword the dialog's own words; the statements keep the words the form served."""
        refresh_localized_widgets(self)


__all__ = ["StatementsScreen"]
