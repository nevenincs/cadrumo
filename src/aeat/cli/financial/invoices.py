"""`aeat financial invoices` / `aeat invoices` command group (#75)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import typer

from ...config import load_settings
from ...financial.invoices import (
    InvoiceCatalogue,
    InvoiceError,
    InvoiceKind,
    LinkInconsistency,
    ReconciliationSuggestion,
    find_invoice,
    find_unmatched,
    link_transaction_bidirectional,
    load_invoices,
    suggest_reconciliations,
    verify_link_consistency,
)
from ...financial.transactions import (
    TransactionCatalogue,
    TransactionError,
    load_transactions,
)

_DEFAULT_INVOICE_FILENAME = "invoices.json"
_DEFAULT_TRANSACTION_FILENAME = "transactions.json"

app = typer.Typer(
    name="invoices",
    no_args_is_help=True,
    help="Invoice catalogue helpers (#75).",
)


@app.command(name="list", help="List stored invoices, optionally filtering by kind.")
def list_cmd(
    kind: InvoiceKind | None = typer.Option(
        None,
        "--kind",
        case_sensitive=False,
        help="Filter by invoice kind: issued or received.",
    ),
) -> None:
    """List invoices from the configured catalogue file."""
    catalogue = _load_invoice_catalogue_or_empty()
    invoices = tuple(invoice for invoice in catalogue.values() if kind is None or invoice.kind is kind)
    if not invoices:
        typer.echo("No invoices found.")
        return
    typer.echo("invoice_id\tkind\tissued_at\tcounterparty\tgrand_total\tcurrency\tpayment_status")
    for invoice in sorted(invoices, key=lambda item: (item.issued_at, item.invoice_id)):
        typer.echo(
            "\t".join(
                [
                    invoice.invoice_id,
                    invoice.kind.value,
                    invoice.issued_at.isoformat(),
                    invoice.counterparty_name,
                    _format_decimal(invoice.grand_total),
                    invoice.currency,
                    invoice.payment_status.value,
                ]
            )
        )


@app.command(name="show", help="Show one stored invoice as JSON.")
def show_cmd(
    invoice_id: str = typer.Argument(..., help="Stable invoice identifier."),
) -> None:
    """Show one invoice from the configured catalogue file."""
    catalogue = _load_invoice_catalogue_required()
    invoice = find_invoice(catalogue, invoice_id)
    if invoice is None:
        typer.echo(f"invoice not found: {invoice_id}", err=True)
        raise typer.Exit(code=2)
    typer.echo(invoice.model_dump_json(indent=2))


@app.command(
    name="link",
    help="Link one transaction to one invoice across both catalogues.",
)
def link_cmd(
    invoice_id: str = typer.Argument(..., help="Stable invoice identifier."),
    transaction_id: str = typer.Argument(..., help="Stable transaction identifier."),
) -> None:
    """Perform a bidirectional link and print the updated invoice."""
    invoices_path = _invoice_catalogue_path()
    transactions_path = _transaction_catalogue_path()
    try:
        updated_invoices, _ = link_transaction_bidirectional(
            invoices_path, transactions_path, invoice_id, transaction_id
        )
    except (InvoiceError, TransactionError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc
    updated_invoice = find_invoice(updated_invoices, invoice_id)
    if updated_invoice is None:
        typer.echo(f"invoice not found after update: {invoice_id}", err=True)
        raise typer.Exit(code=2)
    typer.echo(updated_invoice.model_dump_json(indent=2))


@app.command(
    name="reconcile",
    help="Print auto-suggested transaction/invoice links by amount and counterparty.",
)
def reconcile_cmd(
    apply: bool = typer.Option(
        False,
        "--apply",
        help="Persist each suggestion via link_transaction_bidirectional.",
    ),
) -> None:
    """Print reconciliation suggestions and optionally apply them."""
    invoices_path = _invoice_catalogue_path()
    transactions_path = _transaction_catalogue_path()
    invoices = _load_invoice_catalogue_or_empty()
    transactions = _load_transaction_catalogue_or_empty()
    suggestions = suggest_reconciliations(invoices, transactions)
    if not suggestions:
        typer.echo("No reconciliation suggestions.")
        return
    _print_suggestions(suggestions)
    if not apply:
        return
    applied = 0
    for suggestion in suggestions:
        try:
            link_transaction_bidirectional(
                invoices_path,
                transactions_path,
                suggestion.invoice_id,
                suggestion.transaction_id,
            )
            applied += 1
        except (InvoiceError, TransactionError) as exc:
            typer.echo(
                f"skipped {suggestion.invoice_id} <-> {suggestion.transaction_id}: {exc}",
                err=True,
            )
    typer.echo(f"applied {applied} of {len(suggestions)} suggestions.")


@app.command(
    name="verify",
    help="Report one-sided links between the invoice and transaction catalogues.",
)
def verify_cmd() -> None:
    """Print any inconsistencies and exit non-zero when present."""
    invoices = _load_invoice_catalogue_or_empty()
    transactions = _load_transaction_catalogue_or_empty()
    inconsistencies = verify_link_consistency(invoices, transactions)
    if not inconsistencies:
        typer.echo("Invoice and transaction catalogues are consistent.")
        return
    _print_inconsistencies(inconsistencies)
    raise typer.Exit(code=2)


@app.command(
    name="unmatched",
    help="List invoices that have no linked transactions yet.",
)
def unmatched_cmd(
    kind: InvoiceKind | None = typer.Option(
        None,
        "--kind",
        case_sensitive=False,
        help="Filter by invoice kind: issued or received.",
    ),
) -> None:
    """Print invoices that no transaction cites yet."""
    invoices = _load_invoice_catalogue_or_empty()
    unmatched = find_unmatched(invoices, kind=kind)
    if not unmatched:
        typer.echo("No unmatched invoices.")
        return
    typer.echo("invoice_id\tkind\tissued_at\tcounterparty\tgrand_total\tcurrency")
    for invoice in unmatched:
        typer.echo(
            "\t".join(
                [
                    invoice.invoice_id,
                    invoice.kind.value,
                    invoice.issued_at.isoformat(),
                    invoice.counterparty_name,
                    _format_decimal(invoice.grand_total),
                    invoice.currency,
                ]
            )
        )


def _invoice_catalogue_path() -> Path:
    """Return the default on-disk invoice catalogue path from settings."""
    return load_settings().aeat_invoices_dir.resolve() / _DEFAULT_INVOICE_FILENAME


def _transaction_catalogue_path() -> Path:
    """Return the default on-disk transaction catalogue path from settings."""
    return load_settings().aeat_financial_txs_dir.resolve() / _DEFAULT_TRANSACTION_FILENAME


def _load_invoice_catalogue_required() -> InvoiceCatalogue:
    """Load the configured invoice catalogue or exit cleanly on failure."""
    path = _invoice_catalogue_path()
    try:
        return load_invoices(path)
    except InvoiceError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc


def _load_invoice_catalogue_or_empty() -> InvoiceCatalogue:
    """Load the configured invoice catalogue, returning an empty one when absent."""
    path = _invoice_catalogue_path()
    if path.exists():
        return _load_invoice_catalogue_required()
    return InvoiceCatalogue()


def _load_transaction_catalogue_or_empty() -> TransactionCatalogue:
    """Load the configured transaction catalogue, returning an empty one when absent."""
    path = _transaction_catalogue_path()
    if not path.exists():
        return TransactionCatalogue()
    try:
        return load_transactions(path)
    except TransactionError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc


def _print_suggestions(suggestions: tuple[ReconciliationSuggestion, ...]) -> None:
    typer.echo("invoice_id\ttransaction_id\tamount_match\tcounterparty_match\tscore")
    for suggestion in suggestions:
        typer.echo(
            "\t".join(
                [
                    suggestion.invoice_id,
                    suggestion.transaction_id,
                    "yes" if suggestion.amount_match else "no",
                    "yes" if suggestion.counterparty_match else "no",
                    _format_decimal(suggestion.score),
                ]
            )
        )


def _print_inconsistencies(items: tuple[LinkInconsistency, ...]) -> None:
    typer.echo("invoice_id\ttransaction_id\tdirection")
    for item in items:
        typer.echo("\t".join([item.invoice_id, item.transaction_id, item.direction]))


def _format_decimal(value: object) -> str:
    """Render a ``Decimal`` (or passthrough string) without exponent notation."""
    if isinstance(value, Decimal):
        return "0" if value.is_zero() else format(value.normalize(), "f")
    return str(value)
