"""The real cadrumo-agent's offline declaration, obtained and parsed as the service obtains it.

The agent runs from the checkout ``CADRUMO_DEV_AGENT_CHECKOUT`` names, through
its interpreter as the service's package agent variable reaches the bundled
image. The assertions name no lane or model: they hold for whatever the agent
declares, so the test proves the strict parser accepts the agent's actual
document and the typed facts it carries.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Final

import pytest

from ...providers.domain.catalog import ProviderAuthKind
from ..agent_programs import PACKAGE_AGENT_VARIABLE
from ..agent_provider_catalog import AgentProviderCatalogSource

pytestmark = [
    pytest.mark.integration,
    pytest.mark.external_tool,
    pytest.mark.windows_only,
    pytest.mark.hex_outbound_adapter,
]

CHECKOUT_VARIABLE: Final = "CADRUMO_DEV_AGENT_CHECKOUT"


def _interpreter() -> Path:
    named = os.environ.get(CHECKOUT_VARIABLE)
    if named is None or not named.strip():
        pytest.fail(f"{CHECKOUT_VARIABLE} must name a synced cadrumo-agent checkout", pytrace=False)
    interpreter = Path(named) / ".venv" / "Scripts" / "python.exe"
    if not interpreter.is_file():
        pytest.fail(f"{CHECKOUT_VARIABLE} names no synced cadrumo-agent checkout", pytrace=False)
    return interpreter


def test_the_agents_declaration_parses_with_typed_models_and_background_runs() -> None:
    source = AgentProviderCatalogSource(received={**os.environ, PACKAGE_AGENT_VARIABLE: str(_interpreter())})

    catalog = source.catalog()

    for entry in catalog.providers:
        assert set(entry.recommended.values()) <= {model.id for model in entry.models}, entry.id
        assert entry.background.runnable or not entry.background.inputs, entry.id
    on_host = [entry for entry in catalog.providers if entry.auth_kind is ProviderAuthKind.NONE]
    assert on_host, "the agent declares no keyless lane on this computer"
    for entry in on_host:
        assert entry.reads_off_host is False, entry.id
        assert entry.background.runnable, entry.id
        assert entry.recommended, entry.id
        stated = [model for model in entry.models if model.licence is not None and model.size_bytes is not None]
        assert stated, entry.id
        assert any(model.vision is True for model in entry.models), entry.id
