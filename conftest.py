"""Repo-root pytest conftest.

Hosts the hexagonal marker collection hook from the repo root so every item
gathered through this root passes through the same enforcement surface. The
hook body lives in :mod:`cadrumo.tests.marker_hook`; this conftest is a thin
wrapper.

Also hosts the project-branded ``CADRUMO_PYTEST_WORKERS`` worker-count policy
(``pytest_xdist_auto_num_workers``), delegated to
:func:`cadrumo.tests.worker_count_hook.resolve_auto_num_workers`, so every
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
:func:`cadrumo.tests.env_loader.bridge_env_file_into_environ`.
``os.environ.setdefault`` semantics keep a real ambient environment
variable authoritative over the dotfile — the file only fills gaps a
shell or CI environment left unset, and the bridge is a clean no-op when
``env/.env`` is absent. The single ``cadrumo.tests.live_gate`` gate
remains the only live-opt-in reader.

The storage-root ``setdefault`` below is deliberately spelled out with
pure-stdlib calls (``tempfile.gettempdir()`` / ``os.getpid()``) rather than
imported from :func:`cadrumo.tests.collection_storage_root`, even though
the two compute the identical path. Importing ANY name from
``cadrumo.tests`` -- even a genuinely pure-stdlib submodule such as
``_collection_storage_root`` -- unconditionally executes
``cadrumo/tests/__init__.py``'s own module body first (Python always
initialises a parent package before a submodule access can complete), and
that package's import surface has, in practice, drifted to reach
production modules carrying module-level ``get_logger(__name__)`` calls.
Any such call fires ``configure_logging()``, which binds its
``RotatingFileHandler`` exactly once per process; if that firing happens
before this line runs, it binds to the operator's real log rather than
this process's isolated root, and nothing later in the process can
re-bind it. Spelling the derivation out here removes the dependency on
``cadrumo/tests/__init__.py`` staying import-light for THIS one
safety-critical line -- the guarantee this docstring's next paragraph
already claimed, now enforced structurally instead of by convention.
Verified by instrumenting ``configure_logging`` to dump its first real
call stack: importing ``cadrumo.tests`` alone no longer triggers it, and
the residual triggers found only fire from session-scoped fixtures that
run after this line has already set the environment variable.

See ``src/cadrumo/tests/README.md`` and charter ``#116`` for the full taxonomy.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING

import pytest
from dev.test_runs import logging as _run_logging

# Keep pytest scratch and collection-time storage outside the checkout. The
# run logger retains its relative ``.logs`` layout under this external base.
_run_logging.prepare_environment(Path(tempfile.gettempdir()))
# The runner's product-log artifact is not a Cadrumo Settings override: the
# default must be derived from the isolated storage root used by this run.
os.environ.pop("CADRUMO_LOG_DIR", None)

# Pure stdlib, deliberately not `from cadrumo.tests import collection_storage_root`
# -- see the docstring above. Mirrors `_collection_storage_root.collection_storage_root`'s
# own derivation (`<gettempdir()>/cadrumo-pytest-<pid>`) exactly; the two module docstrings
# cross-reference each other so a future edit to one is not made deaf to the other.
_PURE_STDLIB_COLLECTION_ROOT = Path(tempfile.gettempdir()) / f"cadrumo-pytest-{os.getpid()}"
"""This conftest's own candidate root, computed before any Cadrumo import.

