"""Tests for application export serialization helpers."""

from __future__ import annotations

import csv
from io import StringIO

import pytest

from . import ExportSerializationFormat, serialize_tabular_rows
from ._errors import ExportFieldError, ExportFormatError

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def test_serialize_tabular_rows_writes_stable_csv_payload() -> None:
    result = serialize_tabular_rows(
        (
            {"transaction_id": "b", "amount": "2.00"},
            {"transaction_id": "a", "amount": "1.00"},
        ),
        fieldnames=("transaction_id", "amount"),
        export_format=ExportSerializationFormat.CSV,
    )

    parsed = tuple(csv.DictReader(StringIO(result.payload.decode("utf-8"))))
    assert parsed == (
        {"transaction_id": "b", "amount": "2.00"},
        {"transaction_id": "a", "amount": "1.00"},
    )
    assert result.media_type == "text/csv"
    assert result.filename_extension == "csv"
    assert result.byte_size == len(result.payload)
    assert len(result.sha256) == 64


def test_serialize_tabular_rows_writes_stable_jsonl_payload() -> None:
    result = serialize_tabular_rows(
        ({"transaction_id": "b", "amount": "2.00"},),
        fieldnames=("transaction_id", "amount"),
        export_format=ExportSerializationFormat.JSONL,
    )

    assert result.payload == b'{"amount":"2.00","transaction_id":"b"}\n'
    assert result.media_type == "application/x-ndjson"
    assert result.filename_extension == "jsonl"


def test_serialize_tabular_rows_rejects_unknown_fields() -> None:
    with pytest.raises(ExportFieldError, match="unknown fields"):
        serialize_tabular_rows(
            ({"transaction_id": "b", "amount": "2.00", "extra": "x"},),
            fieldnames=("transaction_id", "amount"),
            export_format=ExportSerializationFormat.CSV,
        )


# ---------------------------------------------------------------------------
# Registry membership — S06
# ---------------------------------------------------------------------------


def test_export_format_error_is_in_error_registry() -> None:
    """ExportFormatError must be registered so the CLI can handle it."""
    from aeat.core.errors import ERROR_REGISTRY

    assert "REFUSED_EXPORT_FORMAT" in ERROR_REGISTRY


def test_export_field_error_is_in_error_registry() -> None:
    """ExportFieldError must be registered so the CLI can handle it."""
    from aeat.core.errors import ERROR_REGISTRY

    assert "REFUSED_EXPORT_FIELD" in ERROR_REGISTRY


def test_export_format_error_code_attributes() -> None:
    """ERROR_REGISTRY entry for ExportFormatError carries expected attributes."""
    from aeat.core.errors import ERROR_REGISTRY

    code = ERROR_REGISTRY["REFUSED_EXPORT_FORMAT"]
    assert code.code == "REFUSED_EXPORT_FORMAT"
    assert code.message_key == "errors.refused.refused_export_format"
    assert code.retryable is False


def test_export_field_error_code_attributes() -> None:
    """ERROR_REGISTRY entry for ExportFieldError carries expected attributes."""
    from aeat.core.errors import ERROR_REGISTRY

    code = ERROR_REGISTRY["REFUSED_EXPORT_FIELD"]
    assert code.code == "REFUSED_EXPORT_FIELD"
    assert code.message_key == "errors.refused.refused_export_field"
    assert code.retryable is False


# ---------------------------------------------------------------------------
# Envelope round-trip — S06
# ---------------------------------------------------------------------------


def test_export_format_error_build_error_envelope() -> None:
    """build_error_envelope must succeed for ExportFormatError."""
    from aeat.core.errors import build_error_envelope

    err = ExportFormatError("unsupported export format: 'xml'")
    envelope = build_error_envelope(err)
    assert envelope.code == "REFUSED_EXPORT_FORMAT"
    assert envelope.category == "REFUSED"
    assert envelope.retryable is False
    assert envelope.schema_version == "1"


def test_export_field_error_build_error_envelope() -> None:
    """build_error_envelope must succeed for ExportFieldError."""
    from aeat.core.errors import build_error_envelope

    err = ExportFieldError("fieldnames must not be empty")
    envelope = build_error_envelope(err)
    assert envelope.code == "REFUSED_EXPORT_FIELD"
    assert envelope.category == "REFUSED"
    assert envelope.retryable is False
    assert envelope.schema_version == "1"


# ---------------------------------------------------------------------------
# Locale translated_message key — S06
# ---------------------------------------------------------------------------


