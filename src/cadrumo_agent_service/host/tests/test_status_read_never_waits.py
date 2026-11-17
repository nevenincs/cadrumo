"""The provider status answers within its bound while a provider program or the sign-in capability read is slow.

The service's administration, the settings service, the lane projection, the
login observation and the catalog source all run for real. Only the agent
program is supplied, at the two seams where the service runs it: the invocation
runner of the login observation and the catalog source's invocation.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Iterator
from pathlib import Path
from threading import Event, Thread
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import pytest

from cadrumo.tests.log_records import delivered_records
from cadrumo_client.transport.service_client import InstalledServiceClient

from ...adapters import agent_provider_auth_status as status_module
from ...adapters import agent_provider_catalog
from ...adapters.agent_programs import AgentImage, provider_login_notice
from ...adapters.agent_provider_catalog import AgentProviderCatalogSource
from ...providers.application.ports import ProviderCatalogUnavailableError, ProviderCatalogUnavailableReason
from ...providers.application.service import ProviderSettingsService
from ...providers.application.tests.memory_store import MemoryProviderSettingsStore
from ...providers.application.tests.synthetic_catalog import SIGN_IN_ONLY_LANE, StaticCatalogSource, synthetic_document
from ...providers.domain.record import LocalEngine
from ...service import AgentService
from ..store_lifecycle import AgentInvocationResult

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROMPT_SECONDS = 1.0
"""Well inside the status bound, and far from a provider program's own."""
_SETTLE_SECONDS = 10.0
_BUSY = {"kind": "refused", "code": "busy"}
_STATUS_LOGGER = "cadrumo_agent_service.service_provider_status"


class _Agent:
    """The agent program: its login read and its sign-in capability read each wait until released."""

    status_release = Event()
    status_reached = Event()
    capabilities_release = Event()
    capabilities_fail = False
    status_reads = 0
    cli_state = "installed_signed_in"

    def __init__(self, **_ignored: Any) -> None:
        self.settled = True

    def run(self, *, arguments: tuple[str, ...], **_ignored: Any) -> AgentInvocationResult:
        assert arguments[-4:] == ("auth", "status", "--json", "--causes")
        type(self).status_reads += 1
        type(self).status_reached.set()
        assert type(self).status_release.wait(_SETTLE_SECONDS)
        body = {"schema_version": 2, "providers": {"example": self.cli_state}, "causes": {"example": None}}
        return AgentInvocationResult(status=0, standard_output=json.dumps(body).encode())

    @staticmethod
    def invoke(_source: object, arguments: tuple[str, ...], **_bounds: Any) -> bytes:
        if arguments == agent_provider_catalog.CATALOG_ARGUMENTS:
            return synthetic_document().encode("utf-8")
        assert arguments == agent_provider_catalog.GUI_AUTH_CAPABILITIES_ARGUMENTS
        assert _Agent.capabilities_release.wait(_SETTLE_SECONDS)
        if _Agent.capabilities_fail:
            raise ProviderCatalogUnavailableError(ProviderCatalogUnavailableReason.AGENT_FAILED)
        return json.dumps({"schema_version": 3, "providers": {"example": ["browser"]}}).encode("utf-8")


