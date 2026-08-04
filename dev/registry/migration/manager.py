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

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Final, Literal
from unicodedata import normalize

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from cadrumo.core import read_toml
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.hashing import canonical_json_bytes, hash_file, sha256_hex
from cadrumo.domain.calculations.registry import (
    CasillaDefinition,
    ModeloDefinition,
    ModeloRevisionSource,
    ModeloSource,
    discover_modelo_sources,
    load_registry_tree,
)
from cadrumo.locales._modelo_manager import (
    ModeloLocaleFieldKind,
    ModeloLocaleLeafState,
    classify_modelo_locale_leaf,
)

_CORPUS_FINGERPRINT_SCHEMA: Final[str] = "cadrumo.modelo-localization-cascade.corpus-fingerprint.v1"
_SOURCE_INVENTORY_SCHEMA: Final[str] = "cadrumo.modelo-localization-cascade.source-inventory.v1"
_RESOLVED_MATRIX_SCHEMA: Final[str] = "cadrumo.modelo-localization-cascade.resolved-matrix.v1"
_CANONICAL_CANDIDATE_SCHEMA: Final[str] = "cadrumo.modelo-localization-cascade.canonical-candidate.v1"
_CANONICAL_CANDIDATES_SCHEMA: Final[str] = "cadrumo.modelo-localization-cascade.canonical-candidates.v1"
_CLASSIFIED_CANDIDATE_SCHEMA: Final[str] = "cadrumo.modelo-localization-cascade.classified-candidate.v1"
_CLASSIFIED_CANDIDATES_SCHEMA: Final[str] = "cadrumo.modelo-localization-cascade.classified-candidates.v1"
_SOURCE_MANIFEST_ENTRY_SCHEMA: Final[str] = "cadrumo.modelo-localization-cascade.source-manifest-entry.v1"
_SOURCE_MANIFEST_SCHEMA: Final[str] = "cadrumo.modelo-localization-cascade.source-manifest.v1"
_UNRESOLVED_REVIEW_REGISTER_SCHEMA: Final[str] = "cadrumo.modelo-localization-cascade.unresolved-review-register.v1"
_CORPUS_SCOPE: Final[str] = "registry/aeat/**/*.toml"
_SHA256_PATTERN: Final[str] = r"^[0-9a-f]{64}$"

ModeloSourceLayout = Literal["single_file", "directory"]
RevisionSourceLayout = Literal["inline", "revision_file", "fragment_directory"]
LocalizationField = Literal["label", "help"]
LocalizationResolution = Literal["localized", "official_spanish", "absent"]
CanonicalOccurrenceScope = Literal["continuity", "revision_occurrence"]
CandidateClassification = Literal["grounded", "revision_exact", "continuity_candidate"]
SourceScope = Literal["schema", "modelo_locale", "revision_locale", "none"]
ReviewStatus = Literal["not_required", "unresolved"]
DriftField = Literal[
    "number",
    "segmento",
    "data_type",
    "semantic_role",
    "input_kind",
    "formula",
    "binding",
    "form_number",
    "label",
    "help",
]

_SUPPORTED_LOCALES: Final[tuple[str, ...]] = tuple(language.value for language in OutputLanguage)
_LOCALIZATION_FIELDS: Final[tuple[LocalizationField, ...]] = ("label", "help")
_DRIFT_FIELDS: Final[tuple[DriftField, ...]] = (
    "number",
    "segmento",
    "data_type",
    "semantic_role",
    "input_kind",
    "formula",
    "binding",
    "form_number",
    "label",
    "help",
)
_STRUCTURAL_DRIFT_FIELDS: Final[tuple[DriftField, ...]] = _DRIFT_FIELDS[:8]


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


class ClassifiedOccurrenceCandidate(_StrictRecord):
    """One S03 candidate with a structural migration-only classification."""

    schema_id: str = _CLASSIFIED_CANDIDATE_SCHEMA
    candidate: CanonicalOccurrenceCandidate
    classification: CandidateClassification
    provisional_candidate_id: str | None = None

    @model_validator(mode="after")
    def _validate_classification(self) -> ClassifiedOccurrenceCandidate:
        """Refuse classifications that disagree with declared continuity."""
        if self.schema_id != _CLASSIFIED_CANDIDATE_SCHEMA:
            raise ValueError(f"unsupported classified candidate schema {self.schema_id!r}")
        has_continuity = self.candidate.continuidad_id is not None
        if has_continuity and self.classification != "grounded":
            raise ValueError("declared continuidad_id candidates must be grounded")
        if not has_continuity and self.classification == "grounded":
            raise ValueError("ungrounded candidates must not be classified as grounded")
        if self.classification == "continuity_candidate":
            expected_id = _provisional_candidate_id(self.candidate)
            if self.provisional_candidate_id != expected_id:
                raise ValueError("continuity_candidate must carry its migration-only provisional group id")
        elif self.provisional_candidate_id is not None:
            raise ValueError("only continuity_candidate rows may carry a provisional group id")
        return self


