"""The wired reading path, end to end, against a real loopback reader.

Stands up a real :class:`~http.server.ThreadingHTTPServer` on a loopback port
speaking the runtime's ``/api/chat`` wire shape, and points the settings at it.
Real HTTP, the real provider client, the real router, the real grounding stage.
**No model is loaded and no inference runs** -- the reply is authored by the
test, which is what makes this runnable on a machine with no accelerator and in
CI.

This is not a mock and not a patch: nothing in the code under test is
substituted. The REPLY is supplied, exactly as a reply from a real runtime would
be, and everything downstream of the socket is production code. The
bind-thread-shutdown plumbing and the wire envelope come from the shared
loopback home, so there is one loopback shape in the tree; only the
request-recording behaviour is declared here.

What it exists to prove is the thing no unit suite could: that a document
entering `extract_invoice_draft_from_evidence` comes out the other side with
its provenance CHECKED. Every stage was individually gated long before anything
reached them, and the campaign's principal risk was a well-tested library that
was not a pipeline.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from http import HTTPStatus
from pathlib import Path
from queue import Queue
from typing import ClassVar, override

import pytest

from ....core import DraftDiscrepancyKind, FieldGroundingOutcome
from ....core.config import load_settings, override_settings
from ....tests.loopback_llm import (
    SilentLoopbackHandler,
    ollama_chat_reply,
    read_json_body,
    serving_loopback,
    write_json_response,
)
from ..evidence_draft import _read_transcription_semantically
from ..evidence_input import EvidenceInput
from ..evidence_textlayer import transcribe_text_layer
from ._loopback_reader import READING_RUNTIME_MODEL

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CORPUS = Path(__file__).parent / "_evidence_corpus"
_CONTROL = _CORPUS / "com_2026_0005_layout_minimal.pdf"

#: The reply the stub returns. Authored from the control document's OWN printed
#: forms, so the anchors are real and the upgrade under test is genuine -- except
#: `iva_amount`, whose anchor is deliberately absent from the document so the
#: fabrication case is exercised on the same pass.
_READER_REPLY: dict[str, str | None] = {
    "supplier_tax_id": "B1234567X",
    "supplier_tax_id_anchor": "B1234567X",
    "invoice_number": "SIN-NUMERO",
    "invoice_number_anchor": "SIN-NUMERO",
    "invoice_date": "2026-06-11",
    "invoice_date_anchor": "2026-06-11",
    "taxable_base": "766,30",
    "taxable_base_anchor": "766,30",
    "iva_rate": "21",
    "iva_rate_anchor": "21%",
    "iva_amount": "9999,99",
    "iva_amount_anchor": "9.999,99",
    "grand_total": "890,00",
    "grand_total_anchor": "890,00",
    "currency": "EUR",
    "currency_anchor": "EUR",
}


class _LoopbackRequestHandler(SilentLoopbackHandler):
    """A real local endpoint speaking the runtime's ``/api/chat`` wire shape."""

    reply: ClassVar[str] = ""
    requests: ClassVar[Queue[dict[str, object]]]

    @override
    def do_POST(self) -> None:
        self.requests.put(dict(read_json_body(self)))
        write_json_response(
            self,
            ollama_chat_reply(
                self.reply,
                model=READING_RUNTIME_MODEL,
                prompt_eval_count=100,
                eval_count=50,
            ),
            status=HTTPStatus.OK,
        )


@pytest.fixture
def reader(secure_objects: object) -> Iterator[tuple[str, Queue[dict[str, object]]]]:
    """Serve a real reader endpoint on a loopback port; yield its URL and requests.

    Depends on ``secure_objects`` for the real bucket runtime: the reading path
    writes run telemetry through the profile-bound encrypted repository, so a
    read with no active bucket fails before the transport is reached. Taking the
    shared fixture keeps this a REAL storage runtime rather than disabling the
    telemetry write to make the test pass.
    """
    requests: Queue[dict[str, object]] = Queue()
    _LoopbackRequestHandler.requests = requests
    _LoopbackRequestHandler.reply = json.dumps(_READER_REPLY)
    with serving_loopback(_LoopbackRequestHandler, path="/api/chat") as chat_url:
        yield (chat_url, requests)


