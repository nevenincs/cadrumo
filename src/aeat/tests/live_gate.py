"""Generic live-test gate for ``@pytest.mark.aeat_live`` tests.

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
    """Skip the calling test unless ``AEAT_LIVE_TESTS_ENABLED`` is exactly ``"1"``.

    The single live-test gate. Reads the opt-in through
    :attr:`Settings.live_tests_enabled` (which sources ``env/.env`` via
    pydantic-settings) so every ``@pytest.mark.aeat_live`` test shares one
    centralised definition rather than scattering raw ``os.environ`` reads.
    """

    if not Settings().live_tests_enabled:
        pytest.skip("AEAT_LIVE_TESTS_ENABLED is not 1; opt in via env/.env")


def requires_live_google_enabled() -> None:
    """Skip the calling test unless ``AEAT_LIVE_TESTS_GOOGLE`` is exactly ``"1"``.

    Companion to :func:`requires_live_enabled` for the Google (OAuth / Drive)
    live tests, routed through :attr:`Settings.live_tests_google_enabled` so
    the Google opt-in is centralised on the same Settings-derived surface.
    """

    if not Settings().live_tests_google_enabled:
        pytest.skip("AEAT_LIVE_TESTS_GOOGLE is not 1; opt in via env/.env")
