from typing import Protocol

class _SpanishStemmer(Protocol):
    def stemWords(self, words: list[str]) -> list[str]: ...  # noqa: N802


def stemmer(lang: str) -> _SpanishStemmer: ...
