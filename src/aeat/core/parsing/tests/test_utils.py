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
    (
        pytest.param(None, id="none"),
        pytest.param("", id="empty"),
        pytest.param(" ", id="space"),
        pytest.param("   ", id="spaces"),
        pytest.param("\t", id="tab"),
        pytest.param("maybe", id="unknown-lower"),
        pytest.param("MAYBE", id="unknown-upper"),
        pytest.param("2", id="numeric-not-bool"),
        pytest.param("yes please", id="phrase"),
    ),
)
def test_parse_bool_unknown_tokens_return_none(raw: str | None) -> None:
    assert _parse_bool(raw) is None


@pytest.mark.parametrize("raw", ["true", "True", "TRUE", "1", "yes", "y", "si", "sí"])
def test_parse_bool_truthy_roundtrip(raw: str) -> None:
    """Every token in the truthy set round-trips through the parser."""
    assert _parse_bool(raw) is True


@pytest.mark.parametrize("raw", ["false", "False", "FALSE", "0", "no", "n"])
def test_parse_bool_falsy_roundtrip(raw: str) -> None:
    """Every token in the falsy set round-trips through the parser."""
    assert _parse_bool(raw) is False
