"""Inventory ledgers for actividad economica stock valuation.

Defines strict pydantic v2 records for tracking opening stock,
period movements (purchases, COGS, counts), and closing stock per
activity / year, plus the FIFO and weighted-average (PMP / coste
medio) valuation engines required by LIS art. 17.1. LIFO is rejected
explicitly via :class:`LIFOForbiddenError`.

Public functions:
    :func:`parse_valuation_method` — coerce user input into a
    :class:`ValuationMethod`, refusing LIFO.
    :func:`compute_inventory_valuation` — value closing stock and
    COGS for one ledger.
    :func:`compute_inventory_variation` — signed Anexo D ``0155``
    closing-minus-opening stock variation.
    :func:`compute_anexo_d_inventory_variation` — per-activity
    aggregation across multiple ledgers.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ....core.errors import AeatError as _AeatError
from ....core.errors import CoreValidationError as _CoreValidationError
from ....core.external_constants import DEFAULT_IVA_GENERAL_RATE_PCT
from ....core.money import round_to_cents as _quantize


class AmortizacionLedgerError(_AeatError):
    """Raised when an amortizacion ledger operation is invalid."""


class InventoryLedgerError(_AeatError):
    """Raised when an inventory ledger operation is invalid."""


class InventoryValidationError(InventoryLedgerError, _CoreValidationError):
    """Raised when an inventory ledger fails Pydantic validation.

    Inherits from CoreValidationError (which itself inherits from CoreError
    and ValueError) to participate in the shared CoreValidationError catch
    surface and remain compatible with pydantic validators.
    """


class LIFOForbiddenError(InventoryLedgerError):
    """Raised when a caller attempts LIFO inventory valuation.

    LIS art. 17.1 does not admit LIFO for tax-purpose stock valuation
    in this regime; the message routes the operator to FIFO, PMP, or
    coste medio.
    """

    def __init__(self, method: str = "lifo") -> None:
        """Construct a refusal citing the LIS art. 17 valuation boundary.

        Args:
            method: User-supplied valuation method.
        """
        super().__init__(
            "LIFO valuation is not admitted for this tax ledger; use FIFO, PMP, or coste_medio per LIS art. 17.1.",
            context={"method": method, "legal_basis": "LIS art. 17.1"},
        )


class BasisCapExceededError(AmortizacionLedgerError):
    """Raised when cumulative amortization would exceed cost basis."""


INVENTORY_SCHEMA_VERSION = "1"
"""Forward-compatible schema version stamped onto every record in this module."""

_ZERO = Decimal("0.00")
_ONE = Decimal("1")
_HUNDRED = Decimal("100")


class MovementKind(StrEnum):
    """Supported inventory movement kinds.

    Attributes:
        OPENING: Stock present at the start of the period.
        PURCHASE: Inbound inventory acquisition.
        COGS: Cost-of-goods-sold consumption.
        COUNT: Adjustment to the physical count, modelled as a
            synthetic COGS movement against the discrepancy.
    """

    OPENING = "opening"
    PURCHASE = "purchase"
    COGS = "cogs"
    COUNT = "count"


class ValuationMethod(StrEnum):
    """Supported inventory valuation methods."""

    FIFO = "fifo"
    PMP = "pmp"
    COSTE_MEDIO = "coste_medio"


class MovementRecord(BaseModel):
    """One inventory movement for an activity/year.

    Attributes:
        movement_id: Stable natural key for the movement.
        movement_date: Date the movement applies on.
        kind: :class:`MovementKind`.
        sku: SKU / item identifier; defaults to ``"default"`` for
            single-SKU ledgers.
        quantity: Movement quantity (strictly positive).
        unit_cost: IVA-exclusive per-unit cost.
        taxable_base: Invoice taxable base (IVA-exclusive).
        iva_rate: IVA rate percentage (0-100).
        iva_amount: Optional explicit IVA amount; when set must equal
            ``taxable_base * iva_rate / 100``.
        deductible_iva_ratio: Fraction of input IVA the contribuyente
            may deduct (0-1).
        schema_version: Forward-compatible schema version. ``"1"``.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    movement_id: str = Field(min_length=1)
    movement_date: date
    kind: MovementKind = MovementKind.PURCHASE
    sku: str = Field(default="default", min_length=1)
    quantity: Decimal = Field(gt=Decimal("0"))
    unit_cost: Decimal | None = Field(default=None, ge=Decimal("0"))
    taxable_base: Decimal | None = Field(default=None, ge=Decimal("0"))
    iva_rate: Decimal = Field(default=DEFAULT_IVA_GENERAL_RATE_PCT, ge=Decimal("0"), le=Decimal("100"))
    iva_amount: Decimal | None = Field(default=None, ge=Decimal("0"))
    deductible_iva_ratio: Decimal = Field(default=Decimal("1.00"), ge=Decimal("0"), le=Decimal("1"))
    schema_version: str = INVENTORY_SCHEMA_VERSION

    @property
    def value(self) -> Decimal:
        """Return the IVA-exclusive movement value."""
        if self.taxable_base is not None:
            return self.taxable_base
        if self.unit_cost is None:
            return _ZERO
        return self.quantity * self.unit_cost

    @property
    def resolved_unit_cost(self) -> Decimal:
        """Return the IVA-exclusive unit cost, falling back to ``taxable_base / quantity``."""
        if self.unit_cost is not None:
            return self.unit_cost
        if self.taxable_base is None:
            return _ZERO
        return self.taxable_base / self.quantity

    @field_validator("schema_version")
    @classmethod
    def _schema_version_supported(cls, value: str) -> str:
        """Reject any schema_version other than the current :data:`INVENTORY_SCHEMA_VERSION`."""
        if value != INVENTORY_SCHEMA_VERSION:
            raise InventoryValidationError(f"unsupported MovementRecord schema_version {value!r}")
        return value

    @model_validator(mode="after")
    def _validate_movement_amounts(self) -> MovementRecord:
        """Enforce that opening / purchase movements carry a cost and IVA decomposes consistently."""
        needs_cost = self.kind in {MovementKind.OPENING, MovementKind.PURCHASE}
        if needs_cost and self.unit_cost is None and self.taxable_base is None:
            raise InventoryValidationError("opening and purchase movements require unit_cost or taxable_base")
        if self.taxable_base is not None:
            computed_iva = _quantize(self.taxable_base * self.iva_rate / _HUNDRED)
            if self.iva_amount is not None and self.iva_amount != computed_iva:
                raise InventoryValidationError("iva_amount must equal taxable_base * iva_rate")
        return self


