"""Turning a self-contradicting document into a finding the confirm gate refuses past.

The consumer of the legend axis's contradicted outcome. That axis
(:func:`~domain.iva.derive_category_from_regime_legend`) decides whether the
regime an issuer printed in words agrees with the tax the document charged; this
module does no deciding of its own. It reads the outcome as data and enrols it,
which is the whole reason the axis returns a typed record rather than a category
or ``None``.

**Why the judgement is not repeated here.** The statutory expectation lives on
:class:`~domain.iva.RegimeLegend` as ``expects_repercutido_line``, exactly so one
place decides what a mention implies. Re-testing that here would make two
authorities on the same question, and the second would drift the moment the
regulation's encoding changed -- the failure the legend table was introduced to
close. The axis also deliberately withholds the category on a contradiction, so
this module could not accidentally use the declared value even if it tried.

**Why it blocks rather than warns.** A contradicted document is wrong under every
reading available: either the mention was printed in error or the tax was charged
in error, and those lead to different declarations. That is unlike a doubtful
figure, where the document says one thing and the confidence in reading it is
what varies. Confirming past it silently picks a side, and the side picked
determines whether output IVA is declared at all.

**What is deliberately NOT decided here.** Which half is wrong. The finding names
the conflict and stops; the operator holds the document and is the only party who
can say whether the mention or the line does not belong.

See Also:
    :func:`~domain.iva.derive_category_from_regime_legend`
        The axis whose contradicted outcome this enrols.
    :data:`~application.ledger.confirmation_gate.BLOCKING_REASON_BY_DISCREPANCY_KIND`
        Where the finding's kind becomes a review-gate refusal.
    :func:`~application.ledger.closure_findings`
        The arithmetic siblings this finding sits beside, and is not one of.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...core.draft_discrepancy import DraftDiscrepancyKind
from ...domain.iva.legend_derivation import LegendDerivationOutcome, derive_category_from_regime_legend
from .evidence_draft import DraftDiscrepancyFinding

if TYPE_CHECKING:
    from .evidence_draft import InvoiceDraft

__all__ = ["draft_prints_a_repercutido_line", "regime_contradiction_finding"]


def draft_prints_a_repercutido_line(draft: InvoiceDraft) -> bool:
    """Whether the document charged Spanish output IVA on its face.

    A charged cuota is the decisive signal, and a stated positive rate is taken
    as one too: a document printing "IVA 21%" beside a reverse-charge mention
    contradicts itself whether or not the cuota was legible.

    Zero is deliberately not a repercutido line. A reverse-charge or exempt
    invoice may legitimately print a zero rate or a zero cuota to show that no
    tax was charged, and reading that as tax charged would turn the ordinary
    presentation of the very regimes this checks into a contradiction -- firing
    on exactly the documents it exists to respect.

    Args:
        draft: The draft carrying the figures the document stated.

    Returns:
        ``True`` when the document states positive output IVA.
    """
    if draft.iva_amount is not None and draft.iva_amount > 0:
        return True
    return draft.iva_rate is not None and draft.iva_rate > 0


def regime_contradiction_finding(draft: InvoiceDraft) -> DraftDiscrepancyFinding | None:
    """Return the finding a self-contradicting document raises, or ``None``.

    Deterministic and total: the same draft always yields the same answer, and
    ``None`` means the document did not contradict itself on this axis -- never
    that its regime is correct, because a document printing no mandated mention
    states no regime to check.

    Args:
        draft: The draft to check, carrying the transcribed mention and the tax
            figures the document stated.

    Returns:
        A :class:`~application.ledger.evidence_draft.DraftDiscrepancyFinding` when the printed
        mention and the charged tax cannot both be true, else ``None``.
    """
    derivation = derive_category_from_regime_legend(
        printed_legend=draft.regime_legend,
        has_repercutido_line=draft_prints_a_repercutido_line(draft),
    )
    if derivation.outcome is not LegendDerivationOutcome.CONTRADICTED:
        return None

    # `field` names the mention rather than the category. The category was never
    # established -- the axis withholds it precisely here -- so pointing at it
    # would send the operator to a value that does not exist. The mention is the
    # half of the conflict they can actually look at on the page.
    return DraftDiscrepancyFinding(
        kind=DraftDiscrepancyKind.REGIME_CONTRADICTED,
        field="regime_legend",
        detail=derivation.note,
    )
