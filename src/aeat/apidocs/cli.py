"""Developer CLI for API documentation stub scaffolding and auditing."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from .manager import ApiStubManager

app = typer.Typer(
    name="apidocs",
    help="Maintain Sphinx automodule RST stubs under docs/api/.",
    no_args_is_help=True,
)


def _default_manager() -> ApiStubManager:
    # cli.py lives at src/aeat/apidocs/cli.py; parents[3] is the repo root.
    repo_root = Path(__file__).resolve().parents[3]
    return ApiStubManager(
        src_aeat=repo_root / "src" / "aeat",
        docs_api=repo_root / "docs" / "api",
    )


@app.command("scaffold")
def scaffold(
    check: Annotated[
        bool,
        typer.Option("--check", help="Check for drift without writing; exit non-zero on any drift."),
    ] = False,
) -> None:
    """Sync ``docs/api/*.rst`` stubs with the current ``src/aeat/`` module tree."""
    manager = _default_manager()
    if check:
        drift = manager.check()
        if drift.is_conformant:
            typer.echo("Stub tree is conformant. No drift detected.")
            return
        typer.echo(f"Drift detected: {len(drift.missing_stubs)} missing, {len(drift.orphan_stubs)} orphan.")
        if drift.missing_stubs:
            typer.echo("Missing stubs:")
            for name in drift.missing_stubs:
                typer.echo(f"  {name}")
        if drift.orphan_stubs:
            typer.echo("Orphan stubs:")
            for name in drift.orphan_stubs:
                typer.echo(f"  {name}")
        raise typer.Exit(code=1)

    result = manager.scaffold()
    typer.echo(f"Scaffolded {result.written} stubs, removed {result.removed} stale stubs.")
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
