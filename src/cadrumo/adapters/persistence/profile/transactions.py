"""Encrypted SQL repository with atomic per-bucket transaction reads and writes."""

from __future__ import annotations

import weakref
from collections.abc import Iterable, Mapping
from datetime import date
from typing import TYPE_CHECKING

from pydantic import ValidationError
from sqlalchemy import func, select

from ....core.config import load_settings
from ....core.errors.hierarchy import InternalInvariantError
from ....core.external_constants import UTF_8_ENCODING
from ....core.hashing import sha256_hex
from ....core.logging import get_logger
from ....core.time.clock import now
from ....domain.bienes_inversion.register import (
    BienesInversionIvaRegister,
)
from ....domain.calculations.registry.governed_fact_scope import governed_facts_in_scope
from ....domain.transactions.date_partition import (
    LedgerDatePartition,
    OutOfWindowTransactionIndexEntry,
    OutOfWindowTransactionSummary,
)
from ....domain.transactions.dates import transaction_filing_date
from ....domain.transactions.errors import LedgerStorageError, StoredTransactionDriftError
from ....domain.transactions.models import (
    Transaction,
    TransactionCatalogue,
    require_no_figures_without_business,
    validate_authenticated_stored_transaction_json,
    validate_stored_transaction_json,
)
from ....domain.transactions.repository import transaction_index_object_key, transaction_object_key
from ....domain.transactions.withheld_figures import figures_held_without_business, withhold_figures_without_business
from ..storage.errors import (
    ClassificationError,
    EnvelopeVersionError,
    SecureObjectRowIdentityError,
)
from ..storage.secure_object_namespaces import (
    PROFILE_BIENES_INVERSION_IVA_REGISTER_NAMESPACE,
    TRANSACTION_CATALOGUE_NAMESPACE,
)
from ..storage.sql.secure_objects import SecureObjectMigrationTarget
from ..storage.sql.tables import transaction_date_index_table
from .bienes_inversion import BienesInversionIvaRegisterRepository
from .transaction_authority_validation import validate_iva_authority_migration
from .transaction_date_index_storage import (
    date_index_candidate_ids,
    date_index_ids_and_count,
    date_routing_unchanged,
    sync_date_index_rows,
)
from .transaction_date_projection import (
    OUT_OF_WINDOW_ROW_PROJECTION_LIMIT,
    IndexedTransactionDates,
    catalogue_from_loaded_transactions,
    project_out_of_window_index_entries,
)
from .transaction_revision_guards import (
    absent_transaction_index_assertions,
    catalogue_revision_and_assertions,
    require_transaction_edit_link_identity,
    resolved_transaction_row_revisions,
)
from .transaction_row_contracts import (
    TransactionMembershipIndex,
    require_persisted_transaction_timestamps,
)
from .transaction_row_writes import (
    FigureDrop,
    membership_index_write,
    stored_rows_holding_figures,
    transaction_row_deletion,
    transaction_row_write,
    with_withheld_figure_trace,
)
from .transaction_storage_failures import translating_transaction_storage_failures

if TYPE_CHECKING:  # pragma: no cover — import-cycle guard
    from ....core.secure_object_write import SecureObjectRevisionAssertion, SecureObjectWrite
    from ..storage.envelope.contract import Envelope
    from ..storage.sql.secure_object_records import SecureObjectDeletion
    from ..storage.sql.secure_objects import SecureObjectRepository


_log = get_logger(__name__)


def _secure_objects_for_bucket(bucket_id: str) -> SecureObjectRepository:
    """Return the runtime-created secure-object repository for ``bucket_id``."""
    from ..storage.runtime_repository import secure_object_repository_for_bucket

    return secure_object_repository_for_bucket(bucket_id, load_settings())


