"""``aeat data ledgers inventory`` commands.

Manages per-actividad inventory ledgers in the encrypted persistence
layer (:mod:`aeat.adapters.persistence.profile.inventory`). Movement
recording, valuation method parsing (FIFO / PMP / coste medio; LIFO is
refused), and closing-stock arithmetic delegate to
:mod:`aeat.domain.profile.inventory`.
"""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path

import typer
from pydantic import BaseModel, ConfigDict

from .....adapters.persistence.profile.inventory import (
    create_inventory_ledger,
    load_inventory,
    record_movement,
)
from .....domain.profile.errors import InventoryLedgerError
from .....domain.profile.inventory import (
    InventoryLedger,
    MovementKind,
    MovementRecord,
    StockLayer,
    compute_inventory_valuation,
    parse_valuation_method,
)
from ..._context import json_output_requested
from ..._i18n import t, tr
from ..._schemas import OutputRootSchema, emit_json_success, register_schema

app = typer.Typer(name="inventory", no_args_is_help=True, help="Per-actividad inventory ledger.")
movement_app = typer.Typer(name="movement", no_args_is_help=True, help="Record stock movements.")
valuation_app = typer.Typer(name="valuation", no_args_is_help=True, help="Preview inventory valuation.")
app.add_typer(movement_app, name="movement")
app.add_typer(valuation_app, name="valuation")

_STRICT = ConfigDict(strict=True, frozen=True, extra="forbid")


class LayerPayload(BaseModel):
    """JSON payload for one remaining stock layer."""

    model_config = _STRICT

    sku: str
    quantity: str
    unit_cost: str
    source_movement_id: str


class InventoryLedgerPayload(BaseModel):
    """JSON payload for one inventory ledger."""

    model_config = _STRICT

    actividad_id: str
    year: int
    valuation_method: str
    opening_stock: str
    opening_layers: list[LayerPayload]
    movement_count: int


class InventoryMutationPayload(BaseModel):
    """JSON payload for inventory mutations."""

    model_config = _STRICT

    ledger: InventoryLedgerPayload
    stored: bool
    movement_id: str | None = None


class InventoryValuationPayload(BaseModel):
    """JSON payload for one inventory valuation preview."""

    model_config = _STRICT

    actividad_id: str
    year: int
    valuation_method: str
    opening_stock: str
    purchase_value: str
    cogs_value: str
    closing_stock: str
    variation: str
    layers: list[LayerPayload]


class InventoryListJson(OutputRootSchema[list[InventoryLedgerPayload]]):
    """JSON contract for inventory list output."""


class InventoryMutationJson(OutputRootSchema[InventoryMutationPayload]):
    """JSON contract for inventory mutation output."""


class InventoryValuationJson(OutputRootSchema[InventoryValuationPayload]):
    """JSON contract for inventory valuation output."""


for _command, _schema in {
    "data ledgers inventory list": InventoryListJson,
    "data ledgers inventory create": InventoryMutationJson,
    "data ledgers inventory movement add": InventoryMutationJson,
    "data ledgers inventory valuation preview": InventoryValuationJson,
}.items():
    register_schema(_command)(_schema)


@app.command(name="list", help="List inventory ledgers.")
def list_inventory(
    storage_dir: Path | None = typer.Option(None, "--storage-dir", help="Override the ledger directory.", hidden=True),
) -> None:
    """List persisted inventory ledgers."""

    ledgers = load_inventory(storage_dir=storage_dir)
    payload = [_ledger_payload(ledger) for ledger in ledgers]
    if json_output_requested():
        emit_json_success("data ledgers inventory list", payload)
        return
    if not payload:
        typer.echo(
            tr(
                t(
                    "No hay libros de inventario.",
                    "No inventory ledgers.",
                    "No hi ha llibres d'inventari.",
                    "Nincsenek készletek könyvei.",
                )
            )
        )
        return
    opening_label = tr(t("apertura", "opening", "obertura", "nyitás"))
    for item in payload:
        typer.echo(
            f"{item['actividad_id']} | {item['year']} | {item['valuation_method']} | "
            f"{opening_label} {item['opening_stock']} EUR"
        )


