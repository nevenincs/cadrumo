"""Child-pytest probe whose only test fails, so the run that selects it fails."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

FAILURE_MESSAGE = "failing run probe"


def test_fails_its_run() -> None:
    """Fails on purpose; only a parent test that needs a failing run selects this file."""
    raise AssertionError(FAILURE_MESSAGE)
