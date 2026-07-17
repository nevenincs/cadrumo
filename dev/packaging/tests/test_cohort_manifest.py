"""Real-file tests for the immutable release-cohort authority."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from dev.packaging.cohort_manifest import (
    REQUIRED_ARTIFACT_KINDS,
    ArtifactKind,
    BuildIdentity,
    SourceIdentity,
    create_manifest,
    load_release_cohort,
    write_manifest,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _build_identity(*, python: str = "3.13.11") -> BuildIdentity:
    return BuildIdentity(
        implementation="dev.packaging.release_cohort",
        format_version=1,
        python=python,
        uv="uv 0.8.0",
        platform="Windows",
        architecture="AMD64",
        build_constraints_sha256="d" * 64,
    )


def _artifact_files(root: Path) -> tuple[tuple[str, ArtifactKind, Path], ...]:
    artifacts = root / "artifacts"
    artifacts.mkdir()
    rows: list[tuple[str, ArtifactKind, Path]] = []
    for name, kind in REQUIRED_ARTIFACT_KINDS.items():
        path = artifacts / f"{name}.bin"
        path.write_bytes(f"real retained bytes for {name}\n".encode())
        rows.append((name, kind, path))
    return tuple(rows)


def test_manifest_roundtrip_binds_every_file_and_stable_identity(tmp_path: Path) -> None:
    """Build diagnostics and creation time do not change the byte-cohort identity."""
    rows = _artifact_files(tmp_path)
    source = SourceIdentity(commit="a" * 40, tag="v0.2.1")
    created = datetime(2026, 7, 17, 4, 0, tzinfo=UTC)
    first = create_manifest(
        root=tmp_path,
        version="0.2.1",
        source=source,
        created_at=created,
        builder=_build_identity(),
        artifacts=rows,
    )
    second = create_manifest(
        root=tmp_path,
        version="0.2.1",
        source=source,
        created_at=created + timedelta(hours=1),
        builder=_build_identity(python="3.13.12"),
        artifacts=reversed(rows),
    )

    assert first.cohort_id == second.cohort_id
    manifest_path = write_manifest(tmp_path, first)
    loaded = load_release_cohort(tmp_path)
    assert loaded.manifest_path == manifest_path
    assert loaded.manifest == first
    assert loaded.artifact("mcpb").read_bytes() == b"real retained bytes for mcpb\n"


def test_manifest_rejects_changed_or_undeclared_bytes(tmp_path: Path) -> None:
    """Neither mutation nor unrecorded material can enter a frozen cohort."""
    rows = _artifact_files(tmp_path)
    manifest = create_manifest(
        root=tmp_path,
        version="0.2.1",
        source=SourceIdentity(commit="b" * 40),
        created_at=datetime.now(UTC),
        builder=_build_identity(),
        artifacts=rows,
    )
    write_manifest(tmp_path, manifest)
    changed = next(path for name, _kind, path in rows if name == "claude-plugin")
    original = changed.read_bytes()
    changed.write_bytes(b"X" * len(original))
    with pytest.raises(SystemExit, match="digest mismatch"):
        load_release_cohort(tmp_path)

    changed.write_bytes(original)
    (tmp_path / "undeclared.bin").write_bytes(b"not in authority")
    with pytest.raises(SystemExit, match="file inventory drifted"):
        load_release_cohort(tmp_path)


def test_manifest_rejects_an_incomplete_artifact_set(tmp_path: Path) -> None:
    """A valid subset cannot masquerade as a complete release cohort."""
    rows = _artifact_files(tmp_path)
    with pytest.raises(ValidationError, match="release cohort is incomplete"):
        create_manifest(
            root=tmp_path,
            version="0.2.1",
            source=SourceIdentity(commit="c" * 40),
            created_at=datetime.now(UTC),
            builder=_build_identity(),
            artifacts=rows[:-1],
        )
