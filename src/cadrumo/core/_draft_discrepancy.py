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

    COUNTRY_CODE_UNASSIGNED = "country_code_unassigned"
    """A party's country field states a code reserved to denote no country.

    The ISO 3166-1 user-assigned ranges -- ``AA``, ``QM``-``QZ``, ``XA``-``XZ``
    and ``ZZ`` -- exist so that no country is ever allocated there, so a
    document stating one has stated a string. It is the shape a placeholder, a
    truncated field or a slipped keystroke actually takes.

    Its own member rather than a variant of the sibling below because the
    OWNER differs, and that is the whole reason the axis splits: this one the
    operator can correct off the page, while a catalogue gap is ours to close
    and no amount of re-reading the document will settle it.

    Raised only where the code cost a territorial answer -- a party the ladder
    settled through some other rung raises nothing however its country field
    is printed, on the sibling terms every check here holds to.

    Blocking on those same terms: where a party is established decides the IVA
    treatment, and on the issued side the reading this replaces was export
    treatment, zero-rated. Confirming past an undetermined territory picks an
    answer by omission, and this is the direction where the omission exempts.
    """

    COUNTRY_CODE_UNCATALOGUED = "country_code_uncatalogued"
    """A party's country field states a code the bundled vocabulary does not carry.

    Distinct from the member above because the claim is weaker and honestly so:
    the reserved ranges are the only codes this codebase can say denote nothing,
    and a code outside them is reported as unknown to US rather than asserted to
    be meaningless. It may well name a real jurisdiction, and the resolution is
    to add the country to the vocabulary rather than to re-read the document.

    It fires no rung until that happens, which is the deliberate half: an
    uncatalogued code establishing a territory on shape alone is the defect this
    axis was narrowed to close, and treating a gap in our data as evidence would
    reopen it under a friendlier name.
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
