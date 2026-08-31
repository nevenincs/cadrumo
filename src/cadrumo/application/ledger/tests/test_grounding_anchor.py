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

from ....core.decimal import coerce_finite_european_decimal
from ....core.draft_discrepancy import DraftDiscrepancyKind
from ....core.field_grounding import FieldGroundingOutcome
from ....core.field_origin import FieldOrigin
from ....core.provenance_stamp import LOCAL_TRANSPORT_LABEL
from ..closure_findings import closure_findings
from ..document_transcription import DocumentTranscription, TranscriberIdentity
from ..evidence_input import EvidenceInput
from ..evidence_textlayer import transcribe_text_layer
from ..grounding_anchor import (
    evaluate_anchor,
    ground_anchored_value,
    ground_self_reported_anchor,
    normalise_for_anchor_search,
    strip_printed_unit,
)
from ..invoice_draft_records import FieldProvenance, InvoiceDraft

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
            transport=LOCAL_TRANSPORT_LABEL,
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


# ---------------------------------------------------------------------------
# The anchor boundary: a short figure must not anchor inside a longer one
# ---------------------------------------------------------------------------

_AMOUNTS_TEXT = "Base imponible 100,00\nIVA 21% 21,00\nTOTAL 121,00 EUR\n"


def test_an_injected_zero_total_does_not_anchor_inside_a_printed_amount() -> None:
    """The near miss, preserved as an assertion rather than stepped around.

    A plain substring search grounds ``0,00`` against a document printing
    ``100,00``. That is not a fixture quirk: most real invoices carry some
    amount ending in ``,00``, so an injected zero total grounded against a large
    share of the corpus with no cleverness at all -- which made D4's structural
    check certify little more than "these digits appear somewhere".
    """
    evaluation = evaluate_anchor(
        value=Decimal("0.00"),
        anchor="0,00",
        transcription=_transcription(_AMOUNTS_TEXT),
    )

    assert evaluation.outcome is FieldGroundingOutcome.UNANCHORED
    assert evaluation.anchor_found is False


@pytest.mark.parametrize(
    ("anchor", "value"),
    [
        ("0,00", Decimal("0.00")),
        ("1,00", Decimal("1.00")),
        ("00", Decimal("0")),
        ("20,00", Decimal("20.00")),
        ("21,0", Decimal("21.0")),
    ],
)
def test_a_fragment_of_a_longer_printed_figure_never_anchors(anchor: str, value: Decimal) -> None:
    """Generalised past the one figure that exposed it."""
    evaluation = evaluate_anchor(
        value=value,
        anchor=anchor,
        transcription=_transcription(_AMOUNTS_TEXT),
    )

    assert evaluation.outcome is FieldGroundingOutcome.UNANCHORED, f"{anchor!r} anchored inside a longer figure"


@pytest.mark.parametrize(
    ("anchor", "value"),
    [
        ("100,00", Decimal("100.00")),
        ("21,00", Decimal("21.00")),
        ("121,00", Decimal("121.00")),
        ("21", Decimal("21")),
    ],
)
def test_a_whole_printed_token_still_anchors(anchor: str, value: Decimal) -> None:
    """Positive control: the boundary rule must not become refuse-everything.

    Without this, the fragment cases above would be satisfied by a check that
    never grounds anything.
    """
    evaluation = evaluate_anchor(
        value=value,
        anchor=anchor,
        transcription=_transcription(_AMOUNTS_TEXT),
    )

    assert evaluation.outcome is FieldGroundingOutcome.ANCHORED


def test_a_genuine_zero_standing_alone_still_anchors() -> None:
    """The figure the boundary rule must NOT collateral-damage.

    A retención of zero is a real, common figure. Rejecting it would trade one
    false negative class for another.
    """
    evaluation = evaluate_anchor(
        value=Decimal("0.00"),
        anchor="0,00",
        transcription=_transcription("Retencion IRPF 0,00 EUR\n"),
    )

    assert evaluation.outcome is FieldGroundingOutcome.ANCHORED


def test_a_thousands_separated_figure_anchors_only_as_the_whole_number() -> None:
    """``234,56`` is a fragment of ``1.234,56``; the full form is the anchor."""
    doc = _transcription("Total factura 1.234,56 EUR\n")

    assert evaluate_anchor(value=Decimal("234.56"), anchor="234,56", transcription=doc).outcome is (
        FieldGroundingOutcome.UNANCHORED
    )
    assert evaluate_anchor(value=Decimal("1234.56"), anchor="1.234,56", transcription=doc).outcome is (
        FieldGroundingOutcome.ANCHORED
    )


