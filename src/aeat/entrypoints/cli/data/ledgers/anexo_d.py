"""`aeat data ledgers anexo-d` commands."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import typer
from pydantic import BaseModel, ConfigDict

from .....adapters.persistence.profile.assets import load_amortization_ledger, load_assets
from .....adapters.persistence.profile.inventory import load_inventory
from .....domain.formulas._rulesets.modelo_100.anexo_d_ledgers import derive_anexo_d_normal_inputs
from ..._context import json_output_requested
from ..._schemas import OutputRootSchema, emit_json_success, register_schema

app = typer.Typer(name="anexo-d", no_args_is_help=True, help="Preview Modelo 100 Anexo D ledger-derived inputs.")

_STRICT = ConfigDict(strict=True, frozen=True, extra="forbid")


class AnexoDPreviewPayload(BaseModel):
    """JSON payload for one Anexo D preview."""

    model_config = _STRICT

    modelo: str
    year: int
    actividad_id: str
    casillas: dict[str, str]
    source: str


class AnexoDPreviewJson(OutputRootSchema[AnexoDPreviewPayload]):
    """JSON contract for Anexo D preview output."""


register_schema("data ledgers anexo-d preview")(AnexoDPreviewJson)


@app.command(name="preview", help="Preview ledger-derived Modelo 100 Anexo D casillas.")
def preview(
    year: int = typer.Option(..., "--year", help="Tax year."),
    actividad: str = typer.Option(..., "--actividad", help="Economic activity id."),
    modelo: str = typer.Option("100", "--modelo", help="Modelo number. Only 100 is supported."),
    storage_dir: Path | None = typer.Option(None, "--storage-dir", help="Override the ledger directory.", hidden=True),
) -> None:
    """Preview Anexo D inputs derived from encrypted local ledgers."""

    if modelo != "100":
        raise typer.BadParameter("only Modelo 100 supports Anexo D ledger preview")
    resolved = derive_anexo_d_normal_inputs(
        {},
        year=year,
        actividad_id=actividad,
        assets=load_assets(storage_dir=storage_dir),
        amortization_ledger=load_amortization_ledger(storage_dir=storage_dir),
        inventory_ledgers=load_inventory(storage_dir=storage_dir),
    )
    payload = {
        "modelo": modelo,
        "year": year,
        "actividad_id": actividad,
        "casillas": _casilla_payload(resolved),
        "source": "encrypted-ledgers",
    }
    if json_output_requested():
        emit_json_success("data ledgers anexo-d preview", payload)
        return
    typer.echo(f"Modelo {modelo} Anexo D {actividad} {year}")
    for casilla, value in payload["casillas"].items():
        typer.echo(f"{casilla}: {value} EUR")


def _casilla_payload(values: dict[str, Decimal]) -> dict[str, str]:
    return {casilla: str(amount) for casilla, amount in sorted(values.items())}


__all__ = ["app"]
