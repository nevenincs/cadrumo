"""Developer CLI for scaffolding a new modelo's registry authoring tree."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Annotated

import typer

from dev._paths import REPO_ROOT

from .checklist import render_checklist
from .manager import NewModeloError, NewModeloScaffoldManager, ScaffoldResult

app = typer.Typer(
    name="newmodelo",
    help="Scaffold the skeleton registry directory tree for a new AEAT modelo revision.",
    no_args_is_help=True,
)


def _default_manager() -> NewModeloScaffoldManager:
    # cli.py lives at dev/registry/newmodelo/cli.py; parents[3] is the repo root.
    repo_root = REPO_ROOT
    modelos_root = repo_root / "src" / "cadrumo" / "_data" / "registry" / "aeat" / "modelos"
    return NewModeloScaffoldManager(registry_modelos_root=modelos_root)


def _date(value: str, *, option: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise NewModeloError(f"{option} must be an ISO date (YYYY-MM-DD)") from exc


def _echo_result(result: ScaffoldResult, *, mode: str) -> None:
    typer.echo(f"Modelo {result.modelo_id} revision {result.revision_id!r} at {result.modelo_root}")
    if mode == "scaffold":
        typer.echo(f"  written        : {len(result.written)}")
        typer.echo(f"  already present: {len(result.already_present)}")
        for path in result.written:
            typer.echo(f"    + {path.as_posix()}")
    else:
        typer.echo(f"  present : {len(result.already_present)}")
        typer.echo(f"  missing : {len(result.missing)}")
        for path in result.missing:
            typer.echo(f"    ! {path.as_posix()}")


@app.command("scaffold")
def scaffold(
    modelo_id: Annotated[str, typer.Argument(help="Three-digit AEAT modelo identifier, e.g. '410'.")],
    revision_id: Annotated[
        str,
        typer.Argument(help="Revision identifier, e.g. '2026-y-siguientes'."),
    ],
    valid_from: Annotated[str, typer.Option("--valid-from", help="Grounded applicability start date (YYYY-MM-DD).")],
    year_from: Annotated[int, typer.Option("--year-from", help="First filing year selected by this revision.")],
    period: Annotated[list[str], typer.Option("--period", help="Applicable filing period; repeat as needed.")],
    title: Annotated[
        str | None,
        typer.Option("--title", help="Working title for the manifest.toml placeholder."),
    ] = None,
    valid_to: Annotated[
        str | None, typer.Option("--valid-to", help="Grounded applicability end date, if known.")
    ] = None,
    registry_modelos_root: Annotated[
        Path | None,
        typer.Option(
            "--registry-modelos-root",
            help="Override the registry modelos root; intended for isolated developer/test runs.",
        ),
    ] = None,
) -> None:
    """Scaffold a new modelo with explicit applicability coordinates.

    Writes ``manifest.toml`` and a ``revisions/<revision_id>/`` fragment
    directory tree (casillas, formulas, bindings, completeness_manifest,
    verification_expectations, extraction_profiles, application_links) under
    ``src/cadrumo/_data/registry/aeat/modelos/<modelo_id>/``. The revision
    manifest is emitted in edition-delta shape without manufacturing a legal
    predecessor claim. Applicability dates, filing year and periods are required.
    The tree is a skeleton only: it does not validate as calc-grade until a
    contributor fills in the contributor checklist (``python -m
    dev.registry.newmodelo checklist``), printed again below after a successful
    scaffold.
    """
    manager = (
        NewModeloScaffoldManager(registry_modelos_root=registry_modelos_root)
        if registry_modelos_root is not None
        else _default_manager()
    )
    try:
        result = manager.scaffold(
            modelo_id,
            revision_id,
            valid_from=_date(valid_from, option="--valid-from"),
            year_from=year_from,
            periods=tuple(period),
            valid_to=_date(valid_to, option="--valid-to") if valid_to is not None else None,
            title=title,
        )
    except NewModeloError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    _echo_result(result, mode="scaffold")
    typer.echo("")
    typer.echo(render_checklist())


@app.command("new-edition")
def new_edition(
    modelo_id: Annotated[str, typer.Argument(help="Existing three-digit AEAT modelo identifier.")],
    revision_id: Annotated[str, typer.Argument(help="New revision identifier.")],
    valid_from: Annotated[str, typer.Option("--valid-from", help="Grounded applicability start date (YYYY-MM-DD).")],
    year_from: Annotated[int, typer.Option("--year-from", help="First filing year selected by this revision.")],
    period: Annotated[list[str], typer.Option("--period", help="Applicable filing period; repeat as needed.")],
    valid_to: Annotated[
        str | None, typer.Option("--valid-to", help="Grounded applicability end date, if known.")
    ] = None,
    registry_modelos_root: Annotated[
        Path | None,
        typer.Option("--registry-modelos-root", help="Override the modelos root for isolated developer/test runs."),
    ] = None,
) -> None:
    """Add only a delta revision manifest to an existing authored modelo."""
    manager = (
        NewModeloScaffoldManager(registry_modelos_root=registry_modelos_root)
        if registry_modelos_root is not None
        else _default_manager()
    )
    try:
        result = manager.scaffold(
            modelo_id,
            revision_id,
            valid_from=_date(valid_from, option="--valid-from"),
            year_from=year_from,
            periods=tuple(period),
            valid_to=_date(valid_to, option="--valid-to") if valid_to is not None else None,
            existing_modelo=True,
        )
    except NewModeloError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    _echo_result(result, mode="scaffold")
    typer.echo(
        "Revision manifest created. Author only evidenced deltas; run independent registry checks before publication."
    )


@app.command("checklist")
def checklist() -> None:
    """Print the contributor checklist for taking a modelo revision calc-grade."""
    typer.echo(render_checklist())


__all__ = ["app"]