def _control_evidence() -> EvidenceInput:
    payload = _CONTROL.read_bytes()
    return EvidenceInput(
        mime_type="application/pdf",
        data=payload,
        content_sha256=hashlib.sha256(payload).hexdigest(),
        attachment_id="b" * 64,
    )


def _read_through_the_wired_path(chat_url: str):
    evidence = _control_evidence()
    with override_settings(cadrumo_llm_ollama_chat_url=chat_url):
        # ``settings`` is required rather than resolved internally, so the
        # override above reaches the read instead of being silently bypassed.
        return _read_transcription_semantically(
            evidence,
            transcribe_text_layer(evidence),
            settings=load_settings(),
        )


def test_the_read_actually_reaches_the_loopback_endpoint(
    reader: tuple[str, Queue[dict[str, object]]],
) -> None:
    """Anchor: if the request never arrives, every assertion below is vacuous."""
    chat_url, requests = reader

    _read_through_the_wired_path(chat_url)

    sent = requests.get(timeout=5)
    assert sent["stream"] is False
    assert isinstance(sent["messages"], list)


def test_the_transcription_not_the_raw_bytes_is_what_the_reader_receives(
    reader: tuple[str, Queue[dict[str, object]]],
) -> None:
    """The reader is fed the document's TEXT, which is what makes the anchor check external.

    If the router ever fed the reader something it also produced, the anchor
    check would be verifying a model against itself.
    """
    chat_url, requests = reader

    _read_through_the_wired_path(chat_url)

    sent = requests.get(timeout=5)
    messages = sent["messages"]
    assert isinstance(messages, list), "the wired request carried no message list"
    prompt = "".join(str(message.get("content", "")) for message in messages if isinstance(message, dict))
    assert "Reformas Delta SL" in prompt, "the document's own text did not reach the reader"
    assert "766,30" in prompt


def test_a_real_anchor_is_upgraded_to_anchored_on_the_wired_path(
    reader: tuple[str, Queue[dict[str, object]]],
) -> None:
    """The upgrade, proven end to end rather than on a hand-built draft.

    The reader emits every envelope ``UNANCHORED``; the grounding stage holds the
    transcription and checks each claim. This is the single assertion that the
    campaign's stages are a pipeline and not a library.
    """
    chat_url, _ = reader

    draft = _read_through_the_wired_path(chat_url)

    by_field = {envelope.field: envelope for envelope in draft.provenance}
    assert by_field["taxable_base"].grounding is FieldGroundingOutcome.ANCHORED
    assert by_field["grand_total"].grounding is FieldGroundingOutcome.ANCHORED


def test_a_percentage_anchor_survives_the_wired_path(
    reader: tuple[str, Queue[dict[str, object]]],
) -> None:
    """`21%` anchoring the value `21` is the most common field in the corpus."""
    chat_url, _ = reader

    draft = _read_through_the_wired_path(chat_url)

    rate = next(e for e in draft.provenance if e.field == "iva_rate")
    assert rate.grounding is FieldGroundingOutcome.ANCHORED
    assert rate.anchor == "21%"


def test_a_fabricated_anchor_is_rejected_on_the_wired_path(
    reader: tuple[str, Queue[dict[str, object]]],
) -> None:
    """Anti-fabrication where it matters: a figure the document does not print.

    The reply claims `9.999,99` for the cuota. It is well-formed, plausible, and
    absent from the page. The wired path must not let it ground, and must strip
    the anchor it could not verify.
    """
    chat_url, _ = reader

    draft = _read_through_the_wired_path(chat_url)

    fabricated = next(e for e in draft.provenance if e.field == "iva_amount")
    assert fabricated.grounding is FieldGroundingOutcome.UNANCHORED
    assert fabricated.anchor is None


