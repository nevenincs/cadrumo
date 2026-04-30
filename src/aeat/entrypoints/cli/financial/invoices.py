"""`aeat financial invoices` / `aeat invoices` command group (#75)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import typer

from ....core.config import load_settings
from ....domain.financial.invoices import (
    InvoiceCatalogue,
    InvoiceCatalogueRepository,
    InvoiceError,
    InvoiceKind,
    LinkInconsistency,
    ReconciliationSuggestion,
    find_invoice,
    find_unmatched,
    link_transaction,
    link_transaction_bidirectional,
    suggest_reconciliations,
    verify_link_consistency,
)
from ....domain.financial.transactions import (
    TransactionCatalogue,
    TransactionError,
    link_invoice,
)
from ._catalogue import catalogue_dir as _transaction_catalogue_dir
from ._catalogue import catalogue_repository as _transaction_catalogue_repository

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
    invoices_dir = _invoice_catalogue_dir()
    transactions_dir = _transaction_catalogue_dir()
    try:
        updated_invoices, _ = link_transaction_bidirectional(invoices_dir, transactions_dir, invoice_id, transaction_id)
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
    """Print reconciliation suggestions and optionally apply them.

    When ``--apply`` is set, every accepted suggestion is folded into
    in-memory copies of both catalogues; the two catalogues are then
    saved once at the end via their respective repositories. This
    mirrors the canonical atomic-save pattern used elsewhere in the
    repository (vs. one round-trip per suggestion).
    """
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
    pending_invoices = invoices
    pending_transactions = transactions
    dirty = False
    for suggestion in suggestions:
        try:
            updated_invoices = link_transaction(
                pending_invoices,
                suggestion.invoice_id,
                suggestion.transaction_id,
            )
            updated_transactions = link_invoice(
                pending_transactions,
                suggestion.transaction_id,
                suggestion.invoice_id,
            )
        except (InvoiceError, TransactionError) as exc:
            typer.echo(
                f"skipped {suggestion.invoice_id} <-> {suggestion.transaction_id}: {exc}",
                err=True,
            )
            continue
        pending_invoices = updated_invoices
        pending_transactions = updated_transactions
        dirty = True
        applied += 1

    if dirty:
        try:
            _invoice_catalogue_repository().save(pending_invoices)
            _transaction_catalogue_repository().save(pending_transactions)
        except (InvoiceError, TransactionError) as exc:
            typer.echo(f"final save failed; no changes persisted: {exc}", err=True)
            raise typer.Exit(code=2) from exc
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


def _invoice_catalogue_dir() -> Path:
    """Return the configured invoice catalogue store directory."""
    return load_settings().aeat_invoices_dir.resolve()


def _invoice_catalogue_repository() -> InvoiceCatalogueRepository:
    """Return an :class:`InvoiceCatalogueRepository` bound to the configured store dir."""
    return InvoiceCatalogueRepository(store_dir=_invoice_catalogue_dir())


def _load_invoice_catalogue_required() -> InvoiceCatalogue:
    """Load the configured invoice catalogue or exit cleanly on failure."""
    repository = _invoice_catalogue_repository()
    if not repository.envelope_path.exists():
        typer.echo(f"invoice catalogue not found at {repository.envelope_path}", err=True)
        raise typer.Exit(code=2)
    try:
        return repository.load()
    except InvoiceError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc


def _load_invoice_catalogue_or_empty() -> InvoiceCatalogue:
    """Load the configured invoice catalogue, returning an empty one when absent."""
    repository = _invoice_catalogue_repository()
    try:
        return repository.load()
    except InvoiceError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc


def _load_transaction_catalogue_or_empty() -> TransactionCatalogue:
    """Load the configured transaction catalogue, returning an empty one when absent."""
    from ....domain.financial.transactions import TransactionCatalogueRepository

    repository = TransactionCatalogueRepository(store_dir=_transaction_catalogue_dir())
    try:
        return repository.load()
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
