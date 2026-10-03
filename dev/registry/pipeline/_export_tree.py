"""Deterministic rendering of generated export-fragment directory trees."""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Final, Literal, cast

import rtoml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from cadrumo.core.directory_scan import iter_directory
from cadrumo.core.external_constants import LATIN_1_ENCODING
from cadrumo.core.link_safety import is_link_like
from cadrumo.domain.calculations.export_field_kind import CasillaFieldKind
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.export_value_policy import (
    ExportValuePolicy,
)
from cadrumo.domain.calculations.registry.fixed_width_codec import (
    ExportEncoding,
    ExportJustification,
    ExportPadding,
)
from cadrumo.domain.calculations.registry.ids import (
    ExportLayoutId,
    ModeloId,
    RevisionId,
    SourceRefId,
)
from cadrumo.domain.calculations.registry.schema_exports import (
    ExportLayoutDefinition,
    ExportRecordDefinition,
    ProjectionEndpointDeclaration,
)

from .export_field_derivation import (
    _literal_derivation,
    _numeric_derivation,
    _profile_signed_composite_derivation,
    _render_profile_anchor,
    _render_profile_numeric_derivation,
)
from .export_field_schema import _is_required, _schema_field
from .export_fragment_provenance import (
    ExportFieldDerivation,
    ExportFieldDerivationCode,
    ExportFragmentProvenanceManifest,
    ExportFragmentTarget,
    attach_field_verdicts,
    emit_export_fragment_provenance_manifest,
)
from .generated_tree_dispositions import type_column_rulings_for
from .joined_record_design import JoinedRecordDesign, JoinedRecordDesignField, JoinedRecordDesignRecord, design_view
from .note_literals import NoteLiteralDeclaration, note_literals_for
from .render_profile import validate_render_profile
from .render_profile_eligibility import (
    _has_absent_naturaleza,
    _is_numeric_aeat_type,
    _states_no_wire_fact,
)
from .render_profile_evidence import RenderProfileSourceEvidence
from .render_profile_model import RenderProfile
from .semantic_map import SemanticMap
from .source_defects import (
    NoteGovernedAmountDeclaration,
    NoteStatedApplicabilityDeclaration,
    SourceDefectDeclaration,
    note_governed_amounts_for,
    note_stated_applicability_for,
    validate_note_governed_amount_declarations,
    validate_note_stated_applicability_declarations,
    validate_source_defect_declarations,
)
from .variable_envelope import (
    compile_auxiliary_envelope_header_definition,
    compile_filing_envelope_definition,
)
from .year_constraints import bounded_year_for

SERIALIZER_CONVENTION: Final[Literal["rtoml-pretty-v1"]] = "rtoml-pretty-v1"


_SAFE_IDENTIFIER_RE: Final[re.Pattern[str]] = re.compile(r"^[^/\\\x00-\x1f]+$")


_SLUG_RE: Final[re.Pattern[str]] = re.compile(r"[^a-z0-9]+")


_ENCODING_ALIAS_MAP: Final[Mapping[str, str]] = {
    LATIN_1_ENCODING: "iso-8859-1",
    "latin_1": "iso-8859-1",
    "iso-8859-1": "iso-8859-1",
    "iso_8859_1": "iso-8859-1",
    "cp1252": "cp1252",
    "windows-1252": "cp1252",
    "iso-8859-15": "iso-8859-15",
    "iso_8859_15": "iso-8859-15",
    "latin-9": "iso-8859-15",
}


#: Text naturalezas, split by the naturaleza AEAT names rather than by the
#: vocabulary it names it in. A workbook prints the abbreviation; a PDF design
#: prints the word, which the shipped parser canonicalises to
#: ``Alfanumerico``/``Alfabetico``. Matched accent-folded, so the accented
#: spellings land here too. The split is load-bearing: these two sets are the
#: only thing that distinguishes the two text derivation codes, and reading
#: them as one set keyed on the abbreviation records every PDF-sourced
#: alphabetic field as the ALPHANUMERIC derivation, because the folded word
#: ``alfabetico`` is not the abbreviation ``a``.
_ALPHABETIC_TYPES: Final[frozenset[str]] = frozenset({"a", "alfabetico", "alphabetic"})


_ALPHANUMERIC_TYPES: Final[frozenset[str]] = frozenset({"an", "alfanumerico", "alphanumeric"})


#: A blank run states no text representation to derive one from. Where the
#: semantic map calls such a field a filler it never reaches here; where it
#: calls it a value-bearing field the two disagree, and the caller refuses
#: rather than recording a naturaleza the design does not state.
_BLANK_RUN_TYPES: Final[frozenset[str]] = frozenset({"blancos"})


