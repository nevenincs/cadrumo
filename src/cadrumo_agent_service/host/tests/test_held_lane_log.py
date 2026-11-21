"""Every lane the picker serves as not selectable has its cause in the service log, as the window is served it."""

from __future__ import annotations

import logging
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import pytest

from cadrumo.tests.log_records import delivered_records
from cadrumo_client.transport.service_client import InstalledServiceClient

from ...local_ai_relay import LocalAiFacts, LocalAiServer
from ...providers.application.local_model_list import LocalModelListService
from ...providers.application.service import ProviderSettingsService
from ...providers.application.tests.memory_store import MemoryLocalModelListStore, MemoryProviderSettingsStore
from ...providers.application.tests.synthetic_catalog import (
    KEYLESS_TEXT_MODEL,
    ProvidedProviderCatalogSource,
    StaticLiveModels,
    engine_catalog,
    sleeping_engine_document,
)
from ...providers.domain.record import LocalEngine
from ...service import AgentService
from ...service_support import HeldLaneLog
from ..controller import AgentGenerations, AgentHostController, AgentHostState, AgentReady

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _lane(*, selectable: bool, authentication: str, catalog: str = "available") -> dict[str, Any]:
    return {
        "provider_id": "codex_cli",
        "transport": "codex_app_server",
        "health": {
            "configured": "available",
            "transport": "available",
            "authentication": authentication,
            "catalog": catalog,
            "admission": "admitted",
            "selectable": selectable,
            "reasons": ["provider sign-in required"],
        },
        "catalog": {"state": {"status": "stale"}},
    }


def _held_lines(caplog: pytest.LogCaptureFixture) -> list[str]:
    records = delivered_records(caplog, "cadrumo_agent_service.service")
    return [record.getMessage() for record in records if "agent picker lane" in record.getMessage()]


def test_a_held_lane_is_logged_with_its_axes_once_per_cause(caplog: pytest.LogCaptureFixture) -> None:
    log = HeldLaneLog()
    with caplog.at_level(logging.INFO):
        log.observe({"providers": [_lane(selectable=False, authentication="unknown")]})
        log.observe({"providers": [_lane(selectable=False, authentication="unknown")]})
        log.observe({"providers": [_lane(selectable=False, authentication="unauthenticated")]})
        log.observe({"providers": [_lane(selectable=True, authentication="authenticated")]})
        log.observe({"providers": [_lane(selectable=True, authentication="authenticated")]})

    lines = _held_lines(caplog)
    assert lines == [
        "agent picker lane held provider=codex_cli transport=codex_app_server configured=available "
        "transport_health=available authentication=unknown catalog=available admission=admitted "
        "catalog_state=stale reasons=provider sign-in required",
        "agent picker lane held provider=codex_cli transport=codex_app_server configured=available "
        "transport_health=available authentication=unauthenticated catalog=available admission=admitted "
        "catalog_state=stale reasons=provider sign-in required",
        "agent picker lane selectable provider=codex_cli transport=codex_app_server",
    ]


def test_a_lane_selectable_from_the_start_is_not_logged(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO):
        HeldLaneLog().observe({"providers": [_lane(selectable=True, authentication="authenticated")]})

    assert _held_lines(caplog) == []


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


def _serving(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *refusals: str) -> AgentService:
    """The service over in-memory stores, its running agent serving the sleeping llama.cpp lane with ``refusals``."""
    service = AgentService(
        local_engine_default=LocalEngine.LLAMACPP,
        client=cast(
            InstalledServiceClient,
            SimpleNamespace(
                lease=SimpleNamespace(lease_id=uuid4(), profile_id=uuid4()),
                connection=SimpleNamespace(close=lambda: None),
            ),
        ),
        storage_root=tmp_path,
        gateway_bearer=bytearray(b"synthetic-gateway-bearer"),
        emit=lambda _event: None,
    )
    source = ProvidedProviderCatalogSource(engine_catalog())
    service._local_models = LocalModelListService(
        store=MemoryLocalModelListStore(),
        catalog_source=source,
        live_models=StaticLiveModels(),
        default_engine=LocalEngine.LLAMACPP,
    )
    service._providers = ProviderSettingsService(
        store=MemoryProviderSettingsStore(),
        catalog_source=source,
        selected_engine=service._local_models.selected_engine,
    )
    document = sleeping_engine_document(LocalEngine.LLAMACPP, KEYLESS_TEXT_MODEL)
    document["providers"][0]["health"]["reasons"].extend(refusals)
    service._controller = cast(AgentHostController, _Controller())
    monkeypatch.setattr(service, "_served_catalog", lambda _ready: document)
    return service


_DORMANT = LocalAiFacts(engine=LocalEngine.LLAMACPP, server=LocalAiServer.DORMANT)


def test_a_sleeping_server_s_lane_is_logged_as_the_window_is_served_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    service = _serving(tmp_path, monkeypatch)
    with caplog.at_level(logging.INFO):
        catalog = service.admin("catalog", local_ai=_DORMANT)

    assert catalog["providers"][0]["health"]["selectable"] is True
    assert _held_lines(caplog) == []
    assert service._local_ai.facts() == _DORMANT
    assert not [record for record in delivered_records(caplog) if record.levelno >= logging.WARNING]


def test_a_sleeping_server_s_lane_refused_for_another_cause_is_logged_held_at_info(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    service = _serving(tmp_path, monkeypatch, "binary_out_of_proof_range")
    with caplog.at_level(logging.INFO):
        service.admin("catalog", local_ai=_DORMANT)
        # A read without the manager's facts relays the lane unknown, and keeps the facts last sent.
        service.admin("catalog")

    records = [
        record
        for record in delivered_records(caplog, "cadrumo_agent_service.service")
        if "agent picker lane" in record.getMessage()
    ]
    assert [record.getMessage() for record in records] == [
        "agent picker lane held provider=llamacpp transport=api configured=available transport_health=available "
        "authentication=not_applicable catalog=available admission=not_admitted catalog_state=None "
        "reasons=binary_version_unavailable; binary_out_of_proof_range",
        "agent picker lane held provider=llamacpp transport=api configured=available transport_health=unknown "
        "authentication=not_applicable catalog=available admission=not_admitted catalog_state=None reasons=",
    ]
    assert {record.levelno for record in records} == {logging.INFO}
    assert service._local_ai.facts() == _DORMANT
