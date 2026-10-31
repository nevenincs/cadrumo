"""Spelling for the authoritative locale audit."""

from __future__ import annotations

from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
from typing import Final

from ._spelling import SpellingToolError, load_dictionaries
from .signal_contracts import SpellingInventory
from .signal_discovery import signal_key_domain
from .signal_spelling_enrollment import (
    check_dictionary_spelling_words,
    enroll_spelling_locale,
    excluded_structural_inventory,
)

# Exact lowercase search aliases: IBI is named in the ibi_* category labels,
# and IRPF in _data/terminology/concepts/irpf.toml. These are accepted only on
# bilingual search-keyword surfaces, never as general prose vocabulary.
_SPANISH_SEARCH_ABBREVIATIONS: Final[frozenset[str]] = frozenset({"ibi", "irpf"})
# Exact lowercase aliases in the three keyword families below. They name
# TGSS, PC, ADSL, ITV, Cadrumo, URL, DEHú, REPL, BOE and TUI. The category
# aliases reflect bank-statement terminology; palette/navigation aliases name
# their actual services, link format and views. Search consumes lowercase
# words, and dehu deliberately supports queries without DEHú's accent.
# This is a closed alias inventory, not a rule accepting arbitrary acronyms,
# name variants, accent loss, or these tokens in translated prose.
_SEARCH_NAME_AND_INITIALISM_ALIASES: Final[frozenset[str]] = frozenset(
    {"tgss", "pc", "adsl", "itv", "cadrumo", "url", "dehu", "repl", "boe", "tui"}
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
    _discard_known_search_keywords(unknown_by_cell, dictionaries.get("es"), dictionaries.get("en"))
    unknown_words = _collect_unknown_words(unknown_by_cell)
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


def _is_spanish_search_keyword(word: str, dictionary: object) -> bool:
    """Accept Spanish search terms with omitted diacritics in keyword fields."""
    if word in _SPANISH_SEARCH_ABBREVIATIONS:
        return True
    lookup = getattr(dictionary, "lookup", None)
    if not callable(lookup):
        return False
    if lookup(word):
        return True
    # Search keywords deliberately omit Spanish accents. Restore zero, one, or
    # two diacritics and require an exact Spanish dictionary entry; unrelated
    # misspellings therefore remain visible to the locale audit.
    letters = tuple((index, char) for index, char in enumerate(word.casefold()) if char in "aeioun")
    accent = {"a": "á", "e": "é", "i": "í", "o": "ó", "u": "ú", "n": "ñ"}
    for count in (1, 2):
        for selected in combinations(letters, count):
            candidate = list(word.casefold())
            for index, char in selected:
                candidate[index] = accent[char]
            if lookup("".join(candidate)):
                return True
    return False


def is_search_keyword_surface(key: str) -> bool:
    """Identify the three presentation families that declare search aliases."""
    return (
        key.startswith("desktop.ledger.category_keywords.")
        or key.startswith("desktop.palette.keywords.")
        or (key.startswith("navigation.view.") and key.endswith(".keywords"))
    )


def _is_known_search_keyword(word: str, spanish_dictionary: object | None, english_dictionary: object | None) -> bool:
    """Check an alias against the exact inventory and its two dictionaries."""
    english_lookup = getattr(english_dictionary, "lookup", None)
    return (
        word in _SEARCH_NAME_AND_INITIALISM_ALIASES
        or (callable(english_lookup) and bool(english_lookup(word)))
        or (spanish_dictionary is not None and _is_spanish_search_keyword(word, spanish_dictionary))
    )


def _discard_known_search_keywords(
    unknown_by_cell: dict[tuple[str, str], set[str]],
    spanish_dictionary: object | None,
    english_dictionary: object | None,
) -> None:
    """Validate bilingual aliases on the three declared search-keyword surfaces.

    Palette actions consume their own keywords and navigation-view keywords
    through ``scoreAction``; ledger choices consume category keywords through
    ``categoryKeywords``. These are searchable aliases, including English and
    accentless Spanish, rather than the translated labels beside them.
    """
    english_lookup = getattr(english_dictionary, "lookup", None)
    if spanish_dictionary is None and not callable(english_lookup):
        return
    for cell, words in tuple(unknown_by_cell.items()):
        _locale, key = cell
        if not is_search_keyword_surface(key):
            continue
        accepted = {word for word in words if _is_known_search_keyword(word, spanish_dictionary, english_dictionary)}
        words.difference_update(accepted)
        if not words:
            del unknown_by_cell[cell]


def _collect_unknown_words(unknown_by_cell: dict[tuple[str, str], set[str]]) -> set[tuple[str, str]]:
    """Collect remaining unknown words by locale for the audit inventory."""
    return {(locale, word) for (locale, _key), words in unknown_by_cell.items() for word in words}
