"""Deterministic provenance contracts for generated export-fragment trees.

This development-only module records how a later generator derived one export
tree.  It deliberately does not locate, load, infer from, or fall back to a
shipped export layout.  The caller supplies the loader-materialised target
layout after the future publication step has validated the generated tree.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Final, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from cadrumo.core.hashing import canonical_json_bytes, content_hash_hex, hash_file
from cadrumo.domain.calculations.registry import (
    ExportLayoutDefinition,
    ModeloId,
    RegistryValidationError,
    RevisionId,
    SourceRefId,
)

from ._record_design_ir import RECORD_DESIGN_INTERMEDIATE_SCHEMA_VERSION, RecordDesignIntermediate
from ._semantic_map import SemanticMap

__all__ = [
    "EXPORT_FRAGMENT_GENERATOR_SCHEMA_VERSION",
    "EXPORT_FRAGMENT_PROVENANCE_FILENAME",
    "EXPORT_FRAGMENT_PROVENANCE_SCHEMA_VERSION",
    "ExportFragmentOutputDigest",
    "ExportFragmentProvenanceManifest",
    "ExportFragmentTarget",
    "build_export_fragment_provenance_manifest",
    "collect_export_fragment_output_digests",
    "export_fragment_provenance_manifest_json_bytes",
    "export_fragment_provenance_path",
    "load_export_fragment_provenance_manifest",
    "loader_semantic_digest",
    "normalised_loader_semantics",
    "semantic_map_digest",
]


EXPORT_FRAGMENT_PROVENANCE_SCHEMA_VERSION: Final[int] = 1
"""Current wire schema for the adjacent non-loader provenance manifest."""

EXPORT_FRAGMENT_GENERATOR_SCHEMA_VERSION: Final[int] = 2
"""Current generator contract recorded by every provenance manifest."""

_LOADER_SEMANTIC_SCHEMA_VERSION: Final[int] = 1
_SHA256_PATTERN: Final[str] = r"^[0-9a-f]{64}$"
EXPORT_FRAGMENT_PROVENANCE_FILENAME: Final[str] = "export.provenance.json"
"""Sibling filename for an export directory's non-loader provenance manifest."""

_SEMANTIC_MAP_KEYS: Final[frozenset[str]] = frozenset({"modelo", "design_epoch", "records", "entries"})
_SEMANTIC_MAP_RECORD_KEYS: Final[frozenset[str]] = frozenset(
    {"sheet", "record_identity", "export_record_id", "record_type"},
)
_SEMANTIC_MAP_ENTRY_KEYS: Final[frozenset[str]] = frozenset(
    {
        "anchor",
        "export_field_id",
        "kind",
        "casilla_id",
        "binding",
        "literal",
        "header_key",
        "draft_attribute",
        "computed_key",
        "legal_refs",
        "source_refs",
    },
)
_SEMANTIC_MAP_ANCHOR_KEYS: Final[frozenset[str]] = frozenset(
    {"sheet", "source_row", "source_cell", "ordinal", "record_identity"},
)
_LAYOUT_KEYS: Final[frozenset[str]] = frozenset(
    {
        "id",
        "format",
        "dictionary_source_ref",
        "source_refs",
        "legal_refs",
        "records",
        "dictionary_path_overrides",
        "aux_idioma",
        "aux_version",
    },
)
_RECORD_KEYS: Final[frozenset[str]] = frozenset(
    {
        "id",
        "record_type",
        "order",
        "encoding",
        "line_ending",
        "required",
        "repeat",
        "binding_record",
        "row_field_casilla_ids",
        "discriminator",
        "requires_positive_casilla_id",
        "fields",
    },
)
_FIELD_KEYS: Final[frozenset[str]] = frozenset(
    {
        "id",
        "offset",
        "length",
        "kind",
        "casilla_id",
        "binding",
        "literal",
        "header_key",
        "draft_attribute",
        "computed_key",
        "data_type",
        "required",
        "padding",
        "justification",
        "date_format",
        "decimals",
        "signed",
        "legal_refs",
        "source_refs",
    },
)
_DISCRIMINATOR_KEYS: Final[frozenset[str]] = frozenset({"offset", "length", "requires"})
_DICTIONARY_OVERRIDE_KEYS: Final[frozenset[str]] = frozenset({"field_id", "path", "reason"})