_MAX_FRAGMENT_LINES: Final[int] = 1_399


_MAX_FRAGMENT_LINE_CHARS: Final[int] = 519


#: Zero-padded width this renderer gives an administrative fragment prefix. It is the
#: single place the width is stated: the same value formats the prefix and checks that
#: the formatting did not overflow, so the guard cannot drift from the format it guards.
_FRAGMENT_PREFIX_DIGITS: Final[int] = 4


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
        if self.encoding.casefold() not in _ENCODING_ALIAS_MAP:
            raise ValueError(f"export tree transport profile declares unsupported encoding {self.encoding!r}")
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
    transport_profile: ExportTreeTransportProfile,
    render_profile: RenderProfile,
    render_profile_source_evidence: RenderProfileSourceEvidence,
    source_defects: tuple[SourceDefectDeclaration, ...] = (),
) -> RenderedExportTree:
    """Render one whole generated ``export/`` tree from its three authorities.

    The caller selects a fresh target owned by the generation transaction.  This
    function does not validate or publish a surrounding revision; those
    responsibilities deliberately remain later generator steps.
    """
    literal_notes, note_governed_amounts, applicability_notes = _validate_render_inputs(
        revision_id=revision_id,
        joined=joined,
        transport_profile=transport_profile,
        render_profile=render_profile,
        render_profile_source_evidence=render_profile_source_evidence,
        source_defects=source_defects,
    )
    records, derivations = _render_records(
        joined.records,
        transport_profile,
        render_profile,
        source_defects=source_defects,
        literal_notes=literal_notes,
        note_governed_amounts=note_governed_amounts,
        applicability_notes=applicability_notes,
    )
    layout, derivations = _build_export_layout(
        revision_id=revision_id,
        joined=joined,
        transport_profile=transport_profile,
        records=records,
        derivations=derivations,
    )
    _require_semantic_map_attestation(joined, semantic_map)
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
    )
    return RenderedExportTree(
        layout=layout,
        field_derivations=tuple(derivations),
        output_files=output_files,
        provenance_manifest=provenance_manifest,
    )


def _validate_render_inputs(
    *,
    revision_id: RevisionId,
    joined: JoinedRecordDesign,
    transport_profile: ExportTreeTransportProfile,
    render_profile: RenderProfile,
    render_profile_source_evidence: RenderProfileSourceEvidence,
    source_defects: tuple[SourceDefectDeclaration, ...],
) -> tuple[
    tuple[NoteLiteralDeclaration, ...],
    tuple[NoteGovernedAmountDeclaration, ...],
    tuple[NoteStatedApplicabilityDeclaration, ...],
]:
    """Validate source-bound inputs and return their exact adjudication sets."""
    _validate_transport_profile(joined, transport_profile)
    validate_source_defect_declarations(source_defects, joined.source)
    literal_notes = note_literals_for(joined.source)
    note_governed_amounts = note_governed_amounts_for(joined.source.source_ref)
    validate_note_governed_amount_declarations(note_governed_amounts, joined.source)
    applicability_notes = note_stated_applicability_for(joined.source.source_ref)
    validate_note_stated_applicability_declarations(applicability_notes, joined.source)
    _require_variable_envelope_contract(revision_id, joined)
    validate_render_profile(render_profile, joined, render_profile_source_evidence)
    return literal_notes, note_governed_amounts, applicability_notes


def _require_variable_envelope_contract(revision_id: RevisionId, joined: JoinedRecordDesign) -> None:
    """Refuse variable records without their exact typed composition contract."""
    if joined.variable_envelopes and joined.variable_envelope_contract is None:
        identities = ", ".join(repr(envelope.record_identity) for envelope in joined.variable_envelopes)
        raise RegistryValidationError(
            "fixed-width export generation refuses variable envelopes without a separately typed and proven "
            f"composition contract: {identities}",
        )
    if joined.variable_envelope_contract is not None and joined.revision_id != revision_id:
        raise RegistryValidationError(
            f"typed filing-envelope target revision {revision_id!r} does not match the "
            f"selected revision {joined.revision_id!r}",
        )


