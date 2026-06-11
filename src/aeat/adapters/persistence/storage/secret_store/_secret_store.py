"""Encrypted, file-locked store for secret and session-bearing records.

Layered on top of :class:`aeat.adapters.persistence.storage.blob_store.EncryptedBlobStore`
and :func:`aeat.core.locks.exclusive_file_lock`, the store persists
short-lived bearer state (:class:`SensitivityClass` SESSION) and long-lived
authentication material (:class:`SensitivityClass` SECRET) under a stable
string key. Each record is wrapped in an
:class:`aeat.adapters.persistence.storage.envelope.Envelope` of
:class:`SecretRecord`, encrypted via the blob store's per-record DEK wrapped
by the active :class:`MasterKeyProvider` using AES-256-GCM, and indexed by
an HMAC-SHA256 digest of the natural-key string so consumers can query
:meth:`SecretStore.get` without leaking the plaintext key.

A JSON catalogue file at ``store_dir / "index.json"`` maps the hex
digest of each key to the underlying
:class:`aeat.adapters.persistence.storage.blob_store.BlobReference`.
Every mutation acquires ``exclusive_file_lock(store_dir / "secrets.lock")``
so parallel writers serialise rather than race.

The retention contract is enforced at write time: SECRET- and SESSION-class
records MUST carry an ``expires_at`` field; the store raises
:exc:`aeat.adapters.persistence.storage.errors.RetentionPolicyError`
when it is absent.
"""

from __future__ import annotations

import hmac
import os
import tempfile
from collections.abc import Iterable
from datetime import datetime
from hashlib import sha256
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from .....core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from .....core.classification import SensitivityClass, default_policy_for
from .....core.errors import CoreValidationError
from .....core.external_constants import UTF_8_ENCODING
from .....core.locks import exclusive_file_lock
from .....core.logging import get_logger
from .....core.time import now
from .....core.time._utc import validate_utc_aware
from .._namespace_registry import SECRET_RECORD_SCHEMA_VERSION
from ..blob_store._blob_store import BlobReference, EncryptedBlobStore
from ..crypto._crypto import KEY_SIZE, derive_key
from ..envelope._envelope import Envelope
from ..errors import (
    BlobIntegrityError,
    BlobNotFoundError,
    RetentionPolicyError,
    SecretAlreadyExistsError,
    SecretNotFoundError,
    StorageValidationError,
)
from ..master_key._active_session import get_active_master_key
from ..master_key._master_key import MasterKeyProvider

_log = get_logger(__name__)

_INDEX_FILE_NAME = "index.json"
_LOCK_FILE_NAME = "secrets.lock"
_HKDF_CONTEXT_SECRET_LOOKUP = b"aeat.secret_store.lookup.v1"
_STORAGE_VALIDATION_MESSAGE_KEY = "errors.integrity.integrity_storage_validation"


def _storage_validation_error(message: str) -> StorageValidationError:
    return StorageValidationError(message, translated_message=_STORAGE_VALIDATION_MESSAGE_KEY)


