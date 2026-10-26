"""Own finite fixture projections over real domain and storage kernels."""

from __future__ import annotations

from datetime import datetime

from ......core.classification.policies import SensitivityClass
from ......core.secure_object_write import DEFAULT_WRITE_PROVENANCE
from ...errors import StorageValidationError
from .._secure_object_writes import SecureObjectWriteOperations


def save_with_raw_key(
    self: SecureObjectWriteOperations,
    *,
    namespace: str,
    hashed_object_key: bytes,
    classification: SensitivityClass,
    schema_version: int,
    written_at: datetime,
    payload: bytes,
    write_provenance: str = DEFAULT_WRITE_PROVENANCE,
    source_event_id: str | None = None,
    expected_revision_id: str | None = None,
) -> None:
    """Encrypt and upsert one byte payload keyed by a pre-computed digest.

    The 32-byte ``hashed_object_key`` is passed straight through
    the :class:`~adapters.persistence.storage.crypto.encrypted_columns.HashedLookup` column
    without re-hashing. Used by
    the archive restore path to round-trip rows whose natural key
    is not present in the bundle (e.g. the path-keyed setup-profile
    and inventory namespaces).

    Args:
        namespace: Storage namespace string.
        hashed_object_key: 32 raw HMAC-SHA256 bytes (the digest
            produced by ``HashedLookup.compute`` under the same master key
            the row was originally written with).
        classification:
            :class:`~core.classification.policies.SensitivityClass`
            to upsert at.
        schema_version: Envelope schema version captured on the row.
        written_at: UTC-aware datetime captured on the row. A naive or
            offset-bearing instant is refused for the same reason as
            :meth:`save`.
        payload: Plaintext envelope bytes (the column encrypts).
        write_provenance: Human-readable string identifying the write
            origin (e.g. caller module or operation name). Defaults to
            the repository's default provenance marker.
        source_event_id: Optional opaque identifier of the domain event
            that triggered this write; stored verbatim for audit trails.
        expected_revision_id: Optional optimistic-concurrency guard; when
            supplied the upsert is rejected if the row's current revision
            does not match.

    Raises:
        StorageValidationError: When ``hashed_object_key`` is not exactly 32 bytes.
        :exc:`RepositoryError`: On underlying SQL integrity errors.
    """
    self._check_session_freshness(namespace)
    if len(hashed_object_key) != 32:
        raise StorageValidationError(
            context={"length": len(hashed_object_key)},
            translated_message="errors.integrity.integrity_storage_secure_object_hashed_key_length",
        )
    self._save_internal(
        namespace=namespace,
        key=hashed_object_key,
        classification=classification,
        schema_version=schema_version,
        written_at=written_at,
        payload=payload,
        write_provenance=write_provenance,
        source_event_id=source_event_id,
        expected_revision_id=expected_revision_id,
    )
