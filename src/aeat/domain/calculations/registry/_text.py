"""Text normalisation helpers for local legal and source corpora."""

from __future__ import annotations

import html
import re
import unicodedata


def normalise_corpus_text(text: str) -> str:
    """Normalise corpus text for citation-presence checks."""

    decoded = html.unescape(text).replace("\xa0", " ")
    without_tags = re.sub(r"<[^>]+>", " ", decoded)
    without_marks = "".join(
        char for char in unicodedata.normalize("NFKD", without_tags) if not unicodedata.combining(char)
    )
    return re.sub(r"\s+", " ", without_marks).strip().lower()
