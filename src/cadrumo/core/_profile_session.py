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
    NOT resumed. ``ABSENT`` is the ordinary logged-out state.  Stale,
    authenticated receipts are removed only when their exact keychain entry
    is reachable; ``KEYRING_UNAVAILABLE`` deliberately preserves that
    evidence and leaves authentication process-scoped.
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

    KEYRING_UNAVAILABLE = "keyring_unavailable"
    """The OS keychain is unavailable; existing cache evidence is retained."""

    CUSTODY_CHANGED = "custody_changed"
    """The current envelope generation or DEK epoch revoked this cache."""

    TAMPERED = "tampered"
    """AEAD tag verification failed (metadata or ciphertext altered)."""


__all__ = ["ProfileSessionRefusalReason"]
