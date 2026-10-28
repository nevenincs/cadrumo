"""Retiring the agent's tree is answered at once and reported by the service's events.

A stop, and a browser or device sign-in, retire the running agent: its gateway
settles its run, ends its worker and exits, and the service confirms the whole
job is gone. That takes longer than an administration exchange may wait, so the
request is answered as soon as the work is admitted, and the end is the
``stopped`` event the desktop already reads.

The tree here is a real hosted cadrumo-agent gateway with its worker, run from
the checkout ``CADRUMO_DEV_AGENT_CHECKOUT`` names, inside the service's own
kill-on-close job. The sign-in helper is that checkout's real ``auth connect``,
which the service reaches through its package agent variable as it would the
bundled image.
What the runtime would supply - the profile's lease and its encrypted provider
settings - is the in-memory store the service's own tests use.
"""

from __future__ import annotations

import os
import secrets
import time
from pathlib import Path
from threading import Lock
from types import SimpleNamespace
from typing import Any, Final, cast, override
from uuid import uuid4

import pytest

from cadrumo.core.secure_object_write import ABSENT_SECURE_OBJECT_REVISION_ID
from cadrumo.core.storage_environment import storage_mode
from cadrumo_client.transport.service_client import InstalledServiceClient

from ...adapters.agent_process import WindowsAgentInvocationRunner, WindowsAgentProcessLauncher
from ...adapters.agent_programs import AGENT_COMMAND_LINE, GATEWAY_ARGUMENTS, PACKAGE_AGENT_VARIABLE
from ...providers.application.agent_credentials import ProviderSettingsAgentCredentialSource
from ...providers.application.ports import StoreGenerations
from ...providers.application.resolution import ProviderCredentialResolver
from ...providers.application.service import ProviderSettingsService
from ...providers.application.tests.memory_store import MemoryProviderSettingsStore
from ...service import AgentService, _GatewayCredentials
from ..controller import (
    AgentGenerations,
    AgentHostController,
    AgentHostState,
    AgentLaunch,
    ResolvedAgentCredentials,
)
from ..launch_environment import (
    GATEWAY_PORT_VARIABLE,
    HOSTED_ROOT_VARIABLE,
    WORKER_PORT_VARIABLE,
    system_environment,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.external_tool,
    pytest.mark.windows_only,
    pytest.mark.hex_application,
]

CHECKOUT_VARIABLE: Final = "CADRUMO_DEV_AGENT_CHECKOUT"
ANSWER_BOUND_SECONDS: Final = 0.5
"""Well inside the desktop's shortest administration bound."""
_GENERATIONS: Final = AgentGenerations("synthetic-session", "synthetic-settings")


def _checkout() -> Path:
    named = os.environ.get(CHECKOUT_VARIABLE)
    if named is None or not named.strip():
        pytest.fail(f"{CHECKOUT_VARIABLE} must name a synced cadrumo-agent checkout", pytrace=False)
    checkout = Path(named)
    if not (checkout / ".venv" / "Scripts" / "python.exe").is_file():
        pytest.fail(f"{CHECKOUT_VARIABLE} names no synced cadrumo-agent checkout", pytrace=False)
    return checkout


def _interpreter(checkout: Path) -> Path:
    return checkout / ".venv" / "Scripts" / "python.exe"


class _FixedCredentials:
    def resolve_for_agent(self) -> ResolvedAgentCredentials:
        return ResolvedAgentCredentials(
            _GENERATIONS,
            {},
            gateway_bearer=bytearray(secrets.token_urlsafe(32), "ascii"),
            host_token=bytearray(secrets.token_urlsafe(32), "ascii"),
        )

    def current_generations(self) -> AgentGenerations:
        return _GENERATIONS


class _SignedInStore(MemoryProviderSettingsStore):
    """The in-memory settings of a profile whose sign-in and settings are current."""

    @override
    def observe_generations(self) -> StoreGenerations | None:
        return StoreGenerations(sign_in="a" * 64, provider_settings="b" * 64)


class _Events:
    def __init__(self) -> None:
        self._lock = Lock()
        self.seen: list[dict[str, Any]] = []

    def __call__(self, event: dict[str, Any]) -> None:
        with self._lock:
            self.seen.append(event)

    def wait_for(self, name: str, *, timeout: float) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self._lock:
                for event in self.seen:
                    if event.get("event") == name:
                        return event
            time.sleep(0.02)
        raise AssertionError(f"no {name} event within {timeout} s; saw {self.seen}")