@pytest.fixture
def agent(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[type[_Agent]]:
    _Agent.status_release, _Agent.status_reached, _Agent.capabilities_release = Event(), Event(), Event()
    _Agent.status_reads = 0
    _Agent.capabilities_fail = False
    monkeypatch.setattr(status_module, "WindowsAgentInvocationRunner", _Agent)
    monkeypatch.setattr(status_module, "agent_image", lambda **_k: AgentImage(tmp_path / "agent.exe", (), tmp_path))
    monkeypatch.setattr(status_module, "hosted_python", lambda: None)
    monkeypatch.setattr(AgentProviderCatalogSource, "_invoke", _Agent.invoke)
    yield _Agent
    _Agent.status_release.set()
    _Agent.capabilities_release.set()


def _service(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AgentService:
    lease = SimpleNamespace(lease_id=uuid4(), profile_id=uuid4())
    service = AgentService(
        local_engine_default=LocalEngine.LLAMACPP,
        client=cast(
            InstalledServiceClient, SimpleNamespace(lease=lease, connection=SimpleNamespace(close=lambda: None))
        ),
        storage_root=tmp_path,
        gateway_bearer=bytearray(b"synthetic-gateway-bearer"),
        emit=lambda _event: None,
    )
    monkeypatch.setattr(
        service._credentials, "current_generations", lambda **_k: SimpleNamespace(sign_in=1, provider_settings=1)
    )
    # The profile's store is in memory; the lane observation is the one the service wired.
    service._providers = ProviderSettingsService(
        store=MemoryProviderSettingsStore(),
        catalog_source=StaticCatalogSource(),
        selected_engine=lambda: LocalEngine.LLAMACPP,
        cli_state_probe=service._providers._cli_state_probe,
    )
    return service


def _prompt_status(service: AgentService) -> dict[str, Any]:
    started = time.monotonic()
    answer = service.admin("status")
    elapsed = time.monotonic() - started
    assert answer != _BUSY, f"status answered busy after {elapsed:.2f}s"
    assert elapsed < _PROMPT_SECONDS, f"status took {elapsed:.2f}s"
    return answer


def _lane(answer: dict[str, Any]) -> dict[str, Any]:
    return next(lane for lane in answer["providers"] if lane["id"] == SIGN_IN_ONLY_LANE)


def _status_until(service: AgentService, settled: Any) -> dict[str, Any]:
    deadline = time.monotonic() + _SETTLE_SECONDS
    while time.monotonic() < deadline:
        answer = _prompt_status(service)
        if settled(answer):
            return answer
        time.sleep(0.02)
    raise AssertionError("the background read never landed in the status")


def test_status_answers_at_once_with_a_cli_lane_unread_while_its_program_outlives_the_bound(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, agent: type[_Agent]
) -> None:
    agent.capabilities_release.set()
    service = _service(tmp_path, monkeypatch)

    first = _prompt_status(service)

    assert (_lane(first)["cli_state"], _lane(first)["cli_state_cause"]) == ("unknown", None)
    assert agent.status_reached.wait(_SETTLE_SECONDS), "the status read started the login read in the background"
    assert _lane(_prompt_status(service))["cli_state"] == "unknown"

    agent.status_release.set()
    landed = _status_until(service, lambda answer: _lane(answer)["cli_state"] == "installed_signed_in")

    assert _lane(landed)["cli_state_cause"] is None
    assert agent.status_reads == 1, "status reads made while one login read ran started no other"


def test_console_login_invalidates_a_fresh_signed_out_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, agent: type[_Agent]
) -> None:
    monkeypatch.setattr(agent, "cli_state", "installed_signed_out")
    agent.capabilities_release.set()
    agent.status_release.set()
    service = _service(tmp_path, monkeypatch)
    first = _status_until(service, lambda answer: not answer["reads_pending"])
    assert _lane(first)["cli_state"] == "installed_signed_out"

    context = service._login_context()
    assert context is not None
    notice = provider_login_notice(context[0])
    notice.parent.mkdir()
    agent.status_release.clear()
    monkeypatch.setattr(agent, "cli_state", "installed_signed_in")
    notice.touch()
    try:
        fresh = _prompt_status(service)
        assert fresh["reads_pending"] and _lane(fresh)["cli_state"] == "unknown"
    finally:
        agent.status_release.set()
    settled = _status_until(service, lambda answer: not answer["reads_pending"])
    assert _lane(settled)["cli_state"] == "installed_signed_in"


def test_repeated_runtime_pushes_during_a_slow_login_read_still_let_status_answer_and_the_read_land(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, agent: type[_Agent]
) -> None:
    agent.capabilities_release.set()
    service = _service(tmp_path, monkeypatch)
    _prompt_status(service)
    assert agent.status_reached.wait(_SETTLE_SECONDS)

    for _ in range(5):
        service.runtime_changed()
        assert _lane(_prompt_status(service))["cli_state"] == "unknown"

    agent.status_release.set()
    _status_until(service, lambda answer: _lane(answer)["cli_state"] == "installed_signed_in")
    for _ in range(3):
        service.runtime_changed()
        assert _lane(_prompt_status(service))["cli_state"] == "installed_signed_in"


def test_status_answers_at_once_while_the_sign_in_capability_read_is_slow_and_lists_its_methods_once_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, agent: type[_Agent]
) -> None:
    agent.status_release.set()
    service = _service(tmp_path, monkeypatch)

    first = _prompt_status(service)

    assert (first["sign_in_providers"], first["sign_in_methods"]) == ([], {})

    agent.capabilities_release.set()
    landed = _status_until(service, lambda answer: answer["sign_in_providers"] != [])

    assert landed["sign_in_methods"] == {"example": ["browser"]}


