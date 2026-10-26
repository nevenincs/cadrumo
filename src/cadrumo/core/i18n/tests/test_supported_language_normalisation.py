"""Normalising a locale token answers from the enum, once per distinct spelling.

Every catalogue lookup normalises its locale first, so this sits on the hottest
path the i18n layer has: one registry validation issues 692k lookups, and the
coercion was 1.20us of the 2.39us each one cost. The answer is fixed by the
supported-language enum for the life of the process, so it is memoised -- and
these gates hold the behaviour that memo must not change.
"""

from __future__ import annotations

import pytest

from ...external_constants import SUPPORTED_OUTPUT_LANGUAGES
from ..render import _normalised_supported_language, normalise_supported_language

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_every_supported_language_normalises_to_itself() -> None:
    for language in SUPPORTED_OUTPUT_LANGUAGES:
        assert normalise_supported_language(language) == language


@pytest.mark.parametrize("spelling", ["ES", "  es  ", "Es"])
def test_case_and_surrounding_space_resolve_to_the_canonical_token(spelling: str) -> None:
    assert normalise_supported_language(spelling) == "es"


@pytest.mark.parametrize("value", ["", "klingon", None, True, 7, object()])
def test_an_unrecognised_or_non_string_value_is_none_rather_than_a_crash(value: object) -> None:
    """A bare bool or arbitrary object is invalid input, not an error.

    The memo keys on the STRINGIFIED value, so an unhashable argument must
    still reach an answer rather than a TypeError from the cache.
    """
    assert normalise_supported_language(value) is None


def test_a_repeated_spelling_is_coerced_once() -> None:
    """The memo answers the second call without re-entering the coercion."""
    _normalised_supported_language.cache_clear()
    before = _normalised_supported_language.cache_info()
    assert before.hits == 0

    normalise_supported_language("es")
    normalise_supported_language("es")
    normalise_supported_language("es")

    after = _normalised_supported_language.cache_info()
    assert after.misses == 1, "one distinct spelling must reach the coercion exactly once"
    assert after.hits == 2


def test_distinct_spellings_are_cached_apart() -> None:
    """Two spellings of the same language are separate entries with equal answers."""
    _normalised_supported_language.cache_clear()

    assert normalise_supported_language("es") == normalise_supported_language("ES") == "es"
    assert _normalised_supported_language.cache_info().misses == 2
