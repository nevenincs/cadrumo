"""Deterministic rendering of generated export-fragment directory trees.

This development-only boundary consumes the exact joined design, its reviewed
record meanings, and a hash-pinned layout profile.  It writes a complete
``export/`` directory without opening a shipped fragment directory or deriving
any output fact from one.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Final, Literal, cast

import rtoml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from cadrumo.core import M303ProductSoftwareIdentity
from cadrumo.domain.calculations.registry import (
    ENCODING_ALIAS_MAP,
    CasillaFieldKind,
    ExportEncoding,
    ExportFieldDefinition,
    ExportJustification,
    ExportLayoutDefinition,
    ExportLayoutId,
    ExportPadding,
    ExportRecordDefinition,
    ExportValuePolicy,
    FixedWidthRecordRenderError,
    ModeloId,
    ProjectionEndpointDeclaration,
    RegistryValidationError,
    RevisionId,
    SourceRefId,
    render_fixed_width_export_record_payload,
)

from ._m303_variable_envelope import (
    M303EnvelopeBodyMember,
    M303EnvelopeBytes,
    M303EnvelopeGenerationInput,
    render_m303_variable_envelope_bytes,
)
from ._provenance_manifest import (
    EXPORT_RENDER_NORMALIZATION_SCHEMA_VERSION,
    ExportFieldDerivation,
    ExportFieldDerivationCode,
    ExportFragmentProvenanceManifest,
    ExportFragmentTarget,
    emit_export_fragment_provenance_manifest,
)
from ._render_profile import (
    RenderProfile,
    RenderProfileAnchor,
    RenderProfileSourceEvidence,
    SingletonNumericRule,
    Width17MembershipRule,
    validate_render_profile,
)
from ._semantic_map import SemanticMap
from ._semantic_map_join import JoinedRecordDesign, JoinedRecordDesignField, JoinedRecordDesignRecord

__all__ = [
    "EXPORT_RENDER_NORMALIZATION_SCHEMA_VERSION",
    "ExportFieldDerivation",
    "ExportTreeTransportProfile",
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
_SINGLETON_POLICY_SHAPES: Final[Mapping[ExportValuePolicy, Literal["integer", "decimal", "date", "digit_identity"]]] = {
    ExportValuePolicy.SELECTED_1_UNSELECTED_0: "integer",
    ExportValuePolicy.FOUR_DIGIT_YEAR_FINAL_TWO_DIGITS: "integer",
    ExportValuePolicy.UNSIGNED_INTEGER: "integer",
    ExportValuePolicy.IMPLIED_DECIMAL: "decimal",
    ExportValuePolicy.YYYYMMDD: "date",
    ExportValuePolicy.ENUMERATED_DIGITS: "integer",
    ExportValuePolicy.DIGIT_STRING: "digit_identity",
    ExportValuePolicy.IDENTIFIER_DIGITS: "digit_identity",
    ExportValuePolicy.FOUR_DIGIT_YEAR: "integer",
    ExportValuePolicy.TWO_DIGIT_MONTH: "integer",
    ExportValuePolicy.TWO_DIGIT_DAY: "integer",
}
_TEXT_TYPES: Final[frozenset[str]] = frozenset({"a", "an"})
_NUMERIC_TYPES: Final[frozenset[str]] = frozenset({"n", "num"})
_OFFICIAL_LITERAL_RE: Final[re.Pattern[str]] = re.compile(
    r"^\s*constante(?:\s+n[uú]mero)?\s+(?P<quote>['\"])(?P<literal>[^'\"]*)(?P=quote)\.?\s*$",
    re.IGNORECASE,
)
_MAX_FRAGMENT_LINES: Final[int] = 1_399
_MAX_FRAGMENT_LINE_CHARS: Final[int] = 519


class _StrictModel(BaseModel):
    """Frozen development-tool boundary with no untyped extras."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class ExportTreeTransportProfile(_StrictModel):
    """Transport-only settings for one generated export tree."""

    modelo: ModeloId
    design_epoch: str = Field(min_length=1)
    source_ref: SourceRefId
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    layout_id: ExportLayoutId
    format: Literal["fixed_width"]
    encoding: ExportEncoding
    line_ending: Literal["crlf", "lf", "none"]
    serializer_convention: Literal["rtoml-pretty-v1"]

    @model_validator(mode="after")
    def _require_supported_encoding_and_safe_ids(self) -> ExportTreeTransportProfile:
        if self.encoding.casefold() not in ENCODING_ALIAS_MAP:
            raise ValueError(f"export tree transport profile declares unsupported encoding {self.encoding!r}")
        _require_safe_identifier(str(self.layout_id), subject="export layout id")
        return self


