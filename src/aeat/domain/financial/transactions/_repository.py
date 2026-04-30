"""Governed-persistence repository for the transaction catalogue.

Wraps the substrate's :class:`Envelope[TransactionCatalogue]` contract
behind a small, typed surface that the bank-import command and any
future consumer can call. Every read consults the envelope file
first; every write goes through ``save_encrypted_envelope`` at the
FINANCIAL sensitivity classification with an exclusive file lock for
the duration so concurrent writers serialise rather than race.

The repository is the only sanctioned read/write path for the
transaction catalogue. There is no plaintext fallback: every CLI
command and downstream consumer routes through this surface so the
on-disk record is always the encrypted envelope.

Idempotency is inherited from the existing
:func:`derive_transaction_id` SHA-256 hash on the
:class:`RawTransaction` shape: re-importing the same parser output
emits the same transaction IDs, so the merge helper skips IDs
already in the catalogue.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from ....adapters.persistence.storage._classification import SensitivityClass
from ....adapters.persistence.storage._encrypted_columns import _resolve_master_key_provider
from ....adapters.persistence.storage._envelope import Envelope, load_encrypted_envelope, save_encrypted_envelope
from ....adapters.persistence.storage._lock import exclusive_file_lock
from ....adapters.persistence.storage.errors import ClassificationError, EnvelopeVersionError
from ....core.logging import get_logger
from ._models import Transaction, TransactionCatalogue, derive_transaction_id

_HKDF_CONTEXT_TX_CATALOGUE = b"aeat.domain.financial.transactions.catalogue.v1"

if TYPE_CHECKING:
    from .._raw_transaction import RawTransaction
    from ._enums import TransactionDirection

_log = get_logger(__name__)

_TX_CATALOGUE_VERSION = 1
_TX_ENVELOPE_FILE_NAME = "transactions.envelope.json"
_TX_LOCK_FILE_NAME = "transactions.lock"


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
        catalogue_path: Resolved path to the envelope file.
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
    """Repository over the file-locked, envelope-backed catalogue."""

    def __init__(self, *, store_dir: Path) -> None:
        """Bind the repository to a store directory.

        Args:
            store_dir: Directory containing the envelope file and the
                lock sidecar. Created on first write.
        """
        self._store_dir = Path(store_dir)

    @property
    def envelope_path(self) -> Path:
        """Return the canonical envelope file path."""
        return self._store_dir / _TX_ENVELOPE_FILE_NAME

    @property
    def lock_target(self) -> Path:
        """Return the canonical lock sidecar path."""
        return self._store_dir / _TX_LOCK_FILE_NAME

    def load(self) -> TransactionCatalogue:
        """Return the persisted catalogue or an empty catalogue if absent.

        Raises:
            ClassificationError: If the on-disk envelope's class is not
                FINANCIAL.
            EnvelopeVersionError: If the envelope schema version is
                higher than the consumer supports.
        """
        target = self.envelope_path
        if not target.exists():
            return TransactionCatalogue()
        envelope = load_encrypted_envelope(
            target,
            Envelope[TransactionCatalogue],
            expected_class=SensitivityClass.FINANCIAL,
            master_key_provider=_resolve_master_key_provider(),
            hkdf_context=_HKDF_CONTEXT_TX_CATALOGUE,
            max_supported_version=_TX_CATALOGUE_VERSION,
        )
        return envelope.payload

    def save(self, catalogue: TransactionCatalogue) -> None:
        """Persist ``catalogue`` atomically under the file lock.

        The on-disk envelope is AES-256-GCM ciphertext at FINANCIAL
        class via the substrate's ``save_encrypted_envelope`` helper —
        no plaintext transaction row lands on disk.
        """
        self._store_dir.mkdir(parents=True, exist_ok=True)
        with exclusive_file_lock(self.lock_target):
            envelope = Envelope[TransactionCatalogue](
                schema_version=_TX_CATALOGUE_VERSION,
                written_at=datetime.now(UTC),
                classification=SensitivityClass.FINANCIAL,
                payload=catalogue,
            )
            save_encrypted_envelope(
                envelope,
                self.envelope_path,
                master_key_provider=_resolve_master_key_provider(),
                hkdf_context=_HKDF_CONTEXT_TX_CATALOGUE,
            )

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
        Concurrent imports against the same store serialise via the
        substrate's :func:`exclusive_file_lock`; a parallel writer that
        cannot acquire the lock within the helper's default timeout
        raises :class:`LockAcquisitionError`.

        Args:
            raw_transactions: Iterable of parser-produced
                :class:`RawTransaction` records.
            direction_resolver: Callable that maps each
                :class:`RawTransaction` to the
                :class:`TransactionDirection` Kent's bookkeeping
                expects (typically just inspecting the amount sign).

        Returns:
            A frozen :class:`ImportSummary`.
        """
        self._store_dir.mkdir(parents=True, exist_ok=True)
        with exclusive_file_lock(self.lock_target):
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
                direction = direction_resolver(raw)
                transaction = Transaction.model_validate(
                    {
                        "raw": raw,
                        "direction": direction,
                    }
                )
                new_transactions[tx_id] = transaction
                existing_ids.add(tx_id)
                imported += 1
            merged = TransactionCatalogue.model_validate({"transactions": new_transactions})
            envelope = Envelope[TransactionCatalogue](
                schema_version=_TX_CATALOGUE_VERSION,
                written_at=datetime.now(UTC),
                classification=SensitivityClass.FINANCIAL,
                payload=merged,
            )
            save_encrypted_envelope(
                envelope,
                self.envelope_path,
                master_key_provider=_resolve_master_key_provider(),
                hkdf_context=_HKDF_CONTEXT_TX_CATALOGUE,
            )
        _log.info(
            "merged raw transactions: imported=%d skipped=%d catalogue=%s",
            imported,
            skipped,
            self.envelope_path,
        )
        return ImportSummary(
            imported=imported,
            skipped=skipped,
            catalogue_path=str(self.envelope_path.resolve()),
        )


__all__ = [
    "ClassificationError",
    "DirectionResolver",
    "EnvelopeVersionError",
    "ImportSummary",
    "TransactionCatalogueRepository",
]
