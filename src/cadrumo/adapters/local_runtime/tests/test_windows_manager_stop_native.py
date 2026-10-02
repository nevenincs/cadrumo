"""Bounded native experiment for per-user Task Scheduler stop behavior."""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path
from uuid import uuid4

import pytest

from cadrumo.adapters.local_runtime.framing import RuntimeTransportCleanup, VerifiedRuntimeConnection
from cadrumo.application.runtime.contracts import RuntimeClientHello, RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.application.runtime.owner_control import (
    RuntimeStopAccepted,
    RuntimeStopConfirm,
    RuntimeStopPreview,
    RuntimeStopPreviewRequest,
)
from cadrumo.application.runtime.profile_access import PROFILE_ADMISSION_TIMEOUT_SECONDS
from cadrumo.core.async_cleanup import (
    async_cleanup_failures,
    await_cancellation_complete,
    close_async_resources,
)

from .windows_managed_runtime_fixture import (
    WINDOWS_STOP_OBSERVATION_SECONDS,
    WindowsFixtureEvent,
    installed_windows_runtime_task,
    installed_windows_task_identity,
    make_windows_fixture_root,
    observe_windows_probe_no_restart,
    read_windows_probe_events,
    registered_windows_probe_task,
    require_windows_manager_desktop,
    start_exact_windows_task,
    stop_exact_windows_task,
    stop_windows_probe_and_release_drain,
    wait_windows_probe_event,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_outbound_adapter,
    pytest.mark.serial,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Task Scheduler and an interactive token"),
]


@pytest.mark.parametrize(
    ("scenario", "terminal_event"),
    (("graceful", "exited_successfully"), ("fail_on_close", "failure_during_stop")),
)
def test_task_stop_delivers_close_and_suppresses_restart(tmp_path: Path, scenario: str, terminal_event: str) -> None:
    """Observe hidden WM_CLOSE drain and intentional-stop restart suppression."""
    pythonw, owner_sid = require_windows_manager_desktop()
    root = make_windows_fixture_root(tmp_path)
    with registered_windows_probe_task(root=root, scenario=scenario, pythonw=pythonw, owner_sid=owner_sid) as (
        task_name,
        identity,
        events_path,
    ):
        start_exact_windows_task(task_name, identity)
        events = wait_windows_probe_event(events_path, "window_ready", timeout=12)
        assert len(tuple(event for event in events if event["kind"] == "started")) == 1
        if scenario == "graceful":
            process = next(event for event in events if event["kind"] == "window_ready")
            events = stop_windows_probe_and_release_drain(task_name, identity, root, events_path, process)
            assert any(event["kind"] == "drain_release_observed" for event in events)
            assert any(event["kind"] == "drain_started" for event in events)
            assert any(event["kind"] == "drain_completed" for event in events)
        else:
            stop_exact_windows_task(task_name, identity)
        events = wait_windows_probe_event(events_path, terminal_event, timeout=12)
        assert any(event["kind"] == "wm_close" for event in events)
        assert any(event["kind"] == terminal_event for event in events)
        observe_windows_probe_no_restart(events_path)


def test_task_restart_on_unrequested_failure_remains_active(tmp_path: Path) -> None:
    """Control: a failure without Stop must restart after the configured minute."""
    pythonw, owner_sid = require_windows_manager_desktop()
    root = make_windows_fixture_root(tmp_path)
    with registered_windows_probe_task(root=root, scenario="fail_start", pythonw=pythonw, owner_sid=owner_sid) as (
        task_name,
        identity,
        events_path,
    ):
        start_exact_windows_task(task_name, identity)
        wait_windows_probe_event(events_path, "started", timeout=12)
        deadline = time.monotonic() + 90
        starts: tuple[WindowsFixtureEvent, ...] = ()
        while time.monotonic() < deadline:
            starts = tuple(event for event in read_windows_probe_events(events_path) if event["kind"] == "started")
            if len(starts) >= 2:
                break
            time.sleep(0.25)
        assert len(starts) >= 2, "Task Scheduler did not retry an unrequested failure within its bound"
        assert starts[1]["at_ns"] - starts[0]["at_ns"] >= 55_000_000_000
        assert starts[1]["pid"] != starts[0]["pid"] or starts[1]["start"] != starts[0]["start"]