class RenderedExportTree(_StrictModel):
    """The complete in-memory layout and materialised output members."""

    layout: ExportLayoutDefinition
    field_derivations: tuple[ExportFieldDerivation, ...] = Field(min_length=1)
    output_files: tuple[str, ...] = Field(min_length=2)
    provenance_manifest: ExportFragmentProvenanceManifest
    m303_variable_envelope: M303EnvelopeBytes | None = None


def render_complete_export_tree(
    target_export_dir: Path,
    *,
    revision_id: RevisionId,
    joined: JoinedRecordDesign,
    semantic_map: SemanticMap,
    transport_profile: ExportTreeTransportProfile,
    render_profile: RenderProfile,
    render_profile_source_evidence: RenderProfileSourceEvidence,
    product_software_identity: M303ProductSoftwareIdentity | None = None,
    m303_envelope_input: M303EnvelopeGenerationInput | None = None,
) -> RenderedExportTree:
    """Render one whole generated ``export/`` tree from its three authorities.

    The caller selects a fresh target owned by the generation transaction.  This
    function does not validate or publish a surrounding revision; those
    responsibilities deliberately remain later generator steps.
    """
    _validate_transport_profile(joined, transport_profile)
    if joined.variable_envelopes and joined.m303_variable_envelope is None:
        identities = ", ".join(repr(envelope.record_identity) for envelope in joined.variable_envelopes)
        raise RegistryValidationError(
            "fixed-width export generation refuses variable envelopes without a separately typed and proven "
            f"composition contract: {identities}",
        )
    if joined.m303_variable_envelope is not None and product_software_identity is None:
        raise RegistryValidationError(
            "typed Modelo 303 DP30300 generation requires explicit product/software identity authority",
        )
    if joined.m303_variable_envelope is None and product_software_identity is not None:
        raise RegistryValidationError(
            "product/software identity is only admitted for a typed Modelo 303 DP30300 envelope",
        )
    if joined.m303_variable_envelope is not None and m303_envelope_input is None:
        raise RegistryValidationError(
            "typed Modelo 303 DP30300 generation requires explicit filing period and canonical body values",
        )
    if joined.m303_variable_envelope is None and m303_envelope_input is not None:
        raise RegistryValidationError(
            "M303 envelope filing period and body values are only admitted for a typed Modelo 303 DP30300 envelope",
        )
    if joined.m303_variable_envelope is not None:
        assert m303_envelope_input is not None
        if joined.revision_id != revision_id:
            raise RegistryValidationError(
                f"typed Modelo 303 DP30300 target revision {revision_id!r} does not match the selected "
                f"snapshot revision {joined.revision_id!r}",
            )
        if joined.filing_period != m303_envelope_input.filing_period:
            raise RegistryValidationError(
                "typed Modelo 303 DP30300 filing period does not match the exact selected snapshot period",
            )
    validate_render_profile(render_profile, joined, render_profile_source_evidence)
    records, derivations = _render_records(joined.records, transport_profile, render_profile)
    _validate_generated_projection_bijection(tuple(derivations), joined.projection_endpoints)
    layout = ExportLayoutDefinition.model_validate(
        {
            "id": transport_profile.layout_id,
            "format": transport_profile.format,
            "source_refs": _sorted_refs(
                (
                    transport_profile.source_ref,
                    *(source for field in derivations for source in field.field.source_refs),
                ),
            ),
            "legal_refs": _sorted_refs(legal for field in derivations for legal in field.field.legal_refs),
            "records": records,
        },
    )
    _require_semantic_map_attestation(joined, semantic_map)
    m303_variable_envelope = (
        _render_m303_variable_envelope(
            records,
            joined=joined,
            product_software_identity=product_software_identity,
            generation_input=m303_envelope_input,
        )
        if joined.m303_variable_envelope is not None
        else None
    )
    rendered_files = _render_tree_files(revision_id=revision_id, layout=layout)
    _prepare_target(target_export_dir)
    for relative_path, payload in rendered_files:
        (target_export_dir / relative_path).write_bytes(payload)
    output_files = tuple(relative_path for relative_path, _payload in rendered_files)
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
        render_profile=render_profile,
        render_profile_source_evidence=render_profile_source_evidence,
        product_software_identity=product_software_identity,
        m303_variable_envelope=m303_variable_envelope,
    )
    return RenderedExportTree(
        layout=layout,
        field_derivations=tuple(derivations),
        output_files=output_files,
        provenance_manifest=provenance_manifest,
        m303_variable_envelope=m303_variable_envelope,
    )


