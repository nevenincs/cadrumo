"""Real clean-source integration proof for release-cohort construction."""

from __future__ import annotations

import shutil
import subprocess
import uuid
from pathlib import Path

import pytest

from dev._paths import REPO_ROOT

from ..cohort_manifest import REQUIRED_ARTIFACT_KINDS
from ..release_cohort import build_release_cohort

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

#: Wall ceiling for the real double build. This test clones the source and
#: builds the twelve-member cohort TWICE, entirely inside child processes, so
#: it runs far past the repository's 300s default.
#:
#: It needs its own ceiling for a reason beyond simply being slow. When the
#: default fires, this test's thread is parked in a subprocess call that the
#: thread timeout method cannot interrupt -- so the xdist WORKER exits
#: uncleanly instead of the test failing, and the run is then re-scheduled or
#: wedged rather than reported. It was observed killing worker gw1.
_REAL_DOUBLE_BUILD_TIMEOUT = 3600


def _stable_source_clone(repo_root: Path, destination: Path) -> Path:
    """Clone the working repository into a source whose tip cannot move.

    A cohort is always built from the tip of the branch it is told to build —
    no commit is ever pinned or passed in, here or in production. That leaves
    this reproducibility proof one requirement: both builds must see the *same*
    tip. Against the working repository they do not, because this tree is shared
    with concurrent agents and each build takes minutes, so a commit landing in
    between silently changes the second build's source. Cloning once gives the
    test a source nobody else commits to, so "build the tip twice" really does
    build the same thing twice.

    The clone is ``--no-checkout``: the builder reads this source's tip and
    clones it again into its own clean tree, so materializing a second copy of
    the (large) working tree would cost minutes and gigabytes per run for
    nothing. Objects are hardlinked from the local source, keeping the clone
    fast and near-free on disk. It must itself be a repository — a plain
    directory under ``var/`` would let git resolve the tip from the enclosing
    working tree and put the moving target straight back.
    """
    git = shutil.which("git")
    if git is None:
        raise RuntimeError("git is required to clone the release-cohort source")
    subprocess.run(  # noqa: S603 - fixed git argv over a local path
        [git, "-c", "core.longpaths=true", "clone", "--no-checkout", "--quiet", str(repo_root), str(destination)],
        check=True,
        capture_output=True,
        text=True,
    )
    (destination / "var").mkdir(exist_ok=True)
    return destination


@pytest.mark.timeout(_REAL_DOUBLE_BUILD_TIMEOUT)
def test_real_clean_source_build_is_complete_and_reproducible() -> None:
    """Build the real 12-member cohort twice from the branch tip and compare every digest."""
    repo_root = REPO_ROOT
    var = (repo_root / "var").resolve(strict=True)
    run_id = uuid.uuid4().hex
    snapshot = var / f"release-cohort-integration-{run_id}-source"
    try:
        source = _stable_source_clone(repo_root, snapshot)
        outputs = (
            source / "var" / "first",
            source / "var" / "second",
        )
        # Neither build is told which commit to use: each resolves the tip
        # itself, exactly as a release does. Both must land on the same one.
        first = build_release_cohort(repo_root=source, output_dir=outputs[0])
        second = build_release_cohort(repo_root=source, output_dir=outputs[1])

        assert first.manifest.source.commit == second.manifest.source.commit
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
