"""One enumeration of everything a pending draft carries that blocks nothing.

Two advisories exist over a draft --- the party-attribution one and the
country-vocabulary one --- and each already knows how to say its own piece on the
one-document surface. What neither could say is the thing a QUEUE needs: not the
prose, but which KINDS this document carries, as a closed value a caller can
count, group and filter on.

**The queue is where a non-blocking condition is either seen or lost.** An
operator who never opens a document never meets an advisory attached only to
``review show``, and the conditions on this axis are exactly the ones that reach
the record without stopping anything --- so "reachable from the detail view" is
indistinguishable from unreachable for any document the operator had no reason to
open. Counting them on the queue row is what makes the reason to open it.

**One authority, two consumers.** The queue and the one-document surface derive
their kinds from this function rather than each classifying the advisories
themselves. A second derivation is a second answer: a queue that decides a draft
carries an attribution advisory while the detail view shows none sends the
operator to a document to look for something that is not there, and they stop
trusting the count.

The kinds are counted, never merged. A code only a registry commit can close and
a typo the operator fixes off the page are different work, and a single
has-advisories flag would make an operator who can only do one of them unable to
find the documents they can act on.

See Also:
    :func:`~application.ledger.party_attribution.party_attribution_advisory`
        The attribution advisory this projects.
    :func:`~application.ledger.country_vocabulary_advisory.country_vocabulary_advisory`
        The country-vocabulary advisory this projects.
    :class:`~core.ReviewAdvisoryKind`
        The closed axis the kinds are drawn from.
    :class:`~core.ConfirmationBlockReason`
        The blocking sibling axis, which answers the other half of a queue row.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from ...core import ReviewAdvisoryKind
from ...domain.iva import StatedCountryCodeStatus
from .country_vocabulary_advisory import country_vocabulary_advisory
from .party_attribution import party_attribution_advisory

if TYPE_CHECKING:
    from .evidence_draft import InvoiceDraft

__all__ = ["review_advisory_kinds"]

_COUNTRY_KIND: Final[dict[StatedCountryCodeStatus, ReviewAdvisoryKind]] = {
    StatedCountryCodeStatus.UNASSIGNED: ReviewAdvisoryKind.COUNTRY_CODE_UNASSIGNED,
    StatedCountryCodeStatus.UNCATALOGUED: ReviewAdvisoryKind.COUNTRY_CODE_UNCATALOGUED,
}
"""Which advisory kind each reported country-code status is.

A table rather than a branch because the mapping is the whole of the
correspondence, and because the country advisory's own reported-status set is
derived from the sentences it can say --- so a status that gains a sentence and
no entry here is a kind the queue would silently stop counting.
"""


def review_advisory_kinds(draft: InvoiceDraft) -> tuple[ReviewAdvisoryKind, ...]:
    """Return every non-blocking advisory kind one pending draft carries.

    Args:
        draft: The pending draft, exactly as the review surfaces hold it.

    Returns:
        The kinds present, each at most once and in a stable order: the
        attribution kind first, then the country kinds in the axis's own
        declaration order. Empty when the draft carries nothing advisory, which
        is an honest empty rather than a claim that the draft was not checked.

    Raises:
        IvaCatalogueError: When the bundled country vocabulary cannot be read,
            propagated on the terms the country advisory states --- a corrupt
            bundled table is a defect, not an unadvised draft.
    """
    kinds: list[ReviewAdvisoryKind] = []
    if party_attribution_advisory(draft) is not None:
        kinds.append(ReviewAdvisoryKind.PARTY_ATTRIBUTION)
    country = country_vocabulary_advisory(draft)
    if country is not None:
        # Ordered by the status table rather than by the parties' document order:
        # a queue row whose kinds reorder because two parties swapped places is a
        # row an operator cannot compare against yesterday's.
        kinds.extend(kind for status, kind in _COUNTRY_KIND.items() if country.by_status(status))
    return tuple(kinds)
