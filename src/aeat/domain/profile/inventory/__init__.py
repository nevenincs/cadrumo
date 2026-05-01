"""Inventory ledgers for actividad economica stock valuation."""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ...formulas import ValuationMethod
from ..errors import InventoryLedgerError, LIFOForbiddenError

SCHEMA_VERSION = "1"
_CENT = Decimal("0.01")
_ZERO = Decimal("0.00")
_ONE = Decimal("1")
_HUNDRED = Decimal("100")


class MovementKind(StrEnum):
    """Supported inventory movement kinds."""

    OPENING = "opening"
    PURCHASE = "purchase"
    COGS = "cogs"
    COUNT = "count"


class MovementRecord(BaseModel):
    """One inventory movement for an activity/year."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    movement_id: str = Field(min_length=1)
    movement_date: date
    kind: MovementKind = MovementKind.PURCHASE
    sku: str = Field(default="default", min_length=1)
    quantity: Decimal = Field(gt=Decimal("0"))
    unit_cost: Decimal | None = Field(default=None, ge=Decimal("0"))
    taxable_base: Decimal | None = Field(default=None, ge=Decimal("0"))
    vat_rate: Decimal = Field(default=Decimal("21.00"), ge=Decimal("0"), le=Decimal("100"))
    vat_amount: Decimal | None = Field(default=None, ge=Decimal("0"))
    deductible_vat_ratio: Decimal = Field(default=Decimal("1.00"), ge=Decimal("0"), le=Decimal("1"))
    schema_version: str = SCHEMA_VERSION

    @property
    def value(self) -> Decimal:
        """Return the VAT-exclusive movement value."""

        if self.taxable_base is not None:
            return self.taxable_base
        if self.unit_cost is None:
            return _ZERO
        return self.quantity * self.unit_cost

    @property
    def resolved_unit_cost(self) -> Decimal:
        """Return the VAT-exclusive unit cost."""

        if self.unit_cost is not None:
            return self.unit_cost
        if self.taxable_base is None:
            return _ZERO
        return self.taxable_base / self.quantity

    @field_validator("schema_version")
    @classmethod
    def _schema_version_supported(cls, value: str) -> str:
        if value != SCHEMA_VERSION:
            raise ValueError(f"unsupported MovementRecord schema_version {value!r}")
        return value

    @model_validator(mode="after")
    def _validate_movement_amounts(self) -> MovementRecord:
        needs_cost = self.kind in {MovementKind.OPENING, MovementKind.PURCHASE}
        if needs_cost and self.unit_cost is None and self.taxable_base is None:
            raise ValueError("opening and purchase movements require unit_cost or taxable_base")
        if self.taxable_base is not None:
            computed_vat = _quantize(self.taxable_base * self.vat_rate / _HUNDRED)
            if self.vat_amount is not None and self.vat_amount != computed_vat:
                raise ValueError("vat_amount must equal taxable_base * vat_rate")
        return self


class StockLayer(BaseModel):
    """Remaining inventory quantity at one VAT-exclusive unit cost."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    sku: str = Field(default="default", min_length=1)
    quantity: Decimal = Field(gt=Decimal("0"))
    unit_cost: Decimal = Field(ge=Decimal("0"))
    source_movement_id: str = Field(min_length=1)


class InventoryLedger(BaseModel):
    """Per-activity inventory ledger for one tax year."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    actividad_id: str = Field(min_length=1)
    year: int = Field(ge=1900)
    valuation_method: ValuationMethod
    opening_stock: Decimal = Field(ge=Decimal("0"))
    opening_layers: tuple[StockLayer, ...] = ()
    closing_stock: Decimal | None = Field(default=None, ge=Decimal("0"))
    period_movements: tuple[MovementRecord, ...] = ()
    schema_version: str = SCHEMA_VERSION

    @field_validator("schema_version")
    @classmethod
    def _schema_version_supported(cls, value: str) -> str:
        if value != SCHEMA_VERSION:
            raise ValueError(f"unsupported InventoryLedger schema_version {value!r}")
        return value

    @model_validator(mode="after")
    def _opening_stock_matches_layers(self) -> InventoryLedger:
        if self.opening_layers and _quantize(_layers_value(self.opening_layers)) != _quantize(self.opening_stock):
            raise ValueError("opening_stock must equal the value of opening_layers")
        return self


class InventoryLedgerDocument(BaseModel):
    """JSON document containing inventory ledgers."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    schema_version: str = SCHEMA_VERSION
    ledgers: tuple[InventoryLedger, ...] = ()

    @field_validator("schema_version")
    @classmethod
    def _schema_version_supported(cls, value: str) -> str:
        if value != SCHEMA_VERSION:
            raise ValueError(f"unsupported InventoryLedgerDocument schema_version {value!r}")
        return value


