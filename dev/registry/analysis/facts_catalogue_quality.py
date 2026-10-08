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

from pydantic import TypeAdapter

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.core.toml import parse_toml
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.facts.resolution import (
    GovernedFactQuery,
    ResolvedGovernedFact,
    resolve_governed_fact,
)
from cadrumo.domain.calculations.registry.facts.schema import GovernedFact, GovernedFactCatalogue
from cadrumo.domain.calculations.registry.facts.variants import GovernedFactVariant
from cadrumo.domain.calculations.registry.schema import SupportedFilingYearsCatalogue
from dev._paths import REPO_ROOT

from ..compiler.fact_providers import (
    FACT_PROVIDER_REGISTRATIONS,
    FactProviderRegistration,
    compile_registered_fact_providers,
    validate_fact_provider_registrations,
)
from ..compiler.loader import load_registry_tree, load_shared_catalogues

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
#: The structured IVA tables allowed to remain until a lossless typed replacement lands.
_TABLE_HOLDS = frozenset(
    {
        "src/cadrumo/_data/registry/aeat/iva/catalogues.toml",
        "src/cadrumo/_data/registry/aeat/iva/place_of_supply.toml",
        "src/cadrumo/_data/registry/aeat/iva/territories.toml",
        "src/cadrumo/_data/registry/aeat/iva/territory_carve_outs.toml",
    }
)
#: The retirement lanes allowed to remain while a named blocker is pending.
_LANE_HOLDS = frozenset({"iva-local-grounding"})
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


def _overlap(fact: GovernedFact, left: GovernedFactVariant, right: GovernedFactVariant) -> bool:
    if left.date_axis != right.date_axis or _selector_key(left) != _selector_key(right):
        return False
    left_window = fact.validity_window(left)
    right_window = fact.validity_window(right)
    left_end = left_window.valid_to or date.max
    right_end = right_window.valid_to or date.max
    return left_window.valid_from <= right_end and right_window.valid_from <= left_end


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
    edges = {variant.variant_id: variant.precedence_over for variant in fact.variants}
    findings: list[FactQualityFinding] = []
    for variant in fact.variants:
        findings.extend(_variant_self_findings(provider_id, fact, variant, edges))
    findings.extend(_variant_pair_findings(provider_id, fact, edges))
    return findings


def _variant_self_findings(
    provider_id: str,
    fact: GovernedFact,
    variant: GovernedFactVariant,
    edges: Mapping[str, tuple[str, ...]],
) -> list[FactQualityFinding]:
    findings: list[FactQualityFinding] = []
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
    if _provenance_is_missing(variant):
        findings.append(
            FactQualityFinding(
                FactQualityKind.MISSING_PROVENANCE,
                provider_id,
                fact.fact_id,
                variant.variant_id,
                "declare a legal_refs lane or a complete source_refs/source_citations lane",
            )
        )
    return findings


def _provenance_is_missing(variant: GovernedFactVariant) -> bool:
    cited = {citation.source_ref for citation in variant.source_citations}
    source_lane_declared = bool(variant.source_refs or variant.source_citations)
    source_lane_complete = bool(variant.source_refs) and cited == set(variant.source_refs)
    return (source_lane_declared and not source_lane_complete) or (not source_lane_declared and not variant.legal_refs)


def _variant_pair_findings(
    provider_id: str,
    fact: GovernedFact,
    edges: Mapping[str, tuple[str, ...]],
) -> list[FactQualityFinding]:
    findings: list[FactQualityFinding] = []
    for index, left in enumerate(fact.variants):
        for right in fact.variants[index + 1 :]:
            finding = _variant_pair_finding(provider_id, fact, left, right, edges)
            if finding is not None:
                findings.append(finding)
    return findings


def _variant_pair_finding(
    provider_id: str,
    fact: GovernedFact,
    left: GovernedFactVariant,
    right: GovernedFactVariant,
    edges: Mapping[str, tuple[str, ...]],
) -> FactQualityFinding | None:
    overlaps = _overlap(fact, left, right)
    ordered = _reaches(left.variant_id, right.variant_id, edges) or _reaches(right.variant_id, left.variant_id, edges)
    directly_ordered = right.variant_id in edges[left.variant_id] or left.variant_id in edges[right.variant_id]
    if overlaps and not ordered:
        kind = FactQualityKind.TEMPORAL_AMBIGUITY
        detail = f"overlaps {right.variant_id!r} without explicit precedence"
    elif directly_ordered and not overlaps:
        kind = FactQualityKind.INVALID_PRECEDENCE
        detail = f"declares precedence with non-overlapping variant {right.variant_id!r}"
    else:
        return None
    return FactQualityFinding(kind, provider_id, fact.fact_id, left.variant_id, detail)


