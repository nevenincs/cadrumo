"""`aeat data ledgers assets` commands."""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path

import typer
from pydantic import BaseModel, ConfigDict

from .....adapters.persistence.profile.assets import (
    AmortizationLedgerRepository,
    default_storage_dir,
    load_amortization_ledger,
    load_assets,
)
from .....adapters.persistence.profile.assets import (
    add_asset as persist_asset,
)
from .....domain.formulas._rulesets.modelo_100._amortization import LIS_ART_12_LINEAL_TABLE, AssetClass
from .....domain.profile.assets import (
    AssetRecord,
    LibertadAmortizacionElection,
    compute_amortization_for_year,
)
from .....domain.profile.errors import AssetRecordError
from ..._context import json_output_requested
from ..._schemas import OutputRootSchema, emit_json_success, register_schema

app = typer.Typer(name="assets", no_args_is_help=True, help="Depreciable technical kit ledger.")

_STRICT = ConfigDict(strict=True, frozen=True, extra="forbid")


class LibertadPayload(BaseModel):
    """JSON payload for an accelerated-amortization election."""

    model_config = _STRICT

    enabled: bool
    legal_basis: str | None
    amount_limit: str | None


class AssetPayload(BaseModel):
    """JSON payload for one asset."""

    model_config = _STRICT

    identifier: str
    description: str
    asset_class: str
    acquisition_date: str
    taxable_base: str
    vat_rate: str
    vat_amount: str
    deductible_vat_ratio: str
    gross_total: str
    cost_basis: str
    useful_life_years: int | None
    libertad_amortizacion: LibertadPayload
    actividad_id: str | None
    allocation_ratio: str


class AssetMutationPayload(BaseModel):
    """JSON payload for asset mutations."""

    model_config = _STRICT

    asset: AssetPayload
    stored: bool


class AssetAmortizationPayload(BaseModel):
    """JSON payload for amortization preview and apply."""

    model_config = _STRICT

    asset_id: str
    year: int
    amount: str
    stored: bool
    entry_count: int | None = None


class AssetClassPayload(BaseModel):
    """JSON payload for one LIS art. 12.1.a table row."""

    model_config = _STRICT

    asset_class: str
    coef_max_pct: str
    period_max_years: int


class AssetsListJson(OutputRootSchema[list[AssetPayload]]):
    """JSON contract for asset list output."""


class AssetsShowJson(OutputRootSchema[dict[str, AssetPayload]]):
    """JSON contract for asset detail output."""


class AssetsMutationJson(OutputRootSchema[AssetMutationPayload]):
    """JSON contract for asset mutation output."""


class AssetAmortizationJson(OutputRootSchema[AssetAmortizationPayload]):
    """JSON contract for amortization output."""


class AssetClassesJson(OutputRootSchema[list[AssetClassPayload]]):
    """JSON contract for LIS asset-class output."""


for _command, _schema in {
    "data ledgers assets list": AssetsListJson,
    "data ledgers assets show": AssetsShowJson,
    "data ledgers assets add": AssetsMutationJson,
    "data ledgers assets amortization preview": AssetAmortizationJson,
    "data ledgers assets amortization apply": AssetAmortizationJson,
    "data ledgers assets classes list": AssetClassesJson,
}.items():
    register_schema(_command)(_schema)


classes_app = typer.Typer(name="classes", no_args_is_help=True, help="Browse LIS art. 12.1.a asset classes.")
amortization_app = typer.Typer(name="amortization", no_args_is_help=True, help="Preview or record amortization.")
app.add_typer(classes_app, name="classes")
app.add_typer(amortization_app, name="amortization")


@app.command(name="list", help="List encrypted asset records.")
def list_assets(
    storage_dir: Path | None = typer.Option(None, "--storage-dir", help="Override the ledger directory.", hidden=True),
) -> None:
    """List persisted assets."""

    assets = load_assets(storage_dir=storage_dir)
    payload = [_asset_payload(asset) for asset in assets]
    if json_output_requested():
        emit_json_success("data ledgers assets list", payload)
        return
    if not payload:
        typer.echo("No asset records.")
        return
    for item in payload:
        typer.echo(
            f"{item['identifier']} | {item['asset_class']} | basis {item['cost_basis']} EUR | "
            f"acquired {item['acquisition_date']}"
        )


