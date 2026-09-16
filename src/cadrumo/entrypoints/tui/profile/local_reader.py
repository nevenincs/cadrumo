"""Document reader: what the local reader reports, and the supervised start, pull and verify.

The page renders :class:`LocalReaderStatus` as measured and nothing more. An
answer the reader could not measure stays "not measured"; it never becomes
"not installed". Installing the runtime is not offered here: it runs a package
manager and needs consent given at the command line.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, Final, Protocol, cast, override

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Static

from ....application.local_reader import LocalReaderRoleStatus, LocalReaderStatus
from ....application.operations.composition import OperationComposedServices
from ....core.errors.hierarchy import CadrumoError
from ....core.i18n.render import tr
from ....core.model_catalogue import ModelRole
from ..components.theme import BASE_CSS
from ..components.widgets import ContentDataTable, ContentScroll
from ..operations.controller import OperationController
from ..operations.modal import OperationModal, OperationModalOutcomeV1

if TYPE_CHECKING:
    from ....application.local_reader_operation import LocalReaderProvisionRequest
    from ....application.operations.models import OperationRequest

_ROLE_LOCALE_KEYS: Final[dict[ModelRole, str]] = {
    ModelRole.VISION_TRANSCRIPTION: "tui.local_reader.role.vision_transcription",
    ModelRole.TEXT_EXTRACTION: "tui.local_reader.role.text_extraction",
    ModelRole.COLUMN_ROLE_MAPPING: "tui.local_reader.role.column_role_mapping",
    ModelRole.SUPPLY_NATURE_PROPOSAL: "tui.local_reader.role.supply_nature_proposal",
}
_ACTOR_REF: Final = "operator:tui-local-reader"


def _answer(value: bool | None) -> str:
    """Render a measured yes or no, keeping an unmeasured answer unmeasured."""
    if value is None:
        return tr("tui.local_reader.answer.unmeasured")
    return tr("tui.local_reader.answer.yes") if value else tr("tui.local_reader.answer.no")


def local_reader_role_cells(row: LocalReaderRoleStatus) -> tuple[str, str, str, str, str]:
    """One role's table cells: role, model, installed, loaded, ready."""
    return (
        tr(_ROLE_LOCALE_KEYS[row.role]),
        row.model or tr("tui.local_reader.no_model"),
        _answer(row.installed),
        _answer(row.resident),
        _answer(row.ready),
    )


def local_reader_summary_lines(status: LocalReaderStatus) -> tuple[str, ...]:
    """The host, the last fetch and the one readiness claim, in the operator's language."""
    host = status.host
    lines = [
        tr(
            "tui.local_reader.host",
            endpoint=host.endpoint_url,
            installed=_answer(host.executable_located),
            reachable=_answer(host.reachable),
            version=host.version or "-",
        ),
    ]
    if status.last_pull is not None:
        pull = status.last_pull
        lines.append(
            tr(
                "tui.local_reader.last_pull",
                model=pull.model,
                outcome=_answer(pull.pulled),
                size="-" if pull.bytes_fetched is None else pull.bytes_fetched,
            )
        )
    lines.append(
        tr("tui.local_reader.extraction_ready")
        if status.extraction_ready
        else tr("tui.local_reader.extraction_not_ready")
    )
    if not host.executable_located:
        lines.append(tr("tui.local_reader.install_at_cli"))
    return tuple(lines)


class LocalReaderDoorV1(Protocol):
    """Reads the reader's status and submits its supervised provisioning actions."""

    def read_status(self) -> LocalReaderStatus:
        """Measure the runtime and every role without starting or loading anything."""
        ...

    async def start(self) -> OperationController:
        """Submit and start the runtime-start operation."""
        ...

    async def pull(self, role: ModelRole) -> OperationController:
        """Submit and start the fetch of ``role``'s model."""
        ...

    async def verify(self, role: ModelRole) -> OperationController:
        """Submit and start the load check of ``role``'s model."""
        ...


@dataclass(frozen=True, slots=True)
class OperationLocalReaderDoor:
    """The reader door over the session's own operation platform."""

    services: OperationComposedServices

    def read_status(self) -> LocalReaderStatus:
        """Measure the reader exactly as ``config provision status`` does."""
        from ....application.local_reader import read_local_reader_status

        return read_local_reader_status()

    async def _run(self, request: OperationRequest[LocalReaderProvisionRequest]) -> OperationController:
        submission = await self.services.submission.submit(request, actor_ref=_ACTOR_REF)
        controller = OperationController(services=self.services, submission=submission, actor_ref=_ACTOR_REF)
        await controller.start()
        return controller

    async def start(self) -> OperationController:
        """Submit and start the runtime-start operation."""
        from ....application.local_reader_operation import build_local_reader_start_request

        return await self._run(build_local_reader_start_request())

    async def pull(self, role: ModelRole) -> OperationController:
        """Submit and start the fetch of ``role``'s model."""
        from ....application.local_reader_operation import build_local_reader_pull_request

        return await self._run(build_local_reader_pull_request(role))

    async def verify(self, role: ModelRole) -> OperationController:
        """Submit and start the load check of ``role``'s model."""
        from ....application.local_reader_operation import build_local_reader_verify_request

        return await self._run(build_local_reader_verify_request(role))


