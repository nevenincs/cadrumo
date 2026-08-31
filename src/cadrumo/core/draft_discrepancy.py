"""The closed set of deterministic checks a read document can fail.

Every member names a check that **deterministic code** performs over values a
reader proposed -- never a model's opinion about its own output. That is the
whole reason the axis is closed: a finding is only worth surfacing to an
operator if a reader can be pointed at the exact identity that did not hold, and
an open free-text kind would let "the model seemed unsure" wear the same shape
as "base plus cuota does not equal the printed total".

Declared in ``core`` alongside :class:`~core.FieldOrigin` and
:class:`~core.FieldGroundingOutcome`, which it travels with: origin says how a
value was obtained, grounding outcome says what checking it survived, and this
says which check it failed.

A new member is added when a new deterministic check lands, never to describe a
suspicion no code evaluates.

**Membership means BLOCKING.** Every member maps to a
:class:`~core.ConfirmationBlockReason`, and the confirmation gate refuses to
import while one does not, so a condition placed here is one an operator must
answer individually before the draft may be confirmed at all. That is why the
country-vocabulary conditions are deliberately absent rather than listed and
exempted: an uncatalogued country code is a gap in this system's own bundled
vocabulary, which carries a bounded subset of the world's jurisdictions, so
blocking on it would refuse a draft for every real jurisdiction outside that
subset. Those conditions are reported on the non-blocking advisory channel
instead -- see :func:`~application.ledger.country_vocabulary_advisory` -- on the
terms the unconsumed-IVA advisory already holds to: an alert only earns the
operator's attention if every firing is a genuine defect in the document.
"""

from __future__ import annotations

from enum import StrEnum

__all__ = ["DraftDiscrepancyKind"]


