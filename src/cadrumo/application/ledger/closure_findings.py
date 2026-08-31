"""Arithmetic identities a real invoice must satisfy, checked at read time.

Three families of identity, all deterministic, all computed from figures the
document itself states:

**The total closes.** ``total = base + cuota + recargo + suplido``. Every term is
a component the document prints; when they do not reach the printed total,
either a component was misread or the document carries one the draft cannot
represent. Both are silent under-declarations when the printed figure is
discarded unexamined, which is why the printed total is never normalised toward
the computed one -- the disagreement IS the finding.

**Cash closes.** ``cash = total - retencion``. IRPF withheld at source is
subtracted from the invoice total to reach the money that actually moves, so a
draft that drops the retención reconciles the ledger against the wrong figure --
and reconciles *successfully*, against a bank movement that is short by exactly
the withholding.

**The per-rate breakdown closes.** The per-rate subtotals must sum to the flat
base and cuota beside them. These are two independent readings of one document,
so a disagreement means at least one is wrong and the draft cannot say which.
Modelo 303 declares cuota devengada per tier, so a breakdown that sums correctly
in total while misattributing base between tiers still declares into the wrong
tier -- checked per tier as well as in aggregate.

**On tolerance, deliberately.** Real invoices round per line, so a few cents of
drift across several terms is arithmetic rather than error. The allowance is one
cent per contributing term and no more (:data:`ROUNDING_ALLOWANCE_PER_TERM`).
That is wide enough to absorb genuine per-line rounding and far too narrow to
absorb a misread component. A tolerance loose enough to let a real discrepancy
pass is not a more forgiving version of this check -- it is the check switched
off, which is why the gate mutation-proves the boundary rather than trusting it.

This module is distinct from :func:`~application.ledger.evidence_draft.printed_total_discrepancy`,
and the distinction is the point: that function compares the document against the
invoice that was actually WRITTEN, so it can only run at confirm. These identities
are internal to the document and run the moment it is read, which is where the
operator is still deciding.

See Also:
    :class:`~application.ledger.evidence_draft.DraftDiscrepancyFinding`
        The finding record produced here.
    :class:`~core.DraftDiscrepancyKind`
        The closed kind axis; this module never widens it.
    :func:`~application.ledger.evidence_draft.printed_total_discrepancy`
        The confirm-time, document-versus-record counterpart.
"""

from __future__ import annotations

from decimal import Decimal

from ...core.draft_discrepancy import DraftDiscrepancyKind
from .evidence_draft import DraftDiscrepancyFinding, InvoiceDraft

__all__ = [
    "ROUNDING_ALLOWANCE_PER_TERM",
    "closure_findings",
    "within_rounding_allowance",
]

ROUNDING_ALLOWANCE_PER_TERM = Decimal("0.01")
"""Cents of drift allowed per contributing term, and not one more.

Per-line rounding is real: a document stating four components can legitimately
land a cent away from their sum. Scaling the allowance by the number of terms
admits exactly that and nothing else. It is deliberately NOT a percentage --
a percentage grows with the invoice, so the largest invoices, where a misread
component costs the most, would get the widest licence to be wrong.
"""


def within_rounding_allowance(difference: Decimal, *, term_count: int) -> bool:
    """Return whether *difference* is inside the per-term rounding allowance.

    Args:
        difference: Signed difference between the stated and computed figures.
        term_count: How many document-stated terms contributed to the
            computation. At least one.

    Returns:
        ``True`` when the difference is attributable to per-line rounding.
    """
    return abs(difference) <= ROUNDING_ALLOWANCE_PER_TERM * max(term_count, 1)


def _zero_if_absent(value: Decimal | None) -> Decimal:
    """Return *value*, treating an absent component as contributing nothing.

    An absent component is not a zero the document stated -- it is a component
    the document did not state. Treating it as zero for the SUM is correct (it
    adds nothing), and it is deliberately not counted as a contributing term for
    the tolerance, so an absent component neither widens the allowance nor
    invents a figure.
    """
    return value if value is not None else Decimal("0")


