"""Typer commands for the curated AEAT casilla catalogue.

Wraps :mod:`aeat.domain.casillas` so the operator can dump, verify, and
request extract / translate operations for per-modelo casilla
catalogues from the command line. Extraction and translation require
external client integrations; this module reports their availability
without duplicating domain parsing rules.
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


@app.command(name="extract", help="Validate catalogue inputs and report extraction availability.")
def extract(
    modelo: str = typer.Option(..., "--modelo", help="Stable modelo identifier, e.g. MODELO_130."),
    period: str = typer.Option(..., "--period", help="Filing period, e.g. 2025Q4."),
    root: Path | None = typer.Option(None, "--root", help="Optional casillas corpus root override."),
) -> None:
    """Report that extraction requires an unavailable LLM client integration.

    Raises:
        typer.Exit: Always exits ``2`` because extraction requires an
            unavailable LLM client.
    """
    _load_for_cli(modelo, period, root)
    typer.secho(
        tr(
            t(
                "aeat casillas extract requiere la superficie de cliente LLM; "
                "solo están disponibles el límite de protocolo y el soporte de corpus canónico.",
                "aeat casillas extract requires the LLM client surface; "
                "only the protocol boundary and canonical corpus support are available.",
                "aeat casillas extract requereix la superfície de client LLM; "
                "només estan disponibles el límit de protocol i el suport de corpus canònic.",
                "az aeat casillas extract az LLM kliens feluletet igényli; "
                "csak a protokoll hatar es a kanonikus korpusz tamogatas erheto el.",
            )
        ),
        fg=typer.colors.YELLOW,
    )
    raise typer.Exit(code=2)


@app.command(
    name="hydrate",
    help="Re-generate the entire corpus/casillas/ tree from the rule engine + curated data.",
)
def hydrate() -> None:
    """Run the deterministic corpus hydration generator.

    Calls :func:`aeat.domain.casillas._hydrate.run`, which writes one
    JSON catalogue per ``(modelo, period)`` for every modelo / year /
    period the project supports. Idempotent; re-running produces zero
    diff against the committed corpus when the rule engine and the
    curated data are unchanged.
    """
    from ...domain.casillas._hydrate import run

    run()


@app.command(name="translate", help="Validate catalogue inputs and report translation availability.")
def translate(
    modelo: str = typer.Option(..., "--modelo", help="Stable modelo identifier, e.g. MODELO_130."),
    period: str = typer.Option(..., "--period", help="Filing period, e.g. 2025Q4."),
    root: Path | None = typer.Option(None, "--root", help="Optional casillas corpus root override."),
) -> None:
    """Report that translation requires an unavailable bulk translator integration.

    Raises:
        typer.Exit: Always exits ``2`` because translation requires an
            unavailable bulk translator client.
    """
    _load_for_cli(modelo, period, root)
    typer.secho(
        tr(
            t(
                "aeat casillas translate requiere la superficie del traductor en bulk; "
                "solo están disponibles el límite de protocolo y el soporte de corpus canónico.",
                "aeat casillas translate requires the bulk translator surface; "
                "only the protocol boundary and canonical corpus support are available.",
                "aeat casillas translate requereix la superfície del traductor en massa; "
                "només estan disponibles el límit de protocol i el suport de corpus canònic.",
                "az aeat casillas translate a csoportos forditasi feluletet igenyli; "
                "csak a protokoll hatar es a kanonikus korpusz tamogatas erheto el.",
            )
        ),
        fg=typer.colors.YELLOW,
    )
    raise typer.Exit(code=2)


__all__ = ["app"]
