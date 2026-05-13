"""Generic live-test gate for ``@pytest.mark.live`` tests."""

from __future__ import annotations

import pytest

from ...core.config import Settings


def requires_live_enabled() -> None:
    """Skip the calling test when ``AEAT_LIVE_TESTS_ENABLED`` is false."""

    if not Settings().aeat_live_tests_enabled:
        pytest.skip("AEAT_LIVE_TESTS_ENABLED is false; opt in via env/.env")
