"""The reference area: the bundled public reads, each answered as its command answers it.

The area reads no profile and needs no session. It lists every read the
shared reference service offers and opens the one the person chooses.
"""

from __future__ import annotations

from typing import ClassVar, cast, override

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import DataTable, Static

from ....core.i18n.render import tr
from ..components.account_chrome import AccountChromeScreen
from ..components.theme import BASE_CSS, tokenised
from ..components.widgets import ContentDataTable, ContentScroll
from ..navigation import TuiScreenContextV1
from .read_screen import ReferenceReadScreen
from .reads import ReferenceQuery, ReferenceRead
from .texts import read_label, read_summary


class ReferenceScreen(AccountChromeScreen):
    """List the reference reads and open the one the person chooses."""

    BINDINGS: ClassVar = [Binding("escape", "close", "", show=False)]
    CSS = BASE_CSS + tokenised(
        """
        #reference-page { width: 100%; height: 1fr; overflow-x: hidden; }
        #reference-intro, #reference-hint, #reference-summary {
            height: auto;
            padding: $cadrumo-space-0 $cadrumo-space-1;
        }
        #reference-summary { margin: $cadrumo-stack $cadrumo-space-0 $cadrumo-space-0 $cadrumo-space-0; }
        #reference-reads { width: 100%; }
        """
    )

    @override
    def compose(self) -> ComposeResult:
        yield Static(tr("tui.reference.title"), classes="cadrumo-banner", markup=False)
        with ContentScroll(id="reference-page", classes="cadrumo-scroll"):
            yield Static(tr("tui.reference.intro"), id="reference-intro", classes="cadrumo-subtle", markup=False)
            yield ContentDataTable[str](id="reference-reads", cursor_type="row", zebra_stripes=True)
            yield Static(id="reference-summary", markup=False)
            yield Static(tr("tui.reference.list_hint"), id="reference-hint", classes="cadrumo-note", markup=False)

    def on_mount(self) -> None:
        """List every read the reference service answers."""
        table = cast("DataTable[str]", self.query_one("#reference-reads", DataTable))
        table.add_column(tr("tui.reference.column.read"))
        for read in ReferenceRead:
            table.add_row(read_label(read), key=read.value)
        table.focus()

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Say what the read under the cursor shows; a table cell would cut the sentence short."""
        if event.data_table.id != "reference-reads" or event.row_key.value is None:
            return
        self.query_one("#reference-summary", Static).update(read_summary(ReferenceRead(event.row_key.value)))

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Open the chosen read."""
        if event.data_table.id != "reference-reads" or event.row_key.value is None:
            return
        self.open_read(ReferenceRead(event.row_key.value))

    def open_read(self, read: ReferenceRead) -> None:
        """Show one read over this list."""
        self.app.push_screen(ReferenceReadScreen(ReferenceQuery(read)))

    def action_close(self) -> None:
        """Return to whatever opened the area."""
        self.dismiss(None)


def reference_screen_factory(context: TuiScreenContextV1, /) -> Screen[None]:
    """Build the reference area for an admitted workbench route."""
    del context
    return ReferenceScreen()


__all__ = ["ReferenceScreen", "reference_screen_factory"]
