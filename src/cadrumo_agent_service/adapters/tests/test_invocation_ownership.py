"""Read-only suppliers retain unconfirmed native scopes until close proves termination."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from types import SimpleNamespace
from typing import cast, override

import pytest

from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.transport.windows_process import WindowsProcessScope

from ...host.store_lifecycle import AgentInvocationResult
from ...providers.application.ports import ProviderCatalogUnavailableError
from .. import agent_provider_auth_status, agent_provider_catalog
from ..agent_process import WindowsAgentInvocationRunner
from ..agent_programs import PACKAGE_AGENT_VARIABLE

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


class _UnconfirmedScope:
    def __init__(self) -> None:
        self.confirmed = False
        self.attempts = 0

    def terminate(self, *, timeout: float) -> None:
        self.attempts += 1
        if self.attempts == 1:
            raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE)
        self.confirmed = True


def _runner(
    scope: _UnconfirmedScope, started: list[WindowsAgentInvocationRunner]
) -> type[WindowsAgentInvocationRunner]:
    class Runner(WindowsAgentInvocationRunner):
        @override
        def run(
            self,
            *,
            executable: Path,
            arguments: Sequence[str],
            directory: Path,
            environment: Mapping[str, str],
            timeout: float,
            output_limit: int,
        ) -> AgentInvocationResult:
            started.append(self)
            self._scope = cast(WindowsProcessScope, scope)
            self.settle()
            raise AssertionError("the first containment proof must fail")

    return Runner


def test_catalogue_retains_the_exact_unconfirmed_scope_and_refuses_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scope = _UnconfirmedScope()
    started: list[WindowsAgentInvocationRunner] = []
    monkeypatch.setattr(agent_provider_catalog, "WindowsAgentInvocationRunner", _runner(scope, started))
    executable = tmp_path / "agent.exe"
    executable.write_bytes(b"")
    source = agent_provider_catalog.AgentProviderCatalogSource(received={PACKAGE_AGENT_VARIABLE: str(executable)})
    for _ in range(2):
        with pytest.raises(ProviderCatalogUnavailableError):
            source.catalog()
    assert len(started) == 1
    assert not started[0].settled
    assert scope.attempts == 1
    source.request_close()
    assert scope.attempts == 1, "the request thread only signals cancellation"
    source.close()
    assert scope.attempts == 2 and scope.confirmed
    assert started[0].settled
    source.close()
    assert scope.attempts == 2


def test_auth_probe_retains_the_exact_unconfirmed_scope_and_refuses_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scope = _UnconfirmedScope()
    started: list[WindowsAgentInvocationRunner] = []
    monkeypatch.setattr(agent_provider_auth_status, "WindowsAgentInvocationRunner", _runner(scope, started))
    monkeypatch.setattr(
        agent_provider_auth_status,
        "agent_image",
        lambda **_arguments: SimpleNamespace(
            executable=tmp_path / "agent.exe",
            directory=tmp_path,
        ),
    )
    monkeypatch.setattr(agent_provider_auth_status, "hosted_python", lambda: tmp_path / "python.exe")
    monkeypatch.setattr(agent_provider_auth_status, "agent_binary_directories", lambda **_arguments: None)
    probe = agent_provider_auth_status.AgentProviderAuthStatusProbe(context=lambda: None)
    assert probe._read(tmp_path) == {}
    assert probe._read(tmp_path) == {}
    assert len(started) == 1
    assert not started[0].settled and scope.attempts == 1
    probe.close()
    assert scope.attempts == 2 and scope.confirmed
    assert started[0].settled
    probe.close()
    assert scope.attempts == 2
