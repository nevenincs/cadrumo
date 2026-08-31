"""Encrypted SQL persistence for actividad economica inventory ledgers.

:class:`InventoryLedger` payloads are grouped in
:class:`InventoryLedgerDocument` and stored as
``FINANCIAL`` :class:`adapters.persistence.storage.SensitivityClass`
secure objects in the primary database through
:class:`adapters.persistence.storage.SecureObjectRepository`. The
singleton namespace, default object key, schema version, and custody contract
come from
:data:`adapters.persistence.storage.PROFILE_INVENTORY_LEDGER_NAMESPACE`.

See Also:
    :mod:`domain.contribuyente.inventory`
        Typed inventory ledger, movement, and valuation payload models persisted
        here.
    :mod:`application.inventory`
        Application service layer that validates inventory commands before this
        adapter writes the encrypted secure object.
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from pydantic import ValidationError

from ....core.errors.hierarchy import CadrumoError
from ....core.logging import get_logger
from ....domain.contribuyente.inventory.records import (
    InventoryClosingAuthorityRecord,
    InventoryLedger,
    InventoryLedgerDocument,
    InventoryLedgerError,
    MovementRecord,
)
from ..storage.secure_object_namespaces import PROFILE_INVENTORY_LEDGER_NAMESPACE
from ..storage.sql import SecureObjectRepository
from ._secure_model_document import (
    ProfileBareModelSecurePersistence,
    resolve_profile_secure_object_repository,
)

_log = get_logger(__name__)

INVENTORY_LEDGER_FILENAME = "inventory-ledger.secure-object"


class InventoryClosingAuthorityConflictError(RuntimeError):
    """A different immutable closing-authority record already exists."""

    __bare_base_rationale__: ClassVar[str] = (
        "internal-inventory-closing-authority-conflict-carrier: the service catches this by name and re- "
        "raises InventoryServiceInputError, which carries the registered code and the operator message"
    )


def load_inventory() -> tuple[InventoryLedger, ...]:
    """Load inventory ledgers from the encrypted ledger.

    Returns:
        Tuple of :class:`InventoryLedger` records, empty when no envelope exists.
    """
    return InventoryLedgerRepository().load().ledgers


def save_inventory(ledgers: tuple[InventoryLedger, ...]) -> Path:
    """Persist ``ledgers`` as a governed FINANCIAL-class secure object.

    The storage contract comes from
    :data:`adapters.persistence.storage.PROFILE_INVENTORY_LEDGER_NAMESPACE`.

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
        The updated :class:`InventoryLedgerDocument` including the newly inserted ledger.
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
        The updated :class:`InventoryLedger`.
    """
    return InventoryLedgerRepository().record_movement(
        actividad_id,
        movement,
        year=year,
    )


class InventoryLedgerRepository:
    """Governed repository for the encrypted :class:`InventoryLedgerDocument` singleton.

    The singleton row is owned by
    :data:`adapters.persistence.storage.PROFILE_INVENTORY_LEDGER_NAMESPACE`
    and persisted through
    :class:`adapters.persistence.storage.SecureObjectRepository`.
    """

    def __init__(self, *, objects: SecureObjectRepository | None = None) -> None:
        """Construct the repository.

        Args:
            objects: Optional injected secure-object repository. When
                supplied, every encrypted-store read and write is routed
                through it instead of a
                :class:`adapters.persistence.storage.SecureObjectRepository`
                resolved from the pydantic-settings :class:`Settings`
                object. This is the dependency-injection seam
                real-adapter tests use to bind a single explicit SQLite
                engine; production callers leave it ``None`` and the
                repository self-resolves from settings.
        """
        self._storage = ProfileBareModelSecurePersistence(
            objects=resolve_profile_secure_object_repository(objects=objects),
            definition=PROFILE_INVENTORY_LEDGER_NAMESPACE,
            model_type=InventoryLedgerDocument,
            empty_document=InventoryLedgerDocument,
        )

    @property
    def envelope_path(self) -> Path:
        """Logical path retained for callers that display the storage target."""
        return self._storage.logical_path(INVENTORY_LEDGER_FILENAME)

    @property
    def lock_target(self) -> Path:
        """Logical lock marker; SQL transactions govern writes."""
        return self._storage.logical_path("inventory-ledger.lock")

    def load(self) -> InventoryLedgerDocument:
        """Load the ledger, returning an empty document when absent.

        Returns:
            Decrypted :class:`InventoryLedgerDocument`.

        Raises:
            InventoryLedgerError: When the envelope exists but cannot be loaded or decrypted.
        """
        try:
            return self._storage.load()
        except (OSError, CadrumoError, ValidationError) as exc:
            _log.debug(
                "inventory ledger load failed",
                extra={
                    "namespace": self._storage.namespace,
                    "object_key": self._storage.object_key,
                    "error_type": type(exc).__name__,
                },
            )
        # Raise outside the handler so Python does not retain the decrypted
        # validation failure as ``__context__`` on the safe public error.
        raise InventoryLedgerError(
            f"unable to load inventory ledger: {self._storage.object_key}",
            context={"namespace": self._storage.namespace, "object_key": self._storage.object_key},
            translated_message="adapters.persistence.profile.inventory.errors.load_inventory_ledger_failed",
        ) from None

    def save(self, document: InventoryLedgerDocument) -> None:
        """Persist ``document`` as FINANCIAL-class ciphertext.

        The classification, schema version, namespace, and object key are taken
        from
        :data:`adapters.persistence.storage.PROFILE_INVENTORY_LEDGER_NAMESPACE`.

        Args:
            document: Ledger document to encrypt and write.
        """
        self._save_unlocked(document)
        _log.info("saved %d inventory ledgers to secure object %s", len(document.ledgers), self._storage.object_key)

    def create(self, ledger: InventoryLedger) -> InventoryLedgerDocument:
        """Atomically create ``ledger`` and refuse duplicate actividad/year pairs.

        Args:
            ledger: Inventory ledger to insert.

        Returns:
            The :class:`InventoryLedgerDocument` including the new ledger.

        The document is a singleton row, so creating one ledger rewrites the
        whole document. Read, duplicate-check, rebuild, and write ran unguarded,
        so two callers creating ledgers for DIFFERENT activity/year pairs both
        read the same document and the later write silently discarded the
        earlier ledger -- a lost update the pair check could never notice,
        because the two ledgers never met in one document.

        The mutation now runs through the shared revision-guarded unit of work,
        with the duplicate check inside it so it is re-evaluated against the
        newly-current document on every attempt.

        Raises:
            InventoryLedgerError: When a ledger with the same ``(actividad_id, year)`` pair exists.
            SecureObjectRevisionConflictError: When contention persists across
                every attempt.
        """

        def _insert(current: InventoryLedgerDocument) -> InventoryLedgerDocument:
            if any(
                existing.actividad_id == ledger.actividad_id and existing.year == ledger.year
                for existing in current.ledgers
            ):
                raise InventoryLedgerError(
                    f"inventory ledger already exists for {ledger.actividad_id!r} in {ledger.year}",
                    context={"actividad_id": ledger.actividad_id, "year": ledger.year},
                    translated_message="adapters.persistence.profile.inventory.errors.inventory_ledger_already_exists",
                )
            return InventoryLedgerDocument(ledgers=(*current.ledgers, ledger))

        return self._storage.mutate(_insert)

    def remove(self, actividad_id: str, *, year: int) -> InventoryLedger:
        """Atomically drop the ledger for ``actividad_id`` and ``year``.

        Args:
            actividad_id: Activity whose ledger is removed.
            year: Filing year of the ledger to remove.

        Returns:
            The :class:`InventoryLedger` that was removed.

        The document is a singleton row, so removing one ledger rewrites the
        whole document -- which means an unguarded removal discards a ledger
        created for a DIFFERENT activity in the interim, losing an entire
        activity's inventory for an operator who was deleting something else.

        The absence check runs inside the guarded unit of work, so a retry
        re-judges it against the newly-current document: a ledger removed by a
        concurrent caller must refuse as absent rather than report a second
        successful removal of something already gone.

        Raises:
            InventoryLedgerError: When no ledger exists for the pair.
            SecureObjectRevisionConflictError: When contention persists across
                every attempt.
        """
        removed: list[InventoryLedger] = []

        def _drop(current: InventoryLedgerDocument) -> InventoryLedgerDocument:
            target = next(
                (
                    existing
                    for existing in current.ledgers
                    if existing.actividad_id == actividad_id and existing.year == year
                ),
                None,
            )
            if target is None:
                raise InventoryLedgerError(
                    f"no inventory ledger for {actividad_id!r} in {year}",
                    context={"actividad_id": actividad_id, "year": year},
                    translated_message="adapters.persistence.profile.inventory.errors.inventory_ledger_absent",
                )
            removed.clear()
            removed.append(target)
            return InventoryLedgerDocument(
                ledgers=tuple(existing for existing in current.ledgers if existing is not target),
            )

        self._storage.mutate(_drop)
        return removed[0]

    def record_movement(self, actividad_id: str, movement: MovementRecord, *, year: int) -> InventoryLedger:
        """Atomically append ``movement`` to the target activity-and-year ledger.

        The domain valuation guard (rejecting movements that would produce an
        invalid valuation) is owned by the application inventory service, which
        runs it before invoking persistence; this adapter performs the storage
        append only and runs no domain calculation.

        Args:
            actividad_id: Identifier of the owning actividad economica.
            movement: Movement record to append.
            year: Tax year of the target ledger.

        Returns:
            The updated :class:`InventoryLedger`.

        Carries the same revision guard as :meth:`create`, and needs it more:
        appending a movement rewrites the WHOLE singleton document, so an
        unguarded append discarded any ledger — or any other activity's
        movement — that landed between this call's read and its write.

        Raises:
            InventoryLedgerError: When the target ledger does not exist or the
                movement id is duplicated.
            SecureObjectRevisionConflictError: When contention persists across
                every attempt.
        """

        def _append(current: InventoryLedgerDocument) -> InventoryLedgerDocument:
            ledgers = list(current.ledgers)
            for index, ledger in enumerate(ledgers):
                if ledger.actividad_id == actividad_id and ledger.year == year:
                    if any(existing.movement_id == movement.movement_id for existing in ledger.period_movements):
                        raise InventoryLedgerError(
                            f"movement {movement.movement_id!r} already exists",
                            context={"movement_id": movement.movement_id},
                            translated_message="adapters.persistence.profile.inventory.errors.movement_already_exists",
                        )
                    ledgers[index] = ledger.model_copy(
                        update={"period_movements": (*ledger.period_movements, movement)},
                    )
                    return InventoryLedgerDocument(ledgers=tuple(ledgers))
            raise InventoryLedgerError(
                f"inventory ledger not found for {actividad_id!r} in {year}",
                context={"actividad_id": actividad_id, "year": year},
                translated_message="adapters.persistence.profile.inventory.errors.inventory_ledger_not_found",
            )

        # Re-read the target out of the committed document rather than closing
        # over the value built inside the mutation: ``mutate`` may run it more
        # than once, and only the winning attempt's ledger is the one persisted.
        document = self._storage.mutate(_append)
        return next(item for item in document.ledgers if item.actividad_id == actividad_id and item.year == year)

    def record_closing_authority(
        self,
        actividad_id: str,
        authority_record: InventoryClosingAuthorityRecord,
        *,
        year: int,
    ) -> InventoryLedger:
        """Atomically replace the target ledger's complete closing-authority record."""

        def _replace(current: InventoryLedgerDocument) -> InventoryLedgerDocument:
            ledgers = list(current.ledgers)
            for index, ledger in enumerate(ledgers):
                if ledger.actividad_id == actividad_id and ledger.year == year:
                    existing_record = ledger.closing_authority_record
                    if existing_record is not None:
                        if existing_record.fingerprint == authority_record.fingerprint:
                            return current
                        raise InventoryClosingAuthorityConflictError(
                            "inventory closing authority already exists with different provenance",
                        )
                    updated = ledger.model_copy(update={"closing_authority_record": authority_record})
                    # Rehydrate instead of trusting ``model_copy`` so every nested
                    # fingerprint and canonical resolver invariant runs before write.
                    ledgers[index] = InventoryLedger.model_validate(updated.model_dump())
                    return InventoryLedgerDocument(ledgers=tuple(ledgers))
            raise InventoryLedgerError(
                f"inventory ledger not found for {actividad_id!r} in {year}",
                context={"actividad_id": actividad_id, "year": year},
                translated_message="adapters.persistence.profile.inventory.errors.inventory_ledger_not_found",
            )

        document = self._storage.mutate(_replace)
        return next(item for item in document.ledgers if item.actividad_id == actividad_id and item.year == year)

    def _save_unlocked(self, document: InventoryLedgerDocument) -> None:
        self._storage.save(document)


__all__ = [
    "InventoryClosingAuthorityConflictError",
    "InventoryLedgerRepository",
    "create_inventory_ledger",
    "load_inventory",
    "record_movement",
    "save_inventory",
]