def facts_catalogue_findings(
    registrations: Iterable[FactProviderRegistration],
    facts_by_provider: Mapping[str, tuple[GovernedFact, ...]],
    governed_directories: Iterable[str],
) -> tuple[FactQualityFinding, ...]:
    """Return every provider, identity, precedence and provenance defect."""
    frozen = tuple(registrations)
    findings: list[FactQualityFinding] = []
    findings.extend(_provider_registration_findings(frozen))
    findings.extend(_unowned_directory_findings(frozen, governed_directories))
    findings.extend(_provider_result_findings(frozen, facts_by_provider))
    findings.extend(_catalogue_identity_findings(facts_by_provider))
    return tuple(sorted(set(findings)))


def _provider_registration_findings(registrations: tuple[FactProviderRegistration, ...]) -> list[FactQualityFinding]:
    try:
        validate_fact_provider_registrations(registrations)
    except RegistryValidationError as error:
        return [FactQualityFinding(FactQualityKind.INVALID_PROVIDER, "", detail=str(error))]
    return []


def _unowned_directory_findings(
    registrations: tuple[FactProviderRegistration, ...],
    governed_directories: Iterable[str],
) -> list[FactQualityFinding]:
    ownership = {
        PurePosixPath(directory).as_posix()
        for registration in registrations
        for directory in registration.owned_directories
    }
    return [
        FactQualityFinding(FactQualityKind.UNOWNED_DIRECTORY, "", detail=directory)
        for directory in sorted(set(governed_directories))
        if PurePosixPath(directory).as_posix() not in ownership
    ]


def _provider_result_findings(
    registrations: tuple[FactProviderRegistration, ...],
    facts_by_provider: Mapping[str, tuple[GovernedFact, ...]],
) -> list[FactQualityFinding]:
    registered_ids = {registration.provider_id for registration in registrations}
    missing = [
        FactQualityFinding(
            FactQualityKind.INVALID_PROVIDER,
            provider_id,
            detail="registered provider has no compiled facts result",
        )
        for provider_id in sorted(registered_ids - set(facts_by_provider))
    ]
    extra = [
        FactQualityFinding(
            FactQualityKind.INVALID_PROVIDER,
            provider_id,
            detail="compiled facts have no provider",
        )
        for provider_id in sorted(set(facts_by_provider) - registered_ids)
    ]
    return [*missing, *extra]


def _catalogue_identity_findings(
    facts_by_provider: Mapping[str, tuple[GovernedFact, ...]],
) -> list[FactQualityFinding]:
    findings: list[FactQualityFinding] = []
    fact_owners: dict[str, str] = {}
    variant_owners: dict[str, tuple[str, str]] = {}
    for provider_id in sorted(facts_by_provider):
        for fact in facts_by_provider[provider_id]:
            _append_fact_identity_findings(findings, fact_owners, variant_owners, provider_id, fact)
            findings.extend(_fact_findings(provider_id, fact))
    return findings


def _append_fact_identity_findings(
    findings: list[FactQualityFinding],
    fact_owners: dict[str, str],
    variant_owners: dict[str, tuple[str, str]],
    provider_id: str,
    fact: GovernedFact,
) -> None:
    previous = fact_owners.get(fact.fact_id)
    if previous:
        findings.append(
            FactQualityFinding(FactQualityKind.DUPLICATE_FACT_ID, provider_id, fact.fact_id, detail=previous)
        )
    else:
        fact_owners[fact.fact_id] = provider_id
    for variant in fact.variants:
        _append_variant_identity_finding(findings, variant_owners, provider_id, fact, variant)


