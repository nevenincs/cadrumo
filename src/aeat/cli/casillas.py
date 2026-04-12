"""Typer commands for casilla catalogue workflows."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from aeat.casillas import CasillaCatalogue, CasillaParseError, load_casillas, verify_casillas
from aeat.config import load_settings

app = typer.Typer(
    name="casillas",
    no_args_is_help=True,
    help="Manage the curated AEAT casilla catalogue.",
)


def _load_for_cli(modelo: str, period: str, root: Path | None) -> CasillaCatalogue:
    """Load a catalogue and convert parse failures into CLI exits."""
    try:
        return load_casillas(modelo, period, root=root)
    except CasillaParseError as exc:
        typer.secho(str(exc), fg=typer.colors.RED)
        raise typer.Exit(code=1) from exc


@app.command(name="list", help="Dump the canonical catalogue JSON for a modelo/period.")
def list_casillas(
    modelo: str = typer.Option(..., "--modelo", help="Stable modelo identifier, e.g. MODELO_130."),
    period: str = typer.Option(..., "--period", help="Filing period, e.g. 2025Q4."),
    root: Path | None = typer.Option(None, "--root", help="Optional casillas corpus root override."),
) -> None:
    """Print a canonical catalogue as JSON."""
    catalogue = _load_for_cli(modelo, period, root)
    typer.echo(json.dumps(catalogue.model_dump(mode="json"), indent=2, ensure_ascii=False))


@app.command(name="verify", help="Validate the canonical catalogue for a modelo/period.")
def verify(
    modelo: str = typer.Option(..., "--modelo", help="Stable modelo identifier, e.g. MODELO_130."),
    period: str = typer.Option(..., "--period", help="Filing period, e.g. 2025Q4."),
    root: Path | None = typer.Option(None, "--root", help="Optional casillas corpus root override."),
) -> None:
    """Verify a canonical catalogue and exit non-zero on failure."""
    resolved_root = root if root is not None else load_settings().aeat_casillas_root
    path = resolved_root / modelo.lower() / f"{period}.json"
    catalogue = _load_for_cli(modelo, period, root)
    errors = verify_casillas(catalogue)
    if errors:
        for error in errors:
            typer.secho(str(error), fg=typer.colors.RED)
        raise typer.Exit(code=1)
    typer.echo(f"verified {path}")


@app.command(name="extract", help="Write a draft extraction payload to a temp JSON file.")
def extract(
    modelo: str = typer.Option(..., "--modelo", help="Stable modelo identifier, e.g. MODELO_130."),
    period: str = typer.Option(..., "--period", help="Filing period, e.g. 2025Q4."),
    root: Path | None = typer.Option(None, "--root", help="Optional casillas corpus root override."),
) -> None:
    """Report that real extraction is blocked on the issue-21 client surface."""
    _load_for_cli(modelo, period, root)
    typer.secho(
        "aeat casillas extract requires the real issue-21 LLM client surface; "
        "this branch only ships the protocol boundary and canonical corpus support.",
        fg=typer.colors.YELLOW,
    )
    raise typer.Exit(code=2)


@app.command(name="translate", help="Write a draft translation payload to a temp JSON file.")
def translate(
    modelo: str = typer.Option(..., "--modelo", help="Stable modelo identifier, e.g. MODELO_130."),
    period: str = typer.Option(..., "--period", help="Filing period, e.g. 2025Q4."),
    root: Path | None = typer.Option(None, "--root", help="Optional casillas corpus root override."),
) -> None:
    """Report that real translation is blocked on the issue-21 client surface."""
    _load_for_cli(modelo, period, root)
    typer.secho(
        "aeat casillas translate requires the real issue-21 bulk translator surface; "
        "this branch only ships the protocol boundary and canonical corpus support.",
        fg=typer.colors.YELLOW,
    )
    raise typer.Exit(code=2)


__all__ = ["app"]
