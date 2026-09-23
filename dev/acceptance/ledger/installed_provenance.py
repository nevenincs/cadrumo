"""Narrow installed-wheel check of public Ledger import filename and row display.

One synthetic invoice CSV and one synthetic bank-statement CSV are imported
through the installed public CLI into a fresh store.  The imported filename
and one-based source row are then read back through ``ledger invoice view``
JSON, ``ledger track`` JSON and text, and the installed TUI invoice and
transaction details.  The profile secret crosses every process boundary on
stdin only and never reaches the receipt.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import secrets
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from dev.acceptance.income_tax.installed_tui_child import (
    InstalledTuiChildError,
    assert_installed_product_origin,
    installed_product_evidence,
    query_public_selector,
    read_passphrase_from_stdin,
    run_installed_tui_child_process,
)
from dev.acceptance.installed_cli import (
    InstalledCli,
    InstalledCliError,
    authority_generation,
    build_installed_cli_environment,
)

from .installed_tui_journey import (
    LedgerInstalledTuiError,
    _admit_existing_profile_for_headless_launcher,
    _open_invoice_detail,
    _open_transaction_detail,
    _require_empty_directory,
    _result,
    _run_launcher,
    _text,
)
from .scenario import build_ledger_cli_scenario

_SCHEMA = "ledger-01-installed-provenance-v1"
_PATTERN_REVISION = "1.7"
_BRIEF_REVISION = "0.1"
_YEAR = 2025
_INVOICE_FILE = "ledger-provenance-invoice.csv"
_STATEMENT_FILE = "ledger-provenance-statement.csv"
_STATEMENT_DESCRIPTION = "ledger-provenance-statement-row"
# Both importers number rows by physical CSV line, so the first data row after
# the header is row 2.
_SOURCE_ROW = 2
_N26_HEADER = ("Date", "Payee", "Payment reference", "Amount (EUR)", "Currency", "Transaction ID")
_TUI_OBSERVATIONS = (
    "installed_tui_invoice_source_filename_and_row",
    "installed_tui_transaction_source_filename_and_row",
)
_CLI_OBSERVATIONS = (
    "installed_cli_invoice_view_json_source_filename_and_row",
    "installed_cli_transaction_track_json_source_filename_and_row",
    "installed_cli_transaction_track_text_source_filename_and_row",
)


def _write_invoice_csv(path: Path) -> str:
    """Write the scenario's accepted received-invoice row and return its public number."""
    source = build_ledger_cli_scenario(_YEAR).structured_import
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(source.columns)
        writer.writerow(source.rows[0].values)
    return source.row_values(source.rows[0])["invoice_number"]


def _write_statement_csv(path: Path) -> None:
    """Write one synthetic bank-statement row in the public CSV provider shape."""
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(_N26_HEADER)
        writer.writerow(
            (f"{_YEAR}-03-16", "Ledger synthetic counterparty", _STATEMENT_DESCRIPTION, "10.00", "EUR", "ledger-prov-1")
        )


def assert_json_provenance(payload: Mapping[str, Any], *, filename: str, row: int, stage: str) -> None:
    """Require the public JSON filename and row projection of one imported record."""
    if (payload.get("source_filename"), payload.get("source_row_index")) != (filename, row):
        raise LedgerInstalledTuiError(f"{stage} did not expose the imported filename and row")


def assert_track_text_provenance(text: str, *, filename: str, row: int) -> None:
    """Require the tab-separated import source and row lines of ``ledger track`` text."""
    lines = set(text.splitlines())
    if f"import_source\t{filename}" not in lines or f"import_source_row\t{row}" not in lines:
        raise LedgerInstalledTuiError("installed ledger track text did not expose the imported filename and row")


def assert_detail_provenance(rendered: str, *, filename: str, row: int, stage: str) -> None:
    """Require the ``filename:row`` provenance token in one rendered TUI detail."""
    if f"{filename}:{row}" not in rendered:
        raise LedgerInstalledTuiError(f"{stage} did not display the imported filename and row")


def _cli_track_text(cli: InstalledCli, transaction_id: str) -> str:
    """Read ``ledger track`` in its default text format with the shared installed environment."""
    completed = subprocess.run(  # noqa: S603 - executable comes from explicit installed-wheel input
        [str(cli.executable), "--profile-secrets-stdin", "app", "ledger", "track", transaction_id],
        check=False,
        capture_output=True,
        cwd=cli.storage_root,
        env=build_installed_cli_environment(storage_root=cli.storage_root, authority_root=cli.authority_root),
        input=json.dumps({"profile_passphrase": cli.passphrase}, separators=(",", ":")),
        text=True,
        timeout=180,
        encoding="utf-8",
    )
    if completed.returncode != 0:
        raise LedgerInstalledTuiError(f"installed CLI ledger.track text failed (exit_code={completed.returncode})")
    return completed.stdout


