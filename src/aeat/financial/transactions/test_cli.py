"""CLI smoke tests for ``aeat financial txs``."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ...cli import app as root_app
from .. import RawProvenance, SourceFormat
from ..providers import RawTransaction
from . import (
    BusinessClassification,
    Transaction,
    TransactionCatalogue,
    TransactionDirection,
    load_transactions,
    save_transactions,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_financial_input]

_RUNNER = CliRunner()
_CATALOGUE_FILENAME = "transactions.json"


def _sample_transaction(
    *,
    provider_id: str,
    amount: Decimal,
    description: str,
    classification: BusinessClassification = BusinessClassification.UNCLASSIFIED,
) -> Transaction:
    raw = RawTransaction(
        transaction_id=provider_id,
        booked_date=date(2026, 4, 10),
        value_date=date(2026, 4, 10),
        amount=amount,
        currency="EUR",
        counterparty="Vendor SL",
        description=description,
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="c" * 64,
            source_row_index=3,
            source_format=SourceFormat.CSV,
            ingested_at=datetime(2026, 4, 14, 10, 0, tzinfo=UTC),
            provider_name="CSV provider",
        ),
        raw_fields={"Concepto": description},
    )
    return Transaction.model_validate(
        {
            "raw": raw,
            "direction": TransactionDirection.OUTGOING if amount < 0 else TransactionDirection.INCOMING,
            "business_classification": classification,
        }
    )


def _write_catalogue(tmp_path: Path) -> TransactionCatalogue:
    catalogue = TransactionCatalogue.from_transactions(
        [
            _sample_transaction(
                provider_id="provider-row-1",
                amount=Decimal("-45.00"),
                description="Train ticket",
            ),
            _sample_transaction(
                provider_id="provider-row-2",
                amount=Decimal("1200.00"),
                description="Client payment",
                classification=BusinessClassification.BUSINESS,
            ),
        ]
    )
    save_transactions(catalogue, tmp_path / _CATALOGUE_FILENAME)
    return catalogue


def test_financial_txs_list_filters_to_unclassified_records(tmp_path: Path) -> None:
    """`aeat financial txs list --unclassified` should filter catalogue output."""
    catalogue = _write_catalogue(tmp_path)
    ids = [transaction.transaction_id for transaction in catalogue.values()]

    result = _RUNNER.invoke(
        root_app,
        ["financial", "txs", "list", "--unclassified"],
        env={"AEAT_FINANCIAL_TXS_DIR": str(tmp_path)},
    )

    assert result.exit_code == 0, result.output
    assert ids[0] in result.output
    assert ids[1] not in result.output


def test_financial_txs_show_emits_json_payload(tmp_path: Path) -> None:
    """`aeat financial txs show <id>` should emit the stored transaction JSON."""
    catalogue = _write_catalogue(tmp_path)
    transaction = next(catalogue.values())

    result = _RUNNER.invoke(
        root_app,
        ["financial", "txs", "show", transaction.transaction_id],
        env={"AEAT_FINANCIAL_TXS_DIR": str(tmp_path)},
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["transaction_id"] == transaction.transaction_id
    assert payload["business_classification"] == "UNCLASSIFIED"


def test_financial_txs_classify_updates_catalogue_file(tmp_path: Path) -> None:
    """`aeat financial txs classify` should persist a manual classification."""
    catalogue = _write_catalogue(tmp_path)
    transaction = next(catalogue.values())

    result = _RUNNER.invoke(
        root_app,
        [
            "financial",
            "txs",
            "classify",
            transaction.transaction_id,
            "--as",
            "MIXED",
            "--pct",
            "0.5",
        ],
        env={"AEAT_FINANCIAL_TXS_DIR": str(tmp_path)},
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["business_classification"] == "MIXED"
    assert payload["business_pct"] == "0.5"
    restored = load_transactions(tmp_path / _CATALOGUE_FILENAME)
    updated = restored.get(transaction.transaction_id)
    assert updated is not None
    assert updated.business_classification is BusinessClassification.MIXED


def test_financial_txs_classify_rejects_invalid_business_pct_combo(tmp_path: Path) -> None:
    """`aeat financial txs classify` should exit cleanly on invalid percentage usage."""
    catalogue = _write_catalogue(tmp_path)
    transaction = next(catalogue.values())

    result = _RUNNER.invoke(
        root_app,
        [
            "financial",
            "txs",
            "classify",
            transaction.transaction_id,
            "--as",
            "BUSINESS",
            "--pct",
            "0.5",
        ],
        env={"AEAT_FINANCIAL_TXS_DIR": str(tmp_path)},
    )

    assert result.exit_code == 2
    assert "invalid classification update for transaction" in result.output


def test_financial_txs_classify_accepts_category_and_reason(tmp_path: Path) -> None:
    """`aeat financial txs classify` should persist category and reason/notes."""
    catalogue = _write_catalogue(tmp_path)
    transaction = next(catalogue.values())

    result = _RUNNER.invoke(
        root_app,
        [
            "financial",
            "txs",
            "classify",
            transaction.transaction_id,
            "--as",
            "BUSINESS",
            "--category",
            "cuotas_autonomos_ss",
            "--reason",
            "Payment for social security",
        ],
        env={"AEAT_FINANCIAL_TXS_DIR": str(tmp_path)},
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["business_classification"] == "BUSINESS"
    assert payload["category_id"] == "cuotas_autonomos_ss"
    assert payload["notes"] == "Payment for social security"

    restored = load_transactions(tmp_path / _CATALOGUE_FILENAME)
    updated = restored.get(transaction.transaction_id)
    assert updated is not None
    assert updated.category_id == "cuotas_autonomos_ss"
    assert updated.notes == "Payment for social security"
