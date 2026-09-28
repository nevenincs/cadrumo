"""Canonical Spanish lexical tokenisation and Snowball stemming primitives.

The command-discovery and corpus-grounding indexes share the same two lexical
operations: Unicode word extraction after case normalisation, and Spanish
Snowball stemming. Keeping those primitives here makes both indexes build and
query the same lexical vocabulary while leaving each index responsible for its
own FTS layout and ranking policy.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from functools import lru_cache

__all__ = [
    "SpanishStemmer",
    "spanish_stemmer",
    "spanish_word_tokens",
    "stem_spanish_terms",
    "stem_spanish_text",
]

_WORD_RE = re.compile(r"\w+", re.UNICODE)


SpanishStemmer = Callable[[list[str]], list[str]]
"""The narrow Snowball contract the application's lexical indexes consume."""


_STEM_CACHE_SIZE = 1 << 17
"""Distinct words remembered per stemmer; the whole bundled corpus fits many times over."""


def spanish_stemmer() -> SpanishStemmer:
    """Build the Spanish Snowball stemmer used by every shipped lexical index.

    A stem depends on the word alone, and the corpus repeats a small
    vocabulary millions of times: stemming every occurrence made the pure
    Python Snowball implementation most of a full index build. Each distinct
    word is therefore stemmed once and remembered, within a bound.
    """
    import snowballstemmer

    stem_uncached = snowballstemmer.stemmer("spanish").stemWords

    @lru_cache(maxsize=_STEM_CACHE_SIZE)
    def stem_word(word: str) -> str:
        return stem_uncached([word])[0]

    def stem_words(words: list[str]) -> list[str]:
        return [stem_word(word) for word in words]

    return stem_words


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
    for word in stemmer(words):
        if not isinstance(word, str):
            raise TypeError("the Spanish stemmer returned a non-string token")
        stemmed.append(word)
    return tuple(stemmed)


def stem_spanish_text(stemmer: SpanishStemmer, text: str) -> str:
    """Return the space-separated Spanish stems for the words in ``text``."""
    return " ".join(stem_spanish_terms(stemmer, spanish_word_tokens(text)))
