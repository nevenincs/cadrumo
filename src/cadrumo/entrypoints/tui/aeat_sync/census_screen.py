"""AeatSyncCensusScreen and its protected projection rendering."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, cast, override

from textual.app import ComposeResult
from textual.widgets import DataTable, Static

from ....application.aeat_sync.workspace import (
    AeatSyncWorkspaceZone,
)
from ....core.i18n.render import tr
from ..components.cell_text import ellipsize
from ..components.widgets import ContentDataTable
from .controller import AeatSyncWorkspaceController

if TYPE_CHECKING:
    pass

from .census_evidence import populate_census_evidence_rows
from .screen_presentation import census_identity, census_value, fit_columns, status_label
from .screens import AeatSyncWorkspaceScreen


class AeatSyncCensusScreen(AeatSyncWorkspaceScreen):
    """Local census comparison and complete persisted AEAT evidence."""

    zone = AeatSyncWorkspaceZone.CENSUS
    HEADING_LOCALE_KEY = "tui.aeat_sync.census.title"

    def __init__(self, controller: AeatSyncWorkspaceController) -> None:
        """Build the census body."""
        super().__init__(controller, id="aeat-sync-census-screen")

    @override
    def compose_evidence(self) -> ComposeResult:
        yield Static(id="aeat-sync-census-captured", markup=False)
        yield ContentDataTable[str](id="aeat-sync-census-evidence", cursor_type="row", zebra_stripes=True)
        yield Static(id="aeat-sync-census-value", markup=False)

    @override
    def reword_evidence(self) -> None:
        """Reword census headings while keeping the selected observed value."""
        value = self.query_one("#aeat-sync-census-value", Static).content
        self._populate_evidence()
        self.query_one("#aeat-sync-census-value", Static).update(value)

    def _populate_evidence(self) -> None:
        observation = self.controller.projection.census_observation
        table = cast("DataTable[str]", self.query_one("#aeat-sync-census-evidence", DataTable))
        table.clear(columns=True)
        self.query_one("#aeat-sync-census-value", Static).update("")
        captured = self.query_one("#aeat-sync-census-captured", Static)
        table.display = observation is not None
        if observation is None:
            captured.update("")
            return
        captured.update(f"{observation.captured_at.isoformat()} · {observation.source_url}")
        available = max(18, self.app.size.width - 18)
        area_width, field_width = available // 4, available // 3
        table.add_column(tr("tui.aeat_sync.column.area"), width=area_width)
        table.add_column(tr("tui.aeat_sync.column.field"), width=field_width)
        table.add_column(tr("tui.aeat_sync.column.aeat_value"), width=available - area_width - field_width)
        populate_census_evidence_rows(table, observation)

    @override
    async def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        table = cast("DataTable[str]", event.data_table)
        if table.id == "aeat-sync-census-evidence":
            event.stop()
            self.query_one("#aeat-sync-census-value", Static).update(
                "\n".join(str(value) for value in table.get_row(event.row_key))
            )
            return
        await super().on_data_table_row_selected(event)

    _COLUMNS_LOCALE_KEYS: ClassVar[tuple[tuple[str, str, int], ...]] = (
        ("field", "tui.aeat_sync.column.field", 26),
        ("status", "tui.aeat_sync.column.status", 16),
        ("category", "tui.aeat_sync.column.category", 16),
    )
    """Census columns that stand alone, in priority order.

    Status ranks above the values, and a first ordering that put them below it
    was wrong: the values are the EVIDENCE, the status is the VERDICT, and an
    operator who cannot see whether a field is adopted or in conflict has lost
    the thing that tells them to act. Showing evidence for a verdict they
    cannot read is the worse trade.
    """

    _VALUE_COLUMNS_LOCALE_KEYS: ClassVar[tuple[tuple[str, str, int], ...]] = (
        ("local_value", "tui.aeat_sync.column.local_value", 22),
        ("aeat_value", "tui.aeat_sync.column.aeat_value", 22),
    )
    """The comparison pair, taken together or not at all.

    Dropping ONE side would leave a column headed "Local value" beside nothing
    to compare it against, which reads as a value AEAT does not hold rather
    than a column the terminal had no room for. Both or neither.
    """

    @override
    def populate_rows(self, table: DataTable[str]) -> None:
        """Render the census comparison, dropping columns before overflowing."""
        taken = fit_columns(self.app.size.width, self._COLUMNS_LOCALE_KEYS, self._VALUE_COLUMNS_LOCALE_KEYS)
        for name, header, size in taken:
            table.add_column(header, key=name, width=size)
        for row in self.controller.projection.census:
            cells = {
                "field": ellipsize(row.path, 32),
                "category": status_label(row.category),
                "status": status_label(row.status),
                # An unobserved side is WORDED. A blank cell beside a populated
                # one reads as "AEAT holds nothing", which is a different claim
                # from "nobody has looked" -- and the second is the truth
                # before any pull.
                "local_value": census_value(row.local_value),
                "aeat_value": census_value(row.aeat_value),
            }
            table.add_row(
                *(cells[name] for name, _, _ in taken),
                key=census_identity(row.path),
            )
        self._populate_evidence()
