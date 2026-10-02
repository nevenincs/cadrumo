"""Native installed supervision keeps the bound Task while replacing a lost host."""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

import pytest

from cadrumo.adapters.local_runtime.framing import RuntimeTransportCleanup
from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.application.runtime.management import RuntimeManagerProcessState
from cadrumo.core.async_cleanup import await_cancellation_complete, close_async_resources, has_async_cleanup_failure

from .windows_managed_runtime_fixture import (
    installed_windows_runtime_task,
    installed_windows_task_identity,
    installed_windows_task_instance,
    retain_windows_runtime_tree,
    retain_windows_task_engine,
    wait_windows_recovery_processes_gone,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_outbound_adapter,
    pytest.mark.serial,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Task Scheduler and an interactive token"),
]


@pytest.mark.asyncio
async def test_installed_task_supervisor_replaces_crashed_host_without_demand(tmp_path: Path) -> None:
    """Actual native crash preserves the Task; confirmed Stop ends its retained engine."""
    async with installed_windows_runtime_task(tmp_path) as task:
        identity = installed_windows_task_identity(task.task_name, task.binding)
        assert identity is not None
        task.mark_launch_possible()
        await task.manager.start()
        deadline = time.monotonic() + 75
        while True:
            try:
                observed, first_boot = await task.observe_live_process(deadline=deadline)
                break
            except RuntimeRefusalError as error:
                if (
                    error.reason is not RuntimeRefusalCode.ENDPOINT_NOT_READY
                    or has_async_cleanup_failure(error)
                    or time.monotonic() >= deadline
                ):
                    task.retain_transport_cleanup(error)
                    raise
                await asyncio.sleep(0.05)
        first_guid, engine_pid = await asyncio.to_thread(
            installed_windows_task_instance, task.binding, task.task_name, identity, observed.pid
        )
        engine = await await_cancellation_complete(
            asyncio.to_thread(retain_windows_task_engine, engine_pid, task.cleanup),
            task_name="recovery-native-handle-capture",
        )
        tree = await await_cancellation_complete(
            asyncio.to_thread(retain_windows_runtime_tree, observed.pid, task.cleanup, require_worker=False),
            task_name="recovery-native-handle-capture",
        )
        first_host = next(process for process in tree if process.pid == observed.pid)
        assert engine.alive() and all(process.alive() for process in tree)
        first_host.terminate()
        await wait_windows_recovery_processes_gone(tree, timeout=17)
        assert engine.alive()
        # This public hello precedes every fresh admission/start request.
        replacement, replacement_boot = await task.observe_replacement_process(
            first_host, first_boot, deadline=time.monotonic() + 90
        )
        assert replacement_boot != first_boot
        replacement_guid, replacement_engine = await asyncio.to_thread(
            installed_windows_task_instance, task.binding, task.task_name, identity, replacement.pid
        )
        assert replacement_guid == first_guid and replacement_engine == engine_pid
        assert engine.alive()
        await task.prepare_physical_cleanup()
        assert task.stop_accepted is not None and task.stop_accepted.runtime_boot_id == replacement_boot
        await asyncio.to_thread(engine.wait, timeout=25)
        await asyncio.to_thread(replacement.wait, timeout=25)
        deadline = time.monotonic() + 7
        while time.monotonic() < deadline:
            assert not engine.alive()
            inspection = await task.manager.inspect()
            assert inspection.binding_matches and inspection.process_state is RuntimeManagerProcessState.STOPPED
            try:
                channel = task.endpoint.connect(timeout=0.1)
            except RuntimeRefusalError as absent:
                assert absent.reason is RuntimeRefusalCode.ENDPOINT_NOT_READY
            else:
                primary = AssertionError("confirmed Stop unexpectedly exposed a new runtime")
                await close_async_resources(
                    RuntimeTransportCleanup(channel), task_name="unexpected-restart-channel", primary_error=primary
                )
                raise primary
            await asyncio.sleep(0.05)