def _validate_generated_projection_bijection(
    derivations: tuple[ExportFieldDerivation, ...],
    declarations: tuple[ProjectionEndpointDeclaration, ...],
) -> None:
    """Refuse a generated layout that differs from revision endpoint authority."""
    projection_refs = tuple(
        derivation.field.projection_ref
        for derivation in derivations
        if derivation.field.kind is CasillaFieldKind.PROJECTION
    )
    if any(reference is None for reference in projection_refs):
        raise RegistryValidationError("generated projection field must carry a typed projection_ref")
    generated = tuple(reference for reference in projection_refs if reference is not None)
    duplicate_generated = tuple(
        sorted(repr(reference) for reference, count in Counter(generated).items() if count > 1),
    )
    if duplicate_generated:
        raise RegistryValidationError(
            "generated layout contains duplicate projection declarations: " + ", ".join(duplicate_generated),
        )
    declared = tuple(declaration.projection_ref for declaration in declarations)
    duplicate_declared = tuple(
        sorted(repr(reference) for reference, count in Counter(declared).items() if count > 1),
    )
    if duplicate_declared:
        raise RegistryValidationError(
            "revision projection declarations are not unique: " + ", ".join(duplicate_declared),
        )
    missing = tuple(sorted(repr(reference) for reference in set(declared) - set(generated)))
    undeclared = tuple(sorted(repr(reference) for reference in set(generated) - set(declared)))
    if missing or undeclared:
        details: list[str] = []
        if missing:
            details.append("missing declarations " + ", ".join(missing))
        if undeclared:
            details.append("undeclared generated refs " + ", ".join(undeclared))
        raise RegistryValidationError(
            "generated projection layout must exactly biject revision declarations: " + "; ".join(details),
        )


