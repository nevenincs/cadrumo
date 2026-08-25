"""Name the country code a party stated when it named no country, without blocking.

The country rung matches against a bounded vocabulary, so a code outside it
fires nothing and the ladder walks on. That refusal is correct and it is silent:
the operator sees a territory that did not resolve, with no way to tell that the
document did state something and that the something was ``XX``. A blank where a
typo lives is exactly the reading an operator clears without acting.

**Advisory, not blocking, and the vocabulary's own size is the reason.** The
bundled country vocabulary carries a bounded subset of the world's
jurisdictions. A stated code outside it is therefore an ordinary event on a live
population -- a Thai supplier, a Kenyan customer -- and refusing to confirm the
draft would make every such document unfileable until somebody committed to the
registry. That is alert fatigue on exactly the operators whose documents are
correct, and an alert only earns attention if every firing is a defect the
operator can act on. What the operator needs here is to be told, in the words
that name the fix, and left free to proceed.

Nothing is bought back by blocking, because the under-declaration this axis was
narrowed to close is already shut one layer down: an unresolved country yields
no ``customer_residency``, the classification criteria do not assemble, and the
zero-rated export category is unreachable. The refusal that matters is the
assembly's, and it is untouched by this module's severity.

**Two kinds, because the two failures have different owners.** A code in an ISO
3166-1 user-assigned range -- ``AA``, ``QM``-``QZ``, ``XA``-``XZ`` and ``ZZ`` in
alpha-2, and their alpha-3 counterparts ``AAA``-``AAZ``, ``QMA``-``QZZ``,
``XAA``-``XZZ`` and ``ZZA``-``ZZZ`` -- denotes no country by construction, so
the document is wrong and the operator can fix it off the page. Both spellings,
because a structured record states either and this module is asked about the
record's own token: naming only the alpha-2 pairs described the axis as half of
what it judges, on the spelling Facturae states. A code outside those ranges that the bundled vocabulary
simply does not carry may name a real jurisdiction, so the data is ours to fix
and re-reading the document will settle nothing. Reporting both as "unrecognised
country" would send the operator to look for a typo that is not there, on
exactly the population where the fix is a registry commit. The distinction
survives the move to the advisory channel: each kind carries its own notice code
and its own sentence, so a JSON consumer can route them apart.

**The token is read from the field that keeps it, not from the resolved one.** A
draft's ``*_country_code`` is contracted alpha-2 and is populated only where the
bundled vocabulary placed the record's token, so it is empty for precisely the
codes this module exists to report -- and reading it made every firing above
unreachable from a real document while the module's own tests, which set that
field by hand, stayed green. The verbatim token lives on
:attr:`~application.ledger.evidence_draft.InvoiceDraft.supplier_stated_country_code` and its
sibling, and that is what is asked. A structured record stating ``THA`` for a
Thai supplier was otherwise byte-identical, all the way to the operator, to one
carrying no address block at all.

**The judgement is borrowed, not restated.** Which bucket a code falls in is
asked of :func:`~domain.iva.record_country_code_status` -- the record-token sibling of
the printed-value axis, which admits the alpha-3 spelling Facturae states and is
the one authority the confirm path's relief guard asks the same question of --
and whether the country already settled the territory is asked of
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
    :func:`~application.ledger.party_attribution.party_attribution_advisory`
        The sibling advisory, on the same non-blocking channel and projected by
        the same review surface.
    :func:`~domain.iva.record_country_code_status`
        The authority on which of the two kinds a stated code is.
    :class:`~core.DraftDiscrepancyKind`
        The blocking axis this deliberately does not join.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from pydantic import BaseModel, Field

from ...core import STRICT_FROZEN_CONFIG
from ...domain.iva import (
    StatedCountryCodeStatus,
    country_code_for_printed_country_name,
    record_country_code_status,
    territorial_scope_for_country,
)
from .party_attribution import PartyAddress, party_addresses

if TYPE_CHECKING:
    from .evidence_draft import InvoiceDraft

__all__ = [
    "COUNTRY_VOCABULARY_ADVISED_STATUSES",
    "CountryVocabularyAdvisory",
    "CountryVocabularyWarning",
    "country_vocabulary_advisory",
]


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

COUNTRY_VOCABULARY_ADVISED_STATUSES: Final[frozenset[StatedCountryCodeStatus]] = frozenset(_DETAIL_BY_STATUS)
"""The statuses this advisory reports, derived from the sentences it can say.

