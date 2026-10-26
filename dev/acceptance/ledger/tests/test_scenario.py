"""Contract checks for the runner-free LEDGER-01 lifecycle fixture."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ..scenario import build_ledger_cli_scenario

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_lifecycle_fixture_preserves_manual_link_and_supported_metadata_update() -> None:
    scenario = build_ledger_cli_scenario(2025)

    issued = scenario.manual_invoices[0]
    transaction = scenario.transactions[0]
    assert issued.fixture_id == scenario.invoice_update.invoice_fixture_id
    assert issued.notes != scenario.invoice_update.notes
    assert transaction.linked_invoice_fixture_id == issued.fixture_id
    assert transaction.amount == issued.grand_total == Decimal("121.00")
    assert transaction.amount > Decimal()
    assert issued.iva_rate_fraction == transaction.iva_rate_fraction == Decimal("0.21")
    assert Decimal(issued.cli_iva_rate_percent) == Decimal("21")
    received = scenario.transactions[1]
    assert received.linked_invoice_fixture_id == scenario.structured_import.fixture_id
    assert received.amount == Decimal("60.50")
    assert scenario.purchase_evidence.linked_transaction_fixture_id == received.fixture_id


def test_structured_import_fixture_retains_row_provenance_and_replay_contract() -> None:
    scenario = build_ledger_cli_scenario(2025)

    imported = scenario.structured_import
    row = imported.rows[0]
    assert imported.fixture_id in scenario.fresh_process_invoice_fixture_ids
    assert imported.filename == "ledger-received.csv"
    assert row.source_row == 2
    assert imported.row_values(row) == {
        "counterparty_nif": "B12345674",
        "counterparty_name": "Synthetic supplier SL",
        "invoice_number": "LEDGER-REC-2025-001",
        "invoice_date": "2025-03-20",
        "taxable_base": "50.00",
        "iva_rate": "21",
        "country_code": "ES",
        "notes": "ledger-cli-import",
    }
    assert imported.rows[1].source_row == 3
    assert imported.row_values(imported.rows[1])["invoice_number"] == ""
    assert (imported.expected_created, imported.expected_refused, imported.expected_replay_skipped_duplicate) == (
        1,
        1,
        1,
    )
