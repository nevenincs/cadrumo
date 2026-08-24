"""Contract tests for exact profile-password assessment."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, fields

import pytest

from cadrumo.core import (
    PassphraseStrength,
    ProfilePasswordAssessment,
    ProfilePasswordRefusalReason,
    assess_profile_password,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.mark.parametrize(
    ("candidate", "accepted", "reason", "scalar_count", "utf8_byte_count"),
    [
        ("a" * 7, False, ProfilePasswordRefusalReason.TOO_FEW_SCALARS, 7, 7),
        ("a" * 8, True, None, 8, 8),
        ("a" * 256, True, None, 256, 256),
        ("a" * 257, False, ProfilePasswordRefusalReason.TOO_MANY_SCALARS, 257, 257),
        ("\U0001f512" * 256, True, None, 256, 1024),
        (
            "\U0001f512" * 256 + "a",
            False,
            ProfilePasswordRefusalReason.TOO_MANY_UTF8_BYTES,
            257,
            1025,
        ),
    ],
)
def test_profile_password_scalar_and_utf8_boundaries(
    candidate: str,
    *,
    accepted: bool,
    reason: ProfilePasswordRefusalReason | None,
    scalar_count: int,
    utf8_byte_count: int,
) -> None:
    assessment = assess_profile_password(candidate)

    assert assessment.accepted is accepted
    assert assessment.reason is reason
    assert assessment.scalar_count == scalar_count
    assert assessment.utf8_byte_count == utf8_byte_count


def test_utf8_limit_precedes_scalar_limit_when_both_are_exceeded() -> None:
    """A valid scalar is at most four bytes, so 1,025 bytes also needs 257 scalars."""
    assessment = assess_profile_password("\U0001f512" * 256 + "a")

    assert assessment.reason is ProfilePasswordRefusalReason.TOO_MANY_UTF8_BYTES


@pytest.mark.parametrize("surrogate", ["\ud800", "\udfff"])
def test_surrogate_refusal_does_not_claim_an_utf8_measurement(surrogate: str) -> None:
    assessment = assess_profile_password("a" * 14 + surrogate)

    assert assessment.accepted is False
    assert assessment.reason is ProfilePasswordRefusalReason.CONTAINS_SURROGATE
    assert assessment.scalar_count == 15
    assert assessment.utf8_byte_count is None


def test_composed_and_decomposed_sequences_are_assessed_without_normalisation() -> None:
    composed = assess_profile_password("\u00e9" * 15)
    decomposed = assess_profile_password("e\u0301" * 15)

    assert composed.accepted is True
    assert composed.scalar_count == 15
    assert composed.utf8_byte_count == 30
    assert decomposed.accepted is True
    assert decomposed.scalar_count == 30
    assert decomposed.utf8_byte_count == 45


def test_assessment_exposes_only_typed_secret_free_facts() -> None:
    assessment = assess_profile_password("a" * 7)

    assert isinstance(assessment.reason, ProfilePasswordRefusalReason)
    assert isinstance(assessment.scalar_count, int)
    assert isinstance(assessment.utf8_byte_count, int)
    assert isinstance(assessment.strength, PassphraseStrength)
    assert {field.name for field in fields(ProfilePasswordAssessment)} == {
        "reason",
        "scalar_count",
        "utf8_byte_count",
        "strength",
    }
    assert not hasattr(assessment, "__dict__")
    with pytest.raises(FrozenInstanceError):
        assessment.scalar_count = 15  # type: ignore[misc]


def test_advisory_strength_neither_accepts_nor_refuses_a_password() -> None:
    strong_but_too_short = assess_profile_password("Aa1!xxx")
    weak_but_valid = assess_profile_password("x" * 8)

    assert strong_but_too_short.strength is PassphraseStrength.FAIR
    assert strong_but_too_short.reason is ProfilePasswordRefusalReason.TOO_FEW_SCALARS
    assert weak_but_valid.strength is PassphraseStrength.WEAK
    assert weak_but_valid.accepted is True
