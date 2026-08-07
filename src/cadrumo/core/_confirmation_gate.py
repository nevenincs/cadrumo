"""The closed axes of the human review gate at the confirm boundary.

Two axes, both closed, both declared here beside
:class:`~core.DraftDiscrepancyKind`, :class:`~core.FieldOrigin` and
:class:`~core.FieldGroundingOutcome` for the same reason those are: a review gate
that admits a free-text reason is a gate whose refusals cannot be enumerated, and
one that admits a free-text resolution is a gate an operator can satisfy by
typing anything.

:class:`ConfirmationBlockReason` says WHY a draft cannot be confirmed.
:class:`FindingResolutionAction` says HOW the operator settled it. A resolution
carries one of these actions and nothing else, so "the operator looked and
attests the document prints this" stays distinguishable from "the operator
supplied a value the document never stated".

Neither axis carries a "waive" or "confirm anyway" member, deliberately and
permanently. Adding one would restore the rubber stamp the gate exists to remove:
the value of a blocking finding is exactly the per-document attention it forces,
and a bulk escape hatch converts every blocker into a keystroke.
"""

from __future__ import annotations

from enum import StrEnum

__all__ = ["ConfirmationBlockReason", "FindingResolutionAction"]


class ConfirmationBlockReason(StrEnum):
    """Why a reviewed draft cannot be confirmed until the operator answers."""

    CLOSURE_DISCREPANCY = "closure_discrepancy"
    """A monetary identity the document's own figures state does not hold.

    Total closure, per-tier rate consistency and breakdown sums all land here:
    each is arithmetic over figures the document itself prints, so a failure
    means a component was misread or the document carries one the draft cannot
    represent. Both under-declare when confirmed unexamined.
    """

    AMBIGUOUS_IDENTITY = "ambiguous_identity"
    """Who the counterparty is was not settled by the document.

    A tax identifier that failed its control character, or several competing
    readings none of which was decidable. The counterparty tax id drives
    deductibility and feeds Modelo 347 per counterparty, so a wrong one reaches
    a filing a human submits, and a misread that happens to be a different
    VALID identifier belongs to a different real taxpayer.
    """

    UNRESOLVED_DIRECTION = "unresolved_direction"
    """Which party issued the document could not be established.

    The document names identifiers but nothing distinguishes issuer from
    recipient. Guessing puts the filer's own identifier where the counterparty
    belongs, and the result reads as a plausible record.
    """


class FindingResolutionAction(StrEnum):
    """How the operator settled one named blocking finding.

    Three actions, distinguished because they carry different evidentiary
    weight. Collapsing them into a single "resolved" flag would lose exactly the
    distinction a later audit needs: whether the operator chose between readings
    the document offered, supplied something it never stated, or looked at the
    page and attested the reading stands.
    """

    CHOOSE_CANDIDATE = "choose_candidate"
    """The operator picked one of the competing readings already recorded.

    The value must match a candidate the grounding pass captured; choosing
    something that was never a candidate is a supplied value, not a choice.
    """

    SUPPLY_VALUE = "supply_value"
    """The operator supplied a value, which the field is then stamped OPERATOR.

    The document did not settle the field, so the value is the operator's own
    assertion about it rather than a reading of it.
    """

    ATTEST = "attest"
    """The operator read the document and attests the finding is not an error.

    A real invoice can legitimately fail an internal identity -- a component the
    draft cannot represent, a rounding convention the tolerance does not model.
    Attesting records that a human looked and accepted it, with their note, and
    it never rewrites any figure.
    """
