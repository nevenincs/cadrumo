"""Encrypted SQL byte-object repository for sensitive application payloads."""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from datetime import datetime
from typing import cast

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Engine, bindparam, delete, inspect, select, text, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from .....core.classification import SensitivityClass
from .....core.i18n import tr
from .....core.logging import get_logger
from .._namespace_registry import SecureObjectNamespaceDefinition, StorageHierarchyRegistry
from ..crypto._encrypted_columns import decrypt_encrypted_bytes_column
from ..errors import (
    ClassificationError,
    DecryptionError,
    EnvelopeVersionError,
    RepositoryError,
    StorageValidationError,
)
from . import _orm
from .engine import get_engine
from .session import session_scope

_log = get_logger(__name__)

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid", arbitrary_types_allowed=True)
_DEFAULT_WRITE_PROVENANCE = "secure-object-repository"
_DEFAULT_CONFLICT_POLICY = "last-write-wins"
_SECURE_OBJECT_REVISION_METADATA_COLUMNS: tuple[tuple[str, str], ...] = (
    ("revision_id", "VARCHAR(64)"),
    ("previous_revision_id", "VARCHAR(64)"),
    ("previous_payload_hash", "VARCHAR(64)"),
    ("payload_hash", "VARCHAR(64)"),
    ("ciphertext_hash", "VARCHAR(64)"),
    ("revision_written_at", "DATETIME"),
    ("write_provenance", "VARCHAR(255)"),
    ("source_event_id", "VARCHAR(128)"),
    ("conflict_policy", "VARCHAR(32)"),
)


class SecureObjectRecord(BaseModel):
    """One decrypted sensitive object loaded from the SQL backend.

    Strict frozen pydantic v2 record so every load/list path emits a
    validated boundary-crossing payload (per the project's pydantic
    mandate).
    """

    model_config = _STRICT_FROZEN

    namespace: str = Field(min_length=1)
    object_key: bytes
    classification: SensitivityClass
    schema_version: int = Field(ge=1)
    written_at: datetime
    payload: bytes


class SecureObjectMetadata(BaseModel):
    """Row-level metadata for one stored secure object, decryption-free.

    Surfaced by :meth:`SecureObjectRepository.peek_metadata` so callers
    (notably the workflow-state reset recovery path) can fingerprint a
    row's wire envelope without decrypting it. Carries the columns the
    database stores alongside the ciphertext payload plus the raw
    payload byte length.
    """

    model_config = _STRICT_FROZEN

    namespace: str = Field(min_length=1)
    classification: str = Field(min_length=1)
    schema_version: int = Field(ge=1)
    written_at: datetime
    byte_length: int = Field(ge=0)


class SecureObjectWrite(BaseModel):
    """One encrypted secure-object upsert prepared for a unit of work."""

    model_config = _STRICT_FROZEN

    namespace: str = Field(min_length=1)
    object_key: str = Field(min_length=1)
    classification: SensitivityClass
    schema_version: int = Field(ge=1)
    written_at: datetime
    payload: bytes = Field(min_length=1)
    write_provenance: str = Field(default=_DEFAULT_WRITE_PROVENANCE, min_length=1, max_length=255)
    source_event_id: str | None = Field(default=None, min_length=1, max_length=128)


class SecureObjectUnreadable(BaseModel):
    """One stored secure object that cannot be decrypted under the current master key.

    Surfaced by :meth:`SecureObjectRepository.iter_records_with_failures`
    so iterating consumers can count and report the unreadable subset
    rather than aborting on the first failure. The plaintext is
    cryptographically unrecoverable from this process — the master key
    under which the row was sealed is no longer available.
    """

    model_config = _STRICT_FROZEN

    namespace: str = Field(min_length=1)
    row_id: int = Field(ge=0)
    object_key: bytes
    classification: str = Field(min_length=1)
    schema_version: int = Field(ge=1)
    written_at: datetime
    reason: str = Field(min_length=1)


SecureObjectListItem = SecureObjectRecord | SecureObjectUnreadable


