"""Row-level codec helpers for SQL secure-object records.

This module keeps the encrypted row decode path and post-write revision
metadata update close to the SQL secure-object adapter without leaving both
algorithms embedded in the repository class. It derives and persists revision
lineage after ciphertext is written, validates row classification and the
schema-lineage ceiling before decrypting (a version above the consumer's
current version is refused; an older version decrypts under its written
version and is chain-upgraded to current), and refuses rows whose revision
hashes no longer match their stored metadata.

See Also:
    :class:`~adapters.persistence.storage.sql.secure_objects.SecureObjectRepository`
        Repository that delegates revision metadata writes and row decoding here.
    :func:`~adapters.persistence.storage.sql._secure_object_crypto.derive_revision_id`
        Deterministic revision-id primitive used after a row write.
    :func:`~adapters.persistence.storage.sql._secure_object_crypto.verify_revision_self_consistency`
        Integrity check applied before decrypting an existing row.
    :func:`~adapters.persistence.storage.sql._secure_object_schema.build_revision_ancestor_ids`
        Revision-lineage helper used to persist ancestor chains.
    :class:`~adapters.persistence.storage.sql._secure_object_records.SecureObjectRecord`
        Plaintext record returned after classification, schema, lineage, and
        AEAD checks pass.
    :func:`~adapters.persistence.storage.crypto.secure_object_payload_aad`
        Associated-data builder that binds ciphertext to row identity.
    :class:`SensitivityClass`
        Expected row classification validated before a row is decoded.
    Governing vault records
        ``2026-05-22-secure-storage-production-hardening-architecture-adr`` and
        ``2026-05-28-secure-storage-production-hardening-w04-p07-s30-review-audit``
        require secure-object revision lineage and conflict-safe metadata.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime

from sqlalchemy import bindparam, text, update
from sqlalchemy.orm import Session

from .....core.classification import SensitivityClass
from .....core.errors import resolve_error_message
from .....core.external_constants import UTF_8_ENCODING
from .....core.hashing import sha256_hex
from .....core.logging import get_logger
from .._namespace_registry import SecureObjectNamespaceDefinition
from .._schema_lineage import ensure_schema_version_readable, upgrade_secure_object_payload
from ..crypto import decrypt_secure_object_payload, secure_object_payload_aad
from ..errors import ClassificationError, DecryptionError, EnvelopeVersionError, SecureObjectUnreadableError
from . import _orm
from ._secure_object_crypto import derive_revision_id, verify_revision_self_consistency
from ._secure_object_records import SecureObjectBatchLoadItem, SecureObjectRecord, SecureObjectUnreadable
from ._secure_object_schema import build_revision_ancestor_ids

_log = get_logger(__name__)


def write_revision_metadata(
    session: Session,
    *,
    row_id: int,
    namespace: str,
    schema_version: int,
    written_at: datetime,
    payload: bytes,
    previous_revision_id: str | None,
    previous_revision_ancestor_ids: tuple[str, ...],
    previous_payload_hash: str | None,
    write_provenance: str,
    source_event_id: str | None,
    conflict_policy: str,
) -> None:
    raw = session.execute(
        text("SELECT object_key, payload FROM secure_objects WHERE id = :row_id").bindparams(
            bindparam("row_id", value=row_id),
        ),
    ).one()
    object_key = raw.object_key if isinstance(raw.object_key, bytes) else bytes(raw.object_key)
    ciphertext = raw.payload if isinstance(raw.payload, bytes) else bytes(raw.payload)
    payload_hash = sha256_hex(payload)
    ciphertext_hash = sha256_hex(ciphertext)
    revision_id = derive_revision_id(
        namespace=namespace,
        object_key=object_key,
        schema_version=schema_version,
        written_at=written_at,
        payload_hash=payload_hash,
        ciphertext_hash=ciphertext_hash,
        previous_revision_id=previous_revision_id,
        previous_payload_hash=previous_payload_hash,
    )
    revision_ancestor_ids = build_revision_ancestor_ids(
        previous_revision_id,
        previous_revision_ancestor_ids,
    )
    session.execute(
        update(_orm.SecureObjectRow)
        .where(_orm.SecureObjectRow.id == row_id)
        .values(
            revision_id=revision_id,
            previous_revision_id=previous_revision_id,
            revision_ancestor_ids=json.dumps(revision_ancestor_ids),
            previous_payload_hash=previous_payload_hash,
            payload_hash=payload_hash,
            ciphertext_hash=ciphertext_hash,
            revision_written_at=written_at,
            write_provenance=write_provenance,
            source_event_id=source_event_id,
            conflict_policy=conflict_policy,
        ),
    )


def secure_object_record_from_row(
    row: _orm.SecureObjectRow,
    *,
    expected_class: SensitivityClass,
    max_supported_version: int,
    namespace_definition: SecureObjectNamespaceDefinition | None = None,
    enforce_registered_row_schema: Callable[..., None],
) -> SecureObjectRecord:
    try:
        classification = SensitivityClass(row.classification)
    except ValueError as exc:
        raise ClassificationError(
            context={
                "namespace": row.namespace,
                "classification": row.classification,
            },
            translated_message="errors.storage.namespace.unknown_classification",
        ) from exc
    if classification is not expected_class:
        raise ClassificationError(
            context={
                "namespace": row.namespace,
                "classification": classification.value,
                "expected": expected_class.value,
            },
            translated_message="errors.storage.namespace.classification_mismatch",
        )
    ensure_schema_version_readable(
        namespace=row.namespace,
        schema_version=row.schema_version,
        current_version=max_supported_version,
    )
    enforce_registered_row_schema(
        namespace=row.namespace,
        schema_version=row.schema_version,
        definition=namespace_definition,
    )
    if not verify_revision_self_consistency(
        namespace=row.namespace,
        object_key=bytes(row.object_key),
        schema_version=row.schema_version,
        written_at=row.written_at,
        revision_id=row.revision_id,
        previous_revision_id=row.previous_revision_id,
        payload_hash=row.payload_hash,
        ciphertext_hash=row.ciphertext_hash,
        previous_payload_hash=row.previous_payload_hash,
    ):
        _log.error(
            "secure_objects: revision lineage self-consistency failed for namespace=%s row id=%s",
            row.namespace,
            row.id,
        )
        raise SecureObjectUnreadableError(row.namespace, int(row.id))
    payload_plain = decrypt_secure_object_payload(
        bytes(row.payload),
        associated_data=secure_object_payload_aad(
            row.namespace,
            bytes(row.object_key),
            row.schema_version,
        ),
    )
    if row.schema_version < max_supported_version:
        payload_plain = upgrade_secure_object_payload(
            payload_plain,
            namespace=row.namespace,
            from_version=row.schema_version,
            to_version=max_supported_version,
        )
    return SecureObjectRecord(
        namespace=row.namespace,
        object_key=bytes(row.object_key),
        classification=classification,
        schema_version=max_supported_version,
        written_at=row.written_at,
        payload=payload_plain,
    )


def secure_object_list_item_from_raw_row(
    raw: object,
    *,
    namespace: str,
    expected_class: SensitivityClass,
    max_supported_version: int,
    namespace_definition: SecureObjectNamespaceDefinition | None,
    enforce_registered_row_schema: Callable[..., None],
) -> SecureObjectBatchLoadItem:
    """Decode one raw ``iter_records_with_failures`` row into a typed outcome.

    Fault-isolated: every failure mode (unknown classification, classification
    mismatch, unreadable schema version, decrypt failure, revision-lineage
    inconsistency, upgrade failure) returns a
    :class:`~._secure_object_records.SecureObjectUnreadable` carrying the
    reason instead of raising, so a caller iterating many rows can attribute a
    failure to its own row and keep inspecting the rest.
    """
    row_id = int(raw.id)
    # ``object_key`` is a HashedLookup digest. Keep the bytes surface
    # stable for diagnostics and raw mirror consumers.
    _raw_ok = raw.object_key
    object_key = _raw_ok.encode(UTF_8_ENCODING) if isinstance(_raw_ok, str) else bytes(_raw_ok)
    classification_str = str(raw.classification)
    schema_version = int(raw.schema_version)
    written_at = raw.written_at
    payload_wire = bytes(raw.payload)
    try:
        classification = SensitivityClass(classification_str)
    except ValueError:
        return SecureObjectUnreadable(
            namespace=namespace,
            row_id=row_id,
            object_key=object_key,
            classification=classification_str,
            schema_version=schema_version,
            written_at=written_at,
            reason=f"unknown classification {classification_str!r}",
        )
    if classification is not expected_class:
        return SecureObjectUnreadable(
            namespace=namespace,
            row_id=row_id,
            object_key=object_key,
            classification=classification_str,
            schema_version=schema_version,
            written_at=written_at,
            reason=f"classification {classification.value!r} does not match expected {expected_class.value!r}",
        )
    try:
        ensure_schema_version_readable(
            namespace=namespace,
            schema_version=schema_version,
            current_version=max_supported_version,
        )
    except EnvelopeVersionError as exc:
        return SecureObjectUnreadable(
            namespace=namespace,
            row_id=row_id,
            object_key=object_key,
            classification=classification_str,
            schema_version=schema_version,
            written_at=written_at,
            reason=resolve_error_message(exc),
        )
    try:
        enforce_registered_row_schema(
            namespace=namespace,
            schema_version=schema_version,
            definition=namespace_definition,
        )
    except EnvelopeVersionError as exc:
        return SecureObjectUnreadable(
            namespace=namespace,
            row_id=row_id,
            object_key=object_key,
            classification=classification_str,
            schema_version=schema_version,
            written_at=written_at,
            reason=resolve_error_message(exc),
        )
    try:
        payload_plain = decrypt_secure_object_payload(
            payload_wire,
            associated_data=secure_object_payload_aad(namespace, object_key, schema_version),
        )
    except DecryptionError as exc:
        return SecureObjectUnreadable(
            namespace=namespace,
            row_id=row_id,
            object_key=object_key,
            classification=classification_str,
            schema_version=schema_version,
            written_at=written_at,
            reason=str(exc),
        )
    if not verify_revision_self_consistency(
        namespace=namespace,
        object_key=object_key,
        schema_version=schema_version,
        written_at=written_at,
        revision_id=raw.revision_id,
        previous_revision_id=raw.previous_revision_id,
        payload_hash=raw.payload_hash,
        ciphertext_hash=raw.ciphertext_hash,
        previous_payload_hash=raw.previous_payload_hash,
    ):
        return SecureObjectUnreadable(
            namespace=namespace,
            row_id=row_id,
            object_key=object_key,
            classification=classification_str,
            schema_version=schema_version,
            written_at=written_at,
            reason="revision lineage self-consistency check failed",
        )
    if schema_version < max_supported_version:
        try:
            payload_plain = upgrade_secure_object_payload(
                payload_plain,
                namespace=namespace,
                from_version=schema_version,
                to_version=max_supported_version,
            )
        except Exception as exc:
            return SecureObjectUnreadable(
                namespace=namespace,
                row_id=row_id,
                object_key=object_key,
                classification=classification_str,
                schema_version=schema_version,
                written_at=written_at,
                reason=resolve_error_message(exc) if isinstance(exc, EnvelopeVersionError) else str(exc),
            )
    return SecureObjectRecord(
        namespace=namespace,
        object_key=object_key,
        classification=classification,
        schema_version=max_supported_version,
        written_at=written_at,
        payload=payload_plain,
    )
