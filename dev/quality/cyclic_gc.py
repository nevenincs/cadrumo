"""Pause the cyclic garbage collector around a bulk build of acyclic objects.

A repository-wide scan parses thousands of modules and keeps the trees alive
together. Every full collection those allocations trigger re-traverses all of
them and frees nothing: a syntax tree references only its children, so it holds
no reference cycle, and reference counting releases it once the last reference
goes. Measured over this tree, those collections were a third to a half of such
a scan's wall time.
"""

from __future__ import annotations

import gc
from collections.abc import Iterator
from contextlib import contextmanager

__all__ = ["cyclic_gc_paused"]


@contextmanager
def cyclic_gc_paused() -> Iterator[None]:
    """Disable the cyclic collector for the block, then restore its prior state.

    Cyclic garbage created inside the block is deferred, not lost: the collector
    reclaims it on its next run after re-enabling. A caller that had already
    disabled the collector finds it still disabled afterwards.
    """
    was_enabled = gc.isenabled()
    gc.disable()
    try:
        yield
    finally:
        if was_enabled:
            gc.enable()
