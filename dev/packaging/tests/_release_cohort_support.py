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

import functools
import platform
import shutil
import subprocess
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from ..._paths import REPO_ROOT
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


@functools.lru_cache(maxsize=1)
def _real_product_wheel() -> Path:
    """Build the product wheel once; never counterfeit it from installed files.

    One wheel, because the harness ships inside it. A second build against a
    separate harness project is what this fixture used to do, and there is no
    such project to build.
    """
    output = Path(tempfile.mkdtemp(prefix="cadrumo-real-cohort-wheels-"))
    uv = shutil.which("uv")
    if uv is None:
        msg = "uv executable not found on PATH"
        raise RuntimeError(msg)
    completed = subprocess.run(  # noqa: S603 - fixed uv build argv over repository-owned paths.
        [uv, "build", "--wheel", "--out-dir", str(output)],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"real wheel fixture build failed: {completed.stderr}")
    candidates = tuple(output.glob("cadrumo-*.whl"))
    if len(candidates) != 1:
        raise RuntimeError(f"real wheel fixture expected one cadrumo-*.whl: {candidates!r}")
    return candidates[0]


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
            shutil.copy2(_real_product_wheel(), path)
            if payload_suffix:
                with zipfile.ZipFile(path, "a") as archive:
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