class _StrictModel(BaseModel):
    """Frozen development-tool boundary with no read tolerance."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class ExportFragmentTarget(_StrictModel):
    """One explicitly authored revision/design generation target."""

    modelo: ModeloId
    revision_id: RevisionId
    design_epoch: str = Field(min_length=1)


class ExportFragmentOutputDigest(_StrictModel):
    """The SHA-256 of one generated file, addressed below its export root."""

    relative_path: str = Field(min_length=1, max_length=4096)
    sha256: str = Field(pattern=_SHA256_PATTERN)

    @field_validator("relative_path")
    @classmethod
    def _refuse_unsafe_relative_path(cls, value: str) -> str:
        if "\\" in value or "\x00" in value or ":" in value:
            raise ValueError("output digest path must be a portable POSIX-relative path")
        if PurePosixPath(value).is_absolute() or PureWindowsPath(value).is_absolute() or PureWindowsPath(value).drive:
            raise ValueError("output digest path must not be absolute or drive-qualified")
        raw_parts = value.split("/")
        if any(part in {"", ".", ".."} for part in raw_parts):
            raise ValueError("output digest path must not contain empty, current, or parent segments")
        return PurePosixPath(value).as_posix()


class ExportFragmentProvenanceManifest(_StrictModel):
    """Adjacent, canonical, non-loader provenance for one generated revision.

    No timestamp, host path, temporary directory, or mutable legacy-tree value
    participates in this contract.  Every required version is explicit so an
    old manifest cannot be mistaken for a current parser or generator schema.
    """

    manifest_schema_version: int = Field(ge=1)
    source_ref: SourceRefId
    source_sha256: str = Field(pattern=_SHA256_PATTERN)
    parser_schema_version: int = Field(ge=1)
    generator_schema_version: int = Field(ge=1)
    semantic_map_sha256: str = Field(pattern=_SHA256_PATTERN)
    modelo: ModeloId
    revision_id: RevisionId
    design_epoch: str = Field(min_length=1)
    loader_semantic_sha256: str = Field(pattern=_SHA256_PATTERN)
    output_files: tuple[ExportFragmentOutputDigest, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _refuse_unknown_schema_or_unordered_outputs(self) -> ExportFragmentProvenanceManifest:
        if self.manifest_schema_version != EXPORT_FRAGMENT_PROVENANCE_SCHEMA_VERSION:
            raise ValueError(
                "unsupported export-fragment provenance manifest schema "
                f"{self.manifest_schema_version}; expected {EXPORT_FRAGMENT_PROVENANCE_SCHEMA_VERSION}",
            )
        if self.parser_schema_version != RECORD_DESIGN_INTERMEDIATE_SCHEMA_VERSION:
            raise ValueError(
                "parser schema drift: manifest records "
                f"{self.parser_schema_version}, expected {RECORD_DESIGN_INTERMEDIATE_SCHEMA_VERSION}",
            )
        if self.generator_schema_version != EXPORT_FRAGMENT_GENERATOR_SCHEMA_VERSION:
            raise ValueError(
                "generator schema drift: manifest records "
                f"{self.generator_schema_version}, expected {EXPORT_FRAGMENT_GENERATOR_SCHEMA_VERSION}",
            )
        paths = tuple(item.relative_path for item in self.output_files)
        if paths != tuple(sorted(paths)):
            raise ValueError("provenance output files must be sorted by relative path")
        if len(set(paths)) != len(paths):
            raise ValueError("provenance output files must not contain duplicate relative paths")
        return self


def export_fragment_provenance_path(export_directory: Path) -> Path:
    """Return the manifest sibling path; it is intentionally outside loader input."""
    return export_directory.parent / EXPORT_FRAGMENT_PROVENANCE_FILENAME


def semantic_map_digest(semantic_map: SemanticMap) -> str:
    """Return a stable digest of reviewed semantic-map meaning, independent of entry order."""
    payload = semantic_map.model_dump(mode="json")
    _require_exact_keys(payload, _SEMANTIC_MAP_KEYS, subject="semantic-map")
    entries = _as_object_list(payload["entries"], subject="semantic-map entries")
    normalised_entries = [_normalise_semantic_map_entry(entry) for entry in entries]
    normalised_entries.sort(key=_semantic_entry_sort_key)
    records = _as_object_list(payload["records"], subject="semantic-map records")
    normalised_records = [_normalise_semantic_map_record(record) for record in records]
    normalised_records.sort(key=_semantic_record_sort_key)
    return content_hash_hex(
        {
            "modelo": payload["modelo"],
            "design_epoch": payload["design_epoch"],
            "records": normalised_records,
            "entries": normalised_entries,
        },
    )


def normalised_loader_semantics(loaded_layout: ExportLayoutDefinition) -> dict[str, object]:
    """Project loader material into the stable semantics that provenance attests.

    The caller must provide the real loader's validated layout from the freshly
    generated target tree. This function receives no paths and has no legacy
    lookup or fallback surface. Exact-key checks are deliberate: an added loader
    schema field refuses until this projection and its version are reviewed.
    """
    payload = loaded_layout.model_dump(mode="json")
    _require_exact_keys(payload, _LAYOUT_KEYS, subject="loader export layout")
    records = [_normalise_loader_record(item) for item in _as_object_list(payload["records"], subject="loader records")]
    records.sort(key=_loader_record_sort_key)
    overrides = [
        _normalise_dictionary_override(item)
        for item in _as_object_list(payload["dictionary_path_overrides"], subject="loader dictionary overrides")
    ]
    overrides.sort(key=lambda item: _as_string(item["field_id"], subject="loader dictionary override field_id"))
    return {
        "loader_semantic_schema_version": _LOADER_SEMANTIC_SCHEMA_VERSION,
        "id": payload["id"],
        "format": payload["format"],
        "dictionary_source_ref": payload["dictionary_source_ref"],
        "source_refs": _sorted_strings(payload["source_refs"], subject="loader layout source_refs"),
        "legal_refs": _sorted_strings(payload["legal_refs"], subject="loader layout legal_refs"),
        "records": records,
        "dictionary_path_overrides": overrides,
        "aux_idioma": payload["aux_idioma"],
        "aux_version": payload["aux_version"],
    }


def loader_semantic_digest(loaded_layout: ExportLayoutDefinition) -> str:
    """Return the canonical digest of a real loader-materialised export layout."""
    return content_hash_hex(normalised_loader_semantics(loaded_layout))


def collect_export_fragment_output_digests(export_root: Path) -> tuple[ExportFragmentOutputDigest, ...]:
    """Hash every real regular file below one generated export root.

    Symlinks and junctions are refused before hashing so no manifest can attest
    to data outside the candidate tree. This function only observes a supplied
    tree; it does not render, create, replace, or publish one.
    """
    if export_root.is_symlink() or export_root.is_junction():
        raise RegistryValidationError(f"export provenance refuses linked export root: {export_root}")
    if not export_root.is_dir():
        raise FileNotFoundError(export_root)
    resolved_root = export_root.resolve()
    entries: list[ExportFragmentOutputDigest] = []
    for candidate in sorted(export_root.rglob("*"), key=lambda path: path.as_posix()):
        if candidate.is_symlink() or candidate.is_junction():
            raise RegistryValidationError(f"export provenance refuses linked output path: {candidate}")
        if not candidate.is_file():
            continue
        relative_path = PurePosixPath(*candidate.relative_to(export_root).parts).as_posix()
        resolved_candidate = candidate.resolve()
        try:
            resolved_candidate.relative_to(resolved_root)
        except ValueError as exc:
            raise RegistryValidationError(f"export provenance path escapes export root: {candidate}") from exc
        digest, _byte_count = hash_file(candidate)
        entries.append(ExportFragmentOutputDigest(relative_path=relative_path, sha256=digest))
    if not entries:
        raise RegistryValidationError(f"export provenance found no generated output files under {export_root}")
    return tuple(sorted(entries, key=lambda item: item.relative_path))


def build_export_fragment_provenance_manifest(
    *,
    intermediate: RecordDesignIntermediate,
    semantic_map: SemanticMap,
    target: ExportFragmentTarget,
    loaded_layout: ExportLayoutDefinition,
    export_root: Path,
) -> ExportFragmentProvenanceManifest:
    """Assemble provenance from fixed authorities without emitting a file."""
    _validate_generation_scope(intermediate=intermediate, semantic_map=semantic_map, target=target)
    return ExportFragmentProvenanceManifest(
        manifest_schema_version=EXPORT_FRAGMENT_PROVENANCE_SCHEMA_VERSION,
        source_ref=intermediate.source.source_ref,
        source_sha256=intermediate.source.source_sha256,
        parser_schema_version=RECORD_DESIGN_INTERMEDIATE_SCHEMA_VERSION,
        generator_schema_version=EXPORT_FRAGMENT_GENERATOR_SCHEMA_VERSION,
        semantic_map_sha256=semantic_map_digest(semantic_map),
        modelo=target.modelo,
        revision_id=target.revision_id,
        design_epoch=target.design_epoch,
        loader_semantic_sha256=loader_semantic_digest(loaded_layout),
        output_files=collect_export_fragment_output_digests(export_root),
    )


def export_fragment_provenance_manifest_json_bytes(manifest: ExportFragmentProvenanceManifest) -> bytes:
    """Return the sole canonical JSON serialisation for a provenance manifest."""
    return canonical_json_bytes(manifest.model_dump(mode="json"))


def load_export_fragment_provenance_manifest(raw: bytes) -> ExportFragmentProvenanceManifest:
    """Load only exact canonical JSON; malformed, duplicate, or old shapes refuse."""
    try:
        decoded = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RegistryValidationError("export provenance manifest is not valid UTF-8 JSON") from exc
    try:
        json.loads(decoded, object_pairs_hook=_json_object_without_duplicates)
    except (json.JSONDecodeError, _DuplicateJsonKeyError) as exc:
        raise RegistryValidationError(f"export provenance manifest is invalid JSON: {exc}") from exc
    try:
        # Pydantic's JSON boundary deliberately accepts JSON arrays for the
        # frozen tuple fields. The preliminary stdlib parse above is retained
        # solely to reject duplicate object keys before this typed parse.
        manifest = ExportFragmentProvenanceManifest.model_validate_json(raw)
    except ValidationError as exc:
        raise RegistryValidationError(f"export provenance manifest violates the current contract: {exc}") from exc
    if raw != export_fragment_provenance_manifest_json_bytes(manifest):
        raise RegistryValidationError("export provenance manifest is not canonical JSON")
    return manifest


def _validate_generation_scope(
    *,
    intermediate: RecordDesignIntermediate,
    semantic_map: SemanticMap,
    target: ExportFragmentTarget,
) -> None:
    if semantic_map.modelo != target.modelo:
        raise RegistryValidationError(
            f"semantic-map modelo {semantic_map.modelo!r} does not match generation target {target.modelo!r}",
        )
    if intermediate.source.design_epoch != target.design_epoch:
        raise RegistryValidationError(
            f"record-design epoch {intermediate.source.design_epoch!r} does not match generation target "
            f"{target.design_epoch!r}",
        )
    if semantic_map.design_epoch != target.design_epoch:
        raise RegistryValidationError(
            f"semantic-map epoch {semantic_map.design_epoch!r} does not match generation target "
            f"{target.design_epoch!r}",
        )


def _normalise_semantic_map_entry(payload: Mapping[str, object]) -> dict[str, object]:
    _require_exact_keys(payload, _SEMANTIC_MAP_ENTRY_KEYS, subject="semantic-map entry")
    anchor = _as_object(payload["anchor"], subject="semantic-map anchor")
    _require_exact_keys(anchor, _SEMANTIC_MAP_ANCHOR_KEYS, subject="semantic-map anchor")
    return {
        "anchor": {
            "sheet": anchor["sheet"],
            "source_row": anchor["source_row"],
            "source_cell": anchor["source_cell"],
            "ordinal": anchor["ordinal"],
            "record_identity": anchor["record_identity"],
        },
        "export_field_id": payload["export_field_id"],
        "kind": payload["kind"],
        "casilla_id": payload["casilla_id"],
        "binding": payload["binding"],
        "literal": payload["literal"],
        "header_key": payload["header_key"],
        "draft_attribute": payload["draft_attribute"],
        "computed_key": payload["computed_key"],
        "legal_refs": _sorted_strings(payload["legal_refs"], subject="semantic-map legal_refs"),
        "source_refs": _sorted_strings(payload["source_refs"], subject="semantic-map source_refs"),
    }


def _semantic_entry_sort_key(payload: Mapping[str, object]) -> tuple[str, int, str, int, str, str]:
    anchor = _as_object(payload["anchor"], subject="normalised semantic-map anchor")
    source_cell = anchor["source_cell"]
    return (
        _as_string(anchor["sheet"], subject="semantic-map anchor sheet"),
        _as_int(anchor["source_row"], subject="semantic-map anchor source_row"),
        "" if source_cell is None else _as_string(source_cell, subject="semantic-map anchor source_cell"),
        _as_int(anchor["ordinal"], subject="semantic-map anchor ordinal"),
        _as_string(anchor["record_identity"], subject="semantic-map anchor record_identity"),
        _as_string(payload["export_field_id"], subject="semantic-map export_field_id"),
    )


def _normalise_semantic_map_record(payload: Mapping[str, object]) -> dict[str, object]:
    _require_exact_keys(payload, _SEMANTIC_MAP_RECORD_KEYS, subject="semantic-map record")
    return {
        "sheet": _as_string(payload["sheet"], subject="semantic-map record sheet"),
        "record_identity": _as_string(
            payload["record_identity"],
            subject="semantic-map record record_identity",
        ),
        "export_record_id": _as_string(
            payload["export_record_id"],
            subject="semantic-map record export_record_id",
        ),
        "record_type": _as_string(payload["record_type"], subject="semantic-map record record_type"),
    }


def _semantic_record_sort_key(payload: Mapping[str, object]) -> tuple[str, str, str, str]:
    return (
        _as_string(payload["sheet"], subject="semantic-map record sheet"),
        _as_string(payload["record_identity"], subject="semantic-map record record_identity"),
        _as_string(payload["export_record_id"], subject="semantic-map record export_record_id"),
        _as_string(payload["record_type"], subject="semantic-map record record_type"),
    )


def _normalise_loader_record(payload: Mapping[str, object]) -> dict[str, object]:
    _require_exact_keys(payload, _RECORD_KEYS, subject="loader export record")
    fields = [
        _normalise_loader_field(item) for item in _as_object_list(payload["fields"], subject="loader record fields")
    ]
    fields.sort(key=_loader_field_sort_key)
    row_fields = _as_object(payload["row_field_casilla_ids"], subject="loader row-field casilla ids")
    discriminator = payload["discriminator"]
    normalised_discriminator: dict[str, object] | None = None
    if discriminator is not None:
        discriminator_payload = _as_object(discriminator, subject="loader record discriminator")
        _require_exact_keys(discriminator_payload, _DISCRIMINATOR_KEYS, subject="loader record discriminator")
        normalised_discriminator = {
            "offset": discriminator_payload["offset"],
            "length": discriminator_payload["length"],
            "requires": discriminator_payload["requires"],
        }
    return {
        "id": payload["id"],
        "record_type": payload["record_type"],
        "order": payload["order"],
        "encoding": payload["encoding"],
        "line_ending": payload["line_ending"],
        "required": payload["required"],
        "repeat": payload["repeat"],
        "binding_record": payload["binding_record"],
        "row_field_casilla_ids": {key: row_fields[key] for key in sorted(row_fields)},
        "discriminator": normalised_discriminator,
        "requires_positive_casilla_id": payload["requires_positive_casilla_id"],
        "fields": fields,
    }


def _normalise_loader_field(payload: Mapping[str, object]) -> dict[str, object]:
    _require_exact_keys(payload, _FIELD_KEYS, subject="loader export field")
    return {
        "id": payload["id"],
        "offset": payload["offset"],
        "length": payload["length"],
        "kind": payload["kind"],
        "casilla_id": payload["casilla_id"],
        "binding": payload["binding"],
        "literal": payload["literal"],
        "header_key": payload["header_key"],
        "draft_attribute": payload["draft_attribute"],
        "computed_key": payload["computed_key"],
        "data_type": payload["data_type"],
        "required": payload["required"],
        "padding": payload["padding"],
        "justification": payload["justification"],
        "date_format": payload["date_format"],
        "decimals": payload["decimals"],
        "signed": payload["signed"],
        "legal_refs": _sorted_strings(payload["legal_refs"], subject="loader field legal_refs"),
        "source_refs": _sorted_strings(payload["source_refs"], subject="loader field source_refs"),
    }


def _loader_record_sort_key(payload: Mapping[str, object]) -> tuple[int, str]:
    return (
        _as_int(payload["order"], subject="loader record order"),
        _as_string(payload["id"], subject="loader record id"),
    )


def _loader_field_sort_key(payload: Mapping[str, object]) -> tuple[int, str]:
    offset = payload["offset"]
    return (
        -1 if offset is None else _as_int(offset, subject="loader field offset"),
        _as_string(payload["id"], subject="loader field id"),
    )


def _normalise_dictionary_override(payload: Mapping[str, object]) -> dict[str, object]:
    _require_exact_keys(payload, _DICTIONARY_OVERRIDE_KEYS, subject="loader dictionary override")
    return {
        "field_id": payload["field_id"],
        "path": payload["path"],
        "reason": payload["reason"],
    }


def _require_exact_keys(payload: Mapping[str, object], expected: frozenset[str], *, subject: str) -> None:
    actual = frozenset(payload)
    if actual == expected:
        return
    missing = sorted(expected - actual)
    unknown = sorted(actual - expected)
    raise RegistryValidationError(
        f"{subject} schema drift: missing={missing!r}, unknown={unknown!r}; review and version the normaliser",
    )


def _as_object(value: object, *, subject: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise RegistryValidationError(f"{subject} schema drift: expected object")
    raw_mapping = cast(Mapping[object, object], value)
    result: dict[str, object] = {}
    for raw_key, raw_value in raw_mapping.items():
        if not isinstance(raw_key, str):
            raise RegistryValidationError(f"{subject} schema drift: expected string object keys")
        result[raw_key] = raw_value
    return result


def _as_object_list(value: object, *, subject: str) -> list[Mapping[str, object]]:
    if not isinstance(value, list):
        raise RegistryValidationError(f"{subject} schema drift: expected array")
    return [_as_object(item, subject=subject) for item in cast(list[object], value)]


def _sorted_strings(value: object, *, subject: str) -> list[str]:
    if not isinstance(value, list):
        raise RegistryValidationError(f"{subject} schema drift: expected string array")
    items = cast(list[object], value)
    if any(not isinstance(item, str) for item in items):
        raise RegistryValidationError(f"{subject} schema drift: expected string array")
    return sorted(cast(list[str], items))


def _as_string(value: object, *, subject: str) -> str:
    if not isinstance(value, str):
        raise RegistryValidationError(f"{subject} schema drift: expected string")
    return value


def _as_int(value: object, *, subject: str) -> int:
    if not isinstance(value, int):
        raise RegistryValidationError(f"{subject} schema drift: expected integer")
    return value


class _DuplicateJsonKeyError(ValueError):
    """Raw JSON contained an ambiguous duplicate object key."""


def _json_object_without_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateJsonKeyError(f"duplicate object key {key!r}")
        result[key] = value
    return result
