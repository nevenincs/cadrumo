"""Drive LEDGER-01 through the existing installed CLI adapter and public verbs."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import secrets
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from cadrumo.tests.pdf_fixtures import text_pdf_bytes
from dev.acceptance.installed_cli import CommandEvidence, InstalledCli

from .scenario import BRIEF_REVISION, SCENARIO_VERSION, TransactionFixture, build_ledger_cli_scenario


class LedgerJourneyError(RuntimeError):
    """A named public CLI acceptance invariant failed."""


@dataclass(frozen=True, slots=True)
class LedgerCliReceipt:
    """Sanitized facts retained after a fresh-process installed CLI journey."""

    brief_revision: str
    pattern_revision: str
    scenario: str
    executable: str
    package_identity: str
    storage_root: str
    authority_root: str
    authority_generation: str
    year: int
    invoice_count: int
    transaction_count: int
    linked_count: int
    imported_count: int
    replay_skipped_count: int
    evidence_count: int
    export_rows: int
    export_sha256: str
    command_count: int
    commands: tuple[CommandEvidence, ...]


def _result(document: dict[str, Any], *, stage: str) -> dict[str, Any]:
    value = document.get("result")
    if not isinstance(value, dict):
        raise LedgerJourneyError(f"{stage}: result is not an object")
    return value


def _equal_decimal(actual: object, expected: Decimal, *, stage: str) -> None:
    try:
        matches = Decimal(str(actual)) == expected
    except (ValueError, ArithmeticError):
        matches = False
    if not matches:
        raise LedgerJourneyError(f"{stage}: monetary meaning differs")


def _expect(condition: bool, *, stage: str) -> None:
    if not condition:
        raise LedgerJourneyError(f"{stage}: canonical readback differs")


def _write_import_fixture(path: Path, *, columns: tuple[str, ...], rows: tuple[tuple[str, ...], ...]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(columns)
        writer.writerows(rows)


def run_cli_journey(
    *,
    executable: Path,
    authority_root: Path,
    storage_root: Path,
    output_root: Path,
    year: int,
    package_identity: str,
) -> LedgerCliReceipt:
    """Create, edit, import, replay, export and reopen one isolated synthetic ledger."""
    if storage_root.exists() and any(storage_root.iterdir()):
        raise LedgerJourneyError("storage root must be fresh and empty")
    storage_root.mkdir(parents=True, exist_ok=True)
    output_root.mkdir(parents=True, exist_ok=False)
    descriptor = json.loads((authority_root / "authority.current.json").read_text(encoding="utf-8"))
    generation = descriptor.get("logical_generation")
    if not isinstance(generation, str) or not generation:
        raise LedgerJourneyError("authority generation is unavailable")
    scenario = build_ledger_cli_scenario(year)
    cli = InstalledCli(
        executable,
        storage_root=storage_root,
        authority_root=authority_root,
        passphrase=secrets.token_urlsafe(32),
    )
    cli.create_profile(year=year)

    def run(args: Sequence[str], *, allow_error: bool = False) -> dict[str, Any]:
        """Keep an installed-command failure diagnostic free of raw arguments."""
        command = " ".join(args[:4] if len(args) > 3 and args[2] == "invoice" else args[:3])
        try:
            document = cli.run(args, allow_error=True)
        except Exception as exc:
            raise LedgerJourneyError(f"{command}: installed command failed") from exc
        if cli.commands[-1].returncode != 0 and not allow_error:
            error = document.get("error")
            code = error.get("code") if isinstance(error, dict) else None
            safe_code = (
                code if isinstance(code, str) and code.replace("_", "").replace(".", "").isalnum() else "unknown"
            )
            raise LedgerJourneyError(f"{command}: installed command failed ({safe_code})")
        return document

    invoice_ids: dict[str, str] = {}
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

    transaction_ids: dict[str, str] = {}

    def add_and_link(fixture: TransactionFixture) -> None:
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

    for fixture in scenario.transactions:
        if fixture.linked_invoice_fixture_id in invoice_ids:
            add_and_link(fixture)

    update = scenario.invoice_update
    updated = _result(
        run(("app", "ledger", "invoice", "update", invoice_ids[update.invoice_fixture_id], "--notes", update.notes)),
        stage="invoice update",
    )
    _expect(updated["invoice_id"] == invoice_ids[update.invoice_fixture_id], stage="invoice update identity")
    _expect(updated["notes"] == update.notes, stage="invoice update notes")

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
        imported_view["source_sha256"] == hashlib.sha256(import_path.read_bytes()).hexdigest(),
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

    for fixture in scenario.transactions:
        if fixture.fixture_id not in transaction_ids:
            add_and_link(fixture)

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

    for fixture in scenario.manual_invoices:
        viewed = _result(
            run(("app", "ledger", "invoice", "view", invoice_ids[fixture.fixture_id])), stage="invoice view"
        )
        _expect(viewed["invoice_number"] == fixture.invoice_number, stage="invoice number")
        _expect(viewed["issued_at"] == fixture.invoice_date.isoformat(), stage="invoice issue date")
        _equal_decimal(viewed["base_total"], fixture.taxable_base, stage="invoice base")
        _equal_decimal(viewed["iva_total"], fixture.iva_amount, stage="invoice IVA")
        _equal_decimal(viewed["grand_total"], fixture.grand_total, stage="invoice grand total")
        _expect(viewed["notes"] == update.notes, stage="invoice edit readback")
        expected_linked = {
            transaction_ids[item.fixture_id]
            for item in scenario.transactions
            if item.linked_invoice_fixture_id == fixture.fixture_id
        }
        _expect(set(viewed["linked_transaction_ids"]) == expected_linked, stage="invoice reciprocal link")

    imported_view = _result(
        run(("app", "ledger", "invoice", "view", invoice_ids[source.fixture_id])), stage="linked imported invoice view"
    )
    _expect(
        set(imported_view["linked_transaction_ids"])
        == {
            transaction_ids[item.fixture_id]
            for item in scenario.transactions
            if item.linked_invoice_fixture_id == source.fixture_id
        },
        stage="imported invoice reciprocal link",
    )

    invoice_list = _result(run(("app", "ledger", "invoice", "list")), stage="invoice list")
    _expect(
        {str(row["invoice_id"]) for row in invoice_list["rows"]} == set(invoice_ids.values()),
        stage="fresh-process invoice list",
    )
    ledger_list = _result(run(("app", "ledger", "list")), stage="ledger list")
    rows = ledger_list["rows"]
    _expect({str(row["transaction_id"]) for row in rows} == set(transaction_ids.values()), stage="ledger identities")
    for fixture in scenario.transactions:
        row = next(row for row in rows if row["transaction_id"] == transaction_ids[fixture.fixture_id])
        _equal_decimal(row["amount"], fixture.amount, stage="transaction amount")
        _expect(row["direction"] == fixture.direction, stage="transaction direction")
        _expect(
            row["invoice_id"] == invoice_ids[fixture.linked_invoice_fixture_id], stage="transaction reciprocal link"
        )
        if fixture.fixture_id == evidence.linked_transaction_fixture_id:
            _expect(row["purchase_invoice_evidence_id"] == evidence_id, stage="evidence transaction association")

    export_path = output_root / "ledger.jsonl"
    exported = _result(
        run(("app", "ledger", "export", "--output", str(export_path), "--export-format", "jsonl")),
        stage="ledger export",
    )
    export_bytes = export_path.read_bytes()
    export_rows = [json.loads(line) for line in export_bytes.decode("utf-8").splitlines()]
    _expect(exported["row_count"] == len(export_rows) == len(rows), stage="ledger export row count")
    _expect(exported["sha256"] == hashlib.sha256(export_bytes).hexdigest(), stage="ledger export digest")
    _expect(
        {row["transaction_id"] for row in export_rows} == set(transaction_ids.values()),
        stage="ledger export identities",
    )
    for row in export_rows:
        source_row = next(item for item in rows if item["transaction_id"] == row["transaction_id"])
        _equal_decimal(row["amount"], Decimal(str(source_row["amount"])), stage="ledger export amount")
        _expect(row["invoice_id"] == source_row["invoice_id"], stage="ledger export reciprocal link")
        _expect(
            row["purchase_invoice_evidence_id"] == (source_row["purchase_invoice_evidence_id"] or ""),
            stage="ledger export evidence link",
        )
        _expect(row["direction"] == source_row["direction"], stage="ledger export direction")

    return LedgerCliReceipt(
        brief_revision=BRIEF_REVISION,
        pattern_revision="1.7",
        scenario=SCENARIO_VERSION,
        executable=str(cli.executable),
        package_identity=package_identity,
        storage_root=str(cli.storage_root),
        authority_root=str(cli.authority_root),
        authority_generation=generation,
        year=year,
        invoice_count=len(invoice_ids),
        transaction_count=len(transaction_ids),
        linked_count=len(transaction_ids),
        imported_count=int(imported["created"]),
        replay_skipped_count=int(replay["skipped_duplicate"]),
        evidence_count=1,
        export_rows=len(export_rows),
        export_sha256=hashlib.sha256(export_bytes).hexdigest(),
        command_count=len(cli.commands),
        commands=tuple(cli.commands),
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Run the installed journey and retain only a sanitized receipt."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cli", type=Path, required=True)
    parser.add_argument("--authority-root", type=Path, required=True)
    parser.add_argument("--storage-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--package-identity", required=True)
    args = parser.parse_args(argv)
    try:
        receipt = run_cli_journey(
            executable=args.cli,
            authority_root=args.authority_root,
            storage_root=args.storage_root,
            output_root=args.output_root,
            year=args.year,
            package_identity=args.package_identity,
        )
    except Exception as exc:
        failure = {
            "status": "failed",
            "brief_revision": BRIEF_REVISION,
            "pattern_revision": "1.7",
            "scenario": SCENARIO_VERSION,
            "package_identity": args.package_identity,
            "error_type": type(exc).__name__,
            "diagnostic": str(exc) if isinstance(exc, LedgerJourneyError) else "installed command or adapter failed",
        }
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(json.dumps(failure, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({"status": "failed", "receipt": str(args.receipt)}))
        return 2
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(asdict(receipt), sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "journey_complete", "receipt": str(args.receipt)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
