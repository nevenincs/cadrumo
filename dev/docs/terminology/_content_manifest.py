"""Deterministic raw-byte manifests for the build-time Rung-2 evidence.

The manifest records exactly which local files were reviewed for one provider,
model, or tokenizer role.  It is deliberately independent of Model2Vec and
does not discover, download, or interpret model files.  Callers provide the
explicit relative paths approved for the pinned revision.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from hashlib import sha256
from pathlib import Path, PurePosixPath
from typing import Annotated, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from ._jcs import CanonicalJsonError, canonical_json_bytes

__all__ = [
    "RAW_BYTE_MANIFEST_SCHEMA_VERSION",
    "RawByteManifest",
    "RawByteManifestEntry",
    "RawByteManifestError",
    "build_raw_byte_manifest",
    "verify_raw_byte_manifest",
]

RAW_BYTE_MANIFEST_SCHEMA_VERSION: Final[int] = 1
_SHA256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
_REVISION = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{40}$")]
_ROLE = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]
_REPOSITORY = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=256)]
_RELATIVE_PATH = Annotated[str, StringConstraints(min_length=1, max_length=4096)]
_DRIVE_PREFIX = re.compile(r"^[A-Za-z]:")


class RawByteManifestError(ValueError):
    """Raised when local evidence cannot satisfy a raw-byte manifest."""


class RawByteManifestEntry(BaseModel):
    """One exact file covered by a raw-byte manifest."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    relative_path: _RELATIVE_PATH
    byte_length: int = Field(ge=0)
    sha256: _SHA256

    @field_validator("relative_path")
    @classmethod
    def _require_posix_relative_path(cls, value: str) -> str:
        return _normalise_relative_path(value)


