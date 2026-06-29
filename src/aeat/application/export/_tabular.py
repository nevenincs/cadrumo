"""Serialize tabular rows into :class:`TabularExportResult` payloads.

Rows are rendered through the closed :class:`ExportSerializationFormat`
surface, with :class:`ExportFieldError` and :class:`ExportFormatError`
preserving validation failures as structured application errors.

This module is a pure in-memory serializer. It returns bytes, media type,
extension, field metadata, row count, and SHA-256 digest to the calling
export service; it does not choose paths, write files, emit bucket events,
or mutate canonical storage.
"""

from __future__ import annotations

import csv
import json
from collections.abc import Mapping, Sequence
from enum import StrEnum
from io import StringIO

from pydantic import BaseModel, Field, field_validator

from ...core import STRICT_FROZEN_CONFIG
from ...core.external_constants import CSV_MIME_TYPE as _CSV_MIME_TYPE
from ...core.external_constants import JSONL_MIME_TYPE as _JSONL_MIME_TYPE
from ...core.external_constants import UTF_8_ENCODING as _UTF_8_ENCODING
from ...core.external_constants import XLSX_MIME_TYPE as _XLSX_MIME_TYPE
from ...core.hashing import sha256_hex
from ._errors import ExportFieldError, ExportFormatError


class ExportSerializationFormat(StrEnum):
    """Closed set of backend tabular export serialization formats."""

    CSV = "csv"
    JSONL = "jsonl"
    XLSX = "xlsx"


_REFUSED_EXPORT_FIELD_MESSAGE = "errors.refused.refused_export_field"
_REFUSED_EXPORT_FORMAT_MESSAGE = "errors.refused.refused_export_format"
_FIELDNAMES_EMPTY_REASON = "fieldnames_empty"
_FIELDNAMES_BLANK_REASON = "fieldnames_blank"
_FIELDNAMES_DUPLICATE_REASON = "fieldnames_duplicate"
_UNKNOWN_FIELDS_REASON = "unknown_fields"
_SHA256_INVALID_REASON = "sha256_invalid"


class TabularExportResult(BaseModel):
    """Serialized tabular payload produced by :func:`serialize_tabular_rows`.

    The result carries the raw payload plus operator-facing metadata:
    :class:`ExportSerializationFormat`, media type, filename extension,
    byte count, SHA-256 digest, row count, and normalized field names.
    """

    model_config = STRICT_FROZEN_CONFIG

    format: ExportSerializationFormat
    media_type: str = Field(min_length=1)
    filename_extension: str = Field(min_length=1)
    payload: bytes
    byte_size: int = Field(ge=0)
    sha256: str
    row_count: int = Field(ge=0)
    fieldnames: tuple[str, ...]

    @field_validator("fieldnames")
    @classmethod
    def _validate_fieldnames(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(field.strip() for field in value)
        if any(not field for field in normalized):
            raise _export_field_error(_FIELDNAMES_BLANK_REASON)
        if len(set(normalized)) != len(normalized):
            raise _export_field_error(_FIELDNAMES_DUPLICATE_REASON)
        return normalized

    @field_validator("sha256")
    @classmethod
    def _validate_sha256(cls, value: str) -> str:
        normalized = value.strip().lower()
        if len(normalized) != 64 or any(char not in "0123456789abcdef" for char in normalized):
            raise _export_field_error(_SHA256_INVALID_REASON)
        return normalized


def serialize_tabular_rows(
    rows: Sequence[Mapping[str, str]],
    *,
    fieldnames: Sequence[str],
    export_format: ExportSerializationFormat,
) -> TabularExportResult:
    """Serialize string-keyed rows as deterministic CSV, JSON Lines, or XLSX.

    Field order follows ``fieldnames`` and row order follows ``rows``.
    Values are coerced to strings, missing fields become empty strings,
    and unknown fields raise :class:`ExportFieldError`. Returns a
    :class:`TabularExportResult` with encoded bytes, media type, filename
    extension, row count, field metadata, and payload digest.
    """
    normalized_fields = _normalize_fieldnames(fieldnames)
    normalized_rows = tuple(_normalize_row(row, fieldnames=normalized_fields) for row in rows)
    if export_format is ExportSerializationFormat.CSV:
        payload = _serialize_csv(normalized_rows, fieldnames=normalized_fields)
        media_type = _CSV_MIME_TYPE
        extension = "csv"
    elif export_format is ExportSerializationFormat.JSONL:
        payload = _serialize_jsonl(normalized_rows, fieldnames=normalized_fields)
        media_type = _JSONL_MIME_TYPE
        extension = "jsonl"
    elif export_format is ExportSerializationFormat.XLSX:
        payload = _serialize_xlsx(normalized_rows, fieldnames=normalized_fields)
        media_type = _XLSX_MIME_TYPE
        extension = "xlsx"
    else:
        raise ExportFormatError(
            translated_message=_REFUSED_EXPORT_FORMAT_MESSAGE,
            context={"export_format": str(export_format)},
        )
    return TabularExportResult(
        format=export_format,
        media_type=media_type,
        filename_extension=extension,
        payload=payload,
        byte_size=len(payload),
        sha256=sha256_hex(payload),
        row_count=len(normalized_rows),
        fieldnames=normalized_fields,
    )


def _normalize_fieldnames(fieldnames: Sequence[str]) -> tuple[str, ...]:
    normalized = tuple(field.strip() for field in fieldnames)
    if not normalized:
        raise _export_field_error(_FIELDNAMES_EMPTY_REASON)
    if any(not field for field in normalized):
        raise _export_field_error(_FIELDNAMES_BLANK_REASON)
    if len(set(normalized)) != len(normalized):
        raise _export_field_error(_FIELDNAMES_DUPLICATE_REASON)
    return normalized


def _normalize_row(row: Mapping[str, str], *, fieldnames: tuple[str, ...]) -> dict[str, str]:
    unknown = sorted(set(row).difference(fieldnames))
    if unknown:
        raise _export_field_error(_UNKNOWN_FIELDS_REASON, unknown_fields=tuple(unknown))
    return {field: str(row.get(field, "")) for field in fieldnames}


def _export_field_error(reason: str, **context: object) -> ExportFieldError:
    return ExportFieldError(
        translated_message=_REFUSED_EXPORT_FIELD_MESSAGE,
        context={"reason": reason, **context},
    )


def _serialize_csv(rows: tuple[dict[str, str], ...], *, fieldnames: tuple[str, ...]) -> bytes:
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode(_UTF_8_ENCODING)


def _serialize_jsonl(rows: tuple[dict[str, str], ...], *, fieldnames: tuple[str, ...]) -> bytes:
    del fieldnames
    text = "".join(json.dumps(row, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n" for row in rows)
    return text.encode(_UTF_8_ENCODING)


def _serialize_xlsx(rows: tuple[dict[str, str], ...], *, fieldnames: tuple[str, ...]) -> bytes:
    """Serialize rows into a single-worksheet XLSX workbook (header + data rows).

    Every cell is written as text so a deterministic, locale-independent
    round-trip is preserved; the workbook re-reads through
    :class:`aeat.adapters.inbound.financial.providers._xlsx.XlsxProvider`,
    which shares the CSV bank-layout catalogue.
    """
    from io import BytesIO

    from openpyxl import Workbook

    workbook = Workbook()
    worksheet = workbook.active
    assert worksheet is not None, "Workbook.active must not be None on a fresh Workbook"
    worksheet.title = "ledger"
    worksheet.append(list(fieldnames))
    for row in rows:
        worksheet.append([row.get(field, "") for field in fieldnames])
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()
