"""Canonical invoice, transaction and lineage observations through installed public commands."""

from __future__ import annotations

from typing import Any, cast

from dev.acceptance.installed_cli import InstalledCli

from .frontend_contract import (
    InvoiceObservation,
    TransactionObservation,
)
from .installed_tui_cli_transport import _cli_command, _decimal, _result, _text
from .installed_tui_contracts import (
    _INVOICE_BASE,
    _INVOICE_IVA,
    _INVOICE_TOTAL,
    _TUI_IMPORTED_TRANSACTION_AMOUNT,
    _TUI_IMPORTED_TRANSACTION_DIRECTION,
    LedgerInstalledTuiError,
)


def _transaction_predecessors(lineage: object, *, stage: str) -> list[str]:
    """Transaction predecessors."""
    if not isinstance(lineage, list):
        raise LedgerInstalledTuiError(f"{stage} exposed invalid transaction edit lineage")
    predecessors: list[str] = []
    for entry in lineage:
        if not isinstance(entry, dict):
            raise LedgerInstalledTuiError(f"{stage} exposed invalid transaction edit lineage")
        predecessor = entry.get("previous_transaction_id")
        if not isinstance(predecessor, str) or not predecessor:
            raise LedgerInstalledTuiError(f"{stage} exposed invalid transaction predecessor identity")
        predecessors.append(predecessor)
    return predecessors


def _assert_tui_only_invoice_readback(
    invoice: InvoiceObservation, invoice_payload: dict[str, Any], invoice_number: str, updated_notes: str
) -> None:
    """Tui only invoice readback."""
    if (
        _text(invoice_payload.get("invoice_id"), stage="TUI-only CLI oracle invoice readback") != invoice.invoice_id
        or invoice_payload.get("invoice_number") != invoice_number
        or invoice_payload.get("notes") != updated_notes
    ):
        raise LedgerInstalledTuiError("TUI-only CLI oracle did not preserve canonical invoice identity or metadata")
    if (
        _decimal(invoice_payload.get("base_total"), stage="TUI-only CLI oracle invoice readback"),
        _decimal(invoice_payload.get("iva_total"), stage="TUI-only CLI oracle invoice readback"),
        _decimal(invoice_payload.get("grand_total"), stage="TUI-only CLI oracle invoice readback"),
    ) != (_INVOICE_BASE, _INVOICE_IVA, _INVOICE_TOTAL):
        raise LedgerInstalledTuiError("TUI-only CLI oracle did not preserve canonical invoice totals")
    if invoice_payload.get("linked_transaction_ids") != []:
        raise LedgerInstalledTuiError("TUI-only CLI oracle invoice unexpectedly acquired a transaction link")


def _tui_only_transaction_identity(cli: InstalledCli, updated_description: str) -> str:
    """Tui only transaction identity."""
    listing = _result(
        _cli_command(
            cli,
            ("app", "ledger", "list"),
            stage="TUI-only CLI oracle transaction discovery",
            command="ledger.list",
        ),
        stage="TUI-only CLI oracle transaction discovery",
    )
    rows = listing.get("rows")
    if not isinstance(rows, list):
        raise LedgerInstalledTuiError("TUI-only CLI oracle did not expose public transaction rows")
    matches = [row for row in rows if isinstance(row, dict) and row.get("description") == updated_description]
    if len(matches) != 1:
        raise LedgerInstalledTuiError("TUI-only CLI oracle did not expose exactly one imported transaction")
    transaction_row = cast("dict[str, Any]", matches[0])
    transaction_id = _text(transaction_row.get("transaction_id"), stage="TUI-only CLI oracle transaction readback")
    if (
        _decimal(transaction_row.get("amount"), stage="TUI-only CLI oracle transaction readback")
        != _TUI_IMPORTED_TRANSACTION_AMOUNT
        or transaction_row.get("direction") != _TUI_IMPORTED_TRANSACTION_DIRECTION
        or transaction_row.get("invoice_id") is not None
    ):
        raise LedgerInstalledTuiError(
            "TUI-only CLI oracle did not preserve imported transaction value, direction, or link"
        )
    return transaction_id


def _assert_tui_only_transaction_tracking(
    tracking_payload: dict[str, Any], transaction_id: str, updated_description: str
) -> None:
    """Tui only transaction tracking."""
    tracked = _transaction_observation(tracking_payload, stage="TUI-only CLI oracle transaction lineage")
    transaction = tracking_payload.get("transaction")
    if (
        not isinstance(transaction, dict)
        or tracked.transaction_id != transaction_id
        or tracked.description != updated_description
        or tracked.amount != _TUI_IMPORTED_TRANSACTION_AMOUNT
        or tracked.invoice_id is not None
        or transaction.get("direction") != _TUI_IMPORTED_TRANSACTION_DIRECTION
    ):
        raise LedgerInstalledTuiError("TUI-only CLI oracle did not preserve tracked transaction state")
    if not tracked.predecessor_ids or transaction_id in tracked.predecessor_ids:
        raise LedgerInstalledTuiError("TUI-only CLI oracle did not expose supported edit lineage")


