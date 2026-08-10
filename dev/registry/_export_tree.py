"""Deterministic rendering of generated export-fragment directory trees.

This development-only boundary consumes the exact joined design, its reviewed
record meanings, and a hash-pinned layout profile.  It writes a complete
``export/`` directory without opening a shipped fragment directory or deriving
any output fact from one.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Final, Literal

import rtoml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from cadrumo.domain.calculations.registry import (
    CasillaFieldKind,
    ExportFieldDefinition,
    ExportLayoutDefinition,
    ExportLayoutId,
    ExportRecordDefinition,
    ModeloId,
    RegistryValidationError,
    RevisionId,
    SourceRefId,
)
from cadrumo.domain.calculations.registry._record_spec import ENCODING_ALIAS_MAP

from ._provenance_manifest import (
    EXPORT_RENDER_NORMALIZATION_SCHEMA_VERSION,
    ExportFieldDerivation,
    ExportFieldDerivationCode,
    ExportFragmentProvenanceManifest,
    ExportFragmentTarget,
    emit_export_fragment_provenance_manifest,
)
from ._semantic_map import SemanticMap
from ._semantic_map_join import JoinedRecordDesign, JoinedRecordDesignField, JoinedRecordDesignRecord

__all__ = [
    "EXPORT_RENDER_NORMALIZATION_SCHEMA_VERSION",
    "ExportFieldDerivation",
    "ExportRenderProfile",
    "RenderedExportTree",
    "render_complete_export_tree",
]


_SERIALIZER_CONVENTION: Final[str] = "rtoml-pretty-v1"
_SAFE_IDENTIFIER_RE: Final[re.Pattern[str]] = re.compile(r"^[^/\\\x00-\x1f]+$")
_SLUG_RE: Final[re.Pattern[str]] = re.compile(r"[^a-z0-9]+")
_DECIMAL_CONTENT_RE: Final[re.Pattern[str]] = re.compile(
    r"^(?P<whole>\d+)\s*enteros?\s+y\s+(?P<decimals>\d+)\s*decimales?$",
    re.IGNORECASE,
)
_INTEGER_CONTENT_RE: Final[re.Pattern[str]] = re.compile(r"^(?P<whole>\d+)\s*enteros?$", re.IGNORECASE)
_DATE_CONTENT: Final[str] = "aaaammdd"
_TEXT_TYPES: Final[frozenset[str]] = frozenset({"a", "an"})
_NUMERIC_TYPES: Final[frozenset[str]] = frozenset({"n", "num"})


class _StrictModel(BaseModel):
    """Frozen development-tool boundary with no untyped extras."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class ExportRenderProfile(_StrictModel):
    """Reviewed irreducible transport facts for one exact official design."""

    modelo: ModeloId
    design_epoch: str = Field(min_length=1)
    source_ref: SourceRefId
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    layout_id: ExportLayoutId
    format: Literal["fixed_width"]
    encoding: str = Field(min_length=1)
    line_ending: Literal["crlf", "lf", "none"]
    serializer_convention: Literal["rtoml-pretty-v1"]

    @model_validator(mode="after")
    def _require_supported_encoding_and_safe_ids(self) -> ExportRenderProfile:
        if self.encoding.casefold() not in ENCODING_ALIAS_MAP:
            raise ValueError(f"export render profile declares unsupported encoding {self.encoding!r}")
        _require_safe_identifier(str(self.layout_id), subject="export layout id")
        return self


class RenderedExportTree(_StrictModel):
    """The complete in-memory layout and materialised output members."""

    layout: ExportLayoutDefinition
    field_derivations: tuple[ExportFieldDerivation, ...] = Field(min_length=1)
    output_files: tuple[str, ...] = Field(min_length=2)
    provenance_manifest: ExportFragmentProvenanceManifest


