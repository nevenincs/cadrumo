"""Keep native browser starts aligned with the isolated adapter test settings."""

from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True)
def _align_browser_binary_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """Restore driver-cache mutations and align direct Playwright starts.

    The repository bootstrap pins the provisioned binary directory before
    private storage isolation. Tests may explicitly choose an empty cache to
    exercise refusal, and production driver startup mutates its native variable;
    those mutations must not redirect the next test's direct driver startup.
    """
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", os.environ["CADRUMO_PLAYWRIGHT_BROWSERS_DIR"])
