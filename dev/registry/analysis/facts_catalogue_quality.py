"""Catalogue-denominated structural gates for governed facts.

The gates consume fact providers and their compiled facts directly.  They do
not inspect ``ModeloRevision`` and therefore cannot alter the mature modelo
conformance denominator.
"""

from __future__ import annotations

import argparse
import re
import sys
import tomllib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from pathlib import Path, PurePosixPath

from pydantic import TypeAdapter

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.facts.resolution import (
    GovernedFactQuery,
    ResolvedGovernedFact,
    resolve_governed_fact,
)
from cadrumo.domain.calculations.registry.facts.schema import GovernedFact, GovernedFactCatalogue, GovernedFactVariant
from dev._paths import REPO_ROOT
from dev.registry.compiler.fact_providers import (
    FACT_PROVIDER_REGISTRATIONS,
    FactProviderRegistration,
    compile_registered_fact_providers,
    validate_fact_provider_registrations,
)
from dev.registry.compiler.loader import load_registry_tree

__all__ = [
    "FactQualityFinding",
    "FactQualityKind",
    "facts_catalogue_findings",
    "live_facts_catalogue_findings",
    "main",
    "migration_retirement_findings",
    "resolved_fact_provenance_findings",
]


_IVA_RETIREMENT_LEDGER = REPO_ROOT / "dev" / "registry" / "analysis" / "facts_iva_retirement.toml"
_FACTS_REGISTRY_PLAN = REPO_ROOT / ".vault" / "plan" / "2026-09-09-facts-registry-plan.md"
_S80_TEMPORARY_HOLD_STEPS = {
    "src/cadrumo/_data/registry/aeat/iva/catalogues.toml": "W04.P15.S81",
    "src/cadrumo/_data/registry/aeat/iva/place_of_supply.toml": "W04.P15.S82",
    "src/cadrumo/_data/registry/aeat/iva/territories.toml": "W04.P15.S83",
    "src/cadrumo/_data/registry/aeat/iva/territory_carve_outs.toml": "W04.P15.S84",
}
_S85_TEMPORARY_HOLD_STEPS = {"iva-local-grounding": "W04.P17.S85"}
_TECHNICAL_IVA_VOCABULARY = "src/cadrumo/_data/registry/aeat/iva/country_names.toml"


class FactQualityKind(StrEnum):
    """Closed finding vocabulary for the facts structural boundary."""

    DUPLICATE_FACT_ID = "duplicate_fact_id"
    DUPLICATE_VARIANT_ID = "duplicate_variant_id"
    INVALID_PRECEDENCE = "invalid_precedence"
    MISSING_PROVENANCE = "missing_provenance"
    PROVENANCE_FREE_RESULT = "provenance_free_result"
    UNAPPROVED_MIGRATION_HOLD = "unapproved_migration_hold"
    STALE_MIGRATION_HOLD = "stale_migration_hold"
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
            directly_ordered = right.variant_id in edges[left.variant_id] or left.variant_id in edges[right.variant_id]
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
            findings.append(FactQualityFinding(FactQualityKind.UNOWNED_DIRECTORY, "", detail=directory))

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


def resolved_fact_provenance_findings(results: Iterable[ResolvedGovernedFact]) -> tuple[FactQualityFinding, ...]:
    """Reject an applicable resolved fact result that lost its legal/source evidence."""
    findings: list[FactQualityFinding] = []
    for result in results:
        is_applicable = result.effective_date >= result.valid_from and (
            result.valid_to is None or result.effective_date <= result.valid_to
        )
        if is_applicable and not result.legal_refs and not result.source_refs:
            findings.append(
                FactQualityFinding(
                    FactQualityKind.PROVENANCE_FREE_RESULT,
                    "resolved-authority",
                    result.fact_id,
                    result.variant_id,
                    "applicable governed result carries neither legal_refs nor source_refs",
                )
            )
    return tuple(sorted(set(findings)))


def _resolved_variants(facts: Iterable[GovernedFact]) -> tuple[ResolvedGovernedFact, ...]:
    """Resolve every declared variant at its first applicable coordinate through the real resolver."""
    frozen = tuple(facts)
    catalogue = GovernedFactCatalogue(facts={fact.fact_id: fact for fact in frozen})
    query_adapter = TypeAdapter(GovernedFactQuery)
    resolved: list[ResolvedGovernedFact] = []
    for fact in frozen:
        for variant in fact.variants:
            query = query_adapter.validate_python(
                {
                    "family": fact.family,
                    "fact_id": fact.fact_id,
                    "date_axis": variant.date_axis,
                    "effective_date": variant.valid_from,
                    "selectors": variant.selectors,
                },
            )
            resolved.append(resolve_governed_fact(catalogue, query, authority_digest="0" * 64))
    return tuple(resolved)


def _open_plan_steps(plan_text: str) -> frozenset[str]:
    """Return the exact open step ids from the active facts-registry plan."""
    return frozenset(re.findall(r"^- \[ \] `([^`]+)`", plan_text, flags=re.MULTILINE))


