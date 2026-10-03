"""Presentation handlers for worker-owned ledger inventory operations."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

import typer
from pydantic import ValidationError

from ...application.inventory.registered_operation import (
    InventoryAcquisitionCostRequest,
    InventoryClosingAuthorityRecordInput,
    InventoryClosingAuthorityRecordRequest,
    InventoryCreateRequest,
    InventoryMovementAddRequest,
    InventoryValuationPreviewRequest,
)
from ...application.operations.public_scalar import PublicDecimal
from ...core.external_constants import UTF_8_ENCODING
from ...core.i18n.render import tr
from ...domain.contribuyente.inventory.closing_authority_records import InventoryClosingAuthorityRecord
from ...domain.contribuyente.inventory.records import (
    InventoryAcquisitionCost,
    MovementKind,
)
from ._date_parsing import _parse_iso_date
from ._decimal_parsing import parse_decimal_amount, parse_optional_decimal_amount
from .common import active_bucket_id_or_refuse as _inventory_bucket_id
from .common import emit_envelope
from .ledger_business_payloads import InventoryClosingAuthorityRecordResult
from .runtime_ledger_inventory import (
    add_inventory_movement,
    create_inventory_ledger,
    preview_inventory_valuation,
    read_inventory_catalogue,
    record_inventory_closing_authority,
)


def _parse_acquisition_cost(*, from_stdin: bool) -> InventoryAcquisitionCostRequest | None:
    """Read one typed purchase-cost request from the non-argv stdin channel."""
    if not from_stdin:
        return None
    value = typer.get_text_stream("stdin").read()
    try:
        acquisition = InventoryAcquisitionCost.model_validate_json(value)
        return InventoryAcquisitionCostRequest.from_domain(acquisition)
    except ValidationError as exc:
        details = "; ".join(f"{'.'.join(str(item) for item in error['loc'])}: {error['msg']}" for error in exc.errors())
        raise typer.BadParameter(
            tr("cli.app.ledger.inventory.acquisition_cost_invalid", details=details),
            param_hint="--acquisition-cost-stdin",
        ) from exc


def inventory_list(ctx: typer.Context) -> None:
    """List the selected profile's activity ledgers from its worker."""
    completion, payload = read_inventory_catalogue(ctx)
    bucket_id = payload.bucket_id
    lines = [f"bucket\t{bucket_id}", f"count\t{payload.count}"]
    for row in completion.projection.rows:
        lines.append(
            f"{row.actividad_id}\t{row.year}\t{row.valuation_method.value}\t"
            f"opening={row.opening_stock.decimal}\tmovements={row.movement_count}",
        )
    emit_envelope(ctx, command="ledger.inventory.list", result=payload, lines=lines)


def inventory_create(
    ctx: typer.Context,
    actividad_id: str,
    year: int,
    valuation_method: str,
    opening_stock: str = "0",
) -> None:
    """Create one ledger through the selected profile's authenticated worker."""
    bucket_id = _inventory_bucket_id()
    request = InventoryCreateRequest(
        profile_id=UUID(bucket_id),
        actividad_id=actividad_id,
        year=year,
        valuation_method=valuation_method,
        opening_stock=PublicDecimal(decimal=str(parse_decimal_amount(opening_stock, label="opening-stock"))),
    )
    completion, payload = create_inventory_ledger(ctx, request=request)
    ledger = completion.projection.ledger
    if ledger is None:
        raise RuntimeError("inventory create bridge returned no canonical ledger")
    emit_envelope(
        ctx,
        command="ledger.inventory.create",
        result=payload,
        lines=(
            f"bucket\t{bucket_id}",
            f"actividad_id\t{ledger.actividad_id}",
            f"year\t{ledger.year}",
            f"valuation_method\t{ledger.valuation_method.value}",
            f"opening_stock\t{ledger.opening_stock.decimal}",
            f"bucket_event_ids\t{','.join(payload.bucket_event_ids)}",
        ),
    )


