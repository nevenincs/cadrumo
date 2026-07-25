"""Shared session-record support for the login and logout test modules.

Both suites need a *real* persisted session record to act on, but minting
one through :func:`mint_profile_session` also custodies the session key in
the OS keychain — and a host reached over a credential-less logon context
(the agent harness's SSH session, a locked keyring) cannot custody
anything, so the mint refuses and the suites lose coverage of behaviour
that never touches the keychain at all.

:func:`lay_down_keychain_free_session` closes that gap the way
``_write_aged_session`` already does for the CLI root-resume suite: it
mirrors :func:`mint_profile_session` step for step — real AEAD wrap of a
real logged-in DEK, the same clamp of the idle deadline to the absolute
cap, the same atomic on-disk write — and skips ONLY
``store_profile_session_key``. The ephemeral session key is generated and
dropped.

That is deliberately NOT a stand-in for custody. It makes exactly those
assertions reachable that :func:`resume_profile_session` decides BEFORE it
consults the keychain — the record's presence on disk, its deletion by a
handover or a logout, and the ``ABSENT`` refusal that proves nothing can
reconstruct the key material afterwards. An assertion that genuinely needs
the keychain (that the *other* half of the split-knowledge pair is gone,
or that a record can be resumed into a live session) is NOT made
reachable by this helper and must stay in a test that states its custody
precondition explicitly.
"""

from __future__ import annotations

import secrets
from datetime import timedelta
from pathlib import Path

import pytest

from ....adapters.persistence.storage.master_key import (
    PersistedProfileSession,
    current_active_bucket_session,
    profile_session_path,
    wrap_profile_session_dek,
    write_profile_session,
)
from ....core.config import SecretStoreBackend
from ....core.time import now as _now

_SESSION_KEY_BYTES = 32


def lay_down_keychain_free_session(
    *,
    storage_root: Path,
    bucket_id: str,
    dek: bytes,
    backend_kind: SecretStoreBackend = SecretStoreBackend.FILE,
    idle_minutes: int = 15,
    absolute_minutes: int = 240,
) -> PersistedProfileSession:
    """Write a genuine session record for ``bucket_id`` without custodying its key.

    Args:
        storage_root: The Cadrumo storage root owning the bucket keystore.
        bucket_id: Identifier of the bucket the record belongs to.
        dek: The real 32-byte bucket DEK to session-wrap.
        backend_kind: Custody backend recorded on the record.
        idle_minutes: Sliding idle window.
        absolute_minutes: Immutable absolute cap.

    Returns:
        The :class:`PersistedProfileSession` written to disk.
    """
    authenticated_at = _now()
    absolute_deadline = authenticated_at + timedelta(minutes=absolute_minutes)
    record = wrap_profile_session_dek(
        session_key=secrets.token_bytes(_SESSION_KEY_BYTES),
        dek=dek,
        bucket_id=bucket_id,
        backend_kind=backend_kind,
        authenticated_at=authenticated_at,
        idle_deadline=min(authenticated_at + timedelta(minutes=idle_minutes), absolute_deadline),
        absolute_deadline=absolute_deadline,
    )
    write_profile_session(storage_root=storage_root, bucket_id=bucket_id, record=record)
    return record


def lay_down_session_for_live_login(*, storage_root: Path, bucket_id: str) -> PersistedProfileSession:
    """Lay a record down for the profile currently holding the live session.

    Reads the DEK from the live
    :class:`~cadrumo.adapters.persistence.storage.master_key.BucketSession`
    so the record wraps the same key material a real mint would have.

    Args:
        storage_root: The Cadrumo storage root owning the bucket keystore.
        bucket_id: Identifier of the logged-in bucket.

    Returns:
        The :class:`PersistedProfileSession` written to disk.
    """
    session = current_active_bucket_session()
    if session is None or session.bucket_id != bucket_id:
        message = f"no live session bound to {bucket_id}; log in before laying a record down"
        raise AssertionError(message)
    return lay_down_keychain_free_session(storage_root=storage_root, bucket_id=bucket_id, dek=session.dek)


def require_keychain_custody(*, storage_root: Path, bucket_id: str) -> None:
    """Fail with the custody reason when the login could not persist a session.

    The assertion subject of a few cases genuinely is the OS keychain: that
    a login custodies a session key at all, and that a later process
    resumes the record by unwrapping the DEK under it. Those cannot be
    proven on a host whose credential store is unreachable, and a bare
    ``FileNotFoundError`` or an unexpected authentication error deep in the
    body reads as a defect in the code under test. Calling this at the top
    of such a case pins the failure on the missing custody instead.

    Args:
        storage_root: The Cadrumo storage root owning the bucket keystore.
        bucket_id: Identifier of the bucket that has just logged in.
    """
    if profile_session_path(storage_root=storage_root, bucket_id=bucket_id).is_file():
        return
    pytest.fail(
        "login did not persist a session record, so this case cannot be exercised: "
        "this host has no usable OS keychain to custody the session key. "
        "The login itself succeeded and correctly degraded to a process-scoped "
        "session; only the custody half is unavailable here.",
    )
