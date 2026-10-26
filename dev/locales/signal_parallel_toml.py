"""Parallel toml for the authoritative locale audit."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from pathlib import Path

from cadrumo.core.toml import TomlDecodeError, load_toml

from .signal_parallel_findings import data_finding
from .signal_policy import LANGUAGE_CORE_FIELDS, LOCALES


def inventory_toml_suffix_translations(
    payload: dict[str, object],
    path: Path,
    repository: Path,
    counts: Counter[str],
    findings: list[dict[str, object]],
    spelling_values: dict[str, dict[str, str]] | None,
) -> None:
    """Inventory toml suffix translations."""
    suffix_groups: dict[str, set[str]] = defaultdict(set)
    for dotted, value in walk_mapping(payload):
        if not isinstance(value, str):
            continue
        match = re.fullmatch(r"(.+)_(ca|en|es|hu)", dotted)
        if match:
            suffix_groups[match.group(1)].add(match.group(2))
            counts["parallel_localization_cells"] += 1
            if spelling_values is not None:
                locale = match.group(2)
                relative = path.relative_to(repository).as_posix()
                spelling_values.setdefault(locale, {})[f"parallel:{relative}:{dotted}"] = value
    for base, present in sorted(suffix_groups.items()):
        for locale in sorted(set(LOCALES) - present):
            counts["parallel_localization_declarations"] += 1
            findings.append(data_finding("parallel_translation_missing", path, f"{base}_{locale}", locale))


def inventory_toml_language_translations(
    payload: dict[str, object],
    path: Path,
    repository: Path,
    counts: Counter[str],
    findings: list[dict[str, object]],
    spelling_values: dict[str, dict[str, str]] | None,
) -> None:
    """Inventory toml language translations."""
    language = payload.get("language")
    if isinstance(language, dict):
        languages = {
            locale: value for locale, value in language.items() if locale in LOCALES and isinstance(value, dict)
        }
        fields = {
            field
            for values in languages.values()
            for field, value in values.items()
            if field in LANGUAGE_CORE_FIELDS and isinstance(value, str)
        }
        for field in sorted(fields):
            inventory_toml_language_field(field, languages, path, repository, counts, findings, spelling_values)


def inventory_parallel_toml_sources(
    data_root: Path,
    repository: Path,
    counts: Counter[str],
    findings: list[dict[str, object]],
    spelling_values: dict[str, dict[str, str]] | None,
) -> None:
    """Inventory parallel toml sources."""
    for path in sorted(data_root.rglob("*.toml")) if data_root.is_dir() else ():
        inventory_parallel_toml_file(path, repository, counts, findings, spelling_values)


def walk_mapping(value: object, prefix: str = "") -> list[tuple[str, object]]:
    """Enumerate scalar leaves with their canonical dotted mapping or list coordinates."""
    leaves: list[tuple[str, object]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            dotted = f"{prefix}.{key}" if prefix else str(key)
            leaves.extend(walk_mapping(child, dotted))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            leaves.extend(walk_mapping(child, f"{prefix}.{index}"))
    else:
        leaves.append((prefix, value))
    return leaves


def inventory_parallel_toml_file(
    path: Path,
    repository: Path,
    counts: Counter[str],
    findings: list[dict[str, object]],
    spelling_values: dict[str, dict[str, str]] | None,
) -> None:
    """Inventory parallel toml file."""
    try:
        with path.open("rb") as handle:
            payload = load_toml(handle)
    except (OSError, TomlDecodeError) as exc:
        counts["invalid_data_files"] += 1
        findings.append(data_finding("invalid_localization_data", path, "", type(exc).__name__))
        return
    inventory_toml_suffix_translations(payload, path, repository, counts, findings, spelling_values)
    inventory_toml_language_translations(payload, path, repository, counts, findings, spelling_values)


def inventory_toml_language_field(
    field: str,
    languages: dict[str, dict[str, object]],
    path: Path,
    repository: Path,
    counts: Counter[str],
    findings: list[dict[str, object]],
    spelling_values: dict[str, dict[str, str]] | None,
) -> None:
    """Inventory toml language field."""
    for locale in LOCALES:
        value = languages.get(locale, {}).get(field)
        counts["parallel_localization_cells"] += 1
        if isinstance(value, str) and value.strip():
            if spelling_values is not None:
                relative = path.relative_to(repository).as_posix()
                spelling_values.setdefault(locale, {})[f"parallel:{relative}:language.{locale}.{field}"] = value
            continue
        counts["parallel_localization_declarations"] += 1
        findings.append(data_finding("parallel_translation_missing", path, f"language.{locale}.{field}", locale))