``CATALOGUED`` is deliberately outside rather than mapped to anything: a code the
vocabulary carries either settled the territory or refused it for Spain's own
documented reason, and neither is worth the operator's attention. Derived from
the detail table rather than hand-listed, so a status that gains a sentence is
reported by construction and one that does not cannot be advised wordlessly.
"""


class CountryVocabularyWarning(BaseModel):
    """One party's stated country code that named no country, and which kind it is.

    Attributes:
        role: The side of the document the code was stated for, in the terms the
            operator reads the invoice in -- issuing or billed.
        field: The draft field carrying the code -- the verbatim ``*_stated_``
            one, never the resolved sibling, because the resolved sibling is
            empty exactly when this warning exists. The review surface emits a
            row per draft field, so the operator goes straight to the row that
            shows the token rather than to the blank one beside it.
        stated_code: The code as the status axis matched it: stripped and
            upper-cased. Quoted rather than described, because an operator shown
            ``XX`` sees the placeholder at a glance while one told "the country
            did not resolve" learns nothing they can act on.
        status: Which of the two failures this is. The machine-readable half of
            the distinction the advisory exists to preserve: a typo the operator
            fixes off the page, or a gap in our vocabulary that a registry commit
            closes.
        detail: The operator-facing sentence, naming the code and its kind.
    """

    model_config = STRICT_FROZEN_CONFIG

    role: str = Field(min_length=1)
    field: str = Field(min_length=1)
    stated_code: str = Field(min_length=1)
    status: StatedCountryCodeStatus
    detail: str = Field(min_length=1)


class CountryVocabularyAdvisory(BaseModel):
    """Every party on one draft stating a country code that named no country.

    Attributes:
        parties: One entry per affected party, in document order. A draft with no
            affected party produces no advisory at all rather than an empty one,
            so a caller cannot surface a warning about nothing.
    """

    model_config = STRICT_FROZEN_CONFIG

    parties: tuple[CountryVocabularyWarning, ...] = Field(min_length=1)

    @property
    def fields(self) -> tuple[str, ...]:
        """Return every affected draft field, in document order."""
        return tuple(party.field for party in self.parties)

    def by_status(self, status: StatedCountryCodeStatus) -> tuple[CountryVocabularyWarning, ...]:
        """Return the warnings of one kind, in document order.

        The projection the review surface needs to emit one notice per kind.
        Offered here rather than filtered at the call site so a second consumer
        cannot group the two kinds together and undo the split.

        Args:
            status: The kind to select.

        Returns:
            The matching warnings, empty when this draft raised none of that kind.
        """
        return tuple(party for party in self.parties if party.status is status)


def _territory_already_settled(draft: InvoiceDraft, party: PartyAddress) -> bool:
    """Return whether this party's country evidence settled its territory anyway.

    Both spellings are consulted in the ladder's own order: the printed NAME
    first, because that is the form an address block prints, and the stated code
    only where no name resolved. A document printing "Alemania" beside a
    country-code field holding ``XX`` is established, and reporting its code
    would spend the operator's attention on a value nothing consumed.

    Spain answers ``False``, as it does everywhere on this axis: it names the
    Member State while the IVA territory inside it stays undetermined.
    """
    from_name = country_code_for_printed_country_name(getattr(draft, party.country_field, None))
    if territorial_scope_for_country(from_name) is not None:
        return True
    return territorial_scope_for_country(getattr(draft, party.country_code_field, None)) is not None


def country_vocabulary_advisory(draft: InvoiceDraft) -> CountryVocabularyAdvisory | None:
    """Return what an operator must be told about this draft's country codes, or ``None``.

    Reports a party only where the country evidence did not settle that party's
    territory some other way, so every entry names a code that was actually
    needed.

    Non-blocking by construction: the result is an advisory model with no route
    into :func:`~application.ledger.confirmation_gate.confirmation_blockers`, and the conditions it
    reports have no member on :class:`~core.DraftDiscrepancyKind`. Making one
    block again takes a deliberate change to that axis, not an edit here.

    Args:
        draft: The draft to check, carrying each party's stated country code and
            printed country name as the reader recovered them.

    Returns:
        The advisory, or ``None`` when every stated code is catalogued, when the
        territories were settled anyway, or when no code was stated at all -- an
        absent field is an honest absence and is not reported as a wrong one.

    Raises:
        IvaCatalogueError: When the bundled country vocabulary cannot be read.
            Propagated rather than softened, on the terms the resolver states:
            a corrupt bundled table is a defect, not an unestablished party.
    """
    warnings: list[CountryVocabularyWarning] = []
    for party in party_addresses():
        stated: str | None = getattr(draft, party.stated_country_code_field, None)
        status = record_country_code_status(stated)
        if status is None or status not in COUNTRY_VOCABULARY_ADVISED_STATUSES:
            continue
        if _territory_already_settled(draft, party):
            continue
        # The status is non-``None``, so the field holds a token the record
        # stated as a country code and the normalisation is total.
        code = str(stated).strip().upper()
        warnings.append(
            CountryVocabularyWarning(
                role=party.operator_role,
                field=party.stated_country_code_field,
                stated_code=code,
                status=status,
                detail=(f"the {party.operator_role} party's country code {code!r} {_DETAIL_BY_STATUS[status]}"),
            ),
        )
    if not warnings:
        return None
    return CountryVocabularyAdvisory(parties=tuple(warnings))
