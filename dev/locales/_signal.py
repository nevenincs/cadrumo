"""Actionable canonical-key translation backlog for locale status commands."""

from __future__ import annotations

import ast
import re
import tomllib
from collections import Counter, defaultdict
from pathlib import Path
from typing import Final, cast

from babel.messages.pofile import read_po

from dev._paths import REPO_ROOT, UTF_8

from ._status import CatalogueLeafState, classify_catalogue_leaf
from .manager import (
    LocaleManager,
    _flatten_raw_locale_leaves,
    discover_locale_codes,
    locale_catalogue_source,
)

_DOTTED_KEY_RE: Final[re.Pattern[str]] = re.compile(r"[a-z][a-z0-9_]*(?:\.[a-z0-9_-]+)+\Z")
_LOCALE_SUFFIX_RE: Final[re.Pattern[str]] = re.compile(r"(?:^|_)(?:ca|en|es|hu)$")
_PRESENTATION_FIELD_RE: Final[re.Pattern[str]] = re.compile(
    r"(?:^|_)(?:description|help|label|message|name|notes|summary|title)$"
)


def locale_signal(manager: LocaleManager, repository: Path = REPO_ROOT) -> dict[str, object]:
    """Build the known translation backlog and inventory-integrity findings."""
    required_keys = set(manager.get_codebase_keys())
    namespace_markers = sorted(manager.get_codebase_namespaces())
    locale_leaves, catalogue_findings = _catalogue_leaves(manager)
    matrix = _translation_matrix(required_keys, locale_leaves)
    source_inventory, source_findings = _source_inventory(manager)
    parallel_inventory, parallel_findings = _parallel_localization_inventory(repository)
    inventory_findings = [*source_findings, *parallel_findings]
    inventory_open = bool(
        source_inventory["invalid_tr_calls"]
        or source_inventory["dynamic_tr_calls"]
        or source_inventory["naked_presentation_sites"]
        or parallel_inventory["parallel_localization_declarations"]
        or namespace_markers
    )
    domains = _domain_summaries(
        required_keys,
        matrix,
        locale_leaves,
        [*inventory_findings, *({"kind": "unbounded_key_family"} for _ in namespace_markers)],
    )
    locales = _locale_summaries(required_keys, matrix, locale_leaves)
    backlog = cast(list[dict[str, object]], matrix["backlog"])
    keys_to_translate = {
        str(item["key"]) for item in backlog if isinstance(item, dict) and item["state"] in {"missing", "needs_value"}
    }
    cells_to_translate = sum(
        1 for item in backlog if isinstance(item, dict) and item["state"] in {"missing", "needs_value"}
    )
    translation_backlog = {
        "exact": not inventory_open,
        "unique_keys_to_translate": len(keys_to_translate) if not inventory_open else None,
        "cells_to_translate": cells_to_translate if not inventory_open else None,
        "known_unique_keys_to_translate": len(keys_to_translate),
        "known_cells_to_translate": cells_to_translate,
    }
    inventory_items = (
        source_inventory["invalid_tr_calls"]
        + source_inventory["dynamic_tr_calls"]
        + source_inventory["naked_presentation_sites"]
        + source_inventory["unread_or_invalid_sources"]
        + parallel_inventory["parallel_localization_declarations"]
        + parallel_inventory["invalid_data_files"]
        + len(namespace_markers)
    )
    largest = _largest_domain_locale(domains)
    catalogue_only_keys = {key for leaves in locale_leaves.values() for key in leaves if key not in required_keys}
    summary = {
        "inventory": {
            "closed": not inventory_open,
            **source_inventory,
            **parallel_inventory,
            "required_keys": len(required_keys),
            "unbounded_key_families": len(namespace_markers),
        },
        "translation_backlog": translation_backlog,
        "cells": matrix["cells"],
        "locales": locales,
        "domains": domains,
        "catalogue_only": {
            "keys": len(catalogue_only_keys),
            "cells": sum(1 for leaves in locale_leaves.values() for key in leaves if key not in required_keys),
        },
        "next_action": _next_action(
            inventory_open,
            inventory_items,
            matrix,
            domains,
            len(catalogue_only_keys),
        ),
    }
    findings = [
        *inventory_findings,
        *(finding for finding in catalogue_findings if finding.get("key") not in required_keys),
        *matrix["findings"],
        *(
            {
                "classification": "blocking",
                "kind": "unbounded_key_family",
                "key_prefix": marker,
                "next_action": "replace with a finite canonical key declaration",
            }
            for marker in namespace_markers
        ),
    ]
    return {
        "outcome": "backlog" if findings else "complete",
        "headline": _headline(translation_backlog, locales, largest, inventory_items),
        "summary": summary,
        "details": {
            "backlog": backlog,
            "findings": findings,
            "required_keys": sorted(required_keys),
        },
    }


