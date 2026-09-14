"""Actionable canonical-key translation backlog for locale status commands."""

from __future__ import annotations

import ast
import hashlib
import io
import json
import re
import tomllib
import unicodedata
from collections import Counter, defaultdict
from collections.abc import Iterable
from difflib import SequenceMatcher
from pathlib import Path
from typing import Final, cast

from babel.messages.mofile import write_mo
from babel.messages.pofile import read_po

from cadrumo.core.i18n.render import extract_placeholders
from dev._paths import REPO_ROOT, UTF_8

from ._spelling import SpellingToolError, load_dictionaries
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
_TRANSLATION_PLACEHOLDER_RE: Final[re.Pattern[str]] = re.compile(
    r"%\{[^{}\r\n]*\}|%\([A-Za-z_][A-Za-z0-9_.]*\)[#0\- +]?"
    r"(?:\d+|\*)?(?:\.\d+|\.\*)?(?:[hlL])?[diouxXeEfFgGcrsa%]|"
    r"\$\{[^{}\r\n]*\}|\{[^{}\r\n]*\}"
)
_TRANSLATION_CODE_RE: Final[re.Pattern[str]] = re.compile(
    r"`[^`]*`|--[A-Za-z][A-Za-z0-9-]*|\b[A-Z][A-Z0-9_]+(?:=[^][,;\s]+)?|"
    r"\b[A-Za-z][A-Za-z0-9]*(?:_[A-Za-z0-9]+)+\b|\[\d{1,4}\]"
)
_TRANSLATION_MARKDOWN_LINK_RE: Final[re.Pattern[str]] = re.compile(
    r"\[(?P<label>[^\]\r\n]+)\]\(\s*(?:<[^>\r\n]*>|[^)\r\n]*)\)"
)
_TRANSLATION_RST_LINK_RE: Final[re.Pattern[str]] = re.compile(
    r"`(?P<label>[^`\r\n<>]*?)\s*<(?P<target>[^>\r\n]+)>\s*`_?"
)
_TRANSLATION_RST_ROLE_RE: Final[re.Pattern[str]] = re.compile(r":[A-Za-z][A-Za-z0-9_-]*:`(?P<target>[^`\r\n]+)`")
_TRANSLATION_MYST_ROLE_RE: Final[re.Pattern[str]] = re.compile(r"\{[A-Za-z][A-Za-z0-9_-]*\}`(?P<target>[^`\r\n]+)`")
_TRANSLATION_LITERAL_RE: Final[re.Pattern[str]] = re.compile(r"```[\s\S]*?```|``[^`\r\n]*``|`[^`\r\n]*`")
_TRANSLATION_BRACKET_REFERENCE_RE: Final[re.Pattern[str]] = re.compile(
    r"\[(?:\d+|(?=[^\]\r\n]*[=+\-*/])[A-Za-z0-9_.+*/=-]+)\]"
)
_TRANSLATION_URL_RE: Final[re.Pattern[str]] = re.compile(
    r"(?i)(?<![\w])(?:https?|ftp|file|mailto):[^\s<>()\[\]{}]+|"
    r"(?<![\w])www\.[^\s<>()\[\]{}]+"
)
_TRANSLATION_PATH_RE: Final[re.Pattern[str]] = re.compile(
    r"(?<![\w])(?:[A-Za-z]:[\\/]|\\\\|\.{1,2}[\\/])[^\s<>()\[\]{}]+|"
    r"(?<![\w])(?:[\w.-]+[\\/])+[\w./-]+|"
    r"(?<![\w])[\w-]+(?:\.[\w-]+)+(?=[\s,;:!?)]|$)"
)
_TRANSLATION_FORMULA_RE: Final[re.Pattern[str]] = re.compile(
    r"(?<![\w])(?:[A-Za-z_][A-Za-z0-9_]*|\d+(?:[.,]\d+)?)(?:\s*(?:=|[+\-*/×÷<>≤≥])\s*"
    r"(?:[A-Za-z_][A-Za-z0-9_]*|\d+(?:[.,]\d+)?))+(?![\w])"
)
_TRANSLATION_NUMERIC_RE: Final[re.Pattern[str]] = re.compile(r"(?<![\w])\d+(?:[.,]\d+)*(?:%)?(?![\w])")
_TRANSLATION_OPTION_RE: Final[re.Pattern[str]] = re.compile(
    r"(?<![\w])--[A-Za-z][A-Za-z0-9-]*(?:=[^\s,;:()[\]{}]+)?|"
    r"(?<![\w])-[A-Za-z](?=\s|$|[,;:.)\]}])"
)
_TRANSLATION_IDENTIFIER_RE: Final[re.Pattern[str]] = re.compile(
    r"(?<![\w])(?:[A-Za-z_][A-Za-z0-9_]*(?:_[A-Za-z0-9_]+)+|"
    r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+|"
    r"[A-Za-z_]*\d[A-Za-z0-9_]*|"
    r"[A-Za-z][A-Za-z0-9]*(?:-[A-Za-z0-9]+){2,})(?![\w])"
)
_TRANSLATION_ROLE_MARKER_RE: Final[re.Pattern[str]] = re.compile(r":[A-Za-z][A-Za-z0-9_-]*:|\{[A-Za-z][A-Za-z0-9_-]*\}")
_TRANSLATION_HTML_TAG_RE: Final[re.Pattern[str]] = re.compile(r"</?[A-Za-z][A-Za-z0-9:-]*(?:\s+[^<>]*?)?/?>")
_TRANSLATION_HTML_LANGUAGE_RE: Final[re.Pattern[str]] = re.compile(
    r"<(?P<tag>[A-Za-z][A-Za-z0-9:-]*)\b"
    r"(?=[^<>]*?\blang\s*=\s*[\"'](?P<locale>[A-Za-z]{2})(?:-[^\"']*)?[\"'])"
    r"[^<>]*>(?P<body>.*?)</(?P=tag)\s*>",
    re.IGNORECASE | re.DOTALL,
)
_TRANSLATION_MARKDOWN_LINK_CONTEXT_RE: Final[re.Pattern[str]] = re.compile(
    r"\[(?P<label>[^\]\r\n]+)\]\(\s*(?:<(?P<angle_target>[^>\r\n]*)>|(?P<target>[^)\r\n]*))\)"
)
_TRANSLATION_LEGAL_TITLE_RE: Final[re.Pattern[str]] = re.compile(
    r"(?P<title>\b(?:[A-ZÁÉÍÓÚÜÑ][\wÁÉÍÓÚÜÑáéíóúüñ]*\s+){1,3})"
    r"(?P<identifier>[A-Z]{0,5}/?\d{1,4}/\d{4})\b"
)
_SPELLING_SURFACES: Final[tuple[str, ...]] = ("docs_po", "generated_docs", "runtime", "toml")
_NEAR_ECHO_THRESHOLD: Final[float] = 0.90
_ECHO_SAMPLE_LIMIT: Final[int] = 20
_INVARIANT_ECHO_REASONS: Final[tuple[str, ...]] = (
    "inline_code",
    "modelo_form",
    "platform_format",
    "canonical_product_identity",
    "target_dictionary_shared_term",
)
_MODELO_FORM_RE: Final[re.Pattern[str]] = re.compile(r"(?i)\b(?:modelo|form)\s+\d{1,4}\b")
_PLATFORM_FORMAT_RE: Final[re.Pattern[str]] = re.compile(
    r"(?:\b[A-Z][A-Z0-9]{1,}\b|(?<![\w])\.[A-Za-z0-9]{1,8}(?![\w]))"
)
_VERSION_TOKEN_RE: Final[re.Pattern[str]] = re.compile(
    r"(?<![\w])v?(?:\d+|[xXyYzZ])(?:[._-](?:\d+|[xXyYzZ])){1,3}(?![\w])"
)
_PLATFORM_LABEL_RE: Final[re.Pattern[str]] = re.compile(
    r"(?<![\w])(?P<label>[A-Za-z][A-Za-z0-9]*)\s*\((?P<details>[^()\r\n]*)\)"
)
_ARCHITECTURE_TOKEN_RE: Final[re.Pattern[str]] = re.compile(
    r"(?<![\w])(?:[A-Za-z]{1,4}[-_]?\d{1,3}(?:[-_][A-Za-z0-9]{1,4})*|\d{1,3}[-_x]\d{1,3})(?![\w])"
)


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
    parallel_values: dict[str, dict[str, str]] = defaultdict(dict)
    parallel_inventory, parallel_findings = _parallel_localization_inventory(
        repository, spelling_values=parallel_values
    )
    spelling, spelling_inventory, spelling_findings = _spellcheck_catalogues(
        required_keys, locale_leaves, repository, additional_values=parallel_values
    )
    matrix = _translation_matrix(required_keys, locale_leaves, spelling)
    finite_dynamic_keys = {key for values in finite_families.values() for key in values}
    source_inventory, source_findings = _source_inventory(
        manager,
        dynamic_resolved_keys=finite_dynamic_keys,
    )
    inventory_findings = [*discovery_findings, *source_findings, *parallel_findings, *spelling_findings]
    matrix_findings = cast(list[dict[str, object]], matrix["findings"])
    placeholder_mismatches = sum(
        finding.get("kind") == "translation_placeholder_mismatch" for finding in matrix_findings
    )
    invalid_placeholders = sum(
        finding.get("kind") in {"reserved_placeholder", "translation_invalid_placeholder"}
        for finding in matrix_findings
    )
    inventory_open = bool(
        discovery_findings
        or source_inventory["invalid_tr_calls"]
        or source_inventory["conflicting_duplicate_declarations"]
        or source_inventory["naked_presentation_sites"]
        or source_inventory["unread_or_invalid_sources"]
        or parallel_inventory["parallel_localization_declarations"]
        or parallel_inventory["invalid_data_files"]
        or parallel_inventory["docs_extraction_failures"]
        or parallel_inventory["docs_source_drift_pages"]
        or parallel_inventory["docs_translation_source_echo"]
        or parallel_inventory["docs_orphan_catalogue_files"]
        or parallel_inventory["docs_missing_catalogue_files"]
        or parallel_inventory["docs_generated_source_failures"]
        or spelling_inventory["spelling_tool_failures"]
        or spelling_inventory["spelling_unknown_cells"]
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
        + source_inventory["conflicting_duplicate_declarations"]
        + source_inventory["naked_presentation_sites"]
        + source_inventory["unread_or_invalid_sources"]
        + parallel_inventory["parallel_localization_declarations"]
        + parallel_inventory["invalid_data_files"]
        + parallel_inventory["docs_extraction_failures"]
        + parallel_inventory["docs_source_drift_pages"]
        + parallel_inventory["docs_translation_source_echo"]
        + parallel_inventory["docs_orphan_catalogue_files"]
        + parallel_inventory["docs_missing_catalogue_files"]
        + parallel_inventory["docs_generated_source_failures"]
        + spelling_inventory["spelling_tool_failures"]
        + spelling_inventory["spelling_unknown_cells"]
        + len(unresolved_families)
        + len(discovery_findings)
    )
    largest = _largest_domain_locale(domains)
    catalogue_key_cells = sum(len(leaves) for leaves in locale_leaves.values())
    catalogue_keys_unique = len({key for leaves in locale_leaves.values() for key in leaves})
    catalogue_only_keys = {key for leaves in locale_leaves.values() for key in leaves if key not in required_keys}
    catalogue_only_findings = [
        {
            "classification": "blocking",
            "kind": "catalogue_only_key",
            "domain": _domain(key),
            "key": key,
            "locales": sorted(locale for locale, leaves in locale_leaves.items() if key in leaves),
            "cells": sum(1 for leaves in locale_leaves.values() if key in leaves),
            "next_action": "remove the stale key through locales-remove-batch",
        }
        for key in sorted(catalogue_only_keys)
    ]
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
        *catalogue_only_findings,
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


