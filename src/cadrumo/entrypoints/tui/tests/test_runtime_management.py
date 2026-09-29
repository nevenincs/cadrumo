"""A passive TUI status panel keeps readiness separate from manager policy."""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from importlib.metadata import version
from pathlib import Path
from threading import Event, get_ident
from uuid import uuid4

import pytest
from textual.pilot import Pilot
from textual.widgets import Button, Static

from cadrumo.adapters.local_runtime.server import RuntimeTransportServer
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.application.runtime.management import (
    RuntimeManagerInspection,
    RuntimeManagerKind,
    RuntimeManagerProcessState,
)
from cadrumo.application.runtime.management_status import (
    RuntimeListenerState,
    RuntimeManagementSnapshot,
    RuntimeManagerAvailability,
)
from cadrumo.core.config import override_settings
from cadrumo.core.i18n.render import tr

from ..app import CadrumoTuiApp
from ..components.host import ScreenHostApp
from ..runtime_management import RuntimeManagementScreen

pytestmark = [pytest.mark.hex_entrypoint]


async def _until[T](pilot: Pilot[T], condition: Callable[[], bool]) -> None:
    async with asyncio.timeout(5):
        while not condition():
            await pilot.pause(0.02)


def _available() -> RuntimeManagementSnapshot:
    return RuntimeManagementSnapshot(
        listener=RuntimeListenerState.READY,
        manager_availability=RuntimeManagerAvailability.AVAILABLE,
        manager=RuntimeManagerInspection(
            kind=RuntimeManagerKind.WINDOWS_TASK,
            available=True,
            provisioned=True,
            binding_matches=False,
            login_autostart=False,
            process_state=RuntimeManagerProcessState.STOPPED,
        ),
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_passive_snapshot_shows_independent_axes_and_refreshes_once() -> None:
    observations = [
        _available(),
        RuntimeManagementSnapshot(
            listener=RuntimeListenerState.UNAVAILABLE,
            manager_availability=RuntimeManagerAvailability.UNSUPPORTED,
        ),
    ]
    calls = 0
    ui_thread = get_ident()

    async def read() -> RuntimeManagementSnapshot:
        nonlocal calls
        assert get_ident() != ui_thread
        result = observations[calls]
        calls += 1
        return result

    screen = RuntimeManagementScreen(reader=read)
    async with ScreenHostApp(screen).run_test(size=(100, 30)) as pilot:
        await _until(pilot, lambda: calls == 1 and not screen._busy)
        assert tr("tui.runtime_management.listener.ready") in str(
            screen.query_one("#runtime-management-listener", Static).content
        )
        assert tr("tui.runtime_management.availability.available") in str(
            screen.query_one("#runtime-management-manager-availability", Static).content
        )
        assert tr("flows.confirm.yes") in str(screen.query_one("#runtime-management-provisioned", Static).content)
        assert tr("flows.confirm.no") in str(screen.query_one("#runtime-management-binding", Static).content)
        assert tr("tui.runtime_management.process.stopped") in str(
            screen.query_one("#runtime-management-process", Static).content
        )
        assert not screen.query("Input")
        screen.query_one("#runtime-management-refresh", Button).press()
        await _until(pilot, lambda: calls == 2 and not screen._busy)
        assert tr("tui.runtime_management.listener.unavailable") in str(
            screen.query_one("#runtime-management-listener", Static).content
        )
        assert tr("tui.runtime_management.availability.unsupported") in str(
            screen.query_one("#runtime-management-manager-availability", Static).content
        )
        assert tr("tui.runtime_management.not_reported") in str(
            screen.query_one("#runtime-management-process", Static).content
        )
        assert calls == 2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_close_owns_pending_read_and_never_restores_late_snapshot() -> None:
    started, release, completed = Event(), Event(), Event()
    calls = 0

    async def read() -> RuntimeManagementSnapshot:
        nonlocal calls
        calls += 1
        started.set()
        await asyncio.to_thread(release.wait)
        completed.set()
        return _available()

    app = CadrumoTuiApp(runtime_management_reader=read)
    async with app.run_test(size=(100, 30)) as pilot:
        app.action_runtime_management()
        await _until(pilot, lambda: isinstance(app.screen, RuntimeManagementScreen))
        screen = app.screen
        assert isinstance(screen, RuntimeManagementScreen)
        assert await asyncio.to_thread(started.wait, 3)
        assert screen.query_one("#runtime-management-refresh", Button).disabled
        screen.query_one("#runtime-management-refresh", Button).press()
        await pilot.pause(0.02)
        assert calls == 1
        screen.query_one("#runtime-management-close", Button).press()
        release.set()
        assert await asyncio.to_thread(completed.wait, 3)
        await _until(pilot, lambda: not isinstance(app.screen, RuntimeManagementScreen))
        assert calls == 1
        assert not screen._live


@pytest.mark.unit
@pytest.mark.asyncio
async def test_close_before_queued_refresh_enters_never_starts_another_read() -> None:
    calls = 0

    async def read() -> RuntimeManagementSnapshot:
        nonlocal calls
        calls += 1
        return _available()

    app = CadrumoTuiApp(runtime_management_reader=read)
    async with app.run_test(size=(100, 30)) as pilot:
        app.action_runtime_management()
        await _until(pilot, lambda: isinstance(app.screen, RuntimeManagementScreen) and calls == 1)
        screen = app.screen
        assert isinstance(screen, RuntimeManagementScreen)
        await _until(pilot, lambda: not screen._busy)
        screen._start_refresh()
        assert screen._busy
        screen.action_close()
        await _until(pilot, lambda: not isinstance(app.screen, RuntimeManagementScreen))
        await pilot.pause(0.02)
        assert calls == 1
        assert not screen._live


@pytest.mark.unit
@pytest.mark.asyncio
async def test_failed_refresh_clears_stale_manager_facts() -> None:
    calls = 0

    async def read() -> RuntimeManagementSnapshot:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("synthetic private path must not surface")
        return _available()

    screen = RuntimeManagementScreen(reader=read)
    async with ScreenHostApp(screen).run_test(size=(100, 30)) as pilot:
        await _until(pilot, lambda: calls == 1 and not screen._busy)
        screen.query_one("#runtime-management-refresh", Button).press()
        await _until(pilot, lambda: calls == 2 and not screen._busy)
        assert tr("tui.runtime_management.refused") in str(
            screen.query_one("#runtime-management-status", Static).content
        )
        assert tr("tui.runtime_management.not_reported") in str(
            screen.query_one("#runtime-management-provisioned", Static).content
        )
        assert "synthetic private path" not in str(screen.query_one("#runtime-management-status", Static).content)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_human_root_offers_profile_free_status_as_a_system_command() -> None:
    calls = 0

    async def read() -> RuntimeManagementSnapshot:
        nonlocal calls
        calls += 1
        return RuntimeManagementSnapshot(
            listener=RuntimeListenerState.UNKNOWN,
            manager_availability=RuntimeManagerAvailability.UNKNOWN,
        )

    app = CadrumoTuiApp(runtime_management_reader=read)
    async with app.run_test(size=(100, 30)) as pilot:
        assert tr("tui.runtime_management.open") in {item.title for item in app.get_system_commands(app.screen)}
        app.action_runtime_management()
        await _until(pilot, lambda: isinstance(app.screen, RuntimeManagementScreen) and calls == 1)
        assert isinstance(app.screen, RuntimeManagementScreen)
        app.screen.action_close()
        await _until(pilot, lambda: not isinstance(app.screen, RuntimeManagementScreen))


@pytest.mark.integration
@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows owner-only pipes")
@pytest.mark.asyncio
async def test_installed_tui_passively_observes_existing_native_listener(tmp_path: Path) -> None:
    """The default UI reader uses the real peer-verified status path without login."""
    root = tmp_path / f"tui-management-{uuid4()}"
    root.mkdir()
    endpoint = WindowsRuntimeEndpoint(storage_root=root)
    stop = Event()
    server = RuntimeTransportServer(endpoint, product_version=version("cadrumo"), stop=stop)
    try:
        with ThreadPoolExecutor(max_workers=1) as pool, override_settings(cadrumo_local_storage_root=root):
            running = pool.submit(server.serve)
            try:
                assert await asyncio.to_thread(server.ready.wait, 3)
                screen = RuntimeManagementScreen()
                async with ScreenHostApp(screen).run_test(size=(100, 30)) as pilot:
                    await _until(
                        pilot,
                        lambda: (
                            tr("tui.runtime_management.listener.ready")
                            in str(screen.query_one("#runtime-management-listener", Static).content)
                            and not screen._busy
                        ),
                    )
                    availability = str(screen.query_one("#runtime-management-manager-availability", Static).content)
                    assert any(
                        tr(key) in availability
                        for key in (
                            "tui.runtime_management.availability.available",
                            "tui.runtime_management.availability.unavailable",
                        )
                    )
                    assert not screen.query("Input")
                    assert not stop.is_set()
            finally:
                stop.set()
                await asyncio.to_thread(running.result, 10)
    finally:
        endpoint.close()
