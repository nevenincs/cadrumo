"""OS keychain custody for profile acceleration receipt secrets."""

from __future__ import annotations

import binascii
from typing import Final, Protocol, cast
from uuid import UUID

from .....core.base64_codec import b64_decode, b64_encode
from .....core.logging import get_logger
from .....core.profile_session import KeychainUnavailability
from ..errors import KeyringUnavailableError, StorageValidationError
from . import acceleration_receipt_crypto as _crypto

_log = get_logger(__name__)

PROFILE_SESSION_KEYCHAIN_SERVICE: Final[str] = "cadrumo:profile-session:v2"
"""OS-keychain service name for current profile acceleration-receipt keys.

The token deliberately lags the concept name. It addresses entries in the OS
credential store, OUTSIDE the storage root, so a rename orphans every existing
entry: deleting the storage root cannot reap them, and code that deleted under
the old token first would be exactly the migration path this project forbids.
Permanent credential residue on real machines is the worse outcome, so the
wire identifier stays fixed while the code name says what the artefact is.
"""

_KEYCHAIN_PROBE_ACCOUNT: Final[str] = "availability-probe"
"""An account no receipt names: never a ``<profile UUID>:<session UUID>`` pair, so a probe reads nothing real."""

_ERROR_NO_SUCH_LOGON_SESSION: Final[int] = 1312
"""Win32 ``ERROR_NO_SUCH_LOGON_SESSION``: the credential store has no credentials for this logon."""


class _ProfileSessionKeyring(Protocol):
    """Direct subset of the OS keychain used by session acceleration."""

    def set_password(self, service_name: str, username: str, password: str) -> None:
        """Persist one secret under the immutable account."""
        ...

    def get_password(self, service_name: str, username: str) -> str | None:
        """Load one exact secret, or return no entry."""
        ...

    def delete_password(self, service_name: str, username: str) -> None:
        """Remove one exact secret."""
        ...


def _keyring() -> tuple[_ProfileSessionKeyring, type[BaseException], type[BaseException]]:
    """Return the direct OS-keychain capability without master/provider reuse."""
    try:
        import keyring
        from keyring.errors import KeyringError, PasswordDeleteError
    except ImportError as exc:
        raise KeyringUnavailableError(
            f"keyring package not importable: {exc}", unavailability=KeychainUnavailability.NO_BACKEND
        ) from exc
    try:
        priority = float(getattr(keyring.get_keyring(), "priority", 0))
    except Exception as exc:
        raise KeyringUnavailableError(
            f"OS keychain cannot be inspected: {exc}", unavailability=keychain_unavailability(exc)
        ) from exc
    if priority <= 0:
        raise KeyringUnavailableError(
            "no usable OS keychain is configured for profile-session acceleration",
            unavailability=KeychainUnavailability.NO_BACKEND,
        )
    return cast(_ProfileSessionKeyring, keyring), KeyringError, PasswordDeleteError


def keychain_unavailability(error: BaseException) -> KeychainUnavailability:
    """Name the prerequisite a keychain failure shows to be missing.

    The Windows credential store raises its own error type carrying the Win32
    code first, so the code is read structurally along the cause chain rather
    than by importing a platform type. A typed error that already names its
    reason keeps it.
    """
    seen: set[int] = set()
    current: BaseException | None = error
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, KeyringUnavailableError):
            return current.unavailability
        if type(current).__name__ == "NoKeyringError":
            return KeychainUnavailability.NO_BACKEND
        code = getattr(current, "winerror", None)
        if code is None and current.args and isinstance(current.args[0], int):
            code = current.args[0]
        if code == _ERROR_NO_SUCH_LOGON_SESSION:
            return KeychainUnavailability.LOGON_WITHOUT_CREDENTIALS
        current = current.__cause__ or current.__context__
    return KeychainUnavailability.REFUSED


def probe_profile_session_keychain() -> KeychainUnavailability | None:
    """Return why this process cannot use the keychain, or ``None`` when it can.

    The probe only reads an account no receipt ever names, so it creates,
    changes and deletes nothing. A process that cannot read the keychain can
    neither keep a sign-in nor present one, which makes this the deciding
    fact behind a sign-in that was not persisted or cannot be followed.
    """
    try:
        keyring, _keyring_error, _password_delete_error = _keyring()
        keyring.get_password(PROFILE_SESSION_KEYCHAIN_SERVICE, _KEYCHAIN_PROBE_ACCOUNT)
    except Exception as exc:
        return keychain_unavailability(exc)
    return None


def _keychain_account(*, profile_id: UUID, session_id: UUID) -> str:
    """Return the immutable UUID-pair account for one acceleration receipt."""
    return f"{profile_id}:{session_id}"


def store_acceleration_secret(*, profile_id: UUID, session_id: UUID, session_key: bytes) -> None:
    """Store and round-trip verify one fresh session key under its UUID pair."""
    if len(session_key) != _crypto.PROFILE_SESSION_KEY_BYTES:
        raise StorageValidationError(f"session_key must be exactly {_crypto.PROFILE_SESSION_KEY_BYTES} bytes")
    keyring, keyring_error, _password_delete_error = _keyring()
    account = _keychain_account(profile_id=profile_id, session_id=session_id)
    encoded = b64_encode(session_key)
    try:
        keyring.set_password(PROFILE_SESSION_KEYCHAIN_SERVICE, account, encoded)
        roundtrip = keyring.get_password(PROFILE_SESSION_KEYCHAIN_SERVICE, account)
    except keyring_error as exc:
        raise KeyringUnavailableError(
            f"OS keychain refused the profile-session key write: {exc}", unavailability=keychain_unavailability(exc)
        ) from exc
    except Exception as exc:
        raise KeyringUnavailableError(
            f"OS keychain raised unexpectedly on the profile-session key write: {exc}",
            unavailability=keychain_unavailability(exc),
        ) from exc
    if roundtrip != encoded:
        delete_acceleration_secret(profile_id=profile_id, session_id=session_id, suppress_unavailable=True)
        raise KeyringUnavailableError("OS keychain accepted the session key but its round-trip read disagreed")


