"""Live CSV verification test for :func:`cadrumo.adapters.outbound.aeat.verify.verify_csv`.

This test is **opt-in**: it is deselected unless
``CADRUMO_LIVE_TESTS_ENABLED=1`` is set in the environment. It spins up a
real Playwright browser session against
AEAT's Sede electrónica and round-trips one CSV. Per the project rule,
this file uses the real outbound verification surface.

When the live browser surface is unavailable, this test raises
:class:`JustificanteVerificationError` from the browser constructor.
"""

from __future__ import annotations

import pytest

from ......domain.justificante import JustificanteVerificationError
from ......tests.live_gate import requires_live_enabled
from ..contract import verify_csv

pytestmark = [pytest.mark.aeat_live, pytest.mark.hex_outbound_adapter]


@pytest.mark.asyncio
async def test_verify_csv_round_trip() -> None:
    requires_live_enabled()
    # We deliberately use a syntactically valid but fictitious CSV. AEAT is
    # expected to report the document as unknown; the test passes as long as
    # the round-trip completes and returns a bool without raising.
    try:
        result = await verify_csv("ABCD1234EFGH5678")
    except JustificanteVerificationError as exc:
        pytest.fail(f"live verification unavailable after live opt-in: {exc}")
    assert isinstance(result, bool)
