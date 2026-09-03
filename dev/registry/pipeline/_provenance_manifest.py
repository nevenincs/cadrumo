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
from typing import Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from cadrumo.core.atomic_write import atomic_write_publish_once_bytes
from cadrumo.core.directory_scan import iter_directory
from cadrumo.core.hashing import canonical_json_bytes, content_hash_hex, hash_file
from cadrumo.core.link_safety import is_link_like
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.ids import (
    ModeloId,
    RevisionId,
    SourceRefId,
)
from cadrumo.domain.calculations.registry.schema_exports import ExportFieldDefinition, ExportLayoutDefinition

from ._record_design_ir import (
    RECORD_DESIGN_INTERMEDIATE_SCHEMA_VERSION,
    RecordDesignIntermediateField,
)
from ._render_profile import (
    RENDER_PROFILE_SCHEMA_VERSION,
    RenderProfile,
    RenderProfileSourceEvidence,
    render_profile_digest,
    validate_render_profile,
)
from ._semantic_map import SemanticMap, SemanticMapEntry
from ._semantic_map_join import JoinedRecordDesign
from ._variable_envelope import FilingEnvelopeProvenance

__all__ = [
    "EXPORT_FRAGMENT_GENERATOR_SCHEMA_VERSION",
    "EXPORT_FRAGMENT_PROVENANCE_FILENAME",
    "EXPORT_FRAGMENT_PROVENANCE_SCHEMA_VERSION",
    "EXPORT_RENDER_NORMALIZATION_SCHEMA_VERSION",
    "LEGACY_EXPORT_FRAGMENT_PROVENANCE_FILENAME",
    "SHA256_PATTERN",
    "ExportFieldDerivation",
    "ExportFieldDerivationCode",
    "ExportFragmentOutputDigest",
    "ExportFragmentProvenanceManifest",
    "ExportFragmentTarget",
    "build_export_fragment_provenance_manifest",
    "collect_export_fragment_output_digests",
    "emit_export_fragment_provenance_manifest",
    "export_fragment_provenance_manifest_json_bytes",
    "export_fragment_provenance_path",
    "load_export_fragment_provenance_manifest",
    "loader_semantic_digest",
    "normalised_loader_semantics",
    "semantic_map_digest",
    "verify_export_fragment_provenance_manifest",
]


EXPORT_FRAGMENT_PROVENANCE_SCHEMA_VERSION: Final[int] = 5
"""Current wire schema for the internal non-loader provenance manifest."""

EXPORT_FRAGMENT_GENERATOR_SCHEMA_VERSION: Final[int] = 6
"""Current generator contract recorded by every provenance manifest."""

EXPORT_RENDER_NORMALIZATION_SCHEMA_VERSION: Final[int] = 2
"""Reviewed parser-to-wire normalization contract recorded for every field."""

_LOADER_SEMANTIC_SCHEMA_VERSION: Final[int] = 6
#: The shape of a lowercase hex digest, stated where digests are validated.
#: The publication module carried an identical copy: two modules deciding
#: separately what a digest looks like is one relaxation away from one of
#: them accepting a value the other refuses.
SHA256_PATTERN: Final[str] = r"^[0-9a-f]{64}$"
EXPORT_FRAGMENT_PROVENANCE_FILENAME: Final[str] = "_generation.provenance.json"
"""Internal JSON member ignored by the TOML-only registry loader."""

#: The pre-rename filename, kept so both the reader that skips it and the
#: publisher that removes it name the same string. It was declared twice
#: under two different names, which is the one shape a reader cannot grep:
#: searching for either name finds half the uses.
LEGACY_EXPORT_FRAGMENT_PROVENANCE_FILENAME: Final[str] = "export.provenance.json"

