"""Encrypted SQL persistence for actividad economica inventory ledgers.

:class:`aeat.domain.profile.inventory.InventoryLedger` payloads are stored
as FINANCIAL-class secure objects in the primary database.
"""

from __future__ import annotations

from pathlib import Path

from ....core.errors import AeatError
from ....core.logging import get_logger
from ....domain.profile.errors import InventoryLedgerError
from ....domain.profile.inventory import (
    InventoryLedger,
    InventoryLedgerDocument,
    MovementRecord,
    compute_inventory_valuation,
)
from ..storage import SensitivityClass
from ..storage.sql import SecureObjectRepository

_log = get_logger(__name__)

INVENTORY_LEDGER_FILENAME = "inventory-ledger.secure-object"
_SECURE_OBJECT_VERSION = 1
_INVENTORY_NAMESPACE = "aeat.persistence.profile.inventory"
_LEDGER_OBJECT_KEY = "default"


def load_inventory() -> tuple[InventoryLedger, ...]:
    """Load inventory ledgers from the encrypted ledger.

    Returns:
        Tuple of persisted inventory ledgers, empty when no envelope exists.
    """

    return InventoryLedgerRepository().load().ledgers


def save_inventory(ledgers: tuple[InventoryLedger, ...]) -> Path:
    """Persist ``ledgers`` as a governed FINANCIAL-class secure object.

    Args:
        ledgers: Inventory ledgers to persist.

    Returns:
        Logical path identifying the secure object.
    """

    repository = InventoryLedgerRepository()
    repository.save(InventoryLedgerDocument(ledgers=ledgers))
    return repository.envelope_path


def create_inventory_ledger(ledger: InventoryLedger) -> InventoryLedgerDocument:
    """Atomically create ``ledger`` and refuse duplicate (actividad, year) pairs.

    Args:
        ledger: Inventory ledger to insert.

    Returns:
        The updated ledger document including the newly inserted ledger.

    Raises:
        :exc:`aeat.domain.profile.errors.InventoryLedgerError`: When a ledger
            with the same ``(actividad_id, year)`` pair already exists.
    """

    return InventoryLedgerRepository().create(ledger)


def record_movement(
    actividad_id: str,
    movement: MovementRecord,
    *,
    year: int,
) -> InventoryLedger:
    """Append ``movement`` to an existing activity-and-year inventory ledger.

    Args:
        actividad_id: Identifier of the actividad economica owning the ledger.
        movement: Movement record to append.
        year: Tax year of the target ledger.

    Returns:
        The updated inventory ledger.

    Raises:
        :exc:`aeat.domain.profile.errors.InventoryLedgerError`: When the
            target ledger does not exist, the movement id is duplicated,
            or the resulting valuation is invalid.
    """

    return InventoryLedgerRepository().record_movement(
        actividad_id,
        movement,
        year=year,
    )


class InventoryLedgerRepository:
    """Governed repository for the encrypted inventory ledger."""

    def __init__(self, *, objects: SecureObjectRepository | None = None) -> None:
        """Construct the repository.

        Args:
            objects: Optional injected secure-object repository. When
                supplied, every encrypted-store read and write is routed
                through it instead of a :class:`SecureObjectRepository`
                resolved from the pydantic-settings :class:`Settings`
                object. This is the dependency-injection seam
                real-adapter tests use to bind a single explicit SQLite
                engine; production callers leave it ``None`` and the
                repository self-resolves from settings.
        """

        self._objects = objects if objects is not None else SecureObjectRepository()

    @property
    def envelope_path(self) -> Path:
        """Logical path retained for callers that display the storage target."""

        return Path("db://secure_objects") / _INVENTORY_NAMESPACE / INVENTORY_LEDGER_FILENAME

    @property
    def lock_target(self) -> Path:
        """Logical lock marker; SQL transactions govern writes."""

        return Path("db://secure_objects") / _INVENTORY_NAMESPACE / "inventory-ledger.lock"

    def load(self) -> InventoryLedgerDocument:
        """Load the ledger, returning an empty document when absent.

        Returns:
            Decrypted inventory ledger document.

        Raises:
            :exc:`aeat.domain.profile.errors.InventoryLedgerError`: When the
                envelope exists but cannot be loaded or decrypted.
        """

        try:
            record = self._objects.load(
                _INVENTORY_NAMESPACE,
                self._object_key,
                expected_class=SensitivityClass.FINANCIAL,
                max_supported_version=_SECURE_OBJECT_VERSION,
            )
            if record is None:
                return InventoryLedgerDocument()
            return InventoryLedgerDocument.model_validate_json(record.payload.decode("utf-8"))
        except (OSError, AeatError) as exc:
            raise InventoryLedgerError(f"unable to load inventory ledger: {self._object_key}") from exc

    def save(self, document: InventoryLedgerDocument) -> None:
        """Persist ``document`` as FINANCIAL-class ciphertext.

        Args:
            document: Ledger document to encrypt and write.
        """

        self._save_unlocked(document)
        _log.info("saved %d inventory ledgers to secure object %s", len(document.ledgers), self._object_key)

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

        current = self._load_unlocked()
        if any(
            existing.actividad_id == ledger.actividad_id and existing.year == ledger.year
            for existing in current.ledgers
        ):
            raise InventoryLedgerError(
                f"inventory ledger already exists for {ledger.actividad_id!r} in {ledger.year}",
                context={"actividad_id": ledger.actividad_id, "year": ledger.year},
                suggestion="aeat app ledger inventory list",
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

        ledgers = list(self._load_unlocked().ledgers)
        for index, ledger in enumerate(ledgers):
            if ledger.actividad_id == actividad_id and ledger.year == year:
                if any(existing.movement_id == movement.movement_id for existing in ledger.period_movements):
                    raise InventoryLedgerError(
                        f"movement {movement.movement_id!r} already exists",
                        context={"movement_id": movement.movement_id},
                        suggestion="aeat app ledger inventory valuation preview",
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
        return self.load()

    def _save_unlocked(self, document: InventoryLedgerDocument) -> None:
        from datetime import UTC, datetime

        self._objects.save(
            namespace=_INVENTORY_NAMESPACE,
            object_key=self._object_key,
            classification=SensitivityClass.FINANCIAL,
            schema_version=_SECURE_OBJECT_VERSION,
            written_at=datetime.now(UTC),
            payload=document.model_dump_json().encode("utf-8"),
        )

    @property
    def _object_key(self) -> str:
        return _LEDGER_OBJECT_KEY


__all__ = [
    "InventoryLedgerRepository",
    "create_inventory_ledger",
    "load_inventory",
    "record_movement",
    "save_inventory",
]
