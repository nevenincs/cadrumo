"""Secret store built on top of the encrypted blob store and the file lock.

The store persists short-lived bearer state (SESSION) and long-lived
authentication material (SECRET) under a stable string key. Each
record:

- is wrapped in a :class:`Envelope[SecretRecord]` (serialised to JSON
  alongside the blob);
- is encrypted via the :class:`EncryptedBlobStore`'s ciphertext layout
  (per-record DEK; master-key-wrapped DEK; AES-256-GCM payload);
- is indexed by an HMAC-SHA256 digest of the natural-key string
  (computed via :class:`HashedLookup` semantics), so consumers can
  query ``store.get(key)`` without leaking the plaintext key.

A small JSON catalogue file under ``aeat_secret_store_dir / "index.json"``
maps the hex digest of the key to the underlying
:class:`BlobReference`. Every mutation acquires
``exclusive_file_lock(secret_store_dir / "secrets.lock")`` so two
parallel writers serialise rather than race.

The retention contract is enforced at write time:
``SECRET``- and ``SESSION``-class records MUST carry an ``expires_at``
field; the store raises :class:`RetentionPolicyError` if it is
absent.
"""

from __future__ import annotations

import contextlib
import hmac
from collections.abc import Iterable
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ._blob_store import BlobReference, EncryptedBlobStore
from ._classification import SensitivityClass, default_policy_for
from ._crypto import KEY_SIZE, derive_key
from ._envelope import Envelope
from ._lock import exclusive_file_lock
from ._master_key import MasterKeyProvider, get_master_key_provider
from .errors import (
    RetentionPolicyError,
    SecretAlreadyExistsError,
    SecretNotFoundError,
)

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")
_INDEX_FILE_NAME = "index.json"
_LOCK_FILE_NAME = "secrets.lock"
_HKDF_CONTEXT_SECRET_LOOKUP = b"aeat.secret_store.lookup.v1"
_SECRET_RECORD_VERSION = 1


