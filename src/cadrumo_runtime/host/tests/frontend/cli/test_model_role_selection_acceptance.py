"""A real absent-selection lookup reaches the CLI in the requested language.

The portable runtime replaces transport and physical worker custody. Its async
service port delegates lookup to the production ModelRunService over a fresh
in-memory selections store; no refusal result is scripted here. Encrypted
selection persistence is exercised separately by the saved-selection test.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import override

import pytest

from cadrumo.adapters.outbound.llm.tests.model_run_support import RecordingModelRuns
from cadrumo.core.model_roles import ModelRole
from cadrumo_agent_service.adapters.agent_background_runs import HostedBackgroundRuns
from cadrumo_agent_service.providers.application.model_runs import ModelRunService
from cadrumo_agent_service.providers.application.resolution import ProviderCredentialResolver
from cadrumo_agent_service.providers.application.tests.memory_store import (
    MemoryModelRoleSelectionsStore,
    MemoryProviderSettingsStore,
)
from cadrumo_agent_service.providers.application.tests.synthetic_catalog import StaticCatalogSource, StaticLiveModels
from cadrumo_client.contracts.model_runs import ModelRunLane, ModelRunRefusal

from .ledger_ux_support import _add_evidence, _invoke, _open_bucket_session
from .portable_human_cli_runtime import serving_portable_agent

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]
__all__ = ["_open_bucket_session"]


class _UnselectedAgent(RecordingModelRuns):
    """Adapt the real service's synchronous lookup to the portable runtime port."""

    def __init__(self) -> None:
        super().__init__()
        catalog = StaticCatalogSource()
        self.models = ModelRunService(
            selections=MemoryModelRoleSelectionsStore(),
            resolver=ProviderCredentialResolver(store=MemoryProviderSettingsStore(), catalog_source=catalog),
            catalog_source=catalog,
            live_models=StaticLiveModels(),
            gateway=HostedBackgroundRuns(
                endpoint=lambda: None,
                bearer=bytearray(b"g" * 64),
                host_token=bytearray(b"h" * 43),
            ),
        )

    @override
    async def lookup(self, role: ModelRole) -> ModelRunLane | ModelRunRefusal:
        self.lookups.append(role)
        return self.models.lookup(role.value)


@pytest.mark.parametrize(
    ("language", "message"),
    [
        ("en", "Choose or check the model that reads documents in the Cadrumo desktop app"),
        ("es", "Elige o revisa el modelo que lee los documentos en la aplicación de escritorio de Cadrumo"),
        ("ca", "Tria o revisa el model que llegeix els documents a l'aplicació d'escriptori de Cadrumo"),
        ("hu", "Válaszd ki vagy ellenőrizd a dokumentumokat olvasó modellt a Cadrumo asztali alkalmazásában"),
    ],
)
def test_cli_renders_no_selection_in_the_requested_language(tmp_path: Path, language: str, message: str) -> None:
    evidence = _add_evidence(tmp_path, ("B1234567X B17283946 766,30",), filename="unlabelled.pdf")
    service = _UnselectedAgent()
    with serving_portable_agent(service):
        result = _invoke(
            [
                "--language",
                language,
                "--format",
                "json",
                "app",
                "ledger",
                "evidence",
                "extract",
                "--evidence-id",
                evidence,
            ]
        )

    assert result.exit_code != 0, result.output
    envelope = json.loads(result.output)
    assert envelope["status"] == "error"
    error = envelope["error"]
    assert error["code"] == "REFUSED_LEDGER_EVIDENCE_READER"
    assert message in error["message"], error
    facts = error["action"]["evidence"][0]["values"]
    assert facts["model_run_refusal"] == "no_selection"
    assert facts["model_role"] == "text_extraction"
    assert facts["role_selection_required"] is True
    assert service.runs == []
