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
    """The nitpicky, warnings-as-errors HTML build must succeed.

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
            "html",
            "-n",
            "-W",
            str(_DOCS),
            str(tmp_path / "html"),
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
