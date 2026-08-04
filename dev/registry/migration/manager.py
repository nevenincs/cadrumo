"""Build the deterministic, read-only source contract for registry migration.

The migration application must begin from a pinned source tree and an
explicit inventory of the revisions the current compiler supports. This
module supplies that foundation without reading resolved localization leaves
or writing any registry or migration output. Later migration stages can carry
the immutable records returned here into their own sealed artifacts.

The corpus digest is content-based and machine-independent: sorted POSIX
relative paths, byte counts, and per-file SHA-256 values are length-framed into
one SHA-256 digest. File metadata such as absolute paths and modification times
is intentionally excluded from the digest. The inventory itself is built from
the public registry loader and source descriptors, so it cannot silently drift
from the compiler's supported revision set.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path, PurePosixPath
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from cadrumo.core.hashing import hash_file, sha256_hex
from cadrumo.domain.calculations.registry import (
    ModeloRevisionSource,
    ModeloSource,
    discover_modelo_sources,
    load_registry_tree,
)

_CORPUS_FINGERPRINT_SCHEMA: Final[str] = "cadrumo.modelo-localization-cascade.corpus-fingerprint.v1"
_SOURCE_INVENTORY_SCHEMA: Final[str] = "cadrumo.modelo-localization-cascade.source-inventory.v1"
_CORPUS_SCOPE: Final[str] = "registry/aeat/**/*.toml"
_SHA256_PATTERN: Final[str] = r"^[0-9a-f]{64}$"

ModeloSourceLayout = Literal["single_file", "directory"]
RevisionSourceLayout = Literal["inline", "revision_file", "fragment_directory"]


class MigrationInventoryError(ValueError):
    """Raised when the migration source tree cannot be pinned consistently."""


class _StrictRecord(BaseModel):
    """Base configuration for immutable, persisted migration evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class CorpusFileFingerprint(_StrictRecord):
    """Content identity for one TOML file under the registry source root."""

    relative_path: str = Field(min_length=1)
    byte_count: int = Field(ge=0)
    sha256: str = Field(pattern=_SHA256_PATTERN)

    @field_validator("relative_path")
    @classmethod
    def _validate_relative_path(cls, value: str) -> str:
        """Require one canonical, machine-independent POSIX relative path."""
        parsed = PurePosixPath(value)
        if (
            parsed.is_absolute()
            or value != parsed.as_posix()
            or "\\" in value
            or ":" in value
            or any(part in {"", ".", ".."} for part in parsed.parts)
        ):
            raise ValueError(f"relative_path must be a canonical POSIX relative path, got {value!r}")
        return value


class CorpusFingerprint(_StrictRecord):
    """Deterministic content fingerprint and auditable file census."""

    schema_id: str = _CORPUS_FINGERPRINT_SCHEMA
    algorithm: Literal["sha256"] = "sha256"
    scope: str = _CORPUS_SCOPE
    file_count: int = Field(ge=0)
    byte_count: int = Field(ge=0)
    locale_file_count: int = Field(ge=0)
    sha256: str = Field(pattern=_SHA256_PATTERN)
    files: tuple[CorpusFileFingerprint, ...]

    @model_validator(mode="after")
    def _validate_derived_values(self) -> CorpusFingerprint:
        """Reject reordered, duplicated, or tampered file-census values."""
        if self.schema_id != _CORPUS_FINGERPRINT_SCHEMA:
            raise ValueError(f"unsupported corpus fingerprint schema {self.schema_id!r}")
        if self.scope != _CORPUS_SCOPE:
            raise ValueError(f"unsupported corpus fingerprint scope {self.scope!r}")
        paths = tuple(item.relative_path for item in self.files)
        if paths != tuple(sorted(paths)) or len(paths) != len(set(paths)):
            raise ValueError("corpus file fingerprints must be unique and sorted by relative_path")
        if self.file_count != len(self.files):
            raise ValueError(f"file_count={self.file_count} does not match {len(self.files)} file records")
        if self.byte_count != sum(item.byte_count for item in self.files):
            raise ValueError("byte_count does not match the file records")
        expected_locale_count = sum("locales" in PurePosixPath(path).parts for path in paths)
        if self.locale_file_count != expected_locale_count:
            raise ValueError("locale_file_count does not match the file records")
        expected_digest = _digest_file_records(self.files)
        if self.sha256 != expected_digest:
            raise ValueError("sha256 does not match the canonical file records")
        return self


