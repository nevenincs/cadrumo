from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

import typer

from ...application.review import EditParseError, FilterParseError, LedgerEditSpec, LedgerReviewFilterSpec
from ...application.user_cli import (
    LedgerSplit,
    UserCliState,
    state_repository,
    update_ledger_review,
)
from ...domain.transactions import (
    Transaction,
    TransactionDirection,
)
from ._v6_common import (
    _bad,
    _canonical_period,
    _emit,
    _fmt_decimal,
    _load_transactions,
    _state,
    _tx_repo,
)

app = typer.Typer(
    name="ledger",
    help="Transaction ledger: import, review, edit.",
    no_args_is_help=True,
)


def _direction_resolver(raw: Any) -> TransactionDirection:
    """Resolve a raw transaction's :class:`TransactionDirection` from amount sign."""
    return TransactionDirection.OUTGOING if raw.amount < 0 else TransactionDirection.INCOMING


@app.command("import", help="Import a bank statement / invoice file into the ledger.")
def ledger_import(
    ctx: typer.Context,
    path: Path = typer.Argument(..., help="Source file path."),
    provider: str = typer.Option(..., "--provider", help="Provider id (n26, csv, ofx, xlsx, pdf, auto)."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Parse only; do not persist."),
    verify: bool = typer.Option(False, "--verify", help="Run import-time diagnostics (gap / duplicate)."),
    source: Path | None = typer.Option(
        None, "--source", help="Original source-file path for original-file diagnostics."
    ),
    verbose: bool = typer.Option(False, "--verbose", help="Emit verbose diagnostic detail."),
    period: str | None = typer.Option(None, "--period", help="Optional period hint for diagnostics."),
) -> None:
    """Import a financial-statement file via the existing provider registry."""
    from ...adapters.inbound.financial.providers import (
        CsvProvider,
        OfxProvider,
        PdfN26Provider,
        XlsxProvider,
        detect_provider,
    )

    pid = provider.strip().lower()
    if pid == "auto":
        chosen = detect_provider(path)
        if chosen is None:
            raise _bad(f"could not auto-detect provider for {path}")
    elif pid in {"csv"}:
        chosen = CsvProvider()
    elif pid in {"ofx", "qfx"}:
        chosen = OfxProvider()
    elif pid in {"xlsx", "excel"}:
        chosen = XlsxProvider()
    elif pid == "n26":
        chosen = detect_provider(path)
        if chosen is None:
            raise _bad(f"could not auto-detect N26 format for {path}")
    elif pid in {"pdf", "pdf-n26"}:
        chosen = PdfN26Provider()
    else:
        raise _bad(f"unknown provider {provider!r}; allowed: auto, csv, ofx, xlsx, n26")
    raws = list(chosen.ingest(path))
    if dry_run:
        payload = {"rows": len(raws), "imported": 0, "skipped": 0, "dry_run": True, "verify": verify}
        _emit(ctx, payload, [f"rows\t{len(raws)}", "dry_run\tyes"])
        return
    summary = _tx_repo().merge_raw_transactions(raws, direction_resolver=_direction_resolver)
    payload = {
        "rows": len(raws),
        "imported": summary.imported,
        "skipped": summary.skipped,
        "dry_run": False,
        "verify": verify,
        "period": _canonical_period(period) if period else None,
    }
    _emit(
        ctx,
        payload,
        [
            f"rows\t{len(raws)}",
            f"imported\t{summary.imported}",
            f"skipped\t{summary.skipped}",
        ],
    )


@app.command("review", help="List ledger rows, optionally filtered, or show one row.")
def ledger_review(
    ctx: typer.Context,
    filters: list[str] = typer.Option([], "--filter", help="--filter KEY=VALUE (status, period, issue, import)."),
    record_id: str | None = typer.Option(None, "--id", help="Show one row in detail."),
    verbose: bool = typer.Option(False, "--verbose", help="Show row provenance and edit history."),
) -> None:
    """Render rows or a single row using the typed filter spec."""
    try:
        spec = LedgerReviewFilterSpec.from_strings(filters)
    except FilterParseError as exc:
        raise _bad(f"--filter parse error ({exc.reason}): {exc.raw_token}")
    catalogue = _load_transactions()
    state = _state()
    rows: list[Transaction] = list(catalogue.transactions.values())
    if spec.period:
        canonical = _canonical_period(spec.period)
        rows = [tx for tx in rows if (tx.raw.value_date or tx.raw.booked_date).isoformat().startswith(canonical[:4])]
    if spec.status is not None:
        rows = [tx for tx in rows if _ledger_row_status(tx, state) == spec.status.value]
    if record_id is not None:
        for tx in rows:
            if tx.transaction_id == record_id:
                review = state.ledger_reviews.get(record_id)
                amount_val = tx.raw.amount
                if review and "amount" in review.fields:
                    amount_val = Decimal(review.fields["amount"])

                payload = {
                    "id": tx.transaction_id,
                    "date": (tx.raw.value_date or tx.raw.booked_date).isoformat(),
                    "amount": _fmt_decimal(amount_val),
                    "description": tx.raw.description,
                    "review": review,
                    "verbose": verbose,
                }
                _emit(
                    ctx,
                    payload,
                    [
                        f"id\t{tx.transaction_id}",
                        f"date\t{(tx.raw.value_date or tx.raw.booked_date).isoformat()}",
                        f"amount\t{_fmt_decimal(amount_val)}",
                        f"description\t{tx.raw.description}",
                    ],
                )
                return
        raise _bad(f"row {record_id!r} not found")
    payload = {
        "rows": [
            {
                "id": tx.transaction_id,
                "date": (tx.raw.value_date or tx.raw.booked_date).isoformat(),
                "amount": format(tx.raw.amount, "f"),
                "description": tx.raw.description,
                "status": _ledger_row_status(tx, state),
            }
            for tx in rows
        ],
        "filters": list(spec.clauses),
    }
    lines: list[str] = ["id\tdate\tamount\tdescription\tstatus"]
    lines.extend(
        f"{tx.transaction_id[:8]}\t{(tx.raw.value_date or tx.raw.booked_date).isoformat()}\t"
        f"{format(tx.raw.amount, 'f')}\t{tx.raw.description}\t{_ledger_row_status(tx, state)}"
        for tx in rows
    )
    if not rows:
        lines.append("(no rows)")
    _emit(ctx, payload, lines)


def _ledger_row_status(tx: Transaction, state: UserCliState) -> str:
    review = state.ledger_reviews.get(tx.transaction_id)
    if review and review.skipped:
        return "skipped"
    if review and review.fields:
        return "reviewed"
    return "pending"


@app.command("edit", help="Edit one ledger row via --set, --skip, or --split (all gated by --reason).")
def ledger_edit(
    ctx: typer.Context,
    record_id: str = typer.Option(..., "--id", help="Ledger row id."),
    sets: list[str] = typer.Option([], "--set", help="--set KEY=VALUE column override."),
    skip: str | None = typer.Option(None, "--skip", help="--skip true|false."),
    splits: list[str] = typer.Option([], "--split", help="--split SHARE=DECIMAL or --split clear."),
    reason: str = typer.Option(..., "--reason", help="Audit-trail reason for the edit."),
) -> None:
    """Apply a typed edit to one ledger row."""
    catalogue = _load_transactions()
    if record_id not in catalogue.transactions:
        raise _bad(f"row {record_id!r} not found")
    try:
        spec = LedgerEditSpec.from_strings(sets)
    except EditParseError as exc:
        raise _bad(f"--set parse error ({exc.reason}): {exc.raw_token}")
    fields: dict[str, str] = {}
    if spec.category is not None:
        fields["category"] = spec.category
    if spec.business_share is not None:
        fields["business.share"] = format(spec.business_share, "f")
    if spec.reference is not None:
        fields["reference"] = spec.reference
    if spec.comments is not None:
        fields["comments"] = spec.comments
    if spec.document_path is not None:
        fields["document.path"] = str(spec.document_path)

    skip_flag: bool | None = None
    if skip is not None:
        skip_normalised = skip.strip().lower()
        if skip_normalised in {"true", "yes", "1"}:
            skip_flag = True
        elif skip_normalised in {"false", "no", "0"}:
            skip_flag = False
        else:
            raise _bad("--skip accepts true|false")

    split_value: LedgerSplit | None = None
    clear_split = False
    if splits:
        if len(splits) == 1 and splits[0].strip().lower() == "clear":
            clear_split = True
        else:
            shares: dict[str, Decimal] = {}
            for raw in splits:
                if "=" not in raw:
                    raise _bad(f"--split expects SHARE=DECIMAL; got {raw!r}")
                k, _, v = raw.partition("=")
                try:
                    shares[k.strip().lower()] = Decimal(v.strip())
                except Exception as exc:
                    raise _bad(f"--split value {v!r} is not a Decimal") from exc
            if "business" not in shares or "personal" not in shares:
                raise _bad("--split requires both business=… and personal=…")
            split_value = LedgerSplit(
                business_share=shares["business"], personal_share=shares["personal"], reason=reason
            )

    if not (fields or skip_flag is not None or split_value is not None or clear_split):
        raise _bad("ledger edit requires at least one of --set, --skip, --split")

    updated = state_repository().update(
        lambda current: update_ledger_review(
            current,
            record_id,
            fields=fields or None,
            skipped=skip_flag,
            split=split_value,
            clear_split=clear_split,
            action="edit",
            reason=reason,
        )
    )
    review = updated.ledger_reviews.get(record_id)
    payload = {"id": record_id, "review": review}
    _emit(
        ctx,
        payload,
        [
            f"id\t{record_id}",
            f"skipped\t{'yes' if review and review.skipped else 'no'}",
            f"fields\t{', '.join(sorted(review.fields)) if review else '-'}",
        ],
    )
