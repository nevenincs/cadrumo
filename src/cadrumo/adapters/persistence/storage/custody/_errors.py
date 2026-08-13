"""Typed refusals and integrity failures for profile custody."""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum

from ..errors import SecretStoreError


class ProfileCustodyRefusal(StrEnum):
    """Stable refusal reasons exposed by the current custody contract."""

    LEGACY_CUSTODY_DETECTED = "LEGACY_CUSTODY_DETECTED"
    DEK_ROTATION_UNSUPPORTED = "DEK_ROTATION_UNSUPPORTED"
    KDF_RESOURCE_LIMIT = "KDF_RESOURCE_LIMIT"
    KDF_SUPERVISION_UNAVAILABLE = "KDF_SUPERVISION_UNAVAILABLE"


class ProfileCustodyError(SecretStoreError):
    """Base failure for profile-scoped password custody."""


class ProfileCustodyRecordError(ProfileCustodyError, ValueError):
    """Raised when a current-format custody record is malformed or altered."""


class ProfileCustodyPasswordError(ProfileCustodyError, ValueError):
    """Raised when a password cannot be represented by the custody contract."""


class ProfileCustodyRefusedError(ProfileCustodyError):
    """Raised for a deliberate, stable current-custody refusal."""

    def __init__(
        self,
        refusal: ProfileCustodyRefusal,
        *,
        context: Mapping[str, object] | None = None,
    ) -> None:
        payload: dict[str, object] = {"refusal": refusal.value}
        if context is not None:
            payload.update((key, value) for key, value in context.items() if key != "refusal")
        super().__init__(refusal.value, context=payload)
        self.refusal = refusal


__all__ = [
    "ProfileCustodyError",
    "ProfileCustodyPasswordError",
    "ProfileCustodyRecordError",
    "ProfileCustodyRefusal",
    "ProfileCustodyRefusedError",
]
