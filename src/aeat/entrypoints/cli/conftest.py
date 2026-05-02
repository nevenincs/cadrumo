"""Shared fixtures for entrypoints/cli tests."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _force_english_output(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin CLI output to English so test assertions stay readable.

    The production default is ``es``; this fixture only affects test
    output, not runtime behaviour.
    """
    monkeypatch.setenv("AEAT_OUTPUT_LANGUAGE", "en")
