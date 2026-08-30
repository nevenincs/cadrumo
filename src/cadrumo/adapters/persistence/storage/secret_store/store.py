"""Encrypted, file-locked store for secret and session-bearing records.

Layered on top of :class:`adapters.persistence.storage.blob_store.EncryptedBlobStore`
and :func:`core.locks.exclusive_file_lock`, the store persists
short-lived bearer state and long-lived authentication material under a
stable string key. ``SECRET_STORE_CLASSES`` below is the one statement of
which :class:`SensitivityClass` members those are; every refusal and
docstring here reads it rather than restating it. Each record is wrapped in an
:class:`adapters.persistence.storage.envelope.Envelope` of
:class:`SecretRecord`, encrypted via the blob store's per-record DEK wrapped
by the active :class:`MasterKeyProvider` using AES-256-GCM, and indexed by
an HMAC-SHA256 digest of the natural-key string so consumers can query
:meth:`SecretStore.get` without leaking the plaintext key.

A JSON catalogue file at ``store_dir / "index.json"`` maps the hex
digest of each key to the underlying
:class:`adapters.persistence.storage.blob_store.BlobReference`.
Every mutation acquires ``exclusive_file_lock(store_dir / "secrets.lock")``
so parallel writers serialise rather than race.

The retention contract is enforced at write time: SECRET- and SESSION-class
records MUST carry an ``expires_at`` field; the store raises
:exc:`~adapters.persistence.storage.RetentionPolicyError`
when it is absent.
"""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from .....core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from .....core.classification import SensitivityClass, default_policy_for
from .....core.errors.hierarchy import CoreValidationError
from .....core.external_constants import UTF_8_ENCODING
from .....core.identity import ContentDigest
from .....core.locks import exclusive_file_lock
from .....core.logging import get_logger
from .....core.time import now, validate_utc_aware
from .._storage_path_definitions import (
    SECRET_INDEX_FILENAME,
    SECRET_INDEX_SCHEMA_VERSION,
    SECRET_RECORD_SCHEMA_VERSION,
)
from ..blob_store import (
    BlobReference,
    EncryptedBlobStore,
)
from ..crypto.aead import derive_key
from ..envelope import Envelope
from ..errors import (
    BlobIntegrityError,
    BlobNotFoundError,
    EnvelopeVersionError,
    RetentionPolicyError,
    SecretAlreadyExistsError,
    SecretNotFoundError,
    StorageValidationError,
)
from ..errors import (
    storage_validation_error as _storage_validation_error,
)
from ..master_key import MasterKeyProvider, get_active_master_key

_log = get_logger(__name__)

_LOCK_FILE_NAME = "secrets.lock"
_HKDF_CONTEXT_SECRET_LOOKUP = b"cadrumo.secret_store.lookup.v1"
_HKDF_CONTEXT_SECRET_VALUE_WITNESS = b"cadrumo.secret_store.value_witness.v1"


def _hkdf_hmac_digest(master_key: bytes, *, context: bytes, material: bytes) -> bytes:
    """Return the deterministic HMAC-SHA256 digest of ``material`` under a master-derived sub-key.

    The "keyed lookup digest" recipe this store uses for both its natural-key
    lookup digest and its value witness: derive a per-consumer 32-byte sub-key
    from ``master_key`` via HKDF-SHA256 (empty salt, ``context`` as the HKDF
    info/context), then HMAC-SHA256 ``material`` under that sub-key. Distinct
    ``context`` values produce unrelated digest spaces from the same master
    key. This store is the only caller, so the recipe lives here rather than
    as a shared crypto-package export.
    """
    sub_key = derive_key(key_material=master_key, salt=b"", context=context)
    return hmac.new(sub_key, material, hashlib.sha256).digest()


#: The only classes a record in this store may carry. The record model and
#: the index row that describes it both enforce this one set, so an index
#: cannot name a class no record here can have.
SECRET_STORE_CLASSES: Final[frozenset[SensitivityClass]] = frozenset(
    {SensitivityClass.SECRET, SensitivityClass.SESSION},
)


def _validated_secret_class(value: SensitivityClass, *, subject: str) -> SensitivityClass:
    """Return ``value`` if it is a class this store may persist.

    The refusal names the accepted set by reading it, rather than restating it
    as prose. The message previously read "must be SECRET or SESSION" while the
    test above it was ``value not in SECRET_STORE_CLASSES`` -- two statements of
    one closed set, so widening the set would have left the operator holding a
    refusal that contradicted the code raising it.
    """
    if value not in SECRET_STORE_CLASSES:
        accepted = ", ".join(sorted(member.name for member in SECRET_STORE_CLASSES))
        raise StorageValidationError(
            f"{subject} must be one of {accepted}",
            translated_message="errors.integrity.integrity_storage_validation",
        )
    return value


