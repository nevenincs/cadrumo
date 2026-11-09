"""Profile acceleration receipt: cross-process custody of a wrapped bucket DEK.

This is NOT a session. It has no counterparty and no protocol: it is a
locally held wrap of an already-unlocked DEK, carrying a deadline, that lets a
later process skip the passphrase. The AEAT authority session -- an encrypted
row inside the bucket, revocable only with the key -- is the artefact that
owns the word "session" in this codebase, and conflating the two has produced
a wrong architectural premise more than once.
The "logged in" state minted by ``aeat config login`` survives across CLI
processes as two split-knowledge artefacts, either of which is useless
alone:

- an ephemeral 32-byte session key persisted ONLY in the OS keychain under the
  service ``cadrumo:profile-session:v2`` with the immutable profile UUID plus
  minted session UUID as account, and
- an on-disk ``session.v2.json`` record in the separated profile keystore
  directory carrying the AES-256-GCM wrap of the bucket DEK under that
  session key, with EVERY metadata field (schema version, immutable profile
  UUID, random session UUID,
  custody generation, DEK epoch, the originating-login commitment, the
  sign-in generation, ``issued_at``, the sliding idle deadline,
  and immutable absolute deadline) bound as AEAD associated data.

Every reader decodes a minimal header first and dispatches on its schema
version. Only a current record reaches the strict model; any other version is
a revocable cache from another build, so it is deleted by its header identity
and refused as ``SCHEMA_VERSION_MISMATCH``. A strict parse of an older record
would fail on fields it never had, and that failure must not strand the
receipt or abort a mint that replaces it.

A mint stamps the sign-in generation its caller captured, and writes nothing
unless that generation is still the durable current one. It never creates the
generation record: the runtime establishes it when it publishes the session
the receipt belongs to. The runtime's supplied-key reader verifies the
expected OS login and the current generation, under the custody root lock
that every generation write also holds, before it hands out the DEK; a
receipt it refuses is deleted there through the typed deletion path, a login
mismatch only once the supplied proof has unwrapped it. The frontend's
proof borrow reads only the keychain proof and the receipt locator, so no DEK
reaches a frontend and no frontend deletes either half.

The record and secret are both required; resume fails closed on invalid bindings.
"""

from __future__ import annotations

import secrets
from collections.abc import Callable
from datetime import datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Final, cast
from uuid import UUID, uuid4

from pydantic import BaseModel, ValidationError

from .....core.base64_codec import b64_decode, b64_encode
from .....core.identity.profile import canonical_profile_bucket_id
from .....core.logging import get_logger
from .....core.models import STRICT_FROZEN_CONFIG
from .....core.profile_session import KeychainUnavailability, ProfileSessionRefusalReason, ReceiptBindingRefusal
from .....core.time.utc import validate_utc_aware
from ..crypto.aes_gcm import KEY_SIZE
from ..errors import (
    DecryptionError,
    KeyringUnavailableError,
    StorageError,
    StorageValidationError,
)
from ..storage_path_definitions import PROFILE_SESSION_FILENAME, PROFILE_SESSION_RETIREMENT_FILENAME
from . import acceleration_receipt_crypto
from .acceleration_keychain import (
    delete_acceleration_secret,
    probe_profile_session_keychain,
    read_acceleration_secret,
    store_acceleration_secret,
)
from .acceleration_receipt_crypto import encryption_error
from .acceleration_receipt_document import (
    AccelerationReceiptDocument,
    DecodedReceipt,
    PendingReceiptRetirementDocument,
    canonical_document_bytes,
    document_from_record,
    parse_canonical_document,
    parse_receipt_header,
    record_from_document,
)
from .errors import ProfileCustodyRecordError
from .filesystem import (
    compare_and_clear_profile_custody_local_record,
    compare_and_replace_profile_custody_local_record,
    profile_custody_local_lock,
    profile_custody_root_lock,
    read_optional_profile_custody_local_record,
)
from .filesystem_primitives import ensure_profile_custody_local_directory
from .sign_in_generation import (
    SignInGeneration,
    SignInGenerationCustody,
    SignInGenerationObservation,
    SignInGenerationState,
)
from .zeroise import zeroise

_log = get_logger(__name__)

PROFILE_SESSION_RECORD_MAX_BYTES: Final[int] = 8 * 1024
"""Strict ceiling for one canonical ``session.v2.json`` receipt."""

_PROFILE_SESSION_RETIREMENT_MAX_BYTES: Final[int] = 24 * 1024
_PROFILE_SESSION_RETIREMENT_SCHEMA_VERSION: Final[int] = 1


class ReceiptDeletion(StrEnum):
    """What a refused receipt's deletion achieved; never silently assumed."""

    NOT_REQUIRED = "not_required"
    """No deletion was attempted: a reader left the receipt alone, or revocation found none.

    Only the second case says anything about the keychain.
    """

    DELETED = "deleted"
    """Both the keychain key and the on-disk receipt are gone."""

    KEYCHAIN_ENTRY_RETAINED = "keychain_entry_retained"
    """The on-disk receipt is gone; its keychain key could not be confirmed removed.

    The orphaned key unwraps nothing once no record names its session.
    """

    RECEIPT_RETAINED = "receipt_retained"
    """The on-disk receipt survived its compare-and-clear."""

    @property
    def receipt_removed(self) -> bool:
        """Whether the on-disk receipt is gone (or was never there to remove)."""
        return self is not ReceiptDeletion.RECEIPT_RETAINED

    @property
    def keychain_removed(self) -> bool:
        """Whether a revocation left no keychain key that any record could name.

        Read this only on :func:`revoke_profile_sign_in`'s outcome. There
        ``NOT_REQUIRED`` means no receipt remained and any pending retirement was
        recovered, so no key has a locator left; on a reader's refusal it would
        claim a removal nobody attempted.
        """
        return self in {ReceiptDeletion.DELETED, ReceiptDeletion.NOT_REQUIRED}


