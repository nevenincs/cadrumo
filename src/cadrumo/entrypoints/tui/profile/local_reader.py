"""Document reader: what the local reader reports, and the supervised setup and per-step actions.

The page renders :class:`LocalReaderStatus` as measured and nothing more. An
answer the reader could not measure stays "not measured"; it never becomes
"not installed". Installing the runtime runs a package manager, so both the
install button and a setup that would install ask for explicit confirmation
first, the same consent ``--confirm`` gives at the command line.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, ClassVar, Final, Protocol, cast, override

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Static

from ....application.local_reader import LocalReaderRoleStatus, LocalReaderStatus, RoleFitnessState
from ....application.local_reader_operation import LocalReaderProvisionPublicResultV1, LocalReaderSetupStep
from ....application.operations.composition import OperationComposedServices
from ....application.operations.frontend_requests import (
    OperationObservationSuccessV1,
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
)
from ....application.provisioning_host import RuntimeInstaller
from ....core.errors.hierarchy import CadrumoError
from ....core.i18n.render import tr
from ....core.model_catalogue import ModelRole
from ....core.operations import OperationTerminalCondition
from ..components.app_access import TypedAppAccess
from ..components.dialogs import ConfirmScreen
from ..components.theme import BASE_CSS, tokenised
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
_SETUP_STEP_LOCALE_KEYS: Final[dict[LocalReaderSetupStep, str]] = {
    LocalReaderSetupStep.INSTALL: "tui.local_reader.setup_step.install",
    LocalReaderSetupStep.START: "tui.local_reader.setup_step.start",
    LocalReaderSetupStep.PULL: "tui.local_reader.setup_step.pull",
    LocalReaderSetupStep.LOAD: "tui.local_reader.setup_step.load",
    LocalReaderSetupStep.VERIFY: "tui.local_reader.setup_step.verify",
}
_CHECKLIST_LOCALE_KEYS: Final = {
    "service_installed": "tui.local_reader.checklist.service_installed",
    "service_running": "tui.local_reader.checklist.service_running",
    "text_model_pulled": "tui.local_reader.checklist.text_model_pulled",
    "vision_model_pulled": "tui.local_reader.checklist.vision_model_pulled",
    "models_loaded": "tui.local_reader.checklist.models_loaded",
    "verified": "tui.local_reader.checklist.verified",
}
_FITNESS_LOCALE_KEYS: Final[dict[RoleFitnessState, str]] = {
    RoleFitnessState.FIT: "tui.local_reader.fitness.fit",
    RoleFitnessState.UNFIT: "tui.local_reader.fitness.unfit",
    RoleFitnessState.TIMED_OUT: "tui.local_reader.fitness.timed_out",
    RoleFitnessState.NOT_VERIFIED: "tui.local_reader.fitness.not_verified",
}
#: What each state that is not a pass means, in the same words `config provision status` uses.
_FITNESS_REASON_LOCALE_KEYS: Final[dict[RoleFitnessState, str]] = {
    RoleFitnessState.UNFIT: "provisioning.condition.role_model_fit_for_role",
    RoleFitnessState.TIMED_OUT: "provisioning.condition.role_model_fitness_within_timeout",
    RoleFitnessState.NOT_VERIFIED: "provisioning.condition.role_model_fitness_verified",
}
_ACTOR_REF: Final = "operator:tui-local-reader"
_LOCAL_READER_CSS = tokenised("""
.local-reader-actions { height: auto; margin: $cadrumo-space-0; }
.local-reader-actions Button { margin: $cadrumo-space-0 $cadrumo-control-gap $cadrumo-space-0 $cadrumo-space-0; }
#local-reader-checklist { height: auto; }
""")
_ROLE_ACTION_BUTTONS: Final = (
    "#local-reader-pull",
    "#local-reader-load",
    "#local-reader-verify",
    "#local-reader-remove",
)


def _answer(value: bool | None) -> str:
    """Render a measured yes or no, keeping an unmeasured answer unmeasured."""
    if value is None:
        return tr("tui.local_reader.answer.unmeasured")
    return tr("tui.local_reader.answer.yes") if value else tr("tui.local_reader.answer.no")


def local_reader_role_cells(row: LocalReaderRoleStatus) -> tuple[str, str, str, str, str, str]:
    """One role's table cells: role, model, installed, loaded, model check, ready."""
    return (
        tr(_ROLE_LOCALE_KEYS[row.role]),
        row.model or tr("tui.local_reader.no_model"),
        _answer(row.installed),
        _answer(row.resident),
        "-" if row.fitness is None else tr(_FITNESS_LOCALE_KEYS[row.fitness]),
        _answer(row.ready),
    )


