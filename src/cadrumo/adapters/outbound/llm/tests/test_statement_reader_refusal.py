"""A PDF statement whose reader the agent cannot run is refused with that verdict, before any run.

The statement reader asks the agent service for each role's lane before it
sends a page. A role with no selection, an unreachable service, or a lane that
reads off the host, which ledger import has no consent for, refuses there, and
the statement is refused with that typed verdict instead of a read failure.
The import lane keeps it: validation declines the PDF with it, detection keeps
the PDF provider, and ingest raises the typed import refusal.

The reader, the production client and the PDF statement provider run for real
against a bundled statement fixture; the agent service is the recording
stand-in that answers the lookup.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager, nullcontext
from pathlib import Path

import pytest

from cadrumo_client.contracts.model_runs import ModelRunRefusalCode

from .....adapters.inbound.financial.ledger_import import FinancialProviderResolverAdapter
from .....adapters.inbound.financial.providers.detection import detect_provider
from .....adapters.inbound.financial.providers.pdf_statement import PdfStatementProvider
from .....application.reader_refusal_wording import statement_reader_refusal_reason
from .....application.ledger.import_ports import LedgerImportReaderUnavailableError
from .....application.ledger.statement_reading import bind_statement_reader_factory
from .....application.operator_actions.models import PreconditionVerdict
from .....core.model_roles import ModelRole
from .....tests.fixtures.settings import EnvFileFreeSettings
from .....tests.inventory import FIXTURES_DIR
from .....tests.pdf_fixtures import multi_page_text_pdf_bytes
from ....persistence.llm.cache import LLMCache
from ....persistence.llm.usage import UsageRecorder
from ..client import LLMClient
from ..preconditions import LLMPreconditionCondition
from ..statement_reading import STATEMENT_READING_PROMPT_ID, StatementReader
from .model_run_support import DEFAULT_LANE, RecordingModelRuns, serving_agent

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_STATEMENT = FIXTURES_DIR / "financial" / "n26" / "n26-savings-2025-01.pdf"


@contextmanager
def _pdf_provider(tmp_path: Path) -> Generator[PdfStatementProvider]:
    """Bind the production reader on a real client, and a PDF provider that reads through it."""
    settings = EnvFileFreeSettings(
        cadrumo_llm_cache_dir=tmp_path / "cache",
        cadrumo_llm_usage_dir=tmp_path / "usage",
        cadrumo_llm_run_record_dir=tmp_path / "run-record",
    )

    def factory() -> StatementReader:
        client = LLMClient(
            settings=settings,
            caller="cadrumo.adapters.outbound.llm.statement_reading",
            prompt_id=STATEMENT_READING_PROMPT_ID,
            cache=LLMCache(root_dir=settings.cadrumo_llm_cache_dir),
            usage_recorder=UsageRecorder(root_dir=settings.cadrumo_llm_usage_dir),
        )
        return StatementReader(settings=settings, client=client)

    with bind_statement_reader_factory(factory):
        yield PdfStatementProvider()


def _model_run_refusal(verdict: PreconditionVerdict | None, code: ModelRunRefusalCode, role: ModelRole) -> None:
    assert verdict is not None
    assert verdict.failed_condition_id == LLMPreconditionCondition.AGENT_MODEL_RUN_COMPLETED.value
    (evidence,) = verdict.evidence
    assert evidence.values["model_run_refusal"] == code.value
    assert evidence.values["model_role"] == role.value


def test_a_text_role_without_a_selection_is_declined_at_every_import_boundary(tmp_path: Path) -> None:
    """Validation, detection and the import boundary all carry the agent's refusal, and no page is sent."""
    with (
        serving_agent(lookup_refusal=ModelRunRefusalCode.NO_SELECTION) as service,
        _pdf_provider(tmp_path) as provider,
    ):
        validation = provider.validate_source(_STATEMENT)
        detected = detect_provider(_STATEMENT)
        boundary = FinancialProviderResolverAdapter().resolve(provider_id="pdf", path=_STATEMENT)
        assert boundary is not None
        crossed = boundary.validate_source(_STATEMENT)
        with pytest.raises(LedgerImportReaderUnavailableError) as refused:
            list(provider.ingest(_STATEMENT))

    verdict = validation.reader_unavailable_verdict
    _model_run_refusal(verdict, ModelRunRefusalCode.NO_SELECTION, ModelRole.TEXT_EXTRACTION)
    assert verdict is not None
    assert not validation.is_valid
    assert validation.warnings == (statement_reader_refusal_reason(),)
    assert isinstance(detected, PdfStatementProvider)
    assert crossed.reader_unavailable_verdict == verdict
    assert refused.value.terminal_precondition_verdict == verdict
    assert refused.value.context == {"reason": statement_reader_refusal_reason()}
    assert ModelRole.TEXT_EXTRACTION in service.lookups
    assert service.runs == []


@pytest.mark.parametrize("bound", [False, True], ids=["no-service", "service"])
def test_an_unavailable_service_is_refused_as_unavailable(tmp_path: Path, *, bound: bool) -> None:
    """No service bound and a service that reports itself unavailable read the same, with nothing sent."""
    service = serving_agent(lookup_refusal=ModelRunRefusalCode.SERVICE_UNAVAILABLE) if bound else nullcontext()
    with service as port, _pdf_provider(tmp_path) as provider:
        validation = provider.validate_source(_STATEMENT)

    _model_run_refusal(
        validation.reader_unavailable_verdict, ModelRunRefusalCode.SERVICE_UNAVAILABLE, ModelRole.TEXT_EXTRACTION
    )
    if isinstance(port, RecordingModelRuns):
        assert port.runs == []


def test_a_lane_that_reads_off_the_host_is_refused_for_want_of_consent(tmp_path: Path) -> None:
    """Ledger import asks for no consent, so a statement is never sent to an off-host lane."""
    with serving_agent(lane=DEFAULT_LANE) as service, _pdf_provider(tmp_path) as provider:
        validation = provider.validate_source(_STATEMENT)

    verdict = validation.reader_unavailable_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == LLMPreconditionCondition.EVIDENCE_OFF_HOST_DISPATCH_PERMITTED.value
    assert not validation.is_valid
    assert service.runs == [], "a statement reached an off-host lane without consent"


def test_a_scanned_page_whose_vision_role_is_refused_is_refused_for_that_role(tmp_path: Path) -> None:
    """A page with no text layer asks the vision role first, and its refusal names that role."""
    source = tmp_path / "scan.pdf"
    source.write_bytes(multi_page_text_pdf_bytes(("Account statement March 2026",), ()))
    with (
        serving_agent(lookup_refusal=ModelRunRefusalCode.LANE_UNAVAILABLE) as service,
        _pdf_provider(tmp_path) as provider,
    ):
        validation = provider.validate_source(source)

    _model_run_refusal(
        validation.reader_unavailable_verdict, ModelRunRefusalCode.LANE_UNAVAILABLE, ModelRole.VISION_TRANSCRIPTION
    )
    assert service.lookups == [ModelRole.VISION_TRANSCRIPTION]
    assert service.runs == []