def migration_retirement_findings(
    iva_ledger: Mapping[str, object],
    *,
    open_steps: Iterable[str],
) -> tuple[FactQualityFinding, ...]:
    """Admit only complete, named S80/S85 temporary migration holds while their steps remain open."""
    open_step_ids = frozenset(open_steps)
    findings: list[FactQualityFinding] = []
    tables = {
        str(table.get("data_path", "")): table
        for table in iva_ledger.get("remaining_structured_tables", ())
        if isinstance(table, Mapping)
    }
    for data_path, step_id in _S80_TEMPORARY_HOLD_STEPS.items():
        table = tables.pop(data_path, None)
        if table is None:
            if step_id in open_step_ids:
                findings.append(
                    FactQualityFinding(
                        FactQualityKind.STALE_MIGRATION_HOLD,
                        "iva-retirement",
                        detail=f"approved S80 hold {data_path!r} is absent while {step_id} remains open",
                    )
                )
            continue
        if step_id not in open_step_ids:
            findings.append(
                FactQualityFinding(
                    FactQualityKind.STALE_MIGRATION_HOLD,
                    "iva-retirement",
                    detail=f"S80 hold {data_path!r} remains after {step_id} closed",
                )
            )
            continue
        complete = (
            table.get("classification") == "needs_typed_schema_and_fact_migration"
            and table.get("decision") == "retain_until_lossless_replacement"
            and bool(table.get("direct_readers"))
            and bool(table.get("safe_next_scope"))
        )
        if not complete:
            findings.append(
                FactQualityFinding(
                    FactQualityKind.UNAPPROVED_MIGRATION_HOLD,
                    "iva-retirement",
                    detail=f"S80 hold {data_path!r} lacks its lossless-replacement contract",
                )
            )
    technical = tables.pop(_TECHNICAL_IVA_VOCABULARY, None)
    if technical is None or technical.get("classification") != "technical_non_legal_canonical_vocabulary":
        findings.append(
            FactQualityFinding(
                FactQualityKind.UNAPPROVED_MIGRATION_HOLD,
                "iva-retirement",
                detail="country_names.toml must remain the explicitly technical IVA vocabulary",
            )
        )
    for data_path in sorted(tables):
        findings.append(
            FactQualityFinding(
                FactQualityKind.UNAPPROVED_MIGRATION_HOLD,
                "iva-retirement",
                detail=f"unowned remaining IVA table {data_path!r}",
            )
        )

    lanes = {
        str(lane.get("lane_id", "")): lane
        for lane in iva_ledger.get("lanes", ())
        if isinstance(lane, Mapping) and "status" in lane
    }
    for lane_id, step_id in _S85_TEMPORARY_HOLD_STEPS.items():
        lane = lanes.pop(lane_id, None)
        if lane is None:
            if step_id in open_step_ids:
                findings.append(
                    FactQualityFinding(
                        FactQualityKind.STALE_MIGRATION_HOLD,
                        "iva-retirement",
                        detail=f"approved S85 hold {lane_id!r} is absent while {step_id} remains open",
                    )
                )
            continue
        if step_id not in open_step_ids:
            findings.append(
                FactQualityFinding(
                    FactQualityKind.STALE_MIGRATION_HOLD,
                    "iva-retirement",
                    detail=f"S85 hold {lane_id!r} remains after {step_id} closed",
                )
            )
            continue
        if not str(lane.get("status", "")).startswith("blocked_pending") or not lane.get("blocker"):
            findings.append(
                FactQualityFinding(
                    FactQualityKind.UNAPPROVED_MIGRATION_HOLD,
                    "iva-retirement",
                    detail=f"S85 hold {lane_id!r} lacks a named pending blocker",
                )
            )
    for lane_id in sorted(lanes):
        findings.append(
            FactQualityFinding(
                FactQualityKind.UNAPPROVED_MIGRATION_HOLD,
                "iva-retirement",
                detail=f"unowned pending retirement lane {lane_id!r}",
            )
        )
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
    governed_directories = tuple(directory for registration in frozen for directory in registration.owned_directories)
    if any(registration.project_modelos is not None for registration in frozen):
        try:
            modelos, _catalogues = load_registry_tree(registry_root)
            provenance_facts = compile_registered_fact_providers(registry_root, modelos=modelos).facts.values()
            resolved_findings = resolved_fact_provenance_findings(
                resolved for resolved in _resolved_variants(provenance_facts)
            )
        except Exception as error:
            resolved_findings = (
                FactQualityFinding(
                    FactQualityKind.INVALID_PROVIDER,
                    "facts-provenance-resolution",
                    detail=f"compiled projection provenance failed: {type(error).__name__}: {error}",
                ),
            )
    else:
        resolved_findings = resolved_fact_provenance_findings(
            resolved for facts in compiled.values() for resolved in _resolved_variants(facts)
        )
    return tuple(
        sorted(
            {
                *compile_findings,
                *facts_catalogue_findings(frozen, compiled, governed_directories),
                *resolved_findings,
            }
        )
    )


def main(argv: list[str] | None = None) -> int:
    """Run the blocking live facts structural gate."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--registry-root", type=Path, default=bundled_path("registry", "aeat"))
    args = parser.parse_args(argv)
    iva_ledger = tomllib.loads(_IVA_RETIREMENT_LEDGER.read_text(encoding="utf-8"))
    open_steps = _open_plan_steps(_FACTS_REGISTRY_PLAN.read_text(encoding="utf-8"))
    findings = (
        *live_facts_catalogue_findings(args.registry_root),
        *migration_retirement_findings(iva_ledger, open_steps=open_steps),
    )
    for finding in findings:
        sys.stdout.write(
            f"{finding.kind} provider={finding.provider_id} fact={finding.fact_id} "
            f"variant={finding.variant_id} detail={finding.detail}\n"
        )
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