def read_acceleration_secret(*, profile_id: UUID, session_id: UUID) -> bytes | None:
    """Read one receipt's session key without changing the keychain.

    Raises:
        KeyringUnavailableError: When the keychain cannot answer.
        ValueError: When the stored entry is not one encoded session key.
    """
    keyring, keyring_error, _password_delete_error = _keyring()
    account = _keychain_account(profile_id=profile_id, session_id=session_id)
    try:
        stored = keyring.get_password(PROFILE_SESSION_KEYCHAIN_SERVICE, account)
    except keyring_error as exc:
        raise KeyringUnavailableError(
            f"OS keychain refused the profile-session key read: {exc}", unavailability=keychain_unavailability(exc)
        ) from exc
    except Exception as exc:
        raise KeyringUnavailableError(
            f"OS keychain raised unexpectedly on the profile-session key read: {exc}",
            unavailability=keychain_unavailability(exc),
        ) from exc
    if stored is None:
        return None
    try:
        key = b64_decode(stored)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("profile-session keychain entry is not base64") from exc
    if len(key) != _crypto.PROFILE_SESSION_KEY_BYTES:
        raise ValueError("profile-session keychain entry has the wrong length")
    return key


def _read_keychain_entry_for_deletion(
    keyring: _ProfileSessionKeyring,
    keyring_error: type[BaseException],
    account: str,
    *,
    refusal_detail: str,
    unexpected_detail: str,
) -> str | None:
    """Read one account while preserving the deletion-phase error wording."""
    try:
        return keyring.get_password(PROFILE_SESSION_KEYCHAIN_SERVICE, account)
    except keyring_error as exc:
        raise KeyringUnavailableError(
            f"OS keychain refused the {refusal_detail}: {exc}", unavailability=keychain_unavailability(exc)
        ) from exc
    except Exception as exc:
        raise KeyringUnavailableError(
            f"OS keychain raised unexpectedly {unexpected_detail}: {exc}", unavailability=keychain_unavailability(exc)
        ) from exc


def _delete_keychain_entry(
    *,
    profile_id: UUID,
    session_id: UUID,
) -> None:
    """Delete and independently confirm one exact UUID-pair account."""
    keyring, keyring_error, password_delete_error = _keyring()
    account = _keychain_account(profile_id=profile_id, session_id=session_id)
    present = _read_keychain_entry_for_deletion(
        keyring,
        keyring_error,
        account,
        refusal_detail="profile-session key read before deletion",
        unexpected_detail="before profile-session key deletion",
    )
    if present is None:
        return
    try:
        keyring.delete_password(PROFILE_SESSION_KEYCHAIN_SERVICE, account)
    except password_delete_error:
        # A concurrent owner may have deleted it after ``present``.  Do
        # not turn that idempotent absence into a false unavailable
        # outcome; only a second exact read decides it.
        confirmed = _read_keychain_entry_for_deletion(
            keyring,
            keyring_error,
            account,
            refusal_detail="profile-session key deletion confirmation",
            unexpected_detail="during profile-session key deletion confirmation",
        )
        if confirmed is None:
            return
        raise KeyringUnavailableError("OS keychain did not confirm profile-session key deletion") from None
    except keyring_error as exc:
        raise KeyringUnavailableError(
            f"OS keychain refused the profile-session key deletion: {exc}",
            unavailability=keychain_unavailability(exc),
        ) from exc
    except Exception as exc:
        raise KeyringUnavailableError(
            f"OS keychain raised unexpectedly during profile-session key deletion: {exc}",
            unavailability=keychain_unavailability(exc),
        ) from exc
    confirmed = _read_keychain_entry_for_deletion(
        keyring,
        keyring_error,
        account,
        refusal_detail="profile-session key deletion confirmation",
        unexpected_detail="during profile-session key deletion confirmation",
    )
    if confirmed is not None:
        raise KeyringUnavailableError("OS keychain did not confirm profile-session key deletion")


def delete_acceleration_secret(
    *,
    profile_id: UUID,
    session_id: UUID,
    suppress_unavailable: bool,
) -> None:
    """Prove one known UUID-pair acceleration entry is absent.

    A missing account is an idempotent success.  A ``PasswordDeleteError``
    alone is not evidence that the backend is unavailable: a sibling may have
    retired this exact account after our first read.  Read once more and
    accept only an observed absence; otherwise preserve the calling journal
    under the typed unavailable path.
    """
    try:
        _delete_keychain_entry(profile_id=profile_id, session_id=session_id)
    except Exception as exc:
        if suppress_unavailable:
            _log.debug("profile-session key cleanup deferred error_type=%s", type(exc).__name__)
            return
        if isinstance(exc, KeyringUnavailableError):
            raise
        raise KeyringUnavailableError(
            f"OS keychain refused the profile-session key deletion: {exc}", unavailability=keychain_unavailability(exc)
        ) from exc
