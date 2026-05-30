"""Strict tabular export serialization for application services."""

from __future__ import annotations

import csv
import hashlib
import json
from collections.abc import Mapping, Sequence
from enum import StrEnum
from io import StringIO

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ...core.external_constants import CSV_MIME_TYPE as _CSV_MIME_TYPE
from ._errors import ExportFieldError, ExportFormatError


class ExportSerializationFormat(StrEnum):
    """Supported backend export serialization formats."""

    CSV = "csv"
    JSONL = "jsonl"


class TabularExportResult(BaseModel):
    """Serialized tabular export payload and integrity metadata."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    format: ExportSerializationFormat
    media_type: str = Field(min_length=1)
    filename_extension: str = Field(min_length=1)
    payload: bytes
    byte_size: int = Field(ge=0)
    sha256: str = Field(min_length=64, max_length=64)
    row_count: int = Field(ge=0)
    fieldnames: tuple[str, ...]

    @field_validator("fieldnames")
    @classmethod
    def _validate_fieldnames(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(field.strip() for field in value)
        if any(not field for field in normalized):
            raise ExportFieldError("fieldnames must not contain blank values")
        if len(set(normalized)) != len(normalized):
            raise ExportFieldError("fieldnames must not contain duplicates")
        return normalized

    @field_validator("sha256")
    @classmethod
    def _validate_sha256(cls, value: str) -> str:
        normalized = value.strip().lower()
        if len(normalized) != 64 or any(char not in "0123456789abcdef" for char in normalized):
            raise ValueError("sha256 must be a lowercase 64-character hex digest")
        return normalized


def serialize_tabular_rows(
    rows: Sequence[Mapping[str, str]],
    *,
    fieldnames: Sequence[str],
    export_format: ExportSerializationFormat,
) -> TabularExportResult:
    """Serialize string-keyed rows as a deterministic CSV or JSON Lines payload."""

    normalized_fields = _normalize_fieldnames(fieldnames)
    normalized_rows = tuple(_normalize_row(row, fieldnames=normalized_fields) for row in rows)
    if export_format is ExportSerializationFormat.CSV:
        payload = _serialize_csv(normalized_rows, fieldnames=normalized_fields)
        media_type = _CSV_MIME_TYPE
        extension = "csv"
    elif export_format is ExportSerializationFormat.JSONL:
        payload = _serialize_jsonl(normalized_rows, fieldnames=normalized_fields)
        media_type = "application/x-ndjson"
        extension = "jsonl"
    else:  # pragma: no cover - closed enum defensive guard
        raise ExportFormatError(f"unsupported export format: {export_format!r}")
    return TabularExportResult(
        format=export_format,
        media_type=media_type,
        filename_extension=extension,
        payload=payload,
        byte_size=len(payload),
        sha256=hashlib.sha256(payload).hexdigest(),
        row_count=len(normalized_rows),
        fieldnames=normalized_fields,
    )


def _normalize_fieldnames(fieldnames: Sequence[str]) -> tuple[str, ...]:
    normalized = tuple(field.strip() for field in fieldnames)
    if not normalized:
        raise ExportFieldError("fieldnames must not be empty")
    if any(not field for field in normalized):
        raise ExportFieldError("fieldnames must not contain blank values")
    if len(set(normalized)) != len(normalized):
        raise ExportFieldError("fieldnames must not contain duplicates")
    return normalized


def _normalize_row(row: Mapping[str, str], *, fieldnames: tuple[str, ...]) -> dict[str, str]:
    unknown = sorted(set(row).difference(fieldnames))
    if unknown:
        raise ExportFieldError(f"row contains unknown fields: {unknown!r}")
    return {field: str(row.get(field, "")) for field in fieldnames}


def _serialize_csv(rows: tuple[dict[str, str], ...], *, fieldnames: tuple[str, ...]) -> bytes:
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def _serialize_jsonl(rows: tuple[dict[str, str], ...], *, fieldnames: tuple[str, ...]) -> bytes:
    del fieldnames
    text = "".join(json.dumps(row, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n" for row in rows)
    return text.encode("utf-8")
