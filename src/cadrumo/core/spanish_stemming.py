"""Canonical Spanish lexical tokenisation and Snowball stemming primitives.

The command-discovery and corpus-grounding indexes share the same two lexical
operations: Unicode word extraction after case normalisation, and Spanish
Snowball stemming. Keeping those primitives here makes both indexes build and
query the same lexical vocabulary while leaving each index responsible for its
own FTS layout and ranking policy.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Protocol

__all__ = [
    "SpanishStemmer",
    "spanish_stemmer",
    "spanish_word_tokens",
    "stem_spanish_terms",
    "stem_spanish_text",
]

_WORD_RE = re.compile(r"\w+", re.UNICODE)


class SpanishStemmer(Protocol):
    """The narrow Snowball contract the application's lexical indexes consume."""

    def stemWords(self, words: list[str]) -> list[str]:  # noqa: N802 - third-party API
        """Return the Snowball stem of each word in ``words``, in order."""
        ...


def spanish_stemmer() -> SpanishStemmer:
    """Build the Spanish Snowball stemmer used by every shipped lexical index."""
    import snowballstemmer

    # CAST-RATIONALE-SPANISH-STEMMER-PROTOCOL: snowballstemmer ships no static
    # return protocol, while this boundary consumes only its stemWords method.
    return snowballstemmer.stemmer("spanish")


def spanish_word_tokens(text: str) -> tuple[str, ...]:
    """Return lowercase Unicode word tokens from ``text`` in source order."""
    tokens: list[str] = []
    for token in _WORD_RE.findall(text.lower()):
        if not isinstance(token, str):
            raise TypeError("the word tokenizer returned a non-string token")
        tokens.append(token)
    return tuple(tokens)


def stem_spanish_terms(stemmer: SpanishStemmer, terms: Iterable[str]) -> tuple[str, ...]:
    """Stem a sequence of Spanish lexical terms without changing their order."""
    words = list(terms)
    if not words:
        return ()
    stemmed: list[str] = []
    for word in stemmer.stemWords(words):
        if not isinstance(word, str):
            raise TypeError("the Spanish stemmer returned a non-string token")
        stemmed.append(word)
    return tuple(stemmed)


def stem_spanish_text(stemmer: SpanishStemmer, text: str) -> str:
    """Return the space-separated Spanish stems for the words in ``text``."""
    return " ".join(stem_spanish_terms(stemmer, spanish_word_tokens(text)))
