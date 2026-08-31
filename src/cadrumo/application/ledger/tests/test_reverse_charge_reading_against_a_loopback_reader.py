"""The reverse-charge classification pair, read end to end off real documents.

Two documents that differ in one printed line, read through a real loopback
endpoint speaking the runtime's wire shape. **No model is loaded and no
inference runs** -- the reply is authored by the test, exactly as a reply from a
real runtime would arrive, and everything downstream of the socket is production
code: the real provider client, the real router, the real grounding stage.

**Both fixtures are real documents rather than authored drafts.** The mention
and the repercutido line are printed on the page and come back through the
transcription, so the reply reports what its document actually says. A pair of
hand-built drafts would exercise the finding while proving nothing about
whether a document reaches it -- a recurring failure shape in this codebase,
where a guard is correct in logic and unreachable in wiring because its tests
supplied the derived value directly.

**Why reverse charge specifically.** A domestic reverse charge prints no cuota
and *obliges the recipient to self-assess* output IVA, so mis-honouring it
OVER-declares rather than under-declares. That is the direction none of this
apparatus watches, and it is why the category is deliberately excluded from the
establishment-premise relief set while the two relieving categories are in it.
The exclusion is asserted here rather than left as a comment.

**The contradiction case asserts the OUTCOME, not a category.** The legend axis
withholds the category precisely on a contradiction, and its only production
consumer reads the outcome and never the derived value -- deliberately, so a
caller cannot use the value while ignoring the conflict. Asserting a category
there would assert something no consumer reads.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from decimal import Decimal
from http import HTTPStatus
from pathlib import Path
from queue import Queue
from typing import ClassVar, override

import pytest

from ....core.draft_discrepancy import DraftDiscrepancyKind
from ....core.field_origin import FieldOrigin
from ....core.config import load_settings, override_settings
from ....domain.iva.legend_derivation import LegendDerivationOutcome, derive_category_from_regime_legend
from ....domain.iva.schema import IvaCategory
from ....tests.loopback_llm import (
    SilentLoopbackHandler,
    ollama_chat_reply,
    read_json_body,
    serving_loopback,
    write_json_response,
)
from ..classification_assembly import _RELIEF_ON_AN_ESTABLISHMENT_PREMISE
from ..evidence_draft import _read_transcription_semantically
from ..evidence_input import EvidenceInput
from ..evidence_textlayer import transcribe_text_layer
from ..regime_contradiction import draft_prints_a_repercutido_line, regime_contradiction_finding
from ._loopback_reader import READING_RUNTIME_MODEL

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CORPUS = Path(__file__).parent / "_evidence_corpus"
#: Prints the art. 84.Uno.2 mention and charges no output IVA -- the lawful
#: presentation of a domestic reverse charge.
_LAWFUL = _CORPUS / "es_reverse_charge_legend_no_repercutido.pdf"
#: The same invoice contradicting itself: the mention beside a 21 % line.
_CONTRADICTORY = _CORPUS / "es_reverse_charge_legend_beside_repercutido.pdf"

#: The mention as both documents print it, copied from the page rather than
#: composed here, so the legend table is matched against real printed text.
_PRINTED_MENTION = "Inversión del sujeto pasivo (art. 84.Uno.2º LIVA)"

_BASE_REPLY: dict[str, str | None] = {
    "supplier_tax_id": "B1234567X",
    "invoice_number": "RC-2026-0001",
    "invoice_date": "2026-06-11",
    "taxable_base": "766,30",
    "regime_legend": _PRINTED_MENTION,
    "currency": "EUR",
}

#: What the lawful document says: the mention, and no tax charged.
_LAWFUL_REPLY = _BASE_REPLY | {"iva_rate": "0", "iva_amount": "0", "grand_total": "766,30"}

#: What the contradictory document says: the same mention, and 21 % charged.
_CONTRADICTORY_REPLY = _BASE_REPLY | {
    "iva_rate": "21",
    "iva_amount": "160,92",
    "grand_total": "927,22",
}

#: A retención withheld on the lawful document, to prove the two response slots
#: survive the wire and the grounding stage rather than being dropped between
#: the reader's reply and the draft.
_RETENCION_REPLY = _LAWFUL_REPLY | {
    "retencion_rate": "15",
    "retencion_amount": "114,95",
    "grand_total": "651,35",
}


class _LoopbackRequestHandler(SilentLoopbackHandler):
    """A real endpoint speaking the runtime's ``/api/chat`` shape."""

    reply: ClassVar[str]
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
def serve(secure_objects: object) -> Iterator[object]:
    """Serve a real reader on a loopback port; yield a callable taking the reply.

    Depends on ``secure_objects`` for the real bucket runtime, because the
    reading path writes run telemetry through the profile-bound encrypted
    repository. Taking the shared fixture keeps this a real storage runtime
    rather than disabling the telemetry write to make the test pass.
    """
    requests: Queue[dict[str, object]] = Queue()
    _LoopbackRequestHandler.requests = requests
    with serving_loopback(_LoopbackRequestHandler, path="/api/chat") as url:

        def read(document: Path, reply: dict[str, str | None]):
            _LoopbackRequestHandler.reply = json.dumps(reply)
            payload = document.read_bytes()
            evidence = EvidenceInput(
                mime_type="application/pdf",
                data=payload,
                content_sha256=hashlib.sha256(payload).hexdigest(),
                attachment_id="c" * 64,
            )
            with override_settings(cadrumo_llm_ollama_chat_url=url):
                # ``settings`` is required rather than resolved internally, so
                # the override reaches the read instead of being silently
                # bypassed.
                return _read_transcription_semantically(
                    evidence,
                    transcribe_text_layer(evidence),
                    settings=load_settings(),
                )

        yield read


