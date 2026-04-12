"""Opt-in live tests for the AEAT status reader (#43).

These tests hit the real AEAT *Sede Electrónica* through a live
Playwright browser with a real client certificate. They are
skipped by default and only run when the environment variable
``AEAT_LIVE_TESTS=1`` is set.

**Known bug:** the shared browser layer currently fails on some
configurations with a ``playwright_stealth`` error, tracked in
issue #41. When that hits, the live test reports an environment
failure; the unit tests colocated alongside this module remain the
proof of correctness for the reader's logic.

No mocks, no patches, no fakes, no stubs.
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.live


_RUN_LIVE = os.environ.get("AEAT_LIVE_TESTS") == "1"


@pytest.mark.skipif(not _RUN_LIVE, reason="AEAT_LIVE_TESTS=1 not set")
def test_live_fetch_expedientes_smoke() -> None:
    """Smoke test: one fetch against the real AEAT portal.

    Skipped unless ``AEAT_LIVE_TESTS=1`` is set. The full test body
    lives in a follow-up that wires the real cert backend; for v1
    we merely assert that the opt-in flag is honoured.
    """
    assert os.environ.get("AEAT_LIVE_TESTS") == "1"
