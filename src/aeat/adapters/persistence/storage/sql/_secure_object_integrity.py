"""Decryptability diagnostics for SQL secure-object persistence."""

from __future__ import annotations

from collections.abc import Iterator
from logging import Logger

from sqlalchemy import Engine, bindparam, text

from .....core.external_constants import UTF_8_ENCODING
from ..crypto._encrypted_columns import decrypt_secure_object_payload, secure_object_payload_aad
from ..errors import DecryptionError
from . import _orm
from ._secure_object_records import SecureObjectDecryptabilityRow, SecureObjectNamespaceIntegrity
from ._secure_object_schema import database_bytes, ensure_quarantine_table, quarantine_timestamp
from .session import session_scope


def quarantine_unreadable_rows(
    engine: Engine,
    *,
    logger: Logger,
) -> tuple[SecureObjectNamespaceIntegrity, ...]:
    """Move every undecryptable row into ``secure_objects_quarantine``.

    Returns a tuple of :class:`SecureObjectNamespaceIntegrity` records, one per namespace.
    """
    ensure_quarantine_table(engine)
    with session_scope(engine) as session:
        quarantined_at = quarantine_timestamp()
        namespaces = (
            session.execute(text("SELECT DISTINCT namespace FROM secure_objects ORDER BY namespace")).scalars().all()
        )
        per_namespace: list[SecureObjectNamespaceIntegrity] = []
        for namespace in namespaces:
            rows = session.execute(
                text(
                    "SELECT id, object_key, classification, schema_version, written_at, "
                    "revision_id, previous_revision_id, revision_ancestor_ids, "
                    "previous_payload_hash, payload_hash, "
                    "ciphertext_hash, revision_written_at, write_provenance, source_event_id, "
                    "conflict_policy, payload "
                    "FROM secure_objects WHERE namespace = :namespace",
                ).bindparams(bindparam("namespace", value=namespace)),
            ).all()
            quarantined = 0
            retained = 0
            for raw in rows:
                payload_bytes = raw.payload if isinstance(raw.payload, bytes) else bytes(raw.payload)
                object_key_value = (
                    raw.object_key
                    if isinstance(raw.object_key, bytes | bytearray | memoryview)
                    else str(raw.object_key).encode(UTF_8_ENCODING)
                )
                object_key_bytes = bytes(object_key_value)
                try:
                    decrypt_secure_object_payload(
                        payload_bytes,
                        associated_data=secure_object_payload_aad(
                            namespace,
                            object_key_bytes,
                            int(raw.schema_version),
                        ),
                    )
                except DecryptionError as exc:
                    logger.debug(
                        "secure_objects: quarantining unreadable row id=%s namespace=%s (%s)",
                        int(raw.id),
                        namespace,
                        exc,
                    )
                    session.execute(
                        text(
                            "INSERT INTO secure_objects_quarantine "
                            "(source_id, namespace, object_key, classification, schema_version, "
                            " written_at, revision_id, previous_revision_id, previous_payload_hash, "
                            " revision_ancestor_ids, payload_hash, ciphertext_hash, "
                            " revision_written_at, write_provenance, "
                            " source_event_id, conflict_policy, payload, quarantined_at) "
                            "VALUES (:source_id, :namespace, :object_key, :classification, "
                            "        :schema_version, :written_at, :revision_id, "
                            "        :previous_revision_id, :previous_payload_hash, "
                            "        :revision_ancestor_ids, :payload_hash, "
                            "        :ciphertext_hash, :revision_written_at, :write_provenance, "
                            "        :source_event_id, :conflict_policy, :payload, :quarantined_at)",
                        ),
                        {
                            "source_id": int(raw.id),
                            "namespace": namespace,
                            "object_key": object_key_bytes,
                            "classification": str(raw.classification),
                            "schema_version": int(raw.schema_version),
                            "written_at": raw.written_at,
                            "revision_id": raw.revision_id,
                            "previous_revision_id": raw.previous_revision_id,
                            "revision_ancestor_ids": raw.revision_ancestor_ids,
                            "previous_payload_hash": raw.previous_payload_hash,
                            "payload_hash": raw.payload_hash,
                            "ciphertext_hash": raw.ciphertext_hash,
                            "revision_written_at": raw.revision_written_at,
                            "write_provenance": raw.write_provenance,
                            "source_event_id": raw.source_event_id,
                            "conflict_policy": raw.conflict_policy,
                            "payload": payload_bytes,
                            "quarantined_at": quarantined_at,
                        },
                    )
                    session.execute(
                        text("DELETE FROM secure_objects WHERE id = :id"),
                        {"id": int(raw.id)},
                    )
                    quarantined += 1
                else:
                    retained += 1
            per_namespace.append(
                SecureObjectNamespaceIntegrity(
                    namespace=namespace,
                    readable=retained,
                    unreadable=quarantined,
                ),
            )
    return tuple(per_namespace)


