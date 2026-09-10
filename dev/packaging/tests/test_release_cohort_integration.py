"""Real clean-source integration proof for release-cohort construction."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from ..._paths import REPO_ROOT
from ...source_tree import repository_files, snapshot
from ..build_scratch_reclaim import (
    RELEASE_COHORT_INTEGRATION_FAMILY,
    matching_family,
    remove_tree,
    var_scratch_name,
)
from ..cohort_manifest import REQUIRED_ARTIFACT_KINDS
from ..release_cohort import build_release_cohort

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

#: Wall ceiling for the real double build. This test snapshots the source and
#: builds the eleven-member cohort TWICE, entirely inside child processes, so
#: it runs far past the repository's 300s default.
#:
#: It needs its own ceiling for a reason beyond simply being slow. When the
#: default fires, this test's thread is parked in a subprocess call that the
#: thread timeout method cannot interrupt -- so the xdist WORKER exits
#: uncleanly instead of the test failing, and the run is then re-scheduled or
#: wedged rather than reported. It was observed killing worker gw1.
_REAL_DOUBLE_BUILD_TIMEOUT = 3600


def _stable_source_snapshot(repo_root: Path, destination: Path) -> Path:
    """Snapshot the working repository into a source whose content cannot move.

    A cohort is always built from the enumerated content it is given — no
    revision is ever pinned or passed in, here or in production. That leaves
    this reproducibility proof one requirement: both builds must see the
    *same* content. Against the working repository they do not, because this
    tree is shared with concurrent agents and each build takes minutes, so an
    edit landing in between silently changes the second build's source.
    Snapshotting once gives the test a source nobody else edits, so "build the
    same content twice" really does build the same thing twice.
    """
    snapshot(repo_root, repository_files(repo_root), destination)
    (destination / "var").mkdir(exist_ok=True)
    return destination


@pytest.mark.timeout(_REAL_DOUBLE_BUILD_TIMEOUT)
def test_real_clean_source_build_is_complete_and_reproducible() -> None:
    """Build the real 12-member cohort twice from the same content and compare every digest."""
    repo_root = REPO_ROOT
    var = (repo_root / "var").resolve(strict=True)
    # Named through the scratch registry rather than spelled here, so the
    # collection-time reclaim and this mint site cannot disagree about the
    # family, and so the name carries this process as its owner.
    snapshot_root = var / var_scratch_name(RELEASE_COHORT_INTEGRATION_FAMILY, uuid.uuid4().hex)
    try:
        source = _stable_source_snapshot(repo_root, snapshot_root)
        outputs = (
            source / "var" / "first",
            source / "var" / "second",
        )
        # Neither build is told which content to use: each enumerates the
        # source itself, exactly as a release does. Both must land on the same one.
        first = build_release_cohort(repo_root=source, output_dir=outputs[0])
        second = build_release_cohort(repo_root=source, output_dir=outputs[1])

        assert first.manifest.source.source_digest == second.manifest.source.source_digest
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
        #
        # NOT `shutil.rmtree(..., ignore_errors=True)`. A copied source tree
        # can carry read-only members, and Windows refuses to unlink a
        # read-only file; `ignore_errors` swallows that refusal, so the block
        # reported success while leaving the copy on disk. The shared reclaim
        # clears the attribute and retries.
        resolved = snapshot_root.resolve()
        if resolved.parent == var and matching_family(resolved.name) is not None and resolved.exists():
            remove_tree(resolved)
