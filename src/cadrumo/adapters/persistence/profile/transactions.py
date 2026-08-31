"""Encrypted SQL repository for the transaction catalogue.

:class:`TransactionCatalogueRepository` is the only sanctioned read/write path
for the transaction catalogue. It stores **one encrypted secure-object row per
transaction** — keyed ``transaction:{bucket_id}:{transaction_id}`` inside the
``cadrumo.domain.transactions.bucket`` namespace at
:class:`~adapters.persistence.storage.SensitivityClass` ``FINANCIAL`` — so a
single-transaction mutation rewrites only that row instead of re-encrypting the
whole catalogue (the prior single-blob shape was O(n) write amplification per
ledger edit). Each row wraps its
:class:`~domain.transactions.Transaction` in an
:class:`~adapters.persistence.storage.Envelope` before serialisation; no
plaintext transaction row, JSON catalogue, or envelope file lands on disk.

This concrete repository is the persistence adapter behind the read-side
:class:`~domain.transactions.TransactionCatalogueRepositoryProtocol`. It
lives in the persistence adapter (not in :mod:`~domain.transactions`) because
its secure-object coupling is SQL/crypto-bound; the domain package owns only the
pure surface — the :class:`~domain.transactions.ImportSummary` record, the
:func:`~domain.transactions.transaction_object_key` /
:func:`transaction_index_object_key` key-derivation helpers, and the
:data:`~adapters.persistence.profile.transactions.TX_BUCKET_NAMESPACE` /
schema-version constants that name the persisted envelope contract. The
namespace/version constants are redeclared here as the persisted-envelope
contract; the strings are preserved to avoid orphaning stored envelopes.

Writes go through the
:class:`~adapters.persistence.storage.SecureObjectRepository` atomic
upsert+delete batch
(:meth:`~adapters.persistence.storage.SecureObjectRepository.apply_batch`)
so a multi-transaction mutation — and any sibling-catalogue co-writes
(bucket-event history, invoices) passed to ``save_with_secure_object_writes`` —
commit all-or-nothing, preserving the co-write atomicity the single-blob
``save`` had. The diff that decides which rows to write or delete is driven by a
decryption-free
:meth:`~adapters.persistence.storage.SecureObjectRepository.namespace_payload_hashes`
scan, so an unchanged transaction is never rewritten.

See Also:
    :class:`~domain.transactions.TransactionCatalogueRepositoryProtocol`
        Domain port this concrete persistence adapter implements.
    :class:`~domain.transactions.Transaction`
        Domain transaction payload stored one encrypted row at a time.
    :data:`~adapters.persistence.storage.TRANSACTION_CATALOGUE_NAMESPACE`
        Central namespace, sensitivity, schema-version, and object-key contract
        for transaction secure objects.
    :class:`~adapters.persistence.storage.SecureObjectRepository`
        Runtime-created encrypted storage boundary used for atomic batches.
    :mod:`~application.ledger`
        Application ledger workflows that consume this repository through the
        transaction catalogue boundary.
"""

from __future__ import annotations

import json
import weakref
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field, TypeAdapter, ValidationError, field_validator
from sqlalchemy import delete, select, update

from ....core.config import load_settings
from ....core.external_constants import UTF_8_ENCODING
from ....core.hashing import sha256_hex
from ....core.iva_deduction_fact import IvaDeductionFactKind
from ....core.logging import get_logger
from ....core.models import STRICT_FROZEN_CONFIG
from ....core.time.clock import now
from ....core.time.utc import validate_utc_aware
from ....domain.bienes_inversion.register import (
    BienesInversionIvaRegister,
    InvestmentAssetAcquisitionLink,
    validate_investment_asset_reciprocity,
)
from ....domain.iva.classification import InvoiceKind
from ....domain.iva.deduction_facts import IvaDeductionClassificationProvenance, validate_iva_deduction_fact
from ....domain.iva.flow import derive_flow_for_classification
from ....domain.iva.lookup import rate_kinds_for_declared_rate
from ....domain.iva.schema import EUMemberState, IvaCategory, IvaRateKind
from ....domain.transactions.dates import transaction_eligible_date_span, transaction_filing_date
from ....domain.transactions.enums import TransactionDirection
from ....domain.transactions.errors import LedgerStorageError, StoredTransactionDriftError
from ....domain.transactions.models import (
    LedgerDatePartition,
    OutOfWindowTransactionIndexEntry,
    OutOfWindowTransactionSummary,
    Transaction,
    TransactionCatalogue,
)
from ....domain.transactions.repository import transaction_index_object_key, transaction_object_key
from ..storage._secure_object_namespaces import (
    PROFILE_BIENES_INVERSION_IVA_REGISTER_NAMESPACE,
    TRANSACTION_CATALOGUE_NAMESPACE,
)
from ..storage.errors import SecureObjectRowIdentityError
from ..storage.sql import SecureObjectMigrationTarget, TransactionDateIndexRow
from .bienes_inversion import BienesInversionIvaRegisterRepository

