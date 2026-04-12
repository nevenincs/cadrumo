"""Opt-in live tests for the AEAT status reader (#43).

These tests hit the real AEAT *Sede Electrónica* through a live
Playwright browser with a real client certificate. They are
skipped by default and only run when the canonical project-wide
opt-in flag :envvar:`AEAT_LIVE_TESTS_ENABLED` is truthy.

**Status in v1:** this module is an *honest placeholder*. A real
live fetch requires the cert-auth backend from #8, which is not
yet merged. Rather than ship a self-fulfilling assertion that
pretends to be live coverage, the test calls :func:`pytest.skip`
unconditionally when opted in — so CI surfaces the gap instead of
masking it with a false-green.

**Known bug:** the shared browser layer currently fails on some
configurations with a ``playwright_stealth`` error, tracked in
issue #41. When #8 lands and the real live fetch gets wired here,
that bug may still bite; the colocated unit tests remain the proof
of correctness for the reader's logic.

No mocks, no patches, no fakes, no stubs.
"""

from __future__ import annotations

import pytest

from aeat.config import load_settings

pytestmark = pytest.mark.live


def test_live_fetch_expedientes_pending_cert_backend() -> None:
    """Live smoke placeholder.

    Skipped unless ``AEAT_LIVE_TESTS_ENABLED=true`` is set. Even
    when opted in, the test skips with a clear reason because the
    real live wiring requires the #8 cert backend — this is
    deliberate so CI cannot report phantom live coverage.
    """
    if not load_settings().aeat_live_tests_enabled:
        pytest.skip("AEAT_LIVE_TESTS_ENABLED is not set")
    pytest.skip("live fetch deferred until #8 cert backend lands; see .vault/exec/2026-04-12-status-reader/summary.md")
