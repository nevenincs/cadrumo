"""Filing snapshot resolution carries no memoization of its own."""

from __future__ import annotations

import pytest

from ..draft_construction import _load_registry_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_snapshot_resolution_exposes_no_cache_handle() -> None:
    """``_load_registry_snapshot`` must carry no memoization wrapper.

    Structural companion to the behavioural freshness tests: ``functools`` caches
    expose ``cache_clear``/``cache_info``, so their absence pins the intent even
    if a future change makes the staleness window harder to trigger.
    """
    for attribute in ("cache_clear", "cache_info", "__wrapped__"):
        assert not hasattr(_load_registry_snapshot, attribute), (
            f"_load_registry_snapshot exposes {attribute!r}, so it is memoized above the registry "
            "loader; such a cache is keyed without the registry-tree fingerprint and can serve a "
            "snapshot from before a registry change"
        )
