"""Supervisor-side refusals for the profile KDF worker boundary."""

from __future__ import annotations

from .errors import ProfileCustodyBusyRefusedError, ProfileCustodyRefusal, ProfileCustodyRefusedError


def resource_busy_refusal() -> ProfileCustodyBusyRefusedError:
    """Return the retryable refusal for a KDF permit, lock or derivation that did not finish before its deadline."""
    return ProfileCustodyBusyRefusedError(
        ProfileCustodyRefusal.KDF_RESOURCE_BUSY,
        translated_message="errors.refused.refused_profile_custody_kdf_resource_busy",
    )


def resource_refusal() -> ProfileCustodyRefusedError:
    """Return the lasting refusal for a host that cannot supply the processors or memory a KDF request needs."""
    return ProfileCustodyRefusedError(
        ProfileCustodyRefusal.KDF_RESOURCE_LIMIT,
        translated_message="errors.refused.refused_profile_custody_kdf_resource_limit",
    )


def busy_refusal() -> ProfileCustodyBusyRefusedError:
    """Return the retryable refusal for a KDF worker that was started but did not attest in time."""
    return ProfileCustodyBusyRefusedError(
        ProfileCustodyRefusal.KDF_SUPERVISION_BUSY,
        translated_message="errors.refused.refused_profile_custody_kdf_supervision_busy",
    )


def supervision_refusal() -> ProfileCustodyRefusedError:
    """Return the custody refusal for a KDF worker that could not be started, contained or verified."""
    return ProfileCustodyRefusedError(
        ProfileCustodyRefusal.KDF_SUPERVISION_UNAVAILABLE,
        translated_message="errors.refused.refused_profile_custody_kdf_supervision_unavailable",
    )


__all__ = ["busy_refusal", "resource_busy_refusal", "resource_refusal", "supervision_refusal"]