class RevisionInventoryEntry(_StrictRecord):
    """One supported revision and the compiler source paths that define it."""

    modelo_id: str = Field(min_length=1)
    revision_id: str = Field(min_length=1)
    modelo_source_layout: ModeloSourceLayout
    modelo_source_path: str = Field(min_length=1)
    revision_source_layout: RevisionSourceLayout
    revision_source_paths: tuple[str, ...] = Field(min_length=1)

    @field_validator("modelo_id", "revision_id")
    @classmethod
    def _validate_identifier(cls, value: str) -> str:
        """Reject empty or whitespace-only source identities."""
        if not value.strip():
            raise ValueError("source identities must not be blank")
        return value

    @field_validator("modelo_source_path", mode="after")
    @classmethod
    def _validate_modelo_source_path(cls, value: str) -> str:
        """Validate the model source path with the same canonical path rules."""
        return _validate_relative_path(value)

    @field_validator("revision_source_paths", mode="after")
    @classmethod
    def _validate_revision_source_paths(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        """Validate, sort, and deduplicate revision source paths."""
        paths = tuple(_validate_relative_path(item) for item in value)
        if paths != tuple(sorted(paths)) or len(paths) != len(set(paths)):
            raise ValueError("revision_source_paths must be unique and sorted by relative_path")
        return paths


class MigrationSourceInventory(_StrictRecord):
    """Pinned corpus plus the complete supported ``modelo/revision`` index."""

    schema_id: str = _SOURCE_INVENTORY_SCHEMA
    corpus_fingerprint: CorpusFingerprint
    modelo_ids: tuple[str, ...]
    supported_revisions: tuple[RevisionInventoryEntry, ...]
    modelo_count: int = Field(ge=0)
    revision_count: int = Field(ge=0)

    @model_validator(mode="after")
    def _validate_inventory(self) -> MigrationSourceInventory:
        """Reject incomplete, duplicated, or non-deterministically ordered inventory rows."""
        if self.schema_id != _SOURCE_INVENTORY_SCHEMA:
            raise ValueError(f"unsupported source inventory schema {self.schema_id!r}")
        if self.modelo_ids != tuple(sorted(self.modelo_ids)) or len(self.modelo_ids) != len(set(self.modelo_ids)):
            raise ValueError("modelo_ids must be unique and sorted")
        revision_keys = tuple((item.modelo_id, item.revision_id) for item in self.supported_revisions)
        if revision_keys != tuple(sorted(revision_keys)) or len(revision_keys) != len(set(revision_keys)):
            raise ValueError("supported_revisions must be unique and sorted by modelo/revision")
        if self.modelo_count != len(self.modelo_ids):
            raise ValueError("modelo_count does not match modelo_ids")
        if self.revision_count != len(self.supported_revisions):
            raise ValueError("revision_count does not match supported_revisions")
        if {item.modelo_id for item in self.supported_revisions} != set(self.modelo_ids):
            raise ValueError("every modelo_id must own at least one supported revision")
        return self


def _validate_relative_path(value: str) -> str:
    """Return ``value`` when it is a canonical POSIX relative path."""
    parsed = PurePosixPath(value)
    if (
        not value
        or parsed.is_absolute()
        or value != parsed.as_posix()
        or "\\" in value
        or ":" in value
        or any(part in {"", ".", ".."} for part in parsed.parts)
    ):
        raise ValueError(f"path must be a canonical POSIX relative path, got {value!r}")
    return value


def _digest_frame(value: str) -> bytes:
    """Length-frame one UTF-8 value for collision-resistant aggregation."""
    encoded = value.encode("utf-8")
    return len(encoded).to_bytes(8, byteorder="big") + encoded


def _digest_file_records(records: Iterable[CorpusFileFingerprint]) -> str:
    """Hash the schema marker and sorted file records into one stable digest."""
    framed = bytearray(_digest_frame(_CORPUS_FINGERPRINT_SCHEMA))
    for record in records:
        framed.extend(_digest_frame(record.relative_path))
        framed.extend(_digest_frame(str(record.byte_count)))
        framed.extend(_digest_frame(record.sha256))
    return sha256_hex(bytes(framed))


def _resolved_directory(root: Path) -> Path:
    """Resolve and validate a read-only source directory."""
    resolved = root.expanduser().resolve()
    if not resolved.is_dir():
        raise MigrationInventoryError(f"registry source root is not a directory: {resolved}")
    return resolved


def _relative_source_path(root: Path, path: Path) -> str:
    """Return one source path relative to ``root`` or raise a scoped error."""
    try:
        relative = path.resolve().relative_to(root)
    except (OSError, ValueError) as exc:
        raise MigrationInventoryError(f"source path {path} is outside registry root {root}") from exc
    return _validate_relative_path(relative.as_posix())


def fingerprint_registry_corpus(root: Path) -> CorpusFingerprint:
    """Fingerprint every TOML source file under a registry root.

    The function is read-only. Its result contains the per-file hashes needed
    to explain a later source-drift refusal as well as the aggregate digest
    used to bind subsequent migration stages to this exact tree.

    Args:
        root: Registry root containing the ``modelos`` source directory.

    Returns:
        A strict, immutable :class:`CorpusFingerprint`.

    Raises:
        MigrationInventoryError: If the root cannot be walked or a file cannot
            be read and hashed.
    """
    resolved = _resolved_directory(root)
    records: list[CorpusFileFingerprint] = []
    try:
        paths = sorted(
            (path for path in resolved.rglob("*.toml") if path.is_file()),
            key=lambda path: path.relative_to(resolved).as_posix(),
        )
    except OSError as exc:
        raise MigrationInventoryError(f"could not enumerate TOML sources below {resolved}: {exc}") from exc
    for path in paths:
        try:
            digest, byte_count = hash_file(path)
        except OSError as exc:
            raise MigrationInventoryError(f"could not hash registry source {path}: {exc}") from exc
        records.append(
            CorpusFileFingerprint(
                relative_path=_relative_source_path(resolved, path),
                byte_count=byte_count,
                sha256=digest,
            ),
        )
    frozen_records = tuple(records)
    return CorpusFingerprint(
        file_count=len(frozen_records),
        byte_count=sum(record.byte_count for record in frozen_records),
        locale_file_count=sum("locales" in PurePosixPath(record.relative_path).parts for record in frozen_records),
        sha256=_digest_file_records(frozen_records),
        files=frozen_records,
    )


def _source_index(sources: tuple[ModeloSource, ...]) -> dict[str, ModeloSource]:
    """Index loader-discovered modelo sources and reject an ambiguous identity."""
    indexed: dict[str, ModeloSource] = {}
    for source in sources:
        if source.modelo_id in indexed:
            raise MigrationInventoryError(f"modelo source {source.modelo_id!r} was discovered more than once")
        indexed[source.modelo_id] = source
    return indexed


def _revision_source_index(source: ModeloSource) -> dict[str, ModeloRevisionSource]:
    """Index one directory-mode source's revision descriptors."""
    indexed: dict[str, ModeloRevisionSource] = {}
    for revision_source in source.revision_sources:
        if revision_source.revision_id in indexed:
            raise MigrationInventoryError(
                f"modelo {source.modelo_id!r} revision {revision_source.revision_id!r} was discovered more than once",
            )
        indexed[revision_source.revision_id] = revision_source
    return indexed


def _revision_entry(
    root: Path,
    source: ModeloSource,
    revision_id: str,
    revision_sources: dict[str, ModeloRevisionSource],
) -> RevisionInventoryEntry:
    """Build one auditable revision row from the loader's source descriptors."""
    modelo_source_path = _relative_source_path(root, source.manifest_path)
    if source.layout == "single_file":
        return RevisionInventoryEntry(
            modelo_id=source.modelo_id,
            revision_id=revision_id,
            modelo_source_layout="single_file",
            modelo_source_path=modelo_source_path,
            revision_source_layout="inline",
            revision_source_paths=(modelo_source_path,),
        )

    revision_source = revision_sources.get(revision_id)
    if revision_source is None:
        raise MigrationInventoryError(
            f"modelo {source.modelo_id!r} revision {revision_id!r} has no discovered source descriptor",
        )
    fragment_paths = tuple(sorted({_relative_source_path(root, path) for path in revision_source.fragment_paths}))
    if not fragment_paths:
        raise MigrationInventoryError(
            f"modelo {source.modelo_id!r} revision {revision_id!r} has no schema source fragments",
        )
    return RevisionInventoryEntry(
        modelo_id=source.modelo_id,
        revision_id=revision_id,
        modelo_source_layout="directory",
        modelo_source_path=modelo_source_path,
        revision_source_layout=revision_source.layout,
        revision_source_paths=fragment_paths,
    )


def build_source_inventory(root: Path) -> MigrationSourceInventory:
    """Load the current registry and return its pinned revision inventory.

    The source fingerprint is captured before and after the canonical loader
    and source-descriptor pass. If the tree changes while it is being read,
    the function refuses to return a mixed snapshot; callers must retry after
    concurrent edits settle. No method in this module writes to ``root``.

    Args:
        root: Registry root containing ``modelos`` and the shared catalogues.

    Returns:
        An immutable :class:`MigrationSourceInventory` with sorted identities
        and source evidence.

    Raises:
        MigrationInventoryError: If the source tree is malformed, changes
            during the read, or cannot be reconciled with loader descriptors.
    """
    resolved = _resolved_directory(root)
    modelos_dir = resolved / "modelos"
    if not modelos_dir.is_dir():
        raise MigrationInventoryError(f"registry source root has no modelos directory: {resolved}")

    before = fingerprint_registry_corpus(resolved)
    try:
        modelos, _catalogues = load_registry_tree(resolved)
        sources = discover_modelo_sources(modelos_dir)
    except Exception as exc:
        raise MigrationInventoryError(f"could not load the registry source contract at {resolved}: {exc}") from exc
    after = fingerprint_registry_corpus(resolved)
    if before != after:
        raise MigrationInventoryError(
            f"registry source changed while inventory was built at {resolved}; retry after concurrent writes settle",
        )

    sources_by_id = _source_index(sources)
    modelos_by_id = {str(modelo.id): modelo for modelo in modelos}
    if set(modelos_by_id) != set(sources_by_id):
        raise MigrationInventoryError(
            "loader and source discovery disagree on modelo ids: "
            f"loader={sorted(modelos_by_id)!r} sources={sorted(sources_by_id)!r}",
        )

    rows: list[RevisionInventoryEntry] = []
    for modelo_id in sorted(modelos_by_id):
        modelo = modelos_by_id[modelo_id]
        source = sources_by_id[modelo_id]
        revision_sources = _revision_source_index(source)
        revision_ids = tuple(sorted(str(revision_id) for revision_id in modelo.revisions))
        if source.layout == "directory" and set(revision_ids) != set(revision_sources):
            raise MigrationInventoryError(
                f"modelo {modelo_id!r} loader/source revision mismatch: "
                f"loader={list(revision_ids)!r} sources={sorted(revision_sources)!r}",
            )
        rows.extend(_revision_entry(resolved, source, revision_id, revision_sources) for revision_id in revision_ids)

    modelo_ids = tuple(sorted(modelos_by_id))
    revisions = tuple(rows)
    return MigrationSourceInventory(
        corpus_fingerprint=after,
        modelo_ids=modelo_ids,
        supported_revisions=revisions,
        modelo_count=len(modelo_ids),
        revision_count=len(revisions),
    )


__all__ = [
    "CorpusFileFingerprint",
    "CorpusFingerprint",
    "MigrationInventoryError",
    "MigrationSourceInventory",
    "RevisionInventoryEntry",
    "build_source_inventory",
    "fingerprint_registry_corpus",
]
