"""The operator's own Ledger entries, shown in full."""

from __future__ import annotations

from typing import ClassVar, cast, override

from textual.app import ComposeResult
from textual.widgets import DataTable, Static

from ....core.identity import TransactionId
from ..components.widgets import ContentDataTable
from .controller import (
    LedgerEntrySelected,
    LedgerWorkspaceController,
    LedgerWorkspaceScreen,
    ledger_copy,
    review_status_label,
)
from .workspace_presentation import ledger_workspace_page, restore_transaction_focus


class LedgerEntriesScreen(LedgerWorkspaceScreen):
    """Show each entry's own facts: date, amount, counterparty, classification.

    The column SET is responsive, the data is not. Seven columns do not fit the
    80-column floor, so narrow terminals drop the lowest-priority columns
    rather than overflowing the right edge, where content is unreachable. The
    order in `_COLUMNS` is that priority: date and description first because
    they identify the entry, review status last-but-kept because it is what the
    operator is acting on.

    Nothing is withheld -- every column returns as the terminal widens, and the
    projection behind it always carries the full record.
    """

    _COLUMNS: ClassVar[tuple[tuple[str, str, int], ...]] = (
        ("date", "tui.ledger.column.date", 10),
        ("description", "tui.ledger.column.description", 24),
        ("amount", "tui.ledger.column.amount", 14),
        ("review_status", "tui.ledger.column.review_status", 10),
        ("counterparty", "tui.ledger.column.counterparty", 18),
        ("classification", "tui.ledger.column.classification", 12),
        ("direction", "tui.ledger.column.direction", 10),
    )

    def __init__(self, controller: LedgerWorkspaceController) -> None:
        """Retain the injected read-only workspace controller."""
        super().__init__(controller, id="ledger-entries-screen")
        self.selected_transaction_id: TransactionId | None = None

    @override
    def compose(self) -> ComposeResult:
        yield Static(ledger_copy("tui.ledger.entries.title"), classes="cadrumo-banner")
        with ledger_workspace_page() as navigation:
            yield navigation
            yield ContentDataTable[str](id="ledger-entries", cursor_type="row", zebra_stripes=True)
            yield Static(id="ledger-refusal", classes="ledger-refusal", markup=False)

    def on_mount(self) -> None:
        """Populate the safe entry index using semantic row identities."""
        self.populate_navigation()
        table = self.query_one("#ledger-entries", ContentDataTable[str])
        self._fill_table(table, self.app.size.width)
        if not table.row_count:
            self.query_one("#ledger-refusal", Static).update(ledger_copy("tui.ledger.entries.empty"))
        navigation = cast("DataTable[str]", self.query_one("#ledger-navigation", DataTable))
        restore_transaction_focus(
            navigation=navigation,
            table=table,
            transaction_id=self.controller.restored_transaction_id(),
        )

    def _visible_columns(self, width: int) -> tuple[tuple[str, str, int], ...]:
        """Take columns in priority order while they still fit the terminal."""
        taken: list[tuple[str, str, int]] = []
        used = 0
        for column in self._COLUMNS:
            # The header is a floor on the rendered column, not merely a label:
            # a column narrower than its own heading is widened to fit it, so
            # budgeting the authored width alone under-counts every column
            # whose translated heading is longer and overflows the last one.
            # Two cells of padding per column, plus one for the scrollbar.
            cost = max(column[2], len(ledger_copy(column[1]))) + 2
            if used + cost > width - 1:
                break
            taken.append(column)
            used += cost
        return tuple(taken)

    def _fill_table(self, table: ContentDataTable[str], width: int) -> None:
        """Rebuild the table for this width, preserving row identity.

        A rebuild replaces every row object, so the cursor -- which addresses a
        row by position -- would silently land on whichever entry now occupies
        that index. The operator would be looking at one entry and acting on
        another. The remembered key is re-resolved after the rebuild so the
        selection follows the ENTRY across a resize, not the row number.
        """
        # The description is what the spare width is FOR: an identifier, a date
        # or a state word gains nothing from being wider than its content,
        # while a truncated description is the one cell the operator cannot
        # reconstruct from the others.
        names = [name for name, _, _ in self._visible_columns(width)]
        table.fill_column = names.index("description") if "description" in names else -1
        selected = None
        if table.is_valid_row_index(table.cursor_row):
            selected = table.ordered_rows[table.cursor_row].key.value
        table.clear(columns=True)
        columns = self._visible_columns(width)
        for name, key, size in columns:
            header = ledger_copy(key)
            # Same floor the budget assumed. Applied here too because the
            # table's own header-floor pass runs on resize, and this rebuild
            # replaces the columns it already corrected.
            table.add_column(header, key=name, width=max(size, len(header)))
        for row in self.controller.entry_rows():
            entry = row.source
            cells = {
                "date": entry.date,
                "description": entry.description,
                "amount": f"{entry.amount} {entry.currency}",
                "review_status": review_status_label(row.review_status),
                "counterparty": entry.counterparty,
                "classification": entry.business_classification,
                "direction": entry.direction,
            }
            table.add_row(*(cells[name] for name, _, _ in columns), key=row.transaction_id)
        if isinstance(table, ContentDataTable):
            table.absorb_surplus_width()
        if selected is not None:
            for index, ordered in enumerate(table.ordered_rows):
                if ordered.key.value == selected:
                    table.move_cursor(row=index)
                    break

    def on_resize(self) -> None:
        """Re-take the column set for the new width."""
        table = self.query_one("#ledger-entries", ContentDataTable[str])
        self._fill_table(table, self.app.size.width)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Route navigation or retain a safe semantic entry selection."""
        if self.handle_navigation_selection(event):
            return
        event_table = cast("DataTable[str]", event.data_table)
        transaction_id = event.row_key.value
        if event_table.id != "ledger-entries" or transaction_id is None:
            return
        self.selected_transaction_id = transaction_id
        self.post_message(LedgerEntrySelected(transaction_id))


__all__ = ["LedgerEntriesScreen"]
