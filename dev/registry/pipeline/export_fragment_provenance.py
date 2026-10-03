"""Attest generated export fragments and preserve their exact publication and read contract."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from cadrumo.core.atomic_write import hardened_staged_publication
from cadrumo.core.directory_scan import iter_directory
from cadrumo.core.fsync import fsync_parent_dir
from cadrumo.core.hashing import canonical_json_bytes, content_hash_hex, hash_file
from cadrumo.core.link_safety import is_link_like
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.ids import (
    ModeloId,
    RevisionId,
    SourceRefId,
)
from cadrumo.domain.calculations.registry.schema_exports import ExportFieldDefinition, ExportLayoutDefinition

from ..compiler.export_fragment_grammar import EXPORT_FRAGMENT_PROVENANCE_FILENAME
from .export_fragment_provenance_projection import (
    _LOADER_SEMANTIC_SCHEMA_VERSION,
    _omit_undeclared_field_keys,
)
from .export_fragment_provenance_projection import (
    loader_semantic_digest as _loader_semantic_digest,
)
from .export_fragment_provenance_projection import (
    semantic_map_digest as _semantic_map_digest,
)
from .generated_export_inheritance_model import GeneratedExportInheritance
from .joined_record_design import JoinedRecordDesign
from .pydantic_error_detail import validation_error_detail
from .record_design_intermediate import (
    RECORD_DESIGN_INTERMEDIATE_SCHEMA_VERSION,
    RecordDesignIntermediateField,
)
from .render_profile import render_profile_digest, validate_render_profile
from .render_profile_evidence import RenderProfileSourceEvidence
from .render_profile_loading import RENDER_PROFILE_SCHEMA_VERSION
from .render_profile_model import RenderProfile
from .semantic_map import SemanticMap, SemanticMapEntry
from .variable_envelope import FilingEnvelopeProvenance


def _publish_once_bytes(path: Path, payload: bytes, *, mode: int = 0o600) -> None:
    """Publish one development provenance payload without replacing an existing target."""
    with hardened_staged_publication(path, mode=mode) as staged:
        with staged.path.open("wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(staged.path, path)
        fsync_parent_dir(path)


EXPORT_FRAGMENT_PROVENANCE_SCHEMA_VERSION: Final[int] = 5
"""Current wire schema for the internal non-loader provenance manifest."""


EXPORT_FRAGMENT_GENERATOR_SCHEMA_VERSION: Final[int] = 6
"""Current generator contract recorded by every provenance manifest."""


EXPORT_RENDER_NORMALIZATION_SCHEMA_VERSION: Final[int] = 2
"""Reviewed parser-to-wire normalization contract recorded for every field."""


#: The shape of a lowercase hex digest, stated where digests are validated.
#: The publication module carried an identical copy: two modules deciding
#: separately what a digest looks like is one relaxation away from one of
#: them accepting a value the other refuses.
SHA256_PATTERN: Final[str] = r"^[0-9a-f]{64}$"


#: The pre-rename filename, kept so both the reader that skips it and the
#: publisher that removes it name the same string. It was declared twice
#: under two different names, which is the one shape a reader cannot grep:
#: searching for either name finds half the uses.
LEGACY_EXPORT_FRAGMENT_PROVENANCE_FILENAME: Final[str] = "export.provenance.json"


type ExportFieldDerivationCode = Literal[
    "filler-v1",
    "literal-exact-v1",
    "literal-note-exact-v1",
    "literal-pdf-source-adjudicated-v1",
    "literal-telematic-choice-v1",
    "numeric-date-aaaammdd-v1",
    "numeric-date-ddmmaaaa-v1",
    "numeric-decimal-v1",
    "numeric-ejercicio-aaaa-v1",
    "numeric-source-bounded-year-v1",
    "numeric-source-stated-year-constant-v1",
    "source-signed-component-v1",
    "source-signed-triple-v1",
    "source-text-date-component-v1",
    "numeric-enumeration-v1",
    "numeric-integer-v1",
    "numeric-note-governed-amount-v1",
    "text-a-v1",
    "text-an-v1",
    "render-profile-width-17-v1",
    "render-profile-singleton-v1",
    "render-profile-signed-monetary-composite-v1",
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
        return _normalise_output_digest_path(value)


def _normalise_output_digest_path(value: str) -> str:
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


#: The design's own numeric type vocabulary, from its type note: "Num: numerico
#: sin signo", "N: numerico con signo". A token outside it states nothing about
#: sign, and no verdict is invented from that silence.
_DESIGN_SIGNED_TYPE: Final[str] = "N"


_DESIGN_UNSIGNED_TYPE: Final[str] = "Num"


#: The sign axis means something only where the slot carries a number. Some
#: designs type a constant slot numerically (the modelo-number slot is typed
#: "N" and holds "151"), and a literal rendered as text there is correct.
_SIGN_BEARING_DATA_TYPES: Final[frozenset[str]] = frozenset({"money", "decimal", "integer"})


def design_stated_divergence(parser_field: RecordDesignIntermediateField, field: ExportFieldDefinition) -> str | None:
    """Return how an emitted field contradicts an axis its official row states, or ``None``.

    Only axes the design states are compared. Offset and length are held equal
    by the derivation itself; the sign is the axis a row states through its type
    column, and the one that diverged unnoticed across a fifth of the corpus.
    """
    if str(field.data_type) not in _SIGN_BEARING_DATA_TYPES:
        return None
    if parser_field.aeat_type == _DESIGN_SIGNED_TYPE and not field.signed:
        return f"design types '{_DESIGN_SIGNED_TYPE}' (numerico con signo), field declares unsigned"
    if parser_field.aeat_type == _DESIGN_UNSIGNED_TYPE and field.signed:
        return f"design types '{_DESIGN_UNSIGNED_TYPE}' (numerico sin signo), field declares signed"
    return None


class ExportFieldVerdict(_StrictModel):
    """How one emitted field stands against the official row it derives from.

    ``agrees``: every axis the design states matches the emitted field.
    ``adjudicated``: a stated axis diverges and ``ruling`` names the
    source-pinned declaration that explains why. A divergence nothing rules on
    never reaches a manifest; generation refuses it, so there is no refused
    verdict to record.
    """

    outcome: Literal["agrees", "adjudicated"]
    ruling: str | None = None

    @model_validator(mode="after")
    def _ruling_matches_outcome(self) -> ExportFieldVerdict:
        if self.outcome == "agrees" and self.ruling is not None:
            raise ValueError("an agreeing verdict carries no ruling")
        if self.outcome == "adjudicated" and not self.ruling:
            raise ValueError("an adjudicated verdict must name the ruling that explains it")
        return self


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
    verdict: ExportFieldVerdict | None = None
    """The field's standing against its official row; attached once generation knows the rulings."""

    @model_validator(mode="after")
    def _require_exact_authority_and_emitted_field(self) -> ExportFieldDerivation:
        _require_same_derivation_anchor(self.parser_field, self.semantic_entry)
        _require_current_derivation_schema(self.normalization_schema_version)
        _require_derivation_field_identity(self.field, self.semantic_entry)
        _require_derivation_field_coordinates(self.parser_field, self.semantic_entry, self.field)
        _require_derivation_field_semantics(self.field, self.semantic_entry)
        _require_recorded_field_verdict(self.parser_field, self.field, self.verdict)
        return self