class ClassifiedOccurrenceCandidates(_StrictRecord):
    """Deterministic structural classification of one canonical candidate set."""

    schema_id: str = _CLASSIFIED_CANDIDATES_SCHEMA
    corpus_fingerprint: CorpusFingerprint
    candidate_count: int = Field(ge=0)
    grounded_count: int = Field(ge=0)
    revision_exact_count: int = Field(ge=0)
    continuity_candidate_count: int = Field(ge=0)
    continuity_candidate_group_count: int = Field(ge=0)
    candidates: tuple[ClassifiedOccurrenceCandidate, ...]

    @model_validator(mode="after")
    def _validate_classified_candidates(self) -> ClassifiedOccurrenceCandidates:
        """Reject reordered rows or classification counter drift."""
        if self.schema_id != _CLASSIFIED_CANDIDATES_SCHEMA:
            raise ValueError(f"unsupported classified candidate set schema {self.schema_id!r}")
        candidate_keys = tuple(_canonical_candidate_sort_key(item.candidate) for item in self.candidates)
        if candidate_keys != tuple(sorted(candidate_keys)) or len(candidate_keys) != len(set(candidate_keys)):
            raise ValueError("classified candidates must be unique and sorted by source coordinate")
        if self.candidate_count != len(self.candidates):
            raise ValueError("candidate_count does not match classified candidates")
        grounded_count = sum(item.classification == "grounded" for item in self.candidates)
        revision_exact_count = sum(item.classification == "revision_exact" for item in self.candidates)
        continuity_candidate_count = sum(item.classification == "continuity_candidate" for item in self.candidates)
        continuity_groups = {
            item.provisional_candidate_id for item in self.candidates if item.classification == "continuity_candidate"
        }
        if self.grounded_count != grounded_count:
            raise ValueError("grounded_count does not match classifications")
        if self.revision_exact_count != revision_exact_count:
            raise ValueError("revision_exact_count does not match classifications")
        if self.continuity_candidate_count != continuity_candidate_count:
            raise ValueError("continuity_candidate_count does not match classifications")
        if self.continuity_candidate_group_count != len(continuity_groups):
            raise ValueError("continuity_candidate_group_count does not match provisional groups")
        if self.candidate_count != grounded_count + revision_exact_count + continuity_candidate_count:
            raise ValueError("classification counts do not partition candidates")
        return self


class SourceManifestEntry(_StrictRecord):
    """One sealed source observation carried into later migration stages."""

    schema_id: str = _SOURCE_MANIFEST_ENTRY_SCHEMA
    candidate: ClassifiedOccurrenceCandidate
    candidate_chain_id: str | None = None
    source_path: str | None = None
    source_scope: SourceScope
    raw_value: str | None
    old_resolved_value: str | None
    official_fallback: bool
    leaf_state: Literal["authored", "key_echo", "blank", "mirrored", "absent"]
    normalized_value_hash: str | None = Field(default=None, pattern=_SHA256_PATTERN)
    drift_fields: tuple[DriftField, ...] = ()
    review_status: ReviewStatus
    emitted_target: str | None = None
    source_hash: str | None = Field(default=None, pattern=_SHA256_PATTERN)

    @field_validator("candidate_chain_id", "emitted_target", mode="after")
    @classmethod
    def _validate_optional_nonblank(cls, value: str | None) -> str | None:
        """Reject blank migration tokens while allowing an absent target."""
        if value is not None and not value.strip():
            raise ValueError("optional migration identifiers must not be blank")
        return value

    @field_validator("source_path", mode="after")
    @classmethod
    def _validate_source_path(cls, value: str | None) -> str | None:
        """Require source paths to use the corpus-relative canonical form."""
        return None if value is None else _validate_relative_path(value)

    @field_validator("drift_fields", mode="after")
    @classmethod
    def _validate_drift_fields(cls, value: tuple[DriftField, ...]) -> tuple[DriftField, ...]:
        """Keep drift dimensions unique and in their documented order."""
        if value != tuple(field for field in _DRIFT_FIELDS if field in value):
            raise ValueError("drift_fields must be unique and in canonical order")
        return value

    @model_validator(mode="after")
    def _validate_source_observation(self) -> SourceManifestEntry:
        """Ensure the row preserves the classified candidate and old oracle."""
        if self.schema_id != _SOURCE_MANIFEST_ENTRY_SCHEMA:
            raise ValueError(f"unsupported source manifest entry schema {self.schema_id!r}")

        candidate = self.candidate.candidate
        classification = self.candidate.classification
        expected_chain_id = (
            candidate.continuidad_id
            if classification == "grounded"
            else self.candidate.provisional_candidate_id
            if classification == "continuity_candidate"
            else None
        )
        if self.candidate_chain_id != expected_chain_id:
            raise ValueError("candidate_chain_id does not match the classified candidate")
        if self.old_resolved_value != candidate.value:
            raise ValueError("old_resolved_value must preserve the resolved candidate value")
        expected_fallback = candidate.resolution == "official_spanish"
        if self.official_fallback != expected_fallback:
            raise ValueError("official_fallback does not match the candidate resolution")
        expected_review: ReviewStatus = "unresolved" if classification == "continuity_candidate" else "not_required"
        if self.review_status != expected_review:
            raise ValueError("review_status does not match the candidate classification")
        if self.emitted_target is not None:
            raise ValueError("S05 source observations must not claim an emitted target")

        if candidate.resolution == "absent":
            if any(
                value is not None
                for value in (self.raw_value, self.normalized_value_hash, self.source_path, self.source_hash)
            ):
                raise ValueError("absent observations must not carry source leaf values or hashes")
            if self.source_scope != "none" or self.leaf_state != "absent":
                raise ValueError("absent observations must use the none/absent source state")
        elif self.official_fallback:
            if self.source_scope != "schema":
                raise ValueError("official Spanish fallback must point at a schema source")
            if self.raw_value is None or self.raw_value != self.old_resolved_value:
                raise ValueError("schema fallback must preserve the official resolved value")
            if self.source_path is None or self.source_hash is None or self.leaf_state != "absent":
                raise ValueError("schema fallback must retain its source hash and absent locale leaf state")
        else:
            if self.source_scope not in {"modelo_locale", "revision_locale"}:
                raise ValueError("localized observations must point at a locale source")
            if self.raw_value is None or self.source_path is None or self.source_hash is None:
                raise ValueError("localized observations must carry source values and hashes")
            if self.raw_value != self.old_resolved_value:
                raise ValueError("localized source value must equal the old resolved value")
            if self.leaf_state == "absent":
                raise ValueError("localized observations must not have an absent leaf state")

        expected_hash = (
            None
            if self.raw_value is None
            else sha256_hex(_normalize_localization_value(self.raw_value).encode("utf-8"))
        )
        if self.normalized_value_hash != expected_hash:
            raise ValueError("normalized_value_hash does not match the raw source value")
        return self


