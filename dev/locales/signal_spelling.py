"""Spelling for the authoritative locale audit."""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

from ._spelling import SpellingToolError, load_dictionaries
from .signal_contracts import SpellingInventory
from .signal_discovery import signal_key_domain
from .signal_spelling_enrollment import (
    check_dictionary_spelling_words,
    enroll_spelling_locale,
    excluded_structural_inventory,
)


def spellcheck_catalogues(
    required_keys: set[str],
    locale_leaves: dict[str, dict[str, object]],
    repository: Path,
    *,
    additional_values: dict[str, dict[str, str]] | None = None,
) -> tuple[dict[tuple[str, str], tuple[str, ...]], SpellingInventory, list[dict[str, object]]]:
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
        enroll_spelling_locale(
            locale,
            required_keys,
            locale_leaves,
            additional_values,
            keys_by_word,
            cell_words,
            cell_words_by_language,
            cell_excluded_structural_tokens,
            cell_text,
            excluded_by_surface_locale,
            enrolled_cells_by_locale,
            prose_cells_by_locale,
            structural_only_cells_by_locale,
        )
    unknown_words: set[tuple[str, str]] = set()
    try:
        dictionaries = load_dictionaries(repository)
        for dictionary_locale, words in keys_by_word.items():
            check_dictionary_spelling_words(
                dictionary_locale, words, dictionaries, cell_text, unknown_words, unknown_by_cell
            )
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
        excluded_inventory = excluded_structural_inventory(excluded_by_surface_locale)
        failure_inventory: SpellingInventory = {
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
            "excluded_structural_tokens": excluded_inventory["excluded_structural_tokens"],
            "excluded_structural_tokens_by_surface_locale": excluded_inventory[
                "excluded_structural_tokens_by_surface_locale"
            ],
        }
        return (
            {},
            failure_inventory,
            [failure],
        )
    spelling = {cell: tuple(sorted(words, key=str.casefold)) for cell, words in unknown_by_cell.items()}
    unknown_findings: list[dict[str, object]] = [
        {
            "classification": "blocking",
            "kind": "translation_spelling_unknown",
            "domain": (
                "docs"
                if key.startswith("parallel:docs/")
                else "structured_data"
                if key.startswith("parallel:")
                else signal_key_domain(key)
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
    excluded_inventory = excluded_structural_inventory(excluded_by_surface_locale)
    spelling_inventory: SpellingInventory = {
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
        "excluded_structural_tokens": excluded_inventory["excluded_structural_tokens"],
        "excluded_structural_tokens_by_surface_locale": excluded_inventory[
            "excluded_structural_tokens_by_surface_locale"
        ],
    }
    return (
        spelling,
        spelling_inventory,
        unknown_findings,
    )
