"""Real clean-source integration proof for release-cohort construction."""

from __future__ import annotations

import shutil
import subprocess
import uuid
from pathlib import Path

import pytest

from dev.packaging.cohort_manifest import REQUIRED_ARTIFACT_KINDS
from dev.packaging.release_cohort import build_release_cohort

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _pin_source_snapshot(repo_root: Path, destination: Path) -> Path:
    """Clone the current HEAD into a snapshot whose commit cannot move.

    ``build_release_cohort`` re-reads the live HEAD on every call and refuses
    when it no longer equals the requested commit — a correct release-integrity
    guard, since a cohort must be bound to a known commit. Running the two
    builds directly against the working repository therefore races: this tree is
    shared with concurrent agents, each build takes minutes, and any commit
    landing in between fails the second call. Cloning once pins the commit for
    the whole test, so the proof exercises the real guard instead of tripping
    over it.

    The clone is ``--no-checkout``: the builder only reads this snapshot's HEAD
    and clones it again into its own clean tree, so materializing a second copy
    of the (large) working tree would cost minutes and gigabytes per run for
    nothing. Objects are hardlinked from the local source, keeping the snapshot
    fast and near-free on disk. The snapshot must itself be a repository — a
    plain directory under ``var/`` would let git resolve HEAD from the enclosing
    working tree and reintroduce the very race this removes.
    """
    git = shutil.which("git")
    if git is None:
        raise RuntimeError("git is required to pin the release-cohort source snapshot")
    subprocess.run(  # noqa: S603 - fixed git argv over a local path
        [git, "-c", "core.longpaths=true", "clone", "--no-checkout", "--quiet", str(repo_root), str(destination)],
        check=True,
        capture_output=True,
        text=True,
    )
    (destination / "var").mkdir(exist_ok=True)
    return destination


def test_real_clean_source_build_is_complete_and_reproducible() -> None:
    """Build the real 12-member cohort twice from one pinned commit and compare every digest."""
    repo_root = Path(__file__).resolve().parents[3]
    var = (repo_root / "var").resolve(strict=True)
    run_id = uuid.uuid4().hex
    snapshot = var / f"release-cohort-integration-{run_id}-source"
    try:
        source = _pin_source_snapshot(repo_root, snapshot)
        outputs = (
            source / "var" / "first",
            source / "var" / "second",
        )
        first = build_release_cohort(repo_root=source, output_dir=outputs[0])
        second = build_release_cohort(
            repo_root=source,
            output_dir=outputs[1],
            expected_commit=first.manifest.source.commit,
        )

        assert first.manifest.cohort_id == second.manifest.cohort_id
        assert first.manifest.source == second.manifest.source
        assert {record.name for record in first.manifest.artifacts} == set(
            REQUIRED_ARTIFACT_KINDS,
        )
        assert tuple(
            (
                record.name,
                record.kind,
                record.path,
                record.sha256,
                record.size,
            )
            for record in first.manifest.artifacts
        ) == tuple(
            (
                record.name,
                record.kind,
                record.path,
                record.sha256,
                record.size,
            )
            for record in second.manifest.artifacts
        )
    finally:
        # One removal covers both cohorts: they are built inside the snapshot.
        resolved = snapshot.resolve()
        if (
            resolved.parent == var
            and resolved.name == f"release-cohort-integration-{run_id}-source"
            and resolved.exists()
        ):
            shutil.rmtree(resolved, ignore_errors=True)
