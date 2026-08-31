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


class ProfileRecordUnavailability(StrEnum):
    """Closed enumeration of why the active profile's record did not resolve.

    Every value names a DIFFERENT operator situation with a different remedy,
    which is the whole reason this type exists: the resolution once returned a
    bare ``None`` for all of them, and the health projection could only read
    that as an absent record.  An operator whose profile was merely locked was
    therefore told their record was gone.

    ``SESSION_REQUIRED`` is the ordinary benign state -- the capsule is
    committed and its record is intact, and nobody has logged in yet, so
    nothing about the record is knowable until they do.  It is emphatically
    not a data-loss finding.
    """

    NO_LIVE_CAPSULE = "no_live_capsule"
    """The active selector resolves to no committed capsule at all."""

    SESSION_REQUIRED = "session_required"
    """The capsule is committed but no authenticated session serves it."""

    SESSION_IDENTITY_MISMATCH = "session_identity_mismatch"
    """A session is authenticated, but for a different profile identity."""


__all__ = ["ProfileRecordUnavailability", "ProfileSessionRefusalReason"]
