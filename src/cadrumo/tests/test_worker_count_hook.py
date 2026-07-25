"""Real-subprocess proof of the ``CADRUMO_PYTEST_WORKERS`` conftest hook.

:mod:`cadrumo.tests._worker_count_hook` is a ``pytest_xdist_auto_num_workers``
hook, consulted by pytest-xdist only during ``-n auto`` resolution (not
during collection of the outer suite itself), so its behavior cannot be
proven by importing and calling the function directly -- that would only
prove the function's pure logic, not that pytest-xdist actually calls it, in
the right order, at the right moment. This module spawns a REAL, fresh
pytest subprocess against a throwaway fixture tree wired to the real hook
(the exact module under test, not a reimplementation) and asserts the
ACTUAL resolved worker count via a file the probe test writes from inside
each xdist worker process, following the same real-subprocess idiom already
established by :mod:`cadrumo.tests.test_acceptance_wall_catalogue`.

No mocks: every run below is a genuine ``pytest -n auto`` boot of the real
pytest-xdist plugin plus the real hook module.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from ._worker_count_hook import DEFAULT_WORKER_CAP, resolve_auto_num_workers

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_SUBPROCESS_TIMEOUT_SECONDS = 60

_PROBE_CONFTEST = (
    "from cadrumo.tests._worker_count_hook import resolve_auto_num_workers as pytest_xdist_auto_num_workers\n"
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


def _resolved_worker_count(*, env_var_value: str | None, numprocesses: str = "auto") -> tuple[int, str]:
    """Run the real probe fixture in a fresh pytest subprocess.

    Writes a throwaway ``conftest.py`` delegating to the real
    :func:`cadrumo.tests._worker_count_hook.resolve_auto_num_workers` and a
    probe test that records the worker count xdist actually resolved
    (``PYTEST_XDIST_WORKER_COUNT``, set by xdist inside every worker
    process) to a sentinel file.

    Args:
        env_var_value: Value to set for ``CADRUMO_PYTEST_WORKERS`` in the
            subprocess environment, or ``None`` to leave it unset.
        numprocesses: The ``-n`` value passed on the command line. ``"auto"``
            exercises the hook; an explicit count proves the hook is bypassed.

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
        env.pop("CADRUMO_PYTEST_WORKERS", None)
        if env_var_value is not None:
            env["CADRUMO_PYTEST_WORKERS"] = env_var_value

        result = subprocess.run(  # noqa: S603 - fixed interpreter argv; numprocesses is a test-local literal.
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "--no-header",
                "-p",
                "no:cacheprovider",
                "-n",
                numprocesses,
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


def test_worker_count_is_capped_when_env_var_set() -> None:
    """``CADRUMO_PYTEST_WORKERS=2`` resolves ``-n auto`` to exactly 2 workers."""
    assert callable(resolve_auto_num_workers)
    worker_count, _stderr = _resolved_worker_count(env_var_value="2")
    assert worker_count == 2


def test_worker_count_defaults_to_the_project_cap_when_unset() -> None:
    """An unset ``CADRUMO_PYTEST_WORKERS`` resolves to the project default, not the machine width.

    The cap was originally opt-in and fell through to xdist's own
    physical-core default when unset. That required every author to remember
    the variable on every invocation, so in practice it was almost never set
    and concurrent runs on a shared box multiplied the full machine width.
    """
    worker_count, _stderr = _resolved_worker_count(env_var_value=None)
    assert worker_count == DEFAULT_WORKER_CAP


def test_worker_count_falls_back_to_the_project_cap_when_invalid() -> None:
    """An invalid ``CADRUMO_PYTEST_WORKERS`` warns and uses the default, never crashes.

    A typo degrades to the safe width rather than to the wider machine
    default, so a malformed value cannot quietly buy more workers than
    setting nothing would.
    """
    worker_count, stderr = _resolved_worker_count(env_var_value="notanumber")
    assert worker_count == DEFAULT_WORKER_CAP
    assert "CADRUMO_PYTEST_WORKERS is not a number" in stderr


def test_explicit_numprocesses_bypasses_the_default() -> None:
    """An explicit ``-n <N>`` overrides the default in both directions.

    The default must never become a ceiling: xdist consults this hook only
    while resolving ``-n auto``, so anyone deliberately asking for a wider
    run still gets it. Asserted with a count ABOVE the default so a
    regression that clamped instead of defaulting would fail here.
    """
    wider = DEFAULT_WORKER_CAP + 2
    worker_count, _stderr = _resolved_worker_count(env_var_value=None, numprocesses=str(wider))
    assert worker_count == wider
