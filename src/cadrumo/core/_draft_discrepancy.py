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
