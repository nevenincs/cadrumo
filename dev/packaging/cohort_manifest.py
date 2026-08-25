"""Define and verify the immutable Cadrumo release-cohort manifest."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Final, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from cadrumo.core.directory_scan import scan_directory

from .._paths import UTF_8
from ._hashing import sha256_path

_UTF_8: Final[str] = UTF_8
_SCHEMA: Final[Literal["cadrumo.release-cohort.v1"]] = "cadrumo.release-cohort.v1"
_MANIFEST_NAME: Final[str] = "release-cohort.json"
_SHA256_PATTERN: Final[str] = r"^[0-9a-f]{64}$"
_COMMIT_PATTERN: Final[str] = r"^[0-9a-f]{40}$"


class ArtifactKind(StrEnum):
    """Closed taxonomy of immutable release-cohort members."""

    PYTHON_WHEEL = "python-wheel"
    PYTHON_SDIST = "python-sdist"
    PYTHON_MANIFEST = "python-manifest"
    PYTHON_SOURCE_ARCHIVE = "python-source-archive"
    PYTHON_WHEELHOUSE = "python-wheelhouse"
    CLAUDE_PLUGIN = "claude-plugin"
    CLAUDE_MARKETPLACE = "claude-marketplace"
    MCPB = "mcpb"
    SCOOP_MANIFEST = "scoop-manifest"
    HOMEBREW_FORMULA = "homebrew-formula"


class SourceIdentity(BaseModel):
    """Exact repository revision from which every cohort member was built."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    commit: str = Field(pattern=_COMMIT_PATTERN)
    tag: str | None = Field(default=None, min_length=2)


class BuildIdentity(BaseModel):
    """Diagnostic identity of the one assembly process."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    implementation: Literal["dev.packaging.release_cohort"]
    format_version: Literal[1]
    python: str = Field(min_length=1)
    uv: str = Field(min_length=1)
    platform: str = Field(min_length=1)
    architecture: str = Field(min_length=1)
    build_constraints_sha256: str = Field(pattern=_SHA256_PATTERN)


class ArtifactRecord(BaseModel):
    """One exact byte sequence carried by the immutable cohort."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    name: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    kind: ArtifactKind
    path: str = Field(min_length=1)
    sha256: str = Field(pattern=_SHA256_PATTERN)
    size: int = Field(gt=0)

    @field_validator("path")
    @classmethod
    def _relative_normal_path(cls, value: str) -> str:
        path = PurePosixPath(value)
        if (
            path.is_absolute()
            or value == "."
            or "\\" in value
            or any(part in {"", ".", ".."} or ":" in part for part in path.parts)
            or path.as_posix() != value
        ):
            raise ValueError("artifact path must be one normalized relative POSIX path")
        return value


class CohortIdentityPayload(BaseModel):
    """Stable inputs whose canonical bytes define the cohort identifier."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_name: Literal["cadrumo.release-cohort.v1"]
    version: str = Field(min_length=1)
    source: SourceIdentity
    artifacts: tuple[ArtifactRecord, ...]


class CohortManifest(BaseModel):
    """Persisted authority for one complete release-candidate cohort."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_name: Literal["cadrumo.release-cohort.v1"]
    cohort_id: str = Field(pattern=_SHA256_PATTERN)
    version: str = Field(min_length=1)
    source: SourceIdentity
    created_at: datetime
    builder: BuildIdentity
    artifacts: tuple[ArtifactRecord, ...]

    @model_validator(mode="after")
    def _complete_and_canonical(self) -> Self:
        names = tuple(record.name for record in self.artifacts)
        paths = tuple(record.path for record in self.artifacts)
        if names != tuple(sorted(names)) or len(names) != len(set(names)):
            raise ValueError("artifact records must have unique names in canonical order")
        if len(paths) != len(set(paths)):
            raise ValueError("artifact records must have unique paths")
        expected = frozenset(REQUIRED_ARTIFACT_KINDS)
        if frozenset(names) != expected:
            raise ValueError(
                f"release cohort is incomplete: expected {sorted(expected)!r}, got {sorted(names)!r}",
            )
        for record in self.artifacts:
            expected_kind = REQUIRED_ARTIFACT_KINDS[record.name]
            if record.kind is not expected_kind:
                raise ValueError(
                    f"artifact {record.name!r} must use kind {expected_kind.value!r}",
                )
        expected_id = cohort_identifier(
            version=self.version,
            source=self.source,
            artifacts=self.artifacts,
        )
        if self.cohort_id != expected_id:
            raise ValueError(
                f"cohort identifier mismatch: expected {expected_id}, got {self.cohort_id}",
            )
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise ValueError("created_at must carry a timezone")
        return self


REQUIRED_ARTIFACT_KINDS: Final[dict[str, ArtifactKind]] = {
    "cadrumo-data-manuals-sdist": ArtifactKind.PYTHON_SDIST,
    "cadrumo-data-manuals-wheel": ArtifactKind.PYTHON_WHEEL,
    "cadrumo-data-official-sdist": ArtifactKind.PYTHON_SDIST,
    "cadrumo-data-official-wheel": ArtifactKind.PYTHON_WHEEL,
    "cadrumo-sdist": ArtifactKind.PYTHON_SDIST,
    "cadrumo-wheel": ArtifactKind.PYTHON_WHEEL,
    "cadrumo-harness-sdist": ArtifactKind.PYTHON_SDIST,
    "cadrumo-harness-wheel": ArtifactKind.PYTHON_WHEEL,
    "cadrumo-source-archive": ArtifactKind.PYTHON_SOURCE_ARCHIVE,
    "cadrumo-runtime-wheelhouse": ArtifactKind.PYTHON_WHEELHOUSE,
    "claude-marketplace": ArtifactKind.CLAUDE_MARKETPLACE,
    "claude-plugin": ArtifactKind.CLAUDE_PLUGIN,
    "homebrew-formula": ArtifactKind.HOMEBREW_FORMULA,
    "mcpb": ArtifactKind.MCPB,
    "python-cohort-manifest": ArtifactKind.PYTHON_MANIFEST,
    "scoop-manifest": ArtifactKind.SCOOP_MANIFEST,
}


