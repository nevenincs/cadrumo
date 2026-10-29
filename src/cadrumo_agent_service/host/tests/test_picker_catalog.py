"""The agent picker's catalog omits the lanes the signed-in profile turned off, served or declared."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from pydantic import SecretStr

from cadrumo.core.secure_object_write import ABSENT_SECURE_OBJECT_REVISION_ID
from cadrumo.core.storage_environment import StorageMode
from cadrumo_client.transport.service_client import InstalledServiceClient

from ... import service_administration as service_module
from ...adapters.provider_catalog_metadata import declared_catalog_envelope
from ...providers.application.contracts import ProviderSettingsActionAccepted
from ...providers.application.ports import (
    ProviderCatalogUnavailableError,
    ProviderCatalogUnavailableReason,
    StoreRefusal,
    StoreRefusalCode,
)
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


def _declared_lane(provider: str, transport: str) -> dict[str, Any]:
    """A lane as cadrumo-agent's declared document states it: its identity is ``provider``, not ``provider_id``."""
    return {
        "id": f"{provider}_{transport}",
        "provider": provider,
        "transport": transport,
        "display_name": f"Synthetic {provider}",
        "models": [{"id": "synthetic-text:1", "display_name": "Synthetic text", "vision": None}],
        "recommended": {},
    }


def _declared() -> dict[str, Any]:
    """The fallback the service serves while no agent is ready: the declared document in its envelope."""
    return declared_catalog_envelope(
        {
            "schema_version": 5,
            "providers": [
                _declared_lane("example", "api"),
                _declared_lane("example", "cli"),
                _declared_lane("other", "api"),
            ],
        }
    )


class _Controller:
    def __init__(self, ready: AgentReady) -> None:
        self.ready = ready
        self.state = AgentHostState.READY

    def published(self) -> AgentReady:
        return self.ready


def _service(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, store: MemoryProviderSettingsStore) -> AgentService:
    service = AgentService(
        client=cast(
            InstalledServiceClient, SimpleNamespace(lease=object(), connection=SimpleNamespace(close=lambda: None))
        ),
        storage_root=tmp_path,
        gateway_bearer=bytearray(b"synthetic-gateway-bearer"),
        emit=lambda _event: None,
    )
    service._providers = ProviderSettingsService(
        store=store,
        catalog_source=StaticCatalogSource(),
        storage_mode=StorageMode.INSTALLED,
    )
    monkeypatch.setattr(service_module, "declared_provider_catalog_response", _declared)
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


def _declared_identities(document: dict[str, Any]) -> list[tuple[str, str]]:
    assert document["kind"] == "declared"
    return [(lane["provider"], lane["transport"]) for lane in document["catalog"]["providers"]]


def test_without_a_ready_agent_the_declared_catalog_is_served_in_its_envelope_less_turned_off_lanes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = _service(tmp_path, monkeypatch, MemoryProviderSettingsStore())
    catalog = service.admin("catalog")
    assert set(catalog) == {"kind", "catalog"}
    assert "api_version" not in catalog["catalog"]
    assert _declared_identities(catalog) == [("example", "api"), ("example", "cli"), ("other", "api")]

    _turn_off_key_lane(service)

    catalog = service.admin("catalog")
    assert _declared_identities(catalog) == [("example", "cli"), ("other", "api")]
    assert catalog["catalog"]["schema_version"] == 5
    assert catalog["catalog"]["providers"][0]["models"] == _declared()["catalog"]["providers"][1]["models"]


def test_a_declared_document_without_providers_is_refused_as_malformed() -> None:
    for document in ({}, {"providers": {}}, ["providers"], None):
        with pytest.raises(ProviderCatalogUnavailableError) as raised:
            declared_catalog_envelope(document)
        assert raised.value.reason is ProviderCatalogUnavailableReason.CATALOG_MALFORMED


def test_without_a_lease_or_readable_settings_the_catalog_is_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = MemoryProviderSettingsStore()
    service = _service(tmp_path, monkeypatch, store)
    _turn_off_key_lane(service)
    every_lane = [("example", "api"), ("example", "cli"), ("other", "api")]

    service.client.lease = None
    assert _declared_identities(service.admin("catalog")) == every_lane

    service.client.lease = cast(Any, object())
    store.refusal = StoreRefusal(code=StoreRefusalCode.PROFILE_LOCKED)
    assert _declared_identities(service.admin("catalog")) == every_lane


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

    assert catalog["api_version"] == "v1"
    assert "kind" not in catalog
    assert _identities(catalog) == [("example", "cli"), ("other", "api")]
    certified = [(item["provider"], item["transport"]) for item in service._hosted_certifications()]
    assert certified == [("example", "api"), ("example", "cli"), ("other", "api")]
