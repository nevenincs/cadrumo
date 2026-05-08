"""Implement the ``aeat financial invoices`` Typer group.

Surfaces the :mod:`aeat.application.invoices` and
:mod:`aeat.domain.invoices` services as CLI verbs (``list``, ``show``,
``link``, ``reconcile``, ``verify``, ``unmatched``) so operators can
inspect the invoice catalogue, link invoices to transactions
bidirectionally, and reconcile unmatched records.

Cross-process movement of the invoice catalogue (backup, restore,
migration to another machine) is served by ``aeat archive export`` and
``aeat archive import``: those verbs walk every registered namespace
including ``aeat.domain.invoices`` and round-trip a portable JSON
bundle against the encrypted SQL backend.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import typer

from ....application.invoices import (
    LinkInconsistency,
    ReconciliationSuggestion,
    find_invoice,
    find_unmatched,
    link_transaction,
    link_transaction_bidirectional,
    suggest_reconciliations,
    verify_link_consistency,
)
from ....domain.invoices import (
    InvoiceCatalogue,
    InvoiceCatalogueRepository,
    InvoiceError,
    InvoiceKind,
)
from ....domain.transactions import (
    TransactionCatalogue,
    TransactionError,
    link_invoice,
)
from .._i18n import tr
from ._catalogue import catalogue_repository as _transaction_catalogue_repository

app = typer.Typer(
    name="invoices",
    no_args_is_help=True,
    help=tr("cli.financial.invoices.app_help"),
)


@app.command(name="list", help=tr("cli.financial.invoices.list_help"))
def list_cmd(
    kind: InvoiceKind | None = typer.Option(
        None,
        "--kind",
        case_sensitive=False,
        help=tr("cli.financial.invoices.kind_help"),
    ),
) -> None:
    """List invoices from the configured catalogue file.

    Loads the catalogue via
    :class:`aeat.domain.invoices.InvoiceCatalogueRepository` and prints
    one tab-separated row per invoice, optionally filtered by
    :class:`aeat.domain.invoices.InvoiceKind`.

    Args:
        kind: Optional filter restricting output to issued or received
            invoices.
    """
    catalogue = _load_invoice_catalogue_or_empty()
    invoices = tuple(invoice for invoice in catalogue.values() if kind is None or invoice.kind is kind)
    if not invoices:
        typer.echo(tr("cli.financial.invoices.no_invoices"))
        return
    typer.echo(tr("cli.financial.invoices.headers.list"))
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


@app.command(name="show", help=tr("cli.financial.invoices.show_help"))
def show_cmd(
    invoice_id: str = typer.Argument(..., help=tr("cli.financial.invoices.id_help")),
) -> None:
    """Show one invoice from the configured catalogue file.

    Args:
        invoice_id: Stable invoice identifier to look up via
            :func:`aeat.application.invoices.find_invoice`.

    Raises:
        :exc:`typer.Exit`: With exit code ``2`` when no invoice matches
            ``invoice_id``.
    """
    catalogue = _load_invoice_catalogue_required()
    invoice = find_invoice(catalogue, invoice_id)
    if invoice is None:
        typer.echo(
            tr("cli.financial.invoices.errors.not_found", id=invoice_id),
            err=True,
        )
        raise typer.Exit(code=2)
    typer.echo(invoice.model_dump_json(indent=2))


@app.command(
    name="link",
    help=tr("cli.financial.invoices.link_help"),
)
def link_cmd(
    invoice_id: str = typer.Argument(..., help=tr("cli.financial.invoices.link_invoice_id_help")),
    transaction_id: str = typer.Argument(..., help=tr("cli.financial.invoices.link_transaction_id_help")),
) -> None:
    """Perform a bidirectional link and print the updated invoice.

    Delegates to
    :func:`aeat.application.invoices.link_transaction_bidirectional`
    so the link is recorded in both the invoice and transaction
    catalogues atomically.

    Args:
        invoice_id: Invoice that should reference ``transaction_id``.
        transaction_id: Transaction that should reference ``invoice_id``.

    Raises:
        :exc:`typer.Exit`: With exit code ``2`` when either catalogue
            rejects the link or when the updated invoice cannot be
            located after the save.
    """
    try:
        updated_invoices, _ = link_transaction_bidirectional(Path(), Path(), invoice_id, transaction_id)
    except (InvoiceError, TransactionError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc
    updated_invoice = find_invoice(updated_invoices, invoice_id)
    if updated_invoice is None:
        typer.echo(
            tr("cli.financial.invoices.errors.not_found_after_update", id=invoice_id),
            err=True,
        )
        raise typer.Exit(code=2)
    typer.echo(updated_invoice.model_dump_json(indent=2))


@app.command(
    name="reconcile",
    help=tr("cli.financial.invoices.reconcile_help"),
)
def reconcile_cmd(
    apply: bool = typer.Option(
        False,
        "--apply",
        help=tr("cli.financial.invoices.apply_help"),
    ),
) -> None:
    """Print reconciliation suggestions and optionally apply them.

    Runs :func:`aeat.application.invoices.suggest_reconciliations` over
    the invoice and transaction catalogues. When ``--apply`` is set,
    every accepted suggestion is folded into in-memory copies of both
    catalogues; the two catalogues are then saved once at the end via
    their respective repositories. This mirrors the canonical atomic-save
    pattern used elsewhere in the repository (vs. one round-trip per
    suggestion).

    Args:
        apply: When ``True``, persist each accepted suggestion via
            :func:`aeat.application.invoices.link_transaction` and
            :func:`aeat.domain.transactions.link_invoice` before saving.

    Raises:
        :exc:`typer.Exit`: With exit code ``2`` when the final
            atomic save fails.
    """
    invoices = _load_invoice_catalogue_or_empty()
    transactions = _load_transaction_catalogue_or_empty()
    suggestions = suggest_reconciliations(invoices, transactions)
    if not suggestions:
        typer.echo(tr("cli.financial.invoices.no_suggestions"))
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
                tr(
                    "cli.financial.invoices.errors.skipped_suggestion",
                    invoice=suggestion.invoice_id,
                    transaction=suggestion.transaction_id,
                    exc=str(exc),
                ),
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
            typer.echo(
                tr("cli.financial.invoices.errors.final_save_failed", exc=str(exc)),
                err=True,
            )
            raise typer.Exit(code=2) from exc
    typer.echo(tr("cli.financial.invoices.labels.applied", applied=applied, total=len(suggestions)))


@app.command(
    name="verify",
    help=tr("cli.financial.invoices.verify_help"),
)
def verify_cmd() -> None:
    """Print any inconsistencies and exit non-zero when present.

    Runs :func:`aeat.application.invoices.verify_link_consistency`
    against both catalogues and exits with code ``2`` when any
    one-sided link is detected.

    Raises:
        :exc:`typer.Exit`: With exit code ``2`` when inconsistencies
            are reported.
    """
    invoices = _load_invoice_catalogue_or_empty()
    transactions = _load_transaction_catalogue_or_empty()
    inconsistencies = verify_link_consistency(invoices, transactions)
    if not inconsistencies:
        typer.echo(tr("cli.financial.invoices.consistent"))
        return
    _print_inconsistencies(inconsistencies)
    raise typer.Exit(code=2)


@app.command(
    name="unmatched",
    help=tr("cli.financial.invoices.unmatched_help"),
)
def unmatched_cmd(
    kind: InvoiceKind | None = typer.Option(
        None,
        "--kind",
        case_sensitive=False,
        help=tr("cli.financial.invoices.kind_help"),
    ),
) -> None:
    """Print invoices that no transaction cites yet.

    Args:
        kind: Optional :class:`aeat.domain.invoices.InvoiceKind` filter
            restricting the unmatched listing.
    """
    invoices = _load_invoice_catalogue_or_empty()
    unmatched = find_unmatched(invoices, kind=kind)
    if not unmatched:
        typer.echo(tr("cli.financial.invoices.no_unmatched"))
        return
    typer.echo(tr("cli.financial.invoices.headers.unmatched"))
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


def _invoice_catalogue_repository() -> InvoiceCatalogueRepository:
    """Return the invoice catalogue repository bound to the secure backend."""
    return InvoiceCatalogueRepository()


def _load_invoice_catalogue_required() -> InvoiceCatalogue:
    """Load the configured invoice catalogue or exit cleanly on failure.

    Raises:
        :exc:`typer.Exit`: With exit code ``2`` when the envelope file
            is missing or when
            :exc:`aeat.domain.invoices.InvoiceError` surfaces during load.
    """
    repository = _invoice_catalogue_repository()
    if not repository.exists():
        typer.echo(
            tr("cli.financial_invoices.errors.catalogue_not_found", path="secure database"),
            err=True,
        )
        raise typer.Exit(code=2)
    try:
        return repository.load()
    except InvoiceError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc


def _load_invoice_catalogue_or_empty() -> InvoiceCatalogue:
    """Load the configured invoice catalogue, returning an empty one when absent.

    Raises:
        :exc:`typer.Exit`: With exit code ``2`` when
            :exc:`aeat.domain.invoices.InvoiceError` surfaces during load.
    """
    repository = _invoice_catalogue_repository()
    try:
        return repository.load()
    except InvoiceError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc


def _load_transaction_catalogue_or_empty() -> TransactionCatalogue:
    """Load the configured transaction catalogue, returning an empty one when absent.

    Raises:
        :exc:`typer.Exit`: With exit code ``2`` when
            :exc:`aeat.domain.transactions.TransactionError` surfaces during load.
    """
    from ....domain.transactions import TransactionCatalogueRepository

    repository = TransactionCatalogueRepository()
    try:
        return repository.load()
    except TransactionError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc


def _print_suggestions(suggestions: tuple[ReconciliationSuggestion, ...]) -> None:
    """Print one tab-separated row per :class:`~aeat.application.invoices.ReconciliationSuggestion`."""
    typer.echo(tr("cli.financial_invoices.headers.suggestions"))
    for suggestion in suggestions:
        typer.echo(
            "\t".join(
                [
                    suggestion.invoice_id,
                    suggestion.transaction_id,
                    tr("cli.financial_invoices.labels.yes")
                    if suggestion.amount_match
                    else tr("cli.financial_invoices.labels.no"),
                    tr("cli.financial_invoices.labels.yes")
                    if suggestion.counterparty_match
                    else tr("cli.financial_invoices.labels.no"),
                    _format_decimal(suggestion.score),
                ]
            )
        )


def _print_inconsistencies(items: tuple[LinkInconsistency, ...]) -> None:
    """Print one tab-separated row per :class:`~aeat.application.invoices.LinkInconsistency`."""
    typer.echo(tr("cli.financial_invoices.headers.inconsistencies"))
    for item in items:
        typer.echo("\t".join([item.invoice_id, item.transaction_id, item.direction]))


def _format_decimal(value: object) -> str:
    """Render a :class:`decimal.Decimal` (or passthrough string) without exponent notation."""
    if isinstance(value, Decimal):
        return "0" if value.is_zero() else format(value.normalize(), "f")
    return str(value)