def _validate_transport_profile(joined: JoinedRecordDesign, profile: ExportTreeTransportProfile) -> None:
    if profile.modelo != joined.modelo:
        raise RegistryValidationError(
            f"export tree transport profile modelo {profile.modelo!r} does not match joined modelo {joined.modelo!r}",
        )
    if profile.design_epoch != joined.source.design_epoch:
        raise RegistryValidationError(
            f"export tree transport profile design epoch {profile.design_epoch!r} does not match "
            f"joined design epoch {joined.source.design_epoch!r}",
        )
    if profile.source_ref != joined.source.source_ref:
        raise RegistryValidationError(
            f"export tree transport profile source {profile.source_ref!r} does not match joined source "
            f"{joined.source.source_ref!r}",
        )
    if profile.source_sha256 != joined.source.source_sha256:
        raise RegistryValidationError("export tree transport profile SHA-256 does not match joined official source")
    if profile.serializer_convention != _SERIALIZER_CONVENTION:
        raise RegistryValidationError(
            f"export tree transport profile serializer {profile.serializer_convention!r} is not supported",
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
    transport_profile: ExportTreeTransportProfile,
    render_profile: RenderProfile,
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
            _normalise_field(
                field,
                transport_profile,
                render_profile,
                export_record_id=record_id,
            )
            for field in joined_record.fields
        )
        derivations.extend(record_derivations)
        records.append(
            ExportRecordDefinition.model_validate(
                {
                    "id": record_id,
                    "record_type": joined_record.semantic_record.record_type,
                    "required": joined_record.semantic_record.required,
                    "repeat": joined_record.semantic_record.repeat,
                    "order": order,
                    "encoding": transport_profile.encoding,
                    "line_ending": transport_profile.line_ending,
                    "fields": tuple(item.field for item in record_derivations),
                },
            ),
        )
    if not records:
        raise RegistryValidationError("joined record design contains no records to render")
    return tuple(records), tuple(derivations)


def _render_m303_variable_envelope(
    records: tuple[ExportRecordDefinition, ...],
    *,
    joined: JoinedRecordDesign,
    product_software_identity: M303ProductSoftwareIdentity | None,
    generation_input: M303EnvelopeGenerationInput | None,
) -> M303EnvelopeBytes:
    """Compose DP30300 from the canonical record payload writer in memory only."""
    if product_software_identity is None or generation_input is None or joined.m303_variable_envelope is None:
        raise RegistryValidationError("typed Modelo 303 DP30300 composition requires every explicit authority")
    supplied_ids = tuple(item.record_id for item in generation_input.body_records)
    rendered_ids = tuple(record.id for record in records)
    if supplied_ids != rendered_ids:
        raise RegistryValidationError(
            "M303 envelope body values must match the exact generated fixed-record order; "
            f"supplied={supplied_ids!r}, generated={rendered_ids!r}",
        )
    _require_explicit_m303_body_values(records, generation_input)
    try:
        body_members = tuple(
            M303EnvelopeBodyMember(
                record_id=record.id,
                payload=render_fixed_width_export_record_payload(
                    record,
                    field_values={value.casilla_id: value.value for value in supplied.casilla_values},
                ),
            )
            for record, supplied in zip(records, generation_input.body_records, strict=True)
        )
    except FixedWidthRecordRenderError as exc:
        raise RegistryValidationError(
            f"M303 envelope body record {exc.export_record_id!r} cannot render through the canonical record codec: "
            f"{exc}",
        ) from exc
    return render_m303_variable_envelope_bytes(
        joined.m303_variable_envelope.semantic,
        joined.m303_variable_envelope.parser_envelope,
        source=joined.source,
        product_software_identity=product_software_identity,
        filing_period=generation_input.filing_period,
        body_members=body_members,
    )


