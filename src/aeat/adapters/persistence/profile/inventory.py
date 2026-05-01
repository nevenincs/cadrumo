"""Encrypted persistence for actividad economica inventory ledgers."""

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
    """Return the configured governed ledger storage directory."""

    return Path(load_settings().aeat_ledgers_dir)


def load_inventory(*, storage_dir: Path | None = None) -> tuple[InventoryLedger, ...]:
    """Load inventory ledgers from the encrypted ledger."""

    return InventoryLedgerRepository(store_dir=storage_dir or default_storage_dir()).load().ledgers


def save_inventory(ledgers: tuple[InventoryLedger, ...], *, storage_dir: Path | None = None) -> Path:
    """Persist inventory ledgers as a governed encrypted envelope."""

    repository = InventoryLedgerRepository(store_dir=storage_dir or default_storage_dir())
    repository.save(InventoryLedgerDocument(ledgers=ledgers))
    return repository.envelope_path


def create_inventory_ledger(ledger: InventoryLedger, *, storage_dir: Path | None = None) -> InventoryLedgerDocument:
    """Atomically create ``ledger`` and refuse duplicates."""

    return InventoryLedgerRepository(store_dir=storage_dir or default_storage_dir()).create(ledger)


def record_movement(
    actividad_id: str,
    movement: MovementRecord,
    *,
    year: int,
    storage_dir: Path | None = None,
) -> InventoryLedger:
    """Append a movement to an existing activity/year ledger."""

    return InventoryLedgerRepository(store_dir=storage_dir or default_storage_dir()).record_movement(
        actividad_id,
        movement,
        year=year,
    )


class InventoryLedgerRepository:
    """Governed repository for the encrypted inventory ledger."""

    def __init__(self, *, store_dir: Path) -> None:
        self._store_dir = Path(store_dir)

    @property
    def envelope_path(self) -> Path:
        """Return the canonical encrypted envelope path."""

        return self._store_dir / INVENTORY_LEDGER_FILENAME

    @property
    def lock_target(self) -> Path:
        """Return the canonical lock sidecar path."""

        return self._store_dir / "inventory-ledger.lock"

    def load(self) -> InventoryLedgerDocument:
        """Load the ledger, returning an empty document when absent."""

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
        """Persist ``document`` as FINANCIAL-class ciphertext."""

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
        """Atomically create a ledger and refuse duplicate actividad/year pairs."""

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
        """Atomically append ``movement`` after validating valuation."""

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
