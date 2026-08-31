"""Export metadata must describe the payload it is attached to.

``TabularExportResult`` carried payload bytes alongside ``byte_size``,
``sha256``, ``row_count`` and format metadata but validated only field-name and
digest *shape*, and ``LedgerExportResult`` redeclared the same seven fields
independently. Producers emitted coherent values, yet any public caller could
construct a contradictory result -- and the ledger export action anchors
``row_count``, ``byte_size`` and ``sha256`` into a durable
``LEDGER_TRANSACTION_EXPORTED`` bucket event, where a false value outlives the
payload that would disprove it.

Every field checked here is a pure function of the payload and the format, so
each mutated case below is not a different opinion but a false one. The valid
round-trip in each format is the positive control: a check that refused
everything would pass the refusal cases and fail those.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from ....core.external_constants import CSV_MIME_TYPE, JSONL_MIME_TYPE, XLSX_MIME_TYPE
from ....core.hashing import sha256_hex
from ..errors import ExportFieldError
from ..tabular import ExportSerializationFormat, TabularExportResult, serialize_tabular_rows, verify_export_metadata

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_ROWS = (
    {"transaction_id": "a", "amount": "1.00"},
    {"transaction_id": "b", "amount": "2.00"},
)
_FIELDNAMES = ("transaction_id", "amount")
_ALL_FORMATS = (
    ExportSerializationFormat.CSV,
    ExportSerializationFormat.JSONL,
    ExportSerializationFormat.XLSX,
)


def _refusal_reason(exc_info: pytest.ExceptionInfo[ValidationError]) -> str:
    """Return the typed refusal reason pydantic wrapped in its ValidationError.

    The model validator raises the same typed, localisable
    :class:`~application.export.errors.ExportFieldError` the rest of the export
    surface raises; pydantic wraps it when it fires inside a validator. Reading
    the reason back proves the refusal is the intended one rather than any
    incidental validation failure.
    """
    context = exc_info.value.errors()[0].get("ctx")
    assert isinstance(context, dict)
    cause = context["error"]
    assert isinstance(cause, ExportFieldError)
    assert cause.context is not None
    return str(cause.context["reason"])


def _serialized(export_format: ExportSerializationFormat) -> TabularExportResult:
    return serialize_tabular_rows(_ROWS, fieldnames=_FIELDNAMES, export_format=export_format)


def _rebuilt(result: TabularExportResult, **overrides: Any) -> TabularExportResult:
    fields: dict[str, Any] = {
        "format": result.format,
        "media_type": result.media_type,
        "filename_extension": result.filename_extension,
        "payload": result.payload,
        "byte_size": result.byte_size,
        "sha256": result.sha256,
        "row_count": result.row_count,
        "fieldnames": result.fieldnames,
    }
    fields.update(overrides)
    return TabularExportResult(**fields)  # type: ignore[arg-type]


@pytest.mark.parametrize("export_format", _ALL_FORMATS)
def test_a_genuine_serialization_round_trips_through_the_contract(
    export_format: ExportSerializationFormat,
) -> None:
    """Positive control: real producer output must still reconstruct."""
    result = _serialized(export_format)

    assert _rebuilt(result) == result
    assert result.byte_size == len(result.payload)
    assert result.sha256 == sha256_hex(result.payload)
    assert result.row_count == len(_ROWS)


@pytest.mark.parametrize("export_format", _ALL_FORMATS)
def test_a_false_byte_size_is_refused(export_format: ExportSerializationFormat) -> None:
    result = _serialized(export_format)

    with pytest.raises(ValidationError) as exc_info:
        _rebuilt(result, byte_size=0)

    assert _refusal_reason(exc_info) == "byte_size_mismatch"


@pytest.mark.parametrize("export_format", _ALL_FORMATS)
def test_a_digest_of_other_bytes_is_refused(export_format: ExportSerializationFormat) -> None:
    """Shape-valid but wrong: the all-zero digest passed the old shape check."""
    result = _serialized(export_format)

    with pytest.raises(ValidationError) as exc_info:
        _rebuilt(result, sha256="0" * 64)

    assert _refusal_reason(exc_info) == "sha256_mismatch"


@pytest.mark.parametrize("export_format", _ALL_FORMATS)
def test_a_false_row_count_is_refused(export_format: ExportSerializationFormat) -> None:
    result = _serialized(export_format)

    with pytest.raises(ValidationError) as exc_info:
        _rebuilt(result, row_count=99)

    assert _refusal_reason(exc_info) == "row_count_mismatch"


@pytest.mark.parametrize(
    ("export_format", "foreign_media_type"),
    [
        (ExportSerializationFormat.CSV, JSONL_MIME_TYPE),
        (ExportSerializationFormat.JSONL, XLSX_MIME_TYPE),
        (ExportSerializationFormat.XLSX, CSV_MIME_TYPE),
    ],
)
def test_media_type_from_another_format_is_refused(
    export_format: ExportSerializationFormat,
    foreign_media_type: str,
) -> None:
    result = _serialized(export_format)

    with pytest.raises(ValidationError) as exc_info:
        _rebuilt(result, media_type=foreign_media_type)

    assert _refusal_reason(exc_info) == "media_type_mismatch"


@pytest.mark.parametrize("export_format", _ALL_FORMATS)
def test_a_foreign_filename_extension_is_refused(export_format: ExportSerializationFormat) -> None:
    result = _serialized(export_format)
    foreign = "csv" if result.filename_extension != "csv" else "jsonl"

    with pytest.raises(ValidationError) as exc_info:
        _rebuilt(result, filename_extension=foreign)

    assert _refusal_reason(exc_info) == "filename_extension_mismatch"


@pytest.mark.parametrize("export_format", _ALL_FORMATS)
def test_metadata_kept_while_the_payload_is_swapped_is_refused(
    export_format: ExportSerializationFormat,
) -> None:
    """The mirror case: tampering with the bytes, not the numbers, must also fail."""
    result = _serialized(export_format)

    with pytest.raises(ValidationError) as exc_info:
        _rebuilt(result, payload=result.payload + b"tampered")

    assert _refusal_reason(exc_info) == "byte_size_mismatch"


def test_an_empty_export_is_still_coherent() -> None:
    """A zero-row export is a real state and must not be mistaken for tampering."""
    empty = serialize_tabular_rows((), fieldnames=_FIELDNAMES, export_format=ExportSerializationFormat.CSV)

    assert empty.row_count == 0
    assert _rebuilt(empty) == empty
    with pytest.raises(ValidationError) as exc_info:
        _rebuilt(empty, row_count=1)

    assert _refusal_reason(exc_info) == "row_count_mismatch"


def test_a_csv_field_containing_a_newline_counts_as_one_row() -> None:
    """Row counting parses CSV rather than counting newlines, so quoting is safe."""
    result = serialize_tabular_rows(
        ({"transaction_id": "a", "amount": "line one\nline two"},),
        fieldnames=_FIELDNAMES,
        export_format=ExportSerializationFormat.CSV,
    )

    assert result.row_count == 1
    assert b"\n" in result.payload
    assert _rebuilt(result) == result


@pytest.mark.parametrize(
    ("export_format", "payload", "media_type", "filename_extension"),
    (
        (ExportSerializationFormat.CSV, b"\xff", CSV_MIME_TYPE, "csv"),
        (ExportSerializationFormat.JSONL, b"\xff", JSONL_MIME_TYPE, "jsonl"),
        (ExportSerializationFormat.XLSX, b"not-a-zip", XLSX_MIME_TYPE, "xlsx"),
    ),
)
def test_malformed_serialized_payloads_raise_typed_export_field_errors(
    export_format: ExportSerializationFormat,
    payload: bytes,
    media_type: str,
    filename_extension: str,
) -> None:
    """Real decoder failures stay inside the export field-error boundary."""

    with pytest.raises(ExportFieldError) as exc_info:
        verify_export_metadata(
            payload=payload,
            export_format=export_format,
            byte_size=len(payload),
            sha256=sha256_hex(payload),
            media_type=media_type,
            filename_extension=filename_extension,
            row_count=0,
        )

    assert exc_info.value.context == {"reason": "payload_decode_invalid", "export_format": export_format.value}


@pytest.mark.parametrize(
    ("payload", "expected_reason"),
    (
        (b"not-json\n", "payload_decode_invalid"),
        (b"[]\n", "jsonl_record_invalid"),
        (b'"scalar"\n', "jsonl_record_invalid"),
    ),
)
def test_jsonl_verification_refuses_invalid_or_non_object_lines(payload: bytes, expected_reason: str) -> None:
    """JSON Lines exports must contain parseable object records, never arbitrary text."""

    with pytest.raises(ExportFieldError) as exc_info:
        verify_export_metadata(
            payload=payload,
            export_format=ExportSerializationFormat.JSONL,
            byte_size=len(payload),
            sha256=sha256_hex(payload),
            media_type=JSONL_MIME_TYPE,
            filename_extension="jsonl",
            row_count=1,
        )

    assert exc_info.value.context is not None
    assert exc_info.value.context["reason"] == expected_reason
