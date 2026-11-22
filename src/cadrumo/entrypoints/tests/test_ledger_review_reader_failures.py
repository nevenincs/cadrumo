"""A classification review that gets no proposal says why, in the refusal's own context.

Drives :func:`suggest_llm_classification` with the review's composed ports, so
the default text reader, the production LLM client and the agent adapter run
against a recording stand-in for the agent service behind the model-run port.
The replies are model text at the parser; nothing is applied.

A failed run names the agent's refusal code and a reply the parse did not
accept is named invalid output, so ``ERROR_TRANSACTION_LLM_CLASSIFIER`` never
arrives without its cause. A reader the service cannot resolve stays the
retryable reader refusal carrying the service's verdict.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo_client.contracts.model_runs import ModelRunRefusalCode

from ...adapters.outbound.llm.tests.model_run_support import ON_HOST_LANE, serving_agent
from ...adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ...adapters.persistence.storage.tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from ...application.ledger.classification_job_run import MODEL_RUN_REFUSAL_CONTEXT_KEY
from ...application.ledger.evidence_errors import PurchaseInvoiceEvidenceReaderError
from ...application.ledger.llm_classification import suggest_llm_classification
from ...application.ledger.llm_classification_ports import LLMClassificationSuggestion
from ...core.errors.error_codes import build_error_envelope
from ...domain.calculations.registry.authority import bundled_indexed_authority
from ...domain.transactions.enums import BusinessClassification, TransactionDirection
from ...domain.transactions.errors import LLMClassifierError
from ...domain.transactions.models import Transaction, TransactionCatalogue
from ...domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ..ledger_llm_composition import compose_ledger_llm

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_BUCKET_ID = "6d2f4a8b-3c5e-4f70-9b1c-2d3e4f5a6b7c"

_VALID_REPLY = '{"classification": "BUSINESS", "confidence": 0.8, "reason": "material de oficina {pedido 3}"}'
"""A small model's answer whose reason quotes braces, as a person's statement wording may."""


@pytest.fixture
def profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as runtime_profile:
        yield runtime_profile


def _transaction() -> Transaction:
    booked = datetime.now(UTC).date()
    raw = RawTransaction(
        provider_transaction_id="row-review-reader",
        booked_date=booked,
        value_date=booked,
        amount=Decimal("42.10"),
        currency="EUR",
        counterparty="Papeleria Demo SL",
        description="Material de oficina pedido 3",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="f" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=datetime.now(UTC),
            provider_name="manual",
        ),
        raw_fields={"Concepto": "Material de oficina pedido 3"},
    )
    return Transaction.model_validate(
        {"raw": raw, "direction": TransactionDirection.OUTGOING, "source_jurisdiction": "ES", "group_label": None}
    )


def _suggest(profile: TestRuntimeProfile) -> LLMClassificationSuggestion:
    with bundled_indexed_authority().operation() as operation:
        transaction = _transaction()
        repository = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=profile.repository)
        repository.save(TransactionCatalogue.from_transactions((transaction,)))
        return suggest_llm_classification(
            bucket_id=_BUCKET_ID,
            transaction_id=transaction.transaction_id,
            transaction_repository=repository,
            settings=profile.settings,
            ports=compose_ledger_llm(bucket_id=_BUCKET_ID, settings=profile.settings).ports,
            operation=operation,
        )


def _refused_cause(profile: TestRuntimeProfile) -> tuple[str, dict[str, str] | None]:
    with pytest.raises(LLMClassifierError) as raised:
        _suggest(profile)
    envelope = build_error_envelope(raised.value)
    return envelope.code, envelope.context


def test_a_valid_reply_is_a_proposal(profile: TestRuntimeProfile) -> None:
    with serving_agent(lane=ON_HOST_LANE, replies=(_VALID_REPLY,)) as service:
        suggestion = _suggest(profile)
    assert suggestion.classification is BusinessClassification.BUSINESS
    assert suggestion.reason == "material de oficina {pedido 3}"
    assert len(service.runs) == 1


@pytest.mark.parametrize(
    "refusal",
    [ModelRunRefusalCode.TIMEOUT, ModelRunRefusalCode.RUN_FAILED, ModelRunRefusalCode.REFUSED_BY_PROVIDER],
)
def test_a_failed_run_names_the_agents_refusal_code(profile: TestRuntimeProfile, refusal: ModelRunRefusalCode) -> None:
    with serving_agent(lane=ON_HOST_LANE, run_refusal=refusal):
        code, context = _refused_cause(profile)
    assert code == "ERROR_TRANSACTION_LLM_CLASSIFIER"
    assert context is not None and context[MODEL_RUN_REFUSAL_CONTEXT_KEY] == refusal.value


def test_prose_without_an_object_twice_is_invalid_output(profile: TestRuntimeProfile) -> None:
    """The adapter asks once more for a reply with no JSON object; a second one without it is invalid output."""
    with serving_agent(lane=ON_HOST_LANE, replies=("Claro, es un gasto de oficina.",)) as service:
        code, context = _refused_cause(profile)
    assert len(service.runs) == 2
    assert code == "ERROR_TRANSACTION_LLM_CLASSIFIER"
    assert context is not None and context[MODEL_RUN_REFUSAL_CONTEXT_KEY] == ModelRunRefusalCode.OUTPUT_INVALID.value


@pytest.mark.parametrize(
    "reply",
    [
        '{"classification": "business", "confidence": 0.8, "reason": "oficina"}',
        '{"classification": "BUSINESS", "confidence": 0.8, "reason": "oficina", "iva_rate": 21}',
        '{"classification": "MIXED", "confidence": 0.8, "reason": "oficina", "business_pct": 50}',
    ],
    ids=["classification-outside-the-closed-list", "field-outside-the-schema", "percentage-outside-0-1"],
)
def test_an_object_the_parse_refuses_is_invalid_output(profile: TestRuntimeProfile, reply: str) -> None:
    with serving_agent(lane=ON_HOST_LANE, replies=(reply,)):
        code, context = _refused_cause(profile)
    assert code == "ERROR_TRANSACTION_LLM_CLASSIFIER"
    assert context is not None and context[MODEL_RUN_REFUSAL_CONTEXT_KEY] == ModelRunRefusalCode.OUTPUT_INVALID.value


def test_a_reader_the_service_cannot_resolve_is_the_reader_refusal_with_its_verdict(
    profile: TestRuntimeProfile,
) -> None:
    with (
        serving_agent(lane=ON_HOST_LANE, lookup_refusal=ModelRunRefusalCode.LANE_UNAVAILABLE) as service,
        pytest.raises(PurchaseInvoiceEvidenceReaderError) as raised,
    ):
        _suggest(profile)
    assert service.runs == []
    assert build_error_envelope(raised.value).code == "REFUSED_LEDGER_EVIDENCE_READER"
    verdict = raised.value.terminal_precondition_verdict
    assert verdict is not None
    assert verdict.evidence[0].values[MODEL_RUN_REFUSAL_CONTEXT_KEY] == ModelRunRefusalCode.LANE_UNAVAILABLE.value