class ProfileSessionResumeOutcome(BaseModel):
    """Typed outcome of a fail-closed persisted-session resume evaluation.

    Never carries key material: the resumed DEK travels beside this record
    as a separate return value so no pydantic dump can surface it.
    ``deletion`` reports how far a refusing reader's typed deletion got;
    readers that do not delete leave it ``NOT_REQUIRED``. ``binding`` names
    the sign-in binding a refused receipt failed; its ``refusal`` is then
    ``ABSENT``, because the receipt no longer signs this login in.
    ``keychain`` names why the reading process cannot use the keychain, when
    that is so: beside ``KEYRING_UNAVAILABLE``, and beside ``ABSENT`` when no
    sign-in could have been kept or presented from this process at all.
    """

    model_config = STRICT_FROZEN_CONFIG

    resumed: bool
    refusal: ProfileSessionRefusalReason | None = None
    record: acceleration_receipt_crypto.PersistedProfileSession | None = None
    deletion: ReceiptDeletion = ReceiptDeletion.NOT_REQUIRED
    binding: ReceiptBindingRefusal | None = None
    keychain: KeychainUnavailability | None = None


def profile_session_path(*, storage_root: Path, profile_id: UUID) -> Path:
    """Return the locator consumed exclusively by custody local-record operations."""
    from ..bucket.keystore_paths import keystore_sidecar_path

    return keystore_sidecar_path(
        storage_root=storage_root,
        bucket_id=canonical_profile_bucket_id(profile_id),
        filename=PROFILE_SESSION_FILENAME,
    )


def profile_session_retirement_path(*, storage_root: Path, profile_id: UUID) -> Path:
    """Return the bounded local receipt for one interrupted session-key swap."""
    return _retirement_path_beside(profile_session_path(storage_root=storage_root, profile_id=profile_id))


def _retirement_path_beside(receipt_path: Path) -> Path:
    """Return the retirement journal beside an already validated receipt path."""
    return receipt_path.with_name(PROFILE_SESSION_RETIREMENT_FILENAME)


def profile_session_lock_path(receipt_path: Path) -> Path:
    """Return the separate anchored lock leaf; never lock the receipt itself."""
    return receipt_path.with_name(f".{receipt_path.name}.lock")


def ensure_profile_session_directory(path: Path) -> None:
    """Provision only the two custody-owned keystore children, anchored.

    The configured storage root itself is an existing product boundary.  The
    session sidecar owns the ``keystore`` child and then its UUID child; using
    the custody primitive for both avoids a recursive convenience mkdir walk.
    """
    ensure_profile_custody_local_directory(path.parent.parent)
    ensure_profile_custody_local_directory(path.parent)


def receipt_bytes(record: acceleration_receipt_crypto.PersistedProfileSession) -> bytes:
    """Return the canonical bytes of a persisted profile session receipt."""
    return canonical_document_bytes(document_from_record(record))


def decode_receipt(payload: bytes) -> DecodedReceipt:
    """Dispatch on the schema version before any strict parse.

    Raises:
        ValueError: When even the header is malformed or non-canonical.
        ValidationError: When a current-schema record fails strict validation.
    """
    header = parse_receipt_header(payload)
    if header.schema_version != acceleration_receipt_crypto.PROFILE_SESSION_SCHEMA_VERSION:
        return header
    document = cast(AccelerationReceiptDocument, parse_canonical_document(payload, AccelerationReceiptDocument))
    return record_from_document(document)


def current_record(decoded: DecodedReceipt) -> acceleration_receipt_crypto.PersistedProfileSession | None:
    """Return the decoded receipt when it is a current-schema record, else None."""
    return decoded if isinstance(decoded, acceleration_receipt_crypto.PersistedProfileSession) else None


def _read_receipt(path: Path) -> tuple[bytes, DecodedReceipt] | None:
    """Read and decode one receipt through the canonical anchored authority."""
    payload = read_optional_profile_custody_local_record(path, maximum_bytes=PROFILE_SESSION_RECORD_MAX_BYTES)
    if payload is None:
        return None
    return payload, decode_receipt(payload)


def inspect_profile_session(
    *, storage_root: Path, profile_id: UUID
) -> acceleration_receipt_crypto.PersistedProfileSession | None:
    """Read current receipt metadata without keychain access, mutation or DEK unwrapping.

    Missing parents and superseded schemas have no current receipt. Malformed,
    linked or unreadable records raise so callers preserve an unknown result.
    This observation cannot authenticate the metadata without the separate proof.
    """
    path = profile_session_path(storage_root=storage_root, profile_id=profile_id)
    for parent in (path.parent.parent, path.parent):
        try:
            parent.lstat()
        except FileNotFoundError:
            return None
    captured = _read_receipt(path)
    return None if captured is None else current_record(captured[1])


def clear_captured_receipt(path: Path, *, payload: bytes, maximum_bytes: int) -> bool:
    """Clear only the exact anchored bytes already evaluated by this caller."""
    try:
        compare_and_clear_profile_custody_local_record(
            path,
            expected=payload,
            maximum_bytes=maximum_bytes,
        )
    except ProfileCustodyRecordError:
        return False
    return True


def write_acceleration_receipt(
    *,
    storage_root: Path,
    profile_id: UUID,
    record: acceleration_receipt_crypto.PersistedProfileSession,
    predecessor: bytes | None,
) -> bytes:
    """CAS-publish a canonical receipt through the custody local-record owner."""
    return _publish_receipt(
        profile_session_path(storage_root=storage_root, profile_id=profile_id),
        profile_id=profile_id,
        record=record,
        predecessor=predecessor,
    )


