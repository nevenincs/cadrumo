"""Fresh-process installed ledger readback and export parity observations."""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from .cli_contracts import LedgerRun, equal_decimal, expect, result
from .scenario import LedgerCliScenario


def stage_invoice_readback(
    run: LedgerRun, scenario: LedgerCliScenario, invoice_ids: dict[str, str], transaction_ids: dict[str, str]
) -> None:
    """Observe the installed ledger invoice readback stage."""
    source = scenario.structured_import
    update = scenario.invoice_update
    for fixture in scenario.manual_invoices:
        viewed = result(
            run(("app", "ledger", "invoice", "view", invoice_ids[fixture.fixture_id])), stage="invoice view"
        )
        expect(viewed["invoice_number"] == fixture.invoice_number, stage="invoice number")
        expect(viewed["issued_at"] == fixture.invoice_date.isoformat(), stage="invoice issue date")
        equal_decimal(viewed["base_total"], fixture.taxable_base, stage="invoice base")
        equal_decimal(viewed["iva_total"], fixture.iva_amount, stage="invoice IVA")
        equal_decimal(viewed["grand_total"], fixture.grand_total, stage="invoice grand total")
        expect(viewed["notes"] == update.notes, stage="invoice edit readback")
        expected_linked = {
            transaction_ids[item.fixture_id]
            for item in scenario.transactions
            if item.linked_invoice_fixture_id == fixture.fixture_id
        }
        expect(set(viewed["linked_transaction_ids"]) == expected_linked, stage="invoice reciprocal link")

    imported_view = result(
        run(("app", "ledger", "invoice", "view", invoice_ids[source.fixture_id])), stage="linked imported invoice view"
    )
    expect(
        set(imported_view["linked_transaction_ids"])
        == {
            transaction_ids[item.fixture_id]
            for item in scenario.transactions
            if item.linked_invoice_fixture_id == source.fixture_id
        },
        stage="imported invoice reciprocal link",
    )

    invoice_list = result(run(("app", "ledger", "invoice", "list")), stage="invoice list")
    expect(
        {str(row["invoice_id"]) for row in invoice_list["rows"]} == set(invoice_ids.values()),
        stage="fresh-process invoice list",
    )


def stage_transaction_readback(
    run: LedgerRun,
    scenario: LedgerCliScenario,
    invoice_ids: dict[str, str],
    transaction_ids: dict[str, str],
    evidence_id: str,
) -> list[dict[str, Any]]:
    """Observe the installed ledger transaction readback stage."""
    evidence = scenario.purchase_evidence
    ledger_list = result(run(("app", "ledger", "list")), stage="ledger list")
    rows = ledger_list["rows"]
    expect({str(row["transaction_id"]) for row in rows} == set(transaction_ids.values()), stage="ledger identities")
    for fixture in scenario.transactions:
        row = next(row for row in rows if row["transaction_id"] == transaction_ids[fixture.fixture_id])
        equal_decimal(row["amount"], fixture.amount, stage="transaction amount")
        expect(row["direction"] == fixture.direction, stage="transaction direction")
        expect(row["invoice_id"] == invoice_ids[fixture.linked_invoice_fixture_id], stage="transaction reciprocal link")
        if fixture.fixture_id == evidence.linked_transaction_fixture_id:
            expect(row["purchase_invoice_evidence_id"] == evidence_id, stage="evidence transaction association")
    return rows


def stage_export_readback(
    run: LedgerRun, output_root: Path, transaction_ids: dict[str, str], rows: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], bytes]:
    """Observe the installed ledger export readback stage."""
    export_path = output_root / "ledger.jsonl"
    exported = result(
        run(("app", "ledger", "export", "--output", str(export_path), "--export-format", "jsonl")),
        stage="ledger export",
    )
    export_bytes = export_path.read_bytes()
    export_rows = [json.loads(line) for line in export_bytes.decode("utf-8").splitlines()]
    expect(exported["row_count"] == len(export_rows) == len(rows), stage="ledger export row count")
    expect(exported["sha256"] == hashlib.sha256(export_bytes).hexdigest(), stage="ledger export digest")
    expect(
        {row["transaction_id"] for row in export_rows} == set(transaction_ids.values()),
        stage="ledger export identities",
    )
    for row in export_rows:
        source_row = next(item for item in rows if item["transaction_id"] == row["transaction_id"])
        equal_decimal(row["amount"], Decimal(str(source_row["amount"])), stage="ledger export amount")
        expect(row["invoice_id"] == source_row["invoice_id"], stage="ledger export reciprocal link")
        expect(
            row["purchase_invoice_evidence_id"] == (source_row["purchase_invoice_evidence_id"] or ""),
            stage="ledger export evidence link",
        )
        expect(row["direction"] == source_row["direction"], stage="ledger export direction")
    return export_rows, export_bytes