def _catalogue_leaves(
    manager: LocaleManager,
) -> tuple[dict[str, dict[str, object]], list[dict[str, object]]]:
    leaves_by_locale: dict[str, dict[str, object]] = {}
    findings: list[dict[str, object]] = []
    for locale in sorted(discover_locale_codes(manager.locales_dir)):
        source = locale_catalogue_source(manager.locales_dir, locale)
        if source is None:
            continue
        leaves = _flatten_raw_locale_leaves(manager.load_locale(source))
        leaves_by_locale[locale] = leaves
        for key, value in sorted(leaves.items()):
            if not isinstance(value, str):
                findings.append(
                    {
                        "classification": "blocking",
                        "kind": "non_string_translation",
                        "key": key,
                        "locale": locale,
                        "value_type": type(value).__name__,
                        "next_action": "set_translation",
                    }
                )
    return leaves_by_locale, findings


def _translation_matrix(
    required_keys: set[str],
    locale_leaves: dict[str, dict[str, object]],
) -> dict[str, object]:
    counts = Counter[str]()
    backlog: list[dict[str, object]] = []
    findings: list[dict[str, object]] = []
    for key in sorted(required_keys):
        domain = _domain(key)
        for locale, leaves in sorted(locale_leaves.items()):
            if key not in leaves:
                state, reason = "missing", "translation_missing"
            else:
                value = leaves[key]
                if not isinstance(value, str):
                    state, reason = "needs_value", "translation_not_text"
                else:
                    leaf_state = classify_catalogue_leaf(key, value)
                    if leaf_state is CatalogueLeafState.AUTHORED:
                        state, reason = "ready", None
                    elif leaf_state is CatalogueLeafState.UNBINDABLE:
                        state, reason = "needs_repair", "reserved_placeholder"
                    else:
                        state, reason = "needs_value", f"translation_{leaf_state.value}"
            counts[state] += 1
            if state == "ready":
                continue
            item = {
                "domain": domain,
                "key": key,
                "locale": locale,
                "state": state,
                "reason": reason,
                "next_action": "set_translation" if state in {"missing", "needs_value"} else "repair_translation",
            }
            backlog.append(item)
            findings.append({"classification": "blocking", "kind": reason, **item})
    required_cells = len(required_keys) * len(locale_leaves)
    return {
        "backlog": backlog,
        "findings": findings,
        "cells": {
            "required": required_cells,
            "defined": required_cells - counts["missing"],
            "ready": counts["ready"],
            "missing": counts["missing"],
            "needs_value": counts["needs_value"],
            "needs_repair": counts["needs_repair"],
            "needs_review": 0,
        },
    }