def render_complete_export_tree(
    target_export_dir: Path,
    *,
    revision_id: RevisionId,
    joined: JoinedRecordDesign,
    semantic_map: SemanticMap,
    profile: ExportRenderProfile,
) -> RenderedExportTree:
    """Render one whole generated ``export/`` tree from its three authorities.

    The caller selects a fresh target owned by the generation transaction.  This
    function does not validate or publish a surrounding revision; those
    responsibilities deliberately remain later generator steps.
    """
    if joined.variable_envelopes:
        identities = ", ".join(
            repr(envelope.record_identity) for envelope in joined.variable_envelopes
        )
        raise RegistryValidationError(
            "fixed-width export generation refuses variable envelopes without a separately typed and proven "
            f"composition contract: {identities}",
        )
    _validate_profile(joined, profile)
    _prepare_target(target_export_dir)
    records, derivations = _render_records(joined.records, profile)
    layout = ExportLayoutDefinition.model_validate(
        {
            "id": profile.layout_id,
            "format": profile.format,
            "source_refs": _sorted_refs(
                (profile.source_ref, *(source for field in derivations for source in field.field.source_refs)),
            ),
            "legal_refs": _sorted_refs(legal for field in derivations for legal in field.field.legal_refs),
            "records": tuple(record.model_dump(mode="python", exclude_none=True) for record in records),
        },
    )
    _write_tree(target_export_dir, revision_id=revision_id, layout=layout)
    output_files = (
        "0000-export-layout.toml",
        *tuple(_record_relative_path(index, record.id) for index, record in enumerate(layout.records, start=1)),
    )
    provenance_manifest = emit_export_fragment_provenance_manifest(
        joined=joined,
        semantic_map=semantic_map,
        target=ExportFragmentTarget(
            modelo=joined.modelo,
            revision_id=revision_id,
            design_epoch=joined.source.design_epoch,
        ),
        loaded_layout=layout,
        export_root=target_export_dir,
        field_derivations=tuple(derivations),
    )
    return RenderedExportTree(
        layout=layout,
        field_derivations=tuple(derivations),
        output_files=output_files,
        provenance_manifest=provenance_manifest,
    )


def _validate_profile(joined: JoinedRecordDesign, profile: ExportRenderProfile) -> None:
    if profile.modelo != joined.modelo:
        raise RegistryValidationError(
            f"export render profile modelo {profile.modelo!r} does not match joined modelo {joined.modelo!r}",
        )
    if profile.design_epoch != joined.source.design_epoch:
        raise RegistryValidationError(
            f"export render profile design epoch {profile.design_epoch!r} does not match "
            f"joined design epoch {joined.source.design_epoch!r}",
        )
    if profile.source_ref != joined.source.source_ref:
        raise RegistryValidationError(
            f"export render profile source {profile.source_ref!r} does not match joined source "
            f"{joined.source.source_ref!r}",
        )
    if profile.source_sha256 != joined.source.source_sha256:
        raise RegistryValidationError("export render profile SHA-256 does not match joined official source")
    if profile.serializer_convention != _SERIALIZER_CONVENTION:
        raise RegistryValidationError(
            f"export render profile serializer {profile.serializer_convention!r} is not supported",
        )


def _prepare_target(target_export_dir: Path) -> None:
    if target_export_dir.name != "export":
        raise RegistryValidationError(f"generated export target must be named 'export', got {target_export_dir.name!r}")
    if target_export_dir.is_symlink() or target_export_dir.is_junction():
        raise RegistryValidationError(f"generated export target must not be a link: {target_export_dir}")
    if target_export_dir.exists():
        if not target_export_dir.is_dir():
            raise RegistryValidationError(f"generated export target is not a directory: {target_export_dir}")
        if any(target_export_dir.iterdir()):
            raise RegistryValidationError(f"generated export target is not empty: {target_export_dir}")
    else:
        target_export_dir.mkdir(parents=True)