class StockLayer(BaseModel):
    """Remaining inventory quantity at one IVA-exclusive unit cost.

    Attributes:
        sku: SKU / item identifier.
        quantity: Layer quantity (strictly positive).
        unit_cost: Per-unit cost the layer was acquired at.
        source_movement_id: Stable id of the originating
            :class:`MovementRecord` (or a synthetic id for opening
            stock and weighted-average pools).
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    sku: str = Field(default="default", min_length=1)
    quantity: Decimal = Field(gt=Decimal("0"))
    unit_cost: Decimal = Field(ge=Decimal("0"))
    source_movement_id: str = Field(min_length=1)


class InventoryLedger(BaseModel):
    """Per-activity inventory ledger for one tax year.

    Attributes:
        actividad_id: Activity identifier the ledger is keyed by.
        year: Calendar year the ledger covers.
        valuation_method: FIFO, PMP, or coste medio; LIFO is forbidden.
        opening_stock: Aggregate IVA-exclusive opening valuation.
        opening_layers: Per-layer breakdown of opening stock; when
            non-empty must value-balance with ``opening_stock``.
        closing_stock: Optional explicit closing valuation; when
            ``None`` it is derived from movements at compute time.
        period_movements: Tuple of :class:`MovementRecord` rows
            covering the period.
        schema_version: Forward-compatible schema version. ``"1"``.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    actividad_id: str = Field(min_length=1)
    year: int = Field(ge=1900)
    valuation_method: ValuationMethod
    opening_stock: Decimal = Field(ge=Decimal("0"))
    opening_layers: tuple[StockLayer, ...] = ()
    closing_stock: Decimal | None = Field(default=None, ge=Decimal("0"))
    period_movements: tuple[MovementRecord, ...] = ()
    schema_version: str = INVENTORY_SCHEMA_VERSION

    @field_validator("schema_version")
    @classmethod
    def _schema_version_supported(cls, value: str) -> str:
        """Reject any schema_version other than the current :data:`INVENTORY_SCHEMA_VERSION`."""
        if value != INVENTORY_SCHEMA_VERSION:
            raise InventoryValidationError(f"unsupported InventoryLedger schema_version {value!r}")
        return value

    @model_validator(mode="after")
    def _opening_stock_matches_layers(self) -> InventoryLedger:
        """Enforce that ``opening_layers`` value-balances with ``opening_stock``."""
        if self.opening_layers and _quantize(_layers_value(self.opening_layers)) != _quantize(self.opening_stock):
            raise InventoryValidationError("opening_stock must equal the value of opening_layers")
        return self


