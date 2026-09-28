"""Tests for pausing the cyclic collector around a bulk tree build.

The pause is process-wide, so the property worth pinning is that it never
outlives its block: a scan that raised must not leave the collector off for
every test that runs after it in the same worker.
"""

from __future__ import annotations

import gc

import pytest

from ..cyclic_gc import cyclic_gc_paused

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_the_collector_is_off_inside_and_back_on_after() -> None:
    assert gc.isenabled()

    with cyclic_gc_paused():
        assert not gc.isenabled()

    assert gc.isenabled()


def test_a_block_that_raises_still_re_enables_the_collector() -> None:
    marker = "scan failed"

    with pytest.raises(RuntimeError, match=marker), cyclic_gc_paused():
        raise RuntimeError(marker)

    assert gc.isenabled()


def test_a_collector_disabled_by_the_caller_stays_disabled() -> None:
    gc.disable()
    try:
        with cyclic_gc_paused():
            assert not gc.isenabled()
        assert not gc.isenabled()
    finally:
        gc.enable()
