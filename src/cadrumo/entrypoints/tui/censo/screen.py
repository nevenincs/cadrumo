"""The census declarations an operator recorded as filed outside the application.

The screen reads the declarations through an injected door and draws what the
read serves: the kind and the dates, the receipt reference and the note the
operator stated. A declaration here is a local assertion: recording one stores
it and sends nothing to the tax authority, and the screen says so beside the
list. Recording opens the registered operation's own request form, built from
the request schema the runtime serves, so preflight, the receipt and an
unconfirmed outcome are the ones every operation uses. A refusal is shown as
the backend served it, and a read that failed shows the failure, never an
empty list.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import ClassVar, Final, Protocol, override
from uuid import UUID

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Button, DataTable, Static

from ....application.modelo.m036_operation import M036DeclarationSnapshot, M036ReadProjection, M036RecordProjection
from ....application.operations.error_detail import build_operation_error_detail
from ....core.errors.hierarchy import CadrumoError
from ....core.i18n.render import tr
from ..account import AccountSessionExpiredError
from ..components.account_chrome import AccountChromeScreen
from ..components.language import localized
from ..components.theme import BASE_CSS, tokenised
from ..components.widgets import ContentDataTable, ContentScroll
from ..navigation import TuiScreenContextV1, TuiScreenFactoryV1
from ..operations.run_screen import OperationRunScreen
from ..operations.run_wording import failure_text
from ..refusal.panel import RefusalSlot
from ..refusal.served import served_refusal

CENSO_DESTINATION: Final = "workbench.censo"


class CensoDoorV1(Protocol):
    """Injected door to the census declarations of one admitted profile session."""

    @property
    def profile_id(self) -> UUID:
        """The profile every request through this door names."""
        ...

    async def declarations(self) -> M036ReadProjection:
        """Read every declaration the profile holds."""
        ...

    async def declaration(self, declaration_id: str) -> M036ReadProjection:
        """Read the one declaration ``declaration_id`` names."""
        ...

    def record_form(self, prefill: Mapping[str, object]) -> OperationRunScreen:
        """Return the served request form of the record, its named fields filled from ``prefill``."""
        ...


class CensoScreen(AccountChromeScreen):
    """List the recorded declarations, show one in full, and open the form that records another."""

    BINDINGS: ClassVar = [Binding("escape", "back", "", show=False)]
    CSS = BASE_CSS + tokenised("""
    #censo-page { width: 100%; height: 1fr; padding: $cadrumo-space-0 $cadrumo-gutter; }
    .censo-actions { height: auto; margin-bottom: $cadrumo-stack; }
    .censo-actions Button { margin-right: $cadrumo-space-1; }
    #censo-status { height: auto; }
    #censo-failure { color: $warning; height: auto; }
    #censo-detail { height: auto; margin-top: $cadrumo-stack; }
    """)

    def __init__(self, door: CensoDoorV1) -> None:
        """Keep the profile-bound door every read and change goes through."""
        super().__init__(id="censo-screen")
        self.door = door
        self.declarations: tuple[M036DeclarationSnapshot, ...] = ()
        self.detail: M036DeclarationSnapshot | None = None
        self._busy = False

    @override
    def compose(self) -> ComposeResult:
        yield localized(
            Static(tr("tui.censo.title"), classes="cadrumo-banner", markup=False),
            "tui.censo.title",
        )
        with ContentScroll(id="censo-page"):
            yield localized(Static(tr("tui.censo.prompt"), markup=False), "tui.censo.prompt")
            yield localized(Static(tr("tui.censo.local_note"), markup=False), "tui.censo.local_note")
            with Horizontal(classes="censo-actions"):
                yield localized(Button(tr("tui.censo.action.read"), id="censo-read"), "tui.censo.action.read")
                yield localized(
                    Button(tr("tui.censo.action.detail"), id="censo-show-detail"), "tui.censo.action.detail"
                )
                yield localized(
                    Button(tr("tui.censo.action.record"), id="censo-record", variant="primary"),
                    "tui.censo.action.record",
                )
            yield Static("", id="censo-status", markup=False)
            yield Static("", id="censo-failure", markup=False)
            yield RefusalSlot(id="censo-refusal")
            yield localized(
                Static(tr("tui.censo.records.title"), classes="cadrumo-heading", markup=False),
                "tui.censo.records.title",
            )
            yield ContentDataTable[str](id="censo-declarations", cursor_type="row", zebra_stripes=True)
            yield Static("", id="censo-detail", markup=False)

    def on_mount(self) -> None:
        """Head the table in the language now on screen, then read the declarations."""
        self._draw()
        self._start_read()

    def _table(self) -> DataTable[str]:
        return self.query_one("#censo-declarations", DataTable)

    def _draw(self) -> None:
        """Draw the declarations as last read, under headings in the language now on screen."""
        table = self._table()
        table.clear(columns=True)
        table.add_columns(
            tr("tui.censo.column.kind"),
            tr("tui.censo.column.declared_on"),
            tr("tui.censo.column.recorded_at"),
        )
        for index, row in enumerate(self.declarations):
            table.add_row(
                row.event_kind.value,
                row.declared_on.isoformat(),
                row.recorded_at.date().isoformat(),
                key=str(index),
            )
        self._draw_detail()

    def _draw_detail(self) -> None:
        """Show the one declaration read in full, every stated fact under its label."""
        item = self.detail
        none = tr("tui.censo.detail.none")
        text = (
            ""
            if item is None
            else "\n".join(
                (
                    f"{tr('tui.censo.detail.id')}: {item.declaration_id}",
                    f"{tr('tui.censo.column.kind')}: {item.event_kind.value}",
                    f"{tr('tui.censo.column.declared_on')}: {item.declared_on.isoformat()}",
                    f"{tr('tui.censo.column.recorded_at')}: {item.recorded_at.isoformat()}",
                    f"{tr('tui.censo.detail.justificante')}: {item.sede_justificante or none}",
                    f"{tr('tui.censo.detail.note')}: {item.note or none}",
                    tr("tui.censo.local_note"),
                )
            )
        )
        self.query_one("#censo-detail", Static).update(text)

    def _status(self, text: str) -> None:
        self.query_one("#censo-status", Static).update(text)

    def _clear_failure(self) -> None:
        self.query_one("#censo-failure", Static).update("")
        self.query_one("#censo-refusal", RefusalSlot).show(None)

    def _show_failure(self, error: CadrumoError) -> None:
        """Show a failed read as the backend served its refusal, or in the failure's own words."""
        refusal = served_refusal(build_operation_error_detail(error))
        if refusal is not None:
            self.query_one("#censo-refusal", RefusalSlot).show(refusal)
        else:
            self.query_one("#censo-failure", Static).update(failure_text(error))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Dispatch the destination's own controls."""
        button_id = event.button.id
        if button_id == "censo-read":
            self._start_read()
        elif button_id == "censo-show-detail":
            self._start_detail()
        elif button_id == "censo-record":
            self._open_record()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Read the declaration whose row was chosen in full."""
        if event.data_table.id == "censo-declarations":
            self._start_detail()

    def action_back(self) -> None:
        """Leave the destination."""
        self.dismiss(None)

    def _start_read(self, note: str = "") -> None:
        if self._busy:
            return
        self._busy = True
        self._clear_failure()
        self._status(tr("tui.censo.status.reading"))
        self.run_worker(self._read(note), group="censo-read", exclusive=True)

    async def _read(self, note: str) -> None:
        """Read the declarations and draw them only once the whole list was read."""
        try:
            projection = await self.door.declarations()
        except CadrumoError as error:
            if isinstance(error, AccountSessionExpiredError):
                self._forget()
            self._show_failure(error)
            self._status(tr("tui.censo.status.read_failed"))
            return
        finally:
            self._busy = False
        self.declarations = projection.declarations
        if self.detail is not None and all(
            row.declaration_id != self.detail.declaration_id for row in self.declarations
        ):
            self.detail = None
        self._draw()
        self._status(note or ("" if self.declarations else tr("tui.censo.status.empty")))

    def _forget(self) -> None:
        """Drop every declaration read under a session that has since lapsed."""
        self.declarations = ()
        self.detail = None
        self._draw()

    def _selected(self) -> M036DeclarationSnapshot | None:
        table = self._table()
        if not self.declarations or table.row_count == 0:
            return None
        index = table.cursor_row
        return self.declarations[index] if 0 <= index < len(self.declarations) else None

    def _start_detail(self) -> None:
        if self._busy:
            return
        selected = self._selected()
        if selected is None:
            self._status(tr("tui.censo.status.choose_declaration"))
            return
        self._busy = True
        self._clear_failure()
        self._status(tr("tui.censo.status.reading"))
        self.run_worker(self._read_detail(selected.declaration_id), group="censo-read", exclusive=True)

    async def _read_detail(self, declaration_id: str) -> None:
        try:
            projection = await self.door.declaration(declaration_id)
        except CadrumoError as error:
            if isinstance(error, AccountSessionExpiredError):
                self._forget()
            self._show_failure(error)
            self._status(tr("tui.censo.status.read_failed"))
            return
        finally:
            self._busy = False
        self.detail = projection.declarations[0]
        self._draw_detail()
        self._status("")

    def _open_record(self) -> None:
        if self._busy:
            return
        self._clear_failure()
        self._status("")
        try:
            form = self.door.record_form({})
        except CadrumoError as error:
            if isinstance(error, AccountSessionExpiredError):
                self._forget()
            self._show_failure(error)
            return

        def closed(_dismissed: None) -> None:
            self._after_record(form)

        self.app.push_screen(form, closed)

    def _after_record(self, form: OperationRunScreen) -> None:
        """Say what the form settled, then read the list again: the list, not the form, is what is stored."""
        result = form.settled_result
        if isinstance(result, M036RecordProjection) and result.profile_id == self.door.profile_id:
            declaration = result.declaration
            note = tr(
                "tui.censo.status.recorded",
                kind=declaration.event_kind.value,
                declared_on=declaration.declared_on.isoformat(),
            )
        else:
            # No confirmed result: the change may or may not be stored, and only the list read now says.
            note = tr("tui.censo.status.unconfirmed")
        self._start_read(note)

    @override
    async def refresh_language(self) -> None:
        """Reword the chrome and re-head the table, keeping the declarations read."""
        await super().refresh_language()
        self._draw()


def censo_screen_factory(door: CensoDoorV1) -> TuiScreenFactoryV1:
    """Bind the destination to one profile-bound door."""

    def create(context: TuiScreenContextV1) -> Screen[None]:
        if context.destination != CENSO_DESTINATION:
            raise ValueError("the census factory requires its exact destination")
        return CensoScreen(door)

    return create


__all__ = [
    "CENSO_DESTINATION",
    "CensoDoorV1",
    "CensoScreen",
    "censo_screen_factory",
]
