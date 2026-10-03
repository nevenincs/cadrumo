"""Deterministic rendering of generated export-fragment directory trees."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from pathlib import Path

from cadrumo.core.directory_scan import iter_directory
from cadrumo.core.link_safety import is_link_like
from cadrumo.domain.calculations.export_field_kind import CasillaFieldKind
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.ids import (
    RevisionId,
)
from cadrumo.domain.calculations.registry.schema_exports import (
    ExportLayoutDefinition,
    ExportRecordDefinition,
    ProjectionEndpointDeclaration,
)

from .export_fragment_provenance import (
    ExportFieldDerivation,
    ExportFragmentTarget,
    attach_field_verdicts,
    emit_export_fragment_provenance_manifest,
)
from .export_tree_field_derivation import _normalise_field
from .export_tree_models import ExportTreeTransportProfile, RenderedExportTree
from .export_tree_serialization import SERIALIZER_CONVENTION, render_tree_files, require_safe_identifier
from .generated_tree_dispositions import type_column_rulings_for
from .joined_record_design import JoinedRecordDesign, JoinedRecordDesignRecord
from .note_literals import NoteLiteralDeclaration, note_literals_for
from .render_profile import validate_render_profile
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
    rendered_files = render_tree_files(revision_id=revision_id, layout=layout)
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
        require_safe_identifier(record_id, subject="export record id")
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
                    "requires_positive_casilla_id": joined_record.semantic_record.requires_positive_casilla_id,
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


def _sorted_refs(refs: Iterable[object]) -> tuple[str, ...]:
    values = tuple(sorted({str(ref) for ref in refs}))
    if not values:
        raise RegistryValidationError("generated export layout has no reviewed references")
    return values
