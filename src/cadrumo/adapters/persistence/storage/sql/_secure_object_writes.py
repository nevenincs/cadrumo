"""Encrypted secure-object write and revision-lineage implementation."""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import datetime
from typing import Any, NamedTuple, Protocol, cast

from sqlalchemy import Table, bindparam, delete, insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .....core.classification.policies import SensitivityClass
from .....core.hashing import sha256_hex
from .....core.i18n import tr
from .....core.secure_object_write import (
    ABSENT_SECURE_OBJECT_REVISION_ID,
    DEFAULT_WRITE_PROVENANCE,
    SecureObjectWrite,
)
from .....core.time.utc import validate_utc_aware
from ..crypto.encrypted_columns import (
    encrypt_secure_object_payload,
    secure_object_key_digest,
    secure_object_payload_aad,
)
from ..errors import RepositoryError, SecureObjectRevisionConflictError, StorageValidationError
from ._orm import SecureObjectRow
from ._secure_object_crypto import derive_revision_id
from ._secure_object_records import SecureObjectDeletion
from .session import session_scope

_DEFAULT_WRITE_PROVENANCE = DEFAULT_WRITE_PROVENANCE
_DEFAULT_CONFLICT_POLICY = "last-write-wins"
_CAS_CONFLICT_POLICY = "compare-and-swap"

#: Digests per ``IN (...)`` slice of a batched object-key read (previous-write
#: metadata, batch existence). Well under SQLite's bound-variable ceiling, and
#: large enough that a 20k-row batch costs ~40 reads instead of 20k.
_OBJECT_KEY_SELECT_CHUNK = 500


def _secure_objects_table() -> Table:
    """Return the ``secure_objects`` :class:`~sqlalchemy.Table` for Core DML.

    ``__table__`` is a ``Table`` at runtime, but the SQLAlchemy stubs widen
    its declared type to ``FromClause``, which the ``insert``/``update``
    constructors do not accept. The assertion narrows it for the checker.
    """
    table = SecureObjectRow.__table__
    assert isinstance(table, Table)
    return table


class _PreviousRowMetadata(NamedTuple):
    """Revision lineage of the stored row a write supersedes."""

    row_id: int
    revision_id: str | None
    revision_ancestor_ids: tuple[str, ...]
    payload_hash: str | None


class _PendingSecureObjectWrite(NamedTuple):
    """One normalised write: UTC-validated instant plus its pre-computed key digest."""

    namespace: str
    object_key_digest: bytes
    classification: SensitivityClass
    schema_version: int
    written_at: datetime
    payload: bytes
    write_provenance: str
    source_event_id: str | None
    expected_revision_id: str | None


class _RowcountResult(Protocol):
    """Structural result shape for SQLAlchemy DML rowcount checks."""

    rowcount: int


