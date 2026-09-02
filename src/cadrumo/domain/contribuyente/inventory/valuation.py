"""Inventory valuation and Anexo D projection engines.

This module owns calculations over the canonical inventory records.
Record shapes remain in :mod:`.records`; callers import each calculation
directly from this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import fields as dataclass_fields
from decimal import Decimal
from typing import Literal

from pydantic import ValidationError

from ....core.hashing import content_hash_hex as _content_hash_hex
from ....core.identity import ContentDigest
from ....core.money.rounding import round_to_cents as _quantize
from ...identifiers import canonical_decimal_string as _canonical_decimal_string
from .records import (
    InventoryAnexoDResult,
    InventoryClosingAuthority,
    InventoryClosingConflictDiagnostic,
    InventoryLedger,
    InventoryLedgerError,
    InventoryValidationError,
    InventoryValuationResult,
    MovementKind,
    MovementRecord,
    StockLayer,
    ValuationMethod,
    resolve_inventory_authoritative_closing,
)

_ZERO = Decimal("0.00")


@dataclass(frozen=True, slots=True)
class _InventoryAnexoDDerivation:
    source_ledger: InventoryLedger
    source_ledger_fingerprint: ContentDigest
    actividad_id: str
    filing_year: int
    opening_value: Decimal
    movement_derived_closing_value: Decimal
    authoritative_closing_value: Decimal
    selected_authority: InventoryClosingAuthority
    authority_record_fingerprint: ContentDigest
    decision_id: str
    decision_fingerprint: ContentDigest
    physical_observation_id: str | None
    physical_observation_fingerprint: ContentDigest | None
    physical_observed_closing_value: Decimal | None
    prior_closing_link_fingerprint: ContentDigest
    complete_acquisition_total: Decimal
    acquisition_fingerprints: tuple[ContentDigest, ...]
    casilla_0177: Decimal
    casilla_0181: Decimal
    casilla_0182: Decimal
    closing_conflict: InventoryClosingConflictDiagnostic | None
    issues: tuple[Literal["physical_closing_conflict"], ...]


def _inventory_projection_source_fingerprint(ledger: InventoryLedger) -> ContentDigest:
    """Hash canonical economic identities without exposing retained source facts."""
    return _content_hash_hex(
        {
            "fingerprint_schema_version": "1",
            "actividad_id": ledger.actividad_id,
            "filing_year": ledger.year,
            "valuation_method": ledger.valuation_method.value,
            "opening_stock": _canonical_decimal_string(ledger.opening_stock),
            "opening_layers": [
                {
                    "sku": layer.sku,
                    "quantity": _canonical_decimal_string(layer.quantity),
                    "unit_cost": _canonical_decimal_string(layer.unit_cost),
                    "source_movement_id": layer.source_movement_id,
                }
                for layer in sorted(
                    ledger.opening_layers,
                    key=lambda item: (item.sku, item.source_movement_id, item.quantity, item.unit_cost),
                )
            ],
            "movements": [
                {
                    "movement_id": movement.movement_id,
                    "movement_date": movement.movement_date.isoformat(),
                    "kind": movement.kind.value,
                    "sku": movement.sku,
                    "quantity": _canonical_decimal_string(movement.quantity),
                    "unit_cost": (
                        _canonical_decimal_string(movement.unit_cost) if movement.unit_cost is not None else None
                    ),
                    "taxable_base": (
                        _canonical_decimal_string(movement.taxable_base) if movement.taxable_base is not None else None
                    ),
                    "iva_rate": _canonical_decimal_string(movement.iva_rate),
                    "iva_amount": (
                        _canonical_decimal_string(movement.iva_amount) if movement.iva_amount is not None else None
                    ),
                    "deductible_iva_ratio": _canonical_decimal_string(movement.deductible_iva_ratio),
                    "schema_version": movement.schema_version,
                    "acquisition_fingerprint": (
                        inventory_acquisition_fingerprint(movement) if movement.kind is MovementKind.PURCHASE else None
                    ),
                }
                for movement in _sorted_movements(ledger)
            ],
            "closing_authority_record_fingerprint": (
                ledger.closing_authority_record.fingerprint if ledger.closing_authority_record is not None else None
            ),
        },
    )


def derive_inventory_anexo_d_values(ledger: InventoryLedger) -> _InventoryAnexoDDerivation:
    """Derive every public projection field from one retained canonical source."""
    if ledger.year != 2025:
        raise InventoryLedgerError(
            "inventory Anexo D projection is grounded only for filing year 2025",
            context={"actividad_id": ledger.actividad_id, "filing_year": ledger.year},
        )
    out_of_period_movements = tuple(
        movement.movement_id for movement in ledger.period_movements if movement.movement_date.year != ledger.year
    )
    if out_of_period_movements:
        raise InventoryLedgerError(
            "inventory Anexo D projection contains movements outside its filing year",
            context={
                "actividad_id": ledger.actividad_id,
                "filing_year": ledger.year,
                "movement_ids": out_of_period_movements,
            },
        )
    try:
        validated = InventoryLedger.model_validate(ledger.model_dump())
    except ValidationError as exc:
        raise InventoryLedgerError("inventory projection source is incomplete or unreadable") from exc
    validated = validated.model_copy(update={"period_movements": _sorted_movements(validated)})
    record = validated.closing_authority_record
    if record is None:
        raise InventoryLedgerError("inventory projection requires a complete closing-authority record")
    resolution = resolve_inventory_authoritative_closing(
        validated,
        decision=record.decision,
        physical_observation=record.physical_observation,
        prior_closing_link=record.prior_closing_link,
    )
    purchases = tuple(movement for movement in _sorted_movements(validated) if movement.kind is MovementKind.PURCHASE)
    if any(movement.acquisition_cost is None for movement in purchases):
        raise InventoryLedgerError("inventory projection requires complete acquisition cost for every purchase")
    acquisition_total = _quantize(
        sum(
            (movement.acquisition_cost.total_acquisition_cost for movement in purchases if movement.acquisition_cost),
            _ZERO,
        ),
    )
    acquisition_fingerprints = tuple(inventory_acquisition_fingerprint(movement) for movement in purchases)
    valuation = compute_inventory_valuation(validated)
    if acquisition_total != valuation.purchase_value:
        raise InventoryLedgerError("complete acquisition totals do not match inventory valuation purchase authority")
    opening = _quantize(ledger.opening_stock)
    signed_variation = _quantize(resolution.authoritative_value - opening)
    return _InventoryAnexoDDerivation(
        source_ledger=validated,
        source_ledger_fingerprint=_inventory_projection_source_fingerprint(validated),
        actividad_id=validated.actividad_id,
        filing_year=2025,
        opening_value=opening,
        movement_derived_closing_value=resolution.movement_derived_value,
        authoritative_closing_value=resolution.authoritative_value,
        selected_authority=resolution.authority,
        authority_record_fingerprint=record.fingerprint,
        decision_id=resolution.decision_id,
        decision_fingerprint=resolution.decision_fingerprint,
        physical_observation_id=resolution.physical_observation_id,
        physical_observation_fingerprint=resolution.physical_observation_fingerprint,
        physical_observed_closing_value=resolution.physical_observed_value,
        prior_closing_link_fingerprint=resolution.prior_closing_link_fingerprint,
        complete_acquisition_total=acquisition_total,
        acquisition_fingerprints=acquisition_fingerprints,
        casilla_0177=max(signed_variation, _ZERO),
        casilla_0181=acquisition_total,
        casilla_0182=max(-signed_variation, _ZERO),
        closing_conflict=resolution.conflict,
        issues=("physical_closing_conflict",) if resolution.conflict is not None else (),
    )


def compute_inventory_anexo_d_projection(
    ledger: InventoryLedger,
) -> InventoryAnexoDResult:
    """Project one complete 2025 activity ledger to inventory casillas."""
    projection_values = derive_inventory_anexo_d_values(ledger)
    payload = {field.name: getattr(projection_values, field.name) for field in dataclass_fields(projection_values)}
    projection = InventoryAnexoDResult.model_construct(
        None,
        **payload,
        projection_fingerprint="0" * 64,
    )
    return InventoryAnexoDResult(**payload, projection_fingerprint=projection.expected_projection_fingerprint)


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
    closing = layers_value(layers)
    return InventoryValuationResult(
        closing_layers=tuple(layers),
        closing_value=_quantize(closing),
        cogs_value=_quantize(cogs_value),
        purchase_value=_quantize(purchase_value),
    )


def _compute_weighted_average(ledger: InventoryLedger) -> InventoryValuationResult:
    pools = _weighted_average_opening_pools(ledger)
    cogs_value = _ZERO
    purchase_value = _ZERO
    for movement in _sorted_movements(ledger):
        purchase_delta, cogs_delta = _apply_weighted_average_movement(ledger, movement, pools)
        purchase_value += purchase_delta
        cogs_value += cogs_delta
    layers = _weighted_average_layers(ledger, pools)
    return InventoryValuationResult(
        closing_layers=layers,
        closing_value=_quantize(sum((quantity_value[1] for quantity_value in pools.values()), _ZERO)),
        cogs_value=_quantize(cogs_value),
        purchase_value=_quantize(purchase_value),
    )


def _weighted_average_opening_pools(ledger: InventoryLedger) -> dict[str, tuple[Decimal, Decimal]]:
    pools: dict[str, tuple[Decimal, Decimal]] = {}
    for layer in _opening_layers(ledger):
        quantity, value = pools.get(layer.sku, (_ZERO, _ZERO))
        pools[layer.sku] = (quantity + layer.quantity, value + layer.quantity * layer.unit_cost)
    return pools


def _apply_weighted_average_movement(
    ledger: InventoryLedger,
    movement: MovementRecord,
    pools: dict[str, tuple[Decimal, Decimal]],
) -> tuple[Decimal, Decimal]:
    quantity, value = pools.get(movement.sku, (_ZERO, _ZERO))
    if movement.kind in {MovementKind.OPENING, MovementKind.PURCHASE}:
        unit_cost = movement.resolved_unit_cost
        movement_value = movement.quantity * unit_cost
        pools[movement.sku] = (quantity + movement.quantity, value + movement_value)
        purchase_delta = movement_value if movement.kind is MovementKind.PURCHASE else _ZERO
        return purchase_delta, _ZERO
    if movement.kind is MovementKind.COGS:
        return _apply_weighted_average_cogs(ledger, movement, quantity, value, pools)
    if movement.kind is MovementKind.COUNT:
        average = _ZERO if quantity == _ZERO else value / quantity
        pools[movement.sku] = (movement.quantity, movement.quantity * average)
    return _ZERO, _ZERO


def _apply_weighted_average_cogs(
    ledger: InventoryLedger,
    movement: MovementRecord,
    quantity: Decimal,
    value: Decimal,
    pools: dict[str, tuple[Decimal, Decimal]],
) -> tuple[Decimal, Decimal]:
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
    pools[movement.sku] = (quantity - movement.quantity, value - consumed)
    return _ZERO, consumed


def _weighted_average_layers(
    ledger: InventoryLedger,
    pools: dict[str, tuple[Decimal, Decimal]],
) -> tuple[StockLayer, ...]:
    return tuple(
        StockLayer(
            sku=sku,
            quantity=quantity,
            unit_cost=_ZERO if quantity == _ZERO else value / quantity,
            source_movement_id=f"{ledger.actividad_id}-{ledger.year}-{sku}-weighted-average",
        )
        for sku, (quantity, value) in sorted(pools.items())
        if quantity > _ZERO
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


def layers_value(layers: tuple[StockLayer, ...] | list[StockLayer]) -> Decimal:
    return sum((layer.quantity * layer.unit_cost for layer in layers), _ZERO)


def inventory_acquisition_fingerprint(movement: MovementRecord) -> ContentDigest:
    """Return a deterministic versioned economic/evidence purchase fingerprint."""
    if movement.kind is not MovementKind.PURCHASE or movement.acquisition_cost is None:
        raise InventoryValidationError("only a complete purchase acquisition can be fingerprinted")
    acquisition = movement.acquisition_cost
    payload = {
        "fingerprint_schema_version": "1",
        "movement_id": movement.movement_id,
        "movement_date": movement.movement_date.isoformat(),
        "kind": movement.kind.value,
        "sku": movement.sku,
        "quantity": _canonical_decimal_string(movement.quantity),
        "consideration_excluding_iva": _canonical_decimal_string(acquisition.consideration_excluding_iva),
        "consideration_iva_amount": _canonical_decimal_string(acquisition.consideration_iva_amount),
        "consideration_deductible_iva_ratio": _canonical_decimal_string(
            acquisition.consideration_deductible_iva_ratio,
        ),
        "components": [
            {
                "component_id": item.component_id,
                "kind": item.kind.value,
                "taxable_base": _canonical_decimal_string(item.taxable_base),
                "iva_amount": _canonical_decimal_string(item.iva_amount),
                "deductible_iva_ratio": _canonical_decimal_string(item.deductible_iva_ratio),
                "evidence_references": sorted(ref.reference for ref in item.evidence_references),
            }
            for item in sorted(acquisition.attributable_cost_components, key=lambda value: value.component_id)
        ],
        "evidence": [
            {
                "reference": item.reference.reference,
                "evidence_kind": item.evidence_kind.value,
                "content_digest": item.content_digest,
            }
            for item in sorted(acquisition.evidence, key=lambda value: value.reference.reference)
        ],
        "completeness": acquisition.completeness.model_dump(mode="json"),
        "totals": {
            "directly_attributable_cost_total": _canonical_decimal_string(
                acquisition.directly_attributable_cost_total,
            ),
            "nonrecoverable_iva_included": _canonical_decimal_string(acquisition.nonrecoverable_iva_included),
            "recoverable_iva_excluded": _canonical_decimal_string(acquisition.recoverable_iva_excluded),
            "total_acquisition_cost": _canonical_decimal_string(acquisition.total_acquisition_cost),
        },
    }
    return _content_hash_hex(payload)
