"""Monotonic checks over the reviewed source-connectivity census."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from pydantic import ValidationError

from cadrumo.application.registry.source_connectivity import load_source_connectivity_census
from cadrumo.core import (
    SourceConnectivityDisposition,
    SourceConnectivityExpiryPosture,
    SourceConnectivityProofAuthority,
)

from .discovery import assign_capabilities_to_census, discovered_source_capability_ids


@dataclass(frozen=True, slots=True)
class SourceConnectivityCheckResult:
    """Successful census comparison counts for gates and operator reporting."""

    capability_count: int
    census_entry_count: int
    assignment_count: int


class SourceConnectivityCheckError(ValueError):
    """Live discovery added, removed, duplicated, or otherwise drifted from review."""


_UNRESOLVED_DISPOSITIONS = frozenset(
    {
        SourceConnectivityDisposition.CONNECT_CANDIDATE,
        SourceConnectivityDisposition.GROUNDING_BLOCKED,
        SourceConnectivityDisposition.INGRESS_BLOCKED,
        SourceConnectivityDisposition.REGISTRY_BLOCKED,
    }
)


def check_census_governance(manifest: object, *, as_of: date) -> None:
    """Reject stale blockers and unresolved rows without bounded accountability."""
    for row in manifest.entries:
        if row.disposition not in _UNRESOLVED_DISPOSITIONS:
            continue
        if not row.owner or row.bounded_follow_up is None or not row.follow_up_owner():
            raise SourceConnectivityCheckError(
                f"unresolved census row lacks owned bounded follow-up: {row.candidate_id}"
            )
        if row.expiry_posture(as_of=as_of) is SourceConnectivityExpiryPosture.EXPIRED:
            raise SourceConnectivityCheckError(
                f"blocked census row expired without adjudication: {row.candidate_id}"
            )


def check_capability_census(
    repo_root: Path,
    *,
    as_of: date | None = None,
    proof_authority: SourceConnectivityProofAuthority | None = None,
) -> SourceConnectivityCheckResult:
    """Reject capability drift, stale governance, and unsupported connections."""
    capability_ids = discovered_source_capability_ids(repo_root)
    try:
        manifest = load_source_connectivity_census(proof_authority=proof_authority)
    except ValidationError as error:
        raise SourceConnectivityCheckError(f"census claim failed live proof validation: {error}") from error
    check_census_governance(manifest, as_of=as_of or date.today())
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
    "check_census_governance",
]
