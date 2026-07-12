"""Repo-root pytest conftest.

Hosts the hexagonal marker collection hook from the repo root so every
item gathered under ``src/cadrumo/...`` passes through the same enforcement
surface. The hook body lives in :mod:`cadrumo.tests._marker_hook`; this
conftest is a thin wrapper.

Also hosts the project-branded ``AEAT_PYTEST_WORKERS`` worker-count cap
(``pytest_xdist_auto_num_workers``), delegated to
:func:`cadrumo.tests._worker_count_hook.resolve_auto_num_workers`, so every
pytest invocation shape resolves ``-n auto`` through the same policy. See
that module's docstring for the hook-ordering contract this delegation
relies on.

The live-test opt-in is read exclusively through
:attr:`cadrumo.core.config.Settings.live_tests_enabled` (and its Google
companion), which sources ``env/.env`` via pydantic-settings. The single
``cadrumo.tests.live_gate`` gate is the only live-opt-in reader, so no
``os.environ`` bridging is needed here — the former env-promotion shim was
removed when the scattered raw ``os.environ`` live-gate reads were
centralised onto that Settings-derived surface.

See ``src/cadrumo/tests/README.md`` and charter ``#116`` for the full taxonomy.
"""

from __future__ import annotations

import pytest

from cadrumo.tests._marker_hook import apply as _apply_marker_contract
from cadrumo.tests._worker_count_hook import resolve_auto_num_workers as _resolve_auto_num_workers


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Delegate to the shared marker-contract enforcer."""
    _apply_marker_contract(config, items)


def pytest_xdist_auto_num_workers(config: pytest.Config) -> int | None:
    """Delegate to the shared ``AEAT_PYTEST_WORKERS`` worker-count resolver."""
    return _resolve_auto_num_workers(config)
