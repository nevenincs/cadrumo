"""Typer registration for ledger inventory commands.

The commands delegate inventory persistence and valuation to
:class:`InventoryService` and emit typed payloads
from :mod:`._ledger_payloads`.
"""

from __future__ import annotations

import json

import typer

from ...application.inventory import InventoryMovementCommand, InventoryService
from ...core.external_constants import DEFAULT_IVA_GENERAL_RATE_PCT
from ...domain.contribuyente.inventory import MovementKind
from ._common import (
    _emit_envelope,
    _parse_iso_date,
    parse_decimal_amount,
    parse_optional_decimal_amount,
)
from ._common import (
    active_bucket_id_or_refuse as _inventory_bucket_id,
)
from ._ledger_payloads import (
    InventoryCreateResult,
    InventoryListResult,
    InventoryMovementAddResult,
    InventoryValuationPreviewPayload,
)


def _inventory_service() -> InventoryService:
    return InventoryService()


def inventory_list(ctx: typer.Context) -> None:
    """List per-actividad ledgers via :meth:`InventoryService.list_all`."""
    bucket_id = _inventory_bucket_id()
    rows = _inventory_service().list_all(bucket_id=bucket_id)
    payload = {
        "bucket_id": bucket_id,
        "rows": [row.model_dump(mode="json") for row in rows],
        "count": len(rows),
    }
    lines = [f"bucket\t{bucket_id}", f"count\t{len(rows)}"]
    for row in rows:
        lines.append(
            f"{row.actividad_id}\t{row.year}\t{row.valuation_method.value}\t"
            f"opening={row.opening_stock}\tmovements={row.movement_count}",
        )
    _emit_envelope(
        ctx,
        command="ledger.inventory.list",
        result=InventoryListResult.model_validate(payload),
        lines=lines,
    )


def inventory_create(
    ctx: typer.Context,
    actividad_id: str = ...,
    year: int = ...,
    valuation_method: str = ...,
    opening_stock: str = "0",
) -> None:
    """Create a ledger via :meth:`InventoryService.create`."""
    bucket_id = _inventory_bucket_id()
    result = _inventory_service().create(
        bucket_id=bucket_id,
        actividad_id=actividad_id,
        year=year,
        valuation_method=valuation_method,
        opening_stock=parse_decimal_amount(opening_stock, label="opening-stock"),
    )
    ledger = result.ledger
    payload = json.loads(ledger.model_dump_json())
    payload["bucket_event_ids"] = list(result.bucket_event_ids)
    _emit_envelope(
        ctx,
        command="ledger.inventory.create",
        result=InventoryCreateResult.model_validate_json(json.dumps(payload)),
        lines=(
            f"bucket\t{bucket_id}",
            f"actividad_id\t{ledger.actividad_id}",
            f"year\t{ledger.year}",
            f"valuation_method\t{ledger.valuation_method.value}",
            f"opening_stock\t{ledger.opening_stock}",
            f"bucket_event_ids\t{','.join(result.bucket_event_ids)}",
        ),
    )


def inventory_movement_add(
    ctx: typer.Context,
    actividad_id: str = ...,
    year: int = ...,
    movement_id: str = ...,
    movement_date: str = ...,
    kind: MovementKind = ...,
    quantity: str = ...,
    unit_cost: str | None = None,
    taxable_base: str | None = None,
    iva_rate: str = str(DEFAULT_IVA_GENERAL_RATE_PCT),
) -> None:
    """Append an :class:`InventoryMovementCommand` to an actividad ledger."""
    bucket_id = _inventory_bucket_id()
    command = InventoryMovementCommand(
        movement_id=movement_id,
        movement_date=_parse_iso_date(movement_date, label="--date"),
        kind=kind,
        quantity=parse_decimal_amount(quantity, label="quantity"),
        unit_cost=parse_optional_decimal_amount(unit_cost, label="unit-cost"),
        taxable_base=parse_optional_decimal_amount(taxable_base, label="taxable-base"),
        iva_rate=parse_decimal_amount(iva_rate, label="iva-rate"),
    )
    result = _inventory_service().movement_add(
        bucket_id=bucket_id,
        actividad_id=actividad_id,
        year=year,
        movement=command,
    )
    ledger = result.ledger
    payload = ledger.model_dump(mode="json")
    payload["bucket_event_ids"] = list(result.bucket_event_ids)
    _emit_envelope(
        ctx,
        command="ledger.inventory.movement.add",
        result=InventoryMovementAddResult.model_validate(payload),
        lines=(
            f"bucket\t{bucket_id}",
            f"actividad_id\t{ledger.actividad_id}",
            f"year\t{ledger.year}",
            f"movements\t{len(ledger.period_movements)}",
            f"bucket_event_ids\t{','.join(result.bucket_event_ids)}",
        ),
    )


def inventory_valuation_preview(
    ctx: typer.Context,
    actividad_id: str = ...,
    year: int = ...,
) -> None:
    """Preview valuation via :meth:`InventoryService.valuation_preview`."""
    bucket_id = _inventory_bucket_id()
    result = _inventory_service().valuation_preview(bucket_id=bucket_id, actividad_id=actividad_id, year=year)
    preview = result.preview
    _emit_envelope(
        ctx,
        command="ledger.inventory.valuation.preview",
        result=InventoryValuationPreviewPayload.from_result(result),
        lines=(
            f"bucket\t{bucket_id}",
            f"actividad_id\t{preview.actividad_id}",
            f"year\t{preview.year}",
            f"valuation_method\t{preview.valuation_method.value}",
            f"closing_stock\t{preview.closing_stock}",
            f"cogs\t{preview.cogs}",
            f"bucket_event_ids\t{','.join(result.bucket_event_ids)}",
        ),
    )