def _require_explicit_m303_body_values(
    records: tuple[ExportRecordDefinition, ...],
    generation_input: M303EnvelopeGenerationInput,
) -> None:
    """Refuse an implicit blank for any generated DP30300 body casilla."""
    for record, supplied in zip(records, generation_input.body_records, strict=True):
        declared = tuple(
            field.casilla_id
            for field in record.fields
            if field.kind is CasillaFieldKind.CASILLA and field.casilla_id is not None
        )
        provided = tuple(value.casilla_id for value in supplied.casilla_values)
        if set(provided) != set(declared):
            raise RegistryValidationError(
                f"M303 envelope body record {record.id!r} requires one explicit value for every declared casilla; "
                f"declared={declared!r}, provided={provided!r}",
            )


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
    transport_profile: ExportTreeTransportProfile,
    render_profile: RenderProfile,
    *,
    export_record_id: str,
) -> ExportFieldDerivation:
    parser_field = joined_field.parser_field
    semantic_entry = joined_field.semantic_entry
    _require_safe_identifier(str(semantic_entry.export_field_id), subject="export field id")
    if semantic_entry.kind is CasillaFieldKind.LITERAL:
        return _literal_derivation(joined_field, transport_profile, export_record_id=export_record_id)
    if semantic_entry.kind is CasillaFieldKind.FILLER:
        return _schema_field(
            joined_field,
            data_type="text",
            required=False,
            padding=ExportPadding.RIGHT_SPACE,
            justification=ExportJustification.LEFT,
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
            padding=ExportPadding.RIGHT_SPACE,
            justification=ExportJustification.LEFT,
            signed=False,
            export_record_id=export_record_id,
            derivation_code=derivation_code,
        )
    if type_code in _NUMERIC_TYPES:
        if parser_field.content is None or not parser_field.content.strip():
            return _render_profile_numeric_derivation(
                joined_field,
                render_profile,
                export_record_id=export_record_id,
            )
        return _numeric_derivation(joined_field, export_record_id=export_record_id)
    raise RegistryValidationError(
        f"official field {semantic_entry.export_field_id!r} declares unsupported AEAT type {parser_field.aeat_type!r}",
    )


def _literal_derivation(
    joined_field: JoinedRecordDesignField,
    profile: ExportTreeTransportProfile,
    *,
    export_record_id: str,
) -> ExportFieldDerivation:
    parser_field = joined_field.parser_field
    literal = joined_field.semantic_entry.literal
    if literal is None:
        raise RegistryValidationError(f"literal field {joined_field.semantic_entry.export_field_id!r} has no literal")
    official_content = parser_field.content
    if official_content is None:
        raise RegistryValidationError(
            f"literal field {joined_field.semantic_entry.export_field_id!r} has no exact official constant content",
        )
    match = _OFFICIAL_LITERAL_RE.fullmatch(official_content)
    if match is None:
        raise RegistryValidationError(
            f"literal field {joined_field.semantic_entry.export_field_id!r} has ambiguous official constant "
            f"content {official_content!r}",
        )
    official_literal = match.group("literal")
    try:
        literal_bytes = literal.encode(profile.encoding)
        official_literal_bytes = official_literal.encode(profile.encoding)
    except UnicodeEncodeError as exc:
        raise RegistryValidationError(
            f"literal field {joined_field.semantic_entry.export_field_id!r} cannot encode as {profile.encoding!r}",
        ) from exc
    if literal_bytes != official_literal_bytes:
        raise RegistryValidationError(
            f"literal field {joined_field.semantic_entry.export_field_id!r} value does not agree byte-for-byte "
            "with the exact official constant content",
        )
    literal_length = len(literal_bytes)
    if literal_length != parser_field.length:
        raise RegistryValidationError(
            f"literal field {joined_field.semantic_entry.export_field_id!r} has {literal_length} encoded bytes, "
            f"but the official slot is {parser_field.length} bytes",
        )
    return _schema_field(
        joined_field,
        data_type="text",
        required=True,
        padding=ExportPadding.NONE,
        justification=ExportJustification.NONE,
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
            padding=ExportPadding.NONE,
            justification=ExportJustification.NONE,
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
            padding=ExportPadding.LEFT_ZERO,
            justification=ExportJustification.RIGHT,
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
            padding=ExportPadding.LEFT_ZERO,
            justification=ExportJustification.RIGHT,
            signed=False,
            export_record_id=export_record_id,
            derivation_code="numeric-integer-v1",
        )
    raise RegistryValidationError(
        f"official numeric field {joined_field.semantic_entry.export_field_id!r} has ambiguous content {content!r}",
    )