_SEMANTIC_MAP_KEYS: Final[frozenset[str]] = frozenset(
    {"modelo", "design_epoch", "source_ref", "source_sha256", "records", "entries", "variable_envelopes"},
)
_SEMANTIC_MAP_RECORD_KEYS: Final[frozenset[str]] = frozenset(
    {
        "sheet",
        "record_identity",
        "export_record_id",
        "record_type",
        "required",
        "repeat",
        "binding_record",
        "row_field_casilla_ids",
        "discriminator",
    },
)
_SEMANTIC_MAP_ENTRY_KEYS: Final[frozenset[str]] = frozenset(
    {
        "anchor",
        "export_field_id",
        "kind",
        "casilla_id",
        "binding",
        "literal",
        "producer_key",
        "projection_ref",
        "draft_attribute",
        "computed_key",
        "legal_refs",
        "source_refs",
    },
)
#: ``ordinal_absent`` joined this set when the parser gained the ability to
#: read a row AEAT printed with NO ordinal -- a gap-filled position whose
#: naturaleza cell was empty. It is part of the anchor identity, so it is
#: normalised into the digest rather than dropped: two anchors differing only
#: in whether the design printed an ordinal are different anchors.
_SEMANTIC_MAP_ANCHOR_KEYS: Final[frozenset[str]] = frozenset(
    {"sheet", "source_row", "source_cell", "ordinal", "ordinal_absent", "record_identity"},
)
_VARIABLE_ENVELOPE_KEYS: Final[frozenset[str]] = frozenset(
    {
        "source_ref",
        "source_sha256",
        "record_identity",
        "prefix_fields",
        "body_anchor",
        "body_record_ids",
        "closer_anchor",
        "total_anchor",
    },
)
_ENVELOPE_PREFIX_FIELD_KEYS: Final[frozenset[str]] = frozenset({"role", "anchor"})
_ENVELOPE_TOTAL_ANCHOR_KEYS: Final[frozenset[str]] = frozenset({"source_row", "source_cell", "label", "length"})
_LAYOUT_KEYS: Final[frozenset[str]] = frozenset(
    {
        "id",
        "format",
        "dictionary_source_ref",
        "source_refs",
        "legal_refs",
        "records",
        "filing_envelope",
        "auxiliary_envelope_header",
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
        "producer_key",
        "projection_ref",
        "draft_attribute",
        "computed_key",
        "data_type",
        "required",
        "padding",
        "justification",
        "date_format",
        "decimals",
        "signed",
        "value_policy",
        "allowed_values",
        "legal_refs",
        "source_refs",
    },
)
_DISCRIMINATOR_KEYS: Final[frozenset[str]] = frozenset({"offset", "length", "requires"})
_DICTIONARY_OVERRIDE_KEYS: Final[frozenset[str]] = frozenset({"field_id", "path", "reason"})

type ExportFieldDerivationCode = Literal[
    "filler-v1",
    "literal-exact-v1",
    "numeric-date-aaaammdd-v1",
    "numeric-date-ddmmaaaa-v1",
    "numeric-decimal-v1",
    "numeric-ejercicio-aaaa-v1",
    "numeric-enumeration-v1",
    "numeric-integer-v1",
    "text-a-v1",
    "text-an-v1",
    "render-profile-width-17-v1",
    "render-profile-singleton-v1",
]


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
    sha256: str = Field(pattern=SHA256_PATTERN)

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
        if not value.endswith(".toml"):
            raise ValueError("output digest path must refer to a generated TOML file")
        return PurePosixPath(value).as_posix()


class ExportFieldDerivation(_StrictModel):
    """Complete evidence for one rendered field's reviewed wire normalization.

    The parser coordinate and semantic-map meaning are retained beside the exact
    emitted field.  A generic or unreviewed normalization code cannot enter a
    generated manifest: adding a supported form requires extending this closed
    contract and its schema-version review.
    """

    export_record_id: str = Field(min_length=1)
    parser_field: RecordDesignIntermediateField
    semantic_entry: SemanticMapEntry
    field: ExportFieldDefinition
    normalization_schema_version: int = Field(ge=1)
    derivation_code: ExportFieldDerivationCode

    @model_validator(mode="after")
    def _require_exact_authority_and_emitted_field(self) -> ExportFieldDerivation:
        parser_anchor = self.parser_field
        semantic_anchor = self.semantic_entry.anchor
        if (
            parser_anchor.sheet,
            parser_anchor.source_row,
            parser_anchor.source_cell,
            parser_anchor.ordinal,
            parser_anchor.record_identity,
        ) != (
            semantic_anchor.sheet,
            semantic_anchor.source_row,
            semantic_anchor.source_cell,
            semantic_anchor.ordinal,
            semantic_anchor.record_identity,
        ):
            raise ValueError("field derivation requires the same complete parser and semantic-map anchor")
        if self.normalization_schema_version != EXPORT_RENDER_NORMALIZATION_SCHEMA_VERSION:
            raise ValueError(
                "normalization schema drift: derivation records "
                f"{self.normalization_schema_version}, expected {EXPORT_RENDER_NORMALIZATION_SCHEMA_VERSION}",
            )
        if self.field.id != self.semantic_entry.export_field_id:
            raise ValueError("field derivation emitted id does not match semantic-map entry")
        if self.field.offset != self.parser_field.offset or self.field.length != self.parser_field.length:
            raise ValueError("field derivation emitted coordinates do not match parser field")
        for attribute in (
            "kind",
            "casilla_id",
            "binding",
            "literal",
            "producer_key",
            "projection_ref",
            "draft_attribute",
            "computed_key",
            "legal_refs",
            "source_refs",
        ):
            if getattr(self.field, attribute) != getattr(self.semantic_entry, attribute):
                raise ValueError(f"field derivation emitted {attribute} does not match semantic-map entry")
        return self


