"""``python -m dev.registry.analysis.load_census`` must run to a report, not die sharing its graph."""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from dev.paths import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_the_module_entry_builds_and_shares_the_import_graph() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "dev.registry.analysis.load_census", "--json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=600,
    )

    assert "may not name __main__" not in completed.stderr, completed.stderr[-2000:]
    report = json.loads(completed.stdout)
    assert report["closure"], "the census reported an empty import closure"
    assert report["universe"], "the census reported an empty universe"
