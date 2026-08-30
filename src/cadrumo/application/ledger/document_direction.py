"""Decide from the document which side of the invoice the filer is on.

Direction — did this taxpayer ISSUE the invoice or RECEIVE it — is the axis every
downstream informativa turns on. Modelo 347 and Modelo 349 report counterparty
totals per direction, so reading a purchase as a sale files it against the wrong
party in the wrong return, and both figures are wrong in a way that reconciles
internally.

Until this module the answer came from one place only: the operator typed it on
the confirm verb. That is a real answer and it stays the decision, but nothing
checked it, and the document itself was never asked. The draft has carried a
``suggested_kind`` slot for exactly this since it was declared -- documented, and
surfaced by the review command -- with nothing on the reading path writing it.

**The question asked is a ROLE question, not an identity one.** Whether the
document names the filer at all is a different check, already owned:
:func:`~application.invoices.counterparty_is_the_filer` answers "is the recorded
counterparty us", and :func:`~application.ledger.identity_roles.resolve_counterparty_identity`
excludes the filer's own identifier from counterparty candidacy. Neither says
which ROLE the filer occupies, and that is the whole of the direction question:
the filer standing in the issuing party's block means they issued it.

**Identity is normalised, attribution is by containment.** Two authorities, each
asked the question it owns. Whether a printed identifier names the filer goes to
:func:`~core.identity.same_tax_identifier`, so a document printing
``B-1234567-4`` is recognised against a stored ``B12345674``; a raw text search
for the stored form would miss every punctuated print. Whether that value belongs
to the party the reader filed it under goes to
:func:`~application.ledger.party_colocation.party_regions` -- the same heading partition the
address attribution uses -- so a value is the issuing party's because it is
printed inside the issuing party's block, never because it is near its heading.

**Autoconsumo needs no carve-out here, and that is why containment was chosen.**
LIVA art. 9 is the one family where a taxpayer documents an operation directed at
themselves, and it has no representation in this codebase. A document placing the
filer on BOTH sides is the both-regions case, which yields no derivation and no
finding — so this module asserts nothing about autoconsumo rather than asserting
something false about it. Comparing the two identity slots alone would have
answered ``ISSUED`` for such a document on slot order.

**It suggests; it never decides.** The returned kind is stamped on the draft as a
suggestion and the operator's ``--kind`` remains the decision. The cross-check
that compares the two, and refuses when they disagree, is the consuming half and
lives at the confirm boundary where both are in hand.

See Also:
    :func:`~application.ledger.party_colocation.party_regions`
        The heading partition this reads containment from.
    :func:`~application.ledger.party_colocation.resolve_party_attribution_by_colocation`
        The sibling that attributes ADDRESS values across the same partition.
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from ...core import STRICT_FROZEN_CONFIG
from ...core.identity import same_tax_identifier
from ...domain.iva.classification import InvoiceKind
from .grounding_anchor import printed_excerpt_occurs_in_text
from .party_attribution import party_addresses
from .party_colocation import party_regions

if TYPE_CHECKING:
    from .document_transcription import DocumentTranscription
    from .evidence_draft import InvoiceDraft

__all__ = [
    "DIRECTION_BY_FILER_ROLE",
    "DirectionDerivationOutcome",
    "InvoiceKindDerivation",
    "derive_invoice_kind_from_filer_role",
]

DIRECTION_BY_FILER_ROLE: dict[str, InvoiceKind] = {
    "supplier": InvoiceKind.ISSUED,
    "customer": InvoiceKind.RECEIVED,
}
"""Which direction each party role implies when the FILER occupies it.