class ExportFragmentProvenanceManifest(_StrictModel):
    """Adjacent, canonical, non-loader provenance for one generated revision.

    No timestamp, host path, temporary directory, or mutable legacy-tree value
    participates in this contract.  Every required version is explicit so an
    old manifest cannot be mistaken for a current parser or generator schema.
    """

    manifest_schema_version: int = Field(ge=1)
    source_ref: SourceRefId
    source_sha256: str = Field(pattern=SHA256_PATTERN)
    parser_schema_version: int = Field(ge=1)
    generator_schema_version: int = Field(ge=1)
    semantic_map_sha256: str = Field(pattern=SHA256_PATTERN)
    render_profile_schema_version: int = Field(ge=1)
    render_profile_sha256: str = Field(pattern=SHA256_PATTERN)
    modelo: ModeloId
    revision_id: RevisionId
    design_epoch: str = Field(min_length=1)
    loader_semantic_sha256: str = Field(pattern=SHA256_PATTERN)
    output_files: tuple[ExportFragmentOutputDigest, ...] = Field(min_length=1)
    field_derivations: tuple[ExportFieldDerivation, ...] = Field(min_length=1)
    variable_envelope_contract: FilingEnvelopeProvenance | None = None

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
        if self.render_profile_schema_version != RENDER_PROFILE_SCHEMA_VERSION:
            raise ValueError(
                "render-profile schema drift: manifest records "
                f"{self.render_profile_schema_version}, expected {RENDER_PROFILE_SCHEMA_VERSION}",
            )
        paths = tuple(item.relative_path for item in self.output_files)
        if paths != tuple(sorted(paths)):
            raise ValueError("provenance output files must be sorted by relative path")
        if len(set(paths)) != len(paths):
            raise ValueError("provenance output files must not contain duplicate relative paths")
        field_keys = tuple((item.export_record_id, str(item.field.id)) for item in self.field_derivations)
        if field_keys != tuple(sorted(field_keys)):
            raise ValueError("provenance field derivations must be sorted by record and field id")
        if len(set(field_keys)) != len(field_keys):
            raise ValueError("provenance field derivations must not contain duplicate emitted fields")
        return self