def _spellcheck_catalogues(
    required_keys: set[str],
    locale_leaves: dict[str, dict[str, object]],
    repository: Path,
    *,
    additional_values: dict[str, dict[str, str]] | None = None,
) -> tuple[dict[tuple[str, str], tuple[str, ...]], dict[str, object], list[dict[str, object]]]:
    """Check authored prose with pinned Hunspell dictionaries through spylls."""
    unknown_by_cell: dict[tuple[str, str], set[str]] = defaultdict(set)
    keys_by_word: dict[str, dict[str, set[tuple[str, str]]]] = {}
    cell_words: dict[tuple[str, str], frozenset[str]] = {}
    cell_words_by_language: dict[tuple[str, str], dict[str, frozenset[str]]] = {}
    cell_excluded_structural_tokens: dict[tuple[str, str], int] = {}
    cell_text: dict[tuple[str, str], str] = {}
    excluded_by_surface_locale: Counter[tuple[str, str]] = Counter()
    # Keep enrollment and dictionary coverage separate.  A cell containing only
    # links, identifiers, placeholders, or numbers is still an enrolled cell;
    # it simply has no prose words to pass through Hunspell.  The report joins
    # these counters with the parallel-surface collector, so counting only
    # non-empty prose here makes the reconciliation appear to lose cells.
    enrolled_cells_by_locale: Counter[str] = Counter()
    prose_cells_by_locale: Counter[str] = Counter()
    structural_only_cells_by_locale: Counter[str] = Counter()
    locales = set(locale_leaves) | set(additional_values or {})
    for locale in sorted(locales):
        leaves = locale_leaves.get(locale, {})
        values = {key: leaves.get(key) for key in required_keys}
        values.update((additional_values or {}).get(locale, {}))
        for key, value in sorted(values.items()):
            if not isinstance(value, str):
                continue
            enrolled_cells_by_locale[locale] += 1
            cell = (locale, value)
            if cell not in cell_words:
                language_segments = _translation_spelling_segments(value, key, locale)
                language_words_mutable: dict[str, set[str]] = defaultdict(set)
                for language, words, _excluded in language_segments:
                    language_words_mutable[language].update(word for word in words if len(word) > 1)
                language_words = {language: frozenset(words) for language, words in language_words_mutable.items()}
                cell_words_by_language[cell] = language_words
                cell_words[cell] = frozenset(word for words in language_words.values() for word in words)
                excluded_tokens = sum(excluded for _language, _words, excluded in language_segments)
                cell_excluded_structural_tokens[cell] = excluded_tokens
            words = cell_words[cell]
            excluded_by_surface_locale[(_spelling_surface(key), locale)] += cell_excluded_structural_tokens[cell]
            cell_text[(locale, key)] = value
            if words:
                prose_cells_by_locale[locale] += 1
            else:
                structural_only_cells_by_locale[locale] += 1
            for dictionary_locale, language_words in cell_words_by_language[cell].items():
                locale_words = keys_by_word.setdefault(dictionary_locale, defaultdict(set))
                for word in language_words:
                    locale_words[word].add((locale, key))
    unknown_words: set[tuple[str, str]] = set()
    try:
        dictionaries = load_dictionaries(repository)
        for dictionary_locale, words in keys_by_word.items():
            dictionary = dictionaries[dictionary_locale]
            for word in words:
                if dictionary.lookup(word):
                    continue
                for owner_locale, key in words[word]:
                    owner_cell = (owner_locale, key)
                    value = cell_text[owner_cell]
                    foreign_context = _spanish_word_context(
                        value,
                        key,
                        word,
                        owner_locale=owner_locale,
                        dictionary=dictionaries.get(owner_locale),
                        spanish_dictionary=dictionaries.get("es"),
                    )
                    if foreign_context and dictionary_locale == owner_locale:
                        # A Spanish legal title or authority name embedded in an
                        # English/Hungarian/Catalan cell is checked by Spanish.
                        # Unknown words remain findings, but are attributed to the
                        # language of the embedded phrase rather than to the page.
                        if dictionaries["es"].lookup(word):
                            continue
                        unknown_words.add(("es", word.casefold()))
                        unknown_by_cell[owner_cell].add(word)
                        continue
                    unknown_words.add((dictionary_locale, word.casefold()))
                    unknown_by_cell[owner_cell].add(word)
    except SpellingToolError as exc:
        failure = {
            "classification": "blocking",
            "kind": exc.kind,
            "error_type": type(exc).__name__,
            "detail": exc.detail,
            "next_action": exc.next_action,
        }
        enrolled_cells = sum(enrolled_cells_by_locale.values())
        prose_cells = sum(prose_cells_by_locale.values())
        return (
            {},
            {
                "spellchecked_cells": enrolled_cells,
                "spelling_cells": enrolled_cells,
                "spelling_cells_by_locale": dict(sorted(enrolled_cells_by_locale.items())),
                "spelling_prose_cells": prose_cells,
                "spelling_prose_cells_by_locale": dict(sorted(prose_cells_by_locale.items())),
                "spelling_structural_only_cells": sum(structural_only_cells_by_locale.values()),
                "spelling_structural_only_cells_by_locale": dict(sorted(structural_only_cells_by_locale.items())),
                "spelling_unknown_cells": 0,
                "spelling_unknown_words": 0,
                "spelling_tool_failures": 1,
                **_excluded_structural_inventory(excluded_by_surface_locale),
            },
            [failure],
        )
    spelling = {cell: tuple(sorted(words, key=str.casefold)) for cell, words in unknown_by_cell.items()}
    unknown_findings = [
        {
            "classification": "blocking",
            "kind": "translation_spelling_unknown",
            "domain": (
                "docs"
                if key.startswith("parallel:docs/")
                else "structured_data"
                if key.startswith("parallel:")
                else _domain(key)
            ),
            "locale": locale,
            "location": key.removeprefix("parallel:"),
            "unknown_words": list(words),
            "next_action": "correct the localized prose in its authoritative data source",
        }
        for (locale, key), words in sorted(spelling.items())
        if words
    ]
    enrolled_cells = sum(enrolled_cells_by_locale.values())
    prose_cells = sum(prose_cells_by_locale.values())
    return (
        spelling,
        {
            "spellchecked_cells": enrolled_cells,
            "spelling_cells": enrolled_cells,
            "spelling_cells_by_locale": dict(sorted(enrolled_cells_by_locale.items())),
            "spelling_prose_cells": prose_cells,
            "spelling_prose_cells_by_locale": dict(sorted(prose_cells_by_locale.items())),
            "spelling_structural_only_cells": sum(structural_only_cells_by_locale.values()),
            "spelling_structural_only_cells_by_locale": dict(sorted(structural_only_cells_by_locale.items())),
            "spelling_unknown_cells": len(unknown_by_cell),
            "spelling_unknown_words": len(unknown_words),
            "spelling_tool_failures": 0,
            **_excluded_structural_inventory(excluded_by_surface_locale),
        },
        unknown_findings,
    )


