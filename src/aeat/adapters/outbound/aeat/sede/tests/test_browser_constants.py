"""Wiring tests for the centralised sede browser settings accessors.

These guard the canonical ``default_viewport`` / ``selector_probe_timeout_ms``
helpers that the GROI, NIF-IVA, and Renta-WEB-Open drivers share, ensuring
they read the intended ``Settings`` keys and produce the Playwright-expected
shape.
"""

from __future__ import annotations

import pytest

from ......core.config import load_settings
from .._browser_constants import default_viewport, selector_probe_timeout_ms

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def test_default_viewport_matches_settings() -> None:
    """``default_viewport`` returns the configured width/height as a viewport dict."""
    settings = load_settings()
    assert default_viewport() == {
        "width": settings.aeat_browser_viewport_width,
        "height": settings.aeat_browser_viewport_height,
    }


def test_selector_probe_timeout_matches_settings() -> None:
    """``selector_probe_timeout_ms`` returns the configured probe timeout."""
    assert selector_probe_timeout_ms() == load_settings().aeat_browser_selector_probe_timeout_ms
