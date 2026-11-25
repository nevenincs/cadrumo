"""Sequential public frontend continuations for installed ledger acceptance."""

from __future__ import annotations

import secrets
from pathlib import Path

from dev.acceptance.installed_cli import InstalledCli

from .frontend_contract import (
    assert_invoice_metadata_continuation,
    assert_linked_identity_refusal,
    assert_unlinked_detail_continuation,
)
from .installed_tui_cli_observations import (
    assert_tui_only_cli_oracle,
    find_invoice_by_number,
    read_invoice,
    read_transaction,
)
from .installed_tui_cli_transport import cli_command, create_profile, installed_tui_cli_transport_result
from .installed_tui_cli_writes import add_invoice, add_transaction, assert_linked_identity_refused, link_transaction
from .installed_tui_contracts import (
    INVOICE_TOTAL,
    SCHEMA_VERSION,
    LedgerContinuationReceipt,
    LedgerInstalledTuiError,
    LedgerTuiChildReceipt,
    TuiOnlyRun,
)
from .installed_tui_controls import tui_only_transaction_descriptions
from .installed_tui_export import compare_export
from .installed_tui_process import run_child
from .installed_tui_storage import require_empty_directory


def run_tui_only(
    *,
    python_executable: Path,
    workspace_root: Path,
    authority_root: Path,
    output_root: Path,
    year: int,
    cli_executable: Path | None = None,
) -> TuiOnlyRun:
    """Prove capture, detail update, and fresh-process readback using only installed TUI controls."""
    store = require_empty_directory(output_root / "secure-store", label="TUI-only Ledger store")
    passphrase = secrets.token_urlsafe(32)
    invoice_number = f"LEDGER-TUI-{year}-001"
    initial_notes = "ledger-tui-initial"
    updated_notes = "ledger-tui-updated"
    _initial_description, updated_description = tui_only_transaction_descriptions(year)
    capture = run_child(
        python_executable=python_executable,
        workspace_root=workspace_root,
        authority_root=authority_root,
        storage_root=store,
        receipt_path=output_root / "capture-update.json",
        passphrase=passphrase,
        mode="tui_only_capture_update",
        year=year,
        invoice_number=invoice_number,
        initial_notes=initial_notes,
        updated_notes=updated_notes,
    )
    reopened = run_child(
        python_executable=python_executable,
        workspace_root=workspace_root,
        authority_root=authority_root,
        storage_root=store,
        receipt_path=output_root / "fresh-reopen.json",
        passphrase=passphrase,
        mode="tui_only_reopen",
        year=year,
        invoice_number=invoice_number,
        initial_notes=updated_notes,
        transaction_description=updated_description,
    )
    if capture.product_init_sha256 != reopened.product_init_sha256:
        raise LedgerInstalledTuiError("TUI-only fresh child imported a different installed product")
    receipt = LedgerTuiChildReceipt(
        schema_version=SCHEMA_VERSION,
        status="proven",
        mode="tui_only_reopen",
        product_origin="site-packages",
        product_init_sha256=capture.product_init_sha256,
        observations=(*capture.observations, *reopened.observations),
    )
    if cli_executable is None:
        return TuiOnlyRun(receipt=receipt, cli_oracle_observations=(), cli_command_count=0)
    cli = InstalledCli(cli_executable, storage_root=store, authority_root=authority_root, passphrase=passphrase)
    return TuiOnlyRun(
        receipt=receipt,
        cli_oracle_observations=assert_tui_only_cli_oracle(
            cli,
            invoice_number=invoice_number,
            updated_notes=updated_notes,
            updated_description=updated_description,
        ),
        cli_command_count=len(cli.commands),
    )


