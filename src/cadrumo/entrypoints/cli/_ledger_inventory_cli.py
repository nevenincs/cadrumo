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
from ...core.i18n import tr
from ...domain.contribuyente.inventory import MovementKind
from ._command_policy import command_execution_policy
from ._common import (
    _emit_envelope,
    _parse_iso_date,
    parse_decimal_amount,
    parse_optional_decimal_amount,
)
from ._common import (
    active_bucket_id_or_refuse as _inventory_bucket_id,
)
from ._ledger_execution_policies import LEDGER_COMPUTE_READ, LEDGER_READ, LEDGER_WRITE, declare_metadata_group
from ._ledger_payloads import (
    InventoryCreateResult,
    InventoryListResult,
    InventoryMovementAddResult,
    InventoryValuationPreviewPayload,
)


def register_inventory_commands(app: typer.Typer) -> None:
    """Mount inventory command groups on the ledger app."""
    app.add_typer(inventory_app, name="inventory")
    inventory_app.add_typer(inventory_movement_app, name="movement")
    inventory_app.add_typer(inventory_valuation_app, name="valuation")


def _inventory_service() -> InventoryService:
    return InventoryService()


inventory_app = typer.Typer(
    name="inventory",
    help=tr("cli.app.ledger.inventory.group_help"),
    no_args_is_help=True,
)

inventory_movement_app = typer.Typer(
    name="movement",
    help=tr("cli.app.ledger.inventory.movement_group_help"),
    no_args_is_help=True,
)
inventory_valuation_app = typer.Typer(
    name="valuation",
    help=tr("cli.app.ledger.inventory.valuation_group_help"),
    no_args_is_help=True,
)
declare_metadata_group(inventory_app)
declare_metadata_group(inventory_movement_app)
declare_metadata_group(inventory_valuation_app)


@inventory_app.command(
    "list",
    help=tr("cli.app.ledger.inventory.list_help"),
)
@command_execution_policy(LEDGER_READ)
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


@inventory_app.command(
    "create",
    help=tr("cli.app.ledger.inventory.create_help"),
)
@command_execution_policy(LEDGER_WRITE)
def inventory_create(
    ctx: typer.Context,
    actividad_id: str = typer.Argument(
        ...,
        help=tr("cli.app.ledger.inventory.actividad_id_help"),
    ),
    year: int = typer.Option(..., "--year", help=tr("cli.app.ledger.inventory.year_help")),
    valuation_method: str = typer.Option(
        ...,
        "--valuation-method",
        help=tr("cli.app.ledger.inventory.valuation_method_help"),
    ),
    opening_stock: str = typer.Option(
        "0",
        "--opening-stock",
        help=tr("cli.app.ledger.inventory.opening_stock_help"),
    ),
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


@inventory_movement_app.command(
    "add",
    help=tr("cli.app.ledger.inventory.movement_add_help"),
)
@command_execution_policy(LEDGER_WRITE)
def inventory_movement_add(
    ctx: typer.Context,
    actividad_id: str = typer.Option(
        ...,
        "--actividad-id",
        help=tr("cli.app.ledger.inventory.actividad_id_help"),
    ),
    year: int = typer.Option(..., "--year", help=tr("cli.app.ledger.inventory.year_help")),
    movement_id: str = typer.Option(
        ...,
        "--movement-id",
        help=tr("cli.app.ledger.inventory.movement_id_help"),
    ),
    movement_date: str = typer.Option(
        ...,
        "--date",
        help=tr("cli.app.ledger.inventory.movement_date_help"),
    ),
    kind: MovementKind = typer.Option(
        ...,
        "--kind",
        help=tr("cli.app.ledger.inventory.movement_kind_help"),
    ),
    quantity: str = typer.Option(
        ...,
        "--quantity",
        help=tr("cli.app.ledger.inventory.quantity_help"),
    ),
    unit_cost: str | None = typer.Option(
        None,
        "--unit-cost",
        help=tr("cli.app.ledger.inventory.unit_cost_help"),
    ),
    taxable_base: str | None = typer.Option(
        None,
        "--taxable-base",
        help=tr("cli.app.ledger.inventory.taxable_base_help"),
    ),
    iva_rate: str = typer.Option(
        str(DEFAULT_IVA_GENERAL_RATE_PCT),
        "--iva-rate",
        help=tr("cli.app.ledger.inventory.iva_rate_help"),
    ),
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


@inventory_valuation_app.command(
    "preview",
    help=tr("cli.app.ledger.inventory.valuation_preview_help"),
)
@command_execution_policy(LEDGER_COMPUTE_READ)
def inventory_valuation_preview(
    ctx: typer.Context,
    actividad_id: str = typer.Option(
        ...,
        "--actividad-id",
        help=tr("cli.app.ledger.inventory.actividad_id_help"),
    ),
    year: int = typer.Option(..., "--year", help=tr("cli.app.ledger.inventory.year_help")),
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