def _publish_receipt(
    path: Path,
    *,
    profile_id: UUID,
    record: acceleration_receipt_crypto.PersistedProfileSession,
    predecessor: bytes | None,
) -> bytes:
    """CAS-publish ``record`` at ``path``, the profile's already validated receipt path."""
    if record.profile_id != profile_id:
        raise StorageValidationError(
            f"session record profile {record.profile_id!s} does not match target profile {profile_id!s}",
        )
    payload = receipt_bytes(record)
    ensure_profile_session_directory(path)
    compare_and_replace_profile_custody_local_record(
        path,
        expected=predecessor,
        replacement=payload,
        maximum_bytes=PROFILE_SESSION_RECORD_MAX_BYTES,
    )
    return payload


def pending_retirement_bytes(*, profile_id: UUID, predecessor: bytes | None, successor: bytes) -> bytes:
    """Encode the bounded exact-byte retirement decision before publication."""
    return canonical_document_bytes(
        PendingReceiptRetirementDocument(
            schema_version=_PROFILE_SESSION_RETIREMENT_SCHEMA_VERSION,
            profile_id=profile_id,
            predecessor_b64=None if predecessor is None else b64_encode(predecessor),
            successor_b64=b64_encode(successor),
        ),
    )


def _read_pending_retirement(path: Path, *, profile_id: UUID) -> tuple[bytes, bytes | None, bytes] | None:
    """Load a current pending-swap receipt, rejecting aliases before action."""
    payload = read_optional_profile_custody_local_record(path, maximum_bytes=_PROFILE_SESSION_RETIREMENT_MAX_BYTES)
    if payload is None:
        return None
    document = cast(
        PendingReceiptRetirementDocument,
        parse_canonical_document(payload, PendingReceiptRetirementDocument),
    )
    if document.schema_version != _PROFILE_SESSION_RETIREMENT_SCHEMA_VERSION:
        raise StorageValidationError("profile-session retirement receipt schema is not current")
    if document.profile_id != profile_id:
        raise StorageValidationError("profile-session retirement receipt profile differs")
    predecessor = None if document.predecessor_b64 is None else b64_decode(document.predecessor_b64)
    successor = b64_decode(document.successor_b64)
    if predecessor is not None:
        prior_record = decode_receipt(predecessor)
        if prior_record.profile_id != profile_id:
            raise StorageValidationError("profile-session retirement predecessor profile differs")
    successor_record = decode_receipt(successor)
    if successor_record.profile_id != profile_id:
        raise StorageValidationError("profile-session retirement successor profile differs")
    return payload, predecessor, successor


def recover_pending_retirement(*, storage_root: Path, profile_id: UUID) -> bool:
    """Finish exactly one interrupted ordered session-key swap.

    Returns ``True`` only when there was no journal or the exact journal was
    consumed.  It never clears a receipt whose bytes differ from the recorded
    predecessor/successor pair.
    """
    receipt_path = profile_session_path(storage_root=storage_root, profile_id=profile_id)
    journal_path = profile_session_retirement_path(storage_root=storage_root, profile_id=profile_id)
    pending = _read_pending_retirement(journal_path, profile_id=profile_id)
    if pending is None:
        return True
    journal_payload, predecessor, successor = pending
    current = read_optional_profile_custody_local_record(
        receipt_path,
        maximum_bytes=PROFILE_SESSION_RECORD_MAX_BYTES,
    )
    if current == successor:
        if predecessor is not None:
            prior = decode_receipt(predecessor)
            delete_acceleration_secret(
                profile_id=prior.profile_id,
                session_id=prior.session_id,
                suppress_unavailable=False,
            )
        if not clear_captured_receipt(
            journal_path,
            payload=journal_payload,
            maximum_bytes=_PROFILE_SESSION_RETIREMENT_MAX_BYTES,
        ):
            raise StorageValidationError("profile-session retirement receipt changed during recovery")
        return True
    if current == predecessor:
        successor_record = decode_receipt(successor)
        delete_acceleration_secret(
            profile_id=successor_record.profile_id,
            session_id=successor_record.session_id,
            suppress_unavailable=False,
        )
        if not clear_captured_receipt(
            journal_path,
            payload=journal_payload,
            maximum_bytes=_PROFILE_SESSION_RETIREMENT_MAX_BYTES,
        ):
            raise StorageValidationError("profile-session retirement receipt changed during rollback")
        return True
    raise StorageValidationError("profile-session retirement receipt conflicts with the current receipt")


def _clear_retirement_journal(journal_path: Path, *, payload: bytes) -> bool:
    """Clear one exact retirement journal whose keychain half cannot be retired.

    The journal carries the wrapped DEK of every receipt it names, so it is an
    on-disk half of the session exactly like the receipt. A keychain entry it
    would have retired holds only a random session key that unwraps nothing
    once no on-disk record names its session id, and no later receipt can name
    it because every mint draws a fresh one. Clearing the journal is therefore
    the fail-closed direction: an entry that may exist is left inert, never
    reachable, and never reused.
    """
    cleared = clear_captured_receipt(
        journal_path,
        payload=payload,
        maximum_bytes=_PROFILE_SESSION_RETIREMENT_MAX_BYTES,
    )
    if cleared:
        _log.debug("profile-session retirement journal cleared with its keychain half unreachable")
    return cleared


class AccelerationReceiptRevocationError(StorageError):
    """Raised when a receipt survived the revocation that was asked to remove it.

    Deliberately NOT a subclass of the custody record error this module already
    catches and logs, because the point is that it must not be swallowed by the
    same handler.

    A boolean return would have repeated the defect one level up: the caller
    that ignored the value is precisely the caller that reports the profile
    closed. The revocation entry point is the single authority for "this
    profile is no longer logged in", so when it cannot prove the receipt is
    gone it must not return as though it had.
    """


def delete_profile_session(*, storage_root: Path, profile_id: UUID) -> None:
    """Complete journalled custody cleanup only after both receipt halves are absent.

    Global human sign-out uses its separate generation-first typed outcome.
    Custody deletion must preserve retry evidence when physical cleanup fails.
    """
    with profile_custody_root_lock(storage_root):
        _delete_profile_session(storage_root=storage_root, profile_id=profile_id)


