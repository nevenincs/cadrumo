"""Generic live-test gate for ``@pytest.mark.aeat_live`` tests.

Test-support helper shared across the package. Live-gated tests under
both ``src/cadrumo/adapters/...`` and ``src/cadrumo/entrypoints/...`` import
``requires_live_enabled`` from here; the helper lives in the bundled
``aeat-tests`` test-support subpackage so no production package needs to
import ``pytest``.
"""

from __future__ import annotations

import pytest

from ..core.config import Settings


def requires_live_enabled() -> None:
    """Fail unless ``CADRUMO_LIVE_TESTS_ENABLED`` is exactly ``"1"``.

    The single live-test gate. Reads the opt-in through
    ``Settings.live_tests_enabled``, which reads only ``os.environ`` --
    production ``Settings`` carries no dotenv source of its own. An
    operator's ``env/.env`` reaches this gate only via the repo-root
    ``conftest.py`` bridge (:func:`cadrumo.tests.env_loader.bridge_env_file_into_environ`),
    which populates ``os.environ`` at collection time. Every
    ``@pytest.mark.aeat_live`` test shares this one centralised definition
    rather than scattering raw ``os.environ`` reads.
    """

    if not Settings().live_tests_enabled:
        pytest.fail(
            "selected live test requires CADRUMO_LIVE_TESTS_ENABLED=1 (set it in env/.env or the process environment)"
        )


def requires_live_google_enabled() -> None:
    """Fail unless ``CADRUMO_LIVE_TESTS_GOOGLE`` is exactly ``"1"``.

    Companion to :func:`requires_live_enabled` for the Google (OAuth / Drive)
    live tests, routed through ``Settings.live_tests_google_enabled`` so
    the Google opt-in is centralised on the same Settings-derived surface.
    """

    if not Settings().live_tests_google_enabled:
        pytest.fail(
            "selected Google live test requires CADRUMO_LIVE_TESTS_GOOGLE=1 (set it in env/.env or the process environment)"
        )
