"""Shared genuine release-cohort fixture builder for the packaging evidence tests.

Underscore-prefixed so it is never collected as a test module. Consolidates
three near-identical ``_release_cohort`` copies (test_evidence.py,
test_distribution_evidence_emit.py, test_evidence_scrub.py) that built the
same real on-disk cohort — every :data:`~dev.packaging.cohort_manifest.REQUIRED_ARTIFACT_KINDS`
artifact, a real manifest, a real ``load_release_cohort`` read-back — and
differed only in filler identity values (version, commit, digest bytes) that
no test asserts against, plus one non-deterministic ``datetime.now(UTC)``
timestamp that the other two copies already pinned. None of the three callers
depended on the exact filler bytes, so one shared default set replaces three
arbitrary ones; the deterministic timestamp is kept as the sole default since
a wall-clock fixture value is never reproducible and nothing read it.
"""

from __future__ import annotations

import platform
from datetime import UTC, datetime
from pathlib import Path

from ..cohort_manifest import (
    REQUIRED_ARTIFACT_KINDS,
    BuildIdentity,
    LoadedReleaseCohort,
    SourceIdentity,
    create_manifest,
    load_release_cohort,
    write_manifest,
)

DEFAULT_COHORT_VERSION = "0.2.1"
DEFAULT_COHORT_COMMIT = "c" * 40
DEFAULT_COHORT_BUILD_CONSTRAINTS_SHA256 = "d" * 64
DEFAULT_COHORT_CREATED_AT = datetime(2026, 1, 1, tzinfo=UTC)


def release_cohort(
    root: Path,
    *,
    version: str = DEFAULT_COHORT_VERSION,
    commit: str = DEFAULT_COHORT_COMMIT,
    build_constraints_sha256: str = DEFAULT_COHORT_BUILD_CONSTRAINTS_SHA256,
    created_at: datetime = DEFAULT_COHORT_CREATED_AT,
) -> LoadedReleaseCohort:
    """Materialise a genuine release cohort with every required artifact kind."""
    root.mkdir()
    artifacts = []
    for index, (name, kind) in enumerate(sorted(REQUIRED_ARTIFACT_KINDS.items())):
        path = root / "artifacts" / f"{name}.bin"
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(f"{index}:{name}\n".encode())
        artifacts.append((name, kind, path))
    manifest = create_manifest(
        root=root,
        version=version,
        source=SourceIdentity(commit=commit, tag=f"v{version}"),
        created_at=created_at,
        builder=BuildIdentity(
            implementation="dev.packaging.release_cohort",
            format_version=1,
            python=platform.python_version(),
            uv="0.11.29",
            platform=platform.system(),
            architecture=platform.machine(),
            build_constraints_sha256=build_constraints_sha256,
        ),
        artifacts=artifacts,
    )
    write_manifest(root, manifest)
    return load_release_cohort(root)