class TransactionCatalogueRepository:
    """Repository over the encrypted SQL-backed transaction catalogue.

    Every instance is bound to one profile bucket via ``bucket_id``. The
    catalogue is stored as one secure-object row per transaction (keyed
    ``transaction:{bucket_id}:{transaction_id}``) inside the
    :data:`~adapters.persistence.storage.secure_object_namespaces.TRANSACTION_CATALOGUE_NAMESPACE`
    namespace, so two operator profiles never share transaction storage and a
    single-transaction mutation touches a single row. Each
    :class:`~domain.transactions.models.Transaction` payload and the bucket
    membership index are wrapped in
    :class:`~adapters.persistence.storage.envelope.contract.Envelope` before
    :class:`~adapters.persistence.storage.sql.secure_objects.SecureObjectRepository`
    persists them. The class exposes the concrete load/save implementation
    behind
    :class:`~domain.transactions.protocols.TransactionCatalogueRepositoryProtocol`.

    ``_serialized_hash_cache`` is a write-path optimization: it memoizes the
    stored-envelope SHA-256 of each loaded frozen
    :class:`~domain.transactions.models.Transaction`
    instance, populated once per row at :meth:`load` and consulted by
    :meth:`_reconcile` before re-serializing an untouched row.

    Keying is identity-based (``id(transaction)``), not value-based:
    ``Transaction``'s pydantic-generated ``__hash__`` is unusable as a dict key
    because :attr:`~domain.transactions.raw_transaction.RawTransaction.raw_fields` is stored as
    a ``mappingproxy`` (unhashable), which rules out a plain
    :class:`~weakref.WeakKeyDictionary` (it hashes the key object itself). A
    bare ``id()`` integer key alone would risk a GC-recycle hazard -- a
    collected instance's address could be reused by an
    unrelated object -- so each cache entry is paired with a
    :class:`~weakref.finalize` callback that evicts the ``id()`` entry the
    INSTANT its ``Transaction`` is garbage-collected, before the address could
    be recycled for a different object. ``Transaction`` is strict-frozen, so a
    content edit always produces a NEW instance rather than mutating the
    loaded one; the edited instance's ``id()`` is simply absent from the cache
    (a miss, correctly falling through to fresh serialize-and-hash). The cache
    never substitutes for the save-time ``namespace_payload_hashes`` store-side
    scan; it only skips re-deriving the FRESH-SERIALIZATION side of that
    comparison for rows the same process already loaded unchanged.

    ``_transaction_revision_cache`` is the corresponding read-path cache for
    immutable transaction rows. Targeted reads first query the stored revision
    ids without loading ciphertext and reuse a validated ``Transaction`` only
    while that exact revision remains current. A changed, deleted, or
    revision-less row is loaded and validated again, so the cache cannot hide
    an external writer or legacy payload.
    """

    def __init__(self, *, bucket_id: str, objects: SecureObjectRepository | None = None) -> None:
        """Bind the repository to ``bucket_id``, resolving the bucket store when ``objects`` is omitted."""
        self._bucket_id = bucket_id.strip()
        if not self._bucket_id:
            raise LedgerStorageError(
                "bucket_id must not be blank",
                context={"repository": "transaction_catalogue", "operation": "object_key"},
            )
        self._objects = objects or _secure_objects_for_bucket(self._bucket_id)
        self._serialized_hash_cache: dict[int, str] = {}
        self._transaction_revision_cache: dict[str, tuple[str, Transaction]] = {}

    @property
    def bucket_id(self) -> str:
        """Return the profile bucket id this repository is bound to."""
        return self._bucket_id

    def exists(self) -> bool:
        """Return whether this bucket holds any persisted transactions."""
        return bool(self._load_index_ids())

    def load_revision(self) -> str | None:
        """Return a digest that changes whenever this bucket's catalogue does, without decrypting rows.

        The digest covers the membership index's revision and every listed
        row's stored revision, so an added, removed or rewritten transaction
        each changes it. ``None`` means no stable revision can be stated -- a
        listed row is missing, or a row predates recorded revisions -- and a
        caller must then treat the catalogue as changed.
        """
        revision, _assertions = self._catalogue_revision_snapshot(include_assertions=False)
        return revision

    def revision_assertions(self, *, expected_revision_id: str) -> tuple[SecureObjectRevisionAssertion, ...]:
        """Prepare in-batch assertions for a previously read full catalogue."""
        from ....application.ledger.persistence_ports import LedgerPersistenceConflictError

        revision, assertions = self._catalogue_revision_snapshot(include_assertions=True)
        if revision is None or revision != expected_revision_id:
            raise LedgerPersistenceConflictError("transaction catalogue changed since its source read")
        return assertions

    @translating_transaction_storage_failures
    def load_revisioned(self) -> tuple[TransactionCatalogue, str]:
        """Return a catalogue whose entire decode is bracketed by one revision.

        Revision ids are append-only, so equal full-catalogue revisions before
        and after ``load`` prove that no transaction row or membership index
        changed while the decoded catalogue was assembled. Unstable or
        revision-less snapshots are retried briefly, then refused.
        """
        from ....application.ledger.persistence_ports import LedgerPersistenceConflictError

        for _attempt in range(3):
            before = self.load_revision()
            if before is None:
                continue
            catalogue = self.load()
            after = self.load_revision()
            if after is not None and before == after:
                return catalogue, before
        raise LedgerPersistenceConflictError("transaction catalogue changed while loading its snapshot")

    @translating_transaction_storage_failures
    def load(self) -> TransactionCatalogue:
        """Return the persisted catalogue, assembled from this bucket's rows.

        Each row is decoded as an authenticated stored row: the store decrypted
        it under its AEAD binding in this call, so the derived-id re-hash is
        skipped while every structural, field and registry check runs.
        :meth:`load_fully_validated` re-runs every admission check instead.

        The per-bucket membership index names exactly the transaction ids this
        bucket owns; only the rows whose digest the index lists are read, so a
        shared secure store never leaks another bucket's transactions.

        Returns:
            The deserialised :class:`TransactionCatalogue`, or a fresh empty
            instance when this bucket has no transactions.

        Raises:
            :class:`~adapters.persistence.storage.errors.ClassificationError`:
                If a row's inner envelope class is not
                ``TRANSACTION_CATALOGUE_NAMESPACE.sensitivity``.
            :class:`~adapters.persistence.storage.errors.EnvelopeVersionError`:
                If a row's inner envelope schema version is higher than the
                consumer supports.
            StoredTransactionDriftError: If a row payload fails pydantic schema
                validation on deserialization.
        """
        return self._load_catalogue(authenticated=True)

    @translating_transaction_storage_failures
    def load_fully_validated(self) -> TransactionCatalogue:
        """Return the persisted catalogue with every admission check re-run on every row.

        The explicit re-validation read: unlike :meth:`load`, it also re-derives
        each row's id from its raw record, so a stored row that no longer
        satisfies admission is refused here as schema drift.
        """
        return self._load_catalogue(authenticated=False)

    def _load_catalogue(self, *, authenticated: bool) -> TransactionCatalogue:
        """Assemble this bucket's catalogue, decoding rows as authenticated or in full."""
        from ..storage.crypto.encrypted_columns import secure_object_key_digest

        index_ids = self._load_index_ids()
        if not index_ids:
            return TransactionCatalogue.from_transactions([])
        transaction_keys = {
            transaction_id: transaction_object_key(self._bucket_id, transaction_id)
            for transaction_id in sorted(index_ids)
        }
        # An ordinary read never upgrades: a row below the current schema is
        # refused before any payload is decrypted, and the explicit IVA
        # authority cutover is the only path that migrates. Reading through the
        # migration machinery here re-scanned every row's version and could
        # never find one to migrate.
        records_by_digest = {
            bytes(record.object_key): record
            for record in self._objects.load_many_current(
                TRANSACTION_CATALOGUE_NAMESPACE.namespace,
                transaction_keys.values(),
                expected_class=TRANSACTION_CATALOGUE_NAMESPACE.sensitivity,
                current_version=TRANSACTION_CATALOGUE_NAMESPACE.schema_version,
                refuse_legacy=self._refuse_targeted_implicit_migration,
            )
        }
        transactions: list[Transaction] = []
        for transaction_id, object_key in transaction_keys.items():
            record = records_by_digest.get(secure_object_key_digest(object_key))
            if record is None:
                continue
            transaction = self._validated_catalogue_row(record.payload, transaction_id, authenticated=authenticated)
            self._assert_transaction_row_identity(transaction, expected_transaction_id=transaction_id)
            # Write-path cache: memoize the stored envelope's payload hash against this exact
            # loaded instance. An untouched row at save time is the SAME
            # object (frozen models never mutate in place), so ``_reconcile``
            # can reuse this hash instead of re-serializing the row.
            self._cache_serialized_hash(transaction, sha256_hex(record.payload))
            transactions.append(transaction)
        _log.debug(
            "loaded transaction catalogue bucket_id=%s entries=%d",
            self._bucket_id,
            len(transactions),
        )
        return catalogue_from_loaded_transactions(transactions)

    def _validated_catalogue_row(self, payload: bytes, transaction_id: str, *, authenticated: bool) -> Transaction:
        """Decode a current transaction row with all schema and classification refusals."""
        from ..storage.schema_lineage import (
            inner_envelope_classification_is_expected,
            inner_envelope_version_is_current,
        )

        # The row is parsed once, in JSON mode, which the envelope's
        # ``strict=True`` config needs for string -> datetime and string -> enum
        # coercion. The store decrypted it under its AEAD binding in the same
        # call, so an ordinary read decodes it as an authenticated stored row.
        envelope = self._decode_catalogue_row(payload, authenticated=authenticated)
        if not inner_envelope_classification_is_expected(
            envelope.classification, TRANSACTION_CATALOGUE_NAMESPACE.sensitivity
        ):
            # errors.integrity.integrity_storage_classification is this
            # adapters/persistence/profile layer's own classification-mismatch
            # key (shared with buckets.py at this same layer). It is
            # deliberately NOT merged with
            # application.user_profile.errors.repository_classification_mismatch
            # (see application/user_profile/repository.py) even though both
            # report the same abstract condition: that key belongs to a
            # different architectural layer (the application-layer profile
            # repository, not this raw secure-object storage adapter), and
            # unifying across the adapter/application boundary would blur
            # which layer owns the message.
            raise ClassificationError(
                context={
                    "namespace": TRANSACTION_CATALOGUE_NAMESPACE.namespace,
                    "object_key": transaction_object_key(self._bucket_id, transaction_id),
                    "bucket_id": self._bucket_id,
                    "classification": envelope.classification.value,
                    "expected": TRANSACTION_CATALOGUE_NAMESPACE.sensitivity.value,
                },
                translated_message="errors.integrity.integrity_storage_classification",
            )
        if not inner_envelope_version_is_current(
            envelope.schema_version, TRANSACTION_CATALOGUE_NAMESPACE.schema_version
        ):
            # The authenticated-row exemption covers only the current schema, so
            # a row of any other version is validated in full before it is refused.
            self._decode_catalogue_row(payload, authenticated=False)
            raise EnvelopeVersionError(
                context={
                    "namespace": TRANSACTION_CATALOGUE_NAMESPACE.namespace,
                    "object_key": transaction_object_key(self._bucket_id, transaction_id),
                    "bucket_id": self._bucket_id,
                    "schema_version": envelope.schema_version,
                    "expected": TRANSACTION_CATALOGUE_NAMESPACE.schema_version,
                },
                translated_message="errors.integrity.integrity_storage_envelope_version",
            )
        # A row stored before personal rows were refused business figures is
        # read without them; its bytes stay as stored until its next write.
        return withhold_figures_without_business(envelope.payload)

    def _decode_catalogue_row(self, payload: bytes, *, authenticated: bool) -> Envelope[Transaction]:
        """Decode one stored row, translating a validation failure into drift.

        ``authenticated`` selects the authenticated stored-row decode, which only
        a row the store decrypted in this call and written under the current
        schema version may use; every other row is validated in full.
        """
        from ..storage.envelope.contract import Envelope

        try:
            if authenticated:
                envelope = validate_authenticated_stored_transaction_json(Envelope[Transaction], payload)
            else:
                envelope = validate_stored_transaction_json(Envelope[Transaction], payload)
            # A row that lost its D6 lifecycle timestamps is refused rather than
            # returned with the defaults the decode stamped on it.
            require_persisted_transaction_timestamps(envelope.payload)
        except ValidationError as exc:
            if governed_facts_in_scope() is None:
                # A row validates against registry vocabulary, so a decode
                # attempted outside an authority operation cannot tell drift
                # from its own missing scope. Reporting drift here sent the
                # operator to repair data that may be perfectly current.
                raise InternalInvariantError(
                    "stored transaction decode requires an explicit authority operation or scope"
                ) from exc
            _log.error(
                "transaction row schema drift bucket_id=%s",
                self._bucket_id,
                exc_info=True,
            )
            raise StoredTransactionDriftError(self._bucket_id, exc) from exc
        return envelope

    def migrate_iva_deduction_authority(
        self,
        *,
        asset_profile_id: str,
    ) -> BienesInversionIvaRegister:
        """Migrate the catalogue and return its reciprocal Bienes authority."""
        if asset_profile_id != self._bucket_id:
            raise LedgerStorageError("transaction and bienes-inversion profiles must be identical")
        index_ids = self._load_index_ids(require_current=False)
        if not index_ids:
            return BienesInversionIvaRegisterRepository(bucket_id=asset_profile_id).load()
        index_key = transaction_index_object_key(self._bucket_id)
        transaction_keys = {
            transaction_id: transaction_object_key(self._bucket_id, transaction_id) for transaction_id in index_ids
        }

        bienes_definition = PROFILE_BIENES_INVERSION_IVA_REGISTER_NAMESPACE
        bienes_key = bienes_definition.require_default_object_key()

        self._objects.migrate_targets_atomically(
            (
                *(
                    SecureObjectMigrationTarget(
                        TRANSACTION_CATALOGUE_NAMESPACE.namespace,
                        key,
                        TRANSACTION_CATALOGUE_NAMESPACE.sensitivity,
                        TRANSACTION_CATALOGUE_NAMESPACE.schema_version,
                    )
                    for key in (index_key, *transaction_keys.values())
                ),
                SecureObjectMigrationTarget(
                    bienes_definition.namespace,
                    bienes_key,
                    bienes_definition.sensitivity,
                    bienes_definition.schema_version,
                ),
            ),
            validate_upgraded_payloads=lambda payloads: validate_iva_authority_migration(
                self._bucket_id,
                payloads,
                bienes_definition=bienes_definition,
                bienes_key=bienes_key,
                asset_profile_id=asset_profile_id,
            ),
            write_provenance="transaction-catalogue:iva-deduction-migration",
        )
        return BienesInversionIvaRegisterRepository(bucket_id=asset_profile_id).load()

    def save(self, catalogue: TransactionCatalogue) -> None:
        """Persist ``catalogue`` as per-transaction encrypted rows.

        Only rows whose content changed are rewritten; transactions removed from
        the catalogue are deleted. The whole diff commits atomically.

        Args:
            catalogue: The :class:`TransactionCatalogue` to persist.
        """
        writes, deletions, drops = self._reconcile(catalogue)
        self._objects.apply_batch((*writes, *self._with_withheld_figure_trace((), drops)), deletions)
        self._sync_date_index(catalogue)
        _log.info(
            "saved transaction catalogue bucket_id=%s entries=%d rewritten=%d deleted=%d",
            self._bucket_id,
            len(catalogue.transactions),
            len(writes),
            len(deletions),
        )

    def save_with_secure_object_writes(
        self,
        catalogue: TransactionCatalogue,
        extra_writes: tuple[SecureObjectWrite, ...],
    ) -> None:
        """Persist ``catalogue`` plus related secure objects in one unit of work.

        The per-transaction diff (changed rows + deletions) and ``extra_writes``
        (e.g. bucket-event history, invoice catalogue) commit atomically, so a
        ledger mutation and its co-emitted records remain all-or-nothing.

        Args:
            catalogue: The :class:`TransactionCatalogue` to persist.
            extra_writes: Additional secure object writes to commit atomically.
        """
        writes, deletions, drops = self._reconcile(catalogue)
        self._objects.apply_batch((*writes, *self._with_withheld_figure_trace(extra_writes, drops)), deletions)
        self._sync_date_index(catalogue)
        _log.info(
            "saved transaction catalogue bucket_id=%s entries=%d rewritten=%d deleted=%d extra_writes=%d",
            self._bucket_id,
            len(catalogue.transactions),
            len(writes),
            len(deletions),
            len(extra_writes),
        )

    @translating_transaction_storage_failures
    def save_if_revision_with_secure_object_writes(
        self,
        catalogue: TransactionCatalogue,
        *,
        expected_revision_id: str,
        extra_writes: tuple[SecureObjectWrite, ...],
    ) -> None:
        """Persist a full catalogue only while every loaded row is unchanged.

        The membership index and every row revision are asserted in the same
        serializable batch that writes the catalogue and its related secure
        objects. This prevents a stale full-catalogue diff from deleting a
        concurrent addition or overwriting a concurrent edit to another row.

        Parameter types: ``catalogue`` (:class:`~cadrumo.domain.transactions.models.TransactionCatalogue`).
        """
        from ....application.ledger.persistence_ports import LedgerPersistenceConflictError

        current_revision, assertions = self._catalogue_revision_snapshot(include_assertions=True)
        if current_revision is None or current_revision != expected_revision_id:
            raise LedgerPersistenceConflictError("transaction catalogue changed since the snapshot was loaded")
        writes, deletions, drops = self._reconcile(catalogue)
        self._objects.apply_batch(
            (*writes, *self._with_withheld_figure_trace(extra_writes, drops)), deletions, assertions=assertions
        )
        try:
            self._sync_date_index(catalogue)
        except Exception:
            # The index is a rebuildable routing cache. The guarded catalogue
            # and audit batch has committed; reporting failure now could invite
            # an unsafe retry of a successful split or other full-catalogue edit.
            _log.warning(
                "transaction date index refresh failed after committed catalogue write bucket_id=%s",
                self._bucket_id,
            )
        _log.info(
            "saved guarded transaction catalogue bucket_id=%s entries=%d rewritten=%d deleted=%d extra_writes=%d",
            self._bucket_id,
            len(catalogue.transactions),
            len(writes),
            len(deletions),
            len(extra_writes),
        )

    def _catalogue_revision_snapshot(
        self,
        *,
        include_assertions: bool,
    ) -> tuple[str | None, tuple[SecureObjectRevisionAssertion, ...]]:
        """Read the full revision digest and optional in-batch row assertions."""
        index_key = transaction_index_object_key(self._bucket_id)
        transaction_ids = tuple(sorted(self._load_index_ids()))
        row_keys = {
            transaction_id: transaction_object_key(self._bucket_id, transaction_id)
            for transaction_id in transaction_ids
        }
        revisions = self._objects.peek_many_revision_ids(
            TRANSACTION_CATALOGUE_NAMESPACE.namespace,
            (index_key, *row_keys.values()),
        )
        index_revision = revisions.get(index_key)
        if not transaction_ids and index_revision is None:
            assertions = absent_transaction_index_assertions(index_key, include_assertions)
            return sha256_hex(b"transaction-catalogue:absent"), assertions
        row_revisions = {transaction_id: revisions.get(row_keys[transaction_id]) for transaction_id in transaction_ids}
        if index_revision is None:
            return None, ()
        resolved_row_revisions = resolved_transaction_row_revisions(row_revisions)
        if resolved_row_revisions is None:
            return None, ()
        return catalogue_revision_and_assertions(
            index_key=index_key,
            index_revision=index_revision,
            row_keys=row_keys,
            row_revisions=resolved_row_revisions,
            include_assertions=include_assertions,
        )

    def replace_if_current_with_secure_object_writes(
        self,
        current: Transaction,
        replacement: Transaction,
        extra_writes: tuple[SecureObjectWrite, ...],
    ) -> None:
        """Atomically replace one opened row without rewriting other catalogue members.

        The opened value is compared with the encrypted row and its revision is
        carried into the batch. A concurrent change to that row, a collision
        with the new identity, or a concurrent membership-index write therefore
        rolls the whole transaction and its audit event back.
        """
        from ....core.secure_object_write import ABSENT_SECURE_OBJECT_REVISION_ID

        stored_row, old_revision = self._opened_stored_row(current)
        old_id = current.transaction_id
        new_id = replacement.transaction_id
        require_transaction_edit_link_identity(current, replacement)
        writes: list[SecureObjectWrite] = [
            transaction_row_write(
                bucket_id=self._bucket_id,
                transaction_id=new_id,
                written_at=replacement.modified_at,
                payload=self._serialise_transaction(replacement),
                expected_revision_id=(old_revision if old_id == new_id else ABSENT_SECURE_OBJECT_REVISION_ID),
            )
        ]
        deletions: tuple[SecureObjectDeletion, ...] = ()
        if old_id != new_id:
            writes.append(self._renamed_membership_index_write(old_id, new_id))
            deletions = (
                transaction_row_deletion(
                    bucket_id=self._bucket_id, transaction_id=old_id, expected_revision_id=old_revision
                ),
            )
        held = figures_held_without_business(stored_row)
        drops = {new_id: (held, replacement.modified_at)} if held else {}
        self._objects.apply_batch((*writes, *self._with_withheld_figure_trace(extra_writes, drops)), deletions)
        try:
            if date_routing_unchanged(current, replacement):
                # Non-routing edits leave the derived date cache unchanged.
                return
            self._sync_date_index(self.load())
        except Exception:
            # The index is a rebuildable routing cache. The guarded financial
            # and audit batch has committed; reporting a failed edit now would
            # invite an unsafe retry of a successful replacement.
            _log.warning("transaction date index refresh failed after committed edit bucket_id=%s", self._bucket_id)

    def _opened_stored_row(self, current: Transaction) -> tuple[Transaction, str]:
        """Return the stored row ``current`` was opened from and its revision, refusing a changed or absent row."""
        from ....application.ledger.persistence_ports import LedgerPersistenceConflictError
        from ..storage.envelope.contract import Envelope

        records = tuple(
            self._objects.load_many_current(
                TRANSACTION_CATALOGUE_NAMESPACE.namespace,
                (transaction_object_key(self._bucket_id, current.transaction_id),),
                expected_class=TRANSACTION_CATALOGUE_NAMESPACE.sensitivity,
                current_version=TRANSACTION_CATALOGUE_NAMESPACE.schema_version,
                refuse_legacy=self._refuse_targeted_implicit_migration,
            )
        )
        if len(records) != 1:
            raise LedgerPersistenceConflictError("opened transaction no longer exists")
        stored_row = validate_stored_transaction_json(Envelope[Transaction], records[0].payload).payload
        stored = withhold_figures_without_business(stored_row)
        if stored != current:
            raise LedgerPersistenceConflictError("transaction changed since it was opened")
        return stored_row, str(records[0].revision_id)

    def _renamed_membership_index_write(self, old_id: str, new_id: str) -> SecureObjectWrite:
        """The membership index write renaming ``old_id`` to ``new_id``, guarded on the index revision."""
        from ....application.ledger.persistence_ports import LedgerPersistenceConflictError

        index_key = transaction_index_object_key(self._bucket_id)
        ids = self._load_index_ids()
        if old_id not in ids or new_id in ids:
            raise LedgerPersistenceConflictError("transaction membership changed during edit")
        index_revisions = self._objects.peek_many_revision_ids(
            TRANSACTION_CATALOGUE_NAMESPACE.namespace,
            (index_key,),
        )
        index_revision = index_revisions.get(index_key)
        if index_revision is None:
            raise LedgerPersistenceConflictError("transaction membership revision is unavailable")
        new_ids = (ids - {old_id}) | {new_id}
        return membership_index_write(
            bucket_id=self._bucket_id,
            written_at=now(),
            payload=self._serialise_index(new_ids),
            expected_revision_id=str(index_revision),
        )

    @translating_transaction_storage_failures
    def load_for_date_range(self, start: date, end: date) -> TransactionCatalogue:
        """Return the persisted catalogue filtered to ``[start, end]`` inclusive.

        Reads the plaintext, non-sensitive :data:`~adapters.persistence.storage.sql.tables.transaction_date_index_table`
        routing rows for this bucket to select the candidate transaction ids
        whose filing date (``value_date`` or ``booked_date``) falls in the
        window, then decrypts only those rows via one targeted batch
        :meth:`~adapters.persistence.storage.sql.secure_objects.SecureObjectRepository.load_many_current` --
        never a full-namespace scan-and-decrypt of every row in the bucket.

        The index is a derived, rebuildable cache: correctness never depends
        on it being present or complete. When the index has no rows for this
        bucket, or its row count for this bucket diverges from the encrypted
        membership index (a staleness signal -- e.g. a row written before this
        index existed, or a prior crash between the two writes), this method
        transparently falls back to a full :meth:`load` and filters in memory,
        exactly reproducing the pre-index result.

        Args:
            start: Inclusive lower bound of the filing-date window.
            end: Inclusive upper bound of the filing-date window.

        Returns:
            The :class:`TransactionCatalogue` containing only transactions
            whose filing date falls within ``[start, end]``.
        """
        index_ids = self._load_index_ids()
        if not index_ids:
            return TransactionCatalogue.from_transactions([])

        candidate_ids = date_index_candidate_ids(self._objects, self._bucket_id, start, end)
        if candidate_ids is None or not candidate_ids <= index_ids:
            # Missing, empty-for-a-nonempty-bucket, or drifted relative to the
            # authoritative membership index: fall back to the full encrypted
            # scan and filter in memory so correctness never depends on the
            # plaintext index being present or fresh.
            full_catalogue = self.load()
            return catalogue_from_loaded_transactions(
                transaction
                for transaction in full_catalogue.values()
                if start <= transaction_filing_date(transaction) <= end
            )

        transactions = self._load_transactions_by_ids(candidate_ids, read_context="date-range read")
        _log.debug(
            "loaded transaction catalogue via date index bucket_id=%s window=%s..%s entries=%d",
            self._bucket_id,
            start.isoformat(),
            end.isoformat(),
            len(transactions),
        )
        return catalogue_from_loaded_transactions(transactions)

    @translating_transaction_storage_failures
    def load_by_ids(self, transaction_ids: Iterable[str]) -> TransactionCatalogue:
        """Return only the securely addressed transaction rows.

        This is the targeted counterpart to :meth:`load`: callers that already
        possess authoritative contributor ids need not decrypt and validate an
        unrelated full bucket merely to fingerprint those contributors. The
        same row-schema and addressed-identity checks run in
        :meth:`_load_transactions_by_ids`; nonexistent ids are omitted exactly
        as they would be from a full-catalogue lookup.
        """
        selected_ids = tuple(sorted(set(transaction_ids)))
        transactions = self._load_transactions_by_ids(selected_ids, read_context="targeted id read")
        _log.debug(
            "loaded transaction catalogue via targeted ids bucket_id=%s entries=%d",
            self._bucket_id,
            len(transactions),
        )
        return catalogue_from_loaded_transactions(transactions)

    def _partition_from_full_scan(self, start: date, end: date) -> LedgerDatePartition:
        """Partition every decrypted row after the date index fails completeness."""
        full_catalogue = self.load()
        in_window: list[Transaction] = []
        out_of_window: list[OutOfWindowTransactionIndexEntry] = []
        for transaction in full_catalogue.values():
            dates = IndexedTransactionDates.for_transaction(transaction)
            if dates.overlaps(start, end):
                in_window.append(transaction)
                continue
            out_of_window.append(
                OutOfWindowTransactionIndexEntry(
                    transaction_id=transaction.transaction_id,
                    filing_date=dates.filing_date,
                ),
            )
        _log.debug(
            "partitioned transaction catalogue via full-scan fallback bucket_id=%s window=%s..%s "
            "in_window=%d out_of_window=%d",
            self._bucket_id,
            start.isoformat(),
            end.isoformat(),
            len(in_window),
            len(out_of_window),
        )
        return LedgerDatePartition(
            in_window=catalogue_from_loaded_transactions(in_window),
            out_of_window=tuple(out_of_window),
            out_of_window_summary=OutOfWindowTransactionSummary.from_index_entries(out_of_window),
            index_complete=False,
        )

    def _partition_from_complete_index(self, start: date, end: date) -> LedgerDatePartition:
        """Partition through a complete plaintext date index and targeted decrypt.

        The completeness gate has already compared the index's transaction ids
        with the encrypted membership index. The partition query therefore only
        needs to materialise the candidate rows that overlap this window and a
        compact aggregate for the out-of-window remainder. Constructing a
        Python date projection for every row on every cumulative M130 quarter
        was an avoidable O(n) CPU cost even though only the in-window ids need
        decryption and large remainders are represented by a summary.
        """
        outside_condition = (transaction_date_index_table.c.eligible_from > end) | (
            transaction_date_index_table.c.eligible_to < start
        )
        with self._objects.guarded_session_scope() as session:
            in_window_ids = set(
                session.execute(
                    select(transaction_date_index_table.c.transaction_id).where(
                        transaction_date_index_table.c.bucket_id == self._bucket_id,
                        transaction_date_index_table.c.eligible_from <= end,
                        transaction_date_index_table.c.eligible_to >= start,
                    ),
                ).scalars(),
            )
            out_count, min_filing_date, max_filing_date = session.execute(
                select(
                    func.count(transaction_date_index_table.c.id),
                    func.min(transaction_date_index_table.c.filing_date),
                    func.max(transaction_date_index_table.c.filing_date),
                ).where(
                    transaction_date_index_table.c.bucket_id == self._bucket_id,
                    outside_condition,
                ),
            ).one()
            out_of_window_rows: tuple[tuple[str, date], ...] = ()
            if out_count <= OUT_OF_WINDOW_ROW_PROJECTION_LIMIT:
                projected_rows: list[tuple[str, date]] = []
                for transaction_id, filing_date in session.execute(
                    select(
                        transaction_date_index_table.c.transaction_id,
                        transaction_date_index_table.c.filing_date,
                    ).where(
                        transaction_date_index_table.c.bucket_id == self._bucket_id,
                        outside_condition,
                    ),
                ).all():
                    if not isinstance(filing_date, date):
                        raise InternalInvariantError("transaction date index filing_date is not a date")
                    projected_rows.append((str(transaction_id), filing_date))
                out_of_window_rows = tuple(projected_rows)

        transactions = self._load_transactions_by_ids(in_window_ids, read_context="partition read")
        out_of_window_summary = (
            None
            if not out_count
            else OutOfWindowTransactionSummary(
                count=int(out_count),
                min_filing_date=min_filing_date,
                max_filing_date=max_filing_date,
            )
        )
        out_of_window_index_entries = project_out_of_window_index_entries(out_of_window_rows)
        _log.debug(
            "partitioned transaction catalogue via date index bucket_id=%s window=%s..%s in_window=%d out_of_window=%d",
            self._bucket_id,
            start.isoformat(),
            end.isoformat(),
            len(transactions),
            int(out_count),
        )
        return LedgerDatePartition(
            in_window=catalogue_from_loaded_transactions(transactions),
            out_of_window=out_of_window_index_entries,
            out_of_window_summary=out_of_window_summary,
            index_complete=True,
        )

    @translating_transaction_storage_failures
    def partition_by_date_range(self, start: date, end: date) -> LedgerDatePartition:
        """Split this bucket's catalogue into an in-window half and an out-of-window remainder.

        The period-first partition runs a completeness gate against the plaintext
        :data:`~adapters.persistence.storage.sql.tables.transaction_date_index_table`
        rows for this bucket -- the index row count and id set must exactly
        match the encrypted membership index -- before trusting the index for
        a partition. On a completeness match, only the in-window transaction
        ids are decrypted through one targeted batch
        :meth:`~adapters.persistence.storage.sql.secure_objects.SecureObjectRepository.load_many_current`;
        out-of-window ids are reported as plaintext
        :class:`~domain.transactions.date_partition.OutOfWindowTransactionIndexEntry` rows (id +
        filing date only, never decrypted). On a completeness MISMATCH -- a
        stale or partially-synced index -- this falls back to a full
        :meth:`load` and partitions the result in memory, so correctness never
        depends on the index being present or fresh
        (``aeat-ledger-contract``): a stale index
        costs a slower read, never a silent drop from either half.

        Membership in the in-window half is decided by OVERLAP against each
        row's :func:`~domain.transactions.dates.transaction_eligible_date_span`, not
        by its filing date. A consuming aggregator applies its own tax-timing
        gate to the decrypted rows, so this half is a candidate superset: a row
        booked in one quarter that carries an IVA criterio-de-caja devengo or
        collection date in another is decrypted and offered to the aggregator
        rather than reported out-of-window undecrypted, which would drop its
        observation with no diagnostic. Both halves stay disjoint and total.

        Args:
            start: Inclusive lower bound of the observation-date window.
            end: Inclusive upper bound of the observation-date window.

        Returns:
            The :class:`~domain.transactions.date_partition.LedgerDatePartition` for ``[start, end]``.
        """
        index_ids = self._load_index_ids()
        if not index_ids:
            return LedgerDatePartition(
                in_window=TransactionCatalogue.from_transactions([]),
                out_of_window=(),
                index_complete=True,
            )

        index_row_ids, index_row_count = date_index_ids_and_count(self._objects, self._bucket_id)
        if index_row_count != len(index_ids) or index_row_ids != index_ids:
            # Stale, partially-synced, or missing index rows for this bucket:
            # fall back to a full decrypt scan and partition in memory so
            # correctness never depends on index freshness.
            return self._partition_from_full_scan(start, end)

        return self._partition_from_complete_index(start, end)

    def _load_transactions_by_ids(self, transaction_ids: Iterable[str], *, read_context: str) -> list[Transaction]:
        """Load selected transaction rows through one targeted secure-object batch."""
        from ..storage.crypto.encrypted_columns import secure_object_key_digest

        selected_ids = tuple(sorted(transaction_ids))
        if not selected_ids:
            return []
        object_key_by_id = {
            transaction_id: transaction_object_key(self._bucket_id, transaction_id) for transaction_id in selected_ids
        }
        transactions_by_id, missing_ids = self._cached_targeted_transactions(selected_ids, object_key_by_id)
        cache = self._transaction_revision_cache
        transaction_id_by_digest = {
            secure_object_key_digest(object_key_by_id[transaction_id]): transaction_id for transaction_id in missing_ids
        }
        records = self._objects.load_many_current(
            TRANSACTION_CATALOGUE_NAMESPACE.namespace,
            (object_key_by_id[transaction_id] for transaction_id in missing_ids),
            expected_class=TRANSACTION_CATALOGUE_NAMESPACE.sensitivity,
            current_version=TRANSACTION_CATALOGUE_NAMESPACE.schema_version,
            refuse_legacy=self._refuse_targeted_implicit_migration,
        )
        for record in records:
            transaction_id = transaction_id_by_digest.get(bytes(record.object_key))
            if transaction_id is None:
                continue
            envelope = self._decode_targeted_row(record.payload, read_context=read_context)
            transaction = withhold_figures_without_business(envelope.payload)
            self._assert_transaction_row_identity(transaction, expected_transaction_id=transaction_id)
            # As for a catalogue read: an untouched row saved back is recognised
            # as the stored row, so withholding a figure never rewrites it.
            self._cache_serialized_hash(transaction, sha256_hex(record.payload))
            transactions_by_id[transaction_id] = transaction
            cache[transaction_id] = (str(record.revision_id), transaction)
        return [
            transactions_by_id[transaction_id]
            for transaction_id in selected_ids
            if transaction_id in transactions_by_id
        ]

    def _decode_targeted_row(self, payload: bytes, *, read_context: str) -> Envelope[Transaction]:
        from ..storage.envelope.contract import Envelope
        from ..storage.schema_lineage import inner_envelope_version_is_current

        try:
            # Validate in full when the authenticated inner envelope names another schema version.
            envelope = validate_authenticated_stored_transaction_json(Envelope[Transaction], payload)
            if not inner_envelope_version_is_current(
                envelope.schema_version, TRANSACTION_CATALOGUE_NAMESPACE.schema_version
            ):
                envelope = validate_stored_transaction_json(Envelope[Transaction], payload)
        except ValidationError as exc:
            _log.error(
                "transaction row schema drift bucket_id=%s (%s)",
                self._bucket_id,
                read_context,
                exc_info=True,
            )
            raise StoredTransactionDriftError(self._bucket_id, exc) from exc
        return envelope

    def _cached_targeted_transactions(
        self,
        selected_ids: tuple[str, ...],
        object_key_by_id: Mapping[str, str],
    ) -> tuple[dict[str, Transaction], list[str]]:
        """Admit decoded rows only while their addressed secure revision matches."""
        transactions_by_id: dict[str, Transaction] = {}
        cache = self._transaction_revision_cache
        current_revisions: Mapping[str, str | None] = dict[str, str | None]()
        if cache:
            current_revisions = self._objects.peek_many_revision_ids(
                TRANSACTION_CATALOGUE_NAMESPACE.namespace,
                object_key_by_id.values(),
            )
            missing_ids: list[str] = []
            for transaction_id, object_key in object_key_by_id.items():
                revision = current_revisions.get(object_key)
                cached = cache.get(transaction_id)
                if revision is not None and cached is not None and cached[0] == revision:
                    transactions_by_id[transaction_id] = cached[1]
                    continue
                cache.pop(transaction_id, None)
                if object_key in current_revisions:
                    missing_ids.append(transaction_id)
        else:
            # Preserve the cold-read contract: schema cutover, outer integrity,
            # decryption, and payload validation share one addressed snapshot.
            # Revision probes exist only to validate already-decoded rows.
            missing_ids = list(selected_ids)

        return transactions_by_id, missing_ids

    @staticmethod
    def _refuse_targeted_implicit_migration(_object_keys: tuple[str, ...]) -> None:
        """Keep exact-ID reads behind the explicit whole-authority cutover."""
        raise LedgerStorageError("transaction catalogue requires explicit IVA authority migration before read")

    def _assert_transaction_row_identity(
        self,
        transaction: Transaction,
        *,
        expected_transaction_id: str,
    ) -> None:
        """Refuse a decrypted transaction whose identity differs from its addressed row.

        The membership and date indexes select encrypted rows by
        ``transaction:{bucket_id}:{transaction_id}``.  A valid transaction
        payload re-filed under another transaction's key passes schema
        validation but must never be projected as the indexed transaction.
        """
        if transaction.transaction_id == expected_transaction_id:
            return
        raise SecureObjectRowIdentityError(
            TRANSACTION_CATALOGUE_NAMESPACE.namespace,
            expected_identifier=transaction_object_key(self._bucket_id, expected_transaction_id),
        )

    def _sync_date_index(self, catalogue: TransactionCatalogue) -> None:
        """Diff this bucket's plaintext date-index rows against ``catalogue``.

        Runs as a SEPARATE transaction immediately after the encrypted write
        commits. Only transactions that are new, removed, or whose filing
        date changed are written -- an unchanged transaction's index row is
        left untouched, mirroring the diff-based write the encrypted rows
        already use (see the module docstring: a full-rewrite-per-save would
        reintroduce the O(n) write-amplification the encrypted per-row store
        was built to eliminate).

        The index is a derived, rebuildable cache
        (``aeat-ledger-contract``): a crash
        between the two writes leaves the index one write behind, which
        :meth:`load_for_date_range` detects via the membership-index subset
        check and safely falls back to a full scan for -- never a correctness
        hazard, only a lost optimisation until the next save re-syncs it.

        Carries ONLY non-sensitive routing keys (bucket id, transaction id,
        filing date, filing year) -- never an amount, counterparty,
        description, or any other financial content.
        """
        sync_date_index_rows(self._objects, self._bucket_id, catalogue)

    def _reconcile(
        self,
        catalogue: TransactionCatalogue,
    ) -> tuple[tuple[SecureObjectWrite, ...], tuple[SecureObjectDeletion, ...], dict[str, FigureDrop]]:
        """Diff ``catalogue`` against this bucket's stored rows.

        Returns ``(changed writes, deletions, figure drops)``. Changed-row detection is a
        decryption-free
        :meth:`~adapters.persistence.storage.sql.secure_object_writes.SecureObjectWriteOperations.namespace_payload_hashes`
        lookup keyed by the bucket-qualified HMAC digest (so it is correct even
        when several buckets share one store): an incoming transaction whose
        freshly-serialised payload hash matches the stored one is left
        untouched. Deletions and the membership index are bounded to *this*
        bucket via the per-bucket index, so a reconciliation can never touch
        another bucket's rows.

        An incoming transaction that IS (object identity) an instance this
        same repository loaded reuses the memoized
        ``_serialized_hash_cache`` entry instead of re-serializing and
        re-hashing the row. The store-side
        comparison (``stored_hashes``) is always fresh; only the
        fresh-serialization side of the diff is skipped for a cache hit.

        A changed row whose stored form holds business figures its
        classification refuses is judged against that stored row, whichever
        repository instance read it: when the incoming row is the stored row as
        a reader sees it, the stored bytes are kept; otherwise the write drops
        those figures, and the drop is returned so the batch records it.
        """
        current_ids = self._load_index_ids()
        incoming_ids = set(catalogue.transactions)
        writes, drops = self._changed_row_writes(catalogue)
        if incoming_ids != current_ids:
            writes.append(
                membership_index_write(
                    bucket_id=self._bucket_id, written_at=now(), payload=self._serialise_index(incoming_ids)
                ),
            )

        deletions = tuple(
            transaction_row_deletion(bucket_id=self._bucket_id, transaction_id=transaction_id)
            for transaction_id in current_ids - incoming_ids
        )
        return tuple(writes), deletions, drops

    def _changed_rows(self, catalogue: TransactionCatalogue) -> list[tuple[str, Transaction, bytes, bool]]:
        """Return each row whose serialised payload differs from its stored one, and whether it is stored."""
        from ..storage.crypto.encrypted_columns import secure_object_key_digest

        stored_hashes = self._objects.namespace_payload_hashes(TRANSACTION_CATALOGUE_NAMESPACE.namespace)
        changed: list[tuple[str, Transaction, bytes, bool]] = []
        for transaction_id, transaction in catalogue.transactions.items():
            digest = secure_object_key_digest(transaction_object_key(self._bucket_id, transaction_id))
            cached_hash = self._serialized_hash_cache.get(id(transaction))
            if cached_hash is not None and stored_hashes.get(digest) == cached_hash:
                continue
            payload = self._serialise_transaction(transaction)
            if cached_hash is None and stored_hashes.get(digest) == sha256_hex(payload):
                continue
            changed.append((transaction_id, transaction, payload, digest in stored_hashes))
        return changed

    def _changed_row_writes(
        self, catalogue: TransactionCatalogue
    ) -> tuple[list[SecureObjectWrite], dict[str, FigureDrop]]:
        """Return the row writes of the changed rows and the figures those writes stop storing."""
        changed = self._changed_rows(catalogue)
        holding = stored_rows_holding_figures(
            self._objects,
            bucket_id=self._bucket_id,
            transaction_ids=(
                transaction_id for transaction_id, _transaction, _payload, is_stored in changed if is_stored
            ),
            refuse_legacy=self._refuse_targeted_implicit_migration,
        )
        writes: list[SecureObjectWrite] = []
        drops: dict[str, FigureDrop] = {}
        for transaction_id, transaction, payload, _is_stored in changed:
            stored_row = holding.get(transaction_id)
            if stored_row is not None:
                if withhold_figures_without_business(stored_row) == transaction:
                    # The row as any reader sees it: saving it back keeps the stored bytes.
                    continue
                drops[transaction_id] = (figures_held_without_business(stored_row), transaction.modified_at)
            writes.append(
                transaction_row_write(
                    bucket_id=self._bucket_id,
                    transaction_id=transaction_id,
                    written_at=transaction.modified_at,
                    payload=payload,
                ),
            )
        return writes, drops

    def _with_withheld_figure_trace(
        self,
        extra_writes: tuple[SecureObjectWrite, ...],
        drops: Mapping[str, FigureDrop],
    ) -> tuple[SecureObjectWrite, ...]:
        """Return ``extra_writes`` with this bucket's event history recording every figure the batch drops."""
        return with_withheld_figure_trace(
            self._objects, bucket_id=self._bucket_id, extra_writes=extra_writes, drops=drops
        )

    def _cache_serialized_hash(self, transaction: Transaction, payload_hash: str) -> None:
        """Memoize ``payload_hash`` against ``transaction``'s identity.

        Keyed by ``id(transaction)`` rather than the object itself (see the
        class docstring for why a plain hash-keyed cache is unsafe here). A
        :class:`~weakref.finalize` callback evicts the entry the instant this
        exact ``transaction`` instance is garbage-collected, so a later,
        unrelated object cannot inherit a stale cache hit at a recycled
        address.
        """
        key = id(transaction)
        cache = self._serialized_hash_cache
        weakref.finalize(transaction, cache.pop, key, None)
        cache[key] = payload_hash

    def _load_index_ids(self, *, require_current: bool = True) -> set[str]:
        """Return the transaction ids the per-bucket membership index records."""
        from ..storage.envelope.contract import Envelope
        from ..storage.schema_lineage import inner_envelope_version_is_current

        index_key = transaction_index_object_key(self._bucket_id)
        record = self._objects.load(
            TRANSACTION_CATALOGUE_NAMESPACE.namespace,
            index_key,
            expected_class=TRANSACTION_CATALOGUE_NAMESPACE.sensitivity,
            max_supported_version=TRANSACTION_CATALOGUE_NAMESPACE.schema_version,
        )
        if record is None:
            return set()
        try:
            envelope = Envelope[TransactionMembershipIndex].model_validate_json(record.payload)
        except ValidationError as exc:
            raise StoredTransactionDriftError(self._bucket_id, exc) from exc
        if require_current and not inner_envelope_version_is_current(
            envelope.schema_version,
            TRANSACTION_CATALOGUE_NAMESPACE.schema_version,
        ):
            raise LedgerStorageError("transaction catalogue requires explicit IVA authority migration before read")
        return set(envelope.payload.transaction_ids)

    def _serialise_index(self, transaction_ids: set[str]) -> bytes:
        """Serialise the membership index (sorted ids) into encrypted-row bytes."""
        from ..storage.envelope.contract import Envelope

        envelope = Envelope[TransactionMembershipIndex](
            schema_version=TRANSACTION_CATALOGUE_NAMESPACE.schema_version,
            written_at=now(),
            classification=TRANSACTION_CATALOGUE_NAMESPACE.sensitivity,
            payload=TransactionMembershipIndex(transaction_ids=tuple(sorted(transaction_ids))),
        )
        return envelope.model_dump_json().encode(UTF_8_ENCODING)

    def _serialise_transaction(self, transaction: Transaction) -> bytes:
        """Serialise one transaction into stable encrypted-row envelope bytes.

        The envelope ``written_at`` is the transaction's own ``modified_at`` (not
        ``now()``), so an unchanged transaction serialises to identical bytes —
        and an identical ``payload_hash`` — letting the diff skip rewriting it.
        """
        from ..storage.envelope.contract import Envelope

        # The write boundary: a row built through its constructor was refused
        # already, and a copied row is refused here before any byte is written.
        require_no_figures_without_business(transaction)
        envelope = Envelope[Transaction](
            schema_version=TRANSACTION_CATALOGUE_NAMESPACE.schema_version,
            written_at=transaction.modified_at,
            classification=TRANSACTION_CATALOGUE_NAMESPACE.sensitivity,
            payload=transaction,
        )
        return envelope.model_dump_json().encode(UTF_8_ENCODING)
