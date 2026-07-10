"""Owner-local parser tests for bulk ledger classification CSV intake."""

from __future__ import annotations

import pytest

from ....domain.transactions import BusinessClassification
from .._actions_classification import _parse_bulk_classify_rows

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_parse_loop_collects_invalid_classification_and_keeps_valid_rows() -> None:
    parsed_rows, failures = _parse_bulk_classify_rows(
        "\n".join(
            (
                "transaction_id,classification",
                "tx-valid,BUSINESS",
                "tx-invalid,NOT_A_CLASSIFICATION",
                "tx-personal,PERSONAL",
            ),
        ),
    )

    assert [row.transaction_id for _idx, row, _provided_columns in parsed_rows] == ["tx-valid", "tx-personal"]
    assert [row.classification for _idx, row, _provided_columns in parsed_rows] == [
        BusinessClassification.BUSINESS,
        BusinessClassification.PERSONAL,
    ]
    (failure,) = failures
    assert failure.row_index == 1
    assert failure.transaction_id == "tx-invalid"
    assert "NOT_A_CLASSIFICATION" in failure.reason


def test_parse_loop_reports_malformed_row_without_dropping_later_rows() -> None:
    parsed_rows, failures = _parse_bulk_classify_rows(
        "\n".join(
            (
                "transaction_id,classification",
                "tx-extra,BUSINESS,unexpected-cell",
                "tx-valid,PERSONAL",
            ),
        ),
    )

    assert [row.transaction_id for _idx, row, _provided_columns in parsed_rows] == ["tx-valid"]
    (failure,) = failures
    assert failure.row_index == 0
    assert failure.transaction_id == "tx-extra"
    assert failure.reason == "bulk classify CSV row has more cells than header columns"
