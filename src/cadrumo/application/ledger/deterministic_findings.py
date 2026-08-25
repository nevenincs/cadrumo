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

**Every check here BLOCKS.** A finding raised by this list carries a
:class:`~core.DraftDiscrepancyKind`, and every member of that axis maps to a
confirmation block reason, so enrolling a check here is deciding the operator
must answer it individually before confirming. A deterministic condition worth
reporting but not worth refusing on therefore belongs on the advisory channel
instead -- :func:`~application.ledger.country_vocabulary_advisory.country_vocabulary_advisory` is the worked
example, and it left this list for exactly that reason: the bundled country
vocabulary carries a bounded subset of jurisdictions, so blocking on a code it
does not carry refuses correct documents for a gap in our own data.

Anchor verification is deliberately NOT here. It needs an independently produced
transcription to check a claimed printed form against, which a structured record
does not have and does not need -- its values are read from the document's own
machine-readable fields rather than proposed by a reader that might be wrong
about what the page said.

See Also:
    :func:`~application.ledger.closure_findings.closure_findings`
        The arithmetic identities, and the bulk of what runs here.
    :func:`~application.ledger.regime_contradiction.regime_contradiction_finding`
        The declared-regime-versus-charged-tax check.
    :func:`~application.ledger.grounded_reading.ground_draft_against_transcription`
        The grounding pass, which calls this and adds the transcription-dependent
        checks a structured record has no use for.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple

from .closure_findings import closure_findings
from .postal_shape_finding import postal_shape_findings
from .regime_contradiction import regime_contradiction_finding

if TYPE_CHECKING:
    from collections.abc import Callable

    from .evidence_draft import DraftDiscrepancyFinding, InvoiceDraft

__all__ = ["DETERMINISTIC_CHECKS", "DeterministicCheck", "deterministic_check_names", "deterministic_findings"]


class DeterministicCheck(NamedTuple):
    """One check, with the name a record stamps it under.

    The name is the CHECK's, not its findings'. The closure check raises three
    different discrepancy kinds, so naming it after any one of them would
    describe a third of what it does.

    Attributes:
        name: Stable identifier. Changing it changes what every later record
            claims ran, so it is renamed only when the check itself changes
            meaning.
        run: Runs the check and returns its findings, empty when it holds.
    """

    name: str
    run: Callable[[InvoiceDraft], tuple[DraftDiscrepancyFinding, ...]]


def _closure_identities(draft: InvoiceDraft) -> tuple[DraftDiscrepancyFinding, ...]:
    return closure_findings(draft)


def _regime_contradiction(draft: InvoiceDraft) -> tuple[DraftDiscrepancyFinding, ...]:
    """Adapt the single-or-nothing check onto the uniform check signature."""
    finding = regime_contradiction_finding(draft)
    return () if finding is None else (finding,)


def _postal_code_shape(draft: InvoiceDraft) -> tuple[DraftDiscrepancyFinding, ...]:
    return postal_shape_findings(draft)


DETERMINISTIC_CHECKS: tuple[DeterministicCheck, ...] = (
    DeterministicCheck("closure_identities", _closure_identities),
    DeterministicCheck("regime_contradiction", _regime_contradiction),
    DeterministicCheck("postal_code_shape", _postal_code_shape),
)
"""Every draft-only check, as data rather than as a sequence of calls.

Declared once and used twice: :func:`deterministic_findings` runs them, and
:func:`deterministic_check_names` names them for the record that stamps which
ran. A hand-written list of names beside this one would be a second declaration
of the same set, drifting the moment a check is added -- which is the defect this
module was created to close, returning one layer up in the record.
"""


def deterministic_check_names() -> tuple[str, ...]:
    """Return the name of every check that runs, in declaration order.

    Derived from :data:`DETERMINISTIC_CHECKS` rather than restated, so a check
    added there reaches every record without anyone remembering a second place.

    Returns:
        The check names, in the order they run.
    """
    return tuple(check.name for check in DETERMINISTIC_CHECKS)


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
    findings: list[DraftDiscrepancyFinding] = []
    for check in DETERMINISTIC_CHECKS:
        findings.extend(check.run(draft))
    return tuple(findings)
