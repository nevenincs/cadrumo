"""Generic live-test gate for ``@pytest.mark.live`` tests.

Test-support helper shared across the package. Live-gated tests under
both ``src/aeat/adapters/...`` and ``src/aeat/entrypoints/...`` import
``requires_live_enabled`` from here; the helper lives in the bundled
``aeat.tests`` test-support subpackage so no production package needs to
import ``pytest``.
"""

from __future__ import annotations

import pytest

from ..core.config import Settings


def requires_live_enabled() -> None:
    """Skip the calling test unless ``AEAT_LIVE_TESTS_ENABLED`` is exactly ``"1"``."""

    if Settings().aeat_live_tests_enabled != "1":
        pytest.skip("AEAT_LIVE_TESTS_ENABLED is not 1; opt in via env/.env")