def _append_variant_identity_finding(
    findings: list[FactQualityFinding],
    variant_owners: dict[str, tuple[str, str]],
    provider_id: str,
    fact: GovernedFact,
    variant: GovernedFactVariant,
) -> None:
    previous = variant_owners.get(variant.variant_id)
    if previous:
        findings.append(
            FactQualityFinding(
                FactQualityKind.DUPLICATE_VARIANT_ID,
                provider_id,
                fact.fact_id,
                variant.variant_id,
                f"already owned by {previous[0]}/{previous[1]}",
            )
        )
    else:
        variant_owners[variant.variant_id] = (provider_id, fact.fact_id)


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


def _resolved_variants(
    facts: Iterable[GovernedFact],
    support: SupportedFilingYearsCatalogue,
) -> tuple[ResolvedGovernedFact, ...]:
    """Resolve every declared variant at its first applicable coordinate through the real resolver."""
    frozen = tuple(facts)
    catalogue = GovernedFactCatalogue(facts={fact.fact_id: fact for fact in frozen})
    query_adapter = TypeAdapter(GovernedFactQuery)
    resolved: list[ResolvedGovernedFact] = []
    envelope = support.date_envelope()
    for fact in frozen:
        for variant in fact.variants:
            window = fact.validity_window(variant, envelope)
            effective_date = max(window.valid_from, envelope.floor)
            if (window.valid_to is not None and window.valid_to < effective_date) or not envelope.admits_coordinate(
                effective_date
            ):
                continue
            query = query_adapter.validate_python(
                {
                    "family": fact.family,
                    "fact_id": fact.fact_id,
                    "date_axis": variant.date_axis,
                    "effective_date": effective_date,
                    "selectors": variant.selectors,
                },
            )
            resolved.append(resolve_governed_fact(catalogue, query, authority_digest="0" * 64, support=support))
    return tuple(resolved)


def migration_retirement_findings(
    iva_ledger: Mapping[str, object],
    *,
    repository_root: Path = REPO_ROOT,
) -> tuple[FactQualityFinding, ...]:
    """Admit only complete, named temporary migration holds, and only while their subject exists.

    A hold is stale once the table it retains no longer exists: the replacement
    landed, and the ledger entry now describes nothing. A hold whose entry is
    absent is simply retired.
    """
    tables = _remaining_tables(iva_ledger, "remaining_structured_tables", "data_path")
    findings = _table_hold_findings(tables, repository_root)
    findings.extend(_technical_vocabulary_findings(tables))
    findings.extend(_unowned_table_findings(tables))
    findings.extend(_lane_hold_findings(iva_ledger))
    return tuple(sorted(set(findings)))


def _remaining_tables(iva_ledger: Mapping[str, object], key: str, id_key: str) -> dict[str, Mapping[str, object]]:
    raw_entries = iva_ledger.get(key)
    entries = raw_entries if isinstance(raw_entries, (list, tuple)) else ()
    return {str(entry.get(id_key, "")): entry for entry in entries if isinstance(entry, Mapping)}


def _table_hold_findings(tables: dict[str, Mapping[str, object]], repository_root: Path) -> list[FactQualityFinding]:
    findings: list[FactQualityFinding] = []
    for data_path in sorted(_TABLE_HOLDS):
        table = tables.pop(data_path, None)
        if table is None:
            continue
        if not (repository_root / data_path).is_file():
            findings.append(
                FactQualityFinding(
                    FactQualityKind.STALE_MIGRATION_HOLD,
                    "iva-retirement",
                    detail=f"hold {data_path!r} remains after its table was retired",
                )
            )
            continue
        if not _table_hold_is_complete(table):
            findings.append(
                FactQualityFinding(
                    FactQualityKind.UNAPPROVED_MIGRATION_HOLD,
                    "iva-retirement",
                    detail=f"hold {data_path!r} lacks its lossless-replacement contract",
                )
            )
    return findings


def _table_hold_is_complete(table: Mapping[str, object]) -> bool:
    return (
        table.get("classification") == "needs_typed_schema_and_fact_migration"
        and table.get("decision") == "retain_until_lossless_replacement"
        and bool(table.get("direct_readers"))
        and bool(table.get("safe_next_scope"))
    )


def _technical_vocabulary_findings(tables: dict[str, Mapping[str, object]]) -> list[FactQualityFinding]:
    technical = tables.pop(_TECHNICAL_IVA_VOCABULARY, None)
    if technical is not None and technical.get("classification") == "technical_non_legal_canonical_vocabulary":
        return []
    return [
        FactQualityFinding(
            FactQualityKind.UNAPPROVED_MIGRATION_HOLD,
            "iva-retirement",
            detail="country_names.toml must remain the explicitly technical IVA vocabulary",
        )
    ]


