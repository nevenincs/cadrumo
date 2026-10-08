"""The installed picker persists new work and opens its fresh admission, over the native runtime.

A real runtime server with a real profile worker serves one password-authenticated
TUI session. The declarations screen comes from that session's workbench root,
the picker creates a declaration through the registered operation, the
workbench opens on the new work unit through the worker's form read, and the
declarations list is checked against fresh runtime generation reads, never
against local storage the frontend does not hold.
"""

from __future__ import annotations

import asyncio
import sys
import time
from collections.abc import Callable, Coroutine
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from importlib.metadata import version
from pathlib import Path
from threading import Event
from typing import Any
from uuid import UUID, uuid4

import pytest
from textual.widgets import Button, DataTable

from .....adapters.local_runtime.framing import VerifiedRuntimeConnection
from .....adapters.local_runtime.frontend_client import RuntimeFrontendClient
from .....adapters.local_runtime.installation import runtime_installation
from .....adapters.local_runtime.tests.profile_worker_support import owner_id
from .....adapters.local_runtime.tests.retained_server import RetainedRuntimeTransportServer
from .....adapters.local_runtime.windows import WindowsRuntimeEndpoint
from .....adapters.local_runtime.workbench_generation import read_workbench_generation
from .....adapters.persistence.storage.custody.tests.enrollment_support import PROFILE_INPUT, administration_subject
from .....adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from .....application.modelo.declarations_workspace_contracts import DeclarationsWorkspaceDeclarationRefV1
from .....application.modelo.work_form_models import ModeloWorkForm
from .....application.operations.registry import OperationFrontendProjection
from .....application.runtime.contracts import RuntimeClientHello
from .....application.user_profile.access_contracts import Availability, LoginEligibility, OsLockState, OsLoginContext
from .....core.external_constants import OutputLanguage
from .....core.period import Period
from .....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....runtime.profile_connections import RuntimeProfileConnections
from ....tests.modelo_operation_test_support import seeded_modelo_work_unit
from ...components.dialogs import ConfirmScreen
from ...components.host import ScreenHostApp
from ...modelo.workbench.screen import ModeloWorkbenchScreen
from ...navigation import TuiFocusIdentityV1, TuiNavigationTargetV1
from ...runtime_workbench import RuntimeWorkbenchRoot
from ..overview import DeclarationsOverviewScreen
from ..picker import NewDeclarationPicker

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires real native profile workers"),
]

_TARGET = Period.from_year_and_code(2025, "2T")


class _LoginObservation:
    login_id = "tui-declarations-create-login"

    def observe(self, *, credential_facilities: Availability) -> OsLoginContext:
        return OsLoginContext(
            login_id=self.login_id,
            os_owner_id=owner_id(),
            active=True,
            lock_state=OsLockState.UNLOCKED,
            unattended=LoginEligibility.ELIGIBLE,
            credential_facilities=credential_facilities,
        )


def _connect(endpoint: WindowsRuntimeEndpoint) -> VerifiedRuntimeConnection:
    return VerifiedRuntimeConnection(
        endpoint.connect(timeout=3),
        expected=RuntimeClientHello(product_version=version("cadrumo"), storage_identity=endpoint.storage_identity),
        deadline=time.monotonic() + 3,
    )


def _declarations(client: RuntimeFrontendClient) -> tuple[DeclarationsWorkspaceDeclarationRefV1, ...]:
    """The declarations a fresh runtime generation lists for this session's profile."""
    projection = read_workbench_generation(client, output_language=OutputLanguage.EN, timeout=90).declarations
    assert projection.projection is not None
    return projection.projection.declarations


async def _settle(app: ScreenHostApp[None], pilot: Any, rounds: int = 4) -> None:
    for _ in range(rounds):
        await app.workers.wait_for_complete()
        await pilot.pause()


async def _pick(app: ScreenHostApp[None], pilot: Any) -> NewDeclarationPicker:
    """Open the picker and move to the target period of Modelo 130."""
    await pilot.press("plus")
    await pilot.pause()
    picker = app.screen
    assert isinstance(picker, NewDeclarationPicker)
    table = picker.query_one("#declaration-picker-table", DataTable)
    table.move_cursor(row=next(i for i, row in enumerate(table.ordered_rows) if row.key.value == "130"))
    table.focus()
    await pilot.press("enter")
    await pilot.pause()
    table.move_cursor(row=next(i for i, item in enumerate(picker.visible_targets) if item.period == _TARGET))
    return picker


def _shown_form(screen: object) -> ModeloWorkForm | None:
    """The form a workbench screen has read, or ``None`` while another screen shows or it is reading."""
    return screen.form if isinstance(screen, ModeloWorkbenchScreen) else None


async def _opened_on(app: ScreenHostApp[None], pilot: Any, work_unit_id: str) -> None:
    """Wait until the workbench has read the expected declaration through the worker."""
    for _ in range(600):
        await pilot.pause(0.05)
        form = _shown_form(app.screen)
        if form is not None:
            assert form.work_unit_id == work_unit_id
            assert form.period == _TARGET
            return
    raise AssertionError("the created declaration's workbench never finished reading through the runtime")


