"""`aeat financial txs` command group."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

import typer

from ...financial.categories import SpendingCategory
from ...financial.transactions import (
    BusinessClassification,
    TransactionError,
    find_transaction,
    save_transactions,
    set_classification,
)
from ._catalogue import catalogue_path, load_catalogue_or_empty, load_catalogue_required

app = typer.Typer(
    name="txs",
    no_args_is_help=True,
    help="Transaction catalogue helpers (#74).",
)


@app.command(name="list", help="List stored transactions, optionally filtering by classification state.")
def list_cmd(
    state: BusinessClassification | None = typer.Option(
        None,
        "--state",
        case_sensitive=False,
        help=(
            "Filter to one BusinessClassification value: BUSINESS, PERSONAL, MIXED, "
            "NOT_YET_PROCESSED, PROCESSED_UNCLASSIFIED, SKIPPED_BY_RULE, or FAILED_VALIDATION."
        ),
    ),
    unclassified: bool = typer.Option(
        False,
        "--unclassified",
        help="Deprecated; alias for --state PROCESSED_UNCLASSIFIED.",
        hidden=True,
    ),
) -> None:
    """List transactions from the configured catalogue file."""
    if state is not None and unclassified:
        typer.echo("--state and --unclassified are mutually exclusive.", err=True)
        raise typer.Exit(code=2)
    effective_state: BusinessClassification | None = state
    if effective_state is None and unclassified:
        effective_state = BusinessClassification.PROCESSED_UNCLASSIFIED
    catalogue = load_catalogue_or_empty()
    transactions = tuple(
        transaction
        for transaction in catalogue.values()
        if effective_state is None or transaction.business_classification is effective_state
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
    catalogue = load_catalogue_required()
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
        help=(
            "Classification target: BUSINESS, PERSONAL, MIXED, "
            "NOT_YET_PROCESSED, PROCESSED_UNCLASSIFIED, SKIPPED_BY_RULE, or FAILED_VALIDATION."
        ),
    ),
    pct: str | None = typer.Option(
        None,
        "--pct",
        help="Business-use percentage in the inclusive 0..1 range for MIXED.",
    ),
    category: SpendingCategory | None = typer.Option(
        None,
        "--category",
        case_sensitive=False,
        help="Specific spending category from the AEAT 39-category catalogue.",
    ),
    reason: str = typer.Option(
        "",
        "--reason",
        help="Optional free-text override justification; recorded in the history chain.",
    ),
) -> None:
    """Classify one transaction and write the updated catalogue to disk."""
    path = catalogue_path()
    catalogue = load_catalogue_required()
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
            category_id=category.value if category else None,
            notes=reason,
            classified_by="manual",
            reason=reason,
        )
        save_transactions(updated, path)
    except TransactionError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc
    updated_transaction = find_transaction(updated, transaction_id)
    assert updated_transaction is not None
    typer.echo(updated_transaction.model_dump_json(indent=2))


def _format_amount(value: Decimal) -> str:
    """Render a ``Decimal`` for CLI tables without exponent notation."""
    if value.is_zero():
        return "0"
    return format(value.normalize(), "f")
