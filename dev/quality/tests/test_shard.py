"""Real-behavior gate for the CI unit-suite shard plugin."""

from __future__ import annotations

import shutil
import subprocess
import sys
import textwrap
import uuid
from pathlib import Path

import pytest

from cadrumo.core import scan_directory

from ..._paths import REPO_ROOT
from ..shard import shard_of

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_REPO_ROOT = REPO_ROOT


def test_shard_assignment_is_a_deterministic_partition() -> None:
    """Every real unit-test module lands in exactly one of two shards."""
    files = sorted(
        path.relative_to(_REPO_ROOT).as_posix()
        for path in scan_directory(
            _REPO_ROOT / "src" / "cadrumo",
            pattern="test_*.py",
            recursive=True,
            prune_directories=("__pycache__",),
        )
    )
    assert files, "no test modules found under src/cadrumo"
    assignments = {path: shard_of(path, 2) for path in files}
    assert set(assignments.values()) <= {0, 1}
    # Both shards carry a substantial share: a degenerate hash that lumped the
    # suite into one shard would silently double one runner's wall time.
    share = sum(1 for shard in assignments.values() if shard == 0) / len(files)
    assert 0.4 < share < 0.6, f"shard balance degenerated: shard 0 holds {share:.0%}"
    # Determinism: recomputing yields the identical assignment.
    assert assignments == {path: shard_of(path, 2) for path in files}


def _collect_ids(sample_dir: Path, shard_args: list[str]) -> set[str]:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "dev.quality.shard",
            "-p",
            "no:cacheprovider",
            "--collect-only",
            "-q",
            "--no-header",
            "-n0",
            str(sample_dir),
            *shard_args,
        ],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert result.returncode in (0, 5), result.stdout + result.stderr
    return {line.strip() for line in result.stdout.splitlines() if "::" in line and not line.startswith("=")}


def test_two_shards_partition_a_real_collection() -> None:
    """Running pytest per shard collects a disjoint union of the whole suite.

    The samples live INSIDE the repo (under ``var/``): shard assignment keys
    on the repo-relative path, and a file outside the rootdir deliberately
    collects in every shard (duplicate, never lose), so an out-of-tree temp
    directory would not exercise the partition behavior.
    """
    sample_dir = _REPO_ROOT / "var" / f"shard-plugin-sample-{uuid.uuid4().hex[:8]}"
    sample_dir.mkdir(parents=True)
    try:
        for index in range(4):
            module = sample_dir / f"test_shard_sample_{index}.py"
            module.write_text(
                textwrap.dedent(
                    f"""
                    import pytest

                    pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


                    def test_case_{index}() -> None:
                        assert True
                    """
                ),
                encoding="utf-8",
            )
        unsharded = _collect_ids(sample_dir, [])
        shard_zero = _collect_ids(sample_dir, ["--num-shards", "2", "--shard-index", "0"])
        shard_one = _collect_ids(sample_dir, ["--num-shards", "2", "--shard-index", "1"])
    finally:
        shutil.rmtree(sample_dir, ignore_errors=True)
    assert unsharded, "sample collection came back empty"
    assert shard_zero | shard_one == unsharded
    assert shard_zero & shard_one == set()
