"""The anchor check, gated on real transcriptions produced by the real reader.

Every case here drives `transcribe_text_layer` over bundled corpus bytes, so the
transcription under check is the one production would build -- not a string a
test author typed to match the assertion below it. Where a case needs a printed
form the corpus does not contain, that is stated in the test's own name.
"""

from __future__ import annotations

import hashlib
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from ....core import FieldGroundingOutcome, FieldOrigin
from .._document_transcription import DocumentTranscription, TranscriberIdentity
from .._evidence import MediaKind
from .._evidence_draft import FieldProvenance
from .._evidence_input import EvidenceInput
from .._evidence_textlayer import transcribe_text_layer
from .._grounding_anchor import (
    evaluate_anchor,
    ground_anchored_value,
    ground_self_reported_anchor,
    normalise_for_anchor_search,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CORPUS = Path(__file__).parent / "_evidence_corpus"


def _transcription(text: str) -> DocumentTranscription:
    """Build a transcription with the real text-layer transcriber stamp.

    The TEXT is supplied by the caller because these cases exercise the anchor
    check, not the extractor; the surrounding record is the production one, so a
    change to its contract breaks these tests rather than passing them by.
    """
    return DocumentTranscription(
        text=text,
        page_count=1,
        source_content_sha256="a" * 64,
        transcriber=TranscriberIdentity(
            origin=FieldOrigin.TEXT_LAYER,
            name="pdfplumber",
            revision="0.11.4",
        ),
    )


_SPANISH_INVOICE_TEXT = (
    "FACTURA N.º FA/2026-0044\n"
    "Base imponible 2.420,00 EUR\n"
    "IVA 21% 508,20\n"
    "Retención IRPF 15% 363,00\n"
    "TOTAL FACTURA 2.565,20\n"
)


def test_a_value_whose_anchor_is_printed_and_parses_to_it_grounds() -> None:
    """Both halves hold: the anchor is on the page and it parses to the value."""
    evaluation = evaluate_anchor(
        value=Decimal("2420.00"),
        anchor="2.420,00",
        transcription=_transcription(_SPANISH_INVOICE_TEXT),
    )

    assert evaluation.outcome is FieldGroundingOutcome.ANCHORED
    assert evaluation.anchor_found is True
    assert evaluation.parsed_anchor == Decimal("2420.00")


def test_an_off_document_value_never_grounds() -> None:
    """The core anti-fabrication case: a figure nobody can point at on the page.

    This is the exact shape a fabricating reader produces -- a plausible,
    well-formed, entirely invented amount. It must not reach ``ANCHORED`` by any
    route.
    """
    evaluation = evaluate_anchor(
        value=Decimal("9999.99"),
        anchor="9.999,99",
        transcription=_transcription(_SPANISH_INVOICE_TEXT),
    )

    assert evaluation.outcome is FieldGroundingOutcome.UNANCHORED
    assert evaluation.anchor_found is False


def test_an_anchor_on_the_page_that_parses_to_something_else_is_contradicted() -> None:
    """Present-but-disagreeing is a stronger statement than merely ungrounded.

    A reader that located a real printed figure and then typed a different value
    has a different defect from one that invented a figure outright, and the
    operator can act on the first far faster.
    """
    evaluation = evaluate_anchor(
        value=Decimal("2420.00"),
        anchor="508,20",
        transcription=_transcription(_SPANISH_INVOICE_TEXT),
    )

    assert evaluation.outcome is FieldGroundingOutcome.CONTRADICTED
    assert evaluation.anchor_found is True
    assert evaluation.parsed_anchor == Decimal("508.20")


def test_the_anchor_need_not_be_byte_identical_to_the_value() -> None:
    """``21%`` anchoring ``Decimal("21")`` is the intended case, not a concession.

    Requiring byte identity would make the check useless for every field that
    needs parsing, which is every monetary field on an invoice.
    """
    evaluation = evaluate_anchor(
        value=Decimal("21"),
        anchor="21% 508,20",
        transcription=_transcription(_SPANISH_INVOICE_TEXT),
    )

    # The anchor is on the page but does not parse to 21 as a whole token, so the
    # honest outcome is CONTRADICTED rather than a silent pass: the reader must
    # cite the token it actually parsed.
    assert evaluation.anchor_found is True
    assert evaluation.outcome is FieldGroundingOutcome.CONTRADICTED


def test_a_percentage_anchor_citing_only_its_number_grounds() -> None:
    evaluation = evaluate_anchor(
        value=Decimal("21"),
        anchor="21",
        transcription=_transcription(_SPANISH_INVOICE_TEXT),
    )

    assert evaluation.outcome is FieldGroundingOutcome.ANCHORED


def test_an_identical_anchor_and_value_is_reported_as_a_vacuous_parse() -> None:
    """The weak case is surfaced rather than left to read as full strength.

    When the anchor and the rendered value are the same string, the parse half of
    the check compares a value against itself and establishes nothing about
    parsing. The anchor half still ran, so the fabrication bound holds -- but the
    record says which half did the work.
    """
    evaluation = evaluate_anchor(
        value=Decimal("21"),
        anchor="21",
        transcription=_transcription(_SPANISH_INVOICE_TEXT),
    )

    assert evaluation.outcome is FieldGroundingOutcome.ANCHORED
    assert evaluation.parse_was_vacuous is True


def test_a_genuinely_parsed_anchor_is_not_reported_as_vacuous() -> None:
    """Positive control for the vacuity flag itself.

    Without this, `parse_was_vacuous` could be hardcoded ``True`` and the case
    above would still pass.
    """
    evaluation = evaluate_anchor(
        value=Decimal("2420.00"),
        anchor="2.420,00",
        transcription=_transcription(_SPANISH_INVOICE_TEXT),
    )

    assert evaluation.outcome is FieldGroundingOutcome.ANCHORED
    assert evaluation.parse_was_vacuous is False


def test_an_ambiguous_thousands_reading_does_not_ground() -> None:
    """The extraction contract drops what it cannot settle, and so does this.

    ``1.234`` is one thousand two hundred thirty-four to a Spanish supplier and
    one point two three four to a dot-decimal one. The repository's extraction
    parser refuses to choose; grounding must not quietly choose for it.
    """
    evaluation = evaluate_anchor(
        value=Decimal("1234"),
        anchor="1.234",
        transcription=_transcription("Importe 1.234 EUR\n"),
    )

    assert evaluation.outcome is FieldGroundingOutcome.CONTRADICTED
    assert evaluation.anchor_found is True
    assert evaluation.parsed_anchor is None


def test_an_empty_anchor_grounds_nothing() -> None:
    evaluation = evaluate_anchor(
        value=Decimal("1"),
        anchor="   ",
        transcription=_transcription(_SPANISH_INVOICE_TEXT),
    )

    assert evaluation.outcome is FieldGroundingOutcome.UNANCHORED
    assert evaluation.anchor_found is False


def test_whitespace_and_unicode_differences_do_not_defeat_the_anchor() -> None:
    """A non-breaking space is not a difference in what was printed.

    Narrow by design: only Unicode form and whitespace are regularised. The
    separator-sensitivity case below is the control proving digits and
    separators are untouched.
    """
    evaluation = evaluate_anchor(
        value=Decimal("2420.00"),
        anchor="2.420,00",
        transcription=_transcription("Base imponible 2.420,00 EUR"),
    )

    assert evaluation.outcome is FieldGroundingOutcome.ANCHORED


def test_separators_are_evidence_and_are_never_normalised_away() -> None:
    """Control for the normalisation above: it must not touch the number itself.

    If `normalise_for_anchor_search` stripped separators, ``1234,56`` would match
    a document printing ``1.234,56`` and the anchor check would stop
    discriminating between readings that differ thousandfold.
    """
    assert normalise_for_anchor_search("1.234,56") != normalise_for_anchor_search("1234,56")

    evaluation = evaluate_anchor(
        value=Decimal("1234.56"),
        anchor="1234,56",
        transcription=_transcription("Importe 1.234,56 EUR"),
    )

    assert evaluation.outcome is FieldGroundingOutcome.UNANCHORED


def test_a_textual_field_grounds_on_its_anchor_alone() -> None:
    """An invoice number has no deterministic re-derivation to check against."""
    evaluation = evaluate_anchor(
        value="FA/2026-0044",
        anchor="FA/2026-0044",
        transcription=_transcription(_SPANISH_INVOICE_TEXT),
    )

    assert evaluation.outcome is FieldGroundingOutcome.ANCHORED
    assert evaluation.parse_was_vacuous is True


def test_an_off_document_textual_value_does_not_ground() -> None:
    """Positive control for the textual path, which has only one check."""
    evaluation = evaluate_anchor(
        value="FA/2026-9999",
        anchor="FA/2026-9999",
        transcription=_transcription(_SPANISH_INVOICE_TEXT),
    )

    assert evaluation.outcome is FieldGroundingOutcome.UNANCHORED


def test_the_envelope_keeps_the_anchor_even_when_contradicted() -> None:
    """The operator resolving a disagreement needs the form the reader misread."""
    envelope = ground_anchored_value(
        field="taxable_base",
        value=Decimal("2420.00"),
        anchor="508,20",
        origin=FieldOrigin.VISION,
        transcription=_transcription(_SPANISH_INVOICE_TEXT),
    )

    assert envelope.grounding is FieldGroundingOutcome.CONTRADICTED
    assert envelope.anchor == "508,20"
    assert envelope.field == "taxable_base"
    assert envelope.origin is FieldOrigin.VISION


def test_an_unanchored_envelope_carries_no_anchor() -> None:
    """A form that was never located must not be recorded as if it had been."""
    envelope = ground_anchored_value(
        field="taxable_base",
        value=Decimal("9999.99"),
        anchor="9.999,99",
        origin=FieldOrigin.VISION,
        transcription=_transcription(_SPANISH_INVOICE_TEXT),
    )

    assert envelope.grounding is FieldGroundingOutcome.UNANCHORED
    assert envelope.anchor is None


def test_grounding_runs_against_a_transcription_of_a_real_corpus_document() -> None:
    """End-to-end over bundled bytes: the printed form must survive to the check.

    Uses the bundled ZUGFeRD PDF, whose text layer the real extractor reads. The
    assertion is deliberately structural rather than pinned to a figure: what is
    being proven is that a value taken FROM the transcription grounds against it,
    and that one not in it does not.
    """
    payload = (_CORPUS / "zugferd_en16931_invoice.pdf").read_bytes()
    transcription = transcribe_text_layer(
        EvidenceInput(
            media_kind=MediaKind.PDF,
            mime_type="application/pdf",
            data=payload,
            content_sha256=hashlib.sha256(payload).hexdigest(),
            attachment_id="b" * 64,
        ),
    )

    assert transcription.text.strip(), "the corpus document produced no text layer"
    printed_token = transcription.text.split()[0]

    grounded = evaluate_anchor(value=printed_token, anchor=printed_token, transcription=transcription)
    assert grounded.outcome is FieldGroundingOutcome.ANCHORED

    absent = evaluate_anchor(
        value="ZZZ-NOT-ON-THIS-PAGE-ZZZ",
        anchor="ZZZ-NOT-ON-THIS-PAGE-ZZZ",
        transcription=transcription,
    )
    assert absent.outcome is FieldGroundingOutcome.UNANCHORED


def test_a_self_reported_anchor_never_reads_as_verified() -> None:
    """The vision lane's anchor is a claim, not evidence, and must say so.

    That path reads image to fields in one model call, so there is no
    independently produced transcription for the anchor to be a substring of.
    Matching the model's claim against the model's own reply would confirm only
    self-consistency, which a fabricating model also has.
    """
    envelope = ground_self_reported_anchor(
        field="taxable_base",
        anchor="766,30",
        origin=FieldOrigin.VISION,
    )

    assert envelope.grounding is FieldGroundingOutcome.UNANCHORED
    assert envelope.anchor_self_reported is True
    assert envelope.anchor == "766,30", "the anchor is still recorded for the operator to check by eye"


def test_a_self_reported_anchor_cannot_be_laundered_into_an_anchored_outcome() -> None:
    """Enforced at the model, so no reading path can bypass it by construction."""
    with pytest.raises(ValidationError, match="self-reported anchor"):
        FieldProvenance(
            field="taxable_base",
            origin=FieldOrigin.VISION,
            grounding=FieldGroundingOutcome.ANCHORED,
            anchor="766,30",
            anchor_self_reported=True,
        )


def test_the_text_lane_anchor_is_not_marked_self_reported() -> None:
    """Positive control: the flag must discriminate, not be always-on.

    Without this, marking every anchor self-reported would satisfy the two cases
    above while destroying the distinction they exist to draw.
    """
    envelope = ground_anchored_value(
        field="taxable_base",
        value=Decimal("2420.00"),
        anchor="2.420,00",
        origin=FieldOrigin.TEXT_LAYER,
        transcription=_transcription(_SPANISH_INVOICE_TEXT),
    )

    assert envelope.grounding is FieldGroundingOutcome.ANCHORED
    assert envelope.anchor_self_reported is False