def _render_profile_numeric_derivation(
    joined_field: JoinedRecordDesignField,
    profile: RenderProfile,
    *,
    export_record_id: str,
) -> ExportFieldDerivation:
    anchor = _render_profile_anchor(joined_field)
    width_rule = next((rule for rule in profile.width_17_rules if anchor in rule.anchors), None)
    if width_rule is not None:
        return _profile_width_17_derivation(
            joined_field,
            width_rule,
            export_record_id=export_record_id,
        )
    singleton = next((rule for rule in profile.singleton_rules if rule.anchor == anchor), None)
    if singleton is None:
        raise RegistryValidationError(
            f"validated render profile has no exact rule for blank numeric anchor {anchor!r}",
        )
    return _profile_singleton_derivation(
        joined_field,
        singleton,
        export_record_id=export_record_id,
    )


def _profile_width_17_derivation(
    joined_field: JoinedRecordDesignField,
    rule: Width17MembershipRule,
    *,
    export_record_id: str,
) -> ExportFieldDerivation:
    return _schema_field(
        joined_field,
        data_type="money" if rule.sign_policy == "n-prefix-negative-blank-nonnegative" else "decimal",
        required=_is_required(joined_field.parser_field.validation),
        padding=ExportPadding.LEFT_ZERO,
        justification=ExportJustification.RIGHT,
        signed=rule.sign_policy == "n-prefix-negative-blank-nonnegative",
        export_record_id=export_record_id,
        decimals=rule.decimal_digits,
        derivation_code="render-profile-width-17-v1",
    )


def _profile_singleton_derivation(
    joined_field: JoinedRecordDesignField,
    rule: SingletonNumericRule,
    *,
    export_record_id: str,
) -> ExportFieldDerivation:
    data_type: Literal["text", "integer", "decimal", "money", "date", "boolean"]
    date_format: str | None = None
    decimals: int | None = None
    policy_shape = _SINGLETON_POLICY_SHAPES.get(rule.value_policy)
    if policy_shape is None:
        raise RegistryValidationError(f"unsupported singleton export value policy {rule.value_policy!r}")
    if policy_shape == "date":
        data_type = "date"
        date_format = _DATE_CONTENT
        padding = ExportPadding.NONE
        justification = ExportJustification.NONE
    elif policy_shape == "decimal":
        data_type = "decimal"
        decimals = rule.decimal_digits
        padding = ExportPadding.LEFT_ZERO
        justification = ExportJustification.RIGHT
    elif policy_shape == "digit_identity":
        data_type = "text"
        padding = ExportPadding.NONE
        justification = ExportJustification.NONE
    elif policy_shape == "integer":
        data_type = "integer"
        padding = ExportPadding.LEFT_ZERO
        justification = ExportJustification.RIGHT
    else:
        raise RegistryValidationError(f"unsupported singleton export policy shape {policy_shape!r}")
    allowed_values = rule.allowed_values or None if rule.value_policy is ExportValuePolicy.ENUMERATED_DIGITS else None
    return _schema_field(
        joined_field,
        data_type=data_type,
        required=_is_required(joined_field.parser_field.validation),
        padding=padding,
        justification=justification,
        signed=False,
        export_record_id=export_record_id,
        derivation_code="render-profile-singleton-v1",
        date_format=date_format,
        decimals=decimals,
        value_policy=rule.value_policy,
        allowed_values=allowed_values,
    )