class SecretRecord(BaseModel):
    """Frozen record persisted in the secret store.

    Attributes:
        key: Operator-facing natural key (e.g. ``aeat:google:oauth-token``).
        value: Secret payload as raw bytes. Plaintext on the API surface
            only; the blob store encrypts before write.
        classification: Sensitivity class. Must be SECRET or SESSION;
            other classes are rejected at write time with
            :class:`SecretStoreError`.
        metadata: Operator-supplied non-secret tags (e.g. operator email,
            issued_by, scope). Stringified key/value entries only.
        created_at: Timezone-aware datetime captured at write time.
        expires_at: Optional explicit expiry. Required for the SECRET
            and SESSION classes per the default retention policy.
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
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("datetime fields must be timezone-aware")
        return value

    @field_validator("classification")
    @classmethod
    def _check_class(cls, value: SensitivityClass) -> SensitivityClass:
        if value not in {SensitivityClass.SECRET, SensitivityClass.SESSION}:
            raise ValueError("SecretRecord.classification must be SECRET or SESSION")
        return value


class _SecretIndexEntry(BaseModel):
    """One row in the JSON-backed secret index."""

    model_config = _STRICT_FROZEN

    digest_hex: str = Field(min_length=64, max_length=64)
    blob_sha256_plaintext_hex: str = Field(min_length=64, max_length=64)
    classification: SensitivityClass


class _SecretIndex(BaseModel):
    """JSON-backed manifest mapping HashedLookup digests to blob references."""

    model_config = ConfigDict(strict=True, extra="forbid")

    schema_version: int = Field(default=1, ge=1)
    entries: dict[str, _SecretIndexEntry] = Field(default_factory=dict)


class SecretStore:
    """Repository for the substrate's secret + session-bearing state."""

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
                HashedLookup sub-key. Falls back to
                :func:`get_master_key_provider`.
        """
        self._store_dir = Path(store_dir)
        self._blob_store = blob_store
        self._master_key_provider = master_key_provider

    @property
    def store_dir(self) -> Path:
        """Return the configured store directory."""
        return self._store_dir

    def _master_key(self) -> bytes:
        provider = self._master_key_provider or get_master_key_provider()
        return provider.get_master_key()

    def _digest(self, key: str) -> str:
        sub_key = derive_key(
            key_material=self._master_key(),
            salt=b"",
            context=_HKDF_CONTEXT_SECRET_LOOKUP,
            length=KEY_SIZE,
        )
        return hmac.new(sub_key, key.encode("utf-8"), sha256).hexdigest()

    def _index_path(self) -> Path:
        return self._store_dir / _INDEX_FILE_NAME

    def _lock_target(self) -> Path:
        return self._store_dir / _LOCK_FILE_NAME

    def _read_index(self) -> _SecretIndex:
        index_path = self._index_path()
        if not index_path.exists():
            return _SecretIndex()
        return _SecretIndex.model_validate_json(index_path.read_text(encoding="utf-8"))

    def _write_index(self, index: _SecretIndex) -> None:
        self._store_dir.mkdir(parents=True, exist_ok=True)
        # The index is stored plaintext; it carries only digests (no
        # plaintext keys, no plaintext values).
        self._index_path().write_text(index.model_dump_json(indent=2), encoding="utf-8")

    def _build_envelope(self, record: SecretRecord) -> Envelope[SecretRecord]:
        return Envelope[SecretRecord](
            schema_version=_SECRET_RECORD_VERSION,
            written_at=datetime.now(UTC),
            classification=record.classification,
            payload=record,
        )

    @staticmethod
    def _envelope_bytes(envelope: Envelope[SecretRecord]) -> bytes:
        return envelope.model_dump_json().encode("utf-8")

    def put(
        self,
        record: SecretRecord,
        *,
        overwrite: bool = False,
    ) -> BlobReference:
        """Persist ``record``. Returns the underlying blob reference.

        Args:
            record: The :class:`SecretRecord` to persist.
            overwrite: If ``True``, replace any existing record at the
                same key. If ``False`` (default), raise
                :class:`SecretAlreadyExistsError` on collision.

        Raises:
            RetentionPolicyError: If ``record.expires_at`` is required
                by the class's retention policy and absent.
            SecretAlreadyExistsError: If the key already exists and
                ``overwrite`` is ``False``.
            SecretStoreError: If the classification is not SECRET or
                SESSION (defensive; the pydantic validator catches this
                at construction).
        """
        policy = default_policy_for(record.classification)
        if policy.retention.require_explicit_expiry and record.expires_at is None:
            raise RetentionPolicyError(
                f"class {record.classification} requires explicit expires_at; "
                "set the field to a timezone-aware datetime.",
            )
        digest = self._digest(record.key)
        self._store_dir.mkdir(parents=True, exist_ok=True)
        with exclusive_file_lock(self._lock_target()):
            index = self._read_index()
            existing = index.entries.get(digest)
            if existing is not None and not overwrite:
                raise SecretAlreadyExistsError(
                    f"secret already exists at digest {digest}; pass overwrite=True to replace.",
                )
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
                # Drop the previous payload to keep the store tidy.
                old_ref = BlobReference(
                    sha256_plaintext_hex=existing.blob_sha256_plaintext_hex,
                    classification=existing.classification,
                )
                with contextlib.suppress(Exception):
                    self._blob_store.delete(old_ref)
        return blob_ref

    def get(self, key: str) -> SecretRecord:
        """Return the :class:`SecretRecord` persisted under ``key``.

        Raises:
            SecretNotFoundError: If no record exists for ``key``.
        """
        digest = self._digest(key)
        index = self._read_index()
        entry = index.entries.get(digest)
        if entry is None:
            raise SecretNotFoundError(f"no secret persisted under digest {digest}")
        blob_ref = BlobReference(
            sha256_plaintext_hex=entry.blob_sha256_plaintext_hex,
            classification=entry.classification,
        )
        wire = self._blob_store.get(blob_ref)
        envelope = Envelope[SecretRecord].model_validate_json(wire.decode("utf-8"))
        return envelope.payload

    def delete(self, key: str) -> None:
        """Remove the record persisted under ``key``.

        Raises:
            SecretNotFoundError: If no record exists for ``key``.
        """
        digest = self._digest(key)
        with exclusive_file_lock(self._lock_target()):
            index = self._read_index()
            entry = index.entries.pop(digest, None)
            if entry is None:
                raise SecretNotFoundError(f"no secret persisted under digest {digest}")
            self._write_index(index)
            blob_ref = BlobReference(
                sha256_plaintext_hex=entry.blob_sha256_plaintext_hex,
                classification=entry.classification,
            )
            with contextlib.suppress(Exception):
                self._blob_store.delete(blob_ref)

    def list_digests(self) -> Iterable[str]:
        """Yield every persisted lookup digest.

        Plaintext keys are NOT recoverable from digests by design; this
        method exists for inventory diagnostics (e.g. counting records,
        rotating store-wide).
        """
        index = self._read_index()
        return tuple(index.entries.keys())

    def rotate(self, key: str, new_value: bytes, *, expires_at: datetime | None = None) -> BlobReference:
        """Replace the value of an existing secret and return the new blob reference.

        Args:
            key: Natural key of the record to rotate.
            new_value: The new secret payload bytes.
            expires_at: New explicit expiry. Required when the policy
                mandates it.

        Raises:
            SecretNotFoundError: If no record exists for ``key``.
            RetentionPolicyError: If the policy requires explicit
                expiry and ``expires_at`` is None.
        """
        existing = self.get(key)
        rotated = SecretRecord(
            key=existing.key,
            value=new_value,
            classification=existing.classification,
            metadata=existing.metadata,
            created_at=datetime.now(UTC),
            expires_at=expires_at,
        )
        return self.put(rotated, overwrite=True)


__all__ = [
    "SecretRecord",
    "SecretStore",
]