if TYPE_CHECKING:  # pragma: no cover — import-cycle guard
    from ..storage._secure_object_namespaces import SecureObjectNamespaceDefinition
    from ..storage.sql import SecureObjectDeletion, SecureObjectRepository, SecureObjectWrite

_log = get_logger(__name__)

_TX_CATALOGUE_VERSION = TRANSACTION_CATALOGUE_NAMESPACE.schema_version
_TX_CATALOGUE_SENSITIVITY = TRANSACTION_CATALOGUE_NAMESPACE.sensitivity
TX_BUCKET_NAMESPACE = TRANSACTION_CATALOGUE_NAMESPACE.namespace
# Row-level projections remain useful for small ledgers and compatibility
# consumers. At scale the compact count/date-span summary is the canonical
# diagnostic channel; materialising tens of thousands of Pydantic rows would
# make excluded transactions dominate a period-scoped read.
_OUT_OF_WINDOW_ROW_PROJECTION_LIMIT = 1024
_JSON_OBJECT = TypeAdapter(dict[str, object])


class _TransactionIndex(BaseModel):
    """Per-bucket membership list: the transaction ids this bucket owns.

    The index is a single secure-object row keyed by ``bucket_id`` that bounds
    both reads and deletions to *this* bucket's rows. It is what preserves
    cross-bucket isolation when several buckets share one secure store: a load
    or a reconciliation reads this bucket's index by its exact key and never
    enumerates another bucket's transactions, and a reconciliation can only
    delete transaction ids the index lists. The heavy per-transaction payloads
    live in their own rows; the index carries only the (cheap) id list.
    """

    model_config = STRICT_FROZEN_CONFIG

    transaction_ids: tuple[str, ...] = ()


def _secure_objects_for_bucket(bucket_id: str) -> SecureObjectRepository:
    """Return the runtime-created secure-object repository for ``bucket_id``."""
    from ..storage.runtime_repository import secure_object_repository_for_bucket

    return secure_object_repository_for_bucket(bucket_id, load_settings())


class _PersistedTransactionTimestampWitness(BaseModel):
    """Required lifecycle timestamps for one stored transaction row."""

    created_at: datetime = Field()
    modified_at: datetime = Field()

    @field_validator("created_at", "modified_at")
    @classmethod
    def _require_utc_aware(cls, value: datetime) -> datetime:
        return validate_utc_aware(value)

    @classmethod
    def validate_payload(cls, payload: object) -> None:
        """Raise ``ValidationError`` when a persisted row lacks timestamp keys."""
        cls.model_validate(payload)


def _decode_persisted_transaction_row(payload: bytes) -> dict[str, object] | None:
    """Return the parsed envelope dict for one persisted row, or ``None`` if not JSON.

    Centralises the single JSON decode of a stored row's plaintext bytes so
    the D6 timestamp guard and the authoritative :class:`Envelope` validation
    share one parse instead of each independently re-decoding the same bytes
    (a real O(n) cost at ledger scale: see the P95 scale benchmark in
    ``application/aggregation/tests/test_ledger_scale_benchmark.py``).
    """
    try:
        decoded: object = json.loads(payload.decode(UTF_8_ENCODING))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    try:
        return _JSON_OBJECT.validate_python(decoded)
    except ValidationError:
        return None


@dataclass(frozen=True, slots=True)
class _IndexedTransactionDates:
    """The plaintext routing dates one :class:`TransactionDateIndexRow` records.

    Groups the filing date with the inclusive eligible-observation span so a
    row's index state is compared and written as one value: a change to
    either axis rewrites the row, and an unchanged row is left untouched.
    """

    filing_date: date
    eligible_from: date
    eligible_to: date

    @classmethod
    def for_transaction(cls, transaction: Transaction) -> _IndexedTransactionDates:
        """Project one transaction's routing dates through the domain date owners."""
        eligible_from, eligible_to = transaction_eligible_date_span(transaction)
        return cls(
            filing_date=transaction_filing_date(transaction),
            eligible_from=eligible_from,
            eligible_to=eligible_to,
        )

    def overlaps(self, start: date, end: date) -> bool:
        """Return whether this row can file an observation inside ``[start, end]``."""
        return self.eligible_from <= end and self.eligible_to >= start


@dataclass(frozen=True, slots=True)
class _MigratedIvaDeductionFact:
    """The complete IVA authority axis required to migrate one transaction row."""

    kind: IvaDeductionFactKind
    provenance: IvaDeductionClassificationProvenance
    taxable_base: Decimal
    iva_rate: Decimal
    iva_amount: Decimal
    category: IvaCategory


def _validate_persisted_transaction_timestamps(decoded: dict[str, object]) -> None:
    """Reject a persisted per-transaction row missing the mandatory D6 timestamps.

    Takes the already-JSON-decoded envelope dict (see
    :func:`_decode_persisted_transaction_row`) rather than re-parsing the raw
    bytes, so this guard adds only a cheap pydantic pass over the small
    ``{created_at, modified_at}`` sub-shape -- not a second full JSON decode
    of the whole row.
    """
    transaction_payload = decoded.get("payload")
    if not isinstance(transaction_payload, dict):
        return
    _PersistedTransactionTimestampWitness.validate_payload(_JSON_OBJECT.validate_python(transaction_payload))