def test_both_documents_print_the_mention_the_legend_table_matches() -> None:
    """The premise both cases rest on, taken from the pages rather than assumed.

    If the printed wording drifted from what the legend table matches, every
    assertion below would still pass -- the derivation would simply return
    ABSENT and no contradiction could ever fire -- so the pair would go quiet in
    the direction it exists to catch.
    """
    for document in (_LAWFUL, _CONTRADICTORY):
        text = transcribe_text_layer(
            EvidenceInput(
                mime_type="application/pdf",
                data=document.read_bytes(),
                content_sha256=hashlib.sha256(document.read_bytes()).hexdigest(),
                attachment_id="c" * 64,
            )
        ).text
        assert _PRINTED_MENTION in text, f"{document.name} no longer prints the mention this pair reads"

    derivation = derive_category_from_regime_legend(
        printed_legend=_PRINTED_MENTION,
        has_repercutido_line=False,
    )
    assert derivation.outcome is LegendDerivationOutcome.DERIVED, (
        "the legend table no longer matches the phrase these documents print"
    )


def test_a_mention_with_no_repercutido_line_derives_the_reverse_charge(serve) -> None:
    """The lawful presentation: the mention stands, no tax is charged, the category derives."""
    draft = serve(_LAWFUL, _LAWFUL_REPLY)

    assert draft.regime_legend == _PRINTED_MENTION
    assert not draft_prints_a_repercutido_line(draft), (
        "a zero rate and a zero cuota are the ordinary presentation of a reverse charge and must "
        "not read as tax charged, or the finding fires on the very documents it exists to respect"
    )
    derivation = derive_category_from_regime_legend(
        printed_legend=draft.regime_legend,
        has_repercutido_line=draft_prints_a_repercutido_line(draft),
    )
    assert derivation.outcome is LegendDerivationOutcome.DERIVED
    assert derivation.category is IvaCategory.DOMESTIC_REVERSE_CHARGE
    assert regime_contradiction_finding(draft) is None


def test_the_reverse_charge_is_not_relieved_on_an_establishment_premise() -> None:
    """The doctrinal distinction, asserted rather than left incidental.

    A reverse charge carries no cuota, which makes it look like the relieving
    categories, and it is deliberately NOT in the relief set: it obliges the
    recipient to self-assess output IVA, so mis-honouring it OVER-declares.
    The relief set exists for the under-declaring direction, where honouring a
    claim for a party nobody could place relieves a supply that was not
    relieved. Admitting reverse charge would withhold a treatment on a premise
    that does not apply to it.
    """
    assert IvaCategory.DOMESTIC_REVERSE_CHARGE not in _RELIEF_ON_AN_ESTABLISHMENT_PREMISE
    # The membership assertion alone would pass against an empty set, which is
    # the shape that proves nothing about the distinction being drawn.
    assert {
        IvaCategory.INTRA_COMMUNITY_SUPPLY,
        IvaCategory.EXPORT_THIRD_COUNTRY_ZERO_RATED,
    } == _RELIEF_ON_AN_ESTABLISHMENT_PREMISE


def test_a_mention_beside_a_repercutido_line_raises_a_blocking_finding(serve) -> None:
    """The contradiction: the document cannot be right on both halves.

    Asserted on the outcome and the finding, never on a category -- the axis
    withholds the category here, and its only production consumer reads the
    outcome, so a category assertion would pin a value nothing reads.
    """
    draft = serve(_CONTRADICTORY, _CONTRADICTORY_REPLY)

    assert draft.regime_legend == _PRINTED_MENTION
    assert draft_prints_a_repercutido_line(draft)
    derivation = derive_category_from_regime_legend(
        printed_legend=draft.regime_legend,
        has_repercutido_line=draft_prints_a_repercutido_line(draft),
    )
    assert derivation.outcome is LegendDerivationOutcome.CONTRADICTED
    assert derivation.category is None, "the category must be withheld, not guessed, on a contradiction"

    finding = regime_contradiction_finding(draft)
    assert finding is not None
    assert finding.kind is DraftDiscrepancyKind.REGIME_CONTRADICTED
    # The field names the mention rather than the category, because the category
    # was never established and would send an operator to a value that does not
    # exist. The mention is the half they can look at on the page.
    assert finding.field == "regime_legend"


def test_the_retencion_slots_survive_the_wire_to_the_draft(serve) -> None:
    """The regression: both response slots reach the draft as grounded figures.

    A withheld retención is money the payer owes AEAT rather than the supplier.
    Losing either slot between the reader's reply and the draft leaves the
    record stating a payment that was never made in full, and nothing downstream
    can recover the figure once it is gone.
    """
    draft = serve(_LAWFUL, _RETENCION_REPLY)

    assert draft.retencion_rate == Decimal("15")
    assert draft.retencion_amount == Decimal("114.95")

    # Provenance must survive with them. A figure that reached the draft with no
    # provenance entry is not recoverable as evidence later, and the two slots
    # are the ones most easily dropped: nothing downstream recomputes them.
    entries = {entry.field: entry for entry in draft.provenance}
    for field in ("retencion_rate", "retencion_amount"):
        assert field in entries, f"{field} reached the draft carrying no provenance entry"
        assert entries[field].origin is FieldOrigin.TEXT_LAYER