def parse_valuation_method(raw: str) -> ValuationMethod:
    """Parse a user-supplied valuation method and refuse LIFO explicitly."""

    normalized = raw.strip().lower().replace("-", "_")
    if normalized == "lifo":
        raise LIFOForbiddenError(raw)
    try:
        return ValuationMethod(normalized)
    except ValueError as exc:
        raise InventoryLedgerError(
            f"unknown valuation method {raw!r}; use fifo, pmp, or coste_medio",
            context={"method": raw},
        ) from exc


def compute_inventory_variation(ledger: InventoryLedger, year: int) -> Decimal:
    """Compute signed Anexo D inventory variation for a ledger.

    Returns closing stock minus opening stock for `0155`. If closing stock is
    not supplied, it is derived from opening stock plus signed movement values.
    Method-specific layer valuation is intentionally left to the continuation
    persistence and UX audit because this v1 model does not store opening
    quantities or stock layers.
    """

    if ledger.year != year:
        return _ZERO
    closing = ledger.closing_stock
    if closing is None:
        closing = compute_inventory_valuation(ledger).closing_value
    return _quantize(closing - ledger.opening_stock)


class InventoryValuationResult(BaseModel):
    """Computed valuation outcome for an inventory ledger."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    closing_layers: tuple[StockLayer, ...]
    closing_value: Decimal
    cogs_value: Decimal
    purchase_value: Decimal


def compute_anexo_d_inventory_variation(
    year: int,
    actividad: str,
    *,
    ledgers: tuple[InventoryLedger, ...] = (),
) -> Decimal:
    """Compute Anexo D normal casilla `0155` for one activity."""

    total = _ZERO
    for ledger in ledgers:
        if ledger.actividad_id == actividad:
            total += compute_inventory_variation(ledger, year)
    return _quantize(total)


def compute_inventory_valuation(ledger: InventoryLedger) -> InventoryValuationResult:
    """Value closing stock and COGS using the ledger's valuation method."""

    if ledger.valuation_method is ValuationMethod.FIFO:
        return _compute_fifo(ledger)
    if ledger.valuation_method in {ValuationMethod.PMP, ValuationMethod.COSTE_MEDIO}:
        return _compute_weighted_average(ledger)
    raise InventoryLedgerError(f"unsupported valuation method {ledger.valuation_method.value}")


def _compute_fifo(ledger: InventoryLedger) -> InventoryValuationResult:
    layers = list(_opening_layers(ledger))
    cogs_value = _ZERO
    purchase_value = _ZERO
    for movement in _sorted_movements(ledger):
        if movement.kind in {MovementKind.OPENING, MovementKind.PURCHASE}:
            unit_cost = movement.resolved_unit_cost
            layers.append(
                StockLayer(
                    sku=movement.sku,
                    quantity=movement.quantity,
                    unit_cost=unit_cost,
                    source_movement_id=movement.movement_id,
                )
            )
            if movement.kind is MovementKind.PURCHASE:
                purchase_value += movement.quantity * unit_cost
            continue
        if movement.kind is MovementKind.COGS:
            consumed, layers = _consume_fifo(layers, movement)
            cogs_value += consumed
            continue
        if movement.kind is MovementKind.COUNT:
            layers = _apply_count(layers, movement)
    closing = _layers_value(layers)
    return InventoryValuationResult(
        closing_layers=tuple(layers),
        closing_value=_quantize(closing),
        cogs_value=_quantize(cogs_value),
        purchase_value=_quantize(purchase_value),
    )


