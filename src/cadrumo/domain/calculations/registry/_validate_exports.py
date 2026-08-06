"""Export layout, record, and field validation helpers.

Validates export layouts, records, and fields declared on a
:class:`~cadrumo.domain.calculations.registry.ModeloRevision` for casilla and
binding reference closure.

Export layouts are layout-authority surfaces: every
:class:`~cadrumo.domain.calculations.registry.ExportFieldDefinition` must point at
declared :class:`~cadrumo.domain.calculations.registry.CasillaId` or
:class:`~cadrumo.domain.calculations.registry.BindingId` values and carry
layout-authority evidence.

See Also:
    :func:`cadrumo.domain.calculations.registry._validate_revision_sections.validate_revision_definition`
        Per-revision dispatcher that invokes this export validator.
    :func:`cadrumo.domain.calculations.registry.derive_export_layouts_from_bindings`
        Export-layout derivation path whose generated records must satisfy these
        reference checks.
"""

from __future__ import annotations

from collections.abc import Mapping

from ....core.aggregation import BindingAggregationOp
from ._binding_aggregation import binding_aggregation_op
from ._binding_selector_utils import (
    BindingExportSelector,
    BindingFixedExportSelector,
    binding_export_selector,
)
from ._errors import RegistryValidationError
from ._ids import BindingId, CasillaId
from ._schema import (
    CasillaDefinition,
    CasillaFieldKind,
    DataBindingDefinition,
    ExportFieldDefinition,
    ExportRecordDefinition,
    LegalReference,
    ModeloRevision,
    SourceReference,
)
from ._validate_evidence import EvidenceValidator
from ._validate_helpers import missing_refs as _missing_refs


def validate_export_layout_section(
    failures: list[str],
    *,
    prefix: str,
    revision: ModeloRevision,
    casillas: set[CasillaId],
    bindings: set[BindingId],
    casilla_by_id: Mapping[CasillaId, CasillaDefinition],
    legal_refs: Mapping[str, LegalReference],
    source_refs: Mapping[str, SourceReference],
    evidence: EvidenceValidator,
) -> None:
    """Append export layout, record, and field failures.

    The :class:`~cadrumo.domain.calculations.registry.ModeloRevision` supplies
    export layouts. Each layout must carry layout-authority evidence, and each
    nested record/field is validated against declared
    :class:`~cadrumo.domain.calculations.registry.CasillaDefinition` and
    :class:`~cadrumo.domain.calculations.registry.DataBindingDefinition` ids from
    the revision validation context.
    """
    for layout in revision.export_layouts:
        owner = f"export {layout.id}"
        failures.extend(_missing_refs(prefix, owner, layout.legal_refs, legal_refs, "legal"))
        failures.extend(_missing_refs(prefix, owner, layout.source_refs, source_refs, "source"))
        failures.extend(evidence.require_source_tier(prefix, owner, layout.source_refs, "layout_authority"))
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
    :class:`~cadrumo.domain.calculations.registry._schema.ExportRecordDefinition`
    is checked against the selected
    :class:`~cadrumo.domain.calculations.registry.ModeloRevision`, including
    binding-record derivation, positive-casilla gates, row-field casilla ids, and
    nested :class:`~cadrumo.domain.calculations.registry.ExportFieldDefinition`
    rows.
    """
    if record.binding_record is not None:
        _validate_export_record_binding_link(failures, prefix=prefix, revision=revision, record=record)
    if (
        record.repeat == "binding_rows"
        and not any(field.kind == CasillaFieldKind.BINDING for field in record.fields)
        and record.binding_record is None
    ):
        failures.append(f"{prefix}: export record {record.id!r} repeats binding rows but has no binding fields")
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
            selector = binding_export_selector(binding)
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
    :class:`~cadrumo.domain.calculations.registry.CasillaId` or
    :class:`~cadrumo.domain.calculations.registry.BindingId`, and respect literal
    byte-length constraints for its parent export record encoding.
    """
    owner = f"export field {field.id}"
    failures.extend(_missing_refs(prefix, owner, field.legal_refs, legal_refs, "legal"))
    failures.extend(_missing_refs(prefix, owner, field.source_refs, source_refs, "source"))
    failures.extend(evidence.require_source_tier(prefix, owner, field.source_refs, "layout_authority"))
    if field.casilla_id is not None and field.casilla_id not in casillas:
        failures.append(f"{prefix}: export field {field.id!r} references unknown casilla {field.casilla_id!r}")
    if (
        field.casilla_id is not None
        and field.casilla_id in casilla_by_id
        and field.id not in casilla_by_id[field.casilla_id].export_refs
        and not _is_binding_record_template_field(record, field)
    ):
        failures.append(f"{prefix}: export field {field.id!r} is not declared by casilla {field.casilla_id!r}")
    if field.binding is not None and field.binding not in bindings:
        failures.append(f"{prefix}: export field {field.id!r} references unknown binding {field.binding!r}")
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
