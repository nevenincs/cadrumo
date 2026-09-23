"""Run the documentation Worker's own unit tests under Node.

The Worker is JavaScript, so its routing, 404 and release-header behaviour is
tested where it runs. It carries ``external_tool`` because it needs Node, which
the default unit lane cannot assume; ``just test-docs-worker`` runs it.
"""

from __future__ import annotations

import shutil
import subprocess

import pytest

from dev._paths import REPO_ROOT

pytestmark = [pytest.mark.integration, pytest.mark.hex_core, pytest.mark.external_tool]

_WORKER_TESTS = REPO_ROOT / "worker" / "docs-site.test.mjs"


def test_the_worker_suite_passes_under_node() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.fail("node is not on PATH; the Worker suite cannot run without it")
    completed = subprocess.run(  # noqa: S603 - fixed argv: the resolved node binary and a repository file
        [node, "--test", str(_WORKER_TESTS)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