def _render_records(
    joined_records: tuple[JoinedRecordDesignRecord, ...],
    profile: ExportRenderProfile,
) -> tuple[tuple[ExportRecordDefinition, ...], tuple[ExportFieldDerivation, ...]]:
    records: list[ExportRecordDefinition] = []
    derivations: list[ExportFieldDerivation] = []
    record_ids: set[str] = set()
    for order, joined_record in enumerate(joined_records):
        record_id = str(joined_record.semantic_record.export_record_id)
        _require_safe_identifier(record_id, subject="export record id")
        if record_id in record_ids:
            raise RegistryValidationError(f"generated export tree has duplicate record id {record_id!r}")
        record_ids.add(record_id)
        _require_exact_record_geometry(joined_record)
        record_derivations = tuple(
            _normalise_field(field, profile, export_record_id=record_id) for field in joined_record.fields
        )
        derivations.extend(record_derivations)
        records.append(
            ExportRecordDefinition.model_validate(
                {
                    "id": record_id,
                    "record_type": joined_record.semantic_record.record_type,
                    "order": order,
                    "encoding": profile.encoding,
                    "line_ending": profile.line_ending,
                    "fields": tuple(
                        item.field.model_dump(mode="python", exclude_none=True) for item in record_derivations
                    ),
                },
            ),
        )
    if not records:
        raise RegistryValidationError("joined record design contains no records to render")
    return tuple(records), tuple(derivations)


def _require_exact_record_geometry(joined_record: JoinedRecordDesignRecord) -> None:
    declared_total = joined_record.parser_sheet.declared_total
    if declared_total is None:
        raise RegistryValidationError(
            f"official record {joined_record.parser_sheet.record_identity!r} has no declared total",
        )
    if not joined_record.fields:
        raise RegistryValidationError(
            f"official record {joined_record.parser_sheet.record_identity!r} has no parsed fields",
        )

    expected_offset = 1
    for joined_field in joined_record.fields:
        parser_field = joined_field.parser_field
        if parser_field.offset != expected_offset:
            defect = "an overlap" if parser_field.offset < expected_offset else "a gap"
            raise RegistryValidationError(
                f"official record {joined_record.parser_sheet.record_identity!r} has {defect} before "
                f"field {parser_field.source_cell!r}: expected offset {expected_offset}, "
                f"got {parser_field.offset}",
            )
        expected_offset = parser_field.offset + parser_field.length

    actual_total = expected_offset - 1
    if actual_total != declared_total:
        raise RegistryValidationError(
            f"official record {joined_record.parser_sheet.record_identity!r} declares total {declared_total}, "
            f"but parsed fields end at {actual_total}",
        )


def _normalise_field(
    joined_field: JoinedRecordDesignField,
    profile: ExportRenderProfile,
    *,
    export_record_id: str,
) -> ExportFieldDerivation:
    parser_field = joined_field.parser_field
    semantic_entry = joined_field.semantic_entry
    _require_safe_identifier(str(semantic_entry.export_field_id), subject="export field id")
    if semantic_entry.kind is CasillaFieldKind.LITERAL:
        return _literal_derivation(joined_field, profile, export_record_id=export_record_id)
    if semantic_entry.kind is CasillaFieldKind.FILLER:
        return _schema_field(
            joined_field,
            data_type="text",
            required=False,
            padding="right_space",
            justification="left",
            signed=False,
            export_record_id=export_record_id,
            derivation_code="filler-v1",
        )
    if semantic_entry.kind is CasillaFieldKind.CHECKSUM:
        raise RegistryValidationError(
            f"official field {semantic_entry.export_field_id!r} has checksum semantics with no reviewed normalizer",
        )
    type_code = parser_field.aeat_type.strip().casefold()
    if type_code in _TEXT_TYPES:
        derivation_code: ExportFieldDerivationCode = "text-a-v1" if type_code == "a" else "text-an-v1"
        return _schema_field(
            joined_field,
            data_type="text",
            required=_is_required(parser_field.validation),
            padding="right_space",
            justification="left",
            signed=False,
            export_record_id=export_record_id,
            derivation_code=derivation_code,
        )
    if type_code in _NUMERIC_TYPES:
        return _numeric_derivation(joined_field, export_record_id=export_record_id)
    raise RegistryValidationError(
        f"official field {semantic_entry.export_field_id!r} declares unsupported AEAT type {parser_field.aeat_type!r}",
    )


