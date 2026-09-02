"""Canonical hold evidence models used by profile custody transactions."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Final, Literal, cast
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from ...core.identity import PrefixedContentDigest
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.time.utc import validate_utc_aware
from ..profile_deletion_hold_contract import ProfileDeletionHoldOwnerProjection, ProfileDeletionHoldOwnerValue

#: Current write version for :class:`ProfileCustodyHoldEvidence`. This format is
#: REGENERABLE (see the campaign's nested-persisted-format-boundary ADR): its
#: ``refresh()`` writer unconditionally recomputes and overwrites, and nothing
#: reads its on-disk file back through the typed model, so no upgrader or
#: durability floor applies -- naming the constant is the outstanding half of
#: its classification.
CUSTODY_HOLD_EVIDENCE_SCHEMA_VERSION: Final[Literal[1]] = 1


class ProfileCustodyRetentionOverride(BaseModel):
    """One operator authorisation to erase despite an asserted filing hold.

    A model rather than a boolean because a bare ``True`` can be defaulted or
    passed by accident, while this cannot be constructed empty: the mandatory
    non-empty reason the CLI promises is enforced by the type at every entry
    instead of re-checked per caller. It is persisted into the digest-bound
    delete journal, so the authorisation travels with the transaction as
    durable evidence rather than as a transient argument, and cannot be edited
    in afterwards.

    It authorises exactly one thing: proceeding past a FILING hold, which is
    the statutory retention floor. It carries no power over a legal hold.
    """

    model_config = STRICT_FROZEN_CONFIG

    reason: str = Field(min_length=1, max_length=512)
    approved_at: datetime
    retained_record_count: int = Field(ge=1)
    latest_safe_erase_date: datetime | None = None

    @model_validator(mode="after")
    def _validate_instants(self) -> ProfileCustodyRetentionOverride:
        validate_utc_aware(self.approved_at)
        if self.latest_safe_erase_date is not None:
            validate_utc_aware(self.latest_safe_erase_date)
        return self


def hold_permits_local_deletion(
    assessment: ProfileCustodyHoldAssessment,
    *,
    retention_override: ProfileCustodyRetentionOverride | None,
) -> bool:
    """The ONE place a gate decides whether holds permit this deletion.

    Single-sited on purpose. Two custody gates ask this question -- delete
    preparation and the pre-effect re-validation -- and inlining the boolean at
    both is how one of them silently keeps refusing an authorisation the other
    honours, which is the defect this function exists to end.

    A legal hold is absolute: no operator authorisation clears it, which is why
    it short-circuits first. A filing hold is the statutory retention floor,
    and the reset's own backstop has always let a recorded override past it --
    so an override presented here clears that half and only that half.
    """
    if assessment.legal_hold:
        return False
    return not assessment.filing_hold or retention_override is not None


class ProfileCustodyHoldAssessment(BaseModel):
    """The bound outcome from the independent legal and filing hold owners."""

    model_config = STRICT_FROZEN_CONFIG

    profile_id: UUID
    legal_hold: bool
    filing_hold: bool
    assessed_at: datetime
    assessor: Literal["application-custody-hold-owner"] = "application-custody-hold-owner"
    evidence_digest: PrefixedContentDigest

    @model_validator(mode="after")
    def _validate_assessed_at(self) -> ProfileCustodyHoldAssessment:
        validate_utc_aware(self.assessed_at)
        return self

    @property
    def permits_local_deletion(self) -> bool:
        """The RAW owner fact: do both owners currently permit local deletion?

        Deliberately override-blind. This is what the owners assessed, and the
        evidence record must keep saying ``filing_hold=True`` when a filing
        hold exists -- an override is a decision ABOUT that fact, never a
        different fact, and falsifying the assessment to clear a gate would
        make ``evidence_digest`` attest something the owners never found.

        Every gate deciding whether a deletion may PROCEED calls
        :func:`hold_permits_local_deletion` instead, which weighs this fact
        against a recorded operator authorisation. A gate reading this property
        directly would silently ignore that authorisation.
        """
        return not self.legal_hold and not self.filing_hold

    @classmethod
    def from_owner_evidence(
        cls,
        *,
        legal: ProfileCustodyHoldEvidence,
        filing: ProfileCustodyHoldEvidence,
    ) -> ProfileCustodyHoldAssessment:
        """Build an assessment from the legal and filing owner evidence."""
        if legal.profile_id != filing.profile_id:
            from .custody_transactions import ProfileCustodyTransactionCorruptError

            raise ProfileCustodyTransactionCorruptError("hold owners disagree on profile identity")
        assessed_at = max(legal.assessed_at, filing.assessed_at)
        payload = {
            "profile_id": str(legal.profile_id),
            "legal_evidence_digest": legal.evidence_digest,
            "filing_evidence_digest": filing.evidence_digest,
            "assessed_at": assessed_at.astimezone(UTC).isoformat(),
            "assessor": "application-custody-hold-owner",
        }
        from .custody_transactions import canonical_payload_digest

        return cls(
            profile_id=legal.profile_id,
            legal_hold=legal.blocks_local_deletion,
            filing_hold=filing.blocks_local_deletion,
            assessed_at=assessed_at,
            assessor="application-custody-hold-owner",
            evidence_digest=canonical_payload_digest(payload, maximum_bytes=1024, subject="hold assessment"),
        )


class ProfileCustodyHoldEvidence(BaseModel):
    """One immutable canonical answer from a legal or filing hold owner."""

    model_config = STRICT_FROZEN_CONFIG

    schema_version: Literal[1] = CUSTODY_HOLD_EVIDENCE_SCHEMA_VERSION
    owner: ProfileDeletionHoldOwnerValue
    profile_id: UUID
    disposition: Literal["cleared", "held"]
    source_record_id: str = Field(min_length=3, max_length=256)
    source_record_digest: PrefixedContentDigest
    assessed_at: datetime
    authority: Literal["application-legal-hold-owner", "application-filing-hold-owner"]
    evidence_digest: PrefixedContentDigest

    @field_validator("source_record_id")
    @classmethod
    def _validate_source_record_id(cls, value: str) -> str:
        if value != value.strip() or any(character in value for character in "\\/\x00"):
            raise ValueError("hold source record id must be one bounded canonical identifier")
        return value

    @field_validator("source_record_digest")
    @classmethod
    def _validate_source_record_digest(cls, value: str) -> str:
        from ...core.hashing import validate_prefixed_digest

        return validate_prefixed_digest(value, field_name="hold source record digest")

    @model_validator(mode="after")
    def _validate_proof(self) -> ProfileCustodyHoldEvidence:
        validate_utc_aware(self.assessed_at)
        expected_authority = f"application-{self.owner}-hold-owner"
        if self.authority != expected_authority:
            raise ValueError("hold evidence authority does not own its evidence kind")
        if self.evidence_digest != self.computed_evidence_digest:
            raise ValueError("hold evidence digest does not match its authoritative fields")
        return self

    @property
    def blocks_local_deletion(self) -> bool:
        """Return whether this owner's disposition blocks local deletion."""
        return self.disposition == "held"

    @property
    def canonical_payload(self) -> dict[str, object]:
        """Return the evidence fields excluding the digest."""
        payload = cast(dict[str, object], self.model_dump(mode="json"))
        del payload["evidence_digest"]
        return payload

    @property
    def computed_evidence_digest(self) -> str:
        """Compute the canonical digest for this evidence payload."""
        from .custody_transactions import canonical_payload_digest

        return canonical_payload_digest(self.canonical_payload, maximum_bytes=1024, subject="hold evidence")


def evidence_from_owner_projection(projection: ProfileDeletionHoldOwnerProjection) -> ProfileCustodyHoldEvidence:
    """Create derived custody evidence from a read-only external owner projection."""
    authority = cast(
        Literal["application-legal-hold-owner", "application-filing-hold-owner"],
        f"application-{projection.owner}-hold-owner",
    )
    values: dict[str, Any] = {
        "owner": projection.owner,
        "profile_id": projection.profile_id,
        "disposition": "held" if projection.blocks_local_deletion else "cleared",
        "source_record_id": projection.source_record_id,
        "source_record_digest": projection.source_record_digest,
        "assessed_at": projection.assessed_at,
        "authority": authority,
    }
    unsigned = ProfileCustodyHoldEvidence.model_construct(**values, evidence_digest="")
    return ProfileCustodyHoldEvidence(**values, evidence_digest=unsigned.computed_evidence_digest)


__all__ = [
    "ProfileCustodyHoldAssessment",
    "ProfileCustodyHoldEvidence",
    "evidence_from_owner_projection",
]