class SecureObjectWriteOperations:
    """Cohesive encrypted write, batch-DML, and revision-lineage operations.

    The concrete repository owns construction, registration policy, session
    freshness, and read decoding. This sibling owns the one write funnel that
    every public mutation reaches, keeping encryption, lineage, and guarded
    DML together without exposing another repository surface.
    """

    def save(
        self,
        *,
        namespace: str,
        object_key: str,
        classification: SensitivityClass,
        schema_version: int,
        written_at: datetime,
        payload: bytes,
        write_provenance: str = _DEFAULT_WRITE_PROVENANCE,
        source_event_id: str | None = None,
        expected_revision_id: str | None = None,
    ) -> None:
        """Encrypt and upsert one byte payload keyed by a natural string id.

        The natural ``object_key`` is HMAC-digested at the column
        boundary. To upsert against a pre-computed digest (e.g. when
        restoring an archive bundle whose natural key was lost in the
        original HMAC), use
        :meth:`~adapters.persistence.storage.SecureObjectRepository.save_with_raw_key`
        instead.

        Args:
            namespace: The storage namespace to write into.
            object_key: Natural string identifier for this record. Digested
                via HMAC before being stored on disk.
            classification: The
                :class:`~adapters.persistence.storage.SensitivityClass`
                for this record.
            schema_version: Envelope schema version to stamp on the row.
            written_at: UTC-aware write timestamp. A naive or
                offset-bearing instant is refused: the SQLite column drops
                ``tzinfo``, so it would not recompute the revision it was
                stored under.
            payload: Plaintext envelope bytes. Encrypted at the column boundary.
            write_provenance: Human-readable string identifying the write origin.
            source_event_id: Optional opaque domain-event identifier for audit trails.
            expected_revision_id: Optional optimistic-concurrency guard.
        """
        self._check_session_freshness(namespace)
        self._save_internal(
            namespace=namespace,
            key=object_key,
            classification=classification,
            schema_version=schema_version,
            written_at=written_at,
            payload=payload,
            write_provenance=write_provenance,
            source_event_id=source_event_id,
            expected_revision_id=expected_revision_id,
        )

    def save_many(self, writes: tuple[SecureObjectWrite, ...]) -> None:
        """Encrypt and upsert several payloads in one SQL unit of work."""
        self.apply_batch(writes)

    def namespace_payload_hashes(self, namespace: str) -> dict[bytes, str | None]:
        """Return ``{object_key_digest: payload_hash}`` for every row in ``namespace``.

        A decryption-free scan of the ``object_key`` (HMAC digest) and
        ``payload_hash`` columns, for diff-based writers that persist a
        namespace as one row per logical entry: an entry whose freshly-serialised
        ``payload_hash`` matches the stored value is unchanged and need not be
        rewritten. The digest is the same value
        :func:`secure_object_key_digest` produces for the entry's natural key,
        so a caller compares ``secure_object_key_digest(key)`` against these
        keys without decrypting anything.
        """
        self._check_session_freshness(namespace)
        with session_scope(self._engine) as session:
            rows = session.execute(
                select(
                    SecureObjectRow.object_key,
                    SecureObjectRow.payload_hash,
                ).where(SecureObjectRow.namespace == namespace),
            ).all()
        hashes: dict[bytes, str | None] = {}
        for object_key, payload_hash in rows:
            digest = object_key if isinstance(object_key, bytes) else bytes(object_key)
            hashes[digest] = payload_hash
        return hashes

    def apply_batch(
        self,
        writes: tuple[SecureObjectWrite, ...],
        deletions: tuple[SecureObjectDeletion, ...] = (),
    ) -> None:
        """Atomically upsert ``writes`` and remove ``deletions`` in one unit of work.

        The single ``session_scope`` transaction commits every upsert and every
        digest-addressed deletion together, so a diff-based per-row writer (e.g.
        the transaction catalogue) keeps the all-or-nothing guarantee the
        whole-blob ``save`` had — including when the same call must also commit
        sibling-catalogue writes (bucket-event history, invoices) passed in
        ``writes``. A crash mid-batch rolls the whole unit back.

        Deletions are addressed by raw HMAC digest (see
        :class:`SecureObjectDeletion`); the digest passes straight through the
        ``HashedLookup`` column comparison without re-hashing.
        """
        if not writes and not deletions:
            return
        for write in writes:
            self._enforce_registered_write_policy(
                namespace=write.namespace,
                classification=write.classification,
                schema_version=write.schema_version,
                object_key=write.object_key,
            )
        for removal in deletions:
            self._registered_namespace_definition(removal.namespace)
        self._check_session_freshness()
        pending = tuple(
            self._pending_write(
                namespace=write.namespace,
                key=write.object_key,
                classification=write.classification,
                schema_version=write.schema_version,
                written_at=write.written_at,
                payload=write.payload,
                write_provenance=write.write_provenance,
                source_event_id=write.source_event_id,
                expected_revision_id=write.expected_revision_id,
            )
            for write in writes
        )
        with session_scope(self._engine) as session:
            self._write_pending_in_session(session, pending)
            for removal in deletions:
                session.execute(
                    delete(SecureObjectRow).where(
                        SecureObjectRow.namespace == removal.namespace,
                        SecureObjectRow.object_key == removal.hashed_object_key,
                    ),
                )

    def save_with_raw_key(
        self,
        *,
        namespace: str,
        hashed_object_key: bytes,
        classification: SensitivityClass,
        schema_version: int,
        written_at: datetime,
        payload: bytes,
        write_provenance: str = _DEFAULT_WRITE_PROVENANCE,
        source_event_id: str | None = None,
        expected_revision_id: str | None = None,
    ) -> None:
        """Encrypt and upsert one byte payload keyed by a pre-computed digest.

        The 32-byte ``hashed_object_key`` is passed straight through
        the :class:`~adapters.persistence.storage.HashedLookup` column
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
                :class:`~adapters.persistence.storage.SensitivityClass`
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

    def _save_internal(
        self,
        *,
        namespace: str,
        key: str | bytes,
        classification: SensitivityClass,
        schema_version: int,
        written_at: datetime,
        payload: bytes,
        write_provenance: str,
        source_event_id: str | None,
        expected_revision_id: str | None,
    ) -> None:
        """Shared secure-object upsert implementation.

        Backs
        :meth:`~adapters.persistence.storage.SecureObjectRepository.save`
        and
        :meth:`~adapters.persistence.storage.SecureObjectRepository.save_with_raw_key`.
        """
        self._enforce_registered_write_policy(
            namespace=namespace,
            classification=classification,
            schema_version=schema_version,
            # ``save`` passes the natural string key; ``save_with_raw_key``
            # passes an already-digested ``bytes`` key with no natural form
            # left to check against the namespace's declared grammar.
            object_key=key if isinstance(key, str) else None,
        )
        pending = self._pending_write(
            namespace=namespace,
            key=key,
            classification=classification,
            schema_version=schema_version,
            written_at=written_at,
            payload=payload,
            write_provenance=write_provenance,
            source_event_id=source_event_id,
            expected_revision_id=expected_revision_id,
        )
        with session_scope(self._engine) as session:
            self._write_pending_in_session(session, (pending,))

    def _pending_write(
        self,
        *,
        namespace: str,
        key: str | bytes,
        classification: SensitivityClass,
        schema_version: int,
        written_at: datetime,
        payload: bytes,
        write_provenance: str,
        source_event_id: str | None,
        expected_revision_id: str | None,
    ) -> _PendingSecureObjectWrite:
        """Normalise one write for the shared funnel.

        ``written_at`` is gated here rather than only on the
        ``SecureObjectWrite`` DTO because the direct ``save`` and
        ``save_with_raw_key`` boundaries take a bare ``datetime`` and never
        construct that model. An offset-bearing instant loses its ``tzinfo``
        in the SQLite column while the revision id was derived from the UTC
        instant, so the row would commit and then fail its own read-time
        self-consistency gate for good; refusing it keeps write and read
        deriving one revision from one spelling.

        The natural key is digested once here; the digest is what the
        ``object_key`` HashedLookup column persists, what the previous-row
        read matches on, and what the AEAD associated data binds, so all
        three surfaces provably share one spelling of the row identity.
        """
        return _PendingSecureObjectWrite(
            namespace=namespace,
            object_key_digest=secure_object_key_digest(key),
            classification=classification,
            schema_version=schema_version,
            written_at=validate_utc_aware(written_at),
            payload=payload,
            write_provenance=write_provenance,
            source_event_id=source_event_id,
            expected_revision_id=expected_revision_id,
        )

    def _write_pending_in_session(
        self,
        session: Session,
        pending: Sequence[_PendingSecureObjectWrite],
    ) -> None:
        """Single write funnel for save, save_many, apply_batch, and save_with_raw_key.

        Writes execute in caller order with set-based SQL: one previous-
        metadata read per namespace slice, then one ``INSERT`` executemany for
        rows the read proved absent and one lineage-guarded ``UPDATE``
        executemany for rows it proved present. Revision lineage is derived in
        Python from the plaintext and ciphertext this funnel already holds,
        so no per-row round-trip remains.

        A batch that writes the same ``(namespace, object_key)`` twice is
        split at the repeat, so the later write's previous-metadata read runs
        after the earlier write flushed inside the same transaction and the
        revision chain links write to write exactly as sequential saves would.
        """
        chunk: list[_PendingSecureObjectWrite] = []
        seen: set[tuple[str, bytes]] = set()
        for write in pending:
            identity = (write.namespace, write.object_key_digest)
            if identity in seen:
                self._flush_pending_chunk(session, chunk)
                chunk = []
                seen = set()
            chunk.append(write)
            seen.add(identity)
        self._flush_pending_chunk(session, chunk)

    def _flush_pending_chunk(
        self,
        session: Session,
        chunk: Sequence[_PendingSecureObjectWrite],
    ) -> None:
        """Resolve lineage for one duplicate-free chunk and execute its DML."""
        if not chunk:
            return
        previous = self._load_previous_metadata_for_chunk(session, chunk)
        insert_rows: list[dict[str, object]] = []
        update_rows: list[dict[str, object]] = []
        for write in chunk:
            prior = previous.get((write.namespace, write.object_key_digest))
            self._assert_expected_revision(write, prior)
            # Encrypt the payload explicitly, binding the row identity into
            # the AEAD associated data so the ciphertext is valid only for
            # this exact (namespace, object_key, schema_version) row.
            payload_hash = sha256_hex(write.payload)
            payload_wire = encrypt_secure_object_payload(
                write.payload,
                associated_data=secure_object_payload_aad(
                    write.namespace,
                    write.object_key_digest,
                    write.schema_version,
                ),
            )
            ciphertext_hash = sha256_hex(payload_wire)
            previous_revision_id = prior.revision_id if prior is not None else None
            previous_payload_hash = prior.payload_hash if prior is not None else None
            revision_id = derive_revision_id(
                namespace=write.namespace,
                object_key=write.object_key_digest,
                schema_version=write.schema_version,
                written_at=write.written_at,
                payload_hash=payload_hash,
                ciphertext_hash=ciphertext_hash,
                previous_revision_id=previous_revision_id,
                previous_payload_hash=previous_payload_hash,
            )
            revision_ancestor_ids = self._build_revision_ancestor_ids(
                previous_revision_id,
                prior.revision_ancestor_ids if prior is not None else (),
            )
            values: dict[str, object] = {
                "namespace": write.namespace,
                "classification": write.classification.value,
                "schema_version": write.schema_version,
                "written_at": write.written_at,
                "payload": payload_wire,
                "revision_id": revision_id,
                "previous_revision_id": previous_revision_id,
                "revision_ancestor_ids": json.dumps(revision_ancestor_ids),
                "previous_payload_hash": previous_payload_hash,
                "payload_hash": payload_hash,
                "ciphertext_hash": ciphertext_hash,
                "revision_written_at": write.written_at,
                "write_provenance": write.write_provenance,
                "source_event_id": write.source_event_id,
                "conflict_policy": (
                    _CAS_CONFLICT_POLICY if write.expected_revision_id is not None else _DEFAULT_CONFLICT_POLICY
                ),
            }
            if prior is None:
                insert_rows.append({**values, "object_key": write.object_key_digest})
            else:
                update_rows.append(
                    {
                        "b_id": prior.row_id,
                        "b_guard_revision_id": previous_revision_id,
                        **{f"v_{name}": value for name, value in values.items()},
                    },
                )
        self._execute_insert_rows(session, insert_rows)
        self._execute_update_rows(session, update_rows)

    def _load_previous_metadata_for_chunk(
        self,
        session: Session,
        chunk: Sequence[_PendingSecureObjectWrite],
    ) -> dict[tuple[str, bytes], _PreviousRowMetadata]:
        """Read the revision lineage of every row this chunk supersedes.

        One indexed ``IN (...)`` read per namespace slice replaces the two
        SELECTs the retired per-row funnel issued per write. The stored
        plaintext hash is always present from birth; the payload column is
        AEAD wire bytes, so there is no plaintext to fall back on (and
        hashing the ciphertext would be meaningless).
        """
        by_namespace: dict[str, list[bytes]] = {}
        for write in chunk:
            by_namespace.setdefault(write.namespace, []).append(write.object_key_digest)
        previous: dict[tuple[str, bytes], _PreviousRowMetadata] = {}
        for namespace, digests in by_namespace.items():
            for start in range(0, len(digests), _OBJECT_KEY_SELECT_CHUNK):
                rows = session.execute(
                    select(
                        SecureObjectRow.id,
                        SecureObjectRow.object_key,
                        SecureObjectRow.revision_id,
                        SecureObjectRow.revision_ancestor_ids,
                        SecureObjectRow.payload_hash,
                    ).where(
                        SecureObjectRow.namespace == namespace,
                        SecureObjectRow.object_key.in_(
                            digests[start : start + _OBJECT_KEY_SELECT_CHUNK],
                        ),
                    ),
                ).all()
                for row in rows:
                    digest = row.object_key if isinstance(row.object_key, bytes) else bytes(row.object_key)
                    previous[(namespace, digest)] = _PreviousRowMetadata(
                        row_id=int(row.id),
                        revision_id=row.revision_id,
                        revision_ancestor_ids=self._parse_revision_ancestor_ids(row.revision_ancestor_ids),
                        payload_hash=row.payload_hash,
                    )
        return previous

    def _assert_expected_revision(
        self,
        write: _PendingSecureObjectWrite,
        prior: _PreviousRowMetadata | None,
    ) -> None:
        """Refuse a compare-and-swap write whose expectation the stored row breaks."""
        expected = write.expected_revision_id
        if expected is None:
            return
        if prior is None:
            if expected != ABSENT_SECURE_OBJECT_REVISION_ID:
                raise self._revision_conflict(
                    namespace=write.namespace,
                    expected_revision_id=expected,
                    current_revision_id=None,
                )
            return
        if expected == ABSENT_SECURE_OBJECT_REVISION_ID or expected != prior.revision_id:
            raise self._revision_conflict(
                namespace=write.namespace,
                expected_revision_id=expected,
                current_revision_id=prior.revision_id,
            )

    def _execute_insert_rows(
        self,
        session: Session,
        insert_rows: Sequence[dict[str, object]],
    ) -> None:
        """Insert every row the previous-metadata read proved absent.

        A UNIQUE violation here means the row appeared after that read — a
        concurrent writer on the same bucket. A single-row batch attributes
        it exactly as the retired per-row funnel did (a compare-and-swap
        insert becomes a revision conflict); a multi-row batch cannot name
        the colliding row after the failed statement poisons the session, so
        it reports every namespace the batch touched and the whole unit rolls
        back re-runnable.
        """
        if not insert_rows:
            return
        try:
            session.execute(insert(_secure_objects_table()), list(insert_rows))
        except IntegrityError as exc:
            if len(insert_rows) == 1:
                # CAST-RATIONALE-SECURE-OBJECTS-INSERT-ROW-SHAPE: this funnel
                # built the row dicts above; the two fields read back here are
                # always present with these types.
                namespace = cast(str, insert_rows[0]["namespace"])
                conflict_policy = insert_rows[0]["conflict_policy"]
                if conflict_policy == _CAS_CONFLICT_POLICY:
                    raise self._revision_conflict(
                        namespace=namespace,
                        expected_revision_id=ABSENT_SECURE_OBJECT_REVISION_ID,
                        current_revision_id=None,
                    ) from exc
                namespaces = namespace
            else:
                # CAST-RATIONALE-SECURE-OBJECTS-NAMESPACE-STR: insert_rows is this
                # method's own batch-constructed dict[str, object]; "namespace" is
                # always written as str by the caller that built the row.
                namespaces = ", ".join(sorted({cast(str, row["namespace"]) for row in insert_rows}))
            raise RepositoryError(
                context={
                    "namespace": namespaces,
                    "error_type": type(exc.orig).__name__,
                },
                translated_message="errors.fail.fail_storage_secure_object_upsert",
            ) from exc

    def _execute_update_rows(
        self,
        session: Session,
        update_rows: Sequence[dict[str, object]],
    ) -> None:
        """Update every superseded row, guarded on the lineage the batch read.

        Each update matches only while the stored ``revision_id`` still equals
        the one this batch derived its lineage from, so a concurrent writer
        landing between the read and this statement can never be silently
        orphaned from the revision chain — the guarded update misses, the
        shortfall is detected, and the whole unit rolls back with a revision
        conflict naming the row that moved. This is strictly stronger than
        the retired per-row funnel, which only guarded compare-and-swap
        writes and stamped last-write-wins lineage from a potentially stale
        read.
        """
        if not update_rows:
            return
        guarded = [row for row in update_rows if row["b_guard_revision_id"] is not None]
        # A stored row without a revision id cannot be lineage-guarded; the
        # write path has stamped every row from birth, so such a row is
        # pre-existing corruption the read path refuses. Overwriting it keyed
        # on id alone matches the retired funnel's behaviour.
        unguarded = [row for row in update_rows if row["b_guard_revision_id"] is None]
        if guarded:
            self._execute_guarded_update_rows(session, guarded, update_rows)
        if unguarded:
            self._execute_unguarded_update_rows(session, unguarded, update_rows)

    @staticmethod
    def _update_row_values(rows: Sequence[dict[str, object]]) -> dict[str, Any]:
        value_names = [name.removeprefix("v_") for name in rows[0] if name.startswith("v_")]
        return {name: bindparam(f"v_{name}") for name in value_names}

    def _execute_guarded_update_rows(
        self,
        session: Session,
        guarded: Sequence[dict[str, object]],
        all_rows: Sequence[dict[str, object]],
    ) -> None:
        table = _secure_objects_table()
        stmt = (
            update(table)
            .where(
                table.c.id == bindparam("b_id"),
                table.c.revision_id == bindparam("b_guard_revision_id"),
            )
            .values(**self._update_row_values(all_rows))
        )
        try:
            # CAST-RATIONALE-SECURE-OBJECTS-SQLALCHEMY-CURSOR-UPDATE:
            # SQLAlchemy types ``Session.execute()`` as ``Result[Any]``; a DML
            # UPDATE always yields a rowcount-bearing result, and pysqlite
            # accumulates executemany rowcounts across parameter sets.
            result = cast(_RowcountResult, session.execute(stmt, guarded))
        except IntegrityError as exc:
            raise self._update_integrity_error(guarded, exc) from exc
        if result.rowcount != len(guarded):
            self._raise_stale_guarded_update(session, guarded)

    def _execute_unguarded_update_rows(
        self,
        session: Session,
        unguarded: Sequence[dict[str, object]],
        all_rows: Sequence[dict[str, object]],
    ) -> None:
        table = _secure_objects_table()
        stmt = update(table).where(table.c.id == bindparam("b_id")).values(**self._update_row_values(all_rows))
        try:
            session.execute(stmt, unguarded)
        except IntegrityError as exc:
            raise self._update_integrity_error(unguarded, exc) from exc

    def _update_integrity_error(
        self,
        rows: Sequence[dict[str, object]],
        exc: IntegrityError,
    ) -> RepositoryError:
        """Translate an UPDATE-path IntegrityError into the shared repository error.

        Mirrors :meth:`_execute_insert_rows`'s translation so both DML halves
        of the batch funnel uphold the same ``RepositoryError`` contract on a
        SQL integrity failure, rather than leaking a raw
        :exc:`~sqlalchemy.exc.IntegrityError` to the caller.
        """
        # CAST-RATIONALE-SECURE-OBJECTS-UPDATE-NAMESPACE-STR: rows is this
        # method's own batch-constructed dict[str, object]; "v_namespace" is
        # always written as str by the caller that built the row.
        namespaces = ", ".join(sorted({cast(str, row["v_namespace"]) for row in rows}))
        return RepositoryError(
            context={
                "namespace": namespaces,
                "error_type": type(exc.orig).__name__,
            },
            translated_message="errors.fail.fail_storage_secure_object_upsert",
        )

    def _raise_stale_guarded_update(
        self,
        session: Session,
        guarded: Sequence[dict[str, object]],
    ) -> None:
        """Name the row whose stored revision moved under a guarded update."""
        # CAST-RATIONALE-SECURE-OBJECTS-ROW-ID-INT: guarded is this method's own
        # batch-constructed dict[str, object]; "b_id" is always the row's int
        # primary key, stamped by the same funnel that built the row.
        row_ids = [cast(int, row["b_id"]) for row in guarded]
        stored: dict[int, str | None] = {}
        for stored_id, stored_revision_id in session.execute(
            select(SecureObjectRow.id, SecureObjectRow.revision_id).where(
                SecureObjectRow.id.in_(row_ids),
            ),
        ):
            stored[int(stored_id)] = stored_revision_id
        for row in guarded:
            # CAST-RATIONALE-SECURE-OBJECTS-ROW-ID-INT: see the identical cast above.
            row_id = cast(int, row["b_id"])
            current = stored.get(row_id)
            if current != row["v_revision_id"]:
                # CAST-RATIONALE-SECURE-OBJECTS-ROW-STR-FIELD: guarded rows are this
                # method's own batch-constructed dict[str, object]; "v_namespace" and
                # "b_guard_revision_id" are always written as str by the caller.
                raise self._revision_conflict(
                    namespace=cast(str, row["v_namespace"]),  # CAST-RATIONALE-SECURE-OBJECTS-ROW-STR-FIELD
                    expected_revision_id=cast(
                        str, row["b_guard_revision_id"]
                    ),  # CAST-RATIONALE-SECURE-OBJECTS-ROW-STR-FIELD
                    current_revision_id=current,
                )
        # The rowcount disagreed but every row now carries the revision this
        # batch wrote — an inconsistency this funnel cannot attribute.
        raise RepositoryError(
            context={
                # CAST-RATIONALE-SECURE-OBJECTS-ROW-STR-FIELD: see the identical cast above.
                "namespace": ", ".join(sorted({cast(str, row["v_namespace"]) for row in guarded})),
                "error_type": "GuardedUpdateRowcountMismatch",
            },
            translated_message="errors.fail.fail_storage_secure_object_upsert",
        )

    def _revision_conflict(
        self,
        *,
        namespace: str,
        expected_revision_id: str,
        current_revision_id: str | None,
    ) -> SecureObjectRevisionConflictError:
        return SecureObjectRevisionConflictError(
            tr("errors.fail.fail_storage_secure_object_revision_conflict"),
            context={
                "namespace": namespace,
                "expected_revision_id": expected_revision_id,
                "current_revision_id": current_revision_id or "",
            },
            translated_message="errors.fail.fail_storage_secure_object_revision_conflict",
        )
