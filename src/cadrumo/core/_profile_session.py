"""Layer-neutral profile-session lifecycle contracts.

The persisted profile session (the cross-process "logged in" state minted
by ``aeat config login``) is evaluated fail-closed on every resume. The
closed set of refusal reasons lives here in core so the storage adapter
that evaluates the session, the application login/logout services, and the
CLI Notice projection all share one typed authority instead of re-deriving
string literals per layer.
"""

from __future__ import annotations

from enum import StrEnum


class ProfileSessionRefusalReason(StrEnum):
    """Closed enumeration of fail-closed persisted-session refusal reasons.

    Every value names one branch on which a persisted profile session is
    NOT resumed. ``ABSENT`` is the ordinary logged-out state; every other
    member also implies the stale artefacts were deleted so the next
    ``aeat config login`` starts clean.
    """

    ABSENT = "absent"
    """No persisted session record exists for the bucket (logged out)."""

    MALFORMED = "malformed"
    """The on-disk record failed strict validation and was deleted."""

    SCHEMA_VERSION_MISMATCH = "schema_version_mismatch"
    """The record carries a non-current schema version; deleted, re-login."""

    EXPIRED_IDLE = "expired_idle"
    """The sliding idle deadline elapsed; deleted, re-login required."""

    EXPIRED_ABSOLUTE = "expired_absolute"
    """The immutable absolute cap elapsed; deleted, re-login required."""

    KEYCHAIN_ENTRY_MISSING = "keychain_entry_missing"
    """The OS-keychain session key vanished; treated as logged out."""

    TAMPERED = "tampered"
    """AEAD tag verification failed (metadata or ciphertext altered)."""


__all__ = ["ProfileSessionRefusalReason"]
