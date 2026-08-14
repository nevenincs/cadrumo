"""Canonical hold evidence models used by profile custody transactions."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal, cast
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from ...core import STRICT_FROZEN_CONFIG
from ...core.time import validate_utc_aware
from .._profile_deletion_hold_contract import ProfileDeletionHoldOwnerProjection


class ProfileCustodyHoldAssessment(BaseModel):
    """The bound outcome from the independent legal and filing hold owners."""

    model_config = STRICT_FROZEN_CONFIG

    profile_id: UUID
    legal_hold: bool
    filing_hold: bool
    assessed_at: datetime
    assessor: Literal["application-custody-hold-owner"] = "application-custody-hold-owner"
    evidence_digest: str = Field(min_length=71, max_length=71)

    @model_validator(mode="after")
    def _validate_assessed_at(self) -> ProfileCustodyHoldAssessment:
        validate_utc_aware(self.assessed_at)
        return self

    @property
    def permits_local_deletion(self) -> bool:
        return not self.legal_hold and not self.filing_hold

    @classmethod
    def from_owner_evidence(
        cls,
        *,
        legal: ProfileCustodyHoldEvidence,
        filing: ProfileCustodyHoldEvidence,
    ) -> ProfileCustodyHoldAssessment:
        if legal.profile_id != filing.profile_id:
            from ._custody_transactions import ProfileCustodyTransactionCorruptError

            raise ProfileCustodyTransactionCorruptError("hold owners disagree on profile identity")
        assessed_at = max(legal.assessed_at, filing.assessed_at)
        payload = {
            "profile_id": str(legal.profile_id),
            "legal_evidence_digest": legal.evidence_digest,
            "filing_evidence_digest": filing.evidence_digest,
            "assessed_at": assessed_at.astimezone(UTC).isoformat(),
            "assessor": "application-custody-hold-owner",
        }
        from ._custody_transactions import _canonical_bytes, _digest

        return cls(
            profile_id=legal.profile_id,
            legal_hold=legal.blocks_local_deletion,
            filing_hold=filing.blocks_local_deletion,
            assessed_at=assessed_at,
            assessor="application-custody-hold-owner",
            evidence_digest=_digest(_canonical_bytes(payload, maximum_bytes=1024, subject="hold assessment")),
        )


class ProfileCustodyHoldEvidence(BaseModel):
    """One immutable canonical answer from a legal or filing hold owner."""

    model_config = STRICT_FROZEN_CONFIG

    schema_version: Literal[1] = 1
    owner: Literal["legal", "filing"]
    profile_id: UUID
    disposition: Literal["cleared", "held"]
    source_record_id: str = Field(min_length=3, max_length=256)
    source_record_digest: str = Field(min_length=71, max_length=71)
    assessed_at: datetime
    authority: Literal["application-legal-hold-owner", "application-filing-hold-owner"]
    evidence_digest: str = Field(min_length=71, max_length=71)

    @field_validator("source_record_id")
    @classmethod
    def _validate_source_record_id(cls, value: str) -> str:
        if value != value.strip() or any(character in value for character in "\\/\x00"):
            raise ValueError("hold source record id must be one bounded canonical identifier")
        return value

    @field_validator("source_record_digest")
    @classmethod
    def _validate_source_record_digest(cls, value: str) -> str:
        from ._custody_transactions import validate_sha256_digest

        return validate_sha256_digest(value, subject="hold source record digest")

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
        return self.disposition == "held"

    @property
    def canonical_payload(self) -> dict[str, object]:
        payload = cast(dict[str, object], self.model_dump(mode="json"))
        del payload["evidence_digest"]
        return payload

    @property
    def computed_evidence_digest(self) -> str:
        from ._custody_transactions import _canonical_bytes, _digest

        return _digest(_canonical_bytes(self.canonical_payload, maximum_bytes=1024, subject="hold evidence"))


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