@pytest.mark.asyncio
async def test_installed_runtime_owner_stop_preserves_bound_task_and_suppresses_restart(tmp_path: Path) -> None:
    """Exercise the real installed runtime, exact task matcher and owner control."""
    async with installed_windows_runtime_task(tmp_path) as task:
        endpoint = task.endpoint
        product_version, binding, manager, task_name = task.product_version, task.binding, task.manager, task.task_name
        configured = await manager.configure(login_autostart=False)
        assert configured.binding_matches and not configured.login_autostart
        if installed_windows_task_identity(task_name, binding) is None:
            raise RuntimeError("configured installed task disappeared")
        task.mark_launch_possible()
        await manager.start()
        # Real cold registry preparation shares the installed admission budget;
        # the short probe deadlines elsewhere do not govern runtime readiness.
        deadline = time.monotonic() + PROFILE_ADMISSION_TIMEOUT_SECONDS
        while True:
            try:
                client = VerifiedRuntimeConnection(
                    endpoint.connect(timeout=1),
                    expected=RuntimeClientHello(
                        product_version=product_version, storage_identity=endpoint.storage_identity
                    ),
                    deadline=time.monotonic() + 3,
                )
                break
            except RuntimeRefusalError as error:
                if error.reason is not RuntimeRefusalCode.ENDPOINT_NOT_READY or time.monotonic() >= deadline:
                    raise
                await asyncio.sleep(0.05)
        wire_primary_errors: list[BaseException] = []
        try:
            process, pinned_boot = await task.observe_live_process()
            preview = client.owner_control(RuntimeStopPreviewRequest(request_id=uuid4()), deadline=time.monotonic() + 5)
            assert isinstance(preview, RuntimeStopPreview)
            assert preview.runtime_boot_id == pinned_boot
            accepted = client.owner_control(
                RuntimeStopConfirm(
                    request_id=uuid4(),
                    runtime_boot_id=preview.runtime_boot_id,
                    preview_id=preview.preview_id,
                    acknowledge_all_profiles_and_work=True,
                ),
                deadline=time.monotonic() + 8,
            )
            assert isinstance(accepted, RuntimeStopAccepted)
        except BaseException as error:
            wire_primary_errors.append(error)
            raise
        finally:
            wire_primary = wire_primary_errors[0] if wire_primary_errors else None
            wire_owner = (
                next(
                    (
                        resource
                        for failure in async_cleanup_failures(wire_primary)
                        for resource in failure.resources
                        if isinstance(resource, RuntimeTransportCleanup) and resource.resource is client
                    ),
                    None,
                )
                if wire_primary is not None
                else None
            )
            await close_async_resources(
                wire_owner if wire_owner is not None else RuntimeTransportCleanup(client),
                task_name="installed-wire-stop-close",
                primary_error=wire_primary,
            )
        await await_cancellation_complete(
            asyncio.to_thread(process.wait, timeout=25), task_name="installed-wire-stop-physical-exit"
        )
        deadline = time.monotonic() + 25
        while True:
            current = await manager.inspect()
            assert current.binding_matches and not current.login_autostart
            if current.process_state.name == "STOPPED":
                break
            if time.monotonic() >= deadline:
                raise AssertionError("installed runtime did not stop within its drain bound")
            await asyncio.sleep(0.05)
        observation_deadline = time.monotonic() + WINDOWS_STOP_OBSERVATION_SECONDS
        while time.monotonic() < observation_deadline:
            current = await manager.inspect()
            assert current.binding_matches and not current.login_autostart
            assert current.process_state.name == "STOPPED", "managed runtime restarted after explicit stop"
            await asyncio.sleep(0.25)
