"""Real-behavior contract tests for Playwright wait-state constants."""

from __future__ import annotations

import pytest

from .._browser_constants import (
    PLAYWRIGHT_WAIT_DOMCONTENTLOADED,
    PLAYWRIGHT_WAIT_NETWORKIDLE,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


@pytest.mark.parametrize(
    ("constant", "expected"),
    (
        (PLAYWRIGHT_WAIT_DOMCONTENTLOADED, "domcontentloaded"),
        (PLAYWRIGHT_WAIT_NETWORKIDLE, "networkidle"),
    ),
)
def test_playwright_wait_constant_values(constant: str, expected: str) -> None:
    """The constants equal the Playwright API strings they represent."""
    assert constant == expected