def test_the_closure_finding_reaches_the_draft_on_the_wired_path(
    reader: tuple[str, Queue[dict[str, object]]],
) -> None:
    """The second leg runs end to end: 890,00 against a base and cuota that miss it."""
    chat_url, _ = reader

    draft = _read_through_the_wired_path(chat_url)

    kinds = {finding.kind for finding in draft.discrepancies}
    assert DraftDiscrepancyKind.ARITHMETIC_CLOSURE in kinds


def test_the_transcription_address_is_stamped_on_the_wired_path(
    reader: tuple[str, Queue[dict[str, object]]],
) -> None:
    """The draft is tied to the exact artefact it was read from."""
    chat_url, _ = reader
    evidence = _control_evidence()

    draft = _read_through_the_wired_path(chat_url)

    assert draft.transcription_sha256 == transcribe_text_layer(evidence).source_content_sha256


def test_a_clean_document_extracts_without_findings_on_the_wired_path(
    reader: tuple[str, Queue[dict[str, object]]],
) -> None:
    """POSITIVE CONTROL for the whole suite, and for the refusal cases elsewhere.

    Without a document that reads cleanly through the same wired path, "refuses
    without a reader" and "rejects a fabricated anchor" are both satisfiable by a
    path that never produces a usable draft at all.

    The reply here states figures that DO close (766,30 + 160,92 = 927,22) and
    anchors that are all really printed, so a clean read must yield no
    arithmetic-closure finding.
    """
    chat_url, _ = reader
    _LoopbackRequestHandler.reply = json.dumps(
        {
            "taxable_base": "766,30",
            "taxable_base_anchor": "766,30",
            "iva_rate": "21",
            "iva_rate_anchor": "21%",
            "iva_amount": "160,92",
            "iva_amount_anchor": "160,92",
            "grand_total": "927,22",
            "grand_total_anchor": "890,00",
        },
    )

    draft = _read_through_the_wired_path(chat_url)

    assert not [f for f in draft.discrepancies if f.kind is DraftDiscrepancyKind.ARITHMETIC_CLOSURE]
    assert all(
        envelope.grounding is FieldGroundingOutcome.ANCHORED
        for envelope in draft.provenance
        if envelope.field in {"taxable_base", "iva_rate", "iva_amount"}
    )


def test_a_short_figure_does_not_anchor_inside_a_longer_one_on_the_wired_path(
    reader: tuple[str, Queue[dict[str, object]]],
) -> None:
    """The anchor boundary, exercised END TO END rather than only in its unit suite.

    The control document prints ``TOTAL 890,00``. A reply claiming a cuota of
    ``0,00`` therefore has an anchor that occurs as a SUBSTRING of a real printed
    figure -- which is exactly how an injected zero total grounded before the
    boundary rule landed, and needs no cleverness because most invoices carry
    some amount ending in ``,00``.

    Added after a mutation showed the rest of this suite could not catch it:
    every other anchor here is a whole printed token, so reverting to substring
    matching left all eight cases green. A suite that only exercises the easy
    shape cannot see the defect the hard shape produces.
    """
    chat_url, _ = reader
    _LoopbackRequestHandler.reply = json.dumps(
        {
            "taxable_base": "766,30",
            "taxable_base_anchor": "766,30",
            "iva_amount": "0",
            "iva_amount_anchor": "0,00",
        },
    )

    draft = _read_through_the_wired_path(chat_url)

    fragment = next(e for e in draft.provenance if e.field == "iva_amount")
    assert fragment.grounding is FieldGroundingOutcome.UNANCHORED, (
        "'0,00' anchored inside the document's printed '890,00'"
    )
    assert fragment.anchor is None
