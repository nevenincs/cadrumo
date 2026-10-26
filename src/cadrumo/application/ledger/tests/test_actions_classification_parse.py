"""Owner-local parser tests for bulk ledger classification CSV intake."""

from __future__ import annotations

import pytest

from ....domain.transactions.enums import BusinessClassification
from ..actions_classification import _parse_bulk_classify_rows

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

# Real hex-64 shapes, one per fixture row: BulkClassifyRow.transaction_id is
# typed core.identity.TransactionId, so a placeholder like the prior
# "tx-valid" literal fails shape validation before the CSV-parsing behaviour
# each test exercises (an invalid classification value; an extra cell) is
# ever reached, and the failure fixtures below stay distinct so a shape
# failure never masquerades as the reason under test.
_TX_VALID = "037fec1116ca801b2dd28423235f9c95cbe68fa8d62b232f4d10a6575849075c"
_TX_PERSONAL = "a58d805e62c0f78128d7bd8633a421649ea402e9560dabd4c270b4bdc3aebb09"
_TX_INVALID = "e5d088b4d57795626dbc10de96b7f28f407f828eb1da75e5c3b909695f5ac1c9"
_TX_EXTRA = "be3084a875bf6b05e423ec89db70bde7a6fce07201293a5b3a950101b0ae3049"


def test_parse_loop_collects_invalid_classification_and_keeps_valid_rows() -> None:
    parsed_rows, failures = _parse_bulk_classify_rows(
        "\n".join(
            (
                "transaction_id,classification",
                f"{_TX_VALID},BUSINESS",
                f"{_TX_INVALID},NOT_A_CLASSIFICATION",
                f"{_TX_PERSONAL},PERSONAL",
            ),
        ),
    )

    assert [row.transaction_id for _idx, row, _provided_columns in parsed_rows] == [_TX_VALID, _TX_PERSONAL]
    assert [row.classification for _idx, row, _provided_columns in parsed_rows] == [
        BusinessClassification.BUSINESS,
        BusinessClassification.PERSONAL,
    ]
    (failure,) = failures
    assert failure.row_index == 1
    assert failure.transaction_id == _TX_INVALID
    assert "NOT_A_CLASSIFICATION" in failure.reason


def test_parse_loop_reports_malformed_row_without_dropping_later_rows() -> None:
    parsed_rows, failures = _parse_bulk_classify_rows(
        "\n".join(
            (
                "transaction_id,classification",
                f"{_TX_EXTRA},BUSINESS,unexpected-cell",
                f"{_TX_VALID},PERSONAL",
            ),
        ),
    )

    assert [row.transaction_id for _idx, row, _provided_columns in parsed_rows] == [_TX_VALID]
    (failure,) = failures
    assert failure.row_index == 0
    assert failure.transaction_id == _TX_EXTRA
    assert failure.reason == "bulk classify CSV row has more cells than header columns"
