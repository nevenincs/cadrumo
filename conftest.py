"""Repo-root pytest conftest.

Hosts the hexagonal marker collection hook from the repo root so every
item gathered under ``src/cadrumo/...`` passes through the same enforcement
surface. The hook body lives in :mod:`cadrumo.tests._marker_hook`; this
conftest is a thin wrapper.

Also hosts the project-branded ``CADRUMO_PYTEST_WORKERS`` worker-count policy
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
from pathlib import Path
from tempfile import TemporaryDirectory

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

from cadrumo.tests import collection_storage_root  # noqa: E402
from cadrumo.tests._env_loader import bridge_env_file_into_environ  # noqa: E402

# Bridge the operator's development-only env/.env dotfile into os.environ
# BEFORE any Cadrumo import resolves Settings (production Settings carries
# no dotenv source of its own — see core.config.Settings). setdefault
# semantics inside the bridge keep a real ambient environment variable
# authoritative; the dotfile only fills gaps. Safe to import cadrumo.tests
# here (unlike the storage-root line above): the storage-root env var this
# module's own import surface might trigger a premature configure_logging()
# against is already set by the pure-stdlib line above.
bridge_env_file_into_environ(Path(__file__).resolve().parent / "env" / ".env")

from collections.abc import Iterator  # noqa: E402
from typing import TYPE_CHECKING  # noqa: E402

import pytest  # noqa: E402

from cadrumo.tests import register_collection_storage_root_cleanup, temporary_env  # noqa: E402
from cadrumo.tests._deselection_hook import apply as _report_deselection  # noqa: E402
from cadrumo.tests._host_load_hook import arm_pre_timeout_stamp as _arm_host_load_stamp  # noqa: E402
from cadrumo.tests._host_load_hook import disarm_pre_timeout_stamp as _disarm_host_load_stamp  # noqa: E402
from cadrumo.tests._marker_hook import apply as _apply_marker_contract  # noqa: E402
from cadrumo.tests._marker_hook import apply_banned_live_import_policy as _apply_banned_live_import_policy  # noqa: E402
from cadrumo.tests._worker_count_hook import resolve_auto_num_workers as _resolve_auto_num_workers  # noqa: E402

if TYPE_CHECKING:
    from _pytest.terminal import TerminalReporter

register_collection_storage_root_cleanup(collection_storage_root())


@pytest.fixture(scope="session")
def _resident_service_environment(
) -> Iterator[None]:
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
    _apply_marker_contract(config, items)
    _apply_banned_live_import_policy(items)


def pytest_xdist_auto_num_workers(config: pytest.Config) -> int | None:
    """Delegate to the repository-owned xdist auto-width resolver."""
    return _resolve_auto_num_workers(config)


def pytest_timeout_set_timer(item: pytest.Item, settings: object) -> None:
    """Delegate to the shared pre-fire host-load stamp.

    Deliberately returns ``None``: the hookspec is ``firstresult`` and
    pytest-timeout's own implementation is ``trylast``, so returning a value
    here would stop the call and leave the real timeout ceiling uninstalled.
    """
    _arm_host_load_stamp(item, settings)
    return None


def pytest_timeout_cancel_timer(item: pytest.Item) -> None:
    """Delegate to the shared host-load stamp's cancel counterpart."""
    _disarm_host_load_stamp(item)
    return None


def pytest_terminal_summary(
    terminalreporter: TerminalReporter,
    exitstatus: int,
    config: pytest.Config,
) -> None:
    """Delegate to the shared marker-deselection reporter."""
    _report_deselection(terminalreporter, exitstatus, config)