def _require_same_derivation_anchor(
    parser_field: RecordDesignIntermediateField,
    semantic_entry: SemanticMapEntry,
) -> None:
    parser_anchor = parser_field
    semantic_anchor = semantic_entry.anchor
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


def _require_current_derivation_schema(version: int) -> None:
    if version != EXPORT_RENDER_NORMALIZATION_SCHEMA_VERSION:
        raise ValueError(
            "normalization schema drift: derivation records "
            f"{version}, expected {EXPORT_RENDER_NORMALIZATION_SCHEMA_VERSION}",
        )


def _require_derivation_field_identity(field: ExportFieldDefinition, semantic_entry: SemanticMapEntry) -> None:
    if field.id != semantic_entry.export_field_id:
        raise ValueError("field derivation emitted id does not match semantic-map entry")


def _require_derivation_field_coordinates(
    parser_field: RecordDesignIntermediateField,
    semantic_entry: SemanticMapEntry,
    field: ExportFieldDefinition,
) -> None:
    # A field filling a declared part of its cell takes the part's coordinates;
    # the part itself was held to the cell's text at join.
    part = semantic_entry.part
    expected = (part.offset, part.length) if part is not None else (parser_field.offset, parser_field.length)
    if (field.offset, field.length) != expected:
        raise ValueError("field derivation emitted coordinates do not match parser field")


