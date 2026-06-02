"""Documentation build conformance gate.

Runs a real nitpicky, warnings-as-errors Sphinx build and asserts it
succeeds. Every unresolved cross-reference or malformed directive fails the
build. The test carries the ``docs`` marker so it is excluded from the fast
unit lane and run via ``just docs-check``; it builds into a ``tmp_path`` and
sets ``AEAT_DOCS_OFFLINE`` so intersphinx inventories are not fetched.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.domain_core, pytest.mark.docs]

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DOCS = _REPO_ROOT / "docs"


def test_sphinx_nitpicky_build_is_clean(tmp_path: Path) -> None:
    """The nitpicky, warnings-as-errors build must succeed.

    Uses the ``dummy`` builder, not ``html``: the gate only asserts that the
    full parse and cross-reference resolution (where ``-n`` nitpicky warnings
    fire) raise no warnings under ``-W``; it does not need rendered HTML, so the
    write phase is skipped. ``-j auto`` parallelises the autodoc read across
    every core, since the cost is dominated by importing and introspecting the
    several-hundred ``automodule`` stubs. Together these cut the build from tens
    of minutes to a fraction without weakening the check.

    Args:
        tmp_path: Pytest-provided isolated output directory.
    """
    env = {**os.environ, "AEAT_DOCS_OFFLINE": "1"}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "sphinx",
            "-b",
            "dummy",
            "-n",
            "-W",
            "-j",
            "auto",
            str(_DOCS),
            str(tmp_path / "out"),
        ],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert result.returncode == 0, (
        "nitpicky sphinx build reported warnings or errors:\n"
        + (result.stdout or "")[-6000:]
        + (result.stderr or "")[-6000:]
    )