def _cli(cli: InstalledCli, arguments: Sequence[str], *, command: str, stage: str) -> dict[str, Any]:
    """Run one public JSON command and name the failed stage without retaining payloads."""
    try:
        return _result(cli.run(arguments, command=command), stage=stage)
    except InstalledCliError as error:
        raise LedgerInstalledTuiError(f"{stage}: installed CLI {command} failed") from error


def _installed_public_cli_imports(cli: InstalledCli, root: Path) -> str:
    """Import both synthetic sources through public CLI and check CLI provenance readback."""
    try:
        cli.create_profile(year=_YEAR)
    except InstalledCliError as error:
        raise LedgerInstalledTuiError("installed CLI profile creation failed") from error

    invoice_path = root / _INVOICE_FILE
    invoice_number = _write_invoice_csv(invoice_path)
    imported_invoice = _cli(
        cli,
        ("app", "ledger", "invoice", "import", "--file", str(invoice_path), "--kind", "received"),
        command="ledger.invoice.import",
        stage="provenance invoice import",
    )
    invoice_ids = imported_invoice.get("created_invoice_ids")
    if imported_invoice.get("created") != 1 or not isinstance(invoice_ids, list) or len(invoice_ids) != 1:
        raise LedgerInstalledTuiError("installed invoice import did not create exactly one public invoice")
    invoice_view = _cli(
        cli,
        ("app", "ledger", "invoice", "view", _text(invoice_ids[0], stage="provenance invoice import")),
        command="ledger.invoice.view",
        stage="provenance invoice readback",
    )
    assert_json_provenance(invoice_view, filename=_INVOICE_FILE, row=_SOURCE_ROW, stage="installed invoice view JSON")

    statement_path = root / _STATEMENT_FILE
    _write_statement_csv(statement_path)
    imported_statement = _cli(
        cli,
        ("app", "ledger", "import", "--file", str(statement_path), "--provider", "csv"),
        command="ledger.import",
        stage="provenance statement import",
    )
    if imported_statement.get("imported") != 1:
        raise LedgerInstalledTuiError("installed statement import did not create exactly one row")
    listed = _cli(cli, ("app", "ledger", "list"), command="ledger.list", stage="provenance statement discovery")
    rows = listed.get("rows")
    if not isinstance(rows, list):
        raise LedgerInstalledTuiError("installed ledger list omitted public rows")
    matches = [row for row in rows if isinstance(row, dict) and row.get("description") == _STATEMENT_DESCRIPTION]
    if len(matches) != 1:
        raise LedgerInstalledTuiError("installed ledger list did not identify one imported transaction")
    transaction_id = _text(matches[0].get("transaction_id"), stage="provenance statement discovery")
    tracked = _cli(
        cli,
        ("app", "ledger", "track", transaction_id),
        command="ledger.track",
        stage="provenance JSON track",
    )
    assert_json_provenance(tracked, filename=_STATEMENT_FILE, row=_SOURCE_ROW, stage="installed ledger track JSON")
    assert_track_text_provenance(_cli_track_text(cli, transaction_id), filename=_STATEMENT_FILE, row=_SOURCE_ROW)
    return invoice_number


def _run_child(*, workspace_root: Path, invoice_number: str, passphrase: str) -> dict[str, object]:
    """Open both imported records through the installed TUI and read their rendered details."""
    from textual.widgets import Static

    _admit_existing_profile_for_headless_launcher(passphrase=passphrase)
    observations: list[str] = []

    async def drive(pilot: Any) -> None:
        await _open_invoice_detail(pilot, invoice_number=invoice_number)
        assert_detail_provenance(
            str(query_public_selector(pilot, "#ledger-record-detail", Static).render()),
            filename=_INVOICE_FILE,
            row=_SOURCE_ROW,
            stage="installed TUI invoice detail",
        )
        observations.append(_TUI_OBSERVATIONS[0])
        await _open_transaction_detail(pilot, description=_STATEMENT_DESCRIPTION)
        assert_detail_provenance(
            str(query_public_selector(pilot, "#ledger-record-detail", Static).render()),
            filename=_STATEMENT_FILE,
            row=_SOURCE_ROW,
            stage="installed TUI transaction detail",
        )
        observations.append(_TUI_OBSERVATIONS[1])
        pilot.app.exit()

    _run_launcher(passphrase=passphrase, drive_after_home=drive)
    if tuple(observations) != _TUI_OBSERVATIONS:
        raise LedgerInstalledTuiError("installed TUI provenance callback did not finish")
    product = installed_product_evidence(workspace_root=workspace_root)
    return {
        "schema_version": _SCHEMA,
        "status": "proven",
        "product_origin": product.product_origin,
        "product_init_path": str(assert_installed_product_origin(workspace_root=workspace_root)),
        "product_init_sha256": product.product_init_sha256,
        "observations": observations,
    }