def _require_derivation_field_semantics(field: ExportFieldDefinition, semantic_entry: SemanticMapEntry) -> None:
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
        if getattr(field, attribute) != getattr(semantic_entry, attribute):
            raise ValueError(f"field derivation emitted {attribute} does not match semantic-map entry")


def _require_recorded_field_verdict(
    parser_field: RecordDesignIntermediateField,
    field: ExportFieldDefinition,
    verdict: ExportFieldVerdict | None,
) -> None:
    if verdict is None:
        return
    diverges = design_stated_divergence(parser_field, field) is not None
    if diverges != (verdict.outcome == "adjudicated"):
        # Recomputed rather than trusted, so a stored manifest cannot claim
        # agreement for a field that contradicts its own row.
        raise ValueError(
            f"field derivation {field.id!r} records verdict {verdict.outcome!r}, but the field "
            f"{'diverges from' if diverges else 'agrees with'} its official row",
        )


def attach_field_verdicts(
    derivations: tuple[ExportFieldDerivation, ...], rulings: Mapping[str, str]
) -> tuple[ExportFieldDerivation, ...]:
    """Attach each derivation's verdict, refusing a divergence no ruling explains.

    ``rulings`` maps a derivation code to the identity of the source-pinned
    declaration that adjudicates divergent fields rendered through it.
    """
    attached: list[ExportFieldDerivation] = []
    for derivation in derivations:
        divergence = design_stated_divergence(derivation.parser_field, derivation.field)
        if divergence is None:
            verdict = ExportFieldVerdict(outcome="agrees")
        elif (ruling := rulings.get(derivation.derivation_code)) is not None:
            verdict = ExportFieldVerdict(outcome="adjudicated", ruling=ruling)
        else:
            raise RegistryValidationError(
                f"export field {derivation.field.id!r} diverges from its official row ({divergence}) "
                f"and no ruling adjudicates derivation {derivation.derivation_code!r}",
            )
        attached.append(derivation.model_copy(update={"verdict": verdict}))
    return tuple(attached)


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
    generated_export_inheritance: GeneratedExportInheritance | None = None

    @model_validator(mode="after")
    def _refuse_unknown_schema_or_unordered_outputs(self) -> ExportFragmentProvenanceManifest:
        _require_supported_manifest_versions(self)
        _require_sorted_unique_output_files(self.output_files)
        _require_sorted_unique_field_derivations(self.field_derivations)
        return self


def _require_supported_manifest_versions(manifest: ExportFragmentProvenanceManifest) -> None:
    if manifest.manifest_schema_version != EXPORT_FRAGMENT_PROVENANCE_SCHEMA_VERSION:
        raise ValueError(
            "unsupported export-fragment provenance manifest schema "
            f"{manifest.manifest_schema_version}; expected {EXPORT_FRAGMENT_PROVENANCE_SCHEMA_VERSION}",
        )
    if manifest.parser_schema_version != RECORD_DESIGN_INTERMEDIATE_SCHEMA_VERSION:
        raise ValueError(
            "parser schema drift: manifest records "
            f"{manifest.parser_schema_version}, expected {RECORD_DESIGN_INTERMEDIATE_SCHEMA_VERSION}",
        )
    if manifest.generator_schema_version != EXPORT_FRAGMENT_GENERATOR_SCHEMA_VERSION:
        raise ValueError(
            "generator schema drift: manifest records "
            f"{manifest.generator_schema_version}, expected {EXPORT_FRAGMENT_GENERATOR_SCHEMA_VERSION}",
        )
    if manifest.render_profile_schema_version != RENDER_PROFILE_SCHEMA_VERSION:
        raise ValueError(
            "render-profile schema drift: manifest records "
            f"{manifest.render_profile_schema_version}, expected {RENDER_PROFILE_SCHEMA_VERSION}",
        )


def _require_sorted_unique_output_files(output_files: tuple[ExportFragmentOutputDigest, ...]) -> None:
    paths = tuple(item.relative_path for item in output_files)
    if paths != tuple(sorted(paths)):
        raise ValueError("provenance output files must be sorted by relative path")
    if len(set(paths)) != len(paths):
        raise ValueError("provenance output files must not contain duplicate relative paths")


