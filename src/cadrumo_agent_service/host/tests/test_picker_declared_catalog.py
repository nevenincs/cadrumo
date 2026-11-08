"""The picker's fallback carries cadrumo-agent's real declared catalogue, as its public function renders it.

The document comes from the checkout ``CADRUMO_DEV_AGENT_CHECKOUT`` names: its
interpreter calls ``declared_provider_catalog()`` and prints the document, as
the bundled image's own interpreter does in process. The service wraps it and
serves it through the catalog read, where no agent is ready. The assertions
name no lane or model: they hold for whatever the agent declares.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Final, cast

import pytest

from cadrumo_client.transport.service_client import InstalledServiceClient

from ... import service_administration as administration_module
from ...adapters.agent_process import WindowsAgentInvocationRunner
from ...adapters.provider_catalog_metadata import DECLARED_CATALOG_MODULE, declared_catalog_envelope
from ...providers.application.service import ProviderSettingsService
from ...providers.application.tests.memory_store import MemoryProviderSettingsStore
from ...providers.application.tests.synthetic_catalog import StaticCatalogSource
from ...service import AgentService
from ..launch_environment import system_environment
from .agent_checkout_support import agent_checkout, checkout_interpreter

pytestmark = [
    pytest.mark.integration,
    pytest.mark.external_tool,
    pytest.mark.windows_only,
    pytest.mark.hex_application,
]

_OUTPUT_LIMIT: Final = 256 * 1024
"""The admin response bound the served document must fit within."""
_RENDER: Final = (
    "import json, sys\n"
    f"from {DECLARED_CATALOG_MODULE} import declared_provider_catalog\n"
    "sys.stdout.write(json.dumps(declared_provider_catalog().model_dump(mode='json')))\n"
)


def _declared_document() -> dict[str, Any]:
    checkout = agent_checkout()
    completed = WindowsAgentInvocationRunner().run(
        executable=checkout_interpreter(checkout),
        arguments=("-I", "-c", _RENDER),
        directory=checkout,
        environment=system_environment(os.environ),
        timeout=60.0,
        output_limit=_OUTPUT_LIMIT,
    )
    assert completed.status == 0
    document = json.loads(completed.standard_output)
    assert isinstance(document, dict)
    return document


def test_the_fallback_serves_the_agents_declared_document_unchanged_in_its_envelope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    document = _declared_document()
    service = AgentService(
        client=cast(
            InstalledServiceClient,
            SimpleNamespace(lease=object(), connection=SimpleNamespace(close=lambda: None)),
        ),
        storage_root=tmp_path,
        gateway_bearer=bytearray(b"synthetic-gateway-bearer"),
        emit=lambda _event: None,
    )
    service._providers = ProviderSettingsService(
        store=MemoryProviderSettingsStore(),
        catalog_source=StaticCatalogSource(),
    )
    monkeypatch.setattr(
        administration_module, "declared_provider_catalog_response", lambda: declared_catalog_envelope(document)
    )

    catalog = service.admin("catalog")

    assert catalog == {"kind": "declared", "catalog": document}
    lanes = document["providers"]
    assert lanes, "the agent declares no lane"
    # The picker filters a declared lane by these two fields and the desktop
    # keys a lane, its models and their facts by these.
    for lane in lanes:
        assert isinstance(lane["provider"], str) and lane["transport"] in {"api", "cli"}, lane["id"]
        assert lane["id"] == f"{lane['provider']}_{lane['transport']}", lane["id"]
        assert isinstance(lane["recommended"], dict), lane["id"]
        for model in lane["models"]:
            assert {"id", "display_name", "vision", "size_bytes", "licence"} <= set(model), lane["id"]