class DraftDiscrepancyKind(StrEnum):
    """Which deterministic identity a read document failed."""

    ARITHMETIC_CLOSURE = "arithmetic_closure"
    """The monetary set does not close against the printed total.

    Base plus cuota, adjusted by any recargo, retencion and suplidos the
    document states, does not reach the total it prints. Either a component was
    misread or the document carries one the draft could not represent -- both
    are silent under-declarations when the figure is discarded unexamined.
    """

    RATE_INCONSISTENT = "rate_inconsistent"
    """The stated base and rate do not produce the stated cuota.

    Checked per rate tier as well as flat, because a multi-rate document whose
    tiers sum correctly can still misattribute base between them, and Modelo 303
    declares cuota devengada per tier.
    """

    BREAKDOWN_INCONSISTENT = "breakdown_inconsistent"
    """The per-rate subtotals do not sum to the flat totals beside them.

    The two are independent readings of the same document, so a disagreement
    means at least one is wrong and the draft cannot say which.
    """

    IDENTITY_UNVERIFIED = "identity_unverified"
    """A stated tax identifier failed its control-character check.

    A NIF, NIE or CIF carries a checksum, so a failure is a read error or a
    genuinely invalid identifier -- never a formatting preference.
    """

    ROLE_UNRESOLVED = "role_unresolved"
    """Which party is which could not be established from unique evidence.

    The document names identifiers but nothing distinguishes issuer from
    recipient. Guessing here puts the filer's own identifier where the
    counterparty belongs, which reads as a plausible record.
    """

    REGIME_CONTRADICTED = "regime_contradicted"
    """The regime the issuer printed in words disagrees with the tax it charged.

    Not an arithmetic failure: every figure may close perfectly and the document
    still say two incompatible things about itself. A mention whose whole point
    is that the issuer charges no Spanish IVA, printed beside a repercutido rate
    and cuota, is the reachable case -- and which half is wrong is not decidable
    from the page, because either the mention was printed in error or the tax
    was charged in error, and the two lead to different declarations.

    Blocking rather than advisory, for the reason the sibling kinds are: the
    disagreement is a fact about the document under every reading, not a doubt
    about one figure, and confirming past it silently picks a side.
    """

    DIRECTION_CONTRADICTED = "direction_contradicted"
    """The document places the filer on the opposite side from the stated direction.

    Two independent sources disagree about a binary fact. The operator's verb
    supplied a direction; the document prints the filer's own tax identifier
    inside the OTHER party's block. One of them is wrong, and which is not
    decidable here -- the operator may have mistyped, or the reader may have
    filed the identifier under the wrong party.

    Blocking rather than advisory, and the distinction from the advisory
    conditions is the population it fires on. A check earns an operator's
    attention only if every firing is a genuine defect, so a condition that
    fires across a large correct population belongs on the advisory channel.
    This one cannot: it requires the document to positively place the filer on
    the side the operator did not state, which no correct invoice does. The
    single family where a taxpayer legitimately occupies both roles --
    autoconsumo, Ley 37/1992 art. 9 -- never reaches this member, because a
    document naming the filer as both parties settles no direction at all and
    raises nothing.

    And the cost of confirming through is not a doubtful figure but an inverted
    record: a purchase filed as a sale reaches the counterparty totals of the
    wrong informativa, where Modelo 347 and Modelo 349 are reconciled against
    what the counterparty declared.
    """

    POSTAL_CODE_UNREADABLE = "postal_code_unreadable"
    """A party's postal code field holds something that is not a postal code.

    Raised only where that costs a territorial answer: the postal code is the
    sub-national evidence separating the three Spanish IVA territories, and it
    is consulted exactly when the printed country did not settle the territory
    on its own. So a party whose country evidence already resolves -- any
    country but Spain -- raises nothing here however its code is printed, and a
    correctly printed non-numeric foreign code is not a finding.

    What remains is the case that costs something: a Spanish or unstated party
    whose code cannot be read, so Canarias, Ceuta y Melilla and the peninsula
    stay undecided. The reading is what failed rather than the document -- the
    free-text validator keeps whatever the field held, by design, because
    dropping it would destroy the anchor the operator reviews -- and an address
    line sitting in a slot the operator surface labels a postal code reads as a
    postal code until someone looks.

    Blocking rather than advisory on the sibling terms: which territory a party
    is established in decides the IVA treatment of the operation, and confirming
    past an undetermined one picks the majority answer by omission.
    """

    PARTY_ATTRIBUTION_CONTRADICTED = "party_attribution_contradicted"
    """A party's address value is printed inside the OTHER party's block.

    The transposition case, caught by the document's own layout: the value was
    read correctly and anchors perfectly, and it sits under the heading that
    assigns the other side. Nothing else in the reading path can see this,
    because every other check asks whether a value is on the page and this asks
    whose it is.

    Reported rather than corrected. Moving the value to the block containing it
    would replace the reader's unverified assignment with the resolver's, and
    both rest on one reading of one document; which of the two is wrong is not
    decidable here, because the blocks may have been swapped or the value may
    have been printed in the wrong place.

    Blocking on the sibling terms, and this is the case where blocking earns its
    cost most clearly: a transposition places both parties in territories
    neither is established in while every figure closes and every anchor holds,
    so the draft is clean on its face. It fires only on positive evidence of a
    swap -- a value found in the other block and not its own -- never on a
    document the layout simply cannot separate, which stays an advisory.
    """

    INVOICE_CLASS_UNMODELLED = "invoice_class_unmodelled"
    """The document declares an invoice class the domain cannot represent.

    Facturae's recapitulativa codes are valid statements, but the domain's
    closed invoice taxonomy has no recapitulativa member. Flattening the code
    onto ordinaria would discard evidence, so the gap is surfaced intact.
    """

    INVOICE_CLASS_CONTRADICTED = "invoice_class_contradicted"
    """The declared class disagrees with the document's corrective reference.

    A corrective class with no corrected invoice, or a non-corrective class
    carrying one, gives two incompatible answers inside the same document.
    Neither statement is silently selected over the other.
    """