def _require_sorted_unique_field_derivations(field_derivations: tuple[ExportFieldDerivation, ...]) -> None:
    field_keys = tuple((item.export_record_id, str(item.field.id)) for item in field_derivations)
    if field_keys != tuple(sorted(field_keys)):
        raise ValueError("provenance field derivations must be sorted by record and field id")
    if len(set(field_keys)) != len(field_keys):
        raise ValueError("provenance field derivations must not contain duplicate emitted fields")


def export_fragment_provenance_path(export_directory: Path) -> Path:
    """Return the internal JSON attestation the TOML-only loader never consumes."""
    return export_directory / EXPORT_FRAGMENT_PROVENANCE_FILENAME


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
        digest = _digest_generated_export_file(candidate, export_root=export_root, resolved_root=resolved_root)
        if digest is not None:
            entries.append(digest)
    if not entries:
        raise RegistryValidationError(f"export provenance found no generated output files under {export_root}")
    return tuple(sorted(entries, key=lambda item: item.relative_path))


def _digest_generated_export_file(
    candidate: Path,
    *,
    export_root: Path,
    resolved_root: Path,
) -> ExportFragmentOutputDigest | None:
    if is_link_like(candidate):
        raise RegistryValidationError(f"export provenance refuses linked output path: {candidate}")
    if not candidate.is_file():
        return None
    relative_path = PurePosixPath(*candidate.relative_to(export_root).parts).as_posix()
    if candidate == export_root / EXPORT_FRAGMENT_PROVENANCE_FILENAME:
        return None
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
    return ExportFragmentOutputDigest(relative_path=relative_path, sha256=digest)


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
    generated_export_inheritance: GeneratedExportInheritance | None = None,
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
        semantic_map_sha256=_semantic_map_digest(semantic_map),
        render_profile_schema_version=RENDER_PROFILE_SCHEMA_VERSION,
        render_profile_sha256=render_profile_digest(render_profile, render_profile_source_evidence),
        modelo=target.modelo,
        revision_id=target.revision_id,
        design_epoch=target.design_epoch,
        loader_semantic_sha256=_loader_semantic_digest(loaded_layout),
        output_files=collect_export_fragment_output_digests(export_root),
        field_derivations=tuple(
            sorted(field_derivations, key=lambda item: (item.export_record_id, str(item.field.id)))
        ),
        variable_envelope_contract=_filing_envelope_provenance(
            joined,
            loaded_layout=loaded_layout,
        ),
        generated_export_inheritance=generated_export_inheritance,
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
    generated_export_inheritance: GeneratedExportInheritance | None = None,
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
        generated_export_inheritance=generated_export_inheritance,
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
    generated_export_inheritance: GeneratedExportInheritance | None = None,
) -> ExportFragmentProvenanceManifest:
    """Refuse current-authority, file, loader-semantic, or derivation drift."""
    manifest_path = export_fragment_provenance_path(export_root)
    if is_link_like(manifest_path):
        raise RegistryValidationError(f"export provenance refuses linked manifest: {manifest_path}")
    if not manifest_path.is_file():
        raise RegistryValidationError(f"export provenance manifest is missing: {manifest_path}")
    manifest = load_export_fragment_provenance_manifest(manifest_path.read_bytes())
    if manifest.generated_export_inheritance != generated_export_inheritance:
        raise RegistryValidationError(
            "export provenance generated-inheritance attestation differs from the selected baseline"
        )
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
    actual_loader_digest = _loader_semantic_digest(loaded_layout)
    if manifest.loader_semantic_sha256 != actual_loader_digest:
        # The output files were proven equal to their attested digests just
        # above, so the tree's bytes did not move: what moved is the projection
        # or the loader's hydration of those unchanged bytes. The manifest keeps
        # only the digest, so the key cannot be named here; say which side moved.
        raise RegistryValidationError(
            "export provenance loader-semantic digest does not match generated tree: "
            f"the manifest attests {manifest.loader_semantic_sha256}, the current projection "
            f"(loader semantic schema {_LOADER_SEMANTIC_SCHEMA_VERSION}) gives {actual_loader_digest}; "
            "every output file matches its attested digest, so the loader projection or the loader's "
            "hydration of this unchanged tree moved after the manifest was written",
        )
    _require_field_derivations_match_layout(manifest.field_derivations, loaded_layout)
    expected_derivations = tuple(
        sorted(field_derivations, key=lambda item: (item.export_record_id, str(item.field.id)))
    )
    if manifest.field_derivations != expected_derivations:
        raise RegistryValidationError("export provenance field derivations do not match the rendered tree")
    return manifest