@app.command(name="show", help="Show one encrypted asset record.")
def show_asset(
    identifier: str = typer.Argument(..., help="Asset identifier."),
    storage_dir: Path | None = typer.Option(None, "--storage-dir", help="Override the ledger directory.", hidden=True),
) -> None:
    """Show one persisted asset."""

    asset = _find_asset(identifier, storage_dir=storage_dir)
    payload = {"asset": _asset_payload(asset)}
    if json_output_requested():
        emit_json_success("data ledgers assets show", payload)
        return
    typer.echo(f"{asset.identifier}: {asset.description}")
    typer.echo(f"class: {asset.asset_class.value}")
    typer.echo(f"basis: {asset.cost_basis} EUR")
    typer.echo(
        f"invoice: base {asset.resolved_taxable_base} EUR, VAT {asset.vat_rate}% ({asset.resolved_vat_amount} EUR)"
    )


@app.command(name="add", help="Add one technical-kit asset. Duplicate identifiers are refused.")
def add_asset(
    identifier: str = typer.Argument(..., help="Stable asset identifier."),
    description: str = typer.Option(..., "--description", help="Human-readable asset description."),
    asset_class: str = typer.Option(..., "--asset-class", help="LIS art. 12.1.a asset-class value."),
    acquisition_date: str = typer.Option(..., "--acquisition-date", help="Acquisition date as YYYY-MM-DD."),
    taxable_base: str = typer.Option(..., "--taxable-base", help="VAT-exclusive invoice base."),
    vat_rate: str = typer.Option("21.00", "--vat-rate", help="VAT rate percentage: 0, 4, 10, or 21."),
    deductible_vat_ratio: str = typer.Option(
        "1.00",
        "--deductible-vat-ratio",
        help="Deductible VAT ratio from 0 to 1.",
    ),
    useful_life_years: int | None = typer.Option(
        None,
        "--useful-life-years",
        help="Optional period override within LIS cap.",
    ),
    actividad: str | None = typer.Option(None, "--actividad", help="Economic activity id."),
    allocation_ratio: str = typer.Option("1.00", "--allocation-ratio", help="Activity allocation ratio from 0 to 1."),
    libertad: bool = typer.Option(
        False,
        "--libertad-amortizacion",
        help="Apply an explicit LIS art. 12 accelerated election.",
    ),
    libertad_basis: str | None = typer.Option(
        None,
        "--libertad-basis",
        help="Legal basis for the accelerated election.",
    ),
    storage_dir: Path | None = typer.Option(None, "--storage-dir", help="Override the ledger directory.", hidden=True),
) -> None:
    """Persist a new asset."""

    if libertad and not libertad_basis:
        raise AssetRecordError(
            "--libertad-basis is required when --libertad-amortizacion is used",
            context={"asset_id": identifier},
        )
    base = _decimal(taxable_base)
    rate = _decimal(vat_rate)
    deductible = _decimal(deductible_vat_ratio)
    vat = _money(base * rate / Decimal("100"))
    basis = _money(base + vat * (Decimal("1") - deductible))
    asset = AssetRecord(
        identifier=identifier,
        description=description,
        asset_class=AssetClass(asset_class),
        acquisition_date=_date(acquisition_date),
        taxable_base=base,
        vat_rate=rate,
        vat_amount=vat,
        deductible_vat_ratio=deductible,
        gross_total=_money(base + vat),
        cost_basis=basis,
        useful_life_years=useful_life_years,
        libertad_amortizacion=LibertadAmortizacionElection(enabled=libertad, legal_basis=libertad_basis),
        actividad_id=actividad,
        allocation_ratio=_decimal(allocation_ratio),
    )
    persist_asset(asset, storage_dir=storage_dir)
    payload = {"asset": _asset_payload(asset), "stored": True}
    if json_output_requested():
        emit_json_success("data ledgers assets add", payload)
        return
    typer.echo(f"Asset recorded: {identifier} ({basis} EUR amortizable basis).")