def _migrated_iva_deduction_fact(transaction: Transaction) -> _MigratedIvaDeductionFact | None:
    """Return complete persisted IVA authority, refusing partial legacy evidence."""
    taxable_base = transaction.taxable_base
    iva_rate = transaction.iva_rate
    iva_amount = transaction.iva_amount
    category = transaction.iva_category
    if all(value is None for value in (taxable_base, iva_rate, iva_amount, category)):
        return None
    kind = transaction.deduction_fact_kind
    provenance = transaction.deduction_provenance
    if (
        kind is None
        or provenance is None
        or taxable_base is None
        or iva_rate is None
        or iva_amount is None
        or category is None
    ):
        raise LedgerStorageError(
            f"transaction {transaction.transaction_id}: exact IVA kind, provenance, "
            "amounts, rate, and category are required"
        )
    return _MigratedIvaDeductionFact(
        kind=kind,
        provenance=provenance,
        taxable_base=taxable_base,
        iva_rate=iva_rate,
        iva_amount=iva_amount,
        category=category,
    )


def _migrated_iva_rate_kind(
    transaction: Transaction,
    fact: _MigratedIvaDeductionFact,
) -> IvaRateKind:
    """Resolve the one dated legal rate tier for persisted IVA evidence."""
    if fact.kind is IvaDeductionFactKind.REAGP_COMPENSATION:
        return IvaRateKind.EXEMPT
    operation_date = transaction.operation_date or transaction.raw.value_date or transaction.raw.booked_date
    rate_kinds = rate_kinds_for_declared_rate(EUMemberState.ES, fact.iva_rate, operation_date)
    if len(rate_kinds) != 1:
        raise LedgerStorageError(
            f"transaction {transaction.transaction_id}: persisted IVA rate does not resolve to exactly one legal tier"
        )
    return rate_kinds[0]


