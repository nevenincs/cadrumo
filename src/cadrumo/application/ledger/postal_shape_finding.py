"""Say so when a party's postal code field does not hold a postal code.

The free-text validator keeps whatever the reader put in the field, trimmed and
otherwise untouched, and that permissiveness is deliberate: dropping an
unreadable value would destroy the printed anchor the operator reviews, leaving
them a blank field and nothing to correct it against. So an address line the
reader lifted whole -- ``"Calle Mayor 3, 28013 Madrid"`` -- reaches the draft and
the operator payload intact, under a label that says *postal code*, and reads as
one until somebody looks.

Nothing unsafe follows from it, which is why this is a visibility problem rather
than a correctness one:
:func:`~domain.iva.territorial_scope_for_spanish_postal_code` answers ``None``
for anything that is not five digits rather than defaulting to the peninsula, so
an unreadable code costs an answer and never invents one.

**The judgement is borrowed, not restated.** Whether a code is readable is asked
by handing it to that resolver and seeing whether it answers; whether the country
already settled the territory is asked of
:func:`~domain.iva.territorial_scope_for_country`. Neither rule is spelled here.
A second copy of "five digits" sitting upstream of the authority that owns it is
the drift this module is placed to avoid, and it would be the weaker copy.

**Why it does not fire on every non-numeric code.** A British ``SW1A 1AA`` and a
Dutch ``1011 AB`` are correctly printed postal codes that are not five digits,
and flagging them would refuse confirmation on a large, entirely legitimate
population for no gain -- every discrepancy kind blocks by construction. Alert
fatigue is a real failure mode: a check that fires mostly on documents that are
fine teaches an operator to clear it without reading, and then it is worth less
than nothing on the one document that mattered.

So the question asked is not *is this five digits* but *does this field being
unreadable cost anything*. The postal code is the SUB-national evidence, consulted
only where the country did not settle the territory on its own. A party whose
printed country resolves -- any country but Spain -- is already established, and
its postal code is decorative. Spain deliberately resolves to no scope, because
the State names the Member State while Canarias, Ceuta y Melilla and the
peninsula stay undecided inside it; a party with no country printed is unsettled
for the plainer reason. Those two are exactly the parties whose postal code was
load-bearing, and exactly the ones this reports.

See Also:
    :func:`~application.ledger.deterministic_findings`
        The one list this check is enrolled in, which both readers call.
    :func:`~domain.iva.territorial_scope_for_spanish_postal_code`
        The authority on whether a printed code can be read at all.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...core.draft_discrepancy import DraftDiscrepancyKind
from ...domain.iva.establishment import (
    country_code_for_printed_country_name,
    territorial_scope_for_country,
    territorial_scope_for_spanish_postal_code,
)
from .party_attribution import party_addresses

if TYPE_CHECKING:
    from .invoice_draft_records import DraftDiscrepancyFinding, InvoiceDraft

__all__ = ["postal_shape_findings"]


def _territory_already_settled(printed_country: str | None) -> bool:
    """Return whether the printed country settles this party's territory alone.

    Spain answers ``False`` deliberately: it names the Member State while the
    IVA territory inside it stays undetermined, which is the whole reason a
    postal code is consulted. An unrecognised or absent country also answers
    ``False`` -- nothing was settled -- rather than being treated as settled by
    default, which would suppress the report for the party we know least about.
    """
    code = country_code_for_printed_country_name(printed_country)
    return territorial_scope_for_country(code) is not None


def postal_shape_findings(draft: InvoiceDraft) -> tuple[DraftDiscrepancyFinding, ...]:
    """Return a finding per party whose postal code was populated but unreadable.

    Only where the country did not already settle that party's territory, so
    every finding names a code that was actually needed.

    Args:
        draft: The draft to check, carrying each party's printed postal code and
            printed country as the reader recovered them.

    Returns:
        The findings, in party declaration order. Empty when every populated
        code reads, when the countries settled the territories, or when no code
        was recovered at all -- an absent field is an honest absence and is not
        reported as a misread one.
    """
    # Imported at call time for the cycle-break reason the sibling checks use:
    # the draft module reaches the parsers and the reading package, so binding it
    # at module scope would make this leaf pay for all of it. Read exactly as if
    # it were written at module scope.
    from .invoice_draft_records import DraftDiscrepancyFinding

    findings: list[DraftDiscrepancyFinding] = []
    for party in party_addresses():
        raw_printed = getattr(draft, party.postal_field, None)
        printed: str | None = raw_printed if isinstance(raw_printed, str) else None
        if printed is None or not printed.strip():
            continue
        if territorial_scope_for_spanish_postal_code(printed) is not None:
            continue
        if _territory_already_settled(getattr(draft, party.country_field, None)):
            continue
        findings.append(
            DraftDiscrepancyFinding(
                kind=DraftDiscrepancyKind.POSTAL_CODE_UNREADABLE,
                field=party.postal_field,
                # Quotes what the field actually holds. An operator told only
                # that a postal code is invalid learns nothing they can act on;
                # one shown the printed text beside what was expected can see at
                # a glance that an address line landed in the wrong slot, and
                # can read the correct code straight out of it.
                detail=(
                    f"the {party.operator_role} party's postal code field holds {printed.strip()!r}, which is not a "
                    f"five-digit postal code, and its printed country did not settle where the party is "
                    f"established; the Spanish IVA territory therefore stays undetermined"
                ),
            ),
        )
    return tuple(findings)