def revoke_profile_sign_in(sign_in: SignInGenerationCustody) -> ReceiptDeletion:
    """Durably fence all issued receipts before attempting their bounded deletion.

    The runtime holds its admission guard across this call and retirement of
    live human sessions. A failed generation write raises before any deletion;
    failure to remove either receipt half is returned explicitly.
    """
    with profile_custody_root_lock(sign_in.root):
        sign_in.advance()
        path = profile_session_path(storage_root=sign_in.root, profile_id=sign_in.binding.profile_id)
        try:
            ensure_profile_session_directory(path)
            with profile_custody_local_lock(profile_session_lock_path(path)):
                keychain_retained = False
                try:
                    recover_pending_retirement(storage_root=sign_in.root, profile_id=sign_in.binding.profile_id)
                except (KeyringUnavailableError, ProfileCustodyRecordError, StorageValidationError):
                    keychain_retained = True
                _clear_unrecovered_retirement(storage_root=sign_in.root, profile_id=sign_in.binding.profile_id)
                captured = _read_receipt(path)
                if captured is None:
                    return (
                        ReceiptDeletion.KEYCHAIN_ENTRY_RETAINED if keychain_retained else ReceiptDeletion.NOT_REQUIRED
                    )
                payload, record = captured
                if record.profile_id != sign_in.binding.profile_id:
                    return ReceiptDeletion.RECEIPT_RETAINED
                deletion = delete_refused_receipt(path=path, payload=payload, decoded=record)
                if keychain_retained and deletion is ReceiptDeletion.DELETED:
                    return ReceiptDeletion.KEYCHAIN_ENTRY_RETAINED
                return deletion
        except (OSError, ValueError, StorageError, ProfileCustodyRecordError):
            return ReceiptDeletion.RECEIPT_RETAINED


def _delete_profile_session(*, storage_root: Path, profile_id: UUID) -> None:
    """Retain the exact key locator until confirmed keychain and receipt removal."""
    path = profile_session_path(storage_root=storage_root, profile_id=profile_id)
    ensure_profile_session_directory(path)
    with profile_custody_local_lock(profile_session_lock_path(path)):
        # A failed recovery leaves its journal available for the next custody
        # attempt. Discarding it would lose the only locator of an orphan key.
        recover_pending_retirement(storage_root=storage_root, profile_id=profile_id)
        observed = _read_receipt(path)
        if observed is None:
            return
        payload, record = observed
        if record.profile_id != profile_id:
            raise AccelerationReceiptRevocationError(
                translated_message="errors.fail.fail_acceleration_receipt_revocation",
                context={"profile_id": canonical_profile_bucket_id(profile_id)},
            )
        delete_acceleration_secret(
            profile_id=record.profile_id,
            session_id=record.session_id,
            suppress_unavailable=False,
        )
        if not clear_captured_receipt(path, payload=payload, maximum_bytes=PROFILE_SESSION_RECORD_MAX_BYTES):
            raise AccelerationReceiptRevocationError(
                translated_message="errors.fail.fail_acceleration_receipt_revocation",
                context={"profile_id": canonical_profile_bucket_id(profile_id)},
            )


def _clear_unrecovered_retirement(*, storage_root: Path, profile_id: UUID) -> None:
    """Remove a retirement journal that recovery could not consume.

    Revocation is the strong close: it removes every on-disk half whether or
    not the keychain answers, as it already does for the receipt itself.

    Raises:
        AccelerationReceiptRevocationError: The journal survived its clear.
    """
    journal_path = profile_session_retirement_path(storage_root=storage_root, profile_id=profile_id)
    payload = read_optional_profile_custody_local_record(
        journal_path,
        maximum_bytes=_PROFILE_SESSION_RETIREMENT_MAX_BYTES,
    )
    if payload is None:
        return
    if not _clear_retirement_journal(journal_path, payload=payload):
        raise AccelerationReceiptRevocationError(
            translated_message="errors.fail.fail_acceleration_receipt_revocation",
            context={"profile_id": canonical_profile_bucket_id(profile_id)},
        )


def mint_profile_session(
    *,
    storage_root: Path,
    profile_id: UUID,
    custody_generation: int,
    dek_epoch: str,
    dek: bytes,
    now: datetime,
    idle_minutes: int,
    absolute_minutes: int,
    login_id: str,
    sign_in: SignInGenerationCustody,
    generation: SignInGeneration,
    retain_sealing_key: Callable[[bytearray], None] | None = None,
) -> acceleration_receipt_crypto.PersistedProfileSession:
    """Mint a profile receipt under the custody-wide session lifecycle lock.

    Validate all deterministic receipt inputs before opening the custody root.
    A rejected bootstrap call must not provision a durable lock leaf merely
    to report malformed identity, metadata, key material, or time windows.

    The receipt binds ``login_id``, the originating OS login, and exactly
    ``generation``: the value the caller captured from ``sign_in`` when it
    published the session, never a fresh read. Under the custody root lock,
    which every generation write also holds, the mint refuses before any
    keychain or receipt write unless ``generation`` is still current. A
    sign-out or lock-down that advanced it in between therefore leaves no
    receipt, and a missing record is never created here.

    Raises:
        StorageValidationError: When an input is malformed or ``sign_in`` is
            bound to another storage root, profile or custody generation.
        AutomationCustodyError: ``INVALID`` when ``sign_in`` is not the
            committed custody; ``CONFLICT`` when ``generation`` is no longer
            current.
        ProfileCustodyRecordError: When the custody root lock cannot be held.
    """
    if idle_minutes <= 0:
        raise StorageValidationError("idle_minutes must be a strict positive integer")
    if absolute_minutes <= 0:
        raise StorageValidationError("absolute_minutes must be a strict positive integer")
    if len(dek) != KEY_SIZE:
        raise encryption_error(f"dek must be exactly {KEY_SIZE} bytes")
    now = acceleration_receipt_crypto.validate_profile_session_metadata(
        profile_id=profile_id,
        custody_generation=custody_generation,
        dek_epoch=dek_epoch,
        issued_at=now,
    )
    if not login_id or len(login_id) > acceleration_receipt_crypto.PROFILE_SESSION_LOGIN_ID_MAX_LENGTH:
        raise StorageValidationError("login_id must be a non-empty OS login locator of bounded length")
    if (
        sign_in.root != storage_root
        or sign_in.binding.profile_id != profile_id
        or sign_in.binding.custody_generation != custody_generation
    ):
        raise StorageValidationError("sign-in generation custody does not belong to this receipt")
    with profile_custody_root_lock(storage_root):
        sign_in.require_current(generation)
        return _mint_profile_session(
            storage_root=storage_root,
            profile_id=profile_id,
            custody_generation=custody_generation,
            dek_epoch=dek_epoch,
            dek=dek,
            now=now,
            idle_minutes=idle_minutes,
            absolute_minutes=absolute_minutes,
            login_id=login_id,
            sign_in=generation,
            retain_sealing_key=retain_sealing_key,
        )


