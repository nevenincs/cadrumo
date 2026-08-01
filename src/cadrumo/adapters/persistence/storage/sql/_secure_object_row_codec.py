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
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime
from typing import Protocol, cast

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


class _SecureObjectListRawRow(Protocol):
    """Typed SQL projection consumed by the batch-list decode boundary."""

    id: int
    object_key: str | bytes
    classification: str
    schema_version: int
    written_at: datetime
    payload: bytes
    revision_id: str | None
    previous_revision_id: str | None
    payload_hash: str | None
    ciphertext_hash: str | None
    previous_payload_hash: str | None


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


def decode_secure_object_row(
    *,
    namespace: str,
    row_id: int,
    object_key: bytes,
    classification_str: str,
    schema_version: int,
    written_at: datetime,
    payload_wire: bytes,
    revision_id: object,
    previous_revision_id: str | None,
    payload_hash: str | None,
    ciphertext_hash: str | None,
    previous_payload_hash: str | None,
    expected_class: SensitivityClass,
    max_supported_version: int,
    namespace_definition: SecureObjectNamespaceDefinition | None,
    enforce_registered_row_schema: Callable[..., None],
) -> SecureObjectRecord:
    """Validate and decrypt one secure-object row, raising on every failure.

    The single decode pipeline behind both read surfaces. It always RAISES;
    choosing between propagating that failure and converting it to an
    unreadable row is the caller's policy, so the two surfaces cannot drift in
    WHAT they check or in WHICH ORDER, only in how they report.

    Order is part of the contract, and is deliberately integrity-before-crypto:

    1. classification is a known value, and is the one this namespace expects
    2. the stored schema version is readable, and registered for the namespace
    3. revision lineage is self-consistent
    4. the AEAD opens
    5. a below-current payload is chain-upgraded

    Step 3 runs before step 4 on purpose: a row whose stored lineage metadata
    already contradicts itself is refused without spending an AEAD open on it.
    That metadata is UNAUTHENTICATED until step 4 verifies the tag, so the
    pre-decrypt check is strictly refuse-only -- it can reject a row, and it can
    do nothing else. It never marks a row readable, never skips a later step,
    and never selects a decode branch, so hostile header metadata cannot buy an
    attacker anything beyond a refusal they could have caused anyway.

    Raises:
        ClassificationError: Unknown classification, or one that does not match
            the namespace's expected class.
        EnvelopeVersionError: Schema version unreadable, unregistered for the
            namespace, or an upgrade hop failure.
        SecureObjectUnreadableError: Revision lineage self-consistency failed.
        DecryptionError: The AEAD did not open.
    """
    try:
        classification = SensitivityClass(classification_str)
    except ValueError as exc:
        raise ClassificationError(
            context={
                "namespace": namespace,
                "classification": classification_str,
            },
            translated_message="errors.storage.namespace.unknown_classification",
        ) from exc
    if classification is not expected_class:
        raise ClassificationError(
            context={
                "namespace": namespace,
                "classification": classification.value,
                "expected": expected_class.value,
            },
            translated_message="errors.storage.namespace.classification_mismatch",
        )
    ensure_schema_version_readable(
        namespace=namespace,
        schema_version=schema_version,
        current_version=max_supported_version,
    )
    enforce_registered_row_schema(
        namespace=namespace,
        schema_version=schema_version,
        definition=namespace_definition,
    )
    if not verify_revision_self_consistency(
        namespace=namespace,
        object_key=object_key,
        schema_version=schema_version,
        written_at=written_at,
        revision_id=revision_id,
        previous_revision_id=previous_revision_id,
        payload_hash=payload_hash,
        ciphertext_hash=ciphertext_hash,
        previous_payload_hash=previous_payload_hash,
    ):
        _log.error(
            "secure_objects: revision lineage self-consistency failed for namespace=%s row id=%s",
            namespace,
            row_id,
        )
        raise SecureObjectUnreadableError(namespace, row_id)
    payload_plain = decrypt_secure_object_payload(
        payload_wire,
        associated_data=secure_object_payload_aad(namespace, object_key, schema_version),
    )
    if schema_version < max_supported_version:
        payload_plain = upgrade_secure_object_payload(
            payload_plain,
            namespace=namespace,
            from_version=schema_version,
            to_version=max_supported_version,
        )
    return SecureObjectRecord(
        namespace=namespace,
        object_key=object_key,
        classification=classification,
        schema_version=max_supported_version,
        written_at=written_at,
        payload=payload_plain,
        revision_id=str(revision_id),
    )


