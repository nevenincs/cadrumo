"""Collection-time objects sit outside the cyclic collector during the run.

The repository conftest freezes what collection built, so a full collection
during a test no longer re-traverses every module, class and collected item.
Nothing else would notice the hook going missing: every test still passes,
only more slowly.
"""

from __future__ import annotations

import gc
import weakref

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_the_session_froze_what_collection_built() -> None:
    assert gc.get_freeze_count() > 0, "no object was frozen after collection; the conftest hook is gone"


def test_objects_created_by_a_test_are_still_collected() -> None:
    """Freezing is bounded to collection time: a test's own cycles are reclaimed.

    Observed through the cycle itself rather than the freeze count. The count
    is not an invariant of a collection: a cycle the collection frees may hold
    the last reference to a frozen object, which then dies and lowers it, so an
    exact comparison depended on what earlier modules left behind.
    """

    class _Node:
        partner: _Node | None = None

    first, second = _Node(), _Node()
    first.partner, second.partner = second, first
    reclaimed = weakref.ref(first)
    del first, second

    gc.collect()

    assert reclaimed() is None, "a cycle created during the test survived a full collection, so it was frozen"