class TransactionCatalogueRepository:
    """Repository over the encrypted SQL-backed transaction catalogue.

    Every instance is bound to one profile bucket via ``bucket_id``. The
    catalogue is stored as one secure-object row per transaction (keyed
    ``transaction:{bucket_id}:{transaction_id}``) inside the
    :data:`~adapters.persistence.storage.TRANSACTION_CATALOGUE_NAMESPACE`
    namespace, so two operator profiles never share transaction storage and a
    single-transaction mutation touches a single row. Each
    :class:`~domain.transactions.Transaction` payload and the bucket
    membership index are wrapped in
    :class:`~adapters.persistence.storage.Envelope` before
    :class:`~adapters.persistence.storage.SecureObjectRepository`
    persists them. The class exposes the concrete load/save implementation
    behind
    :class:`~domain.transactions.TransactionCatalogueRepositoryProtocol`.

    ``_serialized_hash_cache`` is a write-path optimization: it memoizes the
    stored-envelope SHA-256 of each loaded frozen
    :class:`~domain.transactions.Transaction`
    instance, populated once per row at :meth:`load` and consulted by
    :meth:`_reconcile` before re-serializing an untouched row.

    Keying is identity-based (``id(transaction)``), not value-based:
    ``Transaction``'s pydantic-generated ``__hash__`` is unusable as a dict key
    because :attr:`~domain.transactions.RawTransaction.raw_fields` is stored as
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

    @property
    def bucket_id(self) -> str:
        """Return the profile bucket id this repository is bound to."""
        return self._bucket_id

    def exists(self) -> bool:
        """Return whether this bucket holds any persisted transactions."""
        return bool(self._load_index_ids())

    def load(self) -> TransactionCatalogue:
        """Return the persisted catalogue, assembled from this bucket's rows.

        The per-bucket membership index names exactly the transaction ids this
        bucket owns; only the rows whose digest the index lists are read, so a
        shared secure store never leaks another bucket's transactions.

        Returns:
            The deserialised :class:`TransactionCatalogue`, or a fresh empty
            instance when this bucket has no transactions.

        Raises:
            :class:`~adapters.persistence.storage.ClassificationError`:
                If a row's inner envelope class is not
                ``_TX_CATALOGUE_SENSITIVITY``.
            :class:`~adapters.persistence.storage.EnvelopeVersionError`:
                If a row's inner envelope schema version is higher than the
                consumer supports.
            StoredTransactionDriftError: If a row payload fails pydantic schema
                validation on deserialization.
        """
        from ..storage._schema_lineage import (
            inner_envelope_classification_is_expected,
            inner_envelope_version_is_current,
        )
        from ..storage.envelope._envelope import Envelope
        from ..storage.errors import ClassificationError, EnvelopeVersionError

        index_ids = self._load_index_ids()
        if not index_ids:
            return TransactionCatalogue.from_transactions([])
        index_key = transaction_index_object_key(self._bucket_id)
        transaction_keys = {
            transaction_id: transaction_object_key(self._bucket_id, transaction_id) for transaction_id in index_ids
        }
        self._require_current_rows(transaction_keys.values())
        migrated = self._objects.migrate_many_atomically(
            TX_BUCKET_NAMESPACE,
            (index_key, *transaction_keys.values()),
            expected_class=_TX_CATALOGUE_SENSITIVITY,
            current_version=_TX_CATALOGUE_VERSION,
            validate_upgraded_payloads=self._validate_migrated_catalogue_payloads,
            write_provenance="transaction-catalogue:schema-migration",
        )
        transactions: list[Transaction] = []
        for transaction_id, object_key in transaction_keys.items():
            record = migrated.get(object_key)
            if record is None:
                continue
            try:
                decoded_row = _decode_persisted_transaction_row(record.payload)
                if decoded_row is not None:
                    # Reuse the same JSON decode for the cheap D6 timestamp
                    # guard; the authoritative Envelope validation below still
                    # parses the original bytes via ``model_validate_json``
                    # (JSON mode), which is required for correct string ->
                    # datetime / string -> enum coercion under the envelope's
                    # ``strict=True`` config -- ``model_validate`` on an
                    # already-decoded dict runs in *python* mode and rejects
                    # those coercions outright under strict config.
                    _validate_persisted_transaction_timestamps(decoded_row)
                envelope = Envelope[Transaction].model_validate_json(record.payload)
            except ValidationError as exc:
                _log.error(
                    "transaction row schema drift bucket_id=%s",
                    self._bucket_id,
                    exc_info=True,
                )
                raise StoredTransactionDriftError(self._bucket_id, exc) from exc
            if not inner_envelope_classification_is_expected(envelope.classification, _TX_CATALOGUE_SENSITIVITY):
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
                        "namespace": TX_BUCKET_NAMESPACE,
                        "object_key": transaction_object_key(self._bucket_id, transaction_id),
                        "bucket_id": self._bucket_id,
                        "classification": envelope.classification.value,
                        "expected": _TX_CATALOGUE_SENSITIVITY.value,
                    },
                    translated_message="errors.integrity.integrity_storage_classification",
                )
            if not inner_envelope_version_is_current(envelope.schema_version, _TX_CATALOGUE_VERSION):
                raise EnvelopeVersionError(
                    context={
                        "namespace": TX_BUCKET_NAMESPACE,
                        "object_key": transaction_object_key(self._bucket_id, transaction_id),
                        "bucket_id": self._bucket_id,
                        "schema_version": envelope.schema_version,
                        "expected": _TX_CATALOGUE_VERSION,
                    },
                    translated_message="errors.integrity.integrity_storage_envelope_version",
                )
            transaction = envelope.payload
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
        return TransactionCatalogue.from_transactions(transactions)

    def _validate_migrated_catalogue_payloads(self, payloads: Mapping[str, bytes]) -> None:
        """Validate the whole upgraded catalogue before any v2 row replacement."""
        transactions = self._validated_migrated_transactions(payloads)
        if any(
            transaction.deduction_fact_kind is not None and transaction.deduction_fact_kind.is_investment_acquisition
            for transaction in transactions
        ):
            raise LedgerStorageError(
                "investment IVA v1 backfill requires explicit reciprocal bienes-inversion authority"
            )

    def _validated_migrated_transactions(self, payloads: Mapping[str, bytes]) -> tuple[Transaction, ...]:
        """Return the complete semantically validated upgraded transaction set."""
        from ..storage.envelope._envelope import Envelope

        index_key = transaction_index_object_key(self._bucket_id)
        index_payload = payloads.get(index_key)
        if index_payload is None:
            raise LedgerStorageError("transaction index is absent during schema migration")
        index = Envelope[_TransactionIndex].model_validate_json(index_payload).payload
        missing = [
            transaction_id
            for transaction_id in index.transaction_ids
            if transaction_object_key(self._bucket_id, transaction_id) not in payloads
        ]
        if missing:
            raise LedgerStorageError(
                "transaction rows absent for index ids during schema migration: " + ", ".join(sorted(missing)),
            )
        transactions: list[Transaction] = []
        for transaction_id in index.transaction_ids:
            payload = payloads[transaction_object_key(self._bucket_id, transaction_id)]
            envelope = Envelope[Transaction].model_validate_json(payload)
            self._assert_transaction_row_identity(envelope.payload, expected_transaction_id=transaction_id)
            self._validate_migrated_deduction_fact(envelope.payload)
            transactions.append(envelope.payload)
        return tuple(transactions)

    def _validate_migrated_deduction_fact(self, transaction: Transaction) -> None:
        """Validate persisted v1 tax evidence without defaulting any semantic axis."""
        fact = _migrated_iva_deduction_fact(transaction)
        if fact is None:
            return
        rate_kind = _migrated_iva_rate_kind(transaction, fact)
        invoice_kind = (
            InvoiceKind.RECEIVED if transaction.direction is TransactionDirection.OUTGOING else InvoiceKind.ISSUED
        )
        flow_direction = derive_flow_for_classification(
            category=fact.category,
            invoice_direction=invoice_kind,
        )
        validate_iva_deduction_fact(
            kind=fact.kind,
            provenance=fact.provenance,
            category=fact.category,
            rate_kind=rate_kind,
            flow_direction=flow_direction,
            base_amount=fact.taxable_base,
            iva_amount=fact.iva_amount,
            investment_asset_id=transaction.investment_asset_id,
            rectifies_ledger_id=transaction.rectifies_ledger_id,
        )

    def _migration_investment_links(
        self,
        transactions: Iterable[Transaction],
    ) -> dict[int, list[InvestmentAssetAcquisitionLink]]:
        """Group migrated investment deductions by filing year."""
        links_by_year: dict[int, list[InvestmentAssetAcquisitionLink]] = {}
        for transaction in transactions:
            if not (
                transaction.deduction_fact_kind is not None
                and transaction.deduction_fact_kind.is_investment_acquisition
            ):
                continue
            investment_asset_id = transaction.investment_asset_id
            if investment_asset_id is None:
                raise LedgerStorageError(
                    f"transaction {transaction.transaction_id!r} has an investment "
                    "deduction kind without an asset link",
                )
            transaction_date = transaction.operation_date or transaction.raw.value_date or transaction.raw.booked_date
            links_by_year.setdefault(transaction_date.year, []).append(
                InvestmentAssetAcquisitionLink(
                    ledger_id=transaction.transaction_id,
                    transaction_date=transaction_date,
                    deduction_fact_kind=transaction.deduction_fact_kind,
                    investment_asset_id=investment_asset_id,
                    prorrata_sector_id=transaction.prorrata_sector_id,
                ),
            )
        return links_by_year

    def _validate_iva_authority_migration(
        self,
        payloads: Mapping[tuple[str, str], bytes],
        *,
        bienes_definition: SecureObjectNamespaceDefinition,
        bienes_key: str,
        asset_profile_id: str,
    ) -> None:
        """Validate upgraded transaction rows against reciprocal bienes authority."""
        transaction_payloads = {
            key: payload for (namespace, key), payload in payloads.items() if namespace == TX_BUCKET_NAMESPACE
        }
        transactions = self._validated_migrated_transactions(transaction_payloads)
        register_payload = payloads.get((bienes_definition.namespace, bienes_key))
        if register_payload is None:
            raise LedgerStorageError("bienes-inversion register is absent during IVA authority migration")
        register = BienesInversionIvaRegister.model_validate_json(register_payload)
        links_by_year = self._migration_investment_links(transactions)
        years = sorted(set(links_by_year) | {record.acquisition_year for record in register.records})
        for filing_year in years:
            validate_investment_asset_reciprocity(
                observations=tuple(links_by_year.get(filing_year, [])),
                register=register,
                ledger_profile_id=self._bucket_id,
                asset_profile_id=asset_profile_id,
                filing_year=filing_year,
            )

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
                        TX_BUCKET_NAMESPACE,
                        key,
                        _TX_CATALOGUE_SENSITIVITY,
                        _TX_CATALOGUE_VERSION,
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
            validate_upgraded_payloads=lambda payloads: self._validate_iva_authority_migration(
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
        writes, deletions = self._reconcile(catalogue)
        self._objects.apply_batch(writes, deletions)
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
        writes, deletions = self._reconcile(catalogue)
        self._objects.apply_batch((*writes, *extra_writes), deletions)
        self._sync_date_index(catalogue)
        _log.info(
            "saved transaction catalogue bucket_id=%s entries=%d rewritten=%d deleted=%d extra_writes=%d",
            self._bucket_id,
            len(catalogue.transactions),
            len(writes),
            len(deletions),
            len(extra_writes),
        )

    def load_for_date_range(self, start: date, end: date) -> TransactionCatalogue:
        """Return the persisted catalogue filtered to ``[start, end]`` inclusive.

        Reads the plaintext, non-sensitive :class:`~adapters.persistence.storage.sql.TransactionDateIndexRow`
        routing rows for this bucket to select the candidate transaction ids
        whose filing date (``value_date`` or ``booked_date``) falls in the
        window, then decrypts only those rows via one targeted batch
        :meth:`~adapters.persistence.storage.SecureObjectRepository.load_many` --
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

        candidate_ids = self._date_index_candidate_ids(start, end)
        if candidate_ids is None or not candidate_ids <= index_ids:
            # Missing, empty-for-a-nonempty-bucket, or drifted relative to the
            # authoritative membership index: fall back to the full encrypted
            # scan and filter in memory so correctness never depends on the
            # plaintext index being present or fresh.
            full_catalogue = self.load()
            return TransactionCatalogue.from_transactions(
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
        return TransactionCatalogue.from_transactions(transactions)

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
        return TransactionCatalogue.from_transactions(transactions)

    def partition_by_date_range(self, start: date, end: date) -> LedgerDatePartition:
        """Split this bucket's catalogue into an in-window half and an out-of-window remainder.

        The period-first partition runs a completeness gate against the plaintext
        :class:`~adapters.persistence.storage.sql.TransactionDateIndexRow`
        rows for this bucket -- the index row count and id set must exactly
        match the encrypted membership index -- before trusting the index for
        a partition. On a completeness match, only the in-window transaction
        ids are decrypted through one targeted batch
        :meth:`~adapters.persistence.storage.SecureObjectRepository.load_many`;
        out-of-window ids are reported as plaintext
        :class:`~domain.transactions.OutOfWindowTransactionIndexEntry` rows (id +
        filing date only, never decrypted). On a completeness MISMATCH -- a
        stale or partially-synced index -- this falls back to a full
        :meth:`load` and partitions the result in memory, so correctness never
        depends on the index being present or fresh
        (``aeat-ledger-contract``): a stale index
        costs a slower read, never a silent drop from either half.

        Membership in the in-window half is decided by OVERLAP against each
        row's :func:`~domain.transactions.transaction_eligible_date_span`, not
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
            The :class:`~domain.transactions.LedgerDatePartition` for ``[start, end]``.
        """
        index_ids = self._load_index_ids()
        if not index_ids:
            return LedgerDatePartition(
                in_window=TransactionCatalogue.from_transactions([]),
                out_of_window=(),
                index_complete=True,
            )

        index_rows = self._all_date_index_rows()
        index_row_ids = set(index_rows)
        if index_row_ids != index_ids:
            # Stale, partially-synced, or missing index rows for this bucket:
            # fall back to a full decrypt scan and partition in memory so
            # correctness never depends on index freshness.
            full_catalogue = self.load()
            in_window: list[Transaction] = []
            out_of_window: list[OutOfWindowTransactionIndexEntry] = []
            for transaction in full_catalogue.values():
                dates = _IndexedTransactionDates.for_transaction(transaction)
                if dates.overlaps(start, end):
                    in_window.append(transaction)
                else:
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
                in_window=TransactionCatalogue.from_transactions(in_window),
                out_of_window=tuple(out_of_window),
                out_of_window_summary=OutOfWindowTransactionSummary.from_index_entries(out_of_window),
                index_complete=False,
            )

        in_window_ids = {transaction_id for transaction_id, dates in index_rows.items() if dates.overlaps(start, end)}
        transactions = self._load_transactions_by_ids(in_window_ids, read_context="partition read")

        out_of_window_rows = tuple(
            (transaction_id, dates.filing_date)
            for transaction_id, dates in index_rows.items()
            if transaction_id not in in_window_ids
        )
        out_of_window_summary = None
        if out_of_window_rows:
            out_of_window_dates = tuple(filing_date for _transaction_id, filing_date in out_of_window_rows)
            out_of_window_summary = OutOfWindowTransactionSummary(
                count=len(out_of_window_rows),
                min_filing_date=min(out_of_window_dates),
                max_filing_date=max(out_of_window_dates),
            )
        out_of_window_index_entries = (
            tuple(
                OutOfWindowTransactionIndexEntry(transaction_id=transaction_id, filing_date=filing_date)
                for transaction_id, filing_date in sorted(out_of_window_rows)
            )
            if len(out_of_window_rows) <= _OUT_OF_WINDOW_ROW_PROJECTION_LIMIT
            else ()
        )
        _log.debug(
            "partitioned transaction catalogue via date index bucket_id=%s window=%s..%s in_window=%d out_of_window=%d",
            self._bucket_id,
            start.isoformat(),
            end.isoformat(),
            len(transactions),
            len(out_of_window_rows),
        )
        return LedgerDatePartition(
            in_window=TransactionCatalogue.from_transactions(transactions),
            out_of_window=out_of_window_index_entries,
            out_of_window_summary=out_of_window_summary,
            index_complete=True,
        )

    def _load_transactions_by_ids(self, transaction_ids: Iterable[str], *, read_context: str) -> list[Transaction]:
        """Load selected transaction rows through one targeted secure-object batch."""
        from ..storage.crypto.encrypted_columns import secure_object_key_digest
        from ..storage.envelope._envelope import Envelope

        selected_ids = tuple(sorted(transaction_ids))
        if not selected_ids:
            return []

        transaction_id_by_digest = {
            secure_object_key_digest(transaction_object_key(self._bucket_id, transaction_id)): transaction_id
            for transaction_id in selected_ids
        }
        object_keys = tuple(transaction_object_key(self._bucket_id, transaction_id) for transaction_id in selected_ids)
        transactions_by_id: dict[str, Transaction] = {}
        records = self._objects.load_many_current(
            TX_BUCKET_NAMESPACE,
            object_keys,
            expected_class=_TX_CATALOGUE_SENSITIVITY,
            current_version=_TX_CATALOGUE_VERSION,
            refuse_legacy=self._refuse_targeted_implicit_migration,
        )
        for record in records:
            transaction_id = transaction_id_by_digest.get(bytes(record.object_key))
            if transaction_id is None:
                continue
            try:
                envelope = Envelope[Transaction].model_validate_json(record.payload)
            except ValidationError as exc:
                _log.error(
                    "transaction row schema drift bucket_id=%s (%s)",
                    self._bucket_id,
                    read_context,
                    exc_info=True,
                )
                raise StoredTransactionDriftError(self._bucket_id, exc) from exc
            transaction = envelope.payload
            self._assert_transaction_row_identity(transaction, expected_transaction_id=transaction_id)
            transactions_by_id[transaction_id] = transaction
        return [
            transactions_by_id[transaction_id]
            for transaction_id in selected_ids
            if transaction_id in transactions_by_id
        ]

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
            TX_BUCKET_NAMESPACE,
            expected_identifier=transaction_object_key(self._bucket_id, expected_transaction_id),
        )

    def _all_date_index_rows(self) -> dict[str, _IndexedTransactionDates]:
        """Return every ``{transaction_id: routing dates}`` this bucket's date index records."""
        with self._objects.guarded_session_scope() as session:
            rows = session.execute(
                select(
                    TransactionDateIndexRow.transaction_id,
                    TransactionDateIndexRow.filing_date,
                    TransactionDateIndexRow.eligible_from,
                    TransactionDateIndexRow.eligible_to,
                ).where(TransactionDateIndexRow.bucket_id == self._bucket_id),
            ).all()
            return {
                str(transaction_id): _IndexedTransactionDates(
                    filing_date=filing_date,
                    eligible_from=eligible_from,
                    eligible_to=eligible_to,
                )
                for transaction_id, filing_date, eligible_from, eligible_to in rows
            }

    def rebuild_date_index(self) -> int:
        """Rebuild this bucket's plaintext date index from the encrypted catalogue.

        The index is derived and rebuildable
        (``aeat-ledger-contract``): correctness
        never depends on it, so this is an explicit maintenance/recovery
        operation, not something callers need on the normal read/write path.
        Performs a full :meth:`load` (decrypting every row once) and rewrites
        the index rows for this bucket to exactly match it.

        Returns:
            The number of index rows written for this bucket.
        """
        catalogue = self.load()
        self._sync_date_index(catalogue)
        return len(catalogue.transactions)

    def _date_index_candidate_ids(self, start: date, end: date) -> set[str] | None:
        """Return the candidate transaction ids in ``[start, end]`` per the plaintext index.

        Returns ``None`` when this bucket has no rows in the index at all
        (distinguishing "index absent" from "index present but window empty",
        so :meth:`load_for_date_range` can tell a genuinely stale/missing
        index apart from a real empty result).
        """
        with self._objects.guarded_session_scope() as session:
            any_row = session.execute(
                select(TransactionDateIndexRow.id).where(TransactionDateIndexRow.bucket_id == self._bucket_id).limit(1),
            ).first()
            if any_row is None:
                return None
            rows = session.execute(
                select(TransactionDateIndexRow.transaction_id).where(
                    TransactionDateIndexRow.bucket_id == self._bucket_id,
                    TransactionDateIndexRow.filing_date >= start,
                    TransactionDateIndexRow.filing_date <= end,
                ),
            ).scalars()
            return set(rows)

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
        incoming: dict[str, _IndexedTransactionDates] = {
            transaction_id: _IndexedTransactionDates.for_transaction(transaction)
            for transaction_id, transaction in catalogue.transactions.items()
        }

        with self._objects.guarded_session_scope() as session:
            existing_rows = session.execute(
                select(
                    TransactionDateIndexRow.id,
                    TransactionDateIndexRow.transaction_id,
                    TransactionDateIndexRow.filing_date,
                    TransactionDateIndexRow.eligible_from,
                    TransactionDateIndexRow.eligible_to,
                ).where(TransactionDateIndexRow.bucket_id == self._bucket_id),
            ).all()
            existing: dict[str, tuple[int, _IndexedTransactionDates]] = {
                transaction_id: (
                    row_id,
                    _IndexedTransactionDates(
                        filing_date=filing_date,
                        eligible_from=eligible_from,
                        eligible_to=eligible_to,
                    ),
                )
                for row_id, transaction_id, filing_date, eligible_from, eligible_to in existing_rows
            }

            stale_ids = set(existing) - set(incoming)
            if stale_ids:
                session.execute(
                    delete(TransactionDateIndexRow).where(
                        TransactionDateIndexRow.bucket_id == self._bucket_id,
                        TransactionDateIndexRow.transaction_id.in_(stale_ids),
                    ),
                )

            new_rows: list[TransactionDateIndexRow] = []
            for transaction_id, dates in incoming.items():
                current = existing.get(transaction_id)
                if current is not None and current[1] == dates:
                    continue  # unchanged: leave the existing row untouched
                if current is not None:
                    session.execute(
                        update(TransactionDateIndexRow)
                        .where(TransactionDateIndexRow.id == current[0])
                        .values(
                            filing_date=dates.filing_date,
                            filing_year=dates.filing_date.year,
                            eligible_from=dates.eligible_from,
                            eligible_to=dates.eligible_to,
                        ),
                    )
                    continue
                new_rows.append(
                    TransactionDateIndexRow(
                        bucket_id=self._bucket_id,
                        transaction_id=transaction_id,
                        filing_date=dates.filing_date,
                        filing_year=dates.filing_date.year,
                        eligible_from=dates.eligible_from,
                        eligible_to=dates.eligible_to,
                    ),
                )
            if new_rows:
                session.add_all(new_rows)

    def _reconcile(
        self,
        catalogue: TransactionCatalogue,
    ) -> tuple[tuple[SecureObjectWrite, ...], tuple[SecureObjectDeletion, ...]]:
        """Diff ``catalogue`` against this bucket's stored rows.

        Returns ``(changed writes, deletions)``. Changed-row detection is a
        decryption-free
        :meth:`~adapters.persistence.storage.SecureObjectRepository.namespace_payload_hashes`
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
        """
        from ..storage.crypto.encrypted_columns import secure_object_key_digest
        from ..storage.sql import SecureObjectDeletion, SecureObjectWrite

        current_ids = self._load_index_ids()
        incoming_ids = set(catalogue.transactions)
        stored_hashes = self._objects.namespace_payload_hashes(TX_BUCKET_NAMESPACE)

        writes: list[SecureObjectWrite] = []
        for transaction_id, transaction in catalogue.transactions.items():
            object_key = transaction_object_key(self._bucket_id, transaction_id)
            digest = secure_object_key_digest(object_key)
            cached_hash = self._serialized_hash_cache.get(id(transaction))
            if cached_hash is not None and stored_hashes.get(digest) == cached_hash:
                continue
            payload = self._serialise_transaction(transaction)
            if cached_hash is None and stored_hashes.get(digest) == sha256_hex(payload):
                continue
            writes.append(
                SecureObjectWrite(
                    namespace=TX_BUCKET_NAMESPACE,
                    object_key=object_key,
                    classification=_TX_CATALOGUE_SENSITIVITY,
                    schema_version=_TX_CATALOGUE_VERSION,
                    written_at=transaction.modified_at,
                    payload=payload,
                ),
            )

        if incoming_ids != current_ids:
            writes.append(
                SecureObjectWrite(
                    namespace=TX_BUCKET_NAMESPACE,
                    object_key=transaction_index_object_key(self._bucket_id),
                    classification=_TX_CATALOGUE_SENSITIVITY,
                    schema_version=_TX_CATALOGUE_VERSION,
                    written_at=now(),
                    payload=self._serialise_index(incoming_ids),
                ),
            )

        deletions = tuple(
            SecureObjectDeletion(
                namespace=TX_BUCKET_NAMESPACE,
                hashed_object_key=secure_object_key_digest(transaction_object_key(self._bucket_id, transaction_id)),
            )
            for transaction_id in current_ids - incoming_ids
        )
        return tuple(writes), deletions

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

    def _require_current_rows(self, object_keys: Iterable[str]) -> None:
        """Refuse an ordinary read until the explicit catalogue cutover has persisted v2."""
        keys = tuple(object_keys)
        old = [
            object_key
            for object_key, schema_version in self._objects.peek_many_schema_versions(TX_BUCKET_NAMESPACE, keys).items()
            if schema_version != _TX_CATALOGUE_VERSION
        ]
        if old:
            raise LedgerStorageError("transaction catalogue requires explicit IVA authority migration before read")

    def _load_index_ids(self, *, require_current: bool = True) -> set[str]:
        """Return the transaction ids the per-bucket membership index records."""
        from ..storage._schema_lineage import inner_envelope_version_is_current
        from ..storage.envelope._envelope import Envelope

        index_key = transaction_index_object_key(self._bucket_id)
        record = self._objects.load(
            TX_BUCKET_NAMESPACE,
            index_key,
            expected_class=_TX_CATALOGUE_SENSITIVITY,
            max_supported_version=_TX_CATALOGUE_VERSION,
        )
        if record is None:
            return set()
        try:
            envelope = Envelope[_TransactionIndex].model_validate_json(record.payload)
        except ValidationError as exc:
            raise StoredTransactionDriftError(self._bucket_id, exc) from exc
        if require_current and not inner_envelope_version_is_current(
            envelope.schema_version,
            _TX_CATALOGUE_VERSION,
        ):
            raise LedgerStorageError("transaction catalogue requires explicit IVA authority migration before read")
        return set(envelope.payload.transaction_ids)

    def _serialise_index(self, transaction_ids: set[str]) -> bytes:
        """Serialise the membership index (sorted ids) into encrypted-row bytes."""
        from ..storage.envelope._envelope import Envelope

        envelope = Envelope[_TransactionIndex](
            schema_version=_TX_CATALOGUE_VERSION,
            written_at=now(),
            classification=_TX_CATALOGUE_SENSITIVITY,
            payload=_TransactionIndex(transaction_ids=tuple(sorted(transaction_ids))),
        )
        return envelope.model_dump_json().encode(UTF_8_ENCODING)

    def _serialise_transaction(self, transaction: Transaction) -> bytes:
        """Serialise one transaction into stable encrypted-row envelope bytes.

        The envelope ``written_at`` is the transaction's own ``modified_at`` (not
        ``now()``), so an unchanged transaction serialises to identical bytes —
        and an identical ``payload_hash`` — letting the diff skip rewriting it.
        """
        from ..storage.envelope._envelope import Envelope

        envelope = Envelope[Transaction](
            schema_version=_TX_CATALOGUE_VERSION,
            written_at=transaction.modified_at,
            classification=_TX_CATALOGUE_SENSITIVITY,
            payload=transaction,
        )
        return envelope.model_dump_json().encode(UTF_8_ENCODING)


__all__ = [
    "TransactionCatalogueRepository",
]
