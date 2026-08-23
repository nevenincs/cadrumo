"""Shared genuine release-cohort fixture builder.

Underscore-prefixed so it is never collected as a test module. Lives under
``dev/packaging/tests/`` because :mod:`dev.packaging.cohort_manifest` is this
concept's owning module; ``dev/release/tests`` already imports production
cohort/evidence code across that same package boundary
(``dev/release/tests/test_distribution_readiness.py``), so a cross-package
test-helper import here follows an established precedent (see also
``src/cadrumo/tests/test_regulatory_cap_term_dominance.py`` importing
``..domain.tests._regulatory_cap_witnesses``).

Consolidates four near-identical release-cohort builders (three in
``dev/packaging/tests`` -- test_evidence.py, test_distribution_evidence_emit.py,
test_evidence_scrub.py -- plus ``dev/release/tests/test_distribution_readiness.py``'s
``_cohort``) that all built the same real on-disk cohort: every
:data:`~dev.packaging.cohort_manifest.REQUIRED_ARTIFACT_KINDS` artifact, a real
manifest, a real ``load_release_cohort`` read-back. They differed only in
filler identity values (version, commit, digest bytes) that no caller asserts
against -- confirmed by grepping each file for a second reference to its own
filler before folding it into one shared default -- plus one non-deterministic
``datetime.now(UTC)`` timestamp two of the four copies already pinned, and one
genuinely meaningful parameter: the release/readiness cohort builder accepts a
``payload_suffix`` so a test can construct two cohorts sharing a commit but
carrying different artifact bytes (and so different digests), which its
mismatched-evidence gate exercises. That parameter is the strictest variant of
the four and is kept; the shared default keeps the artifact bytes unchanged
for every caller that never varies it.
"""

from __future__ import annotations

import importlib.metadata
import platform
import zipfile
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
    payload_suffix: str = "",
) -> LoadedReleaseCohort:
    """Materialise a genuine release cohort with every required artifact kind.

    ``payload_suffix`` varies each artifact's bytes without touching commit or
    version identity, so two cohorts can share one commit/version yet carry
    different digests -- the shape the digest-mismatch readiness gate needs.
    """
    root.mkdir(parents=True)
    artifacts = []
    for index, (name, kind) in enumerate(sorted(REQUIRED_ARTIFACT_KINDS.items())):
        path = root / "artifacts" / f"{name}.bin"
        path.parent.mkdir(exist_ok=True)
        if name == "cadrumo-wheel":
            distribution = importlib.metadata.distribution("cadrumo")
            with zipfile.ZipFile(path, "w") as archive:
                for item in distribution.files or ():
                    if item.name in {"INSTALLER", "RECORD", "direct_url.json", "REQUESTED"}:
                        continue
                    if item.as_posix().endswith(".pyc") or "/__pycache__/" in item.as_posix():
                        continue
                    source = distribution.locate_file(item)
                    if source.is_file():
                        archive.write(source, item.as_posix())
                if payload_suffix:
                    archive.writestr("cadrumo/_foreign_cohort_plant.py", payload_suffix)
        else:
            path.write_bytes(f"{index}:{name}:{payload_suffix}\n".encode())
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