def _running_tree(checkout: Path, root: Path) -> AgentHostController:
    """Start a real hosted gateway, with its worker, as the service starts one."""
    root.mkdir(parents=True)
    environment = system_environment(os.environ) | {HOSTED_ROOT_VARIABLE: str(root)}
    setup = WindowsAgentInvocationRunner().run(
        executable=_interpreter(checkout),
        arguments=(*AGENT_COMMAND_LINE, "setup"),
        directory=root,
        environment=environment,
        timeout=120,
        output_limit=64 * 1024,
    )
    assert setup.status == 0, setup.standard_output[-2000:]
    controller = AgentHostController(
        launcher=WindowsAgentProcessLauncher(),
        credentials=_FixedCredentials(),
        launch=AgentLaunch(
            executable=_interpreter(checkout),
            arguments=GATEWAY_ARGUMENTS,
            directory=root,
            environment=environment | {GATEWAY_PORT_VARIABLE: "0", WORKER_PORT_VARIABLE: "0"},
        ),
    )
    controller.start()
    # Let the gateway's worker start, so the retirement ends a whole tree.
    time.sleep(3)
    return controller


def _service(storage_root: Path, events: _Events) -> AgentService:
    client = SimpleNamespace(
        lease=SimpleNamespace(profile_id=uuid4(), lease_id=uuid4()), connection=SimpleNamespace(close=lambda: None)
    )
    return AgentService(
        client=cast(InstalledServiceClient, client),
        storage_root=storage_root,
        gateway_bearer=bytearray(secrets.token_urlsafe(32), "ascii"),
        emit=events,
    )


def test_a_stop_is_answered_at_once_and_its_end_follows_as_the_stopped_event(tmp_path: Path) -> None:
    checkout = _checkout()
    events = _Events()
    service = _service(tmp_path / "storage", events)
    controller = _running_tree(checkout, tmp_path / "tree")
    service._controller = controller
    try:
        started = time.monotonic()
        answer = service.admin("stop")
        answered = time.monotonic() - started
        # A second retirement while the first is under way is told the service is busy.
        second = service.admin("stop")

        assert answer == {"kind": "accepted"}
        assert answered < ANSWER_BOUND_SECONDS, f"the stop took {answered:.3f} s to answer"
        assert second == {"kind": "refused", "code": "busy"}
        assert events.wait_for("stopped", timeout=30) == {"event": "stopped", "code": "agent_retired"}
        assert controller.state is AgentHostState.DETACHED
        assert service._controller is None
        assert service.admin("stop") == {"kind": "stopped"}
    finally:
        controller.stop()
        service.close()


def test_a_sign_in_is_answered_starting_while_the_tree_retires_and_its_helper_then_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    checkout = _checkout()
    monkeypatch.setenv(PACKAGE_AGENT_VARIABLE, str(_interpreter(checkout)))
    storage_root = tmp_path / "storage"
    storage_root.mkdir()
    events = _Events()
    service = _service(storage_root, events)
    store = _SignedInStore()
    resolver = ProviderCredentialResolver(store=store, catalog_source=service._catalog)
    service._providers = ProviderSettingsService(
        store=store, catalog_source=service._catalog, storage_mode=storage_mode().mode
    )
    service._credentials = _GatewayCredentials(
        ProviderSettingsAgentCredentialSource(store=store, resolver=resolver, catalog_source=service._catalog),
        bytearray(b"g" * 43),
        bytearray(b"h" * 43),
        service._closing,
    )
    # The running service read both at its start; this test reads them before it times anything.
    assert service._catalog.catalog().entry("claude_cli") is not None
    assert "claude" in service._catalog.gui_sign_in_providers()
    controller = _running_tree(checkout, tmp_path / "tree")
    service._controller = controller
    try:
        started = time.monotonic()
        answer = service.admin(
            "connect", provider="claude_cli", expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID, method="device"
        )
        answered = time.monotonic() - started

        assert answer.get("event") == "starting", answer
        assert answered < ANSWER_BOUND_SECONDS, f"the sign-in took {answered:.3f} s to answer"
        # Anything else that would change the tree waits for the attempt.
        assert service.admin("start") == {"kind": "refused", "code": "busy"}
        assert events.wait_for("stopped", timeout=30) == {"event": "stopped", "code": "agent_retired"}
        assert controller.state is AgentHostState.DETACHED

        # The helper starts once the tree is gone; this lane offers no device sign-in.
        deadline = time.monotonic() + 60
        snapshot = answer
        while snapshot["event"] in {"starting", "started"} and time.monotonic() < deadline:
            time.sleep(0.1)
            snapshot = service.admin("connect_status", attempt_id=answer["attempt_id"])
        assert snapshot == {
            "attempt_id": answer["attempt_id"],
            "provider": "claude_cli",
            "event": "failed",
            "reason": "unsupported_flow",
        }
    finally:
        controller.stop()
        service.close()