def _source_inventory(
    manager: LocaleManager,
) -> tuple[dict[str, int], list[dict[str, object]]]:
    counts = Counter[str]()
    literal_keys = Counter[str]()
    findings: list[dict[str, object]] = []
    for root in (manager.src_dir, *manager.extra_src_dirs):
        for path in sorted(root.rglob("*.py")) if root.is_dir() else ():
            if "tests" in path.parts or path.name.startswith("test_"):
                continue
            try:
                tree = ast.parse(path.read_text(encoding=UTF_8), filename=str(path))
            except (OSError, UnicodeError, SyntaxError) as exc:
                counts["unread_or_invalid_sources"] += 1
                findings.append(_source_finding("source_unreadable", path, 0, type(exc).__name__))
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and _call_name(node.func) == "tr":
                    counts["tr_calls"] += 1
                    if not node.args:
                        counts["invalid_tr_calls"] += 1
                        findings.append(_source_finding("invalid_tr_call", path, node.lineno, "missing key argument"))
                    elif isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                        if _DOTTED_KEY_RE.fullmatch(node.args[0].value):
                            counts["literal_tr_calls"] += 1
                            literal_keys[node.args[0].value] += 1
                        else:
                            counts["invalid_tr_calls"] += 1
                            findings.append(_source_finding("invalid_tr_call", path, node.lineno, "invalid dotted key"))
                    else:
                        counts["dynamic_tr_calls"] += 1
                        findings.append(_source_finding("dynamic_tr_call", path, node.lineno, "key is not a literal"))
                if isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call) and node.exc.args:
                    value = node.exc.args[0]
                    if isinstance(value, ast.Constant) and isinstance(value.value, str):
                        counts["naked_presentation_sites"] += 1
                        findings.append(_source_finding("naked_presentation_text", path, node.lineno, value.value))
                if isinstance(node, ast.Call):
                    for keyword in node.keywords:
                        if keyword.arg not in {"help", "label", "message", "title"}:
                            continue
                        value = keyword.value
                        if isinstance(value, ast.Constant) and isinstance(value.value, str):
                            counts["naked_presentation_sites"] += 1
                            findings.append(_source_finding("naked_presentation_text", path, node.lineno, value.value))
    return {
        "production_occurrences": counts["tr_calls"],
        "tr_calls": counts["tr_calls"],
        "literal_tr_calls": counts["literal_tr_calls"],
        "literal_tr_keys_unique": len(literal_keys),
        "literal_tr_reuse_occurrences": sum(count - 1 for count in literal_keys.values()),
        "literal_tr_keys_reused": sum(1 for count in literal_keys.values() if count > 1),
        "dynamic_tr_calls": counts["dynamic_tr_calls"],
        "invalid_tr_calls": counts["invalid_tr_calls"],
        "naked_presentation_sites": counts["naked_presentation_sites"],
        "unread_or_invalid_sources": counts["unread_or_invalid_sources"],
    }, findings


def _parallel_localization_inventory(
    repository: Path,
) -> tuple[dict[str, int], list[dict[str, object]]]:
    counts = Counter[str]()
    findings: list[dict[str, object]] = []
    data_root = repository / "src" / "cadrumo" / "_data"
    for path in sorted(data_root.rglob("*.toml")) if data_root.is_dir() else ():
        try:
            with path.open("rb") as handle:
                payload = tomllib.load(handle)
        except (OSError, tomllib.TOMLDecodeError) as exc:
            counts["invalid_data_files"] += 1
            findings.append(_data_finding("invalid_localization_data", path, "", type(exc).__name__))
            continue
        for dotted, value in _walk_mapping(payload):
            if not isinstance(value, str):
                continue
            field = dotted.rsplit(".", 1)[-1]
            parallel = bool(
                _LOCALE_SUFFIX_RE.search(field) or re.search(r"(?:^|\.)language\.(?:ca|en|es|hu)(?:\.|$)", dotted)
            )
            naked = bool(_PRESENTATION_FIELD_RE.search(field) and not field.endswith("_key"))
            if parallel or naked:
                counts["parallel_localization_declarations"] += 1
                findings.append(
                    _data_finding(
                        "parallel_localization_declaration" if parallel else "naked_presentation_declaration",
                        path,
                        dotted,
                        value,
                    )
                )
    docs_root = repository / "docs" / "locales"
    for path in sorted(docs_root.rglob("*.po")) if docs_root.is_dir() else ():
        try:
            with path.open(encoding=UTF_8) as handle:
                messages = [message for message in read_po(handle) if message.id]
        except (OSError, UnicodeError) as exc:
            counts["invalid_data_files"] += 1
            findings.append(_data_finding("invalid_localization_data", path, "", type(exc).__name__))
            continue
        counts["parallel_localization_declarations"] += len(messages)
        if messages:
            findings.append(
                _data_finding("parallel_localization_catalogue", path, "", f"{len(messages)} gettext entries")
            )
    return {
        "parallel_localization_declarations": counts["parallel_localization_declarations"],
        "invalid_data_files": counts["invalid_data_files"],
    }, findings