def _translation_matrix(
    required_keys: set[str],
    locale_leaves: dict[str, dict[str, object]],
    spelling: dict[tuple[str, str], tuple[str, ...]] | None = None,
) -> dict[str, object]:
    spelling = spelling or {}
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
                            else ("needs_review", "translation_spelling_unknown")
                            if (locale, key) in spelling
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
            if reason == "translation_spelling_unknown":
                item["unknown_words"] = list(spelling[(locale, key)])
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
    references = frozenset(token for token in bracketed if _is_bracket_reference(token))
    return extract_placeholders(value), references


def _is_bracket_reference(token: str) -> bool:
    """Whether a bracketed token is a casilla number or compact formula expression."""
    return token.isdecimal() or bool(
        not any(character.isspace() for character in token)
        and any(operator in token for operator in "=+-*/")
        and re.fullmatch(r"[A-Za-z0-9_.+*/=-]+", token)
    )


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


def _human_translation_text(value: str) -> str:
    """Return prose after removing interpolation and transport syntax.

    Similarity and spelling signals are intended to review copied prose, not
    the stable syntax embedded in a message.  Links preserve their visible
    labels while their targets, code/literal spans, paths, options, structured
    identifiers, formulas, and interpolation placeholders are excluded before
    either signal inspects the text.  The original value remains untouched for
    placeholder parity and rendering checks.
    """
    return _filtered_translation_text(value)[0]


def _translation_spelling_segments(
    value: str,
    key: str,
    default_locale: str,
) -> tuple[tuple[str, tuple[str, ...], int], ...]:
    """Split prose by explicit language-bearing markup and legal identifiers.

    The returned text is already filtered for transport syntax.  A legal link
    label, a ``lang``-annotated HTML element, or a numbered form/legal title is
    therefore checked with the dictionary that owns that rendered text rather
    than with the language of the surrounding catalogue cell.
    """
    foreign: list[tuple[int, int, str, str, int]] = []
    for match in _TRANSLATION_HTML_LANGUAGE_RE.finditer(value):
        language = match.group("locale").casefold()
        if language in _LOCALES:
            foreign.append(
                (
                    match.start(),
                    match.end(),
                    language,
                    match.group("body"),
                    _filtered_translation_text(match.group(0))[1],
                )
            )
    for match in _TRANSLATION_MARKDOWN_LINK_CONTEXT_RE.finditer(value):
        target = match.group("angle_target") or match.group("target") or ""
        if _is_legal_authority_target(target):
            foreign.append(
                (
                    match.start(),
                    match.end(),
                    "es",
                    match.group("label"),
                    _filtered_translation_text(match.group(0))[1],
                )
            )
    for match in _TRANSLATION_RST_LINK_RE.finditer(value):
        if _is_legal_authority_target(match.group("target")):
            foreign.append(
                (
                    match.start(),
                    match.end(),
                    "es",
                    match.group("label"),
                    _filtered_translation_text(match.group(0))[1],
                )
            )
    if default_locale != "es":
        literal_ranges = tuple((match.start(), match.end()) for match in _TRANSLATION_LITERAL_RE.finditer(value))
        for pattern in (_MODELO_FORM_RE, _TRANSLATION_LEGAL_TITLE_RE):
            for match in pattern.finditer(value):
                if any(start <= match.start() and match.end() <= end for start, end in literal_ranges):
                    continue
                text = match.group(0)
                foreign.append(
                    (
                        match.start(),
                        match.end(),
                        "es",
                        text,
                        _filtered_translation_text(text)[1],
                    )
                )

    # Keep the first structured span when two recognizers describe the same
    # source range (for example a legal title inside a marked link).
    accepted: list[tuple[int, int, str, str, int]] = []
    for candidate in sorted(foreign, key=lambda item: (item[0], -(item[1] - item[0]))):
        if any(candidate[0] < previous[1] and previous[0] < candidate[1] for previous in accepted):
            continue
        accepted.append(candidate)
    masked = list(value)
    for start, end, _language, _text, _excluded in accepted:
        masked[start:end] = [" "] * (end - start)
    filtered, excluded = _filtered_translation_text("".join(masked))
    segments: list[tuple[str, tuple[str, ...], int]] = [(default_locale, _translation_words(filtered), excluded)]
    for _start, _end, language, text, structural_excluded in accepted:
        segments.append((language, _translation_words(_filtered_translation_text(text)[0]), structural_excluded))
    return tuple(segments)


