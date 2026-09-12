"""Actionable canonical-key translation backlog for locale status commands."""

from __future__ import annotations

import ast
import re
import tomllib
from collections import Counter, defaultdict
from collections.abc import Iterable
from difflib import SequenceMatcher
from pathlib import Path
from typing import Final, cast

from babel.messages.pofile import read_po

from cadrumo.core.i18n.render import extract_placeholders
from dev._paths import REPO_ROOT, UTF_8

from ._status import CatalogueLeafState, classify_catalogue_leaf
from .manager import (
    LocaleManager,
    _flatten_raw_locale_leaves,
    discover_locale_codes,
    locale_catalogue_source,
)

_DOTTED_KEY_RE: Final[re.Pattern[str]] = re.compile(r"[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z0-9_-]+)+\Z")
_LOCALES: Final[tuple[str, ...]] = ("ca", "en", "es", "hu")
_LANGUAGE_CORE_FIELDS: Final[frozenset[str]] = frozenset({"definition", "scope_note", "short_description"})
_TRANSLATION_PLACEHOLDER_RE: Final[re.Pattern[str]] = re.compile(r"%\{[^{}]*\}|\{[^{}]*\}")
_TRANSLATION_CODE_RE: Final[re.Pattern[str]] = re.compile(
    r"`[^`]*`|--[A-Za-z][A-Za-z0-9-]*|\b[A-Z][A-Z0-9_]*(?:=[^][,;\s]+)?|"
    r"\b[A-Za-z][A-Za-z0-9]*(?:_[A-Za-z0-9]+)+\b|\[\d{1,4}\]"
)
_UNACCENTED_WORDS: Final[dict[str, frozenset[str]]] = {
    "ca": frozenset(
        {
            "administracio",
            "bonificacio",
            "declaracio",
            "descripcio",
            "exencio",
            "informacio",
            "numero",
            "provincia",
            "telefon",
            "variacio",
        }
    ),
    "es": frozenset(
        {
            "administracion",
            "autoliquidacion",
            "declaracion",
            "deduccion",
            "descripcion",
            "informacion",
            "numero",
            "retencion",
            "telefono",
        }
    ),
}


