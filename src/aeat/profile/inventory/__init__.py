"""Inventory ledgers for actividad economica stock valuation."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ...formulas import ValuationMethod
from ...logging import get_logger
from ..errors import InventoryLedgerError, LIFOForbiddenError

_log = get_logger(__name__)

INVENTORY_LEDGER_FILENAME = "inventory-ledger.envelope.json"
SCHEMA_VERSION = "1"
_ENVELOPE_VERSION = 1
_HKDF_CONTEXT_INVENTORY = b"aeat.profile.inventory.ledger.v1"
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


def default_storage_dir() -> Path:
    """Return the configured governed ledger storage directory."""

    from ...config import load_settings

    return Path(load_settings().aeat_ledgers_dir)


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
    ledgers: tuple[InventoryLedger, ...] | None = None,
    storage_dir: Path | None = None,
) -> Decimal:
    """Compute Anexo D normal casilla `0155` for one activity."""

    resolved = ledgers if ledgers is not None else load_inventory(storage_dir=storage_dir)
    total = _ZERO
    for ledger in resolved:
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


def _inventory_path(storage_dir: Path | None) -> Path:
    return (storage_dir or default_storage_dir()) / INVENTORY_LEDGER_FILENAME


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(_CENT, rounding=ROUND_HALF_UP)


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
            from ...storage import Envelope, SensitivityClass, load_encrypted_envelope
            from ...storage._encrypted_columns import _resolve_master_key_provider

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

        from ...storage import Envelope, SensitivityClass, exclusive_file_lock, save_encrypted_envelope
        from ...storage._encrypted_columns import _resolve_master_key_provider

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

        from ...storage import exclusive_file_lock

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

        from ...storage import exclusive_file_lock

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
        from ...storage import Envelope, SensitivityClass, load_encrypted_envelope
        from ...storage._encrypted_columns import _resolve_master_key_provider

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
        from ...storage import Envelope, SensitivityClass, save_encrypted_envelope
        from ...storage._encrypted_columns import _resolve_master_key_provider

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
    "INVENTORY_LEDGER_FILENAME",
    "InventoryLedger",
    "InventoryLedgerDocument",
    "InventoryLedgerRepository",
    "InventoryValuationResult",
    "MovementKind",
    "MovementRecord",
    "StockLayer",
    "compute_anexo_d_inventory_variation",
    "compute_inventory_valuation",
    "compute_inventory_variation",
    "create_inventory_ledger",
    "default_storage_dir",
    "load_inventory",
    "parse_valuation_method",
    "record_movement",
    "save_inventory",
]
