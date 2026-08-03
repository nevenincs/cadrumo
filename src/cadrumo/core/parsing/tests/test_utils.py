"""Real-behaviour tests for :func:`cadrumo.core.parsing._utils._parse_bool`.

Contract under test (contract):
* Recognised truthy tokens  → True
* Recognised falsy tokens   → False
* Absent / empty / unknown  → None  (caller picks fallback)
"""

from __future__ import annotations

import pytest

from .._utils import _parse_bool

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_RECOGNIZED_TOKENS: tuple[tuple[str, bool], ...] = (
    ("true", True),
    ("True", True),
    ("TRUE", True),
    ("1", True),
    ("yes", True),
    ("YES", True),
    ("y", True),
    ("Y", True),
    ("si", True),
    ("sí", True),
    ("SI", True),
    ("SÍ", True),
    # The Spanish affirmative had been half-supported: "si"/"sí" were
    # recognised while "s" -- the abbreviation the filing layer has always
    # accepted -- and "verdadero", the ordinary word, were not. A vocabulary
    # that takes one spelling of yes and not another is arbitrary from the
    # operator's side, and the missing spellings are exactly what a reader
    # then silently turned into "no".
    ("s", True),
    ("S", True),
    ("verdadero", True),
    ("VERDADERO", True),
    ("false", False),
    ("False", False),
    ("FALSE", False),
    ("0", False),
    ("no", False),
    ("NO", False),
    ("n", False),
    ("N", False),
    ("falso", False),
    ("FALSO", False),
)

_UNKNOWN_TOKENS: tuple[str | None, ...] = (
    None,
    "",
    " ",
    "   ",
    "\t",
    "maybe",
    "MAYBE",
    "2",
    "yes please",
)


def test_parse_bool_recognized_and_unknown_tokens() -> None:
    for raw, expected in _RECOGNIZED_TOKENS:
        assert _parse_bool(raw) is expected

    for raw in _UNKNOWN_TOKENS:
        assert _parse_bool(raw) is None
