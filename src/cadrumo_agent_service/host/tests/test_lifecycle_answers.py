"""Retiring the agent's tree is answered at once and reported by the service's events.

An admitted stop retires the running agent and reports a ``stopped`` event.
An unsupported sign-in method is refused before the existing tree or an auth
helper can be started or changed.

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
from cadrumo_client.contracts.deadline_budget import TimeoutDeadline
from cadrumo_client.transport.service_client import InstalledServiceClient

from ...adapters.agent_process import WindowsAgentInvocationRunner, WindowsAgentProcessLauncher
from ...adapters.agent_programs import AGENT_COMMAND_LINE, GATEWAY_ARGUMENTS, PACKAGE_AGENT_VARIABLE
from ...gateway_credentials import GatewayCredentials
from ...providers.application.agent_credentials import ProviderSettingsAgentCredentialSource
from ...providers.application.ports import StoreGenerations
from ...providers.application.resolution import ProviderCredentialResolver
from ...providers.application.service import ProviderSettingsService
from ...providers.application.tests.memory_store import MemoryProviderSettingsStore
from ...service import AgentService
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
    def resolve_for_agent(self, *, deadline: TimeoutDeadline | None = None) -> ResolvedAgentCredentials:
        return ResolvedAgentCredentials(
            _GENERATIONS,
            {},
            gateway_bearer=bytearray(secrets.token_urlsafe(32), "ascii"),
            host_token=bytearray(secrets.token_urlsafe(32), "ascii"),
        )

    def current_generations(self, *, deadline: TimeoutDeadline | None = None) -> AgentGenerations:
        return _GENERATIONS


class _SignedInStore(MemoryProviderSettingsStore):
    """The in-memory settings of a profile whose sign-in and settings are current."""

    @override
    def observe_generations(self, *, deadline: TimeoutDeadline | None = None) -> StoreGenerations | None:
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


def test_unsupported_sign_in_is_refused_before_retirement_or_auth_work(
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
    service._providers = ProviderSettingsService(store=store, catalog_source=service._catalog)
    service._credentials = GatewayCredentials(
        ProviderSettingsAgentCredentialSource(store=store, resolver=resolver, catalog_source=service._catalog),
        bytearray(b"g" * 43),
        bytearray(b"h" * 43),
        service._closing,
    )
    # The running service read both at its start; this test reads them before it times anything.
    assert service._catalog.catalog().entry("claude_cli") is not None
    methods = service._catalog.gui_sign_in_methods()
    assert "claude" in methods
    assert "device" not in methods["claude"]
    controller = _running_tree(checkout, tmp_path / "tree")
    service._controller = controller
    try:
        started = time.monotonic()
        answer = service.admin(
            "connect", provider="claude_cli", expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID, method="device"
        )
        answered = time.monotonic() - started

        assert answer == {"kind": "refused", "code": "sign_in_unavailable"}
        assert answered < ANSWER_BOUND_SECONDS, f"the sign-in took {answered:.3f} s to answer"
        assert service._auth_attempt is None
        assert service._auth_resume_valid is None
        assert service._stop_thread is None
        assert service._controller is controller
        assert controller.state is AgentHostState.READY
        assert events.seen == []
    finally:
        controller.stop()
        service.close()