def _render_profile_anchor(joined_field: JoinedRecordDesignField) -> RenderProfileAnchor:
    field = joined_field.parser_field
    return RenderProfileAnchor(
        sheet=field.sheet,
        source_row=field.source_row,
        source_cell=field.source_cell,
        ordinal=field.ordinal,
        record_identity=field.record_identity,
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
    padding: ExportPadding,
    justification: ExportJustification,
    signed: bool,
    export_record_id: str,
    derivation_code: ExportFieldDerivationCode,
    date_format: str | None = None,
    decimals: int | None = None,
    value_policy: ExportValuePolicy | None = None,
    allowed_values: tuple[str, ...] | None = None,
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
                "producer_key": semantic_entry.producer_key,
                "projection_ref": semantic_entry.projection_ref,
                "draft_attribute": semantic_entry.draft_attribute,
                "computed_key": semantic_entry.computed_key,
                "data_type": data_type,
                "required": required,
                "padding": padding,
                "justification": justification,
                "date_format": date_format,
                "decimals": decimals,
                "signed": signed,
                "value_policy": value_policy,
                "allowed_values": allowed_values,
                "legal_refs": semantic_entry.legal_refs,
                "source_refs": semantic_entry.source_refs,
            },
        ),
        normalization_schema_version=EXPORT_RENDER_NORMALIZATION_SCHEMA_VERSION,
        derivation_code=derivation_code,
    )


def _is_required(validation: str | None) -> bool:
    return validation is not None and validation.strip().casefold() == "obligatorio"


def _render_tree_files(
    *,
    revision_id: RevisionId,
    layout: ExportLayoutDefinition,
) -> tuple[tuple[str, bytes], ...]:
    layout_payload = layout.model_dump(mode="json", exclude_none=True)
    records = tuple(layout_payload.pop("records"))
    metadata_payload = {"revisions": {str(revision_id): {"export_layouts": [layout_payload]}}}
    metadata_bytes = _render_toml_bytes("0000-export-layout.toml", metadata_payload)
    _require_reviewable_fragment("0000-export-layout.toml", metadata_bytes)
    rendered_files = [("0000-export-layout.toml", metadata_bytes)]
    planned_paths = {"0000-export-layout.toml"}
    for index, record in enumerate(records, start=1):
        record_id = record.get("id")
        if not isinstance(record_id, str):
            raise RegistryValidationError("validated generated export record has no string id")
        record_parts = _render_record_parts(revision_id=revision_id, layout_id=layout.id, record=record)
        for part, fragment_bytes in enumerate(record_parts, start=1):
            relative_path = _record_relative_path(index, part, record_id)
            if relative_path in planned_paths:
                raise RegistryValidationError(f"generated export path collision at {relative_path!r}")
            planned_paths.add(relative_path)
            rendered_files.append((relative_path, fragment_bytes))
    return tuple(rendered_files)


def _render_record_parts(
    *,
    revision_id: RevisionId,
    layout_id: object,
    record: Mapping[str, object],
) -> tuple[bytes, ...]:
    raw_fields = record.get("fields")
    if not isinstance(raw_fields, list) or not raw_fields:
        raise RegistryValidationError(f"validated generated export record {record.get('id')!r} has no fields")
    fields: list[Mapping[str, object]] = []
    for field in cast(list[object], raw_fields):
        if not isinstance(field, Mapping):
            raise RegistryValidationError(
                f"validated generated export record {record.get('id')!r} contains a non-table field",
            )
        fields.append(cast(Mapping[str, object], field))
    record_without_fields = {key: value for key, value in record.items() if key != "fields"}
    rendered_parts: list[bytes] = []
    current_fields: list[Mapping[str, object]] = []
    for field in fields:
        candidate_fields = [*current_fields, field]
        candidate = _render_record_fragment(
            revision_id=revision_id,
            layout_id=layout_id,
            record={**record_without_fields, "fields": candidate_fields},
        )
        if _is_reviewable_fragment(candidate):
            current_fields = candidate_fields
            continue
        if not current_fields:
            field_id = field.get("id")
            raise RegistryValidationError(
                f"generated export field {field_id!r} cannot fit the repository TOML reviewability baseline",
            )
        rendered_parts.append(
            _render_record_fragment(
                revision_id=revision_id,
                layout_id=layout_id,
                record={**record_without_fields, "fields": current_fields},
            ),
        )
        current_fields = [field]
        candidate = _render_record_fragment(
            revision_id=revision_id,
            layout_id=layout_id,
            record={**record_without_fields, "fields": current_fields},
        )
        if not _is_reviewable_fragment(candidate):
            field_id = field.get("id")
            raise RegistryValidationError(
                f"generated export field {field_id!r} cannot fit the repository TOML reviewability baseline",
            )
    rendered_parts.append(
        _render_record_fragment(
            revision_id=revision_id,
            layout_id=layout_id,
            record={**record_without_fields, "fields": current_fields},
        ),
    )
    return tuple(rendered_parts)


