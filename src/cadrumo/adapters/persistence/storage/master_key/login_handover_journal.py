"""Durable journal for the password-authenticated profile handover."""

from __future__ import annotations

import json
from pathlib import Path
from typing import NoReturn, cast

from pydantic import ValidationError

from .....application.user_profile.custody_ports import (
    ProfileCustodyLocalRecordStore,
    default_profile_custody_local_record_store,
)
from .....application.user_profile.login_handover import (
    HANDOVER_JOURNAL_MAX_BYTES,
    HandoverPhase,
    ProfileLoginHandoverJournal,
)
from .....application.user_profile.profile_pointer import ActiveProfilePointerTransactionError
from .....core.hashing import (
    reject_duplicate_json_members,
    reject_json_constant,
)
from .....core.storage_taxonomy import StorageCategory
from .....core.storage_taxonomy_locations import storage_location
_HANDOVER_JOURNAL_FILENAME = "profile-login-handover.v2.json"
_HANDOVER_PREDECESSOR: dict[HandoverPhase, HandoverPhase] = {
    HandoverPhase.POINTER_PUBLISHED: HandoverPhase.PREPARED,
    HandoverPhase.B_BOUND: HandoverPhase.POINTER_PUBLISHED,
    HandoverPhase.ACCELERATED: HandoverPhase.B_BOUND,
    HandoverPhase.ACTIVATED: HandoverPhase.ACCELERATED,
    HandoverPhase.A_RETIRED: HandoverPhase.ACTIVATED,
}


def handover_journal_path(storage_root: Path) -> Path:
    """Return the one root-local journal for an in-flight profile switch."""
    return (
        storage_root / storage_location(StorageCategory.OPERATION_JOURNAL).relative_path() / _HANDOVER_JOURNAL_FILENAME
    )


def _handover_journal_directory(storage_root: Path) -> Path:
    """Return the one anchored local-record parent for the handover witness."""
    return storage_root / storage_location(StorageCategory.OPERATION_JOURNAL).relative_path()


def _parse_handover_journal(payload: bytes) -> ProfileLoginHandoverJournal:
    """Decode only the journal's exact bounded canonical JSON form."""
    if len(payload) > HANDOVER_JOURNAL_MAX_BYTES:
        _refuse_handover_journal("journal exceeds its byte limit")
    try:
        document = json.loads(
            payload.decode("utf-8", errors="strict"),
            object_pairs_hook=reject_duplicate_json_members,
            parse_constant=reject_json_constant,
        )
        if not isinstance(document, dict):
            raise ValueError("handover journal must be a JSON object")
        canonical = bounded_canonical_json_bytes(
            cast(dict[str, object], document),
            maximum_bytes=HANDOVER_JOURNAL_MAX_BYTES,
            subject="profile login handover journal",
        )
        journal = ProfileLoginHandoverJournal.model_validate_json(canonical)
        if journal.canonical_json_bytes() != payload:
            raise ValueError("handover journal bytes are not canonical")
        return journal
    except (UnicodeDecodeError, json.JSONDecodeError, ValidationError, ValueError, TypeError):
        _refuse_handover_journal("journal is malformed or noncanonical")


def _handover_journal_store() -> ProfileCustodyLocalRecordStore:
    """Resolve the one application port for root-local custody records."""
    return default_profile_custody_local_record_store()


def _ensure_handover_journal_directory(*, storage_root: Path, store: ProfileCustodyLocalRecordStore) -> Path:
    """Anchor the journal parent before any local record operation."""
    directory = _handover_journal_directory(storage_root)
    try:
        store.ensure_directory(directory)
    except Exception:
        _refuse_handover_journal("journal directory cannot be anchored")
    return directory


def _refuse_handover_journal(reason: str) -> NoReturn:
    """Fail closed when a durable handover witness cannot be trusted."""
    raise ActiveProfilePointerTransactionError(
        translated_message="errors.integrity.integrity_storage_profile_custody_record",
        context={"owner": "profile-login-handover", "reason": reason},
    )


def save_handover_journal(*, storage_root: Path, journal: ProfileLoginHandoverJournal) -> None:
    """Durably publish one complete non-secret handover phase under root lock."""
    try:
        store = _handover_journal_store()
        _ensure_handover_journal_directory(storage_root=storage_root, store=store)
        if journal.phase is HandoverPhase.PREPARED:
            predecessor = None
        else:
            predecessor = journal.at_phase(_HANDOVER_PREDECESSOR[journal.phase]).canonical_json_bytes()
        path = handover_journal_path(storage_root)
        current = journal.canonical_json_bytes()
        store.compare_and_replace_same_or_predecessor(
            path,
            current=current,
            predecessor=predecessor,
            maximum_bytes=HANDOVER_JOURNAL_MAX_BYTES,
        )
        # The first receipt atomically publishes its target and retains only
        # its exact predecessor as a recoverable cleanup sidecar. Repeating
        # the same canonical receipt has no target write; it removes that
        # verified sidecar or fails closed so a future retry can converge.
        store.compare_and_replace_same_or_predecessor(
            path,
            current=current,
            predecessor=predecessor,
            maximum_bytes=HANDOVER_JOURNAL_MAX_BYTES,
        )
    except Exception:
        _refuse_handover_journal("journal compare-and-replace differs from the exact transition")


def load_handover_journal(*, storage_root: Path) -> ProfileLoginHandoverJournal | None:
    """Load the sole bounded in-flight witness, refusing malformed replacement."""
    try:
        store = _handover_journal_store()
        _ensure_handover_journal_directory(storage_root=storage_root, store=store)
        payload = store.read_optional(handover_journal_path(storage_root), maximum_bytes=HANDOVER_JOURNAL_MAX_BYTES)
    except Exception:
        _refuse_handover_journal("journal cannot be anchored and read")
    if payload is None:
        return None
    return _parse_handover_journal(payload)


def clear_handover_journal(*, storage_root: Path, journal: ProfileLoginHandoverJournal) -> None:
    """Remove the completed or fully rolled-back witness under root lock."""
    try:
        store = _handover_journal_store()
        _ensure_handover_journal_directory(storage_root=storage_root, store=store)
        current = journal.canonical_json_bytes()
        predecessor = (
            None
            if journal.phase is HandoverPhase.PREPARED
            else journal.at_phase(_HANDOVER_PREDECESSOR[journal.phase]).canonical_json_bytes()
        )
        path = handover_journal_path(storage_root)
        # A crash can leave the publication target plus only its exact
        # predecessor sidecar. Re-submit the same receipt first: this is a
        # target no-op that clears that verified sidecar before the terminal
        # compare-and-clear removes the journal itself.
        store.compare_and_replace_same_or_predecessor(
            path,
            current=current,
            predecessor=predecessor,
            maximum_bytes=HANDOVER_JOURNAL_MAX_BYTES,
        )
        store.compare_and_clear(
            path,
            expected=current,
            maximum_bytes=HANDOVER_JOURNAL_MAX_BYTES,
        )
    except Exception:
        _refuse_handover_journal("journal compare-and-clear differs from the exact transition")


__all__ = [
    "clear_handover_journal",
    "handover_journal_path",
    "load_handover_journal",
    "save_handover_journal",
]