def _unowned_table_findings(tables: Mapping[str, Mapping[str, object]]) -> list[FactQualityFinding]:
    return [
        FactQualityFinding(
            FactQualityKind.UNAPPROVED_MIGRATION_HOLD,
            "iva-retirement",
            detail=f"unowned remaining IVA table {data_path!r}",
        )
        for data_path in sorted(tables)
    ]


def _lane_hold_findings(iva_ledger: Mapping[str, object]) -> list[FactQualityFinding]:
    lanes = _remaining_tables(iva_ledger, "lanes", "lane_id")
    lanes = {lane_id: lane for lane_id, lane in lanes.items() if "status" in lane}
    findings: list[FactQualityFinding] = []
    for lane_id in sorted(_LANE_HOLDS):
        lane = lanes.pop(lane_id, None)
        if lane is not None and (
            not str(lane.get("status", "")).startswith("blocked_pending") or not lane.get("blocker")
        ):
            findings.append(
                FactQualityFinding(
                    FactQualityKind.UNAPPROVED_MIGRATION_HOLD,
                    "iva-retirement",
                    detail=f"hold {lane_id!r} lacks a named pending blocker",
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
    return findings


def live_facts_catalogue_findings(
    registry_root: Path,
    registrations: Iterable[FactProviderRegistration] = FACT_PROVIDER_REGISTRATIONS,
) -> tuple[FactQualityFinding, ...]:
    """Compile every live registered provider and evaluate its owned directories."""
    frozen = tuple(registrations)
    compiled, compile_findings = _compile_live_providers(frozen, registry_root)
    governed_directories = tuple(directory for registration in frozen for directory in registration.owned_directories)
    support = load_shared_catalogues(registry_root).require_supported_filing_years()
    resolved_findings = _resolved_provenance_findings(frozen, registry_root, compiled, support)
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
    iva_ledger = parse_toml(_IVA_RETIREMENT_LEDGER.read_text(encoding="utf-8"))
    findings = (
        *live_facts_catalogue_findings(args.registry_root),
        *migration_retirement_findings(iva_ledger),
    )
    for finding in findings:
        sys.stdout.write(
            f"{finding.kind} provider={finding.provider_id} fact={finding.fact_id} "
            f"variant={finding.variant_id} detail={finding.detail}\n"
        )
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())


def _compile_live_providers(
    registrations: tuple[FactProviderRegistration, ...], registry_root: Path
) -> tuple[dict[str, tuple[GovernedFact, ...]], list[FactQualityFinding]]:
    compiled: dict[str, tuple[GovernedFact, ...]] = {}
    failures: list[FactQualityFinding] = []
    for registration in registrations:
        try:
            compiled[registration.provider_id] = registration.compile(registry_root)
        except Exception as error:
            failures.append(
                FactQualityFinding(
                    FactQualityKind.INVALID_PROVIDER,
                    registration.provider_id,
                    detail=f"compile failed: {type(error).__name__}: {error}",
                )
            )
    return compiled, failures


def _resolved_provenance_findings(
    registrations: tuple[FactProviderRegistration, ...],
    registry_root: Path,
    compiled: Mapping[str, tuple[GovernedFact, ...]],
    support: SupportedFilingYearsCatalogue,
) -> tuple[FactQualityFinding, ...]:
    if not any(registration.project_modelos is not None for registration in registrations):
        return resolved_fact_provenance_findings(
            resolved for facts in compiled.values() for resolved in _resolved_variants(facts, support)
        )
    try:
        modelos, _catalogues = load_registry_tree(registry_root)
        provenance_facts = compile_registered_fact_providers(registry_root, modelos=modelos).facts.values()
        return resolved_fact_provenance_findings(resolved for resolved in _resolved_variants(provenance_facts, support))
    except Exception as error:
        return (
            FactQualityFinding(
                FactQualityKind.INVALID_PROVIDER,
                "facts-provenance-resolution",
                detail=f"compiled projection provenance failed: {type(error).__name__}: {error}",
            ),
        )
