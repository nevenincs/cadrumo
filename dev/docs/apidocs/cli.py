"""Developer CLI for API documentation stub scaffolding and auditing."""

from __future__ import annotations

from typing import Annotated

import typer

from ..._paths import REPO_ROOT
from .manager import ApiStubManager

app = typer.Typer(
    name="apidocs",
    help="Maintain Sphinx automodule RST stubs under docs/api/.",
    no_args_is_help=True,
)


def _default_manager() -> ApiStubManager:
    # cli.py lives at dev/docs/apidocs/cli.py; parents[3] is the repo root.
    repo_root = REPO_ROOT
    return ApiStubManager(
        src_cadrumo=repo_root / "src" / "cadrumo",
        docs_api=repo_root / "docs" / "api",
    )


@app.command("scaffold")
def scaffold(
    check: Annotated[
        bool,
        typer.Option("--check", help="Check for drift without writing; exit non-zero on any drift."),
    ] = False,
) -> None:
    """Sync ``docs/api/*.rst`` stubs with the current ``src/cadrumo/`` module tree."""
    manager = _default_manager()
    if check:
        drift = manager.check()
        if drift.is_conformant:
            typer.echo("Stub tree is conformant. No drift detected.")
            return
        typer.echo(
            "Drift detected: "
            f"{len(drift.missing_stubs)} missing, "
            f"{len(drift.orphan_stubs)} orphan, "
            f"{len(drift.stale_stubs)} stale.",
        )
        if drift.missing_stubs:
            typer.echo("Missing stubs:")
            for name in drift.missing_stubs:
                typer.echo(f"  {name}")
        if drift.orphan_stubs:
            typer.echo("Orphan stubs:")
            for name in drift.orphan_stubs:
                typer.echo(f"  {name}")
        if drift.stale_stubs:
            typer.echo("Stale stubs:")
            for name in drift.stale_stubs:
                typer.echo(f"  {name}")
        raise typer.Exit(code=1)

    result = manager.scaffold()
    typer.echo(
        f"Scaffolded {result.written} changed stubs, "
        f"left {result.unchanged} unchanged, removed {result.removed} stale stubs.",
    )
    if result.removed_names:
        typer.echo("Removed stale stubs:")
        for name in result.removed_names:
            typer.echo(f"  {name}")


@app.command("audit")
def audit() -> None:
    """Print a health report for the docs/api/ stub tree."""
    manager = _default_manager()
    typer.echo(manager.audit())
    drift = manager.check()
    if not drift.is_conformant:
        raise typer.Exit(code=1)


__all__ = ["app"]
