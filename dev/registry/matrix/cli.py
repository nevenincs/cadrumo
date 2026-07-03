"""Developer CLI for the per-modelo registry support/capability matrix."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Annotated

import typer

from .manager import build_capability_matrix, render_matrix_table

app = typer.Typer(
    name="matrix",
    help="Report per-modelo registry capability coverage (calc-grade, manifest, export, extractor).",
    no_args_is_help=True,
)


@app.command("report")
def report(
    as_json: Annotated[
        bool,
        typer.Option("--json", help="Emit the matrix as a JSON array instead of a human-readable table."),
    ] = False,
) -> None:
    """Print the per-modelo support/capability matrix for the bundled registry.

    For every modelo the registry can load, probes its *latest* revision
    (by ``valid_from``) for: whether it is calc-grade (a non-empty
    calculation closure), whether it declares a calculation-completeness
    manifest, whether it registers a ``fixed_width`` (fichero-BOE) and/or
    ``xml_dictionary`` export layout, and whether it registers at least one
    extraction profile.
    """
    rows = build_capability_matrix()
    if as_json:
        typer.echo(json.dumps([asdict(row) for row in rows], default=str, indent=2))
        return
    typer.echo(render_matrix_table(rows))


__all__ = ["app"]
