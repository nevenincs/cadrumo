"""Repo-root pytest conftest.

Hosts the nine-marker collection hook so that items gathered under
``src/aeat/...`` (Rust-style colocated tests) pass through the same
enforcement surface as items under ``tests/``. The hook body lives in
:mod:`tests._marker_hook`; this conftest is a thin wrapper.

See ``tests/README.md`` and charter ``#116`` for the full taxonomy and
the three-factor ``live_write`` bypass contract.
"""

from __future__ import annotations

import pytest
from tests._marker_hook import apply as _apply_marker_contract


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Delegate to the shared marker-contract enforcer."""
    _apply_marker_contract(config, items)
