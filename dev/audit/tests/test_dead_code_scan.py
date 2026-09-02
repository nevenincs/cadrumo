"""The dead-code gate that runs a real vulture scan over the tree.

Spawns the real ``uv run --no-sync vulture`` invocation and reads what it
actually reports, so this is ``integration``: it needs the real dev
dependency installed and walks the whole production tree. The parsing and
classification checks are in ``test_dead_code``; this module only proves the
runner against a live process.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from ..._paths import REPO_ROOT
from ..dead_code import DeadCodeOutcome, run_dead_code_scan

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

_REPO_ROOT = REPO_ROOT


def test_real_scan_over_the_tree_returns_a_typed_outcome_with_real_findings() -> None:
    """A real vulture run classifies to CLEAN or FINDINGS, never a crash.

    No self-skip on a clean tree (forbidden by ``test_no_skip_xfail`` for
    tests outside the source tree, per the sibling ``test_duplication_scan``'s
    own convention): both branches are asserted inside one test instead.
    """
    result = run_dead_code_scan(_REPO_ROOT)

    assert result.outcome in {DeadCodeOutcome.CLEAN, DeadCodeOutcome.FINDINGS}
    assert result.headline()

    if result.outcome is DeadCodeOutcome.FINDINGS:
        for finding in result.findings:
            assert (_REPO_ROOT / finding.path).is_file(), f"vulture named a path that does not exist: {finding.path}"
            assert finding.line > 0
            assert 0 <= finding.confidence <= 100


@pytest.mark.parametrize("unused_name", ("quota_project_id", "clock_skew_in_seconds", "interaction_facts"))
def test_whitelist_does_not_mask_former_protocol_parameter_names(tmp_path: Path, unused_name: str) -> None:
    """The live whitelist leaves unrelated unused names detectable by vulture."""
    candidate = tmp_path / "candidate.py"
    candidate.write_text(f"def {unused_name}():\n    pass\n", encoding="utf-8")

    completed = subprocess.run(  # noqa: S603 - fixed argv, no shell
        [  # noqa: S607 - fixed executable path within the project environment
            "uv",
            "run",
            "--no-sync",
            "vulture",
            "--config",
            "pyproject.toml",
            str(candidate),
            "dev/audit/vulture_whitelist.py",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        cwd=_REPO_ROOT,
    )

    assert completed.returncode == 3, completed.stderr
    assert f"unused function '{unused_name}'" in completed.stdout
