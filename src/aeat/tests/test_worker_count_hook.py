"""Real-subprocess proof of the ``AEAT_PYTEST_WORKERS`` conftest hook.

:mod:`aeat.tests._worker_count_hook` is a ``pytest_xdist_auto_num_workers``
hook, consulted by pytest-xdist only during ``-n auto`` resolution (not
during collection of the outer suite itself), so its behavior cannot be
proven by importing and calling the function directly -- that would only
prove the function's pure logic, not that pytest-xdist actually calls it, in
the right order, at the right moment. This module spawns a REAL, fresh
pytest subprocess against a throwaway fixture tree wired to the real hook
(the exact module under test, not a reimplementation) and asserts the
ACTUAL resolved worker count via a file the probe test writes from inside
each xdist worker process, following the same real-subprocess idiom already
established by :mod:`aeat.tests.test_acceptance_wall_catalogue`.

No mocks: every run below is a genuine ``pytest -n auto`` boot of the real
pytest-xdist plugin plus the real hook module.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import psutil
import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_SUBPROCESS_TIMEOUT_SECONDS = 60

_PROBE_CONFTEST = (
    "from aeat.tests._worker_count_hook import resolve_auto_num_workers as "
    "pytest_xdist_auto_num_workers\n"
)
_PROBE_TEST = """
import os
from pathlib import Path


def test_probe():
    Path(__file__).parent.joinpath("worker_count.txt").write_text(
        str(os.environ.get("PYTEST_XDIST_WORKER_COUNT")),
        encoding="utf-8",
    )
    assert True
"""


def _resolved_worker_count(*, env_var_value: str | None) -> tuple[int, str]:
    """Run the real probe fixture in a fresh pytest subprocess.

    Writes a throwaway ``conftest.py`` delegating to the real
    :func:`aeat.tests._worker_count_hook.resolve_auto_num_workers` and a
    probe test that records the worker count xdist actually resolved
    (``PYTEST_XDIST_WORKER_COUNT``, set by xdist inside every worker
    process) to a sentinel file.

    Args:
        env_var_value: Value to set for ``AEAT_PYTEST_WORKERS`` in the
            subprocess environment, or ``None`` to leave it unset.

    Returns:
        A ``(worker_count, stderr)`` pair -- the resolved worker count and
        the subprocess's captured stderr (for asserting on emitted
        warnings).
    """
    with tempfile.TemporaryDirectory(prefix="worker-count-hook-poc-") as tmp_dir:
        tmp_path = Path(tmp_dir)
        (tmp_path / "conftest.py").write_text(_PROBE_CONFTEST, encoding="utf-8")
        (tmp_path / "test_probe.py").write_text(_PROBE_TEST, encoding="utf-8")

        env = dict(os.environ)
        env.pop("AEAT_PYTEST_WORKERS", None)
        if env_var_value is not None:
            env["AEAT_PYTEST_WORKERS"] = env_var_value

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "--no-header",
                "-p",
                "no:cacheprovider",
                "-n",
                "auto",
                "test_probe.py",
            ],
            cwd=tmp_path,
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


def _xdist_default_worker_count() -> int:
    """Return the worker count xdist's own ``-n auto`` default resolves to.

    Mirrors ``xdist.plugin.pytest_xdist_auto_num_workers``'s own algorithm
    for non-``logical`` ``-n auto`` (``psutil.cpu_count(logical=False)``),
    computed fresh at test time so the expectation adapts to whatever
    machine runs the suite rather than a hardcoded core count.
    """
    return psutil.cpu_count(logical=False) or psutil.cpu_count() or 1


def test_worker_count_is_capped_when_env_var_set() -> None:
    """``AEAT_PYTEST_WORKERS=2`` resolves ``-n auto`` to exactly 2 workers."""
    worker_count, _stderr = _resolved_worker_count(env_var_value="2")
    assert worker_count == 2


def test_worker_count_falls_through_to_xdist_default_when_unset() -> None:
    """An unset ``AEAT_PYTEST_WORKERS`` falls through byte-for-byte to xdist's own default."""
    worker_count, _stderr = _resolved_worker_count(env_var_value=None)
    assert worker_count == _xdist_default_worker_count()


def test_worker_count_falls_through_when_invalid_not_a_crash() -> None:
    """An invalid ``AEAT_PYTEST_WORKERS`` falls through to the default and warns, never crashes."""
    worker_count, stderr = _resolved_worker_count(env_var_value="notanumber")
    assert worker_count == _xdist_default_worker_count()
    assert "AEAT_PYTEST_WORKERS is not a number" in stderr
