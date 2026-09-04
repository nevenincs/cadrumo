"""Canonical accent-folding primitive for diacritic-insensitive text matching.

Nine call sites across ``core``, ``application``, ``domain``, and ``adapters``
independently hand-rolled the same NFKD-decompose-and-strip-combining-marks
routine (label matching, denylist matching, dedup fingerprinting, header
aliasing, terminology search, corpus-text normalisation). This module gives
the shared inner step one canonical home; each caller keeps composing its own
trailing transform (whitespace collapse, non-alphanumeric squeeze, HTML-tag
strip, casing) on top of it.

Where two callers compose the SAME trailing transform, that composition earns a
name here rather than being written twice: :func:`fold_for_matching` is the
fold-collapse-casefold pipeline the terminology search and the AEAT marker
matcher had each written out.
"""

from __future__ import annotations

import re
import unicodedata

__all__ = ["fold_diacritics", "fold_for_matching", "fold_printed_phrase", "unicode_compose"]

#: A run of one or more whitespace characters, collapsed to a single space by
#: :func:`fold_for_matching`. Distinct from a single-whitespace pattern used to
#: DELETE whitespace, which is a different operation and is why the deleting
#: caller in the PDF label reader names its pattern for what it does.
_WHITESPACE_RUN_RE = re.compile(r"\s+")

#: Every codepoint in Unicode category ``Mn`` (Mark, nonspacing), mapped to
#: ``None`` for :meth:`str.translate`. Built once at import so folding a
#: string costs one C-level table lookup per character instead of one
#: ``unicodedata.category`` call: a cold bundled-registry load profiled at
#: 11M+ ``category`` calls inside this function alone, all doing the same
#: per-character category check this table now answers by lookup.
_COMBINING_MARK_STRIP_TABLE = {
    codepoint: None for codepoint in range(0x110000) if unicodedata.category(chr(codepoint)) == "Mn"
}


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
    return unicodedata.normalize("NFKD", text).translate(_COMBINING_MARK_STRIP_TABLE)


def fold_printed_phrase(printed: str) -> str:
    """Return the form a printed multi-word phrase is matched under.

    Three transforms and no more, in this order: fold case, fold accents,
    collapse every run of whitespace to one space and trim the ends. Each earns
    its place against how a phrase arrives from a document rather than from a
    keyboard -- typography is the issuer's choice, a phrase set as a line wraps
    with the break inside it, and a text layer or an OCR pass routinely returns
    the ASCII spelling of an accented word.

    **Punctuation is deliberately NOT stripped**, which is the transform a
    fourth one would be. A vocabulary can carry a name whose stops are part of
    it, and squeezing punctuation generally starts matching strings that are not
    phrases at all.

    Case folds BEFORE accents, and the order is load-bearing rather than
    incidental: a caller that folds accents first and cases afterward is a
    different function, because :meth:`str.casefold` can itself emit a combining
    mark that the earlier accent fold is no longer there to remove.

    Args:
        printed: The phrase as it was printed.

    Returns:
        The normalised form to match on.
    """
    return " ".join(fold_diacritics(printed.casefold()).split())


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


def fold_for_matching(text: str) -> str:
    """Fold *text* to the form two matchers compare against.

    Drops diacritics, collapses every run of whitespace to one space, trims the
    ends, and casefolds. This is the exact pipeline the terminology search and
    the AEAT response-marker matcher had each spelled out.

    The casefold runs last, which is equivalent to casefolding first: neither
    ``str.casefold`` nor the whitespace collapse affects what the other does.
    That equivalence is what let the two callers, which ordered the steps
    differently, converge on one function.

    Args:
        text: Raw text to fold.

    Returns:
        The folded, whitespace-collapsed, casefolded form.
    """
    return _WHITESPACE_RUN_RE.sub(" ", fold_diacritics(text)).strip().casefold()