def run_cli_to_tui(
    *,
    cli_executable: Path,
    python_executable: Path,
    workspace_root: Path,
    authority_root: Path,
    output_root: Path,
    year: int,
) -> tuple[LedgerContinuationReceipt, LedgerTuiChildReceipt]:
    """Continue public CLI capture through TUI edits, refusal readback, and export parity."""
    store = require_empty_directory(output_root / "secure-store", label="CLI-to-TUI Ledger store")
    passphrase = secrets.token_urlsafe(32)
    cli = InstalledCli(cli_executable, storage_root=store, authority_root=authority_root, passphrase=passphrase)
    create_profile(cli, year=year, stage="CLI-to-TUI profile creation")
    invoice_number = f"LEDGER-CLI-TUI-{year}-001"
    initial_notes = "ledger-cli-initial"
    updated_notes = "ledger-tui-followup"
    invoice = add_invoice(
        cli,
        invoice_number=invoice_number,
        notes=initial_notes,
        year=year,
        stage="CLI-to-TUI invoice capture",
    )
    linked_description = "ledger-linked-refusal-row"
    linked = add_transaction(
        cli,
        description=linked_description,
        amount=INVOICE_TOTAL,
        idempotency_key="ledger-cli-tui-linked",
        year=year,
        stage="CLI-to-TUI linked transaction capture",
    )
    link_transaction(cli, linked.transaction_id, invoice.invoice_id, stage="CLI-to-TUI public link")
    unlinked_description = "ledger-unlinked-detail-row"
    unlinked = add_transaction(
        cli,
        description=unlinked_description,
        amount=INVOICE_TOTAL,
        idempotency_key="ledger-cli-tui-unlinked",
        year=year,
        stage="CLI-to-TUI unlinked transaction capture",
    )
    before_invoice = read_invoice(cli, invoice.invoice_id, stage="CLI-to-TUI invoice before TUI edit")
    before_unlinked = read_transaction(cli, unlinked.transaction_id, stage="CLI-to-TUI transaction before TUI edit")
    edited_description = "ledger-unlinked-detail-updated"
    continuation_child = run_child(
        python_executable=python_executable,
        workspace_root=workspace_root,
        authority_root=authority_root,
        storage_root=store,
        receipt_path=output_root / "tui-continuation.json",
        passphrase=passphrase,
        mode="cli_to_tui",
        year=year,
        invoice_number=invoice_number,
        initial_notes=initial_notes,
        updated_notes=updated_notes,
        transaction_description=unlinked_description,
        updated_description=edited_description,
    )
    after_invoice = read_invoice(cli, invoice.invoice_id, stage="CLI-to-TUI invoice after TUI edit")
    after_unlinked = read_transaction(cli, unlinked.transaction_id, stage="CLI-to-TUI transaction after TUI edit")
    assert_invoice_metadata_continuation(before_invoice, after_invoice, expected_notes=updated_notes)
    assert_unlinked_detail_continuation(before_unlinked, after_unlinked, expected_description=edited_description)

    before_linked_invoice = read_invoice(cli, invoice.invoice_id, stage="linked refusal invoice before")
    before_linked_transaction = read_transaction(cli, linked.transaction_id, stage="linked refusal transaction before")
    assert_linked_identity_refused(cli, linked.transaction_id)
    refusal_child = run_child(
        python_executable=python_executable,
        workspace_root=workspace_root,
        authority_root=authority_root,
        storage_root=store,
        receipt_path=output_root / "linked-refusal-readback.json",
        passphrase=passphrase,
        mode="linked_refusal_readback",
        year=year,
        invoice_number=invoice_number,
        initial_notes=updated_notes,
        transaction_description=linked_description,
    )
    after_linked_invoice = read_invoice(cli, invoice.invoice_id, stage="linked refusal invoice after")
    after_linked_transaction = read_transaction(cli, linked.transaction_id, stage="linked refusal transaction after")
    assert_linked_identity_refusal(
        before_linked_invoice,
        after_linked_invoice,
        before_linked_transaction,
        after_linked_transaction,
    )
    export_rows, export_sha256 = compare_export(
        cli,
        output_path=output_root / "ledger.jsonl",
        stage="CLI-to-TUI export comparison",
    )
    return (
        LedgerContinuationReceipt(
            direction="cli_to_tui",
            status="proven",
            tui_observations=(*continuation_child.observations, *refusal_child.observations),
            cli_command_count=len(cli.commands),
            export_rows=export_rows,
            export_sha256=export_sha256,
        ),
        continuation_child,
    )


