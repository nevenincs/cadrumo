"""Pure transaction-catalogue fingerprint coverage for filing review."""

from __future__ import annotations

import pytest

from cadrumo.application.filing.draft_review import transaction_catalogue_fingerprint
from cadrumo.core.hashing import content_hash_hex
from cadrumo.domain.transactions.models import TransactionCatalogue

from .review_runtime_storage_support import review_runtime_transaction

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]


def test_transaction_catalogue_fingerprint_has_core_canonical_digest_parity() -> None:
    transaction = review_runtime_transaction("canonical")
    catalogue = TransactionCatalogue.from_transactions((transaction,))
    payload = [
        {
            "business_classification": transaction.business_classification.value,
            "business_pct": None,
            "category_id": None,
            "direction": transaction.direction.value,
            "invoice_id": None,
            "transaction_id": transaction.transaction_id,
        },
    ]

    assert transaction_catalogue_fingerprint(catalogue) == content_hash_hex(payload)
