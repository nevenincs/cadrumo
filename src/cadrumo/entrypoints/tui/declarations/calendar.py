"""Agenda-first host-neutral Declarations calendar screen."""

from __future__ import annotations

from typing import ClassVar, cast, override

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import DataTable, Input, Select, Static

from ....application.modelo.declarations_calendar import (
    DeclarationsCalendarEntryRefV1,
    DeclarationsCalendarProjectionV1,
    DeclarationsCalendarSource,
)
from ....application.overview.home import HomeAvailability
from ..components.theme import BASE_CSS, tokenised
from ..components.widgets import ContentDataTable, ContentScroll
from .controller import (
    DeclarationsCalendarController,
    calendar_aeat_label,
    calendar_date_label,
    calendar_legal_label,
    calendar_local_label,
    declarations_copy,
    natural_address,
    timestamp_label,
)
from .models import DeclarationsCalendarScopeV1


def _identity(row: DeclarationsCalendarEntryRefV1) -> str:
    modelo, year, period = row.semantic_key()
    return f"{modelo}|{year}|{period}"


class DeclarationsCalendarScreen(Screen[None]):
    """Three-control agenda over an injected immutable safe projection."""

    BINDINGS: ClassVar = [Binding("escape", "back", "", show=False)]
    CSS = BASE_CSS + tokenised(
        """
        .declarations-calendar-page { width: 100%; height: 1fr; }
        #declarations-calendar-search, #declarations-calendar-scope { width: 100%; }
        #declarations-calendar-agenda { width: 100%; max-width: 78; }
        #declarations-calendar-detail, #declarations-calendar-notice {
            width: 100%; height: auto; padding: 0 1;
        }
        #declarations-calendar-notice { color: $warning; text-style: bold; }
        """
    )

    def __init__(self, controller: DeclarationsCalendarController) -> None:
        """Retain the injected pure calendar controller."""
        super().__init__(id="declarations-calendar-screen")
        self.controller = controller
        self._scope = DeclarationsCalendarScopeV1.ALL
        self._selected_identity: str | None = controller.context_identity()
        self._hidden_restore_identity: str | None = None
        self._rows_by_identity: dict[str, DeclarationsCalendarEntryRefV1] = {}

    @override
    def compose(self) -> ComposeResult:
        yield Static(
            declarations_copy("tui.declarations.calendar.title"),
            classes="cadrumo-banner",
            markup=False,
        )
        with ContentScroll(
            id="declarations-calendar-page",
            classes="cadrumo-scroll declarations-calendar-page",
        ):
            yield Input(
                placeholder=declarations_copy("tui.declarations.calendar.search.placeholder"),
                id="declarations-calendar-search",
            )
            yield Select[str](
                tuple(
                    (
                        declarations_copy(f"tui.declarations.calendar.scope.{scope.value}"),
                        scope.value,
                    )
                    for scope in DeclarationsCalendarScopeV1
                ),
                value=self._scope.value,
                allow_blank=False,
                id="declarations-calendar-scope",
            )
            yield ContentDataTable[str](
                id="declarations-calendar-agenda", cursor_type="row", zebra_stripes=True
            )
            yield Static(id="declarations-calendar-detail", markup=False)
            yield Static(id="declarations-calendar-notice", markup=False)

    def on_mount(self) -> None:
        """Build the table and place focus at the start of the three-control chain."""
        self._configure_table()
        self._refresh()
        focus = self.controller.context.focus
        if focus is not None and focus.semantic_key == "declarations.calendar.scope":
            self.query_one("#declarations-calendar-scope", Select).focus()
        elif focus is not None and focus.semantic_key.startswith("declarations.calendar"):
            self.query_one("#declarations-calendar-agenda", DataTable).focus()
        else:
            self.query_one("#declarations-calendar-search", Input).focus()

    def _configure_table(self) -> None:
        table = cast(
            "ContentDataTable[str]",
            self.query_one("#declarations-calendar-agenda", ContentDataTable),
        )
        table.add_column(declarations_copy("tui.declarations.calendar.column.close"), width=10)
        table.add_column(declarations_copy("tui.declarations.calendar.column.declaration"), width=16)
        table.add_column(declarations_copy("tui.declarations.calendar.column.legal"), width=13)
        table.add_column(declarations_copy("tui.declarations.calendar.column.local"), width=13)
        table.add_column(declarations_copy("tui.declarations.calendar.column.aeat"), width=12)

    def _refresh(self) -> None:
        table = cast("DataTable[str]", self.query_one("#declarations-calendar-agenda", DataTable))
        current = self._selected_row(table)
        if current is not None and self._hidden_restore_identity is None:
            self._selected_identity = _identity(current)
        query = self.query_one("#declarations-calendar-search", Input).value
        rows = self.controller.visible_entries(self._scope, query)
        table.clear(columns=False)
        self._rows_by_identity = {_identity(row): row for row in rows}
        for row in rows:
            table.add_row(
                calendar_date_label(row.adjusted_closes_on),
                natural_address(row.modelo, row.filing_year, row.period),
                calendar_legal_label(row.legal_status),
                calendar_local_label(row.local_filing_state),
                calendar_aeat_label(row.aeat_submission_state),
                key=_identity(row),
            )
        notice = self.query_one("#declarations-calendar-notice", Static)
        if rows:
            notice.update("")
            restore = self._selected_identity
            restored_index = next(
                (index for index, row in enumerate(rows) if _identity(row) == restore),
                None,
            )
            row_index = restored_index if restored_index is not None else 0
            table.move_cursor(row=row_index)
            if restored_index is not None:
                self._selected_identity = _identity(rows[row_index])
                self._hidden_restore_identity = None
            elif restore is None:
                self._selected_identity = _identity(rows[row_index])
            else:
                self._hidden_restore_identity = restore
            self._render_detail(rows[row_index])
        else:
            self._hidden_restore_identity = self._selected_identity
            self.query_one("#declarations-calendar-detail", Static).update("")
            notice.update(self._empty_copy(query))

    def _empty_copy(self, query: str) -> str:
        schedule = self.controller.source(DeclarationsCalendarSource.SCHEDULE)
        if schedule.availability is HomeAvailability.STALE:
            observed_at = schedule.observed_at
            if observed_at is None:
                raise ValueError("stale calendar schedule requires an observation time")
            return declarations_copy(
                "tui.declarations.calendar.empty.stale",
                observed=timestamp_label(observed_at),
            )
        if query or self.controller.projection.entries:
            return declarations_copy("tui.declarations.calendar.empty.search")
        return declarations_copy("tui.declarations.calendar.empty.known")

    def _selected_row(self, table: DataTable[str]) -> DeclarationsCalendarEntryRefV1 | None:
        if table.row_count == 0 or table.cursor_row < 0:
            return None
        key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value
        return self._rows_by_identity.get(str(key))

    def _render_detail(self, row: DeclarationsCalendarEntryRefV1) -> None:
        lines = [
            natural_address(row.modelo, row.filing_year, row.period),
            declarations_copy(
                "tui.declarations.calendar.detail.dates",
                opening=calendar_date_label(row.opens_on),
                payment=calendar_date_label(row.payment_cutoff_on),
                closing=calendar_date_label(row.adjusted_closes_on),
            ),
            declarations_copy(
                "tui.declarations.calendar.detail.axes",
                legal=calendar_legal_label(row.legal_status),
                local=calendar_local_label(row.local_filing_state),
                aeat=calendar_aeat_label(row.aeat_submission_state),
                receipt=declarations_copy(
                    "tui.declarations.calendar.justificante.unknown"
                    if row.justificante_verified is None
                    else (
                        "tui.declarations.calendar.justificante.verified"
                        if row.justificante_verified
                        else "tui.declarations.calendar.justificante.not_verified"
                    )
                ),
            ),
        ]
        for source in DeclarationsCalendarSource:
            state = self.controller.source(source)
            if state.observed_at is not None:
                observed = timestamp_label(state.observed_at)
            elif state.availability is HomeAvailability.NEVER_CAPTURED:
                observed = declarations_copy("tui.declarations.calendar.never_observed")
            elif state.availability is HomeAvailability.AVAILABLE:
                observed = declarations_copy("tui.declarations.calendar.observation.not_recorded")
            else:
                observed = declarations_copy("tui.declarations.calendar.observation.time_not_recorded")
            lines.append(
                declarations_copy(
                    "tui.declarations.calendar.detail.source",
                    source=declarations_copy(f"tui.declarations.calendar.source.{source.value}"),
                    availability=declarations_copy(
                        f"tui.declarations.availability.{state.availability.value}"
                    ),
                    observed=observed,
                )
            )
        lines.append(
            declarations_copy(
                "tui.declarations.calendar.detail.action",
                action=declarations_copy(
                    "tui.declarations.calendar.action.create"
                    if row.recovery_action is not None
                    else "tui.declarations.calendar.action.open"
                ),
            )
        )
        self.query_one("#declarations-calendar-detail", Static).update("\n".join(lines))

    def on_input_changed(self, event: Input.Changed) -> None:
        """Apply live Unicode AND search."""
        if event.input.id == "declarations-calendar-search":
            self._refresh()

    def on_select_changed(self, event: Select.Changed) -> None:
        """Apply the selected closed agenda scope."""
        if event.select.id != "declarations-calendar-scope" or not isinstance(event.value, str):
            return
        self._scope = DeclarationsCalendarScopeV1(event.value)
        self._refresh()

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Render details for the exact semantic row key."""
        table = cast("DataTable[str]", event.data_table)
        if table.id != "declarations-calendar-agenda":
            return
        row = self._rows_by_identity.get(str(event.row_key.value))
        if row is not None:
            identity = _identity(row)
            if self._hidden_restore_identity is None or identity == self._hidden_restore_identity:
                self._selected_identity = identity
                self._hidden_restore_identity = None
            self._render_detail(row)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Invoke only an injected natural-address or canonical recovery handoff."""
        table = cast("DataTable[str]", event.data_table)
        if table.id != "declarations-calendar-agenda":
            return
        row = self._rows_by_identity.get(str(event.row_key.value))
        if row is None:
            return
        if row.recovery_action is not None:
            if self.controller.recovery_handoff is not None:
                self.controller.recovery_handoff(row.recovery_action, row)
            else:
                self.query_one("#declarations-calendar-notice", Static).update(
                    declarations_copy("tui.declarations.refusal.handoff")
                )
        elif self.controller.entry_handoff is not None:
            self.controller.entry_handoff(row)
        else:
            self.query_one("#declarations-calendar-notice", Static).update(
                declarations_copy("tui.declarations.refusal.handoff")
            )

    def replace_projection(self, projection: DeclarationsCalendarProjectionV1) -> None:
        """Re-render a newly injected projection while preserving semantic focus."""
        self.controller.replace_projection(projection)
        self._refresh()

    def action_back(self) -> None:
        """Dismiss only this child screen."""
        self.dismiss(None)


__all__ = ["DeclarationsCalendarScreen"]
