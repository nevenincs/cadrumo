"""Registry-gated ``aeat data ledgers assets`` command surface."""

from __future__ import annotations

import typer
from pydantic import BaseModel, ConfigDict

from ..._i18n import t, tr
from ..._schemas import OutputRootSchema, register_schema

app = typer.Typer(name="assets", no_args_is_help=True, help="Depreciable technical kit ledger.")
classes_app = typer.Typer(name="classes", no_args_is_help=True, help="Browse registry-backed asset classes.")
amortization_app = typer.Typer(name="amortization", no_args_is_help=True, help="Preview or record amortization.")
app.add_typer(classes_app, name="classes")
app.add_typer(amortization_app, name="amortization")

_STRICT = ConfigDict(strict=True, frozen=True, extra="forbid")
_REGISTRY_REQUIRED = t(
    "los libros de activos requieren un snapshot de registro validado",
    "asset ledgers require a validated registry snapshot",
    "els llibres d'actius requereixen un snapshot de registre validat",
    "az eszkoznyilvantartas validalt registry snapshotot igenyel",
)


class AssetPayload(BaseModel):
    """Disabled asset ledger JSON payload shape retained for schema discovery."""

    model_config = _STRICT

    identifier: str
    description: str


class AssetMutationPayload(BaseModel):
    """Disabled asset mutation JSON payload shape retained for schema discovery."""

    model_config = _STRICT

    asset: AssetPayload
    stored: bool


class AssetAmortizationPayload(BaseModel):
    """Disabled amortization JSON payload shape retained for schema discovery."""

    model_config = _STRICT

    asset_id: str
    year: int
    amount: str
    stored: bool
    entry_count: int | None = None


class AssetClassPayload(BaseModel):
    """Disabled asset-class JSON payload shape retained for schema discovery."""

    model_config = _STRICT

    asset_class: str
    coef_max_pct: str
    period_max_years: int


class AssetsListJson(OutputRootSchema[list[AssetPayload]]):
    """JSON contract for disabled asset list output."""


class AssetsShowJson(OutputRootSchema[dict[str, AssetPayload]]):
    """JSON contract for disabled asset detail output."""


class AssetsMutationJson(OutputRootSchema[AssetMutationPayload]):
    """JSON contract for disabled asset mutation output."""


class AssetAmortizationJson(OutputRootSchema[AssetAmortizationPayload]):
    """JSON contract for disabled amortization output."""


class AssetClassesJson(OutputRootSchema[list[AssetClassPayload]]):
    """JSON contract for disabled asset-class output."""


for _command, _schema in {
    "data ledgers assets list": AssetsListJson,
    "data ledgers assets show": AssetsShowJson,
    "data ledgers assets add": AssetsMutationJson,
    "data ledgers assets amortization preview": AssetAmortizationJson,
    "data ledgers assets amortization apply": AssetAmortizationJson,
    "data ledgers assets classes list": AssetClassesJson,
}.items():
    register_schema(_command)(_schema)


def _raise_registry_required() -> None:
    raise typer.BadParameter(tr(_REGISTRY_REQUIRED))


@app.command(name="list", help="List encrypted asset records.")
def list_assets() -> None:
    """Reject legacy asset-ledger reads."""
    _raise_registry_required()


@app.command(name="show", help="Show one encrypted asset record.")
def show_asset(identifier: str = typer.Argument(..., help="Asset identifier.")) -> None:
    """Reject legacy asset-ledger reads."""
    _ = identifier
    _raise_registry_required()


@app.command(name="add", help="Add one technical-kit asset.")
def add_asset(identifier: str = typer.Argument(..., help="Stable asset identifier.")) -> None:
    """Reject legacy asset-ledger writes."""
    _ = identifier
    _raise_registry_required()


@classes_app.command(name="list", help="List registry-backed asset classes and rates.")
def list_classes() -> None:
    """Reject legacy asset-class lookup."""
    _raise_registry_required()


@amortization_app.command(name="preview", help="Preview amortization without writing the ledger.")
def preview_amortization() -> None:
    """Reject legacy amortization calculation."""
    _raise_registry_required()


@amortization_app.command(name="apply", help="Compute and record one amortization amount.")
def apply_amortization() -> None:
    """Reject legacy amortization calculation and writes."""
    _raise_registry_required()


__all__ = ["app"]
