"""Decryptability diagnostics for SQL secure-object persistence.

The three operations here -- quarantine, namespace counting, and per-row
enumeration -- differ in what they DO with an undecryptable row (move it,
count it, describe it) but agree exactly on how they DECIDE one:
:func:`probe_row_decryptability` is that single decision. Keeping it in one
place means an AAD change or a new decryption-failure mode cannot be applied
to two of the three surfaces and missed on the third.
"""

from __future__ import annotations

from collections.abc import Iterator
from logging import Logger
from typing import NamedTuple, Protocol, cast

from sqlalchemy import Engine, bindparam, text

from ..crypto.encrypted_columns import decrypt_secure_object_payload, secure_object_payload_aad
from ..errors import DecryptionError
from . import orm as _orm
from ._secure_object_records import SecureObjectDecryptabilityRow, SecureObjectNamespaceIntegrity
from ._secure_object_schema import database_bytes, ensure_quarantine_table, quarantine_timestamp
from .session import session_scope


class _DecryptableRawRow(Protocol):
    """The row columns the decryptability decision reads.

    Every query behind the three integrity operations projects at least these
    three columns; the protocol pins that shared minimum.
    """

    object_key: str | bytes
    schema_version: int
    payload: bytes


class RowDecryptability(NamedTuple):
    """Whether one stored row decrypts, with the bytes the caller needs to act.

    ``object_key`` and ``payload`` are the normalised wire bytes: callers that
    quarantine a row re-insert exactly these, so the row that moves is the row
    that was probed. ``reason`` carries the decryption failure text and is
    ``None`` when ``readable`` is ``True``.
    """

    object_key: bytes
    payload: bytes
    readable: bool
    reason: str | None


def probe_row_decryptability(raw: object, *, namespace: str) -> RowDecryptability:
    """Decide whether one secure-object row decrypts under the current master key.

    The single decryptability decision behind quarantine, namespace counting,
    and per-row enumeration. Normalises the row's bytes through
    :func:`~adapters.persistence.storage.sql._secure_object_schema.database_bytes`
    (SQLite returns ``bytes``, ``memoryview``, or ``str`` depending on the
    driver and query form), rebuilds the row-identity AAD, and attempts the
    AEAD open.

    Only :class:`~adapters.persistence.storage.errors.DecryptionError` is
    treated as "unreadable": a row whose bytes are structurally impossible to
    normalise is a programming or schema fault and propagates.
    """
    # CAST-RATIONALE-SECURE-OBJECT-INTEGRITY-ROW: SQL row tuples are structurally
    # validated by this probe's own column reads.
    row = cast(_DecryptableRawRow, raw)
    object_key = database_bytes(row.object_key)
    payload = database_bytes(row.payload)
    schema_version = int(row.schema_version)
    try:
        decrypt_secure_object_payload(
            payload,
            associated_data=secure_object_payload_aad(namespace, object_key, schema_version),
        )
    except DecryptionError as exc:
        return RowDecryptability(object_key=object_key, payload=payload, readable=False, reason=str(exc))
    return RowDecryptability(object_key=object_key, payload=payload, readable=True, reason=None)


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
                probe = probe_row_decryptability(raw, namespace=namespace)
                payload_bytes = probe.payload
                object_key_bytes = probe.object_key
                if not probe.readable:
                    logger.debug(
                        "secure_objects: quarantining unreadable row id=%s namespace=%s (%s)",
                        int(raw.id),
                        namespace,
                        probe.reason,
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
        probe = probe_row_decryptability(raw, namespace=namespace)
        if probe.readable:
            readable += 1
        else:
            logger.debug(
                "secure_objects probe: unreadable row in namespace=%s (%s)",
                namespace,
                probe.reason,
            )
            unreadable += 1
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
        probe = probe_row_decryptability(raw, namespace=namespace)
        yield SecureObjectDecryptabilityRow(
            namespace=namespace,
            row_id=int(raw.id),
            object_key=probe.object_key,
            classification=str(raw.classification),
            schema_version=int(raw.schema_version),
            written_at=raw.written_at,
            readable=probe.readable,
            reason=probe.reason,
        )
