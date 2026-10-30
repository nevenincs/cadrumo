"""Spelling segments for the authoritative locale audit."""

from __future__ import annotations

import re

from .signal_contracts import DictionaryLike
from .signal_policy import LOCALES
from .signal_syntax import (
    MODELO_FORM_RE,
    TRANSLATION_CLAVE_NAME_RE,
    TRANSLATION_HTML_LANGUAGE_RE,
    TRANSLATION_HUNGARIAN_DATE_RE,
    TRANSLATION_HUNGARIAN_HYPHENATED_SUFFIX_RE,
    TRANSLATION_HUNGARIAN_PERCENT_SUFFIX_RE,
    TRANSLATION_LEGAL_TITLE_RE,
    TRANSLATION_LITERAL_RE,
    TRANSLATION_MARKDOWN_LINK_CONTEXT_RE,
    TRANSLATION_RST_LINK_RE,
    TRANSLATION_SPANISH_AUTHORITY_RE,
    TRANSLATION_SPANISH_TAX_TERM_RE,
)
from .signal_tokens import filtered_translation_text, translation_words

# These two exact Catalan forms were attested by the locale findings. Keep the
# exception closed over complete forms; a productive suffix rule could conceal
# a misspelled or malformed host from the dictionary check.
_CATALAN_HYPHENATED_CLITIC_RE = re.compile(r"(?P<form>Mantén-lo|revisar-los)(?![^\W\d_])")


def html_spelling_segments(value: str, foreign: list[tuple[int, int, str, str, int]]) -> None:
    """Html spelling segments."""
    for match in TRANSLATION_HTML_LANGUAGE_RE.finditer(value):
        language = match.group("locale").casefold()
        if language in LOCALES:
            foreign.append(
                (
                    match.start(),
                    match.end(),
                    language,
                    match.group("body"),
                    filtered_translation_text(match.group(0))[1],
                )
            )


def markdown_link_spelling_segments(value: str, foreign: list[tuple[int, int, str, str, int]]) -> None:
    """Markdown link spelling segments."""
    for match in TRANSLATION_MARKDOWN_LINK_CONTEXT_RE.finditer(value):
        target = match.group("angle_target") or match.group("target") or ""
        if is_legal_authority_target(target) and is_spanish_legal_label(match.group("label")):
            foreign.append(
                (
                    match.start(),
                    match.end(),
                    "es",
                    match.group("label"),
                    filtered_translation_text(match.group(0))[1],
                )
            )


def rst_link_spelling_segments(value: str, foreign: list[tuple[int, int, str, str, int]]) -> None:
    """Rst link spelling segments."""
    for match in TRANSLATION_RST_LINK_RE.finditer(value):
        if is_legal_authority_target(match.group("target")) and is_spanish_legal_label(match.group("label")):
            foreign.append(
                (
                    match.start(),
                    match.end(),
                    "es",
                    match.group("label"),
                    filtered_translation_text(match.group(0))[1],
                )
            )


def is_spanish_legal_label(label: str) -> bool:
    """Recognize Spanish official labels independently of their destination."""
    if TRANSLATION_HTML_LANGUAGE_RE.search(label):
        return False
    return bool(
        TRANSLATION_LEGAL_TITLE_RE.match(label.strip()) or TRANSLATION_SPANISH_AUTHORITY_RE.fullmatch(label.strip())
    )


def legal_title_spelling_segments(
    value: str, default_locale: str, foreign: list[tuple[int, int, str, str, int]]
) -> None:
    """Legal title spelling segments."""
    if default_locale != "es":
        literal_ranges = tuple((match.start(), match.end()) for match in TRANSLATION_LITERAL_RE.finditer(value))
        for pattern in (
            MODELO_FORM_RE,
            TRANSLATION_LEGAL_TITLE_RE,
            TRANSLATION_SPANISH_AUTHORITY_RE,
            TRANSLATION_SPANISH_TAX_TERM_RE,
            TRANSLATION_CLAVE_NAME_RE,
        ):
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
                        filtered_translation_text(text)[1],
                    )
                )


def translation_spelling_segments(
    value: str,
    key: str,
    default_locale: str,
) -> tuple[tuple[str, tuple[str, ...], int], ...]:
    """Split prose by explicit language-bearing markup and legal identifiers.

    The returned text is already filtered for transport syntax.  A Spanish legal
    label, a ``lang``-annotated HTML element, or a numbered form/legal title is
    therefore checked with the dictionary that owns that rendered text rather
    than with the language of the surrounding catalogue cell.
    """
    foreign: list[tuple[int, int, str, str, int]] = []
    html_spelling_segments(value, foreign)
    markdown_link_spelling_segments(value, foreign)
    rst_link_spelling_segments(value, foreign)
    legal_title_spelling_segments(value, default_locale, foreign)

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
    words, excluded = locale_spelling_words("".join(masked), default_locale)
    segments: list[tuple[str, tuple[str, ...], int]] = [(default_locale, words, excluded)]
    for _start, _end, language, text, structural_excluded in accepted:
        words, _excluded = locale_spelling_words(text, language)
        wrapper_excluded = structural_excluded - filtered_translation_text(text)[1]
        segments.append((language, words, wrapper_excluded + _excluded))
    return tuple(segments)


def locale_spelling_words(value: str, locale: str) -> tuple[tuple[str, ...], int]:
    """Exclude locale-specific notation before generic syntax splits its tokens."""
    excluded = 0
    if locale == "hu":
        value, matches = TRANSLATION_HUNGARIAN_DATE_RE.subn(" ", value)
        excluded += matches
        # Preserve the numeric stem for the ordinary number filter; remove
        # only the attested Hungarian suffix on percentage expressions.
        value, matches = TRANSLATION_HUNGARIAN_PERCENT_SUFFIX_RE.subn(lambda match: match.group("stem"), value)
        excluded += matches
        # Keep the stem visible to ordinary spelling checks; only the
        # recognized Hungarian suffix is structural notation.
        value, matches = TRANSLATION_HUNGARIAN_HYPHENATED_SUFFIX_RE.subn(lambda match: match.group("stem"), value)
        excluded += matches
    elif locale == "ca":
        value, matches = _CATALAN_HYPHENATED_CLITIC_RE.subn(lambda match: match.group("form").split("-")[0], value)
        excluded += matches
    filtered, structural_excluded = filtered_translation_text(value)
    # English dictionaries own contractions and possessives as complete words;
    # Catalan elisions still need their lexical word checked separately.
    if locale == "en":
        filtered = filtered.replace("’", "'")
    return (
        translation_words(filtered, preserve_apostrophes=locale == "en", preserve_periods=locale == "hu"),
        excluded + structural_excluded,
    )


def is_legal_authority_target(target: str) -> bool:
    """Recognize legal authority links from their structured destination."""
    normalized = target.casefold()
    return (
        "_generated/legal/" in normalized
        or ".boe.es/" in normalized
        or ".aeat.es/" in normalized
        or "agenciatributaria.gob.es/" in normalized
    )


def spanish_word_context(
    value: str,
    key: str,
    word: str,
    *,
    owner_locale: str,
    dictionary: object | None,
    spanish_dictionary: DictionaryLike | None,
) -> bool:
    """Whether an unknown word sits in structured Spanish legal/name prose."""
    if owner_locale == "es" or spanish_dictionary is None:
        return False
    languages = {
        language
        for language, words, _excluded in translation_spelling_segments(value, key, owner_locale)
        if any(candidate.casefold() == word.casefold() for candidate in words)
    }
    return "es" in languages and owner_locale not in languages