def _invoice_observation(payload: dict[str, Any], *, stage: str) -> InvoiceObservation:
    """Project a public invoice envelope into the shared continuation contract."""
    links = payload.get("linked_transaction_ids")
    if not isinstance(links, list) or not all(isinstance(link, str) and link for link in links):
        raise LedgerInstalledTuiError(f"{stage} exposed invalid reciprocal invoice links")
    notes = payload.get("notes")
    if not isinstance(notes, str):
        raise LedgerInstalledTuiError(f"{stage} exposed invalid invoice notes")
    return InvoiceObservation(
        bucket_id=_text(payload.get("bucket_id"), stage=stage),
        invoice_id=_text(payload.get("invoice_id"), stage=stage),
        notes=notes,
        grand_total=_decimal(payload.get("grand_total"), stage=stage),
        linked_transaction_ids=tuple(sorted(links)),
    )


def _transaction_observation(payload: dict[str, Any], *, stage: str) -> TransactionObservation:
    """Project a public tracking envelope into the shared continuation contract."""
    transaction = payload.get("transaction")
    tracking = payload.get("tracking")
    if not isinstance(transaction, dict) or not isinstance(tracking, dict):
        raise LedgerInstalledTuiError(f"{stage} did not expose a public transaction tracking result")
    lineage = tracking.get("edit_lineage")
    predecessors = _transaction_predecessors(lineage, stage=stage)
    invoice_id = transaction.get("invoice_id")
    if invoice_id is not None and (not isinstance(invoice_id, str) or not invoice_id):
        raise LedgerInstalledTuiError(f"{stage} exposed invalid transaction invoice association")
    return TransactionObservation(
        bucket_id=_text(payload.get("bucket_id"), stage=stage),
        transaction_id=_text(transaction.get("transaction_id"), stage=stage),
        description=_text(transaction.get("description"), stage=stage),
        amount=_decimal(transaction.get("amount"), stage=stage),
        invoice_id=invoice_id,
        predecessor_ids=tuple(predecessors),
    )


def _read_invoice(cli: InstalledCli, invoice_id: str, *, stage: str) -> InvoiceObservation:
    """Read one canonical invoice through the installed public CLI."""
    return _invoice_observation(
        _result(
            _cli_command(
                cli,
                ("app", "ledger", "invoice", "view", invoice_id),
                stage=stage,
                command="ledger.invoice.view",
            ),
            stage=stage,
        ),
        stage=stage,
    )


def _read_transaction(cli: InstalledCli, transaction_id: str, *, stage: str) -> TransactionObservation:
    """Read one transaction and its public edit lineage through ``ledger track``."""
    return _transaction_observation(
        _result(
            _cli_command(
                cli,
                ("app", "ledger", "track", transaction_id),
                stage=stage,
                command="ledger.track",
            ),
            stage=stage,
        ),
        stage=stage,
    )


def _find_invoice_by_number(cli: InstalledCli, invoice_number: str, *, stage: str) -> InvoiceObservation:
    """Resolve a public invoice identity only from the canonical list surface."""
    listing = _result(
        _cli_command(
            cli,
            ("app", "ledger", "invoice", "list"),
            stage=stage,
            command="ledger.invoice.list",
        ),
        stage=stage,
    )
    rows = listing.get("rows")
    if not isinstance(rows, list):
        raise LedgerInstalledTuiError(f"{stage} did not expose public invoice rows")
    matches = [row for row in rows if isinstance(row, dict) and row.get("invoice_number") == invoice_number]
    if len(matches) != 1:
        raise LedgerInstalledTuiError(f"{stage} did not expose exactly one matching public invoice")
    return _invoice_observation(cast("dict[str, Any]", matches[0]), stage=stage)


def _assert_tui_only_cli_oracle(
    cli: InstalledCli,
    *,
    invoice_number: str,
    updated_notes: str,
    updated_description: str,
) -> tuple[str, ...]:
    """Read back a TUI-only write through canonical installed JSON commands.

    The child already proves the public import picker, preview, and confirmation.
    The JSON CLI intentionally has no source filename or source-row projection
    for ``ledger track``, so this oracle confines itself to the values and
    lineage the typed JSON surfaces actually expose.
    """
    invoice = _find_invoice_by_number(
        cli,
        invoice_number,
        stage="TUI-only CLI oracle invoice discovery",
    )
    invoice_payload = _result(
        _cli_command(
            cli,
            ("app", "ledger", "invoice", "view", invoice.invoice_id),
            stage="TUI-only CLI oracle invoice readback",
            command="ledger.invoice.view",
        ),
        stage="TUI-only CLI oracle invoice readback",
    )
    _assert_tui_only_invoice_readback(invoice, invoice_payload, invoice_number, updated_notes)

    transaction_id = _tui_only_transaction_identity(cli, updated_description)

    tracking_payload = _result(
        _cli_command(
            cli,
            ("app", "ledger", "track", transaction_id),
            stage="TUI-only CLI oracle transaction lineage",
            command="ledger.track",
        ),
        stage="TUI-only CLI oracle transaction lineage",
    )
    _assert_tui_only_transaction_tracking(tracking_payload, transaction_id, updated_description)
    return (
        "cli_invoice_identity_and_totals",
        "cli_invoice_absent_link",
        "cli_imported_transaction_value_and_direction",
        "cli_imported_transaction_absent_link",
        "cli_post_edit_lineage",
    )
