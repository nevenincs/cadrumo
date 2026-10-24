"""A PDF statement whose local AI is not ready is refused with the setup, before any request.

The statement reader asks the reader probe before its first text or scanned-page
request. When the runtime does not answer, or answers without the model the page
needs, the statement is refused with the probe's verdict, naming the local AI
setup, instead of a transport error after the retries. The import lane keeps
that verdict: validation declines the PDF with it, detection keeps the PDF
provider, and ingest raises the typed import refusal.

The runtime is a real Ollama-shaped loopback serving ``/api/tags`` and
``/api/chat``; the reader, its probe, the production client and the PDF
statement provider run for real against a bundled statement fixture.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from http import HTTPStatus
from pathlib import Path
from typing import override

import pytest

from .....adapters.inbound.financial.ledger_import import FinancialProviderResolverAdapter
from .....adapters.inbound.financial.providers.detection import detect_provider
from .....adapters.inbound.financial.providers.pdf_statement import PdfStatementProvider
from .....application.dependency_wording import statement_reader_refusal_reason
from .....application.ledger.import_ports import LedgerImportReaderUnavailableError
from .....application.ledger.statement_reading import bind_statement_reader_factory
from .....application.operator_actions.models import PreconditionVerdict
from .....application.provisioning_contracts import LOCAL_AI_PROVISION_ACTION_ID, ProvisioningPreconditionCondition
from .....core.config import Settings, override_settings
from .....core.model_catalogue import ModelRole
from .....tests.fixtures.settings import EnvFileFreeSettings
from .....tests.inventory import FIXTURES_DIR
from .....tests.loopback_llm import SilentLoopbackHandler, read_json_body, serving_loopback, write_json_response
from .....tests.pdf_fixtures import multi_page_text_pdf_bytes
from ..statement_reading import STATEMENT_READING_PROMPT_ID, LocalStatementReader
from .load_headroom_support import admitting_client

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_STATEMENT = FIXTURES_DIR / "financial" / "n26" / "n26-savings-2025-01.pdf"

#: A port nothing listens on, so the runtime genuinely does not answer.
_CLOSED_ENDPOINT = "http://127.0.0.1:1/api/chat"


@dataclass
class _RuntimeState:
    """What the loopback runtime holds, and what it was asked."""

    #: Successive ``/api/tags`` answers; the last one repeats.
    tags: list[list[str]]
    chat_requests: list[object] = field(default_factory=list)


@contextmanager
def _runtime(state: _RuntimeState) -> Generator[str]:
    """Serve an Ollama-shaped runtime whose chat answers that the model is not found."""

    class _Runtime(SilentLoopbackHandler):
        @override
        def do_GET(self) -> None:
            if self.path != "/api/tags":
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            names = state.tags[0] if len(state.tags) == 1 else state.tags.pop(0)
            write_json_response(self, {"models": [{"name": name, "size": 1} for name in names]}, status=HTTPStatus.OK)

        @override
        def do_POST(self) -> None:
            state.chat_requests.append(read_json_body(self))
            write_json_response(self, {"error": "model not found"}, status=HTTPStatus.NOT_FOUND)

    with serving_loopback(_Runtime, path="/api/chat") as endpoint:
        yield endpoint


def _settings(tmp_path: Path, endpoint: str) -> Settings:
    return EnvFileFreeSettings(
        cadrumo_llm_ollama_chat_url=endpoint,
        cadrumo_llm_cache_dir=tmp_path / "cache",
        cadrumo_llm_usage_dir=tmp_path / "usage",
        cadrumo_llm_run_record_dir=tmp_path / "run-record",
    )


@contextmanager
def _pdf_provider(tmp_path: Path, endpoint: str) -> Generator[PdfStatementProvider]:
    """Bind the production reader on an admitting client, and a PDF provider that reads through it.

    The local transport reads its chat URL from the process-wide settings, so the
    endpoint is overridden there as well as injected.
    """
    settings = _settings(tmp_path, endpoint)

    def factory() -> LocalStatementReader:
        client = admitting_client(
            settings.cadrumo_llm_ollama_text_model,
            settings=settings,
            caller="cadrumo.adapters.outbound.llm.statement_reading",
            prompt_id=STATEMENT_READING_PROMPT_ID,
        )
        return LocalStatementReader(settings=settings, client=client)

    with override_settings(cadrumo_llm_ollama_chat_url=endpoint), bind_statement_reader_factory(factory):
        yield PdfStatementProvider()


def _assert_local_ai_setup(
    verdict: PreconditionVerdict | None, role: ModelRole, condition: ProvisioningPreconditionCondition
) -> PreconditionVerdict:
    assert verdict is not None
    assert verdict.failed_condition_id == condition.value
    assert verdict.action is not None
    assert verdict.action.action_id == LOCAL_AI_PROVISION_ACTION_ID
    assert {str(evidence.values.get("role")) for evidence in verdict.evidence} == {role.value}
    return verdict


def test_a_text_statement_without_its_model_is_declined_with_the_setup_and_sends_nothing(tmp_path: Path) -> None:
    """Validation, detection and the import boundary all carry the probe's verdict for the text model."""
    state = _RuntimeState(tags=[[]])
    with _runtime(state) as endpoint, _pdf_provider(tmp_path, endpoint) as provider:
        validation = provider.validate_source(_STATEMENT)
        detected = detect_provider(_STATEMENT)
        boundary = FinancialProviderResolverAdapter().resolve(provider_id="pdf", path=_STATEMENT)
        assert boundary is not None
        crossed = boundary.validate_source(_STATEMENT)
        with pytest.raises(LedgerImportReaderUnavailableError) as refused:
            list(provider.ingest(_STATEMENT))

    verdict = _assert_local_ai_setup(
        validation.reader_unavailable_verdict,
        ModelRole.TEXT_EXTRACTION,
        ProvisioningPreconditionCondition.ROLE_MODEL_INSTALLED,
    )
    assert not validation.is_valid
    assert validation.warnings == (statement_reader_refusal_reason(verdict),)
    assert isinstance(detected, PdfStatementProvider)
    assert crossed.reader_unavailable_verdict == verdict
    assert refused.value.terminal_precondition_verdict == verdict
    assert refused.value.context == {"reason": statement_reader_refusal_reason(verdict)}
    assert state.chat_requests == []