class SecretRecord(BaseModel):
    """Frozen record persisted in the :class:`SecretStore`.

    Attributes:
        key: Operator-facing natural key (e.g. ``aeat:google:oauth-token``).
        value: Secret payload as raw bytes. Plaintext on the API surface
            only; the blob store encrypts before write.
        classification: Sensitivity class. Must be
            :attr:`aeat.core.classification.SensitivityClass.SECRET` or
            :attr:`aeat.core.classification.SensitivityClass.SESSION`;
            other classes are rejected by the field validator at
            construction time.
        metadata: Operator-supplied non-secret tags (e.g. operator
            email, issued_by, scope). Stringified key/value entries
            only.
        created_at: Timezone-aware datetime captured at write time.
        expires_at: Optional explicit expiry. Required for the
            ``SECRET`` and ``SESSION`` classes per the default
            retention policy.
    """

    model_config = _STRICT_FROZEN

    key: str = Field(min_length=1, max_length=512)
    value: bytes = Field(min_length=0)
    classification: SensitivityClass
    metadata: dict[str, str] = Field(default_factory=dict)
    created_at: datetime
    expires_at: datetime | None = None

    @field_validator("created_at", "expires_at")
    @classmethod
    def _require_aware(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        try:
            return validate_utc_aware(value)
        except CoreValidationError as exc:
            raise _storage_validation_error(str(exc)) from exc

    @field_validator("classification")
    @classmethod
    def _check_class(cls, value: SensitivityClass) -> SensitivityClass:
        if value not in {SensitivityClass.SECRET, SensitivityClass.SESSION}:
            raise StorageValidationError(
                "SecretRecord.classification must be SECRET or SESSION",
                translated_message="errors.integrity.integrity_storage_validation",
            )
        return value


class _SecretIndexEntry(BaseModel):
    """One row in the JSON-backed secret index.

    Attributes:
        digest_hex: HMAC-SHA256 digest of the natural key as 64 hex chars.
        blob_sha256_plaintext_hex: SHA-256 of the plaintext envelope
            payload, used to address the underlying blob.
        classification: The record's sensitivity class.
    """

    model_config = _STRICT_FROZEN

    digest_hex: str = Field(min_length=64, max_length=64)
    blob_sha256_plaintext_hex: str = Field(min_length=64, max_length=64)
    classification: SensitivityClass


class _SecretIndex(BaseModel):
    """JSON-backed manifest mapping lookup digests to blob references.

    Attributes:
        schema_version: Forward-compatibility marker for the index file.
        entries: Map of digest hex string to :class:`_SecretIndexEntry`.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    schema_version: int = Field(default=1, ge=1)
    entries: dict[str, _SecretIndexEntry] = Field(default_factory=dict)


class SecretStore:
    """Repository for the substrate's secret and session-bearing state.

    Wraps an :class:`aeat.adapters.persistence.storage.blob_store.EncryptedBlobStore`
    behind a digest-keyed index so callers can query records by their
    natural string key without that key ever appearing in plaintext on
    disk. Mutating operations are serialised via
    :func:`aeat.core.locks.exclusive_file_lock`.
    """

    def __init__(
        self,
        *,
        store_dir: Path,
        blob_store: EncryptedBlobStore,
        master_key_provider: MasterKeyProvider | None = None,
    ) -> None:
        """Bind the store to a directory, a blob store, and a master-key provider.

        Args:
            store_dir: Root directory for the index file and the lock
                sidecar. Created on first use.
            blob_store: Underlying encrypted blob store. Records are
                persisted via this repository.
            master_key_provider: Optional override. Used to derive the
                lookup sub-key via HKDF. Falls back to
                :func:`aeat.adapters.persistence.storage.master_key.get_master_key_provider`.
        """
        self._store_dir = Path(store_dir)
        self._blob_store = blob_store
        self._master_key_provider = master_key_provider

    @property
    def store_dir(self) -> Path:
        """Return the configured store directory."""
        return self._store_dir

    def _master_key(self) -> bytes:
        """Return the active master key from injected provider or active session."""
        if self._master_key_provider is not None:
            return self._master_key_provider.get_master_key()
        return get_active_master_key()

    def _digest(self, key: str) -> str:
        """Return the HMAC-SHA256 lookup digest for ``key`` as 64 hex chars."""
        sub_key = derive_key(
            key_material=self._master_key(),
            salt=b"",
            context=_HKDF_CONTEXT_SECRET_LOOKUP,
            length=KEY_SIZE,
        )
        return hmac.new(sub_key, key.encode(UTF_8_ENCODING), sha256).hexdigest()

    def _index_path(self) -> Path:
        """Return the catalogue file path."""
        return self._store_dir / _INDEX_FILE_NAME

    def _lock_target(self) -> Path:
        """Return the path used as the exclusive-write lock sidecar."""
        return self._store_dir / _LOCK_FILE_NAME

    def _read_index(self) -> _SecretIndex:
        """Return the on-disk index, or a fresh empty one when absent."""
        index_path = self._index_path()
        if not index_path.exists():
            return _SecretIndex()
        try:
            return _SecretIndex.model_validate_json(index_path.read_text(encoding=UTF_8_ENCODING))
        except (OSError, ValidationError, ValueError) as exc:
            raise _storage_validation_error("secret-store index is malformed or unreadable") from exc

    def _write_index(self, index: _SecretIndex) -> None:
        """Atomically write ``index`` to disk.

        Uses tempfile + fsync + :func:`os.replace` + parent-dir fsync
        so a crashed writer cannot leave a torn JSON for a concurrent
        reader, and a power loss between :func:`os.replace` and the
        directory flush cannot lose the swap. The index is stored
        plaintext; it carries only digests, never plaintext keys or
        values.
        """
        from .....core.locks import fsync_parent_dir

        self._store_dir.mkdir(parents=True, exist_ok=True)
        target = self._index_path()
        payload = index.model_dump_json(indent=2)
        tmp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding=UTF_8_ENCODING,
                dir=target.parent,
                prefix=f"{target.stem}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                tmp_path = Path(handle.name)
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_path, target)
            fsync_parent_dir(target)
        except OSError:
            _log.error("secret_store: atomic index write failed target=%s", target.name, exc_info=True)
            if tmp_path is not None:
                try:
                    tmp_path.unlink(missing_ok=True)
                except OSError:
                    _log.warning("secret_store: atomic index cleanup failed target=%s", target.name, exc_info=True)
            raise

    def _build_envelope(self, record: SecretRecord) -> Envelope[SecretRecord]:
        """Wrap ``record`` in a versioned, classified envelope."""
        return Envelope[SecretRecord](
            schema_version=SECRET_RECORD_SCHEMA_VERSION,
            written_at=now(),
            classification=record.classification,
            payload=record,
        )

    @staticmethod
    def _envelope_bytes(envelope: Envelope[SecretRecord]) -> bytes:
        """Return the JSON-encoded byte representation of ``envelope``."""
        return envelope.model_dump_json().encode(UTF_8_ENCODING)

    def put(
        self,
        record: SecretRecord,
        *,
        overwrite: bool = False,
    ) -> BlobReference:
        """Persist ``record`` and return the underlying blob reference.

        Acquires the store-wide
        :func:`aeat.core.locks.exclusive_file_lock` for the duration
        of the write.

        Args:
            record: The :class:`SecretRecord` to persist.
            overwrite: If ``True``, replace any existing record at the
                same key. If ``False`` (default), raise
                :exc:`aeat.adapters.persistence.storage.errors.SecretAlreadyExistsError`
                on collision.

        Returns:
            The :class:`aeat.adapters.persistence.storage.blob_store.BlobReference`
            for the freshly written blob.
        """
        self._store_dir.mkdir(parents=True, exist_ok=True)
        with exclusive_file_lock(self._lock_target()):
            return self._put_locked(record, overwrite=overwrite)

    def _put_locked(
        self,
        record: SecretRecord,
        *,
        overwrite: bool = False,
    ) -> BlobReference:
        """Locked-by-caller variant of :meth:`put`.

        The caller MUST already hold the store-wide
        :func:`aeat.core.locks.exclusive_file_lock`. Used by
        :meth:`put` (which wraps in a fresh lock) and :meth:`rotate`
        (which holds the lock across get and put for atomicity).
        """
        policy = default_policy_for(record.classification)
        if policy.retention.require_explicit_expiry and record.expires_at is None:
            raise RetentionPolicyError(
                f"class {record.classification} requires explicit expires_at; "
                "set the field to a timezone-aware datetime.",
            )
        digest = self._digest(record.key)
        index = self._read_index()
        existing = index.entries.get(digest)
        if existing is not None and not overwrite:
            raise SecretAlreadyExistsError("secret already exists; pass overwrite=True to replace.")
        envelope = self._build_envelope(record)
        wire = self._envelope_bytes(envelope)
        blob_ref = self._blob_store.put(
            wire,
            classification=record.classification,
            content_type="application/json+secret-record",
        )
        index.entries[digest] = _SecretIndexEntry(
            digest_hex=digest,
            blob_sha256_plaintext_hex=blob_ref.sha256_plaintext_hex,
            classification=record.classification,
        )
        self._write_index(index)
        if existing is not None and existing.blob_sha256_plaintext_hex != blob_ref.sha256_plaintext_hex:
            # Drop the previous payload to keep the store tidy. Only
            # the benign "blob already gone" case is silently absorbed;
            # anything else (integrity mismatch, OS error) is logged
            # as a WARNING so the operator can investigate.
            old_ref = BlobReference(
                sha256_plaintext_hex=existing.blob_sha256_plaintext_hex,
                classification=existing.classification,
            )
            try:
                self._blob_store.delete(old_ref)
            except BlobNotFoundError:
                _log.debug("stale secret-store blob cleanup skipped because blob is already absent")
            except (BlobIntegrityError, OSError):
                _log.warning("stale secret-store blob cleanup failed", exc_info=True)
        return blob_ref

    def get(self, key: str) -> SecretRecord:
        """Return the :class:`SecretRecord` persisted under ``key``.

        Args:
            key: The natural key string passed to :meth:`put`.

        Returns:
            The decrypted :class:`SecretRecord`.

        Raises:
            SecretNotFoundError: When no record exists for ``key``.
        """
        digest = self._digest(key)
        index = self._read_index()
        entry = index.entries.get(digest)
        if entry is None:
            raise SecretNotFoundError("no secret persisted for the requested key")
        blob_ref = BlobReference(
            sha256_plaintext_hex=entry.blob_sha256_plaintext_hex,
            classification=entry.classification,
        )
        wire = self._blob_store.get(blob_ref)
        envelope = Envelope[SecretRecord].model_validate_json(wire.decode(UTF_8_ENCODING))
        return envelope.payload

    def delete(self, key: str) -> None:
        """Remove the record persisted under ``key``.

        Args:
            key: The natural key string passed to :meth:`put`.

        Raises:
            SecretNotFoundError: When no record exists for ``key``.
        """
        digest = self._digest(key)
        with exclusive_file_lock(self._lock_target()):
            index = self._read_index()
            entry = index.entries.pop(digest, None)
            if entry is None:
                raise SecretNotFoundError("no secret persisted for the requested key")
            self._write_index(index)
            blob_ref = BlobReference(
                sha256_plaintext_hex=entry.blob_sha256_plaintext_hex,
                classification=entry.classification,
            )
            # Mirrors the put path: the benign already-gone case is
            # logged at DEBUG; the rest is logged as a WARNING.
            try:
                self._blob_store.delete(blob_ref)
            except BlobNotFoundError:
                _log.debug("secret-store blob cleanup on delete skipped because blob is already absent")
            except (BlobIntegrityError, OSError):
                _log.warning("secret-store blob cleanup on delete failed", exc_info=True)

    def list_digests(self) -> Iterable[str]:
        """Yield every persisted lookup digest.

        Plaintext keys are NOT recoverable from digests by design; this
        method exists for inventory diagnostics (e.g. counting records,
        rotating store-wide).

        Returns:
            A tuple of 64-character hex digests in iteration order.
        """
        index = self._read_index()
        return tuple(index.entries.keys())

    def rotate(self, key: str, new_value: bytes, *, expires_at: datetime | None = None) -> BlobReference:
        """Replace the value of an existing secret and return the new blob reference.

        Holds the store-wide :func:`aeat.core.locks.exclusive_file_lock`
        across the read and write so a concurrent :meth:`rotate`,
        :meth:`put`, or :meth:`delete` cannot interleave between the
        lookup and the overwrite.

        Args:
            key: Natural key of the record to rotate.
            new_value: The new secret payload bytes.
            expires_at: New explicit expiry. Required when the policy
                mandates it.

        Returns:
            The :class:`aeat.adapters.persistence.storage.blob_store.BlobReference`
            of the rotated blob.

        """
        # Atomic rotate sequence: get -> build -> put-locked, all under
        # the store-wide lock so a concurrent rotate / put / delete
        # cannot interleave between the lookup and the overwrite.
        # ``get`` is read-only and does not acquire the lock;
        # ``_put_locked`` is the lock-bypass variant of ``put`` and is
        # safe to call inside the outer lock.
        self._store_dir.mkdir(parents=True, exist_ok=True)
        with exclusive_file_lock(self._lock_target()):
            existing = self.get(key)
            rotated = SecretRecord(
                key=existing.key,
                value=new_value,
                classification=existing.classification,
                metadata=existing.metadata,
                created_at=now(),
                expires_at=expires_at,
            )
            return self._put_locked(rotated, overwrite=True)


__all__ = [
    "SecretRecord",
    "SecretStore",
]