def export_fragment_provenance_path(export_directory: Path) -> Path:
    """Return the internal JSON attestation the TOML-only loader never consumes."""
    return export_directory / EXPORT_FRAGMENT_PROVENANCE_FILENAME


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
    variable_envelopes = _as_object_list(payload["variable_envelopes"], subject="semantic-map variable envelopes")
    normalised_variable_envelopes = [_normalise_variable_envelope_contract(envelope) for envelope in variable_envelopes]
    normalised_variable_envelopes.sort(
        key=lambda envelope: _as_string(envelope["record_identity"], subject="envelope id"),
    )
    return content_hash_hex(
        {
            "modelo": payload["modelo"],
            "design_epoch": payload["design_epoch"],
            "source_ref": payload["source_ref"],
            "source_sha256": payload["source_sha256"],
            "records": normalised_records,
            "entries": normalised_entries,
            "variable_envelopes": normalised_variable_envelopes,
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
    projected: dict[str, object] = {
        "loader_semantic_schema_version": _LOADER_SEMANTIC_SCHEMA_VERSION,
        "id": payload["id"],
        "format": payload["format"],
        "dictionary_source_ref": payload["dictionary_source_ref"],
        "source_refs": _sorted_strings(payload["source_refs"], subject="loader layout source_refs"),
        "legal_refs": _sorted_strings(payload["legal_refs"], subject="loader layout legal_refs"),
        "records": records,
        "filing_envelope": payload["filing_envelope"],
        "dictionary_path_overrides": overrides,
        "aux_idioma": payload["aux_idioma"],
        "aux_version": payload["aux_version"],
    }
    # Projected only when declared, so a layout without the member attests
    # byte-identical semantics to the projection that preceded it.
    if payload["auxiliary_envelope_header"] is not None:
        projected["auxiliary_envelope_header"] = payload["auxiliary_envelope_header"]
    return projected


def loader_semantic_digest(loaded_layout: ExportLayoutDefinition) -> str:
    """Return the canonical digest of a real loader-materialised export layout."""
    return content_hash_hex(normalised_loader_semantics(loaded_layout))


def collect_export_fragment_output_digests(export_root: Path) -> tuple[ExportFragmentOutputDigest, ...]:
    """Hash every real regular file below one generated export root.

    Symlinks and junctions are refused before hashing so no manifest can attest
    to data outside the candidate tree. This function only observes a supplied
    tree; it does not render, create, replace, or publish one.
    """
    if is_link_like(export_root):
        raise RegistryValidationError(f"export provenance refuses linked export root: {export_root}")
    if not export_root.is_dir():
        raise FileNotFoundError(export_root)
    resolved_root = export_root.resolve()
    entries: list[ExportFragmentOutputDigest] = []
    for candidate in sorted(iter_directory(export_root, recursive=True), key=lambda path: path.as_posix()):
        if is_link_like(candidate):
            raise RegistryValidationError(f"export provenance refuses linked output path: {candidate}")
        if not candidate.is_file():
            continue
        relative_path = PurePosixPath(*candidate.relative_to(export_root).parts).as_posix()
        if candidate == export_root / EXPORT_FRAGMENT_PROVENANCE_FILENAME:
            continue
        if candidate.name == LEGACY_EXPORT_FRAGMENT_PROVENANCE_FILENAME:
            raise RegistryValidationError(
                f"export provenance refuses stale sibling-era manifest under generated export root: {relative_path}",
            )
        if candidate.suffix != ".toml":
            raise RegistryValidationError(
                f"export provenance refuses non-TOML output under generated export root: {relative_path}",
            )
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
    joined: JoinedRecordDesign,
    semantic_map: SemanticMap,
    target: ExportFragmentTarget,
    loaded_layout: ExportLayoutDefinition,
    export_root: Path,
    field_derivations: tuple[ExportFieldDerivation, ...],
    render_profile: RenderProfile,
    render_profile_source_evidence: RenderProfileSourceEvidence,
) -> ExportFragmentProvenanceManifest:
    """Assemble provenance only from the exact joined and rendered authorities."""
    _validate_generation_scope(
        joined=joined,
        semantic_map=semantic_map,
        target=target,
        render_profile=render_profile,
        render_profile_source_evidence=render_profile_source_evidence,
    )
    manifest = ExportFragmentProvenanceManifest(
        manifest_schema_version=EXPORT_FRAGMENT_PROVENANCE_SCHEMA_VERSION,
        source_ref=joined.source.source_ref,
        source_sha256=joined.source.source_sha256,
        parser_schema_version=RECORD_DESIGN_INTERMEDIATE_SCHEMA_VERSION,
        generator_schema_version=EXPORT_FRAGMENT_GENERATOR_SCHEMA_VERSION,
        semantic_map_sha256=semantic_map_digest(semantic_map),
        render_profile_schema_version=RENDER_PROFILE_SCHEMA_VERSION,
        render_profile_sha256=render_profile_digest(render_profile, render_profile_source_evidence),
        modelo=target.modelo,
        revision_id=target.revision_id,
        design_epoch=target.design_epoch,
        loader_semantic_sha256=loader_semantic_digest(loaded_layout),
        output_files=collect_export_fragment_output_digests(export_root),
        field_derivations=tuple(
            sorted(field_derivations, key=lambda item: (item.export_record_id, str(item.field.id)))
        ),
        variable_envelope_contract=_filing_envelope_provenance(
            joined,
            loaded_layout=loaded_layout,
        ),
    )
    _require_field_derivations_match_layout(manifest.field_derivations, loaded_layout)
    return manifest


def emit_export_fragment_provenance_manifest(
    *,
    joined: JoinedRecordDesign,
    semantic_map: SemanticMap,
    target: ExportFragmentTarget,
    loaded_layout: ExportLayoutDefinition,
    export_root: Path,
    field_derivations: tuple[ExportFieldDerivation, ...],
    render_profile: RenderProfile,
    render_profile_source_evidence: RenderProfileSourceEvidence,
) -> ExportFragmentProvenanceManifest:
    """Write one complete canonical sibling manifest after a fresh tree renders.

    This only emits attestation into an isolated, un-published target.  Tree
    validation and atomic target publication remain later generator boundaries.
    """
    manifest = build_export_fragment_provenance_manifest(
        joined=joined,
        semantic_map=semantic_map,
        target=target,
        loaded_layout=loaded_layout,
        export_root=export_root,
        field_derivations=field_derivations,
        render_profile=render_profile,
        render_profile_source_evidence=render_profile_source_evidence,
    )
    manifest_path = export_fragment_provenance_path(export_root)
    if is_link_like(manifest_path):
        raise RegistryValidationError(f"export provenance refuses linked manifest target: {manifest_path}")
    if manifest_path.exists():
        raise RegistryValidationError(f"export provenance manifest already exists: {manifest_path}")
    _write_canonical_manifest_atomically(manifest_path, export_fragment_provenance_manifest_json_bytes(manifest))
    return manifest


def verify_export_fragment_provenance_manifest(
    *,
    export_root: Path,
    joined: JoinedRecordDesign,
    semantic_map: SemanticMap,
    target: ExportFragmentTarget,
    loaded_layout: ExportLayoutDefinition,
    field_derivations: tuple[ExportFieldDerivation, ...],
    render_profile: RenderProfile,
    render_profile_source_evidence: RenderProfileSourceEvidence,
) -> ExportFragmentProvenanceManifest:
    """Refuse current-authority, file, loader-semantic, or derivation drift."""
    manifest_path = export_fragment_provenance_path(export_root)
    if is_link_like(manifest_path):
        raise RegistryValidationError(f"export provenance refuses linked manifest: {manifest_path}")
    if not manifest_path.is_file():
        raise RegistryValidationError(f"export provenance manifest is missing: {manifest_path}")
    manifest = load_export_fragment_provenance_manifest(manifest_path.read_bytes())
    _require_manifest_matches_current_authorities(
        manifest,
        joined=joined,
        semantic_map=semantic_map,
        target=target,
        render_profile=render_profile,
        render_profile_source_evidence=render_profile_source_evidence,
        loaded_layout=loaded_layout,
    )
    actual_outputs = collect_export_fragment_output_digests(export_root)
    if manifest.output_files != actual_outputs:
        raise RegistryValidationError("export provenance output-file digests do not match generated tree")
    actual_loader_digest = loader_semantic_digest(loaded_layout)
    if manifest.loader_semantic_sha256 != actual_loader_digest:
        raise RegistryValidationError("export provenance loader-semantic digest does not match generated tree")
    _require_field_derivations_match_layout(manifest.field_derivations, loaded_layout)
    expected_derivations = tuple(
        sorted(field_derivations, key=lambda item: (item.export_record_id, str(item.field.id)))
    )
    if manifest.field_derivations != expected_derivations:
        raise RegistryValidationError("export provenance field derivations do not match the rendered tree")
    return manifest


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
    joined: JoinedRecordDesign,
    semantic_map: SemanticMap,
    target: ExportFragmentTarget,
    render_profile: RenderProfile,
    render_profile_source_evidence: RenderProfileSourceEvidence,
) -> None:
    validate_render_profile(render_profile, joined, render_profile_source_evidence)
    if joined.modelo != target.modelo:
        raise RegistryValidationError(
            f"joined modelo {joined.modelo!r} does not match generation target {target.modelo!r}",
        )
    if semantic_map.modelo != target.modelo:
        raise RegistryValidationError(
            f"semantic-map modelo {semantic_map.modelo!r} does not match generation target {target.modelo!r}",
        )
    if joined.source.design_epoch != target.design_epoch:
        raise RegistryValidationError(
            f"record-design epoch {joined.source.design_epoch!r} does not match generation target "
            f"{target.design_epoch!r}",
        )
    if semantic_map.design_epoch != target.design_epoch:
        raise RegistryValidationError(
            f"semantic-map epoch {semantic_map.design_epoch!r} does not match generation target "
            f"{target.design_epoch!r}",
        )
    if semantic_map.source_ref != joined.source.source_ref:
        raise RegistryValidationError(
            f"semantic-map source {semantic_map.source_ref!r} does not match joined source "
            f"{joined.source.source_ref!r}",
        )
    if semantic_map.source_sha256 != joined.source.source_sha256:
        raise RegistryValidationError("semantic-map SHA-256 does not match joined official source")
    if joined.variable_envelope_contract is not None and target.revision_id != joined.revision_id:
        raise RegistryValidationError(
            f"typed filing-envelope target revision {target.revision_id!r} does not match the selected "
            f"snapshot revision {joined.revision_id!r}",
        )
    if tuple(
        sorted(
            (field.semantic_entry for field in joined.fields),
            key=lambda entry: (
                entry.anchor.sheet,
                entry.anchor.source_row,
                "" if entry.anchor.source_cell is None else entry.anchor.source_cell,
                entry.anchor.ordinal,
                entry.anchor.record_identity,
                str(entry.export_field_id),
            ),
        )
    ) != tuple(
        sorted(
            semantic_map.entries,
            key=lambda entry: (
                entry.anchor.sheet,
                entry.anchor.source_row,
                "" if entry.anchor.source_cell is None else entry.anchor.source_cell,
                entry.anchor.ordinal,
                entry.anchor.record_identity,
                str(entry.export_field_id),
            ),
        )
    ):
        raise RegistryValidationError("joined fields do not attest the supplied complete semantic map")
    if tuple(
        sorted(
            (record.semantic_record for record in joined.records),
            key=lambda record: (
                record.sheet,
                record.record_identity,
                str(record.export_record_id),
                record.record_type,
            ),
        )
    ) != tuple(
        sorted(
            semantic_map.records,
            key=lambda record: (
                record.sheet,
                record.record_identity,
                str(record.export_record_id),
                record.record_type,
            ),
        )
    ):
        raise RegistryValidationError("joined records do not attest the supplied complete semantic map")


