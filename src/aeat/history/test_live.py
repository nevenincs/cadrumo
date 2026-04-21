"""Opt-in live test for the filing-history fetcher.

Requires ``AEAT_LIVE_TESTS_ENABLED=1`` and the real upstream
collaborators (the #43 status reader wrapped as an
:class:`ExpedienteSource`, plus a real
:class:`FilingDetailFetcher` backed by a browser session). Until
those facades land on ``main``, the test skips with a concrete
reason so CI cannot report phantom live coverage.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

pytestmark = [pytest.mark.live_read, pytest.mark.domain_aeat_remote]


@pytest.mark.asyncio
async def test_live_fetch_history_for_modelo_130(tmp_path: Path) -> None:
    """End-to-end filing-history fetch against the real AEAT portal."""
    if not os.environ.get("AEAT_LIVE_TESTS_ENABLED"):
        pytest.skip("AEAT_LIVE_TESTS_ENABLED not set")

    # The real :class:`ExpedienteSource` + :class:`FilingDetailFetcher`
    # facades live behind #167 (cert auth) and the post-#43 wrapper
    # work. The Protocol-injection design in the #168 ADR means the
    # unit-test path is complete and this live test is wiring-only —
    # it activates once those collaborators ship on ``main``.
    del tmp_path
    pytest.skip(
        "history live wiring deferred until #167 (cert auth) and the public ExpedienteSource facade land on main"
    )