class SecretRecord(BaseModel):
    """Frozen record persisted in the :class:`SecretStore`.

    Attributes:
        key: Operator-facing natural key (e.g. ``aeat:google:oauth-token``).
        value: Secret payload as raw bytes. Plaintext on the API surface
            only; the blob store encrypts before write.
        classification: Sensitivity class. Must be a member of
            ``SECRET_STORE_CLASSES``, which is the one statement of that
            closed set; other classes are rejected by the field validator
            at construction time.
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
        return _validated_secret_class(value, subject="SecretRecord.classification")


class _SecretIndexEntry(BaseModel):
    """One row in the JSON-backed secret index.

    Attributes:
        digest_hex: HMAC-SHA256 digest of the natural key. This restates the
            mapping key the entry is filed under, and every lookup uses that
            key rather than this field -- so on its own the field was purely
            advisory and could disagree with its own key indefinitely without
            any surface noticing. It is retained as a checked cross-reference,
            not deleted: :meth:`SecretStore._read_index` now requires it to
            equal the key, which turns a duplicate that could lie into a
            self-check that catches a torn or hand-edited index.
        blob_sha256_plaintext_hex: SHA-256 of the plaintext envelope
            payload, used to address the underlying blob.
        classification: The record's sensitivity class.
    """

    model_config = _STRICT_FROZEN

    digest_hex: ContentDigest
    blob_sha256_plaintext_hex: ContentDigest
    classification: SensitivityClass

    @field_validator("classification")
    @classmethod
    def _check_class(cls, value: SensitivityClass) -> SensitivityClass:
        """Hold the index to the same closed set the record itself allows.

        ``SecretRecord`` accepts only ``SECRET_STORE_CLASSES``, but the index
        row describing it accepted the whole ``SensitivityClass`` enum -- so
        the index could name a class no record in this store can ever have,
        and the blob layout was then routed from that value.
        """
        return _validated_secret_class(value, subject="_SecretIndexEntry.classification")


class _SecretIndex(BaseModel):
    """JSON-backed manifest mapping lookup digests to blob references.

    Attributes:
        schema_version: Format version of the index file, gated against
            :data:`SECRET_INDEX_SCHEMA_VERSION` on every read. Required and
            stamped explicitly, never defaulted: a default equal to the current
            version makes an index file that omits the key hydrate AS current,
            so the gate below reads a value the writer never wrote and passes.
            Every mutation rewrites the whole index, so that misread would then
            be written back over the file it misread.
        entries: Map of digest hex string to :class:`_SecretIndexEntry`.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    schema_version: int = Field(ge=1)
    entries: dict[str, _SecretIndexEntry] = Field(default_factory=dict)