def locale_signal(manager: LocaleManager, repository: Path = REPO_ROOT) -> dict[str, object]:
    """Build the known translation backlog and inventory-integrity findings."""
    discovery_findings: list[dict[str, object]] = []
    try:
        required_keys = set(manager.get_codebase_keys())
    except Exception as exc:  # This is an intentional audit boundary.
        required_keys = set()
        discovery_findings.append(
            {
                "classification": "blocking",
                "kind": "key_discovery_failure",
                "error_type": type(exc).__name__,
                "detail": str(exc),
                "next_action": "restore authoritative key discovery, then rerun check-locales",
            }
        )
    namespace_markers = sorted(manager.get_codebase_namespaces())
    finite_families, unresolved_families = _dynamic_key_families(namespace_markers)
    locale_leaves, catalogue_findings = _catalogue_leaves(manager)
    if discovery_findings:
        required_keys.update(key for leaves in locale_leaves.values() for key in leaves)
    namespace_prefixes = tuple(marker.rstrip("*").rstrip(".") for marker in namespace_markers)
    required_keys.update(key for values in finite_families.values() for key in values)
    required_keys.update(
        key for leaves in locale_leaves.values() for key in leaves if _covered_by_namespace(key, namespace_prefixes)
    )
    matrix = _translation_matrix(required_keys, locale_leaves)
    source_inventory, source_findings = _source_inventory(manager)
    parallel_inventory, parallel_findings = _parallel_localization_inventory(repository)
    inventory_findings = [*discovery_findings, *source_findings, *parallel_findings]
    inventory_open = bool(
        discovery_findings
        or source_inventory["invalid_tr_calls"]
        or source_inventory["naked_presentation_sites"]
        or parallel_inventory["parallel_localization_declarations"]
        or unresolved_families
    )
    domains = _domain_summaries(
        required_keys,
        matrix,
        locale_leaves,
        [*inventory_findings, *({"kind": "unbounded_key_family"} for _ in unresolved_families)],
    )
    locales = _locale_summaries(required_keys, matrix, locale_leaves)
    backlog = cast(list[dict[str, object]], matrix["backlog"])
    keys_to_translate = {
        str(item["key"]) for item in backlog if isinstance(item, dict) and item["state"] in {"missing", "needs_value"}
    }
    cells_to_translate = sum(
        1 for item in backlog if isinstance(item, dict) and item["state"] in {"missing", "needs_value"}
    )
    keys_to_repair = {
        str(item["key"]) for item in backlog if isinstance(item, dict) and item["state"] == "needs_repair"
    }
    translation_backlog = {
        "exact": not inventory_open,
        "unique_keys_to_translate": len(keys_to_translate) if not inventory_open else None,
        "cells_to_translate": cells_to_translate if not inventory_open else None,
        "known_unique_keys_to_translate": len(keys_to_translate),
        "known_cells_to_translate": cells_to_translate,
        "unique_keys_to_repair": len(keys_to_repair),
        "cells_to_repair": int(cast(dict[str, int], matrix["cells"])["needs_repair"]),
        "cells_to_review": int(cast(dict[str, int], matrix["cells"])["needs_review"]),
    }
    inventory_items = (
        source_inventory["invalid_tr_calls"]
        + source_inventory["naked_presentation_sites"]
        + source_inventory["unread_or_invalid_sources"]
        + parallel_inventory["parallel_localization_declarations"]
        + parallel_inventory["invalid_data_files"]
        + len(unresolved_families)
        + len(discovery_findings)
    )
    largest = _largest_domain_locale(domains)
    catalogue_key_cells = sum(len(leaves) for leaves in locale_leaves.values())
    catalogue_keys_unique = len({key for leaves in locale_leaves.values() for key in leaves})
    catalogue_only_keys = {key for leaves in locale_leaves.values() for key in leaves if key not in required_keys}
    finite_dynamic_keys = {key for values in finite_families.values() for key in values}
    summary = {
        "inventory": {
            "closed": not inventory_open,
            "key_discovery_failures": len(discovery_findings),
            "catalogue_key_declarations": catalogue_key_cells,
            "catalogue_keys_unique": catalogue_keys_unique,
            "catalogue_cross_locale_repetitions": catalogue_key_cells - catalogue_keys_unique,
            "catalogue_duplicate_declarations": 0,
            **source_inventory,
            **parallel_inventory,
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
            for marker in unresolved_families
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
            "dynamic_key_families": {
                "finite": [
                    {
                        "key_prefix": marker,
                        "concrete_keys": list(keys),
                    }
                    for marker, keys in sorted(finite_families.items())
                ],
                "unresolved": [
                    {
                        "key_prefix": marker,
                        "concrete_catalogue_keys": sorted(
                            {
                                key
                                for leaves in locale_leaves.values()
                                for key in leaves
                                if _covered_by_namespace(key, (marker.rstrip("*").rstrip("."),))
                            }
                        ),
                    }
                    for marker in unresolved_families
                ],
            },
        },
    }


def _dynamic_key_families(
    namespace_markers: Iterable[str],
    *,
    registered_keys: Iterable[str] | None = None,
) -> tuple[dict[str, tuple[str, ...]], tuple[str, ...]]:
    """Partition namespace markers using concrete f-string registry evidence.

    The scanner emits a marker whenever it cannot enumerate a dynamic key.  A
    marker is finite when the f-string registry supplies at least one concrete
    key below its prefix; only markers without that evidence remain unresolved.
    ``registered_keys`` is injectable so this boundary can be tested without
    importing the full runtime registry.
    """
    markers = tuple(sorted(set(namespace_markers)))
    if registered_keys is None:
        from .fstring_registry import get_registered_keys

        registered_keys = get_registered_keys()
    concrete_keys = tuple(sorted(set(registered_keys)))
    finite: dict[str, tuple[str, ...]] = {}
    unresolved: list[str] = []
    for marker in markers:
        prefix = marker.rstrip("*").rstrip(".")
        values = tuple(key for key in concrete_keys if _covered_by_namespace(key, (prefix,)))
        if values:
            finite[marker] = values
        else:
            unresolved.append(marker)
    return finite, tuple(unresolved)


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
        review_locales = _suspicious_translation_locales(key, locale_leaves)
        source_value = locale_leaves.get("es", {}).get(key)
        source_placeholders = _translation_tokens(source_value) if isinstance(source_value, str) else None
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
                        state, reason = (
                            ("needs_repair", "translation_placeholder_mismatch")
                            if locale != "es"
                            and source_placeholders is not None
                            and _translation_tokens(value) != source_placeholders
                            else ("needs_review", "translation_spelling_suspect")
                            if _has_unaccented_word(locale, value)
                            else ("needs_review", "translation_too_similar")
                            if locale in review_locales
                            else ("ready", None)
                        )
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
                "next_action": (
                    "set_translation"
                    if state in {"missing", "needs_value"}
                    else "review_translation"
                    if state == "needs_review"
                    else "repair_translation"
                ),
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
            "needs_review": counts["needs_review"],
        },
    }