def _total_closure_finding(draft: InvoiceDraft) -> DraftDiscrepancyFinding | None:
    """Check ``total = base + cuota + recargo + suplido``."""
    if draft.grand_total is None or draft.taxable_base is None:
        # Without a stated total or base there is no identity to check. Silence
        # here is honest: nothing was verified, and nothing is claimed.
        return None

    components = (draft.taxable_base, draft.iva_amount, draft.recargo_amount, draft.suplidos_amount)
    stated_terms = sum(1 for component in components if component is not None)
    computed = sum((_zero_if_absent(component) for component in components), Decimal("0"))
    difference = draft.grand_total - computed

    if within_rounding_allowance(difference, term_count=stated_terms):
        return None

    return DraftDiscrepancyFinding(
        kind=DraftDiscrepancyKind.ARITHMETIC_CLOSURE,
        field="grand_total",
        detail=(
            f"the printed total {draft.grand_total} does not equal base plus cuota plus recargo plus "
            f"suplidos ({computed}); the document states a figure the components do not reach, so a "
            f"component was misread or the document carries one this draft cannot represent"
        ),
        expected=computed,
        observed=draft.grand_total,
    )


def _cash_closure_finding(draft: InvoiceDraft) -> DraftDiscrepancyFinding | None:
    """Check ``cash = total - retencion`` for internal consistency.

    Only meaningful when the document states both a total and a retención: the
    identity is what makes the withheld figure reconcilable against the money
    that actually moved, and with either half missing there is nothing to check.
    """
    if draft.grand_total is None or draft.retencion_amount is None:
        return None

    if draft.retencion_rate is None:
        return None

    expected_retencion = (draft.taxable_base or Decimal("0")) * draft.retencion_rate / Decimal("100")
    difference = draft.retencion_amount - expected_retencion
    if within_rounding_allowance(difference, term_count=2):
        return None

    return DraftDiscrepancyFinding(
        kind=DraftDiscrepancyKind.RATE_INCONSISTENT,
        field="retencion_amount",
        detail=(
            f"the stated retención {draft.retencion_amount} is not {draft.retencion_rate}% of the "
            f"taxable base ({expected_retencion}); the cash actually paid cannot be derived from "
            f"figures that disagree"
        ),
        expected=expected_retencion,
        observed=draft.retencion_amount,
    )


def _rate_consistency_findings(draft: InvoiceDraft) -> tuple[DraftDiscrepancyFinding, ...]:
    """Check each per-rate tier's own ``base * rate == cuota``."""
    findings: list[DraftDiscrepancyFinding] = []
    for entry in draft.iva_breakdown:
        if entry.iva_rate is None or entry.taxable_base is None or entry.iva_amount is None:
            continue
        expected = entry.taxable_base * entry.iva_rate / Decimal("100")
        difference = entry.iva_amount - expected
        if within_rounding_allowance(difference, term_count=2):
            continue
        findings.append(
            DraftDiscrepancyFinding(
                kind=DraftDiscrepancyKind.RATE_INCONSISTENT,
                field="iva_breakdown",
                detail=(
                    f"the tier charged at {entry.iva_rate}% states a cuota of {entry.iva_amount} on a "
                    f"base of {entry.taxable_base}, which should be {expected}; Modelo 303 declares "
                    f"cuota devengada per tier, so this tier declares the wrong figure"
                ),
                expected=expected,
                observed=entry.iva_amount,
            ),
        )
    return tuple(findings)


def _flat_rate_consistency_finding(draft: InvoiceDraft) -> DraftDiscrepancyFinding | None:
    """Check the flat ``base * rate == cuota`` triple against itself.

    The same identity :func:`_rate_consistency_findings` applies per tier,
    applied to the flat triple -- which until this existed was the one
    representation nothing checked. The per-tier check iterates
    ``iva_breakdown``, and only the STRUCTURED reader populates that; only the
    model-read lane populates a flat ``iva_rate``. The two representations are
    disjoint, so the unchecked one was exactly the one a model produced.

    What it catches is the multi-rate collapse. A document charging two rates
    has no flat representation: a reader that copies the printed total base and
    total cuota and then one of the two printed rates produces a draft whose
    total identity still HOLDS -- base plus cuota does equal the total -- while
    the rate it carries is wrong about half its own base, and that rate decides
    which Modelo 303 tier the base lands in. Measured: a 1000-at-21%-plus-
    1000-at-10% invoice read this way raised no finding at all.

    It reads no prose and needs no transcription, which is what keeps it
    precise: it asks only whether three figures the reader already produced are
    mutually consistent. The confounds are handled by the field split rather
    than by tolerance -- recargo carries its own rate and amount and is not
    inside ``iva_amount``, suplidos sit outside the base imponible in their own
    field, retención has its own identity above -- and an exempt or
    reverse-charge document states no rate or no cuota, so the identity does not
    run.

    Skipped when the breakdown carries more than one tier, because there the
    flat rate is legitimately not a single rate and the per-tier and sum checks
    already cover the figures. No producer populates both today; the guard
    states which representation wins before one can.
    """
    if len(draft.iva_breakdown) > 1:
        return None

    if draft.taxable_base is None or draft.iva_rate is None or draft.iva_amount is None:
        return None

    expected = draft.taxable_base * draft.iva_rate / Decimal("100")
    if within_rounding_allowance(draft.iva_amount - expected, term_count=2):
        return None

    return DraftDiscrepancyFinding(
        kind=DraftDiscrepancyKind.RATE_INCONSISTENT,
        field="iva_rate",
        detail=(
            f"the stated cuota {draft.iva_amount} is not {draft.iva_rate}% of the stated base "
            f"{draft.taxable_base} ({expected}); one flat rate cannot describe this document, so "
            f"either a figure was misread or the invoice charges more than one rate and the "
            f"per-rate split is missing -- Modelo 303 declares base and cuota devengada per tier, "
            f"so confirming this would file the whole base under the wrong one"
        ),
        expected=expected,
        observed=draft.iva_amount,
    )


