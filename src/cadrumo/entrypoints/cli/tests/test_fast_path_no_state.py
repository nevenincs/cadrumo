"""Fast-path proof: ``aeat --version`` and ``aeat --help`` never touch state.

The fast-path contract closes the cold-start 10-minute hang: the
``--version`` and ``--help`` surfaces must return without reading
encrypted state, opening a master-key session, or running registry
validation. The original disaster routed ``--version`` through a full
registry TOML parse and bare invocation through a state-requiring
workflow load.

These tests run both surfaces against a *clean* storage root — no
profile pointer, no encrypted database, no buckets directory — and
assert each completes in well under 200 ms. A regression that
re-introduces a registry parse or a state read on either surface
blows the budget by orders of magnitude (the registry probe alone
takes tens of seconds), so the timing assertion is a real
structural guard, not a micro-benchmark.

The CLI is invoked in-process through the cached Click command, the
same harness every other CLI test uses; the budget excludes Python
interpreter and import startup, which an operator pays once.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from ....core import StorageCategory, storage_location
from ....core.product_identity import PRODUCT_IDENTITY
from ....core.bucket_pointer import pointer_path
from ....core.directory_scan import iter_directory
from ....tests.cli_runner import invoke_cached_cli
from ._sessionless_root_fixtures import _sessionless_root

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

if TYPE_CHECKING:
    from click.testing import Result

# In-process budget for a state-free surface. `--version` resolves in
# ~15 ms and `--help` in ~25 ms once imports are warm; 200 ms is the
# fast-path ceiling with generous headroom. A re-introduced
# registry parse or state read overshoots this by 100x or more.
_FAST_PATH_BUDGET_MS = 200.0


__all__ = ["_sessionless_root"]


def _warm() -> None:
    """Prime the cached Click command + module imports before timing."""

    invoke_cached_cli(["--version"])
    invoke_cached_cli(["--help"])


def _fastest_ms(args: list[str], *, runs: int = 5) -> tuple[float, Result]:
    """Return the fastest wall-clock of ``runs`` invocations and the last result."""

    best = float("inf")
    start = time.perf_counter()
    result = invoke_cached_cli(args)
    best = min(best, (time.perf_counter() - start) * 1000.0)
    for _ in range(runs - 1):
        start = time.perf_counter()
        result = invoke_cached_cli(args)
        best = min(best, (time.perf_counter() - start) * 1000.0)
    return best, result


def test_version_completes_under_budget_on_clean_root(_sessionless_root: Path) -> None:
    """``aeat --version`` returns inside the fast-path budget."""

    _warm()
    elapsed_ms, result = _fastest_ms(["--version"])
    assert result.exit_code == 0, result.output
    assert result.output.startswith(f"{PRODUCT_IDENTITY.display_name} ")
    assert elapsed_ms < _FAST_PATH_BUDGET_MS, f"--version took {elapsed_ms:.1f}ms (budget {_FAST_PATH_BUDGET_MS}ms)"


def test_help_completes_under_budget_on_clean_root(_sessionless_root: Path) -> None:
    """``aeat --help`` returns inside the fast-path budget."""

    _warm()
    elapsed_ms, result = _fastest_ms(["--help"])
    assert result.exit_code == 0, result.output
    assert elapsed_ms < _FAST_PATH_BUDGET_MS, f"--help took {elapsed_ms:.1f}ms (budget {_FAST_PATH_BUDGET_MS}ms)"


def test_version_does_not_provision_storage(_sessionless_root: Path) -> None:
    """``aeat --version`` writes nothing under the storage root.

    A registry parse or a state read would create a database file, a
    buckets directory, or an active-profile pointer as a side effect.
    The clean root must stay clean.
    """

    _warm()
    result = invoke_cached_cli(["--version"])
    assert result.exit_code == 0, result.output
    assert not (_sessionless_root / storage_location(StorageCategory.BUCKETS).relative_path()).exists()
    assert not pointer_path(_sessionless_root).exists()
    assert not any(iter_directory(_sessionless_root, pattern="*.db", recursive=True))


def test_help_does_not_provision_storage(_sessionless_root: Path) -> None:
    """``aeat --help`` writes nothing under the storage root."""

    _warm()
    result = invoke_cached_cli(["--help"])
    assert result.exit_code == 0, result.output
    assert not (_sessionless_root / storage_location(StorageCategory.BUCKETS).relative_path()).exists()
    assert not pointer_path(_sessionless_root).exists()
    assert not any(iter_directory(_sessionless_root, pattern="*.db", recursive=True))
