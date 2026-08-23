"""Developer CLI for source-capability census generation and comparison.

This maintenance surface discovers facts from the live tree and compares them
with the reviewed bundled census.  It never authors or rewrites that authority.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from .check import (
    SourceConnectivityCheckError,
    SourceConnectivityCheckResult,
    check_capability_census,
)
from .discovery import discovered_source_capability_ids
from .live_proof import (
    ConnectedProofCompositionError,
    canonical_live_connected_proof_authority,
)

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


def project_census_memberships(
    result: SourceConnectivityCheckResult,
) -> tuple[dict[str, object], ...]:
    """Project deterministic per-capability ownership and reviewed evidence."""
    entries = {entry.candidate_id: entry for entry in result.manifest.entries}
    memberships: list[dict[str, object]] = []
    for candidate_id, capability_ids in result.assignments:
        entry = entries[candidate_id]
        decision_reason = entry.review_condition or entry.grounding[0].summary
        grounding_refs = tuple(item.reference for item in entry.grounding)
        memberships.extend(
            {
                "capability_id": capability_id,
                "candidate_id": candidate_id,
                "disposition": entry.disposition.value,
                "decision_reason": decision_reason,
                "grounding_refs": grounding_refs,
            }
            for capability_id in capability_ids
        )
    return tuple(sorted(memberships, key=lambda item: str(item["capability_id"])))


@app.command("generate")
def generate(repo_root: _RepoRoot = _DEFAULT_REPO_ROOT) -> None:
    """Emit deterministic live discovery facts without editing the census."""
    typer.echo(json.dumps(_generated_payload(repo_root), indent=2, sort_keys=True))


@app.command("compare")
def compare(repo_root: _RepoRoot = _DEFAULT_REPO_ROOT) -> None:
    """Compare live discovery with the canonical reviewed census and fail on drift."""
    try:
        with canonical_live_connected_proof_authority(repo_root) as proof_authority:
            result = check_capability_census(repo_root, proof_authority=proof_authority)
    except (ConnectedProofCompositionError, SourceConnectivityCheckError) as error:
        typer.echo(f"source-connectivity census mismatch: {error}", err=True)
        raise typer.Exit(code=1) from error
    typer.echo(
        json.dumps(
            {
                "schema_version": 1,
                "kind": "source-connectivity-comparison",
                "status": "match",
                "capability_count": result.capability_count,
                "census_entry_count": result.census_entry_count,
                "assignment_count": result.assignment_count,
                "memberships": project_census_memberships(result),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    app()
