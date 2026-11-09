"""A status read kept past its request is served to a retry after the real claim path replaced the lease.

The service client, the provider store, the login observation and the kept read
all run for real over a connection that answers each claim with a lease decoded
anew. Only the agent program's output is supplied, since there is no agent
image to start, and its sign-in capability read is where the read waits.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from threading import Event
from time import sleep
from typing import Any
from uuid import UUID, uuid4

import pytest

from cadrumo_client.transport.service_client import InstalledServiceClient

from ... import service_administration as service_module
from ...adapters import agent_provider_catalog
from ...adapters.agent_programs import PACKAGE_AGENT_VARIABLE
from ...adapters.agent_provider_catalog import AgentProviderCatalogSource
from ...providers.application.tests.runtime_connection import RuntimeConnection, service_client, synthetic_lease
from ...providers.application.tests.synthetic_catalog import synthetic_catalog, synthetic_document
from ...providers.domain.record import LocalEngine
from ...service import AgentService

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_WITHIN_SECONDS = 0.05
_SETTLE_SECONDS = 5.0
_BUSY = {"kind": "refused", "code": "busy"}


class _Agent:
    """The agent program's output; its sign-in capability read waits, as a slow provider program would."""

    def __init__(self) -> None:
        self.reached = Event()
        self.release = Event()

    def invoke(self, arguments: tuple[str, ...], **_bounds: Any) -> bytes:
        if arguments == agent_provider_catalog.CATALOG_ARGUMENTS:
            return synthetic_document().encode("utf-8")
        assert arguments == agent_provider_catalog.GUI_AUTH_CAPABILITIES_ARGUMENTS
        self.reached.set()
        assert self.release.wait(_SETTLE_SECONDS)
        return json.dumps({"schema_version": 3, "providers": {"example": ["browser"]}}).encode("utf-8")


class _Rig:
    def __init__(self, service: AgentService, connection: RuntimeConnection, agent: _Agent) -> None:
        self.service = service
        self.connection = connection
        self.agent = agent

    @property
    def client(self) -> InstalledServiceClient:
        return self.service.client

    def status_after_release(self) -> dict[str, Any]:
        self.agent.release.set()
        for _ in range(500):
            answer = self.service.admin("status")
            if answer != _BUSY:
                return answer
            # A retry under a different lease is refused until the first read ends.
            sleep(0.01)
        raise AssertionError("the status read never settled")


@pytest.fixture
def agent(monkeypatch: pytest.MonkeyPatch) -> Iterator[_Agent]:
    agent = _Agent()
    monkeypatch.setattr(AgentProviderCatalogSource, "_invoke", agent.invoke)
    # With no packaged agent image the login observation reads no state, as it would outside a package.
    monkeypatch.delenv(PACKAGE_AGENT_VARIABLE, raising=False)
    monkeypatch.setattr(service_module, "ADMIN_READ_SECONDS", _WITHIN_SECONDS)
    yield agent
    agent.release.set()


def _rig(tmp_path: Path, agent: _Agent, *, claimed_session: list[UUID | None]) -> _Rig:
    connection = RuntimeConnection(synthetic_lease(), claimed_session=lambda: claimed_session[0])
    client = service_client(connection)
    client.claim()
    service = AgentService(
        local_engine_default=LocalEngine.LLAMACPP,
        client=client,
        storage_root=tmp_path,
        gateway_bearer=bytearray(b"synthetic-gateway-bearer"),
        emit=lambda _: None,
    )
    return _Rig(service, connection, agent)


def test_a_status_read_kept_past_its_request_is_served_after_the_real_claim_replaces_the_lease(
    tmp_path: Path, agent: _Agent
) -> None:
    rig = _rig(tmp_path, agent, claimed_session=[None])
    started = rig.client.lease
    claims_before = rig.connection.claims

    assert rig.service.admin("status") == _BUSY
    assert agent.reached.wait(_SETTLE_SECONDS)

    # The login observation made by the read claimed again: an equal lease that is a new object.
    assert rig.connection.claims == claims_before + 1
    assert rig.client.lease is not started
    assert rig.client.lease == started

    answer = rig.status_after_release()

    assert len(answer["providers"]) == len(synthetic_catalog().provider_ids)
    assert rig.connection.record_reads == len(synthetic_catalog().provider_ids), "the work ran once"


def test_a_status_read_kept_under_one_session_is_not_served_after_a_claim_changes_only_the_session(
    tmp_path: Path, agent: _Agent
) -> None:
    claimed_session: list[UUID | None] = [None]
    rig = _rig(tmp_path, agent, claimed_session=claimed_session)
    started = rig.client.lease
    assert started is not None
    claimed_session[0] = uuid4()

    assert rig.service.admin("status") == _BUSY
    assert agent.reached.wait(_SETTLE_SECONDS)

    # Only the session differs between the two leases.
    answer = rig.status_after_release()
    assert rig.client.lease is not None
    assert rig.client.lease.session_id != started.session_id
    assert rig.client.lease.model_copy(update={"session_id": started.session_id}) == started

    assert len(answer["providers"]) == len(synthetic_catalog().provider_ids)
    assert rig.connection.record_reads == 2 * len(synthetic_catalog().provider_ids), "the kept read was not served"