def _domain_summaries(
    required_keys: set[str],
    matrix: dict[str, object],
    locale_leaves: dict[str, dict[str, object]],
    inventory_findings: list[dict[str, object]],
) -> list[dict[str, object]]:
    locales = sorted(locale_leaves)
    keys_by_domain: dict[str, set[str]] = defaultdict(set)
    for key in required_keys:
        keys_by_domain[_domain(key)].add(key)
    backlog = cast(list[dict[str, object]], matrix["backlog"])
    rows: list[dict[str, object]] = []
    for domain in sorted(keys_by_domain):
        keys = keys_by_domain[domain]
        items = [item for item in backlog if isinstance(item, dict) and item.get("domain") == domain]
        states = Counter(str(item["state"]) for item in items)
        by_locale = {
            locale: sum(1 for item in items if item["locale"] == locale and item["state"] in {"missing", "needs_value"})
            for locale in locales
        }
        translated_keys = {str(item["key"]) for item in items if item["state"] in {"missing", "needs_value"}}
        stale = sum(
            1
            for leaves in locale_leaves.values()
            for key in leaves
            if _domain(key) == domain and key not in required_keys
        )
        to_translate = states["missing"] + states["needs_value"]
        state = (
            "translate" if to_translate else "repair" if states["needs_repair"] else "stale" if stale else "complete"
        )
        largest_locale = max(locales, key=lambda locale: (by_locale[locale], locale))
        rows.append(
            {
                "domain": domain,
                "state": state,
                "required_keys": len(keys),
                "keys_to_translate": len(translated_keys),
                "to_translate": to_translate,
                "needs_repair": states["needs_repair"],
                "catalogue_only": stale,
                "to_translate_by_locale": by_locale,
                "next_action": (
                    f"translate {domain}/{largest_locale}: {by_locale[largest_locale]} cells" if to_translate else None
                ),
            }
        )
    unassigned = next((row for row in rows if row["domain"] == "unassigned"), None)
    if unassigned is None:
        unassigned = {
            "domain": "unassigned",
            "state": "complete",
            "required_keys": 0,
            "keys_to_translate": 0,
            "to_translate": 0,
            "needs_repair": 0,
            "catalogue_only": 0,
            "to_translate_by_locale": dict.fromkeys(locales, 0),
            "next_action": None,
        }
        rows.append(unassigned)
    unassigned["inventory_violations"] = len(inventory_findings)
    if inventory_findings:
        unassigned["state"] = "inventory_open"
        unassigned["next_action"] = "canonicalize production presentation declarations"
    order = {"inventory_open": 0, "translate": 1, "repair": 2, "review": 3, "stale": 4, "complete": 5}
    return sorted(rows, key=lambda row: (order[str(row["state"])], -int(row["to_translate"]), str(row["domain"])))


def _locale_summaries(
    required_keys: set[str],
    matrix: dict[str, object],
    locale_leaves: dict[str, dict[str, object]],
) -> list[dict[str, object]]:
    backlog = cast(list[dict[str, object]], matrix["backlog"])
    rows = []
    for locale, leaves in sorted(locale_leaves.items()):
        items = [item for item in backlog if isinstance(item, dict) and item.get("locale") == locale]
        states = Counter(str(item["state"]) for item in items)
        rows.append(
            {
                "locale": locale,
                "required": len(required_keys),
                "defined": len(required_keys) - states["missing"],
                "ready": len(required_keys) - len(items),
                "missing": states["missing"],
                "needs_value": states["needs_value"],
                "to_translate": states["missing"] + states["needs_value"],
                "needs_repair": states["needs_repair"],
                "needs_review": 0,
                "catalogue_only": sum(1 for key in leaves if key not in required_keys),
            }
        )
    return rows


