"""Canonical profile-password policy and independent strength guidance.

Profile-password validity is an exact-sequence capability contract: accepted
passwords contain 8 through 256 Unicode scalar values and encode to at most
1,024 strict UTF-8 bytes. The assessment never normalises, rewrites, retains,
or returns the submitted password. Its result contains only a finite refusal
reason and numeric measurements that are safe for prospective-password
guidance.

Strength is deliberately advisory. Character-class variety can improve the
display band for a shorter passphrase, but no composition rule affects profile
password validity.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

PROFILE_PASSWORD_MIN_SCALARS: Final[int] = 8
"""Minimum Unicode scalar count for a profile password."""

PROFILE_PASSWORD_MAX_SCALARS: Final[int] = 256
"""Maximum Unicode scalar count for a profile password."""

PROFILE_PASSWORD_MAX_UTF8_BYTES: Final[int] = 1024
"""Maximum strict UTF-8 byte count for a profile password."""

LENGTH_ALONE_IS_STRONG: Final[int] = 20
"""Length at which a passphrase is advised as strong without composition."""

LENGTH_FAIR_FLOOR: Final[int] = 12
"""Length at which a passphrase is at least advised as fair."""


class ProfilePasswordRefusalReason(StrEnum):
    """Finite, secret-free reasons a prospective profile password is refused."""

    CONTAINS_SURROGATE = "contains_surrogate"
    TOO_FEW_SCALARS = "too_few_scalars"
    TOO_MANY_SCALARS = "too_many_scalars"
    TOO_MANY_UTF8_BYTES = "too_many_utf8_bytes"


class PassphraseStrength(StrEnum):
    """Advisory display band that never determines password validity."""

    WEAK = "weak"
    FAIR = "fair"
    STRONG = "strong"


@dataclass(frozen=True, slots=True)
class ProfilePasswordAssessment:
    """Secret-free assessment of a prospective profile password.

    ``utf8_byte_count`` is unavailable only when a surrogate prevents strict
    UTF-8 encoding. No field retains or derives a reproducible fingerprint of
    the candidate.
    """

    reason: ProfilePasswordRefusalReason | None
    scalar_count: int
    utf8_byte_count: int | None
    strength: PassphraseStrength

    @property
    def accepted(self) -> bool:
        """Return whether the candidate satisfies the profile-password contract."""
        return self.reason is None


def _character_class_count(candidate: str) -> int:
    """Count character classes for advisory strength only."""
    return sum(
        (
            any(character.islower() for character in candidate),
            any(character.isupper() for character in candidate),
            any(character.isdigit() for character in candidate),
            any(not character.isalnum() for character in candidate),
        ),
    )


def assess_passphrase_strength(candidate: str) -> PassphraseStrength:
    """Return advisory strength without applying a validity threshold."""
    length = len(candidate)
    if length >= LENGTH_ALONE_IS_STRONG:
        return PassphraseStrength.STRONG
    if length >= LENGTH_FAIR_FLOOR:
        return PassphraseStrength.STRONG if _character_class_count(candidate) >= 3 else PassphraseStrength.FAIR
    return PassphraseStrength.FAIR if _character_class_count(candidate) >= 3 else PassphraseStrength.WEAK


def assess_profile_password(candidate: str) -> ProfilePasswordAssessment:
    """Assess ``candidate`` exactly without retaining or rewriting it."""
    scalar_count = len(candidate)
    strength = assess_passphrase_strength(candidate)

    if any(0xD800 <= ord(character) <= 0xDFFF for character in candidate):
        return ProfilePasswordAssessment(
            reason=ProfilePasswordRefusalReason.CONTAINS_SURROGATE,
            scalar_count=scalar_count,
            utf8_byte_count=None,
            strength=strength,
        )

    utf8_byte_count = len(candidate.encode("utf-8", errors="strict"))
    if scalar_count < PROFILE_PASSWORD_MIN_SCALARS:
        reason = ProfilePasswordRefusalReason.TOO_FEW_SCALARS
    elif utf8_byte_count > PROFILE_PASSWORD_MAX_UTF8_BYTES:
        reason = ProfilePasswordRefusalReason.TOO_MANY_UTF8_BYTES
    elif scalar_count > PROFILE_PASSWORD_MAX_SCALARS:
        reason = ProfilePasswordRefusalReason.TOO_MANY_SCALARS
    else:
        reason = None

    return ProfilePasswordAssessment(
        reason=reason,
        scalar_count=scalar_count,
        utf8_byte_count=utf8_byte_count,
        strength=strength,
    )


__all__ = [
    "LENGTH_ALONE_IS_STRONG",
    "LENGTH_FAIR_FLOOR",
    "PROFILE_PASSWORD_MAX_SCALARS",
    "PROFILE_PASSWORD_MAX_UTF8_BYTES",
    "PROFILE_PASSWORD_MIN_SCALARS",
    "PassphraseStrength",
    "ProfilePasswordAssessment",
    "ProfilePasswordRefusalReason",
    "assess_passphrase_strength",
    "assess_profile_password",
]