def _mint_profile_session(
    *,
    storage_root: Path,
    profile_id: UUID,
    custody_generation: int,
    dek_epoch: str,
    dek: bytes,
    now: datetime,
    idle_minutes: int,
    absolute_minutes: int,
    login_id: str,
    sign_in: SignInGeneration,
    retain_sealing_key: Callable[[bytearray], None] | None = None,
) -> acceleration_receipt_crypto.PersistedProfileSession:
    """Mint the persisted session for a freshly-authenticated login.

    Generates the ephemeral session key, wraps ``dek`` under it with the
    deadline metadata AAD-bound, stores the key in the OS keychain
    (round-trip verified), and atomically writes the on-disk record. The
    session-key buffer is zeroised on every exit path. On a host with no
    usable keychain the mint REFUSES before writing anything, so no
    artefact can exist whose key has no secure home.

    Args:
        storage_root: The Cadrumo storage root owning the profile keystore.
        profile_id: Immutable authenticated capsule UUID.
        custody_generation: Current envelope generation.
        dek_epoch: Current envelope DEK epoch.
        dek: The unwrapped 32-byte bucket DEK to session-wrap.
        now: UTC login instant (becomes ``issued_at``).
        idle_minutes: Sliding idle window; strict positive.
        absolute_minutes: Immutable absolute cap; strict positive.
        login_id: Originating OS login, bound only as a salted commitment.
        sign_in: The durable sign-in generation the receipt is stamped with.
        retain_sealing_key: Trusted worker callback borrowing the key after verified publication.

    Returns:
        The persisted :class:`~.acceleration_receipt_crypto.PersistedProfileSession`.

    Raises:
        StorageValidationError: On non-positive windows.
        EncryptionError: On wrap failure.
        KeyringUnavailableError: When the OS keychain cannot custody the
            session key.
    """
    absolute_deadline = now + timedelta(minutes=absolute_minutes)
    idle_deadline = min(now + timedelta(minutes=idle_minutes), absolute_deadline)

    receipt_path = profile_session_path(storage_root=storage_root, profile_id=profile_id)
    retirement_path = profile_session_retirement_path(storage_root=storage_root, profile_id=profile_id)
    ensure_profile_session_directory(receipt_path)
    with profile_custody_local_lock(profile_session_lock_path(receipt_path)):
        # A prior crash or retirement failure has one bounded exact-byte
        # decision to finish before another random account can be minted.
        recover_pending_retirement(storage_root=storage_root, profile_id=profile_id)
        prior = _read_receipt(receipt_path)
        predecessor = None if prior is None else prior[0]

        session_key_buffer = bytearray(secrets.token_bytes(acceleration_receipt_crypto.PROFILE_SESSION_KEY_BYTES))
        session_id = uuid4()
        try:
            record = acceleration_receipt_crypto.wrap_profile_session_dek(
                session_key=bytes(session_key_buffer),
                dek=dek,
                profile_id=profile_id,
                session_id=session_id,
                custody_generation=custody_generation,
                dek_epoch=dek_epoch,
                login_id=login_id,
                sign_in=sign_in,
                issued_at=now,
                idle_deadline=idle_deadline,
                absolute_deadline=absolute_deadline,
            )
            successor = receipt_bytes(record)
            journal = pending_retirement_bytes(
                profile_id=profile_id,
                predecessor=predecessor,
                successor=successor,
            )
            # Publish the deterministic cleanup instruction first.  If this
            # process dies before a later phase, recovery sees whether the
            # exact current receipt is predecessor or successor and retires
            # only the corresponding staged/displaced UUID-pair account.
            compare_and_replace_profile_custody_local_record(
                retirement_path,
                expected=None,
                replacement=journal,
                maximum_bytes=_PROFILE_SESSION_RETIREMENT_MAX_BYTES,
            )
            try:
                store_acceleration_secret(
                    profile_id=profile_id,
                    session_id=session_id,
                    session_key=bytes(session_key_buffer),
                )
                published = write_acceleration_receipt(
                    storage_root=storage_root,
                    profile_id=profile_id,
                    record=record,
                    predecessor=predecessor,
                )
                verified = read_optional_profile_custody_local_record(
                    receipt_path,
                    maximum_bytes=PROFILE_SESSION_RECORD_MAX_BYTES,
                )
                if verified != published:
                    raise StorageValidationError("profile-session receipt publication could not be verified")
            except BaseException:
                # Do not hand-delete an account whose publication state is
                # unknown.  The exact pending receipt is the recovery owner;
                # it will clean a pre-publication successor or finish
                # retirement after publication without touching a substitute.
                try:
                    recover_pending_retirement(storage_root=storage_root, profile_id=profile_id)
                except (KeyringUnavailableError, ProfileCustodyRecordError, StorageValidationError) as exc:
                    _log.debug("profile-session mint cleanup deferred error_type=%s", type(exc).__name__)
                raise
            try:
                recover_pending_retirement(storage_root=storage_root, profile_id=profile_id)
            except KeyringUnavailableError as exc:
                # The new receipt/key pair is already verified and remains a
                # valid acceleration.  Retiring its displaced predecessor is
                # explicitly retryable through the journal, never an
                # authentication failure or a global account sweep.
                _log.debug("profile-session predecessor retirement deferred error_type=%s", type(exc).__name__)
            if retain_sealing_key is not None:
                retain_sealing_key(session_key_buffer)
            return record
        finally:
            zeroise(session_key_buffer)


