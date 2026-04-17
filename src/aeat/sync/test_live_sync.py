"""Opt-in live smoke test for the self-healing sync runner.

Marked ``live_read`` (historical - previously ``@pytest.mark.live``).
The default ``just test`` invocation runs unit tests only via
``-m 'unit'``; ``just test-live`` opts into ``live_read`` selection.
This test exercises a single end-to-end fetch → validate → classify
cycle against a low-risk AEAT endpoint (the sede landing page).

The real #8 certificate backend is a hard requirement: the test uses
``pytest.importorskip`` so that it becomes actionable the moment #8
merges, without requiring a code change here.
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.live_read, pytest.mark.domain_aeat_remote]


def test_live_sync_smoke() -> None:
    """End-to-end smoke test against real AEAT.

    When this test eventually runs under ``just test-live`` after #8
    (certificate backend) and #17 (corpus loader) merge, it will:

    1. Open a :class:`aeat.browser.BrowserSession` against
       ``AEAT_BASE_URL``.
    2. Preload the real certificate via the #8 backend.
    3. Fetch the sede landing page markup via a concrete
       :class:`aeat.sync.LivePayloadFetcher`.
    4. Validate the payload through :class:`aeat.sync.WireValidator`.
    5. Diff it against the local corpus snapshot.
    6. Assert that zero ``BREAKING`` or ``SUSPICIOUS`` records appear.

    Until #8 merges, ``pytest.importorskip`` raises a SKIP on the
    import attempt — this is the idiomatic "dependency-gated live
    test" pattern and is NOT a silent skip of a broken test.
    """
    pytest.importorskip(
        "aeat.auth.certificate",
        reason="aeat.auth.certificate is pending issue #8",
    )
    pytest.importorskip(
        "aeat.corpus",
        reason="aeat.corpus is pending issue #17",
    )
    pytest.fail(
        "live sync smoke reached the dependency gate — wire the end-to-end "
        "flow the moment #8 and #17 rebase into this branch"
    )
