"""The document reader page renders measured truth and submits only through its door.

The consent and confirmation flows use a recording door, because what they
prove is what the page submits. The load and setup flows use the real door
over the real operation platform, with the model runtime as a loopback
endpoint -- the only substitute is at that transport boundary.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Callable, Generator, Mapping
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from pathlib import Path
from typing import ClassVar, override

import pytest
from textual.pilot import Pilot
from textual.widgets import Button, DataTable, Static

from .....adapters.persistence.operations.journal import OperationJournalRepository
from .....adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from .....adapters.persistence.operations.secure_references import operation_secure_reference_repository
from .....adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from .....application.local_reader import (
    LocalReaderDocumentReadiness,
    LocalReaderRoleStatus,
    LocalReaderStatus,
    RoleFitnessOutcome,
    RoleFitnessState,
)
from .....application.local_reader_operation import (
    LocalReaderProvisionPublicResultV1,
    build_local_reader_operation_definition,
    build_local_reader_operation_registration,
)
from .....application.operations.composition import OperationComposedServices, compose_operation_services
from .....application.operations.registry import OperationRegistry
from .....application.operations.tests.authority_test_support import unread_authority_operation
from .....application.provisioning_contracts import (
    ProvisioningPreconditionCondition,
    provisioning_no_recovery_verdict,
)
from .....application.provisioning_host import RuntimeHostPlatform, RuntimeHostStatus, RuntimeInstaller
from .....core.config import Settings, override_settings
from .....core.errors.hierarchy import InternalInvariantError
from .....core.model_catalogue import ModelRole, default_model_runtime_id
from .....tests.loopback_llm import SilentLoopbackHandler, read_json_body, serving_loopback, write_json_response
from ...components.dialogs import ConfirmScreen
from ...components.host import ScreenHostApp
from ...operations.controller import OperationController
from ...operations.modal import OperationModal
from ..local_reader import (
    LocalReaderChecklistItem,
    LocalReaderScreen,
    OperationLocalReaderDoor,
    local_reader_checklist,
    local_reader_fitness_lines,
    local_reader_role_cells,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_TEXT = default_model_runtime_id(ModelRole.TEXT_EXTRACTION)
_VISION = default_model_runtime_id(ModelRole.VISION_TRANSCRIPTION)


def _host(*, executable_located: bool, reachable: bool, installer: RuntimeInstaller) -> RuntimeHostStatus:
    facts = {"runtime_reachable": reachable}
    verdict = (
        None
        if reachable
        else provisioning_no_recovery_verdict(ProvisioningPreconditionCondition.RUNTIME_REACHABLE, facts=facts)
    )
    return RuntimeHostStatus.model_validate(
        {
            "platform": RuntimeHostPlatform.WINDOWS,
            "endpoint_url": "http://127.0.0.1",
            "endpoint_local": True,
            "executable_located": executable_located,
            "reachable": reachable,
            "version": "0.9.0" if reachable else None,
            "installer": installer,
            "available": reachable,
            "facts": facts,
            "precondition_verdict": verdict,
        }
    )


def _status(
    *,
    executable_located: bool = True,
    installer: RuntimeInstaller = RuntimeInstaller.WINGET,
) -> LocalReaderStatus:
    return LocalReaderStatus(
        host=_host(executable_located=executable_located, reachable=False, installer=installer),
        roles=(
            LocalReaderRoleStatus(
                role=ModelRole.TEXT_EXTRACTION,
                model=_TEXT,
                ready=False,
                failed_condition_id=ProvisioningPreconditionCondition.RUNTIME_REACHABLE.value,
            ),
        ),
        extraction_ready=False,
        document_readiness=LocalReaderDocumentReadiness.TEXT_LAYER_ONLY,
        text_layer_model_fill_available=False,
    )


class _Door:
    """Measures a fixed status and records every submission instead of running it."""

    def __init__(self, status: LocalReaderStatus) -> None:
        self.status = status
        self.submitted: list[tuple[str, object]] = []

    def read_status(self) -> LocalReaderStatus:
        return self.status

    def _record(self, action: str, argument: object) -> OperationController:
        self.submitted.append((action, argument))
        raise InternalInvariantError("recorded, not run")

    async def setup(self, *, consent: bool) -> OperationController:
        return self._record("setup", consent)

    async def install(self, *, consent: bool) -> OperationController:
        return self._record("install", consent)

    async def start(self) -> OperationController:
        return self._record("start", None)

    async def pull(self, role: ModelRole) -> OperationController:
        return self._record("pull", role)

    async def load(self, role: ModelRole) -> OperationController:
        return self._record("load", role)

    async def verify(self, role: ModelRole) -> OperationController:
        return self._record("verify", role)

    async def remove(self, role: ModelRole) -> OperationController:
        return self._record("remove", role)

    async def settled_result(self, controller: OperationController) -> LocalReaderProvisionPublicResultV1 | None:
        del controller
        return None


def _notice(screen: LocalReaderScreen) -> str:
    return str(screen.query_one("#local-reader-notice", Static).render())


def test_an_unmeasured_answer_never_reads_as_not_installed() -> None:
    row = _status().roles[0]
    with override_settings(cadrumo_output_language="en"):
        cells = local_reader_role_cells(row)
    assert cells[2] == "not measured"
    assert cells[3] == "not measured"
    assert cells[4] == "-"
    assert cells[5] == "no"


def test_checklist_keeps_unmeasured_steps_unmeasured() -> None:
    states = dict(local_reader_checklist(_status(executable_located=False)))

    assert states[LocalReaderChecklistItem.SERVICE_INSTALLED] is False
    assert states[LocalReaderChecklistItem.SERVICE_RUNNING] is False
    assert states[LocalReaderChecklistItem.TEXT_MODEL_PULLED] is None
    assert states[LocalReaderChecklistItem.VISION_MODEL_PULLED] is None
    assert states[LocalReaderChecklistItem.MODELS_LOADED] is None
    assert states[LocalReaderChecklistItem.VERIFIED] is None


async def _mounted(pilot: Pilot[None]) -> None:
    await pilot.app.workers.wait_for_complete()
    await pilot.pause()


@pytest.mark.asyncio
async def test_page_shows_the_checklist_and_enables_role_actions_on_selection() -> None:
    screen = LocalReaderScreen(_Door(_status()))
    with override_settings(cadrumo_output_language="en"):
        async with ScreenHostApp[None](screen).run_test(size=(110, 50)) as pilot:
            await _mounted(pilot)
            summary = str(screen.query_one("#local-reader-summary", Static).render())
            assert "answering: no" in summary
            checklist = screen.query_one("#local-reader-checklist", DataTable)
            assert checklist.row_count == len(LocalReaderChecklistItem)
            assert checklist.get_row_at(0) == ["Runtime installed", "done"]
            assert checklist.get_row_at(1) == ["Runtime running", "to do"]
            assert all(screen.query_one(f"#local-reader-{name}", Button).disabled for name in ("load", "remove"))
            screen.query_one("#local-reader-roles", DataTable).focus()
            await pilot.press("enter")
            assert screen.selected_role is ModelRole.TEXT_EXTRACTION
            assert not any(
                screen.query_one(f"#local-reader-{name}", Button).disabled
                for name in ("pull", "load", "verify", "remove")
            )


@pytest.mark.asyncio
async def test_setup_on_a_host_without_the_runtime_asks_first_and_cancel_submits_nothing() -> None:
    door = _Door(_status(executable_located=False))
    screen = LocalReaderScreen(door)
    with override_settings(cadrumo_output_language="en"):
        async with ScreenHostApp[None](screen).run_test(size=(110, 50)) as pilot:
            await _mounted(pilot)
            await pilot.press("s")
            await pilot.pause()
            dialog = pilot.app.screen
            assert isinstance(dialog, ConfirmScreen)
            assert pilot.app.focused is not None
            assert pilot.app.focused.id == "btn-confirm-cancel", "the safe choice has the focus"
            await pilot.press("enter")
            await pilot.pause()
            assert pilot.app.screen is screen
            assert door.submitted == []
            assert _notice(screen) == "Install cancelled; nothing was changed."


@pytest.mark.asyncio
async def test_confirmed_install_submits_with_consent_and_refusal_is_reported() -> None:
    door = _Door(_status(executable_located=False))
    screen = LocalReaderScreen(door)
    with override_settings(cadrumo_output_language="en"):
        async with ScreenHostApp[None](screen).run_test(size=(110, 50)) as pilot:
            await _mounted(pilot)
            screen.query_one("#local-reader-install", Button).press()
            await pilot.pause()
            assert isinstance(pilot.app.screen, ConfirmScreen)
            await pilot.press("y")
            await pilot.app.workers.wait_for_complete()
            await pilot.pause()
            assert door.submitted == [("install", True)]
            assert _notice(screen) == "The action could not be started."


@pytest.mark.asyncio
async def test_install_without_an_installer_is_refused_without_a_dialog() -> None:
    door = _Door(_status(executable_located=False, installer=RuntimeInstaller.NONE))
    screen = LocalReaderScreen(door)
    with override_settings(cadrumo_output_language="en"):
        async with ScreenHostApp[None](screen).run_test(size=(110, 50)) as pilot:
            await _mounted(pilot)
            screen.query_one("#local-reader-install", Button).press()
            await pilot.pause()
            assert pilot.app.screen is screen
            assert door.submitted == []
            assert _notice(screen).startswith("No installer is available on this system.")


@pytest.mark.asyncio
async def test_remove_asks_for_confirmation_naming_the_model() -> None:
    door = _Door(_status())
    screen = LocalReaderScreen(door)
    with override_settings(cadrumo_output_language="en"):
        async with ScreenHostApp[None](screen).run_test(size=(110, 50)) as pilot:
            await _mounted(pilot)
            screen.query_one("#local-reader-roles", DataTable).focus()
            await pilot.press("enter")
            screen.query_one("#local-reader-remove", Button).press()
            await pilot.pause()
            dialog = pilot.app.screen
            assert isinstance(dialog, ConfirmScreen)
            assert _TEXT in str(dialog.query_one("#confirm-message", Static).render())
            await pilot.press("escape")
            await pilot.pause()
            assert door.submitted == []
            assert _notice(screen) == "Removal cancelled; nothing was changed."


class _Runtime(SilentLoopbackHandler):
    installed: ClassVar[set[str]] = set()
    residents: ClassVar[set[str]] = set()

    @override
    def do_GET(self) -> None:
        if self.path == "/api/version":
            write_json_response(self, {"version": "0.9.0"}, status=HTTPStatus.OK)
        elif self.path in {"/api/tags", "/api/ps"}:
            names = self.installed if self.path == "/api/tags" else self.residents
            rows = [{"name": name, "size": 1, "digest": f"sha256:{name}"} for name in sorted(names)]
            write_json_response(self, {"models": rows}, status=HTTPStatus.OK)
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    @override
    def do_POST(self) -> None:
        body = read_json_body(self)
        if self.path == "/api/generate" and "prompt" not in body:
            self.residents.add(str(body.get("model")))
            write_json_response(self, {"done": True}, status=HTTPStatus.OK)
        elif self.path == "/api/pull":
            payload = (json.dumps({"error": "registry unavailable"}) + "\n").encode()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        else:
            self.send_error(HTTPStatus.NOT_FOUND)


def _unused_spawn(executable: Path, env: Mapping[str, str]) -> int:
    raise AssertionError(f"a reachable runtime is never spawned: {executable} {len(env)}")


def _unused_installer(installer: RuntimeInstaller, executable: Path, timeout_s: float) -> int:
    raise AssertionError(f"a reachable runtime is never installed: {installer} {executable} {timeout_s}")


def _unused_probe(model: str, settings: Settings) -> RoleFitnessOutcome:
    raise AssertionError(f"no verification runs in these flows: {model} {settings.cadrumo_output_language}")


def _services(root: Path) -> OperationComposedServices:
    definition = build_local_reader_operation_definition(
        spawn=_unused_spawn, run_installer=_unused_installer, text_probe=_unused_probe
    )
    journal = OperationJournalRepository(storage_root=root)
    return compose_operation_services(
        registry=OperationRegistry(
            definitions=(definition,),
            public_registrations=(build_local_reader_operation_registration(definition),),
        ),
        authority_operation=unread_authority_operation(),
        journal=journal,
        reader=journal,
        event_stream=journal,
        leases=OperationLeaseFilesystemRepository(storage_root=root),
        operands=operation_secure_reference_repository(),
        owner_id="1" * 64,
        lease_token_factory=lambda: "2" * 64,
        clock=lambda: datetime.now(UTC),
        lease_duration=timedelta(minutes=5),
        execution_timeout=timedelta(seconds=_SETTLE_SECONDS),
        cleanup_timeout=timedelta(seconds=5),
    )


_SETTLE_SECONDS = 60


@contextmanager
def _real_runtime(tmp_path: Path, *, installed: set[str]) -> Generator[Path]:
    _Runtime.installed = set(installed)
    _Runtime.residents = set()
    with (
        isolated_runtime_profile(tmp_path=tmp_path) as profile,
        serving_loopback(_Runtime, path="/api/chat") as chat_url,
        override_settings(
            cadrumo_llm_ollama_chat_url=chat_url,
            cadrumo_llm_ollama_text_model=_TEXT,
            cadrumo_llm_ollama_vision_model=_VISION,
            cadrumo_llm_contention_safety_margin_bytes=0,
            cadrumo_output_language="en",
        ),
    ):
        yield profile.storage_root


async def _settle(pilot: Pilot[None], screen: LocalReaderScreen, settled: Callable[[], bool]) -> None:
    """Drive the page until ``settled`` holds, closing any operation modal still on top.

    Bounded by the operations' own execution budget rather than a poll count,
    so a loaded machine cannot turn a slow but valid run into a failure.
    """
    deadline = time.monotonic() + _SETTLE_SECONDS
    while time.monotonic() < deadline:
        await pilot.pause(0.1)
        if isinstance(pilot.app.screen, OperationModal):
            await pilot.press("escape")
            continue
        await pilot.app.workers.wait_for_complete()
        if pilot.app.screen.id != screen.id:
            continue
        if settled():
            return
        # Closing the modal detaches the operation; the page re-measures once
        # on close, which can precede the operation's end. Re-measure as the
        # operator's refresh would until the outcome is visible.
        screen.action_refresh_status()
    raise AssertionError(f"the page never reached the settled state: {screen.status!r}")


def _text_resident(screen: LocalReaderScreen) -> bool:
    status = screen.status
    return status is not None and any(
        row.role is ModelRole.TEXT_EXTRACTION and row.resident is True for row in status.roles
    )


@pytest.mark.timeout(120)
def test_load_through_the_real_door_leaves_the_model_resident(tmp_path: Path) -> None:
    with _real_runtime(tmp_path, installed={_TEXT, _VISION}) as root:

        async def run() -> None:
            services = _services(root)
            try:
                screen = LocalReaderScreen(OperationLocalReaderDoor(services))
                async with ScreenHostApp[None](screen).run_test(size=(110, 50)) as pilot:
                    await _mounted(pilot)
                    table = screen.query_one("#local-reader-roles", DataTable)
                    table.focus()
                    table.move_cursor(row=table.get_row_index(ModelRole.TEXT_EXTRACTION.value))
                    await pilot.press("enter")
                    assert screen.selected_role is ModelRole.TEXT_EXTRACTION
                    screen.query_one("#local-reader-load", Button).press()
                    await _settle(pilot, screen, lambda: _text_resident(screen))
                    assert screen.status is not None
                    rows = {row.role: row for row in screen.status.roles}
                    assert rows[ModelRole.TEXT_EXTRACTION].resident is True
                    assert rows[ModelRole.VISION_TRANSCRIPTION].resident is False
                    assert dict(local_reader_checklist(screen.status))[LocalReaderChecklistItem.MODELS_LOADED] is False
            finally:
                await services.shutdown()

        asyncio.run(run())
        assert _Runtime.residents == {_TEXT}


@pytest.mark.timeout(120)
def test_setup_through_the_real_door_reports_the_step_that_stopped_it(tmp_path: Path) -> None:
    with _real_runtime(tmp_path, installed=set()) as root:

        async def run() -> None:
            services = _services(root)
            try:
                screen = LocalReaderScreen(OperationLocalReaderDoor(services))
                async with ScreenHostApp[None](screen).run_test(size=(110, 50)) as pilot:
                    await _mounted(pilot)
                    await pilot.press("s")
                    await _settle(pilot, screen, lambda: _notice(screen).startswith("Setup stopped"))
                    assert _notice(screen) == (
                        f"Setup stopped at download: {ProvisioningPreconditionCondition.MODEL_PULL_SUCCEEDED.value}."
                    )
            finally:
                await services.shutdown()

        asyncio.run(run())
        assert _Runtime.residents == set()


def _probed_status(fitness: RoleFitnessState) -> LocalReaderStatus:
    base = _status()
    row = base.roles[0].model_copy(update={"fitness": fitness})
    return base.model_copy(update={"roles": (row,)})


@pytest.mark.parametrize(
    ("fitness", "cell", "explained"),
    [
        (RoleFitnessState.FIT, "fit", None),
        (RoleFitnessState.UNFIT, "unfit", "could not be used to read an invoice"),
        (RoleFitnessState.TIMED_OUT, "timed out", "did not finish its test answer"),
        (RoleFitnessState.NOT_VERIFIED, "not verified", "This does not mean the model is unfit"),
    ],
)
def test_each_fitness_state_reads_as_itself(fitness: RoleFitnessState, cell: str, explained: str | None) -> None:
    status = _probed_status(fitness)
    with override_settings(cadrumo_output_language="en"):
        cells = local_reader_role_cells(status.roles[0])
        lines = local_reader_fitness_lines(status)

    assert cells[4] == cell
    if explained is None:
        assert lines == ()
    else:
        (line,) = lines
        assert line.startswith("Documents with text: ")
        assert explained in line
        assert _TEXT in line


def test_the_verified_checklist_row_follows_extraction_readiness_not_a_fit_verdict() -> None:
    status = _probed_status(RoleFitnessState.FIT)
    assert dict(local_reader_checklist(status))[LocalReaderChecklistItem.VERIFIED] is None, "runtime unmeasured"
