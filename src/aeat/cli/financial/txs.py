"""`aeat financial txs` command group."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from pathlib import Path

import typer

from aeat.config import load_settings
from aeat.financial.transactions import (
    BusinessClassification,
    TransactionCatalogue,
    TransactionError,
    find_transaction,
    load_transactions,
    save_transactions,
    set_classification,
)

_DEFAULT_CATALOGUE_FILENAME = "transactions.json"

app = typer.Typer(
    name="txs",
    no_args_is_help=True,
    help="Transaction catalogue helpers (#74).",
)


@app.command(name="list", help="List stored transactions, optionally filtering to UNCLASSIFIED records.")
def list_cmd(
    unclassified: bool = typer.Option(
        False,
        "--unclassified",
        help="Show only UNCLASSIFIED transactions.",
    ),
) -> None:
    """List transactions from the configured catalogue file."""
    catalogue = _load_catalogue_or_empty()
    transactions = tuple(
        transaction
        for transaction in catalogue.values()
        if not unclassified or transaction.business_classification is BusinessClassification.UNCLASSIFIED
    )
    if not transactions:
        typer.echo("No transactions found.")
        return
    typer.echo("transaction_id\tdirection\tamount\tcurrency\tclassification\tnarrative")
    for transaction in sorted(
        transactions,
        key=lambda item: ((item.raw.value_date or item.raw.booked_date), item.transaction_id),
    ):
        typer.echo(
            "\t".join(
                [
                    transaction.transaction_id,
                    transaction.direction.value,
                    _format_amount(transaction.raw.amount),
                    transaction.raw.currency,
                    transaction.business_classification.value,
                    transaction.raw.description,
                ]
            )
        )


@app.command(name="show", help="Show one stored transaction as JSON.")
def show_cmd(
    transaction_id: str = typer.Argument(..., help="Stable transaction identifier."),
) -> None:
    """Show one transaction from the configured catalogue file."""
    catalogue = _load_catalogue_required()
    transaction = find_transaction(catalogue, transaction_id)
    if transaction is None:
        typer.echo(f"transaction not found: {transaction_id}", err=True)
        raise typer.Exit(code=2)
    typer.echo(transaction.model_dump_json(indent=2))


@app.command(
    name="classify",
    help="Persist a manual transaction classification in the configured catalogue.",
)
def classify_cmd(
    transaction_id: str = typer.Argument(..., help="Stable transaction identifier."),
    classification: BusinessClassification = typer.Option(
        ...,
        "--as",
        case_sensitive=False,
        help="Classification target: BUSINESS, PERSONAL, MIXED, or UNCLASSIFIED.",
    ),
    pct: str | None = typer.Option(
        None,
        "--pct",
        help="Business-use percentage in the inclusive 0..1 range for MIXED.",
    ),
) -> None:
    """Classify one transaction and write the updated catalogue to disk."""
    path = _catalogue_path()
    catalogue = _load_catalogue_required()
    try:
        business_pct = Decimal(pct) if pct is not None else None
    except InvalidOperation as exc:
        typer.echo(f"invalid --pct value: {pct}", err=True)
        raise typer.Exit(code=2) from exc
    try:
        updated = set_classification(
            catalogue,
            transaction_id,
            classification=classification,
            business_pct=business_pct,
            classified_by="manual",
        )
        save_transactions(updated, path)
    except TransactionError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc
    updated_transaction = find_transaction(updated, transaction_id)
    assert updated_transaction is not None
    typer.echo(updated_transaction.model_dump_json(indent=2))


def _catalogue_path() -> Path:
    """Return the default on-disk catalogue path from settings."""
    return load_settings().aeat_financial_txs_dir.resolve() / _DEFAULT_CATALOGUE_FILENAME


def _load_catalogue_or_empty() -> TransactionCatalogue:
    """Load the configured catalogue, returning an empty one when absent."""
    path = _catalogue_path()
    if path.exists():
        return _load_catalogue_required()
    return TransactionCatalogue()


def _load_catalogue_required() -> TransactionCatalogue:
    """Load the configured catalogue or exit cleanly on failure."""
    path = _catalogue_path()
    try:
        return load_transactions(path)
    except TransactionError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc


def _format_amount(value: Decimal) -> str:
    """Render a ``Decimal`` for CLI tables without exponent notation."""
    if value.is_zero():
        return "0"
    return format(value.normalize(), "f")
