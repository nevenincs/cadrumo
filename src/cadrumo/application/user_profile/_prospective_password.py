"""Application presentation contract for prospective profile-password refusals."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from ...core import (
    PROFILE_PASSWORD_MAX_SCALARS,
    PROFILE_PASSWORD_MAX_UTF8_BYTES,
    PROFILE_PASSWORD_MIN_SCALARS,
    ProfilePasswordAssessment,
    ProfilePasswordRefusalReason,
)

_MESSAGE_KEYS: Final[dict[ProfilePasswordRefusalReason, str]] = {
    ProfilePasswordRefusalReason.CONTAINS_SURROGATE: (
        "application.user_profile.errors.profile_password_contains_surrogate"
    ),
    ProfilePasswordRefusalReason.TOO_FEW_SCALARS: (
        "application.user_profile.errors.profile_password_too_few_scalars"
    ),
    ProfilePasswordRefusalReason.TOO_MANY_SCALARS: (
        "application.user_profile.errors.profile_password_too_many_scalars"
    ),
    ProfilePasswordRefusalReason.TOO_MANY_UTF8_BYTES: (
        "application.user_profile.errors.profile_password_too_many_utf8_bytes"
    ),
}


@dataclass(frozen=True, slots=True)
class ProspectiveProfilePasswordRefusal:
    """Typed, secret-free application outcome for an invalid new password."""

    reason: ProfilePasswordRefusalReason
    scalar_count: int
    utf8_byte_count: int | None
    translated_message: str
    context: dict[str, object]


def prospective_profile_password_refusal(
    assessment: ProfilePasswordAssessment,
) -> ProspectiveProfilePasswordRefusal | None:
    """Map a canonical assessment to stable application presentation facts."""
    reason = assessment.reason
    if reason is None:
        return None

    context: dict[str, object] = {
        "reason": reason.value,
        "scalar_count": assessment.scalar_count,
    }
    if assessment.utf8_byte_count is not None:
        context["utf8_byte_count"] = assessment.utf8_byte_count
    if reason is ProfilePasswordRefusalReason.TOO_FEW_SCALARS:
        context["minimum_scalars"] = PROFILE_PASSWORD_MIN_SCALARS
    elif reason is ProfilePasswordRefusalReason.TOO_MANY_SCALARS:
        context["maximum_scalars"] = PROFILE_PASSWORD_MAX_SCALARS
    elif reason is ProfilePasswordRefusalReason.TOO_MANY_UTF8_BYTES:
        context["maximum_utf8_bytes"] = PROFILE_PASSWORD_MAX_UTF8_BYTES

    return ProspectiveProfilePasswordRefusal(
        reason=reason,
        scalar_count=assessment.scalar_count,
        utf8_byte_count=assessment.utf8_byte_count,
        translated_message=_MESSAGE_KEYS[reason],
        context=context,
    )


__all__ = ["ProspectiveProfilePasswordRefusal", "prospective_profile_password_refusal"]
