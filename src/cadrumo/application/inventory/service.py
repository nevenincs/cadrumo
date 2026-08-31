"""Inventory application service: bucket-scoped CRUD over :class:`InventoryLedger`.

The service persists :class:`InventoryLedgerDocument` through
:class:`InventoryLedgerRepository`, whose runtime default is built by
:func:`~adapters.persistence.storage.secure_object_repository_for_bucket`.
It does not read or write plaintext inventory JSON side stores.

State-changing and audit-significant verbs append events to the
per-bucket audit trail via :class:`BucketEventHistoryRepository`;
valuation math remains delegated to :func:`compute_inventory_valuation`.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, NonNegativeInt, model_validator

from ...adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ...adapters.persistence.profile.inventory import (
    InventoryClosingAuthorityConflictError,
    InventoryLedgerRepository,
)
from ...adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
from ...core.config import Settings
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.time.clock import now as _now_utc
from ...domain.buckets.event import BucketEventObjectType, BucketEventType
from ...domain.buckets.event_repository import emit_bucket_event
from ...domain.buckets.protocols import BucketEventHistoryRepositoryProtocol
from ...domain.contribuyente.inventory.records import (
    InventoryAcquisitionCost,
    InventoryClosingAuthorityRecord,
    InventoryLedger,
    InventoryLedgerDocument,
    InventoryLedgerError,
    InventoryValuationResult,
    MovementKind,
    MovementRecord,
    ValuationMethod,
    parse_valuation_method,
)
from ...domain.contribuyente.inventory.valuation import compute_inventory_valuation
from .errors import (
    InventoryActividadConflictError,
    InventoryActividadNotFoundError,
    InventoryServiceInputError,
)


class InventoryActividadSummary(BaseModel):
    """One row in ``inventory list``.

    The row summarizes actividad, year, :class:`ValuationMethod`, opening
    stock, and movement count without returning the full
    :class:`InventoryLedger`.
    """

    model_config = STRICT_FROZEN_CONFIG

    actividad_id: str = Field(min_length=1)
    year: int = Field(ge=1900)
    valuation_method: ValuationMethod
    opening_stock: Decimal = Field(ge=Decimal("0"))
    movement_count: NonNegativeInt


class InventoryMovementCommand(BaseModel):
    """Strict input shape for ``inventory movement add``.

    The command is projected into a domain :class:`MovementRecord` with a
    closed :class:`MovementKind` before valuation and persistence.
    """

    model_config = STRICT_FROZEN_CONFIG

    movement_id: str = Field(min_length=1, max_length=64)
    movement_date: date
    kind: MovementKind
    quantity: Decimal
    unit_cost: Decimal | None = Field(default=None)
    taxable_base: Decimal | None = Field(default=None)
    acquisition_cost: InventoryAcquisitionCost | None = None

    @model_validator(mode="after")
    def _purchase_has_one_cost_authority(self) -> InventoryMovementCommand:
        if self.kind is MovementKind.PURCHASE:
            if self.acquisition_cost is None:
                raise ValueError("purchase movements require acquisition_cost")
            if self.unit_cost is not None or self.taxable_base is not None:
                raise ValueError("purchase movements refuse legacy unit_cost and taxable_base authorities")
        elif self.acquisition_cost is not None:
            raise ValueError("acquisition_cost is permitted only for purchase movements")
        return self


class InventoryValuationPreview(BaseModel):
    """Operator-facing projection of an :class:`InventoryValuationResult`."""

    model_config = STRICT_FROZEN_CONFIG

    actividad_id: str = Field(min_length=1)
    year: int = Field(ge=1900)
    valuation_method: ValuationMethod
    derived_closing_value: Decimal = Field(ge=Decimal("0"))
    cogs: Decimal = Field(ge=Decimal("0"))


class InventoryLedgerResult(BaseModel):
    """Return record from a mutating inventory verb.

    ``ledger`` is the affected :class:`InventoryLedger`; ``bucket_event_ids``
    lists the audit events emitted for the application operation.
    """

    model_config = STRICT_FROZEN_CONFIG

    ledger: InventoryLedger
    bucket_event_ids: tuple[str, ...] = ()


class InventoryValuationPreviewResult(BaseModel):
    """Return record from ``valuation_preview`` plus emitted event id."""

    model_config = STRICT_FROZEN_CONFIG

    preview: InventoryValuationPreview
    bucket_event_ids: tuple[str, ...] = ()


_INVENTORY_EVENT_PAYLOAD_VERSION = 1
InventoryRepositoryFactory = Callable[[str], InventoryLedgerRepository]
"""Factory that builds an :class:`InventoryLedgerRepository` for a bucket id."""


def _emit_inventory_event(
    *,
    event_repository: BucketEventHistoryRepositoryProtocol,
    bucket_id: str,
    event_type: BucketEventType,
    actividad_id: str,
    year: int,
    actor: str,
    occurred_at: datetime,
    payload: dict[str, str],
) -> str:
    event = emit_bucket_event(
        repository=event_repository,
        bucket_id=bucket_id,
        event_type=event_type,
        occurred_at=occurred_at,
        actor=actor,
        object_type=BucketEventObjectType.LEDGER_CATALOGUE,
        object_id=f"{actividad_id}:{year}",
        payload=payload,
        payload_version=_INVENTORY_EVENT_PAYLOAD_VERSION,
    )
    return event.event_id


def _runtime_repository_factory(settings: Settings) -> InventoryRepositoryFactory:
    def _factory(bucket_id: str) -> InventoryLedgerRepository:
        return InventoryLedgerRepository(
            objects=secure_object_repository_for_bucket(bucket_id, settings),
        )

    return _factory


def inventory_ledger_repository_for_bucket(bucket_id: str) -> InventoryLedgerRepository:
    """Compose the encrypted inventory repository for one explicit bucket."""
    return InventoryLedgerRepository(objects=secure_object_repository_for_bucket(bucket_id))


def _find_ledger(document: InventoryLedgerDocument, actividad_id: str, year: int) -> InventoryLedger | None:
    for ledger in document.ledgers:
        if ledger.actividad_id == actividad_id and ledger.year == year:
            return ledger
    return None


def _replace_ledger(document: InventoryLedgerDocument, ledger: InventoryLedger) -> InventoryLedgerDocument:
    others = tuple(
        existing
        for existing in document.ledgers
        if not (existing.actividad_id == ledger.actividad_id and existing.year == ledger.year)
    )
    return InventoryLedgerDocument(ledgers=(*others, ledger))


class InventoryService:
    """Bucket-scoped CRUD over per-actividad :class:`InventoryLedger` records.

    Runtime construction routes the repository through
    :func:`~adapters.persistence.storage.secure_object_repository_for_bucket`,
    so the requested ``bucket_id`` is checked by the storage runtime instead
    of bypassing custody with a local file path. Tests may inject an
    :class:`InventoryLedgerRepository` factory or
    :class:`BucketEventHistoryRepository` protocol implementation.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        bucket_event_repository: BucketEventHistoryRepositoryProtocol | None = None,
        repository_factory: InventoryRepositoryFactory | None = None,
    ) -> None:
        # `Settings()` bypasses `override_settings`; route through
        # `load_settings()` so tests and CLI calls see the active scoped
        # storage runtime.
        from ...core.config import load_settings as _load_settings

        self._settings = settings or _load_settings()
        self._event_repository = bucket_event_repository or BucketEventHistoryRepository()
        self._repository_factory = repository_factory or _runtime_repository_factory(self._settings)

    def _repository_for(self, bucket_id: str) -> InventoryLedgerRepository:
        return self._repository_factory(bucket_id)

    def create(
        self,
        *,
        bucket_id: str,
        actividad_id: str,
        year: int,
        valuation_method: str,
        opening_stock: Decimal = Decimal("0"),
        actor: str = "cli",
    ) -> InventoryLedgerResult:
        """Create a fresh ledger for one actividad/year. Rejects duplicates.

        Saves the containing :class:`InventoryLedgerDocument`, emits a
        ``LEDGER_INVENTORY_CREATED`` bucket event, and returns an
        :class:`InventoryLedgerResult`.
        """
        try:
            method = parse_valuation_method(valuation_method)
        except InventoryLedgerError as exc:
            raise InventoryServiceInputError(
                translated_message="application.inventory.service.errors.invalid_valuation_method",
                context={"valuation_method": valuation_method},
            ) from exc
        repository = self._repository_for(bucket_id)
        ledger = InventoryLedger(
            actividad_id=actividad_id,
            year=year,
            valuation_method=method,
            opening_stock=opening_stock,
            closing_authority_record=None,
        )
        # Delegated to the repository's guarded verb rather than repeating its
        # read, duplicate-check and write here. The document is a singleton row,
        # so creating one ledger rewrites all of them: performed unguarded, a
        # ledger created for a DIFFERENT activity in the interim is discarded,
        # and the duplicate check cannot notice because the two never met. The
        # verb runs that check inside the guarded unit of work, so it is
        # re-judged against the document each attempt actually writes to.
        #
        # The refusal is re-raised in this layer's own words: the adapter names
        # a storage-level conflict, and the operator asked to create an
        # actividad.
        try:
            repository.create(ledger)
        except InventoryLedgerError as exc:
            raise InventoryActividadConflictError(
                translated_message="application.inventory.service.errors.actividad_conflict",
                context={"actividad_id": actividad_id, "year": str(year)},
            ) from exc
        now = _now_utc()
        event_id = _emit_inventory_event(
            event_repository=self._event_repository,
            bucket_id=bucket_id,
            event_type=BucketEventType.LEDGER_INVENTORY_CREATED,
            actividad_id=actividad_id,
            year=year,
            actor=actor,
            occurred_at=now,
            payload={"valuation_method": method.value},
        )
        return InventoryLedgerResult(ledger=ledger, bucket_event_ids=(event_id,))

    def list_all(self, *, bucket_id: str) -> tuple[InventoryActividadSummary, ...]:
        """Return one :class:`InventoryActividadSummary` per stored ledger.

        This is a read-only projection over the bucket's
        :class:`InventoryLedgerDocument`; it emits no bucket event.
        """
        document = self._repository_for(bucket_id).load()
        return tuple(
            InventoryActividadSummary(
                actividad_id=ledger.actividad_id,
                year=ledger.year,
                valuation_method=ledger.valuation_method,
                opening_stock=ledger.opening_stock,
                movement_count=len(ledger.period_movements),
            )
            for ledger in document.ledgers
        )

    def show(self, *, bucket_id: str, actividad_id: str, year: int) -> InventoryLedger:
        """Return the exact :class:`InventoryLedger` for ``actividad_id`` and ``year``.

        Raises :class:`InventoryActividadNotFoundError` when the bucket's
        inventory document has no matching actividad/year ledger.
        """
        document = self._repository_for(bucket_id).load()
        ledger = _find_ledger(document, actividad_id, year)
        if ledger is None:
            raise InventoryActividadNotFoundError(
                translated_message="application.inventory.service.errors.actividad_not_found",
                context={"actividad_id": actividad_id, "year": str(year)},
            )
        return ledger

    def movement_add(
        self,
        *,
        bucket_id: str,
        actividad_id: str,
        year: int,
        movement: InventoryMovementCommand,
        actor: str = "cli",
    ) -> InventoryLedgerResult:
        """Append a movement to the named ledger; refuses duplicate movement_id.

        The :class:`InventoryMovementCommand` is converted to a
        :class:`MovementRecord`, then the domain valuation guard runs
        before persistence. Returns an :class:`InventoryLedgerResult`
        with the updated ledger after the movement is appended.
        """
        ledger = self.show(bucket_id=bucket_id, actividad_id=actividad_id, year=year)
        if any(m.movement_id == movement.movement_id for m in ledger.period_movements):
            raise InventoryServiceInputError(
                translated_message="application.inventory.service.errors.duplicate_movement_id",
                context={"movement_id": movement.movement_id},
            )
        if movement.acquisition_cost is not None:
            record = MovementRecord.from_purchase_acquisition(
                movement_id=movement.movement_id,
                movement_date=movement.movement_date,
                quantity=movement.quantity,
                acquisition_cost=movement.acquisition_cost,
            )
        else:
            record = MovementRecord(
                movement_id=movement.movement_id,
                movement_date=movement.movement_date,
                kind=movement.kind,
                quantity=movement.quantity,
                unit_cost=movement.unit_cost,
                taxable_base=movement.taxable_base,
            )
        updated = ledger.model_copy(
            update={"period_movements": (*ledger.period_movements, record)},
        )
        # Domain valuation guard runs in the application layer, before persistence:
        # a movement that would produce an invalid valuation (e.g. consuming more
        # stock than available) raises before any write. Keeping the guard here
        # rather than in the persistence adapter keeps the adapter calculation-free.
        compute_inventory_valuation(updated)
        repository = self._repository_for(bucket_id)
        document = repository.load()
        document = _replace_ledger(document, updated)
        repository.save(document)
        now = _now_utc()
        event_id = _emit_inventory_event(
            event_repository=self._event_repository,
            bucket_id=bucket_id,
            event_type=BucketEventType.LEDGER_INVENTORY_MOVEMENT_ADDED,
            actividad_id=actividad_id,
            year=year,
            actor=actor,
            occurred_at=now,
            payload={"movement_id": movement.movement_id, "kind": movement.kind.value},
        )
        return InventoryLedgerResult(ledger=updated, bucket_event_ids=(event_id,))

    def valuation_preview(
        self,
        *,
        bucket_id: str,
        actividad_id: str,
        year: int,
        actor: str = "cli",
    ) -> InventoryValuationPreviewResult:
        """Run the domain-layer valuation engine and report closing stock + COGS.

        Returns:
            :class:`InventoryValuationPreviewResult`: The valuation preview result.
        """
        ledger = self.show(bucket_id=bucket_id, actividad_id=actividad_id, year=year)
        result: InventoryValuationResult = compute_inventory_valuation(ledger)
        preview = InventoryValuationPreview(
            actividad_id=ledger.actividad_id,
            year=ledger.year,
            valuation_method=ledger.valuation_method,
            derived_closing_value=result.closing_value,
            cogs=result.cogs_value,
        )
        now = _now_utc()
        event_id = _emit_inventory_event(
            event_repository=self._event_repository,
            bucket_id=bucket_id,
            event_type=BucketEventType.LEDGER_INVENTORY_VALUATION_PREVIEWED,
            actividad_id=actividad_id,
            year=year,
            actor=actor,
            occurred_at=now,
            payload={"valuation_method": ledger.valuation_method.value},
        )
        return InventoryValuationPreviewResult(preview=preview, bucket_event_ids=(event_id,))

    def closing_authority_record(
        self,
        *,
        bucket_id: str,
        actividad_id: str,
        year: int,
        authority_record: InventoryClosingAuthorityRecord,
    ) -> InventoryLedgerResult:
        """Atomically validate and persist one complete closing-authority bundle."""
        repository = self._repository_for(bucket_id)
        try:
            ledger = repository.record_closing_authority(
                actividad_id,
                authority_record,
                year=year,
            )
        except InventoryClosingAuthorityConflictError as exc:
            raise InventoryServiceInputError(
                translated_message="application.inventory.service.errors.closing_authority_conflict",
                context={"actividad_id": actividad_id, "year": str(year)},
            ) from exc
        except InventoryLedgerError as exc:
            raise InventoryActividadNotFoundError(
                translated_message="application.inventory.service.errors.actividad_not_found",
                context={"actividad_id": actividad_id, "year": str(year)},
            ) from exc
        # No event is emitted here: inventory and bucket events have distinct
        # repositories with no shared transaction. The encrypted ledger write is
        # atomic and replay-safe; claiming a cross-repository commit would not be.
        return InventoryLedgerResult(ledger=ledger)

    def remove(
        self,
        *,
        bucket_id: str,
        actividad_id: str,
        year: int,
        actor: str = "cli",
    ) -> InventoryLedgerResult:
        """Drop the entire ledger for actividad/year.

        Raises :class:`InventoryActividadNotFoundError` on absence.
        Otherwise saves the remaining :class:`InventoryLedgerDocument`,
        emits ``LEDGER_INVENTORY_REMOVED``, and returns the removed
        :class:`InventoryLedger` in an :class:`InventoryLedgerResult`.
        """
        repository = self._repository_for(bucket_id)
        # Delegated to the guarded verb rather than repeating its read, absence
        # check and write here. Removing ONE ledger rewrites the whole singleton
        # document, so an unguarded removal discards a ledger created for a
        # different activity in the interim -- losing that activity's entire
        # inventory for an operator who was deleting something else.
        #
        # The absence check travels into the guard with it, so a retry re-judges
        # it: a ledger a concurrent caller already removed must refuse as absent
        # rather than report a second successful removal.
        try:
            ledger = repository.remove(actividad_id, year=year)
        except InventoryLedgerError as exc:
            raise InventoryActividadNotFoundError(
                translated_message="application.inventory.service.errors.actividad_not_found",
                context={"actividad_id": actividad_id, "year": str(year)},
            ) from exc
        now = _now_utc()
        event_id = _emit_inventory_event(
            event_repository=self._event_repository,
            bucket_id=bucket_id,
            event_type=BucketEventType.LEDGER_INVENTORY_REMOVED,
            actividad_id=actividad_id,
            year=year,
            actor=actor,
            occurred_at=now,
            payload={"actividad_id": actividad_id, "year": str(year)},
        )
        return InventoryLedgerResult(ledger=ledger, bucket_event_ids=(event_id,))


__all__ = [
    "InventoryActividadSummary",
    "InventoryLedgerResult",
    "InventoryMovementCommand",
    "InventoryService",
    "InventoryValuationPreview",
    "InventoryValuationPreviewResult",
    "inventory_ledger_repository_for_bucket",
]