class LocalReaderScreen(Screen[None]):
    """The document reader's measured state and its three supervised actions."""

    DEFAULT_CSS = BASE_CSS
    BINDINGS: ClassVar = [Binding("escape", "close", "", show=False), Binding("r", "refresh_status", "", show=False)]

    def __init__(self, door: LocalReaderDoorV1) -> None:
        """Hold the door; nothing is read until the page is mounted."""
        super().__init__(id="local-reader-screen")
        self._door = door
        self.status: LocalReaderStatus | None = None
        self.selected_role: ModelRole | None = None

    @override
    def compose(self) -> ComposeResult:
        yield Static(tr("tui.local_reader.title"), classes="cadrumo-banner")
        with ContentScroll(id="local-reader-page", classes="cadrumo-scroll"):
            yield Static(tr("tui.local_reader.intro"), markup=False)
            yield Static("", id="local-reader-summary", markup=False)
            yield ContentDataTable[str](id="local-reader-roles", cursor_type="row", zebra_stripes=True)
            yield Static(tr("tui.local_reader.choose_role"), id="local-reader-selection", markup=False)
            yield Button(tr("tui.local_reader.refresh"), id="local-reader-refresh")
            yield Button(tr("tui.local_reader.start"), id="local-reader-start")
            yield Button(tr("tui.local_reader.pull"), id="local-reader-pull", disabled=True)
            yield Button(tr("tui.local_reader.verify"), id="local-reader-verify", disabled=True)
            yield Static("", id="local-reader-notice", markup=False)
        yield Footer()

    def on_mount(self) -> None:
        """Lay out the role table and take the first measurement."""
        table = cast("DataTable[str]", self.query_one("#local-reader-roles", DataTable))
        for key in (
            "tui.local_reader.column.role",
            "tui.local_reader.column.model",
            "tui.local_reader.column.installed",
            "tui.local_reader.column.loaded",
            "tui.local_reader.column.ready",
        ):
            table.add_column(tr(key))
        self.action_refresh_status()
        table.focus()

    def action_close(self) -> None:
        """Return to the page this was opened from."""
        self.dismiss(None)

    def action_refresh_status(self) -> None:
        """Measure again off the event loop; an unreachable runtime can take seconds to answer."""
        self.query_one("#local-reader-summary", Static).update(tr("tui.local_reader.measuring"))
        self.run_worker(self._measure(), group="local-reader-status", exclusive=True)

    async def _measure(self) -> None:
        try:
            status = await asyncio.to_thread(self._door.read_status)
        except CadrumoError:
            self.query_one("#local-reader-summary", Static).update(tr("tui.local_reader.unreadable"))
            return
        self.status = status
        self._render_status(status)

    def _render_status(self, status: LocalReaderStatus) -> None:
        self.query_one("#local-reader-summary", Static).update("\n".join(local_reader_summary_lines(status)))
        table = cast("DataTable[str]", self.query_one("#local-reader-roles", DataTable))
        table.clear()
        for row in status.roles:
            table.add_row(*local_reader_role_cells(row), key=row.role.value)
        if self.selected_role is not None:
            index = next(
                (index for index, row in enumerate(table.ordered_rows) if row.key.value == self.selected_role.value),
                None,
            )
            if index is not None:
                table.move_cursor(row=index)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Choose the role a pull or verify acts on."""
        if event.row_key.value is None:
            return
        self.selected_role = ModelRole(str(event.row_key.value))
        self.query_one("#local-reader-selection", Static).update(
            tr("tui.local_reader.selected_role", role=tr(_ROLE_LOCALE_KEYS[self.selected_role]))
        )
        self.query_one("#local-reader-pull", Button).disabled = False
        self.query_one("#local-reader-verify", Button).disabled = False

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Submit the pressed action through the operation platform."""
        match event.button.id:
            case "local-reader-refresh":
                self.action_refresh_status()
            case "local-reader-start":
                self.run_worker(self._submit(self._door.start()), group="local-reader-action", exclusive=True)
            case "local-reader-pull" if self.selected_role is not None:
                self.run_worker(
                    self._submit(self._door.pull(self.selected_role)), group="local-reader-action", exclusive=True
                )
            case "local-reader-verify" if self.selected_role is not None:
                self.run_worker(
                    self._submit(self._door.verify(self.selected_role)), group="local-reader-action", exclusive=True
                )
            case _:
                return

    async def _submit(self, submitted: Awaitable[OperationController]) -> None:
        notice = self.query_one("#local-reader-notice", Static)
        notice.update(tr("tui.local_reader.submitting"))
        try:
            controller = await submitted
        except CadrumoError:
            notice.update(tr("tui.local_reader.refused"))
            return
        notice.update("")
        self.app.push_screen(OperationModal(controller), self._on_operation_closed)

    def _on_operation_closed(self, _: OperationModalOutcomeV1 | None) -> None:
        """Measure again: the operation's own result is shown by the modal, the state here."""
        self.action_refresh_status()


__all__ = [
    "LocalReaderDoorV1",
    "LocalReaderScreen",
    "OperationLocalReaderDoor",
    "local_reader_role_cells",
    "local_reader_summary_lines",
]