def _largest_domain_locale(domains: list[dict[str, object]]) -> tuple[str, str, int] | None:
    candidates: list[tuple[int, str, str]] = []
    for row in domains:
        by_locale = row.get("to_translate_by_locale")
        if not isinstance(by_locale, dict):
            continue
        for locale, raw_count in by_locale.items():
            count = int(raw_count)
            if count:
                candidates.append((count, str(row["domain"]), str(locale)))
    if not candidates:
        return None
    count, domain, locale = max(candidates)
    return domain, locale, count


def _headline(
    backlog: dict[str, object],
    locales: list[dict[str, object]],
    largest: tuple[str, str, int] | None,
    inventory_items: int,
) -> str:
    locale_text = ", ".join(f"{row['locale']} {row['to_translate']}" for row in locales)
    largest_text = f" Largest backlog: {largest[0]}/{largest[1]} with {largest[2]}." if largest else ""
    if not backlog["exact"]:
        return (
            f"Translation total is not yet knowable: canonicalize {inventory_items} inventory violations. "
            f"Known backlog: {backlog['known_cells_to_translate']} cells across "
            f"{backlog['known_unique_keys_to_translate']} keys ({locale_text}).{largest_text}"
        )
    return (
        f"Translate {backlog['cells_to_translate']} locale cells for {backlog['unique_keys_to_translate']} "
        f"unique keys: {locale_text}.{largest_text}"
    )


def _next_action(
    inventory_open: bool,
    inventory_items: int,
    matrix: dict[str, object],
    domains: list[dict[str, object]],
    catalogue_only: int,
) -> dict[str, object] | None:
    if inventory_open:
        return {
            "action": "canonicalize_production_declarations",
            "items": inventory_items,
            "command": "fix source declarations, then run just check-locales",
        }
    cells = cast(dict[str, object], matrix["cells"])
    if int(cells["missing"]):
        return {
            "action": "create_missing_catalogue_leaves",
            "items": cells["missing"],
            "command": "just locales-scaffold",
        }
    if int(cells["needs_value"]):
        largest = _largest_domain_locale(domains)
        return {
            "action": "translate",
            "domain": largest[0] if largest else None,
            "locale": largest[1] if largest else None,
            "cells": largest[2] if largest else cells["needs_value"],
            "command": "just locales-set-batch <manifest>",
        }
    if catalogue_only:
        return {
            "action": "remove_stale_keys",
            "items": catalogue_only,
            "command": "just locales-remove-batch <manifest>",
        }
    return None


def _domain(key: str) -> str:
    return key.split(".", 1)[0] if _DOTTED_KEY_RE.fullmatch(key) else "unassigned"


def _call_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _source_finding(kind: str, path: Path, line: int, detail: str) -> dict[str, object]:
    return {
        "classification": "blocking",
        "kind": kind,
        "location": f"{path}:{line}" if line else str(path),
        "detail": detail,
        "next_action": "canonicalize production presentation declaration",
    }


def _data_finding(kind: str, path: Path, field: str, detail: str) -> dict[str, object]:
    return {
        "classification": "blocking",
        "kind": kind,
        "location": str(path),
        "field": field,
        "detail": detail,
        "next_action": "replace presentation prose with a canonical dotted translation key",
    }


def _walk_mapping(value: object, prefix: str = "") -> list[tuple[str, object]]:
    leaves: list[tuple[str, object]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            dotted = f"{prefix}.{key}" if prefix else str(key)
            leaves.extend(_walk_mapping(child, dotted))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            leaves.extend(_walk_mapping(child, f"{prefix}.{index}"))
    else:
        leaves.append((prefix, value))
    return leaves


__all__ = ["locale_signal"]