@app.command(name="create", help="Create one actividad/year inventory ledger.")
def create_inventory(
    actividad: str = typer.Argument(..., help="Economic activity id."),
    year: int = typer.Option(..., "--year", help="Tax year."),
    valuation_method: str = typer.Option(..., "--valuation-method", help="fifo, pmp, or coste_medio. LIFO is refused."),
    opening_stock: str = typer.Option("0.00", "--opening-stock", help="Opening stock value."),
    opening_quantity: str | None = typer.Option(None, "--opening-quantity", help="Optional opening quantity."),
    opening_unit_cost: str | None = typer.Option(None, "--opening-unit-cost", help="Optional opening unit cost."),
    sku: str = typer.Option("default", "--sku", help="Opening stock SKU when quantity is supplied."),
    storage_dir: Path | None = typer.Option(None, "--storage-dir", help="Override the ledger directory.", hidden=True),
) -> None:
    """Create an inventory ledger without overwriting an existing one."""

    layers: tuple[StockLayer, ...] = ()
    if opening_quantity is not None or opening_unit_cost is not None:
        if opening_quantity is None or opening_unit_cost is None:
            raise InventoryLedgerError("opening quantity and opening unit cost must be supplied together")
        layers = (
            StockLayer(
                sku=sku,
                quantity=_decimal(opening_quantity),
                unit_cost=_decimal(opening_unit_cost),
                source_movement_id=f"{actividad}-{year}-opening",
            ),
        )
    ledger = InventoryLedger(
        actividad_id=actividad,
        year=year,
        valuation_method=parse_valuation_method(valuation_method),
        opening_stock=_decimal(opening_stock),
        opening_layers=layers,
    )
    create_inventory_ledger(ledger, storage_dir=storage_dir)
    payload = {"ledger": _ledger_payload(ledger), "stored": True}
    if json_output_requested():
        emit_json_success("data ledgers inventory create", payload)
        return
    typer.echo(
        tr(
            t(
                f"Libro de inventario creado: {actividad} {year}.",
                f"Inventory ledger created: {actividad} {year}.",
                f"Llibre d'inventari creat: {actividad} {year}.",
                f"Keszlet konyv letrehozva: {actividad} {year}.",
            )
        )
    )


@movement_app.command(name="add", help="Add a purchase, COGS, opening, or count movement.")
def add_movement(
    actividad: str = typer.Option(..., "--actividad", help="Economic activity id."),
    year: int = typer.Option(..., "--year", help="Tax year."),
    movement_id: str = typer.Option(..., "--movement-id", help="Stable movement id."),
    movement_date: str = typer.Option(..., "--date", help="Movement date as YYYY-MM-DD."),
    kind: MovementKind = typer.Option(MovementKind.PURCHASE, "--kind", help="Movement kind."),
    sku: str = typer.Option("default", "--sku", help="Stock SKU."),
    quantity: str = typer.Option(..., "--quantity", help="Movement quantity."),
    unit_cost: str | None = typer.Option(None, "--unit-cost", help="VAT-exclusive unit cost for opening/purchase."),
    taxable_base: str | None = typer.Option(
        None,
        "--taxable-base",
        help="VAT-exclusive line base for opening/purchase.",
    ),
    vat_rate: str = typer.Option("21.00", "--vat-rate", help="VAT rate percentage."),
    storage_dir: Path | None = typer.Option(None, "--storage-dir", help="Override the ledger directory.", hidden=True),
) -> None:
    """Append a movement after validating the full valuation path."""

    base = _decimal(taxable_base) if taxable_base is not None else None
    rate = _decimal(vat_rate)
    movement = MovementRecord(
        movement_id=movement_id,
        movement_date=_date(movement_date),
        kind=kind,
        sku=sku,
        quantity=_decimal(quantity),
        unit_cost=_decimal(unit_cost) if unit_cost is not None else None,
        taxable_base=base,
        vat_rate=rate,
        vat_amount=None if base is None else _money(base * rate / Decimal("100")),
    )
    updated = record_movement(actividad, movement, year=year, storage_dir=storage_dir)
    payload = {"ledger": _ledger_payload(updated), "movement_id": movement_id, "stored": True}
    if json_output_requested():
        emit_json_success("data ledgers inventory movement add", payload)
        return
    typer.echo(
        tr(
            t(
                f"Movimiento de inventario registrado: {movement_id}.",
                f"Inventory movement recorded: {movement_id}.",
                f"Moviment d'inventari registrat: {movement_id}.",
                f"Keszlet mozgas rogzitve: {movement_id}.",
            )
        )
    )