def inventory_movement_add(
    ctx: typer.Context,
    actividad_id: str,
    year: int,
    movement_id: str,
    movement_date: str,
    kind: MovementKind,
    quantity: str,
    unit_cost: str | None = None,
    taxable_base: str | None = None,
    acquisition_cost_stdin: bool = False,
) -> None:
    """Append one typed movement through the selected profile's worker."""
    bucket_id = _inventory_bucket_id()
    unit_cost_amount = parse_optional_decimal_amount(unit_cost, label="unit-cost")
    taxable_base_amount = parse_optional_decimal_amount(taxable_base, label="taxable-base")
    request = InventoryMovementAddRequest(
        profile_id=UUID(bucket_id),
        actividad_id=actividad_id,
        year=year,
        movement_id=movement_id,
        movement_date=_parse_iso_date(movement_date, label="--date"),
        kind=kind,
        quantity=PublicDecimal(decimal=str(parse_decimal_amount(quantity, label="quantity"))),
        unit_cost=PublicDecimal(decimal=str(unit_cost_amount)) if unit_cost_amount is not None else None,
        taxable_base=PublicDecimal(decimal=str(taxable_base_amount)) if taxable_base_amount is not None else None,
        acquisition_cost=_parse_acquisition_cost(from_stdin=acquisition_cost_stdin),
    )
    _completion, payload = add_inventory_movement(ctx, request=request)
    emit_envelope(
        ctx,
        command="ledger.inventory.movement.add",
        result=payload,
        lines=(
            f"bucket\t{bucket_id}",
            f"actividad_id\t{payload.actividad_id}",
            f"year\t{payload.year}",
            f"movements\t{len(payload.period_movements)}",
            f"bucket_event_ids\t{','.join(payload.bucket_event_ids)}",
        ),
    )


def inventory_valuation_preview(
    ctx: typer.Context,
    actividad_id: str,
    year: int,
) -> None:
    """Preview the canonical valuation through the selected profile worker."""
    bucket_id = _inventory_bucket_id()
    request = InventoryValuationPreviewRequest(
        profile_id=UUID(bucket_id),
        actividad_id=actividad_id,
        year=year,
    )
    _completion, payload = preview_inventory_valuation(ctx, request=request)
    emit_envelope(
        ctx,
        command="ledger.inventory.valuation.preview",
        result=payload,
        lines=(
            f"bucket\t{bucket_id}",
            f"actividad_id\t{payload.actividad_id}",
            f"year\t{payload.year}",
            f"valuation_method\t{payload.valuation_method}",
            f"derived_closing_value\t{payload.derived_closing_value}",
            f"cogs\t{payload.cogs}",
            f"bucket_event_ids\t{','.join(payload.bucket_event_ids)}",
        ),
    )


def inventory_closing_authority_record(
    ctx: typer.Context,
    actividad_id: str,
    year: int,
    file: Path,
) -> None:
    """Read one typed authority DTO, then persist it in the profile worker."""
    bucket_id = _inventory_bucket_id()
    try:
        authority = InventoryClosingAuthorityRecord.model_validate_json(file.read_text(encoding=UTF_8_ENCODING))
        authority_record = InventoryClosingAuthorityRecordInput.from_domain(authority)
    except (OSError, ValidationError) as exc:
        raise typer.BadParameter(
            tr("cli.app.ledger.inventory.authority_invalid"),
            param_hint="--file",
        ) from exc
    request = InventoryClosingAuthorityRecordRequest(
        profile_id=UUID(bucket_id),
        actividad_id=actividad_id,
        year=year,
        authority_record=authority_record,
    )
    _completion, payload = record_inventory_closing_authority(ctx, request=request)
    result: InventoryClosingAuthorityRecordResult = payload
    emit_envelope(
        ctx,
        command="ledger.inventory.closing-authority.record",
        result=result,
        lines=(
            f"actividad_id\t{result.actividad_id}",
            f"year\t{result.year}",
            f"authority_record_fingerprint\t{result.authority_record_fingerprint}",
        ),
    )


__all__ = [
    "inventory_closing_authority_record",
    "inventory_create",
    "inventory_list",
    "inventory_movement_add",
    "inventory_valuation_preview",
]
