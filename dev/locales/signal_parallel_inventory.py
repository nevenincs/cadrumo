"""Parallel localization audit coordinator."""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

from .signal_documentation_inventory import documentation_source_inventory
from .signal_parallel_findings import data_finding
from .signal_parallel_gettext import inventory_parallel_po_sources
from .signal_parallel_toml import inventory_parallel_toml_sources


def parallel_localization_inventory(
    repository: Path,
    *,
    spelling_values: dict[str, dict[str, str]] | None = None,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    """Reconcile TOML and gettext localization surfaces with current document sources."""
    counts = Counter[str]()
    findings: list[dict[str, object]] = []
    data_root = repository / "src" / "cadrumo" / "_data"
    inventory_parallel_toml_sources(data_root, repository, counts, findings, spelling_values)

    docs_root = repository / "docs" / "locales"
    docs_messages: dict[tuple[str, str], dict[str, bool]] = defaultdict(dict)
    docs_translations: dict[tuple[str, str], dict[str, tuple[str, ...]]] = defaultdict(dict)
    docs_obsolete: dict[tuple[str, str], set[str]] = defaultdict(set)
    docs_catalogue_files: set[tuple[str, str]] = set()
    inventory_parallel_po_sources(
        docs_root,
        repository,
        counts,
        findings,
        docs_catalogue_files,
        docs_messages,
        docs_translations,
        docs_obsolete,
        spelling_values,
    )
    for (catalogue, message_id), states in docs_messages.items():
        for locale in ("ca", "es", "hu"):
            if states.get(locale):
                continue
            counts["parallel_localization_declarations"] += 1
            findings.append(
                data_finding(
                    "docs_translation_missing", docs_root / locale / "LC_MESSAGES" / catalogue, message_id, locale
                )
            )
    docs_inventory, docs_findings = documentation_source_inventory(
        repository,
        docs_messages,
        catalogue_files=docs_catalogue_files,
        catalogue_obsolete=docs_obsolete,
        catalogue_translations=docs_translations,
        spelling_values=spelling_values,
    )
    findings.extend(docs_findings)
    return {
        "parallel_localization_declarations": counts["parallel_localization_declarations"],
        "parallel_localization_cells": counts["parallel_localization_cells"],
        "invalid_data_files": counts["invalid_data_files"],
        "docs_catalogues_compiled": counts["docs_catalogues_compiled"],
        **{
            f"docs_catalogues_compiled_{locale}": counts[f"docs_catalogues_compiled_{locale}"]
            for locale in ("ca", "es", "hu")
        },
        **docs_inventory,
    }, findings