@valuation_app.command(name="preview", help="Preview closing stock and COGS without writing.")
def preview_valuation(
    actividad: str = typer.Option(..., "--actividad", help="Economic activity id."),
    year: int = typer.Option(..., "--year", help="Tax year."),
    storage_dir: Path | None = typer.Option(None, "--storage-dir", help="Override the ledger directory.", hidden=True),
) -> None:
    """Preview inventory valuation."""

    ledger = _find_ledger(actividad, year, storage_dir=storage_dir)
    result = compute_inventory_valuation(ledger)
    payload = {
        "actividad_id": actividad,
        "year": year,
        "valuation_method": ledger.valuation_method.value,
        "opening_stock": str(ledger.opening_stock),
        "purchase_value": str(result.purchase_value),
        "cogs_value": str(result.cogs_value),
        "closing_stock": str(result.closing_value),
        "variation": str(result.closing_value - ledger.opening_stock),
        "layers": [_layer_payload(layer) for layer in result.closing_layers],
    }
    if json_output_requested():
        emit_json_success("data ledgers inventory valuation preview", payload)
        return
    closing_label = tr(t("cierre", "closing", "tancament", "zárás"))
    typer.echo(f"{actividad} {year}: {closing_label} {result.closing_value} EUR, COGS {result.cogs_value} EUR.")


def _find_ledger(actividad: str, year: int, *, storage_dir: Path | None) -> InventoryLedger:
    """Return the persisted ledger for ``(actividad, year)`` or raise :exc:`InventoryLedgerError`."""
    for ledger in load_inventory(storage_dir=storage_dir):
        if ledger.actividad_id == actividad and ledger.year == year:
            return ledger
    raise InventoryLedgerError(
        f"inventory ledger not found for {actividad!r} in {year}",
        context={"actividad_id": actividad, "year": year},
        suggestion="aeat data ledgers inventory list",
    )


def _ledger_payload(ledger: InventoryLedger) -> dict[str, object]:
    """Render an :class:`InventoryLedger` as a JSON-safe mapping for ``--json`` output."""
    return {
        "actividad_id": ledger.actividad_id,
        "year": ledger.year,
        "valuation_method": ledger.valuation_method.value,
        "opening_stock": str(ledger.opening_stock),
        "opening_layers": [_layer_payload(layer) for layer in ledger.opening_layers],
        "movement_count": len(ledger.period_movements),
    }


def _layer_payload(layer: StockLayer) -> dict[str, str]:
    """Render a :class:`StockLayer` as a JSON-safe mapping."""
    return {
        "sku": layer.sku,
        "quantity": str(layer.quantity),
        "unit_cost": str(layer.unit_cost),
        "source_movement_id": layer.source_movement_id,
    }


def _decimal(raw: str) -> Decimal:
    """Parse ``raw`` into a :class:`Decimal` or raise :exc:`typer.BadParameter`."""
    try:
        return Decimal(raw)
    except InvalidOperation as exc:
        raise typer.BadParameter(
            tr(
                t(
                    f"decimal no válido: {raw}",
                    f"invalid decimal: {raw}",
                    f"decimal no vàlid: {raw}",
                    f"ervenytelen tizedes szam: {raw}",
                )
            )
        ) from exc


def _date(raw: str) -> date:
    """Parse an ISO-8601 ``YYYY-MM-DD`` string or raise :exc:`typer.BadParameter`."""
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise typer.BadParameter(
            tr(
                t(
                    f"fecha no válida: {raw}",
                    f"invalid date: {raw}",
                    f"data no vàlida: {raw}",
                    f"ervenytelen datum: {raw}",
                )
            )
        ) from exc


def _money(value: Decimal) -> Decimal:
    """Quantize ``value`` to two decimals using ``ROUND_HALF_UP``."""
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


__all__ = ["app"]
