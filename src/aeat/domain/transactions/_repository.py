"""Governed-persistence repository for the transaction catalogue.

The repository is the only sanctioned read/write path for the
transaction catalogue. It stores the catalogue as an encrypted byte
object in the primary SQL backend at FINANCIAL sensitivity; no
plaintext transaction row, JSON catalogue, or envelope file lands on
disk.

Idempotency is inherited from the existing
:func:`derive_transaction_id` SHA-256 hash on the
:class:`RawTransaction` shape: re-importing the same parser output
emits the same transaction IDs, so the merge helper skips IDs
already in the catalogue.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ...adapters.persistence.storage.envelope._envelope import Envelope
from ...adapters.persistence.storage.sql import SecureObjectRepository
from ...adapters.persistence.storage.errors import ClassificationError, EnvelopeVersionError
from ...core.classification import SensitivityClass
from ...core.logging import get_logger
from ._models import Transaction, TransactionCatalogue, derive_transaction_id

if TYPE_CHECKING:
    from ._enums import TransactionDirection
    from ._raw_transaction import RawTransaction

_log = get_logger(__name__)

_TX_CATALOGUE_VERSION = 1
_TX_NAMESPACE = "aeat.domain.transactions"
_TX_OBJECT_KEY = "catalogue"


class ImportSummary(BaseModel):
    """Frozen summary of one ``aeat financial ingest --persist`` invocation.

    Attributes:
        imported: Number of new transactions persisted by this call.
        skipped: Number of input rows already present in the catalogue
            (idempotency hit; the deterministic
            :func:`derive_transaction_id` ensures re-imports do not
            duplicate).
        errors: Reserved for future per-row error counts; today the
            repository raises on any error rather than tallying.
        catalogue_path: Logical URI of the encrypted database object.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    imported: int = Field(ge=0)
    skipped: int = Field(ge=0)
    errors: int = Field(default=0, ge=0)
    catalogue_path: str


# Direction-resolver shape — the consumer supplies the per-row mapping
# from ``RawTransaction`` to a stable ``TransactionDirection``. Lives
# in this module's signature only; the existing financial code already
# provides resolvers via ``_models.from_raw`` etc.
DirectionResolver = Callable[["RawTransaction"], "TransactionDirection"]


class TransactionCatalogueRepository:
    """Repository over the encrypted SQL-backed transaction catalogue."""

    def __init__(self) -> None:
        self._objects = SecureObjectRepository()

    def exists(self) -> bool:
        """Return whether a transaction catalogue has been persisted."""

        return self._objects.exists(_TX_NAMESPACE, _TX_OBJECT_KEY)

    def load(self) -> TransactionCatalogue:
        """Return the persisted catalogue or an empty catalogue if absent.

        Raises:
            ClassificationError: If the persisted object's class is not
                FINANCIAL.
            EnvelopeVersionError: If the persisted object's schema version is
                higher than the consumer supports.
        """
        record = self._objects.load(
            _TX_NAMESPACE,
            _TX_OBJECT_KEY,
            expected_class=SensitivityClass.FINANCIAL,
            max_supported_version=_TX_CATALOGUE_VERSION,
        )
        if record is None:
            _log.debug("transaction catalogue not found; returning empty catalogue")
            return TransactionCatalogue()
        try:
            envelope = Envelope[TransactionCatalogue].model_validate_json(record.payload.decode("utf-8"))
        except (ClassificationError, EnvelopeVersionError):
            _log.error("transaction catalogue integrity error", exc_info=True)
            raise
        if envelope.classification is not SensitivityClass.FINANCIAL:
            raise ClassificationError(
                f"transaction catalogue has classification {envelope.classification}; "
                f"consumer expected {SensitivityClass.FINANCIAL}",
            )
        if envelope.schema_version > _TX_CATALOGUE_VERSION:
            raise EnvelopeVersionError(
                f"transaction catalogue is at version {envelope.schema_version}; "
                f"consumer supports up to {_TX_CATALOGUE_VERSION}",
            )
        catalogue = envelope.payload
        _log.debug("loaded transaction catalogue with %d entries", len(catalogue.transactions))
        return catalogue

    def save(self, catalogue: TransactionCatalogue) -> None:
        """Persist ``catalogue`` in the encrypted database object store.

        The on-disk database value is an encrypted BLOB at FINANCIAL
        class. No plaintext transaction row lands on disk.
        """
        envelope = Envelope[TransactionCatalogue](
            schema_version=_TX_CATALOGUE_VERSION,
            written_at=datetime.now(UTC),
            classification=SensitivityClass.FINANCIAL,
            payload=catalogue,
        )
        self._objects.save(
            namespace=_TX_NAMESPACE,
            object_key=_TX_OBJECT_KEY,
            classification=SensitivityClass.FINANCIAL,
            schema_version=_TX_CATALOGUE_VERSION,
            written_at=envelope.written_at,
            payload=envelope.model_dump_json().encode("utf-8"),
        )
        _log.info("saved transaction catalogue with %d entries", len(catalogue.transactions))

    def merge_raw_transactions(
        self,
        raw_transactions: Iterable[RawTransaction],
        *,
        direction_resolver: DirectionResolver,
    ) -> ImportSummary:
        """Merge ``raw_transactions`` into the catalogue and persist atomically.

        Re-imports are idempotent: rows whose
        :func:`derive_transaction_id` is already present in the
        catalogue are skipped (counted under ``ImportSummary.skipped``).
        Concurrent imports against the same database object are governed
        by the SQL transaction boundary.

        Args:
            raw_transactions: Iterable of parser-produced
                :class:`RawTransaction` records.
            direction_resolver: Callable that maps each
                :class:`RawTransaction` to the
                :class:`TransactionDirection` the operator's bookkeeping
                expects (typically just inspecting the amount sign).

        Returns:
            A frozen :class:`ImportSummary`.
        """
        current = self.load()
        existing_ids = set(current.transactions.keys())
        imported = 0
        skipped = 0
        new_transactions: dict[str, Transaction] = dict(current.transactions)
        for raw in raw_transactions:
            tx_id = derive_transaction_id(raw)
            if tx_id in existing_ids:
                skipped += 1
                continue
            try:
                direction = direction_resolver(raw)
                transaction = Transaction.model_validate(
                    {
                        "raw": raw,
                        "direction": direction,
                    }
                )
            except (ValueError, ValidationError):
                _log.error(
                    "merge_raw_transactions: failed to process tx_id=%s from %s row=%d",
                    tx_id,
                    raw.provenance.source_path,
                    raw.provenance.source_row_index,
                    exc_info=True,
                )
                raise
            new_transactions[tx_id] = transaction
            existing_ids.add(tx_id)
            imported += 1
        merged = TransactionCatalogue.model_validate({"transactions": new_transactions})
        self.save(merged)
        _log.info(
            "merged raw transactions: imported=%d skipped=%d catalogue=%s",
            imported,
            skipped,
            _TX_OBJECT_KEY,
        )
        return ImportSummary(
            imported=imported,
            skipped=skipped,
            catalogue_path=f"db://secure_objects/{_TX_NAMESPACE}/{_TX_OBJECT_KEY}",
        )


__all__ = [
    "ClassificationError",
    "EnvelopeVersionError",
    "ImportSummary",
    "TransactionCatalogueRepository",
]