def _refresh_record_matches(
    record: acceleration_receipt_crypto.PersistedProfileSession | None,
    *,
    sign_in: SignInGenerationCustody,
    login_id: str,
    now: datetime,
) -> bool:
    binding = sign_in.binding
    return (
        record is not None
        and record.profile_id == binding.profile_id
        and record.custody_generation == binding.custody_generation
        and record.dek_epoch == b64_encode(binding.dek_epoch.bytes)
        and now >= record.issued_at
        and receipt_binding_refusal(record=record, login_id=login_id, generation=sign_in.observe()) is None
    )


def refresh_profile_session_with_key(
    *,
    sign_in: SignInGenerationCustody,
    receipt_key: bytearray,
    login_id: str,
    now: datetime,
    deadline: datetime,
) -> bool:
    """Reseal existing acceleration for an admitted live person, never mint it.

    The caller holds live human custody. Only its retained sealing key is used;
    generation and exact receipt bytes fence sign-out and receipt replacement.
    No keychain operation is performed here, including retirement recovery.
    """
    now, deadline = validate_utc_aware(now), validate_utc_aware(deadline)
    if deadline <= now:
        return False
    binding = sign_in.binding
    # The one validated receipt path names the lock, the retirement journal and the write.
    path = profile_session_path(storage_root=sign_in.root, profile_id=binding.profile_id)
    with profile_custody_root_lock(sign_in.root), profile_custody_local_lock(profile_session_lock_path(path)):
        if (
            read_optional_profile_custody_local_record(
                _retirement_path_beside(path),
                maximum_bytes=_PROFILE_SESSION_RETIREMENT_MAX_BYTES,
            )
            is not None
        ):
            return False
        captured = _read_receipt(path)
        if captured is None:
            return False
        payload, decoded = captured
        record = current_record(decoded)
        if record is None or not _refresh_record_matches(record, sign_in=sign_in, login_id=login_id, now=now):
            return False
        try:
            material = acceleration_receipt_crypto.unwrap_profile_session_dek(
                session_key=bytes(receipt_key), record=record
            )
        except DecryptionError:
            return False
        try:
            if min(record.idle_deadline, record.absolute_deadline) >= deadline:
                return True
            successor = acceleration_receipt_crypto.wrap_profile_session_dek(
                session_key=bytes(receipt_key),
                dek=bytes(material),
                profile_id=record.profile_id,
                session_id=record.session_id,
                custody_generation=record.custody_generation,
                dek_epoch=record.dek_epoch,
                login_id=login_id,
                sign_in=record.sign_in,
                issued_at=record.issued_at,
                idle_deadline=max(record.idle_deadline, deadline),
                absolute_deadline=max(record.absolute_deadline, deadline),
            )
            _publish_receipt(path, profile_id=binding.profile_id, record=successor, predecessor=payload)
            return True
        finally:
            zeroise(material)


def _refusal(
    reason: ProfileSessionRefusalReason,
    record: acceleration_receipt_crypto.PersistedProfileSession | None = None,
    *,
    deletion: ReceiptDeletion = ReceiptDeletion.NOT_REQUIRED,
    binding: ReceiptBindingRefusal | None = None,
    keychain: KeychainUnavailability | None = None,
) -> tuple[ProfileSessionResumeOutcome, None]:
    outcome = ProfileSessionResumeOutcome(
        resumed=False, refusal=reason, record=record, deletion=deletion, binding=binding, keychain=keychain
    )
    return outcome, None


def _resume_artifacts_present(*, path: Path, retirement_path: Path) -> bool:
    """Observe whether either receipt artifact exists without taking a lock."""
    if (
        read_optional_profile_custody_local_record(
            path,
            maximum_bytes=PROFILE_SESSION_RECORD_MAX_BYTES,
        )
        is not None
    ):
        return True
    return (
        read_optional_profile_custody_local_record(
            retirement_path,
            maximum_bytes=_PROFILE_SESSION_RETIREMENT_MAX_BYTES,
        )
        is not None
    )


def _receipt_refusal_reason(
    *,
    record: acceleration_receipt_crypto.PersistedProfileSession,
    profile_id: UUID,
    custody_generation: int,
    dek_epoch: str,
    now: datetime,
) -> ProfileSessionRefusalReason | None:
    """Classify current metadata without choosing a caller's cleanup policy."""
    if record.schema_version != acceleration_receipt_crypto.PROFILE_SESSION_SCHEMA_VERSION:
        return ProfileSessionRefusalReason.SCHEMA_VERSION_MISMATCH
    if record.profile_id != profile_id:
        return ProfileSessionRefusalReason.TAMPERED
    if record.custody_generation != custody_generation or record.dek_epoch != dek_epoch:
        return ProfileSessionRefusalReason.CUSTODY_CHANGED
    if now >= record.absolute_deadline:
        return ProfileSessionRefusalReason.EXPIRED_ABSOLUTE
    if now >= record.idle_deadline:
        return ProfileSessionRefusalReason.EXPIRED_IDLE
    return None


