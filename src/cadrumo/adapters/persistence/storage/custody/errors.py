"""Typed refusals and integrity failures for profile custody."""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum

from ..errors import SecretStoreError, StorageError


class ProfileCustodyRefusal(StrEnum):
    """Stable refusal reasons exposed by the current custody contract."""

    LEGACY_CUSTODY_DETECTED = "LEGACY_CUSTODY_DETECTED"
    DEK_ROTATION_UNSUPPORTED = "DEK_ROTATION_UNSUPPORTED"
    KDF_RESOURCE_LIMIT = "KDF_RESOURCE_LIMIT"
    KDF_SUPERVISION_UNAVAILABLE = "KDF_SUPERVISION_UNAVAILABLE"


class ProfileCustodyRecoveryGuidance(StrEnum):
    """Closed operator actions accompanying a custody refusal."""

    DESTRUCTIVE_RESET = "DESTRUCTIVE_RESET"
    REENROLL_PROFILE = "REENROLL_PROFILE"


class ProfileCustodyError(SecretStoreError):
    """Base failure for profile-scoped password custody."""


class ProfileCustodyRecordError(ProfileCustodyError, ValueError):
    """Raised when a current-format custody record is malformed or altered."""


class ProfileCustodyConcurrentCapsuleChangeError(ProfileCustodyRecordError):
    """Raised when a capsule changed generation between two anchored reads.

    A committed capsule always carries its label beside the commit marker that
    proved it.  So an anchored observation that parses the marker and then
    finds no label member did not observe a malformed capsule -- it observed a
    capsule being published or deleted underneath it.  Separating that from
    :class:`ProfileCustodyRecordError` keeps a caller from reporting a
    transient race as on-disk corruption, which is the difference between
    "retry the listing" and "this store is damaged".
    """


class ProfileCustodyPasswordError(ProfileCustodyError, ValueError):
    """Raised when profile-password representation or proof is refused."""


class ProfileCustodyRecoverySecretError(ProfileCustodyError, ValueError):
    """Raised when recovery-secret representation or proof is refused."""


class ProfileCustodyRefusedError(ProfileCustodyError):
    """Raised for a deliberate, stable current-custody refusal."""

    def __init__(
        self,
        refusal: ProfileCustodyRefusal,
        *,
        context: Mapping[str, object] | None = None,
        recovery_guidance: tuple[ProfileCustodyRecoveryGuidance, ...] = (),
        translated_message: str | None = None,
    ) -> None:
        """Initialize this public contract."""
        payload: dict[str, object] = {"refusal": refusal.value}
        if recovery_guidance:
            payload["recovery_guidance"] = tuple(item.value for item in recovery_guidance)
        if context is not None:
            payload.update(
                (key, value) for key, value in context.items() if key not in {"refusal", "recovery_guidance"}
            )
        super().__init__(refusal.value, context=payload, translated_message=translated_message)
        self.refusal = refusal
        self.recovery_guidance = recovery_guidance


class WipeTypeError(StorageError, TypeError):
    """Raised when the wipe primitive receives a value it cannot overwrite.

    Zeroisation needs a mutable buffer; handing it an immutable ``bytes`` is a
    programming error whose damage is silent, because the caller believes key
    material was wiped when nothing was touched. Inherits from both
    :class:`StorageError` and :class:`TypeError` so a caller catching raw
    :class:`TypeError` still sees it while the typed storage surface
    propagates through domain boundaries.
    """


__all__ = [
    "ProfileCustodyConcurrentCapsuleChangeError",
    "ProfileCustodyError",
    "ProfileCustodyPasswordError",
    "ProfileCustodyRecordError",
    "ProfileCustodyRecoveryGuidance",
    "ProfileCustodyRecoverySecretError",
    "ProfileCustodyRefusal",
    "ProfileCustodyRefusedError",
    "WipeTypeError",
]
