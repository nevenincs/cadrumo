"""Real-subprocess proof of the installed ``CADRUMO_PYTEST_WORKERS`` hook.

This module is an explicit outer-serial ``just test-harness`` member, rather
than routine unit work: each case boots a real pytest-xdist pool. It proves
the installed hook rather than replacing it with a direct helper call.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from ._worker_count_hook import DEFAULT_WORKER_COUNT

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

_SUBPROCESS_TIMEOUT_SECONDS = 60
_REPOSITORY_ROOT = Path(__file__).resolve().parents[3]

_PROBE_TEST = """
import os
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_probe():
    Path(__file__).parent.joinpath("worker_count.txt").write_text(
        str(os.environ.get("PYTEST_XDIST_WORKER_COUNT")),
        encoding="utf-8",
    )
    assert True
"""


def _resolved_worker_count(
    *,
    project_worker_count: str | None,
    native_worker_count: str | None = None,
    numprocesses: str = "auto",
    discover_root_conftest: bool = True,
) -> tuple[int, str]:
    """Run a probe through the repository root's installed pytest hook."""
    with tempfile.TemporaryDirectory(prefix=".worker-count-hook-", dir=_REPOSITORY_ROOT) as tmp_dir:
        tmp_path = Path(tmp_dir)
        probe_path = tmp_path / "test_probe.py"
        probe_path.write_text(_PROBE_TEST, encoding="utf-8")

        env = dict(os.environ)
        env.pop("CADRUMO_PYTEST_WORKERS", None)
        env.pop("PYTEST_XDIST_AUTO_NUM_WORKERS", None)
        if project_worker_count is not None:
            env["CADRUMO_PYTEST_WORKERS"] = project_worker_count
        if native_worker_count is not None:
            env["PYTEST_XDIST_AUTO_NUM_WORKERS"] = native_worker_count

        command = [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "--no-header",
            "-p",
            "no:cacheprovider",
            "-n",
            numprocesses,
        ]
        if not discover_root_conftest:
            command.extend(("--confcutdir", str(tmp_path)))
        command.append(str(probe_path))

        result = subprocess.run(  # noqa: S603 - fixed interpreter argv; remaining values are test-local literals.
            command,
            cwd=_REPOSITORY_ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=_SUBPROCESS_TIMEOUT_SECONDS,
        )
        sentinel = tmp_path / "worker_count.txt"
        assert sentinel.is_file(), (
            f"probe subprocess did not write the sentinel file; "
            f"returncode={result.returncode} stdout={result.stdout!r} stderr={result.stderr!r}"
        )
        return int(sentinel.read_text(encoding="utf-8")), result.stderr


def test_project_worker_count_overrides_auto_resolution() -> None:
    """Root discovery makes the project variable the sole environment authority."""
    worker_count, _stderr = _resolved_worker_count(project_worker_count="2", native_worker_count="3")
    assert worker_count == 2

    without_root_hook, _stderr = _resolved_worker_count(
        project_worker_count="2",
        native_worker_count="3",
        discover_root_conftest=False,
    )
    assert without_root_hook == 3


def test_worker_count_defaults_to_six_without_project_override() -> None:
    """The repository default wins even when xdist's native variable is set."""
    worker_count, _stderr = _resolved_worker_count(project_worker_count=None, native_worker_count="2")
    assert worker_count == DEFAULT_WORKER_COUNT


def test_worker_count_falls_back_to_the_project_default_when_invalid() -> None:
    """An invalid ``CADRUMO_PYTEST_WORKERS`` warns and uses the default, never crashes."""
    worker_count, stderr = _resolved_worker_count(project_worker_count="notanumber", native_worker_count="2")
    assert worker_count == DEFAULT_WORKER_COUNT
    assert "CADRUMO_PYTEST_WORKERS is not a number" in stderr


def test_explicit_numprocesses_bypasses_the_default() -> None:
    """An explicit ``-n <N>`` bypasses both environment values."""
    wider = DEFAULT_WORKER_COUNT + 2
    worker_count, _stderr = _resolved_worker_count(
        project_worker_count="2",
        native_worker_count="3",
        numprocesses=str(wider),
    )
    assert worker_count == wider
