"""The Drive ownership marker admits only this application's entries."""

from __future__ import annotations

import pytest

from ..drive_entries import OWNERSHIP_KEY, OWNERSHIP_VALUE, is_app_owned

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


@pytest.mark.parametrize(
    ("app_properties", "expected"),
    [
        ({OWNERSHIP_KEY: OWNERSHIP_VALUE}, True),
        ({OWNERSHIP_KEY: OWNERSHIP_VALUE, "other": "kept"}, True),
        ({}, False),
        ({OWNERSHIP_KEY: "someone-else"}, False),
        ({"unrelated": "value"}, False),
    ],
)
def test_only_the_exact_marker_counts_as_app_owned(app_properties: dict[str, str], expected: bool) -> None:
    assert is_app_owned(app_properties) is expected
