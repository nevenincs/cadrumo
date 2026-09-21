"""Canonical-byte contracts for Modelo 390 applicability attestations."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ....core.period import Period
from ..errors import AttachmentValidationError
from ..m303_filing_evidence import (
    M303Exonerado390ApplicabilityAssertion,
    M303Exonerado390ApplicabilityAttestation,
    M303Exonerado390ApplicabilityProfileWitness,
    parse_m303_exonerado_390_applicability_attestation,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _attestation() -> M303Exonerado390ApplicabilityAttestation:
    return M303Exonerado390ApplicabilityAttestation(
        schema_version=1,
        role="m303_exonerado_390_applicability",
        asserted_value=M303Exonerado390ApplicabilityAssertion.NOT_APPLICABLE,
        filing_year=2025,
        period=Period.from_year_and_code(2025, "1T"),
        observed_at=datetime(2025, 3, 31, 12, tzinfo=UTC),
        profile_witness=M303Exonerado390ApplicabilityProfileWitness(
            profile_id="3a1f0b2c-4d5e-4f60-8a71-92b3c4d5e6f7",
            record_revision=4,
            content_digest="a" * 64,
            schema_id="cadrumo.user_profile",
            schema_version=1,
        ),
    )


def test_payload_has_one_canonical_strict_byte_spelling() -> None:
    attestation = _attestation()

    payload = attestation.canonical_json_bytes()

    assert parse_m303_exonerado_390_applicability_attestation(payload) == attestation
    with pytest.raises(AttachmentValidationError):
        parse_m303_exonerado_390_applicability_attestation(payload.replace(b'"role"', b'"zz_role"'))
