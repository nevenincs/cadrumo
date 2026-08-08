"""Stamp the address values whose party attribution nothing verifies, and say so.

Party attribution is the question of WHICH PARTY a value belongs to, and it is a
separate axis from whether the value was read correctly. Every anchor check in
this package answers the second question: the printed form is searched in an
independently produced transcription, and a value that cannot be pointed at is
refused. None of that touches the first. A supplier's postal code copied exactly
off the page and filed under the customer passes every one of those checks,
because it IS on the page and it IS what it says it is.

For the identity fields the attribution question has a real answer already:
the reader quotes the printed heading that assigns an identifier to a party,
that excerpt is checked against the transcription like any other anchor, and an
identity left with no surviving evidence does not resolve. That resolver's
candidate set is the two tax-id fields, so the answer stops there -- while the
establishment ladder consumes each party's postal code and printed country as
well, and nothing in the system checks the reader's assignment of those.

**The failure the stamp exists for is silent and total.** A clean
supplier/customer transposition of two address blocks yields a draft that is
internally consistent, anchored throughout, blocking nothing -- and places both
parties in territories neither is established in, which the criteria then consume
as an established fact. There is no red anywhere.

**This module is the honest interim, not the fix.** The fix is deterministic
co-location: an address block containing a role-evidenced identity anchors the
whole block to that party, and its postal and country values inherit attribution
by containment. Until that lands, the affected values say on their face that
their attribution is unchecked, and the operator is told at the review gate --
so the gap cannot read as closed while it is open. When co-location lands, an
attributed value simply stops being stamped here; the field, the advisory and the
surfaces all keep their shape.

See Also:
    :class:`~application.ledger.FieldProvenance`
        The per-field envelope the stamp lives on, beside the anchor and role
        evidence it sits alongside.
    :func:`~application.ledger.scope_printed_evidence_would_establish`
        The domain reading the advisory quotes when it names a territory.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, NamedTuple

from pydantic import BaseModel, Field

from ...core import STRICT_FROZEN_CONFIG, FieldOrigin

# Imported at RUNTIME rather than under ``TYPE_CHECKING``: the scope annotates a
# pydantic field, so a name visible only to the type checker leaves the model
# undefined at construction. The import is already paid for by the ladder this
# module quotes, which binds the same package at its own module scope.
from ...domain.iva import IvaTerritorialScope
from ._establishment_ladder import scope_printed_evidence_would_establish

if TYPE_CHECKING:
    from ._evidence_draft import FieldProvenance, InvoiceDraft

__all__ = [
    "ATTRIBUTION_ESTABLISHING_ORIGINS",
    "PARTY_ATTRIBUTED_ADDRESS_FIELDS",
    "PartyAddress",
    "PartyAttributionAdvisory",
    "PartyAttributionWarning",
    "party_addresses",
    "party_attribution_advisory",
    "stamp_unverified_party_attribution",
]


class PartyAddress(NamedTuple):
    """One side of the document, named by the address fields that describe it."""

    role: str
    tax_id_field: str
    postal_field: str
    country_field: str
    country_code_field: str


_PARTY_ADDRESSES: Final[tuple[PartyAddress, ...]] = (
    PartyAddress("supplier", "supplier_tax_id", "supplier_postal_code", "supplier_country", "supplier_country_code"),
    PartyAddress("customer", "customer_tax_id", "customer_postal_code", "customer_country", "customer_country_code"),
)
"""Both sides, because the transposition this guards against swaps exactly two.

Naming only the supplier would leave the customer's block unstamped, and on an
invoice the filer issued the CUSTOMER is the counterparty -- the side the
classification's territory question is actually asked of.
"""

PARTY_ATTRIBUTED_ADDRESS_FIELDS: Final[frozenset[str]] = frozenset(
    field for party in _PARTY_ADDRESSES for field in (party.postal_field, party.country_field, party.country_code_field)
)
"""The per-party address fields the establishment ladder consumes.

Derived from the party table rather than hand-listed, so adding a side or an
address field to that table cannot leave a consumed value unstamped.

The tax-id fields are deliberately absent: attribution for those is answered by
role evidence and enforced by the identity resolver, which refuses a lone
unevidenced survivor. Stamping them too would report a checked property as
unchecked, which trains an operator to dismiss the stamp everywhere.
"""

ATTRIBUTION_ESTABLISHING_ORIGINS: Final[frozenset[FieldOrigin]] = frozenset(
    {FieldOrigin.EXACT_STRUCTURED, FieldOrigin.OPERATOR, FieldOrigin.DERIVED},
)
"""Origins that answer the attribution question by the way they obtain the value.

A named set rather than an inline test, and stated as the ESTABLISHING side on
purpose: everything not listed is stamped, so an origin added later is treated as
unverified until somebody decides otherwise. The inverse spelling would admit a
new reader silently.

