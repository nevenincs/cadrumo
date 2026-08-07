"""Export layout, record, and field validation helpers.

Validates export layouts, records, and fields declared on a
:class:`~cadrumo.domain.calculations.registry.ModeloRevision` for casilla and
binding reference closure.

Export layouts are layout-authority surfaces: every
:class:`~cadrumo.domain.calculations.registry.ExportFieldDefinition` must point at
declared :class:`~cadrumo.domain.calculations.registry.CasillaId` or
:class:`~cadrumo.domain.calculations.registry.BindingId` values and carry
layout-authority evidence.

Two of the field checks here are about a slot's SHAPE rather than its references,
and belong to the same family as the byte-range overlap check in
:mod:`cadrumo.domain.calculations.registry._export`: a literal may not be longer
than the slot declared for it, and a draft attribute drawn from a typed
fixed-width source must be bound to a slot of exactly that width
(:func:`_validate_draft_field_slot_width`). Both run at registry build over every
revision, where the overlap check runs at layout resolution -- so a width
contradiction is refused when the registry is validated, not when a taxpayer's
export happens to resolve that one layout.

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
from ....core.identity import SPANISH_TAX_ID_WIDTH
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

#: Canonical character width of every export ``draft_attribute`` whose value is
#: supplied by a typed, fixed-width domain source, keyed by the attribute token
#: :class:`~cadrumo.domain.calculations.registry.ExportFieldDefinition` declares.
#:
#: A ``None`` entry means "deliberately not width-gated", which is a different
#: claim from "not considered": the mapping is required to be TOTAL over the
#: declarable attributes, so adding an attribute without ruling on its width
#: fails validation rather than passing silently. That totality is what keeps the
#: check keyed on the property instead of on the fields that happen to exist now.
_DRAFT_ATTRIBUTE_CANONICAL_WIDTHS: Mapping[str, int | None] = {
    # Every value routes through validate_spanish_tax_id, which refuses any
    # identifier that is not exactly this wide, so a slot of a different width
    # cannot be holding the declarant's own identifier. A WIDER AEAT slot at some
    # offset is the tell that the slot belongs to a different party: Modelo 200's
    # page 001B position 141 is 15 wide because it holds the foreign tax
    # identification number of a mercantile group's ultimate parent company, and
    # binding the declarant there declares the filer to be its own parent.
    "profile_tax_id": SPANISH_TAX_ID_WIDTH,
    # The remaining attributes abstain, and each abstention has its own reason
    # rather than a shared "these vary" claim. Recorded per attribute because an
    # abstention that cites the wrong reason is worse than none: it reads as a
    # ruling that the slot widths are legitimately diverse when at least one of
    # them is not.
    #
    # No declaration in the registry binds either of these, so no width is
    # observable to gate against and any value chosen here would be invented.
    "modelo": None,
    "period": None,
    # ABSTAINS OVER A KNOWN DIVERGENCE, not over legitimate variability. The
    # source is str(period.filing_year), always 4 characters, and the registry
    # binds 4 in every declaration but one: Modelo 200's page-000 envelope-open
    # record binds it to a 17-character slot. 17 is the width of the whole
    # envelope-open tag, which the sibling modelos compose from a literal "<T",
    # the modelo code, a page digit, the year, the period token and a literal
    # "0000>" -- six or seven fields, not one. That declaration is suspected
    # wrong, and gating this attribute at 4 would refuse the registry build until
    # it is restructured, which needs its own decision and its own byte-level
    # verification of the emitted tag. Until then the gate is deliberately
    # silent HERE, so the divergence must stay recorded elsewhere to be found.
    "filing_year": None,
    # Uniform at 2 across every declaration, so this one is gateable on the
    # evidence; it abstains only because the token's width has not been
    # established against the published diseños, and a period token is the axis
    # where a per-period-kind width difference would be plausible.
    "period_code": None,
}


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
    _validate_draft_field_slot_width(failures, prefix=prefix, field=field)


def _validate_draft_field_slot_width(
    failures: list[str],
    *,
    prefix: str,
    field: ExportFieldDefinition,
) -> None:
    """Append a failure when a draft field's slot width contradicts its typed source.

    The slot-semantics sibling of the byte-range overlap check in
    :func:`cadrumo.domain.calculations.registry._export._reject_overlapping_ranges`.
    Overlap asks whether two fields claim the same bytes; this asks whether the
    bytes one field claims can hold what its ``draft_attribute`` supplies. Neither
    can check that a slot's MEANING matches AEAT's published record design, but a
    width contradiction is detectable without consulting that design at all: when
    the attribute's source is a typed value of fixed width, a slot of some other
    width is holding a different value than the attribute yields.

    That is the shape of a real defect this catches. Modelo 200 bound the
    declarant's own :data:`~core.identity.SubjectTaxId` into a 15-wide slot the
    diseño reserves for a group parent's foreign tax identification number, and
    every export right-padded the filer's identifier into another entity's field.

    Args:
        failures: Accumulator the caller reports; this validator never raises, so
            one build surfaces every offending field rather than the first.
        prefix: Diagnostic prefix naming the modelo and revision under validation.
        field: The
            :class:`~cadrumo.domain.calculations.registry.ExportFieldDefinition`
            to check. Non-draft fields and logical-only fields return unchecked.
    """
    if field.kind != CasillaFieldKind.DRAFT or field.draft_attribute is None:
        return
    if field.draft_attribute not in _DRAFT_ATTRIBUTE_CANONICAL_WIDTHS:
        failures.append(
            f"{prefix}: export field {field.id!r} binds draft attribute {field.draft_attribute!r}, "
            "which declares no canonical-width ruling; give it a width or record it as "
            "explicitly not width-gated",
        )
        return
    canonical_width = _DRAFT_ATTRIBUTE_CANONICAL_WIDTHS[field.draft_attribute]
    if canonical_width is None or field.length is None:
        return
    if field.length != canonical_width:
        failures.append(
            f"{prefix}: export field {field.id!r} binds draft attribute {field.draft_attribute!r}, "
            f"whose typed source is exactly {canonical_width} characters, to a slot of length "
            f"{field.length}; a slot of that width holds a different value than the attribute "
            "supplies, so either the slot belongs to another party or the binding is wrong",
        )


def _is_binding_record_template_field(record: ExportRecordDefinition, field: ExportFieldDefinition) -> bool:
    return (
        record.binding_record is not None
        and field.kind == CasillaFieldKind.CASILLA
        and field.casilla_id in set(record.row_field_casilla_ids.values())
    )
