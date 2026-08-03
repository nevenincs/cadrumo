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
companion), which reads only ``os.environ`` — production ``Settings``
carries no dotenv source of its own
(``Settings.settings_customise_sources`` never returns a dotenv source).
``env/.env`` is development/test-only configuration (an operator's local
live-test credentials), so this conftest bridges it into ``os.environ``
itself, before any Cadrumo import can resolve ``Settings``, via
:func:`cadrumo.tests._env_loader.bridge_env_file_into_environ`.
``os.environ.setdefault`` semantics keep a real ambient environment
variable authoritative over the dotfile — the file only fills gaps a
shell or CI environment left unset, and the bridge is a clean no-op when
``env/.env`` is absent. The single ``cadrumo.tests.live_gate`` gate
remains the only live-opt-in reader.

See ``src/cadrumo/tests/README.md`` and charter ``#116`` for the full taxonomy.
"""

from __future__ import annotations

import os
from pathlib import Path

from cadrumo.tests import collection_storage_root
from cadrumo.tests._env_loader import bridge_env_file_into_environ

# Bridge the operator's development-only env/.env dotfile into os.environ
# BEFORE any Cadrumo import resolves Settings (production Settings carries
# no dotenv source of its own — see core.config.Settings). setdefault
# semantics inside the bridge keep a real ambient environment variable
# authoritative; the dotfile only fills gaps. Importing `_env_loader` here
# is safe pre-Settings-resolution for the same reason importing
# `collection_storage_root` below is: `cadrumo/__init__.py` and
# `cadrumo/tests/__init__.py` are both documented import-light (no
# logging, registry, or storage side effects).
bridge_env_file_into_environ(Path(__file__).resolve().parent / "env" / ".env")

# Mirror src/cadrumo/conftest.py: point the Cadrumo storage root at a
# process-private temp directory BEFORE any Cadrumo import resolves Settings.
# The repo root also collects dev/** test trees that never traverse the
# src/cadrumo conftest; without this, their module imports resolve the real
# platform state root (which may hold retired former-product state and trip
# the FormerProductStateError guard at collection time). Importing the
# derivation helper itself is safe pre-Settings-resolution: `cadrumo/__init__.py`
# and `cadrumo/tests/__init__.py` are both documented import-light (no logging,
# registry, or storage side effects), and `src/cadrumo/conftest.py` already
# imports from `.tests` before this same env var is set on its own path. A
# single bare `os.environ.setdefault` call (ruff's tolerated pre-import idiom)
# used to keep this block free of the import-not-at-top lint against the
# imports below; the dotenv bridge above is a second pre-import statement
# ruff does not recognise under that idiom, so the imports below carry an
# explicit per-line suppression instead — they must still run AFTER both env
# vars are set, so cleanup registration happens after the import block
# below, not here.
os.environ.setdefault("CADRUMO_LOCAL_STORAGE_ROOT", str(collection_storage_root()))

from typing import TYPE_CHECKING  # noqa: E402

import pytest  # noqa: E402

from cadrumo.tests import register_collection_storage_root_cleanup  # noqa: E402
from cadrumo.tests._deselection_hook import apply as _report_deselection  # noqa: E402
from cadrumo.tests._marker_hook import apply as _apply_marker_contract  # noqa: E402
from cadrumo.tests._worker_count_hook import resolve_auto_num_workers as _resolve_auto_num_workers  # noqa: E402

if TYPE_CHECKING:
    from _pytest.terminal import TerminalReporter

register_collection_storage_root_cleanup(collection_storage_root())


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Delegate to the shared marker-contract enforcer."""
    _apply_marker_contract(config, items)


def pytest_xdist_auto_num_workers(config: pytest.Config) -> int | None:
    """Delegate to the shared ``CADRUMO_PYTEST_WORKERS`` worker-count resolver."""
    return _resolve_auto_num_workers(config)


def pytest_terminal_summary(
    terminalreporter: TerminalReporter,
    exitstatus: int,
    config: pytest.Config,
) -> None:
    """Delegate to the shared marker-deselection reporter."""
    _report_deselection(terminalreporter, exitstatus, config)
