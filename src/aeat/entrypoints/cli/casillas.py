"""Typer commands for the curated AEAT casilla catalogue.

Wraps :mod:`aeat.domain.casillas` so the operator can dump, verify, and
(eventually) extract / translate per-modelo casilla catalogues from the
command line. Real extraction and translation are gated on the LLM
client surface and currently exit ``2`` with an explanatory message.
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


@app.command(name="extract", help="Write a draft extraction payload to a temp JSON file.")
def extract(
    modelo: str = typer.Option(..., "--modelo", help="Stable modelo identifier, e.g. MODELO_130."),
    period: str = typer.Option(..., "--period", help="Filing period, e.g. 2025Q4."),
    root: Path | None = typer.Option(None, "--root", help="Optional casillas corpus root override."),
) -> None:
    """Report that real extraction is blocked on the LLM client surface.

    Raises:
        typer.Exit: Always exits ``2`` until the LLM client surface ships;
            only the protocol boundary and canonical corpus support are
            available today.
    """
    _load_for_cli(modelo, period, root)
    typer.secho(
        tr(
            t(
                "aeat casillas extract requiere la superficie de cliente LLM; "
                "esta rama solo incluye el límite de protocolo y el soporte de corpus canónico.",
                "aeat casillas extract requires the LLM client surface; "
                "this branch only ships the protocol boundary and canonical corpus support.",
                "aeat casillas extract requereix la superfície de client LLM; "
                "aquesta branca només inclou el límit de protocol i el suport de corpus canònic.",
                "az aeat casillas extract az LLM kliens feluletet igényli; ez az ag csak a protokoll hatart es a kanonikus korpusz tamogatast tartalmazza.",
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


@app.command(name="translate", help="Write a draft translation payload to a temp JSON file.")
def translate(
    modelo: str = typer.Option(..., "--modelo", help="Stable modelo identifier, e.g. MODELO_130."),
    period: str = typer.Option(..., "--period", help="Filing period, e.g. 2025Q4."),
    root: Path | None = typer.Option(None, "--root", help="Optional casillas corpus root override."),
) -> None:
    """Report that real translation is blocked on the bulk translator surface.

    Raises:
        typer.Exit: Always exits ``2`` until the bulk translator client
            surface ships; only the protocol boundary and canonical
            corpus support are available today.
    """
    _load_for_cli(modelo, period, root)
    typer.secho(
        tr(
            t(
                "aeat casillas translate requiere la superficie del traductor en bulk; "
                "esta rama solo incluye el límite de protocolo y el soporte de corpus canónico.",
                "aeat casillas translate requires the bulk translator surface; "
                "this branch only ships the protocol boundary and canonical corpus support.",
                "aeat casillas translate requereix la superfície del traductor en massa; "
                "aquesta branca només inclou el límit de protocol i el suport de corpus canònic.",
                "az aeat casillas translate a csoportos forditasi feluletet igényli; ez az ag csak a protokoll hatart es a kanonikus korpusz tamogatast tartalmazza.",
            )
        ),
        fg=typer.colors.YELLOW,
    )
    raise typer.Exit(code=2)


__all__ = ["app"]
