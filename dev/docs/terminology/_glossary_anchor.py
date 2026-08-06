"""The glossary deep-link anchor scheme, shared by the search injection.

The generated glossary (``dev/docs/glossary_reference.py``) renders each
approved concept's headword through the Sphinx ``glossary`` directive, which
derives the term's HTML id from the headword TEXT, not the concept id. A search
record that deep-links a concept to its definition must therefore target that
headword-derived id, or the link lands on the glossary top instead of the term.

:func:`glossary_term_anchor` reproduces the Sphinx id scheme observed in the
built glossary: Unicode-normalise the headword, strip combining accents, fold
every run of non-``[A-Za-z0-9]`` characters to a single hyphen, preserve case,
and prefix ``term-``. The ``test_glossary_anchor_parity`` gate asserts every
injected concept anchor resolves to a real id in the rendered glossary, so a
Sphinx id-scheme drift fails the build rather than silently shipping a dead
deep link.
"""

from __future__ import annotations

import unicodedata
from typing import Final

__all__ = ["glossary_term_anchor"]

_ANCHOR_PREFIX: Final[str] = "term-"


def glossary_term_anchor(headword: str) -> str:
    """Return the glossary HTML anchor id for a concept headword.

    Args:
        headword: The concept's rendered headword (its Spanish preferred term),
            exactly as the glossary entry's first term line carries it.

    Returns:
        The ``term-...`` anchor id the Sphinx glossary directive generates for
        that headword, suitable for a ``#``-fragment deep link into the built
        ``_generated/glossary.html`` page.
    """
    decomposed = unicodedata.normalize("NFKD", headword)
    ascii_text = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    segments: list[str] = []
    current: list[str] = []
    for ch in ascii_text:
        if ch.isascii() and ch.isalnum():
            current.append(ch)
        elif current:
            segments.append("".join(current))
            current = []
    if current:
        segments.append("".join(current))
    return _ANCHOR_PREFIX + "-".join(segments)