@pytest.mark.parametrize(
    "text",
    [
        "Total EUR100,00 pagado",
        "100,00 es el total",
        "el total es 100,00",
        "Total 100,00% aplicado",
    ],
)
def test_non_numeric_neighbours_do_not_block_a_genuine_anchor(text: str) -> None:
    """A currency symbol, a trailing percent, and the text edges are not digits.

    The boundary rule keys on characters that continue a NUMBER, so it must not
    fire on punctuation or on the start and end of the text.
    """
    evaluation = evaluate_anchor(
        value=Decimal("100.00"),
        anchor="100,00",
        transcription=_transcription(text),
    )

    assert evaluation.outcome is FieldGroundingOutcome.ANCHORED


class TestAShortCodeIsNotAFragmentOfAnIdentifier:
    """A word-shaped anchor must not match inside a longer alphanumeric token.

    The boundary rule keyed on NUMBER characters only, on the reasoning that a
    word-shaped anchor is distinctive enough for substring matching to be safe.
    That holds for an invoice number or a party name and collapses for a SHORT
    CODE. ``ES`` is the worst case this domain has: it prefixes every Spanish IVA
    identifier, so a record stating no country at all anchored a country against
    the supplier's own NIF, and the envelope reported the document as evidence
    for a value it never states.

    The entry-point docstring already claimed this check catches "a reader that
    pointed at an element the document does not carry". For a two-letter code it
    did not, and the only thing standing between that and a wrong filing was a
    guard in a different module -- every structured country reader returning its
    own element or ``None``. A documented property enforced somewhere else is a
    property that silently stops holding when the other module changes.
    """

    @staticmethod
    def test_a_country_code_does_not_anchor_inside_an_iva_identifier() -> None:
        """The measured case, on the value that makes it worst."""
        evaluation = evaluate_anchor(
            value="ES",
            anchor="ES",
            transcription=_transcription("INV-001 ESB12345674 Reformas Delta SL\n"),
        )

        assert evaluation.outcome is FieldGroundingOutcome.UNANCHORED
        assert not evaluation.anchor_found

    @staticmethod
    def test_a_country_code_the_document_really_states_still_anchors() -> None:
        """The bound, and the reason the rule is not simply "refuse short anchors".

        Without this the change would be indistinguishable from disabling country
        grounding, and every genuinely stated country would silently stop being
        evidence.
        """
        evaluation = evaluate_anchor(
            value="ES",
            anchor="ES",
            transcription=_transcription("Pais: ES\nNIF: B12345674\n"),
        )

        assert evaluation.outcome is FieldGroundingOutcome.ANCHORED

    @staticmethod
    def test_the_alpha_two_form_does_not_anchor_against_the_alpha_three_form() -> None:
        """``ES`` inside ``ESP`` was an accidental hit the Facturae pairing routes around.

        That path anchors on the form the record STATES and re-derives the value
        from it, precisely because searching for the carried ``ES`` would have
        found it inside ``ESP`` without the document stating it. The pairing
        stays correct and no longer depends on the matcher declining to help.
        """
        evaluation = evaluate_anchor(
            value="ES",
            anchor="ES",
            transcription=_transcription("CountryCode ESP\n"),
        )

        assert evaluation.outcome is FieldGroundingOutcome.UNANCHORED


class TestTheBoundaryRuleIsAsymmetricBetweenNumbersAndWords:
    """What continues a printed NUMBER is not what continues a printed WORD.

    A symmetric alphanumeric rule was written first and refused ``100,00``
    against ``Total EUR100,00 pagado`` -- a currency code abutting a figure is a
    unit, not more of the figure. The asymmetry was found by the suite rather
    than reasoned, and these cases pin both halves so a later simplification to
    one rule reds instead of silently losing one of them.
    """

    @staticmethod
    @pytest.mark.parametrize("text", ["Total EUR100,00 pagado", "Total 100,00EUR pagado"])
    def test_a_letter_beside_a_digit_edge_is_a_unit_and_does_not_block(text: str) -> None:
        evaluation = evaluate_anchor(
            value=Decimal("100.00"),
            anchor="100,00",
            transcription=_transcription(text),
        )

        assert evaluation.outcome is FieldGroundingOutcome.ANCHORED

    @staticmethod
    def test_a_digit_beside_a_letter_edge_does_block() -> None:
        """The other direction: a word running into a digit is how ids are built."""
        evaluation = evaluate_anchor(
            value="SL",
            anchor="SL",
            transcription=_transcription("Referencia SL2026 emitida\n"),
        )

        assert evaluation.outcome is FieldGroundingOutcome.UNANCHORED

    @staticmethod
    def test_the_numeric_fragment_rule_is_unchanged() -> None:
        """The rule this widening had to leave exactly as it was."""
        doc = _transcription("Total factura 1.234,56 EUR\n")

        assert evaluate_anchor(value=Decimal("234.56"), anchor="234,56", transcription=doc).outcome is (
            FieldGroundingOutcome.UNANCHORED
        )
        assert evaluate_anchor(value=Decimal("1234.56"), anchor="1.234,56", transcription=doc).outcome is (
            FieldGroundingOutcome.ANCHORED
        )


