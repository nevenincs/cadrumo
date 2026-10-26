"""The recorded worker fixture imports under its real isolated launch mode."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from cadrumo.tests.audited_process import run_audited_process
from dev._paths import REPO_ROOT

pytestmark = [pytest.mark.integration, pytest.mark.hex_core, pytest.mark.docs]


def test_isolated_worker_script_reaches_its_argument_parser(tmp_path: Path) -> None:
    result = run_audited_process(
        [sys.executable, "-I", str(REPO_ROOT / "dev/docs/sequences/runtime_fixture.py"), "--help"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert isinstance(result.stdout, str)
    assert "--storage-root" in result.stdout
    assert "--worker-id" in result.stdout
    assert "--parent-pid" in result.stdout


def test_package_import_preserves_the_import_path() -> None:
    result = run_audited_process(
        [
            sys.executable,
            "-c",
            "import sys; before = tuple(sys.path); "
            "import dev.docs.sequences.runtime_fixture; "
            "assert tuple(sys.path) == before",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
