"""Export layout, record, and field validation helpers.

Validates export layouts, records, and fields declared on a
:class:`ModeloRevision` for casilla and binding reference closure.
"""

from __future__ import annotations

from collections.abc import Mapping

from ....core.aggregation import BindingAggregationOp
from ._binding_aggregation import binding_aggregation_op
from ._schema import (
    CasillaDefinition,
    ExportFieldDefinition,
    ExportRecordDefinition,
    LegalReference,
    ModeloRevision,
    SourceReference,
)
from ._validate_evidence import EvidenceValidator
from ._validate_helpers import _missing_refs


def validate_export_layout_section(
    failures: list[str],
    *,
    prefix: str,
    revision: ModeloRevision,
    casillas: set[str],
    bindings: set[str],
    casilla_by_id: Mapping[str, CasillaDefinition],
    legal_refs: Mapping[str, LegalReference],
    source_refs: Mapping[str, SourceReference],
    evidence: EvidenceValidator,
) -> None:
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
            )


def _validate_export_record(
    failures: list[str],
    *,
    prefix: str,
    revision: ModeloRevision,
    record: ExportRecordDefinition,
    casillas: set[str],
    bindings: set[str],
    casilla_by_id: Mapping[str, CasillaDefinition],
    legal_refs: Mapping[str, LegalReference],
    source_refs: Mapping[str, SourceReference],
) -> None:
    if record.binding_record is not None:
        _validate_export_record_binding_link(failures, prefix=prefix, revision=revision, record=record)
    if (
        record.repeat == "binding_rows"
        and not any(field.kind == "binding" for field in record.fields)
        and record.binding_record is None
    ):
        failures.append(f"{prefix}: export record {record.id!r} repeats binding rows but has no binding fields")
    if record.requires_positive_casilla is not None and record.requires_positive_casilla not in casillas:
        failures.append(
            f"{prefix}: export record {record.id!r} requires unknown positive casilla "
            f"{record.requires_positive_casilla!r}",
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
        )


def _validate_export_record_binding_link(
    failures: list[str],
    *,
    prefix: str,
    revision: ModeloRevision,
    record: ExportRecordDefinition,
) -> None:
    """Verify a binding-derived export record resolves to bindings with selector closure."""
    matching_bindings = [
        binding for binding in revision.bindings if binding.selector.get("record") == record.binding_record
    ]
    if not matching_bindings:
        failures.append(
            f"{prefix}: export record {record.id!r} derives fields from unknown binding record "
            f"{record.binding_record!r}",
        )
    for binding in matching_bindings:
        if binding.aggregation is not None and binding_aggregation_op(binding) == BindingAggregationOp.ROWS:
            continue
        missing_selector_keys = sorted(key for key in ("offset", "length", "data_type") if key not in binding.selector)
        if missing_selector_keys:
            failures.append(
                f"{prefix}: export record {record.id!r} binding {binding.id!r} lacks selector keys "
                f"{missing_selector_keys!r}",
            )


def _validate_export_field(
    failures: list[str],
    *,
    prefix: str,
    record: ExportRecordDefinition,
    field: ExportFieldDefinition,
    casillas: set[str],
    bindings: set[str],
    casilla_by_id: Mapping[str, CasillaDefinition],
    legal_refs: Mapping[str, LegalReference],
    source_refs: Mapping[str, SourceReference],
) -> None:
    owner = f"export field {field.id}"
    failures.extend(_missing_refs(prefix, owner, field.legal_refs, legal_refs, "legal"))
    failures.extend(_missing_refs(prefix, owner, field.source_refs, source_refs, "source"))
    if field.casilla is not None and field.casilla not in casillas:
        failures.append(f"{prefix}: export field {field.id!r} references unknown casilla {field.casilla!r}")
    if (
        field.casilla is not None
        and field.casilla in casilla_by_id
        and field.id not in casilla_by_id[field.casilla].export_refs
    ):
        failures.append(f"{prefix}: export field {field.id!r} is not declared by casilla {field.casilla!r}")
    if field.binding is not None and field.binding not in bindings:
        failures.append(f"{prefix}: export field {field.id!r} references unknown binding {field.binding!r}")
    if field.kind == "literal" and field.literal is not None and field.length is not None:
        literal_length = len(field.literal.encode(record.encoding))
        if literal_length > field.length:
            failures.append(
                f"{prefix}: export field {field.id!r} literal length {literal_length} exceeds "
                f"declared length {field.length}",
            )