class SourceManifest(_StrictRecord):
    """Sealed, deterministic manifest of every extracted source observation."""

    schema_id: str = _SOURCE_MANIFEST_SCHEMA
    corpus_fingerprint: CorpusFingerprint
    entry_count: int = Field(ge=0)
    grounded_count: int = Field(ge=0)
    revision_exact_count: int = Field(ge=0)
    continuity_candidate_count: int = Field(ge=0)
    unresolved_entry_count: int = Field(ge=0)
    source_file_count: int = Field(ge=0)
    manifest_sha256: str = Field(pattern=_SHA256_PATTERN)
    entries: tuple[SourceManifestEntry, ...]

    @model_validator(mode="after")
    def _validate_manifest(self) -> SourceManifest:
        """Reject reordered observations, counter drift, and unbound hashes."""
        if self.schema_id != _SOURCE_MANIFEST_SCHEMA:
            raise ValueError(f"unsupported source manifest schema {self.schema_id!r}")
        coordinates = tuple(_manifest_entry_sort_key(entry) for entry in self.entries)
        if coordinates != tuple(sorted(coordinates)) or len(coordinates) != len(set(coordinates)):
            raise ValueError("source manifest entries must be unique and sorted by candidate coordinate")
        if self.entry_count != len(self.entries):
            raise ValueError("entry_count does not match source manifest entries")
        counts = {
            classification: sum(entry.candidate.classification == classification for entry in self.entries)
            for classification in ("grounded", "revision_exact", "continuity_candidate")
        }
        if self.grounded_count != counts["grounded"]:
            raise ValueError("grounded_count does not match source manifest entries")
        if self.revision_exact_count != counts["revision_exact"]:
            raise ValueError("revision_exact_count does not match source manifest entries")
        if self.continuity_candidate_count != counts["continuity_candidate"]:
            raise ValueError("continuity_candidate_count does not match source manifest entries")
        if self.unresolved_entry_count != sum(entry.review_status == "unresolved" for entry in self.entries):
            raise ValueError("unresolved_entry_count does not match source manifest entries")
        if self.source_file_count != len(
            {entry.source_path for entry in self.entries if entry.source_path is not None}
        ):
            raise ValueError("source_file_count does not match source paths")
        file_hashes = {file.relative_path: file.sha256 for file in self.corpus_fingerprint.files}
        for entry in self.entries:
            if entry.source_path is not None and file_hashes.get(entry.source_path) != entry.source_hash:
                raise ValueError("source observation hash is not bound to the corpus fingerprint")
        if self.manifest_sha256 != _digest_manifest_entries(_SOURCE_MANIFEST_SCHEMA, self.entries):
            raise ValueError("manifest_sha256 does not match the canonical source observations")
        return self