def _build_export_layout(
    *,
    revision_id: RevisionId,
    joined: JoinedRecordDesign,
    transport_profile: ExportTreeTransportProfile,
    records: tuple[ExportRecordDefinition, ...],
    derivations: tuple[ExportFieldDerivation, ...],
) -> tuple[ExportLayoutDefinition, list[ExportFieldDerivation]]:
    """Attach row verdicts and construct the complete validated export layout."""
    reviewed_derivations = list(
        attach_field_verdicts(
            derivations,
            type_column_rulings_for(str(joined.source.source_ref), joined.source.source_sha256),
        ),
    )
    _validate_generated_projection_bijection(tuple(reviewed_derivations), joined.projection_endpoints)
    filing_envelope = _filing_envelope_definition(revision_id, joined, records)
    auxiliary_envelope_header = _auxiliary_envelope_header_definition(joined)
    layout = ExportLayoutDefinition.model_validate(
        {
            "id": transport_profile.layout_id,
            "format": transport_profile.format,
            "source_refs": _sorted_refs(
                (
                    transport_profile.source_ref,
                    *(source for field in reviewed_derivations for source in field.field.source_refs),
                ),
            ),
            "legal_refs": _sorted_refs(legal for field in reviewed_derivations for legal in field.field.legal_refs),
            "records": records,
            "filing_envelope": filing_envelope,
            "auxiliary_envelope_header": auxiliary_envelope_header,
        },
    )
    return layout, reviewed_derivations


def _filing_envelope_definition(
    revision_id: RevisionId,
    joined: JoinedRecordDesign,
    records: tuple[ExportRecordDefinition, ...],
) -> object | None:
    """Compile a filing envelope only when its reviewed contract is present."""
    contract = joined.variable_envelope_contract
    if contract is None:
        return None
    return compile_filing_envelope_definition(
        contract.semantic,
        contract.parser_envelope,
        modelo=str(joined.modelo),
        source=joined.source,
        body_record_ids=tuple(record.id for record in records),
    )


def _auxiliary_envelope_header_definition(joined: JoinedRecordDesign) -> object | None:
    """Compile an auxiliary envelope header only when the source declares one."""
    if not joined.auxiliary_envelope_headers:
        return None
    return compile_auxiliary_envelope_header_definition(joined.auxiliary_envelope_headers, joined.source)


def _validate_generated_projection_bijection(
    derivations: tuple[ExportFieldDerivation, ...],
    declarations: tuple[ProjectionEndpointDeclaration, ...],
) -> None:
    """Refuse a generated layout that differs from revision endpoint authority."""
    generated = _generated_projection_refs(derivations)
    duplicate_generated = _duplicate_projection_refs(generated)
    if duplicate_generated:
        raise RegistryValidationError(
            "generated layout contains duplicate projection declarations: " + ", ".join(duplicate_generated),
        )
    declared = tuple(declaration.projection_ref for declaration in declarations)
    duplicate_declared = _duplicate_projection_refs(declared)
    if duplicate_declared:
        raise RegistryValidationError(
            "revision projection declarations are not unique: " + ", ".join(duplicate_declared),
        )
    _require_projection_bijection(generated, declared)


def _generated_projection_refs(derivations: tuple[ExportFieldDerivation, ...]) -> tuple[object, ...]:
    """Collect generated projection refs after requiring each one is typed."""
    projection_refs = tuple(
        derivation.field.projection_ref
        for derivation in derivations
        if derivation.field.kind is CasillaFieldKind.PROJECTION
    )
    if any(reference is None for reference in projection_refs):
        raise RegistryValidationError("generated projection field must carry a typed projection_ref")
    return tuple(reference for reference in projection_refs if reference is not None)


def _duplicate_projection_refs(references: tuple[object, ...]) -> tuple[str, ...]:
    """Return stable evidence for duplicate projection refs."""
    return tuple(sorted(repr(reference) for reference, count in Counter(references).items() if count > 1))


def _require_projection_bijection(generated: tuple[object, ...], declared: tuple[object, ...]) -> None:
    """Require generated and declared projection references to match exactly."""
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
    if profile.serializer_convention != SERIALIZER_CONVENTION:
        raise RegistryValidationError(
            f"export tree transport profile serializer {profile.serializer_convention!r} is not supported",
        )


def _prepare_target(target_export_dir: Path) -> None:
    if target_export_dir.name != "export":
        raise RegistryValidationError(f"generated export target must be named 'export', got {target_export_dir.name!r}")
    if is_link_like(target_export_dir):
        raise RegistryValidationError(f"generated export target must not be a link: {target_export_dir}")
    if target_export_dir.exists():
        if not target_export_dir.is_dir():
            raise RegistryValidationError(f"generated export target is not a directory: {target_export_dir}")
        if any(iter_directory(target_export_dir)):
            raise RegistryValidationError(f"generated export target is not empty: {target_export_dir}")
    else:
        target_export_dir.mkdir(parents=True)