def _filing_envelope_provenance(
    joined: JoinedRecordDesign,
    *,
    loaded_layout: ExportLayoutDefinition,
) -> FilingEnvelopeProvenance | None:
    """Attest only the static envelope declaration generated into the layout."""
    joined_envelope = joined.variable_envelope_contract
    if joined_envelope is None:
        if loaded_layout.filing_envelope is not None:
            raise RegistryValidationError(
                "a generated filing-envelope declaration requires its typed reviewed semantic contract",
            )
        return None
    declaration = loaded_layout.filing_envelope
    if declaration is None:
        raise RegistryValidationError(
            "typed filing-envelope generation requires one static envelope declaration in the layout",
        )
    if joined.revision_id is None:
        raise RegistryValidationError(
            "typed filing-envelope generation requires the exact selected snapshot revision",
        )
    if (
        declaration.source_ref != joined_envelope.semantic.source_ref
        or declaration.source_sha256 != joined_envelope.semantic.source_sha256
    ):
        raise RegistryValidationError(
            "typed filing-envelope declaration does not retain the reviewed source identity",
        )
    if declaration.body_record_ids != joined_envelope.semantic.body_record_ids:
        raise RegistryValidationError(
            "typed filing-envelope declaration does not retain the reviewed body-record order",
        )
    return FilingEnvelopeProvenance(
        schema_version=2,
        revision_id=joined.revision_id,
        layout_id=loaded_layout.id,
        semantic_sha256=content_hash_hex(joined_envelope.semantic.model_dump(mode="json")),
        envelope=declaration,
        envelope_sha256=content_hash_hex(declaration.model_dump(mode="json")),
    )


