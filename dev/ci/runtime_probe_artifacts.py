"""Prepare source or sealed artifact inputs for one compatibility mode."""

from __future__ import annotations

from pathlib import Path

from cadrumo.core.product_identity import PRODUCT_IDENTITY
from dev.packaging.evidence import artifact_map_digest
from dev.packaging.hashing import sha256_path
from dev.packaging.lane_verification_core import (
    build_companion_wheels,
    build_root_snapshot,
    build_sdist,
    require_executable,
)
from dev.packaging.python_cohort import PythonCohort, load_python_cohort
from dev.source_tree import content_digest, repository_files

from .runtime_probe_contracts import CompatibilityProbeError
from .runtime_probe_identity import _builder_pin, _cohort_lock_digest, _read_lock_digest


def _cohort_digests(cohort: PythonCohort) -> dict[str, str]:
    """Return the sealed digest of each distribution the cohort publishes."""
    return {name: cohort.sha256[name] for name in PRODUCT_IDENTITY.cohort_distributions}


def _load_binary_artifacts(
    cohort_dir: Path,
    *,
    repo_root: Path,
) -> tuple[PythonCohort, tuple[tuple[str, Path], ...], str, str, str | None]:
    """Load an existing Python cohort and return its exact install artifacts."""
    resolved = cohort_dir.resolve(strict=True)
    # The compatibility workflow normally receives the extracted Python cohort;
    # accepting a full release-cohort root is useful for local invocation and
    # lets us validate the wrapper's exact builder identity when it is present.
    python_dir = resolved / "python" if (resolved / "python" / "python-cohort.json").is_file() else resolved
    cohort = load_python_cohort(python_dir)
    lock_sha256 = _cohort_lock_digest(cohort)
    builder_python: str | None = None
    release_manifest = resolved / "release-cohort.json"
    if release_manifest.is_file():
        from dev.packaging.cohort_manifest import load_release_cohort

        release = load_release_cohort(resolved)
        builder_python = release.manifest.builder.python
        expected = _builder_pin(repo_root)
        if builder_python != expected:
            raise CompatibilityProbeError(
                f"sealed release cohort builder drifted: expected {expected!r}, got {builder_python!r}",
                category="builder-identity-mismatch",
            )
    artifacts = tuple(
        zip(
            PRODUCT_IDENTITY.cohort_distributions,
            (cohort.root_wheel, cohort.manuals_wheel, cohort.official_wheel),
            strict=True,
        )
    )
    return cohort, artifacts, lock_sha256, artifact_map_digest(_cohort_digests(cohort)), builder_python


def _source_artifacts(
    repo_root: Path,
    work_dir: Path,
) -> tuple[tuple[tuple[str, Path], ...], str, dict[str, str], str | None]:
    """Build source artifacts from one isolated tree snapshot and hash them."""
    build_root = build_root_snapshot(repo_root, work_dir / "source-snapshot")
    sdist = build_sdist(work_dir, require_executable("uv"), build_root=build_root)
    manuals, official = build_companion_wheels(work_dir, require_executable("uv"), build_root=build_root)
    artifacts = tuple(zip(PRODUCT_IDENTITY.cohort_distributions, (sdist, manuals, official), strict=True))
    digests = {name: sha256_path(path) for name, path in artifacts}
    # The snapshot is a private, per-probe copy nobody else writes to, so its
    # content digest names exactly the bytes the builders above consumed.
    source_digest = content_digest(build_root, repository_files(build_root))
    return artifacts, _read_lock_digest(build_root / "uv.lock"), digests, source_digest
