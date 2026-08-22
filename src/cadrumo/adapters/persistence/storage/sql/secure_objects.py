"""Encrypted SQL byte-object repository for sensitive application payloads."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from datetime import datetime
from typing import Any, NamedTuple, Protocol, cast

from sqlalchemy import Engine, Table, bindparam, delete, insert, inspect, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .....core import ABSENT_SECURE_OBJECT_REVISION_ID, DEFAULT_WRITE_PROVENANCE, SecureObjectWrite
from .....core.classification import SensitivityClass
from .....core.external_constants import UTF_8_ENCODING
from .....core.hashing import sha256_hex
from .....core.i18n import tr
from .....core.logging import get_logger
from .....core.time import coerce_utc_aware, validate_utc_aware
from .....core.time import now as _utc_now
from .._namespace_registry import (
    SecureObjectNamespaceDefinition,
    StorageHierarchyRegistry,
    is_former_product_namespace,
)
from .._runtime_readiness import StorageRuntimeReadinessCode, runtime_not_ready_error
from .._schema_lineage import ensure_schema_version_readable, inner_envelope_classification_is_expected
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
from ._orm import SecureObjectRow
from ._secure_object_crypto import derive_revision_id
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
    SecureObjectUnreadable,  # deliberate re-export: consumers import it from this module
)
from ._secure_object_row_codec import (
    secure_object_list_item_from_raw_row,
    secure_object_record_from_row,
)
from ._secure_object_schema import (
    build_revision_ancestor_ids,
    coerce_raw_bytes,
    ensure_quarantine_table,
    parse_revision_ancestor_ids,
)
from .engine import get_engine
from .session import session_scope

__all__ = ["SecureObjectUnreadable"]

_log = get_logger(__name__)

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


class SecureObjectMigrationTarget(NamedTuple):
    """One explicitly governed row participating in an atomic schema cutover."""

    namespace: str
    object_key: str
    expected_class: SensitivityClass
    current_version: int


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

        local_table = inspect(SecureObjectRow).local_table
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

    @contextmanager
    def guarded_session_scope(self) -> Iterator[Session]:
        """Yield a session over this repository's engine, session-checked first.

        The counterpart to :attr:`engine` for a sibling plaintext table. Taking
        the engine directly is the one route into this database that skips
        :meth:`_check_session_freshness`, which every operation on this
        repository otherwise applies -- so a caller reading a routing index
        through a raw scope reads after a session seal, an idle expiry, or a
        move to another bucket, with nothing to stop it.

        The existing callers are safe only because each happens to perform a
        guarded load first. That is protection by call ORDER: it holds until
        someone adds an entry point that reaches the raw read first, and
        nothing states the ordering or would notice it changing. This method
        makes the check structural rather than incidental.

        No namespace is passed: a sibling table is not a secure-object
        namespace, so only the session half of the check applies.
        """
        self._check_session_freshness()
        with session_scope(self._engine) as session:
            yield session

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
        if not inner_envelope_classification_is_expected(classification, definition.sensitivity):
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
        if not inner_envelope_classification_is_expected(expected_class, definition.sensitivity):
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
        calls :meth:`~adapters.persistence.storage.master_key.BucketSession` to roll the deadline
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
        from ..master_key import current_active_bucket_session, evaluate_idle, session_serves_bucket

        session = current_active_bucket_session()
        if session is None:
            if self._require_secure_active_session:
                raise runtime_not_ready_error(StorageRuntimeReadinessCode.NO_ACTIVE_SESSION)
            return
        now = _utc_now()
        outcome = evaluate_idle(session=session, now=now)
        if outcome.expired:
            raise SessionExpiredError(
                "the active profile session has expired; run `aeat config login NAME` to re-activate.",
            )
        if self._require_secure_active_session and session.unsecured_backend:
            raise runtime_not_ready_error(StorageRuntimeReadinessCode.UNSECURED_BACKEND)
        if self._active_session_bucket_id is not None and not session_serves_bucket(
            session, self._active_session_bucket_id
        ):
            raise runtime_not_ready_error(StorageRuntimeReadinessCode.SESSION_CHANGED)
        session.touch(now)

    def exists(self, namespace: str, object_key: str) -> bool:
        """Return whether ``namespace`` / ``object_key`` is present."""
        return object_key in self.exists_many(namespace, (object_key,))

    def exists_many(self, namespace: str, object_keys: Iterable[str]) -> frozenset[str]:
        """Return the subset of ``object_keys`` present in ``namespace``.

        The set-based companion of :meth:`exists`, and the implementation
        behind it: one indexed ``IN (...)`` read per key slice answers the
        whole membership question, where per-key :meth:`exists` calls cost
        one session and one statement each — the dominant cost of a bulk
        content-addressed ingest that deduplicates against what is already
        stored. Natural keys are HMAC-digested exactly as the ``object_key``
        column stores them, so membership is decided on the digest and
        reported back as the caller's natural keys. Nothing is decrypted.
        """
        self._check_session_freshness(namespace)
        digest_to_key = {secure_object_key_digest(key): key for key in object_keys}
        if not digest_to_key:
            return frozenset[str]()
        present: set[str] = set()
        digests = tuple(digest_to_key)
        with session_scope(self._engine) as session:
            for start in range(0, len(digests), _OBJECT_KEY_SELECT_CHUNK):
                rows = session.execute(
                    select(SecureObjectRow.object_key).where(
                        SecureObjectRow.namespace == namespace,
                        SecureObjectRow.object_key.in_(
                            digests[start : start + _OBJECT_KEY_SELECT_CHUNK],
                        ),
                    ),
                ).scalars()
                for stored in rows:
                    key = digest_to_key.get(stored)
                    if key is not None:
                        present.add(key)
        return frozenset(present)

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
                select(SecureObjectRow.id).where(
                    SecureObjectRow.namespace == namespace,
                    SecureObjectRow.object_key == hashed_object_key,
                ),
            ).scalar_one_or_none()
            return row_id is not None

    def iter_all_records_raw(
        self,
        *,
        namespace: str | None = None,
        batch_size: int = 256,
    ) -> Iterator[SecureObjectRawRow]:
        """Yield every stored row as a :class:`SecureObjectRawRow` without decryption.

        Walks every row in `secure_objects` ordered by `(namespace, object_key)`
        without attempting to decrypt the payload. The query bypasses
        the encrypted-column type decorators so rows sealed under a
        rotated master key still surface verbatim — this is what the
        outbound sync coordinator's ciphertext-layer mirror
        consumes, mirroring on-wire ciphertext to a remote storage
        provider without ever decrypting domain data.

        Args:
            namespace: Optional exact namespace filter applied by SQL before
                iteration. ``None`` preserves the archive-wide traversal.
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
            projection = (
                "SELECT id, namespace, object_key, classification, schema_version, "
                "written_at, payload, revision_id, previous_revision_id, revision_ancestor_ids, previous_payload_hash, "
                "payload_hash, ciphertext_hash, revision_written_at, write_provenance, source_event_id "
                "FROM secure_objects "
            )
            if namespace is None:
                stmt = text(projection + "ORDER BY namespace, object_key")
            else:
                stmt = text(projection + "WHERE namespace = :namespace ORDER BY namespace, object_key")
            stmt = stmt.execution_options(yield_per=batch_size)
            parameters = {"namespace": namespace} if namespace is not None else {}
            for raw in session.execute(stmt, parameters):
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
                    write_provenance=raw.write_provenance,
                    source_event_id=raw.source_event_id,
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
                    select(SecureObjectRow.namespace).distinct().order_by(SecureObjectRow.namespace),
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
                select(SecureObjectRow.object_key)
                .where(SecureObjectRow.namespace == namespace)
                .order_by(SecureObjectRow.object_key),
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
        :class:`~adapters.persistence.storage.errors.SecureObjectUnreadableError` before
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

    def migrate_many_atomically(
        self,
        namespace: str,
        object_keys: Iterable[str],
        *,
        expected_class: SensitivityClass,
        current_version: int,
        validate_upgraded_payloads: Callable[[Mapping[str, bytes]], None],
        write_provenance: str,
    ) -> Mapping[str, SecureObjectRecord]:
        """Validate every upgraded payload, then persist all replacements atomically.

        Older rows are decrypted and chain-upgraded through the normal read
        policy.  The caller receives the complete natural-keyed payload set in
        ``validate_upgraded_payloads`` before any replacement is written.  Only
        after that callback succeeds are all older rows replaced in one
        compare-and-swap batch, so a malformed sibling or concurrent write
        leaves every original row intact.
        """
        targets = tuple(
            SecureObjectMigrationTarget(namespace, key, expected_class, current_version)
            for key in dict.fromkeys(object_keys)
        )
        records = self.migrate_targets_atomically(
            targets,
            validate_upgraded_payloads=lambda payloads: validate_upgraded_payloads(
                {key: payload for (_namespace, key), payload in payloads.items()}
            ),
            write_provenance=write_provenance,
        )
        return {key: record for (_namespace, key), record in records.items()}

    def migrate_targets_atomically(
        self,
        targets: Sequence[SecureObjectMigrationTarget],
        *,
        validate_upgraded_payloads: Callable[[Mapping[tuple[str, str], bytes]], None],
        write_provenance: str,
    ) -> Mapping[tuple[str, str], SecureObjectRecord]:
        """Validate and CAS-replace an explicit cross-namespace target set once."""
        unique_targets = tuple(dict.fromkeys(targets))
        target_by_stored_key = self._migration_targets_by_stored_key(unique_targets)
        stored_versions = self._migration_stored_versions(target_by_stored_key)
        records = self._load_migration_records(unique_targets)
        old_targets = self._old_migration_targets(unique_targets, records, stored_versions)
        if not old_targets:
            return records
        validate_upgraded_payloads({key: record.payload for key, record in records.items()})
        self._apply_migration_targets(old_targets, records, write_provenance)
        return records

    @staticmethod
    def _migration_targets_by_stored_key(
        targets: Sequence[SecureObjectMigrationTarget],
    ) -> dict[tuple[str, bytes], SecureObjectMigrationTarget]:
        return {(target.namespace, secure_object_key_digest(target.object_key)): target for target in targets}

    def _migration_stored_versions(
        self,
        target_by_stored_key: Mapping[tuple[str, bytes], SecureObjectMigrationTarget],
    ) -> dict[tuple[str, bytes], int]:
        targets_by_namespace: dict[str, list[SecureObjectMigrationTarget]] = {}
        for target in target_by_stored_key.values():
            targets_by_namespace.setdefault(target.namespace, []).append(target)
        versions: dict[tuple[str, bytes], int] = {}
        for namespace, targets in targets_by_namespace.items():
            versions_by_key = self.peek_many_schema_versions(namespace, (target.object_key for target in targets))
            versions.update(
                ((namespace, secure_object_key_digest(object_key)), schema_version)
                for object_key, schema_version in versions_by_key.items()
            )
        return versions

    def _load_migration_records(
        self,
        targets: Sequence[SecureObjectMigrationTarget],
    ) -> dict[tuple[str, str], SecureObjectRecord]:
        records: dict[tuple[str, str], SecureObjectRecord] = {}
        targets_by_contract: dict[tuple[str, SensitivityClass, int], list[SecureObjectMigrationTarget]] = {}
        for target in targets:
            contract = (target.namespace, target.expected_class, target.current_version)
            targets_by_contract.setdefault(contract, []).append(target)
        for (namespace, expected_class, current_version), contract_targets in targets_by_contract.items():
            object_key_by_digest = {
                secure_object_key_digest(target.object_key): target.object_key for target in contract_targets
            }
            for record in self._load_many_for_migration(
                namespace,
                (target.object_key for target in contract_targets),
                expected_class=expected_class,
                max_supported_version=current_version,
            ):
                object_key = object_key_by_digest[bytes(record.object_key)]
                records[(namespace, object_key)] = record
        return records

    def _load_many_for_migration(
        self,
        namespace: str,
        object_keys: Iterable[str],
        *,
        expected_class: SensitivityClass,
        max_supported_version: int,
    ) -> Iterator[SecureObjectRecord]:
        """Batch exact migration targets while preserving validation exceptions."""
        self._check_session_freshness(namespace)
        namespace_definition = self._enforce_registered_read_policy(
            namespace=namespace,
            expected_class=expected_class,
        )
        object_key_digests = tuple(dict.fromkeys(secure_object_key_digest(key) for key in object_keys))
        if not object_key_digests:
            return
        with session_scope(self._engine) as session:
            rows = session.execute(
                select(SecureObjectRow)
                .where(
                    SecureObjectRow.namespace == namespace,
                    SecureObjectRow.object_key.in_(object_key_digests),
                )
                .order_by(SecureObjectRow.object_key),
            ).scalars()
            for row in rows:
                yield self._record_from_row(
                    row,
                    expected_class=expected_class,
                    max_supported_version=max_supported_version,
                    namespace_definition=namespace_definition,
                )

    @staticmethod
    def _old_migration_targets(
        targets: Sequence[SecureObjectMigrationTarget],
        records: Mapping[tuple[str, str], SecureObjectRecord],
        stored_versions: Mapping[tuple[str, bytes], int],
    ) -> tuple[SecureObjectMigrationTarget, ...]:
        return tuple(
            target
            for target in targets
            if (record := records.get((target.namespace, target.object_key))) is not None
            and stored_versions.get((target.namespace, record.object_key), target.current_version)
            < target.current_version
        )

    def _apply_migration_targets(
        self,
        targets: Sequence[SecureObjectMigrationTarget],
        records: Mapping[tuple[str, str], SecureObjectRecord],
        write_provenance: str,
    ) -> None:
        self.apply_batch(
            tuple(
                SecureObjectWrite(
                    namespace=target.namespace,
                    object_key=target.object_key,
                    classification=target.expected_class,
                    schema_version=target.current_version,
                    written_at=_utc_now(),
                    payload=records[(target.namespace, target.object_key)].payload,
                    write_provenance=write_provenance,
                    expected_revision_id=records[(target.namespace, target.object_key)].revision_id,
                )
                for target in targets
            )
        )

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
                    id=SecureObjectRow.__table__.c.id.type,
                    object_key=SecureObjectRow.__table__.c.object_key.type,
                    classification=SecureObjectRow.__table__.c.classification.type,
                    schema_version=SecureObjectRow.__table__.c.schema_version.type,
                    written_at=SecureObjectRow.__table__.c.written_at.type,
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
        :class:`~adapters.persistence.storage.sql.SecureObjectRecord` (the
        row decrypts cleanly and matches the consumer's classification and
        schema-version contract) or a
        :class:`~adapters.persistence.storage.sql._secure_object_records.SecureObjectUnreadable` (the
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
                :class:`~adapters.persistence.storage.sql._secure_object_records.SecureObjectUnreadable`.
            max_supported_version: The consumer's current ``schema_version``
                ceiling. Rows above it, or below it without a complete
                registered upgrade chain, are yielded
                as :class:`~adapters.persistence.storage.sql._secure_object_records.SecureObjectUnreadable`.
            batch_size: SQLAlchemy ``yield_per`` chunk size for the raw row
                scan. The default keeps memory bounded for large namespaces
                while preserving deterministic ``(object_key ASC)`` order.

        Yields:
            One ``SecureObjectListItem`` per stored row — either a
            :class:`~adapters.persistence.storage.sql.SecureObjectRecord` or
            a :class:`~adapters.persistence.storage.sql._secure_object_records.SecureObjectUnreadable`.

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
                    id=SecureObjectRow.__table__.c.id.type,
                    object_key=SecureObjectRow.__table__.c.object_key.type,
                    classification=SecureObjectRow.__table__.c.classification.type,
                    schema_version=SecureObjectRow.__table__.c.schema_version.type,
                    written_at=SecureObjectRow.__table__.c.written_at.type,
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

        Returns a :class:`~adapters.persistence.storage.sql.SecureObjectRecord`
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
                select(SecureObjectRow).where(
                    SecureObjectRow.namespace == namespace,
                    SecureObjectRow.object_key == object_key,
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
                select(SecureObjectRow.id).where(
                    SecureObjectRow.namespace == namespace,
                    SecureObjectRow.object_key == object_key,
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
                    classification=SecureObjectRow.__table__.c.classification.type,
                    schema_version=SecureObjectRow.__table__.c.schema_version.type,
                    written_at=SecureObjectRow.__table__.c.written_at.type,
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

    def peek_many_schema_versions(self, namespace: str, object_keys: Iterable[str]) -> Mapping[str, int]:
        """Return schema versions for exact natural keys without loading ciphertext."""
        self._check_session_freshness(namespace)
        keys = tuple(dict.fromkeys(object_keys))
        if not keys:
            return dict[str, int]()
        key_by_digest = {secure_object_key_digest(key): key for key in keys}
        with session_scope(self._engine) as session:
            stmt = (
                text(
                    "SELECT object_key, schema_version "
                    "FROM secure_objects WHERE namespace = :namespace AND object_key IN :object_keys",
                )
                .bindparams(
                    bindparam("namespace", value=namespace),
                    bindparam("object_keys", value=tuple(key_by_digest), expanding=True),
                )
                .columns(
                    object_key=SecureObjectRow.__table__.c.object_key.type,
                    schema_version=SecureObjectRow.__table__.c.schema_version.type,
                )
            )
            rows = session.execute(stmt).all()
        return {key_by_digest[bytes(raw.object_key)]: int(raw.schema_version) for raw in rows}

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
                    delete(SecureObjectRow).where(
                        SecureObjectRow.namespace == namespace,
                        SecureObjectRow.object_key == object_key,
                    ),
                ),
            )
            return bool(result.rowcount and result.rowcount > 0)

    def _record_from_row(
        self,
        row: SecureObjectRow,
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
