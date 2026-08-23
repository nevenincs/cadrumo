"""Developer CLI for source-capability census generation and comparison.

This maintenance surface discovers facts from the live tree and compares them
with the reviewed bundled census.  It never authors or rewrites that authority.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from cadrumo.application.registry.source_connectivity import load_source_connectivity_census

from .discovery import assign_capabilities_to_census, discovered_source_capability_ids

app = typer.Typer(
    name="source-connectivity",
    help="Generate live source-capability facts and compare them with the reviewed census.",
    no_args_is_help=True,
)
_DEFAULT_REPO_ROOT = Path.cwd()

_RepoRoot = Annotated[
    Path,
    typer.Option(
        "--repo-root",
        exists=True,
        file_okay=False,
        resolve_path=True,
        help="Repository root to discover. Defaults to the current working directory.",
    ),
]


def _generated_payload(repo_root: Path) -> dict[str, object]:
    capability_ids = discovered_source_capability_ids(repo_root)
    return {
        "schema_version": 1,
        "kind": "source-connectivity-discovery",
        "capability_count": len(capability_ids),
        "capability_ids": capability_ids,
    }


@app.command("generate")
def generate(repo_root: _RepoRoot = _DEFAULT_REPO_ROOT) -> None:
    """Emit deterministic live discovery facts without editing the census."""
    typer.echo(json.dumps(_generated_payload(repo_root), indent=2, sort_keys=True))


@app.command("compare")
def compare(repo_root: _RepoRoot = _DEFAULT_REPO_ROOT) -> None:
    """Compare live discovery with the canonical reviewed census and fail on drift."""
    capability_ids = discovered_source_capability_ids(repo_root)
    manifest = load_source_connectivity_census()
    try:
        assignments = assign_capabilities_to_census(capability_ids, manifest)
    except ValueError as error:
        typer.echo(f"source-connectivity census mismatch: {error}", err=True)
        raise typer.Exit(code=1) from error
    typer.echo(
        json.dumps(
            {
                "schema_version": 1,
                "kind": "source-connectivity-comparison",
                "status": "match",
                "capability_count": len(capability_ids),
                "census_entry_count": len(manifest.entries),
                "assignment_count": sum(len(rows) for rows in assignments.values()),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    app()
