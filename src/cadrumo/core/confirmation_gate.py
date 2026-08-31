"""The closed axes of the human review gate at the confirm boundary.

Two axes, both closed, both declared here beside
:class:`~core.DraftDiscrepancyKind`, :class:`~core.FieldOrigin` and
:class:`~core.FieldGroundingOutcome` for the same reason those are: a review gate
that admits a free-text reason is a gate whose refusals cannot be enumerated, and
one that admits a free-text resolution is a gate an operator can satisfy by
typing anything.

:class:`ConfirmationBlockReason` says WHY a draft cannot be confirmed.
:class:`ReviewAdvisoryKind` says what a draft carries that a person should see
even though it refuses nothing --- the non-blocking axis, closed for the same
reason, because a queue whose only vocabulary is refusal cannot describe the
documents it lets through.
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

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType

from .operator_action_enums import OperatorActionAxis

__all__ = [
    "OPERATOR_ACTION_BY_CONFIRMATION_BLOCK_REASON",
    "ConfirmationBlockReason",
    "FindingResolutionAction",
    "ReviewAdvisoryKind",
]


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

    CONTRADICTED_REGIME = "contradicted_regime"
    """The document's stated regime and the tax it charged cannot both be true.

    Distinct from a closure discrepancy, which says the figures do not add up.
    Here the figures may be flawless and the document still contradicts itself
    in words, so an operator sent to re-check the arithmetic would find nothing
    wrong and confirm. The reason has to name the actual conflict for the
    resolution to mean anything.
    """

    UNDETERMINED_ESTABLISHMENT = "undetermined_establishment"
    """Where a party is established was left undecided by the document as read.

    Its own reason rather than an ambiguous identity, because nothing here is
    ambiguous: no candidates competed and no identifier is in doubt. The
    evidence that would have answered simply did not survive reading, and an
    operator sent to choose between readings of an identifier would find no
    such choice to make.

    Territory decides the IVA treatment, so the resolution is to supply the
    value rather than to attest that a disagreement is acceptable.
    """

    UNMODELLED_INVOICE_CLASS = "unmodelled_invoice_class"
    """The document's declared invoice class has no domain representation."""

    CONTRADICTED_INVOICE_CLASS = "contradicted_invoice_class"
    """The document's class code and corrective reference disagree."""


OPERATOR_ACTION_BY_CONFIRMATION_BLOCK_REASON: Mapping[ConfirmationBlockReason, OperatorActionAxis] = MappingProxyType(
    {
        ConfirmationBlockReason.CLOSURE_DISCREPANCY: OperatorActionAxis.RESOLVE_VALUE_DIVERGENCE,
        ConfirmationBlockReason.AMBIGUOUS_IDENTITY: OperatorActionAxis.RESOLVE_IDENTITY,
        ConfirmationBlockReason.UNRESOLVED_DIRECTION: OperatorActionAxis.SUPPLY_MANUAL_INPUT,
        ConfirmationBlockReason.CONTRADICTED_REGIME: OperatorActionAxis.RESOLVE_VALUE_DIVERGENCE,
        ConfirmationBlockReason.UNDETERMINED_ESTABLISHMENT: OperatorActionAxis.SUPPLY_MANUAL_INPUT,
        ConfirmationBlockReason.UNMODELLED_INVOICE_CLASS: OperatorActionAxis.SUPPLY_MANUAL_INPUT,
        ConfirmationBlockReason.CONTRADICTED_INVOICE_CLASS: OperatorActionAxis.RESOLVE_VALUE_DIVERGENCE,
    },
)
"""Total operator-action projection for the native confirmation blocker axis."""

if set(OPERATOR_ACTION_BY_CONFIRMATION_BLOCK_REASON) != set(ConfirmationBlockReason):
    missing = sorted(
        reason.value for reason in set(ConfirmationBlockReason) - set(OPERATOR_ACTION_BY_CONFIRMATION_BLOCK_REASON)
    )
    stale = sorted(
        str(reason) for reason in set(OPERATOR_ACTION_BY_CONFIRMATION_BLOCK_REASON) - set(ConfirmationBlockReason)
    )
    raise RuntimeError(
        f"every ConfirmationBlockReason must declare an OperatorActionAxis; missing={missing}; stale={stale}",
    )


class ReviewAdvisoryKind(StrEnum):
    """What a draft carries that is worth an operator's attention but blocks nothing.

    The queue's non-blocking axis. A blocking reason answers "why can this not be
    confirmed"; a kind here answers "what would a person want to know before they
    confirm it anyway". Closed for the reason the blocking axis is: a queue that
    can only count its refusals shows an operator nothing at all about the
    documents it is willing to let through, and the conditions on this axis are
    precisely the ones that reach the record silently.

    Enumerable rather than a flag, because the kinds have different owners and
    different fixes. An operator narrowing the queue to the codes only a registry
    commit can close is asking a different question from one narrowing it to the
    typos they can fix off the page, and a single "has advisories" boolean makes
    both queries impossible.
    """

    PARTY_ATTRIBUTION = "party_attribution"
    """Nothing verified which party this document's address values belong to.

    Read the wrong way round, both parties land in an IVA territory neither is
    established in and no check downstream catches it.
    """

    COUNTRY_CODE_UNASSIGNED = "country_code_unassigned"
    """A party's country code is one ISO 3166-1 reserves so no country holds it.

    The operator's own fix: the document states a string rather than a country,
    so the code is corrected against the page.
    """

    COUNTRY_CODE_UNCATALOGUED = "country_code_uncatalogued"
    """A party's country code may name a country the bundled vocabulary lacks.

    Not the operator's fix: re-reading the document settles nothing, and the
    country has to be added to the vocabulary before the party can be placed.
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
