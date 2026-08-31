"""Monotonic checks over the reviewed source-connectivity census."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from pydantic import ValidationError

from cadrumo.application.registry.source_connectivity import (
    SourceConnectivityCensusManifest,
    load_source_connectivity_census,
    validate_census_destination_candidates,
)
from cadrumo.application.registry.source_connectivity_authority import LiveSourceConnectivityProofAuthority
from cadrumo.core.source_connectivity import (
    SourceConnectivityDisposition,
    SourceConnectivityExpiryPosture,
    SourceConnectivityProofAuthority,
)
from cadrumo.domain.calculations.registry.authority import bundled_authority

from .discovery import (
    assign_capabilities_to_census,
    discovered_source_capability_evidence,
    discovered_source_capability_ids,
)


@dataclass(frozen=True, slots=True)
class SourceConnectivityCheckResult:
    """Successful census comparison counts for gates and operator reporting."""

    capability_count: int
    census_entry_count: int
    assignment_count: int
    assignments: tuple[tuple[str, tuple[str, ...]], ...]
    manifest: SourceConnectivityCensusManifest


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


def check_census_governance(manifest: SourceConnectivityCensusManifest, *, as_of: date) -> None:
    """Reject stale blockers and unresolved rows without bounded accountability."""
    for row in manifest.entries:
        if row.disposition not in _UNRESOLVED_DISPOSITIONS:
            continue
        if not row.owner or row.bounded_follow_up is None or not row.follow_up_owner():
            raise SourceConnectivityCheckError(
                f"unresolved census row lacks owned bounded follow-up: {row.candidate_id}"
            )
        if row.expiry_posture(as_of=as_of) is SourceConnectivityExpiryPosture.EXPIRED:
            raise SourceConnectivityCheckError(f"blocked census row expired without adjudication: {row.candidate_id}")


def check_capability_locators(
    repo_root: Path,
    manifest: SourceConnectivityCensusManifest,
    *,
    capability_evidence: Mapping[str, str] | None = None,
) -> None:
    """Require reviewed locators to re-fetch and explicit IDs to retain correspondence."""
    evidence_by_id = capability_evidence or discovered_source_capability_evidence(repo_root)
    for row in manifest.entries:
        for locator in row.capability_locators:
            relative_path, separator, line_text = locator.rpartition(":")
            has_line = bool(separator and line_text.isdigit())
            path = repo_root / (relative_path if has_line else locator)
            if not path.is_file():
                raise SourceConnectivityCheckError(
                    f"census capability locator is not re-fetchable: {row.candidate_id}: {locator}"
                )
            if has_line:
                line_count = sum(1 for _ in path.open(encoding="utf-8"))
                if not 1 <= int(line_text) <= line_count:
                    raise SourceConnectivityCheckError(
                        f"census capability locator line is absent: {row.candidate_id}: {locator}"
                    )
        for capability_id in row.capability_ids:
            expected = evidence_by_id.get(capability_id)
            if expected is None or expected not in row.capability_locators:
                raise SourceConnectivityCheckError(
                    f"census capability locator drift for {row.candidate_id}: "
                    f"{capability_id} now resolves to {expected!r}"
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
    if isinstance(proof_authority, LiveSourceConnectivityProofAuthority):
        for row in manifest.entries:
            if row.disposition is not SourceConnectivityDisposition.CONNECTED:
                continue
            proof = row.connected_proof
            if proof is None or not proof_authority.destinations_match(
                proof.connection,
                tuple(candidate.identity for candidate in row.registry_destination_candidates),
            ):
                raise SourceConnectivityCheckError(
                    f"connected census destinations do not match independent proof fixture: {row.candidate_id}"
                )
    try:
        validate_census_destination_candidates(manifest, bundled_authority())
    except ValueError as error:
        raise SourceConnectivityCheckError(str(error)) from error
    check_census_governance(manifest, as_of=as_of or date.today())
    check_capability_locators(repo_root, manifest)
    try:
        assignments = assign_capabilities_to_census(capability_ids, manifest)
    except ValueError as error:
        raise SourceConnectivityCheckError(str(error)) from error
    return SourceConnectivityCheckResult(
        capability_count=len(capability_ids),
        census_entry_count=len(manifest.entries),
        assignment_count=sum(len(rows) for rows in assignments.values()),
        assignments=tuple(sorted(assignments.items())),
        manifest=manifest,
    )


__all__ = [
    "SourceConnectivityCheckError",
    "SourceConnectivityCheckResult",
    "check_capability_census",
    "check_capability_locators",
    "check_census_governance",
]
