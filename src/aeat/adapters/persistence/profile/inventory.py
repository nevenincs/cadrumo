"""Encrypted persistence for actividad economica inventory ledgers.

Wraps :mod:`aeat.adapters.persistence.storage`'s envelope, master-key, and
file-locking primitives to persist
:class:`aeat.domain.profile.inventory.InventoryLedger` payloads as
FINANCIAL-class ciphertext. Module-level helpers wrap the
:class:`InventoryLedgerRepository` for common one-shot operations.

Attributes:
    INVENTORY_LEDGER_FILENAME: Filename used inside the storage directory for
        the encrypted inventory envelope.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from ....core.config import load_settings
from ....core.logging import get_logger
from ....domain.profile.errors import InventoryLedgerError
from ....domain.profile.inventory import (
    InventoryLedger,
    InventoryLedgerDocument,
    MovementRecord,
    compute_inventory_valuation,
    parse_valuation_method,
)
from ..storage import Envelope, SensitivityClass, exclusive_file_lock, load_encrypted_envelope, save_encrypted_envelope
from ..storage.crypto._encrypted_columns import _resolve_master_key_provider

_log = get_logger(__name__)

INVENTORY_LEDGER_FILENAME = "inventory-ledger.envelope.json"
_ENVELOPE_VERSION = 1
_HKDF_CONTEXT_INVENTORY = b"aeat.domain.profile.inventory.ledger.v1"


def default_storage_dir() -> Path:
    """Return the configured governed ledger storage directory.

    Returns:
        Filesystem path resolved from
        :attr:`aeat.core.config.Settings.aeat_ledgers_dir`.
    """

    return Path(load_settings().aeat_ledgers_dir)


def load_inventory(*, storage_dir: Path | None = None) -> tuple[InventoryLedger, ...]:
    """Load inventory ledgers from the encrypted ledger.

    Args:
        storage_dir: Override for the ledger storage directory; defaults to
            :func:`default_storage_dir`.

    Returns:
        Tuple of persisted inventory ledgers, empty when no envelope exists.
    """

    return InventoryLedgerRepository(store_dir=storage_dir or default_storage_dir()).load().ledgers


def save_inventory(ledgers: tuple[InventoryLedger, ...], *, storage_dir: Path | None = None) -> Path:
    """Persist ``ledgers`` as a governed FINANCIAL-class encrypted envelope.

    Args:
        ledgers: Inventory ledgers to persist.
        storage_dir: Override for the ledger storage directory.

    Returns:
        Path to the encrypted envelope file that was written.
    """

    repository = InventoryLedgerRepository(store_dir=storage_dir or default_storage_dir())
    repository.save(InventoryLedgerDocument(ledgers=ledgers))
    return repository.envelope_path


def create_inventory_ledger(ledger: InventoryLedger, *, storage_dir: Path | None = None) -> InventoryLedgerDocument:
    """Atomically create ``ledger`` and refuse duplicate (actividad, year) pairs.

    Args:
        ledger: Inventory ledger to insert.
        storage_dir: Override for the ledger storage directory.

    Returns:
        The updated ledger document including the newly inserted ledger.

    Raises:
        :exc:`aeat.domain.profile.errors.InventoryLedgerError`: When a ledger
            with the same ``(actividad_id, year)`` pair already exists.
    """

    return InventoryLedgerRepository(store_dir=storage_dir or default_storage_dir()).create(ledger)


def record_movement(
    actividad_id: str,
    movement: MovementRecord,
    *,
    year: int,
    storage_dir: Path | None = None,
) -> InventoryLedger:
    """Append ``movement`` to an existing activity-and-year inventory ledger.

    Args:
        actividad_id: Identifier of the actividad economica owning the ledger.
        movement: Movement record to append.
        year: Tax year of the target ledger.
        storage_dir: Override for the ledger storage directory.

    Returns:
        The updated inventory ledger.

    Raises:
        :exc:`aeat.domain.profile.errors.InventoryLedgerError`: When the
            target ledger does not exist, the movement id is duplicated,
            or the resulting valuation is invalid.
    """

    return InventoryLedgerRepository(store_dir=storage_dir or default_storage_dir()).record_movement(
        actividad_id,
        movement,
        year=year,
    )


class InventoryLedgerRepository:
    """Governed repository for the encrypted inventory ledger.

    Each method takes an exclusive file lock on :attr:`lock_target` for the
    duration of the read-modify-write cycle so concurrent processes cannot
    corrupt the ledger envelope.
    """

    def __init__(self, *, store_dir: Path) -> None:
        """Initialize the repository.

        Args:
            store_dir: Directory in which the encrypted envelope and lock
                sidecar live.
        """
        self._store_dir = Path(store_dir)

    @property
    def envelope_path(self) -> Path:
        """Path to the canonical encrypted envelope file."""

        return self._store_dir / INVENTORY_LEDGER_FILENAME

    @property
    def lock_target(self) -> Path:
        """Path to the canonical exclusive-lock sidecar file."""

        return self._store_dir / "inventory-ledger.lock"

    def load(self) -> InventoryLedgerDocument:
        """Load the ledger, returning an empty document when absent.

        Returns:
            Decrypted inventory ledger document.

        Raises:
            :exc:`aeat.domain.profile.errors.InventoryLedgerError`: When the
                envelope exists but cannot be loaded or decrypted.
        """

        if not self.envelope_path.exists():
            return InventoryLedgerDocument()
        try:
            envelope = load_encrypted_envelope(
                self.envelope_path,
                Envelope[InventoryLedgerDocument],
                expected_class=SensitivityClass.FINANCIAL,
                master_key_provider=_resolve_master_key_provider(),
                hkdf_context=_HKDF_CONTEXT_INVENTORY,
                max_supported_version=_ENVELOPE_VERSION,
            )
            return envelope.payload
        except Exception as exc:
            raise InventoryLedgerError(f"unable to load inventory ledger: {self.envelope_path}") from exc

    def save(self, document: InventoryLedgerDocument) -> None:
        """Persist ``document`` as FINANCIAL-class ciphertext.

        Args:
            document: Ledger document to encrypt and write.
        """

        self._store_dir.mkdir(parents=True, exist_ok=True)
        with exclusive_file_lock(self.lock_target):
            envelope = Envelope[InventoryLedgerDocument](
                schema_version=_ENVELOPE_VERSION,
                written_at=datetime.now(UTC),
                classification=SensitivityClass.FINANCIAL,
                payload=document,
            )
            save_encrypted_envelope(
                envelope,
                self.envelope_path,
                master_key_provider=_resolve_master_key_provider(),
                hkdf_context=_HKDF_CONTEXT_INVENTORY,
            )
        _log.info("saved %d inventory ledgers to %s", len(document.ledgers), self.envelope_path)

    def create(self, ledger: InventoryLedger) -> InventoryLedgerDocument:
        """Atomically create ``ledger`` and refuse duplicate actividad/year pairs.

        Args:
            ledger: Inventory ledger to insert.

        Returns:
            The ledger document including the new ledger.

        Raises:
            :exc:`aeat.domain.profile.errors.InventoryLedgerError`: When a
                ledger with the same ``(actividad_id, year)`` pair exists.
        """

        self._store_dir.mkdir(parents=True, exist_ok=True)
        with exclusive_file_lock(self.lock_target):
            current = self._load_unlocked()
            if any(
                existing.actividad_id == ledger.actividad_id and existing.year == ledger.year
                for existing in current.ledgers
            ):
                raise InventoryLedgerError(
                    f"inventory ledger already exists for {ledger.actividad_id!r} in {ledger.year}",
                    context={"actividad_id": ledger.actividad_id, "year": ledger.year},
                    suggestion="aeat data ledgers inventory list",
                )
            updated = InventoryLedgerDocument(ledgers=(*current.ledgers, ledger))
            self._save_unlocked(updated)
            return updated

    def record_movement(self, actividad_id: str, movement: MovementRecord, *, year: int) -> InventoryLedger:
        """Atomically append ``movement`` after validating the new valuation.

        The replacement ledger is fully revalidated via
        :func:`aeat.domain.profile.inventory.compute_inventory_valuation`
        before being persisted, so any rule violation aborts the write.

        Args:
            actividad_id: Identifier of the owning actividad economica.
            movement: Movement record to append.
            year: Tax year of the target ledger.

        Returns:
            The updated inventory ledger.

        Raises:
            :exc:`aeat.domain.profile.errors.InventoryLedgerError`: When the
                target ledger does not exist, the movement id is duplicated,
                or the resulting valuation is invalid.
        """

        self._store_dir.mkdir(parents=True, exist_ok=True)
        with exclusive_file_lock(self.lock_target):
            ledgers = list(self._load_unlocked().ledgers)
            for index, ledger in enumerate(ledgers):
                if ledger.actividad_id == actividad_id and ledger.year == year:
                    if any(existing.movement_id == movement.movement_id for existing in ledger.period_movements):
                        raise InventoryLedgerError(
                            f"movement {movement.movement_id!r} already exists",
                            context={"movement_id": movement.movement_id},
                            suggestion="aeat data ledgers inventory valuation preview",
                        )
                    updated = ledger.model_copy(update={"period_movements": (*ledger.period_movements, movement)})
                    compute_inventory_valuation(updated)
                    ledgers[index] = updated
                    self._save_unlocked(InventoryLedgerDocument(ledgers=tuple(ledgers)))
                    return updated
        raise InventoryLedgerError(
            f"inventory ledger not found for {actividad_id!r} in {year}",
            context={"actividad_id": actividad_id, "year": year},
        )

    def _load_unlocked(self) -> InventoryLedgerDocument:
        if not self.envelope_path.exists():
            return InventoryLedgerDocument()
        envelope = load_encrypted_envelope(
            self.envelope_path,
            Envelope[InventoryLedgerDocument],
            expected_class=SensitivityClass.FINANCIAL,
            master_key_provider=_resolve_master_key_provider(),
            hkdf_context=_HKDF_CONTEXT_INVENTORY,
            max_supported_version=_ENVELOPE_VERSION,
        )
        return envelope.payload

    def _save_unlocked(self, document: InventoryLedgerDocument) -> None:
        envelope = Envelope[InventoryLedgerDocument](
            schema_version=_ENVELOPE_VERSION,
            written_at=datetime.now(UTC),
            classification=SensitivityClass.FINANCIAL,
            payload=document,
        )
        save_encrypted_envelope(
            envelope,
            self.envelope_path,
            master_key_provider=_resolve_master_key_provider(),
            hkdf_context=_HKDF_CONTEXT_INVENTORY,
        )


__all__ = [
    "InventoryLedgerRepository",
    "create_inventory_ledger",
    "default_storage_dir",
    "load_inventory",
    "record_movement",
    "save_inventory",
]
