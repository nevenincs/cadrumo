"""Reconstruct and compare canonical fixed-width export record instances."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from cadrumo.domain.calculations.registry.export_parse import (
    ParsedExportFieldValue,
    ParsedExportPayload,
)
from cadrumo.domain.calculations.registry.schema_exports import ExportLayoutDefinition, ExportRecordDefinition

from .cli_contracts import RetencionesInstalledCliError
from .cli_observations import _money_or_integer_text


def _record_field_ids(record: ExportRecordDefinition, *, stage: str) -> tuple[str, ...]:
    """Record field ids."""
    expected_field_ids = tuple(str(field.id) for field in sorted(record.fields, key=lambda item: item.offset or 0))
    if not expected_field_ids:
        raise RetencionesInstalledCliError(stage=stage, diagnostic_code="annual_export_empty_record_layout")
    return expected_field_ids


def _record_for_type(*, layout: ExportLayoutDefinition, record_type: str, stage: str) -> ExportRecordDefinition:
    """Return one unambiguous official record family by its registry type."""
    matches = tuple(record for record in layout.records if record.record_type == record_type)
    if len(matches) != 1:
        raise RetencionesInstalledCliError(stage=stage, diagnostic_code=f"annual_export_{record_type}_record_mismatch")
    return matches[0]


def _parsed_record_rows(
    *, parsed: ParsedExportPayload, record: ExportRecordDefinition, stage: str
) -> tuple[dict[str, str], ...]:
    """Reconstruct fixed-width record instances in canonical layout field order."""
    expected_field_ids = _record_field_ids(record, stage=stage)
    record_fields = tuple(field for field in parsed.fields if str(field.record_id) == str(record.id))
    if len(record_fields) % len(expected_field_ids) != 0:
        raise RetencionesInstalledCliError(stage=stage, diagnostic_code="annual_export_record_extent_mismatch")
    rows: list[dict[str, str]] = []
    for offset in range(0, len(record_fields), len(expected_field_ids)):
        row = record_fields[offset : offset + len(expected_field_ids)]
        if tuple(str(field.field_id) for field in row) != expected_field_ids:
            raise RetencionesInstalledCliError(stage=stage, diagnostic_code="annual_export_record_field_order_mismatch")
        rows.append({str(field.field_id): _parsed_field_text(field) for field in row})
    return tuple(rows)


def _selected_expected_fields(
    *, actual: Mapping[str, str], expected: Mapping[str, str], stage: str, mismatch_code: str
) -> dict[str, str]:
    """Require every independently authored annual expectation from a parsed row."""
    selected: dict[str, str] = {}
    for field_id, expected_value in expected.items():
        actual_value = actual.get(field_id)
        if actual_value != expected_value:
            raise RetencionesInstalledCliError(stage=stage, diagnostic_code=mismatch_code)
        if actual_value is None:  # Keeps the receipt type honest after the equality check.
            raise RetencionesInstalledCliError(stage=stage, diagnostic_code=mismatch_code)
        selected[field_id] = actual_value
    return selected


def _parsed_field_text(field: ParsedExportFieldValue) -> str:
    """Normalize parser values into the synthetic fixture's stable value form."""
    value = field.value
    if isinstance(value, Decimal):
        return _money_or_integer_text(value)
    return str(value)


def _row_identity(row: Mapping[str, str]) -> tuple[tuple[str, str], ...]:
    """Compare independently ordered type-2 expectations without hiding duplicates."""
    return tuple(sorted(row.items()))
