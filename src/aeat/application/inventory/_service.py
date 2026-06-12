"""Inventory application service: bucket-scoped CRUD over InventoryLedger.

Every mutating verb (add, update, remove) appends an event to the
per-bucket audit trail via :class:`BucketEventHistoryRepository`.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from ...adapters.persistence.profile.inventory import InventoryLedgerRepository
from ...adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
from ...core.config import Settings
from ...core.external_constants import DEFAULT_IVA_GENERAL_RATE_PCT
from ...core.time import now as _now_utc
from ...domain.buckets import (
    BucketEventHistoryRepository,
    BucketEventObjectType,
    BucketEventType,
    append_bucket_event,
)
from ...domain.buckets._protocols import BucketEventHistoryRepositoryProtocol
from ...domain.contribuyente.inventory import (
    InventoryLedger,
    InventoryLedgerDocument,
    InventoryLedgerError,
    InventoryValuationResult,
    MovementKind,
    MovementRecord,
    ValuationMethod,
    compute_inventory_valuation,
    parse_valuation_method,
)
from ._errors import (
    InventoryActividadConflictError,
    InventoryActividadNotFoundError,
    InventoryServiceInputError,
)


class InventoryActividadSummary(BaseModel):
    """One row in ``inventory list``: actividad + year + movement count."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    actividad_id: str = Field(min_length=1)
    year: int = Field(ge=1900)
    valuation_method: ValuationMethod
    opening_stock: Decimal = Field(ge=Decimal("0"))
    movement_count: int = Field(ge=0)


class InventoryMovementCommand(BaseModel):
    """Strict input shape for ``inventory movement add``."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    movement_id: str = Field(min_length=1, max_length=64)
    movement_date: date
    kind: MovementKind
    quantity: Decimal
    unit_cost: Decimal | None = Field(default=None)
    taxable_base: Decimal | None = Field(default=None)
    iva_rate: Decimal = DEFAULT_IVA_GENERAL_RATE_PCT


class InventoryValuationPreview(BaseModel):
    """Outcome of a ``valuation preview`` invocation."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    actividad_id: str = Field(min_length=1)
    year: int = Field(ge=1900)
    valuation_method: ValuationMethod
    closing_stock: Decimal = Field(ge=Decimal("0"))
    cogs: Decimal = Field(ge=Decimal("0"))


class InventoryLedgerResult(BaseModel):
    """Return record from a mutating inventory verb — ledger plus emitted event id."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    ledger: InventoryLedger
    bucket_event_ids: tuple[str, ...] = ()


class InventoryValuationPreviewResult(BaseModel):
    """Return record from valuation_preview — preview plus emitted event id."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

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
    from ...domain.buckets._event import BucketEvent, derive_bucket_event_id

    object_id = f"{actividad_id}:{year}"
    event = BucketEvent(
        event_id=derive_bucket_event_id(
            bucket_id=bucket_id,
            event_type=event_type,
            occurred_at=occurred_at,
            actor=actor,
            object_type=BucketEventObjectType.LEDGER_CATALOGUE,
            object_id=object_id,
            payload=payload,
        ),
        bucket_id=bucket_id,
        event_type=event_type,
        occurred_at=occurred_at,
        actor=actor,
        object_type=BucketEventObjectType.LEDGER_CATALOGUE,
        object_id=object_id,
        payload_version=_INVENTORY_EVENT_PAYLOAD_VERSION,
        payload=payload,
    )
    event_repository.save(append_bucket_event(event_repository.load(), event))
    return event.event_id


def _runtime_repository_factory(settings: Settings) -> InventoryRepositoryFactory:
    def _factory(bucket_id: str) -> InventoryLedgerRepository:
        return InventoryLedgerRepository(
            objects=secure_object_repository_for_bucket(bucket_id, settings),
        )

    return _factory


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
    """Bucket-scoped CRUD over per-actividad inventory ledgers."""

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

        Returns an :class:`InventoryLedgerResult`.
        """
        try:
            method = parse_valuation_method(valuation_method)
        except InventoryLedgerError as exc:
            raise InventoryServiceInputError(
                f"invalid valuation_method {valuation_method!r}",
                translated_message="application.inventory.service.errors.invalid_valuation_method",
                context={"valuation_method": valuation_method},
                suggestion="aeat app ledger inventory create --valuation-method fifo|pmp",
            ) from exc
        repository = self._repository_for(bucket_id)
        document = repository.load()
        if _find_ledger(document, actividad_id, year) is not None:
            raise InventoryActividadConflictError(
                f"inventory ledger already exists for actividad={actividad_id!r} year={year}",
                translated_message="application.inventory.service.errors.actividad_conflict",
                context={"actividad_id": actividad_id, "year": str(year)},
                suggestion="aeat app ledger inventory list",
            )
        ledger = InventoryLedger(
            actividad_id=actividad_id,
            year=year,
            valuation_method=method,
            opening_stock=opening_stock,
        )
        document = InventoryLedgerDocument(ledgers=(*document.ledgers, ledger))
        repository.save(document)
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
        document = self._repository_for(bucket_id).load()
        ledger = _find_ledger(document, actividad_id, year)
        if ledger is None:
            raise InventoryActividadNotFoundError(
                f"no inventory ledger for actividad={actividad_id!r} year={year}",
                translated_message="application.inventory.service.errors.actividad_not_found",
                context={"actividad_id": actividad_id, "year": str(year)},
                suggestion="aeat app ledger inventory list",
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

        Returns an :class:`InventoryLedgerResult` with the updated ledger
        after the movement is appended.
        """
        ledger = self.show(bucket_id=bucket_id, actividad_id=actividad_id, year=year)
        if any(m.movement_id == movement.movement_id for m in ledger.period_movements):
            raise InventoryServiceInputError(
                f"movement_id {movement.movement_id!r} already present in ledger",
                translated_message="application.inventory.service.errors.duplicate_movement_id",
                context={"movement_id": movement.movement_id},
                suggestion="aeat app ledger inventory list",
            )
        record = MovementRecord(
            movement_id=movement.movement_id,
            movement_date=movement.movement_date,
            kind=movement.kind,
            quantity=movement.quantity,
            unit_cost=movement.unit_cost,
            taxable_base=movement.taxable_base,
            iva_rate=movement.iva_rate,
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
            closing_stock=result.closing_value,
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

    def remove(
        self,
        *,
        bucket_id: str,
        actividad_id: str,
        year: int,
        actor: str = "cli",
    ) -> InventoryLedgerResult:
        """Drop the entire ledger for actividad/year.

        Returns an :class:`InventoryLedgerResult`. Idempotent on absence.
        """
        repository = self._repository_for(bucket_id)
        document = repository.load()
        ledger = _find_ledger(document, actividad_id, year)
        if ledger is None:
            raise InventoryActividadNotFoundError(
                f"no inventory ledger for actividad={actividad_id!r} year={year}",
                translated_message="application.inventory.service.errors.actividad_not_found",
                context={"actividad_id": actividad_id, "year": str(year)},
                suggestion="aeat app ledger inventory list",
            )
        document = InventoryLedgerDocument(
            ledgers=tuple(
                existing
                for existing in document.ledgers
                if not (existing.actividad_id == actividad_id and existing.year == year)
            ),
        )
        repository.save(document)
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
]