def _classification_reason(exc: ClassificationError) -> str:
    """Render a classification failure as the batch surface's diagnostic string.

    The batch reason stays a stable, structural English string rather than the
    error's translated message: it is a diagnostic field on a machine-readable
    unreadable-row record, not operator-facing prose, and callers match on its
    shape.
    """
    context = getattr(exc, "context", None) or {}
    classification = str(context.get("classification", ""))
    expected = context.get("expected")
    if expected is None:
        return f"unknown classification {classification!r}"
    return f"classification {classification!r} does not match expected {str(expected)!r}"


def secure_object_record_from_row(
    row: _orm.SecureObjectRow,
    *,
    expected_class: SensitivityClass,
    max_supported_version: int,
    namespace_definition: SecureObjectNamespaceDefinition | None = None,
    enforce_registered_row_schema: Callable[..., None],
) -> SecureObjectRecord:
    """Decode one ORM row, propagating the typed failure.

    Fail-closed policy: a caller loading a specific row wants the typed error,
    not a placeholder. Normalisation of the ORM row is the only thing this
    wrapper adds; every check lives in :func:`decode_secure_object_row`.
    """
    return decode_secure_object_row(
        namespace=row.namespace,
        row_id=int(row.id),
        object_key=bytes(row.object_key),
        classification_str=row.classification,
        schema_version=row.schema_version,
        written_at=row.written_at,
        payload_wire=bytes(row.payload),
        revision_id=row.revision_id,
        previous_revision_id=row.previous_revision_id,
        payload_hash=row.payload_hash,
        ciphertext_hash=row.ciphertext_hash,
        previous_payload_hash=row.previous_payload_hash,
        expected_class=expected_class,
        max_supported_version=max_supported_version,
        namespace_definition=namespace_definition,
        enforce_registered_row_schema=enforce_registered_row_schema,
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

    ``expected_class`` is the :class:`SensitivityClass` required for the
    namespace.

    Fault-isolated: every failure mode (unknown classification, classification
    mismatch, unreadable schema version, revision-lineage inconsistency,
    decrypt failure, upgrade failure) returns a
    :class:`~._secure_object_records.SecureObjectUnreadable` carrying the
    reason instead of raising, so a caller iterating many rows can attribute a
    failure to its own row and keep inspecting the rest.

    Fault isolation is the ONLY thing this wrapper adds to
    :func:`decode_secure_object_row`; the checks and their order live there, so
    the batch surface cannot validate a row differently from the single-row
    surface. Note ``SecureObjectUnreadableError`` subclasses ``DecryptionError``
    and so must be caught first.
    """
    # CAST-RATIONALE-SECURE-OBJECT-RAW-ROW: SQL row tuples are structurally validated by this codec.
    row = cast(_SecureObjectListRawRow, raw)
    row_id = int(row.id)
    # ``object_key`` is a HashedLookup digest. Keep the bytes surface
    # stable for diagnostics and raw mirror consumers.
    _raw_ok = row.object_key
    object_key = _raw_ok.encode(UTF_8_ENCODING) if isinstance(_raw_ok, str) else bytes(_raw_ok)
    classification_str = str(row.classification)
    schema_version = int(row.schema_version)
    written_at = row.written_at
    payload_wire = bytes(row.payload)

    def unreadable(reason: str) -> SecureObjectUnreadable:
        """Report this row as unreadable, carrying the identity every reason shares.

        Every failure mode below reports the SAME row identity and differs
        only in why it could not be read, so the seven shared fields are
        bound once here. Fault isolation is the point: a caller iterating
        many rows can attribute a failure to its own row and keep going.
        """
        return SecureObjectUnreadable(
            namespace=namespace,
            row_id=row_id,
            object_key=object_key,
            classification=classification_str,
            schema_version=schema_version,
            written_at=written_at,
            reason=reason,
        )

    try:
        return decode_secure_object_row(
            namespace=namespace,
            row_id=row_id,
            object_key=object_key,
            classification_str=classification_str,
            schema_version=schema_version,
            written_at=written_at,
            payload_wire=payload_wire,
            revision_id=row.revision_id,
            previous_revision_id=row.previous_revision_id,
            payload_hash=row.payload_hash,
            ciphertext_hash=row.ciphertext_hash,
            previous_payload_hash=row.previous_payload_hash,
            expected_class=expected_class,
            max_supported_version=max_supported_version,
            namespace_definition=namespace_definition,
            enforce_registered_row_schema=enforce_registered_row_schema,
        )
    except SecureObjectUnreadableError:
        return unreadable("revision lineage self-consistency check failed")
    except DecryptionError as exc:
        return unreadable(str(exc))
    except ClassificationError as exc:
        return unreadable(_classification_reason(exc))
    except EnvelopeVersionError as exc:
        return unreadable(resolve_error_message(exc))
    except Exception as exc:
        # An upgrade hop is namespace-supplied and may raise anything; a batch
        # scan must attribute that to its row rather than abort the whole scan.
        return unreadable(str(exc))