class SecretStore:
    """Repository for the substrate's secret and session-bearing state.

    Wraps an :class:`adapters.persistence.storage.blob_store.EncryptedBlobStore`
    behind a digest-keyed index so callers can query records by their
    natural string key without that key ever appearing in plaintext on
    disk. Mutating operations are serialised via
    :func:`core.locks.exclusive_file_lock`.
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
                the active bucket session's data key.
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
        digest = _hkdf_hmac_digest(
            self._master_key(),
            context=_HKDF_CONTEXT_SECRET_LOOKUP,
            material=key.encode(UTF_8_ENCODING),
        )
        return digest.hex()

    def value_witness(self, *, key: str, value: bytes) -> str:
        """Return a master-keyed, non-reversible witness for one key/value request."""
        material = key.encode(UTF_8_ENCODING) + b"\x00" + value
        digest = _hkdf_hmac_digest(
            self._master_key(),
            context=_HKDF_CONTEXT_SECRET_VALUE_WITNESS,
            material=material,
        )
        return digest.hex()

    def _index_path(self) -> Path:
        """Return the catalogue file path."""
        return self._store_dir / SECRET_INDEX_FILENAME

    def _lock_target(self) -> Path:
        """Return the path used as the exclusive-write lock sidecar."""
        return self._store_dir / _LOCK_FILE_NAME

    def _read_index(self) -> _SecretIndex:
        """Return the on-disk index, or a fresh empty one when absent.

        Every read and every mutation of the store passes through here, which
        is why the format-version gate belongs here rather than at each call
        site: a mutation rewrites the whole index, so an index this build
        cannot interpret must be refused before it is read, not after it has
        been written back in a shape the writer understood differently.

        The same argument places the key/value digest agreement here. Each
        entry restates, in ``digest_hex``, the mapping key it is filed under,
        and every lookup uses the key -- so the restatement was advisory and
        could disagree with its own key indefinitely. Requiring agreement in
        the one loader converts a duplicate that could lie into a self-check
        on a torn or hand-edited index, and it applies to mutations too, which
        would otherwise rewrite the disagreement back to disk.

        The mapping keys need no separate shape check, and adding one would be
        unreachable code rather than defence in depth. A ``dict`` key carries
        no pydantic annotation, but ``digest_hex`` does: it is a canonical
        :data:`~core.identity.ContentDigest`, so once the equality above holds
        the key is that same validated value. A malformed key either differs
        from its entry's digest -- caught here -- or matches it, in which case
        the entry itself failed validation above.
        """
        index_path = self._index_path()
        if not index_path.exists():
            # Create-on-first-access: an absent file is a store that has never
            # been written, not a document to interpret, so a fresh index at
            # the current version is materialised exactly as before. The
            # version is stamped here rather than defaulted on the field so
            # that this ONE legitimate source of an unstamped index stays
            # explicit, while a FILE that omits the marker still refuses.
            return _SecretIndex(schema_version=SECRET_INDEX_SCHEMA_VERSION)
        try:
            index = _SecretIndex.model_validate_json(index_path.read_text(encoding=UTF_8_ENCODING))
        except (OSError, ValidationError, ValueError) as exc:
            raise _storage_validation_error("secret-store index is malformed or unreadable") from exc
        # The field documented itself as a forward-compatibility marker, but
        # this comparison used to be absent -- an index claiming any version
        # was accepted and every read and mutation proceeded against it. A
        # marker nothing compares is not forward compatibility: the first
        # real format change would have been read by a build that could not
        # interpret it, and -- because every mutation rewrites the whole
        # index -- the misread would have been written back.
        #
        # The index is enrolled in the persistence compatibility policy as a
        # DURABLE format (``secret_index`` in :data:`~core.PERSISTED_FORMATS`),
        # so a future version bump is governed by the same upgrade-chain
        # rules as every other persisted format rather than by this check
        # alone.
        if index.schema_version != SECRET_INDEX_SCHEMA_VERSION:
            raise EnvelopeVersionError(
                f"secret-store index is at version {index.schema_version}; "
                f"consumer expects {SECRET_INDEX_SCHEMA_VERSION}",
            )
        drifted = sorted(key for key, entry in index.entries.items() if entry.digest_hex != key)
        if drifted:
            raise _storage_validation_error(
                f"secret-store index entries disagree with their own lookup digest: {drifted}",
            )
        return index

    def _write_index(self, index: _SecretIndex) -> None:
        """Atomically write ``index`` to disk.

        Delegates to :func:`~cadrumo.core.atomic_write.atomic_write_text`
        (standard tier: tempfile + fsync + :func:`os.replace` + parent-dir
        fsync) so a crashed writer cannot leave a torn JSON for a
        concurrent reader, and a power loss between the replace and the
        directory flush cannot lose the swap. The index is stored
        plaintext; it carries only digests, never plaintext keys or
        values.
        """
        # Deferred import: mirrors this method's existing deferred
        # `core.locks` import (kept local to avoid widening this module's
        # eager import surface for a bootstrap-adjacent secret-store path).
        from .....core.atomic_write import atomic_write_text

        target = self._index_path()
        payload = index.model_dump_json(indent=2)
        try:
            atomic_write_text(target, payload, encoding=UTF_8_ENCODING)
        except OSError:
            _log.error("secret_store: atomic index write failed target=%s", target.name, exc_info=True)
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
        :func:`core.locks.exclusive_file_lock` for the duration
        of the write.

        Args:
            record: The :class:`SecretRecord` to persist.
            overwrite: If ``True``, replace any existing record at the
                same key. If ``False`` (default), raise
                :exc:`~adapters.persistence.storage.SecretAlreadyExistsError`
                on collision.

        Returns:
            The :class:`adapters.persistence.storage.blob_store.BlobReference`
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
        :func:`core.locks.exclusive_file_lock`. Used by
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
        try:
            self._write_index(index)
        except (OSError, ValidationError, ValueError):
            # The blob is already published and discoverable by the blob store,
            # but no index entry owns it. Leaving it would accumulate
            # unreferenced sensitive material that inventory cannot associate
            # with any natural key, and a retry would add another copy. Undo
            # the publication so the failed put leaves the store exactly as it
            # found it, then surface the original failure.
            #
            # Guarded against discarding a blob the unchanged index still
            # points at. In practice a re-put mints a fresh blob -- the
            # envelope stamps ``written_at``, so the wire bytes differ every
            # time -- but content addressing does not forbid the references
            # coinciding, and if they did, deleting would destroy the live
            # record rather than an orphan.
            if existing is None or existing.blob_sha256_plaintext_hex != blob_ref.sha256_plaintext_hex:
                self._discard_unreferenced_blob(blob_ref)
            raise

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

    def _discard_unreferenced_blob(self, blob_ref: BlobReference) -> None:
        """Best-effort removal of a blob no index entry owns.

        Used only to unwind a publication whose index commit failed. A failure
        here is logged rather than raised: the caller is already unwinding an
        error, and replacing that error with this one would hide the reason
        the put failed. The blob is left behind in that case, which is the
        same outcome as before this compensation existed.
        """
        try:
            self._blob_store.delete(blob_ref)
        except BlobNotFoundError:
            _log.debug("secret-store rollback skipped because the blob is already absent")
        except (BlobIntegrityError, OSError):
            _log.warning("secret-store could not roll back an unreferenced blob after an index failure", exc_info=True)

    def get(self, key: str) -> SecretRecord:
        """Return the :class:`SecretRecord` persisted under ``key``.

        Args:
            key: The natural key string passed to :meth:`put`.

        Returns:
            The decrypted :class:`SecretRecord`.

        Raises:
            SecretNotFoundError: When no record exists for ``key``.
            StorageValidationError: When the index, the stored envelope, and
                the record itself do not all name the same class.
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
        # The class is stated three times about one record -- on the index row
        # that located it, on the envelope sealed with it, and on the record
        # itself -- and only the first two were ever compared, by the blob
        # store's own manifest gate. Relabelling the index and the manifest
        # together therefore satisfied every check while the encrypted bytes
        # still held a SECRET record, and the store returned it. The record's
        # own statement is the one the writer sealed and the only one an
        # editor cannot reach without the key, so it is what the other two
        # must agree with.
        record = envelope.payload
        if entry.classification is not record.classification or envelope.classification is not record.classification:
            raise _storage_validation_error(
                "secret-store classification disagreement between index, envelope, and record",
            )
        # The index binds a lookup digest to a blob reference, but nothing bound
        # the ENCRYPTED RECORD back to the key it was filed under. Repointing one
        # index entry at another entry's blob therefore returned a perfectly valid
        # record for a different key: same class, same envelope, every existing
        # check satisfied. The class triad above cannot see it, because both
        # records are the same class. The record states its own key, and that
        # statement is the one the writer sealed and an index editor cannot reach,
        # so it is what the lookup must agree with.
        if record.key != key:
            raise _storage_validation_error(
                "secret-store record does not carry the key it was addressed by",
            )
        return record

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
            entry = index.entries.get(digest)
            if entry is None:
                raise SecretNotFoundError("no secret persisted for the requested key")
            blob_ref = BlobReference(
                sha256_plaintext_hex=entry.blob_sha256_plaintext_hex,
                classification=entry.classification,
            )
            # Delete the payload BEFORE dropping index ownership of it. The
            # previous order rewrote the index first and then swallowed a
            # failed blob delete as a warning, which left complete encrypted
            # secret material on disk that nothing in the store any longer
            # referenced: list_digests() was empty and get() raised
            # SecretNotFoundError, while the original BlobReference still
            # loaded the secret. Deleting first makes a failure leave the
            # record fully owned and the operation simply retryable.
            #
            # An already-absent blob is the benign case: there is nothing to
            # orphan, so the index entry is dropped as usual.
            try:
                self._blob_store.delete(blob_ref)
            except BlobNotFoundError:
                _log.debug("secret-store blob cleanup on delete skipped because blob is already absent")
            del index.entries[digest]
            self._write_index(index)

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

        Holds the store-wide :func:`core.locks.exclusive_file_lock`
        across the read and write so a concurrent :meth:`rotate`,
        :meth:`put`, or :meth:`delete` cannot interleave between the
        lookup and the overwrite.

        Args:
            key: Natural key of the record to rotate.
            new_value: The new secret payload bytes.
            expires_at: New explicit expiry. Required when the policy
                mandates it.

        Returns:
            The :class:`adapters.persistence.storage.blob_store.BlobReference`
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
