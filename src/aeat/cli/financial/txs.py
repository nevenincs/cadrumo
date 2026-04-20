"""`aeat financial txs` command group."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

import typer

from ...financial._decimal import canonical_decimal
from ...financial.categories import SpendingCategory
from ...financial.transactions import (
    BusinessClassification,
    LLMClassifierError,
    Transaction,
    TransactionCatalogue,
    TransactionError,
    find_transaction,
    is_classified,
    resolve_classifier,
    save_transactions,
    set_classification,
)
from ._catalogue import catalogue_path, load_catalogue_or_empty, load_catalogue_required

_CONFIDENCE_MIN = Decimal("0")
_CONFIDENCE_MAX = Decimal("1")

app = typer.Typer(
    name="txs",
    no_args_is_help=True,
    help="Transaction catalogue helpers (#74).",
)


@app.command(
    name="list",
    help="List stored transactions, optionally filtering by classification state or decision confidence.",
)
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
    confidence_below: str | None = typer.Option(
        None,
        "--confidence-below",
        help="Show only transactions whose classification confidence is strictly below this threshold (0..1).",
    ),
) -> None:
    """List transactions from the configured catalogue file."""
    if state is not None and unclassified:
        typer.echo("--state and --unclassified are mutually exclusive.", err=True)
        raise typer.Exit(code=2)
    effective_state: BusinessClassification | None = state
    if effective_state is None and unclassified:
        effective_state = BusinessClassification.PROCESSED_UNCLASSIFIED
    threshold = _parse_confidence_threshold(confidence_below)
    catalogue = load_catalogue_or_empty()
    transactions = tuple(
        transaction
        for transaction in catalogue.values()
        if _matches_filters(transaction, state=effective_state, threshold=threshold)
    )
    if not transactions:
        if threshold is not None and len(catalogue) > 0:
            typer.echo(
                "No transactions found below that confidence threshold. "
                "Note: manual classifications default to confidence 1.0, so --confidence-below "
                "only surfaces results when a rule engine or LLM classifier has assigned a "
                "lower score (not yet implemented for transactions)."
            )
        else:
            typer.echo("No transactions found.")
        return
    typer.echo("transaction_id\tdirection\tamount\tcurrency\tclassification\tconfidence\tnarrative")
    for transaction in sorted(
        transactions,
        key=lambda item: ((item.raw.value_date or item.raw.booked_date), item.transaction_id),
    ):
        typer.echo(
            "\t".join(
                [
                    transaction.transaction_id,
                    transaction.direction.value,
                    canonical_decimal(transaction.raw.amount),
                    transaction.raw.currency,
                    transaction.business_classification.value,
                    _format_optional_decimal(transaction.classification_confidence),
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
    confidence: str | None = typer.Option(
        None,
        "--confidence",
        help=(
            "Advanced: record a non-default decision confidence (0..1). "
            "Manual classifications default to 1.0; override only when recording the score "
            "of a rule engine or LLM output rather than your own judgement."
        ),
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
    resolved_confidence = _parse_confidence_option(confidence)
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
            confidence=resolved_confidence,
        )
        save_transactions(updated, path)
    except TransactionError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc
    updated_transaction = find_transaction(updated, transaction_id)
    assert updated_transaction is not None
    typer.echo(updated_transaction.model_dump_json(indent=2))


@app.command(
    name="classify-llm",
    help=(
        "Classify transactions via an LLM (claude / gemini / codex). "
        "Pass a transaction ID for one record, or --all to process every "
        "NOT_YET_PROCESSED transaction. Results feed the same history "
        "chain as manual or rule-based decisions."
    ),
)
def classify_llm_cmd(
    transaction_id: str | None = typer.Argument(None, help="Stable transaction identifier (omit with --all)."),
    provider: str = typer.Option(
        ...,
        "--provider",
        case_sensitive=False,
        help="LLM provider: claude, gemini, or codex (must be on PATH).",
    ),
    model: str | None = typer.Option(
        None,
        "--model",
        help="Optional model override passed through to the CLI.",
    ),
    all_pending: bool = typer.Option(
        False,
        "--all",
        help="Classify every NOT_YET_PROCESSED transaction in the catalogue.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Run the classifier and print the results without saving.",
    ),
    max_total_seconds: float | None = typer.Option(
        None,
        "--max-total-seconds",
        help=(
            "Stop the --all loop after this many wall-clock seconds elapsed. "
            "Classifications already persisted before the budget is exhausted are kept. "
            "Omit for no ceiling."
        ),
    ),
) -> None:
    """Classify one or many transactions through an LLM CLI.

    Persists each successful classification immediately so a Ctrl+C or
    a later subprocess failure does not lose the classifications Kent
    has already paid API tokens for.
    """
    import time

    if all_pending and transaction_id is not None:
        typer.echo("--all is mutually exclusive with a transaction-id argument.", err=True)
        raise typer.Exit(code=2)
    if not all_pending and transaction_id is None:
        typer.echo("Pass a transaction-id argument or use --all.", err=True)
        raise typer.Exit(code=2)
    if max_total_seconds is not None and max_total_seconds <= 0:
        typer.echo("--max-total-seconds must be strictly positive.", err=True)
        raise typer.Exit(code=2)
    try:
        classifier = resolve_classifier(provider, model=model)
    except LLMClassifierError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc

    path = catalogue_path()
    catalogue = load_catalogue_required()
    targets = _select_llm_targets(catalogue, transaction_id=transaction_id, all_pending=all_pending)
    if not targets:
        typer.echo("No transactions selected for LLM classification.")
        return

    total = len(targets)
    updated_catalogue = catalogue
    successes = 0
    failures = 0
    stopped_early = False
    started = time.monotonic()
    for index, target in enumerate(targets, start=1):
        if max_total_seconds is not None and time.monotonic() - started >= max_total_seconds:
            stopped_early = True
            typer.echo(
                f"[{index - 1}/{total}] --max-total-seconds reached; keeping {successes} classified so far.",
                err=True,
            )
            break
        prefix = f"[{index}/{total} {target.transaction_id[:16]}]"
        try:
            response = classifier.classify(target)
        except LLMClassifierError as exc:
            failures += 1
            typer.echo(f"{prefix} {provider} error: {exc}", err=True)
            continue
        line = (
            f"{prefix} {response.classification.value} @ {canonical_decimal(response.confidence)} — {response.reason}"
        )
        typer.echo(line)
        if not dry_run:
            try:
                updated_catalogue = set_classification(
                    updated_catalogue,
                    target.transaction_id,
                    classification=response.classification,
                    classified_by=classifier.decided_by,
                    reason=response.reason,
                    confidence=response.confidence,
                )
            except TransactionError as exc:
                failures += 1
                typer.echo(f"{prefix} persist error: {exc}", err=True)
                continue
            try:
                save_transactions(updated_catalogue, path)
            except TransactionError as exc:
                failures += 1
                typer.echo(f"{prefix} save error: {exc}", err=True)
                continue
        successes += 1

    tail = "dry-run" if dry_run else "persisted"
    if stopped_early:
        tail += " (stopped at --max-total-seconds)"
    typer.echo(f"{successes} classified / {failures} failed / {tail}")
    if failures and successes == 0:
        raise typer.Exit(code=2)


def _select_llm_targets(
    catalogue: TransactionCatalogue,
    *,
    transaction_id: str | None,
    all_pending: bool,
) -> list[Transaction]:
    """Return the transactions the classify-llm command should process."""
    if transaction_id is not None:
        transaction = find_transaction(catalogue, transaction_id)
        if transaction is None:
            typer.echo(f"transaction not found: {transaction_id}", err=True)
            raise typer.Exit(code=2)
        return [transaction]
    return [tx for tx in catalogue.values() if not is_classified(tx.business_classification)]


def _parse_confidence_threshold(value: str | None) -> Decimal | None:
    """Parse and range-check the ``--confidence-below`` option value."""
    if value is None:
        return None
    try:
        threshold = Decimal(value)
    except InvalidOperation as exc:
        typer.echo(f"invalid --confidence-below value: {value}", err=True)
        raise typer.Exit(code=2) from exc
    if not _CONFIDENCE_MIN <= threshold <= _CONFIDENCE_MAX:
        typer.echo("--confidence-below must be within the inclusive 0..1 range", err=True)
        raise typer.Exit(code=2)
    return threshold


def _parse_confidence_option(value: str | None) -> Decimal | None:
    """Parse and range-check the ``--confidence`` option value."""
    if value is None:
        return None
    try:
        resolved = Decimal(value)
    except InvalidOperation as exc:
        typer.echo(f"invalid --confidence value: {value}", err=True)
        raise typer.Exit(code=2) from exc
    if not _CONFIDENCE_MIN <= resolved <= _CONFIDENCE_MAX:
        typer.echo("--confidence must be within the inclusive 0..1 range", err=True)
        raise typer.Exit(code=2)
    return resolved


def _matches_filters(
    transaction: Transaction,
    *,
    state: BusinessClassification | None,
    threshold: Decimal | None,
) -> bool:
    """Return whether a transaction passes the current list filters (AND semantics)."""
    if state is not None and transaction.business_classification is not state:
        return False
    if threshold is not None:
        current = transaction.classification_confidence
        if current is None or current >= threshold:
            return False
    return True


def _format_optional_decimal(value: Decimal | None) -> str:
    """Render an optional ``Decimal`` for CLI tables, empty string for None."""
    if value is None:
        return ""
    return canonical_decimal(value)