def _literal_derivation(
    joined_field: JoinedRecordDesignField,
    profile: ExportRenderProfile,
    *,
    export_record_id: str,
) -> ExportFieldDerivation:
    parser_field = joined_field.parser_field
    literal = joined_field.semantic_entry.literal
    if literal is None:
        raise RegistryValidationError(f"literal field {joined_field.semantic_entry.export_field_id!r} has no literal")
    try:
        literal_length = len(literal.encode(profile.encoding))
    except UnicodeEncodeError as exc:
        raise RegistryValidationError(
            f"literal field {joined_field.semantic_entry.export_field_id!r} cannot encode as {profile.encoding!r}",
        ) from exc
    if literal_length != parser_field.length:
        raise RegistryValidationError(
            f"literal field {joined_field.semantic_entry.export_field_id!r} has {literal_length} encoded bytes, "
            f"but the official slot is {parser_field.length} bytes",
        )
    return _schema_field(
        joined_field,
        data_type="text",
        required=True,
        padding="none",
        justification="none",
        signed=False,
        export_record_id=export_record_id,
        derivation_code="literal-exact-v1",
    )


def _numeric_derivation(
    joined_field: JoinedRecordDesignField,
    *,
    export_record_id: str,
) -> ExportFieldDerivation:
    parser_field = joined_field.parser_field
    content = parser_field.content
    if content is None:
        raise RegistryValidationError(
            f"official numeric field {joined_field.semantic_entry.export_field_id!r} has no unambiguous content form",
        )
    normalised_content = " ".join(content.split())
    if normalised_content.casefold() == _DATE_CONTENT:
        if parser_field.length != 8:
            raise RegistryValidationError(
                f"official date field {joined_field.semantic_entry.export_field_id!r} has "
                f"{parser_field.length} bytes, expected 8",
            )
        return _schema_field(
            joined_field,
            data_type="date",
            required=_is_required(parser_field.validation),
            padding="none",
            justification="none",
            signed=False,
            export_record_id=export_record_id,
            date_format=_DATE_CONTENT,
            derivation_code="numeric-date-aaaammdd-v1",
        )
    decimal_match = _DECIMAL_CONTENT_RE.fullmatch(normalised_content)
    if decimal_match is not None:
        whole = int(decimal_match.group("whole"))
        decimals = int(decimal_match.group("decimals"))
        _require_numeric_extent(joined_field, expected_length=whole + decimals)
        return _schema_field(
            joined_field,
            data_type="decimal",
            required=_is_required(parser_field.validation),
            padding="left_zero",
            justification="right",
            signed=False,
            export_record_id=export_record_id,
            decimals=decimals,
            derivation_code="numeric-decimal-v1",
        )
    integer_match = _INTEGER_CONTENT_RE.fullmatch(normalised_content)
    if integer_match is not None:
        _require_numeric_extent(joined_field, expected_length=int(integer_match.group("whole")))
        return _schema_field(
            joined_field,
            data_type="integer",
            required=_is_required(parser_field.validation),
            padding="left_zero",
            justification="right",
            signed=False,
            export_record_id=export_record_id,
            derivation_code="numeric-integer-v1",
        )
    raise RegistryValidationError(
        f"official numeric field {joined_field.semantic_entry.export_field_id!r} has ambiguous content {content!r}",
    )


def _require_numeric_extent(joined_field: JoinedRecordDesignField, *, expected_length: int) -> None:
    actual_length = joined_field.parser_field.length
    if actual_length != expected_length:
        raise RegistryValidationError(
            f"official numeric field {joined_field.semantic_entry.export_field_id!r} has {actual_length} bytes, "
            f"but content declares {expected_length}",
        )


