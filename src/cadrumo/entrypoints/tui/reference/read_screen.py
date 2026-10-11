"""One reference read: its coordinates, its result, and the reads its rows lead to.

The read runs off the event loop, because it opens the published authority.
Its result is shown whole: the facts the command prints as lines, and its rows
as tables whose rows open the read that describes them.
"""

from __future__ import annotations

import asyncio
from logging import ERROR
from typing import ClassVar, cast, override

from pydantic import BaseModel
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Button, Checkbox, DataTable, Input, Label, Select, Static

from ....core.diagnostic_log import diagnostic_error_fields, diagnostic_event
from ....core.i18n.render import tr
from ....core.logging import get_logger
from ..components.account_chrome import AccountChromeScreen
from ..components.status import PinnedStatusBar
from ..components.theme import BASE_CSS, tokenised
from ..components.widgets import ContentDataTable, ContentScroll, DisclosureGroup
from ..secret.credentials import CREDENTIAL_PANEL_CSS
from .filters import (
    ReferenceFilter,
    ReferenceFilterError,
    ReferenceFilterKind,
    filters_of,
    form_value,
    is_complete,
    query_from_form,
)
from .reads import (
    ReferenceCoordinateMissingError,
    ReferenceQuery,
    ReferenceRead,
    ReferenceReadRefusedError,
    read_reference,
)
from .texts import filter_label, read_label, read_summary
from .views import ReferenceView, view_of

_LOGGER = get_logger(__name__)
_WORKER_GROUP = "tui-reference-read"
_TABLE_SLOTS = 2
"""The most tables one result is laid out as."""


def _filter_id(name: str) -> str:
    return f"reference-filter-{name}"


