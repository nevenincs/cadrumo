"""Canonical accent-folding primitive for diacritic-insensitive text matching.

Nine call sites across ``core``, ``application``, ``domain``, and ``adapters``
independently hand-rolled the same NFKD-decompose-and-strip-combining-marks
routine (label matching, denylist matching, dedup fingerprinting, header
aliasing, terminology search, corpus-text normalisation). This module gives
the shared inner step one canonical home; each caller keeps composing its own
trailing transform (whitespace collapse, non-alphanumeric squeeze, HTML-tag
strip, casing) on top of it.
"""

from __future__ import annotations

import unicodedata

__all__ = ["fold_diacritics", "unicode_compose"]


def fold_diacritics(text: str) -> str:
    """Return *text* with combining diacritical marks removed.

    NFKD-decomposes *text*, then drops every character in Unicode category
    ``Mn`` (Mark, nonspacing) — the combining accents NFKD decomposition
    exposes (``"ó"`` -> ``"o"`` + U+0301 COMBINING ACUTE ACCENT, which this
    function then drops). Every other codepoint passes through unchanged,
    including one with no ASCII-compatible decomposition (an em dash, the
    euro sign, ``"ø"``): this function folds ACCENTS, it does not
    transliterate to ASCII. A caller that also needs to discard such
    codepoints composes its own ``str.encode("ascii", "ignore")`` pass
    afterward rather than relying on this function to do it.

    Case is left untouched. Callers that need case-insensitive matching
    compose this with their own :meth:`str.casefold` (preferred over
    :meth:`str.lower` for caseless comparison) call, since the diacritic
    fold and the case fold are orthogonal concerns.

    Args:
        text: The text to fold.

    Returns:
        *text* with every combining diacritical mark removed.
    """
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(char for char in decomposed if unicodedata.category(char) != "Mn")


def unicode_compose(text: str) -> str:
    """Return *text* NFKC-composed, every diacritic and printed character kept.

    A DIFFERENT normalization form from :func:`fold_diacritics`, for a
    different job: two documents printing the same figure can differ in
    whether a composed character (``"ó"``) arrived pre-composed or as a base
    letter plus a combining accent, with no difference in what was printed.
    NFKC folds that representational gap closed without touching accents,
    case, digits, or punctuation — unlike :func:`fold_diacritics`, this must
    never be used where the accent itself is evidence to preserve.

    Args:
        text: The text to compose.

    Returns:
        *text* in NFKC normal form.
    """
    return unicodedata.normalize("NFKC", text)
