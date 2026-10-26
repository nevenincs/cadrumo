"""Canonical secure payload for Modelo 390 applicability evidence."""

from __future__ import annotations

import json
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, ValidationError, model_validator

from ...core.filing_year import FilingYear
from ...core.hashing import canonical_json_bytes, reject_duplicate_json_members, reject_json_constant
from ...core.identity.digest import ContentDigest
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.period import Period
from ...core.time.utc import UtcInstant
from ..user_profile.values import UserProfileRecord
from .errors import AttachmentValidationError

M303_EXONERADO_390_APPLICABILITY_SCHEMA_VERSION = 1
M303_EXONERADO_390_APPLICABILITY_ROLE = "m303_exonerado_390_applicability"


class M303Exonerado390ApplicabilityAssertion(StrEnum):
    """Closed operator assertions for one Modelo 390 applicability fact."""

    NOT_APPLICABLE = "not_applicable"
    APPLICABLE = "applicable"


class M303Exonerado390ApplicabilityProfileWitness(BaseModel):
    """Authenticated current-profile coordinate an attestation is bound to."""

    model_config = STRICT_FROZEN_CONFIG

    profile_id: str = Field(min_length=1)
    record_revision: int = Field(ge=1)
    content_digest: ContentDigest
    schema_id: str = Field(min_length=1)
    schema_version: int = Field(ge=1)

    @classmethod
    def from_profile_record(cls, record: UserProfileRecord) -> M303Exonerado390ApplicabilityProfileWitness:
        """Project the exact immutable witness from an authenticated profile record.

        Core types:
        :class:`~cadrumo.domain.user_profile.values.UserProfileRecord`.
        """
        return cls(
            profile_id=record.profile_id,
            record_revision=record.record_revision,
            content_digest=record.content_digest,
            schema_id=record.schema_id,
            schema_version=record.schema_version,
        )


class M303Exonerado390ApplicabilityAttestation(BaseModel):
    """One canonical, custody-bound operator assertion for an M303 coordinate."""

    model_config = STRICT_FROZEN_CONFIG

    schema_version: Literal[1] = M303_EXONERADO_390_APPLICABILITY_SCHEMA_VERSION
    role: Literal["m303_exonerado_390_applicability"] = M303_EXONERADO_390_APPLICABILITY_ROLE
    asserted_value: M303Exonerado390ApplicabilityAssertion
    filing_year: FilingYear
    period: Period
    observed_at: UtcInstant
    profile_witness: M303Exonerado390ApplicabilityProfileWitness

    @model_validator(mode="after")
    def _period_matches_filing_year(self) -> M303Exonerado390ApplicabilityAttestation:
        if self.period.filing_year != self.filing_year:
            raise AttachmentValidationError("Modelo 390 applicability attestation period disagrees with filing year")
        return self

    def canonical_json_bytes(self) -> bytes:
        """Return the sole custody byte spelling for this typed assertion."""
        return canonical_json_bytes(self.model_dump(mode="json"))


def parse_m303_exonerado_390_applicability_attestation(
    payload: bytes,
) -> M303Exonerado390ApplicabilityAttestation:
    """Strictly parse and canonical-byte-check one stored applicability assertion."""
    try:
        decoded = payload.decode("utf-8")
        json.loads(
            decoded,
            object_pairs_hook=reject_duplicate_json_members,
            parse_constant=reject_json_constant,
        )
        attestation = M303Exonerado390ApplicabilityAttestation.model_validate_json(payload)
    except (UnicodeDecodeError, ValueError, ValidationError) as exc:
        raise AttachmentValidationError("Modelo 390 applicability attestation is invalid") from exc
    if attestation.canonical_json_bytes() != payload:
        raise AttachmentValidationError("Modelo 390 applicability attestation is not canonical")
    return attestation


__all__ = [
    "M303_EXONERADO_390_APPLICABILITY_ROLE",
    "M303_EXONERADO_390_APPLICABILITY_SCHEMA_VERSION",
    "M303Exonerado390ApplicabilityAssertion",
    "M303Exonerado390ApplicabilityAttestation",
    "M303Exonerado390ApplicabilityProfileWitness",
    "parse_m303_exonerado_390_applicability_attestation",
]
