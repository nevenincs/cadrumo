"""The words an IVA wallet receipt serves for each of its amounts.

A recording's result carries its amounts as canonical decimal text and, beside
each, the same amount written as a box writes money in the operator's
language, so no frontend formats a wallet amount of its own. Each word field
is derived from its amount when the result is built and checked against it
whenever a result is read back.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Annotated

from pydantic import Field

from ...core.external_constants import OutputLanguage
from .value_presentation import money_words

__all__ = ["AmountWords", "require_amount_words", "worded_amount"]

AmountWords = Annotated[str, Field(min_length=1, max_length=128)]


def worded_amount(name: str) -> Callable[[Mapping[str, object]], str]:
    """A default factory that writes the result's ``name`` amount in its ``words_language``."""

    def words(data: Mapping[str, object]) -> str:
        amount, language = data[name], data["words_language"]
        if not isinstance(amount, str) or not isinstance(language, OutputLanguage):
            raise ValueError(f"{name}_words is derived from a validated {name} and words_language")
        return money_words(amount, language)

    return words


def require_amount_words(language: OutputLanguage, worded: Mapping[str, tuple[str, str]]) -> None:
    """Refuse a result whose words, by amount name, do not say their amounts in ``language``."""
    for name, (amount, words) in worded.items():
        if words != money_words(amount, language):
            raise ValueError(f"{name}_words does not say {name}")