def _require_manifest_matches_current_authorities(
    manifest: ExportFragmentProvenanceManifest,
    *,
    joined: JoinedRecordDesign,
    semantic_map: SemanticMap,
    target: ExportFragmentTarget,
    render_profile: RenderProfile,
    render_profile_source_evidence: RenderProfileSourceEvidence,
    loaded_layout: ExportLayoutDefinition,
) -> None:
    _validate_generation_scope(
        joined=joined,
        semantic_map=semantic_map,
        target=target,
        render_profile=render_profile,
        render_profile_source_evidence=render_profile_source_evidence,
    )
    expected = {
        "source_ref": joined.source.source_ref,
        "source_sha256": joined.source.source_sha256,
        "parser_schema_version": RECORD_DESIGN_INTERMEDIATE_SCHEMA_VERSION,
        "generator_schema_version": EXPORT_FRAGMENT_GENERATOR_SCHEMA_VERSION,
        "semantic_map_sha256": semantic_map_digest(semantic_map),
        "render_profile_schema_version": RENDER_PROFILE_SCHEMA_VERSION,
        "render_profile_sha256": render_profile_digest(render_profile, render_profile_source_evidence),
        "modelo": target.modelo,
        "revision_id": target.revision_id,
        "design_epoch": target.design_epoch,
    }
    mismatches = {
        name: (getattr(manifest, name), expected_value)
        for name, expected_value in expected.items()
        if getattr(manifest, name) != expected_value
    }
    if mismatches:
        raise RegistryValidationError(
            f"export provenance manifest does not match current generation authorities: {mismatches!r}",
        )
    expected_envelope = _filing_envelope_provenance(
        joined,
        loaded_layout=loaded_layout,
    )
    if manifest.variable_envelope_contract != expected_envelope:
        raise RegistryValidationError("export provenance variable-envelope authority does not match generation")


def _require_field_derivations_match_layout(
    field_derivations: tuple[ExportFieldDerivation, ...],
    loaded_layout: ExportLayoutDefinition,
) -> None:
    layout_fields = {
        (str(record.id), str(field.id)): field for record in loaded_layout.records for field in record.fields
    }
    derivation_fields = {(item.export_record_id, str(item.field.id)): item.field for item in field_derivations}
    if len(layout_fields) != len(tuple(field for record in loaded_layout.records for field in record.fields)):
        raise RegistryValidationError("loader export layout contains duplicate record and field identities")
    if len(derivation_fields) != len(field_derivations):
        raise RegistryValidationError("export provenance contains duplicate field derivations")
    if frozenset(derivation_fields) != frozenset(layout_fields):
        missing = sorted(
            f"{record_id}/{field_id}" for record_id, field_id in layout_fields.keys() - derivation_fields.keys()
        )
        unexpected = sorted(
            f"{record_id}/{field_id}" for record_id, field_id in derivation_fields.keys() - layout_fields.keys()
        )
        raise RegistryValidationError(
            f"export provenance derivations do not cover exactly the generated layout: "
            f"missing={missing!r}, unexpected={unexpected!r}",
        )
    for identity, expected_field in layout_fields.items():
        if derivation_fields[identity] != expected_field:
            raise RegistryValidationError(
                f"export provenance derivation does not match generated field {identity[0]!r}/{identity[1]!r}",
            )


