"""Read the confirmed external filing without implying a local reconciliation."""

from typing import ClassVar, override

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from ....application.modelo.declarations_list import DeclarationListRow
from ....core.external_constants import OutputLanguage
from ....core.i18n.render import output_language, tr
from ..components.theme import tokenised
from ..components.widgets import ContentScroll
from .row_words import row_lines


class ExternalFilingDetailsScreen(ModalScreen[None]):
    """Present independent official completion and the installed action limits."""

    BINDINGS: ClassVar = [Binding("escape", "close", show=False), Binding("t", "technical", show=False)]
    DEFAULT_CSS = tokenised("""
    ExternalFilingDetailsScreen { align: center middle; }
    #external-filing-dialog {
        width: 100%; height: $cadrumo-modal-height;
        padding: $cadrumo-gutter-y $cadrumo-gutter;
        border: $cadrumo-radius-overlay $primary;
    }
    #external-filing-body { height: 1fr; }
    #external-filing-technical { display: none; height: auto; }
    #external-filing-close { width: 100%; }
    """)

    def __init__(self, row: DeclarationListRow) -> None:
        """Keep only the application row's safe observation metadata."""
        super().__init__()
        self.row = row

    @override
    def compose(self) -> ComposeResult:
        language = OutputLanguage(output_language())
        left, right = row_lines(self.row, language, can_open=False, can_create=False)
        with Vertical(id="external-filing-dialog"):
            with ContentScroll(id="external-filing-body"):
                yield Static("\n".join(left + right), markup=False)
                yield Static(tr("tui.declarations.list.aeat_unlinked.help.confirmed"), markup=False)
                yield Static(tr("tui.declarations.list.aeat_unlinked.help.no_refile"), markup=False)
                yield Static(tr("tui.declarations.list.aeat_unlinked.help.unavailable"), markup=False)
                yield Static(id="external-filing-technical", markup=False)
            yield Button(tr("tui.modelo.workbench.issues.technical"), id="external-filing-more")
            yield Button(tr("tui.modelo.workbench.key.close"), id="external-filing-close")

    def on_mount(self) -> None:
        """Make closing the primary keyboard action."""
        self.query_one("#external-filing-close", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Close or reveal the exact observed filing reference on request."""
        if event.button.id == "external-filing-more":
            self.action_technical()
        elif event.button.id == "external-filing-close":
            self.action_close()

    def action_technical(self) -> None:
        """Reveal the source reference without borrowing a local draft's amount."""
        detail = self.query_one("#external-filing-technical", Static)
        detail.display = not detail.display
        reference = None if self.row.calendar is None else self.row.calendar.aeat_reference_id
        detail.update(reference or tr("tui.declarations.calendar.none"))

    def action_close(self) -> None:
        """Return to the selected portfolio row."""
        self.dismiss(None)