def test_a_scanned_page_without_the_vision_model_is_refused_for_that_role(tmp_path: Path) -> None:
    """The text model being present does not hide a missing vision model, and no page is sent."""
    source = tmp_path / "scan.pdf"
    source.write_bytes(multi_page_text_pdf_bytes(("Account statement March 2026",), ()))
    state = _RuntimeState(tags=[[EnvFileFreeSettings().cadrumo_llm_ollama_text_model]])
    with _runtime(state) as endpoint, _pdf_provider(tmp_path, endpoint) as provider:
        validation = provider.validate_source(source)

    _assert_local_ai_setup(
        validation.reader_unavailable_verdict,
        ModelRole.VISION_TRANSCRIPTION,
        ProvisioningPreconditionCondition.ROLE_MODEL_INSTALLED,
    )
    assert state.chat_requests == []


def test_an_unanswering_runtime_is_refused_as_unreachable(tmp_path: Path) -> None:
    """A runtime that does not answer is named as such, with the same setup action."""
    with _pdf_provider(tmp_path, _CLOSED_ENDPOINT) as provider:
        validation = provider.validate_source(_STATEMENT)

    _assert_local_ai_setup(
        validation.reader_unavailable_verdict,
        ModelRole.TEXT_EXTRACTION,
        ProvisioningPreconditionCondition.RUNTIME_REACHABLE,
    )


def test_a_model_lost_after_the_check_is_refused_with_the_probe_verdict(tmp_path: Path) -> None:
    """The runtime drops the model between the check and the read; asked again, the probe names it."""
    state = _RuntimeState(tags=[[EnvFileFreeSettings().cadrumo_llm_ollama_text_model], []])
    with _runtime(state) as endpoint, _pdf_provider(tmp_path, endpoint) as provider:
        validation = provider.validate_source(_STATEMENT)

    _assert_local_ai_setup(
        validation.reader_unavailable_verdict,
        ModelRole.TEXT_EXTRACTION,
        ProvisioningPreconditionCondition.ROLE_MODEL_INSTALLED,
    )
    assert len(state.chat_requests) == 1
