"""Encrypted SQL byte-object repository for sensitive application payloads."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from datetime import datetime
from typing import Protocol, cast

from sqlalchemy import Engine, bindparam, delete, inspect, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .....core import ABSENT_SECURE_OBJECT_REVISION_ID, DEFAULT_WRITE_PROVENANCE, SecureObjectWrite
from .....core.classification import SensitivityClass
from .....core.external_constants import UTF_8_ENCODING
from .....core.i18n import tr
from .....core.logging import get_logger
from .....core.time import coerce_utc_aware, validate_utc_aware
from .....core.time import now as _utc_now
from .._namespace_registry import (
    SecureObjectNamespaceDefinition,
    StorageHierarchyRegistry,
    is_former_product_namespace,
)
from .._schema_lineage import ensure_schema_version_readable
from ..crypto import (
    encrypt_secure_object_payload,
    secure_object_key_digest,
    secure_object_payload_aad,
)
from ..errors import (
    ClassificationError,
    EnvelopeVersionError,
    NamespaceRegistryError,
    RepositoryError,
    SecureObjectRevisionConflictError,
    SecureObjectUnreadableError,
    StorageValidationError,
)
from . import _orm
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
    SecureObjectBatchLoadItem,
    SecureObjectDecryptabilityRow,
    SecureObjectDeletion,
    SecureObjectListItem,
    SecureObjectMetadata,
    SecureObjectNamespaceIntegrity,
    SecureObjectRawRow,
    SecureObjectRecord,
    SecureObjectUnreadable,  # noqa: F401  # deliberate re-export: consumers import it from this module
)
from ._secure_object_row_codec import (
    secure_object_list_item_from_raw_row,
    secure_object_record_from_row,
    write_revision_metadata,
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

    _coerce_raw_bytes = staticmethod(coerce_raw_bytes)
    _parse_revision_ancestor_ids = staticmethod(parse_revision_ancestor_ids)
    _build_revision_ancestor_ids = staticmethod(build_revision_ancestor_ids)

    def _ensure_quarantine_table(self) -> None:
        """Create the quarantine archive table with the secure-object metadata shape."""
        ensure_quarantine_table(self._engine)

    @property
    def namespace_registry(self) -> StorageHierarchyRegistry | None:
        """Return the :class:`~adapters.persistence.storage.StorageHierarchyRegistry` bound here, if any."""
        return self._namespace_registry

    @property
    def engine(self) -> Engine:
        """Return the bound SQLAlchemy :class:`~sqlalchemy.engine.Engine`.

        Exposed so a sibling plaintext ORM table (e.g. a derived, non-sensitive
        routing index) can be written in the SAME database file and, where the
        driver supports it, the same transaction as this repository's encrypted
        rows -- without duplicating the bucket-to-engine routing this repository
        already resolved at construction.
        """
        return self._engine

    def _registered_namespace_definition(self, namespace: str) -> SecureObjectNamespaceDefinition | None:
        """Return the registry contract for ``namespace`` when policy is bound."""
        if is_former_product_namespace(namespace):
            raise StorageValidationError(
                translated_message="errors.storage.namespace.unregistered",
                context={"namespace": namespace, "reason": "former_product_namespace"},
            )
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
        object_key: str | None = None,
    ) -> None:
        definition = self._registered_namespace_definition(namespace)
        if definition is None:
            return
        if object_key is not None:
            # ``save_with_raw_key`` passes ``None``: it addresses a row by a
            # pre-computed HMAC digest whose natural key was already lost, so
            # there is no key left to check against the declared grammar.
            self._enforce_registered_object_key(definition, object_key)
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

    @staticmethod
    def _enforce_registered_object_key(
        definition: SecureObjectNamespaceDefinition,
        object_key: str,
    ) -> None:
        """Refuse an object key the namespace's declared grammar does not admit.

        The registry declares a natural-key grammar per namespace. Until this
        gate existed the declaration was documentation: a singleton namespace
        such as the invoice catalogue accepted any key, so a valid envelope
        written under a mistyped key round-tripped through raw storage while
        the owning repository -- which addresses the singleton by its canonical
        key -- reported the record absent. The row was orphaned, not refused.
        """
        try:
            definition.validate_object_key(object_key)
        except NamespaceRegistryError as exc:
            raise StorageValidationError(
                translated_message="errors.storage.namespace.object_key_grammar_mismatch",
                context={
                    "namespace": definition.namespace,
                    "object_key_grammar": definition.object_key_grammar,
                    "reason": str(exc),
                },
            ) from exc

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
        if definition is None or schema_version == definition.schema_version:
            return
        ensure_schema_version_readable(
            namespace=namespace,
            schema_version=schema_version,
            current_version=definition.schema_version,
        )

    def _check_session_freshness(self, namespace: str | None = None) -> None:
        """Refuse the operation when the active profile session is no longer valid.

        Polls :func:`evaluate_idle` against the live
        :class:`BucketSession` registered in the active-session
        ContextVar. When the session is sealed or past its deadline,
        raises :class:`SessionExpiredError` (translated by the CLI
        error decorator into a refusal that names ``aeat config
        unlock`` as the next action). On a fresh session,
        calls :meth:`~adapters.persistence.storage.BucketSession.touch` to roll the deadline
        forward by the configured idle window — the operator's
        active session remains usable for the next window's
        duration without re-authentication.

        Runtime-bound repositories also refuse stale handles whose active
        session changed bucket or fell back to the unsecured backend after
        construction. No-op when no session is bound and this repository is
        not runtime-bound; bootstrap-exempt verbs rely on that direct mode.
        """
        if namespace is not None:
            self._registered_namespace_definition(namespace)

        from ..errors import SessionExpiredError
        from ..master_key import current_active_bucket_session, evaluate_idle
        from ..runtime import _runtime_not_ready_error

        session = current_active_bucket_session()
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
                "the active profile session has expired; run `aeat config login NAME` to re-activate.",
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
        self._check_session_freshness(namespace)
        with session_scope(self._engine) as session:
            row_id = session.execute(
                select(_orm.SecureObjectRow.id).where(
                    _orm.SecureObjectRow.namespace == namespace,
                    _orm.SecureObjectRow.object_key == object_key,
                ),
            ).scalar_one_or_none()
            return row_id is not None

    def exists_by_raw_key(self, namespace: str, hashed_object_key: bytes) -> bool:
        """Return whether ``namespace`` carries a row with this raw HMAC digest.

        Used by the archive restore pipeline when the natural key was
        not present in the source bundle. Same
        master-key constraint as
        :meth:`~adapters.persistence.storage.SecureObjectRepository.save_with_raw_key`.
        """
        self._check_session_freshness(namespace)
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
                ),
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
                "ORDER BY namespace, object_key",
            ).execution_options(yield_per=batch_size)
            for raw in session.execute(stmt):
                written_at_raw = raw.written_at
                if isinstance(written_at_raw, str):
                    written_at_value = datetime.fromisoformat(written_at_raw)
                else:
                    written_at_value = written_at_raw
                # Re-attach UTC, matching the record and metadata read paths.
                # The raw surface exists to be fed back through
                # ``save_with_raw_key`` when restoring an archive bundle, and
                # that write boundary admits only UTC-aware instants -- a
                # naive value here would make a bundle unrestorable.
                written_at_value = coerce_utc_aware(written_at_value)
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
                    select(_orm.SecureObjectRow.namespace).distinct().order_by(_orm.SecureObjectRow.namespace),
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
        -- and intentionally bypasses the classification, schema-version,
        and namespace-registration contracts that consumer reads enforce.
        It probes over whatever namespaces are physically present in the
        table (as surfaced by :meth:`list_namespaces`), including orphan,
        legacy, and unregistered ones -- those are precisely the rows a
        repair diagnostic exists to find -- so it runs the session /
        route freshness check but not the namespace-registration check.
        Used by ``aeat config repair`` to surface namespaces holding rows
        from a prior keychain master-key generation.
        """
        self._check_session_freshness()
        return _probe_namespace_integrity(self._engine, namespace, logger=_log)

    def iter_namespace_decryptability(self, namespace: str) -> Iterator[SecureObjectDecryptabilityRow]:
        """Yield :class:`SecureObjectDecryptabilityRow` metadata for one namespace.

        This is the row-level companion to :meth:`probe_namespace_integrity`.
        It decrypts only to validate the AEAD tag, never returns plaintext, and
        exposes the HMAC lookup digest plus storage metadata needed by repair
        diagnostics. Like its namespace-level companion it is a crypto-layer
        probe over whatever namespaces are physically present, so it runs the
        session / route freshness check but not the namespace-registration
        check.
        """
        self._check_session_freshness()
        yield from _iter_namespace_decryptability(self._engine, namespace)

    def list_keys(self, namespace: str) -> tuple[str, ...]:
        """Return stored lookup digests under ``namespace`` as hex strings.

        Natural object keys are HMAC digested before storage and cannot be
        recovered from the index. Domain repositories that need natural IDs
        should iterate
        :meth:`~adapters.persistence.storage.SecureObjectRepository.list_records`
        and read IDs from decrypted payloads.
        """
        self._check_session_freshness(namespace)
        with session_scope(self._engine) as session:
            rows = session.execute(
                select(_orm.SecureObjectRow.object_key)
                .where(_orm.SecureObjectRow.namespace == namespace)
                .order_by(_orm.SecureObjectRow.object_key),
            ).scalars()
            return tuple(bytes(row).hex() for row in rows)

    def list_records(
        self,
        namespace: str,
        *,
        expected_class: SensitivityClass,
        max_supported_version: int,
    ) -> Iterator[SecureObjectRecord]:
        """Yield secure-object rows under ``namespace`` or fail on unreadable rows.

        The default listing path is fail-closed: it walks the namespace through
        :meth:`iter_records_with_failures` and raises
        :class:`~adapters.persistence.storage.SecureObjectUnreadableError` before
        yielding a partial readable subset. Use ``iter_records_with_failures`` for
        explicit mixed readable/unreadable diagnostics.

        Args:
            namespace: The storage namespace whose rows are listed.
            expected_class: The
                :class:`~adapters.persistence.storage.SensitivityClass`
                all rows in this namespace must carry.
            max_supported_version: The consumer's current ``schema_version``
                ceiling; a row above it, or below it without a complete
                registered upgrade chain, is treated as unreadable.
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

    def load_many(
        self,
        namespace: str,
        object_keys: Iterable[str],
        *,
        expected_class: SensitivityClass,
        max_supported_version: int,
    ) -> Iterator[SecureObjectRecord]:
        """Yield requested secure-object rows or fail closed on unreadable rows.

        This is the targeted equivalent of :meth:`list_records`: it performs a
        single ``WHERE namespace = ? AND object_key IN (...)`` read for the
        requested natural keys, decrypts matching rows, and raises
        :class:`SecureObjectUnreadableError` before yielding a partial readable
        subset if any matching row is unreadable. Missing keys are omitted,
        mirroring repeated :meth:`load` calls that return ``None`` for absent
        rows. ``expected_class`` is the :class:`SensitivityClass` every
        returned row must be classified under; a mismatch fails closed.
        """
        records: list[SecureObjectRecord] = []
        for item in self.iter_many_with_failures(
            namespace,
            object_keys,
            expected_class=expected_class,
            max_supported_version=max_supported_version,
        ):
            if isinstance(item, SecureObjectRecord):
                records.append(item)
                continue
            _log.debug(
                "secure_objects: refusing targeted batch load for namespace=%s because row id=%s is unreadable (%s)",
                namespace,
                item.row_id,
                item.reason,
            )
            raise SecureObjectUnreadableError(namespace, item.row_id)
        yield from records

    def iter_many_with_failures(
        self,
        namespace: str,
        object_keys: Iterable[str],
        *,
        expected_class: SensitivityClass,
        max_supported_version: int,
    ) -> Iterator[SecureObjectBatchLoadItem]:
        """Yield readable/unreadable outcomes for requested natural object keys.

        Rows are selected by raw HMAC digests derived from ``object_keys`` and
        returned in stored digest order. Missing keys produce no item, matching
        :meth:`load` returning ``None``. Present rows use the same
        classification, schema-version, AEAD, and revision-lineage checks as
        namespace scans. ``expected_class`` is the :class:`SensitivityClass`
        every yielded row must be classified under; a mismatch fails closed.
        """
        self._check_session_freshness(namespace)
        namespace_definition = self._enforce_registered_read_policy(
            namespace=namespace,
            expected_class=expected_class,
        )
        object_key_digests = tuple(dict.fromkeys(secure_object_key_digest(object_key) for object_key in object_keys))
        if not object_key_digests:
            return
        with session_scope(self._engine) as session:
            stmt = (
                text(
                    "SELECT id, object_key, classification, schema_version, "
                    "written_at, payload, revision_id, previous_revision_id, "
                    "payload_hash, ciphertext_hash, previous_payload_hash "
                    "FROM secure_objects WHERE namespace = :namespace "
                    "AND object_key IN :object_keys "
                    "ORDER BY object_key",
                )
                .bindparams(
                    bindparam("namespace", value=namespace),
                    bindparam("object_keys", value=object_key_digests, expanding=True),
                )
                .columns(
                    id=_orm.SecureObjectRow.__table__.c.id.type,
                    object_key=_orm.SecureObjectRow.__table__.c.object_key.type,
                    classification=_orm.SecureObjectRow.__table__.c.classification.type,
                    schema_version=_orm.SecureObjectRow.__table__.c.schema_version.type,
                    written_at=_orm.SecureObjectRow.__table__.c.written_at.type,
                )
            )
            for raw in session.execute(stmt):
                yield self._list_item_from_raw_row(
                    raw,
                    namespace=namespace,
                    expected_class=expected_class,
                    max_supported_version=max_supported_version,
                    namespace_definition=namespace_definition,
                )

    def iter_records_with_failures(
        self,
        namespace: str,
        *,
        expected_class: SensitivityClass,
        max_supported_version: int,
        batch_size: int = 256,
    ) -> Iterator[SecureObjectListItem]:
        """Yield a typed outcome per stored row under ``namespace``.

        Each row is represented by either a
        :class:`~adapters.persistence.storage.SecureObjectRecord` (the
        row decrypts cleanly and matches the consumer's classification and
        schema-version contract) or a
        :class:`~adapters.persistence.storage.SecureObjectUnreadable` (the
        on-wire ciphertext exists but cannot be decrypted under the current
        master key, or its metadata fails the consumer's contract).

        The iterator is fault-isolated: a failure on row ``N`` does not
        prevent rows ``> N`` from being inspected. Consumers count the
        failures and decide how to report them; nothing is auto-deleted.

        Args:
            namespace: The storage namespace whose rows are scanned.
            expected_class: The
                :class:`~adapters.persistence.storage.SensitivityClass`
                all rows in this namespace must carry; rows with a differing
                classification are yielded as
                :class:`~adapters.persistence.storage.SecureObjectUnreadable`.
            max_supported_version: The consumer's current ``schema_version``
                ceiling. Rows above it, or below it without a complete
                registered upgrade chain, are yielded
                as :class:`~adapters.persistence.storage.SecureObjectUnreadable`.
            batch_size: SQLAlchemy ``yield_per`` chunk size for the raw row
                scan. The default keeps memory bounded for large namespaces
                while preserving deterministic ``(object_key ASC)`` order.

        Yields:
            One ``SecureObjectListItem`` per stored row — either a
            :class:`~adapters.persistence.storage.SecureObjectRecord` or
            a :class:`~adapters.persistence.storage.SecureObjectUnreadable`.

        Raises:
            StorageValidationError: When ``batch_size`` is less than 1.
        """
        self._check_session_freshness(namespace)
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
                    "written_at, payload, revision_id, previous_revision_id, "
                    "payload_hash, ciphertext_hash, previous_payload_hash "
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
                .execution_options(stream_results=True, yield_per=batch_size)
            )
            for raw in session.execute(stmt):
                yield self._list_item_from_raw_row(
                    raw,
                    namespace=namespace,
                    expected_class=expected_class,
                    max_supported_version=max_supported_version,
                    namespace_definition=namespace_definition,
                )

    def _list_item_from_raw_row(
        self,
        raw: object,
        *,
        namespace: str,
        expected_class: SensitivityClass,
        max_supported_version: int,
        namespace_definition: SecureObjectNamespaceDefinition | None,
    ) -> SecureObjectBatchLoadItem:
        return secure_object_list_item_from_raw_row(
            raw,
            namespace=namespace,
            expected_class=expected_class,
            max_supported_version=max_supported_version,
            namespace_definition=namespace_definition,
            enforce_registered_row_schema=self._enforce_registered_row_schema,
        )

    def load(
        self,
        namespace: str,
        object_key: str,
        *,
        expected_class: SensitivityClass,
        max_supported_version: int,
    ) -> SecureObjectRecord | None:
        """Load and decrypt one secure-object row, returning ``None`` when absent.

        Returns a :class:`~adapters.persistence.storage.SecureObjectRecord`
        when the row is present and decrypts under the expected class/version.

        Args:
            namespace: The storage namespace to look in.
            object_key: The natural string key identifying the record.
            expected_class: The
                :class:`~adapters.persistence.storage.SensitivityClass`
                the consumer expects.
            max_supported_version: Highest ``schema_version`` the consumer supports.
        """
        self._check_session_freshness(namespace)
        namespace_definition = self._enforce_registered_read_policy(
            namespace=namespace,
            expected_class=expected_class,
        )
        with session_scope(self._engine) as session:
            row = session.execute(
                select(_orm.SecureObjectRow).where(
                    _orm.SecureObjectRow.namespace == namespace,
                    _orm.SecureObjectRow.object_key == object_key,
                ),
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
        if not writes:
            return
        for write in writes:
            self._enforce_registered_write_policy(
                namespace=write.namespace,
                classification=write.classification,
                schema_version=write.schema_version,
                object_key=write.object_key,
            )
        self._check_session_freshness()
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
                    _orm.SecureObjectRow.object_key,
                    _orm.SecureObjectRow.payload_hash,
                ).where(_orm.SecureObjectRow.namespace == namespace),
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
            for removal in deletions:
                session.execute(
                    delete(_orm.SecureObjectRow).where(
                        _orm.SecureObjectRow.namespace == removal.namespace,
                        _orm.SecureObjectRow.object_key == removal.hashed_object_key,
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
        # Single write funnel for save, save_many, apply_batch, and
        # save_with_raw_key. ``written_at`` is gated here rather than only on
        # the ``SecureObjectWrite`` DTO because the direct ``save`` and
        # ``save_with_raw_key`` boundaries take a bare ``datetime`` and never
        # construct that model. An offset-bearing instant loses its ``tzinfo``
        # in the SQLite column while the revision id was derived from the UTC
        # instant, so the row would commit and then fail its own read-time
        # self-consistency gate for good; refusing it keeps write and read
        # deriving one revision from one spelling.
        written_at = validate_utc_aware(written_at)
        (
            row_id,
            previous_revision_id,
            previous_revision_ancestor_ids,
            previous_payload_hash,
        ) = self._load_previous_secure_object_metadata(
            session,
            namespace=namespace,
            key=key,
            expected_revision_id=expected_revision_id,
        )
        # Encrypt the payload explicitly, binding the row identity into the AEAD
        # associated data so the ciphertext is valid only for this exact
        # (namespace, object_key, schema_version) row. ``key`` matches the value
        # the ``object_key`` HashedLookup column persists, so the digest used here
        # reconstructs identically on read.
        object_key_digest = secure_object_key_digest(key)
        payload_wire = encrypt_secure_object_payload(
            payload,
            associated_data=secure_object_payload_aad(namespace, object_key_digest, schema_version),
        )
        try:
            row_id = self._upsert_secure_object_row(
                session,
                row_id,
                namespace=namespace,
                key=key,
                classification=classification,
                schema_version=schema_version,
                written_at=written_at,
                payload_wire=payload_wire,
                expected_revision_id=expected_revision_id,
            )
            write_revision_metadata(
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
            if expected_revision_id is not None and expected_revision_id == ABSENT_SECURE_OBJECT_REVISION_ID:
                raise self._revision_conflict(
                    namespace=namespace,
                    expected_revision_id=expected_revision_id,
                    current_revision_id=None,
                ) from exc
            raise RepositoryError(
                context={
                    "namespace": namespace,
                    "error_type": type(exc.orig).__name__,
                },
                translated_message="errors.fail.fail_storage_secure_object_upsert",
            ) from exc

    def _load_previous_secure_object_metadata(
        self,
        session: Session,
        *,
        namespace: str,
        key: str | bytes,
        expected_revision_id: str | None,
    ) -> tuple[int | None, str | None, tuple[str, ...], str | None]:
        """Load the existing row's revision metadata for a save.

        Returns ``(row_id, previous_revision_id, previous_revision_ancestor_ids,
        previous_payload_hash)``; ``row_id`` is ``None`` when no row exists.
        Raises a revision conflict when a compare-and-swap write expects an
        existing revision but the row is absent.
        """
        row_id = session.execute(
            select(_orm.SecureObjectRow.id).where(
                _orm.SecureObjectRow.namespace == namespace,
                _orm.SecureObjectRow.object_key == key,
            ),
        ).scalar_one_or_none()
        if row_id is not None:
            previous_metadata = session.execute(
                select(
                    _orm.SecureObjectRow.revision_id,
                    _orm.SecureObjectRow.revision_ancestor_ids,
                    _orm.SecureObjectRow.payload_hash,
                ).where(_orm.SecureObjectRow.id == row_id),
            ).one()
            previous_revision_ancestor_ids = self._parse_revision_ancestor_ids(previous_metadata.revision_ancestor_ids)
            # The stored plaintext hash is always present from birth; the payload
            # column is now AEAD wire bytes, so there is no plaintext to fall back
            # on (and hashing the ciphertext would be meaningless).
            return (
                row_id,
                previous_metadata.revision_id,
                previous_revision_ancestor_ids,
                previous_metadata.payload_hash,
            )
        if expected_revision_id is not None and expected_revision_id != ABSENT_SECURE_OBJECT_REVISION_ID:
            raise self._revision_conflict(
                namespace=namespace,
                expected_revision_id=expected_revision_id,
                current_revision_id=None,
            )
        return None, None, (), None

    def _upsert_secure_object_row(
        self,
        session: Session,
        row_id: int | None,
        *,
        namespace: str,
        key: str | bytes,
        classification: SensitivityClass,
        schema_version: int,
        written_at: datetime,
        payload_wire: bytes,
        expected_revision_id: str | None,
    ) -> int:
        """Insert a new secure-object row or update the existing one, returning its id.

        Raises a revision conflict when a compare-and-swap update matches no row.
        """
        if row_id is None:
            row = _orm.SecureObjectRow(
                namespace=namespace,
                object_key=key,
                classification=classification.value,
                schema_version=schema_version,
                written_at=written_at,
                payload=payload_wire,
            )
            session.add(row)
            session.flush()
            return row.id
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
                    payload=payload_wire,
                ),
            ),
        )
        if expected_revision_id is not None and result.rowcount != 1:
            current_revision_id = session.execute(
                select(_orm.SecureObjectRow.revision_id).where(_orm.SecureObjectRow.id == row_id),
            ).scalar_one_or_none()
            raise self._revision_conflict(
                namespace=namespace,
                expected_revision_id=expected_revision_id,
                current_revision_id=current_revision_id,
            )
        session.flush()
        return row_id

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
        self._check_session_freshness(namespace)
        # Resolve the row id through the ORM so the HashedLookup column
        # binding hashes ``object_key`` consistently with the rest of
        # the repository, then read the raw row through ``text()`` so
        # the encrypted payload column is not auto-decrypted.
        with session_scope(self._engine) as session:
            row_id = session.execute(
                select(_orm.SecureObjectRow.id).where(
                    _orm.SecureObjectRow.namespace == namespace,
                    _orm.SecureObjectRow.object_key == object_key,
                ),
            ).scalar_one_or_none()
            if row_id is None:
                return None
            stmt = (
                text(
                    "SELECT classification, schema_version, written_at, payload FROM secure_objects WHERE id = :row_id",
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
            # Re-attach UTC exactly as the record read path does, so peeking a
            # row and loading it report the same instant rather than an aware
            # and a naive spelling of it.
            written_at=coerce_utc_aware(raw.written_at),
            byte_length=len(bytes(raw.payload)),
        )

    def delete(self, namespace: str, object_key: str) -> bool:
        """Delete one object if it exists."""
        self._check_session_freshness(namespace)
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
                    ),
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
        return secure_object_record_from_row(
            row,
            expected_class=expected_class,
            max_supported_version=max_supported_version,
            namespace_definition=namespace_definition,
            enforce_registered_row_schema=self._enforce_registered_row_schema,
        )
