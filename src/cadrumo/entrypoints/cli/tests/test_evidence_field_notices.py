"""A degraded read must be distinguishable from a clean one, per field.

The reading path raises on nothing, so without these notices "read this layout
poorly" and "read this layout fine" reach the operator identically. Each test
here pins one half of the distinction: that a field which failed its check is
reported, that a field which passed is not, and that the two *kinds* of missing
verbatim match are never flattened into one.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path

import pytest

from ....application.ledger.document_transcription import DocumentTranscription, TranscriberIdentity
from ....application.ledger.evidence_draft import FieldAmbiguityCandidate, FieldProvenance, InvoiceDraft
from ....application.ledger.grounded_reading import verified_provenance
from ....application.ledger.identity_roles import IdentityCandidate, resolve_counterparty_identity
from ....core import LOCAL_TRANSPORT_LABEL, FieldGroundingOutcome, FieldOrigin
from ....core.json_contract import Notice, NoticeSeverity, derive_status
from .._evidence_field_notices import DEGRADED_GROUNDING_OUTCOMES, field_degradation_notices
from ._english_locale_fixture import english_locale_fixture

__all__ = ["english_locale_fixture"]

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _contradicted() -> FieldProvenance:
    return FieldProvenance(
        field="taxable_base",
        origin=FieldOrigin.TEXT_LAYER,
        grounding=FieldGroundingOutcome.CONTRADICTED,
        anchor="1.234,56",
        note="the anchor parses to 1234.56",
    )


def _ambiguous() -> FieldProvenance:
    return FieldProvenance(
        field="supplier_tax_id",
        origin=FieldOrigin.TEXT_LAYER,
        grounding=FieldGroundingOutcome.AMBIGUOUS,
        candidates=(FieldAmbiguityCandidate(value="A82645177"), FieldAmbiguityCandidate(value="B17283946")),
    )


def _self_reported() -> FieldProvenance:
    return FieldProvenance(
        field="invoice_date",
        origin=FieldOrigin.VISION,
        grounding=FieldGroundingOutcome.UNANCHORED,
        anchor="07/10/2025",
        anchor_self_reported=True,
    )


def _anchor_not_found() -> FieldProvenance:
    """A form the reader offered and the check reported absent from the document.

    Shaped as the grounding stage really leaves one -- the anchor cleared, the
    refusal recorded -- rather than as a carried anchor under an unanchored
    outcome. That earlier shape was never emitted by any producer at this
    surface, and building the fixture that way was how a THIRD state came to
    share this notice: an anchor the check had located, reported to the operator
    as not occurring in the document.
    """
    return FieldProvenance(
        field="grand_total",
        origin=FieldOrigin.TEXT_LAYER,
        grounding=FieldGroundingOutcome.UNANCHORED,
        refused_anchor="4.528,32",
    )


def _uncorroborated_anchor() -> FieldProvenance:
    """A located printed form on a field something OTHER than the form unsettled.

    The identity resolver's shape: the identifier verified and its anchor is on
    the page, and what is missing is anything assigning it to a party.
    """
    return FieldProvenance(
        field="supplier_tax_id",
        origin=FieldOrigin.TEXT_LAYER,
        grounding=FieldGroundingOutcome.UNANCHORED,
        anchor="B12345674",
        note="one identifier verified but nothing on the document establishes it as the counterparty's",
    )


def _no_anchor() -> FieldProvenance:
    return FieldProvenance(
        field="currency",
        origin=FieldOrigin.TEXT_LAYER,
        grounding=FieldGroundingOutcome.UNANCHORED,
    )


def _reconciled() -> FieldProvenance:
    return FieldProvenance(
        field="iva_rate",
        origin=FieldOrigin.TEXT_LAYER,
        grounding=FieldGroundingOutcome.RECONCILED,
        anchor="21%",
    )


def _anchored() -> FieldProvenance:
    return FieldProvenance(
        field="supplier_name",
        origin=FieldOrigin.TEXT_LAYER,
        grounding=FieldGroundingOutcome.ANCHORED,
        anchor="Iberluz Comercializadora",
    )


def _context(notice: Notice) -> Mapping[str, str]:
    """Return a degradation notice's context, asserting the channel populated it.

    ``Notice.context`` is optional on the envelope model, and every assertion
    below indexed it directly -- reading as though the field were guaranteed
    while proving nothing about it. Every degradation notice names at least the
    field it concerns, so an absent context is a defect. Stated once here, so a
    builder that stopped populating it fails with that sentence rather than a
    subscript error somewhere downstream.
    """
    assert notice.context is not None, f"{notice.code} reached the operator with no context"
    return notice.context


def test_the_degraded_set_is_derived_from_the_vocabulary() -> None:
    """A new grounding outcome is reported by default, not silently ignored.

    Derived by exclusion rather than hand-listed, so a member added to the
    vocabulary lands in the reported set until someone deliberately declares it
    intact. A hand-listed set would leave the new outcome invisible.
    """
    assert (
        frozenset(FieldGroundingOutcome)
        - {
            FieldGroundingOutcome.RECONCILED,
            FieldGroundingOutcome.ANCHORED,
        }
        == DEGRADED_GROUNDING_OUTCOMES
    )
    assert FieldGroundingOutcome.RECONCILED not in DEGRADED_GROUNDING_OUTCOMES
    assert FieldGroundingOutcome.ANCHORED not in DEGRADED_GROUNDING_OUTCOMES


def test_a_field_that_passed_its_check_produces_no_notice() -> None:
    """The channel reports degradation, not inventory."""
    assert field_degradation_notices([_reconciled(), _anchored()]) == []


def test_every_degraded_field_produces_exactly_one_notice() -> None:
    """Positive control for the silence above: degradation is not simply dropped.

    Without this, a builder that returned nothing at all would satisfy the
    no-notice-for-intact-fields assertion perfectly.
    """
    degraded = [
        _contradicted(),
        _ambiguous(),
        _self_reported(),
        _anchor_not_found(),
        _uncorroborated_anchor(),
        _no_anchor(),
    ]
    notices = field_degradation_notices(degraded)

    assert len(notices) == len(degraded)
    assert [_context(notice)["field"] for notice in notices] == [envelope.field for envelope in degraded]


def test_every_degraded_shape_reaches_a_notice_of_its_own() -> None:
    """No two shapes share a code, and none is unreachable.

    The defect this pins is not a wrong message but a shape that cannot reach
    its own notice: a producer emitting one thing while the selection tests for
    another leaves a code correct, present and dead, and every other case here
    goes on passing. Asserted as a bijection rather than as a tally, so a shape
    added later without its own code fails instead of being counted.
    """
    shapes = {
        "contradicted": _contradicted(),
        "ambiguous": _ambiguous(),
        "self_reported": _self_reported(),
        "anchor_not_found": _anchor_not_found(),
        "uncorroborated": _uncorroborated_anchor(),
        "no_anchor": _no_anchor(),
    }
    codes = {name: field_degradation_notices([envelope])[0].code for name, envelope in shapes.items()}

    assert len(set(codes.values())) == len(codes), f"two shapes share one code: {codes}"


def test_an_unchecked_anchor_is_never_reported_as_a_failed_check() -> None:
    """The distinction this gate exists to protect.

    A text-lane ``UNANCHORED`` is a check that RAN against an independently
    produced transcription and did not pass. A self-reported anchor is a check
    that could not run at all, because the same reader produced both the value
    and the claim about where it came from. Same enum member, different
    strengths of evidence, and the operator surface must not flatten them.
    """
    self_reported = field_degradation_notices([_self_reported()])[0]
    checked = field_degradation_notices([_anchor_not_found()])[0]

    # Same underlying outcome...
    assert _self_reported().grounding is _anchor_not_found().grounding
    # ...but never the same thing said to the operator.
    assert self_reported.code != checked.code
    assert self_reported.code == "ledger.evidence.field.anchor_self_reported"
    assert checked.code == "ledger.evidence.field.anchor_not_found"
    assert _context(self_reported)["anchor_self_reported"] == "true"
    assert _context(checked)["anchor_self_reported"] == "false"
    assert "nothing independent" in self_reported.message
    assert "does not occur" in checked.message


def test_a_missing_anchor_is_distinct_from_an_anchor_that_was_not_found() -> None:
    """Nothing offered to check is a different operator situation from a failed check."""
    offered_nothing = field_degradation_notices([_no_anchor()])[0]
    offered_something = field_degradation_notices([_anchor_not_found()])[0]

    assert offered_nothing.code == "ledger.evidence.field.no_anchor"
    assert offered_nothing.code != offered_something.code
    assert "anchor" not in _context(offered_nothing)


def test_a_located_anchor_is_never_reported_as_absent_from_the_document() -> None:
    """The third state, and the reason it cannot share the not-found notice.

    An identifier that verified while nothing on the page assigns it to a party
    keeps its anchor: the check LOCATED that printed form. Telling the operator
    it "does not occur in the document's transcription" sends them to re-read a
    page which says exactly what the reader claimed, and closes the question
    that is actually open.
    """
    located = field_degradation_notices([_uncorroborated_anchor()])[0]
    refused = field_degradation_notices([_anchor_not_found()])[0]

    assert located.code == "ledger.evidence.field.anchor_uncorroborated"
    assert located.code != refused.code
    assert "does not occur" not in located.message
    assert "does not occur" in refused.message

    # The printed form and the reason both reach the operator: the message can
    # only say the form is not the problem, so the reason is the whole content.
    assert "B12345674" in located.message
    assert _context(located)["anchor"] == "B12345674"
    assert _context(located)["detail"] == _uncorroborated_anchor().note
    assert _uncorroborated_anchor().note in located.message


def test_the_not_found_notice_names_the_refused_form_and_never_a_carried_one() -> None:
    """Anti-regression on the selection, from the other side.

    The not-found notice reads the REFUSED anchor alone. If it fell back to the
    carried one, the third state above would render under this notice's text
    again the moment anything routed it here, and the fallback would look like
    defensive coding rather than the re-conflation it is.
    """
    refused = field_degradation_notices([_anchor_not_found()])[0]

    assert _anchor_not_found().anchor is None, "the producer clears the anchor it could not locate"
    assert _context(refused)["anchor"] == "4.528,32"
    assert "4.528,32" in refused.message


def _grounded_against(text: str, *, draft: InvoiceDraft) -> tuple[FieldProvenance, ...]:
    """Return *draft*'s envelopes as the REAL grounding stage leaves them.

    Hand-built envelopes prove which branch a selector takes; they cannot prove
    the producer ever emits that shape. The defect these cases pin lived exactly
    there -- the branch was correct and the producer emitted a shape that could
    not reach it -- so the envelopes below are put through the same function the
    reading path calls, against a real transcription.

    Takes the built draft rather than field keywords to splat: a ``**values:
    object`` signature erases every field's declared type on the way in, so the
    checker can no longer tell a Decimal field from a string one and the fixture
    stops being checked at exactly the boundary it is exercising.
    """
    transcription = DocumentTranscription(
        text=text,
        page_count=1,
        source_content_sha256="c" * 64,
        transcriber=TranscriberIdentity(
            origin=FieldOrigin.TEXT_LAYER,
            name="test-text-layer",
            transport=LOCAL_TRANSPORT_LABEL,
            revision="1",
        ),
    )
    return verified_provenance(draft=draft, transcription=transcription)


def test_a_refused_anchor_is_not_reported_as_an_absent_one() -> None:
    """The two shapes the grounding stage produces must not arrive identical.

    A reader that pointed at a printed form the document does not carry and a
    reader that pointed at nothing reach the operator through the same cleared
    anchor, so without the refusal recorded beside it the first is told to the
    operator as the second -- affirmatively false, and the message it lands in
    ("nothing to point at") closes exactly the investigation the misread case
    deserves.

    Driven through the real grounding stage rather than hand-built envelopes,
    because that is where the two shapes became indistinguishable.
    """
    grounded = _grounded_against(
        "FACTURA 2026-0142\nTOTAL 121,00 EUR\n",
        draft=InvoiceDraft(
            grand_total=Decimal("4528.32"),
            currency="EUR",
            provenance=(
                FieldProvenance(
                    field="grand_total",
                    origin=FieldOrigin.TEXT_LAYER,
                    grounding=FieldGroundingOutcome.UNANCHORED,
                    anchor="4.528,32",
                ),
                FieldProvenance(
                    field="currency",
                    origin=FieldOrigin.TEXT_LAYER,
                    grounding=FieldGroundingOutcome.UNANCHORED,
                ),
            ),
        ),
    )

    notices = field_degradation_notices(grounded)
    by_field = {_context(notice)["field"]: notice for notice in notices}

    refused = by_field["grand_total"]
    assert refused.code == "ledger.evidence.field.anchor_not_found"
    assert "4.528,32" in refused.message, "the operator needs the form that was rejected"

    absent = by_field["currency"]
    assert absent.code == "ledger.evidence.field.no_anchor"
    assert refused.code != absent.code


def test_the_refusal_reaches_the_operator_with_the_reason_the_check_computed() -> None:
    """The detail is computed and carried; dropping it wastes the only explanation.

    A cleared anchor tells the operator that something failed. WHY it failed is
    already written onto the envelope by the check, and it is the sentence that
    separates a normalised value failing a verbatim search from a figure that is
    not on the page at all.
    """
    grounded = _grounded_against(
        "FACTURA 2026-0142\nTOTAL 121,00 EUR\n",
        draft=InvoiceDraft(
            grand_total=Decimal("4528.32"),
            provenance=(
                FieldProvenance(
                    field="grand_total",
                    origin=FieldOrigin.TEXT_LAYER,
                    grounding=FieldGroundingOutcome.UNANCHORED,
                    anchor="4.528,32",
                ),
            ),
        ),
    )
    notice = field_degradation_notices(grounded)[0]

    assert grounded[0].note, "the check must have computed a reason to carry"
    assert _context(notice)["detail"] == grounded[0].note
    assert grounded[0].note in notice.message


def test_the_identity_resolver_really_emits_the_located_but_unroled_shape() -> None:
    """Reachability, from the producer rather than from a fixture.

    The shape above is only worth a notice of its own if something actually
    emits it. A hand-built envelope proves which branch the selection takes and
    nothing about whether the producer ever hands it one -- and the dominant
    defect this suite guards against is precisely a correct branch a producer
    cannot reach.

    So the envelope here comes from the real resolver: one identifier that
    verified, its anchor located on the page, and nothing printed that assigns
    it to a party.
    """
    resolution = resolve_counterparty_identity(
        field="supplier_tax_id",
        candidates=(IdentityCandidate(value="B12345674", anchor="B-12345674", role_evidence=""),),
        taxpayer_tax_id="A82645177",
        origin=FieldOrigin.TEXT_LAYER,
    )
    envelope = resolution.provenance

    # The producer's own shape, asserted before the notice is asked for: an
    # anchor carried under a degraded outcome, with no refusal recorded.
    assert envelope.grounding in DEGRADED_GROUNDING_OUTCOMES
    assert envelope.anchor is not None, "the resolver keeps the anchor it located"
    assert envelope.refused_anchor is None, "nothing was refused here"

    notice = field_degradation_notices([envelope])[0]

    assert notice.code == "ledger.evidence.field.anchor_uncorroborated"
    assert "does not occur" not in notice.message


def test_each_notice_names_what_was_seen() -> None:
    """The printed form the reader claims to have read reaches the operator."""
    contradicted = field_degradation_notices([_contradicted()])[0]
    assert _context(contradicted)["anchor"] == "1.234,56"
    assert "1.234,56" in contradicted.message

    ambiguous = field_degradation_notices([_ambiguous()])[0]
    assert "A82645177" in ambiguous.message
    assert "B17283946" in ambiguous.message
    assert _context(ambiguous)["candidate_count"] == "2"


def test_each_notice_names_why_the_value_was_not_accepted() -> None:
    """The outcome and the origin travel with every report, not just the field name."""
    for envelope in (_contradicted(), _ambiguous(), _self_reported(), _anchor_not_found(), _no_anchor()):
        notice = field_degradation_notices([envelope])[0]
        assert _context(notice)["outcome"] == envelope.grounding.value
        assert _context(notice)["origin"] == envelope.origin.value


def test_a_disagreement_and_an_undecided_reading_are_warnings() -> None:
    """Something positively wrong or unresolved moves the envelope status."""
    for envelope in (_contradicted(), _ambiguous()):
        assert field_degradation_notices([envelope])[0].severity is NoticeSeverity.WARNING
    assert derive_status(field_degradation_notices([_contradicted()])).value == "warning"


def test_a_missing_verbatim_match_is_informational() -> None:
    """A normalised value fails a verbatim search legitimately.

    Warning on every one of those would train an operator to ignore the channel,
    which is how an anti-fabrication signal becomes decoration. These stay
    informational, and the envelope status stays clean for them alone.
    """
    unanchored = [_self_reported(), _anchor_not_found(), _no_anchor()]
    notices = field_degradation_notices(unanchored)

    assert all(notice.severity is NoticeSeverity.INFO for notice in notices)
    assert derive_status(notices).value == "success"


def test_notices_follow_provenance_order() -> None:
    """The report reads in the order the draft's fields were assembled."""
    envelopes = [_no_anchor(), _contradicted(), _ambiguous()]
    notices = field_degradation_notices(envelopes)
    assert [_context(notice)["field"] for notice in notices] == ["currency", "taxable_base", "supplier_tax_id"]


def test_both_evidence_surfaces_emit_the_degradation_notices() -> None:
    """The builder is wired into extract AND confirm, not merely importable.

    Structural rather than end-to-end on purpose: exercising either command for
    real now routes through the reading pipeline and reaches a model endpoint,
    which this environment must not do. What can be checked without one is that
    each command's own code references the builder — which is precisely the
    thing that would go missing if someone deleted the call, leaving every test
    above passing over a builder nothing invokes.
    """
    from .. import _ledger_evidence_cli

    source = Path(_ledger_evidence_cli.__file__).read_text(encoding="utf-8")
    extract_calls = source.count("notices.extend(field_degradation_notices(draft.provenance))")
    confirm_calls = source.count("notices.extend(field_degradation_notices(result.draft.provenance))")

    assert extract_calls == 1, "the extract surface must emit per-field degradation notices"
    assert confirm_calls == 1, "the confirm surface must emit per-field degradation notices"