def _is_legal_authority_target(target: str) -> bool:
    """Recognize legal authority links from their structured destination."""
    normalized = target.casefold()
    return (
        "_generated/legal/" in normalized
        or ".boe.es/" in normalized
        or ".aeat.es/" in normalized
        or "agenciatributaria.gob.es/" in normalized
    )


def _spanish_word_context(
    value: str,
    key: str,
    word: str,
    *,
    owner_locale: str,
    dictionary: object | None,
    spanish_dictionary: object | None,
) -> bool:
    """Whether an unknown word sits in structured Spanish legal/name prose."""
    if owner_locale == "es" or not callable(getattr(spanish_dictionary, "lookup", None)):
        return False
    legal_context = (
        "/legal/" in key.casefold()
        or _TRANSLATION_LEGAL_TITLE_RE.search(value) is not None
        or _MODELO_FORM_RE.search(value) is not None
        or any(_is_legal_authority_target(match.group("target")) for match in _TRANSLATION_RST_LINK_RE.finditer(value))
        or any(
            _is_legal_authority_target(match.group("angle_target") or match.group("target") or "")
            for match in _TRANSLATION_MARKDOWN_LINK_CONTEXT_RE.finditer(value)
        )
    )
    words = list(_translation_words(value))
    try:
        index = next(index for index, candidate in enumerate(words) if candidate.casefold() == word.casefold())
    except StopIteration:
        return legal_context
    for neighbour in words[max(0, index - 1) : index] + words[index + 1 : index + 2]:
        if spanish_dictionary.lookup(neighbour) and neighbour[:1].isupper():
            return True
    return legal_context and bool(_TRANSLATION_LEGAL_TITLE_RE.search(value) or _MODELO_FORM_RE.search(value))


def _filtered_translation_text(value: str) -> tuple[str, int]:
    """Return prose and the number of syntax spans excluded from spelling.

    This is intentionally syntax-only: no locale vocabulary or product-term
    allowlist is consulted.  Link and role callbacks retain explicit visible
    labels, while targets remain outside the dictionary surface.
    """
    text = value
    excluded = 0
    for pattern, replacement in (
        (_TRANSLATION_HTML_TAG_RE, " "),
        (_TRANSLATION_MARKDOWN_LINK_RE, _visible_link_label),
        (_TRANSLATION_RST_LINK_RE, _visible_link_label),
        (_TRANSLATION_RST_ROLE_RE, _visible_role_label),
        (_TRANSLATION_MYST_ROLE_RE, _visible_role_label),
        (_TRANSLATION_LITERAL_RE, " "),
        (_TRANSLATION_BRACKET_REFERENCE_RE, " "),
        (_TRANSLATION_PLACEHOLDER_RE, " "),
        (_TRANSLATION_URL_RE, " "),
        (_TRANSLATION_PATH_RE, " "),
        (_TRANSLATION_OPTION_RE, " "),
        (_TRANSLATION_FORMULA_RE, " "),
        (_TRANSLATION_NUMERIC_RE, " "),
        (_TRANSLATION_IDENTIFIER_RE, " "),
        (_TRANSLATION_CODE_RE, " "),
        (_TRANSLATION_ROLE_MARKER_RE, " "),
    ):
        text, matches = pattern.subn(replacement, text)
        excluded += matches
    text = re.sub(r"[,;]+", " ", text)
    return " ".join(text.casefold().split()), excluded


def _visible_link_label(match: re.Match[str]) -> str:
    """Keep a rendered link label while excluding its target syntax."""
    label = match.group("label").strip()
    return f" {label} " if label else " "


def _visible_role_label(match: re.Match[str]) -> str:
    """Keep an explicit role label while excluding its target."""
    target = match.group("target").strip()
    if "<" not in target or not target.endswith(">"):
        return " "
    label = target.rsplit("<", 1)[0].strip()
    return f" {label} " if label else " "


def _spelling_surface(key: str) -> str:
    """Classify a spelling cell by its authored source surface."""
    if not key.startswith("parallel:"):
        return "runtime"
    relative = key.removeprefix("parallel:")
    if relative.startswith("src/"):
        return "toml"
    if relative.startswith("docs/locales/") or (
        not relative.startswith("docs/cli/") and not relative.startswith("docs/_generated/")
    ):
        return "docs_po"
    return "generated_docs"


def _excluded_structural_inventory(excluded: Counter[tuple[str, str]]) -> dict[str, object]:
    """Return stable structural-exclusion totals for every surface/locale."""
    by_surface_locale = {
        f"{surface}/{locale}": excluded[(surface, locale)] for surface in _SPELLING_SURFACES for locale in _LOCALES
    }
    return {
        "excluded_structural_tokens": sum(excluded.values()),
        "excluded_structural_tokens_by_surface_locale": by_surface_locale,
    }


def _translation_words(value: str) -> tuple[str, ...]:
    """Return alphabetic prose words for locale-quality signals."""
    return tuple(re.findall(r"[^\W\d_]+", value, flags=re.UNICODE))


def _source_inventory(
    manager: LocaleManager,
    *,
    dynamic_resolved_keys: Iterable[str] = (),
) -> tuple[dict[str, int], list[dict[str, object]]]:
    """Inventory production translation calls and their concrete key values.

    Literal calls are observed directly from the source tree.  Bounded dynamic
    calls are supplied by the f-string registry as concrete values, because the
    AST scanner can only see their namespace marker.  The occurrence counters
    intentionally retain reuse while the unique counter is computed from a set;
    their difference is therefore an auditable duplicate-occurrence delta.
    """
    counts = Counter[str]()
    literal_keys = Counter[str]()
    key_occurrences: list[str] = []
    declarations: dict[str, list[dict[str, object]]] = defaultdict(list)
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
                            key = node.args[0].value
                            literal_keys[key] += 1
                            key_occurrences.append(key)
                            placeholders = tuple(
                                sorted(
                                    keyword.arg
                                    for keyword in node.keywords
                                    if keyword.arg not in {"locale", "default"} and keyword.arg is not None
                                )
                            )
                            declarations[key].append(
                                {
                                    "kind": "literal",
                                    "location": f"{path}:{node.lineno}",
                                    "placeholders": list(placeholders),
                                    "semantic_signature": placeholders,
                                }
                            )
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
    resolved_dynamic_keys = tuple(
        key for key in dynamic_resolved_keys if isinstance(key, str) and _DOTTED_KEY_RE.fullmatch(key)
    )
    key_occurrences.extend(resolved_dynamic_keys)
    for key in resolved_dynamic_keys:
        if _DOTTED_KEY_RE.fullmatch(key):
            declarations[key].append(
                {
                    "kind": "dynamic_resolved",
                    "location": "f-string-registry",
                    "placeholders": [],
                    "semantic_signature": None,
                }
            )
    conflicting_duplicates: list[dict[str, object]] = []
    for key, key_declarations in sorted(declarations.items()):
        signatures = {
            cast(tuple[str, ...], declaration["semantic_signature"])
            for declaration in key_declarations
            if declaration["semantic_signature"] is not None
        }
        if len(signatures) < 2:
            continue
        conflicting_duplicates.append(
            {
                "classification": "blocking",
                "kind": "conflicting_duplicate_translation_key",
                "key": key,
                "declarations": [
                    {name: value for name, value in declaration.items() if name != "semantic_signature"}
                    for declaration in key_declarations
                ],
                "next_action": "align duplicate translation-key placeholder declarations",
            }
        )
    findings.extend(conflicting_duplicates)
    unique_keys = set(key_occurrences)
    duplicate_occurrences = len(key_occurrences) - len(unique_keys)
    return {
        "production_occurrences": counts["tr_calls"],
        "tr_calls": counts["tr_calls"],
        "literal_tr_calls": counts["literal_tr_calls"],
        "raw_literal_key_occurrences": counts["literal_tr_calls"],
        "literal_tr_keys_unique": len(literal_keys),
        "literal_tr_reuse_occurrences": sum(count - 1 for count in literal_keys.values()),
        "literal_tr_keys_reused": sum(1 for count in literal_keys.values() if count > 1),
        "dynamic_tr_calls": counts["dynamic_tr_calls"],
        "dynamic_resolved_key_occurrences": len(resolved_dynamic_keys),
        "dynamic_resolved_localization_key_occurrences": len(resolved_dynamic_keys),
        "raw_localization_key_occurrences": len(key_occurrences),
        "unique_dot_keys": len(unique_keys),
        "duplicate_key_occurrence_delta": duplicate_occurrences,
        "conflicting_duplicate_declarations": len(conflicting_duplicates),
        "invalid_tr_calls": counts["invalid_tr_calls"],
        "naked_presentation_sites": counts["naked_presentation_sites"],
        "unread_or_invalid_sources": counts["unread_or_invalid_sources"],
    }, findings


