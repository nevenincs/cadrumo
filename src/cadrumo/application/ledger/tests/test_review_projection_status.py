"""A transaction's review status follows its business classification, one status per classification."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from decimal import Decimal

import pytest

from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.models import Transaction
from ...aggregation.tests.ledger_transaction_support import ledger_raw_transaction
from ...review.filter import LedgerReviewStatus
from ..review_projection import ledger_transaction_review_status

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.fixture(autouse=True)
def _pinned_authority() -> Iterator[None]:
    with bundled_indexed_authority().operation():
        yield


_EXPECTED = {
    BusinessClassification.BUSINESS: LedgerReviewStatus.REVIEWED,
    BusinessClassification.PERSONAL: LedgerReviewStatus.REVIEWED,
    BusinessClassification.MIXED: LedgerReviewStatus.REVIEWED,
    BusinessClassification.SKIPPED_BY_RULE: LedgerReviewStatus.SKIPPED,
    BusinessClassification.REVIEWED_EXCLUDED: LedgerReviewStatus.EXCLUDED,
}


@pytest.mark.parametrize("classification", list(BusinessClassification), ids=lambda value: value.name)
def test_every_classification_maps_to_its_review_status(classification: BusinessClassification) -> None:
    row = Transaction(
        raw=ledger_raw_transaction("review-status", booked_date=date(2026, 4, 15), amount=Decimal("10.00")),
        direction=TransactionDirection.OUTGOING,
        source_jurisdiction="ES",
        group_label=None,
    ).model_copy(update={"business_classification": classification})

    assert ledger_transaction_review_status(row) is _EXPECTED.get(classification, LedgerReviewStatus.PENDING)
