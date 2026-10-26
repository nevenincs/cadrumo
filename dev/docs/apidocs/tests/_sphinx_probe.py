"""Run bounded Sphinx probes without sharing Docutils process globals."""

from __future__ import annotations

import sys
from pathlib import Path

from dev._paths import REPO_ROOT
from dev.packaging.command_execution import run_command


def run_sphinx_probe(module: str, function: str, tmp_path: Path) -> None:
    """Execute a probe and preserve its assertions and complete diagnostics."""
    result = run_command(
        (
            sys.executable,
            "-c",
            f"import sys; from pathlib import Path; from {module} import {function}; {function}(Path(sys.argv[1]))",
            str(tmp_path),
        ),
        cwd=REPO_ROOT,
        timeout_seconds=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
