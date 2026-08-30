"""Stage two reads the stage-one artefact, on-host, under the role-named model.

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
* The provider is pinned LOCAL at the call site rather than inherited, because
  the shipped default is a cloud vendor.
* The model comes from the role-named text-extraction setting, not the vision
  one -- the two roles are sized independently and must stay independently
  resolvable, since the text roles have to be satisfiable on a machine that can
  host no vision model at all.

No model runs here. The transport is asserted through an injected client,
because running local inference has crashed this development host.
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import TYPE_CHECKING, override

import pytest

from ...application.ledger.document_transcription import DocumentTranscription, TranscriberIdentity
from ...core import LOCAL_TRANSPORT_LABEL, FieldOrigin
from ...core.config import load_settings
from ...core.time import now
from ..client import LLMClient
from ..evidence_draft_text import TextInvoiceFieldExtractor
from ..models import LLMProvider, LLMResponse

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

if TYPE_CHECKING:
    from ...application.ledger.evidence_draft import InvoiceDraft
    from ..models import LLMRequest

_REPLY = json.dumps(
    {
        "supplier_tax_id": "B12345674",
        "supplier_tax_id_anchor": "B12345674",
        "supplier_tax_id_role_evidence": "Proveedor:",
        "taxable_base": "100,00",
        "taxable_base_anchor": "100,00 EUR",
    },
)


class _CapturingClient(LLMClient):
    """Captures the request the reader builds. No transport, no inference.

    Subclasses the client the reader's ``client`` parameter declares, so it is
    substitutable for the real one rather than merely shaped like it -- the
    same form the sibling reader tests use.
    """

    def __init__(self) -> None:
        super().__init__()
        self.requests: list[LLMRequest] = []

    @override
    async def complete(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        return LLMResponse(
            text=_REPLY,
            provider=LLMProvider.LOCAL,
            model="stub",
            input_tokens=0,
            output_tokens=0,
            cost_estimate_usd=Decimal("0"),
            cache_hit=False,
            created_at=now(),
            request_id="wiring",
        )


def _transcription(origin: FieldOrigin, *, name: str = "pdfplumber") -> DocumentTranscription:
    return DocumentTranscription(
        text="FACTURA\nProveedor: EJEMPLO SL B12345674\nBase imponible 100,00 EUR",
        page_count=1,
        source_content_sha256="e" * 64,
        transcriber=TranscriberIdentity(transport=LOCAL_TRANSPORT_LABEL, origin=origin, name=name, revision="wiring"),
    )


def _extract(transcription: DocumentTranscription) -> tuple[_CapturingClient, InvoiceDraft]:
    client = _CapturingClient()
    extractor = TextInvoiceFieldExtractor(model="stub-text", client=client, settings=load_settings())
    return client, extractor.extract(transcription=transcription)


def test_the_stage_takes_the_transcription_artefact_and_reads_its_text() -> None:
    """The document text the model receives is the transcription's own."""
    transcription = _transcription(FieldOrigin.TEXT_LAYER)
    client, _draft = _extract(transcription)

    assert len(client.requests) == 1
    assert transcription.text in client.requests[0].prompt


@pytest.mark.parametrize("origin", [FieldOrigin.TEXT_LAYER, FieldOrigin.VISION])
def test_every_envelope_carries_the_transcribers_origin_not_a_hardcoded_one(origin: FieldOrigin) -> None:
    """Both acquisition origins must survive to the envelope, unchanged.

    Parametrised across BOTH members rather than asserting one: a reader that
    hardcoded either value would pass a single-origin case, and the whole point
    of reading the origin off the artefact is that the two stay distinguishable.

    Mutation that must trip this: replace ``transcription.transcriber.origin``
    with a literal ``FieldOrigin.TEXT_LAYER`` in ``TextInvoiceFieldExtractor``.
    """
    _client, draft = _extract(_transcription(origin))

    envelopes = draft.provenance
    assert envelopes, "the fixture must produce envelopes, or this passes vacuously"
    assert {envelope.origin for envelope in envelopes} == {origin}


def test_the_request_pins_local_and_carries_no_images() -> None:
    """On-host by expression, and text-only: a rasterised text document is a defect."""
    client, _draft = _extract(_transcription(FieldOrigin.TEXT_LAYER))
    request = client.requests[0]

    assert request.provider_override is LLMProvider.LOCAL
    assert not request.images


def test_the_request_is_marked_evidence_derived_unless_the_corpus_is_named() -> None:
    """Naming the public corpus is the deliberate act; forgetting gets the gate.

    The default direction is fail-closed, so a caller that says nothing about
    where its pages came from is treated as holding a taxpayer's document.
    """
    client = _CapturingClient()
    TextInvoiceFieldExtractor(model="stub-text", client=client, settings=load_settings()).extract(
        transcription=_transcription(FieldOrigin.TEXT_LAYER),
    )
    assert client.requests[0].evidence_derived is True

    corpus_client = _CapturingClient()
    TextInvoiceFieldExtractor(
        model="stub-text",
        client=corpus_client,
        settings=load_settings(),
        public_corpus=True,
    ).extract(transcription=_transcription(FieldOrigin.TEXT_LAYER))
    assert corpus_client.requests[0].evidence_derived is False


def test_the_default_local_model_is_the_text_extraction_role_not_the_vision_one() -> None:
    """The two local roles resolve independently, and this stage takes the text one.

    They are separate because the capability bars differ in BOTH directions:
    only vision transcription needs image input, and the text roles must be
    satisfiable on a machine that cannot host a vision model at all. A stage
    that reached for the vision setting would make text extraction impossible
    on exactly those machines.
    """
    settings = load_settings()
    client = _CapturingClient()
    TextInvoiceFieldExtractor(client=client, settings=settings).extract(
        transcription=_transcription(FieldOrigin.TEXT_LAYER),
    )

    assert client.requests[0].model_override == settings.cadrumo_llm_ollama_text_model
    assert client.requests[0].model_override != settings.cadrumo_llm_ollama_vision_model


def test_the_role_evidence_the_model_returned_reaches_the_draft_envelope() -> None:
    """Stage two carries the role-evidence claim through, unchecked and intact.

    The check belongs to the grounding stage, which holds the document. What
    this stage must not do is drop the claim -- an identity that arrives with no
    role evidence does not resolve, so losing it here would silently disable
    counterparty auto-fill with nothing reporting a failure.
    """
    _client, draft = _extract(_transcription(FieldOrigin.TEXT_LAYER))

    supplier = next(e for e in draft.provenance if e.field == "supplier_tax_id")
    assert supplier.role_evidence == "Proveedor:"