def probe_namespace_integrity(
    engine: Engine,
    namespace: str,
    *,
    logger: Logger,
) -> SecureObjectNamespaceIntegrity:
    """Count decryptable and undecryptable rows in ``namespace``.

    Returns a :class:`SecureObjectNamespaceIntegrity` for the given namespace.
    """
    readable = 0
    unreadable = 0
    with session_scope(engine) as session:
        stmt = text(
            "SELECT object_key, schema_version, payload FROM secure_objects WHERE namespace = :namespace",
        ).bindparams(
            bindparam("namespace", value=namespace),
        )
        rows = session.execute(stmt).all()
    for raw in rows:
        try:
            decrypt_secure_object_payload(
                bytes(raw.payload),
                associated_data=secure_object_payload_aad(
                    namespace,
                    bytes(raw.object_key),
                    int(raw.schema_version),
                ),
            )
        except DecryptionError as exc:
            logger.debug(
                "secure_objects probe: unreadable row in namespace=%s (%s)",
                namespace,
                exc,
            )
            unreadable += 1
        else:
            readable += 1
    return SecureObjectNamespaceIntegrity(
        namespace=namespace,
        readable=readable,
        unreadable=unreadable,
    )


def iter_namespace_decryptability(
    engine: Engine,
    namespace: str,
) -> Iterator[SecureObjectDecryptabilityRow]:
    """Yield :class:`SecureObjectDecryptabilityRow` records for one namespace."""
    with session_scope(engine) as session:
        stmt = (
            text(
                "SELECT id, object_key, classification, schema_version, written_at, payload "
                "FROM secure_objects WHERE namespace = :namespace "
                "ORDER BY object_key",
            )
            .bindparams(bindparam("namespace", value=namespace))
            .columns(
                id=_orm.SecureObjectRow.__table__.c.id.type,
                object_key=_orm.SecureObjectRow.__table__.c.object_key.type,
                classification=_orm.SecureObjectRow.__table__.c.classification.type,
                schema_version=_orm.SecureObjectRow.__table__.c.schema_version.type,
                written_at=_orm.SecureObjectRow.__table__.c.written_at.type,
            )
        )
        rows = session.execute(stmt).all()
    for raw in rows:
        object_key_value = database_bytes(raw.object_key)
        payload_value = database_bytes(raw.payload)
        try:
            decrypt_secure_object_payload(
                payload_value,
                associated_data=secure_object_payload_aad(
                    namespace,
                    object_key_value,
                    int(raw.schema_version),
                ),
            )
        except DecryptionError as exc:
            yield SecureObjectDecryptabilityRow(
                namespace=namespace,
                row_id=int(raw.id),
                object_key=object_key_value,
                classification=str(raw.classification),
                schema_version=int(raw.schema_version),
                written_at=raw.written_at,
                readable=False,
                reason=str(exc),
            )
        else:
            yield SecureObjectDecryptabilityRow(
                namespace=namespace,
                row_id=int(raw.id),
                object_key=object_key_value,
                classification=str(raw.classification),
                schema_version=int(raw.schema_version),
                written_at=raw.written_at,
                readable=True,
            )