def _render_records(
    joined_records: tuple[JoinedRecordDesignRecord, ...],
    transport_profile: ExportTreeTransportProfile,
    render_profile: RenderProfile,
    *,
    source_defects: tuple[SourceDefectDeclaration, ...] = (),
    literal_notes: tuple[NoteLiteralDeclaration, ...] = (),
    note_governed_amounts: tuple[NoteGovernedAmountDeclaration, ...] = (),
    applicability_notes: tuple[NoteStatedApplicabilityDeclaration, ...] = (),
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
                source_defects=source_defects,
                literal_notes=literal_notes,
                note_governed_amounts=note_governed_amounts,
                applicability_notes=applicability_notes,
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
                    "binding_record": joined_record.semantic_record.binding_record,
                    # The map carries these as sorted pairs to stay hashable; the
                    # registry record takes the mapping they stand for.
                    "row_field_casilla_ids": dict(joined_record.semantic_record.row_field_casilla_ids),
                    "discriminator": joined_record.semantic_record.discriminator,
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


def _require_exact_record_geometry(joined_record: JoinedRecordDesignRecord) -> None:
    """Require ``joined_record`` to be a complete, exact fixed-width geometry.

    This function's two checks are NOT the same kind of check, even though
    they sit side by side. Read them differently:

    ``declared_total is None`` -- NOT redundant. It is the generator's own
    fixed-width requirement, independent of anything the extractor asserts.
    ``RecordDesignSheet.total_positions`` (``src/cadrumo/domain/calculations/
    registry/_record_design.py``) legitimately stays ``None`` when a workbook
    declares a ``"Variable"`` total -- a real AEAT shape the extractor
    correctly TOLERATES for coverage and other non-export consumers. This
    generator can only emit fixed-width byte-exact export records, so it
    correctly REFUSES that same design. A variable-total design passing the
    extractor and failing here is intended behaviour. Do not weaken or
    remove this check, and do not push it down into the extractor -- that
    would force every extractor consumer to need a fixed total, breaking the
    variable-envelope path.

    The offset-contiguity loop below IS redundant, but only conditionally.
    ``joined_record.fields`` reaches this function via a zero-transformation
    pipeline: ``extract_record_design`` (the same extractor, which already
    runs this identical check unconditionally on every field) ->
    ``record_design_intermediate.py``'s ``_intermediate_sheet`` (a straight 1:1
    projection, offset/length unchanged, order preserved) ->
    ``joined_record_design.py``'s ``_join_record_design_semantics`` (wraps
    each field once more, still unreordered, unfiltered). Given that chain,
    this loop can never actually fire differently from the extractor's own
    check -- it is a backstop over an already-guaranteed invariant, kept
    deliberately rather than deleted, because the guarantee holds only as
    long as every hop in that chain stays transformation-free. If a future
    change ever reorders, filters, or recomputes fields anywhere in that
    pipeline, this loop is what would catch it; nobody adding such a
    transformation later would think to re-add a check that looks like
    established duplication today. Do not "clean up" this loop as
    redundant with the ``declared_total`` check above -- they are not the
    same kind of check, and only this one is safe to remove if the pipeline
    it depends on ever changes.
    """
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
        # A declared part stands in for its share of the cell it divides.
        part = joined_field.semantic_entry.part
        offset, length = (part.offset, part.length) if part is not None else (parser_field.offset, parser_field.length)
        if offset != expected_offset:
            defect = "an overlap" if offset < expected_offset else "a gap"
            raise RegistryValidationError(
                f"official record {joined_record.parser_sheet.record_identity!r} has {defect} before "
                f"field {parser_field.source_cell!r}: expected offset {expected_offset}, "
                f"got {offset}",
            )
        expected_offset = offset + length

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
    source_defects: tuple[SourceDefectDeclaration, ...] = (),
    literal_notes: tuple[NoteLiteralDeclaration, ...] = (),
    note_governed_amounts: tuple[NoteGovernedAmountDeclaration, ...] = (),
    applicability_notes: tuple[NoteStatedApplicabilityDeclaration, ...] = (),
) -> ExportFieldDerivation:
    """Derive one emitted field, deriving a declared part from its own printed text.

    A part is derived exactly as a whole cell carrying the part's offset,
    length, type and statement would be, so it earns no reading a printed cell
    could not. The derivation then records the real parser row beside the part
    it filled, and re-validates, so the attested coordinates are the part's.
    """
    part = joined_field.semantic_entry.part
    if part is None:
        return _normalise_cell(
            joined_field,
            transport_profile,
            render_profile,
            export_record_id=export_record_id,
            source_defects=source_defects,
            literal_notes=literal_notes,
            note_governed_amounts=note_governed_amounts,
            applicability_notes=applicability_notes,
        )
    view = joined_field.model_copy(update={"parser_field": design_view(joined_field)})
    derived = _normalise_cell(
        view,
        transport_profile,
        render_profile,
        export_record_id=export_record_id,
        source_defects=source_defects,
        literal_notes=literal_notes,
        note_governed_amounts=note_governed_amounts,
        applicability_notes=applicability_notes,
    )
    return ExportFieldDerivation.model_validate(
        {
            "export_record_id": derived.export_record_id,
            "parser_field": joined_field.parser_field,
            "semantic_entry": derived.semantic_entry,
            "field": derived.field,
            "normalization_schema_version": derived.normalization_schema_version,
            "derivation_code": derived.derivation_code,
            "verdict": derived.verdict,
        },
    )


