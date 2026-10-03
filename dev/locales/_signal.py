"""Actionable canonical-key translation backlog coordinator."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from pathlib import Path

from dev._paths import REPO_ROOT

from .manager import (
    LocaleManager,
)
from .signal_contracts import LocaleSignal, LocaleSignalDetails
from .signal_discovery import discover_signal_catalogues, include_signal_namespace_keys, signal_catalogue_coverage
from .signal_domain_summary import domain_summaries, headline, largest_domain_locale, locale_summaries, next_action
from .signal_parallel_inventory import parallel_localization_inventory
from .signal_report import (
    signal_catalogue_only_cells,
    signal_dynamic_family_details,
    signal_findings,
    signal_finite_dynamic_keys,
    signal_translation_backlog,
)
from .signal_source_inventory import collect_source_inventory
from .signal_spelling import spellcheck_catalogues
from .signal_translation_matrix import translation_matrix


def _inventory_count(inventory: Mapping[str, object], key: str) -> int:
    """Read one integer inventory counter without widening arithmetic to object."""
    value = inventory.get(key, 0)
    return value if isinstance(value, int) else 0


def locale_signal(manager: LocaleManager, repository: Path = REPO_ROOT) -> LocaleSignal:
    """Build the known translation backlog and inventory-integrity findings."""
    (
        required_keys,
        discovery_findings,
        namespace_markers,
        finite_families,
        unresolved_families,
        locale_leaves,
        catalogue_findings,
    ) = discover_signal_catalogues(manager)
    include_signal_namespace_keys(required_keys, namespace_markers, finite_families, locale_leaves)
    parallel_values: dict[str, dict[str, str]] = defaultdict(dict)
    parallel_inventory, parallel_findings = parallel_localization_inventory(repository, spelling_values=parallel_values)
    spelling, spelling_inventory, spelling_findings = spellcheck_catalogues(
        required_keys, locale_leaves, repository, additional_values=parallel_values
    )
    matrix = translation_matrix(required_keys, locale_leaves, spelling)
    finite_dynamic_keys = signal_finite_dynamic_keys(finite_families)
    source_inventory, source_findings = collect_source_inventory(
        manager,
        dynamic_resolved_keys=finite_dynamic_keys,
    )
    inventory_findings = [*discovery_findings, *source_findings, *parallel_findings, *spelling_findings]
    matrix_findings = matrix["findings"]
    placeholder_mismatches = sum(
        finding.get("kind") == "translation_placeholder_mismatch" for finding in matrix_findings
    )
    invalid_placeholders = sum(
        finding.get("kind") in {"reserved_placeholder", "translation_invalid_placeholder"}
        for finding in matrix_findings
    )
    inventory_open = bool(
        discovery_findings
        or _source_signal_inventory_open(source_inventory)
        or _parallel_signal_inventory_open(parallel_inventory)
        or _spelling_signal_inventory_open(spelling_inventory)
        or unresolved_families
    )
    domains = domain_summaries(
        required_keys,
        matrix,
        locale_leaves,
        [*inventory_findings, *({"kind": "unbounded_key_family"} for _ in unresolved_families)],
    )
    locales = locale_summaries(required_keys, matrix, locale_leaves)
    backlog, translation_backlog = signal_translation_backlog(matrix, inventory_open)
    inventory_items = (
        _inventory_count(source_inventory, "invalid_tr_calls")
        + _inventory_count(source_inventory, "conflicting_duplicate_declarations")
        + _inventory_count(source_inventory, "naked_presentation_sites")
        + _inventory_count(source_inventory, "unread_or_invalid_sources")
        + _inventory_count(parallel_inventory, "parallel_localization_declarations")
        + _inventory_count(parallel_inventory, "invalid_data_files")
        + _inventory_count(parallel_inventory, "docs_extraction_failures")
        + _inventory_count(parallel_inventory, "docs_source_drift_pages")
        + _inventory_count(parallel_inventory, "docs_translation_source_echo")
        + _inventory_count(parallel_inventory, "docs_orphan_catalogue_files")
        + _inventory_count(parallel_inventory, "docs_missing_catalogue_files")
        + _inventory_count(parallel_inventory, "docs_generated_source_failures")
        + _inventory_count(spelling_inventory, "spelling_tool_failures")
        + _inventory_count(spelling_inventory, "spelling_unknown_cells")
        + len(unresolved_families)
        + len(discovery_findings)
    )
    largest = largest_domain_locale(domains)
    catalogue_key_cells, catalogue_keys_unique, catalogue_only_keys, catalogue_only_findings = (
        signal_catalogue_coverage(locale_leaves, required_keys)
    )
    summary = {
        "inventory": {
            "closed": not inventory_open,
            "key_discovery_failures": len(discovery_findings),
            "catalogue_key_declarations": catalogue_key_cells,
            "catalogue_keys_unique": catalogue_keys_unique,
            "catalogue_cross_locale_repetitions": catalogue_key_cells - catalogue_keys_unique,
            "catalogue_duplicate_declarations": source_inventory["conflicting_duplicate_declarations"],
            "tr_syntax_invalid": source_inventory["invalid_tr_calls"],
            "placeholder_mismatches": placeholder_mismatches,
            "invalid_placeholders": invalid_placeholders,
            **source_inventory,
            **parallel_inventory,
            **spelling_inventory,
            "required_keys": len(required_keys),
            "dynamic_key_families": len(namespace_markers),
            "finite_key_families": len(finite_families),
            "finite_dynamic_keys": len(finite_dynamic_keys),
            "unbounded_key_families": len(unresolved_families),
        },
        "translation_backlog": translation_backlog,
        "cells": matrix["cells"],
        "locales": locales,
        "domains": domains,
        "catalogue_only": {
            "keys": len(catalogue_only_keys),
            "cells": signal_catalogue_only_cells(locale_leaves, required_keys),
        },
        "next_action": next_action(
            inventory_open,
            inventory_items,
            matrix,
            domains,
            len(catalogue_only_keys),
        ),
    }
    findings = signal_findings(
        inventory_findings, catalogue_findings, required_keys, matrix, catalogue_only_findings, unresolved_families
    )
    dynamic_key_families = signal_dynamic_family_details(finite_families, unresolved_families, locale_leaves)
    details: LocaleSignalDetails = {
        "backlog": backlog,
        "findings": findings,
        "required_keys": sorted(required_keys),
        "dynamic_key_families": dynamic_key_families,
    }
    return {
        "outcome": "backlog" if findings else "complete",
        "headline": headline(translation_backlog, locales, largest, inventory_items),
        "summary": summary,
        "details": details,
    }


def _source_signal_inventory_open(source_inventory: Mapping[str, object]) -> bool:
    """Preserve short-circuit completeness checks for the source authority."""
    return bool(
        source_inventory["invalid_tr_calls"]
        or source_inventory["conflicting_duplicate_declarations"]
        or source_inventory["naked_presentation_sites"]
        or source_inventory["unread_or_invalid_sources"]
    )


def _parallel_signal_inventory_open(parallel_inventory: Mapping[str, object]) -> bool:
    """Preserve short-circuit completeness checks for the parallel authority."""
    return bool(
        parallel_inventory["parallel_localization_declarations"]
        or parallel_inventory["invalid_data_files"]
        or parallel_inventory["docs_extraction_failures"]
        or parallel_inventory["docs_source_drift_pages"]
        or parallel_inventory["docs_translation_source_echo"]
        or parallel_inventory["docs_orphan_catalogue_files"]
        or parallel_inventory["docs_missing_catalogue_files"]
        or parallel_inventory["docs_generated_source_failures"]
    )


def _spelling_signal_inventory_open(spelling_inventory: Mapping[str, object]) -> bool:
    """Preserve short-circuit completeness checks for the spelling authority."""
    return bool(spelling_inventory["spelling_tool_failures"] or spelling_inventory["spelling_unknown_cells"])