def _drive(
    human: RuntimeFrontendClient, profile_id: UUID, reader: ThreadPoolExecutor
) -> Callable[[], Coroutine[Any, Any, None]]:
    async def run() -> None:
        async def reject_recovery() -> RuntimeFrontendClient:
            raise AssertionError("declaration creation must not open profile recovery")

        root = RuntimeWorkbenchRoot(
            human,
            profile_label="Enrollment tests",
            output_language=OutputLanguage.EN,
            open_recovery_client=reject_recovery,
        )
        binding = reader.submit(root.load).result(timeout=120)
        screen = binding.destination_catalogue.create_screen(
            TuiNavigationTargetV1(
                destination="workbench.declarations",
                focus=TuiFocusIdentityV1(destination="workbench.declarations", semantic_key="declarations.work"),
            )
        )
        assert isinstance(screen, DeclarationsOverviewScreen)
        before = reader.submit(_declarations, human).result(timeout=120)
        assert not any(item.period == _TARGET for item in before)
        app = ScreenHostApp[None](screen)
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.pause()
            picker = await _pick(app, pilot)
            await pilot.press("enter")
            await pilot.pause()
            assert app.focused is picker.query_one("#declaration-picker-create", Button)
            await pilot.press("enter")
            await _settle(app, pilot)
            created_rows = tuple(
                item for item in reader.submit(_declarations, human).result(timeout=120) if item.period == _TARGET
            )
            assert len(created_rows) == 1
            created = created_rows[0]
            assert str(created.modelo) == "130"
            await _opened_on(app, pilot, created.work_unit_id)
            assert isinstance(app.screen, ModeloWorkbenchScreen)
            app.screen.dismiss(None)
            await _settle(app, pilot)
            assert app.screen is screen
            table = screen.query_one("#declarations-list", DataTable)
            assert app.focused is table
            assert table.ordered_rows[table.cursor_row].key.value == created.work_unit_id

            after_create = reader.submit(_declarations, human).result(timeout=120)
            assert len(after_create) == len(before) + 1
            for confirm in (False, True):
                await _pick(app, pilot)
                await pilot.press("enter", "enter")
                await pilot.pause()
                assert isinstance(app.screen, ConfirmScreen)
                assert app.focused is app.screen.query_one("#btn-confirm-cancel", Button)
                await pilot.press("y" if confirm else "escape")
                await _settle(app, pilot)
                if confirm:
                    await _opened_on(app, pilot, created.work_unit_id)
                    assert isinstance(app.screen, ModeloWorkbenchScreen)
                    app.screen.dismiss(None)
                    await _settle(app, pilot)
                assert app.screen is screen
                # Reopening an existing period, confirmed or not, creates nothing.
                assert reader.submit(_declarations, human).result(timeout=120) == after_create
            app.exit()
        assert human.profile_id == profile_id

    return run


def test_installed_creation_opens_a_persisted_new_period_and_returns_to_that_row(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    storage_root = tmp_path / "cadrumo-storage"
    storage_root.mkdir()
    endpoint = WindowsRuntimeEndpoint(storage_root=storage_root)
    installation = runtime_installation(
        storage_root=storage_root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity
    )
    with administration_subject(
        tmp_path, os_owner_id=owner_id(), installation_id=installation.installation_id
    ) as subject:
        profile_id = subject.store.binding.profile_id
        seeded_modelo_work_unit(profile_id, operation=operation)
        close_active_bucket_session()
        stop, boot = Event(), uuid4()
        profiles = RuntimeProfileConnections(
            storage_root=storage_root,
            storage_identity=endpoint.storage_identity,
            runtime_boot_id=boot,
            stop=stop,
            capture_login=lambda _channel: _LoginObservation(),
            secret_store=lambda: subject.native,
        )
        # The installed runtime validates the operation graph before listening.
        profiles.prepare_registry()
        server = RetainedRuntimeTransportServer(
            endpoint, product_version=version("cadrumo"), stop=stop, profiles=profiles, boot_id=boot
        )
        with ThreadPoolExecutor(max_workers=1) as pool, ThreadPoolExecutor(max_workers=1) as reader:
            running = pool.submit(server.serve)
            try:
                assert server.ready.wait(3)
                with ExitStack() as cleanup:
                    human = RuntimeFrontendClient(
                        _connect(endpoint), profile_id=profile_id, frontend=OperationFrontendProjection.TUI
                    )
                    cleanup.callback(human.close)
                    password = bytearray(PROFILE_INPUT.encode())
                    # The production login budget: a cold admission launches and prepares a worker.
                    human.login_password(password)
                    assert not any(password)
                    asyncio.run(_drive(human, profile_id, reader)())
            finally:
                primary = sys.exception()
                stop.set()
                try:
                    try:
                        running.result(timeout=20)
                    except Exception:
                        if primary is None:
                            raise
                finally:
                    endpoint.close()
