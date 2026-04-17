"""Opt-in live test for the notifications inbox.

Requires ``AEAT_LIVE_TESTS_ENABLED=1`` and the real AEAT status
reader (#43) to be importable. Until #43 lands on ``main``, the test
skips with a clear reason. If #16's playwright-stealth bug (#41) is
still live, the resulting error is surfaced verbatim.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

pytestmark = [pytest.mark.live_read, pytest.mark.domain_aeat_remote]


@pytest.mark.asyncio
async def test_live_fetch_and_ack(tmp_path: Path) -> None:
    """End-to-end fetch + ack round-trip against the real AEAT portal."""
    if not os.environ.get("AEAT_LIVE_TESTS_ENABLED"):
        pytest.skip("AEAT_LIVE_TESTS_ENABLED not set")

    # #43 (status reader) is now on this branch, but the real end-to-end
    # wiring between `aeat.inbox.InboxFetcher` and
    # `aeat.status.StatusReader` still depends on #8 (cert auth). Until
    # #8 lands, skip here with a concrete reason so CI cannot report
    # phantom live coverage.
    del tmp_path
    pytest.skip("inbox ↔ status live wiring deferred until #8 cert backend lands")
