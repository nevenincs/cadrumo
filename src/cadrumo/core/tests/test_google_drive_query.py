"""Contracts for Google Drive query-literal escaping."""

from __future__ import annotations

import pytest

from ..google_drive_query import escape_google_drive_query_literal

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.mark.parametrize(
    ("value", "expected"),
    (
        ("va'ult", "va\\'ult"),
        ("a\\b", "a\\\\b"),
        ("a\\'b", "a\\\\\\'b"),
        ("plain", "plain"),
        ("", ""),
    ),
)
def test_escape_google_drive_query_literal_preserves_literal_meaning(value: str, expected: str) -> None:
    assert escape_google_drive_query_literal(value) == expected