class ReferenceReadScreen(AccountChromeScreen):
    """Ask for one read's coordinates and show what the reference answers."""

    BINDINGS: ClassVar = [Binding("escape", "close", "", show=False)]
    CSS = (
        BASE_CSS
        + CREDENTIAL_PANEL_CSS
        + tokenised(
            """
        /* In the page's flow: docked, it would lie over the account bar and this read's own title. */
        #reference-status { dock: none; }
        #reference-read-page { width: 100%; height: 1fr; padding: $cadrumo-space-0 $cadrumo-gutter; }
        #reference-read-summary, #reference-facts { height: auto; margin: $cadrumo-stack $cadrumo-space-0; }
        #reference-read-actions Button, #reference-links Button {
            margin: $cadrumo-space-0 $cadrumo-space-0 $cadrumo-space-0 $cadrumo-control-gap;
        }
        #reference-links { height: auto; }
        .reference-table { width: 100%; }
        """
        )
    )

    def __init__(self, query: ReferenceQuery) -> None:
        """Bind one read and whatever coordinates it was opened with."""
        super().__init__()
        self._query = query
        self._result: BaseModel | None = None
        self._view = ReferenceView()

    @property
    def result(self) -> BaseModel | None:
        """The typed result now on screen, or ``None`` before the first answer."""
        return self._result

    @override
    def compose(self) -> ComposeResult:
        read = self._query.read
        yield Static(read_label(read), classes="cadrumo-banner", markup=False)
        yield PinnedStatusBar(id="reference-status")
        with ContentScroll(id="reference-read-page", classes="cadrumo-scroll"):
            yield Static(read_summary(read), id="reference-read-summary", classes="cadrumo-subtle", markup=False)
            if filters_of(read):
                # A read opened from a row already has its coordinates, so they
                # stay folded away and the answer is the first thing on the page.
                with DisclosureGroup(
                    title=tr("tui.reference.filters"), collapsed=is_complete(self._query), id="reference-filters"
                ):
                    for reference_filter in filters_of(read):
                        yield from self._compose_filter(reference_filter)
            with Horizontal(id="reference-read-actions", classes="credential-actions"):
                yield Button(tr("tui.reference.action.close"), id="reference-close")
                yield Button(tr("tui.reference.action.show"), id="reference-show", classes="-primary")
            yield Static(id="reference-facts", markup=False)
            with Horizontal(id="reference-links"):
                for linked in ReferenceRead:
                    yield Button(read_label(linked), id=f"reference-link-{linked.value}")
            for slot in range(_TABLE_SLOTS):
                yield Static(id=f"reference-heading-{slot}", classes="cadrumo-heading", markup=False)
                table = ContentDataTable[str](
                    id=f"reference-table-{slot}", classes="reference-table", cursor_type="row", zebra_stripes=True
                )
                # Every column keeps its whole text, as a printed line does; a
                # row wider than the terminal scrolls sideways.
                table.fill_column = None
                yield table

    def _compose_filter(self, reference_filter: ReferenceFilter) -> ComposeResult:
        label = filter_label(reference_filter.name)
        widget_id = _filter_id(reference_filter.name)
        value = form_value(self._query, reference_filter)
        if reference_filter.kind is ReferenceFilterKind.FLAG:
            yield Checkbox(label, value=bool(value), id=widget_id)
            return
        yield Label(label, classes="field-label")
        if reference_filter.kind is ReferenceFilterKind.CHOICE:
            yield Select[str](
                [(choice, choice) for choice in reference_filter.choices],
                prompt=tr("tui.reference.filter.any"),
                value=value if isinstance(value, str) and value in reference_filter.choices else Select.NULL,
                id=widget_id,
            )
            return
        yield Input(
            value=str(value),
            type="integer" if reference_filter.kind is ReferenceFilterKind.INTEGER else "text",
            id=widget_id,
        )

    def on_mount(self) -> None:
        """Answer at once a read whose coordinates are already complete."""
        self._lay_out(ReferenceView())
        if is_complete(self._query):
            self.call_after_refresh(self._start, self._query)
            return
        inputs = self.query("Input, Select, Checkbox")
        (inputs.first() if inputs else self.query_one("#reference-show", Button)).focus()

    def _form_values(self) -> dict[str, object]:
        values: dict[str, object] = {}
        for reference_filter in filters_of(self._query.read):
            selector = f"#{_filter_id(reference_filter.name)}"
            if reference_filter.kind is ReferenceFilterKind.FLAG:
                values[reference_filter.name] = self.query_one(selector, Checkbox).value
            elif reference_filter.kind is ReferenceFilterKind.CHOICE:
                chosen = cast("Select[str]", self.query_one(selector, Select)).value
                values[reference_filter.name] = chosen if isinstance(chosen, str) else ""
            else:
                values[reference_filter.name] = self.query_one(selector, Input).value
        return values

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Show the read, follow a link to another, or leave."""
        button_id = event.button.id or ""
        if button_id == "reference-close":
            self.action_close()
        elif button_id == "reference-show":
            self.action_show()
        elif button_id.startswith("reference-link-"):
            for link in self._view.links:
                if button_id == f"reference-link-{link.read.value}":
                    self.app.push_screen(ReferenceReadScreen(link.query))

    def on_input_submitted(self, _event: Input.Submitted) -> None:
        """Enter in a coordinate field shows the read."""
        self.action_show()

    def action_show(self) -> None:
        """Read with the coordinates now in the form."""
        try:
            query = query_from_form(self._query.read, self._form_values())
        except ReferenceFilterError as error:
            self._show_invalid(error.fields)
            return
        self._start(query)

    def _show_invalid(self, fields: tuple[str, ...]) -> None:
        self.query_one("#reference-status", PinnedStatusBar).show_error(
            tr("tui.reference.status.invalid", fields=", ".join(filter_label(name) for name in fields))
        )
        for group in self.query("#reference-filters").results(DisclosureGroup):
            group.collapsed = False
        focus = self.query(f"#{_filter_id(fields[0])}")
        if focus:
            focus.first().focus()

    def _start(self, query: ReferenceQuery) -> None:
        self._query = query
        self.query_one("#reference-status", PinnedStatusBar).show_progress(tr("tui.reference.status.loading"))
        self.run_worker(self._load(query), name=_WORKER_GROUP, group=_WORKER_GROUP, exclusive=True, exit_on_error=False)

    async def _load(self, query: ReferenceQuery) -> None:
        refusal: str | None = None
        result: BaseModel | None = None
        try:
            result = await asyncio.to_thread(read_reference, query)
        except ReferenceCoordinateMissingError as error:
            if self.is_mounted:
                self._show_invalid((error.coordinate,))
            return
        except ReferenceReadRefusedError as error:
            refusal = str(error)
        except Exception as error:
            diagnostic_event(
                _LOGGER,
                "tui_reference_read_failed",
                fields={**diagnostic_error_fields(error), "read": query.read.value, "outcome": "failed"},
                level=ERROR,
                primary_error=error,
            )
            refusal = tr("tui.reference.status.failed")
        if not self.is_mounted:
            return
        status = self.query_one("#reference-status", PinnedStatusBar)
        self._result = result
        if result is None:
            self._lay_out(ReferenceView())
            status.show_error(refusal or tr("tui.reference.status.failed"))
            return
        view = view_of(query, result)
        self._lay_out(view)
        if view.tables:
            status.show_success(tr("tui.reference.status.rows", count=view.row_count))
        else:
            status.clear_message()

    def _lay_out(self, view: ReferenceView) -> None:
        self._view = view
        width = max((len(label) for label, _value in view.facts), default=0)
        self.query_one("#reference-facts", Static).update(
            "\n".join(f"{label:<{width}}  {value}" for label, value in view.facts)
        )
        linked = {link.read for link in view.links}
        for read in ReferenceRead:
            self.query_one(f"#reference-link-{read.value}", Button).display = read in linked
        self.query_one("#reference-links", Horizontal).display = bool(linked)
        for slot in range(_TABLE_SLOTS):
            heading = self.query_one(f"#reference-heading-{slot}", Static)
            table = cast("DataTable[str]", self.query_one(f"#reference-table-{slot}", DataTable))
            table.clear(columns=True)
            shown = view.tables[slot] if slot < len(view.tables) else None
            table.display = shown is not None
            heading.display = shown is not None and shown.heading is not None
            if shown is None:
                continue
            heading.update(shown.heading or "")
            for column in shown.columns:
                table.add_column(column)
            for index, row in enumerate(shown.rows):
                table.add_row(*row, key=str(index))
            cast("ContentDataTable[str]", table).absorb_surplus_width()
        focusable = [slot for slot in range(len(view.tables)) if view.tables[slot].rows]
        if focusable:
            self.query_one(f"#reference-table-{focusable[0]}", DataTable).focus()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Open the read that describes the chosen row, when one does."""
        table_id = event.data_table.id or ""
        if not table_id.startswith("reference-table-") or event.row_key.value is None:
            return
        shown = self._view.tables[int(table_id.removeprefix("reference-table-"))]
        opened = shown.opens[int(event.row_key.value)]
        if opened is not None:
            self.app.push_screen(ReferenceReadScreen(opened))

    def action_close(self) -> None:
        """Return to the read or list this one was opened from."""
        self.dismiss(None)


__all__ = ["ReferenceReadScreen"]
