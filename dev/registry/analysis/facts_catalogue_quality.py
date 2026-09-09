"""Catalogue-denominated structural gates for governed facts.

The gates consume fact providers and their compiled facts directly.  They do
not inspect ``ModeloRevision`` and therefore cannot alter the mature modelo
conformance denominator.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from pathlib import Path, PurePosixPath

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.facts.providers import (
    FACT_PROVIDER_REGISTRATIONS,
    FactProviderRegistration,
    validate_fact_provider_registrations,
)
from cadrumo.domain.calculations.registry.facts.schema import GovernedFact, GovernedFactVariant

__all__ = [
    "FactQualityFinding",
    "FactQualityKind",
    "facts_catalogue_findings",
    "live_facts_catalogue_findings",
    "main",
]


class FactQualityKind(StrEnum):
    """Closed finding vocabulary for the facts structural boundary."""

    DUPLICATE_FACT_ID = "duplicate_fact_id"
    DUPLICATE_VARIANT_ID = "duplicate_variant_id"
    INVALID_PRECEDENCE = "invalid_precedence"
    MISSING_PROVENANCE = "missing_provenance"
    TEMPORAL_AMBIGUITY = "temporal_ambiguity"
    UNOWNED_DIRECTORY = "unowned_directory"
    INVALID_PROVIDER = "invalid_provider"


@dataclass(frozen=True, slots=True, order=True)
class FactQualityFinding:
    """One deterministic structural defect in the facts catalogue."""

    kind: FactQualityKind
    provider_id: str
    fact_id: str = ""
    variant_id: str = ""
    detail: str = ""


def _selector_key(variant: GovernedFactVariant) -> tuple[tuple[str, str, str], ...]:
    return tuple(sorted((item.name, type(item.value).__name__, repr(item.value)) for item in variant.selectors))


def _overlap(left: GovernedFactVariant, right: GovernedFactVariant) -> bool:
    if left.date_axis != right.date_axis or _selector_key(left) != _selector_key(right):
        return False
    left_end = left.valid_to or date.max
    right_end = right.valid_to or date.max
    return left.valid_from <= right_end and right.valid_from <= left_end


def _reaches(start: str, target: str, edges: Mapping[str, tuple[str, ...]]) -> bool:
    pending = list(edges.get(start, ()))
    seen: set[str] = set()
    while pending:
        current = pending.pop()
        if current == target:
            return True
        if current not in seen:
            seen.add(current)
            pending.extend(edges.get(current, ()))
    return False


def _fact_findings(provider_id: str, fact: GovernedFact) -> list[FactQualityFinding]:
    findings: list[FactQualityFinding] = []
    edges = {variant.variant_id: variant.precedence_over for variant in fact.variants}
    for variant in fact.variants:
        if _reaches(variant.variant_id, variant.variant_id, edges):
            findings.append(
                FactQualityFinding(
                    FactQualityKind.INVALID_PRECEDENCE,
                    provider_id,
                    fact.fact_id,
                    variant.variant_id,
                    "precedence graph contains a cycle",
                )
            )
        cited = {citation.source_ref for citation in variant.source_citations}
        source_lane_declared = bool(variant.source_refs or variant.source_citations)
        source_lane_complete = bool(variant.source_refs) and cited == set(variant.source_refs)
        legal_lane_complete = bool(variant.legal_refs)
        if (source_lane_declared and not source_lane_complete) or (
            not source_lane_declared and not legal_lane_complete
        ):
            findings.append(
                FactQualityFinding(
                    FactQualityKind.MISSING_PROVENANCE,
                    provider_id,
                    fact.fact_id,
                    variant.variant_id,
                    "declare a legal_refs lane or a complete source_refs/source_citations lane",
                )
            )
    for index, left in enumerate(fact.variants):
        for right in fact.variants[index + 1 :]:
            overlaps = _overlap(left, right)
            ordered = _reaches(left.variant_id, right.variant_id, edges) or _reaches(
                right.variant_id, left.variant_id, edges
            )
            directly_ordered = (
                right.variant_id in edges[left.variant_id] or left.variant_id in edges[right.variant_id]
            )
            if overlaps and not ordered:
                findings.append(
                    FactQualityFinding(
                        FactQualityKind.TEMPORAL_AMBIGUITY,
                        provider_id,
                        fact.fact_id,
                        left.variant_id,
                        f"overlaps {right.variant_id!r} without explicit precedence",
                    )
                )
            elif directly_ordered and not overlaps:
                findings.append(
                    FactQualityFinding(
                        FactQualityKind.INVALID_PRECEDENCE,
                        provider_id,
                        fact.fact_id,
                        left.variant_id,
                        f"declares precedence with non-overlapping variant {right.variant_id!r}",
                    )
                )
    return findings


def facts_catalogue_findings(
    registrations: Iterable[FactProviderRegistration],
    facts_by_provider: Mapping[str, tuple[GovernedFact, ...]],
    governed_directories: Iterable[str],
) -> tuple[FactQualityFinding, ...]:
    """Return every provider, identity, precedence and provenance defect."""
    frozen = tuple(registrations)
    findings: list[FactQualityFinding] = []
    try:
        validate_fact_provider_registrations(frozen)
    except RegistryValidationError as error:
        findings.append(FactQualityFinding(FactQualityKind.INVALID_PROVIDER, "", detail=str(error)))

    ownership = {
        PurePosixPath(directory).as_posix(): registration.provider_id
        for registration in frozen
        for directory in registration.owned_directories
    }
    for directory in sorted(set(governed_directories)):
        if PurePosixPath(directory).as_posix() not in ownership:
            findings.append(
                FactQualityFinding(FactQualityKind.UNOWNED_DIRECTORY, "", detail=directory)
            )

    fact_owners: dict[str, str] = {}
    variant_owners: dict[str, tuple[str, str]] = {}
    registered_ids = {registration.provider_id for registration in frozen}
    for provider_id in sorted(registered_ids - set(facts_by_provider)):
        findings.append(
            FactQualityFinding(
                FactQualityKind.INVALID_PROVIDER,
                provider_id,
                detail="registered provider has no compiled facts result",
            )
        )
    for provider_id in sorted(facts_by_provider):
        if provider_id not in registered_ids:
            findings.append(
                FactQualityFinding(
                    FactQualityKind.INVALID_PROVIDER,
                    provider_id,
                    detail="compiled facts have no provider",
                )
            )
        for fact in facts_by_provider[provider_id]:
            if previous := fact_owners.get(fact.fact_id):
                findings.append(
                    FactQualityFinding(FactQualityKind.DUPLICATE_FACT_ID, provider_id, fact.fact_id, detail=previous)
                )
            else:
                fact_owners[fact.fact_id] = provider_id
            for variant in fact.variants:
                if previous_variant := variant_owners.get(variant.variant_id):
                    findings.append(
                        FactQualityFinding(
                            FactQualityKind.DUPLICATE_VARIANT_ID,
                            provider_id,
                            fact.fact_id,
                            variant.variant_id,
                            f"already owned by {previous_variant[0]}/{previous_variant[1]}",
                        )
                    )
                else:
                    variant_owners[variant.variant_id] = (provider_id, fact.fact_id)
            findings.extend(_fact_findings(provider_id, fact))
    return tuple(sorted(set(findings)))


def live_facts_catalogue_findings(
    registry_root: Path,
    registrations: Iterable[FactProviderRegistration] = FACT_PROVIDER_REGISTRATIONS,
) -> tuple[FactQualityFinding, ...]:
    """Compile every live registered provider and evaluate its owned directories."""
    frozen = tuple(registrations)
    compiled: dict[str, tuple[GovernedFact, ...]] = {}
    compile_findings: list[FactQualityFinding] = []
    for registration in frozen:
        try:
            compiled[registration.provider_id] = registration.compile(registry_root)
        except Exception as error:
            compile_findings.append(
                FactQualityFinding(
                    FactQualityKind.INVALID_PROVIDER,
                    registration.provider_id,
                    detail=f"compile failed: {type(error).__name__}: {error}",
                )
            )
    governed_directories = tuple(
        directory
        for registration in frozen
        for directory in registration.owned_directories
    )
    return tuple(
        sorted(
            {
                *compile_findings,
                *facts_catalogue_findings(frozen, compiled, governed_directories),
            }
        )
    )


def main(argv: list[str] | None = None) -> int:
    """Run the blocking live facts structural gate."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--registry-root", type=Path, default=bundled_path("registry", "aeat"))
    args = parser.parse_args(argv)
    findings = live_facts_catalogue_findings(args.registry_root)
    for finding in findings:
        sys.stdout.write(
            f"{finding.kind} provider={finding.provider_id} fact={finding.fact_id} "
            f"variant={finding.variant_id} detail={finding.detail}\n"
        )
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
