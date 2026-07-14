"""Repo-root pytest conftest.

Hosts the hexagonal marker collection hook from the repo root so every
item gathered under ``src/cadrumo/...`` passes through the same enforcement
surface. The hook body lives in :mod:`cadrumo.tests._marker_hook`; this
conftest is a thin wrapper.

Also hosts the project-branded ``CADRUMO_PYTEST_WORKERS`` worker-count cap
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

import os

from cadrumo.tests import collection_storage_root

# Mirror src/cadrumo/conftest.py: point the Cadrumo storage root at a
# process-private temp directory BEFORE any Cadrumo import resolves Settings.
# The repo root also collects dev/** test trees that never traverse the
# src/cadrumo conftest; without this, their module imports resolve the real
# platform state root (which may hold retired former-product state and trip
# the FormerProductStateError guard at collection time). Importing the
# derivation helper itself is safe pre-Settings-resolution: `cadrumo/__init__.py`
# and `cadrumo/tests/__init__.py` are both documented import-light (no logging,
# registry, or storage side effects), and `src/cadrumo/conftest.py` already
# imports from `.tests` before this same env var is set on its own path. A bare
# `os.environ.setdefault` call (ruff's tolerated pre-import idiom) keeps this
# block free of E402 "import not at top" against the imports below, which must
# still run AFTER the env var is set; cleanup registration therefore happens
# after the import block instead of here.
os.environ.setdefault("CADRUMO_LOCAL_STORAGE_ROOT", str(collection_storage_root()))

import pytest

from cadrumo.tests import register_collection_storage_root_cleanup
from cadrumo.tests._marker_hook import apply as _apply_marker_contract
from cadrumo.tests._worker_count_hook import resolve_auto_num_workers as _resolve_auto_num_workers

register_collection_storage_root_cleanup(collection_storage_root())


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Delegate to the shared marker-contract enforcer."""
    _apply_marker_contract(config, items)


def pytest_xdist_auto_num_workers(config: pytest.Config) -> int | None:
    """Delegate to the shared ``CADRUMO_PYTEST_WORKERS`` worker-count resolver."""
    return _resolve_auto_num_workers(config)
