"""Tests for application export serialization helpers."""

from __future__ import annotations

import csv
from io import StringIO

import pytest

from . import ExportSerializationFormat, serialize_tabular_rows

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
    with pytest.raises(ValueError, match="unknown fields"):
        serialize_tabular_rows(
            ({"transaction_id": "b", "amount": "2.00", "extra": "x"},),
            fieldnames=("transaction_id", "amount"),
            export_format=ExportSerializationFormat.CSV,
        )