def _normalise_cell(
    joined_field: JoinedRecordDesignField,
    transport_profile: ExportTreeTransportProfile,
    render_profile: RenderProfile,
    *,
    export_record_id: str,
    source_defects: tuple[SourceDefectDeclaration, ...] = (),
    literal_notes: tuple[NoteLiteralDeclaration, ...] = (),
    note_governed_amounts: tuple[NoteGovernedAmountDeclaration, ...] = (),
    applicability_notes: tuple[NoteStatedApplicabilityDeclaration, ...] = (),
) -> ExportFieldDerivation:
    semantic_entry = joined_field.semantic_entry
    _require_safe_identifier(str(semantic_entry.export_field_id), subject="export field id")
    year_derivation = _source_bounded_year_derivation(
        joined_field,
        transport_profile,
        render_profile,
        export_record_id=export_record_id,
    )
    if year_derivation is not None:
        return year_derivation
    return _derive_declared_field(
        joined_field,
        transport_profile,
        render_profile,
        export_record_id=export_record_id,
        source_defects=source_defects,
        literal_notes=literal_notes,
        note_governed_amounts=note_governed_amounts,
        applicability_notes=applicability_notes,
    )


def _source_bounded_year_derivation(
    joined_field: JoinedRecordDesignField,
    transport_profile: ExportTreeTransportProfile,
    render_profile: RenderProfile,
    *,
    export_record_id: str,
) -> ExportFieldDerivation | None:
    """Derive an exact source-bounded filing year before ordinary field routing."""
    parser_field = joined_field.parser_field
    semantic_entry = joined_field.semantic_entry
    year_constraint = bounded_year_for(
        source_ref=str(transport_profile.source_ref),
        source_sha256=transport_profile.source_sha256,
        sheet=parser_field.sheet,
        source_cell=parser_field.source_cell,
        published_statement=parser_field.content,
    )
    if year_constraint is None:
        return None
    if not (
        parser_field.aeat_type.casefold() == "num"
        and parser_field.length == 4
        and semantic_entry.kind is CasillaFieldKind.DRAFT
        and semantic_entry.draft_attribute == "filing_year"
    ):
        raise RegistryValidationError("source-bounded year requires a four-position Num draft filing_year field")
    year_rule = render_profile.singleton_rule_by_anchor.get(_render_profile_anchor(joined_field))
    if year_rule is None or year_rule.value_policy is not ExportValuePolicy.FOUR_DIGIT_YEAR:
        raise RegistryValidationError("source-bounded year requires an exact reviewed four-digit-year rule")
    return _schema_field(
        joined_field,
        data_type="integer",
        required=_is_required(parser_field.validation),
        padding=ExportPadding.LEFT_ZERO,
        justification=ExportJustification.RIGHT,
        signed=False,
        export_record_id=export_record_id,
        value_policy=ExportValuePolicy.FOUR_DIGIT_YEAR,
        minimum_year=year_constraint.minimum_year,
        derivation_code="numeric-source-bounded-year-v1",
    )


def _derive_declared_field(
    joined_field: JoinedRecordDesignField,
    transport_profile: ExportTreeTransportProfile,
    render_profile: RenderProfile,
    *,
    export_record_id: str,
    source_defects: tuple[SourceDefectDeclaration, ...],
    literal_notes: tuple[NoteLiteralDeclaration, ...],
    note_governed_amounts: tuple[NoteGovernedAmountDeclaration, ...],
    applicability_notes: tuple[NoteStatedApplicabilityDeclaration, ...],
) -> ExportFieldDerivation:
    semantic_entry = joined_field.semantic_entry
    if semantic_entry.kind is CasillaFieldKind.LITERAL:
        return _literal_derivation(
            joined_field,
            encoding=transport_profile.encoding,
            render_profile=render_profile,
            export_record_id=export_record_id,
            source_defects=source_defects,
            literal_notes=literal_notes,
        )
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
    return _derive_by_aeat_type(
        joined_field,
        render_profile,
        export_record_id=export_record_id,
        note_governed_amounts=note_governed_amounts,
        applicability_notes=applicability_notes,
    )


