"""The service runs the declared agent command and projects its catalog into provider status.

The catalog command runs in an isolated child process. Provider records use
real worker encryption with explicitly controlled login and service verification.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Final

import pytest
from pydantic import SecretStr

from cadrumo.core.storage_environment import StorageMode
from cadrumo_agent_service.adapters.agent_programs import PACKAGE_AGENT_VARIABLE
from cadrumo_agent_service.adapters.agent_provider_catalog import AgentProviderCatalogSource
from cadrumo_agent_service.providers.application.contracts import (
    ProviderCredentialSource,
    ProviderReadiness,
    ProviderSettingsActionAccepted,
    ProviderSettingsRefusal,
    ProviderSettingsRefusalCode,
    ProviderSettingsStatus,
)
from cadrumo_agent_service.providers.application.service import ProviderSettingsService
from cadrumo_agent_service.providers.application.tests.synthetic_catalog import KEY_LANE, synthetic_document
from cadrumo_agent_service.providers.domain.catalog import parse_provider_catalog
from cadrumo_agent_service.providers.persistence.store import SecureProviderSettingsStore
from cadrumo_client.contracts.service_access import ServiceConnected
from cadrumo_runtime.host.tests.test_service_records import service_record_runtime

from .provider_catalog_support import provider_record_capability, stand_in_agent_image

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="the stand-in agent image is a Windows program"),
    pytest.mark.usefixtures("authority_operation"),
]

_PROVIDER_ENVIRONMENT_VARIABLE: Final = "CADRUMO_LLM_EXAMPLE_API_KEY"


def _received_environment(image: Path | None) -> dict[str, str]:
    received = dict(os.environ)
    received[_PROVIDER_ENVIRONMENT_VARIABLE] = "synthetic-secret-that-must-not-reach-the-agent"
    if image is None:
        received.pop(PACKAGE_AGENT_VARIABLE, None)
    else:
        received[PACKAGE_AGENT_VARIABLE] = str(image)
    return received


def test_the_service_runs_the_declared_agent_catalog_and_projects_its_status(tmp_path: Path) -> None:
    image, record = stand_in_agent_image(tmp_path, catalog_document=synthetic_document())
    source = AgentProviderCatalogSource(received=_received_environment(image))

    catalog = source.catalog()
    expected = sorted(parse_provider_catalog(synthetic_document()).provider_ids)
    assert sorted(catalog.provider_ids) == expected
    with service_record_runtime(tmp_path, record_capabilities=(provider_record_capability(),)) as runtime:
        client = runtime.connect_service()
        assert isinstance(runtime.admit(client), ServiceConnected)
        assert client.claim() is not None
        store = SecureProviderSettingsStore(client=client)
        settings = ProviderSettingsService(
            store=store,
            catalog_source=source,
            environment={},
            storage_mode=StorageMode.INSTALLED,
        )
        status = settings.status()
        assert isinstance(status, ProviderSettingsStatus), status
        assert sorted(entry.id for entry in status.providers) == expected
        initial = next(entry for entry in status.providers if entry.id == KEY_LANE)
        accepted = settings.set_credential(
            KEY_LANE,
            secret=SecretStr("synthetic-provider-secret"),
            expected_revision=initial.revision,
        )
        assert isinstance(accepted, ProviderSettingsActionAccepted), accepted
        assert accepted.entry.source is ProviderCredentialSource.PROFILE
        assert accepted.entry.readiness is ProviderReadiness.NOT_VERIFIED
        assert accepted.entry.revision != initial.revision
        reread = settings.status()
        assert isinstance(reread, ProviderSettingsStatus), reread
        assert next(entry for entry in reread.providers if entry.id == KEY_LANE) == accepted.entry
        stale = settings.set_credential(
            KEY_LANE,
            secret=SecretStr("synthetic-rejected-stale-secret"),
            expected_revision=initial.revision,
        )
        assert isinstance(stale, ProviderSettingsRefusal)
        assert stale.code is ProviderSettingsRefusalCode.REVISION_CONFLICT
        assert "synthetic-provider-secret" not in reread.model_dump_json()
        for candidate in runtime.root.rglob("*"):
            if candidate.is_file():
                assert b"synthetic-provider-secret" not in candidate.read_bytes()
    invocation = json.loads((record / "invocation.json").read_text(encoding="utf-8"))
    assert invocation["arguments"] == ["providers", "--declared", "--json"]
    assert invocation["provider_secret_names"] == []


def test_a_service_without_a_declared_agent_returns_typed_catalog_unavailability(tmp_path: Path) -> None:
    source = AgentProviderCatalogSource(received=_received_environment(None))

    with service_record_runtime(tmp_path, record_capabilities=(provider_record_capability(),)) as runtime:
        client = runtime.connect_service()
        assert isinstance(runtime.admit(client), ServiceConnected)
        assert client.claim() is not None
        status = ProviderSettingsService(
            store=SecureProviderSettingsStore(client=client),
            catalog_source=source,
            environment={},
            storage_mode=StorageMode.INSTALLED,
        ).status()
        assert isinstance(status, ProviderSettingsRefusal), status
        assert status.code is ProviderSettingsRefusalCode.CATALOG_UNAVAILABLE
