"""Installed public invoice and transaction writes for frontend continuations."""

from __future__ import annotations

from decimal import Decimal

from dev.acceptance.installed_cli import InstalledCli

from .frontend_contract import (
    InvoiceObservation,
    TransactionObservation,
)
from .installed_tui_cli_observations import _invoice_observation, _read_transaction
from .installed_tui_cli_transport import _cli_command, _result, _text
from .installed_tui_contracts import (
    _COUNTERPARTY_NIF,
    _INVOICE_BASE,
    _INVOICE_IVA,
    _LINKED_IDENTITY_REFUSAL,
    LedgerInstalledTuiError,
)


def _add_invoice(
    cli: InstalledCli,
    *,
    invoice_number: str,
    notes: str,
    year: int,
    stage: str,
) -> InvoiceObservation:
    """Capture one small issued invoice through the installed public CLI."""
    document = _cli_command(
        cli,
        (
            "app",
            "ledger",
            "invoice",
            "add",
            "--kind",
            "issued",
            "--counterparty-name",
            "Ledger acceptance customer",
            "--counterparty-nif",
            _COUNTERPARTY_NIF,
            "--invoice-number",
            invoice_number,
            "--invoice-date",
            f"{year}-03-15",
            "--taxable-base",
            format(_INVOICE_BASE, "f"),
            "--iva-rate",
            "21",
            "--country-code",
            "ES",
            "--iva-category",
            "domestic_general",
            "--notes",
            notes,
        ),
        stage=stage,
        command="ledger.invoice.add",
    )
    return _invoice_observation(_result(document, stage=stage), stage=stage)


def _add_transaction(
    cli: InstalledCli,
    *,
    description: str,
    amount: Decimal,
    idempotency_key: str,
    year: int,
    stage: str,
) -> TransactionObservation:
    """Capture a public unlinked transaction with explicit IVA facts."""
    document = _cli_command(
        cli,
        (
            "app",
            "ledger",
            "add",
            "--date",
            f"{year}-03-18",
            "--amount",
            format(amount, "f"),
            "--direction",
            "INCOMING",
            "--description",
            description,
            "--classification",
            "BUSINESS",
            "--taxable-base",
            format(_INVOICE_BASE, "f"),
            "--iva-rate",
            "0.21",
            "--iva-amount",
            format(_INVOICE_IVA, "f"),
            "--iva-category",
            "domestic_general",
            "--source-jurisdiction",
            "ES",
            "--idempotency-key",
            idempotency_key,
        ),
        stage=stage,
        command="ledger.add",
    )
    result = _result(document, stage=stage)
    return _read_transaction(cli, _text(result.get("transaction_id"), stage=stage), stage=stage)


def _link_transaction(cli: InstalledCli, transaction_id: str, invoice_id: str, *, stage: str) -> None:
    """Link through the public command and require the normal successful envelope."""
    _result(
        _cli_command(
            cli,
            ("app", "ledger", "link", transaction_id, "--invoice-id", invoice_id),
            stage=stage,
            command="ledger.link",
        ),
        stage=stage,
    )


def _assert_linked_identity_refused(cli: InstalledCli, transaction_id: str) -> None:
    """Exercise the public guarded rejection before a TUI readback verifies stability."""
    document = _cli_command(
        cli,
        ("app", "ledger", "update", transaction_id, "--description", "ledger-linked-refusal-attempt"),
        stage="linked identity refusal",
        command="ledger.update",
        allow_error=True,
    )
    error = document.get("error")
    if (
        not cli.commands
        or cli.commands[-1].returncode == 0
        or document.get("status") != "error"
        or not isinstance(error, dict)
        or error.get("code") != "ERROR_TRANSACTION_VALIDATION"
        or error.get("message") != _LINKED_IDENTITY_REFUSAL
    ):
        raise LedgerInstalledTuiError("public linked identity edit did not refuse")