def _derive_by_aeat_type(
    joined_field: JoinedRecordDesignField,
    render_profile: RenderProfile,
    *,
    export_record_id: str,
    note_governed_amounts: tuple[NoteGovernedAmountDeclaration, ...],
    applicability_notes: tuple[NoteStatedApplicabilityDeclaration, ...],
) -> ExportFieldDerivation:
    parser_field = joined_field.parser_field
    semantic_entry = joined_field.semantic_entry
    type_code = (
        unicodedata.normalize("NFKD", parser_field.aeat_type.strip())
        .encode("ascii", "ignore")
        .decode("ascii")
        .casefold()
    )
    if type_code in _BLANK_RUN_TYPES:
        raise RegistryValidationError(
            f"official field {semantic_entry.export_field_id!r} declares blank-run naturaleza "
            f"{parser_field.aeat_type!r}, which states no text representation, but the semantic "
            f"map does not declare it a filler",
        )
    if type_code in _ALPHABETIC_TYPES or type_code in _ALPHANUMERIC_TYPES:
        return _text_field_derivation(
            joined_field,
            render_profile,
            type_code,
            export_record_id=export_record_id,
        )
    if _is_numeric_aeat_type(parser_field.aeat_type):
        return _numeric_field_derivation(
            joined_field,
            render_profile,
            export_record_id=export_record_id,
            note_governed_amounts=note_governed_amounts,
            applicability_notes=applicability_notes,
        )
    if _has_absent_naturaleza(parser_field):
        # The official design printed no naturaleza, so there is nothing to
        # derive a representation from; the reviewed profile governs this field.
        return _render_profile_numeric_derivation(
            joined_field,
            render_profile,
            export_record_id=export_record_id,
        )
    raise RegistryValidationError(
        f"official field {semantic_entry.export_field_id!r} declares unsupported AEAT type {parser_field.aeat_type!r}",
    )


def _text_field_derivation(
    joined_field: JoinedRecordDesignField,
    render_profile: RenderProfile,
    type_code: str,
    *,
    export_record_id: str,
) -> ExportFieldDerivation:
    composite = next(
        (rule for rule in render_profile.signed_composite_rules if rule.anchor == _render_profile_anchor(joined_field)),
        None,
    )
    if composite is not None:
        return _profile_signed_composite_derivation(
            joined_field,
            composite,
            export_record_id=export_record_id,
        )
    derivation_code: ExportFieldDerivationCode = "text-a-v1" if type_code in _ALPHABETIC_TYPES else "text-an-v1"
    return _schema_field(
        joined_field,
        data_type="text",
        required=_is_required(joined_field.parser_field.validation),
        padding=ExportPadding.RIGHT_SPACE,
        justification=ExportJustification.LEFT,
        signed=False,
        export_record_id=export_record_id,
        derivation_code=derivation_code,
    )


def _numeric_field_derivation(
    joined_field: JoinedRecordDesignField,
    render_profile: RenderProfile,
    *,
    export_record_id: str,
    note_governed_amounts: tuple[NoteGovernedAmountDeclaration, ...],
    applicability_notes: tuple[NoteStatedApplicabilityDeclaration, ...],
) -> ExportFieldDerivation:
    parser_field = joined_field.parser_field
    # Use the profile's same applicability-aware predicate as its eligibility
    # check, so the renderer and profile agree about cells that state no wire fact.
    if _states_no_wire_fact(parser_field, applicability_notes=applicability_notes):
        return _render_profile_numeric_derivation(
            joined_field,
            render_profile,
            export_record_id=export_record_id,
        )
    return _numeric_derivation(
        joined_field,
        export_record_id=export_record_id,
        note_governed_amounts=note_governed_amounts,
    )