class UnresolvedReviewRegister(_StrictRecord):
    """The source-manifest subset that still requires continuity review."""

    schema_id: str = _UNRESOLVED_REVIEW_REGISTER_SCHEMA
    source_manifest_sha256: str = Field(pattern=_SHA256_PATTERN)
    entry_count: int = Field(ge=0)
    group_count: int = Field(ge=0)
    register_sha256: str = Field(pattern=_SHA256_PATTERN)
    entries: tuple[SourceManifestEntry, ...]

    @model_validator(mode="after")
    def _validate_review_register(self) -> UnresolvedReviewRegister:
        """Require the register to remain a strict subset of unresolved candidates."""
        if self.schema_id != _UNRESOLVED_REVIEW_REGISTER_SCHEMA:
            raise ValueError(f"unsupported unresolved review register schema {self.schema_id!r}")
        coordinates = tuple(_manifest_entry_sort_key(entry) for entry in self.entries)
        if coordinates != tuple(sorted(coordinates)) or len(coordinates) != len(set(coordinates)):
            raise ValueError("unresolved review entries must be unique and sorted")
        if self.entry_count != len(self.entries):
            raise ValueError("entry_count does not match unresolved review entries")
        if any(
            entry.review_status != "unresolved" or entry.candidate.classification != "continuity_candidate"
            for entry in self.entries
        ):
            raise ValueError("unresolved review register may contain only continuity candidates")
        if self.group_count != len({entry.candidate_chain_id for entry in self.entries}):
            raise ValueError("group_count does not match unresolved candidate chains")
        if self.register_sha256 != _digest_manifest_entries(_UNRESOLVED_REVIEW_REGISTER_SCHEMA, self.entries):
            raise ValueError("register_sha256 does not match the canonical unresolved observations")
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


def _normalize_localization_value(value: str) -> str:
    """Apply the conservative comparison normalisation used for review hashes."""
    return normalize("NFKC", " ".join(value.split())).casefold().rstrip(".:").rstrip()


def _manifest_entry_sort_key(entry: SourceManifestEntry) -> tuple[str, str, str, str, str]:
    """Return the source-coordinate order for one manifest row."""
    candidate = entry.candidate.candidate
    return _canonical_candidate_sort_key(candidate)


def _digest_manifest_entries(schema_id: str, entries: Iterable[SourceManifestEntry]) -> str:
    """Hash one ordered entry stream with the manifest schema in its domain."""
    framed = bytearray(_digest_frame(schema_id))
    for entry in entries:
        payload = canonical_json_bytes(entry.model_dump(mode="json")).decode("utf-8")
        framed.extend(_digest_frame(payload))
    return sha256_hex(bytes(framed))


@dataclass(frozen=True)
class _SourceLeaf:
    """One raw locale leaf and the file that owns it."""

    relative_path: str
    scope: SourceScope
    value: str


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


