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

from ._worker_count_hook import DEFAULT_WORKER_CAP

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

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
    """Run the real probe fixture in a fresh pytest subprocess."""
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
    worker_count, _stderr = _resolved_worker_count(env_var_value="2")
    assert worker_count == 2


def test_worker_count_defaults_to_the_project_cap_when_unset() -> None:
    """An unset ``CADRUMO_PYTEST_WORKERS`` resolves to the project default, not the machine width."""
    worker_count, _stderr = _resolved_worker_count(env_var_value=None)
    assert worker_count == DEFAULT_WORKER_CAP


def test_worker_count_falls_back_to_the_project_cap_when_invalid() -> None:
    """An invalid ``CADRUMO_PYTEST_WORKERS`` warns and uses the default, never crashes."""
    worker_count, stderr = _resolved_worker_count(env_var_value="notanumber")
    assert worker_count == DEFAULT_WORKER_CAP
    assert "CADRUMO_PYTEST_WORKERS is not a number" in stderr


def test_explicit_numprocesses_bypasses_the_default() -> None:
    """An explicit ``-n <N>`` overrides the default in both directions."""
    wider = DEFAULT_WORKER_CAP + 2
    worker_count, _stderr = _resolved_worker_count(env_var_value=None, numprocesses=str(wider))
    assert worker_count == wider