def test_status_says_its_reads_are_pending_until_the_methods_and_the_login_reading_land(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, agent: type[_Agent]
) -> None:
    service = _service(tmp_path, monkeypatch)

    first = _prompt_status(service)

    assert (first["sign_in_providers"], first["sign_in_methods"], first["reads_pending"]) == ([], {}, True)

    agent.capabilities_release.set()
    with_methods = _status_until(service, lambda answer: answer["sign_in_providers"] != [])
    assert with_methods["sign_in_methods"] == {"example": ["browser"]}
    assert with_methods["reads_pending"] is True, "the login reading has not landed yet"

    agent.status_release.set()
    settled = _status_until(service, lambda answer: answer["reads_pending"] is False)

    assert settled["sign_in_methods"] == {"example": ["browser"]}
    assert _lane(settled)["cli_state"] == "installed_signed_in"


def test_a_failed_method_read_settles_the_pending_reads_and_logs_only_its_reason(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, agent: type[_Agent], caplog: pytest.LogCaptureFixture
) -> None:
    agent.status_release.set()
    agent.capabilities_fail = True
    service = _service(tmp_path, monkeypatch)

    with caplog.at_level(logging.WARNING, logger=_STATUS_LOGGER):
        assert _prompt_status(service)["reads_pending"] is True
        agent.capabilities_release.set()
        settled = _status_until(service, lambda answer: answer["reads_pending"] is False)
        messages = [record.getMessage() for record in delivered_records(caplog, _STATUS_LOGGER)]

    assert (settled["sign_in_providers"], settled["sign_in_methods"]) == ([], {})
    assert any("reason=agent_failed" in message for message in messages), messages


def test_status_answers_the_lanes_while_the_agent_starts_and_keeps_its_reads_pending_until_the_start_ends(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, agent: type[_Agent]
) -> None:
    agent.status_release.set()
    agent.capabilities_release.set()
    service = _service(tmp_path, monkeypatch)
    start_ends = Event()
    service._start_thread = Thread(target=start_ends.wait, args=(_SETTLE_SECONDS,), name="synthetic-agent-start")
    service._start_thread.start()
    try:
        first = _prompt_status(service)
        assert first["providers"], "the lanes are the store's, read while the agent starts"
        assert first["reads_pending"] is True

        # Both reads land while the agent still starts.
        _status_until(service, lambda answer: answer["sign_in_providers"] != [])
        read = _status_until(service, lambda answer: _lane(answer)["cli_state"] == "installed_signed_in")
        assert read["reads_pending"] is True, "the agent is still starting"
        assert service.admin("provider_lanes")["reads_pending"] is True
    finally:
        start_ends.set()
        service._start_thread.join(_SETTLE_SECONDS)

    assert _status_until(service, lambda answer: answer["reads_pending"] is False)["sign_in_methods"] == {
        "example": ["browser"]
    }
    assert service.admin("provider_lanes")["reads_pending"] is False
