"""A settings change replaces the running agent and says so; lifecycle work never stalls administration.

A real contained tree stands in for the agent, so retiring it is real process
work. The profile's credential source is reduced to a movable generation, and
the service's connection to a lease that names a profile.
"""

from __future__ import annotations

import json
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import pytest

from cadrumo_client.transport.service_client import InstalledServiceClient
from cadrumo_runtime.adapters.tests.process_support import fixture_arguments, fixture_environment, native_python

from ...adapters.agent_process import WindowsAgentProcessLauncher
from ...adapters.agent_programs import PACKAGE_AGENT_VARIABLE
from ...host.launcher_protocol import AgentLauncherRefusal
from ...providers.application.contracts import ProviderSettingsRefusalCode
from ...service import LIFECYCLE_ADMISSION_SECONDS, AgentService, _GatewayCredentials
from ..controller import (
    AgentGenerations,
    AgentHostController,
    AgentHostState,
    AgentLaunch,
    ResolvedAgentCredentials,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_application,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows Job containment"),
]

_FIXTURE = "cadrumo_agent_service.adapters.tests.agent_host_fixture"


class _CredentialSource:
    """The signed-in profile's resolver, reduced to no credentials and a movable generation."""

    def __init__(self) -> None:
        self.generations = AgentGenerations(sign_in="login-1", provider_settings="settings-1")

    def resolve_for_agent(self) -> ResolvedAgentCredentials:
        return ResolvedAgentCredentials(generations=self.generations, credentials={})

    def current_generations(self) -> AgentGenerations | None:
        return self.generations


def _alive(pid: int, *, within: float = 0) -> bool:
    import pywintypes
    import win32api
    import win32event

    try:
        handle = win32api.OpenProcess(0x100000, False, pid)
    except pywintypes.error:
        return False
    try:
        return win32event.WaitForSingleObject(handle, int(within * 1000)) == win32event.WAIT_TIMEOUT
    finally:
        win32api.CloseHandle(handle)


def _running_service(
    tmp_path: Path, source: _CredentialSource, *, mode: str = "ready", wake: Callable[[], None] | None = None
) -> tuple[AgentService, list[dict[str, Any]], int]:
    events: list[dict[str, Any]] = []
    service = AgentService(
        client=cast(InstalledServiceClient, SimpleNamespace(lease=SimpleNamespace(profile_id=uuid4()))),
        storage_root=tmp_path,
        gateway_bearer=bytearray(b"synthetic-gateway-bearer"),
        emit=events.append,
        wake=wake,
    )
    service._credentials = _GatewayCredentials(
        source, bytearray(b"synthetic-gateway-bearer"), bytearray(b"synthetic-host-token"), service._closing
    )
    record = tmp_path / "tree"
    record.mkdir()
    controller = AgentHostController(
        launcher=WindowsAgentProcessLauncher(on_exit=wake),
        credentials=service._credentials,
        launch=AgentLaunch(
            executable=native_python(),
            arguments=fixture_arguments(_FIXTURE, mode, str(record)),
            directory=record,
            environment=fixture_environment(),
            ready_timeout=30,
            stop_grace=10,
        ),
    )
    controller.start()
    service._controller = controller
    grandchild = json.loads((record / "received.json").read_text(encoding="utf-8"))["grandchild"]
    assert isinstance(grandchild, int) and _alive(grandchild)
    return service, events, grandchild


def test_an_exited_agent_is_not_published_and_its_descendants_are_retired(tmp_path: Path) -> None:
    woke = threading.Event()
    service, events, grandchild = _running_service(tmp_path, _CredentialSource(), mode="crash", wake=woke.set)
    controller = service._controller
    assert controller is not None
    record = tmp_path / "tree"
    process_id = json.loads((record / "received.json").read_text(encoding="utf-8"))["pid"]
    try:
        assert not woke.is_set()
        (record / "crash").touch()
        assert woke.wait(10), "native process exit must wake the otherwise idle service"
        assert not _alive(process_id, within=10)
        assert _alive(grandchild), "only the gateway exited; the owner must still clean up its tree"
        assert controller.published() is None
        assert service.observe() is False
        service.stop()
        assert not _alive(grandchild, within=5)
        assert events == [{"event": "stopped", "code": "agent_retired"}]
    finally:
        service.stop()
        service._ownership.close()


def test_a_settings_change_retires_the_running_agent_and_publishes_why_its_replacement_did_not_start(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The service runs outside a package here, so the replacement cannot find an agent image.
    monkeypatch.delenv(PACKAGE_AGENT_VARIABLE, raising=False)
    source = _CredentialSource()
    service, events, grandchild = _running_service(tmp_path, source)
    try:
        assert service.observe() is True
        assert events == []

        source.generations = AgentGenerations(sign_in="login-1", provider_settings="settings-2")
        assert service.observe() is True
        thread = service._start_thread
        assert thread is not None
        thread.join(60)
        assert not thread.is_alive()

        assert events == [
            {"event": "stopped", "code": "agent_retired"},
            {"event": "refused", "code": AgentLauncherRefusal.SERVICE_ABSENT.value},
        ]
        assert service._controller is None
        assert not _alive(grandchild, within=5)
    finally:
        controller = service._controller
        if controller is not None:
            controller.stop()
        service._ownership.close()


def test_administration_answers_busy_while_lifecycle_work_holds_the_tree_instead_of_waiting_for_its_deadline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Outside a package the catalogue cannot find an agent image, so a provider
    # change that is admitted answers why it could not read the provider's lane.
    monkeypatch.delenv(PACKAGE_AGENT_VARIABLE, raising=False)
    source = _CredentialSource()
    service, events, grandchild = _running_service(tmp_path, source)
    controller = service._controller
    assert controller is not None
    held = threading.Event()
    release = threading.Event()

    def lifecycle_work() -> None:
        # Another thread's lifecycle work, such as a retirement waiting on its tree, holds the lock.
        with service._guard:
            held.set()
            release.wait(30)

    holder = threading.Thread(target=lifecycle_work, name="test-lifecycle-work")
    holder.start()
    try:
        assert held.wait(10)
        # Each of these changes the tree or its settings, so each is admitted only
        # under the lifecycle lock; stop is answered without it and is covered
        # by its own exchange tests.
        for action in ("remove", "turn_on", "sign_in"):
            started = time.monotonic()
            answer = service.admin(action, provider="example", expected_revision="0" * 64)
            elapsed = time.monotonic() - started
            assert answer == {"kind": "refused", "code": "busy"}
            assert LIFECYCLE_ADMISSION_SECONDS <= elapsed < LIFECYCLE_ADMISSION_SECONDS + 1
        assert controller.state is AgentHostState.READY
        assert events == []
        release.set()
        holder.join(30)
        assert not holder.is_alive()

        # Once the lock is free the same request is admitted and answered on its merits.
        started = time.monotonic()
        answer = service.admin("remove", provider="example", expected_revision="0" * 64)
        assert time.monotonic() - started < LIFECYCLE_ADMISSION_SECONDS
        assert answer == {"code": ProviderSettingsRefusalCode.CATALOG_UNAVAILABLE.value}
        assert controller.state is AgentHostState.READY
        assert service._controller is controller
        assert events == []
        assert _alive(grandchild)
    finally:
        release.set()
        holder.join(30)
        controller.stop()
        service._ownership.close()
    assert not _alive(grandchild, within=5)