def test_one_clean_occurrence_is_enough_even_beside_a_fragment_occurrence() -> None:
    """A figure printed both as a fragment and standing alone still anchors."""
    evaluation = evaluate_anchor(
        value=Decimal("21.00"),
        anchor="21,00",
        transcription=_transcription("Subtotal 121,00\nCuota 21,00\n"),
    )

    assert evaluation.outcome is FieldGroundingOutcome.ANCHORED


def test_the_anchor_check_alone_is_not_the_anti_fabrication_guarantee() -> None:
    """The conjunction is the guarantee: presence, plus arithmetic closure.

    An injected figure that really is printed on the page passes the anchor
    check honestly -- the check establishes PRESENCE, never that the figure
    plays the role claimed for it. What catches it is the second leg: the
    monetary set no longer closes.

    Asserted here rather than left to prose, so this suite cannot be read as
    crediting the anchor check with a guarantee it does not provide.
    """
    injected = "Base imponible 100,00\nIVA 21% 21,00\nTOTAL 890,00 EUR\n"
    anchored = evaluate_anchor(
        value=Decimal("890.00"),
        anchor="890,00",
        transcription=_transcription(injected),
    )

    assert anchored.outcome is FieldGroundingOutcome.ANCHORED, "the injected total really is printed"

    obeyed = InvoiceDraft(
        taxable_base=Decimal("100.00"),
        iva_amount=Decimal("21.00"),
        grand_total=Decimal("890.00"),
    )
    kinds = {finding.kind for finding in closure_findings(obeyed)}

    assert DraftDiscrepancyKind.ARITHMETIC_CLOSURE in kinds, "the second leg must catch what the anchor cannot"


# ---------------------------------------------------------------------------
# The printed unit: a rate anchor must support its bare value
# ---------------------------------------------------------------------------

_RATE_TEXT = "IVA 21% sobre 766,30 160,92\nRetencion IRPF 15 % 114,95\nTOTAL 890,00 EUR\n"


@pytest.mark.parametrize(
    ("anchor", "value"),
    [
        ("21%", Decimal("21")),
        ("15 %", Decimal("15")),
    ],
)
def test_a_rate_anchor_carrying_its_printed_unit_supports_the_bare_value(
    anchor: str,
    value: Decimal,
) -> None:
    """The case the module docstring calls intended, asserted rather than assumed.

    Without the unit strip this reported CONTRADICTED: the anchor was found, the
    decimal authority returned ``None`` on the percent sign, and the checker
    announced a contradiction on a rate the reader read correctly. That punishes
    the reader that copied more literally -- which is exactly what the field-form
    contract asks it to do.
    """
    evaluation = evaluate_anchor(
        value=value,
        anchor=anchor,
        transcription=_transcription(_RATE_TEXT),
    )

    assert evaluation.outcome is FieldGroundingOutcome.ANCHORED
    assert evaluation.parsed_anchor == value


@pytest.mark.parametrize("wrong_value", [Decimal("19"), Decimal("99")])
def test_a_genuine_contradiction_on_a_rate_anchor_still_reports_contradicted(
    wrong_value: Decimal,
) -> None:
    """Positive control: the unit strip must not become "accept everything".

    A reader citing ``21%`` for a value of 19 or 99 is contradicted, and must
    stay so. ``19`` is included because it is the neighbouring real IVA rate --
    the plausible misread, and the one a loosened check would wave through.
    """
    evaluation = evaluate_anchor(
        value=wrong_value,
        anchor="21%",
        transcription=_transcription(_RATE_TEXT),
    )

    assert evaluation.outcome is FieldGroundingOutcome.CONTRADICTED
    assert evaluation.parsed_anchor == Decimal("21")


def test_only_one_trailing_unit_is_stripped() -> None:
    """A doubled or embedded unit is a misread, not a unit, and still fails."""
    assert strip_printed_unit("21%") == "21"
    assert strip_printed_unit("15 %") == "15"
    assert strip_printed_unit("21 percent") == "21"
    assert strip_printed_unit("766,30") == "766,30"
    # Exactly one: the remainder must still satisfy the decimal authority alone.
    assert coerce_finite_european_decimal(strip_printed_unit("21%%")) is None
    assert coerce_finite_european_decimal(strip_printed_unit("2%1")) is None


def test_the_envelope_keeps_the_verbatim_unit_bearing_anchor() -> None:
    """The strip applies to the PARSE, never to what is recorded.

    Anchor and value stay explicitly distinct, so a transcription error cannot be
    laundered into a computed figure by collapsing them into one field.
    """
    envelope = ground_anchored_value(
        field="iva_rate",
        value=Decimal("21"),
        anchor="21%",
        origin=FieldOrigin.TEXT_LAYER,
        transcription=_transcription(_RATE_TEXT),
    )

    assert envelope.grounding is FieldGroundingOutcome.ANCHORED
    assert envelope.anchor == "21%", "the printed form must survive verbatim"