def _translation_tokens(value: str) -> tuple[frozenset[str], frozenset[str]]:
    """Return expansion placeholders and bracketed casilla references."""
    bracketed = re.findall(r"\[([^\[\]\r\n]+)\]", value)
    references = frozenset(
        token
        for token in bracketed
        if token.isdecimal()
        or (
            not any(character.isspace() for character in token)
            and any(operator in token for operator in "=+-*/")
            and re.fullmatch(r"[A-Za-z0-9_.+*/=-]+", token)
        )
    )
    return extract_placeholders(value), references


def _suspicious_translation_locales(
    key: str,
    locale_leaves: dict[str, dict[str, object]],
) -> set[str]:
    source = locale_leaves.get("es", {}).get(key)
    if not isinstance(source, str):
        return set()
    normalized_source = _human_translation_text(source)
    source_words = _translation_words(normalized_source)
    if len(normalized_source) < 40 or sum(character.isalpha() for character in normalized_source) < 25:
        return set()
    suspicious: set[str] = set()
    for locale, leaves in locale_leaves.items():
        if locale == "es":
            continue
        target = leaves.get(key)
        if not isinstance(target, str):
            continue
        normalized_target = _human_translation_text(target)
        target_words = _translation_words(normalized_target)
        combined_words = len(source_words) + len(target_words)
        maximum_ratio = 2 * min(len(source_words), len(target_words)) / combined_words if combined_words else 1.0
        if maximum_ratio < 0.985:
            continue
        if SequenceMatcher(None, source_words, target_words).ratio() >= 0.985:
            suspicious.add(locale)
    return suspicious


def _has_unaccented_word(locale: str, value: str) -> bool:
    normalized = _human_translation_text(value)
    if len(normalized) < 20:
        return False
    words = set(_translation_words(normalized))
    return not words.isdisjoint(_UNACCENTED_WORDS.get(locale, frozenset()))


def _human_translation_text(value: str) -> str:
    """Return prose after removing interpolation and transport syntax.

    Similarity and spelling signals are intended to review copied prose, not
    the stable syntax embedded in a message.  CLI commands, option names,
    structured ``FIELD=value`` input, snake-case enum members, casilla
    references, and interpolation placeholders are therefore excluded before
    either signal inspects the text.  The original value remains untouched for
    placeholder parity and rendering checks.
    """
    without_placeholders = _TRANSLATION_PLACEHOLDER_RE.sub(" ", value)
    without_code = _TRANSLATION_CODE_RE.sub(" ", without_placeholders)
    return " ".join(without_code.casefold().split())


