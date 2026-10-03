"""LaunchAgent stop acknowledges retained process exit, with controlled OS ports."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from typing import override

import pytest

from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.application.runtime.management import RuntimeServiceBinding
from cadrumo.core.async_cleanup import async_cleanup_failures

from .. import macos_manager as implementation
from ..macos_manager import MacosJobObservation
from ..macos_process import MacosProcessObservation
from ..manager_commands import ManagerCommandResult, NativeManagerCommand
from ..service_definitions import macos_agent_plist, runtime_service_name

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


class _ObservedExit:
    def __init__(self) -> None:
        self.observation = MacosProcessObservation(123, "501", 1, 123, 1000, 1)
        self.exited = False
        self.closed = 0
        self.close_failure: OSError | None = None

    def close(self) -> None:
        self.closed += 1
        if self.close_failure is not None:
            raise self.close_failure


class _StopPort(implementation._NativeMacosLaunchd):
    def __init__(self) -> None:
        self._binding = RuntimeServiceBinding(
            executable="/Applications/Cadrumo/bin/cadrumo-runtime",
            storage_root="/Users/fixture/Cadrumo",
            storage_identity="a" * 64,
            os_owner_id="501",
            product_version="synthetic-cohort",
        )
        self.payload = macos_agent_plist(self._binding, login_autostart=False)
        self.state = MacosJobObservation(loaded=True, binding_matches=True, login_autostart=False, process_id=123)
        self.watch = _ObservedExit()
        self.target = f"gui/501/{runtime_service_name(self._binding)}"
        self.acknowledged = asyncio.Event()
        self.commands: list[tuple[str, ...]] = []
        self.job_reads = 0
        self.process_reads = 0
        self.replace_before = False
        self.replace_after = False
        self.reuse_pid = False
        self.command_failure = False

    @override
    async def job(self, binding: RuntimeServiceBinding) -> MacosJobObservation:
        assert binding == self._binding
        self.job_reads += 1
        if self.replace_before and self.job_reads == 2:
            return self.state.model_copy(update={"process_id": 124})
        return self.state

    @override
    def definition(self, binding: RuntimeServiceBinding) -> bytes:
        assert binding == self._binding
        return self.payload

    def install(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def retain(observation: MacosProcessObservation) -> _ObservedExit:
            assert observation == self.watch.observation
            return self.watch

        def observe(pid: int, *, expected_owner: str) -> MacosProcessObservation:
            assert pid == 123 and expected_owner == "501"
            self.process_reads += 1
            if self.reuse_pid and self.process_reads > 1:
                return replace(self.watch.observation, started_microseconds=2)
            return self.watch.observation

        async def command(
            kind: NativeManagerCommand, arguments: tuple[str, ...], *, timeout: float = 5
        ) -> ManagerCommandResult:
            assert kind is NativeManagerCommand.LAUNCHCTL and 0 < timeout <= 1
            assert self.watch.closed == 0
            self.commands.append(arguments)
            if not self.command_failure:
                self.state = (
                    self.state.model_copy(update={"process_id": 124})
                    if self.replace_after
                    else MacosJobObservation(loaded=False, binding_matches=False)
                )
            self.acknowledged.set()
            return ManagerCommandResult(1 if self.command_failure else 0, "")

        monkeypatch.setattr(implementation, "MacosProcessWatch", retain)
        monkeypatch.setattr(implementation, "read_macos_process", observe)
        monkeypatch.setattr(implementation, "run_manager_command", command)


@pytest.mark.asyncio
async def test_bootout_acknowledgement_waits_for_retained_process_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    port = _StopPort()
    port.install(monkeypatch)
    task = asyncio.create_task(port.control(("bootout", port.target), timeout=1))
    try:
        await asyncio.wait_for(port.acknowledged.wait(), timeout=1)
        assert not task.done() and port.watch.closed == 0
        port.watch.exited = True
        await task
        assert port.watch.closed == 1
        assert port.commands == [("bootout", port.target)]
        assert port.payload == macos_agent_plist(port._binding, login_autostart=False)
    finally:
        if not task.done():
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["job", "incarnation"])
async def test_substitution_between_retention_and_control_refuses_without_mutation(
    monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    port = _StopPort()
    port.replace_before = change == "job"
    port.reuse_pid = change == "incarnation"
    port.install(monkeypatch)
    with pytest.raises(RuntimeRefusalError) as caught:
        await port.control(("bootout", port.target), timeout=1)
    assert caught.value.reason is (
        RuntimeRefusalCode.VERSION_MISMATCH if change == "job" else RuntimeRefusalCode.PEER_UNTRUSTED
    )
    assert not port.commands and port.watch.closed == 1


@pytest.mark.asyncio
async def test_absent_registration_with_live_process_times_out_and_releases_watch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    port = _StopPort()
    port.install(monkeypatch)
    with pytest.raises(RuntimeRefusalError) as caught:
        await port.control(("bootout", port.target), timeout=0.05)
    assert caught.value.reason is RuntimeRefusalCode.DEADLINE_EXCEEDED
    assert port.acknowledged.is_set() and not port.watch.exited and port.watch.closed == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["control", "replacement"])
async def test_native_failure_or_replacement_job_cannot_acknowledge_stop(
    monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    port = _StopPort()
    port.command_failure = failure == "control"
    port.replace_after = failure == "replacement"
    port.install(monkeypatch)
    with pytest.raises(RuntimeRefusalError) as caught:
        await port.control(("bootout", port.target), timeout=1)
    assert caught.value.reason is RuntimeRefusalCode.UNAVAILABLE
    assert port.commands == [("bootout", port.target)] and port.watch.closed == 1


@pytest.mark.asyncio
async def test_stop_cancellation_releases_watch_and_preserves_cancellation(monkeypatch: pytest.MonkeyPatch) -> None:
    port = _StopPort()
    port.install(monkeypatch)
    task = asyncio.create_task(port.control(("bootout", port.target), timeout=1))
    await asyncio.wait_for(port.acknowledged.wait(), timeout=1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert port.watch.closed == 1 and not port.watch.exited


@pytest.mark.asyncio
async def test_stop_timeout_retains_failed_watch_cleanup_ownership(monkeypatch: pytest.MonkeyPatch) -> None:
    port = _StopPort()
    failure = OSError("watch close outcome uncertain")
    port.watch.close_failure = failure
    port.install(monkeypatch)
    with pytest.raises(RuntimeRefusalError) as caught:
        await port.control(("bootout", port.target), timeout=0.05)
    assert caught.value.reason is RuntimeRefusalCode.DEADLINE_EXCEEDED
    retained = async_cleanup_failures(caught.value)
    assert len(retained) == 1 and retained[0].__cause__ is failure
    assert len(retained[0].resources) == 1 and port.watch.closed == 1
    port.watch.close_failure = None
    await retained[0].retry_cleanup()
