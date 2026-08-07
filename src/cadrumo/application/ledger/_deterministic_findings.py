"""Every check that needs only the draft, in one place both readers call.

The checks here ask nothing of a transcription, a model or a network: they read
the figures and the mention the document itself carried, and they are the same
questions whatever path produced the draft. Collecting them behind one call is
the structural half of a defect this closes.

**The defect.** The deterministic checks were reachable from the grounded reading
path alone. A structured e-invoice -- Facturae, CII, UBL -- is read exactly and
returns straight from its own reader, so it never passed through that assembly:
arithmetic closure, rate consistency, breakdown sums and the regime contradiction
were all structurally unreachable for it. A structured invoice whose base plus
cuota did not equal its total confirmed clean, and so did one printing a
reverse-charge mention beside a charged cuota.

The inversion is worth stating plainly, because the routing comment that produced
it is otherwise correct: a structured document reaches no model, which makes
prompt injection categorically impossible for it. That is true and it is good
design. What does not follow is that it needs no checking. Being unable to be
LIED to is a different property from being RIGHT -- arithmetic that does not
close is not an injection, it is a wrong invoice, and the most machine-readable
documents in the corpus were getting the least scrutiny.

**Why a shared function rather than a second call site.** Two call sites listing
the checks by hand is the same defect one refactor later: the next check lands on
whichever path its author had in mind, and the other silently keeps confirming
clean. One list means adding a check reaches every reader by construction.

Anchor verification is deliberately NOT here. It needs an independently produced
transcription to check a claimed printed form against, which a structured record
does not have and does not need -- its values are read from the document's own
machine-readable fields rather than proposed by a reader that might be wrong
about what the page said.

See Also:
    :func:`~application.ledger.closure_findings`
        The arithmetic identities, and the bulk of what runs here.
    :func:`~application.ledger.regime_contradiction_finding`
        The declared-regime-versus-charged-tax check.
    :func:`~application.ledger.ground_draft_against_transcription`
        The grounding pass, which calls this and adds the transcription-dependent
        checks a structured record has no use for.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ._closure_findings import closure_findings
from ._regime_contradiction import regime_contradiction_finding

if TYPE_CHECKING:
    from ._evidence_draft import DraftDiscrepancyFinding, InvoiceDraft

__all__ = ["deterministic_findings"]


def deterministic_findings(draft: InvoiceDraft) -> tuple[DraftDiscrepancyFinding, ...]:
    """Return every finding the draft's own contents raise, whatever read it.

    Deterministic and total: the same draft always yields the same findings, and
    an empty result means every check that COULD run held -- never that the
    document is correct, because a check whose inputs are absent does not run at
    all.

    Args:
        draft: The draft to check, carrying the figures and the mention the
            document stated.

    Returns:
        The arithmetic findings in their established order, then the regime
        contradiction. Stable, so an operator surface and a test read them the
        same way.
    """
    findings = list(closure_findings(draft))

    contradiction = regime_contradiction_finding(draft)
    if contradiction is not None:
        findings.append(contradiction)

    return tuple(findings)
