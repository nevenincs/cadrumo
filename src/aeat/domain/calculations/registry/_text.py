"""Text normalisation helpers for local legal and source corpora."""

from __future__ import annotations

import html
import re


def normalise_corpus_text(text: str) -> str:
    """Normalise corpus text for citation-presence checks."""

    decoded = html.unescape(text).replace("\xa0", " ")
    without_tags = re.sub(r"<[^>]+>", " ", decoded)
    return re.sub(r"\s+", " ", without_tags).strip().lower()
