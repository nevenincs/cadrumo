"""Repo-root pytest conftest.

Hosts the hexagonal marker collection hook from the repo root so every
item gathered under ``src/aeat/...`` passes through the same enforcement
surface. The hook body lives in :mod:`aeat.tests._marker_hook`; this
conftest is a thin wrapper.

The live-test opt-in is read exclusively through
:attr:`aeat.core.config.Settings.live_tests_enabled` (and its Google
companion), which sources ``env/.env`` via pydantic-settings. The single
``aeat.tests.live_gate`` gate is the only live-opt-in reader, so no
``os.environ`` bridging is needed here — the former env-promotion shim was
removed when the scattered raw ``os.environ`` live-gate reads were
centralised onto that Settings-derived surface.

See ``src/aeat/tests/README.md`` and charter ``#116`` for the full taxonomy.
"""

from __future__ import annotations

import pytest

from aeat.tests._marker_hook import apply as _apply_marker_contract


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Delegate to the shared marker-contract enforcer."""
    _apply_marker_contract(config, items)
