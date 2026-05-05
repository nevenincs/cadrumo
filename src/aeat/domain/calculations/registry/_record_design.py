"""Read-only extraction of official AEAT record-design workbook rows."""

from __future__ import annotations

from pathlib import Path

from openpyxl import load_workbook
from pydantic import ConfigDict

from ._schema import RegistryModel


class RecordDesignField(RegistryModel):
    """One fixed-width field described by an AEAT record-design sheet."""

    sheet: str
    row: int
    ordinal: int
    offset: int
    length: int
    type_code: str
    complementary: str | None = None
    description: str
    validation: str | None = None
    content: str | None = None


class RecordDesignSheet(RegistryModel):
    """Parsed field rows and declared total length for one workbook sheet."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    fields: tuple[RecordDesignField, ...]
    total_positions: int | None = None


def extract_record_design_workbook(path: Path) -> tuple[RecordDesignSheet, ...]:
    """Return the official fixed-width field rows described by ``path``."""

    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        return tuple(_extract_sheet(worksheet) for worksheet in workbook.worksheets)
    finally:
        workbook.close()


def _extract_sheet(worksheet) -> RecordDesignSheet:  # type: ignore[no-untyped-def]
    header_row, header = _find_header(worksheet)
    has_complementary_column = len(header) >= 5 and _clean(header[4]) == "Com"
    fields: list[RecordDesignField] = []
    total_positions: int | None = None
    for row_number, row in enumerate(
        worksheet.iter_rows(min_row=header_row + 1, values_only=True),
        start=header_row + 1,
    ):
        values = tuple(row)
        marker = values[0] if values else None
        if marker == "TOTAL":
            total_positions = _int_or_none(_cell(values, 2))
            continue
        ordinal = _int_or_none(marker)
        offset = _int_or_none(_cell(values, 1))
        length = _int_or_none(_cell(values, 2))
        if ordinal is None or offset is None or length is None:
            continue
        if has_complementary_column:
            type_code = _required_text(_cell(values, 3), worksheet.title, row_number, "type")
            complementary = _optional_text(_cell(values, 4))
            description = _required_text(_cell(values, 5), worksheet.title, row_number, "description")
            validation = _optional_text(_cell(values, 6))
            content = _optional_text(_cell(values, 7))
        else:
            type_code = _required_text(_cell(values, 3), worksheet.title, row_number, "type")
            complementary = None
            description = _required_text(_cell(values, 4), worksheet.title, row_number, "description")
            validation = _optional_text(_cell(values, 5))
            content = _optional_text(_cell(values, 6))
        fields.append(
            RecordDesignField(
                sheet=worksheet.title,
                row=row_number,
                ordinal=ordinal,
                offset=offset,
                length=length,
                type_code=type_code,
                complementary=complementary,
                description=description,
                validation=validation,
                content=content,
            )
        )
    return RecordDesignSheet(name=worksheet.title, fields=tuple(fields), total_positions=total_positions)


def _find_header(worksheet) -> tuple[int, tuple[object, ...]]:  # type: ignore[no-untyped-def]
    for row_number, row in enumerate(worksheet.iter_rows(min_row=1, max_row=10, values_only=True), start=1):
        values = tuple(row)
        if _clean(_cell(values, 0)) == "Nº" and _clean(_cell(values, 1)) == "Posic.":
            return row_number, values
    raise ValueError(f"{worksheet.title!r} has no record-design header")


def _cell(values: tuple[object, ...], index: int) -> object | None:
    return values[index] if index < len(values) else None


def _clean(value: object | None) -> str:
    return "" if value is None else str(value).strip()


def _optional_text(value: object | None) -> str | None:
    cleaned = _clean(value)
    return cleaned or None


def _required_text(value: object | None, sheet: str, row: int, field: str) -> str:
    cleaned = _clean(value)
    if not cleaned:
        raise ValueError(f"{sheet!r} row {row} missing {field}")
    return cleaned


def _int_or_none(value: object | None) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


__all__ = [
    "RecordDesignField",
    "RecordDesignSheet",
    "extract_record_design_workbook",
]