def export_fragment_provenance_manifest_json_bytes(manifest: ExportFragmentProvenanceManifest) -> bytes:
    """Return the sole canonical JSON serialisation for a provenance manifest."""
    payload = manifest.model_dump(mode="json")
    if payload["generated_export_inheritance"] is None:
        del payload["generated_export_inheritance"]
    for derivation in payload["field_derivations"]:
        _omit_undeclared_field_keys(derivation["field"])
        if derivation["semantic_entry"]["part"] is None:
            del derivation["semantic_entry"]["part"]
        if derivation["verdict"] is None:
            del derivation["verdict"]
    return canonical_json_bytes(payload)


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
        raise RegistryValidationError(
            f"export provenance manifest violates the current contract: {validation_error_detail(exc)}",
        ) from exc
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
    _require_generation_coordinate_scope(joined=joined, semantic_map=semantic_map, target=target)
    _require_joined_fields_match_semantic_map(joined, semantic_map)
    _require_joined_records_match_semantic_map(joined, semantic_map)


def _require_generation_coordinate_scope(
    *,
    joined: JoinedRecordDesign,
    semantic_map: SemanticMap,
    target: ExportFragmentTarget,
) -> None:
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


def _require_joined_fields_match_semantic_map(joined: JoinedRecordDesign, semantic_map: SemanticMap) -> None:
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


def _require_joined_records_match_semantic_map(joined: JoinedRecordDesign, semantic_map: SemanticMap) -> None:
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
        "semantic_map_sha256": _semantic_map_digest(semantic_map),
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
    _require_unique_derivation_fields(loaded_layout, field_derivations, layout_fields, derivation_fields)
    _require_exact_derivation_coverage(layout_fields, derivation_fields)
    _require_derivation_fields_match_layout(layout_fields, derivation_fields)


def _require_unique_derivation_fields(
    loaded_layout: ExportLayoutDefinition,
    field_derivations: tuple[ExportFieldDerivation, ...],
    layout_fields: Mapping[tuple[str, str], ExportFieldDefinition],
    derivation_fields: Mapping[tuple[str, str], ExportFieldDefinition],
) -> None:
    if len(layout_fields) != len(tuple(field for record in loaded_layout.records for field in record.fields)):
        raise RegistryValidationError("loader export layout contains duplicate record and field identities")
    if len(derivation_fields) != len(field_derivations):
        raise RegistryValidationError("export provenance contains duplicate field derivations")


def _require_exact_derivation_coverage(
    layout_fields: Mapping[tuple[str, str], ExportFieldDefinition],
    derivation_fields: Mapping[tuple[str, str], ExportFieldDefinition],
) -> None:
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


def _require_derivation_fields_match_layout(
    layout_fields: Mapping[tuple[str, str], ExportFieldDefinition],
    derivation_fields: Mapping[tuple[str, str], ExportFieldDefinition],
) -> None:
    for identity, expected_field in layout_fields.items():
        if derivation_fields[identity] != expected_field:
            raise RegistryValidationError(
                f"export provenance derivation does not match generated field {identity[0]!r}/{identity[1]!r}",
            )


def _write_canonical_manifest_atomically(path: Path, payload: bytes) -> None:
    """Publish the sibling evidence write-once, refusing a pre-existing target.

    Uses the development-owned publish-once primitive above.
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
        _publish_once_bytes(path, payload)
    except FileExistsError as exc:
        raise RegistryValidationError(f"export provenance manifest already exists: {path}") from exc
    except OSError as exc:
        raise RegistryValidationError(f"cannot write export provenance manifest {path}: {exc}") from exc


class _DuplicateJsonKeyError(ValueError):
    """Raw JSON contained an ambiguous duplicate object key."""


def _json_object_without_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateJsonKeyError(f"duplicate object key {key!r}")
        result[key] = value
    return result
