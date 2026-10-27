"""Stage two reads the stage-one artefact, through the agent, for the text extraction role.

The enrolment gate for the semantic extraction surface. It is deliberately about
the WIRING rather than about reading quality: accuracy is owned by the measured
lane, and a unit test passes whether or not anything calls the code.

Four properties, each of which has failed somewhere in this repository before:

* The stage takes a :class:`~application.ledger.document_transcription.DocumentTranscription`, not a
  bare string. A string carries no answer to "who read these characters off the
  document", and that answer is the ORIGIN stamped on every value the stage
  proposes.
* The origin is READ from the artefact rather than asserted. Hardcoding one was
  defensible while a text layer was the only thing that could reach this reader;
  now that a vision transcription can, it would launder a rasterised read into
  an exact-looking one.
* The read names the text extraction role and no model, so the agent service
  runs it on the lane and model it derives for that role.
* A taxpayer's document is marked as evidence unless the caller names the
  public corpus, so a lane that reads off the host refuses it without consent.

No model runs here. The real client dispatches to a recording stand-in for the
agent service, so what was sent, and for which role, is observed at the
model-run port.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from .....application.ledger.document_transcription import DocumentTranscription, TranscriberIdentity
from .....core.field_origin import FieldOrigin
from .....core.model_roles import ModelRole
from .....core.provenance_stamp import LOCAL_TRANSPORT_LABEL
from .....domain.calculations.registry.authority import PinnedAuthorityOperation
from .....tests.fixtures.settings import EnvFileFreeSettings
from ....persistence.llm.cache import LLMCache
from ....persistence.llm.usage import UsageRecorder
from ..client import LLMClient
from ..errors import LLMConsentError
from ..evidence_draft_text import TextInvoiceFieldExtractor
from .model_run_support import DEFAULT_LANE, ON_HOST_LANE, RecordingModelRuns, serving_agent

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

if TYPE_CHECKING:
    from .....application.ledger.invoice_draft_records import InvoiceDraft

_REPLY = json.dumps(
    {
        "supplier_tax_id": "B12345674",
        "supplier_tax_id_anchor": "B12345674",
        "supplier_tax_id_role_evidence": "Proveedor:",
        "taxable_base": "100,00",
        "taxable_base_anchor": "100,00 EUR",
    },
)


def _transcription(origin: FieldOrigin, *, name: str = "pdfplumber") -> DocumentTranscription:
    return DocumentTranscription(
        text="FACTURA\nProveedor: EJEMPLO SL B12345674\nBase imponible 100,00 EUR",
        page_count=1,
        source_content_sha256="e" * 64,
        transcriber=TranscriberIdentity(transport=LOCAL_TRANSPORT_LABEL, origin=origin, name=name, revision="wiring"),
    )


def _extractor(
    tmp_path: Path, *, operation: PinnedAuthorityOperation, public_corpus: bool = False
) -> TextInvoiceFieldExtractor:
    settings = EnvFileFreeSettings(
        cadrumo_llm_cache_dir=tmp_path / "cache",
        cadrumo_llm_usage_dir=tmp_path / "usage",
        cadrumo_llm_run_record_dir=tmp_path / "run-record",
    )
    client = LLMClient(
        settings=settings,
        cache=LLMCache(root_dir=settings.cadrumo_llm_cache_dir),
        usage_recorder=UsageRecorder(root_dir=settings.cadrumo_llm_usage_dir),
    )
    return TextInvoiceFieldExtractor(client=client, operation=operation, settings=settings, public_corpus=public_corpus)


def _extract(
    transcription: DocumentTranscription, tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> tuple[RecordingModelRuns, InvoiceDraft]:
    extractor = _extractor(tmp_path, operation=operation)
    with serving_agent(replies=(_REPLY,), lane=ON_HOST_LANE) as service:
        draft = extractor.extract(transcription=transcription)
    return service, draft


def test_the_stage_takes_the_transcription_artefact_and_reads_its_text(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """The document text the model receives is the transcription's own."""
    transcription = _transcription(FieldOrigin.TEXT_LAYER)
    service, _draft = _extract(transcription, tmp_path, operation=operation)

    ((_, body),) = service.runs
    assert transcription.text in body.prompt


@pytest.mark.parametrize("origin", [FieldOrigin.TEXT_LAYER, FieldOrigin.VISION])
def test_every_envelope_carries_the_transcribers_origin_not_a_hardcoded_one(
    origin: FieldOrigin, tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """Both acquisition origins must survive to the envelope, unchanged.

    Parametrised across BOTH members rather than asserting one: a reader that
    hardcoded either value would pass a single-origin case, and the whole point
    of reading the origin off the artefact is that the two stay distinguishable.

    Mutation that must trip this: replace ``transcription.transcriber.origin``
    with a literal ``FieldOrigin.TEXT_LAYER`` in ``TextInvoiceFieldExtractor``.
    """
    _service, draft = _extract(_transcription(origin), tmp_path, operation=operation)

    envelopes = draft.provenance
    assert envelopes, "the fixture must produce envelopes, or this passes vacuously"
    assert {envelope.origin for envelope in envelopes} == {origin}


def test_the_read_names_the_text_extraction_role_and_carries_no_images(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """The agent resolves the role's lane and model; a rasterised text document is a defect."""
    service, _draft = _extract(_transcription(FieldOrigin.TEXT_LAYER), tmp_path, operation=operation)

    assert service.lookups == [ModelRole.TEXT_EXTRACTION]
    ((header, body),) = service.runs
    assert header.role == ModelRole.TEXT_EXTRACTION.value
    assert header.consent is None, "a lane that stays on this computer carries no consent"
    assert body.attachments == ()


def test_the_document_is_evidence_unless_the_corpus_is_named(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """Naming the public corpus is the deliberate act; forgetting gets the consent gate.

    On a lane that reads off the host, the unconsented taxpayer document is
    refused before anything is sent. The named corpus passes the client's gate
    and reaches the service, which then refuses the consent-less run itself.
    """
    transcription = _transcription(FieldOrigin.TEXT_LAYER)
    with serving_agent(replies=(_REPLY,), lane=DEFAULT_LANE) as evidence, pytest.raises(LLMConsentError):
        _extractor(tmp_path / "evidence", operation=operation).extract(transcription=transcription)
    assert evidence.runs == []

    with serving_agent(replies=(_REPLY,), lane=DEFAULT_LANE) as corpus, pytest.raises(LLMConsentError):
        _extractor(tmp_path / "corpus", operation=operation, public_corpus=True).extract(transcription=transcription)
    ((header, _),) = corpus.runs
    assert header.consent is None


def test_the_role_evidence_the_model_returned_reaches_the_draft_envelope(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    """Stage two carries the role-evidence claim through, unchecked and intact.

    The check belongs to the grounding stage, which holds the document. What
    this stage must not do is drop the claim -- an identity that arrives with no
    role evidence does not resolve, so losing it here would silently disable
    counterparty auto-fill with nothing reporting a failure.
    """
    _service, draft = _extract(_transcription(FieldOrigin.TEXT_LAYER), tmp_path, operation=operation)

    supplier = next(e for e in draft.provenance if e.field == "supplier_tax_id")
    assert supplier.role_evidence == "Proveedor:"