@classes_app.command(name="list", help="List LIS art. 12.1.a asset classes and rates.")
def list_classes() -> None:
    """List supported asset classes."""

    payload = [
        {
            "asset_class": row.asset_class.value,
            "coef_max_pct": str(row.coef_max_pct),
            "period_max_years": row.period_max_years,
        }
        for row in LIS_ART_12_LINEAL_TABLE
    ]
    if json_output_requested():
        emit_json_success("data ledgers assets classes list", payload)
        return
    for row in payload:
        typer.echo(f"{row['asset_class']} | {row['coef_max_pct']}% | max {row['period_max_years']} years")


@amortization_app.command(name="preview", help="Preview amortization without writing the ledger.")
def preview_amortization(
    asset: str = typer.Option(..., "--asset", help="Asset identifier."),
    year: int = typer.Option(..., "--year", help="Tax year."),
    storage_dir: Path | None = typer.Option(None, "--storage-dir", help="Override the ledger directory.", hidden=True),
) -> None:
    """Preview one amortization amount."""

    record = _find_asset(asset, storage_dir=storage_dir)
    ledger = load_amortization_ledger(storage_dir=storage_dir)
    amount = compute_amortization_for_year(record, year, ledger)
    payload = {"asset_id": asset, "year": year, "amount": str(amount), "stored": False}
    if json_output_requested():
        emit_json_success("data ledgers assets amortization preview", payload)
        return
    typer.echo(f"{asset} {year}: {amount} EUR (preview)")


@amortization_app.command(name="apply", help="Compute and record one amortization amount.")
def apply_amortization(
    asset: str = typer.Option(..., "--asset", help="Asset identifier."),
    year: int = typer.Option(..., "--year", help="Tax year."),
    storage_dir: Path | None = typer.Option(None, "--storage-dir", help="Override the ledger directory.", hidden=True),
) -> None:
    """Record one amortization amount."""

    record = _find_asset(asset, storage_dir=storage_dir)
    result = AmortizationLedgerRepository(store_dir=storage_dir or default_storage_dir()).record(record, year)
    payload = {
        "asset_id": asset,
        "year": year,
        "amount": str(result.amount),
        "stored": result.stored,
        "entry_count": len(result.ledger.entries),
    }
    if json_output_requested():
        emit_json_success("data ledgers assets amortization apply", payload)
        return
    status = "recorded" if result.stored else "already recorded"
    typer.echo(f"Amortization {status}: {asset} {year} {result.amount} EUR.")


def _find_asset(identifier: str, *, storage_dir: Path | None) -> AssetRecord:
    for asset in load_assets(storage_dir=storage_dir):
        if asset.identifier == identifier:
            return asset
    raise AssetRecordError(
        f"asset {identifier!r} was not found",
        context={"asset_id": identifier},
        suggestion="aeat data ledgers assets list",
    )


def _asset_payload(asset: AssetRecord) -> dict[str, object]:
    return {
        "identifier": asset.identifier,
        "description": asset.description,
        "asset_class": asset.asset_class.value,
        "acquisition_date": asset.acquisition_date.isoformat(),
        "taxable_base": str(asset.resolved_taxable_base),
        "vat_rate": str(asset.vat_rate),
        "vat_amount": str(asset.resolved_vat_amount),
        "deductible_vat_ratio": str(asset.deductible_vat_ratio),
        "gross_total": str(asset.resolved_gross_total),
        "cost_basis": str(asset.cost_basis),
        "useful_life_years": asset.useful_life_years,
        "libertad_amortizacion": asset.libertad_amortizacion.model_dump(mode="json"),
        "actividad_id": asset.actividad_id,
        "allocation_ratio": str(asset.allocation_ratio),
    }


def _decimal(raw: str) -> Decimal:
    try:
        return Decimal(raw)
    except InvalidOperation as exc:
        raise typer.BadParameter(f"invalid decimal: {raw}") from exc


def _date(raw: str) -> date:
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise typer.BadParameter(f"invalid date: {raw}") from exc


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


__all__ = ["app"]
