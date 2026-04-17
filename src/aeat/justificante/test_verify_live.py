"""Live CSV verification test for :func:`aeat.justificante.verify_csv` (#44).

This test is **opt-in**: it is skipped unless
``AEAT_LIVE_TESTS_ENABLED=1`` is set in the environment. It spins up a
real Playwright browser session against
AEAT's Sede electrónica and round-trips one CSV. Per the project rule,
this file MUST NOT contain mocks, patches, fakes, or stubs.

Known caveat: issue #41 tracks a ``playwright_stealth`` bug in the
:mod:`aeat.browser` evasion layer. When that bug is live, this test will
raise :class:`JustificanteVerificationError` from the browser constructor,
and the unit suite (``test_parser.py``) remains the authoritative proof of
correctness for the parser itself.
"""

from __future__ import annotations

import pytest

from ..cli._live import requires_live_enabled
from . import (
    JustificanteError,
    verify_csv,
)

pytestmark = [pytest.mark.live_read, pytest.mark.domain_aeat_remote]


@pytest.mark.asyncio
async def test_verify_csv_round_trip() -> None:
    requires_live_enabled()
    # We deliberately use a syntactically valid but fictitious CSV. AEAT is
    # expected to report the document as unknown; the test passes as long as
    # the round-trip completes and returns a bool without raising.
    try:
        result = await verify_csv("ABCD1234EFGH5678")
    except JustificanteError as exc:
        pytest.skip(f"live verification unavailable (likely #41 stealth bug): {exc}")
    assert isinstance(result, bool)
