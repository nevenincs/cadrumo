"""Installed public invoice creation, edit, import and replay observations."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from cadrumo.core.hashing import sha256_file
from dev.acceptance.installed_cli import InstalledCli

from .cli_contracts import _equal_decimal, _expect, _LedgerRun, _result
from .scenario import LedgerCliScenario


def _write_import_fixture(path: Path, *, columns: tuple[str, ...], rows: tuple[tuple[str, ...], ...]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(columns)
        writer.writerows(rows)


def _stage_manual_invoices(run: _LedgerRun, scenario: LedgerCliScenario, invoice_ids: dict[str, str]) -> None:
    """Observe the installed ledger manual invoices stage."""
    for fixture in scenario.manual_invoices:
        created = _result(
            run(
                (
                    "app",
                    "ledger",
                    "invoice",
                    "add",
                    "--kind",
                    fixture.kind,
                    "--counterparty-name",
                    fixture.counterparty_name,
                    "--counterparty-nif",
                    fixture.counterparty_tax_id,
                    "--invoice-number",
                    fixture.invoice_number,
                    "--invoice-date",
                    fixture.invoice_date.isoformat(),
                    "--taxable-base",
                    str(fixture.taxable_base),
                    "--iva-rate",
                    fixture.cli_iva_rate_percent,
                    "--country-code",
                    fixture.counterparty_country,
                    "--iva-category",
                    fixture.iva_category,
                    "--notes",
                    fixture.notes,
                )
            ),
            stage="invoice add",
        )
        invoice_ids[fixture.fixture_id] = str(created["invoice_id"])
        _equal_decimal(created["grand_total"], fixture.grand_total, stage="invoice add total")


def _stage_invoice_edit(run: _LedgerRun, scenario: LedgerCliScenario, invoice_ids: dict[str, str]) -> None:
    """Observe the installed ledger invoice edit stage."""
    update = scenario.invoice_update
    updated = _result(
        run(("app", "ledger", "invoice", "update", invoice_ids[update.invoice_fixture_id], "--notes", update.notes)),
        stage="invoice update",
    )
    _expect(updated["invoice_id"] == invoice_ids[update.invoice_fixture_id], stage="invoice update identity")
    _expect(updated["notes"] == update.notes, stage="invoice update notes")


def _stage_invoice_import(
    run: _LedgerRun, cli: InstalledCli, scenario: LedgerCliScenario, output_root: Path, invoice_ids: dict[str, str]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Observe the installed ledger invoice import stage."""
    source = scenario.structured_import
    import_path = output_root / source.filename
    _write_import_fixture(import_path, columns=source.columns, rows=tuple(row.values for row in source.rows))
    unsupported_path = output_root / "unsupported-invoices.txt"
    unsupported_path.write_bytes(import_path.read_bytes())
    unsupported = run(
        ("app", "ledger", "invoice", "import", "--file", str(unsupported_path), "--kind", source.kind),
        allow_error=True,
    )
    _expect(cli.commands[-1].returncode != 0, stage="unsupported import extension refusal")
    _expect(unsupported.get("status") == "error", stage="unsupported import extension status")
    import_command = ("app", "ledger", "invoice", "import", "--file", str(import_path), "--kind", source.kind)
    imported = _result(run(import_command), stage="invoice import")
    _expect(imported["created"] == source.expected_created, stage="invoice import count")
    _expect(len(imported["refused"]) == source.expected_refused, stage="invoice import refusal count")
    _expect(imported["refused"][0]["row_number"] == source.rows[1].source_row, stage="invoice import refused row")
    _expect(imported["refused"][0]["field"] == "invoice_number", stage="invoice import refused field")
    imported_ids = imported["created_invoice_ids"]
    _expect(isinstance(imported_ids, list) and len(imported_ids) == 1, stage="invoice import identities")
    invoice_ids[source.fixture_id] = str(imported_ids[0])
    imported_view = _result(
        run(("app", "ledger", "invoice", "view", invoice_ids[source.fixture_id])), stage="imported invoice view"
    )
    _expect(imported_view["source_filename"] == source.filename, stage="invoice import source filename")
    _expect(imported_view["source_row_index"] == source.rows[0].source_row, stage="invoice import source row")
    _expect(
        imported_view["source_sha256"] == sha256_file(import_path),
        stage="invoice source digest",
    )
    replay_path = output_root / "ledger-received-replay.csv"
    _write_import_fixture(replay_path, columns=source.columns, rows=(source.rows[0].values,))
    replay = _result(
        run(("app", "ledger", "invoice", "import", "--file", str(replay_path), "--kind", source.kind)),
        stage="invoice replay",
    )
    _expect(replay["created"] == 0, stage="invoice replay created")
    _expect(replay["skipped_duplicate"] == source.expected_replay_skipped_duplicate, stage="invoice replay skip")
    return imported, replay
