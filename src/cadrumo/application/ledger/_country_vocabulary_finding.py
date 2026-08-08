"""Name the country code a party stated when it named no country.

The country rung matches against a bounded vocabulary, so a code outside it
fires nothing and the ladder walks on. That refusal is correct and it is silent:
the operator sees a territory that did not resolve, with no way to tell that the
document did state something and that the something was ``XX``. A blank where a
typo lives is exactly the reading an operator clears without acting.

**Two kinds, because the two failures have different owners.** A code in an ISO
3166-1 user-assigned range -- ``AA``, ``QM``-``QZ``, ``XA``-``XZ``, ``ZZ`` --
denotes no country by construction, so the document is wrong and the operator
can fix it off the page. A code outside those ranges that the bundled vocabulary
simply does not carry may name a real jurisdiction, so the data is ours to fix
and re-reading the document will settle nothing. Reporting both as "unrecognised
country" would send the operator to look for a typo that is not there, on
exactly the population where the fix is a registry commit.

**The judgement is borrowed, not restated.** Which bucket a code falls in is
asked of :func:`~domain.iva.stated_country_code_status`, and whether the country
already settled the territory is asked of
:func:`~domain.iva.territorial_scope_for_country`. Neither rule is spelled here.
A second copy of the user-assigned ranges sitting upstream of the authority that
owns them is the drift this module is placed to avoid, and it would be the
weaker copy.

**Why it does not fire on every unresolved country.** A party whose country
field is empty raises nothing: an absent value is an honest absence, already
reported as a missing classifier input, and naming it here would duplicate that
in a shape that reads like a document defect. A party whose field holds
something that is not an alpha-2 code at all raises nothing either -- the status
axis declines to call an address line a bad country code, because a string
nobody claimed was a country is not a country the issuer got wrong.

So the question asked is not *did the country resolve* but *did the document
state a code that named nothing, where naming something would have mattered*.

See Also:
    :func:`~application.ledger.deterministic_findings`
        The one list this check is enrolled in, which both readers call.
    :func:`~domain.iva.stated_country_code_status`
        The authority on which of the two kinds a stated code is.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, NamedTuple

from ...core import DraftDiscrepancyKind
from ...domain.iva import (
    StatedCountryCodeStatus,
    country_code_for_printed_country_name,
    stated_country_code_status,
    territorial_scope_for_country,
)

if TYPE_CHECKING:
    from ._evidence_draft import DraftDiscrepancyFinding, InvoiceDraft

__all__ = ["country_vocabulary_findings"]


class _Party(NamedTuple):
    """One side of the document, named by the fields that state its country."""

    code_field: str
    name_field: str
    role: str


_PARTIES: Final[tuple[_Party, ...]] = (
    _Party("supplier_country_code", "supplier_country", "issuing"),
    _Party("customer_country_code", "customer_country", "billed"),
)
"""Both sides, because establishment is asked of each party independently.

Checking only the supplier would pass every document whose CUSTOMER carried the
unassigned code -- and on an invoice the filer issued, the customer IS the
counterparty whose territory decides whether the operation is an export.
"""

_DETAIL_BY_STATUS: Final[dict[StatedCountryCodeStatus, str]] = {
    StatedCountryCodeStatus.UNASSIGNED: (
        "is reserved by ISO 3166-1 to name no country at all, so it establishes nothing about where "
        "this party is; it is the form a placeholder or a truncated field takes"
    ),
    StatedCountryCodeStatus.UNCATALOGUED: (
        "is not carried by this system's country vocabulary, so nothing can yet be said about where "
        "this party is established; the country may be real and the vocabulary incomplete"
    ),
}
"""What each kind means, in the operator's terms rather than the axis's.

Keyed on the status rather than branched at the call site so the two sentences
sit beside each other and stay distinguishable to the reader who maintains them
-- the whole value of splitting the kinds is that the operator is told which
fix applies.
"""

_KIND_BY_STATUS: Final[dict[StatedCountryCodeStatus, DraftDiscrepancyKind]] = {
    StatedCountryCodeStatus.UNASSIGNED: DraftDiscrepancyKind.COUNTRY_CODE_UNASSIGNED,
    StatedCountryCodeStatus.UNCATALOGUED: DraftDiscrepancyKind.COUNTRY_CODE_UNCATALOGUED,
}
"""The reportable statuses, and the kind each raises.

``CATALOGUED`` is deliberately absent rather than mapped to anything: a code the
vocabulary carries either settled the territory or refused it for Spain's own
documented reason, and neither is a finding.
"""


def _territory_already_settled(draft: InvoiceDraft, party: _Party) -> bool:
    """Return whether this party's country evidence settled its territory anyway.

    Both spellings are consulted in the ladder's own order: the printed NAME
    first, because that is the form an address block prints, and the stated code
    only where no name resolved. A document printing "Alemania" beside a
    country-code field holding ``XX`` is established, and reporting its code
    would spend the operator's attention on a value nothing consumed.

    Spain answers ``False``, as it does everywhere on this axis: it names the
    Member State while the IVA territory inside it stays undetermined.
    """
    from_name = country_code_for_printed_country_name(getattr(draft, party.name_field, None))
    if territorial_scope_for_country(from_name) is not None:
        return True
    return territorial_scope_for_country(getattr(draft, party.code_field, None)) is not None


def country_vocabulary_findings(draft: InvoiceDraft) -> tuple[DraftDiscrepancyFinding, ...]:
    """Return a finding per party stating a country code that names no country.

    Only where the country evidence did not settle that party's territory some
    other way, so every finding names a code that was actually needed.

    Args:
        draft: The draft to check, carrying each party's stated country code and
            printed country name as the reader recovered them.

    Returns:
        The findings, in party declaration order. Empty when every stated code
        is catalogued, when the territories were settled anyway, or when no code
        was stated at all -- an absent field is an honest absence and is not
        reported as a wrong one.

    Raises:
        IvaCatalogueError: When the bundled country vocabulary cannot be read.
            Propagated rather than softened, on the terms the resolver states:
            a corrupt bundled table is a defect, not an unestablished party.
    """
    # Imported at call time for the cycle-break reason the sibling checks use:
    # the draft module reaches the parsers and the reading package, so binding it
    # at module scope would make this leaf pay for all of it. Read exactly as if
    # it were written at module scope.
    from ._evidence_draft import DraftDiscrepancyFinding

    findings: list[DraftDiscrepancyFinding] = []
    for party in _PARTIES:
        stated: str | None = getattr(draft, party.code_field, None)
        status = stated_country_code_status(stated)
        if status is None or status not in _KIND_BY_STATUS:
            continue
        if _territory_already_settled(draft, party):
            continue
        findings.append(
            DraftDiscrepancyFinding(
                kind=_KIND_BY_STATUS[status],
                field=party.code_field,
                # Quotes the string the field actually holds, in the form the
                # axis matched it under. An operator told only that a country
                # did not resolve learns nothing they can act on; one shown
                # `'XX'` sees the placeholder at a glance, and one shown a real
                # code knows to ask for the vocabulary rather than re-read the
                # page. The status is non-``None``, so the field holds a
                # well-formed alpha-2 code and the normalisation is total.
                detail=(
                    f"the {party.role} party's country code {str(stated).strip().upper()!r} {_DETAIL_BY_STATUS[status]}"
                ),
            ),
        )
    return tuple(findings)
