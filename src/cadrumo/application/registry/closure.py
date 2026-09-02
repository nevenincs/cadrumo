"""Strict closure vocabulary for a validated registry revision.

The release predicate joins three independently owned authorities. This module
defines the application-boundary records used to carry one authority's result
without treating an absent measurement or an unsupported capability as a pass.
The composers remain responsible for deriving the evidence; these models own
the common fail-closed contract that they must satisfy.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Final, Literal

from pydantic import BaseModel, StringConstraints, model_validator

from ...core.models import STRICT_FROZEN_CONFIG
from ...domain.calculations.registry.ids import (
    ModeloId,
    RevisionId,
)

__all__ = [
    "RegistryClosureEvidence",
    "RegistryClosureFilingChannelRefusal",
    "RegistryClosureLimb",
    "RegistryClosureLimbName",
    "RegistryClosureLimbOutcome",
    "RegistryClosureOwnerDisposition",
    "RegistryClosureRefusal",
    "RegistryClosureRefusalReason",
]

_BoundedText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=500),
]
_Reference = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=2_048),
]

type RegistryClosureLimbName = Literal["temporal_coverage", "source_connectivity", "filing_export"]
"""One independently-derived conjunct of the registry release predicate."""


class RegistryClosureLimbOutcomeKind(StrEnum):
    """The result of one closure limb, including an explicitly out-of-scope capability."""

    SATISFIED = "satisfied"
    NOT_APPLICABLE = "not_applicable"
    REFUSED = "refused"
    UNMEASURED = "unmeasured"


RegistryClosureLimbOutcome = Literal[
    RegistryClosureLimbOutcomeKind.SATISFIED,
    RegistryClosureLimbOutcomeKind.NOT_APPLICABLE,
    RegistryClosureLimbOutcomeKind.REFUSED,
    RegistryClosureLimbOutcomeKind.UNMEASURED,
]
"""Every outcome, for the strict limb field."""

CLOSURE_SATISFYING_OUTCOMES: Final[frozenset[RegistryClosureLimbOutcomeKind]] = frozenset(
    {
        RegistryClosureLimbOutcomeKind.SATISFIED,
        RegistryClosureLimbOutcomeKind.NOT_APPLICABLE,
    },
)
"""The outcomes that do not withhold closure.

``NOT_APPLICABLE`` is included deliberately: a capability declared out of scope is not a
gap, and treating it as one would refuse a filing over evidence nothing required. The
pair was tested twice in `filing_export_coverage`, once directly and once as its own
negation, so the two could disagree about what counts as satisfied."""

type RegistryClosureRefusalReason = Literal[
    "conflicting_evidence",
    "cross_limb_disagreement",
    "missing_evidence",
    "scope_inadequate_evidence",
    "stale_evidence",
    "unreviewed_evidence",
    "unmeasured",
]
"""Evidence or capability condition that keeps a limb from satisfying closure."""


class _ClosureModel(BaseModel):
    """Strict frozen base for registry-closure application records."""

    model_config = STRICT_FROZEN_CONFIG


class RegistryClosureEvidence(_ClosureModel):
    """One authoritative or executable provenance locator for a closure limb."""

    authority: _BoundedText
    locator: _Reference


class RegistryClosureOwnerDisposition(_ClosureModel):
    """Accountable, bounded disposition for a refusal that remains open to review."""

    limb: RegistryClosureLimbName
    state: Literal["owned", "blocked", "deferred", "resolved"]
    owner: _BoundedText
    work_item: _Reference
    reconsideration_condition: _BoundedText


class RegistryClosureFilingChannelRefusal(_ClosureModel):
    """One public, non-sensitive refusal from a mandatory filing-proof channel."""

    channel: Literal["conformance", "secure_replay"]
    reason: Literal[
        "evidence_missing",
        "authority_unavailable",
        "identity_mismatch",
        "provenance_mismatch",
        "canonical_writer_failed",
        "custody_failed",
        "proof_validation_failed",
    ]
    authority_id: _BoundedText | None = None


class RegistryClosureRefusal(_ClosureModel):
    """Actionable reason a revision cannot claim one closure capability."""

    reason: RegistryClosureRefusalReason
    detail: _BoundedText
    disposition: RegistryClosureOwnerDisposition
    filing_channels: tuple[RegistryClosureFilingChannelRefusal, ...] = ()

    @model_validator(mode="after")
    def _require_coherent_filing_channels(self) -> RegistryClosureRefusal:
        channels = tuple(item.channel for item in self.filing_channels)
        if len(channels) != len(set(channels)):
            raise ValueError("closure refusal permits at most one refusal per filing-proof channel")
        if self.filing_channels and self.disposition.limb != "filing_export":
            raise ValueError("only a filing-export refusal may carry filing-proof channel refusals")
        return self


class RegistryClosureLimb(_ClosureModel):
    """One evidence-bearing closure result for one validated modelo revision."""

    modelo: ModeloId
    revision: RevisionId
    name: RegistryClosureLimbName
    outcome: RegistryClosureLimbOutcome
    evidence: tuple[RegistryClosureEvidence, ...] = ()
    refusal: RegistryClosureRefusal | None = None

    @model_validator(mode="after")
    def _require_fail_closed_outcome(self) -> RegistryClosureLimb:
        """Require evidence for success and a responsible refusal for every other result."""
        evidence_ids = tuple((item.authority, item.locator) for item in self.evidence)
        if len(set(evidence_ids)) != len(evidence_ids):
            raise ValueError("closure limb evidence locators must be unique")
        if self.outcome == "satisfied":
            if not self.evidence:
                raise ValueError("satisfied closure limb requires evidence")
            if self.refusal is not None:
                raise ValueError("satisfied closure limb cannot carry a refusal")
            return self
        if self.outcome == "not_applicable":
            if self.name != "filing_export":
                raise ValueError("only the filing-export limb may be not applicable")
            if self.evidence:
                raise ValueError("not-applicable filing-export limb cannot carry capability evidence")
            if self.refusal is not None:
                raise ValueError("not-applicable filing-export limb cannot carry a refusal")
            return self
        if self.refusal is None:
            raise ValueError("unsatisfied closure limb requires an actionable refusal")
        if self.refusal.disposition.limb != self.name:
            raise ValueError("closure refusal disposition must name the owning limb")
        if self.refusal.disposition.state == "resolved":
            raise ValueError("active closure refusal cannot carry a resolved owner disposition")
        if self.outcome == "unmeasured" and self.refusal.reason != "unmeasured":
            raise ValueError("unmeasured closure limb requires the unmeasured refusal reason")
        if self.outcome == "refused" and self.refusal.reason == "unmeasured":
            raise ValueError("refused closure limb cannot use the unmeasured refusal reason")
        return self
