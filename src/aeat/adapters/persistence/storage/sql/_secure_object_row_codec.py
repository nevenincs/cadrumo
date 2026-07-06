from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime

from sqlalchemy import bindparam, text, update
from sqlalchemy.orm import Session

from .....core.classification import SensitivityClass
from .....core.hashing import sha256_hex
from .....core.logging import get_logger
from .._namespace_registry import SecureObjectNamespaceDefinition
from ..crypto import decrypt_secure_object_payload, secure_object_payload_aad
from ..errors import ClassificationError, EnvelopeVersionError, SecureObjectUnreadableError
from . import _orm
from ._secure_object_crypto import derive_revision_id, verify_revision_self_consistency
from ._secure_object_records import SecureObjectRecord
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
    if row.schema_version != max_supported_version:
        raise EnvelopeVersionError(
            context={
                "namespace": row.namespace,
                "schema_version": row.schema_version,
                "expected": max_supported_version,
            },
            translated_message="errors.storage.namespace.schema_mismatch",
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
    return SecureObjectRecord(
        namespace=row.namespace,
        object_key=bytes(row.object_key),
        classification=classification,
        schema_version=row.schema_version,
        written_at=row.written_at,
        payload=payload_plain,
    )