def local_reader_fitness_lines(status: LocalReaderStatus) -> tuple[str, ...]:
    """Explain every role whose model check did not pass; "not verified" never reads as "unfit"."""
    return tuple(
        f"{tr(_ROLE_LOCALE_KEYS[row.role])}: {tr(_FITNESS_REASON_LOCALE_KEYS[row.fitness], model=row.model or '-')}"
        for row in status.roles
        if row.fitness is not None and row.fitness in _FITNESS_REASON_LOCALE_KEYS
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
    return tuple(lines)


_CHECKLIST_COLUMN_LOCALE_KEYS: Final[tuple[str, ...]] = (
    "tui.local_reader.column.step",
    "tui.local_reader.column.state",
)
_ROLE_COLUMN_LOCALE_KEYS: Final[tuple[str, ...]] = (
    "tui.local_reader.column.role",
    "tui.local_reader.column.model",
    "tui.local_reader.column.installed",
    "tui.local_reader.column.loaded",
    "tui.local_reader.column.fitness",
    "tui.local_reader.column.ready",
)


class LocalReaderChecklistItem(StrEnum):
    """The rows of the setup checklist, in the order setup satisfies them."""

    SERVICE_INSTALLED = "service_installed"
    SERVICE_RUNNING = "service_running"
    TEXT_MODEL_PULLED = "text_model_pulled"
    VISION_MODEL_PULLED = "vision_model_pulled"
    MODELS_LOADED = "models_loaded"
    VERIFIED = "verified"


def _all_of(values: tuple[bool | None, ...]) -> bool | None:
    """Combine measured answers: any unmeasured stays unmeasured, otherwise all must hold."""
    if any(value is None for value in values):
        return None
    return all(values)


def local_reader_checklist(status: LocalReaderStatus) -> tuple[tuple[LocalReaderChecklistItem, bool | None], ...]:
    """Derive each checklist row's measured state; ``None`` means not measured, never missing."""
    host = status.host
    rows = {row.role: row for row in status.roles}
    text = rows.get(ModelRole.TEXT_EXTRACTION)
    vision = rows.get(ModelRole.VISION_TRANSCRIPTION)
    readers = tuple(row for row in (text, vision) if row is not None)
    loaded = _all_of(tuple(row.resident for row in readers)) if readers else None
    return (
        # A runtime that answers is installed somewhere, even when no executable is on this path.
        (LocalReaderChecklistItem.SERVICE_INSTALLED, host.executable_located or host.reachable),
        (LocalReaderChecklistItem.SERVICE_RUNNING, host.reachable),
        (LocalReaderChecklistItem.TEXT_MODEL_PULLED, None if text is None else text.installed),
        (LocalReaderChecklistItem.VISION_MODEL_PULLED, None if vision is None else vision.installed),
        (LocalReaderChecklistItem.MODELS_LOADED, loaded),
        (LocalReaderChecklistItem.VERIFIED, status.extraction_ready if host.reachable else None),
    )


def local_reader_checklist_cells(item: LocalReaderChecklistItem, state: bool | None) -> tuple[str, str]:
    """One checklist row's cells: the step and its done / missing / not measured state."""
    if state is None:
        rendered = tr("tui.local_reader.answer.unmeasured")
    else:
        rendered = tr("tui.local_reader.state.done") if state else tr("tui.local_reader.state.missing")
    return tr(_CHECKLIST_LOCALE_KEYS[item.value]), rendered


def local_reader_setup_notice(result: LocalReaderProvisionPublicResultV1) -> str:
    """Say whether setup finished, or which step stopped it and on which condition."""
    if result.succeeded or result.stopped_step is None:
        return tr("tui.local_reader.setup_done")
    failed = next((step for step in result.steps if step.step is result.stopped_step), None)
    return tr(
        "tui.local_reader.setup_stopped",
        step=tr(_SETUP_STEP_LOCALE_KEYS[result.stopped_step]),
        condition=(failed.failed_condition_id if failed is not None else None) or "-",
    )


class LocalReaderDoorV1(Protocol):
    """Reads the reader's status and submits its supervised provisioning actions."""

    def read_status(self) -> LocalReaderStatus:
        """Measure the runtime and every role without starting or loading anything."""
        ...

    async def setup(self, *, consent: bool) -> OperationController:
        """Submit and start the one-shot setup; ``consent`` permits an install."""
        ...

    async def install(self, *, consent: bool) -> OperationController:
        """Submit and start the runtime install."""
        ...

    async def start(self) -> OperationController:
        """Submit and start the runtime-start operation."""
        ...

    async def pull(self, role: ModelRole) -> OperationController:
        """Submit and start the fetch of ``role``'s model."""
        ...

    async def load(self, role: ModelRole) -> OperationController:
        """Submit and start the load of ``role``'s model into memory."""
        ...

    async def verify(self, role: ModelRole) -> OperationController:
        """Submit and start the readiness check of ``role``'s model."""
        ...

    async def remove(self, role: ModelRole) -> OperationController:
        """Submit and start the removal of ``role``'s model from the runtime's store."""
        ...

    async def settled_result(self, controller: OperationController) -> LocalReaderProvisionPublicResultV1 | None:
        """Return the settled public result of a finished operation, or ``None`` when it has none."""
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

    async def setup(self, *, consent: bool) -> OperationController:
        """Submit and start the one-shot setup."""
        from ....application.local_reader_operation import build_local_reader_setup_request

        return await self._run(build_local_reader_setup_request(consent=consent))

    async def install(self, *, consent: bool) -> OperationController:
        """Submit and start the runtime install."""
        from ....application.local_reader_operation import build_local_reader_install_request

        return await self._run(build_local_reader_install_request(consent=consent))

    async def start(self) -> OperationController:
        """Submit and start the runtime-start operation."""
        from ....application.local_reader_operation import build_local_reader_start_request

        return await self._run(build_local_reader_start_request())

    async def pull(self, role: ModelRole) -> OperationController:
        """Submit and start the fetch of ``role``'s model."""
        from ....application.local_reader_operation import build_local_reader_pull_request

        return await self._run(build_local_reader_pull_request(role))

    async def load(self, role: ModelRole) -> OperationController:
        """Submit and start the load of ``role``'s model."""
        from ....application.local_reader_operation import build_local_reader_load_request

        return await self._run(build_local_reader_load_request(role))

    async def verify(self, role: ModelRole) -> OperationController:
        """Submit and start the readiness check of ``role``'s model."""
        from ....application.local_reader_operation import build_local_reader_verify_request

        return await self._run(build_local_reader_verify_request(role))

    async def remove(self, role: ModelRole) -> OperationController:
        """Submit and start the removal of ``role``'s model."""
        from ....application.local_reader_operation import build_local_reader_remove_request

        return await self._run(build_local_reader_remove_request(role))

    async def settled_result(self, controller: OperationController) -> LocalReaderProvisionPublicResultV1 | None:
        """Resolve the settled public result through the composed result door."""
        # The modal can close while the operation still runs; the result is
        # only defined once it has concluded.
        await self.services.submission.settled(controller.operation_id)
        observed = await controller.observe(0)
        if not isinstance(observed, OperationObservationSuccessV1):
            return None
        projection = observed.projection
        schema = projection.definition_contract.result_schema
        if projection.terminal_condition is not OperationTerminalCondition.SUCCEEDED or schema is None:
            return None
        resolved = await self.services.result.resolve(
            OperationResultProjectionRequestV1(
                operation_id=projection.operation_id,
                terminal_revision=projection.revision,
                definition_contract_digest=projection.definition_contract.definition_contract_digest,
                result_schema=schema,
            ),
            LocalReaderProvisionPublicResultV1,
        )
        if not isinstance(resolved, OperationResultProjectionSuccessV1) or not isinstance(
            resolved.projection, LocalReaderProvisionPublicResultV1
        ):
            return None
        return resolved.projection


class LocalReaderScreen(TypedAppAccess, Screen[None]):
    """The document reader's setup checklist, its measured roles and its supervised actions."""

    DEFAULT_CSS = BASE_CSS + _LOCAL_READER_CSS
    BINDINGS: ClassVar = [
        Binding("escape", "close", "", show=False),
        Binding("r", "refresh_status", "", show=False),
        Binding("s", "setup", "", show=False),
    ]

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
            yield ContentDataTable[str](id="local-reader-checklist", cursor_type="none", zebra_stripes=True)
            with Horizontal(classes="local-reader-actions"):
                yield Button(tr("tui.local_reader.setup"), id="local-reader-setup", variant="primary")
                yield Button(tr("tui.local_reader.refresh"), id="local-reader-refresh")
            with Horizontal(classes="local-reader-actions"):
                yield Button(tr("tui.local_reader.install"), id="local-reader-install")
                yield Button(tr("tui.local_reader.start"), id="local-reader-start")
            yield ContentDataTable[str](id="local-reader-roles", cursor_type="row", zebra_stripes=True)
            yield Static("", id="local-reader-fitness", markup=False)
            yield Static(tr("tui.local_reader.choose_role"), id="local-reader-selection", markup=False)
            with Horizontal(classes="local-reader-actions"):
                yield Button(tr("tui.local_reader.pull"), id="local-reader-pull", disabled=True)
                yield Button(tr("tui.local_reader.load"), id="local-reader-load", disabled=True)
                yield Button(tr("tui.local_reader.verify"), id="local-reader-verify", disabled=True)
                yield Button(tr("tui.local_reader.remove"), id="local-reader-remove", disabled=True)
            yield Static("", id="local-reader-notice", markup=False)
        yield Footer()

    def on_mount(self) -> None:
        """Lay out both tables and take the first measurement."""
        checklist = cast("DataTable[str]", self.query_one("#local-reader-checklist", DataTable))
        for key in _CHECKLIST_COLUMN_LOCALE_KEYS:
            checklist.add_column(tr(key))
        table = cast("DataTable[str]", self.query_one("#local-reader-roles", DataTable))
        for key in _ROLE_COLUMN_LOCALE_KEYS:
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

    def action_setup(self) -> None:
        """Run the one-shot setup, asking before it would install the runtime."""
        status = self.status
        if status is not None and not status.host.executable_located and not status.host.reachable:
            self._confirm_install(lambda: self._door.setup(consent=True))
            return
        self._launch(lambda: self._door.setup(consent=False), setup=True)

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
        checklist = cast("DataTable[str]", self.query_one("#local-reader-checklist", DataTable))
        checklist.clear()
        for item, state in local_reader_checklist(status):
            checklist.add_row(*local_reader_checklist_cells(item, state), key=item.value)
        table = cast("DataTable[str]", self.query_one("#local-reader-roles", DataTable))
        table.clear()
        for row in status.roles:
            table.add_row(*local_reader_role_cells(row), key=row.role.value)
        self.query_one("#local-reader-fitness", Static).update("\n".join(local_reader_fitness_lines(status)))
        if self.selected_role is not None:
            index = next(
                (index for index, row in enumerate(table.ordered_rows) if row.key.value == self.selected_role.value),
                None,
            )
            if index is not None:
                table.move_cursor(row=index)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Choose the role a pull, load, verify or remove acts on."""
        if event.data_table.id != "local-reader-roles" or event.row_key.value is None:
            return
        self.selected_role = ModelRole(str(event.row_key.value))
        self.query_one("#local-reader-selection", Static).update(
            tr("tui.local_reader.selected_role", role=tr(_ROLE_LOCALE_KEYS[self.selected_role]))
        )
        for selector in _ROLE_ACTION_BUTTONS:
            self.query_one(selector, Button).disabled = False

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Submit the pressed action through the operation platform."""
        role = self.selected_role
        match event.button.id:
            case "local-reader-refresh":
                self.action_refresh_status()
            case "local-reader-setup":
                self.action_setup()
            case "local-reader-install":
                self._confirm_install(lambda: self._door.install(consent=True))
            case "local-reader-start":
                self._launch(self._door.start)
            case "local-reader-pull" if role is not None:
                self._launch(lambda: self._door.pull(role))
            case "local-reader-load" if role is not None:
                self._launch(lambda: self._door.load(role))
            case "local-reader-verify" if role is not None:
                self._launch(lambda: self._door.verify(role))
            case "local-reader-remove" if role is not None:
                self._confirm_remove(role)
            case _:
                return

    def _notice(self, text: str) -> None:
        self.query_one("#local-reader-notice", Static).update(text)

    def _confirm_install(self, submit: Callable[[], Awaitable[OperationController]]) -> None:
        installer = RuntimeInstaller.NONE if self.status is None else self.status.host.installer
        if installer is RuntimeInstaller.NONE:
            self._notice(tr("tui.local_reader.no_installer"))
            return

        def decided(confirmed: bool | None) -> None:
            if confirmed:
                self._launch(submit, setup=True)
            else:
                self._notice(tr("tui.local_reader.install_cancelled"))

        self.app.push_screen(
            ConfirmScreen(
                title=tr("tui.local_reader.confirm.install_title"),
                message=tr("tui.local_reader.confirm.install_message", installer=installer.value),
                confirm_label=tr("tui.local_reader.confirm.install_accept"),
                cancel_label=tr("tui.local_reader.confirm.cancel"),
            ),
            decided,
        )

    def _confirm_remove(self, role: ModelRole) -> None:
        row = None if self.status is None else next((r for r in self.status.roles if r.role is role), None)
        model = row.model if row is not None and row.model else tr("tui.local_reader.no_model")

        def decided(confirmed: bool | None) -> None:
            if confirmed:
                self._launch(lambda: self._door.remove(role))
            else:
                self._notice(tr("tui.local_reader.remove_cancelled"))

        self.app.push_screen(
            ConfirmScreen(
                title=tr("tui.local_reader.confirm.remove_title"),
                message=tr("tui.local_reader.confirm.remove_message", model=model),
                confirm_label=tr("tui.local_reader.confirm.remove_accept"),
                cancel_label=tr("tui.local_reader.confirm.cancel"),
            ),
            decided,
        )

    def _launch(self, submit: Callable[[], Awaitable[OperationController]], *, setup: bool = False) -> None:
        self.run_worker(self._submit(submit(), setup=setup), group="local-reader-action", exclusive=True)

    async def _submit(self, submitted: Awaitable[OperationController], *, setup: bool) -> None:
        self._notice(tr("tui.local_reader.submitting"))
        try:
            controller = await submitted
        except CadrumoError:
            self._notice(tr("tui.local_reader.refused"))
            return
        self._notice("")

        def closed(_: OperationModalOutcomeV1 | None) -> None:
            if setup:
                self.run_worker(self._report_setup(controller), group="local-reader-result", exclusive=True)
            self.action_refresh_status()

        self.app.push_screen(OperationModal(controller), closed)

    async def _report_setup(self, controller: OperationController) -> None:
        try:
            result = await self._door.settled_result(controller)
        except CadrumoError:
            return
        if result is not None and result.steps:
            self._notice(local_reader_setup_notice(result))


__all__ = [
    "LocalReaderChecklistItem",
    "LocalReaderDoorV1",
    "LocalReaderScreen",
    "OperationLocalReaderDoor",
    "local_reader_checklist",
    "local_reader_checklist_cells",
    "local_reader_fitness_lines",
    "local_reader_role_cells",
    "local_reader_setup_notice",
    "local_reader_summary_lines",
]