def _translation_words(value: str) -> tuple[str, ...]:
    """Return alphabetic prose words for locale-quality signals."""
    return tuple(re.findall(r"[^\W\d_]+", value, flags=re.UNICODE))


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
            translation_names = _translation_call_names(tree)
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and _is_translation_call(node.func, translation_names):
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
                    for keyword in node.keywords:
                        if keyword.arg != "default":
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
        suffix_groups: dict[str, set[str]] = defaultdict(set)
        for dotted, value in _walk_mapping(payload):
            if not isinstance(value, str):
                continue
            match = re.fullmatch(r"(.+)_(ca|en|es|hu)", dotted)
            if match:
                suffix_groups[match.group(1)].add(match.group(2))
                counts["parallel_localization_cells"] += 1
        for base, present in sorted(suffix_groups.items()):
            for locale in sorted(set(_LOCALES) - present):
                counts["parallel_localization_declarations"] += 1
                findings.append(_data_finding("parallel_translation_missing", path, f"{base}_{locale}", locale))
        language = payload.get("language")
        if isinstance(language, dict):
            languages = {
                locale: value for locale, value in language.items() if locale in _LOCALES and isinstance(value, dict)
            }
            fields = {
                field
                for values in languages.values()
                for field, value in values.items()
                if field in _LANGUAGE_CORE_FIELDS and isinstance(value, str)
            }
            for field in sorted(fields):
                for locale in _LOCALES:
                    value = languages.get(locale, {}).get(field)
                    counts["parallel_localization_cells"] += 1
                    if isinstance(value, str) and value.strip():
                        continue
                    counts["parallel_localization_declarations"] += 1
                    findings.append(
                        _data_finding("parallel_translation_missing", path, f"language.{locale}.{field}", locale)
                    )
    docs_root = repository / "docs" / "locales"
    docs_messages: dict[tuple[str, str], dict[str, bool]] = defaultdict(dict)
    for path in sorted(docs_root.rglob("*.po")) if docs_root.is_dir() else ():
        try:
            with path.open(encoding=UTF_8) as handle:
                messages = [message for message in read_po(handle) if message.id]
        except (OSError, UnicodeError) as exc:
            counts["invalid_data_files"] += 1
            findings.append(_data_finding("invalid_localization_data", path, "", type(exc).__name__))
            continue
        relative = path.relative_to(docs_root)
        locale = relative.parts[0]
        catalogue = str(Path(*relative.parts[2:]))
        for message in messages:
            message_id = message.id if isinstance(message.id, str) else "\x04".join(message.id)
            translated = bool(message.string) and "fuzzy" not in message.flags
            docs_messages[(catalogue, message_id)][locale] = translated
            counts["parallel_localization_cells"] += 1
    for (catalogue, message_id), states in docs_messages.items():
        for locale in ("ca", "es", "hu"):
            if states.get(locale):
                continue
            counts["parallel_localization_declarations"] += 1
            findings.append(
                _data_finding(
                    "docs_translation_missing", docs_root / locale / "LC_MESSAGES" / catalogue, message_id, locale
                )
            )
    return {
        "parallel_localization_declarations": counts["parallel_localization_declarations"],
        "parallel_localization_cells": counts["parallel_localization_cells"],
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
            "translate"
            if to_translate
            else "repair"
            if states["needs_repair"]
            else "review"
            if states["needs_review"]
            else "stale"
            if stale
            else "complete"
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
                "needs_review": states["needs_review"],
                "catalogue_only": stale,
                "to_translate_by_locale": by_locale,
                "next_action": (
                    f"translate {domain}/{largest_locale}: {by_locale[largest_locale]} cells"
                    if to_translate
                    else f"repair {states['needs_repair']} broken translations"
                    if states["needs_repair"]
                    else f"review {states['needs_review']} suspicious translations"
                    if states["needs_review"]
                    else None
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
            "needs_review": 0,
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
                "needs_review": states["needs_review"],
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


def _covered_by_namespace(key: str, prefixes: tuple[str, ...]) -> bool:
    return any(f".{prefix}." in f".{key}." for prefix in prefixes if prefix)


def _translation_call_names(tree: ast.Module) -> set[str]:
    """Return names imported from the canonical runtime translation module."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or not (node.module or "").endswith("i18n.render"):
            continue
        for alias in node.names:
            if alias.name == "tr":
                names.add(alias.asname or alias.name)
    return names


def _is_translation_call(node: ast.expr, translation_names: set[str]) -> bool:
    if isinstance(node, ast.Name):
        return node.id in translation_names
    return isinstance(node, ast.Attribute) and node.attr == "tr"


def _source_finding(kind: str, path: Path, line: int, detail: str) -> dict[str, object]:
    return {
        "classification": "blocking",
        "kind": kind,
        "location": f"{path}:{line}" if line else str(path),
        "detail": detail,
        "next_action": "canonicalize production presentation declaration",
    }


def _data_finding(kind: str, path: Path, field: str, detail: str) -> dict[str, object]:
    next_action = (
        "add the missing accented target-language translation"
        if kind in {"parallel_translation_missing", "docs_translation_missing"}
        else "repair the localization data source"
    )
    return {
        "classification": "blocking",
        "kind": kind,
        "location": str(path),
        "field": field,
        "detail": detail,
        "next_action": next_action,
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