class InventoryLedgerDocument(BaseModel):
    """JSON document containing inventory ledgers.

    Attributes:
        schema_version: Forward-compatible schema version. ``"1"``.
        ledgers: Tuple of :class:`InventoryLedger` rows.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    schema_version: str = INVENTORY_SCHEMA_VERSION
    ledgers: tuple[InventoryLedger, ...] = ()

    @field_validator("schema_version")
    @classmethod
    def _schema_version_supported(cls, value: str) -> str:
        """Reject any schema_version other than the current :data:`INVENTORY_SCHEMA_VERSION`."""
        if value != INVENTORY_SCHEMA_VERSION:
            raise InventoryValidationError(f"unsupported InventoryLedgerDocument schema_version {value!r}")
        return value


def parse_valuation_method(raw: str) -> ValuationMethod:
    """Parse a user-supplied valuation method and refuse LIFO explicitly.

    Args:
        raw: User input (case- and separator-insensitive).

    Returns:
        The matching :class:`ValuationMethod` member.

    Raises:
        LIFOForbiddenError: When the input normalises to ``"lifo"``.
        InventoryLedgerError: When the input matches no known method.
    """
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

    Returns closing stock minus opening stock for casilla ``0155``. If
    ``closing_stock`` is not supplied, it is derived via
    :func:`compute_inventory_valuation`.

    Args:
        ledger: Ledger to evaluate.
        year: Period year. The ledger is skipped when its ``year``
            does not match.

    Returns:
        Signed closing-minus-opening valuation, quantised to cents.
    """
    if ledger.year != year:
        return _ZERO
    closing = ledger.closing_stock
    if closing is None:
        closing = compute_inventory_valuation(ledger).closing_value
    return _quantize(closing - ledger.opening_stock)


class InventoryValuationResult(BaseModel):
    """Computed valuation outcome for an inventory ledger.

    Attributes:
        closing_layers: Tuple of :class:`StockLayer` rows surviving
            after period movements were applied.
        closing_value: Aggregate closing valuation.
        cogs_value: Cost-of-goods-sold for the period.
        purchase_value: Aggregate value of PURCHASE movements during
            the period.
    """

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
    """Compute Anexo D normal casilla ``0155`` for one activity.

    Args:
        year: Calendar year being filed.
        actividad: Activity identifier to filter ledgers by.
        ledgers: Ledgers to aggregate over.

    Returns:
        Sum of :func:`compute_inventory_variation` across matching
        ledgers, quantised to cents.
    """
    total = _ZERO
    for ledger in ledgers:
        if ledger.actividad_id == actividad:
            total += compute_inventory_variation(ledger, year)
    return _quantize(total)


def compute_inventory_valuation(ledger: InventoryLedger) -> InventoryValuationResult:
    """Value closing stock and COGS using the ledger's valuation method.

    Dispatches to the FIFO or weighted-average implementation per
    :attr:`InventoryLedger.valuation_method`.

    Args:
        ledger: Ledger to value.

    Returns:
        :class:`InventoryValuationResult` carrying the closing layers,
        closing valuation, COGS, and purchase totals.

    Raises:
        InventoryLedgerError: When ``valuation_method`` is not
            supported (defence-in-depth — should be unreachable as
            LIFO is rejected at parse time).
    """
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
                ),
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


__all__ = [
    "DEFAULT_IVA_GENERAL_RATE_PCT",
    "AmortizacionLedgerError",
    "BasisCapExceededError",
    "InventoryLedger",
    "InventoryLedgerError",
    "InventoryValidationError",
    "LIFOForbiddenError",
    "MovementKind",
    "MovementRecord",
    "StockLayer",
    "ValuationMethod",
    "compute_anexo_d_inventory_variation",
    "compute_inventory_valuation",
    "compute_inventory_variation",
    "parse_valuation_method",
]
