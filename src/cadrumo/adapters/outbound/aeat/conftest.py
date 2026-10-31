"""Keep native browser starts aligned with the isolated adapter test settings."""

from __future__ import annotations

import os

import pytest

from ....core.storage_environment import TEMPORARY_VARIABLES

_BOOTSTRAP_BROWSER_CACHE = os.environ["PLAYWRIGHT_BROWSERS_PATH"]
"""The browser binary directory the repository bootstrap pinned before private storage isolation."""


@pytest.fixture(autouse=True)
def _align_browser_binary_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """Align direct Playwright starts and restore a test's temporary variables.

    Tests may explicitly choose an empty cache to exercise refusal. The
    monkeypatch keeps those changes and any temporary-directory changes local
    to the test, while direct Playwright starts use the bootstrap cache.
    """
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", _BOOTSTRAP_BROWSER_CACHE)
    for name in TEMPORARY_VARIABLES:
        current = os.environ.get(name)
        if current is not None:
            monkeypatch.setenv(name, current)
