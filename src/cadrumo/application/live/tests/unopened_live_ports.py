"""Live capabilities that refuse to open, for tests that never reach AEAT.

Operation registrations and refusal paths need a browser-session factory and a
censal fetch port to be composed, but the behaviour under test settles before
either is used. These inward implementations satisfy the application ports and
fail loudly if a test ever does reach them, so a passing test cannot have
silently opened a browser or read the Sede.
"""

from __future__ import annotations

from ....core.config import Settings
from ...auth.protocols import BrowserSessionPort
from ...auth.session_types import AeatSession
from ...user_profile.censal_observation import CensalObservation


async def unopened_browser_session_factory(settings: Settings) -> BrowserSessionPort:
    """Refuse to open a browser session; the caller's path must settle first."""
    del settings
    raise AssertionError("this test must settle before any browser session is opened")


async def unopened_censal_fetch(
    session: AeatSession,
    *,
    taxpayer_nif: str,
    settings: Settings,
) -> CensalObservation:
    """Refuse to read the Sede censo; the caller's path must settle first."""
    del session, taxpayer_nif, settings
    raise AssertionError("this test must settle before any censal data is fetched")


__all__ = ["unopened_browser_session_factory", "unopened_censal_fetch"]
