"""Drive LEDGER-01 through ordered installed CLI stages and retain sanitized receipts."""

from __future__ import annotations

import argparse
import hashlib
import json
import secrets
from collections.abc import Sequence
from dataclasses import asdict
from functools import partial
from pathlib import Path
from typing import Any

from dev.acceptance.installed_cli import InstalledCli, authority_generation

from .cli_contracts import LedgerCliReceipt, LedgerJourneyError
from .cli_invoice_stages import _stage_invoice_edit, _stage_invoice_import, _stage_manual_invoices
from .cli_readback import _stage_export_readback, _stage_invoice_readback, _stage_transaction_readback
from .cli_transaction_stages import _add_and_link, _stage_purchase_evidence
from .scenario import BRIEF_REVISION, SCENARIO_VERSION, build_ledger_cli_scenario


def _run_installed_command(cli: InstalledCli, args: Sequence[str], *, allow_error: bool = False) -> dict[str, Any]:
    """Keep an installed-command failure diagnostic free of raw arguments."""
    command = " ".join(args[:4] if len(args) > 3 and args[2] == "invoice" else args[:3])
    try:
        document = cli.run(args, allow_error=True)
    except Exception as exc:
        raise LedgerJourneyError(f"{command}: installed command failed") from exc
    if cli.commands[-1].returncode != 0 and not allow_error:
        error = document.get("error")
        code = error.get("code") if isinstance(error, dict) else None
        safe_code = code if isinstance(code, str) and code.replace("_", "").replace(".", "").isalnum() else "unknown"
        raise LedgerJourneyError(f"{command}: installed command failed ({safe_code})")
    return document


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
    generation = authority_generation(authority_root)
    scenario = build_ledger_cli_scenario(year)
    cli = InstalledCli(
        executable,
        storage_root=storage_root,
        authority_root=authority_root,
        passphrase=secrets.token_urlsafe(32),
    )
    cli.create_profile(year=year)

    run = partial(_run_installed_command, cli)

    invoice_ids: dict[str, str] = {}
    _stage_manual_invoices(run, scenario, invoice_ids)

    transaction_ids: dict[str, str] = {}

    for fixture in scenario.transactions:
        if fixture.linked_invoice_fixture_id in invoice_ids:
            _add_and_link(run, cli, fixture, invoice_ids, transaction_ids)

    _stage_invoice_edit(run, scenario, invoice_ids)

    imported, replay = _stage_invoice_import(run, cli, scenario, output_root, invoice_ids)

    for fixture in scenario.transactions:
        if fixture.fixture_id not in transaction_ids:
            _add_and_link(run, cli, fixture, invoice_ids, transaction_ids)

    evidence_id = _stage_purchase_evidence(run, scenario, output_root, transaction_ids)

    _stage_invoice_readback(run, scenario, invoice_ids, transaction_ids)
    rows = _stage_transaction_readback(run, scenario, invoice_ids, transaction_ids, evidence_id)

    export_rows, export_bytes = _stage_export_readback(run, output_root, transaction_ids, rows)

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
