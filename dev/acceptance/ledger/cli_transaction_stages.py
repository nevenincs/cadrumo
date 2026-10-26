"""Installed public transaction linking and encrypted document custody observations."""

from __future__ import annotations

import hashlib
from decimal import Decimal
from pathlib import Path

from cadrumo.tests.pdf_fixtures import text_pdf_bytes
from dev.acceptance.installed_cli import InstalledCli

from .cli_contracts import _expect, _LedgerRun, _result
from .scenario import LedgerCliScenario, TransactionFixture


def _add_and_link(
    run: _LedgerRun,
    cli: InstalledCli,
    fixture: TransactionFixture,
    invoice_ids: dict[str, str],
    transaction_ids: dict[str, str],
) -> None:
    created = _result(
        run(
            (
                "app",
                "ledger",
                "add",
                "--date",
                fixture.transaction_date.isoformat(),
                "--amount",
                str(fixture.amount),
                "--direction",
                fixture.direction,
                "--description",
                fixture.description,
                "--classification",
                fixture.classification,
                "--taxable-base",
                str(fixture.taxable_base),
                "--iva-rate",
                str(fixture.iva_rate_fraction),
                "--iva-amount",
                str(fixture.iva_amount),
                "--iva-category",
                fixture.iva_category,
                "--source-jurisdiction",
                "ES",
                "--idempotency-key",
                fixture.fixture_id,
            )
        ),
        stage="ledger add",
    )
    transaction_ids[fixture.fixture_id] = str(created["transaction_id"])
    run(
        (
            "app",
            "ledger",
            "link",
            transaction_ids[fixture.fixture_id],
            "--invoice-id",
            invoice_ids[fixture.linked_invoice_fixture_id],
        )
    )

    refused = run(
        (
            "app",
            "ledger",
            "update",
            transaction_ids[fixture.fixture_id],
            "--amount",
            str(fixture.amount + Decimal("1.00")),
        ),
        allow_error=True,
    )
    _expect(cli.commands[-1].returncode != 0, stage="linked identity edit refusal")
    _expect(refused.get("status") == "error", stage="linked identity edit status")


def _stage_purchase_evidence(
    run: _LedgerRun, scenario: LedgerCliScenario, output_root: Path, transaction_ids: dict[str, str]
) -> str:
    """Observe the installed ledger purchase evidence stage."""
    evidence = scenario.purchase_evidence
    document_path = output_root / evidence.filename
    document_bytes = text_pdf_bytes(evidence.text_lines)
    document_path.write_bytes(document_bytes)
    added_evidence = _result(
        run(("app", "ledger", "evidence", "add", str(document_path), "--supplier", evidence.supplier)),
        stage="purchase evidence add",
    )
    evidence_id = str(added_evidence["evidence_id"])
    _expect(added_evidence["source_sha256"] == hashlib.sha256(document_bytes).hexdigest(), stage="evidence digest")
    _expect(bool(added_evidence["attachment_id"]), stage="encrypted attachment reference")
    run(
        (
            "app",
            "ledger",
            "attach",
            transaction_ids[evidence.linked_transaction_fixture_id],
            "--purchase-invoice-evidence-id",
            evidence_id,
        )
    )
    reopened_evidence = _result(run(("app", "ledger", "evidence", "view", evidence_id)), stage="evidence view")
    _expect(reopened_evidence["attachment_id"] == added_evidence["attachment_id"], stage="evidence attachment custody")
    _expect(
        reopened_evidence["source_sha256"] == hashlib.sha256(document_bytes).hexdigest(), stage="evidence reopen digest"
    )
    return evidence_id