class SecureObjectRawRow(BaseModel):
    """One stored row surfaced without classification / version validation or decryption.

    Used by the outbound sync coordinator to walk every persisted object and mirror its on-wire
    payload to a remote storage provider without ever touching the
    plaintext domain data. The repository keeps `payload` as the
    raw on-wire ciphertext bytes; mirroring consumers feed those bytes
    directly into `StorageProvider.put`.
    """

    model_config = _STRICT_FROZEN

    row_id: int = Field(ge=0)
    namespace: str = Field(min_length=1)
    object_key: bytes
    classification: str = Field(min_length=1)
    schema_version: int = Field(ge=1)
    written_at: datetime
    payload: bytes


class SecureObjectNamespaceIntegrity(BaseModel):
    """Per-namespace decryptability counts for the integrity diagnostic.

    Unlike :class:`SecureObjectListItem`, this report answers only the
    crypto-layer question ``can the payload be decrypted under the current
    master key`` -- classification and schema-version contracts are
    intentionally ignored. Used by ``aeat config repair`` to surface rows
    sealed under a rotated master key.
    """

    model_config = _STRICT_FROZEN

    namespace: str = Field(min_length=1)
    readable: int = Field(ge=0)
    unreadable: int = Field(ge=0)


class SecureObjectDecryptabilityRow(BaseModel):
    """Row-level decryptability metadata without plaintext payload disclosure."""

    model_config = _STRICT_FROZEN

    namespace: str = Field(min_length=1)
    row_id: int = Field(ge=0)
    object_key: bytes
    classification: str = Field(min_length=1)
    schema_version: int = Field(ge=1)
    written_at: datetime
    readable: bool
    reason: str | None = None


