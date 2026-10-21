"""The agent picker's catalog omits the lanes the signed-in profile turned off."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from pydantic import SecretStr

from cadrumo.core.secure_object_write import ABSENT_SECURE_OBJECT_REVISION_ID
from cadrumo.core.storage_environment import StorageMode
from cadrumo_client.transport.service_client import InstalledServiceClient

from ... import service as service_module
from ...providers.application.contracts import ProviderSettingsActionAccepted
from ...providers.application.ports import StoreRefusal, StoreRefusalCode
from ...providers.application.service import ProviderSettingsService
from ...providers.application.tests.memory_store import MemoryProviderSettingsStore
from ...providers.application.tests.synthetic_catalog import KEY_LANE, StaticCatalogSource
from ...service import AgentService
from ..controller import AgentGenerations, AgentHostController, AgentHostState, AgentReady

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _lane(provider: str, transport: str) -> dict[str, Any]:
    return {
        "provider_id": provider,
        "transport": transport,
        "execution_mode": f"{provider}-{transport}",
        "hosted_certification": "proven",
    }


def _document() -> dict[str, Any]:
    return {
        "api_version": "v1",
        "providers": [_lane("example", "api"), _lane("example", "cli"), _lane("other", "api")],
    }


class _Controller:
    def __init__(self, ready: AgentReady) -> None:
        self.ready = ready
        self.state = AgentHostState.READY

    def published(self) -> AgentReady:
        return self.ready


def _service(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, store: MemoryProviderSettingsStore) -> AgentService:
    service = AgentService(
        client=cast(InstalledServiceClient, SimpleNamespace(lease=object())),
        storage_root=tmp_path,
        gateway_bearer=bytearray(b"synthetic-gateway-bearer"),
        emit=lambda _event: None,
    )
    service._providers = ProviderSettingsService(
        store=store,
        catalog_source=StaticCatalogSource(),
        environment={},
        storage_mode=StorageMode.INSTALLED,
    )
    monkeypatch.setattr(service_module, "declared_provider_catalog_response", _document)
    return service


def _turn_off_key_lane(service: AgentService) -> None:
    stored = service._providers.set_credential(
        KEY_LANE, secret=SecretStr("synthetic-profile-key"), expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID
    )
    assert isinstance(stored, ProviderSettingsActionAccepted)
    off = service._providers.turn_off(KEY_LANE, expected_revision=stored.entry.revision)
    assert isinstance(off, ProviderSettingsActionAccepted)


def _identities(document: dict[str, Any]) -> list[tuple[str, str]]:
    return [(lane["provider_id"], lane["transport"]) for lane in document["providers"]]


def test_a_turned_off_lane_is_dropped_by_its_exact_provider_and_transport(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = _service(tmp_path, monkeypatch, MemoryProviderSettingsStore())
    assert _identities(service.admin("catalog")) == [("example", "api"), ("example", "cli"), ("other", "api")]

    _turn_off_key_lane(service)

    catalog = service.admin("catalog")
    assert catalog["api_version"] == "v1"
    assert _identities(catalog) == [("example", "cli"), ("other", "api")]


def test_without_a_lease_or_readable_settings_the_catalog_is_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = MemoryProviderSettingsStore()
    service = _service(tmp_path, monkeypatch, store)
    _turn_off_key_lane(service)
    every_lane = [("example", "api"), ("example", "cli"), ("other", "api")]

    service.client.lease = None
    assert _identities(service.admin("catalog")) == every_lane

    service.client.lease = cast(Any, object())
    store.refusal = StoreRefusal(code=StoreRefusalCode.PROFILE_LOCKED)
    assert _identities(service.admin("catalog")) == every_lane


def test_a_served_catalog_is_filtered_but_hosted_certification_keeps_every_lane(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = _service(tmp_path, monkeypatch, MemoryProviderSettingsStore())
    _turn_off_key_lane(service)
    ready = AgentReady(
        generations=AgentGenerations("synthetic-session", "synthetic-settings"),
        gateway_port=12345,
        agent_version="synthetic-agent",
        hosting_contract=1,
    )
    service._controller = cast(AgentHostController, _Controller(ready))
    monkeypatch.setattr(service, "_served_catalog", lambda _ready: _document())

    catalog = service.admin("catalog")

    assert _identities(catalog) == [("example", "cli"), ("other", "api")]
    certified = [(item["provider"], item["transport"]) for item in service._hosted_certifications()]
    assert certified == [("example", "api"), ("example", "cli"), ("other", "api")]