def _parallel_localization_inventory(
    repository: Path,
    *,
    spelling_values: dict[str, dict[str, str]] | None = None,
) -> tuple[dict[str, object], list[dict[str, object]]]:
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
                if spelling_values is not None:
                    locale = match.group(2)
                    relative = path.relative_to(repository).as_posix()
                    spelling_values.setdefault(locale, {})[f"parallel:{relative}:{dotted}"] = value
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
                        if spelling_values is not None:
                            relative = path.relative_to(repository).as_posix()
                            spelling_values.setdefault(locale, {})[f"parallel:{relative}:language.{locale}.{field}"] = (
                                value
                            )
                        continue
                    counts["parallel_localization_declarations"] += 1
                    findings.append(
                        _data_finding("parallel_translation_missing", path, f"language.{locale}.{field}", locale)
                    )
    from dev.docs.i18n import TARGET_LANGUAGES

    docs_root = repository / "docs" / "locales"
    docs_messages: dict[tuple[str, str], dict[str, bool]] = defaultdict(dict)
    docs_translations: dict[tuple[str, str], dict[str, tuple[str, ...]]] = defaultdict(dict)
    docs_obsolete: dict[tuple[str, str], set[str]] = defaultdict(set)
    docs_catalogue_files: set[tuple[str, str]] = set()
    for path in sorted(docs_root.rglob("*.po")) if docs_root.is_dir() else ():
        try:
            with path.open(encoding=UTF_8) as handle:
                catalogue_payload = read_po(handle)
            write_mo(io.BytesIO(), catalogue_payload)
            messages = [message for message in catalogue_payload if message.id]
        except (OSError, UnicodeError, ValueError) as exc:
            counts["invalid_data_files"] += 1
            findings.append(_data_finding("invalid_localization_data", path, "", type(exc).__name__))
            continue
        relative = path.relative_to(docs_root)
        if len(relative.parts) < 3 or relative.parts[0] not in TARGET_LANGUAGES or relative.parts[1] != "LC_MESSAGES":
            counts["invalid_data_files"] += 1
            findings.append(_data_finding("invalid_docs_catalogue_layout", path, "", "unknown_locale_or_layout"))
            continue
        locale = relative.parts[0]
        catalogue = Path(*relative.parts[2:]).as_posix()
        docs_catalogue_files.add((locale, catalogue))
        counts["docs_catalogues_compiled"] += 1
        counts[f"docs_catalogues_compiled_{locale}"] += 1
        for message in messages:
            message_id = _po_message_identity(message)
            translations = _po_translation_strings(message.string)
            translated = (
                bool(translations) and all(value.strip() for value in translations) and "fuzzy" not in message.flags
            )
            docs_messages[(catalogue, message_id)][locale] = translated
            if translated:
                docs_translations[(catalogue, message_id)][locale] = translations
            counts["parallel_localization_cells"] += 1
            if spelling_values is not None and translated:
                for index, value in enumerate(translations):
                    cell = f"parallel:{path.relative_to(repository).as_posix()}:{message_id}"
                    if len(translations) > 1:
                        cell = f"{cell}:plural[{index}]"
                    spelling_values.setdefault(locale, {})[cell] = value
        for message in catalogue_payload.obsolete.values():
            if message.id:
                docs_obsolete[(locale, catalogue)].add(_po_message_identity(message))
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
    docs_inventory, docs_findings = _documentation_source_inventory(
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


def _documentation_source_inventory(
    repository: Path,
    catalogue_messages: dict[tuple[str, str], dict[str, bool]],
    *,
    catalogue_files: set[tuple[str, str]] | None = None,
    catalogue_obsolete: dict[tuple[str, str], set[str]] | None = None,
    catalogue_translations: dict[tuple[str, str], dict[str, tuple[str, ...]]] | None = None,
    spelling_values: dict[str, dict[str, str]] | None = None,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    """Validate cached source extraction and compare it with every PO.

    The committed catalogues are not a source authority: a newly authored
    paragraph is absent from every PO until gettext extraction is rerun.  This
    audit therefore consumes the same page selector and the digest manifest
    written by the canonical Sphinx gettext extractor. English source messages
    are enrolled from a digest-proven POT, alongside translated PO values.
    """
    from dev.docs.i18n import (
        SOURCE_MANIFEST_NAME,
        SOURCE_MANIFEST_SCHEMA_VERSION,
        TARGET_LANGUAGES,
        pot_root,
        user_scope_source_pages,
    )

    counts = Counter[str]()
    findings: list[dict[str, object]] = []
    source_echo_samples: list[dict[str, object]] = []
    invariant_echo_samples: list[dict[str, object]] = []
    near_echo_samples: list[dict[str, object]] = []
    echo_dictionaries: dict[str, object] | None = None
    echo_dictionaries_unavailable = False
    platform_identity_terms = _platform_identity_terms(repository)
    catalogue_obsolete = catalogue_obsolete or {}
    catalogue_translations = catalogue_translations or {}
    for (locale, _catalogue), identities in catalogue_obsolete.items():
        counts["docs_catalogue_messages_obsolete"] += len(identities)
        counts[f"docs_catalogue_messages_obsolete_{locale}"] += len(identities)
    catalogue_files = catalogue_files or {
        (locale, catalogue) for (catalogue, _message_id), states in catalogue_messages.items() for locale in states
    }
    docs_root = repository / "docs"
    try:
        pages = user_scope_source_pages(docs_root)
    except Exception as exc:  # The page authority is an audit boundary.
        counts["docs_extraction_failures"] += 1
        findings.append(_docs_extraction_finding(docs_root, exc))
        return _documentation_counts(counts), findings
    counts["docs_source_pages"] = len(pages)
    if not pages:
        counts["docs_extraction_failures"] += 1
        findings.append(
            {
                "classification": "blocking",
                "kind": "docs_source_surface_empty",
                "domain": "docs",
                "path": docs_root.as_posix(),
                "next_action": "restore user-scope page discovery, then rerun check-locales",
            }
        )
        return _documentation_counts(counts), findings
    generated_roots = (docs_root / "cli", docs_root / "_generated")
    generated_pages = sorted(
        path
        for root in generated_roots
        for path in (root.rglob("*") if root.is_dir() else ())
        if path.is_file() and path.suffix in {".md", ".rst"}
    )
    counts["docs_generated_english_only_pages"] = len(generated_pages)
    for path in generated_pages:
        try:
            prose = _visible_document_prose(path)
        except Exception as exc:  # Parsing is part of the measured docs surface.
            counts["docs_generated_source_failures"] += 1
            findings.append(
                {
                    "classification": "blocking",
                    "kind": "docs_generated_source_unreadable",
                    "domain": "docs",
                    "path": path.relative_to(repository).as_posix(),
                    "error_type": type(exc).__name__,
                    "detail": str(exc),
                    "next_action": "repair the generated user document, then rerun check-locales",
                }
            )
            continue
        counts["docs_generated_spellchecked_pages"] += 1
        embedded = _embedded_document_language_prose(path)
        counts["docs_generated_prose_cells"] += len(prose) + len(embedded)
        if spelling_values is not None:
            relative = path.relative_to(repository).as_posix()
            for line, text in prose:
                spelling_values.setdefault("en", {})[f"parallel:{relative}:line[{line}]"] = text
            for line, language, text in embedded:
                spelling_values.setdefault(language, {})[f"parallel:{relative}:line[{line}]:lang[{language}]"] = text
    extracted = pot_root(docs_root)
    for locale in TARGET_LANGUAGES:
        counts[f"docs_catalogue_files_expected_{locale}"] = len(pages)
    counts["docs_catalogue_files_expected"] = len(pages) * len(TARGET_LANGUAGES)
    expected_catalogues = {
        (locale, Path(page).with_suffix(".po").as_posix()) for locale in TARGET_LANGUAGES for page in pages
    }
    present_catalogues = catalogue_files & expected_catalogues
    counts["docs_catalogue_files_read"] = len(present_catalogues)
    for locale in TARGET_LANGUAGES:
        counts[f"docs_catalogue_files_read_{locale}"] = sum(
            1 for candidate_locale, _catalogue in present_catalogues if candidate_locale == locale
        )
    missing_catalogues = expected_catalogues - catalogue_files
    counts["docs_missing_catalogue_files"] = len(missing_catalogues)
    for locale, catalogue in sorted(missing_catalogues):
        findings.append(
            {
                "classification": "blocking",
                "kind": "docs_catalogue_missing",
                "domain": "docs",
                "path": f"docs/locales/{locale}/LC_MESSAGES/{catalogue}",
                "locale": locale,
                "next_action": "run python -m dev.docs.i18n, then translate the new catalogue",
            }
        )
    orphan_catalogues = catalogue_files - expected_catalogues
    counts["docs_orphan_catalogue_files"] = len(orphan_catalogues)
    for locale, catalogue in sorted(orphan_catalogues):
        findings.append(
            {
                "classification": "blocking",
                "kind": "docs_orphan_catalogue",
                "domain": "docs",
                "path": f"docs/locales/{locale}/LC_MESSAGES/{catalogue}",
                "locale": locale,
                "next_action": "run python -m dev.docs.i18n to prune the orphan catalogue",
            }
        )
    try:
        manifest_payload = json.loads((extracted / SOURCE_MANIFEST_NAME).read_text(encoding=UTF_8))
        if manifest_payload.get("schema_version") != SOURCE_MANIFEST_SCHEMA_VERSION or not isinstance(
            manifest_payload.get("sources"), dict
        ):
            raise ValueError("unsupported or malformed docs source manifest")
        source_digests = manifest_payload["sources"]
        expected_pages = set(pages)
        manifest_pages = set(source_digests)
        counts["docs_orphan_source_templates"] = len(manifest_pages - expected_pages)
        for page in pages:
            catalogue = Path(page).with_suffix(".po").as_posix()
            pot = extracted / Path(page).with_suffix(".pot")
            expected_digest = hashlib.sha256((docs_root / page).read_bytes()).hexdigest()
            source_current = source_digests.get(page) == expected_digest
            source_messages = _read_gettext_messages(pot)
            if not source_current or source_messages is None:
                counts["docs_source_drift_pages"] += 1
                findings.append(
                    {
                        "classification": "blocking",
                        "kind": (
                            "docs_source_template_stale"
                            if source_messages is not None
                            else "docs_source_template_missing"
                        ),
                        "domain": "docs",
                        "path": f"docs/{page}",
                        "next_action": "run python -m dev.docs.i18n, then translate the catalogue delta",
                    }
                )
                continue
            source_ids = set(source_messages)
            counts["docs_source_messages"] += len(source_ids)
            if spelling_values is not None:
                for identity, source_text in source_messages.items():
                    spelling_values.setdefault("en", {})[f"parallel:docs/{page}:{identity}"] = source_text
            page_drifted = False
            for locale in TARGET_LANGUAGES:
                translated_messages = {
                    identity: values
                    for (candidate, identity), localized in catalogue_translations.items()
                    if candidate == catalogue and (values := localized.get(locale)) is not None
                }
                for identity, translations in sorted(translated_messages.items()):
                    source_text = source_messages.get(identity)
                    if source_text is None:
                        continue
                    source_forms = tuple(source_text.split("\x04"))
                    for index, (source_form, translation_form) in enumerate(
                        zip(source_forms, translations, strict=False)
                    ):
                        counts["docs_translation_comparisons"] += 1
                        counts[f"docs_translation_comparisons_{locale}"] += 1
                        source_normalized = _translation_echo_normalize(source_form)
                        translation_normalized = _translation_echo_normalize(translation_form)
                        ratio = _translation_similarity(source_normalized, translation_normalized)
                        form = "singular" if len(source_forms) == 1 else f"plural[{index}]"
                        location = f"docs/locales/{locale}/LC_MESSAGES/{catalogue}"
                        evidence = {
                            "domain": "docs",
                            "form": form,
                            "locale": locale,
                            "message_id": identity,
                            "path": location,
                            "ratio": round(ratio, 6),
                            "source": source_form,
                            "translation": translation_form,
                        }
                        if source_normalized == translation_normalized:
                            if echo_dictionaries is None and not echo_dictionaries_unavailable:
                                try:
                                    echo_dictionaries = cast(dict[str, object], load_dictionaries(repository))
                                except SpellingToolError:
                                    echo_dictionaries_unavailable = True
                            reason = _translation_invariant_echo_reason(
                                source_form,
                                locale,
                                dictionary=(echo_dictionaries or {}).get(locale),
                                source_dictionary=(echo_dictionaries or {}).get("en"),
                                platform_terms=platform_identity_terms,
                            )
                            if reason is None:
                                counts["docs_translation_source_echo"] += 1
                                counts[f"docs_translation_source_echo_{locale}"] += 1
                                finding = {
                                    "classification": "blocking",
                                    "kind": "docs_translation_source_echo",
                                    **evidence,
                                    "next_action": (
                                        "replace the source echo with an accented target-language translation"
                                    ),
                                }
                                findings.append(finding)
                                if len(source_echo_samples) < _ECHO_SAMPLE_LIMIT:
                                    source_echo_samples.append(evidence)
                            else:
                                counts["docs_translation_invariant_echo"] += 1
                                counts[f"docs_translation_invariant_echo_{locale}"] += 1
                                counts[f"docs_translation_invariant_echo_reason_{reason}"] += 1
                                counts[f"docs_translation_invariant_echo_{locale}_{reason}"] += 1
                                invariant_evidence = {**evidence, "reason": reason}
                                findings.append(
                                    {
                                        "classification": "advisory",
                                        "kind": "docs_translation_invariant_echo",
                                        **invariant_evidence,
                                        "next_action": "retain the independently classified invariant spelling",
                                    }
                                )
                                if len(invariant_echo_samples) < _ECHO_SAMPLE_LIMIT:
                                    invariant_echo_samples.append(invariant_evidence)
                        elif ratio >= _NEAR_ECHO_THRESHOLD:
                            counts["docs_translation_near_echo"] += 1
                            counts[f"docs_translation_near_echo_{locale}"] += 1
                            finding = {
                                "classification": "advisory",
                                "kind": "docs_translation_near_echo",
                                **evidence,
                                "next_action": "review whether this translation is sufficiently localized",
                            }
                            findings.append(finding)
                            if len(near_echo_samples) < _ECHO_SAMPLE_LIMIT:
                                near_echo_samples.append(evidence)
                catalogue_ids = {
                    message_id
                    for (candidate, message_id), states in catalogue_messages.items()
                    if candidate == catalogue and locale in states
                }
                obsolete_ids = catalogue_obsolete.get((locale, catalogue), set())
                catalogue_ids.update(obsolete_ids)
                missing = source_ids - catalogue_ids
                stale = catalogue_ids - source_ids
                counts["docs_source_messages_missing"] += len(missing)
                counts["docs_catalogue_messages_stale"] += len(stale)
                counts[f"docs_catalogue_messages_stale_{locale}"] += len(stale)
                if missing or stale:
                    page_drifted = True
                    findings.append(
                        {
                            "classification": "blocking",
                            "kind": "docs_source_catalogue_drift",
                            "domain": "docs",
                            "path": f"docs/{page}",
                            "locale": locale,
                            "source_messages_missing": len(missing),
                            "catalogue_messages_stale": len(stale),
                            "missing_message_ids": sorted(missing),
                            "stale_message_ids": sorted(stale),
                            "catalogue_messages_obsolete": len(obsolete_ids),
                            "obsolete_message_ids": sorted(obsolete_ids),
                            "next_action": "run python -m dev.docs.i18n, then translate the catalogue delta",
                        }
                    )
            counts["docs_source_drift_pages"] += int(page_drifted)
    except Exception as exc:  # Manifest and filesystem failures must fail closed.
        counts["docs_extraction_failures"] += 1
        findings.append(_docs_extraction_finding(docs_root, exc))
    return _documentation_counts(
        counts,
        source_echo_samples=source_echo_samples,
        invariant_echo_samples=invariant_echo_samples,
        near_echo_samples=near_echo_samples,
    ), findings


def _read_gettext_messages(path: Path) -> dict[str, str] | None:
    """Return canonical identities and source prose from one POT template."""
    if not path.is_file():
        return None
    with path.open(encoding=UTF_8) as handle:
        return {_po_message_identity(message): _po_message_id(message.id) for message in read_po(handle) if message.id}


def _po_message_id(value: object) -> str:
    """Normalize singular and plural Babel message identifiers."""
    return value if isinstance(value, str) else "\x04".join(value)


def _po_message_identity(message: object) -> str:
    """Return a gettext identity that retains msgctxt and plural identity."""
    message_id = _po_message_id(message.id)
    context = message.context
    return f"{context}\x1f{message_id}" if isinstance(context, str) and context else message_id


def _translation_echo_normalize(value: str) -> str:
    """Normalize a translation/source pair for semantic echo comparison."""
    normalized = unicodedata.normalize("NFKC", value)
    normalized = " ".join(normalized.split()).casefold()
    normalized = "".join(" " if unicodedata.category(char).startswith("P") else char for char in normalized)
    return " ".join(normalized.split())


def _translation_similarity(left: str, right: str) -> float:
    """Return a normalized similarity ratio using rapidfuzz when installed."""
    try:
        from rapidfuzz.fuzz import ratio
    except ImportError:
        return SequenceMatcher(None, left, right).ratio()
    return ratio(left, right) / 100


def _translation_invariant_echo_reason(
    source: str,
    locale: str,
    *,
    dictionary: object | None,
    source_dictionary: object | None = None,
    platform_terms: Iterable[str] = (),
) -> str | None:
    """Classify an exact echo only when its invariance is independently provable."""
    from cadrumo.core.product_identity import PRODUCT_IDENTITY

    normalized = _translation_echo_normalize(source)
    product_names = tuple(value for value in PRODUCT_IDENTITY if isinstance(value, str))
    normalized_product_names = {_translation_echo_normalize(value) for value in product_names}
    if normalized in normalized_product_names or _is_product_version_identity(source, product_names):
        return "canonical_product_identity"
    if _MODELO_FORM_RE.search(source):
        return "modelo_form"
    words = _translation_words(source)
    if words and all(word.isupper() or not word.isalpha() for word in words):
        return "platform_format"
    if _PLATFORM_FORMAT_RE.search(source) and len(words) <= 2:
        return "platform_format"
    if _PLATFORM_LABEL_RE.search(source) and any(
        _ARCHITECTURE_TOKEN_RE.search(match.group("details")) for match in _PLATFORM_LABEL_RE.finditer(source)
    ):
        return "platform_format"
    normalized_platform_terms = {_translation_echo_normalize(term) for term in platform_terms}
    if normalized in normalized_platform_terms:
        return "platform_format"
    filtered, excluded = _filtered_translation_text(source)
    if excluded and not any(character.isalpha() for character in filtered):
        return "inline_code"
    dictionary_words = _translation_words(filtered)
    lookup = getattr(dictionary, "lookup", None)
    if locale != "en" and callable(lookup) and dictionary_words and all(lookup(word) for word in dictionary_words):
        source_lookup = getattr(source_dictionary, "lookup", None)
        source_is_valid = callable(source_lookup) and all(source_lookup(word) for word in dictionary_words)
        # A single shared loanword/name (for example ``Manual``) is not
        # evidence of an untranslated sentence.  For multiple words, an
        # English-dictionary hit on every word wins over the target hit so a
        # genuine English phrase cannot be silenced by vocabulary overlap.
        if len(dictionary_words) == 1 or not source_is_valid:
            return "target_dictionary_shared_term"
    return None


def _is_product_version_identity(source: str, product_names: Iterable[str]) -> bool:
    """Return whether *source* is only a canonical product name and version."""
    if _VERSION_TOKEN_RE.search(source) is None:
        return False
    remainder = _VERSION_TOKEN_RE.sub(" ", source)
    product_found = False
    for name in sorted(product_names, key=len, reverse=True):
        remainder, substitutions = re.subn(re.escape(name), " ", remainder, flags=re.IGNORECASE)
        product_found = product_found or substitutions > 0
    return product_found and not any(character.isalnum() for character in remainder)


def _platform_identity_terms(repository: Path) -> frozenset[str]:
    """Load platform identity spellings from the canonical download descriptor."""
    descriptor = repository / "docs" / "_data" / "download_channels.toml"
    try:
        with descriptor.open("rb") as handle:
            payload = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError):
        return frozenset()
    channels = payload.get("channel") if isinstance(payload, dict) else None
    if not isinstance(channels, list):
        return frozenset()
    terms: set[str] = set()
    for channel in channels:
        if not isinstance(channel, dict):
            continue
        platform = channel.get("platform")
        if not isinstance(platform, str):
            continue
        for match in _PLATFORM_LABEL_RE.finditer(platform):
            terms.add(_translation_echo_normalize(match.group(0)))
            terms.add(_translation_echo_normalize(match.group("label")))
    return frozenset(terms)


def _ratio(value: int, total: int) -> float:
    """Return a stable zero-safe ratio for an inventory counter."""
    return round(value / total, 6) if total else 0.0


def _documentation_counts(
    counts: Counter[str],
    *,
    source_echo_samples: list[dict[str, object]] | None = None,
    invariant_echo_samples: list[dict[str, object]] | None = None,
    near_echo_samples: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    """Return the stable user-document inventory schema, including zeroes."""
    source_echo_samples = source_echo_samples or []
    invariant_echo_samples = invariant_echo_samples or []
    near_echo_samples = near_echo_samples or []
    return {
        "docs_source_pages": counts["docs_source_pages"],
        "docs_source_messages": counts["docs_source_messages"],
        "docs_catalogue_files_expected": counts["docs_catalogue_files_expected"],
        "docs_catalogue_files_read": counts["docs_catalogue_files_read"],
        "docs_source_drift_pages": counts["docs_source_drift_pages"],
        "docs_source_messages_missing": counts["docs_source_messages_missing"],
        "docs_catalogue_messages_stale": counts["docs_catalogue_messages_stale"],
        "docs_catalogue_messages_obsolete": counts["docs_catalogue_messages_obsolete"],
        "docs_translation_comparisons": counts["docs_translation_comparisons"],
        "docs_translation_source_echo": counts["docs_translation_source_echo"],
        "docs_translation_source_echo_ratio": _ratio(
            counts["docs_translation_source_echo"], counts["docs_translation_comparisons"]
        ),
        "docs_translation_source_echo_samples": source_echo_samples,
        "docs_translation_invariant_echo": counts["docs_translation_invariant_echo"],
        "docs_translation_invariant_echo_ratio": _ratio(
            counts["docs_translation_invariant_echo"], counts["docs_translation_comparisons"]
        ),
        "docs_translation_invariant_echo_samples": invariant_echo_samples,
        "docs_translation_near_echo": counts["docs_translation_near_echo"],
        "docs_translation_near_echo_ratio": _ratio(
            counts["docs_translation_near_echo"], counts["docs_translation_comparisons"]
        ),
        "docs_translation_near_echo_samples": near_echo_samples,
        "docs_extraction_failures": counts["docs_extraction_failures"],
        "docs_orphan_catalogue_files": counts["docs_orphan_catalogue_files"],
        "docs_missing_catalogue_files": counts["docs_missing_catalogue_files"],
        "docs_orphan_source_templates": counts["docs_orphan_source_templates"],
        "docs_generated_english_only_pages": counts["docs_generated_english_only_pages"],
        "docs_generated_spellchecked_pages": counts["docs_generated_spellchecked_pages"],
        "docs_generated_prose_cells": counts["docs_generated_prose_cells"],
        "docs_generated_source_failures": counts["docs_generated_source_failures"],
        **{
            f"docs_catalogue_files_expected_{locale}": counts[f"docs_catalogue_files_expected_{locale}"]
            for locale in ("ca", "es", "hu")
        },
        **{
            f"docs_catalogue_files_read_{locale}": counts[f"docs_catalogue_files_read_{locale}"]
            for locale in ("ca", "es", "hu")
        },
        **{
            f"docs_catalogue_messages_stale_{locale}": counts[f"docs_catalogue_messages_stale_{locale}"]
            for locale in ("ca", "es", "hu")
        },
        **{
            f"docs_catalogue_messages_obsolete_{locale}": counts[f"docs_catalogue_messages_obsolete_{locale}"]
            for locale in ("ca", "es", "hu")
        },
        **{
            f"docs_translation_comparisons_{locale}": counts[f"docs_translation_comparisons_{locale}"]
            for locale in ("ca", "es", "hu")
        },
        **{
            f"docs_translation_source_echo_{locale}": counts[f"docs_translation_source_echo_{locale}"]
            for locale in ("ca", "es", "hu")
        },
        **{
            f"docs_translation_invariant_echo_{locale}": counts[f"docs_translation_invariant_echo_{locale}"]
            for locale in ("ca", "es", "hu")
        },
        **{
            f"docs_translation_invariant_echo_reason_{reason}": counts[
                f"docs_translation_invariant_echo_reason_{reason}"
            ]
            for reason in _INVARIANT_ECHO_REASONS
        },
        **{
            f"docs_translation_invariant_echo_{locale}_{reason}": counts[
                f"docs_translation_invariant_echo_{locale}_{reason}"
            ]
            for locale in ("ca", "es", "hu")
            for reason in _INVARIANT_ECHO_REASONS
        },
        **{
            f"docs_translation_near_echo_{locale}": counts[f"docs_translation_near_echo_{locale}"]
            for locale in ("ca", "es", "hu")
        },
    }


def _docs_extraction_finding(path: Path, exc: BaseException) -> dict[str, object]:
    """Normalize a user-document discovery/extraction tool failure."""
    return {
        "classification": "blocking",
        "kind": "docs_source_extraction_failure",
        "domain": "docs",
        "path": path.as_posix(),
        "error_type": type(exc).__name__,
        "detail": str(exc),
        "next_action": "restore the user-doc gettext extraction path, then rerun check-locales",
    }


def _visible_document_prose(path: Path) -> tuple[tuple[int, str], ...]:
    """Extract visible RST/Markdown prose while excluding literal syntax."""
    if path.suffix == ".rst":
        from docutils import nodes
        from docutils.core import publish_doctree

        source = path.read_text(encoding=UTF_8)
        document = publish_doctree(
            source,
            source_path=str(path),
            settings_overrides={"report_level": 5, "halt_level": 6, "warning_stream": io.StringIO()},
        )
        excluded = (nodes.literal, nodes.literal_block, nodes.option_string, nodes.raw)
        blocks: list[tuple[int, str]] = []
        blocks_to_read = (nodes.title, nodes.paragraph, nodes.term, nodes.caption)
        for node in document.findall(lambda candidate: isinstance(candidate, blocks_to_read)):
            parts = [str(text) for text in node.findall(nodes.Text) if not _node_has_ancestor(text, excluded)]
            value = " ".join("".join(parts).split())
            if value:
                blocks.append((int(node.line or 0), value))
        return tuple(blocks)
    from markdown_it import MarkdownIt

    tokens = MarkdownIt("commonmark").parse(path.read_text(encoding=UTF_8))
    return tuple(
        ((token.map or [0])[0] + 1, " ".join(child.content for child in (token.children or ()) if child.type == "text"))
        for token in tokens
        if token.type == "inline"
        if any(child.type == "text" and child.content.strip() for child in (token.children or ()))
    )


def _embedded_document_language_prose(path: Path) -> tuple[tuple[int, str, str], ...]:
    """Extract visible HTML fragments whose markup declares another language."""
    source = path.read_text(encoding=UTF_8)
    blocks: list[tuple[int, str, str]] = []
    for match in _TRANSLATION_HTML_LANGUAGE_RE.finditer(source):
        language = match.group("locale").casefold()
        if language not in _LOCALES:
            continue
        text = _filtered_translation_text(match.group("body"))[0]
        if text:
            blocks.append((source.count("\n", 0, match.start()) + 1, language, text))
    return tuple(blocks)


def _node_has_ancestor(node: object, node_types: tuple[type[object], ...]) -> bool:
    """Return whether a docutils node is nested below excluded syntax."""
    parent = getattr(node, "parent", None)
    while parent is not None:
        if isinstance(parent, node_types):
            return True
        parent = getattr(parent, "parent", None)
    return False


def _po_translation_strings(value: object) -> tuple[str, ...]:
    """Return every gettext translation form without treating an empty plural tuple as complete."""
    if isinstance(value, str):
        return (value,)
    if isinstance(value, tuple) and all(isinstance(item, str) for item in value):
        return value
    return ()


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
    blocking_inventory_findings = [
        finding for finding in inventory_findings if finding.get("classification") == "blocking"
    ]
    unassigned["inventory_violations"] = len(blocking_inventory_findings)
    if blocking_inventory_findings:
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
