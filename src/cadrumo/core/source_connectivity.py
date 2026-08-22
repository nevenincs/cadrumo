"""Canonical identity and disposition vocabulary for source connectivity.

The connectivity census accounts for capabilities before legal adjudication
settles whether, and where, they feed a modelo.  Candidate identity must
therefore survive changes to source locators, discovered implementation detail,
and proposed casilla destinations.  :class:`SourceConnectivityCandidateIdentity`
holds only the stable census token; evidence and mutable adjudication facts
belong to the census row built around it.

Likewise, :class:`SourceConnectivityDisposition` is the complete vocabulary for
the outcome of that adjudication.  It distinguishes connections from candidates,
three independently actionable blocking boundaries, deliberate manual handling,
stale duplication, and genuine inapplicability.  Free-form states would make a
new capability indistinguishable from a misspelling and defeat the census
ratchet.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, StringConstraints, model_validator

from ._models import STRICT_FROZEN_CONFIG
from .aggregation import BindingSourceKind

__all__ = [
    "SourceConnectivityCandidateId",
    "SourceConnectivityCandidateIdentity",
    "SourceConnectivityCensusRow",
    "SourceConnectivityConnectedProof",
    "SourceConnectivityDisposition",
    "SourceConnectivityEncryptedRevisionProof",
    "SourceConnectivityExpiryPosture",
    "SourceConnectivityFollowUp",
    "SourceConnectivityGrounding",
    "SourceConnectivityGroundingLocatorKind",
    "SourceConnectivityOperatorReachabilityProof",
    "SourceConnectivityResolverOwnershipProof",
]

_BoundedText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=500),
]
_Reference = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=2_048),
]
_StableToken = Annotated[
    str,
    Field(min_length=1, max_length=160, pattern=r"^[a-z0-9][a-z0-9._:-]*$"),
]


type SourceConnectivityCandidateId = Annotated[
    str,
    Field(
        min_length=1,
        max_length=160,
        pattern=r"^[a-z0-9][a-z0-9._:-]*$",
    ),
]
"""Stable, machine-readable identity of one connectivity census candidate.