def run_tui_to_cli(
    *,
    cli_executable: Path,
    python_executable: Path,
    workspace_root: Path,
    authority_root: Path,
    output_root: Path,
    year: int,
) -> tuple[LedgerContinuationReceipt, LedgerTuiChildReceipt]:
    """Continue installed TUI capture through CLI metadata update and a new TUI readback."""
    store = require_empty_directory(output_root / "secure-store", label="TUI-to-CLI Ledger store")
    passphrase = secrets.token_urlsafe(32)
    invoice_number = f"LEDGER-TUI-CLI-{year}-001"
    initial_notes = "ledger-tui-origin"
    tui_updated_notes = "ledger-tui-captured"
    cli_updated_notes = "ledger-cli-followup"
    capture_child = run_child(
        python_executable=python_executable,
        workspace_root=workspace_root,
        authority_root=authority_root,
        storage_root=store,
        receipt_path=output_root / "tui-capture.json",
        passphrase=passphrase,
        mode="tui_only_capture_update",
        year=year,
        invoice_number=invoice_number,
        initial_notes=initial_notes,
        updated_notes=tui_updated_notes,
    )
    cli = InstalledCli(cli_executable, storage_root=store, authority_root=authority_root, passphrase=passphrase)
    before_invoice = find_invoice_by_number(cli, invoice_number, stage="TUI-to-CLI public invoice discovery")
    if before_invoice.notes != tui_updated_notes:
        raise LedgerInstalledTuiError("TUI-to-CLI capture did not commit its visible invoice metadata update")
    installed_tui_cli_transport_result(
        cli_command(
            cli,
            ("app", "ledger", "invoice", "update", before_invoice.invoice_id, "--notes", cli_updated_notes),
            stage="TUI-to-CLI public invoice update",
            command="ledger.invoice.update",
        ),
        stage="TUI-to-CLI public invoice update",
    )
    after_invoice = read_invoice(cli, before_invoice.invoice_id, stage="TUI-to-CLI invoice after CLI edit")
    assert_invoice_metadata_continuation(before_invoice, after_invoice, expected_notes=cli_updated_notes)
    linked = add_transaction(
        cli,
        description="ledger-tui-cli-linked-export-row",
        amount=INVOICE_TOTAL,
        idempotency_key="ledger-tui-cli-linked",
        year=year,
        stage="TUI-to-CLI linked transaction capture",
    )
    link_transaction(cli, linked.transaction_id, before_invoice.invoice_id, stage="TUI-to-CLI public link")
    export_rows, export_sha256 = compare_export(
        cli,
        output_path=output_root / "ledger.jsonl",
        stage="TUI-to-CLI export comparison",
    )
    reopen_child = run_child(
        python_executable=python_executable,
        workspace_root=workspace_root,
        authority_root=authority_root,
        storage_root=store,
        receipt_path=output_root / "tui-reopen.json",
        passphrase=passphrase,
        mode="tui_to_cli_reopen",
        year=year,
        invoice_number=invoice_number,
        initial_notes=cli_updated_notes,
    )
    if capture_child.product_init_sha256 != reopen_child.product_init_sha256:
        raise LedgerInstalledTuiError("TUI-to-CLI children imported different installed product identities")
    return (
        LedgerContinuationReceipt(
            direction="tui_to_cli",
            status="proven",
            tui_observations=(*capture_child.observations, *reopen_child.observations),
            cli_command_count=len(cli.commands),
            export_rows=export_rows,
            export_sha256=export_sha256,
        ),
        capture_child,
    )