def _schema_field(
    joined_field: JoinedRecordDesignField,
    *,
    data_type: Literal["text", "integer", "decimal", "money", "date", "boolean"],
    required: bool,
    padding: Literal["left_zero", "left_space", "right_space", "none"],
    justification: Literal["left", "right", "none"],
    signed: bool,
    export_record_id: str,
    derivation_code: ExportFieldDerivationCode,
    date_format: str | None = None,
    decimals: int | None = None,
) -> ExportFieldDerivation:
    parser_field = joined_field.parser_field
    semantic_entry = joined_field.semantic_entry
    return ExportFieldDerivation(
        export_record_id=export_record_id,
        parser_field=parser_field,
        semantic_entry=semantic_entry,
        field=ExportFieldDefinition.model_validate(
            {
                "id": semantic_entry.export_field_id,
                "offset": parser_field.offset,
                "length": parser_field.length,
                "kind": semantic_entry.kind,
                "casilla_id": semantic_entry.casilla_id,
                "binding": semantic_entry.binding,
                "literal": semantic_entry.literal,
                "header_key": semantic_entry.header_key,
                "draft_attribute": semantic_entry.draft_attribute,
                "computed_key": semantic_entry.computed_key,
                "data_type": data_type,
                "required": required,
                "padding": padding,
                "justification": justification,
                "date_format": date_format,
                "decimals": decimals,
                "signed": signed,
                "legal_refs": semantic_entry.legal_refs,
                "source_refs": semantic_entry.source_refs,
            },
        ),
        normalization_schema_version=EXPORT_RENDER_NORMALIZATION_SCHEMA_VERSION,
        derivation_code=derivation_code,
    )


def _is_required(validation: str | None) -> bool:
    return validation is not None and validation.strip().casefold() == "obligatorio"


def _write_tree(target_export_dir: Path, *, revision_id: RevisionId, layout: ExportLayoutDefinition) -> None:
    layout_payload = layout.model_dump(mode="json", exclude_none=True)
    records = tuple(layout_payload.pop("records"))
    metadata_payload = {"revisions": {str(revision_id): {"export_layouts": [layout_payload]}}}
    _write_toml(target_export_dir / "0000-export-layout.toml", metadata_payload)
    written_paths = {"0000-export-layout.toml"}
    for index, record in enumerate(records, start=1):
        record_id = record.get("id")
        if not isinstance(record_id, str):
            raise RegistryValidationError("validated generated export record has no string id")
        relative_path = _record_relative_path(index, record_id)
        if relative_path in written_paths:
            raise RegistryValidationError(f"generated export path collision at {relative_path!r}")
        written_paths.add(relative_path)
        _write_toml(
            target_export_dir / relative_path,
            {
                "revisions": {
                    str(revision_id): {
                        "export_layouts": [
                            {
                                "id": layout.id,
                                "records": [record],
                            },
                        ],
                    },
                },
            },
        )


def _write_toml(path: Path, payload: Mapping[str, object]) -> None:
    try:
        rendered = rtoml.dumps(payload, pretty=True, none_value=None)
    except (TypeError, ValueError) as exc:
        raise RegistryValidationError(f"cannot serialize generated export TOML {path.name!r}: {exc}") from exc
    path.write_bytes(rendered.encode("utf-8"))


def _record_relative_path(index: int, record_id: object) -> str:
    raw_record_id = str(record_id)
    _require_safe_identifier(raw_record_id, subject="export record id")
    slug = _SLUG_RE.sub("-", raw_record_id.casefold()).strip("-")
    if not slug:
        raise RegistryValidationError(f"export record id {raw_record_id!r} cannot form a stable output slug")
    return f"{index:04d}-record-{slug}.toml"


def _require_safe_identifier(value: str, *, subject: str) -> None:
    if not value or value in {".", ".."} or ".." in value or _SAFE_IDENTIFIER_RE.fullmatch(value) is None:
        raise RegistryValidationError(f"{subject} is unsafe for generated export output: {value!r}")


def _sorted_refs(refs: Iterable[object]) -> tuple[str, ...]:
    values = tuple(sorted({str(ref) for ref in refs}))
    if not values:
        raise RegistryValidationError("generated export layout has no reviewed references")
    return values