def _write_canonical_manifest_atomically(path: Path, payload: bytes) -> None:
    """Publish the sibling evidence write-once, refusing a pre-existing target.

    Delegates to :func:`~cadrumo.core.atomic_write.atomic_write_publish_once_bytes`.
    The guarantee this writer needs -- a manifest that already exists means a
    second write, which is a bug rather than an update -- is that tier's
    contract: it publishes with :func:`os.link`, which fails with
    :exc:`FileExistsError` in one uninterruptible step instead of overwriting.

    An earlier revision open-coded the stage-fsync-replace sequence here and
    documented the duplication as deliberate, on two grounds: that no core tier
    refused an existing target, and that the atomic form needed hardlink support
    this project's network-share working tree could not provide. The second was
    asserted rather than measured, and is false. With it goes the first -- the
    core tier now exists and is built on exactly that primitive -- so what stood
    here was a parallel write path rather than a superset, and re-implementing a
    write path instead of delegating to the single-writer primitive is precisely
    what the architecture boundary forbids.

    The parent-directory precondition stays, because it is this module's
    contract rather than the writer's: a missing parent means the export tree
    was never built, which is a registry error, and the core tier would create
    the directory and mask it.

    Raises:
        RegistryValidationError: When the parent directory is missing, when the
            target already exists, or when the write otherwise fails.
    """
    if not path.parent.is_dir():
        raise RegistryValidationError(f"export provenance manifest parent is missing: {path.parent}")
    try:
        atomic_write_publish_once_bytes(path, payload)
    except FileExistsError as exc:
        raise RegistryValidationError(f"export provenance manifest already exists: {path}") from exc
    except OSError as exc:
        raise RegistryValidationError(f"cannot write export provenance manifest {path}: {exc}") from exc


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
            "ordinal_absent": anchor["ordinal_absent"],
            "record_identity": anchor["record_identity"],
        },
        "export_field_id": payload["export_field_id"],
        "kind": payload["kind"],
        "casilla_id": payload["casilla_id"],
        "binding": payload["binding"],
        "literal": payload["literal"],
        "producer_key": payload["producer_key"],
        "projection_ref": payload["projection_ref"],
        "draft_attribute": payload["draft_attribute"],
        "computed_key": payload["computed_key"],
        "legal_refs": _sorted_strings(payload["legal_refs"], subject="semantic-map legal_refs"),
        "source_refs": _sorted_strings(payload["source_refs"], subject="semantic-map source_refs"),
    }


def _normalise_variable_envelope_contract(payload: Mapping[str, object]) -> dict[str, object]:
    """Normalise the typed envelope contract without re-deriving its meaning."""
    _require_exact_keys(payload, _VARIABLE_ENVELOPE_KEYS, subject="variable envelope")
    prefix_fields = _as_object_list(payload["prefix_fields"], subject="variable envelope prefix fields")
    normalised_prefix_fields: list[dict[str, object]] = []
    for prefix_field in prefix_fields:
        _require_exact_keys(prefix_field, _ENVELOPE_PREFIX_FIELD_KEYS, subject="envelope prefix field")
        anchor = _as_object(prefix_field["anchor"], subject="envelope prefix anchor")
        _require_exact_keys(anchor, _SEMANTIC_MAP_ANCHOR_KEYS, subject="envelope prefix anchor")
        normalised_prefix_fields.append(
            {
                "role": prefix_field["role"],
                "anchor": {
                    "sheet": anchor["sheet"],
                    "source_row": anchor["source_row"],
                    "source_cell": anchor["source_cell"],
                    "ordinal": anchor["ordinal"],
                    "ordinal_absent": anchor["ordinal_absent"],
                    "record_identity": anchor["record_identity"],
                },
            },
        )
    body_anchor = _as_object(payload["body_anchor"], subject="envelope body anchor")
    closer_anchor = _as_object(payload["closer_anchor"], subject="envelope closer anchor")
    for subject, anchor in (("body", body_anchor), ("closer", closer_anchor)):
        _require_exact_keys(anchor, _SEMANTIC_MAP_ANCHOR_KEYS, subject=f"envelope {subject} anchor")
    total_anchor = _as_object(payload["total_anchor"], subject="envelope total anchor")
    _require_exact_keys(total_anchor, _ENVELOPE_TOTAL_ANCHOR_KEYS, subject="envelope total anchor")
    body_record_ids = _strings_in_order(payload["body_record_ids"], subject="envelope body record ids")
    return {
        "source_ref": payload["source_ref"],
        "source_sha256": payload["source_sha256"],
        "record_identity": payload["record_identity"],
        "prefix_fields": normalised_prefix_fields,
        "body_anchor": {
            "sheet": body_anchor["sheet"],
            "source_row": body_anchor["source_row"],
            "source_cell": body_anchor["source_cell"],
            "ordinal": body_anchor["ordinal"],
            "ordinal_absent": body_anchor["ordinal_absent"],
            "record_identity": body_anchor["record_identity"],
        },
        "body_record_ids": body_record_ids,
        "closer_anchor": {
            "sheet": closer_anchor["sheet"],
            "source_row": closer_anchor["source_row"],
            "source_cell": closer_anchor["source_cell"],
            "ordinal": closer_anchor["ordinal"],
            "ordinal_absent": closer_anchor["ordinal_absent"],
            "record_identity": closer_anchor["record_identity"],
        },
        "total_anchor": {
            "source_row": total_anchor["source_row"],
            "source_cell": total_anchor["source_cell"],
            "label": total_anchor["label"],
            "length": total_anchor["length"],
        },
    }


