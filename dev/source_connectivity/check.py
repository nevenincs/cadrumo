"""Monotonic checks over the reviewed source-connectivity census."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from cadrumo.application.registry.source_connectivity import load_source_connectivity_census

from .discovery import assign_capabilities_to_census, discovered_source_capability_ids


@dataclass(frozen=True, slots=True)
class SourceConnectivityCheckResult:
    """Successful census comparison counts for gates and operator reporting."""

    capability_count: int
    census_entry_count: int
    assignment_count: int


class SourceConnectivityCheckError(ValueError):
    """Live discovery added, removed, duplicated, or otherwise drifted from review."""


def check_capability_census(repo_root: Path) -> SourceConnectivityCheckResult:
    """Reject any live capability addition or unexplained reviewed disappearance."""
    capability_ids = discovered_source_capability_ids(repo_root)
    manifest = load_source_connectivity_census()
    try:
        assignments = assign_capabilities_to_census(capability_ids, manifest)
    except ValueError as error:
        raise SourceConnectivityCheckError(str(error)) from error
    return SourceConnectivityCheckResult(
        capability_count=len(capability_ids),
        census_entry_count=len(manifest.entries),
        assignment_count=sum(len(rows) for rows in assignments.values()),
    )


__all__ = [
    "SourceConnectivityCheckError",
    "SourceConnectivityCheckResult",
    "check_capability_census",
]
