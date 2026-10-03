"""Spelling segments for the authoritative locale audit."""

from __future__ import annotations

from .signal_contracts import DictionaryLike
from .signal_policy import LOCALES
from .signal_syntax import (
    MODELO_FORM_RE,
    TRANSLATION_HTML_LANGUAGE_RE,
    TRANSLATION_LEGAL_TITLE_RE,
    TRANSLATION_LITERAL_RE,
    TRANSLATION_MARKDOWN_LINK_CONTEXT_RE,
    TRANSLATION_RST_LINK_RE,
)
from .signal_tokens import filtered_translation_text, translation_words


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
        if is_legal_authority_target(target):
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
        if is_legal_authority_target(match.group("target")):
            foreign.append(
                (
                    match.start(),
                    match.end(),
                    "es",
                    match.group("label"),
                    filtered_translation_text(match.group(0))[1],
                )
            )


def legal_title_spelling_segments(
    value: str, default_locale: str, foreign: list[tuple[int, int, str, str, int]]
) -> None:
    """Legal title spelling segments."""
    if default_locale != "es":
        literal_ranges = tuple((match.start(), match.end()) for match in TRANSLATION_LITERAL_RE.finditer(value))
        for pattern in (MODELO_FORM_RE, TRANSLATION_LEGAL_TITLE_RE):
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


def has_spanish_legal_context(value: str, key: str) -> bool:
    """Has spanish legal context."""
    legal_context = (
        "/legal/" in key.casefold()
        or TRANSLATION_LEGAL_TITLE_RE.search(value) is not None
        or MODELO_FORM_RE.search(value) is not None
        or any(is_legal_authority_target(match.group("target")) for match in TRANSLATION_RST_LINK_RE.finditer(value))
        or any(
            is_legal_authority_target(match.group("angle_target") or match.group("target") or "")
            for match in TRANSLATION_MARKDOWN_LINK_CONTEXT_RE.finditer(value)
        )
    )
    return legal_context


def translation_spelling_segments(
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
    filtered, excluded = filtered_translation_text("".join(masked))
    segments: list[tuple[str, tuple[str, ...], int]] = [(default_locale, translation_words(filtered), excluded)]
    for _start, _end, language, text, structural_excluded in accepted:
        segments.append((language, translation_words(filtered_translation_text(text)[0]), structural_excluded))
    return tuple(segments)


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
    legal_context = has_spanish_legal_context(value, key)
    words = list(translation_words(value))
    try:
        index = next(index for index, candidate in enumerate(words) if candidate.casefold() == word.casefold())
    except StopIteration:
        return legal_context
    if has_spanish_word_neighbour(words, index, legal_context, spanish_dictionary, dictionary):
        return True
    return legal_context and bool(TRANSLATION_LEGAL_TITLE_RE.search(value) or MODELO_FORM_RE.search(value))


def has_spanish_word_neighbour(
    words: list[str], index: int, legal_context: bool, spanish_dictionary: DictionaryLike, dictionary: object | None
) -> bool:
    """Has spanish word neighbour."""
    for neighbour in words[max(0, index - 1) : index] + words[index + 1 : index + 2]:
        if spanish_dictionary.lookup(neighbour) and neighbour[:1].isupper():
            return True
    return False
