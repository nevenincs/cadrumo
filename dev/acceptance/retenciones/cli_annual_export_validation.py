"""Independent annual header, count, control and recipient-row export validation."""

from __future__ import annotations

from collections.abc import Mapping

from cadrumo.domain.calculations.registry.export_parse import (
    parse_export_payload,
)
from cadrumo.domain.calculations.registry.schema_exports import ExportLayoutDefinition

from .cli_contracts import AnnualExportValidationEvidence, RetencionesInstalledCliError
from .cli_export_rows import _parsed_record_rows, _record_for_type, _row_identity, _selected_expected_fields
from .scenario import (
    AnnualExportRecordExpectation,
)


def _validate_annual_export_rows(
    expected_type2_rows: tuple[AnnualExportRecordExpectation, ...],
    type2_rows: tuple[dict[str, str], ...],
    *,
    stage: str,
) -> tuple[tuple[dict[str, str], ...], tuple[dict[str, str], ...]]:
    """Validate annual export rows."""
    expected_rows = tuple(dict(row.values) for row in expected_type2_rows)
    expected_row_fields = {field_id: "" for expected in expected_rows for field_id in expected}
    parsed_rows = tuple(
        _selected_annual_row_fields(
            actual=row,
            expected=expected_row_fields,
            stage=stage,
        )
        for row in type2_rows
    )
    if sorted(_row_identity(row) for row in parsed_rows) != sorted(_row_identity(row) for row in expected_rows):
        raise RetencionesInstalledCliError(stage=stage, diagnostic_code="annual_export_type2_rows_mismatch")
    return parsed_rows, expected_rows


def _validate_annual_export(
    *,
    layout: ExportLayoutDefinition,
    payload: bytes,
    expected_header: tuple[tuple[str, str], ...],
    expected_type2_rows: tuple[AnnualExportRecordExpectation, ...],
    stage: str,
) -> AnnualExportValidationEvidence:
    """Independently parse annual header/count/control and emitted type-2 rows."""
    try:
        parsed = parse_export_payload(layout, payload)
    except Exception as exc:
        raise RetencionesInstalledCliError(
            stage=stage,
            diagnostic_code=f"canonical_annual_export_parse_{type(exc).__name__}",
        ) from exc
    if str(parsed.layout_id) != str(layout.id):
        raise RetencionesInstalledCliError(stage=stage, diagnostic_code="annual_export_layout_mismatch")
    header_record = _record_for_type(layout=layout, record_type="declarante", stage=stage)
    type2_record = _record_for_type(layout=layout, record_type="perceptor", stage=stage)
    header_rows = _parsed_record_rows(parsed=parsed, record=header_record, stage=stage)
    type2_rows = _parsed_record_rows(parsed=parsed, record=type2_record, stage=stage)
    if len(header_rows) != 1:
        raise RetencionesInstalledCliError(stage=stage, diagnostic_code="annual_export_header_count_mismatch")

    expected_header_values = dict(expected_header)
    actual_header = header_rows[0]
    parsed_header = _selected_expected_fields(
        actual=actual_header,
        expected=expected_header_values,
        stage=stage,
        mismatch_code="annual_export_header_field_mismatch",
    )
    if len(type2_rows) != len(expected_type2_rows):
        raise RetencionesInstalledCliError(stage=stage, diagnostic_code="annual_export_type2_count_mismatch")
    _assert_header_count_matches_type2_rows(
        parsed_header=parsed_header,
        expected_header=expected_header_values,
        actual_type2_count=len(type2_rows),
        stage=stage,
    )
    parsed_rows, expected_rows = _validate_annual_export_rows(expected_type2_rows, type2_rows, stage=stage)
    return AnnualExportValidationEvidence(
        layout_id=str(parsed.layout_id),
        parsed_header_fields=dict(sorted(parsed_header.items())),
        expected_header_fields=dict(sorted(expected_header_values.items())),
        parsed_type2_rows=tuple(dict(sorted(row.items())) for row in parsed_rows),
        expected_type2_rows=tuple(dict(sorted(row.items())) for row in expected_rows),
    )


def _selected_annual_row_fields(
    *, actual: Mapping[str, str], expected: Mapping[str, str], stage: str
) -> dict[str, str]:
    """Select required row fields before comparing unordered emitted record identities."""
    selected: dict[str, str] = {}
    for field_id in expected:
        actual_value = actual.get(field_id)
        if actual_value is None:
            raise RetencionesInstalledCliError(stage=stage, diagnostic_code="annual_export_type2_field_missing")
        selected[field_id] = actual_value
    return selected


def _assert_header_count_matches_type2_rows(
    *,
    parsed_header: Mapping[str, str],
    expected_header: Mapping[str, str],
    actual_type2_count: int,
    stage: str,
) -> None:
    """Prove the emitted-record count agrees with the exported control field."""
    count_ids = tuple(
        field_id
        for field_id in expected_header
        if field_id.endswith("total-perceptores") or field_id.endswith("total-percepciones")
    )
    if len(count_ids) != 1:
        raise RetencionesInstalledCliError(stage=stage, diagnostic_code="annual_export_count_field_ambiguous")
    try:
        parsed_count = int(parsed_header[count_ids[0]])
    except (TypeError, ValueError) as exc:
        raise RetencionesInstalledCliError(stage=stage, diagnostic_code="annual_export_count_field_invalid") from exc
    if parsed_count != actual_type2_count:
        raise RetencionesInstalledCliError(stage=stage, diagnostic_code="annual_export_count_control_mismatch")