Only ever materialises on disk (and only ever needs cleanup) when a test run
never reaches ``src/cadrumo/conftest.py`` -- e.g. a ``dev/**``-only
collection -- since that conftest unconditionally overwrites the same
environment variable for every run that does reach it, and this value is
never referenced again once overwritten.
"""
os.environ.setdefault("CADRUMO_LOCAL_STORAGE_ROOT", str(_PURE_STDLIB_COLLECTION_ROOT))

_collection_storage_root = import_module("cadrumo.tests.collection_storage_root")
collection_storage_root = _collection_storage_root.collection_storage_root
register_collection_storage_root_cleanup = _collection_storage_root.register_collection_storage_root_cleanup
bridge_env_file_into_environ = import_module("cadrumo.tests.env_loader").bridge_env_file_into_environ

# Bridge the operator's development-only env/.env dotfile into os.environ
# BEFORE any Cadrumo import resolves Settings (production Settings carries
# no dotenv source of its own — see core.config.Settings). setdefault
# semantics inside the bridge keep a real ambient environment variable
# authoritative; the dotfile only fills gaps. Safe to import cadrumo.tests
# here (unlike the storage-root line above): the storage-root env var this
# module's own import surface might trigger a premature configure_logging()
# against is already set by the pure-stdlib line above.
bridge_env_file_into_environ(Path(__file__).resolve().parent / "env" / ".env")

# The collection-policy, reporting, timeout and worker-count hooks load by their
# public package path, after the storage-root and env bridging above; a
# top-of-file import statement would run before those lines.
deselection_hook = import_module("cadrumo.tests.deselection_hook")
fixture_resolution_hook = import_module("cadrumo.tests.fixture_resolution_hook")
host_load_hook = import_module("cadrumo.tests.host_load_hook")
lost_test_hook = import_module("cadrumo.tests.lost_test_hook")
marker_hook = import_module("cadrumo.tests.marker_hook")
worker_count_hook = import_module("cadrumo.tests.worker_count_hook")
temporary_env = import_module("cadrumo.tests.env").temporary_env

if TYPE_CHECKING:
    from _pytest.terminal import TerminalReporter

# Loaded as a plugin, not inlined here: this module's own `pytest_configure` is
# `trylast`, and the JUnit option has to be set before the junitxml plugin reads
# it. Unset `VAULTSPEC_CI_REPORTS` - every local run - and it does nothing,
# which is what keeps this repository's zero-artifact posture intact.
pytest_plugins = ("dev.ci_reports",)

register_collection_storage_root_cleanup(collection_storage_root())


@pytest.hookimpl(trylast=True)
def pytest_configure(config: pytest.Config) -> None:
    """Create and announce this pytest invocation's durable run log."""
    marker_hook.reset_held_serials()
    fixture_resolution_hook.reset_refused_requests()
    _run_logging.configure(config)


def pytest_runtest_logstart(nodeid: str, location: tuple[str, int | None, str]) -> None:
    """Record the test identity before execution begins."""
    del location
    _run_logging.log_start(nodeid)


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    """Persist each test verdict and immediate failure detail."""
    _run_logging.log_report(report)


def pytest_collectreport(report: pytest.CollectReport) -> None:
    """Persist collection failures immediately."""
    _run_logging.log_collection_report(report)


def pytest_sessionfinish(session: pytest.Session, exitstatus: int | pytest.ExitCode) -> None:
    """Fail incomplete serial runs and sessions with unresolved fixture requests, then finalize metadata."""
    del exitstatus
    marker_hook.fail_session_on_held_serials(session)
    fixture_resolution_hook.fail_session_on_refused_requests(session)
    _run_logging.finish(session.config, session.exitstatus)


def pytest_testnodedown(node: object, error: object | None) -> None:
    """Collect serial items held, and fixture requests refused, inside an xdist worker."""
    del error
    marker_hook.record_held_from_node(node)
    fixture_resolution_hook.record_refused_from_node(node)


@pytest.hookimpl(trylast=True)
def pytest_unconfigure(config: pytest.Config) -> None:
    """Restate the run-log location beneath the terminal reporter's last word."""
    _run_logging.restate(config)


@pytest.fixture(scope="session")
def _resident_service_environment() -> Iterator[None]:
    """Give resident-service child processes one isolated singleton scope."""
    with TemporaryDirectory(prefix="vaultspec-rag-pytest-") as root_text:
        root = Path(root_text)
        status_dir = root / "status"
        qdrant_dir = root / "qdrant"
        status_dir.mkdir()
        qdrant_dir.mkdir()
        with temporary_env(
            _VAULTSPEC_RAG_PYTEST_SINGLETON_ROOT=str(root),
            _VAULTSPEC_RAG_PYTEST_SINGLETON_ACTIVE="1",
            VAULTSPEC_RAG_STATUS_DIR=str(status_dir),
            VAULTSPEC_RAG_QDRANT_STORAGE_DIR=str(qdrant_dir),
        ):
            yield


@pytest.fixture(autouse=True)
def _inherit_resident_service_environment(request: pytest.FixtureRequest) -> None:
    """Activate the shared singleton scope only for resident-service tests."""
    if request.node.get_closest_marker("resident_service") is not None:
        request.getfixturevalue("_resident_service_environment")


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Apply the repository-wide collection-policy contracts."""
    # First, before the marker contract holds serial items back and before
    # marker selection deselects anything: a dead test must be refused even in
    # a lane that would never execute it.
    fixture_resolution_hook.apply(config, items)
    marker_hook.apply(config, items)
    marker_hook.apply_banned_live_import_policy(items)
    # Recorded here, before selection removes anything, so the empty-selection
    # banner can name the markers these tests actually carry instead of
    # guessing a lane that may be just as empty.
    deselection_hook.record_collected_markers(config, items)


def pytest_xdist_auto_num_workers(config: pytest.Config) -> int | None:
    """Delegate to the repository-owned xdist auto-width resolver."""
    return worker_count_hook.resolve_auto_num_workers(config)


def pytest_timeout_set_timer(item: pytest.Item, settings: object) -> None:
    """Delegate to the shared pre-fire host-load stamp.

    Deliberately returns ``None``: the hookspec is ``firstresult`` and
    pytest-timeout's own implementation is ``trylast``, so returning a value
    here would stop the call and leave the real timeout ceiling uninstalled.
    """
    host_load_hook.arm_pre_timeout_stamp(item, settings)
    return None


def pytest_timeout_cancel_timer(item: pytest.Item) -> None:
    """Delegate to the shared host-load stamp's cancel counterpart."""
    host_load_hook.disarm_pre_timeout_stamp(item)
    return None


def pytest_terminal_summary(
    terminalreporter: TerminalReporter,
    exitstatus: int,
    config: pytest.Config,
) -> None:
    """Delegate to the deselection, held-serial, unresolved-fixture and lost-test reporters."""
    deselection_hook.apply(terminalreporter, exitstatus, config)
    marker_hook.report_held_serials(terminalreporter)
    fixture_resolution_hook.report_refused_requests(terminalreporter)
    lost_test_hook.apply(terminalreporter, exitstatus, config)
