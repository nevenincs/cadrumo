"""Keep native browser starts aligned with the isolated adapter test settings."""

from __future__ import annotations

import os

import pytest

from ....core.storage_environment import TEMPORARY_VARIABLES

_BOOTSTRAP_BROWSER_CACHE = os.environ["PLAYWRIGHT_BROWSERS_PATH"]
"""The browser binary directory the repository bootstrap pinned before private storage isolation."""


@pytest.fixture(autouse=True)
def _align_browser_binary_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """Restore driver-environment mutations and align direct Playwright starts.

    Tests may explicitly choose an empty cache to exercise refusal, and
    production driver startup writes the browsers and temporary-directory
    variables for its own process. A test that starts it under a storage root of
    its own would leave those pointing into a directory that is later removed,
    so every test starts from the bootstrap browser cache and its own temporary
    directory variables, and gives them back unchanged.
    """
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", _BOOTSTRAP_BROWSER_CACHE)
    for name in TEMPORARY_VARIABLES:
        current = os.environ.get(name)
        if current is not None:
            monkeypatch.setenv(name, current)