class SecureObjectRepository:
    """Repository over encrypted byte objects stored in the primary database."""

    def __init__(
        self,
        *,
        engine: Engine | None = None,
        namespace_registry: StorageHierarchyRegistry | None = None,
    ) -> None:
        self._engine = engine or get_engine()
        self._namespace_registry = namespace_registry
        # `inspect(mapped_class).local_table` is a `Table` at runtime, but the
        # SQLAlchemy stubs widen its declared type to `FromClause` (which lacks
        # `.create`). Cast through `Table` so pyrefly resolves the method.
        from sqlalchemy import Table as _Table

        local_table = inspect(_orm.SecureObjectRow).local_table
        assert isinstance(local_table, _Table)
        local_table.create(self._engine, checkfirst=True)
        self._ensure_table_revision_metadata_columns("secure_objects")

    def _ensure_table_revision_metadata_columns(self, table_name: str) -> None:
        """Add nullable revision metadata columns to a pre-existing table."""

        existing = {column["name"] for column in inspect(self._engine).get_columns(table_name)}
        missing = tuple(
            (name, column_type)
            for name, column_type in _SECURE_OBJECT_REVISION_METADATA_COLUMNS
            if name not in existing
        )
        if not missing:
            return
        for name, column_type in missing:
            try:
                with self._engine.begin() as connection:
                    connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {name} {column_type}"))
            except OperationalError as exc:
                if self._is_duplicate_column_race(table_name, name, exc):
                    _log.debug(
                        "%s: revision metadata column %s was added by a concurrent bootstrap",
                        table_name,
                        name,
                    )
                    continue
                raise
        _log.debug(
            "%s: added missing revision metadata columns: %s",
            table_name,
            ", ".join(name for name, _ in missing),
        )

    def _is_duplicate_column_race(self, table_name: str, column_name: str, exc: OperationalError) -> bool:
        """Return whether an ``ALTER TABLE ADD COLUMN`` failed after a concurrent add."""

        if "duplicate column" not in str(exc.orig).lower():
            return False
        existing = {column["name"] for column in inspect(self._engine).get_columns(table_name)}
        return column_name in existing

    def _ensure_quarantine_table(self) -> None:
        """Create the quarantine archive table with the secure-object metadata shape."""

        with self._engine.begin() as connection:
            connection.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS secure_objects_quarantine ("
                    "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
                    "  source_id INTEGER NOT NULL,"
                    "  namespace VARCHAR(128) NOT NULL,"
                    "  object_key BLOB NOT NULL,"
                    "  classification VARCHAR(32) NOT NULL,"
                    "  schema_version INTEGER NOT NULL,"
                    "  written_at DATETIME NOT NULL,"
                    "  revision_id VARCHAR(64),"
                    "  previous_revision_id VARCHAR(64),"
                    "  previous_payload_hash VARCHAR(64),"
                    "  payload_hash VARCHAR(64),"
                    "  ciphertext_hash VARCHAR(64),"
                    "  revision_written_at DATETIME,"
                    "  write_provenance VARCHAR(255),"
                    "  source_event_id VARCHAR(128),"
                    "  conflict_policy VARCHAR(32),"
                    "  payload BLOB NOT NULL,"
                    "  quarantined_at DATETIME NOT NULL"
                    ")"
                )
            )
        self._ensure_table_revision_metadata_columns("secure_objects_quarantine")

    @property
    def namespace_registry(self) -> StorageHierarchyRegistry | None:
        """Return the namespace registry bound to this repository, if any."""

        return self._namespace_registry

    def _registered_namespace_definition(self, namespace: str) -> SecureObjectNamespaceDefinition | None:
        """Return the registry contract for ``namespace`` when policy is bound."""

        if self._namespace_registry is None:
            return None
        try:
            return self._namespace_registry.namespace_by_value(namespace)
        except KeyError as exc:
            raise StorageValidationError(
                tr("errors.storage.namespace.unregistered", namespace=namespace),
                context={"namespace": namespace},
                translated_message="errors.storage.namespace.unregistered",
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
                tr(
                    "errors.storage.namespace.classification_mismatch",
                    namespace=namespace,
                    classification=classification.value,
                    expected=definition.sensitivity.value,
                ),
                context={
                    "namespace": namespace,
                    "classification": classification.value,
                    "expected": definition.sensitivity.value,
                },
                translated_message="errors.storage.namespace.classification_mismatch",
            )
        if schema_version != definition.schema_version:
            raise EnvelopeVersionError(
                tr(
                    "errors.storage.namespace.schema_mismatch",
                    namespace=namespace,
                    schema_version=schema_version,
                    expected=definition.schema_version,
                ),
                context={
                    "namespace": namespace,
                    "schema_version": schema_version,
                    "expected": definition.schema_version,
                },
                translated_message="errors.storage.namespace.schema_mismatch",
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
                tr(
                    "errors.storage.namespace.classification_mismatch",
                    namespace=namespace,
                    classification=expected_class.value,
                    expected=definition.sensitivity.value,
                ),
                context={
                    "namespace": namespace,
                    "classification": expected_class.value,
                    "expected": definition.sensitivity.value,
                },
                translated_message="errors.storage.namespace.classification_mismatch",
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
            tr(
                "errors.storage.namespace.schema_mismatch",
                namespace=namespace,
                schema_version=schema_version,
                expected=definition.schema_version,
            ),
            context={
                "namespace": namespace,
                "schema_version": schema_version,
                "expected": definition.schema_version,
            },
            translated_message="errors.storage.namespace.schema_mismatch",
        )

    def _check_session_freshness(self) -> None:
        """Refuse the operation when the active session has crossed its idle deadline.

        Polls :func:`evaluate_idle` against the live
        :class:`BucketSession` registered in the active-session
        ContextVar. When the session is sealed or past its deadline,
        raises :class:`SessionExpiredError` (translated by the CLI
        error decorator into a refusal that names ``aeat config
        profile switch`` as the next action). On a fresh session,
        calls :meth:`BucketSession.touch` to roll the deadline
        forward by the configured idle window — the operator's
        active session remains usable for the next window's
        duration without re-authentication.

        No-op when no session is bound (bootstrap-exempt verbs);
        the active-gate at the CLI root callback already refused
        non-exempt verbs that lack a session.
        """

        from datetime import UTC, datetime

        from ..errors import SessionExpiredError
        from ..master_key._active_session import _active_session
        from ..master_key._idle_timeout import evaluate_idle

        session = _active_session.get()
        if session is None:
            return
        now = datetime.now(UTC)
        outcome = evaluate_idle(session=session, now=now)
        if outcome.expired:
            raise SessionExpiredError(
                "the active profile session has expired; run "
                "`aeat config profile switch NAME` to re-activate.",
            )
        session.touch(now)

    def exists(self, namespace: str, object_key: str) -> bool:
        """Return whether ``namespace`` / ``object_key`` is present."""

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
        if len(hashed_object_key) != 32:
            raise StorageValidationError(
                f"hashed_object_key must be 32 bytes; got {len(hashed_object_key)}",
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
        """Yield every stored row as `SecureObjectRawRow` without decryption.

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

        with session_scope(self._engine) as session:
            stmt = text(
                "SELECT id, namespace, object_key, classification, schema_version, "
                "written_at, payload "
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
                    object_key_value = object_key_raw.encode("utf-8")
                else:
                    object_key_value = bytes(object_key_raw)
                payload_raw = raw.payload
                if isinstance(payload_raw, bytes):
                    payload_value = payload_raw
                elif isinstance(payload_raw, str):
                    payload_value = payload_raw.encode("utf-8")
                else:
                    payload_value = bytes(payload_raw)
                yield SecureObjectRawRow(
                    row_id=int(raw.id),
                    namespace=str(raw.namespace),
                    object_key=object_key_value,
                    classification=str(raw.classification),
                    schema_version=int(raw.schema_version),
                    written_at=written_at_value,
                    payload=payload_value,
                )

    def list_namespaces(self) -> tuple[str, ...]:
        """Return the distinct namespaces present in ``secure_objects`` sorted.

        Used by the integrity diagnostic so consumers do not have to
        hardcode the namespace list (which drifts as new domain
        repositories register their own namespaces).
        """
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
            A :class:`SecureObjectIntegrityReport`-shaped summary
            describing how many rows were quarantined per namespace.
        """
        from datetime import UTC

        self._ensure_quarantine_table()
        with session_scope(self._engine) as session:
            quarantined_at = datetime.now(UTC).isoformat()
            namespaces = (
                session.execute(text("SELECT DISTINCT namespace FROM secure_objects ORDER BY namespace"))
                .scalars()
                .all()
            )
            per_namespace: list[SecureObjectNamespaceIntegrity] = []
            for namespace in namespaces:
                rows = session.execute(
                    text(
                        "SELECT id, object_key, classification, schema_version, written_at, "
                        "revision_id, previous_revision_id, previous_payload_hash, payload_hash, "
                        "ciphertext_hash, revision_written_at, write_provenance, source_event_id, "
                        "conflict_policy, payload "
                        "FROM secure_objects WHERE namespace = :namespace"
                    ).bindparams(bindparam("namespace", value=namespace))
                ).all()
                quarantined = 0
                retained = 0
                for raw in rows:
                    payload_bytes = raw.payload if isinstance(raw.payload, bytes) else bytes(raw.payload)
                    object_key_value = (
                        raw.object_key
                        if isinstance(raw.object_key, bytes | bytearray | memoryview)
                        else str(raw.object_key).encode("utf-8")
                    )
                    object_key_bytes = bytes(object_key_value)
                    try:
                        decrypt_encrypted_bytes_column(payload_bytes)
                    except DecryptionError as exc:
                        _log.debug(
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
                                " payload_hash, ciphertext_hash, revision_written_at, write_provenance, "
                                " source_event_id, conflict_policy, payload, quarantined_at) "
                                "VALUES (:source_id, :namespace, :object_key, :classification, "
                                "        :schema_version, :written_at, :revision_id, "
                                "        :previous_revision_id, :previous_payload_hash, :payload_hash, "
                                "        :ciphertext_hash, :revision_written_at, :write_provenance, "
                                "        :source_event_id, :conflict_policy, :payload, :quarantined_at)"
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
                    )
                )
        return tuple(per_namespace)

    def probe_namespace_integrity(self, namespace: str) -> SecureObjectNamespaceIntegrity:
        """Count decryptable vs undecryptable rows in ``namespace``.

        This method answers a strictly crypto-layer question -- can the
        ``payload`` ciphertext be unwrapped under the current master key
        -- and intentionally bypasses the classification and
        schema-version contracts that consumer reads enforce. Used by
        ``aeat config repair`` to surface namespaces holding rows from a
        prior keychain master-key generation.
        """
        readable = 0
        unreadable = 0
        with session_scope(self._engine) as session:
            stmt = text("SELECT payload FROM secure_objects WHERE namespace = :namespace").bindparams(
                bindparam("namespace", value=namespace)
            )
            rows = session.execute(stmt).all()
        for raw in rows:
            try:
                decrypt_encrypted_bytes_column(bytes(raw.payload))
            except DecryptionError as exc:
                _log.debug(
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

    def iter_namespace_decryptability(self, namespace: str) -> Iterator[SecureObjectDecryptabilityRow]:
        """Yield row-level decryptability metadata for one namespace.

        This is the row-level companion to :meth:`probe_namespace_integrity`.
        It decrypts only to validate the AEAD tag, never returns plaintext, and
        exposes the HMAC lookup digest plus storage metadata needed by repair
        diagnostics.
        """

        with session_scope(self._engine) as session:
            stmt = (
                text(
                    "SELECT id, object_key, classification, schema_version, written_at, payload "
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
            )
            rows = session.execute(stmt).all()
        for raw in rows:
            object_key_raw = raw.object_key
            if isinstance(object_key_raw, bytes):
                object_key_value = object_key_raw
            elif isinstance(object_key_raw, str):
                object_key_value = object_key_raw.encode("utf-8")
            else:
                object_key_value = bytes(object_key_raw)
            payload_raw = raw.payload
            if isinstance(payload_raw, bytes):
                payload_value = payload_raw
            elif isinstance(payload_raw, str):
                payload_value = payload_raw.encode("utf-8")
            else:
                payload_value = bytes(payload_raw)
            try:
                decrypt_encrypted_bytes_column(payload_value)
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

    def list_keys(self, namespace: str) -> tuple[str, ...]:
        """Return stored lookup digests under ``namespace`` as hex strings.

        Natural object keys are HMAC digested before storage and cannot be
        recovered from the index. Domain repositories that need natural IDs
        should iterate :meth:`list_records` and read IDs from decrypted
        payloads.
        """

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
        """Yield every decryptable object under ``namespace``.

        Rows whose payload cannot be decrypted under the current master
        key are skipped; one ``WARNING`` log line summarises the count at
        the end of the iteration. Use :meth:`iter_records_with_failures`
        to receive a typed per-row outcome instead of skipping silently.
        """
        unreadable = 0
        for item in self.iter_records_with_failures(
            namespace,
            expected_class=expected_class,
            max_supported_version=max_supported_version,
        ):
            if isinstance(item, SecureObjectRecord):
                yield item
            else:
                unreadable += 1
        if unreadable > 0:
            _log.warning(
                "secure_objects: skipped %d unreadable row(s) in namespace %s; "
                "the master key under which they were sealed is no longer available "
                "(run 'aeat config repair' for details).",
                unreadable,
                namespace,
            )

    def iter_records_with_failures(
        self,
        namespace: str,
        *,
        expected_class: SensitivityClass,
        max_supported_version: int,
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
        """
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
            )
            rows = session.execute(stmt).all()
        for raw in rows:
            row_id = int(raw.id)
            object_key = bytes(raw.object_key)
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
                raise ClassificationError(
                    f"secure object {namespace}/{object_key.hex()} has classification "
                    f"{classification}; consumer expected {expected_class}",
                )
            if schema_version > max_supported_version:
                raise EnvelopeVersionError(
                    f"secure object {namespace}/{object_key.hex()} is at version "
                    f"{schema_version}; consumer supports up to {max_supported_version}",
                )
            self._enforce_registered_row_schema(
                namespace=namespace,
                schema_version=schema_version,
                definition=namespace_definition,
            )
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
        """Load and decrypt one object, returning ``None`` when absent."""

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
    ) -> None:
        """Encrypt and upsert one byte payload keyed by a natural string id.

        The natural ``object_key`` is HMAC-digested at the column
        boundary. To upsert against a pre-computed digest (e.g. when
        restoring an archive bundle whose natural key was lost in the
        original HMAC), use :meth:`save_with_raw_key` instead.
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
            classification: Sensitivity class to upsert at.
            schema_version: Envelope schema version captured on the row.
            written_at: Timezone-aware datetime captured on the row.
            payload: Plaintext envelope bytes (the column encrypts).

        Raises:
            :exc:`ValueError`: If ``hashed_object_key`` is not exactly
                32 bytes (the size :class:`HashedLookup` requires).
            :exc:`RepositoryError`: On underlying SQL integrity errors.
        """
        if len(hashed_object_key) != 32:
            raise StorageValidationError(
                f"hashed_object_key must be 32 bytes; got {len(hashed_object_key)}",
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
    ) -> None:
        previous_revision_id: str | None = None
        previous_payload_hash: str | None = None
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
                    _orm.SecureObjectRow.payload_hash,
                    _orm.SecureObjectRow.payload,
                ).where(_orm.SecureObjectRow.id == row_id)
            ).one()
            previous_revision_id = previous_metadata.revision_id
            previous_payload_hash = previous_metadata.payload_hash or hashlib.sha256(
                previous_metadata.payload,
            ).hexdigest()
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
                session.execute(
                    update(_orm.SecureObjectRow)
                    .where(_orm.SecureObjectRow.id == row_id)
                    .values(
                        classification=classification.value,
                        schema_version=schema_version,
                        written_at=written_at,
                        payload=payload,
                    )
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
                previous_payload_hash=previous_payload_hash,
                write_provenance=write_provenance,
                source_event_id=source_event_id,
            )
            session.flush()
        except IntegrityError as exc:
            raise RepositoryError(
                f"secure object upsert failed for {namespace}/<key>: {exc.orig}",
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
        previous_payload_hash: str | None,
        write_provenance: str,
        source_event_id: str | None,
    ) -> None:
        raw = session.execute(
            text("SELECT object_key, payload FROM secure_objects WHERE id = :row_id").bindparams(
                bindparam("row_id", value=row_id),
            )
        ).one()
        object_key = raw.object_key if isinstance(raw.object_key, bytes) else bytes(raw.object_key)
        ciphertext = raw.payload if isinstance(raw.payload, bytes) else bytes(raw.payload)
        payload_hash = hashlib.sha256(payload).hexdigest()
        ciphertext_hash = hashlib.sha256(ciphertext).hexdigest()
        revision_id = self._derive_revision_id(
            namespace=namespace,
            object_key=object_key,
            schema_version=schema_version,
            written_at=written_at,
            payload_hash=payload_hash,
            ciphertext_hash=ciphertext_hash,
            previous_revision_id=previous_revision_id,
            previous_payload_hash=previous_payload_hash,
        )
        session.execute(
            update(_orm.SecureObjectRow)
            .where(_orm.SecureObjectRow.id == row_id)
            .values(
                revision_id=revision_id,
                previous_revision_id=previous_revision_id,
                previous_payload_hash=previous_payload_hash,
                payload_hash=payload_hash,
                ciphertext_hash=ciphertext_hash,
                revision_written_at=written_at,
                write_provenance=write_provenance,
                source_event_id=source_event_id,
                conflict_policy=_DEFAULT_CONFLICT_POLICY,
            )
        )

    def _derive_revision_id(
        self,
        *,
        namespace: str,
        object_key: bytes,
        schema_version: int,
        written_at: datetime,
        payload_hash: str,
        ciphertext_hash: str,
        previous_revision_id: str | None,
        previous_payload_hash: str | None,
    ) -> str:
        parts = (
            namespace,
            object_key.hex(),
            str(schema_version),
            written_at.isoformat(),
            payload_hash,
            ciphertext_hash,
            previous_revision_id or "",
            previous_payload_hash or "",
        )
        return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()

    def peek_metadata(self, namespace: str, object_key: str) -> SecureObjectMetadata | None:
        """Return row-level metadata for one object without decrypting it.

        Returns ``None`` when no row matches. Never decrypts the payload
        column; callers use this to fingerprint an envelope they intend
        to discard (e.g. the workflow-state reset recovery path).
        """

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
            # SQLAlchemy types Session.execute() as Result[Any]; a DML
            # statement always yields a CursorResult at runtime, and only
            # CursorResult exposes .rowcount. Cast at this third-party API
            # boundary to read the affected-row count.
            result = cast(
                "CursorResult[object]",
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
                f"secure object {row.namespace}/{bytes(row.object_key).hex()} "
                f"has unknown classification {row.classification!r}",
            ) from exc
        if classification is not expected_class:
            raise ClassificationError(
                f"secure object {row.namespace}/{bytes(row.object_key).hex()} has classification {classification}; "
                f"consumer expected {expected_class}",
            )
        if row.schema_version > max_supported_version:
            raise EnvelopeVersionError(
                f"secure object {row.namespace}/{bytes(row.object_key).hex()} is at version {row.schema_version}; "
                f"consumer supports up to {max_supported_version}",
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
