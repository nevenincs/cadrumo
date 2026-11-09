"""A catalog or status read that outlives its request is served to the next request, even though it refreshed the lease."""

from __future__ import annotations

from pathlib import Path
from threading import Event
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

import pytest

from cadrumo_client.contracts.service_access import ServiceLease
from cadrumo_client.transport.service_client import InstalledServiceClient

from ... import service_administration as service_module
from ...providers.domain.record import LocalEngine
from ...service import AgentService

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_WITHIN_SECONDS = 0.05
_SETTLE_SECONDS = 5.0

# Each kept read is named by its admin action and runs the service method that reads it.
_READS = {
    "catalog": ("_catalog_document", {"kind": "served", "catalog": {"providers": []}}),
    "status": ("_provider_status", {"kind": "served", "providers": [], "hosted_certifications": []}),
}


def _lease(lease_id: UUID) -> ServiceLease:
    return ServiceLease(
        lease_id=lease_id,
        session_id=UUID(int=2),
        profile_id=UUID(int=3),
        parent_session_id=UUID(int=4),
        descriptor_digest="2" * 64,
        service_id="cadrumo-agent-service",
        runtime_boot_id=UUID(int=5),
        connection_id=UUID(int=6),
    )


class _SlowRead:
    """Stands in for the read's work: it refreshes the lease, as the store's claim does, then outlives its request."""

    def __init__(self, service: AgentService, refreshed: ServiceLease, document: dict[str, Any]) -> None:
        self.service = service
        self.refreshed = refreshed
        self.document = document
        self.release = Event()
        self.finished = Event()
        self.calls = 0

    def __call__(self) -> dict[str, Any]:
        self.calls += 1
        self.service.client.lease = self.refreshed
        assert self.release.wait(_SETTLE_SECONDS)
        self.finished.set()
        return self.document


def _service(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, action: str, lease: ServiceLease, refreshed: ServiceLease
) -> tuple[AgentService, _SlowRead]:
    method, document = _READS[action]
    holder: dict[str, _SlowRead] = {}
    monkeypatch.setattr(AgentService, method, lambda _self: holder["work"]())
    monkeypatch.setattr(service_module, "ADMIN_READ_SECONDS", _WITHIN_SECONDS)
    service = AgentService(
        local_engine_default=LocalEngine.LLAMACPP,
        client=cast(
            InstalledServiceClient, SimpleNamespace(lease=lease, connection=SimpleNamespace(close=lambda: None))
        ),
        storage_root=tmp_path,
        gateway_bearer=bytearray(b"synthetic-gateway-bearer"),
        emit=lambda _event: None,
    )
    holder["work"] = _SlowRead(service, refreshed, document)
    return service, holder["work"]


@pytest.mark.parametrize("action", _READS)
def test_a_read_kept_past_its_request_is_served_after_the_lease_is_refreshed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, action: str
) -> None:
    lease_id = uuid4()
    service, work = _service(tmp_path, monkeypatch, action, _lease(lease_id), _lease(lease_id))

    assert service.admin(action) == {"kind": "refused", "code": "busy"}
    work.release.set()
    assert work.finished.wait(_SETTLE_SECONDS)

    # The refreshed lease is a new object equal to the one the read started under.
    assert service.client.lease is work.refreshed
    for _ in range(100):
        answer = service.admin(action)
        if answer != {"kind": "refused", "code": "busy"}:
            break
    assert answer == work.document
    assert work.calls == 1


@pytest.mark.parametrize("action", _READS)
def test_a_read_kept_under_one_lease_is_not_served_under_a_newly_issued_lease(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, action: str
) -> None:
    service, work = _service(tmp_path, monkeypatch, action, _lease(uuid4()), _lease(uuid4()))

    assert service.admin(action) == {"kind": "refused", "code": "busy"}
    work.release.set()
    assert work.finished.wait(_SETTLE_SECONDS)

    work.release.clear()
    work.finished.clear()
    assert service.admin(action) == {"kind": "refused", "code": "busy"}
    assert work.calls == 2
    work.release.set()
    assert work.finished.wait(_SETTLE_SECONDS)
