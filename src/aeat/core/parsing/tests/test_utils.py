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
    ("raw", "expected"),
    (
        pytest.param("true", True, id="true-lower"),
        pytest.param("True", True, id="true-title"),
        pytest.param("TRUE", True, id="true-upper"),
        pytest.param("1", True, id="one"),
        pytest.param("yes", True, id="yes-lower"),
        pytest.param("YES", True, id="yes-upper"),
        pytest.param("y", True, id="y-lower"),
        pytest.param("Y", True, id="y-upper"),
        pytest.param("si", True, id="si-lower"),
        pytest.param("sí", True, id="si-accent-lower"),
        pytest.param("SI", True, id="si-upper"),
        pytest.param("SÍ", True, id="si-accent-upper"),
        pytest.param("false", False, id="false-lower"),
        pytest.param("False", False, id="false-title"),
        pytest.param("FALSE", False, id="false-upper"),
        pytest.param("0", False, id="zero"),
        pytest.param("no", False, id="no-lower"),
        pytest.param("NO", False, id="no-upper"),
        pytest.param("n", False, id="n-lower"),
        pytest.param("N", False, id="n-upper"),
    ),
)
def test_parse_bool_recognized_tokens(raw: str, expected: bool) -> None:
    assert _parse_bool(raw) is expected


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
