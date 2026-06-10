"""Encrypted SQL byte-object repository for sensitive application payloads."""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import datetime
from typing import Protocol, cast

from sqlalchemy import Engine, bindparam, delete, inspect, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .....core.classification import SensitivityClass
from .....core.errors import resolve_error_message
from .....core.external_constants import UTF_8_ENCODING
from .....core.i18n import tr
from .....core.logging import get_logger
from .....core.time import now as _utc_now
from .._namespace_registry import SecureObjectNamespaceDefinition, StorageHierarchyRegistry
from ..crypto._encrypted_columns import (
    decrypt_encrypted_bytes_column,
)
from ..errors import (
    ClassificationError,
    DecryptionError,
    EnvelopeVersionError,
    RepositoryError,
    SecureObjectRevisionConflictError,
    SecureObjectUnreadableError,
    StorageValidationError,
)
from . import _orm
from ._secure_object_crypto import derive_revision_id, sha256_hex
from ._secure_object_integrity import (
    iter_namespace_decryptability as _iter_namespace_decryptability,
)
from ._secure_object_integrity import (
    probe_namespace_integrity as _probe_namespace_integrity,
)
from ._secure_object_integrity import (
    quarantine_unreadable_rows as _quarantine_unreadable_rows,
)
from ._secure_object_records import (
    DEFAULT_WRITE_PROVENANCE,
    SecureObjectDecryptabilityRow,
    SecureObjectListItem,
    SecureObjectMetadata,
    SecureObjectNamespaceIntegrity,
    SecureObjectRawRow,
    SecureObjectRecord,
    SecureObjectUnreadable,
    SecureObjectWrite,
)
from ._secure_object_schema import (
    build_revision_ancestor_ids,
    coerce_raw_bytes,
    ensure_quarantine_table,
    parse_revision_ancestor_ids,
)
from .engine import get_engine
from .session import session_scope

_log = get_logger(__name__)

_DEFAULT_WRITE_PROVENANCE = DEFAULT_WRITE_PROVENANCE
_DEFAULT_CONFLICT_POLICY = "last-write-wins"


class _RowcountResult(Protocol):
    """Structural result shape for SQLAlchemy DML rowcount checks."""

    rowcount: int


