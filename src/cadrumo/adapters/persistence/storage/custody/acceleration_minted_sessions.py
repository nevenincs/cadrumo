"""The record of session ids this storage root minted, so a pruning pass deletes only its own keychain entries.

The keychain account ``<profile>:<session>`` names no storage root, and
copies of a root share profile ids. This record, written through the custody
local-record owner beside the receipt, is the only evidence that lets a pass
delete an entry. It holds session ids only, never a key, receipt or path.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final, cast
from uuid import UUID

from pydantic import BaseModel, Field, ValidationError

from .....core.logging import get_logger
from .....core.models import STRICT_FROZEN_CONFIG
from ..storage_path_definitions import PROFILE_SESSION_MINTED_FILENAME
from .acceleration_receipt_document import canonical_document_bytes, parse_canonical_document
from .errors import ProfileCustodyRecordError
from .filesystem import (
    compare_and_clear_profile_custody_local_record,
    compare_and_replace_profile_custody_local_record,
    read_optional_profile_custody_local_record,
)

_log = get_logger(__name__)

_PROFILE_SESSION_MINTED_SCHEMA_VERSION: Final[int] = 1
_PROFILE_SESSION_MINTED_MAX_SESSIONS: Final[int] = 256
"""Bound on the minted record; a pruning pass drops every id whose key it saw removed."""
_PROFILE_SESSION_MINTED_MAX_BYTES: Final[int] = 16 * 1024


class MintedProfileSessionsDocument(BaseModel):
    """The session ids this storage root minted whose keychain entries it has not yet seen removed.

    It holds session ids only: the profile is the keystore directory it lives
    in, and it names no key, receipt or path.
    """

    model_config = STRICT_FROZEN_CONFIG

    schema_version: int = Field(ge=1)
    session_ids: tuple[UUID, ...]


def minted_sessions_path(receipt_path: Path) -> Path:
    """Return the minted-session record beside an already validated receipt path."""
    return receipt_path.with_name(PROFILE_SESSION_MINTED_FILENAME)


def read_minted_sessions(path: Path) -> tuple[bytes | None, frozenset[UUID]]:
    """Read the exact record bytes and the session ids they name.

    Raises:
        ProfileCustodyRecordError: When the record is linked, oversized or unreadable.
        ValueError: When it is not one canonical current record.
    """
    payload = read_optional_profile_custody_local_record(path, maximum_bytes=_PROFILE_SESSION_MINTED_MAX_BYTES)
    if payload is None:
        return None, frozenset[UUID]()
    document = cast(MintedProfileSessionsDocument, parse_canonical_document(payload, MintedProfileSessionsDocument))
    if document.schema_version != _PROFILE_SESSION_MINTED_SCHEMA_VERSION:
        raise ValueError("profile-session minted record schema is not current")
    return payload, frozenset(document.session_ids)


def publish_minted_sessions(path: Path, *, expected: bytes | None, sessions: frozenset[UUID]) -> None:
    """Compare-and-swap the record through the custody local-record owner; an empty record is cleared."""
    if not sessions:
        if expected is not None:
            compare_and_clear_profile_custody_local_record(
                path, expected=expected, maximum_bytes=_PROFILE_SESSION_MINTED_MAX_BYTES
            )
        return
    compare_and_replace_profile_custody_local_record(
        path,
        expected=expected,
        replacement=canonical_document_bytes(
            MintedProfileSessionsDocument(
                schema_version=_PROFILE_SESSION_MINTED_SCHEMA_VERSION,
                session_ids=tuple(sorted(sessions, key=str)),
            )
        ),
        maximum_bytes=_PROFILE_SESSION_MINTED_MAX_BYTES,
    )


def record_minted_session(receipt_path: Path, session_id: UUID) -> None:
    """Name ``session_id`` as minted by this root before its key reaches the keychain.

    A record that cannot be read, or that is full, leaves the new session
    unrecorded: its entry is then never pruned, which only keeps a key, and
    the sign-in itself does not depend on the record.
    """
    path = minted_sessions_path(receipt_path)
    try:
        payload, sessions = read_minted_sessions(path)
        if len(sessions) >= _PROFILE_SESSION_MINTED_MAX_SESSIONS:
            _log.debug("profile-session minted record is full; the new session is not recorded")
            return
        publish_minted_sessions(path, expected=payload, sessions=sessions | {session_id})
    except (ProfileCustodyRecordError, ValueError, ValidationError) as exc:
        _log.debug("profile-session minted record not written error_type=%s", type(exc).__name__)


__all__ = [
    "MintedProfileSessionsDocument",
    "minted_sessions_path",
    "publish_minted_sessions",
    "read_minted_sessions",
    "record_minted_session",
]
