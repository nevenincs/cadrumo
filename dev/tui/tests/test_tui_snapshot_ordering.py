"""What survives a failure in the middle of replacing a snapshot.

A snapshot used to be built by removing the named directory and then copying
the current review over it. The end state of that sequence and of the staged
one are identical, so nothing that asserts the end state can tell them apart.
Only a failure BETWEEN the two steps separates them, and that is what these
exercise: the copy is interrupted, and what is left on disk is measured. Under
the old order the named snapshot was already gone and a partial tree stood in
its place, still carrying the manifest that makes `known_runs` call a
directory a review.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from .._artifacts import (
    MANIFEST_NAME,
    RUNS_DIR,
    commit_staged_run,
    snapshot_staging_directory,
    stage_run_copy,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


class _InterruptedCopyError(RuntimeError):
    """Stands in for anything that can end a copy part way."""


def _run_tree(root: Path, marker: str) -> Path:
    """Build a directory shaped like a run: a manifest plus some frames."""
    root.mkdir(parents=True)
    (root / MANIFEST_NAME).write_text(f"{marker}-manifest", encoding="utf-8", newline="\n")
    frames = root / "frames"
    frames.mkdir()
    for index in range(4):
        (frames / f"{index}.png").write_text(f"{marker}-{index}", encoding="utf-8", newline="\n")
    return root


def _contents(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_a_copy_that_never_commits_leaves_the_old_snapshot_whole(tmp_path: Path) -> None:
    """The window proof: stage, do not commit, then measure the destination."""
    source = _run_tree(tmp_path / "current", "new")
    destination = _run_tree(tmp_path / "keep", "old")
    before = _contents(destination)

    stage_run_copy(source, tmp_path / "staging")

    assert _contents(destination) == before
    assert (destination / MANIFEST_NAME).read_text(encoding="utf-8") == "old-manifest"


def test_a_failure_raised_between_the_two_steps_costs_nothing(tmp_path: Path) -> None:
    """A real exception in the window, and the state it leaves behind."""
    source = _run_tree(tmp_path / "current", "new")
    destination = _run_tree(tmp_path / "keep", "old")
    staging = tmp_path / "staging"
    before = _contents(destination)

    with pytest.raises(_InterruptedCopyError):
        stage_run_copy(source, staging)
        raise _InterruptedCopyError("interrupted before the swap")

    assert _contents(destination) == before
    assert _contents(staging) == _contents(source)


def test_the_residual_window_parks_a_complete_copy_that_a_retry_commits(tmp_path: Path) -> None:
    """The failure mode the new order accepts, and its recovery.

    Between the removal of the destination and the rename there is still a
    window. Its cost is a MISSING snapshot beside a complete staged copy, not
    a destroyed one beside a partial tree, and a second commit closes it
    without touching the source.
    """
    source = _run_tree(tmp_path / "current", "new")
    destination = _run_tree(tmp_path / "keep", "old")
    staging = tmp_path / "staging"
    stage_run_copy(source, staging)

    shutil.rmtree(destination)

    assert not destination.exists()
    assert _contents(staging) == _contents(source)

    commit_staged_run(staging, destination)

    assert _contents(destination) == _contents(source)
    assert _contents(source) == {
        "manifest.json": "new-manifest",
        "frames/0.png": "new-0",
        "frames/1.png": "new-1",
        "frames/2.png": "new-2",
        "frames/3.png": "new-3",
    }


def test_the_old_order_leaves_a_partial_tree_that_still_looks_like_a_run(tmp_path: Path) -> None:
    """The defect the split exists to prevent, reproduced in isolation.

    Remove-then-copy, against the same trees, interrupted at the same point.
    Nothing production is patched: the retired sequence is written out here
    so its cost can be measured beside the staged one. What stands at the
    named path afterwards is neither the old review nor the new one, and it
    carries a manifest, which is the whole of what makes `known_runs` call
    a directory a run.
    """
    source = _run_tree(tmp_path / "current", "new")
    destination = _run_tree(tmp_path / "keep", "old")
    kept = _contents(destination)

    with pytest.raises(_InterruptedCopyError):
        shutil.rmtree(destination)
        destination.mkdir()
        shutil.copy2(source / MANIFEST_NAME, destination / MANIFEST_NAME)
        raise _InterruptedCopyError("interrupted part way through the copy")

    assert _contents(destination) != kept
    assert _contents(destination) == {"manifest.json": "new-manifest"}
    assert not (destination / "frames").exists()


def test_committing_replaces_the_destination_and_consumes_the_staging_path(tmp_path: Path) -> None:
    source = _run_tree(tmp_path / "current", "new")
    destination = _run_tree(tmp_path / "keep", "old")
    staging = tmp_path / "staging"

    stage_run_copy(source, staging)
    commit_staged_run(staging, destination)

    assert _contents(destination) == _contents(source)
    assert not staging.exists()


def test_restaging_discards_only_the_residue_of_an_earlier_attempt(tmp_path: Path) -> None:
    """The one removal inside the staging step, and what it may destroy."""
    source = _run_tree(tmp_path / "current", "new")
    staging = _run_tree(tmp_path / "staging", "abandoned")

    stage_run_copy(source, staging)

    assert _contents(staging) == _contents(source)


def test_a_staged_copy_is_never_where_known_runs_looks() -> None:
    """Staging lives outside `runs/`, so a half-built copy is never a review.

    A staged copy holds the source run's manifest from its first moment, and
    `known_runs` calls any directory under `runs/` holding a manifest a run.
    Parked as a sibling of the snapshots, an interrupted copy would be listed
    as one.
    """
    staging = snapshot_staging_directory(RUNS_DIR / "release-review")

    assert RUNS_DIR not in staging.parents
    assert staging.parent.name == "scratch"


def test_staging_shares_a_filesystem_with_the_destination(tmp_path: Path) -> None:
    """The swap is a rename, and a rename cannot cross a drive.

    Read off a module constant instead, the staged copy landed wherever the
    repository sits while the destination was somewhere else, and the swap
    died with WinError 17 -- after the destination had been removed. The
    staging path is therefore derived from the destination.
    """
    destination = tmp_path / "runs" / "baseline"

    staging = snapshot_staging_directory(destination)

    assert staging.drive == destination.drive
    assert staging.parent.parent == destination.parent.parent