def test_export_format_error_locale_key_present_in_catalogue() -> None:
    """The locale catalogue must carry the refused_export_format key for every locale."""
    import importlib.resources
    import pathlib
    import yaml

    locale_dir = pathlib.Path(
        importlib.resources.files("aeat.locales").__str__()  # type: ignore[arg-type]
    )
    for locale_code in ("en", "es", "ca", "hu"):
        text = (locale_dir / f"{locale_code}.yml").read_text(encoding="utf-8")
        data = yaml.safe_load(text)
        value = data.get("errors", {}).get("refused", {}).get("refused_export_format")
        assert value, (
            f"locale {locale_code!r}: 'errors.refused.refused_export_format' key is "
            f"missing or empty in {locale_code}.yml"
        )


def test_export_field_error_locale_key_present_in_catalogue() -> None:
    """The locale catalogue must carry the refused_export_field key for every locale."""
    import importlib.resources
    import pathlib
    import yaml

    locale_dir = pathlib.Path(
        importlib.resources.files("aeat.locales").__str__()  # type: ignore[arg-type]
    )
    for locale_code in ("en", "es", "ca", "hu"):
        text = (locale_dir / f"{locale_code}.yml").read_text(encoding="utf-8")
        data = yaml.safe_load(text)
        value = data.get("errors", {}).get("refused", {}).get("refused_export_field")
        assert value, (
            f"locale {locale_code!r}: 'errors.refused.refused_export_field' key is "
            f"missing or empty in {locale_code}.yml"
        )


# ---------------------------------------------------------------------------
# Real raise sites — S06: seven replaced ValueError sites
# ---------------------------------------------------------------------------


def test_normalize_fieldnames_raises_export_field_error_on_empty_sequence() -> None:
    """Site: _normalize_fieldnames — empty fieldnames sequence."""
    with pytest.raises(ExportFieldError, match="must not be empty"):
        serialize_tabular_rows(
            (),
            fieldnames=(),
            export_format=ExportSerializationFormat.CSV,
        )


def test_normalize_fieldnames_raises_export_field_error_on_blank_name() -> None:
    """Site: _normalize_fieldnames — blank field name."""
    with pytest.raises(ExportFieldError, match="blank values"):
        serialize_tabular_rows(
            (),
            fieldnames=("transaction_id", "  "),
            export_format=ExportSerializationFormat.CSV,
        )


def test_normalize_fieldnames_raises_export_field_error_on_duplicate_names() -> None:
    """Site: _normalize_fieldnames — duplicate field names."""
    with pytest.raises(ExportFieldError, match="duplicates"):
        serialize_tabular_rows(
            (),
            fieldnames=("amount", "amount"),
            export_format=ExportSerializationFormat.CSV,
        )


def test_normalize_row_raises_export_field_error_on_unknown_field() -> None:
    """Site: _normalize_row — row contains unknown field keys."""
    with pytest.raises(ExportFieldError, match="unknown fields"):
        serialize_tabular_rows(
            ({"transaction_id": "a", "amount": "1.00", "bogus": "x"},),
            fieldnames=("transaction_id", "amount"),
            export_format=ExportSerializationFormat.JSONL,
        )


def test_model_validator_raises_export_field_error_on_blank_fieldname() -> None:
    """Site: TabularExportResult._validate_fieldnames — blank field in model."""
    from ._tabular import TabularExportResult
    import hashlib
    from pydantic import ValidationError

    payload = b"transaction_id,amount\r\n"
    with pytest.raises((ExportFieldError, ValidationError)):
        TabularExportResult(
            format=ExportSerializationFormat.CSV,
            media_type="text/csv",
            filename_extension="csv",
            payload=payload,
            byte_size=len(payload),
            sha256=hashlib.sha256(payload).hexdigest(),
            row_count=0,
            fieldnames=("transaction_id", "  "),
        )


def test_model_validator_raises_export_field_error_on_duplicate_fieldname() -> None:
    """Site: TabularExportResult._validate_fieldnames — duplicate field in model."""
    from ._tabular import TabularExportResult
    import hashlib
    from pydantic import ValidationError

    payload = b"amount,amount\r\n"
    with pytest.raises((ExportFieldError, ValidationError)):
        TabularExportResult(
            format=ExportSerializationFormat.CSV,
            media_type="text/csv",
            filename_extension="csv",
            payload=payload,
            byte_size=len(payload),
            sha256=hashlib.sha256(payload).hexdigest(),
            row_count=0,
            fieldnames=("amount", "amount"),
        )
