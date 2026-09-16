"""Supervisor-side refusals for the profile KDF worker boundary."""

from __future__ import annotations

from .errors import ProfileCustodyRefusal, ProfileCustodyRefusedError


def resource_refusal() -> ProfileCustodyRefusedError:
    return ProfileCustodyRefusedError(
        ProfileCustodyRefusal.KDF_RESOURCE_LIMIT,
        translated_message="errors.refused.refused_profile_custody_kdf_resource_limit",
    )


def supervision_refusal() -> ProfileCustodyRefusedError:
    return ProfileCustodyRefusedError(
        ProfileCustodyRefusal.KDF_SUPERVISION_UNAVAILABLE,
        translated_message="errors.refused.refused_profile_custody_kdf_supervision_unavailable",
    )


__all__ = ["resource_refusal", "supervision_refusal"]