def _semantic_entry_sort_key(payload: Mapping[str, object]) -> tuple[str, int, str, str, str, str]:
    anchor = _as_object(payload["anchor"], subject="normalised semantic-map anchor")
    source_cell = anchor["source_cell"]
    ordinal = anchor["ordinal"]
    return (
        _as_string(anchor["sheet"], subject="semantic-map anchor sheet"),
        _as_int(anchor["source_row"], subject="semantic-map anchor source_row"),
        "" if source_cell is None else _as_string(source_cell, subject="semantic-map anchor source_cell"),
        "" if ordinal is None else _as_string(ordinal, subject="semantic-map anchor ordinal"),
        _as_string(anchor["record_identity"], subject="semantic-map anchor record_identity"),
        _as_string(payload["export_field_id"], subject="semantic-map export_field_id"),
    )


def _normalise_semantic_map_record(payload: Mapping[str, object]) -> dict[str, object]:
    _require_exact_keys(payload, _SEMANTIC_MAP_RECORD_KEYS, subject="semantic-map record")
    discriminator = payload["discriminator"]
    normalised_discriminator: dict[str, object] | None = None
    if discriminator is not None:
        discriminator_payload = _as_object(discriminator, subject="semantic-map record discriminator")
        _require_exact_keys(discriminator_payload, _DISCRIMINATOR_KEYS, subject="semantic-map record discriminator")
        normalised_discriminator = {
            "offset": discriminator_payload["offset"],
            "length": discriminator_payload["length"],
            "requires": discriminator_payload["requires"],
        }
    normalised: dict[str, object] = {
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
        "required": _as_bool(payload["required"], subject="semantic-map record required"),
        "repeat": _as_optional_string(payload["repeat"], subject="semantic-map record repeat"),
    }
    # Adding an optional semantic-map field must not invalidate every existing
    # generated tree whose authored meaning did not use it. A present rule is
    # attested; absence retains the previous canonical representation.
    if normalised_discriminator is not None:
        normalised["discriminator"] = normalised_discriminator
    binding_record = payload["binding_record"]
    if binding_record is not None:
        normalised["binding_record"] = _as_string(binding_record, subject="semantic-map record binding_record")
    row_field_casilla_ids = _as_sorted_string_pairs(
        payload["row_field_casilla_ids"],
        subject="semantic-map record row_field_casilla_ids",
    )
    if row_field_casilla_ids:
        normalised["row_field_casilla_ids"] = row_field_casilla_ids
    return normalised


def _semantic_record_sort_key(payload: Mapping[str, object]) -> tuple[str, str, str, str, str]:
    return (
        _as_string(payload["sheet"], subject="semantic-map record sheet"),
        _as_string(payload["record_identity"], subject="semantic-map record record_identity"),
        _as_string(payload["export_record_id"], subject="semantic-map record export_record_id"),
        _as_string(payload["record_type"], subject="semantic-map record record_type"),
        _as_optional_string(payload["repeat"], subject="semantic-map record repeat") or "",
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
        "producer_key": payload["producer_key"],
        "projection_ref": payload["projection_ref"],
        "draft_attribute": payload["draft_attribute"],
        "computed_key": payload["computed_key"],
        "data_type": payload["data_type"],
        "required": payload["required"],
        "padding": payload["padding"],
        "justification": payload["justification"],
        "date_format": payload["date_format"],
        "decimals": payload["decimals"],
        "signed": payload["signed"],
        "value_policy": payload["value_policy"],
        "allowed_values": payload["allowed_values"],
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


def _as_sorted_string_pairs(value: object, *, subject: str) -> list[list[str]]:
    """Project a carried mapping (dumped as two-element pairs) in a stable order."""
    if not isinstance(value, list):
        raise RegistryValidationError(f"{subject} schema drift: expected pair array")
    pairs: list[list[str]] = []
    for item in cast(list[object], value):
        if not isinstance(item, list):
            raise RegistryValidationError(f"{subject} schema drift: expected two-element pairs")
        members = cast(list[object], item)
        if len(members) != 2:
            raise RegistryValidationError(f"{subject} schema drift: expected two-element pairs")
        pairs.append([_as_string(members[0], subject=subject), _as_string(members[1], subject=subject)])
    return sorted(pairs)


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


def _strings_in_order(value: object, *, subject: str) -> list[str]:
    """Validate a string array while retaining semantic sequence order."""
    if not isinstance(value, list):
        raise RegistryValidationError(f"{subject} schema drift: expected string array")
    items = cast(list[object], value)
    if any(not isinstance(item, str) for item in items):
        raise RegistryValidationError(f"{subject} schema drift: expected string array")
    return cast(list[str], items)


def _as_string(value: object, *, subject: str) -> str:
    if not isinstance(value, str):
        raise RegistryValidationError(f"{subject} schema drift: expected string")
    return value


def _as_optional_string(value: object, *, subject: str) -> str | None:
    if value is None:
        return None
    return _as_string(value, subject=subject)


def _as_bool(value: object, *, subject: str) -> bool:
    if type(value) is not bool:
        raise RegistryValidationError(f"{subject} schema drift: expected boolean")
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
