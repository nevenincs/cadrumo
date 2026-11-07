"""Navigate exact saved filings through the registered filing view."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import ClassVar, override

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Select, Static

from ....application.modelo.filing_projection import ModeloRelatedFilingProjection
from ....application.modelo.filing_record_view_operation import ModeloFilingRecordViewProjection
from ....core.errors.hierarchy import CadrumoError
from ....core.i18n.render import tr
from ..components.language import localized
from ..components.theme import tokenised
from ..components.widgets import ContentDataTable, ContentScroll
from .controller import timestamp_label


class SavedFilingScreen(ModalScreen[None]):
    """Browse saved history without opening a mutable declaration in its place."""

    BINDINGS: ClassVar = [Binding("escape", "close", show=False)]
    DEFAULT_CSS = tokenised("""
    SavedFilingScreen { align: center middle; }
    #saved-filing-dialog {
        width: 100%; height: $cadrumo-modal-height;
        padding: $cadrumo-gutter-y $cadrumo-gutter;
        border: $cadrumo-radius-overlay $primary;
    }
    #saved-filing-body { height: 1fr; }
    #saved-filing-values { height: auto; min-height: 5; }
    #saved-filing-links { height: auto; }
    """)

    def __init__(
        self, filing_record_id: str, reader: Callable[[str], Awaitable[ModeloFilingRecordViewProjection]]
    ) -> None:
        """Retain the exact selection and its injected registered read."""
        super().__init__()
        self._selected = filing_record_id
        self._reader = reader
        self._view: ModeloFilingRecordViewProjection | None = None
        self._request = 0

    @override
    def compose(self) -> ComposeResult:
        with Vertical(id="saved-filing-dialog"):
            yield localized(Static(markup=False), "workspace.declarations.related_filings.title")
            with ContentScroll(id="saved-filing-body"):
                yield Select[str](
                    [], prompt=tr("workspace.declarations.related_filings.select"), id="saved-filing-select"
                )
                yield Static(id="saved-filing-notice", markup=False)
                yield ContentDataTable[str](id="saved-filing-links", cursor_type="row")
                yield localized(Static(markup=False), "workspace.declarations.related_filings.technical_values")
                yield ContentDataTable[str](id="saved-filing-values", cursor_type="row")
            yield localized(Button(id="saved-filing-retry"), "workspace.declarations.related_filings.retry")
            yield localized(Button(id="saved-filing-close"), "workspace.modelo.key.close")

    def on_mount(self) -> None:
        """Read the selected filing after its controls are mounted."""
        self._load(self._selected)

    def _load(self, filing_id: str) -> None:
        self._selected = filing_id
        self._request += 1
        self._view = None
        self.query_one("#saved-filing-notice", Static).update(tr("workspace.declarations.related_filings.loading"))
        self.query_one("#saved-filing-values", DataTable).clear(columns=True)
        self.query_one("#saved-filing-links", DataTable).clear(columns=True)
        self.run_worker(self._read(filing_id, self._request), group="saved-filing-read")

    async def _read(self, filing_id: str, request: int) -> None:
        try:
            view = await self._reader(filing_id)
        except CadrumoError:
            if request == self._request and self.is_mounted:
                self.query_one("#saved-filing-notice", Static).update(
                    tr("workspace.declarations.related_filings.failed")
                )
            return
        if request != self._request or not self.is_mounted:
            return
        if view.filing_record_id != filing_id or view.record.filing_record_id != filing_id:
            self.query_one("#saved-filing-notice", Static).update(tr("workspace.declarations.related_filings.failed"))
            return
        self._view = view
        picker = self.query_one("#saved-filing-select", Select)
        picker.set_options((self._label(row), row.filing_record_id) for row in view.related_filings)
        picker.value = filing_id
        self.query_one("#saved-filing-notice", Static).update(view.historical_display_words or "")
        links = self.query_one("#saved-filing-links", DataTable)
        links.add_column(tr("workspace.declarations.related_filings.title"))
        for row in view.related_filings:
            if row.filing_record_id == view.record.amends_filing_record_id:
                links.add_row(
                    tr("workspace.declarations.related_filings.base") + ": " + self._label(row),
                    key=row.filing_record_id,
                )
            elif row.amends_filing_record_id == filing_id:
                links.add_row(
                    tr("workspace.declarations.related_filings.corrections") + ": " + self._label(row),
                    key=row.filing_record_id,
                )
        self._render_values(view)

    @staticmethod
    def _label(row: ModeloRelatedFilingProjection) -> str:
        return " · ".join((row.kind_words, timestamp_label(row.filed_at), row.confirmation_words, row.status_words))

    def _render_values(self, view: ModeloFilingRecordViewProjection) -> None:
        table = self.query_one("#saved-filing-values", DataTable)
        table.add_column(tr("workspace.declarations.related_filings.field"))
        comparison = view.comparison
        if comparison is not None and comparison.availability == "available":
            for key in ("before", "after", "change"):
                table.add_column(tr("workspace.declarations.related_filings." + key))
            absent = tr("workspace.declarations.related_filings.absent")
            for row in comparison.rows:
                table.add_row(
                    str(row.casilla_id),
                    row.base_value if row.base_value is not None else absent,
                    row.selected_value if row.selected_value is not None else absent,
                    tr(
                        "workspace.declarations.related_filings.unchanged"
                        if row.change == "unchanged"
                        else "workspace.declarations.related_filings.changed"
                    ),
                )
        else:
            table.add_column(tr("workspace.declarations.related_filings.after"))
            for observed in view.historical_content.observations:
                table.add_row(str(observed.casilla_id), observed.value)

    def on_select_changed(self, event: Select.Changed) -> None:
        """Read another saved filing selected from the served group."""
        if event.select.id == "saved-filing-select" and isinstance(event.value, str) and event.value != self._selected:
            self._load(event.value)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Follow an exact preceding or subsequent filing link."""
        if event.data_table.id == "saved-filing-links" and event.row_key.value is not None:
            self._load(str(event.row_key.value))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Retry a read or return to the filing history."""
        if event.button.id == "saved-filing-close":
            self.action_close()
        elif event.button.id == "saved-filing-retry":
            self._load(self._selected)

    def action_close(self) -> None:
        """Return without changing any filing."""
        self.dismiss(None)
