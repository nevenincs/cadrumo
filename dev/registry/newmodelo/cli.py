"""Developer CLI for scaffolding a new modelo's registry authoring tree."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from ..._paths import REPO_ROOT
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
    title: Annotated[
        str | None,
        typer.Option("--title", help="Working title for the manifest.toml placeholder."),
    ] = None,
    check: Annotated[
        bool,
        typer.Option("--check", help="Report missing skeleton files without writing anything; exit non-zero on drift."),
    ] = False,
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            help=(
                "Overwrite already-present skeleton files with fresh placeholder content, and "
                "bypass the foreign-manifest guard that otherwise refuses to scaffold onto a "
                "modelo directory whose manifest.toml is real registry content this scaffold "
                "did not author."
            ),
        ),
    ] = False,
    registry_modelos_root: Annotated[
        Path | None,
        typer.Option(
            "--registry-modelos-root",
            help="Override the registry modelos root; intended for isolated developer/test runs.",
        ),
    ] = None,
) -> None:
    """Scaffold (or check) the skeleton registry tree for MODELO_ID / REVISION_ID.

    Writes ``manifest.toml`` and a ``revisions/<revision_id>/`` fragment
    directory tree (casillas, formulas, bindings, completeness_manifest,
    verification_expectations, export_layouts, extraction_profiles,
    application_links) under
    ``src/cadrumo/_data/registry/aeat/modelos/<modelo_id>/``. The tree is a
    skeleton only: it does not validate as calc-grade until a contributor
    fills in the 12-item checklist (``python -m dev.registry.newmodelo
    checklist``), printed again below after a successful scaffold.
    """
    manager = (
        NewModeloScaffoldManager(registry_modelos_root=registry_modelos_root)
        if registry_modelos_root is not None
        else _default_manager()
    )
    try:
        if check:
            result = manager.check(modelo_id, revision_id, title=title)
            _echo_result(result, mode="check")
            if not result.is_conformant:
                raise typer.Exit(code=1)
            typer.echo("Skeleton is conformant. No missing files.")
            return

        result = manager.scaffold(modelo_id, revision_id, title=title, force=force)
    except NewModeloError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    _echo_result(result, mode="scaffold")
    typer.echo("")
    typer.echo(render_checklist())


@app.command("checklist")
def checklist() -> None:
    """Print the 12-item contributor checklist for taking a modelo revision calc-grade."""
    typer.echo(render_checklist())


__all__ = ["app"]