def _render_record_fragment(
    *,
    revision_id: RevisionId,
    layout_id: object,
    record: Mapping[str, object],
) -> bytes:
    return _render_toml_bytes(
        str(record.get("id", "record")),
        {
            "revisions": {
                str(revision_id): {
                    "export_layouts": [
                        {
                            "id": layout_id,
                            "records": [record],
                        },
                    ],
                },
            },
        },
    )


def _render_toml_bytes(relative_path: str, payload: Mapping[str, object]) -> bytes:
    try:
        rendered = rtoml.dumps(payload, pretty=True, none_value=None)
    except (TypeError, ValueError) as exc:
        raise RegistryValidationError(
            f"cannot serialize generated export TOML {relative_path!r}: {exc}",
        ) from exc
    return rendered.encode("utf-8")


def _is_reviewable_fragment(payload: bytes) -> bool:
    lines = payload.decode("utf-8").splitlines()
    return (
        len(lines) <= _MAX_FRAGMENT_LINES and max((len(line) for line in lines), default=0) <= _MAX_FRAGMENT_LINE_CHARS
    )


def _require_reviewable_fragment(relative_path: str, payload: bytes) -> None:
    if not _is_reviewable_fragment(payload):
        raise RegistryValidationError(
            f"generated export TOML {relative_path!r} exceeds the repository reviewability baseline",
        )


def _record_relative_path(index: int, part: int, record_id: object) -> str:
    raw_record_id = str(record_id)
    _require_safe_identifier(raw_record_id, subject="export record id")
    slug = _SLUG_RE.sub("-", raw_record_id.casefold()).strip("-")
    if not slug:
        raise RegistryValidationError(f"export record id {raw_record_id!r} cannot form a stable output slug")
    return f"{index:04d}-record-{slug}-part-{part:03d}.toml"


def _require_semantic_map_attestation(joined: JoinedRecordDesign, semantic_map: SemanticMap) -> None:
    if semantic_map.source_ref != joined.source.source_ref:
        raise RegistryValidationError(
            f"semantic-map source {semantic_map.source_ref!r} does not match joined source "
            f"{joined.source.source_ref!r}",
        )
    if semantic_map.source_sha256 != joined.source.source_sha256:
        raise RegistryValidationError("semantic-map SHA-256 does not match joined official source")
    joined_entries = frozenset(field.semantic_entry for field in joined.fields)
    if len(joined_entries) != len(joined.fields) or joined_entries != frozenset(semantic_map.entries):
        raise RegistryValidationError("joined fields do not attest the supplied complete semantic map")
    joined_records = frozenset(record.semantic_record for record in joined.records)
    if len(joined_records) != len(joined.records) or joined_records != frozenset(semantic_map.records):
        raise RegistryValidationError("joined records do not attest the supplied complete semantic map")


def _require_safe_identifier(value: str, *, subject: str) -> None:
    if not value or value in {".", ".."} or ".." in value or _SAFE_IDENTIFIER_RE.fullmatch(value) is None:
        raise RegistryValidationError(f"{subject} is unsafe for generated export output: {value!r}")


def _sorted_refs(refs: Iterable[object]) -> tuple[str, ...]:
    values = tuple(sorted({str(ref) for ref in refs}))
    if not values:
        raise RegistryValidationError("generated export layout has no reviewed references")
    return values