def borrow_profile_session_key(
    *,
    storage_root: Path,
    profile_id: UUID,
) -> tuple[ProfileSessionResumeOutcome, bytearray | None]:
    """Read only the keychain proof that the receipt's locator names.

    This is the frontend's whole share of a receipt: it reads the receipt's
    schema-independent header for the session the keychain account is named
    by, then reads that account. It never decrypts the record, unwraps the DEK,
    evaluates deadlines or custody, settles a retirement journal, or deletes
    either half; the runtime's supplied-key reader decides and owns every
    deletion. A ``resumed`` outcome here means only that a proof was read; it
    carries no record. The returned buffer belongs to its caller, which must
    wipe it after one protected IPC exchange.

    The receipt-local lock is held only so the locator and key are read as a
    pair against a concurrent mint or deletion; nothing is written under it.
    An absent receipt stays ``ABSENT``, and also names the keychain's
    unavailability when this process could not have kept or presented one.
    """
    path = profile_session_path(storage_root=storage_root, profile_id=profile_id)
    if not path.parent.is_dir():
        # A profile that never held a receipt has no keystore directory; the
        # borrow reports that without provisioning one.
        return _refusal(ProfileSessionRefusalReason.ABSENT, keychain=probe_profile_session_keychain())
    try:
        if read_optional_profile_custody_local_record(path, maximum_bytes=PROFILE_SESSION_RECORD_MAX_BYTES) is None:
            return _refusal(ProfileSessionRefusalReason.ABSENT, keychain=probe_profile_session_keychain())
        with profile_custody_local_lock(profile_session_lock_path(path)):
            payload = read_optional_profile_custody_local_record(path, maximum_bytes=PROFILE_SESSION_RECORD_MAX_BYTES)
            if payload is None:
                return _refusal(ProfileSessionRefusalReason.ABSENT, keychain=probe_profile_session_keychain())
            locator = parse_receipt_header(payload)
            if locator.profile_id != profile_id:
                return _refusal(ProfileSessionRefusalReason.TAMPERED)
            try:
                key = read_acceleration_secret(profile_id=locator.profile_id, session_id=locator.session_id)
            except KeyringUnavailableError as exc:
                return _refusal(ProfileSessionRefusalReason.KEYRING_UNAVAILABLE, keychain=exc.unavailability)
            if key is None:
                return _refusal(ProfileSessionRefusalReason.KEYCHAIN_ENTRY_MISSING)
            return ProfileSessionResumeOutcome(resumed=True), bytearray(key)
    except (ProfileCustodyRecordError, StorageValidationError, ValueError, ValidationError):
        return _refusal(ProfileSessionRefusalReason.MALFORMED)


def resume_profile_session_with_key(
    *,
    storage_root: Path,
    profile_id: UUID,
    custody_generation: int,
    dek_epoch: str,
    now: datetime,
    receipt_key: bytearray,
    login_id: str,
    sign_in: SignInGenerationCustody,
) -> tuple[ProfileSessionResumeOutcome, bytearray | None]:
    """Verify a supplied human wrap key; the runtime's only receipt unwrap.

    It never reads the keychain for a key. Before any unwrap it checks the
    receipt against the generation ``sign_in`` currently holds, observed under
    the custody root lock that every generation write also holds, and against
    ``login_id``, the originating OS login of the connection presenting the
    proof. A receipt that its own bytes refuse whatever proof is supplied --
    malformed, another schema, another profile, changed custody, an elapsed
    deadline, or a generation that is missing, unreadable or no longer
    current -- is deleted here, both halves, and the outcome reports how far
    that deletion got. A login mismatch depends on who is calling, so it
    deletes only once the supplied proof has unwrapped the receipt; the
    unwrapped key is then discarded and the refusal is the same. A wrong
    client proof never deletes the current record or its stored key, whatever
    login presents it, because a proof that fails to unwrap cannot tell a
    stale or forged key from a corrupt record. The verified record carries
    the original deadlines; this door does not advance either deadline or
    publish an ambient process session.

    Raises:
        StorageValidationError: When ``sign_in`` is bound to another storage
            root or profile than the receipt being resumed.
    """
    now = validate_utc_aware(now)
    if sign_in.root != storage_root or sign_in.binding.profile_id != profile_id:
        raise StorageValidationError("sign-in generation custody does not belong to this receipt")
    if len(receipt_key) != acceleration_receipt_crypto.PROFILE_SESSION_KEY_BYTES:
        return _refusal(ProfileSessionRefusalReason.TAMPERED)
    path = profile_session_path(storage_root=storage_root, profile_id=profile_id)
    retirement_path = profile_session_retirement_path(storage_root=storage_root, profile_id=profile_id)
    try:
        with profile_custody_root_lock(storage_root):
            ensure_profile_session_directory(path)
            if not _resume_artifacts_present(path=path, retirement_path=retirement_path):
                return _refusal(ProfileSessionRefusalReason.ABSENT)
            with profile_custody_local_lock(profile_session_lock_path(path)):
                # An interrupted key swap is settled here, by the runtime, as
                # an exact-byte decision on the journal; the supplied key never
                # chooses a side. A keychain that cannot answer leaves it pending.
                try:
                    recover_pending_retirement(storage_root=storage_root, profile_id=profile_id)
                except KeyringUnavailableError as exc:
                    return _refusal(ProfileSessionRefusalReason.KEYRING_UNAVAILABLE, keychain=exc.unavailability)
                payload = read_optional_profile_custody_local_record(
                    path, maximum_bytes=PROFILE_SESSION_RECORD_MAX_BYTES
                )
                if payload is None:
                    return _refusal(ProfileSessionRefusalReason.ABSENT)
                return _resume_supplied_key_locked(
                    path=path,
                    payload=payload,
                    expected=_ExpectedReceipt(
                        profile_id=profile_id,
                        custody_generation=custody_generation,
                        dek_epoch=dek_epoch,
                        now=now,
                        login_id=login_id,
                        generation=sign_in.observe(),
                    ),
                    receipt_key=receipt_key,
                )
    except (ProfileCustodyRecordError, StorageValidationError, ValueError, ValidationError):
        return _refusal(ProfileSessionRefusalReason.MALFORMED)


