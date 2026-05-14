"""Inventory application service: bucket-scoped CRUD over InventoryLedger."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from ...core.config import Settings
from ...domain.profile.inventory import (
    InventoryLedger,
    InventoryLedgerDocument,
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
    vat_rate: Decimal = Decimal("21.00")


class InventoryValuationPreview(BaseModel):
    """Outcome of a ``valuation preview`` invocation."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    actividad_id: str = Field(min_length=1)
    year: int = Field(ge=1900)
    valuation_method: ValuationMethod
    closing_stock: Decimal = Field(ge=Decimal("0"))
    cogs: Decimal = Field(ge=Decimal("0"))


def _storage_path(settings: Settings, bucket_id: str) -> Path:
    root = settings.aeat_ledgers_dir / "inventory"
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{bucket_id}.json"


def _load_document(settings: Settings, bucket_id: str) -> InventoryLedgerDocument:
    path = _storage_path(settings, bucket_id)
    if not path.exists():
        return InventoryLedgerDocument(ledgers=())
    return InventoryLedgerDocument.model_validate_json(path.read_text(encoding="utf-8"))


def _save_document(settings: Settings, bucket_id: str, document: InventoryLedgerDocument) -> None:
    path = _storage_path(settings, bucket_id)
    path.write_text(document.model_dump_json(indent=2), encoding="utf-8")


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
    return InventoryLedgerDocument(ledgers=others + (ledger,))


class InventoryService:
    """Bucket-scoped CRUD over per-actividad inventory ledgers."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or Settings()

    def create(
        self,
        *,
        bucket_id: str,
        actividad_id: str,
        year: int,
        valuation_method: str,
        opening_stock: Decimal = Decimal("0"),
    ) -> InventoryLedger:
        """Create a fresh ledger for one actividad/year. Rejects duplicates."""
        try:
            method = parse_valuation_method(valuation_method)
        except Exception as exc:
            raise InventoryServiceInputError(
                f"invalid valuation_method {valuation_method!r}: {exc}",
                suggestion="aeat app ledger inventory create --valuation-method fifo|pmp",
            ) from exc
        document = _load_document(self._settings, bucket_id)
        if _find_ledger(document, actividad_id, year) is not None:
            raise InventoryActividadConflictError(
                f"inventory ledger already exists for actividad={actividad_id!r} year={year}",
                suggestion="aeat app ledger inventory show",
            )
        ledger = InventoryLedger(
            actividad_id=actividad_id,
            year=year,
            valuation_method=method,
            opening_stock=opening_stock,
        )
        document = InventoryLedgerDocument(ledgers=(*document.ledgers, ledger))
        _save_document(self._settings, bucket_id, document)
        return ledger

    def list_all(self, *, bucket_id: str) -> tuple[InventoryActividadSummary, ...]:
        document = _load_document(self._settings, bucket_id)
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
        document = _load_document(self._settings, bucket_id)
        ledger = _find_ledger(document, actividad_id, year)
        if ledger is None:
            raise InventoryActividadNotFoundError(
                f"no inventory ledger for actividad={actividad_id!r} year={year}",
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
    ) -> InventoryLedger:
        """Append a movement to the named ledger; refuses duplicate movement_id."""
        ledger = self.show(bucket_id=bucket_id, actividad_id=actividad_id, year=year)
        if any(m.movement_id == movement.movement_id for m in ledger.period_movements):
            raise InventoryServiceInputError(
                f"movement_id {movement.movement_id!r} already present in ledger",
                suggestion="aeat app ledger inventory show",
            )
        record = MovementRecord(
            movement_id=movement.movement_id,
            movement_date=movement.movement_date,
            kind=movement.kind,
            quantity=movement.quantity,
            unit_cost=movement.unit_cost,
            taxable_base=movement.taxable_base,
            vat_rate=movement.vat_rate,
        )
        updated = ledger.model_copy(
            update={"period_movements": ledger.period_movements + (record,)},
        )
        document = _load_document(self._settings, bucket_id)
        document = _replace_ledger(document, updated)
        _save_document(self._settings, bucket_id, document)
        return updated

    def valuation_preview(
        self,
        *,
        bucket_id: str,
        actividad_id: str,
        year: int,
    ) -> InventoryValuationPreview:
        """Run the domain-layer valuation engine and report closing stock + COGS."""
        ledger = self.show(bucket_id=bucket_id, actividad_id=actividad_id, year=year)
        result: InventoryValuationResult = compute_inventory_valuation(ledger)
        return InventoryValuationPreview(
            actividad_id=ledger.actividad_id,
            year=ledger.year,
            valuation_method=ledger.valuation_method,
            closing_stock=result.closing_value,
            cogs=result.cogs_value,
        )

    def remove(self, *, bucket_id: str, actividad_id: str, year: int) -> InventoryLedger:
        """Drop the entire ledger for actividad/year. Idempotent on absence."""
        document = _load_document(self._settings, bucket_id)
        ledger = _find_ledger(document, actividad_id, year)
        if ledger is None:
            raise InventoryActividadNotFoundError(
                f"no inventory ledger for actividad={actividad_id!r} year={year}",
                suggestion="aeat app ledger inventory list",
            )
        document = InventoryLedgerDocument(
            ledgers=tuple(
                existing
                for existing in document.ledgers
                if not (existing.actividad_id == actividad_id and existing.year == year)
            ),
        )
        _save_document(self._settings, bucket_id, document)
        return ledger


__all__ = [
    "InventoryActividadSummary",
    "InventoryMovementCommand",
    "InventoryService",
    "InventoryValuationPreview",
]
