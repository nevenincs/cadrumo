"""Typer commands for the curated AEAT casilla catalogue.

Wraps :mod:`aeat.domain.casillas` so the operator can dump and verify
per-modelo casilla catalogues from the command line.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer

from ...core.config import load_settings
from ...domain.casillas import CasillaCatalogue, CasillaParseError, load_casillas, verify_casillas
from ._i18n import t, tr

app = typer.Typer(
    name="casillas",
    no_args_is_help=True,
    help="Manage the curated AEAT casilla catalogue.",
)


def _load_for_cli(modelo: str, period: str, root: Path | None) -> CasillaCatalogue:
    """Load a catalogue and convert parse failures into CLI exits.

    Args:
        modelo: Stable modelo identifier (e.g. ``MODELO_130``).
        period: Filing period (e.g. ``2025Q4``).
        root: Optional override of the casillas corpus root.

    Returns:
        The validated catalogue.

    Raises:
        typer.Exit: Exit code ``1`` when the catalogue cannot be parsed.
    """
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
    """Print the canonical :class:`aeat.domain.casillas.CasillaCatalogue` as JSON."""
    catalogue = _load_for_cli(modelo, period, root)
    typer.echo(json.dumps(catalogue.model_dump(mode="json"), indent=2, ensure_ascii=False))


@app.command(name="verify", help="Validate the canonical catalogue for a modelo/period.")
def verify(
    modelo: str = typer.Option(..., "--modelo", help="Stable modelo identifier, e.g. MODELO_130."),
    period: str = typer.Option(..., "--period", help="Filing period, e.g. 2025Q4."),
    root: Path | None = typer.Option(None, "--root", help="Optional casillas corpus root override."),
) -> None:
    """Verify the catalogue via :func:`aeat.domain.casillas.verify_casillas` and exit non-zero on failure."""
    resolved_root = root if root is not None else load_settings().aeat_casillas_root
    path = resolved_root / modelo.lower() / f"{period}.json"
    catalogue = _load_for_cli(modelo, period, root)
    errors = verify_casillas(catalogue)
    if errors:
        for error in errors:
            typer.secho(str(error), fg=typer.colors.RED)
        raise typer.Exit(code=1)
    typer.echo(
        tr(
            t(
                f"verificado {path}",
                f"verified {path}",
                f"verificat {path}",
                f"verifikalva {path}",
            )
        )
    )


__all__ = ["app"]
