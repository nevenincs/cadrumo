"""One entry's lineage and history, read through ``ledger.track`` and the two history reads.

The typed history (``ledger.history.typed``) is shown first: it releases only
the facts each event declares and says when a model's reason or an export path
stayed in custody. The full event record (``ledger.history``) is read only when
the operator asks for it.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import ClassVar, cast, override

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, Checkbox, DataTable, Static

from ....application.ledger.history_operation import (
    LedgerHistoryProjection,
    LedgerHistoryRequest,
    LedgerHistoryTypedProjection,
)
from ....application.ledger.track_operation import LedgerTrackProjection, LedgerTrackRequest
from ....core.errors.hierarchy import CadrumoError
from ....core.i18n.render import tr
from ..account import AccountSessionExpiredError
from ..components.language import localized, repaint_tables
from ..components.theme import tokenised
from ..components.widgets import ContentDataTable
from ..components.workspace_host import replace_workspace_body
from .controller import LedgerWorkspaceController, LedgerWorkspaceScreen
from .entries_common import joined, lifecycle_label
from .entries_doors import LedgerEntriesDoorsV1, call_door_off_loop
from .workspace_presentation import door_refusal_text, ledger_workspace_page


def track_lines(track: LedgerTrackProjection) -> tuple[str, ...]:
    """Say where one entry came from, how it changed and which declarations used it."""
    tracking = track.tracking
    provenance = track.imported_provenance
    lines = [
        tr("tui.ledger.entry_tools.trace.state", state=lifecycle_label(tracking.lifecycle_state)),
        tr(
            "tui.ledger.entry_tools.trace.imported",
            provider=provenance.provider_name,
            file=provenance.source_filename,
            row=provenance.source_row_index,
        )
        if provenance is not None
        else tr("tui.ledger.entry_tools.trace.manual"),
        tr(
            "tui.ledger.entry_tools.trace.changes",
            edits=len(tracking.edit_lineage),
            evidence=len(tracking.evidence_provenance),
        ),
    ]
    lines.extend(
        tr(
            "tui.ledger.entry_tools.trace.lifecycle_change",
            when=item.changed_at,
            previous=lifecycle_label(item.previous_state),
            state=lifecycle_label(item.state),
            reason=item.reason or "-",
        )
        for item in tracking.lifecycle_lineage
    )
    if track.participated_in is None:
        lines.append(tr("tui.ledger.entry_tools.trace.no_participation"))
    else:
        lines.extend(
            tr(
                "tui.ledger.entry_tools.trace.participation",
                modelo=item.modelo,
                year=item.filing_year,
                period=item.period.code,
                state=item.revision_state,
            )
            for item in track.participated_in
        )
    return tuple(lines)


class LedgerEntryTraceScreen(LedgerWorkspaceScreen):
    """Show one entry's lineage, its typed history and, on request, its full event record."""

    CSS: ClassVar[str] = LedgerWorkspaceScreen.CSS + tokenised(
        """
        .entries-trace-row { height: auto; width: 100%; }
        .entries-trace-row > * { width: 1fr; min-width: 0; }
        #entries-trace-entry { height: auto; text-style: bold; }
        """
    )

    def __init__(
        self,
        controller: LedgerWorkspaceController,
        doors: LedgerEntriesDoorsV1,
        *,
        transaction_id: str,
        label: str,
        back_to: Callable[[LedgerWorkspaceController], LedgerWorkspaceScreen],
    ) -> None:
        """Keep the entry this screen traces and the screen Back returns to."""
        super().__init__(controller, id="ledger-entry-trace-screen")
        self.doors = doors
        self.transaction_id = transaction_id
        self.label = label
        self._back_to = back_to
        self.track: LedgerTrackProjection | None = None
        self.typed: LedgerHistoryTypedProjection | None = None
        self.full: LedgerHistoryProjection | None = None
        self.busy = False

    @override
    def compose(self) -> ComposeResult:
        yield localized(
            Static(tr("tui.ledger.entry_tools.trace.title"), classes="cadrumo-banner"),
            "tui.ledger.entry_tools.trace.title",
        )
        with ledger_workspace_page() as navigation:
            yield navigation
            yield Static(self.label, id="entries-trace-entry", markup=False)
            yield Static("", id="entries-trace-track", markup=False)
            with Horizontal(classes="entries-trace-row"):
                yield Checkbox(tr("tui.ledger.entry_tools.trace.siblings"), id="entries-trace-siblings")
                yield localized(
                    Button(tr("tui.ledger.entry_tools.trace.read"), id="entries-trace-read"),
                    "tui.ledger.entry_tools.trace.read",
                )
                yield localized(
                    Button(tr("tui.ledger.entry_tools.trace.full"), id="entries-trace-full"),
                    "tui.ledger.entry_tools.trace.full",
                )
            yield Static("", id="entries-trace-heading", classes="cadrumo-heading", markup=False)
            yield Static("", id="entries-trace-withheld", markup=False)
            yield ContentDataTable[str](id="entries-trace-history", cursor_type="row", zebra_stripes=True)
            yield Static("", id="ledger-flow-status", markup=False)
            yield Static("", id="ledger-refusal", classes="ledger-refusal", markup=False)

    def on_mount(self) -> None:
        """Read the lineage and typed history off the loop."""
        self._repaint()
        self._start(self._read_typed())

    @override
    async def refresh_language(self) -> None:
        """Reword the lineage and history in place."""
        await super().refresh_language()
        self.query_one("#entries-trace-siblings", Checkbox).label = tr("tui.ledger.entry_tools.trace.siblings")
        repaint_tables(self, self._repaint)

    def _history_request(self) -> LedgerHistoryRequest:
        return LedgerHistoryRequest(
            profile_id=self.doors.profile_id,
            transaction_prefix=self.transaction_id,
            include_split_siblings=self.query_one("#entries-trace-siblings", Checkbox).value,
        )

    def _start(self, work: Awaitable[None]) -> None:
        self.busy = True
        for button in self.query(Button):
            button.disabled = True
        self.query_one("#ledger-flow-status", Static).update(tr("tui.ledger.records.loading"))
        self.run_worker(work, exclusive=True, group="entries-trace")

    def _settle(self, error: CadrumoError | None = None) -> None:
        self.busy = False
        for button in self.query(Button):
            button.disabled = False
        self.query_one("#ledger-flow-status", Static).update("")
        if error is not None:
            self.query_one("#ledger-refusal", Static).update(door_refusal_text(error))

    async def _read_typed(self) -> None:
        track_request = LedgerTrackRequest(profile_id=self.doors.profile_id, transaction_prefix=self.transaction_id)
        history_request = self._history_request()
        try:
            track = await call_door_off_loop(lambda: self.doors.track(track_request))
            typed = await call_door_off_loop(lambda: self.doors.history_typed(history_request))
        except AccountSessionExpiredError as error:
            self._clear_private_view()
            self._settle(error)
            return
        except CadrumoError as error:
            self._settle(error)
            return
        self.track, self.typed, self.full = track, typed, None
        self._settle()
        self._paint()

    async def _read_full(self) -> None:
        request = self._history_request()
        try:
            full = await call_door_off_loop(lambda: self.doors.history(request))
        except AccountSessionExpiredError as error:
            self._clear_private_view()
            self._settle(error)
            return
        except CadrumoError as error:
            self._settle(error)
            return
        self.full = full
        self._settle()
        self._paint()

    def _repaint(self) -> None:
        """Redraw every table after a language change cleared them."""
        self.populate_navigation()
        self._paint()

    def _paint(self) -> None:
        self.query_one("#entries-trace-track", Static).update(
            "" if self.track is None else joined(track_lines(self.track))
        )
        table = cast("ContentDataTable[str]", self.query_one("#entries-trace-history", ContentDataTable))
        table.clear(columns=True)
        for key, column, width in (
            ("when", "tui.ledger.entry_tools.trace.column.when", 16),
            ("event", "tui.ledger.entry_tools.trace.column.event", 14),
            ("actor", "tui.ledger.entry_tools.trace.column.actor", 8),
            ("details", "tui.ledger.entry_tools.trace.column.details", 10),
        ):
            header = tr(column)
            table.add_column(header, key=key, width=max(width, len(header)))
        heading = self.query_one("#entries-trace-heading", Static)
        withheld = self.query_one("#entries-trace-withheld", Static)
        if self.full is not None:
            heading.update(tr("tui.ledger.entry_tools.trace.full_heading", count=self.full.event_count))
            withheld.update("")
            for event in self.full.events:
                table.add_row(
                    event.occurred_at.isoformat(timespec="minutes"),
                    event.event_type.value,
                    event.actor,
                    "; ".join(f"{item.name}: {item.value}" for item in event.details),
                    key=event.event_id,
                )
        elif self.typed is not None:
            heading.update(tr("tui.ledger.entry_tools.trace.typed_heading", count=self.typed.event_count))
            held = sum(1 for event in self.typed.events if event.model_reason_withheld or event.output_path_withheld)
            withheld.update(tr("tui.ledger.entry_tools.trace.withheld", count=held) if held else "")
            for typed_event in self.typed.events:
                details = typed_event.details.model_dump(exclude_none=True)
                table.add_row(
                    typed_event.occurred_at.isoformat(timespec="minutes"),
                    typed_event.event_type.value,
                    typed_event.actor,
                    "; ".join(f"{name}: {value}" for name, value in details.items()),
                    key=typed_event.event_id,
                )
        else:
            heading.update("")
            withheld.update("")
        table.absorb_surplus_width()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Re-read the typed history, or read the full event record on request."""
        if self.busy:
            self.query_one("#ledger-flow-status", Static).update(tr("tui.ledger.flow.in_flight_refusal"))
            return
        self.query_one("#ledger-refusal", Static).update("")
        if event.button.id == "entries-trace-read":
            self._start(self._read_typed())
        elif event.button.id == "entries-trace-full":
            self._start(self._read_full())

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Route the area navigation."""
        self.handle_navigation_selection(event)

    def _clear_private_view(self) -> None:
        self.track = self.typed = self.full = None
        self._paint()

    @override
    def action_back(self) -> None:
        """Return to the list this entry was chosen from, as it stood."""
        if self.busy:
            self.query_one("#ledger-flow-status", Static).update(tr("tui.ledger.flow.in_flight_refusal"))
            return
        screen = self._back_to(self.controller)
        screen.back_area = self.back_area
        replace_workspace_body(self.app, screen)


__all__ = ["LedgerEntryTraceScreen", "track_lines"]