class _ExpectedReceipt(BaseModel):
    """Everything a receipt must match before its supplied key may unwrap it."""

    model_config = STRICT_FROZEN_CONFIG

    profile_id: UUID
    custody_generation: int
    dek_epoch: str
    now: datetime
    login_id: str
    generation: SignInGenerationObservation


_GENERATION_UNAVAILABLE: Final[dict[SignInGenerationState, ReceiptBindingRefusal]] = {
    SignInGenerationState.MISSING: ReceiptBindingRefusal.GENERATION_MISSING,
    SignInGenerationState.UNREADABLE: ReceiptBindingRefusal.GENERATION_UNREADABLE,
    SignInGenerationState.BINDING_MISMATCH: ReceiptBindingRefusal.GENERATION_BINDING_MISMATCH,
}


def receipt_binding_refusal(
    *,
    record: acceleration_receipt_crypto.PersistedProfileSession,
    login_id: str,
    generation: SignInGenerationObservation,
) -> ReceiptBindingRefusal | None:
    """Decide whether ``record`` belongs to the expected sign-in, with no I/O.

    The generation fence is checked before the login: it is the revocation
    authority, and a fenced receipt is refused whichever login it names.
    """
    if generation.current is None:
        return _GENERATION_UNAVAILABLE.get(generation.state, ReceiptBindingRefusal.GENERATION_UNREADABLE)
    if record.sign_in != generation.current:
        return ReceiptBindingRefusal.GENERATION_CHANGED
    if not acceleration_receipt_crypto.profile_session_login_matches(record=record, login_id=login_id):
        return ReceiptBindingRefusal.LOGIN_MISMATCH
    return None


def _refuse_supplied_key_receipt(
    reason: ProfileSessionRefusalReason,
    *,
    path: Path,
    payload: bytes,
    decoded: DecodedReceipt,
    binding: ReceiptBindingRefusal | None = None,
) -> tuple[ProfileSessionResumeOutcome, None]:
    """Delete a receipt its own bytes refuse, and report the deletion it achieved."""
    deletion = delete_refused_receipt(path=path, payload=payload, decoded=decoded)
    if deletion is not ReceiptDeletion.DELETED:
        _log.warning(
            "refused profile-session receipt not fully deleted reason=%s binding=%s deletion=%s",
            reason.value,
            None if binding is None else binding.value,
            deletion.value,
        )
    return _refusal(reason, current_record(decoded), deletion=deletion, binding=binding)


def _resume_supplied_key_locked(
    *,
    path: Path,
    payload: bytes,
    expected: _ExpectedReceipt,
    receipt_key: bytearray,
) -> tuple[ProfileSessionResumeOutcome, bytearray | None]:
    """Decide one captured receipt against a supplied key under both receipt locks."""
    try:
        decoded = decode_receipt(payload)
    except (ValueError, ValidationError):
        cleared = clear_captured_receipt(path, payload=payload, maximum_bytes=PROFILE_SESSION_RECORD_MAX_BYTES)
        return _refusal(
            ProfileSessionRefusalReason.MALFORMED,
            deletion=ReceiptDeletion.DELETED if cleared else ReceiptDeletion.RECEIPT_RETAINED,
        )
    record = current_record(decoded)
    if record is None:
        return _refuse_supplied_key_receipt(
            ProfileSessionRefusalReason.SCHEMA_VERSION_MISMATCH, path=path, payload=payload, decoded=decoded
        )
    reason = _receipt_refusal_reason(
        record=record,
        profile_id=expected.profile_id,
        custody_generation=expected.custody_generation,
        dek_epoch=expected.dek_epoch,
        now=expected.now,
    )
    if reason is not None:
        return _refuse_supplied_key_receipt(reason, path=path, payload=payload, decoded=decoded)
    binding = receipt_binding_refusal(record=record, login_id=expected.login_id, generation=expected.generation)
    if binding is not None and binding is not ReceiptBindingRefusal.LOGIN_MISMATCH:
        return _refuse_supplied_key_receipt(
            ProfileSessionRefusalReason.ABSENT, path=path, payload=payload, decoded=decoded, binding=binding
        )
    try:
        dek = acceleration_receipt_crypto.unwrap_profile_session_dek(session_key=bytes(receipt_key), record=record)
    except DecryptionError:
        return _refusal(ProfileSessionRefusalReason.TAMPERED, record)
    if binding is not None:
        # The login is the one refusal that depends on who is calling, so only
        # the holder of the proof may retire the sign-in over it; the key
        # recovered to prove that is not handed out.
        zeroise(dek)
        return _refuse_supplied_key_receipt(
            ProfileSessionRefusalReason.ABSENT, path=path, payload=payload, decoded=decoded, binding=binding
        )
    return ProfileSessionResumeOutcome(resumed=True, record=record), dek


def delete_refused_receipt(*, path: Path, payload: bytes, decoded: DecodedReceipt) -> ReceiptDeletion:
    """Remove both halves of a refused receipt and report what remains.

    The disk half is cleared even when the keychain cannot answer, as
    revocation does: a key with no record naming its session unwraps nothing.
    """
    keychain_retained = False
    try:
        delete_acceleration_secret(
            profile_id=decoded.profile_id,
            session_id=decoded.session_id,
            suppress_unavailable=False,
        )
    except KeyringUnavailableError:
        keychain_retained = True
    if not clear_captured_receipt(path, payload=payload, maximum_bytes=PROFILE_SESSION_RECORD_MAX_BYTES):
        return ReceiptDeletion.RECEIPT_RETAINED
    return ReceiptDeletion.KEYCHAIN_ENTRY_RETAINED if keychain_retained else ReceiptDeletion.DELETED


__all__ = [
    "ProfileSessionResumeOutcome",
    "ReceiptBindingRefusal",
    "ReceiptDeletion",
    "borrow_profile_session_key",
    "delete_profile_session",
    "mint_profile_session",
    "profile_session_path",
    "resume_profile_session_with_key",
]
