"""Real clean-source integration proof for release-cohort construction."""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path

import pytest

from dev.packaging.cohort_manifest import REQUIRED_ARTIFACT_KINDS
from dev.packaging.release_cohort import build_release_cohort

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_real_clean_source_build_is_complete_and_reproducible() -> None:
    """Build the real 12-member cohort twice from HEAD and compare every digest."""
    repo_root = Path(__file__).resolve().parents[3]
    var = (repo_root / "var").resolve(strict=True)
    run_id = uuid.uuid4().hex
    outputs = (
        var / f"release-cohort-integration-{run_id}-first",
        var / f"release-cohort-integration-{run_id}-second",
    )
    try:
        first = build_release_cohort(repo_root=repo_root, output_dir=outputs[0])
        second = build_release_cohort(
            repo_root=repo_root,
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
        for output in outputs:
            resolved = output.resolve()
            if (
                resolved.parent == var
                and resolved.name.startswith(f"release-cohort-integration-{run_id}-")
                and resolved.exists()
            ):
                shutil.rmtree(resolved)
