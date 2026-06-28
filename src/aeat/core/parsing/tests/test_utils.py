"""Real-behaviour tests for :func:`aeat.core.parsing._utils._parse_bool`.

Contract under test (contract):
* Recognised truthy tokens  → True
* Recognised falsy tokens   → False
* Absent / empty / unknown  → None  (caller picks fallback)
"""

from __future__ import annotations

import pytest

from .._utils import _parse_bool

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.mark.parametrize(
    "raw",
    ["true", "True", "TRUE", "1", "yes", "YES", "y", "Y", "si", "sí", "SI", "SÍ"],
)
def test_parse_bool_truthy_tokens(raw: str) -> None:
    assert _parse_bool(raw) is True


@pytest.mark.parametrize(
    "raw",
    ["false", "False", "FALSE", "0", "no", "NO", "n", "N"],
)
def test_parse_bool_falsy_tokens(raw: str) -> None:
    assert _parse_bool(raw) is False


@pytest.mark.parametrize(
    "raw",
    [None, "", "maybe", "MAYBE", "2", "yes please", " ", "\t"],
)
def test_parse_bool_unknown_tokens_return_none(raw: str | None) -> None:
    assert _parse_bool(raw) is None


def test_parse_bool_none_input_is_absent() -> None:
    # Explicit None models a missing/unset field — must never coerce to False.
    result = _parse_bool(None)
    assert result is None


def test_parse_bool_empty_string_is_absent() -> None:
    result = _parse_bool("")
    assert result is None


def test_parse_bool_whitespace_only_is_unknown() -> None:
    # Whitespace-only is not a valid boolean token and must return None.
    result = _parse_bool("   ")
    assert result is None


@pytest.mark.parametrize("raw", ["true", "True", "TRUE", "1", "yes", "y", "si", "sí"])
def test_parse_bool_truthy_roundtrip(raw: str) -> None:
    """Every token in the truthy set round-trips through the parser."""
    assert _parse_bool(raw) is True


@pytest.mark.parametrize("raw", ["false", "False", "FALSE", "0", "no", "n"])
def test_parse_bool_falsy_roundtrip(raw: str) -> None:
    """Every token in the falsy set round-trips through the parser."""
    assert _parse_bool(raw) is False
