"""The picker, the provider settings and the local model lists serve one lane set per local engine.

The service's own administration answers are read, as the window reads them:
the picker's catalogue, the settings status and the local model lists. Only the
profile's stores are in memory and the agent's catalogue is synthetic. For
each engine the three list the same lanes, the selected engine's keyless lane
among them and the other engine's in none, whether the picker is served the
declared catalogue or a running agent's catalogue that still lists both engines.
A frontend that filtered nothing would show the same lanes in all three.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from cadrumo_client.transport.service_client import InstalledServiceClient

from ... import service_administration as administration_module
from ...adapters.provider_catalog_metadata import declared_catalog_envelope
from ...providers.application.local_model_list import LocalModelListService
from ...providers.application.ports import ProviderCatalogUnavailableError, ProviderCatalogUnavailableReason
from ...providers.application.service import ProviderSettingsService
from ...providers.application.tests.memory_store import MemoryLocalModelListStore, MemoryProviderSettingsStore
from ...providers.application.tests.synthetic_catalog import (
    ProvidedProviderCatalogSource,
    engine_catalog,
    engine_document,
)
from ...providers.domain.record import LocalEngine, LocalPlacement
from ...service import AgentService
from ..controller import AgentGenerations, AgentHostController, AgentHostState, AgentReady

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_EVERY_LANE = tuple(entry.id for entry in engine_catalog().providers)
_KEYLESS = frozenset(entry.id for entry in engine_catalog().providers if entry.auth_kind.value == "none")


class _Controller:
    def __init__(self) -> None:
        self.ready = AgentReady(
            generations=AgentGenerations("synthetic-session", "synthetic-settings"),
            gateway_port=12345,
            agent_version="synthetic-agent",
            hosting_contract=1,
        )
        self.state = AgentHostState.READY

    def published(self) -> AgentReady:
        return self.ready


def _no_sign_in() -> dict[str, tuple[str, ...]]:
    raise ProviderCatalogUnavailableError(ProviderCatalogUnavailableReason.AGENT_NOT_FOUND)


def _service(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, engine: LocalEngine | None) -> AgentService:
    """The service over in-memory stores, its record naming ``engine``, or unreadable when ``None``."""
    service = AgentService(
        local_engine_default=LocalEngine.LLAMACPP,
        client=cast(
            InstalledServiceClient, SimpleNamespace(lease=object(), connection=SimpleNamespace(close=lambda: None))
        ),
        storage_root=tmp_path,
        gateway_bearer=bytearray(b"synthetic-gateway-bearer"),
        emit=lambda _event: None,
    )
    source = ProvidedProviderCatalogSource(engine_catalog())
    store = MemoryLocalModelListStore()
    service._local_models = LocalModelListService(
        store=store, catalog_source=source, default_engine=LocalEngine.LLAMACPP
    )
    service._providers = ProviderSettingsService(
        store=MemoryProviderSettingsStore(),
        catalog_source=source,
        selected_engine=service._local_models.selected_engine,
    )
    monkeypatch.setattr(service._catalog, "gui_sign_in_methods", _no_sign_in)
    monkeypatch.setattr(
        administration_module,
        "declared_provider_catalog_response",
        lambda: declared_catalog_envelope(json.loads(engine_document())),
    )
    if engine is None:
        store.unreadable = "f" * 64
    else:
        chosen = service.admin(
            "local_engine_choose",
            engine=engine.value,
            placement=LocalPlacement.AUTO.value,
            expected_revision=service.admin("local_engine")["revision"],
        )
        assert chosen["engine"] == engine.value, chosen
    return service


def _serve_both_engines(service: AgentService, monkeypatch: pytest.MonkeyPatch) -> None:
    """Make a running agent answer with every lane, both engines' included, as an agent unaware of the engine would."""
    document = {
        "api_version": "v1",
        "providers": [
            {"provider_id": entry.provider, "transport": entry.transport.value, "execution_mode": entry.id}
            for entry in engine_catalog().providers
        ],
    }
    service._controller = cast(AgentHostController, _Controller())
    monkeypatch.setattr(service, "_served_catalog", lambda _ready: document)


def _names(values: Iterable[object]) -> tuple[str, ...]:
    names = tuple(values)
    assert all(isinstance(name, str) for name in names), names
    return tuple(str(name) for name in names)


def _picker(service: AgentService) -> tuple[str, ...]:
    catalog = service.admin("catalog")
    if catalog.get("kind") == "declared":
        return _names(lane["id"] for lane in catalog["catalog"]["providers"])
    return _names(f"{lane['provider_id']}_{lane['transport']}" for lane in catalog["providers"])


def _settings(service: AgentService) -> tuple[str, ...]:
    return _names(entry["id"] for entry in service.admin("status")["providers"])


def _setup(service: AgentService) -> tuple[str, ...]:
    return _names(service.admin("local_models")["local_lanes"])


@pytest.mark.parametrize("served", ["declared", "running"])
@pytest.mark.parametrize("engine", list(LocalEngine))
def test_the_three_surfaces_list_the_same_lanes_for_each_engine(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, engine: LocalEngine, served: str
) -> None:
    service = _service(tmp_path, monkeypatch, engine=engine)
    if served == "running":
        _serve_both_engines(service, monkeypatch)
    other = next(held for held in LocalEngine if held is not engine)
    expected = tuple(lane for lane in _EVERY_LANE if lane != f"{other.value}_api")

    picker, settings, setup = _picker(service), _settings(service), _setup(service)

    assert picker == settings == expected
    assert frozenset(setup) == _KEYLESS & frozenset(picker) == _KEYLESS & frozenset(settings)
    assert f"{engine.value}_api" in setup
    assert f"{other.value}_api" not in {*picker, *settings, *setup}


@pytest.mark.parametrize("served", ["declared", "running"])
def test_an_unreadable_engine_record_lists_neither_engine_lane_on_any_surface(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, served: str
) -> None:
    service = _service(tmp_path, monkeypatch, engine=None)
    if served == "running":
        _serve_both_engines(service, monkeypatch)
    engines = {f"{engine.value}_api" for engine in LocalEngine}
    expected = tuple(lane for lane in _EVERY_LANE if lane not in engines)

    picker, settings = _picker(service), _settings(service)

    assert picker == settings == expected
    assert frozenset(_setup(service)) == _KEYLESS - engines


def test_changing_the_engine_changes_every_served_list(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    service = _service(tmp_path, monkeypatch, engine=LocalEngine.LLAMACPP)
    before = (_picker(service), _settings(service), _setup(service))

    changed = service.admin(
        "local_engine_choose",
        engine=LocalEngine.OLLAMA.value,
        placement=LocalPlacement.AUTO.value,
        expected_revision=service.admin("local_engine")["revision"],
    )
    assert changed["engine"] == LocalEngine.OLLAMA.value, changed
    after = (_picker(service), _settings(service), _setup(service))

    for lanes in before:
        assert "llamacpp_api" in lanes and "ollama_api" not in lanes
    for lanes in after:
        assert "ollama_api" in lanes and "llamacpp_api" not in lanes
