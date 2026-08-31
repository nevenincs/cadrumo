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

from ....core.draft_discrepancy import DraftDiscrepancyKind
from ..closure_findings import (
    ROUNDING_ALLOWANCE_PER_TERM,
    closure_findings,
    within_rounding_allowance,
)
from ..evidence_draft import InvoiceDraft, InvoiceDraftRateBreakdown

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


# ── the flat triple, which nothing checked ─────────────────────────────────
#
# The per-tier check above iterates ``iva_breakdown``, populated only by the
# STRUCTURED reader; a flat ``iva_rate`` is populated only by the model-read
# lane. The two representations are disjoint, so until the identity below
# existed the unchecked one was exactly the one a model produced.
#
# The identity is the same accounting one the tier check uses, so these cases
# are legitimate on the terms this module's docstring sets: the expectation
# comes from what "a rate charged on a base" means, not from a registry file.

#: A two-rate invoice as a text or vision lane reads it: 1000 at 21% plus 1000
#: at 10%, so the printed TOTAL base and TOTAL cuota, and ONE of the two rates.
#: The total identity holds, which is why this confirmed clean.
_COLLAPSED_BASE = Decimal("2000.00")
_COLLAPSED_CUOTA = Decimal("310.00")
_COLLAPSED_TOTAL = Decimal("2310.00")


def test_the_collapsed_figures_are_the_two_rate_document_they_are_named_for() -> None:
    """Anchor: if these stop being a two-rate invoice, the case below goes vacuous."""
    assert Decimal("1000.00") * Decimal("21") / Decimal("100") == Decimal("210.00")
    assert Decimal("1000.00") * Decimal("10") / Decimal("100") == Decimal("100.00")
    assert Decimal("1000.00") + Decimal("1000.00") == _COLLAPSED_BASE
    assert Decimal("210.00") + Decimal("100.00") == _COLLAPSED_CUOTA
    # The reason nothing caught it: the TOTAL identity holds perfectly.
    assert _COLLAPSED_BASE + _COLLAPSED_CUOTA == _COLLAPSED_TOTAL


def test_a_multi_rate_document_collapsed_to_one_rate_is_reported() -> None:
    """The measured silence, closed.

    A single rate cannot describe this document, and the rate is what decides
    which Modelo 303 tier the base lands in -- so confirming it files the whole
    base under one tier and its cuota under another.
    """
    draft = InvoiceDraft(
        taxable_base=_COLLAPSED_BASE,
        iva_rate=Decimal("21"),
        iva_amount=_COLLAPSED_CUOTA,
        grand_total=_COLLAPSED_TOTAL,
    )

    assert _closure_over(draft) == (DraftDiscrepancyKind.RATE_INCONSISTENT,)


def test_the_finding_names_the_rate_rather_than_the_cuota() -> None:
    """The rate is the field an operator must correct; the cuota is as printed.

    Both figures were copied from the document. The one that cannot be right is
    the single rate, so pointing the operator at the cuota would send them to
    re-read a number the document states correctly.
    """
    draft = InvoiceDraft(
        taxable_base=_COLLAPSED_BASE,
        iva_rate=Decimal("21"),
        iva_amount=_COLLAPSED_CUOTA,
        grand_total=_COLLAPSED_TOTAL,
    )

    (finding,) = closure_findings(draft)

    assert finding.field == "iva_rate"


def test_a_correctly_read_single_rate_invoice_stays_silent() -> None:
    """The precision half. This is the overwhelming majority of documents."""
    draft = InvoiceDraft(
        taxable_base=Decimal("1000.00"),
        iva_rate=Decimal("21"),
        iva_amount=Decimal("210.00"),
        grand_total=Decimal("1210.00"),
    )

    assert closure_findings(draft) == ()


@pytest.mark.parametrize(
    ("rate", "cuota"),
    [(Decimal("21"), None), (None, Decimal("210.00")), (Decimal("0"), Decimal("0.00"))],
    ids=["no-cuota-stated", "no-rate-stated", "exempt-or-reverse-charge"],
)
def test_a_document_stating_no_charge_is_not_checked_rather_than_flagged(
    rate: Decimal | None,
    cuota: Decimal | None,
) -> None:
    """An exempt or reverse-charge invoice is ordinary, not malformed.

    Two of these have a missing term, so the identity does not run; the third
    states a real zero, and zero percent of a base is zero. None is a finding.
    """
    draft = InvoiceDraft(taxable_base=Decimal("1000.00"), iva_rate=rate, iva_amount=cuota)

    assert closure_findings(draft) == ()


def test_a_recargo_de_equivalencia_charge_is_not_read_as_a_rate_disagreement() -> None:
    """Recargo carries its own rate and amount and is not inside the cuota.

    Handled by the field split rather than by tolerance: were the recargo folded
    into ``iva_amount``, every recargo invoice in the corpus would fire here.
    """
    draft = InvoiceDraft(
        taxable_base=Decimal("1000.00"),
        iva_rate=Decimal("21"),
        iva_amount=Decimal("210.00"),
        recargo_amount=Decimal("52.00"),
        grand_total=Decimal("1262.00"),
    )

    assert closure_findings(draft) == ()


def test_a_multi_tier_breakdown_leaves_the_flat_rate_alone() -> None:
    """Where the breakdown exists it is the authority, and it is already checked.

    A flat rate beside a two-tier breakdown is legitimately not a single rate,
    so checking it against the summed base would report a disagreement that is
    only an artefact of asking the flat triple a question it does not answer.
    """
    draft = InvoiceDraft(
        taxable_base=_COLLAPSED_BASE,
        iva_rate=Decimal("21"),
        iva_amount=_COLLAPSED_CUOTA,
        grand_total=_COLLAPSED_TOTAL,
        iva_breakdown=(
            InvoiceDraftRateBreakdown(
                iva_rate=Decimal("21"),
                taxable_base=Decimal("1000.00"),
                iva_amount=Decimal("210.00"),
            ),
            InvoiceDraftRateBreakdown(
                iva_rate=Decimal("10"),
                taxable_base=Decimal("1000.00"),
                iva_amount=Decimal("100.00"),
            ),
        ),
    )

    assert closure_findings(draft) == ()


def test_the_identity_is_what_causes_the_finding() -> None:
    """Mutation proof: without the comparison the collapse confirms clean again.

    Re-runs the pre-change behaviour, where the flat triple was simply not an
    identity anyone checked. It reports nothing -- which is the measured silence
    this closes. Without this the suite would prove a finding EXISTS, not that
    comparing the three figures is what produces it.
    """
    draft = InvoiceDraft(
        taxable_base=_COLLAPSED_BASE,
        iva_rate=Decimal("21"),
        iva_amount=_COLLAPSED_CUOTA,
        grand_total=_COLLAPSED_TOTAL,
    )

    def _without_the_flat_identity(candidate: InvoiceDraft) -> tuple[DraftDiscrepancyKind, ...]:
        return tuple(finding.kind for finding in closure_findings(candidate) if finding.field != "iva_rate")

    assert _without_the_flat_identity(draft) == ()
    assert _closure_over(draft) == (DraftDiscrepancyKind.RATE_INCONSISTENT,)
