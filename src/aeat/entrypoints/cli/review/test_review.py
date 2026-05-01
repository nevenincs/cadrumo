"""Unit tests for ``aeat review history`` (#237)."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ....adapters.inbound.financial import RawProvenance, RawTransaction, SourceFormat
from ....domain.transactions import (
    BusinessClassification,
    Transaction,
    TransactionCatalogue,
    TransactionCatalogueRepository,
    TransactionDirection,
    set_classification,
)
from .. import app as root_app

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

_RUNNER = CliRunner()


def _sample_transaction(provider_id: str = "review-row-1") -> Transaction:
    raw = RawTransaction(
        transaction_id=provider_id,
        booked_date=date(2026, 4, 10),
        value_date=date(2026, 4, 10),
        amount=Decimal("-50.00"),
        currency="EUR",
        counterparty="Vendor SL",
        description="Review history fixture",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="d" * 64,
            source_row_index=1,
            source_format=SourceFormat.CSV,
            ingested_at=datetime(2026, 4, 14, 9, 0, tzinfo=UTC),
            provider_name="CSV provider",
        ),
        raw_fields={"Concepto": "Review history fixture"},
    )
    return Transaction.model_validate(
        {
            "raw": raw,
            "direction": TransactionDirection.OUTGOING,
        }
    )


def test_review_history_prints_full_chain_oldest_first(tmp_path: Path) -> None:
    """The history chain must be emitted oldest first, with the current head appended last."""
    transaction = _sample_transaction()
    catalogue = TransactionCatalogue.from_transactions([transaction])
    classified = set_classification(
        catalogue,
        transaction.transaction_id,
        classification=BusinessClassification.BUSINESS,
        classified_by="manual",
        reason="initial",
    )
    refined = set_classification(
        classified,
        transaction.transaction_id,
        classification=BusinessClassification.MIXED,
        business_pct=Decimal("0.5"),
        classified_by="manual",
        reason="corrected after review",
    )
    TransactionCatalogueRepository(store_dir=tmp_path).save(refined)

    result = _RUNNER.invoke(
        root_app,
        ["review", "history", transaction.transaction_id],
        env={"AEAT_FINANCIAL_TXS_DIR": str(tmp_path)},
    )

    assert result.exit_code == 0, result.output
    chain = json.loads(result.stdout)
    assert [entry["business_classification"] for entry in chain] == [
        BusinessClassification.NOT_YET_PROCESSED.value,
        BusinessClassification.BUSINESS.value,
        BusinessClassification.MIXED.value,
    ]
    assert chain[0]["reason"] == ""
    assert chain[1]["reason"] == "initial"
    assert chain[-1]["reason"] == "corrected after review"


def test_review_history_exits_cleanly_for_missing_transaction(tmp_path: Path) -> None:
    """Unknown transaction IDs must exit 2 with a clear diagnostic."""
    transaction = _sample_transaction()
    catalogue = TransactionCatalogue.from_transactions([transaction])
    TransactionCatalogueRepository(store_dir=tmp_path).save(catalogue)

    result = _RUNNER.invoke(
        root_app,
        ["review", "history", "missing-id"],
        env={"AEAT_FINANCIAL_TXS_DIR": str(tmp_path)},
    )

    assert result.exit_code == 2
    assert "transaction not found" in result.output
