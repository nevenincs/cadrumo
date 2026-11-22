"""Deleting the profile-session keychain entries this storage root minted and no longer names."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from pydantic import ValidationError

from .....core.logging import get_logger
from .....core.profile_session import KeychainUnavailability
from ..errors import StorageError
from .acceleration_keychain import delete_acceleration_secret, keychain_unavailability
from .acceleration_minted_sessions import minted_sessions_path, publish_minted_sessions, read_minted_sessions
from .acceleration_receipt import profile_session_lock_path, profile_session_path, retained_profile_sessions
from .errors import ProfileCustodyRecordError
from .filesystem import profile_custody_local_lock, profile_custody_root_lock

_log = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class ProfileSessionPruneOutcome:
    """What one pruning pass removed, what it left for the next pass, and why it stopped early if it did.

    It names UUID pairs only, never a secret. ``retained`` holds the minted,
    unretained entries a failed deletion left in place.
    """

    removed: tuple[tuple[UUID, UUID], ...]
    retained: tuple[tuple[UUID, UUID], ...]
    unavailability: KeychainUnavailability | None


def _owned_profiles(storage_root: Path) -> tuple[UUID, ...]:
    from ..bucket.keystore_paths import keystore_root

    try:
        entries = tuple(keystore_root(storage_root).iterdir())
    except FileNotFoundError:
        return ()
    owned: list[UUID] = []
    for entry in entries:
        try:
            profile_id = UUID(entry.name)
        except ValueError:
            continue
        if str(profile_id) == entry.name and not entry.is_symlink() and entry.is_dir():
            owned.append(profile_id)
    return tuple(sorted(owned, key=str))


def profile_session_prune_has_work(storage_root: Path) -> bool:
    """Whether any profile this root owns keeps a minted-session record, read without the custody root lock.

    Only a recorded session can ever be pruned, so a root without such a
    record is left untouched. ``True`` sends the caller to the locked pass,
    which reads every record again under the lock; a session minted after
    this read is recorded and retained under that lock, never pruned. A
    record whose presence cannot be observed also answers ``True``.
    """
    try:
        for profile_id in _owned_profiles(storage_root):
            receipt_path = profile_session_path(storage_root=storage_root, profile_id=profile_id)
            if os.path.lexists(minted_sessions_path(receipt_path)):
                return True
    except (OSError, ValueError, StorageError):
        return True
    return False


def prune_profile_session_entries(storage_root: Path) -> ProfileSessionPruneOutcome:
    """Delete the keychain entries this root minted that no receipt or journal of it names any more.

    The keychain account ``<profile>:<session>`` names no storage root, and
    copies of a root share profile ids, so only a session this root recorded
    when it minted it may be deleted; an entry it never recorded is left
    alone. An id whose key is confirmed absent leaves the record, which keeps
    it bounded. A profile whose receipt, journal or record cannot be read is
    skipped. The pass holds the custody root lock, which every mint holds
    from its journal to its receipt. A keychain that cannot answer stops the
    pass with its typed reason; nothing is raised for it.
    """
    removed: list[tuple[UUID, UUID]] = []
    with profile_custody_root_lock(storage_root):
        for profile_id in _owned_profiles(storage_root):
            receipt_path = profile_session_path(storage_root=storage_root, profile_id=profile_id)
            minted_path = minted_sessions_path(receipt_path)
            try:
                with profile_custody_local_lock(profile_session_lock_path(receipt_path)):
                    payload, minted = read_minted_sessions(minted_path)
                    if not minted:
                        continue
                    retained = retained_profile_sessions(profile_id=profile_id, receipt_path=receipt_path)
                    candidates = sorted(minted - retained, key=str)
                    gone: set[UUID] = set()
                    failure: BaseException | None = None
                    for session_id in candidates:
                        try:
                            delete_acceleration_secret(
                                profile_id=profile_id, session_id=session_id, suppress_unavailable=False
                            )
                        except Exception as exc:
                            failure = exc
                            break
                        gone.add(session_id)
                        removed.append((profile_id, session_id))
                    if gone:
                        publish_minted_sessions(minted_path, expected=payload, sessions=minted - gone)
                    if failure is not None:
                        return ProfileSessionPruneOutcome(
                            removed=tuple(removed),
                            retained=tuple((profile_id, session) for session in candidates if session not in gone),
                            unavailability=keychain_unavailability(failure),
                        )
            except (OSError, ValueError, ValidationError, StorageError, ProfileCustodyRecordError) as exc:
                _log.debug("profile-session prune skipped a profile error_type=%s", type(exc).__name__)
                continue
    return ProfileSessionPruneOutcome(removed=tuple(removed), retained=(), unavailability=None)


__all__ = ["ProfileSessionPruneOutcome", "profile_session_prune_has_work", "prune_profile_session_entries"]
