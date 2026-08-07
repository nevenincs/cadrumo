"""A degraded read must be distinguishable from a clean one, per field.

The reading path raises on nothing, so without these notices "read this layout
poorly" and "read this layout fine" reach the operator identically. Each test
here pins one half of the distinction: that a field which failed its check is
reported, that a field which passed is not, and that the two *kinds* of missing
verbatim match are never flattened into one.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ....application.ledger import FieldProvenance
from ....application.ledger._evidence_draft import FieldAmbiguityCandidate
from ....core import FieldGroundingOutcome, FieldOrigin
from ....core.json_contract import Notice, NoticeSeverity, derive_status
from .._evidence_field_notices import DEGRADED_GROUNDING_OUTCOMES, field_degradation_notices

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
    return FieldProvenance(
        field="grand_total",
        origin=FieldOrigin.TEXT_LAYER,
        grounding=FieldGroundingOutcome.UNANCHORED,
        anchor="4.528,32",
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


def _context(notice: Notice) -> dict[str, str]:
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
    assert frozenset(FieldGroundingOutcome) - {
        FieldGroundingOutcome.RECONCILED,
        FieldGroundingOutcome.ANCHORED,
    } == DEGRADED_GROUNDING_OUTCOMES
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
    degraded = [_contradicted(), _ambiguous(), _self_reported(), _anchor_not_found(), _no_anchor()]
    notices = field_degradation_notices(degraded)

    assert len(notices) == len(degraded)
    assert [_context(notice)["field"] for notice in notices] == [envelope.field for envelope in degraded]


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
