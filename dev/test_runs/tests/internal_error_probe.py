"""Opt-in child-pytest plugin used to prove internal-error persistence."""

from __future__ import annotations

import os

import pytest


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Raise only in the explicitly armed child process."""
    del items
    if os.environ.get("CADRUMO_INTERNAL_ERROR_PROBE") == "1":
        raise RuntimeError("internal error persistence probe")
