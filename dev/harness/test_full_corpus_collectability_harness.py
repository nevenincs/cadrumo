"""Dedicated full-corpus collectability proof for the outer-serial harness.

A collection error silently removes a module's tests from a green summary.
This real child-process proof therefore collects every discovered first-party
test root and reports every module that cannot import.  It deliberately lives
outside the routine unit lane: recursively collecting the complete corpus is
valuable end-to-end evidence, but routine unit execution must not pay for a
second full collection.

Collectable is not passing, and this proof does not establish that every lane
executes every module.  Its dedicated recipe membership preflight provides the
separate non-vacuity control for this explicit harness member.
"""

from __future__ import annotations

import pytest

# The bounded controls for this detector live beside it in the dev tree; this
# module holds only the expensive full-corpus proof and reuses their discovery
# primitives.
from ..tests.test_every_test_module_is_collectable import (
    _MINIMUM_PLAUSIBLE_MODULE_COUNT,
    collection_report,
    discover_test_roots,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]


def test_every_test_module_in_the_tree_is_collectable() -> None:
    """No module anywhere in the first-party corpus fails to import.

    The collected tally is asserted alongside the error list because a clean
    error list proves nothing on its own: a run that collected nothing
    reports no errors either.
    """
    roots = discover_test_roots()
    broken, collected = collection_report(roots)

    assert collected >= _MINIMUM_PLAUSIBLE_MODULE_COUNT, (
        f"collection reported only {collected} tests across {len(roots)} roots — "
        f"the run did not reach the corpus, so a clean error list means nothing"
    )
    assert not broken, "test modules that cannot be collected:\n" + "\n".join(broken)