def _render_tree_files(
    *,
    revision_id: RevisionId,
    layout: ExportLayoutDefinition,
) -> tuple[tuple[str, bytes], ...]:
    layout_payload = layout.model_dump(mode="json", exclude_none=True)
    records = tuple(layout_payload.pop("records"))
    metadata_payload = {"revisions": {str(revision_id): {"export_layouts": [layout_payload]}}}
    metadata_bytes = render_toml_bytes("0000-export-layout.toml", metadata_payload)
    _require_reviewable_fragment("0000-export-layout.toml", metadata_bytes)
    rendered_files = [("0000-export-layout.toml", metadata_bytes)]
    planned_paths = {"0000-export-layout.toml"}
    # One prefix per emitted fragment, not per record. A partitioned record occupies
    # several consecutive prefixes: the loader admits one fragment per administrative
    # prefix, and merges records in prefix order, so the prefix sequence is what makes
    # field order survive the round trip.
    prefix = 0
    for record in records:
        record_id = record.get("id")
        if not isinstance(record_id, str):
            raise RegistryValidationError("validated generated export record has no string id")
        record_parts = _render_record_parts(revision_id=revision_id, layout_id=layout.id, record=record)
        for fragment_bytes in record_parts:
            prefix += 1
            relative_path = _record_relative_path(prefix, record_id)
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
    fields = _require_record_fields(record)
    record_without_fields = {key: value for key, value in record.items() if key != "fields"}
    rendered_parts: list[bytes] = []
    current_fields: list[Mapping[str, object]] = []
    for field in fields:
        current_fields, completed_part = _append_reviewable_record_field(
            revision_id=revision_id,
            layout_id=layout_id,
            record_without_fields=record_without_fields,
            current_fields=current_fields,
            field=field,
        )
        if completed_part is not None:
            rendered_parts.append(completed_part)
    rendered_parts.append(
        _render_record_fragment(
            revision_id=revision_id,
            layout_id=layout_id,
            record={**record_without_fields, "fields": current_fields},
        ),
    )
    return tuple(rendered_parts)


def _require_record_fields(record: Mapping[str, object]) -> list[Mapping[str, object]]:
    """Require a nonempty validated record field table and preserve its order."""
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
    return fields


def _append_reviewable_record_field(
    *,
    revision_id: RevisionId,
    layout_id: object,
    record_without_fields: Mapping[str, object],
    current_fields: list[Mapping[str, object]],
    field: Mapping[str, object],
) -> tuple[list[Mapping[str, object]], bytes | None]:
    """Append one field or close the current reviewable record fragment."""
    candidate_fields: list[Mapping[str, object]] = [*current_fields, field]
    candidate = _render_record_fragment(
        revision_id=revision_id,
        layout_id=layout_id,
        record={**record_without_fields, "fields": candidate_fields},
    )
    if _is_reviewable_fragment(candidate):
        return candidate_fields, None
    if not current_fields:
        _raise_field_exceeds_reviewability(field)
    completed_part = _render_record_fragment(
        revision_id=revision_id,
        layout_id=layout_id,
        record={**record_without_fields, "fields": current_fields},
    )
    next_fields = [field]
    candidate = _render_record_fragment(
        revision_id=revision_id,
        layout_id=layout_id,
        record={**record_without_fields, "fields": next_fields},
    )
    if not _is_reviewable_fragment(candidate):
        _raise_field_exceeds_reviewability(field)
    return next_fields, completed_part


def _raise_field_exceeds_reviewability(field: Mapping[str, object]) -> None:
    field_id = field.get("id")
    raise RegistryValidationError(
        f"generated export field {field_id!r} cannot fit the repository TOML reviewability baseline",
    )


