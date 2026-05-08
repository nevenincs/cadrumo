"""Text normalisation helpers for local legal and source corpora."""

from __future__ import annotations

import html
import re
import unicodedata


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
    without_tags = re.sub(r"<[a-zA-Z!/?][^<>\s]{0,200}>", " ", decoded)
    without_marks = "".join(
        char for char in unicodedata.normalize("NFKD", without_tags) if not unicodedata.combining(char)
    )
    return re.sub(r"\s+", " ", without_marks).strip().lower()
