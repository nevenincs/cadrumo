"""Arithmetic-closure findings over a document's own stated figures.

The identities checked here are ACCOUNTING identities, not registry formulas:
``total = base + cuota + recargo + suplido`` and ``cash = total - retencion``
hold because of what those words mean, not because a registry file says so. That
is what makes a constructed case legitimate rather than tautological here -- the
expectation comes from the identity, and the identity is external to this code.
A test asserting a registry-derived rate or threshold would need bundled AEAT
authority; these do not.

**The 890.00 / 927.22 case is the harness's positive control.** It is a document
that is wrong on purpose: a printed total of 890.00 against components summing to
927.22. It exists to prove the harness can report a failure at all. Nothing here
normalises the printed total toward the computed one -- the disagreement IS the
finding, and a run in which this scores clean is a broken run, not a clean
document.

NOTE ON PROVENANCE: the corpus fixtures named for this case
(``OP-PUR-COM-2026-0005_camera-photo`` and ``_layout-minimal``) are scheduled to
be bundled with their provenance sidecars in a future change and are NOT in the
repository yet. The figures below reproduce the arithmetic those documents
carry so the CHECK is gated now; they are constructed inputs and are labelled
as such rather than named after fixtures that do not exist. When the real
documents land, they plug into :func:`_closure_over` unchanged.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core import DraftDiscrepancyKind
from .._closure_findings import (
    ROUNDING_ALLOWANCE_PER_TERM,
    closure_findings,
    within_rounding_allowance,
)
from .._evidence_draft import InvoiceDraft, InvoiceDraftRateBreakdown

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: The positive control's figures. Base and cuota reach 927.22; the document
#: prints 890.00. The 37.22 gap is the whole point.
_CONTROL_BASE = Decimal("766.30")
_CONTROL_CUOTA = Decimal("160.92")
_CONTROL_COMPUTED_TOTAL = Decimal("927.22")
_CONTROL_PRINTED_TOTAL = Decimal("890.00")


def _closure_over(draft: InvoiceDraft) -> tuple[DraftDiscrepancyKind, ...]:
    return tuple(finding.kind for finding in closure_findings(draft))


def test_the_control_figures_still_disagree_by_the_amount_they_are_named_for() -> None:
    """Anchor: if the constants ever reconcile, every case below goes vacuous."""
    assert _CONTROL_BASE + _CONTROL_CUOTA == _CONTROL_COMPUTED_TOTAL
    assert _CONTROL_PRINTED_TOTAL != _CONTROL_COMPUTED_TOTAL
    assert Decimal("37.22") == _CONTROL_COMPUTED_TOTAL - _CONTROL_PRINTED_TOTAL


def test_the_positive_control_produces_a_blocking_closure_finding() -> None:
    """890.00 against 927.22 must be reported, with both figures named.

    The finding carries the computed and printed values rather than a message
    alone, because an operator resolving this needs to see which side to check.
    """
    draft = InvoiceDraft(
        taxable_base=_CONTROL_BASE,
        iva_rate=Decimal("21"),
        iva_amount=_CONTROL_CUOTA,
        grand_total=_CONTROL_PRINTED_TOTAL,
    )

    findings = closure_findings(draft)

    assert DraftDiscrepancyKind.ARITHMETIC_CLOSURE in {f.kind for f in findings}
    closure = next(f for f in findings if f.kind is DraftDiscrepancyKind.ARITHMETIC_CLOSURE)
    assert closure.expected == _CONTROL_COMPUTED_TOTAL
    assert closure.observed == _CONTROL_PRINTED_TOTAL
    assert closure.field == "grand_total"


def test_the_printed_total_is_never_normalised_toward_the_computed_one() -> None:
    """The document's own figure survives the check unchanged.

    A check that "repaired" the printed total would erase the only evidence that
    something is wrong, and would do it silently.
    """
    draft = InvoiceDraft(
        taxable_base=_CONTROL_BASE,
        iva_amount=_CONTROL_CUOTA,
        grand_total=_CONTROL_PRINTED_TOTAL,
    )

    closure_findings(draft)

    assert draft.grand_total == _CONTROL_PRINTED_TOTAL


def test_a_closing_invoice_raises_nothing() -> None:
    """Positive control: the checker is not a blanket accusation.

    Without this, every assertion above would be satisfied by a function that
    always returns a finding.
    """
    draft = InvoiceDraft(
        taxable_base=Decimal("100.00"),
        iva_rate=Decimal("21"),
        iva_amount=Decimal("21.00"),
        grand_total=Decimal("121.00"),
    )

    assert closure_findings(draft) == ()


def test_recargo_and_suplidos_are_terms_of_the_total_identity() -> None:
    """``total = base + cuota + recargo + suplido``, all four.

    Omitting recargo understates a recargo-de-equivalencia invoice by exactly the
    surcharge; omitting suplidos reports a false discrepancy on every invoice
    that advances sums on the customer's behalf.
    """
    draft = InvoiceDraft(
        taxable_base=Decimal("1000.00"),
        iva_amount=Decimal("210.00"),
        recargo_amount=Decimal("52.00"),
        suplidos_amount=Decimal("30.00"),
        grand_total=Decimal("1292.00"),
    )

    assert closure_findings(draft) == ()


def test_dropping_the_recargo_from_the_total_is_reported() -> None:
    """Control for the term above: it must actually participate."""
    draft = InvoiceDraft(
        taxable_base=Decimal("1000.00"),
        iva_amount=Decimal("210.00"),
        recargo_amount=Decimal("52.00"),
        grand_total=Decimal("1210.00"),
    )

    assert DraftDiscrepancyKind.ARITHMETIC_CLOSURE in _closure_over(draft)


def test_a_retencion_inconsistent_with_its_rate_is_reported() -> None:
    """``cash = total - retencion`` only reconciles if the retención is right."""
    draft = InvoiceDraft(
        taxable_base=Decimal("1000.00"),
        iva_amount=Decimal("210.00"),
        grand_total=Decimal("1210.00"),
        retencion_rate=Decimal("15"),
        retencion_amount=Decimal("90.00"),
    )

    assert DraftDiscrepancyKind.RATE_INCONSISTENT in _closure_over(draft)


def test_a_consistent_retencion_raises_nothing() -> None:
    draft = InvoiceDraft(
        taxable_base=Decimal("1000.00"),
        iva_amount=Decimal("210.00"),
        grand_total=Decimal("1210.00"),
        retencion_rate=Decimal("15"),
        retencion_amount=Decimal("150.00"),
    )

    assert closure_findings(draft) == ()


def test_a_tier_whose_cuota_does_not_match_its_rate_is_reported() -> None:
    """Modelo 303 declares cuota devengada per tier, so a tier must close alone."""
    draft = InvoiceDraft(
        taxable_base=Decimal("1000.00"),
        iva_amount=Decimal("210.00"),
        grand_total=Decimal("1210.00"),
        iva_breakdown=(
            InvoiceDraftRateBreakdown(
                iva_rate=Decimal("21"),
                taxable_base=Decimal("1000.00"),
                iva_amount=Decimal("100.00"),
            ),
        ),
    )

    assert DraftDiscrepancyKind.RATE_INCONSISTENT in _closure_over(draft)


def test_per_rate_subtotals_that_do_not_sum_to_the_flat_totals_are_reported() -> None:
    """Two independent readings of one document that disagree."""
    draft = InvoiceDraft(
        taxable_base=Decimal("1000.00"),
        iva_amount=Decimal("175.00"),
        grand_total=Decimal("1175.00"),
        iva_breakdown=(
            InvoiceDraftRateBreakdown(
                iva_rate=Decimal("21"),
                taxable_base=Decimal("500.00"),
                iva_amount=Decimal("105.00"),
            ),
            InvoiceDraftRateBreakdown(
                iva_rate=Decimal("10"),
                taxable_base=Decimal("400.00"),
                iva_amount=Decimal("40.00"),
            ),
        ),
    )

    kinds = _closure_over(draft)
    assert DraftDiscrepancyKind.BREAKDOWN_INCONSISTENT in kinds


def test_a_two_rate_invoice_whose_tiers_sum_correctly_raises_nothing() -> None:
    """Positive control for the breakdown check."""
    draft = InvoiceDraft(
        taxable_base=Decimal("900.00"),
        iva_amount=Decimal("145.00"),
        grand_total=Decimal("1045.00"),
        iva_breakdown=(
            InvoiceDraftRateBreakdown(
                iva_rate=Decimal("21"),
                taxable_base=Decimal("500.00"),
                iva_amount=Decimal("105.00"),
            ),
            InvoiceDraftRateBreakdown(
                iva_rate=Decimal("10"),
                taxable_base=Decimal("400.00"),
                iva_amount=Decimal("40.00"),
            ),
        ),
    )

    assert closure_findings(draft) == ()


def test_per_line_rounding_drift_is_absorbed() -> None:
    """A cent of drift per stated term is arithmetic, not error."""
    draft = InvoiceDraft(
        taxable_base=Decimal("100.00"),
        iva_amount=Decimal("21.00"),
        grand_total=Decimal("121.01"),
    )

    assert closure_findings(draft) == ()


def test_the_allowance_does_not_stretch_to_the_control_discrepancy() -> None:
    """The boundary, asserted directly rather than inferred from a passing case.

    37.22 must sit far outside the allowance for any plausible term count. If a
    future change widened the tolerance enough to swallow it, this fails before
    the finding tests do, and says why.
    """
    assert Decimal("0.01") == ROUNDING_ALLOWANCE_PER_TERM
    for term_count in range(1, 21):
        assert not within_rounding_allowance(Decimal("37.22"), term_count=term_count)


def test_an_identity_missing_a_term_is_not_checked_rather_than_assumed_to_hold() -> None:
    """Silence must mean "not checked", never "verified".

    A draft with no printed total has no total identity to check. Reporting
    nothing is correct; reporting that it closed would be a claim about a figure
    the document never stated.
    """
    draft = InvoiceDraft(taxable_base=Decimal("100.00"), iva_amount=Decimal("21.00"))

    assert closure_findings(draft) == ()


def test_findings_are_deterministic_and_stably_ordered() -> None:
    """An operator surface and a test must read the same document the same way."""
    draft = InvoiceDraft(
        taxable_base=_CONTROL_BASE,
        iva_amount=_CONTROL_CUOTA,
        grand_total=_CONTROL_PRINTED_TOTAL,
        retencion_rate=Decimal("15"),
        retencion_amount=Decimal("1.00"),
    )

    first = closure_findings(draft)
    second = closure_findings(draft)

    assert first == second
    assert [f.kind for f in first] == [
        DraftDiscrepancyKind.ARITHMETIC_CLOSURE,
        DraftDiscrepancyKind.RATE_INCONSISTENT,
    ]
