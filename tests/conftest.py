"""Shared pytest fixtures and collection hook for the AEAT test suite.

The nine-marker collection hook body lives in :mod:`tests._marker_hook`
and is also invoked from the repo-root ``conftest.py``. This conftest
registers its own thin wrapper for completeness; double-invocation is
safe because the shared helper enforces invariants on items it receives
and filters in-place, so a second pass is a no-op.
"""

from __future__ import annotations

import pytest

from tests._marker_hook import apply as _apply_marker_contract


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Delegate to the shared marker-contract enforcer."""
    _apply_marker_contract(config, items)