class RawByteManifest(BaseModel):
    """Self-attesting, role-scoped manifest over explicitly reviewed bytes."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    schema_version: Literal[1]
    role: _ROLE
    repository: _REPOSITORY
    revision: _REVISION
    entries: tuple[RawByteManifestEntry, ...] = Field(min_length=1)
    manifest_sha256: _SHA256

    @model_validator(mode="after")
    def _validate_manifest(self) -> RawByteManifest:
        paths = tuple(entry.relative_path for entry in self.entries)
        if paths != tuple(sorted(paths, key=lambda path: path.encode("utf-8"))):
            raise ValueError("raw-byte manifest entries must be sorted by UTF-8 path bytes")
        _require_unique_paths(paths)
        expected = _manifest_sha256(
            schema_version=self.schema_version,
            role=self.role,
            repository=self.repository,
            revision=self.revision,
            entries=self.entries,
        )
        if self.manifest_sha256 != expected:
            raise ValueError("raw-byte manifest root hash does not match its entries")
        return self

    def canonical_bytes(self) -> bytes:
        """Return canonical bytes for the complete manifest envelope."""
        return _canonical_json_bytes(self.model_dump(mode="json"))


def build_raw_byte_manifest(
    root: Path,
    *,
    role: str,
    repository: str,
    revision: str,
    relative_paths: Iterable[str],
) -> RawByteManifest:
    """Build a manifest from an explicit, reviewed list of local files.

    The function never walks for discovery: the caller must name every file.
    This keeps the tokenizer/model layout outside this generic contract and
    makes an omitted or unexpected file visible at verification time.
    """
    root_dir = _require_local_directory(root)
    normalised_paths = tuple(_normalise_relative_path(path) for path in relative_paths)
    _require_unique_paths(normalised_paths)
    entries: list[RawByteManifestEntry] = []
    for relative_path in normalised_paths:
        path = _local_path(root_dir, relative_path)
        byte_length, digest = _hash_regular_file(path)
        entries.append(
            RawByteManifestEntry(
                relative_path=relative_path,
                byte_length=byte_length,
                sha256=digest,
            ),
        )
    entries.sort(key=lambda entry: entry.relative_path.encode("utf-8"))
    manifest_sha256 = _manifest_sha256(
        schema_version=RAW_BYTE_MANIFEST_SCHEMA_VERSION,
        role=role,
        repository=repository,
        revision=revision,
        entries=tuple(entries),
    )
    return RawByteManifest(
        schema_version=RAW_BYTE_MANIFEST_SCHEMA_VERSION,
        role=role,
        repository=repository,
        revision=revision,
        entries=tuple(entries),
        manifest_sha256=manifest_sha256,
    )


def verify_raw_byte_manifest(
    root: Path,
    manifest: RawByteManifest,
    *,
    reject_unexpected: bool = True,
) -> None:
    """Verify manifest entries and, by default, reject unlisted local files.

    A complete model/provider snapshot must use the default strict mode.  A
    reviewed role manifest can set ``reject_unexpected=False`` when it is a
    deliberate projection over a root whose complete file set is covered by a
    separate strict snapshot manifest; missing, changed, and linked entries
    remain failures in either mode.
    """
    root_dir = _require_local_directory(root)
    validated = RawByteManifest.model_validate(manifest)
    expected = {entry.relative_path: entry for entry in validated.entries}
    seen: dict[str, Path] = {}
    for path in _walk_local_tree(root_dir):
        relative_path = _normalise_relative_path(path.relative_to(root_dir).as_posix())
        folded = relative_path.casefold()
        previous = seen.get(folded)
        if previous is not None and previous.as_posix() != path.as_posix():
            raise RawByteManifestError(f"case-colliding local files are not admissible: {previous} and {path}")
        seen[folded] = path
        if reject_unexpected and relative_path not in expected:
            raise RawByteManifestError(f"unexpected local file is outside the manifest: {relative_path!r}")
        byte_length, digest = _hash_regular_file(path)
        if relative_path not in expected:
            continue
        entry = expected[relative_path]
        if byte_length != entry.byte_length or digest != entry.sha256:
            raise RawByteManifestError(f"local file bytes do not match the manifest: {relative_path!r}")

    missing = sorted(set(expected) - {path.relative_to(root_dir).as_posix() for path in seen.values()})
    if missing:
        raise RawByteManifestError(f"manifest files are missing locally: {missing!r}")


def _manifest_sha256(
    *,
    schema_version: int,
    role: str,
    repository: str,
    revision: str,
    entries: tuple[RawByteManifestEntry, ...],
) -> str:
    payload = {
        "entries": [
            {
                "byte_length": entry.byte_length,
                "relative_path": entry.relative_path,
                "sha256": entry.sha256,
            }
            for entry in entries
        ],
        "repository": repository,
        "revision": revision,
        "role": role,
        "schema_version": schema_version,
    }
    return sha256(_canonical_json_bytes(payload)).hexdigest()


def _canonical_json_bytes(payload: object) -> bytes:
    """Return the shared Rung-2 canonical bytes for manifest hashing."""
    try:
        return canonical_json_bytes(payload)
    except CanonicalJsonError as exc:
        raise RawByteManifestError("raw-byte manifest payload is not canonical JSON") from exc


def _normalise_relative_path(value: str) -> str:
    if not value or "\\" in value or "\x00" in value or _DRIVE_PREFIX.match(value):
        raise ValueError(f"manifest path must use non-empty POSIX-relative spelling: {value!r}")
    pure = PurePosixPath(value)
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        raise ValueError(f"manifest path must be non-escaping and normalized: {value!r}")
    normalized = pure.as_posix()
    if normalized != value:
        raise ValueError(f"manifest path must be normalized POSIX spelling: {value!r}")
    return value


def _require_unique_paths(paths: Iterable[str]) -> None:
    seen: dict[str, str] = {}
    for path in paths:
        folded = path.casefold()
        previous = seen.get(folded)
        if previous is not None:
            if previous == path:
                raise ValueError(f"duplicate manifest path: {path!r}")
            raise ValueError(f"case-colliding manifest paths: {previous!r} and {path!r}")
        seen[folded] = path


def _require_local_directory(root: Path) -> Path:
    if root.is_symlink() or not root.is_dir():
        raise RawByteManifestError(f"manifest root must be a local directory: {root}")
    return root


def _local_path(root: Path, relative_path: str) -> Path:
    path = root.joinpath(*PurePosixPath(relative_path).parts)
    current = root
    for part in PurePosixPath(relative_path).parts:
        current /= part
        if current.is_symlink():
            raise RawByteManifestError(f"manifest path contains a symlink: {relative_path!r}")
    return path


def _hash_regular_file(path: Path) -> tuple[int, str]:
    if path.is_symlink() or not path.is_file():
        raise RawByteManifestError(f"manifest entry is not a regular local file: {path}")
    digest = sha256()
    byte_length = 0
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                byte_length += len(chunk)
                digest.update(chunk)
    except OSError as exc:
        raise RawByteManifestError(f"cannot read manifest file: {path}") from exc
    return byte_length, digest.hexdigest()


def _walk_local_tree(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*"), key=lambda candidate: candidate.relative_to(root).as_posix().encode("utf-8")):
        if path.is_symlink():
            raise RawByteManifestError(f"symlinks are not admissible in manifest roots: {path}")
        if path.is_file():
            yield path