def _compute_weighted_average(ledger: InventoryLedger) -> InventoryValuationResult:
    pools: dict[str, tuple[Decimal, Decimal]] = {}
    for layer in _opening_layers(ledger):
        quantity, value = pools.get(layer.sku, (_ZERO, _ZERO))
        pools[layer.sku] = (quantity + layer.quantity, value + layer.quantity * layer.unit_cost)
    cogs_value = _ZERO
    purchase_value = _ZERO
    for movement in _sorted_movements(ledger):
        quantity, value = pools.get(movement.sku, (_ZERO, _ZERO))
        if movement.kind in {MovementKind.OPENING, MovementKind.PURCHASE}:
            unit_cost = movement.resolved_unit_cost
            movement_value = movement.quantity * unit_cost
            quantity += movement.quantity
            value += movement_value
            pools[movement.sku] = (quantity, value)
            if movement.kind is MovementKind.PURCHASE:
                purchase_value += movement_value
            continue
        if movement.kind is MovementKind.COGS:
            if movement.quantity > quantity:
                raise InventoryLedgerError(
                    "inventory movement would consume more stock than available",
                    context={
                        "actividad_id": ledger.actividad_id,
                        "movement_id": movement.movement_id,
                        "available_quantity": str(quantity),
                        "requested_quantity": str(movement.quantity),
                    },
                )
            average = _ZERO if quantity == _ZERO else value / quantity
            consumed = movement.quantity * average
            quantity -= movement.quantity
            value -= consumed
            pools[movement.sku] = (quantity, value)
            cogs_value += consumed
            continue
        if movement.kind is MovementKind.COUNT:
            average = _ZERO if quantity == _ZERO else value / quantity
            quantity = movement.quantity
            value = quantity * average
            pools[movement.sku] = (quantity, value)
    layers = tuple(
        StockLayer(
            sku=sku,
            quantity=quantity,
            unit_cost=_quantize(_ZERO if quantity == _ZERO else value / quantity),
            source_movement_id=f"{ledger.actividad_id}-{ledger.year}-{sku}-weighted-average",
        )
        for sku, (quantity, value) in sorted(pools.items())
        if quantity > _ZERO
    )
    return InventoryValuationResult(
        closing_layers=layers,
        closing_value=_quantize(sum((quantity_value[1] for quantity_value in pools.values()), _ZERO)),
        cogs_value=_quantize(cogs_value),
        purchase_value=_quantize(purchase_value),
    )


def _consume_fifo(layers: list[StockLayer], movement: MovementRecord) -> tuple[Decimal, list[StockLayer]]:
    remaining = movement.quantity
    consumed = _ZERO
    updated: list[StockLayer] = []
    for layer in layers:
        if layer.sku != movement.sku or remaining <= _ZERO:
            updated.append(layer)
            continue
        take = min(layer.quantity, remaining)
        consumed += take * layer.unit_cost
        remaining -= take
        leftover = layer.quantity - take
        if leftover > _ZERO:
            updated.append(layer.model_copy(update={"quantity": leftover}))
    if remaining > _ZERO:
        raise InventoryLedgerError(
            "inventory movement would consume more stock than available",
            context={
                "movement_id": movement.movement_id,
                "sku": movement.sku,
                "missing_quantity": str(remaining),
            },
        )
    return consumed, updated


def _apply_count(layers: list[StockLayer], movement: MovementRecord) -> list[StockLayer]:
    current_quantity = sum((layer.quantity for layer in layers if layer.sku == movement.sku), _ZERO)
    if movement.quantity > current_quantity:
        raise InventoryLedgerError(
            "inventory count cannot increase stock without a purchase movement",
            context={
                "movement_id": movement.movement_id,
                "sku": movement.sku,
                "available_quantity": str(current_quantity),
                "counted_quantity": str(movement.quantity),
            },
        )
    to_remove = current_quantity - movement.quantity
    synthetic_cogs = movement.model_copy(update={"kind": MovementKind.COGS, "quantity": to_remove})
    _, updated = _consume_fifo(layers, synthetic_cogs)
    return updated


def _opening_layers(ledger: InventoryLedger) -> tuple[StockLayer, ...]:
    if ledger.opening_layers:
        return ledger.opening_layers
    if ledger.opening_stock == _ZERO:
        return ()
    return (
        StockLayer(
            sku="default",
            quantity=Decimal("1"),
            unit_cost=ledger.opening_stock,
            source_movement_id=f"{ledger.actividad_id}-{ledger.year}-opening",
        ),
    )


def _sorted_movements(ledger: InventoryLedger) -> tuple[MovementRecord, ...]:
    return tuple(sorted(ledger.period_movements, key=lambda item: (item.movement_date, item.movement_id)))


def _layers_value(layers: tuple[StockLayer, ...] | list[StockLayer]) -> Decimal:
    return sum((layer.quantity * layer.unit_cost for layer in layers), _ZERO)


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(_CENT, rounding=ROUND_HALF_UP)


__all__ = [
    "InventoryLedger",
    "MovementKind",
    "MovementRecord",
    "StockLayer",
    "compute_anexo_d_inventory_variation",
    "compute_inventory_valuation",
    "compute_inventory_variation",
    "parse_valuation_method",
]