def _render_record_fragment(
    *,
    revision_id: RevisionId,
    layout_id: object,
    record: Mapping[str, object],
) -> bytes:
    return render_toml_bytes(
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


def render_toml_bytes(relative_path: str, payload: Mapping[str, object]) -> bytes:
    try:
        rendered = rtoml.dumps(_order_toml_values_before_tables(payload), pretty=True, none_value=None)
    except (TypeError, ValueError) as exc:
        # rtoml raises TomlSerializationError (a ValueError subclass) whose sole
        # ``args[0]`` bakes the offending value's own ``repr`` into the message,
        # with no structured field that omits it -- measured:
        # ``rtoml.dumps({"bad": Foo()})`` produces "<Foo object at 0x...> (Foo)
        # is not serializable to TOML". Unlike ``json.dumps``'s purely
        # positional "Object of type X is not JSON serializable", there is no
        # accessor here that separates the offending value from the message, so
        # this refusal names only the exception's type, never its rendered text.
        raise RegistryValidationError(
            f"cannot serialize generated export TOML {relative_path!r}: {type(exc).__name__} refused the payload",
        ) from exc
    return rendered.encode("utf-8")


def _order_toml_values_before_tables(value: object) -> object:
    """Recursively order scalars before TOML tables and arrays of tables.

    The generated M303 declaration introduces a nested prefix-field table.
    ``rtoml`` correctly requires every scalar in that declaration to be
    emitted before the nested table, so preserve values while presenting its
    serializer a valid TOML order.
    """
    if isinstance(value, Mapping):
        # Partitioned in ONE pass: the shape test was evaluated twice per item,
        # once to reject it from the scalars and again to admit it to the
        # tables, and this recursion reaches every node of every generated
        # tree -- 8.9M calls for one modelo.
        values: list[tuple[str, object]] = []
        tables: list[tuple[str, object]] = []
        for key, item in value.items():
            ordered = _order_toml_values_before_tables(item)
            (tables if _toml_table_like(ordered) else values).append((str(key), ordered))
        return dict((*values, *tables))
    if isinstance(value, list):
        return [_order_toml_values_before_tables(item) for item in value]
    if isinstance(value, tuple):
        return [_order_toml_values_before_tables(item) for item in value]
    return value


def _toml_table_like(value: object) -> bool:
    """Return whether TOML must emit ``value`` as a table-shaped value."""
    if isinstance(value, Mapping):
        return True
    return isinstance(value, list) and any(isinstance(item, Mapping) for item in value)


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


def _record_relative_path(prefix: int, record_id: object) -> str:
    """Return the fragment filename for one rendered record part.

    The administrative prefix carries the whole ordering, so the filename states no
    second one: a partitioned record appears as consecutive prefixes sharing a slug.
    """
    raw_record_id = str(record_id)
    _require_safe_identifier(raw_record_id, subject="export record id")
    slug = _SLUG_RE.sub("-", raw_record_id.casefold()).strip("-")
    if not slug:
        raise RegistryValidationError(f"export record id {raw_record_id!r} cannot form a stable output slug")
    rendered_prefix = f"{prefix:0{_FRAGMENT_PREFIX_DIGITS}d}"
    if len(rendered_prefix) != _FRAGMENT_PREFIX_DIGITS:
        raise RegistryValidationError(
            f"generated export record {raw_record_id!r} needs fragment prefix {prefix}, which overflows the "
            f"{_FRAGMENT_PREFIX_DIGITS}-digit prefix width; an overflowed prefix does not sort late, it stops "
            "being a readable fragment name",
        )
    return f"{rendered_prefix}-record-{slug}.toml"


def _require_semantic_map_attestation(joined: JoinedRecordDesign, semantic_map: SemanticMap) -> None:
    compiled_map = _require_semantic_map_source(joined, semantic_map)
    _require_semantic_map_identity(joined, semantic_map, compiled_map)
    _require_semantic_map_entries(joined, compiled_map)
    _require_semantic_map_records(joined, compiled_map)


def _require_semantic_map_source(joined: JoinedRecordDesign, semantic_map: SemanticMap) -> SemanticMap:
    """Require the supplied map attests the joined source bytes."""
    if semantic_map.source_ref != joined.source.source_ref:
        raise RegistryValidationError(
            f"semantic-map source {semantic_map.source_ref!r} does not match joined source "
            f"{joined.source.source_ref!r}",
        )
    if semantic_map.source_sha256 != joined.source.source_sha256:
        raise RegistryValidationError("semantic-map SHA-256 does not match joined official source")
    return joined.compiled_semantic_map or semantic_map


def _require_semantic_map_identity(
    joined: JoinedRecordDesign,
    semantic_map: SemanticMap,
    compiled_map: SemanticMap,
) -> None:
    """Require an authored map or its compiled form agrees with the caller."""
    if (
        joined.authored_semantic_map is not None
        and semantic_map != joined.authored_semantic_map
        and semantic_map != compiled_map
    ):
        raise RegistryValidationError("joined fields do not attest the supplied semantic map")


def _require_semantic_map_entries(joined: JoinedRecordDesign, compiled_map: SemanticMap) -> None:
    """Require joined fields cover every compiled semantic entry exactly once."""
    joined_entries = frozenset(field.semantic_entry for field in joined.fields)
    if len(joined_entries) != len(joined.fields) or joined_entries != frozenset(compiled_map.entries):
        raise RegistryValidationError("joined fields do not attest the supplied complete semantic map")


def _require_semantic_map_records(joined: JoinedRecordDesign, compiled_map: SemanticMap) -> None:
    """Require joined records cover every compiled semantic record exactly once."""
    joined_records = frozenset(record.semantic_record for record in joined.records)
    if len(joined_records) != len(joined.records) or joined_records != frozenset(compiled_map.records):
        raise RegistryValidationError("joined records do not attest the supplied complete semantic map")


def _require_safe_identifier(value: str, *, subject: str) -> None:
    if not value or value in {".", ".."} or ".." in value or _SAFE_IDENTIFIER_RE.fullmatch(value) is None:
        raise RegistryValidationError(f"{subject} is unsafe for generated export output: {value!r}")


def _sorted_refs(refs: Iterable[object]) -> tuple[str, ...]:
    values = tuple(sorted({str(ref) for ref in refs}))
    if not values:
        raise RegistryValidationError("generated export layout has no reviewed references")
    return values