class SecureObjectRepository:
    """Repository over encrypted byte objects stored in the primary database."""

    def __init__(
        self,
        *,
        engine: Engine | None = None,
        namespace_registry: StorageHierarchyRegistry | None = None,
        active_session_bucket_id: str | None = None,
        require_secure_active_session: bool = False,
    ) -> None:
        """Bind the repository to ``engine`` and ensure the secure_objects table exists."""
        self._engine = engine or get_engine()
        self._namespace_registry = namespace_registry
        self._active_session_bucket_id = active_session_bucket_id
        self._require_secure_active_session = require_secure_active_session
        # `inspect(mapped_class).local_table` is a `Table` at runtime, but the
        # SQLAlchemy stubs widen its declared type to `FromClause` (which lacks
        # `.create`). Cast through `Table` so pyrefly resolves the method.
        from sqlalchemy import Table as _Table

        local_table = inspect(_orm.SecureObjectRow).local_table
        assert isinstance(local_table, _Table)
        local_table.create(self._engine, checkfirst=True)

    @staticmethod
    def _coerce_raw_bytes(value: object) -> bytes:
        return coerce_raw_bytes(value)

    @staticmethod
    def _parse_revision_ancestor_ids(raw_value: object) -> tuple[str, ...]:
        return parse_revision_ancestor_ids(raw_value)

    @staticmethod
    def _build_revision_ancestor_ids(
        previous_revision_id: str | None,
        previous_revision_ancestor_ids: tuple[str, ...],
    ) -> tuple[str, ...]:
        return build_revision_ancestor_ids(previous_revision_id, previous_revision_ancestor_ids)

    def _ensure_quarantine_table(self) -> None:
        """Create the quarantine archive table with the secure-object metadata shape."""
        ensure_quarantine_table(self._engine)

    @property
    def namespace_registry(self) -> StorageHierarchyRegistry | None:
        """Return the :class:`StorageHierarchyRegistry` bound to this repository, if any."""
        return self._namespace_registry

    def _registered_namespace_definition(self, namespace: str) -> SecureObjectNamespaceDefinition | None:
        """Return the registry contract for ``namespace`` when policy is bound."""
        if self._namespace_registry is None:
            return None
        try:
            return self._namespace_registry.namespace_by_value(namespace)
        except KeyError as exc:
            raise StorageValidationError(
                translated_message="errors.storage.namespace.unregistered",
                context={"namespace": namespace},
            ) from exc

    def _enforce_registered_write_policy(
        self,
        *,
        namespace: str,
        classification: SensitivityClass,
        schema_version: int,
    ) -> None:
        definition = self._registered_namespace_definition(namespace)
        if definition is None:
            return
        if classification is not definition.sensitivity:
            raise ClassificationError(
                translated_message="errors.storage.namespace.classification_mismatch",
                context={
                    "namespace": namespace,
                    "classification": classification.value,
                    "expected": definition.sensitivity.value,
                },
            )
        if schema_version != definition.schema_version:
            raise EnvelopeVersionError(
                translated_message="errors.storage.namespace.schema_mismatch",
                context={
                    "namespace": namespace,
                    "schema_version": schema_version,
                    "expected": definition.schema_version,
                },
            )

    def _enforce_registered_read_policy(
        self,
        *,
        namespace: str,
        expected_class: SensitivityClass,
    ) -> SecureObjectNamespaceDefinition | None:
        definition = self._registered_namespace_definition(namespace)
        if definition is None:
            return None
        if expected_class is not definition.sensitivity:
            raise ClassificationError(
                translated_message="errors.storage.namespace.classification_mismatch",
                context={
                    "namespace": namespace,
                    "classification": expected_class.value,
                    "expected": definition.sensitivity.value,
                },
            )
        return definition

    def _enforce_registered_row_schema(
        self,
        *,
        namespace: str,
        schema_version: int,
        definition: SecureObjectNamespaceDefinition | None,
    ) -> None:
        if definition is None or schema_version <= definition.schema_version:
            return
        raise EnvelopeVersionError(
            translated_message="errors.storage.namespace.schema_mismatch",
            context={
                "namespace": namespace,
                "schema_version": schema_version,
                "expected": definition.schema_version,
            },
        )

    def _check_session_freshness(self) -> None:
        """Refuse the operation when the active profile session is no longer valid.

        Polls :func:`evaluate_idle` against the live
        :class:`BucketSession` registered in the active-session
        ContextVar. When the session is sealed or past its deadline,
        raises :class:`SessionExpiredError` (translated by the CLI
        error decorator into a refusal that names ``aeat config
        unlock`` as the next action). On a fresh session,
        calls :meth:`BucketSession.touch` to roll the deadline
        forward by the configured idle window — the operator's
        active session remains usable for the next window's
        duration without re-authentication.

        Runtime-bound repositories also refuse stale handles whose active
        session changed bucket or fell back to the unsecured backend after
        construction. No-op when no session is bound and this repository is
        not runtime-bound; bootstrap-exempt verbs rely on that direct mode.
        """
        from ..errors import SessionExpiredError
        from ..master_key._active_session import _active_session
        from ..master_key._idle_timeout import evaluate_idle
        from ..runtime import _runtime_not_ready_error

        session = _active_session.get()
        if session is None:
            if self._require_secure_active_session:
                raise _runtime_not_ready_error(
                    "storage runtime is not ready for profile-bound storage: no active bucket session.",
                    message_key="errors.storage.runtime.no_active_session",
                )
            return
        now = _utc_now()
        outcome = evaluate_idle(session=session, now=now)
        if outcome.expired:
            raise SessionExpiredError(
                "the active profile session has expired; run `aeat config switch NAME` to re-activate.",
            )
        if self._require_secure_active_session and session.unsecured_backend:
            raise _runtime_not_ready_error(
                "storage runtime is not ready for profile-bound storage: active bucket session uses unsecured backend.",
                message_key="errors.storage.runtime.unsecured_backend",
            )
        if self._active_session_bucket_id is not None and session.bucket_id != self._active_session_bucket_id:
            raise _runtime_not_ready_error(
                "storage runtime is not ready for profile-bound storage: active bucket session changed.",
                message_key="errors.storage.runtime.session_changed",
            )
        session.touch(now)

    def exists(self, namespace: str, object_key: str) -> bool:
        """Return whether ``namespace`` / ``object_key`` is present."""
        self._check_session_freshness()
        with session_scope(self._engine) as session:
            row_id = session.execute(
                select(_orm.SecureObjectRow.id).where(
                    _orm.SecureObjectRow.namespace == namespace,
                    _orm.SecureObjectRow.object_key == object_key,
                )
            ).scalar_one_or_none()
            return row_id is not None

    def exists_by_raw_key(self, namespace: str, hashed_object_key: bytes) -> bool:
        """Return whether ``namespace`` carries a row with this raw HMAC digest.

        Used by the archive restore pipeline when the natural key was
        not present in the source bundle. Same
        master-key constraint as :meth:`save_with_raw_key`.
        """
        self._check_session_freshness()
        if len(hashed_object_key) != 32:
            raise StorageValidationError(
                context={"length": len(hashed_object_key)},
                translated_message="errors.integrity.integrity_storage_secure_object_hashed_key_length",
            )
        with session_scope(self._engine) as session:
            row_id = session.execute(
                select(_orm.SecureObjectRow.id).where(
                    _orm.SecureObjectRow.namespace == namespace,
                    _orm.SecureObjectRow.object_key == hashed_object_key,
                )
            ).scalar_one_or_none()
            return row_id is not None

    def iter_all_records_raw(self, *, batch_size: int = 256) -> Iterator[SecureObjectRawRow]:
        """Yield every stored row as a :class:`SecureObjectRawRow` without decryption.

        Walks every row in `secure_objects` ordered by `(namespace, object_key)`
        without attempting to decrypt the payload. The query bypasses
        the encrypted-column type decorators so rows sealed under a
        rotated master key still surface verbatim — this is what the
        outbound sync coordinator's ciphertext-layer mirror
        consumes, mirroring on-wire ciphertext to a remote storage
        provider without ever decrypting domain data.

        Args:
            batch_size: SQLAlchemy `yield_per` chunk size. The default
                keeps memory bounded for very large substrates while
                still amortising session overhead across multiple rows.

        Yields:
            One `SecureObjectRawRow` per persisted row. The order is
            `(namespace ASC, object_key ASC)` so consumers can
            checkpoint progress deterministically.
        """
        self._check_session_freshness()
        with session_scope(self._engine) as session:
            stmt = text(
                "SELECT id, namespace, object_key, classification, schema_version, "
                "written_at, payload, revision_id, previous_revision_id, revision_ancestor_ids, previous_payload_hash, "
                "payload_hash, ciphertext_hash, revision_written_at "
                "FROM secure_objects "
                "ORDER BY namespace, object_key"
            ).execution_options(yield_per=batch_size)
            for raw in session.execute(stmt):
                written_at_raw = raw.written_at
                if isinstance(written_at_raw, str):
                    written_at_value = datetime.fromisoformat(written_at_raw)
                else:
                    written_at_value = written_at_raw
                # SQLite returns BLOB columns as bytes when the stored
                # value contains non-text bytes, but as str when the
                # bytes happen to be valid UTF-8. Normalise both into
                # bytes so downstream consumers see a consistent type.
                object_key_raw = raw.object_key
                if isinstance(object_key_raw, bytes):
                    object_key_value = object_key_raw
                elif isinstance(object_key_raw, str):
                    object_key_value = object_key_raw.encode(UTF_8_ENCODING)
                else:
                    object_key_value = bytes(object_key_raw)
                payload_raw = raw.payload
                if isinstance(payload_raw, bytes):
                    payload_value = payload_raw
                elif isinstance(payload_raw, str):
                    payload_value = payload_raw.encode(UTF_8_ENCODING)
                else:
                    payload_value = bytes(payload_raw)
                revision_written_at_raw = raw.revision_written_at
                if isinstance(revision_written_at_raw, str):
                    revision_written_at_value = datetime.fromisoformat(revision_written_at_raw)
                else:
                    revision_written_at_value = revision_written_at_raw
                yield SecureObjectRawRow(
                    row_id=int(raw.id),
                    namespace=str(raw.namespace),
                    object_key=object_key_value,
                    classification=str(raw.classification),
                    schema_version=int(raw.schema_version),
                    written_at=written_at_value,
                    payload=payload_value,
                    revision_id=raw.revision_id,
                    previous_revision_id=raw.previous_revision_id,
                    revision_ancestor_ids=self._parse_revision_ancestor_ids(raw.revision_ancestor_ids),
                    previous_payload_hash=raw.previous_payload_hash,
                    payload_hash=raw.payload_hash,
                    ciphertext_hash=raw.ciphertext_hash,
                    revision_written_at=revision_written_at_value,
                )

    def list_namespaces(self) -> tuple[str, ...]:
        """Return the distinct namespaces present in ``secure_objects`` sorted.

        Used by the integrity diagnostic so consumers do not have to
        hardcode the namespace list (which drifts as new domain
        repositories register their own namespaces).
        """
        self._check_session_freshness()
        with session_scope(self._engine) as session:
            rows = (
                session.execute(
                    select(_orm.SecureObjectRow.namespace).distinct().order_by(_orm.SecureObjectRow.namespace)
                )
                .scalars()
                .all()
            )
        return tuple(rows)

    def quarantine_unreadable_rows(self) -> tuple[SecureObjectNamespaceIntegrity, ...]:
        """Move every undecryptable row into ``secure_objects_quarantine``.

        Iterates every populated namespace, probes each row's payload
        through :func:`decrypt_encrypted_bytes_column`, and for rows that
        fail tag verification copies the original (encrypted) payload
        plus all metadata into the quarantine table, then deletes the
        row from ``secure_objects``. The quarantine table mirrors
        ``secure_objects`` with the addition of a ``quarantined_at``
        timestamp so the archive is auditable.

        Decryptable rows are NOT touched; the quarantine table is created
        on first use; nothing is auto-deleted from the user's data even
        after quarantine. The operator can recover the quarantined rows
        manually from the table if a missing master key is later
        recovered (for example, restored from a recovery key backup).

        Returns:
            A tuple of :class:`SecureObjectNamespaceIntegrity` records describing
            how many rows were quarantined per namespace.
        """
        self._check_session_freshness()
        return _quarantine_unreadable_rows(self._engine, logger=_log)

    def probe_namespace_integrity(self, namespace: str) -> SecureObjectNamespaceIntegrity:
        """Count decryptable and undecryptable rows in ``namespace``.

        Returns a :class:`SecureObjectNamespaceIntegrity` for the namespace.

        This method answers a strictly crypto-layer question -- can the
        ``payload`` ciphertext be unwrapped under the current master key
        -- and intentionally bypasses the classification and
        schema-version contracts that consumer reads enforce. Used by
        ``aeat config repair`` to surface namespaces holding rows from a
        prior keychain master-key generation.
        """
        self._check_session_freshness()
        return _probe_namespace_integrity(self._engine, namespace, logger=_log)

    def iter_namespace_decryptability(self, namespace: str) -> Iterator[SecureObjectDecryptabilityRow]:
        """Yield :class:`SecureObjectDecryptabilityRow` metadata for one namespace.

        This is the row-level companion to :meth:`probe_namespace_integrity`.
        It decrypts only to validate the AEAD tag, never returns plaintext, and
        exposes the HMAC lookup digest plus storage metadata needed by repair
        diagnostics.
        """
        self._check_session_freshness()
        yield from _iter_namespace_decryptability(self._engine, namespace)

    def list_keys(self, namespace: str) -> tuple[str, ...]:
        """Return stored lookup digests under ``namespace`` as hex strings.

        Natural object keys are HMAC digested before storage and cannot be
        recovered from the index. Domain repositories that need natural IDs
        should iterate :meth:`list_records` and read IDs from decrypted
        payloads.
        """
        self._check_session_freshness()
        with session_scope(self._engine) as session:
            rows = session.execute(
                select(_orm.SecureObjectRow.object_key)
                .where(_orm.SecureObjectRow.namespace == namespace)
                .order_by(_orm.SecureObjectRow.object_key)
            ).scalars()
            return tuple(bytes(row).hex() for row in rows)

    def list_records(
        self,
        namespace: str,
        *,
        expected_class: SensitivityClass,
        max_supported_version: int,
    ) -> Iterator[SecureObjectRecord]:
        """Yield every :class:`SecureObjectRecord` under ``namespace`` or fail on unreadable rows.

        The default listing path is fail-closed: it first walks the
        namespace through :meth:`iter_records_with_failures`, and if any
        row is unreadable it raises :class:`SecureObjectUnreadableError`
        before yielding a readable subset. Use
        :meth:`iter_records_with_failures` for explicit diagnostic
        iteration over mixed readable/unreadable rows.

        Args:
            namespace: The storage namespace whose rows are listed.
            expected_class: The :class:`SensitivityClass` all rows in this
                namespace must carry.
            max_supported_version: Rows whose ``schema_version`` exceeds
                this ceiling are treated as unreadable.
        """
        records: list[SecureObjectRecord] = []
        for item in self.iter_records_with_failures(
            namespace,
            expected_class=expected_class,
            max_supported_version=max_supported_version,
        ):
            if isinstance(item, SecureObjectRecord):
                records.append(item)
                continue
            _log.debug(
                "secure_objects: refusing default list for namespace=%s because row id=%s is unreadable (%s)",
                namespace,
                item.row_id,
                item.reason,
            )
            raise SecureObjectUnreadableError(namespace, item.row_id)
        yield from records

    def iter_records_with_failures(
        self,
        namespace: str,
        *,
        expected_class: SensitivityClass,
        max_supported_version: int,
        batch_size: int = 256,
    ) -> Iterator[SecureObjectListItem]:
        """Yield a typed outcome per stored row under ``namespace``.

        Each row is represented by either a :class:`SecureObjectRecord`
        (the row decrypts cleanly and matches the consumer's classification
        and schema-version contract) or a :class:`SecureObjectUnreadable`
        (the on-wire ciphertext exists but cannot be decrypted under the
        current master key, or its metadata fails the consumer's contract).

        The iterator is fault-isolated: a failure on row ``N`` does not
        prevent rows ``> N`` from being inspected. Consumers count the
        failures and decide how to report them; nothing is auto-deleted.

        Args:
            namespace: The storage namespace whose rows are scanned.
            expected_class: The :class:`SensitivityClass` all rows in this
                namespace must carry; rows with a differing classification
                are yielded as :class:`SecureObjectUnreadable`.
            max_supported_version: Rows whose ``schema_version`` exceeds
                this ceiling are yielded as :class:`SecureObjectUnreadable`
                so callers can detect forward-migration gaps.
            batch_size: SQLAlchemy ``yield_per`` chunk size for the raw row
                scan. The default keeps memory bounded for large namespaces
                while preserving deterministic ``(object_key ASC)`` order.

        Yields:
            One ``SecureObjectListItem`` per stored row — either a
            :class:`SecureObjectRecord` or a :class:`SecureObjectUnreadable`.

        Raises:
            StorageValidationError: When ``batch_size`` is less than 1.
        """
        self._check_session_freshness()
        if batch_size < 1:
            raise StorageValidationError(
                context={"batch_size": batch_size},
                translated_message="errors.integrity.integrity_storage_secure_object_batch_size",
            )
        namespace_definition = self._enforce_registered_read_policy(
            namespace=namespace,
            expected_class=expected_class,
        )
        with session_scope(self._engine) as session:
            stmt = (
                text(
                    "SELECT id, object_key, classification, schema_version, "
                    "written_at, payload "
                    "FROM secure_objects WHERE namespace = :namespace "
                    "ORDER BY object_key"
                )
                .bindparams(bindparam("namespace", value=namespace))
                .columns(
                    id=_orm.SecureObjectRow.__table__.c.id.type,
                    object_key=_orm.SecureObjectRow.__table__.c.object_key.type,
                    classification=_orm.SecureObjectRow.__table__.c.classification.type,
                    schema_version=_orm.SecureObjectRow.__table__.c.schema_version.type,
                    written_at=_orm.SecureObjectRow.__table__.c.written_at.type,
                )
                .execution_options(stream_results=True, yield_per=batch_size)
            )
            for raw in session.execute(stmt):
                row_id = int(raw.id)
                # ``object_key`` is a HashedLookup digest. Keep the bytes
                # surface stable for diagnostics and raw mirror consumers.
                _raw_ok = raw.object_key
                object_key = _raw_ok.encode(UTF_8_ENCODING) if isinstance(_raw_ok, str) else bytes(_raw_ok)
                classification_str = str(raw.classification)
                schema_version = int(raw.schema_version)
                written_at = raw.written_at
                payload_wire = bytes(raw.payload)
                try:
                    classification = SensitivityClass(classification_str)
                except ValueError:
                    yield SecureObjectUnreadable(
                        namespace=namespace,
                        row_id=row_id,
                        object_key=object_key,
                        classification=classification_str,
                        schema_version=schema_version,
                        written_at=written_at,
                        reason=f"unknown classification {classification_str!r}",
                    )
                    continue
                if classification is not expected_class:
                    yield SecureObjectUnreadable(
                        namespace=namespace,
                        row_id=row_id,
                        object_key=object_key,
                        classification=classification_str,
                        schema_version=schema_version,
                        written_at=written_at,
                        reason=(
                            f"classification {classification.value!r} does not match expected {expected_class.value!r}"
                        ),
                    )
                    continue
                if schema_version > max_supported_version:
                    yield SecureObjectUnreadable(
                        namespace=namespace,
                        row_id=row_id,
                        object_key=object_key,
                        classification=classification_str,
                        schema_version=schema_version,
                        written_at=written_at,
                        reason=(f"schema version {schema_version} exceeds supported {max_supported_version}"),
                    )
                    continue
                try:
                    self._enforce_registered_row_schema(
                        namespace=namespace,
                        schema_version=schema_version,
                        definition=namespace_definition,
                    )
                except EnvelopeVersionError as exc:
                    yield SecureObjectUnreadable(
                        namespace=namespace,
                        row_id=row_id,
                        object_key=object_key,
                        classification=classification_str,
                        schema_version=schema_version,
                        written_at=written_at,
                        reason=resolve_error_message(exc),
                    )
                    continue
                try:
                    payload_plain = decrypt_encrypted_bytes_column(payload_wire)
                except DecryptionError as exc:
                    yield SecureObjectUnreadable(
                        namespace=namespace,
                        row_id=row_id,
                        object_key=object_key,
                        classification=classification_str,
                        schema_version=schema_version,
                        written_at=written_at,
                        reason=str(exc),
                    )
                    continue
                yield SecureObjectRecord(
                    namespace=namespace,
                    object_key=object_key,
                    classification=classification,
                    schema_version=schema_version,
                    written_at=written_at,
                    payload=payload_plain,
                )

    def load(
        self,
        namespace: str,
        object_key: str,
        *,
        expected_class: SensitivityClass,
        max_supported_version: int,
    ) -> SecureObjectRecord | None:
        """Load and decrypt one :class:`SecureObjectRecord`, returning ``None`` when absent.

        Args:
            namespace: The storage namespace to look in.
            object_key: The natural string key identifying the record.
            expected_class: The :class:`SensitivityClass` the consumer expects.
            max_supported_version: Highest ``schema_version`` the consumer supports.
        """
        self._check_session_freshness()
        namespace_definition = self._enforce_registered_read_policy(
            namespace=namespace,
            expected_class=expected_class,
        )
        with session_scope(self._engine) as session:
            row = session.execute(
                select(_orm.SecureObjectRow).where(
                    _orm.SecureObjectRow.namespace == namespace,
                    _orm.SecureObjectRow.object_key == object_key,
                )
            ).scalar_one_or_none()
            if row is None:
                return None
            return self._record_from_row(
                row,
                expected_class=expected_class,
                max_supported_version=max_supported_version,
                namespace_definition=namespace_definition,
            )

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
        original HMAC), use :meth:`save_with_raw_key` instead.

        Args:
            namespace: The storage namespace to write into.
            object_key: Natural string identifier for this record. Digested
                via HMAC before being stored on disk.
            classification: The :class:`SensitivityClass` for this record.
            schema_version: Envelope schema version to stamp on the row.
            written_at: Timezone-aware write timestamp.
            payload: Plaintext envelope bytes. Encrypted at the column boundary.
            write_provenance: Human-readable string identifying the write origin.
            source_event_id: Optional opaque domain-event identifier for audit trails.
            expected_revision_id: Optional optimistic-concurrency guard.
        """
        self._check_session_freshness()
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
        if not writes:
            return
        self._check_session_freshness()
        for write in writes:
            self._enforce_registered_write_policy(
                namespace=write.namespace,
                classification=write.classification,
                schema_version=write.schema_version,
            )
        with session_scope(self._engine) as session:
            for write in writes:
                self._save_internal_in_session(
                    session,
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
        the :class:`HashedLookup` column without re-hashing. Used by
        the archive restore path to round-trip rows whose natural key
        is not present in the bundle (e.g. the path-keyed setup-profile
        and inventory namespaces).

        Args:
            namespace: The :class:`SecureObjectRepository` namespace.
            hashed_object_key: 32 raw HMAC-SHA256 bytes (the digest
                produced by :meth:`HashedLookup.compute` under the
                same master key the row was originally written with).
            classification: :class:`SensitivityClass` to upsert at.
            schema_version: Envelope schema version captured on the row.
            written_at: Timezone-aware datetime captured on the row.
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
        self._check_session_freshness()
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
        """Shared upsert backing :meth:`save` and :meth:`save_with_raw_key`."""
        self._enforce_registered_write_policy(
            namespace=namespace,
            classification=classification,
            schema_version=schema_version,
        )
        with session_scope(self._engine) as session:
            self._save_internal_in_session(
                session,
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

    def _save_internal_in_session(
        self,
        session: Session,
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
        previous_revision_id: str | None = None
        previous_payload_hash: str | None = None
        previous_revision_ancestor_ids: tuple[str, ...] = ()
        row_id = session.execute(
            select(_orm.SecureObjectRow.id).where(
                _orm.SecureObjectRow.namespace == namespace,
                _orm.SecureObjectRow.object_key == key,
            )
        ).scalar_one_or_none()
        if row_id is not None:
            previous_metadata = session.execute(
                select(
                    _orm.SecureObjectRow.revision_id,
                    _orm.SecureObjectRow.revision_ancestor_ids,
                    _orm.SecureObjectRow.payload_hash,
                    _orm.SecureObjectRow.payload,
                ).where(_orm.SecureObjectRow.id == row_id)
            ).one()
            previous_revision_id = previous_metadata.revision_id
            previous_revision_ancestor_ids = self._parse_revision_ancestor_ids(previous_metadata.revision_ancestor_ids)
            previous_payload_hash = previous_metadata.payload_hash or sha256_hex(
                previous_metadata.payload,
            )
        elif expected_revision_id is not None:
            raise self._revision_conflict(
                namespace=namespace,
                expected_revision_id=expected_revision_id,
                current_revision_id=None,
            )
        try:
            if row_id is None:
                row = _orm.SecureObjectRow(
                    namespace=namespace,
                    object_key=key,
                    classification=classification.value,
                    schema_version=schema_version,
                    written_at=written_at,
                    payload=payload,
                )
                session.add(row)
                session.flush()
                row_id = row.id
            else:
                update_stmt = update(_orm.SecureObjectRow).where(_orm.SecureObjectRow.id == row_id)
                if expected_revision_id is not None:
                    update_stmt = update_stmt.where(_orm.SecureObjectRow.revision_id == expected_revision_id)
                # CAST-RATIONALE-SECURE-OBJECTS-SQLALCHEMY-CURSOR-UPDATE:
                # SQLAlchemy types ``Session.execute()`` as ``Result[Any]``;
                # a DML UPDATE always yields a rowcount-bearing result.
                result = cast(
                    _RowcountResult,
                    session.execute(
                        update_stmt.values(
                            classification=classification.value,
                            schema_version=schema_version,
                            written_at=written_at,
                            payload=payload,
                        )
                    ),
                )
                if expected_revision_id is not None and result.rowcount != 1:
                    current_revision_id = session.execute(
                        select(_orm.SecureObjectRow.revision_id).where(_orm.SecureObjectRow.id == row_id)
                    ).scalar_one_or_none()
                    raise self._revision_conflict(
                        namespace=namespace,
                        expected_revision_id=expected_revision_id,
                        current_revision_id=current_revision_id,
                    )
                session.flush()
            self._write_revision_metadata(
                session,
                row_id=int(row_id),
                namespace=namespace,
                schema_version=schema_version,
                written_at=written_at,
                payload=payload,
                previous_revision_id=previous_revision_id,
                previous_revision_ancestor_ids=previous_revision_ancestor_ids,
                previous_payload_hash=previous_payload_hash,
                write_provenance=write_provenance,
                source_event_id=source_event_id,
                conflict_policy=("compare-and-swap" if expected_revision_id is not None else _DEFAULT_CONFLICT_POLICY),
            )
            session.flush()
        except IntegrityError as exc:
            raise RepositoryError(
                context={
                    "namespace": namespace,
                    "error_type": type(exc.orig).__name__,
                },
                translated_message="errors.fail.fail_storage_secure_object_upsert",
            ) from exc

    def _write_revision_metadata(
        self,
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
            )
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
        revision_ancestor_ids = self._build_revision_ancestor_ids(
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
            )
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

    def peek_metadata(self, namespace: str, object_key: str) -> SecureObjectMetadata | None:
        """Return :class:`SecureObjectMetadata` for one object without decrypting it.

        Returns ``None`` when no row matches. Never decrypts the payload
        column; callers use this to fingerprint an envelope they intend
        to discard (e.g. the workflow-state reset recovery path).
        """
        self._check_session_freshness()
        # Resolve the row id through the ORM so the HashedLookup column
        # binding hashes ``object_key`` consistently with the rest of
        # the repository, then read the raw row through ``text()`` so
        # the encrypted payload column is not auto-decrypted.
        with session_scope(self._engine) as session:
            row_id = session.execute(
                select(_orm.SecureObjectRow.id).where(
                    _orm.SecureObjectRow.namespace == namespace,
                    _orm.SecureObjectRow.object_key == object_key,
                )
            ).scalar_one_or_none()
            if row_id is None:
                return None
            stmt = (
                text(
                    "SELECT classification, schema_version, written_at, payload FROM secure_objects WHERE id = :row_id"
                )
                .bindparams(bindparam("row_id", value=int(row_id)))
                .columns(
                    classification=_orm.SecureObjectRow.__table__.c.classification.type,
                    schema_version=_orm.SecureObjectRow.__table__.c.schema_version.type,
                    written_at=_orm.SecureObjectRow.__table__.c.written_at.type,
                )
            )
            raw = session.execute(stmt).one()
        return SecureObjectMetadata(
            namespace=namespace,
            classification=str(raw.classification),
            schema_version=int(raw.schema_version),
            written_at=raw.written_at,
            byte_length=len(bytes(raw.payload)),
        )

    def delete(self, namespace: str, object_key: str) -> bool:
        """Delete one object if it exists."""
        self._check_session_freshness()
        with session_scope(self._engine) as session:
            # CAST-RATIONALE-SECURE-OBJECTS-SQLALCHEMY-CURSOR-DELETE:
            # SQLAlchemy types ``Session.execute()`` as ``Result[Any]``; a
            # DML DELETE always yields a rowcount-bearing result.
            result = cast(
                _RowcountResult,
                session.execute(
                    delete(_orm.SecureObjectRow).where(
                        _orm.SecureObjectRow.namespace == namespace,
                        _orm.SecureObjectRow.object_key == object_key,
                    )
                ),
            )
            return bool(result.rowcount and result.rowcount > 0)

    def _record_from_row(
        self,
        row: _orm.SecureObjectRow,
        *,
        expected_class: SensitivityClass,
        max_supported_version: int,
        namespace_definition: SecureObjectNamespaceDefinition | None = None,
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
        if row.schema_version > max_supported_version:
            raise EnvelopeVersionError(
                context={
                    "namespace": row.namespace,
                    "schema_version": row.schema_version,
                    "expected": max_supported_version,
                },
                translated_message="errors.storage.namespace.schema_mismatch",
            )
        self._enforce_registered_row_schema(
            namespace=row.namespace,
            schema_version=row.schema_version,
            definition=namespace_definition,
        )
        return SecureObjectRecord(
            namespace=row.namespace,
            object_key=bytes(row.object_key),
            classification=classification,
            schema_version=row.schema_version,
            written_at=row.written_at,
            payload=row.payload,
        )
