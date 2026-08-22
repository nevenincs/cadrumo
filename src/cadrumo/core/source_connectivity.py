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
from typing import Annotated, Protocol, Self, runtime_checkable
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, StringConstraints, ValidationInfo, model_validator

from ._models import STRICT_FROZEN_CONFIG
from .aggregation import BindingSourceKind
from .identity import CalculationRevisionId, ContentDigest

__all__ = [
    "SourceConnectivityCandidateId",
    "SourceConnectivityCandidateIdentity",
    "SourceConnectivityCensusRow",
    "SourceConnectivityConnectedProof",
    "SourceConnectivityConnectionIdentity",
    "SourceConnectivityDisposition",
    "SourceConnectivityEncryptedRevisionProof",
    "SourceConnectivityExecutableEvidence",
    "SourceConnectivityExecutableEvidenceRole",
    "SourceConnectivityExpiryPosture",
    "SourceConnectivityFollowUp",
    "SourceConnectivityGrounding",
    "SourceConnectivityGroundingLocatorKind",
    "SourceConnectivityOperatorReachabilityProof",
    "SourceConnectivityProofAuthority",
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
_StrictBoolean = Annotated[bool, Field(strict=True)]


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


class SourceConnectivityConnectionIdentity(SourceConnectivityCandidateIdentity):
    """Shared identity of one source-to-revision production connection."""

    source_kind: BindingSourceKind
    source_ref: _StableToken
    resolver_id: _StableToken
    calculation_revision_id: CalculationRevisionId


class SourceConnectivityExecutableEvidenceRole(StrEnum):
    """Behavior an executable evidence artifact independently proves."""

    RESOLVER_ENROLLMENT = "resolver_enrollment"
    ENCRYPTED_REVISION = "encrypted_revision"
    OPERATOR_REACHABILITY = "operator_reachability"


class SourceConnectivityExecutableEvidence(BaseModel):
    """Stable executable proof tied to one exact production connection."""

    model_config = STRICT_FROZEN_CONFIG

    evidence_id: _StableToken
    role: SourceConnectivityExecutableEvidenceRole
    connection: SourceConnectivityConnectionIdentity
    locator: SourceConnectivityGrounding
    content_digest: ContentDigest

    @model_validator(mode="after")
    def _require_test_evidence(self) -> SourceConnectivityExecutableEvidence:
        """Refuse prose, implementation, or non-executable evidence locators."""
        if self.locator.locator_kind is not SourceConnectivityGroundingLocatorKind.REPOSITORY:
            raise ValueError("connected proof requires repository-backed executable evidence")
        path = self.locator.reference.partition(":")[0]
        if "/tests/" not in path or not path.rsplit("/", maxsplit=1)[-1].startswith("test_"):
            raise ValueError("connected proof evidence must identify a test module")
        return self


@runtime_checkable
class SourceConnectivityProofAuthority(Protocol):
    """Live authority required to admit a persisted ``connected`` claim."""

    def source_is_enrolled(self, connection: SourceConnectivityConnectionIdentity) -> bool:
        """Return whether the canonical source mesh currently enrolls this source."""

    def operator_workflow_is_supported(
        self,
        connection: SourceConnectivityConnectionIdentity,
        *,
        entrypoint_id: str,
        command_id: str,
    ) -> bool:
        """Return whether the live operator catalogue owns this workflow identity."""

    def encrypted_revision_matches(
        self,
        proof: SourceConnectivityEncryptedRevisionProof,
    ) -> bool:
        """Return whether encrypted storage contains the exact asserted source proof."""

    def executable_evidence_digest(self, evidence: SourceConnectivityExecutableEvidence) -> ContentDigest | None:
        """Return the verified digest of the existing executable artifact, if any."""


class SourceConnectivityResolverOwnershipProof(BaseModel):
    """Evidence that one canonical resolver owns the candidate source."""

    model_config = STRICT_FROZEN_CONFIG

    connection: SourceConnectivityConnectionIdentity
    owner: _BoundedText
    enrollment_evidence: tuple[SourceConnectivityExecutableEvidence, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _bind_enrollment_evidence(self) -> SourceConnectivityResolverOwnershipProof:
        """Require every enrollment proof to name this exact connection."""
        _require_matching_evidence(
            self.connection,
            self.enrollment_evidence,
            role=SourceConnectivityExecutableEvidenceRole.RESOLVER_ENROLLMENT,
        )
        return self


class SourceConnectivityEncryptedRevisionProof(BaseModel):
    """Evidence that source provenance survives encrypted revision storage."""

    model_config = STRICT_FROZEN_CONFIG

    connection: SourceConnectivityConnectionIdentity
    persisted_source_identity: _StableToken
    persisted_source_fingerprint: _StableToken
    strict_round_trip: _StrictBoolean
    encrypted_at_rest: _StrictBoolean
    anti_tautology_mutation: _StrictBoolean
    evidence: tuple[SourceConnectivityExecutableEvidence, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _require_strict_revision_proof(self) -> SourceConnectivityEncryptedRevisionProof:
        """Require true strict-storage claims tied to this exact connection."""
        if not (self.strict_round_trip and self.encrypted_at_rest and self.anti_tautology_mutation):
            raise ValueError("encrypted revision proof requires every strict proof assertion")
        if self.persisted_source_identity != self.connection.source_ref:
            raise ValueError("persisted source identity must match the asserted source reference")
        _require_matching_evidence(
            self.connection,
            self.evidence,
            role=SourceConnectivityExecutableEvidenceRole.ENCRYPTED_REVISION,
        )
        return self


class SourceConnectivityOperatorReachabilityProof(BaseModel):
    """Evidence that a supported operator workflow reaches the resolver."""

    model_config = STRICT_FROZEN_CONFIG

    connection: SourceConnectivityConnectionIdentity
    entrypoint_id: _StableToken
    command_id: _StableToken
    resolver_observed: _StrictBoolean
    evidence: tuple[SourceConnectivityExecutableEvidence, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _require_observed_connection(self) -> SourceConnectivityOperatorReachabilityProof:
        """Require executable observation of this exact resolver and source."""
        if not self.resolver_observed:
            raise ValueError("operator reachability proof requires an observed resolver")
        _require_matching_evidence(
            self.connection,
            self.evidence,
            role=SourceConnectivityExecutableEvidenceRole.OPERATOR_REACHABILITY,
        )
        return self


class SourceConnectivityConnectedProof(BaseModel):
    """Complete production proof required by a ``connected`` census claim."""

    model_config = STRICT_FROZEN_CONFIG

    resolver_ownership: SourceConnectivityResolverOwnershipProof
    encrypted_revision: SourceConnectivityEncryptedRevisionProof
    operator_reachability: SourceConnectivityOperatorReachabilityProof

    @model_validator(mode="after")
    def _require_one_connection(self) -> SourceConnectivityConnectedProof:
        """Refuse proof components describing different production paths."""
        identity = self.resolver_ownership.connection
        if self.encrypted_revision.connection != identity or self.operator_reachability.connection != identity:
            raise ValueError("connected proof components must identify the same connection")
        return self

    @property
    def connection(self) -> SourceConnectivityConnectionIdentity:
        """Return the connection identity shared by every proof component."""
        return self.resolver_ownership.connection


def _require_matching_evidence(
    connection: SourceConnectivityConnectionIdentity,
    evidence: tuple[SourceConnectivityExecutableEvidence, ...],
    *,
    role: SourceConnectivityExecutableEvidenceRole,
) -> None:
    """Refuse executable evidence for another candidate or source path."""
    if any(item.connection != connection for item in evidence):
        raise ValueError("connected proof evidence must identify the asserted connection")
    if any(item.role is not role for item in evidence):
        raise ValueError(f"connected proof evidence must carry role {role.value!r}")


def _connected_executable_evidence(
    proof: SourceConnectivityConnectedProof,
) -> tuple[SourceConnectivityExecutableEvidence, ...]:
    """Return every role-specific executable artifact in one connected proof."""
    return (
        *proof.resolver_ownership.enrollment_evidence,
        *proof.encrypted_revision.evidence,
        *proof.operator_reachability.evidence,
    )


_BLOCKED_DISPOSITIONS = frozenset(
    {
        SourceConnectivityDisposition.GROUNDING_BLOCKED,
        SourceConnectivityDisposition.INGRESS_BLOCKED,
        SourceConnectivityDisposition.REGISTRY_BLOCKED,
    },
)


class SourceConnectivityCensusRow(SourceConnectivityCandidateIdentity):
    """Governed adjudication record for one stable connectivity candidate.

    Every disposition carries evidence and accountability. A ``connected`` row
    additionally carries relational proof that one candidate and source path
    owns resolution, encrypted revision persistence, and operator reachability.
    """

    disposition: SourceConnectivityDisposition
    grounding: tuple[SourceConnectivityGrounding, ...] = Field(min_length=1)
    owner: _BoundedText
    review_condition: _BoundedText | None = None
    expires_on: date | None = None
    bounded_follow_up: SourceConnectivityFollowUp | None = None
    connected_proof: SourceConnectivityConnectedProof | None = None

    @model_validator(mode="after")
    def _require_actionable_unresolved_state(self, info: ValidationInfo) -> SourceConnectivityCensusRow:
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
            if self.connected_proof.connection.candidate_id != self.candidate_id:
                raise ValueError("connected proof candidate_id must match the census row")
            authority = (info.context or {}).get("source_connectivity_proof_authority")
            if not isinstance(authority, SourceConnectivityProofAuthority):
                raise ValueError("connected connectivity row requires live proof authority validation")
            self._verify_connected_authority(authority)
        elif self.connected_proof is not None:
            raise ValueError("only a connected connectivity row may carry connected_proof")
        if (
            self.expires_on is not None
            and self.bounded_follow_up is not None
            and self.bounded_follow_up.deadline > self.expires_on
        ):
            raise ValueError("bounded follow-up deadline must not outlive the review expiry")
        return self

    @classmethod
    def validate_with_authority(
        cls,
        value: object,
        *,
        authority: SourceConnectivityProofAuthority,
    ) -> Self:
        """Validate a census row with the mandatory live connected-proof authority."""
        return cls.model_validate(
            value,
            context={"source_connectivity_proof_authority": authority},
        )

    def _verify_connected_authority(self, authority: SourceConnectivityProofAuthority) -> None:
        """Require live enrollment, workflow, and executable-evidence authority."""
        proof = self.connected_proof
        if proof is None:
            raise ValueError("connected connectivity row requires complete connected_proof")
        connection = proof.connection
        if not authority.source_is_enrolled(connection):
            raise ValueError("connected proof source is not enrolled by the live source mesh")
        operator = proof.operator_reachability
        if not authority.operator_workflow_is_supported(
            connection,
            entrypoint_id=operator.entrypoint_id,
            command_id=operator.command_id,
        ):
            raise ValueError("connected proof operator workflow is not supported")
        if not authority.encrypted_revision_matches(proof.encrypted_revision):
            raise ValueError("connected proof encrypted revision does not match persisted source provenance")
        for evidence in _connected_executable_evidence(proof):
            verified_digest = authority.executable_evidence_digest(evidence)
            if verified_digest is None or verified_digest != evidence.content_digest:
                raise ValueError(
                    f"connected proof executable evidence is absent or changed: {evidence.evidence_id}",
                )

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
