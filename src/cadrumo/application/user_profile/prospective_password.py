"""Application presentation contract for prospective profile-password refusals."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

from ...core import (
    PROFILE_PASSWORD_MAX_SCALARS,
    PROFILE_PASSWORD_MAX_UTF8_BYTES,
    PROFILE_PASSWORD_MIN_SCALARS,
    ProfilePasswordAssessment,
    ProfilePasswordRefusalReason,
)

_MESSAGE_LOCALE_KEYS: Final[dict[ProfilePasswordRefusalReason, str]] = {
    ProfilePasswordRefusalReason.CONTAINS_SURROGATE: (
        "application.user_profile.errors.profile_password_contains_surrogate"
    ),
    ProfilePasswordRefusalReason.TOO_FEW_SCALARS: ("application.user_profile.errors.profile_password_too_few_scalars"),
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

    @property
    def context(self) -> Mapping[str, object]:
        """Return immutable presentation facts derived from the typed fields."""
        context: dict[str, object] = {
            "reason": self.reason.value,
            "scalar_count": self.scalar_count,
        }
        if self.utf8_byte_count is not None:
            context["utf8_byte_count"] = self.utf8_byte_count
        if self.reason is ProfilePasswordRefusalReason.TOO_FEW_SCALARS:
            context["minimum_scalars"] = PROFILE_PASSWORD_MIN_SCALARS
        elif self.reason is ProfilePasswordRefusalReason.TOO_MANY_SCALARS:
            context["maximum_scalars"] = PROFILE_PASSWORD_MAX_SCALARS
        elif self.reason is ProfilePasswordRefusalReason.TOO_MANY_UTF8_BYTES:
            context["maximum_utf8_bytes"] = PROFILE_PASSWORD_MAX_UTF8_BYTES
        return MappingProxyType(context)


def prospective_profile_password_refusal(
    assessment: ProfilePasswordAssessment,
) -> ProspectiveProfilePasswordRefusal | None:
    """Map a canonical assessment to stable application presentation facts."""
    reason = assessment.reason
    if reason is None:
        return None

    return ProspectiveProfilePasswordRefusal(
        reason=reason,
        scalar_count=assessment.scalar_count,
        utf8_byte_count=assessment.utf8_byte_count,
        translated_message=_MESSAGE_LOCALE_KEYS[reason],
    )


__all__ = ["ProspectiveProfilePasswordRefusal", "prospective_profile_password_refusal"]
