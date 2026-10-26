"""The hex predicates admit only exact-length lowercase hexadecimal text."""

from __future__ import annotations

import pytest

from ..hex import is_hex16, is_hex64

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_HEX_16 = "0123456789abcdef"
_HEX_64 = "a" * 32 + "0123456789abcdef" * 2


@pytest.mark.parametrize(
    ("value", "accepted"),
    [
        (_HEX_16, True),
        (_HEX_16.upper(), False),
        (_HEX_16[:-1], False),
        (_HEX_16 + "0", False),
        ("0123456789abcdeg", False),
        (_HEX_16 + "\n", False),
        (" " + _HEX_16[:-1], False),
        ("", False),
    ],
)
def test_is_hex16_requires_exactly_sixteen_lowercase_hex_characters(value: str, accepted: bool) -> None:
    assert is_hex16(value) is accepted


@pytest.mark.parametrize(
    ("value", "accepted"),
    [
        (_HEX_64, True),
        (_HEX_64.upper(), False),
        (_HEX_64[:-1], False),
        (_HEX_64 + "0", False),
        (_HEX_64[:-1] + "g", False),
        (_HEX_64 + "\n", False),
        (_HEX_16, False),
        ("", False),
    ],
)
def test_is_hex64_requires_exactly_sixty_four_lowercase_hex_characters(value: str, accepted: bool) -> None:
    assert is_hex64(value) is accepted
