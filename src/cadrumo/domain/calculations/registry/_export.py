"""Resolved export layouts for registry-backed AEAT record designs.

Resolves export layouts declared on a :class:`ModeloRevision` and verifies
them against a :class:`RegistrySnapshot`. The resolved layout is a
``ResolvedExportLayout`` ready for fixed-width filing assembly.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

from ....core import (
    CasillaId,
    EstadoCasillaOficial,
    ExportExemptionReason,
    ExportLayoutFormat,
    filing_projection_ref_casilla_id,
)
from ....core.aggregation import BindingAggregationOp
from ._binding_aggregation import binding_aggregation_op
from ._binding_selector_utils import (
    BindingExportDataType,
    BindingExportSelector,
    BindingFixedExportSelector,
    BindingRowExportSelector,
    binding_export_selector,
)
from ._casilla_membership import casillas_by_id
from ._errors import RegistryValidationError
from ._export_parse import xml_dictionary_entries
from ._fixed_width_codec import ExportJustification, ExportPadding
from ._ids import ExportFieldId
from ._schema import (
    CasillaFieldKind,
    DataBindingDefinition,
    ExportFieldDefinition,
    ExportLayoutDefinition,
    ExportRecordDefinition,
    ModeloRevision,
    RegistryModel,
    RegistrySnapshot,
    SourceReference,
)

_BindingExportMember = tuple[DataBindingDefinition, BindingExportSelector]


class ResolvedExportLayout(RegistryModel):
    """A selected, validated export layout ready for read-only filing assembly."""

    layout: ExportLayoutDefinition
    ordered_fields: tuple[ExportFieldDefinition, ...]
    fields_by_id: Mapping[ExportFieldId, ExportFieldDefinition]
    fields_by_casilla: Mapping[CasillaId, tuple[ExportFieldDefinition, ...]]


def resolve_export_layout(snapshot: RegistrySnapshot, layout_id: str | None = None) -> ResolvedExportLayout:
    """Resolve one export layout from a validated registry snapshot.

    Args:
        snapshot: The :class:`RegistrySnapshot` to resolve the layout from.
        layout_id: Identifier of the export layout to resolve. May be ``None``
            when the revision declares exactly one layout; otherwise required
            to disambiguate.

    Returns:
        The :class:`ResolvedExportLayout` for the selected layout.
    """
    layouts = snapshot.revision.export_layouts
    if not layouts:
        raise RegistryValidationError(f"modelo {snapshot.modelo.id} revision {snapshot.revision.id} has no exports")
    if layout_id is None:
        if len(layouts) != 1:
            available = sorted(layout.id for layout in layouts)
            raise RegistryValidationError(f"export layout id is required; available layouts: {available!r}")
        layout = layouts[0]
    else:
        matches = [candidate for candidate in layouts if candidate.id == layout_id]
        if not matches:
            available = sorted(candidate.id for candidate in layouts)
            raise RegistryValidationError(f"unknown export layout {layout_id!r}; available layouts: {available!r}")
        layout = matches[0]

    _verify_layout_evidence(snapshot, layout)
    fields = _ordered_fields(layout)
    fields_by_id = _index_fields(layout, fields)
    fields_by_casilla = _index_fields_by_casilla(snapshot, fields)
    _verify_record_offsets(layout)
    return ResolvedExportLayout(
        layout=layout,
        ordered_fields=fields,
        fields_by_id=fields_by_id,
        fields_by_casilla=fields_by_casilla,
    )


def derive_export_layouts_from_bindings(revision: ModeloRevision) -> tuple[ExportLayoutDefinition, ...]:
    """Return revision export layouts with binding-derived fields resolved.

    Some official AEAT record designs expose structured filing records that are
    already represented as registry bindings. In those cases the export layout
    declares the record-level intent via ``binding_record`` and this resolver
    derives field coordinates from the binding selectors instead of requiring a
    second coordinate table in TOML.

    Args:
        revision: The :class:`ModeloRevision` whose export layouts and bindings
            are used to derive the resolved field coordinates.

    Returns:
        Tuple of :class:`ExportLayoutDefinition` with binding-derived fields populated.
    """
    if not revision.export_layouts:
        return ()
    bindings_by_record: dict[str, list[_BindingExportMember]] = {}
    for binding in revision.bindings:
        selector = binding_export_selector(binding, revision=revision)
        if selector is None:
            continue
        bindings_by_record.setdefault(selector.record, []).append((binding, selector))

    resolved_layouts: list[ExportLayoutDefinition] = []
    for layout in revision.export_layouts:
        resolved_records: list[ExportRecordDefinition] = []
        for record in layout.records:
            if record.binding_record is None:
                resolved_records.append(record)
                continue
            derived = tuple(
                sorted(
                    _export_fields_from_record_bindings(record, bindings_by_record.get(record.binding_record, [])),
                    key=lambda field: (field.offset, field.id),
                ),
            )
            base_fields = tuple(
                field
                for field in record.fields
                if field.kind == CasillaFieldKind.BINDING
                or not any(export_fields_overlap(field, derived_field) for derived_field in derived)
            )
            resolved_records.append(record.model_copy(update={"fields": (*base_fields, *derived)}))
        resolved_layouts.append(layout.model_copy(update={"records": tuple(resolved_records)}))
    return tuple(resolved_layouts)


def fixed_width_record_casilla_ids(records: Sequence[ExportRecordDefinition]) -> frozenset[CasillaId]:
    """Return the casillas ``records`` address by casilla id in a fixed-width layout.

    A fixed-width record addresses a casilla through a ``CASILLA``-kind field, or
    through the ``row_field_casilla_ids`` mapping that names which casilla a
    repeated binding row's slot belongs to. This is the sole derivation of that
    set, shared by two callers that must never disagree about it:

    - the pre-write parity gate
      (:func:`~application.filing._export_parity.boe_representable_casilla_ids`), which passes
      only the records this filing's disposition actually emits, so a casilla the
      disposition suppresses is not demanded; and
    - the registry-build export-exemption gate
      (:func:`~domain.calculations.registry._validate_export_exemption.validate_export_exemption_declarations`),
      which passes EVERY declared record, so a casilla addressed on any
      disposition needs no exemption reason.

    The two scopes are deliberate and the build scope is the wider one: build
    time knows no disposition, and demanding a reason from a casilla some
    disposition does file would be a false refusal.

    A casilla addressed only through a ``BINDING``-kind field is NOT in this set —
    such a field names the binding, not the casilla, so no casilla-keyed scan can
    see it. That is a real representation channel, not an oversight, which is why
    :attr:`~core.ExportExemptionReason.FILED_VIA_BINDING_FIELD` exists to declare
    it rather than the scan being widened to guess at it.

    Args:
        records: The fixed-width export records to scan.

    Returns:
        Frozen set of casilla ids the records address by casilla id.
    """
    addressed: set[CasillaId] = set()
    for record in records:
        for field in record.fields:
            if field.kind == CasillaFieldKind.CASILLA and field.casilla_id is not None:
                addressed.add(field.casilla_id)
        addressed.update(record.row_field_casilla_ids.values())
    return frozenset(addressed)


def clasificar_casillas_oficiales(
    revision: ModeloRevision,
    *,
    source_root: Path | None = None,
    sources: Mapping[str, SourceReference] | None = None,
) -> Mapping[CasillaId, EstadoCasillaOficial]:
    """Classify every revision casilla by its official export representation.

    Binding-derived record fields are resolved before any channel is measured.
    Fixed-width ``CASILLA`` fields, repeated-row slot mappings, and official XML
    dictionary entries address a casilla directly. A casilla carrying the
    reviewed ``FILED_VIA_BINDING_FIELD`` exemption is represented through a
    binding when the resolved design actually contains binding fields. All
    remaining casillas are explicitly undefined.

    XML dictionaries are external registry evidence. A revision containing one
    therefore requires the validated source root and catalogue rather than
    silently treating an unavailable dictionary as an undefined export surface.
    """
    addressed, has_binding_fields = _canales_representacion_casillas_oficiales(
        revision,
        source_root=source_root,
        sources=sources,
    )
    return {
        casilla.id: _estado_casilla_oficial(
            casilla.id,
            exemption_reason=casilla.export_exemption_reason,
            addressed=addressed,
            has_binding_fields=has_binding_fields,
        )
        for casilla in revision.casillas
    }


def _canales_representacion_casillas_oficiales(
    revision: ModeloRevision,
    *,
    source_root: Path | None,
    sources: Mapping[str, SourceReference] | None,
) -> tuple[set[CasillaId], bool]:
    """Resolve the direct-address and binding-representation channels in layout order."""
    addressed: set[CasillaId] = set()
    has_binding_fields = False
    for layout in derive_export_layouts_from_bindings(revision):
        if layout.format is ExportLayoutFormat.FIXED_WIDTH:
            addressed.update(fixed_width_record_casilla_ids(layout.records))
            has_binding_fields = has_binding_fields or _layout_has_binding_fields(layout)
            continue
        if layout.format is ExportLayoutFormat.XML_DICTIONARY:
            addressed.update(
                entry.casilla_id
                for entry in xml_dictionary_entries(layout, source_root=source_root, sources=sources)
                if entry.casilla_id is not None
            )
    # A typed numbered endpoint addresses the official casilla even before the
    # generated layout exists. The declaration contributes classification only:
    # it never supplies a value or an export coordinate.
    addressed.update(
        casilla_id
        for declaration in revision.projection_endpoints
        if (casilla_id := filing_projection_ref_casilla_id(declaration.projection_ref)) is not None
    )
    return addressed, has_binding_fields


def _layout_has_binding_fields(layout: ExportLayoutDefinition) -> bool:
    """Whether the resolved fixed-width layout actually files a binding field."""
    return any(
        field.kind is CasillaFieldKind.BINDING and field.binding is not None
        for record in layout.records
        for field in record.fields
    )


def _estado_casilla_oficial(
    casilla_id: CasillaId,
    *,
    exemption_reason: ExportExemptionReason | None,
    addressed: set[CasillaId],
    has_binding_fields: bool,
) -> EstadoCasillaOficial:
    """Classify one casilla with direct address taking precedence over its exemption."""
    if casilla_id in addressed:
        return EstadoCasillaOficial.ADDRESSED
    if has_binding_fields and exemption_reason is ExportExemptionReason.FILED_VIA_BINDING_FIELD:
        return EstadoCasillaOficial.REPRESENTED_VIA_BINDING
    return EstadoCasillaOficial.UNDEFINED


def export_fields_overlap(left: ExportFieldDefinition, right: ExportFieldDefinition) -> bool:
    if left.offset is None or left.length is None or right.offset is None or right.length is None:
        return False
    left_end = left.offset + left.length - 1
    right_end = right.offset + right.length - 1
    return left.offset <= right_end and right.offset <= left_end


def _export_fields_from_record_bindings(
    record: ExportRecordDefinition,
    bindings: Sequence[_BindingExportMember],
) -> tuple[ExportFieldDefinition, ...]:
    fields: list[ExportFieldDefinition] = []
    bindings_by_id = {binding.id: (binding, selector) for binding, selector in bindings}
    derived_row_fields: set[str] = set()
    for binding, selector in bindings:
        if isinstance(selector, BindingFixedExportSelector):
            if any(field.kind == CasillaFieldKind.BINDING and field.binding == binding.id for field in record.fields):
                continue
            fields.append(_export_field_from_binding(record, binding, selector))
            continue
        row_field = _row_binding_field(binding, selector)
        if row_field is not None:
            if row_field in derived_row_fields:
                continue
            derived_row_fields.add(row_field)
        field = _export_field_from_row_binding(record, binding, selector, bindings_by_id=bindings_by_id)
        if field is not None:
            fields.append(field)
    return tuple(fields)


def _row_binding_field(binding: DataBindingDefinition, selector: BindingExportSelector) -> str | None:
    if binding_aggregation_op(binding) != BindingAggregationOp.ROWS:
        return None
    if not isinstance(selector, BindingRowExportSelector):
        return None
    return selector.row_field


def _export_field_from_row_binding(
    record: ExportRecordDefinition,
    binding: DataBindingDefinition,
    selector: BindingExportSelector,
    *,
    bindings_by_id: Mapping[str, _BindingExportMember],
) -> ExportFieldDefinition | None:
    if binding_aggregation_op(binding) != BindingAggregationOp.ROWS:
        return None
    if record.binding_record is None:
        return None
    row_field = _row_binding_field(binding, selector)
    if row_field is None:
        return None
    casilla_id = record.row_field_casilla_ids.get(row_field)
    if casilla_id is None:
        raise RegistryValidationError(
            f"export record {record.id!r} binding {binding.id!r} row_field {row_field!r}"
            " has no casilla mapping in row_field_casilla_ids",
        )
    # Pattern A: the record already hand-authors a kind="binding" field pinned
    # to this exact binding id. Trust the operator-pinned offset/length.
    if any(field.kind == CasillaFieldKind.BINDING and field.binding == binding.id for field in record.fields):
        return None
    # Pattern B: another hand-authored binding field already occupies this
    # row slot. It is the public field for the row_field, so source mirrors must
    # not derive duplicate export fields from the same fixed-width slot.
    if _record_binding_field_for_row_field(record, row_field=row_field, bindings_by_id=bindings_by_id) is not None:
        return None
    # Pattern C: a kind="casilla" template field exists for this casilla — derive
    # a binding-kind field by copying the template's offset/length/data_type.
    template = next(
        (field for field in record.fields if field.kind == CasillaFieldKind.CASILLA and field.casilla_id == casilla_id),
        None,
    )
    if template is None:
        raise RegistryValidationError(
            f"export record {record.id!r} binding {binding.id!r} casilla {casilla_id!r}"
            " has no matching template field in the record",
        )
    return template.model_copy(
        update={
            "kind": CasillaFieldKind.BINDING,
            "casilla_id": None,
            "binding": binding.id,
            "legal_refs": binding.legal_refs,
            "source_refs": binding.source_refs,
        },
    )


def _record_binding_field_for_row_field(
    record: ExportRecordDefinition,
    *,
    row_field: str,
    bindings_by_id: Mapping[str, _BindingExportMember],
) -> ExportFieldDefinition | None:
    for field in record.fields:
        if field.kind != CasillaFieldKind.BINDING or field.binding is None:
            continue
        if field.binding not in bindings_by_id:
            continue
        _binding, selector = bindings_by_id[field.binding]
        if isinstance(selector, BindingRowExportSelector) and selector.row_field == row_field:
            return field
    return None


def _export_field_from_binding(
    record: ExportRecordDefinition,
    binding: DataBindingDefinition,
    selector: BindingFixedExportSelector,
) -> ExportFieldDefinition:
    return ExportFieldDefinition(
        id=f"{record.id}.{binding.id}",
        offset=selector.offset,
        length=selector.length,
        kind=CasillaFieldKind.BINDING,
        binding=binding.id,
        data_type=selector.data_type,
        decimals=selector.decimals,
        required=False,
        padding=_padding_for_binding_data_type(selector.data_type),
        justification=_justification_for_binding_data_type(selector.data_type),
        # Read from the selector, never assumed. A hard-coded False here made
        # every binding-derived slot unsigned regardless of what AEAT typed the
        # design row, so a binding projecting into an ``N`` row emitted one
        # magnitude digit too many and refused outright on a negative value.
        signed=selector.signed,
        legal_refs=binding.legal_refs,
        source_refs=binding.source_refs,
    )


def _padding_for_binding_data_type(data_type: BindingExportDataType) -> ExportPadding:
    if data_type in {"money", "integer", "decimal"}:
        return ExportPadding.LEFT_ZERO
    return ExportPadding.RIGHT_SPACE


def _justification_for_binding_data_type(data_type: BindingExportDataType) -> ExportJustification:
    if data_type in {"money", "integer", "decimal"}:
        return ExportJustification.RIGHT
    return ExportJustification.LEFT


def export_fields_for_casilla(
    resolved: ResolvedExportLayout,
    casilla_id: CasillaId,
) -> tuple[ExportFieldDefinition, ...]:
    """Return all :class:`ExportFieldDefinition` entries mapped to ``casilla_id``."""
    return resolved.fields_by_casilla.get(casilla_id, ())


def _verify_layout_evidence(snapshot: RegistrySnapshot, layout: ExportLayoutDefinition) -> None:
    missing_legal = sorted(ref for ref in layout.legal_refs if ref not in snapshot.legal)
    missing_sources = sorted(ref for ref in layout.source_refs if ref not in snapshot.sources)
    if missing_legal:
        raise RegistryValidationError(f"export layout {layout.id!r} has unresolved legal refs: {missing_legal!r}")
    if missing_sources:
        raise RegistryValidationError(f"export layout {layout.id!r} has unresolved source refs: {missing_sources!r}")


def _ordered_fields(layout: ExportLayoutDefinition) -> tuple[ExportFieldDefinition, ...]:
    ordered: list[ExportFieldDefinition] = []
    for record in sorted(layout.records, key=lambda item: item.order):
        ordered.extend(sorted(record.fields, key=lambda item: (-1 if item.offset is None else item.offset, item.id)))
    return tuple(ordered)


def _index_fields(
    layout: ExportLayoutDefinition,
    fields: tuple[ExportFieldDefinition, ...],
) -> dict[str, ExportFieldDefinition]:
    fields_by_id: dict[str, ExportFieldDefinition] = {}
    for field in fields:
        if field.id in fields_by_id:
            raise RegistryValidationError(f"export layout {layout.id!r} has duplicate field id {field.id!r}")
        fields_by_id[field.id] = field
    return fields_by_id


def _index_fields_by_casilla(
    snapshot: RegistrySnapshot,
    fields: tuple[ExportFieldDefinition, ...],
) -> dict[CasillaId, tuple[ExportFieldDefinition, ...]]:
    casillas = casillas_by_id(snapshot.revision)
    grouped: dict[CasillaId, list[ExportFieldDefinition]] = {}
    for field in fields:
        if field.casilla_id is None:
            continue
        if field.casilla_id not in casillas:
            raise RegistryValidationError(
                f"export field {field.id!r} references unknown casilla {field.casilla_id!r}",
            )
        casilla = casillas[field.casilla_id]
        if field.id not in casilla.export_refs:
            raise RegistryValidationError(
                f"export field {field.id!r} points to casilla {field.casilla_id!r}, "
                "but the casilla does not declare the export ref",
            )
        grouped.setdefault(field.casilla_id, []).append(field)
    return {casilla_id: tuple(casilla_fields) for casilla_id, casilla_fields in grouped.items()}


def _verify_record_offsets(layout: ExportLayoutDefinition) -> None:
    for record in layout.records:
        ranges = _record_field_ranges(record)
        _reject_overlapping_ranges(record.id, sorted(ranges))


def _record_field_ranges(record: ExportRecordDefinition) -> list[tuple[int, int, str]]:
    """Return ``(start, end, field_id)`` for every offset-bearing field in ``record``.

    A field is offset-bearing when it declares both ``offset`` and
    ``length``. Declaring exactly one of the two is rejected up front;
    declaring neither marks the field as logical-only (e.g. an
    envelope-segment header that does not occupy a fixed-width slot).
    """
    ranges: list[tuple[int, int, str]] = []
    for field in record.fields:
        if field.offset is None and field.length is None:
            continue
        if field.offset is None or field.length is None:
            raise RegistryValidationError(
                f"export field {field.id!r} must declare both offset and length for fixed-width layouts",
            )
        ranges.append((field.offset, field.offset + field.length, field.id))
    return ranges


def _reject_overlapping_ranges(record_id: str, sorted_ranges: list[tuple[int, int, str]]) -> None:
    """Reject any pair of byte ranges that overlap. ``sorted_ranges`` must be sorted by start.

    The slot-geometry check that asks whether two fields claim the same bytes. Its
    slot-WIDTH sibling asks whether the bytes one field claims can hold what that
    field supplies, and lives at registry-build time rather than here: see
    :func:`cadrumo.domain.calculations.registry._validate_export_field_widths.validate_draft_field_slot_width`.
    """
    for index, current in enumerate(sorted_ranges):
        for other in sorted_ranges[index + 1 :]:
            if current[1] <= other[0]:
                break
            raise RegistryValidationError(f"export record {record_id!r} fields {current[2]!r} and {other[2]!r} overlap")


__all__ = [
    "ExportFieldDefinition",
    "ExportLayoutDefinition",
    "ExportRecordDefinition",
    "ResolvedExportLayout",
    "clasificar_casillas_oficiales",
    "derive_export_layouts_from_bindings",
    "export_fields_for_casilla",
    "fixed_width_record_casilla_ids",
    "resolve_export_layout",
]