The whole derivation, as data. The filer standing where the document names the
issuing party means they issued it; standing where it names the recipient means
they received it. Keyed on the role strings
:func:`~application.ledger.party_attribution.party_addresses` declares, so a party table that grew
a side would surface here as a missing key rather than as a silent default.
"""


class DirectionDerivationOutcome(StrEnum):
    """What the document settled about which side the filer is on.

    Attributes:
        DERIVED: The filer's identifier occupies exactly one party's role and is
            printed inside that party's own block. The one outcome carrying a
            direction.
        FILER_ON_BOTH_SIDES: The document places the filer in both parties'
            roles. No direction follows, and nothing is asserted about why —
            a transposed read and a genuine self-directed operation look
            identical from here, and only one of them is a defect.
        FILER_ABSENT: Neither party's identifier names the filer. Ordinary for a
            document that omits the recipient's NIF, which a factura
            simplificada may legitimately do.
        CONTAINMENT_UNCONFIRMED: A party's slot names the filer, but the document
            does not print that value inside that party's own block — it is in
            the other block, in both, or in neither. The reader's assignment is
            exactly what is unverified, so it is not read as the answer.
        NO_PARTITION: The document states no usable two-party heading partition,
            so containment cannot be asked at all.
        NO_FILER_IDENTIFIER: The filer's own identifier was not supplied. Nothing
            can be compared, and this is reported rather than folded into
            :attr:`FILER_ABSENT` — "we did not ask" and "the document does not
            say" are different facts about different owners.
    """

    DERIVED = "derived"
    FILER_ON_BOTH_SIDES = "filer_on_both_sides"
    FILER_ABSENT = "filer_absent"
    CONTAINMENT_UNCONFIRMED = "containment_unconfirmed"
    NO_PARTITION = "no_partition"
    NO_FILER_IDENTIFIER = "no_filer_identifier"


class InvoiceKindDerivation(BaseModel):
    """What the document settled about direction, and what it was read from.

    Attributes:
        kind: The direction the document supports, or ``None`` for every outcome
            but :attr:`DirectionDerivationOutcome.DERIVED`. Never a default:
            an outcome that did not settle direction carries no direction.
        outcome: Which of the six cases this is.
        basis: The operator-facing sentence naming what was read. Carried rather
            than rebuilt at the surface so the review command and any later
            consumer quote one wording, and stamped onto the draft's
            ``suggested_kind`` envelope where the review surface already reads a
            basis from.
    """

    model_config = STRICT_FROZEN_CONFIG

    kind: InvoiceKind | None = None
    outcome: DirectionDerivationOutcome
    basis: str = Field(min_length=1)

    @property
    def settled(self) -> bool:
        """Return whether the document supports a direction."""
        return self.outcome is DirectionDerivationOutcome.DERIVED


def _filer_roles(draft: InvoiceDraft, *, taxpayer_tax_id: str) -> tuple[str, ...]:
    """Return the party roles whose identity slot names the filer, in table order."""
    return tuple(
        party.role
        for party in party_addresses()
        if same_tax_identifier(getattr(draft, party.tax_id_field, None), taxpayer_tax_id)
    )


def _printed_in_own_block_only(value: str, *, role: str, regions: dict[str, str]) -> bool:
    """Return whether *value* is printed inside *role*'s block and no other.

    The same both-sides rule the address attribution holds to, and for the same
    reason: a value printed in both blocks is evidence that containment cannot
    separate the parties on this document, so reading its presence in its own
    block as confirmation would let any repeated identifier launder itself into
    an attributed one. An invoice printing the filer's NIF in a payment-details
    footer under the other party's heading is exactly that document.
    """
    own = regions.get(role)
    if own is None:
        return False
    if not printed_excerpt_occurs_in_text(value, text=own):
        return False
    return not any(printed_excerpt_occurs_in_text(value, text=text) for other, text in regions.items() if other != role)


def derive_invoice_kind_from_filer_role(
    *,
    draft: InvoiceDraft,
    transcription: DocumentTranscription,
    taxpayer_tax_id: str | None,
) -> InvoiceKindDerivation:
    """Return which side of the invoice the document places the filer on.

    Deterministic and side-effect free: it reads the draft and the transcription
    and returns a verdict. It never rewrites a draft value, never re-assigns a
    party, and never returns a direction it did not read from the document.

    Args:
        draft: The read draft, carrying both parties' identity values and the
            role evidence the partition is built from.
        transcription: The independently produced document text, line structure
            intact, which is what the partition is read off.
        taxpayer_tax_id: The filer's own identifier, or ``None`` when it was not
            supplied. ``None`` yields
            :attr:`DirectionDerivationOutcome.NO_FILER_IDENTIFIER` rather than a
            guess: without it every identifier on the page is equally a
            counterparty's, which is the condition under which a first-match scan
            produced confident wrong answers.

    Returns:
        The derivation. Exactly one outcome carries a ``kind``; every other
        reports why the document did not settle direction, so a caller can tell
        "the document says received" from "the document does not say".
    """
    if taxpayer_tax_id is None or not taxpayer_tax_id.strip():
        return InvoiceKindDerivation(
            outcome=DirectionDerivationOutcome.NO_FILER_IDENTIFIER,
            basis=(
                "the filer's own tax identifier was not supplied, so no party on the document "
                "could be compared against it"
            ),
        )

    roles = _filer_roles(draft, taxpayer_tax_id=taxpayer_tax_id)
    if not roles:
        return InvoiceKindDerivation(
            outcome=DirectionDerivationOutcome.FILER_ABSENT,
            basis=(
                "neither party's tax identifier on this document names the filer, so the document "
                "does not place them on either side"
            ),
        )
    if len(roles) > 1:
        return InvoiceKindDerivation(
            outcome=DirectionDerivationOutcome.FILER_ON_BOTH_SIDES,
            basis="this document names the filer as both parties, so it places them on neither side in particular",
        )

    role = next(iter(roles))
    regions = party_regions(draft=draft, transcription=transcription)
    if len(regions) < 2:
        return InvoiceKindDerivation(
            outcome=DirectionDerivationOutcome.NO_PARTITION,
            basis=(
                f"the filer's tax identifier was read as the {role} party's, but this document states no usable "
                f"pair of party headings, so nothing confirms which block it is printed in"
            ),
        )

    field = next(party.tax_id_field for party in party_addresses() if party.role == role)
    printed = getattr(draft, field, None)
    if not isinstance(printed, str) or not _printed_in_own_block_only(printed, role=role, regions=regions):
        return InvoiceKindDerivation(
            outcome=DirectionDerivationOutcome.CONTAINMENT_UNCONFIRMED,
            basis=(
                f"the filer's tax identifier was read as the {role} party's, but this document does not print it "
                f"inside the {role} party's block alone, so the reader's assignment is unconfirmed"
            ),
        )

    return InvoiceKindDerivation(
        kind=DIRECTION_BY_FILER_ROLE[role],
        outcome=DirectionDerivationOutcome.DERIVED,
        basis=(
            f"this document prints the filer's own tax identifier inside the {role} party's block, "
            f"so the filer is the {role} on it"
        ),
    )