@dataclass(frozen=True)
class LoadedReleaseCohort:
    """A validated manifest paired with its immutable on-disk directory."""

    directory: Path
    manifest_path: Path
    manifest: CohortManifest

    def artifact(self, name: str) -> Path:
        """Return the validated path for one named cohort member."""
        record = next((item for item in self.manifest.artifacts if item.name == name), None)
        if record is None:
            raise KeyError(name)
        return (self.directory / PurePosixPath(record.path)).resolve(strict=True)


def cohort_identifier(
    *,
    version: str,
    source: SourceIdentity,
    artifacts: tuple[ArtifactRecord, ...],
) -> str:
    """Hash stable source and artifact identities into one cohort identifier."""
    payload = CohortIdentityPayload(
        schema_name=_SCHEMA,
        version=version,
        source=source,
        artifacts=artifacts,
    )
    canonical = json.dumps(
        payload.model_dump(mode="json"),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode(_UTF_8)
    return hashlib.sha256(canonical).hexdigest()


def artifact_record(
    *,
    root: Path,
    name: str,
    kind: ArtifactKind,
    path: Path,
) -> ArtifactRecord:
    """Create a manifest record after proving the path stays under ``root``."""
    cohort_root = root.resolve(strict=True)
    artifact = path.resolve(strict=True)
    if artifact.parent != cohort_root and cohort_root not in artifact.parents:
        raise ValueError(f"artifact escapes release cohort: {artifact}")
    relative = artifact.relative_to(cohort_root).as_posix()
    return ArtifactRecord(
        name=name,
        kind=kind,
        path=relative,
        sha256=sha256_path(artifact),
        size=artifact.stat().st_size,
    )


def create_manifest(
    *,
    root: Path,
    version: str,
    source: SourceIdentity,
    created_at: datetime,
    builder: BuildIdentity,
    artifacts: Iterable[tuple[str, ArtifactKind, Path]],
) -> CohortManifest:
    """Validate a complete set of artifact bytes and construct its authority."""
    records = tuple(
        sorted(
            (artifact_record(root=root, name=name, kind=kind, path=path) for name, kind, path in artifacts),
            key=lambda item: item.name,
        ),
    )
    return CohortManifest(
        schema_name=_SCHEMA,
        cohort_id=cohort_identifier(version=version, source=source, artifacts=records),
        version=version,
        source=source,
        created_at=created_at,
        builder=builder,
        artifacts=records,
    )


def write_manifest(root: Path, manifest: CohortManifest) -> Path:
    """Persist one validated manifest without replacing an existing authority."""
    cohort_root = root.resolve(strict=True)
    destination = cohort_root / _MANIFEST_NAME
    if destination.exists():
        raise FileExistsError(f"release cohort manifest already exists: {destination}")
    destination.write_text(
        manifest.model_dump_json(indent=2) + "\n",
        encoding=_UTF_8,
        newline="\n",
    )
    return destination


def load_release_cohort(directory: Path) -> LoadedReleaseCohort:
    """Load a complete cohort and reject path, size, or digest drift."""
    root = directory.resolve(strict=True)
    manifest_path = root / _MANIFEST_NAME
    manifest = CohortManifest.model_validate_json(
        manifest_path.read_text(encoding=_UTF_8),
    )
    declared = {record.path for record in manifest.artifacts} | {_MANIFEST_NAME}
    observed = {path.relative_to(root).as_posix() for path in scan_directory(root, recursive=True) if path.is_file()}
    if observed != declared:
        raise SystemExit(
            f"release cohort file inventory drifted: declared={sorted(declared)!r}, observed={sorted(observed)!r}",
        )
    for record in manifest.artifacts:
        artifact = (root / PurePosixPath(record.path)).resolve(strict=True)
        if root not in artifact.parents:
            raise SystemExit(f"cohort artifact escapes its directory: {artifact}")
        if artifact.stat().st_size != record.size:
            raise SystemExit(
                f"cohort artifact size mismatch for {record.name!r}: "
                f"expected {record.size}, got {artifact.stat().st_size}",
            )
        actual = sha256_path(artifact)
        if actual != record.sha256:
            raise SystemExit(
                f"cohort artifact digest mismatch for {record.name!r}: expected {record.sha256}, got {actual}",
            )
    return LoadedReleaseCohort(
        directory=root,
        manifest_path=manifest_path,
        manifest=manifest,
    )


__all__ = [
    "REQUIRED_ARTIFACT_KINDS",
    "ArtifactKind",
    "ArtifactRecord",
    "BuildIdentity",
    "CohortManifest",
    "LoadedReleaseCohort",
    "SourceIdentity",
    "artifact_record",
    "cohort_identifier",
    "create_manifest",
    "load_release_cohort",
    "write_manifest",
]