``EXACT_STRUCTURED`` establishes attribution because the record's own element
path names the party -- ``SellerParty/AddressInSpain/PostCode`` is not a reader's
guess about whose code it is. ``OPERATOR`` establishes it because a person typed
the value into a field that names the party, which is the attribution. ``DERIVED``
establishes it because a derived value cites the inputs it followed from, and
those inputs carry their own answer.
"""


class PartyAttributionWarning(BaseModel):
    """The unverified address values of one party, and where they would place it.

    Attributes:
        role: The party the values were filed under -- the assignment that is
            itself unverified, which is why it is named rather than assumed.
        fields: The party's address fields carrying the stamp, in declaration
            order.
        scope_if_attributed: The territory these values would settle if the
            attribution were correct, or ``None`` where they settle nothing.
            Conditional in the strongest sense: it is what the printed rungs
            read off values whose ownership is exactly what nothing verified.
    """

    model_config = STRICT_FROZEN_CONFIG

    role: str = Field(min_length=1)
    fields: tuple[str, ...] = ()
    scope_if_attributed: IvaTerritorialScope | None = None


class PartyAttributionAdvisory(BaseModel):
    """Every party on one draft carrying address values of unverified attribution.

    Attributes:
        parties: One entry per affected party, in document order. A draft with
            no affected party produces no advisory at all rather than an empty
            one, so a caller cannot surface a warning about nothing.
    """

    model_config = STRICT_FROZEN_CONFIG

    parties: tuple[PartyAttributionWarning, ...] = Field(min_length=1)

    @property
    def fields(self) -> tuple[str, ...]:
        """Return every stamped field across all parties, in document order."""
        return tuple(field for party in self.parties for field in party.fields)


def party_addresses() -> tuple[PartyAddress, ...]:
    """Return both parties and the address fields that describe each.

    The one party table, exposed so the co-location resolver partitions the
    document over exactly the sides this module stamps. Two tables would be the
    drift that lets a resolver attribute a field nothing stamps, or stamp one
    nothing attributes.
    """
    return _PARTY_ADDRESSES


def stamp_unverified_party_attribution(
    envelopes: tuple[FieldProvenance, ...],
    *,
    attributed_fields: frozenset[str] = frozenset(),
) -> tuple[FieldProvenance, ...]:
    """Return *envelopes* with unverified address attribution stamped on each.

    Idempotent and total: every envelope for a per-party address field is
    rewritten to state its attribution status either way, so a re-run cannot
    leave a stale ``True`` on a value whose origin later establishes attribution.
    Setting only the ``True`` side would make the stamp a latch, and a latch on
    a safety flag survives the fix that should clear it.

    Two independent ways a value earns an unstamped envelope, and they compose
    rather than override. Its ORIGIN can answer the attribution question -- a
    structured record's element path names the party, an operator typed into a
    named field. Or the DOCUMENT can answer it, by printing the value inside the
    region a role-evidenced identity anchors to that party, which is what
    ``attributed_fields`` carries. Either is sufficient; neither is required of
    the other.

    Args:
        envelopes: The draft's provenance envelopes, in their original order.
        attributed_fields: Fields the document's own layout attributed, from
            :func:`~application.ledger.resolve_party_attribution_by_colocation`.
            Empty by default, so a caller that cannot segment the document gets
            the interim behaviour rather than a silent clean bill -- the default
            has to be the direction that keeps the stamp.

    Returns:
        The envelopes, in order, each either restamped or passed through where
        the field names no party address.
    """
    stamped: list[FieldProvenance] = []
    for envelope in envelopes:
        if envelope.field not in PARTY_ATTRIBUTED_ADDRESS_FIELDS:
            stamped.append(envelope)
            continue
        origin_answers = envelope.origin in ATTRIBUTION_ESTABLISHING_ORIGINS
        document_answers = envelope.field in attributed_fields
        unverified = not (origin_answers or document_answers)
        if unverified == envelope.attribution_unverified:
            stamped.append(envelope)
            continue
        stamped.append(envelope.model_copy(update={"attribution_unverified": unverified}))
    return tuple(stamped)


def party_attribution_advisory(draft: InvoiceDraft) -> PartyAttributionAdvisory | None:
    """Return what an operator must be told about this draft's attribution, or ``None``.

    Reports a party only where a stamped address field actually carries a value.
    A stamped envelope for an empty field describes an attribution nobody made,
    and warning about it would spend the operator's attention on nothing.

    The territory each party's values would establish is quoted from
    :func:`~application.ledger.scope_printed_evidence_would_establish` rather
    than read here, so the advisory names a concrete claim the operator can
    contest while the boundary that produces it stays in one place.

    Args:
        draft: The reviewed draft, carrying stamped provenance envelopes.

    Returns:
        The advisory, or ``None`` where no populated address value is stamped.
    """
    stamped = {envelope.field for envelope in draft.provenance if envelope.attribution_unverified}
    warnings: list[PartyAttributionWarning] = []
    for party in _PARTY_ADDRESSES:
        affected = tuple(
            field
            for field in (party.postal_field, party.country_field, party.country_code_field)
            if field in stamped and _populated(getattr(draft, field, None))
        )
        if not affected:
            continue
        warnings.append(
            PartyAttributionWarning(
                role=party.role,
                fields=affected,
                # The identifier is passed even though its own attribution IS
                # checked: the ladder consults it first, so omitting it would
                # make the advisory name a territory the real ladder would never
                # reach for this party.
                scope_if_attributed=scope_printed_evidence_would_establish(
                    tax_identifier=getattr(draft, party.tax_id_field, None),
                    printed_country_name=getattr(draft, party.country_field, None),
                    printed_country_code=getattr(draft, party.country_code_field, None),
                    postal_code=getattr(draft, party.postal_field, None),
                ),
            ),
        )
    if not warnings:
        return None
    return PartyAttributionAdvisory(parties=tuple(warnings))


def _populated(value: object | None) -> bool:
    """Return whether a draft field actually carries a printed value."""
    return isinstance(value, str) and bool(value.strip())