def _provisional_candidate_id(candidate: CanonicalOccurrenceCandidate) -> str:
    """Build a migration-only grouping token without creating continuity identity."""
    return _validate_canonical_key_path(
        f"candidate/{candidate.modelo_id}/casilla/{candidate.casilla_id}",
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


def classify_canonical_occurrence_candidates(
    candidates: CanonicalOccurrenceCandidates,
) -> ClassifiedOccurrenceCandidates:
    """Classify candidates structurally without promoting provisional identity.

    A declared continuity id is grounded. An ungrounded casilla id that occurs
    in one revision remains revision-exact. An ungrounded id repeated across
    revisions receives a migration-only provisional grouping token and remains
    an unresolved continuity candidate. No value, label, printed number, or
    normalized text participates in this decision.
    """
    revisions_by_group: dict[tuple[str, str], set[str]] = {}
    for item in candidates.candidates:
        if item.continuidad_id is None:
            revisions_by_group.setdefault((item.modelo_id, item.casilla_id), set()).add(item.revision_id)

    classified: list[ClassifiedOccurrenceCandidate] = []
    for item in candidates.candidates:
        if item.continuidad_id is not None:
            classification: CandidateClassification = "grounded"
            provisional_id = None
        elif len(revisions_by_group[(item.modelo_id, item.casilla_id)]) > 1:
            classification = "continuity_candidate"
            provisional_id = _provisional_candidate_id(item)
        else:
            classification = "revision_exact"
            provisional_id = None
        classified.append(
            ClassifiedOccurrenceCandidate(
                candidate=item,
                classification=classification,
                provisional_candidate_id=provisional_id,
            ),
        )

    frozen = tuple(sorted(classified, key=lambda item: _canonical_candidate_sort_key(item.candidate)))
    return ClassifiedOccurrenceCandidates(
        corpus_fingerprint=candidates.corpus_fingerprint,
        candidate_count=len(frozen),
        grounded_count=sum(item.classification == "grounded" for item in frozen),
        revision_exact_count=sum(item.classification == "revision_exact" for item in frozen),
        continuity_candidate_count=sum(item.classification == "continuity_candidate" for item in frozen),
        continuity_candidate_group_count=len(
            {item.provisional_candidate_id for item in frozen if item.classification == "continuity_candidate"},
        ),
        candidates=frozen,
    )


def _relative_path_path(root: Path, relative_path: str) -> Path:
    """Resolve one validated corpus-relative path below ``root``."""
    return root.joinpath(*PurePosixPath(relative_path).parts)


def _read_source_toml(
    root: Path,
    relative_path: str,
    cache: dict[str, dict[str, object]],
) -> dict[str, object]:
    """Read one already-fingerprinted TOML source into a small parse cache."""
    parsed = cache.get(relative_path)
    if parsed is not None:
        return parsed
    try:
        parsed = read_toml(
            _relative_path_path(root, relative_path),
            error_factory=MigrationInventoryError,
        )
    except Exception as exc:
        if isinstance(exc, MigrationInventoryError):
            raise
        raise MigrationInventoryError(f"could not read source {relative_path!r}: {exc}") from exc
    cache[relative_path] = parsed
    return parsed


def _schema_casilla_ids(
    value: object,
    *,
    revision_id: str,
    casilla_id: str,
    current_revision: str | None = None,
) -> tuple[bool, ...]:
    """Return matches for one casilla while carrying TOML revision context."""
    matches: list[bool] = []
    if isinstance(value, Mapping):
        revisions = value.get("revisions")
        if isinstance(revisions, Mapping):
            for nested_revision_id, nested_value in revisions.items():
                if isinstance(nested_revision_id, str):
                    matches.extend(
                        _schema_casilla_ids(
                            nested_value,
                            revision_id=revision_id,
                            casilla_id=casilla_id,
                            current_revision=nested_revision_id,
                        ),
                    )
        if (
            current_revision == revision_id
            and value.get("id") == casilla_id
            and isinstance(value.get("label"), str)
            and isinstance(value.get("number"), str)
        ):
            matches.append(True)
        for key, nested_value in value.items():
            if key != "revisions":
                matches.extend(
                    _schema_casilla_ids(
                        nested_value,
                        revision_id=revision_id,
                        casilla_id=casilla_id,
                        current_revision=current_revision,
                    ),
                )
    elif isinstance(value, (list, tuple)):
        for nested_value in value:
            matches.extend(
                _schema_casilla_ids(
                    nested_value,
                    revision_id=revision_id,
                    casilla_id=casilla_id,
                    current_revision=current_revision,
                ),
            )
    return tuple(matches)


def _schema_casilla_coordinates(
    value: object,
    *,
    current_revision: str | None = None,
) -> tuple[tuple[str, str], ...]:
    """Index all schema casilla identities carried by one parsed TOML value."""
    coordinates: list[tuple[str, str]] = []
    if isinstance(value, Mapping):
        revisions = value.get("revisions")
        if isinstance(revisions, Mapping):
            for nested_revision_id, nested_value in revisions.items():
                if isinstance(nested_revision_id, str):
                    coordinates.extend(
                        _schema_casilla_coordinates(
                            nested_value,
                            current_revision=nested_revision_id,
                        ),
                    )
        casilla_id = value.get("id")
        if (
            current_revision is not None
            and isinstance(casilla_id, str)
            and isinstance(value.get("label"), str)
            and isinstance(value.get("number"), str)
        ):
            coordinates.append((current_revision, casilla_id))
        for key, nested_value in value.items():
            if key != "revisions":
                coordinates.extend(
                    _schema_casilla_coordinates(
                        nested_value,
                        current_revision=current_revision,
                    ),
                )
    elif isinstance(value, (list, tuple)):
        for nested_value in value:
            coordinates.extend(
                _schema_casilla_coordinates(
                    nested_value,
                    current_revision=current_revision,
                ),
            )
    return tuple(coordinates)


def _schema_source_path(
    *,
    revision_entry: RevisionInventoryEntry,
    revision_id: str,
    casilla_id: str,
    root: Path,
    source_cache: dict[str, dict[str, object]],
) -> str:
    """Locate the single schema fragment that declares one casilla."""
    matches: list[str] = []
    for relative_path in revision_entry.revision_source_paths:
        raw = _read_source_toml(root, relative_path, source_cache)
        if _schema_casilla_ids(raw, revision_id=revision_id, casilla_id=casilla_id):
            matches.append(relative_path)
    if len(matches) != 1:
        raise MigrationInventoryError(
            f"expected one schema source for {revision_entry.modelo_id!r}/{revision_id!r}/{casilla_id!r}, "
            f"found {matches!r}",
        )
    return matches[0]


def _locale_target_paths(
    root: Path,
    base_relative: PurePosixPath | None,
    locale: str,
) -> tuple[str, ...]:
    """Return one flat locale file or its sorted fragment files."""
    if base_relative is None:
        return ()
    flat_relative = base_relative / "locales" / f"{locale}.toml"
    flat_path = _relative_path_path(root, flat_relative.as_posix())
    fragment_relative = flat_relative.with_suffix("")
    fragment_path = _relative_path_path(root, fragment_relative.as_posix())
    if flat_path.exists() and fragment_path.is_dir():
        raise MigrationInventoryError(
            f"locale {locale!r} is both a file and fragment directory at {flat_relative.parent.as_posix()!r}",
        )
    if flat_path.exists():
        if not flat_path.is_file():
            raise MigrationInventoryError(f"locale target is not a file: {flat_relative.as_posix()}")
        return (flat_relative.as_posix(),)
    if not fragment_path.is_dir():
        return ()
    paths = tuple(
        sorted(_relative_source_path(root, path) for path in fragment_path.glob("*.toml") if path.is_file()),
    )
    return paths


def _locale_table_values(
    raw: Mapping[str, object],
    *,
    relative_path: str,
) -> dict[tuple[LocalizationField, str], str]:
    """Narrow one locale TOML mapping to validated label/help leaves."""
    values: dict[tuple[LocalizationField, str], str] = {}
    for field in _LOCALIZATION_FIELDS:
        table = raw.get("labels" if field == "label" else "help", {})
        if not isinstance(table, Mapping):
            raise MigrationInventoryError(
                f"locale source {relative_path!r} has a non-table {field!r} localization section",
            )
        for key, value in table.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise MigrationInventoryError(
                    f"locale source {relative_path!r} has a non-string {field!r} leaf",
                )
            coordinate = (field, key)
            if coordinate in values:
                raise MigrationInventoryError(
                    f"locale source {relative_path!r} repeats {field!r}/{key!r}",
                )
            values[coordinate] = value
    return values


def _modelo_relative_directory(entry: RevisionInventoryEntry) -> PurePosixPath | None:
    """Return a directory-mode modelo directory from its manifest path."""
    if entry.modelo_source_layout != "directory":
        return None
    return PurePosixPath(entry.modelo_source_path).parent


def _revision_relative_directory(entry: RevisionInventoryEntry) -> PurePosixPath | None:
    """Return a fragment-directory revision path, if the loader has one."""
    if entry.revision_source_layout != "fragment_directory":
        return None
    for relative_path in entry.revision_source_paths:
        parts = PurePosixPath(relative_path).parts
        try:
            revisions_index = parts.index("revisions")
        except ValueError:
            continue
        if revisions_index + 1 < len(parts) and parts[revisions_index + 1] == entry.revision_id:
            return PurePosixPath(*parts[: revisions_index + 2])
    raise MigrationInventoryError(
        f"revision source paths do not identify a directory for {entry.modelo_id!r}/{entry.revision_id!r}",
    )


def _locale_leaf_source(
    *,
    root: Path,
    revision_entry: RevisionInventoryEntry,
    locale: str,
    field: LocalizationField,
    casilla_id: str,
    continuidad_id: str | None,
    source_cache: dict[str, dict[str, object]],
    locale_path_cache: dict[tuple[str, str, str, str], tuple[str, ...]],
    locale_value_cache: dict[str, dict[tuple[LocalizationField, str], str]],
) -> _SourceLeaf | None:
    """Find the real loader-winning locale source for one occurrence leaf."""
    target_key = casilla_id
    targets: list[tuple[SourceScope, PurePosixPath | None]] = [
        ("revision_locale", _revision_relative_directory(revision_entry)),
    ]
    if continuidad_id is not None:
        targets.append(("modelo_locale", _modelo_relative_directory(revision_entry)))

    for scope, base_relative in targets:
        cache_key = (revision_entry.modelo_id, revision_entry.revision_id, locale, scope)
        paths = locale_path_cache.get(cache_key)
        if paths is None:
            paths = _locale_target_paths(root, base_relative, locale)
            locale_path_cache[cache_key] = paths
        if scope == "modelo_locale":
            if continuidad_id is None:
                continue
            target_key = continuidad_id
        else:
            target_key = casilla_id
        matches: list[_SourceLeaf] = []
        for relative_path in paths:
            values = locale_value_cache.get(relative_path)
            if values is None:
                values = _locale_table_values(
                    _read_source_toml(root, relative_path, source_cache),
                    relative_path=relative_path,
                )
                locale_value_cache[relative_path] = values
            value = values.get((field, target_key))
            if value is not None:
                matches.append(_SourceLeaf(relative_path=relative_path, scope=scope, value=value))
        if len(matches) > 1:
            raise MigrationInventoryError(
                f"locale source has duplicate {scope}/{locale}/{field}/{target_key} leaves: "
                f"{[match.relative_path for match in matches]!r}",
            )
        if matches:
            return matches[0]
    return None


def _stable_casilla_value(casilla: CasillaDefinition, field: str) -> str | None:
    """Project one structural casilla field into a deterministic scalar."""
    value = getattr(casilla, field)
    if value is None:
        return None
    enum_value = getattr(value, "value", None)
    return str(enum_value if enum_value is not None else value)


def _manifest_drift_fields(
    classified: ClassifiedOccurrenceCandidates,
    casillas: Mapping[tuple[str, str, str], CasillaDefinition],
) -> dict[tuple[str, str, str, str, str], tuple[DriftField, ...]]:
    """Measure structural and resolved-value drift without inferring identity."""
    grouped: dict[tuple[str, str, str], list[ClassifiedOccurrenceCandidate]] = {}
    for item in classified.candidates:
        candidate = item.candidate
        if item.classification == "revision_exact":
            continue
        if item.classification == "grounded":
            if candidate.continuidad_id is None:
                raise MigrationInventoryError("grounded candidate lost continuidad_id")
            group_key = (candidate.modelo_id, "grounded", candidate.continuidad_id)
        else:
            if item.provisional_candidate_id is None:
                raise MigrationInventoryError("continuity candidate lost provisional group id")
            group_key = (candidate.modelo_id, "candidate", item.provisional_candidate_id)
        grouped.setdefault(group_key, []).append(item)

    drift_by_coordinate: dict[tuple[str, str, str, str, str], tuple[DriftField, ...]] = {}
    for members in grouped.values():
        occurrence_keys = {
            (item.candidate.modelo_id, item.candidate.revision_id, item.candidate.casilla_id) for item in members
        }
        if len(occurrence_keys) < 2:
            continue
        drift: list[DriftField] = []
        for field in _STRUCTURAL_DRIFT_FIELDS:
            values = {_stable_casilla_value(casillas[key], field) for key in occurrence_keys}
            if len(values) > 1:
                drift.append(field)
        for field in _LOCALIZATION_FIELDS:
            values = {item.candidate.value for item in members if item.candidate.field == field}
            if len(values) > 1:
                drift.append("label" if field == "label" else "help")
        ordered_drift: tuple[DriftField, ...] = tuple(field for field in _DRIFT_FIELDS if field in drift)
        for item in members:
            candidate = item.candidate
            drift_by_coordinate[
                (
                    candidate.modelo_id,
                    candidate.revision_id,
                    candidate.casilla_id,
                    candidate.locale,
                    candidate.field,
                )
            ] = ordered_drift
    return drift_by_coordinate


def build_source_manifest(
    root: Path,
    classified: ClassifiedOccurrenceCandidates,
    inventory: MigrationSourceInventory | None = None,
) -> SourceManifest:
    """Build the sealed source manifest without writing registry or output data.

    The supplied S04 classification is bound to one S01 fingerprint. The
    current loader supplies structural casilla objects, while raw TOML reads
    identify the exact schema or locale file owning each observation. No
    provisional candidate is copied into a production continuity field.
    """
    resolved = _resolved_directory(root)
    pinned = inventory if inventory is not None else build_source_inventory(resolved)
    if classified.corpus_fingerprint != pinned.corpus_fingerprint:
        raise MigrationInventoryError("classified candidates do not match the pinned source inventory")
    before = fingerprint_registry_corpus(resolved)
    if before != pinned.corpus_fingerprint:
        raise MigrationInventoryError("registry source no longer matches the pinned source inventory")

    try:
        modelos, _catalogues = load_registry_tree(resolved)
    except Exception as exc:
        raise MigrationInventoryError(f"could not load the pinned registry for source manifest: {exc}") from exc
    after_load = fingerprint_registry_corpus(resolved)
    if after_load != before:
        raise MigrationInventoryError("registry source changed while source manifest loader ran")
    modelos_by_id = _validate_loaded_registry_against_inventory(modelos, pinned)

    casillas: dict[tuple[str, str, str], CasillaDefinition] = {}
    for modelo_id, modelo in modelos_by_id.items():
        for revision_id, revision in modelo.revisions.items():
            for casilla in revision.casillas:
                key = (modelo_id, str(revision_id), casilla.id)
                if key in casillas:
                    raise MigrationInventoryError(f"duplicate loaded casilla occurrence {key!r}")
                casillas[key] = casilla

    inventory_by_revision = {(entry.modelo_id, entry.revision_id): entry for entry in pinned.supported_revisions}
    file_hashes = {file.relative_path: file.sha256 for file in pinned.corpus_fingerprint.files}
    source_cache: dict[str, dict[str, object]] = {}
    locale_value_cache: dict[str, dict[tuple[LocalizationField, str], str]] = {}
    locale_path_cache: dict[tuple[str, str, str, str], tuple[str, ...]] = {}
    schema_path_index: dict[tuple[str, str, str], str] = {}
    for revision_entry in pinned.supported_revisions:
        for relative_path in revision_entry.revision_source_paths:
            raw = _read_source_toml(resolved, relative_path, source_cache)
            for revision_id, casilla_id in _schema_casilla_coordinates(raw):
                coordinate = (revision_entry.modelo_id, revision_id, casilla_id)
                previous = schema_path_index.get(coordinate)
                if previous is not None and previous != relative_path:
                    raise MigrationInventoryError(
                        f"duplicate schema sources for {coordinate!r}: {previous!r}, {relative_path!r}",
                    )
                schema_path_index[coordinate] = relative_path
    drift_fields = _manifest_drift_fields(classified, casillas)
    entries: list[SourceManifestEntry] = []

    for classified_candidate in classified.candidates:
        candidate = classified_candidate.candidate
        occurrence_key = (candidate.modelo_id, candidate.revision_id, candidate.casilla_id)
        casilla = casillas.get(occurrence_key)
        if casilla is None:
            raise MigrationInventoryError(
                f"classified candidate is not a loaded casilla occurrence: {occurrence_key!r}"
            )
        revision_entry = inventory_by_revision.get((candidate.modelo_id, candidate.revision_id))
        if revision_entry is None:
            raise MigrationInventoryError(f"classified candidate is not in the pinned inventory: {occurrence_key!r}")

        schema_path = schema_path_index.get(occurrence_key)
        if schema_path is None:
            raise MigrationInventoryError(f"classified candidate has no schema source: {occurrence_key!r}")
        local_source = _locale_leaf_source(
            root=resolved,
            revision_entry=revision_entry,
            locale=candidate.locale,
            field=candidate.field,
            casilla_id=candidate.casilla_id,
            continuidad_id=candidate.continuidad_id,
            source_cache=source_cache,
            locale_path_cache=locale_path_cache,
            locale_value_cache=locale_value_cache,
        )
        localized_label = _locale_leaf_source(
            root=resolved,
            revision_entry=revision_entry,
            locale=candidate.locale,
            field="label",
            casilla_id=candidate.casilla_id,
            continuidad_id=candidate.continuidad_id,
            source_cache=source_cache,
            locale_path_cache=locale_path_cache,
            locale_value_cache=locale_value_cache,
        )

        if candidate.resolution == "localized":
            if local_source is None:
                raise MigrationInventoryError(
                    "localized candidate has no raw locale source: "
                    f"{occurrence_key!r}/{candidate.locale}/{candidate.field}",
                )
            raw_value = local_source.value
            source_path = local_source.relative_path
            source_scope: SourceScope = local_source.scope
            source_key = candidate.continuidad_id if local_source.scope == "modelo_locale" else candidate.casilla_id
            if source_key is None:
                raise MigrationInventoryError("modelo locale source lost its continuity key")
            leaf_value = classify_modelo_locale_leaf(
                ModeloLocaleFieldKind.LABELS if candidate.field == "label" else ModeloLocaleFieldKind.HELP,
                source_key,
                raw_value,
                label_value=localized_label.value if localized_label is not None else None,
                official_label=casilla.label,
            ).value
            official_fallback = False
        elif candidate.resolution == "official_spanish":
            raw_value = casilla.label
            source_path = schema_path
            source_scope = "schema"
            leaf_value = ModeloLocaleLeafState.ABSENT.value
            official_fallback = True
        else:
            raw_value = None
            source_path = None
            source_scope = "none"
            leaf_value = ModeloLocaleLeafState.ABSENT.value
            official_fallback = False

        source_hash = None if source_path is None else file_hashes.get(source_path)
        if source_path is not None and source_hash is None:
            raise MigrationInventoryError(f"source path is absent from the pinned fingerprint: {source_path!r}")
        entries.append(
            SourceManifestEntry(
                candidate=classified_candidate,
                candidate_chain_id=(
                    casilla.continuidad_id
                    if classified_candidate.classification == "grounded"
                    else classified_candidate.provisional_candidate_id
                    if classified_candidate.classification == "continuity_candidate"
                    else None
                ),
                source_path=source_path,
                source_scope=source_scope,
                raw_value=raw_value,
                old_resolved_value=candidate.value,
                official_fallback=official_fallback,
                leaf_state=leaf_value,
                normalized_value_hash=(
                    None if raw_value is None else sha256_hex(_normalize_localization_value(raw_value).encode("utf-8"))
                ),
                drift_fields=drift_fields.get(
                    (
                        candidate.modelo_id,
                        candidate.revision_id,
                        candidate.casilla_id,
                        candidate.locale,
                        candidate.field,
                    ),
                    (),
                ),
                review_status=(
                    "unresolved" if classified_candidate.classification == "continuity_candidate" else "not_required"
                ),
                source_hash=source_hash,
            ),
        )

    frozen_entries = tuple(sorted(entries, key=_manifest_entry_sort_key))
    finished = fingerprint_registry_corpus(resolved)
    if finished != after_load:
        raise MigrationInventoryError("registry source changed while source manifest rows were built")
    return SourceManifest(
        corpus_fingerprint=pinned.corpus_fingerprint,
        entry_count=len(frozen_entries),
        grounded_count=sum(entry.candidate.classification == "grounded" for entry in frozen_entries),
        revision_exact_count=sum(entry.candidate.classification == "revision_exact" for entry in frozen_entries),
        continuity_candidate_count=sum(
            entry.candidate.classification == "continuity_candidate" for entry in frozen_entries
        ),
        unresolved_entry_count=sum(entry.review_status == "unresolved" for entry in frozen_entries),
        source_file_count=len({entry.source_path for entry in frozen_entries if entry.source_path is not None}),
        manifest_sha256=_digest_manifest_entries(_SOURCE_MANIFEST_SCHEMA, frozen_entries),
        entries=frozen_entries,
    )


def build_unresolved_review_register(manifest: SourceManifest) -> UnresolvedReviewRegister:
    """Extract the unresolved continuity-candidate observations for review."""
    entries = tuple(entry for entry in manifest.entries if entry.review_status == "unresolved")
    return UnresolvedReviewRegister(
        source_manifest_sha256=manifest.manifest_sha256,
        entry_count=len(entries),
        group_count=len({entry.candidate_chain_id for entry in entries}),
        register_sha256=_digest_manifest_entries(_UNRESOLVED_REVIEW_REGISTER_SCHEMA, entries),
        entries=entries,
    )


__all__ = [
    "CandidateClassification",
    "CanonicalOccurrenceCandidate",
    "CanonicalOccurrenceCandidates",
    "ClassifiedOccurrenceCandidate",
    "ClassifiedOccurrenceCandidates",
    "CorpusFileFingerprint",
    "CorpusFingerprint",
    "MigrationInventoryError",
    "MigrationSourceInventory",
    "ResolvedLocalizationEntry",
    "ResolvedLocalizationMatrix",
    "RevisionInventoryEntry",
    "build_source_inventory",
    "canonical_occurrence_key",
    "classify_canonical_occurrence_candidates",
    "extract_resolved_localization_matrix",
    "fingerprint_registry_corpus",
    "generate_canonical_occurrence_candidates",
]