The token is deliberately opaque.  It may describe a source capability or a
registry destination, but it must not encode a source-code location or a
tentative legal mapping whose later correction would manufacture a new row.
"""


class SourceConnectivityCandidateIdentity(BaseModel):
    """Location-independent identity of one connectivity census candidate."""

    model_config = STRICT_FROZEN_CONFIG

    candidate_id: SourceConnectivityCandidateId
    """Canonical token retained across discovery and adjudication revisions."""


class SourceConnectivityDisposition(StrEnum):
    """Closed adjudication state of one source-connectivity candidate."""

    CONNECTED = "connected"
    """The production calculation path carries the source into its casillas."""

    CONNECT_CANDIDATE = "connect_candidate"
    """Evidence justifies bounded adjudication of a possible connection."""

    GROUNDING_BLOCKED = "grounding_blocked"
    """Official evidence has not yet settled legal substitutability."""

    INGRESS_BLOCKED = "ingress_blocked"
    """The typed fact exists but lacks a governed calculation input path."""

    REGISTRY_BLOCKED = "registry_blocked"
    """The destination cannot yet be expressed by the validated registry."""

    MANUAL_BY_DESIGN = "manual_by_design"
    """Operator input remains authoritative by an explicit design decision."""

    DUPLICATE_OR_STALE = "duplicate_or_stale"
    """The candidate duplicates another authority or no longer exists."""

    NOT_APPLICABLE = "not_applicable"
    """The candidate does not apply to the filing connectivity boundary."""


class SourceConnectivityGroundingLocatorKind(StrEnum):
    """Closed resolver family for one grounding reference."""

    HTTPS = "https"
    LEGAL_REFERENCE = "legal_reference"
    SOURCE_REFERENCE = "source_reference"
    REPOSITORY = "repository"


class SourceConnectivityGrounding(BaseModel):
    """Re-fetchable evidence supporting one census adjudication."""

    model_config = STRICT_FROZEN_CONFIG

    locator_kind: SourceConnectivityGroundingLocatorKind
    reference: _Reference
    summary: _BoundedText

    @model_validator(mode="after")
    def _validate_re_fetchable_reference(self) -> SourceConnectivityGrounding:
        """Refuse references the declared locator resolver cannot fetch."""
        if self.locator_kind is SourceConnectivityGroundingLocatorKind.HTTPS:
            parsed = urlsplit(self.reference)
            if parsed.scheme != "https" or not parsed.netloc or parsed.username is not None:
                raise ValueError("https grounding requires an absolute credential-free HTTPS URL")
        elif self.locator_kind in {
            SourceConnectivityGroundingLocatorKind.LEGAL_REFERENCE,
            SourceConnectivityGroundingLocatorKind.SOURCE_REFERENCE,
        }:
            if not _is_stable_token(self.reference):
                raise ValueError("catalogue grounding requires a canonical reference identity")
        elif not _is_repository_locator(self.reference):
            raise ValueError("repository grounding requires a production repository path and optional line")
        return self


def _is_stable_token(value: str) -> bool:
    """Return whether ``value`` follows the canonical stable-token grammar."""
    return bool(value) and len(value) <= 160 and value[0].isalnum() and all(
        character.islower() or character.isdigit() or character in "._:-" for character in value
    )


def _is_repository_locator(value: str) -> bool:
    """Return whether ``value`` names a stable in-repository evidence location."""
    path, separator, line = value.rpartition(":")
    candidate_path = path if separator and line.isdigit() else value
    return (
        candidate_path.startswith(("src/", "dev/", "docs/"))
        and "\\" not in candidate_path
        and "//" not in candidate_path
        and ".." not in candidate_path.split("/")
    )


class SourceConnectivityFollowUp(BaseModel):
    """Finite action that can resolve or re-adjudicate one census row."""

    model_config = STRICT_FROZEN_CONFIG

    action_id: _StableToken
    owner: _BoundedText | None = None
    """Action owner; ``None`` explicitly inherits the census-row owner."""

    deadline: date
    completion_criterion: _BoundedText


class SourceConnectivityExpiryPosture(StrEnum):
    """Expiry state evaluated at an explicit caller-supplied civil date."""

    NOT_SCHEDULED = "not_scheduled"
    CURRENT = "current"
    EXPIRED = "expired"


class SourceConnectivityResolverOwnershipProof(BaseModel):
    """Evidence that one canonical resolver owns the candidate source."""

    model_config = STRICT_FROZEN_CONFIG

    source_kind: BindingSourceKind
    resolver_id: _StableToken
    owner: _BoundedText
    enrollment_evidence: tuple[SourceConnectivityGrounding, ...] = Field(min_length=1)


class SourceConnectivityEncryptedRevisionProof(BaseModel):
    """Evidence that source provenance survives encrypted revision storage."""

    model_config = STRICT_FROZEN_CONFIG

    calculation_revision_proof_id: _StableToken
    strict_round_trip: Literal[True]
    encrypted_at_rest: Literal[True]
    anti_tautology_mutation: Literal[True]
    evidence: tuple[SourceConnectivityGrounding, ...] = Field(min_length=1)


class SourceConnectivityOperatorReachabilityProof(BaseModel):
    """Evidence that a supported operator workflow reaches the resolver."""

    model_config = STRICT_FROZEN_CONFIG

    entrypoint_id: _StableToken
    command: _BoundedText
    resolver_observed: Literal[True]
    evidence: tuple[SourceConnectivityGrounding, ...] = Field(min_length=1)


class SourceConnectivityConnectedProof(BaseModel):
    """Complete production proof required by a ``connected`` census claim."""

    model_config = STRICT_FROZEN_CONFIG

    resolver_ownership: SourceConnectivityResolverOwnershipProof
    encrypted_revision: SourceConnectivityEncryptedRevisionProof
    operator_reachability: SourceConnectivityOperatorReachabilityProof


_BLOCKED_DISPOSITIONS = frozenset(
    {
        SourceConnectivityDisposition.GROUNDING_BLOCKED,
        SourceConnectivityDisposition.INGRESS_BLOCKED,
        SourceConnectivityDisposition.REGISTRY_BLOCKED,
    },
)


class SourceConnectivityCensusRow(SourceConnectivityCandidateIdentity):
    """Governed adjudication record for one stable connectivity candidate.

    Connected-slice proof is intentionally absent until its separate contract
    is introduced.  This row establishes only the evidence and accountability
    needed for every disposition, including fail-closed blocked states.
    """

    disposition: SourceConnectivityDisposition
    grounding: tuple[SourceConnectivityGrounding, ...] = Field(min_length=1)
    owner: _BoundedText
    review_condition: _BoundedText | None = None
    expires_on: date | None = None
    bounded_follow_up: SourceConnectivityFollowUp | None = None
    connected_proof: SourceConnectivityConnectedProof | None = None

    @model_validator(mode="after")
    def _require_actionable_unresolved_state(self) -> SourceConnectivityCensusRow:
        """Refuse unresolved rows that cannot drive bounded follow-up."""
        if self.disposition in _BLOCKED_DISPOSITIONS:
            missing = [
                field_name
                for field_name, value in (
                    ("review_condition", self.review_condition),
                    ("expires_on", self.expires_on),
                    ("bounded_follow_up", self.bounded_follow_up),
                )
                if value is None
            ]
            if missing:
                rendered = ", ".join(missing)
                raise ValueError(f"blocked connectivity row requires {rendered}")
        elif self.disposition is SourceConnectivityDisposition.CONNECT_CANDIDATE:
            if self.review_condition is None or self.bounded_follow_up is None:
                raise ValueError(
                    "connectivity candidate requires review_condition and bounded_follow_up",
                )
        elif (
            self.disposition is SourceConnectivityDisposition.MANUAL_BY_DESIGN
            and self.review_condition is None
        ):
            raise ValueError("manual-by-design connectivity row requires review_condition")
        if self.disposition is SourceConnectivityDisposition.CONNECTED:
            if self.connected_proof is None:
                raise ValueError("connected connectivity row requires complete connected_proof")
        elif self.connected_proof is not None:
            raise ValueError("only a connected connectivity row may carry connected_proof")
        if (
            self.expires_on is not None
            and self.bounded_follow_up is not None
            and self.bounded_follow_up.deadline > self.expires_on
        ):
            raise ValueError("bounded follow-up deadline must not outlive the review expiry")
        return self

    def expiry_posture(self, *, as_of: date) -> SourceConnectivityExpiryPosture:
        """Evaluate expiry deterministically at the caller's civil-date seam."""
        if self.expires_on is None:
            return SourceConnectivityExpiryPosture.NOT_SCHEDULED
        if as_of >= self.expires_on:
            return SourceConnectivityExpiryPosture.EXPIRED
        return SourceConnectivityExpiryPosture.CURRENT

    def follow_up_owner(self) -> str | None:
        """Return the accountable action owner, inheriting the row owner."""
        if self.bounded_follow_up is None:
            return None
        return self.bounded_follow_up.owner or self.owner
