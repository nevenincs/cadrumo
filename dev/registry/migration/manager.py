"""Build deterministic, read-only source contracts for registry migration.

The migration application must begin from a pinned source tree, an explicit
inventory of the revisions the current compiler supports, and the complete
resolved localization matrix produced by that compiler. This module supplies
those foundations without writing any registry or migration output. Later
migration stages can carry the immutable records returned here into their own
sealed artifacts.

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

from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.hashing import hash_file, sha256_hex
from cadrumo.domain.calculations.registry import (
    CasillaDefinition,
    ModeloDefinition,
    ModeloRevisionSource,
    ModeloSource,
    discover_modelo_sources,
    load_registry_tree,
)

_CORPUS_FINGERPRINT_SCHEMA: Final[str] = "cadrumo.modelo-localization-cascade.corpus-fingerprint.v1"
_SOURCE_INVENTORY_SCHEMA: Final[str] = "cadrumo.modelo-localization-cascade.source-inventory.v1"
_RESOLVED_MATRIX_SCHEMA: Final[str] = "cadrumo.modelo-localization-cascade.resolved-matrix.v1"
_CANONICAL_CANDIDATE_SCHEMA: Final[str] = "cadrumo.modelo-localization-cascade.canonical-candidate.v1"
_CANONICAL_CANDIDATES_SCHEMA: Final[str] = "cadrumo.modelo-localization-cascade.canonical-candidates.v1"
_CORPUS_SCOPE: Final[str] = "registry/aeat/**/*.toml"
_SHA256_PATTERN: Final[str] = r"^[0-9a-f]{64}$"

ModeloSourceLayout = Literal["single_file", "directory"]
RevisionSourceLayout = Literal["inline", "revision_file", "fragment_directory"]
LocalizationField = Literal["label", "help"]
LocalizationResolution = Literal["localized", "official_spanish", "absent"]
CanonicalOccurrenceScope = Literal["continuity", "revision_occurrence"]

_SUPPORTED_LOCALES: Final[tuple[str, ...]] = tuple(language.value for language in OutputLanguage)
_LOCALIZATION_FIELDS: Final[tuple[LocalizationField, ...]] = ("label", "help")


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


class ResolvedLocalizationEntry(_StrictRecord):
    """One resolved locale/field value for one supported casilla occurrence."""

    modelo_id: str = Field(min_length=1)
    revision_id: str = Field(min_length=1)
    casilla_id: str = Field(min_length=1)
    continuidad_id: str | None = Field(default=None, min_length=1)
    locale: str
    field: LocalizationField
    value: str | None
    resolution: LocalizationResolution

    @field_validator("modelo_id", "revision_id", "casilla_id")
    @classmethod
    def _validate_identifier(cls, value: str) -> str:
        """Reject empty or whitespace-only resolved identities."""
        if not value.strip():
            raise ValueError("resolved localization identities must not be blank")
        return value

    @field_validator("locale")
    @classmethod
    def _validate_locale(cls, value: str) -> str:
        """Keep the matrix bound to the closed production locale set."""
        if value not in _SUPPORTED_LOCALES:
            raise ValueError(f"unsupported resolved localization locale {value!r}")
        return value

    @model_validator(mode="after")
    def _validate_resolution(self) -> ResolvedLocalizationEntry:
        """Ensure resolution states and values describe one real loader result."""
        if self.resolution == "official_spanish" and self.field != "label":
            raise ValueError("official_spanish resolution is valid only for label entries")
        if self.resolution == "absent" and self.value is not None:
            raise ValueError("absent resolution must not carry a value")
        if self.resolution != "absent" and self.value is None:
            raise ValueError("resolved localization must carry a value")
        return self


class ResolvedLocalizationMatrix(_StrictRecord):
    """Complete deterministic resolution matrix from the current registry loader."""

    schema_id: str = _RESOLVED_MATRIX_SCHEMA
    corpus_fingerprint: CorpusFingerprint
    locales: tuple[str, ...] = _SUPPORTED_LOCALES
    fields: tuple[LocalizationField, ...] = _LOCALIZATION_FIELDS
    entry_count: int = Field(ge=0)
    modelo_count: int = Field(ge=0)
    revision_count: int = Field(ge=0)
    occurrence_count: int = Field(ge=0)
    localized_count: int = Field(ge=0)
    official_spanish_fallback_count: int = Field(ge=0)
    absent_count: int = Field(ge=0)
    entries: tuple[ResolvedLocalizationEntry, ...]

    @model_validator(mode="after")
    def _validate_matrix(self) -> ResolvedLocalizationMatrix:
        """Reject incomplete, reordered, duplicated, or tampered matrix rows."""
        if self.schema_id != _RESOLVED_MATRIX_SCHEMA:
            raise ValueError(f"unsupported resolved localization matrix schema {self.schema_id!r}")
        if self.locales != _SUPPORTED_LOCALES:
            raise ValueError("locales must equal the supported production locale set in canonical order")
        if self.fields != _LOCALIZATION_FIELDS:
            raise ValueError("fields must be the canonical label/help pair")

        entry_keys = tuple(_resolved_entry_key(entry) for entry in self.entries)
        if entry_keys != tuple(sorted(entry_keys)) or len(entry_keys) != len(set(entry_keys)):
            raise ValueError("resolved localization entries must be unique and sorted by canonical coordinate")
        if self.entry_count != len(self.entries):
            raise ValueError("entry_count does not match entries")

        occurrence_keys = {(entry.modelo_id, entry.revision_id, entry.casilla_id) for entry in self.entries}
        revision_keys = {(entry.modelo_id, entry.revision_id) for entry in self.entries}
        modelo_ids = {entry.modelo_id for entry in self.entries}
        if self.occurrence_count != len(occurrence_keys):
            raise ValueError("occurrence_count does not match unique occurrence coordinates")
        if self.revision_count != len(revision_keys):
            raise ValueError("revision_count does not match unique revision coordinates")
        if self.modelo_count != len(modelo_ids):
            raise ValueError("modelo_count does not match unique modelo ids")
        expected_entry_count = self.occurrence_count * len(self.locales) * len(self.fields)
        if self.entry_count != expected_entry_count:
            raise ValueError("matrix does not contain every locale/field coordinate for every occurrence")

        expected_coordinates = {(locale, field) for locale in self.locales for field in self.fields}
        coordinates_by_occurrence: dict[tuple[str, str, str], set[tuple[str, LocalizationField]]] = {}
        for entry in self.entries:
            coordinates_by_occurrence.setdefault(
                (entry.modelo_id, entry.revision_id, entry.casilla_id),
                set(),
            ).add((entry.locale, entry.field))
        if any(coordinates != expected_coordinates for coordinates in coordinates_by_occurrence.values()):
            raise ValueError("each occurrence must have one row for every locale and field")

        localized_count = sum(entry.resolution == "localized" for entry in self.entries)
        fallback_count = sum(entry.resolution == "official_spanish" for entry in self.entries)
        absent_count = sum(entry.resolution == "absent" for entry in self.entries)
        if self.localized_count != localized_count:
            raise ValueError("localized_count does not match entry resolution states")
        if self.official_spanish_fallback_count != fallback_count:
            raise ValueError("official_spanish_fallback_count does not match entry resolution states")
        if self.absent_count != absent_count:
            raise ValueError("absent_count does not match entry resolution states")
        return self


def canonical_occurrence_key(
    *,
    modelo_id: str,
    revision_id: str,
    casilla_id: str,
    continuidad_id: str | None,
    field: LocalizationField,
) -> str:
    """Build the canonical occurrence address without inferring identity."""
    if continuidad_id is not None:
        key = f"modelo/{modelo_id}/casilla/continuidad/{continuidad_id}/{field}"
    else:
        key = f"modelo/{modelo_id}/revision/{revision_id}/casilla/{casilla_id}/{field}"
    return _validate_canonical_key_path(key)


class CanonicalOccurrenceCandidate(_StrictRecord):
    """One locale value paired with its identity-derived canonical address."""

    schema_id: str = _CANONICAL_CANDIDATE_SCHEMA
    modelo_id: str = Field(min_length=1)
    revision_id: str = Field(min_length=1)
    casilla_id: str = Field(min_length=1)
    continuidad_id: str | None = Field(default=None, min_length=1)
    locale: str
    field: LocalizationField
    value: str | None
    resolution: LocalizationResolution
    identity_scope: CanonicalOccurrenceScope
    canonical_key: str = Field(min_length=1)

    @field_validator("modelo_id", "revision_id", "casilla_id")
    @classmethod
    def _validate_identifier(cls, value: str) -> str:
        """Reject empty or whitespace-only candidate identities."""
        if not value.strip():
            raise ValueError("canonical candidate identities must not be blank")
        return value

    @field_validator("locale")
    @classmethod
    def _validate_locale(cls, value: str) -> str:
        """Keep candidate rows bound to the supported locale set."""
        if value not in _SUPPORTED_LOCALES:
            raise ValueError(f"unsupported canonical candidate locale {value!r}")
        return value

    @field_validator("canonical_key")
    @classmethod
    def _validate_canonical_key(cls, value: str) -> str:
        """Require one canonical POSIX address rather than a display token."""
        return _validate_canonical_key_path(value)

    @model_validator(mode="after")
    def _validate_candidate(self) -> CanonicalOccurrenceCandidate:
        """Ensure the address is exactly derived from declared source identity."""
        expected_scope: CanonicalOccurrenceScope = (
            "continuity" if self.continuidad_id is not None else "revision_occurrence"
        )
        if self.identity_scope != expected_scope:
            raise ValueError("identity_scope does not match continuidad_id presence")
        expected_key = canonical_occurrence_key(
            modelo_id=self.modelo_id,
            revision_id=self.revision_id,
            casilla_id=self.casilla_id,
            continuidad_id=self.continuidad_id,
            field=self.field,
        )
        if self.canonical_key != expected_key:
            raise ValueError("canonical_key does not match the declared occurrence identity")
        if self.resolution == "official_spanish" and self.field != "label":
            raise ValueError("official_spanish resolution is valid only for label candidates")
        if self.resolution == "absent" and self.value is not None:
            raise ValueError("absent candidate resolution must not carry a value")
        if self.resolution != "absent" and self.value is None:
            raise ValueError("resolved candidate must carry a value")
        return self


class CanonicalOccurrenceCandidates(_StrictRecord):
    """Deterministic candidate set generated from one resolved matrix."""

    schema_id: str = _CANONICAL_CANDIDATES_SCHEMA
    corpus_fingerprint: CorpusFingerprint
    candidate_count: int = Field(ge=0)
    occurrence_count: int = Field(ge=0)
    canonical_key_count: int = Field(ge=0)
    candidates: tuple[CanonicalOccurrenceCandidate, ...]

    @model_validator(mode="after")
    def _validate_candidates(self) -> CanonicalOccurrenceCandidates:
        """Reject reordered, duplicated, or incomplete candidate coordinates."""
        if self.schema_id != _CANONICAL_CANDIDATES_SCHEMA:
            raise ValueError(f"unsupported canonical candidate set schema {self.schema_id!r}")
        candidate_keys = tuple(_canonical_candidate_sort_key(candidate) for candidate in self.candidates)
        if candidate_keys != tuple(sorted(candidate_keys)) or len(candidate_keys) != len(set(candidate_keys)):
            raise ValueError("canonical candidates must be unique and sorted by source coordinate")
        if self.candidate_count != len(self.candidates):
            raise ValueError("candidate_count does not match candidates")
        occurrence_keys = {
            (candidate.modelo_id, candidate.revision_id, candidate.casilla_id) for candidate in self.candidates
        }
        if self.occurrence_count != len(occurrence_keys):
            raise ValueError("occurrence_count does not match candidate occurrences")
        if self.canonical_key_count != len({candidate.canonical_key for candidate in self.candidates}):
            raise ValueError("canonical_key_count does not match candidate keys")

        expected_coordinates = {(locale, field) for locale in _SUPPORTED_LOCALES for field in _LOCALIZATION_FIELDS}
        coordinates_by_occurrence: dict[tuple[str, str, str], set[tuple[str, LocalizationField]]] = {}
        for candidate in self.candidates:
            coordinates_by_occurrence.setdefault(
                (candidate.modelo_id, candidate.revision_id, candidate.casilla_id),
                set(),
            ).add((candidate.locale, candidate.field))
        if any(coordinates != expected_coordinates for coordinates in coordinates_by_occurrence.values()):
            raise ValueError("each occurrence must have one candidate for every locale and field")
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


def _validate_canonical_key_path(value: str) -> str:
    """Validate a logical key path while preserving colon-bearing casilla ids."""
    parsed = PurePosixPath(value)
    if (
        not value
        or parsed.is_absolute()
        or value != parsed.as_posix()
        or "\\" in value
        or any(part in {"", ".", ".."} for part in parsed.parts)
    ):
        raise ValueError(f"canonical key must be a POSIX relative path, got {value!r}")
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


def _resolved_entry_key(entry: ResolvedLocalizationEntry) -> tuple[str, str, str, str, str]:
    """Return the canonical sort coordinate for one resolved matrix row."""
    return (entry.modelo_id, entry.revision_id, entry.casilla_id, entry.locale, entry.field)


def _canonical_candidate_sort_key(candidate: CanonicalOccurrenceCandidate) -> tuple[str, str, str, str, str]:
    """Return the source-coordinate order for one canonical candidate."""
    return (
        candidate.modelo_id,
        candidate.revision_id,
        candidate.casilla_id,
        candidate.locale,
        candidate.field,
    )


def _resolved_entries_for_casilla(
    *,
    modelo_id: str,
    revision_id: str,
    casilla: CasillaDefinition,
) -> tuple[ResolvedLocalizationEntry, ...]:
    """Read every supported locale/field through the current loader behavior."""
    entries: list[ResolvedLocalizationEntry] = []
    for locale in _SUPPORTED_LOCALES:
        entries.append(
            ResolvedLocalizationEntry(
                modelo_id=modelo_id,
                revision_id=revision_id,
                casilla_id=casilla.id,
                continuidad_id=casilla.continuidad_id,
                locale=locale,
                field="label",
                value=casilla.get_label(locale),
                resolution=("localized" if locale in casilla.localized_labels else "official_spanish"),
            ),
        )
        entries.append(
            ResolvedLocalizationEntry(
                modelo_id=modelo_id,
                revision_id=revision_id,
                casilla_id=casilla.id,
                continuidad_id=casilla.continuidad_id,
                locale=locale,
                field="help",
                value=casilla.get_help(locale),
                resolution=("localized" if locale in casilla.localized_help else "absent"),
            ),
        )
    return tuple(entries)


def _validate_loaded_registry_against_inventory(
    modelos: tuple[ModeloDefinition, ...],
    inventory: MigrationSourceInventory,
) -> dict[str, ModeloDefinition]:
    """Require the loaded compiler population to match the pinned identities."""
    modelos_by_id = {str(modelo.id): modelo for modelo in modelos}
    if len(modelos_by_id) != len(modelos):
        raise MigrationInventoryError("current loader returned duplicate modelo ids")
    if tuple(sorted(modelos_by_id)) != inventory.modelo_ids:
        raise MigrationInventoryError(
            "current loader and pinned inventory disagree on modelo ids: "
            f"loader={sorted(modelos_by_id)!r} inventory={list(inventory.modelo_ids)!r}",
        )
    actual_revision_keys = tuple(
        sorted(
            (modelo_id, str(revision_id))
            for modelo_id, modelo in modelos_by_id.items()
            for revision_id in modelo.revisions
        ),
    )
    expected_revision_keys = tuple((item.modelo_id, item.revision_id) for item in inventory.supported_revisions)
    if actual_revision_keys != expected_revision_keys:
        raise MigrationInventoryError(
            "current loader and pinned inventory disagree on supported revisions: "
            f"loader={list(actual_revision_keys)!r} inventory={list(expected_revision_keys)!r}",
        )
    return modelos_by_id


def extract_resolved_localization_matrix(
    root: Path,
    inventory: MigrationSourceInventory | None = None,
) -> ResolvedLocalizationMatrix:
    """Extract the complete current resolved localization matrix read-only.

    The matrix uses the production loader's materialized get_label and
    get_help behavior for every supported Modelo, revision, casilla, locale,
    and field. A supplied S01 inventory pins the extraction to one corpus
    fingerprint; when omitted, the inventory is built immediately before
    extraction. Fingerprints are checked before loading, after loading, and
    after row construction so a concurrent source edit cannot yield a mixed
    matrix. This function never writes to the registry or migration output.

    Args:
        root: Registry root containing the current modelos corpus.
        inventory: Optional immutable S01 source inventory to bind to.

    Returns:
        A strict, sorted ResolvedLocalizationMatrix.

    Raises:
        MigrationInventoryError: If the pinned corpus drifts, the loader
            population changes, or source loading cannot complete.
    """
    resolved = _resolved_directory(root)
    pinned = inventory if inventory is not None else build_source_inventory(resolved)
    before = fingerprint_registry_corpus(resolved)
    if before != pinned.corpus_fingerprint:
        raise MigrationInventoryError(
            "registry source no longer matches the pinned inventory before resolved extraction; rebuild the inventory",
        )
    try:
        modelos, _catalogues = load_registry_tree(resolved)
    except Exception as exc:
        raise MigrationInventoryError(f"could not load the pinned registry for resolved extraction: {exc}") from exc
    after_load = fingerprint_registry_corpus(resolved)
    if after_load != before:
        raise MigrationInventoryError(
            f"registry source changed while resolved localization was loaded at {resolved}; "
            "retry after concurrent writes settle",
        )

    modelos_by_id = _validate_loaded_registry_against_inventory(modelos, pinned)
    entries: list[ResolvedLocalizationEntry] = []
    for modelo_id in sorted(modelos_by_id):
        modelo = modelos_by_id[modelo_id]
        for revision_id in sorted(str(key) for key in modelo.revisions):
            revision = modelo.revisions[revision_id]
            for casilla in sorted(revision.casillas, key=lambda item: item.id):
                entries.extend(
                    _resolved_entries_for_casilla(
                        modelo_id=modelo_id,
                        revision_id=revision_id,
                        casilla=casilla,
                    ),
                )
    frozen_entries = tuple(sorted(entries, key=_resolved_entry_key))
    finished = fingerprint_registry_corpus(resolved)
    if finished != after_load:
        raise MigrationInventoryError(
            f"registry source changed while resolved localization rows were built at {resolved}; "
            "retry after concurrent writes settle",
        )

    return ResolvedLocalizationMatrix(
        corpus_fingerprint=pinned.corpus_fingerprint,
        entry_count=len(frozen_entries),
        modelo_count=len({entry.modelo_id for entry in frozen_entries}),
        revision_count=len({(entry.modelo_id, entry.revision_id) for entry in frozen_entries}),
        occurrence_count=len(
            {(entry.modelo_id, entry.revision_id, entry.casilla_id) for entry in frozen_entries},
        ),
        localized_count=sum(entry.resolution == "localized" for entry in frozen_entries),
        official_spanish_fallback_count=sum(entry.resolution == "official_spanish" for entry in frozen_entries),
        absent_count=sum(entry.resolution == "absent" for entry in frozen_entries),
        entries=frozen_entries,
    )


def generate_canonical_occurrence_candidates(
    matrix: ResolvedLocalizationMatrix,
) -> CanonicalOccurrenceCandidates:
    """Generate identity-derived candidates from one resolved matrix.

    This step serializes only identities already present in the selected
    occurrence rows. A declared continuity id selects the continuity address;
    every other occurrence remains revision-exact. No repeated-id, text, or
    number-based continuity inference occurs here.
    """
    candidates = tuple(
        sorted(
            (
                CanonicalOccurrenceCandidate(
                    modelo_id=entry.modelo_id,
                    revision_id=entry.revision_id,
                    casilla_id=entry.casilla_id,
                    continuidad_id=entry.continuidad_id,
                    locale=entry.locale,
                    field=entry.field,
                    value=entry.value,
                    resolution=entry.resolution,
                    identity_scope=("continuity" if entry.continuidad_id is not None else "revision_occurrence"),
                    canonical_key=canonical_occurrence_key(
                        modelo_id=entry.modelo_id,
                        revision_id=entry.revision_id,
                        casilla_id=entry.casilla_id,
                        continuidad_id=entry.continuidad_id,
                        field=entry.field,
                    ),
                )
                for entry in matrix.entries
            ),
            key=_canonical_candidate_sort_key,
        ),
    )
    return CanonicalOccurrenceCandidates(
        corpus_fingerprint=matrix.corpus_fingerprint,
        candidate_count=len(candidates),
        occurrence_count=len(
            {(candidate.modelo_id, candidate.revision_id, candidate.casilla_id) for candidate in candidates}
        ),
        canonical_key_count=len({candidate.canonical_key for candidate in candidates}),
        candidates=candidates,
    )


__all__ = [
    "CanonicalOccurrenceCandidate",
    "CanonicalOccurrenceCandidates",
    "CorpusFileFingerprint",
    "CorpusFingerprint",
    "MigrationInventoryError",
    "MigrationSourceInventory",
    "ResolvedLocalizationEntry",
    "ResolvedLocalizationMatrix",
    "RevisionInventoryEntry",
    "build_source_inventory",
    "canonical_occurrence_key",
    "extract_resolved_localization_matrix",
    "fingerprint_registry_corpus",
    "generate_canonical_occurrence_candidates",
]
