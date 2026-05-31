"""Text normalisation helpers for local legal and source corpora."""

from __future__ import annotations

import html
import re
import unicodedata

_HTML_TAG_RE = re.compile(r"<[a-zA-Z!/?][^<>\s]{0,200}>")
_COMBINING_MARK_RE = re.compile(r"[\u0300-\u036f]+")
_WHITESPACE_RE = re.compile(r"\s+")


def normalise_corpus_text(text: str) -> str:
    """Normalise corpus text for citation-presence checks.

    The HTML-tag stripper only matches well-formed tags whose `<`
    immediately precedes a tag-name character (letter, slash, or
    `!`/`?`) and whose body is short and contains no spaces — so that
    bare comparison operators (e.g. ``< 500 euros`` and ``< 3 años``
    that AEAT's manuals use as math notation) and other unbalanced
    angle brackets do not inadvertently swallow long spans of prose.
    """
    decoded = html.unescape(text).replace("\xa0", " ")
    without_tags = _HTML_TAG_RE.sub(" ", decoded)
    without_marks = _COMBINING_MARK_RE.sub("", unicodedata.normalize("NFKD", without_tags))
    return _WHITESPACE_RE.sub(" ", without_marks).strip().lower()
