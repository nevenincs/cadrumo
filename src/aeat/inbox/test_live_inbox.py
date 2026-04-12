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


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_fetch_and_ack(tmp_path: Path) -> None:
    """End-to-end fetch + ack round-trip against the real AEAT portal."""
    if not os.environ.get("AEAT_LIVE_TESTS_ENABLED"):
        pytest.skip("AEAT_LIVE_TESTS_ENABLED not set")

    try:
        from aeat.status import StatusReader  # type: ignore
    except ImportError:
        pytest.skip("aeat.status (#43) not yet on main")

    from aeat.inbox import InboxFetcher

    reader = StatusReader()  # type: ignore[call-arg]
    fetcher = InboxFetcher(
        source=reader,
        inbox_file=tmp_path / "inbox.json",
        pdf_dir=tmp_path / "pdfs",
    )
    added = await fetcher.fetch_new()
    if not added:
        pytest.skip("No live notifications available for the test profile")
    first = added[0]
    acked = await fetcher.acknowledge(first.notificacion_id, by="live-test")
    assert acked.acknowledged_by == "live-test"
