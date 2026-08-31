"""Export layout, record, and field validation helpers.

Validates export layouts, records, and fields declared on a
:class:`~cadrumo.domain.calculations.registry.ModeloRevision` for casilla and
binding reference closure.

Export layouts are layout-authority surfaces: every
:class:`~cadrumo.domain.calculations.registry.ExportFieldDefinition` must point at
declared :class:`~cadrumo.core.CasillaId` or
:class:`~cadrumo.domain.calculations.registry.BindingId` values and carry
layout-authority evidence.

Two of the field checks here are about a slot's SHAPE rather than its references,
and belong to the same family as the byte-range overlap check in
:mod:`cadrumo.domain.calculations.registry.export`: a literal may not be longer
than the slot declared for it, and a draft attribute drawn from a typed
fixed-width source must be bound to a slot of exactly that width
(:func:`cadrumo.domain.calculations.registry.validate_export_field_widths.validate_draft_field_slot_width`,
extracted to its own module). Both run at registry build over every
revision, where the overlap check runs at layout resolution -- so a width
contradiction is refused when the registry is validated, not when a taxpayer's
export happens to resolve that one layout.

See Also:
    :func:`cadrumo.domain.calculations.registry.validate_revision_sections.validate_revision_definition`
        Per-revision dispatcher that invokes this export validator.
    :func:`cadrumo.domain.calculations.registry.derive_export_layouts_from_bindings`
        Export-layout derivation path whose generated records must satisfy these
        reference checks.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from pathlib import Path

from ....core.filing_projection_ref import FilingProjectionRef
from ....core.casilla_id import CasillaId
from ....core.aggregation import BindingAggregationOp
from ..export_field_kind import CasillaFieldKind
from ._validate_evidence import EvidenceValidator
from ._validate_export_field_widths import validate_draft_field_slot_width
from ._validate_helpers import missing_refs as _missing_refs
from ._validate_projection_endpoints import (
    validate_projection_endpoint_declarations as _validate_projection_endpoint_declarations,
)
from .binding_aggregation import binding_aggregation_op
from .binding_selector_utils import (
    BindingExportSelector,
    BindingFixedExportSelector,
    binding_export_selector,
)
from .corpus_catalogue import verify_source_file
from .errors import RegistryValidationError
from .ids import BindingId
from .schema import DataBindingDefinition, ModeloRevision
from .schema_exports import (
    AuxiliaryEnvelopeHeaderDefinition,
    ExportFieldDefinition,
    ExportLayoutDefinition,
    ExportRecordDefinition,
    FilingEnvelopeDefinition,
)
from .schema_references import LegalReference, SourceReference
from .schema_surfaces import CasillaDefinition


def validate_export_layout_section(
    *,
    prefix: str,
    revision: ModeloRevision,
    casillas: set[CasillaId],
    bindings: set[BindingId],
    casilla_by_id: Mapping[CasillaId, CasillaDefinition],
    legal_refs: Mapping[str, LegalReference],
    source_refs: Mapping[str, SourceReference],
    evidence: EvidenceValidator,
    source_root: Path | None,
) -> list[str]:
    """Return export layout, record, and field failures.

    The :class:`~cadrumo.domain.calculations.registry.ModeloRevision` supplies
    export layouts. Each layout must carry layout-authority evidence, and each
    nested record/field is validated against declared
    :class:`~cadrumo.domain.calculations.registry.CasillaDefinition` and
    :class:`~cadrumo.domain.calculations.registry.DataBindingDefinition` ids from
    the revision validation context.
    """
    failures: list[str] = []
    for layout in revision.export_layouts:
        owner = f"export {layout.id}"
        failures.extend(_missing_refs(prefix, owner, layout.legal_refs, legal_refs, "legal"))
        failures.extend(_missing_refs(prefix, owner, layout.source_refs, source_refs, "source"))
        failures.extend(evidence.require_source_tier(prefix, owner, layout.source_refs, "layout_authority"))
        _validate_embedded_envelope_source_authority(
            failures,
            prefix=prefix,
            layout=layout,
            source_refs=source_refs,
            source_root=source_root,
        )
        for record in layout.records:
            _validate_export_record(
                failures,
                prefix=prefix,
                revision=revision,
                record=record,
                casillas=casillas,
                bindings=bindings,
                casilla_by_id=casilla_by_id,
                legal_refs=legal_refs,
                source_refs=source_refs,
                evidence=evidence,
            )
    _validate_generated_projection_layout_bijection(failures, prefix=prefix, revision=revision)
    _validate_projection_endpoint_declarations(
        failures,
        prefix=prefix,
        revision=revision,
        casillas=casillas,
        casilla_by_id=casilla_by_id,
        legal_refs=legal_refs,
        source_refs=source_refs,
        evidence=evidence,
    )
    return failures


def _validate_embedded_envelope_source_authority(
    failures: list[str],
    *,
    prefix: str,
    layout: ExportLayoutDefinition,
    source_refs: Mapping[str, SourceReference],
    source_root: Path | None,
) -> None:
    """Bind embedded envelope declarations to a live canonical design source.

    A filing envelope or auxiliary header reproduces source identity and a digest
    inside a generated layout. Merely checking that its ``source_ref`` appears
    among ``layout.source_refs`` leaves two paths for provenance to drift: a
    catalogue entry can be rebound under the same key, or an embedded digest can
    survive after its authoritative source changed. At registry build, require
    the key, entry identity, and digest to agree; when a corpus root is supplied,
    re-hash the exact catalogue entry before composition continues.
    """
    declarations: tuple[tuple[str, FilingEnvelopeDefinition | AuxiliaryEnvelopeHeaderDefinition], ...] = tuple(
        (label, declaration)
        for label, declaration in (
            ("filing envelope", layout.filing_envelope),
            ("auxiliary envelope header", layout.auxiliary_envelope_header),
        )
        if declaration is not None
    )
    for label, declaration in declarations:
        owner = f"export layout {layout.id!r} {label}"
        source = source_refs.get(declaration.source_ref)
        if source is None:
            failures.append(
                f"{prefix}: {owner} source {declaration.source_ref!r} is absent from the canonical source catalogue",
            )
            continue
        if source.id != declaration.source_ref:
            failures.append(
                f"{prefix}: {owner} source catalogue key {declaration.source_ref!r} resolves to source id "
                f"{source.id!r}; embedded source identity must equal its canonical catalogue key",
            )
        if source.kind != "record_design":
            failures.append(
                f"{prefix}: {owner} source {declaration.source_ref!r} is {source.kind!r}, not a record-design source",
            )
        if source.sha256 != declaration.source_sha256:
            failures.append(
                f"{prefix}: {owner} source digest {declaration.source_sha256!r} does not match canonical catalogue "
                f"digest {source.sha256!r} for {declaration.source_ref!r}",
            )
        if source_root is None:
            continue
        try:
            verify_source_file(source_root, source)
        except RegistryValidationError as exc:
            failures.append(
                f"{prefix}: {owner} source {declaration.source_ref!r} fails live canonical re-hash: {exc}",
            )


def _validate_generated_projection_layout_bijection(
    failures: list[str],
    *,
    prefix: str,
    revision: ModeloRevision,
) -> None:
    """Require loaded generated projection fields to exactly match declarations.

    Pre-generation revisions deliberately have no export layouts, so their
    declarations remain valid on their own. Once a layout exists, however, its
    projection fields must be a one-for-one materialisation of the declared
    revision authority.
    """
    if not revision.export_layouts:
        return
    failures.extend(f"{prefix}: {failure}" for failure in _generated_projection_layout_failures(revision))


def _generated_projection_layout_failures(revision: ModeloRevision) -> tuple[str, ...]:
    """Return all projection-layout bijection failures without a revision prefix."""
    generated = _generated_projection_refs(revision)
    if any(reference is None for reference in generated):
        return ("generated projection field lacks a typed projection_ref",)
    generated_refs = tuple(reference for reference in generated if reference is not None)
    declared_refs = tuple(declaration.projection_ref for declaration in revision.projection_endpoints)
    return _projection_layout_failures(generated_refs, declared_refs)


def _projection_layout_failures(
    generated_refs: tuple[FilingProjectionRef, ...],
    declared_refs: tuple[FilingProjectionRef, ...],
) -> tuple[str, ...]:
    """Combine duplicate and set-difference failures for projection identities."""
    return (
        *_duplicate_projection_failure("generated export layouts duplicate projection refs", generated_refs),
        *_duplicate_projection_failure("projection declarations are not unique", declared_refs),
        *_projection_bijection_failure(generated_refs, declared_refs),
    )


def _duplicate_projection_failure(
    message: str,
    references: tuple[FilingProjectionRef, ...],
) -> tuple[str, ...]:
    """Render one duplicate-reference failure, if any."""
    duplicates = _duplicate_projection_refs(references)
    return () if not duplicates else (f"{message}: {duplicates!r}",)


def _projection_bijection_failure(
    generated_refs: tuple[FilingProjectionRef, ...],
    declared_refs: tuple[FilingProjectionRef, ...],
) -> tuple[str, ...]:
    """Render the generated-versus-declared projection set mismatch, if any."""
    missing = tuple(sorted(repr(reference) for reference in set(declared_refs) - set(generated_refs)))
    undeclared = tuple(sorted(repr(reference) for reference in set(generated_refs) - set(declared_refs)))
    if not missing and not undeclared:
        return ()
    return (
        "generated export layouts must exactly biject projection declarations; "
        + _projection_bijection_details(missing, undeclared),
    )


def _generated_projection_refs(revision: ModeloRevision) -> tuple[FilingProjectionRef | None, ...]:
    """Collect the typed projection identities materialised by generated layouts."""
    return tuple(
        field.projection_ref
        for layout in revision.export_layouts
        for record in layout.records
        for field in record.fields
        if field.kind is CasillaFieldKind.PROJECTION
    )


def _duplicate_projection_refs(references: tuple[FilingProjectionRef, ...]) -> tuple[str, ...]:
    """Return duplicate projection identities in deterministic display order."""
    return tuple(
        sorted(repr(reference) for reference, count in Counter(references).items() if count > 1),
    )


def _projection_bijection_details(
    missing: tuple[str, ...],
    undeclared: tuple[str, ...],
) -> str:
    """Format the two possible sides of a projection-bijection mismatch."""
    details: list[str] = []
    if missing:
        details.append(f"missing declared refs {missing!r}")
    if undeclared:
        details.append(f"undeclared generated refs {undeclared!r}")
    return "; ".join(details)


def _validate_export_record(
    failures: list[str],
    *,
    prefix: str,
    revision: ModeloRevision,
    record: ExportRecordDefinition,
    casillas: set[CasillaId],
    bindings: set[BindingId],
    casilla_by_id: Mapping[CasillaId, CasillaDefinition],
    legal_refs: Mapping[str, LegalReference],
    source_refs: Mapping[str, SourceReference],
    evidence: EvidenceValidator,
) -> None:
    """Append failures for one export record declaration.

    The
    :class:`~cadrumo.domain.calculations.registry.schema.ExportRecordDefinition`
    is checked against the selected
    :class:`~cadrumo.domain.calculations.registry.ModeloRevision`, including
    binding-record derivation, positive-casilla gates, row-field casilla ids, and
    nested :class:`~cadrumo.domain.calculations.registry.ExportFieldDefinition`
    rows.
    """
    if record.binding_record is not None:
        _validate_export_record_binding_link(failures, prefix=prefix, revision=revision, record=record)
    if repeat_failure := record.repeat_field_family_failure():
        failures.append(f"{prefix}: export record {record.id!r}: {repeat_failure}")
    if record.requires_positive_casilla_id is not None and record.requires_positive_casilla_id not in casillas:
        failures.append(
            f"{prefix}: export record {record.id!r} requires unknown positive casilla "
            f"{record.requires_positive_casilla_id!r}",
        )
    for row_field, casilla_id in record.row_field_casilla_ids.items():
        if casilla_id not in casillas:
            failures.append(
                f"{prefix}: export record {record.id!r} row_field_casilla_ids.{row_field} "
                f"references unknown casilla {casilla_id!r}",
            )
    for field in record.fields:
        _validate_export_field(
            failures,
            prefix=prefix,
            record=record,
            field=field,
            casillas=casillas,
            bindings=bindings,
            casilla_by_id=casilla_by_id,
            legal_refs=legal_refs,
            source_refs=source_refs,
            evidence=evidence,
        )


def _validate_export_record_binding_link(
    failures: list[str],
    *,
    prefix: str,
    revision: ModeloRevision,
    record: ExportRecordDefinition,
) -> None:
    """Verify a binding-derived export record resolves to selector-closed bindings.

    The :class:`~cadrumo.domain.calculations.registry.ModeloRevision` supplies
    :class:`~cadrumo.domain.calculations.registry.DataBindingDefinition` rows whose
    export selectors may materialise fields for the record's ``binding_record``.
    """
    matching_bindings: list[tuple[DataBindingDefinition, BindingExportSelector]] = []
    for binding in revision.bindings:
        try:
            selector = binding_export_selector(binding, revision=revision)
        except RegistryValidationError as exc:
            failures.append(f"{prefix}: {exc}")
            continue
        if selector is not None and selector.record == record.binding_record:
            matching_bindings.append((binding, selector))
    if not matching_bindings:
        failures.append(
            f"{prefix}: export record {record.id!r} derives fields from unknown binding record "
            f"{record.binding_record!r}",
        )
    for binding, selector in matching_bindings:
        if binding_aggregation_op(binding) == BindingAggregationOp.ROWS:
            continue
        if not isinstance(selector, BindingFixedExportSelector):
            failures.append(
                f"{prefix}: export record {record.id!r} binding {binding.id!r} must declare "
                "a fixed export selector (offset, length, data_type)",
            )


def _validate_export_field(
    failures: list[str],
    *,
    prefix: str,
    record: ExportRecordDefinition,
    field: ExportFieldDefinition,
    casillas: set[CasillaId],
    bindings: set[BindingId],
    casilla_by_id: Mapping[CasillaId, CasillaDefinition],
    legal_refs: Mapping[str, LegalReference],
    source_refs: Mapping[str, SourceReference],
    evidence: EvidenceValidator,
) -> None:
    """Append failures for one export field declaration.

    The :class:`~cadrumo.domain.calculations.registry.ExportFieldDefinition` must
    cite layout-authority refs, target a declared
    :class:`~cadrumo.core.CasillaId` or
    :class:`~cadrumo.domain.calculations.registry.BindingId`, and respect literal
    byte-length constraints for its parent export record encoding.
    """
    _validate_export_field_references(
        failures,
        prefix=prefix,
        record=record,
        field=field,
        casillas=casillas,
        casilla_by_id=casilla_by_id,
        legal_refs=legal_refs,
        source_refs=source_refs,
        evidence=evidence,
    )
    if field.binding is not None and field.binding not in bindings:
        failures.append(f"{prefix}: export field {field.id!r} references unknown binding {field.binding!r}")
    _validate_export_field_literal_length(failures, prefix=prefix, record=record, field=field)
    failures.extend(validate_draft_field_slot_width(prefix=prefix, field=field))


def _validate_export_field_references(
    failures: list[str],
    *,
    prefix: str,
    record: ExportRecordDefinition,
    field: ExportFieldDefinition,
    casillas: set[CasillaId],
    casilla_by_id: Mapping[CasillaId, CasillaDefinition],
    legal_refs: Mapping[str, LegalReference],
    source_refs: Mapping[str, SourceReference],
    evidence: EvidenceValidator,
) -> None:
    """Validate an export field's evidence and casilla ownership references."""
    owner = f"export field {field.id}"
    failures.extend(_missing_refs(prefix, owner, field.legal_refs, legal_refs, "legal"))
    failures.extend(_missing_refs(prefix, owner, field.source_refs, source_refs, "source"))
    failures.extend(evidence.require_source_tier(prefix, owner, field.source_refs, "layout_authority"))
    endpoint_casilla_id = field.endpoint_casilla_id
    if endpoint_casilla_id is not None and endpoint_casilla_id not in casillas:
        failures.append(f"{prefix}: export field {field.id!r} references unknown casilla {endpoint_casilla_id!r}")
    if (
        endpoint_casilla_id is not None
        and endpoint_casilla_id in casilla_by_id
        and field.id not in casilla_by_id[endpoint_casilla_id].export_refs
        and not _is_binding_record_template_field(record, field)
    ):
        failures.append(f"{prefix}: export field {field.id!r} is not declared by casilla {endpoint_casilla_id!r}")


def _validate_export_field_literal_length(
    failures: list[str],
    *,
    prefix: str,
    record: ExportRecordDefinition,
    field: ExportFieldDefinition,
) -> None:
    """Require literal text to fit its declared encoded field width."""
    if field.kind == CasillaFieldKind.LITERAL and field.literal is not None and field.length is not None:
        literal_length = len(field.literal.encode(record.encoding))
        if literal_length > field.length:
            failures.append(
                f"{prefix}: export field {field.id!r} literal length {literal_length} exceeds "
                f"declared length {field.length}",
            )


def _is_binding_record_template_field(record: ExportRecordDefinition, field: ExportFieldDefinition) -> bool:
    return (
        record.binding_record is not None
        and field.kind == CasillaFieldKind.CASILLA
        and field.casilla_id in set(record.row_field_casilla_ids.values())
    )