def _parse_child_receipt(path: Path) -> dict[str, Any]:
    """Read the child's value-free receipt and require its installed-origin proof."""
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise LedgerInstalledTuiError("installed TUI provenance child receipt is unreadable") from error
    if (
        not isinstance(document, dict)
        or document.get("schema_version") != _SCHEMA
        or document.get("status") != "proven"
        or document.get("product_origin") != "site-packages"
        or not isinstance(document.get("product_init_sha256"), str)
        or len(document["product_init_sha256"]) != 64
        or not isinstance(document.get("product_init_path"), str)
        or tuple(document.get("observations") or ()) != _TUI_OBSERVATIONS
    ):
        raise LedgerInstalledTuiError("installed TUI provenance child did not prove both details")
    return document


def _run_outer(args: argparse.Namespace) -> dict[str, object]:
    """Run the public CLI imports and one installed TUI child against a fresh synthetic store."""
    cli_executable = args.cli.resolve(strict=True)
    python_executable = args.python.resolve(strict=True)
    if cli_executable.parent != python_executable.parent:
        raise LedgerInstalledTuiError("installed CLI and TUI child Python do not belong to one environment")
    wheel_sha256 = hashlib.sha256(args.wheel.read_bytes()).hexdigest()
    authority_root = args.authority_root.resolve(strict=True)
    root = _require_empty_directory(args.output_root, label="Ledger provenance output root")
    store = _require_empty_directory(root / "secure-store", label="Ledger provenance secure store")
    passphrase = secrets.token_urlsafe(32)
    cli = InstalledCli(cli_executable, storage_root=store, authority_root=authority_root, passphrase=passphrase)
    invoice_number = _installed_public_cli_imports(cli, root)
    child_path = root / "installed-tui-child.json"
    child = run_installed_tui_child_process(
        python_executable=python_executable,
        workspace_root=args.workspace_root,
        child_module="dev.acceptance.ledger.installed_provenance",
        child_args=(
            "--child",
            "--workspace-root",
            str(args.workspace_root),
            "--receipt",
            str(child_path),
            "--invoice-number",
            invoice_number,
        ),
        storage_root=store,
        receipt_path=child_path,
        passphrase=passphrase,
        authority_root=authority_root,
        timeout_seconds=900,
    )
    if child.returncode != 0:
        raise LedgerInstalledTuiError("installed TUI provenance child exited unsuccessfully")
    child_doc = _parse_child_receipt(child_path)
    return {
        "schema_version": _SCHEMA,
        "status": "proven",
        "pattern_revision": _PATTERN_REVISION,
        "brief_revision": _BRIEF_REVISION,
        "source_commit": args.source_commit,
        "wheel_filename": args.wheel.name,
        "wheel_sha256": wheel_sha256,
        "authority_generation": authority_generation(authority_root),
        "year": _YEAR,
        "product_origin": child_doc["product_origin"],
        "product_init_path": child_doc["product_init_path"],
        "product_init_sha256": child_doc["product_init_sha256"],
        "source_files": [_INVOICE_FILE, _STATEMENT_FILE],
        "source_row_index": _SOURCE_ROW,
        "cli_observations": list(_CLI_OBSERVATIONS),
        "tui_observations": child_doc["observations"],
        "cli_json_command_count": len(cli.commands),
        "cli_text_command_count": 1,
        "tui_child_process_count": 1,
        "synthetic_store_retained": True,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--child", action="store_true")
    parser.add_argument("--cli", type=Path)
    parser.add_argument("--python", type=Path)
    parser.add_argument("--wheel", type=Path)
    parser.add_argument("--workspace-root", required=True, type=Path)
    parser.add_argument("--authority-root", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--source-commit")
    parser.add_argument("--invoice-number")
    parser.add_argument("--receipt", required=True, type=Path)
    return parser


def _failure_document(error: Exception) -> dict[str, object]:
    """Reduce a failure to its type and, for driver-owned refusals, the value-free stage message."""
    if isinstance(error, LedgerInstalledTuiError):
        diagnostic = str(error)
    elif isinstance(error, (InstalledTuiChildError, InstalledCliError)):
        diagnostic = "installed frontend or command failed"
    else:
        diagnostic = "unexpected installed Ledger provenance failure"
    return {"schema_version": _SCHEMA, "status": "failed", "error_type": type(error).__name__, "diagnostic": diagnostic}


def main(argv: Sequence[str] | None = None) -> int:
    """Run the installed outer provenance check or its stdin-credentialed TUI child."""
    args = _parser().parse_args(argv)
    try:
        if args.child:
            if not args.invoice_number:
                raise LedgerInstalledTuiError("installed TUI provenance child has no public invoice coordinate")
            document = _run_child(
                workspace_root=args.workspace_root,
                invoice_number=args.invoice_number,
                passphrase=read_passphrase_from_stdin(),
            )
        else:
            if None in (args.cli, args.python, args.wheel, args.authority_root, args.output_root, args.source_commit):
                raise LedgerInstalledTuiError("installed provenance outer run lacks its wheel and source inputs")
            document = _run_outer(args)
    except Exception as error:
        document = _failure_document(error)
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if document["status"] == "proven" else 2


if __name__ == "__main__":  # pragma: no cover - module entry point
    raise SystemExit(main())