def _breakdown_sum_findings(draft: InvoiceDraft) -> tuple[DraftDiscrepancyFinding, ...]:
    """Check the per-rate subtotals against the flat base and cuota."""
    if not draft.iva_breakdown:
        return ()

    findings: list[DraftDiscrepancyFinding] = []
    term_count = len(draft.iva_breakdown)

    if draft.taxable_base is not None and all(e.taxable_base is not None for e in draft.iva_breakdown):
        summed = sum((_zero_if_absent(e.taxable_base) for e in draft.iva_breakdown), Decimal("0"))
        if not within_rounding_allowance(draft.taxable_base - summed, term_count=term_count):
            findings.append(
                DraftDiscrepancyFinding(
                    kind=DraftDiscrepancyKind.BREAKDOWN_INCONSISTENT,
                    field="taxable_base",
                    detail=(
                        f"the per-rate bases sum to {summed} while the document states a flat taxable "
                        f"base of {draft.taxable_base}; these are two readings of one document and at "
                        f"least one is wrong"
                    ),
                    expected=summed,
                    observed=draft.taxable_base,
                ),
            )

    if draft.iva_amount is not None and all(e.iva_amount is not None for e in draft.iva_breakdown):
        summed = sum((_zero_if_absent(e.iva_amount) for e in draft.iva_breakdown), Decimal("0"))
        if not within_rounding_allowance(draft.iva_amount - summed, term_count=term_count):
            findings.append(
                DraftDiscrepancyFinding(
                    kind=DraftDiscrepancyKind.BREAKDOWN_INCONSISTENT,
                    field="iva_amount",
                    detail=(
                        f"the per-rate cuotas sum to {summed} while the document states a flat cuota "
                        f"of {draft.iva_amount}; these are two readings of one document and at least "
                        f"one is wrong"
                    ),
                    expected=summed,
                    observed=draft.iva_amount,
                ),
            )

    return tuple(findings)


def closure_findings(draft: InvoiceDraft) -> tuple[DraftDiscrepancyFinding, ...]:
    """Return every arithmetic-closure finding the draft's own figures raise.

    Deterministic and total: the same draft always yields the same findings, and
    an empty result means every identity that COULD be checked held -- never that
    the document is correct, because an identity with a missing term is not
    checked at all.

    Args:
        draft: The draft to check, carrying the figures the document stated.

    Returns:
        Findings in a stable order -- total closure, cash closure, flat rate
        consistency, per-tier rate consistency, then breakdown sums -- so an
        operator surface and a test both read them the same way.
    """
    findings: list[DraftDiscrepancyFinding] = []

    total_finding = _total_closure_finding(draft)
    if total_finding is not None:
        findings.append(total_finding)

    cash_finding = _cash_closure_finding(draft)
    if cash_finding is not None:
        findings.append(cash_finding)

    flat_rate_finding = _flat_rate_consistency_finding(draft)
    if flat_rate_finding is not None:
        findings.append(flat_rate_finding)

    findings.extend(_rate_consistency_findings(draft))
    findings.extend(_breakdown_sum_findings(draft))

    return tuple(findings)
