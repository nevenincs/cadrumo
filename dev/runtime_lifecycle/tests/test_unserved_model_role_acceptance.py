"""A real lookup with no picked model reaches the CLI in the requested language.

The portable runtime replaces transport and physical worker custody. Its async
service port delegates lookup to the production ModelRunService over a fresh
in-memory record in which the person picked no model; no refusal result is
scripted here. Encrypted record persistence is exercised separately by the
saved local model list test.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import override

import pytest

from cadrumo.adapters.outbound.llm.tests.model_run_support import RecordingModelRuns
from cadrumo.core.model_roles import ModelRole
from cadrumo.tests.pdf_fixtures import text_pdf_bytes
from cadrumo_agent_service.adapters.agent_background_runs import HostedBackgroundRuns
from cadrumo_agent_service.providers.application.model_runs import ModelRunService
from cadrumo_agent_service.providers.application.resolution import ProviderCredentialResolver
from cadrumo_agent_service.providers.application.tests.memory_store import (
    MemoryLocalModelListStore,
    MemoryProviderSettingsStore,
)
from cadrumo_agent_service.providers.application.tests.synthetic_catalog import (
    ProvidedProviderCatalogSource,
    StaticLiveModels,
    synthetic_catalog,
)
from cadrumo_client.contracts.model_runs import ModelRunLane, ModelRunRefusal
from cadrumo_runtime.host.tests.frontend.cli.cli_runner import invoke_cached_cli
from cadrumo_runtime.host.tests.frontend.cli.ledger_ux_support import open_ledger_ux_session
from cadrumo_runtime.host.tests.frontend.cli.portable_human_cli_runtime import serving_portable_agent

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.fixture(autouse=True)
def _open_bucket_session(tmp_path: Path, cli_runtime_lifetime: None) -> Iterator[None]:
    with open_ledger_ux_session(tmp_path):
        yield


class _UnservedAgent(RecordingModelRuns):
    """Adapt the real service's synchronous lookup to the portable runtime port."""

    def __init__(self) -> None:
        super().__init__()
        catalog = ProvidedProviderCatalogSource(synthetic_catalog())
        self.models = ModelRunService(
            model_list=MemoryLocalModelListStore(),
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
        ("en", "The automatic reader could not run, so nothing was read."),
        ("es", "El lector automático no ha podido funcionar, así que no se ha leído nada."),
        ("ca", "El lector automàtic no ha pogut funcionar, així que no s'ha llegit res."),
        ("hu", "Az automatikus olvasó nem tudott elindulni, ezért semmi sem lett beolvasva."),
    ],
)
def test_cli_renders_no_selection_in_the_requested_language(tmp_path: Path, language: str, message: str) -> None:
    pdf = tmp_path / "unlabelled.pdf"
    pdf.write_bytes(text_pdf_bytes(("B1234567X B17283946 766,30",)))
    added = invoke_cached_cli(
        ["--format", "json", "app", "ledger", "evidence", "add", str(pdf), "--supplier", "Acme SL"]
    )
    assert added.exit_code == 0, added.output
    evidence = json.loads(added.output)["result"]["evidence_id"]
    service = _UnservedAgent()
    with serving_portable_agent(service):
        result = invoke_cached_cli(
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
