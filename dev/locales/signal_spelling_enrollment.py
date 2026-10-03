"""Spelling enrollment for the authoritative locale audit."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping

from .signal_contracts import DictionaryLike, ExcludedStructuralInventory
from .signal_policy import LOCALES, SPELLING_SURFACES
from .signal_spelling_segments import spanish_word_context, translation_spelling_segments


def spelling_surface(key: str) -> str:
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


def excluded_structural_inventory(excluded: Counter[tuple[str, str]]) -> ExcludedStructuralInventory:
    """Return stable structural-exclusion totals for every surface/locale."""
    by_surface_locale = {
        f"{surface}/{locale}": excluded[(surface, locale)] for surface in SPELLING_SURFACES for locale in LOCALES
    }
    return {
        "excluded_structural_tokens": sum(excluded.values()),
        "excluded_structural_tokens_by_surface_locale": by_surface_locale,
    }


def enroll_spelling_locale(
    locale: str,
    required_keys: set[str],
    locale_leaves: dict[str, dict[str, object]],
    additional_values: dict[str, dict[str, str]] | None,
    keys_by_word: dict[str, dict[str, set[tuple[str, str]]]],
    cell_words: dict[tuple[str, str], frozenset[str]],
    cell_words_by_language: dict[tuple[str, str], dict[str, frozenset[str]]],
    cell_excluded_structural_tokens: dict[tuple[str, str], int],
    cell_text: dict[tuple[str, str], str],
    excluded_by_surface_locale: Counter[tuple[str, str]],
    enrolled_cells_by_locale: Counter[str],
    prose_cells_by_locale: Counter[str],
    structural_only_cells_by_locale: Counter[str],
) -> None:
    """Enroll spelling locale."""
    leaves = locale_leaves.get(locale, {})
    values = {key: leaves.get(key) for key in required_keys}
    values.update((additional_values or {}).get(locale, {}))
    for key, value in sorted(values.items()):
        enroll_spelling_cell(
            key,
            value,
            locale,
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


def enroll_spelling_cell(
    key: str,
    value: object,
    locale: str,
    keys_by_word: dict[str, dict[str, set[tuple[str, str]]]],
    cell_words: dict[tuple[str, str], frozenset[str]],
    cell_words_by_language: dict[tuple[str, str], dict[str, frozenset[str]]],
    cell_excluded_structural_tokens: dict[tuple[str, str], int],
    cell_text: dict[tuple[str, str], str],
    excluded_by_surface_locale: Counter[tuple[str, str]],
    enrolled_cells_by_locale: Counter[str],
    prose_cells_by_locale: Counter[str],
    structural_only_cells_by_locale: Counter[str],
) -> None:
    """Enroll spelling cell."""
    if not isinstance(value, str):
        return
    enrolled_cells_by_locale[locale] += 1
    cell = (locale, value)
    if cell not in cell_words:
        cache_spelling_cell_words(
            value, key, locale, cell, cell_words, cell_words_by_language, cell_excluded_structural_tokens
        )
    words = cell_words[cell]
    excluded_by_surface_locale[(spelling_surface(key), locale)] += cell_excluded_structural_tokens[cell]
    cell_text[(locale, key)] = value
    if words:
        prose_cells_by_locale[locale] += 1
    else:
        structural_only_cells_by_locale[locale] += 1
    for dictionary_locale, language_words in cell_words_by_language[cell].items():
        locale_words = keys_by_word.setdefault(dictionary_locale, defaultdict(set))
        for word in language_words:
            locale_words[word].add((locale, key))


def check_dictionary_spelling_words(
    dictionary_locale: str,
    words: dict[str, set[tuple[str, str]]],
    dictionaries: Mapping[str, DictionaryLike],
    cell_text: dict[tuple[str, str], str],
    unknown_words: set[tuple[str, str]],
    unknown_by_cell: dict[tuple[str, str], set[str]],
) -> None:
    """Check dictionary spelling words."""
    dictionary = dictionaries[dictionary_locale]
    for word in words:
        if dictionary.lookup(word):
            continue
        for owner_locale, key in words[word]:
            record_unknown_spelling_word(
                owner_locale, key, word, dictionary_locale, dictionaries, cell_text, unknown_words, unknown_by_cell
            )


def record_unknown_spelling_word(
    owner_locale: str,
    key: str,
    word: str,
    dictionary_locale: str,
    dictionaries: Mapping[str, DictionaryLike],
    cell_text: dict[tuple[str, str], str],
    unknown_words: set[tuple[str, str]],
    unknown_by_cell: dict[tuple[str, str], set[str]],
) -> None:
    """Record unknown spelling word."""
    owner_cell = (owner_locale, key)
    value = cell_text[owner_cell]
    foreign_context = spanish_word_context(
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
            return
        unknown_words.add(("es", word.casefold()))
        unknown_by_cell[owner_cell].add(word)
        return
    unknown_words.add((dictionary_locale, word.casefold()))
    unknown_by_cell[owner_cell].add(word)


def cache_spelling_cell_words(
    value: str,
    key: str,
    locale: str,
    cell: tuple[str, str],
    cell_words: dict[tuple[str, str], frozenset[str]],
    cell_words_by_language: dict[tuple[str, str], dict[str, frozenset[str]]],
    cell_excluded_structural_tokens: dict[tuple[str, str], int],
) -> None:
    """Cache spelling cell words."""
    language_segments = translation_spelling_segments(value, key, locale)
    language_words_mutable: dict[str, set[str]] = defaultdict(set)
    for language, words, _excluded in language_segments:
        language_words_mutable[language].update(word for word in words if len(word) > 1)
    language_words = {language: frozenset(words) for language, words in language_words_mutable.items()}
    cell_words_by_language[cell] = language_words
    cell_words[cell] = frozenset(word for words in language_words.values() for word in words)
    excluded_tokens = sum(excluded for _language, _words, excluded in language_segments)
    cell_excluded_structural_tokens[cell] = excluded_tokens
