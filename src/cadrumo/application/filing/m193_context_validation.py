"""Modelo 193 perceptor PENDIENTE and EJERCICIO DEVENGO context validation."""

from __future__ import annotations

from ...domain.calculations.registry.schema_exports import ExportFieldDefinition, ExportRecordDefinition
from ...domain.filing.errors import FilingExportDesignIntegrityError, FilingExportValidationError

_M193_PERCEPTOR_RECORD_ID = "modelo-193-perceptor"
_M193_FILING_YEAR_ID = "modelo-193-perc-year"
_M193_CLAVE_ID = "modelo-193-perc-clave"
_M193_PENDIENTE_ID = "modelo-193-perc-pendiente"
_M193_DEVENGO_ID = "modelo-193-perc-ejercicio-devengo"
_M193_CONTEXT_FIELD_IDS = (_M193_FILING_YEAR_ID, _M193_CLAVE_ID, _M193_PENDIENTE_ID, _M193_DEVENGO_ID)
# Positions 117 and 118-121 are printed "Solo para claves de percepción A, B o D".
_M193_DEVENGO_CLAVES = frozenset("ABD")
_M193_PENDING_MARK = "X"
_M193_CHANGED = "modelo 193 perceptor pending and devengo declaration is incomplete or changed"


def _field_wire(wire: str, field: ExportFieldDefinition) -> str:
    if field.offset is None or field.length is None:
        raise FilingExportDesignIntegrityError(
            _M193_CHANGED, translated_message="errors.integrity.filing_export_m193_declaration_changed"
        )
    return wire[field.offset - 1 : field.offset - 1 + field.length]


def _is_year(value: str) -> bool:
    return value.isascii() and value.isdigit()


def _context_wires(record: ExportRecordDefinition, wire: str) -> tuple[str, str, str, str]:
    """Return the year, clave, pendiente and devengo wire slices, refusing a changed or short record."""
    by_id = {field.id: field for field in record.fields}
    if any(identifier not in by_id for identifier in _M193_CONTEXT_FIELD_IDS):
        raise FilingExportDesignIntegrityError(
            _M193_CHANGED, translated_message="errors.integrity.filing_export_m193_declaration_changed"
        )
    if len(wire) != max((field.offset or 0) + (field.length or 0) - 1 for field in record.fields):
        raise FilingExportValidationError("modelo 193 perceptor record is incomplete")
    filing_year, clave, pendiente, devengo = (
        _field_wire(wire, by_id[identifier]) for identifier in _M193_CONTEXT_FIELD_IDS
    )
    return filing_year, clave, pendiente, devengo


def _require_devengo_year_before_filing(devengo: str, filing_year: str) -> None:
    if not (_is_year(devengo) and _is_year(filing_year) and int(devengo) < int(filing_year)):
        raise FilingExportValidationError("modelo 193 devengo year must be earlier than the declaration year")


def require_m193_perceptor_devengo_context(record: ExportRecordDefinition, wire: str) -> None:
    """Refuse a perceptor record whose PENDIENTE or EJERCICIO DEVENGO contradicts the printed design."""
    if record.id != _M193_PERCEPTOR_RECORD_ID:
        return
    filing_year, clave, pendiente, devengo = _context_wires(record, wire)
    if pendiente not in {" ", _M193_PENDING_MARK}:
        raise FilingExportValidationError("modelo 193 pending mark must be blank or X")
    pending = pendiente == _M193_PENDING_MARK
    devengo_filled = devengo != "0" * len(devengo)
    if (pending or devengo_filled) and clave not in _M193_DEVENGO_CLAVES:
        raise FilingExportValidationError("modelo 193 pending mark and devengo year apply only to keys A, B and D")
    if pending and devengo_filled:
        raise FilingExportValidationError("modelo 193 pending row has no devengo year")
    if devengo_filled:
        _require_devengo_year_before_filing(devengo, filing_year)
